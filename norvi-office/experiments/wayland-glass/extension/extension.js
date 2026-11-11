import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';
import St from 'gi://St';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const WINDOW_ID = /^(?:org\.libreoffice\.LibreOffice\.|libreoffice-)(writer|calc|impress|draw|base|math)$/i;
const API = `<node><interface name="dev.norvi.OfficeGeometry">
  <method name="Report"><arg type="s" direction="in"/></method>
  <method name="PrepareChrome"><arg type="i" direction="in"/></method>
  <method name="State"><arg type="s" direction="out"/></method>
</interface></node>`;
const TRANSITION_HOLD = 350000; // Wait for a new observation after the input settles.
const MAX_AGE = 600000; // microseconds; missing/slow accessibility fails opaque.

function moduleFor(window) {
    const name = WINDOW_ID.exec(window.get_wm_class() ?? '')?.[1]?.toLowerCase();
    return name ?? null;
}

function uniform(effect, name, number) {
    const value = new GObject.Value();
    value.init(GObject.TYPE_FLOAT);
    value.set_float(number);
    effect.set_uniform_value(name, value);
}

const RibbonMask = GObject.registerClass(
class RibbonMask extends Clutter.ShaderEffect {
    constructor() {
        super();
        this.set_shader_source(`
            uniform sampler2D tex;
            uniform float top;
            uniform float bottom;
            uniform float join_end;
            uniform float join_start;
            uniform float solid_join;
            uniform float panel_top;
            uniform float panel_left;
            uniform float panel_right;
            uniform float buffer_width;
            uniform float buffer_height;
            void main() {
                vec4 source = texture2D(tex, cogl_tex_coord_in[0].st);
                float y = cogl_tex_coord_in[0].y;
                if (y >= join_start && y < join_end) {
                    if (solid_join > 0.5)
                        source.a = 1.0;
                    float ink = smoothstep(0.20, 0.62, dot(source.rgb, vec3(0.2126, 0.7152, 0.0722)));
                    source.rgb = mix(vec3(44.0 / 255.0) * source.a, source.rgb, ink);
                }
                float luminance = dot(source.rgb, vec3(0.2126, 0.7152, 0.0722));
                float foreground = smoothstep(0.30, 0.68, luminance);
                float blend = (y >= top && y < bottom) ? mix(0.72, 1.0, foreground) : 1.0;
                if (panel_top > 0.0 && y >= panel_top && y < bottom) {
                    vec2 pixel = cogl_tex_coord_in[0].st * vec2(buffer_width, buffer_height);
                    vec2 origin = vec2(panel_left, panel_top * buffer_height);
                    vec2 size = vec2(panel_right - panel_left, (bottom - panel_top) * buffer_height - 4.0);
                    vec2 corner = abs(pixel - origin - size * 0.5) - size * 0.5 + vec2(10.0);
                    float distance = length(max(corner, vec2(0.0))) +
                        min(max(corner.x, corner.y), 0.0) - 10.0;
                    float fill = 1.0 - smoothstep(-1.0, 0.0, distance);
                    float rim = (1.0 - smoothstep(0.0, 1.0, abs(distance + 0.7)));
                    // The VCL surface also contains its native control ink.
                    float background = 1.0 - smoothstep(0.19, 0.32, luminance);
                    vec3 panel_ink = vec3(28.0, 27.0, 37.0) / 255.0;
                    source.rgb = mix(source.rgb, panel_ink * source.a, 0.85 * fill * background);
                    source.rgb += 0.075 * rim * background * source.a;
                }
                cogl_color_out = source * blend;
            }
        `);
    }
});

// Tell Mutter this actor needs the scene behind its nominal opaque region.
const RevealBackdrop = GObject.registerClass(class RevealBackdrop extends Clutter.Effect {});

export default class NorviOffice extends Extension {
    enable() {
        if (!GLib.getenv('NORVI_OFFICE_TEST_DIR'))
            throw new Error('Launch the isolated Norvi Office preview harness.');
        this.entries = new Map();
        this.geometry = [];
        this.reportAt = 0;
        this.interfaceSettings = new Gio.Settings({schema_id: 'org.gnome.desktop.interface'});
        this.contrastSettings = new Gio.Settings({schema_id: 'org.gnome.desktop.a11y.interface'});
        this.interfaceSettings.connectObject('changed', () => this.syncAll(), this);
        this.contrastSettings.connectObject('changed', () => this.syncAll(), this);
        this.exported = Gio.DBusExportedObject.wrapJSObject(API, this);
        this.exported.export(Gio.DBus.session, '/dev/norvi/OfficeGeometry');
        this.expiry = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 100, () => {
            this.syncAll();
            return GLib.SOURCE_CONTINUE;
        });
        this.scanId = 0;
        global.window_manager.connectObject('map', (_manager, actor) => this.attach(actor), this);
        // Some documents acquire their application ID after their first map.
        global.display.connectObject('restacked', () => this.scan(),
            'window-created', () => this.scheduleScan(),
            'notify::focus-window', () => this.scheduleScan(), this);
        this.scan();
    }

    Report(text) {
        this.geometry = [];
        this.reportAt = 0;
        if (text.length <= 32768) {
            try {
                const report = JSON.parse(text);
                const age = GLib.get_monotonic_time() - report.at;
                if (Number.isSafeInteger(report.at) && age >= 0 && age < MAX_AGE &&
                    Array.isArray(report.windows) && report.windows.length <= 32) {
                    this.geometry = report.windows.filter(item =>
                        Number.isInteger(item.pid) && typeof item.title === 'string' &&
                        Array.isArray(item.size) && item.size.length === 2 &&
                        item.size.every(n => Number.isInteger(n) && n > 0 && n <= 16384) &&
                        Number.isInteger(item.edge) && Number.isInteger(item.join) &&
                        item.join > 0 && item.edge > item.join && item.edge < item.size[1] / 2 &&
                        (item.join_start === undefined || (Number.isInteger(item.join_start) &&
                            item.join_start >= 0 && item.join_start < item.join)));
                    this.reportAt = report.at;
                }
            } catch (_error) {
                // Malformed or stale reports must not retain a translucent band.
            }
        }
        this.syncAll();
    }

    PrepareChromeAsync([y], invocation) {
        // Authenticate the process through the private bus. The caller cannot
        // request a pause in another process by supplying a PID or window title.
        let pid;
        try {
            [pid] = Gio.DBus.session.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus',
                'org.freedesktop.DBus', 'GetConnectionUnixProcessID',
                new GLib.Variant('(s)', [invocation.get_sender()]), new GLib.VariantType('(u)'),
                Gio.DBusCallFlags.NONE, 100, null).deepUnpack();
        } catch (_error) {
            invocation.return_dbus_error('dev.norvi.OfficeGeometry.Error', 'Cannot identify input owner');
            return;
        }

        const now = GLib.get_monotonic_time();
        const focused = global.display.focus_window;
        for (const entry of this.entries.values()) {
            if (entry.window.get_pid() !== pid)
                continue;
            if (y !== -1 && !(y >= entry.join && y < entry.inputEdge))
                continue;
            if (focused?.get_pid() === pid && focused.get_window_type() === Meta.WindowType.NORMAL &&
                entry.window !== focused)
                continue;
            entry.blockedUntil = now + TRANSITION_HOLD;
            entry.transitionCount++;
            entry.sync();
        }
        invocation.return_value(null);
    }

    State() {
        const box = rect => [rect.x, rect.y, rect.width, rect.height];
        return JSON.stringify([...this.entries.values()].map(entry => ({
            app: moduleFor(entry.window), enabled: entry.mask.enabled,
            edge: entry.edge, reason: entry.reason, transitionCount: entry.transitionCount,
            frame: box(entry.window.get_frame_rect()), buffer: box(entry.window.get_buffer_rect()),
        })));
    }

    syncAll() {
        for (const entry of this.entries.values())
            entry.sync();
    }

    scheduleScan() {
        if (this.scanId)
            return;
        this.scanId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 800, () => {
            this.scanId = 0;
            this.scan();
            return GLib.SOURCE_REMOVE;
        });
    }

    scan() {
        for (const actor of global.get_window_actors())
            this.attach(actor);
    }

    attach(actor) {
        const window = actor.meta_window;
        if (!window || this.entries.has(actor))
            return;

        const module = moduleFor(window);
        const surface = actor.get_first_child();
        if (!module || !surface || window.get_window_type() !== Meta.WindowType.NORMAL)
            return;

        const blur = new St.Widget({reactive: false, name: 'norvi-office-backdrop'});
        const effect = new Shell.BlurEffect({
            mode: Shell.BlurMode.BACKGROUND, radius: 36, brightness: 0.85,
        });
        blur.add_effect(effect);
        const mask = new RibbonMask();
        mask.enabled = false;
        mask.set_uniform_value('tex', 0);
        const guard = new RevealBackdrop();
        actor.add_effect(guard);
        actor.insert_child_below(blur, surface);
        surface.add_effect_with_name('norvi-office-mask', mask);
        const entry = {blur, mask, surface, guard, window, edge: null, reason: 'geometry',
            blockedUntil: 0, transitionCount: 0, inputEdge: 0, join: 0};
        this.entries.set(actor, entry);
        const sync = () => {
            const buffer = window.get_buffer_rect();
            const rect = window.get_frame_rect();
            const matches = this.geometry.filter(item => item.pid === window.get_pid() &&
                item.title === window.get_title() &&
                item.size[0] === buffer.width && item.size[1] === buffer.height);
            const fresh = GLib.get_monotonic_time() - this.reportAt < MAX_AGE;
            const geometry = fresh && matches.length === 1 ? matches[0] : null;
            const dark = this.interfaceSettings.get_string('color-scheme') === 'prefer-dark' &&
                !this.contrastSettings.get_boolean('high-contrast') &&
                !/highcontrast/i.test(this.interfaceSettings.get_string('gtk-theme'));
            const supported = actor.visible && !window.is_fullscreen() &&
                global.display.get_monitor_scale(window.get_monitor()) === 1;
            const top = rect.y - buffer.y;
            const valid = geometry && geometry.edge > top &&
                geometry.join > top && geometry.edge < top + rect.height;
            const settling = this.reportAt <= entry.blockedUntil && entry.blockedUntil > 0;
            if (valid && !settling) {
                entry.inputEdge = geometry.edge;
                entry.join = geometry.join;
            }
            const visible = supported && dark && valid && !settling;
            entry.reason = !supported ? 'window-or-scale' : !dark ? 'appearance' :
                settling ? 'transition' : !valid ? 'geometry' : 'active';
            entry.edge = visible ? geometry.edge : null;
            mask.enabled = Boolean(visible);
            blur.visible = Boolean(visible);
            if (!visible)
                return;
            blur.set_position(rect.x - buffer.x, rect.y - buffer.y);
            blur.set_size(rect.width, geometry.edge - top);
            uniform(mask, 'top', top / buffer.height);
            uniform(mask, 'bottom', geometry.edge / buffer.height);
            uniform(mask, 'join_end', geometry.join / buffer.height);
            uniform(mask, 'join_start', Math.max(top, geometry.join_start ?? top) / buffer.height);
            uniform(mask, 'solid_join', geometry.join_start === undefined ? 0 : 1);
            // Calc's pinned Tabbed preview has a fixed 37px tab band at dark 1×.
            // Require enough measured ribbon height and keep every painted pixel above edge.
            const panelTop = geometry.join + 36;
            const panel = module === 'calc' && GLib.getenv('NORVI_OFFICE_CALC_RIBBON') === '1' &&
                geometry.join_start !== undefined && geometry.edge - panelTop >= 55;
            uniform(mask, 'panel_top', panel ? panelTop / buffer.height : 0);
            if (panel) {
                uniform(mask, 'panel_left', rect.x - buffer.x + 8);
                uniform(mask, 'panel_right', rect.x - buffer.x + rect.width - 8);
                uniform(mask, 'buffer_width', buffer.width);
                uniform(mask, 'buffer_height', buffer.height);
            }
        };
        entry.sync = sync;
        actor.connectObject('notify::allocation', sync, 'notify::visible', sync,
            'destroy', () => this.detach(actor, true), this);
        window.connectObject('position-changed', sync, 'size-changed', sync, this);
        sync();
        console.log(`[Norvi Office] attached ${module} header`);
    }

    detach(actor, destroyed = false) {
        const entry = this.entries.get(actor);
        if (!entry)
            return;
        this.entries.delete(actor);
        actor.meta_window?.disconnectObject(this);
        if (!destroyed) {
            actor.disconnectObject(this);
            entry.surface.remove_effect(entry.mask);
            actor.remove_effect(entry.guard);
        }
        entry.blur.destroy();
    }

    disable() {
        this.exported.unexport();
        GLib.Source.remove(this.expiry);
        this.interfaceSettings.disconnectObject(this);
        this.contrastSettings.disconnectObject(this);
        global.window_manager.disconnectObject(this);
        global.display.disconnectObject(this);
        if (this.scanId) {
            GLib.Source.remove(this.scanId);
            this.scanId = 0;
        }
        for (const actor of this.entries.keys())
            this.detach(actor);
        this.entries = null;
    }
}
