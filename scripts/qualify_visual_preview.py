#!/usr/bin/python3
"""Exercise the exact visible preview without reading a normal Office session."""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import unquote, urlsplit

directory = Path(sys.argv[1]).resolve()
if not directory.name.startswith("capture.preview-"):
    raise SystemExit("Provide the isolated visual-preview workspace")
os.environ["DBUS_SESSION_BUS_ADDRESS"] = (directory / "session-address").read_text()
os.environ["XDG_RUNTIME_DIR"] = str((directory / "runtime").resolve())
os.environ.pop("AT_SPI_BUS_ADDRESS", None)
source = Path(__file__).resolve().parents[1] / "norvi-office/experiments/native-header"
sys.path.insert(0, str(source))
from fixtures import connect  # noqa: E402
from geometry_relay import Atspi, geometry, header_bars  # noqa: E402
from PIL import Image, ImageChops  # noqa: E402


def call(method, *arguments, geometry_api=False):
    interface = "OfficeGeometry" if geometry_api else "OfficeTest"
    output = subprocess.check_output([
        "gdbus", "call", "--session", "--dest", "org.gnome.Shell",
        "--object-path", "/dev/norvi/" + interface, "--method", "dev.norvi." + interface + "." + method,
        *arguments,
    ], text=True)
    return ast.literal_eval(output)


def wait(check, message):
    until = time.monotonic() + 12
    while time.monotonic() < until:
        result = check()
        if result:
            return result
        time.sleep(.1)
    raise AssertionError(message)


def descend(node, depth=0):
    if depth > 6 or node.get_role() in (Atspi.Role.TABLE, Atspi.Role.DOCUMENT_TEXT):
        return []
    return [node] + [item for child in geometry.children(node) for item in descend(child, depth + 1)]


record = json.loads((directory / "ready.json").read_text())
sys.path.insert(0, str(source.parent / "preview"))
from visible import observe_viewer  # noqa: E402
viewer = observe_viewer(record["shell_pid"])
assert viewer and viewer["pid"] == record["viewer"]["pid"], "The host viewer is not mapped and streaming"
context = connect(record["pipe"])
desktop = context.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", context)
doc = desktop.getCurrentComponent()
url = urlsplit(doc.getURL())
document_path = Path(unquote(url.path)).resolve()
assert url.scheme == "file" and document_path.parent == directory and document_path.name in (
    "Ember Plan.ods", "Ember Brief.odt",
), "Not the fictional preview document"
app = "calc" if doc.supportsService("com.sun.star.sheet.SpreadsheetDocument") else "writer"


def tab_transitions():
    """Exercise the pinned 1x preview tabs while sampling its compositor state."""
    results = []
    window = next(item for item in json.loads(call("Windows")[0]) if item["type"] == 0)
    x, y, _width, _height = window["frame"]
    for tab, offset in (("Insert", 255), ("Home", 150), ("Layout", 350), ("Home", 150)):
        started = time.monotonic()
        call("Click", str(x + offset), str(y + 66))
        samples = []
        while time.monotonic() - started < .6:
            state = next(item for item in json.loads(call("State", geometry_api=True)[0]) if item["app"] == app)
            samples.append({"at_ms": round((time.monotonic() - started) * 1000),
                            "enabled": state["enabled"], "reason": state["reason"], "edge": state["edge"]})
            time.sleep(.008)
        assert all(s["enabled"] for s in samples), f"{tab}: the native titlebar lost glass"
        assert samples[-1]["reason"] == "active", f"{tab}: ribbon did not recover"
        settling = [index for index, sample in enumerate(samples) if sample["reason"] == "transition"]
        recovery = 0
        if settling:
            end = next(sample for sample in samples[settling[-1] + 1:] if sample["reason"] == "active")
            recovery = end["at_ms"] - samples[settling[0]]["at_ms"]
        assert recovery < 150, f"{tab}: ribbon paused for {recovery} ms"
        results.append({"tab": tab, "ribbon_recovery_ms": recovery, "samples": samples})
    return results


transitions = tab_transitions()
Atspi.set_timeout(150, 150)
frames = [frame for application in geometry.children(Atspi.get_desktop(0))
          if application.get_name() == "soffice" for frame in geometry.children(application)
          if frame.get_role() == Atspi.Role.FRAME]
assert len(frames) == 1, "Expected exactly one private document window"
bars = header_bars(frames[0])
assert len(bars) == 1
controls = {node.get_name(): node for node in descend(bars[0])}
assert all(name in controls for name in ("Open", "Save", "Undo", "Redo", "Settings", "Main menu"))


def activate(name):
    button = controls[name]
    wait(lambda: button.get_state_set().contains(Atspi.StateType.SENSITIVE), name + " unavailable")
    assert button.get_action_iface().do_action(0)


if app == "calc":
    cell = doc.Sheets.getByIndex(0).getCellRangeByName("D2")
    original = cell.Value
    cell.Value = original + 100
    def unchanged():
        return cell.Value == original

    def changed():
        return cell.Value == original + 100
else:
    original = doc.Text.String
    doc.Text.insertString(doc.Text.End, " Preview check.", False)
    def unchanged():
        return doc.Text.String == original

    def changed():
        return doc.Text.String == original + " Preview check."
activate("Undo")
wait(unchanged, "Header Undo did not change its document")
activate("Redo")
wait(changed, "Header Redo did not change its document")
activate("Undo")
wait(unchanged, "Could not restore the original fictional document")
doc.store()
doc.getUndoManager().clear()
call("Key", "F10")
time.sleep(.6)
windows = json.loads(call("Windows")[0])
assert any(window["type"] != 0 and window["parent"] is not None for window in windows), "F10 menu did not open"
call("Capture", "preview-menu.png")
call("Escape")
time.sleep(.8)
state = wait(lambda: next((item for item in json.loads(call("State", geometry_api=True)[0])
                          if item["app"] == app and item["enabled"]), None), "Glass not active")
subprocess.run(["gsettings", "set", "org.gnome.desktop.interface", "cursor-blink", "false"], check=True)
for value, filename in (("true", "preview-pattern.png"), ("false", "preview-final.png")):
    call("Backdrop", value)
    time.sleep(1)
    call("Capture", filename)
first, second = [Image.open(directory / name).convert("RGB")
                 for name in ("preview-pattern.png", "preview-final.png")]
x, y, width, height = state["frame"]
edge = state["buffer"][1] + state["edge"]
header = (x + 80, y + 8, x + width - 80, edge - 8)
body = (x + 80, max(edge + 150, y + 350), x + width - 80, y + height - 100)
differences = {}
for name, box in (("header", header), ("body", body)):
    difference = ImageChops.difference(first.crop(box), second.crop(box))
    differences[name] = sum(max(pixel) > 0 for pixel in difference.get_flattened_data())
assert differences["header"] > 1000, differences
assert differences["body"] == 0, differences
receipt = {"app": app, "header_controls": "passed", "undo_redo": "passed", "f10_menu": "passed",
           "host_viewer": viewer,
           "tab_transitions": transitions,
           "glass": state, "backdrop_changed_pixels": differences,
           "sampled_opaque_pixels": (body[2] - body[0]) * (body[3] - body[1])}
(directory / "acceptance.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps(receipt))
