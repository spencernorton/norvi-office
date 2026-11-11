"""Small UNO connection helpers shared by desktop and qualification tools."""
import os
import signal
import time
from pathlib import Path
from urllib.parse import unquote, urlsplit

import uno


def prop(name, value):
    item = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    item.Name, item.Value = name, value
    return item


def verify_profile(context, profile):
    substitution = context.ServiceManager.createInstanceWithContext("com.sun.star.util.PathSubstitution", context)
    actual = substitution.substituteVariables("$(user)", True)
    if urlsplit(actual).scheme != "file" or Path(unquote(urlsplit(actual).path)).resolve() != profile.resolve() / "user":
        raise RuntimeError("Office service belongs to another profile; no commands were permitted")


def connect(pipe, profile=None):
    context = uno.getComponentContext()
    resolver = context.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", context)
    for _ in range(150):
        try:
            remote = resolver.resolve(f"uno:pipe,name={pipe};urp;StarOffice.ComponentContext")
        except Exception:
            time.sleep(.1)
            continue
        if profile is not None:
            verify_profile(remote, profile)
        return remote
    raise RuntimeError("The Office document service did not initialize")


def stop_office(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    process.wait(timeout=10)
