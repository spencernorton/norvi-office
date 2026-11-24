"""Capture menus, a dialog, the side panel, a prompt and a narrow window in the private visual lab.

Usage: scripts/visual_lab.sh scripts/lab_states.py
"""
import json
from pathlib import Path
import threading
import time

import lab

# Ribbon and header controls of a maximised 1440 px Calc window, relative to its frame.
POPUPS = (("calc-menu", 1231, 23), ("calc-find", 1368, 146), ("calc-number", 805, 110),
          ("calc-font", 355, 110), ("calc-borders", 291, 147))


def dispatch(command, settle=2.5):
    """Run one command in the lab's Office. A dialog keeps the call open, so do not wait for it."""
    record = json.loads((lab.STATE / "running.json").read_text())

    def run():
        context = lab.connect(record["pipe"], Path(record["profile"]))
        manager = context.ServiceManager
        desktop = manager.createInstanceWithContext("com.sun.star.frame.Desktop", context)
        helper = manager.createInstanceWithContext("com.sun.star.frame.DispatchHelper", context)
        helper.executeDispatch(desktop.Frames.getByIndex(0), command, "", 0, ())

    threading.Thread(target=run, daemon=True).start()
    time.sleep(settle)


def main():
    document = lab.fixtures()["calc"]
    try:
        lab.launch("calc", document)
        left, top = lab.office_windows()[0]["frame"][:2]
        for name, x, y in POPUPS:
            lab.click(left + x, top + y, settle=1.2)
            lab.capture(name)
            lab.call("Escape")
            time.sleep(0.6)
        dispatch(".uno:FormatCellDialog")
        lab.capture("calc-dialog")
        lab.call("Escape")
        time.sleep(1)
        dispatch(".uno:SidebarDeck.PropertyDeck")
        lab.capture("calc-sidebar")
        dispatch(".uno:InsertRowsBefore", settle=1)  # an edit, so closing asks to save
        dispatch(".uno:CloseDoc")
        lab.capture("calc-prompt")
        lab.call("Escape")
        time.sleep(0.6)
    finally:
        lab.stop()
    try:
        lab.launch("calc", document, state=(1024, 700))
        lab.capture("calc-narrow")
    finally:
        lab.stop()


if __name__ == "__main__":
    main()
