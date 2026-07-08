from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import QMessageBox

try:
    from AntSleap.core.tif_local_axis_reslice import align_editable_axis_to_reference_plane
    from AntSleap.ui.tif_workbench_translations import tt
except ModuleNotFoundError as exc:
    if exc.name != "AntSleap":
        raise
    from core.tif_local_axis_reslice import align_editable_axis_to_reference_plane
    from ui.tif_workbench_translations import tt


class TifLocalAxisController:
    def __init__(self, workbench):
        self.workbench = workbench

    @property
    def lang(self):
        return self.workbench.lang

    @property
    def service(self):
        return self.workbench.local_axis_service

    def _set_status(self, message, tooltip=""):
        self.workbench._set_local_axis_status(message, tooltip=tooltip)

    def ignored_draft_lock_task_types(self):
        return self.workbench._preview_interaction_task_types()

    def guard_draft_interaction(self, show_message=True):
        ignored = self.ignored_draft_lock_task_types()
        if self.workbench._guard_backend_write_lock(show_message=show_message, ignored_task_types=ignored):
            return True
        if not show_message:
            self._set_status(self.workbench._backend_write_lock_message(ignored_task_types=ignored))
        return False

    def export_running(self):
        return self.workbench._local_axis_reslice_export_thread is not None

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
        draft = self.workbench.local_axis_draft if isinstance(self.workbench.local_axis_draft, dict) else None
        if draft is None:
            return
        if str(draft.get("specimen_id", "")) != str(specimen_id or "") or str(draft.get("part_id", "")) != str(part_id or ""):
            self.workbench.local_axis_draft = None

    def current_draft(self):
        wb = self.workbench
        draft = wb.local_axis_draft if isinstance(wb.local_axis_draft, dict) else None
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
        _, spacing_zyx = self.workbench._volume_source_geometry()
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
            canvas.set_axis_overlays(self.workbench._local_axis_volume_overlays())

    def _sync_after_draft_change(self, *, request_render=False, render_volume=False):
        self.sync_pick_buttons()
        self.workbench._update_local_axis_summary()
        self._set_axis_overlays()
        if request_render:
            self.workbench._request_volume_interaction_render()
        if render_volume and self.workbench.display_mode == "volume":
            self.workbench.render_volume_preview()

    def set_draft(self, draft, status_message=""):
        wb = self.workbench
        if not isinstance(draft, dict):
            wb.local_axis_draft = None
        else:
            draft.setdefault("specimen_id", wb.current_specimen_id)
            draft.setdefault("part_id", wb.current_part_id)
            draft.setdefault("template_id", str(wb.current_part_id or "generic"))
            self.refresh_frame(draft)
            wb.local_axis_draft = draft
        if hasattr(wb, "volume_local_axes_check"):
            wb.volume_local_axes_check.setChecked(True)
        self._sync_after_draft_change(render_volume=wb.display_mode == "volume")
        specimen = wb.project.get_specimen(wb.current_specimen_id, default=None) if wb.current_specimen_id else None
        if specimen is not None:
            wb._update_status_labels(specimen, part=wb.current_part if wb.current_volume_scope == "part" else None)
        if status_message:
            self._set_status(status_message)
            wb.log(status_message)
        return wb.local_axis_draft

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
        wb.local_axis_draft = draft
        if hasattr(wb, "volume_local_axes_check"):
            wb.volume_local_axes_check.setChecked(True)
        message = tt("Copied source Z axis as editable output axis.", self.lang)
        self._set_status(message)
        wb.log(message)
        specimen = wb.project.get_specimen(wb.current_specimen_id, default=None)
        if specimen is not None:
            wb._update_status_labels(specimen, part=wb.current_part)
        if wb.display_mode == "volume":
            wb.render_volume_preview()
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
        if target and wb._backend_write_lock_active(ignored_task_types=ignored_tasks):
            wb._guard_backend_write_lock(ignored_task_types=ignored_tasks)
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
        wb._local_axis_pick_target = target
        wb._local_axis_roll_pick_target = target if target in {"roll_a", "roll_b", "roll_c"} else ""
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
        point = wb._volume_xy_to_zyx_on_clip_plane(x, y)
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
        wb.local_axis_draft = draft
        wb._local_axis_pick_target = ""
        wb._local_axis_roll_pick_target = ""
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
        wb.local_axis_draft = dict(result.payload.get("draft") or {})
        wb._local_axis_pick_target = ""
        wb._local_axis_roll_pick_target = ""
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
        wb.local_axis_draft = draft
        self._sync_after_draft_change(request_render=True)
        message = tt("Aligned output Z perpendicular to the A/B/C reference plane.", self.lang)
        self._set_status(message)
        wb.log(message)
        return True

    def clear_draft(self):
        wb = self.workbench
        if not self.guard_draft_interaction():
            return
        wb.local_axis_draft = None
        wb._local_axis_pick_target = ""
        wb._local_axis_roll_pick_target = ""
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

    def export_context_matches_current(self, task_id, *, fields=("specimen_id", "volume_scope", "part_id")):
        return self.workbench._task_context_matches_current(task_id, fields=fields)
