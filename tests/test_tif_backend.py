import json
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np

from AntSleap.core.tif_backend import (
    TIF_BACKEND_CONTRACT_SCHEMA_VERSION,
    TifBackendRunner,
    write_mock_tif_backend_result,
)
from AntSleap.core.tif_project import TifProjectManager
from AntSleap.core.tif_volume_io import load_volume_sidecar, write_volume_sidecar


def make_train_ready_project(root):
    manager = TifProjectManager()
    manager.create_project("backend", root / "backend")
    manager.create_specimen_scaffold(
        "01-0101-11",
        modality="micro_ct",
        material_map={
            "materials": [
                {"id": 0, "name": "background", "display_name": "Background", "trainable": False},
                {"id": 2, "name": "brain_region", "display_name": "Brain region", "trainable": True},
            ]
        },
    )
    image_rel = "specimens/01-0101-11/working/image.ome.zarr"
    manual_rel = "specimens/01-0101-11/labels/manual_truth.ome.zarr"
    image_meta = write_volume_sidecar(root / "backend" / image_rel, np.zeros((2, 3, 4), dtype=np.uint8), role="working_image")
    manual_meta = write_volume_sidecar(root / "backend" / manual_rel, np.ones((2, 3, 4), dtype=np.uint16), role="manual_truth")
    manager.register_working_volume("01-0101-11", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
    manager.register_label_volume("01-0101-11", "manual_truth", manual_rel, manual_meta["shape_zyx"], manual_meta["dtype"], save=False)
    manager.set_review_status("01-0101-11", "train_ready", train_ready=True)
    return manager


class TifBackendTests(unittest.TestCase):
    def test_contract_uses_manual_truth_for_prepare_dataset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_train_ready_project(root)
            runner = TifBackendRunner(manager, {"backend_id": "mock_volume"})
            contract = runner.build_contract("prepare_dataset", ["01-0101-11"])

            self.assertEqual(contract["schema_version"], TIF_BACKEND_CONTRACT_SCHEMA_VERSION)
            self.assertTrue(contract["safety"]["protect_manual_truth"])
            self.assertFalse(contract["safety"]["allow_model_draft_as_training_label"])
            self.assertEqual(contract["specimens"][0]["label_volume"]["role"], "manual_truth")
            self.assertTrue(contract["specimens"][0]["label_volume"]["path"].endswith("manual_truth.ome.zarr"))

    def test_prepare_dataset_run_exports_training_exchange_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_train_ready_project(root)
            helper = root / "mock_prepare.py"
            helper.write_text(
                "\n".join(
                    [
                        "import json",
                        "payload=json.load(open('contract.json', encoding='utf-8'))",
                        "result={",
                        "  'schema_version':'ant3d_tif_backend_result_v1',",
                        "  'contract_schema_version':'ant3d_tif_backend_contract_v1',",
                        "  'status':'success',",
                        "  'action':'prepare_dataset',",
                        "  'backend_id':payload['backend_id'],",
                        "  'run_id':payload['run_id'],",
                        "  'artifacts':[{'type':'dataset_manifest','path':payload['dataset_manifest'],'format':'json'}],",
                        "  'metrics':{},",
                        "  'warnings':[],",
                        "  'errors':[],",
                        "  'provenance':{'dataset_manifest':payload['dataset_manifest']},",
                        "}",
                        "json.dump(result, open(payload['result_json'], 'w', encoding='utf-8'))",
                    ]
                ),
                encoding="utf-8",
            )
            runner = TifBackendRunner(
                manager,
                {
                    "backend_id": "mock_export_backend",
                    "prepare_dataset_command": f"{os.sys.executable} {helper}",
                    "export_formats": "nrrd,mha",
                },
                runs_root=root / "runs",
            )
            result = runner.run_action("prepare_dataset", ["01-0101-11"])
            manifest_path = result["contract"]["dataset_manifest"]
            self.assertTrue(os.path.exists(manifest_path))
            self.assertEqual(result["contract"]["dataset_formats"], ["nrrd", "mha"])
            with open(manifest_path, "r", encoding="utf-8") as handle:
                manifest = json.load(handle)
            self.assertEqual(manifest["formats"], ["nrrd", "mha"])

    def test_predict_result_imports_only_model_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_train_ready_project(root)
            runner = TifBackendRunner(manager, {"backend_id": "mock_volume"})
            contract = runner.build_contract("predict", ["01-0101-11"])
            runner.write_contract(contract)
            prediction = np.full((2, 3, 4), 2, dtype=np.uint16)
            result = write_mock_tif_backend_result(contract, {"01-0101-11": prediction})
            result = runner.read_result(contract["result_json"])
            imported = runner.import_prediction_result(result)

            specimen = manager.get_specimen("01-0101-11")
            manual = load_volume_sidecar(manager.to_absolute(specimen["labels"]["manual_truth"]["path"]))
            draft = load_volume_sidecar(manager.to_absolute(imported[0]["path"]))

            self.assertEqual(len(imported), 1)
            self.assertEqual(len(specimen["labels"]["model_drafts"]), 1)
            self.assertTrue(np.all(manual == 1))
            self.assertTrue(np.all(draft == 2))
            self.assertTrue(manager.evaluate_train_ready("01-0101-11")["train_ready"])

    def test_prediction_shape_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_train_ready_project(root)
            runner = TifBackendRunner(manager, {"backend_id": "mock_volume"})
            contract = runner.build_contract("predict", ["01-0101-11"])
            runner.write_contract(contract)
            write_mock_tif_backend_result(contract, {"01-0101-11": np.zeros((1, 3, 4), dtype=np.uint16)})
            result = runner.read_result(contract["result_json"])

            with self.assertRaises(ValueError):
                runner.import_prediction_result(result)
            specimen = manager.get_specimen("01-0101-11")
            self.assertEqual(specimen["labels"]["model_drafts"], [])


if __name__ == "__main__":
    unittest.main()
