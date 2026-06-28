"""Preview-volume builders for TIF/CT volume rendering."""

from __future__ import annotations

import math

import numpy as np


TIF_VOLUME_PREVIEW_VERSION = "taxamask_tif_volume_preview_v1"
DEFAULT_PREVIEW_MAX_SAMPLES = 1_000_000


def preview_factors_for_shape(shape_zyx, max_dim):
    """Return integer downsample factors that keep each dimension under max_dim."""
    shape = tuple(int(value) for value in shape_zyx)
    if len(shape) != 3 or min(shape) <= 0:
        raise ValueError(f"volume_shape_must_be_positive_zyx:{shape}")
    limit = max(1, int(max_dim))
    return tuple(max(1, int(math.ceil(size / float(limit)))) for size in shape)


def preview_shape_for_factors(shape_zyx, factors_zyx):
    shape = tuple(int(value) for value in shape_zyx)
    factors = tuple(max(1, int(value)) for value in factors_zyx)
    if len(shape) != 3 or len(factors) != 3:
        raise ValueError("shape_and_factors_must_be_zyx")
    return tuple(int(math.ceil(size / float(factor))) for size, factor in zip(shape, factors))


def sample_volume_values(volume, max_samples=DEFAULT_PREVIEW_MAX_SAMPLES):
    array = np.asarray(volume)
    if array.size <= int(max_samples):
        return array
    step = max(1, int(math.ceil((float(array.size) / float(max_samples)) ** (1.0 / max(array.ndim, 1)))))
    if array.ndim == 3:
        return array[::step, ::step, ::step]
    return array.reshape(-1)[::step]


def intensity_window_from_sample(volume, lower_percentile=1.0, upper_percentile=99.5):
    sample = np.asarray(sample_volume_values(volume), dtype=np.float32).reshape(-1)
    finite = sample[np.isfinite(sample)]
    if finite.size == 0:
        return 0.0, 0.0
    low = float(np.percentile(finite, float(lower_percentile)))
    high = float(np.percentile(finite, float(upper_percentile)))
    if high <= low:
        low = float(np.min(finite))
        high = float(np.max(finite))
    return low, high


def scale_volume_to_uint8(volume, low, high):
    array = np.asarray(volume)
    if array.size == 0:
        return np.ascontiguousarray(array.astype(np.uint8, copy=False))
    if high <= low:
        return np.zeros(array.shape, dtype=np.uint8)
    scale = 255.0 / max(float(high) - float(low), 1e-6)
    result = np.empty(array.shape, dtype=np.uint8)
    if array.ndim < 3:
        chunk = np.asarray(array, dtype=np.float32)
        chunk = np.clip((chunk - float(low)) * scale, 0.0, 255.0)
        return np.ascontiguousarray(chunk.astype(np.uint8))
    plane_values = max(1, int(np.prod(array.shape[1:])))
    z_chunk = max(1, min(int(array.shape[0]), int((64 * 1024 * 1024) / (plane_values * 4))))
    for z0 in range(0, int(array.shape[0]), z_chunk):
        z1 = min(int(array.shape[0]), z0 + z_chunk)
        chunk = np.asarray(array[z0:z1], dtype=np.float32)
        chunk = np.clip((chunk - float(low)) * scale, 0.0, 255.0)
        result[z0:z1] = chunk.astype(np.uint8)
    return np.ascontiguousarray(result)


def normalize_preview_intensity(volume, preserve_source=False, intensity_window=None):
    if volume is None:
        return None
    source_dtype = np.dtype(getattr(volume, "dtype", np.uint8))
    if preserve_source and source_dtype == np.uint16:
        preview = np.ascontiguousarray(volume)
        return preview if preview.size else None
    if source_dtype == np.uint8:
        preview = np.ascontiguousarray(volume)
        return preview if preview.size else None
    array = np.asarray(volume)
    if array.size == 0:
        return None
    if intensity_window is None:
        low, high = intensity_window_from_sample(array)
    else:
        low, high = (float(intensity_window[0]), float(intensity_window[1]))
    if high <= low:
        return np.zeros(array.shape, dtype=np.uint8)
    return scale_volume_to_uint8(array, low, high)


def downsample_volume(volume, factors_zyx, mode="hybrid", percentile=95.0):
    array = np.asarray(volume)
    if array.ndim != 3:
        raise ValueError(f"volume_must_be_3d:{array.ndim}")
    factors = tuple(max(1, int(value)) for value in factors_zyx)
    if factors == (1, 1, 1):
        return np.ascontiguousarray(array)

    mode = str(mode or "hybrid").lower()
    if mode == "stride":
        return np.ascontiguousarray(array[:: factors[0], :: factors[1], :: factors[2]])

    if mode == "mean":
        result = _block_mean_streaming(array, factors)
    elif mode == "max":
        result = _block_max_streaming(array, factors)
    elif mode == "percentile":
        result = _block_percentile_loop(array, factors, percentile)
    elif mode == "hybrid":
        result = _block_hybrid_streaming(array, factors)
    else:
        raise ValueError(f"unknown_tif_volume_preview_mode:{mode}")

    if np.issubdtype(array.dtype, np.integer) and mode in {"mean", "hybrid", "percentile"}:
        info = np.iinfo(array.dtype)
        result = np.clip(np.rint(result), info.min, info.max).astype(array.dtype)
    return np.ascontiguousarray(result)


def downsample_mask_preview(mask, factors_zyx, mode="occupancy"):
    array = np.asarray(mask)
    if array.ndim != 3:
        raise ValueError(f"mask_must_be_3d:{array.ndim}")
    factors = tuple(max(1, int(value)) for value in factors_zyx)
    if factors == (1, 1, 1):
        return np.ascontiguousarray((array > 0).astype(np.uint8))

    mode = str(mode or "occupancy").lower()
    if mode == "nearest":
        return np.ascontiguousarray((array[:: factors[0], :: factors[1], :: factors[2]] > 0).astype(np.uint8))
    if mode != "occupancy":
        raise ValueError(f"unknown_tif_mask_preview_mode:{mode}")

    mask = array > 0
    result = _block_mask_occupancy_streaming(mask, factors)
    return np.ascontiguousarray(result)


def _reduceat_starts(length, factor):
    return np.arange(0, int(length), max(1, int(factor)), dtype=np.int64)


def _block_mean_streaming(array, factors):
    out_shape = preview_shape_for_factors(array.shape, factors)
    result = np.empty(out_shape, dtype=np.float32)
    zf, yf, xf = factors
    x_starts = _reduceat_starts(array.shape[2], xf)
    for oz, z0 in enumerate(range(0, array.shape[0], zf)):
        z1 = min(array.shape[0], z0 + zf)
        for oy, y0 in enumerate(range(0, array.shape[1], yf)):
            y1 = min(array.shape[1], y0 + yf)
            block = np.asarray(array[z0:z1, y0:y1], dtype=np.float32)
            result[oz, oy] = np.add.reduceat(block, x_starts, axis=2).sum(axis=(0, 1)) / float((z1 - z0) * (y1 - y0) * xf)
            tail_count = int(array.shape[2] - int(x_starts[-1]))
            if tail_count > 0 and tail_count != xf:
                result[oz, oy, -1] *= float(xf) / float(tail_count)
    return result


def _block_max_streaming(array, factors):
    out_shape = preview_shape_for_factors(array.shape, factors)
    result = np.empty(out_shape, dtype=array.dtype)
    zf, yf, xf = factors
    x_starts = _reduceat_starts(array.shape[2], xf)
    for oz, z0 in enumerate(range(0, array.shape[0], zf)):
        z1 = min(array.shape[0], z0 + zf)
        for oy, y0 in enumerate(range(0, array.shape[1], yf)):
            y1 = min(array.shape[1], y0 + yf)
            block = np.asarray(array[z0:z1, y0:y1])
            result[oz, oy] = np.maximum.reduceat(block, x_starts, axis=2).max(axis=(0, 1))
    return result


def _block_hybrid_streaming(array, factors):
    mean_values = _block_mean_streaming(array, factors)
    detail_values = _block_max_streaming(array, factors).astype(np.float32, copy=False)
    return mean_values * 0.65 + detail_values * 0.35


def _block_mask_occupancy_streaming(mask, factors):
    out_shape = preview_shape_for_factors(mask.shape, factors)
    result = np.zeros(out_shape, dtype=np.uint8)
    zf, yf, xf = factors
    x_starts = _reduceat_starts(mask.shape[2], xf)
    for oz, z0 in enumerate(range(0, mask.shape[0], zf)):
        z1 = min(mask.shape[0], z0 + zf)
        for oy, y0 in enumerate(range(0, mask.shape[1], yf)):
            y1 = min(mask.shape[1], y0 + yf)
            block = np.asarray(mask[z0:z1, y0:y1], dtype=np.uint8)
            result[oz, oy] = np.maximum.reduceat(block, x_starts, axis=2).max(axis=(0, 1))
    return result


def _block_percentile_loop(array, factors, percentile):
    out_shape = preview_shape_for_factors(array.shape, factors)
    result = np.empty(out_shape, dtype=np.float32)
    zf, yf, xf = factors
    for oz, z0 in enumerate(range(0, array.shape[0], zf)):
        z1 = min(array.shape[0], z0 + zf)
        for oy, y0 in enumerate(range(0, array.shape[1], yf)):
            y1 = min(array.shape[1], y0 + yf)
            for ox, x0 in enumerate(range(0, array.shape[2], xf)):
                x1 = min(array.shape[2], x0 + xf)
                result[oz, oy, ox] = float(np.percentile(array[z0:z1, y0:y1, x0:x1], float(percentile)))
    return result


def build_volume_preview(
    volume,
    max_dim,
    mode="hybrid",
    preserve_source=False,
    intensity_window=None,
    percentile=95.0,
):
    if volume is None:
        return None
    array = np.asarray(volume)
    if array.ndim != 3 or min(array.shape) <= 0:
        raise ValueError(f"volume_must_be_non_empty_zyx:{array.shape}")
    factors = preview_factors_for_shape(array.shape, max_dim)
    reduced = downsample_volume(array, factors, mode=mode, percentile=percentile)
    return normalize_preview_intensity(reduced, preserve_source=preserve_source, intensity_window=intensity_window)


def build_mask_preview(mask, max_dim, mode="occupancy"):
    if mask is None:
        return None
    array = np.asarray(mask)
    if array.ndim != 3 or min(array.shape) <= 0:
        raise ValueError(f"mask_must_be_non_empty_zyx:{array.shape}")
    factors = preview_factors_for_shape(array.shape, max_dim)
    return downsample_mask_preview(array, factors, mode=mode)


__all__ = [
    "TIF_VOLUME_PREVIEW_VERSION",
    "build_mask_preview",
    "build_volume_preview",
    "downsample_mask_preview",
    "downsample_volume",
    "intensity_window_from_sample",
    "normalize_preview_intensity",
    "preview_factors_for_shape",
    "preview_shape_for_factors",
    "sample_volume_values",
    "scale_volume_to_uint8",
]
