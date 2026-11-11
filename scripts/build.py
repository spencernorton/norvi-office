#!/usr/bin/env python3
"""Build the exact, reproducible Office Debian candidate without root or downloads."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent.parent


def source_files(source):
    prefix = source.relative_to(ROOT).as_posix() + "/"
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    return [ROOT / name for name in names if name.startswith(prefix)]


def copy_source(source, destination, runtime_only=False):
    for path in source_files(source):
        if runtime_only and (path.name.startswith(("test_", "qualify")) or path.name in
                             {"capture.sh", "build.sh", "evidence.py", "fixtures.py", "verify.py", "test_menu.c"}
                             or "test-driver" in path.parts):
            continue
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def extension(source, destination, epoch):
    stamp = datetime.fromtimestamp(max(epoch, 315532800), timezone.utc).timetuple()[:6]
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(source_files(source)):
            if path.is_file():
                info = zipfile.ZipInfo(path.relative_to(source).as_posix(), stamp)
                info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_STORED
                archive.writestr(info, path.read_bytes())


def build(output):
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all"], cwd=ROOT)
    if dirty:
        raise ValueError("Build from a clean committed source tree")
    version = (ROOT / "VERSION").read_text().strip()
    if not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", version):
        raise ValueError("VERSION must be a stable semantic version")
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH") or subprocess.check_output(
        ["git", "log", "-1", "--format=%ct"], cwd=ROOT, text=True).strip())
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    architecture = subprocess.check_output(["dpkg", "--print-architecture"], text=True).strip()
    if architecture != "amd64":
        raise ValueError("Only the qualified Ubuntu amd64 target is supported")
    with tempfile.TemporaryDirectory(prefix="office-build-") as temporary:
        stage = Path(temporary)
        share = stage / "usr/share/norvi-office"
        share.mkdir(parents=True)
        source = ROOT / "norvi-office"
        copy_source(source / "experiments/startup", share / "startup")
        (share / "startup/package-mode").write_text("Shared runtime managed by APT\n")
        experimental = share / "experimental"
        for name in ("native-header", "wayland-glass", "live-tools", "data-model"):
            copy_source(source / "experiments" / name, experimental / name, runtime_only=True)
        modules = stage / "usr/lib/x86_64-linux-gnu/norvi-office"
        modules.mkdir(parents=True)
        flags = subprocess.check_output(["pkg-config", "--cflags", "--libs", "gtk+-3.0", "gmodule-2.0"], text=True).split()
        subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-O2", "-fPIC", "-shared",
                        "-ffile-prefix-map=" + str(ROOT) + "=.", str(source / "experiments/native-header/header.c"),
                        "-o", str(modules / "libnorvi-office-header.so"), *flags], check=True)
        extensions = share / "extensions"
        extensions.mkdir()
        extension(source / "extension", extensions / "NorviGlass.oxt", epoch)
        extension(source / "experiments/live-tools/extension", extensions / "NorviDocumentTools.oxt", epoch)
        shutil.copy2(ROOT / "VERSION", share / "VERSION")
        shutil.copy2(ROOT / "compatibility.json", share / "compatibility.json")
        binary = stage / "usr/bin"
        binary.mkdir(parents=True)
        for command, target in (("norvi-office", "startup/launch.py"), ("norvi-office-integrate", "startup/integrate.py")):
            wrapper = binary / command
            wrapper.write_text('#!/usr/bin/python3\nfrom pathlib import Path\nimport runpy\nrunpy.run_path(str(Path(__file__).resolve().parents[1] / "share/norvi-office/' + target + '"), run_name="__main__")\n')
            wrapper.chmod(0o755)
        applications = stage / "usr/share/applications"
        applications.mkdir()
        shutil.copy2(ROOT / "packaging/norvi-office.desktop", applications / "norvi-office.desktop")
        icons = stage / "usr/share/icons/hicolor/256x256/apps"
        icons.mkdir(parents=True)
        shutil.copy2(ROOT / "packaging/office-256.png", icons / "norvi-office.png")
        docs = stage / "usr/share/doc/norvi-office"
        docs.mkdir(parents=True)
        shutil.copy2(ROOT / "LICENSE", docs / "copyright")
        copy_source(ROOT / "docs", docs / "guides")
        control = stage / "DEBIAN"
        control.mkdir()
        (control / "control").write_text((ROOT / "packaging/control").read_text().replace("@VERSION@", version))
        for path in stage.rglob("*"):
            if path.is_file() and not os.access(path, os.X_OK):
                path.chmod(0o644)
            os.utime(path, (epoch, epoch), follow_symlinks=False)
        package = output / f"norvi-office_{version}_amd64.deb"
        subprocess.run(["dpkg-deb", "--root-owner-group", "--build", str(stage), str(package)], check=True,
                       env={**os.environ, "SOURCE_DATE_EPOCH": str(epoch)})
    (output / "SHA256SUMS.txt").write_text(hashlib.sha256(package.read_bytes()).hexdigest() + "  " + package.name + "\n")
    print(json.dumps({"package": package.name, "version": version, "source_date_epoch": epoch}))
    return package


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "out/candidate")
    build(parser.parse_args().output)
