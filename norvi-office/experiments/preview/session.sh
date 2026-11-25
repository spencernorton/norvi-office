#!/bin/bash
set -euo pipefail
root="$(cd "$(dirname "$0")/../native-header" && pwd)"
cd "$NORVI_OFFICE_TEST_DIR"
printf '%s' "$DBUS_SESSION_BUS_ADDRESS" >session-address
extension_dir="$XDG_DATA_HOME/gnome-shell/extensions"
mkdir -p "$extension_dir" "$XDG_CONFIG_HOME/gtk-3.0" "$XDG_CONFIG_HOME/gtk-4.0"
touch "$XDG_CONFIG_HOME/gtk-3.0/gtk.css" "$XDG_CONFIG_HOME/gtk-4.0/gtk.css"
cp -a "$root/../wayland-glass/extension" "$extension_dir/norvi-office-preview@norvi.local"
cp -a "$root/test-driver" "$extension_dir/norvi-office-test@norvi.local"
cp -a "$HOME/.local/share/gnome-shell/extensions/blur-my-shell@aunetx" "$extension_dir/blur-my-shell@aunetx"
export NORVI_OFFICE_POPUP_SCHEMAS="$extension_dir/blur-my-shell@aunetx/schemas"
gsettings --schemadir "$NORVI_OFFICE_POPUP_SCHEMAS" set org.gnome.shell.extensions.blur-my-shell.applications blur false
gsettings --schemadir "$NORVI_OFFICE_POPUP_SCHEMAS" set org.gnome.shell.extensions.blur-my-shell.popup blur true
gsettings set org.gnome.shell enabled-extensions "['blur-my-shell@aunetx', 'norvi-office-preview@norvi.local', 'norvi-office-test@norvi.local']"
gsettings set org.gnome.shell disable-user-extensions false
gsettings set org.gnome.desktop.interface toolkit-accessibility true
gsettings set org.gnome.desktop.interface gtk-theme Yaru-purple-dark
gsettings set org.gnome.desktop.interface color-scheme prefer-dark
gsettings set org.gnome.desktop.wm.preferences button-layout ':minimize,maximize,close'
gsettings set org.gnome.desktop.interface enable-animations "$NORVI_OFFICE_ANIMATIONS"
gsettings set org.gnome.desktop.background picture-uri "$NORVI_OFFICE_WALLPAPER"
gsettings set org.gnome.desktop.background picture-uri-dark "$NORVI_OFFICE_WALLPAPER"
pipewire >pipewire.log 2>&1 &
pipewire_pid=$!
for attempt in $(seq 1 50); do
    if [[ -S "$XDG_RUNTIME_DIR/pipewire-0" ]]; then break; fi
    kill -0 "$pipewire_pid"
    sleep 0.1
done
# The policy-only instance links the private screen stream to its viewer. It
# never starts hardware audio, Bluetooth or camera monitors.
wireplumber --profile=policy >wireplumber.log 2>&1 &
policy=$!
# Devkit creates the visible monitor itself. A separate --virtual-monitor
# would put Office on an additional screen that the user cannot see.
gnome-shell --wayland --devkit --wayland-display=norvi-office-test --no-x11 >shell.log 2>&1 &
shell=$!
office=
broker=
geometry=
cleanup() {
    for pid in "$broker" "$geometry"; do
        if [[ -n "$pid" ]]; then kill "$pid" 2>/dev/null || true; fi
    done
    if [[ -n "$office" ]]; then kill -- "-$office" 2>/dev/null || true; fi
    kill "$shell" "$policy" "$pipewire_pid" 2>/dev/null || true
}
trap cleanup EXIT
request() {
    gdbus call --session --dest org.gnome.Shell --object-path /dev/norvi/OfficeTest \
        --method "dev.norvi.OfficeTest.$1" "${@:2}"
}
for attempt in $(seq 1 150); do
    if request Windows >windows-start.json 2>/dev/null; then break; fi
    kill -0 "$shell"
    sleep 0.2
done
/usr/bin/python3 "$root/../preview/visible.py" "$shell" >visible.json
export WAYLAND_DISPLAY=norvi-office-test GDK_BACKEND=wayland SAL_USE_VCLPLUGIN=gtk3
export GTK_THEME=Yaru-purple-dark GDK_SCALE=1 GDK_DPI_SCALE=1
/usr/bin/python3 "$root/../preview/prepare.py"
pipe="norvi_preview_${NORVI_OFFICE_PREVIEW_APP}_$$"
/usr/bin/python3 "$root/geometry_relay.py" >geometry.log 2>&1 &
geometry=$!
if [[ "$NORVI_OFFICE_PREVIEW_APP" == calc ]]; then
    export NORVI_OFFICE_CALC_RIBBON=1
    filename="$PWD/Ember Plan.ods"
else
    filename="$PWD/Ember Brief.odt"
fi
GTK3_MODULES="$NORVI_OFFICE_PREVIEW_LIBRARY" setsid soffice \
    "-env:UserInstallation=file://$PWD/profile-$NORVI_OFFICE_PREVIEW_APP" --nologo --norestore \
    "--accept=pipe,name=$pipe;urp;" "$filename" >office.log 2>&1 &
office=$!
/usr/bin/python3 "$root/actions.py" "$pipe" >actions.log 2>&1 &
broker=$!
/usr/bin/python3 "$root/../preview/settle.py" "$pipe" "$NORVI_OFFICE_PREVIEW_APP"
request Place >placement.txt
request WindowState maximized >window-state.txt
sleep 1
request Capture preview-ready.png >capture.txt
printf '{"shell_pid":%s,"office_group":%s,"broker_pid":%s,"geometry_pid":%s,"pipe":"%s","viewer":%s}\n' \
    "$shell" "$office" "$broker" "$geometry" "$pipe" "$(cat visible.json)" >ready.json
wait "$shell"
