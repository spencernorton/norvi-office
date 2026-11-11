"""Verify the actual startup prompt against a cold Calc launch."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
from time import sleep

from PIL import Image, ImageChops

sys.path.insert(0, str(Path(sys.argv[1]).resolve()))
from verify import applications, call, find, wait  # noqa: E402


def qualify(mode):
    directory = Path.cwd()
    assert str(directory) == os.environ["NORVI_OFFICE_TEST_DIR"]
    program = Path(__file__).resolve().with_name("launch.py")
    files = json.loads(Path("fixtures.json").read_text())
    profile = directory / ("startup-" + mode)
    document = directory / f"Ember Plan {mode}.ods"
    shutil.copyfile(files["calc"], document)
    shim = directory / "startup-fixture-bin"
    shim.mkdir(exist_ok=True)
    # Simulate a slow cold start while still opening the actual document.
    binary = shim / "libreoffice"
    binary.write_text('#!/bin/sh\nsleep 3.8\nexec /usr/bin/libreoffice "$@"\n')
    binary.chmod(0o700)
    environment = {**os.environ, "PATH": str(shim) + os.pathsep + os.environ["PATH"]}
    call("DismissOverview")
    client = subprocess.Popen([sys.executable, str(program), "--profile",
                               str(profile), "--app", "calc", str(document)],
                              env=environment, start_new_session=True)

    def windows():
        return json.loads(call("Windows")[0])

    try:
        def office_window():
            return next((window for window in windows() if window["title"] == "office"), None)

        wait(office_window, "Startup prompt did not appear", seconds=5)
        def loading_indicator():
            for app in applications():
                if app is not None and app.get_name() != "soffice":
                    if indicator := find(app, "Loading"):
                        return indicator.get_role_name()
            return None

        role = wait(loading_indicator, "The accessible loading indicator did not appear")
        assert role in (("animation",) if mode == "animated" else ("image", "icon")), role
        # Allow compositor mapping to settle before comparing activity pixels.
        sleep(0.3)
        call("Capture", f"office-startup-{mode}.png")
        if mode == "animated":
            frames = []
            for frame_id in "abcdefghijklmn":
                name = f"office-spinner-{frame_id}.png"
                call("Capture", name)
                with Image.open(name) as capture:
                    frames.append(capture.convert("RGB"))
                sleep(0.07)
            # Crop using the settled position after recording the entrance.
            prompt = office_window()
            assert prompt is not None
            x, y, width, height = prompt["frame"]
            bounds = (x - 16, y - 16, x + width + 16, y + height + 16)
            frames = [frame.crop(bounds) for frame in frames]
            changes = [ImageChops.difference(frames[0], frame).getbbox() for frame in frames[1:]]
            assert any(changes), "The loading line did not animate"
            # The icon and wordmark must stay still; only the 3 px line changes.
            for changed in filter(None, changes):
                assert changed[2] - changed[0] <= 136 and changed[3] - changed[1] <= 3, changed
            frames[0].save("office-startup.gif", save_all=True, append_images=frames[1:],
                           duration=[105] * (len(frames) - 1) + [240], loop=0)
        else:
            sleep(0.25)
            call("Capture", "office-startup-reduced-later.png")
            x, y, width, height = office_window()["frame"]
            bounds = (x, y, x + width, y + height)
            with Image.open("office-startup-reduced.png") as first, Image.open("office-startup-reduced-later.png") as later:
                assert ImageChops.difference(first.crop(bounds).convert("RGB"),
                                            later.crop(bounds).convert("RGB")).getbbox() is None
        wait(lambda: client.poll() is not None, "Startup launcher did not finish")
        assert client.returncode == 0
        final = windows()
        assert not any(window["title"] == "office" for window in final)
        wait(lambda: any(window["app"] == "libreoffice-calc" and "Ember Plan" in window["title"]
                         for window in windows()), "Calc document did not finish mapping", seconds=3)
        print(f"Office startup ({mode}): branded prompt closed on the Calc document", flush=True)
    finally:
        # Match the unique fixture profile, including the subprocess that owns its window.
        uri = profile.as_uri().encode()
        expected = b"-env:UserInstallation=" + uri
        for path in Path("/proc").glob("[0-9]*/cmdline"):
            try:
                arguments = path.read_bytes().split(b"\0")
                programs = (b"/soffice.bin", b"/soffice", b"/oosplash", b"/libreoffice")
                if expected in arguments and any(arg.endswith(programs) for arg in arguments[:2]):
                    os.killpg(os.getpgid(int(path.parent.name)), signal.SIGTERM)
            except (OSError, ValueError):
                continue
        if client.poll() is None:
            client.terminate()
            client.wait(5)


if __name__ == "__main__":
    for mode, setting in (("animated", "true"), ("reduced", "false")):
        subprocess.run(["gsettings", "set", "org.gnome.desktop.interface", "enable-animations", setting], check=True)
        qualify(mode)

    subprocess.run([sys.executable, str(Path(__file__).with_name("qualify_install.py")), sys.argv[1]], check=True)
