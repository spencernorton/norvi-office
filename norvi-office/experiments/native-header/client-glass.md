# Experimental client-buffer glass

This path requires `NORVI_OFFICE_CLIENT_GLASS=1` and an authenticated native
desktop launch. It is disabled by default and is not a qualified release.

The GTK module selects an RGBA visual before realization and expands the
window's damage to the full client area at the start of a frame GTK already
requested. After stock rendering, it accepts only a complete, opaque ARGB32
image target, a complete integer clip, and a supported integer 1× transform.
All checks finish before the first pixel write. The current draw's measured
document edge bounds the alpha pass; document bytes are unchanged. White ink,
saturated color indicators, and dark ink near light input fields stay opaque.
An already composed or partially reused buffer is rejected rather than
multiplied again. Changing appearance or losing backdrop capability requests
a normal complete redraw.

Native Shell mode never attaches the ribbon shader, for either current or
older clients. `ReportClientGlass` enrolls a blur backdrop inside the frame's
upper half; it does not acknowledge or identify a committed buffer. A changed
or reordered geometry report cannot alter client alpha. Old clients remain
opaque. The isolated compositor prototype retains its separate shader path.

The geometry receipt records request state, rejection reason, applied frames,
alpha bounds and changed-pixel count, plus total and maximum composition time.
An acknowledgment or visible backdrop is not evidence that alpha was applied.

The standalone Cairo test exercises document bytes at the exact changing edge,
reused images, repeated composition, colored indicators, partial clips,
non-image/RGB targets, transforms, device offsets and scale rejection. Linux
GTK and actual native application rendering still need qualification. In
particular, normal CSD shadows may fail the intentionally strict opaque-source
check. Full-frame repaint and the backdrop's area also need performance
measurement at the intended display sizes. A source test or state poll does
not establish native visual acceptance, mode-change behavior or frame timing.
