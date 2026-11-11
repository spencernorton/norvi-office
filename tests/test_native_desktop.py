import importlib.util
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
        self.assertNotIn("gnome-shell", args)
        self.assertFalse(any("Ember" in arg or "devkit" in arg for arg in args))
        self.assertNotEqual(runtime.service_pipe(Path("/tmp/profile-one")), runtime.service_pipe(Path("/tmp/profile-two")))
        self.assertEqual(runtime.service_pipe(Path("/tmp/profile-one")), runtime.service_pipe(Path("/tmp/profile-one")))

    @unittest.skipUnless(shutil.which("desktop-file-validate"), "Linux desktop required")
    def test_original_profile_shortcuts_and_documents_survive_install_edit_protection_and_rollback(self):
        self.exercise_install(False)

    @unittest.skipUnless(shutil.which("desktop-file-validate"), "Linux desktop required")
    def test_failed_activation_restores_the_complete_previous_integration(self):
        self.exercise_install(True)

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
                if args[0] in ("gio", "gnome-extensions"):
                    return subprocess.CompletedProcess(args, 0)
                return run(args, **kwargs)

            def outputs(args, **kwargs):
                return str(desktop) + "\n" if args[0] == "xdg-user-dir" else output(args, **kwargs)

            def activation(add):
                if fail and add:
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
                    self.assertTrue((desktop / "Office Calc.desktop").exists())
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
            self.assertEqual(wrapper.read_bytes(), b"previous startup launcher")
            self.assertFalse(state.exists())
