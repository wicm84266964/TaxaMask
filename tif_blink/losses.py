from __future__ import annotations

import torch
import torch.nn.functional as F


def _as_loss_mask(mask: torch.Tensor | None, reference: torch.Tensor) -> torch.Tensor | None:
    if mask is None:
        return None
    out = mask.to(device=reference.device, dtype=reference.dtype)
    while out.dim() < reference.dim():
        out = out.unsqueeze(0)
    return out


def boundary_weighted_cross_entropy(
    logits: torch.Tensor,
    target: torch.Tensor,
    boundary: torch.Tensor | None = None,
    boundary_weight: float = 2.0,
) -> torch.Tensor:
    """Cross entropy with extra weight on boundary-band pixels."""

    ce = F.cross_entropy(logits, target.long(), reduction="none")
    if boundary is None:
        return ce.mean()
    band = boundary.to(device=ce.device, dtype=ce.dtype)
    while band.dim() < ce.dim():
        band = band.unsqueeze(0)
    weights = torch.ones_like(ce) + band * float(boundary_weight)
    return (ce * weights).sum() / torch.clamp(weights.sum(), min=1.0)


def masked_cross_entropy(
    logits: torch.Tensor,
    target: torch.Tensor,
    mask: torch.Tensor | None = None,
) -> torch.Tensor:
    ce = F.cross_entropy(logits, target.long(), reduction="none")
    loss_mask = _as_loss_mask(mask, ce)
    if loss_mask is None:
        return ce.mean()
    denom = torch.clamp(loss_mask.sum(), min=1.0)
    return (ce * loss_mask).sum() / denom


def soft_dice_loss(logits: torch.Tensor, target: torch.Tensor, num_classes: int, ignore_background: bool = True) -> torch.Tensor:
    probs = torch.softmax(logits, dim=1)
    target_1h = F.one_hot(target.long(), num_classes=num_classes).permute(0, 3, 1, 2).to(dtype=probs.dtype, device=probs.device)
    start = 1 if ignore_background and num_classes > 1 else 0
    probs = probs[:, start:]
    target_1h = target_1h[:, start:]
    dims = (0, 2, 3)
    intersection = torch.sum(probs * target_1h, dims)
    denom = torch.sum(probs + target_1h, dims)
    dice = (2.0 * intersection + 1.0) / (denom + 1.0)
    return 1.0 - dice.mean()


def masked_dice_loss(
    logits: torch.Tensor,
    target: torch.Tensor,
    num_classes: int,
    mask: torch.Tensor | None = None,
    ignore_background: bool = True,
) -> torch.Tensor:
    probs = torch.softmax(logits, dim=1)
    target_1h = F.one_hot(target.long(), num_classes=num_classes).permute(0, 3, 1, 2).to(dtype=probs.dtype, device=probs.device)
    start = 1 if ignore_background and int(num_classes) > 1 else 0
    probs = probs[:, start:]
    target_1h = target_1h[:, start:]
    if mask is not None:
        loss_mask = mask.to(device=probs.device, dtype=probs.dtype)
        while loss_mask.dim() < probs.dim():
            loss_mask = loss_mask.unsqueeze(1)
        probs = probs * loss_mask
        target_1h = target_1h * loss_mask
    dims = (0, 2, 3)
    intersection = torch.sum(probs * target_1h, dims)
    denom = torch.sum(probs + target_1h, dims)
    valid = denom > 1e-6
    if not torch.any(valid):
        return torch.zeros((), device=logits.device, dtype=logits.dtype)
    dice = (2.0 * intersection[valid] + 1.0) / (denom[valid] + 1.0)
    return 1.0 - dice.mean()


def boundary_weighted_dice_loss(
    logits: torch.Tensor,
    target: torch.Tensor,
    boundary: torch.Tensor | None = None,
    num_classes: int | None = None,
    boundary_weight: float = 2.0,
    ignore_background: bool = True,
) -> torch.Tensor:
    classes = int(num_classes or logits.shape[1])
    if boundary is None:
        return soft_dice_loss(logits, target, classes, ignore_background=ignore_background)
    weights = torch.ones_like(target, dtype=logits.dtype, device=logits.device)
    band = boundary.to(device=logits.device, dtype=logits.dtype)
    while band.dim() < weights.dim():
        band = band.unsqueeze(0)
    weights = weights + band * float(boundary_weight)
    probs = torch.softmax(logits, dim=1)
    target_1h = F.one_hot(target.long(), num_classes=classes).permute(0, 3, 1, 2).to(dtype=probs.dtype, device=probs.device)
    start = 1 if ignore_background and classes > 1 else 0
    probs = probs[:, start:]
    target_1h = target_1h[:, start:]
    weights = weights.unsqueeze(1)
    dims = (0, 2, 3)
    intersection = torch.sum(probs * target_1h * weights, dims)
    denom = torch.sum((probs + target_1h) * weights, dims)
    dice = (2.0 * intersection + 1.0) / (denom + 1.0)
    return 1.0 - dice.mean()


def consistency_loss(
    logits_a: torch.Tensor,
    logits_b: torch.Tensor,
    temperature: float = 1.0,
    mask: torch.Tensor | None = None,
) -> torch.Tensor:
    temp = max(1e-6, float(temperature))
    prob_a = torch.softmax(logits_a.detach() / temp, dim=1)
    prob_b = torch.softmax(logits_b.detach() / temp, dim=1)
    log_a = torch.log_softmax(logits_a / temp, dim=1)
    log_b = torch.log_softmax(logits_b / temp, dim=1)
    kl_ab = F.kl_div(log_a, prob_b, reduction="none").sum(dim=1)
    kl_ba = F.kl_div(log_b, prob_a, reduction="none").sum(dim=1)
    loss = 0.5 * (kl_ab + kl_ba)
    loss_mask = _as_loss_mask(mask, loss)
    if loss_mask is not None:
        return (loss * loss_mask).sum() / torch.clamp(loss_mask.sum(), min=1.0)
    return loss.mean()
