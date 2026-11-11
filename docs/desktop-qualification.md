# Direct desktop qualification

The target is a cohesive interface in the actual desktop applications, with
normal document opening and editing. A nested desktop, loading prompt, changed
launcher icon or source test alone does not satisfy that target.

## Current source

The direct launcher uses the existing GNOME session and a separate persistent
suite profile. It launches no development viewer or nested compositor. The
installer creates all seven desktop and application-menu entries, preserves
the original LibreOffice profile, and backs up replaced launchers. Only exact,
unchanged, manifest-owned preview shortcuts are retired. Preview runtimes and
documents remain available, including unsaved work in an open process.

New runtime service names are derived from the profile. Before document commands
run, the connected UNO service must report that same profile. Reopening a running
suite must also restore its owned helper services rather than starting duplicate
Office processes or leaving native controls disconnected.

| Application | Interface coverage in source | Current candidate on the real desktop |
| --- | --- | --- |
| Calc | Custom grouped ribbon and shared Home command artwork | Pending |
| Writer | Shared Home command artwork; native Writer layout | Pending |
| Impress | Shared native header; upstream module controls/artwork | Pending |
| Draw | Shared native header; upstream module controls/artwork | Pending |
| Base | Shared native header; upstream module controls/artwork | Pending |
| Math | Shared native header; upstream module controls/artwork | Pending |
| Office start center | Direct suite launcher and desktop entry | Pending |

Unmatched command icons still come from the official Sifr theme. All-tabs icon
coverage and complete module-specific design parity remain outstanding.
Optional document tools and data-model components remain separately scoped
experiments; including them in source does not establish their desktop readiness.

## Ribbon frame-ordering blocker

The native draw hook reports a new boundary before committing the application's
new Wayland buffer. Updating the compositor mask before acknowledging that report
can apply the larger boundary to the preceding buffer. Document pixels can then
fall inside the transparency mask for a compositor frame.

Until a mask can be associated with its committed buffer, the direct-host source
restricts translucency to the measured native titlebar and leaves the ribbon
opaque. This is a partial visual fallback. It must not be described as seamless
ribbon glass or a fix for the complete tab-transition behavior.

Earlier state polling and static backdrop comparisons did not prove frame-level
opacity at a changing ribbon edge. The render qualifier now verifies actual
named notebook-tab selections and samples the static document region starting
at the measured boundary. It still cannot establish atomic buffer association.
Its full-ribbon acceptance remains unsatisfied by the titlebar-only fallback.

## Evidence required before rollout

After the desktop maintenance hold is cleared:

1. Build and qualify the exact committed candidate through native CI. Retain the
   candidate digest and distinguish source checks from installed runtime checks.
2. Recheck the actual desktop session and enabled extension after login. Preserve
   all open work; do not terminate user applications to activate new code.
3. Exercise normal desktop entries and real file associations for every module.
   Verify direct host processes, persistent settings, correct-window actions,
   helper recovery and installation rollback.
4. Resolve buffer association, then capture changing ribbon boundaries at frame
   resolution with document pixels immediately beside the boundary. Confirm
   actual tab changes, accurate color controls, menus and keyboard access.
5. Complete light, dark, high contrast, reduced motion, normal and fractional
   scaling, multiple monitors/hotplug, resize/maximize and effect-conflict checks.
6. Exercise editing, Undo/Redo, formats, encryption, autosave and upgrade/removal
   using owned fictional documents. Publish through the existing signed archive
   pipeline only after its release gates pass.

The current source work does not install or activate a new host build, publish an
APT candidate, or qualify a stable full-glass release.
