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
    from AntSleap.ui.style import get_theme_config, normalize_theme
    from AntSleap.ui.tif_tasks import TifQtTaskAdapter
    from AntSleap.ui.tif_workbench_canvas import LazyRegionMaskVolume, MirroredStatusLabel, TifSliceCanvas, TifSpecimenTree, TifVolumeCanvas, WheelSafeComboBox, WheelSafeSlider, WheelSafeSpinBox, create_tif_volume_canvas
    from AntSleap.ui.tif_backend_panel_controller import TifBackendPanelController
    from AntSleap.ui.tif_workbench_control_panels import build_right_control_panel
    from AntSleap.ui.tif_workbench_dialogs import MaterialEditorDialog, TifPartNameDialog, TifTrainingResultDialog, summarize_tif_training_result
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
    from AntSleap.ui.tif_local_axis_controller import TifLocalAxisController
    from AntSleap.ui.tif_preview_controller import TifPreviewController
    from AntSleap.ui.tif_workbench_translations import TIF_TRANSLATIONS, tt
    from AntSleap.ui.tif_workbench_workers import (
        TifBackendActionWorker,
        TifBatchImportWorker,
        TifConfirmPartRoiWorker,
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
    from ui.style import get_theme_config, normalize_theme
    from ui.tif_tasks import TifQtTaskAdapter
    from ui.tif_workbench_canvas import LazyRegionMaskVolume, MirroredStatusLabel, TifSliceCanvas, TifSpecimenTree, TifVolumeCanvas, WheelSafeComboBox, WheelSafeSlider, WheelSafeSpinBox, create_tif_volume_canvas
    from ui.tif_backend_panel_controller import TifBackendPanelController
    from ui.tif_workbench_control_panels import build_right_control_panel
    from ui.tif_workbench_dialogs import MaterialEditorDialog, TifPartNameDialog, TifTrainingResultDialog, summarize_tif_training_result
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
    from ui.tif_local_axis_controller import TifLocalAxisController
    from ui.tif_preview_controller import TifPreviewController
    from ui.tif_workbench_translations import TIF_TRANSLATIONS, tt
    from ui.tif_workbench_workers import (
        TifBackendActionWorker,
        TifBatchImportWorker,
        TifConfirmPartRoiWorker,
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
    theme = normalize_theme(theme)
    return "#111A2B" if theme == "light" else "#07101D"


def _tif_overlay_background(alpha=190, theme="dark"):
    color = QColor(_tif_canvas_background(theme))
    color.setAlpha(int(alpha))
    return color


def _tif_workbench_theme(theme="dark"):
    c = get_theme_config(theme)
    is_light = bool(c["is_light"])
    canvas_bg = _tif_canvas_background(theme)
    return {
        "root": c["bg_main"],
        "panel": c["bg_surface"],
        "panel_alt": c["bg_surface_alt"],
        "section": c["bg_surface_alt"] if is_light else c["bg_panel"],
        "canvas_shell": "#DCE6F0" if is_light else "#0B1424",
        "canvas": canvas_bg,
        "input": c["bg_input"],
        "table_alt": "#EDF3F8" if is_light else "#122039",
        "button": "#F8FBFE" if is_light else "#17263C",
        "button_hover": "#EEF4FA" if is_light else "#213854",
        "button_pressed": "#E4EDF7" if is_light else "#101B2E",
        "button_disabled": c["bg_panel"],
        "primary": c["accent"],
        "primary_hover": c["accent_hover"],
        "primary_pressed": "#0369A1" if is_light else "#405F88",
        "secondary_checked": "#DCEFFA" if is_light else "#243D63",
        "danger": "#FDE8E8" if is_light else "#3B2528",
        "danger_hover": "#FBD5D5" if is_light else "#512D33",
        "danger_pressed": "#F8B4B4" if is_light else "#2D1C20",
        "danger_border": "#F87171" if is_light else "#8D4B55",
        "danger_text": "#991B1B" if is_light else "#FFE9EC",
        "text": c["text_main"],
        "text_soft": c["text_soft"],
        "text_dim": c["text_dim"],
        "canvas_text": "#C8D7EA",
        "border": c["border"],
        "border_strong": c["border_strong"],
        "glow_border": c["glow_border"],
        "scrollbar_track": "#EEF4FA" if is_light else "#0B1424",
        "scrollbar_thumb": c["border_strong"],
        "scrollbar_thumb_hover": "#9FB4C8" if is_light else c["text_dim"],
        "selection": c["selection"],
        "selection_text": c["text_main"],
        "accent": c["accent"],
        "success": c["success"],
        "warning": c["warning"],
        "error": c["error"],
    }


def _now_log_time():
    from datetime import datetime

    return datetime.now().strftime("%H:%M:%S")


class TifWorkbenchWidget(QWidget):
    start_center_requested = Signal()
    agent_requested = Signal(dict)

    def __init__(self, project_manager=None, lang="zh", parent=None, config_manager=None):
        super().__init__(parent)
        self.setObjectName("tifWorkbenchRoot")
        self.project = project_manager or TifProjectManager()
        self.lang = lang
        self.config_manager = config_manager
        parent_theme = getattr(parent, "current_theme", None) if parent is not None else None
        app_theme = QApplication.instance().property("activeTheme") if isinstance(QApplication.instance(), QApplication) else None
        self.current_theme = normalize_theme(parent_theme or app_theme or "dark")
        config = self.config_manager.get("tif_backend", DEFAULT_TIF_BACKEND_CONFIG) if self.config_manager is not None else DEFAULT_TIF_BACKEND_CONFIG
        self.backend_config = sanitize_tif_backend_config(config)
        self.selection_controller = TifSelectionController()
        self.label_edit_service = TifLabelEditService()
        self.truth_promotion_service = TifTruthPromotionService(self.project)
        self.backend_workflow_service = TifBackendWorkflowService(self.project)
        self.roi_part_service = TifRoiPartService()
        self.volume_preview_service = TifVolumePreviewService()
        self.local_axis_service = TifLocalAxisService()
        self.task_manager = TifTaskManager()
        self.task_adapter = TifQtTaskAdapter(self.task_manager)
        self.backend_panel_controller = TifBackendPanelController(self)
        self.local_axis_controller = TifLocalAxisController(self)
        self.preview_controller = TifPreviewController(self)
        self.current_specimen_id = ""
        self.current_volume_scope = "full"
        self.current_part_id = ""
        self.current_part = None
        self.current_reslice_id = ""
        self.local_axis_draft = None
        self._local_axis_endpoint_drag = None
        self._local_axis_pick_target = ""
        self._local_axis_roll_pick_target = ""
        self.part_preview_mask = None
        self.part_mask_preview_bbox = []
        self.part_mask_preview_accepted = False
        self.part_roi_draw_mode = False
        self.part_contour_draw_mode = False
        self.active_part_roi_id = ""
        self.part_roi_keyframes = []
        self.part_mask_keyframes = []
        self.image_volume = None
        self.label_volume = None
        self.part_mask_volume = None
        self._slice_unavailable_override = ""
        self.material_map = {}
        self.material_colors = {}
        self.current_material_id = 0
        self.annotation_tool_mode = "brush"
        self.advanced_annotation_tool_specs = self._advanced_annotation_tool_specs()
        self.edit_volume = None
        self.working_edit_dirty = False
        self._dirty_edit_slices = set()
        self._edit_slice_revisions = {}
        self._edit_revision_counter = 0
        self._annotation_stroke_active = False
        self._annotation_stroke_undo_pushed = False
        self._annotation_stroke_z_index = None
        self._annotation_stroke_last_pixel = None
        self._annotation_stroke_changed = False
        self._loading_specimen = False
        self._saving_working_edit = False
        self._label_auto_save_thread = None
        self._label_auto_save_worker = None
        self._label_auto_save_token = 0
        self._label_auto_save_task_id = ""
        self._label_auto_save_pending_reason = ""
        self._label_auto_save_handled_tokens = set()
        self._label_manual_save_thread = None
        self._label_manual_save_worker = None
        self._label_manual_save_token = 0
        self._label_manual_save_task_id = ""
        self._pending_manual_save_after_auto = None
        self._pending_promote_after_save = None
        self._promote_thread = None
        self._promote_worker = None
        self._promote_request = {}
        self._promote_task_id = ""
        self._tif_import_thread = None
        self._tif_import_worker = None
        self._tif_import_progress = None
        self._tif_import_specimen_id = ""
        self._tif_import_jobs = []
        self._tif_import_task_id = ""
        self._tif_materialize_thread = None
        self._tif_materialize_worker = None
        self._tif_materialize_progress = None
        self._tif_materialize_specimen_id = ""
        self._tif_materialize_task_id = ""
        self._local_axis_reslice_export_thread = None
        self._local_axis_reslice_export_worker = None
        self._local_axis_reslice_export_progress = None
        self._local_axis_reslice_export_context = {}
        self._local_axis_reslice_export_task_id = ""
        self._part_mask_preview_thread = None
        self._part_mask_preview_worker = None
        self._part_mask_preview_progress = None
        self._part_mask_preview_token = 0
        self._part_mask_preview_context = {}
        self._part_mask_preview_task_id = ""
        self._confirm_part_roi_thread = None
        self._confirm_part_roi_worker = None
        self._confirm_part_roi_progress = None
        self._confirm_part_roi_request = {}
        self._confirm_part_roi_task_id = ""
        self._tif_backend_thread = None
        self._tif_backend_worker = None
        self._tif_backend_task_id = ""
        self._tif_backend_action = ""
        self._tif_backend_started_mono = 0.0
        self._tif_backend_run_dir = ""
        self._tif_backend_result_json = ""
        self._tif_backend_last_result = None
        self._tif_backend_pending_selection = {}
        self._pending_backend_action_after_save = None
        self._tif_backend_progress_value = 0
        self._tif_training_result_summary = None
        self._tif_training_result_dialog = None
        self._tif_training_model_output_dir = ""
        self._tif_training_model_manifest = ""
        self._tif_predict_selected_refs = set()
        self._tif_predict_refreshing = False
        self._result_compare_refreshing = False
        self._result_comparison_stale = True
        self._result_region_mask_cache = {}
        self._result_region_mask_cache_key = None
        self.undo_stack = []
        self.redo_stack = []
        self.slice_axis = "z"
        self._slice_positions = {"z": 0, "y": 0, "x": 0}
        self.display_mode = "slice"
        self._volume_preview_cache = OrderedDict()
        self._volume_preview = None
        self._volume_preview_source_shape = ()
        self._volume_roi_preview_bbox = None
        self._volume_roi_preview_source_shape = ()
        self._volume_render_mode = "still"
        self._volume_last_stats = {}
        self._volume_last_preview_build_ms = 0.0
        self._volume_canvas_renderer = "cpu"
        self._volume_renderer_warning = ""
        self._volume_gl_renderer_info = ""
        self._volume_render_scheduled = False
        self._volume_interaction_render_scheduled = False
        self._volume_interaction_render_pending = False
        self._volume_interaction_render_interval_ms = 16
        self._handling_gpu_volume_failure = False
        self._volume_yaw = -35.0
        self._volume_pitch = 20.0
        self._volume_zoom = 1.0
        self._volume_pan_x = 0.0
        self._volume_pan_y = 0.0
        self._volume_mask_preview_cache = OrderedDict()
        self._volume_masked_preview_cache = OrderedDict()
        self._volume_clarity_mode = False
        self._volume_preview_build_thread = None
        self._volume_preview_build_worker = None
        self._volume_preview_build_token = 0
        self._volume_preview_pending_token = 0
        self._volume_preview_build_task_id = ""
        self._volume_preview_pending_key = None
        self._volume_preview_pending_mask_key = None
        self._volume_preview_pending_message = ""
        self._volume_preview_ui_wait_depth = 0
        self._volume_preview_busy_control_states = []

        self.specimen_list = TifSpecimenTree()
        self.specimen_list.setObjectName("tifSpecimenList")
        self.specimen_list.setHeaderHidden(True)
        self.specimen_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.specimen_list.currentItemChanged.connect(self._on_specimen_tree_selected)
        self.specimen_list.customContextMenuRequested.connect(self._on_specimen_tree_context_menu)

        self.canvas = TifSliceCanvas()
        self.canvas.workbench = self
        self.canvas.set_theme(self.current_theme)
        self.volume_canvas = TifVolumeCanvas()
        self.volume_canvas.workbench = self
        self.volume_canvas.set_theme(self.current_theme)
        self.volume_canvas.setProperty("tifVolumeRenderer", "placeholder")
        self._volume_canvas_created = False
        if hasattr(self, "volume_render_status_label"):
            self.volume_render_status_label.setVisible(False)
        self._reset_canvas_view_on_next_render = False
        self.display_mode_combo = WheelSafeComboBox()
        self.display_mode_combo.setObjectName("tifDisplayModeCombo")
        self._populate_display_mode_combo()
        self.display_mode_combo.currentIndexChanged.connect(self.on_display_mode_changed)
        self.slice_slider = WheelSafeSlider(Qt.Horizontal)
        self.slice_slider.setRange(0, 0)
        self.slice_slider.valueChanged.connect(self.on_slice_slider_changed)
        self.slice_prefix_label = QLabel("Slice")
        self.slice_label = QLabel("0 / 0")
        self.slice_axis_combo = WheelSafeComboBox()
        self.slice_axis_combo.setObjectName("tifSliceAxisCombo")
        self._populate_slice_axis_combo()
        self.slice_axis_combo.currentIndexChanged.connect(self.on_slice_axis_changed)

        self.label_role_combo = WheelSafeComboBox()
        self._populate_label_role_combo()
        self.label_role_combo.currentIndexChanged.connect(self._reload_label_volume)
        self.label_role_help_label = QLabel("")
        self.label_role_help_label.setObjectName("tifLayerHelpText")
        self.label_role_help_label.setWordWrap(True)
        self.ai_review_check_title_label = QLabel("AI review check")
        self.ai_review_check_title_label.setObjectName("tifAiReviewCheckTitle")
        self.ai_review_check_label = QLabel("")
        self.ai_review_check_label.setObjectName("tifAiReviewCheckText")
        self.ai_review_check_label.setWordWrap(True)
        self.ai_review_check_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

        self.opacity_slider = WheelSafeSlider(Qt.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(45)
        self.opacity_slider.valueChanged.connect(self.render_current_slice)
        self.brightness_slider = WheelSafeSlider(Qt.Horizontal)
        self.brightness_slider.setRange(-100, 100)
        self.brightness_slider.setValue(0)
        self.brightness_slider.valueChanged.connect(self.render_current_slice)
        self.contrast_slider = WheelSafeSlider(Qt.Horizontal)
        self.contrast_slider.setRange(1, 30)
        self.contrast_slider.setValue(10)
        self.contrast_slider.valueChanged.connect(self.render_current_slice)
        self.volume_cutoff_slider = WheelSafeSlider(Qt.Horizontal)
        self.volume_cutoff_slider.setObjectName("tifVolumeCutoffSlider")
        self.volume_cutoff_slider.setRange(0, 95)
        self.volume_cutoff_slider.setValue(35)
        self.volume_cutoff_slider.valueChanged.connect(self.render_volume_preview)
        self.volume_projection_combo = WheelSafeComboBox()
        self.volume_projection_combo.setObjectName("tifVolumeProjectionCombo")
        self.volume_projection_combo.currentIndexChanged.connect(self._on_volume_projection_changed)
        self.volume_quality_slider = WheelSafeSlider(Qt.Horizontal)
        self.volume_quality_slider.setObjectName("tifVolumeQualitySlider")
        self.volume_quality_slider.setRange(128, GPU_VOLUME_MAX_TEXTURE_DIM)
        self.volume_quality_slider.setValue(1024)
        self.volume_quality_slider.setTracking(False)
        self._volume_quality_committed_value = int(self.volume_quality_slider.value())
        self._volume_quality_drag_pending = False
        self.volume_quality_slider.sliderPressed.connect(self._on_volume_quality_drag_started)
        self.volume_quality_slider.sliderMoved.connect(self._on_volume_quality_drag_moved)
        self.volume_quality_slider.sliderReleased.connect(self._on_volume_quality_released)
        self.volume_sample_slider = WheelSafeSlider(Qt.Horizontal)
        self.volume_sample_slider.setObjectName("tifVolumeSampleSlider")
        self.volume_sample_slider.setRange(256, GPU_VOLUME_MAX_RAY_STEPS)
        self.volume_sample_slider.setValue(1536)
        self.volume_sample_slider.valueChanged.connect(self.render_volume_preview)
        self.volume_clarity_check = QCheckBox("Clarity mode")
        self.volume_clarity_check.setObjectName("tifVolumeClarityCheck")
        self.volume_clarity_check.toggled.connect(self._on_volume_clarity_toggled)
        self.volume_roi_detail_check = QCheckBox("ROI high detail")
        self.volume_roi_detail_check.setObjectName("tifVolumeRoiDetailCheck")
        self.volume_roi_detail_check.setChecked(True)
        self.volume_roi_detail_check.toggled.connect(self._refresh_volume_preview)
        self.volume_roi_source_combo = WheelSafeComboBox()
        self.volume_roi_source_combo.setObjectName("tifVolumeRoiSourceCombo")
        self._populate_volume_roi_source_combo()
        self.volume_roi_source_combo.currentIndexChanged.connect(self._refresh_volume_preview)
        self.volume_roi_inspect_check = QCheckBox("Inspect ROI crop")
        self.volume_roi_inspect_check.setObjectName("tifVolumeRoiInspectCheck")
        self.volume_roi_inspect_check.setChecked(False)
        self.volume_roi_inspect_check.toggled.connect(self._refresh_volume_preview)
        self.volume_roi_scale_slider = WheelSafeSlider(Qt.Horizontal)
        self.volume_roi_scale_slider.setObjectName("tifVolumeRoiScaleSlider")
        self.volume_roi_scale_slider.setRange(100, 300)
        self.volume_roi_scale_slider.setValue(200)
        self.volume_roi_scale_slider.setTracking(False)
        self._volume_roi_scale_committed_value = int(self.volume_roi_scale_slider.value())
        self.volume_roi_scale_slider.sliderPressed.connect(self._on_volume_roi_scale_drag_started)
        self.volume_roi_scale_slider.valueChanged.connect(self._on_volume_roi_scale_changed)
        self.volume_roi_scale_slider.sliderReleased.connect(self._on_volume_roi_scale_released)
        self.volume_roi_budget_combo = WheelSafeComboBox()
        self.volume_roi_budget_combo.setObjectName("tifVolumeRoiBudgetCombo")
        self.volume_roi_budget_combo.addItem("Balanced 1.5 GB", "balanced")
        self.volume_roi_budget_combo.addItem("High 2.5 GB", "high")
        self.volume_roi_budget_combo.currentIndexChanged.connect(self._refresh_volume_preview)
        self.volume_inside_slider = WheelSafeSlider(Qt.Horizontal)
        self.volume_inside_slider.setObjectName("tifVolumeInsideSlider")
        self.volume_inside_slider.setRange(0, 160)
        self.volume_inside_slider.setValue(0)
        self._connect_volume_interaction_slider(self.volume_inside_slider)
        self.volume_clip_slider = WheelSafeSlider(Qt.Horizontal)
        self.volume_clip_slider.setObjectName("tifVolumeClipSlider")
        self.volume_clip_slider.setRange(0, 92)
        self.volume_clip_slider.setValue(0)
        self._connect_volume_interaction_slider(self.volume_clip_slider)
        self.volume_tint_combo = WheelSafeComboBox()
        self.volume_tint_combo.setObjectName("tifVolumeTintCombo")
        self._populate_volume_tint_combo()
        self.volume_tint_combo.currentIndexChanged.connect(self._on_volume_tint_changed)
        self.btn_volume_custom_color = QPushButton("Choose color")
        self.btn_volume_custom_color.setObjectName("tifVolumeCustomColorButton")
        self.btn_volume_custom_color.clicked.connect(self.choose_volume_custom_color)
        self.btn_volume_morphology_preset = QPushButton("Morphology Inspect")
        self.btn_volume_morphology_preset.setObjectName("tifVolumeMorphologyPresetButton")
        self.btn_volume_morphology_preset.clicked.connect(self.apply_morphology_inspect_preset)
        self.volume_transfer_opacity_slider = WheelSafeSlider(Qt.Horizontal)
        self.volume_transfer_opacity_slider.setObjectName("tifVolumeTransferOpacitySlider")
        self.volume_transfer_opacity_slider.setRange(25, 140)
        self.volume_transfer_opacity_slider.setValue(100)
        self._volume_transfer_opacity_drag_pending = False
        self.volume_transfer_opacity_slider.sliderReleased.connect(self._on_volume_transfer_opacity_released)
        self.volume_transfer_opacity_slider.valueChanged.connect(self._on_volume_transfer_opacity_changed)
        self.volume_enhancement_slider = WheelSafeSlider(Qt.Horizontal)
        self.volume_enhancement_slider.setObjectName("tifVolumeEnhancementSlider")
        self.volume_enhancement_slider.setRange(0, 100)
        self.volume_enhancement_slider.setValue(35)
        self.volume_enhancement_slider.valueChanged.connect(self._on_volume_display_enhancement_changed)
        self.volume_tone_slider = WheelSafeSlider(Qt.Horizontal)
        self.volume_tone_slider.setObjectName("tifVolumeToneSlider")
        self.volume_tone_slider.setRange(70, 130)
        self.volume_tone_slider.setValue(100)
        self.volume_tone_slider.valueChanged.connect(self._on_volume_display_enhancement_changed)
        self.volume_shader_quality_combo = WheelSafeComboBox()
        self.volume_shader_quality_combo.setObjectName("tifVolumeShaderQualityCombo")
        self._populate_volume_shader_quality_combo()
        self.volume_shader_quality_combo.currentIndexChanged.connect(self._on_volume_shader_quality_changed)
        self.volume_surface_refine_check = QCheckBox("Surface refine")
        self.volume_surface_refine_check.setObjectName("tifVolumeSurfaceRefineCheck")
        self.volume_surface_refine_check.setChecked(True)
        self.volume_surface_refine_check.toggled.connect(self._on_volume_display_enhancement_changed)
        self.volume_clip_plane_check = QCheckBox("Clip plane")
        self.volume_clip_plane_check.setObjectName("tifVolumeClipPlaneCheck")
        self.volume_clip_plane_check.setChecked(False)
        self.volume_clip_plane_check.toggled.connect(self._on_volume_clip_plane_changed)
        self.volume_local_axes_check = QCheckBox("Show local axes")
        self.volume_local_axes_check.setObjectName("tifVolumeLocalAxesCheck")
        self.volume_local_axes_check.setChecked(False)
        self.volume_local_axes_check.toggled.connect(self.render_volume_preview)
        self.volume_local_axes_check.toggled.connect(self._update_local_axis_summary)
        self.volume_clip_plane_depth_slider = WheelSafeSlider(Qt.Horizontal)
        self.volume_clip_plane_depth_slider.setObjectName("tifVolumeClipPlaneDepthSlider")
        self.volume_clip_plane_depth_slider.setRange(0, 100)
        self.volume_clip_plane_depth_slider.setValue(0)
        self._connect_volume_interaction_slider(self.volume_clip_plane_depth_slider)
        self.volume_clip_plane_depth_label = QLabel("Clip depth")
        self.volume_mask_combo = WheelSafeComboBox()
        self.volume_mask_combo.setObjectName("tifVolumeMaskCombo")
        self._populate_volume_mask_combo()
        self.volume_mask_combo.currentIndexChanged.connect(self._on_volume_mask_changed)
        self.volume_mask_opacity_slider = WheelSafeSlider(Qt.Horizontal)
        self.volume_mask_opacity_slider.setObjectName("tifVolumeMaskOpacitySlider")
        self.volume_mask_opacity_slider.setRange(0, 100)
        self.volume_mask_opacity_slider.setValue(45)
        self.volume_mask_opacity_slider.valueChanged.connect(self.render_volume_preview)
        self.btn_reset_volume_view = QPushButton("Reset 3D view")
        self.btn_reset_volume_view.setObjectName("tifResetVolumeViewButton")
        self.btn_reset_volume_view.clicked.connect(self.reset_volume_view)
        self.volume_render_status_label = QLabel("")
        self.volume_render_status_label.setObjectName("tifVolumeRenderStatus")
        self.volume_render_status_label.setWordWrap(False)
        status_height = max(26, self.volume_render_status_label.fontMetrics().height() + 12)
        self.volume_render_status_label.setMinimumHeight(status_height)
        self.volume_render_status_label.setMaximumHeight(status_height)
        self.volume_render_status_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.volume_render_status_label.setVisible(False)
        self.local_axis_summary_label = QLabel("")
        self.local_axis_summary_label.setObjectName("tifLocalAxisSummaryText")
        self.local_axis_summary_label.setWordWrap(True)
        self.local_axis_summary_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.local_axis_details_check = QCheckBox("Show axis details")
        self.local_axis_details_check.setObjectName("tifLocalAxisDetailsCheck")
        self.local_axis_details_check.setChecked(False)
        self.local_axis_details_check.toggled.connect(self._update_local_axis_summary)
        self.local_axis_details_label = QLabel("")
        self.local_axis_details_label.setObjectName("tifLocalAxisDetailsText")
        self.local_axis_details_label.setWordWrap(True)
        self.local_axis_details_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.local_axis_status_label = QLabel("")
        self.local_axis_status_label.setObjectName("tifLocalAxisStatusText")
        self.local_axis_status_label.setWordWrap(True)
        self.local_axis_status_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

        self.status_label = QLabel("")
        self.status_label.setObjectName("tifStatusText")
        self.status_label.setWordWrap(True)
        self.status_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.metadata_label = QLabel("")
        self.metadata_label.setObjectName("tifMetadataText")
        self.metadata_label.setWordWrap(True)
        self.metadata_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.metadata_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.show_debug_paths_check = QCheckBox("Show debug paths")
        self.show_debug_paths_check.setObjectName("tifShowDebugPathsCheck")
        self.show_debug_paths_check.setChecked(False)
        self.show_debug_paths_check.toggled.connect(self._on_show_debug_paths_toggled)
        self.material_table = QTableWidget(0, 4)
        self.material_table.setObjectName("tifMaterialTable")
        self.material_table.setMinimumHeight(150)
        self.material_table.setMaximumHeight(240)
        self.material_table.setHorizontalHeaderLabels(["", "ID", "Name", "Train"])
        self.material_table.verticalHeader().setVisible(False)
        self.material_table.setShowGrid(False)
        self.material_table.setAlternatingRowColors(True)
        self.material_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.material_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.material_table.horizontalHeader().setStretchLastSection(True)
        self.material_table.itemSelectionChanged.connect(self._on_material_selected)
        self.current_material_swatch = QLabel("")
        self.current_material_swatch.setObjectName("tifCurrentMaterialSwatch")
        self.current_material_swatch.setFixedSize(34, 34)
        self.current_material_swatch.setToolTip("#000000")
        self.current_material_label = QLabel("")
        self.current_material_label.setObjectName("tifCurrentMaterialText")
        self.current_material_label.setWordWrap(True)
        self.current_material_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.btn_add_material = QPushButton("Add material")
        self.btn_add_material.clicked.connect(self.add_material)
        self.btn_edit_material = QPushButton("Edit material")
        self.btn_edit_material.clicked.connect(self.edit_selected_material)
        self.btn_delete_material = QPushButton("Delete material")
        self.btn_delete_material.clicked.connect(self.delete_selected_material)
        self.material_editor_buttons = QWidget()
        self.material_editor_buttons.setObjectName("tifMaterialEditorButtons")

        self.label_schema_combo = WheelSafeComboBox()
        self.label_schema_combo.setObjectName("tifLabelSchemaCombo")
        self.label_schema_combo.currentIndexChanged.connect(self._on_label_schema_selected)
        self.label_schema_id_edit = QLineEdit()
        self.label_schema_id_edit.setObjectName("tifLabelSchemaIdEdit")
        self.label_schema_part_name_edit = QLineEdit()
        self.label_schema_part_name_edit.setObjectName("tifLabelSchemaPartNameEdit")
        self.label_schema_table = QTableWidget(0, 4)
        self.label_schema_table.setObjectName("tifLabelSchemaTable")
        self.label_schema_table.setMinimumHeight(130)
        self.label_schema_table.setMaximumHeight(220)
        self.label_schema_table.setAlternatingRowColors(True)
        self.label_schema_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.label_schema_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.label_schema_table.verticalHeader().setVisible(False)
        self.label_schema_table.setShowGrid(False)
        self.label_schema_table.horizontalHeader().setStretchLastSection(True)
        self.label_schema_table.itemChanged.connect(self._on_label_schema_table_item_changed)
        self.label_schema_table.cellDoubleClicked.connect(self._on_label_schema_table_cell_double_clicked)
        self.btn_new_label_schema = QPushButton("New schema")
        self.btn_new_label_schema.setObjectName("tifNewLabelSchemaButton")
        self.btn_new_label_schema.clicked.connect(self.new_label_schema)
        self.btn_save_label_schema = QPushButton("Save schema")
        self.btn_save_label_schema.setObjectName("tifSaveLabelSchemaButton")
        self.btn_save_label_schema.clicked.connect(self.save_current_label_schema)
        self.btn_bind_label_schema_to_part = QPushButton("Bind to current part")
        self.btn_bind_label_schema_to_part.setObjectName("tifBindLabelSchemaToPartButton")
        self.btn_bind_label_schema_to_part.clicked.connect(self.bind_current_part_label_schema)
        self.btn_add_label_schema_row = QPushButton("Add region label")
        self.btn_add_label_schema_row.setObjectName("tifAddLabelSchemaRowButton")
        self.btn_add_label_schema_row.clicked.connect(self.add_label_schema_row)
        self.btn_remove_label_schema_row = QPushButton("Remove region label")
        self.btn_remove_label_schema_row.setObjectName("tifRemoveLabelSchemaRowButton")
        self.btn_remove_label_schema_row.clicked.connect(self.remove_selected_label_schema_row)
        self.btn_import_label_schema = QPushButton("Import schema")
        self.btn_import_label_schema.setObjectName("tifImportLabelSchemaButton")
        self.btn_import_label_schema.clicked.connect(self.import_label_schema_dialog)
        self.btn_export_label_schema = QPushButton("Export schema")
        self.btn_export_label_schema.setObjectName("tifExportLabelSchemaButton")
        self.btn_export_label_schema.clicked.connect(self.export_label_schema_dialog)

        self.part_user_tag_table = QTableWidget(0, 5)
        self.part_user_tag_table.setObjectName("tifPartUserTagTable")
        self.part_user_tag_table.setMinimumHeight(130)
        self.part_user_tag_table.setMaximumHeight(220)
        self.part_user_tag_table.setAlternatingRowColors(True)
        self.part_user_tag_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.part_user_tag_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.part_user_tag_table.setDragDropMode(QAbstractItemView.InternalMove)
        self.part_user_tag_table.setDragEnabled(True)
        self.part_user_tag_table.setAcceptDrops(True)
        self.part_user_tag_table.setDropIndicatorShown(True)
        self.part_user_tag_table.setDefaultDropAction(Qt.MoveAction)
        self.part_user_tag_table.verticalHeader().setVisible(False)
        self.part_user_tag_table.setShowGrid(False)
        self.part_user_tag_table.horizontalHeader().setStretchLastSection(True)
        self.part_user_tag_table.itemSelectionChanged.connect(self._on_part_user_tag_selected)
        try:
            self.part_user_tag_table.model().rowsMoved.connect(lambda *args: QTimer.singleShot(0, self.save_part_user_tag_order_from_table))
        except Exception:
            pass
        self.part_user_tag_id_edit = QLineEdit()
        self.part_user_tag_id_edit.setObjectName("tifPartUserTagIdEdit")
        self.part_user_tag_label_edit = QLineEdit()
        self.part_user_tag_label_edit.setObjectName("tifPartUserTagLabelEdit")
        self.part_user_tag_color_edit = QLineEdit("#6B8AFD")
        self.part_user_tag_color_edit.setObjectName("tifPartUserTagColorEdit")
        self.part_user_tag_color_swatch = QLabel("")
        self.part_user_tag_color_swatch.setObjectName("tifPartUserTagColorSwatch")
        self.part_user_tag_color_swatch.setFixedSize(34, 26)
        self.part_user_tag_color_edit.textChanged.connect(self._update_part_user_tag_color_swatch)
        self.part_user_tag_color_edit.setVisible(False)
        self._selected_part_user_tag_id_for_edit = ""
        self.btn_choose_part_user_tag_color = QPushButton("Choose group color")
        self.btn_choose_part_user_tag_color.setObjectName("tifChoosePartUserTagColorButton")
        self.btn_choose_part_user_tag_color.clicked.connect(self.choose_part_user_tag_color)
        self.btn_new_part_user_tag = QPushButton("Add group tag")
        self.btn_new_part_user_tag.setObjectName("tifNewPartUserTagButton")
        self.btn_new_part_user_tag.clicked.connect(self.new_part_user_tag)
        self.btn_save_part_user_tag = QPushButton("Save group tag")
        self.btn_save_part_user_tag.setObjectName("tifSavePartUserTagButton")
        self.btn_save_part_user_tag.clicked.connect(self.save_part_user_tag)
        self.btn_delete_part_user_tag = QPushButton("Delete group tag")
        self.btn_delete_part_user_tag.setObjectName("tifDeletePartUserTagButton")
        self.btn_delete_part_user_tag.clicked.connect(self.delete_selected_part_user_tag)
        self.btn_move_part_user_tag_up = QPushButton("Move up")
        self.btn_move_part_user_tag_up.setObjectName("tifMovePartUserTagUpButton")
        self.btn_move_part_user_tag_up.clicked.connect(lambda: self.move_selected_part_user_tag(-1))
        self.btn_move_part_user_tag_down = QPushButton("Move down")
        self.btn_move_part_user_tag_down.setObjectName("tifMovePartUserTagDownButton")
        self.btn_move_part_user_tag_down.clicked.connect(lambda: self.move_selected_part_user_tag(1))
        self.btn_apply_part_user_tags = QPushButton("Apply tags to current part")
        self.btn_apply_part_user_tags.setObjectName("tifApplyPartUserTagsButton")
        self.btn_apply_part_user_tags.clicked.connect(self.apply_part_user_tags_to_current_part)

        self.annotation_tool_label = QLabel("Tool")
        self.current_material_title_label = QLabel("Current label")
        self.btn_tool_brush = QPushButton("Brush")
        self.btn_tool_brush.setObjectName("tifToolBrushButton")
        self.btn_tool_brush.setCheckable(True)
        self.btn_tool_brush.clicked.connect(lambda checked=False: self.set_annotation_tool_mode("brush"))
        self.btn_tool_eraser = QPushButton("Eraser")
        self.btn_tool_eraser.setObjectName("tifToolEraserButton")
        self.btn_tool_eraser.setCheckable(True)
        self.btn_tool_eraser.clicked.connect(lambda checked=False: self.set_annotation_tool_mode("eraser"))
        self.btn_tool_lasso = QPushButton("Lasso fill")
        self.btn_tool_lasso.setObjectName("tifToolLassoButton")
        self.btn_tool_lasso.setCheckable(True)
        self.btn_tool_lasso.clicked.connect(lambda checked=False: self.set_annotation_tool_mode("lasso"))
        self.btn_tool_rectangle = QPushButton("Rectangle fill")
        self.btn_tool_rectangle.setObjectName("tifToolRectangleButton")
        self.btn_tool_rectangle.setCheckable(True)
        self.btn_tool_rectangle.clicked.connect(lambda checked=False: self.set_annotation_tool_mode("rectangle"))
        self.btn_tool_ellipse = QPushButton("Ellipse fill")
        self.btn_tool_ellipse.setObjectName("tifToolEllipseButton")
        self.btn_tool_ellipse.setCheckable(True)
        self.btn_tool_ellipse.clicked.connect(lambda checked=False: self.set_annotation_tool_mode("ellipse"))
        self.btn_interpolate_current_label = QPushButton("Interpolate fill")
        self.btn_interpolate_current_label.setObjectName("tifInterpolateCurrentLabelButton")
        self.btn_interpolate_current_label.clicked.connect(self.interpolate_current_label_between_key_slices)
        self.btn_tool_picker = QPushButton("Picker")
        self.btn_tool_picker.setObjectName("tifToolPickerButton")
        self.btn_tool_picker.setCheckable(True)
        self.btn_tool_picker.clicked.connect(lambda checked=False: self.set_annotation_tool_mode("picker"))
        self.btn_tool_pan = QPushButton("Pan/view")
        self.btn_tool_pan.setObjectName("tifToolPanButton")
        self.btn_tool_pan.setCheckable(True)
        self.btn_tool_pan.clicked.connect(lambda checked=False: self.set_annotation_tool_mode("pan"))

        self.brush_size_slider = WheelSafeSlider(Qt.Horizontal)
        self.brush_size_slider.setRange(1, 80)
        self.brush_size_slider.setValue(8)
        self.brush_size_slider.valueChanged.connect(self._on_brush_size_changed)
        self.btn_undo = QPushButton("Undo")
        self.btn_undo.clicked.connect(self.undo)
        self.btn_redo = QPushButton("Redo")
        self.btn_redo.clicked.connect(self.redo)
        self.btn_save_edit = QPushButton("Save current labels")
        self.btn_save_edit.clicked.connect(self.save_working_edit_async)
        self.auto_save_check = QCheckBox("Auto-save labels")
        self.auto_save_check.setObjectName("tifAutoSaveEditCheck")
        self.auto_save_check.setChecked(True)
        self.auto_save_check.toggled.connect(self._on_auto_save_toggled)
        self.auto_save_hint_label = QLabel("")
        self.auto_save_hint_label.setObjectName("tifAutoSaveHintText")
        self.auto_save_hint_label.setWordWrap(True)
        self.save_status_title_label = QLabel("Save status")
        self.save_status_label = QLabel("")
        self.save_status_label.setObjectName("tifSaveStatusText")
        self.save_status_label.setWordWrap(True)
        self.save_status_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.btn_promote = QPushButton("Accept as training truth")
        self.btn_promote.clicked.connect(self.promote_working_edit)
        self.btn_accept_selected_ai_results = QPushButton("Accept selected AI results")
        self.btn_accept_selected_ai_results.setObjectName("tifAcceptSelectedAiResultsButton")
        self.btn_accept_selected_ai_results.clicked.connect(self.accept_selected_ai_results)
        self.btn_copy_draft = QPushButton("Copy legacy model draft to current labels")
        self.btn_copy_draft.clicked.connect(self.copy_latest_model_draft_to_working_edit)
        self.btn_copy_draft.setVisible(False)
        self.btn_copy_material_prev = QPushButton("Copy label to previous slice")
        self.btn_copy_material_prev.setObjectName("tifCopyMaterialPrevButton")
        self.btn_copy_material_prev.clicked.connect(lambda: self.copy_current_material_to_adjacent_slice(-1))
        self.btn_copy_material_next = QPushButton("Copy label to next slice")
        self.btn_copy_material_next.setObjectName("tifCopyMaterialNextButton")
        self.btn_copy_material_next.clicked.connect(lambda: self.copy_current_material_to_adjacent_slice(1))
        self.btn_clear_current_material = QPushButton("Clear current label")
        self.btn_clear_current_material.setObjectName("tifClearCurrentMaterialButton")
        self.btn_clear_current_material.clicked.connect(self.clear_current_material_on_slice)
        self.btn_import_tif = QPushButton("Import TIF stack")
        self.btn_import_tif.setObjectName("tifImportStackButton")
        self.btn_import_tif.clicked.connect(self.import_tif_stack_dialog)
        self.btn_import_amira = QPushButton("Import AMIRA directory")
        self.btn_import_amira.setObjectName("tifImportAmiraButton")
        self.btn_import_amira.clicked.connect(self.import_amira_directory_dialog)
        self.part_bbox_edit = QLineEdit()
        self.part_bbox_edit.setObjectName("tifPartBboxEdit")
        self.part_bbox_edit.setPlaceholderText("z0,z1,y0,y1,x0,x1")
        self.part_bbox_edit.textChanged.connect(self.render_current_slice)
        self.btn_part_draw_roi = QPushButton("Draw ROI")
        self.btn_part_draw_roi.setObjectName("tifPartDrawRoiButton")
        self.btn_part_draw_roi.setCheckable(True)
        self.btn_part_draw_roi.toggled.connect(self.set_part_roi_draw_mode)
        self.btn_save_part_roi = QPushButton("Save ROI draft")
        self.btn_save_part_roi.setObjectName("tifSavePartRoiButton")
        self.btn_save_part_roi.clicked.connect(self.save_part_roi_draft)
        self.btn_confirm_part_roi = QPushButton("Confirm ROI")
        self.btn_confirm_part_roi.setObjectName("tifConfirmPartRoiButton")
        self.btn_confirm_part_roi.clicked.connect(self.confirm_part_roi_to_part)
        self.btn_cancel_part_roi = QPushButton("Cancel ROI")
        self.btn_cancel_part_roi.setObjectName("tifCancelPartRoiButton")
        self.btn_cancel_part_roi.clicked.connect(self.cancel_part_roi_draft)
        self.btn_create_part = QPushButton("Create part")
        self.btn_create_part.setObjectName("tifCreatePartButton")
        self.btn_create_part.clicked.connect(self.create_part_from_bbox_dialog)
        self.btn_add_rect_keyframe = QPushButton("Add rectangular key slice")
        self.btn_add_rect_keyframe.setObjectName("tifAddRectKeyframeButton")
        self.btn_add_rect_keyframe.clicked.connect(self.add_current_rect_keyframe)
        self.btn_draw_part_contour = QPushButton("Draw contour")
        self.btn_draw_part_contour.setObjectName("tifDrawPartContourButton")
        self.btn_draw_part_contour.setCheckable(True)
        self.btn_draw_part_contour.toggled.connect(self.set_part_contour_draw_mode)
        self.btn_delete_part_contour = QPushButton("Delete key slice")
        self.btn_delete_part_contour.setObjectName("tifDeletePartContourButton")
        self.btn_delete_part_contour.clicked.connect(self.delete_current_part_keyframe)
        self.btn_clear_part_keyframes = QPushButton("Clear key slices")
        self.btn_clear_part_keyframes.setObjectName("tifClearPartKeyframesButton")
        self.btn_clear_part_keyframes.clicked.connect(self.clear_part_mask_keyframes)
        self.btn_prev_key_slice = QPushButton("Previous key slice")
        self.btn_prev_key_slice.setObjectName("tifPrevPartKeySliceButton")
        self.btn_prev_key_slice.clicked.connect(lambda: self.jump_part_keyframe("previous"))
        self.btn_next_key_slice = QPushButton("Next key slice")
        self.btn_next_key_slice.setObjectName("tifNextPartKeySliceButton")
        self.btn_next_key_slice.clicked.connect(lambda: self.jump_part_keyframe("next"))
        self.btn_preview_part_mask = QPushButton("Preview auto fill")
        self.btn_preview_part_mask.setObjectName("tifPreviewPartMaskButton")
        self.btn_preview_part_mask.clicked.connect(self.preview_part_mask_from_keyframes)
        self.btn_accept_part_mask = QPushButton("Accept part mask")
        self.btn_accept_part_mask.setObjectName("tifAcceptPartMaskButton")
        self.btn_accept_part_mask.clicked.connect(self.accept_part_mask_preview)
        self.btn_clear_part_preview = QPushButton("Clear preview")
        self.btn_clear_part_preview.setObjectName("tifClearPartPreviewButton")
        self.btn_clear_part_preview.clicked.connect(self.clear_part_mask_preview)
        self.btn_local_axis_reslice = QPushButton("Export confirmed reslice")
        self.btn_local_axis_reslice.setObjectName("tifLocalAxisResliceButton")
        self.btn_local_axis_reslice.clicked.connect(self.export_current_local_axis_reslice)
        self.btn_copy_source_z_axis = QPushButton("Copy source Z axis")
        self.btn_copy_source_z_axis.setObjectName("tifCopySourceZAxisButton")
        self.btn_copy_source_z_axis.clicked.connect(self.copy_source_z_axis_to_local_axis_draft)
        self.btn_pick_roll_ref_a = QPushButton("Pick roll reference A")
        self.btn_pick_roll_ref_a.setObjectName("tifPickRollReferenceAButton")
        self.btn_pick_roll_ref_a.setCheckable(True)
        self.btn_pick_roll_ref_a.clicked.connect(lambda checked=False: self.set_local_axis_pick_target("roll_a" if checked else ""))
        self.btn_pick_roll_ref_b = QPushButton("Pick roll reference B")
        self.btn_pick_roll_ref_b.setObjectName("tifPickRollReferenceBButton")
        self.btn_pick_roll_ref_b.setCheckable(True)
        self.btn_pick_roll_ref_b.clicked.connect(lambda checked=False: self.set_local_axis_pick_target("roll_b" if checked else ""))
        self.btn_pick_roll_ref_c = QPushButton("Pick plane reference C")
        self.btn_pick_roll_ref_c.setObjectName("tifPickPlaneReferenceCButton")
        self.btn_pick_roll_ref_c.setCheckable(True)
        self.btn_pick_roll_ref_c.clicked.connect(lambda checked=False: self.set_local_axis_pick_target("roll_c" if checked else ""))
        self.btn_align_axis_to_reference_plane = QPushButton("Make Z perpendicular\nto A/B/C plane")
        self.btn_align_axis_to_reference_plane.setObjectName("tifAlignAxisToReferencePlaneButton")
        self.btn_align_axis_to_reference_plane.clicked.connect(self.align_local_axis_to_reference_plane)
        self.btn_clear_roll_refs = QPushButton("Clear roll refs")
        self.btn_clear_roll_refs.setObjectName("tifClearRollRefsButton")
        self.btn_clear_roll_refs.clicked.connect(self.clear_local_axis_roll_references)
        self.btn_clear_local_axis_draft = QPushButton("Clear axis draft")
        self.btn_clear_local_axis_draft.setObjectName("tifClearLocalAxisDraftButton")
        self.btn_clear_local_axis_draft.clicked.connect(self.clear_local_axis_draft)
        self.local_axis_trainable_check = QCheckBox("Record this export as trainable local-axis data")
        self.local_axis_trainable_check.setObjectName("tifLocalAxisTrainableCheck")
        self.local_axis_trainable_check.setChecked(True)
        self.btn_export_local_axis_training_manifest = QPushButton("Export Local Axis training manifest")
        self.btn_export_local_axis_training_manifest.setObjectName("tifExportLocalAxisTrainingManifestButton")
        self.btn_export_local_axis_training_manifest.clicked.connect(self.export_local_axis_training_manifest_dialog)
        self.btn_export_part_package = QPushButton("Export part package")
        self.btn_export_part_package.setObjectName("tifExportPartPackageButton")
        self.btn_export_part_package.clicked.connect(self.export_current_part_package)
        self.btn_delete_part_volume = QPushButton("Delete part volume")
        self.btn_delete_part_volume.setObjectName("tifDeletePartVolumeButton")
        self.btn_delete_part_volume.clicked.connect(self.delete_current_part_volume)
        self.btn_export_training = QPushButton("Export train-ready volumes")
        self.btn_export_training.setObjectName("tifExportTrainingButton")
        self.btn_export_training.clicked.connect(self.export_training_dataset)
        self.backend_id_edit = QLineEdit()
        self.backend_id_edit.setObjectName("tifBackendIdEdit")
        self.backend_display_edit = QLineEdit()
        self.backend_python_edit = QLineEdit()
        self.backend_formats_edit = QLineEdit()
        self.backend_prepare_edit = QLineEdit()
        self.backend_train_edit = QLineEdit()
        self.backend_predict_edit = QLineEdit()
        self.backend_manifest_edit = QLineEdit()
        self.backend_manifest_edit.textChanged.connect(self._on_predict_manifest_text_changed)
        self.btn_browse_model_manifest = QPushButton("Browse manifest")
        self.btn_browse_model_manifest.setObjectName("tifBrowseModelManifestButton")
        self.btn_browse_model_manifest.clicked.connect(self.browse_model_manifest)
        self.btn_use_nnunet_backend_preset = QPushButton("Use nnU-Net v2 preset")
        self.btn_use_nnunet_backend_preset.setObjectName("tifUseNnunetV2PresetButton")
        self.btn_use_nnunet_backend_preset.clicked.connect(self.apply_nnunet_v2_backend_preset)
        self.btn_save_backend = QPushButton("Save backend settings")
        self.btn_save_backend.setObjectName("tifSaveBackendButton")
        self.btn_save_backend.clicked.connect(self.save_backend_settings)
        self.btn_prepare_dataset = QPushButton("Prepare dataset")
        self.btn_prepare_dataset.setObjectName("tifPrepareDatasetButton")
        self.btn_prepare_dataset.clicked.connect(lambda: self.run_backend_action("prepare_dataset"))
        self.btn_train_backend = QPushButton("Train backend")
        self.btn_train_backend.setObjectName("tifTrainBackendButton")
        self.btn_train_backend.clicked.connect(lambda: self.run_backend_action("train"))
        self.btn_import_prediction = QPushButton("Import prediction")
        self.btn_import_prediction.setObjectName("tifImportPredictionButton")
        self.btn_import_prediction.clicked.connect(lambda: self.run_backend_action("predict"))
        self.predict_filter_combo = WheelSafeComboBox()
        self.predict_filter_combo.setObjectName("tifPredictFilterCombo")
        self.predict_filter_combo.currentIndexChanged.connect(self.refresh_predict_targets)
        self.predict_targets_table = QTableWidget(0, 8)
        self.predict_targets_table.setObjectName("tifPredictTargetsTable")
        self.predict_targets_table.setMinimumHeight(150)
        self.predict_targets_table.setMaximumHeight(260)
        self.predict_targets_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.predict_targets_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.predict_targets_table.setAlternatingRowColors(True)
        self.predict_targets_table.verticalHeader().setVisible(False)
        self.predict_targets_table.setShowGrid(False)
        self.predict_targets_table.horizontalHeader().setStretchLastSection(True)
        self.predict_targets_table.itemChanged.connect(self._on_predict_target_item_changed)
        self.btn_refresh_predict_targets = QPushButton("Refresh targets")
        self.btn_refresh_predict_targets.setObjectName("tifRefreshPredictTargetsButton")
        self.btn_refresh_predict_targets.clicked.connect(self.refresh_predict_targets)
        self.btn_select_current_predict_target = QPushButton("Select current part")
        self.btn_select_current_predict_target.setObjectName("tifSelectCurrentPredictTargetButton")
        self.btn_select_current_predict_target.clicked.connect(self.select_current_predict_target)
        self.btn_select_ready_predict_targets = QPushButton("Select all ready")
        self.btn_select_ready_predict_targets.setObjectName("tifSelectReadyPredictTargetsButton")
        self.btn_select_ready_predict_targets.clicked.connect(self.select_all_ready_predict_targets)
        self.btn_clear_predict_targets = QPushButton("Clear selection")
        self.btn_clear_predict_targets.setObjectName("tifClearPredictTargetsButton")
        self.btn_clear_predict_targets.clicked.connect(self.clear_predict_target_selection)
        self.predict_targets_summary_label = QLabel("")
        self.predict_targets_summary_label.setObjectName("tifPredictTargetsSummaryText")
        self.predict_targets_summary_label.setWordWrap(True)
        self.predict_targets_summary_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.btn_stop_backend = QPushButton("Stop run")
        self.btn_stop_backend.setObjectName("tifStopBackendButton")
        self.btn_stop_backend.clicked.connect(self.cancel_backend_action)
        self.btn_stop_backend.setEnabled(False)
        self.btn_open_backend_run = QPushButton("Open run folder")
        self.btn_open_backend_run.setObjectName("tifOpenBackendRunButton")
        self.btn_open_backend_run.clicked.connect(self.open_latest_backend_run_folder)
        self.btn_open_backend_run.setEnabled(False)
        self.btn_open_backend_result = QPushButton("Open result JSON")
        self.btn_open_backend_result.setObjectName("tifOpenBackendResultButton")
        self.btn_open_backend_result.clicked.connect(self.open_latest_backend_result_json)
        self.btn_open_backend_result.setEnabled(False)
        self.training_result_summary_label = QLabel("No training result yet.")
        self.training_result_summary_label.setObjectName("tifTrainingResultSummaryText")
        self.training_result_summary_label.setWordWrap(True)
        self.training_result_summary_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.training_result_summary_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.btn_show_training_result_summary = QPushButton("Show result summary")
        self.btn_show_training_result_summary.setObjectName("tifShowTrainingResultSummaryButton")
        self.btn_show_training_result_summary.clicked.connect(self.show_latest_training_result_summary)
        self.btn_show_training_result_summary.setEnabled(False)
        self.btn_open_training_model_output = QPushButton("Open model output")
        self.btn_open_training_model_output.setObjectName("tifOpenTrainingModelOutputButton")
        self.btn_open_training_model_output.clicked.connect(self.open_latest_training_model_output)
        self.btn_open_training_model_output.setEnabled(False)
        self.btn_open_training_model_manifest = QPushButton("Open model manifest")
        self.btn_open_training_model_manifest.setObjectName("tifOpenTrainingModelManifestButton")
        self.btn_open_training_model_manifest.clicked.connect(self.open_latest_training_model_manifest)
        self.btn_open_training_model_manifest.setEnabled(False)
        self.btn_batch_predict_entry = QPushButton("Enter batch prediction")
        self.btn_batch_predict_entry.setObjectName("tifBatchPredictEntryButton")
        self.btn_batch_predict_entry.clicked.connect(self.enter_batch_prediction_from_training_result)
        self.btn_batch_predict_entry.setEnabled(False)
        self.model_library_combo = WheelSafeComboBox()
        self.model_library_combo.setObjectName("tifModelLibraryCombo")
        self.model_library_combo.currentIndexChanged.connect(self._on_model_library_selection_changed)
        self.model_library_notes_edit = QTextEdit()
        self.model_library_notes_edit.setObjectName("tifModelLibraryNotesEdit")
        self.model_library_notes_edit.setPlaceholderText("Model notes")
        self.model_library_notes_edit.setMinimumHeight(58)
        self.model_library_notes_edit.setMaximumHeight(86)
        self.model_library_notes_edit.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.model_library_summary_label = QLabel("")
        self.model_library_summary_label.setObjectName("tifModelLibrarySummaryText")
        self.model_library_summary_label.setWordWrap(True)
        self.model_library_summary_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.btn_use_selected_tif_model = QPushButton("Use selected model")
        self.btn_use_selected_tif_model.setObjectName("tifUseSelectedModelButton")
        self.btn_use_selected_tif_model.clicked.connect(self.use_selected_tif_model)
        self.btn_save_tif_model_notes = QPushButton("Save notes")
        self.btn_save_tif_model_notes.setObjectName("tifSaveModelNotesButton")
        self.btn_save_tif_model_notes.clicked.connect(self.save_selected_tif_model_notes)
        self.btn_delete_tif_model_record = QPushButton("Delete registration")
        self.btn_delete_tif_model_record.setObjectName("tifDeleteModelRecordButton")
        self.btn_delete_tif_model_record.clicked.connect(self.delete_selected_tif_model_record)
        self.btn_import_external_prediction_tif = QPushButton("Import external label TIF as review result")
        self.btn_import_external_prediction_tif.setObjectName("tifImportExternalPredictionTifButton")
        self.btn_import_external_prediction_tif.clicked.connect(self.import_external_prediction_tif_dialog)
        self.result_source_manual_radio = QRadioButton("manual_truth")
        self.result_source_manual_radio.setObjectName("tifResultSourceManualTruthRadio")
        self.result_source_manual_radio.setChecked(True)
        self.result_source_editable_radio = QRadioButton("editable_ai_result")
        self.result_source_editable_radio.setObjectName("tifResultSourceEditableAiRadio")
        self.result_region_combo = WheelSafeComboBox()
        self.result_region_combo.setObjectName("tifResultRegionCombo")
        self.result_region_combo.currentIndexChanged.connect(self._on_result_comparison_controls_changed)
        self.result_source_manual_radio.toggled.connect(self._on_result_comparison_controls_changed)
        self.result_source_editable_radio.toggled.connect(self._on_result_comparison_controls_changed)
        self.result_compare_table = QTableWidget(0, 8)
        self.result_compare_table.setObjectName("tifResultComparisonTable")
        self.result_compare_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.result_compare_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.result_compare_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.result_compare_table.setAlternatingRowColors(True)
        self.result_compare_table.setShowGrid(False)
        self.result_compare_table.horizontalHeader().setStretchLastSection(True)
        self.btn_refresh_result_comparison = QPushButton("Refresh comparison")
        self.btn_refresh_result_comparison.setObjectName("tifRefreshResultComparisonButton")
        self.btn_refresh_result_comparison.clicked.connect(self.refresh_result_comparison)
        self.btn_open_result_comparison_target = QPushButton("Open selected in 3D")
        self.btn_open_result_comparison_target.setObjectName("tifOpenResultComparisonTargetButton")
        self.btn_open_result_comparison_target.clicked.connect(self.open_selected_result_comparison_target)
        self.btn_show_result_region_in_3d = QPushButton("Highlight selected region")
        self.btn_show_result_region_in_3d.setObjectName("tifShowResultRegionIn3DButton")
        self.btn_show_result_region_in_3d.clicked.connect(self.show_selected_result_region_in_3d)
        self.result_compare_summary_label = QLabel("")
        self.result_compare_summary_label.setObjectName("tifResultComparisonSummaryText")
        self.result_compare_summary_label.setWordWrap(True)
        self.result_compare_summary_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.btn_export_current_rendering = QPushButton("Export current rendering screenshot")
        self.btn_export_current_rendering.setObjectName("tifExportCurrentRenderingButton")
        self.btn_export_current_rendering.clicked.connect(self.export_current_rendering_screenshot)
        self.btn_start_center = QPushButton("Start Center")
        self.btn_start_center.setObjectName("tifStartCenterButton")
        self.btn_start_center.clicked.connect(self.start_center_requested.emit)
        self.btn_ask_agent = QPushButton("Ask Agent")
        self.btn_ask_agent.setObjectName("tifAskAgentButton")
        self.btn_ask_agent.clicked.connect(lambda: self.agent_requested.emit(self.get_agent_context()))
        self.btn_show_workbench_log = QPushButton("Workbench log")
        self.btn_show_workbench_log.setObjectName("tifShowWorkbenchLogButton")
        self.btn_show_workbench_log.clicked.connect(self.show_workbench_log)
        self.operation_status_label = QLabel("")
        self.operation_status_label.setObjectName("tifOperationStatusText")
        self.operation_status_label.setWordWrap(True)
        self.operation_status_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.training_status_label = MirroredStatusLabel("")
        self.training_status_label.setObjectName("tifTrainingStatusText")
        self.training_status_label.setWordWrap(True)
        self.training_status_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.training_status_label.set_mirror_label(self.operation_status_label)
        self.backend_run_status_label = QLabel("Idle")
        self.backend_run_status_label.setObjectName("tifBackendRunStatusText")
        self.backend_run_status_label.setWordWrap(True)
        self.backend_run_status_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.backend_run_status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.backend_run_title_label = QLabel("Backend run")
        self.backend_run_title_label.setObjectName("tifSectionTitle")
        self.backend_elapsed_label = QLabel("Elapsed: 00:00")
        self.backend_elapsed_label.setObjectName("tifBackendElapsedText")
        self.backend_progress_bar = QProgressBar()
        self.backend_progress_bar.setObjectName("tifBackendProgressBar")
        self.backend_progress_bar.setRange(0, 100)
        self.backend_progress_bar.setValue(0)
        self.backend_progress_bar.setTextVisible(True)
        self.backend_progress_bar.setFormat("%p%")
        self.backend_log_tail = QTextEdit()
        self.backend_log_tail.setObjectName("tifBackendLogTail")
        self.backend_log_tail.setReadOnly(True)
        self.backend_log_tail.setLineWrapMode(QTextEdit.WidgetWidth)
        self.backend_log_tail.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.backend_log_tail.setMinimumHeight(92)
        self.backend_log_tail.setMaximumHeight(132)
        self.backend_elapsed_timer = QTimer(self)
        self.backend_elapsed_timer.setInterval(1000)
        self.backend_elapsed_timer.timeout.connect(self._update_backend_elapsed_label)
        self.log_console = QTextEdit()
        self.log_console.setObjectName("tifLogConsole")
        self.log_console.setReadOnly(True)
        self.log_console.setMinimumHeight(90)
        self.log_console.setMaximumHeight(140)
        self.shortcut_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.shortcut_undo.activated.connect(self.undo)
        self.shortcut_redo = QShortcut(QKeySequence("Ctrl+Y"), self)
        self.shortcut_redo.activated.connect(self.redo)
        self.shortcut_redo_alt = QShortcut(QKeySequence("Ctrl+Shift+Z"), self)
        self.shortcut_redo_alt.activated.connect(self.redo)
        self.shortcut_save_edit = QShortcut(QKeySequence("Ctrl+S"), self)
        self.shortcut_save_edit.activated.connect(self.save_working_edit_async)
        self.shortcut_tool_brush = QShortcut(QKeySequence("B"), self)
        self.shortcut_tool_brush.activated.connect(lambda: self.set_annotation_tool_mode("brush"))
        self.shortcut_tool_eraser = QShortcut(QKeySequence("E"), self)
        self.shortcut_tool_eraser.activated.connect(lambda: self.set_annotation_tool_mode("eraser"))
        self.shortcut_tool_lasso = QShortcut(QKeySequence("L"), self)
        self.shortcut_tool_lasso.activated.connect(lambda: self.set_annotation_tool_mode("lasso"))
        self.shortcut_tool_rectangle = QShortcut(QKeySequence("R"), self)
        self.shortcut_tool_rectangle.activated.connect(lambda: self.set_annotation_tool_mode("rectangle"))
        self.shortcut_tool_ellipse = QShortcut(QKeySequence("O"), self)
        self.shortcut_tool_ellipse.activated.connect(lambda: self.set_annotation_tool_mode("ellipse"))
        self.shortcut_tool_picker = QShortcut(QKeySequence("I"), self)
        self.shortcut_tool_picker.activated.connect(lambda: self.set_annotation_tool_mode("picker"))
        self.shortcut_brush_smaller = QShortcut(QKeySequence("["), self)
        self.shortcut_brush_smaller.activated.connect(lambda: self.adjust_brush_size(-1))
        self.shortcut_brush_larger = QShortcut(QKeySequence("]"), self)
        self.shortcut_brush_larger.activated.connect(lambda: self.adjust_brush_size(1))
        self.auto_save_timer = QTimer(self)
        self.auto_save_timer.setSingleShot(True)
        self.auto_save_timer.setInterval(1200)
        self.auto_save_timer.timeout.connect(lambda: self.save_working_edit(show_message=True, reason="auto_save"))
        self.volume_still_timer = QTimer(self)
        self.volume_still_timer.setSingleShot(True)
        self.volume_still_timer.setInterval(220)
        self.volume_still_timer.timeout.connect(self._finish_volume_interaction)

        self._apply_button_roles()
        self._build_layout()
        self._apply_soft_style()
        self._load_backend_config_into_ui()
        self._sync_annotation_tool_buttons()
        self._update_current_material_summary()
        self._sync_undo_redo_buttons()
        self._update_save_status()
        self._update_texts()
        self._sync_mode_sections()
        self.refresh_project()

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
        current = self.display_mode_combo.currentData() if self.display_mode_combo.count() else self.display_mode
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
        if self.current_volume_scope == "full" and self._active_part_mask_likely_available():
            return "masked_image"
        configured = (self._active_volume_view_settings() or {}).get("volume_mask_mode", "")
        if configured in {"image_only", "mask_boundary", "masked_image"}:
            if configured == "image_only" or self._active_part_mask_likely_available():
                return configured
        if self.current_volume_scope == "part" and self._active_part_mask_likely_available():
            return "masked_image"
        return "image_only"

    def _apply_default_volume_mask_mode(self):
        if self._set_volume_mask_mode(self._default_volume_mask_mode()):
            self._clear_volume_mask_caches(owner=self._active_volume_cache_owner())
            self._reset_active_volume_preview_state()

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
            self.training_status_label.setText(self._volume_renderer_status_message())
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
        self._update_current_material_summary()
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
        self.btn_export_local_axis_training_manifest.setText(tt("Export Local Axis training manifest", self.lang))
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
        self._sync_material_editor_scope()
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
            self._populate_tif_model_library_combo()
        self._refresh_training_result_controls()
        self.refresh_predict_targets()
        if not self._backend_action_running():
            self.backend_run_status_label.setText(tt("Idle", self.lang))
            self.backend_elapsed_label.setText(tt("Elapsed: 00:00", self.lang))
        self.btn_import_external_prediction_tif.setText(tt("Import external label TIF as review result", self.lang))
        self.btn_refresh_result_comparison.setText(tt("Refresh comparison", self.lang))
        self.btn_open_result_comparison_target.setText(tt("Open selected in 3D", self.lang))
        self.btn_show_result_region_in_3d.setText(tt("Highlight selected region", self.lang))
        self._refresh_result_comparison_if_visible()
        self.btn_start_center.setText(tt("Start Center", self.lang))
        self.btn_ask_agent.setText(tt("Ask Agent", self.lang))
        self.material_table.setHorizontalHeaderLabels(
            ["", tt("ID", self.lang), tt("Name", self.lang), tt("Train", self.lang)]
        )
        self._update_local_axis_summary()

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
        selected_material = self._selected_material()
        material_id = ""
        if isinstance(selected_material, dict):
            material_id = selected_material.get("id", "")
        recent_log = ""
        if hasattr(self, "log_console"):
            recent_log = "\n".join(self.log_console.toPlainText().splitlines()[-6:])

        source_shape, spacing_zyx = self._volume_source_geometry()
        active_label_role = self.label_role_combo.currentData() or ""
        active_label_volume = self.label_volume
        if active_label_role == "working_edit" and self.edit_volume is not None:
            active_label_volume = self.edit_volume
        label_shape = tuple(int(value) for value in getattr(active_label_volume, "shape", ()) or ())
        axis = self._current_slice_axis()
        slice_position = ""
        if self.image_volume is not None:
            slice_position = f"{int(self.slice_slider.value()) + 1}/{self._slice_count_for_axis(axis)}"

        readiness_text = ""
        readiness_reasons = ""
        if self.current_specimen_id and self.current_volume_scope == "part" and self.current_part_id:
            try:
                readiness = self.project.evaluate_part_train_ready(
                    self.current_specimen_id,
                    self.current_part_id,
                    self.current_reslice_id,
                    validate_label_ids=False,
                )
            except Exception:
                readiness = {}
            if readiness:
                readiness_text = "yes" if readiness.get("train_ready") else "no"
                readiness_reasons = ",".join(str(item) for item in readiness.get("reasons", []) if str(item))
        elif self.current_specimen_id:
            try:
                readiness = self.project.evaluate_train_ready(self.current_specimen_id)
            except Exception:
                readiness = {}
            if readiness:
                readiness_text = "yes" if readiness.get("train_ready") else "no"
                readiness_reasons = ",".join(str(item) for item in readiness.get("reasons", []) if str(item))

        def triplet_text(values):
            values = tuple(values or ())
            if len(values) != 3:
                return ""
            return f"{values[0]}/{values[1]}/{values[2]}"

        clarity = "on" if bool(getattr(self, "_volume_clarity_mode", False)) else "off"
        volume_status = ""
        if self.image_volume is not None:
            volume_status = self.volume_canvas_overlay_text()
        volume_perf = self.volume_performance_report() if self.image_volume is not None else {}
        backend_config = self._backend_config_from_ui()
        train_ready_part_refs = []
        train_ready_top_level_count = 0
        if self.project is not None:
            try:
                train_ready_part_refs = self._train_ready_part_refs()
            except Exception:
                train_ready_part_refs = []
            try:
                train_ready_top_level_count = len(self.project.list_train_ready_specimens())
            except Exception:
                train_ready_top_level_count = 0
        if train_ready_part_refs:
            training_scope = "part_reslice"
        elif train_ready_top_level_count:
            training_scope = "top_level_volume"
        else:
            training_scope = ""
        selected_model_record = self._selected_tif_model_record() if hasattr(self, "model_library_combo") else None
        selected_model_manifest = ""
        selected_model_id = ""
        if selected_model_record:
            selected_model_id = self._tif_model_record_id(selected_model_record)
            selected_model_manifest = self.project.to_absolute(selected_model_record.get("model_manifest", ""))
        elif hasattr(self, "backend_manifest_edit"):
            selected_model_manifest = str(self.backend_manifest_edit.text() or "").strip()
        model_count = 0
        try:
            model_count = len(self._tif_model_records())
        except Exception:
            model_count = 0
        command_presence = {
            "prepare_dataset": bool(str(backend_config.get("prepare_dataset_command") or "").strip()),
            "train": bool(str(backend_config.get("train_command") or "").strip()),
            "predict": bool(str(backend_config.get("predict_command") or "").strip()),
        }

        return {
            "source_workbench": "tif_volume",
            "project_type": "tif_volume",
            "project_path": getattr(self.project, "current_project_path", "") or "",
            "active_specimen_id": self.current_specimen_id,
            "active_volume_scope": self.current_volume_scope,
            "active_part_id": self.current_part_id,
            "active_part_parent_bbox_zyx": str((self.current_part or {}).get("parent_bbox_zyx", "")),
            "active_label_role": active_label_role,
            "selected_material_id": material_id,
            "display_mode": self.display_mode,
            "active_slice_axis": axis,
            "active_slice_position": slice_position,
            "active_volume_shape_zyx": triplet_text(source_shape),
            "active_volume_spacing_zyx": triplet_text(spacing_zyx),
            "active_label_shape_zyx": triplet_text(label_shape),
            "train_ready_status": readiness_text,
            "train_ready_reasons": readiness_reasons,
            "active_label_schema_id": self._active_part_label_schema_id(),
            "train_ready_part_sample_count": str(len(train_ready_part_refs)),
            "train_ready_top_level_sample_count": str(train_ready_top_level_count),
            "training_selection_scope": training_scope,
            "training_sample_rule": "prepare/train uses all project train-ready part/reslice manual_truth samples; if none exist, it falls back to train-ready top-level specimen volumes. A label schema alone is not enough.",
            "registered_tif_model_count": str(model_count),
            "selected_tif_model_id": selected_model_id,
            "selected_model_manifest": selected_model_manifest,
            "tif_backend_id": str(backend_config.get("backend_id") or ""),
            "tif_backend_python": str(backend_config.get("python_executable") or ""),
            "tif_backend_command_presence": str(command_presence),
            "backend_run_active": "yes" if self._backend_action_running() else "no",
            "backend_action": str(self._tif_backend_action or ""),
            "backend_run_dir": str(self._tif_backend_run_dir or ""),
            "backend_result_json": str(self._tif_backend_result_json or ""),
            "tif_task_summary": str(self._task_summary_for_context()),
            "tif_state_summary": str(self._current_state_summary()),
            "volume_renderer": self._volume_canvas_renderer,
            "volume_renderer_label": self._volume_renderer_label(),
            "volume_render_mode": self._volume_render_mode,
            "volume_projection_mode": self._volume_projection_mode(),
            "volume_mask_mode": self._volume_mask_mode(),
            "volume_density_cutoff": f"{int(self.volume_cutoff_slider.value())}%",
            "volume_density_opacity": f"{int(self.volume_transfer_opacity_slider.value())}%",
            "volume_texture_target_dim": str(self._active_volume_target_dim()),
            "volume_ray_samples": str(self._active_volume_sample_count()),
            "volume_clarity_mode": clarity,
            "volume_detail_enhancement": f"{int(self.volume_enhancement_slider.value())}%",
            "volume_tone_curve": f"{int(self.volume_tone_slider.value())}%",
            "volume_shader_quality": self._volume_shader_quality_mode(),
            "volume_surface_refine": "on" if self.volume_surface_refine_check.isChecked() else "off",
            "volume_clip_plane": "on" if self.volume_clip_plane_check.isChecked() else "off",
            "volume_clip_plane_depth": f"{int(self.volume_clip_plane_depth_slider.value())}%",
            "volume_roi_high_detail": "on" if self.volume_roi_detail_check.isChecked() else "off",
            "volume_roi_inspect": "on" if self._volume_roi_inspect_enabled() else "off",
            "volume_roi_scale": f"{self._active_volume_roi_scale():.1f}x",
            "volume_roi_budget": f"{self._roi_texture_budget_bytes() / (1024.0 ** 3):.1f} GB",
            "volume_inside_depth": f"{int(self.volume_inside_slider.value())}%",
            "volume_front_cut": f"{int(self.volume_clip_slider.value())}%",
            "volume_zoom": f"{int(round(float(self._volume_zoom) * 100))}%",
            "volume_pan": f"x={int(round(float(self._volume_pan_x) * 100))}%, y={int(round(float(self._volume_pan_y) * 100))}%",
            "volume_yaw_pitch": f"yaw={float(self._volume_yaw):.1f}, pitch={float(self._volume_pitch):.1f}",
            "volume_gpu_warning": self._volume_renderer_warning,
            "volume_status_overlay": volume_status,
            "volume_performance_diagnosis": str(volume_perf.get("diagnosis", "")),
            "volume_uploaded_gb": f"{float(volume_perf.get('uploaded_gb', 0.0)):.2f}",
            "volume_upload_ms": f"{float(volume_perf.get('upload_ms', 0.0)):.0f}",
            "volume_draw_ms": f"{float(volume_perf.get('draw_ms', 0.0)):.1f}",
            "volume_uploaded_shape_zyx": triplet_text(volume_perf.get("preview_shape_zyx", ())),
            "volume_texture_sampling": str((getattr(self, "_volume_last_stats", {}) or {}).get("texture_filter", "")),
            "volume_display_scaling": str((getattr(self, "_volume_last_stats", {}) or {}).get("display_scaling", "")),
            "tif_next_requirement": "annotation_training_loop: bind a label schema, select label IDs before brush editing, save reviewed editable_ai_result/manual labels, accept manual_truth, mark samples train-ready, then prepare/train/predict through the TIF backend.",
            "tif_requirement_doc": "docs/designs/2026-07-04_TIF训练回环与切片预览模式隔离设计稿.md; docs/designs/2026-07-04_TIF脑分区训练回环执行清单.md",
            "recent_log_excerpt": recent_log,
        }

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

    def _on_predict_manifest_text_changed(self, text):
        self.backend_config["model_manifest"] = str(text or "").strip()

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

    def _schema_materials_for_part(self, part=None):
        part = part if isinstance(part, dict) else self.current_part
        schema_id = str(((part or {}).get("training") or {}).get("label_schema_id") or "")
        schema = self.project.get_label_schema(schema_id, default=None) if schema_id else None
        labels = (schema or {}).get("labels") or []
        if not labels:
            return []
        materials = [
            {"id": 0, "name": "background", "display_name": tt("Background / erase target", self.lang), "color": "#000000", "trainable": False}
        ]
        for item in labels:
            try:
                label_id = int(item.get("id", 0))
            except (TypeError, ValueError):
                continue
            if label_id <= 0:
                continue
            materials.append(
                {
                    "id": label_id,
                    "name": str(item.get("name") or f"label_{label_id}"),
                    "display_name": str(item.get("display_name") or item.get("name") or f"Label {label_id}"),
                    "color": str(item.get("color") or "#F94144"),
                    "trainable": bool(item.get("trainable", True)),
                    "source_name": str(item.get("display_name") or item.get("name") or f"Label {label_id}"),
                }
            )
        return materials

    def _active_materials(self):
        if self.current_volume_scope == "part":
            schema_materials = self._schema_materials_for_part()
            if schema_materials:
                return schema_materials
        return self.material_map.get("materials", []) if isinstance(self.material_map, dict) else []

    def _sync_material_editor_scope(self):
        is_part = self.current_volume_scope == "part"
        if hasattr(self, "material_editor_buttons"):
            self.material_editor_buttons.setVisible(not is_part)
        if hasattr(self, "material_help_label"):
            message = (
                "Current labels are for selecting the label written by brush/fill tools. For project part volumes and reslices, create or edit labels in the bound schema above."
                if is_part
                else "After binding a label schema, select one current label here before using the brush or fill tools."
            )
            self.material_help_label.setText(tt(message, self.lang))
        if hasattr(self, "material_scope_help_label"):
            self.material_scope_help_label.setText(
                tt(
                    "Label IDs are the numeric labels stored in the current volume. For project part volumes and their reslices, this list follows the bound region label schema; for top-level imported volumes, it is the specimen label map.",
                    self.lang,
                )
            )

    def _sync_material_colors_from_active_source(self):
        self.material_colors = {
            int(item["id"]): QColor(str(item.get("color", "#000000")))
            for item in self._active_materials()
            if isinstance(item, dict) and str(item.get("id", "")).strip() != ""
        }

    def _refresh_active_part_material_schema(self):
        self._sync_material_editor_scope()
        self._sync_material_colors_from_active_source()
        self._populate_material_table()
        self._update_current_material_summary()
        if self.image_volume is not None:
            self.render_current_slice()

    def _populate_label_schema_combo(self, preferred_id=None):
        combo = getattr(self, "label_schema_combo", None)
        if combo is None:
            return
        current = str(preferred_id if preferred_id is not None else (combo.currentData() if combo.count() else self._active_part_label_schema_id()) or "")
        if not current:
            current = self._active_part_label_schema_id()
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
        self._refresh_active_part_material_schema()
        self._refresh_result_comparison_if_visible()
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
        self._refresh_active_part_material_schema()
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
        self._refresh_active_part_material_schema()
        self._refresh_result_comparison_if_visible()
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
        self.refresh_predict_targets()
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
        self.refresh_predict_targets()
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
        self.refresh_predict_targets()
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
        self.refresh_predict_targets()
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
        self.refresh_predict_targets()
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

    def _predict_ref_key(self, ref):
        return self.backend_panel_controller.predict_ref_key(ref)

    def _predict_ref_from_key(self, key):
        return self.backend_panel_controller.predict_ref_from_key(key)

    def _result_source_role(self):
        if getattr(self, "result_source_editable_radio", None) is not None and self.result_source_editable_radio.isChecked():
            return "editable_ai_result"
        return "manual_truth"

    def _result_region_id(self):
        combo = getattr(self, "result_region_combo", None)
        if combo is None or not combo.count():
            return 0
        try:
            return int(combo.currentData() or 0)
        except (TypeError, ValueError):
            return 0

    def _result_region_name(self):
        combo = getattr(self, "result_region_combo", None)
        if combo is None or not combo.count():
            return tt("All", self.lang)
        text = str(combo.currentText() or "").strip()
        if "·" in text:
            text = text.split("·", 1)[1].strip()
        return text or tt("All", self.lang)

    def _result_comparison_tab_is_active(self):
        return bool(
            hasattr(self, "task_tabs")
            and hasattr(self, "training_mode_tabs")
            and hasattr(self, "result_compare_page")
            and self.task_tabs.currentWidget() is self.training_mode_tabs
            and self.training_mode_tabs.currentWidget() is self.result_compare_page
        )

    def _mark_result_comparison_stale(self):
        self._result_comparison_stale = True
        if hasattr(self, "result_compare_summary_label") and not self._result_comparison_tab_is_active():
            self.result_compare_summary_label.setText(tt("Result comparison will refresh when opened.", self.lang))

    def _refresh_result_comparison_if_visible(self):
        if self._result_comparison_tab_is_active():
            self.refresh_result_comparison()
        else:
            self._mark_result_comparison_stale()

    def _part_comparison_name(self, part):
        training = (part or {}).get("training") or {}
        return str(
            training.get("user_defined_part_name")
            or (part or {}).get("display_name")
            or (part or {}).get("part_id")
            or ""
        ).strip()

    def _active_comparison_part_name(self):
        if self.current_volume_scope == "part" and isinstance(self.current_part, dict):
            return self._part_comparison_name(self.current_part)
        return ""

    def _preferred_result_reslice_id(self, specimen_id, part):
        training = (part or {}).get("training") or {}
        active_reslice_id = str(training.get("active_reslice_id") or "").strip()
        part_id = str((part or {}).get("part_id") or "")
        if active_reslice_id:
            try:
                if self.project.get_part_reslice(specimen_id, part_id, active_reslice_id, default=None) is not None:
                    return active_reslice_id
            except Exception:
                return active_reslice_id
        reslices = []
        try:
            reslices = self.project.list_part_reslices(specimen_id, part_id)
        except Exception:
            reslices = ((part or {}).get("metadata") or {}).get("local_axis_reslices", []) or []
        if reslices:
            return str((reslices[-1] or {}).get("reslice_id") or "")
        return ""

    def _label_volume_counts_for_result(self, record, region_id):
        path = self.project.to_absolute((record or {}).get("path", ""))
        if not path:
            return {"ok": False, "status": tt("Label path missing", self.lang), "path": ""}
        if not volume_sidecar_exists(path):
            return {"ok": False, "status": tt("Label file missing", self.lang), "path": path}
        try:
            volume = load_volume_sidecar(path, mmap_mode="r")
            shape = tuple(int(value) for value in getattr(volume, "shape", ()) or ())
            if len(shape) != 3 or min(shape) <= 0:
                return {"ok": False, "status": tt("Label read failed: {0}", self.lang).format("empty_or_non_3d"), "path": path}
            total_labeled = 0
            region_voxels = 0
            plane_values = max(1, int(np.prod(shape[1:])))
            z_chunk = max(1, min(int(shape[0]), int((32 * 1024 * 1024) / (plane_values * max(1, np.dtype(getattr(volume, "dtype", np.uint16)).itemsize)))))
            for z0 in range(0, int(shape[0]), z_chunk):
                z1 = min(int(shape[0]), z0 + z_chunk)
                chunk = np.asarray(volume[z0:z1])
                total_labeled += int(np.count_nonzero(chunk))
                if int(region_id) > 0:
                    region_voxels += int(np.count_nonzero(chunk == int(region_id)))
                else:
                    region_voxels += int(np.count_nonzero(chunk))
            percent = (float(region_voxels) / float(total_labeled) * 100.0) if total_labeled else 0.0
            return {
                "ok": True,
                "status": str((record or {}).get("status") or "available"),
                "path": path,
                "shape": shape,
                "region_voxels": region_voxels,
                "total_labeled_voxels": total_labeled,
                "percent": percent,
            }
        except Exception as exc:
            return {"ok": False, "status": tt("Label read failed: {0}", self.lang).format(str(exc)), "path": path}

    def _result_comparison_rows(self):
        source_role = self._result_source_role()
        region_id = self._result_region_id()
        active_part_name = self._active_comparison_part_name()
        rows = []
        for specimen in self.project.project_data.get("specimens", []) or []:
            if not isinstance(specimen, dict):
                continue
            specimen_id = str(specimen.get("specimen_id") or "")
            if not specimen_id:
                continue
            specimen_label = str(specimen.get("display_name") or specimen_id)
            for part in specimen.get("parts", []) or []:
                if not isinstance(part, dict):
                    continue
                part_id = str(part.get("part_id") or "")
                if not part_id:
                    continue
                part_name = self._part_comparison_name(part)
                if active_part_name and part_name and part_name != active_part_name:
                    continue
                labels = part.get("labels") or {}
                record = labels.get(source_role) or {}
                ref = {
                    "specimen_id": specimen_id,
                    "part_id": part_id,
                    "reslice_id": self._preferred_result_reslice_id(specimen_id, part),
                }
                counts = self._label_volume_counts_for_result(record, region_id) if record and str(record.get("path") or "").strip() else {
                    "ok": False,
                    "status": tt("Missing {0}", self.lang).format(source_role),
                    "path": "",
                }
                rows.append(
                    {
                        "ref": ref,
                        "specimen_label": specimen_label,
                        "part_label": part_name or part_id,
                        "part_id": part_id,
                        "reslice_id": ref["reslice_id"],
                        "source_role": source_role,
                        "source_status": counts.get("status", ""),
                        "ok": bool(counts.get("ok")),
                        "label_path": counts.get("path", ""),
                        "shape": tuple(counts.get("shape") or (record.get("shape_zyx") or [])),
                        "region_voxels": int(counts.get("region_voxels") or 0),
                        "total_labeled_voxels": int(counts.get("total_labeled_voxels") or 0),
                        "percent": float(counts.get("percent") or 0.0),
                    }
                )
        return rows

    def _make_result_table_item(self, text):
        item = QTableWidgetItem(str(text or ""))
        item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        return item

    def _format_result_shape(self, shape):
        try:
            values = tuple(int(value) for value in shape)
        except (TypeError, ValueError):
            values = ()
        if len(values) != 3 or min(values) <= 0:
            return "-"
        return " / ".join(str(value) for value in values)

    def _format_count(self, value):
        try:
            return f"{int(value):,}"
        except (TypeError, ValueError):
            return "0"

    def _update_result_comparison_summary(self, rows):
        rows = list(rows or [])
        total = len(rows)
        ok_rows = [row for row in rows if row.get("ok")]
        region_voxels = sum(int(row.get("region_voxels") or 0) for row in ok_rows)
        labeled_voxels = sum(int(row.get("total_labeled_voxels") or 0) for row in ok_rows)
        percent = (float(region_voxels) / float(labeled_voxels) * 100.0) if labeled_voxels else 0.0
        part_name = self._active_comparison_part_name() or tt("All comparable parts", self.lang)
        text = tt(
            "Listed {0} {1} part result(s); {2} have {3}. Region voxels: {4} / labeled voxels: {5} ({6}%).",
            self.lang,
        ).format(
            total,
            part_name,
            len(ok_rows),
            self._result_source_role(),
            self._format_count(region_voxels),
            self._format_count(labeled_voxels),
            f"{percent:.2f}",
        )
        if total == 0:
            text = tt("No comparable part is selected yet. Select a part volume or use all parts.", self.lang)
        self.result_compare_summary_label.setText(text)

    def refresh_result_comparison(self):
        if not hasattr(self, "result_compare_table"):
            return []
        self._result_comparison_stale = False
        rows = self._result_comparison_rows()
        table = self.result_compare_table
        self._result_compare_refreshing = True
        try:
            table.blockSignals(True)
            table.setRowCount(0)
            table.setColumnCount(8)
            table.setHorizontalHeaderLabels(
                [
                    tt("Specimen", self.lang),
                    tt("Part", self.lang),
                    tt("Reslice", self.lang),
                    tt("Region voxels", self.lang),
                    tt("Labeled voxels", self.lang),
                    tt("Region %", self.lang),
                    tt("Source status", self.lang),
                    tt("Shape Z/Y/X", self.lang),
                ]
            )
            for row_index, row in enumerate(rows):
                table.insertRow(row_index)
                first_item = self._make_result_table_item(row["specimen_label"])
                first_item.setData(Qt.UserRole, dict(row))
                table.setItem(row_index, 0, first_item)
                table.setItem(row_index, 1, self._make_result_table_item(f"{row['part_label']} ({row['part_id']})"))
                table.setItem(row_index, 2, self._make_result_table_item(row.get("reslice_id") or "-"))
                table.setItem(row_index, 3, self._make_result_table_item(self._format_count(row.get("region_voxels"))))
                table.setItem(row_index, 4, self._make_result_table_item(self._format_count(row.get("total_labeled_voxels"))))
                table.setItem(row_index, 5, self._make_result_table_item(f"{float(row.get('percent') or 0.0):.2f}"))
                table.setItem(row_index, 6, self._make_result_table_item(row.get("source_status") or "-"))
                table.setItem(row_index, 7, self._make_result_table_item(self._format_result_shape(row.get("shape"))))
            table.resizeColumnsToContents()
            if rows and not table.selectedItems():
                table.selectRow(0)
        finally:
            table.blockSignals(False)
            self._result_compare_refreshing = False
        self._update_result_comparison_summary(rows)
        self._sync_result_comparison_controls()
        return rows

    def _selected_result_comparison_row(self):
        table = getattr(self, "result_compare_table", None)
        if table is None:
            return {}
        selected = table.selectedItems()
        row_index = selected[0].row() if selected else table.currentRow()
        if row_index < 0:
            return {}
        item = table.item(row_index, 0)
        if item is None:
            return {}
        row = item.data(Qt.UserRole)
        return dict(row or {}) if isinstance(row, dict) else {}

    def _set_label_role_if_available(self, role):
        if not hasattr(self, "label_role_combo"):
            return False
        index = self.label_role_combo.findData(role)
        if index < 0:
            return False
        if index == self.label_role_combo.currentIndex():
            self._reload_label_volume()
            return True
        self.label_role_combo.setCurrentIndex(index)
        return True

    def open_selected_result_comparison_target(self):
        if getattr(self, "_opening_result_comparison_target", False):
            return False
        row = self._selected_result_comparison_row()
        ref = row.get("ref") or {}
        specimen_id = str(ref.get("specimen_id") or "")
        part_id = str(ref.get("part_id") or "")
        reslice_id = str(ref.get("reslice_id") or "")
        if not specimen_id or not part_id:
            self._set_operation_feedback(tt("Select a result row before opening the 3D preview.", self.lang))
            return False
        scope = "part_reslice" if reslice_id else "part"
        start_message = tt("Opening selected result in 3D...", self.lang)
        self._set_operation_feedback(start_message)
        if hasattr(self, "display_mode_combo"):
            display_index = self.display_mode_combo.findData("volume")
            if display_index >= 0:
                self.display_mode_combo.setCurrentIndex(display_index)
            else:
                self.display_mode = "volume"
        if hasattr(self, "view_stack"):
            self.view_stack.setCurrentWidget(self.volume_canvas)
        self._set_volume_canvas_status_text(start_message, replace_existing=True)
        self._update_volume_render_status_label(start_message)
        if hasattr(self, "btn_open_result_comparison_target"):
            self.btn_open_result_comparison_target.setEnabled(False)
        QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)
        self._opening_result_comparison_target = True
        try:
            if not self._select_volume_tree_item(specimen_id, scope, part_id, reslice_id):
                self._set_operation_feedback(tt("Select a result row before opening the 3D preview.", self.lang))
                return False
            self._set_label_role_if_available(self._result_source_role())
            display_index = self.display_mode_combo.findData("volume")
            if display_index >= 0 and display_index != self.display_mode_combo.currentIndex():
                self.display_mode_combo.setCurrentIndex(display_index)
            else:
                self.display_mode = "volume"
                if hasattr(self, "view_stack"):
                    self.view_stack.setCurrentWidget(self.volume_canvas)
            self._invalidate_result_region_mask_cache(clear_active_mask_preview=True)
            self._reset_active_volume_preview_state()
            if hasattr(self, "task_tabs") and hasattr(self, "training_mode_tabs"):
                self.task_tabs.setCurrentWidget(self.training_mode_tabs)
                self.training_mode_tabs.setCurrentWidget(self.result_compare_page)
            if self._result_region_id() > 0 and bool(row.get("ok")):
                self._set_volume_mask_mode("masked_image")
            elif row and not bool(row.get("ok")):
                self._set_volume_mask_mode("image_only")
            self._set_scope_controls_enabled()
            self.render_volume_preview()
            message = tt("Opened {0} / {1} for 3D region comparison.", self.lang).format(specimen_id, part_id)
            self._set_operation_feedback(message)
            return True
        finally:
            self._opening_result_comparison_target = False
            self._sync_result_comparison_controls()

    def show_selected_result_region_in_3d(self):
        if self._result_region_id() <= 0:
            self._set_operation_feedback(tt("Region highlight requires a specific region label.", self.lang))
            return False
        row = self._selected_result_comparison_row()
        ref = row.get("ref") or {}
        selected_key = (
            str(ref.get("specimen_id") or ""),
            str(ref.get("part_id") or ""),
            str(ref.get("reslice_id") or ""),
        )
        current_key = (
            str(self.current_specimen_id or ""),
            str(self.current_part_id or ""),
            str(self.current_reslice_id or ""),
        )
        if self.current_volume_scope != "part" or self.image_volume is None or (selected_key[0] and selected_key != current_key):
            if not self.open_selected_result_comparison_target():
                return False
        self._set_label_role_if_available(self._result_source_role())
        message = tt("Preparing mask preview...", self.lang)
        self._set_operation_feedback(message)
        self._set_volume_canvas_status_text(message)
        self._update_volume_render_status_label(message)
        QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)
        if self._active_result_region_mask_volume() is None:
            self._set_operation_feedback(tt("Selected source has no label volume for the current part.", self.lang))
            return False
        self._clear_volume_mask_caches(owner=self._active_volume_cache_owner())
        self._reset_active_volume_preview_state()
        self._set_volume_mask_mode("masked_image")
        if self.display_mode_combo.findData("volume") >= 0 and self.display_mode_combo.currentData() != "volume":
            self.display_mode_combo.setCurrentIndex(self.display_mode_combo.findData("volume"))
        else:
            self.display_mode = "volume"
        self.render_volume_preview()
        self._set_operation_feedback(tt("Region highlight is ready in 3D preview.", self.lang))
        return True

    def _on_result_comparison_controls_changed(self, *args):
        self._invalidate_result_region_mask_cache(clear_active_mask_preview=True)
        if hasattr(self, "result_compare_table") and not getattr(self, "_result_compare_refreshing", False):
            self._refresh_result_comparison_if_visible()
        if self.display_mode == "volume":
            self.render_volume_preview()

    def _on_task_tab_changed(self, *_args):
        if self._result_comparison_tab_is_active() and bool(getattr(self, "_result_comparison_stale", True)):
            self.refresh_result_comparison()

    def _on_training_mode_tab_changed(self, *_args):
        if self._result_comparison_tab_is_active() and bool(getattr(self, "_result_comparison_stale", True)):
            self.refresh_result_comparison()

    def _sync_result_comparison_controls(self):
        if hasattr(self, "btn_refresh_result_comparison"):
            self.btn_refresh_result_comparison.setEnabled(bool(self.project.project_data.get("specimens", [])))
        has_result_rows = bool(getattr(self, "result_compare_table", None) and self.result_compare_table.rowCount() > 0)
        if hasattr(self, "btn_open_result_comparison_target"):
            self.btn_open_result_comparison_target.setEnabled(has_result_rows)
        if hasattr(self, "btn_show_result_region_in_3d"):
            self.btn_show_result_region_in_3d.setEnabled(self._result_region_id() > 0 and has_result_rows)

    def _populate_predict_filter_combo(self):
        return self.backend_panel_controller.populate_predict_filter_combo()

    def _predict_target_rows(self):
        return self.backend_panel_controller.predict_target_rows()

    def _make_predict_table_item(self, text, editable=False):
        return self.backend_panel_controller.make_predict_table_item(text, editable=editable)

    def _predict_status_text(self, row):
        return self.backend_panel_controller.predict_status_text(row)

    def _sync_predict_selection_from_table(self):
        return self.backend_panel_controller.sync_predict_selection_from_table()

    def _update_predict_target_summary(self):
        return self.backend_panel_controller.update_predict_target_summary()

    def refresh_predict_targets(self):
        return self.backend_panel_controller.refresh_predict_targets()

    def _on_predict_target_item_changed(self, item):
        return self.backend_panel_controller.on_predict_target_item_changed(item)

    def select_all_ready_predict_targets(self):
        return self.backend_panel_controller.select_all_ready_predict_targets()

    def clear_predict_target_selection(self):
        return self.backend_panel_controller.clear_predict_target_selection()

    def select_current_predict_target(self):
        return self.backend_panel_controller.select_current_predict_target()

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

    def _tif_model_records(self):
        return self.backend_panel_controller.model_records()

    def _tif_model_record_id(self, record):
        return self.backend_panel_controller.model_record_id(record)

    def _tif_model_display_name(self, record):
        return self.backend_panel_controller.model_display_name(record)

    def _format_tif_model_summary(self, record):
        return self.backend_panel_controller.format_model_summary(record)

    def _tif_model_tooltip(self, record):
        return self.backend_panel_controller.model_tooltip(record)

    def _populate_tif_model_library_combo(self, preferred_id=None):
        return self.backend_panel_controller.populate_model_library_combo(preferred_id)

    def _selected_tif_model_record(self):
        return self.backend_panel_controller.selected_model_record()

    def _on_model_library_selection_changed(self, *_args):
        return self.backend_panel_controller.on_model_library_selection_changed(*_args)

    def _refresh_model_library_controls(self):
        return self.backend_panel_controller.refresh_model_library_controls()

    def use_selected_tif_model(self):
        record = self._selected_tif_model_record()
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
        record = self._selected_tif_model_record()
        if not record:
            QMessageBox.information(self, tt("Trained model", self.lang), tt("No trained model is selected.", self.lang))
            return False
        model_id = self._tif_model_record_id(record)
        notes = self.model_library_notes_edit.toPlainText() if hasattr(self, "model_library_notes_edit") else ""
        try:
            updated = self.project.update_tif_segmentation_model_notes(model_id, notes, save=True)
        except Exception as exc:
            QMessageBox.warning(self, tt("Trained model", self.lang), str(exc))
            return False
        self._populate_tif_model_library_combo(self._tif_model_record_id(updated))
        self._set_operation_feedback(tt("Model notes saved.", self.lang))
        return True

    def delete_selected_tif_model_record(self):
        record = self._selected_tif_model_record()
        if not record:
            QMessageBox.information(self, tt("Trained model", self.lang), tt("No trained model is selected.", self.lang))
            return False
        model_id = self._tif_model_record_id(record)
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
        self._populate_tif_model_library_combo()
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

    def _invalidate_result_region_mask_cache(self, clear_active_mask_preview=True):
        self._result_region_mask_cache = {}
        self._result_region_mask_cache_key = None
        if clear_active_mask_preview:
            self._clear_volume_mask_caches(owner=self._active_volume_cache_owner())

    def show_workbench_log(self):
        if hasattr(self, "task_tabs") and hasattr(self, "training_mode_tabs"):
            self.task_tabs.setCurrentWidget(self.training_mode_tabs)
            self.training_mode_tabs.setCurrentWidget(self.training_task_page)

    def _set_local_axis_status(self, message, tooltip=""):
        label = getattr(self, "local_axis_status_label", None)
        if label is not None:
            label.setText(str(message or ""))
            label.setToolTip(str(tooltip or message or ""))

    def _connect_volume_interaction_slider(self, slider):
        slider.sliderPressed.connect(self._start_volume_interaction)
        slider.valueChanged.connect(lambda _value, item=slider: self._on_volume_interaction_slider_changed(item))
        slider.sliderReleased.connect(self.finish_volume_interaction_debounced)

    def _on_volume_interaction_slider_changed(self, slider=None):
        if self.display_mode != "volume":
            return
        if slider is not None and callable(getattr(slider, "isSliderDown", None)) and slider.isSliderDown():
            self._start_volume_interaction()
            self._request_volume_interaction_render()
            return
        if self._volume_render_mode == "drag":
            self._request_volume_interaction_render()
            self.finish_volume_interaction_debounced()
            return
        self.render_volume_preview()

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
            self.part_contour_draw_mode = False
            self.btn_draw_part_contour.blockSignals(True)
            self.btn_draw_part_contour.setChecked(False)
            self.btn_draw_part_contour.blockSignals(False)
            message = tt("Side-angle slices are read-only in this version. Use Z axial view for label editing.", self.lang)
            self.training_status_label.setText(message)
            self.log(message)
        self._set_scope_controls_enabled()
        self.render_current_slice()

    def on_display_mode_changed(self):
        mode = self.display_mode_combo.currentData() or "slice"
        self.display_mode = mode if mode in {"slice", "volume"} else "slice"
        if self.display_mode == "volume":
            self._ensure_volume_canvas()
        if hasattr(self, "view_stack"):
            self.view_stack.setCurrentWidget(self.volume_canvas if self.display_mode == "volume" else self.canvas)
        if hasattr(self, "volume_render_status_label"):
            self.volume_render_status_label.setVisible(self.display_mode == "volume")
        self._sync_mode_sections()
        is_volume = self.display_mode == "volume"
        if is_volume:
            self.part_roi_draw_mode = False
            self.part_contour_draw_mode = False
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
            message = self._volume_renderer_status_message()
            self.training_status_label.setText(message)
            self.log(message)
            if self.materialize_current_tif_metadata():
                self._set_scope_controls_enabled()
                return
            self._apply_default_volume_mask_mode()
            self._set_scope_controls_enabled()
            request = self._volume_preview_request("still")
            message = (request or {}).get("message") or tt("Preparing full-volume 3D preview...", self.lang)
            show_canvas_status = self._set_volume_canvas_status_text(message)
            self._update_volume_render_status_label(message)
            if show_canvas_status:
                QApplication.processEvents()
            self.render_volume_preview()
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
        self._update_local_axis_summary()

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
        payload["keyframes"] = self._normalize_full_volume_mask_keyframes(self.part_mask_keyframes)
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
            points = self._dedupe_contour_points(keyframe.get("polygon") or [])
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
            for point in self._dedupe_contour_points(keyframe.get("polygon") or []):
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
        if hasattr(canvas, "render_failed"):
            canvas.render_failed.connect(self._on_gpu_volume_failed)
        if hasattr(canvas, "render_info_changed"):
            canvas.render_info_changed.connect(self._on_gpu_volume_info_changed)
        if hasattr(canvas, "render_stats_changed"):
            canvas.render_stats_changed.connect(self._on_gpu_volume_stats_changed)

    def _ensure_volume_canvas(self, force_gpu=False):
        if self._volume_canvas_created and not force_gpu:
            return
        old_canvas = getattr(self, "volume_canvas", None)
        if force_gpu and old_canvas is not None and hasattr(old_canvas, "release_gl_resources"):
            try:
                old_canvas.release_gl_resources()
            except Exception:
                pass
        canvas, renderer, warning = create_tif_volume_canvas()
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

    def _format_review_reasons(self, report):
        reasons = [str(item) for item in ((report or {}).get("reasons") or [])]
        return ", ".join(reasons)

    def _current_ai_review_check_text(self):
        if self.current_volume_scope != "part" or not self.current_specimen_id or not self.current_part_id:
            return tt("Select a part editable AI result to see review checks.", self.lang)
        try:
            report = self.project.evaluate_part_editable_result_review_ready(
                self.current_specimen_id,
                self.current_part_id,
                self.current_reslice_id,
            )
        except Exception as exc:
            return tt("Review check blocked: {0}", self.lang).format(str(exc))
        detail = self._format_review_blocker_detail(report)
        checks = report.get("checks") or {}
        if not checks.get("editable_ai_result_exists"):
            return "\n".join([tt("No editable AI result is available for this part.", self.lang), detail])
        if report.get("review_ready") and report.get("opened_for_review"):
            return "\n".join([tt("Review check passed. This editable AI result can be accepted as training truth.", self.lang), detail])
        if report.get("review_ready") and not report.get("opened_for_review"):
            return "\n".join([tt("Review check passed, but this result has not been opened for review yet.", self.lang), detail])
        reasons = self._format_review_reasons(report) or "-"
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

    def _annotation_tool_modes(self):
        return {"brush", "eraser", "lasso", "rectangle", "ellipse", "picker", "pan"}

    def _sync_annotation_tool_buttons(self):
        mode = self.annotation_tool_mode if self.annotation_tool_mode in self._annotation_tool_modes() else "brush"
        self.annotation_tool_mode = mode
        for tool_mode, button in self._annotation_tool_buttons().items():
            if button is None:
                continue
            button.blockSignals(True)
            button.setChecked(tool_mode == mode)
            button.blockSignals(False)
        self._update_current_material_summary()
        if hasattr(self, "canvas"):
            self.canvas._refresh_scaled_pixmap()

    def set_annotation_tool_mode(self, mode, show_message=True):
        mode = str(mode or "brush")
        if mode not in self._annotation_tool_modes():
            mode = "brush"
        changed = mode != self.annotation_tool_mode
        self.annotation_tool_mode = mode
        self._sync_annotation_tool_buttons()
        if show_message and changed:
            messages = {
                "brush": "Tool set to Brush.",
                "eraser": "Tool set to Eraser.",
                "lasso": "Tool set to Lasso fill.",
                "rectangle": "Tool set to Rectangle fill.",
                "ellipse": "Tool set to Ellipse fill.",
                "picker": "Tool set to Picker.",
                "pan": "Tool set to Pan/view. Labels will not be changed.",
            }
            self._set_operation_feedback(tt(messages[mode], self.lang))
        return mode

    def _sync_undo_redo_buttons(self):
        if hasattr(self, "btn_undo"):
            self.btn_undo.setEnabled(bool(self.undo_stack) and self._can_edit_current_label_volume() and not self._backend_write_lock_active())
        if hasattr(self, "btn_redo"):
            self.btn_redo.setEnabled(bool(self.redo_stack) and self._can_edit_current_label_volume() and not self._backend_write_lock_active())

    def _dirty_slice_count(self):
        return len(getattr(self, "_dirty_edit_slices", set()) or set())

    def _mark_edit_slice_dirty(self, z_index):
        try:
            z_index = int(z_index)
        except Exception:
            return
        self._dirty_edit_slices.add(z_index)
        self._edit_revision_counter = int(getattr(self, "_edit_revision_counter", 0) or 0) + 1
        self._edit_slice_revisions[z_index] = int(self._edit_revision_counter)

    def _clear_saved_edit_slices(self, slice_revisions):
        for z_index, revision in (slice_revisions or {}).items():
            try:
                z_index = int(z_index)
                revision = int(revision)
            except Exception:
                continue
            if int(self._edit_slice_revisions.get(z_index, -1)) == revision:
                self._dirty_edit_slices.discard(z_index)
                self._edit_slice_revisions.pop(z_index, None)

    def _reset_edit_dirty_tracking(self):
        self._dirty_edit_slices = set()
        self._edit_slice_revisions = {}

    def _update_save_status(self, state=None, detail=""):
        if not hasattr(self, "save_status_label"):
            return
        count = self._dirty_slice_count()
        if state == "saving" or getattr(self, "_saving_working_edit", False) or self._label_auto_save_running() or self._label_manual_save_running():
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

    def _on_brush_size_changed(self, value):
        if hasattr(self, "canvas"):
            self.canvas._refresh_scaled_pixmap()

    def adjust_brush_size(self, delta):
        value = int(self.brush_size_slider.value())
        target = max(self.brush_size_slider.minimum(), min(self.brush_size_slider.maximum(), value + int(delta)))
        if target == value:
            return target
        self.brush_size_slider.setValue(target)
        self._set_operation_feedback(tt("Brush size: {0}", self.lang).format(target), log=False)
        return target

    def annotation_cursor_preview(self, pixel=None):
        mode = self.annotation_tool_mode if self.annotation_tool_mode in self._annotation_tool_modes() else "brush"
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

    def _on_auto_save_toggled(self, checked):
        if checked:
            message = tt("Auto-save is on. Brush changes are saved shortly after editing.", self.lang)
        elif self.current_volume_scope == "part":
            message = tt("Auto-save is off. Remember to save the editable AI result.", self.lang)
        else:
            message = tt("Auto-save is off. Remember to save the current labels.", self.lang)
        self._set_operation_feedback(message)
        if checked and self.working_edit_dirty:
            self.auto_save_timer.start()
        elif not checked:
            self.auto_save_timer.stop()
        self._update_save_status()

    def _current_edit_save_path(self):
        if self.current_volume_scope == "part":
            return self._current_part_label_path("editable_ai_result")
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

    def _snapshot_label_save_request(self, reason="auto_save"):
        if not self._can_auto_save_current_edit_volume():
            return None
        edit_path = self._current_edit_save_path()
        scope = "part" if self.current_volume_scope == "part" else "top_level"
        role = "editable_ai_result" if scope == "part" else "working_edit"
        result = self.label_edit_service.build_save_request(
            edit_volume=self.edit_volume,
            dirty_slices=self._dirty_edit_slices,
            edit_slice_revisions=self._edit_slice_revisions,
            edit_path=edit_path,
            scope=scope,
            specimen_id=self.current_specimen_id,
            part_id=self.current_part_id,
            reslice_id=self.current_reslice_id,
            role=role,
            reason=reason,
        )
        if not result:
            if result.message not in {"edit_volume_missing", "no_dirty_slices", "edit_path_missing"}:
                self._set_operation_feedback(tt("Cannot save this label layer: {0}", self.lang).format(result.message), log=False)
            return None
        request_payload = dict(result.payload.get("request") or {})
        self._label_auto_save_token += 1
        return {
            "token": int(self._label_auto_save_token),
            "reason": str(reason or "auto_save"),
            "edit_path": request_payload.get("edit_path", edit_path),
            "slices": request_payload.get("slices") or {},
            "slice_revisions": request_payload.get("slice_revisions") or {},
            "scope": str(request_payload.get("scope") or self.current_volume_scope or ""),
            "specimen_id": str(request_payload.get("specimen_id") or self.current_specimen_id or ""),
            "part_id": str(request_payload.get("part_id") or self.current_part_id or ""),
            "reslice_id": str(request_payload.get("reslice_id") or self.current_reslice_id or ""),
        }

    def _snapshot_label_auto_save_request(self, reason="auto_save"):
        return self._snapshot_label_save_request(reason=reason)

    def _start_label_auto_save(self, reason="auto_save"):
        if self._label_auto_save_running():
            self._label_auto_save_pending_reason = str(reason or "auto_save")
            self._update_save_status(state="saving")
            return True
        request = self._snapshot_label_auto_save_request(reason=reason)
        if request is None:
            self._update_save_status()
            return False
        thread = QThread(self)
        worker = TifLabelAutoSaveWorker(
            request["token"],
            request["edit_path"],
            request["slices"],
            request["slice_revisions"],
        )
        worker.moveToThread(thread)
        self._label_auto_save_thread = thread
        self._label_auto_save_worker = worker
        task = self._start_tif_task(
            "label_auto_save",
            action=str(reason or "auto_save"),
            payload={"token": request["token"], "edit_path": request["edit_path"]},
            label_role=request.get("role") or ("editable_ai_result" if request.get("scope") == "part" else "working_edit"),
            message=tt("Saving labels in background...", self.lang),
        )
        self._label_auto_save_task_id = task.task_id
        self._label_auto_save_pending_reason = ""
        self.auto_save_timer.stop()
        self._update_save_status(state="saving")
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_label_auto_save_finished)
        worker.failed.connect(self._on_label_auto_save_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.start()
        return True

    def _queue_manual_save_after_auto_save(self, show_message=True, promote_request=None):
        self._pending_manual_save_after_auto = {
            "show_message": bool(show_message),
            "promote_request": dict(promote_request or {}),
        }
        self.auto_save_timer.stop()
        self._update_save_status(state="saving")
        message = (
            tt("Finishing auto-save before accepting training truth...", self.lang)
            if promote_request
            else tt("Finishing auto-save before manual save...", self.lang)
        )
        self._set_operation_feedback(message)
        return True

    def _consume_manual_save_after_auto_save(self):
        pending = self._pending_manual_save_after_auto
        self._pending_manual_save_after_auto = None
        if not pending:
            return False
        promote_request = pending.get("promote_request") or None
        return self.save_working_edit_async(show_message=bool(pending.get("show_message", True)), promote_request=promote_request)

    def _cleanup_label_auto_save_thread(self):
        self._label_auto_save_thread = None
        self._label_auto_save_worker = None
        self._label_auto_save_task_id = ""

    def _cleanup_label_manual_save_thread(self):
        self._label_manual_save_thread = None
        self._label_manual_save_worker = None
        self._label_manual_save_task_id = ""
        self._saving_working_edit = False
        self._set_scope_controls_enabled()

    def _label_save_result_matches_current_view(self, result):
        result = dict(result or {})
        path = str(result.get("edit_path") or "")
        if not path:
            return False
        try:
            result_path = os.path.normcase(os.path.abspath(path))
            current_path = os.path.normcase(os.path.abspath(self._current_edit_save_path()))
        except Exception:
            return False
        return bool(current_path and result_path == current_path)

    def _wait_for_label_auto_save(self):
        thread = self._label_auto_save_thread
        if thread is None:
            return
        worker = self._label_auto_save_worker
        if thread.isRunning():
            thread.quit()
            thread.wait(30000)
        if worker is not None:
            result = getattr(worker, "last_result", None)
            error = getattr(worker, "last_error", None)
            if result:
                self._on_label_auto_save_finished(result)
            elif error:
                self._on_label_auto_save_failed(error)
            else:
                self._cancel_tif_task(self._label_auto_save_task_id, "label_auto_save_finished_without_result")
                self._cleanup_label_auto_save_thread()
        else:
            self._cancel_tif_task(self._label_auto_save_task_id, "label_auto_save_worker_missing")
            self._cleanup_label_auto_save_thread()

    def _label_auto_save_result_matches_current_view(self, result):
        return self._label_save_result_matches_current_view(result)

    def _on_label_auto_save_finished(self, result):
        result = dict(result or {})
        token = int(result.get("token", 0) or 0)
        if token in getattr(self, "_label_auto_save_handled_tokens", set()):
            return
        self._label_auto_save_handled_tokens.add(token)
        if token != int(self._label_auto_save_token):
            return
        if not self._label_auto_save_result_matches_current_view(result):
            self._cancel_tif_task(self._label_auto_save_task_id, "stale_label_auto_save_result")
            self._cleanup_label_auto_save_thread()
            self._pending_manual_save_after_auto = None
            self._pending_promote_after_save = None
            self._pending_backend_action_after_save = None
            return
        self._clear_saved_edit_slices(result.get("slice_revisions") or {})
        self.working_edit_dirty = bool(self._dirty_edit_slices)
        self._finish_tif_task(self._label_auto_save_task_id, payload=result, message="label_auto_save_finished")
        self._cleanup_label_auto_save_thread()
        if self.current_volume_scope == "part":
            self._finalize_part_editable_save_metadata(result.get("metadata") or {}, auto_saved=True, refresh_volumes=False)
        else:
            self._finalize_full_edit_save_metadata(result.get("metadata") or {}, auto_saved=True, refresh_volumes=False)
        if self.working_edit_dirty and self.auto_save_check.isChecked():
            self.auto_save_timer.start()
        self._update_save_status()
        self._set_operation_feedback(tt("Auto-saved current labels.", self.lang) if self.current_volume_scope != "part" else tt("Auto-saved editable AI result.", self.lang), log=False)
        if not self._consume_manual_save_after_auto_save():
            self._resume_pending_backend_action_after_save()

    def _on_label_auto_save_failed(self, result):
        result = dict(result or {})
        token = int(result.get("token", 0) or 0)
        if token in getattr(self, "_label_auto_save_handled_tokens", set()):
            return
        self._label_auto_save_handled_tokens.add(token)
        if token != int(self._label_auto_save_token):
            return
        if not self._label_auto_save_result_matches_current_view(result):
            self._cancel_tif_task(self._label_auto_save_task_id, "stale_label_auto_save_failure")
            self._cleanup_label_auto_save_thread()
            self._pending_backend_action_after_save = None
            return
        self._fail_tif_task(self._label_auto_save_task_id, result.get("error", ""), payload=result)
        self._cleanup_label_auto_save_thread()
        self.working_edit_dirty = True
        message = tt("Save failed: {0}", self.lang).format(str(result.get("error", "")))
        self._set_operation_feedback(message)
        self._update_save_status(state="failed", detail=str(result.get("error", "")))
        self._pending_manual_save_after_auto = None
        self._pending_promote_after_save = None
        self._pending_backend_action_after_save = None

    def save_working_edit_async(self, show_message=True, promote_request=None):
        if not self._guard_backend_write_lock():
            return False
        if self._saving_working_edit:
            return True
        if self._label_auto_save_running():
            return self._queue_manual_save_after_auto_save(show_message=show_message, promote_request=promote_request)
        if self.edit_volume is None and not self._ensure_working_edit_volume():
            return False
        request = self._snapshot_label_save_request(reason="manual")
        if request is None:
            self._update_save_status()
            if promote_request:
                self._pending_promote_after_save = None
                return self._begin_promote_working_edit_async(promote_request)
            self._resume_pending_backend_action_after_save()
            return True
        if promote_request:
            self._pending_promote_after_save = dict(promote_request or {})
        self._label_manual_save_token = int(request["token"])
        save_role = "editable_ai_result" if request.get("scope") == "part" else "working_edit"
        task = self._start_tif_task(
            "label_manual_save",
            action="manual_save",
            payload={"token": request["token"], "edit_path": request["edit_path"]},
            label_role=save_role,
            message=tt("Label save is running. Wait until it finishes before editing project data.", self.lang),
        )
        self._label_manual_save_task_id = task.task_id
        thread = QThread(self)
        worker = TifLabelManualSaveWorker(
            request["token"],
            request["edit_path"],
            request["slices"],
            request["slice_revisions"],
            context={
                "scope": request.get("scope", ""),
                "specimen_id": request.get("specimen_id", ""),
                "part_id": request.get("part_id", ""),
                "reslice_id": request.get("reslice_id", ""),
            },
        )
        worker.moveToThread(thread)
        self._label_manual_save_thread = thread
        self._label_manual_save_worker = worker
        self._saving_working_edit = True
        self.auto_save_timer.stop()
        self._update_save_status(state="saving")
        if show_message:
            self._set_operation_feedback(tt("Saving labels in background...", self.lang))
        self._set_scope_controls_enabled()
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_label_manual_save_finished)
        worker.failed.connect(self._on_label_manual_save_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.start()
        return True

    def _on_label_manual_save_finished(self, result):
        result = dict(result or {})
        if int(result.get("token", 0) or 0) != int(self._label_manual_save_token):
            self._cancel_tif_task(self._label_manual_save_task_id, "stale_label_manual_save_token")
            self._cleanup_label_manual_save_thread()
            self._pending_backend_action_after_save = None
            return
        if not self._label_save_result_matches_current_view(result):
            self._cancel_tif_task(self._label_manual_save_task_id, "stale_label_manual_save_context")
            self._cleanup_label_manual_save_thread()
            self._pending_backend_action_after_save = None
            return
        self._clear_saved_edit_slices(result.get("slice_revisions") or {})
        self.working_edit_dirty = bool(self._dirty_edit_slices)
        if self.current_volume_scope == "part":
            self._finalize_part_editable_save_metadata(result.get("metadata") or {}, refresh_volumes=True)
            message = tt("Editable AI result saved.", self.lang)
        else:
            self._finalize_full_edit_save_metadata(result.get("metadata") or {}, refresh_volumes=True)
            message = tt("Current labels saved.", self.lang)
        self._finish_tif_task(self._label_manual_save_task_id, payload=result, message=message)
        self._cleanup_label_manual_save_thread()
        self._update_save_status()
        self._set_operation_feedback(message)
        pending = self._pending_promote_after_save
        self._pending_promote_after_save = None
        if pending:
            self._begin_promote_working_edit_async(pending)
        else:
            self._resume_pending_backend_action_after_save()

    def _on_label_manual_save_failed(self, result):
        result = dict(result or {})
        self._fail_tif_task(self._label_manual_save_task_id, result.get("error", ""), payload=result)
        self._cleanup_label_manual_save_thread()
        self.working_edit_dirty = True
        message = tt("Save failed: {0}", self.lang).format(str(result.get("error", "")))
        self._set_operation_feedback(message)
        self._update_save_status(state="failed", detail=str(result.get("error", "")))
        QMessageBox.warning(self, tt("Unsaved working edit", self.lang), str(result.get("error", "")))
        self._pending_promote_after_save = None
        self._pending_backend_action_after_save = None

    def _mark_working_edit_dirty(self):
        if self._backend_write_lock_active():
            self._set_operation_feedback(self._backend_write_lock_message())
            return
        self._invalidate_result_region_mask_cache(clear_active_mask_preview=True)
        self.working_edit_dirty = True
        if self.auto_save_check.isChecked():
            self.auto_save_timer.start()
        self._update_save_status()

    def _confirm_discard_or_save_working_edit(self):
        if self._label_auto_save_running():
            message = tt("Auto-save is still finishing. Wait a moment, then try again.", self.lang)
            self._set_operation_feedback(message)
            self._update_save_status(state="saving")
            return False
        self._wait_for_label_auto_save()
        self.auto_save_timer.stop()
        self._update_save_status()
        if not self.working_edit_dirty:
            return True
        title = tt("Unsaved editable AI result", self.lang) if self.current_volume_scope == "part" else tt("Unsaved current labels", self.lang)
        prompt = (
            tt("Save changes to the current editable AI result before continuing?", self.lang)
            if self.current_volume_scope == "part"
            else tt("Save changes to the current labels before continuing?", self.lang)
        )
        reply = QMessageBox.question(
            self,
            title,
            prompt,
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )
        if reply == QMessageBox.Cancel:
            return False
        if reply == QMessageBox.Save:
            return self.save_working_edit(show_message=True)
        self.working_edit_dirty = False
        self._reset_edit_dirty_tracking()
        self._update_save_status()
        if self.current_specimen_id:
            self._load_edit_volume()
        return True

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

    def _task_context_matches_current(self, task_id, *, fields=None, request_key="", label_role="", ignore_empty=True):
        return self.task_adapter.current_context_matches(
            self,
            task_id,
            fields=fields,
            request_key=request_key,
            label_role=label_role,
            ignore_empty=ignore_empty,
        )

    def _safe_load_volume_sidecar(self, path, *, mmap_mode="r", operation="load_volume"):
        return self.preview_controller.safe_load_volume_sidecar(path, mmap_mode=mmap_mode, operation=operation)

    def _clear_preview_resource_issue(self):
        return self.preview_controller.clear_resource_issue()

    def _preview_resource_summary(self):
        return self.preview_controller.state_summary()

    def _current_state_summary(self):
        role = self.label_role_combo.currentData() if hasattr(self, "label_role_combo") else ""
        roll = (self.local_axis_draft or {}).get("roll_reference") if isinstance(self.local_axis_draft, dict) else {}
        preview_key = self._volume_preview_pending_key if self._volume_preview_pending_key is not None else self._volume_preview_pending_mask_key
        return {
            "selection": self.selection_controller.state.to_dict() if hasattr(self.selection_controller, "state") else {},
            "edit": TifEditState(
                dirty_slice_count=self._dirty_slice_count() if hasattr(self, "_dirty_slice_count") else len(getattr(self, "_dirty_edit_slices", set()) or set()),
                auto_save_running=self._label_auto_save_running(),
                manual_save_running=self._label_manual_save_running(),
                role=role,
                scope=self.current_volume_scope,
            ).to_dict(),
            "preview": TifPreviewState(
                display_mode=self.display_mode,
                render_mode=self._volume_render_mode,
                preview_pending=self._volume_preview_build_thread is not None,
                preview_token=self._volume_preview_pending_token,
                request_key=self._task_request_key(preview_key),
            ).to_dict(),
            "preview_resource": self._preview_resource_summary(),
            "backend": TifBackendState(
                running=self._backend_action_running(),
                action=self._tif_backend_action,
                run_dir=self._tif_backend_run_dir,
                result_json=self._tif_backend_result_json,
                progress_value=self._tif_backend_progress_value,
            ).to_dict(),
            "roi": TifRoiState(
                active_roi_id=self.active_part_roi_id,
                roi_keyframe_count=len(self.part_roi_keyframes or []),
                mask_keyframe_count=len(self.part_mask_keyframes or []),
                confirm_running=self._confirm_part_roi_running(),
                mask_preview_running=self._part_mask_preview_running(),
            ).to_dict(),
            "local_axis": TifLocalAxisState(
                draft_active=isinstance(self.local_axis_draft, dict),
                export_running=self._local_axis_reslice_export_running(),
                pick_target=str(getattr(self, "_local_axis_pick_target", "") or ""),
                specimen_id=str((self.local_axis_draft or {}).get("specimen_id") or "") if isinstance(self.local_axis_draft, dict) else "",
                part_id=str((self.local_axis_draft or {}).get("part_id") or "") if isinstance(self.local_axis_draft, dict) else "",
                reslice_id=self.current_reslice_id,
                roll_reference_keys=tuple(sorted((roll or {}).keys())) if isinstance(roll, dict) else (),
            ).to_dict(),
        }

    def _task_summary_for_context(self):
        return self.task_manager.summary()

    def _local_axis_reslice_export_running(self):
        return self._local_axis_reslice_export_thread is not None

    def _confirm_part_roi_running(self):
        return self._confirm_part_roi_thread is not None

    def _backend_action_running(self):
        return self._tif_backend_thread is not None

    def _label_auto_save_running(self):
        return self._label_auto_save_thread is not None

    def _label_manual_save_running(self):
        return self._label_manual_save_thread is not None

    def _promote_running(self):
        return self._promote_thread is not None

    def _active_tif_busy_locks(self, ignored_task_types=None):
        ignored = {str(task_type or "") for task_type in (ignored_task_types or set())}
        return [
            task
            for task in self.task_manager.active_busy_locks()
            if str(getattr(task, "task_type", "") or "") not in ignored
        ]

    def _preview_interaction_task_types(self):
        return {"volume_preview", "mask_preview"}

    def _local_axis_draft_lock_ignored_task_types(self):
        return self.local_axis_controller.ignored_draft_lock_task_types()

    def _backend_write_lock_active(self, ignored_task_types=None):
        return bool(
            self._active_tif_busy_locks(ignored_task_types)
            or (
            self._backend_action_running()
            or self._confirm_part_roi_running()
            or self._local_axis_reslice_export_running()
            or self._label_manual_save_running()
            or self._promote_running()
            )
        )

    def _backend_write_lock_message(self, ignored_task_types=None):
        active_locks = self._active_tif_busy_locks(ignored_task_types)
        if active_locks:
            task_type = active_locks[0].task_type
            if task_type == "truth_promotion":
                return tt("Training truth acceptance is running. Wait until it finishes before editing project data.", self.lang)
            if task_type == "label_auto_save":
                return tt("Label auto-save is running. Wait until it finishes before editing project data.", self.lang)
            if task_type == "label_manual_save":
                return tt("Label save is running. Wait until it finishes before editing project data.", self.lang)
            if task_type == "confirm_part_roi":
                return tt("Part volume creation is running. Wait until it finishes before editing project data.", self.lang)
            if task_type == "local_axis_export":
                return tt("Local Axis Reslice export is running. Wait until it finishes before editing project data.", self.lang)
            if task_type == "backend_action":
                return tt("Backend run is active. Stop it or wait until it finishes before editing project data.", self.lang)
            if task_type == "tif_import":
                return tt("TIF import is running. Wait until it finishes before editing project data.", self.lang)
            if task_type == "amira_import":
                return tt("AMIRA import is running. Wait until it finishes before editing project data.", self.lang)
            if task_type == "tif_materialize":
                return tt("Working volume build is running. Wait until it finishes before editing project data.", self.lang)
            if task_type == "volume_preview":
                return tt("Volume preview is being rebuilt. Wait until it finishes before editing project data.", self.lang)
            if task_type == "mask_preview":
                return tt("Mask preview is being rebuilt. Wait until it finishes before editing project data.", self.lang)
        if self._promote_running():
            return tt("Training truth acceptance is running. Wait until it finishes before editing project data.", self.lang)
        if self._label_manual_save_running():
            return tt("Label save is running. Wait until it finishes before editing project data.", self.lang)
        if self._confirm_part_roi_running():
            return tt("Part volume creation is running. Wait until it finishes before editing project data.", self.lang)
        if self._local_axis_reslice_export_running():
            return tt("Local Axis Reslice export is running. Wait until it finishes before editing project data.", self.lang)
        return tt("Backend run is active. Stop it or wait until it finishes before editing project data.", self.lang)

    def _backend_write_lock_title(self):
        if self._confirm_part_roi_running():
            return tt("Part extraction", self.lang)
        return tt("TIF backend", self.lang)

    def _guard_backend_write_lock(self, show_message=True, ignored_task_types=None):
        if not self._backend_write_lock_active(ignored_task_types=ignored_task_types):
            return True
        message = self._backend_write_lock_message(ignored_task_types=ignored_task_types)
        if show_message:
            self._set_operation_feedback(message)
            QMessageBox.information(self, self._backend_write_lock_title(), message)
        return False

    def _guard_local_axis_draft_interaction(self, show_message=True):
        return self.local_axis_controller.guard_draft_interaction(show_message=show_message)

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

    def _training_result_summary_tooltip(self, summary):
        return self.backend_panel_controller.training_result_summary_tooltip(summary)

    def _update_backend_elapsed_label(self):
        if not self._backend_action_running() or not self._tif_backend_started_mono:
            return
        elapsed = time.monotonic() - float(self._tif_backend_started_mono)
        self.backend_elapsed_label.setText(tt("Elapsed: {0}", self.lang).format(self._format_elapsed_seconds(elapsed)))

    def _set_backend_controls_running(self, running):
        return self.backend_panel_controller.set_backend_controls_running(running)

    def _format_training_result_summary_text(self, summary):
        return self.backend_panel_controller.format_training_result_summary_text(summary)

    def _set_training_result_summary(self, summary):
        previous_auto_manifest = str(self._tif_training_model_manifest or "")
        summary = summary if isinstance(summary, dict) and summary else None
        self._tif_training_result_summary = summary
        self._tif_training_model_output_dir = str((summary or {}).get("model_output") or "")
        self._tif_training_model_manifest = str((summary or {}).get("model_manifest") or "")
        if self._tif_training_model_manifest:
            self.backend_manifest_edit.setText(self._tif_training_model_manifest)
            self.backend_config["model_manifest"] = self._tif_training_model_manifest
        elif previous_auto_manifest and self.backend_manifest_edit.text().strip() == previous_auto_manifest:
            self.backend_manifest_edit.clear()
            self.backend_config["model_manifest"] = ""
        if hasattr(self, "training_result_summary_label"):
            self.training_result_summary_label.setText(self._format_training_result_summary_text(summary))
            self.training_result_summary_label.setToolTip(self._training_result_summary_tooltip(summary))
        self._refresh_training_result_controls()

    def _register_training_summary_model(self, summary, backend_result=None, contract=None):
        summary = summary if isinstance(summary, dict) else {}
        backend_result = backend_result if isinstance(backend_result, dict) else {}
        contract = contract if isinstance(contract, dict) else {}
        manifest = str(summary.get("model_manifest") or (backend_result.get("provenance") or {}).get("model_manifest") or "").strip()
        if not manifest:
            return None
        metrics_summary = ((backend_result.get("metrics") or {}).get("summary") or {}) if isinstance(backend_result.get("metrics"), dict) else {}
        try:
            record = self.project.register_tif_segmentation_model_from_manifest(
                manifest,
                {
                    "backend_id": backend_result.get("backend_id") or contract.get("backend_id"),
                    "run_id": backend_result.get("run_id") or contract.get("run_id") or summary.get("run_id"),
                    "run_dir": summary.get("run_dir") or contract.get("run_dir"),
                    "result_json": backend_result.get("_result_json") or contract.get("result_json"),
                    "dataset_manifest": (backend_result.get("provenance") or {}).get("dataset_manifest", ""),
                    "training_samples": metrics_summary.get("training_samples", 0),
                    "usable_for_research_prediction": (backend_result.get("provenance") or {}).get("usable_for_research_prediction", True),
                },
                save=True,
            )
        except Exception as exc:
            self.log(tt("Model registration skipped: {0}", self.lang).format(str(exc)))
            return None
        return record

    def _refresh_training_result_controls(self):
        return self.backend_panel_controller.refresh_training_result_controls()

    def show_latest_training_result_summary(self, show_message=True):
        summary = self._tif_training_result_summary if isinstance(self._tif_training_result_summary, dict) else None
        if not summary:
            if show_message:
                QMessageBox.information(self, tt("Training result", self.lang), tt("No training result summary is available yet.", self.lang))
            return False
        if self._tif_training_result_dialog is not None:
            try:
                self._tif_training_result_dialog.close()
            except Exception:
                pass
        dialog = TifTrainingResultDialog(summary, self.lang, self)
        dialog.setAttribute(Qt.WA_DeleteOnClose, True)
        dialog.destroyed.connect(lambda _obj=None: setattr(self, "_tif_training_result_dialog", None))
        self._tif_training_result_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        return True

    def open_latest_training_model_output(self):
        path = str(self._tif_training_model_output_dir or "")
        if not path or not os.path.isdir(path):
            QMessageBox.information(self, tt("Training result", self.lang), tt("No model output folder is available yet.", self.lang))
            return False
        return QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def open_latest_training_model_manifest(self):
        path = str(self._tif_training_model_manifest or "")
        if not path or not os.path.exists(path):
            QMessageBox.information(self, tt("Training result", self.lang), tt("No model manifest is available yet.", self.lang))
            return False
        return QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def enter_batch_prediction_from_training_result(self):
        manifest = str(self._tif_training_model_manifest or "")
        if not manifest or not os.path.exists(manifest):
            QMessageBox.information(self, tt("Training result", self.lang), tt("No model manifest is available yet.", self.lang))
            return False
        self.backend_manifest_edit.setText(manifest)
        self.backend_config["model_manifest"] = manifest
        if hasattr(self, "task_tabs") and hasattr(self, "training_mode_tabs"):
            self.task_tabs.setCurrentWidget(self.training_mode_tabs)
            self.training_mode_tabs.setCurrentWidget(self.training_task_page)
        self._populate_predict_filter_combo()
        if self.current_volume_scope in {"part", "part_reslice"} and self.current_specimen_id and self.current_part_id:
            index = self.predict_filter_combo.findData("current")
            if index >= 0:
                self.predict_filter_combo.setCurrentIndex(index)
            self.select_current_predict_target()
        else:
            self.refresh_predict_targets()
        self.btn_import_prediction.setFocus(Qt.OtherFocusReason)
        self._set_operation_feedback(tt("Model manifest filled for batch prediction. Choose target part(s), then run prediction.", self.lang))
        return True

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

    def _set_local_axis_reslice_export_controls_enabled(self, enabled):
        return self.local_axis_controller.set_export_controls_enabled(enabled)

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

    def _cleanup_tif_backend_thread(self):
        self.backend_elapsed_timer.stop()
        self._tif_backend_action = ""
        self._tif_backend_started_mono = 0.0
        self._set_backend_controls_running(False)
        self._set_scope_controls_enabled()

    def _on_tif_backend_thread_finished(self):
        self._tif_backend_worker = None
        self._tif_backend_thread = None
        self._set_backend_controls_running(False)
        self._set_scope_controls_enabled()

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
        batch_results = result.get("results") if isinstance(result, dict) else None
        if isinstance(batch_results, list):
            successes = [item for item in batch_results if item.get("ok")]
            failures = [item for item in batch_results if not item.get("ok")]
            first_id = successes[0].get("specimen_id", "") if successes else ""
            self.refresh_project()
            if first_id:
                self._select_specimen_after_import(first_id)
            message = tt("Imported {0}/{1} TIF stack(s).", self.lang).format(len(successes), len(batch_results))
            if failures:
                message = f"{message} {tt('Failed', self.lang)}: {len(failures)}"
            self.training_status_label.setText(message)
            self.log(message)
            for item in failures:
                self.log(f"TIF import failed [{item.get('specimen_id', '')}]: {item.get('error', '')}")
            thread = self._tif_import_thread
            self._finish_tif_task(self._tif_import_task_id, payload=result if isinstance(result, dict) else {}, message=message)
            self._cleanup_tif_import_thread()
            if thread is not None:
                thread.quit()
            if failures:
                details = "\n".join(f"{item.get('specimen_id', '')}: {item.get('error', '')}" for item in failures[:8])
                QMessageBox.warning(self, tt("Import TIF Stack", self.lang), f"{message}\n{details}")
            return

        specimen_id = self._tif_import_specimen_id
        self.refresh_project()
        self._select_specimen_after_import(specimen_id)
        report_path = result.get("report_path", "") if isinstance(result, dict) else ""
        message = tt("Imported TIF stack for specimen {0}. Report: {1}", self.lang).format(specimen_id, report_path)
        self.training_status_label.setText(message)
        self.log(message)
        thread = self._tif_import_thread
        self._finish_tif_task(self._tif_import_task_id, payload=result if isinstance(result, dict) else {}, message=message)
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

    def _materialize_task_matches(self, specimen_id=""):
        specimen_id = str(specimen_id or self.current_specimen_id or "")
        return bool(
            self._tif_materialize_thread is not None
            and specimen_id
            and str(self._tif_materialize_specimen_id or "") == specimen_id
        )

    def _slice_unavailable_message(self, specimen=None):
        override = str(getattr(self, "_slice_unavailable_override", "") or "").strip()
        if override:
            return override
        specimen = specimen if specimen is not None else self.project.get_specimen(self.current_specimen_id, default=None)
        specimen_id = str((specimen or {}).get("specimen_id") or self.current_specimen_id or "")
        if not specimen_id and not self.specimen_list.count():
            return tt("No specimens in this TIF project", self.lang)
        if self._materialize_task_matches(specimen_id):
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
        if self._materialize_task_matches(specimen_id):
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

    def _cleanup_tif_materialize_thread(self):
        if self._tif_materialize_progress is not None:
            self._tif_materialize_progress.close()
            self._tif_materialize_progress.deleteLater()
        self._tif_materialize_progress = None
        self._tif_materialize_worker = None
        self._tif_materialize_thread = None
        self._tif_materialize_specimen_id = ""
        self._tif_materialize_task_id = ""

    def _on_tif_materialize_progress(self, current, total, message):
        self._progress_tif_task(self._tif_materialize_task_id, current, total, str(message or ""))
        if self._tif_materialize_progress is None:
            return
        maximum = max(1, int(total or 100))
        value = max(0, min(maximum, int(current or 0)))
        self._tif_materialize_progress.setMaximum(maximum)
        self._tif_materialize_progress.setValue(value)
        self._tif_materialize_progress.setLabelText(tt(message, self.lang))

    def _on_tif_materialize_finished(self, result):
        specimen_id = self._tif_materialize_specimen_id
        report_path = result.get("report_path", "") if isinstance(result, dict) else ""
        thread = self._tif_materialize_thread
        task_id = self._tif_materialize_task_id
        task_current = self._task_context_matches_current(task_id, fields=("specimen_id",))
        self._finish_tif_task(task_id, payload=result if isinstance(result, dict) else {}, message="tif_materialize_finished")
        self._cleanup_tif_materialize_thread()
        if thread is not None:
            thread.quit()
        self.refresh_project()
        if specimen_id and task_current:
            self._select_specimen_after_import(specimen_id)
        message = tt("Working volume ready for specimen {0}. Report: {1}", self.lang).format(specimen_id, report_path)
        if specimen_id and not task_current:
            message = f"{message} {tt('Current view was left unchanged because you switched context while it was running.', self.lang)}"
        self.training_status_label.setText(message)
        self.log(message)

    def _on_tif_materialize_failed(self, message):
        thread = self._tif_materialize_thread
        specimen_id = self._tif_materialize_specimen_id
        task_id = self._tif_materialize_task_id
        task_current = self._task_context_matches_current(task_id, fields=("specimen_id",))
        self._fail_tif_task(task_id, str(message or ""), message=str(message or ""))
        self._cleanup_tif_materialize_thread()
        if thread is not None:
            thread.quit()
        self.refresh_project()
        if specimen_id and task_current:
            self._select_volume_tree_item(specimen_id, "full", "")
        QMessageBox.critical(self, tt("Build working volume", self.lang), message)

    def materialize_current_tif_metadata(self):
        if not self.current_specimen_id:
            return False
        specimen = self.project.get_specimen(self.current_specimen_id, default=None)
        if not self._is_metadata_only_specimen(specimen):
            return False
        if self._tif_materialize_thread is not None:
            QMessageBox.information(self, tt("Build working volume", self.lang), tt("Working volume build is already running.", self.lang))
            return True
        self._tif_materialize_specimen_id = self.current_specimen_id
        task = self._start_tif_task(
            "tif_materialize",
            action="materialize_working_volume",
            payload={"specimen_id": self.current_specimen_id},
            request_key=self.current_specimen_id,
            message=tt("Building working volume...", self.lang),
        )
        self._tif_materialize_task_id = task.task_id
        self._tif_materialize_progress = QProgressDialog(
            tt("Building working volume...", self.lang),
            "",
            0,
            100,
            self,
        )
        self._tif_materialize_progress.setWindowTitle(tt("Build working volume", self.lang))
        self._tif_materialize_progress.setCancelButton(None)
        self._tif_materialize_progress.setAutoClose(False)
        self._tif_materialize_progress.setAutoReset(False)
        self._tif_materialize_progress.setWindowModality(Qt.WindowModal)
        self._tif_materialize_progress.show()

        self._tif_materialize_thread = QThread(self)
        self._tif_materialize_worker = TifMaterializeWorker(self.project, self.current_specimen_id)
        self._tif_materialize_worker.moveToThread(self._tif_materialize_thread)
        self._tif_materialize_thread.started.connect(self._tif_materialize_worker.run)
        self._tif_materialize_worker.progress.connect(self._on_tif_materialize_progress)
        self._tif_materialize_worker.finished.connect(self._on_tif_materialize_finished)
        self._tif_materialize_worker.failed.connect(self._on_tif_materialize_failed)
        self._tif_materialize_worker.finished.connect(self._tif_materialize_thread.quit)
        self._tif_materialize_worker.failed.connect(self._tif_materialize_thread.quit)
        self._tif_materialize_thread.finished.connect(self._tif_materialize_worker.deleteLater)
        self._tif_materialize_thread.finished.connect(self._tif_materialize_thread.deleteLater)
        self._tif_materialize_thread.start()
        return True

    def _ensure_current_metadata_materializing_for_slice_review(self, specimen=None):
        if self.display_mode == "volume" or not self.current_specimen_id:
            return False
        specimen = specimen if specimen is not None else self.project.get_specimen(self.current_specimen_id, default=None)
        if not self._is_metadata_only_specimen(specimen):
            return False
        source_path = str((specimen.get("metadata") or {}).get("source_tif") or (specimen.get("source") or {}).get("raw_tif") or "")
        if not source_path:
            return False
        if self._materialize_task_matches(self.current_specimen_id):
            message = tt("Working volume is being built. Slice review will be available when it finishes.", self.lang)
            self._set_slice_review_unavailable(message)
            self.training_status_label.setText(message)
            return True
        if self._tif_materialize_thread is not None:
            return False
        if self.materialize_current_tif_metadata():
            message = tt("Working volume is being built. Slice review will be available when it finishes.", self.lang)
            self._set_slice_review_unavailable(message)
            self.training_status_label.setText(message)
            self.log(message)
            return True
        return False

    def _cleanup_local_axis_reslice_export_thread(self):
        if self._local_axis_reslice_export_progress is not None:
            self._local_axis_reslice_export_progress.close()
            self._local_axis_reslice_export_progress.deleteLater()
        self._local_axis_reslice_export_progress = None
        self._local_axis_reslice_export_worker = None
        self._local_axis_reslice_export_thread = None
        self._local_axis_reslice_export_context = {}
        self._local_axis_reslice_export_task_id = ""
        self._set_scope_controls_enabled()

    def _part_mask_preview_running(self):
        return self._part_mask_preview_thread is not None

    def _cleanup_part_mask_preview_thread(self):
        if self._part_mask_preview_progress is not None:
            self._part_mask_preview_progress.close()
            self._part_mask_preview_progress.deleteLater()
        self._part_mask_preview_progress = None
        self._part_mask_preview_worker = None
        self._part_mask_preview_thread = None
        self._part_mask_preview_context = {}
        self._part_mask_preview_task_id = ""
        self._set_scope_controls_enabled()

    def _on_part_mask_preview_progress(self, current, total, message):
        progress = self._part_mask_preview_progress
        if progress is None:
            return
        total = int(total or 0)
        if total <= 0:
            progress.setRange(0, 0)
        else:
            maximum = max(1, total)
            progress.setRange(0, maximum)
            progress.setValue(max(0, min(maximum, int(current or 0))))
        progress.setLabelText(tt(message, self.lang))

    def _on_part_mask_preview_finished(self, result):
        result = dict(result or {})
        token = int(result.get("token") or 0)
        if token != int(self._part_mask_preview_token):
            return
        if not self._task_context_matches_current(
            self._part_mask_preview_task_id,
            fields=("specimen_id", "volume_scope", "part_id", "reslice_id"),
        ):
            thread = self._part_mask_preview_thread
            self._cancel_tif_task(self._part_mask_preview_task_id, "stale_part_mask_preview_context")
            self._cleanup_part_mask_preview_thread()
            if thread is not None:
                thread.quit()
            return
        thread = self._part_mask_preview_thread
        context = dict(result.get("context") or self._part_mask_preview_context or {})
        if result.get("cancelled"):
            self._cancel_tif_task(self._part_mask_preview_task_id, "part_mask_preview_cancelled")
            self._cleanup_part_mask_preview_thread()
            if thread is not None:
                thread.quit()
            return
        mask = result.get("mask")
        if mask is None:
            self._fail_tif_task(self._part_mask_preview_task_id, "part_mask_preview_empty_result", payload=result)
            self._cleanup_part_mask_preview_thread()
            if thread is not None:
                thread.quit()
            return
        self._finish_tif_task(self._part_mask_preview_task_id, payload={"token": token}, message="part_mask_preview_finished")
        self._cleanup_part_mask_preview_thread()
        if thread is not None:
            thread.quit()
        self._apply_part_mask_preview_result(mask, context)

    def _on_part_mask_preview_failed(self, result):
        result = dict(result or {})
        token = int(result.get("token") or 0)
        if token != int(self._part_mask_preview_token):
            return
        thread = self._part_mask_preview_thread
        message = str(result.get("error") or "")
        task_current = self._task_context_matches_current(
            self._part_mask_preview_task_id,
            fields=("specimen_id", "volume_scope", "part_id", "reslice_id"),
        )
        self._fail_tif_task(self._part_mask_preview_task_id, message, payload=result)
        self._cleanup_part_mask_preview_thread()
        if thread is not None:
            thread.quit()
        if message and task_current:
            QMessageBox.warning(self, tt("Part extraction", self.lang), message)

    def _start_part_mask_preview_build(self, contours, shape, context):
        if self._part_mask_preview_thread is not None:
            QMessageBox.information(
                self,
                tt("Part extraction", self.lang),
                tt("Preview auto fill is already running.", self.lang),
            )
            return
        self._part_mask_preview_token += 1
        token = int(self._part_mask_preview_token)
        self._part_mask_preview_context = dict(context or {})
        task = self._start_tif_task(
            "mask_preview",
            action="build_mask_preview",
            payload={"token": token, "shape_zyx": list(shape or [])},
            request_key=f"part_mask_preview:{token}",
            message=tt("Preview auto fill is running...", self.lang),
        )
        task.context = self._current_task_context(request_key=f"part_mask_preview:{token}")
        if isinstance(context, dict):
            task.context = task.context.__class__.from_mapping(
                {
                    **task.context.to_dict(),
                    "specimen_id": context.get("specimen_id", task.context.specimen_id),
                    "volume_scope": context.get("volume_scope", context.get("scope", task.context.volume_scope)),
                    "part_id": context.get("part_id", task.context.part_id),
                    "reslice_id": context.get("reslice_id", task.context.reslice_id),
                    "request_key": f"part_mask_preview:{token}",
                }
            )
        self._part_mask_preview_task_id = task.task_id
        self._part_mask_preview_progress = QProgressDialog(
            tt("Preview auto fill is running...", self.lang),
            "",
            0,
            0,
            self,
        )
        self._part_mask_preview_progress.setWindowTitle(tt("Part extraction", self.lang))
        self._part_mask_preview_progress.setCancelButton(None)
        self._part_mask_preview_progress.setAutoClose(False)
        self._part_mask_preview_progress.setAutoReset(False)
        self._part_mask_preview_progress.setMinimumDuration(0)
        self._part_mask_preview_progress.setWindowModality(Qt.WindowModal)
        self._part_mask_preview_progress.show()

        self._part_mask_preview_thread = QThread(self)
        self._part_mask_preview_worker = TifPartMaskPreviewWorker(token, contours, shape, context)
        self._part_mask_preview_worker.moveToThread(self._part_mask_preview_thread)
        self._part_mask_preview_thread.started.connect(self._part_mask_preview_worker.run)
        self._part_mask_preview_worker.progress.connect(self._on_part_mask_preview_progress)
        self._part_mask_preview_worker.finished.connect(self._on_part_mask_preview_finished)
        self._part_mask_preview_worker.failed.connect(self._on_part_mask_preview_failed)
        self._part_mask_preview_worker.finished.connect(self._part_mask_preview_thread.quit)
        self._part_mask_preview_worker.failed.connect(self._part_mask_preview_thread.quit)
        self._part_mask_preview_thread.finished.connect(self._part_mask_preview_worker.deleteLater)
        self._part_mask_preview_thread.finished.connect(self._part_mask_preview_thread.deleteLater)
        self._set_scope_controls_enabled()
        self._part_mask_preview_thread.start()

    def _cleanup_confirm_part_roi_thread(self):
        if self._confirm_part_roi_progress is not None:
            self._confirm_part_roi_progress.close()
            self._confirm_part_roi_progress.deleteLater()
        self._confirm_part_roi_progress = None
        self._confirm_part_roi_worker = None
        self._confirm_part_roi_thread = None
        self._confirm_part_roi_request = {}
        self._confirm_part_roi_task_id = ""
        self._set_scope_controls_enabled()

    def _on_confirm_part_roi_progress(self, current, total, message):
        self._progress_tif_task(self._confirm_part_roi_task_id, current, total, str(message or ""))
        progress = self._confirm_part_roi_progress
        if progress is None:
            return
        total = int(total or 0)
        if total <= 0:
            progress.setRange(0, 0)
        else:
            maximum = max(1, total)
            progress.setRange(0, maximum)
            progress.setValue(max(0, min(maximum, int(current or 0))))
        progress.setLabelText(tt(message, self.lang))
        self.training_status_label.setText(tt(message, self.lang))

    def _on_confirm_part_roi_finished(self, result):
        result = dict(result or {})
        thread = self._confirm_part_roi_thread
        task_current = self._task_context_matches_current(
            self._confirm_part_roi_task_id,
            fields=("specimen_id", "volume_scope", "part_id"),
        )
        self._finish_tif_task(self._confirm_part_roi_task_id, payload=result, message="confirm_part_roi_finished")
        self._cleanup_confirm_part_roi_thread()
        if thread is not None:
            thread.quit()
        if not task_current:
            self.refresh_project()
            specimen_id = str(result.get("specimen_id") or "")
            part_id = str(result.get("part_id") or "")
            message = tt("Part volume {0} was created, but current view was left unchanged because you switched context while it was running.", self.lang).format(part_id)
            self.training_status_label.setText(message)
            self.log(message)
            return
        self._finish_confirm_part_roi_result(result)

    def _on_confirm_part_roi_failed(self, result):
        result = dict(result or {})
        thread = self._confirm_part_roi_thread
        message = str(result.get("error") or "")
        task_current = self._task_context_matches_current(
            self._confirm_part_roi_task_id,
            fields=("specimen_id", "volume_scope", "part_id"),
        )
        self._fail_tif_task(self._confirm_part_roi_task_id, message, payload=result)
        self._cleanup_confirm_part_roi_thread()
        if thread is not None:
            thread.quit()
        if message and task_current:
            self.training_status_label.setText(message)
            self.log(f"Failed to confirm ROI: {message}")
            QMessageBox.warning(self, tt("Part extraction", self.lang), message)

    def _start_confirm_part_roi_worker(self, request):
        if self._confirm_part_roi_thread is not None:
            QMessageBox.information(
                self,
                tt("Part extraction", self.lang),
                tt("Part volume creation is already running.", self.lang),
            )
            return False
        self._confirm_part_roi_request = dict(request or {})
        task = self._start_tif_task(
            "confirm_part_roi",
            action="confirm_part_roi",
            payload={"request": dict(request or {})},
            request_key=self._task_request_key((request or {}).get("bbox_zyx") or (request or {}).get("part_id") or ""),
            message=tt("Part volume creation is running. Wait until it finishes before editing project data.", self.lang),
        )
        self._confirm_part_roi_task_id = task.task_id
        self._confirm_part_roi_progress = QProgressDialog(
            tt("Creating part volume...", self.lang),
            "",
            0,
            0,
            self,
        )
        self._confirm_part_roi_progress.setWindowTitle(tt("Part extraction", self.lang))
        self._confirm_part_roi_progress.setCancelButton(None)
        self._confirm_part_roi_progress.setAutoClose(False)
        self._confirm_part_roi_progress.setAutoReset(False)
        self._confirm_part_roi_progress.setMinimumDuration(0)
        self._confirm_part_roi_progress.setWindowModality(Qt.WindowModal)
        self._confirm_part_roi_progress.show()

        self._confirm_part_roi_thread = QThread(self)
        self._confirm_part_roi_worker = TifConfirmPartRoiWorker(self.project, request)
        self._confirm_part_roi_worker.moveToThread(self._confirm_part_roi_thread)
        self._confirm_part_roi_thread.started.connect(self._confirm_part_roi_worker.run)
        self._confirm_part_roi_worker.progress.connect(self._on_confirm_part_roi_progress)
        self._confirm_part_roi_worker.finished.connect(self._on_confirm_part_roi_finished)
        self._confirm_part_roi_worker.failed.connect(self._on_confirm_part_roi_failed)
        self._confirm_part_roi_worker.finished.connect(self._confirm_part_roi_thread.quit)
        self._confirm_part_roi_worker.failed.connect(self._confirm_part_roi_thread.quit)
        self._confirm_part_roi_thread.finished.connect(self._confirm_part_roi_worker.deleteLater)
        self._confirm_part_roi_thread.finished.connect(self._confirm_part_roi_thread.deleteLater)
        self._set_scope_controls_enabled()
        self.training_status_label.setText(tt("Creating part volume...", self.lang))
        self._confirm_part_roi_thread.start()
        return True

    def _on_local_axis_reslice_export_progress(self, current, total, message):
        self._progress_tif_task(self._local_axis_reslice_export_task_id, current, total, str(message or ""))
        progress = self._local_axis_reslice_export_progress
        if progress is None:
            return
        total = int(total or 0)
        if total <= 0:
            progress.setRange(0, 0)
        else:
            maximum = max(1, total)
            value = max(0, min(maximum, int(current or 0)))
            progress.setRange(0, maximum)
            progress.setValue(value)
        progress.setLabelText(tt(message, self.lang))

    def _on_local_axis_reslice_export_finished(self, result):
        context = dict(getattr(self, "_local_axis_reslice_export_context", {}) or {})
        task_id = self._local_axis_reslice_export_task_id
        task_current = self._task_context_matches_current(task_id, fields=("specimen_id", "volume_scope", "part_id"))
        if not isinstance(result, dict):
            message = tt("Local Axis Reslice export did not return a result.", self.lang)
            self._fail_tif_task(task_id, message, message=message)
            self._cleanup_local_axis_reslice_export_thread()
            if task_current:
                self._set_local_axis_status(message)
            self.log(message)
            QMessageBox.warning(self, tt("Local Axis Reslice", self.lang), message)
            return
        record = result.get("record", {})
        reslice_id = record.get("reslice_id", "")
        message = tt("Exported local axis reslice {0}.", self.lang).format(reslice_id)
        self._finish_tif_task(task_id, payload=result, message="local_axis_export_finished")
        self._cleanup_local_axis_reslice_export_thread()
        if task_current:
            self._set_local_axis_status(message)
        self.training_status_label.setText(message)
        self.log(message)
        if task_current:
            self._local_axis_pick_target = ""
            self._local_axis_roll_pick_target = ""
        self.refresh_project()
        if task_current:
            self._select_volume_tree_item(
                context.get("specimen_id") or self.current_specimen_id,
                "part_reslice",
                context.get("part_id") or self.current_part_id,
                reslice_id,
            )

    def _on_local_axis_reslice_export_failed(self, message):
        task_id = self._local_axis_reslice_export_task_id
        task_current = self._task_context_matches_current(task_id, fields=("specimen_id", "volume_scope", "part_id"))
        self._fail_tif_task(task_id, str(message or ""), message=str(message or ""))
        self._cleanup_local_axis_reslice_export_thread()
        message = str(message or "")
        if task_current:
            self._set_local_axis_status(message)
        self.log(message)
        QMessageBox.warning(self, tt("Local Axis Reslice", self.lang), message)

    def import_tif_stack_dialog(self):
        if not self._guard_backend_write_lock():
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
        if not self._guard_backend_write_lock():
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

    def _parse_part_bbox_text(self):
        text = self.part_bbox_edit.text().strip()
        if not text:
            return []
        chunks = [chunk.strip() for chunk in text.replace(";", ",").split(",") if chunk.strip()]
        if len(chunks) != 6:
            raise ValueError("bbox_must_be_z0_z1_y0_y1_x0_x1")
        values = [int(chunk) for chunk in chunks]
        return [[values[0], values[1]], [values[2], values[3]], [values[4], values[5]]]

    def _empty_bbox_for_roi_drag(self):
        if self.image_volume is None:
            return []
        return [[0, 0], [0, 0], [0, 0]]

    def _normalize_roi_keyframes(self, keyframes, shape=None):
        shape = tuple(int(value) for value in (shape or getattr(self.image_volume, "shape", ()) or ()))
        normalized = []
        for item in keyframes or []:
            if not isinstance(item, dict):
                continue
            axis = str(item.get("axis") or "z")
            if axis not in {"z", "y", "x"}:
                continue
            try:
                slice_index = int(item.get("slice_index"))
                rect = [int(value) for value in item.get("rect", [])]
            except Exception:
                continue
            if len(rect) != 4:
                continue
            x0, y0, x1, y1 = rect
            if len(shape) == 3:
                if axis == "z":
                    max_slice, height, width = shape[0], shape[1], shape[2]
                elif axis == "y":
                    max_slice, height, width = shape[1], shape[0], shape[2]
                else:
                    max_slice, height, width = shape[2], shape[0], shape[1]
                if not (0 <= slice_index < max_slice):
                    continue
                x0, x1 = sorted((max(0, min(width, x0)), max(0, min(width, x1))))
                y0, y1 = sorted((max(0, min(height, y0)), max(0, min(height, y1))))
            else:
                x0, x1 = sorted((x0, x1))
                y0, y1 = sorted((y0, y1))
            if x1 <= x0 or y1 <= y0:
                continue
            normalized.append(
                {
                    "axis": axis,
                    "slice_index": slice_index,
                    "rect": [x0, y0, x1, y1],
                    "source": str(item.get("source") or "manual_rectangle"),
                }
            )
        normalized.sort(key=lambda item: (item["axis"], item["slice_index"]))
        return normalized

    def _roi_keyframe_bbox(self, keyframes, shape=None):
        shape = tuple(int(value) for value in (shape or getattr(self.image_volume, "shape", ()) or ()))
        if len(shape) != 3:
            return []
        bbox = [[0, 0], [0, 0], [0, 0]]
        for item in self._normalize_roi_keyframes(keyframes, shape):
            axis = item["axis"]
            index = int(item["slice_index"])
            x0, y0, x1, y1 = [int(value) for value in item["rect"]]
            if axis == "z":
                bbox[0] = self._expanded_axis_range(bbox[0], index, shape[0])
                bbox[1] = self._union_axis_range(bbox[1], y0, y1, shape[1])
                bbox[2] = self._union_axis_range(bbox[2], x0, x1, shape[2])
            elif axis == "y":
                bbox[0] = self._union_axis_range(bbox[0], y0, y1, shape[0])
                bbox[1] = self._expanded_axis_range(bbox[1], index, shape[1])
                bbox[2] = self._union_axis_range(bbox[2], x0, x1, shape[2])
            elif axis == "x":
                bbox[0] = self._union_axis_range(bbox[0], y0, y1, shape[0])
                bbox[1] = self._union_axis_range(bbox[1], x0, x1, shape[1])
                bbox[2] = self._expanded_axis_range(bbox[2], index, shape[2])
        if any(int(pair[1]) <= int(pair[0]) for pair in bbox):
            return []
        return self._clip_bbox_to_shape(bbox, shape)

    def _roi_keyframes_from_bbox_for_axis(self, bbox, axis):
        bbox = self._clip_bbox_to_shape(bbox, self.image_volume.shape) if self.image_volume is not None else bbox
        if not bbox or len(bbox) != 3:
            return []
        axis = axis if axis in {"z", "y", "x"} else "z"
        z_range, y_range, x_range = bbox
        if axis == "z":
            start, end = int(z_range[0]), int(z_range[1]) - 1
            rect = [int(x_range[0]), int(y_range[0]), int(x_range[1]), int(y_range[1])]
        elif axis == "y":
            start, end = int(y_range[0]), int(y_range[1]) - 1
            rect = [int(x_range[0]), int(z_range[0]), int(x_range[1]), int(z_range[1])]
        else:
            start, end = int(x_range[0]), int(x_range[1]) - 1
            rect = [int(y_range[0]), int(z_range[0]), int(y_range[1]), int(z_range[1])]
        if end < start:
            return []
        keyframes = [{"axis": axis, "slice_index": start, "rect": list(rect), "source": "bbox_compat"}]
        if end != start:
            keyframes.append({"axis": axis, "slice_index": end, "rect": list(rect), "source": "bbox_compat"})
        return self._normalize_roi_keyframes(keyframes)

    def _roi_keyframe_metadata(self):
        keyframes = self._normalize_roi_keyframes(self.part_roi_keyframes)
        axes = sorted({item["axis"] for item in keyframes})
        mask_keyframes = self._normalize_full_volume_mask_keyframes(self.part_mask_keyframes)
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

    def _load_roi_draft_for_editing(self, roi):
        self.active_part_roi_id = (roi or {}).get("roi_id", "")
        metadata = (roi or {}).get("metadata") or {}
        self.part_roi_keyframes = self._normalize_roi_keyframes(metadata.get("roi_keyframes", []))
        self.part_mask_keyframes = self._normalize_full_volume_mask_keyframes(metadata.get("part_mask_keyframes", []))
        self.part_preview_mask = None
        self.part_mask_preview_bbox = []
        self.part_mask_preview_accepted = False
        self.part_bbox_edit.setText(self._bbox_text((roi or {}).get("bbox_zyx", [])))

    def _upsert_part_roi_keyframe(self, axis, slice_index, rect):
        axis = axis if axis in {"z", "y", "x"} else "z"
        keyframes = self._normalize_roi_keyframes(self.part_roi_keyframes)
        if not keyframes:
            try:
                bbox = self._parse_part_bbox_text()
            except Exception:
                bbox = []
            if bbox:
                keyframes = self._roi_keyframes_from_bbox_for_axis(bbox, axis)
        axes = {item["axis"] for item in keyframes}
        if axes and axis not in axes:
            message = tt("ROI key slices use one view plane. Switch back to {0} or save a separate ROI.", self.lang).format(sorted(axes)[0].upper())
            QMessageBox.information(self, tt("Part extraction", self.lang), message)
            self.training_status_label.setText(message)
            self.log(message)
            return [], []
        keyframes = [
            item
            for item in keyframes
            if not (item["axis"] == axis and int(item["slice_index"]) == int(slice_index))
        ]
        keyframes.append({"axis": axis, "slice_index": int(slice_index), "rect": [int(value) for value in rect], "source": "manual_rectangle"})
        keyframes = self._normalize_roi_keyframes(keyframes)
        bbox = self._roi_keyframe_bbox(keyframes)
        if bbox:
            self.part_roi_keyframes = keyframes
        return keyframes, bbox

    def _roi_keyframe_projection_for_current_slice(self, keyframes):
        axis, index = self._active_slice_position()
        same_axis = [
            item
            for item in self._normalize_roi_keyframes(keyframes)
            if item.get("axis") == axis
        ]
        if not same_axis:
            return None
        same_axis.sort(key=lambda item: int(item.get("slice_index", 0)))
        index = int(index)
        if index < int(same_axis[0]["slice_index"]) or index > int(same_axis[-1]["slice_index"]):
            return None
        for item in same_axis:
            if int(item["slice_index"]) == index:
                return list(item["rect"])
        left = None
        right = None
        for item in same_axis:
            if int(item["slice_index"]) < index:
                left = item
            elif int(item["slice_index"]) > index and right is None:
                right = item
                break
        if left is None or right is None:
            return None
        left_index = int(left["slice_index"])
        right_index = int(right["slice_index"])
        if right_index <= left_index:
            return None
        weight = float(index - left_index) / float(right_index - left_index)
        values = []
        for left_value, right_value in zip(left["rect"], right["rect"]):
            values.append(int(round((1.0 - weight) * float(left_value) + weight * float(right_value))))
        if values[2] <= values[0] or values[3] <= values[1]:
            return None
        return values

    def _roi_shell_mask_from_keyframes(self, keyframes, parent_bbox):
        keyframes = self._normalize_roi_keyframes(keyframes)
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
        return bool(
            self.part_roi_draw_mode
            and self.current_volume_scope == "full"
            and self.display_mode == "slice"
            and self.image_volume is not None
        )

    def set_part_roi_draw_mode(self, checked):
        self.part_roi_draw_mode = bool(checked)
        if self.part_roi_draw_mode:
            self.part_contour_draw_mode = False
            self.btn_draw_part_contour.blockSignals(True)
            self.btn_draw_part_contour.setChecked(False)
            self.btn_draw_part_contour.blockSignals(False)
            if self.current_volume_scope != "full" or self.image_volume is None:
                self.part_roi_draw_mode = False
                self.btn_part_draw_roi.blockSignals(True)
                self.btn_part_draw_roi.setChecked(False)
                self.btn_part_draw_roi.blockSignals(False)
                QMessageBox.information(self, tt("Part extraction", self.lang), tt("Switch to Full volume before drawing ROI.", self.lang))
                return
            message = tt("Drag rectangles on one or more key slices in the current view plane. The ROI bbox will expand to include them.", self.lang)
            self.training_status_label.setText(message)
            self.log(message)
        self.render_current_slice()

    def is_part_contour_draw_mode(self):
        return bool(
            self.part_contour_draw_mode
            and self.current_volume_scope in {"full", "part"}
            and self.display_mode == "slice"
            and self.image_volume is not None
            and self._current_slice_axis() == "z"
        )

    def set_part_contour_draw_mode(self, checked):
        self.part_contour_draw_mode = bool(checked)
        if self.part_contour_draw_mode:
            self.part_roi_draw_mode = False
            self.btn_part_draw_roi.blockSignals(True)
            self.btn_part_draw_roi.setChecked(False)
            self.btn_part_draw_roi.blockSignals(False)
            if self.current_volume_scope not in {"full", "part"} or self.image_volume is None:
                self.part_contour_draw_mode = False
                self.btn_draw_part_contour.blockSignals(True)
                self.btn_draw_part_contour.setChecked(False)
                self.btn_draw_part_contour.blockSignals(False)
                QMessageBox.information(self, tt("Part extraction", self.lang), tt("Select a full volume or part volume before drawing contours.", self.lang))
                return
            if self.display_mode != "slice" or self._current_slice_axis() != "z":
                self.part_contour_draw_mode = False
                self.btn_draw_part_contour.blockSignals(True)
                self.btn_draw_part_contour.setChecked(False)
                self.btn_draw_part_contour.blockSignals(False)
                QMessageBox.information(self, tt("Part extraction", self.lang), tt("Contour drawing currently uses Z slices.", self.lang))
                return
            message = tt("Drag on the current slice to draw a closed contour.", self.lang)
            self.training_status_label.setText(message)
            self.log(message)
        self.render_current_slice()

    def current_roi_overlay_rects(self):
        if self.current_volume_scope != "full" or self.image_volume is None:
            return []
        overlays = []
        try:
            bbox = self._parse_part_bbox_text()
        except Exception:
            bbox = []
        current_rect = self._roi_keyframe_projection_for_current_slice(self.part_roi_keyframes)
        if current_rect:
            overlays.append({"rect": current_rect, "color": "#FFD34D", "kind": "current"})
        elif bbox and len(bbox) == 3:
            current_rect = self._bbox_projection_for_current_slice(bbox)
            if current_rect:
                overlays.append({"rect": current_rect, "color": "#FFD34D", "kind": "current"})
        specimen = self.project.get_specimen(self.current_specimen_id, default=None) if self.current_specimen_id else None
        for roi in (specimen or {}).get("part_rois", []) or []:
            if (roi or {}).get("status") == "cancelled":
                continue
            rect = self._roi_keyframe_projection_for_current_slice(((roi or {}).get("metadata") or {}).get("roi_keyframes", []))
            if not rect:
                rect = self._bbox_projection_for_current_slice((roi or {}).get("bbox_zyx", []))
            if rect:
                color = "#42D9C8" if (roi or {}).get("status") in {"draft", "confirmed"} else "#7EE787"
                overlays.append({"rect": rect, "color": color, "kind": "roi", "roi_id": (roi or {}).get("roi_id", "")})
        for part in (specimen or {}).get("parts", []) or []:
            rect = self._bbox_projection_for_current_slice((part or {}).get("parent_bbox_zyx", []))
            if rect:
                overlays.append({"rect": rect, "color": "#7EE787", "kind": "part", "part_id": (part or {}).get("part_id", "")})
        return overlays

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

    def finish_part_roi_drag(self, start_x, start_y, end_x, end_y):
        if not self.is_part_roi_draw_mode() or self.image_volume is None:
            return
        axis = self._current_slice_axis()
        start_pixel = self.canvas.widget_to_image_pixel(start_x, start_y)
        end_pixel = self.canvas.widget_to_image_pixel(end_x, end_y)
        if start_pixel is None or end_pixel is None:
            return
        x0 = min(int(start_pixel[0]), int(end_pixel[0]))
        x1 = max(int(start_pixel[0]), int(end_pixel[0])) + 1
        y0 = min(int(start_pixel[1]), int(end_pixel[1]))
        y1 = max(int(start_pixel[1]), int(end_pixel[1])) + 1
        if x1 - x0 < 2 or y1 - y0 < 2:
            return
        slice_index = int(self.slice_slider.value())
        keyframes, bbox = self._upsert_part_roi_keyframe(axis, slice_index, [x0, y0, x1, y1])
        if not bbox:
            return
        self.part_bbox_edit.setText(self._bbox_text(bbox))
        autosaved_roi = self._autosave_active_part_roi_bbox(bbox)
        if autosaved_roi is not None:
            message = tt("ROI bbox updated and saved to draft {0}: {1}", self.lang).format(
                autosaved_roi.get("display_name") or autosaved_roi.get("roi_id"),
                self.part_bbox_edit.text(),
            )
        else:
            message = tt("ROI bbox updated: {0}", self.lang).format(self.part_bbox_edit.text())
        self.training_status_label.setText(message)
        self.log(message)
        self.render_current_slice()

    def _autosave_active_part_roi_bbox(self, bbox):
        if not self.active_part_roi_id or not self.current_specimen_id:
            return None
        roi = self.project.get_part_roi(self.current_specimen_id, self.active_part_roi_id, default=None)
        if roi is None or roi.get("linked_part_id") or roi.get("status") == "part_created":
            return None
        try:
            updated = self.project.update_part_roi(
                self.current_specimen_id,
                self.active_part_roi_id,
                bbox_zyx=bbox,
                status="draft",
                metadata=self._roi_keyframe_metadata(),
                save=True,
            )
        except Exception as exc:
            self.log(f"Failed to auto-save ROI draft {self.active_part_roi_id}: {exc}")
            return None
        self._populate_volume_roi_source_combo()
        return updated

    def _autosave_active_part_roi_mask_keyframes(self, bbox=None):
        if not self.active_part_roi_id or not self.current_specimen_id:
            return None
        roi = self.project.get_part_roi(self.current_specimen_id, self.active_part_roi_id, default=None)
        if roi is None or roi.get("linked_part_id") or roi.get("status") == "part_created":
            return None
        if bbox is None:
            bbox = self._full_volume_contour_bbox()
        if not bbox:
            return None
        try:
            updated = self.project.update_part_roi(
                self.current_specimen_id,
                self.active_part_roi_id,
                bbox_zyx=bbox,
                status="draft",
                metadata=self._roi_keyframe_metadata(),
                save=True,
            )
        except Exception as exc:
            self.log(f"Failed to auto-save part mask key slices for ROI draft {self.active_part_roi_id}: {exc}")
            return None
        self._populate_volume_roi_source_combo()
        return updated

    def open_roi_at_widget_position(self, x, y):
        if self.current_volume_scope != "full" or self.image_volume is None:
            return False
        pixel = self.canvas.widget_to_image_pixel(x, y)
        if pixel is None:
            return False
        px, py = pixel
        overlays = list(reversed(self.current_roi_overlay_rects()))
        for overlay in overlays:
            if not isinstance(overlay, dict):
                continue
            rect = overlay.get("rect", [])
            if len(rect) != 4:
                continue
            x0, y0, x1, y1 = [int(value) for value in rect]
            if not (min(x0, x1) <= px <= max(x0, x1) and min(y0, y1) <= py <= max(y0, y1)):
                continue
            if overlay.get("kind") == "part" and overlay.get("part_id"):
                self._select_volume_tree_item(self.current_specimen_id, "part", overlay.get("part_id", ""))
                return True
            if overlay.get("kind") == "roi" and overlay.get("roi_id"):
                roi = self.project.get_part_roi(self.current_specimen_id, overlay.get("roi_id", ""), default=None)
                if roi is not None:
                    self._load_roi_draft_for_editing(roi)
                    message = tt("Loaded ROI draft {0} for editing.", self.lang).format(roi.get("display_name") or roi.get("roi_id"))
                    self.training_status_label.setText(message)
                    self.log(message)
                    self.render_current_slice()
                    return True
        return False

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

    def _default_roi_id(self):
        existing = len(self.project.list_part_rois(self.current_specimen_id, include_cancelled=True)) if self.current_specimen_id else 0
        return f"roi_{existing + 1}"

    def save_part_roi_draft(self):
        if not self._guard_backend_write_lock():
            return None
        if self.current_volume_scope != "full" or not self.current_specimen_id or self.image_volume is None:
            QMessageBox.information(self, tt("Part extraction", self.lang), tt("Switch to Full volume before saving ROI draft.", self.lang))
            return None
        try:
            bbox = self._current_part_bbox_for_action()
        except Exception as exc:
            QMessageBox.warning(self, tt("Part extraction", self.lang), str(exc))
            return None
        if self.active_part_roi_id:
            roi = self.project.update_part_roi(
                self.current_specimen_id,
                self.active_part_roi_id,
                bbox_zyx=bbox,
                status="draft",
                metadata=self._roi_keyframe_metadata(),
            )
        else:
            dialog = TifPartNameDialog(
                "Save ROI draft",
                part_id=self._default_roi_id(),
                display_name=self._default_roi_id(),
                parent=self,
                lang=self.lang,
                id_label="ROI ID:",
            )
            if dialog.exec() != QDialog.Accepted:
                return None
            roi_id, display_name = dialog.values()
            if not str(roi_id).strip():
                return None
            try:
                roi = self.project.add_part_roi(
                    self.current_specimen_id,
                    roi_id,
                    display_name=display_name or roi_id,
                    bbox_zyx=bbox,
                    status="draft",
                    metadata=self._roi_keyframe_metadata(),
                )
            except Exception as exc:
                QMessageBox.warning(self, tt("Part extraction", self.lang), str(exc))
                return None
        self._load_roi_draft_for_editing(roi)
        self._populate_volume_roi_source_combo()
        message = tt("Saved ROI draft {0}.", self.lang).format(roi.get("display_name") or roi.get("roi_id"))
        self.training_status_label.setText(message)
        self.log(message)
        self.render_current_slice()
        return roi

    def _confirm_part_roi_request_voxel_count(self, request):
        return self.roi_part_service.request_voxel_count(request)

    def _should_confirm_part_roi_in_background(self, request):
        return self.roi_part_service.should_run_in_background(request, threshold=TIF_CONFIRM_PART_BACKGROUND_VOXELS)

    def _accepted_full_volume_preview_mask_for_request(self, bbox):
        if (
            self.part_mask_preview_accepted
            and self.part_preview_mask is not None
            and self.part_mask_preview_bbox == bbox
        ):
            shape = _tif_bbox_shape(bbox)
            if tuple(getattr(self.part_preview_mask, "shape", ()) or ()) == tuple(shape):
                return self.part_preview_mask
        return None

    def _build_confirm_part_roi_request(self, roi, bbox, part_id, display_name, roi_keyframes, mask_contours, mask_bbox):
        result = self.roi_part_service.build_confirm_part_roi_request(
            specimen_id=self.current_specimen_id,
            part_id=part_id,
            display_name=display_name,
            bbox_zyx=bbox,
            source_shape_zyx=[int(value) for value in getattr(self.image_volume, "shape", ()) or ()],
            roi_id=str((roi or {}).get("roi_id") or ""),
            roi_metadata=self._roi_keyframe_metadata(),
            roi_keyframes=roi_keyframes,
            mask_contours=mask_contours,
            mask_bbox_zyx=mask_bbox,
            accepted_preview_mask=self._accepted_full_volume_preview_mask_for_request(bbox) if mask_bbox else None,
        )
        if not result:
            raise ValueError(result.message or ", ".join(result.reasons or []))
        return result.payload.get("request") or {}

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
            self._ensure_roi_for_created_part(part, request.get("bbox_zyx", []), display_name=request.get("display_name") or request.get("part_id", ""))
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

    def _finish_confirm_part_roi_result(self, result):
        result = dict(result or {})
        part = result.get("part") if isinstance(result.get("part"), dict) else None
        specimen_id = str(result.get("specimen_id") or self.current_specimen_id or "")
        part_id = str(result.get("part_id") or (part or {}).get("part_id") or "")
        if not specimen_id or not part_id:
            return
        self.active_part_roi_id = ""
        self.part_mask_keyframes = []
        self.part_mask_preview_bbox = []
        self.part_mask_preview_accepted = False
        self.refresh_project()
        self._populate_volume_roi_source_combo()
        self._select_volume_tree_item(specimen_id, "part", part_id)
        part = self.project.get_part(specimen_id, part_id, default=part)
        message = tt("Confirmed ROI and created part {0}.", self.lang).format((part or {}).get("display_name") or part_id)
        if result.get("mask_initialized"):
            if result.get("mask_bbox_zyx"):
                message = f"{message}\n{tt('Full-volume contour mask initialized from {0} key slice(s).', self.lang).format(int(result.get('mask_keyframe_count') or 0))}"
            else:
                message = f"{message}\n{tt('ROI shell mask initialized from {0} key slice(s).', self.lang).format(int(result.get('roi_keyframe_count') or 0))}"
        elif result.get("mask_message"):
            if result.get("mask_bbox_zyx"):
                message = f"{message}\n{tt('Full-volume contour mask not initialized: {0}', self.lang).format(result.get('mask_message'))}"
            else:
                message = f"{message}\nROI shell mask not initialized: {result.get('mask_message')}"
        self.training_status_label.setText(message)
        self.log(message)

    def confirm_part_roi_to_part(self):
        if not self._guard_backend_write_lock():
            return
        if self._confirm_part_roi_running():
            QMessageBox.information(self, tt("Part extraction", self.lang), tt("Part volume creation is already running.", self.lang))
            return
        if self.current_volume_scope != "full" or not self.current_specimen_id or self.image_volume is None:
            QMessageBox.information(self, tt("Part extraction", self.lang), tt("Switch to Full volume before confirming ROI.", self.lang))
            return
        roi = self.project.get_part_roi(self.current_specimen_id, self.active_part_roi_id, default=None) if self.active_part_roi_id else None
        try:
            bbox = self._current_part_bbox_for_action()
        except Exception as exc:
            if roi is not None and roi.get("bbox_zyx"):
                bbox = self._clip_bbox_to_shape(roi.get("bbox_zyx", []), self.image_volume.shape)
            else:
                QMessageBox.warning(self, tt("Part extraction", self.lang), str(exc))
                return
        mask_contours = self._full_volume_contours_payload()
        mask_bbox = self._full_volume_contour_bbox(mask_contours)
        if mask_bbox:
            bbox = mask_bbox
        if roi is not None:
            default_part_id = str(roi.get("roi_id", "")).replace("_roi", "") or f"part_{len(self.project.list_parts(self.current_specimen_id)) + 1}"
            default_display_name = str(roi.get("display_name") or default_part_id)
        else:
            default_part_id = f"part_{len(self.project.list_parts(self.current_specimen_id)) + 1}"
            default_display_name = default_part_id
        if not bbox:
            return
        roi_keyframes = self._normalize_roi_keyframes(((roi or {}).get("metadata") or {}).get("roi_keyframes", []) if roi is not None else self.part_roi_keyframes)
        dialog = TifPartNameDialog(
            "Confirm ROI",
            part_id=default_part_id,
            display_name=default_display_name,
            parent=self,
            lang=self.lang,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        part_id, display_name = dialog.values()
        if not part_id:
            return
        request = self._build_confirm_part_roi_request(roi, bbox, part_id, display_name or part_id, roi_keyframes, mask_contours, mask_bbox)
        if self._should_confirm_part_roi_in_background(request):
            self._start_confirm_part_roi_worker(request)
            return
        try:
            result = self._confirm_part_roi_request_sync(request)
        except Exception as exc:
            QMessageBox.warning(self, tt("Part extraction", self.lang), str(exc))
            return
        self._finish_confirm_part_roi_result(result)

    def _ensure_roi_for_created_part(self, part, bbox, display_name=""):
        if not isinstance(part, dict):
            return None
        part_id = part.get("part_id", "")
        if self.active_part_roi_id:
            try:
                return self.project.update_part_roi(
                    self.current_specimen_id,
                    self.active_part_roi_id,
                    bbox_zyx=bbox,
                    status="part_created",
                    linked_part_id=part_id,
                    display_name=display_name or part.get("display_name") or part_id,
                    metadata=self._roi_keyframe_metadata(),
                    save=True,
                )
            except Exception:
                pass
        roi_id = f"{part_id}_roi"
        try:
            return self.project.add_part_roi(
                self.current_specimen_id,
                roi_id,
                display_name=display_name or part.get("display_name") or roi_id,
                bbox_zyx=bbox,
                status="part_created",
                linked_part_id=part_id,
                metadata=self._roi_keyframe_metadata(),
                save=True,
            )
        except ValueError:
            return None

    def _roi_keyframes_to_part_contours(self, keyframes, parent_bbox):
        shape = getattr(self.image_volume, "shape", ()) if self.image_volume is not None else ()
        return _tif_roi_keyframes_to_part_contours(keyframes, parent_bbox, shape)

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
                and self.part_mask_preview_bbox == bbox
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

    def cancel_part_roi_draft(self):
        if not self._guard_backend_write_lock():
            return
        if not self.active_part_roi_id:
            self.part_bbox_edit.clear()
            self.part_roi_keyframes = []
            self.part_mask_keyframes = []
            self.part_preview_mask = None
            self.part_mask_preview_bbox = []
            self.part_mask_preview_accepted = False
            self.render_current_slice()
            return
        roi = self.project.get_part_roi(self.current_specimen_id, self.active_part_roi_id, default=None)
        if roi is not None and roi.get("linked_part_id"):
            QMessageBox.information(self, tt("Part extraction", self.lang), tt("This ROI is linked to a created part and cannot be cancelled here.", self.lang))
            return
        self.project.discard_part_roi(self.current_specimen_id, self.active_part_roi_id)
        message = tt("Cancelled ROI draft {0}.", self.lang).format(self.active_part_roi_id)
        self.active_part_roi_id = ""
        self.part_bbox_edit.clear()
        self.part_roi_keyframes = []
        self.part_mask_keyframes = []
        self.part_preview_mask = None
        self.part_mask_preview_bbox = []
        self.part_mask_preview_accepted = False
        self.training_status_label.setText(message)
        self.log(message)
        self.render_current_slice()

    def delete_current_part_volume(self):
        if not self._guard_backend_write_lock():
            return
        if not self._is_editable_part_volume() or not self.current_specimen_id or not self.current_part_id:
            QMessageBox.information(self, tt("Part extraction", self.lang), tt("Select a part volume before exporting a part package.", self.lang))
            return
        self.delete_part_volume(self.current_specimen_id, self.current_part_id)

    def _release_volume_array(self, array):
        mmap = getattr(array, "_mmap", None)
        if mmap is not None:
            try:
                mmap.close()
            except Exception:
                pass

    def delete_part_volume(self, specimen_id, part_id):
        if not self._guard_backend_write_lock():
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
                for array in (self.image_volume, self.label_volume, self.edit_volume, self.part_mask_volume):
                    self._release_volume_array(array)
                self.image_volume = None
                self.label_volume = None
                self.part_mask_volume = None
                self.edit_volume = None
                self.part_preview_mask = None
                self._clear_volume_preview_cache()
            else:
                self._cancel_volume_preview_build()
            import gc

            gc.collect()
            result = self.project.discard_part(specimen_id, part_id, remove_storage=True, save=False)
            specimen = self.project.get_specimen(specimen_id, default=None)
            if specimen is not None:
                for roi in specimen.get("part_rois", []) or []:
                    if str(roi.get("linked_part_id", "")) == part_id:
                        self.project.update_part_roi(
                            specimen_id,
                            roi.get("roi_id", ""),
                            status="cancelled",
                            linked_part_id="",
                            save=False,
                        )
            self.project.save_project()
        except Exception as exc:
            QMessageBox.warning(self, tt("Part extraction", self.lang), str(exc))
            return False
        if specimen_id == self.current_specimen_id and part_id == self.current_part_id:
            self.part_preview_mask = None
            self.current_part = None
            self.current_part_id = ""
            self.current_volume_scope = "full"
            self._clear_volume_preview_cache()
        self.refresh_project()
        self._select_volume_tree_item(specimen_id, "full", "")
        message = tt("Deleted part volume {0}.", self.lang).format(display_name)
        if not result.get("removed_storage"):
            message = f"{message} Storage was already missing."
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
        bbox = self._parse_part_bbox_text()
        if not bbox and self.part_roi_keyframes:
            bbox = self._roi_keyframe_bbox(self.part_roi_keyframes)
        if not bbox and self.part_mask_keyframes:
            bbox = self._full_volume_contour_bbox()
        if not bbox:
            raise ValueError(tt("Draw an ROI or contour before saving or creating a part.", self.lang))
        return self._clip_bbox_to_shape(bbox, self.image_volume.shape)

    def create_part_from_bbox_dialog(self):
        if not self._guard_backend_write_lock():
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
            self._ensure_roi_for_created_part(part, bbox, display_name=display_name or part_id)
        except Exception as exc:
            QMessageBox.warning(self, tt("Part extraction", self.lang), str(exc))
            return
        self.active_part_roi_id = ""
        self.refresh_project()
        self._populate_volume_roi_source_combo()
        self._select_volume_tree_item(self.current_specimen_id, "part", part.get("part_id", ""))
        message = tt("Created part {0} from bbox {1}.", self.lang).format(part.get("display_name") or part.get("part_id"), part.get("parent_bbox_zyx"))
        self.training_status_label.setText(message)
        self.log(message)

    def _current_part_contours_path(self):
        part = self.project.get_part(self.current_specimen_id, self.current_part_id, default=None)
        if part is None:
            return ""
        return self.project.to_absolute(part.get("contours_path", ""))

    def _current_part_contours(self):
        contours_path = self._current_part_contours_path()
        if not contours_path:
            return {}, ""
        return read_contours_json(contours_path), contours_path

    def _is_legacy_roi_shell_keyframe(self, keyframe):
        if not isinstance(keyframe, dict):
            return False
        author = str(keyframe.get("author") or "")
        source = str(keyframe.get("source") or "")
        return author == "taxamask_roi_shell" or source in {"roi_shell", "roi_key_slice_rectangle"}

    def _part_mask_contours_for_preview(self, contours):
        payload = dict(contours or {})
        keyframes = payload.get("keyframes", []) if isinstance(payload.get("keyframes", []), list) else []
        kept = [item for item in keyframes if isinstance(item, dict) and not self._is_legacy_roi_shell_keyframe(item)]
        ignored = len([item for item in keyframes if isinstance(item, dict) and self._is_legacy_roi_shell_keyframe(item)])
        payload["keyframes"] = kept
        return payload, ignored

    def _normalize_full_volume_mask_keyframes(self, keyframes):
        normalized = []
        shape = tuple(int(value) for value in getattr(self.image_volume, "shape", ()) or ())
        for item in keyframes or []:
            if not isinstance(item, dict) or str(item.get("axis", "z")) != "z":
                continue
            slice_index = self._safe_contour_slice_index(item, None)
            if slice_index is None:
                continue
            if len(shape) == 3 and not (0 <= int(slice_index) < int(shape[0])):
                continue
            polygon = self._dedupe_contour_points(item.get("polygon") or [])
            if len(polygon) < 3:
                continue
            normalized.append(
                {
                    "axis": "z",
                    "slice_index": int(slice_index),
                    "polygon": polygon,
                    "author": str(item.get("author") or "taxamask_ui_freehand"),
                    "source": str(item.get("source") or "manual_freehand"),
                    "created_at": str(item.get("created_at") or datetime.now().astimezone().isoformat(timespec="seconds")),
                }
            )
        normalized.sort(key=lambda item: int(item.get("slice_index", 0)))
        return normalized

    def _format_contour_quality_report(self, report):
        if not isinstance(report, dict):
            return ""
        problems = []
        for item in report.get("errors", []) or []:
            problems.append(str(item.get("message") or item.get("code") or "error"))
        for item in report.get("warnings", []) or []:
            problems.append(str(item.get("message") or item.get("code") or "warning"))
        if not problems:
            return tt("Quality check passed", self.lang)
        return f"{tt('Review warnings', self.lang)}: " + " | ".join(problems[:4])

    def _should_build_part_mask_preview_in_background(self, shape):
        try:
            voxel_count = int(np.prod([max(0, int(value)) for value in (shape or ())], dtype=np.int64))
        except Exception:
            voxel_count = 0
        return voxel_count >= 1_000_000

    def _apply_part_mask_preview_result(self, mask, context):
        context = dict(context or {})
        scope = str(context.get("scope") or self.current_volume_scope or "")
        preview_contours = dict(context.get("preview_contours") or {})
        report = dict(context.get("report") or {})
        bbox = context.get("bbox") or []
        ignored_legacy = int(context.get("ignored_legacy") or 0)
        keyframe_count = int(context.get("keyframe_count") or len(preview_contours.get("keyframes", []) or []))

        self.part_preview_mask = mask
        self.part_mask_preview_accepted = False
        if scope == "full":
            self.part_mask_preview_bbox = bbox
            if bbox:
                self.part_bbox_edit.setText(self._bbox_text(bbox))
                self._autosave_active_part_roi_mask_keyframes(bbox)
        else:
            self.part_mask_preview_bbox = []
            part = self.project.update_part_status(self.current_specimen_id, self.current_part_id, "mask_preview")
            self.current_part = part
            self._update_status_labels(self.project.get_specimen(self.current_specimen_id), part=part)

        self._clear_volume_preview_cache()
        self._set_scope_controls_enabled()
        self.render_current_slice()
        quality = self._format_contour_quality_report(report)
        message = (
            tt("Preview mask generated from {0} key slice(s).", self.lang).format(keyframe_count)
            + "\n"
            + tt("Part mask preview quality: {0}", self.lang).format(quality)
        )
        if scope == "full":
            message = (
                f"{message}\n"
                + tt("Review the preview, then accept it before creating the part volume.", self.lang)
            )
        if ignored_legacy:
            message = (
                f"{message}\n"
                + tt("Ignored {0} legacy ROI shell key slice(s). Use Clear key slices to remove them permanently.", self.lang).format(ignored_legacy)
            )
        self.training_status_label.setText(message)
        self.log(message)

    def _dedupe_contour_points(self, points):
        clean = []
        width = int(self.image_volume.shape[2]) if self.image_volume is not None else 0
        height = int(self.image_volume.shape[1]) if self.image_volume is not None else 0
        for point in points or []:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                continue
            px = float(point[0])
            py = float(point[1])
            if not math.isfinite(px) or not math.isfinite(py):
                continue
            if width > 0:
                px = max(0.0, min(float(width - 1), px))
            if height > 0:
                py = max(0.0, min(float(height - 1), py))
            next_point = [round(px, 3), round(py, 3)]
            if not clean or math.hypot(clean[-1][0] - next_point[0], clean[-1][1] - next_point[1]) >= 0.15:
                clean.append(next_point)
        if len(clean) > 2 and math.hypot(clean[0][0] - clean[-1][0], clean[0][1] - clean[-1][1]) < 0.15:
            clean.pop()
        return clean

    def current_contour_overlay_polygons(self):
        if self.current_volume_scope not in {"full", "part"} or self.image_volume is None:
            return []
        axis, slice_index = self._active_slice_position()
        if self.current_volume_scope == "full":
            contours = self._full_volume_contours_payload()
        else:
            contours_path = self._current_part_contours_path()
            if not contours_path:
                return []
            contours = read_contours_json(contours_path)
        overlays = []
        for keyframe in contours.get("keyframes", []) or []:
            if not isinstance(keyframe, dict):
                continue
            if self._is_legacy_roi_shell_keyframe(keyframe):
                continue
            if str(keyframe.get("axis", "z")) != axis:
                continue
            if self._safe_contour_slice_index(keyframe, None) != int(slice_index):
                continue
            polygon = keyframe.get("polygon") or []
            clean_polygon = self._dedupe_contour_points(polygon)
            if len(clean_polygon) >= 3:
                overlays.append({"polygon": clean_polygon, "color": "#FF8C42", "fill_alpha": 30})
        return overlays

    def finish_part_contour_drag(self, points):
        if not self.is_part_contour_draw_mode() or self.image_volume is None:
            return
        polygon = self._dedupe_contour_points(points)
        if len(polygon) < 3:
            message = tt("Contour needs at least 3 points.", self.lang)
            self.training_status_label.setText(message)
            self.log(message)
            return
        if self.current_volume_scope == "full":
            contours = self._full_volume_contours_payload()
            slice_index = int(self.slice_slider.value())
            try:
                contours = add_polygon_keyframe(
                    contours,
                    slice_index,
                    polygon,
                    axis="z",
                    author="taxamask_ui_freehand",
                    source="manual_freehand",
                )
            except Exception as exc:
                QMessageBox.warning(self, tt("Part extraction", self.lang), str(exc))
                return
            self.part_mask_keyframes = list(contours.get("keyframes", []) or [])
            bbox = self._full_volume_contour_bbox(contours)
            if bbox:
                self.part_bbox_edit.setText(self._bbox_text(bbox))
                self._autosave_active_part_roi_mask_keyframes(bbox)
            self.part_preview_mask = None
            self.part_mask_preview_bbox = []
            self.part_mask_preview_accepted = False
            self.render_current_slice()
            message = tt("Contour saved at Z {0}.", self.lang).format(slice_index)
            self.training_status_label.setText(message)
            self.log(message)
            return
        if not self._is_editable_part_volume():
            return
        contours, contours_path = self._current_part_contours()
        if not contours_path:
            return
        slice_index = int(self.slice_slider.value())
        try:
            contours = add_polygon_keyframe(
                contours,
                slice_index,
                polygon,
                axis="z",
                author="taxamask_ui_freehand",
                source="manual_freehand",
            )
            write_contours_json(contours_path, contours)
            part = self.project.update_part_status(self.current_specimen_id, self.current_part_id, "draft")
        except Exception as exc:
            QMessageBox.warning(self, tt("Part extraction", self.lang), str(exc))
            return
        self.current_part = part
        self.part_preview_mask = None
        self._update_status_labels(self.project.get_specimen(self.current_specimen_id), part=part)
        self.render_current_slice()
        message = tt("Contour saved at Z {0}.", self.lang).format(slice_index)
        self.training_status_label.setText(message)
        self.log(message)

    def delete_current_part_keyframe(self):
        if not self._guard_backend_write_lock():
            return
        if self.current_volume_scope not in {"full", "part"} or self.image_volume is None:
            QMessageBox.information(self, tt("Part extraction", self.lang), tt("Select a full volume or part volume before editing part masks.", self.lang))
            return
        if self._current_slice_axis() != "z":
            QMessageBox.information(self, tt("Part extraction", self.lang), tt("Contour drawing currently uses Z slices.", self.lang))
            return
        slice_index = int(self.slice_slider.value())
        if self.current_volume_scope == "full":
            contours, deleted = delete_keyframe(self._full_volume_contours_payload(), slice_index, axis="z")
            if not deleted:
                message = tt("No contour exists at Z {0}.", self.lang).format(slice_index)
                self.training_status_label.setText(message)
                self.log(message)
                return
            self.part_mask_keyframes = list(contours.get("keyframes", []) or [])
            bbox = self._full_volume_contour_bbox(contours)
            if not bbox and self.part_roi_keyframes:
                bbox = self._roi_keyframe_bbox(self.part_roi_keyframes)
            self.part_bbox_edit.setText(self._bbox_text(bbox))
            if bbox:
                self._autosave_active_part_roi_mask_keyframes(bbox)
            self.part_preview_mask = None
            self.part_mask_preview_bbox = []
            self.part_mask_preview_accepted = False
            self.render_current_slice()
            message = tt("Deleted contour at Z {0}.", self.lang).format(slice_index)
            self.training_status_label.setText(message)
            self.log(message)
            return
        if not self._is_editable_part_volume():
            return
        contours, contours_path = self._current_part_contours()
        if not contours_path:
            return
        contours, deleted = delete_keyframe(contours, slice_index, axis="z")
        if not deleted:
            message = tt("No contour exists at Z {0}.", self.lang).format(slice_index)
            self.training_status_label.setText(message)
            self.log(message)
            return
        write_contours_json(contours_path, contours)
        part = self.project.update_part_status(self.current_specimen_id, self.current_part_id, "draft")
        self.current_part = part
        self.part_preview_mask = None
        self._update_status_labels(self.project.get_specimen(self.current_specimen_id), part=part)
        self.render_current_slice()
        message = tt("Deleted contour at Z {0}.", self.lang).format(slice_index)
        self.training_status_label.setText(message)
        self.log(message)

    def clear_part_mask_keyframes(self):
        if not self._guard_backend_write_lock():
            return False
        if self.current_volume_scope not in {"full", "part"} or self.image_volume is None:
            QMessageBox.information(self, tt("Part extraction", self.lang), tt("Select a full volume or part volume before editing part masks.", self.lang))
            return False
        if self.current_volume_scope == "full":
            keyframes = [item for item in self.part_mask_keyframes if isinstance(item, dict)]
            if not keyframes and self.part_preview_mask is None:
                message = tt("No part key slices to clear.", self.lang)
                self.training_status_label.setText(message)
                self.log(message)
                return False
            response = QMessageBox.question(
                self,
                tt("Part extraction", self.lang),
                tt(
                    "Clear all key slices for the current full-volume part draft? This removes the hand-drawn mask draft but keeps the ROI bbox.",
                    self.lang,
                ),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if response != QMessageBox.Yes:
                return False
            self.part_mask_keyframes = []
            self.part_preview_mask = None
            self.part_mask_preview_bbox = []
            self.part_mask_preview_accepted = False
            bbox = self._roi_keyframe_bbox(self.part_roi_keyframes) if self.part_roi_keyframes else []
            if bbox:
                self.part_bbox_edit.setText(self._bbox_text(bbox))
            else:
                try:
                    bbox = self._parse_part_bbox_text()
                except Exception:
                    bbox = []
            if self.active_part_roi_id:
                if bbox:
                    self._autosave_active_part_roi_bbox(bbox)
            self.render_current_slice()
            message = tt("Cleared {0} key slice(s) and reset the part mask draft.", self.lang).format(len(keyframes))
            self.training_status_label.setText(message)
            self.log(message)
            return True
        if not self._is_editable_part_volume():
            return False
        part = self.project.get_part(self.current_specimen_id, self.current_part_id, default=None)
        contours, contours_path = self._current_part_contours()
        if part is None or not contours_path:
            return False
        keyframes = [item for item in (contours.get("keyframes", []) or []) if isinstance(item, dict)]
        if not keyframes and self.part_preview_mask is None and not self._active_part_mask_has_voxels():
            message = tt("No part key slices to clear.", self.lang)
            self.training_status_label.setText(message)
            self.log(message)
            return False
        display_name = part.get("display_name") or part.get("part_id") or self.current_part_id
        response = QMessageBox.question(
            self,
            tt("Part extraction", self.lang),
            tt(
                "Clear all key slices for part {0}? This removes saved mask key slices and the current auto-fill preview, but keeps the cropped part image.",
                self.lang,
            ).format(display_name),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if response != QMessageBox.Yes:
            return False
        try:
            contours["keyframes"] = []
            write_contours_json(contours_path, contours)
            mask_path = self._current_part_mask_path()
            if mask_path and volume_sidecar_exists(mask_path):
                target = load_volume_sidecar(mask_path, mmap_mode="r+")
                try:
                    target[:] = 0
                    metadata = flush_volume_array(mask_path, target)
                finally:
                    mmap_handle = getattr(target, "_mmap", None)
                    if mmap_handle is not None:
                        mmap_handle.close()
                part.setdefault("mask", {}).update(
                    {
                        "shape_zyx": metadata.get("shape_zyx", []),
                        "dtype": metadata.get("dtype", ""),
                        "spacing_zyx": metadata.get("spacing_zyx", []),
                        "spacing_unit": metadata.get("spacing_unit", "micrometer"),
                        "orientation": metadata.get("orientation", "unknown"),
                    }
                )
            metadata_payload = part.setdefault("metadata", {})
            metadata_payload["part_mask_keyframes_cleared_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
            metadata_payload["part_mask_keyframes_cleared_count"] = len(keyframes)
            part = self.project.update_part_status(self.current_specimen_id, self.current_part_id, "roi_confirmed", save=False)
            self.project.save_project()
        except Exception as exc:
            QMessageBox.warning(self, tt("Part extraction", self.lang), str(exc))
            return False
        self.current_part = part
        self.part_preview_mask = None
        self.edit_volume = None
        self._clear_volume_preview_cache()
        self._reload_label_volume()
        self._update_status_labels(self.project.get_specimen(self.current_specimen_id), part=part)
        self.render_current_slice()
        message = tt("Cleared {0} key slice(s) and reset the part mask draft.", self.lang).format(len(keyframes))
        self.training_status_label.setText(message)
        self.log(message)
        return True

    def jump_part_keyframe(self, direction):
        if self.current_volume_scope not in {"full", "part"} or self.image_volume is None:
            return
        if self._current_slice_axis() != "z":
            QMessageBox.information(self, tt("Part extraction", self.lang), tt("Contour drawing currently uses Z slices.", self.lang))
            return
        if self.current_volume_scope == "full":
            contours = self._full_volume_contours_payload()
        else:
            if not self._is_editable_part_volume():
                return
            contours, _contours_path = self._current_part_contours()
        neighbors = neighboring_keyframe_indices(contours, int(self.slice_slider.value()), axis="z")
        target = neighbors.get("previous" if direction == "previous" else "next")
        if target is None:
            message = tt("No previous key slice." if direction == "previous" else "No next key slice.", self.lang)
            self.training_status_label.setText(message)
            self.log(message)
            return
        self.slice_slider.setValue(int(target))
        self.render_current_slice()

    def _part_keyframe_bbox_yx(self):
        if self.image_volume is None:
            return []
        height = int(self.image_volume.shape[1])
        width = int(self.image_volume.shape[2])
        y_margin = max(0, int(round(height * 0.18)))
        x_margin = max(0, int(round(width * 0.18)))
        return [[y_margin, max(y_margin + 1, height - y_margin)], [x_margin, max(x_margin + 1, width - x_margin)]]

    def add_current_rect_keyframe(self):
        if not self._guard_backend_write_lock():
            return
        if not self._is_editable_part_volume() or self.image_volume is None:
            QMessageBox.information(self, tt("Part extraction", self.lang), tt("Select a part volume before editing part masks.", self.lang))
            return
        if self._current_slice_axis() != "z":
            QMessageBox.information(self, tt("Part extraction", self.lang), tt("Key-slice mask preview currently uses Z slices.", self.lang))
            return
        contours_path = self._current_part_contours_path()
        if not contours_path:
            return
        contours = read_contours_json(contours_path)
        contours = add_rectangular_keyframe(
            contours,
            int(self.slice_slider.value()),
            self._part_keyframe_bbox_yx(),
            author="taxamask_ui_rect",
        )
        write_contours_json(contours_path, contours)
        part = self.project.update_part_status(self.current_specimen_id, self.current_part_id, "draft")
        self.current_part = part
        self.part_preview_mask = None
        self._clear_volume_preview_cache()
        self._update_status_labels(self.project.get_specimen(self.current_specimen_id), part=part)
        self.render_current_slice()
        message = tt("Added rectangular key slice at Z {0}.", self.lang).format(int(self.slice_slider.value()))
        self.training_status_label.setText(message)
        self.log(message)

    def preview_part_mask_from_keyframes(self):
        if not self._guard_backend_write_lock():
            return
        if self._part_mask_preview_running():
            QMessageBox.information(self, tt("Part extraction", self.lang), tt("Preview auto fill is already running.", self.lang))
            return
        if self.current_volume_scope not in {"full", "part"} or self.image_volume is None:
            QMessageBox.information(self, tt("Part extraction", self.lang), tt("Select a full volume or part volume before previewing masks.", self.lang))
            return
        if self.current_volume_scope == "full":
            contours = self._full_volume_contours_payload()
            bbox = self._full_volume_contour_bbox(contours)
            if not bbox:
                QMessageBox.warning(self, tt("Part extraction", self.lang), tt("Draw at least one contour before previewing masks.", self.lang))
                return
            local_contours = self._full_volume_contours_to_local(contours, bbox)
            shape = tuple(int(pair[1]) - int(pair[0]) for pair in bbox)
            preview_contours, ignored_legacy = self._part_mask_contours_for_preview(local_contours)
            report = validate_contours_for_interpolation(preview_contours, shape, axis="z")
            if not report.get("ok"):
                QMessageBox.warning(self, tt("Part extraction", self.lang), self._format_contour_quality_report(report))
                return
            context = {
                "scope": "full",
                "preview_contours": preview_contours,
                "report": report,
                "bbox": bbox,
                "ignored_legacy": ignored_legacy,
                "keyframe_count": len(preview_contours.get("keyframes", []) or []),
            }
            if self._should_build_part_mask_preview_in_background(shape):
                self.part_preview_mask = None
                self.part_mask_preview_bbox = []
                self.part_mask_preview_accepted = False
                self._set_scope_controls_enabled()
                self.training_status_label.setText(tt("Preview auto fill is running...", self.lang))
                self._start_part_mask_preview_build(preview_contours, shape, context)
                return
            try:
                mask = build_preview_mask_from_contours(preview_contours, shape)
            except Exception as exc:
                QMessageBox.warning(self, tt("Part extraction", self.lang), str(exc))
                return
            self._apply_part_mask_preview_result(mask, context)
            return
        if not self._is_editable_part_volume():
            return
        contours_path = self._current_part_contours_path()
        contours = read_contours_json(contours_path)
        preview_contours, ignored_legacy = self._part_mask_contours_for_preview(contours)
        report = validate_contours_for_interpolation(preview_contours, self.image_volume.shape, axis="z")
        if not report.get("ok"):
            QMessageBox.warning(self, tt("Part extraction", self.lang), self._format_contour_quality_report(report))
            return
        context = {
            "scope": "part",
            "preview_contours": preview_contours,
            "report": report,
            "ignored_legacy": ignored_legacy,
            "keyframe_count": len(preview_contours.get("keyframes", []) or []),
        }
        if self._should_build_part_mask_preview_in_background(self.image_volume.shape):
            self.part_preview_mask = None
            self.part_mask_preview_bbox = []
            self.part_mask_preview_accepted = False
            self._set_scope_controls_enabled()
            self.training_status_label.setText(tt("Preview auto fill is running...", self.lang))
            self._start_part_mask_preview_build(preview_contours, self.image_volume.shape, context)
            return
        try:
            mask = build_preview_mask_from_contours(preview_contours, self.image_volume.shape)
        except Exception as exc:
            QMessageBox.warning(self, tt("Part extraction", self.lang), str(exc))
            return
        self._apply_part_mask_preview_result(mask, context)

    def accept_part_mask_preview(self):
        if not self._guard_backend_write_lock():
            return False
        if self.current_volume_scope == "full":
            if self.part_preview_mask is None:
                return
            self.part_mask_preview_accepted = True
            self._set_scope_controls_enabled()
            self.render_current_slice()
            message = (
                tt("Accepted part mask.", self.lang)
                + "\n"
                + tt("Use Confirm ROI to create the part volume with this accepted mask.", self.lang)
            )
            self.training_status_label.setText(message)
            self.log(message)
            return
        if not self._is_editable_part_volume() or self.part_preview_mask is None:
            return
        part = self.project.get_part(self.current_specimen_id, self.current_part_id, default=None)
        if part is None:
            return
        try:
            metadata = write_part_mask(self.project, part, self.part_preview_mask)
            part["mask"].update(
                {
                    "shape_zyx": metadata.get("shape_zyx", []),
                    "dtype": metadata.get("dtype", ""),
                    "spacing_zyx": metadata.get("spacing_zyx", []),
                    "spacing_unit": metadata.get("spacing_unit", "micrometer"),
                    "orientation": metadata.get("orientation", "unknown"),
                }
            )
            part = self.project.update_part_status(self.current_specimen_id, self.current_part_id, "reviewed")
            self.project.save_project()
        except Exception as exc:
            QMessageBox.warning(self, tt("Part extraction", self.lang), str(exc))
            return
        self.part_preview_mask = None
        self._reload_part_mask_volume()
        self._clear_volume_preview_cache()
        self.current_part = part
        self._reload_label_volume()
        self._update_status_labels(self.project.get_specimen(self.current_specimen_id), part=part)
        self.render_current_slice()
        message = tt("Accepted part mask.", self.lang)
        self.training_status_label.setText(message)
        self.log(message)

    def clear_part_mask_preview(self):
        if not self._guard_backend_write_lock():
            return
        self.part_preview_mask = None
        self.part_mask_preview_bbox = []
        self.part_mask_preview_accepted = False
        self._clear_volume_preview_cache()
        if self.current_volume_scope == "full":
            self.render_current_slice()
            return
        part = self.project.get_part(self.current_specimen_id, self.current_part_id, default=None)
        if part is not None:
            self.current_part = part
            self._update_status_labels(self.project.get_specimen(self.current_specimen_id), part=part)
        self.render_current_slice()

    def import_external_prediction_tif_dialog(self):
        if not self._guard_backend_write_lock():
            return
        if not self._ensure_tif_project_open():
            return
        if not self.current_specimen_id:
            QMessageBox.warning(
                self,
                tt("Import External Label TIF", self.lang),
                tt("Please select a specimen with a working volume first.", self.lang),
            )
            return
        specimen_id = self.current_specimen_id
        specimen = self.project.get_specimen(specimen_id, default=None)
        working = (specimen or {}).get("working_volume") or {}
        if not working.get("path") or not volume_sidecar_exists(self.project.to_absolute(working.get("path", ""))):
            QMessageBox.warning(
                self,
                tt("Import External Label TIF", self.lang),
                tt("Please select a specimen with a working volume first.", self.lang),
            )
            return
        labels = specimen.get("labels") or {}
        current_edit = labels.get("working_edit") or {}
        if str(current_edit.get("path") or "").strip():
            reply = QMessageBox.question(
                self,
                tt("Import External Label TIF", self.lang),
                tt("This predict run will overwrite the current editable result for selected target(s), but will not overwrite training truth. Continue?", self.lang),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
        tif_path, _ = QFileDialog.getOpenFileName(
            self,
            tt("Import External Label TIF", self.lang),
            "",
            "TIF/TIFF (*.tif *.tiff)",
        )
        if not tif_path:
            return
        prediction_id, ok = QInputDialog.getText(
            self,
            tt("Import External Label TIF", self.lang),
            tt("Prediction ID:", self.lang),
            text=default_prediction_id_for_tif(tif_path),
        )
        if not ok or not prediction_id:
            return
        source_model, ok = QInputDialog.getText(
            self,
            tt("Import External Label TIF", self.lang),
            tt("Source model:", self.lang),
            text="nnUNet",
        )
        if not ok:
            return
        try:
            result = import_external_prediction_tif(
                self.project,
                specimen_id,
                tif_path,
                prediction_id=prediction_id,
                source_model=source_model or "external_tif",
            )
        except Exception as exc:
            QMessageBox.critical(self, tt("Import External Label TIF", self.lang), str(exc))
            return
        self.refresh_project()
        self._select_specimen_after_import(specimen_id)
        index = self.label_role_combo.findData("working_edit")
        if index >= 0:
            self.label_role_combo.setCurrentIndex(index)
        self.load_specimen(specimen_id)
        report_path = result.get("report_path", "")
        message = tt("Imported external label TIF as editable review result for specimen {0}. Report: {1}", self.lang).format(specimen_id, report_path)
        self.training_status_label.setText(message)
        self.log(message)

    def _selected_specimen_ids_for_action(self, action):
        result = self.backend_workflow_service.selected_specimen_ids_for_action(
            action,
            current_specimen_id=self.current_specimen_id,
        )
        if result:
            return result.payload.get("specimen_ids", [])
        if action in {"prepare_dataset", "train"}:
            raise ValueError(tt("No train-ready top-level volumes are available.", self.lang))
        raise ValueError(tt("No top-level volume is available for prediction.", self.lang))

    def _format_train_ready_reasons(self, reasons):
        labels = {
            "manual_truth_missing": "Training truth is missing; accept the current editable labels as training truth first.",
            "part_not_marked_train_ready": "Part has not been marked as verified train-ready.",
            "part_record_missing": "Part record is missing.",
            "part_volume_missing": "Part image is missing.",
            "reslice_record_missing": "Reslice record is missing.",
            "reslice_output_missing": "Reslice image is missing.",
            "label_schema_missing": "Label schema is missing or empty.",
            "part_label_shape_mismatch": "Part label shape does not match the part/reslice image.",
            "unknown_label_ids": "Label IDs are not all defined in the bound label schema.",
            "label_volume_unreadable": "Label volume cannot be read.",
            "specimen_not_marked_train_ready": "Specimen has not been marked train-ready.",
            "working_volume_missing": "Working image is missing.",
            "material_map_missing": "Material map is missing.",
            "image_label_shape_mismatch": "Image and label shapes do not match.",
            "no_trainable_material": "No trainable material is defined in the material map.",
        }
        readable = []
        for reason in reasons or []:
            text = str(reason or "").strip()
            if not text:
                continue
            key = text.split(":", 1)[0]
            label = tt(labels.get(key, text), self.lang)
            if ":" in text and key in labels:
                label = f"{label} ({text.split(':', 1)[1]})"
            readable.append(label)
        return readable

    def _part_training_readiness_reports(self, prefer_current=False, limit=4):
        reports = []
        if prefer_current and self.current_specimen_id and self.current_part_id:
            try:
                readiness = self.project.evaluate_part_train_ready(
                    self.current_specimen_id,
                    self.current_part_id,
                    self.current_reslice_id,
                    validate_label_ids=False,
                )
            except Exception as exc:
                readiness = {
                    "specimen_id": self.current_specimen_id,
                    "part_id": self.current_part_id,
                    "reslice_id": self.current_reslice_id,
                    "train_ready": False,
                    "reasons": [str(exc)],
                }
            reports.append(readiness)
            return reports
        for specimen in self.project.project_data.get("specimens", []) or []:
            if not isinstance(specimen, dict):
                continue
            specimen_id = str(specimen.get("specimen_id") or "")
            for part in specimen.get("parts", []) or []:
                if not isinstance(part, dict):
                    continue
                part_id = str(part.get("part_id") or "")
                if not specimen_id or not part_id:
                    continue
                try:
                    readiness = self.project.evaluate_part_train_ready(specimen_id, part_id, validate_label_ids=False)
                except Exception as exc:
                    readiness = {
                        "specimen_id": specimen_id,
                        "part_id": part_id,
                        "reslice_id": "",
                        "train_ready": False,
                        "reasons": [str(exc)],
                    }
                reports.append(readiness)
                if len(reports) >= int(limit):
                    return reports
        return reports

    def _top_level_training_readiness_reports(self, limit=4):
        reports = []
        for specimen in self.project.project_data.get("specimens", []) or []:
            if not isinstance(specimen, dict):
                continue
            specimen_id = str(specimen.get("specimen_id") or "")
            if not specimen_id:
                continue
            try:
                readiness = self.project.evaluate_train_ready(specimen_id)
            except Exception as exc:
                readiness = {
                    "specimen_id": specimen_id,
                    "train_ready": False,
                    "reasons": [str(exc)],
                }
            reports.append(readiness)
            if len(reports) >= int(limit):
                break
        return reports

    def _summarize_training_readiness_reports(self, title, reports, empty_message, all_ready_message, scope, limit=4):
        lines = [tt(title, self.lang)]
        if not reports:
            lines.append(f"- {tt(empty_message, self.lang)}")
            return lines
        blocked_count = 0
        for report in reports[: int(limit)]:
            if report.get("train_ready"):
                continue
            blocked_count += 1
            if scope == "part":
                label = self._format_part_ref_label(report) or "-"
            else:
                label = str(report.get("specimen_id") or "-")
            reasons = self._format_train_ready_reasons(report.get("reasons") or [])
            detail = "; ".join(reasons) if reasons else "-"
            lines.append(f"- {label}: {tt('Missing: {0}', self.lang).format(detail)}")
        if blocked_count == 0:
            lines.append(f"- {tt(all_ready_message, self.lang)}")
        remaining = max(0, len(reports) - int(limit))
        if remaining:
            lines.append(f"- {tt('+{0} more', self.lang).format(remaining)}")
        return lines

    def _training_reports_need_truth_acceptance(self, reports):
        for report in reports or []:
            reasons = {str(item).split(":", 1)[0] for item in (report.get("reasons") or [])}
            if reasons.intersection({"manual_truth_missing", "part_not_marked_train_ready"}):
                return True
        return False

    def _training_selection_error(self, prefer_part=False):
        if prefer_part:
            part_reports = self._part_training_readiness_reports(prefer_current=True, limit=4)
            lines = [tt("Current part/reslice is not train-ready yet.", self.lang), ""]
            lines.extend(
                self._summarize_training_readiness_reports(
                    "Part readiness",
                    part_reports,
                    "No project part volumes are available.",
                    "All checked part samples are train-ready.",
                    "part",
                )
            )
            if self._training_reports_need_truth_acceptance(part_reports):
                lines.extend(["", tt("Next step: save current labels, then click Accept as training truth in Label review. Training uses reviewed manual_truth only; editable labels are not sent to training directly.", self.lang)])
            return "\n".join(lines)
        part_reports = self._part_training_readiness_reports(prefer_current=False, limit=4)
        top_reports = self._top_level_training_readiness_reports(limit=4)
        lines = [tt("No train-ready samples are available for training.", self.lang), ""]
        lines.extend(
            self._summarize_training_readiness_reports(
                "Part readiness",
                part_reports,
                "No project part volumes are available.",
                "All checked part samples are train-ready.",
                "part",
            )
        )
        lines.append("")
        lines.extend(
            self._summarize_training_readiness_reports(
                "Top-level readiness",
                top_reports,
                "No top-level volume records are available.",
                "All checked top-level volumes are train-ready.",
                "top",
            )
        )
        if self._training_reports_need_truth_acceptance(part_reports):
            lines.extend(["", tt("Next step: save current labels, then click Accept as training truth in Label review. Training uses reviewed manual_truth only; editable labels are not sent to training directly.", self.lang)])
        return "\n".join(lines)

    def _selected_backend_samples_for_action(self, action):
        return self.backend_panel_controller.selected_backend_samples_for_action(action)

    def _selected_backend_samples_for_action_legacy(self, action):
        if action in {"prepare_dataset", "train"}:
            if self.current_volume_scope == "part" and self.current_specimen_id and self.current_part_id:
                current_reports = self._part_training_readiness_reports(prefer_current=True, limit=1)
                if not current_reports or not current_reports[0].get("train_ready"):
                    raise ValueError(self._training_selection_error(prefer_part=True))
            part_refs = self._train_ready_part_refs()
            if part_refs:
                return {
                    "input_scope": "part_reslice",
                    "part_refs": part_refs,
                    "specimen_ids": [],
                    "fallback_reason": "",
                }
            if self.current_volume_scope == "part":
                raise ValueError(self._training_selection_error(prefer_part=True))
            specimen_ids = [item.get("specimen_id") for item in self.project.list_train_ready_specimens()]
            if specimen_ids:
                return {
                    "input_scope": "top_level_volume",
                    "part_refs": [],
                    "specimen_ids": specimen_ids,
                    "fallback_reason": tt("No train-ready parts are available.", self.lang),
                }
            raise ValueError(self._training_selection_error(prefer_part=False))
        try:
            part_refs = self._selected_part_refs_for_action(action)
        except Exception as part_exc:
            if self.current_volume_scope != "part":
                specimen_ids = self._selected_specimen_ids_for_action(action)
                return {
                    "input_scope": "top_level_volume",
                    "part_refs": [],
                    "specimen_ids": specimen_ids,
                    "fallback_reason": str(part_exc),
                }
            raise
        return {
            "input_scope": "part_reslice",
            "part_refs": part_refs,
            "specimen_ids": [],
            "fallback_reason": "",
        }

    def _train_ready_part_refs(self):
        return self.backend_workflow_service.train_ready_part_refs()

    def _selected_part_refs_for_action(self, action):
        refs = []
        if action in {"prepare_dataset", "train"}:
            refs = self._train_ready_part_refs()
            if not refs:
                raise ValueError(self._training_selection_error(prefer_part=(self.current_volume_scope == "part")))
            return refs
        self._sync_predict_selection_from_table()
        for key in sorted(self._tif_predict_selected_refs):
            ref = self._predict_ref_from_key(key)
            if ref["specimen_id"] and ref["part_id"]:
                readiness = self.project.evaluate_part_predict_ready(ref["specimen_id"], ref["part_id"], ref.get("reslice_id", ""))
                if not readiness.get("predict_ready"):
                    raise ValueError(tt("Selected prediction target is incomplete: {0}", self.lang).format(", ".join(readiness.get("reasons") or [])))
                ref["reslice_id"] = readiness.get("reslice_id", ref.get("reslice_id", ""))
                refs.append(ref)
        if not refs:
            raise ValueError(tt("Select at least one prediction target.", self.lang))
        return refs

    def _validated_predict_model_manifest(self):
        manifest = str(self.backend_config.get("model_manifest") or self.backend_manifest_edit.text() or "").strip()
        if not manifest:
            raise ValueError(tt("Select a model manifest before prediction.", self.lang))
        candidate = manifest
        if not os.path.isabs(candidate):
            candidate = self.project.to_absolute(candidate) if self.project.project_dir else os.path.abspath(candidate)
        candidate = os.path.abspath(candidate)
        if not os.path.exists(candidate):
            raise ValueError(tt("Model manifest does not exist: {0}", self.lang).format(manifest))
        self.backend_manifest_edit.setText(candidate)
        self.backend_config["model_manifest"] = candidate
        return candidate

    def _selected_part_refs_for_review_acceptance(self):
        self._sync_predict_selection_from_table()
        refs = []
        for key in sorted(self._tif_predict_selected_refs):
            ref = self._predict_ref_from_key(key)
            if ref["specimen_id"] and ref["part_id"]:
                refs.append(ref)
        return refs

    def _format_part_ref_label(self, ref):
        specimen_id = str((ref or {}).get("specimen_id") or "")
        part_id = str((ref or {}).get("part_id") or "")
        reslice_id = str((ref or {}).get("reslice_id") or "")
        label = f"{specimen_id}:{part_id}" if specimen_id or part_id else ""
        return f"{label}:{reslice_id}" if label and reslice_id else label

    def _summarize_review_blockers(self, blocked, limit=4):
        parts = []
        for item in blocked or []:
            label = self._format_part_ref_label(item)
            report = item.get("report") if isinstance(item.get("report"), dict) else {}
            reasons = self._format_review_reasons(report) or ", ".join(str(reason) for reason in (item.get("reasons") or []))
            detail = self._format_review_blocker_detail(report) if report else ""
            parts.append(f"{label} [{reasons}; {detail}]" if detail else f"{label} [{reasons}]")
        if len(parts) > int(limit):
            parts = parts[: int(limit)] + [f"+{len(blocked) - int(limit)}"]
        return "; ".join(parts)

    def _split_review_acceptance_refs(self, refs):
        result = self.truth_promotion_service.split_review_acceptance_refs(
            refs,
            require_opened_for_review=False,
        )
        report = result.payload.get("report", {}) if result else {}
        ready = list(report.get("ready") or [])
        not_opened = list(report.get("not_opened") or [])
        blocked = list(report.get("blocked") or [])
        return ready, not_opened, blocked

    def accept_selected_ai_results(self):
        if not self._guard_backend_write_lock():
            return False
        if self.current_volume_scope == "part" and self.working_edit_dirty:
            message = tt("Save current labels before accepting selected AI results.", self.lang)
            self._set_operation_feedback(message)
            QMessageBox.information(self, tt("Accept working edit", self.lang), message)
            return False
        refs = self._selected_part_refs_for_review_acceptance()
        if not refs:
            QMessageBox.warning(self, tt("Accept working edit", self.lang), tt("No selected editable AI result is ready for acceptance.", self.lang))
            return False
        try:
            ready, not_opened, blocked = self._split_review_acceptance_refs(refs)
        except Exception as exc:
            QMessageBox.warning(self, tt("Accept working edit", self.lang), str(exc))
            return False
        if blocked:
            message = tt("Selected editable AI result(s) have label/schema problems: {0}", self.lang).format(self._summarize_review_blockers(blocked))
            QMessageBox.warning(self, tt("Accept working edit", self.lang), message)
            self._set_operation_feedback(message)
            return False
        if not ready:
            QMessageBox.warning(self, tt("Accept working edit", self.lang), tt("No selected editable AI result is ready for acceptance.", self.lang))
            return False
        if not_opened:
            reply = QMessageBox.question(
                self,
                tt("Accept working edit", self.lang),
                tt("Some selected editable AI result(s) have not been opened for review. Accept them as training truth anyway?", self.lang),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return False
        reply = QMessageBox.question(
            self,
            tt("Accept working edit", self.lang),
            tt("Accept {0} selected editable AI result(s) as training truth?", self.lang).format(len(ready)),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return False
        try:
            service_result = self.truth_promotion_service.promote_reviewed_refs(
                ready,
                require_opened_for_review=False,
                save=True,
            )
        except Exception as exc:
            QMessageBox.warning(self, tt("Accept working edit", self.lang), str(exc))
            return False
        if not service_result:
            message = service_result.message or ", ".join(service_result.reasons or [])
            QMessageBox.warning(self, tt("Accept working edit", self.lang), message)
            return False
        result = service_result.payload.get("result", {})
        self.refresh_project()
        if self.current_specimen_id and self.current_part_id:
            self._select_volume_tree_item(
                self.current_specimen_id,
                "part_reslice" if self.current_reslice_id else "part",
                self.current_part_id,
                self.current_reslice_id,
            )
        message = tt("Accepted {0} editable AI result(s) as training truth.", self.lang).format(result.get("count", 0))
        self._set_operation_feedback(message)
        return True

    def _predict_will_overwrite_editable_result(self, part_refs=None, specimen_ids=None, input_scope="part_reslice"):
        result = self.backend_workflow_service.predict_will_overwrite_editable_result(
            part_refs=part_refs,
            specimen_ids=specimen_ids,
            input_scope=input_scope,
        )
        return bool(result.payload.get("overwrite"))

    def _confirm_predict_overwrite_if_needed(self, part_refs=None, specimen_ids=None, input_scope="part_reslice"):
        if not self._predict_will_overwrite_editable_result(part_refs=part_refs, specimen_ids=specimen_ids, input_scope=input_scope):
            return True
        reply = QMessageBox.question(
            self,
            tt("TIF backend", self.lang),
            tt("This predict run will overwrite the current editable result for selected target(s), but will not overwrite training truth. Continue?", self.lang),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return reply == QMessageBox.Yes

    def _start_backend_status(self, action, part_refs=None, specimen_ids=None, input_scope="part_reslice"):
        self._tif_backend_action = str(action or "")
        self._tif_backend_started_mono = time.monotonic()
        self._tif_backend_run_dir = ""
        self._tif_backend_result_json = ""
        self._tif_backend_last_result = None
        self._tif_backend_progress_value = 0
        self.backend_progress_bar.setRange(0, 100)
        self.backend_progress_bar.setValue(0)
        self.backend_progress_bar.setFormat("%p%")
        self.backend_log_tail.clear()
        if action == "train":
            self._set_training_result_summary(None)
        status = tt("Running {0}...", self.lang).format(action)
        if str(input_scope or "") == "top_level_volume":
            detail = tt("{0} {1} top-level volume(s).", self.lang).format(status, len(specimen_ids or []))
        else:
            detail = tt("{0} {1} part sample(s).", self.lang).format(status, len(part_refs or []))
        self.backend_run_status_label.setText(detail)
        self.training_status_label.setText(detail)
        self.backend_elapsed_label.setText(tt("Elapsed: {0}", self.lang).format("00:00"))
        self.backend_elapsed_timer.start()
        self._set_backend_controls_running(True)
        self._set_backend_write_locked_controls(True)
        self._sync_undo_redo_buttons()
        self.log(detail)

    def _on_tif_backend_progress(self, current, total, message):
        return self.backend_panel_controller.on_backend_progress(current, total, message)

    def _backend_failure_summary(self, text, action=None):
        raw = str(text or "")
        lower = raw.lower()
        action_text = str(action or self._tif_backend_action or "").strip() or tt("backend task", self.lang)
        if "_cancelled" in lower:
            return tt("Run cancelled: {0}", self.lang).format(action_text)
        if "nnunet_training_requires_at_least_2_samples" in lower:
            count = "0"
            marker = "nnunet_training_requires_at_least_2_samples:"
            tail = raw.split(marker, 1)[1] if marker in raw else ""
            if tail:
                count = tail.split()[0].split(":")[0].strip() or "0"
            return tt("Training needs at least 2 accepted training samples; current selection has {0}.", self.lang).format(count)
        if "nnunet_command_not_found" in lower:
            return tt("nnU-Net command was not found in the selected backend Python environment.", self.lang)
        if "nnunet_command_failed" in lower:
            return tt("nnU-Net command failed. Open the run folder and check nnunet_v2_commands.log.", self.lang)
        if "tif_backend_train_failed" in lower:
            return tt("Training failed. Details are kept in the backend log and run folder.", self.lang)
        if "tif_backend_prepare_dataset_failed" in lower:
            return tt("Dataset preparation failed. Details are kept in the backend log and run folder.", self.lang)
        if "tif_backend_predict_failed" in lower:
            return tt("Prediction failed. Details are kept in the backend log and run folder.", self.lang)
        return tt("Run failed: {0}", self.lang).format(action_text)

    def _backend_failure_dialog_text(self, summary, detail):
        lines = [str(summary or tt("Run failed.", self.lang))]
        run_dir = str(self._tif_backend_run_dir or "").strip()
        result_json = str(self._tif_backend_result_json or "").strip()
        if run_dir:
            lines.append(f"{tt('Run folder', self.lang)}: {run_dir}")
        if result_json:
            lines.append(f"{tt('Result JSON', self.lang)}: {result_json}")
        detail = str(detail or "").strip()
        if detail and len(detail) < 320:
            lines.append(detail)
        return "\n".join(lines)

    def _on_tif_backend_finished(self, result):
        result = result if isinstance(result, dict) else {}
        task_id = self._tif_backend_task_id
        task_current = self._task_context_matches_current(task_id, fields=("specimen_id", "volume_scope", "part_id", "reslice_id"))
        self._tif_backend_last_result = result
        self._tif_backend_run_dir = str(result.get("run_dir") or "")
        backend_result = result.get("result") if isinstance(result.get("result"), dict) else {}
        self._tif_backend_result_json = str(((result.get("contract") or {}).get("result_json")) or backend_result.get("_result_json") or "")
        self._tif_backend_progress_value = 100
        self.backend_progress_bar.setRange(0, 100)
        self.backend_progress_bar.setValue(100)
        self.backend_progress_bar.setFormat("%p%")
        action = str(result.get("contract", {}).get("action") or self._tif_backend_action or "")
        message = tt("Run finished: {0}\nRun: {1}", self.lang).format(action, self._tif_backend_run_dir)
        self.backend_run_status_label.setText(message)
        self.training_status_label.setText(message)
        self.log(message)
        pending = dict(self._tif_backend_pending_selection or {})
        self._finish_tif_task(task_id, payload=result, message="backend_action_finished")
        self._cleanup_tif_backend_thread()
        self.refresh_project()
        if action == "train":
            backend_result = result.get("result") if isinstance(result.get("result"), dict) else result
            result_json = str((backend_result or {}).get("_result_json") or self._tif_backend_result_json or "")
            summary = summarize_tif_training_result(backend_result, result_json=result_json, run_dir=self._tif_backend_run_dir)
            model_record = self._register_training_summary_model(summary, backend_result, result.get("contract", {}))
            self._set_training_result_summary(summary)
            self._populate_tif_model_library_combo(self._tif_model_record_id(model_record) if model_record else None)
            self.show_latest_training_result_summary(show_message=False)
        if action == "predict" and task_current and pending.get("specimen_id") and pending.get("input_scope") == "top_level_volume":
            self._select_volume_tree_item(pending.get("specimen_id", ""), "full")
            index = self.label_role_combo.findData("working_edit")
            if index >= 0:
                self.label_role_combo.setCurrentIndex(index)
            if hasattr(self, "task_tabs") and hasattr(self, "training_mode_tabs"):
                self.task_tabs.setCurrentWidget(self.training_mode_tabs)
                self.training_mode_tabs.setCurrentWidget(self.annotation_task_page)
        elif action == "predict" and task_current and pending.get("specimen_id") and pending.get("part_id"):
            self._select_volume_tree_item(
                pending.get("specimen_id", ""),
                "part_reslice" if pending.get("reslice_id") else "part",
                pending.get("part_id", ""),
                pending.get("reslice_id", ""),
            )
            index = self.label_role_combo.findData("editable_ai_result")
            if index >= 0:
                self.label_role_combo.setCurrentIndex(index)
            if hasattr(self, "task_tabs") and hasattr(self, "training_mode_tabs"):
                self.task_tabs.setCurrentWidget(self.training_mode_tabs)
                self.training_mode_tabs.setCurrentWidget(self.annotation_task_page)
        if action == "predict":
            self.refresh_predict_targets()
        self._tif_backend_pending_selection = {}
        self._tif_backend_task_id = ""

    def _on_tif_backend_failed(self, message, context=None):
        text = str(message or "")
        context = context if isinstance(context, dict) else {}
        self._tif_backend_run_dir = str(context.get("run_dir") or self._tif_backend_run_dir or "")
        self._tif_backend_result_json = str(context.get("result_json") or self._tif_backend_result_json or "")
        action = self._tif_backend_action
        status = self._backend_failure_summary(text, action=action)
        self._tif_backend_progress_value = 0
        self.backend_progress_bar.setRange(0, 100)
        self.backend_progress_bar.setValue(0)
        self.backend_progress_bar.setFormat("%p%")
        self.backend_run_status_label.setText(status)
        self.training_status_label.setText(status)
        detail_lines = text.splitlines()
        detail_tail = "\n".join(detail_lines[-12:]) if detail_lines else text
        self.backend_log_tail.setPlainText(detail_tail)
        self.backend_log_tail.setToolTip(text)
        self.log(status)
        self._tif_backend_pending_selection = {}
        task = self.task_manager.task(self._tif_backend_task_id)
        if task is not None and task.status == "cancelled":
            self._cancel_tif_task(self._tif_backend_task_id, task.error or status)
        else:
            self._fail_tif_task(self._tif_backend_task_id, text, payload=context, message=status)
        self._cleanup_tif_backend_thread()
        self._tif_backend_task_id = ""
        if "_cancelled" not in text:
            QMessageBox.warning(self, tt("TIF backend", self.lang), self._backend_failure_dialog_text(status, text))

    def cancel_backend_action(self):
        if not self._backend_action_running() or self._tif_backend_worker is None:
            return
        action = self._tif_backend_action
        self._tif_backend_worker.cancel()
        message = tt("Cancelling {0}...", self.lang).format(action)
        self.backend_run_status_label.setText(message)
        self.training_status_label.setText(message)
        self.log(message)
        self._cancel_tif_task(self._tif_backend_task_id, message)

    def open_latest_backend_run_folder(self):
        path = str(self._tif_backend_run_dir or "")
        if not path or not os.path.isdir(path):
            QMessageBox.information(self, tt("TIF backend", self.lang), tt("No backend run folder is available yet.", self.lang))
            return False
        return QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def open_latest_backend_result_json(self):
        path = str(self._tif_backend_result_json or "")
        if not path or not os.path.exists(path):
            QMessageBox.information(self, tt("TIF backend", self.lang), tt("No backend result JSON is available yet.", self.lang))
            return False
        return QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _queue_backend_action_after_save(self, action, selection):
        self._pending_backend_action_after_save = {
            "action": str(action or ""),
            "selection": {
                "part_refs": [dict(ref or {}) for ref in (selection or {}).get("part_refs", [])],
                "specimen_ids": [str(item) for item in (selection or {}).get("specimen_ids", [])],
                "input_scope": str((selection or {}).get("input_scope") or "part_reslice"),
            },
        }

    def _resume_pending_backend_action_after_save(self):
        pending = self._pending_backend_action_after_save
        if not pending:
            return False
        if self.working_edit_dirty:
            self._set_operation_feedback(tt("Save finished with remaining unsaved labels. Backend run was not started.", self.lang))
            self._pending_backend_action_after_save = None
            return False
        self._pending_backend_action_after_save = None
        self._start_backend_action_with_selection(pending.get("action", ""), pending.get("selection") or {})
        return True

    def _confirm_or_queue_save_before_backend_action(self, action, selection):
        if not self.working_edit_dirty and not self._label_auto_save_running() and not self._label_manual_save_running():
            return True
        if self._label_manual_save_running():
            self._queue_backend_action_after_save(action, selection)
            self._set_operation_feedback(tt("Label save is running. Backend run will start after saving finishes.", self.lang))
            return False
        if not self.working_edit_dirty and self._label_auto_save_running():
            self._queue_backend_action_after_save(action, selection)
            self._set_operation_feedback(tt("Finishing auto-save before backend run...", self.lang))
            return False

        title = tt("Unsaved editable AI result", self.lang) if self.current_volume_scope == "part" else tt("Unsaved current labels", self.lang)
        prompt = (
            tt("Save changes to the current editable AI result before continuing?", self.lang)
            if self.current_volume_scope == "part"
            else tt("Save changes to the current labels before continuing?", self.lang)
        )
        reply = QMessageBox.question(
            self,
            title,
            prompt,
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )
        if reply == QMessageBox.Cancel:
            return False
        if reply == QMessageBox.Discard:
            self.working_edit_dirty = False
            self._reset_edit_dirty_tracking()
            self._update_save_status()
            if self.current_specimen_id:
                self._load_edit_volume()
            return True

        self._queue_backend_action_after_save(action, selection)
        if not self.save_working_edit_async(show_message=True):
            self._pending_backend_action_after_save = None
        return False

    def _start_backend_action_with_selection(self, action, selection):
        part_refs = selection.get("part_refs") or []
        specimen_ids = selection.get("specimen_ids") or []
        input_scope = selection.get("input_scope") or "part_reslice"
        if self._backend_action_running():
            QMessageBox.information(self, tt("TIF backend", self.lang), tt("Backend task is already running.", self.lang))
            return
        self._tif_backend_pending_selection = {
            "specimen_id": self.current_specimen_id,
            "part_id": self.current_part_id,
            "reslice_id": self.current_reslice_id,
            "input_scope": input_scope,
        }
        self._start_backend_status(action, part_refs=part_refs, specimen_ids=specimen_ids, input_scope=input_scope)
        task = self._start_tif_task(
            "backend_action",
            action=action,
            payload={
                "input_scope": input_scope,
                "part_ref_count": len(part_refs or []),
                "specimen_count": len(specimen_ids or []),
                "pending_selection": dict(self._tif_backend_pending_selection or {}),
            },
            request_key=self._task_request_key((action, input_scope, part_refs or specimen_ids)),
            message=tt("Backend run is active. Stop it or wait until it finishes before editing project data.", self.lang),
        )
        self._tif_backend_task_id = task.task_id
        self._tif_backend_thread = QThread(self)
        self._tif_backend_worker = TifBackendActionWorker(
            self.project,
            self.backend_config,
            action,
            part_refs=part_refs,
            specimen_ids=specimen_ids,
            input_scope=input_scope,
            model_manifest=self.backend_config.get("model_manifest", ""),
        )
        self._tif_backend_worker.moveToThread(self._tif_backend_thread)
        self._tif_backend_thread.started.connect(self._tif_backend_worker.run)
        self._tif_backend_worker.progress.connect(self._on_tif_backend_progress)
        self._tif_backend_worker.finished.connect(self._on_tif_backend_finished)
        self._tif_backend_worker.failed.connect(self._on_tif_backend_failed)
        self._tif_backend_worker.finished.connect(self._tif_backend_thread.quit)
        self._tif_backend_worker.failed.connect(self._tif_backend_thread.quit)
        self._tif_backend_thread.finished.connect(self._tif_backend_worker.deleteLater)
        self._tif_backend_thread.finished.connect(self._on_tif_backend_thread_finished)
        self._tif_backend_thread.finished.connect(self._tif_backend_thread.deleteLater)
        self._tif_backend_thread.start()

    def run_backend_action(self, action):
        if not self._ensure_tif_project_open():
            return
        if self._backend_action_running():
            QMessageBox.information(self, tt("TIF backend", self.lang), tt("Backend task is already running.", self.lang))
            return
        self.backend_config = self._backend_config_from_ui()
        if self.config_manager is not None:
            self.config_manager.set("tif_backend", dict(self.backend_config))
            self.config_manager.save()
        command_key = {
            "prepare_dataset": "prepare_dataset_command",
            "train": "train_command",
            "predict": "predict_command",
        }.get(action, "")
        if command_key and not self.backend_config.get(command_key, "").strip():
            QMessageBox.warning(self, tt("TIF backend", self.lang), tt("No command configured for this backend action.", self.lang))
            return
        if action == "predict":
            try:
                self._validated_predict_model_manifest()
            except Exception as exc:
                message = tt("Action failed: {0}", self.lang).format(str(exc))
                self.training_status_label.setText(message)
                self.log(message)
                QMessageBox.warning(self, tt("TIF backend", self.lang), str(exc))
                return
        try:
            selection = self._selected_backend_samples_for_action(action)
        except Exception as exc:
            message = tt("Action failed: {0}", self.lang).format(str(exc))
            self.training_status_label.setText(message)
            self.log(message)
            QMessageBox.warning(self, tt("TIF backend", self.lang), str(exc))
            return
        part_refs = selection.get("part_refs") or []
        specimen_ids = selection.get("specimen_ids") or []
        input_scope = selection.get("input_scope") or "part_reslice"
        if action == "predict" and not self._confirm_predict_overwrite_if_needed(part_refs=part_refs, specimen_ids=specimen_ids, input_scope=input_scope):
            return
        if not self._confirm_or_queue_save_before_backend_action(action, selection):
            return
        self._start_backend_action_with_selection(action, selection)

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

    def _make_task_page(self, object_name):
        return make_task_page(object_name)

    def _build_layout(self):
        self._field_labels = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        top_bar = QFrame()
        top_bar.setObjectName("tifWorkbenchTopBar")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(12, 8, 12, 8)
        top_layout.setSpacing(8)
        self.tif_top_context_label = QLabel("TIF Volume Workbench")
        self.tif_top_context_label.setObjectName("tifTopContextLabel")
        top_layout.addWidget(self.tif_top_context_label, 1)
        top_layout.addWidget(self.btn_start_center)
        top_layout.addWidget(self.btn_ask_agent)
        root.addWidget(top_bar)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setObjectName("tifWorkbenchSplitter")
        root.addWidget(splitter, 1)

        left, left_layout = self._make_panel("Specimens", "tifSpecimenPanel")
        left_layout.addWidget(self.specimen_list, 1)
        splitter.addWidget(left)

        center, center_layout = self._make_panel("Volume slices", "tifVolumePanel")
        canvas_shell = QFrame()
        canvas_shell.setObjectName("tifCanvasShell")
        canvas_layout = QVBoxLayout(canvas_shell)
        canvas_layout.setContentsMargins(6, 6, 6, 6)
        self.view_stack = QStackedWidget()
        self.view_stack.setObjectName("tifViewStack")
        self.view_stack.addWidget(self.canvas)
        self.view_stack.addWidget(self.volume_canvas)
        canvas_layout.addWidget(self.view_stack, 1)
        canvas_layout.addWidget(self.volume_render_status_label)
        center_layout.addWidget(canvas_shell, 1)
        slice_bar = QFrame()
        slice_bar.setObjectName("tifSliceBar")
        slice_row = QHBoxLayout()
        slice_row.setContentsMargins(10, 6, 10, 6)
        self.display_mode_label = QLabel("Display mode")
        slice_row.addWidget(self.display_mode_combo)
        slice_row.addWidget(self.display_mode_label)
        self.slice_axis_label = QLabel("View plane")
        slice_row.addWidget(self.slice_axis_label)
        slice_row.addWidget(self.slice_axis_combo)
        slice_row.addWidget(self.slice_prefix_label)
        slice_row.addWidget(self.slice_slider, 1)
        slice_row.addWidget(self.slice_label)
        slice_bar.setLayout(slice_row)
        center_layout.addWidget(slice_bar)
        splitter.addWidget(center)

        if not hasattr(self, "_panel_title_labels"):
            self._panel_title_labels = {}
        if not hasattr(self, "_section_title_labels"):
            self._section_title_labels = {}
        right_panel_parts = build_right_control_panel(self._panel_title_labels, self._section_title_labels)
        right = right_panel_parts["panel"]
        right_layout = right_panel_parts["layout"]
        self.operation_status_section = right_panel_parts["operation_status_section"]
        operation_status_layout = right_panel_parts["operation_status_layout"]
        operation_status_layout.addWidget(self.operation_status_label)
        operation_status_layout.addWidget(self.btn_show_workbench_log)
        right_layout.addWidget(self.operation_status_section)

        task_page_parts = build_task_pages(self.lang, tt)
        self.task_tabs = task_page_parts["task_tabs"]
        self.training_mode_tabs = task_page_parts["training_mode_tabs"]
        self.part_task_page = task_page_parts["part_task_page"]
        self.part_task_layout = task_page_parts["part_task_layout"]
        self.display_task_page = task_page_parts["display_task_page"]
        self.display_task_layout = task_page_parts["display_task_layout"]
        self.annotation_task_page = task_page_parts["annotation_task_page"]
        self.annotation_task_layout = task_page_parts["annotation_task_layout"]
        self.training_task_page = task_page_parts["training_task_page"]
        self.training_task_layout = task_page_parts["training_task_layout"]
        self.result_compare_page = task_page_parts["result_compare_page"]
        self.result_compare_layout = task_page_parts["result_compare_layout"]
        right_layout.addWidget(self.task_tabs, 1)
        self.task_tabs.currentChanged.connect(self._on_task_tab_changed)
        self.training_mode_tabs.currentChanged.connect(self._on_training_mode_tab_changed)

        import_section, import_layout = self._make_section("Data import", "tifImportSection")
        import_button_row = QHBoxLayout()
        import_button_row.addWidget(self.btn_import_tif)
        import_button_row.addWidget(self.btn_import_amira)
        import_layout.addLayout(import_button_row)
        self.part_task_layout.addWidget(import_section)

        status_section, status_layout = self._make_section("Current object", "tifStatusSection")
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.show_debug_paths_check)
        status_layout.addWidget(self.metadata_label)
        self.part_task_layout.addWidget(status_section)

        self.part_locate_section, part_locate_layout = self._make_section("1. Locate part", "tifPartLocateSection")
        part_locate_layout.addWidget(self.part_bbox_edit)
        part_bbox_row = QHBoxLayout()
        part_bbox_row.addWidget(self.btn_part_draw_roi)
        part_locate_layout.addLayout(part_bbox_row)
        part_draft_row = QHBoxLayout()
        part_draft_row.addWidget(self.btn_save_part_roi)
        part_draft_row.addWidget(self.btn_confirm_part_roi)
        part_locate_layout.addLayout(part_draft_row)
        part_action_row = QHBoxLayout()
        part_action_row.addWidget(self.btn_cancel_part_roi)
        part_locate_layout.addLayout(part_action_row)
        self.part_task_layout.addWidget(self.part_locate_section)

        self.part_mask_section, part_mask_layout = self._make_section("2. Build part mask", "tifPartMaskSection")
        part_key_row = QHBoxLayout()
        part_key_row.addWidget(self.btn_draw_part_contour)
        part_mask_layout.addLayout(part_key_row)
        part_key_nav_row = QHBoxLayout()
        part_key_nav_row.addWidget(self.btn_prev_key_slice)
        part_key_nav_row.addWidget(self.btn_next_key_slice)
        part_mask_layout.addLayout(part_key_nav_row)
        part_key_action_row = QHBoxLayout()
        part_key_action_row.addWidget(self.btn_delete_part_contour)
        part_key_action_row.addWidget(self.btn_clear_part_keyframes)
        part_key_action_row.addWidget(self.btn_preview_part_mask)
        part_mask_layout.addLayout(part_key_action_row)
        part_mask_row = QHBoxLayout()
        part_mask_row.addWidget(self.btn_accept_part_mask)
        part_mask_row.addWidget(self.btn_clear_part_preview)
        part_mask_layout.addLayout(part_mask_row)
        self.part_task_layout.addWidget(self.part_mask_section)

        self.local_axis_volume_section, local_axis_volume_layout = self._make_section(
            "Local Axis Reslice / part volume",
            "tifLocalAxisVolumeSection",
        )
        self.local_axis_volume_help_label = QLabel(
            tt(
                "Roll A/B/C picking works on the observation-side clip plane only. Turn on Clip plane in the 3D preview, move it to the target cross-section, then click A, B, and C on that plane.",
                self.lang,
            )
        )
        self.local_axis_volume_help_label.setObjectName("tifLayerHelpText")
        self.local_axis_volume_help_label.setWordWrap(True)
        local_axis_volume_layout.addWidget(self.local_axis_volume_help_label)
        local_axis_display_row = QHBoxLayout()
        local_axis_display_row.addWidget(self.volume_local_axes_check)
        local_axis_display_row.addStretch(1)
        local_axis_volume_layout.addLayout(local_axis_display_row)
        local_axis_volume_layout.addWidget(self.local_axis_status_label)
        local_axis_volume_layout.addWidget(self.local_axis_summary_label)
        local_axis_volume_layout.addWidget(self.local_axis_details_check)
        local_axis_volume_layout.addWidget(self.local_axis_details_label)
        local_axis_volume_row = QHBoxLayout()
        local_axis_volume_row.addWidget(self.btn_copy_source_z_axis)
        local_axis_volume_row.addWidget(self.btn_local_axis_reslice)
        local_axis_volume_layout.addLayout(local_axis_volume_row)
        local_axis_roll_grid = QGridLayout()
        local_axis_roll_grid.setHorizontalSpacing(8)
        local_axis_roll_grid.setVerticalSpacing(8)
        local_axis_roll_grid.addWidget(self.btn_pick_roll_ref_a, 0, 0)
        local_axis_roll_grid.addWidget(self.btn_pick_roll_ref_b, 0, 1)
        local_axis_roll_grid.addWidget(self.btn_pick_roll_ref_c, 1, 0)
        local_axis_roll_grid.addWidget(self.btn_clear_roll_refs, 1, 1)
        local_axis_roll_grid.setColumnStretch(0, 1)
        local_axis_roll_grid.setColumnStretch(1, 1)
        local_axis_volume_layout.addLayout(local_axis_roll_grid)
        local_axis_plane_row = QHBoxLayout()
        local_axis_plane_row.addWidget(self.btn_align_axis_to_reference_plane)
        local_axis_volume_layout.addLayout(local_axis_plane_row)
        local_axis_center_row = QHBoxLayout()
        local_axis_center_row.addWidget(self.btn_clear_local_axis_draft)
        local_axis_volume_layout.addLayout(local_axis_center_row)
        local_axis_volume_layout.addWidget(self.local_axis_trainable_check)
        local_axis_volume_layout.addWidget(self.btn_export_local_axis_training_manifest)
        self.part_task_layout.addWidget(self.local_axis_volume_section)

        self.part_output_section, part_output_layout = self._make_section("3. Output and manage", "tifPartOutputSection")
        part_output_layout.addWidget(self.btn_export_part_package)
        part_output_layout.addWidget(self.btn_delete_part_volume)
        self.part_task_layout.addWidget(self.part_output_section)

        self.slice_display_section, slice_display_layout = self._make_section("Slice display", "tifSliceDisplaySection")
        slice_controls = QGridLayout()
        slice_controls.setHorizontalSpacing(10)
        slice_controls.setVerticalSpacing(8)
        self.label_layer_label = QLabel("Label layer")
        self.overlay_label = QLabel("Overlay")
        self.brightness_label = QLabel("Brightness")
        self.contrast_label = QLabel("Contrast")
        slice_controls.addWidget(self.overlay_label, 0, 0)
        slice_controls.addWidget(self.opacity_slider, 0, 1)
        slice_controls.addWidget(self.brightness_label, 1, 0)
        slice_controls.addWidget(self.brightness_slider, 1, 1)
        slice_controls.addWidget(self.contrast_label, 2, 0)
        slice_controls.addWidget(self.contrast_slider, 2, 1)
        slice_display_layout.addLayout(slice_controls)
        self.display_task_layout.addWidget(self.slice_display_section)

        self.volume_render_section, volume_render_layout = self._make_section("3D rendering", "tifVolumeRenderSection")
        volume_controls = QGridLayout()
        volume_controls.setHorizontalSpacing(10)
        volume_controls.setVerticalSpacing(8)
        self.volume_projection_label = QLabel("Render mode")
        self.volume_tint_label = QLabel("Transfer function")
        self.volume_enhancement_label = QLabel("Detail enhancement")
        self.volume_tone_label = QLabel("Tone curve")
        self.volume_mask_label = QLabel("Mask display")
        self.volume_mask_opacity_label = QLabel("Mask opacity")
        self.volume_cutoff_label = QLabel("Density cutoff")
        self.volume_quality_label = QLabel("Render quality")
        self.volume_sample_label = QLabel("Ray samples")
        self.volume_roi_scale_label = QLabel("ROI scale")
        self.volume_roi_budget_label = QLabel("ROI budget")
        self.volume_inside_label = QLabel("Inside depth")
        self.volume_clip_label = QLabel("Front cut")
        volume_controls.addWidget(self.volume_projection_label, 0, 0)
        volume_controls.addWidget(self.volume_projection_combo, 0, 1)
        volume_controls.addWidget(self.volume_tint_label, 1, 0)
        color_row = QHBoxLayout()
        color_row.addWidget(self.volume_tint_combo, 1)
        color_row.addWidget(self.btn_volume_custom_color)
        color_row.addWidget(self.btn_volume_morphology_preset)
        volume_controls.addLayout(color_row, 1, 1)
        self.volume_transfer_opacity_label = QLabel("Density opacity")
        volume_controls.addWidget(self.volume_transfer_opacity_label, 2, 0)
        volume_controls.addWidget(self.volume_transfer_opacity_slider, 2, 1)
        volume_controls.addWidget(self.volume_enhancement_label, 3, 0)
        volume_controls.addWidget(self.volume_enhancement_slider, 3, 1)
        volume_controls.addWidget(self.volume_tone_label, 4, 0)
        volume_controls.addWidget(self.volume_tone_slider, 4, 1)
        self.volume_shader_quality_label = QLabel("Shader quality")
        volume_controls.addWidget(self.volume_shader_quality_label, 5, 0)
        volume_controls.addWidget(self.volume_shader_quality_combo, 5, 1)
        volume_controls.addWidget(self.volume_mask_label, 6, 0)
        volume_controls.addWidget(self.volume_mask_combo, 6, 1)
        volume_controls.addWidget(self.volume_mask_opacity_label, 7, 0)
        volume_controls.addWidget(self.volume_mask_opacity_slider, 7, 1)
        volume_controls.addWidget(self.volume_cutoff_label, 8, 0)
        volume_controls.addWidget(self.volume_cutoff_slider, 8, 1)
        volume_controls.addWidget(self.volume_quality_label, 9, 0)
        volume_controls.addWidget(self.volume_quality_slider, 9, 1)
        volume_controls.addWidget(self.volume_sample_label, 10, 0)
        volume_controls.addWidget(self.volume_sample_slider, 10, 1)
        volume_controls.addWidget(self.volume_clarity_check, 11, 0, 1, 2)
        volume_controls.addWidget(self.volume_surface_refine_check, 12, 0, 1, 2)
        volume_controls.addWidget(self.volume_roi_detail_check, 13, 0, 1, 2)
        volume_controls.addWidget(self.volume_roi_source_combo, 14, 0, 1, 2)
        volume_controls.addWidget(self.volume_roi_inspect_check, 15, 0, 1, 2)
        volume_controls.addWidget(self.volume_roi_scale_label, 16, 0)
        volume_controls.addWidget(self.volume_roi_scale_slider, 16, 1)
        volume_controls.addWidget(self.volume_roi_budget_label, 17, 0)
        volume_controls.addWidget(self.volume_roi_budget_combo, 17, 1)
        volume_controls.addWidget(self.volume_clip_plane_check, 18, 0, 1, 2)
        volume_controls.addWidget(self.volume_clip_plane_depth_label, 19, 0)
        volume_controls.addWidget(self.volume_clip_plane_depth_slider, 19, 1)
        volume_controls.addWidget(self.volume_inside_label, 20, 0)
        volume_controls.addWidget(self.volume_inside_slider, 20, 1)
        volume_controls.addWidget(self.volume_clip_label, 21, 0)
        volume_controls.addWidget(self.volume_clip_slider, 21, 1)
        volume_render_layout.addLayout(volume_controls)
        volume_render_layout.addWidget(self.btn_reset_volume_view)
        self.display_task_layout.addWidget(self.volume_render_section)

        self.material_section, material_layout = self._make_section("Current labels", "tifMaterialSection")
        self.material_help_label = QLabel(tt("After binding a label schema, select one current label here before using the brush or fill tools.", self.lang))
        self.material_help_label.setObjectName("tifLayerHelpText")
        self.material_help_label.setWordWrap(True)
        material_layout.addWidget(self.material_help_label)
        current_material_row = QHBoxLayout()
        current_material_row.setSpacing(10)
        current_material_row.addWidget(self.current_material_swatch)
        current_material_text = QVBoxLayout()
        current_material_text.setSpacing(2)
        current_material_text.addWidget(self.current_material_title_label)
        current_material_text.addWidget(self.current_material_label)
        current_material_row.addLayout(current_material_text, 1)
        material_layout.addLayout(current_material_row)
        self.material_scope_help_label = QLabel(tt("Material IDs are the numeric labels stored in the current volume. For part volumes, this list follows the bound region label schema; for full volumes, it is the specimen material map.", self.lang))
        self.material_scope_help_label.setObjectName("tifLayerHelpText")
        self.material_scope_help_label.setWordWrap(True)
        material_layout.addWidget(self.material_scope_help_label)
        material_button_row = QHBoxLayout(self.material_editor_buttons)
        material_button_row.setContentsMargins(0, 0, 0, 0)
        material_button_row.setSpacing(6)
        material_button_row.addWidget(self.btn_add_material)
        material_button_row.addWidget(self.btn_edit_material)
        material_button_row.addWidget(self.btn_delete_material)
        material_layout.addWidget(self.material_editor_buttons)
        material_layout.addWidget(self.material_table)

        self.annotation_section, annotation_layout = self._make_section("Annotation tools", "tifAnnotationSection")
        controls = QGridLayout()
        controls.setHorizontalSpacing(10)
        controls.setVerticalSpacing(8)
        self.brush_size_label = QLabel("Brush size")
        tool_grid = QGridLayout()
        tool_grid.setHorizontalSpacing(6)
        tool_grid.setVerticalSpacing(6)
        tool_grid.addWidget(self.btn_tool_brush, 0, 0)
        tool_grid.addWidget(self.btn_tool_eraser, 0, 1)
        tool_grid.addWidget(self.btn_tool_lasso, 1, 0)
        tool_grid.addWidget(self.btn_tool_rectangle, 1, 1)
        tool_grid.addWidget(self.btn_tool_ellipse, 2, 0)
        tool_grid.addWidget(self.btn_tool_picker, 2, 1)
        tool_grid.addWidget(self.btn_interpolate_current_label, 3, 0, 1, 2)
        tool_grid.addWidget(self.btn_tool_pan, 4, 0, 1, 2)
        controls.addWidget(self.annotation_tool_label, 0, 0)
        controls.addLayout(tool_grid, 0, 1)
        controls.addWidget(self.label_layer_label, 1, 0)
        controls.addWidget(self.label_role_combo, 1, 1)
        controls.addWidget(self.brush_size_label, 2, 0)
        controls.addWidget(self.brush_size_slider, 2, 1)
        annotation_layout.addLayout(controls)
        annotation_layout.addWidget(self.label_role_help_label)
        annotation_layout.addWidget(self.ai_review_check_title_label)
        annotation_layout.addWidget(self.ai_review_check_label)
        button_row = QHBoxLayout()
        button_row.addWidget(self.btn_undo)
        button_row.addWidget(self.btn_redo)
        annotation_layout.addLayout(button_row)
        save_status_row = QHBoxLayout()
        save_status_row.setSpacing(8)
        save_status_row.addWidget(self.save_status_title_label)
        save_status_row.addWidget(self.save_status_label, 1)
        annotation_layout.addLayout(save_status_row)
        auto_save_row = QHBoxLayout()
        auto_save_row.setSpacing(8)
        auto_save_row.addWidget(self.auto_save_check)
        auto_save_row.addWidget(self.auto_save_hint_label, 1)
        annotation_layout.addLayout(auto_save_row)
        annotation_layout.addWidget(self.btn_save_edit)
        slice_helper_row = QHBoxLayout()
        slice_helper_row.setSpacing(6)
        slice_helper_row.addWidget(self.btn_copy_material_prev)
        slice_helper_row.addWidget(self.btn_copy_material_next)
        annotation_layout.addLayout(slice_helper_row)
        annotation_layout.addWidget(self.btn_clear_current_material)
        annotation_layout.addWidget(self.btn_promote)
        annotation_layout.addWidget(self.btn_copy_draft)

        self.label_schema_section, label_schema_layout = self._make_section("Region label schema", "tifLabelSchemaSection")
        self.label_schema_help_label = QLabel(tt("Bind a label schema first so every specimen uses the same numeric labels for annotation, training, prediction import, and result comparison. Import files should be TaxaMask label schema JSON exported from this panel.", self.lang))
        self.label_schema_help_label.setObjectName("tifLayerHelpText")
        self.label_schema_help_label.setWordWrap(True)
        label_schema_layout.addWidget(self.label_schema_help_label)
        label_schema_select_row = QHBoxLayout()
        label_schema_select_row.setSpacing(6)
        label_schema_select_row.addWidget(self.label_schema_combo, 1)
        label_schema_select_row.addWidget(self.btn_new_label_schema)
        label_schema_layout.addLayout(label_schema_select_row)
        label_schema_form = QFormLayout()
        label_schema_form.setHorizontalSpacing(8)
        label_schema_form.setVerticalSpacing(6)
        self.label_schema_id_label = QLabel("Schema ID")
        self.label_schema_part_name_label = QLabel("User-defined part name")
        label_schema_form.addRow(self.label_schema_id_label, self.label_schema_id_edit)
        label_schema_form.addRow(self.label_schema_part_name_label, self.label_schema_part_name_edit)
        label_schema_layout.addLayout(label_schema_form)
        label_schema_row_buttons = QHBoxLayout()
        label_schema_row_buttons.setSpacing(6)
        label_schema_row_buttons.addWidget(self.btn_add_label_schema_row)
        label_schema_row_buttons.addWidget(self.btn_remove_label_schema_row)
        label_schema_layout.addLayout(label_schema_row_buttons)
        label_schema_layout.addWidget(self.label_schema_table)
        label_schema_save_buttons = QGridLayout()
        label_schema_save_buttons.setHorizontalSpacing(6)
        label_schema_save_buttons.setVerticalSpacing(6)
        label_schema_save_buttons.addWidget(self.btn_save_label_schema, 0, 0)
        label_schema_save_buttons.addWidget(self.btn_bind_label_schema_to_part, 0, 1)
        label_schema_save_buttons.addWidget(self.btn_import_label_schema, 1, 0)
        label_schema_save_buttons.addWidget(self.btn_export_label_schema, 1, 1)
        label_schema_save_buttons.setColumnStretch(0, 1)
        label_schema_save_buttons.setColumnStretch(1, 1)
        label_schema_layout.addLayout(label_schema_save_buttons)
        self.annotation_task_layout.addWidget(self.label_schema_section)
        self.annotation_task_layout.addWidget(self.material_section)
        self.annotation_task_layout.addWidget(self.annotation_section)

        training_section, training_layout = self._make_section("Model training", "tifTrainingSection")
        training_layout.addWidget(self.btn_export_training)
        backend_button_row = QHBoxLayout()
        backend_button_row.addWidget(self.btn_prepare_dataset)
        backend_button_row.addWidget(self.btn_train_backend)
        training_layout.addLayout(backend_button_row)
        training_layout.addWidget(self.backend_run_title_label)
        training_layout.addWidget(self.backend_run_status_label)
        training_layout.addWidget(self.backend_elapsed_label)
        training_layout.addWidget(self.backend_progress_bar)
        backend_run_button_row = QHBoxLayout()
        backend_run_button_row.setSpacing(6)
        backend_run_button_row.addWidget(self.btn_stop_backend)
        backend_run_button_row.addWidget(self.btn_open_backend_run)
        backend_run_button_row.addWidget(self.btn_open_backend_result)
        training_layout.addLayout(backend_run_button_row)
        training_layout.addWidget(self.backend_log_tail)
        part_user_tags_section, part_user_tags_layout = self._make_section("Part group tags", "tifPartUserTagsSection")
        self.part_user_tag_help_label = QLabel(tt("Group tags only organize part volumes for prediction rounds or review batches. They are not annotation classes, label schemas, or training labels.", self.lang))
        self.part_user_tag_help_label.setObjectName("tifLayerHelpText")
        self.part_user_tag_help_label.setWordWrap(True)
        part_user_tags_layout.addWidget(self.part_user_tag_help_label)
        part_tag_form = QFormLayout()
        part_tag_form.setHorizontalSpacing(8)
        part_tag_form.setVerticalSpacing(6)
        self.part_user_tag_id_label = QLabel("Group tag ID")
        self.part_user_tag_label_label = QLabel("Group tag label")
        self.part_user_tag_color_label = QLabel("Color")
        part_tag_form.addRow(self.part_user_tag_id_label, self.part_user_tag_id_edit)
        part_tag_form.addRow(self.part_user_tag_label_label, self.part_user_tag_label_edit)
        part_tag_color_row = QHBoxLayout()
        part_tag_color_row.addWidget(self.part_user_tag_color_swatch)
        part_tag_color_row.addWidget(self.btn_choose_part_user_tag_color, 1)
        part_tag_color_row.addWidget(self.part_user_tag_color_edit)
        part_tag_form.addRow(self.part_user_tag_color_label, part_tag_color_row)
        part_user_tags_layout.addLayout(part_tag_form)
        part_tag_edit_buttons = QGridLayout()
        part_tag_edit_buttons.setHorizontalSpacing(6)
        part_tag_edit_buttons.setVerticalSpacing(6)
        part_tag_edit_buttons.addWidget(self.btn_new_part_user_tag, 0, 0)
        part_tag_edit_buttons.addWidget(self.btn_save_part_user_tag, 0, 1)
        part_tag_edit_buttons.addWidget(self.btn_delete_part_user_tag, 1, 0)
        part_tag_edit_buttons.addWidget(self.btn_apply_part_user_tags, 1, 1)
        part_tag_edit_buttons.setColumnStretch(0, 1)
        part_tag_edit_buttons.setColumnStretch(1, 1)
        part_user_tags_layout.addLayout(part_tag_edit_buttons)
        part_tag_order_buttons = QHBoxLayout()
        part_tag_order_buttons.setSpacing(6)
        part_tag_order_buttons.addWidget(self.btn_move_part_user_tag_up)
        part_tag_order_buttons.addWidget(self.btn_move_part_user_tag_down)
        part_user_tags_layout.addLayout(part_tag_order_buttons)
        part_user_tags_layout.addWidget(self.part_user_tag_table)
        training_layout.addWidget(part_user_tags_section)
        model_library_section, model_library_layout = self._make_section("Trained models", "tifModelLibrarySection")
        self.model_library_label = QLabel("Trained model")
        model_library_layout.addWidget(self.model_library_label)
        model_library_layout.addWidget(self.model_library_combo)
        model_library_layout.addWidget(self.model_library_summary_label)
        self.model_library_notes_label = QLabel("Notes")
        model_library_layout.addWidget(self.model_library_notes_label)
        model_library_layout.addWidget(self.model_library_notes_edit)
        model_library_buttons = QGridLayout()
        model_library_buttons.setHorizontalSpacing(6)
        model_library_buttons.setVerticalSpacing(6)
        model_library_buttons.addWidget(self.btn_use_selected_tif_model, 0, 0)
        model_library_buttons.addWidget(self.btn_save_tif_model_notes, 0, 1)
        model_library_buttons.addWidget(self.btn_delete_tif_model_record, 1, 0, 1, 2)
        model_library_buttons.setColumnStretch(0, 1)
        model_library_buttons.setColumnStretch(1, 1)
        model_library_layout.addLayout(model_library_buttons)
        training_layout.addWidget(model_library_section)
        predict_section, predict_layout = self._make_section("Batch prediction targets", "tifPredictTargetsSection")
        manifest_row = QHBoxLayout()
        manifest_row.setSpacing(6)
        manifest_row.addWidget(self.backend_manifest_edit, 1)
        manifest_row.addWidget(self.btn_browse_model_manifest)
        self.predict_manifest_label = QLabel("Model manifest")
        predict_layout.addWidget(self.predict_manifest_label)
        predict_layout.addLayout(manifest_row)
        filter_row = QHBoxLayout()
        filter_row.setSpacing(6)
        self.predict_filter_label = QLabel("Predict group")
        filter_row.addWidget(self.predict_filter_label)
        filter_row.addWidget(self.predict_filter_combo, 1)
        filter_row.addWidget(self.btn_refresh_predict_targets)
        predict_layout.addLayout(filter_row)
        predict_layout.addWidget(self.predict_targets_table)
        predict_button_row = QHBoxLayout()
        predict_button_row.setSpacing(6)
        predict_button_row.addWidget(self.btn_select_current_predict_target)
        predict_button_row.addWidget(self.btn_select_ready_predict_targets)
        predict_button_row.addWidget(self.btn_clear_predict_targets)
        predict_layout.addLayout(predict_button_row)
        predict_layout.addWidget(self.predict_targets_summary_label)
        predict_layout.addWidget(self.btn_import_prediction)
        predict_layout.addWidget(self.btn_accept_selected_ai_results)
        training_layout.addWidget(predict_section)
        training_layout.addWidget(self.btn_import_external_prediction_tif)
        self.training_task_layout.addWidget(training_section)

        training_result_section, training_result_layout = self._make_section("Training result", "tifTrainingResultSection")
        training_result_layout.addWidget(self.training_result_summary_label)
        training_result_button_grid = QGridLayout()
        training_result_button_grid.setHorizontalSpacing(6)
        training_result_button_grid.setVerticalSpacing(6)
        training_result_button_grid.addWidget(self.btn_show_training_result_summary, 0, 0)
        training_result_button_grid.addWidget(self.btn_open_training_model_output, 0, 1)
        training_result_button_grid.addWidget(self.btn_open_training_model_manifest, 1, 0)
        training_result_button_grid.addWidget(self.btn_batch_predict_entry, 1, 1)
        training_result_button_grid.setColumnStretch(0, 1)
        training_result_button_grid.setColumnStretch(1, 1)
        training_result_layout.addLayout(training_result_button_grid)
        self.training_task_layout.addWidget(training_result_section)

        backend_section, backend_layout = self._make_section("Model configuration", "tifBackendSection")
        backend_form = QFormLayout()
        backend_form.setHorizontalSpacing(8)
        backend_form.setVerticalSpacing(6)
        self.backend_id_label = QLabel("Backend ID")
        self.backend_display_label = QLabel("Display name")
        self.backend_python_label = QLabel("Python")
        self.backend_formats_label = QLabel("Export formats")
        self.backend_prepare_label = QLabel("Prepare command")
        self.backend_train_label = QLabel("Train command")
        self.backend_predict_label = QLabel("Predict command")
        self.backend_manifest_label = QLabel("Model manifest")
        backend_form.addRow(self.backend_id_label, self.backend_id_edit)
        backend_form.addRow(self.backend_display_label, self.backend_display_edit)
        backend_form.addRow(self.backend_python_label, self.backend_python_edit)
        backend_form.addRow(self.backend_formats_label, self.backend_formats_edit)
        backend_form.addRow(self.backend_prepare_label, self.backend_prepare_edit)
        backend_form.addRow(self.backend_train_label, self.backend_train_edit)
        backend_form.addRow(self.backend_predict_label, self.backend_predict_edit)
        self.backend_manifest_label.setVisible(False)
        backend_layout.addLayout(backend_form)
        backend_button_row = QHBoxLayout()
        backend_button_row.setSpacing(6)
        backend_button_row.addWidget(self.btn_use_nnunet_backend_preset)
        backend_button_row.addWidget(self.btn_save_backend)
        backend_button_row.addStretch(1)
        backend_layout.addLayout(backend_button_row)
        self.training_task_layout.addWidget(backend_section)

        log_section, log_layout = self._make_section("Workbench log", "tifLogSection")
        log_layout.addWidget(self.log_console)
        self.training_task_layout.addWidget(log_section)

        result_section, result_layout = self._make_section("Result comparison", "tifResultComparisonSection")
        result_source_row = QHBoxLayout()
        self.result_source_label = QLabel("Review source")
        result_source_row.addWidget(self.result_source_label)
        result_source_row.addWidget(self.result_source_manual_radio)
        result_source_row.addWidget(self.result_source_editable_radio)
        result_source_row.addStretch(1)
        result_layout.addLayout(result_source_row)
        result_region_row = QHBoxLayout()
        self.result_region_label = QLabel("Region label")
        result_region_row.addWidget(self.result_region_label)
        result_region_row.addWidget(self.result_region_combo, 1)
        result_layout.addLayout(result_region_row)
        result_button_grid = QGridLayout()
        result_button_grid.setHorizontalSpacing(8)
        result_button_grid.setVerticalSpacing(8)
        result_button_grid.addWidget(self.btn_refresh_result_comparison, 0, 0)
        result_button_grid.addWidget(self.btn_open_result_comparison_target, 0, 1)
        result_button_grid.addWidget(self.btn_show_result_region_in_3d, 1, 0)
        result_button_grid.addWidget(self.btn_export_current_rendering, 1, 1)
        result_button_grid.setColumnStretch(0, 1)
        result_button_grid.setColumnStretch(1, 1)
        result_layout.addLayout(result_button_grid)
        result_layout.addWidget(self.result_compare_summary_label)
        result_layout.addWidget(self.result_compare_table)
        self.result_compare_layout.addWidget(result_section)
        self.part_task_layout.addStretch(1)
        self.display_task_layout.addStretch(1)
        self.annotation_task_layout.addStretch(1)
        self.training_task_layout.addStretch(1)
        self.result_compare_layout.addStretch(1)
        splitter.addWidget(right)

        self._make_right_sidebar_responsive(right)
        splitter.setSizes([230, 900, 420])

    def _apply_soft_style(self):
        t = _tif_workbench_theme(self.current_theme)
        stylesheet = """
            QWidget#tifWorkbenchRoot {
                background: {t['root']};
            }
            QFrame#tifSpecimenPanel,
            QFrame#tifVolumePanel,
            QFrame#tifControlPanel,
            QFrame#tifWorkbenchTopBar {
                background: {t['panel']};
                border: 1px solid {t['border']};
                border-radius: 12px;
            }
            QLabel#tifTopContextLabel {
                color: {t['text']};
                font-weight: 700;
                border: none;
            }
            QFrame#tifImportSection,
            QFrame#tifPartExtractionSection,
            QFrame#tifSliceDisplaySection,
            QFrame#tifVolumeRenderSection,
            QFrame#tifLocalAxisVolumeSection,
            QFrame#tifOperationStatusSection,
            QFrame#tifAnnotationSection,
            QFrame#tifMaterialSection,
            QFrame#tifLabelSchemaSection,
            QFrame#tifTrainingSection,
            QFrame#tifPartUserTagsSection,
            QFrame#tifTrainingResultSection,
            QFrame#tifBackendSection,
            QFrame#tifStatusSection,
            QFrame#tifLogSection {
                background: {t['section']};
                border: 1px solid {t['border']};
                border-radius: 12px;
            }
            QWidget#tifInspectorBody {
                background: transparent;
            }
            QScrollArea#tifInspectorScroll {
                background: transparent;
                border: none;
            }
            QScrollArea#tifInspectorScroll QScrollBar:vertical,
            QTextEdit#tifLogConsole QScrollBar:vertical {
                background: {t['scrollbar_track']};
                border: none;
                border-radius: 5px;
                margin: 0px;
                width: 10px;
            }
            QScrollArea#tifInspectorScroll QScrollBar::handle:vertical,
            QTextEdit#tifLogConsole QScrollBar::handle:vertical {
                background: {t['scrollbar_thumb']};
                border: 2px solid {t['scrollbar_track']};
                border-radius: 5px;
                min-height: 22px;
            }
            QScrollArea#tifInspectorScroll QScrollBar::handle:vertical:hover,
            QTextEdit#tifLogConsole QScrollBar::handle:vertical:hover {
                background: {t['scrollbar_thumb_hover']};
            }
            QScrollArea#tifInspectorScroll QScrollBar:horizontal,
            QTextEdit#tifLogConsole QScrollBar:horizontal {
                background: {t['scrollbar_track']};
                border: none;
                border-radius: 5px;
                height: 10px;
                margin: 0px;
            }
            QScrollArea#tifInspectorScroll QScrollBar::handle:horizontal,
            QTextEdit#tifLogConsole QScrollBar::handle:horizontal {
                background: {t['scrollbar_thumb']};
                border: 2px solid {t['scrollbar_track']};
                border-radius: 5px;
                min-width: 22px;
            }
            QScrollArea#tifInspectorScroll QScrollBar::handle:horizontal:hover,
            QTextEdit#tifLogConsole QScrollBar::handle:horizontal:hover {
                background: {t['scrollbar_thumb_hover']};
            }
            QScrollArea#tifInspectorScroll QScrollBar::add-line,
            QScrollArea#tifInspectorScroll QScrollBar::sub-line,
            QScrollArea#tifInspectorScroll QScrollBar::add-page,
            QScrollArea#tifInspectorScroll QScrollBar::sub-page,
            QTextEdit#tifLogConsole QScrollBar::add-line,
            QTextEdit#tifLogConsole QScrollBar::sub-line,
            QTextEdit#tifLogConsole QScrollBar::add-page,
            QTextEdit#tifLogConsole QScrollBar::sub-page {
                background: transparent;
                border: none;
            }
            QLabel#tifPanelTitle {
                color: {t['text']};
                font-weight: 700;
                padding-bottom: 4px;
                border: none;
            }
            QLabel#tifSectionTitle {
                color: {t['text_soft']};
                font-weight: 700;
                margin-top: 8px;
                border: none;
            }
            QFrame#tifCanvasShell {
                background: {t['canvas_shell']};
                border: 1px solid {t['border_strong']};
                border-radius: 12px;
            }
            QLabel#tifSliceCanvas {
                background: {t['canvas']};
                color: {t['canvas_text']};
                border: none;
                border-radius: 10px;
            }
            #tifVolumeCanvas {
                background: {t['canvas']};
                color: {t['canvas_text']};
                border: none;
                border-radius: 10px;
            }
            QLabel#tifVolumeRenderStatus {
                background: {t['input']};
                color: {t['text_soft']};
                border: 1px solid {t['border']};
                border-radius: 8px;
                padding: 5px 8px;
                font-size: 11px;
            }
            QLabel#tifLocalAxisStatusText {
                background: {t['input']};
                color: {t['text_soft']};
                border: 1px solid {t['border']};
                border-radius: 8px;
                padding: 5px 8px;
                font-size: 11px;
            }
            QLabel#tifOperationStatusText {
                background: {t['input']};
                color: {t['text']};
                border: 1px solid {t['border_strong']};
                border-radius: 8px;
                padding: 7px 9px;
            }
            QFrame#tifSliceBar {
                background: {t['panel_alt']};
                border: 1px solid {t['border']};
                border-radius: 12px;
            }
            QTreeWidget#tifSpecimenList,
            QTableWidget#tifMaterialTable,
            QTableWidget#tifPredictTargetsTable,
            QTableWidget#tifTrainingResultMetricsTable,
            QTableWidget#tifTrainingResultArtifactTable {
                background: {t['input']};
                alternate-background-color: {t['table_alt']};
                border: 1px solid {t['border']};
                border-radius: 10px;
                padding: 2px;
                selection-background-color: {t['selection']};
                selection-color: {t['selection_text']};
            }
            QTableWidget#tifMaterialTable::item,
            QTableWidget#tifPredictTargetsTable::item,
            QTableWidget#tifTrainingResultMetricsTable::item,
            QTableWidget#tifTrainingResultArtifactTable::item,
            QTreeWidget#tifSpecimenList::item {
                min-height: 24px;
                padding: 4px;
                border: none;
            }
            QTableWidget#tifMaterialTable QHeaderView::section,
            QTableWidget#tifPredictTargetsTable QHeaderView::section,
            QTableWidget#tifTrainingResultMetricsTable QHeaderView::section,
            QTableWidget#tifTrainingResultArtifactTable QHeaderView::section {
                background: {t['panel_alt']};
                color: {t['text_soft']};
                border: none;
                border-right: 1px solid {t['border']};
                padding: 5px 6px;
                font-weight: 700;
            }
            QLineEdit {
                background: {t['input']};
                color: {t['text']};
                border: 1px solid {t['border']};
                border-radius: 8px;
                padding: 4px 6px;
                selection-background-color: {t['selection']};
            }
            QPushButton {
                background: {t['button']};
                color: {t['text']};
                border: 1px solid {t['border_strong']};
                border-radius: 10px;
                padding: 8px 12px;
                font-weight: 700;
                min-height: 18px;
            }
            QPushButton:hover {
                background: {t['button_hover']};
                border-color: {t['glow_border']};
            }
            QPushButton:pressed {
                background: {t['button_pressed']};
                border-color: {t['glow_border']};
                padding-top: 9px;
                padding-bottom: 7px;
            }
            QPushButton:disabled {
                background: {t['button_disabled']};
                color: {t['text_dim']};
                border-color: {t['border']};
            }
            QPushButton[tifRole="primary"] {
                background: {t['primary']};
                border: 1px solid {t['glow_border']};
                color: #FFFFFF;
            }
            QPushButton[tifRole="primary"]:hover {
                background: {t['primary_hover']};
                border-color: {t['glow_border']};
            }
            QPushButton[tifRole="primary"]:pressed {
                background: {t['primary_pressed']};
                border-color: {t['glow_border']};
            }
            QPushButton[tifRole="secondary"] {
                background: {t['button']};
                border: 1px solid {t['border_strong']};
                color: {t['text_soft']};
            }
            QPushButton[tifRole="secondary"]:hover {
                background: {t['button_hover']};
                border-color: {t['glow_border']};
            }
            QPushButton[tifRole="secondary"]:checked {
                background: {t['secondary_checked']};
                border: 2px solid {t['glow_border']};
                color: {t['text']};
            }
            QPushButton[tifRole="danger"] {
                background: {t['danger']};
                border: 1px solid {t['danger_border']};
                color: {t['danger_text']};
            }
            QPushButton[tifRole="danger"]:hover {
                background: {t['danger_hover']};
                border-color: {t['danger_border']};
            }
            QPushButton[tifRole="danger"]:pressed {
                background: {t['danger_pressed']};
                border-color: {t['danger_border']};
            }
            QTextEdit#tifLogConsole {
                background: {t['input']};
                color: {t['text_soft']};
                border: 1px solid {t['border']};
                border-radius: 10px;
                padding: 6px;
            }
            QScrollArea#tifTrainingResultPreviewScroll {
                background: {t['input']};
                border: 1px solid {t['border']};
                border-radius: 10px;
            }
            QLabel#tifTrainingResultSummaryText {
                background: {t['input']};
                color: {t['text_soft']};
                border: 1px solid {t['border']};
                border-radius: 8px;
                padding: 6px 8px;
            }
            QLabel#tifPredictTargetsSummaryText {
                background: {t['input']};
                color: {t['text_soft']};
                border: 1px solid {t['border']};
                border-radius: 8px;
                padding: 6px 8px;
            }
            QLabel#tifLayerHelpText {
                color: {t['text_soft']};
                background: {t['input']};
                border: 1px solid {t['border']};
                border-radius: 8px;
                padding: 6px 8px;
            }
            QLabel#tifCurrentMaterialText {
                color: {t['text']};
                border: none;
                font-weight: 700;
            }
            QLabel#tifAutoSaveHintText {
                color: {t['text_dim']};
                border: none;
                font-size: 11px;
            }
            QLabel#tifSaveStatusText {
                background: {t['input']};
                color: {t['success']};
                border: 1px solid {t['success']};
                border-radius: 8px;
                padding: 5px 8px;
                font-weight: 700;
            }
            QLabel#tifSaveStatusText[tifSaveState="dirty"] {
                color: {t['warning']};
                border-color: {t['warning']};
            }
            QLabel#tifSaveStatusText[tifSaveState="saving"] {
                color: {t['accent']};
                border-color: {t['glow_border']};
            }
            QLabel#tifSaveStatusText[tifSaveState="failed"] {
                color: {t['error']};
                border-color: {t['error']};
            }
            QLabel#tifVolumeRenderStatus {
                background: {t['input']};
                color: {t['text_soft']};
                border: 1px solid {t['border']};
                border-radius: 6px;
                padding: 4px 8px;
            }
            QLabel#tifStatusText,
            QLabel#tifMetadataText,
            QLabel#tifLocalAxisSummaryText,
            QLabel#tifTrainingStatusText {
                color: {t['text_soft']};
                border: none;
            }
            QPushButton#tifExportTrainingButton,
            QPushButton#tifPrepareDatasetButton,
            QPushButton#tifTrainBackendButton,
            QPushButton#tifImportPredictionButton,
            QPushButton#tifImportStackButton,
            QPushButton#tifImportAmiraButton {
                font-weight: 700;
            }
            """
        for key, value in t.items():
            stylesheet = stylesheet.replace("{t['" + key + "']}", str(value))
        self.setStyleSheet(stylesheet)

    def set_theme(self, theme):
        self.current_theme = normalize_theme(theme)
        self._apply_soft_style()
        for canvas in (getattr(self, "canvas", None), getattr(self, "volume_canvas", None)):
            setter = getattr(canvas, "set_theme", None)
            if callable(setter):
                setter(self.current_theme)
        self._update_volume_render_status_label()
        if hasattr(self, "view_stack"):
            self.view_stack.update()

    def set_project_manager(self, project_manager):
        if not self._confirm_discard_or_save_working_edit():
            return
        self.close_project(prompt_unsaved=False)
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
        if (
            self._tif_import_thread is not None
            or self._tif_materialize_thread is not None
            or self._local_axis_reslice_export_thread is not None
            or self._part_mask_preview_thread is not None
            or self._confirm_part_roi_thread is not None
            or self._tif_backend_thread is not None
            or self._label_auto_save_thread is not None
            or self._label_manual_save_thread is not None
            or self._promote_thread is not None
        ):
            if prompt_unsaved:
                if self._label_auto_save_thread is not None or self._label_manual_save_thread is not None or self._promote_thread is not None:
                    message = self._backend_write_lock_message() if self._backend_write_lock_active() else tt("Auto-save is still finishing. Wait a moment, then try again.", self.lang)
                    title = self._backend_write_lock_title() if self._backend_write_lock_active() else tt("TIF backend", self.lang)
                    QMessageBox.information(self, title, message)
                    return False
                QMessageBox.information(
                    self,
                    tt("TIF data import", self.lang),
                    tt("Wait for the current backend task to finish before closing the project.", self.lang)
                    if self._tif_backend_thread is not None
                    else tt("Wait for the current background TIF task to finish before closing the project.", self.lang),
                )
            return False
        self._cancel_and_wait_volume_preview_build()
        self._wait_for_label_auto_save()
        if prompt_unsaved and not self._confirm_discard_or_save_working_edit():
            return False
        self.release_volume_renderer()
        self.image_volume = None
        self.label_volume = None
        self.part_mask_volume = None
        self.material_map = {}
        self.material_colors = {}
        self.current_specimen_id = ""
        self.edit_volume = None
        self._invalidate_result_region_mask_cache(clear_active_mask_preview=False)
        self._clear_volume_preview_cache()
        self._reset_edit_dirty_tracking()
        self.auto_save_timer.stop()
        if hasattr(self, "volume_still_timer"):
            self.volume_still_timer.stop()
        if getattr(self, "_tif_training_result_dialog", None) is not None:
            try:
                self._tif_training_result_dialog.close()
            except Exception:
                pass
            self._tif_training_result_dialog = None
        if hasattr(self, "training_result_summary_label"):
            self._set_training_result_summary(None)
        self.working_edit_dirty = False
        self.current_volume_scope = "full"
        self.current_part_id = ""
        self.current_part = None
        self.local_axis_draft = None
        self.part_preview_mask = None
        self.part_mask_preview_bbox = []
        self.part_mask_preview_accepted = False
        self.active_part_roi_id = ""
        self.part_roi_keyframes = []
        self.part_mask_keyframes = []
        self.undo_stack = []
        self.redo_stack = []
        self._sync_undo_redo_buttons()
        self._update_save_status()
        self.canvas.clear()
        self.volume_canvas.clear()
        self.canvas.setText(tt("No TIF volume loaded", self.lang))
        self.volume_canvas.setText(tt("No TIF volume loaded", self.lang))
        self._update_volume_render_status_label(tt("No TIF volume loaded", self.lang))
        return True

    def prepare_for_agent_panel(self):
        if hasattr(self, "volume_still_timer"):
            self.volume_still_timer.stop()
        if self.display_mode != "volume":
            self._reset_volume_canvas_placeholder_for_agent()
            return
        self.display_mode = "slice"
        index = self.display_mode_combo.findData("slice") if hasattr(self, "display_mode_combo") else -1
        if index >= 0:
            self.display_mode_combo.blockSignals(True)
            self.display_mode_combo.setCurrentIndex(index)
            self.display_mode_combo.blockSignals(False)
        self.on_display_mode_changed()
        self._reset_volume_canvas_placeholder_for_agent()

    def release_volume_renderer(self):
        canvas = getattr(self, "volume_canvas", None)
        if canvas is not None and hasattr(canvas, "release_gl_resources"):
            try:
                canvas.release_gl_resources()
            except Exception:
                pass

    def _current_slice_axis(self):
        axis = self.slice_axis_combo.currentData() if hasattr(self, "slice_axis_combo") else self.slice_axis
        return axis if axis in {"z", "y", "x"} else "z"

    def _slice_axis_dim(self, axis):
        return {"z": 0, "y": 1, "x": 2}.get(axis, 0)

    def _slice_count_for_axis(self, axis=None):
        if self.image_volume is None:
            return 1
        axis = axis or self._current_slice_axis()
        dim = self._slice_axis_dim(axis)
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
        self.release_volume_renderer()
        super().closeEvent(event)

    def refresh_project(self):
        previous_id = self.current_specimen_id
        previous_scope = self.current_volume_scope
        previous_part_id = self.current_part_id
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
            if not self._select_volume_tree_item(previous_id, previous_scope, previous_part_id):
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
        self._populate_tif_model_library_combo()
        self._sync_material_colors_from_active_source()
        self.refresh_predict_targets()
        self._refresh_result_comparison_if_visible()

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

    def _on_specimen_tree_selected(self, current, previous=None):
        if current is None:
            return
        if self._loading_specimen:
            return
        if previous is not None and self.working_edit_dirty:
            if not self._confirm_discard_or_save_working_edit():
                self._loading_specimen = True
                try:
                    self.specimen_list.setCurrentItem(previous)
                finally:
                    self._loading_specimen = False
                return
        payload = self._tree_item_payload(current)
        specimen_id = payload.get("specimen_id", "")
        previous_payload = self._tree_item_payload(previous) if previous is not None else {}
        target_key = (
            payload.get("scope", "full"),
            specimen_id,
            payload.get("part_id", ""),
            payload.get("reslice_id", ""),
        )
        previous_key = (
            previous_payload.get("scope", "full"),
            previous_payload.get("specimen_id", ""),
            previous_payload.get("part_id", ""),
            previous_payload.get("reslice_id", ""),
        )
        if previous is not None and target_key != previous_key and not bool(getattr(self, "_programmatic_volume_tree_select", False)):
            self._defer_volume_preview_render_once = True
            if self.display_mode == "volume":
                message = tt("Preparing full-volume 3D preview...", self.lang)
                show_canvas_status = self._set_volume_canvas_status_text(message, replace_existing=True)
                self._update_volume_render_status_label(message)
                if show_canvas_status:
                    QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)
        if payload.get("scope") in {"part", "part_reslices", "part_reslice"}:
            self.load_part(specimen_id, payload.get("part_id", ""), selected_reslice_id=payload.get("reslice_id", ""))
        else:
            self.load_specimen(specimen_id)

    def load_specimen(self, specimen_id):
        if specimen_id != self.current_specimen_id and self.working_edit_dirty:
            if not self._confirm_discard_or_save_working_edit():
                return
        specimen = self.project.get_specimen(specimen_id, default=None)
        if specimen is None:
            return
        if specimen_id != self.current_specimen_id or self.current_volume_scope != "full":
            self._cancel_volume_preview_build()
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
            self.part_preview_mask = None
            self.part_mask_preview_bbox = []
            self.part_mask_preview_accepted = False
            self.active_part_roi_id = ""
            self.part_roi_keyframes = []
            self.part_mask_keyframes = []
            self.part_roi_draw_mode = False
            self.part_contour_draw_mode = False
            self.btn_part_draw_roi.blockSignals(True)
            self.btn_part_draw_roi.setChecked(False)
            self.btn_part_draw_roi.blockSignals(False)
            self.btn_draw_part_contour.blockSignals(True)
            self.btn_draw_part_contour.setChecked(False)
            self.btn_draw_part_contour.blockSignals(False)
            # Part review should open as inspection first; otherwise the brush
            # radius cursor looks like a stray ROI/contour before the user edits.
            self.set_annotation_tool_mode("pan", show_message=False)
            self.image_volume = None
            self.label_volume = None
            self.part_mask_volume = None
            self.edit_volume = None
            self.working_edit_dirty = False
            self._reset_edit_dirty_tracking()
            self.material_map = {}
            self.material_colors = {}
            self._reset_active_volume_preview_state()
            self.undo_stack = []
            self.redo_stack = []
            self._populate_label_role_combo()
            self._clear_preview_resource_issue()

            image_path = self.project.to_absolute((specimen.get("working_volume") or {}).get("path", ""))
            if image_path and volume_sidecar_exists(image_path):
                self.image_volume, _load_issue = self._safe_load_volume_sidecar(image_path, mmap_mode="r", operation="load_specimen_image")
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
                if self._is_metadata_only_specimen(specimen) or self._materialize_task_matches(specimen_id):
                    message = self._volume_unavailable_message(specimen)
                    self.volume_canvas.setText(message)
                    self._update_volume_render_status_label(message)

            material_path = self.project.to_absolute(specimen.get("material_map", ""))
            if material_path and os.path.exists(material_path):
                self.material_map = read_material_map(material_path)
                self._sync_material_colors_from_active_source()
            self._populate_material_table()
            self._populate_label_schema_combo()
            self._populate_part_user_tag_table()
            self._populate_result_region_combo()
            self._invalidate_result_region_mask_cache(clear_active_mask_preview=False)
            self._refresh_result_comparison_if_visible()
            self._populate_volume_tint_combo()
            self._apply_volume_transfer_opacity_setting()
            self._populate_volume_mask_combo()
            self._reload_label_volume()
            self._reload_part_mask_volume()
            self._load_edit_volume()
            self._update_status_labels(specimen)
            self._apply_default_volume_mask_mode()
            self._sync_mode_sections()
            if not self._ensure_current_metadata_materializing_for_slice_review(specimen):
                self.render_current_slice()
            if self.display_mode == "volume":
                self.render_volume_preview()
        finally:
            self._loading_specimen = False

    def load_part(self, specimen_id, part_id, selected_reslice_id=""):
        if self.working_edit_dirty:
            if not self._confirm_discard_or_save_working_edit():
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
            self._cancel_volume_preview_build()
        self._loading_specimen = True
        try:
            self.auto_save_timer.stop()
            self.current_specimen_id = specimen_id
            self.current_volume_scope = "part"
            self.current_part_id = part.get("part_id", "")
            self.current_part = part
            self.current_reslice_id = str(selected_reslice_id or "")
            self._slice_unavailable_override = ""
            self._clear_local_axis_draft_if_part_changed(specimen_id, self.current_part_id)
            if self.current_reslice_id and self.local_axis_draft is not None:
                self._set_local_axis_status(tt("Selected saved reslice is read-only. Return to the part volume to edit axes or export another reslice.", self.lang))
            if self.current_reslice_id and hasattr(self, "volume_local_axes_check"):
                self.volume_local_axes_check.setChecked(True)
            self.active_part_roi_id = ""
            self.part_roi_keyframes = []
            self.part_mask_keyframes = []
            self.part_roi_draw_mode = False
            self.part_contour_draw_mode = False
            self.btn_part_draw_roi.blockSignals(True)
            self.btn_part_draw_roi.setChecked(False)
            self.btn_part_draw_roi.blockSignals(False)
            self.btn_draw_part_contour.blockSignals(True)
            self.btn_draw_part_contour.setChecked(False)
            self.btn_draw_part_contour.blockSignals(False)
            self.image_volume = None
            self.label_volume = None
            self.part_mask_volume = None
            self.edit_volume = None
            self.working_edit_dirty = False
            self._reset_edit_dirty_tracking()
            self.material_map = {}
            self.material_colors = {}
            self.part_preview_mask = None
            self.part_mask_preview_bbox = []
            self.part_mask_preview_accepted = False
            self._reset_active_volume_preview_state()
            self.undo_stack = []
            self.redo_stack = []
            self._populate_label_role_combo()
            self._clear_preview_resource_issue()

            reslice = self._current_part_reslice_record()
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
                    self.image_volume, _load_issue = self._safe_load_volume_sidecar(image_path, mmap_mode="r", operation="load_part_image")
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
                self.material_map = read_material_map(material_path)
                self._sync_material_colors_from_active_source()
            else:
                self._sync_material_colors_from_active_source()
            self._populate_material_table()
            self._populate_label_schema_combo()
            self._populate_part_user_tag_table()
            self._populate_result_region_combo()
            self._invalidate_result_region_mask_cache(clear_active_mask_preview=False)
            self._refresh_result_comparison_if_visible()
            self._populate_volume_tint_combo()
            self._apply_volume_transfer_opacity_setting()
            self._reload_label_volume()
            self._reload_part_mask_volume()
            self._load_edit_volume()
            self._update_status_labels(specimen, part=part)
            if self.current_reslice_id:
                self._set_local_axis_status(tt("Selected saved reslice is read-only. Return to the part volume to edit axes or export another reslice.", self.lang))
            self._apply_default_volume_mask_mode()
            self._sync_mode_sections()
            self.render_current_slice()
            if self.display_mode == "volume":
                self.render_volume_preview()
        finally:
            self._loading_specimen = False

    def _populate_material_table(self):
        self._sync_material_editor_scope()
        materials = self._active_materials()
        self.material_table.setRowCount(len(materials))
        for row, material in enumerate(materials):
            color_text = str(material.get("color", "#000000"))
            color_item = QTableWidgetItem("")
            color_item.setToolTip(color_text)
            try:
                color_item.setBackground(QColor(color_text))
            except Exception:
                pass
            self.material_table.setItem(row, 0, color_item)
            self.material_table.setItem(row, 1, QTableWidgetItem(str(material.get("id", ""))))
            self.material_table.setItem(row, 2, QTableWidgetItem(str(material.get("display_name") or material.get("name") or "")))
            self.material_table.setItem(row, 3, QTableWidgetItem(tt("yes", self.lang) if material.get("trainable") else tt("no", self.lang)))
        self.material_table.resizeColumnsToContents()
        if self.material_table.rowCount() > 1:
                self.material_table.selectRow(1)
        elif self.material_table.rowCount() == 1:
            self.material_table.selectRow(0)
        self._update_current_material_summary()

    def _selected_material(self):
        items = self.material_table.selectedItems()
        if not items:
            return None
        row = items[0].row()
        try:
            material_id = int(self.material_table.item(row, 1).text())
        except Exception:
            return None
        for material in self._active_materials():
            if int(material.get("id", -1)) == material_id:
                return dict(material)
        return None

    def _material_for_id(self, material_id):
        try:
            target_id = int(material_id)
        except Exception:
            target_id = 0
        for material in self._active_materials():
            try:
                if int(material.get("id", -1)) == target_id:
                    return dict(material)
            except Exception:
                continue
        if target_id == 0:
            return {"id": 0, "name": "background", "display_name": tt("Background / erase target", self.lang), "color": "#000000", "trainable": False}
        return None

    def _material_display_name(self, material_id=None):
        material = self._material_for_id(self.current_material_id if material_id is None else material_id)
        if material is None:
            return str(self.current_material_id if material_id is None else material_id)
        if int(material.get("id", 0)) == 0:
            return tt("Background / erase target", self.lang)
        return str(material.get("display_name") or material.get("name") or material.get("id", ""))

    def _material_color_text(self, material_id=None):
        material = self._material_for_id(self.current_material_id if material_id is None else material_id) or {}
        return str(material.get("color", "#000000") or "#000000")

    def _set_current_material_id(self, material_id, select_row=True, show_message=False, picked=False):
        try:
            material_id = int(material_id)
        except Exception:
            material_id = 0
        self.current_material_id = material_id
        if select_row and hasattr(self, "material_table"):
            for row in range(self.material_table.rowCount()):
                item = self.material_table.item(row, 1)
                if item is None:
                    continue
                try:
                    if int(item.text()) == material_id:
                        self.material_table.blockSignals(True)
                        self.material_table.selectRow(row)
                        self.material_table.blockSignals(False)
                        break
                except Exception:
                    continue
        self._update_current_material_summary()
        if show_message:
            material = self._material_for_id(material_id)
            if material is None:
                message = tt("Sampled label {0}, but it is not in the current label table.", self.lang).format(material_id)
            else:
                name = self._material_display_name(material_id)
                template = "Picked label {0}: {1}." if picked else "Selected label {0}: {1}."
                message = tt(template, self.lang).format(material_id, name)
            self._set_operation_feedback(message)
        return material_id

    def _update_current_material_summary(self):
        if not hasattr(self, "current_material_label"):
            return
        material_id = int(self.current_material_id)
        name = self._material_display_name(material_id)
        color_text = self._material_color_text(material_id)
        if self.annotation_tool_mode == "eraser":
            label_text = tt("Eraser writes background 0. Current label remains {0}: {1}.", self.lang).format(material_id, name)
        else:
            label_text = tt("Label {0}: {1}", self.lang).format(material_id, name)
        self.current_material_label.setText(label_text)
        self.current_material_label.setToolTip(label_text)
        self.current_material_swatch.setToolTip(color_text)
        self.current_material_swatch.setStyleSheet(
            "QLabel#tifCurrentMaterialSwatch {"
            f"background: {color_text};"
            "border: 2px solid #DCE4E8;"
            "border-radius: 8px;"
            "}"
        )

    def _material_map_path(self):
        if self.current_volume_scope == "part":
            return ""
        specimen = self.project.get_specimen(self.current_specimen_id, default=None)
        if specimen is None:
            return ""
        return self.project.to_absolute(specimen.get("material_map", ""))

    def _save_material_map(self):
        path = self._material_map_path()
        if not path:
            return
        self.material_map = write_material_map(path, self.material_map, source=self.material_map.get("source", "manual"))
        self._sync_material_colors_from_active_source()
        specimen = self.project.get_specimen(self.current_specimen_id, default=None)
        if specimen is not None:
            self._update_status_labels(specimen)
            self._populate_material_table()
            self._populate_result_region_combo()
            self._populate_volume_tint_combo()
        self.render_current_slice()

    def add_material(self):
        if not self.current_specimen_id:
            return
        if self.current_volume_scope == "part":
            QMessageBox.information(self, tt("Label table", self.lang), tt("Edit the bound label schema above to add, rename, or recolor labels for this part/reslice.", self.lang))
            return
        dialog = MaterialEditorDialog(next_id=next_material_id(self.material_map), parent=self, lang=self.lang)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.material_map = upsert_material(self.material_map, dialog.get_material())
            self._save_material_map()
        except Exception as exc:
            QMessageBox.warning(self, tt("Material map", self.lang), str(exc))

    def edit_selected_material(self):
        if self.current_volume_scope == "part":
            QMessageBox.information(self, tt("Label table", self.lang), tt("Edit the bound label schema above to add, rename, or recolor labels for this part/reslice.", self.lang))
            return
        material = self._selected_material()
        if material is None:
            return
        dialog = MaterialEditorDialog(material=material, parent=self, lang=self.lang)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.material_map = upsert_material(self.material_map, dialog.get_material())
            self._save_material_map()
        except Exception as exc:
            QMessageBox.warning(self, tt("Material map", self.lang), str(exc))

    def delete_selected_material(self):
        if self.current_volume_scope == "part":
            QMessageBox.information(self, tt("Label table", self.lang), tt("Edit the bound label schema above to add, rename, or recolor labels for this part/reslice.", self.lang))
            return
        material = self._selected_material()
        if material is None:
            return
        material_id = int(material.get("id", -1))
        if material_id == 0:
            QMessageBox.warning(self, tt("Label table", self.lang), tt("Background material cannot be deleted.", self.lang))
            return
        if self._material_id_is_used(material_id):
            QMessageBox.warning(self, tt("Material map", self.lang), tt("Material {0} is still used by a label volume.", self.lang).format(material_id))
            return
        reply = QMessageBox.question(
            self,
            tt("Label table", self.lang),
            tt("Delete material {0} ({1})?", self.lang).format(material_id, material.get("display_name", material.get("name", ""))),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            self.material_map = remove_material(self.material_map, material_id)
            self._save_material_map()
        except Exception as exc:
            QMessageBox.warning(self, tt("Material map", self.lang), str(exc))

    def _material_id_is_used(self, material_id):
        arrays = []
        if self.edit_volume is not None:
            arrays.append(self.edit_volume)
        if self.label_volume is not None:
            arrays.append(self.label_volume)
        specimen = self.project.get_specimen(self.current_specimen_id, default=None)
        if specimen is not None:
            label_records = []
            labels = specimen.get("labels") or {}
            label_records.extend([labels.get("manual_truth") or {}, labels.get("working_edit") or {}])
            label_records.extend(labels.get("model_drafts") or [])
            if self.current_volume_scope == "part":
                part_labels = ((self.current_part or {}).get("labels") or {})
                label_records.extend(
                    [
                        part_labels.get("manual_truth") or {},
                        part_labels.get("editable_ai_result") or {},
                        part_labels.get("raw_ai_prediction_backup") or {},
                    ]
                )
            for record in label_records:
                path = self.project.to_absolute((record or {}).get("path", ""))
                if path and volume_sidecar_exists(path):
                    try:
                        arrays.append(load_volume_sidecar(path, mmap_mode="r"))
                    except Exception:
                        pass
        for array in arrays:
            try:
                z_count = int(array.shape[0]) if getattr(array, "ndim", 0) == 3 else 0
                for z_index in range(z_count):
                    if np.any(np.asarray(array[z_index]) == int(material_id)):
                        return True
            except Exception:
                continue
        return False

    def _on_material_selected(self):
        items = self.material_table.selectedItems()
        if not items:
            return
        row = items[0].row()
        try:
            material_id = int(self.material_table.item(row, 1).text())
        except Exception:
            material_id = 0
        self._set_current_material_id(material_id, select_row=False, show_message=not self._loading_specimen)

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

    def _current_part_label_path(self, role=None):
        record = self._current_part_label_record(role)
        return self.project.to_absolute((record or {}).get("path", ""))

    def _current_part_label_image_path(self):
        if self.current_volume_scope != "part" or not self.current_specimen_id or not self.current_part_id:
            return ""
        reslice = self._current_part_reslice_record()
        if isinstance(reslice, dict) and reslice.get("image_path"):
            path = self.project.to_absolute(reslice.get("image_path", ""))
            return path if path and os.path.exists(path) else ""
        part = self.project.get_part(self.current_specimen_id, self.current_part_id, default=None)
        path = self.project.to_absolute(((part or {}).get("image") or {}).get("path", ""))
        return path if path and volume_sidecar_exists(path) else ""

    def _reload_label_volume(self):
        self.label_volume = None
        self._update_label_role_help()
        if self.current_volume_scope == "part":
            role = self.label_role_combo.currentData() or "editable_ai_result"
            label_path = self._current_part_label_path(role)
            if label_path and volume_sidecar_exists(label_path):
                self.label_volume, _load_issue = self._safe_load_volume_sidecar(label_path, mmap_mode="r", operation=f"load_part_label:{role}")
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
        if label_path and volume_sidecar_exists(label_path):
            self.label_volume, _load_issue = self._safe_load_volume_sidecar(label_path, mmap_mode="r", operation=f"load_label:{role}")
        self.render_current_slice()

    def _load_edit_volume(self):
        self.edit_volume = None
        if self.current_volume_scope == "part":
            edit_path = self._current_part_label_path("editable_ai_result")
            if edit_path and volume_sidecar_exists(edit_path):
                self.edit_volume, _load_issue = self._safe_load_volume_sidecar(edit_path, mmap_mode="c", operation="load_part_edit_volume")
            return
        specimen = self.project.get_specimen(self.current_specimen_id, default=None)
        if specimen is None:
            return
        edit_path = self.project.to_absolute(((specimen.get("labels") or {}).get("working_edit") or {}).get("path", ""))
        if edit_path and volume_sidecar_exists(edit_path):
            self.edit_volume, _load_issue = self._safe_load_volume_sidecar(edit_path, mmap_mode="c", operation="load_working_edit_volume")

    def _current_part_mask_path(self):
        if self.current_volume_scope != "part" or self.current_reslice_id:
            return ""
        part = self.project.get_part(self.current_specimen_id, self.current_part_id, default=None)
        mask_path = self.project.to_absolute(((part or {}).get("mask") or {}).get("path", ""))
        return mask_path if mask_path else ""

    def _reload_part_mask_volume(self):
        self.part_mask_volume = None
        if self.current_volume_scope != "part":
            return
        mask_path = self._current_part_mask_path()
        if mask_path and volume_sidecar_exists(mask_path):
            self.part_mask_volume, _load_issue = self._safe_load_volume_sidecar(mask_path, mmap_mode="r", operation="load_part_mask_volume")

    def _ensure_working_edit_volume(self):
        if not self._guard_backend_write_lock():
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
                    self.edit_volume, _load_issue = self._safe_load_volume_sidecar(edit_path, mmap_mode="c", operation="ensure_part_edit_volume")
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
                self.edit_volume, _load_issue = self._safe_load_volume_sidecar(edit_abs, mmap_mode="c", operation="open_created_part_edit_volume")
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
                self.edit_volume, _load_issue = self._safe_load_volume_sidecar(edit_path, mmap_mode="c", operation="ensure_working_edit_volume")
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
        self.edit_volume, _load_issue = self._safe_load_volume_sidecar(edit_abs, mmap_mode="c", operation="open_created_working_edit_volume")
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
        if self._backend_action_running():
            self.btn_prepare_dataset.setEnabled(False)
            self.btn_train_backend.setEnabled(False)
            self.btn_import_prediction.setEnabled(False)
            self.btn_accept_selected_ai_results.setEnabled(False)
            self.btn_stop_backend.setEnabled(True)
        else:
            self.btn_stop_backend.setEnabled(False)
            self.btn_open_backend_run.setEnabled(bool(self._tif_backend_run_dir) and os.path.isdir(self._tif_backend_run_dir))
            self.btn_open_backend_result.setEnabled(bool(self._tif_backend_result_json) and os.path.exists(self._tif_backend_result_json))
        self._refresh_training_result_controls()
        self.btn_copy_draft.setEnabled(full_volume_editable)
        self.btn_import_external_prediction_tif.setEnabled(full_volume_editable)
        if hasattr(self, "btn_export_current_rendering"):
            self.btn_export_current_rendering.setEnabled(has_image)
        if hasattr(self, "btn_refresh_result_comparison"):
            self._sync_result_comparison_controls()
        self.auto_save_check.setEnabled(label_editable)
        self.btn_add_material.setEnabled(full_volume_editable)
        self.btn_edit_material.setEnabled(full_volume_editable)
        self.btn_delete_material.setEnabled(full_volume_editable)
        if hasattr(self, "btn_bind_label_schema_to_part"):
            self.btn_bind_label_schema_to_part.setEnabled(is_part and has_image)
        if hasattr(self, "btn_apply_part_user_tags"):
            self.btn_apply_part_user_tags.setEnabled(is_part)
        if hasattr(self, "btn_choose_part_user_tag_color"):
            self.btn_choose_part_user_tag_color.setEnabled(not self._backend_write_lock_active())
        confirm_part_busy = self._confirm_part_roi_running()
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
        part_mask_preview_busy = self._part_mask_preview_running()
        self.btn_preview_part_mask.setEnabled((is_editable_part_volume or full_volume_editable) and has_image and not part_mask_preview_busy and not confirm_part_busy)
        self.btn_accept_part_mask.setEnabled((is_editable_part_volume or full_volume_editable) and self.part_preview_mask is not None and not part_mask_preview_busy and not confirm_part_busy)
        self.btn_clear_part_preview.setEnabled((is_editable_part_volume or full_volume_editable) and self.part_preview_mask is not None and not part_mask_preview_busy and not confirm_part_busy)
        local_axis_export_busy = self._local_axis_reslice_export_running()
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
        self.btn_delete_part_volume.setEnabled(is_editable_part_volume and self.current_part is not None)
        write_locked = self._backend_write_lock_active()
        self._set_backend_write_locked_controls(write_locked)
        if write_locked and not self._backend_write_lock_active(ignored_task_types=self._local_axis_draft_lock_ignored_task_types()):
            self.btn_copy_source_z_axis.setEnabled(local_axis_editable)
            self.btn_pick_roll_ref_a.setEnabled(local_axis_editable)
            self.btn_pick_roll_ref_b.setEnabled(local_axis_editable)
            self.btn_pick_roll_ref_c.setEnabled(local_axis_editable)
            self.btn_align_axis_to_reference_plane.setEnabled(local_axis_editable)
            self.btn_clear_roll_refs.setEnabled(local_axis_editable)
            self.btn_clear_local_axis_draft.setEnabled(local_axis_editable)
            self.local_axis_trainable_check.setEnabled(local_axis_editable)
        self._update_local_axis_summary()
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
            draft = self._current_local_axis_draft()
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
        resource_summary = self._preview_resource_summary()
        if resource_summary.get("resource_limited"):
            return str(resource_summary.get("user_message") or "")
        if self.image_volume is None:
            return ""
        return (
            f"{tt('3D volume', self.lang)} | "
            f"{self._volume_renderer_label()} | "
            f"{self._volume_mode_label()} | "
            f"{tt('drag rotate / wheel zoom', self.lang)} | "
            f"{int(round(self._volume_zoom * 100))}%"
        )

    def _can_edit_current_label_volume(self):
        if self._backend_write_lock_active():
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

    def _local_axis_overlay_enabled(self):
        return bool(
            getattr(self, "volume_local_axes_check", None)
            and self.volume_local_axes_check.isChecked()
            and self.current_volume_scope == "part"
            and self.image_volume is not None
        )

    def _is_editable_part_volume(self):
        return bool(self.current_volume_scope == "part" and not self.current_reslice_id)

    def _clear_local_axis_draft_if_part_changed(self, specimen_id="", part_id=""):
        return self.local_axis_controller.clear_draft_if_part_changed(specimen_id, part_id)

    def _source_z_axis_for_current_part(self):
        return self.local_axis_controller.source_z_axis_for_current_part()

    def copy_source_z_axis_to_local_axis_draft(self):
        return self.local_axis_controller.copy_source_z_axis_to_draft()

    def _current_part_reslice_record(self):
        if not self.current_specimen_id or not self.current_part_id or not self.current_reslice_id:
            return None
        return self.project.get_part_reslice(self.current_specimen_id, self.current_part_id, self.current_reslice_id, default=None)

    def _current_local_axis_draft(self):
        return self.local_axis_controller.current_draft()

    def _format_local_axis_point_pair(self, axis):
        if not isinstance(axis, dict):
            return "-"
        start = axis.get("start_zyx") or []
        end = axis.get("end_zyx") or []
        if not start or not end:
            return "-"
        return "{0} -> {1}".format(start, end)

    def _format_local_axis_point(self, values):
        if not values or len(values) != 3:
            return "-"
        return "[{0}]".format(", ".join(f"{float(value):.3f}" for value in values))

    def _format_local_axis_vector(self, values):
        if not values or len(values) != 3:
            return "-"
        return "[{0}]".format(", ".join(f"{float(value):.3f}" for value in values))

    def _local_axis_relation_metrics(self, editable_axis, roll_reference):
        editable = editable_axis if isinstance(editable_axis, dict) else {}
        roll = roll_reference if isinstance(roll_reference, dict) else {}
        point_a = roll.get("point_a") if isinstance(roll.get("point_a"), dict) else {}
        point_b = roll.get("point_b") if isinstance(roll.get("point_b"), dict) else {}
        try:
            start = np.asarray(editable.get("start_zyx") or [], dtype=np.float64)
            end = np.asarray(editable.get("end_zyx") or [], dtype=np.float64)
            a = np.asarray(point_a.get("zyx") or [], dtype=np.float64)
            b = np.asarray(point_b.get("zyx") or [], dtype=np.float64)
        except (TypeError, ValueError):
            return None
        if start.size != 3 or end.size != 3 or a.size != 3 or b.size != 3:
            return None
        spacing = np.asarray(self._local_axis_spacing_zyx(), dtype=np.float64)
        if spacing.size != 3 or np.any(spacing <= 0):
            spacing = np.ones(3, dtype=np.float64)
        start_w = start * spacing
        end_w = end * spacing
        a_w = a * spacing
        b_w = b * spacing
        axis_w = end_w - start_w
        axis_len = float(np.linalg.norm(axis_w))
        if axis_len <= 1e-8:
            return None
        axis_unit = axis_w / axis_len

        def projection(point_w):
            offset = point_w - start_w
            along = float(np.dot(offset, axis_unit))
            lateral_vec = offset - along * axis_unit
            return along, float(np.linalg.norm(lateral_vec))

        a_along, a_lateral = projection(a_w)
        b_along, b_lateral = projection(b_w)
        roll_vec = b_w - a_w
        roll_projected = roll_vec - float(np.dot(roll_vec, axis_unit)) * axis_unit
        roll_width = float(np.linalg.norm(roll_projected))
        status = "usable" if roll_width > 1e-6 else "parallel to output Z"
        return {
            "a_along": a_along,
            "b_along": b_along,
            "a_lateral": a_lateral,
            "b_lateral": b_lateral,
            "z_separation": float(b_along - a_along),
            "roll_width": roll_width,
            "status": status,
        }

    def _format_local_axis_relation_metrics(self, editable_axis, roll_reference):
        metrics = self._local_axis_relation_metrics(editable_axis, roll_reference)
        if not metrics:
            return [
                f"{tt('Axis/reference relation', self.lang)}: {tt('needs two reference points', self.lang)}",
            ]
        unit = self._local_axis_spacing_unit()
        return [
            f"{tt('Axis/reference relation', self.lang)}: {tt(metrics['status'], self.lang)}",
            f"{tt('Roll A projection on output Z', self.lang)}: {metrics['a_along']:.2f} {unit}",
            f"{tt('Roll B projection on output Z', self.lang)}: {metrics['b_along']:.2f} {unit}",
            f"{tt('A/B separation along output Z', self.lang)}: {metrics['z_separation']:.2f} {unit}",
            f"{tt('A/B lateral distance to output Z', self.lang)}: A {metrics['a_lateral']:.2f} / B {metrics['b_lateral']:.2f} {unit}",
            f"{tt('A/B projected roll width', self.lang)}: {metrics['roll_width']:.2f} {unit}",
        ]

    def _roll_reference_payload(self, draft=None):
        return self.local_axis_controller.roll_reference_payload(draft)

    def _local_axis_spacing_zyx(self):
        return self.local_axis_controller.spacing_zyx()

    def _local_axis_spacing_unit(self):
        return self.local_axis_controller.spacing_unit()

    def _local_axis_origin_from_editable_axis(self, editable_axis):
        return self.local_axis_controller.origin_from_editable_axis(editable_axis)

    def _set_local_axis_draft(self, draft, status_message=""):
        return self.local_axis_controller.set_draft(draft, status_message=status_message)

    def _refresh_local_axis_frame(self, draft=None):
        return self.local_axis_controller.refresh_frame(draft)

    def _update_local_axis_summary(self):
        label = getattr(self, "local_axis_summary_label", None)
        if label is None:
            return
        details_label = getattr(self, "local_axis_details_label", None)
        details_check = getattr(self, "local_axis_details_check", None)
        if self.current_volume_scope != "part" or not self.current_part_id or self.image_volume is None:
            label.setText(tt("Local axis unavailable. Select a part volume.", self.lang))
            if details_label is not None:
                details_label.setText("")
                details_label.setVisible(False)
            if details_check is not None:
                details_check.setVisible(False)
            return
        lines = [
            f"{tt('Part', self.lang)}: {self.current_part_id}",
            tt("Source Z axis: locked reference", self.lang),
            tt(
                "3D overlay: on" if self.display_mode == "volume" and self._local_axis_overlay_enabled() else "3D overlay: off",
                self.lang,
            ),
        ]
        detail_lines = []
        draft = self._current_local_axis_draft()
        frame = None
        if draft is not None:
            editable = draft.get("editable_axis") or {}
            lines.append(
                tt("Draft output Z: {0}", self.lang).format(
                    self._format_local_axis_point_pair(editable)
                )
            )
            roll = draft.get("roll_reference") if isinstance(draft.get("roll_reference"), dict) else {}
            point_a = roll.get("point_a") if isinstance(roll.get("point_a"), dict) else {}
            point_b = roll.get("point_b") if isinstance(roll.get("point_b"), dict) else {}
            point_c = roll.get("point_c") if isinstance(roll.get("point_c"), dict) else {}
            if point_a.get("zyx") or point_b.get("zyx"):
                lines.append(
                    tt("Roll reference: {0}", self.lang).format(
                        f"A={tt('set' if point_a.get('zyx') else 'not set', self.lang)} / "
                        f"B={tt('set' if point_b.get('zyx') else 'not set', self.lang)}"
                    )
                )
            else:
                lines.append(tt("Roll reference: A/B not set", self.lang))
            lines.append(tt("Plane reference: C {0}", self.lang).format(tt("set" if point_c.get("zyx") else "not set", self.lang)))
            frame = self._refresh_local_axis_frame(draft)
            lines.append(tt("Frame status: ready" if isinstance(frame, dict) else "Frame status: waiting for roll reference", self.lang))
            detail_lines.extend(
                [
                    f"{tt('Output axis start z,y,x', self.lang)}: {self._format_local_axis_point(editable.get('start_zyx'))}",
                    f"{tt('Output axis end z,y,x', self.lang)}: {self._format_local_axis_point(editable.get('end_zyx'))}",
                    f"{tt('Roll reference A', self.lang)}: {self._format_local_axis_point(point_a.get('zyx'))}",
                    f"{tt('Roll reference B', self.lang)}: {self._format_local_axis_point(point_b.get('zyx'))}",
                    f"{tt('Plane reference C', self.lang)}: {self._format_local_axis_point(point_c.get('zyx'))}",
                ]
            )
            reference_plane = roll.get("reference_plane") if isinstance(roll.get("reference_plane"), dict) else draft.get("reference_plane") if isinstance(draft.get("reference_plane"), dict) else {}
            if isinstance(reference_plane, dict) and reference_plane.get("normal_axis_zyx"):
                detail_lines.append(f"{tt('Reference plane normal', self.lang)}: {self._format_local_axis_vector(reference_plane.get('normal_axis_zyx'))}")
            detail_lines.extend(self._format_local_axis_relation_metrics(editable, roll))
            if isinstance(frame, dict):
                detail_lines.extend(
                    [
                        f"{tt('Local frame', self.lang)} {tt('x_axis', self.lang)}: {self._format_local_axis_vector(frame.get('x_axis'))}",
                        f"{tt('Local frame', self.lang)} {tt('y_axis', self.lang)}: {self._format_local_axis_vector(frame.get('y_axis'))}",
                        f"{tt('Local frame', self.lang)} {tt('z_axis', self.lang)}: {self._format_local_axis_vector(frame.get('z_axis'))}",
                    ]
                )
        else:
            lines.append(tt("Draft output Z: none", self.lang))
            lines.append(tt("Roll reference: A/B not set", self.lang))
            lines.append(tt("Plane reference: C {0}", self.lang).format(tt("not set", self.lang)))
        reslice = self._current_part_reslice_record()
        if isinstance(reslice, dict):
            lines.append(tt("Saved reslice: {0}", self.lang).format(reslice.get("reslice_id", "")))
            saved_axis = ((reslice.get("source") or {}).get("editable_axis") or {})
            saved_frame = reslice.get("local_frame") if isinstance(reslice.get("local_frame"), dict) else {}
            detail_lines.extend(
                [
                    f"{tt('Reslice ID', self.lang)}: {reslice.get('reslice_id', '')}",
                    f"{tt('Image', self.lang)}: {reslice.get('image_path', '')}",
                    f"{tt('Metadata', self.lang)}: {reslice.get('metadata_path', '')}",
                    f"{tt('Output axis start z,y,x', self.lang)}: {self._format_local_axis_point(saved_axis.get('start_zyx'))}",
                    f"{tt('Output axis end z,y,x', self.lang)}: {self._format_local_axis_point(saved_axis.get('end_zyx'))}",
                ]
            )
            saved_roll = (
                saved_frame.get("roll_reference")
                if isinstance(saved_frame.get("roll_reference"), dict)
                else reslice.get("roll_reference")
                if isinstance(reslice.get("roll_reference"), dict)
                else {}
            )
            detail_lines.extend(self._format_local_axis_relation_metrics(saved_axis, saved_roll))
            if saved_frame:
                detail_lines.extend(
                    [
                        f"{tt('Local frame', self.lang)} {tt('x_axis', self.lang)}: {self._format_local_axis_vector(saved_frame.get('x_axis'))}",
                        f"{tt('Local frame', self.lang)} {tt('y_axis', self.lang)}: {self._format_local_axis_vector(saved_frame.get('y_axis'))}",
                        f"{tt('Local frame', self.lang)} {tt('z_axis', self.lang)}: {self._format_local_axis_vector(saved_frame.get('z_axis'))}",
                    ]
                )
        else:
            lines.append(tt("Saved reslice: none selected", self.lang))
        label.setText("\n".join(lines))
        if details_label is not None:
            details_label.setText("\n".join(detail_lines))
            details_label.setVisible(bool(details_check and details_check.isChecked() and detail_lines))
        if details_check is not None:
            details_check.setVisible(bool(detail_lines))

    def _project_zyx_to_volume_xy(self, point_zyx, shape_zyx, source_shape=None, spacing_zyx=None):
        if not point_zyx or len(point_zyx) != 3:
            return None
        shape = tuple(max(1, int(value)) for value in (shape_zyx or (1, 1, 1)))
        if len(shape) != 3:
            return None
        z, y, x = [float(value) for value in point_zyx]
        dims = np.array([max(1, shape[0] - 1), max(1, shape[1] - 1), max(1, shape[2] - 1)], dtype=np.float32)
        coord = np.array([x / dims[2], y / dims[1], z / dims[0]], dtype=np.float32) - 0.5
        x_scale, y_scale, z_scale = volume_shape_scale(source_shape or shape, spacing_zyx)
        coord[0] *= x_scale
        coord[1] *= y_scale
        coord[2] *= z_scale

        yaw = math.radians(float(self._volume_yaw))
        pitch = math.radians(float(self._volume_pitch))
        cy, sy = math.cos(yaw), math.sin(yaw)
        cp, sp = math.cos(pitch), math.sin(pitch)
        rot_yaw = np.array([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]], dtype=np.float32)
        rot_pitch = np.array([[1.0, 0.0, 0.0], [0.0, cp, -sp], [0.0, sp, cp]], dtype=np.float32)
        rotated = coord @ (rot_yaw @ rot_pitch).T

        width = max(1.0, float(self.volume_canvas.width()) if hasattr(self, "volume_canvas") else 1.0)
        height = max(1.0, float(self.volume_canvas.height()) if hasattr(self, "volume_canvas") else 1.0)
        scale = (min(width, height) * 0.78) * float(self._volume_zoom)
        pan_scale = height * 0.5
        center_x = width / 2.0 + float(self._volume_pan_x) * pan_scale
        center_y = height / 2.0 - float(self._volume_pan_y) * pan_scale
        return [float(rotated[0] * scale + center_x), float(-rotated[1] * scale + center_y)]

    def _local_axis_source_point_for_current_reslice(self, point_zyx, saved_reslice=None):
        if not self.current_reslice_id or not point_zyx:
            return point_zyx
        record = saved_reslice if isinstance(saved_reslice, dict) else self._current_part_reslice_record()
        if not isinstance(record, dict):
            return point_zyx
        frame = record.get("local_frame") if isinstance(record.get("local_frame"), dict) else {}
        params = record.get("reslice_params") if isinstance(record.get("reslice_params"), dict) else {}
        if not frame or not params:
            return point_zyx
        try:
            return source_point_to_reslice_point(point_zyx, frame, params)
        except Exception:
            return point_zyx

    def _local_axis_axis_for_current_reslice(self, axis, saved_reslice=None):
        if not isinstance(axis, dict):
            return {}
        if not self.current_reslice_id:
            return axis
        converted = dict(axis)
        for key in ("start_zyx", "end_zyx"):
            if axis.get(key):
                converted[key] = self._local_axis_source_point_for_current_reslice(axis.get(key), saved_reslice=saved_reslice)
        return converted

    def _local_axis_roll_for_current_reslice(self, roll, saved_reslice=None):
        if not isinstance(roll, dict):
            return {}
        if not self.current_reslice_id:
            return roll
        converted = dict(roll)
        for key in ("point_a", "point_b", "point_c"):
            point = roll.get(key) if isinstance(roll.get(key), dict) else {}
            if point.get("zyx"):
                converted_point = dict(point)
                converted_point["zyx"] = self._local_axis_source_point_for_current_reslice(point.get("zyx"), saved_reslice=saved_reslice)
                converted[key] = converted_point
        return converted

    def _local_axis_projection_context(self):
        shape = tuple(int(value) for value in getattr(self.image_volume, "shape", ()) or ())
        if len(shape) != 3 or min(shape) <= 0:
            return None
        source_shape, spacing_zyx = self._volume_source_geometry()
        x_scale, y_scale, z_scale = volume_shape_scale(source_shape or shape, spacing_zyx)
        yaw = math.radians(float(self._volume_yaw))
        pitch = math.radians(float(self._volume_pitch))
        cy, sy = math.cos(yaw), math.sin(yaw)
        cp, sp = math.cos(pitch), math.sin(pitch)
        rot_yaw = np.array([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]], dtype=np.float64)
        rot_pitch = np.array([[1.0, 0.0, 0.0], [0.0, cp, -sp], [0.0, sp, cp]], dtype=np.float64)
        rotation = rot_yaw @ rot_pitch
        width = max(1.0, float(self.volume_canvas.width()) if hasattr(self, "volume_canvas") else 1.0)
        height = max(1.0, float(self.volume_canvas.height()) if hasattr(self, "volume_canvas") else 1.0)
        scale = (min(width, height) * 0.78) * float(self._volume_zoom)
        pan_scale = height * 0.5
        return {
            "shape": shape,
            "dims": np.array([max(1, shape[0] - 1), max(1, shape[1] - 1), max(1, shape[2] - 1)], dtype=np.float64),
            "shape_scale": np.array([x_scale, y_scale, z_scale], dtype=np.float64),
            "rotation": rotation,
            "scale": max(1e-6, scale),
            "center_x": width / 2.0 + float(self._volume_pan_x) * pan_scale,
            "center_y": height / 2.0 - float(self._volume_pan_y) * pan_scale,
        }

    def _local_axis_point_rotated_depth(self, point_zyx, context=None):
        if not point_zyx or len(point_zyx) != 3:
            return None
        context = context or self._local_axis_projection_context()
        if context is None:
            return None
        z, y, x = [float(value) for value in point_zyx]
        dims = np.asarray(context["dims"], dtype=np.float64)
        coord = np.array([x / dims[2], y / dims[1], z / dims[0]], dtype=np.float64) - 0.5
        coord *= np.asarray(context["shape_scale"], dtype=np.float64)
        rotated = coord @ np.asarray(context["rotation"], dtype=np.float64).T
        return float(rotated[2])

    def _volume_xy_to_zyx_at_depth(self, x, y, rotated_depth, context=None):
        context = context or self._local_axis_projection_context()
        if context is None:
            return None
        rotated = np.array(
            [
                (float(x) - float(context["center_x"])) / float(context["scale"]),
                -(float(y) - float(context["center_y"])) / float(context["scale"]),
                float(rotated_depth),
            ],
            dtype=np.float64,
        )
        coord = rotated @ np.asarray(context["rotation"], dtype=np.float64)
        coord = coord / np.maximum(np.asarray(context["shape_scale"], dtype=np.float64), 1e-6)
        normalized_xyz = coord + 0.5
        dims = np.asarray(context["dims"], dtype=np.float64)
        point = np.array(
            [
                normalized_xyz[2] * dims[0],
                normalized_xyz[1] * dims[1],
                normalized_xyz[0] * dims[2],
            ],
            dtype=np.float64,
        )
        shape = context["shape"]
        upper = np.array([max(0, shape[0] - 1), max(0, shape[1] - 1), max(0, shape[2] - 1)], dtype=np.float64)
        point = np.clip(point, np.zeros(3, dtype=np.float64), upper)
        return [float(value) for value in point]

    def _clip_plane_rotated_depth(self, context=None):
        context = context or self._local_axis_projection_context()
        if context is None:
            return None
        shape_scale = np.asarray(context["shape_scale"], dtype=np.float64)
        half_size = shape_scale * 0.5
        view_normal = np.asarray([0.0, 0.0, 1.0], dtype=np.float64)
        extent = max(float(np.dot(np.abs(view_normal), half_size)), 0.0001)
        depth = float(self.volume_clip_plane_depth_slider.value()) / 100.0 if hasattr(self, "volume_clip_plane_depth_slider") else 0.0
        return float((1.0 - 2.0 * max(0.0, min(1.0, depth))) * extent)

    def _volume_xy_to_zyx_on_clip_plane(self, x, y):
        context = self._local_axis_projection_context()
        depth = self._clip_plane_rotated_depth(context)
        if depth is None:
            return None
        return self._volume_xy_to_zyx_at_depth(x, y, depth, context)

    def _hit_local_axis_endpoint(self, x, y):
        draft = self._current_local_axis_draft()
        if not isinstance(draft, dict) or self.current_reslice_id:
            return None
        editable = draft.get("editable_axis") or {}
        if editable.get("locked"):
            return None
        context = self._local_axis_projection_context()
        if context is None:
            return None
        candidates = []
        for endpoint_key in ("start_zyx", "end_zyx"):
            point = editable.get(endpoint_key)
            xy = self._project_zyx_to_volume_xy(point, context["shape"])
            if xy is None:
                continue
            distance = math.hypot(float(x) - float(xy[0]), float(y) - float(xy[1]))
            candidates.append((distance, endpoint_key, point, xy))
        if not candidates:
            return None
        distance, endpoint_key, point, xy = min(candidates, key=lambda item: item[0])
        hit_radius = max(10.0, min(22.0, 8.0 + float(self._volume_zoom) * 1.2))
        if distance > hit_radius:
            return None
        return {
            "endpoint_key": endpoint_key,
            "start_mouse_xy": [float(x), float(y)],
            "start_point_zyx": [float(value) for value in point],
            "rotated_depth": self._local_axis_point_rotated_depth(point, context),
            "context": context,
            "hit_xy": xy,
        }

    def _hit_local_axis_body(self, x, y):
        draft = self._current_local_axis_draft()
        if not isinstance(draft, dict) or self.current_reslice_id:
            return None
        editable = draft.get("editable_axis") or {}
        if editable.get("locked"):
            return None
        context = self._local_axis_projection_context()
        if context is None:
            return None
        start = editable.get("start_zyx") or []
        end = editable.get("end_zyx") or []
        start_xy = self._project_zyx_to_volume_xy(start, context["shape"])
        end_xy = self._project_zyx_to_volume_xy(end, context["shape"])
        if not start_xy or not end_xy:
            return None
        segment = np.asarray(end_xy, dtype=np.float64) - np.asarray(start_xy, dtype=np.float64)
        length_sq = float(np.dot(segment, segment))
        if length_sq <= 1e-6:
            return None
        mouse = np.asarray([float(x), float(y)], dtype=np.float64)
        start_arr = np.asarray(start_xy, dtype=np.float64)
        fraction = max(0.0, min(1.0, float(np.dot(mouse - start_arr, segment) / length_sq)))
        closest = start_arr + segment * fraction
        distance = float(np.linalg.norm(mouse - closest))
        hit_radius = max(8.0, min(18.0, 7.0 + float(self._volume_zoom) * 0.9))
        if distance > hit_radius:
            return None
        start_depth = self._local_axis_point_rotated_depth(start, context)
        end_depth = self._local_axis_point_rotated_depth(end, context)
        if start_depth is None or end_depth is None:
            return None
        anchor_depth = start_depth + (end_depth - start_depth) * fraction
        anchor_point = self._volume_xy_to_zyx_at_depth(x, y, anchor_depth, context)
        if anchor_point is None:
            return None
        return {
            "endpoint_key": "axis_body",
            "start_mouse_xy": [float(x), float(y)],
            "start_axis_start_zyx": [float(value) for value in start],
            "start_axis_end_zyx": [float(value) for value in end],
            "start_anchor_zyx": [float(value) for value in anchor_point],
            "rotated_depth": float(anchor_depth),
            "context": context,
            "hit_xy": [float(closest[0]), float(closest[1])],
        }

    def start_local_axis_endpoint_drag(self, x, y):
        if not self._local_axis_overlay_enabled():
            return False
        hit = self._hit_local_axis_endpoint(x, y)
        if hit is None:
            hit = self._hit_local_axis_body(x, y)
        if hit is None or hit.get("rotated_depth") is None:
            return False
        self._local_axis_endpoint_drag = hit
        self._start_volume_interaction()
        if hit.get("endpoint_key") == "axis_body":
            self._set_local_axis_status(tt("Dragging output axis body.", self.lang))
        else:
            endpoint_text = tt("start", self.lang) if hit.get("endpoint_key") == "start_zyx" else tt("end", self.lang)
            self._set_local_axis_status(tt("Dragging output axis {0}.", self.lang).format(endpoint_text))
        return True

    def drag_local_axis_endpoint(self, x, y):
        drag = self._local_axis_endpoint_drag if isinstance(self._local_axis_endpoint_drag, dict) else None
        draft = self._current_local_axis_draft()
        if drag is None or draft is None:
            return False
        point = self._volume_xy_to_zyx_at_depth(x, y, drag.get("rotated_depth"), drag.get("context"))
        if point is None:
            return False
        editable = dict(draft.get("editable_axis") or {})
        endpoint_key = str(drag.get("endpoint_key") or "")
        if endpoint_key == "axis_body":
            start_anchor = np.asarray(drag.get("start_anchor_zyx") or [], dtype=np.float64)
            start_axis = np.asarray(drag.get("start_axis_start_zyx") or [], dtype=np.float64)
            end_axis = np.asarray(drag.get("start_axis_end_zyx") or [], dtype=np.float64)
            next_anchor = np.asarray(point, dtype=np.float64)
            if start_anchor.size != 3 or start_axis.size != 3 or end_axis.size != 3:
                return False
            delta = next_anchor - start_anchor
            shape = tuple(int(value) for value in getattr(self.image_volume, "shape", ()) or ())
            if len(shape) != 3:
                return False
            upper = np.asarray([max(0, shape[0] - 1), max(0, shape[1] - 1), max(0, shape[2] - 1)], dtype=np.float64)
            axis_min = np.minimum(start_axis, end_axis)
            axis_max = np.maximum(start_axis, end_axis)
            min_delta = -axis_min
            max_delta = upper - axis_max
            delta = np.minimum(np.maximum(delta, min_delta), max_delta)
            editable["start_zyx"] = [round(float(value), 3) for value in start_axis + delta]
            editable["end_zyx"] = [round(float(value), 3) for value in end_axis + delta]
        elif endpoint_key in {"start_zyx", "end_zyx"}:
            other_key = "end_zyx" if endpoint_key == "start_zyx" else "start_zyx"
            other = editable.get(other_key) or []
            if len(other) == 3 and float(np.linalg.norm(np.asarray(point, dtype=np.float64) - np.asarray(other, dtype=np.float64))) < 0.25:
                return False
            editable[endpoint_key] = [round(float(value), 3) for value in point]
        else:
            return False
        draft["editable_axis"] = editable
        draft["dirty"] = True
        self._refresh_local_axis_frame(draft)
        self.local_axis_draft = draft
        self._update_local_axis_summary()
        if hasattr(self.volume_canvas, "set_axis_overlays"):
            self.volume_canvas.set_axis_overlays(self._local_axis_volume_overlays())
        self._request_volume_interaction_render()
        return True

    def finish_local_axis_endpoint_drag(self):
        drag = self._local_axis_endpoint_drag if isinstance(self._local_axis_endpoint_drag, dict) else None
        self._local_axis_endpoint_drag = None
        if drag is None:
            return
        if drag.get("endpoint_key") == "axis_body":
            self._set_local_axis_status(tt("Moved output axis body.", self.lang))
        else:
            endpoint_text = tt("start", self.lang) if drag.get("endpoint_key") == "start_zyx" else tt("end", self.lang)
            self._set_local_axis_status(tt("Updated output axis {0}.", self.lang).format(endpoint_text))
        self._update_local_axis_summary()

    def _sync_local_axis_roll_buttons(self):
        return self.local_axis_controller.sync_roll_buttons()

    def _sync_local_axis_pick_buttons(self):
        return self.local_axis_controller.sync_pick_buttons()

    def set_local_axis_pick_target(self, target=""):
        return self.local_axis_controller.set_pick_target(target)

    def set_local_axis_roll_pick_target(self, target=""):
        return self.set_local_axis_pick_target(target)

    def pick_local_axis_roll_reference_at(self, x, y):
        return self.local_axis_controller.pick_roll_reference_at(x, y)

    def clear_local_axis_roll_references(self):
        return self.local_axis_controller.clear_roll_references()

    def align_local_axis_to_reference_plane(self):
        return self.local_axis_controller.align_to_reference_plane()

    def clear_local_axis_draft(self):
        return self.local_axis_controller.clear_draft()

    def _local_axis_volume_overlays(self):
        if not self._local_axis_overlay_enabled():
            return []
        shape = tuple(int(value) for value in getattr(self.image_volume, "shape", ()) or ())
        if len(shape) != 3:
            return []
        source_shape, spacing_zyx = self._volume_source_geometry()
        overlays = []
        saved_reslice = None

        def add_axis(start, end, label, color, width=2, label_anchor="end", label_offset=(8, -8), label_position="right", role="reference"):
            start_xy = self._project_zyx_to_volume_xy(start, shape, source_shape=source_shape, spacing_zyx=spacing_zyx)
            end_xy = self._project_zyx_to_volume_xy(end, shape, source_shape=source_shape, spacing_zyx=spacing_zyx)
            if start_xy and end_xy:
                anchor_xy = start_xy if str(label_anchor) == "start" else end_xy
                overlays.append(
                    {
                        "start_xy": start_xy,
                        "end_xy": end_xy,
                        "label": label,
                        "color": color,
                        "width": width,
                        "label_anchor_xy": anchor_xy,
                        "label_offset_xy": list(label_offset),
                        "label_position": label_position,
                        "role": role,
                    }
                )

        saved_reslice_source = {}
        saved_reslice_frame = {}
        if self.current_reslice_id:
            saved_reslice = self._current_part_reslice_record()
            if isinstance(saved_reslice, dict):
                has_exported_reslice_image = bool(str(saved_reslice.get("image_path") or "").strip())
                saved_reslice_source = saved_reslice.get("source") if has_exported_reslice_image and isinstance(saved_reslice.get("source"), dict) else {}
                saved_reslice_frame = saved_reslice.get("local_frame") if has_exported_reslice_image and isinstance(saved_reslice.get("local_frame"), dict) else {}
                if not saved_reslice_source:
                    return []

        source_z = saved_reslice_source.get("source_axis") if isinstance(saved_reslice_source.get("source_axis"), dict) else self._source_z_axis_for_current_part()
        source_z = self._local_axis_axis_for_current_reslice(source_z, saved_reslice=saved_reslice)
        add_axis(
            source_z.get("start_zyx"),
            source_z.get("end_zyx"),
            tt("source Z", self.lang),
            "#6AA6FF",
            width=2,
            label_anchor="start",
            label_offset=(-10, 18),
            label_position="left",
            role="locked_reference",
        )

        editable = {}
        draft = self._current_local_axis_draft()
        if isinstance(draft, dict):
            editable = draft.get("editable_axis") or {}
        elif saved_reslice_source:
            editable = (
                saved_reslice_source.get("final_editable_axis")
                or saved_reslice_source.get("editable_axis")
                or saved_reslice_source.get("initial_editable_axis")
                or {}
            )
        editable = self._local_axis_axis_for_current_reslice(editable, saved_reslice=saved_reslice)
        if editable.get("start_zyx") and editable.get("end_zyx"):
            add_axis(
                editable.get("start_zyx"),
                editable.get("end_zyx"),
                tt("output Z", self.lang),
                "#FFB84D",
                width=3,
                label_anchor="end",
                label_offset=(10, -14),
                label_position="right",
                role="editable_output",
            )
        roll = (draft or {}).get("roll_reference") if isinstance(draft, dict) else {}
        if not roll and isinstance(saved_reslice_frame, dict):
            roll = saved_reslice_frame.get("roll_reference") if isinstance(saved_reslice_frame.get("roll_reference"), dict) else {}
        roll = self._local_axis_roll_for_current_reslice(roll, saved_reslice=saved_reslice)
        point_a = roll.get("point_a") if isinstance(roll, dict) and isinstance(roll.get("point_a"), dict) else {}
        point_b = roll.get("point_b") if isinstance(roll, dict) and isinstance(roll.get("point_b"), dict) else {}
        point_c = roll.get("point_c") if isinstance(roll, dict) and isinstance(roll.get("point_c"), dict) else {}
        roll_a_xy = self._project_zyx_to_volume_xy(point_a.get("zyx"), shape, source_shape=source_shape, spacing_zyx=spacing_zyx) if point_a.get("zyx") else None
        roll_b_xy = self._project_zyx_to_volume_xy(point_b.get("zyx"), shape, source_shape=source_shape, spacing_zyx=spacing_zyx) if point_b.get("zyx") else None
        roll_c_xy = self._project_zyx_to_volume_xy(point_c.get("zyx"), shape, source_shape=source_shape, spacing_zyx=spacing_zyx) if point_c.get("zyx") else None
        if roll_a_xy and roll_b_xy:
            overlays.append(
                {
                    "start_xy": roll_a_xy,
                    "end_xy": roll_b_xy,
                    "label": tt("Roll reference", self.lang),
                    "color": "#7CE3A1",
                    "width": 2,
                    "label_anchor_xy": roll_b_xy,
                    "label_offset_xy": [10, 16],
                    "label_position": "right",
                }
            )
        if roll_a_xy and roll_b_xy and roll_c_xy:
            overlays.append(
                {
                    "kind": "polyline",
                    "points_xy": [roll_a_xy, roll_b_xy, roll_c_xy, roll_a_xy],
                    "label": tt("A/B/C reference plane", self.lang),
                    "color": "#D6C56D",
                    "width": 2,
                    "label_anchor_xy": roll_c_xy,
                    "label_offset_xy": [10, 18],
                    "label_position": "right",
                }
            )
        for point, fallback_label, color, offset in (
            (point_a, "Roll reference A", "#7CE3A1", (-18, -12)),
            (point_b, "Roll reference B", "#66D9EF", (10, -12)),
            (point_c, "Plane reference C", "#D6C56D", (10, 16)),
        ):
            xy = self._project_zyx_to_volume_xy(point.get("zyx"), shape, source_shape=source_shape, spacing_zyx=spacing_zyx) if point.get("zyx") else None
            if xy:
                overlays.append(
                    {
                        "kind": "point",
                        "point_xy": xy,
                        "label": tt(fallback_label, self.lang),
                        "color": color,
                        "radius": 5,
                        "label_offset_xy": list(offset),
                        "label_position": "right",
                    }
                )
        return overlays

    def volume_canvas_overlay_text(self):
        if self.image_volume is None:
            return ""
        stats_text = self._volume_stats_text()
        parts = [
            tt("Volume view", self.lang),
            self._volume_renderer_label(),
            self._volume_mode_label(),
            f"{tt('Mode', self.lang)} {self._volume_projection_label()}",
            f"{tt('Transfer function', self.lang)} {self._volume_transfer_label()}",
            f"{tt('Shader quality', self.lang)} {self._volume_shader_quality_label_text()}",
            f"{tt('Mask display', self.lang)} {self._volume_mask_label_text()}",
            f"{tt('Detail enhancement', self.lang)} {int(self.volume_enhancement_slider.value())}%",
            f"{tt('Texture', self.lang)} {self._active_volume_target_dim()}",
            f"{tt('Samples', self.lang)} {self._active_volume_sample_count()}",
            f"{tt('ROI', self.lang)} {self._active_volume_roi_scale():.1f}x",
            f"{tt('ROI budget', self.lang)} {self._roi_texture_budget_bytes() / (1024.0 ** 3):.1f} GB",
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

    def _volume_mode_label(self):
        if self._volume_render_mode != "drag" and self._volume_clarity_mode:
            return tt("Local detail check", self.lang)
        return tt("Drag preview", self.lang) if self._volume_render_mode == "drag" else tt("Still high quality", self.lang)

    def _volume_projection_mode(self):
        if hasattr(self, "volume_projection_combo"):
            mode = self.volume_projection_combo.currentData()
            if mode in {"composite", "mip", "minip", "average", "surface"}:
                return mode
        return "composite"

    def _volume_projection_label(self):
        labels = {
            "composite": "Composite",
            "mip": "MIP",
            "minip": "MinIP",
            "average": "Average",
            "surface": "Surface",
        }
        return tt(labels.get(self._volume_projection_mode(), "Composite"), self.lang)

    def _volume_mask_mode(self):
        if hasattr(self, "volume_mask_combo"):
            mode = self.volume_mask_combo.currentData()
            if mode in {"image_only", "mask_boundary", "masked_image"}:
                return mode
        return "image_only"

    def _volume_mask_label_text(self):
        labels = {
            "image_only": "Image only",
            "mask_boundary": "Mask boundary",
            "masked_image": "Masked image",
        }
        return tt(labels.get(self._volume_mask_mode(), "Image only"), self.lang)

    def _volume_transfer_label(self):
        labels = {
            "amber": "Amber",
            "cyan": "Cyan",
            "white": "White",
            "morphology": "Morphology Inspect",
            "publication": "Publication Inspect",
            "custom": "Custom",
        }
        return tt(labels.get(self._volume_transfer_preset(), "Amber"), self.lang)

    def _volume_transfer_opacity(self, mode=None):
        value = 100
        if hasattr(self, "volume_transfer_opacity_slider"):
            value = int(self.volume_transfer_opacity_slider.value())
        render_mode = "drag" if mode == "drag" else self._volume_render_mode
        if render_mode == "drag" and self._volume_projection_mode() == "composite":
            return max(0.05, min(1.0, 0.55 * (float(value) / 100.0)))
        base = 0.72 if self._volume_clarity_mode and render_mode == "still" else (1.0 if render_mode == "still" else 0.82)
        return max(0.05, min(1.4, base * (float(value) / 100.0)))

    def _volume_detail_enhancement(self, mode=None):
        if mode == "drag":
            return 0.0
        value = int(self.volume_enhancement_slider.value()) if hasattr(self, "volume_enhancement_slider") else 0
        return max(0.0, min(1.0, float(value) / 100.0))

    def _volume_tone_gamma(self):
        value = int(self.volume_tone_slider.value()) if hasattr(self, "volume_tone_slider") else 100
        return max(0.65, min(1.35, float(value) / 100.0))

    def _volume_clip_plane_normal(self):
        try:
            yaw = math.radians(float(self._volume_yaw))
            pitch = math.radians(float(self._volume_pitch))
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
        if self._volume_canvas_renderer != "gpu" or self._volume_render_mode != "still":
            return 1.0
        if not getattr(self, "volume_roi_detail_check", None) or not self.volume_roi_detail_check.isChecked():
            return 1.0
        if float(self._volume_zoom) <= 1.01:
            return 1.0
        return max(1.0, min(3.0, float(self.volume_roi_scale_slider.value()) / 100.0))

    def _volume_roi_inspect_enabled(self):
        return bool(getattr(self, "volume_roi_inspect_check", None) and self.volume_roi_inspect_check.isChecked())

    def _volume_roi_source_mode(self):
        if not getattr(self, "volume_roi_source_combo", None):
            return "full"
        mode = str(self.volume_roi_source_combo.currentData() or "full")
        if mode in {"full", "current_bbox"} or mode.startswith("roi:") or mode.startswith("part:"):
            return mode
        return "full"

    def _active_part_preview_bbox(self):
        if (
            self.current_volume_scope == "full"
            and self.part_preview_mask is not None
            and self.part_mask_preview_bbox
            and self.image_volume is not None
        ):
            try:
                bbox = normalize_roi_bbox_zyx(self.part_mask_preview_bbox, self.image_volume.shape)
                if tuple(getattr(self.part_preview_mask, "shape", ()) or ()) == roi_shape_zyx(bbox):
                    return bbox
            except Exception:
                return None
        return None

    def _selected_volume_roi_source_bbox(self):
        mode = self._volume_roi_source_mode()
        if mode == "current_bbox":
            if not hasattr(self, "part_bbox_edit") or not self.part_bbox_edit.text().strip():
                return None
            return self._parse_part_bbox_text()
        if mode.startswith("roi:"):
            roi = self.project.get_part_roi(self.current_specimen_id, mode.split(":", 1)[1], default=None) if self.current_specimen_id else None
            if roi is None or (roi or {}).get("status") == "cancelled":
                return None
            return roi.get("bbox_zyx", [])
        if mode.startswith("part:"):
            part = self.project.get_part(self.current_specimen_id, mode.split(":", 1)[1], default=None) if self.current_specimen_id else None
            if part is None:
                return None
            return part.get("parent_bbox_zyx", [])
        return None

    def _active_volume_sample_count(self):
        samples = int(self.volume_sample_slider.value())
        if self._volume_render_mode == "drag" and self._volume_canvas_renderer == "gpu":
            if self._volume_projection_mode() == "composite":
                return max(192, min(samples, 384))
            return max(256, min(samples, 768))
        roi_scale = self._active_volume_roi_scale()
        if roi_scale > 1.0 and self._volume_canvas_renderer == "gpu":
            return max(256, min(GPU_VOLUME_MAX_RAY_STEPS, int(round(samples * min(1.5, roi_scale)))))
        return samples

    def _volume_stats_text(self):
        stats = dict(getattr(self, "_volume_last_stats", {}) or {})
        if not stats:
            return tt("GPU stats pending", self.lang) if self._volume_canvas_renderer == "gpu" else ""
        shape = tuple(stats.get("shape_zyx") or ())
        parts = []
        if len(shape) == 3 and all(int(value) > 0 for value in shape):
            parts.append(f"{tt('actual', self.lang)} {int(shape[2])}x{int(shape[1])}x{int(shape[0])}")
        dtype = str(stats.get("dtype") or "")
        if dtype:
            parts.append(f"{tt('Data', self.lang)} {dtype}")
        texture_filter = str(stats.get("texture_filter") or "")
        display_scaling = str(stats.get("display_scaling") or "")
        if texture_filter:
            sampling_text = tt(texture_filter, self.lang)
            if display_scaling and display_scaling != texture_filter:
                sampling_text = f"{sampling_text}/{tt(display_scaling, self.lang)}"
            parts.append(f"{tt('Sampling', self.lang)} {sampling_text}")
        projection = str(stats.get("projection_mode") or "")
        if projection:
            parts.append(f"{tt('Mode', self.lang)} {self._volume_projection_label()}")
        transfer = str(stats.get("transfer_preset") or "")
        if transfer:
            parts.append(f"{tt('Transfer function', self.lang)} {tt(transfer.capitalize(), self.lang)}")
        transfer_opacity = stats.get("transfer_opacity")
        if transfer_opacity is not None:
            try:
                parts.append(f"{tt('Density opacity', self.lang)} {int(round(float(transfer_opacity) * 100))}%")
            except (TypeError, ValueError):
                pass
        mask_mode = str(stats.get("mask_mode") or "")
        if mask_mode and mask_mode != "image_only":
            parts.append(f"{tt('Mask display', self.lang)} {self._volume_mask_label_text()}")
        enhancement = stats.get("enhancement")
        if enhancement is not None:
            try:
                value = int(round(float(enhancement) * 100))
                if value > 0:
                    parts.append(f"{tt('Detail enhancement', self.lang)} {value}%")
            except (TypeError, ValueError):
                pass
        if stats.get("clip_plane_enabled"):
            try:
                parts.append(f"{tt('Clip plane', self.lang)} {int(round(float(stats.get('clip_plane_depth') or 0.0) * 100))}%")
            except (TypeError, ValueError):
                parts.append(tt("Clip plane", self.lang))
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
        if float(getattr(self, "_volume_last_preview_build_ms", 0.0) or 0.0) > 0.0:
            parts.append(f"Load {float(self._volume_last_preview_build_ms):.0f} ms")
        supersample = float(stats.get("supersample_scale") or 1.0)
        if supersample > 1.01:
            parts.append(f"{tt('ROI', self.lang)} {supersample:.1f}x")
            parts.append(f"{tt('ROI budget', self.lang)} {self._roi_texture_budget_bytes() / (1024.0 ** 3):.1f} GB")
        roi_shape = tuple(int(value) for value in getattr(self, "_volume_roi_preview_source_shape", ()) or ())
        if len(roi_shape) == 3 and all(value > 0 for value in roi_shape):
            parts.append(f"{tt('ROI crop source', self.lang)} {int(roi_shape[2])}x{int(roi_shape[1])}x{int(roi_shape[0])}")
        byte_count = int(stats.get("bytes") or 0)
        if byte_count > 0:
            parts.append(f"{tt('VRAM', self.lang)} {byte_count / (1024.0 ** 3):.2f} GB")
        upload_ms = float(stats.get("upload_ms") or 0.0)
        draw_ms = float(stats.get("draw_ms") or 0.0)
        if upload_ms > 0:
            parts.append(f"{tt('Upload', self.lang)} {upload_ms:.0f} ms")
        if draw_ms > 0:
            parts.append(f"{tt('Draw', self.lang)} {draw_ms:.1f} ms")
        diagnosis = self._volume_performance_diagnosis(stats)
        if diagnosis:
            parts.append(diagnosis)
        return " | ".join(parts)

    def _volume_status_summary_text(self):
        resource_summary = self._preview_resource_summary()
        if resource_summary.get("resource_limited"):
            return str(resource_summary.get("user_message") or tt("No TIF volume loaded", self.lang))
        if self.image_volume is None:
            return tt("No TIF volume loaded", self.lang)
        parts = [
            tt("Volume view", self.lang),
            tt("GPU ray march", self.lang) if self._volume_canvas_renderer == "gpu" else tt("CPU fallback", self.lang),
            self._volume_mode_label(),
            f"{tt('Mode', self.lang)} {self._volume_projection_label()}",
            f"{tt('Texture', self.lang)} {self._active_volume_target_dim()}",
            f"{tt('Samples', self.lang)} {self._active_volume_sample_count()}",
        ]
        roi_scale = self._active_volume_roi_scale()
        if roi_scale > 1.01:
            parts.append(f"{tt('ROI', self.lang)} {roi_scale:.1f}x")
        cache_bytes = self._volume_cache_estimated_bytes()
        if cache_bytes > 0:
            parts.append(f"Cache {self._volume_cache_owner_count()}/{self._volume_cache_owner_limit()}")
        stats = dict(getattr(self, "_volume_last_stats", {}) or {})
        texture_cache_entries = int(stats.get("texture_cache_entries") or 0)
        if texture_cache_entries > 0:
            texture_cache_bytes = int(stats.get("texture_cache_bytes") or 0)
            parts.append(f"GPU {texture_cache_entries} {texture_cache_bytes / (1024.0 ** 2):.0f} MB")
        degradation = self._volume_gpu_stream_degradation_text(stats, compact=True)
        if degradation:
            parts.append(degradation)
        load_ms = float(getattr(self, "_volume_last_preview_build_ms", 0.0) or 0.0)
        if load_ms > 0.0:
            parts.append(f"Load {load_ms:.0f} ms")
        diagnosis = self._volume_performance_diagnosis(stats)
        if diagnosis:
            parts.append(diagnosis)
        return " | ".join(parts)

    def _volume_performance_diagnosis(self, stats=None):
        stats = dict(stats or getattr(self, "_volume_last_stats", {}) or {})
        if self._volume_canvas_renderer != "gpu":
            if self._volume_renderer_warning:
                return tt("GPU fallback active", self.lang)
            return ""
        byte_count = int(stats.get("bytes") or 0)
        upload_ms = float(stats.get("upload_ms") or 0.0)
        draw_ms = float(stats.get("draw_ms") or 0.0)
        if upload_ms >= 1200.0:
            return tt("bottleneck: texture upload", self.lang)
        if draw_ms >= 90.0:
            return tt("bottleneck: ray rendering", self.lang)
        if byte_count >= int(1.5 * 1024 * 1024 * 1024):
            return tt("large GPU texture", self.lang)
        return ""

    def _volume_gpu_stream_degradation_text(self, stats=None, compact=False):
        stats = dict(stats or getattr(self, "_volume_last_stats", {}) or {})
        stream = dict(stats.get("gpu_stream_build") or {})
        if not stream.get("degraded"):
            return ""
        actual = int(stream.get("actual_max_dim") or 0)
        requested = int(stream.get("requested_max_dim") or 0)
        if actual > 0 and requested > actual:
            if compact:
                return f"{tt('GPU budget', self.lang)} {actual}/{requested}"
            return f"{tt('GPU budget auto-scaled preview', self.lang)} {actual}/{requested}"
        if compact:
            return tt("GPU budget auto-scaled", self.lang)
        return tt("GPU budget auto-scaled preview", self.lang)

    def volume_performance_report(self):
        stats = dict(getattr(self, "_volume_last_stats", {}) or {})
        source_shape, spacing_zyx = self._volume_source_geometry()
        report = {
            "renderer": self._volume_canvas_renderer,
            "renderer_label": self._volume_renderer_label(),
            "source_shape_zyx": tuple(int(value) for value in source_shape) if len(source_shape) == 3 else (),
            "spacing_zyx": tuple(float(value) for value in spacing_zyx) if len(spacing_zyx) == 3 else (),
            "preview_shape_zyx": tuple(int(value) for value in stats.get("shape_zyx") or ()),
            "dtype": str(stats.get("dtype") or ""),
            "uploaded_bytes": int(stats.get("bytes") or 0),
            "upload_ms": float(stats.get("upload_ms") or 0.0),
            "draw_ms": float(stats.get("draw_ms") or 0.0),
            "samples": int(stats.get("steps") or self._active_volume_sample_count()),
            "render_mode": self._volume_render_mode,
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
            "load_ms": float(getattr(self, "_volume_last_preview_build_ms", 0.0) or 0.0),
            "roi_source_mode": self._volume_roi_source_mode(),
            "roi_inspect_enabled": bool(self._volume_roi_inspect_enabled()),
            "roi_inspect_active": bool(getattr(self, "_volume_roi_preview_bbox", None)),
            "roi_bbox_zyx": getattr(self, "_volume_roi_preview_bbox", None),
            "roi_source_shape_zyx": tuple(int(value) for value in getattr(self, "_volume_roi_preview_source_shape", ()) or ()),
            "shader_quality_mode": self._volume_shader_quality_mode(),
            "clip_plane_enabled": bool(self.volume_clip_plane_check.isChecked()),
            "diagnosis": self._volume_performance_diagnosis(stats),
        }
        if report["uploaded_bytes"] > 0:
            report["uploaded_gb"] = report["uploaded_bytes"] / (1024.0 ** 3)
        else:
            report["uploaded_gb"] = 0.0
        return report

    def _update_volume_render_status_label(self, text=None):
        if not hasattr(self, "volume_render_status_label"):
            return
        full_text = self.volume_canvas_overlay_text() if self.image_volume is not None else ""
        if text is None:
            text = self._volume_status_summary_text()
            tooltip = full_text or str(text or "")
        else:
            text = str(text or "")
            tooltip = text
            if full_text and full_text != text:
                tooltip = f"{text}\n\n{full_text}"
        self.volume_render_status_label.setText(str(text or ""))
        self.volume_render_status_label.setToolTip(tooltip)

    def _volume_canvas_has_visible_content(self):
        canvas = getattr(self, "volume_canvas", None)
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
        canvas = getattr(self, "volume_canvas", None)
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
        return int(getattr(self, "_volume_preview_ui_wait_depth", 0) or 0) > 0

    def eventFilter(self, watched, event):
        if self._volume_preview_ui_waiting() and isinstance(watched, QWidget) and (watched is self or self.isAncestorOf(watched)):
            if event.type() in {
                QEvent.MouseButtonPress,
                QEvent.MouseButtonRelease,
                QEvent.MouseButtonDblClick,
                QEvent.KeyPress,
                QEvent.KeyRelease,
            }:
                return True
        return super().eventFilter(watched, event)

    def _begin_volume_preview_ui_wait(self):
        depth = int(getattr(self, "_volume_preview_ui_wait_depth", 0) or 0)
        self._volume_preview_ui_wait_depth = depth + 1
        if depth == 0:
            try:
                QApplication.instance().installEventFilter(self)
            except Exception:
                pass
        canvas = getattr(self, "volume_canvas", None)
        if hasattr(canvas, "set_stream_build_yield_callback"):
            try:
                canvas.set_stream_build_yield_callback(self._yield_volume_preview_ui_events)
            except Exception:
                pass

    def _end_volume_preview_ui_wait(self):
        depth = max(0, int(getattr(self, "_volume_preview_ui_wait_depth", 0) or 0) - 1)
        self._volume_preview_ui_wait_depth = depth
        if depth == 0:
            canvas = getattr(self, "volume_canvas", None)
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
        QApplication.processEvents()

    def _volume_renderer_label(self):
        renderer = tt("GPU ray march", self.lang) if self._volume_canvas_renderer == "gpu" else tt("CPU fallback", self.lang)
        gpu_label = ""
        if self._volume_canvas_renderer == "gpu":
            if hasattr(self.volume_canvas, "renderer_label"):
                gpu_label = self.volume_canvas.renderer_label()
            if not gpu_label:
                gpu_label = self._compact_gpu_renderer_info(self._volume_gl_renderer_info)
        if gpu_label:
            renderer = f"{renderer} [{gpu_label}]"
        return renderer

    def _compact_gpu_renderer_info(self, info):
        text = " ".join(str(info or "").split())
        if "RTX 3090" in text:
            return "RTX 3090"
        if "NVIDIA GeForce" in text:
            return text.replace("NVIDIA GeForce ", "NVIDIA ").split("|")[0].strip()
        return text.split("|")[0].strip()[:42]

    def _volume_renderer_status_message(self):
        if self._volume_canvas_renderer == "gpu":
            return tt("3D preview uses a downsampled read-only volume. Use Slice review for precise label editing.", self.lang)
        if self._volume_renderer_warning:
            return (
                tt("3D preview uses a downsampled read-only volume. Use Slice review for precise label editing.", self.lang)
                + "\n"
                + tt("GPU renderer unavailable. Using CPU fallback.", self.lang)
            )
        return tt("3D preview uses a downsampled read-only volume. Use Slice review for precise label editing.", self.lang)

    def _on_gpu_volume_info_changed(self, details):
        info = str(details or "")
        if info == self._volume_gl_renderer_info:
            return
        self._volume_gl_renderer_info = info
        if self._volume_gl_renderer_info:
            self.log(f"GPU volume OpenGL renderer: {self._volume_gl_renderer_info}")
        self._update_volume_render_status_label()
        if self.display_mode == "volume":
            self.render_volume_preview()

    def _on_gpu_volume_failed(self, reason):
        if self._volume_canvas_renderer != "gpu":
            return
        if getattr(self, "_handling_gpu_volume_failure", False):
            return
        self._handling_gpu_volume_failure = True
        warning = str(reason or "unknown")
        try:
            self._switch_volume_canvas_to_cpu(warning)
            message = tt("GPU renderer failed. Using CPU fallback: {0}", self.lang).format(warning)
            self.training_status_label.setText(message)
            self._update_volume_render_status_label(
                f"{tt('Volume view', self.lang)} | {tt('CPU fallback', self.lang)} | {tt('GPU failed', self.lang)}: {warning}"
            )
            self.log(message)
        finally:
            self._handling_gpu_volume_failure = False
        self.schedule_volume_preview_render()

    def _switch_volume_canvas_to_cpu(self, warning=""):
        old_canvas = getattr(self, "volume_canvas", None)
        if old_canvas is not None and not hasattr(old_canvas, "set_volume_pixmap"):
            if hasattr(old_canvas, "release_gl_resources"):
                try:
                    old_canvas.release_gl_resources()
                except Exception:
                    pass
            self.volume_canvas = TifVolumeCanvas()
            self.volume_canvas.workbench = self
            self.volume_canvas.set_theme(self.current_theme)
            renderer_property = "cpu-mask-fallback" if str(warning or "").startswith("Mask inspection") else "cpu"
            self.volume_canvas.setProperty("tifVolumeRenderer", renderer_property)
            if hasattr(self, "view_stack"):
                self.view_stack.addWidget(self.volume_canvas)
                index = self.view_stack.indexOf(old_canvas)
                if self.display_mode == "volume":
                    self.view_stack.setCurrentWidget(self.volume_canvas)
                if index >= 0:
                    self.view_stack.removeWidget(old_canvas)
            old_canvas.hide()
            old_canvas.setParent(None)
            old_canvas.deleteLater()
        self._volume_canvas_renderer = "cpu"
        if warning and not str(warning).startswith("Mask inspection"):
            self._volume_renderer_warning = str(warning)
        self._volume_last_stats = {}

    def _try_restore_gpu_volume_canvas(self):
        if self._volume_canvas_renderer == "gpu" or self._volume_renderer_warning:
            return False
        if not getattr(self, "_volume_canvas_created", False):
            return False
        if str(getattr(self.volume_canvas, "property", lambda _key: "")("tifVolumeRenderer") or "") != "cpu-mask-fallback":
            return False
        self._ensure_volume_canvas(force_gpu=True)
        return self._volume_canvas_renderer == "gpu"

    def _on_gpu_volume_stats_changed(self):
        if hasattr(self.volume_canvas, "render_stats"):
            self._volume_last_stats = dict(self.volume_canvas.render_stats() or {})
        self._update_volume_render_status_label()

    def _start_volume_interaction(self):
        if self._volume_render_mode != "drag":
            self._volume_render_mode = "drag"
        if hasattr(self, "volume_still_timer"):
            self.volume_still_timer.start()

    def finish_volume_interaction_debounced(self):
        if hasattr(self, "volume_still_timer"):
            self.volume_still_timer.start()

    def _finish_volume_interaction(self):
        self._volume_interaction_render_pending = False
        if self._volume_render_mode != "still":
            self._volume_render_mode = "still"
            self.render_volume_preview()

    def _on_volume_clarity_toggled(self, checked):
        self._volume_clarity_mode = bool(checked)
        self._reset_active_volume_preview_state()
        self.render_volume_preview()

    def _on_volume_quality_drag_started(self):
        self._volume_quality_drag_pending = True
        try:
            self._volume_quality_committed_value = int(self.volume_quality_slider.value())
        except Exception:
            self._volume_quality_committed_value = None
        self._show_volume_quality_release_status()

    def _on_volume_quality_drag_moved(self, *_args):
        self._volume_quality_drag_pending = True
        self._show_volume_quality_release_status()

    def _show_volume_quality_release_status(self):
        if self.display_mode != "volume":
            return
        message = tt("Release Render quality to rebuild the 3D preview.", self.lang)
        self._set_volume_canvas_status_text(message)
        self._update_volume_render_status_label(message)

    def _on_volume_quality_changed(self, *_args):
        if getattr(self, "_volume_quality_drag_pending", False):
            self._show_volume_quality_release_status()
        elif self.display_mode == "volume":
            self._update_volume_render_status_label()

    def _on_volume_quality_released(self):
        self._commit_volume_quality_change()

    def _commit_volume_quality_change(self):
        try:
            value = int(self.volume_quality_slider.value())
        except Exception:
            value = None
        if value == getattr(self, "_volume_quality_committed_value", None):
            self._volume_quality_drag_pending = False
            return
        self._volume_quality_committed_value = value
        self._volume_quality_drag_pending = False
        self._prune_volume_preview_cache()
        self._refresh_volume_preview()

    def _on_volume_roi_scale_drag_started(self):
        try:
            self._volume_roi_scale_committed_value = int(self.volume_roi_scale_slider.value())
        except Exception:
            self._volume_roi_scale_committed_value = None

    def _on_volume_roi_scale_changed(self, *_args):
        if callable(getattr(self.volume_roi_scale_slider, "isSliderDown", None)) and self.volume_roi_scale_slider.isSliderDown():
            if self.display_mode == "volume":
                self._update_volume_render_status_label(tt("Release ROI scale to update the 3D preview.", self.lang))
            return
        self._commit_volume_roi_scale_change()

    def _on_volume_roi_scale_released(self):
        self._commit_volume_roi_scale_change()

    def _commit_volume_roi_scale_change(self):
        try:
            value = int(self.volume_roi_scale_slider.value())
        except Exception:
            value = None
        if value == getattr(self, "_volume_roi_scale_committed_value", None):
            return
        self._volume_roi_scale_committed_value = value
        self.render_volume_preview()

    def _on_volume_display_enhancement_changed(self, *_args):
        self.render_volume_preview()

    def _on_volume_clip_plane_changed(self, *_args):
        self.render_volume_preview()

    def _on_volume_projection_changed(self):
        self.render_volume_preview()

    def _volume_tint_rgb(self):
        settings = self._active_volume_view_settings()
        mode = self.volume_tint_combo.currentData() if hasattr(self, "volume_tint_combo") else settings.get("volume_tint", "amber")
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
        settings = self._active_volume_view_settings()
        mode = self.volume_tint_combo.currentData() if hasattr(self, "volume_tint_combo") else settings.get("volume_tint", "amber")
        mode = str(mode or "amber").lower()
        return mode if mode in {"amber", "cyan", "white", "custom", "morphology", "publication"} else "amber"

    def _volume_transfer_lut(self):
        return build_volume_transfer_lut(
            self._volume_transfer_preset(),
            tuple(float(value) for value in self._volume_tint_rgb()),
            cutoff=0.0,
            opacity=self._volume_transfer_opacity(),
            clarity=self._volume_clarity_mode and self._volume_render_mode == "still",
        )

    def _volume_shader_quality_mode(self):
        if hasattr(self, "volume_shader_quality_combo"):
            mode = self.volume_shader_quality_combo.currentData()
        else:
            mode = self._active_volume_view_settings().get("volume_shader_quality", "preset")
        mode = str(mode or "preset").lower()
        return mode if mode in {"off", "preset", "all_still"} else "preset"

    def _volume_shader_quality_label_text(self):
        labels = {
            "off": "Off",
            "preset": "Inspect presets",
            "all_still": "All still composite",
        }
        return tt(labels.get(self._volume_shader_quality_mode(), "Inspect presets"), self.lang)

    def _volume_shader_quality_settings(self, mode=None):
        mode = "drag" if mode == "drag" else "still"
        clip_plane_enabled = bool(hasattr(self, "volume_clip_plane_check") and self.volume_clip_plane_check.isChecked())
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
        settings = self._volume_shader_quality_settings(mode)
        return float(settings["gradient_opacity"]), tuple(settings["gradient_opacity_range"])

    def _volume_jitter_strength(self, mode=None):
        settings = self._volume_shader_quality_settings(mode)
        return float(settings["jitter_strength"])

    def _volume_adaptive_step_strength(self, mode=None):
        settings = self._volume_shader_quality_settings(mode)
        return float(settings["adaptive_step_strength"])

    def _on_volume_tint_changed(self):
        settings = self._active_volume_view_settings()
        settings["volume_tint"] = self.volume_tint_combo.currentData() or "amber"
        self._save_active_volume_view_settings()
        self.render_volume_preview()

    def _on_volume_transfer_opacity_changed(self):
        if callable(getattr(self.volume_transfer_opacity_slider, "isSliderDown", None)) and self.volume_transfer_opacity_slider.isSliderDown():
            self._volume_transfer_opacity_drag_pending = True
            self.render_volume_preview()
            return
        self._volume_transfer_opacity_drag_pending = False
        self._save_volume_transfer_opacity_setting()
        self.render_volume_preview()

    def _on_volume_transfer_opacity_released(self):
        if not getattr(self, "_volume_transfer_opacity_drag_pending", False):
            return
        self._volume_transfer_opacity_drag_pending = False
        self._save_volume_transfer_opacity_setting()

    def _save_volume_transfer_opacity_setting(self):
        settings = self._active_volume_view_settings()
        settings["volume_transfer_opacity"] = int(self.volume_transfer_opacity_slider.value())
        self._save_active_volume_view_settings()

    def _on_volume_shader_quality_changed(self):
        settings = self._active_volume_view_settings()
        settings["volume_shader_quality"] = self._volume_shader_quality_mode()
        self._save_active_volume_view_settings()
        self.render_volume_preview()

    def _on_volume_mask_changed(self):
        settings = self._active_volume_view_settings()
        settings["volume_mask_mode"] = self._volume_mask_mode()
        self._save_active_volume_view_settings()
        self._clear_volume_mask_caches(owner=self._active_volume_cache_owner())
        self.render_volume_preview()

    def choose_volume_custom_color(self):
        settings = self._active_volume_view_settings()
        color = QColorDialog.getColor(QColor(str(settings.get("volume_tint_custom", "#FFD34D"))), self, tt("Choose color", self.lang))
        if not color.isValid():
            return
        settings["volume_tint"] = "custom"
        settings["volume_tint_custom"] = color.name()
        index = self.volume_tint_combo.findData("custom")
        if index >= 0:
            self.volume_tint_combo.setCurrentIndex(index)
        self._save_active_volume_view_settings()
        self.render_volume_preview()

    def apply_morphology_inspect_preset(self):
        controls = [
            self.volume_projection_combo,
            self.volume_tint_combo,
            self.volume_shader_quality_combo,
            self.volume_cutoff_slider,
            self.volume_transfer_opacity_slider,
            self.volume_enhancement_slider,
            self.volume_tone_slider,
            self.volume_surface_refine_check,
        ]
        for control in controls:
            control.blockSignals(True)
        try:
            projection_index = self.volume_projection_combo.findData("composite")
            if projection_index >= 0:
                self.volume_projection_combo.setCurrentIndex(projection_index)
            transfer_index = self.volume_tint_combo.findData("morphology")
            if transfer_index >= 0:
                self.volume_tint_combo.setCurrentIndex(transfer_index)
            quality_index = self.volume_shader_quality_combo.findData("preset")
            if quality_index >= 0:
                self.volume_shader_quality_combo.setCurrentIndex(quality_index)
            self.volume_cutoff_slider.setValue(18)
            self.volume_transfer_opacity_slider.setValue(92)
            self.volume_enhancement_slider.setValue(72)
            self.volume_tone_slider.setValue(92)
            self.volume_surface_refine_check.setChecked(True)
        finally:
            for control in controls:
                control.blockSignals(False)

        settings = self._active_volume_view_settings()
        settings["volume_tint"] = "morphology"
        settings["volume_shader_quality"] = "preset"
        settings["volume_transfer_opacity"] = int(self.volume_transfer_opacity_slider.value())
        self._save_active_volume_view_settings()
        self.render_volume_preview()

    def rotate_volume_preview(self, dx, dy):
        self._start_volume_interaction()
        self._volume_yaw = (self._volume_yaw + float(dx) * 0.6) % 360.0
        self._volume_pitch = max(-85.0, min(85.0, self._volume_pitch - float(dy) * 0.45))
        self._request_volume_interaction_render()

    def pan_volume_preview(self, dx, dy):
        self._start_volume_interaction()
        width = max(1.0, float(self.volume_canvas.width()) if hasattr(self, "volume_canvas") else 1.0)
        height = max(1.0, float(self.volume_canvas.height()) if hasattr(self, "volume_canvas") else 1.0)
        pan_speed = 2.8
        self._volume_pan_x += (float(dx) / width) * pan_speed
        self._volume_pan_y -= (float(dy) / height) * pan_speed
        self._clamp_volume_pan()
        self._request_volume_interaction_render()

    def zoom_volume_preview(self, direction):
        self._start_volume_interaction()
        factor = 1.18 if int(direction) > 0 else 1.0 / 1.18
        self._volume_zoom = max(0.35, min(16.0, self._volume_zoom * factor))
        self._clamp_volume_pan()
        self._request_volume_interaction_render()

    def _volume_pan_limit(self):
        return volume_pan_limit_for_zoom(getattr(self, "_volume_zoom", 1.0))

    def _clamp_volume_pan(self):
        limit = self._volume_pan_limit()
        self._volume_pan_x = max(-limit, min(limit, float(self._volume_pan_x)))
        self._volume_pan_y = max(-limit, min(limit, float(self._volume_pan_y)))

    def reset_volume_view(self):
        if hasattr(self, "volume_still_timer"):
            self.volume_still_timer.stop()
        self._volume_render_mode = "still"
        self._volume_yaw = -35.0
        self._volume_pitch = 20.0
        self._volume_zoom = 1.0
        self._volume_pan_x = 0.0
        self._volume_pan_y = 0.0
        if hasattr(self, "volume_inside_slider"):
            self.volume_inside_slider.blockSignals(True)
            self.volume_inside_slider.setValue(0)
            self.volume_inside_slider.blockSignals(False)
        if hasattr(self, "volume_clip_slider"):
            self.volume_clip_slider.blockSignals(True)
            self.volume_clip_slider.setValue(0)
            self.volume_clip_slider.blockSignals(False)
        if hasattr(self, "volume_clip_plane_check"):
            self.volume_clip_plane_check.blockSignals(True)
            self.volume_clip_plane_check.setChecked(False)
            self.volume_clip_plane_check.blockSignals(False)
        if hasattr(self, "volume_clip_plane_depth_slider"):
            self.volume_clip_plane_depth_slider.blockSignals(True)
            self.volume_clip_plane_depth_slider.setValue(0)
            self.volume_clip_plane_depth_slider.blockSignals(False)
        self.render_volume_preview()

    def _refresh_volume_preview(self):
        self._cancel_volume_preview_build()
        self._reset_active_volume_preview_state()
        if self.display_mode == "volume":
            message = tt("Preparing full-volume 3D preview...", self.lang)
            if self._volume_roi_inspect_enabled() and self._volume_roi_source_mode() != "full":
                message = tt("Preparing ROI crop preview...", self.lang)
            elif bool(getattr(self, "_volume_clarity_mode", False)) or self.current_volume_scope == "part":
                message = tt("Preparing local detail preview...", self.lang)
            show_canvas_status = self._set_volume_canvas_status_text(message)
            self._update_volume_render_status_label(message)
            if show_canvas_status:
                QApplication.processEvents()
        self.render_volume_preview()

    def _reset_active_volume_preview_state(self):
        self._volume_preview = None
        self._volume_preview_source_shape = ()
        self._volume_roi_preview_bbox = None
        self._volume_roi_preview_source_shape = ()
        self._volume_last_stats = {}
        self._volume_last_preview_build_ms = 0.0
        self._volume_render_mode = "still"
        self._volume_interaction_render_pending = False

    def _release_gpu_texture_cache(self):
        canvas = getattr(self, "volume_canvas", None)
        if canvas is None or not callable(getattr(canvas, "release_texture_cache", None)):
            return False
        try:
            canvas.release_texture_cache()
            self._volume_last_stats = dict(canvas.render_stats() or {}) if callable(getattr(canvas, "render_stats", None)) else {}
            return True
        except Exception:
            return False

    def _clear_volume_preview_cache(self):
        self._cancel_volume_preview_build()
        self._volume_preview_cache = OrderedDict()
        self._clear_volume_mask_caches()
        self._reset_active_volume_preview_state()

    def _active_volume_cache_owner(self):
        specimen_id = str(getattr(self, "current_specimen_id", "") or "")
        scope = str(getattr(self, "current_volume_scope", "") or "full")
        part_id = str(getattr(self, "current_part_id", "") or "")
        reslice_id = str(getattr(self, "current_reslice_id", "") or "")
        return (specimen_id, scope, part_id, reslice_id)

    def _volume_cache_owner_from_key(self, cache_key):
        if isinstance(cache_key, tuple) and cache_key and isinstance(cache_key[0], tuple) and len(cache_key[0]) == 4:
            return cache_key[0]
        return None

    def _clear_active_volume_preview_cache(self):
        self._cancel_volume_preview_build()
        owner = self._active_volume_cache_owner()
        self._volume_preview_cache = OrderedDict(
            (key, value)
            for key, value in self._volume_preview_cache.items()
            if self._volume_cache_owner_from_key(key) != owner
        )
        self._clear_volume_mask_caches(owner=owner)
        self._reset_active_volume_preview_state()

    def _clear_volume_mask_caches(self, owner=None):
        if owner is None:
            self._volume_mask_preview_cache = OrderedDict()
            self._volume_masked_preview_cache = OrderedDict()
            return
        self._volume_mask_preview_cache = OrderedDict(
            (key, value)
            for key, value in self._volume_mask_preview_cache.items()
            if self._volume_cache_owner_from_key(key) != owner
        )
        self._volume_masked_preview_cache = OrderedDict(
            (key, value)
            for key, value in self._volume_masked_preview_cache.items()
            if self._volume_cache_owner_from_key(key) != owner
        )

    def _touch_volume_cache_owner(self, owner):
        for cache in (self._volume_preview_cache, self._volume_mask_preview_cache, self._volume_masked_preview_cache):
            for key in list(cache.keys()):
                if self._volume_cache_owner_from_key(key) == owner:
                    cache.move_to_end(key)

    def _volume_cache_owner_limit(self):
        try:
            target_dim = int(self._active_volume_target_dim("still"))
        except Exception:
            slider = getattr(self, "volume_quality_slider", None)
            target_dim = int(slider.value()) if hasattr(slider, "value") else 0
        stream = dict((getattr(self, "_volume_last_stats", {}) or {}).get("gpu_stream_build") or {})
        if stream.get("degraded"):
            return 1
        if target_dim >= 3072:
            return int(TIF_VOLUME_ULTRA_QUALITY_CACHE_OWNER_LIMIT)
        if target_dim >= 2048:
            return int(TIF_VOLUME_HIGH_QUALITY_CACHE_OWNER_LIMIT)
        return int(TIF_VOLUME_MAX_CACHED_SPECIMENS)

    def _prune_volume_preview_cache(self):
        owners = []
        for cache in (self._volume_preview_cache, self._volume_mask_preview_cache, self._volume_masked_preview_cache):
            for key in cache.keys():
                owner = self._volume_cache_owner_from_key(key)
                if owner is not None and owner not in owners:
                    owners.append(owner)
        owner_limit = max(1, int(self._volume_cache_owner_limit()))
        while len(owners) > owner_limit:
            evicted_owner = owners.pop(0)
            self._volume_preview_cache = OrderedDict(
                (key, value)
                for key, value in self._volume_preview_cache.items()
                if self._volume_cache_owner_from_key(key) != evicted_owner
            )
            self._volume_mask_preview_cache = OrderedDict(
                (key, value)
                for key, value in self._volume_mask_preview_cache.items()
                if self._volume_cache_owner_from_key(key) != evicted_owner
            )
            self._volume_masked_preview_cache = OrderedDict(
                (key, value)
                for key, value in self._volume_masked_preview_cache.items()
                if self._volume_cache_owner_from_key(key) != evicted_owner
            )
        self._prune_volume_preview_variants_per_owner()

    def _prune_volume_preview_variants_per_owner(self):
        max_variants = int(max(1, TIF_VOLUME_MAX_PREVIEW_VARIANTS_PER_OWNER))
        for cache_name in ("_volume_preview_cache", "_volume_mask_preview_cache", "_volume_masked_preview_cache"):
            cache = getattr(self, cache_name, OrderedDict())
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
        owners = set()
        for cache in (self._volume_preview_cache, self._volume_mask_preview_cache, self._volume_masked_preview_cache):
            for key in cache.keys():
                owner = self._volume_cache_owner_from_key(key)
                if owner is not None:
                    owners.add(owner)
        return len(owners)

    def _volume_cache_estimated_bytes(self):
        total = 0
        seen = set()
        for cache in (self._volume_preview_cache, self._volume_mask_preview_cache, self._volume_masked_preview_cache):
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
        requested = self._volume_texture_target_dim()
        if self._volume_canvas_renderer != "gpu":
            return requested
        if self._volume_projection_mode() == "composite":
            return max(192, min(requested, 384))
        return max(256, min(requested, 640))

    def _active_volume_target_dim(self, mode=None):
        mode = mode or self._volume_render_mode
        if mode == "drag":
            return self._volume_drag_target_dim()
        requested = self._volume_texture_target_dim()
        if self.current_volume_scope == "part" and self.image_volume is not None:
            shape = tuple(int(value) for value in getattr(self.image_volume, "shape", ()) or ())
            voxel_count = int(np.prod(shape)) if len(shape) == 3 else 0
            if voxel_count > 0:
                if self._volume_clarity_mode:
                    clarity_dim = TIF_VOLUME_CLARITY_PART_FULL_DIM
                    if voxel_count > TIF_VOLUME_CLARITY_PART_FULL_VOXEL_LIMIT:
                        clarity_dim = TIF_VOLUME_CLARITY_PART_HIGH_DIM
                    requested = max(requested, min(max(shape), clarity_dim))
                elif voxel_count <= 64_000_000:
                    requested = max(requested, min(max(shape), 1536))
        return requested

    def _active_volume_roi_bbox(self, mode=None):
        mode = "drag" if mode == "drag" else "still"
        if mode != "still" or self.current_volume_scope != "full" or self.image_volume is None:
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
            return normalize_roi_bbox_zyx(bbox, self.image_volume.shape)
        except Exception:
            return None

    def _roi_texture_budget_bytes(self):
        mode = ""
        if hasattr(self, "volume_roi_budget_combo"):
            mode = str(self.volume_roi_budget_combo.currentData() or "").lower()
        if mode == "high":
            return HIGH_ROI_TEXTURE_BUDGET_BYTES
        return DEFAULT_ROI_TEXTURE_BUDGET_BYTES

    def _volume_preview_progress_message(self, mode, roi_bbox=None):
        if roi_bbox is not None:
            return tt("Preparing ROI crop preview...", self.lang)
        if bool(getattr(self, "_volume_clarity_mode", False)) or self.current_volume_scope == "part":
            return tt("Preparing local detail preview...", self.lang)
        return tt("Preparing full-volume 3D preview...", self.lang)

    def _should_show_volume_preview_progress(self, mode, roi_bbox=None):
        if mode != "still" or self.display_mode != "volume" or self.image_volume is None:
            return False
        try:
            dtype_size = max(1, int(np.dtype(getattr(self.image_volume, "dtype", np.uint8)).itemsize))
            if roi_bbox is not None:
                shape = roi_shape_zyx(roi_bbox)
                bytes_estimate = int(shape[0]) * int(shape[1]) * int(shape[2]) * dtype_size
                return bytes_estimate >= 32 * 1024 * 1024
            bytes_estimate = int(getattr(self.image_volume, "nbytes", 0) or 0)
            if self.current_volume_scope == "part" or bool(getattr(self, "_volume_clarity_mode", False)):
                return bytes_estimate >= 32 * 1024 * 1024
            return bytes_estimate >= 64 * 1024 * 1024
        except Exception:
            return True

    def _show_volume_preview_progress(self, message, detail=None):
        dialog = QProgressDialog(message, "", 0, 0, self)
        dialog.setWindowTitle(tt("Volume render", self.lang))
        dialog.setCancelButton(None)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        dialog.setMinimumDuration(0)
        if detail is None:
            detail = tt(
                "Downsampling volume and uploading texture. This can take a moment for large TIF stacks.",
                self.lang,
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
        if self.image_volume is None:
            return None
        shape = tuple(int(value) for value in self.image_volume.shape)
        mode = "drag" if mode == "drag" else "still"
        max_dim = self._active_volume_target_dim(mode)
        source_dtype = str(np.dtype(getattr(self.image_volume, "dtype", np.uint8)))
        preserve_source = mode == "still" and (self._volume_clarity_mode or self.current_volume_scope == "part")
        algorithm = self._volume_preview_algorithm(mode)
        roi_bbox = self._active_volume_roi_bbox(mode)
        roi_key = tuple(tuple(int(value) for value in pair) for pair in roi_bbox) if roi_bbox is not None else None
        if roi_bbox is not None:
            preserve_source = mode == "still" and (self._volume_clarity_mode or self.current_volume_scope == "part" or self._active_volume_roi_scale() > 1.0)
        owner = self._active_volume_cache_owner()
        _ = roi_key
        result = self.volume_preview_service.build_workbench_preview_request(
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
        mask = self._active_part_mask_volume()
        if mask is None:
            return None
        shape = tuple(int(value) for value in getattr(mask, "shape", ()) or ())
        mode = "drag" if mode == "drag" else "still"
        max_dim = self._active_volume_target_dim(mode)
        mask_algorithm = "nearest" if mode == "drag" else "occupancy"
        roi_bbox = self._active_volume_roi_bbox(mode)
        if self.current_volume_scope == "full" and mask is self.part_preview_mask:
            roi_bbox = None
        owner = self._active_volume_cache_owner()
        result = self.volume_preview_service.build_mask_preview_request(
            owner=owner,
            shape=shape,
            source_dtype=str(np.dtype(getattr(mask, "dtype", np.uint16))),
            max_dim=max_dim,
            mask_identity=id(mask),
            algorithm=mask_algorithm,
            roi_bbox=roi_bbox,
            mode=mode,
            message=tt("Preparing mask preview...", self.lang),
        )
        if not result:
            return None
        return dict(result.payload.get("request") or {})

    def _cache_volume_preview_result(self, request, preview, build_ms=None):
        if request is None or preview is None:
            return None
        cache_key = request["cache_key"]
        roi_bbox = request.get("roi_bbox")
        owner = request.get("owner")
        self._volume_preview_cache[cache_key] = preview
        self._touch_volume_cache_owner(owner)
        self._prune_volume_preview_cache()
        self._volume_preview = preview
        self._volume_preview_source_shape = cache_key
        self._volume_roi_preview_bbox = roi_bbox
        self._volume_roi_preview_source_shape = roi_shape_zyx(roi_bbox) if roi_bbox is not None else ()
        if build_ms is not None:
            self._volume_last_preview_build_ms = max(0.0, float(build_ms))
        return preview

    def _cache_volume_mask_preview_result(self, request, preview):
        if request is None or preview is None:
            return None
        cache_key = request["cache_key"]
        self._volume_mask_preview_cache[cache_key] = preview
        self._touch_volume_cache_owner(request.get("owner"))
        self._prune_volume_preview_cache()
        return preview

    def _ensure_volume_preview(self, mode=None):
        request = self._volume_preview_request(mode)
        if request is None:
            return None
        cache_key = request["cache_key"]
        roi_bbox = request.get("roi_bbox")
        cached = self._volume_preview_cache.get(cache_key)
        if cached is not None:
            self._volume_preview_cache.move_to_end(cache_key)
            self._touch_volume_cache_owner(request.get("owner"))
            self._volume_last_preview_build_ms = 0.0
            self._volume_preview = cached
            self._volume_preview_source_shape = cache_key
            self._volume_roi_preview_bbox = roi_bbox
            self._volume_roi_preview_source_shape = roi_shape_zyx(roi_bbox) if roi_bbox is not None else ()
            return cached

        mode = request["mode"]
        if self._should_show_volume_preview_progress(mode, roi_bbox):
            message = request.get("message") or tt("Preparing full-volume 3D preview...", self.lang)
            show_canvas_status = self._set_volume_canvas_status_text(message)
            self._update_volume_render_status_label(message)
            if show_canvas_status:
                QApplication.processEvents()
        build_start = time.perf_counter()
        if roi_bbox is not None:
            preview = build_roi_volume_preview(
                self.image_volume,
                roi_bbox,
                request["max_dim"],
                mode=request["algorithm"],
                preserve_source=request["preserve_source"],
                texture_budget_bytes=request["texture_budget_bytes"],
                max_texture_dim=GPU_VOLUME_MAX_TEXTURE_DIM,
            )
        else:
            preview = build_volume_preview(
                self.image_volume,
                request["max_dim"],
                mode=request["algorithm"],
                preserve_source=request["preserve_source"],
            )
        return self._cache_volume_preview_result(request, preview, (time.perf_counter() - build_start) * 1000.0)

    def _should_show_gpu_upload_progress(self, preview, mask_preview=None):
        if self._volume_canvas_renderer != "gpu" or self._volume_render_mode == "drag":
            return False
        try:
            bytes_estimate = int(getattr(preview, "nbytes", 0) or 0)
            if mask_preview is not None:
                bytes_estimate += int(getattr(mask_preview, "nbytes", 0) or 0)
            return bytes_estimate >= 32 * 1024 * 1024
        except Exception:
            return True

    def _should_show_volume_mask_preview_progress(self, mode, mask):
        if mode != "still" or self.display_mode != "volume" or mask is None:
            return False
        try:
            bytes_estimate = int(getattr(mask, "nbytes", 0) or 0)
            return bytes_estimate >= 32 * 1024 * 1024
        except Exception:
            return True

    def _mask_request_source_bytes(self, mask_request):
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
        if not mask_request or self.display_mode != "volume":
            return False
        if str(mask_request.get("mode") or "still") != "still":
            return False
        if self._volume_mask_preview_cache.get(mask_request.get("cache_key")) is not None:
            return False
        source_bytes = self._mask_request_source_bytes(mask_request)
        if source_bytes <= 0:
            return False
        return source_bytes >= TIF_GPU_STREAM_SYNC_MAX_BYTES

    def _cancel_volume_preview_build(self):
        worker = getattr(self, "_volume_preview_build_worker", None)
        if worker is not None and hasattr(worker, "cancel"):
            try:
                worker.cancel()
            except Exception:
                pass
        self._volume_preview_pending_token = 0
        self._volume_preview_pending_key = None
        self._volume_preview_pending_mask_key = None
        self._cancel_tif_task(self._volume_preview_build_task_id, "volume_preview_cancelled")
        self._volume_preview_build_task_id = ""
        self._set_volume_preview_build_controls_busy(False)

    def _cancel_and_wait_volume_preview_build(self, timeout_ms=2000):
        thread = getattr(self, "_volume_preview_build_thread", None)
        self._cancel_volume_preview_build()
        if thread is not None and thread.isRunning():
            thread.quit()
            thread.wait(int(max(0, timeout_ms)))

    def _cleanup_volume_preview_build_thread(self, thread=None, worker=None):
        if thread is not None and self._volume_preview_build_thread is not thread:
            return
        if worker is not None and self._volume_preview_build_worker is not worker:
            return
        self._volume_preview_build_thread = None
        self._volume_preview_build_worker = None

    def _volume_preview_build_controls(self):
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
            control = getattr(self, name, None)
            if control is not None:
                controls.append(control)
        return controls

    def _set_volume_preview_build_controls_busy(self, busy):
        busy = bool(busy)
        state_attr = "_volume_preview_busy_control_states"
        if busy:
            if getattr(self, state_attr, None):
                return
            states = []
            for control in self._volume_preview_build_controls():
                try:
                    states.append((control, bool(control.isEnabled())))
                    control.setEnabled(False)
                except RuntimeError:
                    continue
            setattr(self, state_attr, states)
            return
        states = list(getattr(self, state_attr, []) or [])
        setattr(self, state_attr, [])
        for control, was_enabled in states:
            try:
                control.setEnabled(bool(was_enabled))
            except RuntimeError:
                continue
        if hasattr(self, "_set_scope_controls_enabled"):
            self._set_scope_controls_enabled()

    def _is_volume_preview_build_pending(self, preview_key, mask_key=None):
        if self._volume_preview_build_thread is None:
            return False
        return self._volume_preview_pending_key == preview_key and self._volume_preview_pending_mask_key == mask_key

    def _start_volume_preview_build(self, volume_request=None, mask_request=None):
        if volume_request is None and mask_request is None:
            return False
        preview_key = volume_request.get("cache_key") if volume_request else None
        mask_key = mask_request.get("cache_key") if mask_request else None
        if self._is_volume_preview_build_pending(preview_key, mask_key):
            return True
        self._cancel_volume_preview_build()
        self._volume_preview_build_token += 1
        token = int(self._volume_preview_build_token)
        self._volume_preview_pending_token = token
        self._volume_preview_pending_key = preview_key
        self._volume_preview_pending_mask_key = mask_key
        message = (volume_request or {}).get("message") or tt("Preparing full-volume 3D preview...", self.lang)
        if mask_request and (volume_request is None or self._volume_preview_cache.get(preview_key) is not None):
            message = mask_request.get("message") or tt("Preparing mask preview...", self.lang)
        self._volume_preview_pending_message = str(message or "")
        self._set_volume_canvas_status_text(self._volume_preview_pending_message)
        self._update_volume_render_status_label(self._volume_preview_pending_message)
        self._set_volume_preview_build_controls_busy(True)
        task = self._start_tif_task(
            "volume_preview",
            action="build_preview",
            payload={"token": token, "preview_key": self._task_request_key(preview_key), "mask_key": self._task_request_key(mask_key)},
            request_key=self._task_request_key(preview_key or mask_key),
            message=self._volume_preview_pending_message,
        )
        self._volume_preview_build_task_id = task.task_id
        thread = QThread(self)
        worker = TifVolumePreviewBuildWorker(
            token,
            volume=self.image_volume,
            volume_request=volume_request,
            mask=self._active_part_mask_volume() if mask_request else None,
            mask_request=mask_request,
        )
        self._volume_preview_build_thread = thread
        self._volume_preview_build_worker = worker
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
        token = int(getattr(self, "_volume_preview_pending_token", 0) or 0)
        if token <= 0:
            return
        self._volume_preview_pending_message = str(message or "")
        if self.display_mode == "volume":
            self._set_volume_canvas_status_text(self._volume_preview_pending_message)
            self._update_volume_render_status_label(self._volume_preview_pending_message)

    def _on_volume_preview_build_finished(self, result):
        result = dict(result or {})
        token = int(result.get("token", 0) or 0)
        if token != int(getattr(self, "_volume_preview_pending_token", 0) or 0):
            return
        if not self._task_context_matches_current(
            self._volume_preview_build_task_id,
            fields=("specimen_id", "volume_scope", "part_id", "reslice_id", "display_mode"),
        ):
            self._cancel_tif_task(self._volume_preview_build_task_id, "stale_volume_preview_context")
            self._volume_preview_pending_token = 0
            self._volume_preview_pending_key = None
            self._volume_preview_pending_mask_key = None
            self._set_volume_preview_build_controls_busy(False)
            return
        self._volume_preview_pending_token = 0
        self._volume_preview_pending_key = None
        self._volume_preview_pending_mask_key = None
        self._set_volume_preview_build_controls_busy(False)
        if result.get("cancelled"):
            self._cancel_tif_task(self._volume_preview_build_task_id, "volume_preview_cancelled")
            self._volume_preview_build_task_id = ""
            return
        volume_request = result.get("volume_request") or {}
        mask_request = result.get("mask_request") or {}
        if result.get("preview") is not None:
            self._cache_volume_preview_result(volume_request, result.get("preview"), result.get("build_ms", 0.0))
        if result.get("mask_preview") is not None:
            self._cache_volume_mask_preview_result(mask_request, result.get("mask_preview"))
        self._finish_tif_task(self._volume_preview_build_task_id, payload={"token": token}, message="volume_preview_finished")
        self._volume_preview_build_task_id = ""
        if self.display_mode == "volume" and not getattr(self, "_handling_gpu_volume_failure", False):
            self.render_volume_preview()

    def _on_volume_preview_build_failed(self, result):
        result = dict(result or {})
        token = int(result.get("token", 0) or 0)
        if token != int(getattr(self, "_volume_preview_pending_token", 0) or 0):
            return
        self._volume_preview_pending_token = 0
        self._volume_preview_pending_key = None
        self._volume_preview_pending_mask_key = None
        self._set_volume_preview_build_controls_busy(False)
        message = tt("GPU renderer failed. Using CPU fallback: {0}", self.lang).format(str(result.get("error", "")))
        issue = self.preview_controller.classify_exception(
            RuntimeError(str(result.get("error", ""))),
            operation="volume_preview_build",
        )
        self.preview_controller.last_resource_issue = issue
        self._fail_tif_task(self._volume_preview_build_task_id, result.get("error", ""), payload=result, message=message)
        self._volume_preview_build_task_id = ""
        self._update_volume_render_status_label(message)
        self.log(message)

    def _volume_preview_algorithm(self, mode=None):
        mode = "drag" if mode == "drag" else "still"
        if mode == "drag":
            return "stride"
        return "hybrid"

    def _active_part_mask_volume(self):
        if self.image_volume is None:
            return None
        if self.current_volume_scope == "full":
            if self.part_preview_mask is not None and self._active_part_preview_bbox() is not None:
                return self.part_preview_mask
            return None
        if self.current_volume_scope != "part":
            return None
        result_region_mask = self._active_result_region_mask_volume()
        if result_region_mask is not None:
            return result_region_mask
        if self.current_reslice_id:
            return None
        if self.part_preview_mask is not None and self.part_preview_mask.shape == self.image_volume.shape:
            return self.part_preview_mask
        if self.part_mask_volume is not None and self.part_mask_volume.shape == self.image_volume.shape:
            return self.part_mask_volume
        return None

    def _active_part_mask_likely_available(self):
        if self.image_volume is None:
            return False
        mask = self._active_part_mask_volume()
        if mask is None:
            return False
        shape = tuple(int(value) for value in getattr(mask, "shape", ()) or ())
        if self.current_volume_scope == "full":
            part_preview_bbox = self._active_part_preview_bbox()
            if part_preview_bbox is None:
                return False
            try:
                image_shape = tuple(int(value) for value in roi_shape_zyx(part_preview_bbox))
            except Exception:
                return False
        else:
            image_shape = tuple(int(value) for value in getattr(self.image_volume, "shape", ()) or ())
        if shape != image_shape:
            return False
        if mask is self.part_preview_mask:
            return True
        if isinstance(mask, LazyRegionMaskVolume):
            return True
        if mask is self.part_mask_volume:
            part = self.project.get_part(self.current_specimen_id, self.current_part_id, default=None)
            if part is None:
                part = self.current_part if isinstance(self.current_part, dict) else {}
            status = str((part or {}).get("status") or "").lower()
            if status in TIF_MASK_PREVIEW_TRUSTED_STATUSES:
                return True
        try:
            source_bytes = int(getattr(mask, "nbytes", 0) or 0)
        except Exception:
            source_bytes = TIF_GPU_STREAM_SYNC_MAX_BYTES
        if source_bytes >= TIF_GPU_STREAM_SYNC_MAX_BYTES:
            return mask is not self.part_mask_volume
        return self._active_part_mask_has_voxels()

    def _active_result_region_mask_volume(self):
        if self.current_volume_scope != "part" or self.image_volume is None:
            return None
        if not getattr(self, "result_region_combo", None):
            return None
        if hasattr(self, "training_mode_tabs") and self.training_mode_tabs.currentWidget() is not getattr(self, "result_compare_page", None):
            return None
        region_id = self._result_region_id()
        if region_id <= 0:
            return None
        role = self._result_source_role()
        source = None
        active_role = self.label_role_combo.currentData() if hasattr(self, "label_role_combo") else ""
        if role == "editable_ai_result" and self.edit_volume is not None and self.edit_volume.shape == self.image_volume.shape:
            source = self.edit_volume
        elif active_role == role and self.label_volume is not None and self.label_volume.shape == self.image_volume.shape:
            source = self.label_volume
        else:
            label_path = self._current_part_label_path(role)
            if label_path and volume_sidecar_exists(label_path):
                try:
                    source = load_volume_sidecar(label_path, mmap_mode="r")
                except Exception:
                    source = None
        if source is None or getattr(source, "shape", None) != self.image_volume.shape:
            return None
        key = (
            self.current_specimen_id,
            self.current_part_id,
            self.current_reslice_id,
            role,
            int(region_id),
            str(getattr(source, "filename", "") or getattr(source, "path", "") or id(source)),
            tuple(int(value) for value in getattr(source, "shape", ()) or ()),
        )
        if key == self._result_region_mask_cache_key:
            cached = self._result_region_mask_cache.get(key)
            if cached is not None:
                return cached
        mask = LazyRegionMaskVolume(source, int(region_id))
        self._result_region_mask_cache = {key: mask}
        self._result_region_mask_cache_key = key
        return mask

    def _active_part_mask_has_voxels(self):
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
        mask = self._active_part_mask_volume()
        if mask is None:
            return None
        request = self._volume_mask_preview_request(mode)
        if request is None:
            return None
        mode = request["mode"]
        roi_bbox = request.get("roi_bbox")
        cache_key = request["cache_key"]
        cached = self._volume_mask_preview_cache.get(cache_key)
        if cached is not None:
            self._volume_mask_preview_cache.move_to_end(cache_key)
            self._touch_volume_cache_owner(request.get("owner"))
            return cached
        if self._should_show_volume_mask_preview_progress(mode, mask):
            message = request.get("message") or tt("Preparing mask preview...", self.lang)
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
        cached = self._volume_masked_preview_cache.get(cache_key)
        if cached is not None:
            self._volume_masked_preview_cache.move_to_end(cache_key)
            self._touch_volume_cache_owner(owner)
            return cached
        mask_values = np.asarray(mask_preview) > 0
        masked = np.ascontiguousarray(np.where(mask_values, preview, np.zeros_like(preview)))
        self._volume_masked_preview_cache[cache_key] = masked
        self._touch_volume_cache_owner(owner)
        self._prune_volume_preview_cache()
        return masked

    def _viewer_side_front_clip_mask(self, rotated_depth, front_clip):
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
        return normalize_preview_intensity(source, preserve_source=preserve_source)

    def _normalize_volume_preview_to_uint8(self, source):
        return self._normalize_volume_preview(source, preserve_source=False)

    def _sample_volume_preview_values(self, preview, max_samples=1_000_000):
        return sample_volume_values(preview, max_samples=max_samples)

    def _scale_volume_preview_to_uint8(self, preview, low, high):
        return scale_volume_to_uint8(preview, low, high)

    def _volume_texture_target_dim(self):
        if getattr(self, "_volume_quality_drag_pending", False):
            requested = getattr(self, "_volume_quality_committed_value", None)
        else:
            requested = None
        if requested is None:
            requested = int(self.volume_quality_slider.value())
        requested = max(8, int(requested))
        if self._volume_canvas_renderer == "gpu":
            return max(256, min(GPU_VOLUME_MAX_TEXTURE_DIM, requested))
        return max(32, min(128, requested))

    def _volume_render_state(self, mode=None):
        mode = "drag" if mode == "drag" else "still"
        samples = self._active_volume_sample_count() if mode == "still" else int(self.volume_sample_slider.value())
        if mode == "drag":
            if self._volume_projection_mode() == "composite":
                samples = max(192, min(samples, 384))
            else:
                samples = max(256, min(samples, 768))
        gradient_opacity, gradient_opacity_range = self._volume_gradient_opacity_settings(mode)
        return {
            "cutoff_percent": self.volume_cutoff_slider.value(),
            "yaw": self._volume_yaw,
            "pitch": self._volume_pitch,
            "zoom": self._volume_zoom,
            "render_quality": self._active_volume_target_dim(mode),
            "sample_steps": samples,
            "inside_depth": float(self.volume_inside_slider.value()) / 100.0,
            "front_clip": float(self.volume_clip_slider.value()) / 100.0,
            "render_mode": mode,
            "pan_x": self._volume_pan_x,
            "pan_y": self._volume_pan_y,
            "clarity_mode": self._volume_clarity_mode,
            "projection_mode": self._volume_projection_mode(),
            "supersample_scale": self._active_volume_roi_scale(),
            "tint_rgb": tuple(float(value) for value in self._volume_tint_rgb()),
            "transfer_preset": self._volume_transfer_preset(),
            "transfer_opacity": self._volume_transfer_opacity(mode),
            "mask_mode": self._volume_mask_mode(),
            "mask_opacity": max(0.0, min(1.0, float(self.volume_mask_opacity_slider.value()) / 100.0)),
            "enhancement": self._volume_detail_enhancement(mode),
            "tone_gamma": self._volume_tone_gamma(),
            "shader_quality_mode": self._volume_shader_quality_mode(),
            "jitter_strength": self._volume_jitter_strength(mode),
            "adaptive_step_strength": self._volume_adaptive_step_strength(mode),
            "gradient_opacity": gradient_opacity,
            "gradient_opacity_range": gradient_opacity_range,
            "surface_refine": bool(self.volume_surface_refine_check.isChecked()),
            "clip_plane_enabled": bool(self.volume_clip_plane_check.isChecked()),
            "clip_plane_depth": float(self.volume_clip_plane_depth_slider.value()) / 100.0,
            "clip_plane_normal": self._volume_clip_plane_normal(),
        }

    def _sync_gpu_volume_canvas(self, preview, mask_preview=None, mask_mode=None, volume_request=None, mask_request=None):
        if self._volume_canvas_renderer != "gpu" or not hasattr(self.volume_canvas, "set_volume_data"):
            return False
        mask_mode = mask_mode if mask_mode in {"mask_boundary", "masked_image"} else "image_only"
        if mask_mode != "image_only" and not hasattr(self.volume_canvas, "set_mask_data"):
            return False
        source_shape, spacing_zyx = self._volume_source_geometry()
        mode = "drag" if self._volume_render_mode == "drag" else "still"
        state = self._volume_render_state(mode)
        state["mask_mode"] = mask_mode
        if hasattr(self.volume_canvas, "set_axis_overlays"):
            self.volume_canvas.set_axis_overlays(self._local_axis_volume_overlays())
        if self._should_show_gpu_upload_progress(preview, mask_preview if mask_mode != "image_only" else None):
            message = tt("Uploading 3D preview to GPU...", self.lang)
            show_canvas_status = self._set_volume_canvas_status_text(message)
            self._update_volume_render_status_label(message)
            if show_canvas_status:
                QApplication.processEvents()
        if hasattr(self.volume_canvas, "set_volume_render_inputs"):
            self.volume_canvas.set_volume_render_inputs(
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
            self.volume_canvas.set_volume_data(
                preview,
                source_shape=source_shape,
                spacing_zyx=spacing_zyx,
                cache_key=(volume_request or {}).get("cache_key"),
            )
        except TypeError:
            self.volume_canvas.set_volume_data(preview, source_shape=source_shape, spacing_zyx=spacing_zyx)
        if hasattr(self.volume_canvas, "set_mask_data"):
            try:
                self.volume_canvas.set_mask_data(
                    mask_preview if mask_mode != "image_only" else None,
                    cache_key=(mask_request or {}).get("cache_key") if mask_mode != "image_only" else None,
                )
            except TypeError:
                self.volume_canvas.set_mask_data(mask_preview if mask_mode != "image_only" else None)
        if hasattr(self.volume_canvas, "set_render_state"):
            self.volume_canvas.set_render_state(**state)
        return True

    def _gpu_volume_source_for_request(self, volume_request):
        if self.image_volume is None:
            return None, (), None
        roi_bbox = (volume_request or {}).get("roi_bbox")
        if roi_bbox is None:
            return self.image_volume, tuple(int(value) for value in self.image_volume.shape), None
        try:
            z_pair, y_pair, x_pair = normalize_roi_bbox_zyx(roi_bbox, self.image_volume.shape)
            source = self.image_volume[int(z_pair[0]):int(z_pair[1]), int(y_pair[0]):int(y_pair[1]), int(x_pair[0]):int(x_pair[1])]
            shape = tuple(int(value) for value in getattr(source, "shape", ()) or ())
            if len(shape) != 3 or min(shape) <= 0:
                return None, (), None
            return source, shape, (tuple(int(value) for value in z_pair), tuple(int(value) for value in y_pair), tuple(int(value) for value in x_pair))
        except Exception:
            return None, (), None

    def _volume_request_source_bytes(self, volume_request):
        if self.image_volume is None or not volume_request:
            return 0
        try:
            dtype_size = max(1, int(np.dtype(getattr(self.image_volume, "dtype", np.uint8)).itemsize))
            roi_bbox = volume_request.get("roi_bbox")
            if roi_bbox is not None:
                shape = roi_shape_zyx(roi_bbox)
            else:
                shape = tuple(int(value) for value in getattr(self.image_volume, "shape", ()) or ())
            if len(shape) != 3 or min(shape) <= 0:
                return 0
            return int(shape[0]) * int(shape[1]) * int(shape[2]) * dtype_size
        except Exception:
            return 0

    def _should_build_volume_preview_in_background(self, volume_request):
        if not volume_request or self.display_mode != "volume":
            return False
        if str(volume_request.get("mode") or "still") != "still":
            return False
        if self._volume_preview_cache.get(volume_request.get("cache_key")) is not None:
            return False
        if (
            self.current_volume_scope == "full"
            and volume_request.get("roi_bbox") is None
            and self._volume_canvas_renderer == "gpu"
            and hasattr(self.volume_canvas, "build_volume_texture_from_source")
        ):
            return False
        source_bytes = self._volume_request_source_bytes(volume_request)
        if source_bytes <= 0:
            return False
        return source_bytes >= TIF_GPU_STREAM_SYNC_MAX_BYTES

    def _gpu_mask_source_for_request(self, mask_request):
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
        if not mask_request or not hasattr(self.volume_canvas, "build_mask_texture_from_source"):
            return False
        source, source_shape, _normalized_roi_bbox = self._gpu_mask_source_for_request(mask_request)
        if source is None:
            return False
        self._begin_volume_preview_ui_wait()
        try:
            return bool(
                self.volume_canvas.build_mask_texture_from_source(
                    source,
                    int(mask_request.get("max_dim", 1024)),
                    algorithm=str(mask_request.get("algorithm", "occupancy")),
                    cache_key=mask_request.get("cache_key"),
                    source_shape=source_shape,
                )
            )
        except Exception as exc:
            self._volume_last_stats = dict(getattr(self, "_volume_last_stats", {}) or {})
            self._volume_last_stats["gpu_mask_build_error"] = str(exc)
            self.preview_controller.last_resource_issue = self.preview_controller.classify_exception(exc, operation="gpu_mask_texture")
            return False
        finally:
            self._end_volume_preview_ui_wait()

    def _try_build_volume_gpu_texture(self, volume_request, mask_mode="image_only", mask_request=None, mask_preview=None):
        if not volume_request or self.image_volume is None:
            return False
        if self._volume_canvas_renderer != "gpu" or not hasattr(self.volume_canvas, "build_volume_texture_from_source"):
            return False
        if self._volume_render_mode == "drag" or str(volume_request.get("mode") or "") == "drag":
            return False
        supports_streamed_mask = bool(mask_mode != "image_only" and mask_request is not None and hasattr(self.volume_canvas, "build_mask_texture_from_source"))
        supports_mask_preview_upload = bool(mask_mode != "image_only" and hasattr(self.volume_canvas, "set_mask_data"))
        if mask_mode != "image_only" and not (supports_streamed_mask or supports_mask_preview_upload):
            return False
        message = volume_request.get("message") or tt("Preparing full-volume 3D preview...", self.lang)
        self._update_volume_render_status_label(message)
        source, request_source_shape, normalized_roi_bbox = self._gpu_volume_source_for_request(volume_request)
        if source is None:
            return False
        use_streamed_mask = supports_streamed_mask and (mask_preview is None or not supports_mask_preview_upload)
        if mask_mode != "image_only" and not use_streamed_mask and mask_preview is None and mask_request is not None:
            mask_preview = self._volume_mask_preview_cache.get(mask_request.get("cache_key"))
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
            provider = self.volume_canvas.build_volume_texture_from_source(
                source,
                int(volume_request.get("max_dim", 1024)),
                algorithm=str(volume_request.get("algorithm", "hybrid")),
                preserve_source=bool(volume_request.get("preserve_source", False)),
                cache_key=volume_request.get("cache_key"),
                source_shape=source_shape,
                spacing_zyx=spacing_zyx,
            )
        except Exception as exc:
            self._volume_last_stats = dict(getattr(self, "_volume_last_stats", {}) or {})
            self._volume_last_stats["gpu_preview_build_error"] = str(exc)
            self.preview_controller.last_resource_issue = self.preview_controller.classify_exception(exc, operation="gpu_volume_texture")
            return False
        finally:
            self._end_volume_preview_ui_wait()
        if provider is None:
            return False
        self._volume_preview = None
        self._volume_preview_source_shape = volume_request.get("cache_key")
        self._volume_roi_preview_bbox = normalized_roi_bbox
        self._volume_roi_preview_source_shape = tuple(int(value) for value in request_source_shape) if normalized_roi_bbox is not None else ()
        self._volume_last_preview_build_ms = 0.0
        if hasattr(self.volume_canvas, "set_axis_overlays"):
            self.volume_canvas.set_axis_overlays(self._local_axis_volume_overlays())
        if mask_mode != "image_only" and use_streamed_mask:
            if not self._try_build_mask_gpu_texture(mask_request):
                mask_mode = "image_only"
                state["mask_mode"] = "image_only"
        elif (mask_mode == "image_only" and hasattr(self.volume_canvas, "set_mask_data")) or (
            supports_mask_preview_upload and mask_preview is not None
        ):
            try:
                self.volume_canvas.set_mask_data(
                    mask_preview if mask_mode != "image_only" else None,
                    cache_key=(mask_request or {}).get("cache_key") if mask_mode != "image_only" else None,
                )
            except TypeError:
                self.volume_canvas.set_mask_data(mask_preview if mask_mode != "image_only" else None)
        if hasattr(self.volume_canvas, "set_render_state"):
            self.volume_canvas.set_render_state(**state)
        if hasattr(self.volume_canvas, "render_stats"):
            self._volume_last_stats = dict(self.volume_canvas.render_stats() or {})
        return True

    def _try_build_full_volume_gpu_texture(self, volume_request, mask_mode="image_only"):
        return self._try_build_volume_gpu_texture(volume_request, mask_mode=mask_mode)

    def _request_volume_interaction_render(self):
        if self.display_mode != "volume":
            return
        self._volume_interaction_render_pending = True
        if self._volume_interaction_render_scheduled:
            return
        self._volume_interaction_render_scheduled = True

        def run():
            self._volume_interaction_render_scheduled = False
            if not self._volume_interaction_render_pending:
                return
            self._volume_interaction_render_pending = False
            self._render_volume_interaction_preview()

        delay_ms = int(self._volume_interaction_render_interval_ms)
        if self._volume_canvas_renderer != "gpu":
            delay_ms = max(delay_ms, 80)
        QTimer.singleShot(delay_ms, run)

    def _render_volume_interaction_preview(self):
        if self.display_mode != "volume" or self.image_volume is None:
            return
        if self._sync_gpu_volume_camera_only():
            self._update_volume_render_status_label()
            return
        self.render_volume_preview()

    def _sync_gpu_volume_camera_only(self):
        if self._volume_canvas_renderer != "gpu" or not hasattr(self.volume_canvas, "set_render_state"):
            return False
        if not callable(getattr(self.volume_canvas, "has_volume", None)) or not self.volume_canvas.has_volume():
            return False
        mode = "drag" if self._volume_render_mode == "drag" else "still"
        state = self._volume_render_state(mode)
        state["mask_mode"] = self._volume_mask_mode()
        if hasattr(self.volume_canvas, "set_axis_overlays"):
            self.volume_canvas.set_axis_overlays(self._local_axis_volume_overlays())
        if callable(getattr(self.volume_canvas, "set_interaction_render_state", None)):
            self.volume_canvas.set_interaction_render_state(**state)
        else:
            self.volume_canvas.set_render_state(**state)
        return True

    def _volume_source_geometry(self):
        shape = tuple(int(value) for value in getattr(self.image_volume, "shape", ()) or ())
        spacing = ()
        roi_shape = tuple(int(value) for value in getattr(self, "_volume_roi_preview_source_shape", ()) or ())
        if len(roi_shape) == 3 and min(roi_shape) > 0:
            shape = roi_shape
        if self.current_volume_scope == "part" and self.current_reslice_id:
            reslice = self._current_part_reslice_record()
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
        if self.current_volume_scope == "part":
            record = ((self.current_part or {}).get("image") or {})
        else:
            specimen = self.project.get_specimen(self.current_specimen_id, default=None) if self.current_specimen_id else None
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
        if getattr(self, "_volume_render_scheduled", False):
            return
        self._volume_render_scheduled = True

        def run():
            self._volume_render_scheduled = False
            if self.display_mode == "volume" and not getattr(self, "_handling_gpu_volume_failure", False):
                self.render_volume_preview()

        QTimer.singleShot(0, run)

    def render_volume_preview(self):
        if not hasattr(self, "volume_canvas"):
            return
        if getattr(self, "_handling_gpu_volume_failure", False):
            return
        if bool(getattr(self, "_defer_volume_preview_render_once", False)):
            self._defer_volume_preview_render_once = False
            if self.display_mode == "volume":
                message = tt("Preparing full-volume 3D preview...", self.lang)
                self._set_volume_canvas_status_text(message)
                self._update_volume_render_status_label(message)
                QTimer.singleShot(0, self.render_volume_preview)
            return
        if self.display_mode == "volume":
            self._ensure_volume_canvas()
        if self.image_volume is None:
            specimen = self.project.get_specimen(self.current_specimen_id, default=None) if self.current_specimen_id else None
            message = self._volume_unavailable_message(specimen)
            if hasattr(self.volume_canvas, "set_axis_overlays"):
                self.volume_canvas.set_axis_overlays([])
            self.volume_canvas.clear()
            self.volume_canvas.setText(message)
            self._update_volume_render_status_label(message)
            return
        mode = "drag" if self._volume_render_mode == "drag" else "still"
        volume_request = self._volume_preview_request(mode)
        if volume_request is not None:
            self._update_volume_render_status_label(
                volume_request.get("message") or self._volume_preview_progress_message(mode, volume_request.get("roi_bbox"))
            )
        else:
            self._update_volume_render_status_label(tt("Building 3D preview...", self.lang))
        preview = None
        if volume_request is not None:
            preview = self._volume_preview_cache.get(volume_request["cache_key"])
            if preview is not None:
                self._volume_preview_cache.move_to_end(volume_request["cache_key"])
                self._touch_volume_cache_owner(volume_request.get("owner"))
                self._volume_preview = preview
                self._volume_preview_source_shape = volume_request["cache_key"]
                roi_bbox = volume_request.get("roi_bbox")
                self._volume_roi_preview_bbox = roi_bbox
                self._volume_roi_preview_source_shape = roi_shape_zyx(roi_bbox) if roi_bbox is not None else ()
            elif mode == "still" and self.display_mode == "volume":
                mask_mode_for_gpu = self._volume_mask_mode()
                mask_request_for_gpu = None
                mask_preview_for_gpu = None
                if mask_mode_for_gpu != "image_only":
                    mask_request_for_gpu = self._volume_mask_preview_request(mode)
                    if mask_request_for_gpu is not None:
                        mask_preview_for_gpu = self._volume_mask_preview_cache.get(mask_request_for_gpu["cache_key"])
                        if mask_preview_for_gpu is not None:
                            self._volume_mask_preview_cache.move_to_end(mask_request_for_gpu["cache_key"])
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
            if hasattr(self.volume_canvas, "set_axis_overlays"):
                self.volume_canvas.set_axis_overlays([])
            self.volume_canvas.clear()
            self.volume_canvas.setText(tt("No TIF volume loaded", self.lang))
            self._update_volume_render_status_label(tt("No TIF volume loaded", self.lang))
            return
        mask_mode = self._volume_mask_mode()
        mask_preview = None
        mask_request = None
        if mask_mode != "image_only":
            mask_request = self._volume_mask_preview_request(mode)
            if mask_request is not None:
                mask_preview = self._volume_mask_preview_cache.get(mask_request["cache_key"])
                if mask_preview is not None:
                    self._volume_mask_preview_cache.move_to_end(mask_request["cache_key"])
                    self._touch_volume_cache_owner(mask_request.get("owner"))
                elif mode == "still" and self.display_mode == "volume":
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
        if mask_mode != "image_only" and not hasattr(self.volume_canvas, "set_volume_pixmap"):
            self._switch_volume_canvas_to_cpu("Mask inspection uses CPU fallback.")
        pixmap = self._render_volume_preview_pixmap(preview, mask_preview=mask_preview, mask_mode=mask_mode)
        if hasattr(self.volume_canvas, "set_axis_overlays"):
            self.volume_canvas.set_axis_overlays(self._local_axis_volume_overlays())
        self.volume_canvas.set_volume_pixmap(pixmap)
        self._update_volume_render_status_label()

    def _render_volume_preview_pixmap(self, preview, mask_preview=None, mask_mode="image_only"):
        max_value = float(np.iinfo(preview.dtype).max) if np.issubdtype(preview.dtype, np.integer) else 1.0
        projection_mode = self._volume_projection_mode()
        cutoff = float(self.volume_cutoff_slider.value()) / 100.0
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
            return self._render_slice_pixmap(center_slice)

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

        yaw = math.radians(self._volume_yaw)
        pitch = math.radians(self._volume_pitch)
        cy, sy = math.cos(yaw), math.sin(yaw)
        cp, sp = math.cos(pitch), math.sin(pitch)
        rot_yaw = np.array([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]], dtype=np.float32)
        rot_pitch = np.array([[1.0, 0.0, 0.0], [0.0, cp, -sp], [0.0, sp, cp]], dtype=np.float32)
        rotated = coords @ (rot_yaw @ rot_pitch).T
        front_clip = max(0.0, min(0.92, float(self.volume_clip_slider.value()) / 100.0))
        if front_clip > 0.0:
            keep = self._viewer_side_front_clip_mask(rotated[:, 2], front_clip)
            if np.any(keep):
                rotated = rotated[keep]
                values = values[keep]
                point_indices = point_indices[keep]
            else:
                pixmap = QPixmap(360, 360)
                pixmap.fill(QColor(_tif_canvas_background(self.current_theme)))
                return pixmap

        out_size = 360
        scale = (out_size * 0.78) * float(self._volume_zoom)
        pan_scale = out_size * 0.5
        center_x = out_size / 2.0 + self._volume_pan_x * pan_scale
        center_y = out_size / 2.0 - self._volume_pan_y * pan_scale
        px = np.round(rotated[:, 0] * scale + center_x).astype(np.int32)
        py = np.round(-rotated[:, 1] * scale + center_y).astype(np.int32)
        inside = (px >= 0) & (px < out_size) & (py >= 0) & (py < out_size)
        if not np.any(inside):
            pixmap = QPixmap(out_size, out_size)
            pixmap.fill(QColor(_tif_canvas_background(self.current_theme)))
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
                opacity = max(0.0, min(1.0, float(self.volume_mask_opacity_slider.value()) / 100.0))
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

    def _reset_annotation_stroke(self):
        self._annotation_stroke_active = False
        self._annotation_stroke_undo_pushed = False
        self._annotation_stroke_z_index = None
        self._annotation_stroke_last_pixel = None
        self._annotation_stroke_changed = False

    def begin_annotation_stroke(self):
        self._annotation_stroke_active = True
        self._annotation_stroke_undo_pushed = False
        self._annotation_stroke_z_index = None
        self._annotation_stroke_last_pixel = None
        self._annotation_stroke_changed = False

    def finish_annotation_stroke(self):
        self._reset_annotation_stroke()

    def _ensure_annotation_undo_for_slice(self, z_index):
        if not self._annotation_stroke_active:
            self._push_undo()
            return
        if self._annotation_stroke_undo_pushed and self._annotation_stroke_z_index == z_index:
            return
        self._push_undo()
        self._annotation_stroke_undo_pushed = True
        self._annotation_stroke_z_index = int(z_index)

    def _paint_disc_on_slice(self, z_index, px, py, radius, value):
        if self.edit_volume is None:
            return False
        height, width = self.edit_volume.shape[1], self.edit_volume.shape[2]
        px = max(0, min(width - 1, int(px)))
        py = max(0, min(height - 1, int(py)))
        radius = max(1, int(radius))
        y0 = max(0, py - radius)
        y1 = min(height, py + radius + 1)
        x0 = max(0, px - radius)
        x1 = min(width, px + radius + 1)
        if y0 >= y1 or x0 >= x1:
            return False
        yy, xx = np.ogrid[y0:y1, x0:x1]
        mask = (xx - px) ** 2 + (yy - py) ** 2 <= radius ** 2
        target = self.edit_volume[int(z_index), y0:y1, x0:x1]
        before = target[mask].copy()
        target[mask] = int(value)
        return bool(np.any(before != int(value)))

    def _paint_interpolated_stroke_on_slice(self, z_index, start_pixel, end_pixel, radius, value):
        if start_pixel is None:
            return self._paint_disc_on_slice(z_index, end_pixel[0], end_pixel[1], radius, value)
        x0, y0 = [int(v) for v in start_pixel]
        x1, y1 = [int(v) for v in end_pixel]
        steps = max(abs(x1 - x0), abs(y1 - y0), 1)
        changed = False
        for step in range(steps + 1):
            ratio = float(step) / float(steps)
            px = int(round(x0 + (x1 - x0) * ratio))
            py = int(round(y0 + (y1 - y0) * ratio))
            changed = self._paint_disc_on_slice(z_index, px, py, radius, value) or changed
        return changed

    def paint_at_widget_position(self, x, y, erase=False, continue_stroke=False):
        if self.image_volume is None:
            return
        if not self._guard_backend_write_lock(show_message=False):
            self._set_operation_feedback(self._backend_write_lock_message())
            return
        block_reason = self._editable_label_block_reason(require_working_edit=True)
        if block_reason:
            self._set_operation_feedback(block_reason)
            return
        if self.edit_volume is None:
            self._set_operation_feedback(tt("Creating current label layer before painting...", self.lang))
            if not self._ensure_working_edit_volume():
                self._set_operation_feedback(tt("Current label layer is unavailable. Check the working volume path before editing labels.", self.lang))
                return
        z_index = int(self.slice_slider.value())
        height, width = self.image_volume.shape[1], self.image_volume.shape[2]
        pixel = self._widget_to_image_pixel(x, y, width, height)
        if pixel is None:
            return
        radius = max(1, int(self.brush_size_slider.value()))
        active_stroke = bool(continue_stroke and self._annotation_stroke_active)
        if not active_stroke and continue_stroke:
            self.begin_annotation_stroke()
            active_stroke = True
        previous_pixel = self._annotation_stroke_last_pixel if active_stroke else None
        self._ensure_annotation_undo_for_slice(z_index)
        value = 0 if erase else int(self.current_material_id)
        changed = self._paint_interpolated_stroke_on_slice(z_index, previous_pixel, pixel, radius, value)
        if active_stroke:
            self._annotation_stroke_last_pixel = tuple(pixel)
            self._annotation_stroke_changed = self._annotation_stroke_changed or changed
        if changed:
            self._mark_edit_slice_dirty(z_index)
            self._mark_working_edit_dirty()
            self.render_current_slice()
        if erase:
            message = tt("Erased labels on slice {0}.", self.lang).format(z_index + 1)
        else:
            message = tt("Painted label {0} on slice {1}.", self.lang).format(self.current_material_id, z_index + 1)
        self._set_operation_feedback(message, log=False)

    def _polygon_fill_mask(self, points, width, height):
        if len(points) < 3 or width <= 0 or height <= 0:
            return np.zeros((max(0, height), max(0, width)), dtype=bool)
        polygon = []
        for point in points:
            if point is None or len(point) < 2:
                continue
            x = max(-1.0, min(float(width), float(point[0]) + 0.5))
            y = max(-1.0, min(float(height), float(point[1]) + 0.5))
            if not polygon or (polygon[-1][0] != x or polygon[-1][1] != y):
                polygon.append((x, y))
        if len(polygon) >= 2 and polygon[0] == polygon[-1]:
            polygon.pop()
        if len(polygon) < 3:
            return np.zeros((height, width), dtype=bool)
        mask = np.zeros((height, width), dtype=bool)
        edges = list(zip(polygon, polygon[1:] + polygon[:1]))
        for y in range(height):
            scan_y = float(y) + 0.5
            intersections = []
            for (x0, y0), (x1, y1) in edges:
                if y0 == y1:
                    continue
                if (y0 <= scan_y < y1) or (y1 <= scan_y < y0):
                    ratio = (scan_y - y0) / (y1 - y0)
                    intersections.append(x0 + ratio * (x1 - x0))
            intersections.sort()
            for left, right in zip(intersections[0::2], intersections[1::2]):
                x_start = max(0, int(math.ceil(min(left, right) - 0.5)))
                x_end = min(width - 1, int(math.floor(max(left, right) - 0.5)))
                if x_start <= x_end:
                    mask[y, x_start : x_end + 1] = True
        return mask

    def _rect_fill_mask(self, start_pixel, end_pixel, width, height):
        mask = np.zeros((height, width), dtype=bool)
        if start_pixel is None or end_pixel is None:
            return mask
        x0, y0 = [int(v) for v in start_pixel]
        x1, y1 = [int(v) for v in end_pixel]
        left = max(0, min(x0, x1))
        right = min(width - 1, max(x0, x1))
        top = max(0, min(y0, y1))
        bottom = min(height - 1, max(y0, y1))
        if right - left < 1 or bottom - top < 1:
            return mask
        mask[top : bottom + 1, left : right + 1] = True
        return mask

    def _ellipse_fill_mask(self, start_pixel, end_pixel, width, height):
        mask = np.zeros((height, width), dtype=bool)
        if start_pixel is None or end_pixel is None:
            return mask
        x0, y0 = [int(v) for v in start_pixel]
        x1, y1 = [int(v) for v in end_pixel]
        left = max(0, min(x0, x1))
        right = min(width - 1, max(x0, x1))
        top = max(0, min(y0, y1))
        bottom = min(height - 1, max(y0, y1))
        if right - left < 1 or bottom - top < 1:
            return mask
        cx = (left + right) / 2.0
        cy = (top + bottom) / 2.0
        rx = max(0.5, (right - left + 1) / 2.0)
        ry = max(0.5, (bottom - top + 1) / 2.0)
        yy, xx = np.ogrid[top : bottom + 1, left : right + 1]
        local = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1.0
        mask[top : bottom + 1, left : right + 1] = local
        return mask

    def _fill_risk_suffix(self, mask):
        if mask is None or mask.size == 0:
            return ""
        count = int(np.count_nonzero(mask))
        if count <= 0:
            return ""
        total = max(1, int(mask.size))
        warnings = []
        percent = int(round((count / total) * 100.0))
        if percent >= 35:
            warnings.append(tt("Large fill area: {0}% of slice.", self.lang).format(percent))
        if (
            np.any(mask[0, :])
            or np.any(mask[-1, :])
            or np.any(mask[:, 0])
            or np.any(mask[:, -1])
        ):
            warnings.append(tt("Fill touches the image edge.", self.lang))
        return (" " + " ".join(warnings)) if warnings else ""

    def _apply_mask_to_slice(self, z_index, mask, value, message_template, *, allow_noop=False):
        if not self._guard_backend_write_lock(show_message=False):
            self._set_operation_feedback(self._backend_write_lock_message())
            return False
        if self.edit_volume is None:
            return False
        z_index = int(z_index)
        if z_index < 0 or z_index >= int(self.edit_volume.shape[0]):
            return False
        if mask is None:
            return False
        mask = np.asarray(mask, dtype=bool)
        height, width = self.edit_volume.shape[1], self.edit_volume.shape[2]
        if mask.shape != (height, width):
            return False
        count = int(np.count_nonzero(mask))
        if count <= 0:
            self._set_operation_feedback(tt("Shape fill is too small. Drag a wider area before releasing.", self.lang))
            return False
        current_slice = self.edit_volume[z_index]
        value = int(value)
        changed_mask = mask & (current_slice != value)
        changed_count = int(np.count_nonzero(changed_mask))
        if changed_count <= 0:
            if allow_noop:
                message = tt("No label changes were needed on slice {0}.", self.lang).format(z_index + 1)
                self._set_operation_feedback(message, log=False)
                return True
            message = tt(message_template, self.lang).format(value, z_index + 1, count) + self._fill_risk_suffix(mask)
            self._set_operation_feedback(message, log=False)
            return True
        self._push_undo_for_slice(z_index)
        current_slice[mask] = value
        self._mark_edit_slice_dirty(z_index)
        self._mark_working_edit_dirty()
        if self._current_slice_axis() == "z":
            self.slice_slider.setValue(z_index)
        self.render_current_slice()
        message = tt(message_template, self.lang).format(value, z_index + 1, changed_count) + self._fill_risk_suffix(mask)
        self._set_operation_feedback(message, log=False)
        return True

    def finish_lasso_fill(self, points):
        if self.image_volume is None:
            return False
        if not self._guard_backend_write_lock(show_message=False):
            self._set_operation_feedback(self._backend_write_lock_message())
            return False
        block_reason = self._editable_label_block_reason(require_working_edit=True)
        if block_reason:
            self._set_operation_feedback(block_reason)
            return False
        if len(points or []) < 3:
            self._set_operation_feedback(tt("Lasso fill needs at least 3 points.", self.lang))
            return False
        if self.edit_volume is None:
            self._set_operation_feedback(tt("Creating current label layer before filling...", self.lang))
            if not self._ensure_working_edit_volume():
                self._set_operation_feedback(tt("Current label layer is unavailable. Check the working volume path before editing labels.", self.lang))
                return False
        z_index = int(self.slice_slider.value())
        height, width = self.image_volume.shape[1], self.image_volume.shape[2]
        mask = self._polygon_fill_mask(points, width, height)
        if int(np.count_nonzero(mask)) <= 0:
            self._set_operation_feedback(tt("Lasso fill did not cover any pixels.", self.lang))
            return False
        return self._apply_mask_to_slice(z_index, mask, int(self.current_material_id), "Filled label {0} on slice {1}: {2} pixel(s).")

    def finish_shape_fill_drag(self, mode, start_x, start_y, end_x, end_y):
        if self.image_volume is None:
            return False
        if not self._guard_backend_write_lock(show_message=False):
            self._set_operation_feedback(self._backend_write_lock_message())
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
        z_index = int(self.slice_slider.value())
        height, width = self.image_volume.shape[1], self.image_volume.shape[2]
        start_pixel = self._widget_to_image_pixel(start_x, start_y, width, height)
        end_pixel = self._widget_to_image_pixel(end_x, end_y, width, height)
        if start_pixel is None or end_pixel is None:
            return False
        if mode == "ellipse":
            mask = self._ellipse_fill_mask(start_pixel, end_pixel, width, height)
            template = "Filled ellipse label {0} on slice {1}: {2} pixel(s)."
        else:
            mask = self._rect_fill_mask(start_pixel, end_pixel, width, height)
            template = "Filled rectangle label {0} on slice {1}: {2} pixel(s)."
        if int(np.count_nonzero(mask)) <= 0:
            self._set_operation_feedback(tt("Shape fill is too small. Drag a wider area before releasing.", self.lang))
            return False
        return self._apply_mask_to_slice(z_index, mask, int(self.current_material_id), template)

    def _bounding_rect_for_mask(self, mask):
        if mask is None:
            return None
        ys, xs = np.nonzero(np.asarray(mask, dtype=bool))
        if len(xs) <= 0 or len(ys) <= 0:
            return None
        return [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]

    def _rect_mask_from_bounds(self, bounds, width, height):
        if bounds is None:
            return np.zeros((height, width), dtype=bool)
        x0, y0, x1, y1 = [int(round(float(value))) for value in bounds]
        x0 = max(0, min(width, x0))
        x1 = max(0, min(width, x1))
        y0 = max(0, min(height, y0))
        y1 = max(0, min(height, y1))
        if x1 <= x0 or y1 <= y0:
            return np.zeros((height, width), dtype=bool)
        mask = np.zeros((height, width), dtype=bool)
        mask[y0:y1, x0:x1] = True
        return mask

    def interpolate_current_label_between_key_slices(self):
        if not self._ensure_editable_working_edit_for_helper():
            return False
        material_id = int(self.current_material_id)
        if material_id == 0:
            self._set_operation_feedback(tt("Background label 0 is not supported by this helper.", self.lang))
            return False
        volume = self.edit_volume
        key_slices = []
        key_masks = {}
        for z_index in range(int(volume.shape[0])):
            mask = np.asarray(volume[z_index] == material_id, dtype=bool)
            if np.any(mask):
                key_slices.append(int(z_index))
                key_masks[int(z_index)] = mask.copy()
        if len(key_slices) < 2:
            self._set_operation_feedback(tt("Interpolate fill needs the current label on at least two key slices.", self.lang))
            return False
        changed_slices = 0
        changed_pixels = 0
        undo_snapshots = []
        changed_indices = []
        for left, right in zip(key_slices, key_slices[1:]):
            span = int(right) - int(left)
            if span <= 1:
                continue
            left_dist = signed_distance(key_masks[left])
            right_dist = signed_distance(key_masks[right])
            left_rect = self._bounding_rect_for_mask(key_masks[left])
            right_rect = self._bounding_rect_for_mask(key_masks[right])
            for z_index in range(int(left) + 1, int(right)):
                ratio = float(z_index - int(left)) / float(span)
                mask = ((1.0 - ratio) * left_dist + ratio * right_dist) <= 0.0
                if int(np.count_nonzero(mask)) <= 0:
                    if left_rect is None or right_rect is None:
                        continue
                    bounds = [
                        (1.0 - ratio) * float(left_rect[idx]) + ratio * float(right_rect[idx])
                        for idx in range(4)
                    ]
                    mask = self._rect_mask_from_bounds(bounds, int(volume.shape[2]), int(volume.shape[1]))
                    if int(np.count_nonzero(mask)) <= 0:
                        continue
                current_slice = volume[z_index]
                changed_mask = mask & (current_slice != material_id)
                count = int(np.count_nonzero(changed_mask))
                if count <= 0:
                    continue
                undo_snapshots.append((int(z_index), current_slice.copy()))
                current_slice[mask] = material_id
                self._mark_edit_slice_dirty(z_index)
                changed_indices.append(int(z_index))
                changed_slices += 1
                changed_pixels += count
        if changed_slices <= 0:
            self._set_operation_feedback(tt("Interpolate fill found no missing slices between key slices.", self.lang))
            return False
        self.undo_stack.append(("multi_slice", undo_snapshots))
        if len(self.undo_stack) > 20:
            self.undo_stack.pop(0)
        self.redo_stack.clear()
        self._mark_working_edit_dirty()
        current_z = int(self.slice_slider.value())
        if current_z not in changed_indices:
            self.slice_slider.setValue(changed_indices[0])
        self.render_current_slice()
        self._sync_undo_redo_buttons()
        self._set_operation_feedback(
            tt("Interpolate filled label {0}: {1} slice(s), {2} pixel(s).", self.lang).format(material_id, changed_slices, changed_pixels),
            log=False,
        )
        return True

    def _ensure_editable_working_edit_for_helper(self):
        if not self._guard_backend_write_lock(show_message=False):
            self._set_operation_feedback(self._backend_write_lock_message())
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

    def copy_current_material_to_adjacent_slice(self, delta):
        if not self._ensure_editable_working_edit_for_helper():
            return False
        material_id = int(self.current_material_id)
        if material_id == 0:
            self._set_operation_feedback(tt("Background label 0 is not supported by this helper.", self.lang))
            return False
        source_z = int(self.slice_slider.value())
        target_z = source_z + int(delta)
        if target_z < 0:
            self._set_operation_feedback(tt("No previous slice is available.", self.lang))
            return False
        if target_z >= int(self.edit_volume.shape[0]):
            self._set_operation_feedback(tt("No next slice is available.", self.lang))
            return False
        source_mask = np.asarray(self.edit_volume[source_z] == material_id)
        source_count = int(np.count_nonzero(source_mask))
        if source_count <= 0:
            self._set_operation_feedback(tt("No pixels of label {0} on slice {1}.", self.lang).format(material_id, source_z + 1))
            return False
        reply = QMessageBox.question(
            self,
            tt("Confirm label edit", self.lang),
            tt("Copy label {0} from slice {1} to slice {2}? Existing pixels of this label on the target slice will be replaced.", self.lang).format(
                material_id,
                source_z + 1,
                target_z + 1,
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return False
        target_slice = self.edit_volume[target_z]
        next_slice = np.asarray(target_slice).copy()
        next_slice[next_slice == material_id] = 0
        next_slice[source_mask] = material_id
        changed = int(np.count_nonzero(next_slice != target_slice))
        if changed <= 0:
            self._set_operation_feedback(tt("No label changes were needed on slice {0}.", self.lang).format(target_z + 1), log=False)
            return True
        self._push_undo_for_slice(target_z)
        self.edit_volume[target_z] = next_slice
        self._mark_edit_slice_dirty(target_z)
        self._mark_working_edit_dirty()
        self.slice_slider.setValue(target_z)
        self.render_current_slice()
        message = tt("Copied label {0} from slice {1} to slice {2}: {3} changed pixel(s).", self.lang).format(
            material_id,
            source_z + 1,
            target_z + 1,
            changed,
        )
        self._set_operation_feedback(message, log=False)
        return True

    def clear_current_material_on_slice(self):
        if not self._ensure_editable_working_edit_for_helper():
            return False
        material_id = int(self.current_material_id)
        if material_id == 0:
            self._set_operation_feedback(tt("Background label 0 is not supported by this helper.", self.lang))
            return False
        z_index = int(self.slice_slider.value())
        mask = np.asarray(self.edit_volume[z_index] == material_id)
        count = int(np.count_nonzero(mask))
        if count <= 0:
            self._set_operation_feedback(tt("No pixels of label {0} on slice {1}.", self.lang).format(material_id, z_index + 1))
            return False
        reply = QMessageBox.question(
            self,
            tt("Confirm label edit", self.lang),
            tt("Clear label {0} from slice {1}?", self.lang).format(material_id, z_index + 1),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return False
        self._push_undo_for_slice(z_index)
        self.edit_volume[z_index][mask] = 0
        self._mark_edit_slice_dirty(z_index)
        self._mark_working_edit_dirty()
        self.render_current_slice()
        message = tt("Cleared label {0} on slice {1}: {2} pixel(s).", self.lang).format(material_id, z_index + 1, count)
        self._set_operation_feedback(message, log=False)
        return True

    def _sample_label_volume(self):
        if self.current_volume_scope == "part":
            if self.label_role_combo.currentData() == "editable_ai_result" and self.edit_volume is not None and self.edit_volume.shape == self.image_volume.shape:
                return self.edit_volume
            if self.label_volume is not None and self.label_volume.shape == self.image_volume.shape:
                return self.label_volume
            return None
        if self.label_role_combo.currentData() == "working_edit" and self.edit_volume is not None and self.edit_volume.shape == self.image_volume.shape:
            return self.edit_volume
        if self.label_volume is not None and self.label_volume.shape == self.image_volume.shape:
            return self.label_volume
        if self.edit_volume is not None and self.edit_volume.shape == self.image_volume.shape:
            return self.edit_volume
        return None

    def pick_material_at_widget_position(self, x, y):
        if self.image_volume is None:
            return
        if self.display_mode == "volume":
            self._set_operation_feedback(tt("3D volume preview is read-only. Switch to Slice review for label editing.", self.lang))
            return
        if self._current_slice_axis() != "z":
            self._set_operation_feedback(tt("Label picker is available on Z slices only. Switch back to Z axial view before sampling labels.", self.lang))
            return
        sample_volume = self._sample_label_volume()
        if sample_volume is None:
            self._set_operation_feedback(tt("No label layer is loaded to sample from.", self.lang))
            return
        z_index = int(self.slice_slider.value())
        height, width = self.image_volume.shape[1], self.image_volume.shape[2]
        pixel = self._widget_to_image_pixel(x, y, width, height)
        if pixel is None:
            return
        px, py = pixel
        try:
            material_id = int(np.asarray(sample_volume[z_index])[py, px])
        except Exception:
            self._set_operation_feedback(tt("No label layer is loaded to sample from.", self.lang))
            return
        self._set_current_material_id(material_id, select_row=True, show_message=True, picked=True)

    def _widget_to_image_pixel(self, x, y, image_width, image_height):
        pixel = self.canvas.widget_to_image_pixel(x, y)
        if pixel is None:
            return None
        px, py = pixel
        return max(0, min(image_width - 1, px)), max(0, min(image_height - 1, py))

    def _push_undo(self):
        if self.edit_volume is None:
            return
        if self._current_slice_axis() != "z":
            return
        z_index = int(self.slice_slider.value())
        self._push_undo_for_slice(z_index)

    def _push_undo_for_slice(self, z_index):
        if self.edit_volume is None:
            return
        z_index = int(z_index)
        if z_index < 0 or z_index >= int(self.edit_volume.shape[0]):
            return
        self.undo_stack.append((z_index, self.edit_volume[z_index].copy()))
        if len(self.undo_stack) > 20:
            self.undo_stack.pop(0)
        self.redo_stack.clear()
        self._sync_undo_redo_buttons()

    def undo(self):
        if not self._guard_backend_write_lock():
            return
        if not self.undo_stack or self.edit_volume is None:
            self._sync_undo_redo_buttons()
            return
        entry = self.undo_stack.pop()
        if isinstance(entry, tuple) and len(entry) == 2 and entry[0] == "multi_slice":
            snapshots = [(int(z_index), np.asarray(slice_array).copy()) for z_index, slice_array in (entry[1] or [])]
            redo_snapshots = []
            for z_index, old_slice in snapshots:
                if 0 <= z_index < int(self.edit_volume.shape[0]):
                    redo_snapshots.append((z_index, self.edit_volume[z_index].copy()))
                    self.edit_volume[z_index] = old_slice
                    self._mark_edit_slice_dirty(z_index)
            self.redo_stack.append(("multi_slice", redo_snapshots))
            z_index = snapshots[0][0] if snapshots else int(self.slice_slider.value())
        else:
            z_index, old_slice = entry
            z_index = int(z_index)
            self.redo_stack.append((z_index, self.edit_volume[z_index].copy()))
            self.edit_volume[z_index] = old_slice
            self._mark_edit_slice_dirty(z_index)
        if self._current_slice_axis() == "z":
            self.slice_slider.setValue(z_index)
        self._mark_working_edit_dirty()
        self.render_current_slice()
        self._sync_undo_redo_buttons()
        self._set_operation_feedback(tt("Undo restored slice {0}.", self.lang).format(z_index + 1), log=False)

    def redo(self):
        if not self._guard_backend_write_lock():
            return
        if not self.redo_stack or self.edit_volume is None:
            self._sync_undo_redo_buttons()
            return
        entry = self.redo_stack.pop()
        if isinstance(entry, tuple) and len(entry) == 2 and entry[0] == "multi_slice":
            snapshots = [(int(z_index), np.asarray(slice_array).copy()) for z_index, slice_array in (entry[1] or [])]
            undo_snapshots = []
            for z_index, redo_slice in snapshots:
                if 0 <= z_index < int(self.edit_volume.shape[0]):
                    undo_snapshots.append((z_index, self.edit_volume[z_index].copy()))
                    self.edit_volume[z_index] = redo_slice
                    self._mark_edit_slice_dirty(z_index)
            self.undo_stack.append(("multi_slice", undo_snapshots))
            z_index = snapshots[0][0] if snapshots else int(self.slice_slider.value())
        else:
            z_index, redo_slice = entry
            z_index = int(z_index)
            self.undo_stack.append((z_index, self.edit_volume[z_index].copy()))
            self.edit_volume[z_index] = redo_slice
            self._mark_edit_slice_dirty(z_index)
        if self._current_slice_axis() == "z":
            self.slice_slider.setValue(z_index)
        self._mark_working_edit_dirty()
        self.render_current_slice()
        self._sync_undo_redo_buttons()
        self._set_operation_feedback(tt("Redo restored slice {0}.", self.lang).format(z_index + 1), log=False)

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
            reslice = self._current_part_reslice_record()
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
            edit_path = self._current_part_label_path("editable_ai_result")
            self.edit_volume = load_volume_sidecar(edit_path, mmap_mode="c") if edit_path else self.edit_volume
            if self.label_role_combo.currentData() == "editable_ai_result" and edit_path:
                self.label_volume = load_volume_sidecar(edit_path, mmap_mode="r")
            else:
                self._reload_label_volume()
            self._update_status_labels(specimen, part=part)
            self._update_ai_review_check_label()
        return True

    def save_working_edit(self, show_message=True, reason="manual"):
        if not self._guard_backend_write_lock(show_message=show_message):
            return False
        if self._saving_working_edit:
            return True
        if reason == "auto_save":
            return self._start_label_auto_save(reason=reason)
        self._wait_for_label_auto_save()
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
            self.working_edit_dirty = False
            self._reset_edit_dirty_tracking()
            self._finalize_full_edit_save_metadata(metadata, refresh_volumes=True)
            self._update_save_status()
        except Exception as exc:
            self.working_edit_dirty = True
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
        edit_path = self._current_part_label_path("editable_ai_result")
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
            self.working_edit_dirty = False
            self._reset_edit_dirty_tracking()
            self._finalize_part_editable_save_metadata(metadata, refresh_volumes=True)
            self._update_save_status()
        except Exception as exc:
            self.working_edit_dirty = True
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

    def _save_part_mask_edit(self, show_message=True, reason="manual"):
        if not self._is_editable_part_volume():
            return False
        specimen = self.project.get_specimen(self.current_specimen_id, default=None)
        part = self.project.get_part(self.current_specimen_id, self.current_part_id, default=None)
        if specimen is None or part is None or self.edit_volume is None:
            return False
        mask_path = self._current_part_mask_path()
        if not mask_path:
            return False
        self._saving_working_edit = True
        self.auto_save_timer.stop()
        self._update_save_status(state="saving")
        try:
            target = load_volume_sidecar(mask_path, mmap_mode="r+")
            if self._dirty_edit_slices:
                for z_index in sorted(self._dirty_edit_slices):
                    if 0 <= int(z_index) < int(target.shape[0]):
                        target[int(z_index)] = self.edit_volume[int(z_index)]
            metadata = flush_volume_array(mask_path, target)
            mask_record = part.setdefault("mask", {})
            mask_record["dtype"] = metadata["dtype"]
            mask_record["shape_zyx"] = metadata["shape_zyx"]
            mask_record["spacing_zyx"] = metadata.get("spacing_zyx", mask_record.get("spacing_zyx", [1.0, 1.0, 1.0]))
            mask_record["spacing_unit"] = metadata.get("spacing_unit", mask_record.get("spacing_unit", "micrometer"))
            mask_record["orientation"] = metadata.get("orientation", mask_record.get("orientation", "unknown"))
            mask_record["format"] = metadata.get("format", mask_record.get("format", ""))
            mask_record["status"] = "in_progress"
            part["status"] = "mask_in_progress"
            self.project.save_project()
            self.working_edit_dirty = False
            self._reset_edit_dirty_tracking()
            self.edit_volume = load_volume_sidecar(mask_path, mmap_mode="c")
            self.part_mask_volume = load_volume_sidecar(mask_path, mmap_mode="r")
            self._reload_label_volume()
            self._update_status_labels(specimen, part=part)
            self._update_save_status()
        except Exception as exc:
            self.working_edit_dirty = True
            message = tt("Save failed: {0}", self.lang).format(str(exc))
            self._set_operation_feedback(message)
            self._update_save_status(state="failed", detail=str(exc))
            QMessageBox.warning(self, tt("Unsaved working edit", self.lang), str(exc))
            return False
        finally:
            self._saving_working_edit = False
            self._update_save_status()
        if show_message:
            message = tt("Auto-saved part mask.", self.lang) if reason == "auto_save" else tt("Part mask saved.", self.lang)
            self._set_operation_feedback(message)
        return True

    def _current_promote_request(self):
        if not self.current_specimen_id:
            return {}
        return {
            "scope": "part" if self.current_volume_scope == "part" else "full",
            "specimen_id": str(self.current_specimen_id or ""),
            "part_id": str(self.current_part_id or ""),
            "reslice_id": str(self.current_reslice_id or ""),
        }

    def _begin_promote_working_edit_async(self, request):
        request = dict(request or {})
        if not request.get("specimen_id"):
            return False
        if self._promote_running():
            return False
        task = self._start_tif_task(
            "truth_promotion",
            action="promote_working_edit",
            payload={"request": dict(request or {})},
            request_key=self._task_request_key((
                request.get("specimen_id", ""),
                request.get("scope", ""),
                request.get("part_id", ""),
                request.get("reslice_id", ""),
            )),
            message=tt("Training truth acceptance is running. Wait until it finishes before editing project data.", self.lang),
        )
        self._promote_task_id = task.task_id
        thread = QThread(self)
        worker = TifPromoteWorkingEditWorker(self.project, request)
        worker.moveToThread(thread)
        self._promote_thread = thread
        self._promote_worker = worker
        self._promote_request = request
        self._set_operation_feedback(tt("Accepting training truth in background...", self.lang))
        self._set_scope_controls_enabled()
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_promote_working_edit_finished)
        worker.failed.connect(self._on_promote_working_edit_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.start()
        return True

    def _cleanup_promote_thread(self):
        self._promote_thread = None
        self._promote_worker = None
        self._promote_request = {}
        self._promote_task_id = ""
        self._set_scope_controls_enabled()

    def _on_promote_working_edit_finished(self, result):
        result = dict(result or {})
        task_id = self._promote_task_id
        task_current = self._task_context_matches_current(task_id, fields=("specimen_id", "volume_scope", "part_id", "reslice_id"))
        self._finish_tif_task(task_id, payload=result, message="truth_promotion_finished")
        self._cleanup_promote_thread()
        self.refresh_project()
        specimen_id = str(result.get("specimen_id") or "")
        part_id = str(result.get("part_id") or "")
        reslice_id = str(result.get("reslice_id") or "")
        if specimen_id and part_id and task_current:
            self._select_volume_tree_item(specimen_id, "part_reslice" if reslice_id else "part", part_id, reslice_id)
        elif specimen_id and task_current:
            self._select_volume_tree_item(specimen_id, "full")
        if task_current:
            self._reload_label_volume()
        specimen = self.project.get_specimen(self.current_specimen_id, default=None) if self.current_specimen_id else None
        if specimen is not None:
            self._update_status_labels(specimen, part=self.current_part if self.current_volume_scope == "part" else None)
        self._update_ai_review_check_label()
        if task_current:
            self._set_operation_feedback(tt("Accepted current labels as training truth.", self.lang))
        else:
            self._set_operation_feedback(tt("Accepted labels as training truth; current view was left unchanged because you switched context while it was running.", self.lang))

    def _on_promote_working_edit_failed(self, result):
        result = dict(result or {})
        task_id = self._promote_task_id
        task_current = self._task_context_matches_current(task_id, fields=("specimen_id", "volume_scope", "part_id", "reslice_id"))
        message = str(result.get("error", ""))
        self._fail_tif_task(task_id, message, payload=result)
        self._cleanup_promote_thread()
        if task_current:
            self._set_operation_feedback(tt("Action failed: {0}", self.lang).format(message))
            QMessageBox.warning(self, tt("Accept working edit", self.lang), message)

    def promote_working_edit(self):
        if not self._guard_backend_write_lock():
            return False
        if not self.current_specimen_id:
            return False
        if self.current_volume_scope == "part":
            if not self.current_part_id:
                return False
            reply = QMessageBox.question(
                self,
                tt("Accept working edit", self.lang),
                tt("Promote the reviewed editable AI result to part-level training truth?", self.lang),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return False
            request = self._current_promote_request()
            if self.working_edit_dirty:
                return self.save_working_edit_async(promote_request=request)
            return self._begin_promote_working_edit_async(request)
        reply = QMessageBox.question(
            self,
            tt("Accept working edit", self.lang),
            tt("Promote the current working_edit layer to training truth?", self.lang),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return False
        request = self._current_promote_request()
        if self.working_edit_dirty:
            return self.save_working_edit_async(promote_request=request)
        return self._begin_promote_working_edit_async(request)

    def copy_latest_model_draft_to_working_edit(self):
        if not self._guard_backend_write_lock():
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
        if not self._guard_backend_write_lock():
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

    def export_current_part_package(self):
        if not self._guard_backend_write_lock():
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
        label = self._safe_export_name_fragment(self._result_region_name(), "")
        suffix = f"_{label}" if label else ""
        return self._safe_export_name_fragment(f"region_{value}{suffix}", "region")

    def _current_rendering_screenshot_metadata(self, image_path, sidecar_path):
        selected_row = self._selected_result_comparison_row() if hasattr(self, "result_compare_table") else {}
        active_part = self.project.get_part(self.current_specimen_id, self.current_part_id, default=None) if self.current_specimen_id and self.current_part_id else None
        training = (active_part or {}).get("training") or {}
        label_role = self._result_source_role() if hasattr(self, "result_source_manual_radio") else (self.label_role_combo.currentData() if hasattr(self, "label_role_combo") else "")
        label_record = self._current_part_label_record(label_role) if self.current_volume_scope == "part" and label_role else {}
        target = self.volume_canvas if self.display_mode == "volume" else self.canvas
        region_id = self._result_region_id() if hasattr(self, "result_region_combo") else 0
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
            "region_name": self._result_region_name() if region_id > 0 else tt("All", self.lang),
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

    def _default_local_axis_reslice_id(self):
        return self.local_axis_controller.default_reslice_id()

    def _current_local_axis_reslice_payload(self):
        return self.local_axis_controller.current_reslice_payload()

    def export_current_local_axis_reslice(self):
        if not self._guard_backend_write_lock():
            return None
        source_specimen_id = self.current_specimen_id
        source_part_id = self.current_part_id
        if self._local_axis_reslice_export_running():
            QMessageBox.information(
                self,
                tt("Local Axis Reslice", self.lang),
                tt("Local Axis Reslice export is already running.", self.lang),
            )
            return None
        try:
            payload = self._current_local_axis_reslice_payload()
        except Exception as exc:
            message = str(exc)
            self._set_local_axis_status(message)
            self.log(message)
            QMessageBox.warning(self, tt("Local Axis Reslice", self.lang), message)
            return None

        progress = QProgressDialog(
            tt("Exporting confirmed Local Axis Reslice...", self.lang),
            "",
            0,
            0,
            self,
        )
        progress.setWindowTitle(tt("Local Axis Reslice", self.lang))
        progress.setCancelButton(None)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setMinimumDuration(0)
        progress.setWindowModality(Qt.WindowModal)
        progress.show()

        thread = QThread(self)
        worker = TifLocalAxisResliceExportWorker(self.project, source_specimen_id, source_part_id, payload)
        worker.moveToThread(thread)
        self._local_axis_reslice_export_thread = thread
        self._local_axis_reslice_export_worker = worker
        self._local_axis_reslice_export_progress = progress
        self._local_axis_reslice_export_context = {
            "specimen_id": source_specimen_id,
            "part_id": source_part_id,
        }
        task = self._start_tif_task(
            "local_axis_export",
            action="export_local_axis_reslice",
            payload={
                "specimen_id": source_specimen_id,
                "part_id": source_part_id,
                "reslice_id": payload.get("reslice_id", ""),
            },
            request_key=self._task_request_key((source_specimen_id, source_part_id, payload.get("reslice_id", ""))),
            message=tt("Local Axis Reslice export is running. Wait until it finishes before editing project data.", self.lang),
        )
        self._local_axis_reslice_export_task_id = task.task_id
        self._set_local_axis_reslice_export_controls_enabled(False)

        thread.started.connect(worker.run)
        worker.progress.connect(self._on_local_axis_reslice_export_progress)
        worker.finished.connect(self._on_local_axis_reslice_export_finished)
        worker.failed.connect(self._on_local_axis_reslice_export_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        thread.start()
        self.training_status_label.setText(tt("Exporting confirmed Local Axis Reslice...", self.lang))
        return {
            "status": "running",
            "specimen_id": source_specimen_id,
            "part_id": source_part_id,
            "reslice_id": payload.get("reslice_id", ""),
        }

    def export_local_axis_training_manifest_dialog(self):
        if not self._ensure_tif_project_open():
            return None
        default_dir = os.path.join(self.project.project_dir, "exports", "local_axis_training")
        os.makedirs(default_dir, exist_ok=True)
        output_dir = QFileDialog.getExistingDirectory(self, tt("Export Local Axis training manifest", self.lang), default_dir)
        if not output_dir:
            return None
        request = self.local_axis_service.build_manifest_export_request(
            self.project,
            output_dir,
            template_id=self.current_part_id if self.current_volume_scope == "part" else "",
        )
        if not request:
            QMessageBox.warning(self, tt("Local Axis data", self.lang), request.message or ", ".join(request.reasons or []))
            return None
        filters = request.payload.get("filters", {})
        output_dir = request.payload.get("output_dir", output_dir)
        try:
            result = export_local_axis_training_manifest(self.project, output_dir, filters)
        except Exception as exc:
            QMessageBox.warning(self, tt("Local Axis data", self.lang), str(exc))
            return None
        message = tt("Exported Local Axis training manifest: {0} samples\n{1}", self.lang).format(
            result.get("sample_count", 0),
            result.get("manifest_path", ""),
        )
        self.training_status_label.setText(message)
        self._set_local_axis_status(message)
        self.log(message)
        return result

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
