#!/usr/bin/env python3
"""Prepare a native Aqua design trial without launching or modifying LibreOffice."""
import argparse
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import plistlib
import shlex
import shutil
import struct
import tempfile
import xml.etree.ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[1]
EXPERIMENTS = HERE.parent
REGISTRY = "http://openoffice.org/2001/registry"
APPS = {"writer": ".odt", "calc": ".ods", "impress": ".odp", "draw": ".odg",
        "base": ".odb", "math": ".odf", "startcenter": None}
DOCUMENTS = {"writer": "Studio Brief.odt", "calc": "Quarterly Budget.ods", "impress": "Launch Review.odp",
             "draw": "Concept Board.odg", "math": "Formula Study.odf", "base": "Data Study.odb"}


def ribbon_module():
    spec = importlib.util.spec_from_file_location("mac_trial_ribbon", EXPERIMENTS / "native-header/calc_ribbon.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def config(appearance):
    tree = ET.parse(SOURCE / "extension/norvi_glass.xcu")
    for item in tree.getroot().findall("item"):
        path = item.get(f"{{{REGISTRY}}}path")
        if path == "/org.openoffice.Office.UI/ToolbarMode":
            item.set(f"{{{REGISTRY}}}path", "/org.openoffice.Office.UI.ToolbarMode")
        for prop in item.findall("prop"):
            name = prop.get(f"{{{REGISTRY}}}name")
            if path == "/org.openoffice.Office.UI/ToolbarMode" and name.startswith("Active"):
                prop.find("value").text = "notebookbar.ui"
            if name == "ApplicationAppearance":
                prop.find("value").text = "2" if appearance == "dark" else "1"
    # ActiveCalc/Writer select the notebookbar implementation, but do not turn
    # notebookbar mode on. Mirror View > User Interface's per-application state.
    for module in ("Calc", "Writer", "Impress", "Draw"):
        path = ("/org.openoffice.Office.UI.ToolbarMode/Applications/"
                f"org.openoffice.Office.UI.ToolbarMode:Application['{module}']")
        item = ET.SubElement(tree.getroot(), "item", {f"{{{REGISTRY}}}path": path})
        prop = ET.SubElement(item, "prop", {f"{{{REGISTRY}}}name": "Active", f"{{{REGISTRY}}}op": "fuse"})
        ET.SubElement(prop, "value").text = "notebookbar.ui"
    ET.register_namespace("oor", REGISTRY)
    return ET.tostring(tree.getroot(), encoding="utf-8", xml_declaration=True)


def safe_output(output, bundle):
    output, bundle = output.expanduser().resolve(), bundle.expanduser().resolve()
    if output.exists():
        raise ValueError("Use a new trial directory; existing trials and documents are preserved")
    protected = (bundle, Path.home() / "Library/Application Support/LibreOffice",
                 Path.home() / ".config/libreoffice")
    if output == Path.home() or output == Path(output.anchor) or any(output.is_relative_to(p.resolve()) for p in protected):
        raise ValueError("The trial must be separate from the application and normal profile")
    return output, bundle


def prepare(bundle, output, appearance="dark"):
    output, bundle = safe_output(output, bundle)
    resources = bundle / "Contents/Resources"
    executable = bundle / "Contents/MacOS/soffice"
    info = plistlib.loads((bundle / "Contents/Info.plist").read_bytes())
    if not executable.is_file() or info.get("CFBundleIdentifier") != "org.libreoffice.script":
        raise ValueError("Select an official LibreOffice application bundle")
    ribbon = ribbon_module()
    notebook = resources / "config/soffice.cfg/modules/scalc/ui/notebookbar.ui"
    original = notebook.read_bytes()
    if sha256(original).hexdigest() != ribbon.SOURCE_HASH:
        raise ValueError("Unsupported Calc ribbon input; no trial files were changed")
    style = "sifr_dark_svg" if appearance == "dark" else "sifr_svg"
    icons = resources / "config" / f"images_{style}.zip"
    if not icons.is_file():
        raise ValueError("The application does not contain the required official Sifr theme")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".norvi-mac-trial-", dir=output.parent) as directory:
        staged = Path(directory) / "trial"
        staged.mkdir()
        profile = staged / "profile"
        destination = profile / "user/config/soffice.cfg/modules/scalc/ui/notebookbar.ui"
        destination.parent.mkdir(parents=True)
        tree = ET.ElementTree(ET.fromstring(original, parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))))
        ribbon.build_home(tree, appearance == "dark")
        ribbon.add_formulas_tab(tree)
        ribbon.build_find_menu(tree)
        label = tree.find(".//object[@id='ExtensionLabel']/property[@name='label']")
        label.attrib, label.text = {"name": "label"}, "E~xtensions"
        tree.write(destination, encoding="utf-8", xml_declaration=True)
        base = staged / "base.oxt"
        description = b'''<?xml version="1.0" encoding="UTF-8"?>
<description xmlns="http://openoffice.org/extensions/description/2006">
  <identifier value="dev.norvi.NorviMacTrial"/>
  <version value="0.1.0"/>
  <display-name><name lang="en">Norvi Office - Mac UI Trial</name></display-name>
  <publisher><name lang="en">Norvi</name></publisher>
  <extension-description><desc lang="en">Native Mac trial of the grouped Calc ribbon and shared command artwork.
  Native macOS controls and shortcuts remain. GNOME glass effects are unavailable on macOS.</desc></extension-description>
</description>'''
        with ZipFile(base, "x", ZIP_DEFLATED) as package:
            for path in sorted((SOURCE / "extension").rglob("*")):
                if path.is_file():
                    content = config(appearance) if path.name == "norvi_glass.xcu" else path.read_bytes()
                    if path.name == "description.xml":
                        content = description
                    package.writestr(path.relative_to(SOURCE / "extension").as_posix(), content)
        package = staged / "NorviMacTrial.oxt"
        # Do not relabel Writer's generic styles command as Calc's Cell Styles.
        ribbon.preview_package(base, package, app="writer", icons_source=icons, appearance=appearance)
        base.unlink()
        (staged / "Documents").mkdir()
        applications = staged / "Applications"
        applications.mkdir()
        png = (EXPERIMENTS / "startup/assets/office.png").read_bytes()
        chunk = b"ic10" + struct.pack(">I", len(png) + 8) + png
        icon = b"icns" + struct.pack(">I", len(chunk) + 8) + chunk
        for app, extension in APPS.items():
            name = "Norvi Office Mac Test" if app == "startcenter" else f"Norvi {app.title()} Mac Test"
            contents = applications / (name + ".app") / "Contents"
            (contents / "MacOS").mkdir(parents=True)
            (contents / "Resources").mkdir()
            (contents / "Resources/Office.icns").write_bytes(icon)
            plist = {"CFBundleIdentifier": "dev.norvi.office.mactrial." + app, "CFBundleName": name,
                     "CFBundleDisplayName": name, "CFBundleExecutable": "launch", "CFBundlePackageType": "APPL",
                     "CFBundleShortVersionString": "0.1.0", "CFBundleVersion": "1", "CFBundleIconFile": "Office.icns",
                     "NSHighResolutionCapable": True}
            (contents / "Info.plist").write_bytes(plistlib.dumps(plist))
            arguments = [str(executable), "--nologo", "-env:UserInstallation=" + (output / "profile").as_uri()]
            if app != "startcenter":
                arguments.append("--" + app)
            script = "#!/bin/sh\nset -eu\nexport PYTHONDONTWRITEBYTECODE=1\n"
            if extension:
                document = output / "Documents" / DOCUMENTS[app]
                script += f"if [ \"$#\" -eq 0 ] && [ -f {shlex.quote(str(document))} ]; then\n  set -- {shlex.quote(str(document))}\nfi\n"
            script += "exec " + " ".join(shlex.quote(value) for value in arguments) + ' "$@"\n'
            launcher = contents / "MacOS/launch"
            launcher.write_text(script)
            launcher.chmod(0o755)
        receipt = {"kind": "native macOS Aqua design trial; not a Linux glass release", "state": "prepared; preset installation and visible acceptance pending",
                   "application": str(bundle), "application_version": info.get("CFBundleShortVersionString"),
                   "source_calc_sha256": sha256(original).hexdigest(), "appearance": appearance,
                   "toolbar_mode": "notebookbar.ui", "toolbar_mode_modules": ["Calc", "Writer", "Impress", "Draw"],
                   "theme_sha256": sha256(icons.read_bytes()).hexdigest(), "profile": str(output / "profile"),
                   "profile_uri": (output / "profile").as_uri(),
                   "package": str(output / package.name), "apps": list(APPS),
                   "install_command": [str(bundle / "Contents/MacOS/unopkg"), "add",
                                       "-env:UserInstallation=" + (output / "profile").as_uri(), str(output / package.name)],
                   "runtime_environment": {"PYTHONDONTWRITEBYTECODE": "1"},
                   "normal_profile": "untouched", "application_bundle": "unmodified",
                   "glass": "unavailable: GNOME compositor effects are not native macOS effects",
                   "native_shortcuts": "Open/Save/Undo/Redo retained; no Linux header suppression",
                   "documents": "fictional review fixtures may be created here; never removed automatically"}
        (staged / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        shutil.copy2(EXPERIMENTS / "startup/assets/provenance.json", staged / "office-icon-provenance.json")
        staged.rename(output)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--appearance", choices=("dark", "light"), default="dark")
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.app_bundle, args.output, args.appearance), indent=2))
    except (OSError, ValueError, KeyError, ET.ParseError) as error:
        parser.exit(1, f"Mac trial preparation: {error}\n")


if __name__ == "__main__":
    main()
