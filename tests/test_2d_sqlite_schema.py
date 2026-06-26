import json
import tempfile
import unittest
from pathlib import Path

from AntSleap.core.project_sqlite_schema import (
    PROJECT_2D_SCHEMA_NAME,
    PROJECT_2D_SCHEMA_VERSION,
    create_2d_project_database,
    initialize_2d_project_schema,
    json_text,
    validate_2d_project_schema,
)
from AntSleap.core.sqlite_storage import get_schema_version, run_integrity_check


class Project2DSQLiteSchemaTests(unittest.TestCase):
    def test_initialize_schema_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "project.taxamask.sqlite"
            conn = create_2d_project_database(db_path)
            try:
                self.assertEqual(get_schema_version(conn, PROJECT_2D_SCHEMA_NAME), PROJECT_2D_SCHEMA_VERSION)
                self.assertEqual(initialize_2d_project_schema(conn), PROJECT_2D_SCHEMA_VERSION)
                self.assertEqual(run_integrity_check(conn), ["ok"])
                project = conn.execute("SELECT project_type FROM projects WHERE id = 1").fetchone()
                self.assertEqual(project[0], "2d_image_annotation")
            finally:
                conn.close()

    def test_existing_version_without_tables_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "broken.taxamask.sqlite"
            conn = create_2d_project_database(db_path)
            try:
                conn.execute("DROP TABLE images")
                conn.commit()
                with self.assertRaisesRegex(ValueError, "missing_2d_sqlite_tables"):
                    initialize_2d_project_schema(conn)
                with self.assertRaisesRegex(ValueError, "missing_2d_sqlite_tables"):
                    validate_2d_project_schema(conn)
            finally:
                conn.close()

    def test_existing_version_with_missing_required_column_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "broken_column.taxamask.sqlite"
            conn = create_2d_project_database(db_path)
            try:
                conn.execute("ALTER TABLE auto_boxes RENAME TO auto_boxes_old")
                conn.execute(
                    """
                    CREATE TABLE auto_boxes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        image_id INTEGER NOT NULL,
                        part_name TEXT NOT NULL
                    )
                    """
                )
                conn.commit()
                with self.assertRaisesRegex(ValueError, "missing_2d_sqlite_columns:auto_boxes"):
                    initialize_2d_project_schema(conn)
            finally:
                conn.close()

    def test_insert_image_polygon_and_auto_box(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "project.taxamask.sqlite"
            conn = create_2d_project_database(db_path)
            try:
                with conn:
                    cursor = conn.execute(
                        """
                        INSERT INTO images (path, filename, width, height)
                        VALUES (?, ?, ?, ?)
                        """,
                        ("images/ant001.jpg", "ant001.jpg", 1200, 900),
                    )
                    image_id = int(cursor.lastrowid)
                    cursor = conn.execute(
                        """
                        INSERT INTO labels (image_id, status, genus, taxon)
                        VALUES (?, ?, ?, ?)
                        """,
                        (image_id, "labeled", "Formica", "Formica testus"),
                    )
                    label_id = int(cursor.lastrowid)
                    conn.execute(
                        """
                        INSERT INTO label_polygons (label_id, part_name, polygon_index, points_json)
                        VALUES (?, ?, ?, ?)
                        """,
                        (label_id, "Head", 0, json_text([[1, 2], [3, 4], [5, 6]])),
                    )
                    conn.execute(
                        """
                        INSERT INTO auto_boxes (
                            image_id, part_name, source, x1, y1, x2, y2,
                            confidence, review_status, run_id, metadata_json
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            image_id,
                            "Head",
                            "vlm_first_mile",
                            10,
                            20,
                            100,
                            140,
                            0.82,
                            "draft",
                            "run_001",
                            json_text({"prompt": "default"}),
                        ),
                    )

                row = conn.execute(
                    """
                    SELECT p.points_json, a.source, a.review_status
                    FROM label_polygons p
                    JOIN labels l ON l.id = p.label_id
                    JOIN images i ON i.id = l.image_id
                    JOIN auto_boxes a ON a.image_id = i.id
                    WHERE i.path = ?
                    """,
                    ("images/ant001.jpg",),
                ).fetchone()
                self.assertEqual(json.loads(row[0]), [[1, 2], [3, 4], [5, 6]])
                self.assertEqual(row[1], "vlm_first_mile")
                self.assertEqual(row[2], "draft")
            finally:
                conn.close()

    def test_image_delete_cascades_related_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "project.taxamask.sqlite"
            conn = create_2d_project_database(db_path)
            try:
                with conn:
                    image_id = conn.execute(
                        "INSERT INTO images (path, filename) VALUES (?, ?)",
                        ("images/delete_me.jpg", "delete_me.jpg"),
                    ).lastrowid
                    label_id = conn.execute(
                        "INSERT INTO labels (image_id, status) VALUES (?, ?)",
                        (image_id, "labeled"),
                    ).lastrowid
                    conn.execute(
                        "INSERT INTO label_boxes (label_id, part_name, x1, y1, x2, y2) VALUES (?, ?, ?, ?, ?, ?)",
                        (label_id, "Head", 1, 2, 3, 4),
                    )
                    conn.execute(
                        """
                        INSERT INTO label_boxes (label_id, part_name, box_type, x1, y1, x2, y2)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (label_id, "Head", "shrink_loose", 0, 1, 5, 6),
                    )
                    conn.execute(
                        """
                        INSERT INTO blink_trajectories (
                            label_id, child_part_name, parent_part_name,
                            trajectory_json, parent_context_json
                        )
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            label_id,
                            "Eye",
                            "Head",
                            json_text({"frames": [{"step": 1, "box": [1, 2, 3, 4]}]}),
                            json_text({"parent_part": "Head", "source": "manual"}),
                        ),
                    )
                    auto_box_id = conn.execute(
                        "INSERT INTO auto_boxes (image_id, part_name, x1, y1, x2, y2) VALUES (?, ?, ?, ?, ?, ?)",
                        (image_id, "Head", 1, 2, 3, 4),
                    ).lastrowid
                    conn.execute(
                        "INSERT INTO auto_box_reviews (auto_box_id, review_status) VALUES (?, ?)",
                        (auto_box_id, "confirmed"),
                    )
                    conn.execute("DELETE FROM images WHERE id = ?", (image_id,))

                self.assertEqual(conn.execute("SELECT COUNT(*) FROM labels").fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM label_boxes").fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM blink_trajectories").fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM auto_boxes").fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM auto_box_reviews").fetchone()[0], 0)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
