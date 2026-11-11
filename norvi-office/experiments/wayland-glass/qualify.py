"""Exercise geometry and appearance using real clients on the private Wayland display."""
import ast
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from PIL import Image, ImageChops

from extension.geometry import Atspi


def call(method, *args, geometry=False):
    interface = "OfficeGeometry" if geometry else "OfficeTest"
    value = subprocess.check_output([
        "gdbus", "call", "--session", "--dest", "org.gnome.Shell",
        "--object-path", f"/dev/norvi/{interface}",
        "--method", f"dev.norvi.{interface}.{method}", *map(str, args),
    ], text=True)
    return ast.literal_eval(value)


def header(enabled=True, reason=None):
    for _ in range(60):
        entries = json.loads(call("State", geometry=True)[0])
        if len(entries) == 1 and entries[0]["enabled"] == enabled and (
            reason is None or entries[0]["reason"] == reason
        ):
            # Allow a second accessibility report after the compositor resize.
            time.sleep(0.3)
            again = json.loads(call("State", geometry=True)[0])
            if again == entries:
                return entries[0]
        time.sleep(0.1)
    raise AssertionError(f"Header did not settle: {entries}")


def pair(name, enabled=True, reason=None):
    state = header(enabled, reason)
    for pattern in (True, False):
        call("Backdrop", str(pattern).lower())
        time.sleep(0.35)
        call("Capture", f"{name}-{'pattern' if pattern else 'solid'}.png")
    diff = ImageChops.difference(
        Image.open(f"{name}-pattern.png").convert("RGB"),
        Image.open(f"{name}-solid.png").convert("RGB"),
    )
    x, y, width, height = state["frame"]
    _, by, _, _ = state["buffer"]
    top = by + state["edge"] if enabled else y
    content = diff.crop((x + 32, top, x + width - 80, y + height - 60))
    assert content.getbbox() is None, f"{name}: backdrop leaked into opaque area"
    if enabled:
        assert diff.crop((x + 32, top - 3, x + width - 80, top)).getbbox(), f"{name}: missing glass"
    state["name"] = name
    state["opaque_pixels"] = content.width * content.height
    print(f"{name}: edge={top}, {state['opaque_pixels']} opaque pixels unchanged", flush=True)
    call("Backdrop", "true")
    return state


def settle(app):
    """Wait for initial document/ruler redraws before the first backdrop swap."""
    state = header()
    x, y, width, height = state["frame"]
    edge = state["buffer"][1] + state["edge"]
    region = (x + 32, edge, x + width - 80, y + height - 60)
    previous = None
    steady = 0
    for _ in range(30):
        call("Capture", app + "-settle.png")
        current = Image.open(app + "-settle.png").convert("RGB").crop(region)
        steady = steady + 1 if previous and ImageChops.difference(previous, current).getbbox() is None else 0
        if steady >= 3:
            return
        previous = current
        time.sleep(0.3)
    raise AssertionError(app + ": initial work area did not settle")


def setting(schema, key, value):
    subprocess.run(["gsettings", "set", schema, key, value], check=True)


def fixture_control(accessible, name, depth=0):
    """Find a native chrome action in the fictional test client only."""
    if accessible is None or depth > 12 or accessible.get_role() in (
        Atspi.Role.DOCUMENT_TEXT, Atspi.Role.DOCUMENT_SPREADSHEET, Atspi.Role.TABLE,
    ):
        return None
    if accessible.get_name() == name:
        return accessible
    for index in range(min(accessible.get_child_count(), 150)):
        found = fixture_control(accessible.get_child_at_index(index), name, depth + 1)
        if found is not None:
            return found
    return None


def activate(name, scope=None):
    for _ in range(30):
        control = fixture_control(scope if scope is not None else Atspi.get_desktop(0), name)
        if control is not None:
            assert control.get_action_iface().do_action(0), f"Could not activate {name}"
            time.sleep(0.3)
            return
        time.sleep(0.1)
    raise AssertionError(f"Missing native fixture control: {name}")


def single_toolbar():
    x, y, _, _ = header()["frame"]
    call("Click", x + 1278, y + 55)
    time.sleep(0.3)
    activate("User Interface...")
    dialog = fixture_control(Atspi.get_desktop(0), "Select Your Preferred User Interface")
    assert dialog is not None, "Layout chooser did not open"
    activate("Single Toolbar", dialog)
    activate("Apply to Calc", dialog)
    activate("Close", dialog)
    call("Escape")
    call("Place")
    assert not any(window["type"] in (3, 4) for window in json.loads(call("Windows")[0])), (
        "Layout chooser did not close"
    )


def qualify(app):
    results = [pair(f"{app}-adaptive")]
    call("Resize", 1000, 620)
    results.append(pair(f"{app}-narrow"))
    call("WindowState", "maximized")
    results.append(pair(f"{app}-maximized"))
    call("WindowState", "restored")
    call("Place")
    results.append(pair(f"{app}-restored"))
    if app in ("calc", "writer", "impress"):
        # Select Insert through the real notebookbar; the helper must rediscover
        # the work panel without a module/tab height table.
        state = header()
        x, y, _, _ = state["frame"]
        call("Click", x + 445, y + 54)
        time.sleep(0.6)
        results.append(pair(f"{app}-insert"))
    if app == "calc":
        call("WindowState", "fullscreen")
        results.append(pair("calc-fullscreen", False, "window-or-scale"))
        call("WindowState", "normal")
        header()
        setting("org.gnome.desktop.a11y.interface", "high-contrast", "true")
        results.append(pair("calc-contrast", False, "appearance"))
        setting("org.gnome.desktop.a11y.interface", "high-contrast", "false")
        header()
        setting("org.gnome.desktop.interface", "color-scheme", "prefer-light")
        results.append(pair("calc-light", False, "appearance"))
        setting("org.gnome.desktop.interface", "color-scheme", "prefer-dark")
        header()
        # Pausing the helper simulates an unavailable/stalled accessibility bus.
        pid = int(os.environ["NORVI_OFFICE_BRIDGE_PID"])
        os.kill(pid, signal.SIGSTOP)
        try:
            results.append(pair("calc-stale", False, "geometry"))
        finally:
            os.kill(pid, signal.SIGCONT)
        results.append(pair("calc-recovered"))
        before = header()["edge"]
        single_toolbar()
        results.append(pair("calc-single-toolbar"))
        assert results[-1]["edge"] < before, "The header did not follow the shorter toolbar"
    Path(f"{app}-qualification.json").write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    directory = os.environ.get("NORVI_OFFICE_TEST_DIR")
    if not directory or Path(directory).resolve() != Path.cwd() or (
        os.environ.get("XDG_CONFIG_HOME") != str(Path(directory) / "config")
    ):
        raise SystemExit("Run the isolated preview harness.")
    if sys.argv[1] == "--settle":
        settle(sys.argv[2])
    else:
        qualify(sys.argv[1])
