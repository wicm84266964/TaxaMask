import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import numpy as np

from AntSleap.core.sqlite_storage import read_project_manifest, resolve_manifest_database_path
from AntSleap.core.tif_project import TifProjectManager
from AntSleap.core.tif_sqlite_migration import (
    TIF_MIGRATION_REPORT_SCHEMA_VERSION,
    migrate_legacy_tif_json_to_sqlite,
)
from AntSleap.core.tif_volume_io import VOLUME_SIDECAR_FORMAT, write_volume_sidecar


def _volume_record(path, shape=(2, 3, 4), dtype="uint8"):
    return {
        "path": str(path),
        "format": VOLUME_SIDECAR_FORMAT,
        "shape_zyx": list(shape),
        "dtype": dtype,
        "spacing_zyx": [1.0, 0.5, 0.5],
        "spacing_unit": "micrometer",
        "orientation": "zyx",
    }


def _build_legacy_tif_project(project_root):
    manager = TifProjectManager()
    project_json = manager.create_project("Legacy TIF ants", project_root, storage_backend="json")
    manager.create_specimen_scaffold(
        "01-0101-local",
        modality="micro_ct",
        material_map={
            "source": "manual",
            "materials": [
                {"id": 0, "name": "background", "display_name": "Background", "trainable": False},
                {"id": 1, "name": "head", "display_name": "Head", "trainable": True},
            ],
        },
    )

    image_rel = "specimens/01-0101-local/working/image.ome.zarr"
    manual_rel = "specimens/01-0101-local/labels/manual_truth.ome.zarr"
    edit_rel = "specimens/01-0101-local/labels/working_edit.ome.zarr"
    draft_rel = "specimens/01-0101-local/labels/model_draft/predict_001.ome.zarr"
    image_meta = write_volume_sidecar(project_root / image_rel, np.zeros((2, 3, 4), dtype=np.uint8), role="working_image")
    manual_meta = write_volume_sidecar(project_root / manual_rel, np.ones((2, 3, 4), dtype=np.uint16), role="manual_truth")
    edit_meta = write_volume_sidecar(project_root / edit_rel, np.ones((2, 3, 4), dtype=np.uint16), role="working_edit")
    draft_meta = write_volume_sidecar(project_root / draft_rel, np.ones((2, 3, 4), dtype=np.uint16), role="model_draft")

    manager.register_working_volume(
        "01-0101-local",
        image_rel,
        image_meta["shape_zyx"],
        image_meta["dtype"],
        spacing_zyx=image_meta["spacing_zyx"],
        fmt=VOLUME_SIDECAR_FORMAT,
        save=False,
    )
    manager.register_label_volume(
        "01-0101-local",
        "manual_truth",
        manual_rel,
        manual_meta["shape_zyx"],
        manual_meta["dtype"],
        status="reviewed",
        spacing_zyx=manual_meta["spacing_zyx"],
        fmt=VOLUME_SIDECAR_FORMAT,
        save=False,
    )
    manager.register_label_volume(
        "01-0101-local",
        "working_edit",
        edit_rel,
        edit_meta["shape_zyx"],
        edit_meta["dtype"],
        status="in_progress",
        spacing_zyx=edit_meta["spacing_zyx"],
        fmt=VOLUME_SIDECAR_FORMAT,
        save=False,
    )
    manager.add_model_draft(
        "01-0101-local",
        draft_rel,
        draft_meta["shape_zyx"],
        draft_meta["dtype"],
        prediction_id="predict_001",
        source_model="models/head_model.json",
        spacing_zyx=draft_meta["spacing_zyx"],
        fmt=VOLUME_SIDECAR_FORMAT,
        save=False,
    )
    manager.add_part(
        "01-0101-local",
        "head",
        display_name="Head",
        image=_volume_record("specimens/01-0101-local/parts/head/image.ome.zarr"),
        mask=_volume_record("specimens/01-0101-local/parts/head/mask.ome.zarr", dtype="uint16"),
        parent_bbox_zyx=[[0, 2], [0, 3], [0, 4]],
        status="reviewed",
        save=False,
    )
    manager.add_part_roi(
        "01-0101-local",
        "roi_head",
        display_name="Head ROI",
        bbox_zyx=[[0, 2], [0, 3], [0, 4]],
        status="confirmed",
        linked_part_id="head",
        save=False,
    )
    manager.add_global_axis_proposal(
        "01-0101-local",
        {
            "global_proposal_id": "global_001",
            "template_id": "head",
            "bbox_zyx": [[0, 2], [0, 3], [0, 4]],
            "center_zyx": [1.0, 1.5, 2.0],
            "confidence": 0.91,
            "status": "accepted",
        },
        save=False,
    )
    manager.add_local_frame_proposal(
        "01-0101-local",
        "head",
        {
            "frame_proposal_id": "frame_001",
            "template_id": "head",
            "origin_zyx": [1.0, 1.5, 2.0],
            "local_frame": {"output_axis": "z_axis"},
            "confidence": 0.87,
            "status": "accepted",
        },
        save=False,
    )
    manager.add_part_reslice(
        "01-0101-local",
        "head",
        {
            "reslice_id": "head_axis_001",
            "template_id": "head",
            "image_path": "specimens/01-0101-local/parts/head/reslices/head_axis_001/image.tif",
            "metadata_path": "specimens/01-0101-local/parts/head/reslices/head_axis_001/metadata.json",
            "local_frame": {"output_axis": "z_axis"},
            "training": {"human_confirmed": True, "usable_for_training": True},
            "labels": {
                "editable_ai_result": _volume_record(
                    "specimens/01-0101-local/parts/head/reslices/head_axis_001/labels/editable_ai_result.ome.zarr",
                    dtype="uint16",
                )
            },
        },
        save=False,
    )
    manager.register_local_axis_model(
        {
            "model_id": "local_axis/head_frame_v1",
            "template_id": "head",
            "model_type": "local_frame",
            "backend_type": "external_local_axis",
            "model_manifest": "models/head_frame_v1/manifest.json",
        },
        save=False,
    )
    manager.add_local_axis_run(
        {
            "run_id": "predict_local_frame_001",
            "action": "predict_local_frame",
            "model_id": "local_axis/head_frame_v1",
            "specimen_ids": ["01-0101-local"],
            "part_ids": ["head"],
            "result_status": "success",
            "metrics": {"accepted": 1},
        },
        save=False,
    )
    manager.project_data["runs"].append(
        {
            "run_id": "external_predict_001",
            "workflow": "tif_backend",
            "action": "predict",
            "backend_id": "nnunet_backend",
            "result_status": "success",
            "artifacts": [
                {
                    "type": "prediction_label_volume",
                    "role": "model_draft",
                    "path": "runs/external_predict_001/model_draft.ome.zarr",
                    "format": "ant3d_volume_sidecar",
                    "specimen_id": "01-0101-local",
                    "prediction_id": "predict_001",
                }
            ],
        }
    )
    manager.save_project()
    return Path(project_json)


class LegacyTifJsonToSQLiteMigrationTests(unittest.TestCase):
    def test_full_legacy_tif_project_migrates_without_changing_source_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_json = _build_legacy_tif_project(root / "legacy_tif")
            db_path = root / "legacy_tif.taxamask_tif.sqlite"
            manifest_path = root / "legacy_tif.tif_sqlite_manifest.json"
            report_path = root / "reports" / "tif_migration_report.json"
            original_text = source_json.read_text(encoding="utf-8")
            events = []

            result = migrate_legacy_tif_json_to_sqlite(
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
                "specimen_count": 1,
                "volume_asset_count": 6,
                "label_layer_count": 3,
                "material_map_count": 1,
                "part_count": 1,
                "part_roi_count": 1,
                "part_reslice_count": 1,
                "global_axis_proposal_count": 1,
                "local_frame_proposal_count": 1,
                "model_count": 1,
                "run_count": 2,
                "run_artifact_count": 1,
                "event_count": 0,
            }
            for key, value in expected_stats.items():
                self.assertEqual(result.stats[key], value, key)

            manifest = read_project_manifest(manifest_path)
            self.assertEqual(Path(resolve_manifest_database_path(manifest_path, manifest)), db_path)
            self.assertEqual(manifest["project_type"], "tif_volume")
            self.assertEqual(manifest["tif_asset_root"], "legacy_tif")
            self.assertEqual(manifest["migration_stats"]["label_layer_count"], 3)

            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["schema_version"], TIF_MIGRATION_REPORT_SCHEMA_VERSION)
            self.assertEqual(report["stats"], result.stats)
            self.assertEqual(report["integrity_check"], ["ok"])

    def test_migrated_rows_preserve_tif_index_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_json = _build_legacy_tif_project(root / "legacy_tif")
            db_path = root / "project.sqlite"
            manifest_path = root / "project_manifest.json"
            report_path = root / "migration_report.json"

            migrate_legacy_tif_json_to_sqlite(
                source_json,
                database_path=db_path,
                manifest_path=manifest_path,
                report_path=report_path,
            )

            conn = sqlite3.connect(db_path)
            try:
                project_row = conn.execute("SELECT name, project_type FROM tif_projects WHERE id = 1").fetchone()
                self.assertEqual(project_row, ("Legacy TIF ants", "tif_volume"))

                specimen_row = conn.execute(
                    """
                    SELECT id, specimen_id, modality, review_status
                    FROM specimens
                    WHERE specimen_id = ?
                    """,
                    ("01-0101-local",),
                ).fetchone()
                self.assertEqual(specimen_row[1:], ("01-0101-local", "micro_ct", "not_started"))

                label_roles = [
                    row[0]
                    for row in conn.execute(
                        """
                        SELECT role
                        FROM label_layers
                        WHERE specimen_id = ?
                        ORDER BY role
                        """,
                        (specimen_row[0],),
                    ).fetchall()
                ]
                self.assertEqual(label_roles, ["manual_truth", "model_draft", "working_edit"])

                volume_paths = [
                    row[0]
                    for row in conn.execute(
                        """
                        SELECT path
                        FROM volume_assets
                        WHERE specimen_id = ? AND role = ?
                        """,
                        (specimen_row[0], "working_image"),
                    ).fetchall()
                ]
                self.assertEqual(volume_paths, ["specimens/01-0101-local/working/image.ome.zarr"])

                material_row = conn.execute(
                    "SELECT path, materials_json FROM material_maps WHERE specimen_id = ?",
                    (specimen_row[0],),
                ).fetchone()
                self.assertTrue(material_row[0].endswith("material_map.json"))
                self.assertEqual(json.loads(material_row[1])[1]["name"], "head")

                part_row = conn.execute(
                    """
                    SELECT id, part_id, image_asset_id, mask_asset_id, parent_bbox_zyx_json
                    FROM parts
                    WHERE specimen_id = ?
                    """,
                    (specimen_row[0],),
                ).fetchone()
                self.assertEqual(part_row[1], "head")
                self.assertIsNotNone(part_row[2])
                self.assertIsNotNone(part_row[3])
                self.assertEqual(json.loads(part_row[4]), [[0, 2], [0, 3], [0, 4]])

                roi_row = conn.execute(
                    "SELECT linked_part_id, linked_part_row_id FROM part_rois WHERE specimen_id = ?",
                    (specimen_row[0],),
                ).fetchone()
                self.assertEqual(roi_row, ("head", part_row[0]))

                global_row = conn.execute(
                    "SELECT proposal_id, status, confidence FROM global_axis_proposals WHERE specimen_id = ?",
                    (specimen_row[0],),
                ).fetchone()
                self.assertEqual(global_row[0], "global_001")
                self.assertEqual(global_row[1], "accepted")
                self.assertAlmostEqual(global_row[2], 0.91)

                frame_row = conn.execute(
                    "SELECT proposal_id, status, local_frame_json FROM local_frame_proposals WHERE part_id = ?",
                    (part_row[0],),
                ).fetchone()
                self.assertEqual(frame_row[0], "frame_001")
                self.assertEqual(json.loads(frame_row[2])["output_axis"], "z_axis")

                reslice_row = conn.execute(
                    "SELECT reslice_id, training_json FROM part_reslices WHERE part_id = ?",
                    (part_row[0],),
                ).fetchone()
                self.assertEqual(reslice_row[0], "head_axis_001")
                self.assertTrue(json.loads(reslice_row[1])["human_confirmed"])

                run_artifact = conn.execute(
                    """
                    SELECT artifact_type, role, specimen_id, prediction_id
                    FROM tif_run_artifacts
                    WHERE run_id = ?
                    """,
                    ("external_predict_001",),
                ).fetchone()
                self.assertEqual(run_artifact, ("prediction_label_volume", "model_draft", "01-0101-local", "predict_001"))
            finally:
                conn.close()

    def test_existing_sqlite_artifact_blocks_migration_and_preserves_source_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_json = _build_legacy_tif_project(root / "legacy_tif")
            db_path = root / "project.sqlite"
            db_path.write_text("existing database placeholder", encoding="utf-8")
            original_text = source_json.read_text(encoding="utf-8")

            with self.assertRaises(FileExistsError):
                migrate_legacy_tif_json_to_sqlite(
                    source_json,
                    database_path=db_path,
                    manifest_path=root / "manifest.json",
                    report_path=root / "report.json",
                )

            self.assertEqual(source_json.read_text(encoding="utf-8"), original_text)
            self.assertFalse((root / "manifest.json").exists())
            self.assertFalse((root / "report.json").exists())

    def test_tif_manager_loads_sqlite_manifest_and_saves_index_transactionally(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_json = _build_legacy_tif_project(root / "legacy_tif")
            db_path = root / "project.sqlite"
            manifest_path = root / "project_manifest.json"
            report_path = root / "migration_report.json"

            migrate_legacy_tif_json_to_sqlite(
                source_json,
                database_path=db_path,
                manifest_path=manifest_path,
                report_path=report_path,
            )

            manager = TifProjectManager()
            manager.load_project(manifest_path)
            self.assertEqual(manager.current_storage_backend, "sqlite")
            self.assertEqual(Path(manager.current_database_path), db_path.resolve())
            self.assertEqual(Path(manager.current_asset_root), (root / "legacy_tif").resolve())
            self.assertEqual(manager.project_data["name"], "Legacy TIF ants")
            self.assertEqual(manager.list_parts("01-0101-local")[0]["part_id"], "head")
            self.assertEqual(manager.list_part_rois("01-0101-local")[0]["linked_part_id"], "head")
            self.assertEqual(manager.list_local_axis_runs()[0]["run_id"], "predict_local_frame_001")
            self.assertIn(
                "reslices/head_axis_001/labels/editable_ai_result.ome.zarr",
                manager.part_label_record("01-0101-local", "head", "editable_ai_result", "head_axis_001")["path"],
            )

            manager.add_part(
                "01-0101-local",
                "antenna",
                display_name="Antenna",
                parent_bbox_zyx=[[0, 1], [0, 2], [0, 3]],
                save=True,
            )
            manager.update_part_roi("01-0101-local", "roi_head", status="cancelled", linked_part_id="", save=True)

            reloaded = TifProjectManager()
            reloaded.load_project(manifest_path)
            self.assertEqual([part["part_id"] for part in reloaded.list_parts("01-0101-local")], ["head", "antenna"])
            self.assertEqual(reloaded.get_part_roi("01-0101-local", "roi_head")["status"], "cancelled")
            self.assertIn(
                "reslices/head_axis_001/labels/editable_ai_result.ome.zarr",
                reloaded.part_label_record("01-0101-local", "head", "editable_ai_result", "head_axis_001")["path"],
            )

            conn = sqlite3.connect(db_path)
            try:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM parts").fetchone()[0], 2)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM specimens").fetchone()[0], 1)
                materials_json = conn.execute("SELECT materials_json FROM material_maps").fetchone()[0]
                self.assertEqual(json.loads(materials_json)[1]["name"], "head")
                self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
