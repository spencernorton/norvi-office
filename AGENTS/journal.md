# Journal

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
