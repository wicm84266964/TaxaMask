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
LOCAL_AXIS_RISK_RANKING_VERSION = "taxamask_local_axis_risk_v2"


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
    sort_key = str(filters.get("sort") or "risk_priority").strip()
    include_reslices = bool(filters.get("include_reslices", True))
    rows = []
    active_model = _active_local_axis_model_reference(project_manager)
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
                        "missing_landmarks": list(proposal.get("missing_landmarks", []) or []),
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
    for original_index, row in enumerate(rows):
        score, tier, reasons, components = _queue_risk(
            row,
            active_model=active_model,
        )
        row["risk_score"] = score
        row["risk_tier"] = tier
        row["risk_reasons"] = reasons
        row["risk_components"] = components
        row["risk_ranking_version"] = LOCAL_AXIS_RISK_RANKING_VERSION
        row["risk_score_interpretation"] = "review_priority_not_error_probability"
        row["risk_reference_model_id"] = active_model.get("model_id", "")
        row["risk_reference_model_version"] = active_model.get(
            "model_version",
            "",
        )
        row["original_order"] = original_index
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
    if sort_key == "risk_priority":
        return lambda item: (
            -float(item.get("risk_score", 0.0) or 0.0),
            float(item.get("confidence", 0.0) or 0.0),
            str(item.get("specimen_id", "")),
            str(item.get("part_id", "")),
        )
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


def _active_local_axis_model_reference(project_manager):
    settings = project_manager.project_data.get("view_settings") or {}
    model_id = str(settings.get("local_axis_active_model_id") or "")
    model = (
        project_manager.get_local_axis_model(model_id, default=None)
        if model_id
        else None
    )
    return {
        "model_id": model_id if isinstance(model, dict) else "",
        "model_version": str((model or {}).get("model_version") or ""),
    }


def _queue_risk(row, active_model=None):
    status = str(row.get("status") or "")
    components = {
        "status_weight": 0.0,
        "hard_case_weight": 0.0,
        "missing_landmark_weight": 0.0,
        "confidence_uncertainty_weight": 0.0,
        "model_version_mismatch_weight": 0.0,
    }
    if row.get("kind") == "batch_failure" or status == "failed":
        components["status_weight"] = 100.0
        return 100.0, "high", ["backend_failure"], components
    if row.get("kind") != "local_frame_proposal" or status not in {
        "proposed",
        "needs_review",
    }:
        return 0.0, "reviewed", [], components
    components["status_weight"] = 25.0 if status == "needs_review" else 10.0
    reasons = [f"status:{status}"]
    hard_flags = [str(value) for value in row.get("hard_case_flags", []) or [] if str(value)]
    if hard_flags:
        components["hard_case_weight"] = 45.0
        reasons.extend(f"hard_case:{value}" for value in hard_flags)
    missing = [str(value) for value in row.get("missing_landmarks", []) or [] if str(value)]
    if missing:
        components["missing_landmark_weight"] = 35.0
        reasons.extend(f"missing_landmark:{value}" for value in missing)
    try:
        confidence = min(1.0, max(0.0, float(row.get("confidence", 0.0) or 0.0)))
    except (TypeError, ValueError):
        confidence = 0.0
    components["confidence_uncertainty_weight"] = round(
        (1.0 - confidence) * 30.0,
        3,
    )
    if confidence < 0.5:
        reasons.append("low_confidence")
    active = active_model if isinstance(active_model, dict) else {}
    expected_version = str(active.get("model_version") or "")
    proposal_version = str(row.get("model_version") or "")
    if expected_version and proposal_version != expected_version:
        components["model_version_mismatch_weight"] = 20.0
        reasons.append(
            f"model_version_mismatch:{proposal_version or 'missing'}!={expected_version}"
        )
    score = sum(float(value) for value in components.values())
    score = round(min(100.0, score), 3)
    tier = "high" if score >= 55.0 else "medium" if score >= 25.0 else "low"
    return score, tier, reasons, components


def compare_local_axis_review_orders(
    rows,
    known_error_proposal_ids,
    *,
    review_seconds_by_proposal_id=None,
    review_budget=100,
):
    proposals = [
        dict(row)
        for row in rows or []
        if row.get("kind") == "local_frame_proposal" and row.get("proposal_id")
    ]
    known_errors = {str(value) for value in known_error_proposal_ids or []}
    seconds = dict(review_seconds_by_proposal_id or {})
    budget = max(0, min(int(review_budget), len(proposals)))
    results = {}
    for mode in ("risk_priority", "status_specimen", "confidence_asc"):
        ordered = sorted(proposals, key=_queue_sort_key(mode))
        reviewed = ordered[:budget]
        error_count = sum(
            str(row.get("proposal_id")) in known_errors for row in reviewed
        )
        elapsed = sum(
            max(0.0, float(seconds.get(str(row.get("proposal_id")), 1.0)))
            for row in reviewed
        )
        results[mode] = {
            "reviewed_count": len(reviewed),
            "known_error_count": int(error_count),
            "errors_per_100_reviewed": round(
                (100.0 * error_count / len(reviewed)) if reviewed else 0.0,
                3,
            ),
            "elapsed_seconds": round(elapsed, 3),
            "sample_coverage": round(
                (len(reviewed) / len(proposals)) if proposals else 0.0,
                6,
            ),
            "proposal_order": [str(row.get("proposal_id")) for row in reviewed],
        }
    return {
        "schema_version": "taxamask_local_axis_review_order_comparison_v1",
        "risk_ranking_version": LOCAL_AXIS_RISK_RANKING_VERSION,
        "sample_count": len(proposals),
        "known_error_count": sum(
            str(row.get("proposal_id")) in known_errors for row in proposals
        ),
        "review_budget": budget,
        "results": results,
        "risk_vs_original_error_gain": (
            results["risk_priority"]["known_error_count"]
            - results["status_specimen"]["known_error_count"]
        ),
    }


def update_proposal_status(
    project_manager,
    proposal_id,
    status,
    reviewer_notes="",
    specimen_id=None,
    part_id=None,
    review_action="local_axis_review_queue_status_update",
):
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
                    reviewed_at = datetime.now().astimezone().isoformat(
                        timespec="seconds"
                    )
                    audit = {
                        "action": str(review_action or ""),
                        "explicit_review": True,
                        "proposal_id": str(proposal_id or ""),
                        "specimen_id": str(specimen.get("specimen_id") or ""),
                        "part_id": str(part.get("part_id") or ""),
                        "previous_status": str(proposal.get("status") or ""),
                        "new_status": clean_status,
                        "reviewed_at": reviewed_at,
                        "model_id": str(proposal.get("model_id") or ""),
                        "model_version": str(proposal.get("model_version") or ""),
                        "reviewer_notes": str(reviewer_notes or ""),
                    }
                    history = [
                        dict(item)
                        for item in proposal.get("review_history", []) or []
                        if isinstance(item, dict)
                    ]
                    history.append(audit)
                    provenance = dict(proposal.get("provenance") or {})
                    provenance["review_audit"] = dict(audit)
                    provenance["review_history"] = [
                        dict(item) for item in history
                    ]
                    return project_manager.update_local_frame_proposal(
                        specimen.get("specimen_id"),
                        part.get("part_id"),
                        proposal_id,
                        {
                            "status": clean_status,
                            "reviewer_notes": reviewer_notes,
                            "review_audit": audit,
                            "review_history": history,
                            "provenance": provenance,
                        },
                    )
    raise KeyError(f"unknown_local_frame_proposal_id:{proposal_id}")


def accept_local_frame_proposal(project_manager, specimen_id, part_id, proposal_id, reviewer_notes=""):
    return update_proposal_status(
        project_manager,
        proposal_id,
        "accepted",
        reviewer_notes=reviewer_notes,
        specimen_id=specimen_id,
        part_id=part_id,
        review_action="accept_local_frame_proposal",
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
