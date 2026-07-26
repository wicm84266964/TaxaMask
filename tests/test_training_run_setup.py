import json
import tempfile
import unittest
from pathlib import Path

from AntSleap.core.file_integrity import compute_fingerprint
from AntSleap.core.training_run_recorder import TrainingRunRecorder
from AntSleap.core.training_run_setup import (
    build_and_attach_verified_training_inputs,
)


class TrainingRunSetupTests(unittest.TestCase):
    def test_external_input_path_remains_runtime_only_and_recheck_succeeds(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            runs_root = root / "runs"
            external_root = root / "external"
            external_root.mkdir()
            image_path = external_root / "image.png"
            image_path.write_bytes(b"image")

            recorder = TrainingRunRecorder(runs_root, recover_on_startup=False)
            run = recorder.create_pending(
                "setup_test",
                project_ref={
                    "project_kind": "taxamask_2d",
                    "project_id": "project_1",
                    "project_data_version_id": "data_v1",
                },
                dataset_ref={
                    "dataset_id": "project_1",
                    "data_version_id": "data_v1",
                    "trusted_label_policy": "manual_truth_only",
                    "source_kind": "project",
                },
                effective_config={
                    "epochs": 1,
                    "batch_size": 1,
                    "learning_rate": 0.001,
                    "weight_decay": 0.0,
                    "random_seed": 42,
                    "input_resolution": [64, 64],
                    "preprocessing": {},
                    "model": {"family": "test", "version": "1"},
                    "loss_weights": {},
                    "persist_weights": False,
                },
                backend={
                    "backend_id": "test_backend",
                    "backend_version": "1.0",
                    "adapter_id": "test_adapter",
                    "adapter_version": "1.0",
                },
            )
            truth_path = Path(run.run_dir) / "truth.json"
            truth_path.write_text('{"parts":{"Head":[]}}', encoding="utf-8")
            build_and_attach_verified_training_inputs(
                run,
                file_specs=[
                    {
                        "file_id": "image_1",
                        "role": "training_image",
                        "external_location_ref": "source_image_1",
                        "runtime_path": image_path,
                        "expected": compute_fingerprint(image_path),
                    },
                    {
                        "file_id": "truth_1",
                        "role": "manual_truth",
                        "path_base": "run_root",
                        "relative_path": "truth.json",
                        "expected": compute_fingerprint(truth_path),
                    },
                ],
                assignments=[
                    {
                        "sample_id": "sample_1",
                        "partition": "train",
                        "group_id": "group_1",
                        "input_file_ids": ["image_1", "truth_1"],
                    }
                ],
                dataset_id="project_1",
                data_version_id="data_v1",
                strategy={
                    "name": "group_holdout",
                    "version": "v1",
                    "seed": 42,
                    "validation_ratio": 0.0,
                },
            )
            run.mark_running()
            report_path = Path(run.run_dir) / "report.json"
            report_path.write_text('{"status":"passed"}', encoding="utf-8")
            run.add_artifact(
                artifact_id="training_report",
                role="training_report",
                path=report_path,
            )
            succeeded = run.succeed()

            self.assertEqual(succeeded["status"], "succeeded")
            record = json.loads(Path(run.record_path).read_text(encoding="utf-8"))
            manifest_path = Path(run.run_dir) / record["integrity_manifest"][
                "relative_path"
            ]
            serialized = manifest_path.read_text(encoding="utf-8")
            self.assertIn('"external_location_ref": "source_image_1"', serialized)
            self.assertNotIn(str(image_path.resolve()), serialized)
            self.assertNotIn(str(image_path.resolve()), Path(run.record_path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
