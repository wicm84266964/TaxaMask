import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from AntSleap.core.sqlite_storage import (
    backup_sqlite_database,
    connect_sqlite_database,
    ensure_integrity_ok,
    initialize_schema_migrations,
    read_project_manifest,
    record_schema_version,
    resolve_manifest_database_path,
    run_integrity_check,
    write_project_manifest,
)


class SQLiteStorageTests(unittest.TestCase):
    def test_connect_initializes_pragmas_and_integrity_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "project.taxamask.sqlite"
            conn = connect_sqlite_database(db_path)
            try:
                self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
                self.assertEqual(conn.execute("PRAGMA journal_mode").fetchone()[0].lower(), "wal")
                self.assertEqual(run_integrity_check(conn), ["ok"])
                self.assertEqual(ensure_integrity_ok(conn), ["ok"])
            finally:
                conn.close()

    def test_schema_migrations_and_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "project.taxamask.sqlite"
            conn = connect_sqlite_database(db_path)
            try:
                initialize_schema_migrations(conn)
                record_schema_version(conn, "example", 1)
                conn.execute("CREATE TABLE IF NOT EXISTS sample (id INTEGER PRIMARY KEY, value TEXT)")
                conn.execute("INSERT INTO sample (value) VALUES ('saved')")
                conn.commit()
            finally:
                conn.close()

            backup_path = backup_sqlite_database(db_path, min_interval_seconds=0)
            self.assertTrue(Path(backup_path).exists())
            backup_conn = sqlite3.connect(backup_path)
            try:
                self.assertEqual(backup_conn.execute("SELECT value FROM sample").fetchone()[0], "saved")
            finally:
                backup_conn.close()

    def test_backup_removes_tmp_file_when_replace_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "project.taxamask.sqlite"
            conn = connect_sqlite_database(db_path)
            try:
                conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT)")
                conn.execute("INSERT INTO sample (value) VALUES ('saved')")
                conn.commit()
            finally:
                conn.close()

            blocked_backup_target = root / "blocked"
            blocked_backup_target.write_text("not a directory", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                backup_sqlite_database(db_path, backup_dir=blocked_backup_target, min_interval_seconds=0)

            self.assertFalse(list(root.glob("*.tmp")))

    def test_multiple_backups_in_same_second_do_not_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "project.taxamask.sqlite"
            conn = connect_sqlite_database(db_path)
            try:
                conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT)")
                conn.execute("INSERT INTO sample (value) VALUES ('first')")
                conn.commit()
            finally:
                conn.close()

            first_backup = Path(backup_sqlite_database(db_path, min_interval_seconds=0))
            conn = connect_sqlite_database(db_path)
            try:
                conn.execute("UPDATE sample SET value = 'second'")
                conn.commit()
            finally:
                conn.close()
            second_backup = Path(backup_sqlite_database(db_path, min_interval_seconds=0))

            self.assertNotEqual(first_backup, second_backup)
            first_conn = sqlite3.connect(first_backup)
            second_conn = sqlite3.connect(second_backup)
            try:
                self.assertEqual(first_conn.execute("SELECT value FROM sample").fetchone()[0], "first")
                self.assertEqual(second_conn.execute("SELECT value FROM sample").fetchone()[0], "second")
            finally:
                first_conn.close()
                second_conn.close()

    def test_manifest_uses_relative_database_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "project.json"
            db_path = root / "project.taxamask.sqlite"
            payload = write_project_manifest(
                manifest_path,
                "2d_image_annotation",
                "ants",
                db_path,
                extra={"legacy_json_source": "old.json"},
            )
            self.assertEqual(payload["storage_backend"], "sqlite")
            self.assertEqual(payload["database_path"], "project.taxamask.sqlite")
            loaded = read_project_manifest(manifest_path)
            self.assertEqual(loaded["legacy_json_source"], "old.json")
            self.assertEqual(Path(resolve_manifest_database_path(manifest_path, loaded)), db_path)
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(raw["schema_version"], "taxamask-project-manifest-v1")


if __name__ == "__main__":
    unittest.main()
