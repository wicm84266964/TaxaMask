import os

from AntSleap.core.tif_local_axis_reslice import (
    compute_local_frame,
    create_editable_axis_from_source,
    local_axis_output_shape_for_source_bbox,
    source_z_axis_for_part,
)

from .tif_service_result import service_blocked, service_ok


class TifLocalAxisService:
    def source_z_axis_for_shape(self, source_shape_zyx):
        try:
            return service_ok("local_axis_source_z_ready", source_axis=source_z_axis_for_part(source_shape_zyx))
        except Exception as exc:
            return service_blocked(str(exc), reasons=[str(exc)])

    def build_initial_draft(
        self,
        *,
        specimen_id,
        part_id,
        source_shape_zyx,
        template_id="",
        source_axis=None,
        source_proposal_id="",
        source_model_id="",
        source_model_version="",
    ):
        try:
            source = dict(source_axis or source_z_axis_for_part(source_shape_zyx))
            editable = create_editable_axis_from_source(source)
            start = editable.get("start_zyx") or []
            end = editable.get("end_zyx") or []
            origin = []
            if len(start) == 3 and len(end) == 3:
                origin = [round((float(start[index]) + float(end[index])) * 0.5, 3) for index in range(3)]
            roll_reference = {}
            if str(part_id or "").lower() == "head":
                roll_reference["pair_id"] = "roll_reference_point_pair"
            if source_proposal_id:
                editable["source_proposal_id"] = str(source_proposal_id)
            draft = {
                "specimen_id": str(specimen_id or ""),
                "part_id": str(part_id or ""),
                "template_id": str(template_id or part_id or "generic"),
                "source_axis": source,
                "initial_editable_axis": dict(editable),
                "editable_axis": editable,
                "origin_zyx": origin,
                "roll_reference": roll_reference,
                "local_frame": None,
                "dirty": True,
            }
            if source_proposal_id:
                draft["source_proposal_id"] = str(source_proposal_id)
            if source_model_id:
                draft["source_model_id"] = str(source_model_id)
            if source_model_version:
                draft["source_model_version"] = str(source_model_version)
        except Exception as exc:
            return service_blocked(str(exc), reasons=[str(exc)])
        return service_ok("local_axis_draft_ready", draft=draft)

    def clear_roll_reference_points(self, draft):
        if not isinstance(draft, dict):
            return service_blocked("local_axis_draft_required", reasons=["local_axis_draft_required"])
        clean = dict(draft)
        roll = dict(clean.get("roll_reference") or {})
        for key in ("point_a", "point_b", "point_c", "reference_plane"):
            roll.pop(key, None)
        clean["roll_reference"] = roll
        clean["local_frame"] = None
        clean["dirty"] = True
        return service_ok("local_axis_roll_references_cleared", draft=clean)

    def roll_reference_payload(self, draft):
        roll = (draft or {}).get("roll_reference") if isinstance((draft or {}).get("roll_reference"), dict) else {}
        point_a = roll.get("point_a") if isinstance(roll.get("point_a"), dict) else {}
        point_b = roll.get("point_b") if isinstance(roll.get("point_b"), dict) else {}
        if not point_a.get("zyx") or not point_b.get("zyx"):
            return None
        return dict(roll)

    def build_local_frame(self, draft, *, spacing_zyx=None):
        if not isinstance(draft, dict):
            return service_blocked("local_axis_draft_required", reasons=["local_axis_draft_required"])
        editable = draft.get("editable_axis") or {}
        roll = self.roll_reference_payload(draft)
        if not roll:
            return service_blocked("roll_reference_required", reasons=["roll_reference_required"])
        try:
            frame = compute_local_frame(
                draft.get("origin_zyx"),
                editable.get("start_zyx"),
                editable.get("end_zyx"),
                roll_reference=roll,
                spacing_zyx=spacing_zyx or [1.0, 1.0, 1.0],
            )
        except Exception as exc:
            return service_blocked(str(exc), reasons=[str(exc)])
        return service_ok("local_axis_frame_ready", frame=frame)

    def build_reslice_payload(
        self,
        *,
        specimen_id,
        part_id,
        draft,
        local_frame,
        source_shape_zyx,
        spacing_zyx,
        reslice_id,
        trainable=True,
        display_name="",
    ):
        if not specimen_id or not part_id:
            return service_blocked("part_context_required", reasons=["part_context_required"])
        if not isinstance(draft, dict):
            return service_blocked("local_axis_draft_required", reasons=["local_axis_draft_required"])
        if not isinstance(local_frame, dict):
            return service_blocked("local_axis_frame_required", reasons=["local_axis_frame_required"])
        try:
            source_shape = [int(value) for value in source_shape_zyx]
            spacing = [float(value) for value in (spacing_zyx or [1.0, 1.0, 1.0])]
            output_shape = local_axis_output_shape_for_source_bbox(source_shape, local_frame, output_spacing_zyx=spacing)
        except Exception as exc:
            return service_blocked(str(exc), reasons=[str(exc)])
        source_proposal_id = str(draft.get("source_proposal_id") or ((draft.get("editable_axis") or {}).get("source_proposal_id") or ""))
        training_source = "AI proposed + human confirmed" if source_proposal_id else "manual_confirmed"
        roll_reference = dict(local_frame.get("roll_reference") or draft.get("roll_reference") or {})
        reference_plane = dict(
            draft.get("reference_plane")
            or (roll_reference.get("reference_plane") if isinstance(roll_reference, dict) else {})
            or {}
        )
        payload = {
            "reslice_id": str(reslice_id or ""),
            "display_name": str(display_name or f"{part_id} local axis"),
            "template_id": str(draft.get("template_id") or part_id or ""),
            "source_axis": dict(draft.get("source_axis") or {}),
            "initial_editable_axis": dict(draft.get("initial_editable_axis") or draft.get("editable_axis") or {}),
            "editable_axis": dict(draft.get("editable_axis") or {}),
            "final_editable_axis": dict(draft.get("editable_axis") or {}),
            "local_frame": dict(local_frame),
            "roll_reference": roll_reference,
            "reference_plane": reference_plane,
            "reslice_params": {
                "output_shape_zyx": output_shape,
                "output_spacing_zyx": spacing,
                "image_interpolation": "linear",
                "coverage": "full_source_part_bbox",
            },
            "export_mask": True,
            "training": {
                "human_confirmed": True,
                "usable_for_training": bool(trainable),
                "source": training_source,
                "reviewer_notes": "Confirmed in TIF Local Axis 3D part preview.",
            },
            "provenance": {
                "workflow": "tif_local_axis_right_sidebar",
                "source_proposal_id": source_proposal_id,
                "source_model_id": str(draft.get("source_model_id") or ""),
                "source_model_version": str(draft.get("source_model_version") or ""),
                "source_interaction": "3d_part_preview_clip_plane",
                "reference_plane_source": "manual_three_point_plane" if reference_plane else "",
                "reslice_coverage": "full_source_part_bbox",
            },
        }
        return service_ok("local_axis_reslice_payload_ready", payload=payload)

    def build_manifest_export_request(self, project_manager, output_dir, *, template_id=""):
        if not output_dir:
            return service_blocked("output_dir_required", reasons=["output_dir_required"])
        abs_output = os.path.abspath(str(output_dir))
        filters = {}
        if template_id:
            filters["template_id"] = str(template_id)
        return service_ok("local_axis_manifest_export_request_ready", output_dir=abs_output, filters=filters)
