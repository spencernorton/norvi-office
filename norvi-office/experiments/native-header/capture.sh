#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")" && pwd)"
glass="$root/../wayland-glass"
if [[ ${1:-} != --inside-preview ]]; then
    workspace=/tmp/norvi-office-tests/norvi-office-native-header
    mkdir -p "$workspace"
    output="$(mktemp -d "$workspace/capture.XXXXXXXX")"
    printf 'Native header preview: %s\n' "$output"
    mkdir -m 700 "$output"/{runtime,config,data,cache,state}
    /usr/bin/python3 "$root/evidence.py" snapshot "$output"
    bash "$root/build.sh" "$output/build"
    export XDG_RUNTIME_DIR="$output/runtime" XDG_CONFIG_HOME="$output/config"
    export XDG_DATA_HOME="$output/data" XDG_CACHE_HOME="$output/cache" XDG_STATE_HOME="$output/state"
    export NORVI_OFFICE_TEST_DIR="$output" LIBGL_ALWAYS_SOFTWARE=1 GIO_USE_VFS=local
    export NORVI_OFFICE_HEADER_TOKEN="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
    unset DISPLAY WAYLAND_DISPLAY GSETTINGS_BACKEND
    dbus-run-session -- bash "$root/capture.sh" --inside-preview 2>"$output/session.log" || \
        { tail -25 "$output/session.log" >&2; exit 1; }
    exit
fi
cd "$NORVI_OFFICE_TEST_DIR"
ulimit -c 0
extension_dir="$XDG_DATA_HOME/gnome-shell/extensions"
mkdir -p "$extension_dir" "$XDG_CONFIG_HOME"/gtk-{3,4}.0
touch "$XDG_CONFIG_HOME/gtk-3.0/gtk.css" "$XDG_CONFIG_HOME/gtk-4.0/gtk.css"
cp -a "$glass/extension" "$extension_dir/norvi-office-preview@norvi.local"
cp -a "$root/test-driver" "$extension_dir/norvi-office-test@norvi.local"
bms="$HOME/.local/share/gnome-shell/extensions/blur-my-shell@aunetx"
cp -a "$bms" "$extension_dir/blur-my-shell@aunetx"
export NORVI_OFFICE_POPUP_SCHEMAS="$extension_dir/blur-my-shell@aunetx/schemas"
gsettings --schemadir "$NORVI_OFFICE_POPUP_SCHEMAS" set org.gnome.shell.extensions.blur-my-shell.applications blur false
gsettings --schemadir "$NORVI_OFFICE_POPUP_SCHEMAS" set org.gnome.shell.extensions.blur-my-shell.popup blur true
gsettings set org.gnome.shell enabled-extensions "['blur-my-shell@aunetx', 'norvi-office-preview@norvi.local', 'norvi-office-test@norvi.local']"
gsettings set org.gnome.shell disable-user-extensions false
gsettings set org.gnome.desktop.interface toolkit-accessibility true
theme="${NORVI_OFFICE_THEME:-Yaru-purple-dark}"
gsettings set org.gnome.desktop.interface gtk-theme "$theme"
case "$theme" in
    *HighContrast*)
        gsettings set org.gnome.desktop.interface color-scheme prefer-light
        gsettings set org.gnome.desktop.a11y.interface high-contrast true ;;
    *dark*) gsettings set org.gnome.desktop.interface color-scheme prefer-dark ;;
    *) gsettings set org.gnome.desktop.interface color-scheme prefer-light ;;
esac
gsettings set org.gnome.desktop.interface enable-animations false
gsettings set org.gnome.desktop.interface enable-hot-corners false
gsettings set org.gnome.desktop.wm.preferences button-layout ":minimize,maximize,close"
gsettings set org.gnome.desktop.interface cursor-blink false
monitor=1440x900
if [[ ${NORVI_OFFICE_SCALE_TEST:-0} == 1 ]]; then monitor=2880x1800; fi
gnome-shell --wayland --headless --virtual-monitor="$monitor" --wayland-display=norvi-office --no-x11 >shell.log 2>&1 &
shell=$!
geometry=
trap 'if [[ -n "$geometry" ]]; then kill "$geometry" 2>/dev/null || true; fi; kill "$shell" 2>/dev/null || true' EXIT
for attempt in $(seq 1 70); do
    if gdbus call --session --dest org.gnome.Shell --object-path /dev/norvi/OfficeTest \
        --method dev.norvi.OfficeTest.Windows >windows-start.txt 2>/dev/null; then break; fi
    kill -0 "$shell"
    sleep 0.2
done
export WAYLAND_DISPLAY=norvi-office GDK_BACKEND=wayland SAL_USE_VCLPLUGIN=gtk3
export GTK_THEME="$theme"
if [[ ${NORVI_OFFICE_SCALE_TEST:-0} == 1 ]]; then
    unset GDK_SCALE GDK_DPI_SCALE
else
    export GDK_SCALE=1 GDK_DPI_SCALE=1
fi
/usr/bin/python3 "$root/geometry_relay.py" >geometry.log 2>&1 &
geometry=$!
export NORVI_OFFICE_BRIDGE_PID="$geometry"
/usr/bin/python3 "$root/fixtures.py" "$PWD"
if [[ ${NORVI_OFFICE_STARTUP_TEST:-0} == 1 ]]; then
    /usr/bin/python3 "$root/../startup/qualify.py" "$root"
fi
if [[ -n "${NORVI_OFFICE_LIVE_TOOLS_OXT:-}" ]]; then
    /usr/bin/python3 "$root/../live-tools/qualify.py" "$root" "$NORVI_OFFICE_LIVE_TOOLS_OXT"
fi
/usr/bin/python3 "$root/verify.py" "$root"
/usr/bin/python3 "$root/evidence.py" finish "$PWD"
