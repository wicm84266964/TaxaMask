import tempfile
import unittest
from pathlib import Path

import numpy as np
import tifffile

from AntSleap.core.tif_prediction_import import import_external_prediction_tif
from AntSleap.core.tif_project import TifProjectManager
from AntSleap.core.tif_volume_io import load_volume_sidecar, read_volume_metadata, write_volume_sidecar


def make_project_with_working_and_truth(root):
    project_root = root / "prediction_project"
    manager = TifProjectManager()
    manager.create_project("prediction_project", project_root)
    manager.create_specimen_scaffold(
        "01-0101-20",
        modality="confocal",
        material_map={
            "materials": [
                {"id": 0, "name": "background", "display_name": "Background", "trainable": False},
                {"id": 2, "name": "brain_region", "display_name": "Brain region", "trainable": True},
            ]
        },
    )
    image_rel = "specimens/01-0101-20/working/image.ome.zarr"
    manual_rel = "specimens/01-0101-20/labels/manual_truth.ome.zarr"
    edit_rel = "specimens/01-0101-20/labels/working_edit.ome.zarr"
    image_meta = write_volume_sidecar(
        project_root / image_rel,
        np.zeros((3, 4, 5), dtype=np.uint8),
        role="working_image",
        spacing_zyx=[2.0, 0.5, 0.5],
        spacing_unit="micrometer",
        orientation="zyx",
    )
    manual_meta = write_volume_sidecar(project_root / manual_rel, np.ones((3, 4, 5), dtype=np.uint16), role="manual_truth")
    edit_meta = write_volume_sidecar(project_root / edit_rel, np.zeros((3, 4, 5), dtype=np.uint16), role="working_edit")
    manager.register_working_volume(
        "01-0101-20",
        image_rel,
        image_meta["shape_zyx"],
        image_meta["dtype"],
        spacing_zyx=image_meta["spacing_zyx"],
        spacing_unit=image_meta["spacing_unit"],
        orientation=image_meta["orientation"],
        save=False,
    )
    manager.register_label_volume("01-0101-20", "manual_truth", manual_rel, manual_meta["shape_zyx"], manual_meta["dtype"], save=False)
    manager.register_label_volume("01-0101-20", "working_edit", edit_rel, edit_meta["shape_zyx"], edit_meta["dtype"], save=False)
    manager.set_review_status("01-0101-20", "train_ready", train_ready=True)
    return manager


class TifPredictionImportTests(unittest.TestCase):
    def test_external_prediction_tif_imports_only_model_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_project_with_working_and_truth(root)
            label_tif = root / "nnunet_prediction.tif"
            prediction = np.full((3, 4, 5), 2, dtype=np.uint16)
            tifffile.imwrite(label_tif, prediction, photometric="minisblack")

            result = import_external_prediction_tif(
                manager,
                "01-0101-20",
                label_tif,
                prediction_id="nnunet_fold0",
                source_model="nnUNet",
            )

            specimen = manager.get_specimen("01-0101-20")
            drafts = specimen["labels"]["model_drafts"]
            draft_path = manager.to_absolute(drafts[0]["path"])
            manual = load_volume_sidecar(manager.to_absolute(specimen["labels"]["manual_truth"]["path"]))
            draft = load_volume_sidecar(draft_path)
            metadata = read_volume_metadata(draft_path)

            self.assertEqual(len(drafts), 1)
            self.assertEqual(drafts[0]["prediction_id"], "nnunet_fold0")
            self.assertEqual(drafts[0]["source_model"], "nnUNet")
            self.assertEqual(drafts[0]["role"], "model_draft")
            self.assertEqual(drafts[0]["import_report"], result["report"]["files"]["import_report"])
            np.testing.assert_array_equal(draft, prediction)
            self.assertTrue(np.all(manual == 1))
            self.assertTrue(manager.evaluate_train_ready("01-0101-20")["train_ready"])
            self.assertEqual(metadata["source_format"], "external_prediction_tif")
            self.assertEqual(metadata["spacing_zyx"], [2.0, 0.5, 0.5])
            self.assertTrue(Path(result["report_path"]).exists())
            self.assertFalse(result["report"]["safety"]["manual_truth_overwritten"])

    def test_shape_mismatch_is_rejected_without_draft_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_project_with_working_and_truth(root)
            label_tif = root / "wrong_shape.tif"
            tifffile.imwrite(label_tif, np.zeros((2, 4, 5), dtype=np.uint16), photometric="minisblack")

            with self.assertRaisesRegex(ValueError, "external_prediction_shape_mismatch"):
                import_external_prediction_tif(manager, "01-0101-20", label_tif, prediction_id="wrong_shape")

            specimen = manager.get_specimen("01-0101-20")
            self.assertEqual(specimen["labels"]["model_drafts"], [])
            self.assertFalse((Path(manager.project_dir) / "specimens" / "01-0101-20" / "labels" / "model_draft" / "wrong_shape.ome.zarr").exists())

    def test_float_prediction_tif_is_rejected_as_label_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_project_with_working_and_truth(root)
            label_tif = root / "float_prediction.tif"
            tifffile.imwrite(label_tif, np.zeros((3, 4, 5), dtype=np.float32), photometric="minisblack")

            with self.assertRaisesRegex(ValueError, "prediction_label_tif_must_be_integer_dtype"):
                import_external_prediction_tif(manager, "01-0101-20", label_tif, prediction_id="float_prediction")

            specimen = manager.get_specimen("01-0101-20")
            self.assertEqual(specimen["labels"]["model_drafts"], [])


if __name__ == "__main__":
    unittest.main()
