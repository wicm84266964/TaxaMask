import tempfile
import unittest
from pathlib import Path

from PIL import Image

from AntSleap.core.stl_project import STL_PROJECT_SCHEMA_VERSION, STL_PROJECT_TYPE, StlRenderedProjectManager


class StlProjectTests(unittest.TestCase):
    def test_import_rendered_view_directory_groups_and_copies_views(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            Image.new("RGB", (32, 24), "red").save(source / "01_0101_02_dorsal.png")
            Image.new("RGB", (32, 24), "blue").save(source / "01_0101_02_lateral.png")
            Image.new("RGB", (20, 20), "green").save(source / "not_a_view.png")

            manager = StlRenderedProjectManager()
            path = manager.create_project("stl_views", root / "project", known_views=["dorsal", "lateral"])
            result = manager.import_rendered_view_directory(source, copy_files=True)
            self.assertEqual(manager.project_data["schema_version"], STL_PROJECT_SCHEMA_VERSION)
            self.assertEqual(manager.project_data["project_type"], STL_PROJECT_TYPE)
            self.assertEqual(result["report"]["specimen_count"], 1)
            self.assertEqual(len(result["report"]["unparsed"]), 1)
            specimen = manager.project_data["specimens"][0]
            self.assertEqual(sorted(specimen["views"].keys()), ["dorsal", "lateral"])
            for view in specimen["views"].values():
                self.assertTrue((Path(manager.project_dir) / view["path"]).exists())

            reloaded = StlRenderedProjectManager()
            reloaded.load_project(path)
            self.assertEqual(reloaded.project_data["specimens"][0]["specimen_id"], "01_0101_02")


if __name__ == "__main__":
    unittest.main()
