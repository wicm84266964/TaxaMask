from __future__ import annotations

from dataclasses import dataclass

import torch
import torch.nn.functional as F


@dataclass(frozen=True)
class BoundaryBand3DConfig:
    radius_xy: int = 2
    radius_z: int = 1
    include_background_boundary: bool = False


def make_boundary_core_3d(label: torch.Tensor, include_background_boundary: bool = False) -> torch.Tensor:
    arr = label.long()
    if arr.dim() == 3:
        arr = arr.unsqueeze(0)
        squeeze = True
    elif arr.dim() == 4:
        squeeze = False
    else:
        raise ValueError(f"label_must_be_3d_or_batched_3d:{tuple(label.shape)}")

    core = torch.zeros_like(arr, dtype=torch.bool)
    for axis in (1, 2, 3):
        front = [slice(None)] * arr.dim()
        back = [slice(None)] * arr.dim()
        front[axis] = slice(1, None)
        back[axis] = slice(None, -1)
        a = arr[tuple(front)]
        b = arr[tuple(back)]
        diff = a != b
        if not include_background_boundary:
            diff = diff & (a != 0) & (b != 0)
        core_front = [slice(None)] * arr.dim()
        core_back = [slice(None)] * arr.dim()
        core_front[axis] = slice(1, None)
        core_back[axis] = slice(None, -1)
        core[tuple(core_front)] |= diff
        core[tuple(core_back)] |= diff
    return core[0] if squeeze else core


def _ellipsoid_kernel(radius_xy: int, radius_z: int, device: torch.device) -> torch.Tensor:
    rx = max(0, int(radius_xy))
    rz = max(0, int(radius_z))
    z = torch.arange(-rz, rz + 1, device=device, dtype=torch.float32)
    y = torch.arange(-rx, rx + 1, device=device, dtype=torch.float32)
    x = torch.arange(-rx, rx + 1, device=device, dtype=torch.float32)
    zz, yy, xx = torch.meshgrid(z, y, x, indexing="ij")
    if rx == 0 and rz == 0:
        mask = torch.ones((1, 1, 1), dtype=torch.float32, device=device)
    elif rx == 0:
        mask = (torch.abs(zz) <= rz).to(torch.float32)
    elif rz == 0:
        mask = ((yy * yy + xx * xx) <= rx * rx).to(torch.float32)
    else:
        mask = ((zz / max(1, rz)) ** 2 + (yy / max(1, rx)) ** 2 + (xx / max(1, rx)) ** 2 <= 1.0).to(torch.float32)
    return mask.unsqueeze(0).unsqueeze(0)


def make_boundary_band_3d(label: torch.Tensor, config: BoundaryBand3DConfig | None = None) -> torch.Tensor:
    cfg = config or BoundaryBand3DConfig()
    core = make_boundary_core_3d(label, include_background_boundary=bool(cfg.include_background_boundary))
    squeeze = False
    if core.dim() == 3:
        core = core.unsqueeze(0)
        squeeze = True
    if int(cfg.radius_xy) <= 0 and int(cfg.radius_z) <= 0:
        return core[0] if squeeze else core
    kernel = _ellipsoid_kernel(int(cfg.radius_xy), int(cfg.radius_z), core.device)
    pad = (int(cfg.radius_xy), int(cfg.radius_xy), int(cfg.radius_xy), int(cfg.radius_xy), int(cfg.radius_z), int(cfg.radius_z))
    dilated = F.conv3d(F.pad(core.to(torch.float32).unsqueeze(1), pad, mode="replicate"), kernel) > 0
    out = dilated[:, 0]
    return out[0] if squeeze else out

