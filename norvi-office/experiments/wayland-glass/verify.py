"""Verify backdrop boundaries and native popup blur from the private captures."""
import ast
import json
from pathlib import Path

from PIL import Image, ImageChops

APPS = ("calc", "writer", "impress", "draw", "math", "base")


def capture_difference(first, second):
    return ImageChops.difference(
        Image.open(first).convert("RGB"), Image.open(second).convert("RGB"),
    )


def windows(file):
    return json.loads(ast.literal_eval(Path(file).read_text())[0])


for app in APPS:
    state = windows(f"{app}-header.txt")[0]
    assert state["enabled"], f"{app}: no adaptive geometry"
    edge = state["buffer"][1] + state["edge"]
    diff = capture_difference(f"{app}-pattern.png", f"{app}-solid.png")
    # Texture sampling can leave another opaque separator pixel. The geometry
    # edge is a strict upper bound, not a promise to blend every chrome pixel.
    assert diff.crop((100, edge - 3, 1290, edge)).getbbox(), f"{app}: no glass near boundary"
    assert not diff.crop((100, edge, 1290, 800)).getbbox(), f"{app}: backdrop beneath glass"
    assert any(win["parent"] == f"libreoffice-{app}" for win in windows(f"{app}-menu-geometry.txt"))
    print(f"{app}: adaptive opaque row {edge}; native menu mapped")

assert any(win["parent"] == "libreoffice-calc" for win in windows("calc-reopen-geometry.txt"))
menu_diff = capture_difference("calc-menu.png", "calc-menu-no-blur.png")
assert menu_diff.crop((1090, 185, 1360, 494)).getbbox(), "Calc popup blur toggle had no effect"
assert not menu_diff.crop((100, 535, 1000, 750)).getbbox(), "Calc grid outside popup changed"
print("Calc: backdrop blur changed the menu, grid stayed identical, popup reopened")
