import os
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from AntSleap.core.tif_export import export_monai_dataset, export_nnunet_dataset, export_tif_part_nnunet_dataset, export_tif_part_training_dataset, export_tif_training_dataset, read_nifti_volume_with_metadata, write_nifti_volume
from AntSleap.core.tif_local_axis_batch import accept_local_frame_proposal
from AntSleap.core.tif_local_axis_reslice import compute_local_frame, export_part_reslice
from AntSleap.core.tif_part_extraction import crop_volume_to_part, export_part_package
from AntSleap.core.tif_project import TifProjectManager
from AntSleap.core.tif_volume_io import read_volume_metadata, write_volume_sidecar


class TifExportTests(unittest.TestCase):
    def _make_part_training_project(self, root):
        manager = TifProjectManager()
        project_root = Path(root) / "part_project"
        manager.create_project("part_project", project_root)
        manager.create_specimen_scaffold("01-0101-brain")
        image_rel = "specimens/01-0101-brain/working/image.ome.zarr"
        image_meta = write_volume_sidecar(project_root / image_rel, np.arange(3 * 4 * 5, dtype=np.uint8).reshape((3, 4, 5)), role="working_image")
        manager.register_working_volume("01-0101-brain", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
        manager.save_project()
        crop_volume_to_part(manager, "01-0101-brain", "brain", [[0, 2], [0, 3], [0, 4]], display_name="Brain")
        roll_reference = {
            "point_a": {"role": "left_reference", "zyx": [0.5, 0.5, 1.0]},
            "point_b": {"role": "right_reference", "zyx": [0.5, 2.5, 1.0]},
            "point_c": {"role": "plane_reference", "zyx": [1.0, 0.5, 3.0]},
        }
        frame = compute_local_frame([0.5, 1.5, 2.0], [0.0, 1.5, 2.0], [1.0, 1.5, 2.0], roll_reference=roll_reference)
        export_part_reslice(
            manager,
            "01-0101-brain",
            "brain",
            {"reslice_id": "brain_axis_001", "template_id": "brain", "local_frame": frame, "roll_reference": roll_reference},
        )
        reslice = manager.get_part_reslice("01-0101-brain", "brain", "brain_axis_001")
        import tifffile

        reslice_shape = tuple(tifffile.imread(manager.to_absolute(reslice["image_path"])).shape)
        manager.add_or_update_label_schema(
            "brain_regions",
            labels=[{"id": 1, "name": "mushroom_body", "color": "#ff0000"}],
            user_defined_part_name="brain",
            save=False,
        )
        manual_rel = "specimens/01-0101-brain/parts/brain/reslices/brain_axis_001/labels/manual_truth.ome.zarr"
        manual_meta = write_volume_sidecar(project_root / manual_rel, np.ones(reslice_shape, dtype=np.uint16), role="manual_truth")
        manager.register_part_reslice_label_volume(
            "01-0101-brain",
            "brain",
            "brain_axis_001",
            "manual_truth",
            manual_rel,
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
            active_reslice_id="brain_axis_001",
            system_status="verified_train_ready",
            save=True,
        )
        return manager

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

    def test_part_training_export_uses_resliced_part_and_manual_truth(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = self._make_part_training_project(root)
            reslice = manager.get_part_reslice("01-0101-brain", "brain", "brain_axis_001")
            manual_record = manager.part_label_record(
                "01-0101-brain",
                "brain",
                "manual_truth",
                "brain_axis_001",
            )
            editable_rel = "specimens/01-0101-brain/parts/brain/reslices/brain_axis_001/labels/editable_ai_result.ome.zarr"
            editable_meta = write_volume_sidecar(
                root / "part_project" / editable_rel,
                np.full(manual_record["shape_zyx"], 9, dtype=np.uint16),
                role="editable_ai_result",
            )
            manager.register_part_reslice_label_volume(
                "01-0101-brain",
                "brain",
                reslice["reslice_id"],
                "editable_ai_result",
                editable_rel,
                editable_meta["shape_zyx"],
                editable_meta["dtype"],
                status="accepted",
                save=True,
            )
            manager.set_part_training_metadata(
                "01-0101-brain",
                "brain",
                active_reslice_id="brain_axis_001",
                system_status="verified_train_ready",
                save=True,
            )

            result = export_tif_part_training_dataset(manager, root / "part_export", formats=["tiff", "nifti"])

            self.assertEqual(result["exported_count"], 1)
            manifest = result["manifest"]
            self.assertEqual(manifest["schema_version"], "ant3d_tif_part_training_export_v1")
            self.assertEqual(manifest["safety"]["input_scope"], "part_reslice")
            self.assertFalse(manifest["safety"]["allow_editable_ai_result_as_training_label"])
            sample = manifest["samples"][0]
            self.assertEqual(sample["specimen_id"], "01-0101-brain")
            self.assertEqual(sample["part_id"], "brain")
            self.assertEqual(sample["reslice_id"], "brain_axis_001")
            self.assertEqual(sample["label_schema_id"], "brain_regions")
            self.assertEqual(sample["label_role"], "manual_truth")
            self.assertIn("reslices/brain_axis_001/labels/manual_truth.ome.zarr", manager.part_label_record("01-0101-brain", "brain", "manual_truth", "brain_axis_001")["path"])
            self.assertTrue((root / "part_export" / sample["image_exports"]["tiff"]).exists())
            self.assertTrue((root / "part_export" / sample["label_exports"]["tiff"]).exists())
            self.assertTrue((root / "part_export" / sample["label_schema"]).exists())
            import tifffile

            np.testing.assert_array_equal(
                tifffile.imread(root / "part_export" / sample["label_exports"]["tiff"]),
                np.ones(manual_record["shape_zyx"], dtype=np.uint16),
            )

    def test_accepted_ai_and_local_axis_do_not_replace_missing_manual_truth(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = self._make_part_training_project(root)
            specimen_id = "01-0101-brain"
            part_id = "brain"
            reslice_id = "brain_axis_001"
            reslice = manager.get_part_reslice(specimen_id, part_id, reslice_id)
            manual_record = manager.part_label_record(specimen_id, part_id, "manual_truth", reslice_id)

            editable_rel = (
                "specimens/01-0101-brain/parts/brain/reslices/brain_axis_001/"
                "labels/editable_ai_result.ome.zarr"
            )
            editable_meta = write_volume_sidecar(
                root / "part_project" / editable_rel,
                np.full(manual_record["shape_zyx"], 1, dtype=np.uint16),
                role="editable_ai_result",
            )
            manager.register_part_reslice_label_volume(
                specimen_id,
                part_id,
                reslice_id,
                "editable_ai_result",
                editable_rel,
                editable_meta["shape_zyx"],
                editable_meta["dtype"],
                status="accepted",
                save=False,
            )
            reslice["labels"]["manual_truth"] = {}
            manager.set_part_training_metadata(
                specimen_id,
                part_id,
                active_reslice_id=reslice_id,
                system_status="verified_train_ready",
                save=False,
            )
            manager.add_local_frame_proposal(
                specimen_id,
                part_id,
                {
                    "frame_proposal_id": "accepted_axis_without_truth",
                    "template_id": part_id,
                    "origin_zyx": [0.5, 1.5, 2.0],
                    "output_axis_start_zyx": [0.0, 1.5, 2.0],
                    "output_axis_end_zyx": [1.0, 1.5, 2.0],
                    "status": "proposed",
                },
                save=False,
            )
            accepted_axis = accept_local_frame_proposal(
                manager,
                specimen_id,
                part_id,
                "accepted_axis_without_truth",
            )
            manager.save_project()

            readiness = manager.evaluate_part_train_ready(specimen_id, part_id, reslice_id)
            editable_label_report = manager.validate_part_label_ids(
                specimen_id,
                part_id,
                "editable_ai_result",
                reslice_id,
            )

            self.assertEqual(accepted_axis["status"], "accepted")
            self.assertEqual(reslice["labels"]["editable_ai_result"]["status"], "accepted")
            self.assertTrue(editable_label_report["ok"])
            self.assertEqual(editable_label_report["unknown_label_ids"], [])
            for check_name in (
                "part_record_exists",
                "part_volume_exists",
                "reslice_record_exists",
                "reslice_output_exists",
                "label_schema_exists",
                "operator_marked_train_ready",
            ):
                self.assertTrue(readiness["checks"][check_name], check_name)
            self.assertFalse(readiness["train_ready"])
            self.assertFalse(readiness["checks"]["manual_truth_exists"])
            self.assertFalse(readiness["checks"]["training_role_allowed"])
            self.assertEqual(readiness["label_report"]["reasons"], ["manual_truth_missing"])
            self.assertEqual(
                [reason for reason in readiness["reasons"] if reason != "unknown_label_ids"],
                ["manual_truth_missing"],
            )
            with self.assertRaisesRegex(
                ValueError,
                r"part_not_train_ready:01-0101-brain:brain:.*manual_truth_missing",
            ):
                export_tif_part_training_dataset(
                    manager,
                    root / "part_export_without_truth",
                    part_refs=[
                        {
                            "specimen_id": specimen_id,
                            "part_id": part_id,
                            "reslice_id": reslice_id,
                        }
                    ],
                    formats=["tiff"],
                )

    def test_part_nnunet_export_uses_label_schema_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = self._make_part_training_project(root)
            manager.add_or_update_label_schema(
                "brain_regions",
                labels=[
                    {"id": 1, "name": "mushroom_body", "color": "#ff0000"},
                    {"id": 2, "name": "antennal_lobe", "color": "#00ff00"},
                ],
                user_defined_part_name="brain",
                save=True,
            )

            result = export_tif_part_nnunet_dataset(manager, root / "part_nnunet", dataset_name="Dataset901_BrainParts")

            self.assertEqual(result["exported_count"], 1)
            self.assertTrue((root / "part_nnunet" / "imagesTr").exists())
            self.assertTrue((root / "part_nnunet" / "labelsTr").exists())
            self.assertTrue(any((root / "part_nnunet" / "imagesTr").glob("*_0000.nii")))
            self.assertTrue(any((root / "part_nnunet" / "labelsTr").glob("*.nii")))
            with open(root / "part_nnunet" / "dataset.json", "r", encoding="utf-8") as handle:
                dataset_json = json.load(handle)
            self.assertEqual(dataset_json["name"], "Dataset901_BrainParts")
            self.assertEqual(dataset_json["labels"]["background"], 0)
            self.assertEqual(dataset_json["labels"]["mushroom_body"], 1)
            self.assertEqual(dataset_json["labels"]["antennal_lobe"], 2)
            manifest = result["manifest"]
            self.assertEqual(manifest["schema_version"], "ant3d_tif_part_nnunet_dataset_v1")
            self.assertEqual(manifest["safety"]["input_scope"], "part_reslice")
            self.assertFalse(manifest["safety"]["allow_editable_ai_result_as_training_label"])
            self.assertEqual(manifest["training"][0]["part_id"], "brain")

    def test_part_nnunet_export_can_write_compact_nii_gz_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = self._make_part_training_project(root)
            manager.add_or_update_label_schema(
                "brain_regions",
                labels=[
                    {"id": 2, "name": "mushroom_body", "color": "#ff0000"},
                    {"id": 5, "name": "antennal_lobe", "color": "#00ff00"},
                ],
                user_defined_part_name="brain",
                save=True,
            )
            manual_rel = manager.part_label_record("01-0101-brain", "brain", "manual_truth", "brain_axis_001")["path"]
            import tifffile

            reslice = manager.get_part_reslice("01-0101-brain", "brain", "brain_axis_001")
            shape = tuple(tifffile.imread(manager.to_absolute(reslice["image_path"])).shape)
            labels = np.zeros(shape, dtype=np.uint16)
            labels.flat[0] = 2
            labels.flat[-1] = 5
            write_volume_sidecar(root / "part_project" / manual_rel, labels, role="manual_truth")

            result = export_tif_part_nnunet_dataset(
                manager,
                root / "part_nnunet",
                dataset_name="Dataset902_BrainParts",
                file_ending=".nii.gz",
                label_id_mode="compact",
                split_mode="leave_one_val",
            )

            self.assertTrue(any((root / "part_nnunet" / "imagesTr").glob("*_0000.nii.gz")))
            self.assertTrue(any((root / "part_nnunet" / "labelsTr").glob("*.nii.gz")))
            with open(root / "part_nnunet" / "dataset.json", "r", encoding="utf-8") as handle:
                dataset_json = json.load(handle)
            self.assertEqual(dataset_json["file_ending"], ".nii.gz")
            self.assertEqual(dataset_json["labels"]["mushroom_body"], 1)
            self.assertEqual(dataset_json["labels"]["antennal_lobe"], 2)
            manifest = result["manifest"]
            self.assertEqual(manifest["label_id_mode"], "compact")
            self.assertEqual(manifest["label_id_mapping"]["source_to_nnunet"]["2"], 1)
            self.assertEqual(manifest["label_id_mapping"]["source_to_nnunet"]["5"], 2)
            self.assertTrue((root / "part_nnunet" / "splits_final.json").exists())

    def test_nifti_round_trip_preserves_spacing_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "volume.nii.gz"
            array = np.zeros((2, 3, 4), dtype=np.uint16)

            write_nifti_volume(path, array, {"spacing_zyx": [2.5, 1.5, 0.75], "spacing_unit": "micrometer"})
            loaded, metadata = read_nifti_volume_with_metadata(path)

            np.testing.assert_array_equal(loaded, array)
            self.assertEqual(metadata["spacing_zyx"], [2.5, 1.5, 0.75])
            self.assertEqual(metadata["spacing_unit"], "micrometer")

    def test_part_nnunet_export_rejects_mixed_incompatible_label_schemas(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = self._make_part_training_project(root)
            specimen = manager.get_specimen("01-0101-brain")
            source_part = manager.get_part("01-0101-brain", "brain")
            import copy

            second = copy.deepcopy(source_part)
            second["part_id"] = "brain_alt"
            second["display_name"] = "Brain alt"
            second["training"]["label_schema_id"] = "brain_regions_alt"
            specimen["parts"].append(second)
            manager.add_or_update_label_schema(
                "brain_regions_alt",
                labels=[{"id": 1, "name": "central_complex", "color": "#0000ff"}],
                user_defined_part_name="brain",
                save=True,
            )

            with self.assertRaisesRegex(ValueError, "mixed_part_label_schemas_not_supported"):
                export_tif_part_nnunet_dataset(
                    manager,
                    root / "part_nnunet",
                    part_refs=[
                        {"specimen_id": "01-0101-brain", "part_id": "brain", "reslice_id": "brain_axis_001"},
                        {"specimen_id": "01-0101-brain", "part_id": "brain_alt", "reslice_id": "brain_axis_001"},
                    ],
                )

    def test_part_training_export_rejects_empty_sample_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = self._make_part_training_project(root)

            with self.assertRaisesRegex(ValueError, "no_part_training_samples"):
                export_tif_part_training_dataset(manager, root / "part_export", part_refs=[])

    def test_part_package_export_keeps_part_artifacts_separate_from_training(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            project_root = root / "project"
            manager.create_project("part_export", project_root)
            manager.create_specimen_scaffold("01-0101-part")
            image_rel = "specimens/01-0101-part/working/image.ome.zarr"
            image_meta = write_volume_sidecar(project_root / image_rel, np.arange(4 * 5 * 6, dtype=np.uint8).reshape((4, 5, 6)), role="working_image")
            manager.register_working_volume("01-0101-part", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            manager.save_project()
            crop_volume_to_part(manager, "01-0101-part", "head", [[1, 3], [1, 4], [2, 5]], display_name="Head")

            result = export_part_package(manager, "01-0101-part", "head", root / "parts_export")

            package_dir = Path(result["package_dir"])
            self.assertTrue((package_dir / "image.ome.zarr").exists())
            self.assertTrue((package_dir / "mask.ome.zarr").exists())
            self.assertTrue((package_dir / "contours.json").exists())
            self.assertTrue((package_dir / "extraction.json").exists())
            self.assertTrue((package_dir / "part_manifest.json").exists())
            self.assertEqual(result["manifest"]["part_id"], "head")
            self.assertEqual(result["manifest"]["parent_bbox_zyx"], [[1, 3], [1, 4], [2, 5]])

    def test_part_package_export_creates_new_folder_instead_of_overwriting_existing_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            project_root = root / "project"
            manager.create_project("part_export_versioned", project_root)
            manager.create_specimen_scaffold("01-0101-part")
            image_rel = "specimens/01-0101-part/working/image.ome.zarr"
            image_meta = write_volume_sidecar(project_root / image_rel, np.arange(4 * 5 * 6, dtype=np.uint8).reshape((4, 5, 6)), role="working_image")
            manager.register_working_volume("01-0101-part", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            manager.save_project()
            crop_volume_to_part(manager, "01-0101-part", "head", [[1, 3], [1, 4], [2, 5]], display_name="Head")

            first = export_part_package(manager, "01-0101-part", "head", root / "parts_export")
            sentinel = Path(first["package_dir"]) / "review_note.txt"
            sentinel.write_text("keep this review note", encoding="utf-8")
            second = export_part_package(manager, "01-0101-part", "head", root / "parts_export")

            self.assertNotEqual(first["package_dir"], second["package_dir"])
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep this review note")
            self.assertTrue((Path(second["package_dir"]) / "part_manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
