from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import QDialog, QMessageBox, QProgressDialog

try:
    from AntSleap.ui.tif_workbench_dialogs import TifPartNameDialog
    from AntSleap.ui.tif_workbench_translations import tt
    from AntSleap.ui.tif_workbench_workers import TifConfirmPartRoiWorker
except ModuleNotFoundError as exc:
    if exc.name != "AntSleap":
        raise
    from ui.tif_workbench_dialogs import TifPartNameDialog
    from ui.tif_workbench_translations import tt
    from ui.tif_workbench_workers import TifConfirmPartRoiWorker


@dataclass
class TifRoiWorkflowState:
    active_roi_id: str = ""
    keyframes: list[dict] = field(default_factory=list)
    draw_mode: bool = False
    confirm_task_id: str = ""
    confirm_request: dict = field(default_factory=dict)


class TifRoiWorkflowController:
    VIEW_SCOPE = "roi_to_part"
    BACKGROUND_VOXEL_THRESHOLD = 1_000_000

    def __init__(self, workbench):
        self.workbench = workbench
        self.state = TifRoiWorkflowState()
        self.confirm_thread = None
        self.confirm_worker = None
        self.confirm_progress = None

    def initialize_compatibility_state(self):
        self.reset_state()

    def reset_state(self):
        self.state = TifRoiWorkflowState()
        return self.state

    def is_confirm_running(self):
        return self.confirm_thread is not None

    def bind_signals(self):
        view = self.workbench.workbench_view
        view.register_scope(
            self.VIEW_SCOPE,
            "part_bbox_edit",
            "btn_part_draw_roi",
            "btn_save_part_roi",
            "btn_confirm_part_roi",
            "btn_cancel_part_roi",
        )
        router = self.workbench.signal_router
        bindings = (
            ("bbox_changed", "part_bbox_edit", "textChanged", self.on_bbox_text_changed),
            ("draw_mode", "btn_part_draw_roi", "toggled", self.set_draw_mode),
            ("save_draft", "btn_save_part_roi", "clicked", self.save_draft),
            ("confirm", "btn_confirm_part_roi", "clicked", self.confirm_to_part),
            ("cancel", "btn_cancel_part_roi", "clicked", self.cancel_draft),
        )
        for key, widget_name, signal_name, slot in bindings:
            signal = getattr(view.require(self.VIEW_SCOPE, widget_name), signal_name)
            router.bind(self.VIEW_SCOPE, key, signal, slot)

    def default_roi_id(self):
        workbench = self.workbench
        existing = len(workbench.project.list_part_rois(workbench.current_specimen_id, include_cancelled=True)) if workbench.current_specimen_id else 0
        return f"roi_{existing + 1:03d}"

    def parse_bbox_text(self):
        workbench = self.workbench
        text = workbench.part_bbox_edit.text().strip()
        if not text:
            return []
        chunks = [chunk.strip() for chunk in text.replace(";", ",").split(",") if chunk.strip()]
        if len(chunks) != 6:
            raise ValueError("bbox_must_be_z0_z1_y0_y1_x0_x1")
        values = [int(chunk) for chunk in chunks]
        return [[values[0], values[1]], [values[2], values[3]], [values[4], values[5]]]

    def empty_bbox_for_drag(self):
        workbench = self.workbench
        if workbench.image_volume is None:
            return []
        return [[0, 0], [0, 0], [0, 0]]

    def normalize_keyframes(self, keyframes, shape=None):
        workbench = self.workbench
        shape = tuple(int(value) for value in (shape or getattr(workbench.image_volume, "shape", ()) or ()))
        normalized = []
        for item in keyframes or []:
            if not isinstance(item, dict):
                continue
            axis = str(item.get("axis") or "z")
            if axis not in {"z", "y", "x"}:
                continue
            try:
                slice_index = int(item.get("slice_index"))
                rect = [int(value) for value in item.get("rect", [])]
            except Exception:
                continue
            if len(rect) != 4:
                continue
            x0, y0, x1, y1 = rect
            if len(shape) == 3:
                if axis == "z":
                    max_slice, height, width = shape[0], shape[1], shape[2]
                elif axis == "y":
                    max_slice, height, width = shape[1], shape[0], shape[2]
                else:
                    max_slice, height, width = shape[2], shape[0], shape[1]
                if not (0 <= slice_index < max_slice):
                    continue
                x0, x1 = sorted((max(0, min(width, x0)), max(0, min(width, x1))))
                y0, y1 = sorted((max(0, min(height, y0)), max(0, min(height, y1))))
            else:
                x0, x1 = sorted((x0, x1))
                y0, y1 = sorted((y0, y1))
            if x1 <= x0 or y1 <= y0:
                continue
            normalized.append(
                {
                    "axis": axis,
                    "slice_index": slice_index,
                    "rect": [x0, y0, x1, y1],
                    "source": str(item.get("source") or "manual_rectangle"),
                }
            )
        normalized.sort(key=lambda item: (item["axis"], item["slice_index"]))
        return normalized

    def keyframe_bbox(self, keyframes, shape=None):
        workbench = self.workbench
        shape = tuple(int(value) for value in (shape or getattr(workbench.image_volume, "shape", ()) or ()))
        if len(shape) != 3:
            return []
        bbox = [[0, 0], [0, 0], [0, 0]]
        for item in self.normalize_keyframes(keyframes, shape):
            axis = item["axis"]
            index = int(item["slice_index"])
            x0, y0, x1, y1 = [int(value) for value in item["rect"]]
            if axis == "z":
                bbox[0] = workbench._expanded_axis_range(bbox[0], index, shape[0])
                bbox[1] = workbench._union_axis_range(bbox[1], y0, y1, shape[1])
                bbox[2] = workbench._union_axis_range(bbox[2], x0, x1, shape[2])
            elif axis == "y":
                bbox[0] = workbench._union_axis_range(bbox[0], y0, y1, shape[0])
                bbox[1] = workbench._expanded_axis_range(bbox[1], index, shape[1])
                bbox[2] = workbench._union_axis_range(bbox[2], x0, x1, shape[2])
            elif axis == "x":
                bbox[0] = workbench._union_axis_range(bbox[0], y0, y1, shape[0])
                bbox[1] = workbench._union_axis_range(bbox[1], x0, x1, shape[1])
                bbox[2] = workbench._expanded_axis_range(bbox[2], index, shape[2])
        if any(int(pair[1]) <= int(pair[0]) for pair in bbox):
            return []
        return workbench._clip_bbox_to_shape(bbox, shape)

    def keyframes_from_bbox_for_axis(self, bbox, axis):
        workbench = self.workbench
        bbox = workbench._clip_bbox_to_shape(bbox, workbench.image_volume.shape) if workbench.image_volume is not None else bbox
        if not bbox or len(bbox) != 3:
            return []
        axis = axis if axis in {"z", "y", "x"} else "z"
        z_range, y_range, x_range = bbox
        if axis == "z":
            start, end = int(z_range[0]), int(z_range[1]) - 1
            rect = [int(x_range[0]), int(y_range[0]), int(x_range[1]), int(y_range[1])]
        elif axis == "y":
            start, end = int(y_range[0]), int(y_range[1]) - 1
            rect = [int(x_range[0]), int(z_range[0]), int(x_range[1]), int(z_range[1])]
        else:
            start, end = int(x_range[0]), int(x_range[1]) - 1
            rect = [int(y_range[0]), int(z_range[0]), int(y_range[1]), int(z_range[1])]
        if end < start:
            return []
        keyframes = [{"axis": axis, "slice_index": start, "rect": list(rect), "source": "bbox_compat"}]
        if end != start:
            keyframes.append({"axis": axis, "slice_index": end, "rect": list(rect), "source": "bbox_compat"})
        return self.normalize_keyframes(keyframes)

    def upsert_keyframe(self, axis, slice_index, rect):
        workbench = self.workbench
        axis = axis if axis in {"z", "y", "x"} else "z"
        keyframes = self.normalize_keyframes(self.state.keyframes)
        if not keyframes:
            try:
                bbox = self.parse_bbox_text()
            except Exception:
                bbox = []
            if bbox:
                keyframes = self.keyframes_from_bbox_for_axis(bbox, axis)
        axes = {item["axis"] for item in keyframes}
        if axes and axis not in axes:
            message = tt("ROI key slices use one view plane. Switch back to {0} or save a separate ROI.", workbench.lang).format(sorted(axes)[0].upper())
            QMessageBox.information(workbench, tt("Part extraction", workbench.lang), message)
            workbench.training_status_label.setText(message)
            workbench.log(message)
            return [], []
        keyframes = [
            item
            for item in keyframes
            if not (item["axis"] == axis and int(item["slice_index"]) == int(slice_index))
        ]
        keyframes.append({"axis": axis, "slice_index": int(slice_index), "rect": [int(value) for value in rect], "source": "manual_rectangle"})
        keyframes = self.normalize_keyframes(keyframes)
        bbox = self.keyframe_bbox(keyframes)
        if bbox:
            self.state.keyframes = keyframes
        return keyframes, bbox

    def keyframe_projection_for_current_slice(self, keyframes):
        workbench = self.workbench
        axis, index = workbench._active_slice_position()
        same_axis = [
            item
            for item in self.normalize_keyframes(keyframes)
            if item.get("axis") == axis
        ]
        if not same_axis:
            return None
        same_axis.sort(key=lambda item: int(item.get("slice_index", 0)))
        index = int(index)
        if index < int(same_axis[0]["slice_index"]) or index > int(same_axis[-1]["slice_index"]):
            return None
        for item in same_axis:
            if int(item["slice_index"]) == index:
                return list(item["rect"])
        left = None
        right = None
        for item in same_axis:
            if int(item["slice_index"]) < index:
                left = item
            elif int(item["slice_index"]) > index and right is None:
                right = item
                break
        if left is None or right is None:
            return None
        left_index = int(left["slice_index"])
        right_index = int(right["slice_index"])
        if right_index <= left_index:
            return None
        weight = float(index - left_index) / float(right_index - left_index)
        values = []
        for left_value, right_value in zip(left["rect"], right["rect"]):
            values.append(int(round((1.0 - weight) * float(left_value) + weight * float(right_value))))
        if values[2] <= values[0] or values[3] <= values[1]:
            return None
        return values

    def is_draw_mode(self):
        workbench = self.workbench
        return bool(
            self.state.draw_mode
            and workbench.current_volume_scope == "full"
            and workbench.display_mode == "slice"
            and workbench.image_volume is not None
        )

    def current_overlay_rects(self):
        workbench = self.workbench
        if workbench.current_volume_scope != "full" or workbench.image_volume is None:
            return []
        overlays = []
        try:
            bbox = self.parse_bbox_text()
        except Exception:
            bbox = []
        current_rect = self.keyframe_projection_for_current_slice(self.state.keyframes)
        if current_rect:
            overlays.append({"rect": current_rect, "color": "#FFD34D", "kind": "current"})
        elif bbox and len(bbox) == 3:
            current_rect = workbench._bbox_projection_for_current_slice(bbox)
            if current_rect:
                overlays.append({"rect": current_rect, "color": "#FFD34D", "kind": "current"})
        specimen = workbench.project.get_specimen(workbench.current_specimen_id, default=None) if workbench.current_specimen_id else None
        for roi in (specimen or {}).get("part_rois", []) or []:
            if (roi or {}).get("status") == "cancelled":
                continue
            rect = self.keyframe_projection_for_current_slice(((roi or {}).get("metadata") or {}).get("roi_keyframes", []))
            if not rect:
                rect = workbench._bbox_projection_for_current_slice((roi or {}).get("bbox_zyx", []))
            if rect:
                color = "#42D9C8" if (roi or {}).get("status") in {"draft", "confirmed"} else "#7EE787"
                overlays.append({"rect": rect, "color": color, "kind": "roi", "roi_id": (roi or {}).get("roi_id", "")})
        for part in (specimen or {}).get("parts", []) or []:
            rect = workbench._bbox_projection_for_current_slice((part or {}).get("parent_bbox_zyx", []))
            if rect:
                overlays.append({"rect": rect, "color": "#7EE787", "kind": "part", "part_id": (part or {}).get("part_id", "")})
        return overlays

    def finish_drag(self, start_x, start_y, end_x, end_y):
        workbench = self.workbench
        if not self.is_draw_mode() or workbench.image_volume is None:
            return
        axis = workbench._current_slice_axis()
        start_pixel = workbench.canvas.widget_to_image_pixel(start_x, start_y)
        end_pixel = workbench.canvas.widget_to_image_pixel(end_x, end_y)
        if start_pixel is None or end_pixel is None:
            return
        x0 = min(int(start_pixel[0]), int(end_pixel[0]))
        x1 = max(int(start_pixel[0]), int(end_pixel[0])) + 1
        y0 = min(int(start_pixel[1]), int(end_pixel[1]))
        y1 = max(int(start_pixel[1]), int(end_pixel[1])) + 1
        if x1 - x0 < 2 or y1 - y0 < 2:
            return
        slice_index = int(workbench.slice_slider.value())
        keyframes, bbox = self.upsert_keyframe(axis, slice_index, [x0, y0, x1, y1])
        if not bbox:
            return
        workbench.part_bbox_edit.setText(workbench._bbox_text(bbox))
        autosaved_roi = self.autosave_active_bbox(bbox)
        if autosaved_roi is not None:
            message = tt("ROI bbox updated and saved to draft {0}: {1}", workbench.lang).format(
                autosaved_roi.get("display_name") or autosaved_roi.get("roi_id"),
                workbench.part_bbox_edit.text(),
            )
        else:
            message = tt("ROI bbox updated: {0}", workbench.lang).format(workbench.part_bbox_edit.text())
        workbench.training_status_label.setText(message)
        workbench.log(message)
        workbench.render_current_slice()

    def autosave_active_bbox(self, bbox):
        workbench = self.workbench
        if not self.state.active_roi_id or not workbench.current_specimen_id:
            return None
        roi = workbench.project.get_part_roi(workbench.current_specimen_id, self.state.active_roi_id, default=None)
        if roi is None or roi.get("linked_part_id") or roi.get("status") == "part_created":
            return None
        try:
            updated = workbench.project.update_part_roi(
                workbench.current_specimen_id,
                self.state.active_roi_id,
                bbox_zyx=bbox,
                status="draft",
                metadata=workbench._roi_keyframe_metadata(),
                save=True,
            )
        except Exception as exc:
            workbench.log(f"Failed to auto-save ROI draft {self.state.active_roi_id}: {exc}")
            return None
        workbench._populate_volume_roi_source_combo()
        return updated

    def on_bbox_text_changed(self, *_args):
        self.workbench.render_current_slice()

    def disable_draw_mode(self):
        self.state.draw_mode = False
        button = getattr(self.workbench, "btn_part_draw_roi", None)
        if button is not None and button.isChecked():
            button.blockSignals(True)
            button.setChecked(False)
            button.blockSignals(False)

    def set_draw_mode(self, checked):
        workbench = self.workbench
        self.state.draw_mode = bool(checked)
        if self.state.draw_mode:
            workbench.part_mask_workflow_controller.disable_contour_draw_mode()
            workbench.btn_draw_part_contour.blockSignals(True)
            workbench.btn_draw_part_contour.setChecked(False)
            workbench.btn_draw_part_contour.blockSignals(False)
            if workbench.current_volume_scope != "full" or workbench.image_volume is None:
                self.state.draw_mode = False
                workbench.btn_part_draw_roi.blockSignals(True)
                workbench.btn_part_draw_roi.setChecked(False)
                workbench.btn_part_draw_roi.blockSignals(False)
                QMessageBox.information(workbench, tt("Part extraction", workbench.lang), tt("Switch to Full volume before drawing ROI.", workbench.lang))
                return
            message = tt("Drag rectangles on one or more key slices in the current view plane. The ROI bbox will expand to include them.", workbench.lang)
            workbench.training_status_label.setText(message)
            workbench.log(message)
        workbench.render_current_slice()

    def load_draft(self, roi):
        workbench = self.workbench
        self.state.active_roi_id = str((roi or {}).get("roi_id", "") or "")
        metadata = (roi or {}).get("metadata") or {}
        self.state.keyframes = self.normalize_keyframes(metadata.get("roi_keyframes", []))
        workbench.part_mask_workflow_controller.load_roi_draft_keyframes(metadata.get("part_mask_keyframes", []))
        workbench.part_bbox_edit.setText(workbench._bbox_text((roi or {}).get("bbox_zyx", [])))

    def save_draft(self, *_args):
        workbench = self.workbench
        if not workbench.coordinator.guard_backend_write_lock():
            return None
        if workbench.current_volume_scope != "full" or not workbench.current_specimen_id or workbench.image_volume is None:
            QMessageBox.information(workbench, tt("Part extraction", workbench.lang), tt("Switch to Full volume before saving ROI draft.", workbench.lang))
            return None
        try:
            bbox = workbench._current_part_bbox_for_action()
        except Exception as exc:
            QMessageBox.warning(workbench, tt("Part extraction", workbench.lang), str(exc))
            return None
        if self.state.active_roi_id:
            roi = workbench.project.update_part_roi(
                workbench.current_specimen_id,
                self.state.active_roi_id,
                bbox_zyx=bbox,
                status="draft",
                metadata=workbench._roi_keyframe_metadata(),
            )
        else:
            roi_id = self.default_roi_id()
            dialog = TifPartNameDialog(
                "Save ROI draft",
                part_id=roi_id,
                display_name=roi_id,
                parent=workbench,
                lang=workbench.lang,
                id_label="ROI ID:",
            )
            if dialog.exec() != QDialog.Accepted:
                return None
            roi_id, display_name = dialog.values()
            if not str(roi_id).strip():
                return None
            try:
                roi = workbench.project.add_part_roi(
                    workbench.current_specimen_id,
                    roi_id,
                    display_name=display_name or roi_id,
                    bbox_zyx=bbox,
                    status="draft",
                    metadata=workbench._roi_keyframe_metadata(),
                )
            except Exception as exc:
                QMessageBox.warning(workbench, tt("Part extraction", workbench.lang), str(exc))
                return None
        self.load_draft(roi)
        workbench._populate_volume_roi_source_combo()
        message = tt("Saved ROI draft {0}.", workbench.lang).format(roi.get("display_name") or roi.get("roi_id"))
        workbench.training_status_label.setText(message)
        workbench.log(message)
        workbench.render_current_slice()
        return roi

    def cancel_draft(self, *_args):
        workbench = self.workbench
        if not workbench.coordinator.guard_backend_write_lock():
            return
        if not self.state.active_roi_id:
            workbench.part_bbox_edit.clear()
            self.state.keyframes = []
            workbench.part_mask_workflow_controller.clear_roi_draft_keyframes()
            workbench.render_current_slice()
            return
        roi = workbench.project.get_part_roi(workbench.current_specimen_id, self.state.active_roi_id, default=None)
        if roi is not None and roi.get("linked_part_id"):
            QMessageBox.information(workbench, tt("Part extraction", workbench.lang), tt("This ROI is linked to a created part and cannot be cancelled here.", workbench.lang))
            return
        roi_id = self.state.active_roi_id
        workbench.project.discard_part_roi(workbench.current_specimen_id, roi_id)
        message = tt("Cancelled ROI draft {0}.", workbench.lang).format(roi_id)
        self.state.active_roi_id = ""
        self.state.keyframes = []
        workbench.part_bbox_edit.clear()
        workbench.part_mask_workflow_controller.clear_roi_draft_keyframes()
        workbench.training_status_label.setText(message)
        workbench.log(message)
        workbench.render_current_slice()

    def cleanup_confirm_thread(self):
        workbench = self.workbench
        if self.confirm_progress is not None:
            self.confirm_progress.close()
            self.confirm_progress.deleteLater()
        self.confirm_progress = None
        self.confirm_worker = None
        self.confirm_thread = None
        self.state.confirm_request = {}
        self.state.confirm_task_id = ""
        workbench._set_scope_controls_enabled()

    def on_confirm_progress(self, current, total, message):
        workbench = self.workbench
        workbench._progress_tif_task(self.state.confirm_task_id, current, total, str(message or ""))
        progress = self.confirm_progress
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
        if workbench._task_context_matches_current(
            self.state.confirm_task_id,
            fields=("specimen_id", "volume_scope", "part_id"),
        ):
            workbench.training_status_label.setText(tt(message, workbench.lang))

    def on_confirm_finished(self, result):
        workbench = self.workbench
        result = dict(result or {})
        thread = self.confirm_thread
        task_id = self.state.confirm_task_id
        task_current = workbench._task_context_matches_current(task_id, fields=("specimen_id", "volume_scope", "part_id"))
        workbench._finish_tif_task(task_id, payload=result, message="confirm_part_roi_finished")
        self.cleanup_confirm_thread()
        if thread is not None:
            thread.quit()
        if not task_current:
            workbench.refresh_project(reload_current=False)
            part_id = str(result.get("part_id") or "")
            message = tt("Part volume {0} was created, but current view was left unchanged because you switched context while it was running.", workbench.lang).format(part_id)
            workbench.log(message)
            return
        self.finish_confirm_result(result)

    def on_confirm_failed(self, result):
        workbench = self.workbench
        result = dict(result or {})
        thread = self.confirm_thread
        message = str(result.get("error") or "")
        task_id = self.state.confirm_task_id
        task_current = workbench._task_context_matches_current(task_id, fields=("specimen_id", "volume_scope", "part_id"))
        workbench._fail_tif_task(task_id, message, payload=result)
        self.cleanup_confirm_thread()
        if thread is not None:
            thread.quit()
        if message and task_current:
            workbench.training_status_label.setText(message)
            workbench.log(f"Failed to confirm ROI: {message}")
            QMessageBox.warning(workbench, tt("Part extraction", workbench.lang), message)

    def start_confirm_worker(self, request):
        workbench = self.workbench
        if self.confirm_thread is not None:
            QMessageBox.information(workbench, tt("Part extraction", workbench.lang), tt("Part volume creation is already running.", workbench.lang))
            return False
        self.state.confirm_request = dict(request or {})
        task = workbench._start_tif_task(
            "confirm_part_roi",
            action="confirm_part_roi",
            payload={"request": dict(request or {})},
            request_key=workbench._task_request_key((request or {}).get("bbox_zyx") or (request or {}).get("part_id") or ""),
            message=tt("Part volume creation is running. Wait until it finishes before editing project data.", workbench.lang),
        )
        self.state.confirm_task_id = task.task_id
        self.confirm_progress = QProgressDialog(tt("Creating part volume...", workbench.lang), "", 0, 0, workbench)
        self.confirm_progress.setWindowTitle(tt("Part extraction", workbench.lang))
        self.confirm_progress.setCancelButton(None)
        self.confirm_progress.setAutoClose(False)
        self.confirm_progress.setAutoReset(False)
        self.confirm_progress.setMinimumDuration(0)
        self.confirm_progress.setWindowModality(Qt.WindowModal)
        self.confirm_progress.show()
        self.confirm_thread = QThread(workbench)
        self.confirm_worker = TifConfirmPartRoiWorker(workbench.project, request)
        self.confirm_worker.moveToThread(self.confirm_thread)
        self.confirm_thread.started.connect(self.confirm_worker.run)
        self.confirm_worker.progress.connect(self.on_confirm_progress)
        self.confirm_worker.finished.connect(self.on_confirm_finished)
        self.confirm_worker.failed.connect(self.on_confirm_failed)
        self.confirm_worker.finished.connect(self.confirm_thread.quit)
        self.confirm_worker.failed.connect(self.confirm_thread.quit)
        self.confirm_thread.finished.connect(self.confirm_worker.deleteLater)
        self.confirm_thread.finished.connect(self.confirm_thread.deleteLater)
        workbench._set_scope_controls_enabled()
        workbench.training_status_label.setText(tt("Creating part volume...", workbench.lang))
        self.confirm_thread.start()
        return True

    def request_voxel_count(self, request):
        return self.workbench.roi_part_service.request_voxel_count(request)

    def should_confirm_in_background(self, request):
        return self.workbench.roi_part_service.should_run_in_background(request, threshold=self.BACKGROUND_VOXEL_THRESHOLD)

    def build_confirm_request(self, roi, bbox, part_id, display_name, roi_keyframes, mask_contours, mask_bbox):
        workbench = self.workbench
        result = workbench.roi_part_service.build_confirm_part_roi_request(
            specimen_id=workbench.current_specimen_id,
            part_id=part_id,
            display_name=display_name,
            bbox_zyx=bbox,
            source_shape_zyx=[int(value) for value in getattr(workbench.image_volume, "shape", ()) or ()],
            roi_id=str((roi or {}).get("roi_id") or ""),
            roi_metadata=workbench._roi_keyframe_metadata(),
            roi_keyframes=roi_keyframes,
            mask_contours=mask_contours,
            mask_bbox_zyx=mask_bbox,
            accepted_preview_mask=workbench._accepted_full_volume_preview_mask_for_request(bbox) if mask_bbox else None,
        )
        if not result:
            raise ValueError(result.message or ", ".join(result.reasons or []))
        return result.payload.get("request") or {}

    def ensure_roi_for_created_part(self, part, bbox, display_name="", specimen_id=""):
        workbench = self.workbench
        if not isinstance(part, dict):
            return None
        specimen_id = str(specimen_id or workbench.current_specimen_id or "")
        part_id = str(part.get("part_id", "") or "")
        if not specimen_id or not part_id:
            return None
        if self.state.active_roi_id:
            try:
                return workbench.project.update_part_roi(
                    specimen_id,
                    self.state.active_roi_id,
                    bbox_zyx=bbox,
                    status="part_created",
                    linked_part_id=part_id,
                    display_name=display_name or part.get("display_name") or part_id,
                    metadata=workbench._roi_keyframe_metadata(),
                    save=True,
                )
            except Exception:
                pass
        roi_id = f"{part_id}_roi"
        try:
            return workbench.project.add_part_roi(
                specimen_id,
                roi_id,
                display_name=display_name or part.get("display_name") or roi_id,
                bbox_zyx=bbox,
                status="part_created",
                linked_part_id=part_id,
                metadata=workbench._roi_keyframe_metadata(),
                save=True,
            )
        except ValueError:
            return None

    def open_at_widget_position(self, x, y):
        workbench = self.workbench
        if workbench.current_volume_scope != "full" or workbench.image_volume is None:
            return False
        pixel = workbench.canvas.widget_to_image_pixel(x, y)
        if pixel is None:
            return False
        px, py = pixel
        overlays = list(reversed(self.current_overlay_rects()))
        for overlay in overlays:
            if not isinstance(overlay, dict):
                continue
            rect = overlay.get("rect", [])
            if len(rect) != 4:
                continue
            x0, y0, x1, y1 = [int(value) for value in rect]
            if not (min(x0, x1) <= px <= max(x0, x1) and min(y0, y1) <= py <= max(y0, y1)):
                continue
            if overlay.get("kind") == "part" and overlay.get("part_id"):
                workbench._select_volume_tree_item(workbench.current_specimen_id, "part", overlay.get("part_id", ""))
                return True
            if overlay.get("kind") == "roi" and overlay.get("roi_id"):
                roi = workbench.project.get_part_roi(workbench.current_specimen_id, overlay.get("roi_id", ""), default=None)
                if roi is not None:
                    self.load_draft(roi)
                    message = tt("Loaded ROI draft {0} for editing.", workbench.lang).format(roi.get("display_name") or roi.get("roi_id"))
                    workbench.training_status_label.setText(message)
                    workbench.log(message)
                    workbench.render_current_slice()
                    return True
        return False

    def finish_confirm_result(self, result):
        workbench = self.workbench
        result = dict(result or {})
        part = result.get("part") if isinstance(result.get("part"), dict) else None
        specimen_id = str(result.get("specimen_id") or workbench.current_specimen_id or "")
        part_id = str(result.get("part_id") or (part or {}).get("part_id") or "")
        if not specimen_id or not part_id:
            return
        self.state.active_roi_id = ""
        self.state.keyframes = []
        workbench.part_mask_workflow_controller.clear_roi_draft_keyframes()
        workbench.refresh_project(reload_current=False)
        workbench._populate_volume_roi_source_combo()
        workbench._select_volume_tree_item(specimen_id, "part", part_id)
        part = workbench.project.get_part(specimen_id, part_id, default=part)
        message = tt("Confirmed ROI and created part {0}.", workbench.lang).format((part or {}).get("display_name") or part_id)
        if result.get("mask_initialized"):
            if result.get("mask_bbox_zyx"):
                message = f"{message}\n{tt('Full-volume contour mask initialized from {0} key slice(s).', workbench.lang).format(int(result.get('mask_keyframe_count') or 0))}"
            else:
                message = f"{message}\n{tt('ROI shell mask initialized from {0} key slice(s).', workbench.lang).format(int(result.get('roi_keyframe_count') or 0))}"
        elif result.get("mask_message"):
            if result.get("mask_bbox_zyx"):
                message = f"{message}\n{tt('Full-volume contour mask not initialized: {0}', workbench.lang).format(result.get('mask_message'))}"
            else:
                message = f"{message}\nROI shell mask not initialized: {result.get('mask_message')}"
        workbench.training_status_label.setText(message)
        workbench.log(message)

    def confirm_to_part(self, *_args):
        workbench = self.workbench
        if not workbench.coordinator.guard_backend_write_lock():
            return
        if self.is_confirm_running():
            QMessageBox.information(workbench, tt("Part extraction", workbench.lang), tt("Part volume creation is already running.", workbench.lang))
            return
        if workbench.current_volume_scope != "full" or not workbench.current_specimen_id or workbench.image_volume is None:
            QMessageBox.information(workbench, tt("Part extraction", workbench.lang), tt("Switch to Full volume before confirming ROI.", workbench.lang))
            return
        roi = workbench.project.get_part_roi(workbench.current_specimen_id, self.state.active_roi_id, default=None) if self.state.active_roi_id else None
        try:
            bbox = workbench._current_part_bbox_for_action()
        except Exception as exc:
            if roi is not None and roi.get("bbox_zyx"):
                bbox = workbench._clip_bbox_to_shape(roi.get("bbox_zyx", []), workbench.image_volume.shape)
            else:
                QMessageBox.warning(workbench, tt("Part extraction", workbench.lang), str(exc))
                return
        mask_contours = workbench._full_volume_contours_payload()
        mask_bbox = workbench._full_volume_contour_bbox(mask_contours)
        if mask_bbox:
            bbox = mask_bbox
        if roi is not None:
            default_part_id = str(roi.get("roi_id", "")).replace("_roi", "") or f"part_{len(workbench.project.list_parts(workbench.current_specimen_id)) + 1}"
            default_display_name = str(roi.get("display_name") or default_part_id)
        else:
            default_part_id = f"part_{len(workbench.project.list_parts(workbench.current_specimen_id)) + 1}"
            default_display_name = default_part_id
        if not bbox:
            return
        roi_keyframes = self.normalize_keyframes(((roi or {}).get("metadata") or {}).get("roi_keyframes", []) if roi is not None else self.state.keyframes)
        dialog = TifPartNameDialog("Confirm ROI", part_id=default_part_id, display_name=default_display_name, parent=workbench, lang=workbench.lang)
        if dialog.exec() != QDialog.Accepted:
            return
        part_id, display_name = dialog.values()
        if not part_id:
            return
        request = self.build_confirm_request(roi, bbox, part_id, display_name or part_id, roi_keyframes, mask_contours, mask_bbox)
        if self.should_confirm_in_background(request):
            self.start_confirm_worker(request)
            return
        try:
            result = workbench._confirm_part_roi_request_sync(request)
        except Exception as exc:
            QMessageBox.warning(workbench, tt("Part extraction", workbench.lang), str(exc))
            return
        self.finish_confirm_result(result)
