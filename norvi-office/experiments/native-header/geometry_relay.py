"""Reuse the shared semantic boundary with a narrow native-header join."""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wayland-glass/extension"))
import geometry  # noqa: E402

Atspi, Gio, GLib = geometry.Atspi, geometry.Gio, geometry.GLib


def header_bars(node, depth=0):
    if node.get_name() == "Document controls":
        return [node]
    if depth >= 4 or node.get_role() in (
        Atspi.Role.ROOT_PANE, Atspi.Role.DOCUMENT_TEXT, Atspi.Role.TABLE,
    ):
        return []
    return [bar for child in geometry.children(node) for bar in header_bars(child, depth + 1)]


def report():
    started = GLib.get_monotonic_time()
    try:
        data = []
        for app in geometry.children(Atspi.get_desktop(0)):
            if app.get_name() != "soffice":
                continue
            for frame in geometry.children(app):
                if frame.get_role() != Atspi.Role.FRAME:
                    continue
                item = geometry.frame_geometry(frame, app.get_process_id())
                if not item:
                    continue
                bars = header_bars(frame)
                box = geometry.rectangle(bars[0]) if len(bars) == 1 else None
                if box:
                    # Use GTK's actual header allocation: VCL's root-pane top
                    # can retain the original decoration offset after injection.
                    join = box[1] + box[3]
                    item["join_start"] = max(0, join - 1)
                    item["join"] = min(join + 3, item["edge"] - 1)
                data.append(item)
    except GLib.Error:
        data = []
    try:
        Gio.bus_get_sync(Gio.BusType.SESSION, None).call_sync(
            "org.gnome.Shell", "/dev/norvi/OfficeGeometry", "dev.norvi.OfficeGeometry", "Report",
            GLib.Variant("(s)", (json.dumps({"at": started, "windows": data}),)),
            None, Gio.DBusCallFlags.NONE, 250, None,
        )
    except GLib.Error:
        pass
    return GLib.SOURCE_CONTINUE


if __name__ == "__main__":
    if not os.environ.get("NORVI_OFFICE_TEST_DIR"):
        sys.exit("Run the isolated native header harness.")
    Atspi.set_timeout(100, 100)
    GLib.timeout_add(200, report)
    GLib.MainLoop().run()
