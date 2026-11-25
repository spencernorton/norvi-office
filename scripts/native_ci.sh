#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
# These are generated candidate outputs, never release truth.
rm -f out/candidate/norvi-office_*.deb out/candidate/SHA256SUMS.txt
rm -f out/reproduction/norvi-office_*.deb out/reproduction/SHA256SUMS.txt
scripts/check.sh
gjs -m tests/test_native_geometry.js
bash norvi-office/experiments/native-header/build.sh /tmp/norvi-office-tests/ci-build
python3 -m unittest discover -s norvi-office/experiments/wayland-glass -p test_geometry.py -v
python3 scripts/build.py --output out/candidate
(umask 077; python3 scripts/build.py --output out/reproduction)
cmp out/candidate/*.deb out/reproduction/*.deb
bash scripts/qualify_package.sh out/candidate >out/installed-runtime.log 2>&1
python3 scripts/qualify_lifecycle.py out/candidate/*.deb
python3 norvi-office/experiments/live-tools/qualify_formats.py >out/format-contract.log 2>&1
python3 scripts/upstream_report.py out/upstream.json
