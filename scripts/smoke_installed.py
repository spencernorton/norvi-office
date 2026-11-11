#!/usr/bin/env python3
"""Open real Writer and Calc through the extracted candidate, outside the checkout."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

import gi
gi.require_version('Atspi', '2.0')
from gi.repository import Atspi  # noqa: E402

payload = Path(sys.argv[1]).resolve()
program = payload / 'usr/bin/norvi-office'
source = Path(sys.argv[2]).resolve()
spec = importlib.util.spec_from_file_location('installed_fixtures', source)
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
work = Path(tempfile.mkdtemp(prefix='office-installed-'))
try:
    files = fixtures.make(work)
except Exception:
    log = work / 'fixtures.log'
    if log.exists():
        print(log.read_text()[-4000:], file=sys.stderr)
    raise
Atspi.set_timeout(150, 150)
for app in ('writer', 'calc'):
    profile = work / ('profile-' + app)
    expected = ('-env:UserInstallation=' + profile.as_uri()).encode()
    try:
        subprocess.run(['unopkg', 'add', '-env:UserInstallation=' + profile.as_uri(),
                        str(payload / 'usr/share/norvi-office/extensions/NorviGlass.oxt')],
                       check=True, stdout=subprocess.DEVNULL)
        started = time.monotonic()
        result = subprocess.run([str(program), '--profile', str(profile), '--app', app, files[app]], timeout=12)
        assert result.returncode == 0
        assert time.monotonic() - started < 7.5, 'Readiness fell back to timeout'
        until = time.monotonic() + 5
        visible = []
        while time.monotonic() < until:
            desktop = Atspi.get_desktop(0)
            visible = []
            for index in range(desktop.get_child_count()):
                item = desktop.get_child_at_index(index)
                if item is not None and item.get_name() == 'soffice':
                    for child in range(item.get_child_count()):
                        window = item.get_child_at_index(child)
                        if window and window.get_role() == Atspi.Role.FRAME:
                            if window.get_state_set().contains(Atspi.StateType.SHOWING):
                                visible.append(window.get_name() or '')
            if any(Path(files[app]).stem in title for title in visible):
                break
            time.sleep(0.05)
        assert any(Path(files[app]).stem in title for title in visible), visible
        print('Installed ' + app + ' startup passed', flush=True)
    finally:
        groups = set()
        for proc in Path('/proc').glob('[0-9]*'):
            try:
                if (proc / 'comm').read_text().strip() in ('soffice.bin', 'oosplash'):
                    if expected in (proc / 'cmdline').read_bytes().split(b'\0'):
                        groups.add(os.getpgid(int(proc.name)))
            except OSError:
                pass
        for group in groups:
            try:
                os.killpg(group, signal.SIGTERM)
            except ProcessLookupError:
                pass
        time.sleep(0.2)
        for group in groups:
            try:
                os.killpg(group, signal.SIGKILL)
            except ProcessLookupError:
                pass
print(json.dumps({'installed_writer_calc': 'passed', 'payload': str(payload)}))
