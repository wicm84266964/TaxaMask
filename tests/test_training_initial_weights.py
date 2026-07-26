import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from AntSleap.core.file_integrity import FULL_FILE_ALGORITHM, compute_fingerprint
from AntSleap.core.project import ProjectManager
from AntSleap.core.training_initial_weights import (
    inspect_initial_weight_registration,
    register_initial_weight_version,
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


if __name__ == "__main__":
    unittest.main()
