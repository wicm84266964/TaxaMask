import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from AntSleap.core.project_sqlite_migration import (
    DEFAULT_LEGACY_VLM_RUN_ID,
    MIGRATION_REPORT_SCHEMA_VERSION,
    migrate_legacy_2d_json_to_sqlite,
)
from AntSleap.core.sqlite_storage import read_project_manifest, resolve_manifest_database_path


def _write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _legacy_project_payload():
    return {
        "name": "Legacy ants",
        "taxonomy": ["Head", "Eye", "Gaster"],
        "locator_scope": ["Head"],
        "project_template": "ant",
        "category_supercategory": "biological_structure",
        "taxon_label": "Species",
        "images": ["images/ant1.png", "images/ant2.png"],
        "labels": {
            "images/ant1.png": {
                "parts": {
                    "Head": [[1, 2], [5, 2], [5, 6], [1, 6]],
                },
                "boxes": {
                    "Head": [0, 0, 10, 12],
                },
                "shrink_loose_boxes": {
                    "Eye": [2, 3, 4, 5],
                },
                "auto_boxes": {
                    "Gaster": [10, 20, 30, 40],
                },
                "auto_box_meta": {
                    "Gaster": {
                        "source": "vlm_first_mile",
                        "review_status": "draft",
                        "confidence": 0.92,
                        "source_run_id": "run_123",
                        "report_path": "reports/vlm_run_123.json",
                        "reason": "visible in image",
                    },
                },
                "trajectories": {
                    "Eye": {
                        "frames": [
                            {"step": 0, "alpha": 0.0, "box": [1, 2, 6, 7]},
                            {"step": 1, "alpha": 1.0, "box": [2, 3, 4, 5], "is_golden": True},
                        ],
                        "parent_context": {"parent_part": "Head", "source": "manual"},
                    },
                },
                "descriptions": {
                    "Head": "manual head note",
                    "Gaster": "Auto-Annotated",
                },
                "description_sources": {
                    "Head": {"source": "paper"},
                },
                "status": "labeled",
                "genus": "Formica",
                "taxon": "Formica rufa",
                "taxon_rank": "species",
                "taxon_metadata": {"authority": "Linnaeus"},
            },
        },
        "scales": {
            "images/ant1.png": 12.5,
        },
        "image_provenance": {
            "images/ant1.png": {
                "source_type": "pdf_candidate",
                "manual_image_group": "review_ready",
            },
        },
        "image_groups": {
            "custom_groups": [
                {
                    "id": "review_ready",
                    "name": "Review Ready",
                    "images": ["images/ant1.png"],
                }
            ],
        },
        "vlm_preannotation": {
            "target_parts": ["Gaster"],
            "processing_scope": "image_group",
            "image_group": "review_ready",
            "concurrency": 1,
            "prompt_profile_id": "prompt_default",
        },
        "model_profiles": {
            "active_profile_id": "profile_1",
            "profiles": [
                {"profile_id": "profile_1", "name": "Default profile"},
            ],
        },
        "cascade_routes": {"version": "project-v2", "routes": []},
    }


class Legacy2DJsonToSQLiteMigrationTests(unittest.TestCase):
    def test_full_legacy_project_migrates_without_changing_source_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_json = root / "legacy_project.json"
            db_path = root / "legacy_project.taxamask.sqlite"
            manifest_path = root / "legacy_project.sqlite_manifest.json"
            report_path = root / "reports" / "migration_report.json"
            _write_json(source_json, _legacy_project_payload())
            original_text = source_json.read_text(encoding="utf-8")
            events = []

            result = migrate_legacy_2d_json_to_sqlite(
                source_json,
                database_path=db_path,
                manifest_path=manifest_path,
                report_path=report_path,
                progress_callback=lambda done, total, message: events.append((done, total, message)),
            )

            self.assertEqual(source_json.read_text(encoding="utf-8"), original_text)
            self.assertTrue(db_path.exists())
            self.assertTrue(manifest_path.exists())
            self.assertTrue(report_path.exists())
            self.assertTrue(Path(result.legacy_json_backup_path).exists())
            self.assertEqual(Path(result.legacy_json_backup_path).read_text(encoding="utf-8"), original_text)
            self.assertEqual(events[-1][0], events[-1][1])
            self.assertIn("manifest", events[-1][2])

            expected_stats = {
                "image_count": 2,
                "label_count": 2,
                "nonempty_label_count": 1,
                "polygon_count": 1,
                "manual_box_count": 1,
                "shrink_loose_box_count": 1,
                "auto_box_count": 1,
                "auto_box_review_count": 1,
                "trajectory_count": 1,
                "scale_count": 1,
                "provenance_count": 1,
                "image_group_count": 1,
                "image_group_member_count": 1,
                "taxonomy_part_count": 3,
                "model_profile_count": 1,
                "vlm_run_count": 1,
                "vlm_image_result_count": 1,
            }
            for key, value in expected_stats.items():
                self.assertEqual(result.stats[key], value, key)

            manifest = read_project_manifest(manifest_path)
            self.assertEqual(Path(resolve_manifest_database_path(manifest_path, manifest)), db_path)
            self.assertEqual(manifest["project_type"], "2d_image_annotation")
            self.assertEqual(manifest["migration_stats"]["auto_box_count"], 1)

            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["schema_version"], MIGRATION_REPORT_SCHEMA_VERSION)
            self.assertEqual(report["stats"], result.stats)
            self.assertEqual(report["integrity_check"], ["ok"])

    def test_migrated_rows_preserve_labels_vlm_boxes_and_blink_trajectory(self):
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

            conn = sqlite3.connect(db_path)
            try:
                project_row = conn.execute(
                    "SELECT name, taxonomy_json, locator_scope_json, settings_json FROM projects WHERE id = 1"
                ).fetchone()
                self.assertEqual(project_row[0], "Legacy ants")
                self.assertEqual(json.loads(project_row[1]), ["Head", "Eye", "Gaster"])
                self.assertEqual(json.loads(project_row[2]), ["Head"])
                settings = json.loads(project_row[3])
                self.assertEqual(settings["vlm_preannotation"]["image_group"], "review_ready")

                label_row = conn.execute(
                    """
                    SELECT l.status, l.genus, l.taxon, l.taxon_rank,
                           l.taxon_metadata_json, l.descriptions_json,
                           l.description_sources_json
                    FROM labels l
                    JOIN images i ON i.id = l.image_id
                    WHERE i.path = ?
                    """,
                    ("images/ant1.png",),
                ).fetchone()
                self.assertEqual(label_row[0], "labeled")
                self.assertEqual(label_row[1], "Formica")
                self.assertEqual(label_row[2], "Formica rufa")
                self.assertEqual(label_row[3], "species")
                self.assertEqual(json.loads(label_row[4]), {"authority": "Linnaeus"})
                self.assertEqual(json.loads(label_row[5])["Gaster"], "Auto-Annotated")
                self.assertEqual(json.loads(label_row[6])["Head"], {"source": "paper"})

                polygon_points = conn.execute(
                    """
                    SELECT p.points_json
                    FROM label_polygons p
                    JOIN labels l ON l.id = p.label_id
                    JOIN images i ON i.id = l.image_id
                    WHERE i.path = ? AND p.part_name = ?
                    """,
                    ("images/ant1.png", "Head"),
                ).fetchone()[0]
                self.assertEqual(json.loads(polygon_points), [[1.0, 2.0], [5.0, 2.0], [5.0, 6.0], [1.0, 6.0]])

                box_rows = conn.execute(
                    """
                    SELECT b.part_name, b.box_type, b.x1, b.y1, b.x2, b.y2
                    FROM label_boxes b
                    JOIN labels l ON l.id = b.label_id
                    JOIN images i ON i.id = l.image_id
                    WHERE i.path = ?
                    ORDER BY b.box_type, b.part_name
                    """,
                    ("images/ant1.png",),
                ).fetchall()
                self.assertEqual(
                    box_rows,
                    [
                        ("Head", "manual", 0.0, 0.0, 10.0, 12.0),
                        ("Eye", "shrink_loose", 2.0, 3.0, 4.0, 5.0),
                    ],
                )

                auto_row = conn.execute(
                    """
                    SELECT part_name, source, confidence, review_status, run_id, raw_response_ref, metadata_json
                    FROM auto_boxes
                    """
                ).fetchone()
                self.assertEqual(auto_row[:6], ("Gaster", "vlm_first_mile", 0.92, "draft", "run_123", "reports/vlm_run_123.json"))
                self.assertEqual(json.loads(auto_row[6])["reason"], "visible in image")

                run_row = conn.execute(
                    "SELECT run_id, status, prompt_profile_id, target_parts_json FROM vlm_runs"
                ).fetchone()
                self.assertEqual(run_row[0], "run_123")
                self.assertEqual(run_row[1], "imported_from_legacy_json")
                self.assertEqual(run_row[2], "prompt_default")
                self.assertEqual(json.loads(run_row[3]), ["Gaster"])
                result_row = conn.execute("SELECT status, box_count FROM vlm_image_results").fetchone()
                self.assertEqual(result_row, ("imported_from_legacy_json", 1))

                trajectory_row = conn.execute(
                    """
                    SELECT t.child_part_name, t.parent_part_name, t.trajectory_json, t.parent_context_json
                    FROM blink_trajectories t
                    JOIN labels l ON l.id = t.label_id
                    JOIN images i ON i.id = l.image_id
                    WHERE i.path = ?
                    """,
                    ("images/ant1.png",),
                ).fetchone()
                self.assertEqual(trajectory_row[0], "Eye")
                self.assertEqual(trajectory_row[1], "Head")
                self.assertEqual(len(json.loads(trajectory_row[2])["frames"]), 2)
                self.assertEqual(json.loads(trajectory_row[3])["source"], "manual")

                scale_row = conn.execute("SELECT pixels_per_mm FROM image_scales").fetchone()
                self.assertEqual(scale_row[0], 12.5)
                provenance = json.loads(conn.execute("SELECT provenance_json FROM image_provenance").fetchone()[0])
                self.assertEqual(provenance["source_type"], "pdf_candidate")
            finally:
                conn.close()

    def test_vlm_auto_box_without_run_id_gets_legacy_import_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_json = root / "legacy_project.json"
            payload = _legacy_project_payload()
            payload["labels"]["images/ant1.png"]["auto_box_meta"]["Gaster"].pop("source_run_id")
            _write_json(source_json, payload)

            migrate_legacy_2d_json_to_sqlite(
                source_json,
                database_path=root / "project.sqlite",
                manifest_path=root / "project_manifest.json",
                report_path=root / "migration_report.json",
            )

            conn = sqlite3.connect(root / "project.sqlite")
            try:
                run_id = conn.execute("SELECT run_id FROM auto_boxes").fetchone()[0]
                self.assertEqual(run_id, DEFAULT_LEGACY_VLM_RUN_ID)
                self.assertEqual(conn.execute("SELECT run_id FROM vlm_runs").fetchone()[0], DEFAULT_LEGACY_VLM_RUN_ID)
            finally:
                conn.close()

    def test_bad_json_does_not_create_outputs_or_modify_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_json = root / "broken.json"
            bad_text = '{"name": "Broken", "images": ['
            source_json.write_text(bad_text, encoding="utf-8")
            db_path = root / "broken.sqlite"
            manifest_path = root / "broken_manifest.json"
            report_path = root / "broken_report.json"
            events = []

            with self.assertRaises(json.JSONDecodeError):
                migrate_legacy_2d_json_to_sqlite(
                    source_json,
                    database_path=db_path,
                    manifest_path=manifest_path,
                    report_path=report_path,
                    progress_callback=lambda done, total, message: events.append((done, total, message)),
                )

            self.assertEqual(source_json.read_text(encoding="utf-8"), bad_text)
            self.assertFalse(db_path.exists())
            self.assertFalse(manifest_path.exists())
            self.assertFalse(report_path.exists())
            self.assertFalse(list(root.glob("*.tmp_migration*")))
            self.assertTrue(any("失败" in message for _, _, message in events))

    def test_existing_outputs_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_json = root / "legacy_project.json"
            db_path = root / "existing.sqlite"
            manifest_path = root / "manifest.json"
            report_path = root / "report.json"
            _write_json(source_json, _legacy_project_payload())
            db_path.write_text("existing db", encoding="utf-8")
            manifest_path.write_text("existing manifest", encoding="utf-8")
            report_path.write_text("existing report", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                migrate_legacy_2d_json_to_sqlite(
                    source_json,
                    database_path=db_path,
                    manifest_path=manifest_path,
                    report_path=report_path,
                )

            self.assertEqual(db_path.read_text(encoding="utf-8"), "existing db")
            self.assertEqual(manifest_path.read_text(encoding="utf-8"), "existing manifest")
            self.assertEqual(report_path.read_text(encoding="utf-8"), "existing report")

    def test_output_paths_must_not_point_at_source_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_json = root / "legacy_project.json"
            _write_json(source_json, _legacy_project_payload())

            with self.assertRaisesRegex(ValueError, "sqlite_report_must_not_overwrite_legacy_json"):
                migrate_legacy_2d_json_to_sqlite(
                    source_json,
                    database_path=root / "project.sqlite",
                    manifest_path=root / "project_manifest.json",
                    report_path=source_json,
                )

            with self.assertRaisesRegex(ValueError, "sqlite_database_path_conflicts_with_output"):
                migrate_legacy_2d_json_to_sqlite(
                    source_json,
                    database_path=root / "same_output",
                    manifest_path=root / "project_manifest.json",
                    report_path=root / "same_output",
                )

            self.assertEqual(json.loads(source_json.read_text(encoding="utf-8"))["name"], "Legacy ants")

    def test_existing_sqlite_wal_artifact_blocks_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_json = root / "legacy_project.json"
            db_path = root / "project.sqlite"
            _write_json(source_json, _legacy_project_payload())
            Path(f"{db_path}-wal").write_text("existing wal", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                migrate_legacy_2d_json_to_sqlite(
                    source_json,
                    database_path=db_path,
                    manifest_path=root / "project_manifest.json",
                    report_path=root / "migration_report.json",
                )

            self.assertEqual(Path(f"{db_path}-wal").read_text(encoding="utf-8"), "existing wal")


if __name__ == "__main__":
    unittest.main()
