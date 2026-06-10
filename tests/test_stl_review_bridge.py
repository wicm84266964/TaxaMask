import tempfile
import unittest
from pathlib import Path

from PIL import Image

from AntSleap.core.project import ProjectManager
from AntSleap.core.stl_project import StlRenderedProjectManager
from AntSleap.core.stl_review_bridge import import_stl_rendered_views_into_2d_project, register_stl_rendered_views_for_2d_review


class StlReviewBridgeTests(unittest.TestCase):
    def test_registers_stl_views_into_existing_2d_review_project_with_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            Image.new("RGB", (32, 24), "red").save(source / "01_0101_02_dorsal.png")

            stl = StlRenderedProjectManager()
            stl.create_project("stl", root / "stl")
            stl.import_rendered_view_directory(source, copy_files=True, known_views=["dorsal"])
            project = ProjectManager()
            (root / "review").mkdir()
            project.create_project("review", root / "review", template_id="generic_taxonomy")

            result = register_stl_rendered_views_for_2d_review(stl, project)
            self.assertEqual(result["registered_count"], 1)
            image_path = project.project_data["images"][0]
            provenance = project.get_image_provenance(image_path)
            self.assertEqual(provenance["source_type"], "stl_rendered_view")
            label = project.project_data["labels"][image_path]
            self.assertEqual(label["view"], "dorsal")
            self.assertEqual(label["specimen_id"], "01_0101_02")
            self.assertEqual(label["review_mode"], "stl_rendered_view")

    def test_imports_rendered_view_directory_directly_into_2d_review_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            Image.new("RGB", (32, 24), "red").save(source / "01_0101_02_dorsal.png")
            Image.new("RGB", (32, 24), "blue").save(source / "01_0101_02_lateral.png")
            Image.new("RGB", (20, 20), "green").save(source / "not_a_view.png")

            project = ProjectManager()
            (root / "review").mkdir()
            project.create_project("review", root / "review", template_id="generic_taxonomy")

            result = import_stl_rendered_views_into_2d_project(project, source, known_views=["dorsal", "lateral"])

            self.assertEqual(result["registered_count"], 2)
            self.assertEqual(result["specimen_count"], 1)
            self.assertEqual(result["unparsed_count"], 1)
            self.assertEqual(len(project.project_data["images"]), 2)
            for image_path in project.project_data["images"]:
                provenance = project.get_image_provenance(image_path)
                self.assertEqual(provenance["source_type"], "stl_rendered_view")
                self.assertEqual(
                    provenance["workflow_note"],
                    "Surface morphology review uses rendered 2D views in the Labeling Workbench and Blink; TaxaMask does not write labels back to the source STL model.",
                )
                self.assertEqual(project.project_data["labels"][image_path]["review_mode"], "stl_rendered_view")


if __name__ == "__main__":
    unittest.main()
