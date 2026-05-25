from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class BoundaryBandConfig:
    """Controls boundary-band construction for material-ID labels."""

    radius_xy: int = 5
    radius_z: int = 0
    include_background_boundary: bool = False


def _binary_dilate(mask: np.ndarray, radius_xy: int, radius_z: int) -> np.ndarray:
    mask = np.asarray(mask, dtype=bool)
    if mask.ndim not in {2, 3}:
        raise ValueError(f"boundary_mask_must_be_2d_or_3d:{mask.ndim}")

    radius_xy = max(0, int(radius_xy))
    radius_z = max(0, int(radius_z))
    if radius_xy == 0 and (mask.ndim == 2 or radius_z == 0):
        return mask.copy()

    padded = mask
    if mask.ndim == 2:
        pad = ((radius_xy, radius_xy), (radius_xy, radius_xy))
        padded = np.pad(mask, pad, mode="edge")
        out = np.zeros_like(mask, dtype=bool)
        for dy in range(-radius_xy, radius_xy + 1):
            for dx in range(-radius_xy, radius_xy + 1):
                if dx * dx + dy * dy > radius_xy * radius_xy:
                    continue
                y0 = radius_xy + dy
                x0 = radius_xy + dx
                out |= padded[y0 : y0 + mask.shape[0], x0 : x0 + mask.shape[1]]
        return out

    pad = ((radius_z, radius_z), (radius_xy, radius_xy), (radius_xy, radius_xy))
    padded = np.pad(mask, pad, mode="edge")
    out = np.zeros_like(mask, dtype=bool)
    for dz in range(-radius_z, radius_z + 1):
        for dy in range(-radius_xy, radius_xy + 1):
            for dx in range(-radius_xy, radius_xy + 1):
                if radius_xy > 0 and dx * dx + dy * dy > radius_xy * radius_xy:
                    continue
                z0 = radius_z + dz
                y0 = radius_xy + dy
                x0 = radius_xy + dx
                out |= padded[
                    z0 : z0 + mask.shape[0],
                    y0 : y0 + mask.shape[1],
                    x0 : x0 + mask.shape[2],
                ]
    return out


def make_boundary_core(label: np.ndarray, include_background_boundary: bool = False) -> np.ndarray:
    """Return voxels/pixels that touch a different material ID."""

    arr = np.asarray(label)
    if arr.ndim not in {2, 3}:
        raise ValueError(f"label_must_be_2d_or_3d:{arr.ndim}")

    core = np.zeros(arr.shape, dtype=bool)
    axes = range(arr.ndim)
    for axis in axes:
        front = [slice(None)] * arr.ndim
        back = [slice(None)] * arr.ndim
        front[axis] = slice(1, None)
        back[axis] = slice(None, -1)
        diff = arr[tuple(front)] != arr[tuple(back)]
        if not include_background_boundary:
            non_bg = (arr[tuple(front)] != 0) & (arr[tuple(back)] != 0)
            diff &= non_bg
        core_front = [slice(None)] * arr.ndim
        core_back = [slice(None)] * arr.ndim
        core_front[axis] = slice(1, None)
        core_back[axis] = slice(None, -1)
        core[tuple(core_front)] |= diff
        core[tuple(core_back)] |= diff
    return core


def make_boundary_band(label: np.ndarray, config: BoundaryBandConfig | None = None) -> np.ndarray:
    """Build a boundary uncertainty band from a 2D or 3D material-ID label map."""

    cfg = config or BoundaryBandConfig()
    core = make_boundary_core(
        label,
        include_background_boundary=bool(cfg.include_background_boundary),
    )
    return _binary_dilate(core, cfg.radius_xy, cfg.radius_z)

