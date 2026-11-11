import importlib.util
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import socket
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "norvi-office/experiments"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PreviewTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("desktop-file-validate"), "Linux desktop validation required")
    def test_shortcut_rollback_preserves_normal_office_user_edits_and_documents(self):
        installer = load("preview_installer", ROOT / "scripts/install_visual_preview.py")
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            data = home / "share"
            applications = data / "applications"
            applications.mkdir(parents=True)
            normal = applications / "libreoffice-calc.desktop"
            original_office = "[Desktop Entry]\nType=Application\nName=Existing Calc\nExec=libreoffice --calc\n"
            normal.write_text(original_office)
            document = home / "retained-preview-document.ods"
            document.write_bytes(b"user work")
            manifest = data / "norvi-office/visual-preview/shortcuts.json"
            desktop = home / "Desktop"
            with patch.object(installer, "locations", return_value=(home, data, desktop, manifest)), \
                    patch.object(installer, "trust_desktop") as trust:
                installer.install()
                self.assertEqual(trust.call_count, 2)
                desktop_calc = desktop / "Office Preview - calc.desktop"
                self.assertEqual(desktop_calc.stat().st_mode & 0o777, 0o755)
                self.assertIn("Name=Office Preview — Calc", desktop_calc.read_text())
                preview = applications / "norvi-office-preview-calc.desktop"
                original = preview.read_text()
                preview.write_text(original + "# user edit\n")
                with self.assertRaises(ValueError):
                    installer.uninstall()
                self.assertTrue((home / ".local/bin/norvi-office-preview").exists())
                preview.write_text(original)
                installer.uninstall()
            self.assertEqual(normal.read_text(), original_office)
            self.assertEqual(document.read_bytes(), b"user work")
            self.assertFalse(preview.exists())
            self.assertFalse(desktop_calc.exists())
            self.assertFalse((home / ".local/bin/norvi-office-preview").exists())

    @unittest.skipUnless(shutil.which("desktop-file-validate"), "Linux desktop validation required")
    def test_legacy_install_adopts_matching_desktop_copy_but_preserves_foreign_copy(self):
        installer = load("preview_installer_upgrade", ROOT / "scripts/install_visual_preview.py")
        for foreign in (False, True):
            with self.subTest(foreign=foreign), tempfile.TemporaryDirectory() as temporary:
                home = Path(temporary)
                data, desktop = home / "share", home / "Desktop"
                manifest = data / "norvi-office/visual-preview/shortcuts.json"
                with patch.object(installer, "locations", return_value=(home, data, desktop, manifest)), \
                        patch.object(installer, "trust_desktop"):
                    installer.install()
                    record = json.loads(manifest.read_text())
                    record["files"] = [r for r in record["files"] if Path(r["path"]).parent != desktop]
                    manifest.write_text(json.dumps(record))
                    copy = desktop / "Office Preview - calc.desktop"
                    if foreign:
                        copy.write_text("user's launcher")
                        with self.assertRaises(ValueError):
                            installer.install()
                        self.assertEqual(copy.read_text(), "user's launcher")
                        self.assertEqual(len(json.loads(manifest.read_text())["files"]), 4)
                    else:
                        installer.install()
                        self.assertEqual(len(json.loads(manifest.read_text())["files"]), 6)
                        installer.uninstall()
                        self.assertFalse(copy.exists())

    def test_visible_viewer_requires_its_own_running_linked_video_stream(self):
        visible = load("preview_visible", EXPERIMENTS / "preview/visible.py")
        objects = [
            {"id": 35, "type": "PipeWire:Interface:Client",
             "info": {"props": {"application.process.id": 123}}},
            {"id": 39, "type": "PipeWire:Interface:Node",
             "info": {"props": {"client.id": 35, "media.class": "Stream/Input/Video"}, "state": "running"}},
            {"id": 56, "type": "PipeWire:Interface:Link", "info": {"state": "active", "input-node-id": 39}},
        ]
        self.assertTrue(visible.video_connected(objects, 123))
        self.assertFalse(visible.video_connected(objects, 456))
        self.assertFalse(visible.video_connected(objects[:2], 123))
        objects[1]["info"]["state"] = "suspended"
        self.assertFalse(visible.video_connected(objects, 123))

    def test_ribbon_uses_official_installed_icons_without_vendored_zip(self):
        fixture = SimpleNamespace(connect=None, prop=None, stop_office=None)
        with patch.dict(sys.modules, {"fixtures": fixture}):
            ribbon = load("preview_ribbon", EXPERIMENTS / "native-header/calc_ribbon.py")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base, icons, output = (root / name for name in ("base.oxt", "icons.zip", "overlay.oxt"))
            with ZipFile(base, "w") as archive:
                archive.writestr("norvi_glass.xcu", (ROOT / "norvi-office/extension/norvi_glass.xcu").read_bytes())
                archive.writestr("description.xml", "unchanged")
            with ZipFile(icons, "w") as archive:
                archive.writestr("links.txt", "cmd/sc_paste.svg cmd/old.svg\n")
                archive.writestr("LICENSE", "upstream license")
            with patch.object(ribbon, "SYSTEM_ICONS", icons):
                ribbon.preview_package(base, output)
            with ZipFile(output) as archive:
                self.assertEqual(archive.read("description.xml"), b"unchanged")
                config = archive.read("norvi_glass.xcu")
                self.assertIn(b"%origin%/iconsets", config)
                self.assertIn(b"Conditional Formatting", config)
                self.assertIn(b"CalcCommands/UserInterface/Popups/['.uno:RowOperations']", config)
                with ZipFile(BytesIO(archive.read("iconsets/images_sifr_dark_svg.zip"))) as theme:
                    self.assertEqual(theme.read("LICENSE"), b"upstream license")
                    self.assertIn(b"#f2eff8", theme.read("cmd/sc_paste.svg"))
                    self.assertNotIn(b"cmd/sc_paste.svg", theme.read("links.txt"))
            writer_output = root / "writer.oxt"
            with patch.object(ribbon, "SYSTEM_ICONS", icons):
                ribbon.preview_package(base, writer_output, "writer")
            with ZipFile(writer_output) as archive:
                self.assertNotIn(b"Cell Styles", archive.read("norvi_glass.xcu"))
                with ZipFile(BytesIO(archive.read("iconsets/images_sifr_dark_svg.zip"))) as theme:
                    for prefix in ("sc_", "lc_", "32/"):
                        for command in ("fontcolor", "backgroundcolor", "grow", "numberformatpercent", "paste"):
                            self.assertIn(b"stroke-width=\"1.55\"", theme.read(f"cmd/{prefix}{command}.svg"))

    def test_preview_separates_bus_config_and_display_from_live_session(self):
        launch = load("preview_launch", EXPERIMENTS / "preview/launch.py")
        with tempfile.TemporaryDirectory() as temporary, socket.socket(socket.AF_UNIX) as display:
            root = Path(temporary)
            display.bind(str(root / "wayland-parent"))
            workspace = root / "capture.preview-test"
            workspace.mkdir()
            parent = {"XDG_RUNTIME_DIR": str(root), "WAYLAND_DISPLAY": "wayland-parent",
                      "DBUS_SESSION_BUS_ADDRESS": "live-session", "AT_SPI_BUS_ADDRESS": "live-atspi",
                      "XDG_CONFIG_HOME": "live-config", "GTK3_MODULES": "unrelated-module", "LD_PRELOAD": "other"}
            environment = launch.preview_environment(workspace, parent)
            for name in ("DBUS_SESSION_BUS_ADDRESS", "AT_SPI_BUS_ADDRESS", "GTK3_MODULES", "LD_PRELOAD"):
                self.assertNotIn(name, environment)
            self.assertEqual(environment["WAYLAND_DISPLAY"], str(root / "wayland-parent"))
            self.assertEqual(environment["XDG_CONFIG_HOME"], str(workspace / "config"))
            self.assertEqual(parent["XDG_CONFIG_HOME"], "live-config")
            self.assertEqual(len(environment["NORVI_OFFICE_HEADER_TOKEN"]), 64)
            self.assertEqual(os.stat(workspace / "runtime").st_mode & 0o777, 0o700)


if __name__ == "__main__":
    unittest.main()
