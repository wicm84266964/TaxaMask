import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import numpy as np

from AntSleap.core.tif_sqlite_loader import _json_loads, load_tif_sqlite_project_data, load_tif_sqlite_project_manifest
from AntSleap.core.tif_sqlite_migration import migrate_legacy_tif_json_to_sqlite
from AntSleap.core.tif_volume_io import write_volume_sidecar
from tests.test_tif_json_to_sqlite_migration import _build_legacy_tif_project


class TifSQLiteLoaderTests(unittest.TestCase):
    def _migrate_rich_project(self, root):
        source_json = _build_legacy_tif_project(root / "legacy_tif")
        db_path = root / "legacy_tif.taxamask_tif.sqlite"
        manifest_path = root / "legacy_tif.tif_sqlite_manifest.json"
        migrate_legacy_tif_json_to_sqlite(
            source_json,
            database_path=db_path,
            manifest_path=manifest_path,
            report_path=root / "migration_report.json",
        )
        return db_path, manifest_path

    def test_manifest_loader_preserves_research_roles_runs_and_reslice_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path, manifest_path = self._migrate_rich_project(root)

            loaded = load_tif_sqlite_project_manifest(manifest_path)
            project_data = loaded["project_data"]

            self.assertEqual(Path(loaded["database_path"]), db_path.resolve())
            self.assertEqual(project_data["name"], "Legacy TIF ants")
            self.assertEqual(project_data["project_type"], "tif_volume")
            self.assertEqual(project_data["models"][0]["model_id"], "local_axis/head_frame_v1")

            specimen = project_data["specimens"][0]
            self.assertEqual(specimen["specimen_id"], "01-0101-local")
            self.assertEqual(specimen["labels"]["manual_truth"]["status"], "reviewed")
            self.assertEqual(specimen["labels"]["working_edit"]["status"], "in_progress")
            self.assertEqual(specimen["labels"]["model_drafts"][0]["prediction_id"], "predict_001")
            self.assertEqual(specimen["part_rois"][0]["linked_part_id"], "head")
            self.assertEqual(specimen["metadata"]["local_axis_global_proposals"][0]["global_proposal_id"], "global_001")

            part = specimen["parts"][0]
            self.assertEqual(part["part_id"], "head")
            self.assertEqual(part["system_status"], "cut_pending_labeling")
            self.assertEqual(part["metadata"]["local_axis_frame_proposals"][0]["frame_proposal_id"], "frame_001")

            reslice = part["metadata"]["local_axis_reslices"][0]
            self.assertEqual(reslice["reslice_id"], "head_axis_001")
            self.assertTrue(reslice["training"]["human_confirmed"])
            self.assertTrue(reslice["training"]["usable_for_training"])
            self.assertIn(
                "editable_ai_result.ome.zarr",
                reslice["labels"]["editable_ai_result"]["path"],
            )

            runs = {item["run_id"]: item for item in project_data["runs"]}
            self.assertEqual(runs["predict_local_frame_001"]["metrics"]["accepted"], 1)
            self.assertEqual(runs["external_predict_001"]["artifacts"][0]["role"], "model_draft")
            self.assertEqual(runs["external_predict_001"]["artifacts"][0]["prediction_id"], "predict_001")

    def test_part_label_roles_round_trip_from_sqlite_volume_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path, _manifest_path = self._migrate_rich_project(root)

            conn = sqlite3.connect(db_path)
            try:
                part_row = conn.execute("SELECT id FROM parts WHERE part_id = ?", ("head",)).fetchone()
                self.assertIsNotNone(part_row)
                specimen_row = conn.execute("SELECT id FROM specimens WHERE specimen_id = ?", ("01-0101-local",)).fetchone()
                self.assertIsNotNone(specimen_row)
                part_row_id = int(part_row[0])
                specimen_row_id = int(specimen_row[0])

                for stored_role, filename, fill_value in (
                    ("part_manual_truth", "manual_truth.ome.zarr", 1),
                    ("part_editable_ai_result", "editable_ai_result.ome.zarr", 2),
                    ("part_raw_ai_prediction_backup", "raw_ai_prediction_backup.ome.zarr", 3),
                ):
                    rel_path = f"legacy_tif/specimens/01-0101-local/parts/head/labels/{filename}"
                    meta = write_volume_sidecar(root / rel_path, np.full((2, 3, 4), fill_value, dtype=np.uint16), role=stored_role)
                    conn.execute(
                        """
                        INSERT INTO volume_assets (
                            specimen_id, part_id, asset_key, role, path, format,
                            shape_zyx_json, dtype, spacing_zyx_json, spacing_unit,
                            orientation, status, metadata_json
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            specimen_row_id,
                            part_row_id,
                            f"parts.head.labels.{stored_role}",
                            stored_role,
                            rel_path,
                            meta["format"],
                            json.dumps(meta["shape_zyx"]),
                            meta["dtype"],
                            json.dumps(meta["spacing_zyx"]),
                            meta["spacing_unit"],
                            meta["orientation"],
                            "available",
                            "{}",
                        ),
                    )
                conn.commit()
            finally:
                conn.close()

            project_data = load_tif_sqlite_project_data(db_path)["project_data"]
            part = project_data["specimens"][0]["parts"][0]
            labels = part["labels"]
            self.assertIn("manual_truth.ome.zarr", labels["manual_truth"]["path"])
            self.assertIn("editable_ai_result.ome.zarr", labels["editable_ai_result"]["path"])
            self.assertIn("raw_ai_prediction_backup.ome.zarr", labels["raw_ai_prediction_backup"]["path"])
            self.assertEqual(labels["manual_truth"]["status"], "available")
            self.assertEqual(labels["editable_ai_result"]["status"], "available")
            self.assertEqual(labels["raw_ai_prediction_backup"]["status"], "available")

    def test_corrupted_optional_json_falls_back_without_blocking_project_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path, _manifest_path = self._migrate_rich_project(root)
            conn = sqlite3.connect(db_path)
            try:
                conn.execute("UPDATE tif_projects SET metadata_json = ?", ("{broken",))
                conn.execute("UPDATE parts SET metadata_json = ?, parent_bbox_zyx_json = ?", ("not-json", "not-json"))
                conn.execute("UPDATE part_reslices SET training_json = ?", ("not-json",))
                conn.commit()
            finally:
                conn.close()

            loaded = load_tif_sqlite_project_data(db_path)
            project_data = loaded["project_data"]
            specimen = project_data["specimens"][0]
            part = specimen["parts"][0]
            reslice = part["metadata"]["local_axis_reslices"][0]

            self.assertEqual(project_data["label_schemas"], [])
            self.assertEqual(part["parent_bbox_zyx"], [])
            self.assertIn("local_axis_reslices", part["metadata"])
            self.assertIn("local_axis_frame_proposals", part["metadata"])
            self.assertEqual(part["metadata"]["local_axis_reslices"], [reslice])
            self.assertEqual(part["metadata"]["local_axis_frame_proposals"][0]["frame_proposal_id"], "frame_001")
            self.assertEqual(reslice["training"], {})
            self.assertFalse(reslice["labels"]["editable_ai_result"]["path"])

    def test_json_loads_returns_fallback_for_empty_invalid_or_null_payloads(self):
        fallback = {"safe": True}

        self.assertIs(_json_loads(None, fallback), fallback)
        self.assertIs(_json_loads("", fallback), fallback)
        self.assertIs(_json_loads("{bad-json", fallback), fallback)
        self.assertIs(_json_loads("null", fallback), fallback)
        self.assertEqual(_json_loads('{"ok": true}', fallback), {"ok": True})


if __name__ == "__main__":
    unittest.main()
