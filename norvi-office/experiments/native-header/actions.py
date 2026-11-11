"""Allowlisted UNO actions for a launch-scoped native GTK header."""
import json
import os
from pathlib import Path
import sys
import time

import uno
import unohelper

from com.sun.star.frame import XStatusListener
from gi.repository import Gio, GLib

from routing import COMMANDS, matching_frame, uses_pipe

API = """<node><interface name="dev.norvi.OfficeHeader">
  <method name="Describe">
    <arg type="u" direction="in"/><arg type="t" direction="in"/>
    <arg type="s" direction="in"/><arg type="s" direction="in"/>
    <arg type="a{sb}" direction="out"/>
  </method>
  <method name="Activate">
    <arg type="u" direction="in"/><arg type="t" direction="in"/><arg type="s" direction="in"/>
    <arg type="s" direction="in"/><arg type="s" direction="in"/>
    <arg type="b" direction="out"/>
  </method>
</interface></node>"""


class Status(unohelper.Base, XStatusListener):
    def __init__(self):
        self.enabled = False

    def statusChanged(self, event):
        self.enabled = bool(event.IsEnabled)

    def disposing(self, _event):
        self.enabled = False


class Broker:
    def __init__(self, pipe, token):
        self.token = token
        self.pipe = pipe
        self.bindings = {}
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
        for _ in range(150):
            try:
                self.context = resolver.resolve(f"uno:pipe,name={pipe};urp;StarOffice.ComponentContext")
                break
            except Exception:
                time.sleep(0.1)
        else:
            raise RuntimeError("Private LibreOffice pipe did not become available")
        manager = self.context.ServiceManager
        self.desktop = manager.createInstanceWithContext("com.sun.star.frame.Desktop", self.context)
        self.transformer = manager.createInstanceWithContext("com.sun.star.util.URLTransformer", self.context)
        self.dispatcher = manager.createInstanceWithContext("com.sun.star.frame.DispatchHelper", self.context)
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.registration = self.bus.register_object(
            "/dev/norvi/OfficeHeader", Gio.DBusNodeInfo.new_for_xml(API).interfaces[0],
            self.call, None, None,
        )
        self.owner = Gio.bus_own_name_on_connection(
            self.bus, os.environ.get("NORVI_OFFICE_HEADER_BUS", "dev.norvi.OfficeHeader"),
            Gio.BusNameOwnerFlags.NONE, None, None,
        )

    def frame(self, sender, pid, handle, identity, token, bind=False):
        if token != self.token:
            return None
        peer = self.bus.call_sync(
            "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
            "GetConnectionUnixProcessID", GLib.Variant("(s)", (sender,)),
            GLib.VariantType.new("(u)"), Gio.DBusCallFlags.NONE, 500, None,
        ).unpack()[0]
        if peer != pid or not uses_pipe(Path(f"/proc/{peer}/cmdline").read_bytes(), self.pipe):
            return None
        key = (pid, identity)
        collection = self.desktop.getFrames()
        frames = [collection.getByIndex(i) for i in range(collection.getCount())]
        frame = matching_frame(frames, handle)
        if key in self.bindings:
            return frame if frame is not None and frame == self.bindings[key] else None
        if not bind:
            return None
        if frame is not None:
            if len(self.bindings) >= 128:
                self.bindings.pop(next(iter(self.bindings)))
            self.bindings[key] = frame
        return frame

    def enabled(self, frame, command):
        url = uno.createUnoStruct("com.sun.star.util.URL")
        url.Complete = COMMANDS[command]
        _, url = self.transformer.parseStrict(url)
        dispatch = frame.queryDispatch(url, "", 0)
        if dispatch is None:
            return False
        listener = Status()
        dispatch.addStatusListener(listener, url)
        dispatch.removeStatusListener(listener, url)
        return listener.enabled

    def call(self, _connection, sender, _path, _interface, method, parameters, invocation):
        try:
            arguments = parameters.unpack()
            pid, handle, identity = arguments[:3]
            frame = self.frame(sender, pid, handle, identity, arguments[-1], bind=method == "Describe")
            if method == "Describe":
                states = {name: frame is not None and self.enabled(frame, name) for name in COMMANDS}
                invocation.return_value(GLib.Variant("(a{sb})", (states,)))
            elif method == "Activate":
                command = arguments[3]
                allowed = frame is not None and command in COMMANDS
                if allowed:
                    frame.activate()
                    allowed = self.enabled(frame, command)
                if allowed:
                    # Dispatch against the matched frame, preserving LibreOffice's
                    # own Save/Open dialogs, undo manager and command semantics.
                    self.dispatcher.executeDispatch(frame, COMMANDS[command], "", 0, ())
                invocation.return_value(GLib.Variant("(b)", (allowed,)))
        except Exception as error:
            print(f"{method}: {type(error).__name__}", flush=True)
            invocation.return_dbus_error("dev.norvi.OfficeHeader.Error", "Office action unavailable")


if __name__ == "__main__":
    root = os.environ.get("NORVI_OFFICE_SESSION_DIR") or os.environ.get("NORVI_OFFICE_TEST_DIR")
    desktop = root and os.environ.get("NORVI_OFFICE_SESSION_DIR") == root and Path(root, "native-session.json").is_file()
    if not root or (not desktop and os.environ.get("XDG_CONFIG_HOME") != str(Path(root) / "config")):
        sys.exit("Run the isolated native header harness.")
    token = os.environ["NORVI_OFFICE_HEADER_TOKEN"]
    broker = Broker(sys.argv[1], token)
    Path(root, "actions-ready.json").write_text(json.dumps({"ready": True}))
    GLib.MainLoop().run()
