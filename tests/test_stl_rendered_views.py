import tempfile
import unittest
from pathlib import Path

from AntSleap.core.stl_rendered_views import build_stl_rendered_view_registry, parse_rendered_view_filename


class StlRenderedViewsTests(unittest.TestCase):
    def test_parse_rendered_view_filename_keeps_specimen_id_separate_from_view(self):
        parsed = parse_rendered_view_filename(r"C:\data\01-0101-02_dorsal.png")

        self.assertEqual(parsed["specimen_id"], "01_0101_02")
        self.assertEqual(parsed["view_name"], "dorsal")

    def test_registry_groups_views_by_specimen_and_reports_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = [
                root / "01-0101-02_dorsal.png",
                root / "01-0101-02_lateral.png",
                root / "01-0101-03_dorsal.png",
                root / "01-0101-03_unknownpose.png",
                root / "01-0101-02_dorsal_copy.png",
            ]
            for path in paths:
                path.write_bytes(b"")

            registry = build_stl_rendered_view_registry(paths, known_views=["dorsal", "lateral"])

            self.assertEqual(registry["schema_version"], "taxamask_stl_rendered_view_registry_v1")
            self.assertEqual(len(registry["specimens"]), 2)
            specimen = registry["specimens"][0]
            self.assertEqual(specimen["specimen_id"], "01_0101_02")
            self.assertEqual(sorted(specimen["views"].keys()), ["dorsal", "lateral"])
            self.assertEqual(len(registry["unparsed"]), 2)


if __name__ == "__main__":
    unittest.main()
