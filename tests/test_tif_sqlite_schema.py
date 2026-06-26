import json
import tempfile
import unittest
from pathlib import Path

from AntSleap.core.sqlite_storage import get_schema_version, run_integrity_check
from AntSleap.core.tif_sqlite_schema import (
    TIF_SQLITE_PROJECT_TYPE,
    TIF_SQLITE_SCHEMA_NAME,
    TIF_SQLITE_SCHEMA_VERSION,
    create_tif_project_database,
    initialize_tif_project_schema,
    json_text,
    validate_tif_project_schema,
)


class TifSQLiteSchemaTests(unittest.TestCase):
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
