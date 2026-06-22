import json
import os
from datetime import datetime

import numpy as np
import tifffile
from scipy.ndimage import map_coordinates

from .tif_project import TifProjectManager
from .tif_volume_io import load_volume_sidecar, read_volume_metadata, volume_sidecar_exists


LOCAL_AXIS_RESLICE_SCHEMA_VERSION = "taxamask_local_axis_reslice_v1"


def _now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _safe_id(value, fallback="reslice"):
    text = str(value or "").strip()
    clean = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in text)
    clean = clean.strip("_")
    return clean or str(fallback or "reslice")


def _write_json(path, payload):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return payload


def _normalize_spacing(spacing_zyx):
    if spacing_zyx is None:
        return np.array([1.0, 1.0, 1.0], dtype=np.float64)
    if len(spacing_zyx) != 3:
        raise ValueError("spacing_zyx_must_have_3_values")
    spacing = np.array([float(value) for value in spacing_zyx], dtype=np.float64)
    if np.any(spacing <= 0):
        raise ValueError("spacing_zyx_must_be_positive")
    return spacing


def _point(values, field_name):
    if not isinstance(values, (list, tuple, np.ndarray)) or len(values) != 3:
        raise ValueError(f"{field_name}_must_have_3_values")
    point = np.array([float(value) for value in values], dtype=np.float64)
    if not np.all(np.isfinite(point)):
        raise ValueError(f"{field_name}_must_be_finite")
    return point


def _unit(vector, field_name):
    vec = _point(vector, field_name)
    norm = float(np.linalg.norm(vec))
    if norm <= 1e-8:
        raise ValueError(f"{field_name}_must_not_be_zero")
    return vec / norm


def _axis_world_from_points(start_zyx, end_zyx, spacing_zyx, field_name="output_axis"):
    start = _point(start_zyx, f"{field_name}_start")
    end = _point(end_zyx, f"{field_name}_end")
    direction = (end - start) * spacing_zyx
    norm = float(np.linalg.norm(direction))
    if norm <= 1e-8:
        raise ValueError(f"{field_name}_points_must_not_overlap")
    return direction / norm


def _world_unit_from_voxel_axis(axis_voxel, spacing_zyx, field_name):
    axis = _unit(axis_voxel, field_name)
    world = axis * spacing_zyx
    norm = float(np.linalg.norm(world))
    if norm <= 1e-8:
        raise ValueError(f"{field_name}_world_length_must_not_be_zero")
    return world / norm


def _voxel_unit_from_world_axis(axis_world, spacing_zyx, field_name):
    world = _unit(axis_world, field_name)
    voxel = world / spacing_zyx
    norm = float(np.linalg.norm(voxel))
    if norm <= 1e-8:
        raise ValueError(f"{field_name}_voxel_length_must_not_be_zero")
    return voxel / norm


def source_z_axis_for_part(part_shape_zyx):
    shape = _point(part_shape_zyx, "part_shape_zyx")
    center = (shape - 1.0) / 2.0
    start = np.array([0.0, center[1], center[2]], dtype=np.float64)
    end = np.array([max(0.0, shape[0] - 1.0), center[1], center[2]], dtype=np.float64)
    return {
        "axis_id": "source_z_axis",
        "role": "source_direction_reference",
        "locked": True,
        "coordinate_space": "part_volume_voxel_zyx",
        "start_zyx": start.tolist(),
        "end_zyx": end.tolist(),
    }


def create_editable_axis_from_source(source_axis, axis_id="local_output_z_axis"):
    if not isinstance(source_axis, dict):
        raise ValueError("source_axis_must_be_object")
    return {
        "axis_id": str(axis_id or "local_output_z_axis"),
        "role": "editable_output_axis",
        "locked": False,
        "coordinate_space": source_axis.get("coordinate_space", "part_volume_voxel_zyx"),
        "start_zyx": list(source_axis.get("start_zyx") or []),
        "end_zyx": list(source_axis.get("end_zyx") or []),
        "source_axis_id": source_axis.get("axis_id", "source_z_axis"),
    }


def compute_local_frame(origin_zyx, output_axis_start_zyx, output_axis_end_zyx, roll_reference=None, spacing_zyx=None, output_axis="z_axis"):
    spacing = _normalize_spacing(spacing_zyx)
    origin = _point(origin_zyx, "origin_zyx")
    z_world = _axis_world_from_points(output_axis_start_zyx, output_axis_end_zyx, spacing)

    roll_reference = roll_reference if isinstance(roll_reference, dict) else {}
    point_a = ((roll_reference.get("point_a") or {}).get("zyx") if isinstance(roll_reference.get("point_a"), dict) else None)
    point_b = ((roll_reference.get("point_b") or {}).get("zyx") if isinstance(roll_reference.get("point_b"), dict) else None)
    if point_a is not None and point_b is not None:
        roll_vec = _point(point_b, "roll_reference_point_b") - _point(point_a, "roll_reference_point_a")
        roll_vec = roll_vec * spacing
        x_world = roll_vec - float(np.dot(roll_vec, z_world)) * z_world
        if float(np.linalg.norm(x_world)) <= 1e-8:
            x_world = _fallback_perpendicular_world(z_world)
        else:
            x_world = x_world / np.linalg.norm(x_world)
    else:
        x_world = _fallback_perpendicular_world(z_world)

    y_world = np.cross(z_world, x_world)
    y_world = y_world / np.linalg.norm(y_world)
    x_world = np.cross(y_world, z_world)
    x_world = x_world / np.linalg.norm(x_world)
    x_axis = _voxel_unit_from_world_axis(x_world, spacing, "x_axis")
    y_axis = _voxel_unit_from_world_axis(y_world, spacing, "y_axis")
    z_axis = _voxel_unit_from_world_axis(z_world, spacing, "z_axis")

    frame = {
        "origin_zyx": origin.tolist(),
        "x_axis": x_axis.tolist(),
        "y_axis": y_axis.tolist(),
        "z_axis": z_axis.tolist(),
        "output_axis": str(output_axis or "z_axis"),
        "spacing_zyx": spacing.tolist(),
        "roll_reference": dict(roll_reference),
        "coordinate_space": "part_volume_voxel_zyx",
    }
    validate_local_frame(frame)
    return frame


def _fallback_perpendicular_world(z_axis_world):
    z_axis = _unit(z_axis_world, "z_axis")
    candidates = [
        np.array([0.0, 0.0, 1.0], dtype=np.float64),
        np.array([0.0, 1.0, 0.0], dtype=np.float64),
        np.array([1.0, 0.0, 0.0], dtype=np.float64),
    ]
    best = min(candidates, key=lambda item: abs(float(np.dot(item, z_axis))))
    x_axis = best - float(np.dot(best, z_axis)) * z_axis
    return x_axis / np.linalg.norm(x_axis)


def validate_local_frame(local_frame):
    if not isinstance(local_frame, dict):
        raise ValueError("local_frame_must_be_object")
    spacing = _normalize_spacing(local_frame.get("spacing_zyx") or [1.0, 1.0, 1.0])
    origin = _point(local_frame.get("origin_zyx"), "origin_zyx")
    x_axis = _unit(local_frame.get("x_axis"), "x_axis")
    y_axis = _unit(local_frame.get("y_axis"), "y_axis")
    z_axis = _unit(local_frame.get("z_axis"), "z_axis")
    x_world = _world_unit_from_voxel_axis(x_axis, spacing, "x_axis")
    y_world = _world_unit_from_voxel_axis(y_axis, spacing, "y_axis")
    z_world = _world_unit_from_voxel_axis(z_axis, spacing, "z_axis")
    matrix = np.stack([x_world, y_world, z_world], axis=1)
    det = float(np.linalg.det(matrix))
    if abs(det) < 0.5:
        raise ValueError("local_frame_axes_must_be_independent")
    return {
        "origin_zyx": origin.tolist(),
        "x_axis": x_axis.tolist(),
        "y_axis": y_axis.tolist(),
        "z_axis": z_axis.tolist(),
        "determinant": det,
        "spacing_zyx": spacing.tolist(),
    }


def validate_roll_reference_pair(roll_reference):
    if not isinstance(roll_reference, dict):
        raise ValueError("roll_reference_must_be_object")
    point_a = roll_reference.get("point_a") if isinstance(roll_reference.get("point_a"), dict) else {}
    point_b = roll_reference.get("point_b") if isinstance(roll_reference.get("point_b"), dict) else {}
    a = _point(point_a.get("zyx"), "roll_reference_point_a")
    b = _point(point_b.get("zyx"), "roll_reference_point_b")
    if float(np.linalg.norm(b - a)) <= 1e-8:
        raise ValueError("roll_reference_points_must_not_overlap")
    return {
        "pair_id": str(roll_reference.get("pair_id") or ""),
        "point_a": {"role": str(point_a.get("role") or "roll_point_a"), "zyx": a.tolist()},
        "point_b": {"role": str(point_b.get("role") or "roll_point_b"), "zyx": b.tolist()},
    }


def _roll_reference_from_payload(payload, local_frame):
    source = payload.get("roll_reference") if isinstance(payload, dict) else None
    if isinstance(source, dict) and source:
        return source
    frame_roll = local_frame.get("roll_reference") if isinstance(local_frame, dict) else None
    if isinstance(frame_roll, dict):
        return frame_roll
    return {}


def reslice_volume(volume, local_frame, params=None, interpolation="linear"):
    array = np.asarray(volume)
    if array.ndim != 3:
        raise ValueError(f"volume_must_be_3d:{array.ndim}")
    params = dict(params or {})
    output_shape = params.get("output_shape_zyx") or params.get("output_shape") or list(array.shape)
    if len(output_shape) != 3:
        raise ValueError("output_shape_zyx_must_have_3_values")
    output_shape = tuple(max(1, int(value)) for value in output_shape)
    spacing = _normalize_spacing(params.get("output_spacing_zyx") or local_frame.get("spacing_zyx") or [1.0, 1.0, 1.0])
    source_spacing = _normalize_spacing(local_frame.get("spacing_zyx") or [1.0, 1.0, 1.0])
    origin = _point(local_frame.get("origin_zyx"), "origin_zyx")
    axes_voxel = np.stack(
        [
            _unit(local_frame.get("z_axis"), "z_axis"),
            _unit(local_frame.get("y_axis"), "y_axis"),
            _unit(local_frame.get("x_axis"), "x_axis"),
        ],
        axis=0,
    )
    axis_steps = []
    for axis_index, axis_voxel in enumerate(axes_voxel):
        world_unit = _world_unit_from_voxel_axis(axis_voxel, source_spacing, f"local_frame_axis_{axis_index}")
        axis_steps.append((world_unit * spacing[axis_index]) / source_spacing)
    axis_steps = np.stack(axis_steps, axis=0)

    center = (np.array(output_shape, dtype=np.float64) - 1.0) / 2.0
    grid = np.indices(output_shape, dtype=np.float64)
    offsets = np.stack([grid[0] - center[0], grid[1] - center[1], grid[2] - center[2]], axis=0)
    coords = origin.reshape((3, 1, 1, 1)) + np.einsum("ia, i... -> a...", axis_steps, offsets)

    order = 0 if str(interpolation).lower() in {"nearest", "nearest-neighbor", "nearest_neighbor"} else 1
    cval = params.get("cval", 0)
    sampled = map_coordinates(array, coords, order=order, mode=str(params.get("mode") or "constant"), cval=float(cval), prefilter=order > 1)
    if order == 0:
        return sampled.astype(array.dtype, copy=False)
    if np.issubdtype(array.dtype, np.integer):
        info = np.iinfo(array.dtype)
        sampled = np.clip(np.rint(sampled), info.min, info.max)
        return sampled.astype(array.dtype)
    return sampled.astype(array.dtype, copy=False)


def build_reslice_preview(volume, local_frame, params=None, max_shape_zyx=(96, 96, 96)):
    array = np.asarray(volume)
    params = dict(params or {})
    max_shape = np.array([int(value) for value in max_shape_zyx], dtype=np.float64)
    shape = np.array(params.get("output_shape_zyx") or array.shape, dtype=np.float64)
    scale = min(1.0, float(np.min(max_shape / np.maximum(shape, 1.0))))
    preview_shape = tuple(max(1, int(round(value * scale))) for value in shape)
    preview_params = dict(params)
    preview_params["output_shape_zyx"] = list(preview_shape)
    base_spacing = _normalize_spacing(params.get("output_spacing_zyx") or local_frame.get("spacing_zyx") or [1.0, 1.0, 1.0])
    preview_spacing = []
    for full_count, preview_count, spacing_value in zip(shape, preview_shape, base_spacing):
        if full_count > 1 and preview_count > 1:
            preview_spacing.append(float(spacing_value) * float(full_count - 1.0) / float(preview_count - 1.0))
        else:
            preview_spacing.append(float(spacing_value))
    preview_params["output_spacing_zyx"] = preview_spacing
    return reslice_volume(array, local_frame, preview_params, interpolation=params.get("interpolation", "linear"))


def export_part_reslice(project_manager, specimen_id, part_id, reslice_payload):
    if not isinstance(project_manager, TifProjectManager):
        raise TypeError("project_manager_must_be_tif_project_manager")
    part = project_manager.get_part(specimen_id, part_id, default=None)
    if part is None:
        raise KeyError(f"unknown_part_id:{specimen_id}:{part_id}")
    payload = dict(reslice_payload or {})
    local_frame = dict(payload.get("local_frame") or {})
    allow_overwrite = bool(payload.get("allow_overwrite", False))
    reslice_id = _safe_id(payload.get("reslice_id") or f"reslice_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}", fallback="reslice")
    existing_record = project_manager.get_part_reslice(specimen_id, part_id, reslice_id, default=None)
    if existing_record is not None and not allow_overwrite:
        raise FileExistsError(f"part_reslice_id_exists:{specimen_id}:{part_id}:{reslice_id}")
    reslice_root_rel = f"{project_manager.part_dir(specimen_id, part_id)}/reslices/{reslice_id}"
    reslice_root_abs = project_manager.to_absolute(reslice_root_rel)
    if os.path.exists(reslice_root_abs):
        if not os.path.isdir(reslice_root_abs):
            raise FileExistsError(f"part_reslice_path_exists:{reslice_root_abs}")
        if not allow_overwrite:
            raise FileExistsError(reslice_root_abs)

    part_image = part.get("image") or {}
    image_path = project_manager.to_absolute(part_image.get("path", ""))
    if not volume_sidecar_exists(image_path):
        raise FileNotFoundError(image_path)
    image = load_volume_sidecar(image_path)
    image_meta = read_volume_metadata(image_path)
    local_frame.setdefault("spacing_zyx", image_meta.get("spacing_zyx") or (part_image.get("spacing_zyx") or [1.0, 1.0, 1.0]))
    roll_reference = validate_roll_reference_pair(_roll_reference_from_payload(payload, local_frame))
    local_frame["roll_reference"] = roll_reference
    validate_local_frame(local_frame)

    params = dict(payload.get("reslice_params") or {})
    params.setdefault("output_shape_zyx", list(image.shape))
    params.setdefault("output_spacing_zyx", image_meta.get("spacing_zyx") or [1.0, 1.0, 1.0])
    image_interpolation = params.get("image_interpolation", "linear")
    image_resliced = reslice_volume(image, local_frame, params, interpolation=image_interpolation)

    os.makedirs(reslice_root_abs, exist_ok=True)
    image_rel = f"{reslice_root_rel}/image.tif"
    image_abs = project_manager.to_absolute(image_rel)
    tifffile.imwrite(image_abs, image_resliced, photometric="minisblack")

    mask_rel = ""
    mask_meta_payload = {}
    if bool(payload.get("export_mask", True)):
        mask_record = part.get("mask") or {}
        mask_path = project_manager.to_absolute(mask_record.get("path", ""))
        if mask_record.get("path") and volume_sidecar_exists(mask_path):
            mask = load_volume_sidecar(mask_path)
            mask_resliced = reslice_volume(mask, local_frame, params, interpolation="nearest")
            mask_rel = f"{reslice_root_rel}/mask.tif"
            tifffile.imwrite(project_manager.to_absolute(mask_rel), mask_resliced, photometric="minisblack")
            mask_meta_payload = {
                "mask_path": mask_rel,
                "mask_dtype": str(mask_resliced.dtype),
                "mask_shape_zyx": [int(value) for value in mask_resliced.shape],
                "mask_interpolation": "nearest",
            }

    metadata_rel = f"{reslice_root_rel}/metadata.json"
    metadata_abs = project_manager.to_absolute(metadata_rel)
    metadata = {
        "schema_version": LOCAL_AXIS_RESLICE_SCHEMA_VERSION,
        "reslice_id": reslice_id,
        "specimen_id": str(specimen_id or ""),
        "part_id": str(part_id or ""),
        "template_id": str(payload.get("template_id") or ""),
        "created_at": _now_iso(),
        "source": {
            "part_image_path": part_image.get("path", ""),
            "part_mask_path": (part.get("mask") or {}).get("path", ""),
            "parent_bbox_zyx": part.get("parent_bbox_zyx", []),
            "source_axis": payload.get("source_axis") or source_z_axis_for_part(image.shape),
            "editable_axis": dict(payload.get("editable_axis") or {}),
        },
        "local_frame": local_frame,
        "reslice_params": params,
        "outputs": {
            "image_path": image_rel,
            "image_dtype": str(image_resliced.dtype),
            "image_shape_zyx": [int(value) for value in image_resliced.shape],
            "image_interpolation": str(image_interpolation),
            **mask_meta_payload,
        },
        "training": dict(payload.get("training") or {}),
        "provenance": dict(payload.get("provenance") or {}),
    }
    _write_json(metadata_abs, metadata)

    record = {
        "reslice_id": reslice_id,
        "specimen_id": specimen_id,
        "part_id": part_id,
        "display_name": payload.get("display_name") or reslice_id,
        "template_id": payload.get("template_id") or "",
        "status": "exported",
        "image_path": image_rel,
        "mask_path": mask_rel,
        "metadata_path": metadata_rel,
        "local_frame": local_frame,
        "reslice_params": params,
        "source": metadata["source"],
        "training": metadata["training"],
        "provenance": metadata["provenance"],
        "created_at": metadata["created_at"],
        "updated_at": metadata["created_at"],
    }
    if existing_record is not None and allow_overwrite:
        saved_record = project_manager.update_part_reslice(specimen_id, part_id, reslice_id, record, save=bool(payload.get("save", True)))
    else:
        saved_record = project_manager.add_part_reslice(specimen_id, part_id, record, save=bool(payload.get("save", True)))
    return {
        "record": saved_record,
        "metadata": metadata,
        "image": image_resliced,
        "image_path": image_abs,
        "mask_path": project_manager.to_absolute(mask_rel) if mask_rel else "",
        "metadata_path": metadata_abs,
    }
