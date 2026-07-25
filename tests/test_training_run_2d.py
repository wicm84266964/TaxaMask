import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from AntSleap.core.project import ProjectManager
from AntSleap.core.file_integrity import compute_fingerprint
from AntSleap.core.project_integrity_registry import ProjectIntegrityRegistryError
from AntSleap.core.training_run_2d import (
    prepare_2d_training_run,
    prepare_blink_training_run,
)


class TrainingRun2DTests(unittest.TestCase):
    def _project(self, root, *, external_images=False):
        project_dir = root / "project"
        project_dir.mkdir()
        manager = ProjectManager()
        manager.create_project("ants", project_dir)
        manager.location_registry_database_path = root / "locations.sqlite"
        manager.project_data["taxonomy"] = ["Head"]
        manager.project_data["locator_scope"] = ["Head"]
        images_dir = (
            root / "external_images"
            if external_images
            else project_dir / "images"
        )
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
            with patch(
                "AntSleap.core.project_integrity_registry.compute_fingerprint",
                wraps=compute_fingerprint,
            ) as registry_fingerprint:
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
            self.assertEqual(
                registry_fingerprint.call_count,
                len(prepared.dataset["resolved_inputs"]["files"]) * 2,
            )
            self.assertNotIn("verification_batch", prepared.dataset)
            self.assertEqual(len(prepared.locator_train_records), 2)
            self.assertEqual(len(prepared.locator_validation_records), 1)
            with closing(sqlite3.connect(manager.current_database_path)) as connection:
                row = connection.execute(
                    "SELECT status FROM training_runs WHERE run_id = ?",
                    (prepared.run.run_id,),
                ).fetchone()
            self.assertEqual(row, ("running",))
            audit_path = (
                Path(prepared.run.run_dir) / "integrity_registry_receipt.json"
            )
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            all_strings = []

            def collect_strings(value):
                if isinstance(value, str):
                    all_strings.append(value)
                elif isinstance(value, list):
                    for item in value:
                        collect_strings(item)
                elif isinstance(value, dict):
                    for item in value.values():
                        collect_strings(item)

            collect_strings(audit)
            self.assertFalse(any(os.path.isabs(value) for value in all_strings))
            self.assertTrue(all(item.get("event_id") for item in audit["files"]))
            self.assertIn(
                "integrity_verification_receipt",
                {item["role"] for item in prepared.run.record["artifacts"]},
            )
            prepared.run.fail(RuntimeError("test cleanup"), stage="test")

    def test_user_cancel_during_integrity_preflight_records_cancelled_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = self._project(root)
            with self.assertRaises(ProjectIntegrityRegistryError) as raised:
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
                    cancel_check=lambda: True,
                )
            self.assertEqual(raised.exception.code, "user_cancelled")
            with closing(sqlite3.connect(manager.current_database_path)) as connection:
                row = connection.execute(
                    "SELECT status, record_json FROM training_runs"
                ).fetchone()
            record = json.loads(row[1])
            self.assertEqual(row[0], "cancelled")
            self.assertEqual(record["error"]["code"], "user_cancelled")
            self.assertEqual(record["error"]["stage"], "integrity_preflight")

    def test_source_change_fails_before_running_and_leaves_failed_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = self._project(root)
            first_path = manager.project_data["images"][0]
            Image.new("RGB", (32, 24), color=(1, 2, 3)).save(first_path)
            with self.assertRaisesRegex(Exception, "source_digest_mismatch") as raised:
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
                rows = [
                    row
                    for row in connection.execute(
                        "SELECT run_id, status FROM training_runs ORDER BY created_at"
                    )
                ]
            self.assertEqual([row[1] for row in rows], ["failed"])
            self.assertEqual(
                getattr(raised.exception, "training_run_id", None), rows[0][0]
            )

    def test_selected_scope_does_not_verify_unselected_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = self._project(root)
            selected_paths = manager.project_data["images"][:2]
            unselected_path = manager.project_data["images"][2]
            Image.new("RGB", (32, 24), color=(1, 2, 3)).save(unselected_path)
            selected_uids = [manager.get_image_uid(path) for path in selected_paths]

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
                allowed_image_uids=selected_uids,
            )

            verified_uids = {
                item["owner_key"]
                for item in prepared.dataset["resolved_inputs"]["files"]
                if item["role"] in {"source_image", "human_confirmed_label"}
            }
            self.assertEqual(verified_uids, set(selected_uids))
            self.assertNotIn(manager.get_image_uid(unselected_path), verified_uids)
            prepared.run.fail(RuntimeError("test cleanup"), stage="test")

    def test_max_samples_limits_registry_verification_scope(self):
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
                max_samples=2,
            )

            verified_pairs = [
                item
                for item in prepared.dataset["resolved_inputs"]["files"]
                if item["role"] in {"source_image", "human_confirmed_label"}
            ]
            verified_uids = {item["owner_key"] for item in verified_pairs}
            self.assertEqual(len(verified_uids), 2)
            self.assertEqual(
                [item["role"] for item in verified_pairs].count("source_image"),
                2,
            )
            self.assertEqual(
                [item["role"] for item in verified_pairs].count(
                    "human_confirmed_label"
                ),
                2,
            )
            self.assertEqual(len(prepared.dataset["locator_records"]), 2)
            prepared.run.fail(RuntimeError("test cleanup"), stage="test")

    def test_max_samples_counts_only_stage_qualified_samples(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_dir = root / "project"
            project_dir.mkdir()
            manager = ProjectManager()
            manager.create_project("stage_limit", project_dir)
            manager.location_registry_database_path = root / "locations.sqlite"
            manager.project_data["taxonomy"] = ["Head", "Mandible"]
            manager.project_data["locator_scope"] = ["Head"]
            manager._mark_sqlite_project_dirty()
            images_dir = project_dir / "images"
            images_dir.mkdir()
            paths = []
            for index in range(3):
                path = images_dir / f"ant_{index}.png"
                Image.new("RGB", (32, 24), color=(100 + index, 80, 60)).save(path)
                paths.append(str(path))
            manager.add_images(paths, save=False)
            for path in paths:
                manager.update_label(
                    path,
                    "Head",
                    [[2, 2], [20, 2], [10, 18]],
                    box=[2, 2, 20, 18],
                    save=False,
                )
            invalid_path = min(paths, key=lambda path: manager.get_image_uid(path))
            manager.delete_label(invalid_path, "Head", save=False)
            manager.update_label(
                invalid_path,
                "Mandible",
                [[5, 5], [15, 5], [10, 14]],
                box=[5, 5, 15, 14],
                save=False,
            )
            manager.save_project()
            manager.initialize_integrity_baseline()

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
                include_parts=True,
                max_samples=2,
            )
            selected_uids = {
                item["owner_key"]
                for item in prepared.dataset["resolved_inputs"]["files"]
                if item["role"] == "source_image"
            }
            self.assertEqual(len(selected_uids), 2)
            self.assertNotIn(manager.get_image_uid(invalid_path), selected_uids)
            self.assertEqual(len(prepared.parts_train_records) + len(prepared.parts_validation_records), 2)
            prepared.run.fail(RuntimeError("test cleanup"), stage="test")

    def test_selected_scope_ignores_missing_unselected_opaque_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = self._project(root, external_images=True)
            selected_paths = manager.project_data["images"][:2]
            unselected_path = Path(manager.project_data["images"][2])
            selected_uids = [manager.get_image_uid(path) for path in selected_paths]
            unselected_uid = manager.get_image_uid(unselected_path)
            unselected_path.unlink()

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
                allowed_image_uids=selected_uids,
            )

            verified_uids = {
                item["owner_key"]
                for item in prepared.dataset["resolved_inputs"]["files"]
                if item["role"] in {"source_image", "human_confirmed_label"}
            }
            self.assertEqual(verified_uids, set(selected_uids))
            self.assertNotIn(unselected_uid, verified_uids)
            prepared.run.fail(RuntimeError("test cleanup"), stage="test")

    def test_success_rechecks_inputs_before_weight_activation(self):
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
            Image.new("RGB", (32, 24), color=(1, 2, 3)).save(
                manager.project_data["images"][0]
            )

            try:
                with self.assertRaisesRegex(
                    ProjectIntegrityRegistryError,
                    "registry_verified_source_changed",
                ):
                    prepared.run.succeed()
                self.assertEqual(prepared.run.status, "running")
            finally:
                if prepared.run.status == "running":
                    prepared.run.fail(RuntimeError("test cleanup"), stage="test")

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
            with patch(
                "AntSleap.core.project_integrity_registry.compute_fingerprint",
                wraps=compute_fingerprint,
            ) as registry_fingerprint:
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
            self.assertEqual(
                registry_fingerprint.call_count,
                len(prepared.dataset["resolved_inputs"]["files"]) * 2,
            )
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
