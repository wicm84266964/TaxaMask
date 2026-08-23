import copy
import json
import multiprocessing
import os
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import tifffile

from AntSleap.core import safe_io, tif_part_extraction
from AntSleap.core.tif_materials import read_material_map
from AntSleap.core.tif_part_extraction import (
    add_polygon_keyframe,
    add_rectangular_keyframe,
    build_preview_mask_from_contours,
    crop_volume_to_part,
    read_contours_json,
    validate_contours_for_interpolation,
)
from AntSleap.core.tif_local_axis_reslice import align_editable_axis_to_reference_plane
from AntSleap.core.tif_project import (
    TIF_PROJECT_SCHEMA_VERSION,
    TIF_PROJECT_TYPE,
    TIF_VOLUME_CLEANUP_WARNING_LIMIT,
    TIF_VOLUME_CLEANUP_WARNING_MAX_BYTES,
    TIF_VOLUME_CLEANUP_WARNING_SCHEMA_VERSION,
    TifProjectManager,
)
from AntSleap.core.tif_volume_io import (
    VOLUME_SIDECAR_FORMAT,
    begin_volume_sidecar_replacement,
    copy_volume_sidecar,
    create_empty_label_sidecar_like,
    load_volume_sidecar,
    read_volume_metadata,
    write_volume_sidecar,
)


def _persist_cleanup_warning_worker(
    manifest_path,
    warning_id,
    ready_queue,
    start_event,
    result_queue,
):
    manager = TifProjectManager()
    manager.load_project(manifest_path)
    manager.volume_cleanup_warnings = [
        manager._normalize_volume_cleanup_warning(
            {
                "warning_id": warning_id,
                "recorded_at": "2026-08-24T00:00:00+00:00",
                "operation": warning_id,
                "error": "locked",
            }
        )
    ]
    manager._volume_cleanup_warning_dirty_ids.update(
        warning["warning_id"] for warning in manager.volume_cleanup_warnings
    )
    ready_queue.put(warning_id)
    if not start_event.wait(15):
        result_queue.put((warning_id, "start_timeout"))
        return
    result_queue.put((warning_id, manager._persist_volume_cleanup_warnings()))


class TifProjectTests(unittest.TestCase):
    def _create_directory_alias(self, alias, target):
        alias = Path(alias)
        target = Path(target)
        try:
            os.symlink(target, alias, target_is_directory=True)
            return
        except OSError as exc:
            if os.name != "nt":
                self.skipTest(f"directory aliases are unavailable: {exc}")
            result = subprocess.run(
                [
                    "cmd.exe",
                    "/d",
                    "/c",
                    "mklink",
                    "/J",
                    str(alias),
                    str(target),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                self.skipTest(
                    f"directory aliases are unavailable: {exc}; {result.stderr}"
                )

    @staticmethod
    def _remove_directory_alias(alias):
        alias = Path(alias)
        if not os.path.lexists(alias):
            return
        if os.name == "nt":
            os.rmdir(alias)
        else:
            alias.unlink()

    def _working_edit_copy_fixture(self, root, project_name):
        project_root = Path(root) / project_name
        manager = TifProjectManager()
        manifest_path = manager.create_project(project_name, project_root)
        manager.create_specimen_scaffold("specimen")
        manual_rel = "specimens/specimen/labels/manual_truth.ome.zarr"
        working_rel = "specimens/specimen/labels/working_edit.ome.zarr"
        draft_rel = "specimens/specimen/labels/model_draft/prediction.ome.zarr"
        manual_array = np.full((2, 3, 4), 2, dtype=np.uint16)
        working_array = np.full((2, 3, 4), 1, dtype=np.uint16)
        draft_array = np.full((2, 3, 4), 9, dtype=np.uint16)
        manual_meta = write_volume_sidecar(
            project_root / manual_rel, manual_array, role="manual_truth"
        )
        working_meta = write_volume_sidecar(
            project_root / working_rel, working_array, role="working_edit"
        )
        draft_meta = write_volume_sidecar(
            project_root / draft_rel, draft_array, role="model_draft"
        )
        manager.register_label_volume(
            "specimen",
            "manual_truth",
            manual_rel,
            manual_meta["shape_zyx"],
            manual_meta["dtype"],
            status="reviewed",
            explicit_review=True,
            operation="truth_promotion",
            audit_metadata={"review_action": "test_fixture"},
            save=False,
        )
        manager.register_label_volume(
            "specimen",
            "working_edit",
            working_rel,
            working_meta["shape_zyx"],
            working_meta["dtype"],
            status="in_progress",
            save=False,
        )
        manager.add_model_draft(
            "specimen",
            draft_rel,
            draft_meta["shape_zyx"],
            draft_meta["dtype"],
            "prediction",
            save=False,
        )
        manager.get_specimen("specimen")["review_status"] = "reviewed"
        manager.get_specimen("specimen")["train_ready"] = True
        manager.save_project()
        return {
            "manager": manager,
            "manifest_path": manifest_path,
            "project_root": project_root,
            "manual_path": project_root / manual_rel,
            "working_path": project_root / working_rel,
            "draft_path": project_root / draft_rel,
            "manual_array": manual_array,
            "working_array": working_array,
            "draft_array": draft_array,
        }

    def test_failed_load_restores_complete_manager_runtime_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            manager.create_project("existing", root / "existing")
            manager.create_specimen_scaffold("specimen")
            manager.volume_cleanup_warnings.append({"error": "existing warning"})
            before = copy.deepcopy(manager.__dict__)
            invalid_path = root / "invalid.json"
            invalid_path.write_text(
                json.dumps({"schema_version": "unsupported", "project_type": TIF_PROJECT_TYPE}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "unsupported_tif_project_schema"):
                manager.load_project(invalid_path)

            self.assertEqual(manager.__dict__, before)

    def test_successful_load_does_not_carry_pending_data_version_into_target_project(self):
        from AntSleap.core.tif_integrity_bridge import register_tif_project_baseline

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            manager.create_project("source", root / "source")
            source_pending_version = manager._mark_manual_truth_data_changed()

            target_manager = TifProjectManager()
            target_manifest = target_manager.create_project("target", root / "target")
            target_database = target_manager.current_database_path
            register_tif_project_baseline(target_manager)

            manager.load_project(target_manifest)

            self.assertEqual(manager._pending_project_data_version_id, "")
            manager.add_or_update_label_schema(
                "target-schema",
                labels=[{"id": 1, "name": "brain"}],
                save=False,
            )
            target_pending_version = manager._pending_project_data_version_id
            self.assertNotEqual(target_pending_version, source_pending_version)
            manager.save_project()

            connection = sqlite3.connect(target_database)
            try:
                version_ids = {
                    row[0]
                    for row in connection.execute(
                        "SELECT data_version_id FROM integrity_data_versions"
                    ).fetchall()
                }
            finally:
                connection.close()
            self.assertIn(target_pending_version, version_ids)
            self.assertNotIn(source_pending_version, version_ids)
            self.assertEqual(
                manager.project_data["project_data_version_id"],
                target_pending_version,
            )

    def test_failed_create_restores_complete_manager_runtime_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            manager.create_project("existing", root / "existing")
            manager.create_specimen_scaffold("specimen")
            before = copy.deepcopy(manager.__dict__)

            def fail_after_mutation(*_args, **_kwargs):
                manager.current_project_path = "partial-project"
                manager.current_database_path = "partial-database"
                manager.project_data = {"name": "partial"}
                raise RuntimeError("injected create failure")

            with patch.object(manager, "_create_sqlite_project_storage", side_effect=fail_after_mutation):
                with self.assertRaisesRegex(RuntimeError, "injected create failure"):
                    manager.create_project("failed", root / "failed")

            self.assertEqual(manager.__dict__, before)

    def test_manifest_write_then_raise_removes_published_project_entry(self):
        from AntSleap.core import tif_project as tif_project_module

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            manager.create_project("existing", root / "existing")
            before = copy.deepcopy(manager.__dict__)
            failed_root = root / "failed"
            manifest_path, database_path = manager._default_sqlite_paths_for_new_project(failed_root)
            original_write = tif_project_module.write_project_manifest

            def write_then_raise(*args, **kwargs):
                original_write(*args, **kwargs)
                raise RuntimeError("injected post-publish manifest failure")

            with patch.object(tif_project_module, "write_project_manifest", side_effect=write_then_raise):
                with self.assertRaisesRegex(RuntimeError, "post-publish manifest failure"):
                    manager.create_project("failed", failed_root)

            self.assertFalse(Path(manifest_path).exists())
            self.assertFalse(Path(database_path).exists())
            self.assertFalse(Path(f"{database_path}-wal").exists())
            self.assertFalse(Path(f"{database_path}-shm").exists())
            self.assertEqual(manager.__dict__, before)

    def _part_truth_alias_fixture(self, root, project_name, *, reslice=False):
        manager = TifProjectManager()
        manager.create_project(project_name, Path(root) / project_name)
        manager.create_specimen_scaffold("specimen")
        manager.add_part("specimen", "brain", save=False)
        manager.set_part_training_metadata(
            "specimen", "brain", opened_for_review=True, save=False
        )
        if reslice:
            manager.add_part_reslice(
                "specimen",
                "brain",
                {"reslice_id": "axis-1", "status": "exported"},
                save=False,
            )
            labels = manager.get_part_reslice(
                "specimen", "brain", "axis-1"
            )["labels"]
            prefix = "specimens/specimen/parts/brain/reslices/axis-1/labels"
        else:
            labels = manager.get_part("specimen", "brain")["labels"]
            prefix = "specimens/specimen/parts/brain/labels"
        labels["editable_ai_result"] = {
            "path": f"{prefix}/editable_ai_result.ome.zarr",
            "role": "editable_ai_result",
            "status": "pending_review",
        }
        labels["manual_truth"] = {
            "path": f"{prefix}/manual_truth.ome.zarr",
            "role": "manual_truth",
            "status": "available",
        }
        return manager, labels

    def test_new_volume_registration_does_not_assume_micrometers(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = TifProjectManager()
            manager.create_project("unknown_scale", Path(tmp) / "unknown_scale")
            manager.create_specimen_scaffold("specimen")

            record = manager.register_working_volume(
                "specimen",
                "specimens/specimen/working/not_written.ome.zarr",
                [2, 3, 4],
                "uint8",
                save=False,
            )

            self.assertEqual(record["spacing_unit"], "unknown")
            self.assertFalse(record["scale_verified"])

    def test_part_delete_save_failure_restores_record_roi_and_storage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_root = root / "part_delete_rollback"
            manager = TifProjectManager()
            manifest_path = manager.create_project("part_delete_rollback", project_root)
            manager.create_specimen_scaffold("specimen")
            image_rel = "specimens/specimen/working/image.ome.zarr"
            image_meta = write_volume_sidecar(
                project_root / image_rel,
                np.arange(3 * 4 * 5, dtype=np.uint8).reshape((3, 4, 5)),
                role="working_image",
            )
            manager.register_working_volume(
                "specimen",
                image_rel,
                image_meta["shape_zyx"],
                image_meta["dtype"],
            )
            crop_volume_to_part(manager, "specimen", "head", [[0, 2], [0, 3], [0, 4]])
            manager.add_part_roi(
                "specimen",
                "head-roi",
                bbox_zyx=[[0, 2], [0, 3], [0, 4]],
                status="part_created",
                linked_part_id="head",
            )
            specimen_before = copy.deepcopy(manager.get_specimen("specimen"))
            part_root = Path(manager.to_absolute(manager.part_dir("specimen", "head")))

            with patch.object(manager, "save_project", side_effect=RuntimeError("sqlite write failed")):
                with self.assertRaisesRegex(RuntimeError, "sqlite write failed"):
                    manager.discard_part(
                        "specimen",
                        "head",
                        remove_storage=True,
                        save=True,
                        unlink_linked_rois=True,
                    )

            self.assertEqual(manager.get_specimen("specimen"), specimen_before)
            self.assertTrue(part_root.exists())
            self.assertFalse(any("delete_pending" in path.name for path in part_root.parent.iterdir()))

            reloaded = TifProjectManager()
            reloaded.load_project(manifest_path)
            self.assertIsNotNone(reloaded.get_part("specimen", "head", default=None))
            roi = reloaded.get_part_roi("specimen", "head-roi")
            self.assertEqual(roi["linked_part_id"], "head")
            self.assertEqual(roi["status"], "part_created")

    def test_specimen_discard_save_failure_restores_record_and_storage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            manifest_path = manager.create_project("specimen_discard_rollback", root / "specimen_discard_rollback")
            manager.create_specimen_scaffold("specimen")
            specimen_root = Path(manager.to_absolute(manager.specimen_dir("specimen")))

            with patch.object(manager, "save_project", side_effect=RuntimeError("sqlite write failed")):
                with self.assertRaisesRegex(RuntimeError, "sqlite write failed"):
                    manager.discard_specimen_scaffold("specimen", save=True)

            self.assertIsNotNone(manager.get_specimen("specimen", default=None))
            self.assertTrue(specimen_root.exists())
            self.assertFalse(any("delete_pending" in path.name for path in specimen_root.parent.iterdir()))

            reloaded = TifProjectManager()
            reloaded.load_project(manifest_path)
            self.assertIsNotNone(reloaded.get_specimen("specimen", default=None))

    def test_sidecar_role_update_failure_preserves_existing_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.ome.zarr"
            target = root / "target.ome.zarr"
            source_array = np.full((2, 3, 4), 9, dtype=np.uint16)
            target_array = np.full((2, 3, 4), 3, dtype=np.uint16)
            write_volume_sidecar(source, source_array, role="editable_ai_result")
            write_volume_sidecar(target, target_array, role="manual_truth")

            with patch("AntSleap.core.tif_volume_io._write_volume_metadata", side_effect=RuntimeError("metadata write failed")):
                with self.assertRaisesRegex(RuntimeError, "metadata write failed"):
                    copy_volume_sidecar(source, target, role="manual_truth")

            np.testing.assert_array_equal(load_volume_sidecar(target), target_array)
            self.assertEqual(read_volume_metadata(target)["role"], "manual_truth")
            self.assertFalse(any(path.name.startswith(".tmp_sidecar_copy_") for path in root.iterdir()))

    def test_volume_sidecar_copy_entrypoints_enforce_platform_path_identity(self):
        for entrypoint in ("copy", "replacement"):
            with self.subTest(entrypoint=entrypoint), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                source = root / "source.ome.zarr"
                target = root / "target.ome.zarr"
                source_array = np.full((2, 3, 4), 9, dtype=np.uint16)
                target_array = np.full((2, 3, 4), 3, dtype=np.uint16)
                write_volume_sidecar(source, source_array, role="editable_ai_result")
                write_volume_sidecar(target, target_array, role="manual_truth")

                with patch(
                    "AntSleap.core.tif_volume_io.paths_refer_to_same_file",
                    return_value=True,
                ):
                    with self.assertRaisesRegex(ValueError, "source_target_sidecar_same"):
                        if entrypoint == "copy":
                            copy_volume_sidecar(source, target, role="manual_truth")
                        else:
                            begin_volume_sidecar_replacement(
                                source, target, role="manual_truth"
                            )

                np.testing.assert_array_equal(load_volume_sidecar(source), source_array)
                np.testing.assert_array_equal(load_volume_sidecar(target), target_array)
                self.assertFalse(
                    any(
                        marker in path.name
                        for path in root.iterdir()
                        for marker in (".pending_", ".rollback_", ".tmp_sidecar_copy_")
                    )
                )

    def test_volume_sidecar_copy_entrypoints_reject_ancestor_and_descendant_overlap(self):
        for entrypoint in ("copy", "replacement"):
            for target_kind in ("ancestor", "descendant"):
                with self.subTest(entrypoint=entrypoint, target_kind=target_kind), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    labels_root = root / "labels"
                    source = labels_root / "model_draft" / "prediction.ome.zarr"
                    manual = labels_root / "manual_truth.ome.zarr"
                    source_array = np.full((2, 3, 4), 9, dtype=np.uint16)
                    manual_array = np.full((2, 3, 4), 3, dtype=np.uint16)
                    write_volume_sidecar(source, source_array, role="model_draft")
                    write_volume_sidecar(manual, manual_array, role="manual_truth")
                    target = labels_root if target_kind == "ancestor" else source / "nested.ome.zarr"

                    with self.assertRaisesRegex(ValueError, "source_target_sidecar_overlap"):
                        if entrypoint == "copy":
                            copy_volume_sidecar(source, target, role="working_edit")
                        else:
                            begin_volume_sidecar_replacement(source, target, role="working_edit")

                    np.testing.assert_array_equal(load_volume_sidecar(source), source_array)
                    np.testing.assert_array_equal(load_volume_sidecar(manual), manual_array)
                    self.assertFalse(
                        any(
                            marker in path.name
                            for path in root.rglob("*")
                            for marker in (".pending_", ".rollback_", ".tmp_sidecar_copy_")
                        )
                    )

    def test_batch_truth_save_failure_restores_all_existing_manual_truth_sidecars(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "truth_batch_rollback"
            manager = TifProjectManager()
            manager.create_project("truth_batch_rollback", project_root)
            manager.create_specimen_scaffold("specimen")
            manager.add_or_update_label_schema(
                "regions",
                labels=[
                    {"id": 2, "name": "region_2"},
                    {"id": 3, "name": "region_3"},
                ],
                save=False,
            )
            expected_manual = {}
            refs = []
            for index, part_id in enumerate(("head", "thorax"), start=2):
                image_rel = f"specimens/specimen/parts/{part_id}/image.ome.zarr"
                manual_rel = f"specimens/specimen/parts/{part_id}/labels/manual_truth.ome.zarr"
                edit_rel = f"specimens/specimen/parts/{part_id}/labels/editable_ai_result.ome.zarr"
                image_meta = write_volume_sidecar(
                    project_root / image_rel,
                    np.zeros((2, 3, 4), dtype=np.uint8),
                    role="part_image",
                )
                manual_array = np.full((2, 3, 4), index + 5, dtype=np.uint16)
                edit_array = np.full((2, 3, 4), index, dtype=np.uint16)
                manual_meta = write_volume_sidecar(project_root / manual_rel, manual_array, role="manual_truth")
                edit_meta = write_volume_sidecar(project_root / edit_rel, edit_array, role="editable_ai_result")
                manager.add_part(
                    "specimen",
                    part_id,
                    image={"path": image_rel, **image_meta},
                    save=False,
                )
                manager.register_part_label_volume(
                    "specimen",
                    part_id,
                    "manual_truth",
                    manual_rel,
                    manual_meta["shape_zyx"],
                    manual_meta["dtype"],
                    explicit_review=True,
                    operation="truth_promotion",
                    audit_metadata={"review_action": "test_existing_truth"},
                    save=False,
                )
                manager.register_part_label_volume(
                    "specimen",
                    part_id,
                    "editable_ai_result",
                    edit_rel,
                    edit_meta["shape_zyx"],
                    edit_meta["dtype"],
                    status="pending_review",
                    save=False,
                )
                manager.set_part_training_metadata(
                    "specimen",
                    part_id,
                    label_schema_id="regions",
                    opened_for_review=True,
                    save=False,
                )
                expected_manual[part_id] = manual_array
                refs.append({"specimen_id": "specimen", "part_id": part_id})
            manager.save_project()
            project_snapshot = copy.deepcopy(manager.project_data)

            with patch.object(manager, "save_project", side_effect=RuntimeError("sqlite write failed")):
                with self.assertRaisesRegex(RuntimeError, "sqlite write failed"):
                    manager.promote_reviewed_part_results_to_manual_truth(
                        refs,
                        require_opened_for_review=True,
                        save=True,
                    )

            self.assertEqual(manager.project_data, project_snapshot)
            for part_id, expected in expected_manual.items():
                manual_path = project_root / manager.get_part("specimen", part_id)["labels"]["manual_truth"]["path"]
                np.testing.assert_array_equal(load_volume_sidecar(manual_path), expected)
                self.assertFalse(
                    any(
                        marker in path.name
                        for path in manual_path.parent.iterdir()
                        for marker in (".pending_", ".rollback_")
                    )
                )

    def test_align_editable_axis_to_three_point_reference_plane(self):
        editable_axis = {
            "axis_id": "local_output_z_axis",
            "start_zyx": [1.0, 4.0, 4.0],
            "end_zyx": [5.0, 4.0, 4.0],
        }
        roll_reference = {
            "point_a": {"role": "roll_reference_a", "zyx": [3.0, 1.0, 1.0]},
            "point_b": {"role": "roll_reference_b", "zyx": [3.0, 6.0, 1.0]},
            "point_c": {"role": "reference_plane_c", "zyx": [5.0, 1.0, 6.0]},
        }

        aligned, plane = align_editable_axis_to_reference_plane(
            editable_axis,
            roll_reference,
            spacing_zyx=[2.0, 1.0, 1.0],
            shape_zyx=[7, 8, 8],
        )

        start = np.asarray(aligned["start_zyx"], dtype=np.float64)
        end = np.asarray(aligned["end_zyx"], dtype=np.float64)
        axis_world = (end - start) * np.asarray([2.0, 1.0, 1.0], dtype=np.float64)
        axis_world /= np.linalg.norm(axis_world)
        normal_world = np.asarray(plane["normal_world_zyx"], dtype=np.float64)

        self.assertEqual(aligned["derived_from"], "three_point_reference_plane")
        self.assertIn("reference_plane", aligned)
        self.assertAlmostEqual(abs(float(np.dot(axis_world, normal_world))), 1.0, places=5)

    def test_tif_project_saves_reopens_and_tracks_train_ready_specimen(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "brain_project"
            manager = TifProjectManager()
            project_json = manager.create_project("brain_project", project_root)
            specimen = manager.create_specimen_scaffold(
                "01-0101-02",
                modality="confocal",
                material_map={
                    "source": "manual",
                    "materials": [
                        {"id": 0, "name": "background", "display_name": "Background", "trainable": False},
                        {"id": 1, "name": "LO_L", "display_name": "LO_L", "color": "#ff4b4b", "trainable": True},
                    ],
                },
            )

            image_rel = "specimens/01-0101-02/working/image.ome.zarr"
            manual_rel = "specimens/01-0101-02/labels/manual_truth.ome.zarr"
            image_meta = write_volume_sidecar(
                project_root / image_rel,
                np.zeros((3, 4, 5), dtype=np.uint8),
                role="working_image",
                source_format="unit_test",
            )
            manual_meta = write_volume_sidecar(
                project_root / manual_rel,
                np.ones((3, 4, 5), dtype=np.uint16),
                role="manual_truth",
                source_format="unit_test",
            )

            manager.register_working_volume(
                "01-0101-02",
                image_rel,
                image_meta["shape_zyx"],
                image_meta["dtype"],
                fmt=VOLUME_SIDECAR_FORMAT,
                save=False,
            )
            manager.register_label_volume(
                "01-0101-02",
                "manual_truth",
                manual_rel,
                manual_meta["shape_zyx"],
                manual_meta["dtype"],
                status="reviewed",
                fmt=VOLUME_SIDECAR_FORMAT,
                save=False,
            )
            manager.set_review_status("01-0101-02", "train_ready", train_ready=True)

            reloaded = TifProjectManager()
            reloaded.load_project(project_json)
            loaded_specimen = reloaded.get_specimen("01-0101-02")
            readiness = reloaded.evaluate_train_ready("01-0101-02")

            self.assertEqual(reloaded.project_data["schema_version"], TIF_PROJECT_SCHEMA_VERSION)
            self.assertEqual(reloaded.project_data["project_type"], TIF_PROJECT_TYPE)
            self.assertEqual(loaded_specimen["modality"], "confocal")
            self.assertEqual(loaded_specimen["working_volume"]["shape_zyx"], [3, 4, 5])
            self.assertTrue(readiness["train_ready"])
            self.assertEqual(readiness["reasons"], [])
            self.assertEqual(len(reloaded.list_train_ready_specimens()), 1)
            self.assertTrue((project_root / specimen["material_map"]).exists())

    def test_train_ready_reports_missing_truth_and_material_risks(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "empty_tif_project"
            manager = TifProjectManager()
            manager.create_project("empty_tif_project", project_root)
            manager.create_specimen_scaffold(
                "01-0101-03",
                material_map={
                    "materials": [
                        {"id": 0, "name": "background", "display_name": "Background", "trainable": False}
                    ]
                },
            )

            image_rel = "specimens/01-0101-03/working/image.ome.zarr"
            image_meta = write_volume_sidecar(project_root / image_rel, np.zeros((2, 2, 2), dtype=np.uint8), role="working_image")
            manager.register_working_volume(
                "01-0101-03",
                image_rel,
                image_meta["shape_zyx"],
                image_meta["dtype"],
                save=False,
            )
            manager.set_review_status("01-0101-03", "train_ready", train_ready=True)

            readiness = manager.evaluate_train_ready("01-0101-03")

            self.assertFalse(readiness["train_ready"])
            self.assertEqual(readiness["reasons"].count("manual_truth_missing"), 1)
            self.assertNotIn("image_label_shape_mismatch", readiness["reasons"])
            self.assertIn("no_trainable_material", readiness["reasons"])


    def test_train_ready_reports_shape_mismatch_only_when_truth_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "shape_mismatch_project"
            manager = TifProjectManager()
            manager.create_project("shape_mismatch_project", project_root)
            manager.create_specimen_scaffold(
                "01-0101-03b",
                material_map={
                    "materials": [
                        {"id": 0, "name": "background", "display_name": "Background", "trainable": False},
                        {"id": 1, "name": "brain", "display_name": "Brain", "trainable": True},
                    ]
                },
            )
            image_rel = "specimens/01-0101-03b/working/image.ome.zarr"
            truth_rel = "specimens/01-0101-03b/labels/manual_truth.ome.zarr"
            image_meta = write_volume_sidecar(project_root / image_rel, np.zeros((2, 2, 2), dtype=np.uint8), role="working_image")
            truth_meta = write_volume_sidecar(project_root / truth_rel, np.zeros((3, 2, 2), dtype=np.uint16), role="manual_truth")
            manager.register_working_volume("01-0101-03b", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            manager.register_label_volume("01-0101-03b", "manual_truth", truth_rel, truth_meta["shape_zyx"], truth_meta["dtype"], save=False)
            manager.set_review_status("01-0101-03b", "train_ready", train_ready=True)

            readiness = manager.evaluate_train_ready("01-0101-03b")

            self.assertIn("image_label_shape_mismatch", readiness["reasons"])
            self.assertNotIn("manual_truth_missing", readiness["reasons"])

    def test_empty_working_edit_sidecar_can_be_created_from_image_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            image_dir = Path(tmp) / "image.ome.zarr"
            edit_dir = Path(tmp) / "working_edit.ome.zarr"
            image_meta = write_volume_sidecar(image_dir, np.zeros((4, 5, 6), dtype=np.uint8), role="working_image")
            edit_meta = create_empty_label_sidecar_like(image_dir, edit_dir)

            self.assertEqual(edit_meta["shape_zyx"], image_meta["shape_zyx"])
            self.assertEqual(edit_meta["role"], "working_edit")

    def test_empty_label_sidecar_downgrades_conflicting_source_record_scale(self):
        with tempfile.TemporaryDirectory() as tmp:
            image_dir = Path(tmp) / "verified_image.ome.zarr"
            edit_dir = Path(tmp) / "working_edit.ome.zarr"
            write_volume_sidecar(
                image_dir,
                np.zeros((4, 5, 6), dtype=np.uint8),
                role="working_image",
                spacing_zyx=[2.0, 1.0, 0.5],
                spacing_unit="micrometer",
                scale_verified=True,
            )

            edit_meta = create_empty_label_sidecar_like(
                image_dir,
                edit_dir,
                source_record={
                    "spacing_zyx": [3.0, 1.0, 0.5],
                    "spacing_unit": "micrometer",
                    "scale_verified": True,
                },
            )

            self.assertEqual(edit_meta["spacing_unit"], "unknown")
            self.assertFalse(edit_meta["scale_verified"])

    def test_material_map_preserves_background_and_trainable_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = TifProjectManager()
            manager.create_project("materials", Path(tmp) / "materials")
            specimen = manager.create_specimen_scaffold(
                "01-0101-04",
                material_map={
                    "source": "manual",
                    "materials": [
                        {"id": 3, "name": "MB", "display_name": "Mushroom body", "trainable": True}
                    ],
                },
            )

            material_map = read_material_map(Path(manager.project_dir) / specimen["material_map"])
            ids = [item["id"] for item in material_map["materials"]]

            self.assertEqual(ids, [0, 3])
            self.assertFalse(material_map["materials"][0]["trainable"])
            self.assertTrue(material_map["materials"][1]["trainable"])

    def test_corrupt_material_map_does_not_erase_last_valid_sqlite_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = TifProjectManager()
            manager.create_project("material_map_rollback", root / "material_map_rollback")
            specimen = manager.create_specimen_scaffold(
                "specimen",
                material_map={
                    "source": "manual",
                    "materials": [
                        {"id": 0, "name": "background", "trainable": False},
                        {"id": 2, "name": "brain", "trainable": True},
                    ],
                },
            )
            material_path = Path(manager.to_absolute(specimen["material_map"]))
            connection = sqlite3.connect(manager.current_database_path)
            try:
                materials_before = connection.execute("SELECT materials_json FROM material_maps").fetchone()[0]
            finally:
                connection.close()

            material_path.write_text("{not valid json", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "tif_material_map_read_failed"):
                manager.save_project()

            connection = sqlite3.connect(manager.current_database_path)
            try:
                materials_after = connection.execute("SELECT materials_json FROM material_maps").fetchone()[0]
            finally:
                connection.close()
            self.assertEqual(materials_after, materials_before)

    def test_working_edit_promotion_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "promotion"
            manager = TifProjectManager()
            manager.create_project("promotion", project_root)
            manager.create_specimen_scaffold(
                "01-0101-09",
                material_map={
                    "materials": [
                        {"id": 0, "name": "background", "display_name": "Background", "trainable": False},
                        {"id": 2, "name": "LO_L", "display_name": "LO_L", "trainable": True},
                    ]
                },
            )
            image_rel = "specimens/01-0101-09/working/image.ome.zarr"
            edit_rel = "specimens/01-0101-09/labels/working_edit.ome.zarr"
            manual_rel = "specimens/01-0101-09/labels/manual_truth.ome.zarr"
            image_meta = write_volume_sidecar(project_root / image_rel, np.zeros((2, 3, 4), dtype=np.uint8), role="working_image")
            edit_array = np.zeros((2, 3, 4), dtype=np.uint16)
            edit_array[0, 1, 1] = 2
            edit_meta = write_volume_sidecar(project_root / edit_rel, edit_array, role="working_edit")
            manager.register_working_volume("01-0101-09", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            manager.register_label_volume("01-0101-09", "working_edit", edit_rel, edit_meta["shape_zyx"], edit_meta["dtype"], save=False)
            manager.save_project()

            self.assertFalse(manager.evaluate_train_ready("01-0101-09")["train_ready"])
            manager.promote_working_edit_to_manual_truth("01-0101-09")

            specimen = manager.get_specimen("01-0101-09")
            self.assertEqual(specimen["labels"]["manual_truth"]["path"], manual_rel)
            self.assertTrue(manager.evaluate_train_ready("01-0101-09")["train_ready"])
            np.testing.assert_array_equal(load_volume_sidecar(project_root / manual_rel), edit_array)

    def test_non_ready_status_clears_train_ready_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "status_sync"
            manager = TifProjectManager()
            manager.create_project("status_sync", project_root)
            manager.create_specimen_scaffold(
                "01-0101-15",
                material_map={
                    "materials": [
                        {"id": 0, "name": "background", "display_name": "Background", "trainable": False},
                        {"id": 2, "name": "brain", "display_name": "Brain", "trainable": True},
                    ]
                },
            )
            image_rel = "specimens/01-0101-15/working/image.ome.zarr"
            manual_rel = "specimens/01-0101-15/labels/manual_truth.ome.zarr"
            image_meta = write_volume_sidecar(project_root / image_rel, np.zeros((2, 3, 4), dtype=np.uint8), role="working_image")
            manual_meta = write_volume_sidecar(project_root / manual_rel, np.ones((2, 3, 4), dtype=np.uint16), role="manual_truth")
            manager.register_working_volume("01-0101-15", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            manager.register_label_volume(
                "01-0101-15",
                "manual_truth",
                manual_rel,
                manual_meta["shape_zyx"],
                manual_meta["dtype"],
                status="reviewed",
                save=False,
            )

            manager.set_review_status("01-0101-15", "train_ready")
            self.assertTrue(manager.evaluate_train_ready("01-0101-15")["train_ready"])
            manager.set_review_status("01-0101-15", "in_progress")

            specimen = manager.get_specimen("01-0101-15")
            self.assertFalse(specimen["train_ready"])
            readiness = manager.evaluate_train_ready("01-0101-15")
            self.assertFalse(readiness["train_ready"])
            self.assertIn("specimen_not_marked_train_ready", readiness["reasons"])

    def test_copy_label_layer_refuses_same_source_and_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "same_path"
            manager = TifProjectManager()
            manager.create_project("same_path", project_root)
            manager.create_specimen_scaffold(
                "01-0101-16",
                material_map={
                    "materials": [
                        {"id": 0, "name": "background", "display_name": "Background", "trainable": False},
                        {"id": 3, "name": "brain", "display_name": "Brain", "trainable": True},
                    ]
                },
            )
            shared_rel = "specimens/01-0101-16/labels/shared.ome.zarr"
            meta = write_volume_sidecar(project_root / shared_rel, np.ones((2, 3, 4), dtype=np.uint16), role="manual_truth")
            manager.register_label_volume("01-0101-16", "manual_truth", shared_rel, meta["shape_zyx"], meta["dtype"], save=False)
            manager.register_label_volume("01-0101-16", "working_edit", shared_rel, meta["shape_zyx"], meta["dtype"], save=False)

            with self.assertRaisesRegex(ValueError, "source_target_label_same"):
                manager.copy_label_layer_to_working_edit("01-0101-16", source_role="manual_truth")
            self.assertTrue((project_root / shared_rel / "array.npy").exists())

            with self.assertRaisesRegex(ValueError, "working_edit_manual_truth_same_path"):
                manager.promote_working_edit_to_manual_truth("01-0101-16")
            self.assertTrue((project_root / shared_rel / "array.npy").exists())

    def test_working_edit_promotion_enforces_platform_reported_path_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._working_edit_copy_fixture(tmp, "promotion_mock_alias")

            with patch(
                "AntSleap.core.tif_project.paths_refer_to_same_file",
                return_value=True,
            ):
                with self.assertRaisesRegex(
                    ValueError, "working_edit_manual_truth_same_path"
                ):
                    fixture["manager"].promote_working_edit_to_manual_truth(
                        "specimen", save=True
                    )

            np.testing.assert_array_equal(
                load_volume_sidecar(fixture["working_path"]), fixture["working_array"]
            )
            np.testing.assert_array_equal(
                load_volume_sidecar(fixture["manual_path"]), fixture["manual_array"]
            )

    def test_full_truth_promotion_rejects_ancestor_target_without_touching_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._working_edit_copy_fixture(tmp, "promotion_overlap")
            labels_root = fixture["working_path"].parent
            fixture["manager"].get_specimen("specimen")["labels"]["manual_truth"]["path"] = (
                fixture["manager"].to_relative(labels_root)
            )

            with self.assertRaisesRegex(ValueError, "working_edit_manual_truth_path_overlap"):
                fixture["manager"].promote_working_edit_to_manual_truth("specimen", save=True)

            np.testing.assert_array_equal(
                load_volume_sidecar(fixture["working_path"]), fixture["working_array"]
            )
            np.testing.assert_array_equal(
                load_volume_sidecar(fixture["manual_path"]), fixture["manual_array"]
            )
            np.testing.assert_array_equal(
                load_volume_sidecar(fixture["draft_path"]), fixture["draft_array"]
            )

    def test_part_truth_promotions_reject_ancestor_target_without_touching_labels(self):
        for reslice in (False, True):
            with self.subTest(reslice=reslice), tempfile.TemporaryDirectory() as tmp:
                manager, labels = self._part_truth_alias_fixture(
                    tmp, f"part_truth_overlap_{reslice}", reslice=reslice
                )
                editable_path = Path(manager.to_absolute(labels["editable_ai_result"]["path"]))
                labels_root = editable_path.parent
                manual_path = labels_root / "manual_truth.ome.zarr"
                editable_array = np.full((2, 3, 4), 7, dtype=np.uint16)
                manual_array = np.full((2, 3, 4), 2, dtype=np.uint16)
                write_volume_sidecar(editable_path, editable_array, role="editable_ai_result")
                write_volume_sidecar(manual_path, manual_array, role="manual_truth")
                labels["manual_truth"]["path"] = manager.to_relative(labels_root)

                expected_error = (
                    "part_reslice_manual_truth_source_target_path_overlap"
                    if reslice
                    else "part_manual_truth_source_target_path_overlap"
                )
                with self.assertRaisesRegex(ValueError, expected_error):
                    if reslice:
                        manager.promote_part_reslice_editable_result_to_manual_truth(
                            "specimen", "brain", "axis-1", save=False
                        )
                    else:
                        manager.promote_part_editable_result_to_manual_truth(
                            "specimen", "brain", save=False
                        )

                np.testing.assert_array_equal(load_volume_sidecar(editable_path), editable_array)
                np.testing.assert_array_equal(load_volume_sidecar(manual_path), manual_array)

    def test_part_truth_promotion_rejects_editable_platform_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager, labels = self._part_truth_alias_fixture(
                tmp, "part_truth_mock_alias"
            )

            with patch(
                "AntSleap.core.tif_project.paths_refer_to_same_file",
                return_value=True,
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "part_editable_ai_result_manual_truth_same_path",
                ):
                    manager.promote_part_editable_result_to_manual_truth(
                        "specimen", "brain", save=False
                    )

            self.assertEqual(labels["manual_truth"]["status"], "available")

    def test_part_reslice_truth_promotion_rejects_editable_platform_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager, labels = self._part_truth_alias_fixture(
                tmp, "reslice_truth_mock_alias", reslice=True
            )

            with patch(
                "AntSleap.core.tif_project.paths_refer_to_same_file",
                return_value=True,
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "part_reslice_editable_ai_result_manual_truth_same_path",
                ):
                    manager.promote_part_reslice_editable_result_to_manual_truth(
                        "specimen", "brain", "axis-1", save=False
                    )

            self.assertEqual(labels["manual_truth"]["status"], "available")

    def test_part_manual_truth_same_physical_path_remains_existing_truth(self):
        for reslice in (False, True):
            with self.subTest(reslice=reslice), tempfile.TemporaryDirectory() as tmp:
                manager, labels = self._part_truth_alias_fixture(
                    tmp, f"existing_truth_{reslice}", reslice=reslice
                )

                with patch(
                    "AntSleap.core.tif_project.paths_refer_to_same_file",
                    return_value=True,
                ):
                    if reslice:
                        result = manager.promote_part_reslice_editable_result_to_manual_truth(
                            "specimen",
                            "brain",
                            "axis-1",
                            source_role="manual_truth",
                            save=False,
                        )
                    else:
                        result = manager.promote_part_editable_result_to_manual_truth(
                            "specimen",
                            "brain",
                            source_role="manual_truth",
                            save=False,
                        )

                self.assertIs(result, labels["manual_truth"])
                self.assertEqual(labels["manual_truth"]["status"], "reviewed")

    def test_copy_model_draft_to_working_edit_commits_volume_and_sqlite_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._working_edit_copy_fixture(tmp, "draft_copy_success")
            manager = fixture["manager"]
            data_version_before = manager.project_data["project_data_version_id"]

            copied = manager.copy_label_layer_to_working_edit(
                "specimen", source_role="model_draft", save=True
            )

            self.assertEqual(copied["status"], "copied_from_model_draft")
            self.assertEqual(manager.get_specimen("specimen")["review_status"], "in_progress")
            self.assertFalse(manager.get_specimen("specimen")["train_ready"])
            self.assertEqual(
                manager.project_data["project_data_version_id"], data_version_before
            )
            self.assertEqual(manager._pending_project_data_version_id, "")
            np.testing.assert_array_equal(
                load_volume_sidecar(fixture["working_path"]), fixture["draft_array"]
            )
            np.testing.assert_array_equal(
                load_volume_sidecar(fixture["manual_path"]), fixture["manual_array"]
            )

            reloaded = TifProjectManager()
            reloaded.load_project(fixture["manifest_path"])
            reloaded_specimen = reloaded.get_specimen("specimen")
            self.assertEqual(
                reloaded_specimen["labels"]["working_edit"]["status"],
                "copied_from_model_draft",
            )
            self.assertEqual(reloaded_specimen["review_status"], "in_progress")
            self.assertFalse(reloaded_specimen["train_ready"])

    def test_single_volume_commit_cleanup_error_is_recorded_without_failing_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._working_edit_copy_fixture(tmp, "draft_copy_cleanup_warning")
            manager = fixture["manager"]

            with self.assertLogs("AntSleap.core.tif_project", level="WARNING") as logs, patch(
                "AntSleap.core.tif_volume_io.VolumeSidecarReplacement.commit",
                return_value="rollback directory is locked",
            ):
                copied = manager.copy_label_layer_to_working_edit(
                    "specimen", source_role="model_draft", save=True
                )

            self.assertEqual(copied["status"], "copied_from_model_draft")
            np.testing.assert_array_equal(
                load_volume_sidecar(fixture["working_path"]), fixture["draft_array"]
            )
            self.assertEqual(len(manager.volume_cleanup_warnings), 1)
            warning = manager.volume_cleanup_warnings[0]
            self.assertEqual(warning["operation"], "volume_replacement_commit")
            self.assertEqual(warning["role"], "working_edit")
            self.assertIn("locked", warning["error"])
            self.assertTrue(warning["rollback_path"])
            self.assertEqual(warning["data_commit_status"], "committed")
            self.assertEqual(warning["cleanup_scope"], "rollback_backup_only")
            self.assertIn("backup cleanup was incomplete", logs.output[0])

            warning_path = Path(manager.volume_cleanup_warning_path)
            self.assertTrue(warning_path.is_file())
            persisted = json.loads(warning_path.read_text(encoding="utf-8"))
            self.assertEqual(
                persisted["schema_version"],
                TIF_VOLUME_CLEANUP_WARNING_SCHEMA_VERSION,
            )
            self.assertEqual(
                persisted["max_records"], TIF_VOLUME_CLEANUP_WARNING_LIMIT
            )
            self.assertLess(warning_path.stat().st_size, TIF_VOLUME_CLEANUP_WARNING_MAX_BYTES)
            persisted_warning = persisted["warnings"][0]
            self.assertEqual(
                persisted_warning["operation"], "volume_replacement_commit"
            )
            self.assertEqual(
                persisted_warning["data_commit_status"], "committed"
            )
            self.assertIn("locked", persisted_warning["error"])
            self.assertTrue(persisted_warning["rollback_path"])
            self.assertFalse(os.path.isabs(persisted_warning["rollback_path"]))

            reloaded = TifProjectManager()
            reloaded.load_project(fixture["manifest_path"])
            self.assertEqual(len(reloaded.volume_cleanup_warnings), 1)
            reloaded_warning = reloaded.volume_cleanup_warnings[0]
            self.assertEqual(
                reloaded_warning["operation"], "volume_replacement_commit"
            )
            self.assertEqual(reloaded_warning["error"], persisted_warning["error"])
            self.assertEqual(
                reloaded_warning["rollback_path"],
                persisted_warning["rollback_path"],
            )

    def test_volume_cleanup_warning_sidecar_is_bounded_and_atomic_write_failure_is_nonfatal(self):
        class CleanupReplacement:
            metadata = {"role": "working_edit"}
            target = "specimens/specimen/labels/working_edit.ome.zarr"
            rollback_path = (
                "specimens/specimen/labels/working_edit.ome.zarr.rollback_locked"
            )

            def commit(self):
                return "rollback directory is locked"

        with tempfile.TemporaryDirectory() as tmp:
            manager = TifProjectManager()
            manager.create_project("cleanup-bound", Path(tmp) / "cleanup-bound")
            manager.volume_cleanup_warnings = [
                manager._normalize_volume_cleanup_warning(
                    {
                        "operation": f"previous-{index}",
                        "rollback_path": f"rollback-{index}",
                        "error": "locked",
                    }
                )
                for index in range(TIF_VOLUME_CLEANUP_WARNING_LIMIT)
            ]

            with patch(
                "AntSleap.core.tif_project.atomic_write_json_in_root",
                side_effect=PermissionError("maintenance warning file is locked"),
            ), patch(
                "AntSleap.app_runtime.runtime_log_event",
                side_effect=RuntimeError("runtime log unavailable"),
            ), self.assertLogs(
                "AntSleap.core.tif_project", level="WARNING"
            ) as logs:
                cleanup_error = manager._commit_volume_replacement_cleanup(
                    CleanupReplacement(),
                    operation="volume_replacement_commit",
                    role="working_edit",
                )

            self.assertEqual(cleanup_error, "rollback directory is locked")
            self.assertEqual(
                len(manager.volume_cleanup_warnings),
                TIF_VOLUME_CLEANUP_WARNING_LIMIT,
            )
            self.assertEqual(
                manager.volume_cleanup_warnings[0]["operation"], "previous-1"
            )
            self.assertEqual(
                manager.volume_cleanup_warnings[-1]["operation"],
                "volume_replacement_commit",
            )
            self.assertTrue(
                any("Could not persist" in message for message in logs.output)
            )

    def test_volume_cleanup_warning_atomic_replace_failure_preserves_previous_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = TifProjectManager()
            manager.create_project(
                "cleanup-atomic-preserve", Path(tmp) / "cleanup-atomic-preserve"
            )
            manager.volume_cleanup_warnings = [
                manager._normalize_volume_cleanup_warning(
                    {
                        "warning_id": "cleanup_warning_original",
                        "operation": "original",
                    }
                )
            ]
            manager._volume_cleanup_warning_dirty_ids.update(
                warning["warning_id"]
                for warning in manager.volume_cleanup_warnings
            )
            warning_path = Path(manager.volume_cleanup_warning_path)
            warning_path.parent.mkdir(parents=True, exist_ok=True)
            fixed_tmp_marker = Path(f"{warning_path}.tmp")
            fixed_tmp_marker.write_text("must remain untouched", encoding="utf-8")
            self.assertEqual(manager._persist_volume_cleanup_warnings(), "")
            original_bytes = warning_path.read_bytes()
            self.assertEqual(
                fixed_tmp_marker.read_text(encoding="utf-8"),
                "must remain untouched",
            )
            manager.volume_cleanup_warnings.append(
                manager._normalize_volume_cleanup_warning(
                    {
                        "warning_id": "cleanup_warning_new",
                        "operation": "new",
                    }
                )
            )
            manager._volume_cleanup_warning_dirty_ids.add(
                manager.volume_cleanup_warnings[-1]["warning_id"]
            )

            directory_fd_guards = safe_io._directory_fd_guards_available()
            replace_function = (
                "rename"
                if directory_fd_guards
                else "replace"
            )
            with patch.object(
                safe_io,
                "_directory_fd_guards_available",
                return_value=directory_fd_guards,
            ), patch.object(
                safe_io.os,
                replace_function,
                side_effect=PermissionError("simulated replace failure"),
            ):
                persistence_error = manager._persist_volume_cleanup_warnings()

            self.assertIn("simulated replace failure", persistence_error)
            self.assertEqual(warning_path.read_bytes(), original_bytes)
            self.assertEqual(
                list(warning_path.parent.glob(f".{warning_path.name}.tmp-*")), []
            )

    def test_volume_cleanup_warning_sidecar_requires_matching_nonempty_project_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "cleanup-project-identity"
            manager = TifProjectManager()
            manifest_path = manager.create_project(
                "cleanup-project-identity", project_root
            )
            warning_path = Path(manager.volume_cleanup_warning_path)
            valid_payload = {
                "schema_version": TIF_VOLUME_CLEANUP_WARNING_SCHEMA_VERSION,
                "record_type": "tif_volume_cleanup_maintenance_warnings",
                "project_id": manager.project_data["project_id"],
                "warnings": [{"operation": "volume_replacement_commit"}],
            }

            rejected_project_ids = {
                "missing": None,
                "different": "project_tif_different",
                "whitespace_variant": (
                    f" {manager.project_data['project_id']} "
                ),
            }
            for case, project_id in rejected_project_ids.items():
                with self.subTest(case=case):
                    payload = copy.deepcopy(valid_payload)
                    if project_id is None:
                        payload.pop("project_id")
                    else:
                        payload["project_id"] = project_id
                    warning_path.parent.mkdir(parents=True, exist_ok=True)
                    warning_path.write_text(
                        json.dumps(payload), encoding="utf-8"
                    )

                    reloaded = TifProjectManager()
                    with self.assertLogs(
                        "AntSleap.core.tif_project", level="WARNING"
                    ) as logs:
                        loaded = reloaded.load_project(manifest_path)

                    self.assertEqual(
                        loaded["project_id"], manager.project_data["project_id"]
                    )
                    self.assertEqual(reloaded.volume_cleanup_warnings, [])
                    self.assertTrue(
                        any(
                            "maintenance_warning_" in message
                            for message in logs.output
                        )
                    )

            warning_path.write_text(json.dumps(valid_payload), encoding="utf-8")
            manager.project_data["project_id"] = ""
            with self.assertLogs(
                "AntSleap.core.tif_project", level="WARNING"
            ) as logs:
                loaded_warnings = manager._load_volume_cleanup_warnings()
            self.assertEqual(loaded_warnings, [])
            self.assertTrue(
                any(
                    "maintenance_warning_current_project_id_missing" in message
                    for message in logs.output
                )
            )

    def test_malformed_volume_cleanup_warning_sidecar_does_not_block_project_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "cleanup-malformed-sidecar"
            manager = TifProjectManager()
            manifest_path = manager.create_project(
                "cleanup-malformed-sidecar", project_root
            )
            warning_path = Path(manager.volume_cleanup_warning_path)
            warning_path.parent.mkdir(parents=True, exist_ok=True)
            warning_path.write_text("{not-json", encoding="utf-8")

            reloaded = TifProjectManager()
            with self.assertLogs(
                "AntSleap.core.tif_project", level="WARNING"
            ):
                loaded = reloaded.load_project(manifest_path)

            self.assertEqual(
                loaded["project_id"], manager.project_data["project_id"]
            )
            self.assertEqual(reloaded.volume_cleanup_warnings, [])

    def test_volume_cleanup_warning_reader_enforces_exact_byte_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = TifProjectManager()
            manifest_path = manager.create_project(
                "cleanup-size-boundary", Path(tmp) / "cleanup-size-boundary"
            )
            warning_path = Path(manager.volume_cleanup_warning_path)
            warning_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema_version": TIF_VOLUME_CLEANUP_WARNING_SCHEMA_VERSION,
                "record_type": "tif_volume_cleanup_maintenance_warnings",
                "project_id": manager.project_data["project_id"],
                "warnings": [
                    {
                        "warning_id": "cleanup_warning_boundary",
                        "operation": "boundary",
                    }
                ],
            }
            encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            warning_path.write_bytes(encoded)

            with patch(
                "AntSleap.core.tif_project.TIF_VOLUME_CLEANUP_WARNING_MAX_BYTES",
                len(encoded),
            ):
                reloaded = TifProjectManager()
                reloaded.load_project(manifest_path)
            self.assertEqual(len(reloaded.volume_cleanup_warnings), 1)

            warning_path.write_bytes(encoded + b" ")
            with patch(
                "AntSleap.core.tif_project.TIF_VOLUME_CLEANUP_WARNING_MAX_BYTES",
                len(encoded),
            ), self.assertLogs(
                "AntSleap.core.tif_project", level="WARNING"
            ) as logs:
                oversized = TifProjectManager()
                oversized.load_project(manifest_path)
            self.assertEqual(oversized.volume_cleanup_warnings, [])
            self.assertTrue(
                any("json_file_too_large" in message for message in logs.output)
            )

    def test_volume_cleanup_warning_reader_rejects_identity_swap_during_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = TifProjectManager()
            manifest_path = manager.create_project(
                "cleanup-open-race", Path(tmp) / "cleanup-open-race"
            )
            warning_path = Path(manager.volume_cleanup_warning_path)
            warning_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema_version": TIF_VOLUME_CLEANUP_WARNING_SCHEMA_VERSION,
                "record_type": "tif_volume_cleanup_maintenance_warnings",
                "project_id": manager.project_data["project_id"],
                "warnings": [{"operation": "before-swap"}],
            }
            warning_path.write_text(json.dumps(payload), encoding="utf-8")
            replacement_path = warning_path.with_name("replacement.json")
            replacement_path.write_text(
                json.dumps({**payload, "warnings": [{"operation": "after-swap"}]}),
                encoding="utf-8",
            )
            real_open = os.open
            swapped = {"done": False}

            def swap_before_open(path, flags, *args, **kwargs):
                if os.path.normcase(os.path.abspath(path)) == os.path.normcase(
                    os.path.abspath(warning_path)
                ) and not swapped["done"]:
                    swapped["done"] = True
                    os.replace(replacement_path, warning_path)
                return real_open(path, flags, *args, **kwargs)

            reloaded = TifProjectManager()
            with patch(
                "AntSleap.core.safe_io.os.open", side_effect=swap_before_open
            ), self.assertLogs(
                "AntSleap.core.tif_project", level="WARNING"
            ) as logs:
                reloaded.load_project(manifest_path)

            self.assertTrue(swapped["done"])
            self.assertEqual(reloaded.volume_cleanup_warnings, [])
            self.assertTrue(
                any("file_identity_changed_during_open" in message for message in logs.output)
            )

    def test_volume_cleanup_warning_sidecar_rejects_parent_directory_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_root = root / "cleanup-alias" / "project"
            external_root = root / "external-warning-target"
            external_root.mkdir(parents=True)
            manager = TifProjectManager()
            manifest_path = manager.create_project("cleanup-alias", project_root)
            warning_path = Path(manager.volume_cleanup_warning_path)
            logs_alias = warning_path.parent
            external_warning = external_root / warning_path.name
            external_payload = {
                "schema_version": TIF_VOLUME_CLEANUP_WARNING_SCHEMA_VERSION,
                "record_type": "tif_volume_cleanup_maintenance_warnings",
                "project_id": manager.project_data["project_id"],
                "warnings": [{"operation": "must-not-load"}],
            }
            external_warning.write_text(
                json.dumps(external_payload), encoding="utf-8"
            )
            original_bytes = external_warning.read_bytes()
            self._create_directory_alias(logs_alias, external_root)
            try:
                reloaded = TifProjectManager()
                with self.assertLogs(
                    "AntSleap.core.tif_project", level="WARNING"
                ):
                    reloaded.load_project(manifest_path)
                self.assertEqual(reloaded.volume_cleanup_warnings, [])

                manager.volume_cleanup_warnings = [
                    manager._normalize_volume_cleanup_warning(
                        {
                            "warning_id": "cleanup_warning_alias",
                            "operation": "must-not-persist",
                        }
                    )
                ]
                manager._volume_cleanup_warning_dirty_ids.update(
                    warning["warning_id"]
                    for warning in manager.volume_cleanup_warnings
                )
                persistence_error = manager._persist_volume_cleanup_warnings()
                self.assertIn("unsafe_parent_entry", persistence_error)
                self.assertEqual(external_warning.read_bytes(), original_bytes)
                self.assertFalse(
                    (external_root / f"{warning_path.name}.lock").exists()
                )
            finally:
                self._remove_directory_alias(logs_alias)

    def test_volume_cleanup_warning_concurrent_processes_merge_without_loss(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = TifProjectManager()
            manifest_path = manager.create_project(
                "cleanup-concurrent", Path(tmp) / "cleanup-concurrent"
            )
            context = multiprocessing.get_context("spawn")
            ready_queue = context.Queue()
            result_queue = context.Queue()
            start_event = context.Event()
            warning_ids = ["cleanup_warning_process_a", "cleanup_warning_process_b"]
            processes = [
                context.Process(
                    target=_persist_cleanup_warning_worker,
                    args=(
                        manifest_path,
                        warning_id,
                        ready_queue,
                        start_event,
                        result_queue,
                    ),
                )
                for warning_id in warning_ids
            ]
            for process in processes:
                process.start()
            try:
                ready = {ready_queue.get(timeout=20) for _index in processes}
                self.assertEqual(ready, set(warning_ids))
                start_event.set()
                results = dict(
                    result_queue.get(timeout=20) for _index in processes
                )
            finally:
                start_event.set()
                for process in processes:
                    process.join(timeout=20)
                    if process.is_alive():
                        process.terminate()
                        process.join(timeout=5)
            self.assertEqual(results, {warning_id: "" for warning_id in warning_ids})
            self.assertTrue(all(process.exitcode == 0 for process in processes))

            reloaded = TifProjectManager()
            reloaded.load_project(manifest_path)
            self.assertEqual(
                {item["warning_id"] for item in reloaded.volume_cleanup_warnings},
                set(warning_ids),
            )

    def test_cleanup_warning_paths_are_relative_or_redacted_before_persistence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_root = root / "cleanup-path-redaction" / "project"
            manager = TifProjectManager()
            manager.create_project("cleanup-path-redaction", project_root)

            internal_path = (
                project_root
                / "specimens"
                / "specimen"
                / "labels"
                / "working_edit.ome.zarr"
            )
            same_drive_external = (
                root / "private-parent" / "same-drive-secret.ome.zarr"
            )
            current_drive = project_root.drive.upper()
            other_drive = "Z:" if current_drive != "Z:" else "Y:"
            cross_drive_external = (
                f"{other_drive}\\private-cross-drive\\cross-drive-secret.ome.zarr"
            )
            nested_error_path = (
                same_drive_external.parent
                / "private-cleanup-error"
                / "nested-secret.ome.zarr"
            )

            internal_reference = manager._cleanup_warning_path_reference(
                internal_path
            )
            same_drive_reference = manager._cleanup_warning_path_reference(
                same_drive_external
            )
            traversal_reference = manager._cleanup_warning_path_reference(
                "../private-traversal/traversal-secret.ome.zarr"
            )
            cross_drive_reference = manager._cleanup_warning_path_reference(
                cross_drive_external
            )

            self.assertEqual(
                internal_reference,
                "specimens/specimen/labels/working_edit.ome.zarr",
            )
            for reference, basename in (
                (same_drive_reference, "same-drive-secret.ome.zarr"),
                (traversal_reference, "traversal-secret.ome.zarr"),
                (cross_drive_reference, "cross-drive-secret.ome.zarr"),
            ):
                with self.subTest(reference=reference):
                    self.assertTrue(reference.startswith("external_path_"))
                    self.assertIn(basename, reference)
                    self.assertIn("_sha256_", reference)
                    self.assertEqual(len(reference.rsplit("_sha256_", 1)[1]), 64)
                    self.assertNotIn("..", reference)
                    self.assertFalse(os.path.isabs(reference))
                    self.assertNotIn("private-parent", reference)
                    self.assertNotIn("private-traversal", reference)
                    self.assertNotIn("private-cross-drive", reference)
                    self.assertNotIn(other_drive, reference)

            self.assertEqual(
                same_drive_reference,
                manager._cleanup_warning_path_reference(same_drive_external),
            )
            manager.volume_cleanup_warnings = [
                manager._normalize_volume_cleanup_warning(
                    {
                        "target_path": internal_path,
                        "rollback_path": same_drive_external,
                        "error": (
                            "PermissionError: [WinError 5] cleanup failed: "
                            f"'{nested_error_path}'"
                        ),
                    }
                )
            ]
            manager._volume_cleanup_warning_dirty_ids.update(
                warning["warning_id"]
                for warning in manager.volume_cleanup_warnings
            )
            self.assertEqual(manager._persist_volume_cleanup_warnings(), "")
            persisted_text = Path(manager.volume_cleanup_warning_path).read_text(
                encoding="utf-8"
            )
            persisted = json.loads(persisted_text)
            self.assertEqual(
                persisted["warnings"][0]["target_path"], internal_reference
            )
            self.assertEqual(
                persisted["warnings"][0]["rollback_path"],
                same_drive_reference,
            )
            self.assertNotIn(str(same_drive_external.parent), persisted_text)
            self.assertNotIn(str(nested_error_path.parent), persisted_text)
            self.assertNotIn("private-cleanup-error", persisted_text)
            self.assertIn("external_path_nested-secret.ome.zarr_sha256_", persisted_text)

    def test_saturated_cleanup_warning_merge_preserves_each_new_writer(self):
        class CleanupReplacement:
            def __init__(self, marker, root):
                self.metadata = {"role": "manual_truth"}
                self.target = root / f"{marker}.ome.zarr"
                self.rollback_path = root / f"{marker}.rollback"

            def commit(self):
                return "rollback directory is locked"

        with tempfile.TemporaryDirectory() as tmp:
            manager = TifProjectManager()
            manifest_path = manager.create_project(
                "cleanup-saturated", Path(tmp) / "cleanup-saturated"
            )
            manager.volume_cleanup_warnings = [
                manager._normalize_volume_cleanup_warning(
                    {
                        "warning_id": f"cleanup_warning_initial_{index:03d}",
                        "recorded_at": "2026-08-24T00:00:00+00:00",
                        "operation": f"initial-{index:03d}",
                        "error": "locked",
                    }
                )
                for index in range(TIF_VOLUME_CLEANUP_WARNING_LIMIT)
            ]
            manager._volume_cleanup_warning_dirty_ids.update(
                warning["warning_id"]
                for warning in manager.volume_cleanup_warnings
            )
            self.assertEqual(manager._persist_volume_cleanup_warnings(), "")

            writer_a = TifProjectManager()
            writer_b = TifProjectManager()
            writer_a.load_project(manifest_path)
            writer_b.load_project(manifest_path)
            root = Path(writer_a.project_dir)

            with self.assertLogs("AntSleap.core.tif_project", level="WARNING"):
                writer_b._commit_volume_replacement_cleanup(
                    CleanupReplacement("writer-b", root),
                    operation="saturated-writer-b",
                )
            self.assertEqual(writer_a._persist_volume_cleanup_warnings(), "")
            after_stale_noop = TifProjectManager()
            after_stale_noop.load_project(manifest_path)
            after_stale_operations = {
                warning["operation"]
                for warning in after_stale_noop.volume_cleanup_warnings
            }
            self.assertIn("saturated-writer-b", after_stale_operations)
            self.assertNotIn("initial-000", after_stale_operations)
            with self.assertLogs("AntSleap.core.tif_project", level="WARNING"):
                writer_a._commit_volume_replacement_cleanup(
                    CleanupReplacement("writer-a", root),
                    operation="saturated-writer-a",
                )

            reloaded = TifProjectManager()
            reloaded.load_project(manifest_path)
            operations = [
                warning["operation"]
                for warning in reloaded.volume_cleanup_warnings
            ]
            self.assertEqual(len(operations), TIF_VOLUME_CLEANUP_WARNING_LIMIT)
            self.assertIn("saturated-writer-a", operations)
            self.assertIn("saturated-writer-b", operations)
            self.assertNotIn("initial-000", operations)
            self.assertNotIn("initial-001", operations)
            self.assertEqual(
                operations[-2:],
                ["saturated-writer-b", "saturated-writer-a"],
            )

    def test_invalid_regular_cleanup_sidecar_is_isolated_before_new_warning(self):
        class CleanupReplacement:
            metadata = {"role": "manual_truth"}

            def __init__(self, root):
                self.target = root / "current.ome.zarr"
                self.rollback_path = root / "current.rollback"

            def commit(self):
                return "rollback directory is locked"

        invalid_cases = {
            "malformed_json": lambda project_id: b'{"warnings": [',
            "oversized_json": lambda project_id: (
                b'{"padding":"'
                + b"x" * TIF_VOLUME_CLEANUP_WARNING_MAX_BYTES
                + b'"}'
            ),
            "wrong_schema": lambda project_id: json.dumps(
                {
                    "schema_version": "unsupported_cleanup_schema",
                    "project_id": project_id,
                    "warnings": [
                        {
                            "warning_id": "cleanup_warning_must_not_merge",
                            "operation": "must-not-merge",
                        }
                    ],
                }
            ).encode("utf-8"),
            "wrong_project": lambda project_id: json.dumps(
                {
                    "schema_version": TIF_VOLUME_CLEANUP_WARNING_SCHEMA_VERSION,
                    "record_type": "tif_volume_cleanup_maintenance_warnings",
                    "project_id": "different-project",
                    "warnings": [
                        {
                            "warning_id": "cleanup_warning_must_not_merge",
                            "operation": "must-not-merge",
                        }
                    ],
                }
            ).encode("utf-8"),
        }

        for case_name, invalid_bytes in invalid_cases.items():
            with self.subTest(case=case_name), tempfile.TemporaryDirectory() as tmp:
                manager = TifProjectManager()
                manager.create_project(
                    f"cleanup-invalid-{case_name}",
                    Path(tmp) / f"cleanup-invalid-{case_name}",
                )
                warning_path = Path(manager.volume_cleanup_warning_path)
                warning_path.parent.mkdir(parents=True, exist_ok=True)
                invalid_content = invalid_bytes(manager.project_data["project_id"])
                warning_path.write_bytes(invalid_content)

                with self.assertLogs(
                    "AntSleap.core.tif_project", level="WARNING"
                ):
                    cleanup_error = manager._commit_volume_replacement_cleanup(
                        CleanupReplacement(Path(manager.project_dir)),
                        operation=f"recovered-{case_name}",
                    )

                self.assertIn("locked", cleanup_error)
                persisted = json.loads(warning_path.read_text(encoding="utf-8"))
                self.assertEqual(
                    persisted["schema_version"],
                    TIF_VOLUME_CLEANUP_WARNING_SCHEMA_VERSION,
                )
                self.assertEqual(
                    persisted["project_id"], manager.project_data["project_id"]
                )
                self.assertEqual(len(persisted["warnings"]), 1)
                self.assertEqual(
                    persisted["warnings"][0]["operation"],
                    f"recovered-{case_name}",
                )
                self.assertNotIn("must-not-merge", warning_path.read_text("utf-8"))
                rejected_path = Path(f"{warning_path}.rejected")
                self.assertEqual(rejected_path.read_bytes(), invalid_content)
                self.assertEqual(
                    list(warning_path.parent.glob(f"{warning_path.name}.rejected*")),
                    [rejected_path],
                )
                self.assertEqual(manager._volume_cleanup_warning_dirty_ids, set())

    def test_cleanup_warning_error_redacts_relative_external_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = TifProjectManager()
            manager.create_project(
                "cleanup-relative-redaction", Path(tmp) / "cleanup-relative-redaction"
            )
            error = (
                "failed ../private-parent/relative-secret.tif, "
                "~/private-home/home-secret.tif, and "
                r"C:private-drive\drive-secret.tif, plus "
                r"\private-root\root-secret.tif"
            )
            normalized = manager._normalize_volume_cleanup_warning(
                {"operation": "relative-redaction", "error": error}
            )

            self.assertNotIn("private-parent", normalized["error"])
            self.assertNotIn("private-home", normalized["error"])
            self.assertNotIn("private-drive", normalized["error"])
            self.assertNotIn("private-root", normalized["error"])
            self.assertNotIn("../", normalized["error"])
            self.assertNotIn("~/", normalized["error"])
            self.assertNotIn("C:private", normalized["error"])
            self.assertEqual(normalized["error"].count("external_path_"), 4)
            self.assertTrue(
                manager._cleanup_warning_path_reference("~/private/home.tif").startswith(
                    "external_path_"
                )
            )
            self.assertTrue(
                manager._cleanup_warning_path_reference(
                    r"C:private\drive.tif"
                ).startswith("external_path_")
            )

    def test_cleanup_warning_error_redacts_unquoted_paths_with_spaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = TifProjectManager()
            manager.create_project(
                "cleanup-spaced-path-redaction",
                Path(tmp) / "cleanup-spaced-path-redaction",
            )
            cases = (
                (
                    r"failed at C:\Secret Folder\private name.txt, retry pending",
                    ("Secret Folder", "private name.txt"),
                    "retry pending",
                ),
                (
                    "failed at /Users/Private Folder/private name.tif; retry pending",
                    ("Private Folder", "private name.tif"),
                    "retry pending",
                ),
                (
                    "failed at ../Private Folder/private name.tif, retry pending",
                    ("Private Folder", "private name.tif"),
                    "retry pending",
                ),
            )

            for error, private_fragments, preserved_suffix in cases:
                with self.subTest(error=error):
                    normalized = manager._normalize_volume_cleanup_warning(
                        {"operation": "spaced-path-redaction", "error": error}
                    )["error"]
                    self.assertIn("external_path_", normalized)
                    self.assertIn(preserved_suffix, normalized)
                    for fragment in private_fragments:
                        self.assertNotIn(fragment, normalized)

            ambiguous = manager._normalize_volume_cleanup_warning(
                {
                    "operation": "spaced-path-redaction",
                    "error": r"failed at C:\Secret Folder\private name.txt because cleanup failed",
                }
            )["error"]
            self.assertIn("external_path_", ambiguous)
            self.assertNotIn("Secret Folder", ambiguous)
            self.assertNotIn("private name.txt", ambiguous)
            self.assertNotIn("because cleanup failed", ambiguous)

    def test_invalid_cleanup_sidecar_is_preserved_when_isolation_slot_is_unsafe(self):
        class CleanupReplacement:
            metadata = {"role": "manual_truth"}

            def __init__(self, root):
                self.target = root / "current.ome.zarr"
                self.rollback_path = root / "current.rollback"

            def commit(self):
                return "rollback directory is locked"

        with tempfile.TemporaryDirectory() as tmp:
            manager = TifProjectManager()
            manager.create_project(
                "cleanup-isolation-blocked", Path(tmp) / "cleanup-isolation-blocked"
            )
            warning_path = Path(manager.volume_cleanup_warning_path)
            warning_path.parent.mkdir(parents=True, exist_ok=True)
            original_bytes = b'{"warnings": ['
            warning_path.write_bytes(original_bytes)
            Path(f"{warning_path}.rejected").mkdir()

            with self.assertLogs("AntSleap.core.tif_project", level="WARNING"):
                cleanup_error = manager._commit_volume_replacement_cleanup(
                    CleanupReplacement(Path(manager.project_dir)),
                    operation="isolation-must-fail",
                )

            self.assertIn("locked", cleanup_error)
            self.assertEqual(warning_path.read_bytes(), original_bytes)
            self.assertTrue(Path(f"{warning_path}.rejected").is_dir())
            self.assertEqual(len(manager._volume_cleanup_warning_dirty_ids), 1)

    def test_safe_json_fstat_failure_closes_fd_and_removes_temp(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "warning.json"
            descriptors = []
            real_mkstemp = safe_io.tempfile.mkstemp

            def tracked_mkstemp(*args, **kwargs):
                descriptor, path = real_mkstemp(*args, **kwargs)
                descriptors.append(descriptor)
                return descriptor, path

            def fail_fstat(_descriptor):
                raise OSError("simulated fstat failure")

            with patch.object(
                safe_io, "_directory_fd_guards_available", return_value=False
            ), patch.object(
                safe_io.tempfile, "mkstemp", side_effect=tracked_mkstemp
            ), patch.object(
                safe_io.os, "fstat", side_effect=fail_fstat
            ):
                with self.assertRaisesRegex(OSError, "simulated fstat failure"):
                    safe_io.atomic_write_json_in_root(
                        target,
                        {"status": "new"},
                        trusted_root=root,
                    )

            self.assertEqual(len(descriptors), 1)
            with self.assertRaises(OSError):
                os.fstat(descriptors[0])
            self.assertEqual(list(root.glob(".warning.json.tmp-*")), [])

    def test_posix_parent_fstat_failure_closes_new_directory_descriptor(self):
        if not safe_io._directory_fd_guards_available():
            self.skipTest("POSIX directory-fd guards are unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "nested").mkdir()
            target = root / "nested" / "warning.json"
            real_open = safe_io.os.open
            real_fstat = safe_io.os.fstat
            child_descriptors = []
            calls = {"count": 0}

            def tracked_open(path, flags, mode=0o777, *, dir_fd=None):
                descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
                if dir_fd is not None:
                    child_descriptors.append(descriptor)
                return descriptor

            def fail_child_fstat(descriptor):
                calls["count"] += 1
                if calls["count"] == 2:
                    raise OSError("simulated child fstat failure")
                return real_fstat(descriptor)

            with patch.object(
                safe_io,
                "_directory_fd_guards_available",
                return_value=True,
            ), patch.object(
                safe_io.os, "open", side_effect=tracked_open
            ), patch.object(
                safe_io.os, "fstat", side_effect=fail_child_fstat
            ):
                with self.assertRaisesRegex(
                    OSError, "simulated child fstat failure"
                ):
                    safe_io._open_safe_parent(
                        target,
                        root,
                        create=False,
                    )

            self.assertEqual(len(child_descriptors), 1)
            with self.assertRaises(OSError):
                os.fstat(child_descriptors[0])

    def test_advisory_lock_fdopen_failure_closes_open_descriptor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock_path = root / "warning.lock"
            descriptors = []
            real_open_entry = safe_io._open_entry

            def tracked_open_entry(*args, **kwargs):
                descriptor = real_open_entry(*args, **kwargs)
                descriptors.append(descriptor)
                return descriptor

            with patch.object(
                safe_io, "_directory_fd_guards_available", return_value=False
            ), patch.object(
                safe_io, "_open_entry", side_effect=tracked_open_entry
            ), patch.object(
                safe_io.os, "fdopen", side_effect=OSError("simulated fdopen failure")
            ):
                with self.assertRaisesRegex(OSError, "simulated fdopen failure"):
                    safe_io.AdvisoryFileLock(
                        lock_path, trusted_root=root
                    ).acquire()

            self.assertEqual(len(descriptors), 1)
            with self.assertRaises(OSError):
                os.fstat(descriptors[0])
            replacement_lock = safe_io.AdvisoryFileLock(
                lock_path, trusted_root=root
            )
            self.assertTrue(replacement_lock.acquire())
            replacement_lock.release()

    def test_advisory_lock_rejects_repeated_acquire_without_losing_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock_path = root / "warning.lock"
            lock = safe_io.AdvisoryFileLock(lock_path, trusted_root=root)
            self.assertTrue(lock.acquire())
            with self.assertRaisesRegex(
                RuntimeError, "advisory_file_lock_already_acquired"
            ):
                lock.acquire()
            self.assertIsNotNone(lock.handle)
            lock.release()

            replacement_lock = safe_io.AdvisoryFileLock(
                lock_path, trusted_root=root
            )
            self.assertTrue(replacement_lock.acquire())
            replacement_lock.release()

    def test_safe_json_read_rejects_content_stat_change_and_closes_fd(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "warning.json"
            target.write_text('{"status": "ready"}', encoding="utf-8")
            real_fstat = safe_io.os.fstat
            descriptors = []
            calls = {"count": 0}

            def changed_second_fstat(descriptor):
                calls["count"] += 1
                descriptors.append(descriptor)
                result = real_fstat(descriptor)
                if calls["count"] == 2:
                    values = list(result)
                    values[6] = int(result.st_size) + 1
                    return os.stat_result(values)
                return result

            with patch.object(
                safe_io, "_directory_fd_guards_available", return_value=False
            ), patch.object(
                safe_io.os, "fstat", side_effect=changed_second_fstat
            ):
                with self.assertRaisesRegex(
                    safe_io.UnsafeFilesystemPath,
                    "file_content_changed_during_read",
                ):
                    safe_io.read_json_bounded_in_root(
                        target,
                        trusted_root=root,
                        max_bytes=1024,
                    )

            self.assertGreaterEqual(len(descriptors), 2)
            with self.assertRaises(OSError):
                os.fstat(descriptors[0])

    def test_batch_volume_commit_cleanup_errors_are_recorded_without_failing_promotion(self):
        class CleanupReplacement:
            def __init__(self, index):
                self.metadata = {"role": "manual_truth"}
                self.target = f"manual-{index}.ome.zarr"
                self.rollback_path = f"manual-{index}.ome.zarr.rollback"
                self.commit_calls = 0

            def commit(self):
                self.commit_calls += 1
                return "rollback directory is locked"

        manager = TifProjectManager()
        refs = [
            {"specimen_id": "specimen", "part_id": "head"},
            {"specimen_id": "specimen", "part_id": "thorax"},
        ]
        replacements = [CleanupReplacement(1), CleanupReplacement(2)]
        next_replacement = iter(replacements)

        def promote(*_args, _replacement_transactions=None, **_kwargs):
            replacement = next(next_replacement)
            _replacement_transactions.append(replacement)
            return {"status": "reviewed"}

        acceptance = {"ready": refs, "blocked": []}
        with self.assertLogs("AntSleap.core.tif_project", level="WARNING") as logs, patch.object(
            manager,
            "build_part_review_acceptance_report",
            return_value=acceptance,
        ), patch.object(
            manager,
            "promote_part_editable_result_to_manual_truth",
            side_effect=promote,
        ):
            result = manager.promote_reviewed_part_results_to_manual_truth(refs, save=False)

        self.assertEqual(result["count"], 2)
        self.assertEqual([item.commit_calls for item in replacements], [1, 1])
        self.assertEqual(len(manager.volume_cleanup_warnings), 2)
        self.assertEqual(
            {item["operation"] for item in manager.volume_cleanup_warnings},
            {"batch_volume_replacement_commit"},
        )
        self.assertEqual(len(logs.output), 2)

    def test_copy_model_draft_rejects_ancestor_target_without_touching_manual_truth(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._working_edit_copy_fixture(tmp, "draft_copy_overlap")
            labels_root = fixture["working_path"].parent
            fixture["manager"].get_specimen("specimen")["labels"]["working_edit"]["path"] = (
                fixture["manager"].to_relative(labels_root)
            )

            with self.assertRaisesRegex(ValueError, "source_target_label_path_overlap:model_draft"):
                fixture["manager"].copy_label_layer_to_working_edit(
                    "specimen", source_role="model_draft", save=True
                )

            np.testing.assert_array_equal(
                load_volume_sidecar(fixture["manual_path"]), fixture["manual_array"]
            )
            np.testing.assert_array_equal(
                load_volume_sidecar(fixture["draft_path"]), fixture["draft_array"]
            )

    def test_copy_model_draft_rejects_target_inside_manual_truth(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._working_edit_copy_fixture(tmp, "draft_copy_truth_child")
            child_target = fixture["manual_path"] / "nested_working_edit.ome.zarr"
            fixture["manager"].get_specimen("specimen")["labels"]["working_edit"]["path"] = (
                fixture["manager"].to_relative(child_target)
            )

            with self.assertRaisesRegex(ValueError, "working_edit_manual_truth_path_overlap"):
                fixture["manager"].copy_label_layer_to_working_edit(
                    "specimen", source_role="model_draft", save=True
                )

            np.testing.assert_array_equal(
                load_volume_sidecar(fixture["manual_path"]), fixture["manual_array"]
            )
            self.assertFalse(child_target.exists())

    def test_copy_manual_truth_to_distinct_working_edit_remains_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._working_edit_copy_fixture(tmp, "manual_copy_success")
            data_version_before = fixture["manager"].project_data[
                "project_data_version_id"
            ]

            copied = fixture["manager"].copy_label_layer_to_working_edit(
                "specimen", source_role="manual_truth", save=True
            )

            self.assertEqual(copied["status"], "copied_from_manual_truth")
            self.assertEqual(
                fixture["manager"].project_data["project_data_version_id"],
                data_version_before,
            )
            np.testing.assert_array_equal(
                load_volume_sidecar(fixture["working_path"]), fixture["manual_array"]
            )
            np.testing.assert_array_equal(
                load_volume_sidecar(fixture["manual_path"]), fixture["manual_array"]
            )

    def test_copy_model_draft_save_failure_rolls_back_volume_memory_and_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._working_edit_copy_fixture(tmp, "draft_copy_rollback")
            manager = fixture["manager"]
            project_snapshot = copy.deepcopy(manager.project_data)
            pending_version_snapshot = manager._pending_project_data_version_id
            pending_assets_snapshot = set(manager._pending_integrity_dirty_assets)

            with patch(
                "AntSleap.core.tif_sqlite_writer._insert_project_row",
                side_effect=RuntimeError("sqlite write failed"),
            ):
                with self.assertRaisesRegex(RuntimeError, "sqlite write failed"):
                    manager.copy_label_layer_to_working_edit(
                        "specimen", source_role="model_draft", save=True
                    )

            self.assertEqual(manager.project_data, project_snapshot)
            self.assertEqual(
                manager._pending_project_data_version_id, pending_version_snapshot
            )
            self.assertEqual(
                manager._pending_integrity_dirty_assets, pending_assets_snapshot
            )
            np.testing.assert_array_equal(
                load_volume_sidecar(fixture["working_path"]), fixture["working_array"]
            )
            np.testing.assert_array_equal(
                load_volume_sidecar(fixture["manual_path"]), fixture["manual_array"]
            )
            self.assertFalse(
                any(
                    marker in path.name
                    for path in fixture["working_path"].parent.iterdir()
                    for marker in (".pending_", ".rollback_")
                )
            )

            reloaded = TifProjectManager()
            reloaded.load_project(fixture["manifest_path"])
            reloaded_specimen = reloaded.get_specimen("specimen")
            self.assertEqual(
                reloaded_specimen["labels"]["working_edit"]["status"], "in_progress"
            )
            self.assertEqual(reloaded_specimen["review_status"], "reviewed")
            self.assertTrue(reloaded_specimen["train_ready"])

    def test_copy_model_draft_refuses_working_edit_alias_to_manual_truth(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._working_edit_copy_fixture(tmp, "draft_copy_alias")
            shutil.rmtree(fixture["working_path"])
            try:
                os.symlink(
                    fixture["manual_path"],
                    fixture["working_path"],
                    target_is_directory=True,
                )
            except (OSError, NotImplementedError) as exc:
                if os.name != "nt":
                    self.skipTest(f"directory aliases are unavailable: {exc}")
                junction = subprocess.run(
                    [
                        "cmd.exe",
                        "/d",
                        "/c",
                        "mklink",
                        "/J",
                        str(fixture["working_path"]),
                        str(fixture["manual_path"]),
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if junction.returncode != 0:
                    self.skipTest(
                        f"directory aliases are unavailable: {exc}; {junction.stderr}"
                    )

            try:
                with self.assertRaisesRegex(
                    ValueError, "working_edit_manual_truth_same_path"
                ):
                    fixture["manager"].copy_label_layer_to_working_edit(
                        "specimen", source_role="model_draft", save=True
                    )

                np.testing.assert_array_equal(
                    load_volume_sidecar(fixture["manual_path"]),
                    fixture["manual_array"],
                )
                self.assertTrue(
                    os.path.samefile(fixture["working_path"], fixture["manual_path"])
                )
            finally:
                if os.path.lexists(fixture["working_path"]):
                    if os.name == "nt":
                        os.rmdir(fixture["working_path"])
                    else:
                        os.unlink(fixture["working_path"])

    def test_copy_model_draft_enforces_platform_reported_path_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._working_edit_copy_fixture(tmp, "draft_copy_mock_alias")

            with patch(
                "AntSleap.core.tif_project.paths_refer_to_same_file",
                side_effect=(False, True),
            ) as same_file:
                with self.assertRaisesRegex(
                    ValueError, "working_edit_manual_truth_same_path"
                ):
                    fixture["manager"].copy_label_layer_to_working_edit(
                        "specimen", source_role="model_draft", save=True
                    )

            self.assertEqual(same_file.call_count, 2)
            np.testing.assert_array_equal(
                load_volume_sidecar(fixture["working_path"]), fixture["working_array"]
            )
            np.testing.assert_array_equal(
                load_volume_sidecar(fixture["manual_path"]), fixture["manual_array"]
            )

    def test_copy_model_draft_refuses_source_alias_to_manual_truth(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._working_edit_copy_fixture(
                tmp, "draft_copy_source_mock_alias"
            )

            with patch(
                "AntSleap.core.tif_project.paths_refer_to_same_file",
                side_effect=(False, False, True),
            ) as same_file:
                with self.assertRaisesRegex(
                    ValueError, "source_manual_truth_same_path:model_draft"
                ):
                    fixture["manager"].copy_label_layer_to_working_edit(
                        "specimen", source_role="model_draft", save=True
                    )

            self.assertEqual(same_file.call_count, 3)
            np.testing.assert_array_equal(
                load_volume_sidecar(fixture["working_path"]), fixture["working_array"]
            )
            np.testing.assert_array_equal(
                load_volume_sidecar(fixture["manual_path"]), fixture["manual_array"]
            )

    def test_raw_backup_cannot_be_promoted_to_manual_truth(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "raw_backup_truth_guard"
            manager = TifProjectManager()
            manager.create_project("raw_backup_truth_guard", project_root)
            manager.create_specimen_scaffold("01-0101-raw")
            part_image_rel = "specimens/01-0101-raw/parts/brain/image.ome.zarr"
            backup_rel = "specimens/01-0101-raw/parts/brain/labels/raw_ai_prediction_backup.ome.zarr"
            part_meta = write_volume_sidecar(project_root / part_image_rel, np.zeros((2, 3, 4), dtype=np.uint8), role="part_image")
            backup_meta = write_volume_sidecar(project_root / backup_rel, np.ones((2, 3, 4), dtype=np.uint16), role="raw_ai_prediction_backup")
            manager.add_part("01-0101-raw", "brain", image={"path": part_image_rel, **part_meta}, save=False)
            manager.register_part_label_volume(
                "01-0101-raw",
                "brain",
                "raw_ai_prediction_backup",
                backup_rel,
                backup_meta["shape_zyx"],
                backup_meta["dtype"],
                operation="prediction_raw_backup_import",
                audit_metadata={"prediction_id": "p1"},
                save=True,
            )

            with self.assertRaisesRegex(ValueError, "raw_ai_prediction_backup_cannot_be_promoted_to_manual_truth"):
                manager.promote_part_editable_result_to_manual_truth(
                    "01-0101-raw",
                    "brain",
                    source_role="raw_ai_prediction_backup",
                )

            self.assertFalse((manager.get_part("01-0101-raw", "brain")["labels"]["manual_truth"] or {}).get("path"))

    def test_specimen_ids_cannot_share_the_same_storage_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "storage_collision"
            manager = TifProjectManager()
            manager.create_project("storage_collision", project_root)
            manager.create_specimen_scaffold("A/B")

            with self.assertRaisesRegex(ValueError, "specimen_storage_path_collision"):
                manager.add_specimen("A?B")

    def test_import_refuses_to_reuse_non_empty_orphan_specimen_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "orphan_folder"
            manager = TifProjectManager()
            manager.create_project("orphan_folder", project_root)
            orphan_dir = project_root / "specimens" / "01-0101-17"
            orphan_dir.mkdir(parents=True)
            (orphan_dir / "leftover.txt").write_text("old data", encoding="utf-8")

            with self.assertRaisesRegex(FileExistsError, "specimen_storage_dir_not_empty"):
                manager.create_specimen_scaffold("01-0101-17")

            self.assertIsNone(manager.get_specimen("01-0101-17", default=None))

    def test_dot_only_specimen_id_cannot_escape_specimens_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "dot_path"
            manager = TifProjectManager()
            manager.create_project("dot_path", project_root)
            manager.create_specimen_scaffold("..")

            specimen = manager.get_specimen("..")
            self.assertIsNotNone(specimen)
            self.assertEqual(specimen["material_map"], "specimens/specimen/material_map.json")
            self.assertTrue((project_root / "specimens" / "specimen" / "material_map.json").exists())

    def test_scaffold_creation_failure_rolls_back_specimen_and_storage(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "scaffold_rollback"
            manager = TifProjectManager()
            manager.create_project("scaffold_rollback", project_root)

            with patch("AntSleap.core.tif_project.write_material_map", side_effect=RuntimeError("material map failed")):
                with self.assertRaisesRegex(RuntimeError, "material map failed"):
                    manager.create_specimen_scaffold("01-0101-18")

            self.assertIsNone(manager.get_specimen("01-0101-18", default=None))
            self.assertFalse((project_root / "specimens" / "01-0101-18").exists())

    def test_old_tif_project_load_adds_empty_parts_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "old_project"
            manager = TifProjectManager()
            project_json = manager.create_project("old_project", project_root)
            manager.add_specimen("01-0101-old", save=True)
            payload_path = Path(project_json)
            payload = payload_path.read_text(encoding="utf-8")
            payload = payload.replace(',\n      "parts": []', "")
            payload_path.write_text(payload, encoding="utf-8")

            reloaded = TifProjectManager()
            reloaded.load_project(project_json)

            self.assertEqual(reloaded.get_specimen("01-0101-old")["parts"], [])
            self.assertEqual(reloaded.get_specimen("01-0101-old")["part_rois"], [])

    def test_part_roi_drafts_round_trip_and_cancel_without_touching_parts(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "roi_project"
            manager = TifProjectManager()
            project_json = manager.create_project("roi_project", project_root)
            manager.create_specimen_scaffold("01-0101-roi")
            roi = manager.add_part_roi(
                "01-0101-roi",
                "head_roi",
                display_name="Head ROI",
                bbox_zyx=[[1, 3], [2, 5], [1, 4]],
            )

            reloaded = TifProjectManager()
            reloaded.load_project(project_json)
            loaded = reloaded.get_part_roi("01-0101-roi", "head_roi")

            self.assertEqual(roi["status"], "draft")
            self.assertEqual(loaded["bbox_zyx"], [[1, 3], [2, 5], [1, 4]])
            self.assertEqual(len(reloaded.list_part_rois("01-0101-roi")), 1)

            reloaded.discard_part_roi("01-0101-roi", "head_roi")

            self.assertEqual(reloaded.list_part_rois("01-0101-roi"), [])
            self.assertEqual(len(reloaded.list_part_rois("01-0101-roi", include_cancelled=True)), 1)

    def test_part_records_round_trip_and_discard_only_removes_part_storage(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "parts_project"
            manager = TifProjectManager()
            project_json = manager.create_project("parts_project", project_root)
            manager.create_specimen_scaffold("01-0101-parts")
            image_rel = "specimens/01-0101-parts/working/image.ome.zarr"
            image_meta = write_volume_sidecar(project_root / image_rel, np.arange(3 * 4 * 5, dtype=np.uint8).reshape((3, 4, 5)), role="working_image")
            manager.register_working_volume("01-0101-parts", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            part_dir = manager.part_dir("01-0101-parts", "Head")
            part_image_rel = f"{part_dir}/image.ome.zarr"
            part_mask_rel = f"{part_dir}/mask.ome.zarr"
            part_image_meta = write_volume_sidecar(project_root / part_image_rel, np.ones((1, 2, 3), dtype=np.uint8), role="part_image")
            part_mask_meta = write_volume_sidecar(project_root / part_mask_rel, np.zeros((1, 2, 3), dtype=np.uint16), role="part_mask")
            part = manager.add_part(
                "01-0101-parts",
                "Head",
                display_name="Head",
                image={"path": part_image_rel, **part_image_meta},
                mask={"path": part_mask_rel, **part_mask_meta},
                parent_bbox_zyx=[[0, 1], [1, 3], [1, 4]],
                contours_path=f"{part_dir}/contours.json",
                extraction_path=f"{part_dir}/extraction.json",
                status="roi_confirmed",
            )
            manager.update_part_view_settings("01-0101-parts", "Head", {"volume_tint": "white", "volume_tint_custom": "#f0f4f2"})

            reloaded = TifProjectManager()
            reloaded.load_project(project_json)
            loaded_part = reloaded.get_part("01-0101-parts", "Head")

            self.assertEqual(part["part_id"], "Head")
            self.assertEqual(loaded_part["display_name"], "Head")
            self.assertEqual(loaded_part["image"]["shape_zyx"], [1, 2, 3])
            self.assertEqual(loaded_part["parent_bbox_zyx"], [[0, 1], [1, 3], [1, 4]])
            self.assertEqual(loaded_part["view_settings"]["volume_tint"], "white")
            self.assertEqual(loaded_part["view_settings"]["volume_tint_custom"], "#f0f4f2")
            self.assertTrue((project_root / image_rel / "array.npy").exists())

            result = reloaded.discard_part("01-0101-parts", "Head")

            self.assertTrue(result["removed_part"])
            self.assertTrue(result["removed_storage"])
            self.assertFalse((project_root / part_dir).exists())
            self.assertTrue((project_root / image_rel / "array.npy").exists())
            self.assertEqual(reloaded.list_parts("01-0101-parts"), [])

    def test_part_ids_reject_duplicates_and_storage_collisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = TifProjectManager()
            manager.create_project("part_collision", Path(tmp) / "part_collision")
            manager.create_specimen_scaffold("01-0101-collision")
            manager.add_part("01-0101-collision", "Head", save=False)

            with self.assertRaisesRegex(ValueError, "duplicate_part_id"):
                manager.add_part("01-0101-collision", "Head", save=False)

            with self.assertRaisesRegex(ValueError, "duplicate_part_id"):
                manager.add_part("01-0101-collision", "Head?", save=False)

    def test_crop_volume_to_part_writes_local_image_mask_and_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "crop_part"
            manager = TifProjectManager()
            manager.create_project("crop_part", project_root)
            manager.create_specimen_scaffold("01-0101-crop")
            image = np.arange(4 * 5 * 6, dtype=np.uint8).reshape((4, 5, 6))
            image_rel = "specimens/01-0101-crop/working/image.ome.zarr"
            image_meta = write_volume_sidecar(
                project_root / image_rel,
                image,
                role="working_image",
                spacing_zyx=[2.0, 1.0, 1.0],
                spacing_unit="micrometer",
                scale_verified=True,
            )
            manager.register_working_volume(
                "01-0101-crop",
                image_rel,
                image_meta["shape_zyx"],
                image_meta["dtype"],
                spacing_zyx=image_meta["spacing_zyx"],
                spacing_unit=image_meta["spacing_unit"],
                save=False,
            )
            manager.save_project()

            part = crop_volume_to_part(manager, "01-0101-crop", "head", [[1, 3], [1, 4], [2, 6]], display_name="Head")

            cropped = load_volume_sidecar(project_root / part["image"]["path"])
            mask = load_volume_sidecar(project_root / part["mask"]["path"])
            np.testing.assert_array_equal(cropped, image[1:3, 1:4, 2:6])
            self.assertEqual(mask.shape, cropped.shape)
            self.assertEqual(int(mask.sum()), 0)
            self.assertTrue((project_root / part["contours_path"]).exists())
            self.assertTrue((project_root / part["extraction_path"]).exists())
            self.assertEqual(part["parent_bbox_zyx"], [[1, 3], [1, 4], [2, 6]])
            self.assertEqual(part["image"]["spacing_unit"], "micrometer")
            self.assertTrue(part["image"]["scale_verified"])
            self.assertTrue(part["mask"]["scale_verified"])

    def test_crop_volume_to_part_requires_sidecar_and_project_scale_trust(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "untrusted_crop"
            manager = TifProjectManager()
            manager.create_project("untrusted_crop", project_root)
            manager.create_specimen_scaffold("01-0101-untrusted")
            image_rel = "specimens/01-0101-untrusted/working/image.ome.zarr"
            image_meta = write_volume_sidecar(
                project_root / image_rel,
                np.zeros((3, 4, 5), dtype=np.uint8),
                role="working_image",
                spacing_zyx=[2.0, 1.0, 0.5],
                spacing_unit="micrometer",
                scale_verified=True,
            )
            manager.register_working_volume(
                "01-0101-untrusted",
                image_rel,
                image_meta["shape_zyx"],
                image_meta["dtype"],
                spacing_zyx=image_meta["spacing_zyx"],
                spacing_unit=image_meta["spacing_unit"],
                scale_verified=False,
                save=True,
            )

            part = crop_volume_to_part(
                manager,
                "01-0101-untrusted",
                "head",
                [[0, 2], [0, 3], [0, 4]],
            )

            self.assertEqual(part["image"]["spacing_unit"], "unknown")
            self.assertFalse(part["image"]["scale_verified"])
            self.assertEqual(part["mask"]["spacing_unit"], "unknown")
            self.assertFalse(part["mask"]["scale_verified"])

    def test_rectangular_keyframes_generate_preview_mask_between_slices(self):
        contours = {"axis": "z", "keyframes": []}
        contours = add_rectangular_keyframe(contours, 0, [[1, 4], [1, 4]])
        contours = add_rectangular_keyframe(contours, 2, [[2, 5], [2, 5]])

        mask = build_preview_mask_from_contours(contours, (3, 6, 6))

        self.assertEqual(mask.shape, (3, 6, 6))
        self.assertGreater(int(mask[1].sum()), 0)
        self.assertGreater(int(mask.sum()), int(mask[0].sum()))

    def test_freehand_polygon_keyframe_preserves_subpixel_points(self):
        contours = {"axis": "z", "keyframes": []}
        drawn_polygon = [[1.2, 1.6], [2.4, 1.2], [4.7, 1.4], [4.4, 4.8], [2.6, 4.2], [1.3, 4.5]]
        contours = add_polygon_keyframe(contours, 1, drawn_polygon, source="manual_freehand")

        polygon = contours["keyframes"][0]["polygon"]
        self.assertEqual(polygon, drawn_polygon)
        self.assertIsInstance(polygon[0][0], float)

        mask = build_preview_mask_from_contours(contours, (3, 6, 6))
        self.assertGreater(int(mask[1].sum()), 0)

    def test_preview_mask_only_fills_between_first_and_last_keyframes(self):
        contours = {"axis": "z", "keyframes": []}
        contours = add_rectangular_keyframe(contours, 1, [[1, 4], [1, 4]])
        contours = add_rectangular_keyframe(contours, 3, [[2, 5], [2, 5]])

        mask = build_preview_mask_from_contours(contours, (5, 6, 6))

        self.assertEqual(int(mask[0].sum()), 0)
        self.assertGreater(int(mask[1].sum()), 0)
        self.assertGreater(int(mask[2].sum()), 0)
        self.assertGreater(int(mask[3].sum()), 0)
        self.assertEqual(int(mask[4].sum()), 0)

    def test_preview_mask_reuses_keyframe_distance_fields(self):
        contours = {"axis": "z", "keyframes": []}
        contours = add_rectangular_keyframe(contours, 0, [[2, 10], [2, 10]])
        contours = add_rectangular_keyframe(contours, 3, [[3, 11], [3, 11]])
        contours = add_rectangular_keyframe(contours, 6, [[4, 12], [4, 12]])

        with patch.object(
            tif_part_extraction,
            "signed_distance",
            wraps=tif_part_extraction.signed_distance,
        ) as distance_mock:
            mask = build_preview_mask_from_contours(contours, (7, 16, 16))

        self.assertGreater(int(mask.sum()), 0)
        self.assertEqual(distance_mock.call_count, 3)

    def test_local_preview_optimization_preserves_full_frame_mask_pixels(self):
        keyframes = [
            {
                "axis": "z",
                "slice_index": 1,
                "polygon": [[1.2, 2.4], [18.8, 3.1], [16.3, 22.7], [3.0, 19.4]],
            },
            {
                "axis": "z",
                "slice_index": 6,
                "polygon": [[8.3, 1.1], [29.1, 8.2], [22.4, 29.0], [4.2, 21.5]],
            },
        ]
        shape = (8, 32, 32)
        start_mask = tif_part_extraction.polygon_to_mask(keyframes[0]["polygon"], shape[1:])
        end_mask = tif_part_extraction.polygon_to_mask(keyframes[1]["polygon"], shape[1:])
        start_distance = tif_part_extraction.signed_distance(start_mask)
        end_distance = tif_part_extraction.signed_distance(end_mask)
        expected = np.zeros(shape, dtype=np.uint16)
        expected[1] = start_mask.astype(np.uint16)
        expected[6] = end_mask.astype(np.uint16)
        for z_index in range(2, 6):
            weight = float(z_index - 1) / 5.0
            expected[z_index] = ((1.0 - weight) * start_distance + weight * end_distance <= 0.0).astype(np.uint16)

        actual = tif_part_extraction.interpolate_masks_from_keyframes(keyframes, shape)

        np.testing.assert_array_equal(actual, expected)

    def test_preview_mask_honors_cancellation_between_slices(self):
        contours = {"axis": "z", "keyframes": []}
        contours = add_rectangular_keyframe(contours, 0, [[2, 20], [2, 20]])
        contours = add_rectangular_keyframe(contours, 15, [[4, 22], [4, 22]])
        checks = []

        def cancel_after_start():
            checks.append(True)
            if len(checks) >= 8:
                raise RuntimeError("cancelled_for_test")

        with self.assertRaisesRegex(RuntimeError, "cancelled_for_test"):
            tif_part_extraction.interpolate_masks_from_keyframes(
                contours["keyframes"],
                (16, 32, 32),
                cancel_callback=cancel_after_start,
            )

    def test_contours_json_damage_and_invalid_keyframes_do_not_crash_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            contours_path = Path(tmp) / "contours.json"
            contours_path.write_text("{bad json", encoding="utf-8")

            contours = read_contours_json(contours_path)
            report = validate_contours_for_interpolation(
                {"axis": "z", "keyframes": ["bad", {"slice_index": "bad", "polygon": [[1, 1], [2, 1], [2, 2]]}]},
                (3, 4, 4),
            )

            self.assertEqual(contours["keyframes"], [])
            self.assertFalse(report["ok"])
            self.assertIn("invalid_slice_index", {item["code"] for item in report["warnings"]})
            self.assertIn("no_key_slices", {item["code"] for item in report["errors"]})

    def test_single_keyframe_preview_fills_only_the_key_slice(self):
        contours = {"axis": "z", "keyframes": []}
        contours = add_rectangular_keyframe(contours, 2, [[1, 4], [1, 4]])

        report = validate_contours_for_interpolation(contours, (5, 6, 6))
        mask = build_preview_mask_from_contours(contours, (5, 6, 6))

        self.assertTrue(report["ok"])
        self.assertIn("single_key_slice", {item["code"] for item in report["warnings"]})
        self.assertEqual(int(mask[0].sum()), 0)
        self.assertEqual(int(mask[1].sum()), 0)
        self.assertGreater(int(mask[2].sum()), 0)
        self.assertEqual(int(mask[3].sum()), 0)
        self.assertEqual(int(mask[4].sum()), 0)

    def test_crop_volume_to_part_validates_duplicate_before_touching_storage(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "duplicate_part"
            manager = TifProjectManager()
            manager.create_project("duplicate_part", project_root)
            manager.create_specimen_scaffold("01-0101-dup")
            image = np.arange(3 * 4 * 5, dtype=np.uint8).reshape((3, 4, 5))
            image_rel = "specimens/01-0101-dup/working/image.ome.zarr"
            image_meta = write_volume_sidecar(project_root / image_rel, image, role="working_image")
            manager.register_working_volume("01-0101-dup", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            manager.save_project()
            first = crop_volume_to_part(manager, "01-0101-dup", "head", [[0, 1], [0, 2], [0, 2]])
            marker = project_root / manager.part_dir("01-0101-dup", first["part_id"]) / "keep.txt"
            marker.write_text("do-not-touch", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "duplicate_part_id"):
                crop_volume_to_part(manager, "01-0101-dup", "head", [[1, 3], [1, 4], [1, 5]])

            self.assertEqual(marker.read_text(encoding="utf-8"), "do-not-touch")

    def test_crop_volume_to_part_refuses_non_empty_orphan_part_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "orphan_part"
            manager = TifProjectManager()
            manager.create_project("orphan_part", project_root)
            manager.create_specimen_scaffold("01-0101-orphan")
            image = np.arange(2 * 3 * 4, dtype=np.uint8).reshape((2, 3, 4))
            image_rel = "specimens/01-0101-orphan/working/image.ome.zarr"
            image_meta = write_volume_sidecar(project_root / image_rel, image, role="working_image")
            manager.register_working_volume("01-0101-orphan", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            manager.save_project()
            orphan_dir = project_root / manager.part_dir("01-0101-orphan", "head")
            orphan_dir.mkdir(parents=True)
            (orphan_dir / "leftover.txt").write_text("old local data", encoding="utf-8")

            with self.assertRaisesRegex(FileExistsError, "part_storage_dir_not_empty"):
                crop_volume_to_part(manager, "01-0101-orphan", "head", [[0, 1], [0, 2], [0, 2]])

            self.assertEqual(manager.list_parts("01-0101-orphan"), [])

    def test_local_axis_records_round_trip_under_specimen_and_part(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "local_axis_records"
            manager = TifProjectManager()
            project_json = manager.create_project("local_axis_records", project_root)
            manager.create_specimen_scaffold("01-0101-local")
            manager.add_part("01-0101-local", "head", parent_bbox_zyx=[[1, 5], [2, 6], [3, 7]], save=False)

            global_proposal = manager.add_global_axis_proposal(
                "01-0101-local",
                {
                    "global_proposal_id": "roi_001",
                    "template_id": "head",
                    "bbox_zyx": [1, 2, 3, 5, 6, 7],
                    "center_zyx": [3.0, 4.0, 5.0],
                    "confidence": 0.8,
                    "status": "proposed",
                },
                save=False,
            )
            frame_proposal = manager.add_local_frame_proposal(
                "01-0101-local",
                "head",
                {
                    "frame_proposal_id": "frame_001",
                    "template_id": "head",
                    "origin_zyx": [2.0, 2.0, 2.0],
                    "output_axis_start_zyx": [0.0, 2.0, 2.0],
                    "output_axis_end_zyx": [4.0, 2.0, 2.0],
                    "roll_reference": {
                        "point_a": {"role": "left_eye", "zyx": [2.0, 1.0, 1.0]},
                        "point_b": {"role": "right_eye", "zyx": [2.0, 3.0, 1.0]},
                    },
                    "confidence": 0.7,
                },
                save=False,
            )
            reslice = manager.add_part_reslice(
                "01-0101-local",
                "head",
                {
                    "reslice_id": "head_axis_001",
                    "template_id": "head",
                    "image_path": "specimens/01-0101-local/parts/head/reslices/head_axis_001/image.tif",
                    "metadata_path": "specimens/01-0101-local/parts/head/reslices/head_axis_001/metadata.json",
                    "local_frame": {
                        "origin_zyx": [2.0, 2.0, 2.0],
                        "x_axis": [0.0, 1.0, 0.0],
                        "y_axis": [0.0, 0.0, 1.0],
                        "z_axis": [1.0, 0.0, 0.0],
                        "output_axis": "z_axis",
                        "spacing_zyx": [2.0, 1.0, 1.0],
                        "coordinate_space": "part_volume_voxel_zyx",
                        "reference_plane": {
                            "plane_id": "three_point_reference_plane",
                            "normal_axis_zyx": [1.0, 0.0, 0.0],
                            "point_c_zyx": [2.0, 2.0, 3.0],
                        },
                    },
                    "training": {"human_confirmed": True, "usable_for_training": True},
                    "training_sample": {
                        "schema_version": "taxamask_tif_local_axis_training_sample_v1",
                        "sample_id": "01-0101-local:head:head_axis_001",
                        "specimen_id": "01-0101-local",
                        "part_id": "head",
                        "reslice_id": "head_axis_001",
                        "template_id": "head",
                        "source_axis": {"axis_id": "source_z_axis", "locked": True},
                        "initial_editable_axis": {"axis_id": "local_output_z_axis", "start_zyx": [0.0, 2.0, 2.0]},
                        "final_editable_axis": {"axis_id": "local_output_z_axis", "end_zyx": [4.0, 2.0, 2.0]},
                        "origin_zyx": [2.0, 2.0, 2.0],
                        "roll_reference_point_pair": {
                            "point_a": {"role": "left_eye", "zyx": [2.0, 1.0, 1.0]},
                            "point_b": {"role": "right_eye", "zyx": [2.0, 3.0, 1.0]},
                        },
                        "human_confirmed": True,
                        "usable_for_training": True,
                    },
                },
                save=False,
            )
            model = manager.register_local_axis_model(
                {
                    "model_id": "local_axis/head_frame_v1",
                    "template_id": "head",
                    "model_type": "local_frame",
                    "backend_type": "external_local_axis",
                    "model_manifest": "models/head_frame_v1/manifest.json",
                },
                save=False,
            )
            run = manager.add_local_axis_run(
                {
                    "run_id": "predict_001",
                    "action": "predict_local_frame",
                    "model_id": model["model_id"],
                    "specimen_ids": ["01-0101-local"],
                    "part_ids": ["head"],
                    "result_status": "success",
                },
                save=True,
            )

            reloaded = TifProjectManager()
            reloaded.load_project(project_json)

            self.assertEqual(global_proposal["bbox_zyx"], [[1, 5], [2, 6], [3, 7]])
            self.assertEqual(reloaded.list_global_axis_proposals("01-0101-local")[0]["global_proposal_id"], "roi_001")
            self.assertEqual(frame_proposal["status"], "proposed")
            self.assertEqual(reloaded.list_local_frame_proposals("01-0101-local", "head")[0]["frame_proposal_id"], "frame_001")
            self.assertEqual(reslice["training"]["human_confirmed"], True)
            reloaded_reslice = reloaded.list_part_reslices("01-0101-local", "head")[0]
            self.assertEqual(reloaded_reslice["reslice_id"], "head_axis_001")
            self.assertEqual(reloaded_reslice["local_frame"]["spacing_zyx"], [2.0, 1.0, 1.0])
            self.assertEqual(reloaded_reslice["local_frame"]["coordinate_space"], "part_volume_voxel_zyx")
            self.assertEqual(reloaded_reslice["local_frame"]["reference_plane"]["plane_id"], "three_point_reference_plane")
            self.assertEqual(reloaded_reslice["training_sample"]["sample_id"], "01-0101-local:head:head_axis_001")
            self.assertEqual(reloaded_reslice["training_sample"]["final_editable_axis"]["end_zyx"], [4.0, 2.0, 2.0])
            self.assertEqual(run["workflow"], "tif_local_axis")
            self.assertEqual(reloaded.project_data["models"][0]["model_id"], "local_axis/head_frame_v1")
            self.assertEqual(reloaded.project_data["runs"][0]["run_id"], "predict_001")
            self.assertEqual(reloaded.list_local_axis_models()[0]["model_id"], "local_axis/head_frame_v1")
            self.assertEqual(reloaded.get_local_axis_model("local_axis/head_frame_v1")["model_type"], "local_frame")
            self.assertEqual(reloaded.list_local_axis_runs()[0]["run_id"], "predict_001")
            self.assertEqual(reloaded.get_local_axis_run("predict_001")["action"], "predict_local_frame")

    def test_non_local_axis_models_and_runs_survive_project_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "legacy_backend_records"
            manager = TifProjectManager()
            project_json = manager.create_project("legacy_backend_records", project_root)
            manager.project_data["models"].append(
                {
                    "model_manifest": "runs/train/model_manifest.json",
                    "backend_id": "nnunet_backend",
                    "run_id": "train_001",
                    "input_contract": {"image": "volume"},
                    "output_contract": {"prediction": "mask"},
                }
            )
            manager.project_data["runs"].append(
                {
                    "run_id": "train_001",
                    "action": "train",
                    "backend_id": "nnunet_backend",
                    "run_dir": "runs/train/train_001",
                    "result_status": "success",
                }
            )
            manager.save_project()

            reloaded = TifProjectManager()
            reloaded.load_project(project_json)

            self.assertEqual(reloaded.project_data["models"][0].get("profile_scope", ""), "")
            self.assertEqual(reloaded.project_data["models"][0]["backend_id"], "nnunet_backend")
            self.assertEqual(reloaded.project_data["runs"][0].get("workflow", ""), "")
            self.assertEqual(reloaded.project_data["runs"][0]["action"], "train")
            self.assertEqual(reloaded.list_local_axis_models(), [])
            self.assertEqual(reloaded.list_local_axis_runs(), [])

    def test_tif_segmentation_models_round_trip_notes_and_delete_registration(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "tif_segmentation_models"
            manager = TifProjectManager()
            project_json = manager.create_project("tif_segmentation_models", project_root)
            output_dir = project_root / "runs" / "train" / "outputs"
            output_dir.mkdir(parents=True)
            checkpoint = output_dir / "checkpoint_final.pth"
            checkpoint.write_bytes(b"fake weights")
            manifest_path = output_dir / "model_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": "ant3d_tif_model_manifest_v1",
                        "model_id": "taxamask_tif_nnunet_v2_backend/train_001",
                        "backend_id": "taxamask_tif_nnunet_v2_backend",
                        "model_family": "nnunet_v2_tif_region",
                        "created_at": "2026-07-07T12:00:00+08:00",
                        "trained_specimens": ["s1", "s2"],
                        "trained_parts": [
                            {"specimen_id": "s1", "part_id": "head", "reslice_id": "axis_1"},
                            {"specimen_id": "s2", "part_id": "head", "reslice_id": "axis_1"},
                        ],
                        "input_scope": "part_reslice",
                        "label_schema_ids": ["head_regions"],
                        "nnunet": {
                            "model_output_dir": str(output_dir),
                            "checkpoint_path": str(checkpoint),
                        },
                        "usable_for_research_prediction": True,
                    }
                ),
                encoding="utf-8",
            )

            model = manager.register_tif_segmentation_model_from_manifest(
                manifest_path,
                {"run_id": "train_001", "training_samples": 2, "notes": "first accepted model"},
                save=True,
            )
            manager.register_tif_segmentation_model_from_manifest(
                manager.to_relative(manifest_path),
                {"run_id": "train_001", "training_samples": 2},
                save=True,
            )

            reloaded = TifProjectManager()
            reloaded.load_project(project_json)
            records = reloaded.list_tif_segmentation_models()
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["model_id"], model["model_id"])
            self.assertEqual(records[0]["training_samples"], 2)
            self.assertEqual(records[0]["notes"], "first accepted model")
            self.assertEqual(reloaded.to_absolute(records[0]["model_manifest"]), str(manifest_path))
            self.assertEqual(reloaded.list_local_axis_models(), [])

            reloaded.update_tif_segmentation_model_notes(model["model_id"], "use for July batch", save=True)
            reloaded_again = TifProjectManager()
            reloaded_again.load_project(project_json)
            self.assertEqual(reloaded_again.get_tif_segmentation_model(model["model_id"])["notes"], "use for July batch")

            removed = reloaded_again.delete_tif_segmentation_model(model["model_id"], save=True)
            self.assertIsNotNone(removed)
            self.assertTrue(manifest_path.exists())
            final = TifProjectManager()
            final.load_project(project_json)
            self.assertEqual(final.list_tif_segmentation_models(), [])

    def test_part_training_labels_schema_and_user_tags_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "part_training_roundtrip"
            manager = TifProjectManager()
            project_json = manager.create_project("part_training_roundtrip", project_root)
            manager.create_specimen_scaffold("01-0101-brain")
            part_image_rel = "specimens/01-0101-brain/parts/brain/image.ome.zarr"
            part_mask_rel = "specimens/01-0101-brain/parts/brain/mask.ome.zarr"
            part_manual_rel = "specimens/01-0101-brain/parts/brain/labels/manual_truth.ome.zarr"
            image_meta = write_volume_sidecar(project_root / part_image_rel, np.zeros((2, 3, 4), dtype=np.uint8), role="part_image")
            mask_meta = write_volume_sidecar(project_root / part_mask_rel, np.zeros((2, 3, 4), dtype=np.uint16), role="part_mask")
            manual_meta = write_volume_sidecar(project_root / part_manual_rel, np.ones((2, 3, 4), dtype=np.uint16), role="manual_truth")
            manager.add_part(
                "01-0101-brain",
                "brain",
                image={"path": part_image_rel, **image_meta},
                mask={"path": part_mask_rel, **mask_meta},
                save=False,
            )
            manager.add_or_update_label_schema(
                "brain_regions",
                labels=[
                    {"id": 1, "name": "mushroom_body", "color": "#ff0000"},
                    {"id": 2, "name": "antennal_lobe", "color": "#00ff00"},
                ],
                user_defined_part_name="brain",
                save=False,
            )
            manager.upsert_part_user_tag("round_1", "Round 1", order_index=0, save=False)
            manager.set_part_user_tags("01-0101-brain", "brain", ["round_1"], save=False)
            manager.register_part_label_volume(
                "01-0101-brain",
                "brain",
                "manual_truth",
                part_manual_rel,
                manual_meta["shape_zyx"],
                manual_meta["dtype"],
                status="reviewed",
                save=False,
            )
            manager.set_part_training_metadata(
                "01-0101-brain",
                "brain",
                user_defined_part_name="brain",
                label_schema_id="brain_regions",
                system_status="verified_train_ready",
                save=True,
            )

            reloaded = TifProjectManager()
            reloaded.load_project(project_json)
            part = reloaded.get_part("01-0101-brain", "brain")

            self.assertEqual(reloaded.get_label_schema("brain_regions")["labels"][0]["name"], "mushroom_body")
            self.assertEqual(reloaded.project_data["part_user_tags"][0]["tag_id"], "round_1")
            self.assertEqual(part["user_tags"], ["round_1"])
            self.assertEqual(part["training"]["label_schema_id"], "brain_regions")
            self.assertEqual(part["labels"]["manual_truth"]["path"], part_manual_rel)
            self.assertTrue(reloaded.validate_part_label_ids("01-0101-brain", "brain")["ok"])

    def test_label_schema_export_import_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = TifProjectManager()
            source.create_project("schema_source", root / "source")
            source.add_or_update_label_schema(
                "brain_regions",
                labels=[
                    {"id": 1, "name": "mushroom_body", "display_name": "Mushroom body", "color": "#ff0000"},
                    {"id": 2, "name": "antennal_lobe", "display_name": "Antennal lobe", "color": "#00ff00"},
                    {"id": 2, "name": "duplicate_should_drop", "color": "#0000ff"},
                ],
                user_defined_part_name="brain",
                save=True,
            )
            export_path = root / "brain_regions.schema.json"

            payload = source.export_label_schema("brain_regions", export_path)

            self.assertTrue(export_path.exists())
            self.assertEqual(payload["schema_version"], "taxamask_tif_label_schema_v1")
            self.assertEqual(payload["label_schema"]["schema_id"], "brain_regions")
            self.assertEqual([item["id"] for item in payload["label_schema"]["labels"]], [1, 2])

            target = TifProjectManager()
            target.create_project("schema_target", root / "target")
            imported = target.import_label_schema(export_path)

            self.assertEqual(imported["schema_id"], "brain_regions")
            self.assertEqual(imported["user_defined_part_name"], "brain")
            self.assertEqual(target.get_label_schema("brain_regions")["labels"][1]["name"], "antennal_lobe")

            raw_export = root / "raw_schema.json"
            raw_export.write_text(
                json.dumps(
                    {
                        "schema_id": "brain_regions",
                        "labels": [{"id": 3, "name": "central_complex", "color": "#123456"}],
                        "user_defined_part_name": "brain",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with self.assertRaises(FileExistsError):
                target.import_label_schema(raw_export, replace=False)
            replaced = target.import_label_schema(raw_export, replace=True)
            self.assertEqual([item["id"] for item in replaced["labels"]], [3])

            empty_export = root / "empty_schema.json"
            empty_export.write_text(json.dumps({"schema_id": "empty", "labels": []}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "label_schema_empty"):
                target.import_label_schema(empty_export)

    def test_part_user_tags_reorder_and_delete_do_not_override_system_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "part_tags"
            manager = TifProjectManager()
            manager.create_project("part_tags", project_root)
            manager.create_specimen_scaffold("01-0101-tags")
            manager.add_part("01-0101-tags", "brain", save=False)
            manager.set_part_training_metadata(
                "01-0101-tags",
                "brain",
                system_status="predicted_pending_review",
                save=False,
            )
            manager.upsert_part_user_tag("candidate", "Candidate", order_index=0, save=False)
            manager.upsert_part_user_tag("paper_fig", "Paper figure", order_index=1, save=False)
            manager.set_part_user_tags("01-0101-tags", "brain", ["candidate", "paper_fig"], save=False)
            manager.set_part_user_tag_order(["paper_fig", "candidate"], save=False)
            manager.delete_part_user_tag("candidate", save=True)

            part = manager.get_part("01-0101-tags", "brain")
            tags = manager.project_data["part_user_tags"]
            self.assertEqual([tag["tag_id"] for tag in tags], ["paper_fig"])
            self.assertEqual(tags[0]["order_index"], 0)
            self.assertEqual(part["user_tags"], ["paper_fig"])
            self.assertEqual(part["training"]["system_status"], "predicted_pending_review")

    def test_reviewed_part_editable_result_batch_promotes_to_manual_truth(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "part_review_batch"
            manager = TifProjectManager()
            manager.create_project("part_review_batch", project_root)
            manager.create_specimen_scaffold("01-0101-review")
            part_image_rel = "specimens/01-0101-review/parts/brain/image.ome.zarr"
            reslice_rel = "specimens/01-0101-review/parts/brain/reslices/brain_axis_001/image.tif"
            edit_rel = "specimens/01-0101-review/parts/brain/reslices/brain_axis_001/labels/editable_ai_result.ome.zarr"
            image_meta = write_volume_sidecar(project_root / part_image_rel, np.zeros((2, 3, 4), dtype=np.uint8), role="part_image")
            (project_root / reslice_rel).parent.mkdir(parents=True, exist_ok=True)
            tifffile.imwrite(project_root / reslice_rel, np.zeros((2, 3, 4), dtype=np.uint8))
            edit_array = np.ones((2, 3, 4), dtype=np.uint16)
            edit_array[0, 0, 0] = 2
            edit_meta = write_volume_sidecar(project_root / edit_rel, edit_array, role="editable_ai_result")
            manager.add_part(
                "01-0101-review",
                "brain",
                image={"path": part_image_rel, **image_meta},
                save=False,
            )
            manager.add_or_update_label_schema(
                "brain_regions",
                labels=[
                    {"id": 1, "name": "mushroom_body", "color": "#ff0000"},
                    {"id": 2, "name": "antennal_lobe", "color": "#00ff00"},
                ],
                user_defined_part_name="brain",
                save=False,
            )
            manager.add_part_reslice(
                "01-0101-review",
                "brain",
                {"reslice_id": "brain_axis_001", "image_path": reslice_rel, "status": "exported"},
                save=False,
            )
            manager.register_part_reslice_label_volume(
                "01-0101-review",
                "brain",
                "brain_axis_001",
                "editable_ai_result",
                edit_rel,
                edit_meta["shape_zyx"],
                edit_meta["dtype"],
                status="pending_review",
                save=False,
            )
            manager.set_part_training_metadata(
                "01-0101-review",
                "brain",
                label_schema_id="brain_regions",
                active_reslice_id="brain_axis_001",
                opened_for_review=False,
                save=True,
            )

            report = manager.evaluate_part_editable_result_review_ready("01-0101-review", "brain", "brain_axis_001")
            self.assertTrue(report["review_ready"])
            self.assertEqual(report["reslice_id"], "brain_axis_001")
            self.assertFalse(report["opened_for_review"])
            self.assertIn("editable_ai_result_not_opened_for_review", report["reasons"])
            self.assertEqual(report["label_schema_id"], "brain_regions")
            self.assertEqual(report["label_ids"], [1, 2])
            with patch.object(manager, "validate_part_label_ids", side_effect=AssertionError("label scan should be deferred")):
                deferred_report = manager.evaluate_part_editable_result_review_ready(
                    "01-0101-review",
                    "brain",
                    "brain_axis_001",
                    validate_label_ids=False,
                )
            self.assertTrue(deferred_report["review_ready"])
            self.assertFalse(deferred_report["label_ids_checked"])
            self.assertEqual(deferred_report["label_report"]["skipped"], "label_id_scan_deferred")
            acceptance = manager.build_part_review_acceptance_report(
                [{"specimen_id": "01-0101-review", "part_id": "brain", "reslice_id": "brain_axis_001"}],
                require_opened_for_review=False,
            )
            self.assertEqual(acceptance["ready_count"], 1)
            self.assertEqual(acceptance["not_opened_count"], 1)
            self.assertEqual(acceptance["blocked_count"], 0)
            blocked_acceptance = manager.build_part_review_acceptance_report(
                [{"specimen_id": "01-0101-review", "part_id": "brain", "reslice_id": "brain_axis_001"}],
                require_opened_for_review=True,
            )
            self.assertEqual(blocked_acceptance["ready_count"], 0)
            self.assertEqual(blocked_acceptance["blocked_count"], 1)
            with self.assertRaisesRegex(ValueError, "part_review_not_ready"):
                manager.promote_reviewed_part_results_to_manual_truth(
                    [{"specimen_id": "01-0101-review", "part_id": "brain", "reslice_id": "brain_axis_001"}],
                    require_opened_for_review=True,
                )

            result = manager.promote_reviewed_part_results_to_manual_truth(
                [{"specimen_id": "01-0101-review", "part_id": "brain", "reslice_id": "brain_axis_001"}],
                require_opened_for_review=False,
            )
            part = manager.get_part("01-0101-review", "brain")
            reslice = manager.get_part_reslice("01-0101-review", "brain", "brain_axis_001")
            self.assertEqual(result["count"], 1)
            self.assertFalse((part["labels"]["manual_truth"] or {}).get("path"))
            self.assertEqual(reslice["labels"]["manual_truth"]["status"], "reviewed")
            self.assertEqual(part["training"]["system_status"], "verified_train_ready")
            self.assertTrue(manager.evaluate_part_train_ready("01-0101-review", "brain")["train_ready"])
            np.testing.assert_array_equal(load_volume_sidecar(project_root / reslice["labels"]["manual_truth"]["path"]), edit_array)

    def test_reslice_shape_check_uses_tif_metadata_without_full_read_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "reslice_shape_metadata"
            manager = TifProjectManager()
            manager.create_project("reslice_shape_metadata", project_root)
            manager.create_specimen_scaffold("01-0101-shape")
            part_image_rel = "specimens/01-0101-shape/parts/head/image.ome.zarr"
            part_meta = write_volume_sidecar(project_root / part_image_rel, np.zeros((2, 3, 4), dtype=np.uint8), role="part_image")
            manager.add_part("01-0101-shape", "head", image={"path": part_image_rel, **part_meta}, save=False)
            manager.add_or_update_label_schema("head_regions", labels=[{"id": 1, "name": "label_1"}], save=False)
            reslice_rel = "specimens/01-0101-shape/parts/head/reslices/compressed_axis/image.tif"
            reslice_abs = project_root / reslice_rel
            reslice_abs.parent.mkdir(parents=True, exist_ok=True)
            tifffile.imwrite(reslice_abs, np.zeros((2, 4, 5), dtype=np.uint8), compression="deflate")
            manager.add_part_reslice(
                "01-0101-shape",
                "head",
                {"reslice_id": "compressed_axis", "image_path": reslice_rel, "status": "exported"},
                save=False,
            )
            manager.set_part_training_metadata(
                "01-0101-shape",
                "head",
                label_schema_id="head_regions",
                active_reslice_id="compressed_axis",
                save=True,
            )

            with patch("tifffile.imread", side_effect=AssertionError("full TIF read should be avoided")):
                report = manager.evaluate_part_predict_ready("01-0101-shape", "head", "compressed_axis")

            self.assertTrue(report["predict_ready"])
            self.assertEqual(report["input_shape_zyx"], [2, 4, 5])

    def test_reviewed_part_editable_result_rejects_unknown_label_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "part_review_unknown_label"
            manager = TifProjectManager()
            manager.create_project("part_review_unknown_label", project_root)
            manager.create_specimen_scaffold("01-0101-review")
            part_image_rel = "specimens/01-0101-review/parts/brain/image.ome.zarr"
            edit_rel = "specimens/01-0101-review/parts/brain/labels/editable_ai_result.ome.zarr"
            image_meta = write_volume_sidecar(project_root / part_image_rel, np.zeros((2, 3, 4), dtype=np.uint8), role="part_image")
            edit_meta = write_volume_sidecar(project_root / edit_rel, np.full((2, 3, 4), 9, dtype=np.uint16), role="editable_ai_result")
            manager.add_part("01-0101-review", "brain", image={"path": part_image_rel, **image_meta}, save=False)
            manager.add_or_update_label_schema(
                "brain_regions",
                labels=[{"id": 1, "name": "mushroom_body", "color": "#ff0000"}],
                save=False,
            )
            manager.register_part_label_volume(
                "01-0101-review",
                "brain",
                "editable_ai_result",
                edit_rel,
                edit_meta["shape_zyx"],
                edit_meta["dtype"],
                save=False,
            )
            manager.set_part_training_metadata(
                "01-0101-review",
                "brain",
                label_schema_id="brain_regions",
                opened_for_review=True,
                save=True,
            )

            report = manager.evaluate_part_editable_result_review_ready("01-0101-review", "brain")
            self.assertFalse(report["review_ready"])
            self.assertIn("unknown_label_ids", report["reasons"])
            self.assertEqual(report["label_report"]["unknown_label_ids"], [9])
            self.assertEqual(report["unknown_label_ids"], [9])
            acceptance = manager.build_part_review_acceptance_report(
                [{"specimen_id": "01-0101-review", "part_id": "brain"}],
                require_opened_for_review=False,
            )
            self.assertEqual(acceptance["ready_count"], 0)
            self.assertEqual(acceptance["blocked_count"], 1)
            self.assertEqual(acceptance["blocked"][0]["report"]["unknown_label_ids"], [9])
            with self.assertRaisesRegex(ValueError, "part_review_not_ready"):
                manager.promote_reviewed_part_results_to_manual_truth(
                    [{"specimen_id": "01-0101-review", "part_id": "brain"}],
                    require_opened_for_review=False,
                )


if __name__ == "__main__":
    unittest.main()
