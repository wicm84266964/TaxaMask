from __future__ import annotations

try:
    import torch

    from ._nnunet_trainer_impl import nnUNetTrainerTifBlink
except ModuleNotFoundError:

    class nnUNetTrainerTifBlink:  # pragma: no cover - placeholder for non-training environments
        """Placeholder import symbol when PyTorch or nnU-Net v2 is unavailable."""

        def __init__(self, *args, **kwargs):
            raise ModuleNotFoundError("PyTorch and nnU-Net v2 are required to instantiate nnUNetTrainerTifBlink")


__all__ = ["nnUNetTrainerTifBlink"]

