# Release and update contract

## Channels

Ubuntu's signed archives remain the source of official LibreOffice binaries and
security fixes. Norvi Office is a separate package in the signed Norvi archive.
A normal APT upgrade resolves both feeds. No upstream binary is repacked, no
upstream package is held and no file under /usr/lib/libreoffice is modified.

The initial supported target is Ubuntu 26.04 amd64. Every release first enters
resolute-candidate. Stable promotion uses the archive's seven-day soak, exact
candidate bytes, fresh/subscriber install tests and an explicit Office desktop
qualification review. The APT signing key stays in protected archive CI.

## Producer

A pull request runs source checks, a deterministic package build and actual
installed-payload startup acceptance with fictional Writer and Calc documents.
The release workflow calls the same CI and publishes the exact tested candidate,
its source/ git archive and SHA256SUMS.txt. The artifact name is
norvi-office-debian-candidate; retain it for the archive's import window.
Tags use vX.Y.Z, must be on main and must match VERSION. Rebuilding a candidate
for publication is forbidden. The importer proves the tag, successful exact-tag
run, source archive, asset digests and matching producer artifact.

The upstream workflow runs the native contract against current official
packages without publishing or changing subscriber systems. Unsupported engine
versions disable the experimental native adapter; they do not block engine
security updates. A compatibility failure stops a new UI release.

## Full glass release gates

The experimental native adapter must also pass six application modules, light,
dark and high contrast, reduced motion, 1x/2x/fractional scaling, real multiple
monitors/hotplug, document opacity during transitions, menu fallback and effect
conflicts. Editing, Undo/Redo, format roundtrips, encryption, autosave and
installed upgrade/removal are required. Data model tests use a loopback-only
fixture and an approved scoped database role before any real connection.

Until these gates are evidenced, normal package launches enable the approved
startup/icon presentation only. No claim of stable glass support is made.
Office promotions are review-required even when the package has no root scripts.

The direct desktop qualification path has its own
[module and evidence record](desktop-qualification.md). Its current source uses
a titlebar-only transparency fallback while committed-buffer association is
unresolved. Passing startup or static backdrop checks cannot promote that path
to full ribbon glass.

## Deployment and rollback

The archive imports public producer releases into candidate, then its existing
protected Git-backed publish job signs and deploys through the shadow and public
archive origins. Verify exact signed InRelease bytes and fresh/subscriber
installation. Never publish from a workstation or edit the live archive.

A subscriber enables module shortcuts with norvi-office-integrate --install.
Updates keep stable paths into /usr/share/norvi-office, so the new code and icon
appear on the next launch. Restoring shortcuts checks every managed file before
changing any and preserves subsequent edits. Disable that integration before
APT removal. No root maintainer script writes into a home directory.
