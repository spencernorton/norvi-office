# Changelog

## 1.2.0 — Grouped Home tabs in Writer, Impress and Draw

- Writer, Impress and Draw open with the Home tab grouped like Calc's: a large
  Paste with icon-only Cut, Copy and Clone, rules between groups, and Find &
  Select at the right. Each fits a 1440 px window without the overflow chevron.
  Impress gains a New Slide button. Commands that left Home stay on their own
  tabs and in the menus: Writer's Insert group, text shadow and character
  spacing, text direction, vertical text, and the slide show buttons (the small
  button above Find & Select still starts the show).
- Each layout is built from the pinned official one. A profile that has its own
  ribbon for a module keeps it, and an engine update that changes the official
  layout brings LibreOffice's own ribbon back for that module.
- Writer's style gallery shows a style name on two lines in full.
- A command that only reports a state no longer shows an empty check box in
  menus, and side panel title bars keep their height.

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
