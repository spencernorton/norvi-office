# Journal

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
