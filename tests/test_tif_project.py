import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import tifffile

from AntSleap.core.tif_materials import read_material_map
from AntSleap.core.tif_part_extraction import (
    add_polygon_keyframe,
    add_rectangular_keyframe,
    build_preview_mask_from_contours,
    crop_volume_to_part,
    read_contours_json,
    validate_contours_for_interpolation,
)
from AntSleap.core.tif_local_axis_reslice import align_editable_axis_to_reference_plane
from AntSleap.core.tif_project import TIF_PROJECT_SCHEMA_VERSION, TIF_PROJECT_TYPE, TifProjectManager
from AntSleap.core.tif_volume_io import (
    VOLUME_SIDECAR_FORMAT,
    copy_volume_sidecar,
    create_empty_label_sidecar_like,
    load_volume_sidecar,
    read_volume_metadata,
    write_volume_sidecar,
)


class TifProjectTests(unittest.TestCase):
    def test_part_delete_save_failure_restores_record_roi_and_storage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_root = root / "part_delete_rollback"
            manager = TifProjectManager()
            manifest_path = manager.create_project("part_delete_rollback", project_root)
            manager.create_specimen_scaffold("specimen")
            image_rel = "specimens/specimen/working/image.ome.zarr"
            image_meta = write_volume_sidecar(
                project_root / image_rel,
                np.arange(3 * 4 * 5, dtype=np.uint8).reshape((3, 4, 5)),
                role="working_image",
            )
            manager.register_working_volume(
                "specimen",
                image_rel,
                image_meta["shape_zyx"],
                image_meta["dtype"],
            )
            crop_volume_to_part(manager, "specimen", "head", [[0, 2], [0, 3], [0, 4]])
            manager.add_part_roi(
                "specimen",
                "head-roi",
                bbox_zyx=[[0, 2], [0, 3], [0, 4]],
                status="part_created",
                linked_part_id="head",
            )
            specimen_before = copy.deepcopy(manager.get_specimen("specimen"))
            part_root = Path(manager.to_absolute(manager.part_dir("specimen", "head")))

            with patch.object(manager, "save_project", side_effect=RuntimeError("sqlite write failed")):
                with self.assertRaisesRegex(RuntimeError, "sqlite write failed"):
                    manager.discard_part(
                        "specimen",
                        "head",
                        remove_storage=True,
                        save=True,
                        unlink_linked_rois=True,
                    )

            self.assertEqual(manager.get_specimen("specimen"), specimen_before)
            self.assertTrue(part_root.exists())
            self.assertFalse(any("delete_pending" in path.name for path in part_root.parent.iterdir()))

            reloaded = TifProjectManager()
            reloaded.load_project(manifest_path)
            self.assertIsNotNone(reloaded.get_part("specimen", "head", default=None))
            roi = reloaded.get_part_roi("specimen", "head-roi")
            self.assertEqual(roi["linked_part_id"], "head")
            self.assertEqual(roi["status"], "part_created")

    def test_specimen_discard_save_failure_restores_record_and_storage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            manifest_path = manager.create_project("specimen_discard_rollback", root / "specimen_discard_rollback")
            manager.create_specimen_scaffold("specimen")
            specimen_root = Path(manager.to_absolute(manager.specimen_dir("specimen")))

            with patch.object(manager, "save_project", side_effect=RuntimeError("sqlite write failed")):
                with self.assertRaisesRegex(RuntimeError, "sqlite write failed"):
                    manager.discard_specimen_scaffold("specimen", save=True)

            self.assertIsNotNone(manager.get_specimen("specimen", default=None))
            self.assertTrue(specimen_root.exists())
            self.assertFalse(any("delete_pending" in path.name for path in specimen_root.parent.iterdir()))

            reloaded = TifProjectManager()
            reloaded.load_project(manifest_path)
            self.assertIsNotNone(reloaded.get_specimen("specimen", default=None))

    def test_sidecar_role_update_failure_preserves_existing_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.ome.zarr"
            target = root / "target.ome.zarr"
            source_array = np.full((2, 3, 4), 9, dtype=np.uint16)
            target_array = np.full((2, 3, 4), 3, dtype=np.uint16)
            write_volume_sidecar(source, source_array, role="editable_ai_result")
            write_volume_sidecar(target, target_array, role="manual_truth")

            with patch("AntSleap.core.tif_volume_io._write_volume_metadata", side_effect=RuntimeError("metadata write failed")):
                with self.assertRaisesRegex(RuntimeError, "metadata write failed"):
                    copy_volume_sidecar(source, target, role="manual_truth")

            np.testing.assert_array_equal(load_volume_sidecar(target), target_array)
            self.assertEqual(read_volume_metadata(target)["role"], "manual_truth")
            self.assertFalse(any(path.name.startswith(".tmp_sidecar_copy_") for path in root.iterdir()))

    def test_batch_truth_save_failure_restores_all_existing_manual_truth_sidecars(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "truth_batch_rollback"
            manager = TifProjectManager()
            manager.create_project("truth_batch_rollback", project_root)
            manager.create_specimen_scaffold("specimen")
            manager.add_or_update_label_schema(
                "regions",
                labels=[
                    {"id": 2, "name": "region_2"},
                    {"id": 3, "name": "region_3"},
                ],
                save=False,
            )
            expected_manual = {}
            refs = []
            for index, part_id in enumerate(("head", "thorax"), start=2):
                image_rel = f"specimens/specimen/parts/{part_id}/image.ome.zarr"
                manual_rel = f"specimens/specimen/parts/{part_id}/labels/manual_truth.ome.zarr"
                edit_rel = f"specimens/specimen/parts/{part_id}/labels/editable_ai_result.ome.zarr"
                image_meta = write_volume_sidecar(
                    project_root / image_rel,
                    np.zeros((2, 3, 4), dtype=np.uint8),
                    role="part_image",
                )
                manual_array = np.full((2, 3, 4), index + 5, dtype=np.uint16)
                edit_array = np.full((2, 3, 4), index, dtype=np.uint16)
                manual_meta = write_volume_sidecar(project_root / manual_rel, manual_array, role="manual_truth")
                edit_meta = write_volume_sidecar(project_root / edit_rel, edit_array, role="editable_ai_result")
                manager.add_part(
                    "specimen",
                    part_id,
                    image={"path": image_rel, **image_meta},
                    save=False,
                )
                manager.register_part_label_volume(
                    "specimen",
                    part_id,
                    "manual_truth",
                    manual_rel,
                    manual_meta["shape_zyx"],
                    manual_meta["dtype"],
                    explicit_review=True,
                    operation="truth_promotion",
                    audit_metadata={"review_action": "test_existing_truth"},
                    save=False,
                )
                manager.register_part_label_volume(
                    "specimen",
                    part_id,
                    "editable_ai_result",
                    edit_rel,
                    edit_meta["shape_zyx"],
                    edit_meta["dtype"],
                    status="pending_review",
                    save=False,
                )
                manager.set_part_training_metadata(
                    "specimen",
                    part_id,
                    label_schema_id="regions",
                    opened_for_review=True,
                    save=False,
                )
                expected_manual[part_id] = manual_array
                refs.append({"specimen_id": "specimen", "part_id": part_id})
            manager.save_project()
            project_snapshot = copy.deepcopy(manager.project_data)

            with patch.object(manager, "save_project", side_effect=RuntimeError("sqlite write failed")):
                with self.assertRaisesRegex(RuntimeError, "sqlite write failed"):
                    manager.promote_reviewed_part_results_to_manual_truth(
                        refs,
                        require_opened_for_review=True,
                        save=True,
                    )

            self.assertEqual(manager.project_data, project_snapshot)
            for part_id, expected in expected_manual.items():
                manual_path = project_root / manager.get_part("specimen", part_id)["labels"]["manual_truth"]["path"]
                np.testing.assert_array_equal(load_volume_sidecar(manual_path), expected)
                self.assertFalse(
                    any(
                        marker in path.name
                        for path in manual_path.parent.iterdir()
                        for marker in (".pending_", ".rollback_")
                    )
                )

    def test_align_editable_axis_to_three_point_reference_plane(self):
        editable_axis = {
            "axis_id": "local_output_z_axis",
            "start_zyx": [1.0, 4.0, 4.0],
            "end_zyx": [5.0, 4.0, 4.0],
        }
        roll_reference = {
            "point_a": {"role": "roll_reference_a", "zyx": [3.0, 1.0, 1.0]},
            "point_b": {"role": "roll_reference_b", "zyx": [3.0, 6.0, 1.0]},
            "point_c": {"role": "reference_plane_c", "zyx": [5.0, 1.0, 6.0]},
        }

        aligned, plane = align_editable_axis_to_reference_plane(
            editable_axis,
            roll_reference,
            spacing_zyx=[2.0, 1.0, 1.0],
            shape_zyx=[7, 8, 8],
        )

        start = np.asarray(aligned["start_zyx"], dtype=np.float64)
        end = np.asarray(aligned["end_zyx"], dtype=np.float64)
        axis_world = (end - start) * np.asarray([2.0, 1.0, 1.0], dtype=np.float64)
        axis_world /= np.linalg.norm(axis_world)
        normal_world = np.asarray(plane["normal_world_zyx"], dtype=np.float64)

        self.assertEqual(aligned["derived_from"], "three_point_reference_plane")
        self.assertIn("reference_plane", aligned)
        self.assertAlmostEqual(abs(float(np.dot(axis_world, normal_world))), 1.0, places=5)

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
            self.assertEqual(readiness["reasons"].count("manual_truth_missing"), 1)
            self.assertNotIn("image_label_shape_mismatch", readiness["reasons"])
            self.assertIn("no_trainable_material", readiness["reasons"])


    def test_train_ready_reports_shape_mismatch_only_when_truth_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "shape_mismatch_project"
            manager = TifProjectManager()
            manager.create_project("shape_mismatch_project", project_root)
            manager.create_specimen_scaffold(
                "01-0101-03b",
                material_map={
                    "materials": [
                        {"id": 0, "name": "background", "display_name": "Background", "trainable": False},
                        {"id": 1, "name": "brain", "display_name": "Brain", "trainable": True},
                    ]
                },
            )
            image_rel = "specimens/01-0101-03b/working/image.ome.zarr"
            truth_rel = "specimens/01-0101-03b/labels/manual_truth.ome.zarr"
            image_meta = write_volume_sidecar(project_root / image_rel, np.zeros((2, 2, 2), dtype=np.uint8), role="working_image")
            truth_meta = write_volume_sidecar(project_root / truth_rel, np.zeros((3, 2, 2), dtype=np.uint16), role="manual_truth")
            manager.register_working_volume("01-0101-03b", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            manager.register_label_volume("01-0101-03b", "manual_truth", truth_rel, truth_meta["shape_zyx"], truth_meta["dtype"], save=False)
            manager.set_review_status("01-0101-03b", "train_ready", train_ready=True)

            readiness = manager.evaluate_train_ready("01-0101-03b")

            self.assertIn("image_label_shape_mismatch", readiness["reasons"])
            self.assertNotIn("manual_truth_missing", readiness["reasons"])

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

    def test_corrupt_material_map_does_not_erase_last_valid_sqlite_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            manager.create_project("material_map_rollback", root / "material_map_rollback")
            specimen = manager.create_specimen_scaffold(
                "specimen",
                material_map={
                    "source": "manual",
                    "materials": [
                        {"id": 0, "name": "background", "trainable": False},
                        {"id": 2, "name": "brain", "trainable": True},
                    ],
                },
            )
            material_path = Path(manager.to_absolute(specimen["material_map"]))
            connection = sqlite3.connect(manager.current_database_path)
            try:
                materials_before = connection.execute("SELECT materials_json FROM material_maps").fetchone()[0]
            finally:
                connection.close()

            material_path.write_text("{not valid json", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "tif_material_map_read_failed"):
                manager.save_project()

            connection = sqlite3.connect(manager.current_database_path)
            try:
                materials_after = connection.execute("SELECT materials_json FROM material_maps").fetchone()[0]
            finally:
                connection.close()
            self.assertEqual(materials_after, materials_before)

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

    def test_raw_backup_cannot_be_promoted_to_manual_truth(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "raw_backup_truth_guard"
            manager = TifProjectManager()
            manager.create_project("raw_backup_truth_guard", project_root)
            manager.create_specimen_scaffold("01-0101-raw")
            part_image_rel = "specimens/01-0101-raw/parts/brain/image.ome.zarr"
            backup_rel = "specimens/01-0101-raw/parts/brain/labels/raw_ai_prediction_backup.ome.zarr"
            part_meta = write_volume_sidecar(project_root / part_image_rel, np.zeros((2, 3, 4), dtype=np.uint8), role="part_image")
            backup_meta = write_volume_sidecar(project_root / backup_rel, np.ones((2, 3, 4), dtype=np.uint16), role="raw_ai_prediction_backup")
            manager.add_part("01-0101-raw", "brain", image={"path": part_image_rel, **part_meta}, save=False)
            manager.register_part_label_volume(
                "01-0101-raw",
                "brain",
                "raw_ai_prediction_backup",
                backup_rel,
                backup_meta["shape_zyx"],
                backup_meta["dtype"],
                operation="prediction_raw_backup_import",
                audit_metadata={"prediction_id": "p1"},
                save=True,
            )

            with self.assertRaisesRegex(ValueError, "raw_ai_prediction_backup_cannot_be_promoted_to_manual_truth"):
                manager.promote_part_editable_result_to_manual_truth(
                    "01-0101-raw",
                    "brain",
                    source_role="raw_ai_prediction_backup",
                )

            self.assertFalse((manager.get_part("01-0101-raw", "brain")["labels"]["manual_truth"] or {}).get("path"))

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

    def test_old_tif_project_load_adds_empty_parts_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "old_project"
            manager = TifProjectManager()
            project_json = manager.create_project("old_project", project_root)
            manager.add_specimen("01-0101-old", save=True)
            payload_path = Path(project_json)
            payload = payload_path.read_text(encoding="utf-8")
            payload = payload.replace(',\n      "parts": []', "")
            payload_path.write_text(payload, encoding="utf-8")

            reloaded = TifProjectManager()
            reloaded.load_project(project_json)

            self.assertEqual(reloaded.get_specimen("01-0101-old")["parts"], [])
            self.assertEqual(reloaded.get_specimen("01-0101-old")["part_rois"], [])

    def test_part_roi_drafts_round_trip_and_cancel_without_touching_parts(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "roi_project"
            manager = TifProjectManager()
            project_json = manager.create_project("roi_project", project_root)
            manager.create_specimen_scaffold("01-0101-roi")
            roi = manager.add_part_roi(
                "01-0101-roi",
                "head_roi",
                display_name="Head ROI",
                bbox_zyx=[[1, 3], [2, 5], [1, 4]],
            )

            reloaded = TifProjectManager()
            reloaded.load_project(project_json)
            loaded = reloaded.get_part_roi("01-0101-roi", "head_roi")

            self.assertEqual(roi["status"], "draft")
            self.assertEqual(loaded["bbox_zyx"], [[1, 3], [2, 5], [1, 4]])
            self.assertEqual(len(reloaded.list_part_rois("01-0101-roi")), 1)

            reloaded.discard_part_roi("01-0101-roi", "head_roi")

            self.assertEqual(reloaded.list_part_rois("01-0101-roi"), [])
            self.assertEqual(len(reloaded.list_part_rois("01-0101-roi", include_cancelled=True)), 1)

    def test_part_records_round_trip_and_discard_only_removes_part_storage(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "parts_project"
            manager = TifProjectManager()
            project_json = manager.create_project("parts_project", project_root)
            manager.create_specimen_scaffold("01-0101-parts")
            image_rel = "specimens/01-0101-parts/working/image.ome.zarr"
            image_meta = write_volume_sidecar(project_root / image_rel, np.arange(3 * 4 * 5, dtype=np.uint8).reshape((3, 4, 5)), role="working_image")
            manager.register_working_volume("01-0101-parts", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            part_dir = manager.part_dir("01-0101-parts", "Head")
            part_image_rel = f"{part_dir}/image.ome.zarr"
            part_mask_rel = f"{part_dir}/mask.ome.zarr"
            part_image_meta = write_volume_sidecar(project_root / part_image_rel, np.ones((1, 2, 3), dtype=np.uint8), role="part_image")
            part_mask_meta = write_volume_sidecar(project_root / part_mask_rel, np.zeros((1, 2, 3), dtype=np.uint16), role="part_mask")
            part = manager.add_part(
                "01-0101-parts",
                "Head",
                display_name="Head",
                image={"path": part_image_rel, **part_image_meta},
                mask={"path": part_mask_rel, **part_mask_meta},
                parent_bbox_zyx=[[0, 1], [1, 3], [1, 4]],
                contours_path=f"{part_dir}/contours.json",
                extraction_path=f"{part_dir}/extraction.json",
                status="roi_confirmed",
            )
            manager.update_part_view_settings("01-0101-parts", "Head", {"volume_tint": "white", "volume_tint_custom": "#f0f4f2"})

            reloaded = TifProjectManager()
            reloaded.load_project(project_json)
            loaded_part = reloaded.get_part("01-0101-parts", "Head")

            self.assertEqual(part["part_id"], "Head")
            self.assertEqual(loaded_part["display_name"], "Head")
            self.assertEqual(loaded_part["image"]["shape_zyx"], [1, 2, 3])
            self.assertEqual(loaded_part["parent_bbox_zyx"], [[0, 1], [1, 3], [1, 4]])
            self.assertEqual(loaded_part["view_settings"]["volume_tint"], "white")
            self.assertEqual(loaded_part["view_settings"]["volume_tint_custom"], "#f0f4f2")
            self.assertTrue((project_root / image_rel / "array.npy").exists())

            result = reloaded.discard_part("01-0101-parts", "Head")

            self.assertTrue(result["removed_part"])
            self.assertTrue(result["removed_storage"])
            self.assertFalse((project_root / part_dir).exists())
            self.assertTrue((project_root / image_rel / "array.npy").exists())
            self.assertEqual(reloaded.list_parts("01-0101-parts"), [])

    def test_part_ids_reject_duplicates_and_storage_collisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = TifProjectManager()
            manager.create_project("part_collision", Path(tmp) / "part_collision")
            manager.create_specimen_scaffold("01-0101-collision")
            manager.add_part("01-0101-collision", "Head", save=False)

            with self.assertRaisesRegex(ValueError, "duplicate_part_id"):
                manager.add_part("01-0101-collision", "Head", save=False)

            with self.assertRaisesRegex(ValueError, "duplicate_part_id"):
                manager.add_part("01-0101-collision", "Head?", save=False)

    def test_crop_volume_to_part_writes_local_image_mask_and_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "crop_part"
            manager = TifProjectManager()
            manager.create_project("crop_part", project_root)
            manager.create_specimen_scaffold("01-0101-crop")
            image = np.arange(4 * 5 * 6, dtype=np.uint8).reshape((4, 5, 6))
            image_rel = "specimens/01-0101-crop/working/image.ome.zarr"
            image_meta = write_volume_sidecar(project_root / image_rel, image, role="working_image")
            manager.register_working_volume(
                "01-0101-crop",
                image_rel,
                image_meta["shape_zyx"],
                image_meta["dtype"],
                spacing_zyx=[2.0, 1.0, 1.0],
                save=False,
            )
            manager.save_project()

            part = crop_volume_to_part(manager, "01-0101-crop", "head", [[1, 3], [1, 4], [2, 6]], display_name="Head")

            cropped = load_volume_sidecar(project_root / part["image"]["path"])
            mask = load_volume_sidecar(project_root / part["mask"]["path"])
            np.testing.assert_array_equal(cropped, image[1:3, 1:4, 2:6])
            self.assertEqual(mask.shape, cropped.shape)
            self.assertEqual(int(mask.sum()), 0)
            self.assertTrue((project_root / part["contours_path"]).exists())
            self.assertTrue((project_root / part["extraction_path"]).exists())
            self.assertEqual(part["parent_bbox_zyx"], [[1, 3], [1, 4], [2, 6]])

    def test_rectangular_keyframes_generate_preview_mask_between_slices(self):
        contours = {"axis": "z", "keyframes": []}
        contours = add_rectangular_keyframe(contours, 0, [[1, 4], [1, 4]])
        contours = add_rectangular_keyframe(contours, 2, [[2, 5], [2, 5]])

        mask = build_preview_mask_from_contours(contours, (3, 6, 6))

        self.assertEqual(mask.shape, (3, 6, 6))
        self.assertGreater(int(mask[1].sum()), 0)
        self.assertGreater(int(mask.sum()), int(mask[0].sum()))

    def test_freehand_polygon_keyframe_preserves_subpixel_points(self):
        contours = {"axis": "z", "keyframes": []}
        drawn_polygon = [[1.2, 1.6], [2.4, 1.2], [4.7, 1.4], [4.4, 4.8], [2.6, 4.2], [1.3, 4.5]]
        contours = add_polygon_keyframe(contours, 1, drawn_polygon, source="manual_freehand")

        polygon = contours["keyframes"][0]["polygon"]
        self.assertEqual(polygon, drawn_polygon)
        self.assertIsInstance(polygon[0][0], float)

        mask = build_preview_mask_from_contours(contours, (3, 6, 6))
        self.assertGreater(int(mask[1].sum()), 0)

    def test_preview_mask_only_fills_between_first_and_last_keyframes(self):
        contours = {"axis": "z", "keyframes": []}
        contours = add_rectangular_keyframe(contours, 1, [[1, 4], [1, 4]])
        contours = add_rectangular_keyframe(contours, 3, [[2, 5], [2, 5]])

        mask = build_preview_mask_from_contours(contours, (5, 6, 6))

        self.assertEqual(int(mask[0].sum()), 0)
        self.assertGreater(int(mask[1].sum()), 0)
        self.assertGreater(int(mask[2].sum()), 0)
        self.assertGreater(int(mask[3].sum()), 0)
        self.assertEqual(int(mask[4].sum()), 0)

    def test_contours_json_damage_and_invalid_keyframes_do_not_crash_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            contours_path = Path(tmp) / "contours.json"
            contours_path.write_text("{bad json", encoding="utf-8")

            contours = read_contours_json(contours_path)
            report = validate_contours_for_interpolation(
                {"axis": "z", "keyframes": ["bad", {"slice_index": "bad", "polygon": [[1, 1], [2, 1], [2, 2]]}]},
                (3, 4, 4),
            )

            self.assertEqual(contours["keyframes"], [])
            self.assertFalse(report["ok"])
            self.assertIn("invalid_slice_index", {item["code"] for item in report["warnings"]})
            self.assertIn("no_key_slices", {item["code"] for item in report["errors"]})

    def test_single_keyframe_preview_fills_only_the_key_slice(self):
        contours = {"axis": "z", "keyframes": []}
        contours = add_rectangular_keyframe(contours, 2, [[1, 4], [1, 4]])

        report = validate_contours_for_interpolation(contours, (5, 6, 6))
        mask = build_preview_mask_from_contours(contours, (5, 6, 6))

        self.assertTrue(report["ok"])
        self.assertIn("single_key_slice", {item["code"] for item in report["warnings"]})
        self.assertEqual(int(mask[0].sum()), 0)
        self.assertEqual(int(mask[1].sum()), 0)
        self.assertGreater(int(mask[2].sum()), 0)
        self.assertEqual(int(mask[3].sum()), 0)
        self.assertEqual(int(mask[4].sum()), 0)

    def test_crop_volume_to_part_validates_duplicate_before_touching_storage(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "duplicate_part"
            manager = TifProjectManager()
            manager.create_project("duplicate_part", project_root)
            manager.create_specimen_scaffold("01-0101-dup")
            image = np.arange(3 * 4 * 5, dtype=np.uint8).reshape((3, 4, 5))
            image_rel = "specimens/01-0101-dup/working/image.ome.zarr"
            image_meta = write_volume_sidecar(project_root / image_rel, image, role="working_image")
            manager.register_working_volume("01-0101-dup", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            manager.save_project()
            first = crop_volume_to_part(manager, "01-0101-dup", "head", [[0, 1], [0, 2], [0, 2]])
            marker = project_root / manager.part_dir("01-0101-dup", first["part_id"]) / "keep.txt"
            marker.write_text("do-not-touch", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "duplicate_part_id"):
                crop_volume_to_part(manager, "01-0101-dup", "head", [[1, 3], [1, 4], [1, 5]])

            self.assertEqual(marker.read_text(encoding="utf-8"), "do-not-touch")

    def test_crop_volume_to_part_refuses_non_empty_orphan_part_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "orphan_part"
            manager = TifProjectManager()
            manager.create_project("orphan_part", project_root)
            manager.create_specimen_scaffold("01-0101-orphan")
            image = np.arange(2 * 3 * 4, dtype=np.uint8).reshape((2, 3, 4))
            image_rel = "specimens/01-0101-orphan/working/image.ome.zarr"
            image_meta = write_volume_sidecar(project_root / image_rel, image, role="working_image")
            manager.register_working_volume("01-0101-orphan", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            manager.save_project()
            orphan_dir = project_root / manager.part_dir("01-0101-orphan", "head")
            orphan_dir.mkdir(parents=True)
            (orphan_dir / "leftover.txt").write_text("old local data", encoding="utf-8")

            with self.assertRaisesRegex(FileExistsError, "part_storage_dir_not_empty"):
                crop_volume_to_part(manager, "01-0101-orphan", "head", [[0, 1], [0, 2], [0, 2]])

            self.assertEqual(manager.list_parts("01-0101-orphan"), [])

    def test_local_axis_records_round_trip_under_specimen_and_part(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "local_axis_records"
            manager = TifProjectManager()
            project_json = manager.create_project("local_axis_records", project_root)
            manager.create_specimen_scaffold("01-0101-local")
            manager.add_part("01-0101-local", "head", parent_bbox_zyx=[[1, 5], [2, 6], [3, 7]], save=False)

            global_proposal = manager.add_global_axis_proposal(
                "01-0101-local",
                {
                    "global_proposal_id": "roi_001",
                    "template_id": "head",
                    "bbox_zyx": [1, 2, 3, 5, 6, 7],
                    "center_zyx": [3.0, 4.0, 5.0],
                    "confidence": 0.8,
                    "status": "proposed",
                },
                save=False,
            )
            frame_proposal = manager.add_local_frame_proposal(
                "01-0101-local",
                "head",
                {
                    "frame_proposal_id": "frame_001",
                    "template_id": "head",
                    "origin_zyx": [2.0, 2.0, 2.0],
                    "output_axis_start_zyx": [0.0, 2.0, 2.0],
                    "output_axis_end_zyx": [4.0, 2.0, 2.0],
                    "roll_reference": {
                        "point_a": {"role": "left_eye", "zyx": [2.0, 1.0, 1.0]},
                        "point_b": {"role": "right_eye", "zyx": [2.0, 3.0, 1.0]},
                    },
                    "confidence": 0.7,
                },
                save=False,
            )
            reslice = manager.add_part_reslice(
                "01-0101-local",
                "head",
                {
                    "reslice_id": "head_axis_001",
                    "template_id": "head",
                    "image_path": "specimens/01-0101-local/parts/head/reslices/head_axis_001/image.tif",
                    "metadata_path": "specimens/01-0101-local/parts/head/reslices/head_axis_001/metadata.json",
                    "local_frame": {
                        "origin_zyx": [2.0, 2.0, 2.0],
                        "x_axis": [0.0, 1.0, 0.0],
                        "y_axis": [0.0, 0.0, 1.0],
                        "z_axis": [1.0, 0.0, 0.0],
                        "output_axis": "z_axis",
                        "spacing_zyx": [2.0, 1.0, 1.0],
                        "coordinate_space": "part_volume_voxel_zyx",
                        "reference_plane": {
                            "plane_id": "three_point_reference_plane",
                            "normal_axis_zyx": [1.0, 0.0, 0.0],
                            "point_c_zyx": [2.0, 2.0, 3.0],
                        },
                    },
                    "training": {"human_confirmed": True, "usable_for_training": True},
                    "training_sample": {
                        "schema_version": "taxamask_tif_local_axis_training_sample_v1",
                        "sample_id": "01-0101-local:head:head_axis_001",
                        "specimen_id": "01-0101-local",
                        "part_id": "head",
                        "reslice_id": "head_axis_001",
                        "template_id": "head",
                        "source_axis": {"axis_id": "source_z_axis", "locked": True},
                        "initial_editable_axis": {"axis_id": "local_output_z_axis", "start_zyx": [0.0, 2.0, 2.0]},
                        "final_editable_axis": {"axis_id": "local_output_z_axis", "end_zyx": [4.0, 2.0, 2.0]},
                        "origin_zyx": [2.0, 2.0, 2.0],
                        "roll_reference_point_pair": {
                            "point_a": {"role": "left_eye", "zyx": [2.0, 1.0, 1.0]},
                            "point_b": {"role": "right_eye", "zyx": [2.0, 3.0, 1.0]},
                        },
                        "human_confirmed": True,
                        "usable_for_training": True,
                    },
                },
                save=False,
            )
            model = manager.register_local_axis_model(
                {
                    "model_id": "local_axis/head_frame_v1",
                    "template_id": "head",
                    "model_type": "local_frame",
                    "backend_type": "external_local_axis",
                    "model_manifest": "models/head_frame_v1/manifest.json",
                },
                save=False,
            )
            run = manager.add_local_axis_run(
                {
                    "run_id": "predict_001",
                    "action": "predict_local_frame",
                    "model_id": model["model_id"],
                    "specimen_ids": ["01-0101-local"],
                    "part_ids": ["head"],
                    "result_status": "success",
                },
                save=True,
            )

            reloaded = TifProjectManager()
            reloaded.load_project(project_json)

            self.assertEqual(global_proposal["bbox_zyx"], [[1, 5], [2, 6], [3, 7]])
            self.assertEqual(reloaded.list_global_axis_proposals("01-0101-local")[0]["global_proposal_id"], "roi_001")
            self.assertEqual(frame_proposal["status"], "proposed")
            self.assertEqual(reloaded.list_local_frame_proposals("01-0101-local", "head")[0]["frame_proposal_id"], "frame_001")
            self.assertEqual(reslice["training"]["human_confirmed"], True)
            reloaded_reslice = reloaded.list_part_reslices("01-0101-local", "head")[0]
            self.assertEqual(reloaded_reslice["reslice_id"], "head_axis_001")
            self.assertEqual(reloaded_reslice["local_frame"]["spacing_zyx"], [2.0, 1.0, 1.0])
            self.assertEqual(reloaded_reslice["local_frame"]["coordinate_space"], "part_volume_voxel_zyx")
            self.assertEqual(reloaded_reslice["local_frame"]["reference_plane"]["plane_id"], "three_point_reference_plane")
            self.assertEqual(reloaded_reslice["training_sample"]["sample_id"], "01-0101-local:head:head_axis_001")
            self.assertEqual(reloaded_reslice["training_sample"]["final_editable_axis"]["end_zyx"], [4.0, 2.0, 2.0])
            self.assertEqual(run["workflow"], "tif_local_axis")
            self.assertEqual(reloaded.project_data["models"][0]["model_id"], "local_axis/head_frame_v1")
            self.assertEqual(reloaded.project_data["runs"][0]["run_id"], "predict_001")
            self.assertEqual(reloaded.list_local_axis_models()[0]["model_id"], "local_axis/head_frame_v1")
            self.assertEqual(reloaded.get_local_axis_model("local_axis/head_frame_v1")["model_type"], "local_frame")
            self.assertEqual(reloaded.list_local_axis_runs()[0]["run_id"], "predict_001")
            self.assertEqual(reloaded.get_local_axis_run("predict_001")["action"], "predict_local_frame")

    def test_non_local_axis_models_and_runs_survive_project_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "legacy_backend_records"
            manager = TifProjectManager()
            project_json = manager.create_project("legacy_backend_records", project_root)
            manager.project_data["models"].append(
                {
                    "model_manifest": "runs/train/model_manifest.json",
                    "backend_id": "nnunet_backend",
                    "run_id": "train_001",
                    "input_contract": {"image": "volume"},
                    "output_contract": {"prediction": "mask"},
                }
            )
            manager.project_data["runs"].append(
                {
                    "run_id": "train_001",
                    "action": "train",
                    "backend_id": "nnunet_backend",
                    "run_dir": "runs/train/train_001",
                    "result_status": "success",
                }
            )
            manager.save_project()

            reloaded = TifProjectManager()
            reloaded.load_project(project_json)

            self.assertEqual(reloaded.project_data["models"][0].get("profile_scope", ""), "")
            self.assertEqual(reloaded.project_data["models"][0]["backend_id"], "nnunet_backend")
            self.assertEqual(reloaded.project_data["runs"][0].get("workflow", ""), "")
            self.assertEqual(reloaded.project_data["runs"][0]["action"], "train")
            self.assertEqual(reloaded.list_local_axis_models(), [])
            self.assertEqual(reloaded.list_local_axis_runs(), [])

    def test_tif_segmentation_models_round_trip_notes_and_delete_registration(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "tif_segmentation_models"
            manager = TifProjectManager()
            project_json = manager.create_project("tif_segmentation_models", project_root)
            output_dir = project_root / "runs" / "train" / "outputs"
            output_dir.mkdir(parents=True)
            checkpoint = output_dir / "checkpoint_final.pth"
            checkpoint.write_bytes(b"fake weights")
            manifest_path = output_dir / "model_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": "ant3d_tif_model_manifest_v1",
                        "model_id": "taxamask_tif_nnunet_v2_backend/train_001",
                        "backend_id": "taxamask_tif_nnunet_v2_backend",
                        "model_family": "nnunet_v2_tif_region",
                        "created_at": "2026-07-07T12:00:00+08:00",
                        "trained_specimens": ["s1", "s2"],
                        "trained_parts": [
                            {"specimen_id": "s1", "part_id": "head", "reslice_id": "axis_1"},
                            {"specimen_id": "s2", "part_id": "head", "reslice_id": "axis_1"},
                        ],
                        "input_scope": "part_reslice",
                        "label_schema_ids": ["head_regions"],
                        "nnunet": {
                            "model_output_dir": str(output_dir),
                            "checkpoint_path": str(checkpoint),
                        },
                        "usable_for_research_prediction": True,
                    }
                ),
                encoding="utf-8",
            )

            model = manager.register_tif_segmentation_model_from_manifest(
                manifest_path,
                {"run_id": "train_001", "training_samples": 2, "notes": "first accepted model"},
                save=True,
            )
            manager.register_tif_segmentation_model_from_manifest(
                manager.to_relative(manifest_path),
                {"run_id": "train_001", "training_samples": 2},
                save=True,
            )

            reloaded = TifProjectManager()
            reloaded.load_project(project_json)
            records = reloaded.list_tif_segmentation_models()
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["model_id"], model["model_id"])
            self.assertEqual(records[0]["training_samples"], 2)
            self.assertEqual(records[0]["notes"], "first accepted model")
            self.assertEqual(reloaded.to_absolute(records[0]["model_manifest"]), str(manifest_path))
            self.assertEqual(reloaded.list_local_axis_models(), [])

            reloaded.update_tif_segmentation_model_notes(model["model_id"], "use for July batch", save=True)
            reloaded_again = TifProjectManager()
            reloaded_again.load_project(project_json)
            self.assertEqual(reloaded_again.get_tif_segmentation_model(model["model_id"])["notes"], "use for July batch")

            removed = reloaded_again.delete_tif_segmentation_model(model["model_id"], save=True)
            self.assertIsNotNone(removed)
            self.assertTrue(manifest_path.exists())
            final = TifProjectManager()
            final.load_project(project_json)
            self.assertEqual(final.list_tif_segmentation_models(), [])

    def test_part_training_labels_schema_and_user_tags_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "part_training_roundtrip"
            manager = TifProjectManager()
            project_json = manager.create_project("part_training_roundtrip", project_root)
            manager.create_specimen_scaffold("01-0101-brain")
            part_image_rel = "specimens/01-0101-brain/parts/brain/image.ome.zarr"
            part_mask_rel = "specimens/01-0101-brain/parts/brain/mask.ome.zarr"
            part_manual_rel = "specimens/01-0101-brain/parts/brain/labels/manual_truth.ome.zarr"
            image_meta = write_volume_sidecar(project_root / part_image_rel, np.zeros((2, 3, 4), dtype=np.uint8), role="part_image")
            mask_meta = write_volume_sidecar(project_root / part_mask_rel, np.zeros((2, 3, 4), dtype=np.uint16), role="part_mask")
            manual_meta = write_volume_sidecar(project_root / part_manual_rel, np.ones((2, 3, 4), dtype=np.uint16), role="manual_truth")
            manager.add_part(
                "01-0101-brain",
                "brain",
                image={"path": part_image_rel, **image_meta},
                mask={"path": part_mask_rel, **mask_meta},
                save=False,
            )
            manager.add_or_update_label_schema(
                "brain_regions",
                labels=[
                    {"id": 1, "name": "mushroom_body", "color": "#ff0000"},
                    {"id": 2, "name": "antennal_lobe", "color": "#00ff00"},
                ],
                user_defined_part_name="brain",
                save=False,
            )
            manager.upsert_part_user_tag("round_1", "Round 1", order_index=0, save=False)
            manager.set_part_user_tags("01-0101-brain", "brain", ["round_1"], save=False)
            manager.register_part_label_volume(
                "01-0101-brain",
                "brain",
                "manual_truth",
                part_manual_rel,
                manual_meta["shape_zyx"],
                manual_meta["dtype"],
                status="reviewed",
                save=False,
            )
            manager.set_part_training_metadata(
                "01-0101-brain",
                "brain",
                user_defined_part_name="brain",
                label_schema_id="brain_regions",
                system_status="verified_train_ready",
                save=True,
            )

            reloaded = TifProjectManager()
            reloaded.load_project(project_json)
            part = reloaded.get_part("01-0101-brain", "brain")

            self.assertEqual(reloaded.get_label_schema("brain_regions")["labels"][0]["name"], "mushroom_body")
            self.assertEqual(reloaded.project_data["part_user_tags"][0]["tag_id"], "round_1")
            self.assertEqual(part["user_tags"], ["round_1"])
            self.assertEqual(part["training"]["label_schema_id"], "brain_regions")
            self.assertEqual(part["labels"]["manual_truth"]["path"], part_manual_rel)
            self.assertTrue(reloaded.validate_part_label_ids("01-0101-brain", "brain")["ok"])

    def test_label_schema_export_import_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = TifProjectManager()
            source.create_project("schema_source", root / "source")
            source.add_or_update_label_schema(
                "brain_regions",
                labels=[
                    {"id": 1, "name": "mushroom_body", "display_name": "Mushroom body", "color": "#ff0000"},
                    {"id": 2, "name": "antennal_lobe", "display_name": "Antennal lobe", "color": "#00ff00"},
                    {"id": 2, "name": "duplicate_should_drop", "color": "#0000ff"},
                ],
                user_defined_part_name="brain",
                save=True,
            )
            export_path = root / "brain_regions.schema.json"

            payload = source.export_label_schema("brain_regions", export_path)

            self.assertTrue(export_path.exists())
            self.assertEqual(payload["schema_version"], "taxamask_tif_label_schema_v1")
            self.assertEqual(payload["label_schema"]["schema_id"], "brain_regions")
            self.assertEqual([item["id"] for item in payload["label_schema"]["labels"]], [1, 2])

            target = TifProjectManager()
            target.create_project("schema_target", root / "target")
            imported = target.import_label_schema(export_path)

            self.assertEqual(imported["schema_id"], "brain_regions")
            self.assertEqual(imported["user_defined_part_name"], "brain")
            self.assertEqual(target.get_label_schema("brain_regions")["labels"][1]["name"], "antennal_lobe")

            raw_export = root / "raw_schema.json"
            raw_export.write_text(
                json.dumps(
                    {
                        "schema_id": "brain_regions",
                        "labels": [{"id": 3, "name": "central_complex", "color": "#123456"}],
                        "user_defined_part_name": "brain",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with self.assertRaises(FileExistsError):
                target.import_label_schema(raw_export, replace=False)
            replaced = target.import_label_schema(raw_export, replace=True)
            self.assertEqual([item["id"] for item in replaced["labels"]], [3])

            empty_export = root / "empty_schema.json"
            empty_export.write_text(json.dumps({"schema_id": "empty", "labels": []}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "label_schema_empty"):
                target.import_label_schema(empty_export)

    def test_part_user_tags_reorder_and_delete_do_not_override_system_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "part_tags"
            manager = TifProjectManager()
            manager.create_project("part_tags", project_root)
            manager.create_specimen_scaffold("01-0101-tags")
            manager.add_part("01-0101-tags", "brain", save=False)
            manager.set_part_training_metadata(
                "01-0101-tags",
                "brain",
                system_status="predicted_pending_review",
                save=False,
            )
            manager.upsert_part_user_tag("candidate", "Candidate", order_index=0, save=False)
            manager.upsert_part_user_tag("paper_fig", "Paper figure", order_index=1, save=False)
            manager.set_part_user_tags("01-0101-tags", "brain", ["candidate", "paper_fig"], save=False)
            manager.set_part_user_tag_order(["paper_fig", "candidate"], save=False)
            manager.delete_part_user_tag("candidate", save=True)

            part = manager.get_part("01-0101-tags", "brain")
            tags = manager.project_data["part_user_tags"]
            self.assertEqual([tag["tag_id"] for tag in tags], ["paper_fig"])
            self.assertEqual(tags[0]["order_index"], 0)
            self.assertEqual(part["user_tags"], ["paper_fig"])
            self.assertEqual(part["training"]["system_status"], "predicted_pending_review")

    def test_reviewed_part_editable_result_batch_promotes_to_manual_truth(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "part_review_batch"
            manager = TifProjectManager()
            manager.create_project("part_review_batch", project_root)
            manager.create_specimen_scaffold("01-0101-review")
            part_image_rel = "specimens/01-0101-review/parts/brain/image.ome.zarr"
            reslice_rel = "specimens/01-0101-review/parts/brain/reslices/brain_axis_001/image.tif"
            edit_rel = "specimens/01-0101-review/parts/brain/reslices/brain_axis_001/labels/editable_ai_result.ome.zarr"
            image_meta = write_volume_sidecar(project_root / part_image_rel, np.zeros((2, 3, 4), dtype=np.uint8), role="part_image")
            (project_root / reslice_rel).parent.mkdir(parents=True, exist_ok=True)
            tifffile.imwrite(project_root / reslice_rel, np.zeros((2, 3, 4), dtype=np.uint8))
            edit_array = np.ones((2, 3, 4), dtype=np.uint16)
            edit_array[0, 0, 0] = 2
            edit_meta = write_volume_sidecar(project_root / edit_rel, edit_array, role="editable_ai_result")
            manager.add_part(
                "01-0101-review",
                "brain",
                image={"path": part_image_rel, **image_meta},
                save=False,
            )
            manager.add_or_update_label_schema(
                "brain_regions",
                labels=[
                    {"id": 1, "name": "mushroom_body", "color": "#ff0000"},
                    {"id": 2, "name": "antennal_lobe", "color": "#00ff00"},
                ],
                user_defined_part_name="brain",
                save=False,
            )
            manager.add_part_reslice(
                "01-0101-review",
                "brain",
                {"reslice_id": "brain_axis_001", "image_path": reslice_rel, "status": "exported"},
                save=False,
            )
            manager.register_part_reslice_label_volume(
                "01-0101-review",
                "brain",
                "brain_axis_001",
                "editable_ai_result",
                edit_rel,
                edit_meta["shape_zyx"],
                edit_meta["dtype"],
                status="pending_review",
                save=False,
            )
            manager.set_part_training_metadata(
                "01-0101-review",
                "brain",
                label_schema_id="brain_regions",
                active_reslice_id="brain_axis_001",
                opened_for_review=False,
                save=True,
            )

            report = manager.evaluate_part_editable_result_review_ready("01-0101-review", "brain", "brain_axis_001")
            self.assertTrue(report["review_ready"])
            self.assertEqual(report["reslice_id"], "brain_axis_001")
            self.assertFalse(report["opened_for_review"])
            self.assertIn("editable_ai_result_not_opened_for_review", report["reasons"])
            self.assertEqual(report["label_schema_id"], "brain_regions")
            self.assertEqual(report["label_ids"], [1, 2])
            with patch.object(manager, "validate_part_label_ids", side_effect=AssertionError("label scan should be deferred")):
                deferred_report = manager.evaluate_part_editable_result_review_ready(
                    "01-0101-review",
                    "brain",
                    "brain_axis_001",
                    validate_label_ids=False,
                )
            self.assertTrue(deferred_report["review_ready"])
            self.assertFalse(deferred_report["label_ids_checked"])
            self.assertEqual(deferred_report["label_report"]["skipped"], "label_id_scan_deferred")
            acceptance = manager.build_part_review_acceptance_report(
                [{"specimen_id": "01-0101-review", "part_id": "brain", "reslice_id": "brain_axis_001"}],
                require_opened_for_review=False,
            )
            self.assertEqual(acceptance["ready_count"], 1)
            self.assertEqual(acceptance["not_opened_count"], 1)
            self.assertEqual(acceptance["blocked_count"], 0)
            blocked_acceptance = manager.build_part_review_acceptance_report(
                [{"specimen_id": "01-0101-review", "part_id": "brain", "reslice_id": "brain_axis_001"}],
                require_opened_for_review=True,
            )
            self.assertEqual(blocked_acceptance["ready_count"], 0)
            self.assertEqual(blocked_acceptance["blocked_count"], 1)
            with self.assertRaisesRegex(ValueError, "part_review_not_ready"):
                manager.promote_reviewed_part_results_to_manual_truth(
                    [{"specimen_id": "01-0101-review", "part_id": "brain", "reslice_id": "brain_axis_001"}],
                    require_opened_for_review=True,
                )

            result = manager.promote_reviewed_part_results_to_manual_truth(
                [{"specimen_id": "01-0101-review", "part_id": "brain", "reslice_id": "brain_axis_001"}],
                require_opened_for_review=False,
            )
            part = manager.get_part("01-0101-review", "brain")
            reslice = manager.get_part_reslice("01-0101-review", "brain", "brain_axis_001")
            self.assertEqual(result["count"], 1)
            self.assertFalse((part["labels"]["manual_truth"] or {}).get("path"))
            self.assertEqual(reslice["labels"]["manual_truth"]["status"], "reviewed")
            self.assertEqual(part["training"]["system_status"], "verified_train_ready")
            self.assertTrue(manager.evaluate_part_train_ready("01-0101-review", "brain")["train_ready"])
            np.testing.assert_array_equal(load_volume_sidecar(project_root / reslice["labels"]["manual_truth"]["path"]), edit_array)

    def test_reslice_shape_check_uses_tif_metadata_without_full_read_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "reslice_shape_metadata"
            manager = TifProjectManager()
            manager.create_project("reslice_shape_metadata", project_root)
            manager.create_specimen_scaffold("01-0101-shape")
            part_image_rel = "specimens/01-0101-shape/parts/head/image.ome.zarr"
            part_meta = write_volume_sidecar(project_root / part_image_rel, np.zeros((2, 3, 4), dtype=np.uint8), role="part_image")
            manager.add_part("01-0101-shape", "head", image={"path": part_image_rel, **part_meta}, save=False)
            manager.add_or_update_label_schema("head_regions", labels=[{"id": 1, "name": "label_1"}], save=False)
            reslice_rel = "specimens/01-0101-shape/parts/head/reslices/compressed_axis/image.tif"
            reslice_abs = project_root / reslice_rel
            reslice_abs.parent.mkdir(parents=True, exist_ok=True)
            tifffile.imwrite(reslice_abs, np.zeros((2, 4, 5), dtype=np.uint8), compression="deflate")
            manager.add_part_reslice(
                "01-0101-shape",
                "head",
                {"reslice_id": "compressed_axis", "image_path": reslice_rel, "status": "exported"},
                save=False,
            )
            manager.set_part_training_metadata(
                "01-0101-shape",
                "head",
                label_schema_id="head_regions",
                active_reslice_id="compressed_axis",
                save=True,
            )

            with patch("tifffile.imread", side_effect=AssertionError("full TIF read should be avoided")):
                report = manager.evaluate_part_predict_ready("01-0101-shape", "head", "compressed_axis")

            self.assertTrue(report["predict_ready"])
            self.assertEqual(report["input_shape_zyx"], [2, 4, 5])

    def test_reviewed_part_editable_result_rejects_unknown_label_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "part_review_unknown_label"
            manager = TifProjectManager()
            manager.create_project("part_review_unknown_label", project_root)
            manager.create_specimen_scaffold("01-0101-review")
            part_image_rel = "specimens/01-0101-review/parts/brain/image.ome.zarr"
            edit_rel = "specimens/01-0101-review/parts/brain/labels/editable_ai_result.ome.zarr"
            image_meta = write_volume_sidecar(project_root / part_image_rel, np.zeros((2, 3, 4), dtype=np.uint8), role="part_image")
            edit_meta = write_volume_sidecar(project_root / edit_rel, np.full((2, 3, 4), 9, dtype=np.uint16), role="editable_ai_result")
            manager.add_part("01-0101-review", "brain", image={"path": part_image_rel, **image_meta}, save=False)
            manager.add_or_update_label_schema(
                "brain_regions",
                labels=[{"id": 1, "name": "mushroom_body", "color": "#ff0000"}],
                save=False,
            )
            manager.register_part_label_volume(
                "01-0101-review",
                "brain",
                "editable_ai_result",
                edit_rel,
                edit_meta["shape_zyx"],
                edit_meta["dtype"],
                save=False,
            )
            manager.set_part_training_metadata(
                "01-0101-review",
                "brain",
                label_schema_id="brain_regions",
                opened_for_review=True,
                save=True,
            )

            report = manager.evaluate_part_editable_result_review_ready("01-0101-review", "brain")
            self.assertFalse(report["review_ready"])
            self.assertIn("unknown_label_ids", report["reasons"])
            self.assertEqual(report["label_report"]["unknown_label_ids"], [9])
            self.assertEqual(report["unknown_label_ids"], [9])
            acceptance = manager.build_part_review_acceptance_report(
                [{"specimen_id": "01-0101-review", "part_id": "brain"}],
                require_opened_for_review=False,
            )
            self.assertEqual(acceptance["ready_count"], 0)
            self.assertEqual(acceptance["blocked_count"], 1)
            self.assertEqual(acceptance["blocked"][0]["report"]["unknown_label_ids"], [9])
            with self.assertRaisesRegex(ValueError, "part_review_not_ready"):
                manager.promote_reviewed_part_results_to_manual_truth(
                    [{"specimen_id": "01-0101-review", "part_id": "brain"}],
                    require_opened_for_review=False,
                )


if __name__ == "__main__":
    unittest.main()
