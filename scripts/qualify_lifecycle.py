#!/usr/bin/env python3
"""Exercise dpkg install/upgrade/purge in a disposable, unprivileged filesystem."""
from pathlib import Path
import subprocess
import sys
import tempfile

package = Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory(prefix='office-dpkg-') as temporary:
    work = Path(temporary)
    root = work / 'root'
    root.mkdir()
    admin = root / 'var/lib/dpkg'
    admin.mkdir(parents=True)
    (admin / 'status').touch()

    def dpkg(*args):
        subprocess.run(['fakeroot', 'dpkg', '--root=' + str(root), '--admindir=' + str(admin),
                        '--log=' + str(work / 'dpkg.log'), '--force-not-root', '--force-depends', *args],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    dpkg('--install', str(package))
    assert (root / 'usr/bin/norvi-office').exists()
    fixture = work / 'upgrade'
    subprocess.run(['dpkg-deb', '-R', str(package), str(fixture)], check=True, capture_output=True)
    control = fixture / 'DEBIAN/control'
    old = next(line.split(': ', 1)[1] for line in control.read_text().splitlines() if line.startswith('Version:'))
    new = old + '+upgradefixture1'
    control.write_text(control.read_text().replace('Version: ' + old, 'Version: ' + new))
    upgrade = work / 'upgrade-fixture.deb'
    subprocess.run(['dpkg-deb', '--root-owner-group', '--build', str(fixture), str(upgrade)],
                   check=True, capture_output=True)
    dpkg('--install', str(upgrade))
    assert 'Version: ' + new in (admin / 'status').read_text()
    dpkg('--purge', 'norvi-office')
    assert not (root / 'usr/bin/norvi-office').exists()
    assert not (root / 'usr/share/norvi-office').exists()
print('Isolated dpkg install, upgrade and purge passed')
