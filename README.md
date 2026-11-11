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
