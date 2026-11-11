"""Generate the Excel-inspired ribbon in a disposable Calc preview profile."""
from hashlib import sha256
from pathlib import Path
from io import BytesIO
import os
import subprocess
import xml.etree.ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

from fixtures import connect, prop, stop_office

SOURCE = Path("/usr/lib/libreoffice/share/config/soffice.cfg/modules/scalc/ui/notebookbar.ui")
SOURCE_HASH = "95663027bb4325d46522b19259fe47fc85b837b6f92558f6568942b58d535804"
SYSTEM_ICONS = Path("/usr/share/libreoffice/share/config/images_sifr_dark_svg.zip")
SHORTCUTS = "private:resource/toolbar/notebookbarshortcuts"
REGISTRY = "http://openoffice.org/2001/registry"

LABEL_GROUPS = (
    ("CalcCommands", "Commands", {
        "ConditionalFormatMenu": "Conditional Formatting",
        "CalculateHard": "Recalculate All",
    }),
    ("GenericCommands", "Commands", {"ViewSidebarStyles": "Cell Styles"}),
    ("CalcCommands", "Popups", {"RowOperations": "Rows", "ColumnOperations": "Columns"}),
)



# The study's command artwork, drawn on a shared 24-unit grid.
ICONS = {
    "bold": ("M7 3h6a5 5 0 0 1 0 10H7Zm0 10h7a4 4 0 0 1 0 8H7Z", "#f2eff8"),
    "italic": ("M10 3h10M4 21h10M15 3 9 21", "#f2eff8"),
    "underline": ("M6 3v9a6 6 0 0 0 12 0V3M4 21h16", "#f2eff8"),
    "fontcolor": ("M5 17 12 3l7 14M8 12h8M4 21h16", "#f2eff8"),
    "backcolor": ("m4 15 10-11 6 6-11 10H4Zm7-8 6 6M3 22h18", "#f2eff8"),
    "backgroundcolor": ("m4 15 10-11 6 6-11 10H4Zm7-8 6 6M3 22h18", "#f2eff8"),
    "charbackcolor": ("m4 15 10-11 6 6-11 10H4Zm7-8 6 6M3 22h18", "#f2eff8"),
    "color": ("M5 17 12 3l7 14M8 12h8M4 21h16", "#f2eff8"),
    "grow": ("M3 19 9 5l6 14M5 14h8m3-9 3-3 3 3m-3-3v9", "#f2eff8"),
    "shrink": ("M3 19 9 5l6 14M5 14h8m3-6 3 3 3-3m-3 3V2", "#f2eff8"),
    "numberformatpercent": ("m5 20 14-16M9 6a3 3 0 1 1-6 0 3 3 0 0 1 6 0Zm12 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z", "#f2eff8"),
    "numberformatthousands": ("M8 8h-3v5h3v4l-3 3m14-12h-3v5h3v4l-3 3", "#f2eff8"),
    "functiondialog": ("M16 3h-3a3 3 0 0 0-3 3L7 19a3 3 0 0 1-3 2H2M5 9h10m0 5 6 7m0-7-6 7", "#f2eff8"),
    "insertgraphic": ("M3 4h18v16H3Zm0 12 5-5 5 5 3-3 5 5M14 8h.01", "#f2eff8"),
    "inserttable": ("M3 4h18v16H3ZM3 9h18M9 9v11m6-11v11M3 14h18", "#f2eff8"),
    "table": ("M3 4h18v16H3ZM3 9h18M9 9v11m6-11v11M3 14h18", "#f2eff8"),
    "insertobjectchart": ("M4 3v18h17M8 16v-5m5 5V6m5 10V9", "#f2eff8"),
    "hyperlinkdialog": ("m9 15 6-6m-7 5-2 2a4 4 0 0 0 6 6l4-4m-6-8 4-4a4 4 0 0 1 6 6l-2 2", "#f2eff8"),
    "insertannotation": ("M3 4h18v13H9l-6 4Zm4 5h10M7 13h7", "#f2eff8"),
    "spellingandgrammardialog": ("m3 12 4 4 8-9M12 4h8m-5 0v6m3 5h3m-3 4h3", "#f2eff8"),
    "calculate": ("M7 3h10v18H7ZM10 7h4m-4 5h4m-4 4h1m2 0h1", "#f2eff8"),
    "calculatehard": ("M7 3h10v18H7ZM10 7h4m-4 5h4m-4 4h1m2 0h1", "#f2eff8"),
    "delete": ("M4 6h16M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7", "#f2eff8"),
    "conditionalformatmenu": ("M3 5h18v14H3ZM3 10h18M3 15h18M9 5v14m6-14v14", "#c1aaf3"),
    "paste": ("M8 5H5v16h14V5h-3M8 7V3h8v4H8m0 5h8m-8 4h6", "#f2eff8"),
    "rowoperations": ("M3 5h18v14H3ZM3 10h18M3 15h18m-12-10v14", "#f2eff8"),
    "columnoperations": ("M3 5h18v14H3ZM3 10h18m-12-5v14m6-14v14", "#f2eff8"),
    "viewsidebarstyles": ("M3 5h18v14H3ZM3 10h18M3 15h9m-3-10v14m5 1 6-6 2 2-6 6h-2Z", "#c1aaf3"),
    "cut": ("M10 12 20 3m-6 9L4 3m10 9-3 3m-3-1 2 2a3 3 0 1 1-2-2Zm8 0-2 2a3 3 0 1 0 2-2Z", "#f2eff8"),
    "copy": ("M8 8h12v13H8ZM5 16H3V3h12v2", "#f2eff8"),
    "formatpaintbrush": ("M3 4h14v6H3Zm14 3h4v6h-9v4m-2 0h4v5h-4Z", "#f2eff8"),
    "alignleft": ("M4 5h16M4 9h10M4 13h16M4 17h10", "#f2eff8"),
    "alignhorizontalcenter": ("M4 5h16M7 9h10M4 13h16M7 17h10", "#f2eff8"),
    "alignright": ("M4 5h16m-10 4h10M4 13h16m-10 4h10", "#f2eff8"),
    "aligntop": ("M4 4h16m-13 5h10M5 13h14M8 17h8", "#f2eff8"),
    "alignvcenter": ("M5 5h14M8 9h8M4 13h16M7 17h10", "#f2eff8"),
    "alignbottom": ("M8 5h8M5 9h14m-12 4h10M4 19h16", "#f2eff8"),
    "wraptext": ("M4 5h16M4 10h13a4 4 0 0 1 0 8h-5m3-3-3 3 3 3M4 16h4", "#f2eff8"),
    "togglemergecells": ("M3 5h18v14H3Zm3 7h12m-3-3 3 3-3 3M9 9l-3 3 3 3", "#f2eff8"),
    "setborderstyle": ("M4 4h16v16H4ZM12 4v16M4 12h16", "#f2eff8"),
    "autosum": ("M20 4H5l7 8-7 8h15", "#f2eff8"),
    "sortascending": ("M6 4v16m-3-3 3 3 3-3m4-9h8m-8 4h6m-6 4h4", "#f2eff8"),
    "datafilterautofilter": ("M3 5h18l-7 8v6l-4 2v-8Z", "#f2eff8"),
    "numberformatcurrency": ("M12 2v20m6-16H9a4 4 0 0 0 0 8h6a4 4 0 0 1 0 8H6", "#f2eff8"),
    "numberformatincdecimals": ("M3 17h1m5-7c-3 0-3 7 0 7s3-7 0-7m6-5h6m-3-3 3 3-3 3", "#c1aaf3"),
    "numberformatdecdecimals": ("M2 17h1m5-7c-3 0-3 7 0 7s3-7 0-7m8 0c-3 0-3 7 0 7s3-7 0-7m0-5H8m3-3-3 3 3 3", "#c1aaf3"),
    "searchdialog": ("M19 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0Zm-2 5 5 6", "#f2eff8"),
}


def localize_commands(config, app="calc"):
    tree = ET.fromstring(config)
    path = ET.SubElement(tree, "item", {
        f"{{{REGISTRY}}}path": "/org.openoffice.Office.Paths/Paths/Iconset/InternalPaths",
    })
    ET.SubElement(path, "node", {
        f"{{{REGISTRY}}}name": "%origin%/iconsets", f"{{{REGISTRY}}}op": "fuse",
    })
    for component, section, labels in LABEL_GROUPS if app == "calc" else ():
        parent = f"/org.openoffice.Office.UI.{component}/UserInterface/{section}"
        for name, label in labels.items():
            item = ET.SubElement(tree, "item", {f"{{{REGISTRY}}}path": f"{parent}/['.uno:{name}']"})
            fields = ("Label",)
            for field_name in fields:
                field = ET.SubElement(item, "prop", {
                    f"{{{REGISTRY}}}name": field_name, f"{{{REGISTRY}}}op": "fuse",
                })
                ET.SubElement(field, "value", {"{http://www.w3.org/XML/1998/namespace}lang": "en-US"}).text = label
    ET.register_namespace("oor", REGISTRY)
    return ET.tostring(tree, encoding="utf-8", xml_declaration=True)


def preview_package(source, output, app="calc"):
    """Build the disposable shared icon package with module-specific labels."""
    theme = "iconsets/images_sifr_dark_svg.zip"
    # The release deliberately does not vendor Sifr. Derive the disposable
    # theme from the official installed package, retaining its license files.
    with ZipFile(source) as base, ZipFile(SYSTEM_ICONS) as icons:
        replacements = {}
        for prefix, size in (("sc_", 16), ("lc_", 24), ("32/", 32)):
            for name, (path, color) in ICONS.items():
                replacements[f"cmd/{prefix}{name}.svg"] = (
                    f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24">'
                    f'<path d="{path}" fill="none" stroke="{color}" stroke-width="1.55" '
                    'stroke-linecap="round" stroke-linejoin="round"/></svg>'
                )
        replacements["cmd/norvi_ribbon_rule.svg"] = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="68">'
            '<path d="M.5 0v68" stroke="#81778e" stroke-opacity=".65"/></svg>'
        )
        # Sifr aliases some command names. The replacement files take their place.
        link_lines = icons.read("links.txt").decode().splitlines()
        links = "\n".join(line for line in link_lines if not line.split() or line.split()[0] not in replacements) + "\n"
        replacements["links.txt"] = links
        bundle = BytesIO()
        with ZipFile(bundle, "w", ZIP_DEFLATED) as themed:
            for item in icons.infolist():
                if item.filename not in replacements:
                    themed.writestr(item, icons.read(item))
            for name, contents in replacements.items():
                themed.writestr(name, contents)
        with ZipFile(output, "x", ZIP_DEFLATED) as package:
            for item in base.infolist():
                if item.filename == theme:
                    continue
                contents = base.read(item)
                if item.filename == "norvi_glass.xcu":
                    contents = localize_commands(contents, app)
                package.writestr(item, contents)
            package.writestr(theme, bundle.getvalue())


def widget(kind, identifier, **properties):
    node = ET.Element("object", {"class": kind, "id": identifier})
    for key, value in {"visible": "True", **properties}.items():
        ET.SubElement(node, "property", name=key).text = value
    return node


def pack(parent, node):
    ET.SubElement(parent, "child").append(node)


def add_formulas_tab(tree):
    tabs = tree.find(".//object[@id='ContextContainer']")
    for child in list(tabs):
        node = child.find("object")
        if node is not None and node.get("id") in ("Tools Tab", "DevLabel"):
            tabs.remove(child)
    page = widget("sfxlo-PriorityHBox", "Norvi Formulas Tab", spacing="8")
    label = widget("GtkLabel", "NorviFormulasLabel", label="For~mulas", use_underline="True")
    for name, commands in (
        ("Functions", ("FunctionDialog", "FunctionBox", "ToggleFormula")),
        ("Names", ("AddName", "DefineName")),
        ("Calculation", ("Calculate", "CalculateHard")),
    ):
        toolbar = widget("sfxlo-NotebookbarToolBox", "NorviFormula" + name,
                         toolbar_style="both", show_arrow="False", icon_size="3", can_focus="True")
        for command in commands:
            pack(toolbar, widget("GtkToolButton", "NorviFormula" + command,
                                 action_name=".uno:" + command))
        pack(page, toolbar)
    data = next(index for index, child in enumerate(tabs)
                if child.find("object") is not None and child.find("object").get("id") == "Data Tab")
    child = ET.Element("child")
    child.append(page)
    tabs.insert(data, child)
    tab = ET.Element("child", type="tab")
    tab.append(label)
    ET.SubElement(ET.SubElement(tab, "packing"), "property", name="tab_fill").text = "False"
    tabs.insert(data + 1, tab)


def set_menu_image(tree, button, identifier, icon):
    image = widget("GtkImage", identifier, pixbuf=f"cmd/sc_{icon}.png")
    tree.getroot().insert(0, image)
    for name, value in (("image", identifier), ("image_position", "left"), ("always_show_image", "True")):
        ET.SubElement(button, "property", name=name).text = value


def build_find_menu(tree):
    menu = widget("GtkMenu", "Norvi Find and Select")
    for command, url in (
        ("Find", "vnd.sun.star.findbar:FocusToFindbar"),
        ("Replace", ".uno:SearchDialog"),
        ("SelectAll", ".uno:SelectAll"),
        ("SelectRow", ".uno:SelectRow"),
        ("SelectColumn", ".uno:SelectColumn"),
        ("SelectData", ".uno:SelectData"),
    ):
        pack(menu, widget("GtkMenuItem", "NorviFind" + command, action_name=url))
    tree.getroot().insert(0, menu)

    box = tree.find(".//object[@id='PasteBox1']")
    dropdown, tools = box.findall("child")
    button = dropdown.find("object")
    button.set("id", "Home-HomeButton:Norvi Find and Select")
    label = button.find("property[@name='label']")
    label.attrib = {"name": "label"}
    label.text = "Find & Select"
    set_menu_image(tree, button, "NorviFindIcon", "searchdialog")
    dropdown.find("packing/property[@name='position']").text = "1"
    tools.find("packing/property[@name='position']").text = "0"
    toolbar = tools.find("object")
    old_find = toolbar.find("child/object[@id='Home-SearchDialog']/property[@name='action_name']")
    old_find.text = ".uno:AutoSum"
    box.remove(dropdown)
    box.append(dropdown)


def build_home(tree, dark):
    home = tree.find(".//object[@id='Home']")
    nodes = {item.get("id"): item for item in home.iter("object")}

    def set_property(identifier, key, value):
        item = nodes[identifier]
        prop = item.find(f"property[@name='{key}']")
        if prop is None:
            prop = ET.Element("property", name=key)
            item.insert(0, prop)
        prop.text = value

    def move(identifier, source, destination):
        child = next(child for child in nodes[source].findall("child")
                     if child.find("object").get("id") == identifier)
        nodes[source].remove(child)
        nodes[destination].append(child)

    # Preserve VCL's stock container identities and real command bindings.
    move("Home-FormatPaintbrush", "LineA7", "LineB7")
    move("Home-WrapText", "second14", "first6")
    move("Home-MergeCells", "SectionBottom35", "second6")
    move("Home-StyleApply", "SectionBottom101", "SectionBottom37")
    for identifier in ("LineA6", "LineB7"):
        set_property(identifier, "toolbar_style", "icons")
    for identifier in ("LineA10", "LineB11"):
        set_property(identifier, "toolbar_style", "both-horiz")

    hide = (
        "Home-ResetAttributes", "Home-Spacing", "Home-IncrementIndent", "Home-DecrementIndent",
        "Home-ParaLeftToRight1", "Home-ParaRightToLeft1", "Home-AlignBlock",
        "Home-StandardStyle", "Home-GoodStyle", "Home-BadStyle",
        "Home-Strikeout", "Home-SubScript", "Home-SuperScript", "Home-NumberFormatDecimal",
        "Home-InsertRowsBefore", "Home-DeleteRows", "Home-InsertColumnsBefore",
        "Home-DeleteColumns", "Home-H1Style", "Home-H2Style", "Home-NeutralStyle",
    )
    for identifier in hide:
        set_property(identifier, "visible", "False")
    for identifier in ("Home-Section-Clipboard", "Home-Section-Find1"):
        set_property(identifier, "margin_start", "10")
    set_property("Home-Section-Format", "margin_start", "8")
    set_property("Home-RowOperations", "label", "Rows")
    set_property("Home-ColumnOperations", "label", "Columns")
    set_property("Home-ConditionalFormatMenu", "label", "Conditional\nFormatting")
    # The native StyleApply combobox takes a full field's width. Use the
    # native Cell Styles deck for the study's compact labeled action.
    set_property("Home-StyleApply", "action_name", ".uno:ViewSidebarStyles")
    for name, priority in (("Style2", 6), ("Cell1", 5), ("Find", 4), ("Find1", 3)):
        nodes["Home-Section-" + name].find("style/class").set("name", f"priority-{priority}")

    if dark:
        # Rules are VCL children of their groups, so they move with overflow.
        for name in ("Format", "Align", "Number", "Condition", "Cell1"):
            group = nodes["Home-Section-" + name]
            rule = widget("GtkImage", "NorviRule" + name, pixbuf="cmd/norvi_ribbon_rule.png",
                          margin_start="6", margin_end="8", valign="center")
            child = ET.Element("child")
            child.append(rule)
            packing = ET.SubElement(child, "packing")
            ET.SubElement(packing, "property", name="position").text = "0"
            for sibling in group.findall("child"):
                position = sibling.find("packing/property[@name='position']")
                if position is not None:
                    position.text = str(int(position.text) + 1)
            group.insert(len(group.findall("property")), child)
        for identifier in ("separator102", "separator30", "separator1"):
            set_property(identifier, "visible", "False")

    # Style commands sit ahead of row and column commands. Narrow windows
    # retain the stock Notebookbar overflow and the Home menu.
    children = {item.find("object").get("id").removeprefix("Home-Section-"): item
                for item in home.findall("child")}
    # The dedicated editing group owns Search, Sort and Filter now.
    order = ("Clipboard", "Style", "Format", "Align", "Align1", "Number",
             "Condition", "Style2", "Cell", "Cell1")
    for item in children.values():
        home.remove(item)
    for index, name in enumerate(order):
        item = children[name]
        item.find("packing/property[@name='position']").text = str(index)
        home.append(item)


def prepare(profile):
    root = Path.cwd().resolve()
    if profile.resolve() != root / "profile-calc" or not root.name.startswith("capture."):
        raise ValueError("The ribbon preview requires a fresh capture profile")
    source = SOURCE.read_bytes()
    if sha256(source).hexdigest() != SOURCE_HASH:
        raise ValueError("Unsupported Calc ribbon input")
    tree = ET.ElementTree(ET.fromstring(source, parser=ET.XMLParser(
        target=ET.TreeBuilder(insert_comments=True))))
    build_home(tree, "dark" in os.environ.get("GTK_THEME", ""))
    add_formulas_tab(tree)
    extension_label = tree.find(".//object[@id='ExtensionLabel']/property[@name='label']")
    extension_label.attrib = {"name": "label"}
    extension_label.text = "E~xtensions"
    build_find_menu(tree)
    destination = profile / "user/config/soffice.cfg/modules/scalc/ui/notebookbar.ui"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as output:
        tree.write(output, encoding="utf-8", xml_declaration=True)

    pipe = "norvi_ribbon_" + root.name.replace(".", "_")
    with Path("calc-ribbon-setup.log").open("w") as log:
        office = subprocess.Popen([
            "soffice", "-env:UserInstallation=" + profile.as_uri(), "--headless", "--norestore",
            f"--accept=pipe,name={pipe};urp;",
        ], stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            context = connect(pipe)
            supplier = context.getValueByName("/singletons/com.sun.star.ui.theModuleUIConfigurationManagerSupplier")
            manager = supplier.getUIConfigurationManager("com.sun.star.sheet.SpreadsheetDocument")
            settings = manager.getSettings(SHORTCUTS, True)
            duplicates = {".uno:OpenFromCalc", ".uno:Save", ".uno:Undo", ".uno:Redo", ".uno:Print", ".uno:Menubar"}
            for index in reversed(range(settings.getCount())):
                properties = {item.Name: item.Value for item in settings.getByIndex(index)}
                if properties.get("CommandURL") in duplicates:
                    settings.removeByIndex(index)
            manager.replaceSettings(SHORTCUTS, settings)
            manager.store()

            provider = context.ServiceManager.createInstanceWithContext(
                "com.sun.star.configuration.ConfigurationProvider", context)
            config = provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationUpdateAccess",
                (prop("nodepath", "/org.openoffice.Office.UI.ToolbarMode"),))
            config.ActiveCalc = "notebookbar.ui"
            config.commitChanges()
            for component, section, labels in LABEL_GROUPS:
                access = provider.createInstanceWithArguments(
                    "com.sun.star.configuration.ConfigurationUpdateAccess",
                    (prop("nodepath", f"/org.openoffice.Office.UI.{component}/UserInterface/{section}"),))
                for command, label in labels.items():
                    entry = access.getByName(".uno:" + command)
                    entry.Label = label
                access.commitChanges()
            desktop = context.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", context)
            desktop.terminate()
        finally:
            stop_office(office)
