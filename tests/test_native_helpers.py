import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def runtime():
    with patch.dict(sys.modules, {"uno_utils": SimpleNamespace(connect=None, prop=None, stop_office=None),
                                  "calc_ribbon": SimpleNamespace(prepare=None, preview_package=None, SHORTCUTS=None)}):
        spec = importlib.util.spec_from_file_location("native_helper_test", ROOT / "norvi-office/experiments/desktop/launch.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


def broker():
    header = ROOT / "norvi-office/experiments/native-header"
    with patch.object(sys, "path", [str(header), *sys.path]):
        spec = importlib.util.spec_from_file_location("native_broker_test", header / "actions.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


class NativeHelperTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("uno"), "LibreOffice's Python bridge required")
    def test_command_state_is_asked_on_the_office_main_thread_or_not_at_all(self):
        actions = broker()
        # Office calls the work back later, from its own main thread.
        later = SimpleNamespace(addCallback=lambda task, _data: threading.Thread(
            target=task.notify, args=(None,)).start())
        self.assertEqual(actions.on_main(later, lambda: 7), 7)
        with self.assertRaises(KeyError):
            actions.on_main(later, lambda: {}["missing"])
        # A busy Office answers too late: the caller gets an error and work not yet started never runs.
        late, ran = [], []
        never = SimpleNamespace(addCallback=lambda task, _data: late.append(task))
        with patch.object(actions.threading.Event, "wait", return_value=False), self.assertRaises(TimeoutError):
            actions.on_main(never, lambda: ran.append(1))
        late[0].notify(None)
        self.assertEqual(ran, [])

        # A description and an action touch the frame only from inside that callback.
        inside, touched, replies = [], [], []

        def call_back(task, _data):
            inside.append(True)
            task.notify(None)
            inside.pop()
        instance = actions.Broker.__new__(actions.Broker)
        instance.main = SimpleNamespace(addCallback=call_back)
        instance.frame = lambda *_arguments, **_options: SimpleNamespace(
            activate=lambda: touched.append(("activate", bool(inside))))
        instance.enabled = lambda _frame, name: touched.append((name, bool(inside))) or True
        instance.dispatcher = SimpleNamespace(executeDispatch=lambda *arguments: replies.append(arguments[1]))
        invocation = SimpleNamespace(return_value=replies.append, return_dbus_error=lambda *error: replies.append(error))
        instance.call(None, ":1.7", None, None, "Describe",
                      SimpleNamespace(unpack=lambda: (1, 2, "window", "token")), invocation)
        instance.call(None, ":1.7", None, None, "Activate",
                      SimpleNamespace(unpack=lambda: (1, 2, "window", "save", "token")), invocation)
        self.assertEqual([name for name, _on_main in touched], [*actions.COMMANDS, "activate", "save"])
        self.assertTrue(all(on_main for _name, on_main in touched))
        self.assertEqual(replies[1], ".uno:Save")
        self.assertEqual(len(replies), 3)

    def test_reused_pid_and_other_session_are_not_accepted_as_live_helpers(self):
        launch = runtime()
        with tempfile.TemporaryDirectory() as directory:
            root, proc = Path(directory) / "session", Path(directory) / "proc"
            process = proc / "123"
            process.mkdir(parents=True)
            process.joinpath("cmdline").write_bytes(b"/usr/bin/python3\0/runtime/native-header/actions.py\0legacy-channel\0")
            process.joinpath("environ").write_bytes(b"NORVI_OFFICE_SESSION_DIR=" + str(root).encode() + b"\0")
            record = {"broker": 123, "pipe": "legacy-channel"}
            self.assertTrue(launch.helper_alive(root, record, "broker", proc))
            self.assertFalse(launch.helper_alive(root, {**record, "pipe": "another-channel"}, "broker", proc))
            self.assertFalse(launch.helper_alive(root, record, "geometry", proc))
            process.joinpath("environ").write_bytes(b"NORVI_OFFICE_SESSION_DIR=/another/session\0")
            self.assertFalse(launch.helper_alive(root, record, "broker", proc))
            process.joinpath("environ").write_bytes(b"NORVI_OFFICE_SESSION_DIR=" + str(root).encode() + b"\0")
            process.joinpath("cmdline").write_bytes(b"/usr/bin/python3\0/other/native-header/unrelated.py\0")
            self.assertFalse(launch.helper_alive(root, record, "broker", proc))
            process.joinpath("cmdline").write_bytes(b"")
            self.assertFalse(launch.helper_alive(root, record, "broker", proc))
            self.assertFalse(launch.helper_alive(root, {"broker": True}, "broker", proc))

    def test_missing_broker_recovers_using_running_legacy_channel_and_preserves_live_geometry(self):
        launch = runtime()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = {"office_group": 100, "pipe": "legacy-desktop-channel", "broker": 111, "geometry": 222}
            env = {"NORVI_OFFICE_SESSION_DIR": str(root)}
            with patch.object(launch, "helper_alive", side_effect=lambda _root, _record, role: role == "geometry"), \
                    patch.object(launch.subprocess, "Popen", return_value=SimpleNamespace(pid=333)) as spawn:
                launch.ensure_helpers(root, record, env)
            self.assertEqual(record["broker"], 333)
            self.assertEqual(record["geometry"], 222)
            arguments = spawn.call_args.args[0]
            self.assertEqual(arguments[-2:], [str(launch.HEADER / "actions.py"), "legacy-desktop-channel"])
            self.assertEqual(json.loads((root / "running.json").read_text()), record)

    def test_partial_helper_recovery_is_recorded_for_next_launch(self):
        launch = runtime()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = {"office_group": 100, "pipe": "private-channel"}
            with patch.object(launch, "helper_alive", return_value=False), \
                    patch.object(launch.subprocess, "Popen", side_effect=[SimpleNamespace(pid=333), OSError("spawn failed")]):
                with self.assertRaises(OSError):
                    launch.ensure_helpers(root, record, {})
            saved = json.loads((root / "running.json").read_text())
            self.assertEqual(saved["broker"], 333)
            self.assertNotIn("geometry", saved)

    def test_reused_service_profile_is_verified_before_helpers_or_documents(self):
        launch = runtime()
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            root = state / "norvi-office/desktop"
            root.mkdir(parents=True)
            profile = root / "profile-calc"
            (root / "running.json").write_text(json.dumps({"pipe": "legacy-channel"}))
            with patch.dict(launch.os.environ, {"XDG_STATE_HOME": str(state)}), \
                    patch.object(launch, "qualified", return_value=True), \
                    patch.object(launch, "initialize", return_value=profile), \
                    patch.object(launch, "running", return_value=True), \
                    patch.object(launch, "connect", side_effect=RuntimeError("wrong profile")) as connect, \
                    patch.object(launch, "ensure_helpers") as helpers, \
                    patch.object(launch.subprocess, "Popen") as spawn:
                with self.assertRaises(RuntimeError):
                    launch.launch("calc", ["/tmp/example.ods"])
            connect.assert_called_once_with("legacy-channel", profile)
            helpers.assert_not_called()
            spawn.assert_not_called()

    def test_parallel_profiles_have_distinct_header_bus_names(self):
        launch = runtime()
        first = launch.service_bus(Path("/tmp/first-profile"))
        self.assertEqual(first, launch.service_bus(Path("/tmp/first-profile")))
        self.assertNotEqual(first, launch.service_bus(Path("/tmp/second-profile")))
        self.assertTrue(first.rsplit(".", 1)[1].startswith("p"))
