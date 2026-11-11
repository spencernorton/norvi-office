#!/usr/bin/env python3
from pathlib import Path
from build import extension
root = Path(__file__).resolve().parent.parent
output = root / "norvi-office/dist"
output.mkdir(exist_ok=True)
extension(root / "norvi-office/extension", output / "NorviGlass.oxt", 315532800)
