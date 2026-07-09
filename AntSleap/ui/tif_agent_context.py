from __future__ import annotations


def _triplet_text(values):
    values = tuple(values or ())
    if len(values) != 3:
        return ""
    return f"{values[0]}/{values[1]}/{values[2]}"


class TifAgentContextBuilder:
    def __init__(self, workbench):
        self.workbench = workbench

    def build(self):
        wb = self.workbench
        selected_material = wb._selected_material()
        material_id = ""
        if isinstance(selected_material, dict):
            material_id = selected_material.get("id", "")
        current_part = getattr(wb, "current_part", None)
        current_part = current_part if isinstance(current_part, dict) else {}
        active_part_tag_ids = [str(item) for item in current_part.get("user_tags", []) if str(item or "")]
        try:
            tag_lookup = wb._part_user_tag_lookup()
        except Exception:
            tag_lookup = {}
        active_part_group_tags = ", ".join(str(tag_lookup.get(tag_id, tag_id)) for tag_id in active_part_tag_ids)
        recent_log = ""
        if hasattr(wb, "log_console"):
            recent_log = "\n".join(wb.log_console.toPlainText().splitlines()[-6:])

        source_shape, spacing_zyx = wb._volume_source_geometry()
        active_label_role = wb.label_role_combo.currentData() or ""
        active_label_volume = wb.label_volume
        if active_label_role == "working_edit" and wb.edit_volume is not None:
            active_label_volume = wb.edit_volume
        label_shape = tuple(int(value) for value in getattr(active_label_volume, "shape", ()) or ())
        axis = wb._current_slice_axis()
        slice_position = ""
        if wb.image_volume is not None:
            slice_position = f"{int(wb.slice_slider.value()) + 1}/{wb._slice_count_for_axis(axis)}"

        readiness_text = ""
        readiness_reasons = ""
        if wb.current_specimen_id and wb.current_volume_scope == "part" and wb.current_part_id:
            try:
                readiness = wb.project.evaluate_part_train_ready(
                    wb.current_specimen_id,
                    wb.current_part_id,
                    wb.current_reslice_id,
                    validate_label_ids=False,
                )
            except Exception:
                readiness = {}
            if readiness:
                readiness_text = "yes" if readiness.get("train_ready") else "no"
                readiness_reasons = ",".join(str(item) for item in readiness.get("reasons", []) if str(item))
        elif wb.current_specimen_id:
            try:
                readiness = wb.project.evaluate_train_ready(wb.current_specimen_id)
            except Exception:
                readiness = {}
            if readiness:
                readiness_text = "yes" if readiness.get("train_ready") else "no"
                readiness_reasons = ",".join(str(item) for item in readiness.get("reasons", []) if str(item))

        clarity = "on" if bool(getattr(wb, "_volume_clarity_mode", False)) else "off"
        volume_status = ""
        if wb.image_volume is not None:
            volume_status = wb.volume_canvas_overlay_text()
        volume_perf = wb.volume_performance_report() if wb.image_volume is not None else {}
        backend_config = wb._backend_config_from_ui()
        train_ready_part_refs = []
        train_ready_top_level_count = 0
        if wb.project is not None:
            try:
                train_ready_part_refs = wb._train_ready_part_refs()
            except Exception:
                train_ready_part_refs = []
            try:
                train_ready_top_level_count = len(wb.project.list_train_ready_specimens())
            except Exception:
                train_ready_top_level_count = 0
        if train_ready_part_refs:
            training_scope = "part_reslice"
        elif train_ready_top_level_count:
            training_scope = "top_level_volume"
        else:
            training_scope = ""
        selected_model_record = wb._selected_tif_model_record() if hasattr(wb, "model_library_combo") else None
        selected_model_manifest = ""
        selected_model_id = ""
        if selected_model_record:
            selected_model_id = wb._tif_model_record_id(selected_model_record)
            selected_model_manifest = wb.project.to_absolute(selected_model_record.get("model_manifest", ""))
        elif hasattr(wb, "backend_manifest_edit"):
            selected_model_manifest = str(wb.backend_manifest_edit.text() or "").strip()
        model_count = 0
        try:
            model_count = len(wb._tif_model_records())
        except Exception:
            model_count = 0
        command_presence = {
            "prepare_dataset": bool(str(backend_config.get("prepare_dataset_command") or "").strip()),
            "train": bool(str(backend_config.get("train_command") or "").strip()),
            "predict": bool(str(backend_config.get("predict_command") or "").strip()),
        }
        predict_filter = ""
        predict_filter_label = ""
        if hasattr(wb, "predict_filter_combo") and wb.predict_filter_combo.count():
            predict_filter = str(wb.predict_filter_combo.currentData() or "")
            predict_filter_label = str(wb.predict_filter_combo.currentText() or "")
        predict_target_summary = ""
        if hasattr(wb, "predict_targets_summary_label"):
            predict_target_summary = str(wb.predict_targets_summary_label.text() or "")
        selected_predict_targets = []
        for key in sorted(getattr(wb, "_tif_predict_selected_refs", set()) or set())[:8]:
            if isinstance(key, (list, tuple)) and len(key) >= 3:
                selected_predict_targets.append("/".join(str(item or "") for item in key[:3]))
            else:
                selected_predict_targets.append(str(key))
        task_summary = wb._task_summary_for_context()
        state_summary = wb._current_state_summary()
        preview_resource_summary = ""
        local_axis_state_summary = ""
        if isinstance(state_summary, dict):
            preview_resource_summary = str(state_summary.get("preview_resource") or "")
            local_axis_state_summary = str(state_summary.get("local_axis") or "")

        return {
            "source_workbench": "tif_volume",
            "project_type": "tif_volume",
            "project_path": getattr(wb.project, "current_project_path", "") or "",
            "active_specimen_id": wb.current_specimen_id,
            "active_volume_scope": wb.current_volume_scope,
            "active_part_id": wb.current_part_id,
            "active_reslice_id": wb.current_reslice_id,
            "active_part_parent_bbox_zyx": str((wb.current_part or {}).get("parent_bbox_zyx", "")),
            "active_part_group_tags": active_part_group_tags,
            "active_label_role": active_label_role,
            "selected_material_id": material_id,
            "display_mode": wb.display_mode,
            "active_slice_axis": axis,
            "active_slice_position": slice_position,
            "active_volume_shape_zyx": _triplet_text(source_shape),
            "active_volume_spacing_zyx": _triplet_text(spacing_zyx),
            "active_label_shape_zyx": _triplet_text(label_shape),
            "train_ready_status": readiness_text,
            "train_ready_reasons": readiness_reasons,
            "active_label_schema_id": wb._active_part_label_schema_id(),
            "train_ready_part_sample_count": str(len(train_ready_part_refs)),
            "train_ready_top_level_sample_count": str(train_ready_top_level_count),
            "training_selection_scope": training_scope,
            "training_sample_rule": "prepare/train uses all project train-ready part/reslice manual_truth samples; if none exist, it falls back to train-ready top-level specimen volumes. A label schema alone is not enough.",
            "registered_tif_model_count": str(model_count),
            "selected_tif_model_id": selected_model_id,
            "selected_model_manifest": selected_model_manifest,
            "tif_backend_id": str(backend_config.get("backend_id") or ""),
            "tif_backend_python": str(backend_config.get("python_executable") or ""),
            "tif_backend_command_presence": str(command_presence),
            "backend_run_active": "yes" if wb._backend_action_running() else "no",
            "backend_action": str(wb._tif_backend_action or ""),
            "backend_run_dir": str(wb._tif_backend_run_dir or ""),
            "backend_result_json": str(wb._tif_backend_result_json or ""),
            "predict_group_filter": predict_filter,
            "predict_group_filter_label": predict_filter_label,
            "predict_target_summary": predict_target_summary,
            "predict_selected_target_count": str(len(getattr(wb, "_tif_predict_selected_refs", set()) or set())),
            "predict_selected_targets": "; ".join(selected_predict_targets),
            "tif_task_summary": str(task_summary),
            "tif_state_summary": str(state_summary),
            "preview_resource_summary": preview_resource_summary,
            "local_axis_state_summary": local_axis_state_summary,
            "volume_renderer": wb._volume_canvas_renderer,
            "volume_renderer_label": wb._volume_renderer_label(),
            "volume_render_mode": wb._volume_render_mode,
            "volume_projection_mode": wb._volume_projection_mode(),
            "volume_mask_mode": wb._volume_mask_mode(),
            "volume_density_cutoff": f"{int(wb.volume_cutoff_slider.value())}%",
            "volume_density_opacity": f"{int(wb.volume_transfer_opacity_slider.value())}%",
            "volume_texture_target_dim": str(wb._active_volume_target_dim()),
            "volume_ray_samples": str(wb._active_volume_sample_count()),
            "volume_clarity_mode": clarity,
            "volume_detail_enhancement": f"{int(wb.volume_enhancement_slider.value())}%",
            "volume_tone_curve": f"{int(wb.volume_tone_slider.value())}%",
            "volume_shader_quality": wb._volume_shader_quality_mode(),
            "volume_surface_refine": "on" if wb.volume_surface_refine_check.isChecked() else "off",
            "volume_clip_plane": "on" if wb.volume_clip_plane_check.isChecked() else "off",
            "volume_clip_plane_depth": f"{int(wb.volume_clip_plane_depth_slider.value())}%",
            "volume_roi_high_detail": "on" if wb.volume_roi_detail_check.isChecked() else "off",
            "volume_roi_inspect": "on" if wb._volume_roi_inspect_enabled() else "off",
            "volume_roi_scale": f"{wb._active_volume_roi_scale():.1f}x",
            "volume_roi_budget": f"{wb._roi_texture_budget_bytes() / (1024.0 ** 3):.1f} GB",
            "volume_inside_depth": f"{int(wb.volume_inside_slider.value())}%",
            "volume_front_cut": f"{int(wb.volume_clip_slider.value())}%",
            "volume_zoom": f"{int(round(float(wb._volume_zoom) * 100))}%",
            "volume_pan": f"x={int(round(float(wb._volume_pan_x) * 100))}%, y={int(round(float(wb._volume_pan_y) * 100))}%",
            "volume_yaw_pitch": f"yaw={float(wb._volume_yaw):.1f}, pitch={float(wb._volume_pitch):.1f}",
            "volume_gpu_warning": wb._volume_renderer_warning,
            "volume_status_overlay": volume_status,
            "volume_performance_diagnosis": str(volume_perf.get("diagnosis", "")),
            "volume_uploaded_gb": f"{float(volume_perf.get('uploaded_gb', 0.0)):.2f}",
            "volume_upload_ms": f"{float(volume_perf.get('upload_ms', 0.0)):.0f}",
            "volume_draw_ms": f"{float(volume_perf.get('draw_ms', 0.0)):.1f}",
            "volume_uploaded_shape_zyx": _triplet_text(volume_perf.get("preview_shape_zyx", ())),
            "volume_texture_sampling": str((getattr(wb, "_volume_last_stats", {}) or {}).get("texture_filter", "")),
            "volume_display_scaling": str((getattr(wb, "_volume_last_stats", {}) or {}).get("display_scaling", "")),
            "tif_next_requirement": "annotation_training_loop: bind a label schema, select label IDs before brush editing, save reviewed editable_ai_result/manual labels, accept manual_truth, mark samples train-ready, then prepare/train/predict through the TIF backend.",
            "tif_requirement_doc": "docs/designs/2026-07-04_TIF训练回环与切片预览模式隔离设计稿.md; docs/designs/2026-07-04_TIF脑分区训练回环执行清单.md",
            "recent_log_excerpt": recent_log,
        }
