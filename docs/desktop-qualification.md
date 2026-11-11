# Direct desktop qualification

The target is a cohesive interface in the actual desktop applications, with
normal document opening and editing. A nested desktop, loading prompt, changed
launcher icon or source test alone does not satisfy that target.

## Current source

The direct launcher uses the existing GNOME session and a separate persistent
suite profile. It launches no development viewer or nested compositor. The
installer creates all seven application-menu entries and optional desktop copies, preserves
the original LibreOffice profile, and backs up replaced launchers. Only exact,
unchanged, manifest-owned preview shortcuts are retired. Preview runtimes and
documents remain available, including unsaved work in an open process.

New runtime service names are derived from the profile. Before document commands
run, the connected UNO service must report that same profile. Reopening a running
suite must also restore its owned helper services rather than starting duplicate
Office processes or leaving native controls disconnected.
Interactive launch arguments preserve normal crash recovery. LibreOffice's
[`--norestore` option](https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html)
disables restart and file recovery after a crash, so it is restricted to
headless initialization and disposable qualification processes.

| Application | Interface coverage in source | Current candidate on the real desktop |
| --- | --- | --- |
| Calc | Custom grouped ribbon; audited Home/Insert/Formulas artwork | Pending |
| Writer | Audited Home/Insert artwork; native Writer layout | Pending |
| Impress | Audited Home/Insert artwork; native Impress layout | Pending |
| Draw | Shared native header; upstream module controls/artwork | Pending |
| Base | Shared native header; upstream module controls/artwork | Pending |
| Math | Shared native header; upstream module controls/artwork | Pending |
| Office start center | Direct suite launcher and desktop entry | Pending |

The [artwork receipt](command-artwork.md) records exact source command coverage.
Unmatched command icons still come from the official Sifr theme. All-tabs icon
coverage and complete module-specific design parity remain outstanding.
Optional document tools and data-model components remain separately scoped
experiments; including them in source does not establish their desktop readiness.

## Ribbon frame-ordering blocker

The native draw hook reports a new boundary before committing the application's
new Wayland buffer. Updating the compositor mask before acknowledging that report
can apply the larger boundary to the preceding buffer. Document pixels can then
fall inside the transparency mask for a compositor frame.

The direct-host source now attaches no native compositor alpha mask and keeps
experimental client alpha disabled, including when its old environment opt-in
is present. Application pixels remain opaque. Neither path may be described as
seamless ribbon glass or a fix for the complete tab-transition behavior.

The client composition experiment exposed a second timing boundary: the exact
LibreOffice GTK backend can copy a cached VCL surface during GTK drawing. A full
GTK invalidation does not establish that current accessibility geometry belongs
to those cached pixels. Rejecting a reused alpha buffer also does not restore
its preceding pixels. The standalone Cairo regression records that failure;
[the investigation](../norvi-office/experiments/native-header/client-glass.md)
separates pure pixel behavior from the unproven application paint association.

Earlier state polling and static backdrop comparisons did not prove frame-level
opacity at a changing ribbon edge. The render qualifier now verifies actual
named notebook-tab selections and samples the static document region starting
at the measured boundary. It still cannot establish atomic buffer association.
Its full-ribbon acceptance remains unsatisfied by the opaque fallback.

## Evidence required before rollout

For the next candidate's installed qualification:

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

## Native Mac design trial

The separate Mac preparation path reuses the matching official Calc ribbon
input and shared icon artwork in a fresh profile, with native Aqua controls and
normal document recovery. Its source and generated launchers do not modify the
official application. GNOME compositor glass is unavailable on macOS.

Manual evaluation has opened Calc, Writer and Impress as actual Mac windows.
The grouped Calc Home and Formulas controls, shared command artwork, editable
fictional documents and native Calc/Writer Undo/Redo were exercised. The trial
uses its own profile; the normal profile and signed official application are
preserved. The original running trial used manually selected Tabbed mode. A
second, fresh light-profile Calc launch then opened the grouped Home ribbon and
custom Formulas tab automatically, without that manual change. That check
establishes Calc's initial mode and tab presence; it does not establish automatic
mode selection for the other modules or selection of the new Formulas tab in
that fresh session. The observations do not qualify full design parity, Linux
glass or a signed archive release. Existing review profiles retain their earlier
artwork until closed and deliberately replaced; newer source coverage does not
describe the pixels already running in those windows.
