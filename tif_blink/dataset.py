from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import torch
from torch.utils.data import Dataset

from .boundary import BoundaryBandConfig, make_boundary_band
from .labels import LabelMapping, coerce_label_mapping, encode_label
from .preprocess import normalize_stack_percentile, slice_stack
from .sample import TifBlinkSample
from .views import BlinkViewConfig, make_blink_view


@dataclass(frozen=True)
class TifBlinkDatasetConfig:
    context_slices: int = 1
    boundary: BoundaryBandConfig = BoundaryBandConfig(radius_xy=5, radius_z=0)
    view_modes: tuple[str, ...] = ("normal", "inside_band", "outside_band")
    include_boundary_channel: bool = False
    label_id_to_class: dict[int, int] | None = None


class TifBlinkSliceDataset(Dataset):
    """2.5D slice dataset for Boundary-Blink experiments."""

    def __init__(self, samples: Sequence[TifBlinkSample], config: TifBlinkDatasetConfig | None = None):
        self.samples = list(samples)
        self.config = config or TifBlinkDatasetConfig()
        self.index: list[tuple[int, int, str]] = []
        label_arrays = []
        for sample_idx, sample in enumerate(self.samples):
            image = np.asarray(sample.image)
            label = np.asarray(sample.label)
            if image.ndim != 3 or label.ndim != 3:
                raise ValueError(f"tif_blink_samples_must_be_zyx:{image.shape}:{label.shape}")
            if image.shape != label.shape:
                raise ValueError(f"image_label_shape_mismatch:{image.shape}:{label.shape}")
            label_arrays.append(label)
            for z in range(image.shape[0]):
                for mode in self.config.view_modes:
                    self.index.append((sample_idx, z, mode))
        self.label_mapping: LabelMapping = coerce_label_mapping(self.config.label_id_to_class, label_arrays)

    def __len__(self) -> int:
        return len(self.index)

    def _slice_stack(self, volume: np.ndarray, z_index: int) -> np.ndarray:
        return slice_stack(volume, z_index, self.config.context_slices)

    def _normalize_stack(self, stack: np.ndarray) -> np.ndarray:
        return normalize_stack_percentile(stack)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor | str]:
        sample_idx, z_index, mode = self.index[idx]
        sample = self.samples[sample_idx]
        image = np.asarray(sample.image)
        label = np.asarray(sample.label)

        label_slice_raw = np.asarray(label[z_index])
        label_slice = encode_label(label_slice_raw, self.label_mapping)
        boundary = make_boundary_band(label_slice, self.config.boundary)
        stack = self._normalize_stack(self._slice_stack(image, z_index))
        view = make_blink_view(stack, boundary, BlinkViewConfig(mode=mode))
        channels = [view]
        if self.config.include_boundary_channel:
            channels.append(boundary.astype(np.float32)[np.newaxis, :, :])
        image_tensor = torch.from_numpy(np.concatenate(channels, axis=0).astype(np.float32, copy=False))

        return {
            "image": image_tensor,
            "label": torch.from_numpy(label_slice.astype(np.int64, copy=False)),
            "boundary": torch.from_numpy(boundary.astype(np.float32, copy=False)),
            "view_mode": mode,
            "specimen_id": sample.specimen_id,
        }


class TifBlinkGroupedSliceDataset(Dataset):
    """Return all Blink views for one 2.5D slice as a single training sample."""

    def __init__(self, samples: Sequence[TifBlinkSample], config: TifBlinkDatasetConfig | None = None):
        self.samples = list(samples)
        self.config = config or TifBlinkDatasetConfig()
        self.view_modes = tuple(self.config.view_modes or ("normal", "inside_band", "outside_band"))
        self.index: list[tuple[int, int]] = []
        label_arrays = []
        for sample_idx, sample in enumerate(self.samples):
            image = np.asarray(sample.image)
            label = np.asarray(sample.label)
            if image.ndim != 3 or label.ndim != 3:
                raise ValueError(f"tif_blink_samples_must_be_zyx:{image.shape}:{label.shape}")
            if image.shape != label.shape:
                raise ValueError(f"image_label_shape_mismatch:{image.shape}:{label.shape}")
            label_arrays.append(label)
            for z in range(image.shape[0]):
                self.index.append((sample_idx, z))
        self.label_mapping: LabelMapping = coerce_label_mapping(self.config.label_id_to_class, label_arrays)

    def __len__(self) -> int:
        return len(self.index)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor | tuple[str, ...] | str]:
        sample_idx, z_index = self.index[idx]
        sample = self.samples[sample_idx]
        image = np.asarray(sample.image)
        label = np.asarray(sample.label)

        label_slice_raw = np.asarray(label[z_index])
        label_slice = encode_label(label_slice_raw, self.label_mapping)
        boundary = make_boundary_band(label_slice, self.config.boundary)
        stack = normalize_stack_percentile(slice_stack(image, z_index, self.config.context_slices))

        views = []
        for mode in self.view_modes:
            view = make_blink_view(stack, boundary, BlinkViewConfig(mode=mode))
            channels = [view]
            if self.config.include_boundary_channel:
                channels.append(boundary.astype(np.float32)[np.newaxis, :, :])
            views.append(np.concatenate(channels, axis=0).astype(np.float32, copy=False))

        return {
            "images": torch.from_numpy(np.stack(views, axis=0).astype(np.float32, copy=False)),
            "label": torch.from_numpy(label_slice.astype(np.int64, copy=False)),
            "boundary": torch.from_numpy(boundary.astype(np.float32, copy=False)),
            "view_modes": self.view_modes,
            "specimen_id": sample.specimen_id,
            "z_index": int(z_index),
        }
