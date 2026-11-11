#!/usr/bin/env bash
# Install the OXT into a fresh profile and launch an app for review.
set -euo pipefail
cd "$(dirname "$0")/.."

app="${1:-writer}"
case "$app" in
    writer|calc|impress) ;;
    *) echo "Usage: $0 [writer|calc|impress]" >&2; exit 2 ;;
esac
profile="$(mktemp -d /tmp/lo-norvi-glass-profile.XXXXXXXX)"
url="file://$profile"
unopkg add "-env:UserInstallation=$url" dist/NorviGlass.oxt
setsid /usr/bin/python3 experiments/startup/launch.py --profile "$profile" --app "$app" &
echo "starting $app with disposable profile $profile"
