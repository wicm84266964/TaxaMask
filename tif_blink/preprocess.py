from __future__ import annotations

import numpy as np


def input_channel_count(context_slices: int, include_boundary_channel: bool = False) -> int:
    context = max(0, int(context_slices))
    channels = context * 2 + 1
    if include_boundary_channel:
        channels += 1
    return channels


def slice_stack(volume: np.ndarray, z_index: int, context_slices: int) -> np.ndarray:
    arr = np.asarray(volume)
    if arr.ndim != 3:
        raise ValueError(f"volume_must_be_zyx:{arr.shape}")
    radius = max(0, int(context_slices))
    z_max = int(arr.shape[0]) - 1
    slices = []
    for offset in range(-radius, radius + 1):
        z = max(0, min(z_max, int(z_index) + offset))
        slices.append(np.asarray(arr[z], dtype=np.float32))
    return np.stack(slices, axis=0)


def normalize_stack_percentile(stack: np.ndarray, low_percentile: float = 1.0, high_percentile: float = 99.0) -> np.ndarray:
    data = np.asarray(stack, dtype=np.float32)
    finite = data[np.isfinite(data)]
    if finite.size == 0:
        return np.zeros_like(data, dtype=np.float32)

    low = float(np.percentile(finite, float(low_percentile)))
    high = float(np.percentile(finite, float(high_percentile)))
    if high <= low:
        high = float(np.max(finite))
        low = float(np.min(finite))
    if high <= low:
        return np.zeros_like(data, dtype=np.float32)
    return np.clip((data - low) / (high - low), 0.0, 1.0).astype(np.float32)

