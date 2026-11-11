"""Drive the actual LibreOffice extension and MCP server in a private GUI session."""
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(sys.argv[1]).resolve()))
from fixtures import connect, stop_office  # noqa: E402
from verify import activate, call, find, menu_items, office_frames, wait  # noqa: E402


def check_gui(package):
    root = Path.cwd()
    assert str(root) == os.environ["NORVI_OFFICE_TEST_DIR"]
    profile = (root / "live-tools-profile").as_uri()
    glass = Path(sys.argv[1]).resolve().parent.parent / "dist/NorviGlass.oxt"
    for extension in (glass, package):
        subprocess.run(["unopkg", "add", "-env:UserInstallation=" + profile, str(extension)], check=True)
    fixtures = json.loads(Path("fixtures.json").read_text())
    pipe = "norvi_live_" + root.name.replace(".", "_")
    office = subprocess.Popen([
        "soffice", "-env:UserInstallation=" + profile, "--nologo", "--norestore",
        f"--accept=pipe,name={pipe};urp;", fixtures["calc"],
    ], start_new_session=True,
        env=dict(os.environ, GTK3_MODULES=str(root / "build/libnorvi-office-header.so")))
    adapter = Path(__file__).resolve().with_name("office_mcp.py")
    with subprocess.Popen([sys.executable, str(adapter)], stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE, text=True) as mcp:
        try:
            check_documents(pipe, fixtures, mcp)
        finally:
            mcp.stdin.close()
            stop_office(office)


def check_documents(pipe, fixtures, mcp):
    context = connect(pipe)
    services = context.ServiceManager
    desktop = services.createInstanceWithContext("com.sun.star.frame.Desktop", context)
    paths = services.createInstanceWithContext("com.sun.star.util.PathSettings", context)
    assert any(path.endswith("/palettes") for path in paths.Palette_internal)
    profile = Path("live-tools-profile")
    assert all(list(profile.rglob(name)) for name in ("Norvi Document.soc", "Norvi Neutral.soc"))
    counter = 0

    def request(method, params):
        nonlocal counter
        counter += 1
        print(json.dumps({"jsonrpc": "2.0", "id": counter, "method": method, "params": params}),
              file=mcp.stdin, flush=True)
        return json.loads(mcp.stdout.readline())["result"]

    def invoke(name, error=False, **arguments):
        result = request("tools/call", {"name": name, "arguments": arguments})
        assert bool(result.get("isError")) == error, result
        text = result["content"][0]["text"]
        return text if error else json.loads(text)

    def command(action, choice):
        def named(prefix):
            return wait(lambda: next((item for window in office_frames() for item in menu_items(window)
                                      if item.get_name().lower().startswith(prefix)), None),
                        "Could not find menu item: " + prefix)

        call("Place")
        activate("Main menu")
        assert named("tools").get_action_iface().do_action(0)
        assert named("add-ons").get_action_iface().do_action(0)
        assert named(action).get_action_iface().do_action(0)
        def prompt():
            return next((window for window in office_frames() if window.get_name() == "Norvi Document Tools"), None)

        window = wait(prompt, "The extension dialog did not open")
        if choice == "Yes":
            call("Capture", "live-tools-share.png")
        button = find(window, choice)
        assert button is not None and button.get_action_iface().do_action(0), choice
        wait(lambda: prompt() is None, "The extension dialog did not close")


    assert request("initialize", {"protocolVersion": "2025-06-18"})["serverInfo"]["name"] == "norvi-office"
    assert len(request("tools/list", {})["tools"]) == 5
    calc = wait(desktop.getCurrentComponent, "Calc did not open")
    sheet = calc.Sheets.getByIndex(0)
    target = {"sheet": sheet.Name, "range": "D6"}
    invoke("document_info", error=True)
    command("share document", "No")
    invoke("document_info", error=True)
    command("share document", "Yes")
    grant = invoke("document_info")
    assert grant["kind"] == "calc"
    target["document"] = grant["document"]
    expected = invoke("read_cells", **target)["revision"]
    invoke("write_cells", **target, expected=expected, formula="=WEBSERVICE(A1)", error=True)
    invoke("write_cells", **target, expected=expected, values=[["=SUM(D2:D5)"]])
    assert sheet.getCellRangeByName("D6").String == "=SUM(D2:D5)"
    assert sheet.getCellRangeByName("D6").Value == 0
    invoke("write_cells", **target, expected=expected, formula="=SUM(D2:D5)", error=True)
    undo = calc.getUndoManager()
    title = undo.getCurrentUndoActionTitle()
    undo.undo()
    wait(lambda: sheet.getCellRangeByName("D6").String == "",
         f"Calc Undo did not restore the original cell (undo action: {title})", seconds=3)
    invoke("write_cells", **target, expected=expected, formula="=SUM(D2:D5)")
    assert sheet.getCellRangeByName("D6").Value == 54
    assert calc.isModified()
    batch = {**target, "range": "D7:E7"}
    before = invoke("read_cells", **batch)["revision"]
    invoke("write_cells", **batch, expected=before, values=[[12, "Test note"]])
    assert sheet.getCellRangeByName("D7:E7").getDataArray() == ((12, "Test note"),)
    undo.undo()
    assert sheet.getCellRangeByName("D7:E7").getDataArray() == (("", ""),)
    print("Calc: explicit share, read, literal and formula edits, conflict rejection and Undo", flush=True)

    writer = desktop.loadComponentFromURL(Path(fixtures["writer"]).as_uri(), "_blank", 0, ())
    assert writer
    # Opening a second document never transfers the grant.
    assert invoke("document_info")["document"] == grant["document"]
    calc.setModified(False)
    calc.close(True)
    command("share document", "Yes")
    document = invoke("document_info")["document"]
    invoke("read_cells", **target, error=True)
    assert "Project Ember" in invoke("read_writer", document=document)["text"]
    invoke("replace_writer_text", document=document, old="missing fragment", new="Revised", error=True)
    invoke("replace_writer_text", document=document, old="Project Ember", new="Project Aurora")
    assert writer.Text.String.startswith("Project Aurora")
    writer.getUndoManager().undo()
    assert writer.Text.String.startswith("Project Ember")
    command("stop document", "OK")
    invoke("document_info", error=True)
    command("share document", "Yes")
    writer.setModified(False)
    writer.close(True)
    invoke("document_info", error=True)
    print("Writer: exact replacement, Undo, revocation and close isolation", flush=True)


if __name__ == "__main__":
    check_gui(Path(sys.argv[2]).resolve())
