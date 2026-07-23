import json
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from AntSleap.core.file_integrity import QUICK_FILE_ALGORITHM
from AntSleap.core.safe_io import atomic_write_json
from AntSleap.core.integrity_manifest_service import (
    IntegrityManifestService,
    build_file_entry,
)
from AntSleap.core.training_run_recorder import (
    IncompleteSuccessfulRun,
    InvalidRunTransition,
    TerminalRunImmutable,
    TrainingRunRecordError,
    TrainingRunRecorder,
    UnsafeRunFact,
    utc_now,
    validate_split_assignments,
)


class TrainingRunRecorderTests(unittest.TestCase):
    def _make_run(self, root):
        recorder = TrainingRunRecorder(root, recover_on_startup=False)
        return recorder, recorder.create_pending(
            "unit_test",
            dataset_ref={
                "dataset_id": "dataset_1",
                "data_version_id": "data_v1",
                "trusted_label_policy": "verified_external_truth",
                "source_kind": "verified_external",
                "trusted_source_ref": "trusted_source_1",
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
            },
            backend={
                "backend_id": "test_backend",
                "backend_version": "1.0",
                "adapter_id": "test_adapter",
                "adapter_version": "1.0",
            },
        )

    def _write_manifests(self, run, *, extra_files=()):
        integrity_path = Path(run.run_dir) / "integrity_manifest.json"
        entries = []
        for file_id, role in (
            ("image_1", "training_image"),
            ("truth_1", "manual_truth"),
            ("image_2", "training_image"),
            ("truth_2", "manual_truth"),
        ):
            relative = f"inputs/{file_id}.bin"
            target = Path(run.run_dir) / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(file_id.encode("ascii"))
            entries.append(
                build_file_entry(
                    file_id,
                    role,
                    "run_root",
                    relative,
                    "data_v1",
                )
            )
        for file_id, role, algorithm in extra_files:
            relative = f"inputs/{file_id}.bin"
            target = Path(run.run_dir) / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(file_id.encode("ascii"))
            entries.append(
                build_file_entry(
                    file_id,
                    role,
                    "run_root",
                    relative,
                    "data_v1",
                    algorithm=algorithm,
                )
            )
        integrity_service = IntegrityManifestService(
            integrity_path, {"run_root": run.run_dir}
        )
        integrity_service.create_manifest(run.run_id, entries)
        integrity_service.capture_expected_fingerprints()
        integrity_service.verify_manifest()
        split_path = Path(run.run_dir) / "split_manifest.json"
        stamp = utc_now()
        atomic_write_json(
            split_path,
            {
                "schema_version": "taxamask_training_split_v1",
                "split_id": "split_1",
                "run_id": run.run_id,
                "status": "verified",
                "created_at": stamp,
                "started_at": stamp,
                "finished_at": stamp,
                "dataset_id": "dataset_1",
                "strategy": {
                    "name": "group_holdout",
                    "version": "v1",
                    "seed": 42,
                    "validation_ratio": 0.5,
                },
                "assignments": [
                    {
                        "sample_id": "sample_1",
                        "partition": "train",
                        "group_id": "specimen_1",
                        "input_file_ids": ["image_1", "truth_1"],
                    },
                    {
                        "sample_id": "sample_2",
                        "partition": "validation",
                        "group_id": "specimen_2",
                        "input_file_ids": ["image_2", "truth_2"],
                    },
                ],
                "error": None,
            },
        )
        run.attach_integrity_manifest(integrity_path)
        run.attach_split_manifest(split_path)

    def test_id_has_utc_microseconds_and_random_component_and_directory_is_unique(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            recorder = TrainingRunRecorder(tmp_dir, recover_on_startup=False)
            first = recorder.create_pending("first")
            second = recorder.create_pending("second")
            pattern = r"^train_\d{8}T\d{12}Z_[0-9a-f]{8}$"
            self.assertRegex(first.run_id, pattern)
            self.assertRegex(second.run_id, pattern)
            self.assertNotEqual(first.run_id, second.run_id)
            self.assertTrue(Path(first.run_dir).is_dir())
            self.assertTrue(Path(second.run_dir).is_dir())
            first.cancel()
            second.cancel()

    def test_state_machine_and_terminal_record_are_immutable(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            _recorder, run = self._make_run(tmp_dir)
            self._write_manifests(run)
            run.mark_running()
            run.fail(ValueError("private details"), stage="fit")
            failed = run.record
            self.assertEqual(failed["status"], "failed")
            self.assertIsNotNone(failed["finished_at"])
            self.assertEqual(failed["error"]["code"], "training_failed")
            with self.assertRaises(TerminalRunImmutable):
                run.attach_facts(project_ref={"project_id": "changed"})
            with self.assertRaises(TerminalRunImmutable):
                run.cancel()

    def test_running_requires_verified_integrity_manifest(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            _recorder, run = self._make_run(tmp_dir)
            with self.assertRaises(IncompleteSuccessfulRun):
                run.mark_running()
            self.assertEqual(run.status, "pending")
            run.cancel()

    def test_success_requires_split_config_and_output_weights_and_rechecks_hashes(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            _recorder, run = self._make_run(tmp_dir)
            self._write_manifests(run)
            weights = Path(run.run_dir) / "best.pt"
            weights.write_bytes(b"weights-v1")
            run.add_artifact(
                artifact_id="best_checkpoint",
                role="output_weights",
                path=weights,
                media_type="application/octet-stream",
            )
            run.mark_running()
            weights.write_bytes(b"weights-v2")
            with self.assertRaisesRegex(
                IncompleteSuccessfulRun, "artifact_fingerprint_mismatch"
            ):
                run.succeed()
            self.assertEqual(run.status, "running")
            run.fail(code="artifact_changed", summary="Output weights changed.")

    def test_complete_success_has_all_terminal_invariants(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            _recorder, run = self._make_run(tmp_dir)
            self._write_manifests(run)
            weights = Path(run.run_dir) / "best.pt"
            weights.write_bytes(b"weights")
            run.add_artifact(
                artifact_id="best_checkpoint",
                role="output_weights",
                path=weights,
            )
            running = run.mark_running()
            succeeded = run.succeed()
            self.assertEqual(running["status"], "running")
            self.assertIsNotNone(running["started_at"])
            self.assertEqual(succeeded["status"], "succeeded")
            self.assertIsNotNone(succeeded["finished_at"])
            self.assertIsNone(succeeded["error"])
            serialized = Path(run.record_path).read_text(encoding="utf-8")
            self.assertNotIn(str(Path(tmp_dir).resolve()), serialized)

    def test_external_run_must_resolve_effective_config_before_success(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            recorder = TrainingRunRecorder(tmp_dir, recover_on_startup=False)
            run = recorder.create_pending(
                "external_test",
                dataset_ref={
                    "dataset_id": "dataset_1",
                    "data_version_id": "data_v1",
                    "trusted_label_policy": "verified_external_truth",
                    "source_kind": "verified_external",
                    "trusted_source_ref": "trusted_source_1",
                },
                effective_config={
                    "resolution_status": "pending_external",
                    "adapter_invocation": {"adapter": "test"},
                    "persist_weights": False,
                },
                backend={
                    "backend_id": "external_test",
                    "backend_version": "1",
                    "adapter_id": "test_adapter",
                    "adapter_version": "1",
                },
            )
            self._write_manifests(run)
            run.mark_running()
            with self.assertRaisesRegex(
                IncompleteSuccessfulRun, "external_effective_config_not_resolved"
            ):
                run.succeed()

            run.resolve_external_effective_config(
                {
                    "epochs": 3,
                    "batch_size": 2,
                    "learning_rate": 0.001,
                    "weight_decay": 0.0,
                    "random_seed": 42,
                    "input_resolution": [64, 64],
                    "preprocessing": {"adapter": "test"},
                    "model": {"family": "external", "version": "1"},
                    "loss_weights": {},
                    "persist_weights": False,
                }
            )
            succeeded = run.succeed()
            self.assertEqual(succeeded["status"], "succeeded")
            self.assertEqual(
                succeeded["effective_config"]["resolution_status"], "resolved"
            )
            self.assertIn(
                "resolved_effective_config",
                {item["artifact_id"] for item in succeeded["artifacts"]},
            )

    def test_sqlite_ledger_is_authority_over_json_projection(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            recorder = TrainingRunRecorder(tmp_dir, recover_on_startup=False)
            run = recorder.create_pending("authority_test")
            Path(run.record_path).write_text(
                '{"status":"succeeded","api_key":"must-not-load"}',
                encoding="utf-8",
            )
            self.assertEqual(recorder.load(run.run_id)["status"], "pending")
            run.cancel()
            projection = json.loads(Path(run.record_path).read_text(encoding="utf-8"))
            self.assertEqual(projection["status"], "cancelled")
            self.assertNotIn("api_key", projection)
            connection = sqlite3.connect(recorder.database_path)
            try:
                row = connection.execute(
                    "SELECT status, record_json FROM training_runs WHERE run_id = ?",
                    (run.run_id,),
                ).fetchone()
            finally:
                connection.close()
            self.assertEqual(row[0], "cancelled")
            self.assertEqual(json.loads(row[1])["run_id"], run.run_id)

    def test_recovery_uses_sqlite_when_projection_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            recorder = TrainingRunRecorder(tmp_dir, recover_on_startup=False)
            run = recorder.create_pending("recovery_test")
            run_id = run.run_id
            projection_path = Path(run.record_path)
            run.close()
            projection_path.unlink()
            recovered = TrainingRunRecorder(tmp_dir)
            self.assertIn(run_id, recovered.startup_recovery_report["interrupted"])
            self.assertEqual(recovered.load(run_id)["status"], "interrupted")
            self.assertTrue(projection_path.is_file())

    def test_custom_project_database_is_authoritative_ledger(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            runs_root = Path(tmp_dir) / "runs"
            project_database = Path(tmp_dir) / "project.sqlite"
            recorder = TrainingRunRecorder(
                runs_root,
                database_path=project_database,
                recover_on_startup=False,
            )
            run = recorder.create_pending("project_database_test")
            run.cancel()
            self.assertTrue(project_database.is_file())
            self.assertFalse((runs_root / "training_runs.sqlite").exists())
            connection = sqlite3.connect(project_database)
            try:
                status = connection.execute(
                    "SELECT status FROM training_runs WHERE run_id = ?",
                    (run.run_id,),
                ).fetchone()[0]
                with self.assertRaises(sqlite3.IntegrityError):
                    with connection:
                        connection.execute(
                            "UPDATE training_runs SET status = 'pending' WHERE run_id = ?",
                            (run.run_id,),
                        )
            finally:
                connection.close()
            self.assertEqual(status, "cancelled")

    def test_source_volume_quick_fingerprint_can_succeed(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            _recorder, run = self._make_run(tmp_dir)
            self._write_manifests(
                run,
                extra_files=[
                    ("source_volume_1", "source_volume", QUICK_FILE_ALGORITHM)
                ],
            )
            weights = Path(run.run_dir) / "best.pt"
            weights.write_bytes(b"weights")
            run.add_artifact(
                artifact_id="best_checkpoint",
                role="output_weights",
                path=weights,
            )
            run.mark_running()
            succeeded = run.succeed()
            self.assertEqual(succeeded["status"], "succeeded")

    def test_protected_truth_quick_fingerprint_is_defensively_rejected(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            _recorder, run = self._make_run(tmp_dir)
            integrity_payload = {
                "files": [
                    {
                        "role": "manual_truth",
                        "hash_algorithm": QUICK_FILE_ALGORITHM,
                    }
                ]
            }
            with patch.object(run, "_validate_dataset_policy"), patch.object(
                run,
                "_validate_integrity_manifest",
                return_value=integrity_payload,
            ):
                with self.assertRaisesRegex(
                    IncompleteSuccessfulRun,
                    "protected_training_input_quick_fingerprint",
                ):
                    run._validate_success(run.record)
            run.cancel()

    def test_success_without_persisted_weights_requires_a_report_artifact(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            _recorder, run = self._make_run(tmp_dir)
            run.attach_facts(effective_config={"persist_weights": False})
            self._write_manifests(run)
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

    def test_success_without_persisted_weights_still_requires_an_artifact(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            _recorder, run = self._make_run(tmp_dir)
            run.attach_facts(effective_config={"persist_weights": False})
            self._write_manifests(run)
            run.mark_running()
            with self.assertRaisesRegex(
                IncompleteSuccessfulRun, "training_artifacts_missing"
            ):
                run.succeed()
            run.fail(code="artifact_missing", summary="No report was produced.")

    def test_missing_persist_weights_keeps_output_weight_requirement(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            _recorder, run = self._make_run(tmp_dir)
            self._write_manifests(run)
            report_path = Path(run.run_dir) / "report.json"
            report_path.write_text('{"status":"passed"}', encoding="utf-8")
            run.add_artifact(
                artifact_id="training_report",
                role="training_report",
                path=report_path,
            )
            run.mark_running()
            with self.assertRaisesRegex(
                IncompleteSuccessfulRun, "output_weights_artifact_missing"
            ):
                run.succeed()
            run.fail(code="weights_missing", summary="No weights were produced.")

    def test_persist_weights_must_be_boolean(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            _recorder, run = self._make_run(tmp_dir)
            run.attach_facts(effective_config={"persist_weights": "false"})
            self._write_manifests(run)
            with self.assertRaisesRegex(
                IncompleteSuccessfulRun,
                "effective_config_persist_weights_invalid",
            ):
                run.mark_running()
            run.cancel()

    def test_mark_running_rechecks_real_inputs_and_preserves_mismatch_record(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            _recorder, run = self._make_run(tmp_dir)
            self._write_manifests(run)
            (Path(run.run_dir) / "inputs" / "truth_1.bin").write_bytes(b"changed")
            with self.assertRaisesRegex(IncompleteSuccessfulRun, "not_verified:mismatch"):
                run.mark_running()
            record = run.record
            self.assertEqual(record["status"], "pending")
            recheck_path = Path(run.run_dir) / record["integrity_manifest"]["relative_path"]
            self.assertEqual(json.loads(recheck_path.read_text(encoding="utf-8"))["status"], "mismatch")
            run.fail(code="integrity_mismatch", summary="Input changed.")

    def test_running_freezes_all_facts_after_actual_config_is_attached(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            _recorder, run = self._make_run(tmp_dir)
            self._write_manifests(run)
            updated = run.attach_facts(effective_config={"epochs": 2})
            self.assertEqual(updated["effective_config"]["epochs"], 2)
            run.mark_running()
            with self.assertRaisesRegex(InvalidRunTransition, "running_fact_frozen"):
                run.attach_facts(dataset_ref={"data_version_id": "changed"})
            with self.assertRaisesRegex(InvalidRunTransition, "running_fact_frozen"):
                run.attach_facts(effective_config={"epochs": 3})
            with self.assertRaisesRegex(InvalidRunTransition, "running_fact_frozen"):
                run.attach_facts(backend={"backend_version": "2.0"})
            run.cancel()

    def test_source_switch_replaces_refs_and_external_rejects_project_residue(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            recorder = TrainingRunRecorder(tmp_dir, recover_on_startup=False)
            run = recorder.create_pending(
                "source_switch",
                project_ref={
                    "project_kind": "taxamask_2d",
                    "project_id": "project_1",
                    "project_data_version_id": "project_v1",
                },
                dataset_ref={
                    "dataset_id": "dataset_1",
                    "data_version_id": "data_v1",
                    "trusted_label_policy": "manual_truth_only",
                    "source_kind": "project",
                },
            )
            switched = run.attach_facts(
                project_ref={},
                dataset_ref={
                    "dataset_id": "dataset_1",
                    "data_version_id": "data_v1",
                    "trusted_label_policy": "verified_external_truth",
                    "source_kind": "verified_external",
                    "trusted_source_ref": "trusted_source_1",
                },
            )
            self.assertEqual(switched["project_ref"], {})
            run.attach_facts(
                project_ref={
                    "project_kind": "taxamask_2d",
                    "project_id": "residue",
                    "project_data_version_id": "project_v1",
                }
            )
            with self.assertRaisesRegex(IncompleteSuccessfulRun, "must_be_empty"):
                run.mark_running()
            run.cancel()

    def test_external_artifact_is_reverified_without_storing_its_path(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            _recorder, run = self._make_run(tmp_dir)
            self._write_manifests(run)
            external_weights = Path(tmp_dir) / "external-best.pt"
            external_weights.write_bytes(b"external-weights")
            artifact = run.add_external_artifact(
                artifact_id="external_checkpoint",
                role="output_weights",
                path=external_weights,
                external_location_ref="location_ref_1",
            )
            run.mark_running()
            succeeded = run.succeed()
            self.assertEqual(succeeded["status"], "succeeded")
            self.assertEqual(artifact["entry_kind"], "external_reference")
            self.assertNotIn("path_base", artifact)
            self.assertNotIn("relative_path", artifact)
            self.assertNotIn(str(external_weights), Path(run.record_path).read_text(encoding="utf-8"))

    def test_external_directory_artifact_is_tree_hashed_and_reverified(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            _recorder, run = self._make_run(tmp_dir)
            self._write_manifests(run)
            external_model = Path(tmp_dir) / "external-model"
            external_model.mkdir()
            (external_model / "checkpoint.bin").write_bytes(b"directory-checkpoint")

            artifact = run.add_external_artifact(
                artifact_id="external_checkpoint_dir",
                role="output_weights",
                path=external_model,
                external_location_ref="location_ref_dir",
            )
            run.mark_running()
            succeeded = run.succeed()

            self.assertEqual(succeeded["status"], "succeeded")
            self.assertEqual(artifact["entry_kind"], "external_reference")
            self.assertEqual(artifact["hash_algorithm"], "sha256-tree-v1")
            archived = Path(run.record_path).read_text(encoding="utf-8")
            self.assertNotIn(str(external_model), archived)

    def test_external_directory_symlink_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "external-target"
            target.mkdir()
            link = Path(tmp_dir) / "external-link"
            try:
                link.symlink_to(target, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("This workstation cannot create directory symlinks")

            _recorder, run = self._make_run(tmp_dir)
            try:
                with self.assertRaisesRegex(UnsafeRunFact, "filesystem_link_not_allowed"):
                    run.register_external_location("location_ref_link", link)
            finally:
                run.cancel()

    def test_context_converges_exception_without_traceback_or_path(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            recorder = TrainingRunRecorder(tmp_dir, recover_on_startup=False)
            with self.assertRaises(RuntimeError):
                with recorder.create_pending("context_test") as run:
                    run_id = run.run_id
                    raise RuntimeError(f"failed at {tmp_dir}/private.txt")
            record = recorder.load(run_id)
            self.assertEqual(record["status"], "failed")
            self.assertEqual(record["error"]["summary"], "Training failed with RuntimeError.")
            self.assertNotIn(tmp_dir, json.dumps(record))

    def test_context_without_terminal_result_becomes_interrupted(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            recorder = TrainingRunRecorder(tmp_dir, recover_on_startup=False)
            with recorder.create_pending("context_test") as run:
                run_id = run.run_id
            self.assertEqual(recorder.load(run_id)["status"], "interrupted")

    def test_startup_recovery_skips_active_lock_then_recovers_released_run(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            recorder, run = self._make_run(tmp_dir)
            observer = TrainingRunRecorder(tmp_dir, recover_on_startup=True)
            self.assertIn(run.run_id, observer.startup_recovery_report["active"])
            self.assertEqual(run.status, "pending")
            run.close()
            report = observer.recover_interrupted_runs()
            self.assertIn(run.run_id, report["interrupted"])
            self.assertEqual(observer.load(run.run_id)["status"], "interrupted")

    def test_released_pending_handle_cannot_write_without_activity_lock(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            _recorder, run = self._make_run(tmp_dir)
            run.close()
            with self.assertRaisesRegex(TrainingRunRecordError, "run_handle_closed"):
                run.attach_facts(project_ref={"project_id": "must_not_write"})
            with self.assertRaisesRegex(TrainingRunRecordError, "run_handle_closed"):
                run.mark_running()

    def test_split_group_leakage_is_rejected(self):
        assignments = [
            {
                "sample_id": "slice_1",
                "partition": "train",
                "group_id": "specimen_1",
                "input_file_ids": ["truth_1"],
            },
            {
                "sample_id": "slice_2",
                "partition": "validation",
                "group_id": "specimen_1",
                "input_file_ids": ["truth_2"],
            },
        ]
        with self.assertRaisesRegex(IncompleteSuccessfulRun, "split_group_leakage"):
            validate_split_assignments(assignments)

    def test_fact_whitelists_reject_absolute_paths_commands_and_secrets(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            recorder = TrainingRunRecorder(tmp_dir, recover_on_startup=False)
            with self.assertRaises(UnsafeRunFact):
                recorder.create_pending(
                    "unsafe",
                    facts={"effective_config": {"project_path": "C:/private/project.json"}},
                )
            run = recorder.create_pending("safe")
            try:
                with self.assertRaises(UnsafeRunFact):
                    run.attach_facts(environment={"PATH": "private"})
                with self.assertRaises(UnsafeRunFact):
                    run.attach_facts(backend={"command_line": "python train.py"})
                with self.assertRaises(UnsafeRunFact):
                    run.attach_facts(effective_config={"api_key": "secret"})
                with self.assertRaisesRegex(UnsafeRunFact, "secret_value_not_allowed"):
                    run.attach_facts(
                        effective_config={"comment": "Bearer abcdefghijklmnop"}
                    )
                private_paths = (
                    "See(C:/Users/researcher/private.txt)",
                    "训练记录（路径：C:/Users/researcher/private.txt）",
                    "训练记录：/home/researcher/private.txt",
                    "训练记录【\\\\server\\private\\weights.pt】",
                    "路径…/home/researcher/private.txt",
                    "路径·\\\\server\\private\\notes.txt",
                    "路径…C:\\Users\\researcher\\private.txt",
                    "路径_/home/researcher/private.txt",
                )
                for private_path in private_paths:
                    with self.subTest(private_path=private_path), self.assertRaisesRegex(
                        UnsafeRunFact, "absolute_path_not_allowed"
                    ):
                        run.attach_facts(
                            effective_config={"research_note": private_path}
                        )
                safe = run.attach_facts(
                    effective_config={
                        "research_note": (
                            "比较 Head/Thorax 比例（C: dorsal；样本 01-02）；"
                            "参考 https://doi.org/10.1234/example"
                        )
                    }
                )
                self.assertIn("Head/Thorax", safe["effective_config"]["research_note"])
                self.assertIn("https://doi.org", safe["effective_config"]["research_note"])
                with self.assertRaisesRegex(UnsafeRunFact, "artifacts_are_append_only"):
                    run.attach_facts(artifacts=[])
            finally:
                if run.status in {"pending", "running"}:
                    run.cancel()

    def test_error_summary_redacts_path_after_chinese_punctuation(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            recorder = TrainingRunRecorder(tmp_dir, recover_on_startup=False)
            private_summaries = (
                "训练失败（诊断位置：C:/Users/researcher/private.txt）",
                "路径…/home/researcher/private.txt",
                "路径·\\\\server\\private\\notes.txt",
                "路径…C:\\Users\\researcher\\private.txt",
                "路径_/home/researcher/private.txt",
            )
            for index, summary in enumerate(private_summaries):
                with self.subTest(summary=summary):
                    run = recorder.create_pending(f"error_privacy_{index}")
                    failed = run.fail(code="training_failed", summary=summary)
                    self.assertIn(
                        "sensitive diagnostic details were omitted",
                        failed["error"]["summary"],
                    )
            url_run = recorder.create_pending("error_privacy_url")
            url_summary = "参考 https://doi.org/10.1234/example"
            url_failed = url_run.fail(code="training_failed", summary=url_summary)
            self.assertEqual(url_failed["error"]["summary"], url_summary)

    def test_split_rejects_missing_truth_cross_partition_file_and_data_version(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            _recorder, run = self._make_run(tmp_dir)
            self._write_manifests(run)
            original_path = Path(run.run_dir) / "split_manifest.json"
            original = json.loads(original_path.read_text(encoding="utf-8"))

            no_truth = json.loads(json.dumps(original))
            no_truth["assignments"][0]["input_file_ids"] = ["image_1"]
            no_truth_path = Path(run.run_dir) / "split_no_truth.json"
            atomic_write_json(no_truth_path, no_truth)
            with self.assertRaisesRegex(IncompleteSuccessfulRun, "trusted_truth_missing"):
                run.attach_split_manifest(no_truth_path)

            leaked = json.loads(json.dumps(original))
            leaked["assignments"][1]["input_file_ids"].append("image_1")
            leaked_path = Path(run.run_dir) / "split_leaked.json"
            atomic_write_json(leaked_path, leaked)
            with self.assertRaisesRegex(IncompleteSuccessfulRun, "partition_leakage"):
                run.attach_split_manifest(leaked_path)

            run.attach_facts(
                dataset_ref={
                    "dataset_id": "dataset_1",
                    "data_version_id": "data_v2",
                    "trusted_label_policy": "verified_external_truth",
                    "source_kind": "verified_external",
                    "trusted_source_ref": "trusted_source_1",
                }
            )
            with self.assertRaisesRegex(IncompleteSuccessfulRun, "data_version_mismatch"):
                run.attach_split_manifest(original_path)
            run.cancel()

    def test_mark_running_rejects_invalid_config_and_backend_versions(self):
        invalid_updates = [
            ({"effective_config": {"epochs": 0}}, "epochs"),
            ({"effective_config": {"learning_rate": float("nan")}}, "learning_rate"),
            ({"effective_config": {"loss_weights": {"bad": -1.0}}}, "loss_weight"),
            ({"backend": {"backend_version": ""}}, "backend_version"),
        ]
        for update, code in invalid_updates:
            with self.subTest(code=code), tempfile.TemporaryDirectory() as tmp_dir:
                _recorder, run = self._make_run(tmp_dir)
                self._write_manifests(run)
                if code == "learning_rate":
                    try:
                        with self.assertRaisesRegex(UnsafeRunFact, "non_finite_number"):
                            run.attach_facts(**update)
                    finally:
                        if run.status in {"pending", "running"}:
                            run.cancel()
                    continue
                run.attach_facts(**update)
                try:
                    with self.assertRaisesRegex(IncompleteSuccessfulRun, code):
                        run.mark_running()
                finally:
                    if run.status in {"pending", "running"}:
                        run.cancel()

    def test_retry_requires_existing_unsuccessful_terminal_run(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            recorder = TrainingRunRecorder(tmp_dir, recover_on_startup=False)
            with self.assertRaises(TrainingRunRecordError):
                recorder.create_pending("retry", retry_of="train_missing")
            original = recorder.create_pending("original")
            with self.assertRaisesRegex(InvalidRunTransition, "unsuccessful_terminal"):
                recorder.create_pending("retry", retry_of=original.run_id)
            original.cancel()
            retry = recorder.create_pending("retry", retry_of=original.run_id)
            self.assertEqual(retry.record["retry_of"], original.run_id)
            retry.cancel()

    def test_project_source_requires_project_reference(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            recorder = TrainingRunRecorder(tmp_dir, recover_on_startup=False)
            run = recorder.create_pending(
                "project_entry",
                dataset_ref={
                    "dataset_id": "dataset_1",
                    "data_version_id": "data_v1",
                    "trusted_label_policy": "manual_truth_only",
                    "source_kind": "project",
                },
            )
            with self.assertRaisesRegex(IncompleteSuccessfulRun, "project_ref_incomplete"):
                run.mark_running()
            run.cancel()

    def test_artifact_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            recorder = TrainingRunRecorder(tmp_dir, recover_on_startup=False)
            run = recorder.create_pending("path_test")
            try:
                target = Path(run.run_dir) / "target.bin"
                target.write_bytes(b"x")
                link = Path(run.run_dir) / "link.bin"
                try:
                    link.symlink_to(target)
                except (OSError, NotImplementedError):
                    self.skipTest("This workstation cannot create symlinks")
                with self.assertRaisesRegex(UnsafeRunFact, "artifact_path_unsafe"):
                    run.fingerprint_artifact(
                        artifact_id="linked",
                        role="output_weights",
                        path=link,
                    )
            finally:
                if run.status in {"pending", "running"}:
                    run.cancel()

    def test_noncanonical_relative_artifact_record_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            recorder = TrainingRunRecorder(tmp_dir, recover_on_startup=False)
            run = recorder.create_pending("path_test")
            try:
                with self.assertRaisesRegex(UnsafeRunFact, "artifact_relative_path_invalid"):
                    run.attach_facts(
                        split_manifest={
                            "artifact_id": "split_manifest",
                            "role": "training_split",
                            "path_base": "run_root",
                            "relative_path": "a//b.json",
                            "entry_kind": "file",
                            "size_bytes": 1,
                            "hash_algorithm": "sha256",
                            "digest": "0" * 64,
                        }
                    )
            finally:
                if run.status in {"pending", "running"}:
                    run.cancel()

    def test_pending_can_cancel_but_cannot_succeed(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            recorder = TrainingRunRecorder(tmp_dir, recover_on_startup=False)
            run = recorder.create_pending("cancel_test")
            with self.assertRaises(InvalidRunTransition):
                run.succeed()
            cancelled = run.cancel()
            self.assertEqual(cancelled["status"], "cancelled")
            self.assertEqual(cancelled["error"]["code"], "user_cancelled")


if __name__ == "__main__":
    unittest.main()
