# Journal

## 2026-11-25 — Sharp application icons: theme sizes instead of one large file
- Reported: the application icons look blurry on the dock. The art is sharp
  (edges about 1 px wide at 512 px). The cause was scaling: each launcher's
  `Icon=` named the 512 px file, and the shell shrinks a file icon on every
  draw. GdkPixbuf at 64 px measured 10.4 to 18.7 on a mean-gradient sharpness
  score; a Lanczos render of the same master scored 18.3 to 32.8. Themed icons
  (Helios, Penguin Mail) were unaffected because the theme gives an exact size.
- Each icon now has the hicolor sizes 16 to 256 px under
  `startup/assets/apps/hicolor/`, rendered once from the 1024 px master; 512
  is the existing file. `provenance.json` records every size and
  `verify_icons` checks them. The direct integration installs the sizes into
  `$XDG_DATA_HOME/icons/hicolor` as managed files, writes
  `Icon=norvi-office-<app>`, and runs `gtk-update-icon-cache` only when a user
  cache already exists. The package installs them under `/usr/share/icons`,
  and `qualify_package.sh` checks all 66.
- On the real dock the open window had been an idle Office process with no
  windows. The lab's window tracker confirms a Writer window is tracked to
  `libreoffice-writer.desktop` through its `libreoffice-writer` class, so the
  launcher's icon is the one the dock shows.
## 2026-11-25 — Base's section bars follow the accent
- `#monoborder` section bars in Base were a fixed `#8f8aa0`. They now use
  `@accent_band` from the accent palette. The rule, kept in
  `tests/test_accents.py`, is 18% accent over grey 149, then lightened or
  darkened to the original bar's contrast with black (6.31:1), because
  LibreOffice draws those titles black. It reproduces the lavender bar within
  three blue steps; purple keeps the exact original. The test requires at
  least 6:1 for every accent.
- Lab, Base on 26.2.7: orange draws `#a18877`, blue `#818e9f`, the palette
  values exactly; titles stay legible.
## 2026-11-25 — LibreOffice 26.2.7 qualified
- Ubuntu's unattended upgrade moved LibreOffice from 26.2.6 to 26.2.7 at
  06:34 MST. Every launch then fell back to plain LibreOffice: `qualified()`
  reads `compatibility.json`, and `header.c` had its own `libo-version` check
  for 26.2.6 only. Eight lab runs timed out at the first Calc start until
  the cause was found; the lab expects the native header.
- The header's check is now `qualified_engines[]`, and `test_release.py`
  requires it to list exactly the contract's versions.
- Evidence on 26.2.7: the Calc, Writer, Impress and Draw `notebookbar.ui`
  files match the pinned SHA-256s; a six-module lab tour under the orange
  accent shows each module with the header, grouped Home ribbon and accent,
  and zero GTK criticals in `office.log`. With the header gated off (version
  not yet listed), the same engine logged 45 `atk_state_set_contains_state`
  and 15 `g_object_unref` criticals from LibreOffice's own title bar path;
  26.2.6 runs logged none. Not from this code, but note it if a future
  engine is checked without the header.
- Base's section bars are `#8f8aa0` from the design study's neutral palette,
  not an accent, so they stay violet-grey under every accent.
## 2026-11-25 — The live accent change reaches LibreOffice's own painting
- The private visual lab (`LAB_ACCENT=orange scripts/visual_lab.sh
  scripts/lab_accent.py blue`) showed 1.4.0 changing only the header and its
  glow while Calc stayed open; the selection, tab underline and ribbon
  background stayed orange. LibreOffice 26.2 copies those colours and copies
  them again on `style-updated` from its frame's event widget
  (`vcl/unx/gtk3/gtkframe.cxx`, `getMouseEventWidget()`), and a provider
  reload changes no property of that widget, so GTK never emits it.
- Emitting `style-updated` on each toplevel alone was not enough (checked in
  the lab); the header now emits it on every realized widget of every
  toplevel after a reload. An independent review found the first version
  emitted from inside `gtk_container_forall()`, where a handler that destroys
  a parent frees the list the container is walking. The tree is now taken
  first, with references, and destroyed (unrealized) widgets are skipped.
- Lab, live orange to blue with Calc open: column header (240,93,0) to
  (82,133,228), tab underline #f49d66 to (134,181,239), the derived blue tint
  exactly, and the glow. The ribbon icons drawn in the accent follow at the
  next start by design. One lab run stopped answering during Calc's start,
  before any accent change (broker `Describe: TimeoutError`); the identical
  rerun passed.
- The lifecycle case asserts a shown child widget receives `style-updated`
  (with the emission removed it fails, 0 >= 1) and that a handler destroying
  its parent mid-restyle leaves no critical and skips the destroyed sibling.
  `visual_lab.sh` takes `LAB_ACCENT`, default purple as before.
## 2026-11-25 — The suite follows the desktop accent; Base icon
- Reported on the real desktop: changing the accent in Settings left the
  suite purple. Two causes, both by construction: `desktop/launch.py` set
  `GTK_THEME=Yaru-purple-dark` for every launch, and `office.css` defined the
  lavender accent and wrote the glow and default-button hover as fixed colours.
- `native-header/accents/<name>.css` now holds one palette per GNOME accent:
  purple is the design study's lavender, byte for byte; the others derive from
  libadwaita's accent colour by the rule in `tests/test_accents.py`.
  `office.css` keeps the lavender as its defaults and names every accent use.
  The header loads the current palette at USER+3, above the sheet, and reloads
  it on `changed::accent-color`, so GTK restyles the open suite. It connects
  before the first read, because GSettings only signals keys read afterwards.
- The launcher reads the accent through GIO, not a `gsettings` subprocess,
  which tests patch. It picks the nearest dark Yaru theme (Yaru has no slate)
  and passes the accent to the ribbon icon package. The accent is part of the
  presentation revision, so a new accent re-tints those icons once, at the next
  start with the profile closed, through the existing refresh and rollback.
- Checked under Xvfb that a later provider's `@define-color` replaces the
  sheet's for the sheet's own rules, and that reloading it restyles: the new
  lifecycle case reads the computed colour of a default button through
  orange, blue and purple. CI installs `gsettings-desktop-schemas` for it.
- Base has its own icon, from the local generator like Writer and Calc.
## 2026-11-25 — An icon for each application
- The seven module launchers all showed the Office icon. Writer, Calc,
  Impress, Draw and Math now have their own, 512 px PNGs under
  `startup/assets/apps/`. Base and the start center keep `office.png`; a
  module without a file falls back to it, so a runtime from before this change
  still installs.
- Writer and Calc came from the local image generator (qwen21); Impress, Draw
  and Math from the Codex image generation tool, with the first two as the
  style reference. All five were cut from their backgrounds, centred and saved
  without metadata. `provenance.json` beside them has each prompt, seed or
  reference, and the checksums of the original and the shipped file.
- `startup/integrate.py` now checks the application icons against that record
  as it already checked the Office icon. Tests cover the icon each launcher
  gets and a replaced icon being refused.
## 2026-11-24 — The menu toggle case expected a message GLib cannot see
- The first CI run of this branch failed in `test_lifecycle.c`. The
  programmatic toggle case expected GTK's "no trigger event for menu popup"
  warning through `g_test_expect_message()`, and the expectation was never
  met although the warning was printed. GTK 3.24 logs it as a structured
  message (a probe's log writer received it with its `CODE_FILE` field), and
  GLib's expectations only see the old logging API. The case had not been
  run on Linux before.
- The expectation is gone and the warning is left to print; warnings are not
  fatal in this binary. All ten lifecycle cases pass, so the menu button's
  guards behave as the four new cases require, and `scripts/native_ci.sh`
  runs to its end in a clean environment.
- Lesson: `scripts/check.sh` does not run the native cases;
  `scripts/native_ci.sh` does. Run the latter before proposing a branch.
## 2026-11-24 — The restart check repeated on the final build; README aligned
- The in-place restart was checked once more on the real desktop, with the
  build that carries the fix in the entry below: Calc from its menu entry, the
  suite restarted in place, the same helper process serving again with its
  bus name owned, and the helper gone after the close.
- README said a closed profile's update replaces only the extension package.
  Since 1.1.0 it also replaces the ribbon layouts this runtime wrote, so the
  sentence now says that. A layout the user changed, settings and documents
  are kept, as before.
- The scale-2 captures named in the qualification notes came from the lab
  with a 2880 x 1800 monitor and a local scene, not committed, that sets the
  monitor's scale through the compositor.
## 2026-11-24 — Review of the restart change: the helper leaves even when starting over fails

- One independent review of the change below, against the engine's source
  where it mattered. One defect, rare: if the helper could not replace itself
  (the interpreter gone after an upgrade) or the launcher's record was not a
  record, nothing ended it. It would have stayed with a closed pipe, holding
  its bus name and logging a failed description three times a second until
  the next new start. Leaving now runs whatever happens before it.
- Confirmed by the review from source: the pipe is closed across the
  replacement; a signal still ends the helper afterwards; a listener added to
  a bridge that has already ended is told at once; a half-written record makes
  the helper keep waiting rather than leave; a reused process ID would need
  the exact pipe argument.
- Tests added: starting over fails and the helper still leaves; a helper
  waiting for an engine leaves once the suite has gone, through the real
  connect loop against a pipe that does not exist. Both lab probes pass again.
- Not settled from source: whether the bus socket is closed across the
  replacement. The lab and the real desktop both show the name owned again
  afterwards.

## 2026-11-24 — The header helper follows an engine that restarts itself

- Measured first, before any change: after `OfficeRestartManager.requestRestart`
  the engine came back under a new process ID, the helper was gone and the
  header's Undo did nothing. The next start through a menu entry brought a
  helper back, and Undo then worked in the new and in the old window. The gap
  in the entry below was reasoning until this probe.
- Fix: when the engine closes the pipe, the helper looks at the process the
  launcher started (`office_group` in `running.json`, recognised by its
  `--accept` argument, which `launch.running()` also checks). That
  process outlives an in-place restart. While it is there the helper replaces
  itself and waits for the pipe; once it has gone, at the close or during the
  wait, the helper leaves.
- The first attempt asked whether the suite's process group was alive. Wrong
  test: two sandboxed image loaders the engine starts (`glycin-svg`,
  `glycin-image-rs`) stay in that group after it exits, so the helper waited
  its full 15 s after every normal close and ended with a traceback. A trace
  showed the engine and its parent gone 0.4 s after the close and only the
  loaders left.
- Lab with the final code: Undo works after an in-place restart through the
  same helper process, a later menu start does not replace it, the helper is
  gone 0.3 s after a normal close and 0.1 s after a kill, and its log is clean.
- Known gaps: after a crash the engine comes back without its `--accept`
  argument (its own behaviour), so the helper waits 15 s and leaves with an
  error, and a later menu start recovers as before; an engine that needs more
  than 15 s to come back does the same.
- Found on the way, not changed here: on the real desktop every run of the
  suite leaves those two image-loader processes behind (dozens by now, the
  oldest many days old, all owned by the session manager). Whether the
  official LibreOffice launcher leaves them too was not checked, and none
  were stopped.

## 2026-11-24 — First screens of Impress and Base from their own entries

- Impress started without a document opens its template chooser, and Base its
  database wizard. Neither had been captured: every earlier check opened both
  with a fictional document. A lab run started each with no document, as the
  menu entry does.
- Both carry the suite's look without a change: dark panels, the suite's
  fields and drop-downs, the purple default button, readable labels, and the
  template thumbnails on the dark well.
- Not checked: the same two screens on the real desktop (closing them there
  means stopping the suite under a modal dialog), choosing a template, and the
  wizard's later pages.

## 2026-11-24 — The header helper leaves with the engine; Draw's zoom glyph

- `actions.py` stayed behind after the last window closed, until the next
  start stopped it. It now listens on its own end of the pipe (the bridge from
  the local `BridgeFactory`) and exits when the engine closes it. That covers a
  normal close, a kill and a crash alike.
- Lab: the header's Undo still works through the helper, the helper stays
  through 20 s with an idle window, is gone 0.1 s after a normal close and
  0.1 s after the engine is killed, and a later start gets a working one. The
  helper's log no longer ends with a failed description at shutdown.
- Known gap: if the engine restarts itself in place (for example "Restart
  Now" after an option changed through the header's Settings button), the
  header's buttons stay off until the next start through a menu entry brings
  a helper back; the header keeps asking, so open windows recover then.
  Before this change they stayed off until the suite was closed and reopened.
  A helper that starts itself again and waits for the pipe would close the
  gap; it was left out because it lingers 15 s after every normal close.
- One independent review against the engine's source: the bridge factory is
  one instance per context, the bridge tells its listeners when the engine's
  end closes, and the helper cannot lose the bridge while the engine is usable.
- Known gap: the check harnesses signal the recorded helper PID after the
  engine has gone. The helper has left by then; a recycled PID within those
  seconds is not guarded against outside the launcher.
- Draw's Zoom & Pan button (`.uno:ZoomMode`) shares the Zoom artwork through
  the alias table: 142 keys. In the lab only that 16 px box changed in Draw's
  Home tab; the command also sits on the View tab, the zoom bar and the menus
  of Draw and Impress, which show the same artwork and were not captured.
- Started without an accessibility bus, as in one check environment, the
  geometry helper stops at once. Not looked into: it only feeds the glass
  header, which stays off.

## 2026-11-24 — Changed artwork did not reach a profile that had drawn the old icon

- Found comparing the real desktop with the lab at the same scale: Navigator,
  Print Preview and Formatting Marks showed the official glyphs on the real
  profile and ours in the lab, from the same package.
- Cause: the engine keeps every icon it renders under `cache/<icon style>/` in
  the profile, by icon name only. The real profile first drew those three
  before they had artwork of ours, and kept serving that drawing. A lab profile
  is new on every run, so the lab could not show it.
- Fix: `refresh_presentation` removes `cache/sifr_dark_svg` and
  `cache/sifr_svg` after it replaces the package (the profile is closed at that
  point; the engine draws them again). The revision seed moved to v2 so a
  profile that already holds the current package is refreshed once more.
- Deliberately simple: a cache directory that cannot be removed is left as it
  is. An old drawing is cosmetic; stopping the start over it would not be.
- Two independent reviews confirmed the engine's behaviour from its source
  (the cache key is style, scale and icon name; nothing else lives under the
  style directory) and that the refresh path keeps user files. The lab shows
  it end to end: a stand-in drawing placed in the cache is shown for
  Navigator, and a refresh brings the real one back.
- Correction: the real desktop used for the 1.2.0 check runs at scale 1, not 2
  as first recorded in the qualification notes. Scale 2 has only been seen in
  the lab.
- Lesson for checks: a new profile cannot show upgrade defects. Compare the
  real profile with the lab pixel for pixel when both run at one scale.

## 2026-11-24 — Find group: the small buttons start at the left edge everywhere

- The official Writer, Impress and Draw layouts right-align the small button
  row above Find & Select; Calc's does not. `build_find_menu` now drops that
  alignment, so the row starts at the group's left edge in all four. Calc's
  generated layouts are byte-identical to before; the three module layouts get
  new hashes and the launcher replaces the ones it wrote on the next start.
- Checked in the lab at 1440 px: only the button row moved (a 130 x 16 px box
  in each of the three), and each Home tab is unchanged after the window is
  narrowed and widened again.
- Trap for the next check: a lab run that opens Writer first on a new profile
  shows Writer without its sidebar rail, because the launcher hides the sidebar
  once, in whichever application opens first. Compare captures only between
  runs that open the applications in the same order.
- Known gap: that one-time default means the sidebar rail is hidden in the
  application opened first on a new profile and stays in the others. Whether
  every application should start without it is a design choice left open.

## 2026-11-24 — Base froze the suite: command state is asked on the main thread

- Found on the real desktop while checking 1.2.0: a Base window stopped
  answering and took the whole Office process with it. The stack showed glibc
  aborting on a corrupted heap (`malloc(): smallbin double linked list
  corrupted`) inside a bridge thread, and the engine's own crash handler then
  waiting for the same heap lock, so the process hung instead of exiting.
- Cause: `actions.py` answered each `Describe` (every 350 ms per window) by
  adding and removing a status listener per command from the bridge's thread.
  Writer, Calc, Impress, Draw and Math take the engine's main lock inside that
  call. Base's controller (`dbaui::OGenericUnoController`) takes none: its
  listener list and state cache are main-thread only, so the two threads freed
  the same memory. The defect dates from the first native header, not from 1.2.0.
- Fix: `actions.on_main` hands the work to `com.sun.star.awt.AsyncCallback`.
  Office calls it back from its main thread, and the bridge keeps the caller's
  thread identity, so every call made inside the callback runs on that thread.
  A description waits 0.9 s for that callback (the header gives up after one
  second) and an action 25 s (the header waits 30); after that the header is
  told the action is unavailable, and work that has not started never runs.
  Finding the frame still happens on the bridge thread, through code that
  takes the engine's own lock.
- Proof in the lab (a local stress probe, not committed): the old way,
  hammered while the Base categories are clicked, kills the engine within
  seconds with the same class of heap error; the same hammer through
  `AsyncCallback` runs for two minutes (38,479 rounds, about 3 ms of main-thread
  time each) with Base alive and its header states right. Any helper that asks
  a frame for state goes through `on_main`; `verify.py` now does, but
  `capture.sh` was not rerun after that change.
- The launcher's first-window sidebar default asked a dispatch that Base does
  not have, so opening Base first on a new profile raised "Office could not
  start" over a working window. It now leaves the default for the next start
  whose first window has a sidebar.
- A hung Office started by a check script is closed by killing its process
  group, then its broker; `RecoveryInfo` held no session data afterwards. Do not
  run a real-desktop check under `timeout` without a cleanup path.
- Known gap: the broker keeps running after the last window closes, until the
  next launch replaces it. It holds no window and a dead bridge. It also logs
  one failed description when Office closes under a poll; that line is not a
  fault during use (no such line in a minute of Base on the real desktop).
- Rebuilt from `479837e`, reinstalled and checked on the real desktop:
  Calc from its menu entry, then Base for a minute, both closed cleanly.

## 2026-11-23 — Grouped Home tabs beyond Calc, and a header that follows the scale

- `calc_ribbon.py` now builds the Home tab of Writer, Impress and Draw from the
  pinned official layouts (`MODULES`: what moves, what leaves, the group order,
  where the rules go). The launcher writes each one unless the profile has its
  own file for that module, and removes its own file when the official layout
  no longer matches the pin, so LibreOffice's ribbon returns.
- Traps in the engine's ribbon builder, each seen as a crash or a wrong capture:
  a size group that names a widget which is gone aborts the application, so
  `remove_nodes` prunes those names after every removal; a hidden widget that is
  a direct child of a group is shown again after the group collapses and
  regrows, so unwanted separators and groups are removed, never hidden; a new
  child needs an explicit packing position to sort before position 0; Writer's
  file spells property names with hyphens, the others with underscores.
- The style gallery's height comes from the larger of the engine's request and
  the stylesheet's `min-height`; 70 px shows a two-line style name and keeps
  Writer's ribbon card the same height as the others.
- Header icons are rendered at the window's scale factor as surfaces, and the
  window buttons pick a second SVG through `-gtk-scaled`. A surface image does
  not get the dimming a pixbuf image gets when insensitive, so the disabled
  opacity is lower than before. The icons keep the scale the window opened
  with. Glass stays off at any scale but 1, as before.
- The launcher always runs the suite on the dark variant, so a light desktop
  changes only what the desktop itself draws around the window.
- A rule's height follows its group, so groups of different content drew rules
  of different heights. The engine honours `height_request` on a separator;
  76 px with a 5 px page margin gives one height and the same card as before.
- A ribbon control built from native widgets sits on a plate the engine paints
  in the window colour. A field covers it; Draw's fill colour did not, so it now
  has a field of its own. The stylesheet cannot remove the plate itself.
- The style gallery's selector also matches Impress's layout list in the side
  panel, so it carries only what suits both (a minimum height and the label
  size). An edge or radius there boxed the layout list and broke at the
  gallery's corners, where the selected tile paints over it.
- `lab_states.py` clicks fixed points in Calc's Home tab; move them when a group
  changes width, or a popup capture silently shows the wrong control.
- A profile's module ribbon counts as the launcher's when it equals the recorded
  hash or the layout this runtime would write, so a run interrupted before its
  record was saved does not turn its own file into "the user's".
- Only Home is regrouped. The other tabs keep the official layouts.

## 2026-11-23 — Carry the Calc study across the suite

- Added the suite stylesheet `native-header/office.css`, loaded by the header
  module above the theme for the suite's launch only. It styles the header, tab
  row, ribbon card, fields, menus, dialogs, lists, side panels, scrollbars and
  the Start Center in every module from the approved Calc study's values.
- How the engine reads GTK styles, confirmed in captures: provider priority
  beats specificity; the UI font must be one family name; controls the engine
  paints itself carry no sibling position, so
  `:not(:nth-child(odd)):not(:nth-child(even))` selects exactly those (ribbon
  notebook, bare push buttons) and leaves dialog widgets alone; field and
  highlight colours come from a bare `.view` path, normal and selected; a
  selected ribbon tab carries both checked and selected state. Only two widget
  names exist for CSS (`combobox`, `monoborder`); builder ids such as
  `titleparent` are not names.
- Registry defaults in the extension layer, all overridable by the user: Draw's
  tabbed mode without the menu bar; the Drawing bar hidden in Impress and Draw
  (LibreOffice hides it only when the ribbon is chosen by hand); one well colour
  for pages, slides and the Start Center's recent documents; small icons for
  classic toolbars. An extension default cannot override a window state the
  profile already stores, so an existing profile keeps its Drawing bar until it
  is hidden once from View > Toolbars. No headless migration was added.
- The launcher writes an empty quick-access bar for Impress and Draw unless one
  exists, and replaces the Calc ribbon of a closed profile only while the
  installed ribbon is one this runtime wrote, keeping a backup.
- Added a private visual lab: `scripts/visual_lab.sh` runs a scene in an
  isolated headless GNOME session; `lab_tour.py --tabs` captures all seven
  modules and every ribbon tab, `lab_states.py` menus, a dialog, the side panel
  and a narrow window. The ribbon is absent from the accessibility tree, so the
  tab sweep clicks the fixed 100 px tab grid until a click changes nothing.
- Limits of the unmodified engine are recorded in
  `docs/desktop-qualification.md`. Curated ribbons for Writer, Impress and Draw
  remain future work; their stock tabbed layouts are styled but not rearranged.

## 2026-11-12 — Guard the owned menu button's popup lifecycle

- Use a private GtkMenuButton subclass only for the injected titlebar menu.
  Accessible activation is synchronous in GTK; unlike a pointer grab, a second
  programmatic toggle does not dismiss the stock GtkMenu. The owned button now
  explicitly pops it down on inactive toggles and permits closing-state cleanup
  even after its anchor is gone.
- Reject opening from an unmapped, unrealized or destroying owner, including
  reentry during the toggle's state change. The public popup path rechecks
  liveness after anchor-property notifications before opening. No global GTK
  class, engine file or alpha behavior changes.
- Four additional mandatory-hit native cases cover programmatic open/close,
  queued activation during owner teardown before the child drops its popup,
  closure during state change and closure during anchor notifications. Source
  checks pass; exact Linux execution and installed retest remain required.

## 2026-11-12 — Avoid descendant snapshots during active destruction

- A callback entered from an earlier destroy handler now retains only the
  header and window. It does not reference borrowed descendants that the
  earlier handler could already have destroyed. Logical liveness still stops
  the callback before further provider or widget operations.

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
