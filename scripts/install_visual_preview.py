#!/usr/bin/python3
"""Install or remove distinct visual-preview shortcuts, preserving normal Office."""
import argparse
import hashlib
import json
from pathlib import Path
import os
import shlex
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def trust_desktop(path):
    subprocess.run(["gio", "set", str(path), "metadata::trusted", "true"], check=True)


def locations():
    home = Path.home()
    data = Path(os.environ.get("XDG_DATA_HOME", home / ".local/share"))
    desktop = Path(subprocess.check_output(["xdg-user-dir", "DESKTOP"], text=True).strip())
    if not desktop.is_absolute() or desktop == home:
        raise ValueError("A separate desktop directory is required for preview icons")
    return home, data, desktop, data / "norvi-office/visual-preview/shortcuts.json"


def expected_paths(home, data, desktop=None):
    return {home / ".local/bin/norvi-office-preview", home / ".local/bin/norvi-office-preview-remove",
            *(data / "applications" / f"norvi-office-preview-{app}.desktop" for app in ("calc", "writer")),
            *((desktop / f"Office Preview - {app}.desktop" for app in ("calc", "writer")) if desktop else ())}


def managed(manifest, home, data, desktop):
    if not manifest.exists():
        if any(path.exists() or path.is_symlink() for path in expected_paths(home, data, desktop)):
            raise ValueError("A preview shortcut already exists outside this installer; preserved it")
        return []
    records = json.loads(manifest.read_text())["files"]
    paths = {Path(r["path"]) for r in records}
    if len(paths) != len(records) or paths not in (expected_paths(home, data), expected_paths(home, data, desktop)):
        raise ValueError("Unrecognized preview shortcut manifest")
    for record in records:
        target = Path(record["path"])
        if target.is_symlink() or not target.is_file() or digest(target) != record["sha256"]:
            raise ValueError(f"A preview shortcut changed after installation; preserved it: {target.name}")
    # Upgrade app-menu-only installs. Adopt an existing desktop copy only when
    # it exactly matches its already verified, managed application entry.
    for app in ("calc", "writer"):
        target = desktop / f"Office Preview - {app}.desktop"
        if target in paths or not (target.exists() or target.is_symlink()):
            continue
        source = data / "applications" / f"norvi-office-preview-{app}.desktop"
        if target.is_symlink() or not target.is_file() or digest(target) != digest(source):
            raise ValueError(f"An unmanaged desktop shortcut already exists; preserved it: {target.name}")
        records.append({"path": str(target), "sha256": digest(target)})
    return records


def install():
    home, data, desktop_directory, manifest = locations()
    managed(manifest, home, data, desktop_directory)
    source = ROOT / "norvi-office/experiments"
    files = sorted(path for name in ("native-header", "wayland-glass", "preview")
                   for path in (source / name).rglob("*")
                   if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc")
    fingerprint = hashlib.sha256()
    for path in files:
        fingerprint.update(path.relative_to(source).as_posix().encode() + b"\0" + path.read_bytes())
    payload = manifest.parent / fingerprint.hexdigest()[:16]
    for path in files:
        target = payload / "experiments" / path.relative_to(source)
        if target.exists():
            if digest(path) != digest(target):
                raise ValueError("An existing preview source file was changed; preserved it")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    shutil.copy2(__file__, payload / "install_visual_preview.py")
    launch = payload / "experiments/preview/launch.py"
    binary = home / ".local/bin/norvi-office-preview"
    remove = home / ".local/bin/norvi-office-preview-remove"
    contents = {
        binary: (f'#!/bin/sh\nexec /usr/bin/python3 {shlex.quote(str(launch))} "$@"\n', 0o755),
        remove: (f'#!/bin/sh\nexec /usr/bin/python3 {shlex.quote(str(payload / "install_visual_preview.py"))} --uninstall\n', 0o755),
    }
    quoted = '"' + str(binary).replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`") + '"'
    for app in ("calc", "writer"):
        desktop = ("[Desktop Entry]\nType=Application\nVersion=1.0\n"
                   f"Name=Office Preview — {app.title()}\nComment=Glass header and ribbon design preview\n"
                   "Icon=/usr/share/norvi-office/startup/assets/office.png\n"
                   f"Exec={quoted} --show-errors --app {app}\nTerminal=false\nStartupNotify=true\nCategories=Office;\n")
        contents[data / "applications" / f"norvi-office-preview-{app}.desktop"] = (desktop, 0o644)
        contents[desktop_directory / f"Office Preview - {app}.desktop"] = (desktop, 0o755)
    # Validate both new desktop entries before replacing any shortcuts.
    for target, (text, _mode) in contents.items():
        if target.suffix == ".desktop":
            check = payload / target.name
            check.write_text(text)
            subprocess.run(["desktop-file-validate", str(check)], check=True)
            check.unlink()
    records = []
    for target, (text, mode) in contents.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".preview-tmp")
        temporary.write_text(text)
        temporary.chmod(mode)
        temporary.replace(target)
        records.append({"path": str(target), "sha256": digest(target)})
    manifest.write_text(json.dumps({"payload": str(payload), "files": records}, indent=2) + "\n")
    for target in contents:
        if target.parent == desktop_directory:
            trust_desktop(target)
    subprocess.run(["update-desktop-database", str(data / "applications")], check=True)
    print("Installed Office Preview — Calc and Office Preview — Writer on the desktop and in the app menu")
    print("Undo: norvi-office-preview-remove (preview documents are retained)")


def uninstall():
    home, data, desktop, manifest = locations()
    records = managed(manifest, home, data, desktop)
    for record in records:
        Path(record["path"]).unlink()
    manifest.unlink(missing_ok=True)
    subprocess.run(["update-desktop-database", str(data / "applications")], check=True)
    print("Removed visual-preview shortcuts; retained preview workspaces and documents")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uninstall", action="store_true")
    arguments = parser.parse_args()
    try:
        uninstall() if arguments.uninstall else install()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Office Preview shortcuts: {error}\n")
