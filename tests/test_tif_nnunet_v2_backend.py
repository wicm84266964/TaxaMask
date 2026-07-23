import json
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np

from AntSleap.core.tif_backend import TifBackendRunner, nnunet_v2_tif_backend_preset
from AntSleap.core.tif_export import write_nifti_volume
from AntSleap.core.tif_project import TifProjectManager
from AntSleap.core.tif_volume_io import load_volume_sidecar
from AntSleap.tools import tif_nnunet_v2_backend
from tests.test_tif_backend import make_predict_ready_project, make_top_level_only_project, make_train_ready_project


def _absolute_path_values(value):
    found = []
    if isinstance(value, dict):
        for item in value.values():
            found.extend(_absolute_path_values(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_absolute_path_values(item))
    elif isinstance(value, str) and os.path.isabs(value):
        found.append(value)
    return found


class TifNnunetV2BackendTests(unittest.TestCase):
    def _add_second_train_ready_part(self, manager):
        source = json.loads(json.dumps(manager.get_specimen("01-0101-11")))
        source["specimen_id"] = "01-0101-12"
        source["display_name"] = "01-0101-12"
        manager.project_data.setdefault("specimens", []).append(source)
        manager.save_project()

    def _script(self, root):
        script = Path(root) / "run_tif_nnunet_v2_backend.py"
        repo_root = Path(__file__).resolve().parents[1]
        script.write_text(
            "\n".join(
                [
                    "import sys",
                    f"sys.path.insert(0, {str(repo_root)!r})",
                    "from AntSleap.tools.tif_nnunet_v2_backend import main",
                    "raise SystemExit(main())",
                ]
            ),
            encoding="utf-8",
        )
        return script

    def _fake_nnunet_command(self, root):
        script = Path(root) / "fake_nnunet_command.py"
        repo_root = Path(__file__).resolve().parents[1]
        script.write_text(
            "\n".join(
                [
                    "import os, sys",
                    f"sys.path.insert(0, {str(repo_root)!r})",
                    "from pathlib import Path",
                    "from AntSleap.core.tif_export import read_nifti_volume, write_nifti_volume",
                    "import numpy as np, torch",
                    "args = sys.argv[1:]",
                    "mode = args[0] if args else ''",
                    "Path(os.environ['nnUNet_results']).mkdir(parents=True, exist_ok=True)",
                    "if mode == 'plan':",
                    "    dataset = 'Dataset701_TaxaMaskTifVolumeSegmentation'",
                    "    out = Path(os.environ['nnUNet_preprocessed']) / dataset",
                    "    out.mkdir(parents=True, exist_ok=True)",
                    "    (out / 'nnUNetPlans.json').write_text('{}', encoding='utf-8')",
                    "elif mode == 'train':",
                    "    dataset = 'Dataset701_TaxaMaskTifVolumeSegmentation'",
                    "    out = Path(os.environ['nnUNet_results']) / dataset / 'nnUNetTrainer__nnUNetPlans__3d_fullres' / 'fold_0'",
                    "    out.mkdir(parents=True, exist_ok=True)",
                    "    torch.save({'current_epoch': 3, 'init_args': {'plans': {'configurations': {'3d_fullres': {'batch_size': 2, 'patch_size': [2, 3, 4]}}}}, 'optimizer_state': {'param_groups': [{'lr': 0.001, 'weight_decay': 0.01}]}, 'logging': {'lrs': [0.001]}}, out / 'checkpoint_final.pth')",
                    "elif mode == 'predict':",
                    "    input_dir = Path(args[args.index('-i') + 1])",
                    "    output_dir = Path(args[args.index('-o') + 1])",
                    "    output_dir.mkdir(parents=True, exist_ok=True)",
                    "    for image in input_dir.glob('*_0000.nii.gz'):",
                    "        case_id = image.name[:-len('_0000.nii.gz')]",
                    "        source = read_nifti_volume(image)",
                    "        write_nifti_volume(output_dir / f'{case_id}.nii.gz', np.full(source.shape, 1, dtype=np.uint16))",
                    "raise SystemExit(0)",
                ]
            ),
            encoding="utf-8",
        )
        return script

    def test_preset_keeps_contract_commands_editable(self):
        preset = nnunet_v2_tif_backend_preset("C:/Python/python.exe")
        self.assertEqual(preset["backend_id"], "taxamask_tif_nnunet_v2_backend")
        self.assertIn("{contract_json}", preset["train_command"])
        self.assertEqual(preset["python_executable"], "C:/Python/python.exe")

    def test_adapter_prepare_dataset_writes_compact_nnunet_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_train_ready_project(root)
            script = self._script(root)
            runner = TifBackendRunner(
                manager,
                {
                    "backend_id": "taxamask_tif_nnunet_v2_backend",
                    "prepare_dataset_command": f"{os.sys.executable} {script} --contract {{contract_json}} --overwrite-dataset",
                },
                runs_root=root / "runs",
            )

            result = runner.run_action(
                "prepare_dataset",
                part_refs=[{"specimen_id": "01-0101-11", "part_id": "brain", "reslice_id": "brain_axis_001"}],
            )

            dataset_ref = Path(result["result"]["provenance"]["dataset_dir"])
            dataset_dir = dataset_ref if dataset_ref.is_absolute() else Path(result["run_dir"]) / dataset_ref
            self.assertTrue((dataset_dir / "dataset.json").exists())
            self.assertTrue(any((dataset_dir / "imagesTr").glob("*_0000.nii.gz")))
            with open(dataset_dir / "nnunet_part_manifest.json", "r", encoding="utf-8") as handle:
                manifest = json.load(handle)
            self.assertEqual(manifest["label_id_mode"], "compact")
            self.assertEqual(manifest["label_id_mapping"]["source_to_nnunet"]["1"], 1)

    def test_adapter_train_runs_fake_nnunet_and_writes_usable_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_train_ready_project(root)
            script = self._script(root)
            fake = self._fake_nnunet_command(root)
            runner = TifBackendRunner(manager, {"backend_id": "taxamask_tif_nnunet_v2_backend"}, runs_root=root / "runs")
            contract = runner.build_contract(
                "train",
                run_id="train_fake",
                run_dir=root / "runs" / "train" / "train_fake",
                part_refs=[
                    {"specimen_id": "01-0101-11", "part_id": "brain", "reslice_id": "brain_axis_001"},
                    {"specimen_id": "01-0101-12", "part_id": "brain", "reslice_id": "brain_axis_001"},
                ],
            )
            contract["training_split"] = {
                "strategy": {"seed": 17},
                "assignments": [
                    {
                        "sample_id": item["sample_id"],
                        "partition": "train" if index == 0 else "validation",
                    }
                    for index, item in enumerate(contract["part_samples"])
                ]
            }
            runner.write_contract(contract)
            args = tif_nnunet_v2_backend.parse_args(
                [
                    "--contract",
                    str(Path(contract["run_dir"]) / "contract.json"),
                    "--overwrite-dataset",
                    "--plan-command",
                    f"{os.sys.executable} {fake} plan",
                    "--train-command",
                    f"{os.sys.executable} {fake} train",
                    "--dataset-id",
                    "701",
                    "--dataset-name",
                    "TaxaMaskTifVolumeSegmentation",
                    "--device",
                    "cpu",
                ]
            )
            tif_nnunet_v2_backend.run_contract(str(Path(contract["run_dir"]) / "contract.json"), args)

            with open(contract["result_json"], "r", encoding="utf-8") as handle:
                result = json.load(handle)
            manifest_path = Path(contract["result_json"]).parent / result["provenance"]["model_manifest"]
            self.assertTrue(manifest_path.exists())
            with open(manifest_path, "r", encoding="utf-8") as handle:
                manifest = json.load(handle)
            self.assertEqual(manifest["training_mode"], "nnunet_v2_real")
            self.assertTrue(manifest["usable_for_research_prediction"])
            self.assertEqual(manifest["nnunet"]["label_id_mode"], "compact")
            self.assertEqual(_absolute_path_values(result), [])
            self.assertEqual(_absolute_path_values(manifest), [])

    def test_adapter_train_rejects_single_sample_before_nnunet_training(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_train_ready_project(root)
            fake = self._fake_nnunet_command(root)
            runner = TifBackendRunner(manager, {"backend_id": "taxamask_tif_nnunet_v2_backend"}, runs_root=root / "runs")
            contract = runner.build_contract(
                "train",
                run_id="train_single_sample",
                run_dir=root / "runs" / "train" / "train_single_sample",
                part_refs=[{"specimen_id": "01-0101-11", "part_id": "brain", "reslice_id": "brain_axis_001"}],
            )
            runner.write_contract(contract)
            args = tif_nnunet_v2_backend.parse_args(
                [
                    "--contract",
                    str(Path(contract["run_dir"]) / "contract.json"),
                    "--overwrite-dataset",
                    "--plan-command",
                    f"{os.sys.executable} {fake} plan",
                    "--train-command",
                    f"{os.sys.executable} {fake} train",
                    "--dataset-id",
                    "701",
                    "--dataset-name",
                    "TaxaMaskTifVolumeSegmentation",
                    "--device",
                    "cpu",
                ]
            )

            with self.assertRaisesRegex(ValueError, "nnunet_training_requires_at_least_2_samples:1"):
                tif_nnunet_v2_backend.run_contract(str(Path(contract["run_dir"]) / "contract.json"), args)

    def test_adapter_train_reports_missing_nnunet_command_before_training(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_train_ready_project(root)
            runner = TifBackendRunner(manager, {"backend_id": "taxamask_tif_nnunet_v2_backend"}, runs_root=root / "runs")
            contract = runner.build_contract(
                "train",
                run_id="train_missing_command",
                run_dir=root / "runs" / "train" / "train_missing_command",
                part_refs=[{"specimen_id": "01-0101-11", "part_id": "brain", "reslice_id": "brain_axis_001"}],
            )
            runner.write_contract(contract)
            args = tif_nnunet_v2_backend.parse_args(
                [
                    "--contract",
                    str(Path(contract["run_dir"]) / "contract.json"),
                    "--overwrite-dataset",
                    "--plan-command",
                    "definitely_missing_nnunet_command",
                    "--dataset-id",
                    "701",
                    "--dataset-name",
                    "TaxaMaskTifVolumeSegmentation",
                    "--device",
                    "cpu",
                ]
            )

            with self.assertRaisesRegex(FileNotFoundError, "nnunet_command_not_found:definitely_missing_nnunet_command"):
                tif_nnunet_v2_backend.run_contract(str(Path(contract["run_dir"]) / "contract.json"), args)

    def test_adapter_train_top_level_volume_writes_scope_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_top_level_only_project(root)
            script = self._script(root)
            runner = TifBackendRunner(manager, {"backend_id": "taxamask_tif_nnunet_v2_backend"}, runs_root=root / "runs")
            contract = runner.build_contract(
                "train",
                run_id="train_top_level_dry",
                run_dir=root / "runs" / "train" / "train_top_level_dry",
                specimen_ids=["top-001", "top-002"],
                input_scope="top_level_volume",
            )
            contract["training_split"] = {
                "strategy": {"seed": 17},
                "assignments": [
                    {"sample_id": "top-001", "partition": "train"},
                    {"sample_id": "top-002", "partition": "validation"},
                ]
            }
            runner.write_contract(contract)
            args = tif_nnunet_v2_backend.parse_args(
                [
                    "--contract",
                    str(Path(contract["run_dir"]) / "contract.json"),
                    "--overwrite-dataset",
                    "--dry-run-commands",
                    "--dataset-id",
                    "702",
                    "--dataset-name",
                    "TaxaMaskTifRegions",
                    "--device",
                    "cpu",
                ]
            )
            tif_nnunet_v2_backend.run_contract(str(Path(contract["run_dir"]) / "contract.json"), args)

            with open(contract["result_json"], "r", encoding="utf-8") as handle:
                result = json.load(handle)
            manifest_path = Path(contract["result_json"]).parent / result["provenance"]["model_manifest"]
            with open(manifest_path, "r", encoding="utf-8") as handle:
                manifest = json.load(handle)
            self.assertEqual(manifest["model_family"], "nnunet_v2_tif_region")
            self.assertEqual(manifest["input_scope"], "top_level_volume")
            self.assertEqual(manifest["trained_parts"], [])
            self.assertEqual(
                manifest["trained_top_level_volumes"],
                [{"specimen_id": "top-001"}, {"specimen_id": "top-002"}],
            )

    def test_adapter_predict_restores_taxamask_label_ids_and_imports_editable_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_predict_ready_project(root)
            script = self._script(root)
            fake = self._fake_nnunet_command(root)
            model_manifest = root / "model_manifest.json"
            nnunet_results = root / "nnunet_results"
            checkpoint = nnunet_results / "Dataset701_TaxaMaskTifVolumeSegmentation" / "nnUNetTrainer__nnUNetPlans__3d_fullres" / "fold_0" / "checkpoint_final.pth"
            checkpoint.parent.mkdir(parents=True)
            checkpoint.write_bytes(b"fake checkpoint")
            model_manifest.write_text(
                json.dumps(
                    {
                        "schema_version": "ant3d_tif_model_manifest_v1",
                        "model_family": "nnunet_v2_part_reslice",
                        "usable_for_research_prediction": True,
                        "nnunet": {
                            "dataset_id": 701,
                            "dataset_name": "TaxaMaskTifVolumeSegmentation",
                            "configuration": "3d_fullres",
                            "fold": "0",
                            "trainer": "nnUNetTrainer",
                            "plans": "nnUNetPlans",
                            "checkpoint": "checkpoint_final.pth",
                            "results_root": str(nnunet_results),
                            "file_ending": ".nii.gz",
                            "label_id_mode": "compact",
                            "label_id_mapping": {"nnunet_to_source": {"0": 0, "1": 2}},
                        },
                    }
                ),
                encoding="utf-8",
            )
            runner = TifBackendRunner(
                manager,
                {
                    "backend_id": "taxamask_tif_nnunet_v2_backend",
                    "predict_command": (
                        f"{os.sys.executable} {script} --contract {{contract_json}} "
                        f"--predict-command \"{os.sys.executable} {fake} predict\" --device cpu"
                    ),
                    "model_manifest": str(model_manifest),
                },
                runs_root=root / "runs",
            )

            result = runner.run_action(
                "predict",
                part_refs=[{"specimen_id": "01-0101-11", "part_id": "brain", "reslice_id": "brain_axis_001"}],
            )

            self.assertEqual(len(result["imported"]), 1)
            part = manager.get_part("01-0101-11", "brain")
            reslice = manager.get_part_reslice("01-0101-11", "brain", "brain_axis_001")
            editable = load_volume_sidecar(manager.to_absolute(reslice["labels"]["editable_ai_result"]["path"]))
            self.assertTrue(np.all(editable == 2))
            self.assertFalse((part["labels"]["editable_ai_result"] or {}).get("path"))
            self.assertEqual(reslice["labels"]["manual_truth"]["path"], "")

    def test_adapter_predict_top_level_volume_imports_current_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_top_level_only_project(root)
            script = self._script(root)
            fake = self._fake_nnunet_command(root)
            model_manifest = root / "model_manifest.json"
            nnunet_results = root / "nnunet_results"
            checkpoint = nnunet_results / "Dataset702_TaxaMaskTifRegions" / "nnUNetTrainer__nnUNetPlans__3d_fullres" / "fold_0" / "checkpoint_final.pth"
            checkpoint.parent.mkdir(parents=True)
            checkpoint.write_bytes(b"fake checkpoint")
            model_manifest.write_text(
                json.dumps(
                    {
                        "schema_version": "ant3d_tif_model_manifest_v1",
                        "model_family": "nnunet_v2_tif_region",
                        "input_scope": "top_level_volume",
                        "usable_for_research_prediction": True,
                        "nnunet": {
                            "dataset_id": 702,
                            "dataset_name": "TaxaMaskTifRegions",
                            "configuration": "3d_fullres",
                            "fold": "0",
                            "trainer": "nnUNetTrainer",
                            "plans": "nnUNetPlans",
                            "checkpoint": "checkpoint_final.pth",
                            "results_root": str(nnunet_results),
                            "file_ending": ".nii.gz",
                            "label_id_mode": "identity",
                            "label_id_mapping": {"nnunet_to_source": {"0": 0, "1": 1}},
                        },
                    }
                ),
                encoding="utf-8",
            )
            runner = TifBackendRunner(
                manager,
                {
                    "backend_id": "taxamask_tif_nnunet_v2_backend",
                    "predict_command": (
                        f"{os.sys.executable} {script} --contract {{contract_json}} "
                        f"--predict-command \"{os.sys.executable} {fake} predict\" --device cpu"
                    ),
                    "model_manifest": str(model_manifest),
                },
                runs_root=root / "runs",
            )

            result = runner.run_action("predict", specimen_ids=["top-001"], input_scope="top_level_volume")

            self.assertEqual(len(result["imported"]), 1)
            specimen = manager.get_specimen("top-001")
            labels = specimen["labels"]
            editable = load_volume_sidecar(manager.to_absolute(labels["working_edit"]["path"]))
            backup = load_volume_sidecar(manager.to_absolute(labels["raw_ai_prediction_backup"]["path"]))
            self.assertTrue(np.all(editable == 1))
            self.assertTrue(np.all(backup == 1))
            self.assertEqual(specimen["review_status"], "pending_review")

            reloaded = TifProjectManager()
            reloaded.load_project(manager.current_project_path)
            reloaded_specimen = reloaded.get_specimen("top-001")
            reloaded_labels = reloaded_specimen["labels"]
            reloaded_backup = reloaded_labels["raw_ai_prediction_backup"]
            self.assertEqual(reloaded_backup["status"], "raw_backup")
            self.assertTrue(reloaded_backup["path"])
            np.testing.assert_array_equal(
                load_volume_sidecar(reloaded.to_absolute(reloaded_backup["path"])),
                backup,
            )


if __name__ == "__main__":
    unittest.main()
