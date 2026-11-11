#!/bin/bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
output="${1:-$root/out/candidate}"
package=("$output"/norvi-office_*_amd64.deb)
test "${#package[@]}" = 1
payload="$(mktemp -d /tmp/office-payload.XXXXXXXX)"
export HOME="$(mktemp -d /tmp/office-home.XXXXXXXX)"
export XDG_CONFIG_HOME="$HOME/.config" XDG_DATA_HOME="$HOME/.local/share" XDG_CACHE_HOME="$HOME/.cache"
export XDG_RUNTIME_DIR="$(mktemp -d /tmp/office-runtime.XXXXXXXX)"
export GIO_USE_VFS=local SAL_USE_VCLPLUGIN=gtk3 GDK_BACKEND=x11
cleanup() {
    if command -v fusermount3 >/dev/null && [ -d "$XDG_RUNTIME_DIR/doc" ]; then
        fusermount3 -u "$XDG_RUNTIME_DIR/doc" 2>/dev/null || fusermount3 -uz "$XDG_RUNTIME_DIR/doc" 2>/dev/null || true
    fi
    rm -rf -- "$payload" "$HOME" "$XDG_RUNTIME_DIR"
}
trap cleanup EXIT
dpkg-deb -x "${package[0]}" "$payload"
# Root code and preexisting LibreOffice files are never part of this package.
test ! -e "$payload/usr/lib/libreoffice"
test ! -e "$payload/etc"
cd /tmp
xvfb-run -a dbus-run-session -- /usr/bin/python3 "$root/scripts/smoke_installed.py" "$payload" "$root/norvi-office/experiments/native-header/fixtures.py"
