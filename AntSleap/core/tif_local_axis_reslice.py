import json
import os
from datetime import datetime

import numpy as np
import tifffile
from scipy.ndimage import map_coordinates

from .safe_io import atomic_write_json
from .tif_project import TifProjectManager
from .tif_volume_io import load_volume_sidecar, read_volume_metadata, volume_sidecar_exists


LOCAL_AXIS_RESLICE_SCHEMA_VERSION = "taxamask_local_axis_reslice_v1"
LOCAL_AXIS_TRAINING_SAMPLE_SCHEMA_VERSION = "taxamask_tif_local_axis_training_sample_v1"
LOCAL_AXIS_RESLICE_SOFTWARE_VERSION = "TaxaMask local_axis_reslice_v1"
LOCAL_AXIS_RESLICE_COORDINATE_BUDGET_BYTES = 256 * 1024 * 1024


def _now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _safe_id(value, fallback="reslice"):
    text = str(value or "").strip()
    clean = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in text)
    clean = clean.strip("_")
    return clean or str(fallback or "reslice")


def _write_json(path, payload):
    atomic_write_json(path, payload, indent=2, ensure_ascii=False)
    return payload


def _axis_payload(value):
    return dict(value) if isinstance(value, dict) else {}


def _shape_payload(values, fallback_shape):
    source = values if isinstance(values, (list, tuple)) and len(values) == 3 else fallback_shape
    return [int(value) for value in source]


def _spacing_payload(values):
    return [float(value) for value in _normalize_spacing(values).tolist()]


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


def editable_axis_from_local_frame(local_frame, source_axis, part_shape_zyx, axis_id="local_output_z_axis"):
    source = source_axis if isinstance(source_axis, dict) else source_z_axis_for_part(part_shape_zyx)
    axis = create_editable_axis_from_source(source, axis_id=axis_id)
    axis["derived_from"] = "local_frame"
    try:
        origin = _point((local_frame or {}).get("origin_zyx"), "origin_zyx")
        z_axis = _unit((local_frame or {}).get("z_axis"), "z_axis")
        start = _point(source.get("start_zyx"), "source_axis_start")
        end = _point(source.get("end_zyx"), "source_axis_end")
        half_extent = max(0.5, float(np.linalg.norm(end - start)) / 2.0)
        axis["start_zyx"] = (origin - z_axis * half_extent).tolist()
        axis["end_zyx"] = (origin + z_axis * half_extent).tolist()
    except Exception:
        axis["derived_from"] = "source_axis_default"
    return axis


def reference_plane_from_points(point_a_zyx, point_b_zyx, point_c_zyx, spacing_zyx=None, preferred_normal_zyx=None):
    spacing = _normalize_spacing(spacing_zyx)
    point_a = _point(point_a_zyx, "reference_plane_point_a")
    point_b = _point(point_b_zyx, "reference_plane_point_b")
    point_c = _point(point_c_zyx, "reference_plane_point_c")
    point_a_world = point_a * spacing
    point_b_world = point_b * spacing
    point_c_world = point_c * spacing
    normal_world = np.cross(point_b_world - point_a_world, point_c_world - point_a_world)
    normal_length = float(np.linalg.norm(normal_world))
    if normal_length <= 1e-8:
        raise ValueError("reference_plane_points_must_not_be_collinear")
    normal_world = normal_world / normal_length
    if preferred_normal_zyx is not None:
        preferred_world = _world_unit_from_voxel_axis(preferred_normal_zyx, spacing, "preferred_reference_plane_normal")
        if float(np.dot(normal_world, preferred_world)) < 0.0:
            normal_world = -normal_world
    normal_axis = _voxel_unit_from_world_axis(normal_world, spacing, "reference_plane_normal")
    return {
        "plane_id": "three_point_reference_plane",
        "coordinate_space": "part_volume_voxel_zyx",
        "point_a_zyx": point_a.tolist(),
        "point_b_zyx": point_b.tolist(),
        "point_c_zyx": point_c.tolist(),
        "normal_axis_zyx": normal_axis.tolist(),
        "normal_world_zyx": normal_world.tolist(),
        "spacing_zyx": spacing.tolist(),
    }


def align_editable_axis_to_reference_plane(editable_axis, roll_reference, spacing_zyx=None, shape_zyx=None):
    axis = dict(editable_axis or {})
    start = _point(axis.get("start_zyx"), "editable_axis_start")
    end = _point(axis.get("end_zyx"), "editable_axis_end")
    spacing = _normalize_spacing(spacing_zyx)
    axis_world = (end - start) * spacing
    axis_length_world = float(np.linalg.norm(axis_world))
    if axis_length_world <= 1e-8:
        raise ValueError("editable_axis_points_must_not_overlap")
    roll = roll_reference if isinstance(roll_reference, dict) else {}
    point_a = roll.get("point_a") if isinstance(roll.get("point_a"), dict) else {}
    point_b = roll.get("point_b") if isinstance(roll.get("point_b"), dict) else {}
    point_c = roll.get("point_c") if isinstance(roll.get("point_c"), dict) else {}
    plane = reference_plane_from_points(
        point_a.get("zyx"),
        point_b.get("zyx"),
        point_c.get("zyx"),
        spacing_zyx=spacing,
        preferred_normal_zyx=end - start,
    )
    normal_world = np.asarray(plane["normal_world_zyx"], dtype=np.float64)
    center = (start + end) * 0.5
    half_length_world = axis_length_world * 0.5
    _ = shape_zyx

    half_delta_voxel = (normal_world * half_length_world) / spacing
    axis["start_zyx"] = [round(float(value), 3) for value in center - half_delta_voxel]
    axis["end_zyx"] = [round(float(value), 3) for value in center + half_delta_voxel]
    axis["derived_from"] = "three_point_reference_plane"
    axis["reference_plane"] = dict(plane)
    return axis, plane


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


def _output_axis_world_units(local_frame, source_spacing):
    return np.stack(
        [
            _world_unit_from_voxel_axis(local_frame.get("z_axis"), source_spacing, "z_axis"),
            _world_unit_from_voxel_axis(local_frame.get("y_axis"), source_spacing, "y_axis"),
            _world_unit_from_voxel_axis(local_frame.get("x_axis"), source_spacing, "x_axis"),
        ],
        axis=0,
    )


def local_axis_output_shape_for_source_bbox(source_shape_zyx, local_frame, output_spacing_zyx=None):
    shape = np.array([float(value) for value in source_shape_zyx], dtype=np.float64)
    if shape.size != 3 or not np.all(np.isfinite(shape)) or np.any(shape <= 0):
        raise ValueError("source_shape_zyx_must_have_3_positive_values")
    source_spacing = _normalize_spacing(local_frame.get("spacing_zyx") or [1.0, 1.0, 1.0])
    output_spacing = _normalize_spacing(output_spacing_zyx or local_frame.get("spacing_zyx") or [1.0, 1.0, 1.0])
    origin = _point(local_frame.get("origin_zyx"), "origin_zyx")
    axes_world = _output_axis_world_units(local_frame, source_spacing)
    upper = np.maximum(shape - 1.0, 0.0)
    corners = np.array(
        [
            [z, y, x]
            for z in (0.0, float(upper[0]))
            for y in (0.0, float(upper[1]))
            for x in (0.0, float(upper[2]))
        ],
        dtype=np.float64,
    )
    deltas_world = (corners - origin.reshape((1, 3))) * source_spacing.reshape((1, 3))
    offsets = deltas_world @ axes_world.T
    offsets = offsets / output_spacing.reshape((1, 3))
    half_extent = np.max(np.abs(offsets), axis=0)
    counts = np.ceil((half_extent * 2.0) + 1.0 - 1e-9).astype(np.int64)
    return [int(max(1, value)) for value in counts.tolist()]


def source_point_to_reslice_point(point_zyx, local_frame, reslice_params=None):
    params = dict(reslice_params or {})
    output_shape = params.get("output_shape_zyx") or params.get("output_shape")
    if output_shape is None or len(output_shape) != 3:
        raise ValueError("output_shape_zyx_must_have_3_values")
    output_shape = np.array([float(value) for value in output_shape], dtype=np.float64)
    if not np.all(np.isfinite(output_shape)) or np.any(output_shape <= 0):
        raise ValueError("output_shape_zyx_must_have_3_positive_values")
    source_spacing = _normalize_spacing(local_frame.get("spacing_zyx") or [1.0, 1.0, 1.0])
    output_spacing = _normalize_spacing(params.get("output_spacing_zyx") or local_frame.get("spacing_zyx") or [1.0, 1.0, 1.0])
    origin = _point(local_frame.get("origin_zyx"), "origin_zyx")
    point = _point(point_zyx, "source_point_zyx")
    axes_world = _output_axis_world_units(local_frame, source_spacing)
    delta_world = (point - origin) * source_spacing
    offsets = (axes_world @ delta_world) / output_spacing
    center = (output_shape - 1.0) / 2.0
    return [float(value) for value in (center + offsets).tolist()]


def validate_roll_reference_pair(roll_reference):
    if not isinstance(roll_reference, dict):
        raise ValueError("roll_reference_must_be_object")
    point_a = roll_reference.get("point_a") if isinstance(roll_reference.get("point_a"), dict) else {}
    point_b = roll_reference.get("point_b") if isinstance(roll_reference.get("point_b"), dict) else {}
    a = _point(point_a.get("zyx"), "roll_reference_point_a")
    b = _point(point_b.get("zyx"), "roll_reference_point_b")
    if float(np.linalg.norm(b - a)) <= 1e-8:
        raise ValueError("roll_reference_points_must_not_overlap")
    clean = {
        "pair_id": str(roll_reference.get("pair_id") or ""),
        "point_a": {"role": str(point_a.get("role") or "roll_point_a"), "zyx": a.tolist()},
        "point_b": {"role": str(point_b.get("role") or "roll_point_b"), "zyx": b.tolist()},
    }
    point_c = roll_reference.get("point_c") if isinstance(roll_reference.get("point_c"), dict) else {}
    if point_c.get("zyx") is not None:
        c = _point(point_c.get("zyx"), "roll_reference_point_c")
        clean["point_c"] = {"role": str(point_c.get("role") or "reference_plane_c"), "zyx": c.tolist()}
    if isinstance(roll_reference.get("reference_plane"), dict):
        clean["reference_plane"] = dict(roll_reference.get("reference_plane"))
    return clean


def _roll_reference_from_payload(payload, local_frame):
    source = payload.get("roll_reference") if isinstance(payload, dict) else None
    if isinstance(source, dict) and source:
        return source
    frame_roll = local_frame.get("roll_reference") if isinstance(local_frame, dict) else None
    if isinstance(frame_roll, dict):
        return frame_roll
    return {}


def _reslice_interpolation_order(interpolation):
    return 0 if str(interpolation).lower() in {"nearest", "nearest-neighbor", "nearest_neighbor"} else 1


def _reslice_axis_steps(local_frame, params, output_shape):
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
    return origin, np.stack(axis_steps, axis=0), (np.array(output_shape, dtype=np.float64) - 1.0) / 2.0


def _reslice_chunk_shape(output_shape, params):
    requested = params.get("chunk_shape_zyx")
    if isinstance(requested, (list, tuple)) and len(requested) == 3:
        return tuple(max(1, min(int(output_shape[index]), int(value))) for index, value in enumerate(requested))
    budget = params.get("coordinate_budget_bytes", LOCAL_AXIS_RESLICE_COORDINATE_BUDGET_BYTES)
    try:
        budget = int(budget)
    except (TypeError, ValueError):
        budget = LOCAL_AXIS_RESLICE_COORDINATE_BUDGET_BYTES
    budget = max(3 * np.dtype(np.float64).itemsize, budget)
    max_coordinate_voxels = max(1, int(budget // (3 * np.dtype(np.float64).itemsize)))
    z_count, y_count, x_count = [int(value) for value in output_shape]
    x_chunk = min(x_count, max(1, max_coordinate_voxels))
    y_chunk = min(y_count, max(1, max_coordinate_voxels // max(1, x_chunk)))
    z_chunk = min(z_count, max(1, max_coordinate_voxels // max(1, y_chunk * x_chunk)))
    return z_chunk, y_chunk, x_chunk


def _reslice_volume_chunk(array, origin, axis_steps, center, output_slices, params, order):
    z_slice, y_slice, x_slice = output_slices
    z_offsets = (np.arange(z_slice.start, z_slice.stop, dtype=np.float64) - center[0]).reshape((-1, 1, 1))
    y_offsets = (np.arange(y_slice.start, y_slice.stop, dtype=np.float64) - center[1]).reshape((1, -1, 1))
    x_offsets = (np.arange(x_slice.start, x_slice.stop, dtype=np.float64) - center[2]).reshape((1, 1, -1))
    coords_shape = (3, z_slice.stop - z_slice.start, y_slice.stop - y_slice.start, x_slice.stop - x_slice.start)
    coords = np.empty(coords_shape, dtype=np.float64)
    for source_axis in range(3):
        coords[source_axis] = origin[source_axis]
        coords[source_axis] += axis_steps[0, source_axis] * z_offsets
        coords[source_axis] += axis_steps[1, source_axis] * y_offsets
        coords[source_axis] += axis_steps[2, source_axis] * x_offsets
    sampled = map_coordinates(
        array,
        coords,
        order=order,
        mode=str(params.get("mode") or "constant"),
        cval=float(params.get("cval", 0)),
        prefilter=order > 1,
    )
    if order == 0:
        return sampled.astype(array.dtype, copy=False)
    if np.issubdtype(array.dtype, np.integer):
        info = np.iinfo(array.dtype)
        sampled = np.clip(np.rint(sampled), info.min, info.max)
        return sampled.astype(array.dtype)
    return sampled.astype(array.dtype, copy=False)


def reslice_volume_to_array(
    volume,
    local_frame,
    output,
    params=None,
    interpolation="linear",
    progress_callback=None,
):
    array = np.asarray(volume)
    if array.ndim != 3:
        raise ValueError(f"volume_must_be_3d:{array.ndim}")
    params = dict(params or {})
    output_shape = params.get("output_shape_zyx") or params.get("output_shape") or list(array.shape)
    if len(output_shape) != 3:
        raise ValueError("output_shape_zyx_must_have_3_values")
    output_shape = tuple(max(1, int(value)) for value in output_shape)
    target = np.asarray(output)
    if tuple(int(value) for value in target.shape) != output_shape:
        raise ValueError(f"output_shape_mismatch:{target.shape}:{output_shape}")
    origin, axis_steps, center = _reslice_axis_steps(local_frame, params, output_shape)
    order = _reslice_interpolation_order(interpolation)
    z_chunk, y_chunk, x_chunk = _reslice_chunk_shape(output_shape, params)
    total_chunks = (
        ((output_shape[0] + z_chunk - 1) // z_chunk)
        * ((output_shape[1] + y_chunk - 1) // y_chunk)
        * ((output_shape[2] + x_chunk - 1) // x_chunk)
    )
    done = 0
    for z0 in range(0, output_shape[0], z_chunk):
        z1 = min(output_shape[0], z0 + z_chunk)
        for y0 in range(0, output_shape[1], y_chunk):
            y1 = min(output_shape[1], y0 + y_chunk)
            for x0 in range(0, output_shape[2], x_chunk):
                x1 = min(output_shape[2], x0 + x_chunk)
                output_slices = (slice(z0, z1), slice(y0, y1), slice(x0, x1))
                target[output_slices] = _reslice_volume_chunk(
                    array,
                    origin,
                    axis_steps,
                    center,
                    output_slices,
                    params,
                    order,
                )
                done += 1
                if callable(progress_callback):
                    progress_callback(done, total_chunks)
    if hasattr(output, "flush"):
        output.flush()
    return output


def reslice_volume(volume, local_frame, params=None, interpolation="linear"):
    array = np.asarray(volume)
    if array.ndim != 3:
        raise ValueError(f"volume_must_be_3d:{array.ndim}")
    params = dict(params or {})
    output_shape = params.get("output_shape_zyx") or params.get("output_shape") or list(array.shape)
    if len(output_shape) != 3:
        raise ValueError("output_shape_zyx_must_have_3_values")
    output_shape = tuple(max(1, int(value)) for value in output_shape)
    output = np.empty(output_shape, dtype=array.dtype)
    return reslice_volume_to_array(array, local_frame, output, params=params, interpolation=interpolation)


def _emit_progress(progress_callback, current, total, message):
    if callable(progress_callback):
        progress_callback(int(current), int(total), str(message or ""))


def _close_memmap(array):
    mmap = getattr(array, "_mmap", None)
    if mmap is not None:
        try:
            mmap.close()
        except Exception:
            pass


def _temporary_tif_path(final_path):
    root, ext = os.path.splitext(str(final_path))
    ext = ext or ".tif"
    return f"{root}.tmp_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{os.getpid()}{ext}"


def _write_resliced_tif(
    volume,
    local_frame,
    params,
    output_path,
    interpolation="linear",
    progress_callback=None,
    progress_start=0,
    progress_end=100,
    progress_label="Reslicing volume",
):
    array = np.asarray(volume)
    output_shape = params.get("output_shape_zyx") or params.get("output_shape") or list(array.shape)
    if len(output_shape) != 3:
        raise ValueError("output_shape_zyx_must_have_3_values")
    output_shape = tuple(max(1, int(value)) for value in output_shape)
    output_path = os.path.abspath(str(output_path))
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    tmp_path = _temporary_tif_path(output_path)
    output = None
    try:
        output = tifffile.memmap(
            tmp_path,
            shape=output_shape,
            dtype=array.dtype,
            photometric="minisblack",
            bigtiff=True,
        )

        def _on_chunk(done, total):
            span = max(0, int(progress_end) - int(progress_start))
            if total > 0:
                current = int(progress_start) + int(round(span * float(done) / float(total)))
            else:
                current = int(progress_start)
            _emit_progress(progress_callback, current, 100, progress_label)

        reslice_volume_to_array(
            array,
            local_frame,
            output,
            params=params,
            interpolation=interpolation,
            progress_callback=_on_chunk if callable(progress_callback) else None,
        )
        if hasattr(output, "flush"):
            output.flush()
        _close_memmap(output)
        output = None
        os.replace(tmp_path, output_path)
        return {
            "path": output_path,
            "shape_zyx": [int(value) for value in output_shape],
            "dtype": str(array.dtype),
        }
    except Exception:
        if output is not None:
            _close_memmap(output)
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        raise


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


def export_part_reslice(project_manager, specimen_id, part_id, reslice_payload, progress_callback=None):
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
    image = load_volume_sidecar(image_path, mmap_mode="r")
    image_meta = read_volume_metadata(image_path)
    part_image_shape = _shape_payload(image_meta.get("shape_zyx") or part_image.get("shape_zyx"), image.shape)
    part_spacing = _spacing_payload(image_meta.get("spacing_zyx") or (part_image.get("spacing_zyx") or [1.0, 1.0, 1.0]))
    part_image_dtype = str(image_meta.get("dtype") or part_image.get("dtype") or image.dtype)
    mask_record = part.get("mask") or {}
    mask_path = project_manager.to_absolute(mask_record.get("path", ""))
    part_mask_available = bool(mask_record.get("path") and volume_sidecar_exists(mask_path))
    part_mask_shape = []
    part_mask_dtype = str(mask_record.get("dtype") or "")
    if part_mask_available:
        try:
            mask_meta = read_volume_metadata(mask_path)
            part_mask_shape = _shape_payload(mask_meta.get("shape_zyx") or mask_record.get("shape_zyx"), image.shape)
            part_mask_dtype = str(mask_meta.get("dtype") or part_mask_dtype)
        except Exception:
            part_mask_shape = _shape_payload(mask_record.get("shape_zyx"), image.shape) if mask_record.get("shape_zyx") else []

    local_frame.setdefault("spacing_zyx", part_spacing)
    roll_reference = validate_roll_reference_pair(_roll_reference_from_payload(payload, local_frame))
    local_frame["roll_reference"] = roll_reference
    reference_plane = dict(roll_reference.get("reference_plane") or payload.get("reference_plane") or {})
    if reference_plane:
        local_frame["reference_plane"] = reference_plane
    validate_local_frame(local_frame)

    params = dict(payload.get("reslice_params") or {})
    params.setdefault("output_spacing_zyx", part_spacing)
    if not params.get("output_shape_zyx") and not params.get("output_shape"):
        params["output_shape_zyx"] = local_axis_output_shape_for_source_bbox(image.shape, local_frame, params.get("output_spacing_zyx"))
    image_interpolation = params.get("image_interpolation", "linear")

    os.makedirs(reslice_root_abs, exist_ok=True)
    image_rel = f"{reslice_root_rel}/image.tif"
    image_abs = project_manager.to_absolute(image_rel)
    _emit_progress(progress_callback, 5, 100, "Preparing Local Axis Reslice image...")
    image_write = _write_resliced_tif(
        image,
        local_frame,
        params,
        image_abs,
        interpolation=image_interpolation,
        progress_callback=progress_callback,
        progress_start=5,
        progress_end=75,
        progress_label="Reslicing Local Axis image",
    )

    mask_rel = ""
    mask_meta_payload = {}
    if bool(payload.get("export_mask", True)):
        if part_mask_available:
            mask = load_volume_sidecar(mask_path, mmap_mode="r")
            mask_rel = f"{reslice_root_rel}/mask.tif"
            mask_write = _write_resliced_tif(
                mask,
                local_frame,
                params,
                project_manager.to_absolute(mask_rel),
                interpolation="nearest",
                progress_callback=progress_callback,
                progress_start=75,
                progress_end=95,
                progress_label="Reslicing Local Axis mask",
            )
            mask_meta_payload = {
                "mask_path": mask_rel,
                "mask_dtype": str(mask_write["dtype"]),
                "mask_shape_zyx": [int(value) for value in mask_write["shape_zyx"]],
                "mask_interpolation": "nearest",
            }

    metadata_rel = f"{reslice_root_rel}/metadata.json"
    metadata_abs = project_manager.to_absolute(metadata_rel)
    created_at = _now_iso()
    updated_at = created_at
    template_id = str(payload.get("template_id") or "")
    source_axis = _axis_payload(payload.get("source_axis")) or source_z_axis_for_part(image.shape)
    initial_editable_axis = (
        _axis_payload(payload.get("initial_editable_axis"))
        or _axis_payload(payload.get("editable_axis"))
        or create_editable_axis_from_source(source_axis)
    )
    final_editable_axis = (
        _axis_payload(payload.get("final_editable_axis"))
        or _axis_payload(payload.get("editable_axis"))
        or editable_axis_from_local_frame(local_frame, source_axis, image.shape)
    )
    source_payload = {
        "part_image_path": part_image.get("path", ""),
        "part_image_shape_zyx": part_image_shape,
        "part_image_dtype": part_image_dtype,
        "part_spacing_zyx": part_spacing,
        "part_spacing_unit": str(image_meta.get("spacing_unit") or part_image.get("spacing_unit") or "micrometer"),
        "part_mask_path": mask_record.get("path", ""),
        "part_mask_available": part_mask_available,
        "parent_bbox_zyx": part.get("parent_bbox_zyx", []),
        "source_axis": source_axis,
        "initial_editable_axis": initial_editable_axis,
        "final_editable_axis": final_editable_axis,
        "editable_axis": final_editable_axis,
    }
    outputs_payload = {
        "image_path": image_rel,
        "image_dtype": str(image_write["dtype"]),
        "image_shape_zyx": [int(value) for value in image_write["shape_zyx"]],
        "image_interpolation": str(image_interpolation),
        **mask_meta_payload,
    }
    training_payload = dict(payload.get("training") or {})
    operator_notes = str(payload.get("operator_notes") or training_payload.get("reviewer_notes") or "")
    human_confirmed = bool(training_payload.get("human_confirmed", False))
    usable_for_training = bool(training_payload.get("usable_for_training", human_confirmed))
    training_sample = {
        "schema_version": LOCAL_AXIS_TRAINING_SAMPLE_SCHEMA_VERSION,
        "sample_id": f"{specimen_id}:{part_id}:{reslice_id}",
        "specimen_id": str(specimen_id or ""),
        "part_id": str(part_id or ""),
        "reslice_id": reslice_id,
        "template_id": template_id,
        "part_image": {
            "path": part_image.get("path", ""),
            "shape_zyx": part_image_shape,
            "dtype": part_image_dtype,
            "spacing_zyx": part_spacing,
            "spacing_unit": source_payload["part_spacing_unit"],
        },
        "part_mask": {
            "path": mask_record.get("path", ""),
            "available": part_mask_available,
            "shape_zyx": part_mask_shape,
            "dtype": part_mask_dtype,
        },
        "parent_bbox_zyx": part.get("parent_bbox_zyx", []),
        "source_axis": source_axis,
        "initial_editable_axis": initial_editable_axis,
        "final_editable_axis": final_editable_axis,
        "origin_zyx": list(local_frame.get("origin_zyx") or []),
        "roll_reference_point_pair": roll_reference,
        "roll_reference": roll_reference,
        "reference_plane": reference_plane,
        "local_frame": local_frame,
        "reslice_params": params,
        "outputs": outputs_payload,
        "human_confirmed": human_confirmed,
        "usable_for_training": usable_for_training,
        "training_source": str(training_payload.get("source") or ""),
        "hard_case_flags": list(training_payload.get("hard_case_flags", []) or []) if isinstance(training_payload.get("hard_case_flags", []), list) else [],
        "operator_notes": operator_notes,
        "created_at": created_at,
        "updated_at": updated_at,
        "software_version": LOCAL_AXIS_RESLICE_SOFTWARE_VERSION,
        "provenance": dict(payload.get("provenance") or {}),
    }
    metadata = {
        "schema_version": LOCAL_AXIS_RESLICE_SCHEMA_VERSION,
        "reslice_id": reslice_id,
        "specimen_id": str(specimen_id or ""),
        "part_id": str(part_id or ""),
        "template_id": template_id,
        "created_at": created_at,
        "updated_at": updated_at,
        "software_version": LOCAL_AXIS_RESLICE_SOFTWARE_VERSION,
        "source": source_payload,
        "local_frame": local_frame,
        "reference_plane": reference_plane,
        "reslice_params": params,
        "outputs": outputs_payload,
        "training": training_payload,
        "training_sample": training_sample,
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
        "training_sample": metadata["training_sample"],
        "provenance": metadata["provenance"],
        "created_at": metadata["created_at"],
        "updated_at": metadata["updated_at"],
    }
    if existing_record is not None and allow_overwrite:
        saved_record = project_manager.update_part_reslice(specimen_id, part_id, reslice_id, record, save=bool(payload.get("save", True)))
    else:
        saved_record = project_manager.add_part_reslice(specimen_id, part_id, record, save=bool(payload.get("save", True)))
    return {
        "record": saved_record,
        "metadata": metadata,
        "image": None,
        "image_path": image_abs,
        "mask_path": project_manager.to_absolute(mask_rel) if mask_rel else "",
        "metadata_path": metadata_abs,
    }
