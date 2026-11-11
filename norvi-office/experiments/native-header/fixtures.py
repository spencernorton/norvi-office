"""Create fictional suite documents in the disposable preview directory."""
from pathlib import Path
import os
import signal
import subprocess
import sys
import time

import uno


def stop_office(process):
    # The soffice launcher can outlive or exit before its soffice.bin child.
    # Every caller creates a dedicated process group for this private client.
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    process.wait(timeout=10)


def prop(name, value):
    item = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    item.Name, item.Value = name, value
    return item


def connect(pipe):
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    for _ in range(150):
        try:
            return resolver.resolve(f"uno:pipe,name={pipe};urp;StarOffice.ComponentContext")
        except Exception:
            time.sleep(0.1)
    raise RuntimeError("Fixture UNO pipe did not open")


def make(root):
    pipe = "norvi_fixture_" + root.name.replace(".", "_")
    log = (root / "fixtures.log").open("w")
    office = subprocess.Popen([
        "soffice", f"-env:UserInstallation={(root / 'fixture-profile').as_uri()}",
        "--headless", "--norestore", f"--accept=pipe,name={pipe};urp;",
    ], stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        ctx = connect(pipe)
        manager = ctx.ServiceManager
        desktop = manager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        outputs = {}
        for app, factory, filename in (
            ("writer", "swriter", "Ember Brief.odt"),
            ("calc", "scalc", "Ember Plan.ods"),
            ("impress", "simpress", "Ember Review.odp"),
            ("draw", "sdraw", "Ember Layout.odg"),
            ("math", "smath", "Ember Formula.odf"),
        ):
            doc = desktop.loadComponentFromURL("private:factory/" + factory, "_blank", 0, (prop("Hidden", True),))
            if app == "writer":
                doc.Text.String = (
                    "Project Ember\nA quieter workspace for focused work\n\n"
                    "Design review\nThe native header keeps document actions, settings and window controls together. "
                    "The ribbon remains contextual and the page stays opaque.\n\n"
                    "This fictional brief is used only to demonstrate the interface."
                )
                cursor = doc.Text.createTextCursor()
                cursor.gotoStart(False)
                cursor.gotoEndOfParagraph(True)
                cursor.CharHeight = 28
                cursor.CharWeight = 150
                cursor.CharColor = 0x7460D4
            elif app == "calc":
                sheet = doc.Sheets.getByIndex(0)
                sheet.Name = "Ember plan"
                values = (("Work item", "Owner", "Stage", "Hours"),
                          ("Header", "Alex", "Review", 12),
                          ("Ribbon", "Sam", "Build", 18),
                          ("Menus", "Taylor", "Verify", 10),
                          ("Accessibility", "Jordan", "Verify", 14))
                sheet.getCellRangeByName("A1:D5").setDataArray(values)
                heading = sheet.getCellRangeByName("A1:D1")
                heading.CellBackColor, heading.CharColor, heading.CharWeight = 0x7460D4, 0xFFFFFF, 150
                for i, width in enumerate((5300, 3500, 3500, 2600)):
                    sheet.Columns.getByIndex(i).Width = width
                if os.environ.get("NORVI_OFFICE_CALC_RIBBON") == "1":
                    sheet.getCellRangeByName("E1:G5").setDataArray((
                        ("Due date", "Budget", "Variance"), ("Nov 12", "$960", "$0"),
                        ("Nov 14", "$1,440", "$120"), ("Nov 17", "$800", "$0"),
                        ("Nov 20", "$1,120", "−$80"),
                    ))
                    heading = sheet.getCellRangeByName("A1:G1")
                    heading.CellBackColor, heading.CharColor, heading.CharWeight = 0xE8E0F8, 0x24212B, 150
                    for i, width in enumerate((4500, 3200, 3200, 2500, 2400, 2400, 2400)):
                        sheet.Columns.getByIndex(i).Width = width
                    sheet.getCellRangeByName("A1:L27").Rows.Height = 640
            elif app in ("impress", "draw"):
                page = doc.DrawPages.getByIndex(0)
                shape = doc.createInstance("com.sun.star.drawing.TextShape")
                shape.Position = uno.createUnoStruct("com.sun.star.awt.Point", 2500, 2500)
                shape.Size = uno.createUnoStruct("com.sun.star.awt.Size", 20000, 8000)
                page.add(shape)
                shape.String = "Project Ember\nA continuous workspace\n\nNative header · contextual tools · opaque work area"
                shape.CharHeight, shape.CharColor = 28, 0x7460D4
            else:
                doc.Formula = "sum from {i = 1} to n i = {n (n + 1)} over 2"
            doc.DocumentProperties.Author = "Fictional example"
            doc.DocumentProperties.ModifiedBy = "Fictional example"
            path = root / filename
            doc.storeAsURL(path.as_uri(), ())
            doc.close(True)
            outputs[app] = str(path)
        base = manager.createInstanceWithContext("com.sun.star.sdb.OfficeDatabaseDocument", ctx)
        base.initNew()
        base.DataSource.URL = "sdbc:embedded:hsqldb"
        path = root / "Ember Records.odb"
        base.storeAsURL(path.as_uri(), ())
        base.close(True)
        outputs["base"] = str(path)
        desktop.terminate()
        office.wait(timeout=15)
        return outputs
    finally:
        stop_office(office)
        log.close()


if __name__ == "__main__":
    import json
    root = Path(sys.argv[1]).resolve()
    (root / "fixtures.json").write_text(json.dumps(make(root), indent=2) + "\n")
