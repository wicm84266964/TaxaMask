from datetime import datetime

from .tif_local_axis_reslice import compute_local_frame, export_part_reslice
from .tif_project import TifProjectManager


LOCAL_AXIS_QUEUE_STATUSES = {
    "all",
    "no_part",
    "part_ready",
    "no_proposal",
    "proposed",
    "needs_review",
    "accepted",
    "exported",
    "rejected",
    "failed",
    "hard_cases",
}


def _now_stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def _require_project(project_manager):
    if not isinstance(project_manager, TifProjectManager):
        raise TypeError("project_manager_must_be_tif_project_manager")


def create_local_axis_run(project_manager, run_type, specimen_ids, template_id="", model_id=None, extra=None):
    _require_project(project_manager)
    payload = {
        "action": str(run_type or ""),
        "template_id": str(template_id or ""),
        "model_id": str(model_id or ""),
        "specimen_ids": [str(item) for item in specimen_ids or []],
    }
    if isinstance(extra, dict):
        payload.update(extra)
    return project_manager.add_local_axis_run(payload)


def list_local_axis_queue(project_manager, filters=None):
    _require_project(project_manager)
    filters = filters if isinstance(filters, dict) else {}
    status_filter = str(filters.get("status") or "all").strip() or "all"
    template_filter = filters.get("template_id")
    model_version_filter = str(filters.get("model_version") or "").strip()
    hard_case_flag_filter = str(filters.get("hard_case_flag") or "").strip()
    sort_key = str(filters.get("sort") or "status_specimen").strip()
    include_reslices = bool(filters.get("include_reslices", True))
    rows = []
    for specimen in project_manager.project_data.get("specimens", []) or []:
        specimen_id = specimen.get("specimen_id", "")
        parts = list(specimen.get("parts", []) or [])
        if not parts and status_filter in {"all", "no_part"}:
            row = {
                "specimen_id": specimen_id,
                "part_id": "",
                "template_id": template_filter or "",
                "kind": "specimen",
                "proposal_id": "",
                "status": "no_part",
                "confidence": 0.0,
                "hard_case_flags": [],
                "model_id": "",
                "model_version": "",
            }
            if _queue_row_matches(row, status_filter, model_version_filter, hard_case_flag_filter):
                rows.append(row)
        for part in parts:
            part_id = part.get("part_id", "")
            metadata = part.get("metadata") or {}
            proposals = list(metadata.get("local_axis_frame_proposals", []) or [])
            reslices = list(metadata.get("local_axis_reslices", []) or [])
            failures = list(metadata.get("local_axis_batch_failures", []) or [])
            if template_filter:
                proposals = [item for item in proposals if item.get("template_id") == template_filter]
                reslices = [item for item in reslices if item.get("template_id") == template_filter]
                failures = [item for item in failures if item.get("template_id") == template_filter]
            if proposals:
                for proposal in proposals:
                    status = proposal.get("status") or "proposed"
                    hard_flags = proposal.get("hard_case_flags") or []
                    row = {
                        "specimen_id": specimen_id,
                        "part_id": part_id,
                        "template_id": proposal.get("template_id", ""),
                        "kind": "local_frame_proposal",
                        "proposal_id": proposal.get("frame_proposal_id", ""),
                        "status": status,
                        "confidence": proposal.get("confidence", 0.0),
                        "hard_case_flags": hard_flags,
                        "model_id": proposal.get("model_id", ""),
                        "model_version": proposal.get("model_version", ""),
                    }
                    if _queue_row_matches(row, status_filter, model_version_filter, hard_case_flag_filter):
                        rows.append(row)
            elif status_filter in {"all", "part_ready", "no_proposal"}:
                row = {
                    "specimen_id": specimen_id,
                    "part_id": part_id,
                    "template_id": template_filter or "",
                    "kind": "part",
                    "proposal_id": "",
                    "status": "part_ready",
                    "confidence": 0.0,
                    "hard_case_flags": [],
                    "model_id": "",
                    "model_version": "",
                }
                if _queue_row_matches(row, status_filter, model_version_filter, hard_case_flag_filter):
                    rows.append(row)
                if status_filter == "no_proposal":
                    legacy_row = dict(row)
                    legacy_row["status"] = "no_proposal"
                    if _queue_row_matches(legacy_row, status_filter, model_version_filter, hard_case_flag_filter):
                        rows.append(legacy_row)
            if include_reslices and status_filter in {"all", "exported"}:
                for reslice in reslices:
                    row = {
                        "specimen_id": specimen_id,
                        "part_id": part_id,
                        "template_id": reslice.get("template_id", ""),
                        "kind": "reslice",
                        "proposal_id": "",
                        "reslice_id": reslice.get("reslice_id", ""),
                        "status": "exported",
                        "confidence": 1.0,
                        "hard_case_flags": [],
                        "model_id": "",
                        "model_version": "",
                    }
                    if _queue_row_matches(row, status_filter, model_version_filter, hard_case_flag_filter):
                        rows.append(row)
            if status_filter in {"all", "failed"}:
                for failure in failures:
                    row = {
                        "specimen_id": specimen_id,
                        "part_id": part_id,
                        "template_id": failure.get("template_id", ""),
                        "kind": "batch_failure",
                        "proposal_id": failure.get("proposal_id", ""),
                        "failure_id": failure.get("failure_id", ""),
                        "status": "failed",
                        "confidence": 0.0,
                        "hard_case_flags": [],
                        "model_id": failure.get("model_id", ""),
                        "model_version": failure.get("model_version", ""),
                        "failure_reason": failure.get("reason", ""),
                        "failure_detail": failure.get("detail", ""),
                    }
                    if _queue_row_matches(row, status_filter, model_version_filter, hard_case_flag_filter):
                        rows.append(row)
    rows.sort(key=_queue_sort_key(sort_key))
    return rows


def _queue_row_matches(row, status_filter, model_version_filter="", hard_case_flag_filter=""):
    if model_version_filter and str(row.get("model_version") or "") != model_version_filter:
        return False
    if hard_case_flag_filter:
        flags = {str(item) for item in row.get("hard_case_flags", []) or []}
        if hard_case_flag_filter not in flags:
            return False
    if status_filter == "all":
        return True
    if status_filter == "hard_cases":
        return bool(row.get("hard_case_flags"))
    return row.get("status") == status_filter


def _queue_sort_key(sort_key):
    if sort_key == "confidence_asc":
        return lambda item: (
            float(item.get("confidence", 0.0) or 0.0),
            str(item.get("status", "")),
            str(item.get("specimen_id", "")),
            str(item.get("part_id", "")),
        )
    if sort_key == "confidence_desc":
        return lambda item: (
            -float(item.get("confidence", 0.0) or 0.0),
            str(item.get("status", "")),
            str(item.get("specimen_id", "")),
            str(item.get("part_id", "")),
        )
    if sort_key == "model_version":
        return lambda item: (
            str(item.get("model_version", "")),
            str(item.get("model_id", "")),
            str(item.get("status", "")),
            str(item.get("specimen_id", "")),
        )
    return lambda item: (
        str(item.get("status", "")),
        str(item.get("specimen_id", "")),
        str(item.get("part_id", "")),
        str(item.get("proposal_id", "")),
    )


def update_proposal_status(project_manager, proposal_id, status, reviewer_notes="", specimen_id=None, part_id=None):
    _require_project(project_manager)
    clean_status = str(status or "").strip()
    if clean_status not in {"proposed", "needs_review", "accepted", "rejected", "exported"}:
        raise ValueError(f"invalid_local_axis_proposal_status:{status}")
    for specimen in project_manager.project_data.get("specimens", []) or []:
        if specimen_id and specimen.get("specimen_id") != specimen_id:
            continue
        for part in specimen.get("parts", []) or []:
            if part_id and part.get("part_id") != part_id:
                continue
            for proposal in (part.get("metadata") or {}).get("local_axis_frame_proposals", []) or []:
                if proposal.get("frame_proposal_id") == proposal_id:
                    return project_manager.update_local_frame_proposal(
                        specimen.get("specimen_id"),
                        part.get("part_id"),
                        proposal_id,
                        {"status": clean_status, "reviewer_notes": reviewer_notes},
                    )
    raise KeyError(f"unknown_local_frame_proposal_id:{proposal_id}")


def accept_local_frame_proposal(project_manager, specimen_id, part_id, proposal_id, reviewer_notes=""):
    return project_manager.update_local_frame_proposal(
        specimen_id,
        part_id,
        proposal_id,
        {"status": "accepted", "reviewer_notes": reviewer_notes},
    )


def _spacing_values(spacing_zyx):
    if spacing_zyx is None:
        return None
    try:
        values = [float(value) for value in spacing_zyx]
    except (TypeError, ValueError):
        return None
    if len(values) != 3 or any(value <= 0 for value in values):
        return None
    return values


def _spacing_matches(left, right):
    left_values = _spacing_values(left)
    right_values = _spacing_values(right)
    if left_values is None or right_values is None:
        return False
    return all(abs(left_values[index] - right_values[index]) <= 1e-9 for index in range(3))


def proposal_to_reslice_payload(frame_proposal, reslice_id=None, display_name=None, reslice_params=None, training=None, spacing_zyx=None):
    proposal = frame_proposal if isinstance(frame_proposal, dict) else {}
    if proposal.get("status") != "accepted":
        raise ValueError(f"local_frame_proposal_not_accepted:{proposal.get('frame_proposal_id')}")
    local_frame = proposal.get("local_frame") if isinstance(proposal.get("local_frame"), dict) else {}
    spacing = _spacing_values(spacing_zyx)
    frame_complete = bool(local_frame.get("origin_zyx") and local_frame.get("x_axis") and local_frame.get("y_axis") and local_frame.get("z_axis"))
    if not frame_complete or (spacing is not None and not _spacing_matches(local_frame.get("spacing_zyx"), spacing)):
        local_frame = compute_local_frame(
            proposal.get("origin_zyx"),
            proposal.get("output_axis_start_zyx"),
            proposal.get("output_axis_end_zyx"),
            proposal.get("roll_reference"),
            spacing_zyx=spacing,
        )
    training_payload = {"human_confirmed": True, "usable_for_training": True, "source": "AI proposed + human reviewed"}
    if isinstance(training, dict):
        training_payload.update(training)
    source_axis = proposal.get("source_axis") if isinstance(proposal.get("source_axis"), dict) else {}
    editable_axis = {}
    if source_axis:
        editable_axis = {
            "axis_id": "local_output_z_axis",
            "role": "editable_output_axis",
            "locked": False,
            "coordinate_space": source_axis.get("coordinate_space", "part_volume_voxel_zyx"),
            "start_zyx": list(proposal.get("output_axis_start_zyx") or []),
            "end_zyx": list(proposal.get("output_axis_end_zyx") or []),
            "source_axis_id": source_axis.get("axis_id", "source_z_axis"),
            "source": "local_frame_proposal",
            "source_proposal_id": proposal.get("frame_proposal_id", ""),
        }
    return {
        "reslice_id": reslice_id or f"{proposal.get('frame_proposal_id')}_reslice",
        "display_name": display_name or proposal.get("frame_proposal_id") or "local_axis_reslice",
        "template_id": proposal.get("template_id", ""),
        "source_axis": source_axis,
        "initial_editable_axis": editable_axis,
        "editable_axis": editable_axis,
        "final_editable_axis": editable_axis,
        "local_frame": local_frame,
        "roll_reference": proposal.get("roll_reference") or local_frame.get("roll_reference") or {},
        "reslice_params": dict(reslice_params or {}),
        "training": training_payload,
        "provenance": {
            "source_proposal_id": proposal.get("frame_proposal_id", ""),
            "source_model_id": proposal.get("model_id", ""),
            "source_model_version": proposal.get("model_version", ""),
        },
    }


def _record_batch_failure(project_manager, specimen_id, part_id, proposal, exc):
    part = project_manager.get_part(specimen_id, part_id, default=None)
    if part is None:
        return None
    proposal_id = str((proposal or {}).get("frame_proposal_id") or "")
    failure = {
        "failure_id": f"failed_{proposal_id or 'proposal'}_{_now_stamp()}",
        "proposal_id": proposal_id,
        "template_id": str((proposal or {}).get("template_id") or ""),
        "reason": type(exc).__name__,
        "detail": str(exc),
        "model_id": str((proposal or {}).get("model_id") or ""),
        "model_version": str((proposal or {}).get("model_version") or ""),
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    part.setdefault("metadata", {}).setdefault("local_axis_batch_failures", []).append(failure)
    return failure


def batch_export_accepted_reslices(project_manager, proposal_ids=None, reslice_params=None):
    _require_project(project_manager)
    wanted = set(str(item) for item in proposal_ids or []) if proposal_ids else None
    exported = []
    skipped = []
    touched_specimens = set()
    touched_parts = set()
    for specimen in project_manager.project_data.get("specimens", []) or []:
        specimen_id = specimen.get("specimen_id", "")
        for part in specimen.get("parts", []) or []:
            part_id = part.get("part_id", "")
            for proposal in (part.get("metadata") or {}).get("local_axis_frame_proposals", []) or []:
                proposal_id = proposal.get("frame_proposal_id", "")
                if wanted is not None and proposal_id not in wanted:
                    continue
                if proposal.get("status") != "accepted":
                    skipped.append({"proposal_id": proposal_id, "reason": "not_accepted", "status": proposal.get("status")})
                    continue
                try:
                    spacing = ((part.get("image") or {}).get("spacing_zyx") or [1.0, 1.0, 1.0])
                    payload = proposal_to_reslice_payload(proposal, reslice_params=reslice_params, spacing_zyx=spacing)
                    result = export_part_reslice(project_manager, specimen_id, part_id, payload)
                    exported.append(result["record"])
                    touched_specimens.add(specimen_id)
                    touched_parts.add(part_id)
                    project_manager.update_local_frame_proposal(specimen_id, part_id, proposal_id, {"status": "exported"}, save=False)
                except Exception as exc:
                    failure = _record_batch_failure(project_manager, specimen_id, part_id, proposal, exc)
                    skipped.append({"proposal_id": proposal_id, "reason": type(exc).__name__, "detail": str(exc), "failure": failure or {}})
    run = project_manager.add_local_axis_run(
        {
            "run_id": f"batch_reslice_export_{_now_stamp()}",
            "action": "batch_reslice_export",
            "specimen_ids": sorted(touched_specimens),
            "part_ids": sorted(touched_parts),
            "result_status": "success" if exported and not skipped else ("partial_success" if exported else "skipped"),
            "metrics": {"exported_count": len(exported), "skipped_count": len(skipped)},
            "warnings": [item.get("detail", item.get("reason", "")) for item in skipped],
        },
        save=False,
    )
    project_manager.save_project()
    return {"exported": exported, "skipped": skipped, "run": run}
