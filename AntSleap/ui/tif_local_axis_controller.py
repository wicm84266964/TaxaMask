from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import math
import os
import numpy as np

from PySide6.QtCore import QObject, QThread, Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox, QProgressDialog

try:
    from AntSleap.core.tif_local_axis_ai import export_local_axis_training_manifest
    from AntSleap.core.tif_local_axis_reslice import align_editable_axis_to_reference_plane, source_point_to_reslice_point
    from AntSleap.ui.tif_gpu_volume_canvas import volume_shape_scale
    from AntSleap.ui.tif_workbench_translations import tt
    from AntSleap.ui.tif_workbench_workers import TifLocalAxisResliceExportWorker
except ModuleNotFoundError as exc:
    if exc.name != "AntSleap":
        raise
    from core.tif_local_axis_ai import export_local_axis_training_manifest
    from core.tif_local_axis_reslice import align_editable_axis_to_reference_plane, source_point_to_reslice_point
    from ui.tif_gpu_volume_canvas import volume_shape_scale
    from ui.tif_workbench_translations import tt
    from ui.tif_workbench_workers import TifLocalAxisResliceExportWorker


@dataclass
class TifLocalAxisState:
    draft: object = None
    endpoint_drag: object = None
    pick_target: str = ""
    roll_pick_target: str = ""
    export_thread: object = None
    export_worker: object = None
    export_progress: object = None
    export_context: dict = field(default_factory=dict)
    export_task_id: str = ""


class TifLocalAxisController(QObject):
    VIEW_SCOPE = "local_axis"

    def __init__(self, workbench):
        super().__init__(workbench)
        self.workbench = workbench
        self.state = TifLocalAxisState()

    def bind_signals(self):
        workbench = self.workbench
        view = workbench.workbench_view
        names = (
            "btn_local_axis_reslice",
            "btn_copy_source_z_axis",
            "btn_pick_roll_ref_a",
            "btn_pick_roll_ref_b",
            "btn_pick_roll_ref_c",
            "btn_align_axis_to_reference_plane",
            "btn_clear_roll_refs",
            "btn_clear_local_axis_draft",
            "btn_export_local_axis_training_manifest",
        )
        view.register_scope(self.VIEW_SCOPE, *names)
        bindings = (
            ("reslice", "btn_local_axis_reslice", "clicked", self.export_current_reslice),
            ("copy_source", "btn_copy_source_z_axis", "clicked", self.copy_source_z_axis_to_draft),
            ("pick_a", "btn_pick_roll_ref_a", "clicked", lambda checked=False: self.set_pick_target("roll_a" if checked else "")),
            ("pick_b", "btn_pick_roll_ref_b", "clicked", lambda checked=False: self.set_pick_target("roll_b" if checked else "")),
            ("pick_c", "btn_pick_roll_ref_c", "clicked", lambda checked=False: self.set_pick_target("roll_c" if checked else "")),
            ("align", "btn_align_axis_to_reference_plane", "clicked", self.align_to_reference_plane),
            ("clear_refs", "btn_clear_roll_refs", "clicked", self.clear_roll_references),
            ("clear_draft", "btn_clear_local_axis_draft", "clicked", self.clear_draft),
            ("training_manifest", "btn_export_local_axis_training_manifest", "clicked", self.export_training_manifest_dialog),
        )
        for key, widget_name, signal_name, slot in bindings:
            signal = getattr(view.require(self.VIEW_SCOPE, widget_name), signal_name)
            workbench.signal_router.bind(self.VIEW_SCOPE, key, signal, slot)

    @property
    def lang(self):
        return self.workbench.lang

    @property
    def service(self):
        return self.workbench.local_axis_service

    def _set_status(self, message, tooltip=""):
        self.workbench._set_local_axis_status(message, tooltip=tooltip)

    def ignored_draft_lock_task_types(self):
        return self.workbench.coordinator.preview_interaction_task_types()

    def guard_draft_interaction(self, show_message=True):
        ignored = self.ignored_draft_lock_task_types()
        if self.workbench.coordinator.guard_backend_write_lock(show_message=show_message, ignored_task_types=ignored):
            return True
        if not show_message:
            self._set_status(self.workbench.coordinator.backend_write_lock_message(ignored_task_types=ignored))
        return False

    def export_running(self):
        return self.state.export_thread is not None

    def set_export_controls_enabled(self, enabled):
        enabled = bool(enabled)
        for widget in (
            getattr(self.workbench, "btn_copy_source_z_axis", None),
            getattr(self.workbench, "btn_pick_roll_ref_a", None),
            getattr(self.workbench, "btn_pick_roll_ref_b", None),
            getattr(self.workbench, "btn_pick_roll_ref_c", None),
            getattr(self.workbench, "btn_align_axis_to_reference_plane", None),
            getattr(self.workbench, "btn_clear_roll_refs", None),
            getattr(self.workbench, "btn_clear_local_axis_draft", None),
            getattr(self.workbench, "btn_local_axis_reslice", None),
        ):
            if widget is not None:
                widget.setEnabled(enabled)

    def clear_draft_if_part_changed(self, specimen_id="", part_id=""):
        draft = self.state.draft if isinstance(self.state.draft, dict) else None
        if draft is None:
            return
        if str(draft.get("specimen_id", "")) != str(specimen_id or "") or str(draft.get("part_id", "")) != str(part_id or ""):
            self.state.draft = None

    def current_draft(self):
        wb = self.workbench
        draft = self.state.draft if isinstance(self.state.draft, dict) else None
        if draft is None:
            return None
        if wb.current_reslice_id:
            return None
        if str(draft.get("specimen_id", "")) != str(wb.current_specimen_id or ""):
            return None
        if str(draft.get("part_id", "")) != str(wb.current_part_id or ""):
            return None
        return draft

    def source_z_axis_for_current_part(self):
        shape = tuple(int(value) for value in getattr(self.workbench.image_volume, "shape", ()) or ())
        if len(shape) != 3 or min(shape) <= 0:
            return {}
        result = self.service.source_z_axis_for_shape(shape)
        if not result:
            return {}
        return dict(result.payload.get("source_axis") or {})

    def roll_reference_payload(self, draft=None):
        draft = draft if isinstance(draft, dict) else self.current_draft()
        return self.service.roll_reference_payload(draft)

    def spacing_zyx(self):
        _, spacing_zyx = self.workbench.volume_render_controller._volume_source_geometry()
        return list(spacing_zyx or [1.0, 1.0, 1.0])

    def spacing_unit(self):
        wb = self.workbench
        if wb.current_volume_scope == "part":
            record = ((wb.current_part or {}).get("image") or {})
        else:
            specimen = wb.project.get_specimen(wb.current_specimen_id, default=None) if wb.current_specimen_id else None
            record = (specimen or {}).get("working_volume") or {}
        return str((record or {}).get("spacing_unit") or tt("voxel", self.lang))

    def origin_from_editable_axis(self, editable_axis):
        axis = editable_axis if isinstance(editable_axis, dict) else {}
        start = axis.get("start_zyx") or []
        end = axis.get("end_zyx") or []
        if len(start) == 3 and len(end) == 3:
            try:
                return [round((float(start[index]) + float(end[index])) * 0.5, 3) for index in range(3)]
            except (TypeError, ValueError):
                pass
        shape = tuple(int(value) for value in getattr(self.workbench.image_volume, "shape", ()) or ())
        return [(float(value) - 1.0) / 2.0 for value in shape] if len(shape) == 3 else []

    def refresh_frame(self, draft=None):
        draft = draft if isinstance(draft, dict) else self.current_draft()
        if not isinstance(draft, dict):
            return None
        editable = draft.get("editable_axis") or {}
        draft["origin_zyx"] = self.origin_from_editable_axis(editable)
        result = self.service.build_local_frame(draft, spacing_zyx=self.spacing_zyx())
        if not result:
            draft["local_frame"] = None
            draft["local_frame_error"] = result.message
            return None
        frame = dict(result.payload.get("frame") or {})
        draft["local_frame"] = frame
        draft.pop("local_frame_error", None)
        return frame

    def _set_axis_overlays(self):
        canvas = getattr(self.workbench, "volume_canvas", None)
        if hasattr(canvas, "set_axis_overlays"):
            canvas.set_axis_overlays(self.volume_overlays())

    def _sync_after_draft_change(self, *, request_render=False, render_volume=False):
        self.sync_pick_buttons()
        self.update_summary()
        self._set_axis_overlays()
        if request_render:
            self.workbench.volume_render_controller._request_volume_interaction_render()
        if render_volume and self.workbench.display_mode == "volume":
            self.workbench.volume_render_controller.render_volume_preview()

    def set_draft(self, draft, status_message=""):
        wb = self.workbench
        if not isinstance(draft, dict):
            self.state.draft = None
        else:
            draft.setdefault("specimen_id", wb.current_specimen_id)
            draft.setdefault("part_id", wb.current_part_id)
            draft.setdefault("template_id", str(wb.current_part_id or "generic"))
            self.refresh_frame(draft)
            self.state.draft = draft
        if hasattr(wb, "volume_local_axes_check"):
            wb.volume_local_axes_check.setChecked(True)
        self._sync_after_draft_change(render_volume=wb.display_mode == "volume")
        specimen = wb.project.get_specimen(wb.current_specimen_id, default=None) if wb.current_specimen_id else None
        if specimen is not None:
            wb._update_status_labels(specimen, part=wb.current_part if wb.current_volume_scope == "part" else None)
        if status_message:
            self._set_status(status_message)
            wb.log(status_message)
        return self.state.draft

    def copy_source_z_axis_to_draft(self):
        wb = self.workbench
        if not self.guard_draft_interaction():
            return None
        if wb.current_volume_scope != "part" or wb.current_reslice_id or not wb.current_specimen_id or not wb.current_part_id or wb.image_volume is None:
            QMessageBox.information(wb, tt("Local Axis Reslice", self.lang), tt("Select a part volume before editing Local Axis Reslice.", self.lang))
            return None
        source_axis = self.source_z_axis_for_current_part()
        if not source_axis:
            return None
        result = self.service.build_initial_draft(
            specimen_id=wb.current_specimen_id,
            part_id=wb.current_part_id,
            source_shape_zyx=tuple(int(value) for value in getattr(wb.image_volume, "shape", ()) or ()),
            source_axis=source_axis,
        )
        if not result:
            return None
        draft = dict(result.payload.get("draft") or {})
        self.refresh_frame(draft)
        self.state.draft = draft
        if hasattr(wb, "volume_local_axes_check"):
            wb.volume_local_axes_check.setChecked(True)
        message = tt("Copied source Z axis as editable output axis.", self.lang)
        self._set_status(message)
        wb.log(message)
        specimen = wb.project.get_specimen(wb.current_specimen_id, default=None)
        if specimen is not None:
            wb._update_status_labels(specimen, part=wb.current_part)
        if wb.display_mode == "volume":
            wb.volume_render_controller.render_volume_preview()
        return draft

    def sync_roll_buttons(self):
        wb = self.workbench
        target = str(getattr(wb, "_local_axis_pick_target", "") or getattr(wb, "_local_axis_roll_pick_target", "") or "")
        for button_name, button_target in (
            ("btn_pick_roll_ref_a", "roll_a"),
            ("btn_pick_roll_ref_b", "roll_b"),
            ("btn_pick_roll_ref_c", "roll_c"),
        ):
            button = getattr(wb, button_name, None)
            if button is None:
                continue
            button.blockSignals(True)
            button.setChecked(target == button_target)
            button.blockSignals(False)

    def set_pick_target(self, target=""):
        wb = self.workbench
        target = str(target or "")
        legacy_map = {"left_eye": "roll_a", "right_eye": "roll_b"}
        target = legacy_map.get(target, target)
        ignored_tasks = self.ignored_draft_lock_task_types()
        if target and wb.coordinator.backend_write_lock_active(ignored_task_types=ignored_tasks):
            wb.coordinator.guard_backend_write_lock(ignored_task_types=ignored_tasks)
            return False
        if target not in {"", "roll_a", "roll_b", "roll_c"}:
            target = ""
        if target and not self.current_draft():
            if self.copy_source_z_axis_to_draft() is None:
                return False
        if target and hasattr(wb, "volume_clip_plane_check") and not wb.volume_clip_plane_check.isChecked():
            wb.volume_clip_plane_check.setChecked(True)
            self._set_status(
                tt(
                    "Observation-side clip plane is now enabled. Move the clip depth if needed, then click the plane to set {0}.",
                    self.lang,
                ).format(target)
            )
        self.state.pick_target = target
        self.state.roll_pick_target = target if target in {"roll_a", "roll_b", "roll_c"} else ""
        self.sync_pick_buttons()
        if target:
            message = tt("Click the observation-side clip plane to set {0}.", self.lang).format(target)
            if hasattr(wb, "volume_clip_plane_check") and wb.volume_clip_plane_check.isChecked():
                self._set_status(message)
            else:
                self._set_status(tt("Turn on the observation-side clip plane before picking local-axis points.", self.lang))
        return bool(target)

    def sync_pick_buttons(self):
        return self.sync_roll_buttons()

    def pick_roll_reference_at(self, x, y):
        wb = self.workbench
        if not self.guard_draft_interaction(show_message=False):
            return False
        target = str(getattr(wb, "_local_axis_pick_target", "") or getattr(wb, "_local_axis_roll_pick_target", "") or "")
        if target not in {"roll_a", "roll_b", "roll_c"}:
            return False
        draft = self.current_draft()
        if not isinstance(draft, dict):
            return False
        if not (hasattr(wb, "volume_clip_plane_check") and wb.volume_clip_plane_check.isChecked()):
            self._set_status(tt("Turn on the observation-side clip plane before picking local-axis points.", self.lang))
            return False
        point = self.volume_xy_to_zyx_on_clip_plane(x, y)
        if point is None:
            return False
        roll = dict(draft.get("roll_reference") or {})
        if not roll.get("pair_id"):
            roll["pair_id"] = "roll_reference_point_pair"
        if target == "roll_a":
            key = "point_a"
            role = "roll_reference_a"
        elif target == "roll_b":
            key = "point_b"
            role = "roll_reference_b"
        else:
            key = "point_c"
            role = "reference_plane_c"
        roll[key] = {"role": role, "zyx": [round(float(value), 3) for value in point]}
        draft["roll_reference"] = roll
        draft["dirty"] = True
        self.refresh_frame(draft)
        self.state.draft = draft
        self.state.pick_target = ""
        self.state.roll_pick_target = ""
        self._sync_after_draft_change(request_render=True)
        self._set_status(tt("Set {0}: {1}", self.lang).format(role, roll[key]["zyx"]))
        return True

    def clear_roll_references(self):
        wb = self.workbench
        if not self.guard_draft_interaction():
            return
        draft = self.current_draft()
        if not isinstance(draft, dict):
            return
        result = self.service.clear_roll_reference_points(draft)
        if not result:
            return
        self.state.draft = dict(result.payload.get("draft") or {})
        self.state.pick_target = ""
        self.state.roll_pick_target = ""
        self._sync_after_draft_change(request_render=True)
        self._set_status(tt("Cleared roll reference points.", self.lang))

    def align_to_reference_plane(self):
        wb = self.workbench
        if not self.guard_draft_interaction():
            return False
        draft = self.current_draft()
        if not isinstance(draft, dict):
            if self.copy_source_z_axis_to_draft() is None:
                return False
            draft = self.current_draft()
        if not isinstance(draft, dict):
            return False
        roll = dict(draft.get("roll_reference") or {})
        if not all(isinstance(roll.get(key), dict) and roll.get(key, {}).get("zyx") for key in ("point_a", "point_b", "point_c")):
            message = tt("Set A/B/C plane reference points before aligning output Z.", self.lang)
            self._set_status(message)
            wb.log(message)
            return False
        shape = tuple(int(value) for value in getattr(wb.image_volume, "shape", ()) or ())
        try:
            editable_axis, reference_plane = align_editable_axis_to_reference_plane(
                draft.get("editable_axis") or {},
                roll,
                spacing_zyx=self.spacing_zyx(),
                shape_zyx=shape if len(shape) == 3 else None,
            )
        except Exception as exc:
            message = tt("Cannot align output Z: {0}", self.lang).format(str(exc))
            self._set_status(message)
            wb.log(message)
            return False
        roll["reference_plane"] = dict(reference_plane)
        draft["editable_axis"] = editable_axis
        draft["roll_reference"] = roll
        draft["reference_plane"] = dict(reference_plane)
        draft["dirty"] = True
        self.refresh_frame(draft)
        self.state.draft = draft
        self._sync_after_draft_change(request_render=True)
        message = tt("Aligned output Z perpendicular to the A/B/C reference plane.", self.lang)
        self._set_status(message)
        wb.log(message)
        return True

    def clear_draft(self):
        wb = self.workbench
        if not self.guard_draft_interaction():
            return
        self.state.draft = None
        self.state.pick_target = ""
        self.state.roll_pick_target = ""
        self._sync_after_draft_change(render_volume=wb.display_mode == "volume")
        self._set_status(tt("Cleared local axis draft.", self.lang))

    def default_reslice_id(self):
        part_id = str(self.workbench.current_part_id or "part").strip() or "part"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{part_id}_local_axis_{stamp}"

    def current_reslice_payload(self):
        wb = self.workbench
        if not wb._is_editable_part_volume() or not wb.current_specimen_id or not wb.current_part_id or wb.image_volume is None:
            raise ValueError(tt("Select a part volume before exporting Local Axis Reslice.", self.lang))
        draft = self.current_draft()
        if not isinstance(draft, dict):
            raise ValueError(tt("Copy source Z and set roll reference points before exporting.", self.lang))
        frame = self.refresh_frame(draft)
        if not isinstance(frame, dict):
            raise ValueError(tt("Local frame is not ready: {0}", self.lang).format(draft.get("local_frame_error") or "missing roll reference"))
        spacing = self.spacing_zyx()
        source_shape = [int(value) for value in getattr(wb.image_volume, "shape", ())]
        trainable = bool(getattr(wb, "local_axis_trainable_check", None) and wb.local_axis_trainable_check.isChecked())
        draft = dict(draft)
        draft.setdefault("source_axis", self.source_z_axis_for_current_part())
        result = self.service.build_reslice_payload(
            specimen_id=wb.current_specimen_id,
            part_id=wb.current_part_id,
            draft=draft,
            local_frame=frame,
            source_shape_zyx=source_shape,
            spacing_zyx=spacing,
            reslice_id=self.default_reslice_id(),
            trainable=trainable,
            display_name=f"{wb.current_part_id} local axis",
        )
        if not result:
            raise ValueError(tt("Local Axis Reslice export request is not ready: {0}", self.lang).format(result.message or ", ".join(result.reasons or [])))
        return dict(result.payload.get("payload") or {})

    def overlay_enabled(self):
        wb = self.workbench
        return bool(
            getattr(wb, "volume_local_axes_check", None)
            and wb.volume_local_axes_check.isChecked()
            and wb.current_volume_scope == "part"
            and wb.image_volume is not None
        )


    def current_part_reslice_record(self):
        wb = self.workbench
        if not wb.current_specimen_id or not wb.current_part_id or not wb.current_reslice_id:
            return None
        return wb.project.get_part_reslice(wb.current_specimen_id, wb.current_part_id, wb.current_reslice_id, default=None)


    def format_point_pair(self, axis):
        wb = self.workbench
        if not isinstance(axis, dict):
            return "-"
        start = axis.get("start_zyx") or []
        end = axis.get("end_zyx") or []
        if not start or not end:
            return "-"
        return "{0} -> {1}".format(start, end)


    def format_point(self, values):
        wb = self.workbench
        if not values or len(values) != 3:
            return "-"
        return "[{0}]".format(", ".join(f"{float(value):.3f}" for value in values))


    def format_vector(self, values):
        wb = self.workbench
        if not values or len(values) != 3:
            return "-"
        return "[{0}]".format(", ".join(f"{float(value):.3f}" for value in values))


    def relation_metrics(self, editable_axis, roll_reference):
        wb = self.workbench
        editable = editable_axis if isinstance(editable_axis, dict) else {}
        roll = roll_reference if isinstance(roll_reference, dict) else {}
        point_a = roll.get("point_a") if isinstance(roll.get("point_a"), dict) else {}
        point_b = roll.get("point_b") if isinstance(roll.get("point_b"), dict) else {}
        try:
            start = np.asarray(editable.get("start_zyx") or [], dtype=np.float64)
            end = np.asarray(editable.get("end_zyx") or [], dtype=np.float64)
            a = np.asarray(point_a.get("zyx") or [], dtype=np.float64)
            b = np.asarray(point_b.get("zyx") or [], dtype=np.float64)
        except (TypeError, ValueError):
            return None
        if start.size != 3 or end.size != 3 or a.size != 3 or b.size != 3:
            return None
        spacing = np.asarray(self.spacing_zyx(), dtype=np.float64)
        if spacing.size != 3 or np.any(spacing <= 0):
            spacing = np.ones(3, dtype=np.float64)
        start_w = start * spacing
        end_w = end * spacing
        a_w = a * spacing
        b_w = b * spacing
        axis_w = end_w - start_w
        axis_len = float(np.linalg.norm(axis_w))
        if axis_len <= 1e-8:
            return None
        axis_unit = axis_w / axis_len

        def projection(point_w):
            offset = point_w - start_w
            along = float(np.dot(offset, axis_unit))
            lateral_vec = offset - along * axis_unit
            return along, float(np.linalg.norm(lateral_vec))

        a_along, a_lateral = projection(a_w)
        b_along, b_lateral = projection(b_w)
        roll_vec = b_w - a_w
        roll_projected = roll_vec - float(np.dot(roll_vec, axis_unit)) * axis_unit
        roll_width = float(np.linalg.norm(roll_projected))
        status = "usable" if roll_width > 1e-6 else "parallel to output Z"
        return {
            "a_along": a_along,
            "b_along": b_along,
            "a_lateral": a_lateral,
            "b_lateral": b_lateral,
            "z_separation": float(b_along - a_along),
            "roll_width": roll_width,
            "status": status,
        }


    def format_relation_metrics(self, editable_axis, roll_reference):
        wb = self.workbench
        metrics = self.relation_metrics(editable_axis, roll_reference)
        if not metrics:
            return [
                f"{tt('Axis/reference relation', wb.lang)}: {tt('needs two reference points', wb.lang)}",
            ]
        unit = self.spacing_unit()
        return [
            f"{tt('Axis/reference relation', wb.lang)}: {tt(metrics['status'], wb.lang)}",
            f"{tt('Roll A projection on output Z', wb.lang)}: {metrics['a_along']:.2f} {unit}",
            f"{tt('Roll B projection on output Z', wb.lang)}: {metrics['b_along']:.2f} {unit}",
            f"{tt('A/B separation along output Z', wb.lang)}: {metrics['z_separation']:.2f} {unit}",
            f"{tt('A/B lateral distance to output Z', wb.lang)}: A {metrics['a_lateral']:.2f} / B {metrics['b_lateral']:.2f} {unit}",
            f"{tt('A/B projected roll width', wb.lang)}: {metrics['roll_width']:.2f} {unit}",
        ]


    def update_summary(self):
        wb = self.workbench
        label = getattr(wb, "local_axis_summary_label", None)
        if label is None:
            return
        details_label = getattr(wb, "local_axis_details_label", None)
        details_check = getattr(wb, "local_axis_details_check", None)
        if wb.current_volume_scope != "part" or not wb.current_part_id or wb.image_volume is None:
            label.setText(tt("Local axis unavailable. Select a part volume.", wb.lang))
            if details_label is not None:
                details_label.setText("")
                details_label.setVisible(False)
            if details_check is not None:
                details_check.setVisible(False)
            return
        lines = [
            f"{tt('Part', wb.lang)}: {wb.current_part_id}",
            tt("Source Z axis: locked reference", wb.lang),
            tt(
                "3D overlay: on" if wb.display_mode == "volume" and self.overlay_enabled() else "3D overlay: off",
                wb.lang,
            ),
        ]
        detail_lines = []
        draft = self.current_draft()
        frame = None
        if draft is not None:
            editable = draft.get("editable_axis") or {}
            lines.append(
                tt("Draft output Z: {0}", wb.lang).format(
                    self.format_point_pair(editable)
                )
            )
            roll = draft.get("roll_reference") if isinstance(draft.get("roll_reference"), dict) else {}
            point_a = roll.get("point_a") if isinstance(roll.get("point_a"), dict) else {}
            point_b = roll.get("point_b") if isinstance(roll.get("point_b"), dict) else {}
            point_c = roll.get("point_c") if isinstance(roll.get("point_c"), dict) else {}
            if point_a.get("zyx") or point_b.get("zyx"):
                lines.append(
                    tt("Roll reference: {0}", wb.lang).format(
                        f"A={tt('set' if point_a.get('zyx') else 'not set', wb.lang)} / "
                        f"B={tt('set' if point_b.get('zyx') else 'not set', wb.lang)}"
                    )
                )
            else:
                lines.append(tt("Roll reference: A/B not set", wb.lang))
            lines.append(tt("Plane reference: C {0}", wb.lang).format(tt("set" if point_c.get("zyx") else "not set", wb.lang)))
            frame = self.refresh_frame(draft)
            lines.append(tt("Frame status: ready" if isinstance(frame, dict) else "Frame status: waiting for roll reference", wb.lang))
            detail_lines.extend(
                [
                    f"{tt('Output axis start z,y,x', wb.lang)}: {self.format_point(editable.get('start_zyx'))}",
                    f"{tt('Output axis end z,y,x', wb.lang)}: {self.format_point(editable.get('end_zyx'))}",
                    f"{tt('Roll reference A', wb.lang)}: {self.format_point(point_a.get('zyx'))}",
                    f"{tt('Roll reference B', wb.lang)}: {self.format_point(point_b.get('zyx'))}",
                    f"{tt('Plane reference C', wb.lang)}: {self.format_point(point_c.get('zyx'))}",
                ]
            )
            reference_plane = roll.get("reference_plane") if isinstance(roll.get("reference_plane"), dict) else draft.get("reference_plane") if isinstance(draft.get("reference_plane"), dict) else {}
            if isinstance(reference_plane, dict) and reference_plane.get("normal_axis_zyx"):
                detail_lines.append(f"{tt('Reference plane normal', wb.lang)}: {self.format_vector(reference_plane.get('normal_axis_zyx'))}")
            detail_lines.extend(self.format_relation_metrics(editable, roll))
            if isinstance(frame, dict):
                detail_lines.extend(
                    [
                        f"{tt('Local frame', wb.lang)} {tt('x_axis', wb.lang)}: {self.format_vector(frame.get('x_axis'))}",
                        f"{tt('Local frame', wb.lang)} {tt('y_axis', wb.lang)}: {self.format_vector(frame.get('y_axis'))}",
                        f"{tt('Local frame', wb.lang)} {tt('z_axis', wb.lang)}: {self.format_vector(frame.get('z_axis'))}",
                    ]
                )
        else:
            lines.append(tt("Draft output Z: none", wb.lang))
            lines.append(tt("Roll reference: A/B not set", wb.lang))
            lines.append(tt("Plane reference: C {0}", wb.lang).format(tt("not set", wb.lang)))
        reslice = self.current_part_reslice_record()
        if isinstance(reslice, dict):
            lines.append(tt("Saved reslice: {0}", wb.lang).format(reslice.get("reslice_id", "")))
            saved_axis = ((reslice.get("source") or {}).get("editable_axis") or {})
            saved_frame = reslice.get("local_frame") if isinstance(reslice.get("local_frame"), dict) else {}
            detail_lines.extend(
                [
                    f"{tt('Reslice ID', wb.lang)}: {reslice.get('reslice_id', '')}",
                    f"{tt('Image', wb.lang)}: {reslice.get('image_path', '')}",
                    f"{tt('Metadata', wb.lang)}: {reslice.get('metadata_path', '')}",
                    f"{tt('Output axis start z,y,x', wb.lang)}: {self.format_point(saved_axis.get('start_zyx'))}",
                    f"{tt('Output axis end z,y,x', wb.lang)}: {self.format_point(saved_axis.get('end_zyx'))}",
                ]
            )
            saved_roll = (
                saved_frame.get("roll_reference")
                if isinstance(saved_frame.get("roll_reference"), dict)
                else reslice.get("roll_reference")
                if isinstance(reslice.get("roll_reference"), dict)
                else {}
            )
            detail_lines.extend(self.format_relation_metrics(saved_axis, saved_roll))
            if saved_frame:
                detail_lines.extend(
                    [
                        f"{tt('Local frame', wb.lang)} {tt('x_axis', wb.lang)}: {self.format_vector(saved_frame.get('x_axis'))}",
                        f"{tt('Local frame', wb.lang)} {tt('y_axis', wb.lang)}: {self.format_vector(saved_frame.get('y_axis'))}",
                        f"{tt('Local frame', wb.lang)} {tt('z_axis', wb.lang)}: {self.format_vector(saved_frame.get('z_axis'))}",
                    ]
                )
        else:
            lines.append(tt("Saved reslice: none selected", wb.lang))
        label.setText("\n".join(lines))
        if details_label is not None:
            details_label.setText("\n".join(detail_lines))
            details_label.setVisible(bool(details_check and details_check.isChecked() and detail_lines))
        if details_check is not None:
            details_check.setVisible(bool(detail_lines))


    def project_zyx_to_volume_xy(self, point_zyx, shape_zyx, source_shape=None, spacing_zyx=None):
        wb = self.workbench
        if not point_zyx or len(point_zyx) != 3:
            return None
        shape = tuple(max(1, int(value)) for value in (shape_zyx or (1, 1, 1)))
        if len(shape) != 3:
            return None
        z, y, x = [float(value) for value in point_zyx]
        dims = np.array([max(1, shape[0] - 1), max(1, shape[1] - 1), max(1, shape[2] - 1)], dtype=np.float32)
        coord = np.array([x / dims[2], y / dims[1], z / dims[0]], dtype=np.float32) - 0.5
        x_scale, y_scale, z_scale = volume_shape_scale(source_shape or shape, spacing_zyx)
        coord[0] *= x_scale
        coord[1] *= y_scale
        coord[2] *= z_scale

        yaw = math.radians(float(wb._volume_yaw))
        pitch = math.radians(float(wb._volume_pitch))
        cy, sy = math.cos(yaw), math.sin(yaw)
        cp, sp = math.cos(pitch), math.sin(pitch)
        rot_yaw = np.array([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]], dtype=np.float32)
        rot_pitch = np.array([[1.0, 0.0, 0.0], [0.0, cp, -sp], [0.0, sp, cp]], dtype=np.float32)
        rotated = coord @ (rot_yaw @ rot_pitch).T

        width = max(1.0, float(wb.volume_canvas.width()) if hasattr(wb, "volume_canvas") else 1.0)
        height = max(1.0, float(wb.volume_canvas.height()) if hasattr(wb, "volume_canvas") else 1.0)
        scale = (min(width, height) * 0.78) * float(wb._volume_zoom)
        pan_scale = height * 0.5
        center_x = width / 2.0 + float(wb._volume_pan_x) * pan_scale
        center_y = height / 2.0 - float(wb._volume_pan_y) * pan_scale
        return [float(rotated[0] * scale + center_x), float(-rotated[1] * scale + center_y)]


    def source_point_for_current_reslice(self, point_zyx, saved_reslice=None):
        wb = self.workbench
        if not wb.current_reslice_id or not point_zyx:
            return point_zyx
        record = saved_reslice if isinstance(saved_reslice, dict) else self.current_part_reslice_record()
        if not isinstance(record, dict):
            return point_zyx
        frame = record.get("local_frame") if isinstance(record.get("local_frame"), dict) else {}
        params = record.get("reslice_params") if isinstance(record.get("reslice_params"), dict) else {}
        if not frame or not params:
            return point_zyx
        try:
            return source_point_to_reslice_point(point_zyx, frame, params)
        except Exception:
            return point_zyx


    def axis_for_current_reslice(self, axis, saved_reslice=None):
        wb = self.workbench
        if not isinstance(axis, dict):
            return {}
        if not wb.current_reslice_id:
            return axis
        converted = dict(axis)
        for key in ("start_zyx", "end_zyx"):
            if axis.get(key):
                converted[key] = self.source_point_for_current_reslice(axis.get(key), saved_reslice=saved_reslice)
        return converted


    def roll_for_current_reslice(self, roll, saved_reslice=None):
        wb = self.workbench
        if not isinstance(roll, dict):
            return {}
        if not wb.current_reslice_id:
            return roll
        converted = dict(roll)
        for key in ("point_a", "point_b", "point_c"):
            point = roll.get(key) if isinstance(roll.get(key), dict) else {}
            if point.get("zyx"):
                converted_point = dict(point)
                converted_point["zyx"] = self.source_point_for_current_reslice(point.get("zyx"), saved_reslice=saved_reslice)
                converted[key] = converted_point
        return converted


    def projection_context(self):
        wb = self.workbench
        shape = tuple(int(value) for value in getattr(wb.image_volume, "shape", ()) or ())
        if len(shape) != 3 or min(shape) <= 0:
            return None
        source_shape, spacing_zyx = wb.volume_render_controller._volume_source_geometry()
        x_scale, y_scale, z_scale = volume_shape_scale(source_shape or shape, spacing_zyx)
        yaw = math.radians(float(wb._volume_yaw))
        pitch = math.radians(float(wb._volume_pitch))
        cy, sy = math.cos(yaw), math.sin(yaw)
        cp, sp = math.cos(pitch), math.sin(pitch)
        rot_yaw = np.array([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]], dtype=np.float64)
        rot_pitch = np.array([[1.0, 0.0, 0.0], [0.0, cp, -sp], [0.0, sp, cp]], dtype=np.float64)
        rotation = rot_yaw @ rot_pitch
        width = max(1.0, float(wb.volume_canvas.width()) if hasattr(wb, "volume_canvas") else 1.0)
        height = max(1.0, float(wb.volume_canvas.height()) if hasattr(wb, "volume_canvas") else 1.0)
        scale = (min(width, height) * 0.78) * float(wb._volume_zoom)
        pan_scale = height * 0.5
        return {
            "shape": shape,
            "dims": np.array([max(1, shape[0] - 1), max(1, shape[1] - 1), max(1, shape[2] - 1)], dtype=np.float64),
            "shape_scale": np.array([x_scale, y_scale, z_scale], dtype=np.float64),
            "rotation": rotation,
            "scale": max(1e-6, scale),
            "center_x": width / 2.0 + float(wb._volume_pan_x) * pan_scale,
            "center_y": height / 2.0 - float(wb._volume_pan_y) * pan_scale,
        }


    def point_rotated_depth(self, point_zyx, context=None):
        wb = self.workbench
        if not point_zyx or len(point_zyx) != 3:
            return None
        context = context or self.projection_context()
        if context is None:
            return None
        z, y, x = [float(value) for value in point_zyx]
        dims = np.asarray(context["dims"], dtype=np.float64)
        coord = np.array([x / dims[2], y / dims[1], z / dims[0]], dtype=np.float64) - 0.5
        coord *= np.asarray(context["shape_scale"], dtype=np.float64)
        rotated = coord @ np.asarray(context["rotation"], dtype=np.float64).T
        return float(rotated[2])


    def volume_xy_to_zyx_at_depth(self, x, y, rotated_depth, context=None):
        wb = self.workbench
        context = context or self.projection_context()
        if context is None:
            return None
        rotated = np.array(
            [
                (float(x) - float(context["center_x"])) / float(context["scale"]),
                -(float(y) - float(context["center_y"])) / float(context["scale"]),
                float(rotated_depth),
            ],
            dtype=np.float64,
        )
        coord = rotated @ np.asarray(context["rotation"], dtype=np.float64)
        coord = coord / np.maximum(np.asarray(context["shape_scale"], dtype=np.float64), 1e-6)
        normalized_xyz = coord + 0.5
        dims = np.asarray(context["dims"], dtype=np.float64)
        point = np.array(
            [
                normalized_xyz[2] * dims[0],
                normalized_xyz[1] * dims[1],
                normalized_xyz[0] * dims[2],
            ],
            dtype=np.float64,
        )
        shape = context["shape"]
        upper = np.array([max(0, shape[0] - 1), max(0, shape[1] - 1), max(0, shape[2] - 1)], dtype=np.float64)
        point = np.clip(point, np.zeros(3, dtype=np.float64), upper)
        return [float(value) for value in point]


    def clip_plane_rotated_depth(self, context=None):
        wb = self.workbench
        context = context or self.projection_context()
        if context is None:
            return None
        shape_scale = np.asarray(context["shape_scale"], dtype=np.float64)
        half_size = shape_scale * 0.5
        view_normal = np.asarray([0.0, 0.0, 1.0], dtype=np.float64)
        extent = max(float(np.dot(np.abs(view_normal), half_size)), 0.0001)
        depth = float(wb.volume_clip_plane_depth_slider.value()) / 100.0 if hasattr(wb, "volume_clip_plane_depth_slider") else 0.0
        return float((1.0 - 2.0 * max(0.0, min(1.0, depth))) * extent)


    def volume_xy_to_zyx_on_clip_plane(self, x, y):
        wb = self.workbench
        context = self.projection_context()
        depth = self.clip_plane_rotated_depth(context)
        if depth is None:
            return None
        return self.volume_xy_to_zyx_at_depth(x, y, depth, context)


    def hit_endpoint(self, x, y):
        wb = self.workbench
        draft = self.current_draft()
        if not isinstance(draft, dict) or wb.current_reslice_id:
            return None
        editable = draft.get("editable_axis") or {}
        if editable.get("locked"):
            return None
        context = self.projection_context()
        if context is None:
            return None
        candidates = []
        for endpoint_key in ("start_zyx", "end_zyx"):
            point = editable.get(endpoint_key)
            xy = self.project_zyx_to_volume_xy(point, context["shape"])
            if xy is None:
                continue
            distance = math.hypot(float(x) - float(xy[0]), float(y) - float(xy[1]))
            candidates.append((distance, endpoint_key, point, xy))
        if not candidates:
            return None
        distance, endpoint_key, point, xy = min(candidates, key=lambda item: item[0])
        hit_radius = max(10.0, min(22.0, 8.0 + float(wb._volume_zoom) * 1.2))
        if distance > hit_radius:
            return None
        return {
            "endpoint_key": endpoint_key,
            "start_mouse_xy": [float(x), float(y)],
            "start_point_zyx": [float(value) for value in point],
            "rotated_depth": self.point_rotated_depth(point, context),
            "context": context,
            "hit_xy": xy,
        }


    def hit_body(self, x, y):
        wb = self.workbench
        draft = self.current_draft()
        if not isinstance(draft, dict) or wb.current_reslice_id:
            return None
        editable = draft.get("editable_axis") or {}
        if editable.get("locked"):
            return None
        context = self.projection_context()
        if context is None:
            return None
        start = editable.get("start_zyx") or []
        end = editable.get("end_zyx") or []
        start_xy = self.project_zyx_to_volume_xy(start, context["shape"])
        end_xy = self.project_zyx_to_volume_xy(end, context["shape"])
        if not start_xy or not end_xy:
            return None
        segment = np.asarray(end_xy, dtype=np.float64) - np.asarray(start_xy, dtype=np.float64)
        length_sq = float(np.dot(segment, segment))
        if length_sq <= 1e-6:
            return None
        mouse = np.asarray([float(x), float(y)], dtype=np.float64)
        start_arr = np.asarray(start_xy, dtype=np.float64)
        fraction = max(0.0, min(1.0, float(np.dot(mouse - start_arr, segment) / length_sq)))
        closest = start_arr + segment * fraction
        distance = float(np.linalg.norm(mouse - closest))
        hit_radius = max(8.0, min(18.0, 7.0 + float(wb._volume_zoom) * 0.9))
        if distance > hit_radius:
            return None
        start_depth = self.point_rotated_depth(start, context)
        end_depth = self.point_rotated_depth(end, context)
        if start_depth is None or end_depth is None:
            return None
        anchor_depth = start_depth + (end_depth - start_depth) * fraction
        anchor_point = self.volume_xy_to_zyx_at_depth(x, y, anchor_depth, context)
        if anchor_point is None:
            return None
        return {
            "endpoint_key": "axis_body",
            "start_mouse_xy": [float(x), float(y)],
            "start_axis_start_zyx": [float(value) for value in start],
            "start_axis_end_zyx": [float(value) for value in end],
            "start_anchor_zyx": [float(value) for value in anchor_point],
            "rotated_depth": float(anchor_depth),
            "context": context,
            "hit_xy": [float(closest[0]), float(closest[1])],
        }


    def start_endpoint_drag(self, x, y):
        wb = self.workbench
        if not self.overlay_enabled():
            return False
        hit = self.hit_endpoint(x, y)
        if hit is None:
            hit = self.hit_body(x, y)
        if hit is None or hit.get("rotated_depth") is None:
            return False
        self.state.endpoint_drag = hit
        wb.volume_render_controller._start_volume_interaction()
        if hit.get("endpoint_key") == "axis_body":
            self._set_status(tt("Dragging output axis body.", wb.lang))
        else:
            endpoint_text = tt("start", wb.lang) if hit.get("endpoint_key") == "start_zyx" else tt("end", wb.lang)
            self._set_status(tt("Dragging output axis {0}.", wb.lang).format(endpoint_text))
        return True


    def drag_endpoint(self, x, y):
        wb = self.workbench
        drag = self.state.endpoint_drag if isinstance(self.state.endpoint_drag, dict) else None
        draft = self.current_draft()
        if drag is None or draft is None:
            return False
        point = self.volume_xy_to_zyx_at_depth(x, y, drag.get("rotated_depth"), drag.get("context"))
        if point is None:
            return False
        editable = dict(draft.get("editable_axis") or {})
        endpoint_key = str(drag.get("endpoint_key") or "")
        if endpoint_key == "axis_body":
            start_anchor = np.asarray(drag.get("start_anchor_zyx") or [], dtype=np.float64)
            start_axis = np.asarray(drag.get("start_axis_start_zyx") or [], dtype=np.float64)
            end_axis = np.asarray(drag.get("start_axis_end_zyx") or [], dtype=np.float64)
            next_anchor = np.asarray(point, dtype=np.float64)
            if start_anchor.size != 3 or start_axis.size != 3 or end_axis.size != 3:
                return False
            delta = next_anchor - start_anchor
            shape = tuple(int(value) for value in getattr(wb.image_volume, "shape", ()) or ())
            if len(shape) != 3:
                return False
            upper = np.asarray([max(0, shape[0] - 1), max(0, shape[1] - 1), max(0, shape[2] - 1)], dtype=np.float64)
            axis_min = np.minimum(start_axis, end_axis)
            axis_max = np.maximum(start_axis, end_axis)
            min_delta = -axis_min
            max_delta = upper - axis_max
            delta = np.minimum(np.maximum(delta, min_delta), max_delta)
            editable["start_zyx"] = [round(float(value), 3) for value in start_axis + delta]
            editable["end_zyx"] = [round(float(value), 3) for value in end_axis + delta]
        elif endpoint_key in {"start_zyx", "end_zyx"}:
            other_key = "end_zyx" if endpoint_key == "start_zyx" else "start_zyx"
            other = editable.get(other_key) or []
            if len(other) == 3 and float(np.linalg.norm(np.asarray(point, dtype=np.float64) - np.asarray(other, dtype=np.float64))) < 0.25:
                return False
            editable[endpoint_key] = [round(float(value), 3) for value in point]
        else:
            return False
        draft["editable_axis"] = editable
        draft["dirty"] = True
        self.refresh_frame(draft)
        self.state.draft = draft
        self.update_summary()
        if hasattr(wb.volume_canvas, "set_axis_overlays"):
            wb.volume_canvas.set_axis_overlays(self.volume_overlays())
        wb.volume_render_controller._request_volume_interaction_render()
        return True


    def finish_endpoint_drag(self):
        wb = self.workbench
        drag = self.state.endpoint_drag if isinstance(self.state.endpoint_drag, dict) else None
        self.state.endpoint_drag = None
        if drag is None:
            return
        if drag.get("endpoint_key") == "axis_body":
            self._set_status(tt("Moved output axis body.", wb.lang))
        else:
            endpoint_text = tt("start", wb.lang) if drag.get("endpoint_key") == "start_zyx" else tt("end", wb.lang)
            self._set_status(tt("Updated output axis {0}.", wb.lang).format(endpoint_text))
        self.update_summary()


    def volume_overlays(self):
        wb = self.workbench
        if not self.overlay_enabled():
            return []
        shape = tuple(int(value) for value in getattr(wb.image_volume, "shape", ()) or ())
        if len(shape) != 3:
            return []
        source_shape, spacing_zyx = wb.volume_render_controller._volume_source_geometry()
        overlays = []
        saved_reslice = None

        def add_axis(start, end, label, color, width=2, label_anchor="end", label_offset=(8, -8), label_position="right", role="reference"):
            start_xy = self.project_zyx_to_volume_xy(start, shape, source_shape=source_shape, spacing_zyx=spacing_zyx)
            end_xy = self.project_zyx_to_volume_xy(end, shape, source_shape=source_shape, spacing_zyx=spacing_zyx)
            if start_xy and end_xy:
                anchor_xy = start_xy if str(label_anchor) == "start" else end_xy
                overlays.append(
                    {
                        "start_xy": start_xy,
                        "end_xy": end_xy,
                        "label": label,
                        "color": color,
                        "width": width,
                        "label_anchor_xy": anchor_xy,
                        "label_offset_xy": list(label_offset),
                        "label_position": label_position,
                        "role": role,
                    }
                )

        saved_reslice_source = {}
        saved_reslice_frame = {}
        if wb.current_reslice_id:
            saved_reslice = self.current_part_reslice_record()
            if isinstance(saved_reslice, dict):
                has_exported_reslice_image = bool(str(saved_reslice.get("image_path") or "").strip())
                saved_reslice_source = saved_reslice.get("source") if has_exported_reslice_image and isinstance(saved_reslice.get("source"), dict) else {}
                saved_reslice_frame = saved_reslice.get("local_frame") if has_exported_reslice_image and isinstance(saved_reslice.get("local_frame"), dict) else {}
                if not saved_reslice_source:
                    return []

        source_z = saved_reslice_source.get("source_axis") if isinstance(saved_reslice_source.get("source_axis"), dict) else self.source_z_axis_for_current_part()
        source_z = self.axis_for_current_reslice(source_z, saved_reslice=saved_reslice)
        add_axis(
            source_z.get("start_zyx"),
            source_z.get("end_zyx"),
            tt("source Z", wb.lang),
            "#6AA6FF",
            width=2,
            label_anchor="start",
            label_offset=(-10, 18),
            label_position="left",
            role="locked_reference",
        )

        editable = {}
        draft = self.current_draft()
        if isinstance(draft, dict):
            editable = draft.get("editable_axis") or {}
        elif saved_reslice_source:
            editable = (
                saved_reslice_source.get("final_editable_axis")
                or saved_reslice_source.get("editable_axis")
                or saved_reslice_source.get("initial_editable_axis")
                or {}
            )
        editable = self.axis_for_current_reslice(editable, saved_reslice=saved_reslice)
        if editable.get("start_zyx") and editable.get("end_zyx"):
            add_axis(
                editable.get("start_zyx"),
                editable.get("end_zyx"),
                tt("output Z", wb.lang),
                "#FFB84D",
                width=3,
                label_anchor="end",
                label_offset=(10, -14),
                label_position="right",
                role="editable_output",
            )
        roll = (draft or {}).get("roll_reference") if isinstance(draft, dict) else {}
        if not roll and isinstance(saved_reslice_frame, dict):
            roll = saved_reslice_frame.get("roll_reference") if isinstance(saved_reslice_frame.get("roll_reference"), dict) else {}
        roll = self.roll_for_current_reslice(roll, saved_reslice=saved_reslice)
        point_a = roll.get("point_a") if isinstance(roll, dict) and isinstance(roll.get("point_a"), dict) else {}
        point_b = roll.get("point_b") if isinstance(roll, dict) and isinstance(roll.get("point_b"), dict) else {}
        point_c = roll.get("point_c") if isinstance(roll, dict) and isinstance(roll.get("point_c"), dict) else {}
        roll_a_xy = self.project_zyx_to_volume_xy(point_a.get("zyx"), shape, source_shape=source_shape, spacing_zyx=spacing_zyx) if point_a.get("zyx") else None
        roll_b_xy = self.project_zyx_to_volume_xy(point_b.get("zyx"), shape, source_shape=source_shape, spacing_zyx=spacing_zyx) if point_b.get("zyx") else None
        roll_c_xy = self.project_zyx_to_volume_xy(point_c.get("zyx"), shape, source_shape=source_shape, spacing_zyx=spacing_zyx) if point_c.get("zyx") else None
        if roll_a_xy and roll_b_xy:
            overlays.append(
                {
                    "start_xy": roll_a_xy,
                    "end_xy": roll_b_xy,
                    "label": tt("Roll reference", wb.lang),
                    "color": "#7CE3A1",
                    "width": 2,
                    "label_anchor_xy": roll_b_xy,
                    "label_offset_xy": [10, 16],
                    "label_position": "right",
                }
            )
        if roll_a_xy and roll_b_xy and roll_c_xy:
            overlays.append(
                {
                    "kind": "polyline",
                    "points_xy": [roll_a_xy, roll_b_xy, roll_c_xy, roll_a_xy],
                    "label": tt("A/B/C reference plane", wb.lang),
                    "color": "#D6C56D",
                    "width": 2,
                    "label_anchor_xy": roll_c_xy,
                    "label_offset_xy": [10, 18],
                    "label_position": "right",
                }
            )
        for point, fallback_label, color, offset in (
            (point_a, "Roll reference A", "#7CE3A1", (-18, -12)),
            (point_b, "Roll reference B", "#66D9EF", (10, -12)),
            (point_c, "Plane reference C", "#D6C56D", (10, 16)),
        ):
            xy = self.project_zyx_to_volume_xy(point.get("zyx"), shape, source_shape=source_shape, spacing_zyx=spacing_zyx) if point.get("zyx") else None
            if xy:
                overlays.append(
                    {
                        "kind": "point",
                        "point_xy": xy,
                        "label": tt(fallback_label, wb.lang),
                        "color": color,
                        "radius": 5,
                        "label_offset_xy": list(offset),
                        "label_position": "right",
                    }
                )
        return overlays


    def export_context_matches_current(self, task_id, *, fields=("specimen_id", "volume_scope", "part_id", "reslice_id")):
        return self.workbench._task_context_matches_current(task_id, fields=fields)

    def cleanup_export(self, thread=None, worker=None):
        wb = self.workbench
        if thread is not None and self.state.export_thread is not thread:
            return
        if worker is not None and self.state.export_worker is not worker:
            return
        if self.state.export_progress is not None:
            self.state.export_progress.close()
            self.state.export_progress.deleteLater()
        self.state.export_progress = None
        self.state.export_worker = None
        self.state.export_thread = None
        self.state.export_context = {}
        self.state.export_task_id = ""
        wb._set_scope_controls_enabled()


    def on_export_progress(self, current, total, message):
        wb = self.workbench
        wb._progress_tif_task(self.state.export_task_id, current, total, str(message or ""))
        progress = self.state.export_progress
        if progress is None:
            return
        total = int(total or 0)
        if total <= 0:
            progress.setRange(0, 0)
        else:
            maximum = max(1, total)
            value = max(0, min(maximum, int(current or 0)))
            progress.setRange(0, maximum)
            progress.setValue(value)
        progress.setLabelText(tt(message, wb.lang))


    def on_export_finished(self, result):
        wb = self.workbench
        context = dict(self.state.export_context or {})
        task_id = self.state.export_task_id
        task_current = wb._task_context_matches_current(task_id, fields=("specimen_id", "volume_scope", "part_id", "reslice_id"))
        if not isinstance(result, dict):
            message = tt("Local Axis Reslice export did not return a result.", wb.lang)
            wb._fail_tif_task(task_id, message, message=message)
            if task_current:
                self._set_status(message)
            wb.log(message)
            if task_current:
                QMessageBox.warning(wb, tt("Local Axis Reslice", wb.lang), message)
            return
        record = result.get("record", {})
        reslice_id = record.get("reslice_id", "")
        message = tt("Exported local axis reslice {0}.", wb.lang).format(reslice_id)
        wb._finish_tif_task(task_id, payload=result, message="local_axis_export_finished")
        if task_current:
            self._set_status(message)
            wb.training_status_label.setText(message)
        wb.log(message)
        if task_current:
            self.state.pick_target = ""
            self.state.roll_pick_target = ""
        wb.refresh_project(reload_current=False)
        if task_current:
            wb.selection_workflow_controller.select_payload({
                "scope": "part_reslice",
                "specimen_id": context.get("specimen_id") or wb.current_specimen_id,
                "part_id": context.get("part_id") or wb.current_part_id,
                "reslice_id": reslice_id,
            })


    def on_export_failed(self, message):
        wb = self.workbench
        task_id = self.state.export_task_id
        task_current = wb._task_context_matches_current(task_id, fields=("specimen_id", "volume_scope", "part_id", "reslice_id"))
        wb._fail_tif_task(task_id, str(message or ""), message=str(message or ""))
        message = str(message or "")
        if task_current:
            self._set_status(message)
            QMessageBox.warning(wb, tt("Local Axis Reslice", wb.lang), message)
        wb.log(message)


    def export_current_reslice(self):
        wb = self.workbench
        if not wb.coordinator.guard_backend_write_lock():
            return None
        source_specimen_id = wb.current_specimen_id
        source_part_id = wb.current_part_id
        if self.export_running():
            QMessageBox.information(
                wb,
                tt("Local Axis Reslice", wb.lang),
                tt("Local Axis Reslice export is already running.", wb.lang),
            )
            return None
        try:
            payload = self.current_reslice_payload()
        except Exception as exc:
            message = str(exc)
            self._set_status(message)
            wb.log(message)
            QMessageBox.warning(wb, tt("Local Axis Reslice", wb.lang), message)
            return None

        progress = QProgressDialog(
            tt("Exporting confirmed Local Axis Reslice...", wb.lang),
            "",
            0,
            0,
            wb,
        )
        progress.setWindowTitle(tt("Local Axis Reslice", wb.lang))
        progress.setCancelButton(None)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setMinimumDuration(0)
        progress.setWindowModality(Qt.WindowModal)
        progress.show()

        thread = QThread(wb)
        worker = TifLocalAxisResliceExportWorker(wb.project, source_specimen_id, source_part_id, payload)
        worker.moveToThread(thread)
        self.state.export_thread = thread
        self.state.export_worker = worker
        self.state.export_progress = progress
        self.state.export_context = {
            "specimen_id": source_specimen_id,
            "part_id": source_part_id,
        }
        task = wb._start_tif_task(
            "local_axis_export",
            action="export_local_axis_reslice",
            payload={
                "specimen_id": source_specimen_id,
                "part_id": source_part_id,
                "reslice_id": payload.get("reslice_id", ""),
            },
            request_key=wb._task_request_key((source_specimen_id, source_part_id, payload.get("reslice_id", ""))),
            message=tt("Local Axis Reslice export is running. Wait until it finishes before editing project data.", wb.lang),
        )
        self.state.export_task_id = task.task_id
        self.set_export_controls_enabled(False)

        thread.started.connect(worker.run)
        worker.progress.connect(self.on_export_progress)
        worker.finished.connect(self.on_export_finished)
        worker.failed.connect(self.on_export_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(lambda t=thread, w=worker: self.cleanup_export(t, w))
        thread.finished.connect(thread.deleteLater)

        thread.start()
        wb.training_status_label.setText(tt("Exporting confirmed Local Axis Reslice...", wb.lang))
        return {
            "status": "running",
            "specimen_id": source_specimen_id,
            "part_id": source_part_id,
            "reslice_id": payload.get("reslice_id", ""),
        }


    def export_training_manifest_dialog(self):
        wb = self.workbench
        if not wb._ensure_tif_project_open():
            return None
        default_dir = os.path.join(wb.project.project_dir, "exports", "local_axis_training")
        os.makedirs(default_dir, exist_ok=True)
        output_dir = QFileDialog.getExistingDirectory(wb, tt("Export confirmed Local Axis training manifest", wb.lang), default_dir)
        if not output_dir:
            return None
        request = wb.local_axis_service.build_manifest_export_request(
            wb.project,
            output_dir,
            template_id=wb.current_part_id if wb.current_volume_scope == "part" else "",
        )
        if not request:
            QMessageBox.warning(wb, tt("Local Axis data", wb.lang), request.message or ", ".join(request.reasons or []))
            return None
        filters = request.payload.get("filters", {})
        output_dir = request.payload.get("output_dir", output_dir)
        try:
            result = export_local_axis_training_manifest(wb.project, output_dir, filters)
        except Exception as exc:
            QMessageBox.warning(wb, tt("Local Axis data", wb.lang), str(exc))
            return None
        message = tt("Exported confirmed Local Axis training manifest: {0} samples\n{1}", wb.lang).format(
            result.get("sample_count", 0),
            result.get("manifest_path", ""),
        )
        wb.training_status_label.setText(message)
        self._set_status(message)
        wb.log(message)
        return result
