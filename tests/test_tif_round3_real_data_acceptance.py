import hashlib
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import tifffile

try:
    from PySide6.QtWidgets import QApplication
except ModuleNotFoundError as exc:
    if exc.name and exc.name.startswith("PySide6"):
        QApplication = None
    else:
        raise
else:
    from AntSleap.core.tif_materials import read_material_map, upsert_material
    from AntSleap.core.tif_prediction_import import import_external_prediction_tif
    from AntSleap.core.tif_project import TifProjectManager
    from AntSleap.core.tif_volume_io import load_volume_sidecar, write_volume_sidecar
    from AntSleap.services.tif_truth_promotion_service import TifTruthPromotionService
    from AntSleap.ui.tif_workbench import TifWorkbenchWidget
    from AntSleap.ui.tif_workbench_workers import TifConfirmPartRoiWorker, _tif_write_label_slice_snapshots


REAL_TIF_FIXTURE = os.environ.get("TAXAMASK_REAL_TIF_FIXTURE", "").strip()


def _fixture_available():
    return bool(REAL_TIF_FIXTURE) and Path(REAL_TIF_FIXTURE).is_dir()


def _tree_hash(path):
    digest = hashlib.sha256()
    for file_path in sorted(Path(path).rglob("*")):
        if not file_path.is_file():
            continue
        digest.update(file_path.relative_to(path).as_posix().encode("utf-8"))
        with file_path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
    return digest.hexdigest()


@unittest.skipUnless(QApplication is not None, "PySide6 is required for real TIF acceptance")
@unittest.skipUnless(_fixture_available(), "Set TAXAMASK_REAL_TIF_FIXTURE to a real read-only volume sidecar")
class TifRound3RealDataAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _wait_for_local_axis_export(self, widget, timeout_ms=30000):
        deadline = datetime.now().timestamp() + float(timeout_ms) / 1000.0
        while widget.local_axis_controller.export_running():
            self.app.processEvents()
            if datetime.now().timestamp() > deadline:
                raise AssertionError("Timed out waiting for real-data Local Axis export")
        self.app.processEvents()

    def test_isolated_real_ant_volume_workflow_preserves_source(self):
        source_path = Path(REAL_TIF_FIXTURE).resolve()
        source_hash_before = _tree_hash(source_path)
        source_volume = load_volume_sidecar(source_path, mmap_mode="r")
        real_volume = np.asarray(source_volume).copy()
        mmap_handle = getattr(source_volume, "_mmap", None)
        if mmap_handle is not None:
            mmap_handle.close()

        self.assertEqual(real_volume.ndim, 3)
        self.assertGreater(int(real_volume.size), 0)
        self.assertGreater(int(real_volume.max()), int(real_volume.min()))

        with tempfile.TemporaryDirectory(dir=Path.cwd() / ".tmp_validation") as tmp:
            project_root = Path(tmp).resolve() / "real_tif_round3_acceptance"
            manager = TifProjectManager()
            manifest_path = Path(manager.create_project("real_tif_round3_acceptance", project_root))
            manager.create_specimen_scaffold(
                "real-ant",
                modality="micro_ct",
                material_map={
                    "materials": [
                        {"id": 0, "name": "background", "display_name": "Background", "trainable": False},
                        {"id": 2, "name": "test_region", "display_name": "Test region", "color": "#ff0000", "trainable": True},
                    ]
                },
            )
            image_rel = "specimens/real-ant/working/image.ome.zarr"
            edit_rel = "specimens/real-ant/labels/working_edit.ome.zarr"
            image_meta = write_volume_sidecar(project_root / image_rel, real_volume, role="working_image")
            edit_meta = write_volume_sidecar(project_root / edit_rel, np.zeros(real_volume.shape, dtype=np.uint16), role="working_edit")
            manager.register_working_volume("real-ant", image_rel, image_meta["shape_zyx"], image_meta["dtype"], save=False)
            manager.register_label_volume("real-ant", "working_edit", edit_rel, edit_meta["shape_zyx"], edit_meta["dtype"], save=False)
            manager.create_specimen_scaffold("real-ant-2", modality="micro_ct")
            image_rel_2 = "specimens/real-ant-2/working/image.ome.zarr"
            edit_rel_2 = "specimens/real-ant-2/labels/working_edit.ome.zarr"
            image_meta_2 = write_volume_sidecar(project_root / image_rel_2, np.flip(real_volume, axis=2).copy(), role="working_image")
            edit_meta_2 = write_volume_sidecar(project_root / edit_rel_2, np.zeros(real_volume.shape, dtype=np.uint16), role="working_edit")
            manager.register_working_volume("real-ant-2", image_rel_2, image_meta_2["shape_zyx"], image_meta_2["dtype"], save=False)
            manager.register_label_volume("real-ant-2", "working_edit", edit_rel_2, edit_meta_2["shape_zyx"], edit_meta_2["dtype"], save=False)
            manager.save_project()

            widget = TifWorkbenchWidget(manager, "en")
            widget.resize(1000, 700)
            widget.canvas.resize(600, 420)
            try:
                widget.load_specimen("real-ant")
                self.assertEqual(tuple(widget.image_volume.shape), tuple(real_volume.shape))
                self.assertEqual(int(widget.image_volume.max()), int(real_volume.max()))
                widget.selection_workflow_controller.select_payload({"scope": "full", "specimen_id": "real-ant-2"})
                self.assertEqual(widget.current_specimen_id, "real-ant-2")
                self.assertEqual(int(widget.image_volume[0, 0, 0]), int(real_volume[0, 0, -1]))
                widget.display_mode = "volume"
                widget.selection_workflow_controller.select_payload({"scope": "full", "specimen_id": "real-ant"})
                self.app.processEvents()
                stale_request = widget.volume_render_controller._volume_preview_request("still")
                cached_before = np.asarray(widget.volume_render_controller.state.volume_preview_cache[stale_request["cache_key"]]).copy()
                stale_task = widget._start_tif_task(
                    "volume_preview",
                    action="build_preview",
                    request_key=widget._task_request_key(stale_request["cache_key"]),
                    message="Preparing real-data preview",
                )
                widget.volume_render_controller.state.volume_preview_build_task_id = stale_task.task_id
                widget.volume_render_controller.state.volume_preview_pending_token = 17
                widget.volume_render_controller.state.volume_preview_pending_key = stale_request["cache_key"]
                widget.volume_render_controller.state.volume_preview_pending_mask_key = None
                widget.selection_workflow_controller.select_payload({"scope": "full", "specimen_id": "real-ant-2"})
                widget.volume_render_controller._on_volume_preview_build_finished({
                    "token": 17,
                    "volume_request": stale_request,
                    "preview": np.ones(real_volume.shape, dtype=np.uint8),
                })
                self.assertEqual(widget.task_manager.task(stale_task.task_id).status, "cancelled")
                cached_after = np.asarray(widget.volume_render_controller.state.volume_preview_cache[stale_request["cache_key"]])
                np.testing.assert_array_equal(cached_after, cached_before)
                self.assertEqual(widget.current_specimen_id, "real-ant-2")
                widget.selection_workflow_controller.select_payload({"scope": "full", "specimen_id": "real-ant"})
                self.assertEqual(widget.current_specimen_id, "real-ant")
                widget.display_mode_combo.setCurrentIndex(widget.display_mode_combo.findData("slice"))
                widget.on_display_mode_changed()
                edit_index = widget.label_role_combo.findData("working_edit")
                self.assertGreaterEqual(edit_index, 0)
                widget.label_role_combo.setCurrentIndex(edit_index)
                widget.part_mask_workflow_controller._set_current_material_id(2)
                widget.edit_volume[0, 2:5, 2:5] = 2
                widget.annotation_workflow_controller.mark_slice_dirty(0)
                widget.annotation_workflow_controller.mark_working_edit_dirty()
                auto_request = widget.annotation_workflow_controller.snapshot_save_request(reason="auto_save")
                self.assertIsNotNone(auto_request)
                saved_revision = int(auto_request["slice_revisions"][0])
                widget.edit_volume[0, 0, 0] = 2
                widget.annotation_workflow_controller.mark_slice_dirty(0)
                auto_result = _tif_write_label_slice_snapshots(
                    auto_request["token"],
                    auto_request["edit_path"],
                    auto_request["slices"],
                    auto_request["slice_revisions"],
                )
                widget.annotation_workflow_controller.on_auto_save_finished(auto_result)
                self.assertTrue(widget.working_edit_dirty)
                self.assertIn(0, widget.annotation_workflow_controller.state.dirty_slices)
                self.assertGreater(widget.annotation_workflow_controller.state.slice_revisions[0], saved_revision)
                auto_saved = np.asarray(load_volume_sidecar(project_root / edit_rel, mmap_mode="r")).copy()
                self.assertEqual(int(auto_saved[0, 0, 0]), 0)
                self.assertTrue(widget.save_working_edit(show_message=False))
                final_saved = np.asarray(load_volume_sidecar(project_root / edit_rel, mmap_mode="r")).copy()
                self.assertEqual(int(final_saved[0, 0, 0]), 2)
                widget.part_mask_workflow_controller.state.material_map = upsert_material(
                    widget.part_mask_workflow_controller.state.material_map,
                    {"id": 3, "name": "real_test_material", "display_name": "Real test material", "color": "#00ff00", "trainable": True},
                )
                widget.part_mask_workflow_controller._save_material_map()
                widget.edit_volume[1, 3:6, 3:6] = 3
                widget.annotation_workflow_controller.mark_slice_dirty(1)
                widget.edit_volume[min(2, int(widget.edit_volume.shape[0]) - 1), 4:7, 4:7] = 3
                widget.annotation_workflow_controller.mark_slice_dirty(min(2, int(widget.edit_volume.shape[0]) - 1))
                widget.annotation_workflow_controller.mark_working_edit_dirty()
                self.assertTrue(widget.save_working_edit(show_message=False))
                material_map_path = widget.project.to_absolute(widget.project.get_specimen("real-ant")["material_map"])
                saved_materials = read_material_map(material_map_path)
                self.assertIn(3, [int(item["id"]) for item in saved_materials["materials"]])
                material_saved_volume = np.asarray(load_volume_sidecar(project_root / edit_rel, mmap_mode="r")).copy()
                self.assertGreaterEqual(int(np.count_nonzero(material_saved_volume == 3)), 18)

                z_count, height, width = [int(value) for value in real_volume.shape]
                z0 = max(0, min(z_count - 1, z_count // 4))
                z1 = max(z0 + 1, min(z_count, z_count - z_count // 4))
                y0 = max(1, height // 5)
                y1 = max(y0 + 4, height - height // 5)
                x0 = max(1, width // 5)
                x1 = max(x0 + 4, width - width // 5)
                widget.part_bbox_edit.setText(f"{z0},{z1},{y0},{y1},{x0},{x1}")

                key_z0 = z0
                key_z1 = z1 - 1
                inset_x = max(1, (x1 - x0) // 6)
                inset_y = max(1, (y1 - y0) // 6)
                polygon = [
                    [x0 + inset_x, y0 + inset_y],
                    [x1 - inset_x, y0 + inset_y],
                    [x1 - inset_x, y1 - inset_y],
                    [x0 + inset_x, y1 - inset_y],
                ]
                widget.part_mask_workflow_controller.state.keyframes = [
                    {"axis": "z", "slice_index": key_z0, "polygon": polygon, "source": "manual_freehand"},
                    {"axis": "z", "slice_index": key_z1, "polygon": polygon, "source": "manual_freehand"},
                ]
                widget.part_mask_workflow_controller.preview_part_mask_from_keyframes()
                self.assertIsNotNone(widget.part_preview_mask)
                first_preview = np.asarray(widget.part_preview_mask).copy()
                self.assertGreater(int(np.count_nonzero(first_preview)), 0)
                widget.part_mask_workflow_controller.clear_part_mask_preview()
                self.assertIsNone(widget.part_preview_mask)
                self.assertFalse(widget.part_mask_preview_accepted)
                inset_polygon = [
                    [polygon[0][0] + 1, polygon[0][1] + 1],
                    [polygon[1][0] - 1, polygon[1][1] + 1],
                    [polygon[2][0] - 1, polygon[2][1] - 1],
                    [polygon[3][0] + 1, polygon[3][1] - 1],
                ]
                widget.part_mask_workflow_controller.state.keyframes[1]["polygon"] = inset_polygon
                widget.part_mask_workflow_controller.preview_part_mask_from_keyframes()
                self.assertIsNotNone(widget.part_preview_mask)
                self.assertFalse(np.array_equal(first_preview, np.asarray(widget.part_preview_mask)))
                widget.part_mask_workflow_controller.accept_part_mask_preview()
                self.assertTrue(widget.part_mask_preview_accepted)

                request = widget.roi_workflow_controller.build_confirm_request(
                    None,
                    widget.part_mask_preview_bbox,
                    "real_part",
                    "Real ant part",
                    [],
                    widget._full_volume_contours_payload(),
                    widget.part_mask_preview_bbox,
                )
                worker = TifConfirmPartRoiWorker(widget.project, request)
                finished = []
                failed = []
                worker.finished.connect(lambda result: finished.append(result))
                worker.failed.connect(lambda result: failed.append(result))
                worker.run()
                self.assertEqual(failed, [])
                self.assertEqual(len(finished), 1)
                widget.roi_workflow_controller.finish_confirm_result(finished[0])

                self.assertEqual(widget.current_volume_scope, "part")
                self.assertEqual(widget.current_part_id, "real_part")
                widget.display_mode_combo.setCurrentIndex(widget.display_mode_combo.findData("slice"))
                widget.on_display_mode_changed()
                part = widget.project.get_part("real-ant", "real_part")
                part_mask_before = np.asarray(load_volume_sidecar(widget.project.to_absolute(part["mask"]["path"]), mmap_mode="r")).copy()
                self.assertGreater(int(np.count_nonzero(part_mask_before)), 0)

                widget.part_mask_workflow_controller._set_current_material_id(2)
                widget.slice_slider.setValue(0)
                widget.render_current_slice()
                point_a = widget.canvas._image_point_to_widget_point([2.5, 2.5])
                point_b = widget.canvas._image_point_to_widget_point([
                    float(min(int(widget.image_volume.shape[2]) - 2, 8)) + 0.5,
                    float(min(int(widget.image_volume.shape[1]) - 2, 8)) + 0.5,
                ])
                self.assertIsNotNone(point_a)
                self.assertIsNotNone(point_b)
                fill_result = widget.annotation_workflow_controller.finish_shape_fill_drag("rectangle", point_a[0], point_a[1], point_b[0], point_b[1])
                self.assertTrue(
                    fill_result,
                    f"scope={widget.current_volume_scope} mode={widget.display_mode} axis={widget.slice_axis_combo.currentData()} role={widget.label_role_combo.currentData()} status={widget.operation_status_label.text()}",
                )
                self.assertTrue(widget.save_working_edit(show_message=False))
                editable = widget.project.part_label_record("real-ant", "real_part", "editable_ai_result")
                self.assertIn("editable_ai_result.ome.zarr", editable["path"])
                saved_edit = np.asarray(load_volume_sidecar(widget.project.to_absolute(editable["path"]), mmap_mode="r")).copy()
                self.assertGreater(int(np.count_nonzero(saved_edit)), 0)
                widget.project.add_or_update_label_schema(
                    "real_part_schema",
                    labels=[{"id": 2, "name": "test_region", "display_name": "Test region", "color": "#ff0000"}],
                    user_defined_part_name="real_part",
                    save=False,
                )
                widget.project.set_part_training_metadata(
                    "real-ant",
                    "real_part",
                    label_schema_id="real_part_schema",
                    opened_for_review=True,
                    save=False,
                )
                raw_rel = "specimens/real-ant/parts/real_part/labels/raw_ai_prediction_backup.ome.zarr"
                raw_meta = write_volume_sidecar(project_root / raw_rel, np.full(saved_edit.shape, 2, dtype=np.uint16), role="raw_ai_prediction_backup")
                widget.project.register_part_label_volume(
                    "real-ant",
                    "real_part",
                    "raw_ai_prediction_backup",
                    raw_rel,
                    raw_meta["shape_zyx"],
                    raw_meta["dtype"],
                    status="audit_backup",
                    save=True,
                )
                raw_path_before = widget.project.part_label_record("real-ant", "real_part", "raw_ai_prediction_backup")["path"]
                raw_before = np.asarray(load_volume_sidecar(widget.project.to_absolute(raw_path_before), mmap_mode="r")).copy()
                manual_target_before = Path(widget.project.to_absolute("specimens/real-ant/parts/real_part/labels/manual_truth.ome.zarr"))
                self.assertFalse(manual_target_before.exists(), f"unexpected existing manual truth target: {manual_target_before}")
                promotion = TifTruthPromotionService(widget.project).promote_reviewed_refs(
                    [{"specimen_id": "real-ant", "part_id": "real_part"}],
                    require_opened_for_review=True,
                    save=True,
                )
                self.assertTrue(promotion.ok, promotion.message)
                self.assertEqual(int(promotion.payload["count"]), 1)
                manual = widget.project.part_label_record("real-ant", "real_part", "manual_truth")
                manual_volume = np.asarray(load_volume_sidecar(widget.project.to_absolute(manual["path"]), mmap_mode="r")).copy()
                np.testing.assert_array_equal(manual_volume, saved_edit)
                raw_after_record = widget.project.part_label_record("real-ant", "real_part", "raw_ai_prediction_backup")
                self.assertEqual(raw_after_record["path"], raw_path_before)
                raw_after = np.asarray(load_volume_sidecar(widget.project.to_absolute(raw_after_record["path"]), mmap_mode="r")).copy()
                np.testing.assert_array_equal(raw_after, raw_before)
                widget.backend_panel_controller.populate_model_library_combo()
                self.assertEqual(widget.model_library_combo.currentData(), "")
                self.assertIn("no trained model", widget.model_library_summary_label.text().lower())
                with self.assertRaisesRegex(ValueError, "Reslice record is missing"):
                    widget.backend_panel_controller.selected_backend_samples_for_action("train")
                training_error = widget.backend_panel_controller._training_selection_error(prefer_part=True)
                self.assertIn("Reslice record is missing", training_error)
                self.assertIn("Reslice image is missing", training_error)
                widget.backend_panel_controller.refresh_predict_targets()
                self.assertGreaterEqual(widget.predict_targets_table.rowCount(), 1)
                part_mask_after = np.asarray(load_volume_sidecar(widget.project.to_absolute(part["mask"]["path"]), mmap_mode="r")).copy()
                np.testing.assert_array_equal(part_mask_after, part_mask_before)

                self.assertIsNotNone(widget.local_axis_controller.copy_source_z_axis_to_draft())
                part_shape = tuple(int(value) for value in widget.image_volume.shape)
                max_z = max(1, part_shape[0] - 1)
                max_y = max(2, part_shape[1] - 1)
                max_x = max(2, part_shape[2] - 1)
                widget.local_axis_draft["roll_reference"] = {
                    "pair_id": "roll_reference_point_pair",
                    "point_a": {"role": "roll_reference_a", "zyx": [min(1.0, max_z), min(1.0, max_y), min(1.0, max_x)]},
                    "point_b": {"role": "roll_reference_b", "zyx": [min(1.0, max_z), min(4.0, max_y), min(1.0, max_x)]},
                    "point_c": {"role": "reference_plane_c", "zyx": [min(3.0, max_z), min(1.0, max_y), min(4.0, max_x)]},
                }
                self.assertTrue(widget.local_axis_controller.align_to_reference_plane())
                with patch("AntSleap.ui.tif_local_axis_controller.QMessageBox.information"), patch("AntSleap.ui.tif_local_axis_controller.QMessageBox.warning"), patch("AntSleap.ui.tif_local_axis_controller.QMessageBox.critical"):
                    export_result = widget.local_axis_controller.export_current_reslice()
                self.assertEqual(export_result["status"], "running")
                self._wait_for_local_axis_export(widget)
                reslice = widget.project.get_part_reslice("real-ant", "real_part", export_result["reslice_id"])
                self.assertTrue(Path(widget.project.to_absolute(reslice["image_path"])).exists())
                widget.project.save_project()
            finally:
                widget.close_project(prompt_unsaved=False)
                widget.deleteLater()

            import_manager = TifProjectManager()
            import_manager.load_project(manifest_path)
            top_manual = import_manager.promote_working_edit_to_manual_truth("real-ant", save=True)
            top_manual_before = np.asarray(load_volume_sidecar(import_manager.to_absolute(top_manual["path"]), mmap_mode="r")).copy()
            correct_prediction_tif = project_root / "external_prediction_correct.tif"
            external_prediction = np.zeros(real_volume.shape, dtype=np.uint16)
            external_prediction[:, 1:4, 1:4] = 3
            tifffile.imwrite(correct_prediction_tif, external_prediction, photometric="minisblack")
            import_result = import_external_prediction_tif(
                import_manager,
                "real-ant",
                correct_prediction_tif,
                prediction_id="real_external_prediction",
                source_model="real_fixture",
            )
            imported_specimen = import_manager.get_specimen("real-ant")
            top_manual_after = np.asarray(load_volume_sidecar(import_manager.to_absolute(imported_specimen["labels"]["manual_truth"]["path"]), mmap_mode="r")).copy()
            np.testing.assert_array_equal(top_manual_after, top_manual_before)
            imported_backup = np.asarray(load_volume_sidecar(import_manager.to_absolute(imported_specimen["labels"]["raw_ai_prediction_backup"]["path"]), mmap_mode="r")).copy()
            np.testing.assert_array_equal(imported_backup, external_prediction)
            self.assertFalse(import_result["report"]["safety"]["manual_truth_overwritten"])
            draft_count_before_bad = len(imported_specimen["labels"]["model_drafts"])
            wrong_prediction_tif = project_root / "external_prediction_wrong_shape.tif"
            tifffile.imwrite(wrong_prediction_tif, np.zeros((max(1, real_volume.shape[0] - 1), real_volume.shape[1], real_volume.shape[2]), dtype=np.uint16), photometric="minisblack")
            with self.assertRaisesRegex(ValueError, "external_prediction_shape_mismatch"):
                import_external_prediction_tif(import_manager, "real-ant", wrong_prediction_tif, prediction_id="wrong_shape")
            self.assertEqual(len(import_manager.get_specimen("real-ant")["labels"]["model_drafts"]), draft_count_before_bad)

            reloaded = TifProjectManager()
            reloaded.load_project(manifest_path)
            reloaded_specimen = reloaded.get_specimen("real-ant")
            reloaded_manual = reloaded.part_label_record("real-ant", "real_part", "manual_truth")
            reloaded_raw = reloaded.part_label_record("real-ant", "real_part", "raw_ai_prediction_backup")
            self.assertTrue(reloaded_manual["path"])
            self.assertEqual(reloaded_raw["path"], raw_path_before)
            np.testing.assert_array_equal(
                np.asarray(load_volume_sidecar(reloaded.to_absolute(reloaded_manual["path"]), mmap_mode="r")),
                saved_edit,
            )
            np.testing.assert_array_equal(
                np.asarray(load_volume_sidecar(reloaded.to_absolute(reloaded_raw["path"]), mmap_mode="r")),
                raw_before,
            )
            reloaded_materials = read_material_map(reloaded.to_absolute(reloaded_specimen["material_map"]))
            self.assertIn(3, [int(item["id"]) for item in reloaded_materials["materials"]])
            reloaded_working = np.asarray(load_volume_sidecar(reloaded.to_absolute(reloaded_specimen["labels"]["working_edit"]["path"]), mmap_mode="r")).copy()
            self.assertGreaterEqual(int(np.count_nonzero(reloaded_working == 3)), 18)
            reloaded_widget = TifWorkbenchWidget(reloaded, "en")
            try:
                reloaded_widget.selection_workflow_controller.select_payload({
                    "scope": "part_reslice",
                    "specimen_id": "real-ant",
                    "part_id": "real_part",
                    "reslice_id": export_result["reslice_id"],
                })
                self.assertEqual(reloaded_widget.current_specimen_id, "real-ant")
                self.assertEqual(reloaded_widget.current_part_id, "real_part")
                self.assertEqual(reloaded_widget.current_reslice_id, export_result["reslice_id"])
                self.assertIsNotNone(reloaded_widget.image_volume)
                reloaded_widget.selection_workflow_controller.select_payload({"scope": "full", "specimen_id": "real-ant-2"})
                self.assertEqual(reloaded_widget.current_specimen_id, "real-ant-2")
                self.assertEqual(reloaded_widget.current_part_id, "")
                self.assertEqual(reloaded_widget.current_reslice_id, "")
                reloaded_widget.selection_workflow_controller.select_payload({
                    "scope": "part_reslice",
                    "specimen_id": "real-ant",
                    "part_id": "real_part",
                    "reslice_id": export_result["reslice_id"],
                })
                self.assertEqual(reloaded_widget.current_specimen_id, "real-ant")
                self.assertEqual(reloaded_widget.current_part_id, "real_part")
                self.assertEqual(reloaded_widget.current_reslice_id, export_result["reslice_id"])
            finally:
                reloaded_widget.close_project(prompt_unsaved=False)
                reloaded_widget.deleteLater()

        self.assertEqual(_tree_hash(source_path), source_hash_before)


if __name__ == "__main__":
    unittest.main()
