#!/usr/bin/python3
"""Opt this user into direct Office desktop launches; retain the original profile."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile

UUID = "norvi-office-preview@norvi.local"
APPS = ("calc", "writer", "impress", "draw", "base", "math", "startcenter")


def preview_shortcuts(home, data, desktop):
    """Retire only unchanged launcher files attributed to the legacy installer.

    Keep the preview runtime, wrappers and manifest so saved work and provenance
    survive and native rollback can restore the preceding launcher arrangement.
    Unknown manifests or individually edited/foreign launchers are never adopted.
    """
    manifest = data / "norvi-office/visual-preview/shortcuts.json"
    if manifest.is_symlink() or not manifest.is_file():
        return []
    try:
        records = json.loads(manifest.read_text())["files"]
        paths = [Path(record["path"]) for record in records]
        shared = {home / ".local/bin/norvi-office-preview", home / ".local/bin/norvi-office-preview-remove",
                  *(data / "applications" / f"norvi-office-preview-{app}.desktop" for app in ("calc", "writer"))}
        complete = shared | {desktop / f"Office Preview - {app}.desktop" for app in ("calc", "writer")}
        if len(paths) != len(set(paths)) or set(paths) not in (shared, complete):
            return []
        selected = []
        for record, target in zip(records, paths):
            if target.suffix != ".desktop" or target.is_symlink() or not target.is_file():
                continue
            if sha(target) == record["sha256"]:
                selected.append(target)
        return selected
    except (OSError, ValueError, KeyError, TypeError):
        return []


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def locations():
    home = Path.home()
    data = Path(os.environ.get("XDG_DATA_HOME", home / ".local/share"))
    return home, data, data / "norvi-office/native-host"


def enabled():
    return ast.literal_eval(subprocess.check_output(["gsettings", "get", "org.gnome.shell", "enabled-extensions"], text=True).replace("@as ", ""))


def activation(add):
    values = [item for item in enabled() if item != UUID]
    if add:
        values.append(UUID)
    subprocess.run(["gsettings", "set", "org.gnome.shell", "enabled-extensions", repr(values)], check=True)


def prune_empty(directory):
    for path in sorted(directory.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_dir():
            try:
                path.rmdir()
            except OSError:
                pass
    try:
        directory.rmdir()
    except OSError:
        pass


def install(candidate):
    home, data, state = locations()
    if state.exists():
        raise ValueError("Desktop integration already exists; use its uninstall command before replacing it")
    candidate = candidate.resolve()
    package_hash = sha(candidate)
    root = data / "norvi-office/desktop-runtime" / package_hash[:16]
    with tempfile.TemporaryDirectory(prefix="office-native-install-") as directory:
        staged = Path(directory)
        subprocess.run(["dpkg-deb", "-x", str(candidate), str(staged)], check=True)
        share = staged / "usr/share/norvi-office"
        library = staged / "usr/lib/x86_64-linux-gnu/norvi-office/libnorvi-office-header.so"
        if not library.is_file() or not (share / "experimental/desktop/launch.py").is_file():
            raise ValueError("Candidate does not contain the direct desktop runtime")
        subprocess.run(["libreoffice", "--version"], check=True, stdout=subprocess.DEVNULL)
        if root.exists():
            for source in staged.rglob("*"):
                if source.is_file():
                    existing = root / source.relative_to(staged)
                    if existing.is_symlink() or not existing.is_file() or sha(existing) != sha(source):
                        raise ValueError("A retained desktop payload changed; preserved it")
        else:
            shutil.copytree(staged, root)
    launch = root / "usr/share/norvi-office/experimental/desktop/launch.py"
    icon = root / "usr/share/norvi-office/startup/assets/office.png"
    wrapper = home / ".local/bin/norvi-office"
    remover = home / ".local/bin/norvi-office-native-uninstall"
    payloads = {
        wrapper: (f'#!/bin/sh\nexec /usr/bin/python3 {shlex.quote(str(launch))} "$@"\n'.encode(), 0o755),
        remover: (f'#!/bin/sh\nexec /usr/bin/python3 {shlex.quote(str(state / "integrate.py"))} --uninstall\n'.encode(), 0o755),
        state / "enabled.json": (json.dumps({"enabled": True, "package_sha256": package_hash}).encode() + b"\n", 0o600),
    }
    desktop_dir = Path(subprocess.check_output(["xdg-user-dir", "DESKTOP"], text=True).strip())
    for app in APPS:
        target = data / "applications" / f"libreoffice-{app}.desktop"
        source = target if target.exists() else Path("/usr/share/applications") / target.name
        if not source.exists():
            continue
        lines = []
        main = False
        for line in source.read_text().splitlines():
            if line.startswith("["):
                main = line == "[Desktop Entry]"
            if main and line.startswith("Name="):
                line = "Name=Office" + (" " + app.title() if app != "startcenter" else "")
            if main and line.startswith("Icon="):
                line = "Icon=" + str(icon)
            # Existing integrated commands already reference the owned wrapper;
            # fallback upstream actions are rewritten without losing URI fields.
            if line.startswith("Exec=") and "libreoffice" in line and "norvi-office" not in line:
                args = shlex.split(line[5:])
                module = next((a[2:] for a in args if a.startswith("--") and a[2:] in ("calc", "writer", "impress", "draw", "base", "math", "startcenter")), app)
                fields = [a for a in args if a in ("%U", "%u", "%F", "%f")]
                line = f'Exec="{wrapper}" --desktop --app {module} ' + " ".join(fields)
            lines.append(line)
        content = ("\n".join(lines) + "\n").encode()
        payloads[target] = (content, 0o644)
        if desktop_dir.is_absolute() and desktop_dir != home:
            name = "Office" if app == "startcenter" else f"Office {app.title()}"
            payloads[desktop_dir / f"{name}.desktop"] = (content, 0o755)
    extension = root / "usr/share/norvi-office/experimental/wayland-glass/extension"
    destination = data / "gnome-shell/extensions" / UUID
    if destination.exists():
        raise ValueError("An existing Office extension is unmanaged; preserved it")
    for source in extension.rglob("*"):
        if source.is_file() and "__pycache__" not in source.parts:
            relative = source.relative_to(extension)
            content = source.read_bytes()
            if relative.as_posix() == "metadata.json":
                metadata = json.loads(content)
                metadata.update(uuid=UUID, name="Norvi Office", description="Glass chrome for directly launched Norvi Office applications")
                content = (json.dumps(metadata, indent=2) + "\n").encode()
            payloads[destination / relative] = (content, 0o644)
    for target, (content, _mode) in payloads.items():
        if target.is_symlink():
            raise ValueError(f"Refusing to replace a symlink: {target.name}")
        if target.suffix == ".desktop":
            with tempfile.TemporaryDirectory() as directory:
                check = Path(directory) / target.name
                check.write_bytes(content)
                subprocess.run(["desktop-file-validate", str(check)], check=True)
    retired = preview_shortcuts(home, data, desktop_dir)
    state.mkdir(parents=True, mode=0o700)
    (state / "backups").mkdir(mode=0o700)
    shutil.copy2(__file__, state / "integrate.py")
    records = []
    for index, (target, (content, mode)) in enumerate(payloads.items()):
        backup = None
        if target.exists():
            backup = str(index)
            shutil.copy2(target, state / "backups" / backup)
        records.append({"path": str(target), "backup": backup, "sha256": hashlib.sha256(content).hexdigest()})
    for target in retired:
        backup = str(len(records))
        shutil.copy2(target, state / "backups" / backup)
        records.append({"path": str(target), "backup": backup, "sha256": sha(target),
                        "removed": True, "desktop": target.parent == desktop_dir})
    manifest = {"runtime": str(root), "files": records, "original_profile": "untouched", "activation": "pending session restart"}
    (state / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    changed = set()
    try:
        for target, (content, mode) in payloads.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + ".norvi-native-tmp")
            temporary.write_bytes(content)
            temporary.chmod(mode)
            temporary.replace(target)
            changed.add(target)
            if target.parent == desktop_dir and target.suffix == ".desktop":
                subprocess.run(["gio", "set", str(target), "metadata::trusted", "true"], check=True)
        for record in records:
            if record.get("removed"):
                target = Path(record["path"])
                if target.is_symlink() or not target.is_file() or sha(target) != record["sha256"]:
                    raise ValueError(f"A preview shortcut changed during installation: {target.name}")
                target.unlink()
                changed.add(target)
        activation(True)
        subprocess.run(["update-desktop-database", str(data / "applications")], check=True)
    except Exception:
        for record in records:
            target = Path(record["path"])
            if target not in changed:
                continue
            if record["backup"] is not None:
                shutil.copy2(state / "backups" / record["backup"], target)
            elif target.is_file() and sha(target) == record["sha256"]:
                target.unlink()
        activation(False)
        prune_empty(destination)
        shutil.rmtree(state)
        raise
    print("Installed direct Office desktop launchers. The new glass extension loads at the next sign-in.")
    print("Original LibreOffice profile retained. Undo: norvi-office-native-uninstall")


def uninstall():
    _home, data, state = locations()
    manifest = json.loads((state / "manifest.json").read_text())
    for record in manifest["files"]:
        target = Path(record["path"])
        if record.get("removed"):
            if target.exists() or target.is_symlink():
                raise ValueError(f"A retired preview shortcut was replaced; preserved all files: {target.name}")
        elif target.is_symlink() or not target.is_file() or sha(target) != record["sha256"]:
            raise ValueError(f"A managed file changed; preserved all files: {target.name}")
    subprocess.run(["gnome-extensions", "disable", UUID], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    activation(False)
    for record in manifest["files"]:
        target = Path(record["path"])
        if record["backup"] is not None:
            shutil.copy2(state / "backups" / record["backup"], target)
            if record.get("desktop"):
                subprocess.run(["gio", "set", str(target), "metadata::trusted", "true"], check=False)
        else:
            target.unlink()
    prune_empty(data / "gnome-shell/extensions" / UUID)
    subprocess.run(["update-desktop-database", str(data / "applications")], check=True)
    shutil.rmtree(state)
    print("Restored previous Office launchers; retained both profiles and all documents. Open apps can be closed normally.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", nargs="?", type=Path)
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args()
    if not args.uninstall and args.candidate is None:
        parser.error("Provide a locally qualified Debian candidate")
    try:
        uninstall() if args.uninstall else install(args.candidate)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Office desktop integration: {error}\n")
