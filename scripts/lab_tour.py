"""Capture every module (and each ribbon tab) in the private visual lab.

Usage: scripts/visual_lab.sh scripts/lab_tour.py [app ...] [--tabs] [--outline]
"""
import sys

import lab

APPS = ("calc", "writer", "impress", "draw", "base", "math", "startcenter")
RIBBON = APPS[:4]


def main(arguments):
    apps = [item for item in arguments if not item.startswith("--")] or APPS
    documents = lab.fixtures()
    for app in apps:
        files = [documents[app]] if app in documents else []
        try:
            lab.launch(app, *files)
            lab.capture(app)
            if "--outline" in arguments:
                (lab.SHOTS / (app + "-outline.txt")).write_text(lab.outline() + "\n")
            if "--tabs" in arguments and app in RIBBON:
                # The ribbon is absent from the accessibility tree. LibreOffice
                # gives its tabs a fixed 100 px, so sweep until a click changes nothing.
                left, top = lab.office_windows()[0]["frame"][:2]
                previous = None
                for index, letter in enumerate("abcdefghijklmnopqr"):
                    lab.click(left + 52 + 100 * index, top + 65, settle=1.2)
                    shot = lab.capture(f"{app}-tab-{letter}")
                    strip = lab.band(shot, top + 47, 160)
                    if strip == previous:
                        shot.unlink()
                        break
                    previous = strip
        finally:
            lab.stop()


if __name__ == "__main__":
    main(sys.argv[1:])
