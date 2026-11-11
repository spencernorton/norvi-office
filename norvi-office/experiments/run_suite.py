"""Repeatable LibreOffice qualification with logs and JUnit output."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
from time import monotonic
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
PYTHON = "/usr/bin/python3"


def cases(tier, output):
    yield "geometry", [PYTHON, "-m", "unittest", "test_geometry"], ROOT / "wayland-glass", {}
    yield "formats", [PYTHON, "live-tools/qualify_formats.py"], ROOT, {}
    if tier == "quick":
        return
    package = output / "NorviDocumentTools.oxt"
    yield "build-extension", [PYTHON, "live-tools/build.py", str(package)], ROOT, {}
    yield "postgres-model", [PYTHON, "data-model/qualify.py", "--sample",
                             str(output / "Activity Report.ods")], ROOT, {}
    apps = "calc writer" if tier == "standard" else "calc writer impress draw math base"
    yield "wayland-native", ["bash", "native-header/capture.sh"], ROOT, {
        "NORVI_OFFICE_APPS": apps, "NORVI_OFFICE_LIVE_TOOLS_OXT": str(package),
        "NORVI_OFFICE_CALC_RIBBON": "1", "NORVI_OFFICE_STARTUP_TEST": "1",
    }
    if tier == "full":
        for name, env in (
            ("light", {"NORVI_OFFICE_THEME": "Yaru-purple"}),
            ("high-contrast", {"NORVI_OFFICE_THEME": "HighContrast"}),
            ("scale-2x", {"NORVI_OFFICE_SCALE_TEST": "1"}),
        ):
            yield f"wayland-{name}", ["bash", "native-header/capture.sh"], ROOT, {
                **env, "NORVI_OFFICE_APPS": "calc", "NORVI_OFFICE_CALC_RIBBON": "1",
            }
        yield "timed-autosave", ["xvfb-run", "-a", "dbus-run-session", "--", PYTHON,
                                 "live-tools/qualify_formats.py", "--autosave"], ROOT, {"GIO_USE_VFS": "local"}


def run(tier, output):
    environment = {key: value for key, value in os.environ.items() if not key.startswith("NORVI_OFFICE_")}
    result = []
    junit = ET.Element("testsuite", name="norvi-office")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    print(f"LibreOffice suite {tier}: {output}", flush=True)
    for name, argv, cwd, extra in cases(tier, output):
        log = output / f"{name}.log"
        started = monotonic()
        with log.open("w") as stream:
            try:
                status = subprocess.run(argv, cwd=cwd, env={**environment, **extra}, stdout=stream,
                                        stderr=subprocess.STDOUT).returncode
            except OSError as error:
                print(str(error), file=stream)
                status = 127
        elapsed = round(monotonic() - started, 3)
        result.append({"case": name, "exit": status, "seconds": elapsed, "log": log.name})
        case = ET.SubElement(junit, "testcase", name=name, time=str(elapsed))
        if status:
            ET.SubElement(case, "failure", message=f"Exit {status}. See {log.name}")
        ET.SubElement(case, "system-out").text = log.name
        print(f"{'PASS' if status == 0 else 'FAIL'} {name} ({elapsed:.1f}s)", flush=True)
    failures = sum(row["exit"] != 0 for row in result)
    junit.attrib.update(tests=str(len(result)), failures=str(failures))
    ET.ElementTree(junit).write(output / "junit.xml", encoding="utf-8", xml_declaration=True)
    (output / "summary.json").write_text(json.dumps({
        "tier": tier, "revision": revision, "failures": failures, "cases": result,
    }, indent=2) + "\n")
    return int(bool(failures))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tier", choices=("quick", "standard", "full"), default="standard")
    parser.add_argument("--output", type=Path, help="New directory for results")
    args = parser.parse_args()
    if args.output:
        output = args.output.resolve()
        output.mkdir(mode=0o700)
    else:
        output = Path(tempfile.mkdtemp(prefix="norvi-office-suite-"))
    return run(args.tier, output)


if __name__ == "__main__":
    raise SystemExit(main())
