from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QDialog, QMessageBox, QProgressDialog, QTableWidgetItem

try:
    from AntSleap.core.tif_materials import next_material_id, remove_material, upsert_material, write_material_map
    from AntSleap.core.tif_part_extraction import (
        add_rectangular_keyframe,
        add_polygon_keyframe,
        build_preview_mask_from_contours,
        delete_keyframe,
        neighboring_keyframe_indices,
        read_contours_json,
        validate_contours_for_interpolation,
        write_contours_json,
        write_part_mask,
    )
    from AntSleap.core.tif_volume_io import flush_volume_array, load_volume_sidecar, volume_sidecar_exists
    from AntSleap.ui.tif_workbench_dialogs import MaterialEditorDialog
    from AntSleap.ui.tif_workbench_translations import tt
    from AntSleap.ui.tif_workbench_workers import TifMaterializeWorker, TifPartMaskPreviewWorker
except ModuleNotFoundError as exc:
    if exc.name != "AntSleap":
        raise
    from core.tif_materials import next_material_id, remove_material, upsert_material, write_material_map
    from core.tif_part_extraction import (
        add_rectangular_keyframe,
        add_polygon_keyframe,
        build_preview_mask_from_contours,
        delete_keyframe,
        neighboring_keyframe_indices,
        read_contours_json,
        validate_contours_for_interpolation,
        write_contours_json,
        write_part_mask,
    )
    from core.tif_volume_io import flush_volume_array, load_volume_sidecar, volume_sidecar_exists
    from ui.tif_workbench_dialogs import MaterialEditorDialog
    from ui.tif_workbench_translations import tt
    from ui.tif_workbench_workers import TifMaterializeWorker, TifPartMaskPreviewWorker


@dataclass
class TifPartMaskWorkflowState:
    preview_mask: object = None
    preview_bbox: list = field(default_factory=list)
    preview_accepted: bool = False
    keyframes: list = field(default_factory=list)
    contour_draw_mode: bool = False
    part_mask_volume: object = None
    material_map: dict = field(default_factory=dict)
    material_colors: dict = field(default_factory=dict)
    current_material_id: int = 0
    preview_token: int = 0
    preview_context: dict = field(default_factory=dict)
    preview_task_id: str = ""


class TifPartMaskWorkflowController:
    VIEW_SCOPE = "part_mask_material"

    def __init__(self, workbench):
        self.workbench = workbench
        self.state = TifPartMaskWorkflowState()
        self.preview_thread = None
        self.preview_worker = None
        self.preview_progress = None
        self.materialize_thread = None
        self.materialize_worker = None
        self.materialize_progress = None
        self.materialize_specimen_id = ""
        self.materialize_task_id = ""

    def bind_signals(self):
        workbench = self.workbench
        view = workbench.workbench_view
        view.register_scope(
            self.VIEW_SCOPE,
            "btn_copy_material_prev",
            "btn_copy_material_next",
            "btn_clear_current_material",
            "btn_draw_part_contour",
            "btn_add_rect_keyframe",
            "btn_delete_part_contour",
            "btn_clear_part_keyframes",
            "btn_prev_key_slice",
            "btn_next_key_slice",
            "btn_preview_part_mask",
            "btn_accept_part_mask",
            "btn_clear_part_preview",
            "btn_add_material",
            "btn_edit_material",
            "btn_delete_material",
            "material_table",
        )
        bindings = (
            ("copy_prev", "btn_copy_material_prev", "clicked", lambda: self.copy_current_material_to_adjacent_slice(-1)),
            ("copy_next", "btn_copy_material_next", "clicked", lambda: self.copy_current_material_to_adjacent_slice(1)),
            ("clear_material", "btn_clear_current_material", "clicked", self.clear_current_material_on_slice),
            ("draw_contour", "btn_draw_part_contour", "toggled", self.set_part_contour_draw_mode),
            ("add_rect", "btn_add_rect_keyframe", "clicked", self.add_current_rect_keyframe),
            ("delete_keyframe", "btn_delete_part_contour", "clicked", self.delete_current_part_keyframe),
            ("clear_keyframes", "btn_clear_part_keyframes", "clicked", self.clear_part_mask_keyframes),
            ("previous_keyframe", "btn_prev_key_slice", "clicked", lambda: self.jump_part_keyframe("previous")),
            ("next_keyframe", "btn_next_key_slice", "clicked", lambda: self.jump_part_keyframe("next")),
            ("preview", "btn_preview_part_mask", "clicked", self.preview_part_mask_from_keyframes),
            ("accept_preview", "btn_accept_part_mask", "clicked", self.accept_part_mask_preview),
            ("clear_preview", "btn_clear_part_preview", "clicked", self.clear_part_mask_preview),
            ("add_material", "btn_add_material", "clicked", self.add_material),
            ("edit_material", "btn_edit_material", "clicked", self.edit_selected_material),
            ("delete_material", "btn_delete_material", "clicked", self.delete_selected_material),
            ("select_material", "material_table", "itemSelectionChanged", self._on_material_selected),
        )
        for key, widget_name, signal_name, slot in bindings:
            signal = getattr(view.require(self.VIEW_SCOPE, widget_name), signal_name)
            workbench.signal_router.bind(self.VIEW_SCOPE, key, signal, slot)

    def load_roi_draft_keyframes(self, keyframes):
        self.state.keyframes = self._normalize_full_volume_mask_keyframes(keyframes)
        self.state.preview_mask = None
        self.state.preview_bbox = []
        self.state.preview_accepted = False
        return list(self.state.keyframes)

    def clear_roi_draft_keyframes(self):
        self.state.keyframes = []
        self.state.preview_mask = None
        self.state.preview_bbox = []
        self.state.preview_accepted = False

    def reset_state(self, *, keep_materials=False):
        material_map = self.state.material_map if keep_materials else {}
        material_colors = self.state.material_colors if keep_materials else {}
        current_material_id = self.state.current_material_id if keep_materials else 0
        self.state = TifPartMaskWorkflowState(
            material_map=material_map,
            material_colors=material_colors,
            current_material_id=current_material_id,
        )

    def _schema_materials_for_part(self, part=None):
        workbench = self.workbench
        part = part if isinstance(part, dict) else workbench.current_part
        schema_id = str(((part or {}).get("training") or {}).get("label_schema_id") or "")
        schema = workbench.project.get_label_schema(schema_id, default=None) if schema_id else None
        labels = (schema or {}).get("labels") or []
        if not labels:
            return []
        materials = [
            {"id": 0, "name": "background", "display_name": tt("Background / erase target", workbench.lang), "color": "#000000", "trainable": False}
        ]
        for item in labels:
            try:
                label_id = int(item.get("id", 0))
            except (TypeError, ValueError):
                continue
            if label_id <= 0:
                continue
            materials.append(
                {
                    "id": label_id,
                    "name": str(item.get("name") or f"label_{label_id}"),
                    "display_name": str(item.get("display_name") or item.get("name") or f"Label {label_id}"),
                    "color": str(item.get("color") or "#F94144"),
                    "trainable": bool(item.get("trainable", True)),
                    "source_name": str(item.get("display_name") or item.get("name") or f"Label {label_id}"),
                }
            )
        return materials

    def _active_materials(self):
        workbench = self.workbench
        if workbench.current_volume_scope == "part":
            schema_materials = self._schema_materials_for_part()
            if schema_materials:
                return schema_materials
        return self.state.material_map.get("materials", []) if isinstance(self.state.material_map, dict) else []

    def _sync_material_editor_scope(self):
        workbench = self.workbench
        is_part = workbench.current_volume_scope == "part"
        has_bound_schema = bool(self._schema_materials_for_part()) if is_part else False
        if hasattr(workbench, "material_editor_buttons"):
            workbench.material_editor_buttons.setVisible(not is_part)
        if hasattr(workbench, "material_table"):
            workbench.material_table.setVisible(not has_bound_schema)
        if hasattr(workbench, "material_help_label"):
            if has_bound_schema:
                message = "Use the bound region label schema above as the brush label selector. Select a colored row there, then paint or fill on the slice."
            elif is_part:
                message = "Bind a region label schema above before painting this part/reslice. The brush uses the bound schema once it is set."
            else:
                message = "After binding a label schema, select one current label here before using the brush or fill tools."
            workbench.material_help_label.setText(tt(message, workbench.lang))
        if hasattr(workbench, "material_scope_help_label"):
            workbench.material_scope_help_label.setVisible(not has_bound_schema)
            workbench.material_scope_help_label.setText(
                tt(
                    "Label IDs are the numeric labels stored in the current volume. For project part volumes and their reslices, this list follows the bound region label schema; for top-level imported volumes, it is the specimen label map.",
                    workbench.lang,
                )
            )

    def _sync_material_colors_from_active_source(self):
        workbench = self.workbench
        self.state.material_colors = {
            int(item["id"]): QColor(str(item.get("color", "#000000")))
            for item in self._active_materials()
            if isinstance(item, dict) and str(item.get("id", "")).strip() != ""
        }

    def _refresh_active_part_material_schema(self):
        workbench = self.workbench
        self._sync_material_editor_scope()
        self._sync_material_colors_from_active_source()
        self._populate_material_table()
        self._update_current_material_summary()
        if workbench.image_volume is not None:
            workbench.render_current_slice()

    def _part_mask_preview_running(self):
        workbench = self.workbench
        return self.preview_thread is not None

    def cancel_and_wait_preview(self, timeout_ms=2000):
        thread = self.preview_thread
        worker = self.preview_worker
        task_id = self.state.preview_task_id
        self.state.preview_token += 1
        if worker is not None and hasattr(worker, "cancel"):
            worker.cancel()
        if task_id:
            self.workbench._cancel_tif_task(task_id, "part_mask_preview_cancelled")
        if thread is not None:
            thread.quit()
            thread.wait(max(0, int(timeout_ms)))
            if thread.isRunning():
                return False
        if self.preview_thread is thread:
            self._cleanup_part_mask_preview_thread(thread, worker)
        return True

    def _cleanup_part_mask_preview_thread(self, thread=None, worker=None):
        workbench = self.workbench
        if thread is not None and self.preview_thread is not thread:
            return
        if worker is not None and self.preview_worker is not worker:
            return
        if self.preview_progress is not None:
            self.preview_progress.close()
            self.preview_progress.deleteLater()
        self.preview_progress = None
        self.preview_worker = None
        self.preview_thread = None
        self.state.preview_context = {}
        self.state.preview_task_id = ""
        workbench._set_scope_controls_enabled()

    def _on_part_mask_preview_progress(self, current, total, message):
        workbench = self.workbench
        progress = self.preview_progress
        if progress is None:
            return
        total = int(total or 0)
        if total <= 0:
            progress.setRange(0, 0)
        else:
            maximum = max(1, total)
            progress.setRange(0, maximum)
            progress.setValue(max(0, min(maximum, int(current or 0))))
        progress.setLabelText(tt(message, workbench.lang))

    def _on_part_mask_preview_finished(self, result):
        workbench = self.workbench
        result = dict(result or {})
        token = int(result.get("token") or 0)
        if token != int(self.state.preview_token):
            return
        if not workbench._task_context_matches_current(
            self.state.preview_task_id,
            fields=("specimen_id", "volume_scope", "part_id", "reslice_id"),
        ):
            thread = self.preview_thread
            workbench._cancel_tif_task(self.state.preview_task_id, "stale_part_mask_preview_context")
            self._cleanup_part_mask_preview_thread()
            if thread is not None:
                thread.quit()
            return
        thread = self.preview_thread
        context = dict(result.get("context") or self.state.preview_context or {})
        if result.get("cancelled"):
            workbench._cancel_tif_task(self.state.preview_task_id, "part_mask_preview_cancelled")
            self._cleanup_part_mask_preview_thread()
            if thread is not None:
                thread.quit()
            return
        mask = result.get("mask")
        if mask is None:
            workbench._fail_tif_task(self.state.preview_task_id, "part_mask_preview_empty_result", payload=result)
            self._cleanup_part_mask_preview_thread()
            if thread is not None:
                thread.quit()
            return
        workbench._finish_tif_task(self.state.preview_task_id, payload={"token": token}, message="part_mask_preview_finished")
        self._cleanup_part_mask_preview_thread()
        if thread is not None:
            thread.quit()
        self._apply_part_mask_preview_result(mask, context)

    def _on_part_mask_preview_failed(self, result):
        workbench = self.workbench
        result = dict(result or {})
        token = int(result.get("token") or 0)
        if token != int(self.state.preview_token):
            return
        thread = self.preview_thread
        message = str(result.get("error") or "")
        task_current = workbench._task_context_matches_current(
            self.state.preview_task_id,
            fields=("specimen_id", "volume_scope", "part_id", "reslice_id"),
        )
        workbench._fail_tif_task(self.state.preview_task_id, message, payload=result)
        self._cleanup_part_mask_preview_thread()
        if thread is not None:
            thread.quit()
        if message and task_current:
            QMessageBox.warning(workbench, tt("Part extraction", workbench.lang), message)

    def _start_part_mask_preview_build(self, contours, shape, context):
        workbench = self.workbench
        if self.preview_thread is not None:
            QMessageBox.information(
                workbench,
                tt("Part extraction", workbench.lang),
                tt("Preview auto fill is already running.", workbench.lang),
            )
            return
        self.state.preview_token += 1
        token = int(self.state.preview_token)
        self.state.preview_context = dict(context or {})
        task = workbench._start_tif_task(
            "mask_preview",
            action="build_mask_preview",
            payload={"token": token, "shape_zyx": list(shape or [])},
            request_key=f"part_mask_preview:{token}",
            message=tt("Preview auto fill is running...", workbench.lang),
        )
        task.context = workbench._current_task_context(request_key=f"part_mask_preview:{token}")
        if isinstance(context, dict):
            task.context = task.context.__class__.from_mapping(
                {
                    **task.context.to_dict(),
                    "specimen_id": context.get("specimen_id", task.context.specimen_id),
                    "volume_scope": context.get("volume_scope", context.get("scope", task.context.volume_scope)),
                    "part_id": context.get("part_id", task.context.part_id),
                    "reslice_id": context.get("reslice_id", task.context.reslice_id),
                    "request_key": f"part_mask_preview:{token}",
                }
            )
        self.state.preview_task_id = task.task_id
        self.preview_progress = QProgressDialog(
            tt("Preview auto fill is running...", workbench.lang),
            "",
            0,
            0,
            workbench,
        )
        self.preview_progress.setWindowTitle(tt("Part extraction", workbench.lang))
        self.preview_progress.setCancelButton(None)
        self.preview_progress.setAutoClose(False)
        self.preview_progress.setAutoReset(False)
        self.preview_progress.setMinimumDuration(0)
        self.preview_progress.setWindowModality(Qt.WindowModal)
        self.preview_progress.show()

        self.preview_thread = QThread(self)
        self.preview_worker = TifPartMaskPreviewWorker(token, contours, shape, context)
        self.preview_worker.moveToThread(self.preview_thread)
        self.preview_thread.started.connect(self.preview_worker.run)
        self.preview_worker.progress.connect(self._on_part_mask_preview_progress)
        self.preview_worker.finished.connect(self._on_part_mask_preview_finished)
        self.preview_worker.failed.connect(self._on_part_mask_preview_failed)
        self.preview_worker.finished.connect(self.preview_thread.quit)
        self.preview_worker.failed.connect(self.preview_thread.quit)
        self.preview_thread.finished.connect(self.preview_worker.deleteLater)
        self.preview_thread.finished.connect(
            lambda thread=self.preview_thread, worker=self.preview_worker: self._cleanup_part_mask_preview_thread(thread, worker)
        )
        self.preview_thread.finished.connect(self.preview_thread.deleteLater)
        workbench._set_scope_controls_enabled()
        self.preview_thread.start()

    def is_part_contour_draw_mode(self):
        workbench = self.workbench
        return bool(
            self.state.contour_draw_mode
            and workbench.current_volume_scope in {"full", "part"}
            and workbench.display_mode == "slice"
            and workbench.image_volume is not None
            and workbench._current_slice_axis() == "z"
        )

    def disable_contour_draw_mode(self):
        self.state.contour_draw_mode = False
        button = getattr(self.workbench, "btn_draw_part_contour", None)
        if button is not None and button.isChecked():
            button.blockSignals(True)
            button.setChecked(False)
            button.blockSignals(False)

    def set_part_contour_draw_mode(self, checked):
        workbench = self.workbench
        self.state.contour_draw_mode = bool(checked)
        if self.state.contour_draw_mode:
            workbench.roi_workflow_controller.disable_draw_mode()
            workbench.btn_part_draw_roi.blockSignals(True)
            workbench.btn_part_draw_roi.setChecked(False)
            workbench.btn_part_draw_roi.blockSignals(False)
            if workbench.current_volume_scope not in {"full", "part"} or workbench.image_volume is None:
                self.state.contour_draw_mode = False
                workbench.btn_draw_part_contour.blockSignals(True)
                workbench.btn_draw_part_contour.setChecked(False)
                workbench.btn_draw_part_contour.blockSignals(False)
                QMessageBox.information(workbench, tt("Part extraction", workbench.lang), tt("Select a full volume or part volume before drawing contours.", workbench.lang))
                return
            if workbench.display_mode != "slice" or workbench._current_slice_axis() != "z":
                self.state.contour_draw_mode = False
                workbench.btn_draw_part_contour.blockSignals(True)
                workbench.btn_draw_part_contour.setChecked(False)
                workbench.btn_draw_part_contour.blockSignals(False)
                QMessageBox.information(workbench, tt("Part extraction", workbench.lang), tt("Contour drawing currently uses Z slices.", workbench.lang))
                return
            message = tt("Drag on the current slice to draw a closed contour.", workbench.lang)
            workbench.training_status_label.setText(message)
            workbench.log(message)
        workbench.render_current_slice()

    def _autosave_active_part_roi_mask_keyframes(self, bbox=None):
        workbench = self.workbench
        if not workbench.active_part_roi_id or not workbench.current_specimen_id:
            return None
        roi = workbench.project.get_part_roi(workbench.current_specimen_id, workbench.active_part_roi_id, default=None)
        if roi is None or roi.get("linked_part_id") or roi.get("status") == "part_created":
            return None
        if bbox is None:
            bbox = workbench._full_volume_contour_bbox()
        if not bbox:
            return None
        try:
            updated = workbench.project.update_part_roi(
                workbench.current_specimen_id,
                workbench.active_part_roi_id,
                bbox_zyx=bbox,
                status="draft",
                metadata=workbench._roi_keyframe_metadata(),
                save=True,
            )
        except Exception as exc:
            workbench.log(f"Failed to auto-save part mask key slices for ROI draft {workbench.active_part_roi_id}: {exc}")
            return None
        workbench._populate_volume_roi_source_combo()
        return updated

    def _current_part_contours_path(self):
        workbench = self.workbench
        part = workbench.project.get_part(workbench.current_specimen_id, workbench.current_part_id, default=None)
        if part is None:
            return ""
        return workbench.project.to_absolute(part.get("contours_path", ""))

    def _current_part_contours(self):
        workbench = self.workbench
        contours_path = self._current_part_contours_path()
        if not contours_path:
            return {}, ""
        return read_contours_json(contours_path), contours_path

    def _is_legacy_roi_shell_keyframe(self, keyframe):
        workbench = self.workbench
        if not isinstance(keyframe, dict):
            return False
        author = str(keyframe.get("author") or "")
        source = str(keyframe.get("source") or "")
        return author == "taxamask_roi_shell" or source in {"roi_shell", "roi_key_slice_rectangle"}

    def _part_mask_contours_for_preview(self, contours):
        workbench = self.workbench
        payload = dict(contours or {})
        keyframes = payload.get("keyframes", []) if isinstance(payload.get("keyframes", []), list) else []
        kept = [item for item in keyframes if isinstance(item, dict) and not self._is_legacy_roi_shell_keyframe(item)]
        ignored = len([item for item in keyframes if isinstance(item, dict) and self._is_legacy_roi_shell_keyframe(item)])
        payload["keyframes"] = kept
        return payload, ignored

    def _normalize_full_volume_mask_keyframes(self, keyframes):
        workbench = self.workbench
        normalized = []
        shape = tuple(int(value) for value in getattr(workbench.image_volume, "shape", ()) or ())
        for item in keyframes or []:
            if not isinstance(item, dict) or str(item.get("axis", "z")) != "z":
                continue
            slice_index = workbench._safe_contour_slice_index(item, None)
            if slice_index is None:
                continue
            if len(shape) == 3 and not (0 <= int(slice_index) < int(shape[0])):
                continue
            polygon = self._dedupe_contour_points(item.get("polygon") or [])
            if len(polygon) < 3:
                continue
            normalized.append(
                {
                    "axis": "z",
                    "slice_index": int(slice_index),
                    "polygon": polygon,
                    "author": str(item.get("author") or "taxamask_ui_freehand"),
                    "source": str(item.get("source") or "manual_freehand"),
                    "created_at": str(item.get("created_at") or datetime.now().astimezone().isoformat(timespec="seconds")),
                }
            )
        normalized.sort(key=lambda item: int(item.get("slice_index", 0)))
        return normalized

    def _format_contour_quality_report(self, report):
        workbench = self.workbench
        if not isinstance(report, dict):
            return ""
        problems = []
        for item in report.get("errors", []) or []:
            problems.append(str(item.get("message") or item.get("code") or "error"))
        for item in report.get("warnings", []) or []:
            problems.append(str(item.get("message") or item.get("code") or "warning"))
        if not problems:
            return tt("Quality check passed", workbench.lang)
        return f"{tt('Review warnings', workbench.lang)}: " + " | ".join(problems[:4])

    def _should_build_part_mask_preview_in_background(self, shape):
        workbench = self.workbench
        try:
            voxel_count = int(np.prod([max(0, int(value)) for value in (shape or ())], dtype=np.int64))
        except Exception:
            voxel_count = 0
        return voxel_count >= 1_000_000

    def _apply_part_mask_preview_result(self, mask, context):
        workbench = self.workbench
        context = dict(context or {})
        scope = str(context.get("scope") or workbench.current_volume_scope or "")
        preview_contours = dict(context.get("preview_contours") or {})
        report = dict(context.get("report") or {})
        bbox = context.get("bbox") or []
        ignored_legacy = int(context.get("ignored_legacy") or 0)
        keyframe_count = int(context.get("keyframe_count") or len(preview_contours.get("keyframes", []) or []))

        self.state.preview_mask = mask
        self.state.preview_accepted = False
        if scope == "full":
            self.state.preview_bbox = bbox
            if bbox:
                workbench.part_bbox_edit.setText(workbench._bbox_text(bbox))
                self._autosave_active_part_roi_mask_keyframes(bbox)
        else:
            self.state.preview_bbox = []
            part = workbench.project.update_part_status(workbench.current_specimen_id, workbench.current_part_id, "mask_preview")
            workbench.current_part = part
            workbench._update_status_labels(workbench.project.get_specimen(workbench.current_specimen_id), part=part)

        workbench.volume_render_controller._clear_volume_preview_cache()
        workbench._set_scope_controls_enabled()
        workbench.render_current_slice()
        quality = self._format_contour_quality_report(report)
        message = (
            tt("Preview mask generated from {0} key slice(s).", workbench.lang).format(keyframe_count)
            + "\n"
            + tt("Part mask preview quality: {0}", workbench.lang).format(quality)
        )
        if scope == "full":
            message = (
                f"{message}\n"
                + tt("Review the preview, then accept it before creating the part volume.", workbench.lang)
            )
        if ignored_legacy:
            message = (
                f"{message}\n"
                + tt("Ignored {0} legacy ROI shell key slice(s). Use Clear key slices to remove them permanently.", workbench.lang).format(ignored_legacy)
            )
        workbench.training_status_label.setText(message)
        workbench.log(message)

    def _dedupe_contour_points(self, points):
        workbench = self.workbench
        clean = []
        width = int(workbench.image_volume.shape[2]) if workbench.image_volume is not None else 0
        height = int(workbench.image_volume.shape[1]) if workbench.image_volume is not None else 0
        for point in points or []:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                continue
            px = float(point[0])
            py = float(point[1])
            if not math.isfinite(px) or not math.isfinite(py):
                continue
            if width > 0:
                px = max(0.0, min(float(width - 1), px))
            if height > 0:
                py = max(0.0, min(float(height - 1), py))
            next_point = [round(px, 3), round(py, 3)]
            if not clean or math.hypot(clean[-1][0] - next_point[0], clean[-1][1] - next_point[1]) >= 0.15:
                clean.append(next_point)
        if len(clean) > 2 and math.hypot(clean[0][0] - clean[-1][0], clean[0][1] - clean[-1][1]) < 0.15:
            clean.pop()
        return clean

    def current_contour_overlay_polygons(self):
        workbench = self.workbench
        if workbench.current_volume_scope not in {"full", "part"} or workbench.image_volume is None:
            return []
        axis, slice_index = workbench._active_slice_position()
        if workbench.current_volume_scope == "full":
            contours = workbench._full_volume_contours_payload()
        else:
            contours_path = self._current_part_contours_path()
            if not contours_path:
                return []
            contours = read_contours_json(contours_path)
        overlays = []
        for keyframe in contours.get("keyframes", []) or []:
            if not isinstance(keyframe, dict):
                continue
            if self._is_legacy_roi_shell_keyframe(keyframe):
                continue
            if str(keyframe.get("axis", "z")) != axis:
                continue
            if workbench._safe_contour_slice_index(keyframe, None) != int(slice_index):
                continue
            polygon = keyframe.get("polygon") or []
            clean_polygon = self._dedupe_contour_points(polygon)
            if len(clean_polygon) >= 3:
                overlays.append({"polygon": clean_polygon, "color": "#FF8C42", "fill_alpha": 30})
        return overlays

    def finish_part_contour_drag(self, points):
        workbench = self.workbench
        if not self.is_part_contour_draw_mode() or workbench.image_volume is None:
            return
        polygon = self._dedupe_contour_points(points)
        if len(polygon) < 3:
            message = tt("Contour needs at least 3 points.", workbench.lang)
            workbench.training_status_label.setText(message)
            workbench.log(message)
            return
        if workbench.current_volume_scope == "full":
            contours = workbench._full_volume_contours_payload()
            slice_index = int(workbench.slice_slider.value())
            try:
                contours = add_polygon_keyframe(
                    contours,
                    slice_index,
                    polygon,
                    axis="z",
                    author="taxamask_ui_freehand",
                    source="manual_freehand",
                )
            except Exception as exc:
                QMessageBox.warning(workbench, tt("Part extraction", workbench.lang), str(exc))
                return
            self.state.keyframes = list(contours.get("keyframes", []) or [])
            bbox = workbench._full_volume_contour_bbox(contours)
            if bbox:
                workbench.part_bbox_edit.setText(workbench._bbox_text(bbox))
                self._autosave_active_part_roi_mask_keyframes(bbox)
            self.state.preview_mask = None
            self.state.preview_bbox = []
            self.state.preview_accepted = False
            workbench.render_current_slice()
            message = tt("Contour saved at Z {0}.", workbench.lang).format(slice_index)
            workbench.training_status_label.setText(message)
            workbench.log(message)
            return
        if not workbench._is_editable_part_volume():
            return
        contours, contours_path = self._current_part_contours()
        if not contours_path:
            return
        slice_index = int(workbench.slice_slider.value())
        try:
            contours = add_polygon_keyframe(
                contours,
                slice_index,
                polygon,
                axis="z",
                author="taxamask_ui_freehand",
                source="manual_freehand",
            )
            write_contours_json(contours_path, contours)
            part = workbench.project.update_part_status(workbench.current_specimen_id, workbench.current_part_id, "draft")
        except Exception as exc:
            QMessageBox.warning(workbench, tt("Part extraction", workbench.lang), str(exc))
            return
        workbench.current_part = part
        self.state.preview_mask = None
        workbench._update_status_labels(workbench.project.get_specimen(workbench.current_specimen_id), part=part)
        workbench.render_current_slice()
        message = tt("Contour saved at Z {0}.", workbench.lang).format(slice_index)
        workbench.training_status_label.setText(message)
        workbench.log(message)

    def delete_current_part_keyframe(self):
        workbench = self.workbench
        if not workbench.coordinator.guard_backend_write_lock():
            return
        if workbench.current_volume_scope not in {"full", "part"} or workbench.image_volume is None:
            QMessageBox.information(workbench, tt("Part extraction", workbench.lang), tt("Select a full volume or part volume before editing part masks.", workbench.lang))
            return
        if workbench._current_slice_axis() != "z":
            QMessageBox.information(workbench, tt("Part extraction", workbench.lang), tt("Contour drawing currently uses Z slices.", workbench.lang))
            return
        slice_index = int(workbench.slice_slider.value())
        if workbench.current_volume_scope == "full":
            contours, deleted = delete_keyframe(workbench._full_volume_contours_payload(), slice_index, axis="z")
            if not deleted:
                message = tt("No contour exists at Z {0}.", workbench.lang).format(slice_index)
                workbench.training_status_label.setText(message)
                workbench.log(message)
                return
            self.state.keyframes = list(contours.get("keyframes", []) or [])
            bbox = workbench._full_volume_contour_bbox(contours)
            if not bbox and workbench.part_roi_keyframes:
                bbox = workbench.roi_workflow_controller.keyframe_bbox(workbench.part_roi_keyframes)
            workbench.part_bbox_edit.setText(workbench._bbox_text(bbox))
            if bbox:
                self._autosave_active_part_roi_mask_keyframes(bbox)
            self.state.preview_mask = None
            self.state.preview_bbox = []
            self.state.preview_accepted = False
            workbench.render_current_slice()
            message = tt("Deleted contour at Z {0}.", workbench.lang).format(slice_index)
            workbench.training_status_label.setText(message)
            workbench.log(message)
            return
        if not workbench._is_editable_part_volume():
            return
        contours, contours_path = self._current_part_contours()
        if not contours_path:
            return
        contours, deleted = delete_keyframe(contours, slice_index, axis="z")
        if not deleted:
            message = tt("No contour exists at Z {0}.", workbench.lang).format(slice_index)
            workbench.training_status_label.setText(message)
            workbench.log(message)
            return
        write_contours_json(contours_path, contours)
        part = workbench.project.update_part_status(workbench.current_specimen_id, workbench.current_part_id, "draft")
        workbench.current_part = part
        self.state.preview_mask = None
        workbench._update_status_labels(workbench.project.get_specimen(workbench.current_specimen_id), part=part)
        workbench.render_current_slice()
        message = tt("Deleted contour at Z {0}.", workbench.lang).format(slice_index)
        workbench.training_status_label.setText(message)
        workbench.log(message)

    def clear_part_mask_keyframes(self):
        workbench = self.workbench
        if not workbench.coordinator.guard_backend_write_lock():
            return False
        if workbench.current_volume_scope not in {"full", "part"} or workbench.image_volume is None:
            QMessageBox.information(workbench, tt("Part extraction", workbench.lang), tt("Select a full volume or part volume before editing part masks.", workbench.lang))
            return False
        if workbench.current_volume_scope == "full":
            keyframes = [item for item in self.state.keyframes if isinstance(item, dict)]
            if not keyframes and self.state.preview_mask is None:
                message = tt("No part key slices to clear.", workbench.lang)
                workbench.training_status_label.setText(message)
                workbench.log(message)
                return False
            response = QMessageBox.question(
                workbench,
                tt("Part extraction", workbench.lang),
                tt(
                    "Clear all key slices for the current full-volume part draft? This removes the hand-drawn mask draft but keeps the ROI bbox.",
                    workbench.lang,
                ),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if response != QMessageBox.Yes:
                return False
            self.state.keyframes = []
            self.state.preview_mask = None
            self.state.preview_bbox = []
            self.state.preview_accepted = False
            bbox = workbench.roi_workflow_controller.keyframe_bbox(workbench.part_roi_keyframes) if workbench.part_roi_keyframes else []
            if bbox:
                workbench.part_bbox_edit.setText(workbench._bbox_text(bbox))
            else:
                try:
                    bbox = workbench.roi_workflow_controller.parse_bbox_text()
                except Exception:
                    bbox = []
            if workbench.active_part_roi_id:
                if bbox:
                    workbench.roi_workflow_controller.autosave_active_bbox(bbox)
            workbench.render_current_slice()
            message = tt("Cleared {0} key slice(s) and reset the part mask draft.", workbench.lang).format(len(keyframes))
            workbench.training_status_label.setText(message)
            workbench.log(message)
            return True
        if not workbench._is_editable_part_volume():
            return False
        part = workbench.project.get_part(workbench.current_specimen_id, workbench.current_part_id, default=None)
        contours, contours_path = self._current_part_contours()
        if part is None or not contours_path:
            return False
        keyframes = [item for item in (contours.get("keyframes", []) or []) if isinstance(item, dict)]
        if not keyframes and self.state.preview_mask is None and not self._part_mask_has_voxels():
            message = tt("No part key slices to clear.", workbench.lang)
            workbench.training_status_label.setText(message)
            workbench.log(message)
            return False
        display_name = part.get("display_name") or part.get("part_id") or workbench.current_part_id
        response = QMessageBox.question(
            workbench,
            tt("Part extraction", workbench.lang),
            tt(
                "Clear all key slices for part {0}? This removes saved mask key slices and the current auto-fill preview, but keeps the cropped part image.",
                workbench.lang,
            ).format(display_name),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if response != QMessageBox.Yes:
            return False
        try:
            contours["keyframes"] = []
            write_contours_json(contours_path, contours)
            mask_path = self._current_part_mask_path()
            if mask_path and volume_sidecar_exists(mask_path):
                target = load_volume_sidecar(mask_path, mmap_mode="r+")
                try:
                    target[:] = 0
                    metadata = flush_volume_array(mask_path, target)
                finally:
                    mmap_handle = getattr(target, "_mmap", None)
                    if mmap_handle is not None:
                        mmap_handle.close()
                part.setdefault("mask", {}).update(
                    {
                        "shape_zyx": metadata.get("shape_zyx", []),
                        "dtype": metadata.get("dtype", ""),
                        "spacing_zyx": metadata.get("spacing_zyx", []),
                        "spacing_unit": metadata.get("spacing_unit", "micrometer"),
                        "orientation": metadata.get("orientation", "unknown"),
                    }
                )
            metadata_payload = part.setdefault("metadata", {})
            metadata_payload["part_mask_keyframes_cleared_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
            metadata_payload["part_mask_keyframes_cleared_count"] = len(keyframes)
            part = workbench.project.update_part_status(workbench.current_specimen_id, workbench.current_part_id, "roi_confirmed", save=False)
            workbench.project.save_project()
        except Exception as exc:
            QMessageBox.warning(workbench, tt("Part extraction", workbench.lang), str(exc))
            return False
        workbench.current_part = part
        self.state.preview_mask = None
        workbench.edit_volume = None
        workbench.volume_render_controller._clear_volume_preview_cache()
        workbench._reload_label_volume()
        workbench._update_status_labels(workbench.project.get_specimen(workbench.current_specimen_id), part=part)
        workbench.render_current_slice()
        message = tt("Cleared {0} key slice(s) and reset the part mask draft.", workbench.lang).format(len(keyframes))
        workbench.training_status_label.setText(message)
        workbench.log(message)
        return True

    def jump_part_keyframe(self, direction):
        workbench = self.workbench
        if workbench.current_volume_scope not in {"full", "part"} or workbench.image_volume is None:
            return
        if workbench._current_slice_axis() != "z":
            QMessageBox.information(workbench, tt("Part extraction", workbench.lang), tt("Contour drawing currently uses Z slices.", workbench.lang))
            return
        if workbench.current_volume_scope == "full":
            contours = workbench._full_volume_contours_payload()
        else:
            if not workbench._is_editable_part_volume():
                return
            contours, _contours_path = self._current_part_contours()
        neighbors = neighboring_keyframe_indices(contours, int(workbench.slice_slider.value()), axis="z")
        target = neighbors.get("previous" if direction == "previous" else "next")
        if target is None:
            message = tt("No previous key slice." if direction == "previous" else "No next key slice.", workbench.lang)
            workbench.training_status_label.setText(message)
            workbench.log(message)
            return
        workbench.slice_slider.setValue(int(target))
        workbench.render_current_slice()

    def _part_keyframe_bbox_yx(self):
        workbench = self.workbench
        if workbench.image_volume is None:
            return []
        height = int(workbench.image_volume.shape[1])
        width = int(workbench.image_volume.shape[2])
        y_margin = max(0, int(round(height * 0.18)))
        x_margin = max(0, int(round(width * 0.18)))
        return [[y_margin, max(y_margin + 1, height - y_margin)], [x_margin, max(x_margin + 1, width - x_margin)]]

    def add_current_rect_keyframe(self):
        workbench = self.workbench
        if not workbench.coordinator.guard_backend_write_lock():
            return
        if not workbench._is_editable_part_volume() or workbench.image_volume is None:
            QMessageBox.information(workbench, tt("Part extraction", workbench.lang), tt("Select a part volume before editing part masks.", workbench.lang))
            return
        if workbench._current_slice_axis() != "z":
            QMessageBox.information(workbench, tt("Part extraction", workbench.lang), tt("Key-slice mask preview currently uses Z slices.", workbench.lang))
            return
        contours_path = self._current_part_contours_path()
        if not contours_path:
            return
        contours = read_contours_json(contours_path)
        contours = add_rectangular_keyframe(
            contours,
            int(workbench.slice_slider.value()),
            self._part_keyframe_bbox_yx(),
            author="taxamask_ui_rect",
        )
        write_contours_json(contours_path, contours)
        part = workbench.project.update_part_status(workbench.current_specimen_id, workbench.current_part_id, "draft")
        workbench.current_part = part
        self.state.preview_mask = None
        workbench.volume_render_controller._clear_volume_preview_cache()
        workbench._update_status_labels(workbench.project.get_specimen(workbench.current_specimen_id), part=part)
        workbench.render_current_slice()
        message = tt("Added rectangular key slice at Z {0}.", workbench.lang).format(int(workbench.slice_slider.value()))
        workbench.training_status_label.setText(message)
        workbench.log(message)

    def preview_part_mask_from_keyframes(self):
        workbench = self.workbench
        if not workbench.coordinator.guard_backend_write_lock():
            return
        if self._part_mask_preview_running():
            QMessageBox.information(workbench, tt("Part extraction", workbench.lang), tt("Preview auto fill is already running.", workbench.lang))
            return
        if workbench.current_volume_scope not in {"full", "part"} or workbench.image_volume is None:
            QMessageBox.information(workbench, tt("Part extraction", workbench.lang), tt("Select a full volume or part volume before previewing masks.", workbench.lang))
            return
        if workbench.current_volume_scope == "full":
            contours = workbench._full_volume_contours_payload()
            bbox = workbench._full_volume_contour_bbox(contours)
            if not bbox:
                QMessageBox.warning(workbench, tt("Part extraction", workbench.lang), tt("Draw at least one contour before previewing masks.", workbench.lang))
                return
            local_contours = workbench._full_volume_contours_to_local(contours, bbox)
            shape = tuple(int(pair[1]) - int(pair[0]) for pair in bbox)
            preview_contours, ignored_legacy = self._part_mask_contours_for_preview(local_contours)
            report = validate_contours_for_interpolation(preview_contours, shape, axis="z")
            if not report.get("ok"):
                QMessageBox.warning(workbench, tt("Part extraction", workbench.lang), self._format_contour_quality_report(report))
                return
            context = {
                "scope": "full",
                "preview_contours": preview_contours,
                "report": report,
                "bbox": bbox,
                "ignored_legacy": ignored_legacy,
                "keyframe_count": len(preview_contours.get("keyframes", []) or []),
            }
            if self._should_build_part_mask_preview_in_background(shape):
                self.state.preview_mask = None
                self.state.preview_bbox = []
                self.state.preview_accepted = False
                workbench._set_scope_controls_enabled()
                workbench.training_status_label.setText(tt("Preview auto fill is running...", workbench.lang))
                self._start_part_mask_preview_build(preview_contours, shape, context)
                return
            try:
                mask = build_preview_mask_from_contours(preview_contours, shape)
            except Exception as exc:
                QMessageBox.warning(workbench, tt("Part extraction", workbench.lang), str(exc))
                return
            self._apply_part_mask_preview_result(mask, context)
            return
        if not workbench._is_editable_part_volume():
            return
        contours_path = self._current_part_contours_path()
        contours = read_contours_json(contours_path)
        preview_contours, ignored_legacy = self._part_mask_contours_for_preview(contours)
        report = validate_contours_for_interpolation(preview_contours, workbench.image_volume.shape, axis="z")
        if not report.get("ok"):
            QMessageBox.warning(workbench, tt("Part extraction", workbench.lang), self._format_contour_quality_report(report))
            return
        context = {
            "scope": "part",
            "preview_contours": preview_contours,
            "report": report,
            "ignored_legacy": ignored_legacy,
            "keyframe_count": len(preview_contours.get("keyframes", []) or []),
        }
        if self._should_build_part_mask_preview_in_background(workbench.image_volume.shape):
            self.state.preview_mask = None
            self.state.preview_bbox = []
            self.state.preview_accepted = False
            workbench._set_scope_controls_enabled()
            workbench.training_status_label.setText(tt("Preview auto fill is running...", workbench.lang))
            self._start_part_mask_preview_build(preview_contours, workbench.image_volume.shape, context)
            return
        try:
            mask = build_preview_mask_from_contours(preview_contours, workbench.image_volume.shape)
        except Exception as exc:
            QMessageBox.warning(workbench, tt("Part extraction", workbench.lang), str(exc))
            return
        self._apply_part_mask_preview_result(mask, context)

    def accept_part_mask_preview(self):
        workbench = self.workbench
        if not workbench.coordinator.guard_backend_write_lock():
            return False
        if workbench.current_volume_scope == "full":
            if self.state.preview_mask is None:
                return
            self.state.preview_accepted = True
            workbench._set_scope_controls_enabled()
            workbench.render_current_slice()
            message = (
                tt("Accepted part mask.", workbench.lang)
                + "\n"
                + tt("Use Confirm ROI to create the part volume with this accepted mask.", workbench.lang)
            )
            workbench.training_status_label.setText(message)
            workbench.log(message)
            return
        if not workbench._is_editable_part_volume() or self.state.preview_mask is None:
            return
        part = workbench.project.get_part(workbench.current_specimen_id, workbench.current_part_id, default=None)
        if part is None:
            return
        try:
            metadata = write_part_mask(workbench.project, part, self.state.preview_mask)
            part["mask"].update(
                {
                    "shape_zyx": metadata.get("shape_zyx", []),
                    "dtype": metadata.get("dtype", ""),
                    "spacing_zyx": metadata.get("spacing_zyx", []),
                    "spacing_unit": metadata.get("spacing_unit", "micrometer"),
                    "orientation": metadata.get("orientation", "unknown"),
                }
            )
            part = workbench.project.update_part_status(workbench.current_specimen_id, workbench.current_part_id, "reviewed")
            workbench.project.save_project()
        except Exception as exc:
            QMessageBox.warning(workbench, tt("Part extraction", workbench.lang), str(exc))
            return
        self.state.preview_mask = None
        self._reload_part_mask_volume()
        workbench.volume_render_controller._clear_volume_preview_cache()
        workbench.current_part = part
        workbench._reload_label_volume()
        workbench._update_status_labels(workbench.project.get_specimen(workbench.current_specimen_id), part=part)
        workbench.render_current_slice()
        message = tt("Accepted part mask.", workbench.lang)
        workbench.training_status_label.setText(message)
        workbench.log(message)

    def clear_part_mask_preview(self):
        workbench = self.workbench
        if not workbench.coordinator.guard_backend_write_lock():
            return
        self.state.preview_mask = None
        self.state.preview_bbox = []
        self.state.preview_accepted = False
        workbench.volume_render_controller._clear_volume_preview_cache()
        if workbench.current_volume_scope == "full":
            workbench.render_current_slice()
            return
        part = workbench.project.get_part(workbench.current_specimen_id, workbench.current_part_id, default=None)
        if part is not None:
            workbench.current_part = part
            workbench._update_status_labels(workbench.project.get_specimen(workbench.current_specimen_id), part=part)
        workbench.render_current_slice()

    def _populate_material_table(self):
        workbench = self.workbench
        self._sync_material_editor_scope()
        materials = self._active_materials()
        workbench.material_table.setRowCount(len(materials))
        for row, material in enumerate(materials):
            color_text = str(material.get("color", "#000000"))
            color_item = QTableWidgetItem("")
            color_item.setToolTip(color_text)
            try:
                color_item.setBackground(QColor(color_text))
            except Exception:
                pass
            workbench.material_table.setItem(row, 0, color_item)
            workbench.material_table.setItem(row, 1, QTableWidgetItem(str(material.get("id", ""))))
            workbench.material_table.setItem(row, 2, QTableWidgetItem(str(material.get("display_name") or material.get("name") or "")))
            workbench.material_table.setItem(row, 3, QTableWidgetItem(tt("yes", workbench.lang) if material.get("trainable") else tt("no", workbench.lang)))
        workbench.material_table.resizeColumnsToContents()
        if workbench.material_table.rowCount() > 1:
                workbench.material_table.selectRow(1)
        elif workbench.material_table.rowCount() == 1:
            workbench.material_table.selectRow(0)
        self._update_current_material_summary()

    def _selected_material(self):
        workbench = self.workbench
        items = workbench.material_table.selectedItems()
        if not items:
            return None
        row = items[0].row()
        try:
            material_id = int(workbench.material_table.item(row, 1).text())
        except Exception:
            return None
        for material in self._active_materials():
            if int(material.get("id", -1)) == material_id:
                return dict(material)
        return None

    def _material_for_id(self, material_id):
        workbench = self.workbench
        try:
            target_id = int(material_id)
        except Exception:
            target_id = 0
        for material in self._active_materials():
            try:
                if int(material.get("id", -1)) == target_id:
                    return dict(material)
            except Exception:
                continue
        if target_id == 0:
            return {"id": 0, "name": "background", "display_name": tt("Background / erase target", workbench.lang), "color": "#000000", "trainable": False}
        return None

    def _material_display_name(self, material_id=None):
        workbench = self.workbench
        material = self._material_for_id(self.state.current_material_id if material_id is None else material_id)
        if material is None:
            return str(self.state.current_material_id if material_id is None else material_id)
        if int(material.get("id", 0)) == 0:
            return tt("Background / erase target", workbench.lang)
        return str(material.get("display_name") or material.get("name") or material.get("id", ""))

    def _material_color_text(self, material_id=None):
        workbench = self.workbench
        material = self._material_for_id(self.state.current_material_id if material_id is None else material_id) or {}
        return str(material.get("color", "#000000") or "#000000")

    def _set_current_material_id(self, material_id, select_row=True, show_message=False, picked=False):
        workbench = self.workbench
        try:
            material_id = int(material_id)
        except Exception:
            material_id = 0
        self.state.current_material_id = material_id
        if select_row and hasattr(workbench, "material_table"):
            for row in range(workbench.material_table.rowCount()):
                item = workbench.material_table.item(row, 1)
                if item is None:
                    continue
                try:
                    if int(item.text()) == material_id:
                        workbench.material_table.blockSignals(True)
                        workbench.material_table.selectRow(row)
                        workbench.material_table.blockSignals(False)
                        break
                except Exception:
                    continue
            workbench._select_label_schema_row_for_material(material_id)
        self._update_current_material_summary()
        if show_message:
            material = self._material_for_id(material_id)
            if material is None:
                message = tt("Sampled label {0}, but it is not in the current label table.", workbench.lang).format(material_id)
            else:
                name = self._material_display_name(material_id)
                template = "Picked label {0}: {1}." if picked else "Selected label {0}: {1}."
                message = tt(template, workbench.lang).format(material_id, name)
            workbench._set_operation_feedback(message)
        return material_id

    def _update_current_material_summary(self):
        workbench = self.workbench
        if not hasattr(workbench, "current_material_label"):
            return
        material_id = int(self.state.current_material_id)
        name = self._material_display_name(material_id)
        color_text = self._material_color_text(material_id)
        if workbench.annotation_tool_mode == "eraser":
            label_text = tt("Eraser writes background 0. Current label remains {0}: {1}.", workbench.lang).format(material_id, name)
        else:
            label_text = tt("Label {0}: {1}", workbench.lang).format(material_id, name)
        workbench.current_material_label.setText(label_text)
        workbench.current_material_label.setToolTip(label_text)
        workbench.current_material_swatch.setToolTip(color_text)
        workbench.current_material_swatch.setStyleSheet(
            "QLabel#tifCurrentMaterialSwatch {"
            f"background: {color_text};"
            "border: 2px solid #DCE4E8;"
            "border-radius: 8px;"
            "}"
        )

    def _material_map_path(self):
        workbench = self.workbench
        if workbench.current_volume_scope == "part":
            return ""
        specimen = workbench.project.get_specimen(workbench.current_specimen_id, default=None)
        if specimen is None:
            return ""
        return workbench.project.to_absolute(specimen.get("material_map", ""))

    def _save_material_map(self):
        workbench = self.workbench
        path = self._material_map_path()
        if not path:
            return
        self.state.material_map = write_material_map(path, self.state.material_map, source=self.state.material_map.get("source", "manual"))
        self._sync_material_colors_from_active_source()
        specimen = workbench.project.get_specimen(workbench.current_specimen_id, default=None)
        if specimen is not None:
            workbench._update_status_labels(specimen)
            self._populate_material_table()
            workbench._populate_result_region_combo()
            workbench._populate_volume_tint_combo()
        workbench.render_current_slice()

    def add_material(self):
        workbench = self.workbench
        if not workbench.current_specimen_id:
            return
        if workbench.current_volume_scope == "part":
            QMessageBox.information(workbench, tt("Label table", workbench.lang), tt("Edit the bound label schema above to add, rename, or recolor labels for this part/reslice.", workbench.lang))
            return
        dialog = MaterialEditorDialog(next_id=next_material_id(self.state.material_map), parent=workbench, lang=workbench.lang)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.state.material_map = upsert_material(self.state.material_map, dialog.get_material())
            self._save_material_map()
        except Exception as exc:
            QMessageBox.warning(workbench, tt("Material map", workbench.lang), str(exc))

    def edit_selected_material(self):
        workbench = self.workbench
        if workbench.current_volume_scope == "part":
            QMessageBox.information(workbench, tt("Label table", workbench.lang), tt("Edit the bound label schema above to add, rename, or recolor labels for this part/reslice.", workbench.lang))
            return
        material = self._selected_material()
        if material is None:
            return
        dialog = MaterialEditorDialog(material=material, parent=workbench, lang=workbench.lang)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.state.material_map = upsert_material(self.state.material_map, dialog.get_material())
            self._save_material_map()
        except Exception as exc:
            QMessageBox.warning(workbench, tt("Material map", workbench.lang), str(exc))

    def delete_selected_material(self):
        workbench = self.workbench
        if workbench.current_volume_scope == "part":
            QMessageBox.information(workbench, tt("Label table", workbench.lang), tt("Edit the bound label schema above to add, rename, or recolor labels for this part/reslice.", workbench.lang))
            return
        material = self._selected_material()
        if material is None:
            return
        material_id = int(material.get("id", -1))
        if material_id == 0:
            QMessageBox.warning(workbench, tt("Label table", workbench.lang), tt("Background material cannot be deleted.", workbench.lang))
            return
        if self._material_id_is_used(material_id):
            QMessageBox.warning(workbench, tt("Material map", workbench.lang), tt("Material {0} is still used by a label volume.", workbench.lang).format(material_id))
            return
        reply = QMessageBox.question(
            workbench,
            tt("Label table", workbench.lang),
            tt("Delete material {0} ({1})?", workbench.lang).format(material_id, material.get("display_name", material.get("name", ""))),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            self.state.material_map = remove_material(self.state.material_map, material_id)
            self._save_material_map()
        except Exception as exc:
            QMessageBox.warning(workbench, tt("Material map", workbench.lang), str(exc))

    def _material_id_is_used(self, material_id):
        workbench = self.workbench
        arrays = []
        if workbench.edit_volume is not None:
            arrays.append(workbench.edit_volume)
        if workbench.label_volume is not None:
            arrays.append(workbench.label_volume)
        specimen = workbench.project.get_specimen(workbench.current_specimen_id, default=None)
        if specimen is not None:
            label_records = []
            labels = specimen.get("labels") or {}
            label_records.extend([labels.get("manual_truth") or {}, labels.get("working_edit") or {}])
            label_records.extend(labels.get("model_drafts") or [])
            if workbench.current_volume_scope == "part":
                part_labels = ((workbench.current_part or {}).get("labels") or {})
                label_records.extend(
                    [
                        part_labels.get("manual_truth") or {},
                        part_labels.get("editable_ai_result") or {},
                        part_labels.get("raw_ai_prediction_backup") or {},
                    ]
                )
            for record in label_records:
                path = workbench.project.to_absolute((record or {}).get("path", ""))
                if path and volume_sidecar_exists(path):
                    try:
                        arrays.append(load_volume_sidecar(path, mmap_mode="r"))
                    except Exception:
                        pass
        for array in arrays:
            try:
                z_count = int(array.shape[0]) if getattr(array, "ndim", 0) == 3 else 0
                for z_index in range(z_count):
                    if np.any(np.asarray(array[z_index]) == int(material_id)):
                        return True
            except Exception:
                continue
        return False

    def _on_material_selected(self):
        workbench = self.workbench
        items = workbench.material_table.selectedItems()
        if not items:
            return
        row = items[0].row()
        try:
            material_id = int(workbench.material_table.item(row, 1).text())
        except Exception:
            material_id = 0
        self._set_current_material_id(material_id, select_row=False, show_message=not workbench._loading_specimen)

    def _current_part_mask_path(self):
        workbench = self.workbench
        if workbench.current_volume_scope != "part" or workbench.current_reslice_id:
            return ""
        part = workbench.project.get_part(workbench.current_specimen_id, workbench.current_part_id, default=None)
        mask_path = workbench.project.to_absolute(((part or {}).get("mask") or {}).get("path", ""))
        return mask_path if mask_path else ""

    def _part_mask_has_voxels(self):
        mask = self.state.part_mask_volume
        if mask is None:
            return False
        try:
            shape = tuple(int(value) for value in getattr(mask, "shape", ()) or ())
            if len(shape) < 3:
                return bool(np.any(np.asarray(mask) > 0))
            plane_values = max(1, int(np.prod(shape[1:])))
            z_chunk = max(1, min(int(shape[0]), int((16 * 1024 * 1024) / plane_values)))
            for z0 in range(0, int(shape[0]), z_chunk):
                z1 = min(int(shape[0]), z0 + z_chunk)
                if np.any(np.asarray(mask[z0:z1]) > 0):
                    return True
            return False
        except Exception:
            return False

    def _reload_part_mask_volume(self):
        workbench = self.workbench
        self.state.part_mask_volume = None
        if workbench.current_volume_scope != "part":
            return
        mask_path = self._current_part_mask_path()
        if mask_path and volume_sidecar_exists(mask_path):
            self.state.part_mask_volume, _load_issue = workbench.preview_controller.safe_load_volume_sidecar(mask_path, mmap_mode="r", operation="load_part_mask_volume")

    def copy_current_material_to_adjacent_slice(self, delta):
        workbench = self.workbench
        if not workbench._ensure_editable_working_edit_for_helper():
            return False
        material_id = int(self.state.current_material_id)
        if material_id == 0:
            workbench._set_operation_feedback(tt("Background label 0 is not supported by this helper.", workbench.lang))
            return False
        source_z = int(workbench.slice_slider.value())
        target_z = source_z + int(delta)
        if target_z < 0:
            workbench._set_operation_feedback(tt("No previous slice is available.", workbench.lang))
            return False
        if target_z >= int(workbench.edit_volume.shape[0]):
            workbench._set_operation_feedback(tt("No next slice is available.", workbench.lang))
            return False
        source_mask = np.asarray(workbench.edit_volume[source_z] == material_id)
        source_count = int(np.count_nonzero(source_mask))
        if source_count <= 0:
            workbench._set_operation_feedback(tt("No pixels of label {0} on slice {1}.", workbench.lang).format(material_id, source_z + 1))
            return False
        reply = QMessageBox.question(
            workbench,
            tt("Confirm label edit", workbench.lang),
            tt("Copy label {0} from slice {1} to slice {2}? Existing pixels of this label on the target slice will be replaced.", workbench.lang).format(
                material_id,
                source_z + 1,
                target_z + 1,
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return False
        target_slice = workbench.edit_volume[target_z]
        next_slice = np.asarray(target_slice).copy()
        next_slice[next_slice == material_id] = 0
        next_slice[source_mask] = material_id
        changed = int(np.count_nonzero(next_slice != target_slice))
        if changed <= 0:
            workbench._set_operation_feedback(tt("No label changes were needed on slice {0}.", workbench.lang).format(target_z + 1), log=False)
            return True
        workbench._push_undo_for_slice(target_z)
        workbench.edit_volume[target_z] = next_slice
        workbench.annotation_workflow_controller.mark_slice_dirty(target_z)
        workbench.annotation_workflow_controller.mark_working_edit_dirty()
        workbench.slice_slider.setValue(target_z)
        workbench.render_current_slice()
        message = tt("Copied label {0} from slice {1} to slice {2}: {3} changed pixel(s).", workbench.lang).format(
            material_id,
            source_z + 1,
            target_z + 1,
            changed,
        )
        workbench._set_operation_feedback(message, log=False)
        return True

    def clear_current_material_on_slice(self):
        workbench = self.workbench
        if not workbench._ensure_editable_working_edit_for_helper():
            return False
        material_id = int(self.state.current_material_id)
        if material_id == 0:
            workbench._set_operation_feedback(tt("Background label 0 is not supported by this helper.", workbench.lang))
            return False
        z_index = int(workbench.slice_slider.value())
        mask = np.asarray(workbench.edit_volume[z_index] == material_id)
        count = int(np.count_nonzero(mask))
        if count <= 0:
            workbench._set_operation_feedback(tt("No pixels of label {0} on slice {1}.", workbench.lang).format(material_id, z_index + 1))
            return False
        reply = QMessageBox.question(
            workbench,
            tt("Confirm label edit", workbench.lang),
            tt("Clear label {0} from slice {1}?", workbench.lang).format(material_id, z_index + 1),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return False
        workbench._push_undo_for_slice(z_index)
        workbench.edit_volume[z_index][mask] = 0
        workbench.annotation_workflow_controller.mark_slice_dirty(z_index)
        workbench.annotation_workflow_controller.mark_working_edit_dirty()
        workbench.render_current_slice()
        message = tt("Cleared label {0} on slice {1}: {2} pixel(s).", workbench.lang).format(material_id, z_index + 1, count)
        workbench._set_operation_feedback(message, log=False)
        return True

    def _sample_label_volume(self):
        workbench = self.workbench
        if workbench.current_volume_scope == "part":
            if workbench.label_role_combo.currentData() == "editable_ai_result" and workbench.edit_volume is not None and workbench.edit_volume.shape == workbench.image_volume.shape:
                return workbench.edit_volume
            if workbench.label_volume is not None and workbench.label_volume.shape == workbench.image_volume.shape:
                return workbench.label_volume
            return None
        if workbench.label_role_combo.currentData() == "working_edit" and workbench.edit_volume is not None and workbench.edit_volume.shape == workbench.image_volume.shape:
            return workbench.edit_volume
        if workbench.label_volume is not None and workbench.label_volume.shape == workbench.image_volume.shape:
            return workbench.label_volume
        if workbench.edit_volume is not None and workbench.edit_volume.shape == workbench.image_volume.shape:
            return workbench.edit_volume
        return None

    def pick_material_at_widget_position(self, x, y):
        workbench = self.workbench
        if workbench.image_volume is None:
            return
        if workbench.display_mode == "volume":
            workbench._set_operation_feedback(tt("3D volume preview is read-only. Switch to Slice review for label editing.", workbench.lang))
            return
        if workbench._current_slice_axis() != "z":
            workbench._set_operation_feedback(tt("Label picker is available on Z slices only. Switch back to Z axial view before sampling labels.", workbench.lang))
            return
        sample_volume = self._sample_label_volume()
        if sample_volume is None:
            workbench._set_operation_feedback(tt("No label layer is loaded to sample from.", workbench.lang))
            return
        z_index = int(workbench.slice_slider.value())
        height, width = workbench.image_volume.shape[1], workbench.image_volume.shape[2]
        pixel = workbench._widget_to_image_pixel(x, y, width, height)
        if pixel is None:
            return
        px, py = pixel
        try:
            material_id = int(np.asarray(sample_volume[z_index])[py, px])
        except Exception:
            workbench._set_operation_feedback(tt("No label layer is loaded to sample from.", workbench.lang))
            return
        self._set_current_material_id(material_id, select_row=True, show_message=True, picked=True)

    def _save_part_mask_edit(self, show_message=True, reason="manual"):
        workbench = self.workbench
        if not workbench._is_editable_part_volume():
            return False
        specimen = workbench.project.get_specimen(workbench.current_specimen_id, default=None)
        part = workbench.project.get_part(workbench.current_specimen_id, workbench.current_part_id, default=None)
        if specimen is None or part is None or workbench.edit_volume is None:
            return False
        mask_path = self._current_part_mask_path()
        if not mask_path:
            return False
        workbench._saving_working_edit = True
        workbench.auto_save_timer.stop()
        workbench._update_save_status(state="saving")
        try:
            target = load_volume_sidecar(mask_path, mmap_mode="r+")
            if workbench._dirty_edit_slices:
                for z_index in sorted(workbench._dirty_edit_slices):
                    if 0 <= int(z_index) < int(target.shape[0]):
                        target[int(z_index)] = workbench.edit_volume[int(z_index)]
            metadata = flush_volume_array(mask_path, target)
            mask_record = part.setdefault("mask", {})
            mask_record["dtype"] = metadata["dtype"]
            mask_record["shape_zyx"] = metadata["shape_zyx"]
            mask_record["spacing_zyx"] = metadata.get("spacing_zyx", mask_record.get("spacing_zyx", [1.0, 1.0, 1.0]))
            mask_record["spacing_unit"] = metadata.get("spacing_unit", mask_record.get("spacing_unit", "micrometer"))
            mask_record["orientation"] = metadata.get("orientation", mask_record.get("orientation", "unknown"))
            mask_record["format"] = metadata.get("format", mask_record.get("format", ""))
            mask_record["status"] = "in_progress"
            part["status"] = "mask_in_progress"
            workbench.project.save_project()
            workbench.annotation_workflow_controller.reset_dirty_tracking()
            workbench.edit_volume = load_volume_sidecar(mask_path, mmap_mode="c")
            self.state.part_mask_volume = load_volume_sidecar(mask_path, mmap_mode="r")
            workbench._reload_label_volume()
            workbench._update_status_labels(specimen, part=part)
            workbench._update_save_status()
        except Exception as exc:
            workbench.annotation_workflow_controller.set_dirty(True)
            message = tt("Save failed: {0}", workbench.lang).format(str(exc))
            workbench._set_operation_feedback(message)
            workbench._update_save_status(state="failed", detail=str(exc))
            QMessageBox.warning(workbench, tt("Unsaved working edit", workbench.lang), str(exc))
            return False
        finally:
            workbench._saving_working_edit = False
            workbench._update_save_status()
        if show_message:
            message = tt("Auto-saved part mask.", workbench.lang) if reason == "auto_save" else tt("Part mask saved.", workbench.lang)
            workbench._set_operation_feedback(message)
        return True

    def _materialize_task_matches(self, specimen_id=""):
        workbench = self.workbench
        specimen_id = str(specimen_id or workbench.current_specimen_id or "")
        return bool(
            self.materialize_thread is not None
            and specimen_id
            and str(self.materialize_specimen_id or "") == specimen_id
        )

    def _cleanup_tif_materialize_thread(self):
        workbench = self.workbench
        if self.materialize_progress is not None:
            self.materialize_progress.close()
            self.materialize_progress.deleteLater()
        self.materialize_progress = None
        self.materialize_worker = None
        self.materialize_thread = None
        self.materialize_specimen_id = ""
        self.materialize_task_id = ""

    def _on_tif_materialize_progress(self, current, total, message):
        workbench = self.workbench
        workbench._progress_tif_task(self.materialize_task_id, current, total, str(message or ""))
        if self.materialize_progress is None:
            return
        maximum = max(1, int(total or 100))
        value = max(0, min(maximum, int(current or 0)))
        self.materialize_progress.setMaximum(maximum)
        self.materialize_progress.setValue(value)
        self.materialize_progress.setLabelText(tt(message, workbench.lang))

    def _on_tif_materialize_finished(self, result):
        workbench = self.workbench
        specimen_id = self.materialize_specimen_id
        report_path = result.get("report_path", "") if isinstance(result, dict) else ""
        thread = self.materialize_thread
        task_id = self.materialize_task_id
        task_current = workbench._task_context_matches_current(task_id, fields=("specimen_id",))
        workbench._finish_tif_task(task_id, payload=result if isinstance(result, dict) else {}, message="tif_materialize_finished")
        self._cleanup_tif_materialize_thread()
        if thread is not None:
            thread.quit()
        workbench.refresh_project(reload_current=False)
        if specimen_id and task_current:
            workbench.selection_workflow_controller.select_payload({"specimen_id": specimen_id, "scope": "full"})
        message = tt("Working volume ready for specimen {0}. Report: {1}", workbench.lang).format(specimen_id, report_path)
        if specimen_id and not task_current:
            message = f"{message} {tt('Current view was left unchanged because you switched context while it was running.', workbench.lang)}"
        else:
            workbench.training_status_label.setText(message)
        workbench.log(message)

    def _on_tif_materialize_failed(self, message):
        workbench = self.workbench
        thread = self.materialize_thread
        specimen_id = self.materialize_specimen_id
        task_id = self.materialize_task_id
        task_current = workbench._task_context_matches_current(task_id, fields=("specimen_id",))
        workbench._fail_tif_task(task_id, str(message or ""), message=str(message or ""))
        self._cleanup_tif_materialize_thread()
        if thread is not None:
            thread.quit()
        workbench.refresh_project(reload_current=False)
        if specimen_id and task_current:
            workbench.selection_workflow_controller.select_payload({"specimen_id": specimen_id, "scope": "full"})
            QMessageBox.critical(workbench, tt("Build working volume", workbench.lang), message)
        else:
            workbench.log(f"Working volume build failed for {specimen_id}: {message}")

    def materialize_current_tif_metadata(self):
        workbench = self.workbench
        if not workbench.current_specimen_id:
            return False
        specimen = workbench.project.get_specimen(workbench.current_specimen_id, default=None)
        if not workbench._is_metadata_only_specimen(specimen):
            return False
        if self.materialize_thread is not None:
            QMessageBox.information(workbench, tt("Build working volume", workbench.lang), tt("Working volume build is already running.", workbench.lang))
            return True
        self.materialize_specimen_id = workbench.current_specimen_id
        task = workbench._start_tif_task(
            "tif_materialize",
            action="materialize_working_volume",
            payload={"specimen_id": workbench.current_specimen_id},
            request_key=workbench.current_specimen_id,
            message=tt("Building working volume...", workbench.lang),
        )
        self.materialize_task_id = task.task_id
        self.materialize_progress = QProgressDialog(
            tt("Building working volume...", workbench.lang),
            "",
            0,
            100,
            workbench,
        )
        self.materialize_progress.setWindowTitle(tt("Build working volume", workbench.lang))
        self.materialize_progress.setCancelButton(None)
        self.materialize_progress.setAutoClose(False)
        self.materialize_progress.setAutoReset(False)
        self.materialize_progress.setWindowModality(Qt.WindowModal)
        self.materialize_progress.show()

        self.materialize_thread = QThread(workbench)
        self.materialize_worker = TifMaterializeWorker(workbench.project, workbench.current_specimen_id)
        self.materialize_worker.moveToThread(self.materialize_thread)
        self.materialize_thread.started.connect(self.materialize_worker.run)
        self.materialize_worker.progress.connect(self._on_tif_materialize_progress)
        self.materialize_worker.finished.connect(self._on_tif_materialize_finished)
        self.materialize_worker.failed.connect(self._on_tif_materialize_failed)
        self.materialize_worker.finished.connect(self.materialize_thread.quit)
        self.materialize_worker.failed.connect(self.materialize_thread.quit)
        self.materialize_thread.finished.connect(self.materialize_worker.deleteLater)
        self.materialize_thread.finished.connect(self.materialize_thread.deleteLater)
        self.materialize_thread.start()
        return True

    def _ensure_current_metadata_materializing_for_slice_review(self, specimen=None):
        workbench = self.workbench
        if workbench.display_mode == "volume" or not workbench.current_specimen_id:
            return False
        specimen = specimen if specimen is not None else workbench.project.get_specimen(workbench.current_specimen_id, default=None)
        if not workbench._is_metadata_only_specimen(specimen):
            return False
        source_path = str((specimen.get("metadata") or {}).get("source_tif") or (specimen.get("source") or {}).get("raw_tif") or "")
        if not source_path:
            return False
        if self._materialize_task_matches(workbench.current_specimen_id):
            message = tt("Working volume is being built. Slice review will be available when it finishes.", workbench.lang)
            workbench._set_slice_review_unavailable(message)
            workbench.training_status_label.setText(message)
            return True
        if self.materialize_thread is not None:
            return False
        if self.materialize_current_tif_metadata():
            message = tt("Working volume is being built. Slice review will be available when it finishes.", workbench.lang)
            workbench._set_slice_review_unavailable(message)
            workbench.training_status_label.setText(message)
            workbench.log(message)
            return True
        return False
