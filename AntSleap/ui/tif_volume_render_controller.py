from __future__ import annotations

import math
import time
from collections import OrderedDict
from dataclasses import dataclass, field

import numpy as np
from PySide6.QtCore import QEvent, QEventLoop, QObject, Qt, QThread, QTimer
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import QApplication, QColorDialog, QMessageBox, QProgressDialog

try:
    from AntSleap.core.tif_roi_preview import DEFAULT_ROI_TEXTURE_BUDGET_BYTES, HIGH_ROI_TEXTURE_BUDGET_BYTES, build_roi_mask_preview, build_roi_volume_preview, normalize_roi_bbox_zyx, roi_shape_zyx
    from AntSleap.core.tif_volume_io import load_volume_sidecar, volume_sidecar_exists
    from AntSleap.core.tif_volume_preview import build_mask_preview, build_volume_preview, normalize_preview_intensity, scale_volume_to_uint8, sample_volume_values
    from AntSleap.ui.tif_gpu_volume_canvas import GPU_VOLUME_MAX_RAY_STEPS, GPU_VOLUME_MAX_TEXTURE_DIM, TifGpuVolumeCanvas, TifGpuVolumeOffscreenWidget, build_volume_transfer_lut, gpu_volume_canvas_available, gpu_volume_offscreen_available, gpu_volume_unavailable_reason, volume_pan_limit_for_zoom, volume_shader_quality_settings, volume_shape_scale
    from AntSleap.ui.tif_workbench_canvas import LazyRegionMaskVolume, TifVolumeCanvas, create_tif_volume_canvas
    from AntSleap.ui.tif_workbench_style import tif_canvas_background
    from AntSleap.ui.tif_workbench_translations import tt
    from AntSleap.ui.tif_workbench_workers import TifVolumePreviewBuildWorker
except ModuleNotFoundError as exc:
    if exc.name != "AntSleap":
        raise
    from core.tif_roi_preview import DEFAULT_ROI_TEXTURE_BUDGET_BYTES, HIGH_ROI_TEXTURE_BUDGET_BYTES, build_roi_mask_preview, build_roi_volume_preview, normalize_roi_bbox_zyx, roi_shape_zyx
    from core.tif_volume_io import load_volume_sidecar, volume_sidecar_exists
    from core.tif_volume_preview import build_mask_preview, build_volume_preview, normalize_preview_intensity, scale_volume_to_uint8, sample_volume_values
    from ui.tif_gpu_volume_canvas import GPU_VOLUME_MAX_RAY_STEPS, GPU_VOLUME_MAX_TEXTURE_DIM, TifGpuVolumeCanvas, TifGpuVolumeOffscreenWidget, build_volume_transfer_lut, gpu_volume_canvas_available, gpu_volume_offscreen_available, gpu_volume_unavailable_reason, volume_pan_limit_for_zoom, volume_shader_quality_settings, volume_shape_scale
    from ui.tif_workbench_canvas import LazyRegionMaskVolume, TifVolumeCanvas, create_tif_volume_canvas
    from ui.tif_workbench_style import tif_canvas_background
    from ui.tif_workbench_translations import tt
    from ui.tif_workbench_workers import TifVolumePreviewBuildWorker

TIF_VOLUME_CLARITY_PART_FULL_VOXEL_LIMIT = 128_000_000
TIF_VOLUME_CLARITY_PART_HIGH_DIM = 3072
TIF_VOLUME_CLARITY_PART_FULL_DIM = GPU_VOLUME_MAX_TEXTURE_DIM
TIF_VOLUME_MAX_CACHED_SPECIMENS = 3
TIF_VOLUME_MAX_PREVIEW_VARIANTS_PER_OWNER = 8
TIF_VOLUME_HIGH_QUALITY_CACHE_OWNER_LIMIT = 2
TIF_VOLUME_ULTRA_QUALITY_CACHE_OWNER_LIMIT = 1
TIF_GPU_STREAM_SYNC_MAX_BYTES = 32 * 1024 * 1024
TIF_MASK_PREVIEW_TRUSTED_STATUSES = {"mask_preview", "mask_in_progress", "reviewed", "ready_for_labeling", "predicted_pending_review", "train_ready"}

def _tif_canvas_background(theme="dark"):
    return tif_canvas_background(theme)

@dataclass
class TifVolumeRenderState:
    defer_volume_preview_render_once: object = False
    selection_render_pending: object = False
    handling_gpu_volume_failure: object = False
    volume_canvas_renderer: object = "cpu"
    volume_clarity_mode: object = False
    volume_gl_renderer_info: object = ""
    volume_interaction_render_pending: object = False
    volume_interaction_render_scheduled: object = False
    volume_interaction_render_interval_ms: object = 16
    volume_last_preview_build_ms: object = 0.0
    volume_last_stats: object = field(default_factory=dict)
    volume_mask_preview_cache: object = field(default_factory=OrderedDict)
    volume_masked_preview_cache: object = field(default_factory=OrderedDict)
    volume_pan_x: object = 0.0
    volume_pan_y: object = 0.0
    volume_pitch: object = 20.0
    volume_preview: object = None
    volume_preview_build_task_id: object = ""
    volume_preview_build_token: object = 0
    volume_preview_cache: object = field(default_factory=OrderedDict)
    volume_preview_pending_key: object = None
    volume_preview_pending_mask_key: object = None
    volume_preview_pending_message: object = ""
    volume_preview_pending_token: object = 0
    volume_preview_source_shape: object = field(default_factory=tuple)
    volume_preview_ui_wait_depth: object = 0
    volume_quality_committed_value: object = 1024
    volume_quality_drag_pending: object = False
    volume_render_mode: object = "still"
    volume_render_scheduled: object = False
    volume_renderer_warning: object = ""
    volume_roi_preview_bbox: object = None
    volume_roi_preview_source_shape: object = field(default_factory=tuple)
    volume_roi_scale_committed_value: object = 200
    volume_transfer_opacity_drag_pending: object = False
    volume_yaw: object = -35.0
    volume_zoom: object = 1.0
    volume_preview_busy_control_states: object = field(default_factory=list)

class TifVolumeRenderController(QObject):
    VIEW_SCOPE = "volume_render"

    def __init__(self, workbench):
        super().__init__(workbench)
        self.workbench = workbench
        self.state = TifVolumeRenderState()
        self.preview_build_thread = None
        self.preview_build_worker = None

    def bind_signals(self):
        workbench = self.workbench
        view = workbench.workbench_view
        names = (
            "volume_cutoff_slider", "volume_projection_combo", "volume_quality_slider",
            "volume_sample_slider", "volume_clarity_check", "volume_roi_detail_check",
            "volume_roi_source_combo", "volume_roi_inspect_check", "volume_roi_scale_slider",
            "volume_roi_budget_combo", "volume_inside_slider", "volume_clip_slider",
            "volume_tint_combo", "btn_volume_custom_color", "volume_transfer_opacity_slider",
            "volume_enhancement_slider", "volume_tone_slider", "volume_shader_quality_combo",
            "volume_surface_refine_check", "volume_clip_plane_check", "volume_local_axes_check",
            "volume_mask_combo", "volume_mask_opacity_slider", "btn_reset_volume_view",
            "btn_volume_morphology_preset", "volume_clip_plane_depth_slider",
        )
        view.register_scope(self.VIEW_SCOPE, *names)
        bindings = (
            ("cutoff", "volume_cutoff_slider", "valueChanged", self.render_volume_preview),
            ("projection", "volume_projection_combo", "currentIndexChanged", self._on_volume_projection_changed),
            ("quality_press", "volume_quality_slider", "sliderPressed", self._on_volume_quality_drag_started),
            ("quality_move", "volume_quality_slider", "sliderMoved", self._on_volume_quality_drag_moved),
            ("quality_release", "volume_quality_slider", "sliderReleased", self._on_volume_quality_released),
            ("samples", "volume_sample_slider", "valueChanged", self.render_volume_preview),
            ("clarity", "volume_clarity_check", "toggled", self._on_volume_clarity_toggled),
            ("roi_detail", "volume_roi_detail_check", "toggled", self._refresh_volume_preview),
            ("roi_source", "volume_roi_source_combo", "currentIndexChanged", self._refresh_volume_preview),
            ("roi_inspect", "volume_roi_inspect_check", "toggled", self._refresh_volume_preview),
            ("roi_scale_press", "volume_roi_scale_slider", "sliderPressed", self._on_volume_roi_scale_drag_started),
            ("roi_scale_change", "volume_roi_scale_slider", "valueChanged", self._on_volume_roi_scale_changed),
            ("roi_scale_release", "volume_roi_scale_slider", "sliderReleased", self._on_volume_roi_scale_released),
            ("roi_budget", "volume_roi_budget_combo", "currentIndexChanged", self._refresh_volume_preview),
            ("tint", "volume_tint_combo", "currentIndexChanged", self._on_volume_tint_changed),
            ("custom_color", "btn_volume_custom_color", "clicked", self.choose_volume_custom_color),
            ("transfer_release", "volume_transfer_opacity_slider", "sliderReleased", self._on_volume_transfer_opacity_released),
            ("transfer_change", "volume_transfer_opacity_slider", "valueChanged", self._on_volume_transfer_opacity_changed),
            ("enhancement", "volume_enhancement_slider", "valueChanged", self._on_volume_display_enhancement_changed),
            ("tone", "volume_tone_slider", "valueChanged", self._on_volume_display_enhancement_changed),
            ("shader_quality", "volume_shader_quality_combo", "currentIndexChanged", self._on_volume_shader_quality_changed),
            ("surface_refine", "volume_surface_refine_check", "toggled", self._on_volume_display_enhancement_changed),
            ("clip_plane", "volume_clip_plane_check", "toggled", self._on_volume_clip_plane_changed),
            ("local_axes", "volume_local_axes_check", "toggled", self.render_volume_preview),
            ("mask_mode", "volume_mask_combo", "currentIndexChanged", self._on_volume_mask_changed),
            ("mask_opacity", "volume_mask_opacity_slider", "valueChanged", self.render_volume_preview),
            ("reset", "btn_reset_volume_view", "clicked", self.reset_volume_view),
            ("morphology_preset", "btn_volume_morphology_preset", "clicked", self.apply_morphology_inspect_preset),
        )
        for key, widget_name, signal_name, slot in bindings:
            signal = getattr(view.require(self.VIEW_SCOPE, widget_name), signal_name)
            workbench.signal_router.bind(self.VIEW_SCOPE, key, signal, slot)
        for key, widget_name in (
            ("inside", "volume_inside_slider"),
            ("clip", "volume_clip_slider"),
            ("clip_plane_depth", "volume_clip_plane_depth_slider"),
        ):
            slider = view.require(self.VIEW_SCOPE, widget_name)
            workbench.signal_router.bind(self.VIEW_SCOPE, f"{key}_press", slider.sliderPressed, self._start_volume_interaction)
            workbench.signal_router.bind(self.VIEW_SCOPE, f"{key}_change", slider.valueChanged, lambda _value, item=slider: self._on_volume_interaction_slider_changed(item))
            workbench.signal_router.bind(self.VIEW_SCOPE, f"{key}_release", slider.sliderReleased, self.finish_volume_interaction_debounced)
        workbench.signal_router.bind(
            self.VIEW_SCOPE,
            "still_timer",
            workbench.volume_still_timer.timeout,
            self._finish_volume_interaction,
        )

    def _volume_mode_label(self):
        workbench = self.workbench
        if self.state.volume_render_mode != "drag" and self.state.volume_clarity_mode:
            return tt("Local detail check", workbench.lang)
        return tt("Drag preview", workbench.lang) if self.state.volume_render_mode == "drag" else tt("Still high quality", workbench.lang)

    def _volume_projection_mode(self):
        workbench = self.workbench
        if hasattr(workbench, "volume_projection_combo"):
            mode = workbench.volume_projection_combo.currentData()
            if mode in {"composite", "mip", "minip", "average", "surface"}:
                return mode
        return "composite"

    def _volume_projection_label(self):
        workbench = self.workbench
        labels = {
            "composite": "Composite",
            "mip": "MIP",
            "minip": "MinIP",
            "average": "Average",
            "surface": "Surface",
        }
        return tt(labels.get(self._volume_projection_mode(), "Composite"), workbench.lang)

    def _volume_mask_mode(self):
        workbench = self.workbench
        if hasattr(workbench, "volume_mask_combo"):
            mode = workbench.volume_mask_combo.currentData()
            if mode in {"image_only", "mask_boundary", "masked_image"}:
                return mode
        return "image_only"

    def _volume_mask_label_text(self):
        workbench = self.workbench
        labels = {
            "image_only": "Image only",
            "mask_boundary": "Mask boundary",
            "masked_image": "Masked image",
        }
        return tt(labels.get(self._volume_mask_mode(), "Image only"), workbench.lang)

    def _volume_transfer_label(self):
        workbench = self.workbench
        labels = {
            "amber": "Amber",
            "cyan": "Cyan",
            "white": "White",
            "morphology": "Morphology Inspect",
            "publication": "Publication Inspect",
            "custom": "Custom",
        }
        return tt(labels.get(self._volume_transfer_preset(), "Amber"), workbench.lang)

    def _volume_transfer_opacity(self, mode=None):
        workbench = self.workbench
        value = 100
        if hasattr(workbench, "volume_transfer_opacity_slider"):
            value = int(workbench.volume_transfer_opacity_slider.value())
        render_mode = "drag" if mode == "drag" else self.state.volume_render_mode
        if render_mode == "drag" and self._volume_projection_mode() == "composite":
            return max(0.05, min(1.0, 0.55 * (float(value) / 100.0)))
        base = 0.72 if self.state.volume_clarity_mode and render_mode == "still" else (1.0 if render_mode == "still" else 0.82)
        return max(0.05, min(1.4, base * (float(value) / 100.0)))

    def _volume_detail_enhancement(self, mode=None):
        workbench = self.workbench
        if mode == "drag":
            return 0.0
        value = int(workbench.volume_enhancement_slider.value()) if hasattr(workbench, "volume_enhancement_slider") else 0
        return max(0.0, min(1.0, float(value) / 100.0))

    def _volume_tone_gamma(self):
        workbench = self.workbench
        value = int(workbench.volume_tone_slider.value()) if hasattr(workbench, "volume_tone_slider") else 100
        return max(0.65, min(1.35, float(value) / 100.0))

    def _volume_clip_plane_normal(self):
        workbench = self.workbench
        try:
            yaw = math.radians(float(self.state.volume_yaw))
            pitch = math.radians(float(self.state.volume_pitch))
            cy, sy = math.cos(yaw), math.sin(yaw)
            cp, sp = math.cos(pitch), math.sin(pitch)
            rot_yaw = np.array([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]], dtype=np.float32)
            rot_pitch = np.array([[1.0, 0.0, 0.0], [0.0, cp, -sp], [0.0, sp, cp]], dtype=np.float32)
            direction = (rot_yaw @ rot_pitch).T @ np.asarray((0.0, 0.0, 1.0), dtype=np.float32)
            length = float(np.linalg.norm(direction))
            if not np.isfinite(length) or length <= 1e-6:
                return (0.0, 0.0, 1.0)
            direction = direction / length
            return tuple(float(value) for value in direction)
        except Exception:
            return (0.0, 0.0, 1.0)

    def _active_volume_roi_scale(self):
        workbench = self.workbench
        if self.state.volume_canvas_renderer != "gpu" or self.state.volume_render_mode != "still":
            return 1.0
        if not getattr(workbench, "volume_roi_detail_check", None) or not workbench.volume_roi_detail_check.isChecked():
            return 1.0
        if float(self.state.volume_zoom) <= 1.01:
            return 1.0
        return max(1.0, min(3.0, float(workbench.volume_roi_scale_slider.value()) / 100.0))

    def _volume_roi_inspect_enabled(self):
        workbench = self.workbench
        return bool(getattr(workbench, "volume_roi_inspect_check", None) and workbench.volume_roi_inspect_check.isChecked())

    def _volume_roi_source_mode(self):
        workbench = self.workbench
        if not getattr(workbench, "volume_roi_source_combo", None):
            return "full"
        mode = str(workbench.volume_roi_source_combo.currentData() or "full")
        if mode in {"full", "current_bbox"} or mode.startswith("roi:") or mode.startswith("part:"):
            return mode
        return "full"

    def _active_part_preview_bbox(self):
        workbench = self.workbench
        if (
            workbench.current_volume_scope == "full"
            and workbench.part_preview_mask is not None
            and workbench.part_mask_preview_bbox
            and workbench.image_volume is not None
        ):
            try:
                bbox = normalize_roi_bbox_zyx(workbench.part_mask_preview_bbox, workbench.image_volume.shape)
                if tuple(getattr(workbench.part_preview_mask, "shape", ()) or ()) == roi_shape_zyx(bbox):
                    return bbox
            except Exception:
                return None
        return None

    def _selected_volume_roi_source_bbox(self):
        workbench = self.workbench
        mode = self._volume_roi_source_mode()
        if mode == "current_bbox":
            if not hasattr(workbench, "part_bbox_edit") or not workbench.part_bbox_edit.text().strip():
                return None
            return workbench.roi_workflow_controller.parse_bbox_text()
        if mode.startswith("roi:"):
            roi = workbench.project.get_part_roi(workbench.current_specimen_id, mode.split(":", 1)[1], default=None) if workbench.current_specimen_id else None
            if roi is None or (roi or {}).get("status") == "cancelled":
                return None
            return roi.get("bbox_zyx", [])
        if mode.startswith("part:"):
            part = workbench.project.get_part(workbench.current_specimen_id, mode.split(":", 1)[1], default=None) if workbench.current_specimen_id else None
            if part is None:
                return None
            return part.get("parent_bbox_zyx", [])
        return None

    def _active_volume_sample_count(self):
        workbench = self.workbench
        samples = int(workbench.volume_sample_slider.value())
        if self.state.volume_render_mode == "drag" and self.state.volume_canvas_renderer == "gpu":
            if self._volume_projection_mode() == "composite":
                return max(192, min(samples, 384))
            return max(256, min(samples, 768))
        roi_scale = self._active_volume_roi_scale()
        if roi_scale > 1.0 and self.state.volume_canvas_renderer == "gpu":
            return max(256, min(GPU_VOLUME_MAX_RAY_STEPS, int(round(samples * min(1.5, roi_scale)))))
        return samples

    def _volume_stats_text(self):
        workbench = self.workbench
        stats = dict(getattr(self.state, "volume_last_stats", {}) or {})
        if not stats:
            return tt("GPU stats pending", workbench.lang) if self.state.volume_canvas_renderer == "gpu" else ""
        shape = tuple(stats.get("shape_zyx") or ())
        parts = []
        if len(shape) == 3 and all(int(value) > 0 for value in shape):
            parts.append(f"{tt('actual', workbench.lang)} {int(shape[2])}x{int(shape[1])}x{int(shape[0])}")
        dtype = str(stats.get("dtype") or "")
        if dtype:
            parts.append(f"{tt('Data', workbench.lang)} {dtype}")
        texture_filter = str(stats.get("texture_filter") or "")
        display_scaling = str(stats.get("display_scaling") or "")
        if texture_filter:
            sampling_text = tt(texture_filter, workbench.lang)
            if display_scaling and display_scaling != texture_filter:
                sampling_text = f"{sampling_text}/{tt(display_scaling, workbench.lang)}"
            parts.append(f"{tt('Sampling', workbench.lang)} {sampling_text}")
        projection = str(stats.get("projection_mode") or "")
        if projection:
            parts.append(f"{tt('Mode', workbench.lang)} {self._volume_projection_label()}")
        transfer = str(stats.get("transfer_preset") or "")
        if transfer:
            parts.append(f"{tt('Transfer function', workbench.lang)} {tt(transfer.capitalize(), workbench.lang)}")
        transfer_opacity = stats.get("transfer_opacity")
        if transfer_opacity is not None:
            try:
                parts.append(f"{tt('Density opacity', workbench.lang)} {int(round(float(transfer_opacity) * 100))}%")
            except (TypeError, ValueError):
                pass
        mask_mode = str(stats.get("mask_mode") or "")
        if mask_mode and mask_mode != "image_only":
            parts.append(f"{tt('Mask display', workbench.lang)} {self._volume_mask_label_text()}")
        enhancement = stats.get("enhancement")
        if enhancement is not None:
            try:
                value = int(round(float(enhancement) * 100))
                if value > 0:
                    parts.append(f"{tt('Detail enhancement', workbench.lang)} {value}%")
            except (TypeError, ValueError):
                pass
        if stats.get("clip_plane_enabled"):
            try:
                parts.append(f"{tt('Clip plane', workbench.lang)} {int(round(float(stats.get('clip_plane_depth') or 0.0) * 100))}%")
            except (TypeError, ValueError):
                parts.append(tt("Clip plane", workbench.lang))
        cache_bytes = self._volume_cache_estimated_bytes()
        if cache_bytes > 0:
            parts.append(f"Cache {self._volume_cache_owner_count()}/{self._volume_cache_owner_limit()} {cache_bytes / (1024.0 ** 2):.0f} MB")
        texture_cache_bytes = int(stats.get("texture_cache_bytes") or 0)
        texture_cache_entries = int(stats.get("texture_cache_entries") or 0)
        if texture_cache_entries > 0:
            hits = int(stats.get("texture_cache_hits") or 0)
            misses = int(stats.get("texture_cache_misses") or 0)
            parts.append(
                f"GPU cache {texture_cache_entries} {texture_cache_bytes / (1024.0 ** 2):.0f} MB hit {hits}/{hits + misses}"
            )
        degradation = self._volume_gpu_stream_degradation_text(stats)
        if degradation:
            parts.append(degradation)
        if float(getattr(self.state, "volume_last_preview_build_ms", 0.0) or 0.0) > 0.0:
            parts.append(f"Load {float(self.state.volume_last_preview_build_ms):.0f} ms")
        supersample = float(stats.get("supersample_scale") or 1.0)
        if supersample > 1.01:
            parts.append(f"{tt('ROI', workbench.lang)} {supersample:.1f}x")
            parts.append(f"{tt('ROI budget', workbench.lang)} {self._roi_texture_budget_bytes() / (1024.0 ** 3):.1f} GB")
        roi_shape = tuple(int(value) for value in getattr(self.state, "volume_roi_preview_source_shape", ()) or ())
        if len(roi_shape) == 3 and all(value > 0 for value in roi_shape):
            parts.append(f"{tt('ROI crop source', workbench.lang)} {int(roi_shape[2])}x{int(roi_shape[1])}x{int(roi_shape[0])}")
        byte_count = int(stats.get("bytes") or 0)
        if byte_count > 0:
            parts.append(f"{tt('VRAM', workbench.lang)} {byte_count / (1024.0 ** 3):.2f} GB")
        upload_ms = float(stats.get("upload_ms") or 0.0)
        draw_ms = float(stats.get("draw_ms") or 0.0)
        if upload_ms > 0:
            parts.append(f"{tt('Upload', workbench.lang)} {upload_ms:.0f} ms")
        if draw_ms > 0:
            parts.append(f"{tt('Draw', workbench.lang)} {draw_ms:.1f} ms")
        diagnosis = self._volume_performance_diagnosis(stats)
        if diagnosis:
            parts.append(diagnosis)
        return " | ".join(parts)

    def _volume_status_summary_text(self):
        workbench = self.workbench
        resource_summary = workbench.preview_controller.state_summary()
        if resource_summary.get("resource_limited"):
            return str(resource_summary.get("user_message") or tt("No TIF volume loaded", workbench.lang))
        if workbench.image_volume is None:
            return tt("No TIF volume loaded", workbench.lang)
        parts = [
            tt("Volume view", workbench.lang),
            tt("GPU ray march", workbench.lang) if self.state.volume_canvas_renderer == "gpu" else tt("CPU fallback", workbench.lang),
            self._volume_mode_label(),
            f"{tt('Mode', workbench.lang)} {self._volume_projection_label()}",
            f"{tt('Texture', workbench.lang)} {self._active_volume_target_dim()}",
            f"{tt('Samples', workbench.lang)} {self._active_volume_sample_count()}",
        ]
        roi_scale = self._active_volume_roi_scale()
        if roi_scale > 1.01:
            parts.append(f"{tt('ROI', workbench.lang)} {roi_scale:.1f}x")
        cache_bytes = self._volume_cache_estimated_bytes()
        if cache_bytes > 0:
            parts.append(f"Cache {self._volume_cache_owner_count()}/{self._volume_cache_owner_limit()}")
        stats = dict(getattr(self.state, "volume_last_stats", {}) or {})
        texture_cache_entries = int(stats.get("texture_cache_entries") or 0)
        if texture_cache_entries > 0:
            texture_cache_bytes = int(stats.get("texture_cache_bytes") or 0)
            parts.append(f"GPU {texture_cache_entries} {texture_cache_bytes / (1024.0 ** 2):.0f} MB")
        degradation = self._volume_gpu_stream_degradation_text(stats, compact=True)
        if degradation:
            parts.append(degradation)
        load_ms = float(getattr(self.state, "volume_last_preview_build_ms", 0.0) or 0.0)
        if load_ms > 0.0:
            parts.append(f"Load {load_ms:.0f} ms")
        diagnosis = self._volume_performance_diagnosis(stats)
        if diagnosis:
            parts.append(diagnosis)
        return " | ".join(parts)

    def _volume_performance_diagnosis(self, stats=None):
        workbench = self.workbench
        stats = dict(stats or getattr(self.state, "volume_last_stats", {}) or {})
        if self.state.volume_canvas_renderer != "gpu":
            if self.state.volume_renderer_warning:
                return tt("GPU fallback active", workbench.lang)
            return ""
        byte_count = int(stats.get("bytes") or 0)
        upload_ms = float(stats.get("upload_ms") or 0.0)
        draw_ms = float(stats.get("draw_ms") or 0.0)
        if upload_ms >= 1200.0:
            return tt("bottleneck: texture upload", workbench.lang)
        if draw_ms >= 90.0:
            return tt("bottleneck: ray rendering", workbench.lang)
        if byte_count >= int(1.5 * 1024 * 1024 * 1024):
            return tt("large GPU texture", workbench.lang)
        return ""

    def _volume_gpu_stream_degradation_text(self, stats=None, compact=False):
        workbench = self.workbench
        stats = dict(stats or getattr(self.state, "volume_last_stats", {}) or {})
        stream = dict(stats.get("gpu_stream_build") or {})
        if not stream.get("degraded"):
            return ""
        actual = int(stream.get("actual_max_dim") or 0)
        requested = int(stream.get("requested_max_dim") or 0)
        if actual > 0 and requested > actual:
            if compact:
                return f"{tt('GPU budget', workbench.lang)} {actual}/{requested}"
            return f"{tt('GPU budget auto-scaled preview', workbench.lang)} {actual}/{requested}"
        if compact:
            return tt("GPU budget auto-scaled", workbench.lang)
        return tt("GPU budget auto-scaled preview", workbench.lang)

    def volume_performance_report(self):
        workbench = self.workbench
        stats = dict(getattr(self.state, "volume_last_stats", {}) or {})
        source_shape, spacing_zyx = self._volume_source_geometry()
        report = {
            "renderer": self.state.volume_canvas_renderer,
            "renderer_label": self._volume_renderer_label(),
            "source_shape_zyx": tuple(int(value) for value in source_shape) if len(source_shape) == 3 else (),
            "spacing_zyx": tuple(float(value) for value in spacing_zyx) if len(spacing_zyx) == 3 else (),
            "preview_shape_zyx": tuple(int(value) for value in stats.get("shape_zyx") or ()),
            "dtype": str(stats.get("dtype") or ""),
            "uploaded_bytes": int(stats.get("bytes") or 0),
            "upload_ms": float(stats.get("upload_ms") or 0.0),
            "draw_ms": float(stats.get("draw_ms") or 0.0),
            "samples": int(stats.get("steps") or self._active_volume_sample_count()),
            "render_mode": self.state.volume_render_mode,
            "projection_mode": self._volume_projection_mode(),
            "roi_scale": float(self._active_volume_roi_scale()),
            "roi_texture_budget_bytes": int(self._roi_texture_budget_bytes()),
            "cache_specimen_count": int(self._volume_cache_owner_count()),
            "cache_max_specimens": int(self._volume_cache_owner_limit()),
            "cache_estimated_bytes": int(self._volume_cache_estimated_bytes()),
            "cache_estimated_gb": float(self._volume_cache_estimated_bytes()) / (1024.0 ** 3),
            "gpu_texture_cache_entries": int(stats.get("texture_cache_entries") or 0),
            "gpu_texture_cache_bytes": int(stats.get("texture_cache_bytes") or 0),
            "gpu_texture_cache_gb": float(stats.get("texture_cache_bytes") or 0) / (1024.0 ** 3),
            "gpu_texture_cache_budget_bytes": int(stats.get("texture_cache_budget_bytes") or 0),
            "gpu_texture_cache_hits": int(stats.get("texture_cache_hits") or 0),
            "gpu_texture_cache_misses": int(stats.get("texture_cache_misses") or 0),
            "gpu_stream_build": dict(stats.get("gpu_stream_build") or {}),
            "gpu_stream_degraded": bool((stats.get("gpu_stream_build") or {}).get("degraded")),
            "load_ms": float(getattr(self.state, "volume_last_preview_build_ms", 0.0) or 0.0),
            "roi_source_mode": self._volume_roi_source_mode(),
            "roi_inspect_enabled": bool(self._volume_roi_inspect_enabled()),
            "roi_inspect_active": bool(getattr(self.state, "volume_roi_preview_bbox", None)),
            "roi_bbox_zyx": getattr(self.state, "volume_roi_preview_bbox", None),
            "roi_source_shape_zyx": tuple(int(value) for value in getattr(self.state, "volume_roi_preview_source_shape", ()) or ()),
            "shader_quality_mode": self._volume_shader_quality_mode(),
            "clip_plane_enabled": bool(workbench.volume_clip_plane_check.isChecked()),
            "diagnosis": self._volume_performance_diagnosis(stats),
        }
        if report["uploaded_bytes"] > 0:
            report["uploaded_gb"] = report["uploaded_bytes"] / (1024.0 ** 3)
        else:
            report["uploaded_gb"] = 0.0
        return report

    def _update_volume_render_status_label(self, text=None):
        workbench = self.workbench
        if not hasattr(workbench, "volume_render_status_label"):
            return
        full_text = workbench.volume_canvas_overlay_text() if workbench.image_volume is not None else ""
        if text is None:
            text = self._volume_status_summary_text()
            tooltip = full_text or str(text or "")
        else:
            text = str(text or "")
            tooltip = text
            if full_text and full_text != text:
                tooltip = f"{text}\n\n{full_text}"
        workbench.volume_render_status_label.setText(str(text or ""))
        workbench.volume_render_status_label.setToolTip(tooltip)

    def _volume_canvas_has_visible_content(self):
        workbench = self.workbench
        canvas = getattr(workbench, "volume_canvas", None)
        if canvas is None:
            return False
        if callable(getattr(canvas, "has_volume", None)):
            try:
                if canvas.has_volume():
                    return True
            except Exception:
                pass
        if callable(getattr(canvas, "pixmap", None)):
            try:
                pixmap = canvas.pixmap()
                if pixmap is not None and not pixmap.isNull():
                    return True
            except Exception:
                pass
        return False

    def _set_volume_canvas_status_text(self, text, replace_existing=False):
        workbench = self.workbench
        canvas = getattr(workbench, "volume_canvas", None)
        if canvas is None or not hasattr(canvas, "setText"):
            return False
        if not replace_existing and self._volume_canvas_has_visible_content():
            return False
        try:
            canvas.setText(str(text or ""))
            return True
        except Exception:
            return False

    def _volume_preview_ui_waiting(self):
        workbench = self.workbench
        return int(getattr(self.state, "volume_preview_ui_wait_depth", 0) or 0) > 0

    def _begin_volume_preview_ui_wait(self):
        workbench = self.workbench
        depth = int(getattr(self.state, "volume_preview_ui_wait_depth", 0) or 0)
        self.state.volume_preview_ui_wait_depth = depth + 1
        if depth == 0:
            try:
                QApplication.instance().installEventFilter(self)
            except Exception:
                pass
        canvas = getattr(workbench, "volume_canvas", None)
        if hasattr(canvas, "set_stream_build_yield_callback"):
            try:
                canvas.set_stream_build_yield_callback(self._yield_volume_preview_ui_events)
            except Exception:
                pass

    def _end_volume_preview_ui_wait(self):
        workbench = self.workbench
        depth = max(0, int(getattr(self.state, "volume_preview_ui_wait_depth", 0) or 0) - 1)
        self.state.volume_preview_ui_wait_depth = depth
        if depth == 0:
            canvas = getattr(workbench, "volume_canvas", None)
            if hasattr(canvas, "set_stream_build_yield_callback"):
                try:
                    canvas.set_stream_build_yield_callback(None)
                except Exception:
                    pass
            try:
                QApplication.instance().removeEventFilter(self)
            except Exception:
                pass

    def _yield_volume_preview_ui_events(self):
        workbench = self.workbench
        QApplication.processEvents()

    def _volume_renderer_label(self):
        workbench = self.workbench
        renderer = tt("GPU ray march", workbench.lang) if self.state.volume_canvas_renderer == "gpu" else tt("CPU fallback", workbench.lang)
        gpu_label = ""
        if self.state.volume_canvas_renderer == "gpu":
            if hasattr(workbench.volume_canvas, "renderer_label"):
                gpu_label = workbench.volume_canvas.renderer_label()
            if not gpu_label:
                gpu_label = self._compact_gpu_renderer_info(self.state.volume_gl_renderer_info)
        if gpu_label:
            renderer = f"{renderer} [{gpu_label}]"
        return renderer

    def _compact_gpu_renderer_info(self, info):
        workbench = self.workbench
        text = " ".join(str(info or "").split())
        if "RTX 3090" in text:
            return "RTX 3090"
        if "NVIDIA GeForce" in text:
            return text.replace("NVIDIA GeForce ", "NVIDIA ").split("|")[0].strip()
        return text.split("|")[0].strip()[:42]

    def _volume_renderer_status_message(self):
        workbench = self.workbench
        if self.state.volume_canvas_renderer == "gpu":
            return tt("3D preview uses a downsampled read-only volume. Use Slice review for precise label editing.", workbench.lang)
        if self.state.volume_renderer_warning:
            return (
                tt("3D preview uses a downsampled read-only volume. Use Slice review for precise label editing.", workbench.lang)
                + "\n"
                + tt("GPU renderer unavailable. Using CPU fallback.", workbench.lang)
            )
        return tt("3D preview uses a downsampled read-only volume. Use Slice review for precise label editing.", workbench.lang)

    def _on_gpu_volume_info_changed(self, details):
        workbench = self.workbench
        info = str(details or "")
        if info == self.state.volume_gl_renderer_info:
            return
        self.state.volume_gl_renderer_info = info
        if self.state.volume_gl_renderer_info:
            workbench.log(f"GPU volume OpenGL renderer: {self.state.volume_gl_renderer_info}")
        self._update_volume_render_status_label()
        if workbench.display_mode == "volume":
            self.render_volume_preview()

    def _on_gpu_volume_failed(self, reason):
        workbench = self.workbench
        if self.state.volume_canvas_renderer != "gpu":
            return
        if getattr(self.state, "handling_gpu_volume_failure", False):
            return
        self.state.handling_gpu_volume_failure = True
        warning = str(reason or "unknown")
        try:
            self._switch_volume_canvas_to_cpu(warning)
            message = tt("GPU renderer failed. Using CPU fallback: {0}", workbench.lang).format(warning)
            workbench.training_status_label.setText(message)
            self._update_volume_render_status_label(
                f"{tt('Volume view', workbench.lang)} | {tt('CPU fallback', workbench.lang)} | {tt('GPU failed', workbench.lang)}: {warning}"
            )
            workbench.log(message)
        finally:
            self.state.handling_gpu_volume_failure = False
        self.schedule_volume_preview_render()

    def _switch_volume_canvas_to_cpu(self, warning=""):
        workbench = self.workbench
        old_canvas = getattr(workbench, "volume_canvas", None)
        if old_canvas is not None and not hasattr(old_canvas, "set_volume_pixmap"):
            if hasattr(old_canvas, "release_gl_resources"):
                try:
                    old_canvas.release_gl_resources()
                except Exception:
                    pass
            workbench.volume_canvas = TifVolumeCanvas()
            workbench.volume_canvas.workbench = workbench
            workbench.volume_canvas.set_theme(workbench.current_theme)
            renderer_property = "cpu-mask-fallback" if str(warning or "").startswith("Mask inspection") else "cpu"
            workbench.volume_canvas.setProperty("tifVolumeRenderer", renderer_property)
            if hasattr(workbench, "view_stack"):
                workbench.view_stack.addWidget(workbench.volume_canvas)
                index = workbench.view_stack.indexOf(old_canvas)
                if workbench.display_mode == "volume":
                    workbench.view_stack.setCurrentWidget(workbench.volume_canvas)
                if index >= 0:
                    workbench.view_stack.removeWidget(old_canvas)
            old_canvas.hide()
            old_canvas.setParent(None)
            old_canvas.deleteLater()
        self.state.volume_canvas_renderer = "cpu"
        if warning and not str(warning).startswith("Mask inspection"):
            self.state.volume_renderer_warning = str(warning)
        self.state.volume_last_stats = {}

    def _try_restore_gpu_volume_canvas(self):
        workbench = self.workbench
        if self.state.volume_canvas_renderer == "gpu" or self.state.volume_renderer_warning:
            return False
        if not getattr(workbench, "_volume_canvas_created", False):
            return False
        if str(getattr(workbench.volume_canvas, "property", lambda _key: "")("tifVolumeRenderer") or "") != "cpu-mask-fallback":
            return False
        workbench._ensure_volume_canvas(force_gpu=True)
        return self.state.volume_canvas_renderer == "gpu"

    def _on_gpu_volume_stats_changed(self):
        workbench = self.workbench
        if hasattr(workbench.volume_canvas, "render_stats"):
            self.state.volume_last_stats = dict(workbench.volume_canvas.render_stats() or {})
        self._update_volume_render_status_label()

    def _start_volume_interaction(self):
        workbench = self.workbench
        if self.state.volume_render_mode != "drag":
            self.state.volume_render_mode = "drag"
        if hasattr(workbench, "volume_still_timer"):
            workbench.volume_still_timer.start()

    def finish_volume_interaction_debounced(self):
        workbench = self.workbench
        if hasattr(workbench, "volume_still_timer"):
            workbench.volume_still_timer.start()

    def _finish_volume_interaction(self):
        workbench = self.workbench
        self.state.volume_interaction_render_pending = False
        if self.state.volume_render_mode != "still":
            self.state.volume_render_mode = "still"
            self.render_volume_preview()

    def _on_volume_interaction_slider_changed(self, slider=None):
        workbench = self.workbench
        if workbench.display_mode != "volume":
            return
        if slider is not None and callable(getattr(slider, "isSliderDown", None)) and slider.isSliderDown():
            self._start_volume_interaction()
            self._request_volume_interaction_render()
            return
        if self.state.volume_render_mode == "drag":
            self._request_volume_interaction_render()
            self.finish_volume_interaction_debounced()
            return
        self.render_volume_preview()

    def _on_volume_clarity_toggled(self, checked):
        workbench = self.workbench
        self.state.volume_clarity_mode = bool(checked)
        self._reset_active_volume_preview_state()
        self.render_volume_preview()

    def _on_volume_quality_drag_started(self):
        workbench = self.workbench
        self.state.volume_quality_drag_pending = True
        try:
            self.state.volume_quality_committed_value = int(workbench.volume_quality_slider.value())
        except Exception:
            self.state.volume_quality_committed_value = None
        self._show_volume_quality_release_status()

    def _on_volume_quality_drag_moved(self, *_args):
        workbench = self.workbench
        self.state.volume_quality_drag_pending = True
        self._show_volume_quality_release_status()

    def _show_volume_quality_release_status(self):
        workbench = self.workbench
        if workbench.display_mode != "volume":
            return
        message = tt("Release Render quality to rebuild the 3D preview.", workbench.lang)
        self._set_volume_canvas_status_text(message)
        self._update_volume_render_status_label(message)

    def _on_volume_quality_changed(self, *_args):
        workbench = self.workbench
        if getattr(self.state, "volume_quality_drag_pending", False):
            self._show_volume_quality_release_status()
        elif workbench.display_mode == "volume":
            self._update_volume_render_status_label()

    def _on_volume_quality_released(self):
        workbench = self.workbench
        self._commit_volume_quality_change()

    def _commit_volume_quality_change(self):
        workbench = self.workbench
        try:
            value = int(workbench.volume_quality_slider.value())
        except Exception:
            value = None
        if value == getattr(self.state, "volume_quality_committed_value", None):
            self.state.volume_quality_drag_pending = False
            return
        self.state.volume_quality_committed_value = value
        self.state.volume_quality_drag_pending = False
        self._prune_volume_preview_cache()
        self._refresh_volume_preview()

    def _on_volume_roi_scale_drag_started(self):
        workbench = self.workbench
        try:
            self.state.volume_roi_scale_committed_value = int(workbench.volume_roi_scale_slider.value())
        except Exception:
            self.state.volume_roi_scale_committed_value = None

    def _on_volume_roi_scale_changed(self, *_args):
        workbench = self.workbench
        if callable(getattr(workbench.volume_roi_scale_slider, "isSliderDown", None)) and workbench.volume_roi_scale_slider.isSliderDown():
            if workbench.display_mode == "volume":
                self._update_volume_render_status_label(tt("Release ROI scale to update the 3D preview.", workbench.lang))
            return
        self._commit_volume_roi_scale_change()

    def _on_volume_roi_scale_released(self):
        workbench = self.workbench
        self._commit_volume_roi_scale_change()

    def _commit_volume_roi_scale_change(self):
        workbench = self.workbench
        try:
            value = int(workbench.volume_roi_scale_slider.value())
        except Exception:
            value = None
        if value == getattr(self.state, "volume_roi_scale_committed_value", None):
            return
        self.state.volume_roi_scale_committed_value = value
        self.render_volume_preview()

    def _on_volume_display_enhancement_changed(self, *_args):
        workbench = self.workbench
        self.render_volume_preview()

    def _on_volume_clip_plane_changed(self, *_args):
        workbench = self.workbench
        self.render_volume_preview()

    def _on_volume_projection_changed(self):
        workbench = self.workbench
        self.render_volume_preview()

    def _volume_tint_rgb(self):
        workbench = self.workbench
        settings = workbench._active_volume_view_settings()
        mode = workbench.volume_tint_combo.currentData() if hasattr(workbench, "volume_tint_combo") else settings.get("volume_tint", "amber")
        if mode == "cyan":
            color = QColor("#61D9FF")
        elif mode == "white":
            color = QColor("#F0F4F2")
        elif mode == "morphology":
            color = QColor("#9CB8A6")
        elif mode == "publication":
            color = QColor("#FFE1A1")
        elif mode == "custom":
            color = QColor(str(settings.get("volume_tint_custom", "#FFD34D")))
            if not color.isValid():
                color = QColor("#FFD34D")
        else:
            color = QColor("#FFD34D")
        return np.asarray([color.redF(), color.greenF(), color.blueF()], dtype=np.float32)

    def _volume_transfer_preset(self):
        workbench = self.workbench
        settings = workbench._active_volume_view_settings()
        mode = workbench.volume_tint_combo.currentData() if hasattr(workbench, "volume_tint_combo") else settings.get("volume_tint", "amber")
        mode = str(mode or "amber").lower()
        return mode if mode in {"amber", "cyan", "white", "custom", "morphology", "publication"} else "amber"

    def _volume_transfer_lut(self):
        workbench = self.workbench
        return build_volume_transfer_lut(
            self._volume_transfer_preset(),
            tuple(float(value) for value in self._volume_tint_rgb()),
            cutoff=0.0,
            opacity=self._volume_transfer_opacity(),
            clarity=self.state.volume_clarity_mode and self.state.volume_render_mode == "still",
        )

    def _volume_shader_quality_mode(self):
        workbench = self.workbench
        if hasattr(workbench, "volume_shader_quality_combo"):
            mode = workbench.volume_shader_quality_combo.currentData()
        else:
            mode = workbench._active_volume_view_settings().get("volume_shader_quality", "preset")
        mode = str(mode or "preset").lower()
        return mode if mode in {"off", "preset", "all_still"} else "preset"

    def _volume_shader_quality_label_text(self):
        workbench = self.workbench
        labels = {
            "off": "Off",
            "preset": "Inspect presets",
            "all_still": "All still composite",
        }
        return tt(labels.get(self._volume_shader_quality_mode(), "Inspect presets"), workbench.lang)

    def _volume_shader_quality_settings(self, mode=None):
        workbench = self.workbench
        mode = "drag" if mode == "drag" else "still"
        clip_plane_enabled = bool(hasattr(workbench, "volume_clip_plane_check") and workbench.volume_clip_plane_check.isChecked())
        settings = volume_shader_quality_settings(
            self._volume_transfer_preset(),
            mode,
            self._volume_projection_mode(),
            self._volume_mask_mode(),
            clip_plane_enabled,
            self._volume_shader_quality_mode(),
        )
        return settings

    def _volume_gradient_opacity_settings(self, mode=None):
        workbench = self.workbench
        settings = self._volume_shader_quality_settings(mode)
        return float(settings["gradient_opacity"]), tuple(settings["gradient_opacity_range"])

    def _volume_jitter_strength(self, mode=None):
        workbench = self.workbench
        settings = self._volume_shader_quality_settings(mode)
        return float(settings["jitter_strength"])

    def _volume_adaptive_step_strength(self, mode=None):
        workbench = self.workbench
        settings = self._volume_shader_quality_settings(mode)
        return float(settings["adaptive_step_strength"])

    def _on_volume_tint_changed(self):
        workbench = self.workbench
        settings = workbench._active_volume_view_settings()
        settings["volume_tint"] = workbench.volume_tint_combo.currentData() or "amber"
        workbench._save_active_volume_view_settings()
        self.render_volume_preview()

    def _on_volume_transfer_opacity_changed(self):
        workbench = self.workbench
        if callable(getattr(workbench.volume_transfer_opacity_slider, "isSliderDown", None)) and workbench.volume_transfer_opacity_slider.isSliderDown():
            self.state.volume_transfer_opacity_drag_pending = True
            self.render_volume_preview()
            return
        self.state.volume_transfer_opacity_drag_pending = False
        self._save_volume_transfer_opacity_setting()
        self.render_volume_preview()

    def _on_volume_transfer_opacity_released(self):
        workbench = self.workbench
        if not getattr(self.state, "volume_transfer_opacity_drag_pending", False):
            return
        self.state.volume_transfer_opacity_drag_pending = False
        self._save_volume_transfer_opacity_setting()

    def _save_volume_transfer_opacity_setting(self):
        workbench = self.workbench
        settings = workbench._active_volume_view_settings()
        settings["volume_transfer_opacity"] = int(workbench.volume_transfer_opacity_slider.value())
        workbench._save_active_volume_view_settings()

    def _on_volume_shader_quality_changed(self):
        workbench = self.workbench
        settings = workbench._active_volume_view_settings()
        settings["volume_shader_quality"] = self._volume_shader_quality_mode()
        workbench._save_active_volume_view_settings()
        self.render_volume_preview()

    def _on_volume_mask_changed(self):
        workbench = self.workbench
        settings = workbench._active_volume_view_settings()
        settings["volume_mask_mode"] = self._volume_mask_mode()
        workbench._save_active_volume_view_settings()
        self._clear_volume_mask_caches(owner=self._active_volume_cache_owner())
        self.render_volume_preview()

    def choose_volume_custom_color(self):
        workbench = self.workbench
        settings = workbench._active_volume_view_settings()
        color = QColorDialog.getColor(QColor(str(settings.get("volume_tint_custom", "#FFD34D"))), self, tt("Choose color", workbench.lang))
        if not color.isValid():
            return
        settings["volume_tint"] = "custom"
        settings["volume_tint_custom"] = color.name()
        index = workbench.volume_tint_combo.findData("custom")
        if index >= 0:
            workbench.volume_tint_combo.setCurrentIndex(index)
        workbench._save_active_volume_view_settings()
        self.render_volume_preview()

    def apply_morphology_inspect_preset(self):
        workbench = self.workbench
        controls = [
            workbench.volume_projection_combo,
            workbench.volume_tint_combo,
            workbench.volume_shader_quality_combo,
            workbench.volume_cutoff_slider,
            workbench.volume_transfer_opacity_slider,
            workbench.volume_enhancement_slider,
            workbench.volume_tone_slider,
            workbench.volume_surface_refine_check,
        ]
        for control in controls:
            control.blockSignals(True)
        try:
            projection_index = workbench.volume_projection_combo.findData("composite")
            if projection_index >= 0:
                workbench.volume_projection_combo.setCurrentIndex(projection_index)
            transfer_index = workbench.volume_tint_combo.findData("morphology")
            if transfer_index >= 0:
                workbench.volume_tint_combo.setCurrentIndex(transfer_index)
            quality_index = workbench.volume_shader_quality_combo.findData("preset")
            if quality_index >= 0:
                workbench.volume_shader_quality_combo.setCurrentIndex(quality_index)
            workbench.volume_cutoff_slider.setValue(18)
            workbench.volume_transfer_opacity_slider.setValue(92)
            workbench.volume_enhancement_slider.setValue(72)
            workbench.volume_tone_slider.setValue(92)
            workbench.volume_surface_refine_check.setChecked(True)
        finally:
            for control in controls:
                control.blockSignals(False)

        settings = workbench._active_volume_view_settings()
        settings["volume_tint"] = "morphology"
        settings["volume_shader_quality"] = "preset"
        settings["volume_transfer_opacity"] = int(workbench.volume_transfer_opacity_slider.value())
        workbench._save_active_volume_view_settings()
        self.render_volume_preview()

    def rotate_volume_preview(self, dx, dy):
        workbench = self.workbench
        self._start_volume_interaction()
        self.state.volume_yaw = (self.state.volume_yaw + float(dx) * 0.6) % 360.0
        self.state.volume_pitch = max(-85.0, min(85.0, self.state.volume_pitch - float(dy) * 0.45))
        self._request_volume_interaction_render()

    def pan_volume_preview(self, dx, dy):
        workbench = self.workbench
        self._start_volume_interaction()
        width = max(1.0, float(workbench.volume_canvas.width()) if hasattr(workbench, "volume_canvas") else 1.0)
        height = max(1.0, float(workbench.volume_canvas.height()) if hasattr(workbench, "volume_canvas") else 1.0)
        pan_speed = 2.8
        self.state.volume_pan_x += (float(dx) / width) * pan_speed
        self.state.volume_pan_y -= (float(dy) / height) * pan_speed
        self._clamp_volume_pan()
        self._request_volume_interaction_render()

    def zoom_volume_preview(self, direction):
        workbench = self.workbench
        self._start_volume_interaction()
        factor = 1.18 if int(direction) > 0 else 1.0 / 1.18
        self.state.volume_zoom = max(0.35, min(16.0, self.state.volume_zoom * factor))
        self._clamp_volume_pan()
        self._request_volume_interaction_render()

    def _volume_pan_limit(self):
        workbench = self.workbench
        return volume_pan_limit_for_zoom(getattr(self.state, "volume_zoom", 1.0))

    def _clamp_volume_pan(self):
        workbench = self.workbench
        limit = self._volume_pan_limit()
        self.state.volume_pan_x = max(-limit, min(limit, float(self.state.volume_pan_x)))
        self.state.volume_pan_y = max(-limit, min(limit, float(self.state.volume_pan_y)))

    def reset_volume_view(self):
        workbench = self.workbench
        if hasattr(workbench, "volume_still_timer"):
            workbench.volume_still_timer.stop()
        self.state.volume_render_mode = "still"
        self.state.volume_yaw = -35.0
        self.state.volume_pitch = 20.0
        self.state.volume_zoom = 1.0
        self.state.volume_pan_x = 0.0
        self.state.volume_pan_y = 0.0
        if hasattr(workbench, "volume_inside_slider"):
            workbench.volume_inside_slider.blockSignals(True)
            workbench.volume_inside_slider.setValue(0)
            workbench.volume_inside_slider.blockSignals(False)
        if hasattr(workbench, "volume_clip_slider"):
            workbench.volume_clip_slider.blockSignals(True)
            workbench.volume_clip_slider.setValue(0)
            workbench.volume_clip_slider.blockSignals(False)
        if hasattr(workbench, "volume_clip_plane_check"):
            workbench.volume_clip_plane_check.blockSignals(True)
            workbench.volume_clip_plane_check.setChecked(False)
            workbench.volume_clip_plane_check.blockSignals(False)
        if hasattr(workbench, "volume_clip_plane_depth_slider"):
            workbench.volume_clip_plane_depth_slider.blockSignals(True)
            workbench.volume_clip_plane_depth_slider.setValue(0)
            workbench.volume_clip_plane_depth_slider.blockSignals(False)
        self.render_volume_preview()

    def _refresh_volume_preview(self):
        workbench = self.workbench
        self._cancel_volume_preview_build()
        self._reset_active_volume_preview_state()
        if workbench.display_mode == "volume":
            message = tt("Preparing full-volume 3D preview...", workbench.lang)
            if self._volume_roi_inspect_enabled() and self._volume_roi_source_mode() != "full":
                message = tt("Preparing ROI crop preview...", workbench.lang)
            elif bool(getattr(self.state, "volume_clarity_mode", False)) or workbench.current_volume_scope == "part":
                message = tt("Preparing local detail preview...", workbench.lang)
            show_canvas_status = self._set_volume_canvas_status_text(message)
            self._update_volume_render_status_label(message)
            if show_canvas_status:
                QApplication.processEvents()
        self.render_volume_preview()

    def _reset_active_volume_preview_state(self):
        workbench = self.workbench
        self.state.volume_preview = None
        self.state.volume_preview_source_shape = ()
        self.state.volume_roi_preview_bbox = None
        self.state.volume_roi_preview_source_shape = ()
        self.state.volume_last_stats = {}
        self.state.volume_last_preview_build_ms = 0.0
        self.state.volume_render_mode = "still"
        self.state.volume_interaction_render_pending = False

    def _release_gpu_texture_cache(self):
        workbench = self.workbench
        canvas = getattr(workbench, "volume_canvas", None)
        if canvas is None or not callable(getattr(canvas, "release_texture_cache", None)):
            return False
        try:
            canvas.release_texture_cache()
            self.state.volume_last_stats = dict(canvas.render_stats() or {}) if callable(getattr(canvas, "render_stats", None)) else {}
            return True
        except Exception:
            return False

    def release_volume_renderer(self):
        canvas = getattr(self.workbench, "volume_canvas", None)
        if canvas is not None and hasattr(canvas, "release_gl_resources"):
            try:
                canvas.release_gl_resources()
            except Exception:
                pass

    def _clear_volume_preview_cache(self):
        workbench = self.workbench
        self._cancel_volume_preview_build()
        self.state.volume_preview_cache = OrderedDict()
        self._clear_volume_mask_caches()
        self._reset_active_volume_preview_state()

    def _active_volume_cache_owner(self):
        workbench = self.workbench
        specimen_id = str(getattr(workbench, "current_specimen_id", "") or "")
        scope = str(getattr(workbench, "current_volume_scope", "") or "full")
        part_id = str(getattr(workbench, "current_part_id", "") or "")
        reslice_id = str(getattr(workbench, "current_reslice_id", "") or "")
        return (specimen_id, scope, part_id, reslice_id)

    def _volume_cache_owner_from_key(self, cache_key):
        workbench = self.workbench
        if isinstance(cache_key, tuple) and cache_key and isinstance(cache_key[0], tuple) and len(cache_key[0]) == 4:
            return cache_key[0]
        return None

    def _clear_active_volume_preview_cache(self):
        workbench = self.workbench
        self._cancel_volume_preview_build()
        owner = self._active_volume_cache_owner()
        self.state.volume_preview_cache = OrderedDict(
            (key, value)
            for key, value in self.state.volume_preview_cache.items()
            if self._volume_cache_owner_from_key(key) != owner
        )
        self._clear_volume_mask_caches(owner=owner)
        self._reset_active_volume_preview_state()

    def _clear_volume_mask_caches(self, owner=None):
        workbench = self.workbench
        if owner is None:
            self.state.volume_mask_preview_cache = OrderedDict()
            self.state.volume_masked_preview_cache = OrderedDict()
            return
        self.state.volume_mask_preview_cache = OrderedDict(
            (key, value)
            for key, value in self.state.volume_mask_preview_cache.items()
            if self._volume_cache_owner_from_key(key) != owner
        )
        self.state.volume_masked_preview_cache = OrderedDict(
            (key, value)
            for key, value in self.state.volume_masked_preview_cache.items()
            if self._volume_cache_owner_from_key(key) != owner
        )

    def _touch_volume_cache_owner(self, owner):
        workbench = self.workbench
        for cache in (self.state.volume_preview_cache, self.state.volume_mask_preview_cache, self.state.volume_masked_preview_cache):
            for key in list(cache.keys()):
                if self._volume_cache_owner_from_key(key) == owner:
                    cache.move_to_end(key)

    def _volume_cache_owner_limit(self):
        workbench = self.workbench
        try:
            target_dim = int(self._active_volume_target_dim("still"))
        except Exception:
            slider = getattr(workbench, "volume_quality_slider", None)
            target_dim = int(slider.value()) if hasattr(slider, "value") else 0
        stream = dict((getattr(self.state, "volume_last_stats", {}) or {}).get("gpu_stream_build") or {})
        if stream.get("degraded"):
            return 1
        if target_dim >= 3072:
            return int(TIF_VOLUME_ULTRA_QUALITY_CACHE_OWNER_LIMIT)
        if target_dim >= 2048:
            return int(TIF_VOLUME_HIGH_QUALITY_CACHE_OWNER_LIMIT)
        return int(TIF_VOLUME_MAX_CACHED_SPECIMENS)

    def _prune_volume_preview_cache(self):
        workbench = self.workbench
        owners = []
        for cache in (self.state.volume_preview_cache, self.state.volume_mask_preview_cache, self.state.volume_masked_preview_cache):
            for key in cache.keys():
                owner = self._volume_cache_owner_from_key(key)
                if owner is not None and owner not in owners:
                    owners.append(owner)
        owner_limit = max(1, int(self._volume_cache_owner_limit()))
        while len(owners) > owner_limit:
            evicted_owner = owners.pop(0)
            self.state.volume_preview_cache = OrderedDict(
                (key, value)
                for key, value in self.state.volume_preview_cache.items()
                if self._volume_cache_owner_from_key(key) != evicted_owner
            )
            self.state.volume_mask_preview_cache = OrderedDict(
                (key, value)
                for key, value in self.state.volume_mask_preview_cache.items()
                if self._volume_cache_owner_from_key(key) != evicted_owner
            )
            self.state.volume_masked_preview_cache = OrderedDict(
                (key, value)
                for key, value in self.state.volume_masked_preview_cache.items()
                if self._volume_cache_owner_from_key(key) != evicted_owner
            )
        self._prune_volume_preview_variants_per_owner()

    def _prune_volume_preview_variants_per_owner(self):
        workbench = self.workbench
        max_variants = int(max(1, TIF_VOLUME_MAX_PREVIEW_VARIANTS_PER_OWNER))
        for cache_name in ("_volume_preview_cache", "_volume_mask_preview_cache", "_volume_masked_preview_cache"):
            cache = ({"_volume_preview_cache": self.state.volume_preview_cache, "_volume_mask_preview_cache": self.state.volume_mask_preview_cache, "_volume_masked_preview_cache": self.state.volume_masked_preview_cache}.get(cache_name, OrderedDict()))
            owner_keys = {}
            for key in list(cache.keys()):
                owner = self._volume_cache_owner_from_key(key)
                if owner is not None:
                    owner_keys.setdefault(owner, []).append(key)
            for keys in owner_keys.values():
                while len(keys) > max_variants:
                    stale_key = keys.pop(0)
                    cache.pop(stale_key, None)

    def _volume_cache_owner_count(self):
        workbench = self.workbench
        owners = set()
        for cache in (self.state.volume_preview_cache, self.state.volume_mask_preview_cache, self.state.volume_masked_preview_cache):
            for key in cache.keys():
                owner = self._volume_cache_owner_from_key(key)
                if owner is not None:
                    owners.add(owner)
        return len(owners)

    def _volume_cache_estimated_bytes(self):
        workbench = self.workbench
        total = 0
        seen = set()
        for cache in (self.state.volume_preview_cache, self.state.volume_mask_preview_cache, self.state.volume_masked_preview_cache):
            for value in cache.values():
                marker = id(value)
                if marker in seen:
                    continue
                seen.add(marker)
                try:
                    total += int(getattr(value, "nbytes", 0) or 0)
                except Exception:
                    pass
        return int(total)

    def _volume_drag_target_dim(self):
        workbench = self.workbench
        requested = self._volume_texture_target_dim()
        if self.state.volume_canvas_renderer != "gpu":
            return requested
        if self._volume_projection_mode() == "composite":
            return max(192, min(requested, 384))
        return max(256, min(requested, 640))

    def _active_volume_target_dim(self, mode=None):
        workbench = self.workbench
        mode = mode or self.state.volume_render_mode
        if mode == "drag":
            return self._volume_drag_target_dim()
        requested = self._volume_texture_target_dim()
        if workbench.current_volume_scope == "part" and workbench.image_volume is not None:
            shape = tuple(int(value) for value in getattr(workbench.image_volume, "shape", ()) or ())
            voxel_count = int(np.prod(shape)) if len(shape) == 3 else 0
            if voxel_count > 0:
                if self.state.volume_clarity_mode:
                    clarity_dim = TIF_VOLUME_CLARITY_PART_FULL_DIM
                    if voxel_count > TIF_VOLUME_CLARITY_PART_FULL_VOXEL_LIMIT:
                        clarity_dim = TIF_VOLUME_CLARITY_PART_HIGH_DIM
                    requested = max(requested, min(max(shape), clarity_dim))
                elif voxel_count <= 64_000_000:
                    requested = max(requested, min(max(shape), 1536))
        return requested

    def _active_volume_roi_bbox(self, mode=None):
        workbench = self.workbench
        mode = "drag" if mode == "drag" else "still"
        if mode != "still" or workbench.current_volume_scope != "full" or workbench.image_volume is None:
            return None
        part_preview_bbox = self._active_part_preview_bbox()
        if part_preview_bbox is not None:
            return part_preview_bbox
        if not self._volume_roi_inspect_enabled():
            return None
        if self._volume_roi_source_mode() == "full":
            return None
        try:
            bbox = self._selected_volume_roi_source_bbox()
            if not bbox:
                return None
            return normalize_roi_bbox_zyx(bbox, workbench.image_volume.shape)
        except Exception:
            return None

    def _roi_texture_budget_bytes(self):
        workbench = self.workbench
        mode = ""
        if hasattr(workbench, "volume_roi_budget_combo"):
            mode = str(workbench.volume_roi_budget_combo.currentData() or "").lower()
        if mode == "high":
            return HIGH_ROI_TEXTURE_BUDGET_BYTES
        return DEFAULT_ROI_TEXTURE_BUDGET_BYTES

    def _volume_preview_progress_message(self, mode, roi_bbox=None):
        workbench = self.workbench
        if roi_bbox is not None:
            return tt("Preparing ROI crop preview...", workbench.lang)
        if bool(getattr(self.state, "volume_clarity_mode", False)) or workbench.current_volume_scope == "part":
            return tt("Preparing local detail preview...", workbench.lang)
        return tt("Preparing full-volume 3D preview...", workbench.lang)

    def _should_show_volume_preview_progress(self, mode, roi_bbox=None):
        workbench = self.workbench
        if mode != "still" or workbench.display_mode != "volume" or workbench.image_volume is None:
            return False
        try:
            dtype_size = max(1, int(np.dtype(getattr(workbench.image_volume, "dtype", np.uint8)).itemsize))
            if roi_bbox is not None:
                shape = roi_shape_zyx(roi_bbox)
                bytes_estimate = int(shape[0]) * int(shape[1]) * int(shape[2]) * dtype_size
                return bytes_estimate >= 32 * 1024 * 1024
            bytes_estimate = int(getattr(workbench.image_volume, "nbytes", 0) or 0)
            if workbench.current_volume_scope == "part" or bool(getattr(self.state, "volume_clarity_mode", False)):
                return bytes_estimate >= 32 * 1024 * 1024
            return bytes_estimate >= 64 * 1024 * 1024
        except Exception:
            return True

    def _show_volume_preview_progress(self, message, detail=None):
        workbench = self.workbench
        dialog = QProgressDialog(message, "", 0, 0, workbench)
        dialog.setWindowTitle(tt("Volume render", workbench.lang))
        dialog.setCancelButton(None)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        dialog.setMinimumDuration(0)
        if detail is None:
            detail = tt(
                "Downsampling volume and uploading texture. This can take a moment for large TIF stacks.",
                workbench.lang,
            )
        dialog.setLabelText(
            str(message or "")
            + "\n"
            + str(detail or "")
        )
        dialog.show()
        QApplication.processEvents()
        return dialog

    def _volume_preview_request(self, mode=None):
        workbench = self.workbench
        if workbench.image_volume is None:
            return None
        shape = tuple(int(value) for value in workbench.image_volume.shape)
        mode = "drag" if mode == "drag" else "still"
        max_dim = self._active_volume_target_dim(mode)
        source_dtype = str(np.dtype(getattr(workbench.image_volume, "dtype", np.uint8)))
        preserve_source = mode == "still" and (self.state.volume_clarity_mode or workbench.current_volume_scope == "part")
        algorithm = self._volume_preview_algorithm(mode)
        roi_bbox = self._active_volume_roi_bbox(mode)
        roi_key = tuple(tuple(int(value) for value in pair) for pair in roi_bbox) if roi_bbox is not None else None
        if roi_bbox is not None:
            preserve_source = mode == "still" and (self.state.volume_clarity_mode or workbench.current_volume_scope == "part" or self._active_volume_roi_scale() > 1.0)
        owner = self._active_volume_cache_owner()
        _ = roi_key
        result = workbench.volume_preview_service.build_workbench_preview_request(
            owner=owner,
            shape=shape,
            source_dtype=source_dtype,
            max_dim=max_dim,
            preserve_source=preserve_source,
            algorithm=algorithm,
            roi_bbox=roi_bbox,
            texture_budget_bytes=self._roi_texture_budget_bytes(),
            mode=mode,
            message=self._volume_preview_progress_message(mode, roi_bbox),
        )
        if not result:
            return None
        return dict(result.payload.get("request") or {})

    def _volume_mask_preview_request(self, mode=None):
        workbench = self.workbench
        mask = self._active_part_mask_volume()
        if mask is None:
            return None
        shape = tuple(int(value) for value in getattr(mask, "shape", ()) or ())
        mode = "drag" if mode == "drag" else "still"
        max_dim = self._active_volume_target_dim(mode)
        mask_algorithm = "nearest" if mode == "drag" else "occupancy"
        roi_bbox = self._active_volume_roi_bbox(mode)
        if workbench.current_volume_scope == "full" and mask is workbench.part_preview_mask:
            roi_bbox = None
        owner = self._active_volume_cache_owner()
        result = workbench.volume_preview_service.build_mask_preview_request(
            owner=owner,
            shape=shape,
            source_dtype=str(np.dtype(getattr(mask, "dtype", np.uint16))),
            max_dim=max_dim,
            mask_identity=id(mask),
            algorithm=mask_algorithm,
            roi_bbox=roi_bbox,
            mode=mode,
            message=tt("Preparing mask preview...", workbench.lang),
        )
        if not result:
            return None
        return dict(result.payload.get("request") or {})

    def _cache_volume_preview_result(self, request, preview, build_ms=None):
        workbench = self.workbench
        if request is None or preview is None:
            return None
        cache_key = request["cache_key"]
        roi_bbox = request.get("roi_bbox")
        owner = request.get("owner")
        self.state.volume_preview_cache[cache_key] = preview
        self._touch_volume_cache_owner(owner)
        self._prune_volume_preview_cache()
        self.state.volume_preview = preview
        self.state.volume_preview_source_shape = cache_key
        self.state.volume_roi_preview_bbox = roi_bbox
        self.state.volume_roi_preview_source_shape = roi_shape_zyx(roi_bbox) if roi_bbox is not None else ()
        if build_ms is not None:
            self.state.volume_last_preview_build_ms = max(0.0, float(build_ms))
        return preview

    def _cache_volume_mask_preview_result(self, request, preview):
        workbench = self.workbench
        if request is None or preview is None:
            return None
        cache_key = request["cache_key"]
        self.state.volume_mask_preview_cache[cache_key] = preview
        self._touch_volume_cache_owner(request.get("owner"))
        self._prune_volume_preview_cache()
        return preview

    def _ensure_volume_preview(self, mode=None):
        workbench = self.workbench
        request = self._volume_preview_request(mode)
        if request is None:
            return None
        cache_key = request["cache_key"]
        roi_bbox = request.get("roi_bbox")
        cached = self.state.volume_preview_cache.get(cache_key)
        if cached is not None:
            self.state.volume_preview_cache.move_to_end(cache_key)
            self._touch_volume_cache_owner(request.get("owner"))
            self.state.volume_last_preview_build_ms = 0.0
            self.state.volume_preview = cached
            self.state.volume_preview_source_shape = cache_key
            self.state.volume_roi_preview_bbox = roi_bbox
            self.state.volume_roi_preview_source_shape = roi_shape_zyx(roi_bbox) if roi_bbox is not None else ()
            return cached

        mode = request["mode"]
        if self._should_show_volume_preview_progress(mode, roi_bbox):
            message = request.get("message") or tt("Preparing full-volume 3D preview...", workbench.lang)
            show_canvas_status = self._set_volume_canvas_status_text(message)
            self._update_volume_render_status_label(message)
            if show_canvas_status:
                QApplication.processEvents()
        build_start = time.perf_counter()
        if roi_bbox is not None:
            preview = build_roi_volume_preview(
                workbench.image_volume,
                roi_bbox,
                request["max_dim"],
                mode=request["algorithm"],
                preserve_source=request["preserve_source"],
                texture_budget_bytes=request["texture_budget_bytes"],
                max_texture_dim=GPU_VOLUME_MAX_TEXTURE_DIM,
            )
        else:
            preview = build_volume_preview(
                workbench.image_volume,
                request["max_dim"],
                mode=request["algorithm"],
                preserve_source=request["preserve_source"],
            )
        return self._cache_volume_preview_result(request, preview, (time.perf_counter() - build_start) * 1000.0)

    def _should_show_gpu_upload_progress(self, preview, mask_preview=None):
        workbench = self.workbench
        if self.state.volume_canvas_renderer != "gpu" or self.state.volume_render_mode == "drag":
            return False
        try:
            bytes_estimate = int(getattr(preview, "nbytes", 0) or 0)
            if mask_preview is not None:
                bytes_estimate += int(getattr(mask_preview, "nbytes", 0) or 0)
            return bytes_estimate >= 32 * 1024 * 1024
        except Exception:
            return True

    def _should_show_volume_mask_preview_progress(self, mode, mask):
        workbench = self.workbench
        if mode != "still" or workbench.display_mode != "volume" or mask is None:
            return False
        try:
            bytes_estimate = int(getattr(mask, "nbytes", 0) or 0)
            return bytes_estimate >= 32 * 1024 * 1024
        except Exception:
            return True

    def _mask_request_source_bytes(self, mask_request):
        workbench = self.workbench
        if not mask_request:
            return 0
        mask = self._active_part_mask_volume()
        if mask is None:
            return 0
        try:
            dtype_size = max(1, int(np.dtype(getattr(mask, "dtype", np.uint8)).itemsize))
            roi_bbox = mask_request.get("roi_bbox")
            if roi_bbox is not None:
                shape = roi_shape_zyx(roi_bbox)
            else:
                shape = tuple(int(value) for value in mask_request.get("shape") or getattr(mask, "shape", ()) or ())
            if len(shape) != 3 or min(shape) <= 0:
                return 0
            return int(shape[0]) * int(shape[1]) * int(shape[2]) * dtype_size
        except Exception:
            return 0

    def _should_build_mask_preview_in_background(self, mask_request):
        workbench = self.workbench
        if not mask_request or workbench.display_mode != "volume":
            return False
        if str(mask_request.get("mode") or "still") != "still":
            return False
        if self.state.volume_mask_preview_cache.get(mask_request.get("cache_key")) is not None:
            return False
        source_bytes = self._mask_request_source_bytes(mask_request)
        if source_bytes <= 0:
            return False
        return source_bytes >= TIF_GPU_STREAM_SYNC_MAX_BYTES

    def _cancel_volume_preview_build(self):
        workbench = self.workbench
        worker = (self.preview_build_worker if self.preview_build_worker is not None else None)
        if worker is not None and hasattr(worker, "cancel"):
            try:
                worker.cancel()
            except Exception:
                pass
        self.state.volume_preview_pending_token = 0
        self.state.volume_preview_pending_key = None
        self.state.volume_preview_pending_mask_key = None
        workbench._cancel_tif_task(self.state.volume_preview_build_task_id, "volume_preview_cancelled")
        self.state.volume_preview_build_task_id = ""
        self._set_volume_preview_build_controls_busy(False)

    def _cancel_and_wait_volume_preview_build(self, timeout_ms=2000):
        workbench = self.workbench
        thread = (self.preview_build_thread if self.preview_build_thread is not None else None)
        self._cancel_volume_preview_build()
        if thread is not None and thread.isRunning():
            thread.quit()
            return bool(thread.wait(int(max(0, timeout_ms))))
        return True

    def _cleanup_volume_preview_build_thread(self, thread=None, worker=None):
        workbench = self.workbench
        if thread is not None and self.preview_build_thread is not thread:
            return
        if worker is not None and self.preview_build_worker is not worker:
            return
        self.preview_build_thread = None
        self.preview_build_worker = None

    def _volume_preview_build_controls(self):
        workbench = self.workbench
        controls = []
        for name in (
            "volume_quality_slider",
            "volume_clarity_check",
            "volume_roi_detail_check",
            "volume_roi_source_combo",
            "volume_roi_inspect_check",
            "volume_roi_scale_slider",
            "volume_roi_budget_combo",
            "volume_mask_combo",
        ):
            control = getattr(workbench, name, None)
            if control is not None:
                controls.append(control)
        return controls

    def _set_volume_preview_build_controls_busy(self, busy):
        workbench = self.workbench
        busy = bool(busy)
        state_attr = "_volume_preview_busy_control_states"
        if busy:
            if self.state.volume_preview_busy_control_states:
                return
            states = []
            for control in self._volume_preview_build_controls():
                try:
                    states.append((control, bool(control.isEnabled())))
                    control.setEnabled(False)
                except RuntimeError:
                    continue
            self.state.volume_preview_busy_control_states = states
            return
        states = list(self.state.volume_preview_busy_control_states or [])
        self.state.volume_preview_busy_control_states = []
        for control, was_enabled in states:
            try:
                control.setEnabled(bool(was_enabled))
            except RuntimeError:
                continue
        if hasattr(workbench, "_set_scope_controls_enabled"):
            workbench._set_scope_controls_enabled()

    def _is_volume_preview_build_pending(self, preview_key, mask_key=None):
        workbench = self.workbench
        if self.preview_build_thread is None:
            return False
        return self.state.volume_preview_pending_key == preview_key and self.state.volume_preview_pending_mask_key == mask_key

    def _start_volume_preview_build(self, volume_request=None, mask_request=None):
        workbench = self.workbench
        if volume_request is None and mask_request is None:
            return False
        preview_key = volume_request.get("cache_key") if volume_request else None
        mask_key = mask_request.get("cache_key") if mask_request else None
        if self._is_volume_preview_build_pending(preview_key, mask_key):
            return True
        self._cancel_volume_preview_build()
        self.state.volume_preview_build_token += 1
        token = int(self.state.volume_preview_build_token)
        self.state.volume_preview_pending_token = token
        self.state.volume_preview_pending_key = preview_key
        self.state.volume_preview_pending_mask_key = mask_key
        message = (volume_request or {}).get("message") or tt("Preparing full-volume 3D preview...", workbench.lang)
        if mask_request and (volume_request is None or self.state.volume_preview_cache.get(preview_key) is not None):
            message = mask_request.get("message") or tt("Preparing mask preview...", workbench.lang)
        self.state.volume_preview_pending_message = str(message or "")
        self._set_volume_canvas_status_text(self.state.volume_preview_pending_message)
        self._update_volume_render_status_label(self.state.volume_preview_pending_message)
        self._set_volume_preview_build_controls_busy(True)
        task = workbench._start_tif_task(
            "volume_preview",
            action="build_preview",
            payload={"token": token, "preview_key": workbench._task_request_key(preview_key), "mask_key": workbench._task_request_key(mask_key)},
            request_key=workbench._task_request_key(preview_key or mask_key),
            message=self.state.volume_preview_pending_message,
        )
        self.state.volume_preview_build_task_id = task.task_id
        thread = QThread(workbench)
        worker = TifVolumePreviewBuildWorker(
            token,
            volume=workbench.image_volume,
            volume_request=volume_request,
            mask=self._active_part_mask_volume() if mask_request else None,
            mask_request=mask_request,
        )
        self.preview_build_thread = thread
        self.preview_build_worker = worker
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_volume_preview_build_progress)
        worker.finished.connect(self._on_volume_preview_build_finished)
        worker.failed.connect(self._on_volume_preview_build_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(lambda t=thread, w=worker: self._cleanup_volume_preview_build_thread(t, w))
        thread.finished.connect(thread.deleteLater)
        thread.start()
        return True

    def _on_volume_preview_build_progress(self, message):
        workbench = self.workbench
        token = int(getattr(self.state, "volume_preview_pending_token", 0) or 0)
        if token <= 0:
            return
        self.state.volume_preview_pending_message = str(message or "")
        if workbench.display_mode == "volume":
            self._set_volume_canvas_status_text(self.state.volume_preview_pending_message)
            self._update_volume_render_status_label(self.state.volume_preview_pending_message)

    def _on_volume_preview_build_finished(self, result):
        workbench = self.workbench
        result = dict(result or {})
        token = int(result.get("token", 0) or 0)
        if token != int(getattr(self.state, "volume_preview_pending_token", 0) or 0):
            return
        if not workbench._task_context_matches_current(
            self.state.volume_preview_build_task_id,
            fields=("specimen_id", "volume_scope", "part_id", "reslice_id", "display_mode"),
        ):
            workbench._cancel_tif_task(self.state.volume_preview_build_task_id, "stale_volume_preview_context")
            self.state.volume_preview_pending_token = 0
            self.state.volume_preview_pending_key = None
            self.state.volume_preview_pending_mask_key = None
            self.state.volume_preview_build_task_id = ""
            self._set_volume_preview_build_controls_busy(False)
            return
        self.state.volume_preview_pending_token = 0
        self.state.volume_preview_pending_key = None
        self.state.volume_preview_pending_mask_key = None
        self._set_volume_preview_build_controls_busy(False)
        if result.get("cancelled"):
            workbench._cancel_tif_task(self.state.volume_preview_build_task_id, "volume_preview_cancelled")
            self.state.volume_preview_build_task_id = ""
            return
        volume_request = result.get("volume_request") or {}
        mask_request = result.get("mask_request") or {}
        if result.get("preview") is not None:
            self._cache_volume_preview_result(volume_request, result.get("preview"), result.get("build_ms", 0.0))
        if result.get("mask_preview") is not None:
            self._cache_volume_mask_preview_result(mask_request, result.get("mask_preview"))
        workbench._finish_tif_task(self.state.volume_preview_build_task_id, payload={"token": token}, message="volume_preview_finished")
        self.state.volume_preview_build_task_id = ""
        if workbench.display_mode == "volume" and not getattr(self.state, "handling_gpu_volume_failure", False):
            self.render_volume_preview()

    def _on_volume_preview_build_failed(self, result):
        workbench = self.workbench
        result = dict(result or {})
        token = int(result.get("token", 0) or 0)
        if token != int(getattr(self.state, "volume_preview_pending_token", 0) or 0):
            return
        if not workbench._task_context_matches_current(
            self.state.volume_preview_build_task_id,
            fields=("specimen_id", "volume_scope", "part_id", "reslice_id", "display_mode"),
        ):
            workbench._cancel_tif_task(self.state.volume_preview_build_task_id, "stale_volume_preview_context")
            self.state.volume_preview_pending_token = 0
            self.state.volume_preview_pending_key = None
            self.state.volume_preview_pending_mask_key = None
            self.state.volume_preview_build_task_id = ""
            self._set_volume_preview_build_controls_busy(False)
            return
        self.state.volume_preview_pending_token = 0
        self.state.volume_preview_pending_key = None
        self.state.volume_preview_pending_mask_key = None
        self._set_volume_preview_build_controls_busy(False)
        error_text = str(result.get("error", ""))
        issue = workbench.preview_controller.classify_exception(
            RuntimeError(error_text),
            operation="volume_preview_build",
        )
        workbench.preview_controller.last_resource_issue = issue
        if str(getattr(issue, "kind", "")) == "gpu_preview":
            message = tt("GPU renderer failed. Using CPU fallback: {0}", workbench.lang).format(error_text)
        else:
            message = workbench.preview_controller.resource_issue_message(issue)
        workbench._fail_tif_task(self.state.volume_preview_build_task_id, result.get("error", ""), payload=result, message=message)
        self.state.volume_preview_build_task_id = ""
        self._update_volume_render_status_label(message)
        workbench.log(message)

    def _volume_preview_algorithm(self, mode=None):
        workbench = self.workbench
        mode = "drag" if mode == "drag" else "still"
        if mode == "drag":
            return "stride"
        return "hybrid"

    def _active_part_mask_volume(self):
        workbench = self.workbench
        if workbench.image_volume is None:
            return None
        if workbench.current_volume_scope == "full":
            if workbench.part_preview_mask is not None and self._active_part_preview_bbox() is not None:
                return workbench.part_preview_mask
            return None
        if workbench.current_volume_scope != "part":
            return None
        result_region_mask = self._active_result_region_mask_volume()
        if result_region_mask is not None:
            return result_region_mask
        if workbench.current_reslice_id:
            return None
        if workbench.part_preview_mask is not None and workbench.part_preview_mask.shape == workbench.image_volume.shape:
            return workbench.part_preview_mask
        if workbench.part_mask_volume is not None and workbench.part_mask_volume.shape == workbench.image_volume.shape:
            return workbench.part_mask_volume
        return None

    def _active_part_mask_likely_available(self):
        workbench = self.workbench
        if workbench.image_volume is None:
            return False
        mask = self._active_part_mask_volume()
        if mask is None:
            return False
        shape = tuple(int(value) for value in getattr(mask, "shape", ()) or ())
        if workbench.current_volume_scope == "full":
            part_preview_bbox = self._active_part_preview_bbox()
            if part_preview_bbox is None:
                return False
            try:
                image_shape = tuple(int(value) for value in roi_shape_zyx(part_preview_bbox))
            except Exception:
                return False
        else:
            image_shape = tuple(int(value) for value in getattr(workbench.image_volume, "shape", ()) or ())
        if shape != image_shape:
            return False
        if mask is workbench.part_preview_mask:
            return True
        if isinstance(mask, LazyRegionMaskVolume):
            return True
        if mask is workbench.part_mask_volume:
            part = workbench.project.get_part(workbench.current_specimen_id, workbench.current_part_id, default=None)
            if part is None:
                part = workbench.current_part if isinstance(workbench.current_part, dict) else {}
            status = str((part or {}).get("status") or "").lower()
            if status in TIF_MASK_PREVIEW_TRUSTED_STATUSES:
                return True
        try:
            source_bytes = int(getattr(mask, "nbytes", 0) or 0)
        except Exception:
            source_bytes = TIF_GPU_STREAM_SYNC_MAX_BYTES
        if source_bytes >= TIF_GPU_STREAM_SYNC_MAX_BYTES:
            return mask is not workbench.part_mask_volume
        return self._active_part_mask_has_voxels()

    def _active_result_region_mask_volume(self):
        workbench = self.workbench
        if workbench.current_volume_scope != "part" or workbench.image_volume is None:
            return None
        if not getattr(workbench, "result_region_combo", None):
            return None
        if hasattr(workbench, "training_mode_tabs") and workbench.training_mode_tabs.currentWidget() is not getattr(workbench, "result_compare_page", None):
            return None
        region_id = workbench.result_review_controller.result_region_id()
        if region_id <= 0:
            return None
        role = workbench.result_review_controller.result_source_role()
        source = None
        active_role = workbench.label_role_combo.currentData() if hasattr(workbench, "label_role_combo") else ""
        if role == "editable_ai_result" and workbench.edit_volume is not None and workbench.edit_volume.shape == workbench.image_volume.shape:
            source = workbench.edit_volume
        elif active_role == role and workbench.label_volume is not None and workbench.label_volume.shape == workbench.image_volume.shape:
            source = workbench.label_volume
        else:
            label_path = workbench.annotation_workflow_controller.current_part_label_path(role)
            if label_path and volume_sidecar_exists(label_path):
                try:
                    source = load_volume_sidecar(label_path, mmap_mode="r")
                except Exception:
                    source = None
        if source is None or getattr(source, "shape", None) != workbench.image_volume.shape:
            return None
        key = (
            workbench.current_specimen_id,
            workbench.current_part_id,
            workbench.current_reslice_id,
            role,
            int(region_id),
            str(getattr(source, "filename", "") or getattr(source, "path", "") or id(source)),
            tuple(int(value) for value in getattr(source, "shape", ()) or ()),
        )
        if key == workbench.result_review_controller.state.region_mask_cache_key:
            cached = workbench.result_review_controller.state.region_mask_cache.get(key)
            if cached is not None:
                return cached
        mask = LazyRegionMaskVolume(source, int(region_id))
        workbench.result_review_controller.state.region_mask_cache = {key: mask}
        workbench.result_review_controller.state.region_mask_cache_key = key
        return mask

    def _active_part_mask_has_voxels(self):
        workbench = self.workbench
        mask = self._active_part_mask_volume()
        if mask is None:
            return False
        try:
            shape = tuple(int(value) for value in getattr(mask, "shape", ()) or ())
            if len(shape) < 3:
                return bool(np.any(np.asarray(mask) > 0))
            plane_values = max(1, int(np.prod(shape[1:])))
            z_chunk = max(1, min(int(shape[0]), int((16 * 1024 * 1024) / plane_values)))
            for z0 in range(0, int(shape[0]), z_chunk):
                z1 = min(int(shape[0]), z0 + z_chunk)
                if np.any(np.asarray(mask[z0:z1]) > 0):
                    return True
            return False
        except Exception:
            return False

    def _ensure_volume_mask_preview(self, mode=None):
        workbench = self.workbench
        mask = self._active_part_mask_volume()
        if mask is None:
            return None
        request = self._volume_mask_preview_request(mode)
        if request is None:
            return None
        mode = request["mode"]
        roi_bbox = request.get("roi_bbox")
        cache_key = request["cache_key"]
        cached = self.state.volume_mask_preview_cache.get(cache_key)
        if cached is not None:
            self.state.volume_mask_preview_cache.move_to_end(cache_key)
            self._touch_volume_cache_owner(request.get("owner"))
            return cached
        if self._should_show_volume_mask_preview_progress(mode, mask):
            message = request.get("message") or tt("Preparing mask preview...", workbench.lang)
            show_canvas_status = self._set_volume_canvas_status_text(message)
            self._update_volume_render_status_label(message)
            if show_canvas_status:
                QApplication.processEvents()
        if roi_bbox is not None:
            preview = build_roi_mask_preview(mask, roi_bbox, request["max_dim"], mode=request["algorithm"], max_texture_dim=GPU_VOLUME_MAX_TEXTURE_DIM)
        else:
            preview = build_mask_preview(mask, request["max_dim"], mode=request["algorithm"])
        return self._cache_volume_mask_preview_result(request, preview)

    def _masked_volume_preview(self, preview, mask_preview):
        workbench = self.workbench
        if mask_preview is None or tuple(mask_preview.shape) != tuple(preview.shape):
            return preview
        owner = self._active_volume_cache_owner()
        cache_key = (
            owner,
            id(preview),
            id(mask_preview),
            tuple(int(value) for value in preview.shape),
            str(np.dtype(getattr(preview, "dtype", np.uint8))),
        )
        cached = self.state.volume_masked_preview_cache.get(cache_key)
        if cached is not None:
            self.state.volume_masked_preview_cache.move_to_end(cache_key)
            self._touch_volume_cache_owner(owner)
            return cached
        mask_values = np.asarray(mask_preview) > 0
        masked = np.ascontiguousarray(np.where(mask_values, preview, np.zeros_like(preview)))
        self.state.volume_masked_preview_cache[cache_key] = masked
        self._touch_volume_cache_owner(owner)
        self._prune_volume_preview_cache()
        return masked

    def _viewer_side_front_clip_mask(self, rotated_depth, front_clip):
        workbench = self.workbench
        depth = np.asarray(rotated_depth)
        if depth.size == 0:
            return np.zeros(depth.shape, dtype=bool)
        clip = max(0.0, min(0.92, float(front_clip)))
        if clip <= 0.0:
            return np.ones(depth.shape, dtype=bool)
        back_depth = float(np.min(depth))
        front_depth = float(np.max(depth))
        keep_depth = front_depth - (front_depth - back_depth) * clip
        return depth <= keep_depth

    def _mask_boundary_preview(self, mask_preview):
        workbench = self.workbench
        mask = np.asarray(mask_preview, dtype=bool)
        if mask.size == 0:
            return np.zeros_like(mask, dtype=bool)
        eroded = mask.copy()
        for axis in range(3):
            before = np.roll(mask, 1, axis=axis)
            after = np.roll(mask, -1, axis=axis)
            index_first = [slice(None)] * 3
            index_last = [slice(None)] * 3
            index_first[axis] = 0
            index_last[axis] = -1
            before[tuple(index_first)] = False
            after[tuple(index_last)] = False
            eroded &= before & after
        return mask & ~eroded

    def _normalize_volume_preview(self, source, preserve_source=False):
        workbench = self.workbench
        return normalize_preview_intensity(source, preserve_source=preserve_source)

    def _normalize_volume_preview_to_uint8(self, source):
        workbench = self.workbench
        return self._normalize_volume_preview(source, preserve_source=False)

    def _sample_volume_preview_values(self, preview, max_samples=1_000_000):
        workbench = self.workbench
        return sample_volume_values(preview, max_samples=max_samples)

    def _scale_volume_preview_to_uint8(self, preview, low, high):
        workbench = self.workbench
        return scale_volume_to_uint8(preview, low, high)

    def _volume_texture_target_dim(self):
        workbench = self.workbench
        if getattr(self.state, "volume_quality_drag_pending", False):
            requested = getattr(self.state, "volume_quality_committed_value", None)
        else:
            requested = None
        if requested is None:
            requested = int(workbench.volume_quality_slider.value())
        requested = max(8, int(requested))
        if self.state.volume_canvas_renderer == "gpu":
            return max(256, min(GPU_VOLUME_MAX_TEXTURE_DIM, requested))
        return max(32, min(128, requested))

    def _volume_render_state(self, mode=None):
        workbench = self.workbench
        mode = "drag" if mode == "drag" else "still"
        samples = self._active_volume_sample_count() if mode == "still" else int(workbench.volume_sample_slider.value())
        if mode == "drag":
            if self._volume_projection_mode() == "composite":
                samples = max(192, min(samples, 384))
            else:
                samples = max(256, min(samples, 768))
        gradient_opacity, gradient_opacity_range = self._volume_gradient_opacity_settings(mode)
        return {
            "cutoff_percent": workbench.volume_cutoff_slider.value(),
            "yaw": self.state.volume_yaw,
            "pitch": self.state.volume_pitch,
            "zoom": self.state.volume_zoom,
            "render_quality": self._active_volume_target_dim(mode),
            "sample_steps": samples,
            "inside_depth": float(workbench.volume_inside_slider.value()) / 100.0,
            "front_clip": float(workbench.volume_clip_slider.value()) / 100.0,
            "render_mode": mode,
            "pan_x": self.state.volume_pan_x,
            "pan_y": self.state.volume_pan_y,
            "clarity_mode": self.state.volume_clarity_mode,
            "projection_mode": self._volume_projection_mode(),
            "supersample_scale": self._active_volume_roi_scale(),
            "tint_rgb": tuple(float(value) for value in self._volume_tint_rgb()),
            "transfer_preset": self._volume_transfer_preset(),
            "transfer_opacity": self._volume_transfer_opacity(mode),
            "mask_mode": self._volume_mask_mode(),
            "mask_opacity": max(0.0, min(1.0, float(workbench.volume_mask_opacity_slider.value()) / 100.0)),
            "enhancement": self._volume_detail_enhancement(mode),
            "tone_gamma": self._volume_tone_gamma(),
            "shader_quality_mode": self._volume_shader_quality_mode(),
            "jitter_strength": self._volume_jitter_strength(mode),
            "adaptive_step_strength": self._volume_adaptive_step_strength(mode),
            "gradient_opacity": gradient_opacity,
            "gradient_opacity_range": gradient_opacity_range,
            "surface_refine": bool(workbench.volume_surface_refine_check.isChecked()),
            "clip_plane_enabled": bool(workbench.volume_clip_plane_check.isChecked()),
            "clip_plane_depth": float(workbench.volume_clip_plane_depth_slider.value()) / 100.0,
            "clip_plane_normal": self._volume_clip_plane_normal(),
        }

    def _sync_gpu_volume_canvas(self, preview, mask_preview=None, mask_mode=None, volume_request=None, mask_request=None):
        workbench = self.workbench
        if self.state.volume_canvas_renderer != "gpu" or not hasattr(workbench.volume_canvas, "set_volume_data"):
            return False
        mask_mode = mask_mode if mask_mode in {"mask_boundary", "masked_image"} else "image_only"
        if mask_mode != "image_only" and not hasattr(workbench.volume_canvas, "set_mask_data"):
            return False
        source_shape, spacing_zyx = self._volume_source_geometry()
        mode = "drag" if self.state.volume_render_mode == "drag" else "still"
        state = self._volume_render_state(mode)
        state["mask_mode"] = mask_mode
        if hasattr(workbench.volume_canvas, "set_axis_overlays"):
            workbench.volume_canvas.set_axis_overlays(workbench.local_axis_controller.volume_overlays())
        if self._should_show_gpu_upload_progress(preview, mask_preview if mask_mode != "image_only" else None):
            message = tt("Uploading 3D preview to GPU...", workbench.lang)
            show_canvas_status = self._set_volume_canvas_status_text(message)
            self._update_volume_render_status_label(message)
            if show_canvas_status:
                QApplication.processEvents()
        if hasattr(workbench.volume_canvas, "set_volume_render_inputs"):
            workbench.volume_canvas.set_volume_render_inputs(
                preview,
                mask=mask_preview if mask_mode != "image_only" else None,
                render_state=state,
                source_shape=source_shape,
                spacing_zyx=spacing_zyx,
                volume_cache_key=(volume_request or {}).get("cache_key"),
                mask_cache_key=(mask_request or {}).get("cache_key") if mask_mode != "image_only" else None,
            )
            return True
        try:
            workbench.volume_canvas.set_volume_data(
                preview,
                source_shape=source_shape,
                spacing_zyx=spacing_zyx,
                cache_key=(volume_request or {}).get("cache_key"),
            )
        except TypeError:
            workbench.volume_canvas.set_volume_data(preview, source_shape=source_shape, spacing_zyx=spacing_zyx)
        if hasattr(workbench.volume_canvas, "set_mask_data"):
            try:
                workbench.volume_canvas.set_mask_data(
                    mask_preview if mask_mode != "image_only" else None,
                    cache_key=(mask_request or {}).get("cache_key") if mask_mode != "image_only" else None,
                )
            except TypeError:
                workbench.volume_canvas.set_mask_data(mask_preview if mask_mode != "image_only" else None)
        if hasattr(workbench.volume_canvas, "set_render_state"):
            workbench.volume_canvas.set_render_state(**state)
        return True

    def _gpu_volume_source_for_request(self, volume_request):
        workbench = self.workbench
        if workbench.image_volume is None:
            return None, (), None
        roi_bbox = (volume_request or {}).get("roi_bbox")
        if roi_bbox is None:
            return workbench.image_volume, tuple(int(value) for value in workbench.image_volume.shape), None
        try:
            z_pair, y_pair, x_pair = normalize_roi_bbox_zyx(roi_bbox, workbench.image_volume.shape)
            source = workbench.image_volume[int(z_pair[0]):int(z_pair[1]), int(y_pair[0]):int(y_pair[1]), int(x_pair[0]):int(x_pair[1])]
            shape = tuple(int(value) for value in getattr(source, "shape", ()) or ())
            if len(shape) != 3 or min(shape) <= 0:
                return None, (), None
            return source, shape, (tuple(int(value) for value in z_pair), tuple(int(value) for value in y_pair), tuple(int(value) for value in x_pair))
        except Exception:
            return None, (), None

    def _volume_request_source_bytes(self, volume_request):
        workbench = self.workbench
        if workbench.image_volume is None or not volume_request:
            return 0
        try:
            dtype_size = max(1, int(np.dtype(getattr(workbench.image_volume, "dtype", np.uint8)).itemsize))
            roi_bbox = volume_request.get("roi_bbox")
            if roi_bbox is not None:
                shape = roi_shape_zyx(roi_bbox)
            else:
                shape = tuple(int(value) for value in getattr(workbench.image_volume, "shape", ()) or ())
            if len(shape) != 3 or min(shape) <= 0:
                return 0
            return int(shape[0]) * int(shape[1]) * int(shape[2]) * dtype_size
        except Exception:
            return 0

    def _should_build_volume_preview_in_background(self, volume_request):
        workbench = self.workbench
        if not volume_request or workbench.display_mode != "volume":
            return False
        if str(volume_request.get("mode") or "still") != "still":
            return False
        if self.state.volume_preview_cache.get(volume_request.get("cache_key")) is not None:
            return False
        if (
            workbench.current_volume_scope == "full"
            and volume_request.get("roi_bbox") is None
            and self.state.volume_canvas_renderer == "gpu"
            and hasattr(workbench.volume_canvas, "build_volume_texture_from_source")
        ):
            return False
        source_bytes = self._volume_request_source_bytes(volume_request)
        if source_bytes <= 0:
            return False
        return source_bytes >= TIF_GPU_STREAM_SYNC_MAX_BYTES

    def _gpu_mask_source_for_request(self, mask_request):
        workbench = self.workbench
        mask = self._active_part_mask_volume()
        if mask is None:
            return None, (), None
        shape = tuple(int(value) for value in getattr(mask, "shape", ()) or ())
        if len(shape) != 3 or min(shape) <= 0:
            return None, (), None
        roi_bbox = (mask_request or {}).get("roi_bbox")
        if roi_bbox is None:
            return mask, shape, None
        try:
            z_pair, y_pair, x_pair = normalize_roi_bbox_zyx(roi_bbox, shape)
            source = mask[int(z_pair[0]):int(z_pair[1]), int(y_pair[0]):int(y_pair[1]), int(x_pair[0]):int(x_pair[1])]
            source_shape = tuple(int(value) for value in getattr(source, "shape", ()) or ())
            if len(source_shape) != 3 or min(source_shape) <= 0:
                return None, (), None
            return source, source_shape, (tuple(int(value) for value in z_pair), tuple(int(value) for value in y_pair), tuple(int(value) for value in x_pair))
        except Exception:
            return None, (), None

    def _try_build_mask_gpu_texture(self, mask_request):
        workbench = self.workbench
        if not mask_request or not hasattr(workbench.volume_canvas, "build_mask_texture_from_source"):
            return False
        source, source_shape, _normalized_roi_bbox = self._gpu_mask_source_for_request(mask_request)
        if source is None:
            return False
        self._begin_volume_preview_ui_wait()
        try:
            return bool(
                workbench.volume_canvas.build_mask_texture_from_source(
                    source,
                    int(mask_request.get("max_dim", 1024)),
                    algorithm=str(mask_request.get("algorithm", "occupancy")),
                    cache_key=mask_request.get("cache_key"),
                    source_shape=source_shape,
                )
            )
        except Exception as exc:
            self.state.volume_last_stats = dict(getattr(self.state, "volume_last_stats", {}) or {})
            self.state.volume_last_stats["gpu_mask_build_error"] = str(exc)
            workbench.preview_controller.last_resource_issue = workbench.preview_controller.classify_exception(exc, operation="gpu_mask_texture")
            return False
        finally:
            self._end_volume_preview_ui_wait()

    def _try_build_volume_gpu_texture(self, volume_request, mask_mode="image_only", mask_request=None, mask_preview=None):
        workbench = self.workbench
        if not volume_request or workbench.image_volume is None:
            return False
        if self.state.volume_canvas_renderer != "gpu" or not hasattr(workbench.volume_canvas, "build_volume_texture_from_source"):
            return False
        if self.state.volume_render_mode == "drag" or str(volume_request.get("mode") or "") == "drag":
            return False
        supports_streamed_mask = bool(mask_mode != "image_only" and mask_request is not None and hasattr(workbench.volume_canvas, "build_mask_texture_from_source"))
        supports_mask_preview_upload = bool(mask_mode != "image_only" and hasattr(workbench.volume_canvas, "set_mask_data"))
        if mask_mode != "image_only" and not (supports_streamed_mask or supports_mask_preview_upload):
            return False
        message = volume_request.get("message") or tt("Preparing full-volume 3D preview...", workbench.lang)
        self._update_volume_render_status_label(message)
        source, request_source_shape, normalized_roi_bbox = self._gpu_volume_source_for_request(volume_request)
        if source is None:
            return False
        use_streamed_mask = supports_streamed_mask and (mask_preview is None or not supports_mask_preview_upload)
        if mask_mode != "image_only" and not use_streamed_mask and mask_preview is None and mask_request is not None:
            mask_preview = self.state.volume_mask_preview_cache.get(mask_request.get("cache_key"))
            if mask_preview is None:
                if self._should_show_volume_mask_preview_progress(str(mask_request.get("mode") or "still"), self._active_part_mask_volume()):
                    return False
                else:
                    mask_preview = self._ensure_volume_mask_preview(str(mask_request.get("mode") or "still"))
        if mask_mode != "image_only" and mask_preview is None and not use_streamed_mask:
            mask_mode = "image_only"
        source_shape, spacing_zyx = self._volume_source_geometry()
        if normalized_roi_bbox is not None:
            source_shape = tuple(int(value) for value in request_source_shape)
        state = self._volume_render_state("still")
        state["mask_mode"] = mask_mode
        self._begin_volume_preview_ui_wait()
        try:
            provider = workbench.volume_canvas.build_volume_texture_from_source(
                source,
                int(volume_request.get("max_dim", 1024)),
                algorithm=str(volume_request.get("algorithm", "hybrid")),
                preserve_source=bool(volume_request.get("preserve_source", False)),
                cache_key=volume_request.get("cache_key"),
                source_shape=source_shape,
                spacing_zyx=spacing_zyx,
            )
        except Exception as exc:
            self.state.volume_last_stats = dict(getattr(self.state, "volume_last_stats", {}) or {})
            self.state.volume_last_stats["gpu_preview_build_error"] = str(exc)
            workbench.preview_controller.last_resource_issue = workbench.preview_controller.classify_exception(exc, operation="gpu_volume_texture")
            return False
        finally:
            self._end_volume_preview_ui_wait()
        if provider is None:
            return False
        self.state.volume_preview = None
        self.state.volume_preview_source_shape = volume_request.get("cache_key")
        self.state.volume_roi_preview_bbox = normalized_roi_bbox
        self.state.volume_roi_preview_source_shape = tuple(int(value) for value in request_source_shape) if normalized_roi_bbox is not None else ()
        self.state.volume_last_preview_build_ms = 0.0
        if hasattr(workbench.volume_canvas, "set_axis_overlays"):
            workbench.volume_canvas.set_axis_overlays(workbench.local_axis_controller.volume_overlays())
        if mask_mode != "image_only" and use_streamed_mask:
            if not self._try_build_mask_gpu_texture(mask_request):
                mask_mode = "image_only"
                state["mask_mode"] = "image_only"
        elif (mask_mode == "image_only" and hasattr(workbench.volume_canvas, "set_mask_data")) or (
            supports_mask_preview_upload and mask_preview is not None
        ):
            try:
                workbench.volume_canvas.set_mask_data(
                    mask_preview if mask_mode != "image_only" else None,
                    cache_key=(mask_request or {}).get("cache_key") if mask_mode != "image_only" else None,
                )
            except TypeError:
                workbench.volume_canvas.set_mask_data(mask_preview if mask_mode != "image_only" else None)
        if hasattr(workbench.volume_canvas, "set_render_state"):
            workbench.volume_canvas.set_render_state(**state)
        if hasattr(workbench.volume_canvas, "render_stats"):
            self.state.volume_last_stats = dict(workbench.volume_canvas.render_stats() or {})
        return True

    def _try_build_full_volume_gpu_texture(self, volume_request, mask_mode="image_only"):
        workbench = self.workbench
        return self._try_build_volume_gpu_texture(volume_request, mask_mode=mask_mode)

    def _request_volume_interaction_render(self):
        workbench = self.workbench
        if workbench.display_mode != "volume":
            return
        self.state.volume_interaction_render_pending = True
        if self.state.volume_interaction_render_scheduled:
            return
        self.state.volume_interaction_render_scheduled = True

        def run():
            self.state.volume_interaction_render_scheduled = False
            if not self.state.volume_interaction_render_pending:
                return
            self.state.volume_interaction_render_pending = False
            self._render_volume_interaction_preview()

        delay_ms = int(self.state.volume_interaction_render_interval_ms)
        if self.state.volume_canvas_renderer != "gpu":
            delay_ms = max(delay_ms, 80)
        QTimer.singleShot(delay_ms, run)

    def _render_volume_interaction_preview(self):
        workbench = self.workbench
        if workbench.display_mode != "volume" or workbench.image_volume is None:
            return
        if self._sync_gpu_volume_camera_only():
            self._update_volume_render_status_label()
            return
        self.render_volume_preview()

    def _sync_gpu_volume_camera_only(self):
        workbench = self.workbench
        if self.state.volume_canvas_renderer != "gpu" or not hasattr(workbench.volume_canvas, "set_render_state"):
            return False
        if not callable(getattr(workbench.volume_canvas, "has_volume", None)) or not workbench.volume_canvas.has_volume():
            return False
        mode = "drag" if self.state.volume_render_mode == "drag" else "still"
        state = self._volume_render_state(mode)
        state["mask_mode"] = self._volume_mask_mode()
        if hasattr(workbench.volume_canvas, "set_axis_overlays"):
            workbench.volume_canvas.set_axis_overlays(workbench.local_axis_controller.volume_overlays())
        if callable(getattr(workbench.volume_canvas, "set_interaction_render_state", None)):
            workbench.volume_canvas.set_interaction_render_state(**state)
        else:
            workbench.volume_canvas.set_render_state(**state)
        return True

    def _volume_source_geometry(self):
        workbench = self.workbench
        shape = tuple(int(value) for value in getattr(workbench.image_volume, "shape", ()) or ())
        spacing = ()
        roi_shape = tuple(int(value) for value in getattr(self.state, "volume_roi_preview_source_shape", ()) or ())
        if len(roi_shape) == 3 and min(roi_shape) > 0:
            shape = roi_shape
        if workbench.current_volume_scope == "part" and workbench.current_reslice_id:
            reslice = workbench.local_axis_controller.current_part_reslice_record()
            if isinstance(reslice, dict):
                outputs = reslice.get("outputs") if isinstance(reslice.get("outputs"), dict) else {}
                params = reslice.get("reslice_params") if isinstance(reslice.get("reslice_params"), dict) else {}
                record_shape = outputs.get("image_shape_zyx") or params.get("output_shape_zyx") or []
                try:
                    record_shape = tuple(int(value) for value in record_shape)
                except (TypeError, ValueError):
                    record_shape = ()
                if len(record_shape) == 3 and min(record_shape) > 0:
                    shape = record_shape
                record_spacing = params.get("output_spacing_zyx") or []
                try:
                    record_spacing = tuple(float(value) for value in record_spacing)
                except (TypeError, ValueError):
                    record_spacing = ()
                if len(record_spacing) == 3 and min(record_spacing) > 0:
                    spacing = record_spacing
                return shape, spacing
        if workbench.current_volume_scope == "part":
            record = ((workbench.current_part or {}).get("image") or {})
        else:
            specimen = workbench.project.get_specimen(workbench.current_specimen_id, default=None) if workbench.current_specimen_id else None
            record = (specimen or {}).get("working_volume") or {}
        record_shape = record.get("shape_zyx") or []
        try:
            record_shape = tuple(int(value) for value in record_shape)
        except (TypeError, ValueError):
            record_shape = ()
        if not roi_shape and len(record_shape) == 3 and min(record_shape) > 0:
            shape = record_shape
        record_spacing = record.get("spacing_zyx") or []
        try:
            record_spacing = tuple(float(value) for value in record_spacing)
        except (TypeError, ValueError):
            record_spacing = ()
        if len(record_spacing) == 3 and min(record_spacing) > 0:
            spacing = record_spacing
        return shape, spacing

    def schedule_volume_preview_render(self):
        workbench = self.workbench
        if getattr(self.state, "volume_render_scheduled", False):
            return
        self.state.volume_render_scheduled = True

        def run():
            self.state.volume_render_scheduled = False
            if workbench.display_mode == "volume" and not getattr(self.state, "handling_gpu_volume_failure", False):
                self.render_volume_preview()

        QTimer.singleShot(0, run)

    def flush_selection_render(self):
        if not bool(getattr(self.state, "selection_render_pending", False)):
            return False
        self.state.selection_render_pending = False
        if self.workbench.display_mode != "volume":
            return False
        QTimer.singleShot(0, self.render_volume_preview)
        return True

    def render_volume_preview(self):
        workbench = self.workbench
        if bool(getattr(workbench, "_loading_specimen", False)):
            self.state.selection_render_pending = True
            return
        if not hasattr(workbench, "volume_canvas"):
            return
        if getattr(self.state, "handling_gpu_volume_failure", False):
            return
        if bool(getattr(self.state, "defer_volume_preview_render_once", False)):
            self.state.defer_volume_preview_render_once = False
            if workbench.display_mode == "volume":
                message = tt("Preparing full-volume 3D preview...", workbench.lang)
                self._set_volume_canvas_status_text(message)
                self._update_volume_render_status_label(message)
                QTimer.singleShot(0, self.render_volume_preview)
            return
        if workbench.display_mode == "volume":
            workbench._ensure_volume_canvas()
        if workbench.image_volume is None:
            specimen = workbench.project.get_specimen(workbench.current_specimen_id, default=None) if workbench.current_specimen_id else None
            message = workbench._volume_unavailable_message(specimen)
            if hasattr(workbench.volume_canvas, "set_axis_overlays"):
                workbench.volume_canvas.set_axis_overlays([])
            workbench.volume_canvas.clear()
            workbench.volume_canvas.setText(message)
            self._update_volume_render_status_label(message)
            return
        mode = "drag" if self.state.volume_render_mode == "drag" else "still"
        volume_request = self._volume_preview_request(mode)
        if volume_request is not None:
            self._update_volume_render_status_label(
                volume_request.get("message") or self._volume_preview_progress_message(mode, volume_request.get("roi_bbox"))
            )
        else:
            self._update_volume_render_status_label(tt("Building 3D preview...", workbench.lang))
        preview = None
        if volume_request is not None:
            preview = self.state.volume_preview_cache.get(volume_request["cache_key"])
            if preview is not None:
                self.state.volume_preview_cache.move_to_end(volume_request["cache_key"])
                self._touch_volume_cache_owner(volume_request.get("owner"))
                self.state.volume_preview = preview
                self.state.volume_preview_source_shape = volume_request["cache_key"]
                roi_bbox = volume_request.get("roi_bbox")
                self.state.volume_roi_preview_bbox = roi_bbox
                self.state.volume_roi_preview_source_shape = roi_shape_zyx(roi_bbox) if roi_bbox is not None else ()
            elif mode == "still" and workbench.display_mode == "volume":
                mask_mode_for_gpu = self._volume_mask_mode()
                mask_request_for_gpu = None
                mask_preview_for_gpu = None
                if mask_mode_for_gpu != "image_only":
                    mask_request_for_gpu = self._volume_mask_preview_request(mode)
                    if mask_request_for_gpu is not None:
                        mask_preview_for_gpu = self.state.volume_mask_preview_cache.get(mask_request_for_gpu["cache_key"])
                        if mask_preview_for_gpu is not None:
                            self.state.volume_mask_preview_cache.move_to_end(mask_request_for_gpu["cache_key"])
                            self._touch_volume_cache_owner(mask_request_for_gpu.get("owner"))
                if self._should_build_volume_preview_in_background(volume_request):
                    self._start_volume_preview_build(volume_request=volume_request, mask_request=mask_request_for_gpu)
                    return
                if (
                    mask_request_for_gpu is not None
                    and mask_preview_for_gpu is None
                    and self._should_build_mask_preview_in_background(mask_request_for_gpu)
                ):
                    self._start_volume_preview_build(mask_request=mask_request_for_gpu)
                    return
                if self._try_build_volume_gpu_texture(
                    volume_request,
                    mask_mode=mask_mode_for_gpu,
                    mask_request=mask_request_for_gpu,
                    mask_preview=mask_preview_for_gpu,
                ):
                    self._update_volume_render_status_label()
                    return
                if self._should_show_volume_preview_progress(mode, volume_request.get("roi_bbox")):
                    self._start_volume_preview_build(volume_request=volume_request)
                    return
        if preview is None:
            preview = self._ensure_volume_preview(mode)
        if preview is None:
            if hasattr(workbench.volume_canvas, "set_axis_overlays"):
                workbench.volume_canvas.set_axis_overlays([])
            workbench.volume_canvas.clear()
            workbench.volume_canvas.setText(tt("No TIF volume loaded", workbench.lang))
            self._update_volume_render_status_label(tt("No TIF volume loaded", workbench.lang))
            return
        mask_mode = self._volume_mask_mode()
        mask_preview = None
        mask_request = None
        if mask_mode != "image_only":
            mask_request = self._volume_mask_preview_request(mode)
            if mask_request is not None:
                mask_preview = self.state.volume_mask_preview_cache.get(mask_request["cache_key"])
                if mask_preview is not None:
                    self.state.volume_mask_preview_cache.move_to_end(mask_request["cache_key"])
                    self._touch_volume_cache_owner(mask_request.get("owner"))
                elif mode == "still" and workbench.display_mode == "volume":
                    if self._should_build_mask_preview_in_background(mask_request):
                        self._start_volume_preview_build(mask_request=mask_request)
                        return
            if mask_preview is None:
                mask_preview = self._ensure_volume_mask_preview(mode)
        if mask_preview is None and mask_mode != "image_only":
            mask_mode = "image_only"
        self._try_restore_gpu_volume_canvas()
        if self._sync_gpu_volume_canvas(
            preview,
            mask_preview=mask_preview,
            mask_mode=mask_mode,
            volume_request=volume_request,
            mask_request=mask_request,
        ):
            self._update_volume_render_status_label()
            return
        if mask_mode != "image_only" and not hasattr(workbench.volume_canvas, "set_volume_pixmap"):
            self._switch_volume_canvas_to_cpu("Mask inspection uses CPU fallback.")
        pixmap = self._render_volume_preview_pixmap(preview, mask_preview=mask_preview, mask_mode=mask_mode)
        if hasattr(workbench.volume_canvas, "set_axis_overlays"):
            workbench.volume_canvas.set_axis_overlays(workbench.local_axis_controller.volume_overlays())
        workbench.volume_canvas.set_volume_pixmap(pixmap)
        self._update_volume_render_status_label()

    def _render_volume_preview_pixmap(self, preview, mask_preview=None, mask_mode="image_only"):
        workbench = self.workbench
        max_value = float(np.iinfo(preview.dtype).max) if np.issubdtype(preview.dtype, np.integer) else 1.0
        projection_mode = self._volume_projection_mode()
        cutoff = float(workbench.volume_cutoff_slider.value()) / 100.0
        mask_mode = mask_mode if mask_mode in {"mask_boundary", "masked_image"} else "image_only"
        mask_values = None
        if mask_preview is not None and tuple(mask_preview.shape) == tuple(preview.shape):
            mask_values = np.asarray(mask_preview) > 0
        render_source = preview
        if mask_mode == "masked_image" and mask_values is not None:
            render_source = np.where(mask_values, preview, np.zeros_like(preview))
        if projection_mode == "minip":
            threshold = int(round(cutoff * max_value))
            points = np.argwhere((render_source > 0) & (render_source <= max(1, threshold)))
        elif projection_mode == "average":
            threshold = int(round(max(0.0, cutoff * 0.65) * max_value))
            points = np.argwhere(render_source > threshold)
        else:
            threshold = int(round(cutoff * max_value / (1.25 if projection_mode == "surface" else 1.0)))
            points = np.argwhere(render_source > threshold)
        if points.size == 0:
            points = np.argwhere(render_source > 0)
        if points.size == 0:
            center_slice = np.asarray(render_source[int(render_source.shape[0] // 2)], dtype=np.uint8)
            return workbench._render_slice_pixmap(center_slice)

        point_indices = points.copy()
        values = render_source[points[:, 0], points[:, 1], points[:, 2]].astype(np.float32)
        if projection_mode == "minip":
            values = max_value - values
        if max_value > 255.0:
            values = values * (255.0 / max_value)
        source_shape, spacing_zyx = self._volume_source_geometry()
        x_scale, y_scale, z_scale = volume_shape_scale(source_shape or preview.shape, spacing_zyx)
        dims = np.array([max(1, preview.shape[0] - 1), max(1, preview.shape[1] - 1), max(1, preview.shape[2] - 1)], dtype=np.float32)
        coords = points.astype(np.float32) / dims
        coords = coords[:, [2, 1, 0]] - 0.5
        coords[:, 0] *= x_scale
        coords[:, 1] *= y_scale
        coords[:, 2] *= z_scale

        yaw = math.radians(self.state.volume_yaw)
        pitch = math.radians(self.state.volume_pitch)
        cy, sy = math.cos(yaw), math.sin(yaw)
        cp, sp = math.cos(pitch), math.sin(pitch)
        rot_yaw = np.array([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]], dtype=np.float32)
        rot_pitch = np.array([[1.0, 0.0, 0.0], [0.0, cp, -sp], [0.0, sp, cp]], dtype=np.float32)
        rotated = coords @ (rot_yaw @ rot_pitch).T
        front_clip = max(0.0, min(0.92, float(workbench.volume_clip_slider.value()) / 100.0))
        if front_clip > 0.0:
            keep = self._viewer_side_front_clip_mask(rotated[:, 2], front_clip)
            if np.any(keep):
                rotated = rotated[keep]
                values = values[keep]
                point_indices = point_indices[keep]
            else:
                pixmap = QPixmap(360, 360)
                pixmap.fill(QColor(_tif_canvas_background(workbench.current_theme)))
                return pixmap

        out_size = 360
        scale = (out_size * 0.78) * float(self.state.volume_zoom)
        pan_scale = out_size * 0.5
        center_x = out_size / 2.0 + self.state.volume_pan_x * pan_scale
        center_y = out_size / 2.0 - self.state.volume_pan_y * pan_scale
        px = np.round(rotated[:, 0] * scale + center_x).astype(np.int32)
        py = np.round(-rotated[:, 1] * scale + center_y).astype(np.int32)
        inside = (px >= 0) & (px < out_size) & (py >= 0) & (py < out_size)
        if not np.any(inside):
            pixmap = QPixmap(out_size, out_size)
            pixmap.fill(QColor(_tif_canvas_background(workbench.current_theme)))
            return pixmap

        px = px[inside]
        py = py[inside]
        depth = rotated[:, 2][inside]
        values = values[inside]
        point_indices = point_indices[inside]

        image = np.zeros((out_size, out_size, 3), dtype=np.uint8)
        shade = 0.65 + 0.35 * np.clip((depth - depth.min()) / max(1e-6, depth.max() - depth.min()), 0.0, 1.0)
        lut = self._volume_transfer_lut()[0]
        lut_index = np.clip(np.round(values), 0, lut.shape[0] - 1).astype(np.int32)
        opacity = lut[lut_index, 3].astype(np.float32) / 255.0
        color_float = lut[lut_index, :3].astype(np.float32) * shade[:, None] * (0.38 + 0.62 * opacity[:, None])
        color = np.clip(color_float, 0, 255).astype(np.uint8)
        if mask_mode == "mask_boundary" and mask_values is not None:
            boundary = self._mask_boundary_preview(mask_values)
            boundary_values = boundary[point_indices[:, 0], point_indices[:, 1], point_indices[:, 2]]
            if np.any(boundary_values):
                opacity = max(0.0, min(1.0, float(workbench.volume_mask_opacity_slider.value()) / 100.0))
                mask_color = np.asarray([255, 142, 66], dtype=np.float32)
                color_float = color.astype(np.float32)
                color_float[boundary_values] = (1.0 - opacity) * color_float[boundary_values] + opacity * mask_color
                color = np.clip(color_float, 0, 255).astype(np.uint8)
        flat_index = py * out_size + px
        flat = image.reshape((-1, 3))
        for channel in range(3):
            np.maximum.at(flat[:, channel], flat_index, color[:, channel])
        for off_x, off_y in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx = px + off_x
            ny = py + off_y
            neighbor = (nx >= 0) & (nx < out_size) & (ny >= 0) & (ny < out_size)
            if np.any(neighbor):
                nidx = ny[neighbor] * out_size + nx[neighbor]
                ncolor = (color[neighbor].astype(np.float32) * 0.42).astype(np.uint8)
                for channel in range(3):
                    np.maximum.at(flat[:, channel], nidx, ncolor[:, channel])
        qimage = QImage(np.ascontiguousarray(image).data, out_size, out_size, out_size * 3, QImage.Format_RGB888).copy()
        return QPixmap.fromImage(qimage)
