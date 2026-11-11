"""Read chrome geometry, never document contents, on the private preview bus."""
import json
import os

import gi

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi, Gio, GLib  # noqa: E402


def rectangle(accessible):
    states = accessible.get_state_set()
    if not all(states.contains(state) for state in (Atspi.StateType.VISIBLE, Atspi.StateType.SHOWING)):
        return None
    component = accessible.get_component_iface()
    if component is None:
        return None
    box = component.get_extents(Atspi.CoordType.WINDOW)
    if min(box.x, box.y) < 0 or min(box.width, box.height) <= 0:
        return None
    return [box.x, box.y, box.width, box.height]


def children(accessible):
    count = accessible.get_child_count()
    if not 0 <= count <= 64:
        return []
    return [child for index in range(count)
            if (child := accessible.get_child_at_index(index)) is not None]


def roots(accessible, depth=0):
    """Only descend through chrome containers, never into a document or table."""
    if accessible.get_role() == Atspi.Role.ROOT_PANE:
        return [accessible]
    if depth >= 4 or accessible.get_role() not in (
        Atspi.Role.FRAME, Atspi.Role.PANEL, Atspi.Role.FILLER,
    ):
        return []
    return [root for child in children(accessible) for root in roots(child, depth + 1)]


def frame_geometry(frame, pid):
    bounds = rectangle(frame)
    panes = roots(frame)
    if bounds is None or len(panes) != 1:
        return None
    pane = panes[0]
    root = rectangle(pane)
    if root is None:
        return None
    # LibreOffice's root pane contains the central work panel and surrounding
    # dock/toolbar panels. Require one large central panel, not a guessed height.
    bodies = []
    for child in children(pane):
        if child.get_role() != Atspi.Role.PANEL:
            continue
        box = rectangle(child)
        if box and box[2] > root[2] / 2 and box[3] > root[3] / 2:
            bodies.append(box)
    if len(bodies) != 1:
        return None
    body = bodies[0]
    if not (root[1] < body[1] < bounds[3] / 2 and
            root[0] <= body[0] and body[0] + body[2] <= root[0] + root[2] and
            body[1] + body[3] <= root[1] + root[3]):
        return None
    return {"pid": pid, "title": frame.get_name(), "size": bounds[2:],
            "edge": body[1] - 1, "join": root[1]}


def snapshot():
    result = []
    for app in children(Atspi.get_desktop(0)):
        if app.get_name() != "soffice":
            continue
        pid = app.get_process_id()
        for frame in children(app):
            if frame.get_role() == Atspi.Role.FRAME:
                geometry = frame_geometry(frame, pid)
                if geometry:
                    result.append(geometry)
    return result


def report():
    started = GLib.get_monotonic_time()
    try:
        data = snapshot()
    except GLib.Error:
        data = []
    try:
        Gio.bus_get_sync(Gio.BusType.SESSION, None).call_sync(
            "org.gnome.Shell", "/dev/norvi/OfficeGeometry", "dev.norvi.OfficeGeometry", "Report",
            GLib.Variant("(s)", (json.dumps({"at": started, "windows": data}),)),
            None, Gio.DBusCallFlags.NONE, 250, None,
        )
    except GLib.Error:
        pass  # Shell expires the last report if this bridge or accessibility stops.
    return GLib.SOURCE_CONTINUE


if __name__ == "__main__":
    if not os.environ.get("NORVI_OFFICE_TEST_DIR"):
        raise SystemExit("Run the isolated preview harness.")
    Atspi.set_timeout(100, 100)
    GLib.timeout_add(200, report)
    GLib.MainLoop().run()
