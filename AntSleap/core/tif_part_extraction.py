import json
import os
import shutil
from datetime import datetime

import numpy as np

from .tif_volume_io import flush_volume_array, load_volume_sidecar, write_volume_sidecar


TIF_PART_EXTRACTION_VERSION = "taxamask_tif_part_extraction_v1"


def _now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def normalize_bbox_zyx(bbox_zyx, shape_zyx):
    shape = [int(value) for value in shape_zyx]
    if len(shape) != 3 or min(shape) <= 0:
        raise ValueError("shape_zyx_must_have_3_positive_values")
    if not isinstance(bbox_zyx, (list, tuple)) or len(bbox_zyx) != 3:
        raise ValueError("bbox_zyx_must_have_3_ranges")
    clean = []
    for axis, pair in enumerate(bbox_zyx):
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError("bbox_zyx_range_must_have_2_values")
        start = max(0, min(shape[axis], int(pair[0])))
        end = max(0, min(shape[axis], int(pair[1])))
        if end < start:
            start, end = end, start
        if end == start:
            end = min(shape[axis], start + 1)
            start = max(0, end - 1)
        clean.append([start, end])
    return clean


def bbox_shape_zyx(bbox_zyx):
    return [int(pair[1]) - int(pair[0]) for pair in bbox_zyx]


def crop_volume_to_part(project_manager, specimen_id, part_id, bbox_zyx, display_name="", save=True):
    specimen = project_manager.get_specimen(specimen_id, default=None)
    if specimen is None:
        raise KeyError(f"unknown_specimen_id:{specimen_id}")
    clean_part_id = (
        project_manager._validate_new_part_id(specimen, part_id)
        if callable(getattr(project_manager, "_validate_new_part_id", None))
        else str(part_id or "").strip()
    )
    working = specimen.get("working_volume") or {}
    image_path = project_manager.to_absolute(working.get("path", ""))
    if not image_path:
        raise ValueError("working_volume_missing")
    source = load_volume_sidecar(image_path, mmap_mode="r")
    bbox = normalize_bbox_zyx(bbox_zyx, source.shape)
    z_range, y_range, x_range = bbox
    crop = np.asarray(source[z_range[0] : z_range[1], y_range[0] : y_range[1], x_range[0] : x_range[1]])
    if crop.size == 0:
        raise ValueError("part_crop_empty")

    part_root_rel = project_manager.part_dir(specimen_id, clean_part_id)
    part_root_abs = project_manager.to_absolute(part_root_rel)
    if os.path.exists(part_root_abs):
        if not os.path.isdir(part_root_abs):
            raise FileExistsError(f"part_storage_path_exists:{part_root_rel}")
        with os.scandir(part_root_abs) as entries:
            if any(entries):
                raise FileExistsError(f"part_storage_dir_not_empty:{part_root_rel}")
    image_rel = f"{part_root_rel}/image.ome.zarr"
    mask_rel = f"{part_root_rel}/mask.ome.zarr"
    contours_rel = f"{part_root_rel}/contours.json"
    extraction_rel = f"{part_root_rel}/extraction.json"
    image_abs = project_manager.to_absolute(image_rel)
    mask_abs = project_manager.to_absolute(mask_rel)
    contours_abs = project_manager.to_absolute(contours_rel)
    extraction_abs = project_manager.to_absolute(extraction_rel)

    spacing = working.get("spacing_zyx") or [1.0, 1.0, 1.0]
    spacing_unit = working.get("spacing_unit", "micrometer")
    orientation = working.get("orientation", "unknown")
    image_meta = write_volume_sidecar(
        image_abs,
        crop,
        role="part_image",
        spacing_zyx=spacing,
        spacing_unit=spacing_unit,
        orientation=orientation,
        source_format=TIF_PART_EXTRACTION_VERSION,
        extra_metadata={
            "parent_specimen_id": specimen_id,
            "parent_volume_role": "working_volume",
            "parent_bbox_zyx": bbox,
        },
    )
    mask = np.zeros(crop.shape, dtype=np.uint16)
    mask_meta = write_volume_sidecar(
        mask_abs,
        mask,
        role="part_mask",
        spacing_zyx=spacing,
        spacing_unit=spacing_unit,
        orientation=orientation,
        source_format=TIF_PART_EXTRACTION_VERSION,
        extra_metadata={
            "parent_specimen_id": specimen_id,
            "parent_volume_role": "working_volume",
            "parent_bbox_zyx": bbox,
        },
    )

    extraction = {
        "schema_version": TIF_PART_EXTRACTION_VERSION,
        "part_id": str(clean_part_id or ""),
        "display_name": str(display_name or clean_part_id or ""),
        "parent_specimen_id": str(specimen_id or ""),
        "parent_volume_role": "working_volume",
        "bbox_zyx": bbox,
        "source_shape_zyx": [int(value) for value in source.shape],
        "part_shape_zyx": bbox_shape_zyx(bbox),
        "spacing_zyx": [float(value) for value in spacing],
        "spacing_unit": str(spacing_unit or "micrometer"),
        "orientation": str(orientation or "unknown"),
        "status": "roi_confirmed",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    write_json(extraction_abs, extraction)
    if not os.path.exists(contours_abs):
        write_contours_json(
            contours_abs,
            {
                "schema_version": TIF_PART_EXTRACTION_VERSION,
                "part_id": str(clean_part_id or ""),
                "axis": "z",
                "keyframes": [],
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
            },
        )

    return project_manager.add_part(
        specimen_id,
        clean_part_id,
        display_name=display_name or clean_part_id,
        image={"path": image_rel, **image_meta},
        mask={"path": mask_rel, **mask_meta},
        parent_bbox_zyx=bbox,
        source={"parent_specimen_id": specimen_id, "parent_volume_role": "working_volume"},
        contours_path=contours_rel,
        extraction_path=extraction_rel,
        status="roi_confirmed",
        metadata={"algorithm_version": TIF_PART_EXTRACTION_VERSION},
        save=save,
    )


def write_json(path, payload):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return payload


def read_json(path, default=None):
    if not path or not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError, UnicodeError):
        return default
    return payload if isinstance(payload, dict) else default


def _safe_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def _clean_polygon_points(polygon):
    points = []
    for point in polygon or []:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        x = _safe_int(point[0])
        y = _safe_int(point[1])
        if x is None or y is None:
            continue
        points.append([x, y])
    return points


def _iter_keyframe_records(contours_payload):
    keyframes = (contours_payload or {}).get("keyframes", []) or []
    if not isinstance(keyframes, (list, tuple)):
        return
    for item in keyframes:
        if isinstance(item, dict):
            yield item


def read_contours_json(path):
    payload = read_json(path, default=None)
    if not isinstance(payload, dict):
        return {"schema_version": TIF_PART_EXTRACTION_VERSION, "axis": "z", "keyframes": []}
    payload.setdefault("schema_version", TIF_PART_EXTRACTION_VERSION)
    payload.setdefault("axis", "z")
    if not isinstance(payload.get("keyframes", []), list):
        payload["keyframes"] = []
    else:
        payload.setdefault("keyframes", [])
    return payload


def write_contours_json(path, payload):
    clean = dict(payload or {}) if isinstance(payload, dict) else {}
    clean.setdefault("schema_version", TIF_PART_EXTRACTION_VERSION)
    clean.setdefault("axis", "z")
    if not isinstance(clean.get("keyframes", []), list):
        clean["keyframes"] = []
    else:
        clean.setdefault("keyframes", [])
    clean["updated_at"] = _now_iso()
    return write_json(path, clean)


def rectangle_polygon_for_slice(bbox_yx):
    (y0, y1), (x0, x1) = bbox_yx
    return [[int(x0), int(y0)], [int(x1), int(y0)], [int(x1), int(y1)], [int(x0), int(y1)]]


def polygon_to_mask(points, shape_yx):
    height, width = [int(value) for value in shape_yx]
    if height <= 0 or width <= 0:
        raise ValueError("shape_yx_must_be_positive")
    if not points or len(points) < 3:
        return np.zeros((height, width), dtype=bool)
    polygon = np.asarray(points, dtype=np.float32)
    try:
        from matplotlib.path import Path

        yy, xx = np.mgrid[:height, :width]
        coords = np.stack([xx.reshape(-1), yy.reshape(-1)], axis=1)
        return Path(polygon).contains_points(coords).reshape((height, width))
    except Exception:
        return _scanline_polygon_to_mask(polygon, height, width)


def _scanline_polygon_to_mask(polygon, height, width):
    mask = np.zeros((height, width), dtype=bool)
    x = polygon[:, 0]
    y = polygon[:, 1]
    count = len(polygon)
    for row in range(height):
        intersections = []
        py = row + 0.5
        for idx in range(count):
            jdx = (idx + 1) % count
            y0, y1 = y[idx], y[jdx]
            if (y0 <= py < y1) or (y1 <= py < y0):
                x0, x1 = x[idx], x[jdx]
                denom = y1 - y0
                if abs(float(denom)) > 1e-6:
                    intersections.append(x0 + (py - y0) * (x1 - x0) / denom)
        intersections.sort()
        for left, right in zip(intersections[0::2], intersections[1::2]):
            x0 = max(0, int(np.floor(left)))
            x1 = min(width, int(np.ceil(right)))
            if x1 > x0:
                mask[row, x0:x1] = True
    return mask


def signed_distance(mask):
    mask_bool = np.asarray(mask, dtype=bool)
    try:
        from scipy.ndimage import distance_transform_edt

        outside = distance_transform_edt(~mask_bool)
        inside = distance_transform_edt(mask_bool)
        return outside - inside
    except Exception:
        return np.where(mask_bool, -1.0, 1.0).astype(np.float32)


def scipy_distance_available():
    try:
        from scipy.ndimage import distance_transform_edt  # noqa: F401

        return True
    except Exception:
        return False


def validate_contours_for_interpolation(contours_payload, shape_zyx=None, axis="z", max_gap_slices=24):
    axis = str(axis or "z")
    keyframes = []
    warnings = []
    errors = []
    try:
        shape = tuple(int(value) for value in shape_zyx) if shape_zyx is not None else ()
    except (TypeError, ValueError):
        shape = ()
        errors.append({"code": "invalid_shape_zyx", "message": "Volume shape is invalid."})
    if shape and (len(shape) != 3 or min(shape) <= 0):
        errors.append({"code": "invalid_shape_zyx", "message": "Volume shape is invalid."})
        shape = ()
    for item in _iter_keyframe_records(contours_payload):
        item_axis = str(item.get("axis", "z") or "z")
        slice_index = _safe_int(item.get("slice_index"), None)
        if slice_index is None:
            warnings.append({"code": "invalid_slice_index", "message": "A key slice has an invalid slice index."})
            continue
        polygon = _clean_polygon_points(item.get("polygon") or [])
        if item_axis != axis:
            warnings.append(
                {
                    "code": "ignored_non_target_axis",
                    "message": f"Key slice {slice_index} uses axis {item_axis}; current interpolation uses {axis}.",
                    "slice_index": slice_index,
                    "axis": item_axis,
                }
            )
            continue
        if shape and not (0 <= slice_index < shape[0]):
            errors.append(
                {
                    "code": "slice_index_out_of_range",
                    "message": f"Key slice {slice_index} is outside the part volume.",
                    "slice_index": slice_index,
                }
            )
            continue
        if len(polygon) < 3:
            errors.append(
                {
                    "code": "polygon_too_small",
                    "message": f"Key slice {slice_index} has fewer than 3 contour points.",
                    "slice_index": slice_index,
                }
            )
            continue
        if shape:
            height, width = int(shape[1]), int(shape[2])
            outside = [
                point
                for point in polygon
                if len(point) < 2 or int(point[0]) < 0 or int(point[0]) >= width or int(point[1]) < 0 or int(point[1]) >= height
            ]
            if outside:
                warnings.append(
                    {
                        "code": "polygon_points_clipped_or_outside",
                        "message": f"Key slice {slice_index} has contour points outside the part image.",
                        "slice_index": slice_index,
                    }
                )
        keyframes.append({"slice_index": slice_index, "polygon": polygon, "axis": item_axis})
    indices = sorted(int(item["slice_index"]) for item in keyframes)
    if not indices:
        errors.append({"code": "no_key_slices", "message": "No usable key slices were found."})
    elif len(indices) == 1:
        warnings.append({"code": "single_key_slice", "message": "Only one key slice is available; preview will fill that slice only."})
    else:
        gaps = [right - left for left, right in zip(indices, indices[1:])]
        large_gaps = [gap for gap in gaps if gap > int(max_gap_slices)]
        if large_gaps:
            warnings.append(
                {
                    "code": "large_key_slice_gap",
                    "message": f"Some neighboring key slices are far apart ({max(large_gaps)} slices). Add middle key slices for safer interpolation.",
                    "max_gap_slices": max(large_gaps),
                }
            )
    if not scipy_distance_available():
        warnings.append(
            {
                "code": "scipy_distance_unavailable",
                "message": "SciPy distance transform is unavailable; interpolation falls back to copied inside/outside masks.",
            }
        )
    return {
        "ok": not errors,
        "axis": axis,
        "key_slice_indices": indices,
        "key_slice_count": len(indices),
        "errors": errors,
        "warnings": warnings,
    }


def interpolate_masks_from_keyframes(keyframes, shape_zyx):
    shape = tuple(int(value) for value in shape_zyx)
    if len(shape) != 3 or min(shape) <= 0:
        raise ValueError("shape_zyx_must_have_3_positive_values")
    normalized = []
    for keyframe in keyframes or []:
        if not isinstance(keyframe, dict):
            continue
        if str(keyframe.get("axis", "z")) != "z":
            continue
        slice_index = _safe_int(keyframe.get("slice_index"), None)
        if slice_index is None:
            continue
        if 0 <= slice_index < shape[0]:
            mask = polygon_to_mask(_clean_polygon_points(keyframe.get("polygon") or []), shape[1:])
            normalized.append((slice_index, mask))
    if not normalized:
        return np.zeros(shape, dtype=np.uint16)
    normalized.sort(key=lambda item: item[0])
    result = np.zeros(shape, dtype=np.uint16)
    for index, mask in normalized:
        result[index] = mask.astype(np.uint16)
    for (start_idx, start_mask), (end_idx, end_mask) in zip(normalized, normalized[1:]):
        if end_idx <= start_idx:
            continue
        start_dist = signed_distance(start_mask)
        end_dist = signed_distance(end_mask)
        span = float(end_idx - start_idx)
        for z_index in range(start_idx + 1, end_idx):
            weight = float(z_index - start_idx) / span
            dist = (1.0 - weight) * start_dist + weight * end_dist
            result[z_index] = (dist <= 0.0).astype(np.uint16)
    return result


def add_rectangular_keyframe(contours_payload, slice_index, bbox_yx, author="taxamask"):
    return add_polygon_keyframe(
        contours_payload,
        slice_index,
        rectangle_polygon_for_slice(bbox_yx),
        author=author,
        source="rectangle",
    )


def add_polygon_keyframe(contours_payload, slice_index, polygon, axis="z", author="taxamask", source="manual"):
    payload = dict(contours_payload or {})
    payload.setdefault("schema_version", TIF_PART_EXTRACTION_VERSION)
    axis = str(axis or "z")
    payload["axis"] = axis
    clean_polygon = []
    for point in polygon or []:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        try:
            clean_polygon.append([int(round(float(point[0]))), int(round(float(point[1])))])
        except (TypeError, ValueError):
            continue
    if len(clean_polygon) < 3:
        raise ValueError("contour_polygon_needs_at_least_3_points")
    keyframes = [
        item
        for item in _iter_keyframe_records(payload)
        if not (str(item.get("axis", "z")) == axis and _safe_int(item.get("slice_index"), None) == int(slice_index))
    ]
    keyframes.append(
        {
            "axis": axis,
            "slice_index": int(slice_index),
            "polygon": clean_polygon,
            "author": str(author or "taxamask"),
            "source": str(source or "manual"),
            "created_at": _now_iso(),
        }
    )
    keyframes.sort(key=lambda item: _safe_int(item.get("slice_index"), 0) or 0)
    payload["keyframes"] = keyframes
    payload["updated_at"] = _now_iso()
    return payload


def delete_keyframe(contours_payload, slice_index, axis="z"):
    payload = dict(contours_payload or {})
    axis = str(axis or "z")
    before = len(payload.get("keyframes", []) or [])
    payload["keyframes"] = [
        item
        for item in _iter_keyframe_records(payload)
        if not (str(item.get("axis", "z")) == axis and _safe_int(item.get("slice_index"), None) == int(slice_index))
    ]
    payload["updated_at"] = _now_iso()
    return payload, before != len(payload.get("keyframes", []) or [])


def keyframe_indices(contours_payload, axis="z"):
    axis = str(axis or "z")
    indices = []
    for item in _iter_keyframe_records(contours_payload):
        if str(item.get("axis", "z")) == axis:
            index = _safe_int(item.get("slice_index"), None)
            if index is not None:
                indices.append(index)
    return sorted(set(indices))


def neighboring_keyframe_indices(contours_payload, current_index, axis="z"):
    indices = keyframe_indices(contours_payload, axis=axis)
    previous_items = [value for value in indices if int(value) < int(current_index)]
    next_items = [value for value in indices if int(value) > int(current_index)]
    return {
        "previous": previous_items[-1] if previous_items else None,
        "next": next_items[0] if next_items else None,
        "indices": indices,
    }


def build_preview_mask_from_contours(contours_payload, shape_zyx):
    report = validate_contours_for_interpolation(contours_payload, shape_zyx, axis="z")
    if not report.get("ok"):
        codes = ",".join(item.get("code", "error") for item in report.get("errors", []))
        raise ValueError(f"invalid_part_contours:{codes}")
    return interpolate_masks_from_keyframes((contours_payload or {}).get("keyframes", []), shape_zyx)


def export_part_package(project_manager, specimen_id, part_id, output_dir):
    specimen = project_manager.get_specimen(specimen_id, default=None)
    part = project_manager.get_part(specimen_id, part_id, default=None)
    if specimen is None or part is None:
        raise KeyError(f"unknown_part:{specimen_id}:{part_id}")
    out_root = os.path.abspath(str(output_dir))
    os.makedirs(out_root, exist_ok=True)
    safe_specimen = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in str(specimen_id or "")).strip("_") or "specimen"
    safe_part = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in str(part_id or "")).strip("_") or "part"
    base_name = f"{safe_specimen}_{safe_part}"
    package_dir = os.path.join(out_root, base_name)
    if os.path.exists(package_dir):
        package_dir = os.path.join(out_root, f"{base_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        suffix = 2
        while os.path.exists(package_dir):
            package_dir = os.path.join(out_root, f"{base_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{suffix}")
            suffix += 1
    os.makedirs(package_dir, exist_ok=True)

    artifacts = {}
    for key, rel_or_record in (
        ("image", (part.get("image") or {}).get("path", "")),
        ("mask", (part.get("mask") or {}).get("path", "")),
        ("contours", part.get("contours_path", "")),
        ("extraction", part.get("extraction_path", "")),
    ):
        source = project_manager.to_absolute(rel_or_record)
        if not source or not os.path.exists(source):
            artifacts[key] = ""
            continue
        target_name = {
            "image": "image.ome.zarr",
            "mask": "mask.ome.zarr",
            "contours": "contours.json",
            "extraction": "extraction.json",
        }[key]
        target = os.path.join(package_dir, target_name)
        if os.path.isdir(source):
            if os.path.exists(target):
                shutil.rmtree(target)
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
        artifacts[key] = target_name

    manifest = {
        "schema_version": f"{TIF_PART_EXTRACTION_VERSION}_export_package",
        "created_at": _now_iso(),
        "specimen_id": str(specimen_id or ""),
        "part_id": str(part_id or ""),
        "display_name": part.get("display_name") or part.get("part_id") or "",
        "parent_bbox_zyx": part.get("parent_bbox_zyx", []),
        "parent_project": os.path.abspath(project_manager.current_project_path or ""),
        "parent_working_volume": ((specimen or {}).get("working_volume") or {}).get("path", ""),
        "status": part.get("status", ""),
        "artifacts": artifacts,
        "notes": [
            "This package is for independent review and archiving of a cropped part volume.",
            "It is not automatically included in full-volume training export.",
        ],
    }
    manifest_path = os.path.join(package_dir, "part_manifest.json")
    write_json(manifest_path, manifest)
    return {
        "package_dir": package_dir,
        "manifest_path": manifest_path,
        "manifest": manifest,
    }


def write_part_mask(project_manager, part, mask):
    mask_path = project_manager.to_absolute(((part or {}).get("mask") or {}).get("path", ""))
    if not mask_path:
        raise ValueError("part_mask_path_missing")
    target = load_volume_sidecar(mask_path, mmap_mode="r+")
    target[:] = np.asarray(mask, dtype=target.dtype)
    return flush_volume_array(mask_path, target)
