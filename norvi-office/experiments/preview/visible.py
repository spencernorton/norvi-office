#!/usr/bin/python3
"""Require a mapped host viewer with a connected private video stream."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def video_connected(objects, viewer_pid):
    clients = {item["id"] for item in objects if item["type"].endswith(":Client")
               and str(item["info"]["props"].get("application.process.id")) == str(viewer_pid)}
    inputs = {item["id"] for item in objects if item["type"].endswith(":Node")
              and item["info"]["props"].get("client.id") in clients
              and item["info"]["props"].get("media.class") == "Stream/Input/Video"
              and item["info"].get("state") == "running"}
    return any(item["type"].endswith(":Link") and item["info"].get("state") == "active"
               and item["info"].get("input-node-id") in inputs for item in objects)


def observe_viewer(shell_pid):
    import gi
    gi.require_version("Atspi", "2.0")
    from gi.repository import Atspi, GLib
    Atspi.set_timeout(200, 200)
    for app in Atspi.get_desktop(0):
        pid = app.get_process_id()
        try:
            process = Path(f"/proc/{pid}")
            if process.joinpath("comm").read_text().strip() != "mutter-devkit":
                continue
            if int(process.joinpath("stat").read_text().rsplit(")", 1)[1].split()[1]) != shell_pid:
                continue
            for window in app:
                states = window.get_state_set()
                if not all(states.contains(state) for state in (Atspi.StateType.VISIBLE, Atspi.StateType.SHOWING)):
                    continue
                rect = window.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
                if rect.width < 100 or rect.height < 100:
                    continue
                result = subprocess.run(["pw-dump"], capture_output=True, text=True, timeout=3, check=True)
                if video_connected(json.loads(result.stdout), pid):
                    return {"pid": pid, "title": window.get_name(), "mapped": True,
                            "video_stream": "active", "size": [rect.width, rect.height],
                            "parent_display": os.environ.get("WAYLAND_DISPLAY")}
        except (OSError, ValueError, GLib.Error, subprocess.SubprocessError):
            continue
    return None


def main():
    until = time.monotonic() + 30
    while time.monotonic() < until:
        result = observe_viewer(int(sys.argv[1]))
        if result:
            print(json.dumps(result))
            return
        time.sleep(.2)
    raise SystemExit("The host preview window did not map with an active video stream")


if __name__ == "__main__":
    main()
