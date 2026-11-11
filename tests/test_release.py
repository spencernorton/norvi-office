import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
STARTUP = ROOT / 'norvi-office/experiments/startup'
spec = importlib.util.spec_from_file_location('integration', STARTUP / 'integrate.py')
integration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(integration)


class ReleaseTests(unittest.TestCase):
    def test_official_engine_security_updates_are_not_held(self):
        control = (ROOT / 'packaging/control').read_text()
        dependencies = next(line for line in control.splitlines() if line.startswith('Depends:'))
        self.assertNotIn('<<', dependencies)
        self.assertNotIn('(=', dependencies)
        self.assertNotIn('Replaces:', control)
        self.assertNotIn('Conflicts:', control)
        for app in ('writer', 'calc', 'impress', 'draw', 'base', 'math'):
            self.assertIn('libreoffice-' + app, dependencies)
        self.assertFalse(json.loads((ROOT / 'compatibility.json').read_text())['engine_pins'])

    @unittest.skipUnless(shutil.which('desktop-file-validate'), 'Linux desktop validation required')
    def test_package_updates_use_shared_runtime_and_removal_falls_back(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            home = directory / 'home'
            home.mkdir()
            runtime = directory / 'package/startup'
            shutil.copytree(STARTUP, runtime, ignore=shutil.ignore_patterns('__pycache__'))
            (runtime / 'package-mode').write_text('managed by APT\n')
            program = runtime / 'launch.py'
            program.write_text('print("version one")\n')
            environment = {**os.environ, 'HOME': str(home), 'XDG_DATA_HOME': str(home / 'share')}
            with patch.dict(os.environ, environment), patch.object(integration, 'SOURCE', runtime):
                integration.install()
                launcher = home / '.local/bin/norvi-office'
                self.assertEqual(subprocess.check_output([str(launcher)], env=environment, text=True).strip(), 'version one')
                self.assertFalse((home / 'share/norvi-office/startup/launch.py').exists())
                program.write_text('print("version two")\n')
                self.assertEqual(subprocess.check_output([str(launcher)], env=environment, text=True).strip(), 'version two')
                # Simulate package removal while a user's module shortcuts remain.
                program.unlink()
                tools = directory / 'tools'
                tools.mkdir()
                fallback = tools / 'libreoffice'
                fallback.write_text('#!/usr/bin/python3\nimport sys,json\nprint(json.dumps(sys.argv[1:]))\n')
                fallback.chmod(0o755)
                env = {**environment, 'PATH': str(tools) + ':' + os.environ['PATH']}
                args = ['--desktop', '--app', 'calc', 'https://example.invalid/a%20b.xlsx', '/tmp/a b.ods']
                reached = json.loads(subprocess.check_output([str(launcher), *args], env=env, text=True))
                self.assertEqual(reached, ['--calc', *args[3:]])
                subprocess.run([str(home / '.local/bin/norvi-office-uninstall')], env=environment, check=True,
                               stdout=subprocess.DEVNULL)
                self.assertFalse(launcher.exists())
                self.assertFalse((home / 'share/norvi-office/startup').exists())

    def test_unknown_native_build_is_not_enabled(self):
        contract = json.loads((ROOT / 'compatibility.json').read_text())['experimental_native_adapter']
        self.assertFalse(contract['enabled_by_default'])
        self.assertEqual(contract['libreoffice_versions'], ['26.2.6.3'])
        self.assertIn('unmodified upstream', contract['unknown_version_behavior'])


if __name__ == '__main__':
    unittest.main()
