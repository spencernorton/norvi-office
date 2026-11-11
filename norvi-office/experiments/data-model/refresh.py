"""Refresh a Calc workbook from the saved, bounded PostgreSQL model."""
import argparse
from getpass import getpass
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile

from model import create_model, datasource_url, load_report, refresh_report, setting

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "native-header"))
from fixtures import connect, stop_office  # noqa: E402


def update(args, profile, password):
    pipe = "norvi_data_" + secrets.token_hex(12)
    office = subprocess.Popen(["soffice", "-env:UserInstallation=" + profile.as_uri(),
                               "--headless", "--norestore", f"--accept=pipe,name={pipe};urp;"],
                              start_new_session=True)
    try:
        context = connect(pipe)
        desktop = context.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", context)
        url = datasource_url(args.host, args.port, args.database, args.ca)
        safety = (setting("Hidden", True), setting("MacroExecutionMode", 0), setting("UpdateDocMode", 0))
        if args.model.exists():
            model = desktop.loadComponentFromURL(args.model.as_uri(), "_blank", 0, safety)
            if model is None or not model.supportsService("com.sun.star.sdb.OfficeDatabaseDocument"):
                raise ValueError("The saved Base model could not be opened.")
        else:
            model = create_model(context, url, args.user, args.model)
        try:
            source = model.DataSource
            if source.URL != url or source.User != args.user:
                raise ValueError("The saved model does not match the configured connection.")
            rows = load_report(source, password)
            exists = args.workbook.exists()
            target = args.workbook.as_uri() if exists else "private:factory/scalc"
            workbook = desktop.loadComponentFromURL(target, "_blank", 0, safety)
            if workbook is None or not workbook.supportsService("com.sun.star.sheet.SpreadsheetDocument"):
                raise ValueError("The Calc workbook could not be opened.")
            try:
                refresh_report(workbook, rows)
                if exists:
                    workbook.store()
                else:
                    workbook.storeAsURL(args.workbook.as_uri(),
                                        (setting("FilterName", "calc8"), setting("Overwrite", False)))
            finally:
                workbook.setModified(False)
                workbook.close(True)
        finally:
            model.close(True)
        return len(rows)
    finally:
        stop_office(office)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--database", required=True)
    parser.add_argument("--user", required=True, help="Scoped read-only PostgreSQL user")
    parser.add_argument("--ca", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--workbook", required=True, type=Path)
    args = parser.parse_args()
    args.model = args.model.resolve()
    args.workbook = args.workbook.resolve()
    if args.model.suffix.lower() != ".odb" or args.workbook.suffix.lower() != ".ods":
        parser.error("Use an .odb model and an .ods workbook.")
    password = getpass("Read-only warehouse password: ")
    try:
        with tempfile.TemporaryDirectory(prefix="norvi-data-client-") as path:
            count = update(args, Path(path), password)
    except ValueError as error:
        parser.exit(1, f"{error}\n")
    except Exception:
        parser.exit(1, "LibreOffice could not refresh the model. Check the connection and workbook lock.\n")
    print(f"Refreshed {count} rows in {args.workbook.name}.")


if __name__ == "__main__":
    main()
