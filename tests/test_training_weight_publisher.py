import hashlib
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from AntSleap.core.training_weight_publisher import (
    PUBLICATION_FILENAME,
    PUBLICATION_STATUS_ACTIVE,
    PUBLICATION_STATUS_PENDING,
    ActivePublicationImmutable,
    PublicationAlreadyExists,
    PublicationIntegrityError,
    PublicationLockBusy,
    TrainingWeightPublisher,
    UnsafePublicationEntry,
)


class TrainingWeightPublisherTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.staging = self.root / "staging"
        self.staging.mkdir()
        self.model_root = self.root / "managed_models"
        self.publisher = TrainingWeightPublisher(self.model_root)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write(self, relative_path, content):
        path = self.staging / Path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    @staticmethod
    def _artifact(artifact_id, relative_path, **extra):
        result = {
            "artifact_id": artifact_id,
            "relative_path": relative_path,
        }
        result.update(extra)
        return result

    def _publish_one(self, run_id="train_publish_one", content=b"weights-v1"):
        self._write("weights/model.pt", content)
        return self.publisher.publish_pending(
            run_id,
            self.staging,
            [self._artifact("model_weights", "weights/model.pt")],
        )

    @staticmethod
    def _successful_record(publication):
        return {
            "schema_version": "taxamask_training_run_v1",
            "run_id": publication["run_id"],
            "status": "succeeded",
            "artifacts": [dict(item) for item in publication["artifacts"]],
        }

    def _manifest(self, run_id):
        path = self.model_root / "training_runs" / run_id / PUBLICATION_FILENAME
        return json.loads(path.read_text(encoding="utf-8"))

    def test_multiple_weights_are_fully_verified_and_activated(self):
        locator = self._write("parent/locator.pth", b"locator-weights")
        segmenter = self._write("parent/sam_decoder.pt", b"sam-weights")

        pending = self.publisher.publish_pending(
            "train_multi",
            self.staging,
            [
                self._artifact("locator_weights", "parent/locator.pth"),
                self._artifact(
                    "segmenter_weights",
                    "parent/sam_decoder.pt",
                    media_type="application/x-pytorch",
                ),
            ],
        )

        self.assertEqual(pending["status"], PUBLICATION_STATUS_PENDING)
        self.assertTrue(Path(pending["bundle_path"]).is_dir())
        self.assertEqual(len(pending["artifacts"]), 2)
        for source, artifact in zip((locator, segmenter), pending["artifacts"]):
            expected_digest = hashlib.sha256(source.read_bytes()).hexdigest()
            self.assertEqual(artifact["digest"], expected_digest)
            self.assertEqual(artifact["hash_algorithm"], "sha256")
            self.assertEqual(artifact["path_base"], "managed_model_root")
            self.assertEqual(artifact["entry_kind"], "file")
            published = self.model_root / Path(artifact["relative_path"])
            self.assertEqual(published.read_bytes(), source.read_bytes())

        active = self.publisher.activate(
            "train_multi", self._successful_record(pending)
        )

        self.assertEqual(active["status"], PUBLICATION_STATUS_ACTIVE)
        self.assertIsNotNone(active["activated_at"])
        persisted = self._manifest("train_multi")
        self.assertEqual(persisted["status"], PUBLICATION_STATUS_ACTIVE)
        self.assertNotIn("bundle_path", persisted)
        self.assertNotIn("manifest_path", persisted)
        self.assertTrue(
            all(item["role"] == "output_weights" for item in persisted["artifacts"])
        )

    def test_copy_failure_removes_partial_temp_and_never_creates_final_bundle(self):
        self._write("first.pt", b"first")
        self._write("second.pt", b"second")
        original = self.publisher._copy_verified_file
        calls = 0

        def fail_on_second(source, target):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated copy failure")
            return original(source, target)

        with mock.patch.object(
            self.publisher, "_copy_verified_file", side_effect=fail_on_second
        ):
            with self.assertRaises(OSError):
                self.publisher.publish_pending(
                    "train_copy_failure",
                    self.staging,
                    [
                        self._artifact("first_weights", "first.pt"),
                        self._artifact("second_weights", "second.pt"),
                    ],
                )

        run_root = self.model_root / "training_runs"
        self.assertFalse((run_root / "train_copy_failure").exists())
        self.assertEqual(list(run_root.iterdir()), [])

    def test_interruption_before_rename_leaves_hidden_bundle_for_safe_recovery(self):
        self._write("model.pt", b"weights")
        with mock.patch.object(
            self.publisher,
            "_rename_pending_bundle",
            side_effect=KeyboardInterrupt(),
        ):
            with self.assertRaises(KeyboardInterrupt):
                self.publisher.publish_pending(
                    "train_rename_interrupted",
                    self.staging,
                    [self._artifact("model_weights", "model.pt")],
                )

        run_root = self.model_root / "training_runs"
        hidden = list(run_root.iterdir())
        self.assertEqual(len(hidden), 1)
        self.assertTrue(hidden[0].name.startswith(".taxamask-weight-publish-"))

        report = self.publisher.recover(lambda _run_id: None)

        self.assertEqual(report["cleaned"], [hidden[0].name])
        self.assertEqual(report["manual_review"], [])
        self.assertEqual(list(run_root.iterdir()), [])

    def test_activation_write_interruption_recovers_successful_run_to_active(self):
        pending = self._publish_one("train_activation_interrupted")
        run_record = self._successful_record(pending)

        with mock.patch(
            "AntSleap.core.training_weight_publisher.atomic_write_json",
            side_effect=OSError("simulated activation interruption"),
        ):
            with self.assertRaises(OSError):
                self.publisher.activate("train_activation_interrupted", run_record)

        self.assertEqual(
            self._manifest("train_activation_interrupted")["status"],
            PUBLICATION_STATUS_PENDING,
        )
        report = self.publisher.recover(lambda _run_id: run_record)
        self.assertEqual(report["activated"], ["train_activation_interrupted"])
        self.assertEqual(
            self._manifest("train_activation_interrupted")["status"],
            PUBLICATION_STATUS_ACTIVE,
        )

    def test_recovery_removes_failed_and_missing_run_publications(self):
        failed = self._publish_one("train_failed")
        self.staging = self.root / "staging_missing"
        self.staging.mkdir()
        self._write("weights/model.pt", b"missing-run-weights")
        self.publisher.publish_pending(
            "train_missing",
            self.staging,
            [self._artifact("model_weights", "weights/model.pt")],
        )

        def resolve(run_id):
            if run_id == "train_failed":
                return {
                    "schema_version": "taxamask_training_run_v1",
                    "run_id": run_id,
                    "status": "failed",
                    "artifacts": failed["artifacts"],
                }
            return None

        report = self.publisher.recover(resolve)

        self.assertEqual(set(report["cleaned"]), {"train_failed", "train_missing"})
        self.assertFalse((self.model_root / "training_runs" / "train_failed").exists())
        self.assertFalse((self.model_root / "training_runs" / "train_missing").exists())

    def test_live_run_publication_waits_without_being_deleted(self):
        pending = self._publish_one("train_still_running")

        report = self.publisher.recover(
            lambda run_id: {
                "schema_version": "taxamask_training_run_v1",
                "run_id": run_id,
                "status": "running",
                "artifacts": pending["artifacts"],
            }
        )

        self.assertEqual(report["waiting"], ["train_still_running"])
        self.assertTrue((self.model_root / "training_runs" / "train_still_running").is_dir())
        self.assertEqual(
            self._manifest("train_still_running")["status"],
            PUBLICATION_STATUS_PENDING,
        )

    def test_active_bundle_is_never_rewritten_or_overwritten(self):
        pending = self._publish_one("train_active")
        run_record = self._successful_record(pending)
        self.publisher.activate("train_active", run_record)
        manifest_path = self.model_root / "training_runs" / "train_active" / PUBLICATION_FILENAME
        before = manifest_path.read_bytes()

        with self.assertRaises(ActivePublicationImmutable):
            self.publisher.activate("train_active", run_record)
        with self.assertRaises(PublicationAlreadyExists):
            self.publisher.publish_pending(
                "train_active",
                self.staging,
                [self._artifact("model_weights", "weights/model.pt")],
            )
        resolver = mock.Mock(return_value=run_record)
        report = self.publisher.recover(resolver)

        self.assertEqual(report["active"], ["train_active"])
        resolver.assert_called_once_with("train_active")
        self.assertEqual(manifest_path.read_bytes(), before)

    def test_active_bundle_without_matching_success_record_requires_manual_review(self):
        pending = self._publish_one("train_active_orphan")
        self.publisher.activate(
            "train_active_orphan", self._successful_record(pending)
        )

        report = self.publisher.recover(lambda _run_id: None)

        self.assertEqual(report["active"], [])
        self.assertEqual(len(report["manual_review"]), 1)
        self.assertEqual(
            report["manual_review"][0]["reason"],
            "successful_run_record_required",
        )
        self.assertEqual(
            self._manifest("train_active_orphan")["status"],
            PUBLICATION_STATUS_ACTIVE,
        )

    def test_list_active_requires_matching_success_record_and_current_hashes(self):
        pending = self._publish_one("train_discover_active")
        successful = self._successful_record(pending)
        self.publisher.activate("train_discover_active", successful)

        discovered = self.publisher.list_active(lambda _run_id: successful)

        self.assertEqual(
            [item["run_id"] for item in discovered["publications"]],
            ["train_discover_active"],
        )
        self.assertEqual(discovered["rejected"], [])
        artifact = discovered["publications"][0]["artifacts"][0]
        published_path = self.model_root / Path(artifact["relative_path"])
        published_path.write_bytes(b"tampered")

        rejected = self.publisher.list_active(lambda _run_id: successful)

        self.assertEqual(rejected["publications"], [])
        self.assertEqual(
            rejected["rejected"][0]["reason"],
            "published_weight_fingerprint_mismatch",
        )

    def test_list_active_rejects_orphaned_active_bundle(self):
        pending = self._publish_one("train_discover_orphan")
        self.publisher.activate(
            "train_discover_orphan", self._successful_record(pending)
        )

        discovered = self.publisher.list_active(lambda _run_id: None)

        self.assertEqual(discovered["publications"], [])
        self.assertEqual(
            discovered["rejected"][0]["reason"],
            "successful_run_record_required",
        )

    def test_same_pending_run_cannot_be_published_twice(self):
        self._publish_one("train_duplicate")
        with self.assertRaises(PublicationAlreadyExists):
            self.publisher.publish_pending(
                "train_duplicate",
                self.staging,
                [self._artifact("model_weights", "weights/model.pt")],
            )

    def test_non_model_role_is_rejected(self):
        self._write("model.pt", b"weights")
        with self.assertRaises(UnsafePublicationEntry) as raised:
            self.publisher.publish_pending(
                "train_wrong_role",
                self.staging,
                [
                    self._artifact(
                        "training_report", "model.pt", role="training_report"
                    )
                ],
            )
        self.assertEqual(
            raised.exception.code, "publication_artifact_role_invalid"
        )

    def test_model_manifest_can_publish_with_weights(self):
        self._write("model.pt", b"weights")
        self._write("model.manifest.json", b"{}")
        publication = self.publisher.publish_pending(
            "train_with_manifest",
            self.staging,
            [
                self._artifact("model_weights", "model.pt"),
                self._artifact(
                    "model_manifest",
                    "model.manifest.json",
                    role="model_manifest",
                ),
            ],
        )
        self.assertEqual(
            {item["role"] for item in publication["artifacts"]},
            {"output_weights", "model_manifest"},
        )

    def test_absolute_parent_backslash_and_noncanonical_paths_are_rejected(self):
        invalid_paths = (
            "/absolute/model.pt",
            "C:/absolute/model.pt",
            "../model.pt",
            "weights/../model.pt",
            "weights\\model.pt",
            "./model.pt",
            "weights//model.pt",
        )
        for index, invalid in enumerate(invalid_paths):
            with self.subTest(relative_path=invalid):
                with self.assertRaises(UnsafePublicationEntry):
                    self.publisher.publish_pending(
                        f"train_invalid_{index}",
                        self.staging,
                        [self._artifact("model_weights", invalid)],
                    )

    def test_duplicate_and_parent_child_artifact_paths_are_rejected(self):
        declarations = (
            [
                self._artifact("one", "model.pt"),
                self._artifact("one", "other.pt"),
            ],
            [
                self._artifact("one", "model.pt"),
                self._artifact("two", "model.pt"),
            ],
            [
                self._artifact("one", "weights"),
                self._artifact("two", "weights/model.pt"),
            ],
        )
        for index, artifacts in enumerate(declarations):
            with self.subTest(index=index), self.assertRaises(UnsafePublicationEntry):
                self.publisher.publish_pending(
                    f"train_conflict_{index}", self.staging, artifacts
                )

    def test_source_file_and_parent_symlinks_are_rejected(self):
        target = self._write("real/model.pt", b"weights")
        file_link = self.staging / "file_link.pt"
        parent_link = self.staging / "linked_parent"
        try:
            file_link.symlink_to(target)
            parent_link.symlink_to(target.parent, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("This workstation cannot create test symlinks")

        for index, relative in enumerate(("file_link.pt", "linked_parent/model.pt")):
            with self.subTest(relative=relative), self.assertRaises(UnsafePublicationEntry):
                self.publisher.publish_pending(
                    f"train_source_link_{index}",
                    self.staging,
                    [self._artifact("model_weights", relative)],
                )

    def test_managed_root_and_training_runs_links_are_rejected(self):
        external = self.root / "external"
        external.mkdir()
        linked_root = self.root / "linked_models"
        try:
            linked_root.symlink_to(external, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("This workstation cannot create directory symlinks")

        with self.assertRaises(UnsafePublicationEntry):
            TrainingWeightPublisher(linked_root)

        run_root = self.model_root / "training_runs"
        run_root.rmdir()
        run_root.symlink_to(external, target_is_directory=True)
        with self.assertRaises(UnsafePublicationEntry):
            self.publisher.publish_pending(
                "train_linked_target",
                self.staging,
                [self._artifact("model_weights", "unused.pt")],
            )

    def test_unsafe_hidden_directory_is_preserved_for_manual_review(self):
        hidden = (
            self.model_root
            / "training_runs"
            / ".taxamask-weight-publish-train_unsafe_hidden.0123456789abcdef"
        )
        hidden.mkdir()
        target = self.root / "outside.bin"
        target.write_bytes(b"outside")
        link = hidden / "unsafe_link"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("This workstation cannot create test symlinks")

        report = self.publisher.recover(lambda _run_id: None)

        self.assertEqual(len(report["manual_review"]), 1)
        self.assertEqual(
            report["manual_review"][0]["reason"], "filesystem_link_not_allowed"
        )
        self.assertTrue(hidden.exists())
        self.assertTrue(link.is_symlink())
        self.assertEqual(target.read_bytes(), b"outside")

    def test_manifest_never_persists_staging_or_runtime_absolute_paths(self):
        private_staging = self.root / "sensitive_user_name" / "private_staging"
        private_staging.mkdir(parents=True)
        (private_staging / "model.pt").write_bytes(b"weights")

        result = self.publisher.publish_pending(
            "train_private_paths",
            private_staging,
            [self._artifact("model_weights", "model.pt")],
        )
        manifest_path = Path(result["manifest_path"])
        raw = manifest_path.read_text(encoding="utf-8")
        payload = json.loads(raw)

        self.assertNotIn(str(private_staging), raw)
        self.assertNotIn(str(self.model_root), raw)
        self.assertNotIn("sensitive_user_name", raw)
        self.assertNotIn("bundle_path", payload)
        self.assertNotIn("manifest_path", payload)
        self.assertEqual(
            payload["artifacts"][0]["relative_path"],
            "training_runs/train_private_paths/model.pt",
        )

    def test_success_record_must_register_each_exact_weight_file(self):
        pending = self._publish_one("train_missing_registration")
        incomplete_record = {
            "schema_version": "taxamask_training_run_v1",
            "run_id": "train_missing_registration",
            "status": "succeeded",
            "artifacts": [],
        }

        with self.assertRaises(PublicationIntegrityError) as raised:
            self.publisher.activate("train_missing_registration", incomplete_record)

        self.assertEqual(raised.exception.code, "run_artifact_not_registered")
        self.assertEqual(
            self._manifest("train_missing_registration")["status"],
            PUBLICATION_STATUS_PENDING,
        )
        self.assertEqual(len(pending["artifacts"]), 1)

    def test_activation_rejects_unversioned_success_record(self):
        pending = self._publish_one("train_unversioned_record")
        unversioned = self._successful_record(pending)
        unversioned.pop("schema_version")

        with self.assertRaises(PublicationIntegrityError) as raised:
            self.publisher.activate("train_unversioned_record", unversioned)

        self.assertEqual(raised.exception.code, "run_record_schema_invalid")
        self.assertEqual(
            self._manifest("train_unversioned_record")["status"],
            PUBLICATION_STATUS_PENDING,
        )

    def test_live_hidden_publication_waits_for_recorder_recovery(self):
        self._write("model.pt", b"weights")
        with mock.patch.object(
            self.publisher,
            "_rename_pending_bundle",
            side_effect=KeyboardInterrupt(),
        ):
            with self.assertRaises(KeyboardInterrupt):
                self.publisher.publish_pending(
                    "train_live_hidden",
                    self.staging,
                    [self._artifact("model_weights", "model.pt")],
                )
        hidden = next((self.model_root / "training_runs").iterdir())

        live_record = {
            "schema_version": "taxamask_training_run_v1",
            "run_id": "train_live_hidden",
            "status": "running",
            "artifacts": [],
        }
        waiting = self.publisher.recover(lambda _run_id: live_record)
        self.assertEqual(waiting["waiting"], ["train_live_hidden"])
        self.assertTrue(hidden.exists())

        interrupted_record = dict(live_record, status="interrupted")
        cleaned = self.publisher.recover(lambda _run_id: interrupted_record)
        self.assertEqual(cleaned["cleaned"], [hidden.name])
        self.assertFalse(hidden.exists())

    def test_second_publisher_instance_cannot_modify_root_concurrently(self):
        self._write("model.pt", b"weights")
        second = TrainingWeightPublisher(self.model_root)
        entered_copy = threading.Event()
        release_copy = threading.Event()
        original_copy = self.publisher._copy_verified_file
        failures = []

        def blocking_copy(source, target):
            entered_copy.set()
            if not release_copy.wait(5):
                raise RuntimeError("test did not release blocked publication")
            return original_copy(source, target)

        def publish_in_thread():
            try:
                self.publisher.publish_pending(
                    "train_locked",
                    self.staging,
                    [self._artifact("model_weights", "model.pt")],
                )
            except BaseException as exc:
                failures.append(exc)

        with mock.patch.object(
            self.publisher, "_copy_verified_file", side_effect=blocking_copy
        ):
            worker = threading.Thread(target=publish_in_thread)
            worker.start()
            self.assertTrue(entered_copy.wait(5))
            try:
                with self.assertRaises(PublicationLockBusy) as raised:
                    second.recover(lambda _run_id: None)
                self.assertEqual(raised.exception.code, "publication_lock_busy")
            finally:
                release_copy.set()
                worker.join(5)

        self.assertFalse(worker.is_alive())
        self.assertEqual(failures, [])
        self.assertTrue((self.model_root / "training_runs" / "train_locked").is_dir())

    def test_modified_pending_weight_is_preserved_for_manual_review(self):
        pending = self._publish_one("train_modified")
        published = self.model_root / Path(pending["artifacts"][0]["relative_path"])
        published.write_bytes(b"tampered")

        report = self.publisher.recover(
            lambda _run_id: self._successful_record(pending)
        )

        self.assertEqual(report["activated"], [])
        self.assertEqual(len(report["manual_review"]), 1)
        self.assertEqual(
            report["manual_review"][0]["reason"],
            "published_weight_fingerprint_mismatch",
        )
        self.assertTrue(published.exists())
        self.assertEqual(
            self._manifest("train_modified")["status"],
            PUBLICATION_STATUS_PENDING,
        )

    def test_stale_atomic_manifest_temp_is_removed_before_recovery_activation(self):
        pending = self._publish_one("train_stale_manifest_tmp")
        bundle = self.model_root / "training_runs" / "train_stale_manifest_tmp"
        stale = bundle / f"{PUBLICATION_FILENAME}.tmp"
        stale.write_text('{"status": "active"', encoding="utf-8")

        report = self.publisher.recover(
            lambda _run_id: self._successful_record(pending)
        )

        self.assertEqual(report["activated"], ["train_stale_manifest_tmp"])
        self.assertFalse(stale.exists())
        self.assertEqual(
            self._manifest("train_stale_manifest_tmp")["status"],
            PUBLICATION_STATUS_ACTIVE,
        )


if __name__ == "__main__":
    unittest.main()
