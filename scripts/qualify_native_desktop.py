#!/usr/bin/python3
"""Exercise actual host Office windows using newly created, owned check documents."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "norvi-office/experiments/native-header"))
from uno_utils import connect, prop  # noqa: E402
from geometry_relay import Atspi, GLib, geometry, header_bars  # noqa: E402


def wait(check, message):
    until = time.monotonic() + 12
    while time.monotonic() < until:
        try:
            value = check()
        except GLib.Error:
            value = None
        if value:
            return value
        time.sleep(.1)
    raise AssertionError(message)


def controls(node, depth=0):
    if depth > 6:
        return []
    return [node] + [item for child in geometry.children(node) for item in controls(child, depth + 1)]


def frame_for(document, pid):
    title = document.CurrentController.Frame.getTitle()
    def find():
        for app in geometry.children(Atspi.get_desktop(0)):
            if app.get_process_id() != pid:
                continue
            for frame in geometry.children(app):
                try:
                    if frame.get_role() == Atspi.Role.FRAME and frame.get_name().startswith(title):
                        bars = header_bars(frame)
                        if len(bars) == 1:
                            return frame, {n.get_name(): n for n in controls(bars[0])}
                except GLib.Error:
                    continue  # A disposed sibling must not hide the live owned frame.
        return None
    return wait(find, "The owned document did not acquire a native host header")


def activate(buttons, name):
    button = buttons[name]
    wait(lambda: button.get_state_set().contains(Atspi.StateType.SENSITIVE), name + " unavailable")
    assert button.get_action_iface().do_action(0), name + " activation failed"


def main():
    os.environ.pop("AT_SPI_BUS_ADDRESS", None)
    root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "norvi-office/desktop"
    record = json.loads((root / "running.json").read_text())
    context = connect(record["pipe"])
    desktop = context.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", context)
    directory = Path(tempfile.mkdtemp(prefix="native-check-", dir=root))
    documents = []
    result = {}
    try:
        for name, kind, filter_name in (("Calc check A", "scalc", "calc8"),
                                        ("Calc check B", "scalc", "calc8"),
                                        ("Writer check", "swriter", "writer8")):
            doc = desktop.loadComponentFromURL("private:factory/" + kind, "_blank", 0, ())
            documents.append(doc)
            if kind == "scalc":
                doc.Sheets.getByIndex(0).getCellRangeByName("A1").Value = 10 if name.endswith("A") else 20
            else:
                doc.Text.String = "Office native desktop verification."
            extension = ".ods" if kind == "scalc" else ".odt"
            doc.storeAsURL((directory / (name + extension)).as_uri(), (prop("FilterName", filter_name),))
            doc.getUndoManager().clear()
        Atspi.set_timeout(150, 150)
        groups = []
        for app in geometry.children(Atspi.get_desktop(0)):
            try:
                if os.getpgid(app.get_process_id()) == record["office_group"]:
                    groups.append(app.get_process_id())
            except (ProcessLookupError, PermissionError):
                pass
        assert len(groups) == 1, "Expected one actual desktop Office process"
        pid = groups[0]
        environment = dict(item.split(b"=", 1) for item in Path(f"/proc/{pid}/environ").read_bytes().split(b"\0") if b"=" in item)
        assert environment.get(b"XDG_RUNTIME_DIR") == f"/run/user/{os.getuid()}".encode()
        assert b"NORVI_OFFICE_TEST_DIR" not in environment
        assert environment.get(b"WAYLAND_DISPLAY") in (b"wayland-0", f"/run/user/{os.getuid()}/wayland-0".encode())
        a, b, writer = documents
        _frame_a, buttons_a = frame_for(a, pid)
        _frame_b, buttons_b = frame_for(b, pid)
        _frame_writer, writer_buttons = frame_for(writer, pid)
        required = ("Open", "Save", "Undo", "Redo", "Settings", "Main menu")
        assert all(key in buttons for key in required for buttons in (buttons_a, buttons_b, writer_buttons))
        # Duplicate captions and another active module must not redirect Undo.
        a.CurrentController.Frame.setTitle("Office routing check")
        b.CurrentController.Frame.setTitle("Office routing check")
        ca = a.Sheets.getByIndex(0).getCellRangeByName("A1")
        cb = b.Sheets.getByIndex(0).getCellRangeByName("A1")
        ca.Value = 11
        writer.CurrentController.Frame.activate()
        activate(buttons_a, "Undo")
        wait(lambda: ca.Value == 10, "Undo reached the wrong Calc document")
        assert cb.Value == 20 and writer.Text.String == "Office native desktop verification."
        activate(buttons_a, "Redo")
        wait(lambda: ca.Value == 11, "Redo did not reach its own document")
        activate(buttons_a, "Save")
        wait(lambda: not a.isModified(), "Save did not store its own check document")
        a.getUndoManager().clear()
        writer.Text.insertString(writer.Text.End, " Edit.", False)
        activate(writer_buttons, "Undo")
        wait(lambda: writer.Text.String == "Office native desktop verification.", "Writer header Undo failed")
        writer.store()
        activate(writer_buttons, "Main menu")
        wait(lambda: writer_buttons["Main menu"].get_state_set().contains(Atspi.StateType.CHECKED), "Native main menu did not open")
        activate(writer_buttons, "Main menu")
        result = {"host_process": pid, "wayland_display": environment[b"WAYLAND_DISPLAY"].decode(),
                  "nested_compositor": False, "persistent_profile": record["profile"],
                  "native_headers": "passed", "calc_undo_redo_save": "passed", "writer_undo": "passed",
                  "duplicate_caption_routing": "passed", "native_main_menu": "passed",
                  "glass": "pending compositor activation and separate host visual acceptance",
                  "owned_documents": str(directory)}
        (root / "native-core-acceptance.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result))
    finally:
        for doc in documents:
            try:
                # These are only the objects created in this invocation.
                doc.store()
                doc.close(True)
            except Exception:
                pass


if __name__ == "__main__":
    main()
