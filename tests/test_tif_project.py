import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from AntSleap.core.tif_materials import read_material_map
from AntSleap.core.tif_project import TIF_PROJECT_SCHEMA_VERSION, TIF_PROJECT_TYPE, TifProjectManager
from AntSleap.core.tif_volume_io import (
    VOLUME_SIDECAR_FORMAT,
    create_empty_label_sidecar_like,
    load_volume_sidecar,
    write_volume_sidecar,
)


class TifProjectTests(unittest.TestCase):
    def test_tif_project_saves_reopens_and_tracks_train_ready_specimen(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "brain_project"
            manager = TifProjectManager()
            project_json = manager.create_project("brain_project", project_root)
            specimen = manager.create_specimen_scaffold(
                "01-0101-02",
                modality="confocal",
                material_map={
                    "source": "manual",
                    "materials": [
                        {"id": 0, "name": "background", "display_name": "Background", "trainable": False},
                        {"id": 1, "name": "LO_L", "display_name": "LO_L", "color": "#ff4b4b", "trainable": True},
                    ],
                },
            )

            image_rel = "specimens/01-0101-02/working/image.ome.zarr"
            manual_rel = "specimens/01-0101-02/labels/manual_truth.ome.zarr"
            image_meta = write_volume_sidecar(
                project_root / image_rel,
                np.zeros((3, 4, 5), dtype=np.uint8),
                role="working_image",
                source_format="unit_test",
            )
            manual_meta = write_volume_sidecar(
                project_root / manual_rel,
                np.ones((3, 4, 5), dtype=np.uint16),
                role="manual_truth",
                source_format="unit_test",
            )

            manager.register_working_volume(
                "01-0101-02",
                image_rel,
                image_meta["shape_zyx"],
                image_meta["dtype"],
                fmt=VOLUME_SIDECAR_FORMAT,
                save=False,
            )
            manager.register_label_volume(
                "01-0101-02",
                "manual_truth",
                manual_rel,
                manual_meta["shape_zyx"],
                manual_meta["dtype"],
                status="reviewed",
                fmt=VOLUME_SIDECAR_FORMAT,
                save=False,
            )
            manager.set_review_status("01-0101-02", "train_ready", train_ready=True)

            reloaded = TifProjectManager()
            reloaded.load_project(project_json)
            loaded_specimen = reloaded.get_specimen("01-0101-02")
            readiness = reloaded.evaluate_train_ready("01-0101-02")

            self.assertEqual(reloaded.project_data["schema_version"], TIF_PROJECT_SCHEMA_VERSION)
            self.assertEqual(reloaded.project_data["project_type"], TIF_PROJECT_TYPE)
            self.assertEqual(loaded_specimen["modality"], "confocal")
            self.assertEqual(loaded_specimen["working_volume"]["shape_zyx"], [3, 4, 5])
            self.assertTrue(readiness["train_ready"])
            self.assertEqual(readiness["reasons"], [])
            self.assertEqual(len(reloaded.list_train_ready_specimens()), 1)
            self.assertTrue((project_root / specimen["material_map"]).exists())

    def test_train_ready_reports_missing_truth_and_material_risks(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "empty_tif_project"
            manager = TifProjectManager()
            manager.create_project("empty_tif_project", project_root)
            manager.create_specimen_scaffold(
                "01-0101-03",
                material_map={
                    "materials": [
                        {"id": 0, "name": "background", "display_name": "Background", "trainable": False}
                    ]
                },
            )

            image_rel = "specimens/01-0101-03/working/image.ome.zarr"
            image_meta = write_volume_sidecar(project_root / image_rel, np.zeros((2, 2, 2), dtype=np.uint8), role="working_image")
            manager.register_working_volume(
                "01-0101-03",
                image_rel,
                image_meta["shape_zyx"],
                image_meta["dtype"],
                save=False,
            )
            manager.set_review_status("01-0101-03", "train_ready", train_ready=True)

            readiness = manager.evaluate_train_ready("01-0101-03")

            self.assertFalse(readiness["train_ready"])
            self.assertIn("manual_truth_missing", readiness["reasons"])
            self.assertIn("image_label_shape_mismatch", readiness["reasons"])
            self.assertIn("no_trainable_material", readiness["reasons"])

    def test_empty_working_edit_sidecar_can_be_created_from_image_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            image_dir = Path(tmp) / "image.ome.zarr"
            edit_dir = Path(tmp) / "working_edit.ome.zarr"
            image_meta = write_volume_sidecar(image_dir, np.zeros((4, 5, 6), dtype=np.uint8), role="working_image")
            edit_meta = create_empty_label_sidecar_like(image_dir, edit_dir)

            self.assertEqual(edit_meta["shape_zyx"], image_meta["shape_zyx"])
            self.assertEqual(edit_meta["role"], "working_edit")

    def test_material_map_preserves_background_and_trainable_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = TifProjectManager()
            manager.create_project("materials", Path(tmp) / "materials")
            specimen = manager.create_specimen_scaffold(
                "01-0101-04",
                material_map={
                    "source": "manual",
                    "materials": [
                        {"id": 3, "name": "MB", "display_name": "Mushroom body", "trainable": True}
                    ],
                },
            )

            material_map = read_material_map(Path(manager.project_dir) / specimen["material_map"])
            ids = [item["id"] for item in material_map["materials"]]

            self.assertEqual(ids, [0, 3])
            self.assertFalse(material_map["materials"][0]["trainable"])
            self.assertTrue(material_map["materials"][1]["trainable"])

    def test_working_edit_promotion_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "promotion"
            manager = TifProjectManager()
            manager.create_project("promotion", project_root)
            manager.create_specimen_scaffold(
                "01-0101-09",
                material_map={
                    "materials": [
                        {"id": 0, "name": "background", "display_name": "Background", "trainable": False},
                        {"id": 2, "name": "LO_L", "display_name": "LO_L", "trainable": True},
                    ]
                },
            )
            image_rel = "specimens/01-0101-09/working/image.ome.zarr"
            edit_rel = "specimens/01-0101-09/labels/working_edit.ome.zarr"
            manual_rel = "specimens/01-0101-09/labels/manual_truth.ome.zarr"
            image_meta = write_volume_sidecar(project_root / image_rel, np.zeros((2, 3, 4), dtype=np.uint8), role="working_image")
            edit_array = np.zeros((2, 3, 4), dtype=np.uint16)
            edit_array[0, 1, 1] = 2
            edit_meta = write_volume_sidecar(project_root / edit_rel, edit_array, role="working_edit")
            manager.register_working_volume("01-0101-09", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            manager.register_label_volume("01-0101-09", "working_edit", edit_rel, edit_meta["shape_zyx"], edit_meta["dtype"], save=False)
            manager.save_project()

            self.assertFalse(manager.evaluate_train_ready("01-0101-09")["train_ready"])
            manager.promote_working_edit_to_manual_truth("01-0101-09")

            specimen = manager.get_specimen("01-0101-09")
            self.assertEqual(specimen["labels"]["manual_truth"]["path"], manual_rel)
            self.assertTrue(manager.evaluate_train_ready("01-0101-09")["train_ready"])
            np.testing.assert_array_equal(load_volume_sidecar(project_root / manual_rel), edit_array)

    def test_non_ready_status_clears_train_ready_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "status_sync"
            manager = TifProjectManager()
            manager.create_project("status_sync", project_root)
            manager.create_specimen_scaffold(
                "01-0101-15",
                material_map={
                    "materials": [
                        {"id": 0, "name": "background", "display_name": "Background", "trainable": False},
                        {"id": 2, "name": "brain", "display_name": "Brain", "trainable": True},
                    ]
                },
            )
            image_rel = "specimens/01-0101-15/working/image.ome.zarr"
            manual_rel = "specimens/01-0101-15/labels/manual_truth.ome.zarr"
            image_meta = write_volume_sidecar(project_root / image_rel, np.zeros((2, 3, 4), dtype=np.uint8), role="working_image")
            manual_meta = write_volume_sidecar(project_root / manual_rel, np.ones((2, 3, 4), dtype=np.uint16), role="manual_truth")
            manager.register_working_volume("01-0101-15", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            manager.register_label_volume("01-0101-15", "manual_truth", manual_rel, manual_meta["shape_zyx"], manual_meta["dtype"], save=False)

            manager.set_review_status("01-0101-15", "train_ready")
            self.assertTrue(manager.evaluate_train_ready("01-0101-15")["train_ready"])
            manager.set_review_status("01-0101-15", "in_progress")

            specimen = manager.get_specimen("01-0101-15")
            self.assertFalse(specimen["train_ready"])
            readiness = manager.evaluate_train_ready("01-0101-15")
            self.assertFalse(readiness["train_ready"])
            self.assertIn("specimen_not_marked_train_ready", readiness["reasons"])

    def test_copy_label_layer_refuses_same_source_and_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "same_path"
            manager = TifProjectManager()
            manager.create_project("same_path", project_root)
            manager.create_specimen_scaffold(
                "01-0101-16",
                material_map={
                    "materials": [
                        {"id": 0, "name": "background", "display_name": "Background", "trainable": False},
                        {"id": 3, "name": "brain", "display_name": "Brain", "trainable": True},
                    ]
                },
            )
            shared_rel = "specimens/01-0101-16/labels/shared.ome.zarr"
            meta = write_volume_sidecar(project_root / shared_rel, np.ones((2, 3, 4), dtype=np.uint16), role="manual_truth")
            manager.register_label_volume("01-0101-16", "manual_truth", shared_rel, meta["shape_zyx"], meta["dtype"], save=False)
            manager.register_label_volume("01-0101-16", "working_edit", shared_rel, meta["shape_zyx"], meta["dtype"], save=False)

            with self.assertRaisesRegex(ValueError, "source_target_label_same"):
                manager.copy_label_layer_to_working_edit("01-0101-16", source_role="manual_truth")
            self.assertTrue((project_root / shared_rel / "array.npy").exists())

            with self.assertRaisesRegex(ValueError, "working_edit_manual_truth_same_path"):
                manager.promote_working_edit_to_manual_truth("01-0101-16")
            self.assertTrue((project_root / shared_rel / "array.npy").exists())

    def test_specimen_ids_cannot_share_the_same_storage_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "storage_collision"
            manager = TifProjectManager()
            manager.create_project("storage_collision", project_root)
            manager.create_specimen_scaffold("A/B")

            with self.assertRaisesRegex(ValueError, "specimen_storage_path_collision"):
                manager.add_specimen("A?B")

    def test_import_refuses_to_reuse_non_empty_orphan_specimen_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "orphan_folder"
            manager = TifProjectManager()
            manager.create_project("orphan_folder", project_root)
            orphan_dir = project_root / "specimens" / "01-0101-17"
            orphan_dir.mkdir(parents=True)
            (orphan_dir / "leftover.txt").write_text("old data", encoding="utf-8")

            with self.assertRaisesRegex(FileExistsError, "specimen_storage_dir_not_empty"):
                manager.create_specimen_scaffold("01-0101-17")

            self.assertIsNone(manager.get_specimen("01-0101-17", default=None))

    def test_dot_only_specimen_id_cannot_escape_specimens_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "dot_path"
            manager = TifProjectManager()
            manager.create_project("dot_path", project_root)
            manager.create_specimen_scaffold("..")

            specimen = manager.get_specimen("..")
            self.assertIsNotNone(specimen)
            self.assertEqual(specimen["material_map"], "specimens/specimen/material_map.json")
            self.assertTrue((project_root / "specimens" / "specimen" / "material_map.json").exists())

    def test_scaffold_creation_failure_rolls_back_specimen_and_storage(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "scaffold_rollback"
            manager = TifProjectManager()
            manager.create_project("scaffold_rollback", project_root)

            with patch("AntSleap.core.tif_project.write_material_map", side_effect=RuntimeError("material map failed")):
                with self.assertRaisesRegex(RuntimeError, "material map failed"):
                    manager.create_specimen_scaffold("01-0101-18")

            self.assertIsNone(manager.get_specimen("01-0101-18", default=None))
            self.assertFalse((project_root / "specimens" / "01-0101-18").exists())


if __name__ == "__main__":
    unittest.main()
