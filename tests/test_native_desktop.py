import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NativeDesktopTests(unittest.TestCase):
    def test_connected_profile_must_match_before_any_document_commands(self):
        with patch.dict(sys.modules, {"uno": SimpleNamespace()}):
            utilities = load("native_profile_check", ROOT / "norvi-office/experiments/native-header/uno_utils.py")
        profile = Path("/tmp/native-profile-one")
        actual = (profile / "user").as_uri()
        service = SimpleNamespace(substituteVariables=lambda _value, _required: actual)
        context = SimpleNamespace(ServiceManager=SimpleNamespace(createInstanceWithContext=lambda _name, _context: service))
        utilities.verify_profile(context, profile)
        actual = Path("/tmp/native-profile-two/user").as_uri()
        with self.assertRaises(RuntimeError):
            utilities.verify_profile(context, profile)

    def test_direct_launch_preserves_real_document_arguments_without_a_development_desktop(self):
        with patch.dict(sys.modules, {"uno_utils": SimpleNamespace(connect=None, prop=None, stop_office=None),
                                      "calc_ribbon": SimpleNamespace(prepare=None, preview_package=None, SHORTCUTS=None)}):
            runtime = load("native_launch_test", ROOT / "norvi-office/experiments/desktop/launch.py")
        files = ["https://example.invalid/work%20plan.xlsx", "/tmp/work plan.ods"]
        args = runtime.command("calc", files, Path("/tmp/persistent office profile"), "office-test")
        self.assertEqual(args[-2:], [files[0], str(Path(files[1]).resolve())])
        self.assertIn("-env:UserInstallation=file:///tmp/persistent%20office%20profile", args)
        self.assertIn("--calc", args)
        self.assertNotIn("--headless", args)
        self.assertNotIn("--norestore", args)
        self.assertNotIn("gnome-shell", args)
        self.assertFalse(any("Ember" in arg or "devkit" in arg for arg in args))
        self.assertNotEqual(runtime.service_pipe(Path("/tmp/profile-one")), runtime.service_pipe(Path("/tmp/profile-two")))
        self.assertEqual(runtime.service_pipe(Path("/tmp/profile-one")), runtime.service_pipe(Path("/tmp/profile-one")))

    def test_original_profile_shortcuts_and_documents_survive_install_edit_protection_and_rollback(self):
        self.exercise_install(False)

    def test_failed_activation_restores_the_complete_previous_integration(self):
        self.exercise_install(True)

    def test_preview_changed_during_install_is_preserved_while_new_shortcuts_are_rolled_back(self):
        self.exercise_install("preview-edit")

    def exercise_install(self, fail):
        installer = load("native_installer_test", ROOT / "norvi-office/experiments/desktop/integrate.py")
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            data, desktop = home / "share", home / "Desktop"
            state = data / "norvi-office/native-host"
            original = home / ".config/libreoffice/4/user/registrymodifications.xcu"
            original.parent.mkdir(parents=True)
            original.write_bytes(b"original profile must remain untouched")
            saved = home / "important work.ods"
            saved.write_bytes(b"saved work")
            wrapper = home / ".local/bin/norvi-office"
            wrapper.parent.mkdir(parents=True)
            wrapper.write_bytes(b"previous startup launcher")
            target = data / "applications/libreoffice-calc.desktop"
            target.parent.mkdir(parents=True)
            text = "[Desktop Entry]\nType=Application\nName=Existing Calc\nExec=libreoffice --calc %U\nIcon=libreoffice-calc\n"
            target.write_text(text)
            for app in installer.APPS:
                if app != "calc":
                    (target.parent / f"libreoffice-{app}.desktop").write_text(text.replace("Calc", app.title()).replace("--calc", "--" + app))
            original_entries = {path: path.read_bytes() for path in target.parent.glob("libreoffice-*.desktop")}
            desktop.mkdir(parents=True)
            preview_manifest = data / "norvi-office/visual-preview/shortcuts.json"
            preview_manifest.parent.mkdir(parents=True)
            preview_paths = [home / ".local/bin/norvi-office-preview", home / ".local/bin/norvi-office-preview-remove",
                             *(data / "applications" / f"norvi-office-preview-{app}.desktop" for app in ("calc", "writer")),
                             *(desktop / f"Office Preview - {app}.desktop" for app in ("calc", "writer"))]
            preview_records = []
            for path in preview_paths:
                path.write_bytes(("original preview " + path.name).encode())
                preview_records.append({"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            preview_manifest.write_text(json.dumps({"files": preview_records}))
            edited_preview = desktop / "Office Preview - writer.desktop"
            edited_preview.write_bytes(b"user-customized preview shortcut")
            preview_before = {path: path.read_bytes() for path in preview_paths}
            preview_document = preview_manifest.parent / "saved work.ods"
            preview_document.write_bytes(b"preview document must survive")
            candidate = Path(directory) / "candidate.deb"
            candidate.write_bytes(b"local candidate")
            run = subprocess.run
            output = subprocess.check_output

            def commands(args, **kwargs):
                if args[0] == "dpkg-deb":
                    root = Path(args[-1])
                    for relative, content in (
                        ("usr/share/norvi-office/experimental/desktop/launch.py", "# runtime"),
                        ("usr/lib/x86_64-linux-gnu/norvi-office/libnorvi-office-header.so", "native module"),
                        ("usr/share/norvi-office/experimental/wayland-glass/extension/metadata.json", '{"uuid":"preview"}'),
                        ("usr/share/norvi-office/experimental/wayland-glass/extension/extension.js", "// compositor"),
                    ):
                        path = root / relative
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(content)
                    return subprocess.CompletedProcess(args, 0)
                if fail == "preview-edit" and args[:2] == ["gio", "set"] and args[2] == str(desktop / "Office.desktop"):
                    changed = desktop / "Office Preview - calc.desktop"
                    changed.write_bytes(b"user edit during installation")
                    preview_before[changed] = changed.read_bytes()
                if args[0] in ("gio", "gnome-extensions", "libreoffice", "update-desktop-database") or (args[0] == "desktop-file-validate" and not shutil.which(args[0])):
                    return subprocess.CompletedProcess(args, 0)
                return run(args, **kwargs)

            def outputs(args, **kwargs):
                return str(desktop) + "\n" if args[0] == "xdg-user-dir" else output(args, **kwargs)

            def activation(add):
                if fail is True and add:
                    raise ValueError("activation failed")

            with patch.object(installer, "locations", return_value=(home, data, state)), \
                    patch.object(installer.subprocess, "run", side_effect=commands), \
                    patch.object(installer.subprocess, "check_output", side_effect=outputs), \
                    patch.object(installer, "activation", side_effect=activation):
                if fail:
                    with self.assertRaises(ValueError):
                        installer.install(candidate)
                else:
                    installer.install(candidate)
                    installed = target.read_text()
                    self.assertIn("Name=Office Calc", installed)
                    self.assertIn("--desktop --app calc %U", installed)
                    self.assertEqual({path.name for path in desktop.glob("Office*.desktop") if "Preview" not in path.name},
                                     {"Office.desktop", "Office Calc.desktop", "Office Writer.desktop", "Office Impress.desktop",
                                      "Office Draw.desktop", "Office Base.desktop", "Office Math.desktop"})
                    self.assertFalse((desktop / "Office Preview - calc.desktop").exists())
                    self.assertFalse((data / "applications/norvi-office-preview-calc.desktop").exists())
                    self.assertFalse((data / "applications/norvi-office-preview-writer.desktop").exists())
                    self.assertEqual(edited_preview.read_bytes(), b"user-customized preview shortcut")
                    self.assertTrue((home / ".local/bin/norvi-office-preview").exists())
                    # A newly created launcher at a retired path is user work.
                    retired = desktop / "Office Preview - calc.desktop"
                    retired.write_bytes(b"new shortcut since migration")
                    with self.assertRaises(ValueError):
                        installer.uninstall()
                    self.assertEqual(retired.read_bytes(), b"new shortcut since migration")
                    self.assertIn("Name=Office Calc", target.read_text())
                    retired.unlink()
                    target.write_text(installed + "# user edit\n")
                    with self.assertRaises(ValueError):
                        installer.uninstall()
                    self.assertTrue(state.exists())
                    target.write_text(installed)
                    installer.uninstall()
                    # Re-enrollment can reuse an unchanged retained runtime.
                    installer.install(candidate)
                    installer.uninstall()
            self.assertEqual(original.read_bytes(), b"original profile must remain untouched")
            self.assertEqual(saved.read_bytes(), b"saved work")
            self.assertEqual(target.read_text(), text)
            self.assertEqual({path: path.read_bytes() for path in original_entries}, original_entries)
            self.assertEqual(wrapper.read_bytes(), b"previous startup launcher")
            self.assertFalse(state.exists())
            self.assertEqual({path: path.read_bytes() for path in preview_paths}, preview_before)
            self.assertEqual(preview_document.read_bytes(), b"preview document must survive")
            self.assertEqual(json.loads(preview_manifest.read_text())["files"], preview_records)

    def test_preview_migration_preserves_unmanaged_paths_symlinks_and_unknown_manifests(self):
        installer = load("native_preview_migration_test", ROOT / "norvi-office/experiments/desktop/integrate.py")
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            data, desktop = home / "share", home / "Desktop"
            desktop.mkdir()
            manifest = data / "norvi-office/visual-preview/shortcuts.json"
            manifest.parent.mkdir(parents=True)
            foreign = desktop / "Office Preview - calc.desktop"
            foreign.write_bytes(b"foreign launcher")
            self.assertEqual(installer.preview_shortcuts(home, data, desktop), [])
            manifest.write_text(json.dumps({"files": [{"path": str(foreign), "sha256": installer.sha(foreign)}]}))
            self.assertEqual(installer.preview_shortcuts(home, data, desktop), [])
            shared = [home / ".local/bin/norvi-office-preview", home / ".local/bin/norvi-office-preview-remove",
                      *(data / "applications" / f"norvi-office-preview-{app}.desktop" for app in ("calc", "writer"))]
            for path in shared:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"managed preview")
            records = [{"path": str(path), "sha256": installer.sha(path)} for path in shared]
            manifest.write_text(json.dumps({"files": records}))
            self.assertEqual(set(installer.preview_shortcuts(home, data, desktop)), set(shared[-2:]))
            # A desktop copy is unowned by the older four-file manifest.
            self.assertNotIn(foreign, installer.preview_shortcuts(home, data, desktop))
            altered = shared[-1]
            altered.unlink()
            altered.symlink_to(shared[-2])
            self.assertEqual(installer.preview_shortcuts(home, data, desktop), [shared[-2]])
            records.append(records[-1])
            manifest.write_text(json.dumps({"files": records}))
            self.assertEqual(installer.preview_shortcuts(home, data, desktop), [])
            self.assertEqual(foreign.read_bytes(), b"foreign launcher")
