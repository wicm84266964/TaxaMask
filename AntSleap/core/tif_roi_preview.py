"""Read-only high-detail ROI preview helpers for TIF/CT volume rendering."""

from __future__ import annotations

import math

import numpy as np

from .tif_volume_preview import build_mask_preview, build_volume_preview


TIF_ROI_PREVIEW_VERSION = "taxamask_tif_roi_preview_v1"
DEFAULT_ROI_TEXTURE_BUDGET_BYTES = int(1.5 * 1024 * 1024 * 1024)
HIGH_ROI_TEXTURE_BUDGET_BYTES = int(2.5 * 1024 * 1024 * 1024)


def normalize_roi_bbox_zyx(bbox_zyx, shape_zyx):
    shape = tuple(int(value) for value in shape_zyx)
    if len(shape) != 3 or min(shape) <= 0:
        raise ValueError(f"volume_shape_must_be_positive_zyx:{shape}")
    if not isinstance(bbox_zyx, (list, tuple)) or len(bbox_zyx) != 3:
        raise ValueError("roi_bbox_must_have_3_ranges")
    clean = []
    for axis, pair in enumerate(bbox_zyx):
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError("roi_bbox_range_must_have_2_values")
        start = max(0, min(shape[axis], int(pair[0])))
        end = max(0, min(shape[axis], int(pair[1])))
        if end < start:
            start, end = end, start
        if end == start:
            end = min(shape[axis], start + 1)
            start = max(0, end - 1)
        clean.append([start, end])
    return clean


def roi_shape_zyx(bbox_zyx):
    if not isinstance(bbox_zyx, (list, tuple)) or len(bbox_zyx) != 3:
        raise ValueError("roi_bbox_must_have_3_ranges")
    return tuple(max(1, int(pair[1]) - int(pair[0])) for pair in bbox_zyx)


def roi_crop_view(volume, bbox_zyx):
    if volume is None:
        return None
    shape = tuple(int(value) for value in getattr(volume, "shape", ()) or ())
    bbox = normalize_roi_bbox_zyx(bbox_zyx, shape)
    z_range, y_range, x_range = bbox
    return volume[z_range[0] : z_range[1], y_range[0] : y_range[1], x_range[0] : x_range[1]]


def texture_budgeted_max_dim(shape_zyx, dtype, budget_bytes=DEFAULT_ROI_TEXTURE_BUDGET_BYTES, max_texture_dim=4096):
    shape = tuple(int(value) for value in shape_zyx)
    if len(shape) != 3 or min(shape) <= 0:
        raise ValueError(f"volume_shape_must_be_positive_zyx:{shape}")
    itemsize = max(1, int(np.dtype(dtype).itemsize))
    budget_voxels = max(1, int(float(budget_bytes) / float(itemsize)))
    voxel_count = int(shape[0]) * int(shape[1]) * int(shape[2])
    max_dim = max(1, min(int(max_texture_dim), max(shape)))
    if voxel_count <= budget_voxels:
        return max_dim
    scale = (float(budget_voxels) / float(voxel_count)) ** (1.0 / 3.0)
    return max(1, min(max_dim, int(math.floor(max(shape) * scale))))


def build_roi_volume_preview(
    volume,
    bbox_zyx,
    max_dim,
    mode="hybrid",
    preserve_source=True,
    texture_budget_bytes=DEFAULT_ROI_TEXTURE_BUDGET_BYTES,
    max_texture_dim=4096,
):
    crop = roi_crop_view(volume, bbox_zyx)
    if crop is None:
        return None
    bbox = normalize_roi_bbox_zyx(bbox_zyx, getattr(volume, "shape", ()))
    crop_shape = roi_shape_zyx(bbox)
    budget_dim = texture_budgeted_max_dim(
        crop_shape,
        getattr(crop, "dtype", np.uint8),
        budget_bytes=texture_budget_bytes,
        max_texture_dim=max_texture_dim,
    )
    target_dim = max(1, min(int(max_dim), int(budget_dim), int(max_texture_dim)))
    return build_volume_preview(crop, target_dim, mode=mode, preserve_source=preserve_source)


def build_roi_mask_preview(mask, bbox_zyx, max_dim, mode="occupancy", max_texture_dim=4096):
    crop = roi_crop_view(mask, bbox_zyx)
    if crop is None:
        return None
    target_dim = max(1, min(int(max_dim), int(max_texture_dim)))
    return build_mask_preview(crop, target_dim, mode=mode)


__all__ = [
    "DEFAULT_ROI_TEXTURE_BUDGET_BYTES",
    "HIGH_ROI_TEXTURE_BUDGET_BYTES",
    "TIF_ROI_PREVIEW_VERSION",
    "build_roi_mask_preview",
    "build_roi_volume_preview",
    "normalize_roi_bbox_zyx",
    "roi_crop_view",
    "roi_shape_zyx",
    "texture_budgeted_max_dim",
]
