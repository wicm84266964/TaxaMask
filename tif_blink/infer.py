from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import torch

from .labels import LabelMapping, decode_label
from .model import TifBlinkUNet2D
from .preprocess import normalize_stack_percentile, slice_stack
from .train import TifBlinkTrainConfig


@dataclass(frozen=True)
class TifBlinkPredictConfig:
    checkpoint_path: str
    device: str = "cpu"
    batch_size: int = 4


def _device(value: str) -> torch.device:
    text = str(value or "cpu").strip().lower()
    if text == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(text)


def _label_mapping_from_payload(payload: dict[str, Any]) -> LabelMapping:
    label_id_to_class = {int(k): int(v) for k, v in payload.get("label_id_to_class", {}).items()}
    class_to_label_id = {int(k): int(v) for k, v in payload.get("class_to_label_id", {}).items()}
    return LabelMapping(label_id_to_class=label_id_to_class, class_to_label_id=class_to_label_id)


def load_checkpoint_model(checkpoint_path: str, device: str = "cpu") -> tuple[TifBlinkUNet2D, TifBlinkTrainConfig, LabelMapping, dict[str, Any]]:
    target_device = _device(device)
    payload = torch.load(str(checkpoint_path), map_location=target_device)
    config = TifBlinkTrainConfig(**payload["train_config"])
    mapping = _label_mapping_from_payload(payload)
    model = TifBlinkUNet2D(
        in_channels=int(config.in_channels),
        num_classes=int(config.num_classes),
        base_channels=int(config.base_channels),
    )
    model.load_state_dict(payload["model_state"])
    model.to(target_device)
    model.eval()
    return model, config, mapping, payload


def infer_volume(
    volume: np.ndarray,
    checkpoint_path: str,
    device: str = "cpu",
    batch_size: int = 4,
) -> np.ndarray:
    arr = np.asarray(volume)
    if arr.ndim != 3:
        raise ValueError(f"volume_must_be_zyx:{arr.shape}")
    model, train_config, mapping, _payload = load_checkpoint_model(checkpoint_path, device=device)
    if bool(train_config.include_boundary_channel):
        raise ValueError("boundary_channel_checkpoint_cannot_run_without_manual_labels")
    target_device = _device(device)
    predicted = np.zeros(arr.shape, dtype=np.int64)

    z_indices = list(range(arr.shape[0]))
    for start in range(0, len(z_indices), int(batch_size)):
        batch_z = z_indices[start : start + int(batch_size)]
        stacks = [
            normalize_stack_percentile(slice_stack(arr, z, train_config.context_slices))
            for z in batch_z
        ]
        images = torch.from_numpy(np.stack(stacks, axis=0).astype(np.float32, copy=False)).to(target_device)
        with torch.no_grad():
            logits = model(images)
            batch_pred = torch.argmax(logits, dim=1).detach().cpu().numpy()
        for offset, z in enumerate(batch_z):
            predicted[z] = batch_pred[offset]

    return decode_label(predicted, mapping, dtype=np.uint16)
