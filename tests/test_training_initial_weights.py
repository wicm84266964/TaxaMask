import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from AntSleap.core import training_initial_weights
from AntSleap.core.file_integrity import FULL_FILE_ALGORITHM, compute_fingerprint
from AntSleap.core.project import ProjectManager
from AntSleap.core.training_initial_weights import (
    inspect_initial_weight_registration,
    read_verified_initial_weight,
    register_initial_weight_version,
    training_run_initial_weight_evidence,
)
from AntSleap.core.training_run_2d import prepare_2d_training_run


class TrainingInitialWeightsTests(unittest.TestCase):
    def _project(self, root):
        manager = ProjectManager()
        manager.location_registry_database_path = root / "locations.sqlite"
        project_root = root / "project"
        project_root.mkdir()
        manager.create_project("weights", project_root)
        images = []
        for index in range(2):
            image = project_root / f"ant_{index}.png"
            Image.new("RGB", (8, 8), color=(10, 20, 30)).save(image)
            images.append(str(image))
        manager.add_images(images, save=True)
        for image in images:
            manager.update_label(
                image, "Head", [[1, 1], [6, 1], [3, 6]], save=True
            )
        manager.initialize_integrity_baseline()
        return manager

    def test_registration_verifies_and_detects_one_byte_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = self._project(root)
            weight = root / "models" / "sam_b.pt"
            weight.parent.mkdir()
            weight.write_bytes(b"trusted-weight")
            entries = [{"slot": "parent.sam_base", "path": weight}]

            before = inspect_initial_weight_registration(manager, entries)
            self.assertEqual(before["items"][0]["status"], "missing")
            registered = register_initial_weight_version(
                manager, entries, note="Researcher approved installed base SAM."
            )
            self.assertTrue(registered["changed"])
            self.assertTrue(inspect_initial_weight_registration(manager, entries)["verified"])

            weight.write_bytes(b"trusted-weighu")
            changed = inspect_initial_weight_registration(manager, entries)
            self.assertFalse(changed["verified"])
            self.assertEqual(changed["items"][0]["status"], "mismatch")

    def test_publisher_expected_hash_must_match_before_registration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = self._project(root)
            weight = root / "models" / "locator.pth"
            weight.parent.mkdir()
            weight.write_bytes(b"published")
            expected = compute_fingerprint(weight, FULL_FILE_ALGORITHM)
            weight.write_bytes(b"tampered-")

            with self.assertRaisesRegex(
                ValueError, "initial_weight_publisher_hash_mismatch"
            ):
                register_initial_weight_version(
                    manager,
                    [{"slot": "parent.locator", "path": weight, "expected": expected}],
                    note="Publisher evidence.",
                )

    def test_verified_payload_and_digest_come_from_one_descriptor_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = self._project(root)
            weight = root / "models" / "sam_b.pt"
            weight.parent.mkdir()
            original = b"registered-sam-checkpoint"
            weight.write_bytes(original)
            entry = {"slot": "parent.sam_base", "path": weight}
            register_initial_weight_version(
                manager,
                [entry],
                note="Researcher approved base SAM.",
            )

            with patch(
                "AntSleap.core.training_initial_weights._read_initial_weight_descriptor",
                wraps=training_initial_weights._read_initial_weight_descriptor,
            ) as read_mock:
                verified = read_verified_initial_weight(manager, entry)

            self.assertEqual(read_mock.call_count, 1)
            self.assertEqual(verified["payload"], original)
            self.assertEqual(
                verified["observed"]["digest"],
                hashlib.sha256(verified["payload"]).hexdigest(),
            )
            self.assertEqual(
                verified["observed"]["size_bytes"],
                len(verified["payload"]),
            )
            weight.write_bytes(b"replaced-after-verification")
            self.assertEqual(verified["payload"], original)

            ordinary = inspect_initial_weight_registration(manager, [entry])
            self.assertNotIn("payload", ordinary["items"][0])
            json.dumps(ordinary)

    def test_strict_read_rejects_unregistered_and_mismatched_weights(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = self._project(root)
            weight = root / "models" / "sam_b.pt"
            weight.parent.mkdir()
            weight.write_bytes(b"candidate")
            entry = {"slot": "parent.sam_base", "path": weight}

            with self.assertRaisesRegex(
                ValueError,
                "initial_weight_not_verified:parent.sam_base:missing",
            ):
                read_verified_initial_weight(manager, entry)

            register_initial_weight_version(
                manager,
                [entry],
                note="Researcher approved base SAM.",
            )
            weight.write_bytes(b"tampered-")
            with self.assertRaisesRegex(
                ValueError,
                "initial_weight_not_verified:parent.sam_base:mismatch",
            ):
                read_verified_initial_weight(manager, entry)

    def test_descriptor_read_rejects_concurrent_content_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = self._project(root)
            weight = root / "models" / "sam_b.pt"
            weight.parent.mkdir()
            weight.write_bytes(b"stable-before-read")
            entry = {"slot": "parent.sam_base", "path": weight}
            register_initial_weight_version(
                manager,
                [entry],
                note="Researcher approved base SAM.",
            )
            original_read = os.read
            changed = False

            def read_then_touch(descriptor, count):
                nonlocal changed
                chunk = original_read(descriptor, count)
                if chunk and not changed:
                    changed = True
                    current = weight.stat()
                    os.utime(
                        weight,
                        ns=(current.st_atime_ns, current.st_mtime_ns + 1_000_000_000),
                    )
                return chunk

            with patch(
                "AntSleap.core.training_initial_weights.os.read",
                side_effect=read_then_touch,
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "initial_weight_changed_during_read",
                ):
                    read_verified_initial_weight(manager, entry)

    def test_symbolic_link_weight_is_rejected_before_descriptor_follow(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = self._project(root)
            target = root / "outside-sam.pt"
            target.write_bytes(b"must-not-be-followed")
            link = root / "models" / "sam_b.pt"
            link.parent.mkdir()
            try:
                link.symlink_to(target)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symbolic links unavailable: {exc}")

            with self.assertRaisesRegex(ValueError, "initial_weight_unsafe_entry"):
                inspect_initial_weight_registration(
                    manager,
                    [{"slot": "parent.sam_base", "path": link}],
                    include_payload=True,
                )

    def test_registered_weight_enters_run_manifest_and_tamper_blocks_prepare(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = self._project(root)
            weight = root / "models" / "locator.pth"
            weight.parent.mkdir()
            weight.write_bytes(b"registered-locator")
            register_initial_weight_version(
                manager,
                [{"slot": "parent.locator", "path": weight}],
                note="Researcher approved legacy Locator.",
            )
            kwargs = {
                "runs_root": root / "runs",
                "entrypoint": "builtin_locator_sam",
                "effective_config": {
                    "epochs": 1,
                    "batch_size": 1,
                    "learning_rate": 0.001,
                    "weight_decay": 0.0001,
                    "random_seed": 0,
                    "input_resolution": [8, 8],
                    "preprocessing": {"dataset_adapter": "TwoStageDataset"},
                    "model": {"family": "AntEngine", "version": "1"},
                    "loss_weights": {},
                },
                "backend": {
                    "backend_id": "builtin_locator_sam",
                    "backend_version": "1",
                    "adapter_id": "test",
                    "adapter_version": "1",
                },
                "include_parts": False,
                "initial_weight_slots": ("parent.locator",),
            }
            prepared = prepare_2d_training_run(manager, **kwargs)
            record = prepared.run.record
            manifest_path = (
                Path(prepared.run.run_dir)
                / record["integrity_manifest"]["relative_path"]
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertIn(
                "initial_weights", {item["role"] for item in manifest["files"]}
            )
            prepared.run.fail(RuntimeError("test cleanup"), stage="test")

            weight.write_bytes(b"tampered-locator-")
            with self.assertRaisesRegex(Exception, "source_digest_mismatch"):
                prepare_2d_training_run(manager, **kwargs)

    def test_run_weight_evidence_is_historical_and_detects_version_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = self._project(root)
            weight = root / "models" / "sam_b.pt"
            weight.parent.mkdir()
            original = b"base-sam-used-by-training-run"
            replacement = original[:-1] + b"N"
            weight.write_bytes(original)
            entry = {"slot": "parent.sam_base", "path": weight}
            register_initial_weight_version(
                manager,
                [entry],
                note="Register the Base SAM used by this run.",
            )
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
                    "input_resolution": [8, 8],
                    "preprocessing": {"dataset_adapter": "TwoStageDataset"},
                    "model": {"family": "AntEngine", "version": "1"},
                    "loss_weights": {},
                },
                backend={
                    "backend_id": "builtin_locator_sam",
                    "backend_version": "1",
                    "adapter_id": "test",
                    "adapter_version": "1",
                },
                include_parts=True,
                initial_weight_slots=("parent.sam_base",),
            )
            try:
                record = prepared.run.record
                evidence = training_run_initial_weight_evidence(
                    manager,
                    record,
                    run_dir=prepared.run.run_dir,
                    slot="parent.sam_base",
                )
                original_digest = hashlib.sha256(original).hexdigest()
                self.assertEqual(
                    evidence["fingerprint"]["digest"], original_digest
                )
                self.assertEqual(
                    evidence["data_version_id"],
                    record["project_ref"]["project_data_version_id"],
                )

                weight.write_bytes(replacement)
                register_initial_weight_version(
                    manager,
                    [entry],
                    note="Register the replacement Base SAM.",
                )
                current = read_verified_initial_weight(manager, entry)
                self.assertNotEqual(
                    current["observed"]["digest"],
                    evidence["fingerprint"]["digest"],
                )
                historical = training_run_initial_weight_evidence(
                    manager,
                    record,
                    run_dir=prepared.run.run_dir,
                    slot="parent.sam_base",
                )
                self.assertEqual(
                    historical["fingerprint"]["digest"], original_digest
                )

                wrong_version_record = dict(record)
                wrong_version_record["project_ref"] = dict(record["project_ref"])
                wrong_version_record["project_ref"][
                    "project_data_version_id"
                ] = str(manager.project_data["project_data_version_id"])
                with self.assertRaisesRegex(
                    ValueError,
                    "training_run_initial_weight_evidence_mismatch:digest",
                ):
                    training_run_initial_weight_evidence(
                        manager,
                        wrong_version_record,
                        run_dir=prepared.run.run_dir,
                        slot="parent.sam_base",
                    )
            finally:
                prepared.run.fail(RuntimeError("test cleanup"), stage="test")


if __name__ == "__main__":
    unittest.main()
