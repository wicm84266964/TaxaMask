import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np

from AntSleap.core.file_integrity import QUICK_FILE_ALGORITHM, TREE_ALGORITHM
from AntSleap.core.project_integrity_registry import ProjectIntegrityRegistryError
from AntSleap.core.project_integrity_recovery import (
    inspect_project_integrity,
    register_current_asset_version,
)
from AntSleap.core.tif_integrity_bridge import relocate_tif_project_asset
from AntSleap.core.tif_project import TifProjectManager
from AntSleap.core.tif_volume_io import write_volume_sidecar


class TifIntegrityBridgeTests(unittest.TestCase):
    def _manager(self, root, *, explicit_review=True):
        project_root = root / "tif_project"
        manager = TifProjectManager()
        manager.create_project("tif_project", project_root)
        manager.location_registry_database_path = root / "locations.sqlite"
        manager.create_specimen_scaffold(
            "specimen_1",
            material_map={
                "materials": [
                    {
                        "id": 1,
                        "name": "head",
                        "display_name": "Head",
                        "trainable": True,
                    }
                ]
            },
        )
        source_rel = "specimens/specimen_1/working/source.tif"
        source_path = project_root / source_rel
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_bytes(b"source-volume-v1")
        manager.register_working_volume(
            "specimen_1",
            source_rel,
            [2, 3, 4],
            "uint16",
            save=False,
        )
        truth_rel = "specimens/specimen_1/labels/manual_truth.ome.zarr"
        truth_path = project_root / truth_rel
        metadata = write_volume_sidecar(
            truth_path,
            np.ones((2, 3, 4), dtype=np.uint16),
            role="manual_truth",
        )
        manager.register_label_volume(
            "specimen_1",
            "manual_truth",
            truth_rel,
            metadata["shape_zyx"],
            metadata["dtype"],
            status="reviewed",
            explicit_review=True,
            operation="truth_promotion",
            save=False,
        )
        if not explicit_review:
            manager.get_specimen("specimen_1")["labels"]["manual_truth"].pop(
                "review_audit", None
            )
        manager.set_review_status(
            "specimen_1", "train_ready", train_ready=True, save=True
        )
        return manager, source_path, truth_path

    def test_explicit_baseline_uses_quick_source_and_full_truth(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager, _source, _truth = self._manager(Path(tmp))
            self.assertEqual(
                manager.integrity_registry_state()["status"], "uninitialized"
            )
            snapshot = manager.initialize_integrity_baseline()
            source = next(
                item for item in snapshot["files"] if item["role"] == "source_volume"
            )
            truth = next(
                item for item in snapshot["files"] if item["role"] == "manual_truth"
            )
            self.assertEqual(source["hash_algorithm"], QUICK_FILE_ALGORITHM)
            self.assertEqual(truth["hash_algorithm"], TREE_ALGORITHM)
            self.assertNotIn(
                str(Path(tmp).resolve()), json.dumps(snapshot, ensure_ascii=False)
            )

    def test_draft_does_not_advance_but_review_and_truth_do(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager, _source, truth_path = self._manager(root)
            manager.initialize_integrity_baseline()
            baseline = manager.project_data["project_data_version_id"]
            manager.add_model_draft(
                "specimen_1",
                "predictions/draft.ome.zarr",
                [2, 3, 4],
                "uint16",
                "prediction_1",
                save=True,
            )
            self.assertEqual(manager.project_data["project_data_version_id"], baseline)
            manager.set_review_status(
                "specimen_1", "reviewed", train_ready=False, save=True
            )
            reviewed_version = manager.project_data["project_data_version_id"]
            self.assertNotEqual(reviewed_version, baseline)
            write_volume_sidecar(
                truth_path,
                np.full((2, 3, 4), 2, dtype=np.uint16),
                role="manual_truth",
            )
            manager._mark_manual_truth_data_changed()
            manager.save_project()
            self.assertNotEqual(
                manager.project_data["project_data_version_id"], reviewed_version
            )

    def test_unattested_legacy_truth_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager, _source, _truth = self._manager(
                Path(tmp), explicit_review=False
            )
            with self.assertRaises(ProjectIntegrityRegistryError) as raised:
                manager.initialize_integrity_baseline(
                    legacy_truth_attestation=False
                )
            self.assertEqual(
                raised.exception.code, "legacy_truth_attestation_required"
            )
            snapshot = manager.initialize_integrity_baseline(
                legacy_truth_attestation=True,
                note="Researcher reviewed the legacy manual truth.",
            )
            self.assertEqual(snapshot["status"], "registered")

    def test_same_content_relocation_keeps_data_version_and_restores_training_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager, source, _truth = self._manager(root)
            manager.initialize_integrity_baseline()
            version = manager.project_data["project_data_version_id"]
            moved = root / "relocated" / source.name
            moved.parent.mkdir()
            shutil.move(source, moved)

            issue = next(
                item
                for item in inspect_project_integrity(manager)["items"]
                if item["role"] == "source_volume"
            )
            self.assertEqual(issue["status"], "missing")
            operation = relocate_tif_project_asset(manager, issue, moved)

            self.assertTrue(operation["changed"])
            self.assertEqual(manager.project_data["project_data_version_id"], version)
            self.assertEqual(inspect_project_integrity(manager)["status"], "verified")
            self.assertEqual(
                manager.to_absolute(
                    manager.get_specimen("specimen_1")["working_volume"]["path"]
                ),
                str(moved),
            )

    def test_tif_content_change_requires_note_and_creates_new_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager, source, _truth = self._manager(root)
            manager.initialize_integrity_baseline()
            version = manager.project_data["project_data_version_id"]
            source.write_bytes(b"source-volume-v2")
            issue = next(
                item
                for item in inspect_project_integrity(manager)["items"]
                if item["role"] == "source_volume"
            )

            with self.assertRaisesRegex(ValueError, "note_required"):
                register_current_asset_version(manager, issue, note="")
            register_current_asset_version(
                manager,
                issue,
                note="Researcher intentionally replaced the source volume.",
            )

            self.assertNotEqual(manager.project_data["project_data_version_id"], version)
            self.assertEqual(inspect_project_integrity(manager)["status"], "verified")


if __name__ == "__main__":
    unittest.main()
