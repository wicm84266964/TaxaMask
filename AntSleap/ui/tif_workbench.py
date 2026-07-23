import json
import math
import os
import time
from collections import OrderedDict
from datetime import datetime

import numpy as np
import tifffile
from PySide6.QtCore import QEvent, QEventLoop, QObject, QPointF, QRect, QRectF, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QImage, QKeySequence, QPainter, QPen, QPixmap, QPolygonF, QShortcut, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QAbstractItemView,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QProgressBar,
    QRadioButton,
    QScrollArea,
    QSlider,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

try:
    from AntSleap.core.safe_io import atomic_write_json
    from AntSleap.core.amira_import import import_amira_directory
    from AntSleap.core.tif_backend import DEFAULT_TIF_BACKEND_CONFIG, TifBackendRunner, nnunet_v2_tif_backend_preset, normalize_tif_backend_runtime_config, sanitize_tif_backend_config
    from AntSleap.core.tif_export import export_tif_part_training_dataset, export_tif_training_dataset
    from AntSleap.core.tif_label_guard import can_write_label_role, require_editable_label_role
    from AntSleap.core.tif_materials import next_material_id, read_material_map, remove_material, upsert_material, write_material_map
    from AntSleap.core.tif_part_extraction import (
        add_rectangular_keyframe,
        add_polygon_keyframe,
        build_preview_mask_from_contours,
        crop_volume_to_part,
        delete_keyframe,
        export_part_package,
        neighboring_keyframe_indices,
        read_contours_json,
        signed_distance,
        validate_contours_for_interpolation,
        write_contours_json,
        write_part_mask,
    )
    from AntSleap.core.tif_prediction_import import default_prediction_id_for_tif, import_external_prediction_tif
    from AntSleap.core.tif_project import TifProjectManager
    from AntSleap.core.tif_stack_import import import_tif_stack, materialize_registered_tif_stack, register_tif_stack_metadata
    from AntSleap.core.tif_roi_preview import DEFAULT_ROI_TEXTURE_BUDGET_BYTES, HIGH_ROI_TEXTURE_BUDGET_BYTES, build_roi_mask_preview, build_roi_volume_preview, normalize_roi_bbox_zyx, roi_shape_zyx
    from AntSleap.core.tif_volume_io import create_empty_label_sidecar_like, create_volume_sidecar_memmap, flush_volume_array, load_volume_sidecar, volume_sidecar_exists
    from AntSleap.core.tif_volume_preview import (
        build_mask_preview,
        build_volume_preview,
        normalize_preview_intensity,
        scale_volume_to_uint8,
        sample_volume_values,
    )
    from AntSleap.core.tif_local_axis_ai import export_local_axis_training_manifest
    from AntSleap.core.tif_local_axis_reslice import source_point_to_reslice_point
    from AntSleap.services.tif_backend_workflow_service import TifBackendWorkflowService
    from AntSleap.services.tif_label_edit_service import TifLabelEditService
    from AntSleap.services.tif_local_axis_service import TifLocalAxisService
    from AntSleap.services.tif_roi_part_service import TifRoiPartService
    from AntSleap.services.tif_selection_controller import TifSelectionController
    from AntSleap.services.tif_task_manager import TifTaskManager
    from AntSleap.services.tif_truth_promotion_service import TifTruthPromotionService
    from AntSleap.services.tif_volume_preview_service import TifVolumePreviewService
    from AntSleap.services.tif_workbench_states import TifBackendState, TifEditState, TifLocalAxisState, TifPreviewState, TifRoiState
    from AntSleap.ui.style import normalize_theme
    from AntSleap.ui.tif_agent_context import TifAgentContextBuilder
    from AntSleap.ui.tif_tasks import TifQtTaskAdapter
    from AntSleap.ui.tif_workbench_canvas import LazyRegionMaskVolume, MirroredStatusLabel, TifSliceCanvas, TifSpecimenTree, TifVolumeCanvas, WheelSafeComboBox, WheelSafeSlider, WheelSafeSpinBox, create_tif_volume_canvas
    from AntSleap.ui.tif_backend_panel_controller import TifBackendPanelController
    from AntSleap.ui.tif_workbench_control_panels import build_right_control_panel
    from AntSleap.ui.tif_workbench_dialogs import MaterialEditorDialog, TifPartNameDialog, TifTrainingResultDialog, summarize_tif_training_result
    from AntSleap.ui.tif_mesh_export_dialog import TifMeshExportDialog
    from AntSleap.ui.tif_workbench_helpers import (
        _tif_bbox_shape,
        _tif_clip_bbox_to_shape,
        _tif_dedupe_contour_points,
        _tif_empty_contours_payload,
        _tif_format_contour_quality_report,
        _tif_full_volume_contours_to_local,
        _tif_initialize_part_mask_from_full_volume_contours,
        _tif_initialize_part_mask_from_roi_shell,
        _tif_normalize_roi_keyframes,
        _tif_open_reslice_volume_for_review,
        _tif_roi_keyframes_to_part_contours,
        _tif_roi_shell_mask_from_keyframes,
        _tif_safe_contour_slice_index,
        _tif_shape_from_metadata,
        _tif_write_mask_metadata,
    )
    from AntSleap.ui.tif_workbench_layout import make_panel, make_right_sidebar_responsive, make_section, make_task_page
    from AntSleap.ui.tif_workbench_pages import build_task_pages
    from AntSleap.ui.tif_workbench_style import build_tif_workbench_stylesheet, tif_canvas_background
    from AntSleap.ui.tif_workbench_shell import TifWorkbenchShell
    from AntSleap.ui.tif_workbench_view_builder import TifWorkbenchViewBuilder
    from AntSleap.ui.tif_local_axis_controller import TifLocalAxisController
    from AntSleap.ui.tif_preview_controller import TifPreviewController
    from AntSleap.ui.tif_workbench_translations import TIF_TRANSLATIONS, tt
    from AntSleap.ui.tif_workbench_workers import (
        TifBackendActionWorker,
        TifBatchImportWorker,
        TifImportWorker,
        TifLabelAutoSaveWorker,
        TifLabelManualSaveWorker,
        TifLocalAxisResliceExportWorker,
        TifMaterializeWorker,
        TifPartMaskPreviewWorker,
        TifPromoteWorkingEditWorker,
        TifVolumePreviewBuildWorker,
        _tif_write_label_slice_snapshots,
    )
    from AntSleap.ui.tif_gpu_volume_canvas import (
        GPU_VOLUME_MAX_RAY_STEPS,
        GPU_VOLUME_MAX_TEXTURE_DIM,
        TifGpuVolumeCanvas,
        TifGpuVolumeOffscreenWidget,
        build_volume_transfer_lut,
        gpu_volume_canvas_available,
        gpu_volume_offscreen_available,
        gpu_volume_unavailable_reason,
        volume_shader_quality_settings,
        volume_pan_limit_for_zoom,
        volume_shape_scale,
    )
except ModuleNotFoundError as exc:
    if exc.name != "AntSleap":
        raise
    from core.safe_io import atomic_write_json
    from core.amira_import import import_amira_directory
    from core.tif_backend import DEFAULT_TIF_BACKEND_CONFIG, TifBackendRunner, nnunet_v2_tif_backend_preset, normalize_tif_backend_runtime_config, sanitize_tif_backend_config
    from core.tif_export import export_tif_part_training_dataset, export_tif_training_dataset
    from core.tif_label_guard import can_write_label_role, require_editable_label_role
    from core.tif_materials import next_material_id, read_material_map, remove_material, upsert_material, write_material_map
    from core.tif_part_extraction import (
        add_rectangular_keyframe,
        add_polygon_keyframe,
        build_preview_mask_from_contours,
        crop_volume_to_part,
        delete_keyframe,
        export_part_package,
        neighboring_keyframe_indices,
        read_contours_json,
        signed_distance,
        validate_contours_for_interpolation,
        write_contours_json,
        write_part_mask,
    )
    from core.tif_prediction_import import default_prediction_id_for_tif, import_external_prediction_tif
    from core.tif_project import TifProjectManager
    from core.tif_stack_import import import_tif_stack, materialize_registered_tif_stack, register_tif_stack_metadata
    from core.tif_roi_preview import DEFAULT_ROI_TEXTURE_BUDGET_BYTES, HIGH_ROI_TEXTURE_BUDGET_BYTES, build_roi_mask_preview, build_roi_volume_preview, normalize_roi_bbox_zyx, roi_shape_zyx
    from core.tif_volume_io import create_empty_label_sidecar_like, create_volume_sidecar_memmap, flush_volume_array, load_volume_sidecar, volume_sidecar_exists
    from core.tif_volume_preview import (
        build_mask_preview,
        build_volume_preview,
        normalize_preview_intensity,
        scale_volume_to_uint8,
        sample_volume_values,
    )
    from core.tif_local_axis_ai import export_local_axis_training_manifest
    from core.tif_local_axis_reslice import source_point_to_reslice_point
    from services.tif_backend_workflow_service import TifBackendWorkflowService
    from services.tif_label_edit_service import TifLabelEditService
    from services.tif_local_axis_service import TifLocalAxisService
    from services.tif_roi_part_service import TifRoiPartService
    from services.tif_selection_controller import TifSelectionController
    from services.tif_task_manager import TifTaskManager
    from services.tif_truth_promotion_service import TifTruthPromotionService
    from services.tif_volume_preview_service import TifVolumePreviewService
    from services.tif_workbench_states import TifBackendState, TifEditState, TifLocalAxisState, TifPreviewState, TifRoiState
    from ui.style import normalize_theme
    from ui.tif_agent_context import TifAgentContextBuilder
    from ui.tif_tasks import TifQtTaskAdapter
    from ui.tif_workbench_canvas import LazyRegionMaskVolume, MirroredStatusLabel, TifSliceCanvas, TifSpecimenTree, TifVolumeCanvas, WheelSafeComboBox, WheelSafeSlider, WheelSafeSpinBox, create_tif_volume_canvas
    from ui.tif_backend_panel_controller import TifBackendPanelController
    from ui.tif_workbench_control_panels import build_right_control_panel
    from ui.tif_workbench_dialogs import MaterialEditorDialog, TifPartNameDialog, TifTrainingResultDialog, summarize_tif_training_result
    from ui.tif_mesh_export_dialog import TifMeshExportDialog
    from ui.tif_workbench_helpers import (
        _tif_bbox_shape,
        _tif_clip_bbox_to_shape,
        _tif_dedupe_contour_points,
        _tif_empty_contours_payload,
        _tif_format_contour_quality_report,
        _tif_full_volume_contours_to_local,
        _tif_initialize_part_mask_from_full_volume_contours,
        _tif_initialize_part_mask_from_roi_shell,
        _tif_normalize_roi_keyframes,
        _tif_open_reslice_volume_for_review,
        _tif_roi_keyframes_to_part_contours,
        _tif_roi_shell_mask_from_keyframes,
        _tif_safe_contour_slice_index,
        _tif_shape_from_metadata,
        _tif_write_mask_metadata,
    )
    from ui.tif_workbench_layout import make_panel, make_right_sidebar_responsive, make_section, make_task_page
    from ui.tif_workbench_pages import build_task_pages
    from ui.tif_workbench_style import build_tif_workbench_stylesheet, tif_canvas_background
    from ui.tif_workbench_shell import TifWorkbenchShell
    from ui.tif_workbench_view_builder import TifWorkbenchViewBuilder
    from ui.tif_local_axis_controller import TifLocalAxisController
    from ui.tif_preview_controller import TifPreviewController
    from ui.tif_workbench_translations import TIF_TRANSLATIONS, tt
    from ui.tif_workbench_workers import (
        TifBackendActionWorker,
        TifBatchImportWorker,
        TifImportWorker,
        TifLabelAutoSaveWorker,
        TifLabelManualSaveWorker,
        TifLocalAxisResliceExportWorker,
        TifMaterializeWorker,
        TifPartMaskPreviewWorker,
        TifPromoteWorkingEditWorker,
        TifVolumePreviewBuildWorker,
        _tif_write_label_slice_snapshots,
    )
    from ui.tif_gpu_volume_canvas import (
        GPU_VOLUME_MAX_RAY_STEPS,
        GPU_VOLUME_MAX_TEXTURE_DIM,
        TifGpuVolumeCanvas,
        TifGpuVolumeOffscreenWidget,
        build_volume_transfer_lut,
        gpu_volume_canvas_available,
        gpu_volume_offscreen_available,
        gpu_volume_unavailable_reason,
        volume_shader_quality_settings,
        volume_pan_limit_for_zoom,
        volume_shape_scale,
    )


TIF_VOLUME_CLARITY_PART_FULL_VOXEL_LIMIT = 128_000_000
TIF_VOLUME_CLARITY_PART_HIGH_DIM = 3072
TIF_VOLUME_CLARITY_PART_FULL_DIM = GPU_VOLUME_MAX_TEXTURE_DIM
TIF_VOLUME_MAX_CACHED_SPECIMENS = 3
TIF_VOLUME_MAX_PREVIEW_VARIANTS_PER_OWNER = 8
TIF_VOLUME_HIGH_QUALITY_CACHE_OWNER_LIMIT = 2
TIF_VOLUME_ULTRA_QUALITY_CACHE_OWNER_LIMIT = 1
TIF_CONFIRM_PART_BACKGROUND_VOXELS = 1_000_000
TIF_GPU_STREAM_SYNC_MAX_BYTES = 32 * 1024 * 1024
TIF_MASK_PREVIEW_TRUSTED_STATUSES = {
    "mask_preview",
    "mask_in_progress",
    "reviewed",
    "ready_for_labeling",
    "predicted_pending_review",
    "train_ready",
}


def _tif_canvas_background(theme="dark"):
    return tif_canvas_background(theme)


def _tif_overlay_background(alpha=190, theme="dark"):
    color = QColor(_tif_canvas_background(theme))
    color.setAlpha(int(alpha))
    return color

def _now_log_time():
    from datetime import datetime

    return datetime.now().strftime("%H:%M:%S")


def _controller_state_property(controller_name, state_name, normalize=None, readonly=False):
    def getter(workbench):
        controller = getattr(workbench, controller_name)
        return getattr(controller.state, state_name)

    if readonly:
        return property(getter)

    def setter(workbench, value):
        controller = getattr(workbench, controller_name)
        setattr(controller.state, state_name, normalize(value) if normalize else value)

    return property(getter, setter)


def _controller_attribute_property(controller_name, attribute_name):
    return property(
        lambda workbench: getattr(getattr(workbench, controller_name), attribute_name),
        lambda workbench, value: setattr(getattr(workbench, controller_name), attribute_name, value),
    )


def _selection_state_property(state_name):
    return property(
        lambda workbench: getattr(workbench.selection_controller.state, state_name),
        lambda workbench, value: workbench.selection_controller.update(**{state_name: value}),
    )


def _backend_panel_state_property(name):
    return property(
        lambda workbench: getattr(workbench.backend_panel_controller.state, name),
        lambda workbench, value: setattr(workbench.backend_panel_controller.state, name, value),
    )


def _result_review_state_property(name):
    return property(
        lambda workbench: getattr(workbench.result_review_controller.state, name),
        lambda workbench, value: setattr(workbench.result_review_controller.state, name, value),
    )


def _local_axis_state_property(name):
    return property(
        lambda workbench: getattr(workbench.local_axis_controller.state, name),
        lambda workbench, value: setattr(workbench.local_axis_controller.state, name, value),
    )


def _volume_render_state_property(name):
    return property(
        lambda workbench: getattr(workbench.volume_render_controller.state, name),
        lambda workbench, value: setattr(workbench.volume_render_controller.state, name, value),
    )


class TifWorkbenchWidget(QWidget):
    start_center_requested = Signal()
    agent_requested = Signal(dict)

    _tif_backend_thread = _backend_panel_state_property("thread")
    _tif_backend_worker = _backend_panel_state_property("worker")
    _tif_backend_task_id = _backend_panel_state_property("task_id")
    _tif_backend_action = _backend_panel_state_property("action")
    _tif_backend_started_mono = _backend_panel_state_property("started_mono")
    _tif_backend_run_dir = _backend_panel_state_property("run_dir")
    _tif_backend_result_json = _backend_panel_state_property("result_json")
    _tif_backend_last_result = _backend_panel_state_property("last_result")
    _tif_backend_pending_selection = _backend_panel_state_property("pending_selection")
    _pending_backend_action_after_save = _backend_panel_state_property("pending_action_after_save")
    _tif_backend_progress_value = _backend_panel_state_property("progress_value")
    _tif_training_result_summary = _backend_panel_state_property("training_result_summary")
    _tif_training_result_dialog = _backend_panel_state_property("training_result_dialog")
    _tif_training_model_output_dir = _backend_panel_state_property("training_model_output_dir")
    _tif_training_model_manifest = _backend_panel_state_property("training_model_manifest")
    _tif_predict_selected_refs = _backend_panel_state_property("predict_selected_refs")
    _tif_predict_refreshing = _backend_panel_state_property("predict_refreshing")

    _defer_volume_preview_render_once = _volume_render_state_property("defer_volume_preview_render_once")
    _handling_gpu_volume_failure = _volume_render_state_property("handling_gpu_volume_failure")
    _volume_canvas_renderer = _volume_render_state_property("volume_canvas_renderer")
    _volume_clarity_mode = _volume_render_state_property("volume_clarity_mode")
    _volume_gl_renderer_info = _volume_render_state_property("volume_gl_renderer_info")
    _volume_interaction_render_pending = _volume_render_state_property("volume_interaction_render_pending")
    _volume_interaction_render_scheduled = _volume_render_state_property("volume_interaction_render_scheduled")
    _volume_interaction_render_interval_ms = _volume_render_state_property("volume_interaction_render_interval_ms")
    _volume_last_preview_build_ms = _volume_render_state_property("volume_last_preview_build_ms")
    _volume_last_stats = _volume_render_state_property("volume_last_stats")
    _volume_mask_preview_cache = _volume_render_state_property("volume_mask_preview_cache")
    _volume_masked_preview_cache = _volume_render_state_property("volume_masked_preview_cache")
    _volume_pan_x = _volume_render_state_property("volume_pan_x")
    _volume_pan_y = _volume_render_state_property("volume_pan_y")
    _volume_pitch = _volume_render_state_property("volume_pitch")
    _volume_preview = _volume_render_state_property("volume_preview")
    _volume_preview_build_task_id = _volume_render_state_property("volume_preview_build_task_id")
    _volume_preview_build_token = _volume_render_state_property("volume_preview_build_token")
    _volume_preview_cache = _volume_render_state_property("volume_preview_cache")
    _volume_preview_pending_key = _volume_render_state_property("volume_preview_pending_key")
    _volume_preview_pending_mask_key = _volume_render_state_property("volume_preview_pending_mask_key")
    _volume_preview_pending_message = _volume_render_state_property("volume_preview_pending_message")
    _volume_preview_pending_token = _volume_render_state_property("volume_preview_pending_token")
    _volume_preview_source_shape = _volume_render_state_property("volume_preview_source_shape")
    _volume_preview_ui_wait_depth = _volume_render_state_property("volume_preview_ui_wait_depth")
    _volume_quality_committed_value = _volume_render_state_property("volume_quality_committed_value")
    _volume_quality_drag_pending = _volume_render_state_property("volume_quality_drag_pending")
    _volume_render_mode = _volume_render_state_property("volume_render_mode")
    _volume_render_scheduled = _volume_render_state_property("volume_render_scheduled")
    _volume_renderer_warning = _volume_render_state_property("volume_renderer_warning")
    _volume_roi_preview_bbox = _volume_render_state_property("volume_roi_preview_bbox")
    _volume_roi_preview_source_shape = _volume_render_state_property("volume_roi_preview_source_shape")
    _volume_roi_scale_committed_value = _volume_render_state_property("volume_roi_scale_committed_value")
    _volume_transfer_opacity_drag_pending = _volume_render_state_property("volume_transfer_opacity_drag_pending")
    _volume_yaw = _volume_render_state_property("volume_yaw")
    _volume_zoom = _volume_render_state_property("volume_zoom")

    local_axis_draft = _local_axis_state_property("draft")
    _local_axis_endpoint_drag = _local_axis_state_property("endpoint_drag")
    _local_axis_pick_target = _local_axis_state_property("pick_target")
    _local_axis_roll_pick_target = _local_axis_state_property("roll_pick_target")
    _local_axis_reslice_export_thread = _local_axis_state_property("export_thread")
    _local_axis_reslice_export_worker = _local_axis_state_property("export_worker")
    _local_axis_reslice_export_progress = _local_axis_state_property("export_progress")
    _local_axis_reslice_export_context = _local_axis_state_property("export_context")
    _local_axis_reslice_export_task_id = _local_axis_state_property("export_task_id")

    _result_compare_refreshing = _result_review_state_property("refreshing")
    _result_comparison_stale = _result_review_state_property("stale")
    _result_region_mask_cache = _result_review_state_property("region_mask_cache")
    _result_region_mask_cache_key = _result_review_state_property("region_mask_cache_key")

    working_edit_dirty = _controller_state_property("annotation_workflow_controller", "dirty", bool)
    _dirty_edit_slices = _controller_state_property("annotation_workflow_controller", "dirty_slices", lambda value: set(value or ()))
    _edit_slice_revisions = _controller_state_property("annotation_workflow_controller", "slice_revisions", lambda value: dict(value or {}))
    _edit_revision_counter = _controller_state_property("annotation_workflow_controller", "revision_counter", lambda value: int(value or 0))
    annotation_tool_mode = _controller_state_property("annotation_workflow_controller", "tool_mode", lambda value: str(value or "brush"))
    undo_stack = _controller_state_property("annotation_workflow_controller", "undo_stack", lambda value: list(value or []))
    redo_stack = _controller_state_property("annotation_workflow_controller", "redo_stack", lambda value: list(value or []))
    _annotation_stroke_active = _controller_state_property("annotation_workflow_controller", "stroke_active")
    _annotation_stroke_undo_pushed = _controller_state_property("annotation_workflow_controller", "stroke_undo_pushed")
    _annotation_stroke_z_index = _controller_state_property("annotation_workflow_controller", "stroke_z_index")
    _annotation_stroke_last_pixel = _controller_state_property("annotation_workflow_controller", "stroke_last_pixel")
    _annotation_stroke_changed = _controller_state_property("annotation_workflow_controller", "stroke_changed")

    _label_auto_save_thread = _controller_attribute_property("annotation_workflow_controller", "auto_save_thread")
    _label_auto_save_worker = _controller_attribute_property("annotation_workflow_controller", "auto_save_worker")
    _label_auto_save_token = _controller_attribute_property("annotation_workflow_controller", "auto_save_token")
    _label_auto_save_task_id = _controller_attribute_property("annotation_workflow_controller", "auto_save_task_id")
    _label_auto_save_pending_reason = _controller_attribute_property("annotation_workflow_controller", "auto_save_pending_reason")
    _label_auto_save_handled_tokens = _controller_attribute_property("annotation_workflow_controller", "auto_save_handled_tokens")
    _label_manual_save_thread = _controller_attribute_property("annotation_workflow_controller", "manual_save_thread")
    _label_manual_save_worker = _controller_attribute_property("annotation_workflow_controller", "manual_save_worker")
    _label_manual_save_token = _controller_attribute_property("annotation_workflow_controller", "manual_save_token")
    _label_manual_save_task_id = _controller_attribute_property("annotation_workflow_controller", "manual_save_task_id")
    _pending_manual_save_after_auto = _controller_attribute_property("annotation_workflow_controller", "pending_manual_save_after_auto")
    _promote_thread = _controller_attribute_property("annotation_workflow_controller", "promote_thread")
    _promote_worker = _controller_attribute_property("annotation_workflow_controller", "promote_worker")
    _promote_request = _controller_attribute_property("annotation_workflow_controller", "promote_request")
    _promote_task_id = _controller_attribute_property("annotation_workflow_controller", "promote_task_id")
    _saving_working_edit = _controller_attribute_property("annotation_workflow_controller", "saving_working_edit")
    _pending_promote_after_save = _controller_attribute_property("annotation_workflow_controller", "pending_promote_after_save")

    current_specimen_id = _selection_state_property("specimen_id")
    current_volume_scope = _selection_state_property("volume_scope")
    current_part_id = _selection_state_property("part_id")
    current_reslice_id = _selection_state_property("reslice_id")

    active_part_roi_id = _controller_state_property("roi_workflow_controller", "active_roi_id", readonly=True)
    part_roi_keyframes = _controller_state_property("roi_workflow_controller", "keyframes", readonly=True)
    part_roi_draw_mode = _controller_state_property("roi_workflow_controller", "draw_mode", readonly=True)
    part_preview_mask = _controller_state_property("part_mask_workflow_controller", "preview_mask", readonly=True)
    part_mask_preview_bbox = _controller_state_property("part_mask_workflow_controller", "preview_bbox", readonly=True)
    part_mask_preview_accepted = _controller_state_property("part_mask_workflow_controller", "preview_accepted", readonly=True)
    part_mask_keyframes = _controller_state_property("part_mask_workflow_controller", "keyframes", readonly=True)
    part_contour_draw_mode = _controller_state_property("part_mask_workflow_controller", "contour_draw_mode", readonly=True)
    part_mask_volume = _controller_state_property("part_mask_workflow_controller", "part_mask_volume", readonly=True)
    material_map = _controller_state_property("part_mask_workflow_controller", "material_map", readonly=True)
    material_colors = _controller_state_property("part_mask_workflow_controller", "material_colors", readonly=True)
    current_material_id = _controller_state_property("part_mask_workflow_controller", "current_material_id", readonly=True)

    def __init__(self, project_manager=None, lang="zh", parent=None, config_manager=None):
        super().__init__(parent)
        self.setObjectName("tifWorkbenchRoot")
        self.workbench_shell = TifWorkbenchShell(self)
        self.workbench_view = self.workbench_shell.view
        self.signal_router = self.workbench_shell.signal_router
        self.workbench_shell.configure_foundation(project_manager, lang, parent, config_manager)
        self.workbench_shell.initialize_runtime_state()
        self.view_builder = TifWorkbenchViewBuilder(self)
        self.view_builder.create_widgets()
        self.workbench_shell.finalize_startup()

    def _style_button(self, button, role="secondary", full_width=False):
        button.setProperty("tifRole", role)
        button.setCursor(Qt.PointingHandCursor)
        button.setMinimumHeight(34)
        if full_width:
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _apply_button_roles(self):
        primary_buttons = [
            self.btn_import_tif,
            self.btn_import_amira,
            self.btn_export_training,
            self.btn_prepare_dataset,
            self.btn_train_backend,
            self.btn_import_prediction,
            self.btn_open_backend_run,
            self.btn_open_backend_result,
            self.btn_show_training_result_summary,
            self.btn_open_training_model_output,
            self.btn_open_training_model_manifest,
            self.btn_batch_predict_entry,
            self.btn_use_selected_tif_model,
            self.btn_import_external_prediction_tif,
            self.btn_promote,
            self.btn_accept_selected_ai_results,
            self.btn_preview_part_mask,
            self.btn_accept_part_mask,
            self.btn_local_axis_reslice,
            self.btn_export_local_axis_training_manifest,
            self.btn_export_part_package,
            self.btn_export_reviewed_mesh,
        ]
        secondary_buttons = [
            self.btn_start_center,
            self.btn_ask_agent,
            self.btn_show_workbench_log,
            self.btn_undo,
            self.btn_redo,
            self.btn_save_edit,
            self.btn_tool_brush,
            self.btn_tool_eraser,
            self.btn_tool_lasso,
            self.btn_tool_rectangle,
            self.btn_tool_ellipse,
            self.btn_interpolate_current_label,
            self.btn_tool_picker,
            self.btn_tool_pan,
            self.btn_copy_material_prev,
            self.btn_copy_material_next,
            self.btn_clear_current_material,
            self.btn_reset_volume_view,
            self.btn_volume_custom_color,
            self.btn_copy_draft,
            self.btn_copy_source_z_axis,
            self.btn_pick_roll_ref_a,
            self.btn_pick_roll_ref_b,
            self.btn_pick_roll_ref_c,
            self.btn_align_axis_to_reference_plane,
            self.btn_clear_roll_refs,
            self.btn_clear_local_axis_draft,
            self.btn_add_material,
            self.btn_edit_material,
            self.btn_choose_part_user_tag_color,
            self.btn_save_backend,
            self.btn_part_draw_roi,
            self.btn_save_part_roi,
            self.btn_draw_part_contour,
            self.btn_clear_part_keyframes,
            self.btn_prev_key_slice,
            self.btn_next_key_slice,
            self.btn_clear_part_preview,
            self.btn_stop_backend,
            self.btn_browse_model_manifest,
            self.btn_refresh_predict_targets,
            self.btn_select_current_predict_target,
            self.btn_select_ready_predict_targets,
            self.btn_clear_predict_targets,
            self.btn_refresh_result_comparison,
            self.btn_open_result_comparison_target,
            self.btn_show_result_region_in_3d,
            self.btn_new_label_schema,
            self.btn_save_label_schema,
            self.btn_bind_label_schema_to_part,
            self.btn_add_label_schema_row,
            self.btn_import_label_schema,
            self.btn_export_label_schema,
            self.btn_new_part_user_tag,
            self.btn_save_part_user_tag,
            self.btn_save_tif_model_notes,
            self.btn_move_part_user_tag_up,
            self.btn_move_part_user_tag_down,
            self.btn_apply_part_user_tags,
        ]
        for button in primary_buttons:
            self._style_button(button, "primary", full_width=True)
        for button in secondary_buttons:
            self._style_button(button, "secondary", full_width=True)
        self._style_button(self.btn_delete_material, "danger", full_width=True)
        self._style_button(self.btn_remove_label_schema_row, "danger", full_width=True)
        self._style_button(self.btn_delete_part_user_tag, "danger", full_width=True)
        self._style_button(self.btn_delete_tif_model_record, "danger", full_width=True)
        self._style_button(self.btn_stop_backend, "danger", full_width=True)
        self._style_button(self.btn_confirm_part_roi, "primary", full_width=True)
        self._style_button(self.btn_cancel_part_roi, "danger", full_width=True)
        self._style_button(self.btn_delete_part_contour, "danger", full_width=True)
        self._style_button(self.btn_delete_part_volume, "danger", full_width=True)

    def _populate_label_role_combo(self):
        current = self.label_role_combo.currentData() if self.label_role_combo.count() else "manual_truth"
        self.label_role_combo.blockSignals(True)
        self.label_role_combo.clear()
        roles = self.selection_controller.label_roles_for_scope(self.current_volume_scope)
        for role in roles:
            self.label_role_combo.addItem(tt(role, self.lang), role)
        preferred = self.selection_controller.preferred_label_role(current, self.current_volume_scope)
        index = self.label_role_combo.findData(preferred)
        self.label_role_combo.setCurrentIndex(index if index >= 0 else 0)
        self.label_role_combo.blockSignals(False)

    def _populate_slice_axis_combo(self):
        current = self.slice_axis_combo.currentData() if self.slice_axis_combo.count() else self.slice_axis
        self.slice_axis_combo.blockSignals(True)
        self.slice_axis_combo.clear()
        for axis, label in (("z", "Z axial"), ("y", "Y coronal"), ("x", "X sagittal")):
            self.slice_axis_combo.addItem(tt(label, self.lang), axis)
        index = self.slice_axis_combo.findData(current)
        self.slice_axis_combo.setCurrentIndex(index if index >= 0 else 0)
        self.slice_axis_combo.blockSignals(False)

    def _populate_display_mode_combo(self):
        current = self.display_mode if self.display_mode in {"slice", "volume"} else "slice"
        self.display_mode_combo.blockSignals(True)
        self.display_mode_combo.clear()
        for mode, label in (("slice", "Slice review"), ("volume", "3D volume")):
            self.display_mode_combo.addItem(tt(label, self.lang), mode)
        index = self.display_mode_combo.findData(current)
        self.display_mode_combo.setCurrentIndex(index if index >= 0 else 0)
        self.display_mode_combo.blockSignals(False)

    def _populate_volume_projection_combo(self):
        current = self.volume_projection_combo.currentData() if self.volume_projection_combo.count() else "composite"
        self.volume_projection_combo.blockSignals(True)
        self.volume_projection_combo.clear()
        for mode, label in (
            ("composite", "Composite"),
            ("mip", "MIP"),
            ("minip", "MinIP"),
            ("average", "Average"),
            ("surface", "Surface"),
        ):
            self.volume_projection_combo.addItem(tt(label, self.lang), mode)
        index = self.volume_projection_combo.findData(current)
        self.volume_projection_combo.setCurrentIndex(index if index >= 0 else 0)
        self.volume_projection_combo.blockSignals(False)

    def _populate_volume_tint_combo(self):
        current = self._active_volume_view_settings().get("volume_tint", "amber")
        self.volume_tint_combo.blockSignals(True)
        self.volume_tint_combo.clear()
        for mode, label in (
            ("amber", "Amber"),
            ("cyan", "Cyan"),
            ("white", "White"),
            ("morphology", "Morphology Inspect"),
            ("publication", "Publication Inspect"),
            ("custom", "Custom"),
        ):
            self.volume_tint_combo.addItem(tt(label, self.lang), mode)
        index = self.volume_tint_combo.findData(current)
        self.volume_tint_combo.setCurrentIndex(index if index >= 0 else 0)
        self.volume_tint_combo.blockSignals(False)

    def _populate_volume_shader_quality_combo(self):
        current = self._active_volume_view_settings().get("volume_shader_quality", "preset")
        self.volume_shader_quality_combo.blockSignals(True)
        self.volume_shader_quality_combo.clear()
        for mode, label in (
            ("preset", "Inspect presets"),
            ("off", "Off"),
            ("all_still", "All still composite"),
        ):
            self.volume_shader_quality_combo.addItem(tt(label, self.lang), mode)
        index = self.volume_shader_quality_combo.findData(current)
        self.volume_shader_quality_combo.setCurrentIndex(index if index >= 0 else 0)
        self.volume_shader_quality_combo.blockSignals(False)

    def _populate_volume_roi_source_combo(self):
        combo = getattr(self, "volume_roi_source_combo", None)
        if combo is None:
            return
        current = str(combo.currentData() or "full")
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(tt("Full volume", self.lang), "full")
        combo.addItem(tt("Current bbox draft", self.lang), "current_bbox")
        specimen = self.project.get_specimen(self.current_specimen_id, default=None) if self.current_specimen_id else None
        for roi in (specimen or {}).get("part_rois", []) or []:
            if (roi or {}).get("status") == "cancelled":
                continue
            roi_id = str((roi or {}).get("roi_id", "") or "")
            if not roi_id:
                continue
            label = str((roi or {}).get("display_name") or roi_id)
            combo.addItem(f"ROI: {label}", f"roi:{roi_id}")
        for part in (specimen or {}).get("parts", []) or []:
            part_id = str((part or {}).get("part_id", "") or "")
            image_path = ((part or {}).get("image") or {}).get("path", "")
            if not part_id or not image_path:
                continue
            label = str((part or {}).get("display_name") or part_id)
            combo.addItem(f"Part: {label}", f"part:{part_id}")
        index = combo.findData(current)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)

    def _apply_volume_transfer_opacity_setting(self):
        if not hasattr(self, "volume_transfer_opacity_slider"):
            return
        settings = self._active_volume_view_settings()
        value = settings.get("volume_transfer_opacity", 100)
        try:
            value = int(round(float(value)))
        except (TypeError, ValueError):
            value = 100
        value = max(self.volume_transfer_opacity_slider.minimum(), min(self.volume_transfer_opacity_slider.maximum(), value))
        self.volume_transfer_opacity_slider.blockSignals(True)
        self.volume_transfer_opacity_slider.setValue(value)
        self.volume_transfer_opacity_slider.blockSignals(False)

    def _populate_volume_mask_combo(self):
        current = self.volume_mask_combo.currentData() if self.volume_mask_combo.count() else self._default_volume_mask_mode()
        self.volume_mask_combo.blockSignals(True)
        self.volume_mask_combo.clear()
        for mode, label in (
            ("image_only", "Image only"),
            ("mask_boundary", "Mask boundary"),
            ("masked_image", "Masked image"),
        ):
            self.volume_mask_combo.addItem(tt(label, self.lang), mode)
        index = self.volume_mask_combo.findData(current)
        self.volume_mask_combo.setCurrentIndex(index if index >= 0 else 0)
        self.volume_mask_combo.blockSignals(False)

    def _populate_result_region_combo(self):
        combo = getattr(self, "result_region_combo", None)
        if combo is None:
            return
        current = combo.currentData() if combo.count() else None
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(tt("All", self.lang), 0)
        labels = OrderedDict()
        schema_ids = []
        if self.current_volume_scope == "part" and self.current_specimen_id and self.current_part_id:
            part = self.project.get_part(self.current_specimen_id, self.current_part_id, default=None)
            schema_id = str(((part or {}).get("training") or {}).get("label_schema_id") or "")
            if schema_id:
                schema_ids.append(schema_id)
        if not schema_ids:
            for specimen in self.project.project_data.get("specimens", []) or []:
                for part in (specimen or {}).get("parts", []) or []:
                    schema_id = str(((part or {}).get("training") or {}).get("label_schema_id") or "")
                    if schema_id and schema_id not in schema_ids:
                        schema_ids.append(schema_id)
        for schema_id in schema_ids:
            schema = self.project.get_label_schema(schema_id, default={}) if schema_id else {}
            for item in (schema.get("labels") or []):
                try:
                    label_id = int(item.get("id", 0))
                except (TypeError, ValueError):
                    continue
                if label_id > 0 and label_id not in labels:
                    labels[label_id] = item.get("display_name") or item.get("name") or str(label_id)
        if not labels:
            for item in (self.material_map or {}).get("materials", []) or []:
                try:
                    label_id = int(item.get("id", 0))
                except (TypeError, ValueError):
                    continue
                if label_id > 0 and bool(item.get("trainable", True)):
                    labels.setdefault(label_id, item.get("display_name") or item.get("name") or str(label_id))
        for label_id, label_name in sorted(labels.items(), key=lambda pair: pair[0]):
            combo.addItem(f"{label_id} · {label_name}", label_id)
        index = combo.findData(current)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)

    def _set_volume_mask_mode(self, mode):
        if not hasattr(self, "volume_mask_combo"):
            return False
        mode = mode if mode in {"image_only", "mask_boundary", "masked_image"} else "image_only"
        index = self.volume_mask_combo.findData(mode)
        if index < 0 or index == self.volume_mask_combo.currentIndex():
            return False
        self.volume_mask_combo.blockSignals(True)
        self.volume_mask_combo.setCurrentIndex(index)
        self.volume_mask_combo.blockSignals(False)
        return True

    def _default_volume_mask_mode(self):
        if self.current_volume_scope == "full" and self.volume_render_controller._active_part_mask_likely_available():
            return "masked_image"
        configured = (self._active_volume_view_settings() or {}).get("volume_mask_mode", "")
        if configured in {"image_only", "mask_boundary", "masked_image"}:
            if configured == "image_only" or self.volume_render_controller._active_part_mask_likely_available():
                return configured
        if self.current_volume_scope == "part" and self.volume_render_controller._active_part_mask_likely_available():
            return "masked_image"
        return "image_only"

    def _apply_default_volume_mask_mode(self):
        if self._set_volume_mask_mode(self._default_volume_mask_mode()):
            self.volume_render_controller._clear_volume_mask_caches(owner=self.volume_render_controller._active_volume_cache_owner())
            self.volume_render_controller._reset_active_volume_preview_state()

    def _project_view_settings(self):
        return self.project.project_data.setdefault("view_settings", {})

    def _active_volume_view_settings(self):
        if self.current_volume_scope == "part" and isinstance(self.current_part, dict):
            part_settings = self.current_part.setdefault("view_settings", {})
            parent_settings = self._project_view_settings()
            for key in ("volume_tint", "volume_tint_custom", "volume_transfer_opacity", "volume_shader_quality"):
                if key not in part_settings and key in parent_settings:
                    part_settings[key] = parent_settings[key]
            return part_settings
        return self._project_view_settings()

    def _save_active_volume_view_settings(self):
        if self.current_volume_scope == "part" and self.current_specimen_id and self.current_part_id:
            settings = dict((self.current_part or {}).get("view_settings") or {})
            try:
                self.current_part = self.project.update_part_view_settings(self.current_specimen_id, self.current_part_id, settings)
            except Exception:
                if self.project.current_project_path:
                    self.project.save_project()
            return
        if self.project.current_project_path:
            self.project.save_project()

    def change_language(self, lang):
        self.lang = lang
        self._update_texts()
        self.refresh_project()
        self.render_current_slice()

    def _update_texts(self):
        for title, label in getattr(self, "_panel_title_labels", {}).values():
            label.setText(tt(title, self.lang))
        for title, label in getattr(self, "_section_title_labels", {}).values():
            label.setText(tt(title, self.lang))
        self._populate_label_role_combo()
        self._populate_display_mode_combo()
        self._populate_volume_projection_combo()
        self._populate_volume_tint_combo()
        self._populate_volume_shader_quality_combo()
        self._populate_volume_roi_source_combo()
        self._populate_result_region_combo()
        self._apply_volume_transfer_opacity_setting()
        self._populate_volume_mask_combo()
        if hasattr(self, "task_tabs"):
            for index, label in enumerate(("Review", "Part Extraction", "Annotation / training")):
                self.task_tabs.setTabText(index, tt(label, self.lang))
        if hasattr(self, "training_mode_tabs"):
            for index, label in enumerate(("Label review", "Train / predict", "Result comparison")):
                self.training_mode_tabs.setTabText(index, tt(label, self.lang))
        if self.image_volume is None:
            specimen = self.project.get_specimen(self.current_specimen_id, default=None) if self.current_specimen_id else None
            self.canvas.setText(self._slice_unavailable_message(specimen))
        self.slice_prefix_label.setText(tt("Slice", self.lang))
        self.display_mode_label.setText(tt("Display mode", self.lang))
        self.slice_axis_label.setText(tt("View plane", self.lang))
        self._populate_slice_axis_combo()
        self.label_layer_label.setText(tt("Label layer", self.lang))
        self._update_label_role_help()
        self.overlay_label.setText(tt("Overlay", self.lang))
        self.brightness_label.setText(tt("Brightness", self.lang))
        self.contrast_label.setText(tt("Contrast", self.lang))
        self.volume_projection_label.setText(tt("Render mode", self.lang))
        self.volume_tint_label.setText(tt("Transfer function", self.lang))
        self.volume_transfer_opacity_label.setText(tt("Density opacity", self.lang))
        self.volume_enhancement_label.setText(tt("Detail enhancement", self.lang))
        self.volume_tone_label.setText(tt("Tone curve", self.lang))
        self.volume_shader_quality_label.setText(tt("Shader quality", self.lang))
        self.volume_surface_refine_check.setText(tt("Surface refine", self.lang))
        self.volume_clip_plane_check.setText(tt("Clip plane", self.lang))
        self.volume_local_axes_check.setText(tt("Show local axes", self.lang))
        self.volume_clip_plane_depth_label.setText(tt("Clip depth", self.lang))
        self.volume_mask_label.setText(tt("Mask display", self.lang))
        self.volume_mask_opacity_label.setText(tt("Mask opacity", self.lang))
        self.volume_cutoff_label.setText(tt("Density cutoff", self.lang))
        self.volume_quality_label.setText(tt("Render quality", self.lang))
        self.volume_sample_label.setText(tt("Ray samples", self.lang))
        self.volume_clarity_check.setText(tt("Local detail check", self.lang))
        self.volume_roi_detail_check.setText(tt("ROI high detail", self.lang))
        self.volume_roi_inspect_check.setText(tt("Inspect ROI crop", self.lang))
        self._populate_volume_roi_source_combo()
        self.volume_roi_scale_label.setText(tt("ROI scale", self.lang))
        self.volume_roi_budget_label.setText(tt("ROI budget", self.lang))
        self.volume_inside_label.setText(tt("Inside depth", self.lang))
        self.volume_clip_label.setText(tt("Front cut", self.lang))
        self.btn_volume_custom_color.setText(tt("Choose color", self.lang))
        self.btn_volume_morphology_preset.setText(tt("Morphology Inspect", self.lang))
        self.btn_reset_volume_view.setText(tt("Reset 3D view", self.lang))
        self._update_volume_control_tooltips()
        if hasattr(self, "operation_status_label") and not self.operation_status_label.text():
            self.operation_status_label.setText(tt("Ready. Annotation feedback will appear here.", self.lang))
        if hasattr(self, "btn_show_workbench_log"):
            self.btn_show_workbench_log.setText(tt("Show full log", self.lang))
        if self.display_mode == "volume":
            self.training_status_label.setText(self.volume_render_controller._volume_renderer_status_message())
        self.annotation_tool_label.setText(tt("Tool", self.lang))
        self.btn_tool_brush.setText(tt("Brush", self.lang))
        self.btn_tool_eraser.setText(tt("Eraser", self.lang))
        self.btn_tool_lasso.setText(tt("Lasso fill", self.lang))
        self.btn_tool_rectangle.setText(tt("Rectangle fill", self.lang))
        self.btn_tool_ellipse.setText(tt("Ellipse fill", self.lang))
        self.btn_interpolate_current_label.setText(tt("Interpolate fill", self.lang))
        self.btn_tool_picker.setText(tt("Picker", self.lang))
        self.btn_tool_pan.setText(tt("Pan/view", self.lang))
        self.btn_tool_brush.setToolTip(tt("Brush (B): paint the selected label. Hold Ctrl for temporary erase.", self.lang))
        self.btn_tool_eraser.setToolTip(tt("Eraser (E): write background 0. Ctrl + left drag still works as temporary erase.", self.lang))
        self.btn_tool_lasso.setToolTip(tt("Lasso fill (L): draw a closed outline and fill it with the selected label.", self.lang))
        self.btn_tool_rectangle.setToolTip(tt("Rectangle fill (R): drag a box and fill it with the selected label.", self.lang))
        self.btn_tool_ellipse.setToolTip(tt("Ellipse fill (O): drag an ellipse and fill it with the selected label.", self.lang))
        self.btn_interpolate_current_label.setToolTip(tt("Interpolate fill: use slices where the current label already exists as key slices, then fill the slices between them.", self.lang))
        self.btn_tool_picker.setToolTip(tt("Picker (I): sample a label under the cursor and select that label.", self.lang))
        self.btn_tool_pan.setToolTip(tt("Pan/view: drag the zoomed slice without changing labels. Right drag also pans when zoomed.", self.lang))
        self._sync_annotation_tool_buttons()
        self.brush_size_label.setText(tt("Brush size", self.lang))
        self.brush_size_slider.setToolTip(f"{tt('Decrease brush size ([)', self.lang)} / {tt('Increase brush size (])', self.lang)}")
        self.btn_undo.setToolTip(tt("Undo last stroke (Ctrl+Z)", self.lang))
        self.btn_redo.setToolTip(tt("Redo stroke (Ctrl+Y / Ctrl+Shift+Z)", self.lang))
        self.btn_save_edit.setToolTip(tt("Save current label layer (Ctrl+S)", self.lang))
        self.btn_copy_material_prev.setText(tt("Copy label to previous slice", self.lang))
        self.btn_copy_material_next.setText(tt("Copy label to next slice", self.lang))
        self.btn_clear_current_material.setText(tt("Clear current label", self.lang))
        self.btn_copy_material_prev.setToolTip(tt("Copy current label mask to the previous slice for refinement.", self.lang))
        self.btn_copy_material_next.setToolTip(tt("Copy current label mask to the next slice for refinement.", self.lang))
        self.btn_clear_current_material.setToolTip(tt("Clear the selected label from the current slice. Other labels are kept.", self.lang))
        self.save_status_title_label.setText(tt("Save status", self.lang))
        self.auto_save_hint_label.setText(tt("Auto-save writes the current label layer about 1.2 seconds after edits.", self.lang))
        self._update_save_status()
        self._sync_undo_redo_buttons()
        self.current_material_title_label.setText(tt("Current label", self.lang))
        self.part_mask_workflow_controller._update_current_material_summary()
        self.btn_import_tif.setText(tt("Import TIF stack", self.lang))
        self.btn_import_amira.setText(tt("Import AMIRA directory", self.lang))
        self.part_bbox_edit.setPlaceholderText(tt("z0,z1,y0,y1,x0,x1", self.lang))
        self.btn_part_draw_roi.setText(tt("Draw ROI", self.lang))
        self.btn_save_part_roi.setText(tt("Save ROI draft", self.lang))
        self.btn_confirm_part_roi.setText(tt("Confirm ROI", self.lang))
        self.btn_cancel_part_roi.setText(tt("Cancel ROI", self.lang))
        self.btn_create_part.setText(tt("Create part", self.lang))
        self.btn_add_rect_keyframe.setText(tt("Add rectangular key slice", self.lang))
        self.btn_draw_part_contour.setText(tt("Draw contour", self.lang))
        self.btn_delete_part_contour.setText(tt("Delete key slice", self.lang))
        self.btn_clear_part_keyframes.setText(tt("Clear key slices", self.lang))
        self.btn_prev_key_slice.setText(tt("Previous key slice", self.lang))
        self.btn_next_key_slice.setText(tt("Next key slice", self.lang))
        self.btn_preview_part_mask.setText(tt("Preview auto fill", self.lang))
        self.btn_accept_part_mask.setText(tt("Accept part mask", self.lang))
        self.btn_clear_part_preview.setText(tt("Clear preview", self.lang))
        self.btn_export_part_package.setText(tt("Export part package", self.lang))
        self.btn_export_reviewed_mesh.setText(tt("Export reviewed label STL", self.lang))
        self.btn_export_reviewed_mesh.setToolTip(
            tt(
                "Create Blender-ready STL only from the current reviewed manual truth.",
                self.lang,
            )
        )
        if hasattr(self, "local_axis_volume_help_label"):
            self.local_axis_volume_help_label.setText(
                tt(
                    "Roll A/B/C picking works on the observation-side clip plane only. Turn on Clip plane in the 3D preview, move it to the target cross-section, then click A, B, and C on that plane.",
                    self.lang,
                )
            )
        self.volume_local_axes_check.setText(tt("Show source/output axes in 3D preview", self.lang))
        if hasattr(self, "local_axis_status_label") and not self.local_axis_status_label.text():
            self.local_axis_status_label.setText(tt("Local axis status: ready", self.lang))
        self.local_axis_details_check.setText(tt("Show axis details", self.lang))
        self.btn_local_axis_reslice.setText(tt("Export confirmed reslice", self.lang))
        self.btn_copy_source_z_axis.setText(tt("Copy source Z axis", self.lang))
        self.btn_pick_roll_ref_a.setText(tt("Pick roll reference A", self.lang))
        self.btn_pick_roll_ref_b.setText(tt("Pick roll reference B", self.lang))
        self.btn_pick_roll_ref_c.setText(tt("Pick plane reference C", self.lang))
        self.btn_align_axis_to_reference_plane.setText(tt("Make Z perpendicular\nto A/B/C plane", self.lang))
        self.btn_clear_roll_refs.setText(tt("Clear roll refs", self.lang))
        roll_pick_tooltip = tt("Pick roll/reference points on the current observation-side clip plane. If the clip plane is off, it will be enabled first.", self.lang)
        self.btn_pick_roll_ref_a.setToolTip(roll_pick_tooltip)
        self.btn_pick_roll_ref_b.setToolTip(roll_pick_tooltip)
        self.btn_pick_roll_ref_c.setToolTip(roll_pick_tooltip)
        self.btn_align_axis_to_reference_plane.setToolTip(tt("The A/B/C plane is computed from points picked on the observation-side clip plane; use it after A, B, and C are set.", self.lang))
        self.btn_clear_local_axis_draft.setText(tt("Clear axis draft", self.lang))
        self.local_axis_trainable_check.setText(tt("Record this export as trainable local-axis data", self.lang))
        self.btn_export_local_axis_training_manifest.setText(tt("Export confirmed Local Axis training manifest", self.lang))
        self.btn_delete_part_volume.setText(tt("Delete part volume", self.lang))
        self.btn_undo.setText(tt("Undo", self.lang))
        self.btn_redo.setText(tt("Redo", self.lang))
        self.btn_save_edit.setText(tt("Save current labels", self.lang))
        self.auto_save_check.setText(tt("Auto-save labels", self.lang))
        self.show_debug_paths_check.setText(tt("Show debug paths", self.lang))
        self.btn_promote.setText(tt("Accept as training truth", self.lang))
        self.btn_accept_selected_ai_results.setText(tt("Accept selected AI results", self.lang))
        self.btn_copy_draft.setText(tt("Copy legacy model draft to current labels", self.lang))
        self.btn_add_material.setText(tt("Add material", self.lang))
        self.btn_edit_material.setText(tt("Edit material", self.lang))
        self.btn_delete_material.setText(tt("Delete material", self.lang))
        self.part_mask_workflow_controller._sync_material_editor_scope()
        if hasattr(self, "label_schema_id_label"):
            self.label_schema_id_label.setText(tt("Schema ID", self.lang))
            self.label_schema_part_name_label.setText(tt("User-defined part name", self.lang))
            self.label_schema_table.setHorizontalHeaderLabels(["", tt("Label ID", self.lang), tt("Region name", self.lang), tt("Color", self.lang)])
            self.btn_new_label_schema.setText(tt("New schema", self.lang))
            self.btn_save_label_schema.setText(tt("Save schema", self.lang))
            self.btn_bind_label_schema_to_part.setText(tt("Bind to current part", self.lang))
            self.btn_add_label_schema_row.setText(tt("Add region label", self.lang))
            self.btn_remove_label_schema_row.setText(tt("Remove region label", self.lang))
            self.btn_import_label_schema.setText(tt("Import schema", self.lang))
            self.btn_export_label_schema.setText(tt("Export schema", self.lang))
            if hasattr(self, "label_schema_help_label"):
                self.label_schema_help_label.setText(tt("Bind a label schema first so every specimen uses the same numeric labels for annotation, training, prediction import, and result comparison. Import files should be TaxaMask label schema JSON exported from this panel.", self.lang))
            self._populate_label_schema_combo()
        if hasattr(self, "part_user_tag_id_label"):
            self.part_user_tag_id_label.setText(tt("Group tag ID", self.lang))
            self.part_user_tag_label_label.setText(tt("Group tag label", self.lang))
            self.part_user_tag_color_label.setText(tt("Color", self.lang))
            self.btn_choose_part_user_tag_color.setText(tt("Choose group color", self.lang))
            self.part_user_tag_table.setHorizontalHeaderLabels(["", tt("Group tag ID", self.lang), tt("Group tag label", self.lang), tt("Color", self.lang), tt("Assigned", self.lang)])
            self.btn_new_part_user_tag.setText(tt("Add group tag", self.lang))
            self.btn_save_part_user_tag.setText(tt("Save group tag", self.lang))
            self.btn_delete_part_user_tag.setText(tt("Delete group tag", self.lang))
            self.btn_move_part_user_tag_up.setText(tt("Move up", self.lang))
            self.btn_move_part_user_tag_down.setText(tt("Move down", self.lang))
            self.btn_apply_part_user_tags.setText(tt("Apply tags to current part", self.lang))
            if hasattr(self, "part_user_tag_help_label"):
                self.part_user_tag_help_label.setText(tt("Group tags only organize part volumes for prediction rounds or review batches. They are not annotation classes, label schemas, or training labels.", self.lang))
            self._populate_part_user_tag_table()
        self.btn_export_training.setText(tt("Export train-ready volumes", self.lang))
        self.result_source_label.setText(tt("Review source", self.lang))
        self.result_source_manual_radio.setText(tt("manual_truth", self.lang))
        self.result_source_editable_radio.setText(tt("editable_ai_result", self.lang))
        self.result_region_label.setText(tt("Region label", self.lang))
        self.btn_export_current_rendering.setText(tt("Export current rendering screenshot", self.lang))
        self.backend_id_label.setText(tt("Backend ID", self.lang))
        self.backend_display_label.setText(tt("Display name", self.lang))
        self.backend_python_label.setText(tt("Python", self.lang))
        self.backend_formats_label.setText(tt("Export formats", self.lang))
        self.backend_prepare_label.setText(tt("Prepare command", self.lang))
        self.backend_train_label.setText(tt("Train command", self.lang))
        self.backend_predict_label.setText(tt("Predict command", self.lang))
        self.backend_manifest_label.setText(tt("Model manifest", self.lang))
        self.predict_manifest_label.setText(tt("Model manifest", self.lang))
        self.predict_filter_label.setText(tt("Predict group", self.lang))
        self.btn_use_nnunet_backend_preset.setText(tt("Use nnU-Net v2 preset", self.lang))
        self.btn_save_backend.setText(tt("Save backend settings", self.lang))
        self.btn_prepare_dataset.setText(tt("Prepare dataset", self.lang))
        self.btn_train_backend.setText(tt("Train backend", self.lang))
        self.backend_run_title_label.setText(tt("Backend run", self.lang))
        self.btn_browse_model_manifest.setText(tt("Browse manifest", self.lang))
        self.btn_refresh_predict_targets.setText(tt("Refresh targets", self.lang))
        self.btn_select_current_predict_target.setText(tt("Select current part", self.lang))
        self.btn_select_ready_predict_targets.setText(tt("Select all ready", self.lang))
        self.btn_clear_predict_targets.setText(tt("Clear selection", self.lang))
        self.btn_import_prediction.setText(tt("Import prediction", self.lang))
        self.btn_stop_backend.setText(tt("Stop run", self.lang))
        self.btn_open_backend_run.setText(tt("Open run folder", self.lang))
        self.btn_open_backend_result.setText(tt("Open result JSON", self.lang))
        self.btn_show_training_result_summary.setText(tt("Show result summary", self.lang))
        self.btn_open_training_model_output.setText(tt("Open model output", self.lang))
        self.btn_open_training_model_manifest.setText(tt("Open model manifest", self.lang))
        self.btn_batch_predict_entry.setText(tt("Enter batch prediction", self.lang))
        self.btn_batch_predict_entry.setToolTip(tt("Batch prediction entry will use the selected model manifest in the next phase.", self.lang))
        if hasattr(self, "model_library_label"):
            self.model_library_label.setText(tt("Trained model", self.lang))
            self.model_library_notes_label.setText(tt("Notes", self.lang))
            self.btn_use_selected_tif_model.setText(tt("Use selected model", self.lang))
            self.btn_save_tif_model_notes.setText(tt("Save notes", self.lang))
            self.btn_delete_tif_model_record.setText(tt("Delete registration", self.lang))
            self.model_library_notes_edit.setPlaceholderText(tt("Model notes", self.lang))
            self.backend_panel_controller.populate_model_library_combo()
        self.backend_panel_controller.refresh_training_result_controls()
        self.backend_panel_controller.refresh_predict_targets()
        if not self.backend_panel_controller.action_running():
            self.backend_run_status_label.setText(tt("Idle", self.lang))
            self.backend_elapsed_label.setText(tt("Elapsed: 00:00", self.lang))
        self.btn_import_external_prediction_tif.setText(tt("Import external label TIF as review result", self.lang))
        self.btn_refresh_result_comparison.setText(tt("Refresh comparison", self.lang))
        self.btn_open_result_comparison_target.setText(tt("Open selected in 3D", self.lang))
        self.btn_show_result_region_in_3d.setText(tt("Highlight selected region", self.lang))
        self.result_review_controller.refresh_result_comparison_if_visible()
        self.btn_start_center.setText(tt("Start Center", self.lang))
        self.btn_ask_agent.setText(tt("Ask Agent", self.lang))
        self.material_table.setHorizontalHeaderLabels(
            ["", tt("ID", self.lang), tt("Name", self.lang), tt("Train", self.lang)]
        )
        self.local_axis_controller.update_summary()

    def _update_volume_control_tooltips(self):
        pairs = (
            (
                self.volume_projection_label,
                self.volume_projection_combo,
                "Switches how values along the viewing ray are projected. MIP highlights bright structures, MinIP highlights dark gaps, Average shows density trend, and Surface emphasizes boundaries.",
            ),
            (
                self.volume_cutoff_label,
                self.volume_cutoff_slider,
                "Filters low-gray background and noise. Raise it for outer shape review; lower it when weak internal structures disappear.",
            ),
            (
                self.volume_quality_label,
                self.volume_quality_slider,
                "Controls the maximum edge length of the still GPU volume. Dragging uses a smaller temporary texture, then rebuilds this sharper texture when the view settles.",
            ),
            (
                self.volume_sample_label,
                self.volume_sample_slider,
                "Controls the number of samples per screen pixel along the viewing ray. Higher values stabilize internal layers and fine lines, mainly increasing GPU compute load.",
            ),
            (
                self.volume_clarity_check,
                self.volume_clarity_check,
                "Sharp still rendering keeps more source intensity detail and uses crisper sampling. It may upload more data and can look grainier while revealing fine internal structures.",
            ),
            (
                self.volume_transfer_opacity_label,
                self.volume_transfer_opacity_slider,
                "Controls how strongly dense voxels accumulate in 3D. Lower values make internal layers less blocked; higher values make weak structures more visible.",
            ),
            (
                self.btn_volume_morphology_preset,
                self.btn_volume_morphology_preset,
                "Applies a display-only CT morphology inspection preset for weak internal structures, boundaries, and shell detail.",
            ),
            (
                self.volume_enhancement_label,
                self.volume_enhancement_slider,
                "Enhances fine boundaries while the view is still. It is a display-only aid for checking internal layers and part edges.",
            ),
            (
                self.volume_tone_label,
                self.volume_tone_slider,
                "Adjusts display gamma for 3D rendering. Lower values brighten faint structures; higher values keep dense regions calmer.",
            ),
            (
                self.volume_shader_quality_label,
                self.volume_shader_quality_combo,
                "Controls display-only shader experiments. Inspect presets enables them only for Morphology/Publication, Off disables them, and All still composite applies them broadly while the view is still.",
            ),
            (
                self.volume_surface_refine_check,
                self.volume_surface_refine_check,
                "Refines first surface hits in Surface mode while still. It improves contour stability without affecting Composite rendering.",
            ),
            (
                self.volume_clip_plane_check,
                self.volume_clip_plane_check,
                "Enables a view-aligned GPU clipping plane. It only cuts the display, not the saved TIF, mask, or training data.",
            ),
            (
                self.volume_local_axes_check,
                self.volume_local_axes_check,
                "Shows the locked source Z axis and the selected local output axis on the 3D part preview. This is display-only and does not edit data.",
            ),
            (
                self.volume_clip_plane_depth_label,
                self.volume_clip_plane_depth_slider,
                "Moves the clipping plane through the current 3D view. Use it to peel away outer tissue and inspect inside structures.",
            ),
            (
                self.volume_roi_detail_check,
                self.volume_roi_detail_check,
                "When zoomed in and still, renders the 3D view at a higher offscreen pixel density before scaling it back, improving small-part inspection at the cost of more GPU readback work.",
            ),
            (
                self.volume_roi_inspect_check,
                self.volume_roi_inspect_check,
                "When full-volume ROI bbox text is present, uploads a read-only high-detail crop from the original bbox for 3D inspection. It never writes TIF, mask, part, or training data.",
            ),
            (
                self.volume_roi_scale_label,
                self.volume_roi_scale_slider,
                "Controls the offscreen supersampling factor used by ROI high detail. Higher values make still zoomed views smoother but heavier.",
            ),
            (
                self.volume_roi_budget_label,
                self.volume_roi_budget_combo,
                "Controls the maximum GPU texture memory used by true ROI high-detail crops. High is intended for 8 GB or larger GPUs.",
            ),
            (
                self.volume_inside_label,
                self.volume_inside_slider,
                "Moves the camera into the volume. Use it to enter the specimen and inspect internal structures; keep it at 0 for outer shape review.",
            ),
            (
                self.volume_clip_label,
                self.volume_clip_slider,
                "Cuts away the front part of the current view. Use it to remove blocking outer tissue and inspect deeper structures; keep it at 0 for the full outline.",
            ),
            (
                self.volume_mask_label,
                self.volume_mask_combo,
                "Shows accepted or preview part masks in the 3D view. Boundary is best for checking extraction edges; masked image hides voxels outside the mask.",
            ),
            (
                self.volume_mask_opacity_label,
                self.volume_mask_opacity_slider,
                "Controls how strongly mask boundaries are blended into the 3D inspection view.",
            ),
        )
        for label, slider, text in pairs:
            help_text = tt(text, self.lang)
            label.setToolTip(help_text)
            slider.setToolTip(help_text)
        self.btn_reset_volume_view.setToolTip(tt("Restores the external default view and clears inside depth and front cut.", self.lang))

    def get_agent_context(self):
        return self.agent_context_builder.build()

    def _backend_config_from_ui(self):
        config = sanitize_tif_backend_config(
            {
                "backend_id": self.backend_id_edit.text(),
                "display_name": self.backend_display_edit.text(),
                "python_executable": self.backend_python_edit.text(),
                "export_formats": self.backend_formats_edit.text(),
                "prepare_dataset_command": self.backend_prepare_edit.text(),
                "train_command": self.backend_train_edit.text(),
                "predict_command": self.backend_predict_edit.text(),
                "model_manifest": self.backend_manifest_edit.text(),
            }
        )
        return normalize_tif_backend_runtime_config(config)

    def _load_backend_config_into_ui(self):
        config = normalize_tif_backend_runtime_config(self.backend_config)
        self.backend_config = config
        self.backend_id_edit.setText(config.get("backend_id", ""))
        self.backend_display_edit.setText(config.get("display_name", ""))
        self.backend_python_edit.setText(config.get("python_executable", "python"))
        self.backend_formats_edit.setText(config.get("export_formats", "ome_tiff,nrrd,mha,nifti"))
        self.backend_prepare_edit.setText(config.get("prepare_dataset_command", ""))
        self.backend_train_edit.setText(config.get("train_command", ""))
        self.backend_predict_edit.setText(config.get("predict_command", ""))
        self.backend_manifest_edit.setText(config.get("model_manifest", ""))

    def apply_nnunet_v2_backend_preset(self):
        self.backend_config = normalize_tif_backend_runtime_config(
            nnunet_v2_tif_backend_preset(self.backend_python_edit.text().strip() or "python")
        )
        self._load_backend_config_into_ui()
        message = tt("nnU-Net v2 preset filled. Commands remain editable for other 3D backends.", self.lang)
        self.training_status_label.setText(message)
        self.log(message)

    def _active_part_label_schema_id(self):
        if self.current_volume_scope == "part" and self.current_specimen_id and self.current_part_id:
            part = self.project.get_part(self.current_specimen_id, self.current_part_id, default=None)
            return str(((part or {}).get("training") or {}).get("label_schema_id") or "")
        return ""

    def _populate_label_schema_combo(self, preferred_id=None):
        combo = getattr(self, "label_schema_combo", None)
        if combo is None:
            return
        active_part_schema_id = self._active_part_label_schema_id()
        if preferred_id is not None:
            current = str(preferred_id or "")
        elif active_part_schema_id:
            current = active_part_schema_id
        else:
            current = str(combo.currentData() if combo.count() else "")
        combo.blockSignals(True)
        combo.clear()
        for schema in self.project.project_data.get("label_schemas", []) or []:
            if not isinstance(schema, dict):
                continue
            schema_id = str(schema.get("schema_id") or "")
            if not schema_id:
                continue
            label = str(schema.get("display_name") or schema_id)
            combo.addItem(f"{label} ({schema_id})", schema_id)
        index = combo.findData(current)
        combo.setCurrentIndex(index if index >= 0 else (-1 if combo.count() == 0 else 0))
        combo.blockSignals(False)
        self._on_label_schema_selected()

    def _set_label_schema_table_rows(self, labels):
        table = getattr(self, "label_schema_table", None)
        if table is None:
            return
        table.blockSignals(True)
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["", tt("Label ID", self.lang), tt("Region name", self.lang), tt("Color", self.lang)])
        table.setRowCount(0)
        for item in labels or []:
            self._append_label_schema_row(item)
        table.resizeColumnsToContents()
        table.blockSignals(False)

    def _append_label_schema_row(self, item=None):
        table = self.label_schema_table
        item = dict(item or {})
        try:
            label_id = int(item.get("id", table.rowCount() + 1))
        except (TypeError, ValueError):
            label_id = table.rowCount() + 1
        color_text = str(item.get("color") or self._default_schema_label_color(label_id))
        color = QColor(color_text)
        if not color.isValid():
            color = QColor(self._default_schema_label_color(label_id))
            color_text = color.name()
        row = table.rowCount()
        table.insertRow(row)
        swatch = QTableWidgetItem("")
        swatch.setToolTip(color.name())
        swatch.setBackground(color)
        swatch.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        table.setItem(row, 0, swatch)
        table.setItem(row, 1, QTableWidgetItem(str(label_id)))
        name = str(item.get("display_name") or item.get("name") or f"label_{label_id}")
        table.setItem(row, 2, QTableWidgetItem(name))
        table.setItem(row, 3, QTableWidgetItem(color.name()))
        return row

    def _default_schema_label_color(self, label_id):
        palette = ("#F94144", "#43AA8B", "#577590", "#F9C74F", "#90BE6D", "#F3722C", "#277DA1", "#B56576")
        try:
            return palette[(int(label_id) - 1) % len(palette)]
        except Exception:
            return palette[0]

    def _on_label_schema_selected(self, *args):
        schema_id = str(self.label_schema_combo.currentData() or "") if getattr(self, "label_schema_combo", None) else ""
        schema = self.project.get_label_schema(schema_id, default=None) if schema_id else None
        self.label_schema_id_edit.setText(schema_id)
        self.label_schema_part_name_edit.setText(str((schema or {}).get("user_defined_part_name") or ""))
        self._set_label_schema_table_rows((schema or {}).get("labels") or [])
        if self.current_volume_scope == "part" and schema_id == self._active_part_label_schema_id():
            self._select_label_schema_row_for_material(self.current_material_id)

    def _label_schema_row_material_id(self, row):
        table = getattr(self, "label_schema_table", None)
        if table is None or row < 0 or row >= table.rowCount():
            return None
        item = table.item(row, 1)
        try:
            label_id = int(str(item.text() if item is not None else "").strip())
        except (TypeError, ValueError):
            return None
        return label_id if label_id > 0 else None

    def _select_label_schema_row_for_material(self, material_id):
        if self.current_volume_scope != "part" or not hasattr(self, "label_schema_table"):
            return False
        active_schema_id = self._active_part_label_schema_id()
        selected_schema_id = self._selected_label_schema_id() if hasattr(self, "label_schema_combo") else ""
        if not active_schema_id or selected_schema_id != active_schema_id:
            return False
        try:
            target_id = int(material_id)
        except Exception:
            target_id = 0
        if target_id <= 0:
            return False
        table = self.label_schema_table
        for row in range(table.rowCount()):
            if self._label_schema_row_material_id(row) == target_id:
                table.blockSignals(True)
                table.selectRow(row)
                table.blockSignals(False)
                return True
        return False

    def _on_label_schema_row_selected(self):
        if self.current_volume_scope != "part":
            return
        if self._selected_label_schema_id() != self._active_part_label_schema_id():
            return
        label_id = self._label_schema_row_material_id(self.label_schema_table.currentRow())
        if label_id is None:
            return
        self.part_mask_workflow_controller._set_current_material_id(label_id, select_row=True, show_message=not self._loading_specimen)

    def new_label_schema(self):
        part_name = str(self.current_part_id or "").strip()
        if not part_name and isinstance(self.current_part, dict):
            part_name = str(self.current_part.get("part_id") or self.current_part.get("display_name") or "").strip()
        clean_part = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in part_name).strip("_").lower()
        base = f"{clean_part}_regions" if clean_part else "generic_regions"
        existing = {
            str((schema or {}).get("schema_id") or "")
            for schema in self.project.project_data.get("label_schemas", []) or []
            if isinstance(schema, dict)
        }
        candidate = base
        suffix = 2
        while candidate in existing:
            candidate = f"{base}_{suffix}"
            suffix += 1
        self.label_schema_combo.blockSignals(True)
        self.label_schema_combo.setCurrentIndex(-1)
        self.label_schema_combo.blockSignals(False)
        self.label_schema_id_edit.setText(candidate)
        self.label_schema_part_name_edit.setText(part_name or "part")
        self._set_label_schema_table_rows(
            [
                {"id": 1, "name": "label_1", "color": "#F94144"},
                {"id": 2, "name": "label_2", "color": "#43AA8B"},
            ]
        )
        self.label_schema_id_edit.setFocus(Qt.OtherFocusReason)
        self.label_schema_id_edit.selectAll()
        self._set_operation_feedback(tt("Drafted label schema {0}. Edit labels, then save or bind it to the current part.", self.lang).format(candidate))
        return candidate

    def add_label_schema_row(self):
        existing_ids = []
        for row in range(self.label_schema_table.rowCount()):
            item = self.label_schema_table.item(row, 1)
            try:
                existing_ids.append(int(item.text()))
            except Exception:
                continue
        next_id = max(existing_ids or [0]) + 1
        row = self._append_label_schema_row({"id": next_id, "name": f"label_{next_id}", "color": self._default_schema_label_color(next_id)})
        self.label_schema_table.selectRow(row)
        return row

    def remove_selected_label_schema_row(self):
        table = self.label_schema_table
        row = table.currentRow()
        if row < 0 and table.selectedItems():
            row = table.selectedItems()[0].row()
        if row >= 0:
            table.removeRow(row)
            return True
        return False

    def _label_schema_rows_from_table(self):
        labels = []
        used = set()
        for row in range(self.label_schema_table.rowCount()):
            id_item = self.label_schema_table.item(row, 1)
            name_item = self.label_schema_table.item(row, 2)
            color_item = self.label_schema_table.item(row, 3)
            try:
                label_id = int(str(id_item.text() if id_item is not None else "").strip())
            except (TypeError, ValueError):
                continue
            if label_id <= 0 or label_id in used:
                continue
            used.add(label_id)
            name = str(name_item.text() if name_item is not None else "").strip() or f"label_{label_id}"
            color = QColor(str(color_item.text() if color_item is not None else "").strip())
            if not color.isValid():
                color = QColor(self._default_schema_label_color(label_id))
            labels.append(
                {
                    "id": label_id,
                    "name": name,
                    "display_name": name,
                    "color": color.name(),
                    "trainable": True,
                }
            )
        labels.sort(key=lambda item: int(item.get("id", 0)))
        return labels

    def _on_label_schema_table_item_changed(self, item):
        if item is None or item.column() != 3:
            return
        color = QColor(str(item.text() or ""))
        if not color.isValid():
            return
        swatch = self.label_schema_table.item(item.row(), 0)
        if swatch is not None:
            swatch.setBackground(color)
            swatch.setToolTip(color.name())

    def _choose_label_schema_row_color(self, row):
        if row < 0 or row >= self.label_schema_table.rowCount():
            return False
        color_item = self.label_schema_table.item(row, 3)
        current = QColor(str(color_item.text() if color_item is not None else ""))
        if not current.isValid():
            id_item = self.label_schema_table.item(row, 1)
            try:
                label_id = int(id_item.text() if id_item is not None else row + 1)
            except Exception:
                label_id = row + 1
            current = QColor(self._default_schema_label_color(label_id))
        chosen = QColorDialog.getColor(current, self, tt("Choose label color", self.lang))
        if not chosen.isValid():
            return False
        if color_item is None:
            color_item = QTableWidgetItem(chosen.name())
            self.label_schema_table.setItem(row, 3, color_item)
        else:
            color_item.setText(chosen.name())
        swatch = self.label_schema_table.item(row, 0)
        if swatch is not None:
            swatch.setBackground(chosen)
            swatch.setToolTip(chosen.name())
        return True

    def _on_label_schema_table_cell_double_clicked(self, row, column):
        if column in (0, 3):
            self._choose_label_schema_row_color(row)

    def save_current_label_schema(self):
        schema_id = self.label_schema_id_edit.text().strip()
        if not schema_id:
            self._set_operation_feedback(tt("Select or create a label schema before saving.", self.lang))
            return None
        labels = self._label_schema_rows_from_table()
        schema = self.project.add_or_update_label_schema(
            schema_id,
            labels=labels,
            user_defined_part_name=self.label_schema_part_name_edit.text().strip(),
            display_name=schema_id,
            save=True,
        )
        self._populate_label_schema_combo(schema.get("schema_id", schema_id))
        self._populate_result_region_combo()
        self.part_mask_workflow_controller._refresh_active_part_material_schema()
        self.result_review_controller.refresh_result_comparison_if_visible()
        self._set_operation_feedback(tt("Saved label schema {0}.", self.lang).format(schema.get("schema_id", schema_id)))
        return schema

    def bind_current_part_label_schema(self):
        if self.current_volume_scope != "part" or not self.current_specimen_id or not self.current_part_id:
            self._set_operation_feedback(tt("Select a part volume before binding a label schema.", self.lang))
            return False
        schema = self.save_current_label_schema()
        if not schema:
            return False
        schema_id = str(schema.get("schema_id") or "")
        self.project.set_part_training_metadata(
            self.current_specimen_id,
            self.current_part_id,
            user_defined_part_name=str(schema.get("user_defined_part_name") or self.label_schema_part_name_edit.text().strip() or self.current_part_id),
            label_schema_id=schema_id,
            save=True,
        )
        self.current_part = self.project.get_part(self.current_specimen_id, self.current_part_id, default=self.current_part)
        self.part_mask_workflow_controller._refresh_active_part_material_schema()
        self.refresh_project()
        self._select_volume_tree_item(self.current_specimen_id, "part", self.current_part_id, self.current_reslice_id)
        self._set_operation_feedback(tt("Bound label schema {0} to current part {1}.", self.lang).format(schema_id, self.current_part_id))
        return True

    def _selected_label_schema_id(self):
        schema_id = str(self.label_schema_combo.currentData() or "") if getattr(self, "label_schema_combo", None) else ""
        return schema_id or str(self.label_schema_id_edit.text() or "").strip()

    def export_label_schema_dialog(self):
        schema_id = self._selected_label_schema_id()
        if not schema_id:
            self._set_operation_feedback(tt("Select a label schema before exporting.", self.lang))
            return ""
        default_dir = os.path.join(self.project.project_dir, "exports", "label_schemas")
        os.makedirs(default_dir, exist_ok=True)
        default_name = self._safe_export_name_fragment(schema_id, "label_schema") + ".json"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            tt("Export Label Schema", self.lang),
            os.path.join(default_dir, default_name),
            tt("TaxaMask label schema (*.json)", self.lang),
        )
        if not file_path:
            return ""
        try:
            self.project.export_label_schema(schema_id, file_path)
        except Exception as exc:
            message = tt("Label schema export failed: {0}", self.lang).format(str(exc))
            self._set_operation_feedback(message)
            QMessageBox.warning(self, tt("Export Label Schema", self.lang), message)
            return ""
        message = tt("Exported label schema {0}: {1}", self.lang).format(schema_id, file_path)
        self._set_operation_feedback(message)
        self.log(message)
        return file_path

    def _label_schema_id_from_import_file(self, file_path):
        with open(file_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            return ""
        source = payload.get("label_schema") if isinstance(payload.get("label_schema"), dict) else payload
        if not isinstance(source, dict):
            return ""
        return str(source.get("schema_id") or source.get("id") or source.get("name") or "").strip()

    def import_label_schema_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            tt("Import Label Schema", self.lang),
            self.project.project_dir,
            tt("TaxaMask label schema (*.json)", self.lang),
        )
        if not file_path:
            return None
        try:
            incoming_schema_id = self._label_schema_id_from_import_file(file_path)
            if incoming_schema_id and self.project.get_label_schema(incoming_schema_id, default=None) is not None:
                reply = QMessageBox.question(
                    self,
                    tt("Import Label Schema", self.lang),
                    tt("Label schema {0} already exists. Replace it with the imported schema?", self.lang).format(incoming_schema_id),
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if reply != QMessageBox.Yes:
                    return None
            schema = self.project.import_label_schema(file_path, replace=True, save=True)
        except Exception as exc:
            message = tt("Label schema import failed: {0}", self.lang).format(str(exc))
            self._set_operation_feedback(message)
            QMessageBox.warning(self, tt("Import Label Schema", self.lang), message)
            return None
        schema_id = str(schema.get("schema_id") or "")
        self._populate_label_schema_combo(schema_id)
        self._populate_result_region_combo()
        self.part_mask_workflow_controller._refresh_active_part_material_schema()
        self.result_review_controller.refresh_result_comparison_if_visible()
        message = tt("Imported label schema {0}.", self.lang).format(schema_id)
        self._set_operation_feedback(message)
        self.log(message)
        return schema

    def _part_user_tags_for_current_part(self):
        if self.current_volume_scope != "part" or not self.current_specimen_id or not self.current_part_id:
            return []
        part = self.project.get_part(self.current_specimen_id, self.current_part_id, default={}) or {}
        return [str(item) for item in (part.get("user_tags") or []) if str(item or "")]

    def _update_part_user_tag_color_swatch(self, *args):
        if not hasattr(self, "part_user_tag_color_swatch"):
            return
        color = QColor(str(self.part_user_tag_color_edit.text() or "#6B8AFD"))
        if not color.isValid():
            color = QColor("#6B8AFD")
        self.part_user_tag_color_swatch.setToolTip(color.name())
        self.part_user_tag_color_swatch.setStyleSheet(
            "QLabel#tifPartUserTagColorSwatch {"
            f"background: {color.name()};"
            "border: 1px solid #D7E0E4;"
            "border-radius: 5px;"
            "}"
        )

    def choose_part_user_tag_color(self):
        current = QColor(str(self.part_user_tag_color_edit.text() or "#6B8AFD"))
        if not current.isValid():
            current = QColor("#6B8AFD")
        chosen = QColorDialog.getColor(current, self, tt("Choose group color", self.lang))
        if not chosen.isValid():
            return False
        self.part_user_tag_color_edit.setText(chosen.name())
        self._update_part_user_tag_color_swatch()
        return True

    def _populate_part_user_tag_table(self):
        table = getattr(self, "part_user_tag_table", None)
        if table is None:
            return
        selected_id = self._selected_part_user_tag_id()
        assigned = set(self._part_user_tags_for_current_part())
        tags = [tag for tag in self.project.project_data.get("part_user_tags", []) or [] if isinstance(tag, dict)]
        tags.sort(key=lambda item: int((item or {}).get("order_index", 0)))
        table.blockSignals(True)
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["", tt("Group tag ID", self.lang), tt("Group tag label", self.lang), tt("Color", self.lang), tt("Assigned", self.lang)])
        table.setRowCount(0)
        for row, tag in enumerate(tags):
            table.insertRow(row)
            tag_id = str(tag.get("tag_id") or "")
            color = QColor(str(tag.get("color") or "#6B8AFD"))
            if not color.isValid():
                color = QColor("#6B8AFD")
            swatch = QTableWidgetItem("")
            swatch.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            swatch.setToolTip(color.name())
            swatch.setBackground(color)
            table.setItem(row, 0, swatch)
            id_item = QTableWidgetItem(tag_id)
            id_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            id_item.setData(Qt.UserRole, tag_id)
            table.setItem(row, 1, id_item)
            label_item = QTableWidgetItem(str(tag.get("label") or tag_id))
            label_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            table.setItem(row, 2, label_item)
            color_item = QTableWidgetItem(color.name())
            color_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            table.setItem(row, 3, color_item)
            assigned_item = QTableWidgetItem("")
            assigned_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            assigned_item.setCheckState(Qt.Checked if tag_id in assigned else Qt.Unchecked)
            assigned_item.setData(Qt.UserRole, tag_id)
            table.setItem(row, 4, assigned_item)
        table.resizeColumnsToContents()
        table.blockSignals(False)
        target_row = -1
        if selected_id:
            for row in range(table.rowCount()):
                item = table.item(row, 1)
                if item is not None and item.text() == selected_id:
                    target_row = row
                    break
        if target_row >= 0:
            table.selectRow(target_row)
        elif table.rowCount() > 0:
            table.selectRow(0)
        self._on_part_user_tag_selected()
        self._update_part_user_tag_color_swatch()

    def _selected_part_user_tag_id(self):
        table = getattr(self, "part_user_tag_table", None)
        if table is None:
            return ""
        row = table.currentRow()
        if row < 0 and table.selectedItems():
            row = table.selectedItems()[0].row()
        item = table.item(row, 1) if row >= 0 else None
        return str(item.data(Qt.UserRole) or item.text() or "") if item is not None else ""

    def _on_part_user_tag_selected(self):
        tag_id = self._selected_part_user_tag_id()
        tag = None
        for item in self.project.project_data.get("part_user_tags", []) or []:
            if isinstance(item, dict) and str(item.get("tag_id") or "") == tag_id:
                tag = item
                break
        self._selected_part_user_tag_id_for_edit = tag_id
        if tag is None:
            return
        self.part_user_tag_id_edit.setText(tag_id)
        self.part_user_tag_label_edit.setText(str(tag.get("label") or tag_id))
        color = QColor(str(tag.get("color") or "#6B8AFD"))
        self.part_user_tag_color_edit.setText(color.name() if color.isValid() else "#6B8AFD")
        self._update_part_user_tag_color_swatch()

    def new_part_user_tag(self):
        base = "round_1"
        existing = {
            str((tag or {}).get("tag_id") or "")
            for tag in self.project.project_data.get("part_user_tags", []) or []
            if isinstance(tag, dict)
        }
        candidate = base
        suffix = 2
        while candidate in existing:
            candidate = f"round_{suffix}"
            suffix += 1
        self._selected_part_user_tag_id_for_edit = ""
        self.part_user_tag_id_edit.setText(candidate)
        self.part_user_tag_label_edit.setText("Round 1" if candidate == base else f"Round {suffix - 1}")
        self.part_user_tag_color_edit.setText("#6B8AFD")
        self._update_part_user_tag_color_swatch()
        self.part_user_tag_id_edit.setFocus(Qt.OtherFocusReason)
        self.part_user_tag_id_edit.selectAll()
        self._set_operation_feedback(tt("Drafted group tag {0}. Save it, then check Assigned and apply it to the current part.", self.lang).format(candidate))
        return candidate

    def save_part_user_tag(self):
        tag_id = self.part_user_tag_id_edit.text().strip()
        if not tag_id:
            return None
        color = QColor(str(self.part_user_tag_color_edit.text() or "#6B8AFD"))
        if not color.isValid():
            color = QColor("#6B8AFD")
        existing_ids = [
            str((tag or {}).get("tag_id") or "")
            for tag in self.project.project_data.get("part_user_tags", []) or []
            if isinstance(tag, dict)
        ]
        order_index = existing_ids.index(tag_id) if tag_id in existing_ids else len(existing_ids)
        tag = self.project.upsert_part_user_tag(
            tag_id,
            self.part_user_tag_label_edit.text().strip() or tag_id,
            color.name(),
            order_index=order_index,
            save=True,
        )
        self._populate_part_user_tag_table()
        self.backend_panel_controller.refresh_predict_targets()
        self.refresh_project()
        self._set_operation_feedback(tt("Saved part tag {0}.", self.lang).format(tag.get("label") or tag_id))
        return tag

    def delete_selected_part_user_tag(self):
        tag_id = self._selected_part_user_tag_id_for_edit or self._selected_part_user_tag_id()
        if not tag_id:
            return False
        if not self.project.delete_part_user_tag(tag_id, save=True):
            return False
        self._selected_part_user_tag_id_for_edit = ""
        self._populate_part_user_tag_table()
        self.backend_panel_controller.refresh_predict_targets()
        self.refresh_project()
        self._set_operation_feedback(tt("Deleted part tag {0}.", self.lang).format(tag_id))
        return True

    def _part_user_tag_order_from_table(self):
        order = []
        for row in range(self.part_user_tag_table.rowCount()):
            item = self.part_user_tag_table.item(row, 1)
            tag_id = str(item.data(Qt.UserRole) or item.text() or "") if item is not None else ""
            if tag_id and tag_id not in order:
                order.append(tag_id)
        return order

    def save_part_user_tag_order_from_table(self):
        if not hasattr(self, "part_user_tag_table"):
            return []
        order = self._part_user_tag_order_from_table()
        tags = self.project.set_part_user_tag_order(order, save=True)
        self._populate_part_user_tag_table()
        self.backend_panel_controller.refresh_predict_targets()
        return tags

    def move_selected_part_user_tag(self, delta):
        table = self.part_user_tag_table
        row = table.currentRow()
        if row < 0:
            return False
        target = max(0, min(table.rowCount() - 1, row + int(delta)))
        if target == row:
            return False
        order = self._part_user_tag_order_from_table()
        item = order.pop(row)
        order.insert(target, item)
        self.project.set_part_user_tag_order(order, save=True)
        self._populate_part_user_tag_table()
        table.selectRow(target)
        self.backend_panel_controller.refresh_predict_targets()
        return True

    def apply_part_user_tags_to_current_part(self):
        if self.current_volume_scope != "part" or not self.current_specimen_id or not self.current_part_id:
            self._set_operation_feedback(tt("Select a part volume before assigning tags.", self.lang))
            return False
        selected = []
        for row in range(self.part_user_tag_table.rowCount()):
            item = self.part_user_tag_table.item(row, 4)
            if item is not None and item.checkState() == Qt.Checked:
                tag_id = str(item.data(Qt.UserRole) or "")
                if tag_id:
                    selected.append(tag_id)
        self.project.set_part_user_tags(self.current_specimen_id, self.current_part_id, selected, save=True)
        self.current_part = self.project.get_part(self.current_specimen_id, self.current_part_id, default=self.current_part)
        self._populate_part_user_tag_table()
        self.backend_panel_controller.refresh_predict_targets()
        self.refresh_project()
        self._select_volume_tree_item(self.current_specimen_id, "part", self.current_part_id, self.current_reslice_id)
        self._set_operation_feedback(tt("Applied {0} user tag(s) to current part.", self.lang).format(len(selected)))
        return True

    def _part_user_tag_lookup(self):
        return {
            str((tag or {}).get("tag_id") or ""): str((tag or {}).get("label") or (tag or {}).get("tag_id") or "")
            for tag in self.project.project_data.get("part_user_tags", []) or []
            if isinstance(tag, dict) and str((tag or {}).get("tag_id") or "")
        }

    def _format_count(self, value):
        try:
            return f"{int(value):,}"
        except (TypeError, ValueError):
            return "0"

    def browse_model_manifest(self):
        start_dir = os.path.dirname(str(self.backend_manifest_edit.text() or "").strip())
        if not start_dir or not os.path.isdir(start_dir):
            start_dir = self.project.project_dir or os.getcwd()
        path, _filter = QFileDialog.getOpenFileName(
            self,
            tt("Select model manifest", self.lang),
            start_dir,
            "JSON (*.json);;All files (*)",
        )
        if not path:
            return False
        self.backend_manifest_edit.setText(path)
        self.backend_config["model_manifest"] = path
        self._set_operation_feedback(tt("Selected model manifest: {0}", self.lang).format(path))
        return True

    def use_selected_tif_model(self):
        record = self.backend_panel_controller.selected_model_record()
        if not record:
            QMessageBox.information(self, tt("Trained model", self.lang), tt("No trained model is selected.", self.lang))
            return False
        manifest = self.project.to_absolute(record.get("model_manifest", ""))
        if not manifest or not os.path.exists(manifest):
            message = tt("Model manifest does not exist: {0}", self.lang).format(manifest or "-")
            QMessageBox.warning(self, tt("Trained model", self.lang), message)
            self._set_operation_feedback(message)
            return False
        self.backend_manifest_edit.setText(manifest)
        self.backend_config["model_manifest"] = manifest
        self._set_operation_feedback(tt("Selected trained model for prediction.", self.lang))
        return True

    def save_selected_tif_model_notes(self):
        record = self.backend_panel_controller.selected_model_record()
        if not record:
            QMessageBox.information(self, tt("Trained model", self.lang), tt("No trained model is selected.", self.lang))
            return False
        model_id = self.backend_panel_controller.model_record_id(record)
        notes = self.model_library_notes_edit.toPlainText() if hasattr(self, "model_library_notes_edit") else ""
        try:
            updated = self.project.update_tif_segmentation_model_notes(model_id, notes, save=True)
        except Exception as exc:
            QMessageBox.warning(self, tt("Trained model", self.lang), str(exc))
            return False
        self.backend_panel_controller.populate_model_library_combo(self.backend_panel_controller.model_record_id(updated))
        self._set_operation_feedback(tt("Model notes saved.", self.lang))
        return True

    def delete_selected_tif_model_record(self):
        record = self.backend_panel_controller.selected_model_record()
        if not record:
            QMessageBox.information(self, tt("Trained model", self.lang), tt("No trained model is selected.", self.lang))
            return False
        model_id = self.backend_panel_controller.model_record_id(record)
        reply = QMessageBox.question(
            self,
            tt("Trained model", self.lang),
            tt("Delete this model registration from the project? The model files on disk will not be deleted.", self.lang),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return False
        removed = self.project.delete_tif_segmentation_model(model_id, save=True)
        if removed is None:
            QMessageBox.warning(self, tt("Trained model", self.lang), tt("No trained model is selected.", self.lang))
            return False
        if self.backend_manifest_edit.text().strip() == self.project.to_absolute((record or {}).get("model_manifest", "")):
            self.backend_manifest_edit.clear()
            self.backend_config["model_manifest"] = ""
        self.backend_panel_controller.populate_model_library_combo()
        self._set_operation_feedback(tt("Model registration deleted. Model files were left on disk.", self.lang))
        return True

    def log(self, message):
        if not hasattr(self, "log_console"):
            return
        self.log_console.append(f"[{_now_log_time()}] {message}")

    def _set_operation_feedback(self, message, log=True):
        text = str(message or "")
        if not text:
            return
        if hasattr(self, "training_status_label"):
            self.training_status_label.setText(text)
        elif hasattr(self, "operation_status_label"):
            self.operation_status_label.setText(text)
        if log:
            self.log(text)

    def show_workbench_log(self):
        if hasattr(self, "task_tabs") and hasattr(self, "training_mode_tabs"):
            self.task_tabs.setCurrentWidget(self.training_mode_tabs)
            self.training_mode_tabs.setCurrentWidget(self.training_task_page)

    def _set_local_axis_status(self, message, tooltip=""):
        label = getattr(self, "local_axis_status_label", None)
        if label is not None:
            label.setText(str(message or ""))
            label.setToolTip(str(tooltip or message or ""))

    def canvas_status_text(self, zoom_factor):
        if self.image_volume is None:
            return ""
        axis = self._current_slice_axis()
        index = int(self.slice_slider.value()) + 1
        total = self._slice_count_for_axis(axis)
        return f"{axis.upper()} {index}/{total} · {int(round(float(zoom_factor) * 100))}%"

    def move_slice(self, delta):
        if self.image_volume is None:
            return
        current = int(self.slice_slider.value())
        target = max(self.slice_slider.minimum(), min(self.slice_slider.maximum(), current + int(delta)))
        if target == current:
            return
        self.slice_slider.setValue(target)

    def on_slice_slider_changed(self):
        self._slice_positions[self._current_slice_axis()] = int(self.slice_slider.value())
        self.render_current_slice()

    def on_slice_axis_changed(self):
        axis = self.slice_axis_combo.currentData() or "z"
        self.slice_axis = axis if axis in {"z", "y", "x"} else "z"
        self._configure_slice_slider_for_axis(self.slice_axis, preserve_position=True)
        self._reset_canvas_view_on_next_render = True
        if self.slice_axis != "z":
            self.part_mask_workflow_controller.disable_contour_draw_mode()
            self.btn_draw_part_contour.blockSignals(True)
            self.btn_draw_part_contour.setChecked(False)
            self.btn_draw_part_contour.blockSignals(False)
            message = tt("Side-angle slices are read-only in this version. Use Z axial view for label editing.", self.lang)
            self.training_status_label.setText(message)
            self.log(message)
        self._set_scope_controls_enabled()
        self.render_current_slice()

    def on_display_mode_changed(self, mode=None):
        requested_mode = mode if isinstance(mode, str) else self.display_mode_combo.currentData()
        self.display_mode = requested_mode if requested_mode in {"slice", "volume"} else "slice"
        combo_index = self.display_mode_combo.findData(self.display_mode)
        if combo_index >= 0 and self.display_mode_combo.currentIndex() != combo_index:
            self.display_mode_combo.blockSignals(True)
            self.display_mode_combo.setCurrentIndex(combo_index)
            self.display_mode_combo.blockSignals(False)
        if self.display_mode == "volume":
            self._ensure_volume_canvas()
        if hasattr(self, "view_stack"):
            self.view_stack.setCurrentWidget(self.volume_canvas if self.display_mode == "volume" else self.canvas)
        if hasattr(self, "volume_render_status_label"):
            self.volume_render_status_label.setVisible(self.display_mode == "volume")
        self._sync_mode_sections()
        is_volume = self.display_mode == "volume"
        if is_volume:
            self.roi_workflow_controller.disable_draw_mode()
            self.part_mask_workflow_controller.disable_contour_draw_mode()
            reslice_open_error = ""
            self.btn_part_draw_roi.blockSignals(True)
            self.btn_part_draw_roi.setChecked(False)
            self.btn_part_draw_roi.blockSignals(False)
            self.btn_draw_part_contour.blockSignals(True)
            self.btn_draw_part_contour.setChecked(False)
            self.btn_draw_part_contour.blockSignals(False)
        volume_mode_controls = (
            self.volume_sample_label,
            self.volume_sample_slider,
            self.volume_clarity_check,
            self.volume_enhancement_label,
            self.volume_enhancement_slider,
            self.volume_tone_label,
            self.volume_tone_slider,
            self.volume_shader_quality_label,
            self.volume_shader_quality_combo,
            self.volume_surface_refine_check,
            self.volume_roi_detail_check,
            self.volume_roi_source_combo,
            self.volume_roi_inspect_check,
            self.volume_roi_scale_label,
            self.volume_roi_scale_slider,
            self.volume_roi_budget_label,
            self.volume_roi_budget_combo,
            self.volume_clip_plane_check,
            self.volume_clip_plane_depth_label,
            self.volume_clip_plane_depth_slider,
            self.volume_inside_label,
            self.volume_inside_slider,
            self.volume_clip_label,
            self.volume_clip_slider,
        )
        for widget in (
            self.slice_axis_label,
            self.slice_axis_combo,
            self.slice_prefix_label,
            self.slice_slider,
            self.slice_label,
            self.volume_sample_label,
            self.volume_sample_slider,
            self.volume_clarity_check,
            self.volume_enhancement_label,
            self.volume_enhancement_slider,
            self.volume_tone_label,
            self.volume_tone_slider,
            self.volume_shader_quality_label,
            self.volume_shader_quality_combo,
            self.volume_surface_refine_check,
            self.volume_roi_detail_check,
            self.volume_roi_source_combo,
            self.volume_roi_inspect_check,
            self.volume_roi_scale_label,
            self.volume_roi_scale_slider,
            self.volume_roi_budget_label,
            self.volume_roi_budget_combo,
            self.volume_clip_plane_check,
            self.volume_clip_plane_depth_label,
            self.volume_clip_plane_depth_slider,
            self.volume_inside_label,
            self.volume_inside_slider,
            self.volume_clip_label,
            self.volume_clip_slider,
        ):
            is_volume_control = any(widget is control for control in volume_mode_controls)
            widget.setVisible(is_volume if is_volume_control else not is_volume)
        if is_volume:
            message = self.volume_render_controller._volume_renderer_status_message()
            self.training_status_label.setText(message)
            self.log(message)
            if self.part_mask_workflow_controller.materialize_current_tif_metadata():
                self._set_scope_controls_enabled()
                return
            self._apply_default_volume_mask_mode()
            self._set_scope_controls_enabled()
            request = self.volume_render_controller._volume_preview_request("still")
            message = (request or {}).get("message") or tt("Preparing full-volume 3D preview...", self.lang)
            show_canvas_status = self.volume_render_controller._set_volume_canvas_status_text(message)
            self.volume_render_controller._update_volume_render_status_label(message)
            if show_canvas_status:
                QApplication.processEvents()
            self.volume_render_controller.render_volume_preview()
        else:
            self._set_scope_controls_enabled()
            self.render_current_slice()

    def _sync_mode_sections(self):
        is_volume = self.display_mode == "volume"
        is_part = self.current_volume_scope == "part"
        is_full = not is_part
        self._place_local_axis_volume_section(is_volume=is_volume, is_part=is_part)
        if hasattr(self, "slice_display_section"):
            self.slice_display_section.setVisible(not is_volume)
        if hasattr(self, "material_section"):
            self.material_section.setVisible(not is_volume)
        if hasattr(self, "annotation_section"):
            self.annotation_section.setVisible(not is_volume)
        if hasattr(self, "volume_render_section"):
            self.volume_render_section.setVisible(is_volume)
        if hasattr(self, "local_axis_volume_section"):
            self.local_axis_volume_section.setVisible(is_part)
        if hasattr(self, "part_locate_section"):
            self.part_locate_section.setVisible(is_full and not is_volume)
        if hasattr(self, "part_mask_section"):
            self.part_mask_section.setVisible(not is_volume)
        if hasattr(self, "part_output_section"):
            self.part_output_section.setVisible(is_part and not is_volume)
        if hasattr(self, "task_tabs"):
            current = self.task_tabs.currentWidget()
            if current is not getattr(self, "training_mode_tabs", None):
                target = self.display_task_page if is_volume else self.part_task_page
                if current is not target:
                    self.task_tabs.setCurrentWidget(target)
        self.local_axis_controller.update_summary()

    def _place_local_axis_volume_section(self, is_volume=None, is_part=None):
        section = getattr(self, "local_axis_volume_section", None)
        if section is None:
            return
        is_volume = self.display_mode == "volume" if is_volume is None else bool(is_volume)
        is_part = self.current_volume_scope == "part" if is_part is None else bool(is_part)
        if is_volume and is_part and hasattr(self, "display_task_layout"):
            if self.display_task_layout.indexOf(section) != 0:
                self.display_task_layout.insertWidget(0, section)
            return
        if hasattr(self, "part_task_layout") and hasattr(self, "part_output_section"):
            output_index = self.part_task_layout.indexOf(self.part_output_section)
            target_index = output_index if output_index >= 0 else self.part_task_layout.count()
            current_index = self.part_task_layout.indexOf(section)
            if current_index != target_index - (1 if 0 <= current_index < target_index else 0):
                self.part_task_layout.insertWidget(target_index, section)

    def _safe_contour_slice_index(self, keyframe, default=None):
        try:
            return int((keyframe or {}).get("slice_index", default))
        except (TypeError, ValueError, OverflowError):
            return default

    def _empty_contours_payload(self):
        return {
            "schema_version": "taxamask_tif_part_extraction_v1",
            "axis": "z",
            "keyframes": [],
        }

    def _full_volume_contours_payload(self):
        payload = self._empty_contours_payload()
        payload["scope"] = "full_volume_part_mask"
        payload["keyframes"] = self.part_mask_workflow_controller._normalize_full_volume_mask_keyframes(self.part_mask_keyframes)
        return payload

    def _full_volume_contour_bbox(self, contours=None):
        if self.image_volume is None:
            return []
        payload = contours if isinstance(contours, dict) else self._full_volume_contours_payload()
        shape = tuple(int(value) for value in getattr(self.image_volume, "shape", ()) or ())
        if len(shape) != 3:
            return []
        bbox = [[0, 0], [0, 0], [0, 0]]
        for keyframe in payload.get("keyframes", []) or []:
            if not isinstance(keyframe, dict) or str(keyframe.get("axis", "z")) != "z":
                continue
            z_index = self._safe_contour_slice_index(keyframe, None)
            if z_index is None or not (0 <= int(z_index) < shape[0]):
                continue
            points = self.part_mask_workflow_controller._dedupe_contour_points(keyframe.get("polygon") or [])
            if len(points) < 3:
                continue
            xs = [float(point[0]) for point in points]
            ys = [float(point[1]) for point in points]
            bbox[0] = self._expanded_axis_range(bbox[0], int(z_index), shape[0])
            bbox[1] = self._union_axis_range(bbox[1], math.floor(min(ys)), math.ceil(max(ys)) + 1, shape[1])
            bbox[2] = self._union_axis_range(bbox[2], math.floor(min(xs)), math.ceil(max(xs)) + 1, shape[2])
        if any(int(pair[1]) <= int(pair[0]) for pair in bbox):
            return []
        return self._clip_bbox_to_shape(bbox, shape)

    def _full_volume_contours_to_local(self, contours, bbox):
        payload = self._empty_contours_payload()
        if not bbox or len(bbox) != 3:
            return payload
        z0, y0, x0 = int(bbox[0][0]), float(bbox[1][0]), float(bbox[2][0])
        keyframes = []
        for keyframe in (contours or {}).get("keyframes", []) or []:
            if not isinstance(keyframe, dict) or str(keyframe.get("axis", "z")) != "z":
                continue
            z_index = self._safe_contour_slice_index(keyframe, None)
            if z_index is None:
                continue
            local_polygon = []
            for point in self.part_mask_workflow_controller._dedupe_contour_points(keyframe.get("polygon") or []):
                local_polygon.append([round(float(point[0]) - x0, 3), round(float(point[1]) - y0, 3)])
            if len(local_polygon) < 3:
                continue
            keyframes.append(
                {
                    "axis": "z",
                    "slice_index": int(z_index) - z0,
                    "polygon": local_polygon,
                    "author": str(keyframe.get("author") or "taxamask_ui_freehand"),
                    "source": str(keyframe.get("source") or "manual_freehand"),
                    "created_at": str(keyframe.get("created_at") or datetime.now().astimezone().isoformat(timespec="seconds")),
                }
            )
        keyframes.sort(key=lambda item: int(item.get("slice_index", 0)))
        payload["keyframes"] = keyframes
        return payload

    def _connect_volume_canvas_signals(self, canvas):
        controller = self.volume_render_controller
        if hasattr(canvas, "render_failed"):
            canvas.render_failed.connect(controller._on_gpu_volume_failed)
        if hasattr(canvas, "render_info_changed"):
            canvas.render_info_changed.connect(controller._on_gpu_volume_info_changed)
        if hasattr(canvas, "render_stats_changed"):
            canvas.render_stats_changed.connect(controller._on_gpu_volume_stats_changed)

    def _ensure_volume_canvas(self, force_gpu=False):
        if self._volume_canvas_created and not force_gpu:
            return
        old_canvas = getattr(self, "volume_canvas", None)
        if force_gpu and old_canvas is not None and hasattr(old_canvas, "release_gl_resources"):
            try:
                old_canvas.release_gl_resources()
            except Exception:
                pass
        parent = self.view_stack if hasattr(self, "view_stack") else self
        canvas, renderer, warning = create_tif_volume_canvas(parent)
        canvas.workbench = self
        if hasattr(canvas, "set_theme"):
            canvas.set_theme(self.current_theme)
        if not hasattr(canvas, "set_volume_data"):
            canvas.setProperty("tifVolumeRenderer", "cpu")
            renderer = "cpu"
        self._connect_volume_canvas_signals(canvas)
        self.volume_canvas = canvas
        self._volume_canvas_renderer = renderer
        self._volume_renderer_warning = warning
        self._volume_canvas_created = True
        if hasattr(self, "view_stack"):
            self.view_stack.addWidget(self.volume_canvas)
            if self.display_mode == "volume":
                self.view_stack.setCurrentWidget(self.volume_canvas)
            if old_canvas is not None:
                index = self.view_stack.indexOf(old_canvas)
                if index >= 0:
                    self.view_stack.removeWidget(old_canvas)
        if old_canvas is not None:
            old_canvas.hide()
            old_canvas.setParent(None)
            old_canvas.deleteLater()
        if warning:
            self.log(tt("GPU renderer unavailable. Using CPU fallback.", self.lang) + f" {warning}")

    def _reset_volume_canvas_placeholder_for_agent(self):
        canvas = getattr(self, "volume_canvas", None)
        if canvas is None or not getattr(self, "_volume_canvas_created", False):
            return
        renderer_kind = str(canvas.property("tifVolumeRenderer") or "")
        if renderer_kind == "gpu-offscreen":
            return
        if hasattr(canvas, "release_gl_resources"):
            try:
                canvas.release_gl_resources()
            except Exception:
                pass
        placeholder = TifVolumeCanvas()
        placeholder.workbench = self
        placeholder.set_theme(self.current_theme)
        placeholder.setProperty("tifVolumeRenderer", "placeholder")
        self.volume_canvas = placeholder
        self._volume_canvas_renderer = "cpu"
        self._volume_renderer_warning = ""
        self._volume_gl_renderer_info = ""
        self._volume_canvas_created = False
        if hasattr(self, "view_stack"):
            self.view_stack.addWidget(self.volume_canvas)
            if self.display_mode == "volume":
                self.view_stack.setCurrentWidget(self.volume_canvas)
            index = self.view_stack.indexOf(canvas)
            if index >= 0:
                self.view_stack.removeWidget(canvas)
        canvas.hide()
        canvas.setParent(None)
        canvas.deleteLater()

    def _label_role_help_text(self, role=None):
        role = role or self.label_role_combo.currentData()
        if role == "editable_ai_result":
            return tt("Editable AI result is the review layer for this project part. Brush changes are saved here; only accepted results become training truth.", self.lang)
        if role == "raw_ai_prediction_backup":
            return tt("Raw AI prediction backup is read-only and kept for audit. Edit the review result layer instead.", self.lang)
        if role == "working_edit":
            return tt("Current labels are editable. Brush changes are saved here first; accept them as training truth after review.", self.lang)
        if role == "model_draft":
            return tt("Model draft is a legacy read-only prediction copy kept for audit. Current prediction results open as Current labels now.", self.lang)
        return tt("Training truth is the reviewed read-only label used for training. Switch to Current labels before changing labels.", self.lang)

    def _update_label_role_help(self):
        if hasattr(self, "label_role_help_label"):
            self.label_role_help_label.setText(self._label_role_help_text())
        self._update_ai_review_check_label()

    def _format_review_id_list(self, values):
        clean = []
        for value in values or []:
            try:
                clean.append(str(int(value)))
            except (TypeError, ValueError):
                text = str(value or "").strip()
                if text:
                    clean.append(text)
        return ", ".join(clean) if clean else tt("none", self.lang)

    def _format_review_blocker_detail(self, report):
        label_ids = self._format_review_id_list((report or {}).get("label_ids") or [])
        unknown_ids = self._format_review_id_list((report or {}).get("unknown_label_ids") or [])
        schema_id = str((report or {}).get("label_schema_id") or "-")
        if label_ids == tt("none", self.lang):
            label_ids = tt("No labels present", self.lang)
        return tt("Schema {0}; labels present: {1}; unknown labels: {2}", self.lang).format(schema_id, label_ids, unknown_ids)

    def _current_ai_review_check_text(self):
        if self.current_volume_scope != "part" or not self.current_specimen_id or not self.current_part_id:
            return tt("Select a part editable AI result to see review checks.", self.lang)
        try:
            report = self.project.evaluate_part_editable_result_review_ready(
                self.current_specimen_id,
                self.current_part_id,
                self.current_reslice_id,
                validate_label_ids=False,
            )
        except Exception as exc:
            return tt("Review check blocked: {0}", self.lang).format(str(exc))
        checks = report.get("checks") or {}
        if not checks.get("editable_ai_result_exists"):
            detail = self._format_review_blocker_detail(report)
            return "\n".join([tt("No editable AI result is available for this part.", self.lang), detail])
        if (report.get("label_report") or {}).get("skipped") == "label_id_scan_deferred":
            lines = [
                tt("Editable AI result is available. Full label-ID validation will run when you accept it as training truth.", self.lang),
                tt("Schema {0}; label scan deferred until acceptance.", self.lang).format(report.get("label_schema_id") or "-"),
            ]
            if not report.get("opened_for_review"):
                lines.append(tt("This result has not been marked opened for review yet.", self.lang))
            return "\n".join(lines)
        detail = self._format_review_blocker_detail(report)
        if report.get("review_ready") and report.get("opened_for_review"):
            return "\n".join([tt("Review check passed. This editable AI result can be accepted as training truth.", self.lang), detail])
        if report.get("review_ready") and not report.get("opened_for_review"):
            return "\n".join([tt("Review check passed, but this result has not been opened for review yet.", self.lang), detail])
        reasons = self.result_review_controller.format_review_reasons(report) or "-"
        return "\n".join([tt("Review check blocked: {0}", self.lang).format(reasons), detail])

    def _update_ai_review_check_label(self):
        if not hasattr(self, "ai_review_check_label"):
            return
        is_part = self.current_volume_scope == "part"
        self.ai_review_check_title_label.setVisible(is_part)
        self.ai_review_check_label.setVisible(is_part)
        if not is_part:
            self.ai_review_check_label.clear()
            return
        text = self._current_ai_review_check_text()
        self.ai_review_check_title_label.setText(tt("AI review check", self.lang))
        self.ai_review_check_label.setText(text)
        self.ai_review_check_label.setToolTip(text)

    def _advanced_annotation_tool_specs(self):
        return {
            "bucket_fill": {"requires_design": True, "requires_undo_plan": True, "requires_risk_notice": True},
            "slice_propagation": {"requires_design": True, "requires_undo_plan": True, "requires_risk_notice": True},
            "boundary_smoothing": {"requires_design": True, "requires_undo_plan": True, "requires_risk_notice": True},
        }

    def _annotation_tool_buttons(self):
        return {
            "brush": getattr(self, "btn_tool_brush", None),
            "eraser": getattr(self, "btn_tool_eraser", None),
            "lasso": getattr(self, "btn_tool_lasso", None),
            "rectangle": getattr(self, "btn_tool_rectangle", None),
            "ellipse": getattr(self, "btn_tool_ellipse", None),
            "picker": getattr(self, "btn_tool_picker", None),
            "pan": getattr(self, "btn_tool_pan", None),
        }

    def _sync_annotation_tool_buttons(self):
        mode = self.annotation_tool_mode if self.annotation_tool_mode in self.annotation_workflow_controller.TOOL_MODES else "brush"
        self.annotation_tool_mode = mode
        for tool_mode, button in self._annotation_tool_buttons().items():
            if button is None:
                continue
            button.blockSignals(True)
            button.setChecked(tool_mode == mode)
            button.blockSignals(False)
        self.part_mask_workflow_controller._update_current_material_summary()
        if hasattr(self, "canvas"):
            self.canvas._refresh_scaled_pixmap()

    def _sync_undo_redo_buttons(self):
        annotation_state = self.annotation_workflow_controller.state
        if hasattr(self, "btn_undo"):
            self.btn_undo.setEnabled(bool(annotation_state.undo_stack) and self._can_edit_current_label_volume() and not self.coordinator.backend_write_lock_active())
        if hasattr(self, "btn_redo"):
            self.btn_redo.setEnabled(bool(annotation_state.redo_stack) and self._can_edit_current_label_volume() and not self.coordinator.backend_write_lock_active())

    def _update_save_status(self, state=None, detail=""):
        if not hasattr(self, "save_status_label"):
            return
        count = self.annotation_workflow_controller.dirty_slice_count()
        if state == "saving" or getattr(self, "_saving_working_edit", False) or self.annotation_workflow_controller.auto_save_thread is not None or self.annotation_workflow_controller.manual_save_thread is not None:
            text = tt("Saving editable AI result...", self.lang) if self.current_volume_scope == "part" else tt("Saving working edit...", self.lang)
        elif state == "failed":
            text = tt("Save failed: {0}", self.lang).format(detail)
        elif self.working_edit_dirty:
            if self.auto_save_check.isChecked() and self.auto_save_timer.isActive():
                text = tt("Auto-save pending: {0} slice(s)", self.lang).format(count)
            else:
                text = tt("Unsaved changes: {0} slice(s)", self.lang).format(count)
        else:
            text = tt("Saved", self.lang)
        self.save_status_label.setText(text)
        self.save_status_label.setToolTip(text)
        self.save_status_label.setProperty("tifSaveState", state or ("dirty" if self.working_edit_dirty else "saved"))
        self.save_status_label.style().unpolish(self.save_status_label)
        self.save_status_label.style().polish(self.save_status_label)

    def annotation_cursor_preview(self, pixel=None):
        mode = self.annotation_tool_mode if self.annotation_tool_mode in self.annotation_workflow_controller.TOOL_MODES else "brush"
        if mode == "pan":
            return {}
        block_reason = ""
        if mode in {"brush", "eraser", "lasso", "rectangle", "ellipse"}:
            block_reason = self._editable_label_block_reason(require_working_edit=True)
        elif mode == "picker":
            if self.image_volume is None:
                block_reason = ""
            elif self.display_mode == "volume":
                block_reason = tt("3D volume preview is read-only. Switch to Slice review for label editing.", self.lang)
            elif self._current_slice_axis() != "z":
                block_reason = tt("Label picker is available on Z slices only. Switch back to Z axial view before sampling labels.", self.lang)
        else:
            block_reason = tt("Pan/view mode is active. Labels were not changed.", self.lang)
        return {
            "mode": mode,
            "radius": int(self.brush_size_slider.value()) if hasattr(self, "brush_size_slider") else 1,
            "disabled": bool(block_reason),
            "reason": block_reason,
        }

    def _current_edit_save_path(self):
        if self.current_volume_scope == "part":
            return self.annotation_workflow_controller.current_part_label_path("editable_ai_result")
        specimen = self.project.get_specimen(self.current_specimen_id, default=None)
        if specimen is None:
            return ""
        return self.project.to_absolute(((specimen.get("labels") or {}).get("working_edit") or {}).get("path", ""))

    def _can_auto_save_current_edit_volume(self):
        if self.current_volume_scope == "part":
            return self.label_role_combo.currentData() == "editable_ai_result"
        return self.label_role_combo.currentData() == "working_edit"

    def _guard_current_label_save(self, *, role=None, reason="manual", show_message=False):
        clean_role = str(role or ("editable_ai_result" if self.current_volume_scope == "part" else "working_edit"))
        scope = "part" if self.current_volume_scope == "part" else "top_level"
        result = self.label_edit_service.can_save_role(
            clean_role,
            scope=scope,
            reason=reason,
            context={
                "scope": scope,
                "specimen_id": str(self.current_specimen_id or ""),
                "part_id": str(self.current_part_id or ""),
                "reslice_id": str(self.current_reslice_id or ""),
            },
        )
        if result:
            return True
        reason_text = (result.reasons or [result.message or "blocked"])[0]
        message = tt("Cannot save this label layer: {0}", self.lang).format(reason_text)
        self._set_operation_feedback(message)
        self._update_save_status(state="failed", detail=reason_text)
        if show_message:
            QMessageBox.warning(self, tt("Unsaved working edit", self.lang), message)
        return False

    def save_working_edit_async(self, show_message=True, promote_request=None):
        return self.annotation_workflow_controller.save_async(show_message=show_message, promote_request=promote_request)

    def save_backend_settings(self):
        self.backend_config = self._backend_config_from_ui()
        if self.config_manager is not None:
            self.config_manager.set("tif_backend", dict(self.backend_config))
            self.config_manager.save()
        self.training_status_label.setText(tt("Backend settings saved.", self.lang))
        self.log(tt("Backend settings saved.", self.lang))
        QMessageBox.information(self, tt("TIF backend", self.lang), tt("Backend settings saved.", self.lang))

    def _ensure_tif_project_open(self):
        if not self.project.current_project_path:
            QMessageBox.warning(
                self,
                tt("TIF data import", self.lang),
                tt("Please create or open a TIF project first.", self.lang),
            )
            return False
        return True

    def _select_specimen_after_import(self, specimen_id):
        self._select_volume_tree_item(specimen_id, "full")

    def _default_import_specimen_id(self, tif_path, used_ids=None):
        used = {str(value or "") for value in (used_ids or set())}
        used.update(
            str(specimen.get("specimen_id") or "")
            for specimen in (self.project.project_data.get("specimens", []) or [])
            if isinstance(specimen, dict)
        )
        base = os.path.splitext(os.path.basename(str(tif_path or "")))[0]
        clean = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in base).strip("._")
        clean = clean or "tif_specimen"
        candidate = clean
        suffix = 2
        while candidate in used:
            candidate = f"{clean}_{suffix}"
            suffix += 1
        used.add(candidate)
        return candidate

    def _set_tif_import_controls_enabled(self, enabled):
        for button in (self.btn_import_tif, self.btn_import_amira):
            button.setEnabled(bool(enabled))

    def _task_request_key(self, value):
        try:
            if isinstance(value, tuple):
                return repr(value)
            if isinstance(value, dict):
                return repr(sorted(value.items()))
            return str(value or "")
        except Exception:
            return str(id(value))

    def _current_task_context(self, *, request_key="", label_role=""):
        return self.task_adapter.context_from_widget(self, request_key=request_key, label_role=label_role)

    def _start_tif_task(self, task_type, *, action="", payload=None, request_key="", label_role="", message=""):
        return self.task_adapter.start_from_widget(
            self,
            task_type,
            action=action,
            payload=payload,
            request_key=request_key,
            label_role=label_role,
            message=message,
        )

    def _finish_tif_task(self, task_id, *, payload=None, message=""):
        return self.task_manager.finish_task(task_id, payload=payload, message=message)

    def _fail_tif_task(self, task_id, error="", *, payload=None, message=""):
        return self.task_manager.fail_task(task_id, error, payload=payload, message=message)

    def _progress_tif_task(self, task_id, current=0, total=0, message=""):
        return self.task_manager.progress_task(task_id, current=current, total=total, message=message)

    def _cancel_tif_task(self, task_id, reason=""):
        return self.task_manager.cancel_task(task_id, reason)

    def _task_context_matches_current(self, task_id, *, fields=None, request_key="", label_role="", ignore_empty=False):
        return self.task_adapter.current_context_matches(
            self,
            task_id,
            fields=fields,
            request_key=request_key,
            label_role=label_role,
            ignore_empty=ignore_empty,
        )

    def _current_state_summary(self):
        role = self.label_role_combo.currentData() if hasattr(self, "label_role_combo") else ""
        roll = (self.local_axis_draft or {}).get("roll_reference") if isinstance(self.local_axis_draft, dict) else {}
        preview_key = self._volume_preview_pending_key if self._volume_preview_pending_key is not None else self._volume_preview_pending_mask_key
        return {
            "selection": self.selection_controller.state.to_dict() if hasattr(self.selection_controller, "state") else {},
            "edit": TifEditState(
                dirty_slice_count=self.annotation_workflow_controller.dirty_slice_count() if hasattr(self, "_dirty_slice_count") else len(getattr(self, "_dirty_edit_slices", set()) or set()),
                auto_save_running=self.annotation_workflow_controller.auto_save_thread is not None,
                manual_save_running=self.annotation_workflow_controller.manual_save_thread is not None,
                role=role,
                scope=self.current_volume_scope,
            ).to_dict(),
            "preview": TifPreviewState(
                display_mode=self.display_mode,
                render_mode=self._volume_render_mode,
                preview_pending=self.volume_render_controller.preview_build_thread is not None,
                preview_token=self._volume_preview_pending_token,
                request_key=self._task_request_key(preview_key),
            ).to_dict(),
            "preview_resource": self.preview_controller.state_summary(),
            "backend": TifBackendState(
                running=self.backend_panel_controller.action_running(),
                action=self._tif_backend_action,
                run_dir=self._tif_backend_run_dir,
                result_json=self._tif_backend_result_json,
                progress_value=self._tif_backend_progress_value,
            ).to_dict(),
            "roi": TifRoiState(
                active_roi_id=self.active_part_roi_id,
                roi_keyframe_count=len(self.part_roi_keyframes or []),
                mask_keyframe_count=len(self.part_mask_keyframes or []),
                confirm_running=self.roi_workflow_controller.is_confirm_running(),
                mask_preview_running=self.part_mask_workflow_controller._part_mask_preview_running(),
            ).to_dict(),
            "local_axis": TifLocalAxisState(
                draft_active=isinstance(self.local_axis_draft, dict),
                export_running=self.local_axis_controller.export_running(),
                pick_target=str(getattr(self, "_local_axis_pick_target", "") or ""),
                specimen_id=str((self.local_axis_draft or {}).get("specimen_id") or "") if isinstance(self.local_axis_draft, dict) else "",
                part_id=str((self.local_axis_draft or {}).get("part_id") or "") if isinstance(self.local_axis_draft, dict) else "",
                reslice_id=self.current_reslice_id,
                roll_reference_keys=tuple(sorted((roll or {}).keys())) if isinstance(roll, dict) else (),
            ).to_dict(),
        }

    def _format_elapsed_seconds(self, seconds):
        seconds = max(0, int(seconds or 0))
        minutes, sec = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{sec:02d}"
        return f"{minutes:02d}:{sec:02d}"

    def _compact_path_for_side_panel(self, path, max_chars=72):
        text = str(path or "").strip()
        if not text or text == "-":
            return "-"
        max_chars = max(24, int(max_chars or 72))
        normalized = text.replace("\\", "/")
        if len(normalized) <= max_chars:
            return normalized
        parts = [part for part in normalized.split("/") if part]
        if len(parts) >= 2:
            compact = ".../" + "/".join(parts[-2:])
            if len(compact) <= max_chars:
                return compact
        if parts:
            leaf = parts[-1]
            if len(leaf) + 4 <= max_chars:
                return ".../" + leaf
        return "..." + normalized[-(max_chars - 3):]

    def _update_backend_elapsed_label(self):
        if not self.backend_panel_controller.action_running() or not self._tif_backend_started_mono:
            return
        elapsed = time.monotonic() - float(self._tif_backend_started_mono)
        self.backend_elapsed_label.setText(tt("Elapsed: {0}", self.lang).format(self._format_elapsed_seconds(elapsed)))

    def _set_backend_write_locked_controls(self, locked):
        locked = bool(locked)
        if not locked:
            return
        write_controls = (
            self.label_role_combo,
            self.btn_save_edit,
            self.btn_tool_brush,
            self.btn_tool_eraser,
            self.btn_tool_lasso,
            self.btn_tool_rectangle,
            self.btn_tool_ellipse,
            self.btn_interpolate_current_label,
            self.btn_copy_material_prev,
            self.btn_copy_material_next,
            self.btn_clear_current_material,
            self.btn_promote,
            self.btn_copy_draft,
            self.btn_export_training,
            self.btn_import_external_prediction_tif,
            self.btn_accept_selected_ai_results,
            self.auto_save_check,
            self.btn_add_material,
            self.btn_edit_material,
            self.btn_delete_material,
            self.part_bbox_edit,
            self.btn_part_draw_roi,
            self.btn_save_part_roi,
            self.btn_confirm_part_roi,
            self.btn_cancel_part_roi,
            self.btn_create_part,
            self.btn_add_rect_keyframe,
            self.btn_draw_part_contour,
            self.btn_delete_part_contour,
            self.btn_clear_part_keyframes,
            self.btn_prev_key_slice,
            self.btn_next_key_slice,
            self.btn_preview_part_mask,
            self.btn_accept_part_mask,
            self.btn_clear_part_preview,
            self.btn_copy_source_z_axis,
            self.btn_pick_roll_ref_a,
            self.btn_pick_roll_ref_b,
            self.btn_pick_roll_ref_c,
            self.btn_align_axis_to_reference_plane,
            self.btn_clear_roll_refs,
            self.btn_clear_local_axis_draft,
            self.btn_local_axis_reslice,
            self.local_axis_trainable_check,
            self.btn_export_local_axis_training_manifest,
            self.btn_export_part_package,
            self.btn_delete_part_volume,
            self.btn_import_tif,
            self.btn_import_amira,
        )
        for widget in write_controls:
            if widget is not None:
                widget.setEnabled(False)
        self.btn_tool_picker.setEnabled(False)
        self.btn_tool_pan.setEnabled(False)
        self.btn_undo.setEnabled(False)
        self.btn_redo.setEnabled(False)

    def _cleanup_tif_import_thread(self):
        self._set_tif_import_controls_enabled(True)
        if self._tif_import_progress is not None:
            self._tif_import_progress.close()
            self._tif_import_progress.deleteLater()
        self._tif_import_progress = None
        self._tif_import_worker = None
        self._tif_import_thread = None
        self._tif_import_specimen_id = ""
        self._tif_import_jobs = []
        self._tif_import_task_id = ""



    def _on_tif_import_progress(self, current, total, message):
        self._progress_tif_task(self._tif_import_task_id, current, total, str(message or ""))
        if self._tif_import_progress is None:
            return
        maximum = max(1, int(total or 100))
        value = max(0, min(maximum, int(current or 0)))
        self._tif_import_progress.setMaximum(maximum)
        self._tif_import_progress.setValue(value)
        self._tif_import_progress.setLabelText(tt(message, self.lang))

    def _on_tif_import_finished(self, result):
        task_id = self._tif_import_task_id
        task_current = self._task_context_matches_current(
            task_id,
            fields=("specimen_id", "volume_scope", "part_id", "reslice_id"),
        )
        batch_results = result.get("results") if isinstance(result, dict) else None
        if isinstance(batch_results, list):
            successes = [item for item in batch_results if item.get("ok")]
            failures = [item for item in batch_results if not item.get("ok")]
            first_id = successes[0].get("specimen_id", "") if successes else ""
            self.refresh_project(reload_current=False)
            if first_id and task_current:
                self._select_specimen_after_import(first_id)
            message = tt("Imported {0}/{1} TIF stack(s).", self.lang).format(len(successes), len(batch_results))
            if failures:
                message = f"{message} {tt('Failed', self.lang)}: {len(failures)}"
            if not task_current:
                message = f"{message} {tt('Current view was left unchanged because you switched context while it was running.', self.lang)}"
            else:
                self.training_status_label.setText(message)
            self.log(message)
            for item in failures:
                self.log(f"TIF import failed [{item.get('specimen_id', '')}]: {item.get('error', '')}")
            thread = self._tif_import_thread
            self._finish_tif_task(task_id, payload=result if isinstance(result, dict) else {}, message=message)
            self._cleanup_tif_import_thread()
            if thread is not None:
                thread.quit()
            if failures:
                details = "\n".join(f"{item.get('specimen_id', '')}: {item.get('error', '')}" for item in failures[:8])
                QMessageBox.warning(self, tt("Import TIF Stack", self.lang), f"{message}\n{details}")
            return

        specimen_id = self._tif_import_specimen_id
        self.refresh_project(reload_current=False)
        if task_current:
            self._select_specimen_after_import(specimen_id)
        report_path = result.get("report_path", "") if isinstance(result, dict) else ""
        message = tt("Imported TIF stack for specimen {0}. Report: {1}", self.lang).format(specimen_id, report_path)
        if not task_current:
            message = f"{message} {tt('Current view was left unchanged because you switched context while it was running.', self.lang)}"
        else:
            self.training_status_label.setText(message)
        self.log(message)
        thread = self._tif_import_thread
        self._finish_tif_task(task_id, payload=result if isinstance(result, dict) else {}, message=message)
        self._cleanup_tif_import_thread()
        if thread is not None:
            thread.quit()

    def _on_tif_import_failed(self, message):
        thread = self._tif_import_thread
        self._fail_tif_task(self._tif_import_task_id, str(message or ""), message=str(message or ""))
        self._cleanup_tif_import_thread()
        if thread is not None:
            thread.quit()
        QMessageBox.critical(self, tt("Import TIF Stack", self.lang), message)

    def _is_metadata_only_specimen(self, specimen=None):
        specimen = specimen if specimen is not None else self.project.get_specimen(self.current_specimen_id, default=None)
        if specimen is None:
            return False
        return (specimen.get("metadata") or {}).get("import_status") == "metadata_only" or ((specimen.get("working_volume") or {}).get("status") == "metadata_only")

    def _slice_unavailable_message(self, specimen=None):
        override = str(getattr(self, "_slice_unavailable_override", "") or "").strip()
        if override:
            return override
        specimen = specimen if specimen is not None else self.project.get_specimen(self.current_specimen_id, default=None)
        specimen_id = str((specimen or {}).get("specimen_id") or self.current_specimen_id or "")
        if not specimen_id and not self.specimen_list.count():
            return tt("No specimens in this TIF project", self.lang)
        if self.part_mask_workflow_controller._materialize_task_matches(specimen_id):
            return tt("Working volume is being built. Slice review will be available when it finishes.", self.lang)
        if self._is_metadata_only_specimen(specimen):
            return tt("TIF metadata registered. Build a working volume before slice review.", self.lang)
        return tt("Working volume missing", self.lang)

    def _volume_unavailable_message(self, specimen=None):
        override = str(getattr(self, "_slice_unavailable_override", "") or "").strip()
        if override:
            return override
        specimen = specimen if specimen is not None else self.project.get_specimen(self.current_specimen_id, default=None)
        specimen_id = str((specimen or {}).get("specimen_id") or self.current_specimen_id or "")
        if self.part_mask_workflow_controller._materialize_task_matches(specimen_id):
            return tt("Working volume is being built. 3D preview will open when it finishes.", self.lang)
        if self._is_metadata_only_specimen(specimen):
            return tt("TIF metadata registered. Build a working volume before 3D preview.", self.lang)
        return tt("No TIF volume loaded", self.lang)

    def _set_slice_review_available(self, available):
        available = bool(available)
        if hasattr(self, "slice_slider"):
            self.slice_slider.setEnabled(available)
        if hasattr(self, "slice_axis_combo"):
            self.slice_axis_combo.setEnabled(available)

    def _set_slice_review_unavailable(self, message=""):
        self._set_slice_review_available(False)
        if hasattr(self, "slice_slider"):
            self.slice_slider.blockSignals(True)
            self.slice_slider.setRange(0, 0)
            self.slice_slider.setValue(0)
            self.slice_slider.blockSignals(False)
        if hasattr(self, "slice_label"):
            self.slice_label.setText("0 / 0")
        self.canvas.reset_view()
        self.canvas.setText(str(message or self._slice_unavailable_message()))

    def _show_volume_selection_loading_feedback(self, payload=None, flush_events=True):
        payload = payload if isinstance(payload, dict) else {}
        scope = str(payload.get("scope") or "full")
        if scope == "part_reslice":
            message_key = "Loading selected reslice and labels..."
        elif scope in {"part", "part_reslices"}:
            message_key = "Loading selected part volume and labels..."
        else:
            message_key = "Loading selected TIF volume and labels..."
        message = tt(message_key, self.lang)
        self._set_operation_feedback(message, log=False)
        if hasattr(self, "canvas"):
            self.canvas.setText(message)
        if hasattr(self, "status_label"):
            self.status_label.setText(message)
        cursor_set = False
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            cursor_set = True
            if flush_events:
                QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)
            return True
        except Exception:
            if cursor_set:
                try:
                    QApplication.restoreOverrideCursor()
                except Exception:
                    pass
            return False

    def _finish_volume_selection_loading_feedback(self, payload=None):
        payload = payload if isinstance(payload, dict) else {}
        scope = str(payload.get("scope") or "full")
        if scope == "part_reslice":
            message_key = "Loaded selected reslice and labels."
        elif scope in {"part", "part_reslices"}:
            message_key = "Loaded selected part volume and labels."
        else:
            message_key = "Loaded selected TIF volume and labels."
        self._set_operation_feedback(tt(message_key, self.lang), log=False)

    def import_tif_stack_dialog(self):
        if not self.coordinator.guard_backend_write_lock():
            return
        if not self._ensure_tif_project_open():
            return
        if self._tif_import_thread is not None:
            QMessageBox.information(
                self,
                tt("Import TIF Stack", self.lang),
                tt("TIF import is already running.", self.lang),
            )
            return
        tif_paths, _ = QFileDialog.getOpenFileNames(
            self,
            tt("Import TIF Stack", self.lang),
            "",
            "TIF/TIFF (*.tif *.tiff)",
        )
        if not tif_paths:
            return
        tif_paths = [str(path) for path in tif_paths if str(path or "").strip()]
        if not tif_paths:
            return
        jobs = []
        used_ids = set()
        if len(tif_paths) == 1:
            tif_path = tif_paths[0]
            default_id = self._default_import_specimen_id(tif_path, used_ids)
            specimen_id, ok = QInputDialog.getText(
                self,
                tt("Import TIF Stack", self.lang),
                tt("Specimen ID:", self.lang),
                text=default_id,
            )
            if not ok or not specimen_id:
                return
            jobs.append({"tif_path": tif_path, "specimen_id": str(specimen_id)})
        else:
            for tif_path in tif_paths:
                specimen_id = self._default_import_specimen_id(tif_path, used_ids)
                used_ids.add(specimen_id)
                jobs.append({"tif_path": tif_path, "specimen_id": specimen_id})
        self._set_tif_import_controls_enabled(False)
        self._tif_import_jobs = jobs
        self._tif_import_specimen_id = jobs[0]["specimen_id"] if jobs else ""
        task = self._start_tif_task(
            "tif_import",
            action="import_tif_stack",
            payload={"jobs": [dict(job) for job in jobs]},
            request_key=self._tif_import_specimen_id,
            message=tt("Importing TIF stack...", self.lang),
        )
        self._tif_import_task_id = task.task_id
        self._tif_import_progress = QProgressDialog(
            tt("Importing TIF stack...", self.lang) if len(jobs) == 1 else tt("Importing TIF stack batch...", self.lang),
            "",
            0,
            max(100, len(jobs) * 100),
            self,
        )
        self._tif_import_progress.setWindowTitle(tt("Import TIF Stack", self.lang))
        self._tif_import_progress.setCancelButton(None)
        self._tif_import_progress.setAutoClose(False)
        self._tif_import_progress.setAutoReset(False)
        self._tif_import_progress.setWindowModality(Qt.WindowModal)
        self._tif_import_progress.show()

        self._tif_import_thread = QThread(self)
        if len(jobs) == 1:
            self._tif_import_worker = TifImportWorker(self.project, jobs[0]["tif_path"], jobs[0]["specimen_id"])
        else:
            self._tif_import_worker = TifBatchImportWorker(self.project, jobs)
        self._tif_import_worker.moveToThread(self._tif_import_thread)
        self._tif_import_thread.started.connect(self._tif_import_worker.run)
        self._tif_import_worker.progress.connect(self._on_tif_import_progress)
        self._tif_import_worker.finished.connect(self._on_tif_import_finished)
        if hasattr(self._tif_import_worker, "failed"):
            self._tif_import_worker.failed.connect(self._on_tif_import_failed)
        self._tif_import_worker.finished.connect(self._tif_import_thread.quit)
        if hasattr(self._tif_import_worker, "failed"):
            self._tif_import_worker.failed.connect(self._tif_import_thread.quit)
        self._tif_import_thread.finished.connect(self._tif_import_worker.deleteLater)
        self._tif_import_thread.finished.connect(self._tif_import_thread.deleteLater)
        self._tif_import_thread.start()

    def import_amira_directory_dialog(self):
        if not self.coordinator.guard_backend_write_lock():
            return
        if not self._ensure_tif_project_open():
            return
        source_dir = QFileDialog.getExistingDirectory(self, tt("Import AMIRA Directory", self.lang), self.project.project_dir)
        if not source_dir:
            return
        default_id = os.path.basename(os.path.normpath(source_dir))
        specimen_id, ok = QInputDialog.getText(
            self,
            tt("Import AMIRA Directory", self.lang),
            tt("Specimen ID:", self.lang),
            text=default_id,
        )
        if not ok or not specimen_id:
            return
        task = self._start_tif_task(
            "amira_import",
            action="import_amira_directory",
            payload={"source_dir": str(source_dir), "specimen_id": str(specimen_id)},
            request_key=str(specimen_id),
            message=tt("Importing AMIRA directory...", self.lang),
        )
        try:
            result = import_amira_directory(self.project, source_dir, specimen_id)
        except Exception as exc:
            self._fail_tif_task(task.task_id, str(exc), message=str(exc))
            QMessageBox.critical(self, tt("Import AMIRA Directory", self.lang), str(exc))
            return
        self._finish_tif_task(task.task_id, payload=result if isinstance(result, dict) else {}, message="amira_import_finished")
        self.refresh_project()
        self._select_specimen_after_import(specimen_id)
        report_path = result.get("report_path", "")
        message = tt("Imported AMIRA directory for specimen {0}. Report: {1}", self.lang).format(specimen_id, report_path)
        self.training_status_label.setText(message)
        self.log(message)

    def _bbox_text(self, bbox):
        if not bbox or len(bbox) != 3:
            return ""
        return ",".join(str(int(value)) for pair in bbox for value in pair)

    def _roi_keyframe_metadata(self):
        keyframes = self.roi_workflow_controller.normalize_keyframes(self.roi_workflow_controller.state.keyframes)
        axes = sorted({item["axis"] for item in keyframes})
        mask_keyframes = self.part_mask_workflow_controller._normalize_full_volume_mask_keyframes(self.part_mask_keyframes)
        mask_bbox = self._full_volume_contour_bbox({"keyframes": mask_keyframes}) if mask_keyframes else []
        return {
            "roi_shell_mode": "key_slice_rectangles" if keyframes else "bbox",
            "roi_keyframes": keyframes,
            "roi_axis": axes[0] if len(axes) == 1 else "",
            "part_mask_mode": "freehand_key_slices" if mask_keyframes else "",
            "part_mask_axis": "z" if mask_keyframes else "",
            "part_mask_keyframes": mask_keyframes,
            "part_mask_bbox_zyx": mask_bbox,
        }

    def _roi_shell_mask_from_keyframes(self, keyframes, parent_bbox):
        keyframes = self.roi_workflow_controller.normalize_keyframes(keyframes)
        axes = sorted({item["axis"] for item in keyframes})
        if len(axes) != 1:
            return None
        axis = axes[0]
        bbox = self._clip_bbox_to_shape(parent_bbox, self.image_volume.shape)
        shape = tuple(int(pair[1]) - int(pair[0]) for pair in bbox)
        if len(shape) != 3 or min(shape) <= 0:
            return None
        local_frames = []
        for item in keyframes:
            if item["axis"] != axis:
                continue
            slice_index = int(item["slice_index"])
            x0, y0, x1, y1 = [int(value) for value in item["rect"]]
            if axis == "z":
                local_slice = slice_index - int(bbox[0][0])
                rect = [x0 - int(bbox[2][0]), y0 - int(bbox[1][0]), x1 - int(bbox[2][0]), y1 - int(bbox[1][0])]
                slice_count, height, width = shape[0], shape[1], shape[2]
            elif axis == "y":
                local_slice = slice_index - int(bbox[1][0])
                rect = [x0 - int(bbox[2][0]), y0 - int(bbox[0][0]), x1 - int(bbox[2][0]), y1 - int(bbox[0][0])]
                slice_count, height, width = shape[1], shape[0], shape[2]
            else:
                local_slice = slice_index - int(bbox[2][0])
                rect = [x0 - int(bbox[1][0]), y0 - int(bbox[0][0]), x1 - int(bbox[1][0]), y1 - int(bbox[0][0])]
                slice_count, height, width = shape[2], shape[0], shape[1]
            if not (0 <= local_slice < slice_count):
                continue
            rect[0] = max(0, min(width, rect[0]))
            rect[2] = max(0, min(width, rect[2]))
            rect[1] = max(0, min(height, rect[1]))
            rect[3] = max(0, min(height, rect[3]))
            if rect[2] <= rect[0] or rect[3] <= rect[1]:
                continue
            local_frames.append((int(local_slice), rect))
        if not local_frames:
            return None
        local_frames.sort(key=lambda item: item[0])
        mask = np.zeros(shape, dtype=np.uint16)

        def fill_slice(slice_index, rect_values):
            x0, y0, x1, y1 = [int(value) for value in rect_values]
            if x1 <= x0 or y1 <= y0:
                return
            if axis == "z":
                mask[int(slice_index), y0:y1, x0:x1] = 1
            elif axis == "y":
                mask[y0:y1, int(slice_index), x0:x1] = 1
            else:
                mask[y0:y1, x0:x1, int(slice_index)] = 1

        for idx, (slice_index, rect) in enumerate(local_frames):
            fill_slice(slice_index, rect)
            if idx + 1 >= len(local_frames):
                continue
            next_slice, next_rect = local_frames[idx + 1]
            span = int(next_slice) - int(slice_index)
            if span <= 0:
                continue
            for step in range(1, span):
                weight = float(step) / float(span)
                interp = []
                for left_value, right_value in zip(rect, next_rect):
                    interp.append(int(round((1.0 - weight) * float(left_value) + weight * float(right_value))))
                fill_slice(int(slice_index) + step, interp)
        return mask

    def is_part_roi_draw_mode(self):
        return self.roi_workflow_controller.is_draw_mode()

    def current_roi_overlay_rects(self):
        return self.roi_workflow_controller.current_overlay_rects()

    def _bbox_projection_for_current_slice(self, bbox):
        if not bbox or len(bbox) != 3:
            return None
        axis, index = self._active_slice_position()
        z_range, y_range, x_range = bbox
        if axis == "z":
            if not (int(z_range[0]) <= int(index) < int(z_range[1])):
                return None
            return [x_range[0], y_range[0], x_range[1], y_range[1]]
        if axis == "y":
            if not (int(y_range[0]) <= int(index) < int(y_range[1])):
                return None
            return [x_range[0], z_range[0], x_range[1], z_range[1]]
        if axis == "x":
            if not (int(x_range[0]) <= int(index) < int(x_range[1])):
                return None
            return [y_range[0], z_range[0], y_range[1], z_range[1]]
        return None

    def _expanded_axis_range(self, existing_range, index, size):
        try:
            start, end = int(existing_range[0]), int(existing_range[1])
        except Exception:
            start, end = index, index + 1
        if end <= start:
            start, end = index, index + 1
        return [max(0, min(start, index)), min(int(size), max(end, index + 1))]

    def _union_axis_range(self, existing_range, start_value, end_value, size):
        start_value = max(0, min(int(size), int(start_value)))
        end_value = max(0, min(int(size), int(end_value)))
        if end_value < start_value:
            start_value, end_value = end_value, start_value
        if end_value <= start_value:
            end_value = min(int(size), start_value + 1)
            start_value = max(0, end_value - 1)
        try:
            start, end = int(existing_range[0]), int(existing_range[1])
        except Exception:
            start, end = start_value, end_value
        if end <= start:
            start, end = start_value, end_value
        return [max(0, min(start, start_value)), min(int(size), max(end, end_value))]

    def _accepted_full_volume_preview_mask_for_request(self, bbox):
        if (
            self.part_mask_preview_accepted
            and self.part_preview_mask is not None
            and self.part_mask_workflow_controller.state.preview_bbox == bbox
        ):
            shape = _tif_bbox_shape(bbox)
            if tuple(getattr(self.part_preview_mask, "shape", ()) or ()) == tuple(shape):
                return self.part_preview_mask
        return None

    def _confirm_part_roi_request_sync(self, request):
        part = crop_volume_to_part(
            self.project,
            request.get("specimen_id", ""),
            request.get("part_id", ""),
            request.get("bbox_zyx", []),
            display_name=request.get("display_name") or request.get("part_id", ""),
        )
        mask_initialized = False
        mask_message = ""
        mask_bbox = request.get("mask_bbox_zyx") or []
        roi_keyframes = request.get("roi_keyframes") or []
        if mask_bbox:
            mask_initialized, mask_message = _tif_initialize_part_mask_from_full_volume_contours(
                self.project,
                request.get("specimen_id", ""),
                part,
                request.get("mask_contours") or {},
                request.get("bbox_zyx", []),
                request.get("source_shape_zyx") or [],
                accepted_preview_mask=request.get("accepted_preview_mask"),
            )
            if mask_initialized:
                part.setdefault("view_settings", {})["volume_mask_mode"] = "masked_image"
                self.project.save_project()
        elif roi_keyframes:
            mask_initialized, mask_message = _tif_initialize_part_mask_from_roi_shell(
                self.project,
                request.get("specimen_id", ""),
                part,
                roi_keyframes,
                request.get("source_shape_zyx") or [],
            )
            if mask_initialized:
                part.setdefault("view_settings", {})["volume_mask_mode"] = "masked_image"
                self.project.save_project()
        roi_id = str(request.get("roi_id") or "")
        if roi_id:
            self.project.update_part_roi(
                request.get("specimen_id", ""),
                roi_id,
                bbox_zyx=request.get("bbox_zyx", []),
                status="part_created",
                linked_part_id=part.get("part_id", ""),
                metadata=request.get("roi_metadata") or {},
                save=True,
            )
        else:
            self.roi_workflow_controller.ensure_roi_for_created_part(part, request.get("bbox_zyx", []), display_name=request.get("display_name") or request.get("part_id", ""), specimen_id=request.get("specimen_id", ""))
        return {
            "part": part,
            "part_id": part.get("part_id", request.get("part_id", "")),
            "specimen_id": request.get("specimen_id", ""),
            "bbox_zyx": request.get("bbox_zyx", []),
            "mask_bbox_zyx": mask_bbox,
            "mask_initialized": bool(mask_initialized),
            "mask_message": str(mask_message or ""),
            "mask_keyframe_count": len(((request.get("mask_contours") or {}).get("keyframes") or [])),
            "roi_keyframe_count": len(roi_keyframes),
        }

    def _initialize_part_mask_from_roi_shell(self, part, roi_keyframes):
        if not isinstance(part, dict) or not roi_keyframes:
            return False, ""
        if self.image_volume is None:
            return False, ""
        try:
            initialized, message = _tif_initialize_part_mask_from_roi_shell(
                self.project,
                self.current_specimen_id,
                part,
                roi_keyframes,
                self.image_volume.shape,
            )
            return initialized, tt(message, self.lang)
        except Exception as exc:
            self.log(f"Failed to initialize ROI shell mask: {exc}")
            return False, str(exc)

    def _initialize_part_mask_from_full_volume_contours(self, part, contours, bbox):
        if not isinstance(part, dict) or not isinstance(contours, dict):
            return False, ""
        try:
            accepted_preview_mask = None
            if (
                self.part_mask_preview_accepted
                and self.part_preview_mask is not None
                and self.part_mask_workflow_controller.state.preview_bbox == bbox
            ):
                accepted_preview_mask = self.part_preview_mask
            initialized, message = _tif_initialize_part_mask_from_full_volume_contours(
                self.project,
                self.current_specimen_id,
                part,
                contours,
                bbox,
                self.image_volume.shape,
                accepted_preview_mask=accepted_preview_mask,
            )
            return initialized, tt(message, self.lang)
        except Exception as exc:
            self.log(f"Failed to initialize part mask from full-volume contours: {exc}")
            return False, str(exc)

    def delete_current_part_volume(self):
        if not self.coordinator.guard_backend_write_lock():
            return
        if not self._is_editable_part_volume() or not self.current_specimen_id or not self.current_part_id:
            QMessageBox.information(self, tt("Part extraction", self.lang), tt("Select a part volume before exporting a part package.", self.lang))
            return
        self.delete_part_volume(self.current_specimen_id, self.current_part_id)

    def release_loaded_volume_arrays(self, defer=False):
        arrays = (
            self.image_volume,
            self.label_volume,
            self.edit_volume,
            self.part_mask_workflow_controller.state.part_mask_volume,
        )
        released = set()
        unique_arrays = []
        for array in arrays:
            if array is None or id(array) in released:
                continue
            released.add(id(array))
            unique_arrays.append(array)
        self.image_volume = None
        self.label_volume = None
        self.edit_volume = None
        self.part_mask_workflow_controller.state.part_mask_volume = None
        preview_thread = self.volume_render_controller.preview_build_thread if defer else None
        return self.project_lifecycle_controller.release_volume_arrays(
            unique_arrays,
            preview_thread=preview_thread,
            defer=defer,
        )

    def delete_part_volume(self, specimen_id, part_id):
        if not self.coordinator.guard_backend_write_lock():
            return False
        specimen_id = str(specimen_id or "").strip()
        part_id = str(part_id or "").strip()
        if not specimen_id or not part_id:
            return False
        part = self.project.get_part(specimen_id, part_id, default=None)
        if part is None:
            return False
        display_name = part.get("display_name") or part.get("part_id") or part_id
        response = QMessageBox.question(
            self,
            tt("Delete part volume?", self.lang),
            tt(
                "Delete part volume {0}? This removes the cropped image, mask, contours, and extraction files, but keeps the parent TIF volume.",
                self.lang,
            ).format(display_name),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if response != QMessageBox.Yes:
            return False
        try:
            deleting_current = specimen_id == self.current_specimen_id and part_id == self.current_part_id
            if deleting_current:
                if not self.volume_render_controller._cancel_and_wait_volume_preview_build():
                    QMessageBox.information(
                        self,
                        tt("Volume render", self.lang),
                        tt("The 3D preview is still stopping. Wait a moment, then delete the part again.", self.lang),
                    )
                    return False
                self.release_loaded_volume_arrays()
                self.part_mask_workflow_controller.state.preview_mask = None
                self.volume_render_controller._clear_volume_preview_cache()
            else:
                self.volume_render_controller._cancel_volume_preview_build()
            result = self.project.discard_part(
                specimen_id,
                part_id,
                remove_storage=True,
                save=True,
                unlink_linked_rois=True,
            )
        except Exception as exc:
            QMessageBox.warning(self, tt("Part extraction", self.lang), str(exc))
            return False
        if specimen_id == self.current_specimen_id and part_id == self.current_part_id:
            self.part_mask_workflow_controller.state.preview_mask = None
            self.current_part = None
            self.current_part_id = ""
            self.current_volume_scope = "full"
            self.volume_render_controller._clear_volume_preview_cache()
        self.refresh_project()
        self._select_volume_tree_item(specimen_id, "full", "")
        message = tt("Deleted part volume {0}.", self.lang).format(display_name)
        if not result.get("removed_storage"):
            message = f"{message} Storage was already missing."
        if result.get("storage_cleanup_error"):
            message = f"{message} Pending-delete storage cleanup needs attention: {result.get('storage_cleanup_error')}"
        self.training_status_label.setText(message)
        self.log(f"{message} part_id={part_id}")
        return True

    def _clip_bbox_to_shape(self, bbox, shape):
        clean = []
        for axis, pair in enumerate(bbox):
            size = int(shape[axis])
            start = max(0, min(size, int(pair[0])))
            end = max(0, min(size, int(pair[1])))
            if end < start:
                start, end = end, start
            if end == start:
                end = min(size, start + 1)
                start = max(0, end - 1)
            clean.append([start, end])
        return clean

    def _current_part_bbox_for_action(self):
        bbox = self.roi_workflow_controller.parse_bbox_text()
        if not bbox and self.part_roi_keyframes:
            bbox = self.roi_workflow_controller.keyframe_bbox(self.part_roi_keyframes)
        if not bbox and self.part_mask_keyframes:
            bbox = self._full_volume_contour_bbox()
        if not bbox:
            raise ValueError(tt("Draw an ROI or contour before saving or creating a part.", self.lang))
        return self._clip_bbox_to_shape(bbox, self.image_volume.shape)

    def create_part_from_bbox_dialog(self):
        if not self.coordinator.guard_backend_write_lock():
            return
        if self.current_volume_scope != "full" or not self.current_specimen_id or self.image_volume is None:
            QMessageBox.information(self, tt("Part extraction", self.lang), tt("Switch to Full volume before creating a part.", self.lang))
            return
        default_part_id = f"part_{len(self.project.list_parts(self.current_specimen_id)) + 1}"
        dialog = TifPartNameDialog(
            "Create part",
            part_id=default_part_id,
            display_name=default_part_id,
            parent=self,
            lang=self.lang,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        part_id, display_name = dialog.values()
        if not part_id:
            return
        try:
            bbox = self._current_part_bbox_for_action()
            part = crop_volume_to_part(self.project, self.current_specimen_id, part_id, bbox, display_name=display_name or part_id)
            self.roi_workflow_controller.ensure_roi_for_created_part(part, bbox, display_name=display_name or part_id)
        except Exception as exc:
            QMessageBox.warning(self, tt("Part extraction", self.lang), str(exc))
            return
        self.roi_workflow_controller.reset_state()
        self.refresh_project()
        self._populate_volume_roi_source_combo()
        self._select_volume_tree_item(self.current_specimen_id, "part", part.get("part_id", ""))
        message = tt("Created part {0} from bbox {1}.", self.lang).format(part.get("display_name") or part.get("part_id"), part.get("parent_bbox_zyx"))
        self.training_status_label.setText(message)
        self.log(message)

    def _selected_part_refs_for_action(self, action):
        refs = []
        if action in {"prepare_dataset", "train"}:
            refs = self.backend_workflow_service.train_ready_part_refs()
            if not refs:
                raise ValueError(
                    self.backend_panel_controller._training_selection_error(
                        prefer_part=(self.current_volume_scope == "part")
                    )
                )
            return refs
        self.backend_panel_controller.sync_predict_selection_from_table()
        for key in sorted(self._tif_predict_selected_refs):
            ref = self.backend_panel_controller.predict_ref_from_key(key)
            if ref["specimen_id"] and ref["part_id"]:
                readiness = self.project.evaluate_part_predict_ready(ref["specimen_id"], ref["part_id"], ref.get("reslice_id", ""))
                if not readiness.get("predict_ready"):
                    raise ValueError(tt("Selected prediction target is incomplete: {0}", self.lang).format(", ".join(readiness.get("reasons") or [])))
                ref["reslice_id"] = readiness.get("reslice_id", ref.get("reslice_id", ""))
                refs.append(ref)
        if not refs:
            raise ValueError(tt("Select at least one prediction target.", self.lang))
        return refs





    def _make_panel(self, title, object_name):
        if not hasattr(self, "_panel_title_labels"):
            self._panel_title_labels = {}
        return make_panel(title, object_name, self._panel_title_labels)

    def _make_section(self, title, object_name):
        if not hasattr(self, "_section_title_labels"):
            self._section_title_labels = {}
        return make_section(title, object_name, self._section_title_labels)

    def _make_right_sidebar_responsive(self, right_panel):
        make_right_sidebar_responsive(
            right_panel,
            (
            self.part_task_page,
            self.display_task_page,
            self.annotation_task_page,
            self.training_task_page,
            self.result_compare_page,
            ),
        )

    def _apply_soft_style(self):
        self.setStyleSheet(build_tif_workbench_stylesheet(self.current_theme))

    def set_theme(self, theme):
        self.current_theme = normalize_theme(theme)
        self._apply_soft_style()
        for canvas in (getattr(self, "canvas", None), getattr(self, "volume_canvas", None)):
            setter = getattr(canvas, "set_theme", None)
            if callable(setter):
                setter(self.current_theme)
        self.volume_render_controller._update_volume_render_status_label()
        if hasattr(self, "view_stack"):
            self.view_stack.update()

    def set_project_manager(self, project_manager):
        if not self.annotation_workflow_controller.confirm_discard_or_save():
            return
        if not self.close_project(prompt_unsaved=False):
            return
        self.project = project_manager
        self.refresh_project()

    def set_config_manager(self, config_manager):
        self.config_manager = config_manager
        config = self.config_manager.get("tif_backend", DEFAULT_TIF_BACKEND_CONFIG) if self.config_manager is not None else DEFAULT_TIF_BACKEND_CONFIG
        self.backend_config = sanitize_tif_backend_config(config)
        self._load_backend_config_into_ui()

    def _handle_slice_shortcut_key(self, key):
        if self.display_mode == "slice":
            if key == Qt.Key_Left:
                self.move_slice(-1)
                return True
            if key == Qt.Key_Right:
                self.move_slice(1)
                return True
            if key == Qt.Key_Up:
                self.canvas.zoom_in()
                return True
            if key == Qt.Key_Down:
                self.canvas.zoom_out()
                return True
        return False

    def keyPressEvent(self, event):
        if self._handle_slice_shortcut_key(event.key()):
            event.accept()
            return
        super().keyPressEvent(event)

    def close_project(self, prompt_unsaved=True):
        return self.project_lifecycle_controller.close_project(prompt_unsaved=prompt_unsaved)

    def prepare_for_agent_panel(self):
        if hasattr(self, "volume_still_timer"):
            self.volume_still_timer.stop()
        if self.display_mode != "volume":
            self._reset_volume_canvas_placeholder_for_agent()
            return
        self.on_display_mode_changed("slice")
        self._reset_volume_canvas_placeholder_for_agent()

    def _current_slice_axis(self):
        axis = self.slice_axis_combo.currentData() if hasattr(self, "slice_axis_combo") else self.slice_axis
        return axis if axis in {"z", "y", "x"} else "z"

    def _slice_count_for_axis(self, axis=None):
        if self.image_volume is None:
            return 1
        axis = axis or self._current_slice_axis()
        dim = {"z": 0, "y": 1, "x": 2}.get(axis, 0)
        return max(1, int(self.image_volume.shape[dim]))

    def _configure_slice_slider_for_axis(self, axis=None, preserve_position=True):
        axis = axis or self._current_slice_axis()
        count = self._slice_count_for_axis(axis)
        position = int(self._slice_positions.get(axis, 0)) if preserve_position else 0
        position = max(0, min(count - 1, position))
        self._set_slice_review_available(self.image_volume is not None)
        self.slice_slider.blockSignals(True)
        self.slice_slider.setRange(0, count - 1)
        self.slice_slider.setValue(position)
        self.slice_slider.blockSignals(False)
        self._slice_positions[axis] = position
        self.slice_label.setText(f"{position + 1} / {count}")

    def _active_slice_position(self):
        axis = self._current_slice_axis()
        count = self._slice_count_for_axis(axis)
        index = max(0, min(int(self.slice_slider.value()), count - 1))
        self._slice_positions[axis] = index
        return axis, index

    def closeEvent(self, event):
        if not self.close_project(prompt_unsaved=True):
            event.ignore()
            return
        self.workbench_shell.shutdown()
        self.volume_render_controller.release_volume_renderer()
        super().closeEvent(event)

    def refresh_project(self, reload_current=True):
        previous_id = self.current_specimen_id
        previous_scope = self.current_volume_scope
        previous_part_id = self.current_part_id
        previous_reslice_id = self.current_reslice_id
        self.specimen_list.blockSignals(True)
        self.specimen_list.clear()
        for specimen in self.project.project_data.get("specimens", []):
            specimen_id = specimen.get("specimen_id", "")
            parent = QTreeWidgetItem([self._format_specimen_label(specimen)])
            parent.setData(0, Qt.UserRole, {"scope": "full", "specimen_id": specimen_id, "part_id": ""})
            parent.setExpanded(True)

            full_item = QTreeWidgetItem([tt("Full volume", self.lang)])
            full_item.setData(0, Qt.UserRole, {"scope": "full", "specimen_id": specimen_id, "part_id": ""})
            parent.addChild(full_item)

            for part in specimen.get("parts", []) or []:
                label = self._format_part_label(part)
                part_item = QTreeWidgetItem([label])
                part_item.setData(
                    0,
                    Qt.UserRole,
                    {"scope": "part", "specimen_id": specimen_id, "part_id": part.get("part_id", "")},
                )
                reslices = ((part.get("metadata") or {}).get("local_axis_reslices", []) or [])
                if reslices:
                    reslices_item = QTreeWidgetItem([tt("Reslices", self.lang)])
                    reslices_item.setData(
                        0,
                        Qt.UserRole,
                        {"scope": "part_reslices", "specimen_id": specimen_id, "part_id": part.get("part_id", "")},
                    )
                    part_item.addChild(reslices_item)
                    for reslice in reslices:
                        reslice_item = QTreeWidgetItem([self._format_reslice_label(reslice)])
                        reslice_item.setData(
                            0,
                            Qt.UserRole,
                            {
                                "scope": "part_reslice",
                                "specimen_id": specimen_id,
                                "part_id": part.get("part_id", ""),
                                "reslice_id": reslice.get("reslice_id", ""),
                            },
                        )
                        reslices_item.addChild(reslice_item)
                    part_item.setExpanded(True)
                parent.addChild(part_item)
            self.specimen_list.addTopLevelItem(parent)
        self.specimen_list.blockSignals(False)
        self._populate_volume_roi_source_combo()
        if self.specimen_list.count():
            target_scope = "part_reslice" if previous_scope == "part" and previous_reslice_id else previous_scope
            if reload_current:
                selected = self._select_volume_tree_item(previous_id, target_scope, previous_part_id, previous_reslice_id)
            else:
                signals_were_blocked = self.specimen_list.blockSignals(True)
                try:
                    selected = self._select_volume_tree_item(previous_id, target_scope, previous_part_id, previous_reslice_id)
                finally:
                    self.specimen_list.blockSignals(signals_were_blocked)
            if not selected and (reload_current or previous_id):
                self._select_volume_tree_item("", "full", "")
        else:
            self.current_specimen_id = ""
            self.current_volume_scope = "full"
            self.current_part_id = ""
            self.current_part = None
            self.current_reslice_id = ""
            self.canvas.setText(tt("No specimens in this TIF project", self.lang))
            self.status_label.setText("")
            self.metadata_label.setText("")
        self._populate_label_schema_combo()
        self._populate_part_user_tag_table()
        self.backend_panel_controller.populate_model_library_combo()
        self.part_mask_workflow_controller._sync_material_colors_from_active_source()
        self.backend_panel_controller.refresh_predict_targets()
        self.result_review_controller.refresh_result_comparison_if_visible()

    def _format_specimen_label(self, specimen):
        status = specimen.get("review_status", "not_started")
        train = tt("train-ready", self.lang) if specimen.get("train_ready") else tt("not train-ready", self.lang)
        return f"{specimen.get('display_name') or specimen.get('specimen_id')} ({status}, {train})"

    def _format_part_label(self, part):
        status = str((part or {}).get("status", "draft") or "draft")
        name = str((part or {}).get("display_name") or (part or {}).get("part_id") or tt("Part volume", self.lang))
        training = (part or {}).get("training") or {}
        system_status = str(training.get("system_status") or (part or {}).get("system_status") or status)
        tag_lookup = self._part_user_tag_lookup()
        tag_labels = [tag_lookup.get(str(tag_id), str(tag_id)) for tag_id in (part or {}).get("user_tags", []) if str(tag_id or "")]
        suffix = f" | {', '.join(tag_labels)}" if tag_labels else ""
        return f"{name} ({system_status}){suffix}"

    def _format_reslice_label(self, reslice):
        name = str((reslice or {}).get("display_name") or (reslice or {}).get("reslice_id") or "reslice")
        status = str((reslice or {}).get("status") or "exported")
        return f"{name} ({status})"

    def _tree_item_payload(self, item):
        payload = item.data(0, Qt.UserRole) if item is not None else {}
        if isinstance(payload, dict):
            return {
                "scope": payload.get("scope", "full"),
                "specimen_id": payload.get("specimen_id", ""),
                "part_id": payload.get("part_id", ""),
                "reslice_id": payload.get("reslice_id", ""),
            }
        return {"scope": "full", "specimen_id": str(payload or ""), "part_id": "", "reslice_id": ""}

    def _on_specimen_tree_context_menu(self, position):
        item = self.specimen_list.itemAt(position)
        payload = self._tree_item_payload(item)
        if payload.get("scope") not in {"part", "part_reslices", "part_reslice"}:
            return
        specimen_id = str(payload.get("specimen_id") or "")
        part_id = str(payload.get("part_id") or "")
        if not specimen_id or not part_id:
            return
        menu = QMenu(self)
        delete_action = menu.addAction(tt("Delete part volume", self.lang))
        action = menu.exec(self.specimen_list.viewport().mapToGlobal(position))
        if action is delete_action:
            self.delete_part_volume(specimen_id, part_id)

    def _select_volume_tree_item(self, specimen_id="", scope="full", part_id="", reslice_id=""):
        target_specimen = str(specimen_id or "").strip()
        target_scope = "part_reslice" if scope == "part_reslice" else ("part" if scope in {"part", "part_reslices"} else "full")
        target_part = str(part_id or "").strip()
        target_reslice = str(reslice_id or "").strip()
        fallback = None

        def select_item(item):
            self._programmatic_volume_tree_select = True
            try:
                self.specimen_list.setCurrentItem(item)
            finally:
                self._programmatic_volume_tree_select = False

        for row in range(self.specimen_list.topLevelItemCount()):
            parent = self.specimen_list.topLevelItem(row)
            if parent is None:
                continue
            parent_payload = self._tree_item_payload(parent)
            if fallback is None:
                fallback = parent.child(0) or parent
            if target_specimen and parent_payload.get("specimen_id") != target_specimen:
                continue
            if target_scope == "full":
                select_item(parent.child(0) or parent)
                return True
            for child_index in range(parent.childCount()):
                child = parent.child(child_index)
                payload = self._tree_item_payload(child)
                if payload.get("scope") == "part" and payload.get("part_id") == target_part:
                    if target_scope == "part_reslice":
                        for group_index in range(child.childCount()):
                            group = child.child(group_index)
                            group_payload = self._tree_item_payload(group)
                            if group_payload.get("scope") == "part_reslices" and group.childCount():
                                if target_reslice:
                                    for reslice_index in range(group.childCount()):
                                        reslice_item = group.child(reslice_index)
                                        reslice_payload = self._tree_item_payload(reslice_item)
                                        if reslice_payload.get("reslice_id") == target_reslice:
                                            select_item(reslice_item)
                                            return True
                                    return False
                                select_item(group.child(0))
                                return True
                        if target_reslice:
                            return False
                    select_item(child)
                    return True
        if fallback is not None and not target_specimen:
            select_item(fallback)
            return True
        return False

    def load_specimen(self, specimen_id):
        if specimen_id != self.current_specimen_id and self.working_edit_dirty:
            if not self.annotation_workflow_controller.confirm_discard_or_save():
                return
        specimen = self.project.get_specimen(specimen_id, default=None)
        if specimen is None:
            return
        if specimen_id != self.current_specimen_id or self.current_volume_scope != "full":
            self.volume_render_controller._cancel_volume_preview_build()
        self._loading_specimen = True
        try:
            self.auto_save_timer.stop()
            self.current_specimen_id = specimen_id
            self.current_volume_scope = "full"
            self.current_part_id = ""
            self.current_part = None
            self.current_reslice_id = ""
            self._slice_unavailable_override = ""
            self.local_axis_draft = None
            self.part_mask_workflow_controller.state.preview_mask = None
            self.part_mask_workflow_controller.state.preview_bbox = []
            self.part_mask_workflow_controller.state.preview_accepted = False
            self.roi_workflow_controller.reset_state()
            self.part_mask_workflow_controller.state.keyframes = []
            self.roi_workflow_controller.disable_draw_mode()
            self.part_mask_workflow_controller.disable_contour_draw_mode()
            self.btn_part_draw_roi.blockSignals(True)
            self.btn_part_draw_roi.setChecked(False)
            self.btn_part_draw_roi.blockSignals(False)
            self.btn_draw_part_contour.blockSignals(True)
            self.btn_draw_part_contour.setChecked(False)
            self.btn_draw_part_contour.blockSignals(False)
            # Part review should open as inspection first; otherwise the brush
            # radius cursor looks like a stray ROI/contour before the user edits.
            self.annotation_workflow_controller.set_tool_mode("pan", show_message=False)
            self.release_loaded_volume_arrays(defer=True)
            self.annotation_workflow_controller.reset_dirty_tracking()
            self.part_mask_workflow_controller.state.material_map = {}
            self.part_mask_workflow_controller.state.material_colors = {}
            self.volume_render_controller._reset_active_volume_preview_state()
            self.annotation_workflow_controller.reset_history()
            self._populate_label_role_combo()
            self.preview_controller.clear_resource_issue()

            image_path = self.project.to_absolute((specimen.get("working_volume") or {}).get("path", ""))
            if image_path and volume_sidecar_exists(image_path):
                self.image_volume, _load_issue = self.preview_controller.safe_load_volume_sidecar(image_path, mmap_mode="r", operation="load_specimen_image")
                if self.image_volume is not None:
                    self._slice_positions = {
                        "z": max(0, min(int(self.slice_slider.value()), int(self.image_volume.shape[0]) - 1)),
                        "y": max(0, int(self.image_volume.shape[1]) // 2),
                        "x": max(0, int(self.image_volume.shape[2]) // 2),
                    }
                    self._configure_slice_slider_for_axis(self._current_slice_axis(), preserve_position=True)
                    self._reset_canvas_view_on_next_render = True
            else:
                self._set_slice_review_unavailable(self._slice_unavailable_message(specimen))
                if self._is_metadata_only_specimen(specimen) or self.part_mask_workflow_controller._materialize_task_matches(specimen_id):
                    message = self._volume_unavailable_message(specimen)
                    self.volume_canvas.setText(message)
                    self.volume_render_controller._update_volume_render_status_label(message)

            material_path = self.project.to_absolute(specimen.get("material_map", ""))
            if material_path and os.path.exists(material_path):
                self.part_mask_workflow_controller.state.material_map = read_material_map(material_path)
                self.part_mask_workflow_controller._sync_material_colors_from_active_source()
            self.part_mask_workflow_controller._populate_material_table()
            self._populate_label_schema_combo()
            self._populate_part_user_tag_table()
            self._populate_result_region_combo()
            self.result_review_controller.invalidate_result_region_mask_cache(clear_active_mask_preview=False)
            self.result_review_controller.refresh_result_comparison_if_visible()
            self._populate_volume_tint_combo()
            self._apply_volume_transfer_opacity_setting()
            self._populate_volume_mask_combo()
            self._load_edit_volume()
            self._reload_label_volume(render=False)
            self.part_mask_workflow_controller._reload_part_mask_volume()
            self._update_status_labels(specimen)
            self._apply_default_volume_mask_mode()
            self._sync_mode_sections()
            if not self.part_mask_workflow_controller._ensure_current_metadata_materializing_for_slice_review(specimen):
                self.render_current_slice()
            if self.display_mode == "volume":
                self.volume_render_controller.render_volume_preview()
        finally:
            self._loading_specimen = False
            self.selection_workflow_controller.sync_state_from_workbench()
            self.volume_render_controller.flush_selection_render()

    def load_part(self, specimen_id, part_id, selected_reslice_id=""):
        if self.working_edit_dirty:
            if not self.annotation_workflow_controller.confirm_discard_or_save():
                return
        specimen = self.project.get_specimen(specimen_id, default=None)
        part = self.project.get_part(specimen_id, part_id, default=None)
        if specimen is None or part is None:
            return
        switching_part = (
            specimen_id != self.current_specimen_id
            or part_id != self.current_part_id
            or str(selected_reslice_id or "") != self.current_reslice_id
            or self.current_volume_scope != "part"
        )
        if switching_part:
            self.volume_render_controller._cancel_volume_preview_build()
        self._loading_specimen = True
        try:
            self.auto_save_timer.stop()
            self.current_specimen_id = specimen_id
            self.current_volume_scope = "part"
            self.current_part_id = part.get("part_id", "")
            self.current_part = part
            self.current_reslice_id = str(selected_reslice_id or "")
            self._slice_unavailable_override = ""
            self.local_axis_controller.clear_draft_if_part_changed(specimen_id, self.current_part_id)
            if self.current_reslice_id and self.local_axis_draft is not None:
                self._set_local_axis_status(tt("Selected saved reslice is read-only. Return to the part volume to edit axes or export another reslice.", self.lang))
            if self.current_reslice_id and hasattr(self, "volume_local_axes_check"):
                self.volume_local_axes_check.setChecked(True)
            self.roi_workflow_controller.reset_state()
            self.part_mask_workflow_controller.state.keyframes = []
            self.roi_workflow_controller.disable_draw_mode()
            self.part_mask_workflow_controller.disable_contour_draw_mode()
            self.btn_part_draw_roi.blockSignals(True)
            self.btn_part_draw_roi.setChecked(False)
            self.btn_part_draw_roi.blockSignals(False)
            self.btn_draw_part_contour.blockSignals(True)
            self.btn_draw_part_contour.setChecked(False)
            self.btn_draw_part_contour.blockSignals(False)
            self.release_loaded_volume_arrays(defer=True)
            self.annotation_workflow_controller.reset_dirty_tracking()
            self.part_mask_workflow_controller.state.material_map = {}
            self.part_mask_workflow_controller.state.material_colors = {}
            self.part_mask_workflow_controller.state.preview_mask = None
            self.part_mask_workflow_controller.state.preview_bbox = []
            self.part_mask_workflow_controller.state.preview_accepted = False
            self.volume_render_controller._reset_active_volume_preview_state()
            self.annotation_workflow_controller.reset_history()
            self._populate_label_role_combo()
            self.preview_controller.clear_resource_issue()

            reslice_open_error = ""
            reslice = self.local_axis_controller.current_part_reslice_record()
            if isinstance(reslice, dict) and reslice.get("image_path"):
                image_path = self.project.to_absolute(reslice.get("image_path", ""))
                if image_path and os.path.exists(image_path):
                    self.image_volume, open_error = _tif_open_reslice_volume_for_review(image_path)
                    if open_error:
                        reslice_open_error = open_error
                        self._slice_unavailable_override = tt("Reslice TIF cannot be opened quickly. Re-export the reslice as an uncompressed TaxaMask local-axis TIF before slice review.", self.lang)
                        self.log(tt("Reslice TIF cannot be opened for immediate slice review: {0}", self.lang).format(open_error))
            else:
                image_path = self.project.to_absolute((part.get("image") or {}).get("path", ""))
                if image_path and volume_sidecar_exists(image_path):
                    self.image_volume, _load_issue = self.preview_controller.safe_load_volume_sidecar(image_path, mmap_mode="r", operation="load_part_image")
            if self.image_volume is not None:
                self._slice_positions = {
                    "z": max(0, min(int(self.slice_slider.value()), int(self.image_volume.shape[0]) - 1)),
                    "y": max(0, int(self.image_volume.shape[1]) // 2),
                    "x": max(0, int(self.image_volume.shape[2]) // 2),
                }
                self._configure_slice_slider_for_axis(self._current_slice_axis(), preserve_position=True)
                self._reset_canvas_view_on_next_render = True
            else:
                message = (
                    tt("Reslice TIF cannot be opened quickly. Re-export the reslice as an uncompressed TaxaMask local-axis TIF before slice review.", self.lang)
                    if reslice_open_error
                    else tt("Working volume missing", self.lang)
                )
                self._set_slice_review_unavailable(message)

            material_path = self.project.to_absolute(specimen.get("material_map", ""))
            if material_path and os.path.exists(material_path):
                self.part_mask_workflow_controller.state.material_map = read_material_map(material_path)
                self.part_mask_workflow_controller._sync_material_colors_from_active_source()
            else:
                self.part_mask_workflow_controller._sync_material_colors_from_active_source()
            self.part_mask_workflow_controller._populate_material_table()
            self._populate_label_schema_combo()
            self._populate_part_user_tag_table()
            self._populate_result_region_combo()
            self.result_review_controller.invalidate_result_region_mask_cache(clear_active_mask_preview=False)
            self.result_review_controller.refresh_result_comparison_if_visible()
            self._populate_volume_tint_combo()
            self._apply_volume_transfer_opacity_setting()
            self._load_edit_volume()
            self._reload_label_volume(render=False)
            self.part_mask_workflow_controller._reload_part_mask_volume()
            self._update_status_labels(specimen, part=part)
            if self.current_reslice_id:
                self._set_local_axis_status(tt("Selected saved reslice is read-only. Return to the part volume to edit axes or export another reslice.", self.lang))
            self._apply_default_volume_mask_mode()
            self._sync_mode_sections()
            if self.display_mode == "volume":
                self.volume_render_controller.render_volume_preview()
            else:
                self.render_current_slice()
        finally:
            self._loading_specimen = False
            self.selection_workflow_controller.sync_state_from_workbench()
            self.volume_render_controller.flush_selection_render()

    def _current_part_training_reslice_record(self):
        if self.current_volume_scope != "part" or not self.current_specimen_id or not self.current_part_id:
            return None
        if self.current_reslice_id:
            return self.project.get_part_reslice(self.current_specimen_id, self.current_part_id, self.current_reslice_id, default=None)
        part = self.project.get_part(self.current_specimen_id, self.current_part_id, default=None)
        training = (part or {}).get("training") or {}
        active_reslice_id = str(training.get("active_reslice_id") or "").strip()
        if active_reslice_id:
            reslice = self.project.get_part_reslice(self.current_specimen_id, self.current_part_id, active_reslice_id, default=None)
            if reslice is not None:
                return reslice
        reslices = self.project.list_part_reslices(self.current_specimen_id, self.current_part_id) if part is not None else []
        return reslices[-1] if reslices else None

    def _current_part_label_record(self, role=None):
        if self.current_volume_scope != "part" or not self.current_specimen_id or not self.current_part_id:
            return {}
        role = role or self.label_role_combo.currentData() or "editable_ai_result"
        return self.project.part_label_record(
            self.current_specimen_id,
            self.current_part_id,
            role,
            reslice_id=self.current_reslice_id,
        )

    def _current_part_label_image_path(self):
        if self.current_volume_scope != "part" or not self.current_specimen_id or not self.current_part_id:
            return ""
        reslice = self.local_axis_controller.current_part_reslice_record()
        if isinstance(reslice, dict) and reslice.get("image_path"):
            path = self.project.to_absolute(reslice.get("image_path", ""))
            return path if path and os.path.exists(path) else ""
        part = self.project.get_part(self.current_specimen_id, self.current_part_id, default=None)
        path = self.project.to_absolute(((part or {}).get("image") or {}).get("path", ""))
        return path if path and volume_sidecar_exists(path) else ""

    def _reload_label_volume(self, render=True):
        self.label_volume = None
        self._update_label_role_help()
        if self.current_volume_scope == "part":
            role = self.label_role_combo.currentData() or "editable_ai_result"
            label_path = self.annotation_workflow_controller.current_part_label_path(role)
            if role == "editable_ai_result" and self.edit_volume is not None:
                self.label_volume = self.edit_volume
            elif label_path and volume_sidecar_exists(label_path):
                self.label_volume, _load_issue = self.preview_controller.safe_load_volume_sidecar(label_path, mmap_mode="r", operation=f"load_part_label:{role}")
            if render:
                self.render_current_slice()
            return
        specimen = self.project.get_specimen(self.current_specimen_id, default=None)
        if specimen is None:
            return
        role = self.label_role_combo.currentData()
        label_record = None
        labels = specimen.get("labels") or {}
        if role in {"manual_truth", "working_edit"}:
            label_record = labels.get(role) or {}
        elif role == "model_draft":
            drafts = labels.get("model_drafts") or []
            label_record = drafts[-1] if drafts else {}
        label_path = self.project.to_absolute((label_record or {}).get("path", ""))
        if role == "working_edit" and self.edit_volume is not None:
            self.label_volume = self.edit_volume
        elif label_path and volume_sidecar_exists(label_path):
            self.label_volume, _load_issue = self.preview_controller.safe_load_volume_sidecar(label_path, mmap_mode="r", operation=f"load_label:{role}")
        if render:
            self.render_current_slice()

    def _load_edit_volume(self):
        self.edit_volume = None
        if self.current_volume_scope == "part":
            edit_path = self.annotation_workflow_controller.current_part_label_path("editable_ai_result")
            if edit_path and volume_sidecar_exists(edit_path):
                self.edit_volume, _load_issue = self.preview_controller.safe_load_volume_sidecar(edit_path, mmap_mode="c", operation="load_part_edit_volume")
            return
        specimen = self.project.get_specimen(self.current_specimen_id, default=None)
        if specimen is None:
            return
        edit_path = self.project.to_absolute(((specimen.get("labels") or {}).get("working_edit") or {}).get("path", ""))
        if edit_path and volume_sidecar_exists(edit_path):
            self.edit_volume, _load_issue = self.preview_controller.safe_load_volume_sidecar(edit_path, mmap_mode="c", operation="load_working_edit_volume")

    def _ensure_working_edit_volume(self):
        if not self.coordinator.guard_backend_write_lock():
            return False
        if self.current_volume_scope == "part":
            if not self._guard_current_label_save(role="editable_ai_result", reason="manual", show_message=True):
                return False
            part = self.project.get_part(self.current_specimen_id, self.current_part_id, default=None)
            if part is None:
                return False
            edit_record = self._current_part_label_record("editable_ai_result")
            edit_path = self.project.to_absolute((edit_record or {}).get("path", ""))
            if edit_path and volume_sidecar_exists(edit_path):
                if self.edit_volume is None:
                    self.edit_volume, _load_issue = self.preview_controller.safe_load_volume_sidecar(edit_path, mmap_mode="c", operation="ensure_part_edit_volume")
                return self.edit_volume is not None
            image_path = self._current_part_label_image_path()
            if not image_path:
                return False
            if self.current_reslice_id:
                edit_rel = os.path.join(
                    self.project.part_dir(self.current_specimen_id, self.current_part_id),
                    "reslices",
                    self.current_reslice_id,
                    "labels",
                    "editable_ai_result.ome.zarr",
                ).replace("\\", "/")
            else:
                edit_rel = os.path.join(self.project.part_dir(self.current_specimen_id, self.current_part_id), "labels", "editable_ai_result.ome.zarr").replace("\\", "/")
            edit_abs = self.project.to_absolute(edit_rel)
            if volume_sidecar_exists(image_path):
                metadata = create_empty_label_sidecar_like(image_path, edit_abs, role="editable_ai_result", write_ome_zarr=False)
            else:
                image_array = tifffile.memmap(image_path) if os.path.exists(image_path) else None
                if image_array is None:
                    return False
                metadata, array = create_volume_sidecar_memmap(
                    edit_abs,
                    image_array.shape,
                    "uint16",
                    role="editable_ai_result",
                    orientation="local_axis_reslice" if self.current_reslice_id else "part_volume",
                    source_format="empty_label_like",
                    fill_value=0,
                )
                if hasattr(array, "_mmap"):
                    array._mmap.close()
            if self.current_reslice_id:
                self.project.register_part_reslice_label_volume(
                    self.current_specimen_id,
                    self.current_part_id,
                    self.current_reslice_id,
                    "editable_ai_result",
                    edit_rel,
                    metadata["shape_zyx"],
                    metadata["dtype"],
                    status="empty_edit",
                    spacing_zyx=metadata.get("spacing_zyx"),
                    spacing_unit=metadata.get("spacing_unit", "micrometer"),
                    orientation=metadata.get("orientation", "local_axis_reslice"),
                    fmt=metadata.get("format", ""),
                    operation="create_empty_edit_layer",
                    save=False,
                )
            else:
                self.project.register_part_label_volume(
                    self.current_specimen_id,
                    self.current_part_id,
                    "editable_ai_result",
                    edit_rel,
                    metadata["shape_zyx"],
                    metadata["dtype"],
                    status="empty_edit",
                    spacing_zyx=metadata.get("spacing_zyx"),
                    spacing_unit=metadata.get("spacing_unit", "micrometer"),
                    orientation=metadata.get("orientation", "unknown"),
                    fmt=metadata.get("format", ""),
                    operation="create_empty_edit_layer",
                    save=False,
                )
            self.project.save_project()
            if self.edit_volume is None:
                self.edit_volume, _load_issue = self.preview_controller.safe_load_volume_sidecar(edit_abs, mmap_mode="c", operation="open_created_part_edit_volume")
            return self.edit_volume is not None
        specimen = self.project.get_specimen(self.current_specimen_id, default=None)
        if specimen is None:
            return False
        if not self._guard_current_label_save(role="working_edit", reason="manual", show_message=True):
            return False
        labels = specimen.setdefault("labels", {})
        edit_record = labels.get("working_edit") or {}
        edit_path = self.project.to_absolute(edit_record.get("path", ""))
        if edit_path and volume_sidecar_exists(edit_path):
            if self.edit_volume is None:
                self.edit_volume, _load_issue = self.preview_controller.safe_load_volume_sidecar(edit_path, mmap_mode="c", operation="ensure_working_edit_volume")
            return self.edit_volume is not None
        image_path = self.project.to_absolute((specimen.get("working_volume") or {}).get("path", ""))
        if not image_path or not volume_sidecar_exists(image_path):
            return False
        edit_rel = os.path.join(self.project.specimen_dir(self.current_specimen_id), "labels", "working_edit.ome.zarr").replace("\\", "/")
        edit_abs = self.project.to_absolute(edit_rel)
        metadata = create_empty_label_sidecar_like(image_path, edit_abs, role="working_edit", write_ome_zarr=False)
        self.project.register_label_volume(
            self.current_specimen_id,
            "working_edit",
            edit_rel,
            metadata["shape_zyx"],
            metadata["dtype"],
            status="empty_edit",
            spacing_zyx=metadata.get("spacing_zyx"),
            spacing_unit=metadata.get("spacing_unit", "micrometer"),
            orientation=metadata.get("orientation", "unknown"),
            fmt=metadata.get("format", ""),
            operation="create_empty_edit_layer",
            save=False,
        )
        self.project.save_project()
        self.edit_volume, _load_issue = self.preview_controller.safe_load_volume_sidecar(edit_abs, mmap_mode="c", operation="open_created_working_edit_volume")
        return self.edit_volume is not None

    def _format_tif_path_line(self, label, path_value):
        path_text = str(path_value or "").strip()
        if not path_text:
            return f"{tt(label, self.lang)}: -"
        try:
            absolute = self.project.to_absolute(path_text)
        except Exception:
            absolute = path_text
        if absolute and os.path.normpath(absolute) != os.path.normpath(path_text):
            return f"{tt(label, self.lang)}: {path_text}\n  {absolute}"
        return f"{tt(label, self.lang)}: {path_text}"

    def _on_show_debug_paths_toggled(self, checked=False):
        specimen = self.project.get_specimen(self.current_specimen_id, default=None) if self.current_specimen_id else None
        if specimen is not None:
            self._update_status_labels(specimen, part=self.current_part if self.current_volume_scope == "part" else None)

    def _set_scope_controls_enabled(self):
        is_part = self.current_volume_scope == "part"
        is_saved_reslice = is_part and bool(self.current_reslice_id)
        is_editable_part_volume = is_part and not is_saved_reslice
        has_image = self.image_volume is not None
        label_editable = has_image
        full_volume_editable = has_image and not is_part
        part_training_available = has_image and is_part
        self.label_role_combo.setEnabled(has_image)
        self._set_slice_review_available(has_image)
        for widget in (
            self.brush_size_slider,
            self.btn_save_edit,
            self.btn_tool_brush,
            self.btn_tool_eraser,
            self.btn_tool_lasso,
            self.btn_tool_rectangle,
            self.btn_tool_ellipse,
            self.btn_interpolate_current_label,
            self.btn_copy_material_prev,
            self.btn_copy_material_next,
            self.btn_clear_current_material,
        ):
            widget.setEnabled(label_editable)
        for widget in (
            self.btn_tool_picker,
            self.btn_tool_pan,
        ):
            widget.setEnabled(has_image)
        for widget in (
            self.btn_promote,
            self.btn_export_training,
            self.btn_prepare_dataset,
            self.btn_train_backend,
            self.btn_import_prediction,
            self.btn_accept_selected_ai_results,
        ):
            widget.setEnabled(full_volume_editable or part_training_available)
        if self.backend_panel_controller.action_running():
            self.btn_prepare_dataset.setEnabled(False)
            self.btn_train_backend.setEnabled(False)
            self.btn_import_prediction.setEnabled(False)
            self.btn_accept_selected_ai_results.setEnabled(False)
            self.btn_stop_backend.setEnabled(True)
        else:
            self.btn_stop_backend.setEnabled(False)
            self.btn_open_backend_run.setEnabled(bool(self._tif_backend_run_dir) and os.path.isdir(self._tif_backend_run_dir))
            self.btn_open_backend_result.setEnabled(bool(self._tif_backend_result_json) and os.path.exists(self._tif_backend_result_json))
        self.backend_panel_controller.refresh_training_result_controls()
        self.btn_copy_draft.setEnabled(full_volume_editable)
        self.btn_import_external_prediction_tif.setEnabled(full_volume_editable)
        if hasattr(self, "btn_export_current_rendering"):
            self.btn_export_current_rendering.setEnabled(has_image)
        if hasattr(self, "btn_refresh_result_comparison"):
            self.result_review_controller.sync_result_comparison_controls()
        self.auto_save_check.setEnabled(label_editable)
        self.btn_add_material.setEnabled(full_volume_editable)
        self.btn_edit_material.setEnabled(full_volume_editable)
        self.btn_delete_material.setEnabled(full_volume_editable)
        if hasattr(self, "btn_bind_label_schema_to_part"):
            self.btn_bind_label_schema_to_part.setEnabled(is_part and has_image)
        if hasattr(self, "btn_apply_part_user_tags"):
            self.btn_apply_part_user_tags.setEnabled(is_part)
        if hasattr(self, "btn_choose_part_user_tag_color"):
            self.btn_choose_part_user_tag_color.setEnabled(not self.coordinator.backend_write_lock_active())
        confirm_part_busy = self.roi_workflow_controller.is_confirm_running()
        self.part_bbox_edit.setEnabled(not is_part and has_image and not confirm_part_busy)
        self.btn_part_draw_roi.setEnabled(not is_part and has_image and self.display_mode == "slice" and not confirm_part_busy)
        self.btn_save_part_roi.setEnabled(not is_part and has_image and not confirm_part_busy)
        self.btn_confirm_part_roi.setEnabled(not is_part and has_image and not confirm_part_busy)
        self.btn_cancel_part_roi.setEnabled(not is_part and not confirm_part_busy)
        self.btn_create_part.setEnabled(False)
        self.btn_add_rect_keyframe.setEnabled(False)
        full_volume_mask_editable = full_volume_editable and self.display_mode == "slice" and self._current_slice_axis() == "z"
        contour_enabled = (is_editable_part_volume or full_volume_mask_editable) and has_image and self.display_mode == "slice" and self._current_slice_axis() == "z"
        self.btn_draw_part_contour.setEnabled(contour_enabled)
        self.btn_delete_part_contour.setEnabled(contour_enabled)
        self.btn_clear_part_keyframes.setEnabled((is_editable_part_volume or full_volume_editable) and has_image)
        self.btn_prev_key_slice.setEnabled(contour_enabled)
        self.btn_next_key_slice.setEnabled(contour_enabled)
        part_mask_preview_busy = self.part_mask_workflow_controller._part_mask_preview_running()
        self.btn_preview_part_mask.setEnabled((is_editable_part_volume or full_volume_editable) and has_image and not part_mask_preview_busy and not confirm_part_busy)
        self.btn_accept_part_mask.setEnabled((is_editable_part_volume or full_volume_editable) and self.part_preview_mask is not None and not part_mask_preview_busy and not confirm_part_busy)
        self.btn_clear_part_preview.setEnabled((is_editable_part_volume or full_volume_editable) and self.part_preview_mask is not None and not part_mask_preview_busy and not confirm_part_busy)
        local_axis_export_busy = self.local_axis_controller.export_running()
        local_axis_editable = is_editable_part_volume and has_image and not local_axis_export_busy
        self.btn_copy_source_z_axis.setEnabled(local_axis_editable)
        self.btn_pick_roll_ref_a.setEnabled(local_axis_editable)
        self.btn_pick_roll_ref_b.setEnabled(local_axis_editable)
        self.btn_pick_roll_ref_c.setEnabled(local_axis_editable)
        self.btn_align_axis_to_reference_plane.setEnabled(local_axis_editable)
        self.btn_clear_roll_refs.setEnabled(local_axis_editable)
        self.btn_clear_local_axis_draft.setEnabled(local_axis_editable)
        self.btn_local_axis_reslice.setEnabled(local_axis_editable)
        self.local_axis_trainable_check.setEnabled(local_axis_editable)
        self.btn_export_local_axis_training_manifest.setEnabled(bool(self.project.project_data.get("specimens", [])))
        self.btn_export_part_package.setEnabled(is_editable_part_volume and has_image)
        mesh_export_available = bool(
            has_image and self._current_reviewed_mesh_truth()
        )
        self.btn_export_reviewed_mesh.setEnabled(mesh_export_available)
        if mesh_export_available:
            self.btn_export_reviewed_mesh.setToolTip(
                tt(
                    "Create Blender-ready STL only from the current reviewed manual truth.",
                    self.lang,
                )
            )
        else:
            self.btn_export_reviewed_mesh.setToolTip(
                tt(
                    "The current object has no reviewed training truth. Use Accept as training truth after review, then export STL.",
                    self.lang,
                )
            )
        self.btn_delete_part_volume.setEnabled(is_editable_part_volume and self.current_part is not None)
        write_locked = self.coordinator.backend_write_lock_active()
        self._set_backend_write_locked_controls(write_locked)
        if write_locked and not self.coordinator.backend_write_lock_active(ignored_task_types=self.local_axis_controller.ignored_draft_lock_task_types()):
            self.btn_copy_source_z_axis.setEnabled(local_axis_editable)
            self.btn_pick_roll_ref_a.setEnabled(local_axis_editable)
            self.btn_pick_roll_ref_b.setEnabled(local_axis_editable)
            self.btn_pick_roll_ref_c.setEnabled(local_axis_editable)
            self.btn_align_axis_to_reference_plane.setEnabled(local_axis_editable)
            self.btn_clear_roll_refs.setEnabled(local_axis_editable)
            self.btn_clear_local_axis_draft.setEnabled(local_axis_editable)
            self.local_axis_trainable_check.setEnabled(local_axis_editable)
        self.local_axis_controller.update_summary()
        self._sync_undo_redo_buttons()
        self._update_save_status()

    def _update_status_labels(self, specimen, part=None):
        self._set_scope_controls_enabled()
        readiness = self.project.evaluate_train_ready(specimen.get("specimen_id"))
        if part is not None:
            try:
                part_readiness = self.project.evaluate_part_train_ready(
                    specimen.get("specimen_id"),
                    part.get("part_id", ""),
                    self.current_reslice_id,
                    validate_label_ids=False,
                )
            except Exception:
                part_readiness = {"train_ready": False, "reasons": []}
            training = part.get("training") or {}
            self.status_label.setText(
                f"{tt('Current view', self.lang)}: {tt('Part volume', self.lang)}\n"
                f"{tt('Part', self.lang)}: {part.get('display_name') or part.get('part_id')}\n"
                f"{tt('Status', self.lang)}: {training.get('system_status') or part.get('system_status') or part.get('status', 'draft')}\n"
                f"{tt('Train-ready', self.lang)}: {tt('yes', self.lang) if part_readiness.get('train_ready') else tt('no', self.lang)}\n"
                f"{tt('Reasons', self.lang)}: {', '.join(part_readiness.get('reasons', [])) if part_readiness.get('reasons') else '-'}\n"
                f"{tt('Parent specimen', self.lang)}: {specimen.get('display_name') or specimen.get('specimen_id')}"
            )
        else:
            self.status_label.setText(
                f"{tt('Current view', self.lang)}: {tt('Full volume', self.lang)}\n"
                f"{tt('Status', self.lang)}: {specimen.get('review_status', 'not_started')}\n"
                f"{tt('Train-ready', self.lang)}: {tt('yes', self.lang) if readiness['train_ready'] else tt('no', self.lang)}\n"
                f"{tt('Reasons', self.lang)}: {', '.join(readiness['reasons']) if readiness['reasons'] else '-'}"
            )
        working = specimen.get("working_volume") or {}
        labels = specimen.get("labels") or {}
        model_drafts = labels.get("model_drafts") or []
        latest_draft = model_drafts[-1] if model_drafts else {}
        source = specimen.get("source") or {}
        path_lines = [
            self._format_tif_path_line("Source TIF", source.get("raw_tif") or (specimen.get("provenance") or {}).get("source_file", "")),
            self._format_tif_path_line("Working volume", working.get("path", "")),
            self._format_tif_path_line("Working edit", (labels.get("working_edit") or {}).get("path", "")),
            self._format_tif_path_line("Training truth", (labels.get("manual_truth") or {}).get("path", "")),
            self._format_tif_path_line("Latest model draft", latest_draft.get("path", "")),
            self._format_tif_path_line("Material map", specimen.get("material_map", "")),
            self._format_tif_path_line("Import report", working.get("import_report", "")),
        ]
        if part is not None:
            part_image = part.get("image") or {}
            part_mask = part.get("mask") or {}
            part_labels = part.get("labels") or {}
            path_lines = [
                self._format_tif_path_line("Part image", part_image.get("path", "")),
                self._format_tif_path_line("Part mask", part_mask.get("path", "")),
                self._format_tif_path_line("Editable AI result", (part_labels.get("editable_ai_result") or {}).get("path", "")),
                self._format_tif_path_line("Training truth", (part_labels.get("manual_truth") or {}).get("path", "")),
                self._format_tif_path_line("Raw AI prediction backup", (part_labels.get("raw_ai_prediction_backup") or {}).get("path", "")),
                self._format_tif_path_line("Contours", part.get("contours_path", "")),
                self._format_tif_path_line("Extraction", part.get("extraction_path", "")),
                self._format_tif_path_line("Parent working volume", working.get("path", "")),
            ]
            metadata_lines = [
                f"{tt('Shape Z/Y/X', self.lang)}: {part_image.get('shape_zyx', [])}",
                f"{tt('dtype', self.lang)}: {part_image.get('dtype', '')}",
                f"{tt('spacing Z/Y/X', self.lang)}: {part_image.get('spacing_zyx', [])} {part_image.get('spacing_unit', '')}",
                f"{tt('Parent bbox Z/Y/X', self.lang)}: {part.get('parent_bbox_zyx', [])}",
                f"{tt('Label schema', self.lang)}: {(part.get('training') or {}).get('label_schema_id', '') or '-'}",
                f"{tt('modality', self.lang)}: {specimen.get('modality', 'unknown')}",
            ]
            draft = self.local_axis_controller.current_draft()
            if draft is not None:
                metadata_lines.extend(
                    [
                        "",
                        f"{tt('Local axis draft', self.lang)}: {draft.get('template_id', '')}",
                        f"{tt('Output axis start z,y,x', self.lang)}: {(draft.get('editable_axis') or {}).get('start_zyx', [])}",
                        f"{tt('Output axis end z,y,x', self.lang)}: {(draft.get('editable_axis') or {}).get('end_zyx', [])}",
                    ]
                )
            if self.current_reslice_id:
                reslice = self.project.get_part_reslice(
                    specimen.get("specimen_id", ""),
                    part.get("part_id", ""),
                    self.current_reslice_id,
                    default=None,
                )
                if reslice is not None:
                    training = reslice.get("training") or {}
                    provenance = reslice.get("provenance") or {}
                    metadata_lines.extend(
                        [
                            "",
                            f"{tt('Reslice ID', self.lang)}: {reslice.get('reslice_id', '')}",
                            f"{tt('Template', self.lang)}: {reslice.get('template_id', '')}",
                            f"{tt('Status', self.lang)}: {reslice.get('status', '')}",
                            f"{tt('Image', self.lang)}: {reslice.get('image_path', '')}",
                            f"{tt('Mask', self.lang)}: {reslice.get('mask_path', '') or '-'}",
                            f"{tt('Metadata', self.lang)}: {reslice.get('metadata_path', '')}",
                            f"{tt('Output shape Z/Y/X', self.lang)}: {(reslice.get('reslice_params') or {}).get('output_shape_zyx', [])}",
                            f"{tt('Human confirmed', self.lang)}: {bool(training.get('human_confirmed'))}",
                            f"{tt('Usable for training', self.lang)}: {bool(training.get('usable_for_training', True))}",
                            f"{tt('Hard case flags', self.lang)}: {', '.join(training.get('hard_case_flags', []) or []) or '-'}",
                            f"{tt('Source proposal', self.lang)}: {provenance.get('source_proposal_id', '') or '-'}",
                            f"{tt('Model version', self.lang)}: {provenance.get('source_model_version', '') or '-'}",
                        ]
                    )
        else:
            metadata_lines = [
                f"{tt('Shape Z/Y/X', self.lang)}: {working.get('shape_zyx', [])}",
                f"{tt('dtype', self.lang)}: {working.get('dtype', '')}",
                f"{tt('spacing Z/Y/X', self.lang)}: {working.get('spacing_zyx', [])} {working.get('spacing_unit', '')}",
                f"{tt('modality', self.lang)}: {specimen.get('modality', 'unknown')}",
            ]
        if self.show_debug_paths_check.isChecked():
            metadata_lines.extend(["", *path_lines])
        self.metadata_label.setText("\n".join(metadata_lines))

    def render_current_slice(self):
        if self.image_volume is None:
            specimen = self.project.get_specimen(self.current_specimen_id, default=None) if self.current_specimen_id else None
            self._set_slice_review_unavailable(self._slice_unavailable_message(specimen))
            return
        axis, slice_index = self._active_slice_position()
        total = self._slice_count_for_axis(axis)
        self.slice_label.setText(f"{slice_index + 1} / {total}")
        image_slice = self._extract_axis_slice(self.image_volume, axis, slice_index)
        label_slice = None
        if self.label_volume is not None and self.label_volume.shape == self.image_volume.shape:
            label_slice = self._extract_axis_slice(self.label_volume, axis, slice_index)
        if (
            (
                (self.current_volume_scope == "part" and self.label_role_combo.currentData() == "editable_ai_result")
                or (self.current_volume_scope != "part" and self.label_role_combo.currentData() == "working_edit")
            )
            and self.edit_volume is not None
            and self.edit_volume.shape == self.image_volume.shape
        ):
            label_slice = self._extract_axis_slice(self.edit_volume, axis, slice_index)
        if (
            self.current_volume_scope == "full"
            and self.part_preview_mask is not None
            and self.part_mask_preview_bbox
            and self._current_slice_axis() == "z"
        ):
            bbox = self.part_mask_preview_bbox
            z0, z1 = int(bbox[0][0]), int(bbox[0][1])
            if z0 <= int(slice_index) < z1:
                overlay = np.zeros_like(image_slice, dtype=np.asarray(self.part_preview_mask).dtype)
                local_z = int(slice_index) - z0
                y0, y1 = int(bbox[1][0]), int(bbox[1][1])
                x0, x1 = int(bbox[2][0]), int(bbox[2][1])
                overlay[y0:y1, x0:x1] = np.asarray(self.part_preview_mask[local_z])
                label_slice = overlay
        if self.current_volume_scope == "part" and not self.current_reslice_id and self.part_preview_mask is not None and self.part_preview_mask.shape == self.image_volume.shape:
            label_slice = self._extract_axis_slice(self.part_preview_mask, axis, slice_index)
        pixmap = self._render_slice_pixmap(image_slice, label_slice)
        reset_view = bool(getattr(self, "_reset_canvas_view_on_next_render", False))
        self._reset_canvas_view_on_next_render = False
        self.canvas.set_slice_pixmap(pixmap, reset_view=reset_view)

    def _extract_axis_slice(self, volume, axis, index):
        if volume is None:
            return None
        axis = axis if axis in {"z", "y", "x"} else "z"
        if axis == "y":
            index = max(0, min(int(index), int(volume.shape[1]) - 1))
            return np.asarray(volume[:, index, :])
        if axis == "x":
            index = max(0, min(int(index), int(volume.shape[2]) - 1))
            return np.asarray(volume[:, :, index])
        index = max(0, min(int(index), int(volume.shape[0]) - 1))
        return np.asarray(volume[index])

    def volume_status_text(self):
        resource_summary = self.preview_controller.state_summary()
        if resource_summary.get("resource_limited"):
            return str(resource_summary.get("user_message") or "")
        if self.image_volume is None:
            return ""
        return (
            f"{tt('3D volume', self.lang)} | "
            f"{self.volume_render_controller._volume_renderer_label()} | "
            f"{self.volume_render_controller._volume_mode_label()} | "
            f"{tt('drag rotate / wheel zoom', self.lang)} | "
            f"{int(round(self._volume_zoom * 100))}%"
        )

    def _can_edit_current_label_volume(self):
        if self.coordinator.backend_write_lock_active():
            return False
        if self.image_volume is None:
            return False
        if self.display_mode == "volume":
            return False
        if self._current_slice_axis() != "z":
            return False
        if self.current_volume_scope == "part":
            return self.label_role_combo.currentData() == "editable_ai_result"
        if not hasattr(self, "label_role_combo"):
            return False
        return self.label_role_combo.currentData() == "working_edit"

    def _is_editable_part_volume(self):
        return bool(self.current_volume_scope == "part" and not self.current_reslice_id)

    def volume_canvas_overlay_text(self):
        if self.image_volume is None:
            return ""
        stats_text = self.volume_render_controller._volume_stats_text()
        parts = [
            tt("Volume view", self.lang),
            self.volume_render_controller._volume_renderer_label(),
            self.volume_render_controller._volume_mode_label(),
            f"{tt('Mode', self.lang)} {self.volume_render_controller._volume_projection_label()}",
            f"{tt('Transfer function', self.lang)} {self.volume_render_controller._volume_transfer_label()}",
            f"{tt('Shader quality', self.lang)} {self.volume_render_controller._volume_shader_quality_label_text()}",
            f"{tt('Mask display', self.lang)} {self.volume_render_controller._volume_mask_label_text()}",
            f"{tt('Detail enhancement', self.lang)} {int(self.volume_enhancement_slider.value())}%",
            f"{tt('Texture', self.lang)} {self.volume_render_controller._active_volume_target_dim()}",
            f"{tt('Samples', self.lang)} {self.volume_render_controller._active_volume_sample_count()}",
            f"{tt('ROI', self.lang)} {self.volume_render_controller._active_volume_roi_scale():.1f}x",
            f"{tt('ROI budget', self.lang)} {self.volume_render_controller._roi_texture_budget_bytes() / (1024.0 ** 3):.1f} GB",
        ]
        if self.volume_clip_plane_check.isChecked():
            parts.append(f"{tt('Clip plane', self.lang)} {int(self.volume_clip_plane_depth_slider.value())}%")
        parts.extend(
            [
                f"{tt('Inside', self.lang)} {int(self.volume_inside_slider.value())}%",
                f"{tt('Cut', self.lang)} {int(self.volume_clip_slider.value())}%",
                f"{tt('Zoom', self.lang)} {int(round(self._volume_zoom * 100))}%",
                f"{tt('Pan X', self.lang)} {int(round(self._volume_pan_x * 100))}%",
                f"{tt('Pan Y', self.lang)} {int(round(self._volume_pan_y * 100))}%",
            ]
        )
        if stats_text:
            parts.append(stats_text)
        return " | ".join(parts)

    def eventFilter(self, watched, event):
        if self.volume_render_controller._volume_preview_ui_waiting() and isinstance(watched, QWidget) and (watched is self or self.isAncestorOf(watched)):
            if event.type() in {
                QEvent.MouseButtonPress,
                QEvent.MouseButtonRelease,
                QEvent.MouseButtonDblClick,
                QEvent.KeyPress,
                QEvent.KeyRelease,
            }:
                return True
        return super().eventFilter(watched, event)

    def _editable_label_block_reason(self, require_working_edit=True):
        if self.image_volume is None:
            return ""
        if self.current_volume_scope == "part":
            if self.display_mode == "volume":
                return tt("3D volume preview is read-only. Switch to Slice review for label editing.", self.lang)
            if self._current_slice_axis() != "z":
                return tt("Painting is available on Z slices only. Switch back to Z axial view before editing labels.", self.lang)
            if require_working_edit and self.label_role_combo.currentData() != "editable_ai_result":
                role = self.label_role_combo.currentData()
                guard = require_editable_label_role(role, scope="part")
                if guard.reason == "raw_ai_prediction_backup_is_read_only":
                    return tt("Raw AI prediction backup is read-only. Switch to editable AI result before correcting labels.", self.lang)
                if guard.reason == "manual_truth_is_not_directly_editable":
                    return tt("Cannot paint on training truth directly. Switch to editable AI result first.", self.lang)
                return tt("Cannot paint on this part label layer. Switch to editable AI result first.", self.lang)
            return ""
        if self.display_mode == "volume":
            return tt("3D volume preview is read-only. Switch to Slice review for label editing.", self.lang)
        if self._current_slice_axis() != "z":
            return tt("Painting is available on Z slices only. Switch back to Z axial view before editing labels.", self.lang)
        if not require_working_edit:
            return ""
        role = self.label_role_combo.currentData()
        if role != "working_edit":
            guard = require_editable_label_role(role, scope="top_level")
            if guard.reason == "model_draft_is_read_only":
                return tt("Cannot paint on the legacy model draft. Switch to Current labels first.", self.lang)
            if guard.reason == "raw_ai_prediction_backup_is_read_only":
                return tt("Raw AI prediction backup is read-only. Switch to Current labels first.", self.lang)
            if guard.reason == "manual_truth_is_not_directly_editable":
                return tt("Cannot paint on training truth directly. Switch to Current labels first.", self.lang)
            return tt("Cannot paint on this label layer. Switch to Current labels first.", self.lang)
        return ""

    def begin_annotation_stroke(self):
        return self.annotation_workflow_controller.begin_annotation_stroke()

    def finish_annotation_stroke(self):
        return self.annotation_workflow_controller.finish_annotation_stroke()

    def paint_at_widget_position(self, x, y, erase=False, continue_stroke=False):
        return self.annotation_workflow_controller.paint_at_widget_position(x, y, erase=erase, continue_stroke=continue_stroke)

    def finish_lasso_fill(self, points):
        return self.annotation_workflow_controller.finish_lasso_fill(points)

    def finish_shape_fill_drag(self, mode, start_x, start_y, end_x, end_y):
        return self.annotation_workflow_controller.finish_shape_fill_drag(mode, start_x, start_y, end_x, end_y)

    def _ensure_editable_working_edit_for_helper(self):
        if not self.coordinator.guard_backend_write_lock(show_message=False):
            self._set_operation_feedback(self.coordinator.backend_write_lock_message())
            return False
        if self.image_volume is None:
            return False
        block_reason = self._editable_label_block_reason(require_working_edit=True)
        if block_reason:
            self._set_operation_feedback(block_reason)
            return False
        if self.edit_volume is None:
            self._set_operation_feedback(tt("Creating current label layer before filling...", self.lang))
            if not self._ensure_working_edit_volume():
                self._set_operation_feedback(tt("Current label layer is unavailable. Check the working volume path before editing labels.", self.lang))
                return False
        return True

    def _widget_to_image_pixel(self, x, y, image_width, image_height):
        pixel = self.canvas.widget_to_image_pixel(x, y)
        if pixel is None:
            return None
        px, py = pixel
        return max(0, min(image_width - 1, px)), max(0, min(image_height - 1, py))

    def _push_undo_for_slice(self, z_index):
        return self.annotation_workflow_controller.push_undo_for_slice(z_index)

    def undo(self):
        return self.annotation_workflow_controller.undo()

    def redo(self):
        return self.annotation_workflow_controller.redo()

    def _finalize_full_edit_save_metadata(self, metadata, auto_saved=False, refresh_volumes=True):
        specimen = self.project.get_specimen(self.current_specimen_id, default=None)
        if specimen is None:
            return False
        labels = specimen.setdefault("labels", {})
        labels.setdefault("working_edit", {})
        if metadata:
            labels["working_edit"]["dtype"] = metadata.get("dtype", labels["working_edit"].get("dtype", ""))
            labels["working_edit"]["shape_zyx"] = metadata.get("shape_zyx", labels["working_edit"].get("shape_zyx", []))
            labels["working_edit"]["spacing_zyx"] = metadata.get("spacing_zyx", labels["working_edit"].get("spacing_zyx", [1.0, 1.0, 1.0]))
            labels["working_edit"]["spacing_unit"] = metadata.get("spacing_unit", labels["working_edit"].get("spacing_unit", "micrometer"))
            labels["working_edit"]["orientation"] = metadata.get("orientation", labels["working_edit"].get("orientation", "unknown"))
            labels["working_edit"]["format"] = metadata.get("format", labels["working_edit"].get("format", ""))
        labels["working_edit"]["status"] = "in_progress"
        specimen["review_status"] = "in_progress"
        specimen["train_ready"] = False
        self.project.save_project()
        if refresh_volumes:
            edit_path = self._current_edit_save_path()
            self.edit_volume = load_volume_sidecar(edit_path, mmap_mode="c") if edit_path else self.edit_volume
            if self.label_role_combo.currentData() == "working_edit" and edit_path:
                self.label_volume = load_volume_sidecar(edit_path, mmap_mode="r")
            else:
                self._reload_label_volume()
            self._update_status_labels(specimen)
        return True

    def _finalize_part_editable_save_metadata(self, metadata, auto_saved=False, refresh_volumes=True):
        specimen = self.project.get_specimen(self.current_specimen_id, default=None)
        part = self.project.get_part(self.current_specimen_id, self.current_part_id, default=None)
        if specimen is None or part is None:
            return False
        if self.current_reslice_id:
            reslice = self.local_axis_controller.current_part_reslice_record()
            label_record = (reslice or {}).setdefault("labels", {}).setdefault("editable_ai_result", {})
        else:
            label_record = part.setdefault("labels", {}).setdefault("editable_ai_result", {})
        if metadata:
            label_record["dtype"] = metadata.get("dtype", label_record.get("dtype", ""))
            label_record["shape_zyx"] = metadata.get("shape_zyx", label_record.get("shape_zyx", []))
            label_record["spacing_zyx"] = metadata.get("spacing_zyx", label_record.get("spacing_zyx", [1.0, 1.0, 1.0]))
            label_record["spacing_unit"] = metadata.get("spacing_unit", label_record.get("spacing_unit", "micrometer"))
            label_record["orientation"] = metadata.get("orientation", label_record.get("orientation", "unknown"))
            label_record["format"] = metadata.get("format", label_record.get("format", ""))
        label_record["role"] = "editable_ai_result"
        label_record["status"] = "pending_review"
        if self.current_reslice_id:
            label_record["coordinate_space"] = "local_axis_reslice_voxel_zyx"
            label_record["reslice_id"] = str(self.current_reslice_id or "")
        self.project.set_part_training_metadata(
            self.current_specimen_id,
            self.current_part_id,
            active_reslice_id=str(self.current_reslice_id or "") if self.current_reslice_id else None,
            system_status="predicted_pending_review",
            opened_for_review=True,
            save=False,
        )
        self.project.save_project()
        self.current_part = part
        if refresh_volumes:
            edit_path = self.annotation_workflow_controller.current_part_label_path("editable_ai_result")
            self.edit_volume = load_volume_sidecar(edit_path, mmap_mode="c") if edit_path else self.edit_volume
            if self.label_role_combo.currentData() == "editable_ai_result" and edit_path:
                self.label_volume = load_volume_sidecar(edit_path, mmap_mode="r")
            else:
                self._reload_label_volume()
            self._update_status_labels(specimen, part=part)
            self._update_ai_review_check_label()
        return True

    def save_working_edit(self, show_message=True, reason="manual"):
        if not self.coordinator.guard_backend_write_lock(show_message=show_message):
            return False
        if self._saving_working_edit:
            return True
        if reason == "auto_save":
            return self.annotation_workflow_controller.start_auto_save(reason=reason)
        self.annotation_workflow_controller.wait_for_auto_save()
        if self.current_volume_scope == "part":
            return self._save_part_editable_label(show_message=show_message, reason=reason)
        specimen = self.project.get_specimen(self.current_specimen_id, default=None)
        if specimen is None or self.edit_volume is None:
            return False
        edit_path = self.project.to_absolute(((specimen.get("labels") or {}).get("working_edit") or {}).get("path", ""))
        if not edit_path:
            return False
        if not self._guard_current_label_save(role="working_edit", reason=reason, show_message=show_message):
            return False
        self._saving_working_edit = True
        self.auto_save_timer.stop()
        self._update_save_status(state="saving")
        try:
            self.label_volume = None
            target = load_volume_sidecar(edit_path, mmap_mode="r+")
            if self._dirty_edit_slices:
                for z_index in sorted(self._dirty_edit_slices):
                    if 0 <= int(z_index) < int(target.shape[0]):
                        target[int(z_index)] = self.edit_volume[int(z_index)]
            metadata = flush_volume_array(edit_path, target)
            self.annotation_workflow_controller.reset_dirty_tracking()
            self._finalize_full_edit_save_metadata(metadata, refresh_volumes=True)
            self._update_save_status()
        except Exception as exc:
            self.annotation_workflow_controller.set_dirty(True)
            message = tt("Save failed: {0}", self.lang).format(str(exc))
            self._set_operation_feedback(message)
            self._update_save_status(state="failed", detail=str(exc))
            QMessageBox.warning(self, tt("Unsaved working edit", self.lang), str(exc))
            return False
        finally:
            self._saving_working_edit = False
            self._update_save_status()
        if show_message:
            message = tt("Auto-saved current labels.", self.lang) if reason == "auto_save" else tt("Current labels saved.", self.lang)
            self._set_operation_feedback(message)
        return True

    def _save_part_editable_label(self, show_message=True, reason="manual"):
        specimen = self.project.get_specimen(self.current_specimen_id, default=None)
        part = self.project.get_part(self.current_specimen_id, self.current_part_id, default=None)
        if specimen is None or part is None:
            return False
        if self.edit_volume is None and not self._ensure_working_edit_volume():
            return False
        edit_path = self.annotation_workflow_controller.current_part_label_path("editable_ai_result")
        if not edit_path:
            return False
        if not self._guard_current_label_save(role="editable_ai_result", reason=reason, show_message=show_message):
            return False
        self._saving_working_edit = True
        self.auto_save_timer.stop()
        self._update_save_status(state="saving")
        try:
            self.label_volume = None
            target = load_volume_sidecar(edit_path, mmap_mode="r+")
            if self._dirty_edit_slices:
                for z_index in sorted(self._dirty_edit_slices):
                    if 0 <= int(z_index) < int(target.shape[0]):
                        target[int(z_index)] = self.edit_volume[int(z_index)]
            metadata = flush_volume_array(edit_path, target)
            self.annotation_workflow_controller.reset_dirty_tracking()
            self._finalize_part_editable_save_metadata(metadata, refresh_volumes=True)
            self._update_save_status()
        except Exception as exc:
            self.annotation_workflow_controller.set_dirty(True)
            message = tt("Save failed: {0}", self.lang).format(str(exc))
            self._set_operation_feedback(message)
            self._update_save_status(state="failed", detail=str(exc))
            QMessageBox.warning(self, tt("Unsaved working edit", self.lang), str(exc))
            return False
        finally:
            self._saving_working_edit = False
            self._update_save_status()
        if show_message:
            message = tt("Auto-saved editable AI result.", self.lang) if reason == "auto_save" else tt("Editable AI result saved.", self.lang)
            self._set_operation_feedback(message)
        return True

    def promote_working_edit(self):
        return self.annotation_workflow_controller.promote_working_edit()

    def copy_latest_model_draft_to_working_edit(self):
        if not self.coordinator.guard_backend_write_lock():
            return
        if not self.current_specimen_id:
            return
        if self.current_volume_scope == "part":
            QMessageBox.information(self, tt("TIF backend", self.lang), tt("Part volumes do not use model draft handoff in this version.", self.lang))
            return
        specimen = self.project.get_specimen(self.current_specimen_id, default=None)
        drafts = ((specimen or {}).get("labels") or {}).get("model_drafts") or []
        if not drafts:
            QMessageBox.warning(
                self,
                tt("TIF backend", self.lang),
                tt("No model draft is available for this specimen.", self.lang),
            )
            return
        try:
            self.project.copy_label_layer_to_working_edit(self.current_specimen_id, source_role="model_draft")
        except Exception as exc:
            QMessageBox.warning(self, tt("TIF backend", self.lang), str(exc))
            return
        index = self.label_role_combo.findData("working_edit")
        if index >= 0:
            self.label_role_combo.setCurrentIndex(index)
        self.load_specimen(self.current_specimen_id)
        message = tt("Copied latest model draft into working_edit.", self.lang)
        self.training_status_label.setText(message)
        self.log(message)

    def export_training_dataset(self):
        if not self.coordinator.guard_backend_write_lock():
            return
        if not self.project.current_project_path:
            QMessageBox.warning(self, tt("TIF training handoff", self.lang), tt("Please create or open a TIF project first.", self.lang))
            return
        use_part_training = bool(self.current_volume_scope == "part" or self.project.list_train_ready_parts())
        default_dir = os.path.join(self.project.project_dir, "exports", "part_train_ready" if use_part_training else "train_ready")
        os.makedirs(default_dir, exist_ok=True)
        output_dir = QFileDialog.getExistingDirectory(self, tt("Export train-ready TIF volumes", self.lang), default_dir)
        if not output_dir:
            return
        formats = [
            item.strip()
            for item in self.backend_formats_edit.text().split(",")
            if item.strip()
        ]
        try:
            if use_part_training:
                part_refs = self._selected_part_refs_for_action("prepare_dataset")
                result = export_tif_part_training_dataset(
                    self.project,
                    output_dir,
                    part_refs=part_refs,
                    formats=formats or ["ome_tiff", "nrrd", "mha", "nifti"],
                    require_train_ready=True,
                )
            else:
                result = export_tif_training_dataset(
                    self.project,
                    output_dir,
                    formats=formats or ["ome_tiff", "nrrd", "mha", "nifti"],
                    require_train_ready=True,
                )
        except Exception as exc:
            QMessageBox.warning(self, tt("TIF training handoff", self.lang), str(exc))
            message = tt("Export failed: {0}", self.lang).format(str(exc))
            self.training_status_label.setText(message)
            self.log(message)
            return
        manifest_path = result.get("manifest_path", "")
        exported_count = result.get("exported_count", 0)
        if use_part_training:
            message = tt("Exported {0} train-ready part(s).\nManifest: {1}", self.lang).format(exported_count, manifest_path)
        else:
            message = tt("Exported {0} train-ready specimen(s).\nManifest: {1}", self.lang).format(exported_count, manifest_path)
        self.training_status_label.setText(message)
        self.log(message)
        QMessageBox.information(
            self,
            tt("TIF training handoff", self.lang),
            message,
        )

    def _current_reviewed_mesh_truth(self):
        if not self.current_specimen_id:
            return {}
        try:
            if self.current_volume_scope == "part":
                record = self.project.part_label_record(
                    self.current_specimen_id,
                    self.current_part_id,
                    "manual_truth",
                    reslice_id=self.current_reslice_id,
                )
            else:
                specimen = self.project.get_specimen(
                    self.current_specimen_id,
                    default=None,
                )
                record = ((specimen or {}).get("labels") or {}).get(
                    "manual_truth"
                ) or {}
            if (
                not record.get("path")
                or str(record.get("status") or "reviewed")
                not in {"reviewed", "verified", "train_ready"}
            ):
                return {}
            path = self.project.to_absolute(record["path"])
            return dict(record) if volume_sidecar_exists(path) else {}
        except Exception:
            return {}

    def open_reviewed_mesh_export_dialog(self):
        if not self.current_specimen_id or self.image_volume is None:
            QMessageBox.information(
                self,
                tt("Mesh export", self.lang),
                tt(
                    "Select a TIF volume before exporting reviewed label meshes.",
                    self.lang,
                ),
            )
            return None
        if not self._current_reviewed_mesh_truth():
            QMessageBox.information(
                self,
                tt("Mesh export", self.lang),
                tt(
                    "The current object has no reviewed training truth. Use Accept as training truth after review, then export STL.",
                    self.lang,
                ),
            )
            return None
        try:
            dialog = TifMeshExportDialog(
                self.project,
                self.current_specimen_id,
                part_id=self.current_part_id if self.current_volume_scope == "part" else "",
                reslice_id=self.current_reslice_id if self.current_volume_scope == "part" else "",
                lang=self.lang,
                parent=self,
            )
            dialog.exec()
            return dialog
        except Exception as exc:
            message = tt("Mesh export could not be opened: {0}", self.lang).format(
                str(exc)
            )
            self.log(message)
            QMessageBox.warning(self, tt("Mesh export", self.lang), message)
            return None

    def export_current_part_package(self):
        if not self.coordinator.guard_backend_write_lock():
            return
        if not self._is_editable_part_volume() or not self.current_specimen_id or not self.current_part_id:
            QMessageBox.information(self, tt("Part extraction", self.lang), tt("Select a part volume before exporting a part package.", self.lang))
            return
        default_dir = os.path.join(self.project.project_dir, "exports", "parts")
        os.makedirs(default_dir, exist_ok=True)
        output_dir = QFileDialog.getExistingDirectory(self, tt("Export part package", self.lang), default_dir)
        if not output_dir:
            return
        try:
            result = export_part_package(self.project, self.current_specimen_id, self.current_part_id, output_dir)
        except Exception as exc:
            QMessageBox.warning(self, tt("Part extraction", self.lang), str(exc))
            return
        manifest_path = result.get("manifest_path", "")
        package_dir = result.get("package_dir", "") or os.path.dirname(manifest_path)
        package_name = os.path.basename(os.path.normpath(package_dir)) if package_dir else "-"
        manifest_name = os.path.basename(manifest_path) if manifest_path else "-"
        message = tt("Exported part package.\nFolder: {0}\nManifest: {1}", self.lang).format(package_name, manifest_name)
        full_message = tt("Exported part package.\nFolder: {0}\nManifest: {1}", self.lang).format(package_dir or "-", manifest_path or "-")
        self.training_status_label.setText(message)
        self.training_status_label.setToolTip(full_message)
        self.log(full_message)
        QMessageBox.information(self, tt("Part extraction", self.lang), message)

    def _safe_export_name_fragment(self, value, fallback="item"):
        text = str(value or "").strip() or str(fallback or "item")
        clean = []
        for char in text:
            clean.append(char if char.isalnum() or char in {"-", "_"} else "_")
        result = "".join(clean).strip("_")
        return result or str(fallback or "item")

    def _current_result_region_slug(self):
        combo = getattr(self, "result_region_combo", None)
        value = combo.currentData() if combo is not None and combo.count() else 0
        if value in (None, "", 0):
            return "all"
        label = self._safe_export_name_fragment(self.result_review_controller.result_region_name(), "")
        suffix = f"_{label}" if label else ""
        return self._safe_export_name_fragment(f"region_{value}{suffix}", "region")

    def _current_rendering_screenshot_metadata(self, image_path, sidecar_path):
        selected_row = self.result_review_controller.selected_result_comparison_row() if hasattr(self, "result_compare_table") else {}
        active_part = self.project.get_part(self.current_specimen_id, self.current_part_id, default=None) if self.current_specimen_id and self.current_part_id else None
        training = (active_part or {}).get("training") or {}
        label_role = self.result_review_controller.result_source_role() if hasattr(self, "result_source_manual_radio") else (self.label_role_combo.currentData() if hasattr(self, "label_role_combo") else "")
        label_record = self._current_part_label_record(label_role) if self.current_volume_scope == "part" and label_role else {}
        target = self.volume_canvas if self.display_mode == "volume" else self.canvas
        region_id = self.result_review_controller.result_region_id() if hasattr(self, "result_region_combo") else 0
        return {
            "schema_version": "taxamask_tif_render_screenshot_v1",
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "image_path": os.path.abspath(str(image_path)),
            "sidecar_path": os.path.abspath(str(sidecar_path)),
            "project_path": os.path.abspath(str(self.project.current_project_path or "")),
            "project_relative_image_path": self.project.to_relative(image_path),
            "project_relative_sidecar_path": self.project.to_relative(sidecar_path),
            "scope": self.current_volume_scope,
            "specimen_id": str(self.current_specimen_id or ""),
            "part_id": str(self.current_part_id or ""),
            "reslice_id": str(self.current_reslice_id or training.get("active_reslice_id") or ""),
            "user_defined_part_name": str(training.get("user_defined_part_name") or (active_part or {}).get("display_name") or ""),
            "label_schema_id": str(training.get("label_schema_id") or ""),
            "region_id": int(region_id),
            "region_name": self.result_review_controller.result_region_name() if region_id > 0 else tt("All", self.lang),
            "region_slug": self._current_result_region_slug(),
            "label_role": str(label_role or ""),
            "label_path": self.project.to_relative((label_record or {}).get("path", "")),
            "label_status": str((label_record or {}).get("status") or ""),
            "prediction_id": str((label_record or {}).get("prediction_id") or ""),
            "source_model": str((label_record or {}).get("source_model") or ""),
            "display_mode": str(self.display_mode or ""),
            "volume_mask_mode": str(self.volume_mask_combo.currentData() if hasattr(self, "volume_mask_combo") else ""),
            "volume_renderer": str(getattr(self, "_volume_canvas_renderer", "")),
            "slice_axis": str(self._current_slice_axis() if hasattr(self, "_current_slice_axis") else ""),
            "slice_index": int(getattr(self, "slice_index", 0) or 0),
            "canvas_size": [int(target.width()), int(target.height())],
            "selected_result_row": selected_row,
            "notes": [
                "This sidecar records the TaxaMask view state for the exported screenshot.",
                "Use label_role and label_status to distinguish reviewed manual_truth from editable AI results pending review.",
            ],
        }

    def export_current_rendering_screenshot(self):
        if self.image_volume is None:
            QMessageBox.information(self, tt("Export current rendering", self.lang), tt("Select a TIF volume before exporting the current rendering.", self.lang))
            return ""
        default_dir = os.path.join(self.project.project_dir, "exports", "render_screenshots")
        os.makedirs(default_dir, exist_ok=True)
        timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
        specimen_id = self._safe_export_name_fragment(self.current_specimen_id, "specimen")
        part_id = self._safe_export_name_fragment(self.current_part_id or "full", "full")
        region = self._current_result_region_slug()
        mode = "volume" if self.display_mode == "volume" else "slice"
        default_path = os.path.join(default_dir, f"{specimen_id}_{part_id}_{region}_{mode}_{timestamp}.png")
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            tt("Export current rendering", self.lang),
            default_path,
            "PNG image (*.png)",
        )
        if not file_path:
            return ""
        target = self.volume_canvas if self.display_mode == "volume" else self.canvas
        pixmap = target.grab()
        try:
            if not pixmap.save(file_path, "PNG"):
                raise ValueError("pixmap_save_failed")
            sidecar_path = os.path.splitext(file_path)[0] + ".json"
            atomic_write_json(
                sidecar_path,
                self._current_rendering_screenshot_metadata(file_path, sidecar_path),
                indent=2,
                ensure_ascii=False,
            )
        except Exception as exc:
            message = tt("Screenshot export failed: {0}", self.lang).format(str(exc))
            self.training_status_label.setText(message)
            QMessageBox.warning(self, tt("Export current rendering", self.lang), message)
            return ""
        message = tt("Exported current rendering screenshot: {0}", self.lang).format(file_path)
        self.training_status_label.setText(message)
        self.training_status_label.setToolTip(file_path)
        self.log(message)
        return file_path

    def _render_slice_pixmap(self, image_slice, label_slice=None):
        gray = self._normalize_image(image_slice)
        rgb = np.stack([gray, gray, gray], axis=-1)
        if label_slice is not None and self.opacity_slider.value() > 0:
            alpha = self.opacity_slider.value() / 100.0
            mask = label_slice > 0
            if np.any(mask):
                overlay = np.zeros_like(rgb)
                for material_id in np.unique(label_slice[mask]):
                    color = self.material_colors.get(int(material_id), QColor("#ff4b4b"))
                    overlay[label_slice == material_id] = [color.red(), color.green(), color.blue()]
                rgb[mask] = ((1.0 - alpha) * rgb[mask].astype(np.float32) + alpha * overlay[mask].astype(np.float32)).astype(np.uint8)
        height, width = rgb.shape[:2]
        rgb = np.ascontiguousarray(rgb)
        image = QImage(rgb.data, width, height, rgb.strides[0], QImage.Format_RGB888).copy()
        return QPixmap.fromImage(image)

    def _normalize_image(self, image_slice):
        data = np.asarray(image_slice, dtype=np.float32)
        finite = data[np.isfinite(data)]
        if finite.size == 0:
            return np.zeros(data.shape, dtype=np.uint8)
        low = float(np.percentile(finite, 1))
        high = float(np.percentile(finite, 99))
        if high <= low:
            low = float(np.min(finite))
            high = float(np.max(finite))
        if high <= low:
            return np.zeros(data.shape, dtype=np.uint8)
        normalized = (data - low) / (high - low)
        contrast = self.contrast_slider.value() / 10.0
        brightness = self.brightness_slider.value() / 100.0
        normalized = (normalized - 0.5) * contrast + 0.5 + brightness
        return np.clip(normalized * 255.0, 0, 255).astype(np.uint8)
