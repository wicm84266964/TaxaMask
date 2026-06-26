import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import numpy as np

from AntSleap.core.project import ProjectManager
from AntSleap.core.project_sqlite_maintenance import (
    backup_sqlite_project_manifest,
    export_sqlite_project_to_legacy_json,
    sqlite_project_migration_report_path,
)
from AntSleap.core.sqlite_storage import read_project_manifest, resolve_manifest_database_path
from AntSleap.core.tif_project import TifProjectManager
from AntSleap.core.tif_volume_io import VOLUME_SIDECAR_FORMAT, write_volume_sidecar
from tests.test_2d_json_to_sqlite_migration import _legacy_project_payload, _write_json
from AntSleap.core.project_sqlite_migration import migrate_legacy_2d_json_to_sqlite
from tests.test_tif_json_to_sqlite_migration import _build_legacy_tif_project


class SQLiteProjectMaintenanceTests(unittest.TestCase):
    def test_new_2d_project_defaults_to_sqlite_and_exports_legacy_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_path = root / "ant.png"
            image_path.write_bytes(b"image")

            manager = ProjectManager()
            manifest_path = Path(manager.create_project("field_review", root))
            manager.add_images([str(image_path)], save=False)
            manager.update_label(
                str(image_path),
                "Head",
                [[1, 1], [5, 1], [5, 4], [1, 4]],
                box=[0, 0, 6, 5],
                save=False,
            )
            manager.save_project()

            self.assertEqual(manager.current_storage_backend, "sqlite")
            self.assertEqual(manifest_path.name, "field_review.sqlite_manifest.json")
            self.assertTrue((root / "field_review.taxamask.sqlite").exists())
            self.assertFalse((root / "field_review.json").exists())

            export_path = root / "audit" / "field_review.json"
            result = export_sqlite_project_to_legacy_json(manifest_path, export_path)
            payload = json.loads(export_path.read_text(encoding="utf-8"))

            self.assertEqual(result.stats["image_count"], 1)
            self.assertEqual(payload["images"], ["../ant.png"])
            self.assertIn("../ant.png", payload["labels"])
            self.assertIn("Head", payload["labels"]["../ant.png"]["parts"])

            reloaded = ProjectManager()
            reloaded.load_project(manifest_path)
            self.assertIn(str(image_path.resolve()), reloaded.project_data["labels"])

    def test_sqlite_backup_manifest_can_be_opened(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = ProjectManager()
            manifest_path = Path(manager.create_project("backup_demo", root))
            manager.save_project()

            backup = backup_sqlite_project_manifest(manifest_path, min_interval_seconds=0)

            self.assertTrue(Path(backup.backup_database_path).exists())
            self.assertTrue(Path(backup.backup_manifest_path).exists())
            self.assertEqual(backup.integrity_check, ["ok"])
            backup_manifest = read_project_manifest(backup.backup_manifest_path)
            self.assertEqual(Path(resolve_manifest_database_path(backup.backup_manifest_path, backup_manifest)), Path(backup.backup_database_path))

            reloaded = ProjectManager()
            reloaded.load_project(backup.backup_manifest_path)
            self.assertEqual(reloaded.project_data["name"], "backup_demo")
            self.assertEqual(reloaded.current_storage_backend, "sqlite")

    def test_legacy_2d_migration_report_path_is_resolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_json = root / "legacy_project.json"
            manifest_path = root / "legacy_project.sqlite_manifest.json"
            db_path = root / "legacy_project.taxamask.sqlite"
            report_path = root / "reports" / "migration_report.json"
            _write_json(source_json, _legacy_project_payload())
            migrate_legacy_2d_json_to_sqlite(
                source_json,
                database_path=db_path,
                manifest_path=manifest_path,
                report_path=report_path,
            )

            self.assertEqual(sqlite_project_migration_report_path(manifest_path), str(report_path.resolve()))

    def test_new_tif_project_defaults_to_sqlite_and_exports_rebased_legacy_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_root = root / "tif_project"
            manager = TifProjectManager()
            manifest_path = Path(manager.create_project("tif_default", project_root))
            manager.create_specimen_scaffold("01-0101-sqlite")
            image_rel = "specimens/01-0101-sqlite/working/image.ome.zarr"
            meta = write_volume_sidecar(project_root / image_rel, np.zeros((2, 3, 4), dtype=np.uint8), role="working_image")
            manager.register_working_volume(
                "01-0101-sqlite",
                image_rel,
                meta["shape_zyx"],
                meta["dtype"],
                fmt=VOLUME_SIDECAR_FORMAT,
            )

            self.assertEqual(manager.current_storage_backend, "sqlite")
            self.assertEqual(manifest_path.name, "project.tif_sqlite_manifest.json")
            self.assertTrue((project_root / "project.taxamask_tif.sqlite").exists())
            self.assertFalse((project_root / "project.json").exists())

            export_path = root / "exports" / "tif_default.json"
            result = export_sqlite_project_to_legacy_json(manifest_path, export_path)
            payload = json.loads(export_path.read_text(encoding="utf-8"))
            specimen = payload["specimens"][0]

            self.assertEqual(result.stats["specimen_count"], 1)
            self.assertEqual(specimen["working_volume"]["path"], "../tif_project/specimens/01-0101-sqlite/working/image.ome.zarr")

            reloaded = TifProjectManager()
            reloaded.load_project(manifest_path)
            self.assertEqual(reloaded.project_data["name"], "tif_default")
            self.assertEqual(reloaded.current_asset_root, str(project_root.resolve()))

    def test_migrated_tif_backup_preserves_asset_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy_path = _build_legacy_tif_project(root / "legacy_tif")
            from AntSleap.core.tif_sqlite_migration import migrate_legacy_tif_json_to_sqlite

            manifest_path = root / "project_manifest.json"
            db_path = root / "project.sqlite"
            report_path = root / "report.json"
            migrate_legacy_tif_json_to_sqlite(
                legacy_path,
                database_path=db_path,
                manifest_path=manifest_path,
                report_path=report_path,
            )

            backup = backup_sqlite_project_manifest(manifest_path, min_interval_seconds=0)
            backup_manifest = read_project_manifest(backup.backup_manifest_path)
            self.assertIn("tif_asset_root", backup_manifest)

            reloaded = TifProjectManager()
            reloaded.load_project(backup.backup_manifest_path)
            self.assertTrue(Path(reloaded.to_absolute("specimens/01-0101-local/material_map.json")).exists())


if __name__ == "__main__":
    unittest.main()
