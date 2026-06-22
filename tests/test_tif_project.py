import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from AntSleap.core.tif_materials import read_material_map
from AntSleap.core.tif_part_extraction import (
    add_rectangular_keyframe,
    build_preview_mask_from_contours,
    crop_volume_to_part,
    read_contours_json,
    validate_contours_for_interpolation,
)
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

            self.assertNotIn("profile_scope", reloaded.project_data["models"][0])
            self.assertEqual(reloaded.project_data["models"][0]["backend_id"], "nnunet_backend")
            self.assertNotIn("workflow", reloaded.project_data["runs"][0])
            self.assertEqual(reloaded.project_data["runs"][0]["action"], "train")
            self.assertEqual(reloaded.list_local_axis_models(), [])
            self.assertEqual(reloaded.list_local_axis_runs(), [])


if __name__ == "__main__":
    unittest.main()
