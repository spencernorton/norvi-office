import importlib.util
from io import BytesIO
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / "norvi-office/experiments/native-header"
# GNOME's accent colours, as libadwaita defines them.
GNOME = {"blue": "#3584e4", "teal": "#2190a4", "green": "#3a944a", "yellow": "#c88800", "orange": "#ed5b00",
         "red": "#e62d42", "pink": "#d56199", "purple": "#9141ac", "slate": "#6f8396"}
TOKENS = {"accent_deep", "accent", "accent_hover", "accent_glow", "accent_glow_dim", "accent_icon",
          "accent_icon_light", "accent_band"}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def derived(base):
    """The rule the generated palettes follow, fitted to the approved lavender."""
    def rgb(value):
        return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))

    def mix(first, second, fraction):
        return "#%02x%02x%02x" % tuple(round(a * (1 - fraction) + b * fraction) for a, b in zip(first, second))

    colour, white, chrome = rgb(base), (255, 255, 255), (0x25, 0x24, 0x2d)
    return {"accent_deep": base, "accent": mix(colour, white, .4), "accent_hover": mix(colour, white, .1),
            "accent_glow": mix(colour, chrome, .15), "accent_glow_dim": mix(colour, chrome, .62),
            "accent_icon": mix(colour, white, .5), "accent_icon_light": base, "accent_band": band(colour)}


def contrast_with_black(value):
    def channel(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (int(value[i:i + 2], 16) for i in (1, 3, 5))
    return (0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b) + 0.05) / 0.05


def band(colour):
    """Base's section band: a muted accent tint at the approved band's contrast with black text."""
    def mix(first, second, fraction):
        return tuple(round(a * (1 - fraction) + b * fraction) for a, b in zip(first, second))

    def hexa(value):
        return "#%02x%02x%02x" % value

    tint = mix(colour, (149, 149, 149), 0.82)
    target = contrast_with_black("#8f8aa0")
    steps = [i / 200 for i in range(101)]
    options = [(abs(contrast_with_black(hexa(mix(tint, (255, 255, 255), f))) - target), f) for f in steps]
    options += [(abs(contrast_with_black(hexa(mix(tint, (0, 0, 0), f))) - target), -f) for f in steps[1:]]
    shift = min(options)[1]
    return hexa(mix(tint, (255, 255, 255), shift) if shift >= 0 else mix(tint, (0, 0, 0), -shift))


class AccentTests(unittest.TestCase):
    def setUp(self):
        self.accents = load("accents_test", HEADER / "accents.py")

    def test_every_gnome_accent_has_a_palette_derived_from_its_colour(self):
        self.assertEqual({path.stem for path in (HEADER / "accents").glob("*.css")}, set(GNOME))
        for name, base in GNOME.items():
            with self.subTest(accent=name):
                colours = self.accents.colours(name)
                self.assertEqual(set(colours), TOKENS)
                if name != "purple":
                    self.assertEqual(colours, derived(base))

    def test_purple_is_the_approved_lavender_and_the_sheet_never_hard_codes_an_accent(self):
        sheet = (HEADER / "office.css").read_text()
        defaults = dict(re.findall(r"@define-color (accent\w*) (#[0-9a-f]{6});", sheet))
        purple = self.accents.colours("purple")
        self.assertEqual(set(defaults), TOKENS - {"accent_icon", "accent_icon_light"})
        # Base's black section titles stay readable in every accent.
        for name in GNOME:
            self.assertGreaterEqual(contrast_with_black(self.accents.colours(name)["accent_band"]), 6.0, name)
        self.assertEqual(defaults, {key: purple[key] for key in defaults})
        self.assertEqual((purple["accent_icon"], purple["accent_icon_light"]), ("#c1aaf3", "#7460d4"))
        rules = re.sub(r"@define-color[^\n]*\n", "", sheet)
        for value in purple.values():
            self.assertNotIn(value, rules)
        for legacy in ("rgba(107, 85, 160", "rgba(69, 64, 102"):
            self.assertNotIn(legacy, sheet)

    def test_unknown_or_unsafe_names_use_the_default(self):
        self.assertTrue(self.accents.known("orange"))
        for name in ("", "Orange", "../purple", "orange/../purple", "magenta", None):
            with self.subTest(name=name):
                self.assertFalse(self.accents.known(name))
                self.assertEqual(self.accents.colours(name), self.accents.colours(self.accents.DEFAULT))

    def test_each_accent_selects_an_installed_dark_theme(self):
        self.assertEqual(set(self.accents.THEMES), set(GNOME))
        # The ribbon layout reads "dark" in the theme name.
        self.assertTrue(all("dark" in theme for theme in self.accents.THEMES.values()))
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            (folder / "Yaru-blue-dark").mkdir()
            with patch.object(self.accents, "THEME_FOLDERS", (folder,)):
                self.assertEqual(self.accents.theme("blue"), "Yaru-blue-dark")
                self.assertEqual(self.accents.theme("teal"), self.accents.FALLBACK_THEME)
                self.assertEqual(self.accents.theme("unknown"), self.accents.FALLBACK_THEME)

    def test_ribbon_icons_drawn_in_the_accent_take_its_colour(self):
        ribbon = load("accent_ribbon", HEADER / "calc_ribbon.py")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base, icons = root / "base.oxt", root / "official-icons.zip"
            with ZipFile(base, "w") as archive:
                archive.writestr("norvi_glass.xcu", (ROOT / "norvi-office/extension/norvi_glass.xcu").read_bytes())
            with ZipFile(icons, "w") as archive:
                archive.writestr("links.txt", "")
                archive.writestr("LICENSE", "official theme license")
            for accent in (None, "purple", "orange", "blue"):
                for appearance, ink in (("dark", "#f2eff8"), ("light", "#2e3436")):
                    with self.subTest(accent=accent, appearance=appearance):
                        output = root / f"{accent}-{appearance}.oxt"
                        ribbon.preview_package(base, output, "calc", icons, appearance, accent=accent)
                        palette = self.accents.colours(accent or "purple")
                        tint = palette["accent_icon" if appearance == "dark" else "accent_icon_light"]
                        style = "sifr_dark_svg" if appearance == "dark" else "sifr_svg"
                        with ZipFile(output) as package, ZipFile(BytesIO(package.read(f"iconsets/images_{style}.zip"))) as theme:
                            for command, colour in (("conditionalformatmenu", tint), ("bold", ink)):
                                svg = ET.fromstring(theme.read(f"cmd/lc_{command}.svg"))
                                self.assertEqual(svg.find("{http://www.w3.org/2000/svg}path").get("stroke"), colour)


if __name__ == "__main__":
    unittest.main()
