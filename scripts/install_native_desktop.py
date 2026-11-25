#!/usr/bin/python3
"""Run the versioned desktop component's reversible user installer."""
from pathlib import Path
import runpy

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parents[1] /
                      "norvi-office/experiments/desktop/integrate.py"), run_name="__main__")
