import importlib.util
import json
from pathlib import Path
import sys
import tempfile
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


class NativeHelperTests(unittest.TestCase):
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
