from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class PanelSplitSettings:
    white_threshold: int = 230
    color_tolerance: int = 35
    separator_ratio: float = 0.80
    trim_ratio: float = 0.965
    adaptive_background: bool = True
    adaptive_background_tolerance: int = 42
    adaptive_background_min_brightness: int = 188
    seam_ratio: float = 0.72
    seam_strength: float = 18.0
    min_separator_px: int | None = None
    min_panel_width: int | None = None
    min_panel_height: int | None = None
    max_panels: int = 24
    max_depth: int = 6
    hard_seam_max_pixels: int = 1_400_000


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

    white_mask = _separator_background_mask(rgb, active_settings)
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
    boxes = _unique_sorted_boxes(splitter.split((0, 0, width, height), depth=0))
    boxes = [
        box
        for box in boxes
        if (box[2] - box[0]) >= min_panel_width and (box[3] - box[1]) >= min_panel_height
        and not _is_background_dominated_box(white_mask, box)
    ]
    source = splitter.split_source()
    if len(boxes) > active_settings.max_panels:
        largest = sorted(boxes, key=lambda item: (item[2] - item[0]) * (item[3] - item[1]), reverse=True)
        boxes = _unique_sorted_boxes(largest[: active_settings.max_panels])

    if len(boxes) > 1 and source != "hard_seam_panel_split":
        return _panel_detections_from_boxes(boxes, source)

    if len(boxes) <= 1:
        return []
    if len(boxes) > 2 and not _has_explicit_hard_separator_line(rgb, boxes):
        return []
    return _panel_detections_from_boxes(boxes, source)


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
        smoothed_scores = _smooth_scores(scores, max(1, self.min_separator_px // 2))
        candidate_mask = (scores >= self.settings.separator_ratio) | (
            (smoothed_scores >= self.settings.separator_ratio)
            & (scores >= max(0.0, self.settings.separator_ratio - 0.10))
        )
        groups = _true_runs(candidate_mask)
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
        subimage = self.rgb[y0:y1, x0:x1]
        if subimage.shape[0] < self.min_panel_height or subimage.shape[1] < self.min_panel_width:
            return []
        analysis_rgb, scale_x, scale_y = _downscale_rgb_for_analysis(subimage, self.settings.hard_seam_max_pixels)
        analysis = analysis_rgb.astype(np.float32, copy=False)
        analysis_min_width = max(8, int(round(self.min_panel_width * scale_x)))
        analysis_min_height = max(8, int(round(self.min_panel_height * scale_y)))
        if analysis.shape[0] < analysis_min_height or analysis.shape[1] < analysis_min_width:
            return []

        if axis == 0:
            window = max(3, min(12, int(analysis.shape[0] * 0.015)))
            if analysis.shape[0] <= window * 2:
                return []
            scores, support = _hard_seam_scores(analysis, axis=0, window=window, seam_strength=self.settings.seam_strength)
            span_origin = y0
            span_length = y1 - y0
            scale = scale_y
            min_size = self.min_panel_height
        else:
            window = max(3, min(12, int(analysis.shape[1] * 0.015)))
            if analysis.shape[1] <= window * 2:
                return []
            scores, support = _hard_seam_scores(analysis, axis=1, window=window, seam_strength=self.settings.seam_strength)
            span_origin = x0
            span_length = x1 - x0
            scale = scale_x
            min_size = self.min_panel_width

        if scores.size == 0:
            return []
        robust_floor = float(np.median(scores) + max(10.0, np.std(scores) * 2.5))
        threshold = max(float(self.settings.seam_strength), robust_floor)
        candidate_mask = (scores >= threshold) & (support >= self.settings.seam_ratio)
        groups = _true_runs(candidate_mask)
        edge_margin = max(min_size, int(span_length * 0.08))
        seams: list[int] = []
        for start, end in groups:
            group_scores = scores[start:end]
            if group_scores.size == 0:
                continue
            best_index = int(start + np.argmax(group_scores))
            analysis_pos = window + best_index
            abs_pos = span_origin + int(round(analysis_pos / max(float(scale), 1e-6)))
            abs_pos = max(span_origin + 1, min(span_origin + span_length - 1, abs_pos))
            if abs_pos - span_origin < edge_margin:
                continue
            if span_origin + span_length - abs_pos < edge_margin:
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


def _separator_background_mask(rgb: np.ndarray, settings: PanelSplitSettings) -> np.ndarray:
    near_white = _near_white_mask(rgb, settings.white_threshold, settings.color_tolerance)
    channel_min = rgb.min(axis=2)
    channel_max = rgb.max(axis=2)
    light_neutral = (channel_min >= int(settings.adaptive_background_min_brightness)) & (
        (channel_max - channel_min) <= int(settings.adaptive_background_tolerance)
    )
    if not settings.adaptive_background:
        return near_white | light_neutral

    background = _estimate_light_background_color(rgb, min_brightness=settings.adaptive_background_min_brightness)
    if background is None:
        return near_white | light_neutral

    diff = np.abs(rgb.astype(np.int16) - background.reshape(1, 1, 3).astype(np.int16))
    color_distance = np.max(diff, axis=2)
    adaptive = (color_distance <= int(settings.adaptive_background_tolerance)) & (
        channel_min >= int(settings.adaptive_background_min_brightness)
    )
    return near_white | light_neutral | adaptive


def _estimate_light_background_color(rgb: np.ndarray, min_brightness: int = 188) -> np.ndarray | None:
    height, width = rgb.shape[:2]
    if height <= 0 or width <= 0:
        return None

    edge = max(2, int(min(height, width) * 0.04))
    samples = np.concatenate(
        [
            rgb[:edge, :, :].reshape(-1, 3),
            rgb[-edge:, :, :].reshape(-1, 3),
            rgb[:, :edge, :].reshape(-1, 3),
            rgb[:, -edge:, :].reshape(-1, 3),
        ],
        axis=0,
    )
    if samples.size == 0:
        return None
    brightness = samples.min(axis=1)
    light_samples = samples[brightness >= int(min_brightness)]
    if light_samples.shape[0] < max(20, samples.shape[0] * 0.08):
        return None
    background = np.median(light_samples.astype(np.float32), axis=0)
    if float(background.min()) < float(min_brightness):
        return None
    return background.astype(np.int16)


def _near_white_mask(rgb: np.ndarray, threshold: int, tolerance: int) -> np.ndarray:
    channel_min = rgb.min(axis=2)
    channel_max = rgb.max(axis=2)
    return (channel_min >= int(threshold)) & ((channel_max - channel_min) <= int(tolerance))


def _smooth_scores(scores: np.ndarray, radius: int) -> np.ndarray:
    if scores.size == 0 or radius <= 0:
        return scores
    kernel_size = radius * 2 + 1
    kernel = np.ones(kernel_size, dtype=np.float32) / float(kernel_size)
    return np.convolve(scores.astype(np.float32), kernel, mode="same")


def _downscale_rgb_for_analysis(rgb: np.ndarray, max_pixels: int) -> tuple[np.ndarray, float, float]:
    height, width = rgb.shape[:2]
    if height <= 0 or width <= 0:
        return rgb, 1.0, 1.0
    pixel_count = int(height) * int(width)
    if max_pixels <= 0 or pixel_count <= int(max_pixels):
        return rgb, 1.0, 1.0
    scale = float(max_pixels / float(pixel_count)) ** 0.5
    new_width = max(1, int(round(width * scale)))
    new_height = max(1, int(round(height * scale)))
    resample = Image.Resampling.BILINEAR if hasattr(Image, "Resampling") else Image.BILINEAR
    resized = Image.fromarray(rgb).resize((new_width, new_height), resample=resample)
    return np.asarray(resized.convert("RGB")).copy(), new_width / float(width), new_height / float(height)


def _hard_seam_scores(
    analysis: np.ndarray,
    *,
    axis: int,
    window: int,
    seam_strength: float,
) -> tuple[np.ndarray, np.ndarray]:
    if window <= 0:
        return np.asarray([], dtype=np.float32), np.asarray([], dtype=np.float32)
    if axis == 0:
        length = analysis.shape[0]
    else:
        length = analysis.shape[1]
    if length <= window * 2:
        return np.asarray([], dtype=np.float32), np.asarray([], dtype=np.float32)

    scores: list[float] = []
    support: list[float] = []
    for index in range(window, length - window + 1):
        if axis == 0:
            before = analysis[index - window : index, :, :].mean(axis=0)
            after = analysis[index : index + window, :, :].mean(axis=0)
            diff = np.abs(after - before).mean(axis=1)
        else:
            before = analysis[:, index - window : index, :].mean(axis=1)
            after = analysis[:, index : index + window, :].mean(axis=1)
            diff = np.abs(after - before).mean(axis=1)
        scores.append(float(diff.mean()))
        support.append(float((diff >= float(seam_strength)).mean()))
    return np.asarray(scores, dtype=np.float32), np.asarray(support, dtype=np.float32)


def _is_background_dominated_box(mask: np.ndarray, box: tuple[int, int, int, int], ratio: float = 0.94) -> bool:
    x0, y0, x1, y1 = [int(value) for value in box]
    submask = mask[y0:y1, x0:x1]
    if submask.size == 0:
        return True
    height, width = mask.shape[:2]
    box_width = max(1, x1 - x0)
    box_height = max(1, y1 - y0)
    is_slender = box_width <= max(6, int(width * 0.12)) or box_height <= max(6, int(height * 0.12))
    return bool(is_slender and float(submask.mean()) >= float(ratio))


def _has_explicit_hard_separator_line(rgb: np.ndarray, boxes: list[tuple[int, int, int, int]]) -> bool:
    height, width = rgb.shape[:2]
    boundaries: list[tuple[str, int, int, int]] = []
    for index, first in enumerate(boxes):
        ax0, ay0, ax1, ay1 = [int(value) for value in first]
        for second in boxes[index + 1 :]:
            bx0, by0, bx1, by1 = [int(value) for value in second]
            if abs(ax1 - bx0) <= 2 or abs(bx1 - ax0) <= 2:
                x = int(round((ax1 + bx0) / 2.0)) if abs(ax1 - bx0) <= 2 else int(round((bx1 + ax0) / 2.0))
                y0 = max(ay0, by0)
                y1 = min(ay1, by1)
                if y1 - y0 >= max(24, int(height * 0.08)):
                    boundaries.append(("v", x, y0, y1))
            if abs(ay1 - by0) <= 2 or abs(by1 - ay0) <= 2:
                y = int(round((ay1 + by0) / 2.0)) if abs(ay1 - by0) <= 2 else int(round((by1 + ay0) / 2.0))
                x0 = max(ax0, bx0)
                x1 = min(ax1, bx1)
                if x1 - x0 >= max(24, int(width * 0.08)):
                    boundaries.append(("h", y, x0, x1))
    return any(_boundary_has_separator_line(rgb, boundary) for boundary in boundaries)


def _boundary_has_separator_line(rgb: np.ndarray, boundary: tuple[str, int, int, int]) -> bool:
    axis, position, start, end = boundary
    height, width = rgb.shape[:2]
    if end <= start:
        return False

    for offset in range(-2, 3):
        if axis == "v":
            x = int(position) + offset
            if x <= 0 or x >= width - 1:
                continue
            y0 = max(0, int(start))
            y1 = min(height, int(end))
            line = rgb[y0:y1, x : x + 1, :]
            before = rgb[y0:y1, max(0, x - 8) : max(0, x - 3), :]
            after = rgb[y0:y1, min(width, x + 3) : min(width, x + 8), :]
        else:
            y = int(position) + offset
            if y <= 0 or y >= height - 1:
                continue
            x0 = max(0, int(start))
            x1 = min(width, int(end))
            line = rgb[y : y + 1, x0:x1, :]
            before = rgb[max(0, y - 8) : max(0, y - 3), x0:x1, :]
            after = rgb[min(height, y + 3) : min(height, y + 8), x0:x1, :]
        if _line_distinguishes_panels(line, before, after):
            return True
    return False


def _line_distinguishes_panels(line: np.ndarray, before: np.ndarray, after: np.ndarray) -> bool:
    if line.size == 0 or before.size == 0 or after.size == 0:
        return False
    line_mean = line.reshape(-1, 3).astype(np.float32).mean(axis=0)
    before_mean = before.reshape(-1, 3).astype(np.float32).mean(axis=0)
    after_mean = after.reshape(-1, 3).astype(np.float32).mean(axis=0)
    before_distance = float(np.linalg.norm(line_mean - before_mean))
    after_distance = float(np.linalg.norm(line_mean - after_mean))
    return min(before_distance, after_distance) >= 30.0


def _panel_detections_from_boxes(boxes: list[tuple[int, int, int, int]], source: str) -> list[dict[str, Any]]:
    if source == "hard_seam_panel_split":
        confidence = min(0.86, 0.58 + len(boxes) * 0.025)
    elif source == "mixed_separator_panel_split":
        confidence = min(0.94, 0.68 + len(boxes) * 0.025)
    else:
        confidence = min(0.98, 0.74 + len(boxes) * 0.025)
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
