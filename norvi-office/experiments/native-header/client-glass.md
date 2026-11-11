# Disabled client-buffer glass research

The native adapter is disabled in source. `NORVI_OFFICE_CLIENT_GLASS=1` cannot
enable it. This is a rejected experimental design and a separately testable
pixel primitive, not an available release feature.

Review found two blockers. LibreOffice GTK signalDraw copies its cached VCL
surface; full GTK invalidation does not prove that post-draw ATK geometry
belongs to that image. A newer boundary with old cached pixels can still make
document pixels translucent. Also, rejecting a reused composed image does not
remove its alpha. A regression reproduces this with a shrinking ribbon.
Opaque-source checks and acknowledgments alone solve neither problem. A
public paint-to-geometry association and proven opaque rebuild are required.

The attempted adapter selects RGBA before realization and expands damage to
the complete client area on frames GTK already requested. Its pixel primitive
accepts only a complete opaque ARGB32 image, complete integer clip and integer
1× coordinates. All conditions are checked before writing. Document bytes
below the supplied edge, bright foreground and saturated indicators remain
unchanged. That edge is untrusted until its paint association is established.
Rejection prevents repeated multiplication but does not guarantee cleanup.

Native Shell mode never attaches the ribbon shader for current or older
clients. The unused ReportClientGlass method enrolls backdrop blur inside the
upper half of a frame; it does not identify a committed buffer. Native clients
remain opaque. The isolated compositor prototype retains its separate shader.

Diagnostic receipts record rejection reasons, applied frames, alpha bounds,
changed-pixel counts and composition timing. Acknowledgment or a visible
backdrop is not evidence that alpha was applied.

Standalone Cairo tests cover document bytes for supplied changing edges,
reused images, repeated composition, colored indicators, partial clips,
non-image/RGB targets, transforms, offsets and scale rejection. They explicitly
reproduce the rejection-cleanup defect. Native visual acceptance, engine paint
association, appearance transitions and performance are not established by
these tests or by state polling.
