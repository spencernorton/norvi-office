#!/usr/bin/env bash
# Create an unregistered, empty embedded database in the private fixture directory.
set -euo pipefail
directory="$1"
pipe="norvi_base_${directory##*.}"
soffice "-env:UserInstallation=file://$directory/base-fixture-profile" --headless --norestore \
    "--accept=pipe,name=$pipe;urp;" >"$directory/base-fixture.log" 2>&1 &
office=$!
trap 'kill "$office" 2>/dev/null || true' EXIT
/usr/bin/python3 - "$pipe" "$directory" <<'PY'
import sys
import time

import uno

local = uno.getComponentContext()
resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
for _ in range(80):
    try:
        context = resolver.resolve(f"uno:pipe,name={sys.argv[1]};urp;StarOffice.ComponentContext")
        break
    except Exception:
        time.sleep(0.05)
else:
    sys.exit("Unable to open the local UNO fixture pipe")

manager = context.ServiceManager
document = manager.createInstanceWithContext("com.sun.star.sdb.OfficeDatabaseDocument", context)
document.initNew()
document.DataSource.URL = "sdbc:embedded:hsqldb"
document.storeAsURL(uno.systemPathToFileUrl(sys.argv[2] + "/Norvi Sample.odb"), ())
document.close(True)
manager.createInstanceWithContext("com.sun.star.frame.Desktop", context).terminate()
PY
wait "$office"
