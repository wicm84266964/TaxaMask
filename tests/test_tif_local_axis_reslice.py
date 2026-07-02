import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import tifffile

from AntSleap.core.tif_local_axis_reslice import (
    align_editable_axis_to_reference_plane,
    compute_local_frame,
    create_editable_axis_from_source,
    export_part_reslice,
    local_axis_output_shape_for_source_bbox,
    reslice_volume,
    source_point_to_reslice_point,
    source_z_axis_for_part,
)
from AntSleap.core.tif_local_axis_signal import analyze_source_z_signal, compute_source_z_signal
from AntSleap.core.tif_part_extraction import crop_volume_to_part
from AntSleap.core.tif_project import TifProjectManager
from AntSleap.core.tif_volume_io import load_volume_sidecar, write_volume_sidecar


class TifLocalAxisResliceTests(unittest.TestCase):
    def test_source_z_axis_can_seed_editable_axis(self):
        source = source_z_axis_for_part((5, 7, 9))
        editable = create_editable_axis_from_source(source, "head_output_axis")

        self.assertTrue(source["locked"])
        self.assertFalse(editable["locked"])
        self.assertEqual(source["start_zyx"], [0.0, 3.0, 4.0])
        self.assertEqual(editable["end_zyx"], [4.0, 3.0, 4.0])
        self.assertEqual(editable["source_axis_id"], "source_z_axis")

    def test_compute_local_frame_uses_roll_reference_for_orientation(self):
        frame = compute_local_frame(
            [2.0, 2.0, 2.0],
            [0.0, 2.0, 2.0],
            [4.0, 2.0, 2.0],
            roll_reference={
                "pair_id": "left_eye_right_eye",
                "point_a": {"role": "left_eye", "zyx": [2.0, 1.0, 1.0]},
                "point_b": {"role": "right_eye", "zyx": [2.0, 3.0, 1.0]},
            },
            spacing_zyx=[1.0, 1.0, 1.0],
        )

        np.testing.assert_allclose(frame["z_axis"], [1.0, 0.0, 0.0])
        self.assertGreater(float(np.dot(frame["x_axis"], [0.0, 1.0, 0.0])), 0.9)
        self.assertEqual(frame["output_axis"], "z_axis")

    def test_compute_local_frame_preserves_world_axes_with_anisotropic_spacing(self):
        frame = compute_local_frame(
            [2.0, 2.0, 2.0],
            [0.0, 2.0, 2.0],
            [4.0, 4.0, 2.0],
            roll_reference={
                "point_a": {"role": "roll_point_a", "zyx": [2.0, 2.0, 1.0]},
                "point_b": {"role": "roll_point_b", "zyx": [2.0, 2.0, 3.0]},
            },
            spacing_zyx=[2.0, 1.0, 1.0],
        )

        spacing = np.array(frame["spacing_zyx"], dtype=np.float64)
        x_world = np.array(frame["x_axis"]) * spacing
        y_world = np.array(frame["y_axis"]) * spacing
        z_world = np.array(frame["z_axis"]) * spacing
        x_world = x_world / np.linalg.norm(x_world)
        y_world = y_world / np.linalg.norm(y_world)
        z_world = z_world / np.linalg.norm(z_world)
        np.testing.assert_allclose(np.dot(x_world, z_world), 0.0, atol=1e-7)
        np.testing.assert_allclose(np.dot(y_world, z_world), 0.0, atol=1e-7)
        np.testing.assert_allclose(np.dot(x_world, y_world), 0.0, atol=1e-7)
        expected_z_world = np.array([8.0, 2.0, 0.0], dtype=np.float64)
        expected_z_world = expected_z_world / np.linalg.norm(expected_z_world)
        np.testing.assert_allclose(z_world, expected_z_world, atol=1e-7)

    def test_reslice_volume_identity_frame_preserves_volume(self):
        volume = np.arange(3 * 4 * 5, dtype=np.uint16).reshape((3, 4, 5))
        frame = {
            "origin_zyx": [1.0, 1.5, 2.0],
            "x_axis": [0.0, 0.0, 1.0],
            "y_axis": [0.0, 1.0, 0.0],
            "z_axis": [1.0, 0.0, 0.0],
            "output_axis": "z_axis",
            "spacing_zyx": [1.0, 1.0, 1.0],
        }

        resliced = reslice_volume(volume, frame, {"output_shape_zyx": list(volume.shape)}, interpolation="nearest")

        np.testing.assert_array_equal(resliced, volume)

    def test_three_point_alignment_preserves_axis_length_near_volume_edge(self):
        editable = {
            "start_zyx": [0.0, 1.5, 1.5],
            "end_zyx": [3.0, 1.5, 1.5],
        }
        roll = {
            "point_a": {"role": "roll_reference_a", "zyx": [1.5, 0.0, 0.0]},
            "point_b": {"role": "roll_reference_b", "zyx": [1.5, 3.0, 0.0]},
            "point_c": {"role": "reference_plane_c", "zyx": [3.0, 0.0, 3.0]},
        }

        aligned, _plane = align_editable_axis_to_reference_plane(
            editable,
            roll,
            spacing_zyx=[1.0, 1.0, 1.0],
            shape_zyx=[4, 4, 4],
        )

        original_length = np.linalg.norm(np.array(editable["end_zyx"]) - np.array(editable["start_zyx"]))
        aligned_length = np.linalg.norm(np.array(aligned["end_zyx"]) - np.array(aligned["start_zyx"]))
        self.assertAlmostEqual(aligned_length, original_length, places=2)

    def test_output_shape_for_source_bbox_covers_rotated_part_extent(self):
        frame = compute_local_frame(
            [2.0, 2.0, 2.0],
            [0.0, 2.0, 2.0],
            [4.0, 4.0, 2.0],
            roll_reference={
                "point_a": {"role": "roll_point_a", "zyx": [2.0, 2.0, 0.0]},
                "point_b": {"role": "roll_point_b", "zyx": [2.0, 2.0, 4.0]},
            },
            spacing_zyx=[1.0, 1.0, 1.0],
        )

        shape = local_axis_output_shape_for_source_bbox((5, 5, 5), frame, output_spacing_zyx=[1.0, 1.0, 1.0])

        self.assertGreater(shape[0], 5)
        self.assertGreaterEqual(shape[1], 5)
        self.assertGreaterEqual(shape[2], 5)

    def test_source_point_to_reslice_point_maps_origin_to_output_center(self):
        frame = compute_local_frame(
            [2.0, 2.0, 2.0],
            [0.0, 2.0, 2.0],
            [4.0, 4.0, 2.0],
            roll_reference={
                "point_a": {"role": "roll_point_a", "zyx": [2.0, 2.0, 0.0]},
                "point_b": {"role": "roll_point_b", "zyx": [2.0, 2.0, 4.0]},
            },
            spacing_zyx=[1.0, 1.0, 1.0],
        )
        params = {"output_shape_zyx": [7, 9, 11], "output_spacing_zyx": [1.0, 1.0, 1.0]}

        mapped = source_point_to_reslice_point(frame["origin_zyx"], frame, params)

        np.testing.assert_allclose(mapped, [3.0, 4.0, 5.0], atol=1e-7)

    def test_export_part_reslice_writes_image_mask_metadata_and_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "local_axis_export"
            manager = TifProjectManager()
            project_json = manager.create_project("local_axis_export", project_root)
            manager.create_specimen_scaffold("01-0101-export")
            image = np.arange(5 * 6 * 7, dtype=np.uint16).reshape((5, 6, 7))
            image_rel = "specimens/01-0101-export/working/image.ome.zarr"
            image_meta = write_volume_sidecar(project_root / image_rel, image, role="working_image")
            manager.register_working_volume("01-0101-export", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            manager.save_project()
            part = crop_volume_to_part(manager, "01-0101-export", "head", [[1, 5], [1, 5], [1, 6]], display_name="Head")
            mask = load_volume_sidecar(project_root / part["mask"]["path"])
            mask[1:3, 1:3, 1:3] = 1
            write_volume_sidecar(project_root / part["mask"]["path"], mask, role="part_mask")
            frame = compute_local_frame(
                [1.5, 1.5, 2.0],
                [0.0, 1.5, 2.0],
                [3.0, 1.5, 2.0],
                roll_reference={
                    "point_a": {"role": "left_eye", "zyx": [1.5, 1.0, 1.0]},
                    "point_b": {"role": "right_eye", "zyx": [1.5, 3.0, 1.0]},
                },
                spacing_zyx=[1.0, 1.0, 1.0],
            )
            source_axis = source_z_axis_for_part((4, 4, 5))
            initial_axis = create_editable_axis_from_source(source_axis)
            final_axis = dict(initial_axis)
            final_axis["start_zyx"] = [0.0, 1.5, 2.0]
            final_axis["end_zyx"] = [3.0, 1.5, 2.0]

            result = export_part_reslice(
                manager,
                "01-0101-export",
                "head",
                {
                    "reslice_id": "head_axis_001",
                    "template_id": "head",
                    "source_axis": source_axis,
                    "initial_editable_axis": initial_axis,
                    "editable_axis": final_axis,
                    "final_editable_axis": final_axis,
                    "local_frame": frame,
                    "reslice_params": {"output_shape_zyx": [4, 4, 5]},
                    "training": {
                        "human_confirmed": True,
                        "usable_for_training": True,
                        "source": "human_manual_local_axis",
                        "reviewer_notes": "clear left/right eye roll points",
                    },
                },
            )

            self.assertTrue(Path(result["image_path"]).exists())
            self.assertTrue(Path(result["mask_path"]).exists())
            self.assertTrue(Path(result["metadata_path"]).exists())
            exported_image = tifffile.imread(result["image_path"])
            exported_mask = tifffile.imread(result["mask_path"])
            self.assertEqual(exported_image.shape, (4, 4, 5))
            self.assertEqual(exported_mask.shape, (4, 4, 5))
            self.assertTrue(np.issubdtype(exported_mask.dtype, np.integer))
            metadata = json.loads(Path(result["metadata_path"]).read_text(encoding="utf-8"))
            self.assertEqual(metadata["source"]["part_image_shape_zyx"], [4, 4, 5])
            self.assertEqual(metadata["source"]["part_image_dtype"], "uint16")
            self.assertEqual(metadata["source"]["part_spacing_zyx"], [1.0, 1.0, 1.0])
            self.assertTrue(metadata["source"]["part_mask_available"])
            self.assertEqual(metadata["source"]["source_axis"]["role"], "source_direction_reference")
            self.assertEqual(metadata["source"]["initial_editable_axis"]["start_zyx"], [0.0, 1.5, 2.0])
            self.assertEqual(metadata["source"]["final_editable_axis"]["end_zyx"], [3.0, 1.5, 2.0])
            self.assertEqual(metadata["outputs"]["image_interpolation"], "linear")
            self.assertEqual(metadata["outputs"]["mask_interpolation"], "nearest")
            self.assertEqual(metadata["training"]["human_confirmed"], True)
            self.assertEqual(metadata["training_sample"]["schema_version"], "taxamask_tif_local_axis_training_sample_v1")
            self.assertEqual(metadata["training_sample"]["specimen_id"], "01-0101-export")
            self.assertEqual(metadata["training_sample"]["part_id"], "head")
            self.assertEqual(metadata["training_sample"]["template_id"], "head")
            self.assertEqual(metadata["training_sample"]["part_image"]["shape_zyx"], [4, 4, 5])
            self.assertTrue(metadata["training_sample"]["part_mask"]["available"])
            self.assertEqual(metadata["training_sample"]["source_axis"]["axis_id"], "source_z_axis")
            self.assertEqual(metadata["training_sample"]["initial_editable_axis"]["axis_id"], "local_output_z_axis")
            self.assertEqual(metadata["training_sample"]["final_editable_axis"]["end_zyx"], [3.0, 1.5, 2.0])
            self.assertEqual(metadata["training_sample"]["origin_zyx"], frame["origin_zyx"])
            self.assertEqual(metadata["training_sample"]["roll_reference_point_pair"]["point_a"]["role"], "left_eye")
            self.assertEqual(metadata["training_sample"]["local_frame"]["output_axis"], "z_axis")
            self.assertEqual(metadata["training_sample"]["reslice_params"]["output_shape_zyx"], [4, 4, 5])
            self.assertEqual(metadata["training_sample"]["outputs"]["image_path"], metadata["outputs"]["image_path"])
            self.assertTrue(metadata["training_sample"]["human_confirmed"])
            self.assertTrue(metadata["training_sample"]["usable_for_training"])
            self.assertEqual(metadata["training_sample"]["operator_notes"], "clear left/right eye roll points")
            self.assertTrue(metadata["training_sample"]["created_at"])
            self.assertTrue(metadata["training_sample"]["updated_at"])
            self.assertTrue(metadata["training_sample"]["software_version"])
            record = manager.list_part_reslices("01-0101-export", "head")[0]
            self.assertEqual(record["reslice_id"], "head_axis_001")
            self.assertEqual(record["training_sample"]["sample_id"], "01-0101-export:head:head_axis_001")

            reloaded = TifProjectManager()
            reloaded.load_project(project_json)
            reloaded_record = reloaded.list_part_reslices("01-0101-export", "head")[0]
            self.assertEqual(reloaded_record["metadata_path"], result["record"]["metadata_path"])
            self.assertEqual(reloaded_record["training_sample"]["final_editable_axis"]["end_zyx"], [3.0, 1.5, 2.0])

    def test_duplicate_reslice_id_is_rejected_before_overwriting_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "duplicate_reslice"
            manager = TifProjectManager()
            manager.create_project("duplicate_reslice", project_root)
            manager.create_specimen_scaffold("01-0101-duplicate")
            image = np.arange(4 * 5 * 6, dtype=np.uint16).reshape((4, 5, 6))
            image_rel = "specimens/01-0101-duplicate/working/image.ome.zarr"
            image_meta = write_volume_sidecar(project_root / image_rel, image, role="working_image")
            manager.register_working_volume("01-0101-duplicate", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            manager.save_project()
            crop_volume_to_part(manager, "01-0101-duplicate", "head", [[0, 4], [0, 5], [0, 6]], display_name="Head")
            frame = compute_local_frame(
                [1.5, 2.0, 2.5],
                [0.0, 2.0, 2.5],
                [3.0, 2.0, 2.5],
                roll_reference={
                    "point_a": {"role": "roll_point_a", "zyx": [1.5, 1.0, 2.5]},
                    "point_b": {"role": "roll_point_b", "zyx": [1.5, 3.0, 2.5]},
                },
                spacing_zyx=[1.0, 1.0, 1.0],
            )
            first = export_part_reslice(
                manager,
                "01-0101-duplicate",
                "head",
                {"reslice_id": "axis_001", "template_id": "head", "local_frame": frame, "reslice_params": {"output_shape_zyx": [4, 5, 6]}},
            )
            first_image = Path(first["image_path"])
            first_metadata = Path(first["metadata_path"])
            image_bytes = first_image.read_bytes()
            metadata_bytes = first_metadata.read_bytes()

            with self.assertRaisesRegex(FileExistsError, "part_reslice_id_exists"):
                export_part_reslice(
                    manager,
                    "01-0101-duplicate",
                    "head",
                    {"reslice_id": "axis_001", "template_id": "head", "local_frame": frame, "reslice_params": {"output_shape_zyx": [2, 2, 2]}},
                )

            self.assertEqual(first_image.read_bytes(), image_bytes)
            self.assertEqual(first_metadata.read_bytes(), metadata_bytes)
            self.assertEqual(len(manager.list_part_reslices("01-0101-duplicate", "head")), 1)

    def test_allow_overwrite_updates_existing_reslice_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "overwrite_reslice"
            manager = TifProjectManager()
            manager.create_project("overwrite_reslice", project_root)
            manager.create_specimen_scaffold("01-0101-overwrite")
            image = np.arange(4 * 5 * 6, dtype=np.uint16).reshape((4, 5, 6))
            image_rel = "specimens/01-0101-overwrite/working/image.ome.zarr"
            image_meta = write_volume_sidecar(project_root / image_rel, image, role="working_image")
            manager.register_working_volume("01-0101-overwrite", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            manager.save_project()
            crop_volume_to_part(manager, "01-0101-overwrite", "head", [[0, 4], [0, 5], [0, 6]], display_name="Head")
            frame = compute_local_frame(
                [1.5, 2.0, 2.5],
                [0.0, 2.0, 2.5],
                [3.0, 2.0, 2.5],
                roll_reference={
                    "point_a": {"role": "roll_point_a", "zyx": [1.5, 1.0, 2.5]},
                    "point_b": {"role": "roll_point_b", "zyx": [1.5, 3.0, 2.5]},
                },
                spacing_zyx=[1.0, 1.0, 1.0],
            )
            export_part_reslice(
                manager,
                "01-0101-overwrite",
                "head",
                {"reslice_id": "axis_001", "template_id": "head", "local_frame": frame, "display_name": "First"},
            )
            second = export_part_reslice(
                manager,
                "01-0101-overwrite",
                "head",
                {
                    "reslice_id": "axis_001",
                    "template_id": "head",
                    "local_frame": frame,
                    "display_name": "Second",
                    "allow_overwrite": True,
                    "reslice_params": {"output_shape_zyx": [2, 2, 2]},
                },
            )

            self.assertEqual(len(manager.list_part_reslices("01-0101-overwrite", "head")), 1)
            self.assertEqual(second["record"]["display_name"], "Second")
            self.assertEqual(tifffile.imread(second["image_path"]).shape, (2, 2, 2))

    def test_export_fills_missing_frame_spacing_from_part_image_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "frame_spacing"
            manager = TifProjectManager()
            manager.create_project("frame_spacing", project_root)
            manager.create_specimen_scaffold("01-0101-spacing")
            image = np.arange(4 * 5 * 6, dtype=np.uint16).reshape((4, 5, 6))
            image_rel = "specimens/01-0101-spacing/working/image.ome.zarr"
            image_meta = write_volume_sidecar(project_root / image_rel, image, role="working_image", spacing_zyx=[2.0, 1.0, 1.0])
            manager.register_working_volume(
                "01-0101-spacing",
                image_rel,
                image_meta["shape_zyx"],
                image_meta["dtype"],
                spacing_zyx=image_meta["spacing_zyx"],
                save=False,
            )
            manager.save_project()
            crop_volume_to_part(manager, "01-0101-spacing", "head", [[0, 4], [0, 5], [0, 6]], display_name="Head")
            frame = {
                "origin_zyx": [1.5, 2.0, 2.5],
                "x_axis": [0.0, 0.0, 1.0],
                "y_axis": [0.0, 1.0, 0.0],
                "z_axis": [1.0, 0.0, 0.0],
                "output_axis": "z_axis",
                "coordinate_space": "part_volume_voxel_zyx",
                "roll_reference": {
                    "point_a": {"role": "roll_point_a", "zyx": [1.5, 1.0, 2.5]},
                    "point_b": {"role": "roll_point_b", "zyx": [1.5, 3.0, 2.5]},
                },
            }

            result = export_part_reslice(
                manager,
                "01-0101-spacing",
                "head",
                {"reslice_id": "axis_001", "template_id": "head", "local_frame": frame},
            )

            self.assertEqual(result["record"]["local_frame"]["spacing_zyx"], [2.0, 1.0, 1.0])

    def test_export_requires_roll_reference_pair_for_final_reslice(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "missing_roll"
            manager = TifProjectManager()
            manager.create_project("missing_roll", project_root)
            manager.create_specimen_scaffold("01-0101-missing-roll")
            image = np.arange(4 * 5 * 6, dtype=np.uint16).reshape((4, 5, 6))
            image_rel = "specimens/01-0101-missing-roll/working/image.ome.zarr"
            image_meta = write_volume_sidecar(project_root / image_rel, image, role="working_image")
            manager.register_working_volume("01-0101-missing-roll", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            manager.save_project()
            crop_volume_to_part(manager, "01-0101-missing-roll", "head", [[0, 4], [0, 5], [0, 6]], display_name="Head")
            frame = compute_local_frame(
                [1.5, 2.0, 2.5],
                [0.0, 2.0, 2.5],
                [3.0, 2.0, 2.5],
                spacing_zyx=[1.0, 1.0, 1.0],
            )

            with self.assertRaisesRegex(ValueError, "roll_reference"):
                export_part_reslice(
                    manager,
                    "01-0101-missing-roll",
                    "head",
                    {"reslice_id": "axis_without_roll", "template_id": "head", "local_frame": frame},
                )

    def test_source_z_signal_is_navigation_diagnostic_only(self):
        volume = np.zeros((6, 5, 5), dtype=np.uint8)
        volume[2:4, 1:4, 1:4] = 20

        signal = compute_source_z_signal(volume)
        summary = analyze_source_z_signal(signal)

        self.assertEqual(signal["role"], "navigation_diagnostic_only")
        self.assertEqual(signal["axis"], "source_z")
        self.assertIn("source_z_signal_is_auxiliary_navigation_only", summary["warnings"])
        self.assertIn(summary["peak_slice"], {2, 3})
        self.assertIn("not an anatomical direction decision", summary["message"])


if __name__ == "__main__":
    unittest.main()
