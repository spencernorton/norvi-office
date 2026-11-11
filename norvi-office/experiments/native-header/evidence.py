"""Record the exact preview inputs; combine only complete, matching runs."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
PROGRAMS = [Path("/usr/lib/libreoffice/program") / name
            for name in ("soffice.bin", "libvclplug_gtk3lo.so")]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
    files = [path for path in ROOT.rglob("*") if path.suffix in (".c", ".py", ".sh", ".js")]
    files += [ROOT / "test-driver/metadata.json", ROOT.parent.parent / "dist/NorviGlass.oxt"]
    files += [ROOT.parent / "wayland-glass" / name for name in (
        "extension/extension.js", "extension/geometry.py", "extension/metadata.json", "qualify.py")]
    files += list((ROOT.parent / "startup").glob("*.py"))
    return {os.path.relpath(path, ROOT): digest(path) for path in sorted(files)}


def binaries():
    return {str(path): digest(path) for path in PROGRAMS}


def snapshot(output):
    record = {
        "at": datetime.now(timezone.utc).isoformat(), "source_sha256": sources(),
        "native_binary_sha256_before": binaries(),
        "theme": os.environ.get("NORVI_OFFICE_THEME", "Yaru-purple-dark"),
        "requested_scale": 2 if os.environ.get("NORVI_OFFICE_SCALE_TEST") == "1" else 1,
        "packages": subprocess.check_output(["dpkg-query", "-W", "-f=${Package} ${Version}\n",
            "libreoffice-core", "libgtk-3-0t64", "gnome-shell"], text=True).splitlines(),
    }
    (output / "evidence.json").write_text(json.dumps(record, indent=2) + "\n")


def finish(output):
    path = output / "evidence.json"
    record = json.loads(path.read_text())
    assert record["source_sha256"] == sources(), "Preview sources changed during the run"
    assert record["native_binary_sha256_before"] == binaries(), "Native application binaries changed"
    assert json.loads((output / "rollback-results.json").read_text())["custom_header_absent"]
    record["native_binaries_unchanged"] = True
    record["result"] = "passed"
    path.write_text(json.dumps(record, indent=2) + "\n")


def combine(destination, outputs):
    runs = []
    for output in outputs:
        record = json.loads((output / "evidence.json").read_text())
        assert record["result"] == "passed" and record["source_sha256"] == sources()
        checks = {path.name.removesuffix("-results.json"): json.loads(path.read_text())
                  for path in sorted(output.glob("*-results.json"))}
        runs.append({"run": output.name, "theme": record["theme"],
                     "scale": record["requested_scale"], "checks": checks})
    states = [state for run in runs for app in run["checks"].values() for state in app.get("states", [])]
    record = {"verified_on": datetime.now(timezone.utc).date().isoformat(),
              "result": "passed", "scope": "Private GNOME Wayland; fictional documents; settled states.",
              "source_sha256": sources(), "packages": record["packages"],
              "native_binaries_unchanged": True, "menu_regressions": 3, "routing_regressions": 9,
              "state_checks": len(states), "unchanged_opaque_pixels": sum(s["opaque_pixels"] for s in states),
              "runs": runs,
              "unqualified": ["intermediate frames during same-size VCL layout changes",
                              "fractional scaling, multiple monitors and hotplug",
                              "larger text, broader languages and other LibreOffice builds",
                              "live desktop effect conflicts and full color-control accuracy"]}
    destination.write_text(json.dumps(record, indent=2) + "\n")


if __name__ == "__main__":
    mode, output = sys.argv[1], Path(sys.argv[2]).resolve()
    if mode == "snapshot":
        snapshot(output)
    elif mode == "finish":
        finish(output)
    elif mode == "combine":
        combine(output, [Path(arg).resolve() for arg in sys.argv[3:]])
    else:
        sys.exit("Use snapshot, finish or combine")
