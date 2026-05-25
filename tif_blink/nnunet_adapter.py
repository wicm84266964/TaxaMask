from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch.utils.data import Dataset

from .boundary import BoundaryBandConfig, make_boundary_band
from .labels import LabelMapping, encode_label
from .preprocess import normalize_stack_percentile, slice_stack
from .views import BlinkViewConfig, make_blink_view


@dataclass(frozen=True)
class NnUNetBlinkDatasetConfig:
    preprocessed_root: str
    dataset_dir: str
    plans: str
    configuration: str = "3d_fullres"
    fold: int = 0
    split: str = "train"
    context_slices: int = 1
    boundary: BoundaryBandConfig = BoundaryBandConfig(radius_xy=5, radius_z=0)
    view_modes: tuple[str, ...] = ("normal", "inside_band", "outside_band")
    include_boundary_channel: bool = False
    ignore_label: int | None = -1
    ignore_to_background: bool = True
    renormalize_percentile: bool = True
    grouped_views: bool = False
    patch_size: tuple[int, int] | None = None
    foreground_patch_probability: float = 0.5
    foreground_slices_only: bool = False
    slice_stride: int = 1
    max_cases: int | None = None
    max_slices_per_case: int | None = None
    seed: int = 17


@dataclass(frozen=True)
class NnUNetCaseRecord:
    case_id: str
    image_path: Path
    seg_path: Path
    shape: tuple[int, int, int, int]


def _import_blosc2():
    try:
        import blosc2  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on local env
        raise ModuleNotFoundError(
            "blosc2 is required to read nnU-Net .b2nd preprocessed data. "
            "Use the 3d-brain environment for this adapter."
        ) from exc
    return blosc2


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _resolve_dataset_dir(preprocessed_root: str, dataset_dir: str) -> Path:
    root = Path(preprocessed_root)
    candidate = Path(dataset_dir)
    if candidate.is_absolute():
        resolved = candidate
    else:
        resolved = root / candidate
    if not resolved.exists():
        raise FileNotFoundError(f"nnunet_dataset_dir_not_found:{resolved}")
    return resolved


def _resolve_plans_dir(dataset_dir: Path, plans: str, configuration: str) -> Path:
    plans_path = Path(plans)
    candidates: list[Path] = []
    if plans_path.is_absolute():
        candidates.append(plans_path)
    else:
        candidates.append(dataset_dir / plans)
        suffix = f"_{configuration}" if configuration else ""
        if suffix and not str(plans).endswith(suffix):
            candidates.append(dataset_dir / f"{plans}{suffix}")

    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate
    raise FileNotFoundError(f"nnunet_plans_dir_not_found:{[str(item) for item in candidates]}")


def _label_mapping_from_dataset_json(dataset_json: dict[str, Any]) -> LabelMapping:
    labels = dataset_json.get("labels") or {}
    label_ids: set[int] = set()
    for value in labels.values():
        if isinstance(value, list):
            label_ids.update(int(item) for item in value)
        else:
            label_ids.add(int(value))
    label_ids.add(0)
    ordered = [0]
    ordered.extend(sorted(label_id for label_id in label_ids if label_id != 0))
    label_id_to_class = {int(label_id): idx for idx, label_id in enumerate(ordered)}
    class_to_label_id = {idx: int(label_id) for label_id, idx in label_id_to_class.items()}
    return LabelMapping(label_id_to_class=label_id_to_class, class_to_label_id=class_to_label_id)


def _slice_case_ids(dataset_dir: Path, fold: int, split: str) -> list[str]:
    splits_path = dataset_dir / "splits_final.json"
    if not splits_path.exists():
        raise FileNotFoundError(f"nnunet_splits_not_found:{splits_path}")
    splits = _read_json(splits_path)
    fold_idx = int(fold)
    if fold_idx < 0 or fold_idx >= len(splits):
        raise IndexError(f"nnunet_fold_out_of_range:{fold_idx}:{len(splits)}")
    clean_split = str(split).strip().lower()
    if clean_split not in splits[fold_idx]:
        raise KeyError(f"nnunet_split_not_found:{clean_split}")
    return [str(item) for item in splits[fold_idx][clean_split]]


def _normalize_patch_size(value: tuple[int, int] | None) -> tuple[int, int] | None:
    if value is None:
        return None
    height, width = (int(value[0]), int(value[1]))
    if height <= 0 or width <= 0:
        return None
    return (height, width)


class NnUNetBlinkDataset(Dataset):
    """TIF-Blink dataset backed by nnU-Net preprocessed .b2nd cases."""

    is_grouped_views = False

    def __init__(self, config: NnUNetBlinkDatasetConfig):
        self.config = config
        self.dataset_dir = _resolve_dataset_dir(config.preprocessed_root, config.dataset_dir)
        self.plans_dir = _resolve_plans_dir(self.dataset_dir, config.plans, config.configuration)
        self.dataset_json = _read_json(self.dataset_dir / "dataset.json")
        self.label_mapping = _label_mapping_from_dataset_json(self.dataset_json)
        self.view_modes = tuple(config.view_modes or ("normal", "inside_band", "outside_band"))
        self.is_grouped_views = bool(config.grouped_views)
        self.patch_size = _normalize_patch_size(config.patch_size)
        self._handle_cache: dict[str, Any] = {}

        case_ids = _slice_case_ids(self.dataset_dir, config.fold, config.split)
        if config.max_cases is not None:
            case_ids = case_ids[: max(0, int(config.max_cases))]
        self.cases = self._build_cases(case_ids)
        self.index = self._build_index()

    @property
    def case_ids(self) -> list[str]:
        return [case.case_id for case in self.cases]

    def __getstate__(self) -> dict[str, Any]:
        state = dict(self.__dict__)
        state["_handle_cache"] = {}
        return state

    def _open_array(self, path: Path):
        key = str(path)
        cached = self._handle_cache.get(key)
        if cached is not None:
            return cached
        arr = _import_blosc2().open(key, mode="r")
        if len(self._handle_cache) < 8:
            self._handle_cache[key] = arr
        return arr

    def _build_cases(self, case_ids: list[str]) -> list[NnUNetCaseRecord]:
        blosc2 = _import_blosc2()
        cases: list[NnUNetCaseRecord] = []
        for case_id in case_ids:
            image_path = self.plans_dir / f"{case_id}.b2nd"
            seg_path = self.plans_dir / f"{case_id}_seg.b2nd"
            if not image_path.exists() or not seg_path.exists():
                raise FileNotFoundError(f"nnunet_case_files_missing:{case_id}")
            image = blosc2.open(str(image_path), mode="r")
            seg = blosc2.open(str(seg_path), mode="r")
            shape = tuple(int(value) for value in image.shape)
            seg_shape = tuple(int(value) for value in seg.shape)
            if len(shape) != 4 or shape[0] < 1:
                raise ValueError(f"nnunet_image_shape_must_be_czyx:{case_id}:{shape}")
            if seg_shape != shape:
                raise ValueError(f"nnunet_image_seg_shape_mismatch:{case_id}:{shape}:{seg_shape}")
            cases.append(NnUNetCaseRecord(case_id=case_id, image_path=image_path, seg_path=seg_path, shape=shape))
        return cases

    def _slice_has_foreground(self, case: NnUNetCaseRecord, z_index: int) -> bool:
        seg = self._open_array(case.seg_path)
        label = np.asarray(seg[0, int(z_index)])
        if self.config.ignore_label is not None:
            label = np.where(label == int(self.config.ignore_label), 0, label)
        return bool(np.any(label > 0))

    def _build_index(self) -> list[tuple[int, int] | tuple[int, int, str]]:
        entries: list[tuple[int, int] | tuple[int, int, str]] = []
        stride = max(1, int(self.config.slice_stride))
        max_slices = self.config.max_slices_per_case
        for case_idx, case in enumerate(self.cases):
            z_count = int(case.shape[1])
            z_indices = list(range(0, z_count, stride))
            if self.config.foreground_slices_only:
                z_indices = [z for z in z_indices if self._slice_has_foreground(case, z)]
            if max_slices is not None:
                z_indices = z_indices[: max(0, int(max_slices))]
            if self.is_grouped_views:
                entries.extend((case_idx, int(z)) for z in z_indices)
            else:
                for z in z_indices:
                    for mode in self.view_modes:
                        entries.append((case_idx, int(z), str(mode)))
        return entries

    def __len__(self) -> int:
        return len(self.index)

    def _read_label_slice(self, case: NnUNetCaseRecord, z_index: int) -> np.ndarray:
        label = np.asarray(self._open_array(case.seg_path)[0, int(z_index)])
        if self.config.ignore_label is not None:
            ignore = int(self.config.ignore_label)
            if np.any(label == ignore):
                if not bool(self.config.ignore_to_background):
                    raise ValueError(f"nnunet_ignore_label_present:{case.case_id}:{z_index}:{ignore}")
                label = np.where(label == ignore, 0, label)
        return encode_label(label, self.label_mapping)

    def _slice_stack(self, case: NnUNetCaseRecord, z_index: int) -> np.ndarray:
        image = self._open_array(case.image_path)
        radius = max(0, int(self.config.context_slices))
        z_max = int(case.shape[1]) - 1
        slices = []
        for offset in range(-radius, radius + 1):
            z = max(0, min(z_max, int(z_index) + offset))
            slices.append(np.asarray(image[0, z], dtype=np.float32))
        stack = np.stack(slices, axis=0)
        if bool(self.config.renormalize_percentile):
            return normalize_stack_percentile(stack)
        return stack.astype(np.float32, copy=False)

    def _patch_origin(self, label: np.ndarray, patch_size: tuple[int, int]) -> tuple[int, int]:
        height, width = label.shape
        patch_h, patch_w = patch_size
        max_y = max(0, int(height) - patch_h)
        max_x = max(0, int(width) - patch_w)
        use_foreground = (
            float(self.config.foreground_patch_probability) > 0
            and np.random.random() < float(self.config.foreground_patch_probability)
            and np.any(label > 0)
        )
        if use_foreground:
            ys, xs = np.nonzero(label > 0)
            pick = int(np.random.randint(0, len(ys)))
            center_y, center_x = int(ys[pick]), int(xs[pick])
            y0 = min(max(0, center_y - patch_h // 2), max_y)
            x0 = min(max(0, center_x - patch_w // 2), max_x)
            return int(y0), int(x0)
        y0 = int(np.random.randint(0, max_y + 1)) if max_y > 0 else 0
        x0 = int(np.random.randint(0, max_x + 1)) if max_x > 0 else 0
        return y0, x0

    def _crop_or_pad(self, arr: np.ndarray, y0: int, x0: int, patch_size: tuple[int, int], fill: float = 0) -> np.ndarray:
        patch_h, patch_w = patch_size
        data = np.asarray(arr)
        out_shape = (*data.shape[:-2], patch_h, patch_w)
        out = np.full(out_shape, fill, dtype=data.dtype)
        cropped = data[..., y0 : y0 + patch_h, x0 : x0 + patch_w]
        crop_h, crop_w = cropped.shape[-2:]
        out[..., :crop_h, :crop_w] = cropped
        return out

    def _prepare_slice(self, case: NnUNetCaseRecord, z_index: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        label = self._read_label_slice(case, z_index)
        boundary = make_boundary_band(label, self.config.boundary)
        stack = self._slice_stack(case, z_index)
        if self.patch_size is not None:
            y0, x0 = self._patch_origin(label, self.patch_size)
            stack = self._crop_or_pad(stack, y0, x0, self.patch_size, fill=0)
            label = self._crop_or_pad(label, y0, x0, self.patch_size, fill=0)
            boundary = self._crop_or_pad(boundary, y0, x0, self.patch_size, fill=0)
        return stack, label, boundary

    def _channels_for_view(self, stack: np.ndarray, boundary: np.ndarray, mode: str) -> np.ndarray:
        view = make_blink_view(stack, boundary, BlinkViewConfig(mode=mode))
        channels = [view]
        if self.config.include_boundary_channel:
            channels.append(boundary.astype(np.float32)[np.newaxis, :, :])
        return np.concatenate(channels, axis=0).astype(np.float32, copy=False)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor | str | int | tuple[str, ...]]:
        entry = self.index[int(idx)]
        if self.is_grouped_views:
            case_idx, z_index = entry  # type: ignore[misc]
            case = self.cases[int(case_idx)]
            stack, label, boundary = self._prepare_slice(case, int(z_index))
            views = [self._channels_for_view(stack, boundary, mode) for mode in self.view_modes]
            return {
                "images": torch.from_numpy(np.stack(views, axis=0).astype(np.float32, copy=False)),
                "label": torch.from_numpy(label.astype(np.int64, copy=False)),
                "boundary": torch.from_numpy(boundary.astype(np.float32, copy=False)),
                "view_modes": self.view_modes,
                "specimen_id": case.case_id,
                "z_index": int(z_index),
            }

        case_idx, z_index, mode = entry  # type: ignore[misc]
        case = self.cases[int(case_idx)]
        stack, label, boundary = self._prepare_slice(case, int(z_index))
        return {
            "image": torch.from_numpy(self._channels_for_view(stack, boundary, str(mode))),
            "label": torch.from_numpy(label.astype(np.int64, copy=False)),
            "boundary": torch.from_numpy(boundary.astype(np.float32, copy=False)),
            "view_mode": str(mode),
            "specimen_id": case.case_id,
            "z_index": int(z_index),
        }

    def slice_boundary_densities(self) -> list[float]:
        densities: list[float] = []
        for entry in self.index:
            case_idx, z_index = int(entry[0]), int(entry[1])
            label = self._read_label_slice(self.cases[case_idx], z_index)
            boundary = make_boundary_band(label, self.config.boundary)
            densities.append(float(np.count_nonzero(boundary) / max(1, boundary.size)))
        return densities
