#!/usr/bin/python3
"""Install or remove the Office startup integration for the current user."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess

MODULES = ("writer", "calc", "impress", "draw", "base", "math", "startcenter")
SOURCE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def paths():
    home = Path.home()
    data = Path(os.environ.get("XDG_DATA_HOME", home / ".local/share"))
    return data / "norvi-office/startup", data / "applications", home / ".local/bin"


def quote(value):
    # Desktop Exec has its own quoting rules; it is not a shell command.
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$") + '"'


def desktop(source, module, launcher, icon):
    output = []
    main = False
    for line in source.splitlines():
        if line.startswith("["):
            main = line == "[Desktop Entry]"
        if main and line.startswith("Icon="):
            line = "Icon=" + str(icon)
        if line.startswith("Exec="):
            args = shlex.split(line[5:])
            if not args or Path(args[0]).name not in ("libreoffice", "soffice"):
                raise ValueError("Unrecognized Office desktop command")
            selected = next((part[2:] for part in args[1:] if part in {"--" + app for app in MODULES}), module)
            rest = [part for part in args[1:] if part != "--" + selected]
            if any(part.startswith("-") for part in rest):
                raise ValueError("Unsupported option in Office desktop command")
            line = "Exec=" + quote(str(launcher)) + " --desktop --app " + selected
            if rest:
                line += " " + " ".join(part if part in ("%U", "%u", "%F", "%f") else quote(part) for part in rest)
        output.append(line)
    return "\n".join(output) + "\n"


def atomic(path, content, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".norvi-tmp")
    temporary.write_text(content)
    temporary.chmod(mode)
    temporary.replace(path)


def refresh(applications):
    subprocess.run(["update-desktop-database", str(applications)], check=True, capture_output=True)


def install():
    root, applications, binary = paths()
    manifest = root / "manifest.json"
    if root.exists():
        raise ValueError("Startup integration already exists; uninstall it before installing another version")
    provenance = json.loads((SOURCE / "assets/provenance.json").read_text())
    if digest(SOURCE / "assets/office.png") != provenance["sha256"]:
        raise ValueError("Office icon does not match its provenance")
    packaged = (SOURCE / "package-mode").exists()
    runtime = SOURCE if packaged else root
    launcher, remover = binary / "norvi-office", binary / "norvi-office-uninstall"
    payloads = {}
    for module in MODULES:
        name = f"libreoffice-{module}.desktop"
        target = applications / name
        source = target if target.exists() else Path("/usr/share/applications") / name
        if source.exists():
            payloads[target] = (desktop(source.read_text(), module, launcher, runtime / "assets/office.png"), 0o644)
    fallback = ('#!/bin/sh\nif [ -f ' + shlex.quote(str(runtime / "launch.py")) + ' ]; then\n'
                + '  exec /usr/bin/python3 ' + shlex.quote(str(runtime / "launch.py")) + ' "$@"\nfi\n'
                + '[ "${1:-}" = --desktop ] || exit 2\nshift\n'
                + '[ "${1:-}" = --app ] || exit 2\nshift\napp="$1"; shift\n'
                + 'if [ "$app" = startcenter ]; then exec libreoffice "$@"; fi\n'
                + 'exec libreoffice "--$app" "$@"\n')
    payloads[launcher] = (fallback, 0o755)
    payloads[remover] = ('#!/bin/sh\nexec /usr/bin/python3 ' + shlex.quote(str(root / "integrate.py")) + ' --uninstall\n', 0o755)
    for target in payloads:
        if target.is_symlink():
            raise ValueError(f"Refusing to replace a symlink: {target}")
    root.mkdir(parents=True, mode=0o700)
    (root / "backups").mkdir(mode=0o700)
    records = []
    try:
        shutil.copy2(SOURCE / "integrate.py", root / "integrate.py")
        if not packaged:
            shutil.copy2(SOURCE / "launch.py", root / "launch.py")
            shutil.copytree(SOURCE / "assets", root / "assets")
        # Validate every shortcut before changing any user files.
        for index, (target, (content, mode)) in enumerate(payloads.items()):
            if target.suffix == ".desktop":
                candidate = root / target.name
                candidate.write_text(content)
                subprocess.run(["desktop-file-validate", str(candidate)], check=True, capture_output=True)
                candidate.unlink()
            record = {"path": str(target), "backup": None, "installed_sha256": hashlib.sha256(content.encode()).hexdigest()}
            if target.exists():
                backup = root / "backups" / str(index)
                shutil.copy2(target, backup)
                record["backup"] = str(backup.relative_to(root))
            records.append(record)
        manifest.write_text(json.dumps({"files": records}, indent=2) + "\n")
        for target, (content, mode) in payloads.items():
            atomic(target, content, mode)
        refresh(applications)
    except Exception:
        # All originals are backed up before the first replacement.
        for record in records:
            target = Path(record["path"])
            if record["backup"]:
                shutil.copy2(root / record["backup"], target)
            elif target.exists() and digest(target) == record["installed_sha256"]:
                target.unlink()
        shutil.rmtree(root)
        raise
    print(f"Installed Office startup integration for {sum(p.suffix == '.desktop' for p in payloads)} shortcuts")
    print(f"Undo: {remover}")


def uninstall():
    root, applications, _binary = paths()
    records = json.loads((root / "manifest.json").read_text())["files"]
    # Check the whole restore before changing anything; preserve later edits.
    for record in records:
        target = Path(record["path"])
        if target.is_symlink() or not target.exists() or digest(target) != record["installed_sha256"]:
            raise ValueError(f"A managed file changed after installation; preserved it: {target}")
    for record in records:
        target = Path(record["path"])
        if record["backup"]:
            shutil.copy2(root / record["backup"], target)
        else:
            target.unlink()
    refresh(applications)
    shutil.rmtree(root)
    print("Restored the previous Office shortcuts and icons")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--install", action="store_true")
    modes.add_argument("--uninstall", action="store_true")
    args = parser.parse_args()
    try:
        uninstall() if args.uninstall else install()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Office integration: {error}\n")


if __name__ == "__main__":
    main()
