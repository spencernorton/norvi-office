"""Exercise the actual Base/PostgreSQL driver and Calc refresh on an isolated fixture."""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
from zipfile import ZipFile

from model import COLUMNS, REPORT, create_model, datasource_url, load_report, refresh_report
from refresh import update

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "native-header"))
from fixtures import connect, prop, stop_office  # noqa: E402


def docker(*args, **kwargs):
    return subprocess.run(["docker", *args], check=True, text=True, **kwargs)


def sql(container, script):
    return docker("exec", "-i", container, "psql", "-U", "postgres", "-v", "ON_ERROR_STOP=1",
                  input=script, capture_output=True)


def qualify(directory, sample):
    marker = secrets.token_hex(8)
    container = "norvi-office-pg-" + marker
    password = secrets.token_hex(24)
    cert = directory / "server.crt"
    key = directory / "server.key"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                    "-keyout", str(key), "-out", str(cert), "-days", "1",
                    "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost"],
                   check=True, capture_output=True)
    try:
        docker("run", "-d", "--rm", "--pull", "never", "--name", container,
               "-p", "127.0.0.1::5432", "--env", "POSTGRES_PASSWORD",
               "--mount", f"type=bind,src={cert},dst=/fixture/server.crt,readonly",
               "--mount", f"type=bind,src={key},dst=/fixture/server.key,readonly",
               "--entrypoint", "sh", "postgres:17-alpine", "-ec",
               "cp /fixture/server.* /tmp/; chown postgres:postgres /tmp/server.*; chmod 600 /tmp/server.key; "
               "exec docker-entrypoint.sh postgres -c ssl=on -c ssl_cert_file=/tmp/server.crt "
               "-c ssl_key_file=/tmp/server.key",
               env={**os.environ, "POSTGRES_PASSWORD": secrets.token_hex(24)}, capture_output=True)
        for _ in range(100):
            ready = subprocess.run(["docker", "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres"],
                                   capture_output=True)
            if ready.returncode == 0:
                break
            time.sleep(0.15)
        else:
            raise RuntimeError("The PostgreSQL fixture did not start.")
        port = int(docker("port", container, "5432/tcp", capture_output=True).stdout.strip().rsplit(":", 1)[1])
        sql(container, f"""
            CREATE SCHEMA calc_reporting;
            CREATE TABLE categories (id integer PRIMARY KEY, name text NOT NULL);
            CREATE TABLE activity (day date, category_id integer REFERENCES categories(id), minutes numeric);
            INSERT INTO categories VALUES (1,'Film'), (2,'Series');
            INSERT INTO activity VALUES ('2026-01-01',1,40), ('2026-01-01',1,30), ('2026-01-01',2,25);
            CREATE VIEW calc_reporting.daily_activity AS
                SELECT a.day AS activity_day, c.name AS category, count(*) AS plays, sum(a.minutes) AS minutes
                FROM activity a JOIN categories c ON c.id = a.category_id GROUP BY a.day, c.name;
            CREATE ROLE calc_reader LOGIN PASSWORD '{password}';
            ALTER ROLE calc_reader SET default_transaction_read_only = on;
            GRANT USAGE ON SCHEMA calc_reporting TO calc_reader;
            GRANT SELECT ON calc_reporting.daily_activity TO calc_reader;
        """)
        run_office(directory, container, port, cert, password, marker, sample)
    finally:
        subprocess.run(["docker", "rm", "-f", container], capture_output=True)


def run_office(directory, container, port, cert, password, marker, sample):
    pipe = "norvi_model_" + marker
    office = subprocess.Popen(["soffice", "-env:UserInstallation=" + (directory / "profile").as_uri(),
                               "--headless", "--norestore", f"--accept=pipe,name={pipe};urp;"],
                              start_new_session=True)
    try:
        context = connect(pipe)
        manager = context.ServiceManager
        desktop = manager.createInstanceWithContext("com.sun.star.frame.Desktop", context)
        url = datasource_url("localhost", port, "postgres", cert)
        path = directory / "Activity Model.odb"
        base = create_model(context, url, "calc_reader", path)
        base.close(True)
        base = desktop.loadComponentFromURL(path.as_uri(), "_blank", 0, (prop("Hidden", True),))
        source = base.DataSource
        driver = manager.createInstanceWithContext("com.sun.star.sdbc.DriverManager", context)
        wrong_host = datasource_url("127.0.0.1", port, "postgres", cert)
        try:
            mismatch = driver.getConnectionWithInfo(wrong_host, (prop("user", "calc_reader"), prop("password", password)))
        except Exception as error:
            assert "does not match host name" in str(error).lower(), str(error)
        else:
            mismatch.close()
            raise AssertionError("The driver accepted a mismatched certificate hostname.")
        data = load_report(source, password)
        assert data == (("2026-01-01", "Film", 2, 70), ("2026-01-01", "Series", 1, 25)), data
        reader = source.getConnection("calc_reader", password)
        try:
            check = reader.createStatement()
            tls = check.executeQuery("SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()")
            assert tls.next() and tls.getBoolean(1)
            for command in ("SELECT * FROM public.activity", "INSERT INTO public.activity VALUES (now(),1,10)"):
                try:
                    check.execute(command)
                except Exception as error:
                    assert any(message in str(error) for message in
                               ("permission denied for table activity", "read-only transaction")), str(error)
                else:
                    raise AssertionError("The fixture reader reached the base table.")
        finally:
            reader.close()
        workbook = desktop.loadComponentFromURL("private:factory/scalc", "_blank", 0, (prop("Hidden", True),))
        analysis = workbook.Sheets.getByIndex(0)
        analysis.Name = "Analysis"
        analysis.getCellRangeByName("A1").setString("Fictional activity report")
        analysis.getCellRangeByName("A2").setString("Total plays")
        refresh_report(workbook, data)
        analysis.getCellRangeByName("B2").setFormula("=SUM('Warehouse Activity'.C2:C501)")
        assert analysis.getCellRangeByName("B2").Value == 3
        workbook_path = directory / "Activity Report.ods"
        workbook.storeAsURL(workbook_path.as_uri(), (prop("FilterName", "calc8"),))
        workbook.close(True)
        base.close(True)

        sql(container, "DELETE FROM activity WHERE category_id = 2; INSERT INTO activity VALUES ('2026-01-01',1,10);")
        args = SimpleNamespace(host="localhost", port=port, database="postgres", ca=cert,
                               user="calc_reader", model=path, workbook=workbook_path)
        assert update(args, directory / "refresh-profile", password) == 1
        workbook = desktop.loadComponentFromURL(workbook_path.as_uri(), "_blank", 0, (prop("Hidden", True),))
        report = workbook.Sheets.getByName(REPORT)
        assert report.getCellRangeByName("A1:D3").getDataArray() == (
            COLUMNS, ("2026-01-01", "Film", 3, 80), ("", "", "", ""))
        analysis = workbook.Sheets.getByName("Analysis")
        assert analysis.getCellRangeByName("A1").String == "Fictional activity report"
        assert analysis.getCellRangeByName("B2").Value == 3
        workbook.close(True)

        for path in (args.model, workbook_path):
            with ZipFile(path) as package:
                assert all(password.encode() not in package.read(name) for name in package.namelist())
        if sample is not None:
            shutil.copyfile(workbook_path, sample)
        print(json.dumps({"database": "PostgreSQL 17", "verified_tls": True, "base_table_denied": True,
                          "write_denied": True, "report_refresh": True, "stale_rows_removed": True,
                          "analysis_preserved": True}), flush=True)
    finally:
        stop_office(office)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=Path, help="Keep the fictional Calc workbook at this path")
    args = parser.parse_args()
    if args.sample is not None and args.sample.exists():
        parser.error("The sample destination already exists.")
    with tempfile.TemporaryDirectory(prefix="norvi-data-model-") as temporary:
        qualify(Path(temporary), args.sample)
