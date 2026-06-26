import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from AntSleap.core.project import ProjectManager
from AntSleap.core.project_sqlite_loader import load_2d_sqlite_project_manifest
from AntSleap.core.project_sqlite_migration import migrate_legacy_2d_json_to_sqlite
from AntSleap.core.project_sqlite_writer import finish_vlm_run, record_vlm_image_result
from tests.test_2d_json_to_sqlite_migration import _legacy_project_payload, _write_json


def _sqlite_manager(root):
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
    manager = ProjectManager()
    manager.load_project(manifest_path)
    return manager, manifest_path, db_path


class Project2DSQLiteSaveTests(unittest.TestCase):
    def test_update_label_persists_only_through_sqlite_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager, manifest_path, _db_path = _sqlite_manager(root)
            manifest_before = manifest_path.read_text(encoding="utf-8")
            image_path = manager.project_data["images"][0]

            manager.update_label(
                image_path,
                "Eye",
                [[2, 2], [8, 2], [8, 9], [2, 9]],
                description_text="manual eye",
                box=[1, 1, 9, 10],
                save=False,
            )

            self.assertTrue(manager.save_project())
            self.assertEqual(manifest_path.read_text(encoding="utf-8"), manifest_before)

            reloaded = ProjectManager()
            reloaded.load_project(manifest_path)
            label = reloaded.project_data["labels"][image_path]
            self.assertEqual(label["parts"]["Eye"], [[2.0, 2.0], [8.0, 2.0], [8.0, 9.0], [2.0, 9.0]])
            self.assertEqual(label["boxes"]["Eye"], [1.0, 1.0, 9.0, 10.0])
            self.assertEqual(label["descriptions"]["Eye"], "manual eye")

    def test_auto_box_review_scale_and_provenance_persist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager, manifest_path, db_path = _sqlite_manager(root)
            image_path = manager.project_data["images"][0]

            manager.update_auto_box(
                image_path,
                "Eye",
                [3, 4, 12, 16],
                description_text="Auto-Annotated",
                source_meta={
                    "source": "vlm_first_mile",
                    "review_status": "draft",
                    "confidence": 0.77,
                    "source_run_id": "run_stage5",
                    "report_path": "reports/run_stage5.json",
                },
                save=False,
            )
            manager.set_auto_box_review_status(image_path, "Eye", "confirmed", save=False)
            manager.set_scale(image_path, 22.5, save=False)
            manager.set_image_provenance(image_path, {"source_type": "manual_import", "manual_image_group": "review_ready"}, save=False)
            self.assertTrue(manager.save_project())

            reloaded = ProjectManager()
            reloaded.load_project(manifest_path)
            label = reloaded.project_data["labels"][image_path]
            self.assertEqual(label["auto_boxes"]["Eye"], [3.0, 4.0, 12.0, 16.0])
            self.assertEqual(label["auto_box_meta"]["Eye"]["review_status"], "confirmed")
            self.assertEqual(label["auto_box_meta"]["Eye"]["source_run_id"], "run_stage5")
            self.assertEqual(reloaded.project_data["scales"][image_path], 22.5)
            self.assertEqual(reloaded.project_data["image_provenance"][image_path]["source_type"], "manual_import")

            conn = sqlite3.connect(db_path)
            try:
                row = conn.execute(
                    """
                    SELECT status, box_count
                    FROM vlm_image_results
                    WHERE run_id = ?
                    """,
                    ("run_stage5",),
                ).fetchone()
            finally:
                conn.close()
            self.assertIsNone(row)

    def test_add_and_remove_images_persist_without_rewriting_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager, manifest_path, db_path = _sqlite_manager(root)
            original_image = manager.project_data["images"][0]
            new_image = root / "images" / "ant3.png"
            new_image.parent.mkdir(exist_ok=True)
            new_image.write_bytes(b"not a real image for metadata test")

            manager.add_images([str(new_image)], save=False)
            manager.remove_images([original_image], save=False)
            self.assertTrue(manager.save_project())

            reloaded = ProjectManager()
            reloaded.load_project(manifest_path)
            self.assertNotIn(original_image, reloaded.project_data["images"])
            self.assertIn(str(new_image.resolve()), reloaded.project_data["images"])

            conn = sqlite3.connect(db_path)
            try:
                paths = [row[0] for row in conn.execute("SELECT path FROM images ORDER BY path").fetchall()]
            finally:
                conn.close()
            self.assertFalse(any(path.endswith("ant1.png") for path in paths))
            self.assertTrue(any(path.endswith("ant3.png") for path in paths))

    def test_project_settings_and_taxonomy_rename_persist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager, manifest_path, _db_path = _sqlite_manager(root)
            image_path = manager.project_data["images"][0]

            manager.set_vlm_preannotation_settings(
                {
                    "target_parts": ["Eye"],
                    "processing_scope": "all_images",
                    "image_group": "original",
                    "concurrency": 2,
                },
                save=False,
            )
            manager.rename_taxonomy_part("Eye", "CompoundEye", save=False)
            self.assertTrue(manager.save_project())

            reloaded = ProjectManager()
            reloaded.load_project(manifest_path)
            self.assertIn("CompoundEye", reloaded.project_data["taxonomy"])
            self.assertNotIn("Eye", reloaded.project_data["taxonomy"])
            self.assertEqual(reloaded.project_data["vlm_preannotation"]["target_parts"], ["CompoundEye"])
            label = reloaded.project_data["labels"][image_path]
            self.assertIn("CompoundEye", label["shrink_loose_boxes"])
            self.assertIn("CompoundEye", label["trajectories"])

    def test_loader_sees_sqlite_rows_after_direct_flush(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager, manifest_path, _db_path = _sqlite_manager(root)
            image_path = manager.project_data["images"][0]

            manager.set_taxon(image_path, "Formica polyctena", taxon_rank="species", save=False)
            self.assertTrue(manager.flush_sqlite_changes(image_paths=[image_path], integrity_check=True))

            loaded = load_2d_sqlite_project_manifest(manifest_path)
            label = loaded["project_data"]["labels"][image_path]
            self.assertEqual(label["taxon"], "Formica polyctena")
            self.assertEqual(label["taxon_rank"], "species")

    def test_vlm_image_result_and_run_summary_are_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager, _manifest_path, db_path = _sqlite_manager(root)
            image_path = manager.project_data["images"][0]

            manager.update_auto_box(
                image_path,
                "Eye",
                [3, 4, 12, 16],
                description_text="Auto-Annotated",
                source_meta={
                    "source": "vlm_first_mile",
                    "review_status": "draft",
                    "confidence": 0.77,
                    "source_run_id": "vlm_run_1",
                    "report_path": "reports/vlm_run_1.json",
                },
                save=False,
            )
            self.assertTrue(manager.flush_sqlite_changes(image_paths=[image_path], project_dirty=True))
            record_vlm_image_result(
                manager,
                "vlm_run_1",
                image_path,
                status="done",
                raw_response_ref="reports/vlm_run_1.json",
                box_count=1,
            )
            finish_vlm_run(manager, "vlm_run_1", status="finished", summary={"saved_box_count": 1})

            conn = sqlite3.connect(db_path)
            try:
                run_row = conn.execute(
                    "SELECT status, summary_json FROM vlm_runs WHERE run_id = ?",
                    ("vlm_run_1",),
                ).fetchone()
                result_row = conn.execute(
                    """
                    SELECT status, raw_response_ref, box_count
                    FROM vlm_image_results
                    WHERE run_id = ?
                    """,
                    ("vlm_run_1",),
                ).fetchone()
            finally:
                conn.close()

            self.assertEqual(run_row[0], "finished")
            self.assertEqual(json.loads(run_row[1])["saved_box_count"], 1)
            self.assertEqual(result_row, ("done", "reports/vlm_run_1.json", 1))

    def test_delete_blink_trajectory_dataset_can_defer_sqlite_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager, manifest_path, _db_path = _sqlite_manager(root)
            image_path = manager.project_data["images"][0]

            removed = manager.delete_blink_trajectory_dataset("Head", "Eye", save=False)
            self.assertEqual(removed, 1)
            self.assertTrue(manager.save_project())

            reloaded = ProjectManager()
            reloaded.load_project(manifest_path)
            self.assertNotIn("Eye", reloaded.project_data["labels"][image_path].get("trajectories", {}))


if __name__ == "__main__":
    unittest.main()
