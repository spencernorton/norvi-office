import hashlib
import importlib.util
from io import BytesIO
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch
from zipfile import ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture(directory):
    root, share, header = (directory / name for name in ("session", "share", "header"))
    root.mkdir()
    (share / "extensions").mkdir(parents=True)
    header.mkdir()
    (header / "calc_ribbon.py").write_text("owned artwork revision one\n")
    ribbon = load("refresh_ribbon", ROOT / "norvi-office/experiments/native-header/calc_ribbon.py")
    icons = directory / "official-icons.zip"
    with ZipFile(icons, "w") as archive:
        archive.writestr("links.txt", "cmd/sc_paste.svg cmd/sc_old.svg\n")
        archive.writestr("LICENSE", "official icon license")
    ribbon.SYSTEM_ICONS = icons
    with ZipFile(share / "extensions/NorviGlass.oxt", "w") as archive:
        for filename in ("description.xml", "norvi_glass.xcu"):
            archive.writestr(filename, (ROOT / "norvi-office/extension" / filename).read_bytes())
    with patch.dict(sys.modules, {"uno_utils": SimpleNamespace(connect=None, prop=None, stop_office=None), "calc_ribbon": ribbon}):
        launch = load("refresh_launch", ROOT / "norvi-office/experiments/desktop/launch.py")
    launch.SHARE, launch.HEADER = share, header
    package = root / "NorviDesktop.oxt"
    # A real old overlay, with a smaller command set and the same extension ID.
    with patch.dict(ribbon.ICONS, {"paste": ribbon.ICONS["paste"]}, clear=True):
        ribbon.preview_package(share / "extensions/NorviGlass.oxt", package)
    profile = root / "profile-calc"
    retained = [profile / "user/config/soffice.cfg/modules/scalc/ui/notebookbar.ui",
                profile / "user/registrymodifications.xcu", root / "work.ods"]
    for index, path in enumerate(retained):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"user work {index}".encode())
    (root / "profile-ready.json").write_text(json.dumps({"separate_profile": str(profile), "schema": 1, "retained": "metadata"}) + "\n")
    installed = profile / "user/uno_packages/owned-package.oxt"

    def install(arguments, **_kwargs):
        if arguments[:2] != ["unopkg", "add"] or "-env:UserInstallation=" + profile.as_uri() not in arguments:
            raise AssertionError(arguments)
        installed.parent.mkdir(parents=True, exist_ok=True)
        installed.write_bytes(Path(arguments[-1]).read_bytes())
        return subprocess.CompletedProcess(arguments, 0)

    return launch, root, profile, retained, installed, install


class PresentationRefreshTests(unittest.TestCase):
    def test_new_profile_records_revision_and_installed_package_digest(self):
        with tempfile.TemporaryDirectory() as temporary:
            launch, root, profile, _retained, installed, install = fixture(Path(temporary))
            shutil.rmtree(profile)
            (root / "profile-ready.json").unlink()
            (root / "NorviDesktop.oxt").unlink()
            settings = SimpleNamespace(getCount=lambda: 0)
            manager = SimpleNamespace(getSettings=lambda *_args: settings, replaceSettings=lambda *_args: None, store=lambda: None)
            supplier = SimpleNamespace(getUIConfigurationManager=lambda _name: manager)
            config = SimpleNamespace(commitChanges=lambda: None)
            provider = SimpleNamespace(createInstanceWithArguments=lambda *_args: config)
            desktop = SimpleNamespace(terminate=lambda: None)
            context = SimpleNamespace(getValueByName=lambda _name: supplier,
                                      ServiceManager=SimpleNamespace(createInstanceWithContext=lambda name, _context:
                                          provider if name.endswith("ConfigurationProvider") else desktop))
            with patch.object(launch.subprocess, "run", side_effect=install), \
                    patch.object(launch.subprocess, "Popen", return_value=SimpleNamespace(pid=123)), \
                    patch.object(launch, "prepare") as prepare, patch.object(launch, "connect", return_value=context), \
                    patch.object(launch, "prop", side_effect=lambda *_args: None), patch.object(launch, "stop_office"):
                self.assertEqual(launch.initialize(root, {}), profile)
                prepare.assert_called_once_with(profile, native=True, environment={})
            record = json.loads((root / "profile-ready.json").read_text())
            self.assertEqual(record["presentation_revision"], launch.presentation_revision())
            self.assertEqual(record["presentation_package_sha256"], hashlib.sha256(installed.read_bytes()).hexdigest())

    def test_legacy_closed_profile_receives_new_icons_without_resetting_user_work(self):
        with tempfile.TemporaryDirectory() as temporary:
            launch, root, profile, retained, installed, install = fixture(Path(temporary))
            before = {path: path.read_bytes() for path in retained}
            package = root / "NorviDesktop.oxt"
            old = package.read_bytes()
            with patch.object(launch, "profile_live", return_value=False), \
                    patch.object(launch.subprocess, "run", side_effect=install) as run, \
                    patch.object(launch, "prepare") as prepare, patch.object(launch, "connect") as connect:
                self.assertEqual(launch.initialize(root, {}), profile)
                self.assertIn("--force", run.call_args.args[0])
                self.assertEqual(installed.read_bytes(), package.read_bytes())
                with ZipFile(package) as archive, ZipFile(BytesIO(archive.read("iconsets/images_sifr_dark_svg.zip"))) as theme:
                    self.assertIn("cmd/lc_presentationcurrentslide.svg", theme.namelist())
                    self.assertIn("cmd/lc_basicshapes.rectangle.svg", theme.namelist())
                record = json.loads((root / "profile-ready.json").read_text())
                self.assertEqual(record["presentation_revision"], launch.presentation_revision())
                self.assertEqual(record["presentation_package_sha256"], hashlib.sha256(package.read_bytes()).hexdigest())
                self.assertEqual(record["retained"], "metadata")
                self.assertEqual(next(root.glob("NorviDesktop.backup-*.oxt")).read_bytes(), old)
                marker = (root / "profile-ready.json").read_bytes()
                launch.initialize(root, {})
                self.assertEqual(run.call_count, 1)
                self.assertEqual((root / "profile-ready.json").read_bytes(), marker)
                prepare.assert_not_called()
                connect.assert_not_called()
            self.assertEqual({path: path.read_bytes() for path in retained}, before)

    def test_closed_profile_gets_current_ribbon_and_quiet_shortcut_bars(self):
        with tempfile.TemporaryDirectory() as temporary:
            launch, root, profile, retained, _installed, install = fixture(Path(temporary))
            ribbon, modules = retained[0], profile / "user/config/soffice.cfg/modules"
            custom = modules / "sdraw/toolbar/notebookbarshortcuts.xml"
            custom.parent.mkdir(parents=True)
            custom.write_text("customised by the user")
            retired = hashlib.sha256(ribbon.read_bytes()).hexdigest()
            with patch.object(launch, "profile_live", return_value=False), \
                    patch.object(launch.subprocess, "run", side_effect=install), \
                    patch.object(launch.calc_ribbon, "RETIRED_RIBBONS", {retired}), \
                    patch.object(launch.calc_ribbon, "ribbon", return_value=b"current ribbon"):
                launch.initialize(root, {})
            self.assertEqual(ribbon.read_bytes(), b"current ribbon")
            self.assertEqual((root / f"notebookbar.backup-{retired}.ui").read_bytes(), b"user work 0")
            record = json.loads((root / "profile-ready.json").read_text())
            self.assertEqual(record["ribbon_sha256"], hashlib.sha256(b"current ribbon").hexdigest())
            self.assertEqual(custom.read_text(), "customised by the user")
            self.assertEqual((modules / "simpress/toolbar/notebookbarshortcuts.xml").read_text(), launch.EMPTY_TOOLBAR)

    def test_module_ribbons_follow_the_runtime_until_the_user_changes_one(self):
        with tempfile.TemporaryDirectory() as temporary:
            launch, _root, profile, _retained, _installed, _install = fixture(Path(temporary))
            paths = {module: profile / "user/config/soffice.cfg/modules" / module / "ui/notebookbar.ui"
                     for module in launch.calc_ribbon.MODULES}
            paths["sdraw"].parent.mkdir(parents=True)
            paths["sdraw"].write_text("customised by the user")
            with patch.object(launch.calc_ribbon, "module_ribbon", side_effect=lambda module: module.encode()):
                record = launch.module_ribbons(profile, {})
            self.assertEqual(set(record["ribbons"]), {"swriter", "simpress"})
            self.assertEqual(paths["swriter"].read_bytes(), b"swriter")
            self.assertEqual(paths["sdraw"].read_text(), "customised by the user")
            paths["simpress"].write_text("edited later")
            with patch.object(launch.calc_ribbon, "module_ribbon", return_value=b"next"):
                record = launch.module_ribbons(profile, record)
            self.assertEqual(paths["swriter"].read_bytes(), b"next")
            self.assertEqual(paths["simpress"].read_text(), "edited later")
            self.assertEqual(set(record["ribbons"]), {"swriter"})
            # A run interrupted before its record was saved still owns what it wrote.
            with patch.object(launch.calc_ribbon, "module_ribbon", return_value=b"next"):
                self.assertEqual(set(launch.module_ribbons(profile, {})["ribbons"]), {"swriter"})
            # An unknown official layout gets its own ribbon back.
            with patch.object(launch.calc_ribbon, "module_ribbon", return_value=None):
                record = launch.module_ribbons(profile, record)
            self.assertFalse(paths["swriter"].exists())
            self.assertEqual(record["ribbons"], {})
            self.assertEqual(paths["simpress"].read_text(), "edited later")

    def test_module_home_tabs_keep_the_planned_groups_and_commands(self):
        ribbon = load("module_ribbon", ROOT / "norvi-office/experiments/native-header/calc_ribbon.py")
        for module, spec in ribbon.MODULES.items():
            contents = ribbon.module_ribbon(module)
            if contents is None:
                self.skipTest("The pinned official layouts are not installed here")
            with self.subTest(module=module):
                tree = ET.fromstring(contents)
                page = tree.find(".//object[@id='Home Tab']")
                home = page.find(".//object[@id='Home']")
                self.assertEqual([child.find("object").get("id") for child in home.findall("child")],
                                 ["Home-Section-" + name for name in spec["sections"]])
                identifiers = {item.get("id") for item in page.iter("object")}
                self.assertFalse(identifiers.intersection(spec["drop"]))
                for identifier, _source, destination in spec["move"]:
                    self.assertIsNotNone(page.find(f".//object[@id='{destination}']//object[@id='{identifier}']"))
                self.assertEqual({item.get("id") for item in home.iter("object") if item.get("class") == "GtkSeparator"},
                                 {"NorviRule" + name for name in spec["rules"]})
                self.assertIn("Home-HomeButton:Norvi Find and Select", identifiers)
                self.assertFalse({item.get("name") for item in tree.iter("widget")}
                                 - {item.get("id") for item in tree.iter("object")})
                self.assertEqual(len(tree.findall("object[@id='Norvi Find and Select']/child")), len(spec["find"]))
        calc = ET.fromstring(ribbon.ribbon({"GTK_THEME": "Yaru-purple-dark"}, native=True))
        self.assertFalse({item.get("name") for item in calc.iter("widget")}
                         - {item.get("id") for item in calc.iter("object")})
        self.assertFalse([item for item in calc.find(".//object[@id='Home']").iter("object")
                          if item.get("class") == "GtkSeparator" and not item.get("id").startswith("NorviRule")])

    def test_live_exact_profile_defers_without_touching_package_or_marker(self):
        with tempfile.TemporaryDirectory() as temporary:
            launch, root, profile, _retained, _installed, _install = fixture(Path(temporary))
            proc = Path(temporary) / "proc"
            process = proc / "123"
            process.mkdir(parents=True)
            expected = ("-env:UserInstallation=" + profile.as_uri()).encode()
            process.joinpath("cmdline").write_bytes(b"soffice.bin\0" + expected + b"-other\0")
            self.assertFalse(launch.profile_live(root, profile, proc))
            process.joinpath("cmdline").write_bytes(b"soffice.bin\0" + expected + b"\0")
            self.assertTrue(launch.profile_live(root, profile, proc))
            read_bytes = Path.read_bytes

            def unreadable(path):
                if path == process / "cmdline":
                    raise PermissionError("owned process arguments unavailable")
                return read_bytes(path)

            with patch.object(Path, "read_bytes", unreadable):
                self.assertTrue(launch.profile_live(root, profile, proc), "Unknown owned process must defer migration")
            snapshot = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
            check_live = launch.profile_live
            with patch.object(launch, "profile_live", side_effect=lambda r, p: check_live(r, p, proc)), \
                    patch.object(launch.subprocess, "run") as run, patch.object(launch, "preview_package") as build:
                self.assertEqual(launch.initialize(root, {}), profile)
                run.assert_not_called()
                build.assert_not_called()
            self.assertEqual({path: path.read_bytes() for path in root.rglob("*") if path.is_file()}, snapshot)
            with patch.object(launch, "running", return_value=True):
                self.assertTrue(launch.profile_live(root, profile, Path("/nonexistent-proc")))

    def test_failed_install_rolls_back_and_next_launch_retries(self):
        with tempfile.TemporaryDirectory() as temporary:
            launch, root, profile, retained, installed, install = fixture(Path(temporary))
            before = {path: path.read_bytes() for path in retained}
            package, ready = root / "NorviDesktop.oxt", root / "profile-ready.json"
            old, marker = package.read_bytes(), ready.read_bytes()
            attempts = []

            def fail_once(arguments, **kwargs):
                attempts.append(arguments)
                install(arguments, **kwargs)
                if len(attempts) == 1:
                    raise subprocess.CalledProcessError(1, arguments)

            with patch.object(launch, "profile_live", return_value=False), \
                    patch.object(launch.subprocess, "run", side_effect=fail_once):
                with self.assertRaisesRegex(RuntimeError, "previous package restored"):
                    launch.initialize(root, {})
                self.assertEqual(installed.read_bytes(), old)
                self.assertEqual(package.read_bytes(), old)
                self.assertEqual(ready.read_bytes(), marker)
                self.assertEqual(len(attempts), 2)
                self.assertIn("backup-", attempts[1][-1])
                self.assertEqual(launch.initialize(root, {}), profile)
            self.assertNotEqual(installed.read_bytes(), old)
            self.assertEqual(len(attempts), 3)
            self.assertEqual({path: path.read_bytes() for path in retained}, before)

    def test_unknown_missing_symlink_and_edited_owned_packages_are_preserved(self):
        for replacement in ("missing", "symlink", "foreign", "edited"):
            with self.subTest(replacement=replacement), tempfile.TemporaryDirectory() as temporary:
                launch, root, _profile, _retained, _installed, _install = fixture(Path(temporary))
                package, ready = root / "NorviDesktop.oxt", root / "profile-ready.json"
                if replacement == "missing":
                    package.unlink()
                elif replacement == "symlink":
                    saved = Path(temporary) / "user-package.oxt"
                    package.rename(saved)
                    package.symlink_to(saved)
                elif replacement == "foreign":
                    with ZipFile(package, "w") as archive:
                        archive.writestr("description.xml", "<description/>")
                else:
                    record = json.loads(ready.read_text())
                    record["presentation_package_sha256"] = "not-the-package-digest"
                    ready.write_text(json.dumps(record))
                snapshot = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
                with patch.object(launch, "profile_live", return_value=False), patch.object(launch.subprocess, "run") as run:
                    with self.assertRaises(ValueError):
                        launch.initialize(root, {})
                    run.assert_not_called()
                self.assertEqual({path: path.read_bytes() for path in root.rglob("*") if path.is_file()}, snapshot)
                self.assertEqual(package.is_symlink(), replacement == "symlink")

    def test_failed_rollback_retains_backup_and_old_ready_record(self):
        with tempfile.TemporaryDirectory() as temporary:
            launch, root, _profile, _retained, _installed, _install = fixture(Path(temporary))
            package, ready = root / "NorviDesktop.oxt", root / "profile-ready.json"
            old, marker = package.read_bytes(), ready.read_bytes()
            with patch.object(launch, "profile_live", return_value=False), \
                    patch.object(launch.subprocess, "run", side_effect=OSError("unopkg unavailable")):
                with self.assertRaisesRegex(RuntimeError, "backup retained.*Rollback failed"):
                    launch.initialize(root, {})
            self.assertEqual(package.read_bytes(), old)
            self.assertEqual(ready.read_bytes(), marker)
            self.assertEqual(next(root.glob("NorviDesktop.backup-*.oxt")).read_bytes(), old)

    def test_revision_is_reproducible_but_changes_with_each_presentation_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            launch, _root, _profile, _retained, _installed, _install = fixture(Path(temporary))
            revision = launch.presentation_revision()
            base = launch.SHARE / "extensions/NorviGlass.oxt"
            with ZipFile(base) as archive:
                contents = {name: archive.read(name) for name in archive.namelist()}
            with ZipFile(base, "w") as archive:
                for name, data in reversed(list(contents.items())):
                    entry = ZipInfo(name, (2000, 1, 1, 0, 0, 0))
                    archive.writestr(entry, data)
            self.assertEqual(launch.presentation_revision(), revision)
            for target in (launch.HEADER / "calc_ribbon.py", base, launch.calc_ribbon.SYSTEM_ICONS):
                original = target.read_bytes()
                if target.suffix == ".py":
                    target.write_bytes(original + b"new artwork\n")
                else:
                    with ZipFile(target, "a") as archive:
                        archive.writestr("new-presentation-input", "changed content")
                self.assertNotEqual(launch.presentation_revision(), revision)
                target.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
