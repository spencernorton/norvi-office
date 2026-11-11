#!/usr/bin/python3
"""Open the actual experimental Office UI in a separate visible workspace."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import subprocess
import tempfile
import time

HERE = Path(__file__).resolve().parent


def preview_environment(directory, parent):
    environment = dict(parent)
    for key in ("DISPLAY", "DBUS_SESSION_BUS_ADDRESS", "AT_SPI_BUS_ADDRESS", "GTK3_MODULES",
                "GTK_MODULES", "LD_PRELOAD", "GSETTINGS_BACKEND", "GDK_SCALE", "GDK_DPI_SCALE"):
        environment.pop(key, None)
    runtime = Path(parent.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    display = Path(parent.get("WAYLAND_DISPLAY", "wayland-0"))
    if not display.is_absolute():
        display = runtime / display
    if not stat.S_ISSOCK(display.stat().st_mode):
        raise ValueError("A running Wayland desktop is required")
    environment["WAYLAND_DISPLAY"] = str(display)
    # AT-SPI creates additional Unix sockets: long persistent workspace paths
    # exceed the socket path limit. Keep only the ephemeral runtime short.
    short_runtime = Path(tempfile.mkdtemp(prefix="office-preview-", dir=runtime))
    (directory / "runtime").symlink_to(short_runtime, target_is_directory=True)
    environment["XDG_RUNTIME_DIR"] = str(short_runtime)
    for variable, name in (("XDG_CONFIG_HOME", "config"),
                           ("XDG_DATA_HOME", "data"), ("XDG_CACHE_HOME", "cache"),
                           ("XDG_STATE_HOME", "state")):
        path = directory / name
        path.mkdir(mode=0o700)
        environment[variable] = str(path)
    environment.update(NORVI_OFFICE_TEST_DIR=str(directory), GIO_USE_VFS="local",
                       NORVI_OFFICE_HEADER_TOKEN=secrets.token_hex(32))
    return environment


def launch(app):
    for program in ("pipewire", "wireplumber", "pw-dump"):
        subprocess.run([program, "--version"], check=True, stdout=subprocess.DEVNULL)
    installed = Path("/usr/share/norvi-office")
    contract = json.loads((installed / "compatibility.json").read_text())["experimental_native_adapter"]
    version = subprocess.check_output(["libreoffice", "--version"], text=True).split()[1]
    if version not in contract["libreoffice_versions"]:
        raise ValueError("This LibreOffice version is not qualified for the visual preview")
    shell = subprocess.check_output(["gnome-shell", "--version"], text=True).split()[-1].split(".")[0]
    if shell not in contract["gnome_shell_versions"]:
        raise ValueError("This GNOME Shell version is not qualified for the visual preview")
    source = HERE.parent / "native-header/header.c"
    packaged = installed / "experimental/native-header/header.c"
    if hashlib.sha256(source.read_bytes()).digest() != hashlib.sha256(packaged.read_bytes()).digest():
        raise ValueError("The installed native adapter does not match this preview source")
    workspace = Path.home() / ".local/state/norvi-office/previews"
    workspace.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory = Path(tempfile.mkdtemp(prefix="capture.preview-", dir=workspace))
    environment = preview_environment(directory, os.environ)
    environment["NORVI_OFFICE_PREVIEW_APP"] = app
    # This versioned adapter flag also selects the shared header artwork.
    # The compositor limits the ribbon panel itself to Calc.
    environment["NORVI_OFFICE_CALC_RIBBON"] = "1"
    environment["NORVI_OFFICE_INTERACTIVE_PREVIEW"] = "1"
    environment["NORVI_OFFICE_ANIMATIONS"] = subprocess.check_output(
        ["gsettings", "get", "org.gnome.desktop.interface", "enable-animations"], text=True).strip()
    environment["NORVI_OFFICE_WALLPAPER"] = ast.literal_eval(subprocess.check_output(
        ["gsettings", "get", "org.gnome.desktop.background", "picture-uri-dark"], text=True).strip())
    environment["NORVI_OFFICE_PREVIEW_LIBRARY"] = "/usr/lib/x86_64-linux-gnu/norvi-office/libnorvi-office-header.so"
    environment["NORVI_OFFICE_PREVIEW_OXT"] = "/usr/share/norvi-office/extensions/NorviGlass.oxt"
    with (directory / "session.log").open("w") as log:
        process = subprocess.Popen(["dbus-run-session", "--", "bash", str(HERE / "session.sh")],
                                   env=environment, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    record = {"app": app, "directory": str(directory), "pid": process.pid}
    (workspace / f"latest-{app}.json").write_text(json.dumps(record) + "\n")
    until = time.monotonic() + 60
    while time.monotonic() < until:
        if (directory / "ready.json").exists():
            ready = json.loads((directory / "ready.json").read_text())
            if not ready.get("viewer", {}).get("mapped"):
                raise RuntimeError("The preview document is ready but its host viewer is not visible")
            print(json.dumps({**record, "ready": True, "viewer": ready["viewer"]}))
            return
        if process.poll() is not None:
            break
        time.sleep(0.2)
    raise RuntimeError(f"Preview did not become ready. See {directory / 'session.log'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", choices=("calc", "writer"), default="calc")
    parser.add_argument("--show-errors", action="store_true", help="Show launch failures on the desktop")
    arguments = parser.parse_args()
    try:
        launch(arguments.app)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        if arguments.show_errors:
            import gi
            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk
            if Gtk.init_check()[0]:
                dialog = Gtk.MessageDialog(message_type=Gtk.MessageType.ERROR,
                                          buttons=Gtk.ButtonsType.CLOSE,
                                          text="Office Preview couldn’t start")
                dialog.format_secondary_text(str(error))
                dialog.run()
                dialog.destroy()
        parser.exit(1, f"Office Preview: {error}\n")


if __name__ == "__main__":
    main()
