import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import tifffile

from AntSleap.core.tif_project import TifProjectManager
from AntSleap.core.tif_stack_import import (
    _build_tif_working_sidecar,
    import_tif_slice_series,
    import_tif_stack,
    materialize_registered_tif_stack,
    register_tif_stack_metadata,
)
from AntSleap.core.tif_volume_io import load_volume_sidecar, read_volume_metadata


class TifStackImportTests(unittest.TestCase):
    def test_tif_slice_series_imports_only_selected_files_in_natural_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slices_dir = root / "selected_slices"
            slices_dir.mkdir()
            paths = {}
            for number in (1, 2, 3, 10):
                path = slices_dir / f"slice_{number}.tif"
                tifffile.imwrite(path, np.full((4, 5), number, dtype=np.uint16), photometric="minisblack")
                paths[number] = path

            manager = TifProjectManager()
            manager.create_project("slice_subset", root / "slice_subset_project")
            progress = []
            result = import_tif_slice_series(
                manager,
                [paths[10], paths[2]],
                "selected-brain-region",
                progress_callback=lambda current, total, message: progress.append((current, total, message)),
            )

            specimen = manager.get_specimen("selected-brain-region")
            image_abs = manager.to_absolute(specimen["working_volume"]["path"])
            volume = load_volume_sidecar(image_abs)
            self.assertEqual(list(volume.shape), [2, 4, 5])
            np.testing.assert_array_equal(volume[0], np.full((4, 5), 2, dtype=np.uint16))
            np.testing.assert_array_equal(volume[1], np.full((4, 5), 10, dtype=np.uint16))
            self.assertEqual(specimen["source"]["raw_tif"], "")
            manifest_rel = specimen["source"]["tif_slice_series_manifest"]
            manifest = json.loads(Path(manager.to_absolute(manifest_rel)).read_text(encoding="utf-8"))
            self.assertEqual([item["filename"] for item in manifest["slices"]], ["slice_2.tif", "slice_10.tif"])
            self.assertEqual([item["z_index"] for item in manifest["slices"]], [0, 1])
            self.assertEqual(manifest["selected_file_count"], 2)
            self.assertEqual(manifest["photometric"], "MINISBLACK")
            self.assertEqual(manifest["samples_per_pixel"], 1)
            self.assertEqual(result["report"]["source_series"]["selected_file_count"], 2)
            self.assertEqual(result["report"]["source_series"]["ordering"], "natural_filename_v1")
            self.assertEqual(result["report"]["tiff_metadata"]["photometric"], "MINISBLACK")
            self.assertTrue(result["report"]["memory_policy"]["one_source_slice_loaded_at_a_time"])
            self.assertFalse(result["report"]["memory_policy"]["whole_volume_imread"])
            self.assertTrue(progress)
            normalized_progress = [current / float(max(1, total)) for current, total, _message in progress]
            self.assertEqual(normalized_progress, sorted(normalized_progress))
            self.assertIn((94, 100, "Finalizing working volume"), progress)

    def test_tif_slice_series_shape_mismatch_leaves_no_specimen(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "slice_1.tif"
            second = root / "slice_2.tif"
            tifffile.imwrite(first, np.ones((4, 5), dtype=np.uint8), photometric="minisblack")
            tifffile.imwrite(second, np.ones((5, 5), dtype=np.uint8), photometric="minisblack")

            manager = TifProjectManager()
            manager.create_project("shape_mismatch", root / "shape_mismatch_project")
            with self.assertRaisesRegex(ValueError, "tif_slice_series_shape_mismatch"):
                import_tif_slice_series(manager, [second, first], "invalid-series")

            self.assertIsNone(manager.get_specimen("invalid-series", default=None))
            self.assertEqual(manager.project_data["specimens"], [])

    def test_tif_slice_series_dtype_mismatch_leaves_no_specimen(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "slice_1.tif"
            second = root / "slice_2.tif"
            tifffile.imwrite(first, np.ones((4, 5), dtype=np.uint8), photometric="minisblack")
            tifffile.imwrite(second, np.ones((4, 5), dtype=np.uint16), photometric="minisblack")

            manager = TifProjectManager()
            manager.create_project("dtype_mismatch", root / "dtype_mismatch_project")
            specimen_root = Path(manager.to_absolute(manager.specimen_dir("invalid-dtype-series")))
            with self.assertRaisesRegex(ValueError, "tif_slice_series_dtype_mismatch"):
                import_tif_slice_series(manager, [second, first], "invalid-dtype-series")

            self.assertIsNone(manager.get_specimen("invalid-dtype-series", default=None))
            self.assertFalse(specimen_root.exists())

    def test_tif_slice_series_midstream_failure_removes_partial_specimen(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "slice_1.tif"
            second = root / "slice_2.tif"
            tifffile.imwrite(first, np.ones((4, 5), dtype=np.uint8), photometric="minisblack")
            tifffile.imwrite(second, np.ones((4, 5), dtype=np.uint8), photometric="minisblack")

            manager = TifProjectManager()
            manager.create_project("stream_failure", root / "stream_failure_project")
            specimen_root = Path(manager.to_absolute(manager.specimen_dir("partial-series")))
            with patch(
                "AntSleap.core.tif_stack_import._read_tif_slice_yx",
                side_effect=[np.ones((4, 5), dtype=np.uint8), OSError("simulated_read_failure")],
            ):
                with self.assertRaisesRegex(OSError, "simulated_read_failure"):
                    import_tif_slice_series(manager, [second, first], "partial-series")

            self.assertIsNone(manager.get_specimen("partial-series", default=None))
            self.assertFalse(specimen_root.exists())
            self.assertFalse((specimen_root / "working" / "image.ome.zarr.building").exists())

    def test_tif_slice_series_rejects_palette_tif(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            palette_slice = root / "palette_slice.tif"
            colormap = np.zeros((3, 256), dtype=np.uint16)
            colormap[0] = np.arange(256, dtype=np.uint16) * 257
            tifffile.imwrite(
                palette_slice,
                np.arange(20, dtype=np.uint8).reshape((4, 5)),
                photometric="palette",
                colormap=colormap,
            )

            manager = TifProjectManager()
            manager.create_project("palette_reject", root / "palette_reject_project")
            with self.assertRaisesRegex(ValueError, "tif_slice_file_must_be_grayscale"):
                import_tif_slice_series(manager, [palette_slice], "invalid-palette")

            self.assertIsNone(manager.get_specimen("invalid-palette", default=None))

    def test_tif_slice_series_rejects_mixed_photometric_meanings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            black_zero = root / "slice_1.tif"
            white_zero = root / "slice_2.tif"
            tifffile.imwrite(black_zero, np.ones((4, 5), dtype=np.uint8), photometric="minisblack")
            tifffile.imwrite(white_zero, np.ones((4, 5), dtype=np.uint8), photometric="miniswhite")

            manager = TifProjectManager()
            manager.create_project("photometric_mismatch", root / "photometric_mismatch_project")
            with self.assertRaisesRegex(ValueError, "tif_slice_series_photometric_mismatch"):
                import_tif_slice_series(manager, [white_zero, black_zero], "invalid-photometric")

            self.assertIsNone(manager.get_specimen("invalid-photometric", default=None))

    def test_tif_slice_series_rejects_multipage_stack_as_one_slice(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stack = root / "not_a_single_slice.tif"
            tifffile.imwrite(
                stack,
                np.ones((2, 4, 5), dtype=np.uint8),
                photometric="minisblack",
            )

            manager = TifProjectManager()
            manager.create_project("multipage_reject", root / "multipage_reject_project")
            with self.assertRaisesRegex(ValueError, "tif_slice_file_must_contain_one_page"):
                import_tif_slice_series(manager, [stack], "invalid-multipage")

            self.assertIsNone(manager.get_specimen("invalid-multipage", default=None))

    def test_plain_tif_stack_import_creates_working_volume_but_not_manual_truth(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tif_path = root / "brain_stack.tif"
            source_volume = np.arange(3 * 4 * 5, dtype=np.uint8).reshape((3, 4, 5))
            tifffile.imwrite(tif_path, source_volume, photometric="minisblack")

            manager = TifProjectManager()
            manager.create_project("plain_tif", root / "plain_tif_project")
            result = import_tif_stack(
                manager,
                tif_path,
                "01-0101-05",
                modality="micro_ct",
                material_map={
                    "source": "manual",
                    "materials": [
                        {"id": 0, "name": "background", "display_name": "Background", "trainable": False},
                        {"id": 1, "name": "brain_region", "display_name": "Brain region", "trainable": True},
                    ],
                },
            )

            specimen = manager.get_specimen("01-0101-05")
            readiness = manager.evaluate_train_ready("01-0101-05")
            image_abs = manager.to_absolute(specimen["working_volume"]["path"])
            edit_abs = manager.to_absolute(specimen["labels"]["working_edit"]["path"])
            manual_truth = specimen["labels"]["manual_truth"]
            report = result["report"]

            self.assertEqual(specimen["modality"], "micro_ct")
            self.assertEqual(specimen["working_volume"]["shape_zyx"], [3, 4, 5])
            self.assertEqual(specimen["working_volume"]["spacing_unit"], "unknown")
            self.assertEqual(manual_truth["path"], "")
            self.assertFalse(readiness["train_ready"])
            self.assertIn("specimen_not_marked_train_ready", readiness["reasons"])
            self.assertIn("manual_truth_missing", readiness["reasons"])
            self.assertEqual(report["alignment"]["manual_truth"], "not_created")
            self.assertEqual(report["memory_policy"]["import_mode"], "stream_to_memmap_sidecar")
            self.assertFalse(report["memory_policy"]["whole_volume_imread"])
            self.assertTrue(report["memory_policy"]["source_tif_copied"])
            self.assertTrue(report["memory_policy"]["working_edit_created_on_import"])
            self.assertEqual(report["tiff_metadata"]["spacing_unit"], "unknown")
            self.assertIn("physical_spacing_unit_unknown", report["warnings"])
            self.assertTrue((Path(manager.project_dir) / specimen["source"]["raw_tif"]).exists())
            np.testing.assert_array_equal(load_volume_sidecar(image_abs), source_volume)
            self.assertEqual(read_volume_metadata(image_abs)["spacing_unit"], "unknown")
            self.assertEqual(read_volume_metadata(edit_abs)["shape_zyx"], [3, 4, 5])
            self.assertTrue(np.all(load_volume_sidecar(edit_abs) == 0))

    def test_single_page_tif_is_imported_as_one_slice_volume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tif_path = root / "single_slice.tif"
            tifffile.imwrite(tif_path, np.ones((6, 7), dtype=np.uint16), photometric="minisblack")

            manager = TifProjectManager()
            manager.create_project("single_slice", root / "single_slice_project")
            import_tif_stack(manager, tif_path, "01-0101-06")
            specimen = manager.get_specimen("01-0101-06")

            self.assertEqual(specimen["working_volume"]["shape_zyx"], [1, 6, 7])
            self.assertFalse(manager.evaluate_train_ready("01-0101-06")["train_ready"])

    def test_plain_tif_stack_import_does_not_use_whole_volume_imread(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tif_path = root / "stream_stack.tif"
            source_volume = np.arange(2 * 3 * 4, dtype=np.uint8).reshape((2, 3, 4))
            tifffile.imwrite(tif_path, source_volume, photometric="minisblack")

            manager = TifProjectManager()
            manager.create_project("stream_tif", root / "stream_tif_project")
            progress = []

            with patch("AntSleap.core.tif_stack_import.tifffile.imread", side_effect=AssertionError("imread should not be used")):
                result = import_tif_stack(
                    manager,
                    tif_path,
                    "01-0101-stream",
                    progress_callback=lambda current, total, message: progress.append((current, total, message)),
                )

            specimen = manager.get_specimen("01-0101-stream")
            image_abs = manager.to_absolute(specimen["working_volume"]["path"])
            np.testing.assert_array_equal(load_volume_sidecar(image_abs), source_volume)
            self.assertFalse(result["report"]["memory_policy"]["whole_volume_imread"])
            self.assertTrue(progress)

    def test_working_sidecar_replaces_stale_building_directory_atomically(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tif_path = root / "stack.tif"
            source_volume = np.arange(2 * 3 * 4, dtype=np.uint8).reshape((2, 3, 4))
            tifffile.imwrite(tif_path, source_volume, photometric="minisblack")
            image_path = root / "working" / "image.ome.zarr"
            building_path = Path(f"{image_path}.building")
            building_path.mkdir(parents=True)
            (building_path / "stale.txt").write_text("interrupted import", encoding="utf-8")

            _build_tif_working_sidecar(
                tif_path,
                image_path,
                {
                    "shape_zyx": list(source_volume.shape),
                    "dtype": str(source_volume.dtype),
                    "spacing_zyx": [1.0, 1.0, 1.0],
                    "spacing_unit": "unknown",
                    "orientation": "unknown",
                    "source_path": str(tif_path),
                },
            )

            self.assertTrue(image_path.is_dir())
            self.assertFalse(building_path.exists())
            np.testing.assert_array_equal(load_volume_sidecar(image_path), source_volume)

    def test_failed_working_sidecar_build_cleans_temporary_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_path = root / "working" / "image.ome.zarr"
            building_path = Path(f"{image_path}.building")

            def fail_after_partial_write(_source_path, target_path, _metadata, progress_callback=None):
                del progress_callback
                target = Path(target_path)
                target.mkdir(parents=True)
                (target / "partial.bin").write_bytes(b"partial")
                raise RuntimeError("mechanical disk write failed")

            with patch("AntSleap.core.tif_stack_import._stream_tif_stack_to_sidecar", side_effect=fail_after_partial_write):
                with self.assertRaisesRegex(RuntimeError, "mechanical disk write failed"):
                    _build_tif_working_sidecar("source.tif", image_path, {})

            self.assertFalse(image_path.exists())
            self.assertFalse(building_path.exists())

    def test_plain_tif_stack_import_can_defer_source_copy_and_working_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tif_path = root / "preview_only.tif"
            source_volume = np.arange(2 * 3 * 4, dtype=np.uint8).reshape((2, 3, 4))
            tifffile.imwrite(tif_path, source_volume, photometric="minisblack")

            manager = TifProjectManager()
            manager.create_project("preview_only", root / "preview_project")
            result = import_tif_stack(
                manager,
                tif_path,
                "01-0101-preview",
                copy_source=False,
                create_working_edit=False,
            )

            specimen = manager.get_specimen("01-0101-preview")
            self.assertEqual(os.path.normcase(specimen["source"]["raw_tif"]), os.path.normcase(str(tif_path.resolve())))
            self.assertEqual(specimen["labels"]["working_edit"]["path"], "")
            self.assertEqual(result["report"]["files"]["working_edit"], "")
            self.assertFalse(result["report"]["memory_policy"]["source_tif_copied"])
            self.assertFalse(result["report"]["memory_policy"]["working_edit_created_on_import"])
            self.assertFalse((Path(manager.project_dir) / "specimens" / "01-0101-preview" / "source" / "raw" / tif_path.name).exists())

    def test_metadata_only_tif_registration_does_not_create_sidecar_or_read_volume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tif_path = root / "metadata_only.tif"
            source_volume = np.arange(2 * 3 * 4, dtype=np.uint8).reshape((2, 3, 4))
            tifffile.imwrite(tif_path, source_volume, photometric="minisblack")

            manager = TifProjectManager()
            manager.create_project("metadata_only", root / "metadata_project")
            with patch("AntSleap.core.tif_stack_import._stream_tif_stack_to_sidecar", side_effect=AssertionError("sidecar should not be created")):
                result = register_tif_stack_metadata(manager, tif_path, "01-0101-meta")

            specimen = manager.get_specimen("01-0101-meta")
            self.assertEqual(os.path.normcase(specimen["source"]["raw_tif"]), os.path.normcase(str(tif_path.resolve())))
            self.assertEqual(specimen["metadata"]["import_status"], "metadata_only")
            self.assertEqual(specimen["metadata"]["shape_zyx"], [2, 3, 4])
            self.assertEqual(specimen["metadata"]["dtype"], "uint8")
            self.assertEqual(specimen["metadata"]["source_file_size"], tif_path.stat().st_size)
            self.assertEqual(specimen["working_volume"]["path"], "")
            self.assertEqual(specimen["working_volume"]["shape_zyx"], [2, 3, 4])
            self.assertEqual(specimen["working_volume"]["status"], "metadata_only")
            self.assertEqual(specimen["working_volume"]["spacing_unit"], "unknown")
            self.assertIn("physical_spacing_unit_unknown", result["report"]["warnings"])
            self.assertEqual(result["report"]["memory_policy"]["import_mode"], "metadata_only")
            self.assertFalse(result["report"]["memory_policy"]["sidecar_created_on_import"])
            self.assertFalse((Path(manager.project_dir) / "specimens" / "01-0101-meta" / "working" / "image.ome.zarr").exists())

    def test_failed_materialize_restores_metadata_record_and_import_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tif_path = root / "metadata_only.tif"
            source_volume = np.arange(2 * 3 * 4, dtype=np.uint8).reshape((2, 3, 4))
            tifffile.imwrite(tif_path, source_volume, photometric="minisblack")

            manager = TifProjectManager()
            manifest_path = manager.create_project("materialize_rollback", root / "materialize_rollback")
            result = register_tif_stack_metadata(manager, tif_path, "01-0101-meta")
            specimen_before = copy.deepcopy(manager.get_specimen("01-0101-meta"))
            report_path = Path(result["report_path"])
            report_before = report_path.read_bytes()
            image_path = Path(manager.project_dir) / "specimens" / "01-0101-meta" / "working" / "image.ome.zarr"

            with patch.object(manager, "save_project", side_effect=RuntimeError("sqlite write failed")):
                with self.assertRaisesRegex(RuntimeError, "sqlite write failed"):
                    materialize_registered_tif_stack(manager, "01-0101-meta")

            self.assertEqual(manager.get_specimen("01-0101-meta"), specimen_before)
            self.assertEqual(report_path.read_bytes(), report_before)
            self.assertFalse(image_path.exists())

            reloaded = TifProjectManager()
            reloaded.load_project(manifest_path)
            reloaded_specimen = reloaded.get_specimen("01-0101-meta")
            self.assertEqual((reloaded_specimen.get("metadata") or {}).get("import_status"), "metadata_only")
            self.assertEqual((reloaded_specimen.get("working_volume") or {}).get("path"), "")
            self.assertEqual(
                os.path.normcase((reloaded_specimen.get("source") or {}).get("raw_tif", "")),
                os.path.normcase(str(tif_path.resolve())),
            )

    def test_failed_tif_read_does_not_leave_half_registered_specimen(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tif_path = root / "broken_stack.tif"
            tif_path.write_bytes(b"not a tif")

            manager = TifProjectManager()
            manager.create_project("broken_tif", root / "broken_tif_project")

            with self.assertRaises(Exception):
                import_tif_stack(manager, tif_path, "01-0101-broken")

            self.assertIsNone(manager.get_specimen("01-0101-broken", default=None))
            self.assertEqual(manager.project_data["specimens"], [])

    def test_failed_tif_sidecar_write_rolls_back_registered_specimen_and_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tif_path = root / "stack.tif"
            tifffile.imwrite(tif_path, np.ones((2, 3, 4), dtype=np.uint8), photometric="minisblack")

            manager = TifProjectManager()
            manager.create_project("rollback_tif", root / "rollback_project")

            with patch("AntSleap.core.tif_stack_import.create_volume_sidecar_memmap", side_effect=RuntimeError("disk write failed")):
                with self.assertRaisesRegex(RuntimeError, "disk write failed"):
                    import_tif_stack(manager, tif_path, "01-0101-rollback")

            self.assertIsNone(manager.get_specimen("01-0101-rollback", default=None))
            self.assertFalse((Path(manager.project_dir) / "specimens" / "01-0101-rollback").exists())


if __name__ == "__main__":
    unittest.main()
