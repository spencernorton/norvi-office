# Changelog

## 1.3.0 — An icon for each application

- Writer, Calc, Impress, Draw and Math each have their own launcher icon, in one
  flat family of overlapping translucent shapes: a blue page, a green grid, an
  orange slide with a pie chart, golden shapes and a violet radical. Base and the
  start center keep the Office icon.
- Both the direct desktop integration and the packaged startup integration use
  them, in the application menu, on the desktop and in the dock. A module
  without its own icon falls back to the Office icon.
- Every icon's generator, prompt and checksums are recorded beside it, and the
  startup integration refuses an icon that no longer matches its record.

## 1.2.0 — Grouped Home tabs in Writer, Impress and Draw

- Writer, Impress and Draw open with the Home tab grouped like Calc's: a large
  Paste with icon-only Cut, Copy and Clone, rules between groups, and Find &
  Select at the right. Each fits a 1440 px window without the overflow chevron.
  Impress gains a New Slide button. Commands that left Home stay on their own
  tabs and in the menus: Writer's Insert group, text shadow and character
  spacing, text direction, vertical text, and the slide show buttons (the small
  button above Find & Select still starts the show).
- Each layout is built from the pinned official one. A profile that has its own
  ribbon for a module keeps it, and a module whose official layout is not the
  pinned one keeps LibreOffice's own ribbon.
- Writer's style gallery shows a style name on two lines in full.
- A command that only reports a state no longer shows an empty check box in
  menus, and side panel title bars keep their height.
- The header's line icons and window buttons are drawn at the monitor's scale,
  so they stay sharp at scale 2.
- Calc's Home tab keeps only its own rules after a narrow window is widened
  again, and no longer carries an empty indent group.
- The rules between groups are one height in every Home tab, Calc's first group
  is as wide as the other applications', and Calc's Formulas tab is centred in
  the card. The small buttons above Find & Select start at the group's left
  edge in Writer, Impress and Draw, as they do in Calc.
- Draw's fill colour sits in a field like the fill type beside it.
- A Base window no longer freezes the suite. The header asked Base which of its
  buttons apply three times a second from a second thread, which Base's
  controller cannot take: memory was corrupted and every open window stopped.
  The header now asks on LibreOffice's own main thread, in every application.
- Command artwork that changed since a profile's first start now shows.
  LibreOffice keeps each icon it has drawn in the profile and went on showing
  the old drawing; the launcher now clears those drawings whenever it replaces
  the icon package. Each profile is refreshed once on its next start.
- The header's helper process leaves when LibreOffice closes, instead of
  staying until the next start.
  When LibreOffice restarts itself in place ("Restart Now" after an option
  change), the helper waits for it, so the header's buttons work again as soon
  as it is back.
- The Zoom & Pan command in Draw and Impress uses the suite's line artwork,
  as on the small button above Draw's Find & Select.
- Opening Base first on a new profile no longer ends in a false "Office could
  not start" message.

## 1.1.0 — One look across the suite

- A suite stylesheet carries the approved Calc design study to every module on
  the dark desktop: header, tab row, ribbon card, fields, menus, dialogs, lists,
  side panels, scrollbars and the Start Center. It is loaded for the suite's own
  launch only; no theme, system file or LibreOffice file changes.
- Thin line icons for the header's menu, settings and window buttons, and a
  hairline under the title row.
- Calc's Home ribbon gains the study's group rules and padding. Impress and
  Draw open without the duplicate Drawing bar and quick-access bar, and Draw
  without the classic menu bar; every command stays in the header menu.
- Page, slide and Start Center wells share one colour. Classic toolbars in
  Base and Math use the ribbon's small icons. All of these are defaults that a
  user's own choice overrides.
- Existing profiles receive the current Calc ribbon on the next closed start,
  only while the installed ribbon is one this runtime wrote, with a backup.
- The package now depends on `fonts-inter`.
- A private visual lab (`scripts/visual_lab.sh`) captures every module, every
  ribbon tab, menus, a dialog, a save prompt and a narrow window in a headless
  session.

## 1.0.0 — Initial release candidate

- Approved Office icon and line-only startup presentation.
- User shortcut integration with shared APT runtime, restore and removal fallback.
- Configuration preset, optional document-tools extension and experimental
  native glass qualification sources.
- Reproducible Debian candidate, installed Writer/Calc acceptance and immutable
  release artifacts for signed candidate import.
