#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")" && pwd)"
if [[ ${1:-} != --inside-preview ]]; then
    workspace=/tmp/norvi-office-tests/norvi-office-wayland
    mkdir -p "$workspace"
    output="$(mktemp -d "$workspace/capture.XXXXXXXX")"
    printf 'Wayland captures: %s\n' "$output"
    mkdir -m 700 "$output"/{runtime,config,data,cache,state}
    export XDG_RUNTIME_DIR="$output/runtime" XDG_CONFIG_HOME="$output/config"
    export XDG_DATA_HOME="$output/data" XDG_CACHE_HOME="$output/cache" XDG_STATE_HOME="$output/state"
    export NORVI_OFFICE_TEST_DIR="$output" LIBGL_ALWAYS_SOFTWARE=1
    unset DISPLAY WAYLAND_DISPLAY GSETTINGS_BACKEND
    dbus-run-session -- bash "$root/capture.sh" --inside-preview 2>"$output/session.log" ||
        { tail -30 "$output/shell.log" >&2; exit 1; }
    exit
fi

cd "$NORVI_OFFICE_TEST_DIR"
ulimit -c 0
extension_dir="$XDG_DATA_HOME/gnome-shell/extensions"
mkdir -p "$extension_dir"
cp -a "$root/extension" "$extension_dir/norvi-office-preview@norvi.local"
cp -a "$root/test-driver" "$extension_dir/norvi-office-test@norvi.local"
bms="$HOME/.local/share/gnome-shell/extensions/blur-my-shell@aunetx"
test -f "$bms/metadata.json"
cp -a "$bms" "$extension_dir/blur-my-shell@aunetx"
schemas="$extension_dir/blur-my-shell@aunetx/schemas"
gsettings --schemadir "$schemas" set org.gnome.shell.extensions.blur-my-shell.applications blur false
gsettings --schemadir "$schemas" set org.gnome.shell.extensions.blur-my-shell.popup blur true
mkdir -p "$XDG_CONFIG_HOME"/gtk-{3,4}.0
touch "$XDG_CONFIG_HOME/gtk-4.0/gtk.css"
cp "$root/menu.css" "$XDG_CONFIG_HOME/gtk-3.0/gtk.css"
gsettings set org.gnome.shell enabled-extensions "['blur-my-shell@aunetx', 'norvi-office-preview@norvi.local', 'norvi-office-test@norvi.local']"
gsettings set org.gnome.shell disable-user-extensions false
gsettings set org.gnome.desktop.interface color-scheme prefer-dark
gsettings set org.gnome.desktop.interface toolkit-accessibility true
gsettings set org.gnome.desktop.interface enable-animations false
gsettings set org.gnome.desktop.interface enable-hot-corners false
gsettings set org.gnome.desktop.interface cursor-blink false
gnome-shell --wayland --headless --virtual-monitor=1440x900 --wayland-display=norvi-office --no-x11 >shell.log 2>&1 &
shell=$!
office=
bridge=
trap 'if [[ -n "$office" ]]; then kill "$office" 2>/dev/null || true; fi; if [[ -n "$bridge" ]]; then kill "$bridge" 2>/dev/null || true; fi; kill "$shell" 2>/dev/null || true' EXIT

request() {
    gdbus call --session --dest org.gnome.Shell --object-path /dev/norvi/OfficeTest \
        --method "dev.norvi.OfficeTest.$1" "${@:2}"
}

for attempt in $(seq 1 50); do
    if request Windows >windows-start.txt 2>/dev/null; then break; fi
    kill -0 "$shell"
    sleep 0.2
done
request Windows
/usr/bin/python3 "$root/extension/geometry.py" >bridge.log 2>&1 &
bridge=$!
export NORVI_OFFICE_BRIDGE_PID="$bridge"
export WAYLAND_DISPLAY=norvi-office GDK_BACKEND=wayland SAL_USE_VCLPLUGIN=gtk3
export GTK_THEME=Yaru-purple-dark GDK_SCALE=1 GDK_DPI_SCALE=1
"$root/make-base-fixture.sh" "$PWD"
for app in calc writer impress draw math base; do
    url="file://$PWD/profile-$app"
    unopkg add "-env:UserInstallation=$url" "$root/../../dist/NorviGlass.oxt"
    if [[ "$app" == base ]]; then
        launch=("$PWD/Norvi Sample.odb")
    else
        launch=("--$app")
    fi
    soffice "-env:UserInstallation=$url" --nologo --norestore "${launch[@]}" >"$app.log" 2>&1 &
    office=$!
    sleep 3
    request Windows >"$app-before.txt"
    if [[ "$app" == impress ]]; then
        request Escape
        sleep 0.4
    fi
    request Place
    sleep 1
    /usr/bin/python3 "$root/qualify.py" --settle "$app"
    request Windows >"$app-geometry.txt"
    gdbus call --session --dest org.gnome.Shell --object-path /dev/norvi/OfficeGeometry \
        --method dev.norvi.OfficeGeometry.State >"$app-header.txt"
    request Backdrop true
    sleep 0.6
    request Capture "$app-pattern.png"
    request Backdrop false
    sleep 0.6
    request Capture "$app-solid.png"
    request Backdrop true
    case "$app" in
        draw) request Click 1348 183 ;;
        math|base) request Click 90 151 ;;
        *) request Click 1348 154 ;;
    esac
    sleep 0.6
    request Windows >"$app-menu-geometry.txt"
    request Capture "$app-menu.png"
    if [[ "$app" == calc ]]; then
        gsettings --schemadir "$schemas" set org.gnome.shell.extensions.blur-my-shell.popup blur false
        sleep 0.7
        request Capture calc-menu-no-blur.png
        gsettings --schemadir "$schemas" set org.gnome.shell.extensions.blur-my-shell.popup blur true
        sleep 0.4
        request Escape
        request Click 1348 154
        sleep 0.6
        request Windows >calc-reopen-geometry.txt
        request Capture calc-menu-reopen.png
    fi
    request Escape
    /usr/bin/python3 "$root/qualify.py" "$app"
    kill "$office"
    wait "$office" || true
    office=
done

/usr/bin/python3 "$root/verify.py"
