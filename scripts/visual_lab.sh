#!/usr/bin/env bash
# Private visual lab: the staged desktop runtime with the real LibreOffice
# controls inside a headless GNOME Shell. Nothing appears on the user's desktop,
# and the normal Office profile is never read or written.
# Usage: scripts/visual_lab.sh <scene.py> [scene arguments...]
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
if [[ ${1:-} != --inside ]]; then
    scene="$(realpath "${1:?Provide a scene script}")"
    shift
    workspace=/tmp/norvi-office-tests/lab
    mkdir -p "$workspace"
    output="$(mktemp -d "$workspace/run.XXXXXXXX")"
    mkdir -m 700 "$output"/{runtime,config,data,cache,state,shots}
    # Stage the same layout the Debian candidate installs, without dpkg.
    stage="$output/stage/usr"
    share="$stage/share/norvi-office"
    mkdir -p "$share/experimental" "$share/extensions" "$stage/lib/x86_64-linux-gnu/norvi-office"
    for part in native-header wayland-glass desktop; do
        cp -a "$root/norvi-office/experiments/$part" "$share/experimental/"
    done
    cp -a "$root/norvi-office/experiments/startup" "$share/startup"
    cp "$root/compatibility.json" "$root/VERSION" "$share/"
    (cd "$root/norvi-office/extension" && zip -q -X -0 -r "$share/extensions/NorviGlass.oxt" .)
    cc -std=c11 -Wall -Wextra -Werror -O2 -fPIC -shared \
        "$root/norvi-office/experiments/native-header/header.c" \
        -o "$stage/lib/x86_64-linux-gnu/norvi-office/libnorvi-office-header.so" \
        $(pkg-config --cflags --libs gtk+-3.0 gmodule-2.0)
    # The interface typeface comes from the official Ubuntu package. Keep a
    # private copy for the lab so no system package changes during a check.
    fonts="$workspace/fonts-inter"
    if [[ ! -d "$fonts" ]]; then
        scratch="$(mktemp -d "$workspace/fonts.XXXXXXXX")"
        (cd "$scratch" && apt-get download fonts-inter >/dev/null 2>&1 && dpkg-deb -x fonts-inter_*.deb extracted)
        mv "$scratch/extracted/usr/share/fonts" "$fonts"
        rm -rf "$scratch"
    fi
    mkdir -p "$output/data/fonts"
    cp -a "$fonts/." "$output/data/fonts/"
    export XDG_RUNTIME_DIR="$output/runtime" XDG_CONFIG_HOME="$output/config"
    export XDG_DATA_HOME="$output/data" XDG_CACHE_HOME="$output/cache" XDG_STATE_HOME="$output/state"
    export LAB_DIR="$output" LAB_STAGE="$stage" LIBGL_ALWAYS_SOFTWARE=1 GIO_USE_VFS=local
    unset DISPLAY WAYLAND_DISPLAY GSETTINGS_BACKEND
    printf 'Visual lab: %s\n' "$output"
    status=0
    dbus-run-session -- bash "$root/scripts/visual_lab.sh" --inside "$scene" "$@" 2>"$output/session.log" || status=$?
    if [[ $status != 0 ]]; then tail -30 "$output/session.log" >&2; fi
    printf 'Captures: %s\n' "$output/shots"
    exit $status
fi
shift
cd "$LAB_DIR"
ulimit -c 0
extension_dir="$XDG_DATA_HOME/gnome-shell/extensions"
mkdir -p "$extension_dir" "$XDG_CONFIG_HOME"/gtk-{3,4}.0
touch "$XDG_CONFIG_HOME/gtk-3.0/gtk.css" "$XDG_CONFIG_HOME/gtk-4.0/gtk.css"
driver="$root/norvi-office/experiments/native-header/test-driver"
uuid=$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["uuid"])' "$driver/metadata.json")
cp -a "$driver" "$extension_dir/$uuid"
gsettings set org.gnome.shell enabled-extensions "['$uuid']"
gsettings set org.gnome.shell disable-user-extensions false
gsettings set org.gnome.desktop.interface toolkit-accessibility true
gsettings set org.gnome.desktop.interface gtk-theme "${LAB_THEME:-Yaru-purple-dark}"
gsettings set org.gnome.desktop.interface color-scheme "${LAB_SCHEME:-prefer-dark}"
gsettings set org.gnome.desktop.interface accent-color purple
gsettings set org.gnome.desktop.interface enable-animations false
gsettings set org.gnome.desktop.interface enable-hot-corners false
gsettings set org.gnome.desktop.interface cursor-blink false
gsettings set org.gnome.desktop.wm.preferences button-layout ":minimize,maximize,close"
NORVI_OFFICE_TEST_DIR="$LAB_DIR/shots" gnome-shell --wayland --headless \
    --virtual-monitor="${LAB_MONITOR:-1440x900}" --wayland-display=norvi-lab --no-x11 >shell.log 2>&1 &
shell=$!
cleanup() {
    if [[ -f state/norvi-office/desktop/running.json ]]; then
        /usr/bin/python3 - <<'PY' || true
import json, os, signal
record = json.load(open("state/norvi-office/desktop/running.json"))
for key in ("broker", "geometry"):
    try:
        os.kill(record[key], signal.SIGTERM)
    except (KeyError, ProcessLookupError):
        pass
try:
    os.killpg(record["office_group"], signal.SIGTERM)
except (KeyError, ProcessLookupError):
    pass
PY
    fi
    kill "$shell" 2>/dev/null || true
}
trap cleanup EXIT
for attempt in $(seq 1 150); do
    if gdbus call --session --dest org.gnome.Shell --object-path /dev/norvi/OfficeTest \
        --method dev.norvi.OfficeTest.Windows >/dev/null 2>&1; then break; fi
    kill -0 "$shell"
    sleep 0.2
done
export WAYLAND_DISPLAY=norvi-lab GDK_BACKEND=wayland GDK_SCALE=1 GDK_DPI_SCALE=1
export PYTHONPATH="$root/scripts:$root/norvi-office/experiments/native-header"
/usr/bin/python3 "$@"
