#!/usr/bin/python3
"""Qualify render synchronization headlessly; never present this as host evidence."""
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent


def outer(candidate, app):
    parent = Path("/tmp/norvi-office-tests")
    parent.mkdir(exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="capture.native-render-", dir=parent))
    runtime = Path(tempfile.mkdtemp(prefix="office-render-", dir=f"/run/user/{os.getuid()}"))
    env = dict(os.environ, XDG_RUNTIME_DIR=str(runtime), NORVI_OFFICE_TEST_DIR=str(output),
               LIBGL_ALWAYS_SOFTWARE="1", GIO_USE_VFS="local", NORVI_OFFICE_QUAL_APP=app)
    for key in ("DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS", "AT_SPI_BUS_ADDRESS", "GTK3_MODULES"):
        env.pop(key, None)
    for key, name in (("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "data"),
                      ("XDG_CACHE_HOME", "cache"), ("XDG_STATE_HOME", "state")):
        path = output / name
        path.mkdir(mode=0o700)
        env[key] = str(path)
    subprocess.run(["dpkg-deb", "-x", str(candidate.resolve()), str(output / "payload")], check=True)
    print("Headless compositor qualification:", output, flush=True)
    with (output / "session.log").open("w") as log:
        result = subprocess.run(["dbus-run-session", "--", sys.executable, __file__, "--inside", str(output)],
                                env=env, stdout=log, stderr=subprocess.STDOUT)
    print((output / "receipt.json").read_text() if (output / "receipt.json").exists()
          else (output / "session.log").read_text()[-3500:])
    return result.returncode


def inside(output):
    import gi
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio, GLib
    from PIL import Image, ImageChops
    connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    app = os.environ.get("NORVI_OFFICE_QUAL_APP", "calc")

    def call(interface, method, signature=None, *values):
        parameters = GLib.Variant(signature, values) if signature else None
        return connection.call_sync("org.gnome.Shell", "/dev/norvi/" + interface,
            "dev.norvi." + interface, method, parameters, None, 0, 5000, None).unpack()

    def state():
        return next((item for item in json.loads(call("OfficeGeometry", "State")[0]) if item["app"] == app), None)

    def wait(check, message):
        until = time.monotonic() + 35
        while time.monotonic() < until:
            try:
                result = check()
            except GLib.Error:
                result = None
            if result:
                return result
            time.sleep(.15)
        raise AssertionError(message)

    data = Path(os.environ["XDG_DATA_HOME"])
    extensions = data / "gnome-shell/extensions"
    extensions.mkdir(parents=True)
    share = output / "payload/usr/share/norvi-office"
    shutil.copytree(share / "experimental/wayland-glass/extension", extensions / "norvi-office-preview@norvi.local")
    shutil.copytree(HERE.parent / "native-header/test-driver", extensions / "norvi-office-test@norvi.local")
    shutil.copytree(Path.home() / ".local/share/gnome-shell/extensions/blur-my-shell@aunetx", extensions / "blur-my-shell@aunetx")
    marker = data / "norvi-office/native-host/enabled.json"
    marker.parent.mkdir(parents=True)
    marker.write_text('{"qualification":true}\n')
    for schema, key, value in (
        ("org.gnome.shell", "enabled-extensions", "['norvi-office-preview@norvi.local', 'norvi-office-test@norvi.local', 'blur-my-shell@aunetx']"),
        ("org.gnome.desktop.interface", "toolkit-accessibility", "true"),
        ("org.gnome.desktop.interface", "gtk-theme", "Yaru-purple-dark"),
        ("org.gnome.desktop.interface", "color-scheme", "prefer-dark"),
        ("org.gnome.desktop.interface", "enable-animations", "true"),
    ):
        subprocess.run(["gsettings", "set", schema, key, value], check=True)
    with (output / "shell.log").open("w") as log:
        shell = subprocess.Popen(["gnome-shell", "--wayland", "--headless", "--virtual-monitor=1600x1000",
                                  "--wayland-display=norvi-render-test", "--no-x11"], stdout=log, stderr=subprocess.STDOUT)
    native = Path(os.environ["XDG_STATE_HOME"]) / "norvi-office/desktop"
    try:
        wait(lambda: call("OfficeTest", "Screen"), "Headless Shell did not initialize")
        env = dict(os.environ, WAYLAND_DISPLAY="norvi-render-test")
        with (output / "launch.log").open("w") as log:
            subprocess.run([sys.executable, str(share / "experimental/desktop/launch.py"), "--worker", "--app", app],
                           env=env, stdout=log, stderr=subprocess.STDOUT, timeout=60, check=True)
        call("OfficeTest", "Place")
        call("OfficeTest", "WindowState", "(s)", "maximized")
        active = wait(lambda: (s if (s := state()) and s["enabled"] and s["geometry_source"] == "native-render" else None),
                      "Native render geometry never became active")
        samples = []
        x, y, _width, _height = active["frame"]
        for tab, offset in (("Insert", 255), ("Home", 150), ("Layout", 350), ("Home", 150)):
            call("OfficeTest", "Click", "(ii)", x + offset, y + 66)
            start = time.monotonic()
            while time.monotonic() - start < .6:
                s = state()
                samples.append({"tab": tab, "enabled": s["enabled"], "reason": s["reason"], "source": s["geometry_source"]})
                time.sleep(.008)
        assert all(s["enabled"] and s["reason"] == "active" and s["source"] == "native-render" for s in samples), samples
        active = state()
        paths = []
        for pattern, name in ((True, "native-pattern.png"), (False, "native-final.png")):
            call("OfficeGeometry", "ProbeBackdrop", "(ub)", active["window_id"], pattern)
            time.sleep(.3)
            call("OfficeGeometry", "CaptureNative", "(us)", active["window_id"], name)
            paths.append(Path(os.environ["XDG_STATE_HOME"]) / "norvi-office/native-evidence" / name)
        first, second = [Image.open(path).convert("RGB") for path in paths]
        frame, buffer = active["frame"], active["buffer"]
        edge = buffer[1] + active["edge"] - frame[1]
        differences = {}
        for label, box in (("header", (80, 8, first.width - 80, edge - 8)),
                           ("body", (80, max(350, edge + 150), first.width - 80, first.height - 100))):
            delta = ImageChops.difference(first.crop(box), second.crop(box))
            differences[label] = sum(max(pixel) > 0 for pixel in delta.get_flattened_data())
        assert differences["header"] > 1000 and differences["body"] == 0, differences
        result = {"kind": "headless qualification; not physical host evidence", "app": app, "render_source": active["geometry_source"],
                  "tab_samples": len(samples), "opaque_or_transition_samples": 0, "backdrop_changed_pixels": differences,
                  "geometry": active}
        (output / "receipt.json").write_text(json.dumps(result, indent=2) + "\n")
    finally:
        if (native / "running.json").exists():
            record = json.loads((native / "running.json").read_text())
            for key in ("broker", "geometry"):
                try:
                    os.kill(record[key], signal.SIGTERM)
                except ProcessLookupError:
                    pass
            try:
                os.killpg(record["office_group"], signal.SIGTERM)
            except ProcessLookupError:
                pass
        shell.terminate()
        shell.wait(timeout=15)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", nargs="?", type=Path)
    parser.add_argument("--inside", type=Path)
    parser.add_argument("--app", choices=("calc", "writer"), default="calc")
    arguments = parser.parse_args()
    if arguments.inside:
        inside(arguments.inside)
    elif arguments.candidate:
        raise SystemExit(outer(arguments.candidate, arguments.app))
    else:
        parser.error("Provide a locally built candidate")
