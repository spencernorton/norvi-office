# PyGObject requires version selection before repository imports.
# ruff: noqa: E402
"""Scene helpers for the private visual lab. Run scenes through visual_lab.sh."""
import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import gi

gi.require_version("Atspi", "2.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Atspi, GdkPixbuf, GLib

from uno_utils import connect

LAB = Path(os.environ["LAB_DIR"])
STAGE = Path(os.environ["LAB_STAGE"])
LAUNCH = STAGE / "share/norvi-office/experimental/desktop/launch.py"
STATE = LAB / "state/norvi-office/desktop"
SHOTS = LAB / "shots"
SKIP = (Atspi.Role.DOCUMENT_TEXT, Atspi.Role.DOCUMENT_SPREADSHEET, Atspi.Role.DOCUMENT_PRESENTATION,
        Atspi.Role.DOCUMENT_FRAME, Atspi.Role.TABLE, Atspi.Role.TREE_TABLE)


def call(method, *arguments):
    output = subprocess.check_output([
        "gdbus", "call", "--session", "--dest", "org.gnome.Shell", "--object-path", "/dev/norvi/OfficeTest",
        "--method", "dev.norvi.OfficeTest." + method, *map(str, arguments)], text=True).strip()
    return ast.literal_eval(output) if output not in ("", "()") else ()


def windows():
    return json.loads(call("Windows")[0])


def wait(check, message, seconds=30):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        try:
            value = check()
        except GLib.Error:
            value = None
        if value:
            return value
        time.sleep(0.2)
    raise AssertionError(message)


def office_windows():
    return [item for item in windows() if item["type"] == 0 and (item["app"] or "").startswith("libreoffice")]


def fixtures():
    """Fictional documents for every module, created once per lab run."""
    record = LAB / "fixtures.json"
    if not record.exists():
        import fixtures as maker
        os.environ["NORVI_OFFICE_CALC_RIBBON"] = "1"
        record.write_text(json.dumps(maker.make(LAB), indent=2) + "\n")
    return json.loads(record.read_text())


def launch(app, *files, state="maximized", settle=2.5):
    """Open one module through the staged desktop launcher, as the menu entry does."""
    result = subprocess.run([sys.executable, str(LAUNCH), "--worker", "--app", app, "--", *files],
                            capture_output=True, text=True, timeout=300)
    if result.returncode:
        raise AssertionError("Launcher failed: " + result.stderr[-2000:])
    wait(office_windows, f"{app} did not map a window", 60)
    call("DismissOverview")
    time.sleep(1)
    if state == "maximized":
        call("WindowState", "maximized")
    else:
        call("Place")
        call("Resize", *state)
    time.sleep(settle)
    return json.loads(result.stdout.strip().splitlines()[-1])


def stop():
    """Close the lab's own Office without leaving recovery data behind."""
    record_path = STATE / "running.json"
    if not record_path.exists():
        return
    record = json.loads(record_path.read_text())
    try:
        context = connect(record["pipe"], Path(record["profile"]))
        desktop = context.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", context)
        components = desktop.Components.createEnumeration()
        while components.hasMoreElements():
            component = components.nextElement()
            if hasattr(component, "setModified"):
                component.setModified(False)
        desktop.terminate()
    except Exception:
        pass
    until = time.monotonic() + 20
    while time.monotonic() < until and Path(f"/proc/{record['office_group']}").exists():
        time.sleep(0.2)
    for key, group in (("office_group", True), ("broker", False), ("geometry", False)):
        try:
            (os.killpg if group else os.kill)(record[key], 15)
        except (KeyError, ProcessLookupError, PermissionError):
            pass
    record_path.unlink(missing_ok=True)
    wait(lambda: not office_windows(), "Office windows remained after closing", 20)


def capture(name):
    if not re.fullmatch(r"[a-z-]+", name):
        raise ValueError("Capture names use lowercase letters and hyphens")
    call("Capture", name + ".png")
    return SHOTS / (name + ".png")


def band(path, top, height):
    """One full-width strip of a capture, for telling whether a click changed it."""
    image = GdkPixbuf.Pixbuf.new_from_file(str(path))
    return image.new_subpixbuf(0, top, image.get_width(), height).get_pixels()


def frame():
    desktop = Atspi.get_desktop(0)
    for index in range(desktop.get_child_count()):
        app = desktop.get_child_at_index(index)
        if app is None or app.get_name() != "soffice":
            continue
        for child in range(app.get_child_count()):
            node = app.get_child_at_index(child)
            if node is not None and node.get_role() == Atspi.Role.FRAME:
                return node
    return None


def walk(node, depth=0, limit=16):
    """Chrome only: never descend into a document, table or its cells."""
    if node is None or depth > limit:
        return
    yield node
    if node.get_role() in SKIP:
        return
    for index in range(min(node.get_child_count(), 200)):
        yield from walk(node.get_child_at_index(index), depth + 1, limit)


def find(role=None, name=None, owner=None):
    for node in walk(owner or frame()):
        if (role is None or node.get_role() == role) and (name is None or node.get_name() == name):
            return node
    return None


def find_all(role, owner=None):
    return [node for node in walk(owner or frame()) if node.get_role() == role]


def point(node):
    """Screen coordinates of a control's centre, from its window-relative extents."""
    box = node.get_component_iface().get_extents(Atspi.CoordType.WINDOW)
    window = office_windows()[0]
    return (round(window["buffer"][0] + box.x + box.width / 2),
            round(window["buffer"][1] + box.y + box.height / 2))


def click(node_or_x, y=None, settle=0.8):
    x, y = point(node_or_x) if y is None else (node_or_x, y)
    call("Click", x, y)
    time.sleep(settle)


def tabs():
    return [node.get_name() for node in find_all(Atspi.Role.PAGE_TAB)
            if node.get_name() and node.get_state_set().contains(Atspi.StateType.SHOWING)]


def select_tab(name, settle=1.2):
    node = wait(lambda: find(Atspi.Role.PAGE_TAB, name), f"No ribbon tab named {name}", 10)
    click(node, settle=settle)


def outline(owner=None, limit=7):
    """A compact accessibility outline of the chrome, for layout diagnostics."""
    lines = []

    def visit(node, depth):
        if node is None or depth > limit:
            return
        try:
            box = node.get_component_iface().get_extents(Atspi.CoordType.WINDOW)
            where = f"{box.x},{box.y} {box.width}x{box.height}"
        except Exception:
            where = "-"
        lines.append(f"{'  ' * depth}{node.get_role_name()} {node.get_name()!r} [{where}]")
        if node.get_role() in SKIP:
            return
        for index in range(min(node.get_child_count(), 80)):
            visit(node.get_child_at_index(index), depth + 1)

    visit(owner or frame(), 0)
    return "\n".join(lines)
