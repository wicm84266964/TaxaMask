import json
import tempfile
import unittest
from pathlib import Path

from AntSleap.core.project import ProjectManager
from AntSleap.core.project_sqlite_loader import load_2d_sqlite_project_manifest
from AntSleap.core.project_sqlite_migration import migrate_legacy_2d_json_to_sqlite
from tests.test_2d_json_to_sqlite_migration import _legacy_project_payload, _write_json


class Project2DSQLiteLoadTests(unittest.TestCase):
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
