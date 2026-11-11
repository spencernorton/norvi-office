# PyGObject requires version selection before repository imports.
# ruff: noqa: E402
"""Native widget and command checks, using only fictional disposable documents."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from xml.sax.saxutils import escape

import gi

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi, Gio, GLib

from PIL import Image, ImageChops

from fixtures import connect, prop, stop_office
from geometry_relay import header_bars, geometry
from actions import Status
from routing import COMMANDS

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT.parent / "wayland-glass"))
from qualify import call, header  # noqa: E402


def wait(check, message, seconds=15):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        value = check()
        if value:
            return value
        time.sleep(0.15)
    raise AssertionError(message)


def applications():
    desktop = Atspi.get_desktop(0)
    return [desktop.get_child_at_index(i) for i in range(desktop.get_child_count())]


def office_frames():
    result = []
    for app in applications():
        if app and app.get_name() == "soffice":
            result.extend(app.get_child_at_index(i) for i in range(app.get_child_count()))
    return [node for node in result if node is not None]


def frame():
    return next((node for node in office_frames() if node.get_role() == Atspi.Role.FRAME), None)


def controls(node, depth=0):
    if node is None or depth > 5 or node.get_role() in (
        Atspi.Role.ROOT_PANE, Atspi.Role.DOCUMENT_TEXT, Atspi.Role.TABLE,
    ):
        return []
    found = [node] if node.get_role() in (Atspi.Role.PUSH_BUTTON, Atspi.Role.TOGGLE_BUTTON) else []
    for i in range(min(node.get_child_count(), 64)):
        found.extend(controls(node.get_child_at_index(i), depth + 1))
    return found


def menu_items(node, depth=0):
    if node is None or depth > 8 or node.get_role() in (
        Atspi.Role.ROOT_PANE, Atspi.Role.DOCUMENT_TEXT, Atspi.Role.TABLE,
    ):
        return []
    found = [node] if node.get_role() in (Atspi.Role.MENU_ITEM, Atspi.Role.CHECK_MENU_ITEM, Atspi.Role.MENU) else []
    for i in range(min(node.get_child_count(), 64)):
        found.extend(menu_items(node.get_child_at_index(i), depth + 1))
    return found


def native_menu_settings():
    def items():
        return [item for node in office_frames() for item in menu_items(node)]
    tools = wait(lambda: next((item for item in items() if item.get_name() == "Tools"), None),
                 "Native Tools menu was not exported")
    assert tools.get_action_iface().do_action(0)
    option = wait(lambda: next((item for item in items() if item.get_name() in
                               ("Options", "Options...", "Options…")), None),
                  "Native Options command was not exported")
    assert option.get_action_iface().do_action(0)
    cancel_dialog()


def sidebar_visible(context, owner):
    import uno

    class SidebarStatus(Status):
        visible = None

        def statusChanged(self, event):
            self.visible = event.State if event.IsEnabled else None

    transformer = context.ServiceManager.createInstanceWithContext("com.sun.star.util.URLTransformer", context)
    url = uno.createUnoStruct("com.sun.star.util.URL")
    url.Complete = ".uno:Sidebar"
    _, url = transformer.parseStrict(url)
    dispatch = owner.queryDispatch(url, "", 0)
    listener = SidebarStatus()
    dispatch.addStatusListener(listener, url)
    dispatch.removeStatusListener(listener, url)
    return listener.visible


def toggle_sidebar_from_menu():
    activate("Main menu")

    def find_item(name):
        return next((item for node in office_frames() for item in menu_items(node)
                     if item.get_name() == name), None)

    view = wait(lambda: find_item("View"), "Native View menu did not open")
    assert view.get_action_iface().do_action(0)
    sidebar = wait(lambda: find_item("Sidebar"), "View menu has no Sidebar command")
    assert sidebar.get_action_iface().do_action(0)


def control(name, owner=None):
    return next((node for node in controls(owner or frame()) if node.get_name() == name), None)


def sensitive(name, enabled=True):
    item = control(name)
    if item is None:
        return False
    value = item.get_state_set().contains(Atspi.StateType.SENSITIVE)
    return item if value == enabled else False


def native_enabled(context, owner, command):
    import uno
    transformer = context.ServiceManager.createInstanceWithContext("com.sun.star.util.URLTransformer", context)
    url = uno.createUnoStruct("com.sun.star.util.URL")
    url.Complete = COMMANDS[command]
    _, url = transformer.parseStrict(url)
    dispatch = owner.queryDispatch(url, "", 0)
    if dispatch is None:
        return False
    listener = Status()
    dispatch.addStatusListener(listener, url)
    dispatch.removeStatusListener(listener, url)
    return listener.enabled


def activate(name):
    item = wait(lambda: sensitive(name), f"{name} is unavailable")
    box = item.get_component_iface().get_extents(Atspi.CoordType.WINDOW)
    native = frame()
    bounds = native.get_component_iface().get_extents(Atspi.CoordType.WINDOW)
    windows = [window for window in json.loads(call("Windows")[0]) if window["type"] == 0 and
               window["title"] == native.get_name()]
    assert len(windows) == 1, "Ambiguous fixture geometry"
    ratio = windows[0]["buffer"][2] / bounds.width
    call("Click", round(windows[0]["buffer"][0] + (box.x + box.width / 2) * ratio),
         round(windows[0]["buffer"][1] + (box.y + box.height / 2) * ratio))
    time.sleep(0.2)


def dialog():
    for app in applications():
        if app is None or app.get_name() not in ("soffice", "xdg-desktop-portal-gtk"):
            continue
        for i in range(app.get_child_count()):
            node = app.get_child_at_index(i)
            if node and node.get_role() in (Atspi.Role.DIALOG, Atspi.Role.ALERT, Atspi.Role.FILE_CHOOSER):
                return node
    return None


def find(node, name, depth=0):
    if node is None or depth > 12:
        return None
    if node.get_name() == name:
        return node
    for i in range(min(node.get_child_count(), 100)):
        item = find(node.get_child_at_index(i), name, depth + 1)
        if item:
            return item
    return None


def cancel_dialog():
    window = wait(dialog, "Native dialog did not open")
    button = find(window, "Cancel")
    assert button is not None and button.get_action_iface().do_action(0)
    wait(lambda: dialog() is None, "Native dialog did not close")


def pair(name, enabled=True, reason=None):
    state = header(enabled, reason)
    for pattern in (True, False):
        call("Backdrop", str(pattern).lower())
        time.sleep(0.35)
        call("Capture", name + ("-pattern.png" if pattern else "-solid.png"))
    first = Image.open(name + "-pattern.png").convert("RGB")
    diff = ImageChops.difference(first, Image.open(name + "-solid.png").convert("RGB"))
    screen = json.loads(call("Screen")[0])
    scale = first.width / screen["size"][0]
    x, y, width, height = state["frame"]
    edge = state["buffer"][1] + state["edge"] if enabled else y
    rectangle = tuple(round(n * scale) for n in (x + 32, edge, x + width - 80, y + height - 60))
    sample = diff.crop(rectangle)
    assert sample.getbbox() is None, name + ": backdrop leaked into the opaque area"
    if enabled:
        glass = tuple(round(n * scale) for n in (x + 32, edge - 3, x + width - 80, edge))
        assert diff.crop(glass).getbbox(), name + ": no glass near the boundary"
    state.update(name=name, opaque_pixels=sample.width * sample.height, monitor_scale=screen["scale"])
    print(f"{name}: {state['opaque_pixels']} opaque pixels unchanged", flush=True)
    call("Backdrop", "true")
    return state


def transition_probe():
    before = header()
    x, y, _, _ = before["frame"]
    call("PrepareChrome", 120, geometry=True)
    assert header()["transitionCount"] == before["transitionCount"], "Other process affected the header"

    # A normal grid click must not flash the ribbon.
    call("Click", x + 440, y + 260)
    time.sleep(0.2)
    assert header()["transitionCount"] == before["transitionCount"], "Grid click paused header"

    relay = int(os.environ["NORVI_OFFICE_BRIDGE_PID"])
    os.kill(relay, signal.SIGSTOP)
    try:
        # The opt-in profile removes the left quick-access strip, so tabs shift left.
        tab_x = 278 if os.environ.get("NORVI_OFFICE_CALC_RIBBON") == "1" else 450
        call("Click", x + tab_x, y + 65)
        paused = wait(lambda: next((item for item in json.loads(call("State", geometry=True)[0])
                                   if item["reason"] == "transition" and not item["enabled"]), None),
                      "Ribbon input never suspended glass", seconds=1)
        assert paused["transitionCount"] > before["transitionCount"]
        call("Capture", "calc-tab-transition.png")
        time.sleep(0.45)
        # Even after the hold, an old report cannot bring back the mask.
        opaque = pair("calc-transition-stalled", False, "transition")
    finally:
        os.kill(relay, signal.SIGCONT)
    recovered = header()
    assert recovered["transitionCount"] == opaque["transitionCount"]
    return [opaque, pair("calc-insert-settled")]


def monitor_scale_two():
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    dest, path = "org.gnome.Mutter.DisplayConfig", "/org/gnome/Mutter/DisplayConfig"
    state = bus.call_sync(dest, path, dest, "GetCurrentState", None, None,
                          Gio.DBusCallFlags.NONE, 3000, None).unpack()
    serial, monitors, _, properties = state
    connector = monitors[0][0][0]
    mode = next(mode for mode in monitors[0][1] if mode[-1].get("is-current"))
    assert 2.0 in mode[5], "Private monitor does not support 2x"
    options = {"layout-mode": GLib.Variant("u", properties.get("layout-mode", 1))}
    config = [(0, 0, 2.0, 0, True, [(connector, mode[0], {})])]
    bus.call_sync(dest, path, dest, "ApplyMonitorsConfig",
                  GLib.Variant("(uua(iiduba(ssa{sv}))a{sv})", (serial, 1, config, options)),
                  None, Gio.DBusCallFlags.NONE, 3000, None)
    wait(lambda: json.loads(call("Screen")[0])["scale"] == 2, "Private monitor did not switch to 2x")


def profile_settings(profile):
    user = profile / "user"
    user.mkdir(parents=True, exist_ok=True)
    light = "dark" not in os.environ.get("GTK_THEME", "")
    style = "sifr_svg" if light else "sifr_dark_svg"
    (user / "registrymodifications.xcu").write_text(
        '<?xml version="1.0"?><oor:items xmlns:oor="http://openoffice.org/2001/registry">'
        '<item oor:path="/org.openoffice.Office.Common/Misc">'
        '<prop oor:name="SymbolStyle" oor:op="fuse"><value>' + style + '</value></prop></item>'
        '<item oor:path="/org.openoffice.Office.Common/Save/Document">'
        '<prop oor:name="CreateBackup" oor:op="fuse"><value>false</value></prop>'
        '<prop oor:name="AutoSave" oor:op="fuse"><value>false</value></prop></item>'
        '<item oor:path="/org.openoffice.Office.Paths/Paths/Work">'
        '<prop oor:name="WritePath" oor:op="fuse"><value>' + escape(Path.cwd().as_uri()) +
        '</value></prop></item></oor:items>'
    )


def undo_redo(app, doc):
    if app == "calc":
        cell = doc.Sheets.getByIndex(0).getCellRangeByName("C8")
        doc.getCurrentController().select(cell)
        cell.Value = 88
        wait(lambda: cell.Value == 88, "Calc edit did not arrive")
        activate("Undo")
        wait(lambda: cell.String == "", "Undo reached the wrong cell/document")
        call("Capture", "calc-undo.png")
        activate("Redo")
        wait(lambda: cell.Value == 88, "Redo did not restore Calc edit")
        call("Capture", "calc-redo.png")
    elif app == "writer":
        before = doc.Text.String
        doc.Text.insertString(doc.Text.End, "Native header check. ", False)
        wait(lambda: doc.Text.String != before, "Writer edit did not arrive")
        edited = doc.Text.String
        activate("Undo")
        wait(lambda: doc.Text.String == before, "Undo did not restore Writer text")
        activate("Redo")
        wait(lambda: doc.Text.String == edited, "Redo did not restore Writer edit")


def menu_opaque_fallback(app):
    activate("Main menu")
    time.sleep(0.4)
    subprocess.run(["gsettings", "--schemadir", os.environ["NORVI_OFFICE_POPUP_SCHEMAS"], "set",
                    "org.gnome.shell.extensions.blur-my-shell.popup", "blur", "false"], check=True)
    time.sleep(0.6)
    windows = [win for win in json.loads(call("Windows")[0]) if win["parent"] is not None]
    assert windows, "No native menu for fallback check"
    popup = windows[0]["frame"]
    for pattern in (True, False):
        call("Backdrop", str(pattern).lower())
        time.sleep(0.35)
        call("Capture", app + "-opaque-menu-" + ("pattern.png" if pattern else "solid.png"))
    first = Image.open(app + "-opaque-menu-pattern.png").convert("RGB")
    diff = ImageChops.difference(first, Image.open(app + "-opaque-menu-solid.png").convert("RGB"))
    ratio = first.width / json.loads(call("Screen")[0])["size"][0]
    x, y, width, height = popup
    region = tuple(round(n * ratio) for n in (x + 24, y + 24, x + width - 24, y + height - 24))
    assert diff.crop(region).getbbox() is None, "No-blur menu stayed translucent"
    call("Escape")
    subprocess.run(["gsettings", "--schemadir", os.environ["NORVI_OFFICE_POPUP_SCHEMAS"], "set",
                    "org.gnome.shell.extensions.blur-my-shell.popup", "blur", "true"], check=True)
    call("Backdrop", "true")


def close_cancel(doc):
    doc.setModified(True)
    activate("Close")
    cancel_dialog()
    assert doc.isModified() and frame() is not None, "Close bypassed the document confirmation"


def multiwindow(desktop, first):
    original = frame()
    first_cell = first.Sheets.getByIndex(0).getCellRangeByName("C8")
    first_cell.Value = 101
    wait(lambda: sensitive("Save"), "First document Save did not enable")
    target = Path.cwd() / "Ember Second Plan.ods"
    shutil.copyfile(Path.cwd() / "Ember Plan.ods", target)
    second = desktop.loadComponentFromURL(target.as_uri(), "_blank", 0, (prop("Hidden", False),))
    try:
        other = wait(lambda: next((node for node in office_frames()
                                  if node.get_role() == Atspi.Role.FRAME and node != original), None),
                     "Second document window did not map")
        second_cell = second.Sheets.getByIndex(0).getCellRangeByName("C8")
        second_cell.Value = 202
        second.getCurrentController().getFrame().activate()
        wait(lambda: control("Save", other).get_state_set().contains(Atspi.StateType.SENSITIVE),
             "Second document Save did not enable")
        # Give both actual windows the same caption. Invoke the held first
        # window's native button while the second owns keyboard focus.
        for doc in (first, second):
            doc.getCurrentController().getFrame().setTitle("Fictional shared caption")
        wait(lambda: original.get_name() == other.get_name(), "Duplicate captions did not arrive")
        button = control("Save", original)
        assert button.get_action_iface().do_action(0)
        wait(lambda: not first.isModified(), "First header Save did not reach its owner")
        assert second.isModified() and second_cell.Value == 202, "Save reached the focused document"
        first.getCurrentController().getFrame().activate()
        undo = control("Undo", original)
        wait(lambda: undo.get_state_set().contains(Atspi.StateType.SENSITIVE), "First Undo unavailable")
        assert undo.get_action_iface().do_action(0)
        wait(lambda: first_cell.Value != 101, "First header Undo did not reach its owner")
        assert second_cell.Value == 202, "Undo reached the focused document"
        redo = control("Redo", original)
        wait(lambda: redo.get_state_set().contains(Atspi.StateType.SENSITIVE), "First Redo unavailable")
        assert redo.get_action_iface().do_action(0)
        wait(lambda: first_cell.Value == 101, "First header Redo did not reach its owner")
        print("calc: duplicate-caption windows routed Save/Undo/Redo to their owner", flush=True)
    finally:
        second.setModified(False)
        second.close(True)
        first.setModified(False)
        first.getCurrentController().getFrame().activate()


def test_app(app, filename):
    pipe = "norvi_header_" + Path.cwd().name.replace(".", "_") + "_" + app
    profile = Path.cwd() / ("profile-" + app)
    profile_settings(profile)
    package = ROOT.parent.parent / "dist/NorviGlass.oxt"
    ribbon_preview = app == "calc" and os.environ.get("NORVI_OFFICE_CALC_RIBBON") == "1"
    if ribbon_preview:
        from calc_ribbon import prepare, preview_package
        overlay = Path.cwd() / package.name
        preview_package(package, overlay)
        package = overlay
    subprocess.run(["unopkg", "add", "-env:UserInstallation=" + profile.as_uri(), str(package)], check=True)
    if ribbon_preview:
        prepare(profile)
    environment = dict(os.environ, GTK3_MODULES=str(Path.cwd() / "build/libnorvi-office-header.so"))
    if not ribbon_preview:
        environment.pop("NORVI_OFFICE_CALC_RIBBON", None)
    log = Path(app + ".log").open("w")
    office = subprocess.Popen([
        "soffice", "-env:UserInstallation=" + profile.as_uri(), "--nologo", "--norestore",
        f"--accept=pipe,name={pipe};urp;", filename,
    ], env=environment, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    broker = None
    broker_log = Path(app + "-actions.log").open("w")
    try:
        context = connect(pipe)
        manager = context.ServiceManager
        desktop = manager.createInstanceWithContext("com.sun.star.frame.Desktop", context)
        doc = wait(desktop.getCurrentComponent, "No document controller")
        manager.createInstanceWithContext("com.sun.star.util.PathSettings", context).Work = Path.cwd().as_uri()
        peer = doc.getCurrentController().getFrame().getContainerWindow()
        assert peer.getWindowHandle((), 6) is not None, "No native window identity"
        ready = Path("actions-ready.json")
        ready.unlink(missing_ok=True)
        broker = subprocess.Popen(["/usr/bin/python3", str(ROOT / "actions.py"), pipe],
                                  stdout=broker_log, stderr=subprocess.STDOUT)
        wait(ready.exists, "Action broker did not start")
        wait(frame, "Native application frame did not map")
        call("Place")
        native = wait(frame, "No accessible native frame")
        Path(app + "-identity.json").write_text(json.dumps({
            "native": native.get_name(), "uno": doc.getCurrentController().getFrame().getTitle(),
        }, indent=2))
        wait(lambda: sensitive("Settings"), "Native Settings did not become available")
        names = [node.get_name() for node in controls(frame())]
        assert all(name in names for name in ("Open", "Save", "Undo", "Redo", "Settings", "Main menu", "Close")), names
        print(f"{app}: native header and exact document routing ready", flush=True)
        time.sleep(0.7)
        Path(app + "-chrome-geometry.json").write_text(json.dumps({
            "frame": geometry.rectangle(native),
            "children": [{"role": node.get_role_name(), "name": node.get_name(),
                          "bounds": geometry.rectangle(node)} for node in geometry.children(native)],
            "header": [geometry.rectangle(bar) for bar in header_bars(native)],
        }, indent=2))
        screen = json.loads(call("Screen")[0])
        dark = "dark" in os.environ.get("GTK_THEME", "")
        glass = screen["scale"] == 1 and dark
        reason = None if glass else "window-or-scale" if screen["scale"] != 1 else "appearance"
        if ribbon_preview:
            owner = doc.getCurrentController().getFrame()
            def sidebar_state():
                visible = sidebar_visible(context, owner)
                return (visible,) if isinstance(visible, bool) else None

            visible, = wait(sidebar_state, "Calc Sidebar command did not initialize")
            if visible:
                dispatcher = manager.createInstanceWithContext("com.sun.star.frame.DispatchHelper", context)
                dispatcher.executeDispatch(owner, ".uno:Sidebar", "", 0, ())
            wait(lambda: sidebar_visible(context, owner) is False, "Calc Sidebar did not hide")
        if ribbon_preview:
            sheet = doc.Sheets.getByIndex(0)
            doc.getCurrentController().select(sheet.getCellRangeByName("D2"))
        results = [pair(app + "-native-header", glass, reason)]
        if ribbon_preview and glass:
            # Exercise an actual ribbon command on a regular cell and revert the edit.
            doc.getCurrentController().select(doc.Sheets.getByIndex(0).getCellRangeByName("C2"))
            state = header()
            x = state["frame"][0]
            bottom = state["buffer"][1] + state["edge"]
            cell = doc.Sheets.getByIndex(0).getCellRangeByName("C2")
            original_weight = cell.CharWeight
            call("Click", x + 162, bottom - 17)
            wait(lambda: cell.CharWeight > original_weight, "Home Bold did not format the selected cell")
            activate("Undo")
            wait(lambda: cell.CharWeight == original_weight, "Undo did not restore the cell format")
        if ribbon_preview:
            toggle_sidebar_from_menu()
            wait(lambda: sidebar_visible(context, owner) is True, "View menu did not show the Sidebar")
            toggle_sidebar_from_menu()
            wait(lambda: sidebar_visible(context, owner) is False, "View menu did not hide the Sidebar")
        if ribbon_preview and glass:
            x, y, _, _ = header()["frame"]
            call("Click", x + 1210, y + 140)
            wait(lambda: any(win["parent"] is not None for win in json.loads(call("Windows")[0])),
                 "Find & Select popup did not open")
            call("Capture", "calc-find-select.png")
            call("Escape")
            wait(lambda: not any(win["parent"] is not None for win in json.loads(call("Windows")[0])),
                 "Find & Select popup did not close")
            transition = header()["transitionCount"]
            call("Click", x + 476, y + 65)
            wait(lambda: header()["transitionCount"] > transition, "Formulas tab did not settle")
            call("Capture", "calc-formulas-tab.png")
            call("Click", x + 46, y + 112)
            wait(dialog, "Formulas tab did not open the function wizard")
            cancel_dialog()
            call("Click", x + 175, y + 65)
            activate("Maximize")
            doc.getCurrentController().select(sheet.getCellRangeByName("D2"))
            wait(lambda: header()["frame"][2] == screen["size"][0], "Calc did not maximize")
            results.append(pair("calc-study-maximized-home"))
            # Wide layout keeps the complete style and cell groups on the ribbon.
            call("Click", 1030, 144)
            wait(lambda: sidebar_visible(context, owner) is True, "Home Cell Styles did not open the Sidebar")
            toggle_sidebar_from_menu()
            wait(lambda: sidebar_visible(context, owner) is False, "Styles Sidebar did not close")
            call("Click", 1132, 136)
            wait(lambda: any(win["parent"] is not None for win in json.loads(call("Windows")[0])),
                 "Rows popup did not open")
            call("Capture", "calc-rows-menu.png")
            call("Escape")
            wait(lambda: not any(win["parent"] is not None for win in json.loads(call("Windows")[0])),
                 "Rows popup did not close")
            call("Place")
        if app == "calc" and glass:
            results.extend(transition_probe())
        activate("Settings")
        window = wait(dialog, "Settings did not open")
        call("Capture", app + "-settings.png")
        assert find(window, "Open") is None, "Document header was attached to a Settings dialog"
        cancel_dialog()
        wait(lambda: sensitive("Settings"), "Settings action did not recover")
        activate("Main menu")
        time.sleep(0.6)
        call("Capture", app + "-native-menu.png")
        assert any(win["parent"] is not None for win in json.loads(call("Windows")[0])), "No native menu"
        if app == "calc":
            native_menu_settings()
        else:
            call("Escape")
        if app in ("calc", "writer"):
            undo_redo(app, doc)
        doc.setModified(True)
        activate("Save")
        wait(lambda: not doc.isModified(), "Save did not reach the owning document")
        save_enabled = native_enabled(context, doc.getCurrentController().getFrame(), "save")
        print(f"{app}: native Save status after storing = {save_enabled}", flush=True)
        wait(lambda: sensitive("Save", save_enabled), "Header Save disagrees with native command status")
        call("Resize", 800, 620)
        results.append(pair(app + "-narrow", glass, reason))
        activate("Maximize")
        results.append(pair(app + "-maximized", glass, reason))
        call("WindowState", "restored")
        call("Place")
        results.append(pair(app + "-restored", glass, reason))
        if app == "calc":
            call("Place")
            call("Key", "F10")
            wait(lambda: any(win["parent"] is not None for win in json.loads(call("Windows")[0])),
                 "F10 did not open the native header menu")
            call("Escape")
            call("Key", "F6")
            settings = wait(lambda: sensitive("Settings"), "Header did not recover after menu")
            def focus_settings():
                settings.get_component_iface().grab_focus()
                return settings.get_state_set().contains(Atspi.StateType.FOCUSED)
            wait(focus_settings, "Settings did not receive keyboard focus")
            call("Key", "Return")
            cancel_dialog()
            activate("Open")
            cancel_dialog()
            assert not doc.isModified(), "Cancelling Open changed the document"
            menu_opaque_fallback(app)
            box = next(win["frame"] for win in json.loads(call("Windows")[0]) if win["type"] == 0)
            call("Drag", box[0] + 280, box[1] + 20, box[0] + 340, box[1] + 50)
            time.sleep(0.7)
            after = next(win["frame"] for win in json.loads(call("Windows")[0]) if win["type"] == 0)
            assert after[:2] != box[:2], "Native header did not drag the window"
            call("Place")
            close_cancel(doc)
            activate("Save")
            wait(lambda: not doc.isModified(), "Save did not recover after cancelled Close")
            multiwindow(desktop, doc)
        print(f"{app}: Settings, native menu and Save verified", flush=True)
        Path(app + "-results.json").write_text(json.dumps({"states": results, "controls": names,
            "settings": True, "menu": True, "save": True,
            "native_save_enabled_after_store": save_enabled,
            "native_menu_command": app == "calc", "keyboard_menu": app == "calc",
            "undo_redo": app in ("calc", "writer"), "open_cancel": app == "calc",
            "keyboard_settings": app == "calc", "drag": app == "calc",
            "close_cancel": app == "calc", "multiwindow": app == "calc",
            "opaque_menu_without_blur": app == "calc"}, indent=2) + "\n")
    finally:
        if broker and broker.poll() is None:
            broker.terminate()
            broker.wait(timeout=10)
        stop_office(office)
        log.close()
        broker_log.close()
        time.sleep(0.4)


def rollback(filename):
    profile = Path.cwd() / "profile-without-module"
    profile_settings(profile)
    environment = dict(os.environ)
    environment.pop("GTK3_MODULES", None)
    target = Path.cwd() / "Ember Rollback Plan.ods"
    shutil.copyfile(filename, target)
    with Path("without-module.log").open("w") as log:
        office = subprocess.Popen(["soffice", "-env:UserInstallation=" + profile.as_uri(),
            "--nologo", "--norestore", str(target)], env=environment, stdout=log,
            stderr=subprocess.STDOUT, start_new_session=True)
        try:
            native = wait(lambda: (node if (node := frame()) and target.name in node.get_name() else None),
                          "Unmodified GTK3 document did not load")
            assert dialog() is None, "Rollback stopped at a warning instead of loading the document"
            call("Place")
            time.sleep(0.6)
            assert not header_bars(native), "Native header remained without the module"
            assert control("Settings") is None and control("Open") is None
            call("Capture", "without-module.png")
            Path("rollback-results.json").write_text(json.dumps({
                "module_omitted": True, "custom_header_absent": True,
                "document_loaded": True,
                "controls": [node.get_name() for node in controls(native)],
            }, indent=2) + "\n")
            print("rollback: stock native header restored by omitting GTK3_MODULES", flush=True)
        finally:
            stop_office(office)


if __name__ == "__main__":
    directory = os.environ.get("NORVI_OFFICE_TEST_DIR")
    if not directory or Path.cwd() != Path(directory) or os.environ.get("XDG_CONFIG_HOME") != str(Path(directory) / "config"):
        sys.exit("Run the isolated native header harness.")
    fixtures = json.loads(Path("fixtures.json").read_text())
    if os.environ.get("NORVI_OFFICE_SCALE_TEST") == "1":
        monitor_scale_two()
    for app in os.environ.get("NORVI_OFFICE_APPS", "calc writer impress draw math base").split():
        test_app(app, fixtures[app])
    rollback(fixtures["calc"])
