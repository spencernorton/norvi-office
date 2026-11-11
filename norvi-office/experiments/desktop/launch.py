#!/usr/bin/python3
"""Launch the actual suite on the current desktop using a persistent Norvi profile."""
import argparse
import fcntl
import importlib.util
from hashlib import sha256
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


def service_pipe(profile, stage="runtime"):
    return "norvi_" + stage + "_" + sha256(profile.resolve().as_uri().encode()).hexdigest()[:20]


def service_bus(profile):
    return "dev.norvi.OfficeHeader.Desktop.p" + sha256(profile.resolve().as_uri().encode()).hexdigest()[:20]


def qualified():
    contract = json.loads((SHARE / "compatibility.json").read_text())["experimental_native_adapter"]
    office = subprocess.check_output(["libreoffice", "--version"], text=True).split()[1]
    shell = subprocess.check_output(["gnome-shell", "--version"], text=True).split()[-1].split(".")[0]
    return office in contract["libreoffice_versions"] and shell in contract["gnome_shell_versions"]


def command(app, files, profile=None, pipe=None):
    # Interactive applications retain normal crash recovery. --norestore belongs
    # only to disposable/headless initialization and qualification processes.
    args = ["soffice", "--nologo"]
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
    pipe = service_pipe(profile, "setup")
    with (root / "setup.log").open("w") as log:
        office = subprocess.Popen(["soffice", "-env:UserInstallation=" + profile.as_uri(), "--headless",
                                   "--norestore", f"--accept=pipe,name={pipe};urp;"],
                                  env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            context = connect(pipe, profile)
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


def running(root, profile):
    record = root / "running.json"
    if not record.exists():
        return False
    item = json.loads(record.read_text())
    try:
        process = Path(f'/proc/{item["office_group"]}/cmdline').read_bytes()
    except FileNotFoundError:
        return False
    return Path(item["profile"]).resolve() == profile.resolve() and \
        f'--accept=pipe,name={item["pipe"]};urp;'.encode() in process.split(b"\0") and \
        ("-env:UserInstallation=" + profile.as_uri()).encode() in process.split(b"\0")


HELPERS = {"broker": "actions.py", "geometry": "geometry_relay.py"}


def helper_alive(root, record, role, proc=Path("/proc")):
    """A reused PID is not proof that our helper is still running."""
    try:
        pid = record[role]
        if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
            return False
        process = proc / str(pid)
        if process.stat().st_uid != os.getuid():
            return False
        arguments = process.joinpath("cmdline").read_bytes().split(b"\0")
        values = dict(item.split(b"=", 1) for item in process.joinpath("environ").read_bytes().split(b"\0") if b"=" in item)
        return values.get(b"NORVI_OFFICE_SESSION_DIR") == str(root).encode() and \
            (role != "broker" or str(record.get("pipe", "")).encode() in arguments) and any(
            Path(os.fsdecode(arg)).name == HELPERS[role] and
            Path(os.fsdecode(arg)).parent.name == "native-header" for arg in arguments if arg)
    except (KeyError, OSError):
        return False


def ensure_helpers(root, record, env):
    """Recover failed presentation helpers without closing any Office document."""
    for role, script in HELPERS.items():
        if helper_alive(root, record, role):
            continue
        arguments = [record["pipe"]] if role == "broker" else []
        with (root / (role + ".log")).open("a") as log:
            process = subprocess.Popen([sys.executable, str(HEADER / script), *arguments], env=env, cwd=root,
                                       stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        record[role] = process.pid
        # Retain each successfully created helper even if a later spawn fails.
        (root / "running.json").write_text(json.dumps(record) + "\n")
    return record


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
                   GTK_THEME="Yaru-purple-dark", NORVI_OFFICE_CALC_RIBBON="1")
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
        pipe = service_pipe(profile)
        env["NORVI_OFFICE_PROFILE_URI"] = profile.as_uri()
        env["NORVI_OFFICE_HEADER_BUS"] = service_bus(profile)
        env["GTK3_MODULES"] = str(HERE.parents[3] / "lib/x86_64-linux-gnu/norvi-office/libnorvi-office-header.so")
        if running(root, profile):
            record = json.loads((root / "running.json").read_text())
            # A retained legacy runtime may have its older channel name. Verify
            # the actual service before restarting helpers or opening documents.
            connect(record["pipe"], profile)
            env["NORVI_OFFICE_HEADER_BUS"] = record.get("bus", "dev.norvi.OfficeHeader.Desktop")
            ensure_helpers(root, record, env)
            subprocess.Popen(command(app, files, profile), env=env, start_new_session=True)
            return {"native": True, "reused": True, "profile": str(profile)}
        if (root / "running.json").exists():
            previous = json.loads((root / "running.json").read_text())
            for role in ("broker", "geometry"):
                try:
                    if helper_alive(root, previous, role):
                        os.kill(previous[role], signal.SIGTERM)
                except (KeyError, FileNotFoundError, ProcessLookupError):
                    pass
        with (root / "office.log").open("w") as log:
            office = subprocess.Popen(command(app, files, profile, pipe), env=env, cwd=root,
                                      stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        result = {"native": True, "office_group": office.pid, "profile": str(profile), "pipe": pipe,
                  "bus": env["NORVI_OFFICE_HEADER_BUS"]}
        (root / "running.json").write_text(json.dumps(result) + "\n")
        context = connect(pipe, profile)
        ensure_helpers(root, result, env)
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
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--app", choices=APPS, default="startcenter")
    parser.add_argument("files", nargs="*")
    args = parser.parse_args()
    if not args.worker:
        spec = importlib.util.spec_from_file_location("office_loading", SHARE / "startup/launch.py")
        startup = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(startup)
        startup.GIVE_UP_AFTER = 30
        return startup.launch([sys.executable, str(HERE / "launch.py"), "--worker", "--app", args.app,
                               "--", *args.files], allow_startcenter=args.app == "startcenter")
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
    raise SystemExit(main())
