import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import tifffile

from AntSleap.core.tif_project import TifProjectManager
from AntSleap.core.tif_stack_import import import_tif_stack
from AntSleap.core.tif_volume_io import load_volume_sidecar, read_volume_metadata


class TifStackImportTests(unittest.TestCase):
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
            self.assertEqual(manual_truth["path"], "")
            self.assertFalse(readiness["train_ready"])
            self.assertIn("specimen_not_marked_train_ready", readiness["reasons"])
            self.assertIn("manual_truth_missing", readiness["reasons"])
            self.assertEqual(report["alignment"]["manual_truth"], "not_created")
            self.assertTrue((Path(manager.project_dir) / specimen["source"]["raw_tif"]).exists())
            np.testing.assert_array_equal(load_volume_sidecar(image_abs), source_volume)
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

            with patch("AntSleap.core.tif_stack_import.write_volume_sidecar", side_effect=RuntimeError("disk write failed")):
                with self.assertRaisesRegex(RuntimeError, "disk write failed"):
                    import_tif_stack(manager, tif_path, "01-0101-rollback")

            self.assertIsNone(manager.get_specimen("01-0101-rollback", default=None))
            self.assertFalse((Path(manager.project_dir) / "specimens" / "01-0101-rollback").exists())


if __name__ == "__main__":
    unittest.main()
