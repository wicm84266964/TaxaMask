import tempfile
import unittest
from pathlib import Path

from AntSleap.core.mesh_export_ledger import (
    MESH_EXPORT_SCHEMA_VERSION,
    MeshExportLedger,
    MeshExportLedgerError,
)
from AntSleap.core.tif_sqlite_schema import create_tif_project_database


def _pending(export_id="mesh_test_001", retry_of=None):
    return {
        "export_id": export_id,
        "retry_of": retry_of,
        "project_id": "project_mesh_test",
        "specimen_id": "specimen_mesh_test",
        "source_data_version_id": "data_v0001",
        "target_location_ref": "location_mesh_test",
        "target_relative_path": f"mesh_export_{export_id}",
        "source_relative_path": "specimens/specimen_mesh_test/labels/manual_truth.ome.zarr",
        "source_entry_kind": "directory",
        "source_size_bytes": 123,
        "source_hash_algorithm": "sha256-tree-v1",
        "source_digest": "a" * 64,
        "source_hashed_at": "2026-07-20T00:00:00Z",
        "coordinates": {
            "source_axis_order": "zyx",
            "mesh_axis_order": "xyz",
            "spacing_zyx": [2.0, 1.0, 0.5],
            "spacing_unit": "micrometer",
            "output_unit": "millimeter",
            "scale_status": "verified",
        },
        "requested_labels": [{"label_id": 1, "label_name": "brain"}],
        "options": {
            "preview_smoothing": False,
            "smoothing_iterations": 10,
        },
    }


def _item():
    return {
        "artifact_id": "raw_label_1",
        "label_id": 1,
        "label_name": "brain",
        "kind": "raw",
        "relative_path": "raw/specimen_mesh_test_label_1_brain.stl",
        "size_bytes": 456,
        "hash_algorithm": "sha256",
        "digest": "b" * 64,
        "vertex_count": 8,
        "face_count": 12,
        "bounds_xyz_mm": [[0.0, 0.0, 0.0], [1.0, 2.0, 3.0]],
        "component_count": 1,
        "watertight": True,
        "scale_status": "verified",
        "processing": {
            "smoothed": False,
            "filled_holes": False,
            "removed_components": False,
        },
    }


class MeshExportLedgerTests(unittest.TestCase):
    def test_tif_database_initializes_mesh_export_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            connection = create_tif_project_database(Path(tmp) / "project.sqlite")
            try:
                tables = {
                    str(row[0])
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                }
            finally:
                connection.close()
        self.assertTrue(
            {"mesh_export_runs", "mesh_export_items", "mesh_export_reviews"}
            <= tables
        )

    def test_complete_export_round_trips_without_absolute_target_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = MeshExportLedger(Path(tmp) / "project.sqlite")
            pending = ledger.create_pending(_pending())
            self.assertEqual(pending["record_schema_version"], MESH_EXPORT_SCHEMA_VERSION)
            self.assertEqual(pending["status"], "pending")
            self.assertNotIn("absolute", " ".join(pending.keys()))

            ledger.mark_running(pending["export_id"])
            ledger.add_item(pending["export_id"], _item())
            complete = ledger.finish(pending["export_id"], "complete")

            self.assertEqual(complete["status"], "complete")
            self.assertEqual(complete["stl_item_count"], 1)
            self.assertEqual(complete["completed_item_count"], 1)
            self.assertEqual(complete["items"][0]["label_id"], 1)
            self.assertTrue(complete["items"][0]["watertight"])

            with self.assertRaises(MeshExportLedgerError):
                ledger.finish(pending["export_id"], "failed")
            with self.assertRaises(MeshExportLedgerError):
                ledger.create_pending(_pending("mesh_retry_complete", pending["export_id"]))

    def test_failed_export_can_be_retried_without_overwriting_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = MeshExportLedger(Path(tmp) / "project.sqlite")
            original = ledger.create_pending(_pending("mesh_failed_001"))
            ledger.mark_running(original["export_id"])
            failed = ledger.finish(
                original["export_id"],
                "failed",
                error_code="stl_write_failed",
                error_summary="Synthetic write failure",
                error_stage="publish",
            )
            retry = ledger.create_pending(
                _pending("mesh_retry_001", failed["export_id"])
            )

            self.assertEqual(failed["status"], "failed")
            self.assertEqual(retry["retry_of"], failed["export_id"])
            self.assertEqual(retry["attempt"], 2)
            self.assertEqual(
                ledger.load(failed["export_id"])["error_code"],
                "stl_write_failed",
            )

    def test_retry_requires_same_scope_source_labels_and_options(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = MeshExportLedger(Path(tmp) / "project.sqlite")
            original = ledger.create_pending(_pending("mesh_failed_constraints"))
            ledger.mark_running(original["export_id"])
            ledger.finish(original["export_id"], "failed")

            cases = (
                ("specimen_id", "another_specimen", "retry_scope_changed_create_new_export"),
                ("source_digest", "b" * 64, "retry_source_changed_create_new_export"),
                (
                    "requested_labels",
                    [{"label_id": 2, "label_name": "gland"}],
                    "retry_labels_changed_create_new_export",
                ),
                (
                    "options",
                    {"preview_smoothing": True, "smoothing_iterations": 10},
                    "retry_options_changed_create_new_export",
                ),
            )
            for index, (field, value, expected) in enumerate(cases):
                retry = _pending(
                    f"mesh_retry_constraint_{index}",
                    original["export_id"],
                )
                retry[field] = value
                with self.subTest(field=field):
                    with self.assertRaises(MeshExportLedgerError) as raised:
                        ledger.create_pending(retry)
                    self.assertEqual(str(raised.exception), expected)

    def test_completed_export_review_appends_attention_without_rewriting_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = MeshExportLedger(Path(tmp) / "project.sqlite")
            run = ledger.create_pending(_pending("mesh_review_001"))
            ledger.mark_running(run["export_id"])
            ledger.add_item(run["export_id"], _item())
            ledger.finish(run["export_id"], "complete")

            reviewed = ledger.add_review(
                run["export_id"],
                "needs_attention",
                error_code="stl_digest_mismatch",
                summary="STL no longer matches the completed record.",
                details={"artifact_id": "raw_label_1"},
            )

            self.assertEqual(reviewed["status"], "complete")
            self.assertEqual(reviewed["reviews"][-1]["review_status"], "needs_attention")
            self.assertEqual(
                reviewed["reviews"][-1]["details"]["artifact_id"],
                "raw_label_1",
            )

    def test_export_history_can_be_scoped_to_part_and_reslice(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = MeshExportLedger(Path(tmp) / "project.sqlite")
            full = _pending("mesh_scope_full")
            part = _pending("mesh_scope_part")
            part["part_id"] = "head"
            reslice = _pending("mesh_scope_reslice")
            reslice["part_id"] = "head"
            reslice["reslice_id"] = "head_axis_001"
            for record in (full, part, reslice):
                ledger.create_pending(record)

            self.assertEqual(
                [item["export_id"] for item in ledger.list_exports(
                    specimen_id="specimen_mesh_test",
                    part_id="",
                    reslice_id="",
                )],
                ["mesh_scope_full"],
            )
            self.assertEqual(
                [item["export_id"] for item in ledger.list_exports(
                    specimen_id="specimen_mesh_test",
                    part_id="head",
                    reslice_id="head_axis_001",
                )],
                ["mesh_scope_reslice"],
            )


if __name__ == "__main__":
    unittest.main()
