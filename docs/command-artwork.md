# Shared command artwork coverage

This is a source audit of the official 26.2.3.2 arm64 Mac resources, with the
existing Norvi Calc transformation applied in memory. It records command icon
lookup coverage, not installed or visually accepted application coverage.

| Module | Home | Insert | Custom Formulas | Shortcut strip |
| --- | --- | --- | --- | --- |
| Calc | 31 / 31 | 31 / 31 | 7 / 7 | 6 / 6 |
| Writer | 40 / 40 | 33 / 33 | — | 6 / 6 |
| Impress | 45 / 45 | 34 / 34 | — | 6 / 6 |

Counts are distinct command keys within each group. The audit traverses native
button objects with `.uno:` actions in Home and Insert, excluding descendants
of an explicit `visible=False` object. It accepts both upstream `action_name`
and `action-name` property spellings. Context-dependent buttons declared visible
in the source are included even if the runtime later hides them. Native font,
font-size and number-format fields are excluded; their controllers supply the
actual UI. The shortcut strip is included where retained by the native profile.

[The machine-readable receipt](../tests/fixtures/notebookbar-artwork.json)
records the official resource paths, SHA-256 hashes and exact command sets.
The source regression builds both light and dark theme overlays and resolves
every recorded command at 16, 24 and 32 pixels. It also checks native alias
replacement, untouched fallback aliases, field artwork and theme license
retention. No official icon ZIP is vendored.

The theme now contains 141 command keys, including semantic aliases. Seventy
additional keys fill the audited gaps: text and shape tools; objects, media and
fields; slide creation and playback; Writer navigation and text controls; and
shared Open, Save, Undo, Redo and Print commands. The existing 24-unit drawing
grid, stroke weight and light/dark palette are retained. Native command bindings
remain unchanged. Line/fill glyphs leave the bottom swatch band clear for the
native selected-color indicator; the artwork does not supply a selected color.
Calc's direct and registry Conditional Formatting labels now use the same
single-line text. Calc-only Cell Styles vocabulary remains scoped to Calc.

Remaining work includes installed icon-resolution and selected-color checks on
each target platform, tab/context transitions and small-size visual review.
Other tabs, menus, sidebars, dialogs and the Draw, Base and Math modules have
not received a complete audit. Shared artwork may improve those surfaces, but
these counts do not establish full-suite parity or a new module-specific layout.
