#!/usr/bin/python3
"""Launch an isolated Office profile with a small native startup prompt."""
import argparse
import os
import re
from pathlib import Path
import subprocess
import sys
from time import monotonic, sleep
from urllib.parse import urlsplit

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("Atspi", "2.0")
gi.require_version("Atk", "1.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Atk, Atspi, Gdk, GdkPixbuf, GLib, Gtk  # noqa: E402

APPS = ("writer", "calc", "impress", "draw", "base", "math", "startcenter")
SHOW_AFTER = 0.15
GIVE_UP_AFTER = 8
ICON = Path(__file__).resolve().parent / "assets" / "office.png"
CSS = b"""
window#office-startup { background-color: transparent; }
#office-card {
    background-color: #272727;
    border: 1px solid #585263;
    border-radius: 18px;
    padding: 20px 36px;
}
#office-wordmark { color: #f2eff8; font-size: 26px; font-weight: 600; }
"""


class LoadingLine(Gtk.DrawingArea):
    def __init__(self, animated):
        super().__init__()
        self.phase = 0 if animated else 0.675
        self.set_size_request(136, 3)
        self.get_accessible().set_name("Loading")
        self.get_accessible().set_role(Atk.Role.ANIMATION if animated else Atk.Role.IMAGE)
        self.connect("draw", self.draw_motion)

    def draw_motion(self, _widget, context):
        width, height = self.get_allocated_width(), self.get_allocated_height()
        context.set_source_rgba(0.71, 0.60, 0.96, 0.16)
        context.rectangle(0, 0, width, height)
        context.fill()
        # A soft highlight travels across the track and wraps continuously.
        position = (self.phase / 1.35 % 1) * (width + 48) - 24
        for offset in range(-24, 25):
            context.set_source_rgba(0.71, 0.60, 0.96, 0.85 * (1 - abs(offset) / 25))
            context.rectangle(position + offset, 0, 1.1, height)
            context.fill()
        return False


def animate(indicator):
    start = None

    def tick(_widget, clock):
        nonlocal start
        now = clock.get_frame_time()
        if start is None:
            start = now
        indicator.phase = (now - start) / 1_000_000
        indicator.queue_draw()
        return GLib.SOURCE_CONTINUE

    indicator.add_tick_callback(tick)


def make_window():
    window = Gtk.Window(title="office", decorated=False, resizable=False)
    window.set_type_hint(Gdk.WindowTypeHint.SPLASHSCREEN)
    window.set_position(Gtk.WindowPosition.CENTER)
    window.set_skip_taskbar_hint(True)
    window.set_accept_focus(False)
    window.set_focus_on_map(False)
    window.set_name("office-startup")
    visual = window.get_screen().get_rgba_visual()
    if visual is not None:
        window.set_visual(visual)
    provider = Gtk.CssProvider()
    provider.load_from_data(CSS)
    Gtk.StyleContext.add_provider_for_screen(window.get_screen(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    card.set_name("office-card")
    row = Gtk.Box(spacing=13)
    row.set_halign(Gtk.Align.CENTER)
    motion = window.get_settings().get_property("gtk-enable-animations")
    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(ICON), 44, 44, True)
    window.set_icon_from_file(str(ICON))
    icon = Gtk.Image.new_from_pixbuf(pixbuf)
    icon.get_accessible().set_name("Office")
    row.pack_start(icon, False, False, 0)
    label = Gtk.Label(label="office")
    label.set_name("office-wordmark")
    row.pack_start(label, False, False, 0)
    card.pack_start(row, False, False, 0)
    sweep = LoadingLine(animated=motion)
    card.pack_start(sweep, False, False, 0)
    window.add(card)
    if motion:
        animate(sweep)
    return window


def office_ready(group, allow_startcenter=False):
    desktop = Atspi.get_desktop(0)
    if desktop is None:
        return False
    for index in range(desktop.get_child_count()):
        app = desktop.get_child_at_index(index)
        if app is None or app.get_name() != "soffice":
            continue
        try:
            if os.getpgid(app.get_process_id()) != group:
                continue
        except ProcessLookupError:
            continue
        for child in range(app.get_child_count()):
            item = app.get_child_at_index(child)
            if item is None or not item.get_state_set().contains(Atspi.StateType.SHOWING):
                continue
            role = item.get_role()
            if role in (Atspi.Role.DIALOG, Atspi.Role.ALERT):
                return True
            if role == Atspi.Role.FRAME:
                title = item.get_name() or ""
                # A fresh profile can briefly map the generic Start Center.
                if title and (allow_startcenter or not re.fullmatch(r"LibreOffice(?: [0-9.]+)?", title)):
                    return True
    return False


def readiness_probe(group, allow_startcenter=False):
    # AT-SPI calls can block. Keep them out of the animated GTK process.
    Atspi.set_timeout(75, 75)
    until = monotonic() + GIVE_UP_AFTER
    while monotonic() < until:
        try:
            if office_ready(group, allow_startcenter):
                return 0
        except GLib.Error:
            pass
        sleep(0.07)
    return 1


def launch(command, allow_startcenter=False):
    child = subprocess.Popen(command, start_new_session=True)
    if not Gtk.init_check()[0]:
        return 0
    popup = make_window()
    probe = subprocess.Popen([sys.executable, __file__, "--readiness-probe", str(child.pid),
                              str(int(allow_startcenter))])
    started = monotonic()
    result = 0

    def update():
        nonlocal result
        status = child.poll()
        elapsed = monotonic() - started
        if status is not None or probe.poll() == 0 or elapsed >= GIVE_UP_AFTER:
            result = 0 if status is None else status
            Gtk.main_quit()
            return GLib.SOURCE_REMOVE
        if elapsed >= SHOW_AFTER and not popup.get_visible():
            popup.show_all()
        return GLib.SOURCE_CONTINUE

    def dismiss(*_):
        Gtk.main_quit()
        return True

    # Closing the prompt never closes the application that it launched.
    popup.connect("delete-event", dismiss)
    GLib.timeout_add(40, update)
    try:
        Gtk.main()
    finally:
        popup.destroy()
        if probe.poll() is None:
            probe.terminate()
            probe.wait()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--profile", type=Path, help="Disposable LibreOffice profile directory")
    mode.add_argument("--desktop", action="store_true", help="Use the existing normal Office profile")
    parser.add_argument("--app", choices=APPS, default="writer")
    parser.add_argument("files", nargs="*", help="Local paths or document URLs")
    args = parser.parse_args()
    command = ["libreoffice", "--nologo"]
    if args.profile is not None:
        profile = args.profile.resolve()
        default = Path.home() / ".config"
        live_roots = {(root / "libreoffice").resolve()
                      for root in (default, Path(os.environ.get("XDG_CONFIG_HOME", default)))}
        if any(profile == live or live in profile.parents for live in live_roots):
            parser.error("Use a separate preview profile.")
        command.append("-env:UserInstallation=" + profile.as_uri())
    if args.app != "startcenter":
        command.append("--" + args.app)
    command.extend(target if urlsplit(target).scheme else str(Path(target).expanduser().resolve())
                   for target in args.files)
    try:
        return launch(command, allow_startcenter=args.app == "startcenter")
    except OSError as error:
        parser.exit(1, f"Could not start Office: {error.strerror}\n")


if __name__ == "__main__":
    if len(sys.argv) in (3, 4) and sys.argv[1] == "--readiness-probe":
        raise SystemExit(readiness_probe(int(sys.argv[2]), len(sys.argv) == 4 and sys.argv[3] == "1"))
    raise SystemExit(main())
