from __future__ import annotations

from dataclasses import dataclass

import torch

from .boundary3d import BoundaryBand3DConfig, make_boundary_band_3d


@dataclass(frozen=True)
class BlinkView3DConfig:
    outside_scale: float = 0.15
    inside_scale: float = 0.15
    boundary: BoundaryBand3DConfig = BoundaryBand3DConfig()


def make_blink_views_3d(
    image: torch.Tensor,
    label: torch.Tensor,
    config: BlinkView3DConfig | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    cfg = config or BlinkView3DConfig()
    if image.dim() != 5:
        raise ValueError(f"image_must_be_bcdhw:{tuple(image.shape)}")
    if label.dim() != 4:
        raise ValueError(f"label_must_be_bdhw:{tuple(label.shape)}")
    if tuple(image.shape[0:1] + image.shape[2:]) != tuple(label.shape):
        raise ValueError(f"image_label_shape_mismatch:{tuple(image.shape)}:{tuple(label.shape)}")

    boundary = make_boundary_band_3d(label, cfg.boundary)
    band = boundary.to(device=image.device, dtype=torch.bool).unsqueeze(1)
    normal = image
    inside = torch.where(band, image, image * float(cfg.outside_scale))
    outside = torch.where(band, image * float(cfg.inside_scale), image)
    return torch.stack([normal, inside, outside], dim=1), boundary

