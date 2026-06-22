from datetime import datetime

import numpy as np

from .tif_local_axis_reslice import compute_local_frame, source_z_axis_for_part
from .tif_project import TifProjectManager
from .tif_volume_io import load_volume_sidecar, volume_sidecar_exists


def _now_stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def _safe_id(value, fallback="baseline"):
    text = str(value or "").strip()
    clean = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in text)
    clean = clean.strip("_")
    return clean or str(fallback or "baseline")


def _spacing_zyx(part):
    spacing = ((part.get("image") or {}).get("spacing_zyx") or [1.0, 1.0, 1.0])
    try:
        values = [float(value) for value in spacing]
    except (TypeError, ValueError):
        values = [1.0, 1.0, 1.0]
    if len(values) != 3 or any(value <= 0 for value in values):
        return [1.0, 1.0, 1.0]
    return values


def _part_shape_zyx(part):
    shape = ((part.get("image") or {}).get("shape_zyx") or [1, 1, 1])
    try:
        values = [max(1, int(value)) for value in shape]
    except (TypeError, ValueError):
        values = [1, 1, 1]
    return values if len(values) == 3 else [1, 1, 1]


def _source_axis_points(shape_zyx):
    axis = source_z_axis_for_part(shape_zyx)
    start = np.asarray(axis.get("start_zyx"), dtype=np.float64)
    end = np.asarray(axis.get("end_zyx"), dtype=np.float64)
    if float(np.linalg.norm(end - start)) <= 1e-8:
        center = (np.asarray(shape_zyx, dtype=np.float64) - 1.0) / 2.0
        start = center - np.array([0.5, 0.0, 0.0], dtype=np.float64)
        end = center + np.array([0.5, 0.0, 0.0], dtype=np.float64)
    return start, end


def _mask_coords(project_manager, part):
    mask_record = part.get("mask") or {}
    mask_path = project_manager.to_absolute(mask_record.get("path", ""))
    if not mask_record.get("path") or not volume_sidecar_exists(mask_path):
        return None, "missing_part_mask"
    mask = np.asarray(load_volume_sidecar(mask_path))
    coords = np.argwhere(mask > 0)
    if coords.shape[0] < 2:
        return None, "empty_part_mask"
    return coords.astype(np.float64), ""


def _pca_axis_from_coords(coords_zyx, spacing_zyx):
    spacing = np.asarray(spacing_zyx, dtype=np.float64)
    coords_world = coords_zyx * spacing
    center = coords_zyx.mean(axis=0)
    centered = coords_world - coords_world.mean(axis=0)
    try:
        _, _, vh = np.linalg.svd(centered, full_matrices=False)
    except np.linalg.LinAlgError:
        return None
    if vh.shape[0] == 0:
        return None
    direction_world = vh[0]
    direction_voxel = direction_world / spacing
    norm = float(np.linalg.norm(direction_voxel))
    if norm <= 1e-8:
        return None
    direction_voxel = direction_voxel / norm
    projections = np.dot(coords_zyx - center, direction_voxel)
    low = float(np.min(projections))
    high = float(np.max(projections))
    if abs(high - low) <= 1e-6:
        return None
    return center, center + low * direction_voxel, center + high * direction_voxel


def build_baseline_local_frame_proposal(project_manager, specimen_id, part_id, template_id="", proposal_id=""):
    if not isinstance(project_manager, TifProjectManager):
        raise TypeError("project_manager_must_be_tif_project_manager")
    part = project_manager.get_part(specimen_id, part_id, default=None)
    if part is None:
        raise KeyError(f"unknown_part_id:{specimen_id}:{part_id}")
    shape = _part_shape_zyx(part)
    spacing = _spacing_zyx(part)
    center = (np.asarray(shape, dtype=np.float64) - 1.0) / 2.0
    source_start, source_end = _source_axis_points(shape)
    coords, mask_warning = _mask_coords(project_manager, part)
    axis_source = "source_z_fallback"
    confidence = 0.05
    hard_flags = []
    if mask_warning:
        hard_flags.append(mask_warning)
    if coords is not None:
        pca = _pca_axis_from_coords(coords, spacing)
        if pca is not None:
            center, source_start, source_end = pca
            axis_source = "part_mask_pca"
            confidence = 0.25
            hard_flags.append("baseline_pca_initial_axis")
    else:
        hard_flags.append("source_z_fallback")
    roll_reference = {}
    local_frame = compute_local_frame(
        center.tolist(),
        np.asarray(source_start, dtype=np.float64).tolist(),
        np.asarray(source_end, dtype=np.float64).tolist(),
        roll_reference=roll_reference,
        spacing_zyx=spacing,
    )
    clean_id = _safe_id(proposal_id or f"baseline_{part_id}_{_now_stamp()}", "baseline_frame")
    return {
        "frame_proposal_id": clean_id,
        "specimen_id": str(specimen_id or ""),
        "part_id": str(part_id or ""),
        "template_id": str(template_id or part_id or ""),
        "coordinate_space": "part_volume_voxel_zyx",
        "origin_zyx": center.tolist(),
        "output_axis_start_zyx": np.asarray(source_start, dtype=np.float64).tolist(),
        "output_axis_end_zyx": np.asarray(source_end, dtype=np.float64).tolist(),
        "roll_reference": roll_reference,
        "local_frame": local_frame,
        "confidence": confidence,
        "model_id": "taxamask_baseline_local_axis",
        "model_version": "baseline_v1",
        "status": "needs_review",
        "hard_case_flags": sorted(set(hard_flags)),
        "missing_landmarks": ["roll_reference"],
        "reviewer_notes": "Baseline proposal only. Human review is required before export.",
        "provenance": {
            "source": "taxamask_baseline",
            "axis_source": axis_source,
            "uses_body_signal": False,
            "creates_final_reslice": False,
        },
    }


def add_baseline_local_frame_proposal(project_manager, specimen_id, part_id, template_id="", proposal_id="", save=True):
    proposal = build_baseline_local_frame_proposal(project_manager, specimen_id, part_id, template_id, proposal_id)
    return project_manager.add_local_frame_proposal(specimen_id, part_id, proposal, save=save)


def add_baseline_local_frame_proposals(project_manager, specimen_ids=None, part_ids_by_specimen=None, template_id="", save=True):
    if not isinstance(project_manager, TifProjectManager):
        raise TypeError("project_manager_must_be_tif_project_manager")
    wanted_specimens = {str(item) for item in specimen_ids or []}
    part_map = part_ids_by_specimen or {}
    proposals = []
    skipped = []
    for specimen in project_manager.project_data.get("specimens", []) or []:
        specimen_id = specimen.get("specimen_id", "")
        if wanted_specimens and specimen_id not in wanted_specimens:
            continue
        wanted_parts = set(str(item) for item in part_map.get(specimen_id, []) or []) if specimen_id in part_map else None
        for part in specimen.get("parts", []) or []:
            part_id = part.get("part_id", "")
            if wanted_parts is not None and part_id not in wanted_parts:
                continue
            try:
                proposals.append(add_baseline_local_frame_proposal(project_manager, specimen_id, part_id, template_id or part_id, save=False))
            except Exception as exc:
                skipped.append({"specimen_id": specimen_id, "part_id": part_id, "reason": type(exc).__name__, "detail": str(exc)})
    run = project_manager.add_local_axis_run(
        {
            "run_id": f"baseline_local_frame_{_now_stamp()}",
            "action": "baseline_local_frame_proposal",
            "backend_id": "taxamask_baseline_local_axis",
            "model_id": "taxamask_baseline_local_axis",
            "template_id": str(template_id or ""),
            "specimen_ids": sorted({item.get("specimen_id", "") for item in proposals}),
            "part_ids": sorted({item.get("part_id", "") for item in proposals}),
            "result_status": "success" if proposals and not skipped else ("partial_success" if proposals else "skipped"),
            "metrics": {"proposal_count": len(proposals), "skipped_count": len(skipped)},
            "warnings": [item.get("detail", item.get("reason", "")) for item in skipped],
        },
        save=False,
    )
    if save:
        project_manager.save_project()
    return {"proposals": proposals, "skipped": skipped, "run": run}
