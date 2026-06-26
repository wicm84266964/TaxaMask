import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from AntSleap.core.project import ProjectManager
from AntSleap.core.project_sqlite_maintenance import backup_sqlite_project_manifest, export_sqlite_project_to_legacy_json
from AntSleap.core.tif_project import TifProjectManager
from AntSleap.core.tif_volume_io import VOLUME_SIDECAR_FORMAT


class SQLiteLargeScaleRehearsalTests(unittest.TestCase):
    def test_2d_large_project_single_image_update_keeps_manifest_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = ProjectManager()
            manifest_path = Path(manager.create_project("large_2d", root))
            image_paths = [str(root / "images" / f"ant_{index:04d}.png") for index in range(180)]
            manager.add_images(image_paths, save=False)
            for index, image_path in enumerate(image_paths):
                manager.project_data["labels"][image_path] = {
                    "parts": {
                        "Head": [[1, 1], [10, 1], [10, 8], [1, 8]],
                    },
                    "boxes": {
                        "Head": [0, 0, 12, 10],
                    },
                    "status": "labeled",
                    "genus": "Formica",
                    "taxon": f"Formica rehearsal {index}",
                    "taxon_rank": "species",
                    "taxon_metadata": {},
                    "descriptions": {},
                    "description_sources": {},
                }
            manager.mark_sqlite_images_dirty(image_paths)
            manager.save_project()

            manifest_before = manifest_path.read_text(encoding="utf-8")
            target_image = image_paths[42]
            manager.update_auto_box(
                target_image,
                "Gaster",
                [12, 10, 30, 25],
                source_meta={"source": "vlm_first_mile", "review_status": "draft", "source_run_id": "large_run"},
                save=False,
            )
            manager.save_project()

            self.assertEqual(manifest_path.read_text(encoding="utf-8"), manifest_before)
            db_path = Path(manager.current_database_path)
            conn = sqlite3.connect(db_path)
            try:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM images").fetchone()[0], 180)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM labels").fetchone()[0], 180)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM auto_boxes").fetchone()[0], 1)
                self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            finally:
                conn.close()

            backup = backup_sqlite_project_manifest(manifest_path, min_interval_seconds=0)
            self.assertTrue(Path(backup.backup_manifest_path).exists())
            self.assertTrue(Path(backup.backup_database_path).exists())

            export_path = root / "exports" / "large_2d.audit.json"
            export = export_sqlite_project_to_legacy_json(manifest_path, export_path)
            self.assertEqual(export.stats["image_count"], 180)
            self.assertEqual(export.stats["label_count"], 180)
            payload = json.loads(export_path.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["images"]), 180)

    def test_tif_large_index_rehearsal_flushes_and_exports_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            manifest_path = Path(manager.create_project("large_tif", root / "large_tif"))
            for index in range(45):
                specimen_id = f"01-0101-{index:04d}"
                manager.add_specimen(
                    specimen_id,
                    modality="micro_ct",
                    working_volume={
                        "path": f"specimens/{specimen_id}/working/image.ome.zarr",
                        "format": VOLUME_SIDECAR_FORMAT,
                        "shape_zyx": [24, 128, 128],
                        "dtype": "uint8",
                        "spacing_zyx": [1.0, 0.5, 0.5],
                    },
                    labels={
                        "manual_truth": {
                            "path": f"specimens/{specimen_id}/labels/manual_truth.ome.zarr",
                            "format": VOLUME_SIDECAR_FORMAT,
                            "shape_zyx": [24, 128, 128],
                            "dtype": "uint16",
                            "status": "reviewed",
                        },
                        "working_edit": {
                            "path": f"specimens/{specimen_id}/labels/working_edit.ome.zarr",
                            "format": VOLUME_SIDECAR_FORMAT,
                            "shape_zyx": [24, 128, 128],
                            "dtype": "uint16",
                            "status": "in_progress",
                        },
                        "model_drafts": [],
                    },
                    save=False,
                )
                manager.add_part(
                    specimen_id,
                    "head",
                    display_name="Head",
                    image={
                        "path": f"specimens/{specimen_id}/parts/head/image.ome.zarr",
                        "format": VOLUME_SIDECAR_FORMAT,
                        "shape_zyx": [8, 64, 64],
                        "dtype": "uint8",
                    },
                    mask={
                        "path": f"specimens/{specimen_id}/parts/head/mask.ome.zarr",
                        "format": VOLUME_SIDECAR_FORMAT,
                        "shape_zyx": [8, 64, 64],
                        "dtype": "uint16",
                    },
                    parent_bbox_zyx=[[4, 12], [16, 80], [16, 80]],
                    save=False,
                )
                manager.add_part_roi(
                    specimen_id,
                    "roi_head",
                    bbox_zyx=[[4, 12], [16, 80], [16, 80]],
                    linked_part_id="head",
                    status="part_created",
                    save=False,
                )
            manager.save_project()

            conn = sqlite3.connect(manager.current_database_path)
            try:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM specimens").fetchone()[0], 45)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM parts").fetchone()[0], 45)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM part_rois").fetchone()[0], 45)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM label_layers").fetchone()[0], 90)
                self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            finally:
                conn.close()

            backup = backup_sqlite_project_manifest(manifest_path, min_interval_seconds=0)
            self.assertTrue(Path(backup.backup_manifest_path).exists())

            export_path = root / "exports" / "large_tif.audit.json"
            export = export_sqlite_project_to_legacy_json(manifest_path, export_path)
            self.assertEqual(export.stats["specimen_count"], 45)
            self.assertEqual(export.stats["part_count"], 45)
            self.assertEqual(export.stats["part_roi_count"], 45)


if __name__ == "__main__":
    unittest.main()
