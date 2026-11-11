"""Generate the Excel-inspired ribbon in a disposable Calc preview profile."""
from hashlib import sha256
from pathlib import Path
from io import BytesIO
import os
import subprocess
import xml.etree.ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

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



# The study's command artwork, drawn on a shared 24-unit grid. Home and Insert
# keys are taken from the official Calc, Writer and Impress notebookbars. Native
# field controllers (font, size, number format) continue to supply their own UI.
ICONS = {
    "justifypara": ("M4 5h16M4 9h16M4 13h16M4 17h16", "#f2eff8"),
    "charmapcontrol": ("M3 21h6v-3a8 8 0 1 1 6 0v3h6", "#f2eff8"),
    "decrementindent": ("M10 5h11M10 10h11M10 15h11M3 10l4-4m-4 4 4 4M3 20h18", "#f2eff8"),
    "incrementindent": ("M10 5h11M10 10h11M10 15h11M7 10 3 6m4 4-4 4M3 20h18", "#f2eff8"),
    "defaultbullet": ("M9 5h12M9 12h12M9 19h12M3 5h.1M3 12h.1M3 19h.1", "#f2eff8"),
    "defaultnumbering": ("M10 5h11M10 12h11M10 19h11M3 3h1v4M2 11a2 2 0 1 1 4 0l-4 3h4M2 18h3l-2 2h2v2H2", "#f2eff8"),
    "editstyle": ("M4 3h12l4 4v4M4 3v18h7m-3-15h5m-5 4h7m-2 7 7-7 3 3-7 7h-3Z", "#f2eff8"),
    "fontdialog": ("M3 3h18v18H3Zm4 14 5-10 5 10m-8-3h6", "#f2eff8"),
    "insertpagebreak": ("M5 9V3h14v6M5 15v6h14v-6M2 12h20", "#f2eff8"),
    "linespacing": ("M10 5h11M10 12h11M10 19h11M4 3v18m-3-3 3 3 3-3M1 6l3-3 3 3", "#f2eff8"),
    "paragraphdialog": ("M13 21V3h7M18 3v18M13 3H9a5 5 0 0 0 0 10h4", "#f2eff8"),
    "paralefttoright": ("M13 21V3h7M18 3v18M13 3H9a5 5 0 0 0 0 10h4M2 17h7m-3-3 3 3-3 3", "#f2eff8"),
    "pararighttoleft": ("M13 21V3h7M18 3v18M13 3H9a5 5 0 0 0 0 10h4M9 17H2m3-3-3 3 3 3", "#f2eff8"),
    "paraspaceincrease": ("M3 4h18M3 9h18M3 15h9M3 20h9m6 1V11m-3 3 3-3 3 3", "#f2eff8"),
    "paraspacedecrease": ("M3 4h18M3 9h18M3 15h9M3 20h9m6-9v10m-3-3 3 3 3-3", "#f2eff8"),
    "resetattributes": ("M3 16 8 4l5 12M5 12h6m3 9-3-3 7-7 5 5-5 5h-4Zm2-7 5 5", "#f2eff8"),
    "setoutline": ("M3 21 10 3h4l7 18h-5l-2-5h-4l-2 5Zm7-9h4l-2-6Z", "#f2eff8"),
    "strikeout": ("M18 5c-2-3-11-3-11 2s10 4 10 10-9 6-12 2M3 12h18", "#f2eff8"),
    "styleupdatebyexample": ("M4 3h12l4 4v6M4 3v18h7M8 7h5m-5 4h7m-2 8a5 5 0 0 0 9-3m-1-4v5h-5", "#f2eff8"),
    "subscript": ("m3 4 10 13M13 4 3 17m13 0a3 3 0 1 1 6 0l-6 5h6", "#f2eff8"),
    "superscript": ("m3 7 10 14M13 7 3 21m13-16a3 3 0 1 1 6 0l-6 5h6", "#f2eff8"),
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
    "shadowed": ("M3 19 10 3l7 16M6 13h8m1-6 6 15h-5", "#f2eff8"),
    "spacing": ("M3 12 7 3l4 9M5 8h4m6-5v9m0-6h3a3 3 0 0 1 0 6h-3M3 19h18m-15-3-3 3 3 3m12-6 3 3-3 3", "#f2eff8"),
    "controlcodes": ("M13 21V3h7M18 3v18M13 3H9a5 5 0 0 0 0 10h4", "#f2eff8"),
    "stylespreview": ("M3 3h18v18H3Zm3 13 3-7 3 7m-5-2h4m4-6h3m-3 4h3m-3 4h3", "#c1aaf3"),
    "zoom": ("M19 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0Zm-2 5 5 6M8 10h8m-4-4v8", "#f2eff8"),
    "printpreview": ("M5 9V3h14v4M5 17v4h6M3 9h14v5M3 9v8h7m10-1a4 4 0 1 1-8 0 4 4 0 0 1 8 0Zm-1 3 4 4", "#f2eff8"),
    "navigator": ("M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-6-3-2 4-4 2 2-4Z", "#f2eff8"),
    "datadatapilotrun": ("M3 4h17v7M3 4v16h8M3 9h17M8 4v16m5-11v3m1 5h7m-3-3 3 3-3 3m-4-5v6", "#f2eff8"),
    "insert": ("M3 4h17v9M3 4v16h9M3 9h17M8 4v16m5-16v9M3 14h9m5 1v7m-4-3.5h8", "#f2eff8"),
    "insertcell": ("M3 3h8v8H3Zm8 3h10v15H6V11m5 0h10M6 16h15m-5-10v15M5 7h4M7 5v4", "#f2eff8"),
    "insertobject": ("M4 3h12l4 4v14H4Zm12 0v5h4M8 11h8v7H8Z", "#f2eff8"),
    "gallery": ("M7 3h14v14M3 7h14v14H3Zm0 10 4-4 4 4 3-3 3 3M12 11h.1", "#f2eff8"),
    "insertavmedia": ("M3 4h18v16H3Zm6 4 7 4-7 4ZM3 8h3m-3 8h3M18 8h3m-3 8h3", "#f2eff8"),
    "addname": ("M3 5h14l4 7-4 7H3Zm4 4v6m-3-3h6m4-3h2m-2 6h2", "#f2eff8"),
    "definename": ("M3 5h14l4 7-4 7H3Zm3 10V9l4 6V9m3 0h3m-3 6h3", "#f2eff8"),
    "fieldmenu": ("M4 3h12l4 4v14H4Zm12 0v5h4M10 11H8v2l-1 1 1 1v2h2m4-6h2v2l1 1-1 1v2h-2", "#f2eff8"),
    "drawtext": ("M3 3h18v18H3Zm4 5V7h10v1m-5-1v10m-3 0h6", "#f2eff8"),
    "verticaltext": ("M3 3h18v18H3Zm4 4h7m-3.5 0v9M8 16h5m4-8v9m-2-2 2 2 2-2", "#f2eff8"),
    "line": ("M4 20 20 4", "#f2eff8"),
    "connectortoolbox": ("M3 3h5v5H3Zm13 13h5v5h-5ZM8 5.5h4v13h4", "#f2eff8"),
    "arrowstoolbox": ("M3 20 20 3m-8 0h8v8", "#f2eff8"),
    "basicshapes.rectangle": ("M3 5h18v14H3Z", "#f2eff8"),
    "basicshapes.ellipse": ("M21 12a9 7 0 1 1-18 0 9 7 0 0 1 18 0Z", "#f2eff8"),
    "drawcaption": ("M3 4h18v13H10l-7 4Zm4 5h10m-10 4h7", "#f2eff8"),
    "linetoolbox": ("M3 20 9 6l6 12 6-14", "#f2eff8"),
    "basicshapes": ("M3 3h10v10H3Zm18 13a5 5 0 1 1-10 0 5 5 0 0 1 10 0Z", "#f2eff8"),
    "symbolshapes": ("M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0ZM8 9h.1m7.9 0h.1M7 14c2 5 8 5 10 0", "#f2eff8"),
    "arrowshapes": ("M3 8h10V3l8 9-8 9v-5H3Z", "#f2eff8"),
    "starshapes": ("m12 2 3 6 7 1-5 5 1 8-6-4-6 4 1-8-5-5 7-1Z", "#f2eff8"),
    "flowchartshapes": ("M8 2h8v6H8Zm4 6v4m-6 4h12m-6-4v4m-9 0h6v6H3Zm12 0h6v6h-6Z", "#f2eff8"),
    # The bottom three units remain clear for the native selected-color swatch.
    # These are neutral command glyphs, never a painted-in current color.
    "xlinecolor": ("M4 4h16v14H4Z", "#f2eff8"),
    "fillcolor": ("m4 12 8-8 8 8-8 7Zm4-4 4-4V2m6 11 3 4a2 2 0 1 1-4 0Z", "#f2eff8"),
    "presentation": ("M3 3h18v14H3ZM10 7l6 3-6 3ZM7 7v6m5 4v4M7 21h10", "#c1aaf3"),
    "presentationcurrentslide": ("M3 3h18v14H3ZM9 7l7 3-7 3ZM12 17v4M7 21h10", "#c1aaf3"),
    "insertslide": ("M3 4h18v12H3Zm3 4h9m-9 4h5m6 4v6m-3-3h6", "#f2eff8"),
    "duplicateslide": ("M8 8h13v13H8ZM4 16H3V3h13v1M11 12h7m-7 4h4", "#f2eff8"),
    "importslidefromfile": ("M3 3h11l4 4v6M3 3v15h7M14 3v5h4m-2 9H9m3-3-3 3 3 3m4-6h5v8h-5", "#f2eff8"),
    "photoalbumdialog": ("M6 3h15v18H6ZM3 6h3m-3 6h3m-3 6h3m3-10h9v9H9Zm0 6 3-3 3 3 2-2", "#f2eff8"),
    "fontworkgalleryfloater": ("M3 19 8 6l5 13M5 14h6m3-7 2 12 3-9 2 9M3 4c5-3 13-3 18 0", "#f2eff8"),
    "capturepoint": ("M12 3v18M3 12h18M8 8h8v8H8Z", "#f2eff8"),
    "polygon_unfilled": ("M3 17 7 4l13 3 1 12-12 2Z", "#f2eff8"),
    "bezier_unfilled": ("M3 18C6 3 18 21 21 6M3 18V9m18-3v9M1 7h4v4H1Zm18 6h4v4h-4Z", "#f2eff8"),
    "objects3dtoolbox": ("m12 2 9 5v10l-9 5-9-5V7Zm-9 5 9 5 9-5m-9 5v10", "#f2eff8"),
    "insertmath": ("M2 13h3l3 8 5-18h9m-7 8 6 8m0-8-6 8", "#f2eff8"),
    "titlepagedialog": ("M4 3h16v18H4Zm4 5h8m-6 0v6m-2 3h8", "#f2eff8"),
    "insertsection": ("M3 3h18v18H3ZM7 7h3m-3 5h3m-3 5h3m4-10h3m-3 5h3m-3 5h3M12 3v18", "#f2eff8"),
    "insertbookmark": ("M6 3h12v18l-6-4-6 4Z", "#f2eff8"),
    "insertreferencefield": ("M4 3h12l4 4v14H4Zm12 0v5h4M7 12h10m-3-3 3 3-3 3M7 17h7", "#f2eff8"),
    "editglossary": ("M3 3h8v18H3Zm8 3h10v15H11M6 7h2m-2 4h2m-2 4h2m6-5h4m-4 4h4", "#f2eff8"),
    "insertdraw": ("M3 3h18v18H3Zm4 4h6v6H7Zm10 9a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z", "#f2eff8"),
    "toggleformula": ("M3 4h18v16H3ZM3 9h18M8 13h8m-8 4h8", "#f2eff8"),
    "open": ("M3 19V4h7l3 4h8v3M3 19l3-8h16l-3 8Z", "#f2eff8"),
    "save": ("M3 3h15l3 3v15H3Zm4 0v6h10V3M7 21v-8h10v8", "#f2eff8"),
    "undo": ("M3 10h10a7 7 0 0 1 7 7v3M3 10l6-6m-6 6 6 6", "#f2eff8"),
    "redo": ("M21 10H11a7 7 0 0 0-7 7v3m17-10-6-6m6 6-6 6", "#f2eff8"),
    "print": ("M6 9V3h12v6M6 17H3V9h18v8h-3M6 14h12v7H6Zm11-2h1", "#f2eff8"),
    "menubar": ("M3 5h18M3 12h18M3 19h18", "#f2eff8"),
}

# Commands that use the same native concept share artwork; retain their real
# icon lookup keys (including the dot in BasicShapes.rectangle/ellipse).
for alias, original in {
    "leftpara": "alignleft", "centerpara": "alignhorizontalcenter", "rightpara": "alignright",
    "setdefault": "resetattributes", "cellverttop": "aligntop", "cellvertcenter": "alignvcenter",
    "cellvertbottom": "alignbottom", "outlineright": "incrementindent", "outlineleft": "decrementindent",
    "functionbox": "functiondialog", "text": "drawtext", "insertfieldctrl": "fieldmenu",
    "calloutshapes": "drawcaption", "insertobjectstarmath": "insertmath",
    "openfromcalc": "open", "openfromwriter": "open",
}.items():
    ICONS[alias] = ICONS[original]


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


def preview_package(source, output, app="calc", icons_source=None, appearance="dark"):
    """Build the disposable shared icon package with module-specific labels."""
    if appearance not in ("dark", "light"):
        raise ValueError("Icon appearance must be dark or light")
    style = "sifr_dark_svg" if appearance == "dark" else "sifr_svg"
    theme = f"iconsets/images_{style}.zip"
    # The release deliberately does not vendor Sifr. Derive the disposable
    # theme from the official installed package, retaining its license files.
    with ZipFile(source) as base, ZipFile(icons_source or SYSTEM_ICONS) as icons:
        replacements = {}
        for prefix, size in (("sc_", 16), ("lc_", 24), ("32/", 32)):
            for name, (path, color) in ICONS.items():
                if appearance == "light":
                    # Sifr's official light ink and the existing Norvi accent.
                    color = "#2e3436" if color == "#f2eff8" else "#7460d4"
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
                    if appearance == "light":
                        contents = contents.replace(b">sifr_dark_svg<", b">sifr_svg<")
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
    set_property("Home-ConditionalFormatMenu", "label", "Conditional Formatting")
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


def prepare(profile, native=False, environment=None):
    from uno_utils import connect, prop, stop_office

    root = Path.cwd().resolve()
    environment = os.environ if environment is None else environment
    permitted = root.name.startswith("capture.") or (native and environment.get("NORVI_OFFICE_SESSION_DIR") == str(root))
    if profile.resolve() != root / "profile-calc" or not permitted:
        raise ValueError("The ribbon preview requires a fresh capture profile")
    source = SOURCE.read_bytes()
    if sha256(source).hexdigest() != SOURCE_HASH:
        raise ValueError("Unsupported Calc ribbon input")
    tree = ET.ElementTree(ET.fromstring(source, parser=ET.XMLParser(
        target=ET.TreeBuilder(insert_comments=True))))
    build_home(tree, "dark" in environment.get("GTK_THEME", ""))
    add_formulas_tab(tree)
    extension_label = tree.find(".//object[@id='ExtensionLabel']/property[@name='label']")
    extension_label.attrib = {"name": "label"}
    extension_label.text = "E~xtensions"
    build_find_menu(tree)
    destination = profile / "user/config/soffice.cfg/modules/scalc/ui/notebookbar.ui"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as output:
        tree.write(output, encoding="utf-8", xml_declaration=True)

    pipe = "norvi_ribbon_" + sha256(profile.as_uri().encode()).hexdigest()[:20]
    with Path("calc-ribbon-setup.log").open("w") as log:
        office = subprocess.Popen([
            "soffice", "-env:UserInstallation=" + profile.as_uri(), "--headless", "--norestore",
            f"--accept=pipe,name={pipe};urp;",
        ], env=environment, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            context = connect(pipe, profile)
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
