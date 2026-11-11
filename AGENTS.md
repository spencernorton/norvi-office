# Norvi Office contributor guidance

Keep changes on a topic branch. Read README.md and AGENTS/journal.md first.
Run scripts/check.sh, build the Debian candidate, and exercise the installed
payload before proposing a release. CI must qualify that same candidate.

Keep the LibreOffice engine unmodified and independently updatable. Never add
holds or upper-version dependencies that prevent official security updates.
The native glass adapter is experimental and must fail closed on an unknown
engine version or desktop. Default launches continue using upstream Office.

Never publish personal paths, infrastructure details, credentials or private
histories. Demonstration documents must be fictional. Preserve icon licenses
and provenance. Record meaningful changes as a new top journal entry.
