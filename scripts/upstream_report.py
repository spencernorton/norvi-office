#!/usr/bin/env python3
"""Record installed official dependency versions without changing system state."""
import json
from pathlib import Path
import re
import subprocess
import sys

root = Path(__file__).resolve().parent.parent
contract = json.loads((root / 'compatibility.json').read_text())
result = subprocess.check_output(['libreoffice', '--version'], text=True).strip()
match = re.search(r'LibreOffice\s+(\d+(?:\.\d+){3})', result)
version = match[1] if match else None
packages = subprocess.check_output(['dpkg-query', '-W', '-f=${Package} ${Version}\n',
                                    'libreoffice-core', 'libreoffice-gtk3', 'python3-uno'], text=True).splitlines()
report = {'engine': result, 'packages': packages, 'engine_pins': False,
          'native_adapter_qualified': version in contract['experimental_native_adapter']['libreoffice_versions'],
          'native_adapter_enabled_by_default': False,
          'unknown_version_fallback': 'normal unmodified LibreOffice UI'}
print(json.dumps(report, indent=2))
if len(sys.argv) > 1:
    Path(sys.argv[1]).write_text(json.dumps(report, indent=2) + '\n')
