#!/bin/sh
set -eu
root="$(cd "$(dirname "$0")/../.." && pwd)"
exec python3 "$root/scripts/build_extensions.py"
