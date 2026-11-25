import importlib.util
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("mac_trial_prepare", ROOT / "norvi-office/experiments/macos/prepare.py")
MAC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MAC)


class MacTrialTests(unittest.TestCase):
    def fixture(self, root):
        bundle = root / "Official Office.app"
        resources = bundle / "Contents/Resources"
        executable = bundle / "Contents/MacOS/soffice"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"official executable must stay unchanged")
        (bundle / "Contents/Info.plist").write_bytes(plistlib.dumps({"CFBundleIdentifier": "org.libreoffice.script",
                                                                  "CFBundleShortVersionString": "test"}))
        notebook = resources / "config/soffice.cfg/modules/scalc/ui/notebookbar.ui"
        notebook.parent.mkdir(parents=True)
        notebook.write_bytes(b'<interface><object id="ExtensionLabel"><property name="label">Extensions</property></object></interface>')
        for variant in ("sifr_dark_svg", "sifr_svg"):
            with ZipFile(resources / "config" / f"images_{variant}.zip", "w") as archive:
                archive.writestr("links.txt", "cmd/sc_bold.svg old/bold.svg\n")
                archive.writestr("LICENSE", "official theme license must survive")
        return bundle, notebook

    def test_changed_source_and_existing_trial_are_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle, _source = self.fixture(root)
            output = root / "Trial"
            with self.assertRaises(ValueError):
                MAC.prepare(bundle, output)
            self.assertFalse(output.exists())
            output.mkdir()
            document = output / "my work.odt"
            document.write_bytes(b"retain my work")
            with self.assertRaises(ValueError):
                MAC.prepare(bundle, output)
            self.assertEqual(document.read_bytes(), b"retain my work")
            with self.assertRaises(ValueError):
                MAC.safe_output(bundle / "Contents/new trial", bundle)

    def test_native_launchers_keep_normal_recovery_and_their_own_profile(self):
        for appearance in ("dark", "light"):
            with self.subTest(appearance=appearance), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                bundle, source = self.fixture(root)
                before = source.read_bytes()
                ribbon = MAC.ribbon_module()
                output = (root / "Trial with spaces").resolve()
                with patch.object(MAC, "ribbon_module", return_value=ribbon), \
                        patch.object(ribbon, "SOURCE_HASH", MAC.sha256(before).hexdigest()), \
                        patch.object(ribbon, "build_home"), patch.object(ribbon, "add_formulas_tab"), \
                        patch.object(ribbon, "build_find_menu"):
                    receipt = MAC.prepare(bundle, output, appearance)
                self.assertEqual(source.read_bytes(), before)
                self.assertEqual(receipt["profile"], str(output / "profile"))
                self.assertEqual(len(list((output / "Applications").glob("*.app"))), 7)
                self.assertIn("unavailable", receipt["glass"])
                for app in (output / "Applications").glob("*.app"):
                    script = (app / "Contents/MacOS/launch").read_text()
                    self.assertIn((output / "profile").as_uri(), script)
                    self.assertIn("PYTHONDONTWRITEBYTECODE=1", script)
                    self.assertNotIn("--norestore", script)
                    self.assertNotIn("--headless", script)
                    self.assertNotIn("gnome-shell", script)
                self.assertEqual((bundle / "Contents/MacOS/soffice").read_bytes(), b"official executable must stay unchanged")
                with ZipFile(output / "NorviMacTrial.oxt") as package:
                    config = package.read("norvi_glass.xcu")
                    self.assertIn(b"/org.openoffice.Office.UI.ToolbarMode", config)
                    self.assertIn(b"notebookbar.ui", config)
                    self.assertNotIn(b"Cell Styles", config)
                    settings = ET.fromstring(config)
                    for module in ("Calc", "Writer", "Impress", "Draw"):
                        path = ("/org.openoffice.Office.UI.ToolbarMode/Applications/"
                                f"org.openoffice.Office.UI.ToolbarMode:Application['{module}']")
                        matches = [item for item in settings if item.get(f"{{{MAC.REGISTRY}}}path") == path]
                        self.assertEqual(len(matches), 1, module)
                        prop = matches[0].find("prop")
                        self.assertEqual(prop.get(f"{{{MAC.REGISTRY}}}name"), "Active")
                        self.assertEqual(prop.findtext("value"), "notebookbar.ui")
                    variant = "sifr_dark_svg" if appearance == "dark" else "sifr_svg"
                    from io import BytesIO
                    with ZipFile(BytesIO(package.read(f"iconsets/images_{variant}.zip"))) as icons:
                        self.assertEqual(icons.read("LICENSE"), b"official theme license must survive")
                        self.assertIn(b"#f2eff8" if appearance == "dark" else b"#2e3436", icons.read("cmd/sc_bold.svg"))


if __name__ == "__main__":
    unittest.main()
