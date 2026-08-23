import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from AntSleap.core.project import ProjectManager
from AntSleap.core.stl_project import StlRenderedProjectManager
from AntSleap.core.stl_review_bridge import (
    collect_stl_rendered_review_images,
    import_stl_rendered_views_into_2d_project,
    register_stl_rendered_views_for_2d_review,
)


class StlReviewBridgeTests(unittest.TestCase):
    def _project_and_stl_fixture(self, root, *, storage_backend="sqlite"):
        source = root / "source"
        source.mkdir()
        Image.new("RGB", (32, 24), "red").save(source / "01_0101_02_dorsal.png")
        stl = StlRenderedProjectManager()
        stl.create_project("stl", root / "stl")
        stl.import_rendered_view_directory(source, copy_files=True, known_views=["dorsal"])
        project = ProjectManager()
        (root / "review").mkdir()
        project.create_project(
            "review",
            root / "review",
            template_id="generic_taxonomy",
            storage_backend=storage_backend,
        )
        return stl, project

    @staticmethod
    def _sqlite_dump(database_path):
        connection = sqlite3.connect(database_path)
        try:
            return "\n".join(connection.iterdump())
        finally:
            connection.close()

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
                self.assertEqual(provenance["workflow_note"], "Surface morphology review uses the 2D Labeling Workbench and Blink; labels remain separate from TIF material IDs.")
                self.assertEqual(project.project_data["labels"][image_path]["review_mode"], "stl_rendered_view")

    def test_register_updates_existing_record_once_without_false_truth_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            stl, project = self._project_and_stl_fixture(Path(tmp))
            image_path = collect_stl_rendered_review_images(stl)[0]["path"]
            project.add_images([image_path])
            project.initialize_integrity_baseline()
            version_before = project.project_data["project_data_version_id"]

            with patch.object(
                project, "save_project", wraps=project.save_project
            ) as save_project, patch.object(
                project,
                "_mark_sqlite_label_dirty",
                wraps=project._mark_sqlite_label_dirty,
            ) as mark_label_dirty:
                result = register_stl_rendered_views_for_2d_review(stl, project)

            self.assertEqual(result["registered_count"], 1)
            save_project.assert_called_once_with()
            mark_label_dirty.assert_called_once_with(image_path)
            self.assertEqual(
                project.project_data["project_data_version_id"], version_before
            )
            self.assertEqual(project._pending_project_data_version_id, "")
            reloaded = ProjectManager()
            reloaded.load_project(project.current_project_path)
            reloaded_image = reloaded.project_data["images"][0]
            provenance = reloaded.get_image_provenance(reloaded_image)
            self.assertEqual(provenance["view_name"], "dorsal")
            self.assertEqual(provenance["specimen_id"], "01_0101_02")
            self.assertEqual(
                reloaded.project_data["labels"][reloaded_image]["review_mode"],
                "stl_rendered_view",
            )
            self.assertEqual(
                reloaded.project_data["labels"][reloaded_image]["view"],
                "dorsal",
            )
            self.assertEqual(
                reloaded.project_data["labels"][reloaded_image]["specimen_id"],
                "01_0101_02",
            )
            self.assertEqual(
                reloaded.project_data["labels"][reloaded_image]["metadata_ref"],
                "",
            )
            self.assertEqual(
                reloaded.project_data["project_data_version_id"],
                project.project_data["project_data_version_id"],
            )

    def test_register_new_source_advances_integrity_version_in_single_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            stl, project = self._project_and_stl_fixture(Path(tmp))
            project.initialize_integrity_baseline()
            version_before = project.project_data["project_data_version_id"]

            with patch.object(
                project, "save_project", wraps=project.save_project
            ) as save_project:
                register_stl_rendered_views_for_2d_review(stl, project)

            save_project.assert_called_once_with()
            self.assertNotEqual(
                project.project_data["project_data_version_id"], version_before
            )
            reloaded = ProjectManager()
            reloaded.load_project(project.current_project_path)
            image_path = reloaded.project_data["images"][0]
            self.assertEqual(
                reloaded.get_image_provenance(image_path)["source_type"],
                "stl_rendered_view",
            )

    def test_save_false_stages_without_changing_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            stl, project = self._project_and_stl_fixture(Path(tmp))
            runtime_before = project._snapshot_runtime_state(deep=True)
            database_before = self._sqlite_dump(project.current_database_path)

            result = register_stl_rendered_views_for_2d_review(
                stl, project, save=False
            )

            self.assertEqual(result["registered_count"], 1)
            self.assertEqual(len(project.project_data["images"]), 1)
            self.assertEqual(
                project.project_data["labels"][project.project_data["images"][0]][
                    "review_mode"
                ],
                "stl_rendered_view",
            )
            rollback_token = result["rollback_token"]
            self.assertTrue(rollback_token.active)
            image_key = project.project_data["images"][0]
            self.assertIn(image_key, project._sqlite_label_dirty_images)
            self.assertTrue(project._pending_project_data_version_id)
            self.assertEqual(
                self._sqlite_dump(project.current_database_path), database_before
            )
            reloaded = ProjectManager()
            reloaded.load_project(project.current_project_path)
            self.assertEqual(reloaded.project_data["images"], [])
            self.assertTrue(rollback_token.rollback())
            self.assertFalse(rollback_token.active)
            self.assertFalse(rollback_token.rollback())
            self.assertEqual(project._snapshot_runtime_state(deep=True), runtime_before)

    def test_sqlite_write_failure_restores_memory_and_transaction(self):
        from AntSleap.core import project_sqlite_writer

        with tempfile.TemporaryDirectory() as tmp:
            stl, project = self._project_and_stl_fixture(Path(tmp))
            runtime_before = project._snapshot_runtime_state(deep=True)
            database_before = self._sqlite_dump(project.current_database_path)
            original_write = project_sqlite_writer.write_image_state

            def write_then_fail(*args, **kwargs):
                original_write(*args, **kwargs)
                raise RuntimeError("injected sqlite bridge failure")

            with patch.object(
                project_sqlite_writer,
                "write_image_state",
                side_effect=write_then_fail,
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "injected sqlite bridge failure"
                ):
                    register_stl_rendered_views_for_2d_review(stl, project)

            self.assertEqual(
                project._snapshot_runtime_state(deep=True), runtime_before
            )
            self.assertEqual(
                self._sqlite_dump(project.current_database_path), database_before
            )

    def test_partial_add_failure_removes_already_staged_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            stl, project = self._project_and_stl_fixture(Path(tmp))
            runtime_before = project._snapshot_runtime_state(deep=True)
            original_add_images = project.add_images

            def add_then_fail(image_paths, **_kwargs):
                original_add_images([image_paths[0]], save=False)
                raise RuntimeError("injected partial add failure")

            with patch.object(project, "add_images", side_effect=add_then_fail):
                with self.assertRaisesRegex(
                    RuntimeError, "injected partial add failure"
                ):
                    register_stl_rendered_views_for_2d_review(stl, project)

            self.assertEqual(
                project._snapshot_runtime_state(deep=True), runtime_before
            )

    def test_json_replace_failure_restores_memory_and_project_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            stl, project = self._project_and_stl_fixture(
                Path(tmp), storage_backend="json"
            )
            runtime_before = project._snapshot_runtime_state(deep=True)
            project_path = Path(project.current_project_path)
            project_before = project_path.read_bytes()

            with patch(
                "AntSleap.core.project.os.replace",
                side_effect=OSError("injected json bridge failure"),
            ):
                with self.assertRaisesRegex(
                    OSError, "injected json bridge failure"
                ):
                    register_stl_rendered_views_for_2d_review(stl, project)

            self.assertEqual(
                project._snapshot_runtime_state(deep=True), runtime_before
            )
            self.assertEqual(project_path.read_bytes(), project_before)
            self.assertFalse(Path(f"{project_path}.tmp").exists())


if __name__ == "__main__":
    unittest.main()
