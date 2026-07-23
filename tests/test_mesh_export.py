import tempfile
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from AntSleap.core.mesh_export import (
    MeshExportError,
    _atomic_publish_stl,
    export_reviewed_label_meshes,
    label_mesh_from_volume,
    safe_cleanup_incomplete_mesh_export,
    spacing_to_millimeters,
    verify_mesh_export,
)
from AntSleap.core.mesh_export_ledger import MeshExportLedger
from AntSleap.core.tif_project import TifProjectManager
from AntSleap.core.tif_volume_io import load_volume_sidecar, write_volume_sidecar


def _project(root):
    project_root = root / "project"
    manager = TifProjectManager()
    manager.location_registry_database_path = root / "locations.sqlite"
    manager.create_project("mesh_export", project_root)
    manager.create_specimen_scaffold("ant_001", modality="micro_ct")
    manager.add_or_update_label_schema(
        "internal_regions",
        labels=[
            {"id": 1, "name": "brain", "display_name": "Brain"},
            {"id": 2, "name": "gland", "display_name": "Gland"},
        ],
        save=False,
    )
    volume = np.zeros((8, 10, 12), dtype=np.uint16)
    volume[1:5, 2:7, 1:6] = 1
    volume[4:7, 5:9, 7:11] = 2
    relative = "specimens/ant_001/labels/manual_truth.ome.zarr"
    metadata = write_volume_sidecar(
        project_root / relative,
        volume,
        role="manual_truth",
        spacing_zyx=[2.0, 3.0, 5.0],
        spacing_unit="micrometer",
    )
    manager.register_label_volume(
        "ant_001",
        "manual_truth",
        relative,
        metadata["shape_zyx"],
        metadata["dtype"],
        spacing_zyx=metadata["spacing_zyx"],
        spacing_unit=metadata["spacing_unit"],
        save=False,
    )
    manager.get_specimen("ant_001")["labels"]["manual_truth"]["status"] = "reviewed"
    manager.set_review_status("ant_001", "reviewed", train_ready=True)
    manager.save_project()
    return manager


class MeshExportTests(unittest.TestCase):
    def test_spacing_conversion_and_unknown_scale_status(self):
        spacing, status, factor = spacing_to_millimeters(
            [2.0, 3.0, 5.0], "micrometer"
        )
        self.assertEqual(spacing, [0.002, 0.003, 0.005])
        self.assertEqual(status, "verified")
        self.assertEqual(factor, 0.001)

        spacing, status, factor = spacing_to_millimeters(
            [2.0, 3.0, 5.0], "unknown_unit"
        )
        self.assertEqual(spacing, [2.0, 3.0, 5.0])
        self.assertEqual(status, "scale_unverified")
        self.assertEqual(factor, 1.0)

    def test_non_isotropic_zyx_volume_becomes_physical_xyz_mesh(self):
        volume = np.zeros((5, 6, 7), dtype=np.uint8)
        volume[1:4, 2:5, 1:6] = 3
        mesh, bbox = label_mesh_from_volume(
            volume,
            3,
            spacing_zyx_mm=[0.002, 0.003, 0.005],
        )

        self.assertEqual(
            [(item.start, item.stop) for item in bbox],
            [(1, 4), (2, 5), (1, 6)],
        )
        np.testing.assert_allclose(
            mesh.bounds,
            [[0.0025, 0.0045, 0.001], [0.0275, 0.0135, 0.007]],
            rtol=0,
            atol=1e-9,
        )
        self.assertTrue(mesh.is_watertight)

    def test_edge_single_voxel_and_multiple_components_are_preserved(self):
        edge = np.zeros((3, 3, 3), dtype=np.uint8)
        edge[0, 0, 0] = 1
        single, _bbox = label_mesh_from_volume(
            edge,
            1,
            spacing_zyx_mm=[1.0, 1.0, 1.0],
        )
        self.assertGreater(len(single.faces), 0)
        np.testing.assert_allclose(single.bounds[0], [-0.5, -0.5, -0.5])

        separated = np.zeros((8, 8, 8), dtype=np.uint8)
        separated[1:3, 1:3, 1:3] = 2
        separated[5:7, 5:7, 5:7] = 2
        multiple, _bbox = label_mesh_from_volume(
            separated,
            2,
            spacing_zyx_mm=[1.0, 1.0, 1.0],
        )
        self.assertEqual(len(multiple.split(only_watertight=False)), 2)

        with self.assertRaises(MeshExportError) as raised:
            label_mesh_from_volume(
                separated,
                3,
                spacing_zyx_mm=[1.0, 1.0, 1.0],
            )
        self.assertEqual(raised.exception.code, "mesh_label_empty")

    def test_export_records_raw_and_preview_stl_in_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = _project(root)
            target = root / "exports"
            target.mkdir()

            record = export_reviewed_label_meshes(
                manager,
                "ant_001",
                target,
                label_ids=[1, 2],
                preview_smoothing=True,
                smoothing_iterations=3,
            )

            self.assertEqual(record["status"], "complete")
            self.assertEqual(len(record["items"]), 4)
            self.assertEqual(
                {item["kind"] for item in record["items"]},
                {"raw", "preview"},
            )
            self.assertEqual(record["coordinates"]["mesh_axis_order"], "xyz")
            self.assertEqual(record["coordinates"]["output_unit"], "millimeter")
            self.assertNotIn(str(target), str(record))
            export_root = target / record["target_relative_path"]
            for item in record["items"]:
                self.assertTrue((export_root / item["relative_path"]).is_file())
                self.assertEqual(len(item["digest"]), 64)
            raw = [item for item in record["items"] if item["kind"] == "raw"]
            self.assertTrue(all(not item["processing"]["smoothed"] for item in raw))
            previews = [item for item in record["items"] if item["kind"] == "preview"]
            self.assertTrue(
                all("metric_delta_from_raw" in item["processing"] for item in previews)
            )
            self.assertEqual(list(export_root.rglob("*.json")), [])

    def test_cancel_after_first_item_leaves_incomplete_recoverable_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = _project(root)
            target = root / "exports"
            target.mkdir()
            state = {"cancel": False}

            def progress(_done, _total, stage):
                if stage == "raw_label_1":
                    state["cancel"] = True

            record = export_reviewed_label_meshes(
                manager,
                "ant_001",
                target,
                label_ids=[1, 2],
                cancel_check=lambda: state["cancel"],
                progress_callback=progress,
            )

            self.assertEqual(record["status"], "incomplete")
            self.assertEqual(record["error_code"], "mesh_export_cancelled")
            self.assertEqual(len(record["items"]), 1)
            self.assertEqual(record["recovery_action"], "retry_or_safe_cleanup")

            reviewed = verify_mesh_export(manager, record["export_id"])
            self.assertEqual(reviewed["status"], "incomplete")
            self.assertTrue(
                any(
                    issue.get("reason") == "stl_not_recorded"
                    for issue in reviewed["reviews"][-1].get("details", {}).get("issues", [])
                )
                if reviewed.get("reviews")
                else reviewed["error_code"] == "mesh_export_verification_failed"
            )

            export_root = target / record["target_relative_path"]
            self.assertTrue(export_root.exists())
            cleaned = safe_cleanup_incomplete_mesh_export(
                manager,
                record["export_id"],
            )
            self.assertFalse(export_root.exists())
            self.assertEqual(
                cleaned["reviews"][-1]["error_code"],
                "mesh_export_safely_cleaned",
            )

    def test_retry_refuses_changed_reviewed_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = _project(root)
            target = root / "exports"
            target.mkdir()
            state = {"cancel": False}

            def progress(_done, _total, stage):
                if stage == "raw_label_1":
                    state["cancel"] = True

            record = export_reviewed_label_meshes(
                manager,
                "ant_001",
                target,
                label_ids=[1, 2],
                cancel_check=lambda: state["cancel"],
                progress_callback=progress,
            )
            source = load_volume_sidecar(
                manager.to_absolute(
                    manager.get_specimen("ant_001")["labels"]["manual_truth"]["path"]
                ),
                mmap_mode="r+",
            )
            source[0, 0, 0] = 1
            source.flush()
            source._mmap.close()

            with self.assertRaises(MeshExportError) as raised:
                export_reviewed_label_meshes(
                    manager,
                    "ant_001",
                    target,
                    label_ids=[1, 2],
                    retry_of=record["export_id"],
                )
            self.assertEqual(
                raised.exception.code,
                "retry_source_changed_create_new_export",
            )

    def test_publish_failure_is_recorded_without_success_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = _project(root)
            target = root / "exports"
            target.mkdir()

            with patch(
                "AntSleap.core.mesh_export._atomic_publish_stl",
                side_effect=OSError("synthetic disk full"),
            ):
                with self.assertRaises(MeshExportError) as raised:
                    export_reviewed_label_meshes(
                        manager,
                        "ant_001",
                        target,
                        label_ids=[1],
                    )

            record = MeshExportLedger(manager.current_database_path).load(
                raised.exception.export_id
            )
            self.assertEqual(record["status"], "incomplete")
            self.assertEqual(record["error_code"], "OSError")
            self.assertEqual(record["completed_item_count"], 0)

    def test_temporary_stl_validation_failure_leaves_no_partial_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            volume = np.zeros((4, 4, 4), dtype=np.uint8)
            volume[1:3, 1:3, 1:3] = 1
            mesh, _bbox = label_mesh_from_volume(
                volume,
                1,
                spacing_zyx_mm=[1.0, 1.0, 1.0],
            )
            final_path = Path(tmp) / "raw" / "label_1.stl"
            with patch("trimesh.load_mesh", side_effect=OSError("interrupted reopen")):
                with self.assertRaises(OSError):
                    _atomic_publish_stl(mesh, final_path)
            self.assertFalse(final_path.exists())
            self.assertEqual(list(final_path.parent.glob("*.tmp_*")), [])

    def test_sqlite_final_commit_failure_is_recoverable_not_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = _project(root)
            target = root / "exports"
            target.mkdir()
            original_finish = MeshExportLedger.finish
            failed_once = {"value": False}

            def fail_first_complete(ledger, export_id, status, **kwargs):
                if status == "complete" and not failed_once["value"]:
                    failed_once["value"] = True
                    raise sqlite3.OperationalError("synthetic final commit failure")
                return original_finish(ledger, export_id, status, **kwargs)

            with patch.object(MeshExportLedger, "finish", new=fail_first_complete):
                with self.assertRaises(MeshExportError) as raised:
                    export_reviewed_label_meshes(
                        manager,
                        "ant_001",
                        target,
                        label_ids=[1],
                    )

            record = MeshExportLedger(manager.current_database_path).load(
                raised.exception.export_id
            )
            self.assertEqual(record["status"], "incomplete")
            self.assertEqual(record["error_code"], "OperationalError")
            self.assertEqual(len(record["items"]), 1)

    def test_completed_export_tamper_appends_attention_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = _project(root)
            target = root / "exports"
            target.mkdir()
            record = export_reviewed_label_meshes(
                manager,
                "ant_001",
                target,
                label_ids=[1],
            )
            item = record["items"][0]
            stl_path = target / record["target_relative_path"] / item["relative_path"]
            stl_path.write_bytes(stl_path.read_bytes() + b"tampered")

            reviewed = verify_mesh_export(manager, record["export_id"])

            self.assertEqual(reviewed["status"], "complete")
            self.assertEqual(reviewed["reviews"][-1]["review_status"], "needs_attention")
            self.assertEqual(
                reviewed["reviews"][-1]["details"]["issues"][0]["artifact_id"],
                item["artifact_id"],
            )


if __name__ == "__main__":
    unittest.main()
