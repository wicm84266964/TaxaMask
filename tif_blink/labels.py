from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class LabelMapping:
    """Maps TaxaMask material IDs to compact model class indices."""

    label_id_to_class: dict[int, int]
    class_to_label_id: dict[int, int]

    @property
    def num_classes(self) -> int:
        return len(self.class_to_label_id)


def build_label_mapping(label_arrays: Iterable[np.ndarray], include_background: bool = True) -> LabelMapping:
    ids: set[int] = set()
    for label in label_arrays:
        arr = np.asarray(label)
        if arr.size:
            ids.update(int(value) for value in np.unique(arr))
    if include_background:
        ids.add(0)

    ordered = [0] if 0 in ids else []
    ordered.extend(sorted(value for value in ids if value != 0))
    label_id_to_class = {int(label_id): class_idx for class_idx, label_id in enumerate(ordered)}
    class_to_label_id = {class_idx: int(label_id) for label_id, class_idx in label_id_to_class.items()}
    return LabelMapping(label_id_to_class=label_id_to_class, class_to_label_id=class_to_label_id)


def coerce_label_mapping(label_id_to_class: dict[int, int] | None, label_arrays: Iterable[np.ndarray]) -> LabelMapping:
    if label_id_to_class:
        clean = {int(label_id): int(class_idx) for label_id, class_idx in label_id_to_class.items()}
        class_to_label_id = {class_idx: label_id for label_id, class_idx in clean.items()}
        if sorted(class_to_label_id) != list(range(len(class_to_label_id))):
            raise ValueError("label_mapping_class_indices_must_be_contiguous")
        return LabelMapping(label_id_to_class=clean, class_to_label_id=class_to_label_id)
    return build_label_mapping(label_arrays)


def encode_label(label: np.ndarray, mapping: LabelMapping) -> np.ndarray:
    arr = np.asarray(label)
    out = np.zeros(arr.shape, dtype=np.int64)
    known = np.zeros(arr.shape, dtype=bool)
    for label_id, class_idx in mapping.label_id_to_class.items():
        mask = arr == int(label_id)
        if np.any(mask):
            out[mask] = int(class_idx)
            known |= mask
    if not np.all(known):
        unknown = np.unique(arr[~known])
        raise ValueError(f"unknown_material_ids:{[int(value) for value in unknown[:10]]}")
    return out


def decode_label(encoded: np.ndarray, mapping: LabelMapping, dtype=np.uint16) -> np.ndarray:
    arr = np.asarray(encoded)
    out = np.zeros(arr.shape, dtype=dtype)
    known = np.zeros(arr.shape, dtype=bool)
    for class_idx, label_id in mapping.class_to_label_id.items():
        mask = arr == int(class_idx)
        if np.any(mask):
            out[mask] = int(label_id)
            known |= mask
    if not np.all(known):
        unknown = np.unique(arr[~known])
        raise ValueError(f"unknown_class_indices:{[int(value) for value in unknown[:10]]}")
    return out

