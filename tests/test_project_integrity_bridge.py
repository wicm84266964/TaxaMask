import json
import os
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from AntSleap.core.project import ProjectManager
from AntSleap.core.project_integrity_registry import (
    ProjectIntegrityRegistryError,
    get_training_baseline_snapshot,
)
from AntSleap.core.training_truth import LABEL_PART_METADATA_FIELD


class ProjectIntegrityBridgeTests(unittest.TestCase):
    def _manager(self, root, *, manual=True):
        project_dir = root / "project"
        source_dir = root / "source"
        source_dir.mkdir()
        image_path = source_dir / "ant.png"
        Image.new("RGB", (16, 12), color=(120, 80, 40)).save(image_path)
        manager = ProjectManager()
        manager.create_project("ants", project_dir)
        manager.location_registry_database_path = root / "locations.sqlite"
        manager.add_images([str(image_path)], save=True)
        if manual:
            manager.update_label(
                str(image_path),
                "Head",
                [[1, 1], [10, 1], [8, 8]],
                box=[1, 1, 10, 8],
                save=True,
            )
        return manager, image_path

    def test_registry_stays_uninitialized_until_explicit_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager, _image_path = self._manager(Path(tmp))
            self.assertEqual(
                manager.integrity_registry_state()["status"], "uninitialized"
            )
            snapshot = manager.initialize_integrity_baseline(
                note="Initial reviewed project state."
            )
            self.assertEqual(snapshot["status"], "registered")
            self.assertEqual(
                manager.integrity_registry_state()["status"], "ready"
            )
            roles = {item["role"] for item in snapshot["files"]}
            self.assertEqual(
                roles, {"label_schema", "source_image", "human_confirmed_label"}
            )
            serialized = json.dumps(snapshot, ensure_ascii=False)
            self.assertNotIn(str(Path(tmp).resolve()), serialized)

    def test_image_uid_survives_reload_and_same_digest_relocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager, image_path = self._manager(root)
            manager.initialize_integrity_baseline()
            uid_before = manager.get_image_uid(str(image_path))
            version_before = manager.project_data["project_data_version_id"]
            relocated_dir = root / "relocated"
            relocated_dir.mkdir()
            relocated = relocated_dir / image_path.name
            os.replace(image_path, relocated)
            relocation = manager.relocate_registered_images(
                [{"old_path": str(image_path), "new_path": str(relocated)}]
            )
            self.assertEqual(len(relocation["relocated"]), 1)
            changed = manager.apply_image_path_remap(
                relocation["relocated"], save=True
            )
            self.assertEqual(changed, 1)
            self.assertEqual(manager.get_image_uid(str(relocated)), uid_before)
            self.assertEqual(
                manager.project_data["project_data_version_id"], version_before
            )
            reloaded = ProjectManager()
            reloaded.load_project(manager.current_project_path)
            self.assertEqual(reloaded.get_image_uid(str(relocated)), uid_before)

    def test_relocation_rejects_same_name_with_different_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager, image_path = self._manager(root)
            manager.initialize_integrity_baseline()
            replacement_dir = root / "replacement"
            replacement_dir.mkdir()
            replacement = replacement_dir / image_path.name
            Image.new("RGB", (16, 12), color=(1, 2, 3)).save(replacement)

            relocation = manager.relocate_registered_images(
                [{"old_path": str(image_path), "new_path": str(replacement)}]
            )

            self.assertEqual(relocation["relocated"], [])
            self.assertEqual(
                relocation["rejected"][0]["reason"],
                "relocation_digest_mismatch",
            )
            self.assertIn(str(image_path), manager.project_data["images"])

    def test_only_training_facts_advance_data_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager, image_path = self._manager(root)
            manager.initialize_integrity_baseline()
            initial = manager.project_data["project_data_version_id"]
            manager.set_image_provenance(
                str(image_path), {"review_note": "display-only"}, save=True
            )
            self.assertEqual(manager.project_data["project_data_version_id"], initial)
            manager.update_auto_box(
                str(image_path),
                "Thorax",
                [2, 2, 9, 9],
                description_text="Auto-Annotated",
                save=True,
            )
            self.assertEqual(manager.project_data["project_data_version_id"], initial)
            manager.update_label(
                str(image_path),
                "Head",
                [[1, 1], [11, 1], [8, 9]],
                box=[1, 1, 11, 9],
                save=True,
            )
            self.assertNotEqual(manager.project_data["project_data_version_id"], initial)

    def test_reviewed_blink_trajectory_advances_data_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager, image_path = self._manager(root)
            manager.initialize_integrity_baseline()
            initial = manager.project_data["project_data_version_id"]
            manager.update_trajectory(
                str(image_path),
                "Head",
                [
                    {"box": [1, 1, 12, 10]},
                    {"box": [2, 2, 10, 8]},
                ],
                save=True,
            )
            self.assertNotEqual(
                manager.project_data["project_data_version_id"], initial
            )

    def test_legacy_truth_requires_explicit_attestation(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager, image_path = self._manager(Path(tmp))
            label = manager.project_data["labels"][str(image_path)]
            label.pop(LABEL_PART_METADATA_FIELD, None)
            manager._mark_sqlite_label_dirty(str(image_path))
            manager.save_project()
            with self.assertRaises(ProjectIntegrityRegistryError) as raised:
                manager.initialize_integrity_baseline(
                    legacy_truth_attestation=False
                )
            self.assertEqual(
                raised.exception.code, "legacy_truth_attestation_required"
            )
            self.assertEqual(
                manager.integrity_registry_state()["status"], "uninitialized"
            )
            snapshot = manager.initialize_integrity_baseline(
                legacy_truth_attestation=True,
                note="Researcher reviewed the legacy polygon source.",
            )
            self.assertEqual(snapshot["status"], "registered")

    def test_training_snapshot_uses_current_registered_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager, _image_path = self._manager(Path(tmp))
            manager.initialize_integrity_baseline()
            snapshot = get_training_baseline_snapshot(
                manager.current_database_path
            )
            self.assertEqual(
                snapshot["data_version_id"],
                manager.project_data["project_data_version_id"],
            )


if __name__ == "__main__":
    unittest.main()
