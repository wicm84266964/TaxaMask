from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class PanelSplitSettings:
    white_threshold: int = 230
    color_tolerance: int = 35
    separator_ratio: float = 0.86
    trim_ratio: float = 0.975
    seam_ratio: float = 0.72
    seam_strength: float = 18.0
    min_separator_px: int | None = None
    min_panel_width: int | None = None
    min_panel_height: int | None = None
    max_panels: int = 24
    max_depth: int = 6


def detect_panel_crops(image: str | Image.Image, settings: PanelSplitSettings | None = None) -> list[dict[str, Any]]:
    """Detect figure-panel crop boxes separated by white gutters.

    The detector is intentionally conservative: it only returns crops when at
    least two panel-sized regions are separated by near-white bands.
    """

    active_settings = settings or PanelSplitSettings()
    rgb = _load_rgb_array(image)
    height, width = rgb.shape[:2]
    if width <= 1 or height <= 1:
        return []

    white_mask = _near_white_mask(rgb, active_settings.white_threshold, active_settings.color_tolerance)
    min_panel_width = active_settings.min_panel_width or max(40, int(width * 0.08))
    min_panel_height = active_settings.min_panel_height or max(40, int(height * 0.08))
    min_separator_px = active_settings.min_separator_px or max(3, int(min(width, height) * 0.006))

    splitter = _PanelSplitter(
        rgb=rgb,
        white_mask=white_mask,
        settings=active_settings,
        min_separator_px=min_separator_px,
        min_panel_width=min_panel_width,
        min_panel_height=min_panel_height,
    )
    boxes = splitter.split((0, 0, width, height), depth=0)
    boxes = _unique_sorted_boxes(boxes)
    boxes = [
        box
        for box in boxes
        if (box[2] - box[0]) >= min_panel_width and (box[3] - box[1]) >= min_panel_height
    ]
    if len(boxes) <= 1:
        return []
    if len(boxes) > active_settings.max_panels:
        largest = sorted(boxes, key=lambda item: (item[2] - item[0]) * (item[3] - item[1]), reverse=True)
        boxes = _unique_sorted_boxes(largest[: active_settings.max_panels])

    confidence = min(0.98, 0.72 + len(boxes) * 0.025)
    source = splitter.split_source()
    return [
        {
            "box": [int(x0), int(y0), int(x1), int(y1)],
            "width": int(x1 - x0),
            "height": int(y1 - y0),
            "source": source,
            "confidence": confidence,
        }
        for x0, y0, x1, y1 in boxes
    ]


class _PanelSplitter:
    def __init__(
        self,
        rgb: np.ndarray,
        white_mask: np.ndarray,
        settings: PanelSplitSettings,
        min_separator_px: int,
        min_panel_width: int,
        min_panel_height: int,
    ) -> None:
        self.rgb = rgb
        self.white_mask = white_mask
        self.settings = settings
        self.min_separator_px = int(min_separator_px)
        self.min_panel_width = int(min_panel_width)
        self.min_panel_height = int(min_panel_height)
        self.used_white_separator = False
        self.used_hard_seam = False

    def split_source(self) -> str:
        if self.used_white_separator and self.used_hard_seam:
            return "mixed_separator_panel_split"
        if self.used_hard_seam:
            return "hard_seam_panel_split"
        return "white_separator_panel_split"

    def split(self, region: tuple[int, int, int, int], depth: int) -> list[tuple[int, int, int, int]]:
        x0, y0, x1, y1 = region
        if depth >= self.settings.max_depth:
            trimmed = self._trim_region(region)
            return [trimmed] if self._is_panel_sized(trimmed) else []
        if (x1 - x0) < self.min_panel_width or (y1 - y0) < self.min_panel_height:
            return []

        horizontal_bands = self._separator_bands(region, axis=0)
        horizontal_chunks = self._chunks_from_bands(y0, y1, horizontal_bands, self.min_panel_height)
        if len(horizontal_chunks) >= 2:
            results: list[tuple[int, int, int, int]] = []
            for chunk_start, chunk_end in horizontal_chunks:
                results.extend(self.split((x0, chunk_start, x1, chunk_end), depth + 1))
            if len(results) >= 2:
                self.used_white_separator = True
                return results

        vertical_bands = self._separator_bands(region, axis=1)
        vertical_chunks = self._chunks_from_bands(x0, x1, vertical_bands, self.min_panel_width)
        if len(vertical_chunks) >= 2:
            results = []
            for chunk_start, chunk_end in vertical_chunks:
                results.extend(self.split((chunk_start, y0, chunk_end, y1), depth + 1))
            if len(results) >= 2:
                self.used_white_separator = True
                return results

        horizontal_seams = self._hard_seams(region, axis=0)
        horizontal_chunks = self._chunks_from_seams(y0, y1, horizontal_seams, self.min_panel_height)
        if len(horizontal_chunks) >= 2:
            results = []
            for chunk_start, chunk_end in horizontal_chunks:
                results.extend(self.split((x0, chunk_start, x1, chunk_end), depth + 1))
            if len(results) >= 2:
                self.used_hard_seam = True
                return results

        vertical_seams = self._hard_seams(region, axis=1)
        vertical_chunks = self._chunks_from_seams(x0, x1, vertical_seams, self.min_panel_width)
        if len(vertical_chunks) >= 2:
            results = []
            for chunk_start, chunk_end in vertical_chunks:
                results.extend(self.split((chunk_start, y0, chunk_end, y1), depth + 1))
            if len(results) >= 2:
                self.used_hard_seam = True
                return results

        trimmed = self._trim_region(region)
        return [trimmed] if self._is_panel_sized(trimmed) else []

    def _separator_bands(self, region: tuple[int, int, int, int], axis: int) -> list[tuple[int, int]]:
        x0, y0, x1, y1 = region
        submask = self.white_mask[y0:y1, x0:x1]
        if submask.size == 0:
            return []
        scores = submask.mean(axis=1 if axis == 0 else 0)
        groups = _true_runs(scores >= self.settings.separator_ratio)
        span_start = y0 if axis == 0 else x0
        span_end = y1 if axis == 0 else x1
        span_len = span_end - span_start
        edge_margin = max(self.min_separator_px, int(span_len * 0.015))
        bands: list[tuple[int, int]] = []
        for start, end in groups:
            if end - start < self.min_separator_px:
                continue
            abs_start = span_start + start
            abs_end = span_start + end
            if abs_start - span_start < edge_margin:
                continue
            if span_end - abs_end < edge_margin:
                continue
            bands.append((abs_start, abs_end))
        return bands

    def _chunks_from_bands(
        self,
        start: int,
        end: int,
        bands: list[tuple[int, int]],
        min_size: int,
    ) -> list[tuple[int, int]]:
        chunks: list[tuple[int, int]] = []
        cursor = start
        for band_start, band_end in bands:
            if band_start - cursor >= min_size:
                chunks.append((cursor, band_start))
            cursor = max(cursor, band_end)
        if end - cursor >= min_size:
            chunks.append((cursor, end))
        return chunks

    def _hard_seams(self, region: tuple[int, int, int, int], axis: int) -> list[int]:
        x0, y0, x1, y1 = region
        subimage = self.rgb[y0:y1, x0:x1].astype(np.float32)
        if subimage.shape[0] < self.min_panel_height or subimage.shape[1] < self.min_panel_width:
            return []

        if axis == 0:
            window = max(3, min(12, int(subimage.shape[0] * 0.015)))
            if subimage.shape[0] <= window * 2:
                return []
            upper = np.stack(
                [subimage[index - window : index, :, :].mean(axis=0) for index in range(window, subimage.shape[0] - window + 1)]
            )
            lower = np.stack(
                [subimage[index : index + window, :, :].mean(axis=0) for index in range(window, subimage.shape[0] - window + 1)]
            )
            diff = np.abs(lower - upper).mean(axis=2)
            scores = diff.mean(axis=1)
            support = (diff >= self.settings.seam_strength).mean(axis=1)
            span_start = y0 + window
            span_end = y0 + subimage.shape[0] - window + 1
            min_size = self.min_panel_height
        else:
            window = max(3, min(12, int(subimage.shape[1] * 0.015)))
            if subimage.shape[1] <= window * 2:
                return []
            left = np.stack(
                [subimage[:, index - window : index, :].mean(axis=1) for index in range(window, subimage.shape[1] - window + 1)]
            )
            right = np.stack(
                [subimage[:, index : index + window, :].mean(axis=1) for index in range(window, subimage.shape[1] - window + 1)]
            )
            diff = np.abs(right - left).mean(axis=2)
            scores = diff.mean(axis=1)
            support = (diff >= self.settings.seam_strength).mean(axis=1)
            span_start = x0 + window
            span_end = x0 + subimage.shape[1] - window + 1
            min_size = self.min_panel_width

        if scores.size == 0:
            return []
        robust_floor = float(np.median(scores) + max(10.0, np.std(scores) * 2.5))
        threshold = max(float(self.settings.seam_strength), robust_floor)
        candidate_mask = (scores >= threshold) & (support >= self.settings.seam_ratio)
        groups = _true_runs(candidate_mask)
        edge_margin = max(min_size, int((span_end - span_start) * 0.08))
        seams: list[int] = []
        for start, end in groups:
            group_scores = scores[start:end]
            if group_scores.size == 0:
                continue
            best_index = int(start + np.argmax(group_scores))
            abs_pos = span_start + best_index
            if abs_pos - (span_start - window) < edge_margin:
                continue
            if span_end - abs_pos < edge_margin:
                continue
            seams.append(abs_pos)
        return self._dedupe_seams(seams, min_size)

    def _chunks_from_seams(
        self,
        start: int,
        end: int,
        seams: list[int],
        min_size: int,
    ) -> list[tuple[int, int]]:
        chunks: list[tuple[int, int]] = []
        cursor = start
        for seam in seams:
            if seam - cursor >= min_size:
                chunks.append((cursor, seam))
                cursor = seam
        if end - cursor >= min_size:
            chunks.append((cursor, end))
        return chunks

    def _dedupe_seams(self, seams: list[int], min_size: int) -> list[int]:
        unique: list[int] = []
        min_gap = max(8, int(min_size * 0.2))
        for seam in sorted(seams):
            if not unique or seam - unique[-1] >= min_gap:
                unique.append(seam)
        return unique

    def _trim_region(self, region: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        x0, y0, x1, y1 = region
        submask = self.white_mask[y0:y1, x0:x1]
        if submask.size == 0:
            return region
        row_scores = submask.mean(axis=1)
        col_scores = submask.mean(axis=0)
        top = 0
        bottom = len(row_scores)
        left = 0
        right = len(col_scores)
        while top < bottom and row_scores[top] >= self.settings.trim_ratio:
            top += 1
        while bottom > top and row_scores[bottom - 1] >= self.settings.trim_ratio:
            bottom -= 1
        while left < right and col_scores[left] >= self.settings.trim_ratio:
            left += 1
        while right > left and col_scores[right - 1] >= self.settings.trim_ratio:
            right -= 1
        trimmed = (x0 + left, y0 + top, x0 + right, y0 + bottom)
        return trimmed if self._is_panel_sized(trimmed) else region

    def _is_panel_sized(self, box: tuple[int, int, int, int]) -> bool:
        return (box[2] - box[0]) >= self.min_panel_width and (box[3] - box[1]) >= self.min_panel_height


def _load_rgb_array(image: str | Image.Image) -> np.ndarray:
    if isinstance(image, Image.Image):
        return np.asarray(image.convert("RGB")).copy()
    with Image.open(image) as img:
        return np.asarray(img.convert("RGB")).copy()


def _near_white_mask(rgb: np.ndarray, threshold: int, tolerance: int) -> np.ndarray:
    channel_min = rgb.min(axis=2)
    channel_max = rgb.max(axis=2)
    return (channel_min >= int(threshold)) & ((channel_max - channel_min) <= int(tolerance))


def _true_runs(values: np.ndarray) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for index, value in enumerate(values):
        if bool(value) and start is None:
            start = index
        elif not bool(value) and start is not None:
            runs.append((start, index))
            start = None
    if start is not None:
        runs.append((start, len(values)))
    return runs


def _unique_sorted_boxes(boxes: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
    seen: set[tuple[int, int, int, int]] = set()
    unique: list[tuple[int, int, int, int]] = []
    for box in boxes:
        normalized = tuple(int(v) for v in box)
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    unique.sort(key=lambda item: (item[1], item[0], item[3], item[2]))
    return unique
