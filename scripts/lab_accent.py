"""Capture Calc under the lab's accent, then again after the accent changes while it stays open.

Usage: LAB_ACCENT=orange scripts/visual_lab.sh scripts/lab_accent.py blue
Captures accent-start.png and accent-live.png. Everything GTK or LibreOffice
paints in the accent changes in the second; the few ribbon icons drawn in the
accent change at the next start of the suite.
"""
import subprocess
import sys
import time

import lab


def main(arguments):
    accent = arguments[0] if arguments else "blue"
    documents = lab.fixtures()
    try:
        lab.launch("calc", documents["calc"])
        lab.capture("accent-start")
        subprocess.run(["gsettings", "set", "org.gnome.desktop.interface", "accent-color", accent], check=True)
        time.sleep(3)
        lab.capture("accent-live")
    finally:
        lab.stop()


if __name__ == "__main__":
    main(sys.argv[1:])
