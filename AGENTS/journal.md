# Journal

## 2026-11-12 — Use GObject cleanup for retained action interfaces

- Exact Linux compilation exposed that GActionGroup has no automatic cleanup
  typedef on the qualified GLib. Retain it through a GObject owner and a typed
  interface alias. Native regression execution remains pending that rebuild.

## 2026-11-12 — Clear timer identity during nested teardown

- A destroy handler registered earlier can pump the main context before the
  header's own handler runs. Its timer may then return REMOVE while the window
  is already in destruction. Source teardown now clears the matching recorded
  timer ID before releasing callback ownership, preventing a later stale-ID
  removal. Dispatch retains the header even when its own source is removed.
- Added a sixth mandatory-hit GTK case that pumps an actual ready timer from
  the earlier destroy handler. Native execution remains a separate check.

## 2026-11-12 — Guard native callbacks against reentrant document closure

- ATK geometry providers, menu models and GTK notifications can close their
  owning document during a header callback. Keep callback-scoped references to
  the header, window, controls and models, then check logical liveness after
  provider calls. Stop reporting, refreshing, styling and updating controls
  as soon as destruction invalidates that snapshot.
- Timer sources and signal closures now own their header data. Destruction
  clears pointers and source IDs before cancellation/removal; geometry reports
  copy titles before bus calls. Opaque launches write geometry receipts only
  initially or when values change, avoiding unchanged periodic disk writes.
- Added mandatory-hit GTK regressions for destruction during ATK reporting,
  actual timer refresh, menu installation, asynchronous description updates and
  focus handoff. The build runs them on Xvfb with fatal criticals. Source/Python
  checks pass locally; Linux compilation and those native regressions still
  require execution on the qualified toolchain before installed acceptance.

## 2026-11-11 — Refresh owned presentation packages in closed profiles

- Existing ready profiles now compare a reproducible revision of the owned
  artwork generator, base preset and official icon input. ZIP timestamps and
  entry order do not change that revision. New records also retain the owned
  package digest, while known legacy records migrate using the extension ID.
- Closed profiles receive only the updated presentation package through a
  bounded force install. The original package remains in a hash-named backup;
  a failed install restores it and leaves the old ready record eligible for
  retry. Missing, foreign, symlinked or unexpectedly edited packages are
  preserved with an explicit error. Module layouts, settings and documents
  are retained without rerunning profile preparation or UNO configuration.
- Exact owned-process profile arguments and verified running records defer
  updates while Office is live. Unreadable owned-process arguments also defer
  conservatively. Thirty-three Python tests pass with three Linux-only skips;
  focused lint, compilation and diff checks pass. Installed upgrade acceptance
  remains separate from these source and package-fixture checks.

## 2026-11-11 — Keep cached compositor code out of opaque enrollment

- The candidate's native header and ribbon do not require compositor effects.
  Enrollment now leaves the Office extension disabled, so replacing files cannot
  reactivate an older cached shader against new clients. No sign-out, Shell
  restart or open-document closure is needed for this opaque application UI.
- Eight integration regressions pass, including the inactive-effects invariant
  and complete restoration after a settings-write failure. The preceding exact
  source built on Linux and passed twenty-nine Python tests, twenty-four GJS
  cases and native checks; its isolated runtime exercised all six modules,
  Calc editing/Undo/Redo/Save, Writer Undo and Base embedded SQL. This newer
  installer head still requires its own native CI and installed verification.

## 2026-11-11 — Verify fresh Mac Calc mode and reconcile candidate coverage

- A fresh light-profile native Calc launch opened grouped Home and exposed the
  custom Formulas tab without manually changing interface mode. Evidence covers
  initial mode and tab presence; selecting that tab in this check and automatic
  modes in other modules remain unverified. The original three review windows
  and the light comparison remain available, with the normal profile unchanged.
- Reconciled qualification documentation with the 141-key source artwork audit
  and disabled native alpha. Existing review profiles still use their preceding
  artwork. Pure Cairo composition cannot establish the VCL paint association;
  the exact Linux source build exposed and corrected the floor link dependency.
- Combined Python validation passes twenty-six cases with three Linux-only
  skips; lint, byte compilation and diff checks pass. Native package and actual
  installed qualification remain separate requirements for this new head.

## 2026-11-11 — Disable client glass after cached-paint review

- The GTK draw signal copies a cached VCL surface. Full GTK invalidation alone
  does not bind post-draw ATK geometry to that image, so the attempted client
  composition still lacks the required paint/layout association.
- Added a regression reproducing the second blocker: rejecting a reused glass
  buffer after a shrinking boundary leaves its old alpha intact. Rejection is
  not an opaque cleanup mechanism. The adapter is now disabled in source, and
  no environment flag can enable native ribbon alpha. Native Shell mode still
  never attaches a geometry-driven opacity shader.
- Retain pure Cairo diagnostics as research, with these limits stated. Remove
  the unnecessary libm dependency in the coordinate check and require exact
  dimensions when acknowledging backdrop readiness. No native glass runtime
  acceptance or completed UI-overhaul claim follows from these source tests.

## 2026-11-11 — Add an opt-in client-buffer glass candidate

- Native Shell mode no longer attaches the geometry-driven alpha shader.
  The new protocol enrolls backdrop blur only; reports cannot change client
  alpha or make document pixels translucent before a matching buffer commit.
- The experimental GTK path selects RGBA before realization and requests a
  complete repaint on existing frames. It modifies only a fully opaque ARGB32
  image target with complete clip and supported integer 1× coordinates. The
  current painted frame's document pixels remain byte-identical, while bright
  and saturated control ink stays opaque. Ordinary launches retain opaque UI.
- Added receipts for actual alpha application, rejection reasons, bounds and
  composition time. Pure Cairo pixel tests, twenty-four JavaScript policy
  cases and the existing Python suite pass locally. GTK compilation, real CSD
  target support, appearance transitions and full-repaint performance still
  require exact Linux candidate qualification; no installed acceptance claimed.

## 2026-11-11 — Cover shared Home, Insert and shortcut command artwork

- Audited actual official Calc, Writer and Impress notebookbar command keys,
  including both upstream action property spellings and dotted shape keys.
  Added seventy shared keys on the existing 24-unit grid, bringing the theme to
  141 keys. Native font/format fields and all command bindings remain intact.
- The source receipt covers Home/Insert, custom Calc Formulas and retained
  shortcut strips. Light/dark package regressions check every recorded key at
  three sizes, real theme aliases, untouched fallback artwork and licenses.
  Line/fill artwork reserves the native live-color swatch band. Calc's explicit
  Conditional Formatting label now matches its single-line registry label.
- Twenty-four Python tests pass, with three Linux-only skips; focused lint,
  compilation and diff checks pass. Rendered artwork was inspected headlessly.
  No installed profile, application bundle or desktop was changed. Installed
  visual acceptance, remaining tabs and complete six-module coverage are pending.

## 2026-11-11 — Preserve removed launchers during desktop restoration

- Removing the native integration now accepts missing owned entries without
  recreating their preceding backups. Edited files and replacement symlinks
  still stop restoration before any settings or files change.
- Added an application-menu-only enrollment option, so a replacement candidate
  can respect a desktop from which the preceding shortcuts were removed.
- Eight desktop integration regressions pass, including a deleted entry with
  an original backup, dangling-symlink protection and enrollment without new
  desktop copies. No installed runtime or desktop settings changed here.

## 2026-11-11 — Record native Mac evaluation and publish the combined trial source

- The Mac UI owner opened actual native Calc, Writer and Impress windows using
  the isolated design-trial profile. Calc's grouped Home and Formulas controls,
  shared command artwork, native editing and Calc/Writer Undo/Redo were exercised.
  Fictional spreadsheet formulas, editable prose and a presentation were saved.
- The official arm64 application remains signed and unmodified, and the normal
  profile hash is unchanged. No embedded-Python launch constraint was weakened;
  trial configuration used the application's own native menus.
- Those running windows were set to Tabbed mode through the native dialog.
  The new preset's automatic first-use mode selections still require a fresh
  profile GUI check; source assertions do not establish that acceptance.
- Combined local checks pass: twenty-three Python regressions, three Linux-only
  skips, fourteen JavaScript policy cases, lint, compilation and diff checks.
  Keep the source PR a draft: macOS glass is unavailable, Linux ribbon buffer
  association and complete suite parity remain unfinished, and the existing
  desktop maintenance hold is retained.

## 2026-11-11 — Select notebookbar mode in fresh Mac profiles

- Real Mac review initially opened standard toolbars despite the preset's
  notebookbar implementation fields. The native UI dialog additionally persists
  each Applications/<module>/Active mode; its schema defaults those to Default.
- Add those per-application selections for Calc, Writer, Impress and Draw,
  matching the actual dialog's persisted values. Regressions inspect both dark
  and light packages for all four mode records.
- This is a source correction for future fresh trials. The running review profile
  was inspected read-only and left unchanged; fresh-launch acceptance remains
  distinct from the source/package assertions.

## 2026-11-11 — Prepare native Mac design trials

- Added a pure preparation helper for a matching official Mac bundle, an isolated
  profile, shared artwork and the existing Calc ribbon transformation. It creates
  seven native launch entries with normal recovery/shortcuts and no nested desktop.
- Preparation rejects unknown ribbon inputs, existing trials and application/live
  profile destinations. The generated receipt separates preparation, preset
  installation and visible acceptance. Runtime commands suppress Python bytecode
  writes inside the signed application bundle.
- Dark/light icon variants derive from the corresponding official Sifr resources
  and retain their license/provenance. GNOME glass is explicitly unavailable on
  macOS; no complete-suite or installed-runtime acceptance is claimed here.
- Source-only regressions cover unchanged official inputs, retained trial work,
  launch/profile isolation, recovery, theme licenses and both icon variants.

## 2026-11-11 — Scope render checks to notebookbar tabs

- A separate selected tab group, such as Calc's sheet tabs, must not be confused
  with the ribbon. Locate the unique group containing the named ribbon tabs
  and reject ambiguous groups before exercising transitions.
- Added a regression with independently selected ribbon and sheet groups. The
  native accessibility structure still requires qualification after maintenance.

## 2026-11-11 — Preserve interactive document recovery

- Removed the disposable-preview no-recovery flag from actual application
  commands. Normal crash recovery remains available in the persistent suite
  profile; headless initialization retains its separate controlled arguments.
- The real-document launch regression now rejects recovery suppression. This
  source-only correction changes no running application or installed payload.

## 2026-11-11 — Continue direct application source work during maintenance

- Consolidated the direct-host branch, full suite shortcut migration, service
  recovery and profile isolation. No desktop activity or installation occurs
  while the existing maintenance hold remains in effect.
- Native CI dependency resolution is repaired; the preceding preview branch
  passed genuine source/native/tests checks. That result does not qualify this
  newer combined source or the desktop compositor.
- Tightened render qualification to prove named tab selection changes and sample
  document opacity at the measured boundary. Static comparisons and geometry
  polling still cannot prove per-buffer synchronization.
- Documented current module/artwork coverage and the titlebar-only fallback.
  The complete native UI, six-module desktop checks and archive rollout remain
  unfinished. Preserve this distinction when resuming installed acceptance.
- Local validation: twenty Python regressions pass, three Linux-only tests are
  skipped; fourteen JavaScript policy checks, lint, compilation and diff checks
  pass. Native build and actual desktop validation remain separate gates.

## 2026-11-11 — Bound unqualified desktop transparency

- A synchronous geometry acknowledgment precedes the client buffer commit but
  does not identify that buffer. Growing ribbon masks could therefore expose
  document pixels from the preceding frame.
- Direct-desktop effects now use only the fixed native titlebar band, including
  the accessibility fallback. Dynamic ribbon transparency stays disabled until
  committed-buffer association is qualified; diagnostic state says titlebar-only.
- Fourteen pure geometry-policy checks pass locally, including reordered
  growing/shrinking ribbon measurements and invalid-boundary rejection. Native
  compositor acceptance remains pending; the installed host build is unchanged.

## 2026-11-11 — Recover desktop presentation helpers

- Reused desktop sessions now verify their existing profile service and recover
  missing presentation helpers without closing documents. Recorded helper
  identity includes its session, script and channel rather than a PID alone.
- New profiles also receive distinct header bus names; existing desktop
  sessions retain their original service names until closed normally.
- Thirteen Mac-compatible regressions pass; five Linux integration checks are
  skipped on the development host. Native build and installed acceptance stay
  pending while host maintenance is in progress. No host runtime changed.

## 2026-11-11 — Isolate native CI dependency resolution

- Give the disposable native job explicit DNS resolvers after repeated archive
  lookups failed before source checkout. Official signed package sources and
  the digest-pinned runtime image remain unchanged.
- Retry transient APT transport errors and fail dependency setup if any index
  refresh fails, rather than continuing with an empty package index.
- Source validation passes locally. The exact-head native candidate acceptance
  must pass in Actions before this change can be merged or released.

## 2026-11-11 — Migrate the complete desktop suite

- Added direct desktop entries for all six editors and the suite start center.
- Retire only unchanged, manifest-owned design-preview launchers; preserve
  customized or foreign shortcuts, preview runtimes and every document/profile.
- Native rollback restores the previous preview entries and refuses to replace
  newly created files at their retired paths. Failed installs restore only
  their completed mutations, preserving a concurrent preview-shortcut edit.
- Six installer/routing regressions run on macOS using isolated command fixtures.
  Actual desktop entry validation remains enabled wherever its Linux utility
  is available; no host installation or glass acceptance is claimed.

## 2026-11-11 — Checkpoint before desktop activation

- Actual host Calc/Writer header actions and duplicate-caption routing passed
  on the persistent desktop profile. That installed beta still uses the older
  accessibility geometry bridge; it is not the newer render-sync source.
- Native C geometry measured during draw and acknowledged before buffer commit
  passed an isolated Calc render check with 230 active samples and unchanged
  sampled body pixels. Physical compositor and Writer render acceptance remain
  pending; headless captures are not host-desktop evidence.
- Found a globally named UNO channel shared by independent test profiles.
  Prepared profile-derived channel names, connected-profile ownership checks
  and safe reuse of a running legacy session. These changes require native
  qualification before installation.
- Host activity is checkpointed for planned maintenance. No further host
  deployment, tests or activation until the coordinating task clears it.

## 2026-11-11 — Prepare actual desktop integration

- The user rejected the nested Devkit delivery and reported persistent visual
  faults. Added an explicit direct-host launch path with a separate persistent
  suite profile, real document arguments and one shared command broker.
- Added transactional user shortcut integration, a dedicated compositor UUID,
  backups and restoration. The existing LibreOffice profile is not overwritten.
- GNOME 50's extension reload API reports NOT_SUPPORTED. New compositor code
  needs a fresh login; activation must preserve open work and cannot be claimed
  complete based on nested previews or source checks.
- Native candidate, rollback and actual host acceptance follow before rollout.

## 2026-11-11 — Reduce tab flashes and complete Home artwork

- Replaced the fixed input hold with event-driven chrome measurements. Native
  titlebar glass persists while the ribbon boundary is revalidated; stale
  geometry still expires opaque instead of exposing the work area.
- Shared the disposable icon overlay with Writer and completed the visible
  Home command artwork in both modules, preserving native color indicators,
  font fields, styles and command bindings.
- Seventeen Linux regressions and the Debian candidate build pass. Native
  acceptance on fresh Calc/Writer previews confirms mapped, streaming host
  viewers, working Undo/Redo and menus, and unchanged opaque body pixels.
  Sampled tab recovery is 14–52 ms; the titlebar stays glass in every sample.
- Closed superseded unmodified fictional previews. A modified earlier preview
  remains open with its edits preserved. Source CI passes; remote native CI
  currently cannot resolve the official distribution package hosts, so the
  release remains gated rather than bypassing required checks.

## 2026-11-11 — Verify the outer desktop viewer

- Corrected the previous acceptance gap: an inner compositor capture did not
  prove that its outer desktop window was mapped or receiving video.
- Start a private policy-only WirePlumber instance and use Devkit's sole
  displayed monitor. Readiness now requires the matching host viewer and an
  active video link, independently of the document's inner capture.
- Install trusted, executable desktop icons as well as app-menu entries. The
  removal manifest covers both and safely upgrades older four-file installs.
- Nine Linux regressions and the Debian candidate build pass. Fresh Calc and
  Writer launches have mapped outer windows with active streams; native header
  Undo/Redo, menus and opaque work-area checks pass for both applications.

## 2026-11-11 — Qualify the visible application launchers

- Installed distinct Calc/Writer preview entries and launched both through
  their actual desktop IDs. Normal application profiles remain separate.
- Verified native header controls, actual document Undo/Redo and F10 menus.
  Backdrop changes affected each header while leaving all 535,040 sampled
  work-area pixels unchanged. Real desktop screenshots were reviewed.
- Corrected popup-label registration, compositor startup flags, short runtime
  sockets and the Writer sample's paragraph styling. Sidebar rails and the
  duplicate Writer quick-access toolbar are hidden in the preview.
- Seven Linux regressions pass, including shortcut rollback/user-edit and
  retained-document protection. The scoped source privacy scan has no
  unaccepted findings. This remains an experimental visible workspace rather
  than enabling the native adapter in ordinary Office launches.

## 2026-11-11 — Make the approved visual prototype reachable

- Corrected the gap between the startup-only release and the approved visual
  prototype by adding a separately launched visible Calc/Writer workspace.
- Fixed the ribbon overlay's dependency on a removed vendored icon ZIP. It now
  derives a temporary icon theme from the official installed Sifr package and
  registers that theme in the disposable extension.
- Added regressions for the missing-theme packaging case and isolation from the
  live display, accessibility bus and configuration. Native desktop acceptance
  and screenshot review follow before the preview is presented as ready.

## 2026-11-10 — Initial release pipeline

- Extracted the approved loader, icon, configuration preset and experimental
  GTK/glass and document tools into independent release source.
- Added reproducible Debian packaging, native installed-payload acceptance,
  upstream compatibility reporting and immutable release artifacts.
- Candidate import and explicit stable review preserve the separate update
  paths for the upstream engine and custom UI.
