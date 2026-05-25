from __future__ import annotations

import json
import os
import random
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

import numpy as np
import torch
from torch.nn import functional as F
from torch.utils.data import DataLoader

from .dataset import TifBlinkGroupedSliceDataset, TifBlinkSliceDataset
from .labels import LabelMapping
from .losses import (
    boundary_weighted_cross_entropy,
    consistency_loss,
    masked_cross_entropy,
    masked_dice_loss,
    soft_dice_loss,
)
from .metrics import boundary_dice, multiclass_dice
from .model import TifBlinkUNet2D
from .sampler import BalancedSliceSamplerConfig, build_balanced_slice_sampler


TIF_BLINK_MODEL_MANIFEST_SCHEMA_VERSION = "tif_blink_model_manifest_v1"


@dataclass(frozen=True)
class TifBlinkTrainConfig:
    num_classes: int
    in_channels: int
    context_slices: int = 1
    include_boundary_channel: bool = False
    base_channels: int = 32
    epochs: int = 5
    batch_size: int = 2
    learning_rate: float = 1e-3
    boundary_weight: float = 2.0
    dice_weight: float = 1.0
    normal_loss_weight: float = 1.0
    inside_boundary_loss_weight: float = 0.7
    outside_loss_weight: float = 0.25
    consistency_weight: float = 0.15
    consistency_temperature: float = 1.0
    use_grouped_views: bool = False
    use_balanced_sampler: bool = False
    sampler_boundary_bias: float = 4.0
    sampler_max_boundary_density: float = 0.6
    device: str = "cpu"
    num_workers: int = 0
    seed: int = 17
    output_dir: str = ""
    model_name: str = "tif_blink_unet2d"


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _device(value: str) -> torch.device:
    text = str(value or "cpu").strip().lower()
    if text == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(text)


def set_reproducible_seed(seed: int) -> None:
    clean = int(seed)
    random.seed(clean)
    np.random.seed(clean)
    torch.manual_seed(clean)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(clean)


def build_model(config: TifBlinkTrainConfig) -> TifBlinkUNet2D:
    return TifBlinkUNet2D(
        in_channels=int(config.in_channels),
        num_classes=int(config.num_classes),
        base_channels=int(config.base_channels),
    )


def _loss(logits: torch.Tensor, labels: torch.Tensor, boundary: torch.Tensor, config: TifBlinkTrainConfig) -> torch.Tensor:
    ce = boundary_weighted_cross_entropy(
        logits,
        labels,
        boundary=boundary,
        boundary_weight=float(config.boundary_weight),
    )
    dice = soft_dice_loss(logits, labels, num_classes=int(config.num_classes))
    return ce + float(config.dice_weight) * dice


def _loader(dataset, config: TifBlinkTrainConfig, shuffle: bool) -> DataLoader:
    sampler = None
    if bool(config.use_balanced_sampler):
        sampler = build_balanced_slice_sampler(
            dataset,
            BalancedSliceSamplerConfig(
                enabled=True,
                boundary_bias=float(config.sampler_boundary_bias),
                max_boundary_density=float(config.sampler_max_boundary_density),
            ),
        )
    return DataLoader(
        dataset,
        batch_size=int(config.batch_size),
        shuffle=bool(shuffle) if sampler is None else False,
        sampler=sampler,
        num_workers=int(config.num_workers),
        collate_fn=_collate_blink_batch,
    )


def _pad_hw(tensor: torch.Tensor, height: int, width: int, value: float = 0.0) -> torch.Tensor:
    diff_h = int(height) - int(tensor.shape[-2])
    diff_w = int(width) - int(tensor.shape[-1])
    if diff_h == 0 and diff_w == 0:
        return tensor
    return F.pad(tensor, (0, diff_w, 0, diff_h), value=float(value))


def _collate_blink_batch(items: list[dict[str, Any]]) -> dict[str, Any]:
    if not items:
        return {}
    grouped = "images" in items[0]
    image_key = "images" if grouped else "image"
    max_h = max(int(item[image_key].shape[-2]) for item in items)
    max_w = max(int(item[image_key].shape[-1]) for item in items)
    batch: dict[str, Any] = {
        image_key: torch.stack([_pad_hw(item[image_key], max_h, max_w, 0.0) for item in items], dim=0),
        "label": torch.stack([_pad_hw(item["label"], max_h, max_w, 0) for item in items], dim=0),
        "boundary": torch.stack([_pad_hw(item["boundary"], max_h, max_w, 0.0) for item in items], dim=0),
    }
    for key in items[0]:
        if key in batch:
            continue
        values = [item[key] for item in items]
        if all(torch.is_tensor(value) and value.shape == values[0].shape for value in values):
            batch[key] = torch.stack(values, dim=0)
        else:
            batch[key] = values
    return batch


def train_one_epoch(model, dataset, config: TifBlinkTrainConfig) -> float:
    set_reproducible_seed(config.seed)
    loader = _loader(dataset, config, shuffle=True)
    device = _device(config.device)
    model.to(device)
    model.train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=float(config.learning_rate))
    metrics = _run_train_epoch(model, loader, optimizer, config, device)
    return float(metrics["loss"])


def _run_train_epoch(
    model: torch.nn.Module,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    config: TifBlinkTrainConfig,
    device: torch.device,
) -> dict[str, Any]:
    model.train()
    losses: list[float] = []
    dice_values: list[float] = []
    for batch in loader:
        images = batch["image"].to(device)
        labels = batch["label"].to(device)
        boundary = batch["boundary"].to(device)
        optimizer.zero_grad()
        logits = model(images)
        loss = _loss(logits, labels, boundary, config)
        loss.backward()
        optimizer.step()
        losses.append(float(loss.detach().cpu().item()))
        dice_values.append(float(multiclass_dice(logits.detach(), labels, int(config.num_classes))["mean_dice"]))
    return {
        "loss": float(sum(losses) / max(1, len(losses))),
        "mean_dice": float(sum(dice_values) / max(1, len(dice_values))),
    }


def evaluate_model(model, dataset, config: TifBlinkTrainConfig) -> dict[str, Any]:
    loader = _loader(dataset, config, shuffle=False)
    device = _device(config.device)
    model.to(device)
    if _dataset_uses_grouped_views(dataset):
        return _run_grouped_eval_epoch(model, loader, config, device)
    return _run_eval_epoch(model, loader, config, device)


def _is_tif_blink_dataset(dataset: Any) -> bool:
    return (
        hasattr(dataset, "label_mapping")
        and hasattr(dataset, "config")
        and hasattr(dataset, "__len__")
        and hasattr(dataset, "__getitem__")
    )


def _dataset_uses_grouped_views(dataset: Any) -> bool:
    return isinstance(dataset, TifBlinkGroupedSliceDataset) or bool(getattr(dataset, "is_grouped_views", False))


def _run_eval_epoch(
    model: torch.nn.Module,
    loader: DataLoader,
    config: TifBlinkTrainConfig,
    device: torch.device,
) -> dict[str, Any]:
    model.eval()
    losses: list[float] = []
    dice_values: list[float] = []
    per_class_accum: list[list[float]] = []
    with torch.no_grad():
        for batch in loader:
            images = batch["image"].to(device)
            labels = batch["label"].to(device)
            boundary = batch["boundary"].to(device)
            logits = model(images)
            loss = _loss(logits, labels, boundary, config)
            dice = multiclass_dice(logits, labels, int(config.num_classes))
            losses.append(float(loss.detach().cpu().item()))
            dice_values.append(float(dice["mean_dice"]))
            per_class_accum.append([float(value) for value in dice["per_class_dice"]])

    per_class = []
    if per_class_accum:
        width = max(len(item) for item in per_class_accum)
        for idx in range(width):
            values = [item[idx] for item in per_class_accum if idx < len(item)]
            per_class.append(float(sum(values) / max(1, len(values))))
    return {
        "loss": float(sum(losses) / max(1, len(losses))),
        "mean_dice": float(sum(dice_values) / max(1, len(dice_values))),
        "per_class_dice": per_class,
    }


def _view_indices(view_modes: tuple[str, ...] | list[str]) -> dict[str, int]:
    clean = [str(item).strip().lower() for item in view_modes]
    return {
        "normal": clean.index("normal") if "normal" in clean else 0,
        "inside": clean.index("inside_band") if "inside_band" in clean else clean.index("inside") if "inside" in clean else 1,
        "outside": clean.index("outside_band") if "outside_band" in clean else clean.index("outside") if "outside" in clean else 2,
    }


def _grouped_view_loss(
    logits: torch.Tensor,
    labels: torch.Tensor,
    boundary: torch.Tensor,
    view_modes: tuple[str, ...] | list[str],
    config: TifBlinkTrainConfig,
) -> tuple[torch.Tensor, dict[str, float]]:
    indices = _view_indices(view_modes)
    normal = logits[:, indices["normal"]]
    inside = logits[:, indices["inside"]]
    outside = logits[:, indices["outside"]]
    boundary_mask = (boundary > 0).to(device=logits.device, dtype=logits.dtype)

    normal_ce = boundary_weighted_cross_entropy(
        normal,
        labels,
        boundary=boundary,
        boundary_weight=float(config.boundary_weight),
    )
    normal_dice = soft_dice_loss(normal, labels, num_classes=int(config.num_classes))
    normal_loss = normal_ce + float(config.dice_weight) * normal_dice

    inside_ce = masked_cross_entropy(inside, labels, mask=boundary_mask)
    inside_dice = masked_dice_loss(
        inside,
        labels,
        num_classes=int(config.num_classes),
        mask=boundary_mask,
    )
    inside_loss = inside_ce + float(config.dice_weight) * inside_dice

    outside_loss = boundary_weighted_cross_entropy(
        outside,
        labels,
        boundary=boundary,
        boundary_weight=max(0.0, float(config.boundary_weight) * 0.5),
    )
    consistency = (
        consistency_loss(normal, inside, temperature=float(config.consistency_temperature), mask=boundary_mask)
        + consistency_loss(normal, outside, temperature=float(config.consistency_temperature), mask=boundary_mask)
    ) * 0.5

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


def _mean_parts(parts: list[dict[str, float]]) -> dict[str, float]:
    if not parts:
        return {}
    keys = sorted({key for item in parts for key in item})
    return {key: float(sum(item.get(key, 0.0) for item in parts) / len(parts)) for key in keys}


def _run_grouped_train_epoch(
    model: torch.nn.Module,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    config: TifBlinkTrainConfig,
    device: torch.device,
) -> dict[str, Any]:
    model.train()
    losses: list[float] = []
    dice_values: list[float] = []
    boundary_values: list[float] = []
    part_values: list[dict[str, float]] = []
    view_modes = tuple(getattr(loader.dataset, "view_modes", ("normal", "inside_band", "outside_band")))
    for batch in loader:
        images = batch["images"].to(device)
        labels = batch["label"].to(device)
        boundary = batch["boundary"].to(device)
        batch_size, view_count, channels, height, width = images.shape
        optimizer.zero_grad()
        flat_logits = model(images.reshape(batch_size * view_count, channels, height, width))
        logits = flat_logits.reshape(batch_size, view_count, int(config.num_classes), height, width)
        loss, parts = _grouped_view_loss(logits, labels, boundary, view_modes, config)
        loss.backward()
        optimizer.step()

        normal_logits = logits[:, _view_indices(view_modes)["normal"]].detach()
        dice_values.append(float(multiclass_dice(normal_logits, labels, int(config.num_classes))["mean_dice"]))
        boundary_values.append(float(boundary_dice(normal_logits, labels, boundary, int(config.num_classes))["boundary_dice"]))
        losses.append(float(loss.detach().cpu().item()))
        part_values.append(parts)
    metrics = _mean_parts(part_values)
    metrics.update(
        {
            "loss": float(sum(losses) / max(1, len(losses))),
            "mean_dice": float(sum(dice_values) / max(1, len(dice_values))),
            "boundary_dice": float(sum(boundary_values) / max(1, len(boundary_values))),
        }
    )
    return metrics


def _run_grouped_eval_epoch(
    model: torch.nn.Module,
    loader: DataLoader,
    config: TifBlinkTrainConfig,
    device: torch.device,
) -> dict[str, Any]:
    model.eval()
    losses: list[float] = []
    dice_values: list[float] = []
    boundary_values: list[float] = []
    part_values: list[dict[str, float]] = []
    view_modes = tuple(getattr(loader.dataset, "view_modes", ("normal", "inside_band", "outside_band")))
    with torch.no_grad():
        for batch in loader:
            images = batch["images"].to(device)
            labels = batch["label"].to(device)
            boundary = batch["boundary"].to(device)
            batch_size, view_count, channels, height, width = images.shape
            flat_logits = model(images.reshape(batch_size * view_count, channels, height, width))
            logits = flat_logits.reshape(batch_size, view_count, int(config.num_classes), height, width)
            loss, parts = _grouped_view_loss(logits, labels, boundary, view_modes, config)
            normal_logits = logits[:, _view_indices(view_modes)["normal"]]
            dice_values.append(float(multiclass_dice(normal_logits, labels, int(config.num_classes))["mean_dice"]))
            boundary_values.append(float(boundary_dice(normal_logits, labels, boundary, int(config.num_classes))["boundary_dice"]))
            losses.append(float(loss.detach().cpu().item()))
            part_values.append(parts)
    metrics = _mean_parts(part_values)
    metrics.update(
        {
            "loss": float(sum(losses) / max(1, len(losses))),
            "mean_dice": float(sum(dice_values) / max(1, len(dice_values))),
            "boundary_dice": float(sum(boundary_values) / max(1, len(boundary_values))),
        }
    )
    return metrics


def checkpoint_payload(
    model: torch.nn.Module,
    config: TifBlinkTrainConfig,
    label_mapping: LabelMapping,
    epoch: int,
    history: list[dict[str, Any]],
    best_metric: float,
) -> dict[str, Any]:
    return {
        "schema_version": TIF_BLINK_MODEL_MANIFEST_SCHEMA_VERSION,
        "saved_at": _now_iso(),
        "epoch": int(epoch),
        "best_metric": float(best_metric),
        "model_state": model.state_dict(),
        "train_config": asdict(config),
        "label_id_to_class": {int(k): int(v) for k, v in label_mapping.label_id_to_class.items()},
        "class_to_label_id": {int(k): int(v) for k, v in label_mapping.class_to_label_id.items()},
        "history": history,
    }


def save_manifest(
    path: str,
    config: TifBlinkTrainConfig,
    label_mapping: LabelMapping,
    history: list[dict[str, Any]],
    best_checkpoint: str,
    last_checkpoint: str,
    trained_specimens: list[str] | None = None,
) -> dict[str, Any]:
    payload = {
        "schema_version": TIF_BLINK_MODEL_MANIFEST_SCHEMA_VERSION,
        "created_at": _now_iso(),
        "model_name": str(config.model_name),
        "model_family": "tif_blink_unet2d",
        "train_config": asdict(config),
        "label_id_to_class": {str(k): int(v) for k, v in label_mapping.label_id_to_class.items()},
        "class_to_label_id": {str(k): int(v) for k, v in label_mapping.class_to_label_id.items()},
        "num_classes": int(label_mapping.num_classes),
        "checkpoints": {
            "best": os.path.abspath(best_checkpoint),
            "last": os.path.abspath(last_checkpoint),
        },
        "history": history,
        "trained_specimens": list(trained_specimens or []),
        "safety": {
            "input_label_role": "manual_truth",
            "prediction_role": "model_draft",
            "manual_truth_overwritten": False,
            "boundary_channel_default": False,
        },
    }
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return payload


def train_model(
    train_dataset: TifBlinkSliceDataset | TifBlinkGroupedSliceDataset,
    config: TifBlinkTrainConfig,
    val_dataset: TifBlinkSliceDataset | TifBlinkGroupedSliceDataset | None = None,
    model: torch.nn.Module | None = None,
    trained_specimens: list[str] | None = None,
) -> dict[str, Any]:
    if not _is_tif_blink_dataset(train_dataset):
        raise TypeError("train_dataset_must_be_tif_blink_dataset")
    if bool(config.use_grouped_views) and not _dataset_uses_grouped_views(train_dataset):
        raise TypeError("grouped_training_requires_tif_blink_grouped_slice_dataset")
    if not bool(config.use_grouped_views) and _dataset_uses_grouped_views(train_dataset):
        raise TypeError("grouped_dataset_requires_use_grouped_views")
    if int(config.num_classes) != int(train_dataset.label_mapping.num_classes):
        raise ValueError(f"num_classes_label_mapping_mismatch:{config.num_classes}:{train_dataset.label_mapping.num_classes}")
    expected_channels = int(config.context_slices) * 2 + 1
    if bool(config.include_boundary_channel):
        expected_channels += 1
    if int(config.in_channels) != expected_channels:
        raise ValueError(f"in_channels_context_mismatch:{config.in_channels}:{expected_channels}")
    if int(train_dataset.config.context_slices) != int(config.context_slices):
        raise ValueError(f"dataset_context_slices_mismatch:{train_dataset.config.context_slices}:{config.context_slices}")
    if bool(train_dataset.config.include_boundary_channel) != bool(config.include_boundary_channel):
        raise ValueError("dataset_boundary_channel_mismatch")
    if val_dataset is not None:
        if int(val_dataset.config.context_slices) != int(config.context_slices):
            raise ValueError(f"validation_context_slices_mismatch:{val_dataset.config.context_slices}:{config.context_slices}")
        if bool(val_dataset.config.include_boundary_channel) != bool(config.include_boundary_channel):
            raise ValueError("validation_boundary_channel_mismatch")
    set_reproducible_seed(config.seed)
    output_dir = os.path.abspath(config.output_dir or os.path.join(os.getcwd(), "tif_blink_run"))
    os.makedirs(output_dir, exist_ok=True)

    device = _device(config.device)
    net = model or build_model(config)
    net.to(device)
    optimizer = torch.optim.AdamW(net.parameters(), lr=float(config.learning_rate))
    train_loader = _loader(train_dataset, config, shuffle=True)
    val_loader = _loader(val_dataset, config, shuffle=False) if val_dataset is not None else None
    label_mapping = train_dataset.label_mapping

    history: list[dict[str, Any]] = []
    history_path = os.path.join(output_dir, "history.json")
    progress_path = os.path.join(output_dir, "history_progress.jsonl")
    if os.path.exists(progress_path):
        os.remove(progress_path)
    best_metric = -1.0
    best_path = os.path.join(output_dir, "best.pt")
    last_path = os.path.join(output_dir, "last.pt")

    for epoch in range(1, int(config.epochs) + 1):
        if bool(config.use_grouped_views):
            train_metrics = _run_grouped_train_epoch(net, train_loader, optimizer, config, device)
            val_metrics = _run_grouped_eval_epoch(net, val_loader, config, device) if val_loader is not None else {}
        else:
            train_metrics = _run_train_epoch(net, train_loader, optimizer, config, device)
            val_metrics = _run_eval_epoch(net, val_loader, config, device) if val_loader is not None else {}
        metric = float(val_metrics.get("mean_dice", train_metrics.get("mean_dice", 0.0)))
        record = {
            "epoch": epoch,
            "train": train_metrics,
            "validation": val_metrics,
        }
        history.append(record)
        with open(history_path, "w", encoding="utf-8") as handle:
            json.dump(history, handle, ensure_ascii=False, indent=2)
        with open(progress_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(
            json.dumps(
                {
                    "epoch": epoch,
                    "train_loss": train_metrics.get("loss"),
                    "train_mean_dice": train_metrics.get("mean_dice"),
                    "val_loss": val_metrics.get("loss"),
                    "val_mean_dice": val_metrics.get("mean_dice"),
                    "val_boundary_dice": val_metrics.get("boundary_dice"),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

        torch.save(
            checkpoint_payload(net, config, label_mapping, epoch, history, best_metric=max(best_metric, metric)),
            last_path,
        )
        if metric >= best_metric:
            best_metric = metric
            torch.save(
                checkpoint_payload(net, config, label_mapping, epoch, history, best_metric=best_metric),
                best_path,
            )

    if not os.path.exists(best_path):
        torch.save(
            checkpoint_payload(net, config, label_mapping, int(config.epochs), history, best_metric=best_metric),
            best_path,
        )

    with open(history_path, "w", encoding="utf-8") as handle:
        json.dump(history, handle, ensure_ascii=False, indent=2)

    manifest_path = os.path.join(output_dir, "model_manifest.json")
    manifest = save_manifest(
        manifest_path,
        config,
        label_mapping,
        history,
        best_checkpoint=best_path,
        last_checkpoint=last_path,
        trained_specimens=trained_specimens,
    )
    return {
        "model": net,
        "history": history,
        "history_path": history_path,
        "manifest": manifest,
        "manifest_path": manifest_path,
        "best_checkpoint": best_path,
        "last_checkpoint": last_path,
        "best_metric": best_metric,
    }
