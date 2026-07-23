import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from AntSleap.core.project import ProjectManager
from AntSleap.core.training_run_2d import prepare_blink_training_run
from AntSleap.ui.blink_lab import (
    BLINK_EXPERT_BACKEND_HEATMAP,
    BLINK_EXPERT_BACKEND_VIT_B,
    BlinkTrainingThread,
)


class _FakeTrainer:
    report_root = None

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.last_report = {}

    def train(self, **_kwargs):
        target = Path(self.kwargs["save_dir"]) / self.kwargs["part_name"]
        target.mkdir()
        weight = target / "expert_fixture.pth"
        manifest = target / "expert_fixture.manifest.json"
        weight.write_bytes(b"blink weights")
        manifest.write_text(
            json.dumps({"schema_version": "taxamask_blink_expert_manifest_v1"}),
            encoding="utf-8",
        )
        report = Path(self.report_root) / "blink_report"
        report.mkdir(parents=True)
        (report / "report_summary.json").write_text("{}", encoding="utf-8")
        self.last_report = {
            "dir": str(report),
            "manifest_path": str(manifest),
        }
        return str(weight)


class BlinkTrainingRunLifecycleTests(unittest.TestCase):
    def _prepared(self, root, entrypoint):
        project_dir = root / "project"
        project_dir.mkdir()
        manager = ProjectManager()
        manager.create_project("ants", project_dir)
        manager.project_data["taxonomy"] = ["Head", "Mandible"]
        manager.project_data["locator_scope"] = ["Head"]
        paths = []
        for index in range(2):
            path = project_dir / f"ant_{index}.png"
            Image.new("RGB", (32, 24), color=(120, 90, 60)).save(path)
            paths.append(str(path))
        manager.add_images(paths, save=True)
        for path in paths:
            manager.update_label(
                path,
                "Mandible",
                [[5, 5], [15, 5], [10, 14]],
                box=[5, 5, 15, 14],
                save=True,
            )
            manager.update_trajectory(
                path,
                "Mandible",
                [{"box": [4, 4, 18, 16]}, {"box": [5, 5, 15, 14]}],
                parent_context={
                    "parent_part": "Head",
                    "parent_box": [2, 2, 20, 18],
                },
                save=True,
            )
        manager.initialize_integrity_baseline()
        prepared = prepare_blink_training_run(
            manager,
            runs_root=root / "runs",
            entrypoint=entrypoint,
            target_part="Mandible",
            parent_part="Head",
            effective_config={
                "epochs": 1,
                "batch_size": 1,
                "learning_rate": 0.001,
                "weight_decay": 0.0001,
                "random_seed": 0,
                "input_resolution": [224, 224],
                "preprocessing": {"dataset_adapter": "blink"},
                "model": {
                    "family": entrypoint,
                    "version": "1",
                    "locator": "disabled",
                    "parts": "Mandible",
                },
                "loss_weights": {"outer": {"final": 1.0}},
            },
            backend={
                "backend_id": entrypoint,
                "backend_version": "1.0",
                "adapter_id": "blink_training_thread",
                "adapter_version": "1.0",
            },
        )
        return prepared

    def _assert_backend(self, backend, entrypoint, patch_target):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepared = self._prepared(root, entrypoint)
            _FakeTrainer.report_root = root / "reports"
            model_root = root / "models"
            thread = BlinkTrainingThread(
                project_path=str(root / "unused.json"),
                part_name="Mandible",
                parent_part="Head",
                epochs=1,
                batch_size=1,
                trainer_backend=backend,
                training_run=prepared.run,
                training_records=prepared.training_records,
                validation_records=prepared.validation_records,
                model_output_root=model_root,
            )
            errors = []
            thread.error_signal.connect(errors.append)
            with patch(patch_target, _FakeTrainer):
                thread.run()
            record = prepared.run.recorder.load(prepared.run.run_id)
            self.assertEqual(record["status"], "succeeded", errors or record.get("error"))
            self.assertEqual(
                {item["role"] for item in record["artifacts"]},
                {"output_weights", "model_manifest", "training_report"},
            )
            publication = json.loads(
                (
                    model_root
                    / "training_runs"
                    / prepared.run.run_id
                    / "publication.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(publication["status"], "active")

    def test_vit_b_lifecycle(self):
        self._assert_backend(
            BLINK_EXPERT_BACKEND_VIT_B,
            "blink_vit_b",
            "AntSleap.core.blink_trainer.BlinkExpertTrainer",
        )

    def test_heatmap_lifecycle(self):
        self._assert_backend(
            BLINK_EXPERT_BACKEND_HEATMAP,
            "blink_heatmap",
            "AntSleap.core.blink_heatmap_trainer.BlinkHeatmapTrainer",
        )


if __name__ == "__main__":
    unittest.main()
