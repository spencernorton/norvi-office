import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("render_qualification", ROOT / "norvi-office/experiments/desktop/qualify_render.py")
QUALIFICATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(QUALIFICATION)
API = SimpleNamespace(Role=SimpleNamespace(DOCUMENT_TEXT="document", TABLE="table", PAGE_TAB="tab", PAGE_TAB_LIST="tabs"),
                      StateType=SimpleNamespace(SELECTED="selected"))


class Node:
    def __init__(self, name="", role="container", children=(), selected=False, accept=True):
        self.name, self.role, self.children = name, role, list(children)
        self.selected, self.accept = selected, accept
        self.activations = 0

    def get_name(self):
        return self.name

    def get_role(self):
        return self.role

    def get_child_count(self):
        return len(self.children)

    def get_child_at_index(self, index):
        return self.children[index]

    def get_state_set(self):
        return SimpleNamespace(contains=lambda _state: self.selected)

    def get_action_iface(self):
        def activate(_index):
            self.activations += 1
            return self.accept
        return SimpleNamespace(get_n_actions=lambda: 1, do_action=activate)


class RenderQualificationTests(unittest.TestCase):
    def test_an_unchanged_or_rejected_tab_cannot_qualify_as_a_transition(self):
        home, insert = Node("Home", "tab", selected=True), Node("Insert", "tab", accept=False)
        frame = Node(children=[Node(role="tabs", children=[home, insert, Node("Layout", "tab")])])
        with self.assertRaises(AssertionError):
            QUALIFICATION.activate_tab(frame, "Home", API)
        self.assertEqual(home.activations, 0)
        with self.assertRaises(AssertionError):
            QUALIFICATION.activate_tab(frame, "Insert", API)
        self.assertEqual(insert.activations, 1)
        self.assertEqual(QUALIFICATION.selected_tab(frame, API), "Home")

    def test_document_content_cannot_impersonate_a_notebook_tab(self):
        home, insert = Node("Home", "tab", selected=True), Node("Insert", "tab")
        fake = Node("Insert", "tab", selected=True)
        frame = Node(children=[Node(role="tabs", children=[home, insert, Node("Layout", "tab")]),
                               Node(role="document", children=[fake])])
        self.assertEqual(QUALIFICATION.activate_tab(frame, "Insert", API), "Home")
        self.assertEqual(insert.activations, 1)
        self.assertEqual(fake.activations, 0)
        home.selected, insert.selected = False, True
        self.assertEqual(QUALIFICATION.selected_tab(frame, API), "Insert")

    def test_ambiguous_or_missing_tab_selection_fails_acceptance(self):
        for children in ([], [Node(role="tabs", children=[Node("Home", "tab", selected=True),
                                                         Node("Insert", "tab", selected=True), Node("Layout", "tab")])]):
            with self.subTest(children=children), self.assertRaises(AssertionError):
                QUALIFICATION.selected_tab(Node(children=children), API)

    def test_independent_selected_sheet_tab_is_not_a_ribbon_selection(self):
        home, insert = Node("Home", "tab", selected=True), Node("Insert", "tab")
        sheet = Node("Sheet1", "tab", selected=True)
        frame = Node(children=[Node(role="tabs", children=[home, insert, Node("Layout", "tab")]),
                               Node(role="tabs", children=[sheet])])
        self.assertEqual(QUALIFICATION.selected_tab(frame, API), "Home")
        self.assertEqual(QUALIFICATION.activate_tab(frame, "Insert", API), "Home")
        self.assertEqual(sheet.activations, 0)


if __name__ == "__main__":
    unittest.main()
