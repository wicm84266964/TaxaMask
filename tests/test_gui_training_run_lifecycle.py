import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from AntSleap.core.project import ProjectManager
from AntSleap.core.training_run_2d import prepare_2d_training_run
from AntSleap.ui.main_window_model_management import MainWindowModelManagementMixin
from AntSleap.ui.main_window_training import MainWindowTrainingMixin
from AntSleap.ui.main_window_workers import TrainingThread


class _Engine:
    def __init__(self, root, *, fail=False):
        self.root = Path(root)
        self.fail = fail
        self.device = "cpu"
        self.weights_dir = str(self.root / "models")
        Path(self.weights_dir).mkdir()
        self.locator_resolution = (32, 24)
        self.locator = object()
        self.opt_loc = object()
        self.history = {}

    def ensure_locator_loaded(self):
        return self.locator

    def train_epoch(self, *_args, **_kwargs):
        if self.fail:
            raise RuntimeError("training exploded")
        return 0.2

    def validate_epoch(self, *_args, **_kwargs):
        return {"loss": 0.1, "pixel_error": 1.0}

    def save_weights(self, *, output_dir, artifact_key, **_kwargs):
        Path(output_dir, f"locator_{artifact_key}.pth").write_bytes(b"weights")
        return artifact_key

    def generate_report(self, *_args, **_kwargs):
        report_dir = self.root / "reports" / "parent"
        report_dir.mkdir(parents=True)
        (report_dir / "report_summary.json").write_text(
            json.dumps({"status": "passed"}), encoding="utf-8"
        )
        return {"dir": str(report_dir)}


class GuiTrainingRunLifecycleTests(unittest.TestCase):
    def _prepared(self, root):
        project_dir = root / "project"
        project_dir.mkdir()
        manager = ProjectManager()
        manager.create_project("ants", project_dir)
        manager.project_data["taxonomy"] = ["Head"]
        manager.project_data["locator_scope"] = ["Head"]
        images = []
        for index in range(2):
            path = project_dir / f"ant_{index}.png"
            Image.new("RGB", (32, 24), color=(100, 80, 60)).save(path)
            images.append(str(path))
        manager.add_images(images, save=True)
        for path in images:
            manager.update_label(
                path,
                "Head",
                [[2, 2], [20, 2], [10, 18]],
                box=[2, 2, 20, 18],
                save=True,
            )
        manager.initialize_integrity_baseline()
        prepared = prepare_2d_training_run(
            manager,
            runs_root=root / "runs",
            entrypoint="builtin_locator_sam",
            effective_config={
                "epochs": 1,
                "batch_size": 1,
                "learning_rate": 0.001,
                "weight_decay": 0.0001,
                "random_seed": 0,
                "input_resolution": [32, 24],
                "preprocessing": {"dataset_adapter": "TwoStageDataset"},
                "model": {
                    "family": "AntEngine",
                    "version": "1",
                    "locator": "TraitRegressor",
                    "parts": "disabled",
                },
                "loss_weights": {"locator": {"heatmap": 1.0, "wh": 1.0}},
            },
            backend={
                "backend_id": "builtin_locator_sam",
                "backend_version": "1.0",
                "adapter_id": "gui_training_thread",
                "adapter_version": "1.0",
            },
            include_parts=False,
        )
        preflight = {
            "locator_train_data": prepared.locator_train_records,
            "locator_val_data": prepared.locator_validation_records,
            "parts_train_data": [],
            "parts_val_data": [],
            "selected_locator_size": (32, 24),
        }
        return manager, prepared, preflight

    def test_success_publishes_bundle_and_finalizes_sqlite_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager, prepared, preflight = self._prepared(root)
            engine = _Engine(root)
            thread = TrainingThread(
                engine,
                preflight,
                ["Head"],
                ["Head"],
                epochs=1,
                batch_size=1,
                train_segmenter=False,
                training_run=prepared.run,
                model_output_root=engine.weights_dir,
            )
            thread.run()
            record = prepared.run.recorder.load(prepared.run.run_id)
            self.assertEqual(record["status"], "succeeded")
            roles = {item["role"] for item in record["artifacts"]}
            self.assertIn("output_weights", roles)
            self.assertIn("training_report", roles)
            publication = json.loads(
                (
                    Path(engine.weights_dir)
                    / "training_runs"
                    / prepared.run.run_id
                    / "publication.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(publication["status"], "active")

            model_view = MainWindowModelManagementMixin.__new__(
                MainWindowModelManagementMixin
            )
            model_view.engine = engine
            model_view.project = manager
            discovered = model_view._verified_managed_parent_weights()
            self.assertEqual(len(discovered["locator"]), 1)
            self.assertEqual(
                discovered["locator"][0]["run_id"], prepared.run.run_id
            )

            locator_path = (
                Path(engine.weights_dir)
                / Path(discovered["locator"][0]["relative_path"])
            )
            locator_path.write_bytes(b"tampered")
            self.assertEqual(
                model_view._verified_managed_parent_weights()["locator"], []
            )

            training_view = MainWindowTrainingMixin.__new__(
                MainWindowTrainingMixin
            )
            training_view.project = manager
            training_view.current_lang = "en"
            _recorder, note_store = training_view._training_run_stores()
            immutable_before = prepared.run.recorder.load(prepared.run.run_id)
            note_store.save(
                prepared.run.run_id,
                purpose="Compare parent model settings",
                importance="Key run",
                conclusion="Keep for later comparison",
            )
            rows = training_view._discover_training_run_records()
            run_row = next(
                item for item in rows if item["run_id"] == prepared.run.run_id
            )
            self.assertEqual(run_row["status_label"], "succeeded")
            self.assertEqual(run_row["note_label"], "Key run")
            immutable_after = prepared.run.recorder.load(prepared.run.run_id)
            self.assertEqual(
                immutable_after["effective_config"],
                immutable_before["effective_config"],
            )
            self.assertEqual(
                immutable_after["integrity_manifest"],
                immutable_before["integrity_manifest"],
            )

    def test_training_exception_finalizes_failed_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager, prepared, preflight = self._prepared(root)
            engine = _Engine(root, fail=True)
            thread = TrainingThread(
                engine,
                preflight,
                ["Head"],
                ["Head"],
                epochs=1,
                batch_size=1,
                train_segmenter=False,
                training_run=prepared.run,
                model_output_root=engine.weights_dir,
            )
            thread.run()
            record = prepared.run.recorder.load(prepared.run.run_id)
            self.assertEqual(record["status"], "failed")
            self.assertFalse(
                (Path(engine.weights_dir) / "training_runs" / prepared.run.run_id).exists()
            )

            retry = prepare_2d_training_run(
                manager,
                runs_root=root / "runs",
                entrypoint="builtin_locator_sam",
                effective_config=record["effective_config"],
                backend=record["backend"],
                include_parts=False,
                retry_of=prepared.run.run_id,
            )
            retry_record = retry.run.recorder.load(retry.run.run_id)
            self.assertEqual(retry_record["retry_of"], prepared.run.run_id)
            retry.run.cancel(stage="test_cleanup")


if __name__ == "__main__":
    unittest.main()
