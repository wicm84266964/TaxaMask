import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from AntSleap.core.project import ProjectManager
from AntSleap.core.project_sqlite_loader import load_2d_sqlite_project_manifest
from AntSleap.core.project_sqlite_migration import migrate_legacy_2d_json_to_sqlite
from tests.test_2d_json_to_sqlite_migration import _legacy_project_payload, _write_json


class Project2DSQLiteLoadTests(unittest.TestCase):
    def _manager_with_runtime_state(self, root):
        manager = ProjectManager()
        manager.create_project("existing", root / "existing")
        manager.project_data["labels"]["existing-image"] = {"status": "labeled"}
        manager._sqlite_dirty_images = {"dirty-image"}
        manager._sqlite_deleted_images = {"deleted-image"}
        manager._sqlite_label_dirty_images = {"dirty-label"}
        manager._sqlite_project_dirty = True
        manager._pending_project_data_version_id = "pending-version"
        manager._traceability_backfill_needed = True
        manager._legacy_json_write_enabled = True
        manager.known_relocated_roots = [
            {"marker": "old-root", "relocated_root": "new-root"}
        ]
        manager._last_label_journal_fsync = 123.5
        manager._image_path_identity_cache = {"cached-image"}
        manager._image_path_identity_cache_signature = (123, 1)
        return manager

    def test_failed_load_restores_complete_manager_runtime_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = self._manager_with_runtime_state(root)
            before = copy.deepcopy(manager.__dict__)
            target_path = root / "target.json"
            target_path.write_text(json.dumps({"name": "target"}), encoding="utf-8")

            def fail_after_clear(*_args, **_kwargs):
                manager.clear()
                manager.project_data["name"] = "partial"
                manager.known_relocated_roots = [
                    {"marker": "partial-root", "relocated_root": "partial-target"}
                ]
                manager._last_label_journal_fsync = 999.0
                raise RuntimeError("injected load failure")

            with patch.object(manager, "_snapshot_runtime_state", wraps=manager._snapshot_runtime_state) as snapshot:
                with patch.object(manager, "_apply_loaded_project_data", side_effect=fail_after_clear):
                    with self.assertRaisesRegex(RuntimeError, "injected load failure"):
                        manager.load_project(target_path)

            snapshot.assert_called_once_with()
            self.assertEqual(manager.__dict__, before)

    def test_failed_create_restores_complete_manager_runtime_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = self._manager_with_runtime_state(root)
            before = copy.deepcopy(manager.__dict__)

            def fail_after_clear(*_args, **_kwargs):
                manager.current_project_path = "partial-project"
                manager.current_database_path = "partial-database"
                manager.project_data = {"name": "partial"}
                manager.known_relocated_roots = [
                    {"marker": "partial-root", "relocated_root": "partial-target"}
                ]
                manager._last_label_journal_fsync = 999.0
                raise RuntimeError("injected create failure")

            with patch.object(manager, "_snapshot_runtime_state", wraps=manager._snapshot_runtime_state) as snapshot:
                with patch.object(manager, "_create_sqlite_project_storage", side_effect=fail_after_clear):
                    with self.assertRaisesRegex(RuntimeError, "injected create failure"):
                        manager.create_project("failed", root / "failed")

            snapshot.assert_called_once_with()
            self.assertEqual(manager.__dict__, before)

    def test_deep_runtime_snapshot_restores_in_place_nested_mutations(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager_with_runtime_state(Path(tmp))
            before = copy.deepcopy(manager.__dict__)

            shallow_state = manager._snapshot_runtime_state()
            self.assertIs(shallow_state["project_data"], manager.project_data)
            self.assertIs(shallow_state["_sqlite_dirty_images"], manager._sqlite_dirty_images)

            deep_state = manager._snapshot_runtime_state(deep=True)
            self.assertIsNot(deep_state["project_data"], manager.project_data)
            self.assertIsNot(deep_state["_sqlite_dirty_images"], manager._sqlite_dirty_images)
            manager.project_data["labels"]["existing-image"]["status"] = "partial"
            manager.known_relocated_roots[0]["marker"] = "mutated-root"
            manager._sqlite_dirty_images.add("staged-image")

            manager._restore_runtime_state(deep_state)

            self.assertEqual(manager.__dict__, before)

    def test_sqlite_reload_rebuilds_stl_label_mirrors_from_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = ProjectManager()
            manager.create_project("stl-review", root / "review")
            image_path = root / "dorsal.png"
            image_path.write_bytes(b"rendered-view")
            manager.add_images([image_path], save=False)
            image_key = manager.project_data["images"][0]
            provenance = {
                "schema_version": "ant3d_stl_review_provenance_v1",
                "source_type": "stl_rendered_view",
                "view_name": "dorsal",
                "specimen_id": "specimen-01",
                "metadata_ref": "specimens/specimen-01/metadata.json",
            }
            manager.set_image_provenance(image_key, provenance, save=False)
            manager.project_data["labels"][image_key].update(
                {
                    "view": "dorsal",
                    "specimen_id": "specimen-01",
                    "metadata_ref": "specimens/specimen-01/metadata.json",
                    "review_mode": "stl_rendered_view",
                }
            )
            manager._mark_sqlite_label_dirty(image_key)
            manager.save_project()

            reloaded = ProjectManager()
            reloaded.load_project(manager.current_project_path)
            reloaded_image = reloaded.project_data["images"][0]
            reloaded_provenance = reloaded.get_image_provenance(reloaded_image)
            reloaded_label = reloaded.project_data["labels"][reloaded_image]

            self.assertEqual(reloaded_provenance, provenance)
            self.assertEqual(reloaded_label["view"], "dorsal")
            self.assertEqual(reloaded_label["specimen_id"], "specimen-01")
            self.assertEqual(
                reloaded_label["metadata_ref"],
                "specimens/specimen-01/metadata.json",
            )
            self.assertEqual(reloaded_label["review_mode"], "stl_rendered_view")

    def test_manifest_loads_sqlite_project_into_project_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_json = root / "legacy_project.json"
            db_path = root / "legacy_project.taxamask.sqlite"
            manifest_path = root / "legacy_project.sqlite_manifest.json"
            report_path = root / "migration_report.json"
            _write_json(source_json, _legacy_project_payload())

            migrate_legacy_2d_json_to_sqlite(
                source_json,
                database_path=db_path,
                manifest_path=manifest_path,
                report_path=report_path,
            )

            manager = ProjectManager()
            manager.load_project(manifest_path)

            ant1 = str((root / "images" / "ant1.png").resolve())
            ant2 = str((root / "images" / "ant2.png").resolve())
            self.assertEqual(manager.current_storage_backend, "sqlite")
            self.assertEqual(Path(manager.current_database_path), db_path)
            self.assertEqual(manager.current_project_path, str(manifest_path.resolve()))
            self.assertEqual(manager.project_data["name"], "Legacy ants")
            self.assertEqual(manager.project_data["images"], [ant1, ant2])
            self.assertEqual(manager.project_data["taxonomy"], ["Head", "Eye", "Gaster"])
            self.assertEqual(manager.project_data["locator_scope"], ["Head"])
            self.assertEqual(manager.project_data["taxon_label"], "Species")

            label = manager.project_data["labels"][ant1]
            self.assertEqual(label["status"], "labeled")
            self.assertEqual(label["genus"], "Formica")
            self.assertEqual(label["taxon"], "Formica rufa")
            self.assertEqual(label["taxon_rank"], "species")
            self.assertEqual(label["taxon_metadata"], {"authority": "Linnaeus"})
            self.assertEqual(label["parts"]["Head"], [[1.0, 2.0], [5.0, 2.0], [5.0, 6.0], [1.0, 6.0]])
            self.assertEqual(label["boxes"]["Head"], [0.0, 0.0, 10.0, 12.0])
            self.assertEqual(label["shrink_loose_boxes"]["Eye"], [2.0, 3.0, 4.0, 5.0])
            self.assertEqual(label["auto_boxes"]["Gaster"], [10.0, 20.0, 30.0, 40.0])
            self.assertEqual(label["auto_box_meta"]["Gaster"]["source"], "vlm_first_mile")
            self.assertEqual(label["auto_box_meta"]["Gaster"]["review_status"], "draft")
            self.assertEqual(label["auto_box_meta"]["Gaster"]["confidence"], 0.92)
            self.assertEqual(label["descriptions"]["Gaster"], "Auto-Annotated")
            self.assertEqual(label["description_sources"]["Head"], {"source": "paper"})
            self.assertEqual(label["trajectories"]["Eye"]["parent_context"]["parent_part"], "Head")

            self.assertEqual(manager.project_data["labels"][ant2]["status"], "unlabeled")
            self.assertEqual(manager.project_data["scales"][ant1], 12.5)
            self.assertEqual(manager.project_data["image_provenance"][ant1]["source_type"], "pdf_candidate")
            self.assertEqual(manager.project_data["image_provenance"][ant1]["manual_image_group"], "review_ready")
            self.assertEqual(manager.project_data["image_groups"]["custom_groups"][0]["id"], "review_ready")
            self.assertEqual(manager.project_data["vlm_preannotation"]["image_group"], "review_ready")
            self.assertEqual(manager.project_data["model_profiles"]["active_profile_id"], "profile_1")

    def test_sqlite_manifest_save_without_changes_leaves_manifest_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_json = root / "legacy_project.json"
            db_path = root / "project.sqlite"
            manifest_path = root / "project_manifest.json"
            report_path = root / "migration_report.json"
            _write_json(source_json, _legacy_project_payload())
            migrate_legacy_2d_json_to_sqlite(
                source_json,
                database_path=db_path,
                manifest_path=manifest_path,
                report_path=report_path,
            )
            manifest_before = manifest_path.read_text(encoding="utf-8")

            manager = ProjectManager()
            manager.load_project(manifest_path)
            self.assertFalse(manager.save_project())

            self.assertEqual(manifest_path.read_text(encoding="utf-8"), manifest_before)
            self.assertEqual(json.loads(manifest_before)["storage_backend"], "sqlite")

    def test_loader_preserves_integrity_check_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_json = root / "legacy_project.json"
            db_path = root / "project.sqlite"
            manifest_path = root / "project_manifest.json"
            report_path = root / "migration_report.json"
            _write_json(source_json, _legacy_project_payload())
            migrate_legacy_2d_json_to_sqlite(
                source_json,
                database_path=db_path,
                manifest_path=manifest_path,
                report_path=report_path,
            )

            loaded = load_2d_sqlite_project_manifest(manifest_path)
            self.assertEqual(loaded["integrity_check"], ["ok"])
            self.assertEqual(loaded["database_path"], str(db_path))


if __name__ == "__main__":
    unittest.main()
