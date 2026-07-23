import json
import tempfile
import unittest
from pathlib import Path

from AntSleap.core.file_integrity import compute_fingerprint
from AntSleap.core.integrity_manifest_service import (
    IntegrityGateError,
    IntegrityManifestError,
    IntegrityManifestService,
    build_external_file_entry,
    build_file_entry,
    require_verified_training_inputs,
    validate_relative_path,
    write_manifest,
)


class IntegrityManifestServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.project_root = self.root / "project"
        self.run_root = self.root / "run"
        self.project_root.mkdir()
        self.run_root.mkdir()
        self.path_bases = {
            "project_root": self.project_root,
            "run_root": self.run_root,
        }

    def tearDown(self):
        self.tmp.cleanup()

    def _service(self, name="integrity_manifest.json"):
        return IntegrityManifestService(self.run_root / name, self.path_bases)

    def _entry(self, relative_path="data/source.bin", **kwargs):
        return build_file_entry(
            kwargs.pop("file_id", "source_volume"),
            kwargs.pop("role", "source_volume"),
            kwargs.pop("path_base", "project_root"),
            relative_path,
            kwargs.pop("data_version_id", "data_v1"),
            **kwargs,
        )

    def _write_source(self, relative_path="data/source.bin", payload=b"source"):
        path = self.project_root.joinpath(*relative_path.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return path

    def _entry_with_expected_fingerprint(self, relative_path, path):
        entry = self._entry(relative_path)
        entry.update(compute_fingerprint(path))
        return entry

    def test_relative_paths_are_strict_and_nfc(self):
        self.assertEqual(validate_relative_path("labels/e\u0301.zarr"), "labels/\u00e9.zarr")
        invalid = [
            "",
            "/absolute",
            "C:/private/file",
            "../escape",
            "a/../b",
            "a/./b",
            "a//b",
            "a\\b",
            "a\0b",
        ]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(IntegrityManifestError):
                validate_relative_path(value)

    def test_create_and_verify_manifest_atomically(self):
        path = self._write_source(payload=b"manual truth")
        service = self._service()
        pending = service.create_manifest("train_run_01", [self._entry()])
        self.assertEqual(pending["status"], "pending")
        self.assertIsNone(pending["started_at"])
        self.assertFalse(Path(str(service.manifest_path) + ".tmp").exists())

        captured = service.capture_expected_fingerprints()
        self.assertEqual(captured["status"], "pending")
        self.assertIsNotNone(captured["baseline_captured_at"])
        verified = service.verify_manifest()
        self.assertEqual(verified["status"], "verified")
        self.assertEqual(verified["files"][0]["status"], "verified")
        self.assertEqual(
            verified["files"][0]["digest"], compute_fingerprint(path)["digest"]
        )
        self.assertIsNone(verified["error"])
        self.assertIsNotNone(verified["finished_at"])
        archived_text = Path(service.manifest_path).read_text(encoding="utf-8")
        self.assertNotIn(str(self.project_root), archived_text)
        self.assertNotIn(str(self.run_root), archived_text)
        self.assertEqual(
            require_verified_training_inputs(
                verified,
                required_file_ids=["source_volume"],
                required_roles=["source_volume"],
            )["manifest_id"],
            verified["manifest_id"],
        )

    def test_one_byte_change_produces_mismatch_with_expected_and_actual(self):
        source = self._write_source(payload=b"AAAA")
        entry = self._entry_with_expected_fingerprint("data/source.bin", source)
        expected_digest = entry["digest"]
        service = self._service()
        service.create_manifest("train_run_02", [entry])
        source.write_bytes(b"AAAB")

        result = service.verify_manifest()
        file_result = result["files"][0]
        self.assertEqual(result["status"], "mismatch")
        self.assertEqual(file_result["status"], "mismatch")
        self.assertEqual(file_result["expected_digest"], expected_digest)
        self.assertNotEqual(file_result["digest"], expected_digest)
        self.assertEqual(file_result["error"]["code"], "source_digest_mismatch")
        with self.assertRaises(IntegrityGateError):
            require_verified_training_inputs(result)

    def test_missing_file_keeps_expected_fingerprint_but_no_fake_observation(self):
        source = self._write_source(payload=b"move me")
        entry = self._entry_with_expected_fingerprint("data/source.bin", source)
        expected_digest = entry["digest"]
        service = self._service()
        service.create_manifest("train_run_03", [entry])
        source.unlink()

        result = service.verify_manifest()
        file_result = result["files"][0]
        self.assertEqual(result["status"], "missing")
        self.assertEqual(file_result["status"], "missing")
        self.assertEqual(file_result["expected_digest"], expected_digest)
        self.assertIsNone(file_result["digest"])
        self.assertEqual(file_result["error"]["code"], "source_missing")

    def test_cancel_is_incomplete_and_resume_rechecks_every_entry(self):
        self._write_source(payload=b"large" * 10000)
        service = self._service()
        original = service.create_manifest("train_run_04", [self._entry()])
        service.capture_expected_fingerprints()

        interrupted = service.verify_manifest(cancel_check=lambda: True)
        self.assertEqual(interrupted["status"], "incomplete")
        self.assertEqual(interrupted["files"][0]["status"], "incomplete")
        self.assertEqual(interrupted["files"][0]["error"]["code"], "user_cancelled")

        resumed = service.resume_incomplete(chunk_size=257)
        self.assertEqual(resumed["manifest_id"], original["manifest_id"])
        self.assertEqual(resumed["attempt"], 2)
        self.assertEqual(resumed["status"], "verified")
        self.assertEqual(resumed["phase"], "verification")

    def test_pending_started_record_recovers_to_incomplete(self):
        self._write_source()
        service = self._service()
        service.create_manifest("train_run_05", [self._entry()])
        service.capture_expected_fingerprints()
        payload = service.load()
        payload["started_at"] = payload["created_at"]
        service._write(payload)

        recovered = service.recover_pending_as_incomplete()
        self.assertEqual(recovered["status"], "incomplete")
        self.assertEqual(recovered["error"]["code"], "process_interrupted")
        self.assertEqual(service.resume_incomplete()["status"], "verified")

    def test_relocate_requires_same_digest_and_preserves_old_record(self):
        old_source = self._write_source(payload=b"same bytes")
        entry = self._entry_with_expected_fingerprint("data/source.bin", old_source)
        service = self._service()
        service.create_manifest("train_run_06", [entry])
        old_source.unlink()
        missing = service.verify_manifest()
        self.assertEqual(missing["status"], "missing")
        new_source = self._write_source("relocated/source.bin", b"same bytes")
        output_path = self.run_root / "relocated_manifest.json"

        relocated = service.relocate_same_digest(
            "source_volume",
            "project_root",
            "relocated/source.bin",
            output_manifest_path=output_path,
        )
        self.assertEqual(relocated["status"], "verified")
        self.assertEqual(relocated["supersedes"], missing["manifest_id"])
        self.assertEqual(relocated["files"][0]["relative_path"], "relocated/source.bin")
        self.assertEqual(service.load()["status"], "missing")
        self.assertTrue(output_path.exists())
        self.assertEqual(relocated["files"][0]["size_bytes"], new_source.stat().st_size)
        self.assertNotIn(str(self.project_root), json.dumps(relocated))

    def test_relocation_mismatch_does_not_publish_a_manifest(self):
        old_source = self._write_source(payload=b"expected")
        entry = self._entry_with_expected_fingerprint("data/source.bin", old_source)
        service = self._service()
        service.create_manifest("train_run_07", [entry])
        old_source.unlink()
        service.verify_manifest()
        self._write_source("relocated/source.bin", b"different")
        output_path = self.run_root / "must_not_exist.json"

        with self.assertRaises(IntegrityManifestError) as caught:
            service.relocate_same_digest(
                "source_volume",
                "project_root",
                "relocated/source.bin",
                output_manifest_path=output_path,
            )
        self.assertEqual(caught.exception.code, "relocation_digest_mismatch")
        self.assertFalse(output_path.exists())

    def test_relocation_rechecks_every_other_file_in_new_manifest(self):
        old_source = self._write_source("data/moved.bin", b"same bytes")
        truth = self._write_source("labels/truth.bin", b"truth-v1")
        moved_entry = self._entry_with_expected_fingerprint(
            "data/moved.bin", old_source
        )
        truth_entry = build_file_entry(
            "manual_truth",
            "manual_truth",
            "project_root",
            "labels/truth.bin",
            "truth_v1",
            entry_kind="file",
        )
        truth_entry.update(compute_fingerprint(truth))
        service = self._service()
        service.create_manifest(
            "train_run_relocate_all", [moved_entry, truth_entry]
        )
        old_source.unlink()
        missing = service.verify_manifest()
        self.assertEqual(missing["status"], "missing")
        self._write_source("relocated/moved.bin", b"same bytes")
        truth.write_bytes(b"truth-v2")

        relocated = service.relocate_same_digest(
            "source_volume",
            "project_root",
            "relocated/moved.bin",
            output_manifest_path=self.run_root / "relocate_all_manifest.json",
        )
        by_id = {entry["file_id"]: entry for entry in relocated["files"]}
        self.assertEqual(relocated["status"], "mismatch")
        self.assertEqual(by_id["source_volume"]["status"], "verified")
        self.assertEqual(by_id["manual_truth"]["status"], "mismatch")

    def test_supersede_requires_note_and_creates_new_pending_version(self):
        source = self._write_source(payload=b"version one")
        service = self._service()
        first = service.create_manifest("train_run_08", [self._entry()])
        service.capture_expected_fingerprints()
        first = service.verify_manifest()
        source.write_bytes(b"version two")
        output_path = self.run_root / "version_two_manifest.json"

        with self.assertRaises(IntegrityManifestError):
            service.supersede_with_note("source_volume", note="")
        second = service.supersede_with_note(
            "source_volume",
            note="Intentional correction after specimen review",
            data_version_id="data_v2",
            output_manifest_path=output_path,
        )
        self.assertEqual(second["status"], "pending")
        self.assertEqual(second["supersedes"], first["manifest_id"])
        self.assertEqual(second["files"][0]["data_version_id"], "data_v2")
        self.assertEqual(service.load()["manifest_id"], first["manifest_id"])

        second_service = IntegrityManifestService(output_path, self.path_bases)
        verified_second = second_service.verify_manifest()
        self.assertEqual(verified_second["status"], "verified")
        self.assertNotEqual(
            verified_second["files"][0]["digest"], first["files"][0]["digest"]
        )

    def test_gate_reports_structured_issues_and_has_no_override_parameter(self):
        self._write_source()
        pending = self._service().create_manifest("train_run_09", [self._entry()])
        with self.assertRaises(IntegrityGateError) as caught:
            require_verified_training_inputs(
                pending, required_file_ids=["source_volume", "manual_truth"]
            )
        self.assertEqual(caught.exception.code, "training_inputs_not_verified")
        self.assertTrue(caught.exception.issues)
        with self.assertRaises(TypeError):
            require_verified_training_inputs(pending, allow_unverified=True)

    def test_managed_root_symlink_is_rejected_even_when_target_is_contained(self):
        target = self._write_source("data/target.bin", b"target")
        link = self.project_root / "data" / "link.bin"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("This workstation cannot create test symlinks")
        service = self._service()
        service.create_manifest("train_run_10", [self._entry("data/link.bin")])
        result = service.capture_expected_fingerprints()
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(
            result["files"][0]["error"]["code"], "unsupported_entry_type"
        )

    def test_empty_expected_fingerprint_cannot_self_certify(self):
        self._write_source()
        service = self._service()
        service.create_manifest("train_run_11", [self._entry()])
        with self.assertRaises(IntegrityManifestError) as caught:
            service.verify_manifest()
        self.assertEqual(caught.exception.code, "baseline_capture_required")
        unchanged = service.load()
        self.assertEqual(unchanged["status"], "pending")
        self.assertEqual(unchanged["phase"], "baseline_capture")
        self.assertIsNone(unchanged["files"][0]["digest"])

    def test_verified_manifest_requires_new_recheck_and_detects_later_change(self):
        source = self._write_source(payload=b"baseline")
        service = self._service()
        service.create_manifest("train_run_12", [self._entry()])
        service.capture_expected_fingerprints()
        original = service.verify_manifest()
        with self.assertRaises(IntegrityManifestError) as caught:
            service.verify_manifest()
        self.assertEqual(caught.exception.code, "manifest_recheck_required")

        source.write_bytes(b"modified")
        recheck_path = self.run_root / "recheck_manifest.json"
        recheck = service.recheck_verified(output_manifest_path=recheck_path)
        self.assertEqual(recheck["status"], "mismatch")
        self.assertEqual(recheck["recheck_of"], original["manifest_id"])
        self.assertEqual(service.load()["status"], "verified")

    def test_protected_roles_reject_quick_but_source_volume_allows_it(self):
        with self.assertRaises(IntegrityManifestError) as caught:
            build_file_entry(
                "truth",
                "manual_truth",
                "project_root",
                "labels/truth.bin",
                "data_v1",
                algorithm="quick_fingerprint",
                entry_kind="file",
            )
        self.assertEqual(caught.exception.code, "quick_fingerprint_not_archival")

        self._write_source(payload=b"ct" * 100)
        service = self._service()
        service.create_manifest(
            "train_run_13", [self._entry(algorithm="quick_fingerprint")]
        )
        service.capture_expected_fingerprints()
        verified = service.verify_manifest()
        self.assertEqual(
            verified["files"][0]["hash_algorithm"],
            "taxamask-sampled-sha256-v1",
        )

    def test_schema_cleaning_drops_unknown_fields_sanitizes_error_and_writes_nfc(self):
        self._write_source("labels/\u00e9.bin", b"x")
        entry = self._entry("labels/e\u0301.bin")
        entry["private_path"] = "C:/Users/private/source.bin"
        service = self._service()
        created = service.create_manifest("train_run_14", [entry])
        created["api_key"] = "must-not-survive"
        cleaned = write_manifest(service.manifest_path, created)
        raw = Path(service.manifest_path).read_text(encoding="utf-8")
        self.assertNotIn("api_key", raw)
        self.assertNotIn("private_path", raw)
        self.assertEqual(cleaned["files"][0]["relative_path"], "labels/\u00e9.bin")

        service.capture_expected_fingerprints(cancel_check=lambda: True)
        incomplete = service.load()
        incomplete["error"]["summary"] = "Failed at C:/Users/private/source.bin"
        incomplete["error"]["traceback"] = "api_key=secret"
        cleaned = write_manifest(service.manifest_path, incomplete)
        self.assertNotIn("C:/Users", cleaned["error"]["summary"])
        self.assertNotIn("traceback", cleaned["error"])

    def test_activity_lock_prevents_recovery_from_interrupting_live_verification(self):
        self._write_source()
        first = self._service()
        first.create_manifest("train_run_15", [self._entry()])
        first.capture_expected_fingerprints()
        second = IntegrityManifestService(first.manifest_path, self.path_bases)
        with first._activity_guard():
            with self.assertRaises(IntegrityManifestError) as caught:
                second.recover_pending_as_incomplete()
        self.assertEqual(caught.exception.code, "manifest_busy")
        self.assertEqual(first.verify_manifest()["status"], "verified")

    def test_baseline_capture_persists_phase_before_hashing_and_cancel_resumes_capture(self):
        self._write_source(payload=b"baseline" * 100)
        service = self._service()
        service.create_manifest("train_run_phase_01", [self._entry()])
        observed = []

        def progress(_file_id, _done, _total):
            if not observed:
                active = service.load()
                observed.append((active["phase"], active["started_at"]))

        interrupted = service.capture_expected_fingerprints(
            progress_callback=progress,
            cancel_check=lambda: bool(observed),
        )
        self.assertTrue(observed)
        self.assertEqual(observed[0][0], "baseline_capture")
        self.assertIsNotNone(observed[0][1])
        self.assertEqual(interrupted["status"], "incomplete")
        self.assertEqual(interrupted["phase"], "baseline_capture")

        resumed = service.resume_incomplete()
        self.assertEqual(resumed["status"], "pending")
        self.assertEqual(resumed["phase"], "verification")
        self.assertIsNotNone(resumed["files"][0]["digest"])
        self.assertEqual(service.verify_manifest()["status"], "verified")

    def test_missing_during_baseline_capture_resumes_capture_not_verify(self):
        service = self._service()
        service.create_manifest("train_run_phase_02", [self._entry()])
        missing = service.capture_expected_fingerprints()
        self.assertEqual(missing["status"], "incomplete")
        self.assertEqual(missing["phase"], "baseline_capture")
        self._write_source(payload=b"now available")

        resumed = service.resume_incomplete()
        self.assertEqual(resumed["status"], "pending")
        self.assertEqual(resumed["phase"], "verification")
        self.assertEqual(service.verify_manifest()["status"], "verified")

    def test_recovery_retains_baseline_capture_phase_for_resume(self):
        self._write_source()
        service = self._service()
        service.create_manifest("train_run_phase_03", [self._entry()])
        payload = service.load()
        payload["phase"] = "baseline_capture"
        payload["started_at"] = payload["created_at"]
        write_manifest(service.manifest_path, payload)

        recovered = service.recover_pending_as_incomplete()
        self.assertEqual(recovered["status"], "incomplete")
        self.assertEqual(recovered["phase"], "baseline_capture")
        resumed = service.resume_incomplete()
        self.assertEqual(resumed["status"], "pending")
        self.assertEqual(resumed["phase"], "verification")

    def test_external_directory_is_recomputed_without_archiving_its_path(self):
        external_root = self.root / "private_external_dataset"
        external_root.mkdir()
        (external_root / "case_01.bin").write_bytes(b"case-one")
        entry = build_external_file_entry(
            "external_dataset",
            "verified_external_truth",
            "source_ref_01",
            "external_v1",
            algorithm="sha256-tree-v1",
        )
        self.assertEqual(entry["entry_kind"], "external_reference")
        self.assertNotIn("path_base", entry)
        self.assertNotIn("relative_path", entry)
        service = IntegrityManifestService(
            self.run_root / "external_manifest.json",
            self.path_bases,
            external_locations={"source_ref_01": external_root},
        )
        service.create_manifest("train_external_01", [entry])
        service.capture_expected_fingerprints()
        verified = service.verify_manifest()
        archived = Path(service.manifest_path).read_text(encoding="utf-8")
        self.assertEqual(verified["status"], "verified")
        self.assertEqual(
            verified["files"][0]["hash_algorithm"], "sha256-tree-v1"
        )
        self.assertNotIn(str(external_root), archived)
        self.assertNotIn("path_base", verified["files"][0])
        self.assertNotIn("relative_path", verified["files"][0])

        (external_root / "case_01.bin").write_bytes(b"changed")
        recheck = service.recheck_verified(
            output_manifest_path=self.run_root / "external_recheck.json"
        )
        self.assertEqual(recheck["status"], "mismatch")

    def test_external_location_mapping_is_required_and_missing_source_is_explicit(self):
        entry = build_external_file_entry(
            "external_dataset",
            "verified_external_truth",
            "source_ref_02",
            "external_v1",
            algorithm="sha256-tree-v1",
        )
        service = IntegrityManifestService(
            self.run_root / "external_missing_mapping.json", self.path_bases
        )
        service.create_manifest("train_external_02", [entry])
        unavailable = service.capture_expected_fingerprints()
        self.assertEqual(unavailable["status"], "incomplete")
        self.assertEqual(
            unavailable["files"][0]["error"]["code"],
            "external_location_unavailable",
        )

        missing_path = self.root / "does_not_exist"
        missing_service = IntegrityManifestService(
            self.run_root / "external_missing_source.json",
            self.path_bases,
            external_locations={"source_ref_02": missing_path},
        )
        missing_service.create_manifest("train_external_03", [entry])
        missing = missing_service.capture_expected_fingerprints()
        self.assertEqual(missing["status"], "incomplete")
        self.assertEqual(missing["files"][0]["error"]["code"], "source_missing")

    def test_external_reference_rejects_paths_and_protected_quick_hash(self):
        for role in (
            "manual_truth",
            "human_confirmed_label",
            "verified_external_truth",
        ):
            with self.subTest(role=role), self.assertRaises(
                IntegrityManifestError
            ) as caught:
                build_external_file_entry(
                    f"external_{role}",
                    role,
                    "source_ref_03",
                    "external_v1",
                    algorithm="quick_fingerprint",
                )
            self.assertEqual(
                caught.exception.code, "quick_fingerprint_not_archival"
            )

        entry = build_external_file_entry(
            "external_truth",
            "verified_external_truth",
            "source_ref_03",
            "external_v1",
            algorithm="sha256-tree-v1",
        )
        entry["path_base"] = "project_root"
        entry["relative_path"] = "private/data"
        service = IntegrityManifestService(
            self.run_root / "external_path_leak.json", self.path_bases
        )
        with self.assertRaises(IntegrityManifestError) as caught:
            service.create_manifest("train_external_04", [entry])
        self.assertEqual(caught.exception.code, "external_reference_path_not_allowed")
        self.assertFalse(Path(service.manifest_path).exists())

    def test_external_reference_can_relocate_by_opaque_ref_only(self):
        old_root = self.root / "old_external"
        new_root = self.root / "new_external"
        old_root.mkdir()
        new_root.mkdir()
        (old_root / "case.bin").write_bytes(b"same")
        (new_root / "case.bin").write_bytes(b"same")
        entry = build_external_file_entry(
            "external_dataset",
            "verified_external_truth",
            "source_old",
            "external_v1",
            algorithm="sha256-tree-v1",
        )
        service = IntegrityManifestService(
            self.run_root / "external_relocate_source.json",
            self.path_bases,
            external_locations={"source_old": old_root, "source_new": new_root},
        )
        service.create_manifest("train_external_05", [entry])
        service.capture_expected_fingerprints()
        service.verify_manifest()
        relocated = service.relocate_same_digest(
            "external_dataset",
            new_external_location_ref="source_new",
            output_manifest_path=self.run_root / "external_relocated.json",
        )
        self.assertEqual(relocated["status"], "verified")
        relocated_entry = relocated["files"][0]
        self.assertEqual(relocated_entry["external_location_ref"], "source_new")
        self.assertNotIn("path_base", relocated_entry)
        self.assertNotIn("relative_path", relocated_entry)


if __name__ == "__main__":
    unittest.main()
