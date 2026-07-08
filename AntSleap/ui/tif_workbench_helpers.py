import math
import os
from datetime import datetime

import numpy as np
import tifffile

try:
    from AntSleap.core.tif_part_extraction import (
        add_rectangular_keyframe,
        build_preview_mask_from_contours,
        validate_contours_for_interpolation,
        write_contours_json,
        write_part_mask,
    )
except ModuleNotFoundError as exc:
    if exc.name != "AntSleap":
        raise
    from core.tif_part_extraction import (
        add_rectangular_keyframe,
        build_preview_mask_from_contours,
        validate_contours_for_interpolation,
        write_contours_json,
        write_part_mask,
    )


def _tif_empty_contours_payload():
    return {
        "schema_version": "taxamask_tif_part_extraction_v1",
        "axis": "z",
        "keyframes": [],
    }


def _tif_clip_bbox_to_shape(bbox, shape):
    clean = []
    shape = tuple(int(value) for value in (shape or ()))
    if len(shape) != 3:
        return []
    for axis, pair in enumerate(bbox or []):
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            return []
        size = int(shape[axis])
        start = max(0, min(size, int(pair[0])))
        end = max(0, min(size, int(pair[1])))
        if end < start:
            start, end = end, start
        if end == start:
            end = min(shape[axis], start + 1)
            start = max(0, end - 1)
        clean.append([start, end])
    return clean if len(clean) == 3 else []


def _tif_bbox_shape(bbox):
    return tuple(int(pair[1]) - int(pair[0]) for pair in (bbox or []))


def _tif_dedupe_contour_points(points, shape=None):
    clean = []
    shape = tuple(int(value) for value in (shape or ()))
    width = int(shape[2]) if len(shape) == 3 else 0
    height = int(shape[1]) if len(shape) == 3 else 0
    for point in points or []:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        try:
            px = float(point[0])
            py = float(point[1])
        except (TypeError, ValueError, OverflowError):
            continue
        if not math.isfinite(px) or not math.isfinite(py):
            continue
        if width > 0:
            px = max(0.0, min(float(width - 1), px))
        if height > 0:
            py = max(0.0, min(float(height - 1), py))
        next_point = [round(px, 3), round(py, 3)]
        if not clean or math.hypot(clean[-1][0] - next_point[0], clean[-1][1] - next_point[1]) >= 0.15:
            clean.append(next_point)
    if len(clean) > 2 and math.hypot(clean[0][0] - clean[-1][0], clean[0][1] - clean[-1][1]) < 0.15:
        clean.pop()
    return clean


def _tif_safe_contour_slice_index(keyframe, default=None):
    try:
        return int((keyframe or {}).get("slice_index", default))
    except (TypeError, ValueError, OverflowError):
        return default


def _tif_full_volume_contours_to_local(contours, bbox, source_shape=None):
    payload = _tif_empty_contours_payload()
    bbox = _tif_clip_bbox_to_shape(bbox, source_shape) if source_shape else [list(pair) for pair in (bbox or [])]
    if not bbox or len(bbox) != 3:
        return payload
    z0, y0, x0 = int(bbox[0][0]), float(bbox[1][0]), float(bbox[2][0])
    keyframes = []
    for keyframe in (contours or {}).get("keyframes", []) or []:
        if not isinstance(keyframe, dict) or str(keyframe.get("axis", "z")) != "z":
            continue
        z_index = _tif_safe_contour_slice_index(keyframe, None)
        if z_index is None:
            continue
        local_polygon = []
        for point in _tif_dedupe_contour_points(keyframe.get("polygon") or [], source_shape):
            local_polygon.append([round(float(point[0]) - x0, 3), round(float(point[1]) - y0, 3)])
        if len(local_polygon) < 3:
            continue
        keyframes.append(
            {
                "axis": "z",
                "slice_index": int(z_index) - z0,
                "polygon": local_polygon,
                "author": str(keyframe.get("author") or "taxamask_ui_freehand"),
                "source": str(keyframe.get("source") or "manual_freehand"),
                "created_at": str(keyframe.get("created_at") or datetime.now().astimezone().isoformat(timespec="seconds")),
            }
        )
    keyframes.sort(key=lambda item: int(item.get("slice_index", 0)))
    payload["keyframes"] = keyframes
    return payload


def _tif_normalize_roi_keyframes(keyframes, shape=None):
    shape = tuple(int(value) for value in (shape or ()))
    normalized = []
    for item in keyframes or []:
        if not isinstance(item, dict):
            continue
        axis = str(item.get("axis") or "z")
        if axis not in {"z", "y", "x"}:
            continue
        try:
            slice_index = int(item.get("slice_index"))
            rect = [int(value) for value in item.get("rect", [])]
        except Exception:
            continue
        if len(rect) != 4:
            continue
        x0, y0, x1, y1 = rect
        if len(shape) == 3:
            if axis == "z":
                max_slice, height, width = shape[0], shape[1], shape[2]
            elif axis == "y":
                max_slice, height, width = shape[1], shape[0], shape[2]
            else:
                max_slice, height, width = shape[2], shape[0], shape[1]
            if not (0 <= slice_index < max_slice):
                continue
            x0, x1 = sorted((max(0, min(width, x0)), max(0, min(width, x1))))
            y0, y1 = sorted((max(0, min(height, y0)), max(0, min(height, y1))))
        else:
            x0, x1 = sorted((x0, x1))
            y0, y1 = sorted((y0, y1))
        if x1 <= x0 or y1 <= y0:
            continue
        normalized.append(
            {
                "axis": axis,
                "slice_index": slice_index,
                "rect": [x0, y0, x1, y1],
                "source": str(item.get("source") or "manual_rectangle"),
            }
        )
    normalized.sort(key=lambda item: (item["axis"], item["slice_index"]))
    return normalized


def _tif_roi_keyframes_to_part_contours(keyframes, parent_bbox, source_shape=None):
    bbox = _tif_clip_bbox_to_shape(parent_bbox, source_shape) if source_shape else [list(pair) for pair in (parent_bbox or [])]
    contours = _tif_empty_contours_payload()
    if not bbox or len(bbox) != 3:
        return contours
    for item in _tif_normalize_roi_keyframes(keyframes, source_shape):
        if item.get("axis") != "z":
            continue
        slice_index = int(item.get("slice_index"))
        if not (int(bbox[0][0]) <= slice_index < int(bbox[0][1])):
            continue
        x0, y0, x1, y1 = [int(value) for value in item.get("rect", [])]
        local_z = slice_index - int(bbox[0][0])
        local_y0 = y0 - int(bbox[1][0])
        local_y1 = y1 - int(bbox[1][0])
        local_x0 = x0 - int(bbox[2][0])
        local_x1 = x1 - int(bbox[2][0])
        contours = add_rectangular_keyframe(
            contours,
            local_z,
            [[local_y0, local_y1], [local_x0, local_x1]],
            author="taxamask_roi_shell",
        )
    return contours


def _tif_roi_shell_mask_from_keyframes(keyframes, parent_bbox, source_shape):
    keyframes = _tif_normalize_roi_keyframes(keyframes, source_shape)
    axes = sorted({item["axis"] for item in keyframes})
    if len(axes) != 1:
        return None
    axis = axes[0]
    bbox = _tif_clip_bbox_to_shape(parent_bbox, source_shape)
    shape = _tif_bbox_shape(bbox)
    if len(shape) != 3 or min(shape) <= 0:
        return None
    local_frames = []
    for item in keyframes:
        if item["axis"] != axis:
            continue
        slice_index = int(item["slice_index"])
        x0, y0, x1, y1 = [int(value) for value in item["rect"]]
        if axis == "z":
            local_slice = slice_index - int(bbox[0][0])
            rect = [x0 - int(bbox[2][0]), y0 - int(bbox[1][0]), x1 - int(bbox[2][0]), y1 - int(bbox[1][0])]
            slice_count, height, width = shape[0], shape[1], shape[2]
        elif axis == "y":
            local_slice = slice_index - int(bbox[1][0])
            rect = [x0 - int(bbox[2][0]), y0 - int(bbox[0][0]), x1 - int(bbox[2][0]), y1 - int(bbox[0][0])]
            slice_count, height, width = shape[1], shape[0], shape[2]
        else:
            local_slice = slice_index - int(bbox[2][0])
            rect = [x0 - int(bbox[1][0]), y0 - int(bbox[0][0]), x1 - int(bbox[1][0]), y1 - int(bbox[0][0])]
            slice_count, height, width = shape[2], shape[0], shape[1]
        if not (0 <= local_slice < slice_count):
            continue
        rect[0] = max(0, min(width, rect[0]))
        rect[2] = max(0, min(width, rect[2]))
        rect[1] = max(0, min(height, rect[1]))
        rect[3] = max(0, min(height, rect[3]))
        if rect[2] <= rect[0] or rect[3] <= rect[1]:
            continue
        local_frames.append((int(local_slice), rect))
    if not local_frames:
        return None
    local_frames.sort(key=lambda item: item[0])
    mask = np.zeros(shape, dtype=np.uint16)

    def fill_slice(slice_index, rect_values):
        x0, y0, x1, y1 = [int(value) for value in rect_values]
        if x1 <= x0 or y1 <= y0:
            return
        if axis == "z":
            mask[int(slice_index), y0:y1, x0:x1] = 1
        elif axis == "y":
            mask[y0:y1, int(slice_index), x0:x1] = 1
        else:
            mask[y0:y1, x0:x1, int(slice_index)] = 1

    for idx, (slice_index, rect) in enumerate(local_frames):
        fill_slice(slice_index, rect)
        if idx + 1 >= len(local_frames):
            continue
        next_slice, next_rect = local_frames[idx + 1]
        span = int(next_slice) - int(slice_index)
        if span <= 0:
            continue
        for step in range(1, span):
            weight = float(step) / float(span)
            interp = []
            for left_value, right_value in zip(rect, next_rect):
                interp.append(int(round((1.0 - weight) * float(left_value) + weight * float(right_value))))
            fill_slice(int(slice_index) + step, interp)
    return mask


def _tif_format_contour_quality_report(report):
    if not isinstance(report, dict):
        return ""
    problems = []
    for item in report.get("errors", []) or []:
        problems.append(str(item.get("message") or item.get("code") or "error"))
    for item in report.get("warnings", []) or []:
        problems.append(str(item.get("message") or item.get("code") or "warning"))
    if not problems:
        return "Quality check passed"
    return "Review warnings: " + " | ".join(problems[:4])


def _tif_shape_from_metadata(path):
    try:
        with tifffile.TiffFile(path) as tif:
            shape = getattr(tif.series[0], "shape", ()) if tif.series else ()
        return tuple(int(value) for value in shape) if shape else ()
    except Exception:
        return ()


def _tif_open_reslice_volume_for_review(path):
    if not path or not os.path.exists(path):
        return None, ""
    try:
        return tifffile.memmap(path), ""
    except Exception as exc:
        shape = _tif_shape_from_metadata(path)
        detail = f"{type(exc).__name__}: {exc}"
        if shape:
            return None, f"reslice_tif_not_memory_mappable:{shape}:{detail}"
        return None, f"reslice_tif_not_memory_mappable:{detail}"


def _tif_write_mask_metadata(project_manager, part, mask):
    metadata = write_part_mask(project_manager, part, mask)
    part.setdefault("mask", {}).update(
        {
            "shape_zyx": metadata.get("shape_zyx", []),
            "dtype": metadata.get("dtype", ""),
            "spacing_zyx": metadata.get("spacing_zyx", []),
            "spacing_unit": metadata.get("spacing_unit", "micrometer"),
            "orientation": metadata.get("orientation", "unknown"),
        }
    )
    return metadata


def _tif_initialize_part_mask_from_roi_shell(project_manager, specimen_id, part, roi_keyframes, source_shape):
    if not isinstance(part, dict) or not roi_keyframes:
        return False, ""
    bbox = _tif_clip_bbox_to_shape(part.get("parent_bbox_zyx", []), source_shape)
    shape = _tif_bbox_shape(bbox)
    if len(shape) != 3 or min(shape) <= 0:
        return False, ""
    contours = _tif_roi_keyframes_to_part_contours(roi_keyframes, bbox, source_shape)
    mask = _tif_roi_shell_mask_from_keyframes(roi_keyframes, bbox, source_shape)
    if mask is None or not np.any(np.asarray(mask) > 0):
        report = validate_contours_for_interpolation(contours, shape, axis="z")
        if not report.get("ok"):
            return False, _tif_format_contour_quality_report(report)
        mask = build_preview_mask_from_contours(contours, shape)
        quality = _tif_format_contour_quality_report(report)
    else:
        quality = "rectangular key-slice shell"
    _tif_write_mask_metadata(project_manager, part, mask)
    metadata_payload = part.setdefault("metadata", {})
    metadata_payload["roi_shell_keyframe_count"] = len(_tif_normalize_roi_keyframes(roi_keyframes, source_shape))
    metadata_payload["roi_shell_keyframes"] = _tif_normalize_roi_keyframes(roi_keyframes, source_shape)
    project_manager.update_part_status(specimen_id, part.get("part_id", ""), "mask_preview", save=False)
    project_manager.save_project()
    return True, quality


def _tif_initialize_part_mask_from_full_volume_contours(project_manager, specimen_id, part, contours, bbox, source_shape, accepted_preview_mask=None):
    if not isinstance(part, dict) or not isinstance(contours, dict):
        return False, ""
    bbox = _tif_clip_bbox_to_shape(bbox, source_shape)
    shape = _tif_bbox_shape(bbox)
    if len(shape) != 3 or min(shape) <= 0:
        return False, "invalid contour bbox"
    local_contours = _tif_full_volume_contours_to_local(contours, bbox, source_shape)
    report = validate_contours_for_interpolation(local_contours, shape, axis="z")
    if not report.get("ok"):
        return False, _tif_format_contour_quality_report(report)
    mask = None
    if accepted_preview_mask is not None and tuple(getattr(accepted_preview_mask, "shape", ()) or ()) == tuple(shape):
        mask = accepted_preview_mask
    if mask is None:
        mask = build_preview_mask_from_contours(local_contours, shape)
    _tif_write_mask_metadata(project_manager, part, mask)
    contours_path = project_manager.to_absolute(part.get("contours_path", ""))
    if contours_path:
        write_contours_json(contours_path, local_contours)
    metadata_payload = part.setdefault("metadata", {})
    metadata_payload["full_volume_mask_keyframe_count"] = len(local_contours.get("keyframes", []) or [])
    metadata_payload["full_volume_mask_bbox_zyx"] = bbox
    metadata_payload["full_volume_mask_source"] = "manual_freehand_key_slices"
    project_manager.update_part_status(specimen_id, part.get("part_id", ""), "mask_preview", save=False)
    project_manager.save_project()
    return True, _tif_format_contour_quality_report(report)
