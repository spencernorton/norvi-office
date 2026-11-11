"""Check file filters and password protection on the installed LibreOffice build."""
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
from time import monotonic, sleep
from zipfile import BadZipFile, ZipFile

import uno
import unohelper
from com.sun.star.lang import IllegalArgumentException
from com.sun.star.task import XInteractionHandler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "native-header"))
from fixtures import connect, prop, stop_office  # noqa: E402


class AbortPrompts(unohelper.Base, XInteractionHandler):
    def handle(self, request):
        for choice in request.getContinuations():
            if hasattr(choice, "queryInterface") and choice.queryInterface(
                    uno.getTypeByName("com.sun.star.task.XInteractionAbort")):
                choice.select()
                return


def qualify(directory):
    pipe = "norvi_formats_" + secrets.token_hex(12)
    password = secrets.token_urlsafe(24)
    profile = (directory / "profile").as_uri()
    client = subprocess.Popen([
        "soffice", "-env:UserInstallation=" + profile, "--headless", "--norestore",
        f"--accept=pipe,name={pipe};urp;",
    ], start_new_session=True)
    try:
        context = connect(pipe)
        manager = context.ServiceManager
        desktop = manager.createInstanceWithContext("com.sun.star.frame.Desktop", context)
        provider = manager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", context)
        recovery = provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationUpdateAccess",
            (prop("nodepath", "/org.openoffice.Office.Recovery/AutoSave"),))
        initial = (recovery.Enabled, recovery.UserAutoSaveEnabled, recovery.TimeIntervall)
        recovery.Enabled = True
        recovery.UserAutoSaveEnabled = True
        recovery.TimeIntervall = 5
        recovery.commitChanges()
        reread = provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationAccess",
            (prop("nodepath", "/org.openoffice.Office.Recovery/AutoSave"),))
        assert (reread.Enabled, reread.UserAutoSaveEnabled, reread.TimeIntervall) == (True, True, 5)
        print("Recovery settings read and changed in private profile. Fresh values:", initial, flush=True)
        recovery.UserAutoSaveEnabled = False
        recovery.commitChanges()

        for factory, formats in (
            ("swriter", (("odt", "writer8"), ("docx", "Office Open XML Text"))),
            ("scalc", (("ods", "calc8"), ("xlsx", "Calc MS Excel 2007 XML"))),
            ("simpress", (("odp", "impress8"), ("pptx", "Impress MS PowerPoint 2007 XML"))),
            ("sdraw", (("odg", "draw8"),)),
            ("smath", (("odf", "math8"),)),
        ):
            doc = desktop.loadComponentFromURL(f"private:factory/{factory}", "_blank", 0, (prop("Hidden", True),))
            marker = "Fictional document " + secrets.token_hex(8)
            if factory == "swriter":
                doc.Text.String = marker
                def check(reopened):
                    return reopened.Text.String == marker
            elif factory == "scalc":
                sheet = doc.Sheets.getByIndex(0)
                sheet.getCellRangeByName("A1:B1").setDataArray(((marker, 7),))
                sheet.getCellRangeByName("C1").setFormula("=B1*3")
                def check(reopened):
                    values = reopened.Sheets.getByIndex(0)
                    return (values.getCellRangeByName("A1").String == marker and
                            values.getCellRangeByName("C1").Formula == "=B1*3" and
                            values.getCellRangeByName("C1").Value == 21)
            elif factory == "smath":
                doc.Formula = "sum from {i=1} to 4 i"
                def check(reopened):
                    return reopened.Formula == doc.Formula
            else:
                page = doc.DrawPages.getByIndex(0)
                shape = doc.createInstance("com.sun.star.drawing.TextShape")
                page.add(shape)
                shape.String = marker
                def check(reopened):
                    return any(getattr(shape, "String", "") == marker
                               for shape in reopened.DrawPages.getByIndex(0))
            for suffix, filter_name in formats:
                for encrypted in (False, True):
                    if encrypted and factory not in ("swriter", "scalc"):
                        continue
                    path = directory / f"{factory}-{encrypted}.{suffix}"
                    args = [prop("FilterName", filter_name)]
                    if encrypted:
                        args.append(prop("Password", password))
                    doc.storeToURL(path.as_uri(), tuple(args))
                    if encrypted:
                        if suffix in ("odt", "ods"):
                            with ZipFile(path) as package:
                                assert b"encryption-data" in package.read("META-INF/manifest.xml")
                                assert all(marker.encode() not in package.read(name) for name in package.namelist())
                        else:
                            assert path.read_bytes().startswith(bytes.fromhex("d0cf11e0a1b11ae1"))
                        try:
                            refused = desktop.loadComponentFromURL(path.as_uri(), "_blank", 0, (
                                prop("Hidden", True), prop("Password", "wrong"),
                                prop("InteractionHandler", AbortPrompts()),
                            ))
                        except IllegalArgumentException as error:
                            assert "type detection aborted" in str(error)
                            refused = None
                        assert refused is None, f"{suffix} opened with an incorrect password"
                    arguments = [prop("Hidden", True)]
                    if encrypted:
                        arguments.append(prop("Password", password))
                    reopened = desktop.loadComponentFromURL(path.as_uri(), "_blank", 0, tuple(arguments))
                    assert reopened and check(reopened), f"{suffix} round trip lost test content"
                    reopened.close(True)
                    print(f"{suffix}: content round trip" + (" and password rejection" if encrypted else ""), flush=True)
            pdf = directory / f"{factory}.pdf"
            doc.storeToURL(pdf.as_uri(), (prop("FilterName", f"{factory[1:]}_pdf_Export"),))
            assert pdf.read_bytes().startswith(b"%PDF-")
            doc.close(True)
        print("Writer, Calc, Impress, Draw and Math: PDF export signatures verified", flush=True)
        base = manager.createInstanceWithContext("com.sun.star.sdb.OfficeDatabaseDocument", context)
        base.initNew()
        base.DataSource.URL = "sdbc:embedded:hsqldb"
        database = directory / "fictional.odb"
        base.storeAsURL(database.as_uri(), ())
        base.close(True)
        reopened = desktop.loadComponentFromURL(database.as_uri(), "_blank", 0, (prop("Hidden", True),))
        assert reopened is not None and reopened.DataSource.URL == "sdbc:embedded:hsqldb"
        reopened.close(True)
        print("odb: embedded database document round trip", flush=True)
    finally:
        stop_office(client)


def qualify_autosave(directory):
    # LibreOffice disables recovery and automatic saves with --headless or --norestore.
    user = directory / "profile/user"
    user.mkdir(parents=True)
    (user / "registrymodifications.xcu").write_text(
        '<oor:items xmlns:oor="http://openoffice.org/2001/registry">'
        '<item oor:path="/org.openoffice.Office.Recovery/AutoSave">'
        '<prop oor:name="Enabled" oor:op="fuse"><value>true</value></prop>'
        '<prop oor:name="UserAutoSaveEnabled" oor:op="fuse"><value>true</value></prop>'
        '<prop oor:name="TimeIntervall" oor:op="fuse"><value>1</value></prop>'
        '</item></oor:items>'
    )
    pipe = "norvi_autosave_" + secrets.token_hex(12)
    office = subprocess.Popen([
        "soffice", "-env:UserInstallation=" + user.parent.as_uri(), "--nologo",
        f"--accept=pipe,name={pipe};urp;",
    ], start_new_session=True)
    try:
        context = connect(pipe)
        desktop = context.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", context)
        doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, ())
        path = directory / "fixture.odt"
        doc.Text.String = "Fictional original"
        doc.storeAsURL(path.as_uri(), (prop("FilterName", "writer8"),))
        doc.Text.String = "Fictional autosaved revision"
        until = monotonic() + 100
        while monotonic() < until:
            sleep(1)
            try:
                with ZipFile(path) as package:
                    if b"Fictional autosaved revision" in package.read("content.xml"):
                        print("Writer: automatic saving wrote the updated ODT to disk.", flush=True)
                        return
            except (OSError, BadZipFile):
                pass
        raise AssertionError("Automatic save did not update the GUI fixture within 100 seconds.")
    finally:
        stop_office(office)


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="norvi-formats-") as temp:
        action = qualify_autosave if sys.argv[1:] == ["--autosave"] else qualify
        action(Path(temp))
