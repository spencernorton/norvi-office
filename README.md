# Norvi Office

A maintained presentation and integration layer for LibreOffice on Ubuntu 26.04.
The official LibreOffice engine stays unmodified. Ubuntu supplies engine and
security updates; the signed Norvi APT channel supplies our UI updates.

The initial package provides the approved Office icon and line-only loading
prompt, a configuration extension and dormant experimental native glass components.
The source release includes the complete qualification harness. The glass adapter is qualified against
LibreOffice 26.2.6.3 and GNOME 50 only and is not enabled by normal launches.

## Build and check

```sh
scripts/check.sh
python3 scripts/build.py --output out/candidate
```

Build dependencies: Python 3, dpkg-dev, a C compiler, pkg-config and GTK 3 headers.
Native qualification also needs LibreOffice GTK3, Python UNO, AT-SPI, Pillow,
GNOME Shell and an isolated display. See docs/release.md for the complete CI path.

## Install and remove

Candidate enrollment is explicit. Once the approved package is available:

```sh
sudo apt install norvi-office
norvi-office-integrate --install
```

The package adds an Office suite launcher. The second command opts the current
user's seven module shortcuts into our presentation. Existing shortcuts are
backed up. Package updates change the shared runtime without freezing a copy
inside the user profile. No document profile is copied or overwritten.

```sh
norvi-office-integrate --uninstall
sudo apt remove norvi-office
```

Remove the shortcut integration before removing the package. A previous preview
installation must be restored with its existing uninstall command first; the
new integration refuses to overwrite it. Saved documents are unaffected.

## Components and compatibility

### Direct desktop opt-in

The explicit desktop integration launches the actual applications on the
current GNOME session. It starts no nested Shell or Devkit viewer and accepts
real document paths/URLs from the normal suite shortcuts and file associations.
A separate persistent Norvi profile retains its settings across launches;
the original LibreOffice profile is preserved. The shared native command broker
routes each header to its own frame when several documents or modules are open.
The integration creates normal desktop and application-menu entries for Writer,
Calc, Impress, Draw, Base, Math and the Office start center. When replacing a
managed design preview, it retires only unchanged preview shortcuts. Open
preview applications, their runtimes and documents are preserved. Uninstalling
the native integration restores those preceding shortcuts.

The current direct-host source limits translucency to the measured native
titlebar. Dynamic ribbon translucency remains blocked on matching each mask to
the actual committed application buffer; a synchronous geometry report alone
does not prove that match. This source is not a completed suite redesign.
See [desktop qualification](docs/desktop-qualification.md) for the module and
acceptance gaps before installing a new candidate.

After locally qualifying a candidate, install the user integration with
`python3 scripts/install_native_desktop.py /path/to/candidate.deb`.
The new compositor extension requires a sign-out/sign-in on GNOME 50; its old
reload API is disabled. Existing open work is never closed for activation.
Restore the preceding launchers with `norvi-office-native-uninstall`; profiles
and documents remain, and open applications can be closed normally.
Restore the native integration before using an older preview removal command.
Removal preserves deleted managed entries as well as saved work; edited or
replaced entries stop removal so their contents can be reviewed. To enroll only
the application-menu entries, pass `--no-desktop-shortcuts` to the installer.
This is an opt-in desktop qualification path, not automatic stable promotion.

### Native Mac design trial

The source can prepare an isolated trial for an official macOS LibreOffice
bundle whose Calc notebookbar matches the pinned source. It reuses the grouped
Calc layout and shared command artwork with native Aqua controls and shortcuts.
The GNOME glass adapter is unavailable on macOS; this does not qualify a glass
release or a completed redesign across all modules.

```sh
python3 norvi-office/experiments/macos/prepare.py --app-bundle /path/to/LibreOffice.app --output /path/to/new-trial --appearance dark
```

Preparation launches nothing and changes neither the application nor the normal
profile. Its receipt includes the explicit `unopkg` installation arguments for
the fresh trial profile. Install that preset before opening its module entries
under `Applications`. All runtime commands preserve document recovery and set
`PYTHONDONTWRITEBYTECODE=1` to keep signed application resources unchanged.
Dark and light variants use the corresponding official Sifr resources and
the approved command paths. Save work before closing; trial documents and
profiles are never removed automatically.

### Visible Linux design preview

The normal Office launcher currently enables the loading prompt and icon only.
It does not display the experimental header, ribbon or glass. The separate
visual-preview launcher opens the real LibreOffice controls in a private visible
GNOME workspace, with a fresh document profile and fictional example document:

```sh
python3 norvi-office/experiments/preview/launch.py --app calc
python3 norvi-office/experiments/preview/launch.py --app writer
```

Install clearly named **Office Preview — Calc** and **Office Preview — Writer**
desktop icons and application entries with `python3 scripts/install_visual_preview.py`. Remove
those entries with `norvi-office-preview-remove`; saved preview documents remain.

It requires the installed Norvi Office package, the matching official Sifr
package, GNOME Shell's Devkit, PipeWire, WirePlumber and the user's existing Blur My Shell extension.
The preview uses its own video policy manager, without opening hardware audio,
Bluetooth or camera monitors. Launch readiness requires the outer desktop viewer
to be mapped with an active video stream; an inner screenshot alone does not pass.
The Calc preview includes the study's grouped ribbon, command artwork and labels,
and hides the sidebar. Icons are derived locally from the installed official
theme; both Calc and Writer use the shared Home command artwork. Theme files are
not vendored in the release. Tab changes trigger layout observations immediately;
the native titlebar stays glass while the ribbon boundary is revalidated. A
stopped geometry bridge still expires to an opaque fallback. The workspace follows the desktop's
animation preference. Save and close documents using their own window controls
before closing the outer preview workspace. Workspaces are retained under the
user's state directory; they never replace the normal LibreOffice profile.

The startup UI is the supported runtime in this initial release. The native
header, glass boundary, ribbon adapter, optional document tools and warehouse
model remain experimental. They are included for reproducible qualification,
not activated by package installation. The document-tools extension requires
an explicit, expiring per-document grant before an AI client can edit.

Unknown LibreOffice versions use the normal engine without the experimental
native adapter. The package does not pin or replace official engine packages.
Our scheduled upstream check records their installed versions and runs the
compatibility gates. No background job changes the user's document profile.

LibreOffice is a project of The Document Foundation. This is an independent UI
layer. Original licenses and upstream branding are retained. The Sifr icon theme remains owned and licensed by its upstream APT package. The generated Office
icon's prompt, model, seed and checksum are included beside its source PNG.
