import unittest
from types import SimpleNamespace

from routing import COMMANDS, matching_frame, uses_pipe


class Frame:
    def __init__(self, handle, title="Same caption"):
        self.handle, self.title = handle, title

    def getContainerWindow(self):
        return self

    def getWindowHandle(self, _process, _system):
        return SimpleNamespace(WindowHandle=self.handle)


class RoutingTests(unittest.TestCase):
    def test_duplicate_captions_do_not_select_the_wrong_document(self):
        first, second = Frame(120), Frame(240)
        self.assertIs(matching_frame([first, second], 240), second)

    def test_caption_changes_do_not_change_identity(self):
        target = Frame(120, "Renamed document")
        self.assertIs(matching_frame([target], 120), target)

    def test_signed_legacy_handle_matches_the_native_surface(self):
        target = Frame(-552683328)
        self.assertIs(matching_frame([target], 0x6486DF0EB8C0), target)

    def test_ambiguous_legacy_handles_fail_closed(self):
        self.assertIsNone(matching_frame([Frame(120), Frame(120)], 0x100000078))

    def test_unknown_handle_does_not_fall_back_to_focus(self):
        self.assertIsNone(matching_frame([Frame(120)], 240))

    def test_invalid_identity_is_rejected(self):
        for value in (None, 0, -1, "120", 0x100000000):
            with self.subTest(value=value):
                self.assertIsNone(matching_frame([Frame(120)], value))

    def test_disposed_frame_is_ignored(self):
        class Closed(Frame):
            def getContainerWindow(self):
                raise RuntimeError("disposed")
        target = Frame(240)
        self.assertIs(matching_frame([Closed(120), target], 240), target)

    def test_only_the_five_header_actions_are_brokered(self):
        self.assertEqual(set(COMMANDS), {"open", "save", "undo", "redo", "settings"})
        self.assertNotIn("close", COMMANDS)

    def test_caller_must_own_the_exact_private_pipe(self):
        self.assertTrue(uses_pipe(b"soffice.bin\0--accept=pipe,name=example;urp;\0", "example"))
        self.assertFalse(uses_pipe(b"soffice.bin\0--accept=pipe,name=example-other;urp;\0", "example"))
        self.assertFalse(uses_pipe(b"other\0comment --accept=pipe,name=example;urp;\0", "example"))


if __name__ == "__main__":
    unittest.main()
