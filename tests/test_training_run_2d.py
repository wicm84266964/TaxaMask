import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from PIL import Image

from AntSleap.core.project import ProjectManager
from AntSleap.core.training_run_2d import (
    prepare_2d_training_run,
    prepare_blink_training_run,
)


class TrainingRun2DTests(unittest.TestCase):
    def _project(self, root):
        project_dir = root / "project"
        project_dir.mkdir()
        manager = ProjectManager()
        manager.create_project("ants", project_dir)
        manager.location_registry_database_path = root / "locations.sqlite"
        manager.project_data["taxonomy"] = ["Head"]
        manager.project_data["locator_scope"] = ["Head"]
        images_dir = project_dir / "images"
        images_dir.mkdir()
        paths = []
        for index in range(3):
            path = images_dir / f"ant_{index}.png"
            Image.new("RGB", (32, 24), color=(100 + index, 80, 60)).save(path)
            paths.append(str(path))
        manager.add_images(paths, save=True)
        for path in paths:
            manager.update_label(
                path,
                "Head",
                [[2, 2], [20, 2], [10, 18]],
                box=[2, 2, 20, 18],
                save=True,
            )
        manager.initialize_integrity_baseline()
        return manager

    def _config(self):
        return {
            "epochs": 2,
            "batch_size": 4,
            "learning_rate": 0.001,
            "weight_decay": 0.0001,
            "random_seed": 0,
            "input_resolution": [512, 512],
            "preprocessing": {"dataset_adapter": "TwoStageDataset"},
            "model": {
                "family": "AntEngine",
                "version": "1",
                "locator": "TraitRegressor",
                "parts": "disabled",
            },
            "loss_weights": {"locator": {"heatmap": 1.0, "wh": 1.0}},
        }

    def test_prepare_uses_registry_and_project_sqlite_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = self._project(root)
            prepared = prepare_2d_training_run(
                manager,
                runs_root=root / "runs",
                entrypoint="builtin_locator_sam",
                effective_config=self._config(),
                backend={
                    "backend_id": "builtin_locator_sam",
                    "backend_version": "1.0",
                    "adapter_id": "gui_training_thread",
                    "adapter_version": "1.0",
                },
                include_parts=False,
            )
            self.assertEqual(prepared.run.status, "running")
            self.assertEqual(len(prepared.locator_train_records), 2)
            self.assertEqual(len(prepared.locator_validation_records), 1)
            with closing(sqlite3.connect(manager.current_database_path)) as connection:
                row = connection.execute(
                    "SELECT status FROM training_runs WHERE run_id = ?",
                    (prepared.run.run_id,),
                ).fetchone()
            self.assertEqual(row, ("running",))
            prepared.run.fail(RuntimeError("test cleanup"), stage="test")

    def test_source_change_fails_before_running_and_leaves_failed_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = self._project(root)
            first_path = manager.project_data["images"][0]
            Image.new("RGB", (32, 24), color=(1, 2, 3)).save(first_path)
            with self.assertRaisesRegex(Exception, "source_digest_mismatch"):
                prepare_2d_training_run(
                    manager,
                    runs_root=root / "runs",
                    entrypoint="builtin_locator_sam",
                    effective_config=self._config(),
                    backend={
                        "backend_id": "builtin_locator_sam",
                        "backend_version": "1.0",
                        "adapter_id": "gui_training_thread",
                        "adapter_version": "1.0",
                    },
                    include_parts=False,
                )
            with closing(sqlite3.connect(manager.current_database_path)) as connection:
                statuses = [
                    row[0]
                    for row in connection.execute(
                        "SELECT status FROM training_runs ORDER BY created_at"
                    )
                ]
            self.assertEqual(statuses, ["failed"])

    def test_prepare_blink_uses_registered_trajectories_and_uid_split(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = self._project(root)
            manager.project_data["taxonomy"] = ["Head", "Mandible"]
            manager.save_project()
            for path in manager.project_data["images"]:
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
                    [
                        {"box": [4, 4, 18, 16]},
                        {"box": [5, 5, 15, 14]},
                    ],
                    parent_context={
                        "parent_part": "Head",
                        "parent_box": [2, 2, 20, 18],
                    },
                    save=True,
                )
            prepared = prepare_blink_training_run(
                manager,
                runs_root=root / "runs",
                entrypoint="blink_vit_b",
                target_part="Mandible",
                parent_part="Head",
                effective_config={
                    "epochs": 2,
                    "batch_size": 1,
                    "learning_rate": 0.001,
                    "weight_decay": 0.0001,
                    "random_seed": 0,
                    "input_resolution": [224, 224],
                    "preprocessing": {
                        "dataset_adapter": "BlinkTrajectoryDataset"
                    },
                    "model": {
                        "family": "MicroExpertLocator",
                        "version": "1",
                        "locator": "disabled",
                        "parts": "Mandible",
                    },
                    "loss_weights": {
                        "outer": {
                            "final": 1.0,
                            "step": 1.0,
                            "view": 1.0,
                            "consistency": 1.0,
                        }
                    },
                },
                backend={
                    "backend_id": "blink_vit_b",
                    "backend_version": "1.0",
                    "adapter_id": "blink_training_thread",
                    "adapter_version": "1.0",
                },
            )
            self.assertEqual(prepared.run.status, "running")
            self.assertEqual(len(prepared.training_records), 2)
            self.assertEqual(len(prepared.validation_records), 1)
            self.assertTrue(
                all(
                    "Mandible" in label["trajectories"]
                    for _path, label in prepared.training_records
                    + prepared.validation_records
                )
            )
            prepared.run.fail(RuntimeError("test cleanup"), stage="test")


if __name__ == "__main__":
    unittest.main()
