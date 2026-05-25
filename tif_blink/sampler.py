from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .boundary import BoundaryBandConfig, make_boundary_band
from .labels import LabelMapping, encode_label


@dataclass(frozen=True)
class BalancedSliceSamplerConfig:
    enabled: bool = False
    boundary_bias: float = 4.0
    max_boundary_density: float = 0.6
    min_weight: float = 1.0
    replacement: bool = True


def boundary_density(label_slice: np.ndarray, boundary_config: BoundaryBandConfig | None = None) -> float:
    label = np.asarray(label_slice)
    if label.size == 0:
        return 0.0
    band = make_boundary_band(label, boundary_config or BoundaryBandConfig())
    return float(np.count_nonzero(band) / max(1, band.size))


def slice_boundary_densities(dataset) -> list[float]:
    custom = getattr(dataset, "slice_boundary_densities", None)
    if callable(custom):
        return [float(value) for value in custom()]
    densities: list[float] = []
    label_mapping: LabelMapping = dataset.label_mapping
    boundary_config = dataset.config.boundary
    for sample_idx, z_index in getattr(dataset, "index", []):
        sample = dataset.samples[sample_idx]
        label_slice = encode_label(np.asarray(sample.label[z_index]), label_mapping)
        densities.append(boundary_density(label_slice, boundary_config))
    return densities


def sampler_weights_from_densities(
    densities: list[float],
    config: BalancedSliceSamplerConfig | None = None,
) -> np.ndarray:
    cfg = config or BalancedSliceSamplerConfig()
    if not densities:
        return np.asarray([], dtype=np.float64)
    clipped = []
    for value in densities:
        density = max(0.0, float(value))
        if density > float(cfg.max_boundary_density):
            density = 0.0
        clipped.append(density)
    weights = [float(cfg.min_weight) + float(cfg.boundary_bias) * value for value in clipped]
    return np.asarray(weights, dtype=np.float64)


def build_balanced_slice_sampler(dataset, config: BalancedSliceSamplerConfig | None = None):
    cfg = config or BalancedSliceSamplerConfig()
    if not bool(cfg.enabled):
        return None
    from torch.utils.data import WeightedRandomSampler

    weights = sampler_weights_from_densities(slice_boundary_densities(dataset), cfg)
    if int(weights.size) == 0:
        return None
    return WeightedRandomSampler(
        weights=weights,
        num_samples=int(weights.size),
        replacement=bool(cfg.replacement),
    )
