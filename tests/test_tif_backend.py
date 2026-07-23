import copy
import json
import os
import shutil
import tempfile
import types
import unittest
from pathlib import Path

import numpy as np
import tifffile

from AntSleap.core.tif_backend import (
    TIF_BACKEND_CONTRACT_SCHEMA_VERSION,
    TIF_NNUNET_V2_REQUIRED_COMMANDS,
    TifBackendRunner,
    _validate_training_split_receipt,
    normalize_tif_backend_runtime_config,
    write_mock_tif_backend_result,
)
from AntSleap.core.tif_local_axis_reslice import compute_local_frame, export_part_reslice
from AntSleap.core.tif_project import TifProjectManager
from AntSleap.core.tif_volume_io import load_volume_sidecar, write_volume_sidecar
from AntSleap.core.training_run_recorder import TrainingRunRecorder
from AntSleap.tools.tif_nnunet_v2_backend import _resolved_effective_config


TRAIN_PART_REFS = [
    {"specimen_id": specimen_id, "part_id": "brain", "reslice_id": "brain_axis_001"}
    for specimen_id in ("01-0101-11", "01-0101-12")
]


def _replace_specimen_id(value, old_id, new_id):
    if isinstance(value, dict):
        return {key: _replace_specimen_id(item, old_id, new_id) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_specimen_id(item, old_id, new_id) for item in value]
    if isinstance(value, str):
        return value.replace(old_id, new_id)
    return copy.deepcopy(value)


def _clone_specimen(manager, old_id, new_id):
    source_dir = Path(manager.to_absolute(manager.specimen_dir(old_id)))
    target_dir = Path(manager.to_absolute(manager.specimen_dir(new_id)))
    shutil.copytree(source_dir, target_dir)
    original = manager.get_specimen(old_id)
    cloned = _replace_specimen_id(original, old_id, new_id)
    cloned["specimen_id"] = new_id
    manager.project_data.setdefault("specimens", []).append(cloned)


def _run_artifact_path(run_result, value):
    path = Path(value)
    return path if path.is_absolute() else Path(run_result["run_dir"]) / path


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
    part_dir = manager.part_dir("01-0101-11", "brain")
    part_image_rel = f"{part_dir}/image.ome.zarr"
    part_mask_rel = f"{part_dir}/mask.ome.zarr"
    write_volume_sidecar(root / "backend" / part_image_rel, np.zeros((2, 3, 4), dtype=np.uint8), role="part_image")
    write_volume_sidecar(root / "backend" / part_mask_rel, np.zeros((2, 3, 4), dtype=np.uint16), role="part_mask")
    manager.add_part(
        "01-0101-11",
        "brain",
        display_name="Brain",
        image={"path": part_image_rel, "format": "ant3d_volume_sidecar", "shape_zyx": [2, 3, 4], "dtype": "uint8"},
        mask={"path": part_mask_rel, "format": "ant3d_volume_sidecar", "shape_zyx": [2, 3, 4], "dtype": "uint16"},
        save=False,
    )
    roll_reference = {
        "point_a": {"role": "left_reference", "zyx": [0.5, 0.5, 1.0]},
        "point_b": {"role": "right_reference", "zyx": [0.5, 2.5, 1.0]},
        "point_c": {"role": "plane_reference", "zyx": [1.0, 0.5, 3.0]},
    }
    frame = compute_local_frame([0.5, 1.5, 2.0], [0.0, 1.5, 2.0], [1.0, 1.5, 2.0], roll_reference=roll_reference)
    export_part_reslice(
        manager,
        "01-0101-11",
        "brain",
        {"reslice_id": "brain_axis_001", "template_id": "brain", "local_frame": frame, "roll_reference": roll_reference},
    )
    reslice = manager.get_part_reslice("01-0101-11", "brain", "brain_axis_001")
    reslice_shape = list(tifffile.imread(manager.to_absolute(reslice["image_path"])).shape)
    manager.add_or_update_label_schema(
        "brain_regions",
        labels=[{"id": 1, "name": "mushroom_body", "color": "#ff0000"}, {"id": 2, "name": "antennal_lobe", "color": "#00ff00"}],
        user_defined_part_name="brain",
        save=False,
    )
    part_manual_rel = f"{part_dir}/reslices/brain_axis_001/labels/manual_truth.ome.zarr"
    part_manual_meta = write_volume_sidecar(root / "backend" / part_manual_rel, np.ones(tuple(reslice_shape), dtype=np.uint16), role="manual_truth")
    manager.register_part_reslice_label_volume(
        "01-0101-11",
        "brain",
        "brain_axis_001",
        "manual_truth",
        part_manual_rel,
        part_manual_meta["shape_zyx"],
        part_manual_meta["dtype"],
        status="reviewed",
        save=False,
    )
    manager.set_part_training_metadata(
        "01-0101-11",
        "brain",
        user_defined_part_name="brain",
        label_schema_id="brain_regions",
        active_reslice_id="brain_axis_001",
        system_status="verified_train_ready",
        save=True,
    )
    _clone_specimen(manager, "01-0101-11", "01-0101-12")
    manager.save_project()
    manager.initialize_integrity_baseline(
        legacy_truth_attestation=True,
        note="Test fixture truth is explicitly reviewed.",
    )
    return manager


def make_predict_ready_project(root):
    manager = make_train_ready_project(root)
    part = manager.get_part("01-0101-11", "brain")
    reslice = manager.get_part_reslice("01-0101-11", "brain", "brain_axis_001")
    labels = reslice.setdefault("labels", {})
    labels["manual_truth"] = {
        "path": "",
        "format": "",
        "shape_zyx": [],
        "dtype": "",
        "spacing_zyx": [1.0, 1.0, 1.0],
        "spacing_unit": "micrometer",
        "orientation": "unknown",
    }
    part["status"] = "ready_for_labeling"
    training = part.setdefault("training", {})
    training["system_status"] = "cut_pending_labeling"
    training["opened_for_review"] = False
    manager.save_project()
    return manager


def make_top_level_only_project(root):
    manager = TifProjectManager()
    manager.create_project("top_level_backend", root / "top_level_backend")
    manager.create_specimen_scaffold(
        "top-001",
        modality="micro_ct",
        material_map={
            "materials": [
                {"id": 0, "name": "background", "display_name": "Background", "trainable": False},
                {"id": 1, "name": "region_1", "display_name": "Region 1", "trainable": True},
            ]
        },
    )
    image_rel = "specimens/top-001/working/image.ome.zarr"
    manual_rel = "specimens/top-001/labels/manual_truth.ome.zarr"
    image_meta = write_volume_sidecar(root / "top_level_backend" / image_rel, np.zeros((2, 3, 4), dtype=np.uint8), role="working_image")
    manual_meta = write_volume_sidecar(root / "top_level_backend" / manual_rel, np.ones((2, 3, 4), dtype=np.uint16), role="manual_truth")
    manager.register_working_volume("top-001", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
    manager.register_label_volume("top-001", "manual_truth", manual_rel, manual_meta["shape_zyx"], manual_meta["dtype"], save=False)
    manager.set_review_status("top-001", "train_ready", train_ready=True)
    _clone_specimen(manager, "top-001", "top-002")
    manager.save_project()
    manager.initialize_integrity_baseline(
        legacy_truth_attestation=True,
        note="Test fixture truth is explicitly reviewed.",
    )
    return manager


class TifBackendTests(unittest.TestCase):
    def test_nnunet_runtime_config_autodetects_backend_python(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env_root = root / "envs" / "3d-brain"
            scripts = env_root / "Scripts"
            scripts.mkdir(parents=True)
            python = env_root / "python.exe"
            python.write_text("", encoding="utf-8")
            for command in TIF_NNUNET_V2_REQUIRED_COMMANDS:
                (scripts / f"{command}.exe").write_text("", encoding="utf-8")

            config = normalize_tif_backend_runtime_config(
                {
                    "backend_id": "taxamask_tif_nnunet_v2_backend",
                    "python_executable": "python",
                    "train_command": "{python} -m AntSleap.tools.tif_nnunet_v2_backend --contract {contract_json}",
                },
                action="train",
                env={"PATH": ""},
                extra_roots=[root / "envs"],
            )

            self.assertEqual(Path(config["python_executable"]), python.resolve())

    def test_contract_uses_manual_truth_for_prepare_dataset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_train_ready_project(root)
            runner = TifBackendRunner(manager, {"backend_id": "mock_volume"})
            contract = runner.build_contract("prepare_dataset", ["01-0101-11"])

            self.assertEqual(contract["schema_version"], TIF_BACKEND_CONTRACT_SCHEMA_VERSION)
            self.assertTrue(contract["safety"]["protect_manual_truth"])
            self.assertFalse(contract["safety"]["allow_model_draft_as_training_label"])
            self.assertEqual(contract["input_scope"], "part_reslice")
            self.assertEqual(contract["part_samples"][0]["label_volume"]["role"], "manual_truth")
            self.assertEqual(contract["part_samples"][0]["part_id"], "brain")
            self.assertTrue(contract["part_samples"][0]["input_volume"]["path"].endswith("image.tif"))
            self.assertEqual(contract["part_samples"][0]["label_schema_id"], "brain_regions")
            self.assertEqual(contract["part_samples"][0]["label_schema"]["labels"][0]["name"], "mushroom_body")

    def test_contract_rejects_empty_part_sample_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_train_ready_project(root)
            runner = TifBackendRunner(manager, {"backend_id": "mock_volume"})

            with self.assertRaisesRegex(ValueError, "no_tif_part_samples:prepare_dataset"):
                runner.build_contract("prepare_dataset", part_refs=[])

    def test_contract_can_use_top_level_volume_when_no_project_parts_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_top_level_only_project(root)
            runner = TifBackendRunner(manager, {"backend_id": "mock_volume"})

            contract = runner.build_contract("prepare_dataset", input_scope="top_level_volume")

            self.assertEqual(contract["input_scope"], "top_level_volume")
            self.assertEqual(contract["part_samples"], [])
            self.assertEqual(contract["specimens"][0]["specimen_id"], "top-001")
            self.assertEqual(contract["specimens"][0]["label_volume"]["role"], "manual_truth")
            self.assertTrue(contract["specimens"][0]["input_volume"]["path"].endswith("image.ome.zarr"))

    def test_predict_contract_accepts_objectively_ready_part_without_manual_truth(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_predict_ready_project(root)
            readiness = manager.evaluate_part_predict_ready("01-0101-11", "brain", "brain_axis_001")
            train_readiness = manager.evaluate_part_train_ready("01-0101-11", "brain", "brain_axis_001")
            runner = TifBackendRunner(manager, {"backend_id": "mock_volume"})

            contract = runner.build_contract(
                "predict",
                part_refs=[{"specimen_id": "01-0101-11", "part_id": "brain", "reslice_id": "brain_axis_001"}],
            )

            self.assertTrue(readiness["predict_ready"])
            self.assertEqual(readiness["reasons"], [])
            self.assertFalse(train_readiness["train_ready"])
            self.assertIn("manual_truth_missing", train_readiness["reasons"])
            self.assertNotIn("part_label_shape_mismatch", train_readiness["reasons"])
            self.assertIn("part_not_marked_train_ready", train_readiness["reasons"])
            self.assertEqual(contract["part_samples"][0]["label_volume"]["role"], "none")
            self.assertEqual(contract["part_samples"][0]["label_volume"]["path"], "")
            self.assertEqual(contract["part_samples"][0]["input_volume"]["shape_zyx"], readiness["input_shape_zyx"])

    def test_predict_contract_rejects_missing_objective_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_predict_ready_project(root)
            manager.project_data["label_schemas"] = []
            runner = TifBackendRunner(manager, {"backend_id": "mock_volume"})

            with self.assertRaisesRegex(ValueError, "part_not_predict_ready:01-0101-11:brain:label_schema_missing"):
                runner.build_contract(
                    "predict",
                    part_refs=TRAIN_PART_REFS,
                )

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
            self.assertEqual(manifest["samples"][0]["part_id"], "brain")

    def test_train_run_emits_progress_and_can_cancel_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_train_ready_project(root)
            helper = root / "slow_train.py"
            helper.write_text(
                "\n".join(
                    [
                        "import json, time",
                        "payload=json.load(open('contract.json', encoding='utf-8'))",
                        "print('slow train started', flush=True)",
                        "time.sleep(5)",
                        "json.dump({",
                        "  'schema_version':'ant3d_tif_backend_result_v1',",
                        "  'contract_schema_version':'ant3d_tif_backend_contract_v1',",
                        "  'status':'success',",
                        "  'action':'train',",
                        "  'backend_id':payload['backend_id'],",
                        "  'run_id':payload['run_id'],",
                        "  'artifacts':[],",
                        "  'metrics':{},",
                        "  'warnings':[],",
                        "  'errors':[],",
                        "  'provenance':{},",
                        "}, open(payload['result_json'], 'w', encoding='utf-8'))",
                    ]
                ),
                encoding="utf-8",
            )
            runner = TifBackendRunner(
                manager,
                {"backend_id": "mock_slow_backend", "train_command": f"{os.sys.executable} {helper}"},
                runs_root=root / "runs",
            )
            progress = []

            def on_progress(current, total, message):
                progress.append((current, total, message))

            def cancel_check():
                return any("slow train started" in item[2] for item in progress)

            with self.assertRaisesRegex(RuntimeError, "tif_backend_train_cancelled"):
                runner.run_action("train", part_refs=TRAIN_PART_REFS, progress_callback=on_progress, cancel_check=cancel_check)
            self.assertTrue(any("Running train command" in item[2] for item in progress))
            records = TrainingRunRecorder(
                root / "runs",
                database_path=manager.current_database_path,
                recover_on_startup=False,
            ).list_records()
            self.assertEqual(records[-1]["status"], "cancelled")

    def test_backend_command_can_import_antsleap_from_run_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_train_ready_project(root)
            helper = root / "import_antsleap_prepare.py"
            helper.write_text(
                "\n".join(
                    [
                        "import json",
                        "import AntSleap",
                        "payload=json.load(open('contract.json', encoding='utf-8'))",
                        "json.dump({",
                        "  'schema_version':'ant3d_tif_backend_result_v1',",
                        "  'contract_schema_version':'ant3d_tif_backend_contract_v1',",
                        "  'status':'success',",
                        "  'action':'prepare_dataset',",
                        "  'backend_id':payload['backend_id'],",
                        "  'run_id':payload['run_id'],",
                        "  'artifacts':[],",
                        "  'metrics':{},",
                        "  'warnings':[],",
                        "  'errors':[],",
                        "  'provenance':{},",
                        "}, open(payload['result_json'], 'w', encoding='utf-8'))",
                    ]
                ),
                encoding="utf-8",
            )
            runner = TifBackendRunner(
                manager,
                {
                    "backend_id": "mock_import_backend",
                    "prepare_dataset_command": f"{os.sys.executable} {helper}",
                },
                runs_root=root / "runs",
            )

            result = runner.run_action("prepare_dataset", part_refs=[{"specimen_id": "01-0101-11", "part_id": "brain", "reslice_id": "brain_axis_001"}])

            self.assertEqual(result["result"]["status"], "success")

    def test_backend_command_failure_includes_log_tail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_train_ready_project(root)
            helper = root / "fail_train.py"
            helper.write_text(
                "\n".join(
                    [
                        "import sys",
                        "print('clear backend failure detail', file=sys.stderr, flush=True)",
                        "raise SystemExit(2)",
                    ]
                ),
                encoding="utf-8",
            )
            runner = TifBackendRunner(
                manager,
                {"backend_id": "mock_fail_backend", "train_command": f"{os.sys.executable} {helper}"},
                runs_root=root / "runs",
            )

            with self.assertRaisesRegex(RuntimeError, "clear backend failure detail"):
                runner.run_action(
                    "train",
                    part_refs=TRAIN_PART_REFS,
                )
            records = TrainingRunRecorder(
                root / "runs",
                database_path=manager.current_database_path,
                recover_on_startup=False,
            ).list_records()
            self.assertEqual(records[-1]["status"], "failed")

    def test_nnunet_v2_dry_run_uses_verified_split_and_records_sqlite_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_train_ready_project(root)
            command = (
                f"{os.sys.executable} -m AntSleap.tools.tif_nnunet_v2_backend "
                "--contract {contract_json} --dry-run-commands --overwrite-dataset"
            )
            runner = TifBackendRunner(
                manager,
                {
                    "backend_id": "taxamask_tif_nnunet_v2_backend",
                    "train_command": command,
                },
                runs_root=root / "runs",
            )

            result = runner.run_action("train", part_refs=TRAIN_PART_REFS)

            config = result["result"]["effective_config"]
            self.assertEqual(config["execution_kind"], "backend_dry_run")
            self.assertFalse(config["persist_weights"])
            self.assertEqual(config["preprocessing"]["split_source"], "taxamask_verified_training_split")
            split_path = _run_artifact_path(result, result["result"]["provenance"]["dataset_dir"]) / "splits_final.json"
            with open(split_path, "r", encoding="utf-8") as handle:
                actual_split = json.load(handle)[0]
            self.assertEqual(actual_split, config["preprocessing"]["split"])
            self.assertEqual(len(actual_split["train"]), 1)
            self.assertEqual(len(actual_split["val"]), 1)
            records = TrainingRunRecorder(
                root / "runs",
                database_path=manager.current_database_path,
                recover_on_startup=False,
            ).list_records()
            record = next(item for item in records if item["run_id"] == result["run_id"])
            self.assertEqual(record["status"], "succeeded")
            self.assertFalse(record["effective_config"]["persist_weights"])
            self.assertFalse(any(item["role"] == "output_weights" for item in record["artifacts"]))

    def test_nnunet_checkpoint_resolves_actual_effective_config_and_fails_closed(self):
        import torch

        with tempfile.TemporaryDirectory() as tmp:
            checkpoint_path = Path(tmp) / "checkpoint_final.pth"
            checkpoint = {
                "current_epoch": 5,
                "trainer_name": "nnUNetTrainer",
                "init_args": {
                    "plans": {
                        "configurations": {
                            "3d_fullres": {
                                "batch_size": 2,
                                "patch_size": [32, 48, 64],
                            }
                        }
                    }
                },
                "optimizer_state": {
                    "param_groups": [
                        {
                            "initial_lr": 0.01,
                            "lr": 0.001,
                            "weight_decay": 0.00001,
                        }
                    ]
                },
                "logging": {"lrs": [0.01, 0.005]},
            }
            torch.save(checkpoint, checkpoint_path)
            contract = {
                "training_split": {
                    "strategy": {"seed": 20260720},
                }
            }
            args = types.SimpleNamespace(
                configuration="3d_fullres",
                plans="nnUNetPlans",
                trainer="nnUNetTrainer",
                verify_dataset_integrity=True,
                continue_training=False,
                checkpoint="checkpoint_final.pth",
            )
            split = {"train": ["case_a"], "val": ["case_b"]}

            config = _resolved_effective_config(
                contract, args, checkpoint_path, split
            )

            self.assertEqual(config["epochs"], 5)
            self.assertEqual(config["batch_size"], 2)
            self.assertEqual(config["input_resolution"], [32, 48, 64])
            self.assertEqual(config["learning_rate"], 0.01)
            self.assertEqual(config["weight_decay"], 0.00001)
            self.assertTrue(config["persist_weights"])
            del checkpoint["optimizer_state"]["param_groups"][0]["weight_decay"]
            torch.save(checkpoint, checkpoint_path)
            with self.assertRaisesRegex(ValueError, "weight_decay_missing"):
                _resolved_effective_config(contract, args, checkpoint_path, split)

    def test_external_training_split_receipt_is_required_and_must_match(self):
        assignments = [
            {"sample_id": "a", "partition": "train", "group_id": "a", "input_file_ids": ["a_image", "a_truth"]},
            {"sample_id": "b", "partition": "validation", "group_id": "b", "input_file_ids": ["b_image", "b_truth"]},
        ]
        contract = {"training_split": {"assignments": assignments}}
        config = {"persist_weights": True}
        with self.assertRaisesRegex(ValueError, "receipt_missing"):
            _validate_training_split_receipt(contract, {}, config)
        with self.assertRaisesRegex(ValueError, "receipt_mismatch"):
            _validate_training_split_receipt(
                contract,
                {"training_split": {"status": "applied", "assignments": assignments[:1]}},
                config,
            )
        _validate_training_split_receipt(
            contract,
            {"training_split": {"status": "applied", "assignments": list(reversed(assignments))}},
            config,
        )

    def test_nnunet_v2_backend_prepare_dataset_runs_from_run_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_train_ready_project(root)
            command = (
                f"{os.sys.executable} -m AntSleap.tools.tif_nnunet_v2_backend "
                "--contract {contract_json} --dataset-id 799 --dataset-name SmokeTaxaMask "
                "--file-ending .nii --overwrite-dataset"
            )
            runner = TifBackendRunner(
                manager,
                {
                    "backend_id": "taxamask_tif_nnunet_v2_backend",
                    "prepare_dataset_command": command,
                    "export_formats": "nifti",
                },
                runs_root=root / "runs",
            )

            result = runner.run_action("prepare_dataset", part_refs=[{"specimen_id": "01-0101-11", "part_id": "brain", "reslice_id": "brain_axis_001"}])

            self.assertEqual(result["result"]["status"], "success")
            dataset_dir = _run_artifact_path(result, result["result"]["provenance"]["dataset_dir"])
            self.assertTrue((dataset_dir / "dataset.json").exists())
            self.assertTrue((dataset_dir / "imagesTr").exists())
            self.assertTrue((dataset_dir / "labelsTr").exists())
            self.assertTrue(any(item["type"] == "nnunet_dataset_dir" for item in result["result"]["artifacts"]))

    def test_part_predict_result_imports_editable_ai_result_without_touching_manual_truth(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_train_ready_project(root)
            runner = TifBackendRunner(manager, {"backend_id": "mock_volume"})
            contract = runner.build_contract("predict", part_refs=[{"specimen_id": "01-0101-11", "part_id": "brain", "reslice_id": "brain_axis_001"}])
            runner.write_contract(contract)
            shape = tuple(contract["part_samples"][0]["input_volume"]["shape_zyx"])
            prediction = np.full(shape, 2, dtype=np.uint16)
            result = write_mock_tif_backend_result(contract, {"01-0101-11:brain": prediction})
            result = runner.read_result(contract["result_json"])
            imported = runner.import_prediction_result(result)

            specimen = manager.get_specimen("01-0101-11")
            manual = load_volume_sidecar(manager.to_absolute(specimen["labels"]["manual_truth"]["path"]))
            part = manager.get_part("01-0101-11", "brain")
            reslice = manager.get_part_reslice("01-0101-11", "brain", "brain_axis_001")
            editable = load_volume_sidecar(manager.to_absolute(reslice["labels"]["editable_ai_result"]["path"]))

            self.assertEqual(len(imported), 1)
            self.assertEqual(part["training"]["system_status"], "predicted_pending_review")
            self.assertFalse((part["labels"]["editable_ai_result"] or {}).get("path"))
            self.assertTrue(np.all(manual == 1))
            self.assertTrue(np.all(editable == 2))
            self.assertTrue(manager.evaluate_train_ready("01-0101-11")["train_ready"])

    def test_top_level_predict_result_imports_current_labels_without_touching_training_truth(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_top_level_only_project(root)
            runner = TifBackendRunner(manager, {"backend_id": "mock_volume"})
            contract = runner.build_contract("predict", specimen_ids=["top-001"], input_scope="top_level_volume")
            runner.write_contract(contract)
            prediction = np.full(tuple(contract["specimens"][0]["input_volume"]["shape_zyx"]), 1, dtype=np.uint16)
            write_mock_tif_backend_result(contract, {"top-001": prediction})
            result = runner.read_result(contract["result_json"])
            imported = runner.import_prediction_result(result)

            specimen = manager.get_specimen("top-001")
            labels = specimen["labels"]
            manual = load_volume_sidecar(manager.to_absolute(labels["manual_truth"]["path"]))
            working = load_volume_sidecar(manager.to_absolute(labels["working_edit"]["path"]))
            backup = load_volume_sidecar(manager.to_absolute(labels["raw_ai_prediction_backup"]["path"]))

            self.assertEqual(len(imported), 1)
            self.assertEqual(specimen["review_status"], "pending_review")
            self.assertFalse(manager.evaluate_train_ready("top-001")["train_ready"])
            self.assertEqual(labels["working_edit"]["status"], "pending_review")
            self.assertEqual(labels["raw_ai_prediction_backup"]["status"], "raw_backup")
            self.assertEqual(len(labels["model_drafts"]), 1)
            np.testing.assert_array_equal(working, prediction)
            np.testing.assert_array_equal(backup, prediction)
            self.assertTrue(np.all(manual == 1))

    def test_backend_prediction_artifact_cannot_import_as_manual_truth(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_top_level_only_project(root)
            runner = TifBackendRunner(manager, {"backend_id": "mock_volume"})
            contract = runner.build_contract("predict", specimen_ids=["top-001"], input_scope="top_level_volume")
            runner.write_contract(contract)
            prediction_dir = Path(contract["run_dir"]) / "manual_truth_prediction.ome.zarr"
            write_volume_sidecar(prediction_dir, np.full((2, 3, 4), 7, dtype=np.uint16), role="manual_truth")
            result_payload = {
                "schema_version": "ant3d_tif_backend_result_v1",
                "contract_schema_version": TIF_BACKEND_CONTRACT_SCHEMA_VERSION,
                "run_id": contract["run_id"],
                "status": "success",
                "artifacts": [
                    {
                        "type": "prediction_label_volume",
                        "role": "manual_truth",
                        "specimen_id": "top-001",
                        "path": str(prediction_dir),
                        "prediction_id": "bad_manual_truth",
                    }
                ],
                "metrics": {},
                "warnings": [],
                "provenance": {"run_dir": contract["run_dir"]},
            }
            with open(contract["result_json"], "w", encoding="utf-8") as handle:
                json.dump(result_payload, handle)
            result = runner.read_result(contract["result_json"])
            before = load_volume_sidecar(manager.to_absolute(manager.get_specimen("top-001")["labels"]["manual_truth"]["path"])).copy()

            imported = runner.import_prediction_result(result)

            self.assertEqual(imported, [])
            np.testing.assert_array_equal(
                load_volume_sidecar(manager.to_absolute(manager.get_specimen("top-001")["labels"]["manual_truth"]["path"])),
                before,
            )
            labels = manager.get_specimen("top-001")["labels"]
            self.assertFalse((labels.get("raw_ai_prediction_backup") or {}).get("path"))

    def test_prediction_shape_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_train_ready_project(root)
            runner = TifBackendRunner(manager, {"backend_id": "mock_volume"})
            contract = runner.build_contract("predict", part_refs=[{"specimen_id": "01-0101-11", "part_id": "brain", "reslice_id": "brain_axis_001"}])
            runner.write_contract(contract)
            write_mock_tif_backend_result(contract, {"01-0101-11:brain": np.zeros((1, 3, 4), dtype=np.uint16)})
            result = runner.read_result(contract["result_json"])

            with self.assertRaises(ValueError):
                runner.import_prediction_result(result)
            part = manager.get_part("01-0101-11", "brain")
            reslice = manager.get_part_reslice("01-0101-11", "brain", "brain_axis_001")
            self.assertFalse(part["labels"]["editable_ai_result"]["path"])
            self.assertFalse(reslice["labels"]["editable_ai_result"]["path"])

    def test_tif_trainer_adapter_prepare_dataset_writes_part_nnunet_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_train_ready_project(root)
            helper = root / "run_tif_trainer_backend.py"
            repo_root = Path(__file__).resolve().parents[1]
            helper.write_text(
                "\n".join(
                    [
                        "import sys",
                        f"sys.path.insert(0, {str(repo_root)!r})",
                        "from AntSleap.tools.tif_trainer_backend import main",
                        "raise SystemExit(main())",
                    ]
                ),
                encoding="utf-8",
            )
            runner = TifBackendRunner(
                manager,
                {
                    "backend_id": "taxamask_tif_trainer_backend",
                    "prepare_dataset_command": f"{os.sys.executable} {helper} --contract {{contract_json}}",
                },
                runs_root=root / "runs",
            )

            result = runner.run_action("prepare_dataset", part_refs=[{"specimen_id": "01-0101-11", "part_id": "brain", "reslice_id": "brain_axis_001"}])

            dataset_dir = Path(result["contract"]["dataset_dir"])
            self.assertTrue((dataset_dir / "imagesTr").exists())
            self.assertTrue((dataset_dir / "labelsTr").exists())
            self.assertTrue((dataset_dir / "dataset.json").exists())
            with open(dataset_dir / "dataset.json", "r", encoding="utf-8") as handle:
                dataset_json = json.load(handle)
            self.assertEqual(dataset_json["labels"]["background"], 0)
            self.assertEqual(dataset_json["labels"]["mushroom_body"], 1)
            self.assertEqual(dataset_json["labels"]["antennal_lobe"], 2)
            manifest_path = _run_artifact_path(result, result["result"]["provenance"]["dataset_manifest"])
            self.assertTrue(manifest_path.exists())
            self.assertTrue(any(item["type"] == "nnunet_dataset_dir" for item in result["result"]["artifacts"]))

    def test_tif_trainer_adapter_train_writes_model_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_train_ready_project(root)
            helper = root / "run_tif_trainer_backend.py"
            repo_root = Path(__file__).resolve().parents[1]
            helper.write_text(
                "\n".join(
                    [
                        "import sys",
                        f"sys.path.insert(0, {str(repo_root)!r})",
                        "from AntSleap.tools.tif_trainer_backend import main",
                        "raise SystemExit(main())",
                    ]
                ),
                encoding="utf-8",
            )
            runner = TifBackendRunner(
                manager,
                {
                    "backend_id": "taxamask_tif_trainer_backend",
                    "train_command": f"{os.sys.executable} {helper} --contract {{contract_json}}",
                },
                runs_root=root / "runs",
            )

            result = runner.run_action("train", part_refs=TRAIN_PART_REFS)

            manifest_path = _run_artifact_path(result, result["result"]["provenance"]["model_manifest"])
            self.assertTrue(manifest_path.exists())
            with open(manifest_path, "r", encoding="utf-8") as handle:
                manifest = json.load(handle)
            self.assertEqual(manifest["schema_version"], "ant3d_tif_model_manifest_v1")
            self.assertEqual(manifest["input_scope"], "part_reslice")
            self.assertEqual(manifest["label_role"], "manual_truth")
            self.assertEqual(manifest["training_mode"], "smoke_adapter")
            self.assertFalse(manifest["usable_for_research_prediction"])
            self.assertTrue(
                any(
                    manager.to_absolute(model.get("model_manifest", "")) == str(manifest_path)
                    for model in manager.project_data.get("models", [])
                )
            )

    def test_tif_trainer_adapter_predict_imports_editable_ai_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_predict_ready_project(root)
            model_manifest = root / "model_manifest.json"
            model_manifest.write_text('{"schema_version":"ant3d_tif_model_manifest_v1"}', encoding="utf-8")
            helper = root / "run_tif_trainer_backend.py"
            repo_root = Path(__file__).resolve().parents[1]
            helper.write_text(
                "\n".join(
                    [
                        "import sys",
                        f"sys.path.insert(0, {str(repo_root)!r})",
                        "from AntSleap.tools.tif_trainer_backend import main",
                        "raise SystemExit(main())",
                    ]
                ),
                encoding="utf-8",
            )
            runner = TifBackendRunner(
                manager,
                {
                    "backend_id": "taxamask_tif_trainer_backend",
                    "predict_command": f"{os.sys.executable} {helper} --contract {{contract_json}}",
                    "model_manifest": str(model_manifest),
                },
                runs_root=root / "runs",
            )

            result = runner.run_action("predict", part_refs=[{"specimen_id": "01-0101-11", "part_id": "brain", "reslice_id": "brain_axis_001"}])

            self.assertEqual(len(result["imported"]), 1)
            part = manager.get_part("01-0101-11", "brain")
            reslice = manager.get_part_reslice("01-0101-11", "brain", "brain_axis_001")
            self.assertEqual(part["training"]["system_status"], "predicted_pending_review")
            self.assertEqual(reslice["labels"]["manual_truth"]["path"], "")
            self.assertFalse((part["labels"]["editable_ai_result"] or {}).get("path"))
            editable = load_volume_sidecar(manager.to_absolute(reslice["labels"]["editable_ai_result"]["path"]))
            self.assertTrue(np.all(editable == 0))
            self.assertEqual(result["result"]["warnings"], ["smoke_zero_predictions"])

    def test_tif_trainer_adapter_supports_top_level_volume_loop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_top_level_only_project(root)
            helper = root / "run_tif_trainer_backend.py"
            repo_root = Path(__file__).resolve().parents[1]
            helper.write_text(
                "\n".join(
                    [
                        "import sys",
                        f"sys.path.insert(0, {str(repo_root)!r})",
                        "from AntSleap.tools.tif_trainer_backend import main",
                        "raise SystemExit(main())",
                    ]
                ),
                encoding="utf-8",
            )
            command = f"{os.sys.executable} {helper} --contract {{contract_json}}"
            runner = TifBackendRunner(
                manager,
                {
                    "backend_id": "taxamask_tif_trainer_backend",
                    "prepare_dataset_command": command,
                    "train_command": command,
                    "predict_command": command,
                },
                runs_root=root / "runs",
            )

            prepare = runner.run_action("prepare_dataset", specimen_ids=["top-001"], input_scope="top_level_volume")
            self.assertEqual(prepare["contract"]["input_scope"], "top_level_volume")
            self.assertEqual(prepare["contract"]["specimens"][0]["label_volume"]["role"], "manual_truth")
            self.assertTrue(_run_artifact_path(prepare, prepare["result"]["provenance"]["dataset_manifest"]).exists())

            train = runner.run_action("train", specimen_ids=["top-001", "top-002"], input_scope="top_level_volume")
            manifest_path = _run_artifact_path(train, train["result"]["provenance"]["model_manifest"])
            with open(manifest_path, "r", encoding="utf-8") as handle:
                manifest = json.load(handle)
            self.assertEqual(manifest["input_scope"], "top_level_volume")
            self.assertEqual(manifest["trained_top_level_volumes"], [{"specimen_id": "top-001"}, {"specimen_id": "top-002"}])

            runner.backend_config["model_manifest"] = str(manifest_path)
            before_manual = np.asarray(
                load_volume_sidecar(manager.to_absolute(manager.get_specimen("top-001")["labels"]["manual_truth"]["path"]))
            ).copy()
            predict = runner.run_action("predict", specimen_ids=["top-001"], input_scope="top_level_volume")
            self.assertEqual(predict["contract"]["specimens"][0]["label_volume"]["role"], "none")

            specimen = manager.get_specimen("top-001")
            labels = specimen["labels"]
            self.assertEqual(specimen["review_status"], "pending_review")
            self.assertEqual(labels["working_edit"]["status"], "pending_review")
            self.assertTrue(labels["raw_ai_prediction_backup"]["path"])
            np.testing.assert_array_equal(
                load_volume_sidecar(manager.to_absolute(labels["manual_truth"]["path"])),
                before_manual,
            )

    def test_tif_trainer_adapter_smoke_closes_review_retrain_loop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_train_ready_project(root)
            helper = root / "run_tif_trainer_backend.py"
            repo_root = Path(__file__).resolve().parents[1]
            helper.write_text(
                "\n".join(
                    [
                        "import sys",
                        f"sys.path.insert(0, {str(repo_root)!r})",
                        "from AntSleap.tools.tif_trainer_backend import main",
                        "raise SystemExit(main())",
                    ]
                ),
                encoding="utf-8",
            )
            command = f"{os.sys.executable} {helper} --contract {{contract_json}}"
            runner = TifBackendRunner(
                manager,
                {
                    "backend_id": "taxamask_tif_trainer_backend",
                    "prepare_dataset_command": command,
                    "train_command": command,
                    "predict_command": command,
                },
                runs_root=root / "runs",
            )
            ref = {"specimen_id": "01-0101-11", "part_id": "brain", "reslice_id": "brain_axis_001"}

            prepare = runner.run_action("prepare_dataset", part_refs=[ref])
            self.assertEqual(prepare["contract"]["part_samples"][0]["label_volume"]["role"], "manual_truth")
            self.assertEqual(prepare["result"]["provenance"]["input_label_role"], "manual_truth")
            self.assertTrue(_run_artifact_path(prepare, prepare["result"]["provenance"]["dataset_manifest"]).exists())

            train = runner.run_action("train", part_refs=TRAIN_PART_REFS)
            manifest_path = _run_artifact_path(train, train["result"]["provenance"]["model_manifest"])
            self.assertTrue(manifest_path.exists())
            with open(manifest_path, "r", encoding="utf-8") as handle:
                model_manifest = json.load(handle)
            self.assertEqual(model_manifest["label_role"], "manual_truth")
            self.assertEqual(model_manifest["input_scope"], "part_reslice")

            runner.backend_config["model_manifest"] = str(manifest_path)
            before_manual_record = manager.part_label_record("01-0101-11", "brain", "manual_truth", "brain_axis_001")
            before_manual = np.asarray(load_volume_sidecar(manager.to_absolute(before_manual_record["path"]))).copy()
            predict = runner.run_action("predict", part_refs=[ref])
            self.assertEqual(predict["contract"]["part_samples"][0]["label_volume"]["role"], "none")
            self.assertEqual(predict["result"]["provenance"]["input_label_role"], "none")

            part = manager.get_part("01-0101-11", "brain")
            reslice = manager.get_part_reslice("01-0101-11", "brain", "brain_axis_001")
            editable_record = reslice["labels"]["editable_ai_result"]
            backup_record = reslice["labels"]["raw_ai_prediction_backup"]
            manual_record = reslice["labels"]["manual_truth"]
            self.assertEqual(part["training"]["system_status"], "predicted_pending_review")
            self.assertFalse((part["labels"]["editable_ai_result"] or {}).get("path"))
            self.assertEqual(manual_record["status"], "reviewed")
            self.assertTrue(editable_record["path"])
            self.assertTrue(backup_record["path"])
            np.testing.assert_array_equal(
                load_volume_sidecar(manager.to_absolute(manual_record["path"])),
                before_manual,
            )

            manager.set_part_training_metadata("01-0101-11", "brain", opened_for_review=True, save=True)
            accepted = manager.promote_reviewed_part_results_to_manual_truth([ref])
            self.assertEqual(accepted["count"], 1)
            self.assertEqual(accepted["promoted"][0]["part_id"], "brain")
            reviewed = manager.evaluate_part_train_ready("01-0101-11", "brain", "brain_axis_001")
            self.assertTrue(reviewed["train_ready"])

            retrain_prepare = runner.run_action("prepare_dataset", part_refs=[ref])
            self.assertEqual(retrain_prepare["contract"]["part_samples"][0]["label_volume"]["role"], "manual_truth")
            exported_manifest = _run_artifact_path(
                retrain_prepare,
                retrain_prepare["result"]["provenance"]["dataset_manifest"],
            )
            with open(exported_manifest, "r", encoding="utf-8") as handle:
                exported = json.load(handle)
            self.assertEqual(exported["safety"]["label_role"], "manual_truth")
            self.assertFalse(exported["safety"]["allow_editable_ai_result_as_training_label"])


if __name__ == "__main__":
    unittest.main()
