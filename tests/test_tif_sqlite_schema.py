import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from AntSleap.core.mesh_export import _mesh_coordinate_context
from AntSleap.core.sqlite_storage import get_schema_version, run_integrity_check
from AntSleap.core.tif_sqlite_schema import (
    TIF_SQLITE_PROJECT_TYPE,
    TIF_SQLITE_SCHEMA_NAME,
    TIF_SQLITE_SCHEMA_VERSION,
    create_tif_project_database,
    initialize_tif_project_schema,
    json_text,
    migrate_tif_project_database,
    validate_tif_project_schema,
)
from AntSleap.core.sqlite_storage import read_database_schema_version


class TifSQLiteSchemaTests(unittest.TestCase):
    LEGACY_TABLES = {
        "schema_migrations", "tif_projects", "specimens", "volume_assets",
        "label_layers", "material_maps", "parts", "part_rois", "part_reslices",
        "global_axis_proposals", "local_frame_proposals", "tif_models", "tif_runs",
        "tif_run_artifacts", "tif_events", "sqlite_sequence",
    }
    LEGACY_V1_VOLUME_ASSETS_DDL = """
        CREATE TABLE volume_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            specimen_id INTEGER NOT NULL,
            part_id INTEGER,
            asset_key TEXT NOT NULL DEFAULT '',
            role TEXT NOT NULL DEFAULT 'unknown',
            path TEXT NOT NULL DEFAULT '',
            format TEXT NOT NULL DEFAULT '',
            shape_zyx_json TEXT NOT NULL DEFAULT '[]',
            dtype TEXT NOT NULL DEFAULT '',
            spacing_zyx_json TEXT NOT NULL DEFAULT '[]',
            spacing_unit TEXT NOT NULL DEFAULT 'micrometer',
            orientation TEXT NOT NULL DEFAULT 'unknown',
            status TEXT NOT NULL DEFAULT '',
            source_format TEXT NOT NULL DEFAULT '',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (specimen_id) REFERENCES specimens(id) ON DELETE CASCADE,
            FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE CASCADE
        )
    """

    def test_v1_database_migrates_explicitly_to_v2_with_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "legacy_tif.taxamask.sqlite"
            connection = create_tif_project_database(db_path)
            try:
                connection.execute(
                    """
                    INSERT INTO specimens (specimen_id, display_name)
                    VALUES ('01-legacy', 'Legacy specimen')
                    """
                )
                connection.commit()
            finally:
                connection.close()

            connection = sqlite3.connect(db_path)
            try:
                connection.execute("PRAGMA foreign_keys = OFF")
                for (name,) in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'trigger'"
                ).fetchall():
                    connection.execute(f'DROP TRIGGER "{name}"')
                for (name,) in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall():
                    if name not in self.LEGACY_TABLES:
                        connection.execute(f'DROP TABLE "{name}"')
                connection.execute("DROP TABLE volume_assets")
                connection.execute(self.LEGACY_V1_VOLUME_ASSETS_DDL)
                specimen_row_id = connection.execute(
                    "SELECT id FROM specimens WHERE specimen_id = '01-legacy'"
                ).fetchone()[0]
                connection.execute(
                    """
                    INSERT INTO volume_assets (
                        specimen_id, asset_key, role, path, format,
                        shape_zyx_json, dtype, spacing_zyx_json
                    )
                    VALUES (?, 'legacy_default', 'manual_truth', ?, ?, ?, ?, ?)
                    """,
                    (
                        specimen_row_id,
                        "specimens/01-legacy/labels/default.ome.zarr",
                        "ant3d_volume_sidecar",
                        json_text([2, 3, 4]),
                        "uint16",
                        json_text([2.0, 3.0, 5.0]),
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO volume_assets (
                        specimen_id, asset_key, role, path, format,
                        shape_zyx_json, dtype, spacing_zyx_json,
                        spacing_unit, metadata_json
                    )
                    VALUES (?, 'explicit_verified', 'manual_truth', ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        specimen_row_id,
                        "specimens/01-legacy/labels/verified.ome.zarr",
                        "ant3d_volume_sidecar",
                        json_text([2, 3, 4]),
                        "uint16",
                        json_text([0.2, 0.3, 0.5]),
                        "millimeter",
                        json_text(
                            {
                                "scale_verified": True,
                                "scale_verification_source": "scanner_header",
                            }
                        ),
                    ),
                )
                connection.execute(
                    "DELETE FROM schema_migrations WHERE schema_name = ?",
                    (TIF_SQLITE_SCHEMA_NAME,),
                )
                connection.execute(
                    "INSERT INTO schema_migrations (schema_name, version) VALUES (?, 1)",
                    (TIF_SQLITE_SCHEMA_NAME,),
                )
                connection.execute("UPDATE tif_projects SET schema_version = 1 WHERE id = 1")
                connection.commit()
            finally:
                connection.close()

            result = migrate_tif_project_database(db_path)

            self.assertTrue(result["migrated"])
            self.assertTrue(Path(result["backup_path"]).is_file())
            self.assertEqual(
                read_database_schema_version(db_path, TIF_SQLITE_SCHEMA_NAME),
                TIF_SQLITE_SCHEMA_VERSION,
            )
            connection = sqlite3.connect(db_path)
            try:
                self.assertEqual(
                    connection.execute(
                        "SELECT display_name FROM specimens WHERE specimen_id = '01-legacy'"
                    ).fetchone()[0],
                    "Legacy specimen",
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT schema_version FROM tif_projects WHERE id = 1"
                    ).fetchone()[0],
                    2,
                )
                self.assertEqual(
                    [row[0] for row in connection.execute(
                        "SELECT version FROM schema_migrations WHERE schema_name = ? ORDER BY version",
                        (TIF_SQLITE_SCHEMA_NAME,),
                    ).fetchall()],
                    [1, 2],
                )
                scale_rows = {
                    row[0]: row[1:]
                    for row in connection.execute(
                        """
                        SELECT asset_key, spacing_zyx_json, spacing_unit, metadata_json
                        FROM volume_assets
                        ORDER BY asset_key
                        """
                    ).fetchall()
                }
                default_spacing, default_unit, default_metadata_json = scale_rows[
                    "legacy_default"
                ]
                default_metadata = json.loads(default_metadata_json)
                self.assertEqual(default_unit, "unknown")
                self.assertFalse(default_metadata["scale_verified"])
                self.assertEqual(
                    default_metadata["legacy_unverified_spacing_unit"],
                    "micrometer",
                )
                default_context = _mesh_coordinate_context(
                    json.loads(default_spacing),
                    default_unit,
                    scale_verified=default_metadata["scale_verified"],
                )
                self.assertEqual(default_context["mesh_purpose"], "observation")
                self.assertEqual(default_context["output_unit"], "unitless")

                verified_spacing, verified_unit, verified_metadata_json = scale_rows[
                    "explicit_verified"
                ]
                verified_metadata = json.loads(verified_metadata_json)
                self.assertEqual(verified_unit, "millimeter")
                self.assertTrue(verified_metadata["scale_verified"])
                verified_context = _mesh_coordinate_context(
                    json.loads(verified_spacing),
                    verified_unit,
                    scale_verified=verified_metadata["scale_verified"],
                )
                self.assertEqual(verified_context["mesh_purpose"], "measurement")
                self.assertEqual(verified_context["output_unit"], "millimeter")
                validate_tif_project_schema(connection)
            finally:
                connection.close()

    def test_initialize_schema_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "tif_project.taxamask.sqlite"
            conn = create_tif_project_database(db_path)
            try:
                self.assertEqual(get_schema_version(conn, TIF_SQLITE_SCHEMA_NAME), TIF_SQLITE_SCHEMA_VERSION)
                self.assertEqual(initialize_tif_project_schema(conn), TIF_SQLITE_SCHEMA_VERSION)
                self.assertEqual(run_integrity_check(conn), ["ok"])
                project = conn.execute("SELECT project_type FROM tif_projects WHERE id = 1").fetchone()
                self.assertEqual(project[0], TIF_SQLITE_PROJECT_TYPE)
            finally:
                conn.close()

    def test_existing_version_without_tables_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "broken_tif.taxamask.sqlite"
            conn = create_tif_project_database(db_path)
            try:
                conn.execute("DROP TABLE specimens")
                conn.commit()
                with self.assertRaisesRegex(ValueError, "missing_tif_sqlite_tables"):
                    initialize_tif_project_schema(conn)
                with self.assertRaisesRegex(ValueError, "missing_tif_sqlite_tables"):
                    validate_tif_project_schema(conn)
            finally:
                conn.close()

    def test_existing_version_with_missing_required_column_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "broken_tif_column.taxamask.sqlite"
            conn = create_tif_project_database(db_path)
            try:
                conn.execute("ALTER TABLE volume_assets RENAME TO volume_assets_old")
                conn.execute(
                    """
                    CREATE TABLE volume_assets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        specimen_id INTEGER NOT NULL,
                        path TEXT NOT NULL DEFAULT ''
                    )
                    """
                )
                conn.commit()
                with self.assertRaisesRegex(ValueError, "missing_tif_sqlite_columns:volume_assets"):
                    initialize_tif_project_schema(conn)
            finally:
                conn.close()

    def test_project_row_version_must_match_migration_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "inconsistent_tif.taxamask.sqlite"
            conn = create_tif_project_database(db_path)
            try:
                conn.execute(
                    "UPDATE tif_projects SET schema_version = 1 WHERE id = 1"
                )
                conn.commit()

                with self.assertRaisesRegex(
                    ValueError, "inconsistent_tif_sqlite_schema_version"
                ):
                    initialize_tif_project_schema(conn)
                self.assertEqual(
                    conn.execute(
                        "SELECT schema_version FROM tif_projects WHERE id = 1"
                    ).fetchone()[0],
                    1,
                )
            finally:
                conn.close()

    def test_insert_specimen_volume_material_and_label_layer(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "tif_project.taxamask.sqlite"
            conn = create_tif_project_database(db_path)
            try:
                with conn:
                    specimen_row_id = conn.execute(
                        """
                        INSERT INTO specimens (
                            specimen_id, display_name, modality, review_status,
                            train_ready, metadata_json
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            "01-0101-02",
                            "01-0101-02 worker",
                            "micro_ct",
                            "in_progress",
                            0,
                            json_text({"collector": "unit-test"}),
                        ),
                    ).lastrowid
                    conn.execute(
                        """
                        INSERT INTO material_maps (specimen_id, path, source, materials_json)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            specimen_row_id,
                            "specimens/01-0101-02/material_map.json",
                            "manual",
                            json_text([{"id": 0, "name": "background"}, {"id": 1, "name": "head"}]),
                        ),
                    )
                    volume_id = conn.execute(
                        """
                        INSERT INTO volume_assets (
                            specimen_id, asset_key, role, path, format,
                            shape_zyx_json, dtype, spacing_zyx_json, orientation, status
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            specimen_row_id,
                            "working_volume",
                            "working_image",
                            "specimens/01-0101-02/working/image.ome.zarr",
                            "ant3d_volume_sidecar",
                            json_text([40, 512, 512]),
                            "uint8",
                            json_text([1.0, 0.7, 0.7]),
                            "zyx",
                            "available",
                        ),
                    ).lastrowid
                    label_volume_id = conn.execute(
                        """
                        INSERT INTO volume_assets (
                            specimen_id, asset_key, role, path, format,
                            shape_zyx_json, dtype, spacing_zyx_json, orientation, status
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            specimen_row_id,
                            "labels.working_edit",
                            "working_edit",
                            "specimens/01-0101-02/labels/working_edit.ome.zarr",
                            "ant3d_volume_sidecar",
                            json_text([40, 512, 512]),
                            "uint16",
                            json_text([1.0, 0.7, 0.7]),
                            "zyx",
                            "in_progress",
                        ),
                    ).lastrowid
                    conn.execute(
                        """
                        INSERT INTO label_layers (specimen_id, volume_asset_id, role, status)
                        VALUES (?, ?, ?, ?)
                        """,
                        (specimen_row_id, label_volume_id, "working_edit", "in_progress"),
                    )

                row = conn.execute(
                    """
                    SELECT s.specimen_id, v.path, l.role, m.materials_json
                    FROM specimens s
                    JOIN volume_assets v ON v.specimen_id = s.id AND v.id = ?
                    JOIN label_layers l ON l.volume_asset_id = v.id
                    JOIN material_maps m ON m.specimen_id = s.id
                    WHERE s.id = ?
                    """,
                    (label_volume_id, specimen_row_id),
                ).fetchone()

                self.assertEqual(volume_id > 0, True)
                self.assertEqual(row[0], "01-0101-02")
                self.assertTrue(row[1].endswith("working_edit.ome.zarr"))
                self.assertEqual(row[2], "working_edit")
                self.assertEqual(json.loads(row[3])[1]["name"], "head")
            finally:
                conn.close()

    def test_insert_part_roi_axis_records_and_cascade_from_specimen(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "tif_project.taxamask.sqlite"
            conn = create_tif_project_database(db_path)
            try:
                with conn:
                    specimen_row_id = conn.execute(
                        "INSERT INTO specimens (specimen_id, display_name) VALUES (?, ?)",
                        ("01-0101-local", "local axis specimen"),
                    ).lastrowid
                    part_row_id = conn.execute(
                        """
                        INSERT INTO parts (
                            specimen_id, part_id, display_name, status,
                            parent_bbox_zyx_json, source_json
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            specimen_row_id,
                            "head",
                            "Head",
                            "reviewed",
                            json_text([[0, 20], [10, 90], [15, 110]]),
                            json_text({"parent_volume_role": "working_volume"}),
                        ),
                    ).lastrowid
                    roi_row_id = conn.execute(
                        """
                        INSERT INTO part_rois (
                            specimen_id, roi_id, display_name, status,
                            bbox_zyx_json, linked_part_id, linked_part_row_id
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            specimen_row_id,
                            "roi_head",
                            "Head ROI",
                            "confirmed",
                            json_text([[0, 20], [10, 90], [15, 110]]),
                            "head",
                            part_row_id,
                        ),
                    ).lastrowid
                    conn.execute(
                        """
                        INSERT INTO part_reslices (
                            part_id, reslice_id, display_name, template_id,
                            image_path, local_frame_json, reslice_params_json
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            part_row_id,
                            "frame_001_reslice",
                            "Frame 001",
                            "standard_head",
                            "specimens/01-0101-local/parts/head/reslices/frame_001/image.ome.zarr",
                            json_text({"output_axis": "z_axis"}),
                            json_text({"thickness": 32}),
                        ),
                    )
                    conn.execute(
                        """
                        INSERT INTO global_axis_proposals (
                            specimen_id, proposal_id, template_id, status,
                            bbox_zyx_json, center_zyx_json, confidence
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            specimen_row_id,
                            "global_001",
                            "standard_head",
                            "accepted",
                            json_text([[0, 20], [10, 90], [15, 110]]),
                            json_text([10.0, 50.0, 60.0]),
                            0.91,
                        ),
                    )
                    conn.execute(
                        """
                        INSERT INTO local_frame_proposals (
                            part_id, proposal_id, template_id, status,
                            origin_zyx_json, local_frame_json, confidence
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            part_row_id,
                            "frame_001",
                            "standard_head",
                            "accepted",
                            json_text([10.0, 50.0, 60.0]),
                            json_text({"output_axis": "z_axis"}),
                            0.87,
                        ),
                    )
                    conn.execute(
                        """
                        INSERT INTO tif_runs (
                            run_id, workflow, action, specimen_ids_json, part_ids_json,
                            result_status, metrics_json
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            "run_001",
                            "tif_local_axis",
                            "predict_local_frame",
                            json_text(["01-0101-local"]),
                            json_text(["head"]),
                            "success",
                            json_text({"accepted": 1}),
                        ),
                    )
                    conn.execute(
                        """
                        INSERT INTO tif_run_artifacts (
                            run_id, artifact_type, role, path, format, specimen_id, part_id
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            "run_001",
                            "local_frame_proposals",
                            "model_output",
                            "runs/run_001/local_frame_proposals.json",
                            "json",
                            "01-0101-local",
                            "head",
                        ),
                    )
                    conn.execute(
                        """
                        INSERT INTO tif_events (specimen_id, part_id, run_id, event_type, payload_json)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            specimen_row_id,
                            part_row_id,
                            "run_001",
                            "local_frame_accepted",
                            json_text({"proposal_id": "frame_001"}),
                        ),
                    )

                linked = conn.execute(
                    """
                    SELECT r.linked_part_id, p.part_id, f.proposal_id, g.proposal_id
                    FROM part_rois r
                    JOIN parts p ON p.id = r.linked_part_row_id
                    JOIN local_frame_proposals f ON f.part_id = p.id
                    JOIN global_axis_proposals g ON g.specimen_id = p.specimen_id
                    WHERE r.id = ?
                    """,
                    (roi_row_id,),
                ).fetchone()
                self.assertEqual(linked, ("head", "head", "frame_001", "global_001"))

                with conn:
                    conn.execute("DELETE FROM specimens WHERE id = ?", (specimen_row_id,))

                self.assertEqual(conn.execute("SELECT COUNT(*) FROM parts").fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM part_rois").fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM part_reslices").fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM global_axis_proposals").fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM local_frame_proposals").fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM tif_events WHERE specimen_id IS NOT NULL").fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM tif_run_artifacts").fetchone()[0], 1)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
