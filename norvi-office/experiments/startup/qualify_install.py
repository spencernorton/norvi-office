"""Exercise installed desktop shortcuts and exact restore in an isolated home."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
from time import sleep
from unittest.mock import patch

sys.path.insert(0, str(Path(sys.argv[1]).resolve()))
from verify import call, wait  # noqa: E402

ROOT = Path(__file__).resolve().parent
DIRECTORY = Path.cwd()


def qualify():
    home = DIRECTORY / "installed-startup-home"
    home.mkdir()
    data = home / "share"
    applications = data / "applications"
    applications.mkdir(parents=True)
    original = Path("/usr/share/applications/libreoffice-writer.desktop").read_bytes().replace(
        b"Icon=libreoffice-writer\n", b"Icon=custom-existing-writer-icon\n")
    writer = applications / "libreoffice-writer.desktop"
    writer.write_bytes(original)
    environment = {**os.environ, "HOME": str(home), "XDG_DATA_HOME": str(data),
                   "XDG_CONFIG_HOME": str(home / "config"), "XDG_CACHE_HOME": str(home / "cache")}
    command = [sys.executable, str(ROOT / "integrate.py")]
    subprocess.run(command + ["--install"], env=environment, check=True)
    installed = data / "norvi-office/startup"
    shortcuts = sorted(applications.glob("libreoffice-*.desktop"))
    assert len(shortcuts) == 7
    for shortcut in shortcuts:
        subprocess.run(["desktop-file-validate", str(shortcut)], check=True)
    assert subprocess.run(command + ["--install"], env=environment, capture_output=True).returncode != 0
    # A URL must reach Office intact; command construction makes no request.
    spec = importlib.util.spec_from_file_location("installed_office_loader", installed / "launch.py")
    loader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loader)
    url = "https://example.invalid/annual%20plan.xlsx"
    with patch.object(sys, "argv", ["office", "--desktop", "--app", "calc", url]), patch.object(loader, "launch", return_value=0) as launch:
        assert loader.main() == 0
        assert launch.call_args.args[0] == ["libreoffice", "--nologo", "--calc", url]
    fixtures = json.loads((DIRECTORY / "fixtures.json").read_text())
    try:
        for app in ("calc", "writer"):
            document = home / Path(fixtures[app]).name
            shutil.copyfile(fixtures[app], document)
            subprocess.run(["gio", "launch", str(applications / f"libreoffice-{app}.desktop"),
                            document.as_uri()], env=environment, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            wait(lambda: any(window["app"] == "libreoffice-" + app and document.stem in window["title"]
                             for window in json.loads(call("Windows")[0])),
                 f"Installed {app} shortcut did not open the document", seconds=15)
        assert (home / ".config/libreoffice/4/user").is_dir()
    finally:
        groups = set()
        for proc in Path("/proc").glob("[0-9]*"):
            try:
                if (proc / "comm").read_text().strip() in ("oosplash", "soffice.bin"):
                    if ("HOME=" + str(home)).encode() in (proc / "environ").read_bytes().split(b"\0"):
                        groups.add(os.getpgid(int(proc.name)))
            except (OSError, ValueError):
                pass
        for group in groups:
            try:
                os.killpg(group, signal.SIGTERM)
            except ProcessLookupError:
                pass
        sleep(0.2)
        for group in groups:
            try:
                os.killpg(group, signal.SIGKILL)
            except ProcessLookupError:
                pass
    # Refuse a destructive rollback if another program has edited a shortcut.
    calc = applications / "libreoffice-calc.desktop"
    clean = calc.read_bytes()
    calc.write_bytes(clean + b"# subsequent user edit\n")
    before = writer.read_bytes()
    assert subprocess.run(command + ["--uninstall"], env=environment, capture_output=True).returncode != 0
    assert writer.read_bytes() == before
    calc.write_bytes(clean)
    subprocess.run([str(home / ".local/bin/norvi-office-uninstall")], env=environment, check=True)
    assert writer.read_bytes() == original
    assert sorted(path.name for path in applications.glob("*.desktop")) == [writer.name]
    assert not installed.exists()
    assert not (home / ".local/bin/norvi-office").exists()
    print("Office desktop integration: Writer/Calc URI launch and exact rollback passed", flush=True)


if __name__ == "__main__":
    qualify()
