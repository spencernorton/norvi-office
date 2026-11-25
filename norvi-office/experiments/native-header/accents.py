"""The desktop accent colour, shared by the suite stylesheet and the ribbon icons.

accents/<name>.css holds the colours for each GNOME accent. The native header
loads the current one above office.css and reloads it when the setting changes;
the launcher reads the same files for the GTK theme and the tinted ribbon icons.
"""
from pathlib import Path
import re

FOLDER = Path(__file__).resolve().parent / "accents"
DEFAULT = "purple"  # The approved Norvi lavender, and the colour without a setting.
FALLBACK_THEME = "Yaru-purple-dark"
# The dark Yaru variant nearest each GNOME accent. Yaru has no slate.
THEMES = {
    "blue": "Yaru-blue-dark", "teal": "Yaru-prussiangreen-dark", "green": "Yaru-olive-dark",
    "yellow": "Yaru-yellow-dark", "orange": "Yaru-dark", "red": "Yaru-red-dark",
    "pink": "Yaru-magenta-dark", "purple": "Yaru-purple-dark", "slate": "Yaru-sage-dark",
}
THEME_FOLDERS = (Path("/usr/share/themes"),)


def known(name):
    return isinstance(name, str) and re.fullmatch(r"[a-z]+", name) is not None and (FOLDER / f"{name}.css").is_file()


def current():
    """The desktop's accent name, or the Norvi default when it has none we know."""
    try:
        import gi
        gi.require_version("Gio", "2.0")
        from gi.repository import Gio
    except (ImportError, ValueError):
        return DEFAULT
    source = Gio.SettingsSchemaSource.get_default()
    schema = source.lookup("org.gnome.desktop.interface", True) if source else None
    if schema is None or not schema.has_key("accent-color"):
        return DEFAULT
    name = Gio.Settings.new("org.gnome.desktop.interface").get_string("accent-color")
    return name if known(name) else DEFAULT


def colours(name):
    """The accent's named colours, e.g. {"accent_icon": "#c1aaf3", ...}."""
    if not known(name):
        name = DEFAULT
    return dict(re.findall(r"@define-color (\w+) (#[0-9a-f]{6});", (FOLDER / f"{name}.css").read_text()))


def theme(name):
    """The installed dark GTK theme that matches the accent."""
    candidate = THEMES.get(name, FALLBACK_THEME)
    return candidate if any((folder / candidate).is_dir() for folder in THEME_FOLDERS) else FALLBACK_THEME
