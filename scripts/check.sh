#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
python3 -m compileall -q scripts norvi-office/experiments
python3 -m unittest discover -s tests -v
desktop-file-validate packaging/norvi-office.desktop
git diff --check
