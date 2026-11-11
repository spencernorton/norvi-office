"""Boundary regressions for the preview's accessibility adapter."""
import unittest

from extension.geometry import Atspi, frame_geometry


class Node:
    def __init__(self, role, box, children=(), showing=True):
        self.role, self.box, self.nodes, self.showing = role, box, children, showing

    def get_role(self):
        return self.role

    def get_state_set(self):
        return self

    def contains(self, _state):
        return self.showing

    def get_component_iface(self):
        return self

    def get_extents(self, _coordinates):
        class Box:
            pass
        box = Box()
        box.x, box.y, box.width, box.height = self.box
        return box

    def get_child_count(self):
        if self.role == Atspi.Role.DOCUMENT_TEXT:
            raise AssertionError("must not traverse a document")
        return len(self.nodes)

    def get_child_at_index(self, index):
        return self.nodes[index]

    def get_name(self):
        return "Fictional sample"


def frame(body_y=177, extras=(), root_count=1, showing=True):
    work = Node(Atspi.Role.PANEL, [26, body_y, 1300, 734 - body_y], showing=showing)
    root = Node(Atspi.Role.ROOT_PANE, [26, 60, 1300, 698], [work, *extras])
    return Node(Atspi.Role.FRAME, [0, 0, 1352, 787], [root] * root_count)


class GeometryTests(unittest.TestCase):
    def test_follows_work_panel_after_toolbar_height_change(self):
        for y in (125, 177, 208, 240):
            with self.subTest(y=y):
                self.assertEqual(frame_geometry(frame(y), 42)["edge"], y - 1)

    def test_hidden_panel_has_no_boundary(self):
        self.assertIsNone(frame_geometry(frame(showing=False), 42))

    def test_ambiguous_main_panels_fail_opaque(self):
        extra = Node(Atspi.Role.PANEL, [26, 177, 1300, 557])
        self.assertIsNone(frame_geometry(frame(extras=[extra]), 42))

    def test_missing_or_ambiguous_root_fails_opaque(self):
        for count in (0, 2):
            with self.subTest(count=count):
                self.assertIsNone(frame_geometry(frame(root_count=count), 42))

    def test_does_not_read_document_children(self):
        document = Node(Atspi.Role.DOCUMENT_TEXT, [26, 177, 1300, 557])
        value = frame()
        value.nodes.append(document)
        self.assertIsNotNone(frame_geometry(value, 42))

    def test_out_of_bounds_panel_fails_opaque(self):
        for y in (-1, 10, 500):
            with self.subTest(y=y):
                self.assertIsNone(frame_geometry(frame(y), 42))

    def test_child_disappearing_during_layout_change(self):
        value = frame()
        value.nodes.insert(0, None)
        value.nodes[1].nodes.insert(0, None)
        self.assertIsNotNone(frame_geometry(value, 42))


if __name__ == "__main__":
    unittest.main()
