import json
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np

from AntSleap.core.tif_local_axis_ai import (
    LOCAL_AXIS_BACKEND_CONTRACT_SCHEMA_VERSION,
    LOCAL_AXIS_BACKEND_RESULT_SCHEMA_VERSION,
    LOCAL_AXIS_MODEL_MANIFEST_SCHEMA_VERSION,
    TifLocalAxisBackendRunner,
    export_local_axis_training_manifest,
    import_local_axis_proposals,
    load_global_roi_proposals,
    load_local_frame_proposals,
    normalize_frame_proposal,
    normalize_global_proposal,
    register_local_axis_model_manifest,
    validate_local_axis_backend_command,
)
from AntSleap.core.tif_local_axis_reslice import compute_local_frame, export_part_reslice
from AntSleap.core.tif_part_extraction import crop_volume_to_part
from AntSleap.core.tif_project import TifProjectManager
from AntSleap.core.tif_volume_io import write_volume_sidecar


def make_local_axis_project(root):
    project_root = root / "local_axis_project"
    manager = TifProjectManager()
    manager.create_project("local_axis_project", project_root)
    manager.create_specimen_scaffold("01-0101-ai")
    image = np.arange(5 * 6 * 7, dtype=np.uint16).reshape((5, 6, 7))
    image_rel = "specimens/01-0101-ai/working/image.ome.zarr"
    image_meta = write_volume_sidecar(project_root / image_rel, image, role="working_image")
    manager.register_working_volume("01-0101-ai", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
    manager.save_project()
    crop_volume_to_part(manager, "01-0101-ai", "head", [[1, 5], [1, 5], [1, 6]], display_name="Head")
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
    export_part_reslice(
        manager,
        "01-0101-ai",
        "head",
        {
            "reslice_id": "head_axis_001",
            "template_id": "head",
            "local_frame": frame,
            "training": {"human_confirmed": True, "usable_for_training": True},
        },
    )
    return manager


class TifLocalAxisAiTests(unittest.TestCase):
    def test_backend_command_validation_requires_contract_placeholder(self):
        self.assertTrue(validate_local_axis_backend_command(""))
        self.assertTrue(validate_local_axis_backend_command("python train.py --contract {contract}"))
        self.assertTrue(validate_local_axis_backend_command("python train.py --contract-json {contract_json}"))
        self.assertFalse(validate_local_axis_backend_command("python train.py"))

    def test_proposal_normalizers_reject_missing_required_fields(self):
        with self.assertRaisesRegex(ValueError, "bbox_zyx"):
            normalize_global_proposal({"specimen_id": "s1", "center_zyx": [1, 2, 3]})
        with self.assertRaisesRegex(ValueError, "origin"):
            normalize_frame_proposal({"specimen_id": "s1", "part_id": "head"})

    def test_import_local_axis_proposals_stores_reviewable_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = make_local_axis_project(Path(tmp))
            imported = import_local_axis_proposals(
                manager,
                global_proposals=[
                    {
                        "global_proposal_id": "roi_001",
                        "specimen_id": "01-0101-ai",
                        "template_id": "head",
                        "bbox_zyx": [1, 1, 1, 5, 5, 6],
                        "center_zyx": [3, 3, 3],
                        "status": "accepted",
                        "model_id": "external/head_roi",
                        "input_data": {"volume_role": "working_volume"},
                    }
                ],
                local_frame_proposals=[
                    {
                        "frame_proposal_id": "frame_001",
                        "specimen_id": "01-0101-ai",
                        "part_id": "head",
                        "template_id": "head",
                        "origin_zyx": [1.5, 1.5, 2.0],
                        "output_axis_start_zyx": [0.0, 1.5, 2.0],
                        "output_axis_end_zyx": [3.0, 1.5, 2.0],
                        "status": "accepted",
                        "failure_reason": "",
                    }
                ],
            )

            self.assertEqual(len(imported["global_roi_proposals"]), 1)
            self.assertEqual(len(imported["local_frame_proposals"]), 1)
            global_record = manager.list_global_axis_proposals("01-0101-ai")[0]
            frame_record = manager.list_local_frame_proposals("01-0101-ai", "head")[0]
            self.assertEqual(global_record["status"], "needs_review")
            self.assertEqual(global_record["input_data"]["volume_role"], "working_volume")
            self.assertEqual(frame_record["frame_proposal_id"], "frame_001")
            self.assertEqual(frame_record["status"], "needs_review")
            self.assertIn("roll_reference_point_pair", frame_record["missing_landmarks"])

    def test_proposal_file_loaders_reject_wrong_schema_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            global_path = root / "global.json"
            frame_path = root / "frame.json"
            global_path.write_text(json.dumps({"schema_version": "wrong_schema", "proposals": []}), encoding="utf-8")
            frame_path.write_text(json.dumps({"schema_version": "wrong_schema", "proposals": []}), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "invalid_local_axis_proposal_schema"):
                load_global_roi_proposals(global_path)
            with self.assertRaisesRegex(ValueError, "invalid_local_axis_proposal_schema"):
                load_local_frame_proposals(frame_path)

    def test_training_manifest_exports_only_confirmed_training_records_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = make_local_axis_project(Path(tmp))
            export = export_local_axis_training_manifest(manager, Path(tmp) / "dataset")

            self.assertEqual(export["sample_count"], 1)
            sample = export["manifest"]["samples"][0]
            self.assertEqual(sample["specimen_id"], "01-0101-ai")
            self.assertEqual(sample["part_id"], "head")
            self.assertEqual(sample["template_id"], "head")
            self.assertTrue(sample["training"]["human_confirmed"])
            self.assertTrue(sample["part_image"]["path"])
            self.assertEqual(sample["parent_bbox_zyx"], [[1, 5], [1, 5], [1, 6]])
            self.assertEqual(sample["schema_version"], "taxamask_tif_local_axis_training_sample_v1")
            self.assertTrue(sample["human_confirmed"])
            self.assertTrue(sample["usable_for_training"])
            self.assertEqual(sample["source_axis"]["role"], "source_direction_reference")
            self.assertEqual(sample["final_editable_axis"]["role"], "editable_output_axis")
            self.assertEqual(sample["origin_zyx"], [1.5, 1.5, 2.0])
            self.assertEqual(sample["roll_reference_point_pair"]["point_a"]["role"], "left_eye")
            self.assertEqual(sample["outputs"]["image_shape_zyx"], [4, 4, 5])
            self.assertTrue(sample["outputs"]["image_path"].endswith("image.tif"))
            self.assertTrue(sample["metadata_path"].endswith("metadata.json"))

    def test_backend_contract_contains_selected_specimen_parts_and_safety(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = make_local_axis_project(Path(tmp))
            runner = TifLocalAxisBackendRunner(manager, {"backend_id": "mock_local_axis"})
            contract = runner.build_contract("predict", ["01-0101-ai"], {"01-0101-ai": ["head"]}, template_id="head")

            self.assertEqual(contract["schema_version"], LOCAL_AXIS_BACKEND_CONTRACT_SCHEMA_VERSION)
            self.assertTrue(contract["safety"]["output_is_reviewable_proposal"])
            self.assertTrue(contract["safety"]["do_not_write_project_json"])
            self.assertTrue(contract["safety"]["do_not_create_final_reslice"])
            self.assertEqual(contract["specimens"][0]["parts"][0]["part_id"], "head")
            self.assertTrue(contract["specimens"][0]["parts"][0]["part_image"]["path"].endswith("image.ome.zarr"))
            self.assertEqual(contract["specimens"][0]["parts"][0]["source_axis"]["role"], "source_direction_reference")

    def test_train_contract_prepares_training_manifest_like_prepare_dataset(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = make_local_axis_project(Path(tmp))
            runner = TifLocalAxisBackendRunner(manager, {"backend_id": "mock_local_axis"}, runs_root=Path(tmp) / "runs")
            run_id, run_dir = runner.create_run_dir("train")
            contract = runner.build_contract("train", ["01-0101-ai"], {"01-0101-ai": ["head"]}, template_id="head", run_id=run_id, run_dir=run_dir)
            export = export_local_axis_training_manifest(manager, contract["dataset_dir"], {"template_id": "head"})

            self.assertEqual(export["sample_count"], 1)
            self.assertTrue(export["manifest_path"].endswith("local_axis_training_manifest.json"))

    def test_backend_runner_imports_result_artifacts_as_project_proposals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_local_axis_project(root)
            helper = root / "mock_local_axis_backend.py"
            helper.write_text(
                "\n".join(
                    [
                        "import json, os",
                        "contract=json.load(open('contract.json', encoding='utf-8'))",
                        "out=contract['output_dir']",
                        "os.makedirs(out, exist_ok=True)",
                        "global_path=os.path.join(out, 'global_roi_proposals.json')",
                        "frame_path=os.path.join(out, 'local_frame_proposals.json')",
                        "json.dump({'schema_version':'taxamask_tif_local_axis_global_roi_proposals_v1','proposals':[{'global_proposal_id':'roi_from_backend','specimen_id':'01-0101-ai','template_id':'head','bbox_zyx':[1,1,1,5,5,6],'center_zyx':[3,3,3]}]}, open(global_path, 'w', encoding='utf-8'))",
                        "json.dump({'schema_version':'taxamask_tif_local_axis_frame_proposals_v1','proposals':[{'frame_proposal_id':'frame_from_backend','specimen_id':'01-0101-ai','part_id':'head','template_id':'head','origin_zyx':[1.5,1.5,2.0],'output_axis_start_zyx':[0,1.5,2.0],'output_axis_end_zyx':[3,1.5,2.0]}]}, open(frame_path, 'w', encoding='utf-8'))",
                        "result={'schema_version':'taxamask_tif_local_axis_backend_result_v1','contract_schema_version':'taxamask_tif_local_axis_backend_contract_v1','status':'success','action':contract['action'],'backend_id':contract['backend_id'],'run_id':contract['run_id'],'artifacts':[{'type':'global_roi_proposals','path':os.path.relpath(global_path, os.path.dirname(contract['result_json'])),'format':'json'},{'type':'local_frame_proposals','path':os.path.relpath(frame_path, os.path.dirname(contract['result_json'])),'format':'json'}],'metrics':{},'warnings':[],'errors':[],'provenance':{}}",
                        "json.dump(result, open(contract['result_json'], 'w', encoding='utf-8'))",
                    ]
                ),
                encoding="utf-8",
            )
            runner = TifLocalAxisBackendRunner(
                manager,
                {
                    "backend_id": "mock_local_axis",
                    "predict_command": f"{os.sys.executable} {helper}",
                },
                runs_root=root / "runs",
            )

            result = runner.run_action("predict", ["01-0101-ai"], {"01-0101-ai": ["head"]}, template_id="head")

            self.assertEqual(result["result"]["schema_version"], LOCAL_AXIS_BACKEND_RESULT_SCHEMA_VERSION)
            self.assertEqual(manager.list_global_axis_proposals("01-0101-ai")[0]["global_proposal_id"], "roi_from_backend")
            self.assertEqual(manager.list_local_frame_proposals("01-0101-ai", "head")[0]["frame_proposal_id"], "frame_from_backend")
            self.assertEqual(manager.list_local_frame_proposals("01-0101-ai", "head")[0]["status"], "needs_review")
            self.assertEqual(manager.project_data["runs"][-1]["action"], "predict")

    def test_backend_result_top_level_model_metadata_flows_to_proposals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_local_axis_project(root)
            frame_path = root / "local_frame_proposals.json"
            frame_path.write_text(
                json.dumps(
                    {
                        "schema_version": "taxamask_tif_local_axis_frame_proposals_v1",
                        "template_id": "head",
                        "model_id": "external/frame",
                        "model_version": "v2",
                        "proposals": [
                            {
                                "frame_proposal_id": "frame_with_defaults",
                                "specimen_id": "01-0101-ai",
                                "part_id": "head",
                                "origin_zyx": [1.5, 1.5, 2.0],
                                "output_axis_start_zyx": [0.0, 1.5, 2.0],
                                "output_axis_end_zyx": [3.0, 1.5, 2.0],
                                "roll_reference": {
                                    "point_a": {"role": "left_eye", "zyx": [1.5, 1.0, 1.0]},
                                    "point_b": {"role": "right_eye", "zyx": [1.5, 3.0, 1.0]},
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            proposals = load_local_frame_proposals(frame_path)

            self.assertEqual(proposals[0]["template_id"], "head")
            self.assertEqual(proposals[0]["model_id"], "external/frame")
            self.assertEqual(proposals[0]["model_version"], "v2")
            self.assertEqual(proposals[0]["status"], "proposed")

    def test_register_model_manifest_stores_local_axis_model_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_local_axis_project(root)
            manifest_path = root / "model_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": LOCAL_AXIS_MODEL_MANIFEST_SCHEMA_VERSION,
                        "model_id": "external_local_axis/head_frame_v1",
                        "model_version": "v1",
                        "backend_id": "external_local_axis",
                        "template_id": "head",
                        "model_type": "local_frame",
                        "trained_from": {"training_manifest": str(root / "local_axis_training_manifest.json")},
                        "input_contract": {"input_space": "part_volume_voxel_zyx"},
                        "output_contract": {"artifact_type": "local_frame_proposals"},
                    }
                ),
                encoding="utf-8",
            )

            record = register_local_axis_model_manifest(manager, manifest_path)

            self.assertEqual(record["model_id"], "external_local_axis/head_frame_v1")
            self.assertEqual(record["profile_scope"], "tif_local_axis")
            self.assertEqual(record["template_id"], "head")
            self.assertEqual(manager.list_local_axis_models()[0]["model_version"], "v1")


if __name__ == "__main__":
    unittest.main()
