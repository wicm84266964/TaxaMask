from __future__ import annotations

import torch


def boundary_dice_3d(
    logits: torch.Tensor,
    target: torch.Tensor,
    boundary: torch.Tensor,
    num_classes: int,
    ignore_background: bool = True,
) -> dict[str, float | list[float]]:
    prediction = torch.argmax(logits, dim=1)
    band = boundary.to(device=prediction.device, dtype=torch.bool)
    start = 1 if bool(ignore_background) and int(num_classes) > 1 else 0
    per_class: list[float] = []
    for class_idx in range(start, int(num_classes)):
        pred_mask = (prediction == class_idx) & band
        target_mask = (target == class_idx) & band
        denom = pred_mask.sum().item() + target_mask.sum().item()
        if denom == 0:
            per_class.append(1.0)
            continue
        intersection = torch.logical_and(pred_mask, target_mask).sum().item()
        per_class.append(float((2.0 * intersection) / denom))
    mean = float(sum(per_class) / len(per_class)) if per_class else 1.0
    return {"boundary_dice": mean, "per_class_boundary_dice": per_class}

