"""Set up the fictional sheet and confirm the native command broker is ready."""
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "native-header"))
from fixtures import connect  # noqa: E402
from actions import Status  # noqa: E402
import uno  # noqa: E402


def sidebar_visible(context, owner):
    class SidebarStatus(Status):
        visible = None

        def statusChanged(self, event):
            self.visible = event.State if event.IsEnabled else None

    transformer = context.ServiceManager.createInstanceWithContext("com.sun.star.util.URLTransformer", context)
    url = uno.createUnoStruct("com.sun.star.util.URL")
    url.Complete = ".uno:Sidebar"
    _, url = transformer.parseStrict(url)
    dispatch = owner.queryDispatch(url, "", 0)
    listener = SidebarStatus()
    dispatch.addStatusListener(listener, url)
    dispatch.removeStatusListener(listener, url)
    return listener.visible

context = connect(sys.argv[1])
desktop = context.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", context)
until = time.monotonic() + 20
while time.monotonic() < until:
    doc = desktop.getCurrentComponent()
    if doc is not None and (Path.cwd() / "actions-ready.json").exists():
        break
    time.sleep(0.1)
else:
    raise RuntimeError("The preview document and command broker did not initialize")
frame = doc.getCurrentController().getFrame()
dispatcher = context.ServiceManager.createInstanceWithContext("com.sun.star.frame.DispatchHelper", context)
state = None
until = time.monotonic() + 10
while time.monotonic() < until and not isinstance(state, bool):
    state = sidebar_visible(context, frame)
    time.sleep(0.1)
if not isinstance(state, bool):
    raise RuntimeError("Sidebar state did not initialize")
if state is True:
    dispatcher.executeDispatch(frame, ".uno:Sidebar", "", 0, ())
if sys.argv[2] == "calc":
    sheet = doc.Sheets.getByIndex(0)
    data = (("Work item", "Owner", "Stage", "Hours", "Due date", "Budget", "Variance"),
            ("Header", "Alex", "Review", 12, "Nov 12", 960, 0),
            ("Ribbon", "Sam", "Build", 18, "Nov 14", 1440, 120),
            ("Menus", "Taylor", "Verify", 10, "Nov 17", 800, 0),
            ("Accessibility", "Jordan", "Review", 14, "Nov 20", 1120, -80))
    sheet.getCellRangeByName("A1:G5").setDataArray(data)
    area = sheet.getCellRangeByName("A1:L40")
    area.CharFontName, area.CharHeight = "Liberation Sans", 11
    heading = sheet.getCellRangeByName("A1:G1")
    # A restrained paper tint derived from the existing lavender token.
    lavender = (0xC1, 0xAA, 0xF3)
    tint = [round(255 * .7 + channel * .3) for channel in lavender]
    heading.CellBackColor = tint[0] * 65536 + tint[1] * 256 + tint[2]
    heading.CharColor, heading.CharWeight = 0x272727, 150
    for index in range(12):
        sheet.Columns.getByIndex(index).Width = 4400 if index == 0 else 2960
    for index in range(40):
        sheet.Rows.getByIndex(index).Height = 660
    controller = doc.getCurrentController()
    if controller.getPropertySetInfo().hasPropertyByName("ShowPageBreaks"):
        controller.setPropertyValue("ShowPageBreaks", False)
    locale = uno.createUnoStruct("com.sun.star.lang.Locale")
    locale.Language, locale.Country = "en", "US"
    formats = doc.NumberFormats
    currency = uno.getConstantByName("com.sun.star.util.NumberFormat.CURRENCY")
    base = formats.queryKeys(currency, locale, True)[0]
    code = formats.generateFormat(base, locale, True, False, 0, 1)
    key = formats.queryKey(code, locale, False)
    if key < 0:
        key = formats.addNew(code, locale)
    sheet.getCellRangeByName("F2:G5").NumberFormat = key
    controller.select(sheet.getCellRangeByName("D2"))
    doc.store()
else:
    # Construct actual paragraphs so the title's direct formatting cannot
    # bleed into an entire sample document made from soft line breaks.
    paragraphs = (
        ("Title", "Project Ember", 26, True, 0x7460D4),
        ("Subtitle", "A calmer workspace for focused work", 15, False, 0x272727),
        ("Heading 1", "Design review", 16, True, 0x272727),
        ("Text body", "This brief brings the proposal, decisions and next steps together in one place. "
         "Use it to keep the team aligned as the project moves forward.", 12, False, 0x272727),
        ("Heading 1", "Priorities", 16, True, 0x272727),
        ("Text body", "Keep the work clear, make common actions easy to reach, and use color with restraint. "
         "A consistent visual language helps people focus on the content.", 12, False, 0x272727),
        ("Heading 1", "Next steps", 16, True, 0x272727),
        ("Text body", "Review the draft with the team, confirm the next milestone, and record decisions here.",
         12, False, 0x272727),
    )
    doc.Text.String = ""
    cursor = doc.Text.createTextCursor()
    paragraph_break = uno.getConstantByName("com.sun.star.text.ControlCharacter.PARAGRAPH_BREAK")
    body = None
    for index, (style, text, size, bold, color) in enumerate(paragraphs):
        if index:
            doc.Text.insertControlCharacter(cursor, paragraph_break, False)
            cursor.gotoEnd(False)
        cursor.ParaStyleName = style
        cursor.CharFontName, cursor.CharHeight = "Liberation Sans", size
        cursor.CharWeight, cursor.CharColor = (150 if bold else 100), color
        cursor.ParaTopMargin, cursor.ParaBottomMargin = 0, 320
        doc.Text.insertString(cursor, text, False)
        cursor.gotoEnd(False)
        if index == 3:
            body = doc.Text.createTextCursorByRange(cursor)
    doc.getCurrentController().getViewCursor().gotoRange(body, False)
    doc.store()
doc.getUndoManager().clear()
