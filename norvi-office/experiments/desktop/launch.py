#!/usr/bin/python3
"""Launch the actual suite on the current desktop using a persistent Norvi profile."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import time
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
HEADER = HERE.parent / "native-header"
SHARE = HERE.parents[1]
sys.path.insert(0, str(HEADER))
from uno_utils import connect, prop, stop_office  # noqa: E402
from calc_ribbon import prepare, preview_package, SHORTCUTS  # noqa: E402

APPS = ("writer", "calc", "impress", "draw", "base", "math", "startcenter")


def qualified():
    contract = json.loads((SHARE / "compatibility.json").read_text())["experimental_native_adapter"]
    office = subprocess.check_output(["libreoffice", "--version"], text=True).split()[1]
    shell = subprocess.check_output(["gnome-shell", "--version"], text=True).split()[-1].split(".")[0]
    return office in contract["libreoffice_versions"] and shell in contract["gnome_shell_versions"]


def command(app, files, profile=None, pipe=None):
    args = ["soffice", "--nologo", "--norestore"]
    if profile:
        args.append("-env:UserInstallation=" + profile.as_uri())
    if pipe:
        args.append(f"--accept=pipe,name={pipe};urp;")
    if app != "startcenter":
        args.append("--" + app)
    args.extend(target if urlsplit(target).scheme else str(Path(target).expanduser().resolve()) for target in files)
    return args


def initialize(root, env):
    profile = root / "profile-calc"
    if (root / "profile-ready.json").is_file():
        return profile
    if profile.exists():
        raise ValueError("An unfinished Norvi profile exists; preserved it for recovery")
    package = root / "NorviDesktop.oxt"
    preview_package(SHARE / "extensions/NorviGlass.oxt", package)
    subprocess.run(["unopkg", "add", "-env:UserInstallation=" + profile.as_uri(), str(package)], env=env, check=True)
    prepare(profile, native=True, environment=env)
    pipe = "norvi_desktop_setup_" + str(os.getuid())
    with (root / "setup.log").open("w") as log:
        office = subprocess.Popen(["soffice", "-env:UserInstallation=" + profile.as_uri(), "--headless",
                                   "--norestore", f"--accept=pipe,name={pipe};urp;"],
                                  env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            context = connect(pipe)
            supplier = context.getValueByName("/singletons/com.sun.star.ui.theModuleUIConfigurationManagerSupplier")
            manager = supplier.getUIConfigurationManager("com.sun.star.text.TextDocument")
            settings = manager.getSettings(SHORTCUTS, True)
            for index in reversed(range(settings.getCount())):
                settings.removeByIndex(index)
            manager.replaceSettings(SHORTCUTS, settings)
            manager.store()
            provider = context.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", context)
            config = provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationUpdateAccess",
                (prop("nodepath", "/org.openoffice.Office.Common/Save/Document"),))
            config.AutoSave = True
            config.AutoSaveTimeIntervall = 5
            config.commitChanges()
            context.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", context).terminate()
        finally:
            stop_office(office)
    (root / "profile-ready.json").write_text(json.dumps({"separate_profile": str(profile), "schema": 1}) + "\n")
    return profile


def running(root, pipe):
    record = root / "running.json"
    if not record.exists():
        return False
    item = json.loads(record.read_text())
    try:
        process = Path(f'/proc/{item["office_group"]}/cmdline').read_bytes()
    except FileNotFoundError:
        return False
    return f"--accept=pipe,name={pipe};urp;".encode() in process.split(b"\0")


def launch(app, files):
    if not qualified():
        subprocess.Popen(command(app, files), start_new_session=True)
        return {"native": False, "reason": "unsupported engine or desktop"}
    root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "norvi-office/desktop"
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (root / "launch.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        env = dict(os.environ)
        for key in ("NORVI_OFFICE_TEST_DIR", "GTK3_MODULES", "GTK_MODULES", "AT_SPI_BUS_ADDRESS"):
            env.pop(key, None)
        env.update(NORVI_OFFICE_SESSION_DIR=str(root), SAL_USE_VCLPLUGIN="gtk3", GDK_BACKEND="wayland",
                   GTK_THEME="Yaru-purple-dark", NORVI_OFFICE_CALC_RIBBON="1",
                   NORVI_OFFICE_HEADER_BUS="dev.norvi.OfficeHeader.Desktop")
        marker = root / "native-session.json"
        if not marker.exists():
            marker.write_text(json.dumps({"mode": "desktop", "token": secrets.token_hex(32)}) + "\n")
            marker.chmod(0o600)
        env["NORVI_OFFICE_HEADER_TOKEN"] = json.loads(marker.read_text())["token"]
        schemas = Path.home() / ".local/share/gnome-shell/extensions/blur-my-shell@aunetx/schemas"
        env["NORVI_OFFICE_POPUP_SCHEMAS"] = str(schemas)
        original = Path.cwd()
        os.chdir(root)
        try:
            # Headless profile creation never loads the native GTK module.
            profile = initialize(root, env)
        finally:
            os.chdir(original)
        pipe = "norvi_desktop_" + str(os.getuid())
        env["GTK3_MODULES"] = str(HERE.parents[3] / "lib/x86_64-linux-gnu/norvi-office/libnorvi-office-header.so")
        if running(root, pipe):
            subprocess.Popen(command(app, files, profile), env=env, start_new_session=True)
            return {"native": True, "reused": True, "profile": str(profile)}
        if (root / "running.json").exists():
            previous = json.loads((root / "running.json").read_text())
            for role in ("broker", "geometry"):
                try:
                    pid = previous[role]
                    process = Path(f"/proc/{pid}")
                    values = dict(item.split(b"=", 1) for item in process.joinpath("environ").read_bytes().split(b"\0") if b"=" in item)
                    if values.get(b"NORVI_OFFICE_SESSION_DIR") == str(root).encode() and process.joinpath("comm").read_text().strip() == "python3":
                        os.kill(pid, signal.SIGTERM)
                except (KeyError, FileNotFoundError, ProcessLookupError):
                    pass
        with (root / "office.log").open("w") as log:
            office = subprocess.Popen(command(app, files, profile, pipe), env=env, cwd=root,
                                      stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        children = {}
        for name, script, arguments in (("broker", "actions.py", [pipe]), ("geometry", "geometry_relay.py", [])):
            with (root / (name + ".log")).open("w") as log:
                process = subprocess.Popen([sys.executable, str(HEADER / script), *arguments], env=env, cwd=root,
                                           stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            children[name] = process.pid
        result = {"native": True, "office_group": office.pid, "profile": str(profile), "pipe": pipe, **children}
        (root / "running.json").write_text(json.dumps(result) + "\n")
        context = connect(pipe)
        desktop = context.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", context)
        until = time.monotonic() + 20
        while time.monotonic() < until:
            doc = desktop.getCurrentComponent()
            if doc is not None and hasattr(doc, "getCurrentController"):
                frame = doc.getCurrentController().getFrame()
                # Initial defaults only; subsequent user sidebar choices persist.
                if not (root / "first-window.json").exists():
                    from actions import Status
                    import uno

                    class Sidebar(Status):
                        visible = None

                        def statusChanged(self, event):
                            self.visible = event.State if event.IsEnabled else None

                    url = uno.createUnoStruct("com.sun.star.util.URL")
                    url.Complete = ".uno:Sidebar"
                    transformer = context.ServiceManager.createInstanceWithContext("com.sun.star.util.URLTransformer", context)
                    _, url = transformer.parseStrict(url)
                    dispatch = frame.queryDispatch(url, "", 0)
                    listener = Sidebar()
                    dispatch.addStatusListener(listener, url)
                    dispatch.removeStatusListener(listener, url)
                    if listener.visible is True:
                        context.ServiceManager.createInstanceWithContext("com.sun.star.frame.DispatchHelper", context).executeDispatch(frame, ".uno:Sidebar", "", 0, ())
                    (root / "first-window.json").write_text('{"configured":true}\n')
                break
            time.sleep(.1)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--desktop", action="store_true")
    parser.add_argument("--app", choices=APPS, default="startcenter")
    parser.add_argument("files", nargs="*")
    args = parser.parse_args()
    try:
        print(json.dumps(launch(args.app, args.files)))
    except Exception as error:
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk
        if Gtk.init_check()[0]:
            dialog = Gtk.MessageDialog(message_type=Gtk.MessageType.ERROR, buttons=Gtk.ButtonsType.CLOSE,
                                       text="Office could not start")
            dialog.format_secondary_text(str(error))
            dialog.run()
            dialog.destroy()
        parser.exit(1, f"Office: {error}\n")


if __name__ == "__main__":
    main()
