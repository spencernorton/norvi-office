"""Prepare only the newly created, isolated visual preview profile."""
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent.parent / "native-header"
sys.path.insert(0, str(root))
from fixtures import make, connect, stop_office  # noqa: E402
from calc_ribbon import prepare, preview_package, SHORTCUTS  # noqa: E402

directory = Path.cwd()
app = os.environ["NORVI_OFFICE_PREVIEW_APP"]
profile = directory / ("profile-" + app)
if not directory.name.startswith("capture.preview-") or profile.exists():
    raise ValueError("The visual preview must use a fresh separate profile")
make(directory)
package = Path(os.environ["NORVI_OFFICE_PREVIEW_OXT"])
overlay = directory / "NorviRibbon.oxt"
preview_package(package, overlay, app)
package = overlay
subprocess.run(["unopkg", "add", "-env:UserInstallation=" + profile.as_uri(), str(package)], check=True)
if app == "calc":
    prepare(profile)
else:
    pipe = "norvi_writer_setup_" + directory.name.replace(".", "_")
    with (directory / "writer-setup.log").open("w") as log:
        office = subprocess.Popen([
            "soffice", "-env:UserInstallation=" + profile.as_uri(), "--headless", "--norestore",
            "--accept=pipe,name=" + pipe + ";urp;",
        ], stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            context = connect(pipe)
            supplier = context.getValueByName("/singletons/com.sun.star.ui.theModuleUIConfigurationManagerSupplier")
            manager = supplier.getUIConfigurationManager("com.sun.star.text.TextDocument")
            settings = manager.getSettings(SHORTCUTS, True)
            for index in reversed(range(settings.getCount())):
                settings.removeByIndex(index)
            manager.replaceSettings(SHORTCUTS, settings)
            manager.store()
            context.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", context).terminate()
        finally:
            stop_office(office)
