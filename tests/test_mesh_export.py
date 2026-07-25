import tempfile
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from AntSleap.core.mesh_export import (
    MeshExportError,
    _atomic_publish_stl,
    _scan_label_statistics,
    export_reviewed_label_meshes,
    label_mesh_from_volume,
    recover_interrupted_mesh_exports,
    reviewed_mesh_source_summary,
    safe_cleanup_incomplete_mesh_export,
    spacing_to_millimeters,
    verify_mesh_export,
)
from AntSleap.core.mesh_export_ledger import MeshExportLedger
from AntSleap.core.file_integrity import FULL_FILE_ALGORITHM, compute_fingerprint
from AntSleap.core.project_integrity_registry import get_training_baseline_snapshot
from AntSleap.core.tif_project import TifProjectManager
from AntSleap.core.tif_volume_io import load_volume_sidecar, write_volume_sidecar


def _project(root, *, spacing_unit="micrometer", scale_verified=None):
    if scale_verified is None:
        scale_verified = spacing_unit == "micrometer"
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
        spacing_unit=spacing_unit,
        scale_verified=scale_verified,
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
    manager.initialize_integrity_baseline(
        legacy_truth_attestation=True,
        note="mesh export test fixture",
    )
    return manager


class _FakeMesh:
    def __init__(self, offset=0.0):
        self.vertices = np.asarray(
            [[offset, 0, 0], [offset + 1, 0, 0], [offset, 1, 0], [offset, 0, 1]],
            dtype=np.float64,
        )
        self.faces = np.asarray([[0, 1, 2], [0, 1, 3]], dtype=np.int64)
        self.bounds = np.asarray(
            [[offset, 0, 0], [offset + 1, 1, 1]],
            dtype=np.float64,
        )
        self.is_watertight = True

    def split(self, only_watertight=False):
        return [self]


def _fake_publish_stl(_mesh, final_path):
    path = Path(final_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"synthetic-stl")
    return compute_fingerprint(path, FULL_FILE_ALGORITHM)


def _fake_incomplete_export(manager, target):
    with patch(
        "AntSleap.core.mesh_export.label_mesh_from_volume",
        return_value=(_FakeMesh(), (slice(1, 5), slice(2, 7), slice(1, 6))),
    ), patch(
        "AntSleap.core.mesh_export._atomic_publish_stl",
        side_effect=_fake_publish_stl,
    ):
        record = export_reviewed_label_meshes(
            manager,
            "ant_001",
            target,
            label_ids=[1],
        )
    connection = sqlite3.connect(manager.current_database_path)
    try:
        with connection:
            connection.execute(
                "UPDATE mesh_export_runs SET status = 'incomplete' WHERE export_id = ?",
                (record["export_id"],),
            )
    finally:
        connection.close()
    return MeshExportLedger(manager.current_database_path).load(record["export_id"])


class MeshExportTests(unittest.TestCase):
    def test_spacing_conversion_and_unknown_scale_status(self):
        spacing, status, factor = spacing_to_millimeters(
            [2.0, 3.0, 5.0], "micrometer", scale_verified=True
        )
        self.assertEqual(spacing, [0.002, 0.003, 0.005])
        self.assertEqual(status, "verified")
        self.assertEqual(factor, 0.001)

        spacing, status, factor = spacing_to_millimeters(
            [2.0, 3.0, 5.0], "micrometer"
        )
        self.assertEqual(spacing, [2.0, 3.0, 5.0])
        self.assertEqual(status, "scale_unverified")
        self.assertEqual(factor, 1.0)

        spacing, status, factor = spacing_to_millimeters(
            [2.0, 3.0, 5.0], "unknown_unit"
        )
        self.assertEqual(spacing, [2.0, 3.0, 5.0])
        self.assertEqual(status, "scale_unverified")
        self.assertEqual(factor, 1.0)

        invalid_spacings = (
            [float("nan"), 1.0, 1.0],
            [float("inf"), 1.0, 1.0],
            [float("-inf"), 1.0, 1.0],
        )
        for invalid in invalid_spacings:
            with self.assertRaisesRegex(MeshExportError, "mesh_spacing_invalid"):
                spacing_to_millimeters(invalid, "millimeter")

    def test_supported_unit_name_without_scale_evidence_stays_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = _project(Path(tmp), scale_verified=False)

            summary = reviewed_mesh_source_summary(manager, "ant_001")

            self.assertEqual(summary["spacing_unit"], "micrometer")
            self.assertFalse(summary["scale_verified"])
            self.assertEqual(summary["scale_status"], "scale_unverified")
            self.assertEqual(summary["mesh_purpose"], "observation")
            self.assertEqual(summary["output_unit"], "unitless")

    def test_conflicting_verified_scale_records_stay_observation_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = _project(Path(tmp), scale_verified=True)
            truth = manager.get_specimen("ant_001")["labels"]["manual_truth"]
            truth["spacing_zyx"] = [3.0, 3.0, 5.0]

            summary = reviewed_mesh_source_summary(manager, "ant_001")

            self.assertFalse(summary["scale_verified"])
            self.assertEqual(summary["scale_status"], "scale_unverified")
            self.assertEqual(summary["mesh_purpose"], "observation")
            self.assertEqual(summary["output_unit"], "unitless")

    def test_manual_truth_path_rejects_symlink_components(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = _project(root)
            truth = manager.get_specimen("ant_001")["labels"]["manual_truth"]
            original = Path(manager.to_absolute(truth["path"]))
            linked = original.parent / "manual_truth_link.ome.zarr"
            try:
                linked.symlink_to(original, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation is unavailable")
            truth["path"] = manager.to_relative(linked)

            with self.assertRaises(MeshExportError) as raised:
                reviewed_mesh_source_summary(manager, "ant_001")

            self.assertEqual(
                raised.exception.code,
                "mesh_manual_truth_path_unsafe",
            )

    def test_export_target_rejects_symlink_components(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = _project(root)
            actual_target = root / "actual_exports"
            actual_target.mkdir()
            linked_target = root / "linked_exports"
            try:
                linked_target.symlink_to(actual_target, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation is unavailable")

            with self.assertRaises(MeshExportError) as raised:
                export_reviewed_label_meshes(
                    manager,
                    "ant_001",
                    linked_target,
                    label_ids=[1],
                )

            self.assertEqual(raised.exception.code, "mesh_target_directory_unsafe")

    def test_label_statistics_scan_counts_and_bounds_across_row_chunks(self):
        volume = np.zeros((3, 260, 6), dtype=np.uint16)
        volume[0, 120:132, 1:3] = 1
        volume[1:3, 250:260, 4:6] = 2

        statistics = _scan_label_statistics(volume, row_chunk_size=128)

        self.assertEqual(statistics[1]["voxel_count"], 24)
        self.assertEqual(statistics[1]["bbox_zyx"], [[0, 1], [120, 132], [1, 3]])
        self.assertEqual(statistics[2]["voxel_count"], 40)
        self.assertEqual(statistics[2]["bbox_zyx"], [[1, 3], [250, 260], [4, 6]])

    def test_multi_label_export_scans_once_and_records_unitless_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = _project(root, spacing_unit="unknown")
            target = root / "exports"
            target.mkdir()
            bbox_calls = []

            def fake_label_mesh(_volume, label_id, **kwargs):
                bbox_calls.append((int(label_id), kwargs.get("bbox_zyx")))
                return _FakeMesh(float(label_id)), tuple(
                    slice(int(start), int(stop))
                    for start, stop in kwargs["bbox_zyx"]
                )

            with patch(
                "AntSleap.core.mesh_export._scan_label_statistics",
                wraps=_scan_label_statistics,
            ) as scan, patch(
                "AntSleap.core.mesh_export.label_mesh_from_volume",
                side_effect=fake_label_mesh,
            ), patch(
                "AntSleap.core.mesh_export._atomic_publish_stl",
                side_effect=_fake_publish_stl,
            ):
                record = export_reviewed_label_meshes(
                    manager,
                    "ant_001",
                    target,
                    label_ids=[1, 2],
                )

            self.assertEqual(scan.call_count, 1)
            self.assertEqual([item[0] for item in bbox_calls], [1, 2])
            self.assertTrue(all(item[1] for item in bbox_calls))
            self.assertEqual(record["coordinates"]["mesh_purpose"], "observation")
            self.assertEqual(record["coordinates"]["output_unit"], "unitless")
            self.assertNotIn("spacing_zyx_mm", record["coordinates"])
            for item in record["items"]:
                self.assertEqual(item["role"], "observation_mesh")
                self.assertEqual(item["mesh_purpose"], "observation")
                self.assertEqual(item["bounds_unit"], "unitless")
                self.assertFalse(item["measurement_allowed"])
                self.assertNotIn("bounds_xyz_mm", item)
                self.assertEqual(item["processing"]["bounds_xyz"], item["bounds_xyz"])

    def test_interrupted_export_recovery_recalculates_from_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = _project(root)
            target = root / "exports"
            target.mkdir()
            with patch(
                "AntSleap.core.mesh_export.label_mesh_from_volume",
                return_value=(_FakeMesh(), (slice(1, 5), slice(2, 7), slice(1, 6))),
            ), patch(
                "AntSleap.core.mesh_export._atomic_publish_stl",
                side_effect=_fake_publish_stl,
            ):
                record = export_reviewed_label_meshes(
                    manager,
                    "ant_001",
                    target,
                    label_ids=[1],
                )

            connection = sqlite3.connect(manager.current_database_path)
            try:
                with connection:
                    connection.execute(
                        "UPDATE mesh_export_runs SET status = 'running' WHERE export_id = ?",
                        (record["export_id"],),
                    )
            finally:
                connection.close()
            recovered = recover_interrupted_mesh_exports(manager)
            self.assertEqual(recovered["complete_count"], 1)
            self.assertEqual(recovered["records"][0]["status"], "complete")

            item_path = (
                target
                / record["target_relative_path"]
                / record["items"][0]["relative_path"]
            )
            item_path.unlink()
            connection = sqlite3.connect(manager.current_database_path)
            try:
                with connection:
                    connection.execute(
                        "UPDATE mesh_export_runs SET status = 'running' WHERE export_id = ?",
                        (record["export_id"],),
                    )
            finally:
                connection.close()
            recovered = recover_interrupted_mesh_exports(manager)
            self.assertEqual(recovered["incomplete_count"], 1)
            self.assertEqual(recovered["records"][0]["status"], "incomplete")

    def test_measurement_raw_and_smoothed_preview_have_distinct_roles(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = _project(root)
            with patch(
                "AntSleap.core.mesh_export.label_mesh_from_volume",
                return_value=(_FakeMesh(), (slice(1, 5), slice(2, 7), slice(1, 6))),
            ), patch(
                "AntSleap.core.mesh_export.smoothed_preview_mesh",
                return_value=_FakeMesh(0.25),
            ), patch(
                "AntSleap.core.mesh_export._atomic_publish_stl",
                side_effect=_fake_publish_stl,
            ):
                record = export_reviewed_label_meshes(
                    manager,
                    "ant_001",
                    root,
                    label_ids=[1],
                    preview_smoothing=True,
                )

            by_kind = {item["kind"]: item for item in record["items"]}
            raw = by_kind["raw"]
            preview = by_kind["preview"]
            self.assertEqual(raw["role"], "measurement_mesh")
            self.assertEqual(raw["mesh_purpose"], "measurement")
            self.assertTrue(raw["measurement_allowed"])
            self.assertEqual(raw["bounds_xyz_mm"], raw["bounds_xyz"])
            self.assertEqual(preview["role"], "display_preview")
            self.assertEqual(preview["mesh_purpose"], "display_preview")
            self.assertFalse(preview["measurement_allowed"])
            self.assertEqual(preview["bounds_unit"], "millimeter")
            self.assertNotIn("bounds_xyz_mm", preview)
            self.assertEqual(
                preview["processing"]["source_mesh_purpose"],
                "measurement",
            )

    def test_mesh_truth_requires_explicit_status_but_allows_legacy_missing_role(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = _project(root)
            truth = manager.get_specimen("ant_001")["labels"]["manual_truth"]
            truth.pop("role", None)
            truth["status"] = ""
            truth.pop("review_audit", None)
            truth.pop("training", None)
            with self.assertRaises(MeshExportError) as raised:
                export_reviewed_label_meshes(
                    manager,
                    "ant_001",
                    root,
                    label_ids=[1],
                )
            self.assertEqual(raised.exception.code, "mesh_manual_truth_not_reviewed")

            truth["status"] = "reviewed"
            with patch(
                "AntSleap.core.mesh_export.label_mesh_from_volume",
                return_value=(_FakeMesh(), (slice(1, 5), slice(2, 7), slice(1, 6))),
            ), patch(
                "AntSleap.core.mesh_export._atomic_publish_stl",
                side_effect=_fake_publish_stl,
            ):
                record = export_reviewed_label_meshes(
                    manager,
                    "ant_001",
                    root,
                    label_ids=[1],
                )
            self.assertEqual(record["status"], "complete")

    def test_summary_and_export_block_externally_changed_reviewed_truth(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = _project(root)
            truth_path = manager.to_absolute(
                manager.get_specimen("ant_001")["labels"]["manual_truth"]["path"]
            )
            source = load_volume_sidecar(truth_path, mmap_mode="r+")
            source[0, 0, 0] = 2
            source.flush()
            source._mmap.close()

            with self.assertRaises(MeshExportError) as summary_error:
                reviewed_mesh_source_summary(manager, "ant_001")
            self.assertEqual(
                summary_error.exception.code,
                "mesh_manual_truth_registry_mismatch",
            )
            with self.assertRaises(MeshExportError) as export_error:
                export_reviewed_label_meshes(
                    manager,
                    "ant_001",
                    root,
                    label_ids=[1],
                )
            self.assertEqual(
                export_error.exception.code,
                "mesh_manual_truth_registry_mismatch",
            )

    def test_export_blocks_when_open_project_version_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = _project(root)
            stale_version = manager.project_data["project_data_version_id"]
            manager.add_or_update_label_schema(
                "internal_regions",
                labels=[
                    {"id": 1, "name": "brain", "display_name": "Brain"},
                    {"id": 2, "name": "gland", "display_name": "Gland"},
                    {"id": 3, "name": "nerve", "display_name": "Nerve"},
                ],
            )
            self.assertNotEqual(
                manager.project_data["project_data_version_id"],
                stale_version,
            )
            manager.project_data["project_data_version_id"] = stale_version

            with self.assertRaises(MeshExportError) as raised:
                export_reviewed_label_meshes(
                    manager,
                    "ant_001",
                    root,
                    label_ids=[1],
                )
            self.assertEqual(
                raised.exception.code,
                "mesh_registry_data_version_mismatch",
            )

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

            recovered = recover_interrupted_mesh_exports(manager)
            self.assertEqual(recovered["checked_count"], 0)
            self.assertEqual(
                MeshExportLedger(manager.current_database_path)
                .load(record["export_id"])["status"],
                "incomplete",
            )

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

    def test_safe_cleanup_rejects_tampered_relative_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = _project(root)
            target = root / "exports"
            target.mkdir()
            record = _fake_incomplete_export(manager, target)
            export_root = target / record["target_relative_path"]
            outside = root / "outside"
            outside.mkdir()
            sentinel = outside / "keep.txt"
            sentinel.write_text("keep", encoding="utf-8")

            invalid_paths = (
                "../outside",
                "nested/name",
                "mesh_export_mesh_x\\..\\outside",
                "wrong_prefix",
            )
            for invalid in invalid_paths:
                with self.subTest(target_relative_path=invalid):
                    connection = sqlite3.connect(manager.current_database_path)
                    try:
                        with connection:
                            connection.execute(
                                "UPDATE mesh_export_runs SET target_relative_path = ? WHERE export_id = ?",
                                (invalid, record["export_id"]),
                            )
                    finally:
                        connection.close()
                    with self.assertRaises(MeshExportError) as raised:
                        safe_cleanup_incomplete_mesh_export(
                            manager,
                            record["export_id"],
                        )
                    self.assertEqual(
                        raised.exception.code,
                        "mesh_cleanup_target_invalid",
                    )
                    self.assertTrue(sentinel.is_file())
                    self.assertTrue(export_root.is_dir())

    def test_safe_cleanup_rejects_linked_export_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = _project(root)
            target = root / "exports"
            target.mkdir()
            record = _fake_incomplete_export(manager, target)
            export_root = target / record["target_relative_path"]
            relocated = target / "relocated_export"
            export_root.rename(relocated)
            try:
                export_root.symlink_to(relocated, target_is_directory=True)
            except (OSError, NotImplementedError):
                relocated.rename(export_root)
                self.skipTest("symlink creation is unavailable")

            with self.assertRaises(MeshExportError) as raised:
                safe_cleanup_incomplete_mesh_export(
                    manager,
                    record["export_id"],
                )

            self.assertEqual(
                raised.exception.code,
                "mesh_cleanup_target_unsafe",
            )
            self.assertTrue(relocated.is_dir())

    def test_safe_cleanup_rejects_linked_descendant(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = _project(root)
            target = root / "exports"
            target.mkdir()
            record = _fake_incomplete_export(manager, target)
            export_root = target / record["target_relative_path"]
            outside = root / "outside"
            outside.mkdir()
            sentinel = outside / "keep.txt"
            sentinel.write_text("keep", encoding="utf-8")
            linked = export_root / "linked_external"
            try:
                linked.symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation is unavailable")

            with self.assertRaises(MeshExportError) as raised:
                safe_cleanup_incomplete_mesh_export(
                    manager,
                    record["export_id"],
                )

            self.assertEqual(
                raised.exception.code,
                "mesh_cleanup_target_unsafe",
            )
            self.assertTrue(sentinel.is_file())
            self.assertTrue(export_root.is_dir())

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
                "mesh_manual_truth_registry_mismatch",
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
            self.assertEqual(record["error_stage"], "commit_complete")
            self.assertEqual(
                record["recovery_action"],
                "verify_complete_or_retry_or_safe_cleanup",
            )

            recovered = recover_interrupted_mesh_exports(manager)
            self.assertEqual(recovered["checked_count"], 1)
            self.assertEqual(recovered["complete_count"], 1)
            self.assertEqual(recovered["records"][0]["status"], "complete")

    def test_complete_commit_failure_with_changed_source_stays_incomplete(self):
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

            truth_path = manager.to_absolute(
                manager.get_specimen("ant_001")["labels"]["manual_truth"]["path"]
            )
            source = load_volume_sidecar(truth_path, mmap_mode="r+")
            source[0, 0, 0] = 2
            source.flush()
            source._mmap.close()

            recovered = recover_interrupted_mesh_exports(manager)
            self.assertEqual(recovered["checked_count"], 1)
            self.assertEqual(recovered["complete_count"], 0)
            self.assertEqual(recovered["incomplete_count"], 1)
            self.assertEqual(
                MeshExportLedger(manager.current_database_path)
                .load(raised.exception.export_id)["recovery_action"],
                "retry_or_safe_cleanup",
            )

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

    def test_verify_resolves_source_from_export_data_version(self):
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

            with patch(
                "AntSleap.core.mesh_export.get_training_baseline_snapshot",
                wraps=get_training_baseline_snapshot,
            ) as snapshot:
                reviewed = verify_mesh_export(manager, record["export_id"])

            self.assertEqual(reviewed["reviews"][-1]["review_status"], "verified")
            self.assertEqual(
                snapshot.call_args.args[1],
                record["source_data_version_id"],
            )

    def test_verify_rejects_linked_export_root(self):
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
            export_root = target / record["target_relative_path"]
            relocated = target / f"{record['target_relative_path']}_relocated"
            export_root.rename(relocated)
            try:
                export_root.symlink_to(relocated, target_is_directory=True)
            except (OSError, NotImplementedError):
                relocated.rename(export_root)
                self.skipTest("symlink creation is unavailable")

            reviewed = verify_mesh_export(manager, record["export_id"])

            self.assertEqual(reviewed["reviews"][-1]["review_status"], "needs_attention")
            self.assertIn(
                "target_path_unsafe",
                {
                    item["reason"]
                    for item in reviewed["reviews"][-1]["details"]["issues"]
                },
            )


if __name__ == "__main__":
    unittest.main()
