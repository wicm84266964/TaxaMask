import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from AntSleap.core.location_registry import (
    LocationRegistryError,
    connect_location_registry,
    default_location_registry_path,
    register_location,
    resolve_location,
    resolve_locations,
)


class LocationRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config_dir = self.root / "config" / "TaxaMask"
        self.db_path = self.config_dir / "location_registry.sqlite"
        self.file_path = self.root / "inputs" / "image_a.png"
        self.file_path.parent.mkdir(parents=True)
        self.file_path.write_bytes(b"image-a")
        self.directory_path = self.root / "volumes" / "specimen_a.zarr"
        self.directory_path.mkdir(parents=True)
        (self.directory_path / "0").write_bytes(b"volume")

    def tearDown(self):
        self.temp.cleanup()

    def test_default_path_uses_user_config_directory(self):
        with patch(
            "AntSleap.core.location_registry.user_config_dir",
            return_value=self.config_dir,
        ):
            self.assertEqual(default_location_registry_path(), self.db_path)

    def test_file_and_directory_survive_registry_reopen(self):
        file_ref = register_location(
            self.file_path,
            entry_kind="file",
            database_path=self.db_path,
        )
        directory_ref = register_location(
            self.directory_path,
            entry_kind="directory",
            database_path=self.db_path,
        )

        self.assertEqual(
            resolve_location(
                file_ref, expected_kind="file", database_path=self.db_path
            ),
            self.file_path,
        )
        resolved = resolve_locations(
            [file_ref, directory_ref], database_path=self.db_path
        )
        self.assertEqual(resolved[file_ref], self.file_path)
        self.assertEqual(resolved[directory_ref], self.directory_path)

        connection = sqlite3.connect(self.db_path)
        try:
            rows = connection.execute(
                "SELECT location_ref, entry_kind, absolute_path FROM locations"
            ).fetchall()
        finally:
            connection.close()
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(os.path.isabs(row[2]) for row in rows))
        self.assertNotIn("/", file_ref)
        self.assertNotIn("\\", file_ref)

    def test_same_path_is_idempotent_and_conflicts_are_rejected(self):
        location_ref = register_location(
            self.file_path,
            entry_kind="file",
            location_ref="location_file_a",
            database_path=self.db_path,
        )
        self.assertEqual(
            register_location(
                self.file_path,
                entry_kind="file",
                database_path=self.db_path,
            ),
            location_ref,
        )

        with self.assertRaises(LocationRegistryError) as path_conflict:
            register_location(
                self.file_path,
                entry_kind="file",
                location_ref="location_other",
                database_path=self.db_path,
            )
        self.assertEqual(
            path_conflict.exception.code, "location_path_already_registered"
        )

        second_file = self.root / "inputs" / "image_b.png"
        second_file.write_bytes(b"image-b")
        with self.assertRaises(LocationRegistryError) as ref_conflict:
            register_location(
                second_file,
                entry_kind="file",
                location_ref=location_ref,
                database_path=self.db_path,
            )
        self.assertEqual(ref_conflict.exception.code, "location_ref_conflict")

    def test_missing_and_wrong_kind_are_rejected_without_creating_on_resolve(self):
        missing_db = self.root / "missing_config" / "location_registry.sqlite"
        with self.assertRaises(LocationRegistryError) as registry_missing:
            resolve_location("location_missing", database_path=missing_db)
        self.assertEqual(registry_missing.exception.code, "location_registry_missing")
        self.assertFalse(missing_db.exists())

        with self.assertRaises(LocationRegistryError) as source_missing:
            register_location(
                self.root / "missing.tif",
                entry_kind="file",
                database_path=self.db_path,
            )
        self.assertEqual(source_missing.exception.code, "location_path_missing")

        with self.assertRaises(LocationRegistryError) as wrong_kind:
            register_location(
                self.file_path,
                entry_kind="directory",
                database_path=self.db_path,
            )
        self.assertEqual(wrong_kind.exception.code, "location_kind_mismatch")

        location_ref = register_location(
            self.file_path,
            entry_kind="file",
            database_path=self.db_path,
        )
        with self.assertRaises(LocationRegistryError) as expected_kind:
            resolve_location(
                location_ref,
                expected_kind="directory",
                database_path=self.db_path,
            )
        self.assertEqual(expected_kind.exception.code, "location_kind_mismatch")

        self.file_path.unlink()
        with self.assertRaises(LocationRegistryError) as moved:
            resolve_location(location_ref, database_path=self.db_path)
        self.assertEqual(moved.exception.code, "location_path_missing")

    def test_target_and_parent_symlinks_are_rejected(self):
        file_link = self.root / "file_link.png"
        linked_parent = self.root / "linked_inputs"
        try:
            os.symlink(self.file_path, file_link)
            os.symlink(self.file_path.parent, linked_parent, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation is unavailable")

        for candidate in (file_link, linked_parent / self.file_path.name):
            with self.subTest(candidate=candidate):
                with self.assertRaises(LocationRegistryError) as raised:
                    register_location(
                        candidate,
                        entry_kind="file",
                        database_path=self.db_path,
                    )
                self.assertEqual(raised.exception.code, "location_link_not_allowed")

    def test_windows_reparse_path_is_rejected_without_os_privileges(self):
        original_lstat = os.lstat
        target_identity = os.path.normcase(os.path.abspath(self.file_path))

        def flagged_lstat(path):
            result = original_lstat(path)
            if os.path.normcase(os.path.abspath(os.fspath(path))) == target_identity:
                return SimpleNamespace(
                    st_mode=result.st_mode,
                    st_file_attributes=int(
                        getattr(result, "st_file_attributes", 0) or 0
                    )
                    | 0x400,
                )
            return result

        with patch(
            "AntSleap.core.location_registry.os.lstat",
            side_effect=flagged_lstat,
        ):
            with self.assertRaises(LocationRegistryError) as raised:
                register_location(
                    self.file_path,
                    entry_kind="file",
                    database_path=self.db_path,
                )
        self.assertEqual(raised.exception.code, "location_link_not_allowed")

    def test_post_insert_validation_failure_rolls_back_mapping(self):
        with patch(
            "AntSleap.core.location_registry._validate_registered_path",
            side_effect=LocationRegistryError(
                "location_changed_during_registration"
            ),
        ):
            with self.assertRaises(LocationRegistryError) as raised:
                register_location(
                    self.file_path,
                    entry_kind="file",
                    database_path=self.db_path,
                )
        self.assertEqual(
            raised.exception.code, "location_changed_during_registration"
        )

        connection = sqlite3.connect(self.db_path)
        try:
            count = connection.execute("SELECT COUNT(*) FROM locations").fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(count, 0)

    def test_location_mappings_are_immutable(self):
        location_ref = register_location(
            self.file_path,
            entry_kind="file",
            database_path=self.db_path,
        )
        connection = connect_location_registry(self.db_path)
        try:
            with self.assertRaisesRegex(sqlite3.IntegrityError, "location_mapping_immutable"):
                with connection:
                    connection.execute(
                        "UPDATE locations SET absolute_path = ? WHERE location_ref = ?",
                        (str(self.directory_path), location_ref),
                    )
            with self.assertRaisesRegex(sqlite3.IntegrityError, "location_mapping_immutable"):
                with connection:
                    connection.execute(
                        "DELETE FROM locations WHERE location_ref = ?",
                        (location_ref,),
                    )
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
