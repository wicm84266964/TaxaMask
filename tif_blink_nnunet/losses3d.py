from __future__ import annotations

from dataclasses import dataclass

import torch
import torch.nn.functional as F


@dataclass(frozen=True)
class TifBlink3DLossConfig:
    num_classes: int
    normal_loss_weight: float = 1.0
    inside_boundary_loss_weight: float = 0.7
    outside_loss_weight: float = 0.25
    consistency_weight: float = 0.15
    dice_weight: float = 1.0
    boundary_weight: float = 2.0
    consistency_temperature: float = 1.0
    ignore_background: bool = True
    ignore_label: int | None = None


def _loss_mask(mask: torch.Tensor | None, reference: torch.Tensor) -> torch.Tensor | None:
    if mask is None:
        return None
    out = mask.to(device=reference.device, dtype=reference.dtype)
    while out.dim() < reference.dim():
        out = out.unsqueeze(1)
    return out


def _combined_voxel_mask(
    mask: torch.Tensor | None,
    target: torch.Tensor,
    reference: torch.Tensor,
    ignore_label: int | None = None,
) -> torch.Tensor | None:
    out = None
    if mask is not None:
        out = mask.to(device=reference.device, dtype=torch.bool)
    if ignore_label is not None:
        valid = target.to(device=reference.device) != int(ignore_label)
        out = valid if out is None else out & valid
    if out is None:
        return None
    return out.to(dtype=reference.dtype)


def _target_for_one_hot(target: torch.Tensor, num_classes: int, ignore_label: int | None = None) -> torch.Tensor:
    target = target.long()
    if ignore_label is not None:
        target = torch.where(target == int(ignore_label), torch.zeros_like(target), target)
    if torch.any((target < 0) | (target >= int(num_classes))):
        min_label = int(target.min().detach().cpu().item())
        max_label = int(target.max().detach().cpu().item())
        raise ValueError(f"target_label_out_of_range:min={min_label}:max={max_label}:classes={int(num_classes)}")
    return target


def masked_cross_entropy_3d(
    logits: torch.Tensor,
    target: torch.Tensor,
    mask: torch.Tensor | None = None,
    ignore_label: int | None = None,
) -> torch.Tensor:
    ignore_index = int(ignore_label) if ignore_label is not None else -100
    ce = F.cross_entropy(logits, target.long(), reduction="none", ignore_index=ignore_index)
    loss_mask = _combined_voxel_mask(mask, target, ce, ignore_label)
    if loss_mask is None:
        return ce.mean()
    return (ce * loss_mask).sum() / torch.clamp(loss_mask.sum(), min=1.0)


def masked_dice_loss_3d(
    logits: torch.Tensor,
    target: torch.Tensor,
    num_classes: int,
    mask: torch.Tensor | None = None,
    ignore_background: bool = True,
    ignore_label: int | None = None,
) -> torch.Tensor:
    probs = torch.softmax(logits, dim=1)
    target_safe = _target_for_one_hot(target.to(device=probs.device), int(num_classes), ignore_label)
    target_1h = F.one_hot(target_safe, num_classes=int(num_classes)).permute(0, 4, 1, 2, 3).to(device=probs.device, dtype=probs.dtype)
    start = 1 if bool(ignore_background) and int(num_classes) > 1 else 0
    probs = probs[:, start:]
    target_1h = target_1h[:, start:]
    loss_mask = _loss_mask(_combined_voxel_mask(mask, target, probs[:, 0], ignore_label), probs)
    if loss_mask is not None:
        probs = probs * loss_mask
        target_1h = target_1h * loss_mask
    dims = (0, 2, 3, 4)
    intersection = torch.sum(probs * target_1h, dims)
    denom = torch.sum(probs + target_1h, dims)
    valid = denom > 1e-6
    if not torch.any(valid):
        return torch.zeros((), device=logits.device, dtype=logits.dtype)
    dice = (2.0 * intersection[valid] + 1.0) / (denom[valid] + 1.0)
    return 1.0 - dice.mean()


def boundary_weighted_cross_entropy_3d(
    logits: torch.Tensor,
    target: torch.Tensor,
    boundary: torch.Tensor,
    boundary_weight: float = 2.0,
    ignore_label: int | None = None,
) -> torch.Tensor:
    ignore_index = int(ignore_label) if ignore_label is not None else -100
    ce = F.cross_entropy(logits, target.long(), reduction="none", ignore_index=ignore_index)
    band = boundary.to(device=ce.device, dtype=ce.dtype)
    weights = torch.ones_like(ce) + band * float(boundary_weight)
    valid = _combined_voxel_mask(None, target, ce, ignore_label)
    if valid is not None:
        weights = weights * valid
    return (ce * weights).sum() / torch.clamp(weights.sum(), min=1.0)


def symmetric_kl_consistency_3d(
    logits_a: torch.Tensor,
    logits_b: torch.Tensor,
    mask: torch.Tensor | None = None,
    temperature: float = 1.0,
) -> torch.Tensor:
    temp = max(1e-6, float(temperature))
    prob_a = torch.softmax(logits_a.detach() / temp, dim=1)
    prob_b = torch.softmax(logits_b.detach() / temp, dim=1)
    log_a = torch.log_softmax(logits_a / temp, dim=1)
    log_b = torch.log_softmax(logits_b / temp, dim=1)
    loss = 0.5 * (
        F.kl_div(log_a, prob_b, reduction="none").sum(dim=1)
        + F.kl_div(log_b, prob_a, reduction="none").sum(dim=1)
    )
    if mask is not None:
        loss_mask = mask.to(device=loss.device, dtype=loss.dtype)
        return (loss * loss_mask).sum() / torch.clamp(loss_mask.sum(), min=1.0)
    return loss.mean()


def tif_blink_grouped_loss_3d(
    grouped_logits: torch.Tensor,
    target: torch.Tensor,
    boundary: torch.Tensor,
    config: TifBlink3DLossConfig,
) -> tuple[torch.Tensor, dict[str, float]]:
    if grouped_logits.dim() != 6:
        raise ValueError(f"grouped_logits_must_be_bvcdhw:{tuple(grouped_logits.shape)}")
    normal = grouped_logits[:, 0]
    inside = grouped_logits[:, 1]
    outside = grouped_logits[:, 2]
    band = (boundary > 0).to(device=grouped_logits.device, dtype=grouped_logits.dtype)

    normal_ce = boundary_weighted_cross_entropy_3d(
        normal,
        target,
        boundary,
        boundary_weight=float(config.boundary_weight),
        ignore_label=config.ignore_label,
    )
    normal_dice = masked_dice_loss_3d(
        normal,
        target,
        int(config.num_classes),
        mask=None,
        ignore_background=bool(config.ignore_background),
        ignore_label=config.ignore_label,
    )
    normal_loss = normal_ce + float(config.dice_weight) * normal_dice

    inside_ce = masked_cross_entropy_3d(inside, target, mask=band, ignore_label=config.ignore_label)
    inside_dice = masked_dice_loss_3d(
        inside,
        target,
        int(config.num_classes),
        mask=band,
        ignore_background=bool(config.ignore_background),
        ignore_label=config.ignore_label,
    )
    inside_loss = inside_ce + float(config.dice_weight) * inside_dice

    outside_loss = boundary_weighted_cross_entropy_3d(
        outside,
        target,
        boundary,
        boundary_weight=max(0.0, float(config.boundary_weight) * 0.5),
        ignore_label=config.ignore_label,
    )
    consistency_mask = band
    if config.ignore_label is not None:
        consistency_mask = consistency_mask * (target.to(device=band.device) != int(config.ignore_label)).to(dtype=band.dtype)
    consistency = 0.5 * (
        symmetric_kl_consistency_3d(normal, inside, mask=consistency_mask, temperature=float(config.consistency_temperature))
        + symmetric_kl_consistency_3d(normal, outside, mask=consistency_mask, temperature=float(config.consistency_temperature))
    )
    total = (
        float(config.normal_loss_weight) * normal_loss
        + float(config.inside_boundary_loss_weight) * inside_loss
        + float(config.outside_loss_weight) * outside_loss
        + float(config.consistency_weight) * consistency
    )
    parts = {
        "normal_loss": float(normal_loss.detach().cpu().item()),
        "inside_boundary_loss": float(inside_loss.detach().cpu().item()),
        "outside_loss": float(outside_loss.detach().cpu().item()),
        "consistency_loss": float(consistency.detach().cpu().item()),
        "total_loss": float(total.detach().cpu().item()),
    }
    return total, parts
