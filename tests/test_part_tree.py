import unittest

from AntSleap.core.part_tree import build_part_tree_groups


class PartTreeGroupingTests(unittest.TestCase):
    def test_locator_scope_parts_are_top_level_and_single_parent_children_nest(self):
        groups = build_part_tree_groups(
            ["Head", "Mesosoma", "Gaster", "Mandible", "Eye"],
            ["Head", "Mesosoma", "Gaster"],
            [{"parent": "Head", "child": "Mandible"}, {"parent": "Head", "child": "Eye"}],
        )

        self.assertEqual(
            groups["parents"],
            [
                {"part": "Head", "children": ["Mandible", "Eye"]},
                {"part": "Mesosoma", "children": []},
                {"part": "Gaster", "children": []},
            ],
        )
        self.assertEqual(groups["cross_region"], [])
        self.assertEqual(groups["ungrouped"], [])

    def test_multi_parent_children_stay_cross_region_instead_of_hiding_under_one_parent(self):
        groups = build_part_tree_groups(
            ["Head", "Mesosoma", "Gaster", "Seta"],
            ["Head", "Mesosoma", "Gaster"],
            [{"parent": "Head", "child": "Seta"}, {"parent": "Mesosoma", "child": "Seta"}],
        )

        self.assertEqual(groups["cross_region"], ["Seta"])
        self.assertEqual(groups["parents"][0], {"part": "Head", "children": []})
        self.assertEqual(groups["parents"][1], {"part": "Mesosoma", "children": []})

    def test_non_locator_route_parent_is_still_visible_as_parent(self):
        groups = build_part_tree_groups(
            ["Head", "Mandible", "Tooth"],
            ["Head"],
            [{"parent": "Mandible", "child": "Tooth"}],
        )

        self.assertEqual(
            groups["parents"],
            [
                {"part": "Head", "children": []},
                {"part": "Mandible", "children": ["Tooth"]},
            ],
        )
        self.assertEqual(groups["ungrouped"], [])

    def test_unrouted_non_locator_parts_are_ungrouped(self):
        groups = build_part_tree_groups(
            ["Head", "Mesosoma", "Gaster", "Wing"],
            ["Head", "Mesosoma", "Gaster"],
            [],
        )

        self.assertEqual(groups["ungrouped"], ["Wing"])

    def test_invalid_routes_do_not_duplicate_or_leak_unknown_parts(self):
        groups = build_part_tree_groups(
            ["Head", "Head", "Mandible"],
            ["Head"],
            [
                {"parent": "Head", "child": "Mandible"},
                {"parent": "Missing", "child": "Mandible"},
                {"parent": "Head", "child": "Missing"},
                {"parent": "Head", "child": "Head"},
            ],
        )

        self.assertEqual(groups["parents"], [{"part": "Head", "children": ["Mandible"]}])
        self.assertEqual(groups["cross_region"], [])
        self.assertEqual(groups["ungrouped"], [])


if __name__ == "__main__":
    unittest.main()
