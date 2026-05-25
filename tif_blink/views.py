from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class BlinkViewConfig:
    """Controls how TIF-Blink creates inside/outside boundary-band views."""

    mode: str = "normal"
    fill: str = "zero"
    outside_scale: float = 0.15
    inside_scale: float = 0.15


def _fill_like(image: np.ndarray, fill: str) -> np.ndarray:
    if fill == "mean":
        value = float(np.mean(image)) if image.size else 0.0
        return np.full_like(image, value)
    if fill == "min":
        value = float(np.min(image)) if image.size else 0.0
        return np.full_like(image, value)
    return np.zeros_like(image)


def make_blink_view(image: np.ndarray, boundary_band: np.ndarray, config: BlinkViewConfig | None = None) -> np.ndarray:
    """Return normal, inside-band, or outside-band image view."""

    cfg = config or BlinkViewConfig()
    mode = str(cfg.mode or "normal").strip().lower()
    image_arr = np.asarray(image)
    band = np.asarray(boundary_band, dtype=bool)
    if image_arr.shape[-band.ndim :] != band.shape:
        raise ValueError(f"image_band_shape_mismatch:{image_arr.shape}:{band.shape}")

    if mode == "normal":
        return image_arr.copy()

    fill = _fill_like(image_arr, cfg.fill)
    expanded_band = band
    while expanded_band.ndim < image_arr.ndim:
        expanded_band = np.expand_dims(expanded_band, axis=0)

    if mode in {"inside", "inside_band"}:
        if float(cfg.outside_scale) > 0:
            scaled = image_arr.astype(np.float32) * float(cfg.outside_scale)
            return np.where(expanded_band, image_arr, scaled).astype(image_arr.dtype, copy=False)
        return np.where(expanded_band, image_arr, fill).astype(image_arr.dtype, copy=False)

    if mode in {"outside", "outside_band"}:
        if float(cfg.inside_scale) > 0:
            scaled = image_arr.astype(np.float32) * float(cfg.inside_scale)
            return np.where(expanded_band, scaled, image_arr).astype(image_arr.dtype, copy=False)
        return np.where(expanded_band, fill, image_arr).astype(image_arr.dtype, copy=False)

    raise ValueError(f"unsupported_blink_view_mode:{cfg.mode}")
