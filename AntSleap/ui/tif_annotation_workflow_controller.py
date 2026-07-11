from __future__ import annotations

import os
import math
from dataclasses import dataclass, field

import numpy as np

from PySide6.QtCore import QThread
from PySide6.QtWidgets import QMessageBox

try:
    from AntSleap.core.tif_part_extraction import signed_distance
    from AntSleap.ui.tif_workbench_translations import tt
    from AntSleap.ui.tif_workbench_workers import TifLabelAutoSaveWorker, TifLabelManualSaveWorker, TifPromoteWorkingEditWorker
except ModuleNotFoundError as exc:
    if exc.name != "AntSleap":
        raise
    from core.tif_part_extraction import signed_distance
    from ui.tif_workbench_translations import tt
    from ui.tif_workbench_workers import TifLabelAutoSaveWorker, TifLabelManualSaveWorker, TifPromoteWorkingEditWorker


@dataclass
class TifAnnotationWorkflowState:
    dirty_slices: set[int] = field(default_factory=set)
    slice_revisions: dict[int, int] = field(default_factory=dict)
    revision_counter: int = 0
    dirty: bool = False
    tool_mode: str = "brush"
    undo_stack: list = field(default_factory=list)
    redo_stack: list = field(default_factory=list)
    stroke_active: bool = False
    stroke_undo_pushed: bool = False
    stroke_z_index: int | None = None
    stroke_last_pixel: tuple[int, int] | None = None
    stroke_changed: bool = False


class TifAnnotationWorkflowController:
    TOOL_MODES = frozenset({"brush", "eraser", "lasso", "rectangle", "ellipse", "picker", "pan"})
    VIEW_SCOPE = "annotation"

    def __init__(self, workbench):
        self.workbench = workbench
        self.state = TifAnnotationWorkflowState()
        self.auto_save_thread = None
        self.auto_save_worker = None
        self.auto_save_token = 0
        self.auto_save_task_id = ""
        self.auto_save_pending_reason = ""
        self.auto_save_handled_tokens = set()
        self.manual_save_thread = None
        self.manual_save_worker = None
        self.manual_save_token = 0
        self.manual_save_task_id = ""
        self.pending_manual_save_after_auto = None
        self.promote_thread = None
        self.promote_worker = None
        self.promote_request = {}
        self.promote_task_id = ""
        self.saving_working_edit = False
        self.pending_promote_after_save = None

    def initialize_compatibility_state(self):
        return self.state

    def bind_signals(self):
        view = self.workbench.workbench_view
        view.register_scope(
            self.VIEW_SCOPE,
            "btn_tool_brush",
            "btn_tool_eraser",
            "btn_tool_lasso",
            "btn_tool_rectangle",
            "btn_tool_ellipse",
            "btn_tool_picker",
            "btn_tool_pan",
            "brush_size_slider",
            "btn_undo",
            "btn_redo",
            "btn_save_edit",
            "auto_save_check",
            "btn_promote",
            "btn_interpolate_current_label",
            "shortcut_undo",
            "shortcut_redo",
            "shortcut_redo_alt",
            "shortcut_save_edit",
            "shortcut_tool_brush",
            "shortcut_tool_eraser",
            "shortcut_tool_lasso",
            "shortcut_tool_rectangle",
            "shortcut_tool_ellipse",
            "shortcut_tool_picker",
            "shortcut_brush_smaller",
            "shortcut_brush_larger",
        )
        router = self.workbench.signal_router
        bindings = (
            ("tool_brush", "btn_tool_brush", "clicked", self.select_brush),
            ("tool_eraser", "btn_tool_eraser", "clicked", self.select_eraser),
            ("tool_lasso", "btn_tool_lasso", "clicked", self.select_lasso),
            ("tool_rectangle", "btn_tool_rectangle", "clicked", self.select_rectangle),
            ("tool_ellipse", "btn_tool_ellipse", "clicked", self.select_ellipse),
            ("tool_picker", "btn_tool_picker", "clicked", self.select_picker),
            ("tool_pan", "btn_tool_pan", "clicked", self.select_pan),
            ("brush_size", "brush_size_slider", "valueChanged", self.on_brush_size_changed),
            ("undo", "btn_undo", "clicked", self.undo),
            ("redo", "btn_redo", "clicked", self.redo),
            ("save", "btn_save_edit", "clicked", self.save),
            ("auto_save", "auto_save_check", "toggled", self.on_auto_save_toggled),
            ("promote", "btn_promote", "clicked", self.promote),
            ("interpolate", "btn_interpolate_current_label", "clicked", self.interpolate_current_label_between_key_slices),
            ("shortcut_undo", "shortcut_undo", "activated", self.undo),
            ("shortcut_redo", "shortcut_redo", "activated", self.redo),
            ("shortcut_redo_alt", "shortcut_redo_alt", "activated", self.redo),
            ("shortcut_save", "shortcut_save_edit", "activated", self.save),
            ("shortcut_brush", "shortcut_tool_brush", "activated", self.select_brush),
            ("shortcut_eraser", "shortcut_tool_eraser", "activated", self.select_eraser),
            ("shortcut_lasso", "shortcut_tool_lasso", "activated", self.select_lasso),
            ("shortcut_rectangle", "shortcut_tool_rectangle", "activated", self.select_rectangle),
            ("shortcut_ellipse", "shortcut_tool_ellipse", "activated", self.select_ellipse),
            ("shortcut_picker", "shortcut_tool_picker", "activated", self.select_picker),
            ("shortcut_brush_smaller", "shortcut_brush_smaller", "activated", self.decrease_brush_size),
            ("shortcut_brush_larger", "shortcut_brush_larger", "activated", self.increase_brush_size),
        )
        for key, widget_name, signal_name, slot in bindings:
            signal = getattr(view.require(self.VIEW_SCOPE, widget_name), signal_name)
            router.bind(self.VIEW_SCOPE, key, signal, slot)

    def set_tool_mode(self, mode, show_message=True):
        workbench = self.workbench
        mode = str(mode or "brush")
        if mode not in self.TOOL_MODES:
            mode = "brush"
        changed = mode != self.state.tool_mode
        self.state.tool_mode = mode
        workbench.annotation_tool_mode = mode
        workbench._sync_annotation_tool_buttons()
        if show_message and changed:
            messages = {
                "brush": "Tool set to Brush.",
                "eraser": "Tool set to Eraser.",
                "lasso": "Tool set to Lasso fill.",
                "rectangle": "Tool set to Rectangle fill.",
                "ellipse": "Tool set to Ellipse fill.",
                "picker": "Tool set to Picker.",
                "pan": "Tool set to Pan/view. Labels will not be changed.",
            }
            workbench._set_operation_feedback(tt(messages[mode], workbench.lang))
        return mode

    def dirty_slice_count(self):
        return len(self.state.dirty_slices)

    def mark_slice_dirty(self, z_index):
        try:
            z_index = int(z_index)
        except Exception:
            return
        self.state.dirty_slices.add(z_index)
        self.state.revision_counter += 1
        self.state.slice_revisions[z_index] = self.state.revision_counter
        self.state.dirty = True
        self._sync_mirror()

    def clear_saved_slices(self, slice_revisions):
        for z_index, revision in (slice_revisions or {}).items():
            try:
                z_index = int(z_index)
                revision = int(revision)
            except Exception:
                continue
            if int(self.state.slice_revisions.get(z_index, -1)) == revision:
                self.state.dirty_slices.discard(z_index)
                self.state.slice_revisions.pop(z_index, None)
        self.state.dirty = bool(self.state.dirty_slices)
        self._sync_mirror()

    def reset_dirty_tracking(self):
        self.state.dirty_slices.clear()
        self.state.slice_revisions.clear()
        self.state.dirty = False
        self._sync_mirror()

    def reset_history(self):
        self.state.undo_stack.clear()
        self.state.redo_stack.clear()
        self.reset_annotation_stroke()
        self._sync_mirror()
        self.workbench._sync_undo_redo_buttons()

    def reset_annotation_stroke(self):
        self.state.stroke_active = False
        self.state.stroke_undo_pushed = False
        self.state.stroke_z_index = None
        self.state.stroke_last_pixel = None
        self.state.stroke_changed = False
        self._sync_mirror()

    def begin_annotation_stroke(self):
        self.state.stroke_active = True
        self.state.stroke_undo_pushed = False
        self.state.stroke_z_index = None
        self.state.stroke_last_pixel = None
        self.state.stroke_changed = False
        self._sync_mirror()

    def finish_annotation_stroke(self):
        self.reset_annotation_stroke()

    def ensure_annotation_undo_for_slice(self, z_index):
        if not self.state.stroke_active:
            self.push_undo()
            return
        z_index = int(z_index)
        if self.state.stroke_undo_pushed and self.state.stroke_z_index == z_index:
            return
        self.push_undo()
        self.state.stroke_undo_pushed = True
        self.state.stroke_z_index = z_index
        self._sync_mirror()

    def push_undo(self):
        workbench = self.workbench
        if workbench.edit_volume is None or workbench._current_slice_axis() != "z":
            return
        self.push_undo_for_slice(int(workbench.slice_slider.value()))

    def push_undo_for_slice(self, z_index):
        workbench = self.workbench
        if workbench.edit_volume is None:
            return
        z_index = int(z_index)
        if z_index < 0 or z_index >= int(workbench.edit_volume.shape[0]):
            return
        self.state.undo_stack.append((z_index, workbench.edit_volume[z_index].copy()))
        if len(self.state.undo_stack) > 20:
            self.state.undo_stack.pop(0)
        self.state.redo_stack.clear()
        self._sync_mirror()
        workbench._sync_undo_redo_buttons()

    def undo(self, *_args):
        workbench = self.workbench
        if not workbench.coordinator.guard_backend_write_lock():
            return
        if not self.state.undo_stack or workbench.edit_volume is None:
            workbench._sync_undo_redo_buttons()
            return
        entry = self.state.undo_stack.pop()
        if isinstance(entry, tuple) and len(entry) == 2 and entry[0] == "multi_slice":
            snapshots = [(int(z_index), np.asarray(slice_array).copy()) for z_index, slice_array in (entry[1] or [])]
            redo_snapshots = []
            for z_index, old_slice in snapshots:
                if 0 <= z_index < int(workbench.edit_volume.shape[0]):
                    redo_snapshots.append((z_index, workbench.edit_volume[z_index].copy()))
                    workbench.edit_volume[z_index] = old_slice
                    self.mark_slice_dirty(z_index)
            self.state.redo_stack.append(("multi_slice", redo_snapshots))
            z_index = snapshots[0][0] if snapshots else int(workbench.slice_slider.value())
        else:
            z_index, old_slice = entry
            z_index = int(z_index)
            self.state.redo_stack.append((z_index, workbench.edit_volume[z_index].copy()))
            workbench.edit_volume[z_index] = old_slice
            self.mark_slice_dirty(z_index)
        if workbench._current_slice_axis() == "z":
            workbench.slice_slider.setValue(z_index)
        self.mark_working_edit_dirty()
        workbench.render_current_slice()
        self._sync_mirror()
        workbench._sync_undo_redo_buttons()
        workbench._set_operation_feedback(tt("Undo restored slice {0}.", workbench.lang).format(z_index + 1), log=False)

    def redo(self, *_args):
        workbench = self.workbench
        if not workbench.coordinator.guard_backend_write_lock():
            return
        if not self.state.redo_stack or workbench.edit_volume is None:
            workbench._sync_undo_redo_buttons()
            return
        entry = self.state.redo_stack.pop()
        if isinstance(entry, tuple) and len(entry) == 2 and entry[0] == "multi_slice":
            snapshots = [(int(z_index), np.asarray(slice_array).copy()) for z_index, slice_array in (entry[1] or [])]
            undo_snapshots = []
            for z_index, redo_slice in snapshots:
                if 0 <= z_index < int(workbench.edit_volume.shape[0]):
                    undo_snapshots.append((z_index, workbench.edit_volume[z_index].copy()))
                    workbench.edit_volume[z_index] = redo_slice
                    self.mark_slice_dirty(z_index)
            self.state.undo_stack.append(("multi_slice", undo_snapshots))
            z_index = snapshots[0][0] if snapshots else int(workbench.slice_slider.value())
        else:
            z_index, redo_slice = entry
            z_index = int(z_index)
            self.state.undo_stack.append((z_index, workbench.edit_volume[z_index].copy()))
            workbench.edit_volume[z_index] = redo_slice
            self.mark_slice_dirty(z_index)
        if workbench._current_slice_axis() == "z":
            workbench.slice_slider.setValue(z_index)
        self.mark_working_edit_dirty()
        workbench.render_current_slice()
        self._sync_mirror()
        workbench._sync_undo_redo_buttons()
        workbench._set_operation_feedback(tt("Redo restored slice {0}.", workbench.lang).format(z_index + 1), log=False)

    def set_dirty(self, dirty):
        self.state.dirty = bool(dirty)
        self._sync_mirror()

    def current_part_label_path(self, role=None):
        record = self.workbench._current_part_label_record(role)
        return self.workbench.project.to_absolute((record or {}).get("path", ""))

    def has_unsaved_changes(self):
        return bool(self.state.dirty)

    def sync_dirty_from_slices(self):
        self.state.dirty = bool(self.state.dirty_slices)
        self._sync_mirror()
        return self.state.dirty

    def mark_working_edit_dirty(self):
        if self.workbench.coordinator.backend_write_lock_active():
            self.workbench._set_operation_feedback(self.workbench.coordinator.backend_write_lock_message())
            return
        self.workbench.result_review_controller.invalidate_result_region_mask_cache(clear_active_mask_preview=True)
        self.state.dirty = True
        self._sync_mirror()
        if self.workbench.auto_save_check.isChecked():
            self.workbench.auto_save_timer.start()
        self.workbench._update_save_status()

    def on_brush_size_changed(self, _value):
        if hasattr(self.workbench, "canvas"):
            self.workbench.canvas._refresh_scaled_pixmap()

    def adjust_brush_size(self, delta):
        slider = self.workbench.brush_size_slider
        value = int(slider.value())
        target = max(slider.minimum(), min(slider.maximum(), value + int(delta)))
        if target != value:
            slider.setValue(target)
            self.workbench._set_operation_feedback(tt("Brush size: {0}", self.workbench.lang).format(target), log=False)
        return target

    def select_brush(self, *_args):
        return self.set_tool_mode("brush")

    def select_eraser(self, *_args):
        return self.set_tool_mode("eraser")

    def select_lasso(self, *_args):
        return self.set_tool_mode("lasso")

    def select_rectangle(self, *_args):
        return self.set_tool_mode("rectangle")

    def select_ellipse(self, *_args):
        return self.set_tool_mode("ellipse")

    def select_picker(self, *_args):
        return self.set_tool_mode("picker")

    def select_pan(self, *_args):
        return self.set_tool_mode("pan")

    def decrease_brush_size(self, *_args):
        return self.adjust_brush_size(-1)

    def increase_brush_size(self, *_args):
        return self.adjust_brush_size(1)

    def save(self, *_args):
        return self.save_async()

    def on_auto_save_toggled(self, enabled):
        workbench = self.workbench
        if enabled:
            message = tt("Auto-save is on. Brush changes are saved shortly after editing.", workbench.lang)
        elif workbench.current_volume_scope == "part":
            message = tt("Auto-save is off. Remember to save the editable AI result.", workbench.lang)
        else:
            message = tt("Auto-save is off. Remember to save the current labels.", workbench.lang)
        workbench._set_operation_feedback(message)
        if enabled and self.state.dirty:
            workbench.auto_save_timer.start()
        elif not enabled:
            workbench.auto_save_timer.stop()
        workbench._update_save_status()

    def promote(self, *_args):
        return self.promote_working_edit()

    def _paint_disc_on_slice(self, z_index, px, py, radius, value):
        workbench = self.workbench
        if workbench.edit_volume is None:
            return False
        height, width = workbench.edit_volume.shape[1], workbench.edit_volume.shape[2]
        px = max(0, min(width - 1, int(px)))
        py = max(0, min(height - 1, int(py)))
        radius = max(1, int(radius))
        y0 = max(0, py - radius)
        y1 = min(height, py + radius + 1)
        x0 = max(0, px - radius)
        x1 = min(width, px + radius + 1)
        if y0 >= y1 or x0 >= x1:
            return False
        yy, xx = np.ogrid[y0:y1, x0:x1]
        mask = (xx - px) ** 2 + (yy - py) ** 2 <= radius ** 2
        target = workbench.edit_volume[int(z_index), y0:y1, x0:x1]
        before = target[mask].copy()
        target[mask] = int(value)
        return bool(np.any(before != int(value)))

    def _paint_interpolated_stroke_on_slice(self, z_index, start_pixel, end_pixel, radius, value):
        workbench = self.workbench
        if start_pixel is None:
            return self._paint_disc_on_slice(z_index, end_pixel[0], end_pixel[1], radius, value)
        x0, y0 = [int(v) for v in start_pixel]
        x1, y1 = [int(v) for v in end_pixel]
        steps = max(abs(x1 - x0), abs(y1 - y0), 1)
        changed = False
        for step in range(steps + 1):
            ratio = float(step) / float(steps)
            px = int(round(x0 + (x1 - x0) * ratio))
            py = int(round(y0 + (y1 - y0) * ratio))
            changed = self._paint_disc_on_slice(z_index, px, py, radius, value) or changed
        return changed

    def paint_at_widget_position(self, x, y, erase=False, continue_stroke=False):
        workbench = self.workbench
        if workbench.image_volume is None:
            return
        if not workbench.coordinator.guard_backend_write_lock(show_message=False):
            workbench._set_operation_feedback(workbench.coordinator.backend_write_lock_message())
            return
        block_reason = workbench._editable_label_block_reason(require_working_edit=True)
        if block_reason:
            workbench._set_operation_feedback(block_reason)
            return
        if workbench.edit_volume is None:
            workbench._set_operation_feedback(tt("Creating current label layer before painting...", workbench.lang))
            if not workbench._ensure_working_edit_volume():
                workbench._set_operation_feedback(tt("Current label layer is unavailable. Check the working volume path before editing labels.", workbench.lang))
                return
        z_index = int(workbench.slice_slider.value())
        height, width = workbench.image_volume.shape[1], workbench.image_volume.shape[2]
        pixel = workbench._widget_to_image_pixel(x, y, width, height)
        if pixel is None:
            return
        radius = max(1, int(workbench.brush_size_slider.value()))
        annotation_state = self.state
        active_stroke = bool(continue_stroke and annotation_state.stroke_active)
        if not active_stroke and continue_stroke:
            self.begin_annotation_stroke()
            active_stroke = True
        previous_pixel = annotation_state.stroke_last_pixel if active_stroke else None
        self.ensure_annotation_undo_for_slice(z_index)
        value = 0 if erase else int(workbench.current_material_id)
        changed = self._paint_interpolated_stroke_on_slice(z_index, previous_pixel, pixel, radius, value)
        if active_stroke:
            annotation_state.stroke_last_pixel = tuple(pixel)
            annotation_state.stroke_changed = annotation_state.stroke_changed or changed
            self._sync_mirror()
        if changed:
            self.mark_slice_dirty(z_index)
            self.mark_working_edit_dirty()
            workbench.render_current_slice()
        if erase:
            message = tt("Erased labels on slice {0}.", workbench.lang).format(z_index + 1)
        else:
            message = tt("Painted label {0} on slice {1}.", workbench.lang).format(workbench.current_material_id, z_index + 1)
        workbench._set_operation_feedback(message, log=False)

    def _polygon_fill_mask(self, points, width, height):
        workbench = self.workbench
        if len(points) < 3 or width <= 0 or height <= 0:
            return np.zeros((max(0, height), max(0, width)), dtype=bool)
        polygon = []
        for point in points:
            if point is None or len(point) < 2:
                continue
            x = max(-1.0, min(float(width), float(point[0]) + 0.5))
            y = max(-1.0, min(float(height), float(point[1]) + 0.5))
            if not polygon or (polygon[-1][0] != x or polygon[-1][1] != y):
                polygon.append((x, y))
        if len(polygon) >= 2 and polygon[0] == polygon[-1]:
            polygon.pop()
        if len(polygon) < 3:
            return np.zeros((height, width), dtype=bool)
        mask = np.zeros((height, width), dtype=bool)
        edges = list(zip(polygon, polygon[1:] + polygon[:1]))
        for y in range(height):
            scan_y = float(y) + 0.5
            intersections = []
            for (x0, y0), (x1, y1) in edges:
                if y0 == y1:
                    continue
                if (y0 <= scan_y < y1) or (y1 <= scan_y < y0):
                    ratio = (scan_y - y0) / (y1 - y0)
                    intersections.append(x0 + ratio * (x1 - x0))
            intersections.sort()
            for left, right in zip(intersections[0::2], intersections[1::2]):
                x_start = max(0, int(math.ceil(min(left, right) - 0.5)))
                x_end = min(width - 1, int(math.floor(max(left, right) - 0.5)))
                if x_start <= x_end:
                    mask[y, x_start : x_end + 1] = True
        return mask

    def _rect_fill_mask(self, start_pixel, end_pixel, width, height):
        workbench = self.workbench
        mask = np.zeros((height, width), dtype=bool)
        if start_pixel is None or end_pixel is None:
            return mask
        x0, y0 = [int(v) for v in start_pixel]
        x1, y1 = [int(v) for v in end_pixel]
        left = max(0, min(x0, x1))
        right = min(width - 1, max(x0, x1))
        top = max(0, min(y0, y1))
        bottom = min(height - 1, max(y0, y1))
        if right - left < 1 or bottom - top < 1:
            return mask
        mask[top : bottom + 1, left : right + 1] = True
        return mask

    def _ellipse_fill_mask(self, start_pixel, end_pixel, width, height):
        workbench = self.workbench
        mask = np.zeros((height, width), dtype=bool)
        if start_pixel is None or end_pixel is None:
            return mask
        x0, y0 = [int(v) for v in start_pixel]
        x1, y1 = [int(v) for v in end_pixel]
        left = max(0, min(x0, x1))
        right = min(width - 1, max(x0, x1))
        top = max(0, min(y0, y1))
        bottom = min(height - 1, max(y0, y1))
        if right - left < 1 or bottom - top < 1:
            return mask
        cx = (left + right) / 2.0
        cy = (top + bottom) / 2.0
        rx = max(0.5, (right - left + 1) / 2.0)
        ry = max(0.5, (bottom - top + 1) / 2.0)
        yy, xx = np.ogrid[top : bottom + 1, left : right + 1]
        local = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1.0
        mask[top : bottom + 1, left : right + 1] = local
        return mask

    def _fill_risk_suffix(self, mask):
        workbench = self.workbench
        if mask is None or mask.size == 0:
            return ""
        count = int(np.count_nonzero(mask))
        if count <= 0:
            return ""
        total = max(1, int(mask.size))
        warnings = []
        percent = int(round((count / total) * 100.0))
        if percent >= 35:
            warnings.append(tt("Large fill area: {0}% of slice.", workbench.lang).format(percent))
        if (
            np.any(mask[0, :])
            or np.any(mask[-1, :])
            or np.any(mask[:, 0])
            or np.any(mask[:, -1])
        ):
            warnings.append(tt("Fill touches the image edge.", workbench.lang))
        return (" " + " ".join(warnings)) if warnings else ""

    def _apply_mask_to_slice(self, z_index, mask, value, message_template, *, allow_noop=False):
        workbench = self.workbench
        if not workbench.coordinator.guard_backend_write_lock(show_message=False):
            workbench._set_operation_feedback(workbench.coordinator.backend_write_lock_message())
            return False
        if workbench.edit_volume is None:
            return False
        z_index = int(z_index)
        if z_index < 0 or z_index >= int(workbench.edit_volume.shape[0]):
            return False
        if mask is None:
            return False
        mask = np.asarray(mask, dtype=bool)
        height, width = workbench.edit_volume.shape[1], workbench.edit_volume.shape[2]
        if mask.shape != (height, width):
            return False
        count = int(np.count_nonzero(mask))
        if count <= 0:
            workbench._set_operation_feedback(tt("Shape fill is too small. Drag a wider area before releasing.", workbench.lang))
            return False
        current_slice = workbench.edit_volume[z_index]
        value = int(value)
        changed_mask = mask & (current_slice != value)
        changed_count = int(np.count_nonzero(changed_mask))
        if changed_count <= 0:
            if allow_noop:
                message = tt("No label changes were needed on slice {0}.", workbench.lang).format(z_index + 1)
                workbench._set_operation_feedback(message, log=False)
                return True
            message = tt(message_template, workbench.lang).format(value, z_index + 1, count) + self._fill_risk_suffix(mask)
            workbench._set_operation_feedback(message, log=False)
            return True
        self.push_undo_for_slice(z_index)
        current_slice[mask] = value
        self.mark_slice_dirty(z_index)
        self.mark_working_edit_dirty()
        if workbench._current_slice_axis() == "z":
            workbench.slice_slider.setValue(z_index)
        workbench.render_current_slice()
        message = tt(message_template, workbench.lang).format(value, z_index + 1, changed_count) + self._fill_risk_suffix(mask)
        workbench._set_operation_feedback(message, log=False)
        return True

    def finish_lasso_fill(self, points):
        workbench = self.workbench
        if workbench.image_volume is None:
            return False
        if not workbench.coordinator.guard_backend_write_lock(show_message=False):
            workbench._set_operation_feedback(workbench.coordinator.backend_write_lock_message())
            return False
        block_reason = workbench._editable_label_block_reason(require_working_edit=True)
        if block_reason:
            workbench._set_operation_feedback(block_reason)
            return False
        if len(points or []) < 3:
            workbench._set_operation_feedback(tt("Lasso fill needs at least 3 points.", workbench.lang))
            return False
        if workbench.edit_volume is None:
            workbench._set_operation_feedback(tt("Creating current label layer before filling...", workbench.lang))
            if not workbench._ensure_working_edit_volume():
                workbench._set_operation_feedback(tt("Current label layer is unavailable. Check the working volume path before editing labels.", workbench.lang))
                return False
        z_index = int(workbench.slice_slider.value())
        height, width = workbench.image_volume.shape[1], workbench.image_volume.shape[2]
        mask = self._polygon_fill_mask(points, width, height)
        if int(np.count_nonzero(mask)) <= 0:
            workbench._set_operation_feedback(tt("Lasso fill did not cover any pixels.", workbench.lang))
            return False
        return self._apply_mask_to_slice(z_index, mask, int(workbench.current_material_id), "Filled label {0} on slice {1}: {2} pixel(s).")

    def finish_shape_fill_drag(self, mode, start_x, start_y, end_x, end_y):
        workbench = self.workbench
        if workbench.image_volume is None:
            return False
        if not workbench.coordinator.guard_backend_write_lock(show_message=False):
            workbench._set_operation_feedback(workbench.coordinator.backend_write_lock_message())
            return False
        block_reason = workbench._editable_label_block_reason(require_working_edit=True)
        if block_reason:
            workbench._set_operation_feedback(block_reason)
            return False
        if workbench.edit_volume is None:
            workbench._set_operation_feedback(tt("Creating current label layer before filling...", workbench.lang))
            if not workbench._ensure_working_edit_volume():
                workbench._set_operation_feedback(tt("Current label layer is unavailable. Check the working volume path before editing labels.", workbench.lang))
                return False
        z_index = int(workbench.slice_slider.value())
        height, width = workbench.image_volume.shape[1], workbench.image_volume.shape[2]
        start_pixel = workbench._widget_to_image_pixel(start_x, start_y, width, height)
        end_pixel = workbench._widget_to_image_pixel(end_x, end_y, width, height)
        if start_pixel is None or end_pixel is None:
            return False
        if mode == "ellipse":
            mask = self._ellipse_fill_mask(start_pixel, end_pixel, width, height)
            template = "Filled ellipse label {0} on slice {1}: {2} pixel(s)."
        else:
            mask = self._rect_fill_mask(start_pixel, end_pixel, width, height)
            template = "Filled rectangle label {0} on slice {1}: {2} pixel(s)."
        if int(np.count_nonzero(mask)) <= 0:
            workbench._set_operation_feedback(tt("Shape fill is too small. Drag a wider area before releasing.", workbench.lang))
            return False
        return self._apply_mask_to_slice(z_index, mask, int(workbench.current_material_id), template)

    def _bounding_rect_for_mask(self, mask):
        workbench = self.workbench
        if mask is None:
            return None
        ys, xs = np.nonzero(np.asarray(mask, dtype=bool))
        if len(xs) <= 0 or len(ys) <= 0:
            return None
        return [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]

    def _rect_mask_from_bounds(self, bounds, width, height):
        workbench = self.workbench
        if bounds is None:
            return np.zeros((height, width), dtype=bool)
        x0, y0, x1, y1 = [int(round(float(value))) for value in bounds]
        x0 = max(0, min(width, x0))
        x1 = max(0, min(width, x1))
        y0 = max(0, min(height, y0))
        y1 = max(0, min(height, y1))
        if x1 <= x0 or y1 <= y0:
            return np.zeros((height, width), dtype=bool)
        mask = np.zeros((height, width), dtype=bool)
        mask[y0:y1, x0:x1] = True
        return mask

    def interpolate_current_label_between_key_slices(self):
        workbench = self.workbench
        if not workbench._ensure_editable_working_edit_for_helper():
            return False
        material_id = int(workbench.current_material_id)
        if material_id == 0:
            workbench._set_operation_feedback(tt("Background label 0 is not supported by this helper.", workbench.lang))
            return False
        volume = workbench.edit_volume
        key_slices = []
        key_masks = {}
        for z_index in range(int(volume.shape[0])):
            mask = np.asarray(volume[z_index] == material_id, dtype=bool)
            if np.any(mask):
                key_slices.append(int(z_index))
                key_masks[int(z_index)] = mask.copy()
        if len(key_slices) < 2:
            workbench._set_operation_feedback(tt("Interpolate fill needs the current label on at least two key slices.", workbench.lang))
            return False
        changed_slices = 0
        changed_pixels = 0
        undo_snapshots = []
        changed_indices = []
        for left, right in zip(key_slices, key_slices[1:]):
            span = int(right) - int(left)
            if span <= 1:
                continue
            left_dist = signed_distance(key_masks[left])
            right_dist = signed_distance(key_masks[right])
            left_rect = self._bounding_rect_for_mask(key_masks[left])
            right_rect = self._bounding_rect_for_mask(key_masks[right])
            for z_index in range(int(left) + 1, int(right)):
                ratio = float(z_index - int(left)) / float(span)
                mask = ((1.0 - ratio) * left_dist + ratio * right_dist) <= 0.0
                if int(np.count_nonzero(mask)) <= 0:
                    if left_rect is None or right_rect is None:
                        continue
                    bounds = [
                        (1.0 - ratio) * float(left_rect[idx]) + ratio * float(right_rect[idx])
                        for idx in range(4)
                    ]
                    mask = self._rect_mask_from_bounds(bounds, int(volume.shape[2]), int(volume.shape[1]))
                    if int(np.count_nonzero(mask)) <= 0:
                        continue
                current_slice = volume[z_index]
                changed_mask = mask & (current_slice != material_id)
                count = int(np.count_nonzero(changed_mask))
                if count <= 0:
                    continue
                undo_snapshots.append((int(z_index), current_slice.copy()))
                current_slice[mask] = material_id
                self.mark_slice_dirty(z_index)
                changed_indices.append(int(z_index))
                changed_slices += 1
                changed_pixels += count
        if changed_slices <= 0:
            workbench._set_operation_feedback(tt("Interpolate fill found no missing slices between key slices.", workbench.lang))
            return False
        self.state.undo_stack.append(("multi_slice", undo_snapshots))
        if len(self.state.undo_stack) > 20:
            self.state.undo_stack.pop(0)
        self.state.redo_stack.clear()
        self.mark_working_edit_dirty()
        current_z = int(workbench.slice_slider.value())
        if current_z not in changed_indices:
            workbench.slice_slider.setValue(changed_indices[0])
        workbench.render_current_slice()
        workbench._sync_undo_redo_buttons()
        workbench._set_operation_feedback(
            tt("Interpolate filled label {0}: {1} slice(s), {2} pixel(s).", workbench.lang).format(material_id, changed_slices, changed_pixels),
            log=False,
        )
        return True

    def confirm_discard_or_save(self):
        workbench = self.workbench
        if self.auto_save_thread is not None:
            message = tt("Auto-save is still finishing. Wait a moment, then try again.", workbench.lang)
            workbench._set_operation_feedback(message)
            workbench._update_save_status(state="saving")
            return False
        if self.manual_save_thread is not None or self.saving_working_edit:
            message = tt("Label save is running. Wait until it finishes before editing project data.", workbench.lang)
            workbench._set_operation_feedback(message)
            workbench._update_save_status(state="saving")
            return False
        self.wait_for_auto_save()
        workbench.auto_save_timer.stop()
        workbench._update_save_status()
        if not self.state.dirty:
            return True
        title = tt("Unsaved editable AI result", workbench.lang) if workbench.current_volume_scope == "part" else tt("Unsaved current labels", workbench.lang)
        prompt = tt("Save changes to the current editable AI result before continuing?", workbench.lang) if workbench.current_volume_scope == "part" else tt("Save changes to the current labels before continuing?", workbench.lang)
        reply = QMessageBox.question(workbench, title, prompt, QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
        if reply == QMessageBox.Cancel:
            return False
        if reply == QMessageBox.Save:
            return workbench.save_working_edit(show_message=True)
        self.reset_dirty_tracking()
        workbench._update_save_status()
        if workbench.current_specimen_id:
            workbench._load_edit_volume()
        return True

    def snapshot_save_request(self, reason="auto_save"):
        workbench = self.workbench
        if not workbench._can_auto_save_current_edit_volume():
            return None
        edit_path = workbench._current_edit_save_path()
        scope = "part" if workbench.current_volume_scope == "part" else "top_level"
        role = "editable_ai_result" if scope == "part" else "working_edit"
        result = workbench.label_edit_service.build_save_request(
            edit_volume=workbench.edit_volume,
            dirty_slices=self.state.dirty_slices,
            edit_slice_revisions=self.state.slice_revisions,
            edit_path=edit_path,
            scope=scope,
            specimen_id=workbench.current_specimen_id,
            part_id=workbench.current_part_id,
            reslice_id=workbench.current_reslice_id,
            role=role,
            reason=reason,
        )
        if not result:
            if result.message not in {"edit_volume_missing", "no_dirty_slices", "edit_path_missing"}:
                workbench._set_operation_feedback(tt("Cannot save this label layer: {0}", workbench.lang).format(result.message), log=False)
            return None
        payload = dict(result.payload.get("request") or {})
        self.auto_save_token += 1
        return {
            "token": int(self.auto_save_token),
            "reason": str(reason or "auto_save"),
            "edit_path": payload.get("edit_path", edit_path),
            "slices": payload.get("slices") or {},
            "slice_revisions": payload.get("slice_revisions") or {},
            "scope": str(payload.get("scope") or workbench.current_volume_scope or ""),
            "specimen_id": str(payload.get("specimen_id") or workbench.current_specimen_id or ""),
            "part_id": str(payload.get("part_id") or workbench.current_part_id or ""),
            "reslice_id": str(payload.get("reslice_id") or workbench.current_reslice_id or ""),
            "role": role,
        }

    def start_auto_save(self, reason="auto_save"):
        workbench = self.workbench
        if self.auto_save_thread is not None:
            self.auto_save_pending_reason = str(reason or "auto_save")
            workbench._update_save_status(state="saving")
            return True
        request = self.snapshot_save_request(reason=reason)
        if request is None:
            workbench._update_save_status()
            return False
        thread = QThread(workbench)
        worker = TifLabelAutoSaveWorker(request["token"], request["edit_path"], request["slices"], request["slice_revisions"])
        worker.moveToThread(thread)
        self.auto_save_thread = thread
        self.auto_save_worker = worker
        task = workbench._start_tif_task("label_auto_save", action=str(reason or "auto_save"), payload={"token": request["token"], "edit_path": request["edit_path"]}, label_role=request["role"], message=tt("Saving labels in background...", workbench.lang))
        self.auto_save_task_id = task.task_id
        self.auto_save_pending_reason = ""
        workbench.auto_save_timer.stop()
        workbench._update_save_status(state="saving")
        thread.started.connect(worker.run)
        worker.finished.connect(self.on_auto_save_finished)
        worker.failed.connect(self.on_auto_save_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.start()
        return True

    def queue_manual_save(self, show_message=True, promote_request=None):
        workbench = self.workbench
        self.pending_manual_save_after_auto = {"show_message": bool(show_message), "promote_request": dict(promote_request or {})}
        workbench.auto_save_timer.stop()
        workbench._update_save_status(state="saving")
        message = tt("Finishing auto-save before accepting training truth...", workbench.lang) if promote_request else tt("Finishing auto-save before manual save...", workbench.lang)
        workbench._set_operation_feedback(message)
        return True

    def consume_manual_save(self):
        workbench = self.workbench
        pending = self.pending_manual_save_after_auto
        self.pending_manual_save_after_auto = None
        if not pending:
            return False
        promote_request = dict(pending.get("promote_request") or {})
        return self.save_async(show_message=bool(pending.get("show_message", True)), promote_request=promote_request)

    def cleanup_auto_save(self):
        self.auto_save_thread = None
        self.auto_save_worker = None
        self.auto_save_task_id = ""

    def cleanup_manual_save(self):
        workbench = self.workbench
        self.manual_save_thread = None
        self.manual_save_worker = None
        self.manual_save_task_id = ""
        self.saving_working_edit = False
        workbench._set_scope_controls_enabled()

    def result_matches_current_view(self, result, *, task_id=""):
        workbench = self.workbench
        context = dict((result or {}).get("context") or {})
        if context and task_id:
            return workbench._task_context_matches_current(task_id, fields=("specimen_id", "volume_scope", "part_id", "reslice_id"))
        path = str((result or {}).get("edit_path") or (result or {}).get("path") or "")
        if not path:
            return False
        try:
            return os.path.normcase(os.path.abspath(path)) == os.path.normcase(os.path.abspath(workbench._current_edit_save_path()))
        except Exception:
            return False

    def wait_for_auto_save(self):
        workbench = self.workbench
        thread = self.auto_save_thread
        if thread is None:
            return
        worker = self.auto_save_worker
        if thread.isRunning():
            thread.quit()
            thread.wait(30000)
        if worker is not None:
            result = getattr(worker, "last_result", None)
            error = getattr(worker, "last_error", None)
            if result:
                self.on_auto_save_finished(result)
            elif error:
                self.on_auto_save_failed(error)
            else:
                workbench._cancel_tif_task(self.auto_save_task_id, "label_auto_save_finished_without_result")
                self.cleanup_auto_save()
        else:
            workbench._cancel_tif_task(self.auto_save_task_id, "label_auto_save_worker_missing")
            self.cleanup_auto_save()

    def save_async(self, show_message=True, promote_request=None):
        workbench = self.workbench
        if not workbench.coordinator.guard_backend_write_lock():
            return False
        if self.saving_working_edit:
            return True
        if self.auto_save_thread is not None:
            return self.queue_manual_save(show_message=show_message, promote_request=promote_request)
        if workbench.edit_volume is None and not workbench._ensure_working_edit_volume():
            return False
        request = self.snapshot_save_request(reason="manual")
        if request is None:
            workbench._update_save_status()
            if promote_request:
                self.pending_promote_after_save = None
                return self.begin_promote(promote_request)
            workbench.backend_panel_controller._resume_pending_backend_action_after_save()
            return True
        if promote_request:
            self.pending_promote_after_save = dict(promote_request or {})
        self.manual_save_token = int(request["token"])
        task = workbench._start_tif_task("label_manual_save", action="manual_save", payload={"token": request["token"], "edit_path": request["edit_path"]}, label_role=request["role"], message=tt("Label save is running. Wait until it finishes before editing project data.", workbench.lang))
        self.manual_save_task_id = task.task_id
        thread = QThread(workbench)
        worker = TifLabelManualSaveWorker(request["token"], request["edit_path"], request["slices"], request["slice_revisions"], context={key: request.get(key, "") for key in ("scope", "specimen_id", "part_id", "reslice_id")})
        worker.moveToThread(thread)
        self.manual_save_thread = thread
        self.manual_save_worker = worker
        self.saving_working_edit = True
        workbench.auto_save_timer.stop()
        workbench._update_save_status(state="saving")
        if show_message:
            workbench._set_operation_feedback(tt("Saving labels in background...", workbench.lang))
        workbench._set_scope_controls_enabled()
        thread.started.connect(worker.run)
        worker.finished.connect(self.on_manual_save_finished)
        worker.failed.connect(self.on_manual_save_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.start()
        return True

    def current_promote_request(self):
        workbench = self.workbench
        if not workbench.current_specimen_id:
            return {}
        return {
            "scope": "part" if workbench.current_volume_scope == "part" else "full",
            "specimen_id": str(workbench.current_specimen_id or ""),
            "part_id": str(workbench.current_part_id or ""),
            "reslice_id": str(workbench.current_reslice_id or ""),
        }

    def begin_promote(self, request):
        workbench = self.workbench
        request = dict(request or {})
        if not request.get("specimen_id") or self.promote_thread is not None:
            return False
        task = workbench._start_tif_task(
            "truth_promotion",
            action="promote_working_edit",
            payload={"request": dict(request)},
            request_key=workbench._task_request_key((request.get("specimen_id", ""), request.get("scope", ""), request.get("part_id", ""), request.get("reslice_id", ""))),
            message=tt("Training truth acceptance is running. Wait until it finishes before editing project data.", workbench.lang),
        )
        self.promote_task_id = task.task_id
        thread = QThread(workbench)
        worker = TifPromoteWorkingEditWorker(workbench.project, request)
        worker.moveToThread(thread)
        self.promote_thread = thread
        self.promote_worker = worker
        self.promote_request = request
        workbench._set_operation_feedback(tt("Accepting training truth in background...", workbench.lang))
        workbench._set_scope_controls_enabled()
        thread.started.connect(worker.run)
        worker.finished.connect(self.on_promote_finished)
        worker.failed.connect(self.on_promote_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.start()
        return True

    def cleanup_promote(self):
        workbench = self.workbench
        self.promote_thread = None
        self.promote_worker = None
        self.promote_request = {}
        self.promote_task_id = ""
        workbench._set_scope_controls_enabled()

    def on_promote_finished(self, result):
        workbench = self.workbench
        result = dict(result or {})
        task_id = self.promote_task_id
        task_current = workbench._task_context_matches_current(task_id, fields=("specimen_id", "volume_scope", "part_id", "reslice_id"))
        workbench._finish_tif_task(task_id, payload=result, message="truth_promotion_finished")
        self.cleanup_promote()
        workbench.refresh_project(reload_current=False)
        specimen_id = str(result.get("specimen_id") or "")
        part_id = str(result.get("part_id") or "")
        reslice_id = str(result.get("reslice_id") or "")
        if specimen_id and part_id and task_current:
            workbench.selection_workflow_controller.select_payload(
                {
                    "specimen_id": specimen_id,
                    "scope": "part_reslice" if reslice_id else "part",
                    "part_id": part_id,
                    "reslice_id": reslice_id,
                }
            )
        elif specimen_id and task_current:
            workbench.selection_workflow_controller.select_payload({"specimen_id": specimen_id, "scope": "full"})
        message = tt("Accepted current labels as training truth.", workbench.lang) if task_current else tt("Accepted labels as training truth; current view was left unchanged because you switched context while it was running.", workbench.lang)
        workbench._set_operation_feedback(message)

    def on_promote_failed(self, result):
        workbench = self.workbench
        result = dict(result or {})
        task_id = self.promote_task_id
        task_current = workbench._task_context_matches_current(task_id, fields=("specimen_id", "volume_scope", "part_id", "reslice_id"))
        message = str(result.get("error", ""))
        workbench._fail_tif_task(task_id, message, payload=result)
        self.cleanup_promote()
        if task_current:
            workbench._set_operation_feedback(tt("Action failed: {0}", workbench.lang).format(message))
            QMessageBox.warning(workbench, tt("Accept working edit", workbench.lang), message)

    def promote_working_edit(self):
        workbench = self.workbench
        if not workbench.coordinator.guard_backend_write_lock() or not workbench.current_specimen_id:
            return False
        if workbench.current_volume_scope == "part" and not workbench.current_part_id:
            return False
        prompt = tt("Promote the reviewed editable AI result to part-level training truth?", workbench.lang) if workbench.current_volume_scope == "part" else tt("Promote the current working_edit layer to training truth?", workbench.lang)
        reply = QMessageBox.question(workbench, tt("Accept working edit", workbench.lang), prompt, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return False
        request = self.current_promote_request()
        if self.state.dirty:
            return self.save_async(promote_request=request)
        return self.begin_promote(request)

    def on_auto_save_finished(self, result):
        workbench = self.workbench
        result = dict(result or {})
        token = int(result.get("token", 0) or 0)
        if token in self.auto_save_handled_tokens:
            return
        self.auto_save_handled_tokens.add(token)
        if token != int(self.auto_save_token):
            return
        if not self.result_matches_current_view(result, task_id=self.auto_save_task_id):
            workbench._cancel_tif_task(self.auto_save_task_id, "stale_label_auto_save_result")
            self.cleanup_auto_save()
            self.pending_manual_save_after_auto = None
            self.pending_promote_after_save = None
            workbench._pending_backend_action_after_save = None
            return
        self.clear_saved_slices(result.get("slice_revisions") or {})
        workbench._finish_tif_task(self.auto_save_task_id, payload=result, message="label_auto_save_finished")
        self.cleanup_auto_save()
        if workbench.current_volume_scope == "part":
            workbench._finalize_part_editable_save_metadata(result.get("metadata") or {}, auto_saved=True, refresh_volumes=False)
        else:
            workbench._finalize_full_edit_save_metadata(result.get("metadata") or {}, auto_saved=True, refresh_volumes=False)
        if self.state.dirty and workbench.auto_save_check.isChecked():
            workbench.auto_save_timer.start()
        workbench._update_save_status()
        message = tt("Auto-saved editable AI result.", workbench.lang) if workbench.current_volume_scope == "part" else tt("Auto-saved current labels.", workbench.lang)
        workbench._set_operation_feedback(message, log=False)
        if not self.consume_manual_save():
            workbench.backend_panel_controller._resume_pending_backend_action_after_save()

    def on_auto_save_failed(self, result):
        workbench = self.workbench
        result = dict(result or {})
        token = int(result.get("token", 0) or 0)
        if token in self.auto_save_handled_tokens:
            return
        self.auto_save_handled_tokens.add(token)
        if token != int(self.auto_save_token):
            return
        if not self.result_matches_current_view(result, task_id=self.auto_save_task_id):
            workbench._cancel_tif_task(self.auto_save_task_id, "stale_label_auto_save_failure")
            self.cleanup_auto_save()
            workbench._pending_backend_action_after_save = None
            return
        workbench._fail_tif_task(self.auto_save_task_id, result.get("error", ""), payload=result)
        self.cleanup_auto_save()
        self.set_dirty(True)
        message = tt("Save failed: {0}", workbench.lang).format(str(result.get("error", "")))
        workbench._set_operation_feedback(message)
        workbench._update_save_status(state="failed", detail=str(result.get("error", "")))
        self.pending_manual_save_after_auto = None
        self.pending_promote_after_save = None
        workbench._pending_backend_action_after_save = None

    def on_manual_save_finished(self, result):
        workbench = self.workbench
        result = dict(result or {})
        if int(result.get("token", 0) or 0) != int(self.manual_save_token):
            workbench._cancel_tif_task(self.manual_save_task_id, "stale_label_manual_save_token")
            self.cleanup_manual_save()
            workbench._pending_backend_action_after_save = None
            return
        if not self.result_matches_current_view(result, task_id=self.manual_save_task_id):
            workbench._cancel_tif_task(self.manual_save_task_id, "stale_label_manual_save_context")
            self.cleanup_manual_save()
            workbench._pending_backend_action_after_save = None
            return
        self.clear_saved_slices(result.get("slice_revisions") or {})
        if workbench.current_volume_scope == "part":
            workbench._finalize_part_editable_save_metadata(result.get("metadata") or {}, refresh_volumes=True)
            message = tt("Editable AI result saved.", workbench.lang)
        else:
            workbench._finalize_full_edit_save_metadata(result.get("metadata") or {}, refresh_volumes=True)
            message = tt("Current labels saved.", workbench.lang)
        workbench._finish_tif_task(self.manual_save_task_id, payload=result, message=message)
        self.cleanup_manual_save()
        workbench._update_save_status()
        workbench._set_operation_feedback(message)
        pending = self.pending_promote_after_save
        self.pending_promote_after_save = None
        if pending:
            self.begin_promote(pending)
        else:
            workbench.backend_panel_controller._resume_pending_backend_action_after_save()

    def on_manual_save_failed(self, result):
        workbench = self.workbench
        result = dict(result or {})
        task_id = self.manual_save_task_id
        if int(result.get("token", 0) or 0) != int(self.manual_save_token):
            workbench._cancel_tif_task(task_id, "stale_label_manual_save_token")
            self.cleanup_manual_save()
            self.pending_promote_after_save = None
            workbench._pending_backend_action_after_save = None
            return
        task_current = self.result_matches_current_view(result, task_id=task_id)
        workbench._fail_tif_task(task_id, result.get("error", ""), payload=result)
        self.cleanup_manual_save()
        self.pending_promote_after_save = None
        workbench._pending_backend_action_after_save = None
        if not task_current:
            context = dict(result.get("context") or {})
            target = "/".join(
                value
                for value in (
                    str(context.get("specimen_id") or ""),
                    str(context.get("part_id") or ""),
                    str(context.get("reslice_id") or ""),
                )
                if value
            )
            detail = f"{target}: {result.get('error', '')}" if target else str(result.get("error", ""))
            message = tt("Save failed: {0}", workbench.lang).format(detail)
            workbench.log(message)
            QMessageBox.warning(workbench, tt("Unsaved working edit", workbench.lang), message)
            return
        self.set_dirty(True)
        message = tt("Save failed: {0}", workbench.lang).format(str(result.get("error", "")))
        workbench._set_operation_feedback(message)
        workbench._update_save_status(state="failed", detail=str(result.get("error", "")))
        QMessageBox.warning(workbench, tt("Unsaved working edit", workbench.lang), str(result.get("error", "")))

    def _sync_mirror(self):
        return self.state
