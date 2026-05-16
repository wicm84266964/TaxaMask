import os
import tempfile
import unittest
from pathlib import Path

import numpy as np

from AntSleap.core.tif_export import export_monai_dataset, export_nnunet_dataset, export_tif_training_dataset
from AntSleap.core.tif_project import TifProjectManager
from AntSleap.core.tif_volume_io import read_volume_metadata, write_volume_sidecar


class TifExportTests(unittest.TestCase):
    def test_sidecar_writes_minimal_ome_ngff_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            sidecar = Path(tmp) / "image.ome.zarr"
            metadata = write_volume_sidecar(sidecar, np.zeros((2, 3, 4), dtype=np.uint8), role="working_image")
            self.assertTrue(metadata["ome_ngff_complete"])
            self.assertTrue((sidecar / ".zgroup").exists())
            self.assertTrue((sidecar / ".zattrs").exists())
            self.assertTrue((sidecar / "0" / ".zarray").exists())
            self.assertTrue((sidecar / "0" / "0.0.0").exists())
            reloaded = read_volume_metadata(sidecar)
            self.assertEqual(reloaded["zarr_array_path"], "0")

    def test_training_export_writes_exchange_formats_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            project_root = root / "project"
            manager.create_project("exportable", project_root)
            specimen = manager.create_specimen_scaffold(
                "01-0101-12",
                material_map={
                    "materials": [
                        {"id": 0, "name": "background", "trainable": False},
                        {"id": 2, "name": "brain", "trainable": True},
                    ]
                },
                modality="confocal",
            )
            image = np.arange(24, dtype=np.uint16).reshape((2, 3, 4))
            label = np.ones((2, 3, 4), dtype=np.uint16)
            image_rel = "specimens/01-0101-12/working/image.ome.zarr"
            label_rel = "specimens/01-0101-12/labels/manual_truth.ome.zarr"
            image_meta = write_volume_sidecar(project_root / image_rel, image, role="working_image")
            label_meta = write_volume_sidecar(project_root / label_rel, label, role="manual_truth")
            manager.register_working_volume("01-0101-12", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            manager.register_label_volume("01-0101-12", "manual_truth", label_rel, label_meta["shape_zyx"], label_meta["dtype"], save=False)
            specimen["train_ready"] = True
            specimen["review_status"] = "train_ready"
            manager.save_project()

            result = export_tif_training_dataset(
                manager,
                root / "export",
                formats=["ome_tiff", "nrrd", "mha", "nifti"],
            )
            self.assertEqual(result["exported_count"], 1)
            manifest = result["manifest"]
            self.assertEqual(manifest["schema_version"], "ant3d_tif_training_export_v1")
            exported = manifest["specimens"][0]
            for key in ["ome_tiff", "nrrd", "mha", "nifti"]:
                self.assertIn(key, exported["image_exports"])
                self.assertIn(key, exported["label_exports"])
                self.assertTrue((root / "export" / exported["image_exports"][key]).exists())
                self.assertTrue((root / "export" / exported["label_exports"][key]).exists())
            with open(root / "export" / exported["image_exports"]["nrrd"], "rb") as handle:
                self.assertEqual(handle.read(8), b"NRRD0005")
            with open(root / "export" / exported["image_exports"]["mha"], "rb") as handle:
                self.assertIn(b"ObjectType = Image", handle.read(64))
            with open(root / "export" / exported["image_exports"]["nifti"], "rb") as handle:
                self.assertEqual(handle.read(4), (348).to_bytes(4, "little", signed=True))

    def test_nnunet_and_monai_exports_create_backend_layouts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            project_root = root / "project"
            manager.create_project("backend_layouts", project_root)
            specimen = manager.create_specimen_scaffold(
                "01-0101-14",
                material_map={
                    "materials": [
                        {"id": 0, "name": "background", "trainable": False},
                        {"id": 1, "name": "region", "trainable": True},
                    ]
                },
            )
            image_rel = "specimens/01-0101-14/working/image.ome.zarr"
            label_rel = "specimens/01-0101-14/labels/manual_truth.ome.zarr"
            image_meta = write_volume_sidecar(project_root / image_rel, np.zeros((2, 3, 4), dtype=np.uint8), role="working_image")
            label_meta = write_volume_sidecar(project_root / label_rel, np.ones((2, 3, 4), dtype=np.uint16), role="manual_truth")
            manager.register_working_volume("01-0101-14", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            manager.register_label_volume("01-0101-14", "manual_truth", label_rel, label_meta["shape_zyx"], label_meta["dtype"], save=False)
            specimen["train_ready"] = True
            specimen["review_status"] = "train_ready"
            manager.save_project()

            nnunet = export_nnunet_dataset(manager, root / "nnunet", dataset_name="Dataset777_Ants")
            self.assertEqual(nnunet["exported_count"], 1)
            self.assertTrue((root / "nnunet" / "dataset.json").exists())
            self.assertTrue(any((root / "nnunet" / "imagesTr").glob("*_0000.nii")))
            self.assertTrue(any((root / "nnunet" / "labelsTr").glob("*.nii")))

            monai = export_monai_dataset(manager, root / "monai")
            self.assertEqual(monai["exported_count"], 1)
            self.assertTrue((root / "monai" / "monai_datalist.json").exists())
            self.assertTrue((root / "monai" / "monai_manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
