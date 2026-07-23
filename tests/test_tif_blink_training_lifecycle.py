import json
import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.test_tif_backend import make_top_level_only_project
from tif_blink.cli import train_from_nnunet_preprocessed, train_from_project

from AntSleap.core.training_run_recorder import TrainingRunRecorder
from tif_blink.labels import LabelMapping
from tif_blink.train import TifBlinkTrainConfig, checkpoint_payload, save_manifest


def _args(**overrides):
    values = {
        "project": "",
        "specimen": [],
        "output_dir": "",
        "context_slices": 0,
        "view_mode": ["normal"],
        "include_boundary_channel": False,
        "base_channels": 4,
        "epochs": 1,
        "batch_size": 1,
        "learning_rate": 0.001,
        "weight_decay": 0.01,
        "boundary_weight": 2.0,
        "dice_weight": 1.0,
        "grouped_views": False,
        "balanced_sampler": False,
        "consistency_weight": 0.15,
        "device": "cpu",
        "model_name": "tif_blink_test",
        "seed": 17,
        "preprocessed_root": "",
        "dataset_dir": "",
        "plans": "plans",
        "configuration": "3d_fullres",
        "fold": 0,
        "trusted_source_id": "reviewed_nnunet_dataset",
        "trusted_source_note": "Labels were reviewed before this training run.",
        "num_workers": 0,
        "ignore_label": -1,
        "ignore_to_background": True,
        "renormalize_percentile": True,
        "patch_size": None,
        "foreground_patch_probability": 0.5,
        "foreground_slices_only": False,
        "slice_stride": 1,
        "max_cases": None,
        "max_train_cases": None,
        "max_val_cases": None,
        "max_slices_per_case": None,
    }
    values.update(overrides)
    return types.SimpleNamespace(**values)


def _fake_train_result(_train_dataset, config, **_kwargs):
    output = Path(config.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    history = output / "history.json"
    progress = output / "history_progress.jsonl"
    manifest = output / "model_manifest.json"
    best = output / "best.pt"
    last = output / "last.pt"
    history.write_text('[{"epoch": 1}]', encoding="utf-8")
    progress.write_text('{"epoch": 1}\n', encoding="utf-8")
    manifest.write_text('{"schema_version":"tif_blink_model_manifest_v1"}', encoding="utf-8")
    best.write_bytes(b"best")
    last.write_bytes(b"last")
    return {
        "history": [{"epoch": 1}],
        "history_path": str(history),
        "manifest": {},
        "manifest_path": str(manifest),
        "best_checkpoint": str(best),
        "last_checkpoint": str(last),
        "best_metric": 0.5,
    }


class _FakeExternalDataset:
    def __init__(self, config, dataset_dir, cases_by_split):
        self.config = config
        self.dataset_dir = Path(dataset_dir)
        self.cases = list(cases_by_split[config.split])
        self.label_mapping = types.SimpleNamespace(
            num_classes=3,
            label_id_to_class={0: 0, 1: 1, 2: 2},
        )

    @property
    def case_ids(self):
        return [case.case_id for case in self.cases]

    def __len__(self):
        return len(self.cases)


class TifBlinkTrainingLifecycleTests(unittest.TestCase):
    def test_model_artifacts_do_not_persist_private_absolute_output_path(self):
        import torch

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "private_user_path" / "outputs"
            output_dir.mkdir(parents=True)
            manifest_path = output_dir / "model_manifest.json"
            config = TifBlinkTrainConfig(
                num_classes=2,
                in_channels=1,
                output_dir=str(output_dir),
            )
            mapping = LabelMapping(
                label_id_to_class={0: 0, 2: 1},
                class_to_label_id={0: 0, 1: 2},
            )

            manifest = save_manifest(
                str(manifest_path),
                config,
                mapping,
                [],
                str(output_dir / "best.pt"),
                str(output_dir / "last.pt"),
            )
            checkpoint = checkpoint_payload(
                torch.nn.Linear(1, 1),
                config,
                mapping,
                1,
                [],
                0.0,
            )

            self.assertEqual(manifest["train_config"]["output_dir"], ".")
            self.assertEqual(manifest["checkpoints"], {"best": "best.pt", "last": "last.pt"})
            self.assertEqual(checkpoint["train_config"]["output_dir"], ".")
            self.assertFalse(os.path.isabs(checkpoint["train_config"]["output_dir"]))

    def test_project_training_records_verified_specimen_split_and_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_top_level_only_project(root)
            args = _args(
                project=manager.current_project_path,
                output_dir=str(Path(manager.project_dir) / "runs" / "tif_blink"),
            )

            with patch("tif_blink.cli.train_model", side_effect=_fake_train_result):
                summary = train_from_project(args)

            recorder = TrainingRunRecorder(
                Path(manager.project_dir) / "runs" / "tif_blink",
                database_path=manager.current_database_path,
                recover_on_startup=False,
            )
            record = next(
                item for item in recorder.list_records() if item["run_id"] == summary["run_id"]
            )
            self.assertEqual(record["status"], "succeeded")
            self.assertEqual(record["entrypoint"], "tif_blink_project")
            self.assertEqual(set(summary["train_specimens"] + summary["val_specimens"]), {"top-001", "top-002"})
            self.assertEqual(len(summary["train_specimens"]), 1)
            self.assertEqual(len(summary["val_specimens"]), 1)
            self.assertEqual(record["dataset_ref"]["trusted_label_policy"], "manual_truth_only")
            roles = [item["role"] for item in record["artifacts"]]
            self.assertEqual(roles.count("output_weights"), 2)
            self.assertIn("model_manifest", roles)
            self.assertIn("training_history", roles)

    def test_project_open_failure_leaves_global_sqlite_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = _args(
                project=str(root / "missing_project.json"),
                output_dir=str(root / "blink_runs"),
            )

            with self.assertRaises(Exception):
                train_from_project(args)

            records = TrainingRunRecorder(
                root / "blink_runs", recover_on_startup=False
            ).list_records()
            self.assertEqual(records[-1]["status"], "failed")
            self.assertEqual(records[-1]["entrypoint"], "tif_blink_project")
            self.assertEqual(records[-1]["error"]["stage"], "project_load")

    def test_project_training_keyboard_interrupt_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = make_top_level_only_project(root)
            args = _args(
                project=manager.current_project_path,
                output_dir=str(Path(manager.project_dir) / "runs" / "tif_blink"),
            )

            with patch("tif_blink.cli.train_model", side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    train_from_project(args)

            records = TrainingRunRecorder(
                Path(manager.project_dir) / "runs" / "tif_blink",
                database_path=manager.current_database_path,
                recover_on_startup=False,
            ).list_records()
            self.assertEqual(records[-1]["status"], "interrupted")
            self.assertEqual(records[-1]["error"]["stage"], "tif_blink_project")

    def test_external_nnunet_training_records_trust_hashes_split_and_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset_dir = root / "Dataset901_Test"
            dataset_dir.mkdir()
            (dataset_dir / "dataset.json").write_text('{"labels":{"background":0,"region":1}}', encoding="utf-8")
            (dataset_dir / "splits_final.json").write_text('[{"train":["case_a"],"val":["case_b"]}]', encoding="utf-8")
            (dataset_dir / "nnUNetPlans.json").write_text('{"configurations":{"3d_fullres":{}}}', encoding="utf-8")
            (dataset_dir / "dataset_fingerprint.json").write_text('{"median_relative_size_after_cropping":1.0}', encoding="utf-8")
            cases_by_split = {"train": [], "val": []}
            for split, case_id in (("train", "case_a"), ("val", "case_b")):
                image = dataset_dir / f"{case_id}.b2nd"
                truth = dataset_dir / f"{case_id}_seg.b2nd"
                image.write_bytes(f"image:{case_id}".encode("ascii"))
                truth.write_bytes(f"truth:{case_id}".encode("ascii"))
                cases_by_split[split].append(
                    types.SimpleNamespace(
                        case_id=case_id,
                        image_path=image,
                        seg_path=truth,
                        shape=(1, 2, 12, 10),
                    )
                )
            args = _args(
                output_dir=str(root / "external_runs"),
                preprocessed_root=str(root),
                dataset_dir=str(dataset_dir),
            )

            def fake_dataset(config):
                return _FakeExternalDataset(config, dataset_dir, cases_by_split)

            with patch("tif_blink.cli.NnUNetBlinkDataset", side_effect=fake_dataset), patch(
                "tif_blink.cli.train_model", side_effect=_fake_train_result
            ):
                summary = train_from_nnunet_preprocessed(args)

            recorder = TrainingRunRecorder(
                root / "external_runs", recover_on_startup=False
            )
            record = next(
                item for item in recorder.list_records() if item["run_id"] == summary["run_id"]
            )
            self.assertEqual(record["status"], "succeeded")
            self.assertEqual(record["entrypoint"], "tif_blink_nnunet_preprocessed")
            self.assertEqual(record["dataset_ref"]["trusted_label_policy"], "verified_external_truth")
            self.assertEqual(record["dataset_ref"]["trusted_source_ref"], "reviewed_nnunet_dataset")
            split_path = Path(summary["run_dir"]) / record["split_manifest"]["relative_path"]
            split = json.loads(split_path.read_text(encoding="utf-8"))
            self.assertEqual(
                {(item["sample_id"], item["partition"]) for item in split["assignments"]},
                {("case_a", "train"), ("case_b", "validation")},
            )

    def test_external_nnunet_rejects_missing_trust_note_and_case_leakage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing_note_args = _args(
                output_dir=str(root / "missing_note_runs"),
                trusted_source_note="",
            )
            with self.assertRaisesRegex(ValueError, "trusted_source_note_required"):
                train_from_nnunet_preprocessed(missing_note_args)
            missing_records = TrainingRunRecorder(
                root / "missing_note_runs", recover_on_startup=False
            ).list_records()
            self.assertEqual(missing_records[-1]["status"], "failed")

            dataset_dir = root / "Dataset902_Leak"
            dataset_dir.mkdir()
            (dataset_dir / "dataset.json").write_text("{}", encoding="utf-8")
            (dataset_dir / "splits_final.json").write_text("[]", encoding="utf-8")
            (dataset_dir / "nnUNetPlans.json").write_text("{}", encoding="utf-8")
            (dataset_dir / "dataset_fingerprint.json").write_text("{}", encoding="utf-8")
            image = dataset_dir / "same.b2nd"
            truth = dataset_dir / "same_seg.b2nd"
            image.write_bytes(b"image")
            truth.write_bytes(b"truth")
            case = types.SimpleNamespace(
                case_id="same",
                image_path=image,
                seg_path=truth,
                shape=(1, 2, 8, 8),
            )
            cases_by_split = {"train": [case], "val": [case]}
            leak_args = _args(
                output_dir=str(root / "leak_runs"),
                preprocessed_root=str(root),
                dataset_dir=str(dataset_dir),
            )

            with patch(
                "tif_blink.cli.NnUNetBlinkDataset",
                side_effect=lambda config: _FakeExternalDataset(config, dataset_dir, cases_by_split),
            ):
                with self.assertRaisesRegex(ValueError, "case_leakage:same"):
                    train_from_nnunet_preprocessed(leak_args)
            leak_records = TrainingRunRecorder(
                root / "leak_runs", recover_on_startup=False
            ).list_records()
            self.assertEqual(leak_records[-1]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
