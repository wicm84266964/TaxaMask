from __future__ import annotations

from dataclasses import asdict

import torch
from torch import autocast

try:
    from nnunetv2.utilities.helpers import dummy_context
except ModuleNotFoundError:  # pragma: no cover - exercised on machines without nnU-Net v2
    from contextlib import nullcontext as dummy_context

from .boundary3d import BoundaryBand3DConfig
from .losses3d import TifBlink3DLossConfig, tif_blink_grouped_loss_3d
from .views3d import BlinkView3DConfig, make_blink_views_3d

try:
    from nnunetv2.training.nnUNetTrainer.nnUNetTrainer import nnUNetTrainer
except ModuleNotFoundError:  # pragma: no cover - exercised on machines without nnU-Net v2
    nnUNetTrainer = None


class _MissingNnUNetTrainer:
    def __init__(self, *args, **kwargs):
        raise ModuleNotFoundError("nnunetv2 is required to instantiate nnUNetTrainerTifBlink")


BaseTrainer = nnUNetTrainer if nnUNetTrainer is not None else _MissingNnUNetTrainer


class nnUNetTrainerTifBlink(BaseTrainer):
    """nnU-Net v2 trainer prototype with TIF-Blink 3D boundary-weakening loss."""

    tif_blink_boundary_radius_xy: int = 2
    tif_blink_boundary_radius_z: int = 1
    tif_blink_include_background_boundary: bool = False
    tif_blink_outside_scale: float = 0.15
    tif_blink_inside_scale: float = 0.15
    tif_blink_normal_loss_weight: float = 1.0
    tif_blink_inside_boundary_loss_weight: float = 0.7
    tif_blink_outside_loss_weight: float = 0.25
    tif_blink_consistency_weight: float = 0.15
    tif_blink_boundary_weight: float = 2.0
    tif_blink_dice_weight: float = 1.0
    tif_blink_consistency_temperature: float = 1.0

    def _ensure_supported_label_mode(self) -> None:
        label_manager = getattr(self, "label_manager", None)
        if label_manager is not None and getattr(label_manager, "has_regions", False):
            raise NotImplementedError("nnUNetTrainerTifBlink currently supports ordinary multiclass labels, not nnU-Net regions mode")

    def _target_num_classes(self) -> int:
        label_manager = getattr(self, "label_manager", None)
        if label_manager is not None and hasattr(label_manager, "num_segmentation_heads"):
            return int(label_manager.num_segmentation_heads)
        network = getattr(self, "network", None)
        if network is not None:
            for module in reversed(list(network.modules())):
                if hasattr(module, "out_channels"):
                    try:
                        return int(module.out_channels)
                    except (TypeError, ValueError):
                        pass
        raise ValueError("unable_to_determine_num_classes")

    def _blink_view_config(self) -> BlinkView3DConfig:
        return BlinkView3DConfig(
            outside_scale=float(self.tif_blink_outside_scale),
            inside_scale=float(self.tif_blink_inside_scale),
            boundary=BoundaryBand3DConfig(
                radius_xy=int(self.tif_blink_boundary_radius_xy),
                radius_z=int(self.tif_blink_boundary_radius_z),
                include_background_boundary=bool(self.tif_blink_include_background_boundary),
            ),
        )

    def _blink_loss_config(self) -> TifBlink3DLossConfig:
        return TifBlink3DLossConfig(
            num_classes=self._target_num_classes(),
            normal_loss_weight=float(self.tif_blink_normal_loss_weight),
            inside_boundary_loss_weight=float(self.tif_blink_inside_boundary_loss_weight),
            outside_loss_weight=float(self.tif_blink_outside_loss_weight),
            consistency_weight=float(self.tif_blink_consistency_weight),
            dice_weight=float(self.tif_blink_dice_weight),
                boundary_weight=float(self.tif_blink_boundary_weight),
                consistency_temperature=float(self.tif_blink_consistency_temperature),
                ignore_label=self._ignore_label(),
        )

    def _ignore_label(self) -> int | None:
        label_manager = getattr(self, "label_manager", None)
        if label_manager is None or not getattr(label_manager, "has_ignore_label", False):
            return None
        return int(label_manager.ignore_label)

    @staticmethod
    def _select_fullres_target(target: torch.Tensor | list[torch.Tensor] | tuple[torch.Tensor, ...]) -> torch.Tensor:
        if isinstance(target, (list, tuple)):
            target = target[0]
        if target.dim() == 5 and target.shape[1] == 1:
            target = target[:, 0]
        return target

    def _compute_tif_blink_loss(self, data: torch.Tensor, target: torch.Tensor) -> tuple[torch.Tensor, dict[str, float]]:
        self._ensure_supported_label_mode()
        target = self._select_fullres_target(target)
        if data.dim() != 5 or target.dim() != 4:
            raise ValueError(f"expected_bcdhw_and_bdhw:{tuple(data.shape)}:{tuple(target.shape)}")

        target = target.long()
        views, boundary = make_blink_views_3d(data, target, self._blink_view_config())
        batch_size, view_count, channels, depth, height, width = views.shape
        flat_logits = self.network(views.reshape(batch_size * view_count, channels, depth, height, width))
        if isinstance(flat_logits, (list, tuple)):
            flat_logits = flat_logits[0]
        logits_shape = tuple(flat_logits.shape)
        expected_shape = (batch_size * view_count, self._target_num_classes(), depth, height, width)
        if logits_shape != expected_shape:
            raise ValueError(f"unexpected_logits_shape:{logits_shape}:expected:{expected_shape}")
        logits = flat_logits.reshape(batch_size, view_count, self._target_num_classes(), depth, height, width)
        return tif_blink_grouped_loss_3d(logits, target, boundary, self._blink_loss_config())

    def train_step(self, batch: dict) -> dict:
        data = batch["data"]
        target = batch["target"]

        data = data.to(self.device, non_blocking=True)
        if isinstance(target, list):
            target = [i.to(self.device, non_blocking=True) for i in target]
        elif isinstance(target, tuple):
            target = tuple(i.to(self.device, non_blocking=True) for i in target)
        else:
            target = target.to(self.device, non_blocking=True)

        self.optimizer.zero_grad(set_to_none=True)
        with autocast(self.device.type, enabled=True) if self.device.type == "cuda" else dummy_context():
            loss, parts = self._compute_tif_blink_loss(data, target)

        if self.grad_scaler is not None:
            self.grad_scaler.scale(loss).backward()
            self.grad_scaler.unscale_(self.optimizer)
            torch.nn.utils.clip_grad_norm_(self.network.parameters(), 12)
            self.grad_scaler.step(self.optimizer)
            self.grad_scaler.update()
        else:
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.network.parameters(), 12)
            self.optimizer.step()

        out = {"loss": loss.detach().cpu().numpy()}
        for key, value in parts.items():
            out[f"tif_blink_{key}"] = float(value)
        return out

    def tif_blink_config_dict(self) -> dict:
        return {
            "view": asdict(self._blink_view_config()),
            "loss": asdict(self._blink_loss_config()),
        }
