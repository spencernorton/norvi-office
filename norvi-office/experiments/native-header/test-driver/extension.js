import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Shell from 'gi://Shell';
import St from 'gi://St';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const API = `<node><interface name="dev.norvi.OfficeTest">
  <method name="Windows"><arg type="s" direction="out"/></method>
  <method name="Screen"><arg type="s" direction="out"/></method>
  <method name="Place"/>
  <method name="DismissOverview"/>
  <method name="Click"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
  <method name="Escape"/>
  <method name="Resize"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
  <method name="WindowState"><arg type="s" direction="in"/></method>
  <method name="Key"><arg type="s" direction="in"/></method>
  <method name="Drag"><arg type="i" direction="in"/><arg type="i" direction="in"/>
    <arg type="i" direction="in"/><arg type="i" direction="in"/></method>
  <method name="Backdrop"><arg type="b" direction="in"/></method>
  <method name="Capture"><arg type="s" direction="in"/></method>
</interface></node>`;
Gio._promisify(Shell.Screenshot.prototype, 'screenshot');

export default class Driver extends Extension {
    enable() {
        this.directory = GLib.getenv('NORVI_OFFICE_TEST_DIR');
        if (!this.directory)
            throw new Error('Start the private capture harness to enable this driver.');
        const seat = Clutter.get_default_backend().get_default_seat();
        this.pointer = seat.create_virtual_device(Clutter.InputDeviceType.POINTER_DEVICE);
        this.keyboard = seat.create_virtual_device(Clutter.InputDeviceType.KEYBOARD_DEVICE);
        this.plate = new St.Widget({width: 1440, height: 900, reactive: false});
        Main.layoutManager._backgroundGroup.add_child(this.plate);
        this.Backdrop(true);
        this.exported = Gio.DBusExportedObject.wrapJSObject(API, this);
        this.exported.export(Gio.DBus.session, '/dev/norvi/OfficeTest');
    }

    Windows() {
        return JSON.stringify(global.get_window_actors().map(actor => {
            const w = actor.meta_window;
            const f = w.get_frame_rect();
            const b = w.get_buffer_rect();
            return {app: w.get_wm_class(), title: w.get_title(), type: w.get_window_type(),
                parent: w.get_transient_for()?.get_wm_class() ?? null,
                frame: [f.x, f.y, f.width, f.height], buffer: [b.x, b.y, b.width, b.height]};
        }));
    }

    Screen() {
        return JSON.stringify({size: [global.stage.width, global.stage.height],
            scale: global.display.get_monitor_scale(0)});
    }

    DismissOverview() {
        Main.overview.hide();
    }

    Place() {
        this.DismissOverview();
        const window = global.get_window_actors().find(actor =>
            actor.meta_window.get_wm_class()?.startsWith('libreoffice-')).meta_window;
        window.activate(global.get_current_time());
        window.unmaximize();
        window.move_resize_frame(true, 68, 68, 1300, 735);
        this.pointer.notify_absolute_motion(GLib.get_monotonic_time(), 1420, 865);
    }

    officeWindow() {
        return global.get_window_actors().find(actor =>
            actor.meta_window.get_window_type() === 0 &&
            actor.meta_window.get_wm_class()?.startsWith('libreoffice-')).meta_window;
    }

    Resize(width, height) {
        if (width < 700 || width > 1400 || height < 450 || height > 850)
            throw new Error('Invalid fixture size');
        this.officeWindow().move_resize_frame(true, 68, 68, width, height);
    }

    WindowState(state) {
        const window = this.officeWindow();
        if (state === 'maximized')
            window.maximize();
        else if (state === 'restored')
            window.unmaximize();
        else if (state === 'fullscreen')
            window.make_fullscreen();
        else if (state === 'normal')
            window.unmake_fullscreen();
        else
            throw new Error('Invalid fixture window state');
    }

    Click(x, y) {
        const now = GLib.get_monotonic_time();
        this.pointer.notify_absolute_motion(now, x, y);
        GLib.timeout_add(GLib.PRIORITY_DEFAULT, 75, () => {
            const time = GLib.get_monotonic_time();
            this.pointer.notify_button(time, 1, Clutter.ButtonState.PRESSED);
            this.pointer.notify_button(time + 1, 1, Clutter.ButtonState.RELEASED);
            return GLib.SOURCE_REMOVE;
        });
    }

    Escape() {
        const now = GLib.get_monotonic_time();
        this.keyboard.notify_keyval(now, Clutter.KEY_Escape, Clutter.KeyState.PRESSED);
        this.keyboard.notify_keyval(now, Clutter.KEY_Escape, Clutter.KeyState.RELEASED);
    }

    Key(name) {
        const key = {Return: Clutter.KEY_Return, Tab: Clutter.KEY_Tab,
            F10: Clutter.KEY_F10, F6: Clutter.KEY_F6,
            Down: Clutter.KEY_Down, Right: Clutter.KEY_Right, Escape: Clutter.KEY_Escape}[name];
        if (!key)
            throw new Error('Unsupported fixture key');
        const now = GLib.get_monotonic_time();
        this.keyboard.notify_keyval(now, key, Clutter.KeyState.PRESSED);
        this.keyboard.notify_keyval(now + 1, key, Clutter.KeyState.RELEASED);
    }

    Drag(x, y, toX, toY) {
        const now = GLib.get_monotonic_time();
        this.pointer.notify_absolute_motion(now, x, y);
        GLib.timeout_add(GLib.PRIORITY_DEFAULT, 80, () => {
            this.pointer.notify_button(GLib.get_monotonic_time(), 1, Clutter.ButtonState.PRESSED);
            let step = 0;
            GLib.timeout_add(GLib.PRIORITY_DEFAULT, 45, () => {
                step++;
                this.pointer.notify_absolute_motion(GLib.get_monotonic_time(),
                    x + (toX - x) * step / 6, y + (toY - y) * step / 6);
                if (step < 6)
                    return GLib.SOURCE_CONTINUE;
                this.pointer.notify_button(GLib.get_monotonic_time(), 1, Clutter.ButtonState.RELEASED);
                return GLib.SOURCE_REMOVE;
            });
            return GLib.SOURCE_REMOVE;
        });
    }

    Backdrop(pattern) {
        this.plate.set_style('background-color: #272727;');
        this.plate.destroy_all_children();
        if (pattern) {
            const band = new St.Widget({x: 490, y: 0, width: 420, height: 900,
                style: 'background-color: #7460d4;'});
            const label = new St.Label({x: 520, y: 100, text: 'NORVI GLASS',
                style: 'font-size: 38px; color: white; font-weight: bold;'});
            this.plate.add_child(band);
            this.plate.add_child(label);
        }
    }

    async CaptureAsync([name], invocation) {
        try {
            if (!/^[a-z-]+\.png$/.test(name))
                throw new Error('Invalid capture filename');
            const file = Gio.File.new_for_path(GLib.build_filenamev([this.directory, name]));
            const stream = file.replace(null, false, Gio.FileCreateFlags.NONE, null);
            await new Shell.Screenshot().screenshot(false, stream);
            stream.close(null);
            invocation.return_value(null);
        } catch (error) {
            invocation.return_dbus_error('dev.norvi.OfficeTest.Error', error.message);
        }
    }

    disable() {
        this.exported.unexport();
        this.plate.destroy();
        this.pointer = null;
        this.keyboard = null;
    }
}
