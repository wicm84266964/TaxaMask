import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from AntSleap.core.file_integrity import (
    FULL_FILE_ALGORITHM,
    QUICK_FILE_ALGORITHM,
    compute_fingerprint,
)
from AntSleap.core.project_integrity_registry import (
    BASELINE_SNAPSHOT_SCHEMA_VERSION,
    LABEL_SNAPSHOT_SCHEMA_ID,
    ProjectIntegrityRegistryError,
    canonical_snapshot_text,
    commit_project_data_version,
    create_operation,
    get_registry_version_snapshot,
    get_training_baseline_snapshot,
    register_project_baseline,
    registry_state,
    relocate_project_asset,
    resolve_training_baseline_inputs,
    update_operation_status,
    validate_project_integrity_registry_schema,
)
from AntSleap.core.project_sqlite_schema import (
    PROJECT_2D_SCHEMA_NAME,
    PROJECT_2D_SCHEMA_VERSION,
    create_2d_project_database,
    initialize_2d_project_schema,
)
from AntSleap.core.project_traceability import (
    PROJECT_KIND_2D,
    ensure_project_traceability,
    new_project_traceability,
)
from AntSleap.core.sqlite_storage import connect_sqlite_database_readonly


class ProjectIntegrityRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project_root = self.root / "project"
        self.run_root = self.root / "run"
        self.model_root = self.root / "models"
        self.project_root.mkdir()
        self.run_root.mkdir()
        self.model_root.mkdir()
        self.db_path = self.project_root / "project.sqlite"
        self.connection = create_2d_project_database(self.db_path)
        self.project_id = "project_2d_test"
        self.version_id = "project_data_v1"

    def tearDown(self):
        self.connection.close()
        self.temp.cleanup()

    def _write(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def _baseline_entries(self, *, include_weight=False):
        image_path = self._write(self.project_root / "images" / "a.png", b"image-v1")
        label_payload = {
            "schema_version": LABEL_SNAPSHOT_SCHEMA_ID,
            "image_uid": "image_a",
            "parts": {"Head": [[0.0, 0.0], [2.0, 0.0], [1.0, 2.0]]},
        }
        entries = [
            {
                "owner_kind": "image",
                "owner_key": "image_a",
                "role": "source_image",
                "media_type": "image/png",
                "expected": compute_fingerprint(image_path, FULL_FILE_ALGORITHM),
                "location": {
                    "location_kind": "managed_relative",
                    "path_base": "project_root",
                    "relative_path": "images/a.png",
                },
            },
            {
                "owner_kind": "image",
                "owner_key": "image_a",
                "role": "human_confirmed_label",
                "media_type": "application/json",
                "schema_id": LABEL_SNAPSHOT_SCHEMA_ID,
                "snapshot_text": canonical_snapshot_text(label_payload),
            },
        ]
        if include_weight:
            weight_path = self._write(self.model_root / "sam_b.pt", b"weights-v1")
            entries.append(
                {
                    "owner_kind": "model_input",
                    "owner_key": "sam_b",
                    "role": "initial_weights",
                    "media_type": "application/octet-stream",
                    "expected": compute_fingerprint(weight_path, FULL_FILE_ALGORITHM),
                    "location": {
                        "location_kind": "managed_relative",
                        "path_base": "managed_model_root",
                        "relative_path": "sam_b.pt",
                    },
                }
            )
        return entries

    def _register(self, *, include_weight=False):
        with self.connection:
            return register_project_baseline(
                self.connection,
                project_kind=PROJECT_KIND_2D,
                project_id=self.project_id,
                data_version_id=self.version_id,
                entries=self._baseline_entries(include_weight=include_weight),
            )

    def test_new_database_is_v2_but_registry_remains_uninitialized(self):
        state = registry_state(self.connection)
        self.assertEqual(PROJECT_2D_SCHEMA_VERSION, 2)
        self.assertEqual(state["status"], "uninitialized")
        self.assertEqual(state["current_data_version_id"], "")
        with self.assertRaises(ProjectIntegrityRegistryError) as raised:
            get_training_baseline_snapshot(self.db_path)
        self.assertEqual(raised.exception.code, "integrity_baseline_missing")

    def test_schema_backfills_stable_unique_image_uid_without_hashing(self):
        self.connection.execute("DROP INDEX idx_images_image_uid_unique")
        self.connection.execute(
            "INSERT INTO images (image_uid, path, filename) VALUES ('', 'a.png', 'a.png')"
        )
        self.connection.execute(
            "INSERT INTO images (image_uid, path, filename) VALUES ('', 'b.png', 'b.png')"
        )
        self.connection.execute(
            "DELETE FROM schema_migrations WHERE schema_name = ? AND version = 2",
            (PROJECT_2D_SCHEMA_NAME,),
        )
        self.connection.commit()

        initialize_2d_project_schema(self.connection)
        first = self.connection.execute(
            "SELECT image_uid FROM images ORDER BY id"
        ).fetchall()
        initialize_2d_project_schema(self.connection)
        second = self.connection.execute(
            "SELECT image_uid FROM images ORDER BY id"
        ).fetchall()

        self.assertEqual(first, second)
        self.assertEqual(len({row[0] for row in first}), 2)
        self.assertTrue(all(str(row[0]).startswith("image_") for row in first))
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM integrity_asset_revisions").fetchone()[0],
            0,
        )

    def test_traceability_rejects_new_invalid_id_and_repairs_legacy_ids(self):
        with self.assertRaisesRegex(ValueError, "invalid_project_id"):
            new_project_traceability(PROJECT_KIND_2D, project_id="bad id")
        payload = {"project_id": "C:/private/project", "project_data_version_id": "bad id"}
        self.assertTrue(ensure_project_traceability(payload, PROJECT_KIND_2D))
        self.assertNotIn(":", payload["project_id"])
        self.assertNotIn(" ", payload["project_data_version_id"])

    def test_snapshot_is_path_safe_and_uses_location_xor_materializer(self):
        self._register(include_weight=True)
        snapshot = get_training_baseline_snapshot(self.db_path)

        self.assertEqual(snapshot["schema_version"], BASELINE_SNAPSHOT_SCHEMA_VERSION)
        self.assertEqual(snapshot["status"], "registered")
        self.assertEqual(len(snapshot["files"]), 3)
        for entry in snapshot["files"]:
            self.assertNotEqual("location" in entry, "materializer" in entry)
        serialized = json.dumps(snapshot, ensure_ascii=False)
        self.assertNotIn(str(self.root), serialized)
        weight = next(item for item in snapshot["files"] if item["role"] == "initial_weights")
        self.assertEqual(weight["location"]["path_base"], "managed_model_root")

    def test_resolver_verifies_source_and_materializes_exact_snapshot(self):
        self._register(include_weight=True)
        snapshot = get_training_baseline_snapshot(self.db_path)
        resolved = resolve_training_baseline_inputs(
            self.db_path,
            snapshot,
            project_root=self.project_root,
            run_root=self.run_root,
            managed_roots={"managed_model_root": self.model_root},
        )

        self.assertEqual(resolved["status"], "verified")
        label = next(
            item for item in resolved["files"] if item["role"] == "human_confirmed_label"
        )
        self.assertTrue(label["materializer"]["materialized"])
        materialized = Path(label["materializer"]["runtime_path"])
        self.assertTrue(materialized.is_relative_to(self.run_root))
        fingerprint = compute_fingerprint(materialized, FULL_FILE_ALGORITHM)
        self.assertEqual(fingerprint["digest"], label["digest"])
        self.assertEqual(fingerprint["size_bytes"], label["size_bytes"])

    def test_cancelled_verification_records_incomplete_and_retry_can_verify(self):
        self._register()
        snapshot = get_training_baseline_snapshot(self.db_path)

        with self.assertRaises(ProjectIntegrityRegistryError) as raised:
            resolve_training_baseline_inputs(
                self.db_path,
                snapshot,
                project_root=self.project_root,
                run_root=self.run_root,
                cancel_check=lambda: True,
            )
        self.assertEqual(raised.exception.code, "user_cancelled")
        row = self.connection.execute(
            """
            SELECT status, error_code
            FROM integrity_verification_events
            ORDER BY verified_at DESC, event_id DESC
            LIMIT 1
            """
        ).fetchone()
        self.assertEqual(tuple(row), ("incomplete", "user_cancelled"))

        resolved = resolve_training_baseline_inputs(
            self.db_path,
            snapshot,
            project_root=self.project_root,
            run_root=self.run_root,
        )
        self.assertEqual(resolved["status"], "verified")

    def test_label_version_change_never_rebaselines_modified_source_image(self):
        baseline = self._register()
        image_entry = next(item for item in baseline["files"] if item["role"] == "source_image")
        expected_digest = image_entry["digest"]
        self._write(self.project_root / "images" / "a.png", b"externally-modified")

        changed_label = canonical_snapshot_text(
            {
                "schema_version": LABEL_SNAPSHOT_SCHEMA_ID,
                "image_uid": "image_a",
                "parts": {"Head": [[0.0, 0.0], [3.0, 0.0], [1.0, 3.0]]},
            }
        )
        with self.connection:
            result = commit_project_data_version(
                self.connection,
                project_id=self.project_id,
                parent_data_version_id=self.version_id,
                new_data_version_id="project_data_v2",
                changes=[
                    {
                        "owner_kind": "image",
                        "owner_key": "image_a",
                        "role": "human_confirmed_label",
                        "schema_id": LABEL_SNAPSHOT_SCHEMA_ID,
                        "snapshot_text": changed_label,
                    }
                ],
                reason="trusted_label_changed",
            )
        self.assertTrue(result["changed"])
        new_snapshot = get_registry_version_snapshot(self.connection, "project_data_v2")
        new_image = next(item for item in new_snapshot["files"] if item["role"] == "source_image")
        self.assertEqual(new_image["digest"], expected_digest)
        with self.assertRaises(ProjectIntegrityRegistryError) as raised:
            resolve_training_baseline_inputs(
                self.db_path,
                new_snapshot,
                project_root=self.project_root,
                run_root=self.run_root,
            )
        self.assertEqual(raised.exception.code, "source_digest_mismatch")

    def test_identical_revision_does_not_create_child_version(self):
        baseline = self._register()
        label = next(item for item in baseline["files"] if item["role"] == "human_confirmed_label")
        row = self.connection.execute(
            "SELECT snapshot_text FROM integrity_asset_revisions WHERE revision_id = ?",
            (label["revision_id"],),
        ).fetchone()
        with self.connection:
            result = commit_project_data_version(
                self.connection,
                project_id=self.project_id,
                parent_data_version_id=self.version_id,
                new_data_version_id="project_data_unused",
                changes=[
                    {
                        "owner_kind": "image",
                        "owner_key": "image_a",
                        "role": "human_confirmed_label",
                        "schema_id": LABEL_SNAPSHOT_SCHEMA_ID,
                        "snapshot_text": row[0],
                    }
                ],
                reason="no_change",
            )
        self.assertFalse(result["changed"])
        self.assertIsNone(
            self.connection.execute(
                "SELECT 1 FROM integrity_data_versions WHERE data_version_id = 'project_data_unused'"
            ).fetchone()
        )

    def test_transaction_failure_rolls_back_version_revision_and_head(self):
        self._register()
        with self.assertRaisesRegex(RuntimeError, "forced_failure"):
            with self.connection:
                commit_project_data_version(
                    self.connection,
                    project_id=self.project_id,
                    parent_data_version_id=self.version_id,
                    new_data_version_id="project_data_rollback",
                    changes=[
                        {
                            "owner_kind": "image",
                            "owner_key": "image_a",
                            "role": "human_confirmed_label",
                            "schema_id": LABEL_SNAPSHOT_SCHEMA_ID,
                            "snapshot_text": canonical_snapshot_text(
                                {
                                    "schema_version": LABEL_SNAPSHOT_SCHEMA_ID,
                                    "image_uid": "image_a",
                                    "parts": {},
                                }
                            ),
                        }
                    ],
                    reason="rollback_test",
                )
                raise RuntimeError("forced_failure")
        self.assertIsNone(
            self.connection.execute(
                "SELECT 1 FROM integrity_data_versions WHERE data_version_id = 'project_data_rollback'"
            ).fetchone()
        )
        self.assertEqual(registry_state(self.connection)["current_data_version_id"], self.version_id)

    def test_revision_rows_are_immutable(self):
        snapshot = self._register()
        revision_id = snapshot["files"][0]["revision_id"]
        with self.assertRaises(sqlite3.IntegrityError):
            with self.connection:
                self.connection.execute(
                    "UPDATE integrity_asset_revisions SET digest = ? WHERE revision_id = ?",
                    ("0" * 64, revision_id),
                )

    def test_registry_records_never_store_runtime_absolute_paths(self):
        self._register(include_weight=True)
        create_operation(
            self.connection,
            "materialize_snapshot",
            target_location_ref="run_snapshot_target",
        )
        self.connection.commit()
        for table in (
            "integrity_registry_state",
            "integrity_data_versions",
            "integrity_assets",
            "integrity_asset_revisions",
            "integrity_version_changes",
            "integrity_asset_heads",
            "integrity_locations",
            "integrity_operations",
        ):
            rows = self.connection.execute(f"SELECT * FROM {table}").fetchall()
            self.assertNotIn(str(self.root), json.dumps(rows, ensure_ascii=False))

    def test_operation_rejects_absolute_location_reference(self):
        with self.assertRaises(ProjectIntegrityRegistryError) as raised:
            create_operation(
                self.connection,
                "materialize_snapshot",
                target_location_ref="C:/private/target",
            )
        self.assertEqual(raised.exception.code, "invalid_operation_location_ref")

    def test_operation_allows_declared_transitions_and_persists_error(self):
        with self.connection:
            completed = create_operation(self.connection, "materialize_snapshot")
            self.assertEqual(
                update_operation_status(self.connection, completed, "fs_applied"),
                "fs_applied",
            )
            self.assertEqual(
                update_operation_status(self.connection, completed, "db_committed"),
                "db_committed",
            )
            self.assertEqual(
                update_operation_status(self.connection, completed, "finalized"),
                "finalized",
            )

            rolled_back = create_operation(self.connection, "restore_backup")
            error = {"code": "filesystem_failed", "summary": "Recovery is required."}
            self.assertEqual(
                update_operation_status(
                    self.connection, rolled_back, "needs_attention", error=error
                ),
                "needs_attention",
            )
            stored_error = self.connection.execute(
                "SELECT error_json FROM integrity_operations WHERE operation_id = ?",
                (rolled_back,),
            ).fetchone()[0]
            self.assertEqual(json.loads(stored_error), error)
            self.assertEqual(
                update_operation_status(
                    self.connection, rolled_back, "rolled_back", error=error
                ),
                "rolled_back",
            )

    def test_operation_rejects_undeclared_transition_without_mutation(self):
        with self.connection:
            operation_id = create_operation(self.connection, "materialize_snapshot")
        for rejected in ("finalized",):
            with self.subTest(current="prepared", rejected=rejected):
                with self.assertRaises(ProjectIntegrityRegistryError) as raised:
                    update_operation_status(self.connection, operation_id, rejected)
                self.assertEqual(raised.exception.code, "invalid_operation_transition")
                row = self.connection.execute(
                    "SELECT status, error_json FROM integrity_operations WHERE operation_id = ?",
                    (operation_id,),
                ).fetchone()
                self.assertEqual(row, ("prepared", "{}"))

        with self.connection:
            update_operation_status(self.connection, operation_id, "fs_applied")
        with self.assertRaises(ProjectIntegrityRegistryError) as raised:
            update_operation_status(self.connection, operation_id, "prepared")
        self.assertEqual(raised.exception.code, "invalid_operation_transition")
        self.assertEqual(
            self.connection.execute(
                "SELECT status FROM integrity_operations WHERE operation_id = ?",
                (operation_id,),
            ).fetchone()[0],
            "fs_applied",
        )

        with self.connection:
            update_operation_status(self.connection, operation_id, "db_committed")
        with self.assertRaises(ProjectIntegrityRegistryError) as raised:
            update_operation_status(self.connection, operation_id, "rolled_back")
        self.assertEqual(raised.exception.code, "invalid_operation_transition")
        self.assertEqual(
            self.connection.execute(
                "SELECT status FROM integrity_operations WHERE operation_id = ?",
                (operation_id,),
            ).fetchone()[0],
            "db_committed",
        )

    def test_operation_terminal_triggers_reject_direct_update_and_delete(self):
        with self.connection:
            finalized = create_operation(self.connection, "materialize_snapshot")
            update_operation_status(self.connection, finalized, "db_committed")
            update_operation_status(self.connection, finalized, "finalized")
            rolled_back = create_operation(self.connection, "restore_backup")
            update_operation_status(self.connection, rolled_back, "rolled_back")

        for operation_id in (finalized, rolled_back):
            with self.subTest(operation_id=operation_id, action="update"):
                with self.assertRaisesRegex(sqlite3.IntegrityError, "operation_terminal"):
                    with self.connection:
                        self.connection.execute(
                            "UPDATE integrity_operations SET status = 'needs_attention' WHERE operation_id = ?",
                            (operation_id,),
                        )
            with self.subTest(operation_id=operation_id, action="delete"):
                with self.assertRaisesRegex(sqlite3.IntegrityError, "operation_terminal"):
                    with self.connection:
                        self.connection.execute(
                            "DELETE FROM integrity_operations WHERE operation_id = ?",
                            (operation_id,),
                        )
            with self.assertRaises(ProjectIntegrityRegistryError) as raised:
                update_operation_status(
                    self.connection, operation_id, "needs_attention"
                )
            self.assertEqual(raised.exception.code, "invalid_operation_transition")

    def test_relocation_same_digest_keeps_version_and_writes_audit(self):
        baseline = self._register()
        image = next(item for item in baseline["files"] if item["role"] == "source_image")
        original_head = self.connection.execute(
            "SELECT data_version_id, revision_id FROM integrity_asset_heads WHERE asset_id = ?",
            (image["asset_id"],),
        ).fetchone()
        original_location = self.connection.execute(
            "SELECT location_id FROM integrity_locations WHERE asset_id = ? AND is_active = 1",
            (image["asset_id"],),
        ).fetchone()[0]
        original_counts = {
            table: self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "integrity_data_versions",
                "integrity_asset_revisions",
                "integrity_asset_heads",
            )
        }
        relocated_path = self._write(
            self.root / "relocated" / "a.png", b"image-v1"
        )

        with self.connection:
            result = relocate_project_asset(
                self.connection,
                project_id=self.project_id,
                asset_id=image["asset_id"],
                location={
                    "location_kind": "opaque_ref",
                    "opaque_ref": "location_relocated_a",
                },
                runtime_path=relocated_path,
            )

        self.assertTrue(result["changed"])
        self.assertEqual(result["data_version_id"], self.version_id)
        self.assertEqual(
            self.connection.execute(
                "SELECT data_version_id, revision_id FROM integrity_asset_heads WHERE asset_id = ?",
                (image["asset_id"],),
            ).fetchone(),
            original_head,
        )
        for table, expected_count in original_counts.items():
            self.assertEqual(
                self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0],
                expected_count,
            )
        locations = self.connection.execute(
            "SELECT location_id, opaque_ref, is_active FROM integrity_locations WHERE asset_id = ?",
            (image["asset_id"],),
        ).fetchall()
        self.assertIn((original_location, None, 0), locations)
        self.assertIn(
            (result["new_location_id"], "location_relocated_a", 1), locations
        )

        operation = self.connection.execute(
            """
            SELECT operation_kind, status, target_location_ref,
                   backup_location_ref, payload_json
            FROM integrity_operations WHERE operation_id = ?
            """,
            (result["operation_id"],),
        ).fetchone()
        self.assertEqual(operation[:4], (
            "asset_relocation",
            "finalized",
            result["new_location_id"],
            original_location,
        ))
        payload = json.loads(operation[4])
        self.assertEqual(payload["asset_id"], image["asset_id"])
        self.assertEqual(payload["data_version_id"], self.version_id)
        self.assertEqual(payload["digest"], image["digest"])
        self.assertTrue(payload["same_content_verified"])
        self.assertNotIn(str(self.root), json.dumps(operation, ensure_ascii=False))

    def test_relocation_digest_mismatch_has_no_side_effects(self):
        baseline = self._register()
        image = next(item for item in baseline["files"] if item["role"] == "source_image")
        original_location = self.connection.execute(
            "SELECT location_id FROM integrity_locations WHERE asset_id = ? AND is_active = 1",
            (image["asset_id"],),
        ).fetchone()[0]
        before = {
            table: self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "integrity_data_versions",
                "integrity_asset_revisions",
                "integrity_asset_heads",
                "integrity_locations",
                "integrity_operations",
            )
        }
        wrong_path = self._write(self.root / "relocated" / "a.png", b"wrong")

        with self.assertRaises(ProjectIntegrityRegistryError) as raised:
            with self.connection:
                relocate_project_asset(
                    self.connection,
                    project_id=self.project_id,
                    asset_id=image["asset_id"],
                    location={
                        "location_kind": "opaque_ref",
                        "opaque_ref": "location_wrong_a",
                    },
                    runtime_path=wrong_path,
                )
        self.assertEqual(raised.exception.code, "relocation_digest_mismatch")
        for table, expected_count in before.items():
            self.assertEqual(
                self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0],
                expected_count,
            )
        self.assertEqual(
            self.connection.execute(
                "SELECT location_id FROM integrity_locations WHERE asset_id = ? AND is_active = 1",
                (image["asset_id"],),
            ).fetchone()[0],
            original_location,
        )

    def test_relocation_caller_transaction_rolls_back_location_and_audit(self):
        baseline = self._register()
        image = next(item for item in baseline["files"] if item["role"] == "source_image")
        original_location = self.connection.execute(
            "SELECT location_id FROM integrity_locations WHERE asset_id = ? AND is_active = 1",
            (image["asset_id"],),
        ).fetchone()[0]
        relocated_path = self._write(
            self.root / "relocated" / "a.png", b"image-v1"
        )

        with self.assertRaisesRegex(RuntimeError, "forced_relocation_rollback"):
            with self.connection:
                result = relocate_project_asset(
                    self.connection,
                    project_id=self.project_id,
                    asset_id=image["asset_id"],
                    location={
                        "location_kind": "opaque_ref",
                        "opaque_ref": "location_rollback_a",
                    },
                    runtime_path=relocated_path,
                )
                raise RuntimeError("forced_relocation_rollback")

        self.assertIsNone(
            self.connection.execute(
                "SELECT 1 FROM integrity_operations WHERE operation_id = ?",
                (result["operation_id"],),
            ).fetchone()
        )
        self.assertIsNone(
            self.connection.execute(
                "SELECT 1 FROM integrity_locations WHERE opaque_ref = 'location_rollback_a'"
            ).fetchone()
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT location_id FROM integrity_locations WHERE asset_id = ? AND is_active = 1",
                (image["asset_id"],),
            ).fetchone()[0],
            original_location,
        )
        self.assertEqual(
            registry_state(self.connection)["current_data_version_id"],
            self.version_id,
        )

    def test_versions_store_only_deltas_and_heads_remain_current_only(self):
        baseline = self._register()
        old_label = next(
            item for item in baseline["files"] if item["role"] == "human_confirmed_label"
        )
        with self.connection:
            commit_project_data_version(
                self.connection,
                project_id=self.project_id,
                parent_data_version_id=self.version_id,
                new_data_version_id="project_data_v2",
                changes=[
                    {
                        "owner_kind": "image",
                        "owner_key": "image_a",
                        "role": "human_confirmed_label",
                        "schema_id": LABEL_SNAPSHOT_SCHEMA_ID,
                        "snapshot_text": canonical_snapshot_text(
                            {
                                "schema_version": LABEL_SNAPSHOT_SCHEMA_ID,
                                "image_uid": "image_a",
                                "parts": {"Head": [[0, 0], [4, 0], [1, 4]]},
                            }
                        ),
                    }
                ],
                reason="trusted_label_changed",
            )

        counts = dict(
            self.connection.execute(
                """
                SELECT data_version_id, COUNT(*)
                FROM integrity_version_changes
                GROUP BY data_version_id
                """
            ).fetchall()
        )
        self.assertEqual(counts, {self.version_id: 2, "project_data_v2": 1})
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM integrity_asset_heads"
            ).fetchone()[0],
            2,
        )
        old_snapshot = get_registry_version_snapshot(self.connection, self.version_id)
        current_snapshot = get_registry_version_snapshot(self.connection, "project_data_v2")
        historical_label = next(
            item for item in old_snapshot["files"] if item["role"] == "human_confirmed_label"
        )
        current_label = next(
            item for item in current_snapshot["files"] if item["role"] == "human_confirmed_label"
        )
        self.assertEqual(historical_label["digest"], old_label["digest"])
        self.assertNotEqual(current_label["digest"], old_label["digest"])

    def test_committed_version_is_immutable(self):
        self._register()
        with self.assertRaises(sqlite3.IntegrityError):
            with self.connection:
                self.connection.execute(
                    """
                    UPDATE integrity_data_versions
                    SET change_reason = 'rewritten'
                    WHERE data_version_id = ?
                    """,
                    (self.version_id,),
                )

    def test_readonly_snapshot_query_does_not_compete_with_writer(self):
        self._register()
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            snapshot = get_training_baseline_snapshot(self.db_path)
        finally:
            self.connection.rollback()
        self.assertEqual(snapshot["status"], "registered")

        readonly = connect_sqlite_database_readonly(self.db_path)
        try:
            self.assertEqual(readonly.execute("PRAGMA query_only").fetchone()[0], 1)
            with self.assertRaises(sqlite3.OperationalError):
                readonly.execute(
                    "UPDATE integrity_registry_state SET status = 'recovery_required'"
                )
        finally:
            readonly.close()

    def test_schema_validation_requires_immutability_triggers(self):
        self.connection.execute(
            "DROP TRIGGER trg_integrity_asset_revisions_immutable_update"
        )
        with self.assertRaises(ProjectIntegrityRegistryError) as raised:
            validate_project_integrity_registry_schema(self.connection)
        self.assertEqual(raised.exception.code, "missing_integrity_registry_triggers")

    def test_canonical_snapshot_is_nfc_finite_and_has_no_trailing_newline(self):
        text = canonical_snapshot_text(
            {
                "schema_version": LABEL_SNAPSHOT_SCHEMA_ID,
                "label": "e\u0301",
                "value": 1.25,
            }
        )
        self.assertFalse(text.endswith("\n"))
        self.assertEqual(json.loads(text)["label"], "é")
        with self.assertRaises(ProjectIntegrityRegistryError) as raised:
            canonical_snapshot_text(
                {
                    "schema_version": LABEL_SNAPSHOT_SCHEMA_ID,
                    "value": float("nan"),
                }
            )
        self.assertEqual(raised.exception.code, "unsafe_non_finite_number")

    def test_registry_rejects_absolute_paths_secrets_and_noncanonical_snapshots(self):
        invalid_entries = [
            {
                "owner_kind": "image",
                "owner_key": "C:/private/image.png",
                "role": "source_image",
                "expected": {
                    "entry_kind": "file",
                    "size_bytes": 1,
                    "mtime_ns": 1,
                    "hash_algorithm": FULL_FILE_ALGORITHM,
                    "digest": "0" * 64,
                },
                "location": {
                    "location_kind": "managed_relative",
                    "path_base": "project_root",
                    "relative_path": "images/a.png",
                },
            },
            {
                "owner_kind": "image",
                "owner_key": "image_a",
                "role": "source_image",
                "asset_metadata": {"api_key": "private-value"},
                "expected": {
                    "entry_kind": "file",
                    "size_bytes": 1,
                    "mtime_ns": 1,
                    "hash_algorithm": FULL_FILE_ALGORITHM,
                    "digest": "0" * 64,
                },
                "location": {
                    "location_kind": "managed_relative",
                    "path_base": "project_root",
                    "relative_path": "images/a.png",
                },
            },
            {
                "owner_kind": "image",
                "owner_key": "image_a",
                "role": "human_confirmed_label",
                "schema_id": LABEL_SNAPSHOT_SCHEMA_ID,
                "snapshot_text": json.dumps(
                    {
                        "schema_version": LABEL_SNAPSHOT_SCHEMA_ID,
                        "image_uid": "image_a",
                        "parts": {},
                    }
                ),
            },
        ]
        for index, entry in enumerate(invalid_entries):
            with self.subTest(index=index):
                with self.assertRaises(ProjectIntegrityRegistryError):
                    with self.connection:
                        register_project_baseline(
                            self.connection,
                            project_kind=PROJECT_KIND_2D,
                            project_id=self.project_id,
                            data_version_id=self.version_id,
                            entries=[entry],
                        )
                self.assertEqual(registry_state(self.connection)["status"], "uninitialized")

    def test_source_volume_may_use_quick_but_initial_weights_may_not(self):
        source = self._write(self.project_root / "volumes" / "source.tif", b"volume")
        with self.connection:
            snapshot = register_project_baseline(
                self.connection,
                project_kind=PROJECT_KIND_2D,
                project_id=self.project_id,
                data_version_id=self.version_id,
                entries=[
                    {
                        "owner_kind": "volume",
                        "owner_key": "specimen_a",
                        "role": "source_volume",
                        "expected": compute_fingerprint(source, QUICK_FILE_ALGORITHM),
                        "location": {
                            "location_kind": "managed_relative",
                            "path_base": "project_root",
                            "relative_path": "volumes/source.tif",
                        },
                    }
                ],
            )
        self.assertEqual(snapshot["files"][0]["hash_algorithm"], QUICK_FILE_ALGORITHM)

        second_db = self.project_root / "weights.sqlite"
        second = create_2d_project_database(second_db)
        try:
            weight = self._write(self.model_root / "quick.pt", b"weights")
            with self.assertRaises(ProjectIntegrityRegistryError) as raised:
                with second:
                    register_project_baseline(
                        second,
                        project_kind=PROJECT_KIND_2D,
                        project_id="project_2d_weights",
                        data_version_id="project_data_weights",
                        entries=[
                            {
                                "owner_kind": "model_input",
                                "owner_key": "sam_b",
                                "role": "initial_weights",
                                "expected": compute_fingerprint(
                                    weight, QUICK_FILE_ALGORITHM
                                ),
                                "location": {
                                    "location_kind": "managed_relative",
                                    "path_base": "managed_model_root",
                                    "relative_path": "quick.pt",
                                },
                            }
                        ],
                    )
            self.assertEqual(raised.exception.code, "protected_hash_algorithm_invalid")
        finally:
            second.close()

    def test_resolver_rejects_symlink_root_and_leaves_no_temp_files(self):
        self._register()
        snapshot = get_training_baseline_snapshot(self.db_path)
        linked_root = self.root / "linked_project"
        try:
            os.symlink(self.project_root, linked_root, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation is unavailable")
        with self.assertRaises(ProjectIntegrityRegistryError) as raised:
            resolve_training_baseline_inputs(
                self.db_path,
                snapshot,
                project_root=linked_root,
                run_root=self.run_root,
            )
        self.assertEqual(raised.exception.code, "filesystem_link_not_allowed")

        resolved = resolve_training_baseline_inputs(
            self.db_path,
            snapshot,
            project_root=self.project_root,
            run_root=self.run_root,
        )
        self.assertEqual(resolved["status"], "verified")
        leftovers = [
            path
            for path in self.run_root.rglob("*")
            if ".tmp_" in path.name or path.name.endswith(".tmp")
        ]
        self.assertEqual(leftovers, [])

    def test_resolver_rejects_windows_reparse_root_without_os_privileges(self):
        self._register()
        snapshot = get_training_baseline_snapshot(self.db_path)
        original_lstat = os.lstat
        project_identity = os.path.normcase(os.path.abspath(self.project_root))

        def flagged_lstat(path):
            result = original_lstat(path)
            if os.path.normcase(os.path.abspath(os.fspath(path))) == project_identity:
                return SimpleNamespace(
                    st_mode=result.st_mode,
                    st_file_attributes=int(
                        getattr(result, "st_file_attributes", 0) or 0
                    )
                    | 0x400,
                )
            return result

        with patch(
            "AntSleap.core.project_integrity_registry.os.lstat",
            side_effect=flagged_lstat,
        ):
            with self.assertRaises(ProjectIntegrityRegistryError) as raised:
                resolve_training_baseline_inputs(
                    self.db_path,
                    snapshot,
                    project_root=self.project_root,
                    run_root=self.run_root,
                )
        self.assertEqual(raised.exception.code, "filesystem_link_not_allowed")


if __name__ == "__main__":
    unittest.main()
