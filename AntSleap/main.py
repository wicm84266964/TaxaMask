import sys
import os

try:
    from AntSleap.app_runtime import (
        _append_env_flag,
        _ensure_qtwebengine_quiet_cpu_flags,
        _is_wsl_runtime,
        _prepare_qt_runtime_environment,
        _runtime_log_enabled,
        _runtime_log_filename_timestamp,
        _runtime_log_prune,
        _runtime_log_timestamp,
        _runtime_log_value,
        _setup_runtime_logging,
        runtime_log_event,
        runtime_log_exception,
    )
except ImportError:
    from app_runtime import (
        _append_env_flag,
        _ensure_qtwebengine_quiet_cpu_flags,
        _is_wsl_runtime,
        _prepare_qt_runtime_environment,
        _runtime_log_enabled,
        _runtime_log_filename_timestamp,
        _runtime_log_prune,
        _runtime_log_timestamp,
        _runtime_log_value,
        _setup_runtime_logging,
        runtime_log_event,
        runtime_log_exception,
    )


_prepare_qt_runtime_environment()
import csv
import json
import re
import threading
import time
import cv2
from fractions import Fraction

# pyright: reportMissingImports=false, reportGeneralTypeIssues=false, reportAttributeAccessIssue=false, reportArgumentType=false, reportCallIssue=false, reportOptionalMemberAccess=false, reportOptionalCall=false, reportUninitializedInstanceVariable=false, reportOperatorIssue=false

# Disable Ultralytics checks BEFORE importing it
os.environ["YOLO_VERBOSE"] = "False"
os.environ["ULTRALYTICS_QUIET"] = "True"


_ensure_qtwebengine_quiet_cpu_flags()

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(PACKAGE_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

if __name__ == "__main__":
    _setup_runtime_logging()

    def _early_runtime_excepthook(exc_type, exc_value, exc_tb):
        runtime_log_exception("uncaught_exception", exc_type, exc_value, exc_tb)
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _early_runtime_excepthook

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QPushButton, QLabel, QFileDialog, QTextEdit,
    QComboBox, QMessageBox, QSplitter, QProgressBar, QProgressDialog, QDialog,
    QLineEdit, QScrollArea, QRadioButton, QButtonGroup, QSlider,
    QCheckBox, QInputDialog, QGroupBox, QListWidgetItem, QMenu,
    QDialogButtonBox, QGridLayout, QSizePolicy, QFrame, QFormLayout,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QSpinBox, QToolButton,
    QAbstractItemView, QTreeWidget, QTreeWidgetItem)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSize, QEvent
from PySide6.QtGui import QIcon, QAction, QColor
import numpy as np
import torch
from PIL import Image as PILImage

try:
    from AntSleap.core.project import (
        AUTO_BOX_REVIEW_CONFIRMED,
        AUTO_BOX_REVIEW_DRAFT,
        AUTO_BOX_SOURCE_EXTERNAL_MODEL,
        AUTO_BOX_SOURCE_MODEL,
        AUTO_BOX_SOURCE_VLM,
        ProjectManager,
    )
    from AntSleap.core.database import MultiModalDB
    from AntSleap.core.engine import AntEngine
    from AntSleap.core.sam_helper import SAMWorker
    from AntSleap.core.config import ConfigManager
    from AntSleap.core.window_geometry import compute_centered_window_geometry
    from AntSleap.ui.canvas import AnnotationCanvas
    from AntSleap.ui.style import (
        SCI_THEME,
        LIGHT_THEME,
        BUTTON_ROLE_COMMIT,
        BUTTON_ROLE_DESTRUCTIVE,
        BUTTON_ROLE_NEUTRAL,
        BUTTON_ROLE_RUN,
        BUTTON_ROLE_STOP,
        SURFACE_ROLE_CANVAS,
        SURFACE_ROLE_PANEL,
        SURFACE_ROLE_RAISED,
        SURFACE_ROLE_SUBTLE,
        SURFACE_ROLE_TOOLBAR,
        apply_theme_dialog_button_box_style,
        apply_theme_button_style,
        apply_semantic_button_style,
        apply_surface_role,
        build_theme_palette,
        get_theme_config,
        get_theme_stylesheet,
        normalize_theme,
        refresh_themed_buttons,
        register_windows_scholarly_ui_fonts,
        themed_yes_no_question,
    )
    from AntSleap.ui.cropper import ImageCropper
    from AntSleap.ui.pdf_processing_widget import PdfProcessingWidget
    from AntSleap.ui.blink_lab import BlinkExpertTrainingReportDialog, BlinkLabWidget
    from AntSleap.ui.tif_workbench import TifWorkbenchWidget
    from AntSleap.ui.taxamask_agent_panel import TaxaMaskAgentPanel
    from AntSleap.core.training_preflight import build_training_preflight, describe_training_preflight, describe_part_coverage, format_size_pair
    from AntSleap.core.cascade_routes import (
        ROUTE_BACKEND_EXTERNAL_BLINK,
        ROUTE_BACKEND_HEATMAP_BLINK,
        ROUTE_BACKEND_VIT_B_BLINK,
        format_expert_label,
        get_route_appointed_expert,
        get_route_persisted_expert_candidates,
        merge_expert_candidates,
    )
    from AntSleap.core.expert_notes import format_expert_display_name, load_expert_notes, set_expert_note
    from AntSleap.core.parent_model_notes import (
        format_parent_model_display_name,
        load_parent_model_notes,
        set_parent_model_note,
    )
    from AntSleap.core.model_profiles import (
        CHILD_BACKEND_EXTERNAL,
        CHILD_BACKEND_HEATMAP,
        CHILD_BACKEND_VIT_B,
        DEFAULT_EXTERNAL_BLINK_BACKEND,
        DEFAULT_CHILD_AUTO_SHRINK_STEPS,
        DEFAULT_HEATMAP_BLINK_PARAMS,
        DEFAULT_MODEL_PROFILE_ID,
        DEFAULT_VLM_IMAGE_GROUP,
        PARENT_BACKEND_BUILTIN,
        PARENT_BACKEND_EXTERNAL,
        sanitize_model_profiles,
    )
    from AntSleap.core.blink_training_strategy import (
        BLINK_STRATEGY_FULL_INSIDE_RANDOM,
        BLINK_STRATEGY_TRIVIEW_RANDOM,
        BLINK_STRATEGY_TWO_STAGE_FULL_THEN_INSIDE,
        DEFAULT_BLINK_TRAINING_STRATEGY,
        blink_training_strategy_label,
        blink_training_strategy_note,
        sanitize_blink_training_strategy,
    )
    from AntSleap.core.project_templates import DEFAULT_PROJECT_TEMPLATE_ID, iter_project_templates
    from AntSleap.core.external_backend import BUILTIN_BACKEND_ID, EXTERNAL_BACKEND_ID, ExternalBackendRunner, sanitize_external_backend_config
    from AntSleap.core.tif_backend import DEFAULT_TIF_BACKEND_CONFIG, nnunet_v2_tif_backend_preset, sanitize_tif_backend_config
    from AntSleap.core.tif_export import SUPPORTED_TIF_EXPORT_FORMATS
    from AntSleap.core.tif_project import TIF_PROJECT_SCHEMA_VERSION, TIF_PROJECT_TYPE, TifProjectManager
    from AntSleap.core.stl_project import STL_PROJECT_SCHEMA_VERSION, STL_PROJECT_TYPE, StlRenderedProjectManager
    from AntSleap.core.stl_review_bridge import import_stl_rendered_views_into_2d_project, register_stl_rendered_views_for_2d_review
    from AntSleap.core.tif_stack_import import import_tif_stack
    from AntSleap.core.amira_import import import_amira_directory
    from AntSleap.core.part_tree import build_part_tree_groups
    from AntSleap.core.platform_open import open_path
    from AntSleap.core.runtime_device import normalize_device_preference, resolve_torch_device
    from AntSleap.core.agent_context_routes import enrich_agent_context
    from AntSleap.core.vlm_preannotation import (
        DEFAULT_VLM_PROMPT_PROFILE_ID,
        default_vlm_prompt_profile,
        load_vlm_api_config_from_runtime_settings,
        sanitize_vlm_prompt_profile,
    )
    from AntSleap.core.project_sqlite_migration import default_sqlite_manifest_path, migrate_legacy_2d_json_to_sqlite
    from AntSleap.core.project_sqlite_maintenance import (
        backup_sqlite_project_manifest,
        export_sqlite_project_to_legacy_json,
        sqlite_project_migration_report_path,
    )
    from AntSleap.core.project_sqlite_writer import finish_vlm_run, record_vlm_image_result
    from AntSleap.core.sqlite_storage import PROJECT_MANIFEST_SCHEMA_VERSION, SQLITE_BACKEND, read_project_manifest, resolve_manifest_database_path
    from AntSleap.core.tif_sqlite_migration import (
        default_tif_sqlite_manifest_path,
        migrate_legacy_tif_json_to_sqlite,
    )
    from AntSleap.core.literature_descriptions import (
        build_text_block_source,
        build_description_source,
        candidate_literature_db_paths,
        default_literature_db_path,
        infer_literature_db_path_from_artifact_image,
        query_literature_part_descriptions,
        query_literature_text_blocks,
        resolve_literature_context,
    )
except ImportError:
    from core.project import (
        AUTO_BOX_REVIEW_CONFIRMED,
        AUTO_BOX_REVIEW_DRAFT,
        AUTO_BOX_SOURCE_EXTERNAL_MODEL,
        AUTO_BOX_SOURCE_MODEL,
        AUTO_BOX_SOURCE_VLM,
        ProjectManager,
    )
    from core.database import MultiModalDB
    from core.engine import AntEngine
    from core.sam_helper import SAMWorker
    from core.config import ConfigManager
    from core.window_geometry import compute_centered_window_geometry
    from ui.canvas import AnnotationCanvas
    from ui.style import (
        SCI_THEME,
        LIGHT_THEME,
        BUTTON_ROLE_COMMIT,
        BUTTON_ROLE_DESTRUCTIVE,
        BUTTON_ROLE_NEUTRAL,
        BUTTON_ROLE_RUN,
        BUTTON_ROLE_STOP,
        SURFACE_ROLE_CANVAS,
        SURFACE_ROLE_PANEL,
        SURFACE_ROLE_RAISED,
        SURFACE_ROLE_SUBTLE,
        SURFACE_ROLE_TOOLBAR,
        apply_theme_dialog_button_box_style,
        apply_theme_button_style,
        apply_semantic_button_style,
        apply_surface_role,
        build_theme_palette,
        get_theme_config,
        get_theme_stylesheet,
        normalize_theme,
        refresh_themed_buttons,
        register_windows_scholarly_ui_fonts,
        themed_yes_no_question,
    )
    from ui.cropper import ImageCropper
    from ui.pdf_processing_widget import PdfProcessingWidget
    from ui.blink_lab import BlinkExpertTrainingReportDialog, BlinkLabWidget
    from ui.tif_workbench import TifWorkbenchWidget
    from ui.taxamask_agent_panel import TaxaMaskAgentPanel
    from core.training_preflight import build_training_preflight, describe_training_preflight, describe_part_coverage, format_size_pair
    from core.cascade_routes import (
        ROUTE_BACKEND_EXTERNAL_BLINK,
        ROUTE_BACKEND_HEATMAP_BLINK,
        ROUTE_BACKEND_VIT_B_BLINK,
        format_expert_label,
        get_route_appointed_expert,
        get_route_persisted_expert_candidates,
        merge_expert_candidates,
    )
    from core.expert_notes import format_expert_display_name, load_expert_notes, set_expert_note
    from core.parent_model_notes import (
        format_parent_model_display_name,
        load_parent_model_notes,
        set_parent_model_note,
    )
    from core.model_profiles import (
        CHILD_BACKEND_EXTERNAL,
        CHILD_BACKEND_HEATMAP,
        CHILD_BACKEND_VIT_B,
        DEFAULT_EXTERNAL_BLINK_BACKEND,
        DEFAULT_CHILD_AUTO_SHRINK_STEPS,
        DEFAULT_HEATMAP_BLINK_PARAMS,
        DEFAULT_MODEL_PROFILE_ID,
        DEFAULT_VLM_IMAGE_GROUP,
        PARENT_BACKEND_BUILTIN,
        PARENT_BACKEND_EXTERNAL,
        sanitize_model_profiles,
    )
    from core.blink_training_strategy import (
        BLINK_STRATEGY_FULL_INSIDE_RANDOM,
        BLINK_STRATEGY_TRIVIEW_RANDOM,
        BLINK_STRATEGY_TWO_STAGE_FULL_THEN_INSIDE,
        DEFAULT_BLINK_TRAINING_STRATEGY,
        blink_training_strategy_label,
        blink_training_strategy_note,
        sanitize_blink_training_strategy,
    )
    from core.project_templates import DEFAULT_PROJECT_TEMPLATE_ID, iter_project_templates
    from core.external_backend import BUILTIN_BACKEND_ID, EXTERNAL_BACKEND_ID, ExternalBackendRunner, sanitize_external_backend_config
    from core.tif_backend import DEFAULT_TIF_BACKEND_CONFIG, nnunet_v2_tif_backend_preset, sanitize_tif_backend_config
    from core.tif_export import SUPPORTED_TIF_EXPORT_FORMATS
    from core.tif_project import TIF_PROJECT_SCHEMA_VERSION, TIF_PROJECT_TYPE, TifProjectManager
    from core.stl_project import STL_PROJECT_SCHEMA_VERSION, STL_PROJECT_TYPE, StlRenderedProjectManager
    from core.stl_review_bridge import import_stl_rendered_views_into_2d_project, register_stl_rendered_views_for_2d_review
    from core.tif_stack_import import import_tif_stack
    from core.amira_import import import_amira_directory
    from core.part_tree import build_part_tree_groups
    from core.platform_open import open_path
    from core.runtime_device import normalize_device_preference, resolve_torch_device
    from core.agent_context_routes import enrich_agent_context
    from core.vlm_preannotation import (
        DEFAULT_VLM_PROMPT_PROFILE_ID,
        default_vlm_prompt_profile,
        load_vlm_api_config_from_runtime_settings,
        sanitize_vlm_prompt_profile,
    )
    from core.project_sqlite_migration import default_sqlite_manifest_path, migrate_legacy_2d_json_to_sqlite
    from core.project_sqlite_maintenance import (
        backup_sqlite_project_manifest,
        export_sqlite_project_to_legacy_json,
        sqlite_project_migration_report_path,
    )
    from core.project_sqlite_writer import finish_vlm_run, record_vlm_image_result
    from core.sqlite_storage import PROJECT_MANIFEST_SCHEMA_VERSION, SQLITE_BACKEND, read_project_manifest, resolve_manifest_database_path
    from core.tif_sqlite_migration import (
        default_tif_sqlite_manifest_path,
        migrate_legacy_tif_json_to_sqlite,
    )
    from core.literature_descriptions import (
        build_text_block_source,
        build_description_source,
        candidate_literature_db_paths,
        default_literature_db_path,
        infer_literature_db_path_from_artifact_image,
        query_literature_part_descriptions,
        query_literature_text_blocks,
        resolve_literature_context,
    )

try:
    from AntSleap.core.panel_splitter import detect_panel_crops
except ImportError:
    from core.panel_splitter import detect_panel_crops

try:
    from AntSleap.ui.main_window_widgets import ImageGroupListWidget, NoWheelComboBox, NoWheelSlider, NoWheelSpinBox
    from AntSleap.ui.main_window_workers import (
        DatasetExportThread,
        ExternalBatchInferenceThread,
        ExternalTrainingThread,
        ImageImportThread,
        InferenceThread,
        TrainingThread,
        VlmPreannotationThread,
    )
except ImportError:
    from ui.main_window_widgets import ImageGroupListWidget, NoWheelComboBox, NoWheelSlider, NoWheelSpinBox
    from ui.main_window_workers import (
        DatasetExportThread,
        ExternalBatchInferenceThread,
        ExternalTrainingThread,
        ImageImportThread,
        InferenceThread,
        TrainingThread,
        VlmPreannotationThread,
    )

try:
    from AntSleap.ui.main_window_i18n import SECTION_TRANSLATIONS, TRANSLATIONS, tr, ui_text
    from AntSleap.ui.main_window_dialog_support import (
        APP_ICON_FALLBACK_PATH,
        APP_ICON_PATH,
        BACKGROUND_IMAGE_IMPORT_THRESHOLD,
        BRAND_ASSETS_DIR,
        DEFAULT_2D_STL_PROJECTS_DIR_NAME,
        DEFAULT_OUTPUTS_DIR_NAME,
        DEFAULT_PROJECT_NAME,
        DEFAULT_STARTUP_PROJECT_DIR_NAME,
        DEFAULT_TIF_PROJECTS_DIR_NAME,
        EXPERIMENTAL_TIF_WORKFLOW_ENV,
        LARGE_PROJECT_OPEN_LIGHTWEIGHT_THRESHOLD,
        WORKBENCH_WINDOW_TITLE,
        _active_profile_from_manager,
        _agent_command_has_contract,
        _agent_error_summary,
        _agent_yes_no,
        _blink_preferred_roi_parts,
        _child_backend_label,
        _clean_box,
        _compact_path_text,
        _env_flag_enabled,
        _format_backend_contract_error,
        _parent_backend_label,
        _route_backend_from_child_backend,
        _route_backend_from_entry,
        _route_backend_label,
        _route_manifest_from_entry,
        _runtime_child_backend_defaults,
        _runtime_parent_backend,
        _translate_route_registration_source,
        _translate_training_warning_text,
        _translate_validation_provenance,
        _yes_no_text,
    )
except ImportError:
    from ui.main_window_i18n import SECTION_TRANSLATIONS, TRANSLATIONS, tr, ui_text
    from ui.main_window_dialog_support import (
        APP_ICON_FALLBACK_PATH,
        APP_ICON_PATH,
        BACKGROUND_IMAGE_IMPORT_THRESHOLD,
        BRAND_ASSETS_DIR,
        DEFAULT_2D_STL_PROJECTS_DIR_NAME,
        DEFAULT_OUTPUTS_DIR_NAME,
        DEFAULT_PROJECT_NAME,
        DEFAULT_STARTUP_PROJECT_DIR_NAME,
        DEFAULT_TIF_PROJECTS_DIR_NAME,
        EXPERIMENTAL_TIF_WORKFLOW_ENV,
        LARGE_PROJECT_OPEN_LIGHTWEIGHT_THRESHOLD,
        WORKBENCH_WINDOW_TITLE,
        _active_profile_from_manager,
        _agent_command_has_contract,
        _agent_error_summary,
        _agent_yes_no,
        _blink_preferred_roi_parts,
        _child_backend_label,
        _clean_box,
        _compact_path_text,
        _env_flag_enabled,
        _format_backend_contract_error,
        _parent_backend_label,
        _route_backend_from_child_backend,
        _route_backend_from_entry,
        _route_backend_label,
        _route_manifest_from_entry,
        _runtime_child_backend_defaults,
        _runtime_parent_backend,
        _translate_route_registration_source,
        _translate_training_warning_text,
        _translate_validation_provenance,
        _yes_no_text,
    )



try:
    from AntSleap.ui.training_report_dialogs import (
        TrainingPreflightDialog,
        TrainingReportDialog,
        TrainingResultBrowserDialog,
    )
except ImportError:
    from ui.training_report_dialogs import (
        TrainingPreflightDialog,
        TrainingReportDialog,
        TrainingResultBrowserDialog,
    )


try:
    from AntSleap.ui.route_management_panel import RouteManagementPanel
except ImportError:
    from ui.route_management_panel import RouteManagementPanel


try:
    from AntSleap.ui.model_settings_dialog import ModelSettingsDialog
except ImportError:
    from ui.model_settings_dialog import ModelSettingsDialog


try:
    from AntSleap.ui.settings_dialogs import GeneralSettingsDialog, TifModelSettingsDialog
except ImportError:
    from ui.settings_dialogs import GeneralSettingsDialog, TifModelSettingsDialog


try:
    from AntSleap.ui.main_window_dialogs import BlinkEntryDialog, ExportDialog, LiteratureDescriptionDialog
except ImportError:
    from ui.main_window_dialogs import BlinkEntryDialog, ExportDialog, LiteratureDescriptionDialog


class MainWindow(QMainWindow):
    sam_point_requested = Signal(str, float, float)
    sam_box_requested = Signal(str, float, float, float, float)

    def __init__(self):
        super().__init__()
        self._apply_window_icon()
        self.startup_size = QSize(1480, 920)
        self.resize(self.startup_size)
        self.config = ConfigManager()
        self.current_lang = self.config.get("language", "en")
        self.current_theme = normalize_theme(self.config.get("theme", "dark"))
        if self.config.get("theme", "dark") != self.current_theme:
            self.config.set("theme", self.current_theme)
        self.tif_workflow_enabled = _env_flag_enabled(EXPERIMENTAL_TIF_WORKFLOW_ENV)
        self.project = ProjectManager()
        self.project.set_known_relocated_roots(self.config.get("known_relocated_roots", []))
        self.tif_project = TifProjectManager()
        self.stl_project = StlRenderedProjectManager()
        self.active_project_kind = "image"
        self.active_project_source_kind = "image"
        self.active_project_entry_path = ""
        self.db = MultiModalDB()
        
        self.train_epochs = self.config.get("train_epochs", 5)
        self.train_batch = self.config.get("train_batch", 4)
        self.blink_train_epochs = self.config.get("blink_train_epochs", 5)
        self.blink_train_batch = self.config.get("blink_train_batch", 2)
        self.blink_train_lr = self.config.get("blink_train_lr", 1e-3)
        self.blink_train_weight_decay = self.config.get("blink_train_weight_decay", 1e-4)
        self.blink_train_input_size = self.config.get("blink_train_input_size", 224)
        self.blink_auto_shrink_steps = int(self.config.get("blink_auto_shrink_steps", DEFAULT_CHILD_AUTO_SHRINK_STEPS) or DEFAULT_CHILD_AUTO_SHRINK_STEPS)
        self.blink_training_strategy = sanitize_blink_training_strategy(
            self.config.get("blink_training_strategy", DEFAULT_BLINK_TRAINING_STRATEGY)
        )
        self.train_lr = self.config.get("train_lr", 1e-4)
        self.train_wd = self.config.get("train_weight_decay", 1e-4)
        self.runtime_device = normalize_device_preference(self.config.get("runtime_device", "auto"))
        self.model_backend = self.config.get("model_backend", BUILTIN_BACKEND_ID)
        self.external_backend_config = sanitize_external_backend_config(self.config.get("external_backend", {}))
        self.inf_conf = self.config.get("inf_conf_thresh", 0.1)
        self.inf_adapt = self.config.get("inf_adapt_thresh", 0.4)
        self.inf_pad = self.config.get("inf_box_pad", 0.4)
        self.inf_noise_floor = self.config.get("inf_noise_floor", 0.15)
        self.inf_poly_epsilon = self.config.get("inf_poly_epsilon", 2.0)
        self.engine = AntEngine(
            learning_rate=self.train_lr,
            weight_decay=self.train_wd,
            num_classes=len(self.project.get_locator_scope()),
            device=self.runtime_device,
        )
        self.current_image = None
        self.inf_thread = None
        self.sam_thread = None
        self.sam_worker = None
        self.sam_busy = False
        self.pending_sam_part = None
        self.pending_sam_image = None
        self.pending_sam_description = ""
        self.image_import_thread = None
        self.image_import_progress_dialog = None
        self.external_batch_inference_thread = None
        self.external_batch_inference_progress_dialog = None
        self.external_batch_inference_failed = False
        self.external_batch_inference_saved_any = False
        self.external_training_thread = None
        self.external_training_failed = False
        self.trainer = None
        self.locator_preload_thread = None
        self.parts_model_preload_thread = None
        try:
            autosave_seconds = int(float(self.config.get("project_autosave_interval_sec", 3)))
        except Exception:
            autosave_seconds = 3
        self.project_autosave_delay_ms = max(1, autosave_seconds) * 1000
        self.project_save_navigation_idle_ms = max(1200, min(5000, self.project_autosave_delay_ms))
        self.project_last_image_switch_at = 0.0
        self.project_save_pending = False
        self.project_save_context = {}
        self.project_save_timer = QTimer(self)
        self.project_save_timer.setSingleShot(True)
        self.project_save_timer.timeout.connect(self._flush_pending_project_save)
        self.last_confirmed_locator_timestamp = None
        self.pending_training_preflight = None
        self.training_retry_requested = False
        self.parent_training_failed = False
        self.parent_training_cancel_requested = False
        self.child_training_failed = False
        self.child_training_cancel_requested = False
        self.active_training_kind = None
        self.active_training_label = ""
        self.current_blink_context = {}
        self.vlm_preannotation_thread = None
        self.vlm_preannotation_threads = []
        self.vlm_preannotation_progress_dialog = None
        self.vlm_preannotation_cancel_requested = False
        self.vlm_preannotation_cancelled_queued_images = 0
        self.image_list_group_collapsed = {
            "original": False,
            "split": False,
            "manual": False,
        }
        self._image_list_state_cache = None
        self.parent_box_aspect_ratios = (
            self.project.get_parent_box_aspect_ratios()
            if hasattr(self.project, "get_parent_box_aspect_ratios")
            else {}
        )

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.start_center_widget = self._build_start_center()

        self.workbench_widget = QWidget()
        main_layout = QVBoxLayout(self.workbench_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)
        self.create_menus()

        self.btn_export = QPushButton()
        self.btn_export.clicked.connect(self.export_dataset)
        apply_semantic_button_style(self.btn_export, BUTTON_ROLE_COMMIT)
        self.btn_crop = QPushButton()
        self.btn_crop.clicked.connect(self.open_cropper)
        apply_semantic_button_style(self.btn_crop, BUTTON_ROLE_NEUTRAL)
        self.btn_batch_split_panels = QPushButton()
        self.btn_batch_split_panels.clicked.connect(self.batch_split_panel_images)
        apply_semantic_button_style(self.btn_batch_split_panels, BUTTON_ROLE_NEUTRAL)
        self.btn_blink_entry = QPushButton()
        self.btn_blink_entry.clicked.connect(self.launch_blink_from_workbench)
        apply_semantic_button_style(self.btn_blink_entry, BUTTON_ROLE_NEUTRAL)
        self.btn_start_center_from_workbench = QPushButton()
        self.btn_start_center_from_workbench.setObjectName("workbenchStartCenterButton")
        self.btn_start_center_from_workbench.clicked.connect(self.return_to_start_center_with_context)
        apply_semantic_button_style(self.btn_start_center_from_workbench, BUTTON_ROLE_NEUTRAL)
        self.btn_agent_from_workbench = QPushButton()
        self.btn_agent_from_workbench.setObjectName("workbenchAskAgentButton")
        self.btn_agent_from_workbench.clicked.connect(lambda: self.open_agent_from_context(self._collect_image_workbench_agent_context()))
        apply_semantic_button_style(self.btn_agent_from_workbench, BUTTON_ROLE_NEUTRAL)
        self.btn_vlm_preannotate_current = QPushButton()
        self.btn_vlm_preannotate_current.setObjectName("workbenchVlmPreannotateCurrentButton")
        self.btn_vlm_preannotate_current.clicked.connect(self.run_vlm_preannotation_current)
        apply_semantic_button_style(self.btn_vlm_preannotate_current, BUTTON_ROLE_RUN)
        self.btn_vlm_preannotate_batch = QPushButton()
        self.btn_vlm_preannotate_batch.setObjectName("workbenchVlmPreannotateBatchButton")
        self.btn_vlm_preannotate_batch.clicked.connect(self.run_vlm_preannotation_batch)
        apply_semantic_button_style(self.btn_vlm_preannotate_batch, BUTTON_ROLE_RUN)

        self.workbench_top_bar = QWidget()
        apply_surface_role(self.workbench_top_bar, SURFACE_ROLE_TOOLBAR, "workbenchTopBar")
        top_bar_layout = QHBoxLayout(self.workbench_top_bar)
        top_bar_layout.setContentsMargins(12, 10, 12, 10)
        top_bar_layout.setSpacing(10)

        self.toolbar_project_panel = QWidget()
        apply_surface_role(self.toolbar_project_panel, SURFACE_ROLE_SUBTLE, "workbenchToolbarProjectPanel")
        toolbar_project_layout = QHBoxLayout(self.toolbar_project_panel)
        toolbar_project_layout.setContentsMargins(10, 8, 10, 8)
        toolbar_project_layout.setSpacing(8)
        toolbar_project_layout.addWidget(self.btn_export)
        toolbar_project_layout.addWidget(self.btn_crop)
        toolbar_project_layout.addWidget(self.btn_batch_split_panels)

        self.toolbar_flow_panel = QWidget()
        apply_surface_role(self.toolbar_flow_panel, SURFACE_ROLE_SUBTLE, "workbenchToolbarFlowPanel")
        toolbar_flow_layout = QHBoxLayout(self.toolbar_flow_panel)
        toolbar_flow_layout.setContentsMargins(10, 8, 10, 8)
        toolbar_flow_layout.setSpacing(8)
        toolbar_flow_layout.addWidget(self.btn_blink_entry)
        toolbar_flow_layout.addWidget(self.btn_start_center_from_workbench)
        toolbar_flow_layout.addWidget(self.btn_vlm_preannotate_current)
        toolbar_flow_layout.addWidget(self.btn_vlm_preannotate_batch)
        toolbar_flow_layout.addWidget(self.btn_agent_from_workbench)

        top_bar_layout.addWidget(self.toolbar_project_panel, 0)
        top_bar_layout.addStretch(1)
        top_bar_layout.addWidget(self.toolbar_flow_panel, 0)
        main_layout.addWidget(self.workbench_top_bar)

        self.workbench_splitter = QSplitter(Qt.Horizontal)
        self.workbench_splitter.setChildrenCollapsible(False)
        self.workbench_splitter.setHandleWidth(8)
        main_layout.addWidget(self.workbench_splitter, 1)

        left_panel = QWidget()
        apply_surface_role(left_panel, SURFACE_ROLE_SUBTLE, "workbenchLibraryPanel")
        left_panel.setMinimumWidth(220)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(10)
        self.label_project_images = QLabel()
        self.label_project_images.setObjectName("HeaderLabel")
        left_layout.addWidget(self.label_project_images)
        self.file_list = ImageGroupListWidget()
        self.file_list.setObjectName("imageList")
        self.file_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.file_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self.show_file_list_context_menu)
        self.file_list.itemClicked.connect(self._handle_image_list_item_clicked)
        self.file_list.currentItemChanged.connect(self.on_file_selected)
        self.file_list.imagesDroppedToGroup.connect(self.move_images_to_group)
        left_layout.addWidget(self.file_list)
        self.btn_add = QPushButton()
        self.btn_add.clicked.connect(self.add_images)
        apply_semantic_button_style(self.btn_add, BUTTON_ROLE_NEUTRAL)
        left_layout.addWidget(self.btn_add)
        self.workbench_splitter.addWidget(left_panel)

        center_panel = QWidget()
        center_panel.setObjectName("workbenchCenterPanel")
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(12)

        self.tool_strip = QWidget()
        apply_surface_role(self.tool_strip, SURFACE_ROLE_SUBTLE, "workbenchToolStrip")
        tool_layout = QHBoxLayout(self.tool_strip)
        tool_layout.setContentsMargins(12, 8, 12, 8)
        tool_layout.setSpacing(12)
        self.tool_group = QButtonGroup(self)
        self.radio_draw = QRadioButton()
        self.radio_draw.setObjectName("toolChip")
        self.radio_draw.setChecked(True)
        self.radio_draw.toggled.connect(self.on_tool_changed)
        self.tool_group.addButton(self.radio_draw)
        tool_layout.addWidget(self.radio_draw)
        self.radio_magic = QRadioButton()
        self.radio_magic.setObjectName("toolChip")
        self.radio_magic.toggled.connect(self.on_tool_changed)
        self.tool_group.addButton(self.radio_magic)
        tool_layout.addWidget(self.radio_magic)
        self.radio_box = QRadioButton()
        self.radio_box.setObjectName("toolChip")
        self.radio_box.toggled.connect(self.on_tool_changed)
        self.tool_group.addButton(self.radio_box)
        tool_layout.addWidget(self.radio_box)
        self.radio_annotation_box = QRadioButton()
        self.radio_annotation_box.setObjectName("toolChip")
        self.radio_annotation_box.toggled.connect(self.on_tool_changed)
        self.tool_group.addButton(self.radio_annotation_box)
        tool_layout.addWidget(self.radio_annotation_box)
        self.radio_loose_shrink_box = QRadioButton()
        self.radio_loose_shrink_box.setObjectName("toolChip")
        self.radio_loose_shrink_box.toggled.connect(self.on_tool_changed)
        self.tool_group.addButton(self.radio_loose_shrink_box)
        tool_layout.addWidget(self.radio_loose_shrink_box)
        self.radio_scale = QRadioButton()
        self.radio_scale.setObjectName("scaleToolRadio")
        self.radio_scale.toggled.connect(self.on_tool_changed)
        self.tool_group.addButton(self.radio_scale)
        self.radio_scale.setVisible(False) 
        tool_layout.addWidget(self.radio_scale)
        tool_layout.addStretch(1)
        center_layout.addWidget(self.tool_strip)

        self.canvas = AnnotationCanvas()
        self.canvas.setObjectName("annotationCanvas")
        self.canvas.polygon_completed.connect(self.on_polygon_completed)
        self.canvas.magic_wand_clicked.connect(self.on_magic_wand_clicked)
        self.canvas.magic_box_completed.connect(self.on_magic_box_completed)
        self.canvas.annotation_box_completed.connect(self.on_annotation_box_completed)
        self.canvas.scale_defined.connect(self.on_scale_defined)
        self.canvas_shell = QWidget()
        apply_surface_role(self.canvas_shell, SURFACE_ROLE_CANVAS, "workbenchCanvasShell")
        canvas_layout = QVBoxLayout(self.canvas_shell)
        canvas_layout.setContentsMargins(12, 12, 12, 12)
        canvas_layout.addWidget(self.canvas)
        center_layout.addWidget(self.canvas_shell, 1)
        self.workbench_splitter.addWidget(center_panel)

        from PySide6.QtGui import QKeySequence, QShortcut
        self.shortcut_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.shortcut_undo.activated.connect(self.canvas.undo)
        self.shortcut_redo = QShortcut(QKeySequence("Ctrl+Y"), self)
        self.shortcut_redo.activated.connect(self.canvas.redo)
        self.shortcut_save = QShortcut(QKeySequence(Qt.Key_S), self)
        self.shortcut_save.activated.connect(lambda: self._flush_pending_project_save(force=True))
        self.shortcut_verify = QShortcut(QKeySequence(Qt.Key_Space), self)
        self.shortcut_verify.activated.connect(self.verify_current_image)

        self.workbench_inspector_scroll = QScrollArea()
        self.workbench_inspector_scroll.setObjectName("workbenchInspectorScroll")
        self.workbench_inspector_scroll.setWidgetResizable(True)
        self.workbench_inspector_scroll.setFrameShape(QFrame.NoFrame)
        self.workbench_inspector_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.workbench_inspector_scroll.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Ignored)
        right_panel = QWidget()
        right_panel.setMinimumWidth(320)
        right_panel.setObjectName("workbenchInspectorPanel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        self.metadata_panel = QWidget()
        apply_surface_role(self.metadata_panel, SURFACE_ROLE_PANEL, "workbenchMetadataPanel")
        metadata_layout = QVBoxLayout(self.metadata_panel)
        metadata_layout.setContentsMargins(12, 12, 12, 12)
        metadata_layout.setSpacing(10)
        self.label_taxonomy = QLabel()
        self.label_taxonomy.setObjectName("HeaderLabel")
        self.genus_combo = NoWheelComboBox()
        self.genus_combo.setEditable(True)
        self.genus_combo.setInsertPolicy(QComboBox.InsertAlphabetically)
        self.genus_combo.currentTextChanged.connect(self.on_genus_changed)
        self.label_structures = QLabel()
        self.label_structures.setObjectName("HeaderLabel")
        metadata_layout.addWidget(self.label_structures)
        self.part_list = QTreeWidget()
        self.part_list.setObjectName("workbenchPartTree")
        self.part_list.setHeaderHidden(True)
        self.part_list.setRootIsDecorated(True)
        self.part_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.part_list.currentItemChanged.connect(self.on_part_selected)
        self.part_list.setFixedHeight(190) 
        metadata_layout.addWidget(self.part_list)
        self.blink_context_status_label = QLabel()
        self.blink_context_status_label.setObjectName("mutedLabel")
        self.blink_context_status_label.setWordWrap(True)
        metadata_layout.addWidget(self.blink_context_status_label)
        
        tax_btn_layout = QHBoxLayout()
        self.btn_add_part = QPushButton("+")
        self.btn_add_part.clicked.connect(self.add_taxonomy_part)
        apply_semantic_button_style(self.btn_add_part, BUTTON_ROLE_NEUTRAL, "font-weight: bold;")
        self.btn_rename_part = QPushButton(tr("Rename Structure", self.current_lang))
        self.btn_rename_part.clicked.connect(self.rename_taxonomy_part)
        apply_semantic_button_style(self.btn_rename_part, BUTTON_ROLE_NEUTRAL, "padding: 4px 8px;")
        self.btn_del_part = QPushButton("-")
        self.btn_del_part.clicked.connect(self.remove_taxonomy_part)
        apply_semantic_button_style(self.btn_del_part, BUTTON_ROLE_DESTRUCTIVE, "font-weight: bold;")
        tax_btn_layout.addWidget(self.btn_add_part)
        tax_btn_layout.addWidget(self.btn_rename_part)
        tax_btn_layout.addWidget(self.btn_del_part)
        metadata_layout.addLayout(tax_btn_layout)
        
        self.check_morpho = QCheckBox() 
        self.check_morpho.stateChanged.connect(self.toggle_morphometrics)
        metadata_layout.addWidget(self.check_morpho)
        self.group_morpho = QGroupBox()
        apply_surface_role(self.group_morpho, SURFACE_ROLE_SUBTLE, "workbenchMorphometricsPanel")
        self.group_morpho.setVisible(False)
        morpho_layout = QVBoxLayout(self.group_morpho)
        self.label_measurements = QLabel("N/A")
        self.label_measurements.setObjectName("mutedLabel")
        morpho_layout.addWidget(self.label_measurements)
        metadata_layout.addWidget(self.group_morpho)
        self.image_taxon_panel = QWidget()
        self.image_taxon_panel.setObjectName("workbenchImageTaxonPanel")
        image_taxon_layout = QVBoxLayout(self.image_taxon_panel)
        image_taxon_layout.setContentsMargins(0, 0, 0, 0)
        image_taxon_layout.setSpacing(6)
        image_taxon_layout.addWidget(self.label_taxonomy)
        image_taxon_layout.addWidget(self.genus_combo)
        metadata_layout.addWidget(self.image_taxon_panel)
        self.description_header_panel = QWidget()
        self.description_header_panel.setObjectName("workbenchDescriptionHeader")
        description_header = QHBoxLayout(self.description_header_panel)
        description_header.setContentsMargins(0, 0, 0, 0)
        description_header.setSpacing(8)
        self.btn_literature_descriptions = QPushButton()
        self.btn_literature_descriptions.setObjectName("workbenchLiteratureDescriptionButton")
        self.btn_literature_descriptions.clicked.connect(self.open_literature_description_dialog)
        apply_semantic_button_style(self.btn_literature_descriptions, BUTTON_ROLE_NEUTRAL, "padding: 4px 8px;")
        description_header.addWidget(self.btn_literature_descriptions)
        self.label_description = QLabel()
        self.label_description.setObjectName("HeaderLabel")
        description_header.addWidget(self.label_description)
        description_header.addStretch()
        metadata_layout.addWidget(self.description_header_panel)
        self.desc_box = QTextEdit()
        self.desc_box.setMaximumHeight(100)
        self.desc_box.setObjectName("LinkedDescriptionBox")
        metadata_layout.addWidget(self.desc_box)
        right_layout.addWidget(self.metadata_panel)

        self.ai_panel = QWidget()
        apply_surface_role(self.ai_panel, SURFACE_ROLE_PANEL, "workbenchAIPanel")
        ai_layout = QVBoxLayout(self.ai_panel)
        ai_layout.setContentsMargins(12, 12, 12, 12)
        ai_layout.setSpacing(10)
        self.label_ai_workflow = QLabel()
        self.label_ai_workflow.setObjectName("HeaderLabel")
        ai_layout.addWidget(self.label_ai_workflow)

        self.label_model_backend = QLabel()
        self.label_model_backend.setObjectName("mutedLabel")
        ai_layout.addWidget(self.label_model_backend)

        self.parent_annotation_panel = QWidget()
        apply_surface_role(self.parent_annotation_panel, SURFACE_ROLE_RAISED, "workbenchParentAnnotationPanel")
        parent_annotation_layout = QVBoxLayout(self.parent_annotation_panel)
        parent_annotation_layout.setContentsMargins(10, 10, 10, 10)
        parent_annotation_layout.setSpacing(8)
        self.label_parent_annotation = QLabel()
        self.label_parent_annotation.setObjectName("HeaderLabel")
        parent_annotation_layout.addWidget(self.label_parent_annotation)

        # --- Model Selection Area (Decoupled) ---
        self.ai_model_panel = QWidget()
        self.ai_model_panel.setObjectName("workbenchAIModelPanel")
        models_form = QGridLayout(self.ai_model_panel)
        models_form.setContentsMargins(0, 0, 0, 0)
        models_form.setHorizontalSpacing(8)
        models_form.setVerticalSpacing(5)
        models_form.setColumnStretch(1, 1)
        
        # Locator Selection
        self.lbl_locator = QLabel("Locator:")
        models_form.addWidget(self.lbl_locator, 0, 0)
        self.combo_locator = NoWheelComboBox()
        self.combo_locator.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.combo_locator.activated.connect(self.on_locator_changed)
        self.combo_locator.currentIndexChanged.connect(self.update_model_delete_button_states)
        models_form.addWidget(self.combo_locator, 0, 1)
        
        self.btn_del_locator = QPushButton("Del")
        self.btn_del_locator.setEnabled(False)
        self.btn_del_locator.clicked.connect(self.delete_locator_model)
        apply_semantic_button_style(self.btn_del_locator, BUTTON_ROLE_DESTRUCTIVE)
        self.btn_note_locator = QPushButton("Note")
        self.btn_note_locator.setEnabled(False)
        self.btn_note_locator.clicked.connect(self.edit_locator_model_note)
        apply_semantic_button_style(self.btn_note_locator, BUTTON_ROLE_NEUTRAL)
        models_form.addWidget(self.btn_note_locator, 0, 2)
        models_form.addWidget(self.btn_del_locator, 0, 3)
        
        # Segmenter Selection
        self.lbl_segmenter = QLabel("Segmenter:")
        models_form.addWidget(self.lbl_segmenter, 1, 0)
        self.combo_segmenter = NoWheelComboBox()
        self.combo_segmenter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.combo_segmenter.activated.connect(self.on_segmenter_changed)
        self.combo_segmenter.currentIndexChanged.connect(self.update_model_delete_button_states)
        models_form.addWidget(self.combo_segmenter, 1, 1)
        
        self.btn_del_segmenter = QPushButton("Del")
        self.btn_del_segmenter.setEnabled(False)
        self.btn_del_segmenter.clicked.connect(self.delete_segmenter_model)
        apply_semantic_button_style(self.btn_del_segmenter, BUTTON_ROLE_DESTRUCTIVE)
        self.btn_note_segmenter = QPushButton("Note")
        self.btn_note_segmenter.setEnabled(False)
        self.btn_note_segmenter.clicked.connect(self.edit_segmenter_model_note)
        apply_semantic_button_style(self.btn_note_segmenter, BUTTON_ROLE_NEUTRAL)
        models_form.addWidget(self.btn_note_segmenter, 1, 2)
        models_form.addWidget(self.btn_del_segmenter, 1, 3)
        
        parent_annotation_layout.addWidget(self.ai_model_panel)

        self.ai_action_panel = QWidget()
        self.ai_action_panel.setObjectName("workbenchAIActionPanel")
        ai_action_layout = QVBoxLayout(self.ai_action_panel)
        ai_action_layout.setContentsMargins(0, 0, 0, 0)
        ai_action_layout.setSpacing(8)

        btns_layout = QHBoxLayout()
        self.btn_predict = QPushButton()
        self.btn_predict.clicked.connect(self.run_prediction)
        apply_semantic_button_style(self.btn_predict, BUTTON_ROLE_RUN, "padding: 5px;")
        btns_layout.addWidget(self.btn_predict)
        self.btn_batch = QPushButton()
        self.btn_batch.clicked.connect(self.run_batch_inference)
        apply_semantic_button_style(self.btn_batch, BUTTON_ROLE_RUN, "padding: 5px;")
        btns_layout.addWidget(self.btn_batch)
        ai_action_layout.addLayout(btns_layout)
        self.btn_accept_current_ai_drafts = QPushButton()
        self.btn_accept_current_ai_drafts.clicked.connect(self.accept_current_image_ai_drafts)
        apply_semantic_button_style(self.btn_accept_current_ai_drafts, BUTTON_ROLE_COMMIT, "padding: 6px;")
        ai_action_layout.addWidget(self.btn_accept_current_ai_drafts)
        self.btn_accept_batch_ai_drafts = QPushButton()
        self.btn_accept_batch_ai_drafts.clicked.connect(self.accept_batch_ai_drafts)
        apply_semantic_button_style(self.btn_accept_batch_ai_drafts, BUTTON_ROLE_COMMIT, "padding: 6px;")
        ai_action_layout.addWidget(self.btn_accept_batch_ai_drafts)
        self.chk_train_locator_only = QCheckBox()
        self.chk_train_locator_only.setToolTip(
            tr(
                "Skip SAM/parts training for this run. Useful when the base SAM result is already good enough.",
                self.current_lang,
            )
        )
        ai_action_layout.addWidget(self.chk_train_locator_only)
        train_scope_row = QHBoxLayout()
        train_scope_row.setContentsMargins(0, 0, 0, 0)
        train_scope_row.setSpacing(8)
        self.lbl_training_scope = QLabel()
        self.lbl_training_scope.setObjectName("mutedLabel")
        train_scope_row.addWidget(self.lbl_training_scope)
        self.combo_training_scope = NoWheelComboBox()
        self.combo_training_scope.setObjectName("workbenchTrainingScopeCombo")
        self.combo_training_scope.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        train_scope_row.addWidget(self.combo_training_scope, 1)
        ai_action_layout.addLayout(train_scope_row)

        train_buttons_layout = QHBoxLayout()
        self.btn_train = QPushButton()
        self.btn_train.clicked.connect(self.run_training)
        apply_semantic_button_style(self.btn_train, BUTTON_ROLE_RUN, "padding: 8px; margin-top: 5px;")
        train_buttons_layout.addWidget(self.btn_train, 3)
        self.btn_stop_training = QPushButton()
        self.btn_stop_training.setEnabled(False)
        self.btn_stop_training.clicked.connect(self.stop_training)
        apply_semantic_button_style(self.btn_stop_training, BUTTON_ROLE_STOP, "padding: 8px; margin-top: 5px;")
        train_buttons_layout.addWidget(self.btn_stop_training, 2)
        ai_action_layout.addLayout(train_buttons_layout)
        self.btn_clear_ai = QPushButton()
        self.btn_clear_ai.clicked.connect(self.clear_ai_labels)
        apply_semantic_button_style(self.btn_clear_ai, BUTTON_ROLE_DESTRUCTIVE, "font-weight: bold; margin-top: 5px;")
        ai_action_layout.addWidget(self.btn_clear_ai)
        parent_annotation_layout.addWidget(self.ai_action_panel)
        ai_layout.addWidget(self.parent_annotation_panel)

        self.blink_refine_panel = QWidget()
        apply_surface_role(self.blink_refine_panel, SURFACE_ROLE_RAISED, "workbenchBlinkRefinePanel")
        blink_refine_layout = QVBoxLayout(self.blink_refine_panel)
        blink_refine_layout.setContentsMargins(10, 10, 10, 10)
        blink_refine_layout.setSpacing(8)
        self.label_blink_refine = QLabel()
        self.label_blink_refine.setObjectName("HeaderLabel")
        blink_refine_layout.addWidget(self.label_blink_refine)
        self.label_blink_route = QLabel()
        self.label_blink_route.setObjectName("mutedLabel")
        self.label_blink_route.setWordWrap(True)
        blink_refine_layout.addWidget(self.label_blink_route)
        self.label_blink_parent_context = QLabel()
        self.label_blink_parent_context.setObjectName("mutedLabel")
        blink_refine_layout.addWidget(self.label_blink_parent_context)
        self.combo_blink_parent_context = NoWheelComboBox()
        self.combo_blink_parent_context.activated.connect(self.on_blink_parent_context_changed)
        blink_refine_layout.addWidget(self.combo_blink_parent_context)
        self.label_blink_parent_box = QLabel()
        self.label_blink_parent_box.setObjectName("mutedLabel")
        self.label_blink_parent_box.setWordWrap(True)
        blink_refine_layout.addWidget(self.label_blink_parent_box)
        self.label_blink_expert = QLabel()
        self.label_blink_expert.setObjectName("mutedLabel")
        self.label_blink_expert.setWordWrap(True)
        blink_refine_layout.addWidget(self.label_blink_expert)
        self.check_lock_parent_box_ratio = QCheckBox()
        self.check_lock_parent_box_ratio.setChecked(False)
        self.check_lock_parent_box_ratio.stateChanged.connect(self._refresh_annotation_box_constraints)
        blink_refine_layout.addWidget(self.check_lock_parent_box_ratio)
        self.btn_configure_route_expert = QPushButton()
        self.btn_configure_route_expert.clicked.connect(self.open_current_route_expert_settings)
        apply_semantic_button_style(self.btn_configure_route_expert, BUTTON_ROLE_NEUTRAL)
        blink_refine_layout.addWidget(self.btn_configure_route_expert)
        self.btn_blink_auto_annotate = QPushButton()
        self.btn_blink_auto_annotate.clicked.connect(self.run_blink_child_auto_annotate)
        apply_semantic_button_style(self.btn_blink_auto_annotate, BUTTON_ROLE_RUN, "padding: 6px;")
        blink_refine_layout.addWidget(self.btn_blink_auto_annotate)
        blink_shrink_buttons = QHBoxLayout()
        blink_shrink_buttons.setContentsMargins(0, 0, 0, 0)
        blink_shrink_buttons.setSpacing(8)
        self.btn_blink_auto_shrink = QPushButton()
        self.btn_blink_auto_shrink.clicked.connect(self.run_blink_auto_shrink)
        apply_semantic_button_style(self.btn_blink_auto_shrink, BUTTON_ROLE_RUN, "padding: 6px;")
        blink_shrink_buttons.addWidget(self.btn_blink_auto_shrink)
        self.btn_blink_batch_auto_shrink = QPushButton()
        self.btn_blink_batch_auto_shrink.clicked.connect(self.run_blink_batch_auto_shrink)
        apply_semantic_button_style(self.btn_blink_batch_auto_shrink, BUTTON_ROLE_RUN, "padding: 6px;")
        blink_shrink_buttons.addWidget(self.btn_blink_batch_auto_shrink)
        blink_refine_layout.addLayout(blink_shrink_buttons)
        blink_train_buttons = QHBoxLayout()
        blink_train_buttons.setContentsMargins(0, 0, 0, 0)
        blink_train_buttons.setSpacing(8)
        self.btn_blink_train_expert = QPushButton()
        self.btn_blink_train_expert.clicked.connect(self.train_current_blink_expert)
        apply_semantic_button_style(self.btn_blink_train_expert, BUTTON_ROLE_RUN, "padding: 6px;")
        blink_train_buttons.addWidget(self.btn_blink_train_expert, 3)
        self.btn_blink_stop_training = QPushButton()
        self.btn_blink_stop_training.setEnabled(False)
        self.btn_blink_stop_training.clicked.connect(self.stop_current_blink_expert_training)
        apply_semantic_button_style(self.btn_blink_stop_training, BUTTON_ROLE_STOP, "padding: 6px;")
        blink_train_buttons.addWidget(self.btn_blink_stop_training, 2)
        blink_refine_layout.addLayout(blink_train_buttons)
        ai_layout.addWidget(self.blink_refine_panel)

        self.training_progress_panel = QWidget()
        apply_surface_role(self.training_progress_panel, SURFACE_ROLE_SUBTLE, "workbenchTrainingProgressPanel")
        training_progress_layout = QVBoxLayout(self.training_progress_panel)
        training_progress_layout.setContentsMargins(10, 10, 10, 10)
        training_progress_layout.setSpacing(6)
        training_progress_header = QHBoxLayout()
        training_progress_header.setContentsMargins(0, 0, 0, 0)
        training_progress_header.setSpacing(8)
        self.label_training_progress = QLabel()
        self.label_training_progress.setObjectName("HeaderLabel")
        self.label_training_progress.setText(tr("Training progress", self.current_lang))
        training_progress_header.addWidget(self.label_training_progress)
        training_progress_header.addStretch()
        self.btn_training_results = QPushButton()
        self.btn_training_results.setObjectName("workbenchTrainingResultsButton")
        self.btn_training_results.clicked.connect(self.open_training_results_browser)
        apply_semantic_button_style(self.btn_training_results, BUTTON_ROLE_NEUTRAL, "padding: 4px 8px;")
        training_progress_header.addWidget(self.btn_training_results)
        training_progress_layout.addLayout(training_progress_header)
        self.label_training_progress_status = QLabel()
        self.label_training_progress_status.setObjectName("mutedLabel")
        self.label_training_progress_status.setWordWrap(True)
        self.label_training_progress_status.setText(tr("No training running.", self.current_lang))
        training_progress_layout.addWidget(self.label_training_progress_status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        training_progress_layout.addWidget(self.progress)
        ai_layout.addWidget(self.training_progress_panel)
        right_layout.addWidget(self.ai_panel)

        self.logs_panel = QWidget()
        apply_surface_role(self.logs_panel, SURFACE_ROLE_SUBTLE, "workbenchLogsPanel")
        logs_layout = QVBoxLayout(self.logs_panel)
        logs_layout.setContentsMargins(12, 12, 12, 12)
        logs_layout.setSpacing(8)
        self.label_logs = QLabel()
        self.label_logs.setObjectName("HeaderLabel")
        logs_layout.addWidget(self.label_logs)
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setMinimumHeight(260)
        self.log_console.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.log_console.setObjectName("MutedLogConsole")
        logs_layout.addWidget(self.log_console, 1)
        right_layout.addWidget(self.logs_panel, 1)
        right_layout.addStretch(0)
        self.workbench_inspector_scroll.setWidget(right_panel)
        self.workbench_splitter.addWidget(self.workbench_inspector_scroll)
        self.workbench_splitter.setStretchFactor(0, 1)
        self.workbench_splitter.setStretchFactor(1, 5)
        self.workbench_splitter.setStretchFactor(2, 2)
        self.workbench_splitter.setSizes([240, 1080, 320])

        self.pdf_widget = PdfProcessingWidget(self.current_lang)
        self.pdf_widget.start_center_requested.connect(self.return_to_start_center_with_context)
        self.pdf_widget.agent_requested.connect(self.open_agent_from_context)
        self.tif_workbench = TifWorkbenchWidget(self.tif_project, self.current_lang, config_manager=self.config)
        self.tif_workbench.start_center_requested.connect(self.return_to_start_center_with_context)
        self.tif_workbench.agent_requested.connect(self.open_agent_from_context)
        self.blink_lab = BlinkLabWidget(
            self.engine,
            self.project,
            self.current_lang,
            blink_epochs=self.blink_train_epochs,
            blink_batch=self.blink_train_batch,
            blink_lr=self.blink_train_lr,
            blink_weight_decay=self.blink_train_weight_decay,
            blink_input_size=self.blink_train_input_size,
            blink_auto_shrink_steps=self.blink_auto_shrink_steps,
            blink_training_strategy=self.blink_training_strategy,
            runtime_device=self.runtime_device,
        )
        self.blink_lab.start_center_requested.connect(self.return_to_start_center_with_context)
        self.blink_lab.agent_requested.connect(self.open_agent_from_context)
        self.blink_lab.global_labels_updated.connect(self.on_global_labels_updated)
        self.blink_lab.route_registry_refresh_requested.connect(self.refresh_route_table)
        self.route_settings_panel = RouteManagementPanel(self, self.current_lang)
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

        self._open_or_create_startup_project()
        self.active_project_entry_path = self.project.current_project_path or ""
        self.active_project_kind = "start"
        if self.config.get("startup_behavior", "start_center") == "continue_last" and self.config.get("last_project_path", ""):
            self.open_last_project()
            if self.active_project_kind == "start":
                self._show_start_center()
        else:
            self._show_start_center()
        self.log(tr("System Initialized.", self.current_lang))
        self.refresh_model_list()
        self.refresh_ui()
        self.refresh_route_table()
        self.change_theme(self.current_theme)
        self.apply_startup_window_geometry()

    def _is_tif_workflow_enabled(self):
        return bool(getattr(self, "tif_workflow_enabled", False))

    def _show_tif_workflow_unavailable(self):
        QMessageBox.information(
            self,
            tr("TIF Volume Workbench", self.current_lang),
            (
                "The experimental TIF workflow is hidden in the public build. "
                f"Set {EXPERIMENTAL_TIF_WORKFLOW_ENV}=1 before starting TaxaMask to enable it for local development."
            ),
        )

    def _apply_window_icon(self):
        for icon_path in (APP_ICON_PATH, APP_ICON_FALLBACK_PATH):
            if icon_path and os.path.exists(icon_path):
                icon = QIcon(icon_path)
                if not icon.isNull():
                    self.setWindowIcon(icon)
                    app = QApplication.instance()
                    if app is not None:
                        app.setWindowIcon(icon)
                    return

    def apply_startup_window_geometry(self):
        if QApplication.platformName() == "offscreen":
            return

        app = QApplication.instance()
        if app is None:
            return

        screen = app.primaryScreen()
        if screen is None:
            return

        available = screen.availableGeometry()
        x, y, width, height = compute_centered_window_geometry(
            (available.left(), available.top(), available.width(), available.height()),
            (self.startup_size.width(), self.startup_size.height()),
        )
        self.setGeometry(x, y, width, height)

    def _build_start_center(self):
        page = QWidget()
        page.setObjectName("startCenterPage")
        outer_layout = QHBoxLayout(page)
        outer_layout.setContentsMargins(24, 22, 24, 22)
        outer_layout.setSpacing(18)

        agent_area = QWidget()
        agent_area.setObjectName("startCenterAgentMain")
        agent_layout = QVBoxLayout(agent_area)
        agent_layout.setContentsMargins(0, 0, 0, 0)
        agent_layout.setSpacing(14)

        self.agent_panel = TaxaMaskAgentPanel(self.current_lang)
        self.agent_panel.status_changed.connect(self._handle_agent_dashboard_status_changed)

        header = QWidget()
        apply_surface_role(header, SURFACE_ROLE_PANEL, "startCenterHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 14, 20, 14)
        header_layout.setSpacing(14)

        header_text = QWidget()
        header_text_layout = QVBoxLayout(header_text)
        header_text_layout.setContentsMargins(0, 0, 0, 0)
        header_text_layout.setSpacing(6)
        self.start_title = QLabel()
        self.start_title.setObjectName("startCenterTitle")
        self.start_subtitle = QLabel()
        self.start_subtitle.setObjectName("mutedLabel")
        self.start_subtitle.setWordWrap(True)
        header_text_layout.addWidget(self.start_title)
        header_text_layout.addWidget(self.start_subtitle)
        header_layout.addWidget(header_text, 1)

        header_controls = QWidget()
        header_controls.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        header_controls_layout = QVBoxLayout(header_controls)
        header_controls_layout.setContentsMargins(0, 0, 0, 0)
        header_controls_layout.setSpacing(6)
        self.start_agent_status_label = QLabel()
        self.start_agent_status_label.setObjectName("mutedLabel")
        self.start_agent_status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.start_agent_status_label.setWordWrap(False)
        header_controls_layout.addWidget(self.start_agent_status_label)
        header_button_layout = QHBoxLayout()
        header_button_layout.setContentsMargins(0, 0, 0, 0)
        header_button_layout.setSpacing(8)
        self.btn_start_ant_code = QPushButton()
        self.btn_start_ant_code.setObjectName("startCenterStartAntCodeButton")
        self.btn_start_ant_code.clicked.connect(self.agent_panel.start_dashboard)
        self.btn_stop_ant_code = QPushButton()
        self.btn_stop_ant_code.setObjectName("startCenterStopAntCodeButton")
        self.btn_stop_ant_code.clicked.connect(self.agent_panel.stop_dashboard)
        button_extras = "padding: 5px 10px;"
        apply_semantic_button_style(self.btn_start_ant_code, BUTTON_ROLE_RUN, button_extras)
        apply_semantic_button_style(self.btn_stop_ant_code, BUTTON_ROLE_STOP, button_extras)
        header_button_layout.addWidget(self.btn_start_ant_code)
        header_button_layout.addWidget(self.btn_stop_ant_code)
        header_controls_layout.addLayout(header_button_layout)
        header_layout.addWidget(header_controls, 0, Qt.AlignTop | Qt.AlignRight)
        agent_layout.addWidget(header)

        agent_layout.addWidget(self.agent_panel, 1)
        outer_layout.addWidget(agent_area, 1)

        workflow_rail_scroll = QScrollArea()
        workflow_rail_scroll.setObjectName("startWorkflowRailScroll")
        workflow_rail_scroll.setWidgetResizable(True)
        workflow_rail_scroll.setFrameShape(QFrame.NoFrame)
        workflow_rail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        workflow_rail_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        workflow_rail_scroll.setMinimumWidth(360)
        workflow_rail_scroll.setMaximumWidth(410)
        workflow_rail_scroll.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        workflow_rail = QWidget()
        workflow_rail.setObjectName("startWorkflowRail")
        workflow_rail.setMinimumWidth(340)
        workflow_rail.setMaximumWidth(390)
        rail_layout = QVBoxLayout(workflow_rail)
        rail_layout.setContentsMargins(0, 0, 0, 0)
        rail_layout.setSpacing(14)
        self.start_console_panel = self._build_project_console()
        rail_layout.addWidget(self.start_console_panel)
        self.start_quick_panel = self._build_start_quick_panel()
        rail_layout.addWidget(self.start_quick_panel)
        self.start_image_card = self._build_workflow_card(
            "start2DWorkflowCard",
            "2D / STL morphology annotation",
            "Annotate high-resolution 2D views rendered from STL, or ordinary 2D morphology images, then train Locator/SAM/Blink models.",
            "Enter 2D/STL workflow",
            self.enter_image_workflow,
            "Create 2D/STL project",
            self.new_project,
        )
        self.start_tif_card = None
        if self._is_tif_workflow_enabled():
            self.start_tif_card = self._build_workflow_card(
                "startTifWorkflowCard",
                "TIF volume annotation",
                "Annotate continuous slice volumes with material IDs, export train-ready volumes, and call TIF segmentation backends.",
                "Enter TIF workflow",
                self.enter_tif_workflow,
                "Create TIF project",
                self.new_tif_project,
            )
        self.start_pdf_card = self._build_workflow_card(
            "startPdfEvidenceCard",
            "PDF evidence workflow",
            "Use Agent first to confirm the target taxon, screening rules, figure extraction scope, evidence indexes, candidate review, and safe import.",
            "Plan PDF workflow with Agent",
            self.open_agent_for_pdf_workflow,
            "Open PDF tools",
            self.open_pdf_evidence_tools,
        )
        rail_layout.addWidget(self.start_pdf_card)
        rail_layout.addWidget(self.start_image_card)
        if self.start_tif_card is not None:
            rail_layout.addWidget(self.start_tif_card)
        rail_layout.addStretch(1)
        workflow_rail_scroll.setWidget(workflow_rail)
        outer_layout.addWidget(workflow_rail_scroll, 0)
        return page

    def _build_start_quick_panel(self):
        panel = QWidget()
        apply_surface_role(panel, SURFACE_ROLE_SUBTLE, "startCenterQuickPanel")
        panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        self.start_recent_label = QLabel()
        self.start_recent_label.setObjectName("mutedLabel")
        self.start_recent_label.setWordWrap(True)
        self.start_recent_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.btn_continue_last = QPushButton()
        self.btn_continue_last.clicked.connect(self.open_last_project)
        apply_semantic_button_style(self.btn_continue_last, BUTTON_ROLE_COMMIT)
        self.btn_open_any = QPushButton()
        self.btn_open_any.clicked.connect(self.open_project)
        apply_semantic_button_style(self.btn_open_any, BUTTON_ROLE_NEUTRAL)
        self.btn_general_settings = QPushButton()
        self.btn_general_settings.clicked.connect(self.open_general_settings)
        apply_semantic_button_style(self.btn_general_settings, BUTTON_ROLE_NEUTRAL)
        layout.addWidget(self.start_recent_label)
        layout.addWidget(self.btn_continue_last)
        layout.addWidget(self.btn_open_any)
        layout.addWidget(self.btn_general_settings)
        return panel

    def _build_project_console(self):
        panel = QWidget()
        apply_surface_role(panel, SURFACE_ROLE_SUBTLE, "startProjectConsole")
        panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        self.start_console_title = QLabel()
        self.start_console_title.setObjectName("startProjectConsoleTitle")
        self.start_console_summary = QLabel()
        self.start_console_summary.setObjectName("mutedLabel")
        self.start_console_summary.setWordWrap(False)
        self.start_console_summary.setMinimumWidth(0)
        self.start_console_summary.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        title_layout = QVBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(2)
        title_layout.addWidget(self.start_console_title)
        title_layout.addWidget(self.start_console_summary)
        header_layout.addLayout(title_layout, 1)
        self.btn_start_console_toggle = QPushButton()
        self.btn_start_console_toggle.setObjectName("startProjectConsoleToggleButton")
        self.btn_start_console_toggle.clicked.connect(self._toggle_start_project_console)
        apply_semantic_button_style(self.btn_start_console_toggle, BUTTON_ROLE_NEUTRAL, "padding: 3px 8px; min-width: 34px;")
        header_layout.addWidget(self.btn_start_console_toggle, 0, Qt.AlignTop | Qt.AlignRight)
        layout.addWidget(header)

        self.start_console_body = QWidget()
        self.start_console_body.setObjectName("startProjectConsoleBody")
        body_layout = QVBoxLayout(self.start_console_body)
        body_layout.setContentsMargins(0, 2, 0, 0)
        body_layout.setSpacing(5)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)

        self.start_console_workflow_label, self.start_console_workflow_value = self._build_project_console_row(
            grid, 0, "startConsoleWorkflowValue"
        )
        self.start_console_project_label, self.start_console_project_value = self._build_project_console_row(
            grid, 1, "startConsoleProjectValue"
        )
        self.start_console_images_label, self.start_console_images_value = self._build_project_console_row(
            grid, 2, "startConsoleImagesValue"
        )
        if self._is_tif_workflow_enabled():
            self.start_console_tif_label, self.start_console_tif_value = self._build_project_console_row(
                grid, 3, "startConsoleTifValue"
            )
        else:
            self.start_console_tif_label = None
            self.start_console_tif_value = None
        self.start_console_pdf_label, self.start_console_pdf_value = self._build_project_console_row(
            grid, 4 if self._is_tif_workflow_enabled() else 3, "startConsolePdfValue"
        )
        self.start_console_agent_label, self.start_console_agent_value = self._build_project_console_row(
            grid, 5 if self._is_tif_workflow_enabled() else 4, "startConsoleAgentValue"
        )
        grid.setColumnStretch(1, 1)
        body_layout.addLayout(grid)

        self.start_console_stl_note = QLabel()
        self.start_console_stl_note.setObjectName("mutedLabel")
        self.start_console_stl_note.setWordWrap(True)
        body_layout.addWidget(self.start_console_stl_note)
        layout.addWidget(self.start_console_body)
        self.start_console_expanded = False
        self.start_console_body.setVisible(False)
        return panel

    def _toggle_start_project_console(self):
        self.start_console_expanded = not bool(getattr(self, "start_console_expanded", False))
        self._update_start_project_console_collapsed_state()

    def _update_start_project_console_collapsed_state(self):
        if not hasattr(self, "start_console_body"):
            return
        expanded = bool(getattr(self, "start_console_expanded", False))
        self.start_console_body.setVisible(expanded)
        if hasattr(self, "btn_start_console_toggle"):
            self.btn_start_console_toggle.setText("−" if expanded else "+")
            self.btn_start_console_toggle.setToolTip(
                tr("Collapse Project Console", self.current_lang)
                if expanded
                else tr("Expand Project Console", self.current_lang)
            )

    def _build_project_console_row(self, grid, row, value_object_name):
        label = QLabel()
        label.setObjectName("mutedLabel")
        label.setMinimumWidth(92)
        value = QLabel()
        value.setObjectName(value_object_name)
        value.setProperty("consoleValue", True)
        value.setWordWrap(True)
        value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        grid.addWidget(label, row, 0)
        grid.addWidget(value, row, 1)
        return label, value

    def _build_workflow_card(self, object_name, title_key, description_key, enter_key, enter_callback, create_key, create_callback):
        card = QFrame()
        card.setObjectName(object_name)
        card.setFrameShape(QFrame.NoFrame)
        card.setProperty("surfaceRole", SURFACE_ROLE_PANEL)
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setMinimumHeight(230)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        title = QLabel()
        title.setObjectName("startWorkflowTitle")
        title.setProperty("textKey", title_key)
        title.setWordWrap(True)
        description = QLabel()
        description.setObjectName("mutedLabel")
        description.setWordWrap(True)
        description.setProperty("textKey", description_key)
        enter_button = QPushButton()
        enter_button.setProperty("textKey", enter_key)
        enter_button.clicked.connect(enter_callback)
        apply_semantic_button_style(enter_button, BUTTON_ROLE_RUN, "padding: 10px; font-weight: bold;")
        create_button = QPushButton()
        create_button.setProperty("textKey", create_key)
        create_button.clicked.connect(create_callback)
        apply_semantic_button_style(create_button, BUTTON_ROLE_NEUTRAL)
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addStretch(1)
        layout.addWidget(enter_button)
        layout.addWidget(create_button)
        return card

    def _show_start_center(self):
        self.active_project_kind = "start"
        self._apply_project_mode_tabs()
        self._update_start_center_texts()

    def _update_start_center_texts(self):
        if not hasattr(self, "start_center_widget"):
            return
        self.start_title.setText(tr("TaxaMask Agent Center", self.current_lang))
        self.start_subtitle.setText(
            tr(
                "Ask Ant-Code to configure workflows, inspect errors, prepare PDF evidence, or plan training. Use the right rail when you want to enter a workbench directly.",
                self.current_lang,
            )
        )
        last_project = self.config.get("last_project_path", "")
        if last_project and os.path.exists(last_project):
            self.start_recent_label.setText(
                f"{tr('Continue last project', self.current_lang)}\n{self._compact_project_path(last_project)}"
            )
            self.start_recent_label.setToolTip(os.path.abspath(last_project))
            self.btn_continue_last.setEnabled(True)
        else:
            self.start_recent_label.setText(tr("No recent project", self.current_lang))
            self.start_recent_label.setToolTip("")
            self.btn_continue_last.setEnabled(False)
        self.btn_continue_last.setText(tr("Continue last project", self.current_lang))
        self.btn_open_any.setText(tr("Open any project", self.current_lang))
        self.btn_general_settings.setText(tr("General Settings", self.current_lang))
        if hasattr(self, "btn_start_ant_code"):
            self.btn_start_ant_code.setText(tr("Start Ant-Code", self.current_lang))
            self.btn_stop_ant_code.setText(tr("Stop Ant-Code", self.current_lang))
        self._refresh_project_console()
        if hasattr(self, "create_menus"):
            self.create_menus()
        for label in self.start_center_widget.findChildren(QLabel):
            key = label.property("textKey")
            if key:
                label.setText(tr(str(key), self.current_lang))
        for button in self.start_center_widget.findChildren(QPushButton):
            key = button.property("textKey")
            if key:
                button.setText(tr(str(key), self.current_lang))
        if hasattr(self, "agent_panel"):
            self.agent_panel.set_language(self.current_lang)
            self.agent_panel.update_runtime_status(
                model_status=tr("Local task cards", self.current_lang),
                workflow=self._agent_current_workflow_label(),
                project=self._agent_current_project_label(),
                state=tr("Idle", self.current_lang),
            )
            self._update_start_agent_status(self.agent_panel.status_text())
            self._refresh_project_console()

    def _handle_agent_dashboard_status_changed(self, status):
        self._update_start_agent_status(status)
        self._refresh_project_console()

    def _update_start_agent_status(self, status=None):
        if not hasattr(self, "start_agent_status_label"):
            return
        panel = getattr(self, "agent_panel", None)
        text = str(status or (panel.status_text() if panel is not None else "") or "").strip()
        if not text:
            text = self._start_console_agent_status()
        max_len = 72
        display = text if len(text) <= max_len else f"{text[: max_len - 1]}..."
        self.start_agent_status_label.setText(tr("Agent status: {0}", self.current_lang).format(display))
        self.start_agent_status_label.setToolTip(text)

    def _refresh_project_console(self):
        if not hasattr(self, "start_console_title"):
            return
        self.start_console_title.setText(tr("Project Console", self.current_lang))
        self.start_console_workflow_label.setText(tr("Current workflow", self.current_lang))
        self.start_console_project_label.setText(tr("Current project", self.current_lang))
        self.start_console_images_label.setText(tr("2D/STL images", self.current_lang))
        if self._is_tif_workflow_enabled() and self.start_console_tif_label is not None:
            self.start_console_tif_label.setText(tr("TIF specimens", self.current_lang))
        self.start_console_pdf_label.setText(tr("PDF evidence", self.current_lang))
        self.start_console_agent_label.setText("Ant-Code")

        self.start_console_workflow_value.setText(self._agent_current_workflow_label())
        project_summary, project_detail = self._start_console_project_summary()
        image_summary, image_detail = self._start_console_image_summary()
        tif_summary, tif_detail = (
            self._start_console_tif_summary()
            if self._is_tif_workflow_enabled()
            else ("", "")
        )
        pdf_summary, pdf_detail = self._start_console_pdf_summary()
        agent_summary = self._start_console_agent_status()
        summary = self._start_console_collapsed_summary(project_summary, agent_summary)
        self.start_console_summary.setText(summary)
        self.start_console_summary.setToolTip(f"{project_summary}\n{agent_summary}".strip())
        self.start_console_project_value.setText(project_summary)
        self.start_console_images_value.setText(image_summary)
        if self._is_tif_workflow_enabled() and self.start_console_tif_value is not None:
            self.start_console_tif_value.setText(tif_summary)
        self.start_console_pdf_value.setText(pdf_summary)
        self.start_console_agent_value.setText(agent_summary)
        self.start_console_workflow_value.setToolTip(self._agent_current_workflow_label())
        self.start_console_project_value.setToolTip(project_detail)
        self.start_console_images_value.setToolTip(image_detail)
        if self._is_tif_workflow_enabled() and self.start_console_tif_value is not None:
            self.start_console_tif_value.setToolTip(tif_detail)
        self.start_console_pdf_value.setToolTip(pdf_detail)
        self.start_console_agent_value.setToolTip(agent_summary)
        self.start_console_stl_note.setText(
            tr(
                "STL source stays as exported high-resolution 2D views; TaxaMask does not label 3D meshes.",
                self.current_lang,
            )
        )
        self._update_start_project_console_collapsed_state()

    def _start_console_collapsed_summary(self, project_summary, agent_summary):
        project_text = str(project_summary or "").replace("\n", " ").strip()
        agent_text = str(agent_summary or "").replace("\n", " ").strip()
        if len(project_text) > 34:
            project_text = f"{project_text[:33]}..."
        if len(agent_text) > 26:
            agent_text = f"{agent_text[:25]}..."
        return " · ".join([item for item in (project_text, agent_text) if item])

    def _start_console_project_summary(self):
        kind = getattr(self, "active_project_kind", "start")
        source_kind = getattr(self, "active_project_source_kind", kind)
        if kind == "tif":
            path = getattr(self.tif_project, "current_project_path", "") or ""
            if path:
                return tr("TIF project: {0}", self.current_lang).format(self._compact_project_path(path)), os.path.abspath(path)
            return tr("No active project", self.current_lang), ""
        if kind == "image":
            path = self._active_recent_project_path() or getattr(self.project, "current_project_path", "") or ""
            if source_kind == "stl":
                if path:
                    return tr("STL rendered-view project: {0}", self.current_lang).format(self._compact_project_path(path)), os.path.abspath(path)
                return tr("No active project", self.current_lang), ""
            if path:
                return tr("2D project: {0}", self.current_lang).format(self._compact_project_path(path)), os.path.abspath(path)
            return tr("No active project", self.current_lang), ""

        last_project = self.config.get("last_project_path", "") or ""
        if last_project:
            return tr("Recent project: {0}", self.current_lang).format(self._compact_project_path(last_project)), os.path.abspath(last_project)
        return tr("Repository only; no research project selected", self.current_lang), REPO_ROOT

    def _compact_project_path(self, path):
        text = str(path or "").strip()
        if not text:
            return ""
        name = os.path.basename(os.path.normpath(text))
        parent = os.path.basename(os.path.dirname(os.path.normpath(text)))
        display = f"{parent}/{name}" if parent else name
        max_chars = 48
        if len(display) <= max_chars:
            return display
        keep_left = 18
        keep_right = max(12, max_chars - keep_left - 3)
        return f"{display[:keep_left]}...{display[-keep_right:]}"

    def _start_console_image_summary(self):
        images = list((self.project.project_data or {}).get("images", []))
        labels = (self.project.project_data or {}).get("labels", {})
        labeled_count = 0
        stl_count = 0
        for image_path in images:
            entry = labels.get(image_path, {}) if isinstance(labels, dict) else {}
            if isinstance(entry, dict) and entry.get("parts"):
                labeled_count += 1
            provenance = self.project.get_image_provenance(image_path)
            if provenance.get("source_type") == "stl_rendered_view":
                stl_count += 1
        summary = tr("{0} image(s), {1} labeled, {2} STL rendered 2D view(s)", self.current_lang).format(
            len(images),
            labeled_count,
            stl_count,
        )
        detail = tr("2D/STL images", self.current_lang) + f": {len(images)}; labeled: {labeled_count}; STL rendered 2D views: {stl_count}"
        return summary, detail

    def _start_console_tif_summary(self):
        specimens = list((self.tif_project.project_data or {}).get("specimens", []))
        manual_truth_count = 0
        for specimen in specimens:
            manual = ((specimen.get("labels") or {}) if isinstance(specimen, dict) else {}).get("manual_truth") or {}
            if manual.get("path"):
                manual_truth_count += 1
        try:
            train_ready_count = len(self.tif_project.list_train_ready_specimens())
        except Exception:
            train_ready_count = sum(
                1
                for specimen in specimens
                if isinstance(specimen, dict) and (specimen.get("train_ready") or specimen.get("review_status") == "train_ready")
            )
        summary = tr("{0} specimen(s), {1} train-ready, {2} with manual_truth", self.current_lang).format(
            len(specimens),
            train_ready_count,
            manual_truth_count,
        )
        detail = tr("TIF specimens", self.current_lang) + f": {len(specimens)}; train-ready: {train_ready_count}; manual_truth: {manual_truth_count}"
        return summary, detail

    def _start_console_pdf_summary(self):
        skill_path = os.path.join(REPO_ROOT, ".lab-agent", "skills", "taxamask-pdf-evidence", "SKILL.md")
        if not os.path.exists(skill_path):
            return tr("PDF evidence skill missing", self.current_lang), skill_path
        candidates = 0
        for image_path in (self.project.project_data or {}).get("images", []):
            provenance = self.project.get_image_provenance(image_path)
            if self._is_pdf_candidate_provenance(provenance):
                entry = (self.project.project_data or {}).get("labels", {}).get(image_path, {})
                if not isinstance(entry, dict) or entry.get("status") != "labeled":
                    candidates += 1
        summary = tr("PDF evidence skill ready; {0} review candidate(s)", self.current_lang).format(candidates)
        detail = f"{summary}\n{skill_path}"
        return summary, detail

    def _is_pdf_candidate_provenance(self, provenance):
        if not isinstance(provenance, dict):
            return False
        source_type = str(provenance.get("source_type", "") or "").strip()
        return source_type in {"pdf_candidate", "pdf_candidate_crop"}

    def _start_console_agent_status(self):
        panel = getattr(self, "agent_panel", None)
        if panel is None or not panel.is_running():
            return tr("Ant-Code stopped", self.current_lang)
        return tr("Ant-Code ready", self.current_lang)

    def _agent_current_workflow_label(self):
        kind = getattr(self, "active_project_kind", "start")
        if kind == "tif":
            return tr("TIF Volume Workflow", self.current_lang)
        if kind == "image":
            return tr("2D/STL Morphology Workflow", self.current_lang)
        return tr("Start Center", self.current_lang)

    def _agent_current_project_label(self):
        if getattr(self, "active_project_kind", "start") == "tif":
            path = getattr(self.tif_project, "current_project_path", "") or ""
        elif getattr(self, "active_project_kind", "start") == "image":
            path = self._active_recent_project_path() or getattr(self.project, "current_project_path", "") or ""
        else:
            path = self.config.get("last_project_path", "") or ""
        return path if path else tr("No active project", self.current_lang)

    AGENT_CONTEXT_TEXT_LIMIT = 320
    AGENT_CONTEXT_REFERENCE_TEXT_LIMIT = 960
    AGENT_CONTEXT_LOG_LINES = 6
    AGENT_CONTEXT_LOG_LINE_LIMIT = 160
    AGENT_CONTEXT_TOTAL_LIMIT = 5200

    def _recent_text_excerpt(self, widget, line_limit=AGENT_CONTEXT_LOG_LINES):
        if widget is None or not hasattr(widget, "toPlainText"):
            return ""
        lines = []
        for line in widget.toPlainText().splitlines()[-line_limit:]:
            lines.append(self._agent_context_text(line, self.AGENT_CONTEXT_LOG_LINE_LIMIT))
        return "\n".join(lines)

    def _agent_context_text(self, value, limit=AGENT_CONTEXT_TEXT_LIMIT):
        text = str(value or "").replace("\r", " ").strip()
        if len(text) <= limit:
            return text
        return f"{text[:limit]}... [truncated]"

    def _compact_agent_context(self, context):
        context = enrich_agent_context(context)
        allowed_keys = (
            "source_workbench",
            "project_type",
            "project_source_kind",
            "project_path",
            "review_project_path",
            "diagnostic_route",
            "diagnostic_focus",
            "health_check_summary",
            "validation_errors",
            "llm_context_refs",
            "source_code_refs",
            "artifact_hints",
            "safety_notes",
            "suggested_agent_action",
            "agent_route_source",
            "active_specimen_id",
            "active_volume_scope",
            "active_part_id",
            "active_reslice_id",
            "active_part_parent_bbox_zyx",
            "active_part_group_tags",
            "active_image_path",
            "active_label_role",
            "active_slice_axis",
            "active_slice_position",
            "active_volume_shape_zyx",
            "active_volume_spacing_zyx",
            "active_label_shape_zyx",
            "active_label_schema_id",
            "selected_part",
            "selected_material_id",
            "display_mode",
            "train_ready_status",
            "train_ready_reasons",
            "train_ready_part_sample_count",
            "train_ready_top_level_sample_count",
            "training_selection_scope",
            "training_sample_rule",
            "registered_tif_model_count",
            "selected_tif_model_id",
            "selected_model_manifest",
            "tif_backend_id",
            "tif_backend_python",
            "tif_backend_command_presence",
            "backend_run_active",
            "backend_action",
            "backend_run_dir",
            "backend_result_json",
            "predict_group_filter",
            "predict_group_filter_label",
            "predict_target_summary",
            "predict_selected_target_count",
            "predict_selected_targets",
            "tif_task_summary",
            "tif_state_summary",
            "preview_resource_summary",
            "local_axis_state_summary",
            "volume_lifecycle_summary",
            "volume_renderer",
            "volume_renderer_label",
            "volume_render_mode",
            "volume_projection_mode",
            "volume_mask_mode",
            "volume_density_cutoff",
            "volume_density_opacity",
            "volume_texture_target_dim",
            "volume_ray_samples",
            "volume_clarity_mode",
            "volume_detail_enhancement",
            "volume_tone_curve",
            "volume_shader_quality",
            "volume_surface_refine",
            "volume_clip_plane",
            "volume_clip_plane_depth",
            "volume_roi_high_detail",
            "volume_roi_inspect",
            "volume_roi_scale",
            "volume_roi_budget",
            "volume_inside_depth",
            "volume_front_cut",
            "volume_zoom",
            "volume_pan",
            "volume_yaw_pitch",
            "volume_gpu_warning",
            "volume_status_overlay",
            "volume_performance_diagnosis",
            "volume_uploaded_gb",
            "volume_upload_ms",
            "volume_draw_ms",
            "volume_uploaded_shape_zyx",
            "volume_texture_sampling",
            "volume_display_scaling",
            "tif_next_requirement",
            "tif_requirement_doc",
            "pdf_acquisition_stage",
            "harvest_skill",
            "harvest_skill_path",
            "harvest_outputs",
            "harvest_safety_boundary",
            "screener_profile",
            "figure_profile",
            "part_description_profile",
            "screening_mode",
            "text_llm_key_configured",
            "text_llm_base_url_configured",
            "text_llm_model",
            "text_llm_api_protocol",
            "multimodal_llm_uses_text_provider",
            "multimodal_llm_key_configured",
            "multimodal_llm_base_url_configured",
            "multimodal_llm_model",
            "multimodal_llm_api_protocol",
            "pdf_source_dir",
            "screening_output_dir",
            "extract_input_dir",
            "extract_result_folder",
            "extract_db_name",
            "extract_db_path",
            "multimodal_enabled",
            "settings_scope",
            "settings_question_focus",
            "advanced_extension_scope",
            "language",
            "theme",
            "startup_behavior",
            "project_autosave_interval_sec",
            "runtime_device",
            "model_backend",
            "active_model_profile_id",
            "active_model_profile_name",
            "parent_backend",
            "child_backend",
            "route_backend_summary",
            "parent_model_source",
            "parent_model_source_label",
            "default_child_expert",
            "default_child_expert_label",
            "default_child_route_backend",
            "route_specific_backend_count",
            "route_specific_backend_summary",
            "backend_id",
            "display_name",
            "python_executable",
            "export_formats",
            "external_backend_id",
            "external_display_name",
            "external_python",
            "parent_prepare_command_present",
            "parent_train_command_present",
            "parent_predict_command_present",
            "parent_prepare_command_has_contract",
            "parent_train_command_has_contract",
            "parent_predict_command_has_contract",
            "parent_model_manifest_present",
            "child_extension_id",
            "child_extension_display_name",
            "child_extension_python",
            "child_predict_command_present",
            "child_train_command_present",
            "child_predict_command_has_contract",
            "child_train_command_has_contract",
            "child_model_manifest_present",
            "prepare_command_present",
            "train_command_present",
            "predict_command_present",
            "prepare_command_has_contract",
            "train_command_has_contract",
            "predict_command_has_contract",
            "model_manifest_present",
            "locator_scope_count",
            "parent_box_ratio_count",
            "recent_log_excerpt",
        )
        compact = {}
        for key in allowed_keys:
            value = (context or {}).get(key)
            if not value:
                continue
            limit = self.AGENT_CONTEXT_TEXT_LIMIT
            if key in ("llm_context_refs", "source_code_refs", "artifact_hints", "safety_notes"):
                limit = self.AGENT_CONTEXT_REFERENCE_TEXT_LIMIT
            if key == "recent_log_excerpt":
                limit = self.AGENT_CONTEXT_LOG_LINES * self.AGENT_CONTEXT_LOG_LINE_LIMIT
            compact[key] = self._agent_context_text(value, limit)
        context_policy = (
            "Only compact field indexes, route hints, and short log excerpts are provided. "
            "Do not assume full project data is loaded; read the referenced docs/source/artifacts only when needed."
        )
        text_budget = len("context_policy") + len(context_policy)
        limited = {"context_policy": context_policy}
        for key, value in compact.items():
            text = str(value)
            next_budget = text_budget + len(key) + len(text)
            if next_budget > self.AGENT_CONTEXT_TOTAL_LIMIT:
                limited[key] = self._agent_context_text(text, max(80, self.AGENT_CONTEXT_TOTAL_LIMIT - text_budget - len(key)))
                break
            limited[key] = value
            text_budget = next_budget
        return limited

    def _collect_image_workbench_agent_context(self):
        model_context = self._active_model_profile_context()
        route_backends = []
        for route in self._active_project_route_manifest().get("routes", []):
            if not isinstance(route, dict):
                continue
            parent = str(route.get("parent") or "")
            child = str(route.get("child") or "")
            backend = str(route.get("expert_backend") or "")
            if parent and child:
                route_backends.append(f"{parent}->{child}:{backend or 'unknown'}")
        active_profile = _active_profile_from_manager(self.project)
        return {
            "source_workbench": "labeling",
            "project_type": "2d_stl",
            "project_source_kind": getattr(self, "active_project_source_kind", "image"),
            "project_path": self._active_recent_project_path() or getattr(self.project, "current_project_path", "") or "",
            "review_project_path": getattr(self.project, "current_project_path", "") or "",
            "active_image_path": self.current_image or "",
            "selected_part": self._current_part_name() or "",
            "active_model_profile_id": model_context.get("active_profile_id", ""),
            "active_model_profile_name": active_profile.get("display_name", ""),
            "parent_backend": model_context.get("parent_backend", ""),
            "child_backend": model_context.get("child_backend", ""),
            "route_backend_summary": "; ".join(route_backends[:12]),
            "recent_log_excerpt": self._recent_text_excerpt(getattr(self, "log_console", None)),
        }

    def _collect_blink_agent_context(self):
        active_session = getattr(self.blink_lab, "active_session", None) or {}
        return {
            "source_workbench": "blink",
            "project_type": "2d_stl",
            "project_source_kind": getattr(self, "active_project_source_kind", "image"),
            "project_path": self._active_recent_project_path() or getattr(self.project, "current_project_path", "") or "",
            "review_project_path": getattr(self.project, "current_project_path", "") or "",
            "active_image_path": getattr(self.blink_lab, "current_image_path", None) or self.current_image or "",
            "selected_part": getattr(self.blink_lab, "session_target_part", None) or "",
            "active_label_role": "blink_session" if active_session else "",
            "recent_log_excerpt": self._recent_text_excerpt(getattr(self.blink_lab, "training_log_console", None)),
        }

    def _pdf_agent_prompt(self):
        project_hint = self._agent_current_project_label()
        pdf_summary, _pdf_detail = self._start_console_pdf_summary()
        return (
            "请按 TaxaMask 的 PDF evidence workflow 作为分阶段向导接管一次 PDF 文献处理任务。"
            "这个流程面向各种分类学研究者，不要默认用户研究蚂蚁，也不要默认当前筛选配置或图文提取配置已经合适。\n\n"
            "请先读取并遵守这些本地规则/skill：\n"
            "- ANTCODE.md\n"
            "- .lab-agent/memory.md\n"
            "- vendor/ant-code/config/skills/taxonomy-pdf-harvest/SKILL.md\n"
            "- .lab-agent/skills/taxamask-pdf-evidence/SKILL.md\n\n"
            "当前现场：\n"
            f"- 当前项目：{project_hint}\n"
            f"- PDF 状态：{pdf_summary}\n"
            "- PDF 筛选依赖文本 LLM key/model；启用多模态图文复核时还需要可用的视觉模型配置。\n\n"
            "请不要一次性输出全流程长说明。请按五个阶段推进，每轮只处理当前阶段，最多问 3 个问题：\n"
            "0. 文献/PDF 来源判断：用户已经有 PDF 文件夹，还是需要先用 taxonomy-pdf-harvest 合法采集开放 PDF。\n"
            "1. key/model 就绪检查。\n"
            "2. 目标类群与 PDF 筛选条件适配。\n"
            "3. figure/caption 数据处理与图文复核条件适配。\n"
            "4. 跑通流程、说明产物位置和复核/导入边界。\n\n"
            "如果用户还没有 PDF，请先停在第 0 阶段，按 taxonomy-pdf-harvest 的边界规划检索/下载："
            "只使用开放元数据和合法暴露的 PDF 链接，不使用 Sci-Hub、LibGen、付费墙绕过、验证码绕过或登录态抓取。"
            "第 0 阶段的关键产物是 records.csv、doi_list.txt、summary.json、download_manifest.csv 和 pdfs/，"
            "这些是文献来源和下载审计材料，不是训练真值。\n\n"
            "请优先使用需求确认式交互：给我简短选项或短问题让我确认，不要用长段说明替代确认。"
            "现在先停在第 0 阶段：只确认我是否已经有待筛选 PDF 文件夹，还是需要先按目标类群合法采集开放 PDF；"
            "若已有 PDF，再进入第 1 阶段确认文本 LLM key、base URL、model、API 协议和必要的视觉模型配置。"
            "不要要求我在聊天里粘贴真实 key，不要提前展开后面复杂配置。"
        )

    def open_agent_for_pdf_workflow(self):
        prompt = self._pdf_agent_prompt()
        self.active_project_kind = "start"
        self._apply_project_mode_tabs()
        self._update_start_center_texts()
        if hasattr(self, "agent_panel"):
            self.agent_panel.update_runtime_status(
                model_status=tr("Local task cards", self.current_lang),
                workflow=tr("PDF evidence workflow", self.current_lang),
                project=self._agent_current_project_label(),
                state=tr("Idle", self.current_lang),
            )
            self.agent_panel.set_prompt_text(prompt)
            if not self.agent_panel.is_running():
                self.agent_panel.start_dashboard()

    def open_agent_from_context(self, context=None):
        payload = dict(context or {})
        source_widget = self.tabs.currentWidget() if hasattr(self, "tabs") else None
        if not payload and hasattr(self, "tabs") and self.tabs.currentWidget() is self.pdf_widget:
            payload = self.pdf_widget.get_agent_context()
        if not payload and hasattr(self, "tabs") and self.tabs.currentWidget() is self.blink_lab:
            payload = self._collect_blink_agent_context()
        if not payload and hasattr(self, "tabs") and self.tabs.currentWidget() is self.tif_workbench:
            payload = self.tif_workbench.get_agent_context()
        if not payload:
            payload = self._collect_image_workbench_agent_context()
        payload = self._compact_agent_context(payload)
        if source_widget is getattr(self, "tif_workbench", None) and hasattr(self.tif_workbench, "prepare_for_agent_panel"):
            self.tif_workbench.prepare_for_agent_panel()
        self.active_project_kind = "start"
        self._apply_project_mode_tabs()
        self._update_start_center_texts()
        if hasattr(self, "agent_panel"):
            self.agent_panel.set_context(payload, announce=True)
            self.agent_panel.update_runtime_status(
                model_status=tr("Local task cards", self.current_lang),
                workflow=str(payload.get("source_workbench") or self._agent_current_workflow_label()),
                project=str(payload.get("project_path") or self._agent_current_project_label()),
                state=tr("Idle", self.current_lang),
            )
            if not self.agent_panel.is_running():
                self.agent_panel.start_dashboard()

    def return_to_start_center_with_context(self):
        self._show_start_center()

    def _open_workflow_from_agent(self, workflow):
        if workflow == "tif":
            if not self._is_tif_workflow_enabled():
                self._show_tif_workflow_unavailable()
                return
            self.enter_tif_workflow()
            return
        self.enter_image_workflow()

    def _open_model_settings_from_agent(self, workflow):
        if workflow == "tif":
            if not self._is_tif_workflow_enabled():
                self._show_tif_workflow_unavailable()
                return
            self.open_tif_model_settings()
            return
        self.open_stl_model_settings()

    def enter_image_workflow(self):
        self.active_project_kind = "image"
        self._refresh_project_bound_views()
        self.tabs.setCurrentWidget(self.workbench_widget)
        self.ensure_2d_stl_models_preloaded()
        self.log(tr("Opened 2D/STL workflow.", self.current_lang))

    def enter_tif_workflow(self):
        if not self._is_tif_workflow_enabled():
            self._show_tif_workflow_unavailable()
            return
        self.active_project_kind = "tif"
        self._refresh_project_bound_views()
        self.tabs.setCurrentWidget(self.tif_workbench)
        self.log(tr("Opened TIF volume workflow.", self.current_lang))

    def _default_outputs_root(self):
        return os.path.abspath(os.path.join(REPO_ROOT, DEFAULT_OUTPUTS_DIR_NAME))

    def _ensure_default_output_subdir(self, *parts):
        path = os.path.join(self._default_outputs_root(), *parts)
        os.makedirs(path, exist_ok=True)
        return path

    def _default_2d_stl_projects_root(self):
        return self._ensure_default_output_subdir(DEFAULT_2D_STL_PROJECTS_DIR_NAME)

    def _default_tif_projects_root(self):
        return self._ensure_default_output_subdir(DEFAULT_TIF_PROJECTS_DIR_NAME)

    def _default_startup_project_dir(self):
        return self._ensure_default_output_subdir(DEFAULT_2D_STL_PROJECTS_DIR_NAME, DEFAULT_STARTUP_PROJECT_DIR_NAME)

    def _startup_project_manifest_path(self):
        return os.path.join(self._default_startup_project_dir(), f"{DEFAULT_PROJECT_NAME}.sqlite_manifest.json")

    def _startup_legacy_json_project_path(self):
        return os.path.join(self._default_startup_project_dir(), f"{DEFAULT_PROJECT_NAME}.json")

    def _open_or_create_startup_project(self):
        manifest_path = self._startup_project_manifest_path()
        legacy_json_path = self._startup_legacy_json_project_path()
        if os.path.exists(manifest_path):
            self.project.load_project(manifest_path)
            return
        if os.path.exists(legacy_json_path):
            self.open_project_path(legacy_json_path)
            return
        self.project.create_project(
            DEFAULT_PROJECT_NAME,
            self._default_startup_project_dir(),
            template_id=DEFAULT_PROJECT_TEMPLATE_ID,
        )

    def _default_project_dialog_dir(self, project_kind):
        if str(project_kind or "").lower() == "tif":
            return self._default_tif_projects_root()
        return self._default_2d_stl_projects_root()

    def _current_2d_project_dir(self):
        project_path = getattr(self.project, "current_project_path", "") or ""
        if project_path:
            return os.path.dirname(os.path.abspath(project_path))
        return self._default_2d_stl_projects_root()

    def _default_2d_export_dir(self):
        path = os.path.join(self._current_2d_project_dir(), "exports")
        os.makedirs(path, exist_ok=True)
        return path

    def _default_vlm_preannotation_dir(self):
        path = os.path.join(self._current_2d_project_dir(), "vlm_preannotation")
        os.makedirs(path, exist_ok=True)
        return path

    def _default_open_project_dir(self):
        candidates = [
            self.config.get("last_project_path", ""),
            getattr(self, "active_project_entry_path", ""),
            getattr(self.project, "current_project_path", ""),
        ]
        if self._is_tif_workflow_enabled():
            candidates.append(getattr(self.tif_project, "current_project_path", ""))
        for candidate in candidates:
            if not candidate:
                continue
            path = os.path.abspath(str(candidate))
            if self._path_is_startup_project(path):
                continue
            folder = path if os.path.isdir(path) else os.path.dirname(path)
            if folder and os.path.isdir(folder) and not self._path_is_inside_program_package(folder):
                return folder
        return self._ensure_default_output_subdir()

    def _path_is_startup_project(self, path_text):
        try:
            startup_dir = self._default_startup_project_dir()
            path = os.path.abspath(str(path_text))
            folder = path if os.path.isdir(path) else os.path.dirname(path)
            return os.path.commonpath([startup_dir, folder]) == startup_dir
        except (TypeError, ValueError):
            return False

    def _path_is_inside_program_package(self, path_text):
        try:
            return os.path.commonpath([PACKAGE_DIR, os.path.abspath(str(path_text))]) == PACKAGE_DIR
        except (TypeError, ValueError):
            return False

    def open_last_project(self):
        last_project = self.config.get("last_project_path", "")
        if not last_project or not os.path.exists(last_project):
            return
        if self._is_tif_project_file(last_project) and not self._is_tif_workflow_enabled():
            self._show_tif_workflow_unavailable()
            return
        self.open_project_path(last_project)

    def closeEvent(self, event):
        if getattr(self, "image_import_thread", None) is not None and self.image_import_thread.isRunning():
            QMessageBox.information(
                self,
                tr("Image Import", self.current_lang),
                tr("Image import is running. Please wait for it to finish before closing TaxaMask.", self.current_lang),
            )
            event.ignore()
            return
        if getattr(self, "external_batch_inference_thread", None) is not None and self.external_batch_inference_thread.isRunning():
            QMessageBox.information(
                self,
                tr("Batch Inference", self.current_lang),
                tr("Batch inference is running. Please wait for it to finish before closing TaxaMask.", self.current_lang),
            )
            event.ignore()
            return
        if getattr(self, "vlm_preannotation_run_active", False):
            QMessageBox.information(
                self,
                tr("VLM Pre-Annotate", self.current_lang),
                tr(
                    "VLM stop requested. Remaining queued images were cancelled; waiting for active request(s) to finish.",
                    self.current_lang,
                ),
            )
            self.request_stop_vlm_preannotation(confirm=False)
            event.ignore()
            return
        if getattr(self, "external_training_thread", None) is not None and self.external_training_thread.isRunning():
            QMessageBox.information(
                self,
                tr("Training", self.current_lang),
                tr("External backend training is running. Please wait for it to finish before closing TaxaMask.", self.current_lang),
            )
            event.ignore()
            return
        self._shutdown_background_workers()
        self._flush_pending_project_save(defer_for_navigation=False)
        recent_project_path = self._active_recent_project_path()
        if recent_project_path:
            self.config.set("last_project_path", recent_project_path)
        self.config.save()
        event.accept()
        os._exit(0)

    def _active_recent_project_path(self):
        active_kind = getattr(self, "active_project_kind", "start")
        source_kind = getattr(self, "active_project_source_kind", active_kind)
        if active_kind == "tif":
            return getattr(self.tif_project, "current_project_path", None) or ""
        if active_kind == "image":
            if source_kind == "stl":
                return getattr(self.stl_project, "current_project_path", None) or getattr(self, "active_project_entry_path", "")
            return getattr(self.project, "current_project_path", None) or getattr(self, "active_project_entry_path", "")
        return ""

    def _shutdown_background_workers(self):
        tif_workbench = getattr(self, "tif_workbench", None)
        if tif_workbench is not None and hasattr(tif_workbench, "release_volume_renderer"):
            try:
                tif_workbench.release_volume_renderer()
            except Exception:
                pass
        agent_panel = getattr(self, "agent_panel", None)
        if agent_panel is not None and hasattr(agent_panel, "stop_dashboard"):
            try:
                agent_panel.stop_dashboard()
            except Exception:
                pass
        if self.sam_thread and self.sam_thread.isRunning():
            self.sam_thread.quit()
            self.sam_thread.wait(1000)
        thread = getattr(self, "image_import_thread", None)
        if thread is not None and thread.isRunning():
            thread.wait(30000)
        thread = getattr(self, "parts_model_preload_thread", None)
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)

    def destroy(self, destroyWindow=True, destroySubWindows=True):
        self._shutdown_background_workers()
        return super().destroy(destroyWindow, destroySubWindows)

    def _schedule_project_save(self, reason="pending_change", **context):
        self.project_save_pending = True
        if context:
            self.project_save_context = {"reason": reason, **context}
        self.project_save_timer.start(self.project_autosave_delay_ms)

    def _defer_project_save_for_active_navigation(self):
        if not self.project_save_pending:
            return
        self.project_last_image_switch_at = time.monotonic()
        self.project_save_timer.start(self.project_autosave_delay_ms)

    def _flush_pending_project_save(self, force=False, defer_for_navigation=True):
        if self.project_save_timer.isActive():
            self.project_save_timer.stop()

        if not self.project.current_project_path:
            self.project_save_pending = False
            self.project_save_context = {}
            return False

        if not force and not self.project_save_pending:
            return False

        if defer_for_navigation and not force and self.project_last_image_switch_at:
            elapsed_ms = (time.monotonic() - self.project_last_image_switch_at) * 1000.0
            if elapsed_ms < self.project_save_navigation_idle_ms:
                remaining_ms = max(
                    250,
                    int(self.project_save_navigation_idle_ms - elapsed_ms),
                )
                self.project_save_timer.start(remaining_ms)
                return False

        context = getattr(self, "project_save_context", {}) or {}
        try:
            try:
                self.project.save_project(force=force)
            except TypeError as exc:
                if "force" not in str(exc):
                    raise
                self.project.save_project()
        except Exception:
            runtime_log_exception(
                "project_save_failed",
                *sys.exc_info(),
            )
            runtime_log_event(
                "project_save_failed_context",
                project=getattr(self.project, "current_project_path", ""),
                image_count=len(self.project.project_data.get("images", []) or []),
                label_count=len(self.project.project_data.get("labels", {}) or {}),
                **context,
            )
            raise
        if context:
            runtime_log_event(
                "project_save_ok",
                project=getattr(self.project, "current_project_path", ""),
                image_count=len(self.project.project_data.get("images", []) or []),
                label_count=len(self.project.project_data.get("labels", {}) or {}),
                **context,
            )
        self.project_save_pending = False
        self.project_save_context = {}
        return True

    def refresh_model_list(self):
        current_locator = self.combo_locator.currentData() if self.combo_locator.count() else None
        current_segmenter = self.combo_segmenter.currentData() if self.combo_segmenter.count() else None
        self.combo_locator.blockSignals(True)
        self.combo_segmenter.blockSignals(True)
        self.combo_locator.clear()
        self.combo_segmenter.clear()
        
        if not self.engine:
            return
            
        import glob
        parent_model_notes = load_parent_model_notes(self.engine.weights_dir)
        # 1. Populate Locators
        loc_files = glob.glob(os.path.join(self.engine.weights_dir, "locator_*.pth"))
        # Format: "20260105_1105"
        loc_timestamps = sorted([os.path.basename(f).replace("locator_", "").replace(".pth", "") for f in loc_files], reverse=True)
        
        if loc_timestamps:
            for ts in loc_timestamps:
                self.combo_locator.addItem(self._build_locator_combo_label(ts, parent_model_notes), ts)
            locator_index = self.combo_locator.findData(current_locator)
            if locator_index < 0:
                locator_index = 0
            self.combo_locator.setCurrentIndex(locator_index)
        else:
            self.combo_locator.addItem(tr("No Locators Found", self.current_lang), "__no_locator__")
            
        # 2. Populate Segmenters
        self.combo_segmenter.addItem(tr("Base SAM (Original)", self.current_lang), "BASE_SAM")
        
        seg_files = glob.glob(os.path.join(self.engine.weights_dir, "sam_decoder_lora_*.pth"))
        seg_timestamps = sorted([os.path.basename(f).replace("sam_decoder_lora_", "").replace(".pth", "") for f in seg_files], reverse=True)
        
        if seg_timestamps:
            for ts in seg_timestamps:
                self.combo_segmenter.addItem(self._build_segmenter_combo_label(ts, parent_model_notes), ts)
            
        # Default to Base SAM (Index 0) for safety/compatibility, or latest if user prefers?
        # User strategy: "配合原始的sam模型，先达到一个很好的效果". So default to Base SAM.
        segmenter_index = self.combo_segmenter.findData(current_segmenter)
        if segmenter_index < 0:
            segmenter_index = 0
        self.combo_segmenter.setCurrentIndex(segmenter_index)
        
        self.combo_locator.blockSignals(False)
        self.combo_segmenter.blockSignals(False)
        if getattr(self, "active_project_kind", "start") == "image":
            self._apply_locator_selection_to_runtime()
            self._apply_segmenter_selection_to_runtime()
        self.update_model_delete_button_states()

    def _selected_locator_timestamp(self):
        item_data = self.combo_locator.currentData() if self.combo_locator.count() else None
        if item_data in (None, "", "__no_locator__"):
            return None
        return str(item_data)

    def _selected_locator_display_text(self):
        if not self.combo_locator.count():
            return ""
        return str(self.combo_locator.currentText() or "").strip()

    def _parent_model_filename(self, model_kind, timestamp):
        ts = str(timestamp or "").strip()
        if not ts:
            return ""
        if model_kind == "locator":
            return f"locator_{ts}.pth"
        if model_kind == "segmenter":
            return f"sam_decoder_lora_{ts}.pth"
        return ""

    def _build_locator_combo_label(self, timestamp, parent_model_notes=None):
        ts = str(timestamp or "").strip()
        if not ts:
            return ts
        filename = self._parent_model_filename("locator", ts)
        notes = parent_model_notes if isinstance(parent_model_notes, dict) else load_parent_model_notes(getattr(self.engine, "weights_dir", ""))
        note = notes.get(filename, "")

        path = self._locator_model_path(ts)
        if not path or not os.path.exists(path):
            return format_parent_model_display_name(filename or ts, note)

        state_label = ""
        try:
            saved_state = torch.load(path, map_location="cpu")
        except Exception:
            pass
        else:
            checkpoint_meta = {}
            if isinstance(saved_state, dict) and isinstance(saved_state.get("meta"), dict):
                checkpoint_meta = saved_state.get("meta") or {}

            saved_resolution = checkpoint_meta.get("locator_size")
            legacy_resolution = checkpoint_meta.get("locator_resolution")
            if saved_resolution is None and legacy_resolution is not None:
                try:
                    legacy_side = max(1, int(legacy_resolution))
                except Exception:
                    legacy_side = 512
                saved_resolution = [legacy_side, legacy_side]

            if saved_resolution is None:
                state_label = "legacy-512"
            else:
                try:
                    size_pair = (max(1, int(saved_resolution[0])), max(1, int(saved_resolution[1])))
                except Exception:
                    size_pair = (512, 512)
                state_label = f"exact {format_size_pair(size_pair)}"
        return format_parent_model_display_name(filename, note, details=state_label)

    def _build_segmenter_combo_label(self, timestamp, parent_model_notes=None):
        ts = str(timestamp or "").strip()
        if not ts:
            return ts
        filename = self._parent_model_filename("segmenter", ts)
        notes = parent_model_notes if isinstance(parent_model_notes, dict) else load_parent_model_notes(getattr(self.engine, "weights_dir", ""))
        return format_parent_model_display_name(filename, notes.get(filename, ""))

    def _selected_segmenter_timestamp(self):
        item_data = self.combo_segmenter.currentData() if self.combo_segmenter.count() else None
        if item_data in (None, "", "BASE_SAM", "No Segmenters Found"):
            return None
        return str(item_data)

    def _active_project_route_manifest(self):
        return self.project.get_cascade_routes()

    def _active_model_profile_context(self):
        active_profile = _active_profile_from_manager(self.project)
        parent_backend = active_profile.get("parent_backend", {}) if isinstance(active_profile.get("parent_backend"), dict) else {}
        child_defaults = active_profile.get("child_backend_defaults", {}) if isinstance(active_profile.get("child_backend_defaults"), dict) else {}
        return {
            "active_profile_id": str(active_profile.get("profile_id") or ""),
            "parent_backend": str(parent_backend.get("backend_type") or ""),
            "child_backend": str(child_defaults.get("backend_type") or ""),
        }

    def _active_external_backend_config(self):
        active_profile = _active_profile_from_manager(self.project)
        parent_backend = active_profile.get("parent_backend", {}) if isinstance(active_profile.get("parent_backend"), dict) else {}
        if parent_backend.get("backend_type") == PARENT_BACKEND_EXTERNAL:
            return sanitize_external_backend_config(parent_backend.get("external_backend", {}))
        return sanitize_external_backend_config(self.external_backend_config)

    def _selected_route_entry(self):
        panel = getattr(self, "route_settings_panel", None)
        if panel is None:
            return None
        return panel._selected_route_entry()

    def _route_runtime_status(self, route_entry):
        panel = getattr(self, "route_settings_panel", None)
        if panel is None:
            return ui_text("Unknown", self.current_lang)
        return panel._route_runtime_status(route_entry)

    def refresh_route_table(self):
        panel = getattr(self, "route_settings_panel", None)
        if panel is not None:
            panel.refresh_route_table()
        if hasattr(self, "part_list"):
            self._refresh_part_tree(self._current_part_name())
        if hasattr(self, "blink_refine_panel"):
            self._refresh_blink_refine_state()

    def update_route_action_buttons(self):
        panel = getattr(self, "route_settings_panel", None)
        if panel is not None:
            panel.update_action_buttons()

    def _refresh_project_bound_views(self):
        self._apply_project_mode_tabs()
        if getattr(self, "active_project_kind", "image") == "start":
            self._update_start_center_texts()
            if hasattr(self, "tabs"):
                self.tabs.setCurrentWidget(self.start_center_widget)
            return
        if getattr(self, "active_project_kind", "image") == "tif":
            if hasattr(self, "tif_workbench"):
                self.tif_workbench.refresh_project()
            if hasattr(self, "tabs"):
                self.tabs.setCurrentWidget(self.tif_workbench)
            return
        self.refresh_file_list()
        self.refresh_ui()
        self.refresh_route_table()

    def _project_image_count(self):
        try:
            return len([img for img in self.project.project_data.get("images", []) if img])
        except Exception:
            return 0

    def _prepare_image_list_for_project_open(self):
        image_count = self._project_image_count()
        self._image_list_state_cache = None
        should_collapse = image_count >= LARGE_PROJECT_OPEN_LIGHTWEIGHT_THRESHOLD

        for group_key, _label in self._all_image_group_definitions():
            self.image_list_group_collapsed[str(group_key)] = should_collapse
        if not should_collapse:
            return False
        self.current_image = None
        self.log(
            tr(
                "Large project detected ({0} images). The image groups are collapsed for faster opening; expand a group when you are ready to review images.",
                self.current_lang,
            ).format(image_count)
        )
        return True

    def _preload_2d_stl_models_after_open(self):
        if getattr(self, "active_project_kind", "image") != "image":
            return
        if self._project_image_count() >= LARGE_PROJECT_OPEN_LIGHTWEIGHT_THRESHOLD:
            self.log(
                tr(
                    "Large project opened without startup model preloading. Models will load when auto annotation or training starts.",
                    self.current_lang,
                )
            )
            return
        QTimer.singleShot(0, self.ensure_2d_stl_models_preloaded)

    def _ensure_tab_visible(self, widget, title):
        if not hasattr(self, "tabs") or widget is None:
            return
        if self.tabs.indexOf(widget) < 0:
            self.tabs.addTab(widget, title)

    def _remove_tab_if_present(self, widget):
        if not hasattr(self, "tabs") or widget is None:
            return
        index = self.tabs.indexOf(widget)
        if index >= 0:
            self.tabs.removeTab(index)

    def _apply_project_mode_tabs(self):
        if not hasattr(self, "tabs"):
            return
        if getattr(self, "active_project_kind", "image") == "start":
            for widget in (self.workbench_widget, self.blink_lab, self.tif_workbench, self.pdf_widget):
                self._remove_tab_if_present(widget)
            self._ensure_tab_visible(self.start_center_widget, tr("Start Center", self.current_lang))
            self.tabs.setCurrentWidget(self.start_center_widget)
            return
        if getattr(self, "active_project_kind", "image") == "tif":
            self._remove_tab_if_present(self.start_center_widget)
            self._remove_tab_if_present(self.workbench_widget)
            self._remove_tab_if_present(self.blink_lab)
            self._remove_tab_if_present(self.pdf_widget)
            self._ensure_tab_visible(self.tif_workbench, tr("TIF Volume Workbench", self.current_lang))
            self.tabs.setCurrentWidget(self.tif_workbench)
            return
        self._remove_tab_if_present(self.start_center_widget)
        self._remove_tab_if_present(self.tif_workbench)
        self._remove_tab_if_present(self.blink_lab)
        self._ensure_tab_visible(self.workbench_widget, tr("Labeling Workbench", self.current_lang))
        if self.tabs.currentWidget() is None or self.tabs.currentWidget() is self.tif_workbench:
            self.tabs.setCurrentWidget(self.workbench_widget)

    def _is_tif_project_file(self, path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception:
            return False
        if self._is_tif_sqlite_project_manifest_payload(payload):
            return True
        return (
            isinstance(payload, dict)
            and payload.get("schema_version") == TIF_PROJECT_SCHEMA_VERSION
            and payload.get("project_type") == TIF_PROJECT_TYPE
        )

    def _is_stl_project_file(self, path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception:
            return False
        return (
            isinstance(payload, dict)
            and payload.get("schema_version") == STL_PROJECT_SCHEMA_VERSION
            and payload.get("project_type") == STL_PROJECT_TYPE
        )

    def _read_project_probe_payload(self, path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    def _is_sqlite_project_manifest_payload(self, payload):
        return (
            isinstance(payload, dict)
            and payload.get("schema_version") == PROJECT_MANIFEST_SCHEMA_VERSION
            and payload.get("storage_backend") == SQLITE_BACKEND
        )

    def _is_tif_sqlite_project_manifest_payload(self, payload):
        return self._is_sqlite_project_manifest_payload(payload) and payload.get("project_type") == TIF_PROJECT_TYPE

    def _is_2d_sqlite_project_manifest_payload(self, payload):
        return self._is_sqlite_project_manifest_payload(payload) and payload.get("project_type") != TIF_PROJECT_TYPE

    def _is_legacy_2d_json_project_payload(self, payload):
        if not isinstance(payload, dict):
            return False
        if self._is_sqlite_project_manifest_payload(payload):
            return False
        if (
            payload.get("schema_version") in {TIF_PROJECT_SCHEMA_VERSION, STL_PROJECT_SCHEMA_VERSION}
            or payload.get("project_type") in {TIF_PROJECT_TYPE, STL_PROJECT_TYPE}
        ):
            return False
        project_keys = {"images", "labels", "taxonomy", "locator_scope", "project_template"}
        return bool(project_keys.intersection(payload.keys())) and (
            isinstance(payload.get("images", []), list)
            or isinstance(payload.get("labels", {}), dict)
        )

    def _is_legacy_2d_json_project_file(self, path):
        return self._is_legacy_2d_json_project_payload(self._read_project_probe_payload(path))

    def _candidate_manifest_paths_for_sqlite_database(self, path):
        database_path = os.path.abspath(str(path))
        directory = os.path.dirname(database_path) or "."
        filename = os.path.basename(database_path)
        candidates = []
        suffixes = [
            (".taxamask.sqlite", ".sqlite_manifest.json"),
            (".taxamask_tif.sqlite", ".tif_sqlite_manifest.json"),
        ]
        for db_suffix, manifest_suffix in suffixes:
            if filename.endswith(db_suffix):
                candidates.append(os.path.join(directory, f"{filename[:-len(db_suffix)]}{manifest_suffix}"))
        for name in os.listdir(directory) if os.path.isdir(directory) else []:
            if name.endswith(".sqlite_manifest.json") or name.endswith(".tif_sqlite_manifest.json"):
                candidates.append(os.path.join(directory, name))
        seen = set()
        unique = []
        for candidate in candidates:
            norm = os.path.normcase(os.path.normpath(os.path.abspath(str(candidate))))
            if norm not in seen:
                seen.add(norm)
                unique.append(os.path.abspath(str(candidate)))
        return unique

    def _manifest_for_sqlite_database_file(self, path):
        database_path = os.path.abspath(str(path))
        database_norm = os.path.normcase(os.path.normpath(database_path))
        for manifest_path in self._candidate_manifest_paths_for_sqlite_database(database_path):
            if not os.path.exists(manifest_path):
                continue
            try:
                payload = read_project_manifest(manifest_path)
                resolved_db = resolve_manifest_database_path(manifest_path, payload)
            except Exception:
                continue
            resolved_norm = os.path.normcase(os.path.normpath(os.path.abspath(resolved_db)))
            if resolved_norm == database_norm:
                return os.path.abspath(manifest_path)
        return ""

    def _is_project_sqlite_database_file(self, path):
        filename = os.path.basename(str(path or ""))
        return filename.endswith(".taxamask.sqlite") or filename.endswith(".taxamask_tif.sqlite")

    def _active_sqlite_project_manager(self):
        if getattr(self, "active_project_kind", "image") == "tif":
            manager = getattr(self, "tif_project", None)
        else:
            manager = getattr(self, "project", None)
        if manager is None:
            return None
        is_sqlite = getattr(manager, "is_sqlite_project", None)
        if not callable(is_sqlite) or not is_sqlite():
            return None
        return manager

    def _flush_active_sqlite_project_before_maintenance(self):
        manager = self._active_sqlite_project_manager()
        if manager is None:
            return None
        if manager is getattr(self, "project", None):
            self._flush_pending_project_save(force=True, defer_for_navigation=False)
        else:
            manager.save_project()
        return manager

    def _sqlite_maintenance_default_dir(self, manager):
        database_path = str(getattr(manager, "current_database_path", "") or "")
        if database_path:
            return os.path.dirname(os.path.abspath(database_path)) or "."
        project_path = str(getattr(manager, "current_project_path", "") or "")
        return os.path.dirname(os.path.abspath(project_path)) if project_path else self._default_outputs_root()

    def backup_current_sqlite_project(self):
        manager = self._flush_active_sqlite_project_before_maintenance()
        if manager is None:
            QMessageBox.information(
                self,
                tr("Backup SQLite Project", self.current_lang),
                tr("The current project is not a SQLite-backed project.", self.current_lang),
            )
            return
        try:
            result = backup_sqlite_project_manifest(
                manager.current_project_path,
                min_interval_seconds=0,
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                tr("Backup SQLite Project", self.current_lang),
                tr("SQLite project backup failed.\n\n{0}", self.current_lang).format(str(exc)),
            )
            return
        if not result.backup_manifest_path:
            QMessageBox.information(
                self,
                tr("Backup SQLite Project", self.current_lang),
                tr("SQLite project backup was skipped because a recent backup already exists.", self.current_lang),
            )
            return
        self.log(
            tr(
                "SQLite project backup created. Manifest: {0}; database: {1}",
                self.current_lang,
            ).format(result.backup_manifest_path, result.backup_database_path)
        )
        QMessageBox.information(
            self,
            tr("Backup SQLite Project", self.current_lang),
            tr(
                "SQLite backup created.\n\nOpen this manifest to inspect the backup:\n{0}",
                self.current_lang,
            ).format(result.backup_manifest_path),
        )

    def export_current_project_legacy_json(self):
        manager = self._flush_active_sqlite_project_before_maintenance()
        if manager is None:
            QMessageBox.information(
                self,
                tr("Export Legacy JSON", self.current_lang),
                tr("The current project is not a SQLite-backed project.", self.current_lang),
            )
            return
        default_dir = os.path.join(self._sqlite_maintenance_default_dir(manager), "legacy_json_exports")
        os.makedirs(default_dir, exist_ok=True)
        project_name = str(getattr(manager, "project_data", {}).get("name") or "project").strip() or "project"
        safe_name = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in project_name).strip("_") or "project"
        default_path = os.path.join(default_dir, f"{safe_name}.legacy_export_{time.strftime('%Y%m%d_%H%M%S')}.json")
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            tr("Export Legacy JSON", self.current_lang),
            default_path,
            tr("TaxaMask Projects (*.json);;All Files (*)", self.current_lang),
        )
        if not output_path:
            return
        try:
            result = export_sqlite_project_to_legacy_json(manager.current_project_path, output_path)
        except Exception as exc:
            QMessageBox.critical(
                self,
                tr("Export Legacy JSON", self.current_lang),
                tr("Legacy JSON export failed.\n\n{0}", self.current_lang).format(str(exc)),
            )
            return
        self.log(
            tr(
                "Exported SQLite project to legacy JSON for audit. Path: {0}; stats: {1}",
                self.current_lang,
            ).format(result.output_path, result.stats)
        )
        QMessageBox.information(
            self,
            tr("Export Legacy JSON", self.current_lang),
            tr("Legacy JSON export created:\n{0}", self.current_lang).format(result.output_path),
        )

    def open_current_sqlite_migration_report(self):
        manager = self._active_sqlite_project_manager()
        if manager is None:
            QMessageBox.information(
                self,
                tr("Open Migration Report", self.current_lang),
                tr("The current project is not a SQLite-backed project.", self.current_lang),
            )
            return
        report_path = sqlite_project_migration_report_path(manager.current_project_path)
        if not report_path:
            QMessageBox.information(
                self,
                tr("Open Migration Report", self.current_lang),
                tr("No migration report is recorded for this project.", self.current_lang),
            )
            return
        if not open_path(report_path):
            QMessageBox.information(
                self,
                tr("Open Migration Report", self.current_lang),
                tr("Migration report path:\n{0}", self.current_lang).format(report_path),
            )

    def appoint_selected_route_expert(self):
        panel = getattr(self, "route_settings_panel", None)
        if panel is not None:
            panel.appoint_selected_route_expert()

    def toggle_selected_route_enabled(self):
        panel = getattr(self, "route_settings_panel", None)
        if panel is not None:
            panel.toggle_selected_route_enabled()

    def delete_selected_route(self):
        panel = getattr(self, "route_settings_panel", None)
        if panel is not None:
            panel.delete_selected_route()

    def _log_route_usage_summary(self, payload, image_path=None, prefix=None):
        if not isinstance(payload, dict):
            return
        meta = payload.get("meta", {}) if isinstance(payload.get("meta"), dict) else {}
        attempted = list(meta.get("cascade_attempted_routes", []) or [])
        applied = list(meta.get("cascade_applied_routes", []) or [])
        block_reasons = dict(meta.get("cascade_block_reasons", {}) or {})
        route_source = str(meta.get("cascade_route_source", "none") or "none")
        image_name = os.path.basename(image_path) if image_path else tr("Current Image", self.current_lang)
        title = prefix or ui_text("Route usage for {0}", self.current_lang).format(image_name)
        attempted_text = attempted or [ui_text("None", self.current_lang)]
        applied_text = applied or [ui_text("None", self.current_lang)]
        self.log(
            f"{title}: "
            f"{ui_text('source={0}; attempted={1}; applied={2}', self.current_lang).format(route_source, attempted_text, applied_text)}"
        )
        profile_id = str(meta.get("model_profile_id") or "")
        parent_backend = str(meta.get("parent_backend") or "")
        route_backends = list(meta.get("cascade_route_backends", []) or [])
        if profile_id or parent_backend or route_backends:
            self.log(
                ui_text("Model audit: profile={0}; parent_backend={1}; route_backends={2}", self.current_lang).format(
                    profile_id or "unknown",
                    parent_backend or "unknown",
                    route_backends or [ui_text("None", self.current_lang)],
                )
            )
        if block_reasons:
            block_text = ", ".join(f"{part}={reason}" for part, reason in sorted(block_reasons.items()))
            self.log(ui_text("Route blocks: {0}", self.current_lang).format(block_text))

    def _locator_model_path(self, timestamp):
        if not self.engine or not timestamp:
            return None
        return os.path.join(self.engine.weights_dir, f"locator_{timestamp}.pth")

    def _segmenter_model_path(self, timestamp):
        if not self.engine or not timestamp:
            return None
        return os.path.join(self.engine.weights_dir, f"sam_decoder_lora_{timestamp}.pth")

    def _apply_locator_selection_to_runtime(self, *, log_change=False):
        if not self.engine:
            return

        ts = self._selected_locator_timestamp()
        if not ts:
            if self.engine.locator is None:
                self.engine.ensure_locator_loaded()
            else:
                self.engine.reset_locator_to_base()
            if log_change:
                self.log(tr("Locator reset to base (untrained).", self.current_lang))
            return

        self.engine.load_locator(ts)
        if log_change:
            locator_label = self._selected_locator_display_text() or ts
            self.log(tr("Locator switched to: {0}", self.current_lang).format(locator_label))

    def _locator_selection_needs_legacy_confirmation(self):
        return bool(getattr(self.engine, "loaded_locator_requires_legacy_confirmation", False))

    def _confirm_legacy_locator_selection_if_needed(self):
        if not self.engine or not self._locator_selection_needs_legacy_confirmation():
            return True

        reply = themed_yes_no_question(
            self,
            tr("Legacy Locator Confirmation", self.current_lang),
            tr(
                "The selected locator checkpoint does not store its training resolution. It will be treated as a legacy 512px locator only if you confirm.",
                self.current_lang,
            ),
            confirm_role=BUTTON_ROLE_COMMIT,
        )
        if reply == QMessageBox.Yes:
            self.engine.loaded_locator_requires_legacy_confirmation = False
            self.last_confirmed_locator_timestamp = self._selected_locator_timestamp()
            return True

        self.log("Legacy locator selection was cancelled.")
        return False

    def _show_structured_training_preflight(self, preflight):
        dialog = TrainingPreflightDialog(preflight, self, self.current_lang)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        return bool(dialog.accepted_training())

    def _is_locator_oom_error(self, exc):
        message = str(exc or "").lower()
        return "out of memory" in message or "cuda out of memory" in message

    def _ask_locator_oom_retry_resolution(self, current_resolution, lower_options):
        if not lower_options:
            QMessageBox.warning(
                self,
                tr("Training Retry", self.current_lang),
                tr("No lower locator resolutions are available for retry.", self.current_lang),
            )
            return None

        options_text = ", ".join(format_size_pair(value) for value in lower_options)
        message = tr(
            "Locator stage ran out of memory at {0}. You can retry with a lower locator size: {1}",
            self.current_lang,
        ).format(format_size_pair(current_resolution), options_text)

        selected_text, ok = QInputDialog.getItem(
            self,
            tr("Training Retry", self.current_lang),
            message,
            [format_size_pair(value) for value in lower_options],
            0,
            False,
        )
        if not ok or not selected_text:
            return None

        for candidate in lower_options:
            if format_size_pair(candidate) == str(selected_text).strip():
                return tuple(candidate)
        return None

    def _is_parent_training_running(self):
        external_thread = getattr(self, "external_training_thread", None)
        return bool((self.trainer and self.trainer.isRunning()) or (external_thread and external_thread.isRunning()))

    def _is_child_training_running(self):
        blink_lab = getattr(self, "blink_lab", None)
        thread = getattr(blink_lab, "training_thread", None) if blink_lab is not None else None
        return bool(thread and thread.isRunning())

    def _is_any_training_running(self):
        return self._is_parent_training_running() or self._is_child_training_running()

    def _set_training_progress(self, kind=None, status_text=None, percent=None):
        if kind:
            self.active_training_kind = kind
        if status_text is not None:
            self.active_training_label = str(status_text)
        if percent is not None:
            try:
                progress_value = max(0, min(100, int(percent)))
            except Exception:
                progress_value = None
        else:
            progress_value = None
        if hasattr(self, "label_training_progress_status"):
            text = self.active_training_label or tr("No training running.", self.current_lang)
            if progress_value is not None:
                text = f"{text} | {progress_value}%"
            self.label_training_progress_status.setText(text)
        if progress_value is not None and hasattr(self, "progress"):
            self.progress.setValue(progress_value)

    def _connect_child_training_progress(self):
        blink_lab = getattr(self, "blink_lab", None)
        thread = getattr(blink_lab, "training_thread", None) if blink_lab is not None else None
        if thread is None or getattr(thread, "_taxamask_shared_progress_connected", False):
            return
        thread._taxamask_shared_progress_connected = True
        thread.progress_signal.connect(lambda value: self._set_training_progress("child", None, value))
        thread.result_signal.connect(self._on_child_training_result)
        thread.error_signal.connect(self._on_child_training_error)
        thread.cancelled_signal.connect(self._on_child_training_cancelled)
        thread.finished.connect(self._on_child_training_finished)

    def _on_child_training_result(self, save_path):
        self.child_training_failed = not bool(save_path)
        if save_path:
            self._set_training_progress("child", tr("Child-part expert training finished.", self.current_lang), 100)
        else:
            self._set_training_progress("child", tr("Child-part expert training failed.", self.current_lang), self.progress.value())

    def _on_child_training_error(self, _error_msg):
        self.child_training_failed = True
        self._set_training_progress("child", tr("Child-part expert training failed.", self.current_lang), self.progress.value())

    def _on_child_training_cancelled(self):
        self.child_training_cancel_requested = True
        self._set_training_progress("child", tr("Training cancelled.", self.current_lang), self.progress.value())

    def _on_child_training_finished(self):
        if self.active_training_kind == "child" and not self.child_training_failed and not self.child_training_cancel_requested:
            self._set_training_progress("child", tr("Child-part expert training finished.", self.current_lang), 100)
        if hasattr(self, "btn_train"):
            self.btn_train.setEnabled(True)
        if hasattr(self, "btn_blink_stop_training"):
            self.btn_blink_stop_training.setEnabled(False)
        self.child_training_failed = False
        self.child_training_cancel_requested = False
        self._refresh_blink_refine_state()

    def _launch_training_with_preflight(self, preflight, tax, locator_scope, train_segmenter=True, training_scope=None):
        if self._is_child_training_running():
            self.log(tr("Child-part expert training is running. Wait for it to finish before training parent models.", self.current_lang))
            QMessageBox.information(
                self,
                tr("Training", self.current_lang),
                tr("Child-part expert training is running. Wait for it to finish before training parent models.", self.current_lang),
            )
            return
        active_preflight = dict(preflight or {})
        active_training_scope = dict(training_scope or {})
        scope_label = str(
            active_training_scope.get("label")
            or active_preflight.get("training_scope_label")
            or tr("All Images", self.current_lang)
        )
        scope_id = str(
            active_training_scope.get("scope_id")
            or active_preflight.get("training_scope_id")
            or "__all__"
        )
        try:
            scope_image_count = int(
                active_preflight.get(
                    "training_scope_image_count",
                    len(active_training_scope.get("images", []) or []),
                )
                or 0
            )
        except Exception:
            scope_image_count = 0
        active_preflight["training_scope_id"] = scope_id
        active_preflight["training_scope_label"] = scope_label
        active_preflight["training_scope_image_count"] = scope_image_count
        self.pending_training_preflight = {
            "preflight": active_preflight,
            "taxonomy": list(tax or []),
            "locator_scope": list(locator_scope or []),
            "train_segmenter": bool(train_segmenter),
            "training_scope": {
                "scope_id": scope_id,
                "label": scope_label,
                "image_count": scope_image_count,
            },
        }
        self.training_retry_requested = False
        self.parent_training_failed = False
        self.parent_training_cancel_requested = False

        self.engine.locator_resolution = tuple(active_preflight.get("selected_locator_size") or (512, 512))
        active_profile = _active_profile_from_manager(self.project)
        parent_backend = active_profile.get("parent_backend", {}) if isinstance(active_profile.get("parent_backend"), dict) else {}
        self.trainer = TrainingThread(
            self.engine,
            active_preflight,
            tax,
            locator_scope,
            self.train_epochs,
            self.train_batch,
            lang=self.current_lang,
            train_segmenter=train_segmenter,
            training_context={
                "active_profile_id": active_profile.get("profile_id", ""),
                "parent_backend": parent_backend.get("backend_type", PARENT_BACKEND_BUILTIN),
                "locator_scope": list(locator_scope or []),
                "train_segmenter": bool(train_segmenter),
                "locator_resolution": list(self.engine.locator_resolution),
                "training_scope": {
                    "scope_id": scope_id,
                    "label": scope_label,
                    "image_count": scope_image_count,
                },
            },
        )
        if hasattr(self.trainer, "translate"):
            self.trainer.translate = tr
        self.trainer.log_signal.connect(self.log)
        self.trainer.progress_signal.connect(lambda value: self._set_training_progress("parent", None, value))
        self.trainer.report_signal.connect(self.show_training_report)
        self.trainer.success_signal.connect(self._on_training_success)
        self.trainer.error_signal.connect(self._on_training_error)
        self.trainer.finished_signal.connect(self._on_training_finished)
        self.btn_train.setEnabled(False)
        self.btn_stop_training.setEnabled(True)
        self._set_training_progress("parent", tr("Parent-part model training", self.current_lang), 0)
        self._refresh_blink_refine_state()
        self.trainer.start()

    def _on_training_success(self):
        context = dict(getattr(self.trainer, "training_context", {}) or {})
        locator_weights = context.get("locator_weights") or None
        segmenter_weights = context.get("segmenter_weights") or None
        if (locator_weights or segmenter_weights) and hasattr(self.project, "update_active_model_profile_parent_weights"):
            self.project.update_active_model_profile_parent_weights(
                locator_weights=locator_weights,
                segmenter_weights=segmenter_weights,
                save=False,
            )
            self.project.save_project()
            self.log(
                tr("Active model profile updated with trained parent weights.", self.current_lang)
            )
        self.refresh_model_list()

    def _on_training_finished(self):
        self.btn_train.setEnabled(False if self.training_retry_requested else True)
        self.btn_stop_training.setEnabled(False)
        if not self.training_retry_requested and not self.parent_training_failed and not self.parent_training_cancel_requested:
            if self.active_training_kind == "parent":
                self._set_training_progress("parent", tr("Parent-part model training finished.", self.current_lang), 100)
            self.refresh_model_list()
        if not self.training_retry_requested:
            finished_trainer = self.trainer
            self.trainer = None
            if finished_trainer is not None and hasattr(finished_trainer, "deleteLater"):
                finished_trainer.deleteLater()
        self._refresh_blink_refine_state()

    def _on_training_error(self, payload):
        payload = dict(payload or {})
        error_type = payload.get("type")
        self.training_retry_requested = False
        self.parent_training_failed = True

        if error_type == "oom" and payload.get("stage") == "locator":
            retry_resolution = self._ask_locator_oom_retry_resolution(
                payload.get("current_resolution") or 512,
                payload.get("lower_options", []),
            )
            if retry_resolution is not None and self.pending_training_preflight:
                self.training_retry_requested = True
                updated_preflight = dict(self.pending_training_preflight.get("preflight") or {})
                updated_preflight["selected_locator_size"] = tuple(retry_resolution)
                updated_preflight["lower_locator_size_options"] = [
                    tuple(value)
                    for value in updated_preflight.get("lower_locator_size_options", [])
                    if tuple(value) != tuple(retry_resolution)
                ]
                self.pending_training_preflight["preflight"] = updated_preflight
                self.parent_training_failed = False
                QTimer.singleShot(
                    0,
                    lambda: self._launch_training_with_preflight(
                        updated_preflight,
                        self.pending_training_preflight.get("taxonomy", []),
                        self.pending_training_preflight.get("locator_scope", []),
                        self.pending_training_preflight.get("train_segmenter", True),
                        self.pending_training_preflight.get("training_scope", {}),
                    ),
                )
                return

        message = str(payload.get("message") or "Training failed.")
        self._set_training_progress("parent", tr("Parent-part model training failed.", self.current_lang), self.progress.value())
        self.log(tr("Training aborted: {0}", self.current_lang).format(message))
        QMessageBox.critical(self, tr("Error", self.current_lang), message)

    def stop_training(self):
        if self.trainer and self.trainer.isRunning():
            self.trainer.requestInterruption()
            self.btn_stop_training.setEnabled(False)
            self.parent_training_cancel_requested = True
            self._set_training_progress("parent", tr("Stopping parent-part training...", self.current_lang), self.progress.value())
            self.log(tr("Stopping training after the current epoch/batch...", self.current_lang))

    def _apply_segmenter_selection_to_runtime(self, *, log_change=False):
        if not self.engine:
            return

        ts = self._selected_segmenter_timestamp()
        if not ts:
            if self.engine.parts_model is not None:
                self.engine.reset_sam_to_base()
            if self.sam_worker:
                self.sam_worker.reload_base_model()
            if log_change:
                self.log(tr("Segmenter switched to: Base SAM (Original)", self.current_lang))
            return

        self.engine.load_sam_decoder(ts)
        if self.sam_worker:
            weights_path = self._segmenter_model_path(ts)
            if weights_path:
                self.sam_worker.load_decoder_weights(weights_path)
        if log_change:
            self.log(tr("Segmenter switched to: Fine-tuned {0}", self.current_lang).format(ts))

    def update_model_delete_button_states(self, *_):
        locator_ts = self._selected_locator_timestamp()
        locator_path = self._locator_model_path(locator_ts)
        can_edit_locator = bool(locator_path and os.path.exists(locator_path))
        self.btn_del_locator.setEnabled(can_edit_locator)
        self.btn_note_locator.setEnabled(can_edit_locator)

        segmenter_ts = self._selected_segmenter_timestamp()
        segmenter_path = self._segmenter_model_path(segmenter_ts)
        can_edit_segmenter = bool(segmenter_path and os.path.exists(segmenter_path))
        self.btn_del_segmenter.setEnabled(can_edit_segmenter)
        self.btn_note_segmenter.setEnabled(can_edit_segmenter)

    def _edit_parent_model_note(self, model_kind):
        if model_kind == "locator":
            ts = self._selected_locator_timestamp()
            path = self._locator_model_path(ts)
            title = tr("Edit Locator Note", self.current_lang)
        elif model_kind == "segmenter":
            ts = self._selected_segmenter_timestamp()
            path = self._segmenter_model_path(ts)
            title = tr("Edit Segmenter Note", self.current_lang)
        else:
            return
        filename = self._parent_model_filename(model_kind, ts)
        if not ts or not filename or not path or not os.path.exists(path):
            self.update_model_delete_button_states()
            return

        notes = load_parent_model_notes(self.engine.weights_dir)
        current_note = notes.get(filename, "")
        note, ok = QInputDialog.getText(
            self,
            title,
            tr("Model display note:", self.current_lang),
            QLineEdit.Normal,
            current_note,
        )
        if not ok:
            return
        clean_note = set_parent_model_note(self.engine.weights_dir, filename, note)
        self.refresh_model_list()
        if clean_note:
            self.log(tr("Updated model note for {0}: {1}", self.current_lang).format(filename, clean_note))
        else:
            self.log(tr("Cleared model note for {0}.", self.current_lang).format(filename))

    def edit_locator_model_note(self):
        self._edit_parent_model_note("locator")

    def edit_segmenter_model_note(self):
        self._edit_parent_model_note("segmenter")

    def on_locator_changed(self, index):
        if getattr(self, "active_project_kind", "start") != "image" or getattr(self.engine, "locator", None) is None:
            self.update_model_delete_button_states()
            return
        self._apply_locator_selection_to_runtime(log_change=False)
        if self._locator_selection_needs_legacy_confirmation():
            if not self._confirm_legacy_locator_selection_if_needed():
                fallback_ts = self.last_confirmed_locator_timestamp
                fallback_index = self.combo_locator.findData(fallback_ts) if fallback_ts else -1
                if fallback_index < 0:
                    fallback_index = 0 if self.combo_locator.count() else -1
                if fallback_index >= 0:
                    self.combo_locator.blockSignals(True)
                    self.combo_locator.setCurrentIndex(fallback_index)
                    self.combo_locator.blockSignals(False)
                    self._apply_locator_selection_to_runtime(log_change=False)
                    fallback_label = self._selected_locator_display_text()
                    if fallback_label:
                        self.log(tr("Locator switched to: {0}", self.current_lang).format(fallback_label))
                    else:
                        self.log(tr("Locator reset to base (untrained).", self.current_lang))
            else:
                self.last_confirmed_locator_timestamp = self._selected_locator_timestamp()
                self.log(
                    tr("Locator switched to: {0}", self.current_lang).format(
                        self._selected_locator_display_text() or self.last_confirmed_locator_timestamp
                    )
                )
        else:
            self.last_confirmed_locator_timestamp = self._selected_locator_timestamp()
            current_label = self._selected_locator_display_text()
            if current_label:
                self.log(tr("Locator switched to: {0}", self.current_lang).format(current_label))
            else:
                self.log(tr("Locator reset to base (untrained).", self.current_lang))
        self.update_model_delete_button_states()

    def delete_locator_model(self):
        ts = self._selected_locator_timestamp()
        if not ts:
            self.update_model_delete_button_states()
            return
        
        reply = themed_yes_no_question(
            self,
            tr("Delete Model", self.current_lang),
            tr("Delete locator model {0}?", self.current_lang).format(ts),
            confirm_role=BUTTON_ROLE_DESTRUCTIVE,
        )
        if reply == QMessageBox.Yes:
            try:
                p = self._locator_model_path(ts)
                if os.path.exists(p):
                    os.remove(p)
                    set_parent_model_note(self.engine.weights_dir, self._parent_model_filename("locator", ts), "")
                    self.log(f"Deleted locator: {ts}")
                    self.refresh_model_list()
                else:
                    self.log(f"File not found: {p}")
                    self.update_model_delete_button_states()
            except Exception as e:
                self.log(f"Error deleting model: {e}")
                self.update_model_delete_button_states()

    def on_segmenter_changed(self, index):
        self._apply_segmenter_selection_to_runtime(log_change=True)
        self.update_model_delete_button_states()

    def delete_segmenter_model(self):
        ts = self._selected_segmenter_timestamp()
        if not ts:
            self.update_model_delete_button_states()
            return
        
        reply = themed_yes_no_question(
            self,
            tr("Delete Model", self.current_lang),
            tr("Delete segmenter LoRA {0}?", self.current_lang).format(ts),
            confirm_role=BUTTON_ROLE_DESTRUCTIVE,
        )
        if reply == QMessageBox.Yes:
            try:
                p = self._segmenter_model_path(ts)
                if os.path.exists(p):
                    os.remove(p)
                    set_parent_model_note(self.engine.weights_dir, self._parent_model_filename("segmenter", ts), "")
                    self.log(f"Deleted segmenter: {ts}")
                    self.refresh_model_list()
                else:
                    self.log(f"File not found: {p}")
                    self.update_model_delete_button_states()
            except Exception as e:
                self.log(f"Error deleting model: {e}")
                self.update_model_delete_button_states()

    def on_model_changed(self, index):
        # Deprecated
        pass

    def create_menus(self):
        menubar = self.menuBar()
        menubar.clear()
        file_menu = menubar.addMenu(tr("File", self.current_lang))
        file_menu.addAction(tr("Start Center", self.current_lang), self._show_start_center)
        file_menu.addAction(tr("New Project", self.current_lang), self.new_project)
        if self._is_tif_workflow_enabled():
            file_menu.addAction(tr("New TIF Volume Project", self.current_lang), self.new_tif_project)
        file_menu.addAction(tr("Open Project", self.current_lang), self.open_project)
        file_menu.addAction(tr("Save Project", self.current_lang), lambda: self._flush_pending_project_save(force=True))
        file_menu.addAction(tr("Backup SQLite Project", self.current_lang), self.backup_current_sqlite_project)
        file_menu.addAction(tr("Export Legacy JSON", self.current_lang), self.export_current_project_legacy_json)
        file_menu.addAction(tr("Open Migration Report", self.current_lang), self.open_current_sqlite_migration_report)
        file_menu.addAction(tr("Import STL Rendered Views to Labeling Workbench", self.current_lang), self.import_stl_rendered_views_action)
        file_menu.addAction(tr("Open PDF Evidence Tools", self.current_lang), self.open_pdf_evidence_tools)
        file_menu.addAction(tr("Check / Relocate Project Images", self.current_lang), self.check_relocate_project_images)
        file_menu.addAction(tr("Export Dataset", self.current_lang), self.export_dataset)
        workflow_menu = menubar.addMenu(tr("Workflow", self.current_lang))
        workflow_menu.addAction(tr("2D/STL Morphology Workflow", self.current_lang), self.enter_image_workflow)
        workflow_menu.addAction(tr("Create 2D/STL project", self.current_lang), self.new_project)
        if self._is_tif_workflow_enabled():
            workflow_menu.addAction(tr("TIF Volume Workflow", self.current_lang), self.enter_tif_workflow)
            workflow_menu.addAction(tr("Create TIF project", self.current_lang), self.new_tif_project)
        workflow_menu.addAction(tr("Import STL Rendered Views to Labeling Workbench", self.current_lang), self.import_stl_rendered_views_action)
        settings_menu = menubar.addMenu(tr("Settings", self.current_lang))
        settings_menu.addAction(tr("General Settings", self.current_lang), self.open_general_settings)
        settings_menu.addAction(tr("2D/STL Model Settings", self.current_lang), self.open_stl_model_settings)
        if self._is_tif_workflow_enabled():
            settings_menu.addAction(tr("TIF Volume Model Settings", self.current_lang), self.open_tif_model_settings)

    def new_project(self):
        d = QFileDialog.getExistingDirectory(
            self,
            tr("New Project Directory", self.current_lang),
            self._default_project_dialog_dir("image"),
        )
        if d:
            name, ok = QInputDialog.getText(self, tr("New Project", self.current_lang), tr("Project Name:", self.current_lang))
            if ok and name:
                template = self._choose_project_template()
                if template is None:
                    return
                self._flush_pending_project_save(defer_for_navigation=False)
                self.project.create_project(name, d, template_id=template["template_id"])
                self.active_project_kind = "image"
                self.active_project_source_kind = "image"
                self.active_project_entry_path = self.project.current_project_path or ""
                self.config.set("last_project_path", self.active_project_entry_path)
                self._refresh_project_bound_views()
                self.ensure_2d_stl_models_preloaded()
                self.canvas.load_image("") 

    def new_tif_project(self):
        if not self._is_tif_workflow_enabled():
            self._show_tif_workflow_unavailable()
            return
        d = QFileDialog.getExistingDirectory(
            self,
            tr("New TIF Project Directory", self.current_lang),
            self._default_project_dialog_dir("tif"),
        )
        if not d:
            return
        name, ok = QInputDialog.getText(self, tr("New TIF Volume Project", self.current_lang), tr("Project Name:", self.current_lang))
        if not ok or not name:
            return
        self._flush_pending_project_save(defer_for_navigation=False)
        self.tif_project.create_project(name, d)
        self.active_project_kind = "tif"
        self.active_project_source_kind = "tif"
        self.active_project_entry_path = self.tif_project.current_project_path or ""
        self.config.set("last_project_path", self.tif_project.current_project_path)
        self._refresh_project_bound_views()
        self.log(tr("Created TIF volume project: {0}", self.current_lang).format(self.tif_project.current_project_path))

    def _ensure_tif_project_open(self):
        if getattr(self, "active_project_kind", "image") != "tif" or not self.tif_project.current_project_path:
            QMessageBox.warning(
                self,
                tr("TIF Volume Workbench", self.current_lang),
                tr("Please create or open a TIF volume project first.", self.current_lang),
            )
            return False
        return True

    def import_tif_stack_action(self):
        if not self._ensure_tif_project_open():
            return
        tif_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("Import TIF Stack", self.current_lang),
            "",
            "TIF/TIFF (*.tif *.tiff)",
        )
        if not tif_path:
            return
        default_id = os.path.splitext(os.path.basename(tif_path))[0]
        specimen_id, ok = QInputDialog.getText(
            self,
            tr("Import TIF Stack", self.current_lang),
            tr("Specimen ID:", self.current_lang),
            text=default_id,
        )
        if not ok or not specimen_id:
            return
        try:
            result = import_tif_stack(self.tif_project, tif_path, specimen_id)
        except Exception as exc:
            QMessageBox.critical(self, tr("Import TIF Stack", self.current_lang), str(exc))
            return
        self.tif_workbench.refresh_project()
        self.tabs.setCurrentWidget(self.tif_workbench)
        report_path = result.get("report_path", "")
        self.log(tr("Imported TIF stack for specimen {0}. Report: {1}", self.current_lang).format(specimen_id, report_path))

    def import_amira_directory_action(self):
        if not self._ensure_tif_project_open():
            return
        source_dir = QFileDialog.getExistingDirectory(
            self,
            tr("Import AMIRA Directory", self.current_lang),
            self.tif_project.project_dir,
        )
        if not source_dir:
            return
        default_id = os.path.basename(os.path.normpath(source_dir))
        specimen_id, ok = QInputDialog.getText(
            self,
            tr("Import AMIRA Directory", self.current_lang),
            tr("Specimen ID:", self.current_lang),
            text=default_id,
        )
        if not ok or not specimen_id:
            return
        try:
            result = import_amira_directory(self.tif_project, source_dir, specimen_id)
        except Exception as exc:
            QMessageBox.critical(self, tr("Import AMIRA Directory", self.current_lang), str(exc))
            return
        self.tif_workbench.refresh_project()
        self.tabs.setCurrentWidget(self.tif_workbench)
        report_path = result.get("report_path", "")
        self.log(tr("Imported AMIRA directory for specimen {0}. Report: {1}", self.current_lang).format(specimen_id, report_path))

    def import_stl_rendered_views_action(self):
        source_dir = QFileDialog.getExistingDirectory(
            self,
            tr("Import STL Rendered Views to Labeling Workbench", self.current_lang),
            self._current_2d_project_dir(),
        )
        if not source_dir:
            return
        try:
            result = import_stl_rendered_views_into_2d_project(self.project, source_dir)
        except Exception as exc:
            QMessageBox.critical(self, tr("Import STL Rendered Views to Labeling Workbench", self.current_lang), str(exc))
            return
        self.active_project_kind = "image"
        self.active_project_source_kind = "image"
        self.active_project_entry_path = self.project.current_project_path or ""
        self.config.set("last_project_path", self.active_project_entry_path)
        self._refresh_project_bound_views()
        self.tabs.setCurrentWidget(self.workbench_widget)
        self.ensure_2d_stl_models_preloaded()
        self.log(
            tr("Imported STL rendered views into the Labeling Workbench from {0}. Registered views: {1}, specimens: {2}, unparsed files: {3}.", self.current_lang).format(
                source_dir,
                result.get("registered_count", 0),
                result.get("specimen_count", 0),
                result.get("unparsed_count", 0),
            )
        )

    def open_pdf_evidence_tools(self):
        index = self.tabs.indexOf(self.pdf_widget)
        if index < 0:
            index = self.tabs.addTab(self.pdf_widget, tr("PDF Evidence Tools", self.current_lang))
        self.tabs.setCurrentIndex(index)

    def open_pdf_multimodal_api_settings(self):
        self.open_pdf_evidence_tools()
        pdf_widget = getattr(self, "pdf_widget", None)
        if pdf_widget is None:
            return
        if hasattr(pdf_widget, "tabs"):
            try:
                pdf_widget.tabs.setCurrentIndex(0)
            except Exception:
                pass
        if hasattr(pdf_widget, "api_panel"):
            try:
                pdf_widget.api_panel.setVisible(True)
            except Exception:
                pass
        target = getattr(pdf_widget, "mllm_group", None) or getattr(pdf_widget, "api_panel", None)
        scroll = getattr(pdf_widget, "main_scroll", None)
        if target is not None and scroll is not None:
            try:
                scroll.ensureWidgetVisible(target)
            except Exception:
                pass
        use_same = True
        same_widget = getattr(pdf_widget, "check_mllm_same_as_text", None)
        if same_widget is not None and hasattr(same_widget, "isChecked"):
            try:
                use_same = bool(same_widget.isChecked())
            except Exception:
                use_same = True
        editor = (
            getattr(pdf_widget, "edit_api_key", None)
            if use_same
            else getattr(pdf_widget, "edit_mllm_api_key", None)
        )
        if editor is None:
            editor = getattr(pdf_widget, "edit_mllm_model", None) or getattr(pdf_widget, "edit_model", None)
        if editor is not None and hasattr(editor, "setFocus"):
            try:
                editor.setFocus()
            except Exception:
                pass

    def _choose_project_template(self):
        templates = iter_project_templates()
        if not templates:
            return {"template_id": DEFAULT_PROJECT_TEMPLATE_ID}
        labels = [tr(template["display_name"], self.current_lang) for template in templates]
        selected, ok = QInputDialog.getItem(
            self,
            tr("New Project", self.current_lang),
            tr("Project Template:", self.current_lang),
            labels,
            0,
            False,
        )
        if not ok:
            return None
        try:
            return templates[labels.index(selected)]
        except ValueError:
            return templates[0]

    def open_project(self):
        f, _ = QFileDialog.getOpenFileName(
            self,
            tr("Open Project", self.current_lang),
            self._default_open_project_dir(),
            tr(
                "TaxaMask Project Entry (*.sqlite_manifest.json *.tif_sqlite_manifest.json *.json);;SQLite Database (*.taxamask.sqlite *.taxamask_tif.sqlite);;All Files (*)",
                self.current_lang,
            ),
        )
        if f:
            self.open_project_path(f)

    def _confirm_legacy_2d_json_migration(self, path):
        message = tr(
            "This is an older 2D JSON project. TaxaMask now stores 2D projects in SQLite so large annotation projects are saved incrementally instead of rewriting one large JSON file.\n\nThe old JSON will not be overwritten. A SQLite database, a manifest file, a migration report, and a legacy JSON backup will be created next to the project.\n\nMigrate and open the SQLite project now?",
            self.current_lang,
        )
        reply = themed_yes_no_question(
            self,
            tr("Migrate 2D Project to SQLite", self.current_lang),
            f"{message}\n\n{path}",
            confirm_role=BUTTON_ROLE_COMMIT,
        )
        return reply == QMessageBox.Yes

    def _existing_sqlite_manifest_for_legacy_json(self, path):
        manifest_path = default_sqlite_manifest_path(path)
        if not os.path.exists(manifest_path):
            return ""
        try:
            read_project_manifest(manifest_path)
        except Exception:
            return ""
        return os.path.abspath(manifest_path)

    def _confirm_open_existing_sqlite_migration(self, manifest_path):
        reply = themed_yes_no_question(
            self,
            tr("Migrate 2D Project to SQLite", self.current_lang),
            tr(
                "A migrated SQLite version already exists for this old JSON project.\n\nOpen the existing SQLite manifest instead?\n\n{0}",
                self.current_lang,
            ).format(manifest_path),
            confirm_role=BUTTON_ROLE_COMMIT,
        )
        return reply == QMessageBox.Yes

    def _confirm_legacy_tif_json_migration(self, path):
        message = tr(
            "This is an older TIF JSON project. TaxaMask can now store the TIF project index in SQLite while keeping the large volume and label sidecar files on disk.\n\nThe old JSON will not be overwritten. The TIF volume sidecar files will not be moved. A SQLite database, a manifest file, a migration report, and a legacy JSON backup will be created next to the project.\n\nMigrate and open the SQLite project now?",
            self.current_lang,
        )
        reply = themed_yes_no_question(
            self,
            tr("Migrate TIF Project to SQLite", self.current_lang),
            f"{message}\n\n{path}",
            confirm_role=BUTTON_ROLE_COMMIT,
        )
        return reply == QMessageBox.Yes

    def _existing_tif_sqlite_manifest_for_legacy_json(self, path):
        manifest_path = default_tif_sqlite_manifest_path(path)
        if not os.path.exists(manifest_path):
            return ""
        try:
            payload = read_project_manifest(manifest_path)
        except Exception:
            return ""
        if payload.get("project_type") != TIF_PROJECT_TYPE:
            return ""
        return os.path.abspath(manifest_path)

    def _confirm_open_existing_tif_sqlite_migration(self, manifest_path):
        reply = themed_yes_no_question(
            self,
            tr("Migrate TIF Project to SQLite", self.current_lang),
            tr(
                "A migrated SQLite version already exists for this old TIF JSON project.\n\nOpen the existing SQLite manifest instead?\n\n{0}",
                self.current_lang,
            ).format(manifest_path),
            confirm_role=BUTTON_ROLE_COMMIT,
        )
        return reply == QMessageBox.Yes

    def _migrate_legacy_2d_project_with_progress(self, path):
        progress = QProgressDialog(
            tr("Migrating 2D project to SQLite...", self.current_lang),
            "",
            0,
            100,
            self,
        )
        progress.setWindowTitle(tr("Migrate 2D Project to SQLite", self.current_lang))
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setCancelButton(None)
        self._prepare_progress_dialog(progress, width=560)
        progress.show()
        app = QApplication.instance()
        if app is not None:
            app.processEvents()

        def on_progress(done, total, message):
            total = max(0, int(total or 0))
            done = max(0, int(done or 0))
            if total > 0:
                if progress.maximum() != total:
                    progress.setRange(0, total)
                progress.setValue(min(done, total))
            else:
                progress.setRange(0, 0)
            progress.setLabelText(str(message or ""))
            if app is not None:
                app.processEvents()

        try:
            result = migrate_legacy_2d_json_to_sqlite(path, progress_callback=on_progress)
        finally:
            progress.close()
            progress.deleteLater()
            if app is not None:
                app.processEvents()
        return result

    def _migrate_legacy_tif_project_with_progress(self, path):
        progress = QProgressDialog(
            tr("Migrating TIF project to SQLite...", self.current_lang),
            "",
            0,
            100,
            self,
        )
        progress.setWindowTitle(tr("Migrate TIF Project to SQLite", self.current_lang))
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setCancelButton(None)
        self._prepare_progress_dialog(progress, width=560)
        progress.show()
        app = QApplication.instance()
        if app is not None:
            app.processEvents()

        def on_progress(done, total, message):
            total = max(0, int(total or 0))
            done = max(0, int(done or 0))
            if total > 0:
                if progress.maximum() != total:
                    progress.setRange(0, total)
                progress.setValue(min(done, total))
            else:
                progress.setRange(0, 0)
            progress.setLabelText(str(message or ""))
            if app is not None:
                app.processEvents()

        try:
            result = migrate_legacy_tif_json_to_sqlite(path, progress_callback=on_progress)
        finally:
            progress.close()
            progress.deleteLater()
            if app is not None:
                app.processEvents()
        return result

    def open_project_path(self, path):
        f = os.path.abspath(str(path))
        runtime_log_event("open_project_begin", path=f)
        self._flush_pending_project_save(defer_for_navigation=False)
        if self._is_project_sqlite_database_file(f):
            manifest_path = self._manifest_for_sqlite_database_file(f)
            if not manifest_path:
                QMessageBox.warning(
                    self,
                    tr("Project entry file not found", self.current_lang),
                    tr(
                        "This is a SQLite database file, but TaxaMask could not find the matching project entry file. Please open the project entry file next to it instead:\n\n2D: *.sqlite_manifest.json\nTIF: *.tif_sqlite_manifest.json\n\nSelected database:\n{0}",
                        self.current_lang,
                    ).format(f),
                )
                runtime_log_event("open_project_sqlite_database_without_manifest", path=f)
                return
            self.log(
                tr(
                    "Selected a SQLite database file. Opening its project entry instead: {0}",
                    self.current_lang,
                ).format(manifest_path)
            )
            runtime_log_event("open_project_sqlite_database_redirected", path=f, manifest=manifest_path)
            f = manifest_path
        payload = self._read_project_probe_payload(f)
        if self._is_legacy_2d_json_project_payload(payload):
            existing_manifest = self._existing_sqlite_manifest_for_legacy_json(f)
            if existing_manifest:
                if not self._confirm_open_existing_sqlite_migration(existing_manifest):
                    runtime_log_event("open_project_existing_sqlite_manifest_cancelled", path=f, manifest=existing_manifest)
                    return
                f = existing_manifest
                payload = self._read_project_probe_payload(f)
            else:
                if not self._confirm_legacy_2d_json_migration(f):
                    runtime_log_event("open_project_legacy_json_migration_cancelled", path=f)
                    return
                try:
                    migration_result = self._migrate_legacy_2d_project_with_progress(f)
                except Exception as exc:
                    runtime_log_exception("open_project_legacy_json_migration_failed", *sys.exc_info())
                    QMessageBox.critical(
                        self,
                        tr("Migrate 2D Project to SQLite", self.current_lang),
                        tr("2D project migration failed. The old JSON was not modified.\n\n{0}", self.current_lang).format(str(exc)),
                    )
                    return
                f = os.path.abspath(str(migration_result.manifest_path))
                runtime_log_event(
                    "open_project_legacy_json_migrated",
                    source=migration_result.source_json_path,
                    manifest=f,
                    database=migration_result.database_path,
                    image_count=migration_result.stats.get("image_count", 0),
                    label_count=migration_result.stats.get("label_count", 0),
                )
                self.log(
                    tr(
                        "Migrated legacy 2D JSON project to SQLite. Manifest: {0}; database: {1}; report: {2}",
                        self.current_lang,
                    ).format(f, migration_result.database_path, migration_result.report_path)
                )
        if self._is_tif_project_file(f):
            if not self._is_tif_workflow_enabled():
                self._show_tif_workflow_unavailable()
                return
            if (
                isinstance(payload, dict)
                and payload.get("schema_version") == TIF_PROJECT_SCHEMA_VERSION
                and payload.get("project_type") == TIF_PROJECT_TYPE
            ):
                existing_manifest = self._existing_tif_sqlite_manifest_for_legacy_json(f)
                if existing_manifest:
                    if not self._confirm_open_existing_tif_sqlite_migration(existing_manifest):
                        runtime_log_event("open_tif_existing_sqlite_manifest_cancelled", path=f, manifest=existing_manifest)
                        return
                    f = existing_manifest
                else:
                    if not self._confirm_legacy_tif_json_migration(f):
                        runtime_log_event("open_tif_legacy_json_migration_cancelled", path=f)
                        return
                    try:
                        migration_result = self._migrate_legacy_tif_project_with_progress(f)
                    except Exception as exc:
                        runtime_log_exception("open_tif_legacy_json_migration_failed", *sys.exc_info())
                        QMessageBox.critical(
                            self,
                            tr("Migrate TIF Project to SQLite", self.current_lang),
                            tr("TIF project migration failed. The old JSON was not modified.\n\n{0}", self.current_lang).format(str(exc)),
                        )
                        return
                    f = os.path.abspath(str(migration_result.manifest_path))
                    runtime_log_event(
                        "open_tif_legacy_json_migrated",
                        source=migration_result.source_json_path,
                        manifest=f,
                        database=migration_result.database_path,
                        specimen_count=migration_result.stats.get("specimen_count", 0),
                        part_count=migration_result.stats.get("part_count", 0),
                    )
                    self.log(
                        tr(
                            "Migrated legacy TIF JSON project to SQLite. Manifest: {0}; database: {1}; report: {2}",
                            self.current_lang,
                        ).format(f, migration_result.database_path, migration_result.report_path)
                    )
            self.tif_project.load_project(f)
            self.active_project_kind = "tif"
            self.active_project_source_kind = "tif"
            self.active_project_entry_path = f
            self.config.set("last_project_path", f)
            self.log(tr("Opened TIF volume project: {0}", self.current_lang).format(f))
        elif self._is_stl_project_file(f):
            self.stl_project.load_project(f)
            result = register_stl_rendered_views_for_2d_review(self.stl_project, self.project)
            self.active_project_kind = "image"
            self.active_project_source_kind = "stl"
            self.active_project_entry_path = f
            self.config.set("last_project_path", f)
            self._prepare_image_list_for_project_open()
            self.log(tr("Opened STL rendered-view project and registered it into the Labeling Workbench: {0}", self.current_lang).format(f))
            self.log(
                tr("Registered STL rendered-view project into the Labeling Workbench. Views: {0}, missing files: {1}.", self.current_lang).format(
                    result.get("registered_count", 0),
                    result.get("missing_count", 0),
                )
            )
        else:
            self.project.load_project(f)
            self.active_project_kind = "image"
            self.active_project_source_kind = "image"
            self.active_project_entry_path = f
            self.config.set("last_project_path", f)
            self._prepare_image_list_for_project_open()
        self._refresh_project_bound_views()
        if hasattr(self.engine, "cascade_manager"):
            self.engine.cascade_manager.project_manager = self.project
        self._sync_blink_lab_model_profile_defaults()
        if getattr(self, "active_project_kind", "image") == "image":
            self._preload_2d_stl_models_after_open()
        runtime_log_event(
            "open_project_ok",
            path=f,
            active_kind=getattr(self, "active_project_kind", ""),
            source_kind=getattr(self, "active_project_source_kind", ""),
            image_count=len(self.project.project_data.get("images", []) or []),
            label_count=len(self.project.project_data.get("labels", {}) or {}),
        )
        self.canvas.load_image("")

    def _format_relocation_preview(self, matches, limit=8):
        lines = []
        for item in list(matches or [])[:limit]:
            old_name = os.path.basename(str(item.get("old_path", "")))
            new_path = str(item.get("new_path", ""))
            lines.append(f"{old_name} -> {new_path}")
        remaining = max(0, len(matches or []) - limit)
        if remaining:
            lines.append(f"... +{remaining}")
        return "\n".join(lines) if lines else "-"

    def check_relocate_project_images(self):
        health = self.project.get_image_path_health()
        message = tr("Project has {0}/{1} image paths available. Missing: {2}.", self.current_lang).format(
            health["existing_count"],
            health["total"],
            health["missing_count"],
        )
        if health["missing_count"] <= 0:
            QMessageBox.information(
                self,
                tr("Project Image Health", self.current_lang),
                tr("All project image paths are available.", self.current_lang),
            )
            self.log(message)
            return

        self.log(message)
        new_root = QFileDialog.getExistingDirectory(self, tr("Select New Image Root", self.current_lang))
        if not new_root:
            return

        preview = self.project.preview_image_path_remap(new_root)
        matches = preview.get("matches", [])
        if not matches:
            QMessageBox.information(
                self,
                tr("Relocation Preview", self.current_lang),
                tr("No missing image paths could be matched under the selected folder.", self.current_lang),
            )
            return

        preview_text = self._format_relocation_preview(matches)
        reply = themed_yes_no_question(
            self,
            tr("Relocation Preview", self.current_lang),
            tr("Matched {0} missing image path(s). Still unresolved: {1}.\n\nPreview:\n{2}\n\nApply this remap and save the project?", self.current_lang).format(
                len(matches),
                len(preview.get("unresolved", [])),
                preview_text,
            ),
            confirm_role=BUTTON_ROLE_COMMIT,
        )
        if reply != QMessageBox.Yes:
            return

        self._flush_pending_project_save(defer_for_navigation=False)
        changed = self.project.apply_image_path_remap(matches, save=True)
        self.refresh_file_list()
        if self.current_image and not os.path.exists(self.current_image):
            self.current_image = None
            self.canvas.load_image("")
        result = tr("Remapped {0} project image path(s).", self.current_lang).format(changed)
        self.log(result)
        QMessageBox.information(self, tr("Project Image Health", self.current_lang), result)

    def _part_item_name(self, item):
        if item is None:
            return None
        part_name = item.data(0, Qt.UserRole)
        clean_name = str(part_name or "").strip()
        return clean_name or None

    def _current_part_name(self):
        return self._part_item_name(self.part_list.currentItem())

    def _workbench_parent_parts(self):
        project = getattr(self, "project", None)
        taxonomy = list(getattr(project, "project_data", {}).get("taxonomy", [])) if project is not None else []
        taxonomy_set = {str(part).strip() for part in taxonomy if str(part).strip()}
        get_scope = getattr(project, "get_locator_scope", None)
        try:
            scope = get_scope() if callable(get_scope) else []
        except Exception:
            scope = []
        parents = []
        for part in scope or []:
            clean = str(part or "").strip()
            if clean and clean in taxonomy_set and clean not in parents:
                parents.append(clean)
        return parents

    def _is_parent_part(self, part_name):
        clean_part = str(part_name or "").strip()
        return bool(clean_part) and clean_part in set(self._workbench_parent_parts())

    def _part_tree_parent_for(self, part_name):
        clean_part = str(part_name or "").strip()
        if not clean_part or not hasattr(self, "part_list"):
            return None

        def walk(item):
            if item is None:
                return None
            if self._part_item_name(item) == clean_part:
                parent_item = item.parent()
                parent_part = self._part_item_name(parent_item)
                return parent_part if parent_part and parent_part != clean_part else None
            for index in range(item.childCount()):
                found = walk(item.child(index))
                if found:
                    return found
            return None

        for index in range(self.part_list.topLevelItemCount()):
            found_parent = walk(self.part_list.topLevelItem(index))
            if found_parent:
                return found_parent
        return None

    def _route_parents_for_child(self, child_part):
        clean_child = str(child_part or "").strip()
        if not clean_child:
            return []
        routes = []
        try:
            routes = self.project.iter_cascade_routes()
        except Exception:
            routes = []
        parents = []
        for route in routes or []:
            if not isinstance(route, dict):
                continue
            parent = str(route.get("parent") or "").strip()
            child = str(route.get("child") or "").strip()
            if parent and child == clean_child and parent != clean_child and parent not in parents:
                parents.append(parent)
        return parents

    def _resolve_child_parent(self, child_part):
        clean_child = str(child_part or "").strip()
        if not clean_child:
            return None, "none"
        taxonomy = set(str(part).strip() for part in self.project.project_data.get("taxonomy", []) if str(part).strip())

        remembered_parent = None
        get_parent = getattr(self.project, "get_blink_context_parent", None)
        if callable(get_parent):
            try:
                remembered_parent = get_parent(clean_child)
            except Exception:
                remembered_parent = None
        remembered_parent = str(remembered_parent or "").strip()
        if remembered_parent and remembered_parent in taxonomy and remembered_parent != clean_child:
            return remembered_parent, "remembered"

        route_parents = self._route_parents_for_child(clean_child)
        if len(route_parents) == 1:
            return route_parents[0], "route"

        tree_parent = self._part_tree_parent_for(clean_child)
        if tree_parent and tree_parent != clean_child:
            return tree_parent, "part_tree"
        return None, "none"

    def _parent_context_box(self, parent_part):
        if not self.current_image or not parent_part:
            return None, "none"
        manual = self.project.get_boxes(self.current_image)
        box = _clean_box(manual.get(parent_part) if isinstance(manual, dict) else None)
        if box:
            return box, "manual"
        auto, vlm = self._auto_boxes_for_canvas(self.current_image)
        box = _clean_box(auto.get(parent_part) if isinstance(auto, dict) else None)
        if box:
            return box, "auto"
        box = _clean_box(vlm.get(parent_part) if isinstance(vlm, dict) else None)
        if box:
            return box, "vlm"
        return None, "none"

    def _current_shrink_loose_boxes(self):
        if not self.current_image or not hasattr(self.project, "get_shrink_loose_boxes"):
            return {}
        boxes = self.project.get_shrink_loose_boxes(self.current_image)
        return boxes if isinstance(boxes, dict) else {}

    def _auto_boxes_for_canvas(self, image_path):
        splitter = getattr(self.project, "split_auto_boxes_by_source", None)
        if callable(splitter):
            try:
                model_boxes, vlm_boxes = splitter(image_path)
                return model_boxes if isinstance(model_boxes, dict) else {}, vlm_boxes if isinstance(vlm_boxes, dict) else {}
            except Exception:
                pass
        auto_boxes = self.project.get_auto_boxes(image_path)
        if not isinstance(auto_boxes, dict):
            return {}, {}
        meta = {}
        get_meta = getattr(self.project, "get_auto_box_meta", None)
        if callable(get_meta):
            try:
                meta = get_meta(image_path)
            except Exception:
                meta = {}
        meta = meta if isinstance(meta, dict) else {}
        model_boxes = {}
        vlm_boxes = {}
        for part_name, box in auto_boxes.items():
            part_meta = meta.get(part_name, {}) if isinstance(meta.get(part_name), dict) else {}
            if part_meta.get("source") == AUTO_BOX_SOURCE_VLM:
                vlm_boxes[part_name] = box
            else:
                model_boxes[part_name] = box
        return model_boxes, vlm_boxes

    def _refresh_current_canvas_boxes(self):
        if not self.current_image:
            return
        model_auto_boxes, vlm_auto_boxes = self._auto_boxes_for_canvas(self.current_image)
        self.canvas.set_boxes(
            self.project.get_boxes(self.current_image),
            model_auto_boxes,
            self._current_shrink_loose_boxes(),
            vlm=vlm_auto_boxes,
        )

    def _route_entry_for_context(self, parent_part, child_part):
        get_route = getattr(self.project, "get_cascade_route", None)
        if callable(get_route):
            try:
                route = get_route(parent_part, child_part)
            except Exception:
                route = None
            if isinstance(route, dict):
                return dict(route)
        for route in self.project.iter_cascade_routes():
            if not isinstance(route, dict):
                continue
            if route.get("parent") == parent_part and route.get("child") == child_part:
                return dict(route)
        return None

    def _route_expert_status(self, route_entry):
        if not isinstance(route_entry, dict):
            return "missing", tr("Route not configured", self.current_lang), False
        appointed = get_route_appointed_expert(route_entry)
        has_appointed = bool(appointed.get("expert_id"))
        block_reason = None
        cascade_manager = getattr(getattr(self, "engine", None), "cascade_manager", None)
        get_block = getattr(cascade_manager, "get_route_block_reason", None)
        if callable(get_block):
            try:
                block_reason = get_block(route_entry)
            except Exception:
                block_reason = None
        if block_reason == "expert_unappointed":
            return "unappointed", ui_text("Expert not appointed yet", self.current_lang), False
        if block_reason == "expert_model_missing":
            if has_appointed:
                return "ready", tr("Expert file missing", self.current_lang), True
            return "missing_file", tr("Expert file missing", self.current_lang), False
        if not has_appointed:
            return "unappointed", ui_text("Expert not appointed yet", self.current_lang), False
        if not bool(route_entry.get("enabled", False)):
            return "disabled", ui_text("Disabled", self.current_lang), has_appointed
        if has_appointed:
            return "ready", ui_text("Enabled", self.current_lang), True
        return "unappointed", ui_text("Expert not appointed yet", self.current_lang), False

    def _current_blink_context(self):
        selected_part = self._current_part_name()
        context = {
            "selected_part": selected_part,
            "role": "none",
            "parent_part": None,
            "child_part": None,
            "parent_source": "none",
            "route_label": "",
            "parent_box": None,
            "parent_box_source": "none",
            "has_parent_box": False,
            "route_entry": None,
            "route_status": "none",
            "route_status_text": ui_text("Unknown", self.current_lang),
            "has_appointed_expert": False,
            "can_refine": False,
            "disabled_reason": tr("Select a child structure first.", self.current_lang),
        }
        if not selected_part:
            return context

        if self._is_parent_part(selected_part):
            box, source = self._parent_context_box(selected_part)
            context.update(
                {
                    "role": "parent",
                    "parent_part": selected_part,
                    "parent_box": box,
                    "parent_box_source": source,
                    "has_parent_box": bool(box),
                    "disabled_reason": tr("Select a child structure for refinement.", self.current_lang),
                }
            )
            return context

        parent_part, parent_source = self._resolve_child_parent(selected_part)
        context.update(
            {
                "role": "child",
                "child_part": selected_part,
                "parent_part": parent_part,
                "parent_source": parent_source,
            }
        )
        if parent_part:
            context["route_label"] = f"{parent_part} -> {selected_part}"
            parent_box, parent_box_source = self._parent_context_box(parent_part)
            route_entry = self._route_entry_for_context(parent_part, selected_part)
            route_status, route_status_text, has_appointed = self._route_expert_status(route_entry)
            context.update(
                {
                    "parent_box": parent_box,
                    "parent_box_source": parent_box_source,
                    "has_parent_box": bool(parent_box),
                    "route_entry": route_entry,
                    "route_status": route_status,
                    "route_status_text": route_status_text,
                    "has_appointed_expert": has_appointed,
                }
            )
        if not parent_part:
            context["disabled_reason"] = tr("Choose or remember a parent structure for this child first.", self.current_lang)
        elif not context["has_parent_box"]:
            context["disabled_reason"] = tr("Draw a parent box before child refinement.", self.current_lang)
        elif context["route_status"] in {"missing", "unappointed", "missing_file"}:
            context["disabled_reason"] = tr("Configure a route expert before automatic child annotation.", self.current_lang)
        elif context["route_status"] == "disabled":
            context["disabled_reason"] = tr("Enable the current route before automatic child annotation.", self.current_lang)
        else:
            context["can_refine"] = True
            context["disabled_reason"] = ""
        return context

    def _parent_box_aspect_ratio(self, parent_part):
        ratios = getattr(self, "parent_box_aspect_ratios", None)
        if not isinstance(ratios, dict):
            ratios = self.project.get_parent_box_aspect_ratios() if hasattr(self.project, "get_parent_box_aspect_ratios") else {}
            self.parent_box_aspect_ratios = dict(ratios)
        try:
            ratio = float(ratios.get(parent_part))
        except Exception:
            ratio = None
        return ratio if ratio and ratio > 0 else None

    def _parent_context_options(self, child_part):
        clean_child = str(child_part or "").strip()
        if not clean_child:
            return []
        taxonomy = {
            str(part).strip()
            for part in self.project.project_data.get("taxonomy", [])
            if str(part).strip()
        }
        options = []
        for parent_part in (
            list(self._workbench_parent_parts())
            + list(self._route_parents_for_child(clean_child))
            + [self._part_tree_parent_for(clean_child)]
        ):
            clean_parent = str(parent_part or "").strip()
            if (
                clean_parent
                and clean_parent != clean_child
                and clean_parent in taxonomy
                and clean_parent not in options
            ):
                options.append(clean_parent)
        return options

    def _refresh_annotation_box_constraints(self):
        if not hasattr(self, "canvas"):
            return
        context = dict(getattr(self, "current_blink_context", {}) or self._current_blink_context())
        ratio = None
        lock_parent_ratio = True
        if hasattr(self, "check_lock_parent_box_ratio"):
            lock_parent_ratio = self.check_lock_parent_box_ratio.isChecked()
        if (
            self._active_box_tool_role() in {"sam", "annotation"}
            and lock_parent_ratio
            and context.get("role") == "parent"
        ):
            ratio = self._parent_box_aspect_ratio(context.get("parent_part"))
        self.canvas.set_annotation_box_aspect_ratio(ratio)

    def _active_box_tool_role(self):
        if hasattr(self, "radio_loose_shrink_box") and self.radio_loose_shrink_box.isChecked():
            return "shrink"
        if hasattr(self, "radio_annotation_box") and self.radio_annotation_box.isChecked():
            return "annotation"
        if hasattr(self, "radio_box") and self.radio_box.isChecked():
            return "sam"
        return "other"

    def _refresh_blink_refine_state(self):
        context = self._current_blink_context()
        self.current_blink_context = dict(context)
        self._refresh_annotation_box_constraints()
        self._update_blink_refine_panel(context)
        return context

    def _append_part_tree_item(self, parent_item, text, part_name=None, tooltip=None):
        item = QTreeWidgetItem(parent_item) if parent_item is not None else QTreeWidgetItem(self.part_list)
        item.setText(0, text)
        item.setData(0, Qt.UserRole, part_name)
        if tooltip:
            item.setToolTip(0, tooltip)
        return item

    def _select_part_in_tree(self, part_name):
        clean_name = str(part_name or "").strip()
        if not clean_name:
            return False

        def walk(item):
            if item is None:
                return None
            if self._part_item_name(item) == clean_name:
                return item
            for index in range(item.childCount()):
                found = walk(item.child(index))
                if found is not None:
                    return found
            return None

        for index in range(self.part_list.topLevelItemCount()):
            found_item = walk(self.part_list.topLevelItem(index))
            if found_item is not None:
                self.part_list.setCurrentItem(found_item)
                return True
        return False

    def _first_selectable_part_item(self):
        def walk(item):
            if item is None:
                return None
            if self._part_item_name(item):
                return item
            for index in range(item.childCount()):
                found = walk(item.child(index))
                if found is not None:
                    return found
            return None

        for index in range(self.part_list.topLevelItemCount()):
            found_item = walk(self.part_list.topLevelItem(index))
            if found_item is not None:
                return found_item
        return None

    def _refresh_part_tree(self, selected_part=None):
        if getattr(self, "_refreshing_part_tree", False):
            return
        if not hasattr(self, "part_list"):
            return
        self._refreshing_part_tree = True
        previous_selection = selected_part or self._current_part_name()
        try:
            self.part_list.blockSignals(True)
            self.part_list.clear()
            groups = build_part_tree_groups(
                self.project.project_data.get("taxonomy", []),
                self.project.get_locator_scope(),
                self.project.iter_cascade_routes(),
            )

            for parent_group in groups.get("parents", []):
                parent_part = parent_group.get("part")
                if not parent_part:
                    continue
                parent_item = self._append_part_tree_item(
                    None,
                    tr(parent_part, self.current_lang),
                    part_name=parent_part,
                    tooltip=tr("Main locator parts", self.current_lang),
                )
                for child_part in parent_group.get("children", []):
                    self._append_part_tree_item(
                        parent_item,
                        tr(child_part, self.current_lang),
                        part_name=child_part,
                        tooltip=tr("Blink child parts", self.current_lang),
                    )
                parent_item.setExpanded(True)

            cross_region = groups.get("cross_region", [])
            if cross_region:
                group_item = self._append_part_tree_item(
                    None,
                    tr("Cross-region structures", self.current_lang),
                    tooltip=tr("Structure group", self.current_lang),
                )
                for part_name in cross_region:
                    self._append_part_tree_item(group_item, tr(part_name, self.current_lang), part_name=part_name)
                group_item.setExpanded(True)

            ungrouped = groups.get("ungrouped", [])
            if ungrouped:
                group_item = self._append_part_tree_item(
                    None,
                    tr("Ungrouped structures", self.current_lang),
                    tooltip=tr("Structure group", self.current_lang),
                )
                for part_name in ungrouped:
                    self._append_part_tree_item(group_item, tr(part_name, self.current_lang), part_name=part_name)
                group_item.setExpanded(True)

            selected = self._select_part_in_tree(previous_selection)
            if not selected:
                first_part_item = self._first_selectable_part_item()
                if first_part_item is not None:
                    self.part_list.setCurrentItem(first_part_item)
        finally:
            self.part_list.blockSignals(False)
            self._refreshing_part_tree = False

        current_part = self._current_part_name()
        if current_part:
            self.canvas.set_active_part(current_part)
            self.update_db_description(current_part)
        else:
            self.canvas.set_active_part(None)
            self.desc_box.clear()
        if hasattr(self, "blink_refine_panel"):
            self._refresh_blink_refine_state()

    def add_taxonomy_part(self):
        name, ok = QInputDialog.getText(self, tr("Add Structure", self.current_lang), tr("Structure Name:", self.current_lang))
        if ok and name:
            if self.project.add_taxonomy_part(name.strip()):
                self.refresh_ui()
                self.project.save_project()
            else:
                QMessageBox.warning(self, tr("Error", self.current_lang), tr("Exists.", self.current_lang))

    def _count_ai_labels_for_images(self, image_paths):
        count = 0
        for image_path in image_paths or []:
            entry = self.project.project_data.get("labels", {}).get(image_path, {})
            descriptions = entry.get("descriptions", {}) if isinstance(entry.get("descriptions", {}), dict) else {}
            count += sum(1 for desc in descriptions.values() if desc == "Auto-Annotated")
        return count

    def _choose_clear_ai_scope(self):
        all_images = [path for path in self.project.project_data.get("images", []) if path]
        scope_options = [("__all__", tr("All project images", self.current_lang), all_images)]
        image_groups = self._project_image_groups(images=all_images)
        for group_id, group_label in self._all_image_group_definitions():
            group_images = list(image_groups.get(group_id, []) or [])
            if group_images:
                scope_options.append((group_id, tr("Images in group: {0}", self.current_lang).format(group_label), group_images))

        dialog = QDialog(self)
        dialog.setWindowTitle(tr("Clear AI Label Scope", self.current_lang))
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        layout.addWidget(QLabel(tr("Scope:", self.current_lang)))
        scope_combo = NoWheelComboBox()
        for group_id, label, paths in scope_options:
            scope_combo.addItem(label, {"group_id": group_id, "label": label, "paths": list(paths)})
        layout.addWidget(scope_combo)
        summary_label = QLabel()
        summary_label.setWordWrap(True)
        summary_label.setObjectName("mutedLabel")
        layout.addWidget(summary_label)
        button_row = QHBoxLayout()
        clear_button = QPushButton(tr("Clear AI", self.current_lang))
        apply_semantic_button_style(clear_button, BUTTON_ROLE_DESTRUCTIVE)
        cancel_button = QPushButton(tr("Cancel", self.current_lang))
        apply_semantic_button_style(cancel_button, BUTTON_ROLE_STOP)
        button_row.addStretch(1)
        button_row.addWidget(clear_button)
        button_row.addWidget(cancel_button)
        layout.addLayout(button_row)
        selected_payload = {"accepted": False, "paths": [], "label": "", "count": 0}

        def refresh_summary():
            payload = scope_combo.currentData() or {}
            paths = list(payload.get("paths", []) or [])
            count = self._count_ai_labels_for_images(paths)
            selected_payload.update({"paths": paths, "label": payload.get("label", ""), "count": count})
            if count:
                summary_label.setText(
                    tr(
                        "This will remove {0} AI label(s) from {1} image(s). Manual and confirmed labels are kept.",
                        self.current_lang,
                    ).format(count, len(paths))
                )
                clear_button.setEnabled(True)
            else:
                summary_label.setText(tr("No AI labels found in the selected scope.", self.current_lang))
                clear_button.setEnabled(False)

        def accept_scope():
            selected_payload["accepted"] = True
            dialog.accept()

        scope_combo.currentIndexChanged.connect(lambda _index: refresh_summary())
        clear_button.clicked.connect(accept_scope)
        cancel_button.clicked.connect(dialog.reject)
        refresh_summary()
        self._prepare_progress_dialog(dialog, width=460)
        if not dialog.exec() or not selected_payload["accepted"]:
            return None
        return {
            "paths": list(selected_payload.get("paths", []) or []),
            "label": str(selected_payload.get("label", "") or ""),
            "count": int(selected_payload.get("count", 0) or 0),
        }

    def rename_taxonomy_part(self):
        old_name = self._current_part_name()
        if not old_name:
            return
        new_name, ok = QInputDialog.getText(
            self,
            tr("Rename Structure", self.current_lang),
            tr("New Structure Name:", self.current_lang),
            text=old_name,
        )
        new_name = str(new_name or "").strip()
        if not ok or not new_name or new_name == old_name:
            return
        if themed_yes_no_question(
            self,
            tr("Rename Structure", self.current_lang),
            tr(
                "Rename '{0}' to '{1}'? Existing labels, VLM drafts, parent-child routes, and training context for this structure will be moved to the new name.",
                self.current_lang,
            ).format(old_name, new_name),
            confirm_role=BUTTON_ROLE_COMMIT,
        ) != QMessageBox.Yes:
            return

        rename_part = getattr(self.project, "rename_taxonomy_part", None)
        renamed = bool(rename_part(old_name, new_name, save=False)) if callable(rename_part) else False
        if not renamed:
            QMessageBox.warning(
                self,
                tr("Rename Structure", self.current_lang),
                tr("Could not rename structure. The new name may already exist or contain unsafe characters.", self.current_lang),
            )
            return

        self._schedule_project_save()
        self.refresh_ui()
        self._select_part_in_tree(new_name)
        if self.current_image:
            self.canvas.set_polygons(self.project.get_labels(self.current_image))
            self._refresh_current_canvas_boxes()
        self._refresh_blink_refine_state()

    def remove_taxonomy_part(self):
        part_name = self._current_part_name()
        if not part_name:
            return
        if themed_yes_no_question(
            self,
            tr("Remove Structure", self.current_lang),
            tr("Delete '{0}'?", self.current_lang).format(part_name),
            confirm_role=BUTTON_ROLE_DESTRUCTIVE,
        ) == QMessageBox.Yes:
            if self.project.remove_taxonomy_part(part_name):
                self.refresh_ui()
                self.project.save_project()

    def clear_ai_labels(self):
        choose_scope = getattr(self, "_choose_clear_ai_scope", None)
        if callable(choose_scope):
            scope = choose_scope()
        else:
            scope = {
                "paths": list(getattr(self.project, "project_data", {}).get("images", []) or []) or ["__all__"],
                "count": 1,
                "label": tr("All project images", self.current_lang),
                "legacy_message": True,
            }
        if not scope:
            return
        paths = list(scope.get("paths", []) or [])
        expected_count = int(scope.get("count", 0) or 0)
        scope_label = str(scope.get("label", "") or tr("All project images", self.current_lang))
        if expected_count <= 0 or not paths:
            self.log(tr("No AI labels found in the selected scope.", self.current_lang))
            return
        if scope.get("legacy_message"):
            message = tr("Clear all AI labels from the current project?", self.current_lang)
        else:
            message = (
                tr("Clear selected AI labels?", self.current_lang)
                + "\n\n"
                + tr(
                    "This will remove {0} AI label(s) from {1} image(s). Manual and confirmed labels are kept.",
                    self.current_lang,
                ).format(expected_count, len(paths))
                + f"\n{scope_label}"
            )
        if themed_yes_no_question(
            self,
            tr("Clear AI Labels", self.current_lang),
            message,
            confirm_role=BUTTON_ROLE_DESTRUCTIVE,
        ) != QMessageBox.Yes:
            return
        remove_auto_labels_for_images = getattr(self.project, "remove_auto_labels_for_images", None)
        if callable(remove_auto_labels_for_images):
            c = remove_auto_labels_for_images(paths, save=False)
        else:
            remove_auto_labels = getattr(self.project, "remove_auto_labels")
            try:
                c = remove_auto_labels(save=False)
            except TypeError:
                c = remove_auto_labels()
        if c:
            self._schedule_project_save()
        self.refresh_file_list()
        if self.current_image:
            self.canvas.set_polygons(self.project.get_labels(self.current_image))
            self._refresh_current_canvas_boxes()
        self._refresh_blink_refine_state()
        self.log(tr("Removed {0} AI labels from {1}.", self.current_lang).format(c, scope_label))

    def on_global_labels_updated(self):
        """Called when the child expert session applies changes back to the global project."""
        if self.current_image:
            self.canvas.set_polygons(self.project.get_labels(self.current_image))
            self._refresh_current_canvas_boxes()
        self.log(tr("Global labels updated from Child Expert Session.", self.current_lang))

    def refresh_ui(self):
        if self.engine:
            current_locator_scope = self.project.get_locator_scope()
            curr_scope_len = len(current_locator_scope)
        if curr_scope_len != self.engine.current_num_classes:
                self.log(
                    tr("Syncing Locator Scope ({0} -> {1})...", self.current_lang).format(
                        self.engine.current_num_classes, curr_scope_len
                    )
                )
                if self.engine.locator is not None:
                    self.engine.rebuild_locator(curr_scope_len, self.train_lr, self.train_wd)
                else:
                    self.engine.current_num_classes = curr_scope_len
                    self.engine.loaded_locator_timestamp = None
                    self.engine.loaded_locator_requires_legacy_confirmation = False
                    self.engine.loaded_locator_is_legacy_512 = False
                # FIX: Do NOT auto-load weights here as they might mismatch dimensions.
                self.log(tr("Locator scope changed. Please retrain or select a matching model.", self.current_lang))
                self.refresh_model_list()
        self.setWindowTitle(f"{WORKBENCH_WINDOW_TITLE} ({self.current_lang.upper()})")
        self.create_menus()
        self.btn_export.setText(tr("Export Dataset", self.current_lang))
        self.btn_crop.setText(tr("Import & Crop", self.current_lang))
        self.btn_batch_split_panels.setText(tr("Batch Split Plates", self.current_lang))
        self.btn_add.setText(tr("+ Add Images", self.current_lang))
        self.label_project_images.setText(tr("PROJECT IMAGES", self.current_lang))
        self.label_taxonomy.setText(tr("Current image taxon", self.current_lang))
        taxon_tooltip = tr(
            "Per-image taxon metadata used for export and literature search hints. This does not change the structure labels.",
            self.current_lang,
        )
        self.label_taxonomy.setToolTip(taxon_tooltip)
        self.genus_combo.setToolTip(taxon_tooltip)
        self.label_structures.setText(tr("Structures", self.current_lang))
        if hasattr(self, "btn_rename_part"):
            self.btn_rename_part.setText(tr("Rename Structure", self.current_lang))
        self.label_ai_workflow.setText(tr("Auto Annotation", self.current_lang))
        self.label_parent_annotation.setText(tr("Parent-part annotation", self.current_lang))
        backend_label = tr("Built-in Locator + SAM", self.current_lang)
        if self.model_backend == EXTERNAL_BACKEND_ID:
            backend_label = self.external_backend_config.get("display_name") or tr("External Script Backend", self.current_lang)
        active_parent_backend = _runtime_parent_backend(self.project, self.model_backend)
        if active_parent_backend == EXTERNAL_BACKEND_ID:
            backend_config = self._active_external_backend_config()
            backend_label = backend_config.get("display_name") or tr("External Script Backend", self.current_lang)
        elif active_parent_backend == BUILTIN_BACKEND_ID:
            backend_label = tr("Built-in Locator + SAM", self.current_lang)
        self.label_model_backend.setText(f"{tr('Model Backend:', self.current_lang)} {backend_label}")
        self.btn_predict.setText(tr("Auto (Current)", self.current_lang))
        self.btn_batch.setText(tr("Batch (All)", self.current_lang))
        if hasattr(self, "btn_vlm_preannotate_current"):
            self.btn_vlm_preannotate_current.setText(tr("VLM Pre-Label", self.current_lang))
            self.btn_vlm_preannotate_current.setToolTip(
                tr(
                    "Use the configured multimodal model to propose draft boxes for the current image only.",
                    self.current_lang,
                )
            )
        if hasattr(self, "btn_vlm_preannotate_batch"):
            self.btn_vlm_preannotate_batch.setText(tr("VLM Batch Pre-Label", self.current_lang))
            self.btn_vlm_preannotate_batch.setToolTip(
                tr(
                    "Use the configured multimodal model to batch pre-annotate the configured image range.",
                    self.current_lang,
                )
            )
        if hasattr(self, "btn_accept_current_ai_drafts"):
            self.btn_accept_current_ai_drafts.setText(tr("Confirm current AI polygon drafts", self.current_lang))
            self.btn_accept_current_ai_drafts.setToolTip(
                tr(
                    "Only confirms AI drafts that already have polygons. Box-only drafts stay pending until SAM or manual drawing creates a polygon.",
                    self.current_lang,
                )
            )
        if hasattr(self, "btn_accept_batch_ai_drafts"):
            self.btn_accept_batch_ai_drafts.setText(tr("Confirm batch AI polygon drafts", self.current_lang))
            self.btn_accept_batch_ai_drafts.setToolTip(
                tr(
                    "Confirms polygon AI drafts across the current project after a confirmation dialog.",
                    self.current_lang,
                )
            )
        self.chk_train_locator_only.setText(tr("Train Locator only (skip SAM)", self.current_lang))
        self.chk_train_locator_only.setToolTip(
            tr(
                "Skip SAM/parts training for this run. Useful when the base SAM result is already good enough.",
                self.current_lang,
            )
        )
        if hasattr(self, "lbl_training_scope"):
            self.lbl_training_scope.setText(tr("Training Scope:", self.current_lang))
        self._refresh_training_scope_combo()
        self.btn_train.setText(tr("Train Models", self.current_lang))
        self.btn_stop_training.setText(tr("Stop Training", self.current_lang))
        self.btn_clear_ai.setText(tr("Clear AI Labels", self.current_lang))
        if hasattr(self, "label_training_progress"):
            self.label_training_progress.setText(tr("Training progress", self.current_lang))
        if hasattr(self, "btn_training_results"):
            self.btn_training_results.setText(tr("Training Results", self.current_lang))
        if hasattr(self, "label_training_progress_status") and not self.active_training_label:
            self.label_training_progress_status.setText(tr("No training running.", self.current_lang))
        self.btn_blink_entry.setText(tr("Open Child Expert Session", self.current_lang))
        self.btn_blink_entry.setVisible(False)
        if hasattr(self, "btn_literature_descriptions"):
            self.btn_literature_descriptions.setText(tr("Literature Traits", self.current_lang))
            self.btn_literature_descriptions.setToolTip(
                tr(
                    "Search PDF-extracted taxon/part descriptions linked to the current image and apply one to the current part description box.",
                    self.current_lang,
                )
            )
        self.btn_start_center_from_workbench.setText(tr("Start Center", self.current_lang))
        self.btn_agent_from_workbench.setText(tr("Ask Agent", self.current_lang))
        self.label_blink_refine.setText(tr("Child-part annotation", self.current_lang))
        self.btn_configure_route_expert.setText(tr("Configure Route Expert", self.current_lang))
        self.btn_blink_auto_annotate.setText(tr("Annotate child from existing parent box", self.current_lang))
        self.btn_blink_auto_shrink.setText(tr("Run auto-shrink", self.current_lang))
        if hasattr(self, "btn_blink_batch_auto_shrink"):
            self.btn_blink_batch_auto_shrink.setText(tr("Batch auto-shrink", self.current_lang))
        self.btn_blink_train_expert.setText(tr("Train current child expert", self.current_lang))
        if hasattr(self, "btn_blink_stop_training"):
            self.btn_blink_stop_training.setText(tr("Stop Training", self.current_lang))
        if hasattr(self, "label_blink_parent_context"):
            self.label_blink_parent_context.setText(tr("Parent context:", self.current_lang))
        self.label_logs.setText(tr("LOGS", self.current_lang))
        self.radio_draw.setText(tr("Manual Draw", self.current_lang))
        self.radio_magic.setText(tr("Magic Wand (SAM)", self.current_lang))
        self.radio_box.setText(tr("SAM Box Segmentation", self.current_lang))
        self.radio_box.setToolTip(
            tr(
                "Draw a box to run SAM immediately and create a draft polygon for the current part.",
                self.current_lang,
            )
        )
        self.radio_annotation_box.setText(tr("Manual ROI Box", self.current_lang))
        self.radio_annotation_box.setToolTip(
            tr(
                "Draw or replace the manually confirmed ROI box saved with the current part. It does not run SAM by itself.",
                self.current_lang,
            )
        )
        self.radio_loose_shrink_box.setText(tr("Blink Shrink Start Box", self.current_lang))
        self.radio_loose_shrink_box.setToolTip(
            tr(
                "Draw a loose starting box around a child structure for Blink auto-shrink trajectory training. It is not the final annotation box.",
                self.current_lang,
            )
        )
        self.radio_scale.setText(tr("Scale Tool", self.current_lang))
        self.check_morpho.setText(tr("Enable Morphometrics", self.current_lang))
        self.group_morpho.setTitle(tr("Measurements", self.current_lang))
        self.lbl_locator.setText(tr("Locator:", self.current_lang))
        self.lbl_segmenter.setText(tr("Segmenter:", self.current_lang))
        self.btn_note_locator.setText(tr("Note", self.current_lang))
        self.btn_note_locator.setToolTip(tr("Edit the selected locator model display note.", self.current_lang))
        self.btn_del_locator.setText(tr("Del", self.current_lang))
        self.btn_del_locator.setToolTip(tr("Delete the selected locator model file from disk.", self.current_lang))
        self.btn_note_segmenter.setText(tr("Note", self.current_lang))
        self.btn_note_segmenter.setToolTip(tr("Edit the selected segmenter model display note.", self.current_lang))
        self.btn_del_segmenter.setText(tr("Del", self.current_lang))
        self.btn_del_segmenter.setToolTip(tr("Delete the selected segmenter model file from disk.", self.current_lang))
        for index in range(self.tabs.count()):
            widget = self.tabs.widget(index)
            if widget is self.workbench_widget:
                self.tabs.setTabText(index, tr("Labeling Workbench", self.current_lang))
            elif widget is self.blink_lab:
                self.tabs.setTabText(index, tr("Child Expert Session", self.current_lang))
            elif widget is self.tif_workbench:
                self.tabs.setTabText(index, tr("TIF Volume Workbench", self.current_lang))
            elif widget is self.pdf_widget:
                self.tabs.setTabText(index, tr("PDF Evidence Tools", self.current_lang))
            elif widget is self.start_center_widget:
                self.tabs.setTabText(index, tr("Start Center", self.current_lang))
        self._update_start_center_texts()
        self.genus_combo.blockSignals(True)
        self.genus_combo.clear()
        if hasattr(self.project, "list_taxa"):
            taxa = self.project.list_taxa()
        else:
            labels_vals = self.project.project_data["labels"].values()
            taxa = sorted(list(set(["Unknown"] + [d.get("genus", "Unknown") for d in labels_vals])))
        self.genus_combo.addItems(taxa)
        get_taxon = getattr(self.project, "get_taxon", self.project.get_genus)
        self.genus_combo.setCurrentText(get_taxon(self.current_image) if self.current_image else "Unknown")
        self.genus_combo.blockSignals(False)
        if self.check_morpho.isChecked() and self._current_part_name():
            self.update_measurements(self._current_part_name())
        self.refresh_route_table()
        self._refresh_blink_refine_state()

    def _update_blink_refine_panel(self, context=None):
        if not hasattr(self, "blink_refine_panel"):
            return
        context = dict(context or getattr(self, "current_blink_context", {}) or {})
        role = context.get("role") or "none"
        selected_part = context.get("selected_part") or ""
        parent_part = context.get("parent_part") or ""
        child_part = context.get("child_part") or ""

        if role == "parent":
            role_text = tr("Parent context", self.current_lang)
            box_status = tr("parent box exists", self.current_lang) if context.get("has_parent_box") else tr("parent box missing", self.current_lang)
            summary = tr("Current structure: {0} ({1}); {2}.", self.current_lang).format(selected_part, role_text, box_status)
        elif role == "child":
            role_text = tr("Child structure", self.current_lang)
            route_text = context.get("route_label") or tr("Parent not selected", self.current_lang)
            summary = tr("Current structure: {0} ({1}); route {2}.", self.current_lang).format(selected_part, role_text, route_text)
        else:
            summary = tr("Select a structure to see Blink parent-child status.", self.current_lang)

        self.blink_context_status_label.setText(summary)
        self.label_blink_route.setText(
            tr("Current route: {0}", self.current_lang).format(context.get("route_label") or tr("Not available", self.current_lang))
        )
        self.label_blink_parent_context.setText(tr("Parent context:", self.current_lang))
        self._update_blink_parent_context_combo(context)
        parent_box_text = tr("Parent box: {0}", self.current_lang).format(
            tr("available ({0})", self.current_lang).format(context.get("parent_box_source"))
            if context.get("has_parent_box")
            else tr("missing", self.current_lang)
        )
        if parent_part and role == "child":
            parent_box_text = f"{parent_part} · {parent_box_text}"
        self.label_blink_parent_box.setText(parent_box_text)
        self.label_blink_expert.setText(
            tr("Route expert: {0}", self.current_lang).format(context.get("route_status_text") or ui_text("Unknown", self.current_lang))
        )
        self.check_lock_parent_box_ratio.setText(tr("Lock parent box ratio", self.current_lang))
        self.check_lock_parent_box_ratio.setToolTip(
            tr(
                "Off by default. Enable when preparing fixed-ratio parent boxes for child-part training; it affects parent SAM box prompts and parent manual ROI boxes.",
                self.current_lang,
            )
        )

        can_open_route = bool(parent_part and child_part)
        self.btn_configure_route_expert.setEnabled(can_open_route)
        self.btn_configure_route_expert.setToolTip(
            tr("Open route expert settings for {0}.", self.current_lang).format(context.get("route_label"))
            if can_open_route
            else tr("Select a child structure with a parent context first.", self.current_lang)
        )

        can_refine = bool(context.get("can_refine"))
        disabled_reason = str(context.get("disabled_reason") or "")
        self.btn_blink_auto_annotate.setEnabled(can_refine)
        self.btn_blink_auto_annotate.setToolTip(disabled_reason)
        self.btn_blink_auto_shrink.setEnabled(bool(role == "child" and parent_part and context.get("has_parent_box")))
        self.btn_blink_auto_shrink.setToolTip(disabled_reason if not self.btn_blink_auto_shrink.isEnabled() else "")
        if hasattr(self, "btn_blink_batch_auto_shrink"):
            self.btn_blink_batch_auto_shrink.setEnabled(bool(role == "child" and parent_part))
            self.btn_blink_batch_auto_shrink.setToolTip(disabled_reason if not self.btn_blink_batch_auto_shrink.isEnabled() else "")
        parent_training_busy = self._is_parent_training_running()
        child_training_busy = self._is_child_training_running()
        training_busy = parent_training_busy or child_training_busy
        can_train_child = bool(role == "child" and parent_part) and not training_busy
        self.btn_blink_train_expert.setEnabled(can_train_child)
        if self.btn_blink_train_expert.isEnabled():
            train_child_tooltip = tr("Training uses saved shrink trajectories for this parent-child route.", self.current_lang)
        elif parent_training_busy:
            train_child_tooltip = tr("Parent-part training is running. Wait for it to finish before training a child expert.", self.current_lang)
        elif child_training_busy:
            train_child_tooltip = tr("Blink expert training is already running.", self.current_lang)
        else:
            train_child_tooltip = tr("Select a child structure with a parent context first.", self.current_lang)
        self.btn_blink_train_expert.setToolTip(
            train_child_tooltip
        )

    def _update_blink_parent_context_combo(self, context):
        if not hasattr(self, "combo_blink_parent_context"):
            return
        context = dict(context or {})
        combo = self.combo_blink_parent_context
        self._updating_blink_parent_context = True
        try:
            combo.blockSignals(True)
            combo.clear()
            role = context.get("role")
            child_part = context.get("child_part")
            parent_part = context.get("parent_part")
            options = self._parent_context_options(child_part) if role == "child" else []
            prompt_text = tr("Choose parent context", self.current_lang)
            unavailable_text = tr("Parent context unavailable", self.current_lang)
            if hasattr(combo, "setPlaceholderText"):
                combo.setPlaceholderText(prompt_text if role == "child" else unavailable_text)
            for option in options:
                combo.addItem(option, option)
            index = combo.findData(parent_part)
            if index >= 0:
                combo.setCurrentIndex(index)
            elif options:
                combo.setCurrentIndex(-1)
            else:
                combo.addItem(unavailable_text, "")
                item = combo.model().item(0) if combo.model() is not None else None
                if item is not None:
                    item.setEnabled(False)
                combo.setCurrentIndex(0)
            combo.setEnabled(role == "child" and bool(options))
            combo.setToolTip(
                prompt_text
                if combo.isEnabled()
                else unavailable_text
            )
        finally:
            combo.blockSignals(False)
            self._updating_blink_parent_context = False

    def open_general_settings(self):
        params = {
            "language": self.current_lang,
            "theme": self.current_theme,
            "startup_behavior": self.config.get("startup_behavior", "start_center"),
            "project_autosave_interval_sec": max(1, int(self.project_autosave_delay_ms / 1000)),
            "runtime_device": self.runtime_device,
        }
        dlg = GeneralSettingsDialog(params, self.current_lang, self)
        dlg.agent_requested.connect(self.open_agent_from_context)
        if not dlg.exec():
            return
        values = dlg.get_values()
        if not values:
            return

        old_lang = self.current_lang
        old_theme = self.current_theme
        old_runtime_device = self.runtime_device
        self.project_autosave_delay_ms = max(1, int(values["project_autosave_interval_sec"])) * 1000
        self.config.set("startup_behavior", values["startup_behavior"])
        self.config.set("project_autosave_interval_sec", int(values["project_autosave_interval_sec"]))

        new_runtime_device = normalize_device_preference(values.get("runtime_device", "auto"))
        self.runtime_device = new_runtime_device
        self.config.set("runtime_device", self.runtime_device)
        if old_runtime_device != self.runtime_device:
            if self.engine.set_device_preference(self.runtime_device):
                self.log(tr("Runtime device resolved to: {0}", self.current_lang).format(str(self.engine.device)))
            if self.sam_worker:
                self.sam_worker.device_preference = self.runtime_device
                self.sam_worker.reload_base_model()
                selected_segmenter = self._selected_segmenter_timestamp()
                if selected_segmenter:
                    weights_path = self._segmenter_model_path(selected_segmenter)
                    if weights_path:
                        self.sam_worker.load_decoder_weights(weights_path)
            if hasattr(self, "blink_lab"):
                self._sync_blink_lab_model_profile_defaults()

        if values["language"] != old_lang:
            self.change_language(values["language"])
        else:
            self.config.set("language", self.current_lang)
        if values["theme"] != old_theme:
            self.change_theme(values["theme"])
        else:
            self.config.set("theme", self.current_theme)
        self.config.save()
        self.log(tr("General settings updated.", self.current_lang))
        self.refresh_ui()

    def open_stl_model_settings(self, target_route=None, focus_vlm=False):
        params = {
            'epochs': self.train_epochs, 'batch': self.train_batch, 'lr': self.train_lr, 'wd': self.train_wd,
            'blink_epochs': self.blink_train_epochs,
            'blink_batch': self.blink_train_batch,
            'blink_lr': self.blink_train_lr,
            'blink_weight_decay': self.blink_train_weight_decay,
            'blink_input_size': self.blink_train_input_size,
            'blink_auto_shrink_steps': self.blink_auto_shrink_steps,
            'blink_training_strategy': self.blink_training_strategy,
            'conf': self.inf_conf, 'adapt': self.inf_adapt, 'pad': self.inf_pad, 
            'noise_floor': self.inf_noise_floor, 'poly_epsilon': self.inf_poly_epsilon,
            'model_backend': self.model_backend,
            'external_backend': self.external_backend_config,
            'runtime_device': self.runtime_device,
            'taxonomy': self.project.project_data.get("taxonomy", []),
            'locator_scope': self.project.get_locator_scope(),
            'vlm_preannotation': self.project.get_vlm_preannotation_settings() if hasattr(self.project, "get_vlm_preannotation_settings") else {},
            'vlm_image_group_definitions': self._all_image_group_definitions(),
            'parent_box_aspect_ratios': self.project.get_parent_box_aspect_ratios() if hasattr(self.project, "get_parent_box_aspect_ratios") else {},
            'model_profiles': self.project.get_model_profiles() if hasattr(self.project, "get_model_profiles") else {},
        }
        route_panel = getattr(self, "route_settings_panel", None)
        if route_panel is not None:
            route_panel.setParent(None)
        dlg = ModelSettingsDialog(params, self.current_lang, self, route_panel=route_panel)
        if focus_vlm and hasattr(dlg, "tabs"):
            dlg.tabs.setCurrentIndex(getattr(dlg, "inference_tab_index", 0))
        if target_route and route_panel is not None:
            if hasattr(dlg, "tabs"):
                dlg.tabs.setCurrentIndex(getattr(dlg, "inference_tab_index", 0))
            parent_part, child_part = target_route
            route_panel.refresh_route_table()
            route_item = route_panel._find_route_item(parent_part, child_part)
            if route_item is not None:
                route_panel.route_tree.setCurrentItem(route_item)
                route_panel.route_tree.scrollToItem(route_item)
        dlg.agent_requested.connect(self.open_agent_from_context)
        if dlg.exec():
            v = dlg.get_values()
            if not v:
                if route_panel is not None:
                    route_panel.setParent(self)
                return
            self.train_epochs, self.train_batch = v['epochs'], v['batch']
            self.blink_train_epochs, self.blink_train_batch = v['blink_epochs'], v['blink_batch']
            self.blink_train_lr = v['blink_lr']
            self.blink_train_weight_decay = v['blink_weight_decay']
            self.blink_train_input_size = v['blink_input_size']
            self.blink_auto_shrink_steps = v.get('blink_auto_shrink_steps', DEFAULT_CHILD_AUTO_SHRINK_STEPS)
            self.blink_training_strategy = sanitize_blink_training_strategy(
                v.get("blink_training_strategy", DEFAULT_BLINK_TRAINING_STRATEGY)
            )
            self.train_lr, self.train_wd = v['lr'], v['wd']
            self.inf_conf, self.inf_adapt = v['conf'], v['adapt']
            self.inf_pad, self.inf_noise_floor = v['pad'], v['noise_floor']
            self.inf_poly_epsilon = v['poly_epsilon']
            old_runtime_device = self.runtime_device
            self.runtime_device = normalize_device_preference(v.get("runtime_device", "auto"))
            self.model_backend = v.get("model_backend", BUILTIN_BACKEND_ID)
            self.external_backend_config = sanitize_external_backend_config(v.get("external_backend", {}))
            self.project.set_locator_scope(v.get("locator_scope", []), save=False)
            if hasattr(self.project, "set_vlm_preannotation_settings"):
                self.project.set_vlm_preannotation_settings(v.get("vlm_preannotation", {}), save=False)
            self.project.project_data["parent_box_aspect_ratios"] = v.get("parent_box_aspect_ratios", {})
            if hasattr(self.project, "mark_sqlite_project_dirty"):
                self.project.mark_sqlite_project_dirty()
            if hasattr(self.project, "set_model_profiles"):
                self.project.set_model_profiles(v.get("model_profiles", {}), save=False)
                active_profile_id = (v.get("model_profiles", {}) or {}).get("active_profile_id")
                if active_profile_id:
                    try:
                        self.project.set_active_model_profile(active_profile_id, save=False)
                    except Exception:
                        pass
            self.parent_box_aspect_ratios = (
                self.project.get_parent_box_aspect_ratios()
                if hasattr(self.project, "get_parent_box_aspect_ratios")
                else dict(v.get("parent_box_aspect_ratios", {}))
            )
            
            self.config.set("train_epochs", self.train_epochs)
            self.config.set("train_batch", self.train_batch)
            self.config.set("blink_train_epochs", self.blink_train_epochs)
            self.config.set("blink_train_batch", self.blink_train_batch)
            self.config.set("blink_train_lr", self.blink_train_lr)
            self.config.set("blink_train_weight_decay", self.blink_train_weight_decay)
            self.config.set("blink_train_input_size", self.blink_train_input_size)
            self.config.set("blink_auto_shrink_steps", self.blink_auto_shrink_steps)
            self.config.set("blink_training_strategy", self.blink_training_strategy)
            self.config.set("train_lr", self.train_lr)
            self.config.set("train_weight_decay", self.train_wd)
            self.config.set("inf_conf_thresh", self.inf_conf)
            self.config.set("inf_adapt_thresh", self.inf_adapt)
            self.config.set("inf_box_pad", self.inf_pad)
            self.config.set("inf_noise_floor", self.inf_noise_floor)
            self.config.set("inf_poly_epsilon", self.inf_poly_epsilon)
            self.config.set("runtime_device", self.runtime_device)
            self.config.set("model_backend", self.model_backend)
            self.config.set("external_backend", self.external_backend_config)
            self.project.save_project()
            
            self.engine.update_hyperparameters(self.train_lr, self.train_wd)
            if self.engine.set_device_preference(self.runtime_device):
                self.log(tr("Runtime device resolved to: {0}", self.current_lang).format(str(self.engine.device)))
            
            # Update SAM Worker epsilon
            if self.sam_worker:
                self.sam_worker.set_epsilon(self.inf_poly_epsilon)
                if old_runtime_device != self.runtime_device:
                    self.sam_worker.device_preference = self.runtime_device
                    self.sam_worker.reload_base_model()
                    selected_segmenter = self._selected_segmenter_timestamp()
                    if selected_segmenter:
                        weights_path = self._segmenter_model_path(selected_segmenter)
                        if weights_path:
                            self.sam_worker.load_decoder_weights(weights_path)

            if hasattr(self, "blink_lab"):
                self._sync_blink_lab_model_profile_defaults()

            self.log(tr("Settings updated.", self.current_lang))
            self.refresh_ui()

        if route_panel is not None:
            route_panel.setParent(self)
            route_panel.set_language(self.current_lang)
            route_panel.set_theme(self.current_theme)
        self.refresh_route_table()

    def open_settings(self):
        self.open_stl_model_settings()

    def open_tif_model_settings(self):
        if not self._is_tif_workflow_enabled():
            self._show_tif_workflow_unavailable()
            return
        current_config = self.config.get("tif_backend", DEFAULT_TIF_BACKEND_CONFIG)
        dlg = TifModelSettingsDialog(current_config, self.current_lang, self)
        dlg.agent_requested.connect(self.open_agent_from_context)
        if not dlg.exec():
            return
        backend_config = dlg.get_values()
        self.config.set("tif_backend", dict(backend_config))
        self.config.save()
        if hasattr(self, "tif_workbench"):
            self.tif_workbench.set_config_manager(self.config)
        self.log(tr("TIF backend settings updated.", self.current_lang))

    def change_language(self, lang):
        self.current_lang = lang
        self.config.set("language", lang)
        self.pdf_widget.change_language(lang)
        self.tif_workbench.change_language(lang)
        self.blink_lab.change_language(lang)
        if hasattr(self, "route_settings_panel"):
            self.route_settings_panel.set_language(lang)
        self.refresh_model_list()
        self.refresh_ui()
        self._refresh_vlm_image_group_combo()
        self.change_theme(self.current_theme)
        self.log(tr("Language: {0}", self.current_lang).format(lang))

    def change_theme(self, theme):
        theme = normalize_theme(theme)
        self.current_theme = theme
        self.config.set("theme", theme)
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.setProperty("activeTheme", theme)
            app.setPalette(build_theme_palette(theme))
        self.setStyleSheet(get_theme_stylesheet(theme))

        for widget in [self.pdf_widget, self.blink_lab, self.canvas, getattr(self, "tif_workbench", None), getattr(self, "agent_panel", None)]:
            if hasattr(widget, "set_theme"):
                widget.set_theme(theme)

        if hasattr(self, "route_settings_panel"):
            self.route_settings_panel.set_theme(theme)

        self.update_widget_themes()
        self.update_button_themes()
        refresh_themed_buttons(self, theme)
        theme_label = tr("Light Mode", self.current_lang) if theme == "light" else tr("Dark Mode (Deep Space Neon)", self.current_lang)
        self.log(f"{tr('Theme', self.current_lang)}: {theme_label}")

    def update_widget_themes(self):
        c = get_theme_config(self.current_theme)

        if hasattr(self, "desc_box"):
            self.desc_box.setStyleSheet(
                f"color: {c['text_soft']}; font-style: italic; background-color: {c['bg_input']};"
                f"border: 1px solid {c['border']}; border-radius: 10px; padding: 8px 10px; font-size: 10pt;"
            )

        if hasattr(self, "log_console"):
            self.log_console.setStyleSheet(
                f"background-color: {c['bg_input']}; color: {c['text_main']};"
                f"font-family: Consolas, 'Courier New', monospace; font-size: 9pt;"
                f"border: 1px solid {c['border']}; border-radius: 10px; padding: 8px;"
            )

    def update_button_themes(self):
        if hasattr(self, "btn_export"):
            apply_theme_button_style(self.btn_export, BUTTON_ROLE_COMMIT, "", self.current_theme)
        if hasattr(self, "btn_crop"):
            apply_theme_button_style(self.btn_crop, BUTTON_ROLE_NEUTRAL, "", self.current_theme)
        if hasattr(self, "btn_batch_split_panels"):
            apply_theme_button_style(self.btn_batch_split_panels, BUTTON_ROLE_NEUTRAL, "", self.current_theme)
        if hasattr(self, "btn_blink_entry"):
            apply_theme_button_style(self.btn_blink_entry, BUTTON_ROLE_NEUTRAL, "", self.current_theme)
        if hasattr(self, "btn_start_center_from_workbench"):
            apply_theme_button_style(self.btn_start_center_from_workbench, BUTTON_ROLE_NEUTRAL, "", self.current_theme)
        if hasattr(self, "btn_agent_from_workbench"):
            apply_theme_button_style(self.btn_agent_from_workbench, BUTTON_ROLE_NEUTRAL, "", self.current_theme)
        if hasattr(self, "btn_literature_descriptions"):
            apply_theme_button_style(self.btn_literature_descriptions, BUTTON_ROLE_NEUTRAL, "padding: 4px 8px;", self.current_theme)
        if hasattr(self, "btn_start_ant_code"):
            compact_agent_button = "padding: 5px 10px;"
            apply_theme_button_style(self.btn_start_ant_code, BUTTON_ROLE_RUN, compact_agent_button, self.current_theme)
            apply_theme_button_style(self.btn_stop_ant_code, BUTTON_ROLE_STOP, compact_agent_button, self.current_theme)
        if hasattr(self, "btn_add"):
            apply_theme_button_style(self.btn_add, BUTTON_ROLE_NEUTRAL, "", self.current_theme)
        if hasattr(self, "btn_add_part"):
            apply_theme_button_style(self.btn_add_part, BUTTON_ROLE_NEUTRAL, "font-weight: bold;", self.current_theme)
        if hasattr(self, "btn_rename_part"):
            apply_theme_button_style(self.btn_rename_part, BUTTON_ROLE_NEUTRAL, "padding: 4px 8px;", self.current_theme)
        if hasattr(self, "btn_del_part"):
            apply_theme_button_style(self.btn_del_part, BUTTON_ROLE_DESTRUCTIVE, "font-weight: bold;", self.current_theme)
        if hasattr(self, "btn_del_locator"):
            apply_theme_button_style(self.btn_note_locator, BUTTON_ROLE_NEUTRAL, "", self.current_theme)
            apply_theme_button_style(self.btn_del_locator, BUTTON_ROLE_DESTRUCTIVE, "", self.current_theme)
        if hasattr(self, "btn_del_segmenter"):
            apply_theme_button_style(self.btn_note_segmenter, BUTTON_ROLE_NEUTRAL, "", self.current_theme)
            apply_theme_button_style(self.btn_del_segmenter, BUTTON_ROLE_DESTRUCTIVE, "", self.current_theme)
        if hasattr(self, "btn_predict"):
            apply_theme_button_style(self.btn_predict, BUTTON_ROLE_RUN, "padding: 5px;", self.current_theme)
        if hasattr(self, "btn_batch"):
            apply_theme_button_style(self.btn_batch, BUTTON_ROLE_RUN, "padding: 5px;", self.current_theme)
        if hasattr(self, "btn_vlm_preannotate_current"):
            apply_theme_button_style(self.btn_vlm_preannotate_current, BUTTON_ROLE_RUN, "padding: 6px;", self.current_theme)
        if hasattr(self, "btn_vlm_preannotate_batch"):
            apply_theme_button_style(self.btn_vlm_preannotate_batch, BUTTON_ROLE_RUN, "padding: 6px;", self.current_theme)
        if hasattr(self, "btn_accept_current_ai_drafts"):
            apply_theme_button_style(self.btn_accept_current_ai_drafts, BUTTON_ROLE_COMMIT, "padding: 6px;", self.current_theme)
        if hasattr(self, "btn_accept_batch_ai_drafts"):
            apply_theme_button_style(self.btn_accept_batch_ai_drafts, BUTTON_ROLE_COMMIT, "padding: 6px;", self.current_theme)
        if hasattr(self, "btn_train"):
            apply_theme_button_style(self.btn_train, BUTTON_ROLE_RUN, "padding: 8px; margin-top: 5px;", self.current_theme)
        if hasattr(self, "btn_stop_training"):
            apply_theme_button_style(self.btn_stop_training, BUTTON_ROLE_STOP, "padding: 8px; margin-top: 5px;", self.current_theme)
        if hasattr(self, "btn_training_results"):
            apply_theme_button_style(self.btn_training_results, BUTTON_ROLE_NEUTRAL, "padding: 4px 8px;", self.current_theme)
        if hasattr(self, "btn_clear_ai"):
            apply_theme_button_style(self.btn_clear_ai, BUTTON_ROLE_DESTRUCTIVE, "font-weight: bold; margin-top: 5px;", self.current_theme)

        if hasattr(self, "btn_configure_route_expert"):
            apply_theme_button_style(self.btn_configure_route_expert, BUTTON_ROLE_NEUTRAL, "", self.current_theme)
        if hasattr(self, "btn_blink_auto_annotate"):
            apply_theme_button_style(self.btn_blink_auto_annotate, BUTTON_ROLE_RUN, "padding: 6px;", self.current_theme)
        if hasattr(self, "btn_blink_auto_shrink"):
            apply_theme_button_style(self.btn_blink_auto_shrink, BUTTON_ROLE_RUN, "padding: 6px;", self.current_theme)
        if hasattr(self, "btn_blink_batch_auto_shrink"):
            apply_theme_button_style(self.btn_blink_batch_auto_shrink, BUTTON_ROLE_RUN, "padding: 6px;", self.current_theme)
        if hasattr(self, "btn_blink_train_expert"):
            apply_theme_button_style(self.btn_blink_train_expert, BUTTON_ROLE_RUN, "padding: 6px;", self.current_theme)
        if hasattr(self, "btn_blink_stop_training"):
            apply_theme_button_style(self.btn_blink_stop_training, BUTTON_ROLE_STOP, "padding: 6px;", self.current_theme)
    def add_images(self):
        fs, _ = QFileDialog.getOpenFileNames(self, tr("Select Images", self.current_lang), "", "Images (*.png *.jpg *.jpeg *.tif)")
        if fs:
            self._start_image_import(fs)

    def _start_image_import(self, image_paths, crop_records=None, completion_message=None, show_success_message=False):
        paths = [path for path in list(image_paths or []) if path]
        if not paths:
            return False
        if getattr(self, "image_import_thread", None) is not None and self.image_import_thread.isRunning():
            QMessageBox.information(
                self,
                tr("Image Import", self.current_lang),
                tr("Image import is already running.", self.current_lang),
            )
            return False

        crop_records = list(crop_records or [])
        self._flush_pending_project_save(defer_for_navigation=False)
        if len(paths) < BACKGROUND_IMAGE_IMPORT_THRESHOLD:
            added = self.project.add_images(paths)
            self._inherit_crop_provenance(crop_records)
            self.refresh_file_list()
            message = completion_message or tr("Imported {0}/{1} image(s).", self.current_lang).format(added, len(paths))
            self.log(message)
            if show_success_message:
                QMessageBox.information(self, tr("Success", self.current_lang), message)
            return True

        progress = QProgressDialog(
            tr("Preparing image import...", self.current_lang),
            "",
            0,
            len(paths),
            self,
        )
        progress.setWindowTitle(tr("Image Import Progress", self.current_lang))
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setCancelButton(None)
        self._prepare_progress_dialog(progress, width=520)
        progress.show()
        self.image_import_progress_dialog = progress
        self._set_image_import_controls_enabled(False)

        self.image_import_thread = ImageImportThread(self.project, paths)
        thread = self.image_import_thread

        def on_progress(done, total, label):
            total = max(0, int(total))
            done = max(0, int(done))
            if total > 0 and progress.maximum() != total:
                progress.setRange(0, total)
            if total > 0:
                progress.setValue(min(done, total))
            if label:
                message = tr("Importing images: {0}/{1}\n{2}", self.current_lang).format(
                    min(done, total),
                    total,
                    self._short_progress_path(label, limit=72),
                )
            else:
                message = tr("Importing images: {0}/{1}", self.current_lang).format(min(done, total), total)
            progress.setLabelText(message)

        def on_success(added, total):
            progress.setValue(progress.maximum())
            self._inherit_crop_provenance(crop_records)
            self.refresh_file_list()
            message = completion_message or tr("Imported {0}/{1} image(s).", self.current_lang).format(added, total)
            self.log(message)
            if show_success_message:
                QMessageBox.information(self, tr("Success", self.current_lang), message)

        def on_error(message):
            self.log(tr("Image import failed: {0}", self.current_lang).format(message))
            QMessageBox.critical(
                self,
                tr("Image Import", self.current_lang),
                tr("Image import failed: {0}", self.current_lang).format(message),
            )

        def on_finished():
            progress.close()
            if self.image_import_progress_dialog is progress:
                self.image_import_progress_dialog = None
            self._set_image_import_controls_enabled(True)
            thread.deleteLater()
            if self.image_import_thread is thread:
                self.image_import_thread = None

        thread.progress_signal.connect(on_progress)
        thread.success_signal.connect(on_success)
        thread.error_signal.connect(on_error)
        thread.finished_signal.connect(on_finished)
        thread.start()
        return True

    def _set_image_import_controls_enabled(self, enabled):
        for attr in ("btn_add", "btn_crop", "btn_batch_split_panels"):
            widget = getattr(self, attr, None)
            if widget is not None:
                widget.setEnabled(bool(enabled))

    def open_cropper(self):
        img = None
        if self.file_list.currentItem():
            selected_path = self.file_list.currentItem().data(Qt.UserRole)
            if selected_path:
                img = selected_path
            else:
                fn = self.file_list.currentItem().text().strip()
                for p in self.project.project_data["images"]:
                    if os.path.basename(p) == fn:
                        img = p
                        break
        dlg = ImageCropper(initial_image=img, parent=self, lang=self.current_lang)
        if dlg.exec():
            nf = dlg.get_files()
            if nf:
                crop_records = []
                if hasattr(dlg, "get_crop_records"):
                    crop_records = dlg.get_crop_records()
                self._start_image_import(nf, crop_records=crop_records)

    def _is_split_crop_image(self, image_path):
        if not image_path or not hasattr(self.project, "get_image_provenance"):
            return False
        provenance = self.project.get_image_provenance(image_path)
        derived_from = provenance.get("derived_from") if isinstance(provenance, dict) else {}
        if isinstance(derived_from, dict) and bool(derived_from.get("image_path")):
            return True
        return self._looks_like_panel_crop_path(image_path)

    def _is_hard_joined_candidate_crop(self, image_path, provenance=None):
        if not image_path or not hasattr(self.project, "get_image_provenance"):
            return False
        if provenance is None:
            provenance = self.project.get_image_provenance(image_path)
        if not isinstance(provenance, dict):
            return False
        derived_from = provenance.get("derived_from")
        if not isinstance(derived_from, dict):
            return False
        return str(derived_from.get("crop_source") or "").strip() in {
            "hard_seam_panel_split",
            "letter_label_panel_split",
            "label_guided_panel_split",
        }

    def _looks_like_panel_crop_path(self, image_path):
        """Fallback for crops created before provenance was available."""
        if not image_path:
            return False
        base_name = os.path.basename(str(image_path))
        if not re.search(r"__(?:panel|crop)_\d{3}(?:_\d+)?\.(?:png|jpe?g|tif|tiff)$", base_name, re.IGNORECASE):
            return False
        crop_dir = os.path.normcase(os.path.abspath(os.path.dirname(str(image_path))))
        crop_abs = os.path.normcase(os.path.abspath(str(image_path)))
        crop_stem = os.path.splitext(base_name)[0]
        source_stem = re.sub(r"__(?:panel|crop)_\d{3}(?:_\d+)?$", "", crop_stem, flags=re.IGNORECASE)
        return any(
            os.path.normcase(os.path.abspath(path)) != crop_abs
            and os.path.normcase(os.path.abspath(os.path.dirname(path))) == crop_dir
            and os.path.normcase(os.path.splitext(os.path.basename(path))[0]) == os.path.normcase(source_stem)
            for path in self.project.project_data.get("images", [])
        )

    def _has_split_crops_from_image(self, image_path):
        if not image_path or not hasattr(self.project, "get_image_provenance"):
            return False
        source_abs = os.path.normcase(os.path.abspath(str(image_path)))
        source_dir = os.path.normcase(os.path.abspath(os.path.dirname(str(image_path))))
        source_stem = os.path.normcase(os.path.splitext(os.path.basename(str(image_path)))[0])
        for path in self.project.project_data.get("images", []):
            if not path:
                continue
            crop_abs = os.path.normcase(os.path.abspath(str(path)))
            if crop_abs == source_abs:
                continue
            provenance = self.project.get_image_provenance(path)
            derived_from = provenance.get("derived_from") if isinstance(provenance, dict) else {}
            if isinstance(derived_from, dict) and derived_from.get("image_path"):
                derived_abs = os.path.normcase(os.path.abspath(str(derived_from.get("image_path"))))
                if derived_abs == source_abs:
                    return True
            if not self._looks_like_panel_crop_path(path):
                continue
            crop_dir = os.path.normcase(os.path.abspath(os.path.dirname(str(path))))
            crop_stem = os.path.splitext(os.path.basename(str(path)))[0]
            parent_stem = re.sub(r"__(?:panel|crop)_\d{3}(?:_\d+)?$", "", crop_stem, flags=re.IGNORECASE)
            if crop_dir == source_dir and os.path.normcase(parent_stem) == source_stem:
                return True
        return False

    def _needs_manual_panel_split(self, image_path):
        if not image_path or not hasattr(self.project, "get_image_provenance"):
            return False
        if self._is_split_crop_image(image_path):
            return False
        if self._has_split_crops_from_image(image_path):
            return False
        provenance = self.project.get_image_provenance(image_path)
        review = provenance.get("panel_split_review") if isinstance(provenance, dict) else {}
        return isinstance(review, dict) and review.get("status") == "manual_required"

    def _is_manual_panel_split_done(self, image_path):
        if not image_path or not hasattr(self.project, "get_image_provenance"):
            return False
        if self._is_split_crop_image(image_path):
            return False
        provenance = self.project.get_image_provenance(image_path)
        review = provenance.get("panel_split_review") if isinstance(provenance, dict) else {}
        return isinstance(review, dict) and review.get("status") == "manual_done"

    def _set_panel_split_review(self, image_path, status, reason="", detections=None):
        if not image_path or not hasattr(self.project, "get_image_provenance"):
            return
        provenance = self.project.get_image_provenance(image_path)
        provenance["panel_split_review"] = {
            "status": str(status or ""),
            "reason": str(reason or ""),
            "candidate_count": len(detections or []),
        }
        self.project.set_image_provenance(image_path, provenance, save=False)

    def _clear_panel_split_review(self, image_path):
        if not image_path or not hasattr(self.project, "get_image_provenance"):
            return
        provenance = self.project.get_image_provenance(image_path)
        if "panel_split_review" in provenance:
            del provenance["panel_split_review"]
            self.project.set_image_provenance(image_path, provenance, save=False)

    def _builtin_image_group_definitions(self):
        return [
            ("original", tr("Original Images", self.current_lang)),
            ("split", tr("Split Crops", self.current_lang)),
            ("hard_candidates", tr("Hard-joined Candidates", self.current_lang)),
            ("manual_done", tr("Manual Split Done", self.current_lang)),
            ("manual", tr("Manual Split Needed", self.current_lang)),
        ]

    def _custom_image_group_definitions(self):
        groups = self.project.project_data.get("image_groups", {}) if hasattr(self, "project") else {}
        raw_groups = groups.get("custom_groups", []) if isinstance(groups, dict) else []
        clean = []
        seen = set()
        if isinstance(raw_groups, list):
            for group in raw_groups:
                if not isinstance(group, dict):
                    continue
                group_id = str(group.get("id", "") or "").strip()
                name = str(group.get("name", "") or "").strip()
                if not group_id or not name or group_id in seen:
                    continue
                seen.add(group_id)
                clean.append((group_id, name))
        return clean

    def _all_image_group_definitions(self):
        return self._builtin_image_group_definitions() + self._custom_image_group_definitions()

    def _training_scope_group_definitions(self, all_images=None):
        images = [path for path in (all_images if all_images is not None else self.project.project_data.get("images", [])) if path]
        state = getattr(self, "_image_list_state_cache", None)
        if isinstance(state, dict):
            try:
                state_total = int(state.get("total_count", -1))
            except Exception:
                state_total = -1
            group_definitions = list(state.get("group_definitions", []) or [])
            if state_total == len(images) and group_definitions:
                return group_definitions

        image_groups = self._project_image_groups(images=images)
        group_definitions = []
        for group_key, label in self._builtin_image_group_definitions():
            group_definitions.append((group_key, label, image_groups.get(group_key, []), group_key == "split"))
        for group_key, label in self._custom_image_group_definitions():
            group_definitions.append((group_key, label, image_groups.get(group_key, []), False))
        return group_definitions

    def _populate_training_scope_combo(self, selected_scope=None):
        if not hasattr(self, "combo_training_scope"):
            return
        current = str(selected_scope or self.combo_training_scope.currentData() or "__all__")
        all_images = [path for path in self.project.project_data.get("images", []) if path]
        group_definitions = self._training_scope_group_definitions(all_images)
        self.combo_training_scope.blockSignals(True)
        self.combo_training_scope.clear()
        self.combo_training_scope.addItem(
            tr("All Images ({0})", self.current_lang).format(len(all_images)),
            "__all__",
        )
        for group_id, label, group_images, _is_split_group in group_definitions:
            group_images = list(group_images or [])
            if group_images:
                self.combo_training_scope.addItem(
                    tr("{0} ({1})", self.current_lang).format(label, len(group_images)),
                    group_id,
                )
        index = self.combo_training_scope.findData(current)
        if index < 0:
            index = self.combo_training_scope.findData("__all__")
        self.combo_training_scope.setCurrentIndex(index if index >= 0 else 0)
        self.combo_training_scope.blockSignals(False)

    def _refresh_training_scope_combo(self):
        selected = "__all__"
        if hasattr(self, "combo_training_scope"):
            selected = str(self.combo_training_scope.currentData() or selected)
        self._populate_training_scope_combo(selected)

    def _selected_training_scope_payload(self):
        all_images = [path for path in self.project.project_data.get("images", []) if path]
        scope_id = "__all__"
        if hasattr(self, "combo_training_scope"):
            scope_id = str(self.combo_training_scope.currentData() or "__all__")
        if scope_id == "__all__":
            label = tr("All Images", self.current_lang)
            return {"scope_id": "__all__", "label": label, "images": all_images}

        group_images = []
        for group_id, _label, images, _is_split_group in self._training_scope_group_definitions(all_images):
            if str(group_id) == scope_id:
                group_images = list(images or [])
                break
        label = self._image_group_display_name(scope_id) or scope_id
        return {"scope_id": scope_id, "label": label, "images": group_images}

    def _populate_vlm_image_group_combo(self, selected_group=None):
        if not hasattr(self, "combo_vlm_image_group"):
            return
        current = str(selected_group or self.combo_vlm_image_group.currentData() or "split")
        self.combo_vlm_image_group.blockSignals(True)
        self.combo_vlm_image_group.clear()
        for group_id, label in self._all_image_group_definitions():
            self.combo_vlm_image_group.addItem(label, group_id)
        index = self.combo_vlm_image_group.findData(current)
        if index < 0:
            index = self.combo_vlm_image_group.findData("split")
        self.combo_vlm_image_group.setCurrentIndex(index if index >= 0 else 0)
        self.combo_vlm_image_group.blockSignals(False)

    def _refresh_vlm_image_group_combo(self):
        selected = "split"
        if hasattr(self, "combo_vlm_image_group"):
            selected = str(self.combo_vlm_image_group.currentData() or selected)
        self._populate_vlm_image_group_combo(selected)

    def _image_group_display_name(self, group_key):
        key = str(group_key or "").strip()
        for group_id, label in self._all_image_group_definitions():
            if group_id == key:
                return label
        return key

    def _custom_image_group_ids(self):
        return {group_id for group_id, _label in self._custom_image_group_definitions()}

    def _image_group_move_target_definitions(self):
        definitions = list(self._builtin_image_group_definitions())
        custom_groups = self._custom_image_group_definitions()
        if custom_groups:
            image_groups = self._project_image_groups()
            for group_id, label in custom_groups:
                if image_groups.get(group_id):
                    definitions.append((group_id, label))
        return definitions

    def _remove_empty_custom_image_groups(self):
        if not hasattr(self, "project"):
            return set()
        groups_config = self.project.project_data.get("image_groups", {})
        if not isinstance(groups_config, dict):
            return set()
        custom_groups = list(groups_config.get("custom_groups", []) or [])
        if not custom_groups:
            return set()

        image_groups = self._project_image_groups()
        kept_groups = []
        removed_ids = set()
        seen = set()
        for group in custom_groups:
            if not isinstance(group, dict):
                continue
            group_id = str(group.get("id", "") or "").strip()
            name = str(group.get("name", "") or "").strip()
            if not group_id or not name or group_id in seen:
                continue
            seen.add(group_id)
            if image_groups.get(group_id):
                kept_groups.append(group)
            else:
                removed_ids.add(group_id)

        if not removed_ids:
            return set()

        groups_config["custom_groups"] = kept_groups
        self.project.project_data["image_groups"] = groups_config
        if hasattr(self.project, "mark_sqlite_project_dirty"):
            self.project.mark_sqlite_project_dirty()

        settings = self.project.project_data.get("vlm_preannotation")
        if isinstance(settings, dict) and str(settings.get("image_group", "") or "").strip() in removed_ids:
            settings["image_group"] = DEFAULT_VLM_IMAGE_GROUP

        collapsed = getattr(self, "image_list_group_collapsed", None)
        if isinstance(collapsed, dict):
            for group_id in removed_ids:
                collapsed.pop(group_id, None)

        return removed_ids

    def _safe_custom_image_group_id(self, name):
        text = str(name or "").strip()
        clean = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in text).strip("_")
        clean = clean or "custom_group"
        if clean in {"original", "split", "hard_candidates", "manual_done", "manual"}:
            clean = f"custom_{clean}"
        existing = {group_id for group_id, _label in self._all_image_group_definitions()}
        group_id = clean
        suffix = 2
        while group_id in existing:
            group_id = f"{clean}_{suffix}"
            suffix += 1
        return group_id

    def create_custom_image_group(self):
        removed_empty = self._remove_empty_custom_image_groups()
        if removed_empty:
            self._schedule_project_save()
            self.refresh_file_list()
            self._refresh_vlm_image_group_combo()
        name, ok = QInputDialog.getText(
            self,
            tr("New Image Group", self.current_lang),
            tr("Group Name:", self.current_lang),
        )
        name = str(name or "").strip()
        if not ok or not name:
            return ""
        existing_names = {
            str(label).strip().lower()
            for _group_id, label in self._all_image_group_definitions()
            if str(label).strip()
        }
        if name.lower() in existing_names:
            QMessageBox.information(self, tr("New Image Group", self.current_lang), tr("Image group already exists.", self.current_lang))
            return ""
        groups = dict(self.project.project_data.get("image_groups", {}) or {})
        custom_groups = list(groups.get("custom_groups", []) or [])
        group_id = self._safe_custom_image_group_id(name)
        custom_groups.append({"id": group_id, "name": name[:80]})
        groups["custom_groups"] = custom_groups
        self.project.project_data["image_groups"] = groups
        if hasattr(self.project, "mark_sqlite_project_dirty"):
            self.project.mark_sqlite_project_dirty()
        self._schedule_project_save()
        self.refresh_file_list()
        self._refresh_vlm_image_group_combo()
        return group_id

    def _set_image_manual_group(self, image_path, group_key):
        if not image_path or not hasattr(self.project, "get_image_provenance"):
            return
        key = str(group_key or "").strip()
        provenance = self.project.get_image_provenance(image_path)
        if key:
            provenance["manual_image_group"] = key
        else:
            provenance.pop("manual_image_group", None)
        self.project.set_image_provenance(image_path, provenance, save=False)

    def move_images_to_group(self, image_paths, group_key):
        paths = [path for path in (image_paths or []) if path]
        key = str(group_key or "").strip()
        if not paths or not key:
            return
        allowed = {group_id for group_id, _label in self._all_image_group_definitions()}
        if key not in allowed:
            return
        for path in paths:
            self._set_image_manual_group(path, key)
        self._remove_empty_custom_image_groups()
        self._schedule_project_save()
        self.refresh_file_list()
        self._refresh_vlm_image_group_combo()
        self.log(tr("Moved {0} image(s) to {1}.", self.current_lang).format(len(paths), self._image_group_display_name(key)))

    def clear_selected_custom_image_group(self):
        paths = self._selected_image_paths()
        if not paths:
            return
        for path in paths:
            self._set_image_manual_group(path, "")
        self._remove_empty_custom_image_groups()
        self._schedule_project_save()
        self.refresh_file_list()
        self._refresh_vlm_image_group_combo()

    def _short_progress_path(self, path, limit=64):
        name = os.path.basename(str(path or ""))
        if len(name) <= limit:
            return name
        root, ext = os.path.splitext(name)
        ext = ext[:10]
        keep = max(12, limit - len(ext) - 3)
        head = max(6, keep // 2)
        tail = max(6, keep - head)
        return f"{root[:head]}...{root[-tail:]}{ext}"

    def _prepare_progress_dialog(self, progress, width=460):
        if progress is None:
            return
        progress.setMinimumWidth(int(width))
        progress.setMaximumWidth(int(width))
        progress.adjustSize()
        try:
            center = self.frameGeometry().center()
            rect = progress.frameGeometry()
            rect.moveCenter(center)
            progress.move(rect.topLeft())
        except Exception:
            pass

    def _candidate_panel_split_sources(self):
        return [
            path
            for path in self.project.project_data.get("images", [])
            if path and not self._is_split_crop_image(path)
        ]

    def batch_split_panel_images(self):
        source_images = self._candidate_panel_split_sources()
        if not source_images:
            QMessageBox.information(self, tr("Empty", self.current_lang), tr("No panel crops were detected.", self.current_lang))
            return
        reply = themed_yes_no_question(
            self,
            tr("Batch Split Plates", self.current_lang),
            tr(
                "Run automatic panel splitting on {0} original image(s)?\n\nDetected crops will be added after the original images. Please review the generated crops before training.",
                self.current_lang,
            ).format(len(source_images)),
            confirm_role=BUTTON_ROLE_COMMIT,
        )
        if reply != QMessageBox.Yes:
            return

        crop_records = []
        skipped = 0
        manual_required = 0
        cancelled = False
        progress = QProgressDialog(
            tr("Batch Split Plates", self.current_lang),
            tr("Cancel", self.current_lang),
            0,
            len(source_images),
            self,
        )
        progress.setWindowTitle(tr("Batch Split Plates", self.current_lang))
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setValue(0)
        self._prepare_progress_dialog(progress)
        app = QApplication.instance()
        if app is not None:
            app.processEvents()

        for index, source_image in enumerate(source_images, start=1):
            progress.setLabelText(
                f"{tr('Batch Split Plates', self.current_lang)}: {index}/{len(source_images)}\n{self._short_progress_path(source_image)}"
            )
            progress.setValue(index - 1)
            if app is not None:
                app.processEvents()
            if progress.wasCanceled():
                cancelled = True
                break
            try:
                detections = detect_panel_crops(source_image)
            except Exception as exc:
                skipped += 1
                self._set_panel_split_review(source_image, "skipped", reason=f"error: {exc}")
                self.log(f"Panel split skipped {os.path.basename(source_image)}: {exc}")
                continue
            hard_joined_detections = [
                detection
                for detection in detections
                if str(detection.get("source") or "") in {"hard_seam_panel_split", "letter_label_panel_split", "label_guided_panel_split"}
            ]
            if hard_joined_detections and not any(
                str(detection.get("source") or "") in {"white_separator_panel_split", "mixed_separator_panel_split"}
                for detection in detections
            ):
                manual_required += 1
                self._set_panel_split_review(
                    source_image,
                    "candidate_split",
                    reason="hard_seam_panel_split_candidate",
                    detections=hard_joined_detections,
                )
                crop_records.extend(self._save_detected_panel_crops(source_image, hard_joined_detections))
                progress.setValue(index)
                if app is not None:
                    app.processEvents()
                continue
            detections = [
                detection
                for detection in detections
                if str(detection.get("source") or "") in {"white_separator_panel_split", "mixed_separator_panel_split"}
            ]
            if not detections:
                skipped += 1
                self._set_panel_split_review(source_image, "skipped", reason="no_split_detected")
                continue
            crop_records.extend(self._save_detected_panel_crops(source_image, detections))
            self._set_panel_split_review(source_image, "auto_split", reason="white_separator_panel_split", detections=detections)
            progress.setValue(index)
            if app is not None:
                app.processEvents()

        progress.setValue(len(source_images))

        if not crop_records:
            if hasattr(self.project, "save_project"):
                self.project.save_project()
            if cancelled:
                self.refresh_file_list()
                message = tr("Panel splitting cancelled.", self.current_lang)
                QMessageBox.information(self, tr("Batch Split Plates", self.current_lang), message)
                return
            if manual_required:
                self.refresh_file_list()
                message = tr(
                    "Panel splitting finished: {0} crop(s) from {1} image(s); hard-joined candidate plates needing review: {2}; no split detected/errors: {3}.",
                    self.current_lang,
                ).format(0, 0, manual_required, skipped)
                QMessageBox.information(self, tr("Batch Split Plates", self.current_lang), message)
                return
            QMessageBox.information(self, tr("Empty", self.current_lang), tr("No panel crops were detected.", self.current_lang))
            return

        message = tr(
            "Panel splitting finished: {0} crop(s) from {1} image(s); hard-joined candidate plates needing review: {2}; no split detected/errors: {3}.",
            self.current_lang,
        ).format(
            len(crop_records),
            len({record.get("source_image") for record in crop_records}),
            manual_required,
            skipped,
        )
        if cancelled:
            message = f"{message}\n{tr('Panel splitting cancelled.', self.current_lang)}"
        progress.close()
        self._start_image_import(
            [record["path"] for record in crop_records],
            crop_records=crop_records,
            completion_message=message,
            show_success_message=True,
        )

    def _save_detected_panel_crops(self, source_image, detections):
        records = []
        save_dir = os.path.dirname(source_image)
        base_name = os.path.splitext(os.path.basename(source_image))[0]
        with PILImage.open(source_image) as img:
            for index, detection in enumerate(detections, start=1):
                box = [int(value) for value in detection.get("box", [])]
                if len(box) != 4 or box[2] <= box[0] or box[3] <= box[1]:
                    continue
                new_path = self._next_panel_crop_path(save_dir, base_name, index)
                img.crop(tuple(box)).save(new_path, quality=95)
                records.append(
                    {
                        "path": os.path.abspath(new_path),
                        "source_image": os.path.abspath(source_image),
                        "crop_index": index,
                        "crop_box": list(box),
                        "source_size": [int(img.width), int(img.height)],
                        "crop_source": str(detection.get("source") or "auto_panel_split"),
                    }
                )
        return records

    def _next_panel_crop_path(self, save_dir, base_name, index):
        candidate = os.path.join(save_dir, f"{base_name}__panel_{index:03d}.jpg")
        if not os.path.exists(candidate):
            return candidate
        suffix = 2
        while True:
            candidate = os.path.join(save_dir, f"{base_name}__panel_{index:03d}_{suffix}.jpg")
            if not os.path.exists(candidate):
                return candidate
            suffix += 1

    def _inherit_crop_provenance(self, crop_records):
        if not crop_records or not hasattr(self.project, "get_image_provenance"):
            return
        changed = False
        for record in crop_records:
            if not isinstance(record, dict):
                continue
            crop_path = record.get("path")
            source_image = record.get("source_image")
            if not crop_path or not source_image:
                continue
            parent_provenance = self.project.get_image_provenance(source_image)
            crop_provenance = dict(parent_provenance)
            parent_review = parent_provenance.get("panel_split_review") if isinstance(parent_provenance, dict) else {}
            parent_was_manual_required = isinstance(parent_review, dict) and parent_review.get("status") == "manual_required"
            crop_provenance.pop("panel_split_review", None)
            parent_source_type = str(parent_provenance.get("source_type", "") or "image").strip() or "image"
            crop_source = str(record.get("crop_source") or "manual")
            crop_provenance["source_type"] = "pdf_candidate_crop" if self._is_pdf_candidate_provenance(parent_provenance) else f"{parent_source_type}_crop"
            crop_provenance["derived_from"] = {
                "image_path": os.path.abspath(source_image),
                "crop_index": int(record.get("crop_index", 0) or 0),
                "crop_box": list(record.get("crop_box", []) or []),
                "source_size": list(record.get("source_size", []) or []),
                "crop_source": crop_source,
            }
            self.project.set_image_provenance(crop_path, crop_provenance, save=False)
            if crop_source == "manual" or parent_was_manual_required:
                self._set_panel_split_review(source_image, "manual_done", reason="manual_crop_saved")
            changed = True
        if changed:
            self.project.save_project()

    def _selected_image_paths(self):
        if not hasattr(self, "file_list"):
            return []
        paths = []
        for item in self.file_list.selectedItems():
            path = item.data(Qt.UserRole)
            if path:
                paths.append(path)
        return paths

    def _set_selected_panel_split_status(self, status, reason):
        paths = self._selected_image_paths()
        if not paths:
            return
        for path in paths:
            self._set_panel_split_review(path, status, reason=reason)
        self._schedule_project_save()
        self.refresh_file_list()

    def mark_selected_manual_split_done(self):
        self._set_selected_panel_split_status("manual_done", "user_marked_done")

    def mark_selected_manual_split_needed(self):
        self._set_selected_panel_split_status("manual_required", "user_marked_manual_required")

    def clear_selected_split_status(self):
        paths = self._selected_image_paths()
        if not paths:
            return
        for path in paths:
            self._clear_panel_split_review(path)
        self._schedule_project_save()
        self.refresh_file_list()

    def show_file_list_context_menu(self, pos):
        its = self.file_list.selectedItems()
        if not its:
            return
        its = [item for item in its if item.data(Qt.UserRole)]
        if not its:
            return
        m = QMenu(self)
        if len(its) == 1:
            m.addAction(tr("Crop this Image", self.current_lang), self.open_cropper)
        m.addSeparator()
        m.addAction(tr("Mark Manual Split Done", self.current_lang), self.mark_selected_manual_split_done)
        m.addAction(tr("Mark Needs Manual Split", self.current_lang), self.mark_selected_manual_split_needed)
        m.addAction(tr("Clear Split Status", self.current_lang), self.clear_selected_split_status)
        m.addSeparator()
        m.addAction(tr("New Image Group", self.current_lang), self._move_selected_images_to_new_group)
        move_menu = m.addMenu(tr("Move to Image Group", self.current_lang))
        for group_id, label in self._image_group_move_target_definitions():
            move_menu.addAction(label, lambda checked=False, gid=group_id: self.move_images_to_group(self._selected_image_paths(), gid))
        m.addAction(tr("Clear Custom Image Group", self.current_lang), self.clear_selected_custom_image_group)
        m.addSeparator()
        m.addAction(tr("Remove Image", self.current_lang), self.remove_selected_images)
        m.exec(self.file_list.mapToGlobal(pos))

    def _move_selected_images_to_new_group(self):
        paths = self._selected_image_paths()
        if not paths:
            return
        group_id = self.create_custom_image_group()
        if group_id:
            self.move_images_to_group(paths, group_id)

    def remove_selected_images(self):
        paths = self._selected_image_paths()
        if not paths:
            return
        if themed_yes_no_question(
            self,
            tr("Remove", self.current_lang),
            tr("Remove {0} images?", self.current_lang).format(len(paths)),
            confirm_role=BUTTON_ROLE_DESTRUCTIVE,
        ) == QMessageBox.Yes:
            was_current_removed = bool(
                self.current_image
                and any(self._same_project_image_path(path, self.current_image) for path in paths)
            )
            previous_current_image = self.current_image
            previous_visible_paths = self._visible_image_list_paths()
            replacement_image = None
            if was_current_removed:
                replacement_image = self._replacement_image_after_removal(
                    previous_visible_paths,
                    paths,
                    previous_current_image,
                )
            remove_many = getattr(self.project, "remove_images", None)
            if callable(remove_many):
                remove_many(paths, save=False)
            else:
                for path in paths:
                    self.project.remove_image(path, save=False)
            runtime_log_event(
                "remove_images",
                count=len(paths),
                removed_current=was_current_removed,
                previous_current=os.path.basename(str(previous_current_image or "")),
                replacement=os.path.basename(str(replacement_image or "")),
                project=getattr(self.project, "current_project_path", ""),
                remaining_images=len(self.project.project_data.get("images", []) or []),
            )
            self._schedule_project_save(
                reason="remove_images",
                changed_count=len(paths),
                removed_current=was_current_removed,
            )
            current_still_registered = bool(
                self.current_image
                and any(
                    self._same_project_image_path(path, self.current_image)
                    for path in self.project.project_data.get("images", [])
                )
            )
            if not current_still_registered:
                self.current_image = None
                self.canvas.load_image("")
            if not self._remove_visible_image_list_items(paths):
                self._image_list_state_cache = None
                self.refresh_file_list(restore_selection=bool(self.current_image))
                if was_current_removed and replacement_image:
                    self._select_first_visible_image_after_removal(replacement_image)
            elif was_current_removed:
                self._select_first_visible_image_after_removal(replacement_image)

    def refresh_file_list(self, restore_selection=True, reuse_group_cache=False):
        # 1. Remember the currently selected image path
        current_selection_path = self.current_image

        self.file_list.blockSignals(True) # Prevent signal spam during rebuild
        self.file_list.setUpdatesEnabled(False)
        try:
            self.file_list.clear()
            state = self._image_list_state_cache if reuse_group_cache else None
            if not isinstance(state, dict):
                state = self._build_image_list_state()
                self._image_list_state_cache = state

            total_count = int(state.get("total_count", 0) or 0)
            labeled_count = int(state.get("labeled_count", 0) or 0)
            group_definitions = list(state.get("group_definitions", []) or [])
            labeled_images = set(state.get("labeled_images", set()) or set())
            split_images = set(state.get("split_images", set()) or set())
            non_empty_groups = [group for group in group_definitions if group[2]]
            has_collapsed_group = any(
                bool(self.image_list_group_collapsed.get(group[0], False))
                for group in non_empty_groups
            )
            use_group_headers = (
                total_count >= LARGE_PROJECT_OPEN_LIGHTWEIGHT_THRESHOLD
                or has_collapsed_group
                or not (len(non_empty_groups) == 1 and non_empty_groups[0][0] == "original")
            )

            item_to_select = None
            first_image_item = None
            theme_colors = get_theme_config(self.current_theme)

            def add_group_header(group_key, text, count):
                collapsed = bool(self.image_list_group_collapsed.get(group_key, False))
                arrow = "▸" if collapsed else "▾"
                item = QListWidgetItem(f"{arrow} {text} ({count})")
                item.setData(Qt.UserRole, None)
                item.setData(Qt.UserRole + 1, group_key)
                item.setFlags((item.flags() | Qt.ItemIsEnabled | Qt.ItemIsSelectable) & ~Qt.ItemIsEditable)
                item.setForeground(QColor(theme_colors["text_dim"]))
                self.file_list.addItem(item)
                return collapsed

            def add_image_item(img, is_split_crop=False, group_key=""):
                nonlocal item_to_select, first_image_item
                base_name = os.path.basename(img)
                display_name = f"  {base_name}" if is_split_crop else base_name
                item = QListWidgetItem(display_name)
                item.setData(Qt.UserRole, img) # Store full path for safer lookup
                item.setData(Qt.UserRole + 2, group_key)
                if is_split_crop:
                    item.setToolTip(tr("Split Crops", self.current_lang))

                if img in labeled_images:
                    item.setForeground(QColor(theme_colors["success"]))
                elif is_split_crop:
                    item.setForeground(QColor(theme_colors["text_dim"]))
                else:
                    item.setForeground(QColor(theme_colors["text_soft"]))

                self.file_list.addItem(item)
                if first_image_item is None:
                    first_image_item = item

                # Check if this is the one we were looking at
                if current_selection_path and self._same_project_image_path(img, current_selection_path):
                    item_to_select = item

            for group_key, label, images, is_split_group in group_definitions:
                if not images:
                    continue
                if use_group_headers:
                    collapsed = add_group_header(group_key, label, len(images))
                    if collapsed:
                        continue
                for img in images:
                    add_image_item(img, is_split_crop=(is_split_group or img in split_images), group_key=group_key)

            # 2. Restore Selection
            if restore_selection:
                target_item = item_to_select or first_image_item
                if target_item:
                    self.file_list.setCurrentItem(target_item)
                    self.file_list.scrollToItem(target_item) # Ensure visible
                    if target_item.data(Qt.UserRole):
                        self.on_file_selected(target_item, None)

            # Update the header label on the left side
            header_base = tr("PROJECT IMAGES", self.current_lang)
            self.label_project_images.setText(f"{header_base} ({labeled_count}/{total_count})")
            self._refresh_training_scope_combo()
        finally:
            self.file_list.setUpdatesEnabled(True)
            self.file_list.blockSignals(False)

    def _image_has_review_content(self, image_path):
        if not image_path:
            return False
        return bool(self.project.get_labels(image_path) or self.project.get_auto_boxes(image_path))

    def _set_image_list_item_status(self, item, image_path, labeled_images=None, split_images=None):
        if item is None or not image_path:
            return
        group_key = str(item.data(Qt.UserRole + 2) or "")
        if labeled_images is None:
            is_labeled = self._image_has_review_content(image_path)
        else:
            is_labeled = image_path in set(labeled_images or [])
        if split_images is None:
            is_split_crop = group_key == "split" or self._is_split_crop_image(image_path)
        else:
            is_split_crop = group_key == "split" or image_path in set(split_images or [])
        theme_colors = get_theme_config(self.current_theme)
        if is_labeled:
            item.setForeground(QColor(theme_colors["success"]))
        elif is_split_crop:
            item.setForeground(QColor(theme_colors["text_dim"]))
        else:
            item.setForeground(QColor(theme_colors["text_soft"]))

    def _refresh_current_image_list_status(self, image_path=None):
        image_path = image_path or self.current_image
        if not image_path or not hasattr(self, "file_list"):
            return False

        state = self._image_list_state_cache
        if not isinstance(state, dict):
            state = self._build_image_list_state()
            self._image_list_state_cache = state

        labeled_images = set(state.get("labeled_images", set()) or set())
        before_labeled = image_path in labeled_images
        after_labeled = self._image_has_review_content(image_path)
        if after_labeled:
            labeled_images.add(image_path)
        else:
            labeled_images.discard(image_path)

        state["labeled_images"] = labeled_images
        if before_labeled != after_labeled:
            state["labeled_count"] = max(0, int(state.get("labeled_count", 0) or 0) + (1 if after_labeled else -1))

        target_item = None
        for index in range(self.file_list.count()):
            item = self.file_list.item(index)
            if item is not None and self._same_project_image_path(item.data(Qt.UserRole), image_path):
                target_item = item
                break
        if target_item is not None:
            self._set_image_list_item_status(
                target_item,
                image_path,
                labeled_images=labeled_images,
                split_images=set(state.get("split_images", set()) or set()),
            )

        header_base = tr("PROJECT IMAGES", self.current_lang)
        self.label_project_images.setText(
            f"{header_base} ({int(state.get('labeled_count', 0) or 0)}/{int(state.get('total_count', 0) or 0)})"
        )
        return target_item is not None

    def _refresh_image_list_status_or_rebuild(self, image_path=None):
        if self._refresh_current_image_list_status(image_path):
            return True
        self._image_list_state_cache = None
        self.refresh_file_list(restore_selection=bool(self.current_image))
        return False

    def _image_list_path_identity(self, path):
        if not path:
            return ""
        try:
            return os.path.normcase(os.path.normpath(os.path.abspath(str(path))))
        except Exception:
            return str(path)

    def _visible_image_list_paths(self):
        if not hasattr(self, "file_list"):
            return []
        paths = []
        for row in range(self.file_list.count()):
            item = self.file_list.item(row)
            path = item.data(Qt.UserRole) if item is not None else None
            if path:
                paths.append(path)
        return paths

    def _replacement_image_after_removal(self, previous_visible_paths, removed_paths, previous_current_image):
        visible_paths = [path for path in list(previous_visible_paths or []) if path]
        if not visible_paths:
            return None

        removed_identities = {
            self._image_list_path_identity(path)
            for path in list(removed_paths or [])
            if path
        }
        removed_identities.discard("")

        current_index = -1
        for index, path in enumerate(visible_paths):
            if self._same_project_image_path(path, previous_current_image):
                current_index = index
                break

        if current_index < 0:
            search_order = visible_paths
        else:
            search_order = visible_paths[current_index + 1:] + list(reversed(visible_paths[:current_index]))

        for path in search_order:
            if self._image_list_path_identity(path) not in removed_identities:
                return path
        return None

    def _remove_visible_image_list_items(self, image_paths):
        if not image_paths or not hasattr(self, "file_list"):
            return False
        state = self._image_list_state_cache
        if not isinstance(state, dict):
            return False

        remove_identities = set()
        for path in image_paths:
            identity = self._image_list_path_identity(path)
            if identity:
                remove_identities.add(identity)
        if not remove_identities:
            return False

        removed_visible_rows = 0
        self.file_list.blockSignals(True)
        self.file_list.setUpdatesEnabled(False)
        try:
            for row in range(self.file_list.count() - 1, -1, -1):
                item = self.file_list.item(row)
                path = item.data(Qt.UserRole) if item is not None else None
                if not path:
                    continue
                identity = self._image_list_path_identity(path)
                if identity in remove_identities:
                    removed_visible_rows += 1
                    self.file_list.takeItem(row)
        finally:
            self.file_list.setUpdatesEnabled(True)
            self.file_list.blockSignals(False)

        labeled_images = set(state.get("labeled_images", set()) or set())
        removed_labeled = 0
        filtered_labeled = set()
        for path in labeled_images:
            identity = self._image_list_path_identity(path)
            if identity in remove_identities:
                removed_labeled += 1
            else:
                filtered_labeled.add(path)
        state["labeled_images"] = filtered_labeled
        state["split_images"] = {
            path
            for path in set(state.get("split_images", set()) or set())
            if self._image_list_path_identity(path) not in remove_identities
        }
        state["total_count"] = max(0, int(state.get("total_count", 0) or 0) - len(remove_identities))
        state["labeled_count"] = max(0, int(state.get("labeled_count", 0) or 0) - removed_labeled)
        state["group_definitions"] = self._filtered_group_definitions_after_removal(
            state.get("group_definitions", []),
            remove_identities,
        )
        self._refresh_visible_image_group_header_counts(state.get("group_definitions", []))

        header_base = tr("PROJECT IMAGES", self.current_lang)
        self.label_project_images.setText(
            f"{header_base} ({int(state.get('labeled_count', 0) or 0)}/{int(state.get('total_count', 0) or 0)})"
        )
        self._refresh_training_scope_combo()
        return removed_visible_rows > 0

    def _filtered_group_definitions_after_removal(self, group_definitions, remove_identities):
        filtered = []
        for group_key, label, images, is_split_group in list(group_definitions or []):
            kept_images = []
            for path in list(images or []):
                identity = self._image_list_path_identity(path)
                if identity not in remove_identities:
                    kept_images.append(path)
            filtered.append((group_key, label, kept_images, is_split_group))
        return filtered

    def _refresh_visible_image_group_header_counts(self, group_definitions):
        counts = {
            str(group_key): len(list(images or []))
            for group_key, _label, images, _is_split_group in list(group_definitions or [])
        }
        for row in range(self.file_list.count()):
            item = self.file_list.item(row)
            group_key = item.data(Qt.UserRole + 1) if item is not None else None
            if not group_key:
                continue
            key = str(group_key)
            collapsed = bool(self.image_list_group_collapsed.get(key, False))
            arrow = "▸" if collapsed else "▾"
            item.setText(f"{arrow} {self._image_group_display_name(key)} ({counts.get(key, 0)})")

    def _select_first_visible_image_after_removal(self, preferred_path=None):
        if not hasattr(self, "file_list"):
            return False
        if preferred_path:
            for row in range(self.file_list.count()):
                item = self.file_list.item(row)
                if item is not None and self._same_project_image_path(item.data(Qt.UserRole), preferred_path):
                    previous = bool(getattr(self, "_suppress_selection_save_flush", False))
                    self._suppress_selection_save_flush = True
                    try:
                        self.file_list.setCurrentItem(item)
                        self.file_list.scrollToItem(item)
                        if not self.current_image or not self._same_project_image_path(self.current_image, item.data(Qt.UserRole)):
                            self.on_file_selected(item, None)
                    finally:
                        self._suppress_selection_save_flush = previous
                    return True
        for row in range(self.file_list.count()):
            item = self.file_list.item(row)
            if item is not None and item.data(Qt.UserRole):
                previous = bool(getattr(self, "_suppress_selection_save_flush", False))
                self._suppress_selection_save_flush = True
                try:
                    self.file_list.setCurrentItem(item)
                    self.file_list.scrollToItem(item)
                    if not self.current_image or not self._same_project_image_path(self.current_image, item.data(Qt.UserRole)):
                        self.on_file_selected(item, None)
                finally:
                    self._suppress_selection_save_flush = previous
                return True
        return False

    def _build_image_list_state(self):
        images = [img for img in self.project.project_data.get("images", []) if img]
        total_count = len(images)
        labeled_images = {
            img
            for img in images
            if bool(self.project.get_labels(img) or self.project.get_auto_boxes(img))
        }
        image_groups = self._project_image_groups(
            images=images,
            labeled_images=labeled_images,
        )

        group_definitions = []
        for group_key, label in self._builtin_image_group_definitions():
            group_definitions.append((group_key, label, image_groups.get(group_key, []), group_key == "split"))
        for group_key, label in self._custom_image_group_definitions():
            group_definitions.append((group_key, label, image_groups.get(group_key, []), False))

        return {
            "total_count": total_count,
            "labeled_count": len(labeled_images),
            "labeled_images": labeled_images,
            "split_images": set(image_groups.get("split", []) or []),
            "group_definitions": group_definitions,
        }

    def _handle_image_list_item_clicked(self, item):
        if item is None:
            return
        group_key = item.data(Qt.UserRole + 1)
        if not group_key:
            return
        key = str(group_key)
        self.image_list_group_collapsed[key] = not bool(self.image_list_group_collapsed.get(key, False))
        self.file_list.blockSignals(True)
        self.file_list.setCurrentItem(None)
        self.file_list.blockSignals(False)
        self.refresh_file_list(restore_selection=False, reuse_group_cache=True)

    def eventFilter(self, watched, event):
        if (
            event is not None
            and event.type() == QEvent.Close
            and watched is getattr(self, "vlm_preannotation_progress_dialog", None)
            and getattr(self, "vlm_preannotation_run_active", False)
        ):
            if hasattr(event, "spontaneous") and not event.spontaneous():
                event.ignore()
                return True
            if self.request_stop_vlm_preannotation(confirm=True):
                event.ignore()
                return True
            event.ignore()
            return True
        if (
            event is not None
            and event.type() == QEvent.KeyPress
            and event.key() in (Qt.Key_Up, Qt.Key_Down)
            and event.modifiers() == Qt.NoModifier
            and self._should_use_image_list_arrow_navigation(watched)
        ):
            self._select_adjacent_image(1 if event.key() == Qt.Key_Down else -1)
            event.accept()
            return True
        return super().eventFilter(watched, event)

    def _should_use_image_list_arrow_navigation(self, watched):
        if not hasattr(self, "tabs") or not hasattr(self, "workbench_widget") or not hasattr(self, "file_list"):
            return False
        if self.tabs.currentWidget() is not self.workbench_widget:
            return False
        if getattr(self, "active_project_kind", "image") != "image":
            return False
        if getattr(self.file_list, "count", lambda: 0)() <= 0:
            return False

        focus = QApplication.focusWidget()
        widget = watched if isinstance(watched, QWidget) else focus
        if widget is None:
            return False

        blocked_types = (
            QLineEdit,
            QTextEdit,
            QComboBox,
            QSpinBox,
            QSlider,
            QTreeWidget,
            QTableWidget,
        )
        if isinstance(widget, blocked_types):
            return False

        parent = widget
        while parent is not None:
            if parent in (self.file_list, self.canvas, self.canvas_shell, self.workbench_widget):
                return True
            if isinstance(parent, (QLineEdit, QTextEdit, QComboBox, QSpinBox, QSlider, QTreeWidget, QTableWidget)):
                return False
            parent = parent.parentWidget()
        return False

    def _select_adjacent_image(self, direction):
        if not hasattr(self, "file_list"):
            return False
        direction = 1 if int(direction or 0) >= 0 else -1
        count = self.file_list.count()
        if count <= 0:
            return False

        current_row = self.file_list.currentRow()
        if current_row < 0:
            current_row = -1 if direction > 0 else count

        row = current_row + direction
        while 0 <= row < count:
            item = self.file_list.item(row)
            if item is not None and item.data(Qt.UserRole):
                self.file_list.setCurrentItem(item)
                self.file_list.scrollToItem(item, QAbstractItemView.PositionAtCenter)
                return True
            row += direction
        return False

    def _collect_blink_roi_candidates(self, image_path, selected_part=None, preferred_roi_parts=None):
        manual_boxes = self.project.get_boxes(image_path)
        box_splitter = getattr(self, "_auto_boxes_for_canvas", None)
        if callable(box_splitter):
            auto_boxes, vlm_boxes = box_splitter(image_path)
        else:
            project_splitter = getattr(self.project, "split_auto_boxes_by_source", None)
            if callable(project_splitter):
                auto_boxes, vlm_boxes = project_splitter(image_path)
            else:
                auto_boxes = self.project.get_auto_boxes(image_path)
                vlm_boxes = {}
                get_meta = getattr(self.project, "get_auto_box_meta", None)
                meta = get_meta(image_path) if callable(get_meta) else {}
                meta = meta if isinstance(meta, dict) else {}
                if isinstance(auto_boxes, dict):
                    model_boxes = {}
                    for part_name, box in auto_boxes.items():
                        part_meta = meta.get(part_name, {}) if isinstance(meta.get(part_name), dict) else {}
                        if part_meta.get("source") == AUTO_BOX_SOURCE_VLM:
                            vlm_boxes[part_name] = box
                        else:
                            model_boxes[part_name] = box
                    auto_boxes = model_boxes
        candidates = []

        def _append(boxes, source):
            if not isinstance(boxes, dict):
                return

            ordered_parts = list(boxes.keys())
            preferred_parts = [part for part in list(preferred_roi_parts or []) if part in ordered_parts]
            if preferred_parts:
                ordered_parts = preferred_parts + [part for part in ordered_parts if part not in preferred_parts]

            for part in ordered_parts:
                box = boxes.get(part)
                if not isinstance(box, (list, tuple)) or len(box) != 4:
                    continue
                try:
                    clean_box = [float(v) for v in box]
                except Exception:
                    continue
                if clean_box[2] <= clean_box[0] or clean_box[3] <= clean_box[1]:
                    continue
                candidates.append({
                    "part": part,
                    "source": source,
                    "box": clean_box,
                })

        _append(manual_boxes, "manual")
        _append(auto_boxes, "auto")
        _append(vlm_boxes, "vlm")
        return candidates

    def on_file_selected(self, curr, prev):
        if not curr:
            return
        if curr.data(Qt.UserRole + 1):
            return
        
        # Robust Retrieval: Try getting data from UserRole first
        p = curr.data(Qt.UserRole)
        
        # Fallback for old items (shouldn't happen with new refresh logic)
        if not p:
            fn = curr.text()
            p = next((path for path in self.project.project_data["images"] if os.path.basename(path) == fn), None)
        if not p:
            return
            
        if p:
            previous_image = self.current_image
            same_image = bool(previous_image) and self._same_project_image_path(previous_image, p)
            if not same_image:
                self._defer_project_save_for_active_navigation()
            has_loaded_pixmap = bool(self.canvas.original_pixmap and not self.canvas.original_pixmap.isNull())

            self.current_image = p
            labels = self.project.get_labels(p)
            manual_boxes = self.project.get_boxes(p)
            auto_boxes, vlm_boxes = self._auto_boxes_for_canvas(p)
            if not (same_image and has_loaded_pixmap):
                self.canvas.load_image(p)
                self.on_enhancement_changed()
            self.canvas.set_polygons(labels)
            self.canvas.set_boxes(manual_boxes, auto_boxes, self._current_shrink_loose_boxes(), vlm=vlm_boxes)
            get_taxon = getattr(self.project, "get_taxon", self.project.get_genus)
            self.genus_combo.blockSignals(True)
            try:
                self.genus_combo.setCurrentText(get_taxon(p))
            finally:
                self.genus_combo.blockSignals(False)
            self._refresh_blink_refine_state()

    def on_part_selected(self, curr, prev):
        p = self._part_item_name(curr)
        if not p:
            self.canvas.set_active_part(None)
            self.desc_box.clear()
            return
        self.canvas.set_active_part(p)
        self.update_db_description(p)
        if self.check_morpho.isChecked():
            self.update_measurements(p)
        self._refresh_blink_refine_state()

    def launch_blink_from_workbench(self):
        if not self.current_image:
            QMessageBox.warning(self, tr("Child Expert Session Entry", self.current_lang), tr("Please select an image first.", self.current_lang))
            return

        selected_part = self._current_part_name()
        if not selected_part:
            QMessageBox.warning(self, tr("Child Expert Session Entry", self.current_lang), tr("Please select a target part first.", self.current_lang))
            return

        taxonomy = list(self.project.project_data.get("taxonomy", []))
        remembered_parent_map = self.project.get_blink_context_roi_parents()
        remembered_parent = remembered_parent_map.get(str(selected_part or "").strip())
        preferred_roi_parts = _blink_preferred_roi_parts(selected_part, remembered_parent)
        roi_candidates = self._collect_blink_roi_candidates(
            self.current_image,
            selected_part,
            preferred_roi_parts=preferred_roi_parts,
        )
        if not roi_candidates:
            QMessageBox.information(
                self,
                tr("Child Expert Session Entry", self.current_lang),
                tr("No entry ROI is available yet. Draw a manual box or generate an auto box in the workbench first.", self.current_lang),
            )
            return

        dialog = BlinkEntryDialog(
            self.current_image,
            taxonomy,
            selected_part,
            roi_candidates,
            self,
            self.current_lang,
            remembered_parent_map=remembered_parent_map,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        session = dialog.get_session_spec(self.current_image)
        if not session:
            QMessageBox.warning(
                self,
                tr("Child Expert Session Entry", self.current_lang),
                tr("Failed to build a child expert session from the selected options.", self.current_lang),
            )
            return

        labels = self.project.get_labels(self.current_image)
        manual_boxes = self.project.get_boxes(self.current_image)
        box_splitter = getattr(self, "_auto_boxes_for_canvas", None)
        if callable(box_splitter):
            auto_boxes, _vlm_boxes = box_splitter(self.current_image)
        else:
            project_splitter = getattr(self.project, "split_auto_boxes_by_source", None)
            if callable(project_splitter):
                auto_boxes, _vlm_boxes = project_splitter(self.current_image)
            else:
                auto_boxes = self.project.get_auto_boxes(self.current_image)
        started = self.blink_lab.start_session(session, labels, manual_boxes, auto_boxes)
        if not started:
            return
        self.tabs.setCurrentWidget(self.blink_lab)

        focus_roi = session.get("focus_roi", {})
        if not isinstance(focus_roi, dict):
            focus_roi = {}
        remembered_target_part = session.get("target_part")
        remembered_parent_part = str(focus_roi.get("part") or "").strip()
        if remembered_parent_part and remembered_target_part:
            if remembered_parent_part == remembered_target_part:
                self.project.clear_blink_context_parent(remembered_target_part)
            else:
                self.project.remember_blink_context_parent(remembered_target_part, remembered_parent_part)
                if hasattr(self.project, "register_cascade_route_candidate"):
                    self.project.register_cascade_route_candidate(
                        remembered_parent_part,
                        remembered_target_part,
                        focus_source=focus_roi.get("source"),
                        registration_source="blink_candidate",
                    )
                    if hasattr(self, "refresh_route_table"):
                        self.refresh_route_table()
        focus_label = focus_roi.get("part", "ROI")
        focus_source = focus_roi.get("source", "manual")
        self.log(
            tr("Opened child expert session for {0} via {1} ({2}).", self.current_lang).format(
                session.get('target_part'), focus_label, focus_source
            )
        )

    def on_genus_changed(self, txt):
        if self.current_image:
            set_taxon = getattr(self.project, "set_taxon", self.project.set_genus)
            try:
                set_taxon(self.current_image, txt, save=False)
            except TypeError:
                set_taxon(self.current_image, txt)
            self._schedule_project_save()

    def update_db_description(self, p):
        if p:
            saved_description = ""
            if self.current_image and hasattr(self.project, "get_part_description"):
                saved_description = self.project.get_part_description(self.current_image, p)
            if saved_description:
                self.desc_box.setText(saved_description)
            else:
                self.desc_box.setText(self.db.query_trait_description(self.genus_combo.currentText(), p))

    def _current_taxon_text(self):
        try:
            return self.genus_combo.currentText().strip()
        except Exception:
            return ""

    def _literature_source_taxon(self, source_meta):
        if not isinstance(source_meta, dict):
            return ""
        for key in ("taxon_name", "llm_taxon_name", "species_candidate"):
            value = str(source_meta.get(key) or "").strip()
            if value and value.lower() not in {"unknown", "unknown taxon", "n/a", "none", "null"}:
                return value
        return ""

    def _set_current_image_taxon_from_literature(self, source_meta):
        taxon = self._literature_source_taxon(source_meta)
        if not self.current_image or not taxon:
            return False
        set_taxon = getattr(self.project, "set_taxon", self.project.set_genus)
        try:
            set_taxon(self.current_image, taxon, save=False)
        except TypeError:
            set_taxon(self.current_image, taxon)
        self._schedule_project_save()
        if hasattr(self, "genus_combo"):
            self.genus_combo.blockSignals(True)
            try:
                if self.genus_combo.findText(taxon) < 0:
                    self.genus_combo.addItem(taxon)
                self.genus_combo.setCurrentText(taxon)
            finally:
                self.genus_combo.blockSignals(False)
        return True

    def _candidate_literature_db_paths(self, provenance):
        extra_paths = []
        inferred_db = infer_literature_db_path_from_artifact_image(self.current_image)
        if inferred_db:
            extra_paths.append(inferred_db)
        for candidate in self._project_literature_db_paths():
            if candidate:
                extra_paths.append(candidate)
        pdf_widget = getattr(self, "pdf_widget", None)
        if pdf_widget is not None and hasattr(pdf_widget, "_resolve_extract_db_path"):
            try:
                widget_path = pdf_widget._resolve_extract_db_path(pdf_widget.edit_db_path.text())
                if widget_path:
                    extra_paths.append(widget_path)
            except Exception:
                pass
        return candidate_literature_db_paths(
            repo_root=REPO_ROOT,
            provenance=provenance,
            extra_paths=extra_paths,
        )

    def _project_literature_db_paths(self):
        paths = []

        def add_path(value):
            text = str(value or "").strip()
            if not text:
                return
            try:
                expanded = os.path.abspath(os.path.expanduser(text))
            except Exception:
                return
            norm = os.path.normcase(os.path.normpath(expanded))
            if norm not in {os.path.normcase(os.path.normpath(path)) for path in paths}:
                paths.append(expanded)

        provenance_map = {}
        try:
            provenance_map = self.project.project_data.get("image_provenance", {})
        except Exception:
            provenance_map = {}
        if isinstance(provenance_map, dict):
            for provenance in provenance_map.values():
                if not isinstance(provenance, dict):
                    continue
                add_path(provenance.get("source_db"))
                source_ref = provenance.get("source_ref", {})
                if isinstance(source_ref, dict):
                    add_path(source_ref.get("db_path"))
                inferred_from_parent = infer_literature_db_path_from_artifact_image(
                    (provenance.get("derived_from") or {}).get("image_path", "")
                    if isinstance(provenance.get("derived_from"), dict)
                    else ""
                )
                add_path(inferred_from_parent)

        project_path = getattr(self.project, "current_project_path", "") or ""
        if project_path:
            project_dir = os.path.dirname(os.path.abspath(project_path))
            for value in (
                os.path.join(project_dir, "taxamask_literature.db"),
                os.path.join(project_dir, "pdf_extraction", "taxamask_literature.db"),
                os.path.join(os.path.dirname(project_dir), "pdf_extraction", "taxamask_literature.db"),
            ):
                add_path(value)
        try:
            pdf_root = os.path.join(self._default_outputs_root(), "pdf_extraction")
            add_path(os.path.join(pdf_root, "taxamask_literature.db"))
            if os.path.isdir(pdf_root):
                for dirpath, _dirnames, filenames in os.walk(pdf_root):
                    for filename in filenames:
                        if filename.lower().endswith(".db"):
                            add_path(os.path.join(dirpath, filename))
        except Exception:
            pass
        return paths

    def _resolve_current_literature_context(self):
        if not self.current_image:
            return "", {}, "no_current_image"
        provenance = {}
        if hasattr(self.project, "get_image_provenance"):
            provenance = self.project.get_image_provenance(self.current_image)
        last_reason = "literature_db_missing"
        taxon_hint = self._current_taxon_text()
        for db_path in self._candidate_literature_db_paths(provenance):
            if not os.path.exists(db_path):
                continue
            trusted_db = self._literature_db_matches_image_source(db_path, provenance)
            context = resolve_literature_context(
                db_path,
                image_path=self.current_image,
                provenance=provenance,
                taxon_hint=taxon_hint,
                allow_filename_figure_id=trusted_db,
            )
            if context.get("available"):
                return db_path, context, ""
            last_reason = str(context.get("reason", "") or last_reason)
        if taxon_hint and taxon_hint.lower() not in {"unknown", "unknown taxon", "n/a", "none", "null"}:
            for db_path in self._candidate_literature_db_paths(provenance):
                if not os.path.exists(db_path):
                    continue
                context = resolve_literature_context(
                    db_path,
                    image_path=self.current_image,
                    provenance=provenance,
                    taxon_hint=taxon_hint,
                    allow_filename_figure_id=False,
                    allow_taxon_match=True,
                )
                if context.get("available") and context.get("link_mode") == "taxon_match_not_image_provenance":
                    return db_path, context, ""
                last_reason = str(context.get("reason", "") or last_reason)
        fallback_db = default_literature_db_path(REPO_ROOT)
        return fallback_db, {}, last_reason

    def _resolve_literature_context_from_selected_db(self, db_path):
        if not self.current_image or not db_path:
            return {}, "literature_db_missing"
        provenance = {}
        if hasattr(self.project, "get_image_provenance"):
            provenance = self.project.get_image_provenance(self.current_image)
        taxon_hint = self._current_taxon_text()
        context = resolve_literature_context(
            db_path,
            image_path=self.current_image,
            provenance=provenance,
            taxon_hint=taxon_hint,
            allow_filename_figure_id=True,
        )
        if context.get("available"):
            return context, ""
        context = resolve_literature_context(
            db_path,
            image_path=self.current_image,
            provenance=provenance,
            taxon_hint=taxon_hint,
            allow_filename_figure_id=False,
            allow_taxon_match=True,
        )
        if context.get("available"):
            return context, ""
        return {}, str(context.get("reason", "") or "figure_context_missing")

    def _choose_literature_db_for_current_taxon(self):
        start_dir = os.path.join(self._default_outputs_root(), "pdf_extraction")
        if not os.path.isdir(start_dir):
            start_dir = self._default_outputs_root()
        db_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("Choose Literature Database", self.current_lang),
            start_dir,
            "SQLite Database (*.db);;All Files (*)",
        )
        db_path = str(db_path or "").strip()
        if not db_path:
            return "", {}, "literature_db_missing"
        context, reason = self._resolve_literature_context_from_selected_db(db_path)
        if context:
            pdf_widget = getattr(self, "pdf_widget", None)
            if pdf_widget is not None and hasattr(pdf_widget, "_set_extract_db_path"):
                try:
                    pdf_widget._set_extract_db_path(db_path)
                except Exception:
                    pass
            return db_path, context, ""
        return db_path, {}, reason

    def _literature_db_matches_image_source(self, db_path, provenance):
        db_norm = os.path.normcase(os.path.normpath(os.path.abspath(str(db_path or ""))))
        provenance = provenance if isinstance(provenance, dict) else {}
        source_db = str(provenance.get("source_db", "") or "").strip()
        source_ref = provenance.get("source_ref", {})
        if not isinstance(source_ref, dict):
            source_ref = {}
        for value in (source_db, source_ref.get("db_path")):
            if not value:
                continue
            try:
                candidate = os.path.normcase(os.path.normpath(os.path.abspath(os.path.expanduser(str(value)))))
            except Exception:
                continue
            if candidate == db_norm:
                return True
        inferred_db = infer_literature_db_path_from_artifact_image(self.current_image)
        if inferred_db:
            inferred_norm = os.path.normcase(os.path.normpath(os.path.abspath(inferred_db)))
            if inferred_norm == db_norm:
                return True
        return False

    def open_literature_description_dialog(self):
        if not self.current_image:
            QMessageBox.warning(self, tr("Literature Trait Descriptions", self.current_lang), tr("Please select an image first.", self.current_lang))
            return
        current_part = self._current_part_name()
        if not current_part:
            QMessageBox.warning(self, tr("Literature Trait Descriptions", self.current_lang), tr("Please select a target part first.", self.current_lang))
            return

        db_path, context, reason = self._resolve_current_literature_context()
        if not context:
            taxon_text = self._current_taxon_text()
            if taxon_text and taxon_text.lower() not in {"unknown", "unknown taxon", "n/a", "none", "null"}:
                reply = themed_yes_no_question(
                    self,
                    tr("Choose Literature Database", self.current_lang),
                    tr(
                        "No literature database was found automatically. Choose the PDF extraction database that contains this species?",
                        self.current_lang,
                    ),
                    default_button=QMessageBox.Yes,
                )
                if reply == QMessageBox.Yes:
                    db_path, context, reason = self._choose_literature_db_for_current_taxon()
                    if context:
                        return self._open_literature_description_dialog_with_context(db_path, context, current_part)
            if not self._current_taxon_text() or self._current_taxon_text().lower() in {"unknown", "unknown taxon", "n/a", "none", "null"}:
                message = tr(
                    "No PDF literature source is linked to the current image, and the current image taxon is unknown. Set the current image taxon first, or import images through the PDF candidate workflow.",
                    self.current_lang,
                )
            else:
                message = tr(
                    "No PDF literature source is linked to the current image. Import images through the PDF candidate workflow or open a project that preserves PDF image provenance.",
                    self.current_lang,
                )
            if reason == "literature_db_missing":
                message = tr("PDF literature database was not found: {0}", self.current_lang).format(db_path)
            QMessageBox.information(self, tr("Literature Trait Descriptions", self.current_lang), message)
            return

        self._open_literature_description_dialog_with_context(db_path, context, current_part)

    def _open_literature_description_dialog_with_context(self, db_path, context, current_part):
        dialog = LiteratureDescriptionDialog(
            db_path=db_path,
            context=context,
            image_path=self.current_image,
            current_part=current_part,
            taxon_hint=self._current_taxon_text(),
            parent=self,
            lang=self.current_lang,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        description_text = dialog.selected_description_text()
        if not description_text:
            return
        source_meta = dialog.selected_source()
        self._apply_literature_description(
            current_part,
            description_text,
            source_meta,
            append=(dialog.action_mode == "append"),
        )

    def _apply_literature_description(self, part_name, description_text, source_meta, append=False):
        clean_part = str(part_name or "").strip()
        clean_text = str(description_text or "").strip()
        if not self.current_image or not clean_part or not clean_text:
            return
        existing = self.desc_box.toPlainText().strip()
        missing_prefix = "No description found for "
        if append and existing and not existing.startswith(missing_prefix) and clean_text not in existing:
            final_text = f"{existing}\n\n{clean_text}"
        else:
            final_text = clean_text
        self.desc_box.setText(final_text)
        self._ensure_workbench_description_visible()
        set_part_description = getattr(self.project, "set_part_description", None)
        if callable(set_part_description):
            set_part_description(self.current_image, clean_part, final_text, source_meta=source_meta, save=False)
        else:
            existing_points = self.project.get_labels(self.current_image).get(clean_part, [])
            self.project.update_label(self.current_image, clean_part, existing_points, final_text, save=False)
            if source_meta and hasattr(self.project, "set_description_source"):
                self.project.set_description_source(self.current_image, clean_part, source_meta, save=False)
        self._set_current_image_taxon_from_literature(source_meta)
        self._schedule_project_save()
        self.log(tr("Applied literature description for {0}.", self.current_lang).format(clean_part))

    def _ensure_workbench_description_visible(self):
        if hasattr(self, "workbench_inspector_scroll"):
            self.workbench_inspector_scroll.setMinimumWidth(260)
        if hasattr(self, "workbench_splitter"):
            sizes = self.workbench_splitter.sizes()
            if len(sizes) >= 3 and sizes[2] < 180:
                total = max(sum(sizes), 900)
                left = sizes[0] if sizes[0] >= 180 else 240
                right = min(360, max(260, total // 5))
                center = max(360, total - left - right)
                self.workbench_splitter.setSizes([left, center, right])
        if hasattr(self, "desc_box"):
            if hasattr(self, "workbench_inspector_scroll"):
                self.workbench_inspector_scroll.ensureWidgetVisible(self.desc_box)
            self.desc_box.setFocus(Qt.OtherFocusReason)

    def on_enhancement_changed(self):
        self.canvas.set_enhancements(0, 1.0)

    def on_tool_changed(self):
        if self.radio_magic.isChecked():
            self.canvas.set_mode("MAGIC_WAND")
            self._refresh_annotation_box_constraints()
        elif self.radio_box.isChecked():
            self.canvas.set_mode("BOX_PROMPT")
            self._refresh_annotation_box_constraints()
        elif self.radio_annotation_box.isChecked() or self.radio_loose_shrink_box.isChecked():
            self.canvas.set_mode("ANNOTATION_BOX")
            self._refresh_annotation_box_constraints()
        elif self.radio_scale.isChecked():
            self.canvas.set_mode("SCALE")
            self._refresh_annotation_box_constraints()
        else:
            self.canvas.set_mode("DRAW")
            self._refresh_annotation_box_constraints()

    def on_blink_parent_context_changed(self, _index=None):
        if getattr(self, "_updating_blink_parent_context", False):
            return
        child_part = self._current_part_name()
        parent_part = self.combo_blink_parent_context.currentData() if hasattr(self, "combo_blink_parent_context") else None
        child_part = str(child_part or "").strip()
        parent_part = str(parent_part or "").strip()
        if not child_part or not parent_part or child_part == parent_part:
            return
        if self._is_parent_part(child_part):
            return
        if hasattr(self.project, "remember_blink_context_parent"):
            self.project.remember_blink_context_parent(child_part, parent_part, save=False)
        if hasattr(self.project, "register_cascade_route_candidate"):
            self.project.register_cascade_route_candidate(
                parent_part,
                child_part,
                registration_source="workbench_blink_refine",
                save=False,
            )
        self._schedule_project_save()
        self.refresh_route_table()
        self.log(tr("Manual parent context set: {0} -> {1}.", self.current_lang).format(parent_part, child_part))

    def on_magic_wand_clicked(self, x, y):
        self._request_sam_point(x, y)

    def on_magic_box_completed(self, x1, y1, x2, y2):
        self._request_sam_box(x1, y1, x2, y2)

    def _sam_worker_ready(self):
        return bool(self.sam_worker and getattr(self.sam_worker, "model", None) is not None)

    def _on_sam_model_loaded(self):
        self.log(tr("SAM Model Loaded and Ready!", self.current_lang))

    def _begin_sam_prompt(self):
        if not self.current_image:
            return None
        if not self._sam_worker_ready():
            self.ensure_sam_preloaded()
            self.log(tr("SAM is still loading. Try the box again after the ready message.", self.current_lang))
            return None
        if self.sam_busy:
            self.log(tr("SAM is still processing the previous prompt. Please wait a moment.", self.current_lang))
            return None
        part = self._current_part_name()
        if not part:
            return None
        self.sam_busy = True
        self.pending_sam_part = part
        self.pending_sam_image = self.current_image
        self.pending_sam_description = self.desc_box.toPlainText()
        return self.current_image, part

    def _request_sam_point(self, x, y):
        prompt = self._begin_sam_prompt()
        if not prompt:
            return
        image_path, _part = prompt
        self.sam_point_requested.emit(image_path, float(x), float(y))

    def _request_sam_box(self, x1, y1, x2, y2):
        prompt = self._begin_sam_prompt()
        if not prompt:
            return
        image_path, _part = prompt
        self.sam_box_requested.emit(image_path, float(x1), float(y1), float(x2), float(y2))

    def on_annotation_box_completed(self, x1, y1, x2, y2):
        part = self._current_part_name()
        clean_box = _clean_box([x1, y1, x2, y2])
        if not self.current_image or not part or not clean_box:
            return

        context = self._current_blink_context()
        if self._active_box_tool_role() == "shrink":
            if context.get("role") != "child":
                self._warn_blink_context(
                    tr("Blink shrink start boxes are only used for child structures. Select a child structure first.", self.current_lang)
                )
                return
            update_loose_box = getattr(self.project, "update_shrink_loose_box", None)
            if callable(update_loose_box):
                update_loose_box(self.current_image, part, clean_box, save=False)
            self._refresh_current_canvas_boxes()
            self.log(tr("Saved Blink shrink start box for {0}.", self.current_lang).format(part))
        else:
            existing_points = self.project.get_labels(self.current_image).get(part, [])
            self.project.update_label(
                self.current_image,
                part,
                existing_points,
                self.desc_box.toPlainText(),
                box=clean_box,
                save=False,
            )
            self._refresh_current_canvas_boxes()
            if context.get("role") == "child" and context.get("parent_part"):
                self.project.remember_blink_context_parent(part, context.get("parent_part"), save=False)
            self.log(tr("Saved manual ROI box for {0}.", self.current_lang).format(part))
        self._schedule_project_save()
        self._refresh_blink_refine_state()

    def _warn_blink_context(self, message):
        QMessageBox.information(self, tr("Child-part annotation", self.current_lang), message)

    def _active_child_blink_context(self, require_ready=False):
        context = self._refresh_blink_refine_state()
        if context.get("role") != "child" or not context.get("child_part") or not context.get("parent_part"):
            self._warn_blink_context(tr("Select a child structure with a parent context first.", self.current_lang))
            return None
        if not context.get("has_parent_box"):
            self._warn_blink_context(tr("Draw a parent box before child refinement.", self.current_lang))
            return None
        if require_ready and not context.get("can_refine"):
            self._warn_blink_context(context.get("disabled_reason") or tr("Configure the current route before continuing.", self.current_lang))
            return None
        return context

    def run_blink_child_auto_annotate(self):
        context = self._active_child_blink_context(require_ready=True)
        if not context or not self.current_image:
            return
        child_part = context.get("child_part")
        parent_part = context.get("parent_part")
        parent_box = context.get("parent_box")
        self.log(tr("Running child auto-annotation for {0} via {1}.", self.current_lang).format(child_part, parent_part))
        try:
            expert_result = self.engine.cascade_manager.infer_child_part(
                self.current_image,
                parent_box,
                child_part,
                parent_part=parent_part,
                route_manifest=self.project.get_cascade_routes(),
            )
            if not isinstance(expert_result, dict):
                self._warn_blink_context(tr("No usable route expert result was returned for this child structure.", self.current_lang))
                return
            raw_box = _clean_box(expert_result.get("box"))
            if not raw_box:
                self._warn_blink_context(tr("The route expert did not return a valid child box.", self.current_lang))
                return
            image_bgr = cv2.imread(self.current_image)
            if image_bgr is None:
                raise RuntimeError(tr("Could not read the current image.", self.current_lang))
            image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
            polygon = self.engine.predict_base_sam_polygon(image_rgb, raw_box, poly_epsilon=self.inf_poly_epsilon)
            if polygon and len(polygon) >= 3:
                self.project.update_label(self.current_image, child_part, polygon, self.desc_box.toPlainText(), box=raw_box, save=False)
                self.canvas.set_polygons(self.project.get_labels(self.current_image))
                self._refresh_current_canvas_boxes()
                self.log(tr("Generated child draft polygon for {0}.", self.current_lang).format(child_part))
            else:
                existing_points = self.project.get_labels(self.current_image).get(child_part, [])
                self.project.update_label(self.current_image, child_part, existing_points, self.desc_box.toPlainText(), box=raw_box, save=False)
                self._refresh_current_canvas_boxes()
                self.log(tr("Route expert produced a child box for {0}; refine polygon manually.", self.current_lang).format(child_part))
            self.project.remember_blink_context_parent(child_part, parent_part, save=False)
            self._schedule_project_save()
            self._refresh_blink_refine_state()
        except Exception as exc:
            self._warn_blink_context(tr("Child auto-annotation failed: {0}", self.current_lang).format(str(exc)))

    def _load_blink_refiner_class(self):
        if "core.blink_refiner" in sys.modules:
            from core.blink_refiner import BlinkRefiner
            return BlinkRefiner
        try:
            from AntSleap.core.blink_refiner import BlinkRefiner
        except ImportError:
            from core.blink_refiner import BlinkRefiner
        return BlinkRefiner

    def _active_blink_auto_shrink_steps(self):
        child_defaults = _runtime_child_backend_defaults(self.project)
        try:
            value = int(child_defaults.get("auto_shrink_steps", self.blink_auto_shrink_steps))
        except Exception:
            value = self.blink_auto_shrink_steps
        try:
            value = int(value)
        except Exception:
            value = DEFAULT_CHILD_AUTO_SHRINK_STEPS
        return max(1, min(200, value))

    def _blink_parent_context_for_image(self, image_path, child_part, parent_part):
        previous_current = self.current_image
        try:
            self.current_image = image_path
            parent_box, parent_box_source = self._parent_context_box(parent_part)
        finally:
            self.current_image = previous_current
        if not parent_box:
            return None
        return {
            "parent_part": parent_part,
            "parent_box": parent_box,
            "source": parent_box_source or "workbench",
        }

    def _prepared_blink_auto_shrink_images(self, child_part, parent_part):
        prepared = []
        missing_polygon = 0
        missing_loose_box = 0
        missing_parent_box = 0
        existing_trajectory = 0
        for image_path in self.project.project_data.get("images", []):
            if not image_path:
                continue
            labels = self.project.project_data.get("labels", {}).get(image_path, {})
            parts = labels.get("parts", {}) if isinstance(labels.get("parts", {}), dict) else {}
            polygon = parts.get(child_part, [])
            if not polygon or len(polygon) < 3:
                missing_polygon += 1
                continue
            loose_boxes = labels.get("shrink_loose_boxes", {}) if isinstance(labels.get("shrink_loose_boxes", {}), dict) else {}
            loose_box = _clean_box(loose_boxes.get(child_part))
            if not loose_box:
                missing_loose_box += 1
                continue
            trajectories = labels.get("trajectories", {}) if isinstance(labels.get("trajectories", {}), dict) else {}
            if child_part in trajectories:
                existing_trajectory += 1
                continue
            parent_context = self._blink_parent_context_for_image(image_path, child_part, parent_part)
            if not parent_context:
                missing_parent_box += 1
                continue
            prepared.append({
                "image_path": image_path,
                "polygon": polygon,
                "loose_box": loose_box,
                "parent_context": parent_context,
            })
        return {
            "prepared": prepared,
            "missing_polygon": missing_polygon,
            "missing_loose_box": missing_loose_box,
            "missing_parent_box": missing_parent_box,
            "existing_trajectory": existing_trajectory,
        }

    def _generate_blink_shrink_for_image(self, image_path, child_part, polygon, loose_box, parent_context, refiner, steps=None):
        image_bgr = cv2.imread(image_path)
        if image_bgr is None:
            raise RuntimeError(tr("Could not read the current image.", self.current_lang))
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        trajectory = refiner.generate_shrink_trajectory(
            image_rgb,
            loose_box,
            polygon,
            steps=steps or self._active_blink_auto_shrink_steps(),
        )
        if not trajectory:
            return []
        self.project.update_trajectory(
            image_path,
            child_part,
            trajectory,
            parent_context=parent_context,
            save=False,
        )
        best_box = _clean_box(trajectory[-1].get("box") if isinstance(trajectory[-1], dict) else None)
        if best_box:
            description = ""
            if self.current_image and self._same_project_image_path(image_path, self.current_image):
                description = self.desc_box.toPlainText()
            else:
                descriptions = self.project.project_data.get("labels", {}).get(image_path, {}).get("descriptions", {})
                if isinstance(descriptions, dict):
                    description = descriptions.get(child_part, "")
            self.project.update_label(
                image_path,
                child_part,
                polygon,
                description,
                box=best_box,
                save=False,
            )
        return trajectory

    def run_blink_auto_shrink(self):
        context = self._active_child_blink_context(require_ready=False)
        if not context or not self.current_image:
            return
        child_part = context.get("child_part")
        parent_part = context.get("parent_part")
        polygon = self.project.get_labels(self.current_image).get(child_part, [])
        if not polygon or len(polygon) < 3:
            self._warn_blink_context(tr("Draw or confirm the child polygon before auto-shrink.", self.current_lang))
            return
        loose_boxes = self.project.get_shrink_loose_boxes(self.current_image) if hasattr(self.project, "get_shrink_loose_boxes") else {}
        loose_box = _clean_box(loose_boxes.get(child_part) if isinstance(loose_boxes, dict) else None)
        if not loose_box:
            self._warn_blink_context(tr("Select Blink Shrink Start Box on the canvas toolbar and draw one around the child first.", self.current_lang))
            return
        try:
            BlinkRefiner = self._load_blink_refiner_class()
            parts_model = self.engine.ensure_parts_model_loaded() if hasattr(self.engine, "ensure_parts_model_loaded") else self.engine.parts_model
            sam_model = getattr(parts_model, "ultralytics_sam", None)
            refiner = BlinkRefiner(sam_model=sam_model, device=self.runtime_device)
            trajectory = self._generate_blink_shrink_for_image(
                self.current_image,
                child_part,
                polygon,
                loose_box,
                {
                    "parent_part": parent_part,
                    "parent_box": context.get("parent_box"),
                    "source": context.get("parent_box_source") or "workbench",
                },
                refiner,
            )
            if not trajectory:
                self._warn_blink_context(tr("Auto-shrink did not generate a trajectory.", self.current_lang))
                return
            self.project.remember_blink_context_parent(child_part, parent_part, save=False)
            self._schedule_project_save()
            self._refresh_current_canvas_boxes()
            self._refresh_blink_refine_state()
            self.log(tr("Saved {0} shrink trajectory frames for {1}.", self.current_lang).format(len(trajectory), child_part))
        except Exception as exc:
            self._warn_blink_context(tr("Auto-shrink failed: {0}", self.current_lang).format(str(exc)))

    def run_blink_batch_auto_shrink(self):
        context = self._active_child_blink_context(require_ready=False)
        if not context:
            return
        child_part = context.get("child_part")
        parent_part = context.get("parent_part")
        if not child_part or not parent_part:
            return

        summary = self._prepared_blink_auto_shrink_images(child_part, parent_part)
        prepared = list(summary.get("prepared", []) or [])
        if not prepared:
            self.log(
                tr(
                    "No prepared images for batch auto-shrink. Existing trajectories: {0}; missing polygon: {1}; missing shrink box: {2}; missing parent box: {3}.",
                    self.current_lang,
                ).format(
                    summary.get("existing_trajectory", 0),
                    summary.get("missing_polygon", 0),
                    summary.get("missing_loose_box", 0),
                    summary.get("missing_parent_box", 0),
                )
            )
            return

        reply = themed_yes_no_question(
            self,
            tr("Batch auto-shrink", self.current_lang),
            tr(
                "Batch auto-shrink prepared {0} image(s) for {1}. Existing trajectories skipped: {2}; missing polygon: {3}; missing shrink box: {4}; missing parent box: {5}.\n\nRun auto-shrink for all prepared images?",
                self.current_lang,
            ).format(
                len(prepared),
                child_part,
                summary.get("existing_trajectory", 0),
                summary.get("missing_polygon", 0),
                summary.get("missing_loose_box", 0),
                summary.get("missing_parent_box", 0),
            ),
            confirm_role=BUTTON_ROLE_RUN,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            BlinkRefiner = self._load_blink_refiner_class()
            parts_model = self.engine.ensure_parts_model_loaded() if hasattr(self.engine, "ensure_parts_model_loaded") else self.engine.parts_model
            sam_model = getattr(parts_model, "ultralytics_sam", None)
            refiner = BlinkRefiner(sam_model=sam_model, device=self.runtime_device)
            success = 0
            failed = 0
            for item in prepared:
                try:
                    trajectory = self._generate_blink_shrink_for_image(
                        item["image_path"],
                        child_part,
                        item["polygon"],
                        item["loose_box"],
                        item["parent_context"],
                        refiner,
                    )
                    if trajectory:
                        success += 1
                    else:
                        failed += 1
                except Exception as exc:
                    failed += 1
                    self.log(
                        tr("Auto-shrink failed: {0}", self.current_lang).format(
                            f"{os.path.basename(str(item.get('image_path', '')))} | {exc}"
                        )
                    )
            if success:
                self.project.remember_blink_context_parent(child_part, parent_part, save=False)
                self.project.save_project()
            if self.current_image:
                self.canvas.set_polygons(self.project.get_labels(self.current_image))
                self._refresh_current_canvas_boxes()
            self._refresh_image_list_status_or_rebuild(self.current_image)
            self._refresh_blink_refine_state()
            self.log(
                tr("Batch auto-shrink finished for {0}/{1} image(s) of {2}. Failed: {3}.", self.current_lang).format(
                    success,
                    len(prepared),
                    child_part,
                    failed,
                )
            )
        except Exception as exc:
            self._warn_blink_context(tr("Auto-shrink failed: {0}", self.current_lang).format(str(exc)))

    def train_current_blink_expert(self):
        context = self._active_child_blink_context(require_ready=False)
        if not context:
            return
        if self._is_parent_training_running():
            self._warn_blink_context(tr("Parent-part training is running. Wait for it to finish before training a child expert.", self.current_lang))
            return
        if getattr(self.blink_lab, "training_thread", None) is not None and self.blink_lab.training_thread.isRunning():
            self._warn_blink_context(tr("Blink expert training is already running.", self.current_lang))
            return
        child_part = context.get("child_part")
        parent_part = context.get("parent_part")
        scope_payload = self._selected_training_scope_payload()
        scope_images = list(scope_payload.get("images", []) or [])
        scope_label = str(scope_payload.get("label") or tr("All Images", self.current_lang))
        scope_id = str(scope_payload.get("scope_id") or "__all__")
        if not scope_images:
            self._warn_blink_context(
                tr(
                    "Selected training scope is empty. Choose another image group or add images to this group first.",
                    self.current_lang,
                )
            )
            return
        child_training_scope = {
            "scope_id": scope_id,
            "label": scope_label,
            "image_count": len(scope_images),
        }
        self.child_training_failed = False
        self.child_training_cancel_requested = False
        self.btn_train.setEnabled(False)
        self._set_training_progress(
            "child",
            f"{tr('Child-part expert training', self.current_lang)}: {parent_part} -> {child_part}",
            0,
        )
        self.blink_lab.canvas.current_tool_part = child_part
        self.blink_lab.session_target_part = child_part
        self.blink_lab.current_image_path = self.current_image
        self.blink_lab.active_session = {
            "image_path": self.current_image,
            "target_part": child_part,
            "focus_roi": {
                "part": parent_part,
                "source": context.get("parent_box_source") or "workbench",
                "box": context.get("parent_box"),
            },
        }
        self.blink_lab.training_route_context = self.blink_lab._route_context_for_training(parent_part, child_part)
        self.blink_lab.train_expert_model(
            allowed_image_paths=scope_images,
            training_scope=child_training_scope,
        )
        self._connect_child_training_progress()
        if getattr(self.blink_lab, "training_thread", None) is None:
            self.btn_train.setEnabled(True)
            if hasattr(self, "btn_blink_stop_training"):
                self.btn_blink_stop_training.setEnabled(False)
            self._set_training_progress(None, tr("No training running.", self.current_lang), 0)
        else:
            if hasattr(self, "btn_blink_stop_training"):
                self.btn_blink_stop_training.setEnabled(True)
        self._refresh_blink_refine_state()
        self.log(tr("Started Blink expert training for {0} -> {1}.", self.current_lang).format(parent_part, child_part))
        self.log(tr("Training scope: {0} ({1} image(s))", self.current_lang).format(scope_label, len(scope_images)))

    def stop_current_blink_expert_training(self):
        if not self._is_child_training_running():
            if hasattr(self, "btn_blink_stop_training"):
                self.btn_blink_stop_training.setEnabled(False)
            return
        self.child_training_cancel_requested = True
        if hasattr(self, "btn_blink_stop_training"):
            self.btn_blink_stop_training.setEnabled(False)
        self._set_training_progress("child", tr("Stopping child-part expert training...", self.current_lang), self.progress.value())
        self.blink_lab.stop_expert_training()

    def open_current_route_expert_settings(self):
        context = self._refresh_blink_refine_state()
        parent_part = context.get("parent_part")
        child_part = context.get("child_part")
        if not parent_part or not child_part:
            self._warn_blink_context(tr("Select a child structure with a parent context first.", self.current_lang))
            return
        if hasattr(self.project, "register_cascade_route_candidate"):
            self.project.register_cascade_route_candidate(
                parent_part,
                child_part,
                focus_source=context.get("parent_box_source"),
                registration_source="workbench_blink_refine",
                save=False,
            )
            self.project.remember_blink_context_parent(child_part, parent_part, save=False)
            self._schedule_project_save()
        self.open_stl_model_settings(target_route=(parent_part, child_part))

    def on_sam_mask_generated(self, pts, box=None):
        image_path = self.pending_sam_image or self.current_image
        part = self.pending_sam_part or self._current_part_name()
        description_text = self.pending_sam_description
        self.sam_busy = False
        self.pending_sam_part = None
        self.pending_sam_image = None
        self.pending_sam_description = ""
        if image_path and part:
            self.on_polygon_completed(part, pts, box, image_path=image_path, description_text=description_text)

    def on_sam_prompt_failed(self, message):
        self.sam_busy = False
        self.pending_sam_part = None
        self.pending_sam_image = None
        self.pending_sam_description = ""
        if message:
            self.log(str(message))

    def on_polygon_completed(self, p, pts, box=None, image_path=None, description_text=None):
        target_image = image_path or self.current_image
        if target_image:
            if not pts:
                # Empty points means DELETE
                self.project.delete_label(target_image, p, save=False)
            else:
                label_description = self.desc_box.toPlainText() if description_text is None else str(description_text)
                if label_description.strip() == "Auto-Annotated":
                    label_description = ""
                self.project.update_label(target_image, p, pts, label_description, box=box, save=False)
            self._schedule_project_save()
            is_current_image = bool(self.current_image) and self._same_project_image_path(target_image, self.current_image)
            if is_current_image:
                self.canvas.set_polygons(self.project.get_labels(self.current_image))
                self._refresh_current_canvas_boxes()
            
            self._refresh_current_image_list_status(target_image)
            
            if is_current_image and self.check_morpho.isChecked():
                self.update_measurements(p)
            if is_current_image:
                self._refresh_blink_refine_state()

    def toggle_morphometrics(self, state):
        on = self.check_morpho.isChecked()
        self.radio_scale.setVisible(on)
        self.group_morpho.setVisible(on)
        p = self._current_part_name()
        if on and p:
            self.update_measurements(p)

    def on_scale_defined(self, lpx):
        v, ok = QInputDialog.getDouble(self, tr("Scale Tool", self.current_lang), tr("mm:", self.current_lang), 1.0, 0.001, 1000.0, 3)
        if ok and self.current_image:
            try:
                self.project.set_scale(self.current_image, lpx/v, save=False)
            except TypeError:
                self.project.set_scale(self.current_image, lpx/v)
            self._schedule_project_save()
            self.refresh_ui()

    def update_measurements(self, p):
        if not self.current_image or not p:
            return
        sc = self.project.get_scale(self.current_image)
        if not sc:
            self.label_measurements.setText(tr("No Scale.", self.current_lang))
            return
        pts = self.project.get_labels(self.current_image).get(p)
        if pts and len(pts) > 2:
            import cv2
            pts_np = np.array(pts, dtype=np.float32)
            a = cv2.contourArea(pts_np) / (sc*sc)
            peri = cv2.arcLength(pts_np, True) / sc
            self.label_measurements.setText(tr("Area: {0:.4f} mm2\nPeri: {1:.4f} mm", self.current_lang).format(a, peri))
        else:
            self.label_measurements.setText(tr("No Polygon.", self.current_lang))

    def run_training(self):
        self._flush_pending_project_save(defer_for_navigation=False)
        if self.trainer and self.trainer.isRunning():
            self.log(tr("Training already running...", self.current_lang))
            return
        if self._is_child_training_running():
            self.log(tr("Child-part expert training is running. Wait for it to finish before training parent models.", self.current_lang))
            QMessageBox.information(
                self,
                tr("Training", self.current_lang),
                tr("Child-part expert training is running. Wait for it to finish before training parent models.", self.current_lang),
            )
            return
        scope_payload = self._selected_training_scope_payload()
        scope_id = str(scope_payload.get("scope_id", "__all__") or "__all__")
        if _runtime_parent_backend(self.project, self.model_backend) == EXTERNAL_BACKEND_ID:
            if scope_id != "__all__":
                QMessageBox.information(
                    self,
                    tr("Training", self.current_lang),
                    tr(
                        "Parent-part image-group training is available for the built-in Locator/SAM backend. Custom parent extensions still receive the full project contract.",
                        self.current_lang,
                    )
                    + "\n\n"
                    + tr(
                        "Choose All Images to run this custom parent extension, or switch the active profile to Built-in Locator + SAM for image-group training.",
                        self.current_lang,
                    ),
                )
                return
            self.run_external_training()
            return
        images = list(scope_payload.get("images", []) or [])
        labels_by_image = dict(self.project.project_data.get("labels", {}))
        if not images:
            QMessageBox.warning(
                self,
                tr("No Labels", self.current_lang),
                tr("Selected training scope is empty. Choose another image group or add images to this group first.", self.current_lang),
            )
            return
        tax = self.project.project_data["taxonomy"]
        locator_scope = self.project.get_locator_scope()
        preflight = build_training_preflight(images, labels_by_image, tax, locator_scope)
        scope_label = str(scope_payload.get("label", "") or tr("All Images", self.current_lang))
        preflight["training_scope_id"] = scope_id
        preflight["training_scope_label"] = scope_label
        preflight["training_scope_image_count"] = len(images)

        if not preflight.get("locator_samples") and not preflight.get("parts_samples"):
            QMessageBox.warning(self, tr("No Labels", self.current_lang), tr("Annotate first!", self.current_lang))
            return

        self.log(tr("Training scope: {0} ({1} image(s))", self.current_lang).format(scope_label, len(images)))
        self.log(tr("Training with Taxonomy ({0}): {1}", self.current_lang).format(len(tax), tax))
        self.log(tr("Training with Locator Scope ({0}): {1}", self.current_lang).format(len(locator_scope), locator_scope))
        self.log(describe_training_preflight(preflight))
        train_segmenter = not self.chk_train_locator_only.isChecked()
        if not train_segmenter and not preflight.get("locator_samples"):
            QMessageBox.warning(
                self,
                tr("Training", self.current_lang),
                tr("Locator stage skipped: no eligible locator samples.", self.current_lang),
            )
            return
        
        if len(locator_scope) != self.engine.current_num_classes:
            self.engine.rebuild_locator(len(locator_scope), self.train_lr, self.train_wd)

        if not self._show_structured_training_preflight(preflight):
            return

        if preflight.get("locator_samples"):
            self.ensure_locator_preloaded()
        if not self._confirm_legacy_locator_selection_if_needed():
            return
        if train_segmenter and preflight.get("parts_samples"):
            self.ensure_sam_preloaded()

        self._launch_training_with_preflight(
            preflight,
            tax,
            locator_scope,
            train_segmenter=train_segmenter,
            training_scope=scope_payload,
        )

    def _external_backend_runner(self):
        return ExternalBackendRunner(self.project, self._active_external_backend_config())

    def _sync_blink_lab_model_profile_defaults(self):
        if not hasattr(self, "blink_lab"):
            return
        child_defaults = _runtime_child_backend_defaults(self.project)
        train_params = child_defaults.get("train_params", {}) if isinstance(child_defaults.get("train_params"), dict) else {}
        heatmap_params = child_defaults.get("heatmap_params", {}) if isinstance(child_defaults.get("heatmap_params"), dict) else {}
        backend_type = child_defaults.get("backend_type") or CHILD_BACKEND_VIT_B
        input_size = child_defaults.get("input_size", self.blink_train_input_size)
        auto_shrink_steps = child_defaults.get("auto_shrink_steps", self.blink_auto_shrink_steps)
        training_strategy = sanitize_blink_training_strategy(
            child_defaults.get("training_strategy"),
            DEFAULT_BLINK_TRAINING_STRATEGY,
        )
        if backend_type == CHILD_BACKEND_HEATMAP:
            input_size = heatmap_params.get("input_size", input_size)
        self.blink_lab.set_training_defaults(
            train_params.get("epochs", self.blink_train_epochs),
            train_params.get("batch", self.blink_train_batch),
            train_params.get("lr", self.blink_train_lr),
            train_params.get("weight_decay", self.blink_train_weight_decay),
            input_size,
            self.runtime_device,
            trainer_backend=backend_type,
            heatmap_params=heatmap_params,
            auto_shrink_steps=auto_shrink_steps,
            training_strategy=training_strategy,
        )

    def run_external_training(self):
        self._flush_pending_project_save(defer_for_navigation=False)
        if getattr(self, "external_training_thread", None) is not None and self.external_training_thread.isRunning():
            self.log(tr("Training already running...", self.current_lang))
            return
        if self._is_child_training_running():
            self.log(tr("Child-part expert training is running. Wait for it to finish before training parent models.", self.current_lang))
            QMessageBox.information(
                self,
                tr("Training", self.current_lang),
                tr("Child-part expert training is running. Wait for it to finish before training parent models.", self.current_lang),
            )
            return
        if not self.project.current_project_path:
            QMessageBox.warning(self, tr("Training", self.current_lang), tr("Save Project", self.current_lang))
            return

        self.external_training_failed = False
        self.active_training_kind = "parent"
        self.btn_train.setEnabled(False)
        self.btn_stop_training.setEnabled(False)
        self._set_training_progress("parent", tr("Parent-part model training", self.current_lang), 0)
        thread = ExternalTrainingThread(self.project, self._active_external_backend_config())
        self.external_training_thread = thread

        def on_success(summary):
            self._set_training_progress("parent", tr("Parent-part model training finished.", self.current_lang), 100)
            self.log(f"External training complete. Contract: {summary.get('contract_json')}")
            self.log(f"External model manifest: {summary.get('model_manifest')}")

        def on_error(message):
            self.external_training_failed = True
            self._set_training_progress("parent", tr("Parent-part model training failed.", self.current_lang), self.progress.value())
            self.log(f"External training failed: {message}")
            QMessageBox.critical(self, tr("Error", self.current_lang), str(message))

        def on_finished():
            if not getattr(self, "external_training_failed", False):
                self._set_training_progress("parent", tr("Parent-part model training finished.", self.current_lang), 100)
            if getattr(self, "external_training_thread", None) is thread:
                self.external_training_thread = None
            thread.deleteLater()
            self.btn_train.setEnabled(True)
            self.btn_stop_training.setEnabled(False)
            self._refresh_blink_refine_state()

        thread.log_signal.connect(self.log)
        thread.success_signal.connect(on_success)
        thread.error_signal.connect(on_error)
        thread.finished_signal.connect(on_finished)
        thread.start()

    def show_training_report(self, report_data):
        dlg = TrainingReportDialog(report_data, self, self.current_lang)
        dlg.exec()

    def _candidate_training_experiment_dirs(self):
        roots = []

        weights_dir = getattr(self.engine, "weights_dir", "")
        if weights_dir:
            roots.append(os.path.join(os.path.dirname(os.path.abspath(weights_dir)), "experiments"))

        project_path = getattr(self.project, "current_project_path", "") or ""
        if project_path:
            project_root = os.path.dirname(os.path.abspath(project_path))
            roots.append(os.path.join(project_root, "experiments"))
            roots.append(os.path.join(os.path.dirname(project_root), "experiments"))

        roots.append(os.path.join(PACKAGE_DIR, "experiments"))

        seen = set()
        clean_roots = []
        for root in roots:
            if not root:
                continue
            root_abs = os.path.abspath(root)
            if root_abs in seen:
                continue
            seen.add(root_abs)
            clean_roots.append(root_abs)
        return clean_roots

    def _resolve_report_artifact_path(self, report_dir, summary, summary_key, fallback_name=None):
        value = summary.get(summary_key) if isinstance(summary, dict) else None
        if isinstance(value, str) and value.strip():
            candidate = value.strip()
            if not os.path.isabs(candidate):
                candidate = os.path.join(report_dir, candidate)
            return candidate
        if fallback_name:
            return os.path.join(report_dir, fallback_name)
        return None

    def _training_report_time_label(self, report_dir):
        name = os.path.basename(os.path.normpath(report_dir))
        match = re.search(r"(\d{8})_(\d{6})", name)
        if match:
            date_value, time_value = match.groups()
            return f"{date_value[0:4]}-{date_value[4:6]}-{date_value[6:8]} {time_value[0:2]}:{time_value[2:4]}:{time_value[4:6]}"
        try:
            timestamp = os.path.getmtime(report_dir)
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
        except Exception:
            return tr("Unknown time", self.current_lang)

    def _training_report_payload_from_summary(self, report_dir, summary_path):
        try:
            with open(summary_path, "r", encoding="utf-8") as handle:
                summary = json.load(handle)
        except Exception:
            return None
        if not isinstance(summary, dict):
            return None

        dir_name = os.path.basename(os.path.normpath(report_dir))
        kind = str(summary.get("kind") or "").strip()
        is_child = kind in {"blink_expert_report", "heatmap_blink_expert_report"} or dir_name.startswith(("blink_", "heatmap_blink_"))
        report_type = "child" if is_child else "parent"
        if is_child:
            target = str(summary.get("part_name") or "").strip() or tr("Unknown target", self.current_lang)
            parent_part = str(summary.get("parent_part") or "").strip()
            target_label = f"{parent_part} -> {target}" if parent_part else target
            backend_label = tr("Heatmap Blink Expert", self.current_lang) if kind.startswith("heatmap") or dir_name.startswith("heatmap_blink_") else tr("ViT-B Blink Expert", self.current_lang)
            strategy = (
                summary.get("training_strategy")
                or (summary.get("train_params") if isinstance(summary.get("train_params"), dict) else {}).get("training_strategy")
                or (summary.get("manifest") if isinstance(summary.get("manifest"), dict) else {}).get("training_strategy")
            )
        else:
            context = summary.get("training_context") if isinstance(summary.get("training_context"), dict) else {}
            locator_scope = context.get("locator_scope") if isinstance(context.get("locator_scope"), list) else []
            target_label = ", ".join(str(part) for part in locator_scope) if locator_scope else tr("Parent-part model training", self.current_lang)
            backend_label = _parent_backend_label(context.get("parent_backend", PARENT_BACKEND_BUILTIN), self.current_lang)
            strategy = "locator-only" if context.get("train_segmenter") is False else ""

        if is_child and strategy:
            strategy_label = blink_training_strategy_label(strategy, self.current_lang)
        elif (not is_child) and strategy == "locator-only":
            strategy_label = tr("Train Locator only (skip SAM)", self.current_lang)
        else:
            strategy_label = str(strategy or "")
        validation_count = summary.get("validation_count", "")
        try:
            samples_label = str(int(validation_count))
        except Exception:
            samples_label = str(validation_count or "")

        metrics_path = self._resolve_report_artifact_path(report_dir, summary, "metrics_plot", "metrics_plot.png")
        val_path = self._resolve_report_artifact_path(report_dir, summary, "validation_summary_image", "validation_samples.png")
        validation_index_path = self._resolve_report_artifact_path(report_dir, summary, "validation_index_csv", "validation_index.csv")
        details_dir = self._resolve_report_artifact_path(report_dir, summary, "validation_details_dir", "val_details")

        report = {
            "report_type": report_type,
            "type_label": tr("Child-part", self.current_lang) if is_child else tr("Parent-part", self.current_lang),
            "target_label": target_label,
            "backend_label": backend_label,
            "strategy_label": strategy_label,
            "samples_label": samples_label,
            "time_label": self._training_report_time_label(report_dir),
            "dir": report_dir,
            "csv": self._resolve_report_artifact_path(report_dir, summary, "training_log_csv", "training_log.csv"),
            "metrics": metrics_path if metrics_path and os.path.exists(metrics_path) else metrics_path,
            "val": val_path if val_path and os.path.exists(val_path) else val_path,
            "validation_index": validation_index_path,
            "report_summary": summary_path,
            "validation_summary": summary,
            "details_dir": details_dir,
            "model_path": summary.get("model_path", ""),
        }
        return report

    def discover_training_reports(self):
        reports = []
        seen_dirs = set()
        for experiments_root in self._candidate_training_experiment_dirs():
            if not os.path.isdir(experiments_root):
                continue
            try:
                entries = sorted(os.scandir(experiments_root), key=lambda entry: entry.name.lower())
            except Exception:
                continue
            for entry in entries:
                if not entry.is_dir():
                    continue
                report_dir = os.path.abspath(entry.path)
                if report_dir in seen_dirs:
                    continue
                summary_path = os.path.join(report_dir, "report_summary.json")
                if not os.path.exists(summary_path):
                    continue
                report = self._training_report_payload_from_summary(report_dir, summary_path)
                if not report:
                    continue
                seen_dirs.add(report_dir)
                reports.append(report)
        reports.sort(key=lambda item: item.get("time_label", ""), reverse=True)
        return reports

    def open_training_report_payload(self, report):
        if not isinstance(report, dict):
            return
        if report.get("report_type") == "child":
            dlg = BlinkExpertTrainingReportDialog(report, self.current_lang, self)
        else:
            dlg = TrainingReportDialog(report, self, self.current_lang)
        dlg.exec()

    def open_training_results_browser(self):
        reports = self.discover_training_reports()
        if not reports:
            QMessageBox.information(
                self,
                tr("Training Results", self.current_lang),
                tr("No training reports found.", self.current_lang),
            )
            return
        dlg = TrainingResultBrowserDialog(
            reports,
            parent=self,
            lang=self.current_lang,
            preview_callback=self.open_training_report_payload,
            refresh_callback=self.discover_training_reports,
        )
        dlg.exec()

    def _extract_prediction_payload(self, payload):
        """兼容新旧推理输出协议，统一返回 polygons + auto_boxes。"""
        polygons = {}
        auto_boxes = {}
        taxonomy_set = set(self.project.project_data.get("taxonomy", []))

        if not isinstance(payload, dict):
            return polygons, auto_boxes

        # 新协议: {polygons: {...}, auto_boxes: {...}}
        if isinstance(payload.get("polygons"), dict):
            polygons = {
                str(part): points
                for part, points in payload.get("polygons", {}).items()
                if str(part) in taxonomy_set
            }
            raw_auto_boxes = payload.get("auto_boxes", {}) if isinstance(payload.get("auto_boxes"), dict) else {}
            auto_boxes = {
                str(part): box
                for part, box in raw_auto_boxes.items()
                if str(part) in taxonomy_set
            }
            return polygons, auto_boxes

        # 旧协议回退: {part: polygon, part_BOX: box_polygon}
        for key, value in payload.items():
            if key.endswith("_BOX") and isinstance(value, list):
                xs = [p[0] for p in value if isinstance(p, (list, tuple)) and len(p) >= 2]
                ys = [p[1] for p in value if isinstance(p, (list, tuple)) and len(p) >= 2]
                if xs and ys:
                    real_part = key.replace("_BOX", "")
                    auto_boxes[real_part] = [float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))]
            elif isinstance(value, list):
                if key in taxonomy_set:
                    polygons[key] = value

        return polygons, auto_boxes

    def _is_unconfirmed_ai_draft(self, image_path, part_name):
        entry = self.project.project_data.get("labels", {}).get(image_path, {})
        if not isinstance(entry, dict):
            return False
        descriptions = entry.get("descriptions", {}) if isinstance(entry.get("descriptions", {}), dict) else {}
        if descriptions.get(part_name) != "Auto-Annotated":
            return False
        meta = entry.get("auto_box_meta", {}) if isinstance(entry.get("auto_box_meta", {}), dict) else {}
        review_status = ""
        if isinstance(meta.get(part_name), dict):
            review_status = str(meta.get(part_name, {}).get("review_status") or "").strip()
        return review_status != "confirmed"

    def _auto_box_meta_for_part(self, image_path, part_name):
        get_meta = getattr(self.project, "get_auto_box_meta", None)
        meta = None
        if callable(get_meta):
            try:
                meta = get_meta(image_path)
            except Exception:
                meta = None
        if not isinstance(meta, dict):
            entry = self.project.project_data.get("labels", {}).get(image_path, {})
            meta = entry.get("auto_box_meta", {}) if isinstance(entry, dict) and isinstance(entry.get("auto_box_meta", {}), dict) else {}
        part_meta = meta.get(part_name, {}) if isinstance(meta.get(part_name), dict) else {}
        return dict(part_meta)

    def _auto_box_source_for_part(self, image_path, part_name):
        meta = self._auto_box_meta_for_part(image_path, part_name)
        return str(meta.get("source") or AUTO_BOX_SOURCE_MODEL).strip() or AUTO_BOX_SOURCE_MODEL

    def _auto_box_review_status_for_part(self, image_path, part_name):
        meta = self._auto_box_meta_for_part(image_path, part_name)
        return str(meta.get("review_status") or AUTO_BOX_REVIEW_DRAFT).strip() or AUTO_BOX_REVIEW_DRAFT

    def _auto_annotation_source_meta(self, source=AUTO_BOX_SOURCE_MODEL):
        return {
            "source": source,
            "review_status": AUTO_BOX_REVIEW_DRAFT,
        }

    def _can_replace_existing_auto_annotation(self, image_path, part_name, new_source):
        existing_points = self.project.get_labels(image_path).get(part_name, [])
        if existing_points and not self._is_unconfirmed_ai_draft(image_path, part_name):
            return False
        existing_auto_boxes = self.project.get_auto_boxes(image_path)
        has_auto_box = isinstance(existing_auto_boxes, dict) and part_name in existing_auto_boxes
        if not existing_points and not has_auto_box:
            return True
        existing_status = self._auto_box_review_status_for_part(image_path, part_name)
        if existing_status == AUTO_BOX_REVIEW_CONFIRMED:
            return False
        existing_source = self._auto_box_source_for_part(image_path, part_name)
        if new_source == AUTO_BOX_SOURCE_VLM:
            return existing_source == AUTO_BOX_SOURCE_VLM
        return True

    def _apply_prediction_to_project(self, image_path, payload, only_new=True, save=True, source=AUTO_BOX_SOURCE_MODEL):
        polygons, auto_boxes = self._extract_prediction_payload(payload)
        existing_parts = set(self.project.get_labels(image_path).keys())
        saved_count = 0

        for part_name, points in polygons.items():
            if only_new and not self._can_replace_existing_auto_annotation(image_path, part_name, source):
                continue

            auto_box = auto_boxes.get(part_name)
            if (not auto_box) and isinstance(points, list) and points:
                xs = [pt[0] for pt in points if isinstance(pt, (list, tuple)) and len(pt) >= 2]
                ys = [pt[1] for pt in points if isinstance(pt, (list, tuple)) and len(pt) >= 2]
                if xs and ys:
                    auto_box = [float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))]

            self.project.update_label(image_path, part_name, points, "Auto-Annotated", auto_box=auto_box, save=False)
            if auto_box:
                update_auto_box = getattr(self.project, "update_auto_box", None)
                if callable(update_auto_box):
                    update_auto_box(
                        image_path,
                        part_name,
                        auto_box,
                        source_meta=self._auto_annotation_source_meta(source),
                        save=False,
                    )
            existing_parts.add(part_name)
            saved_count += 1

        if saved_count and save:
            self.project.save_project()
        return saved_count, len(polygons)

    def _vlm_api_settings_path(self):
        pdf_widget = getattr(self, "pdf_widget", None)
        if pdf_widget is not None and getattr(pdf_widget, "api_settings_file", ""):
            return pdf_widget.api_settings_file
        return os.path.join(REPO_ROOT, "screener_configs", "api_runtime_settings.json")

    def _vlm_api_config_from_pdf_widget(self):
        pdf_widget = getattr(self, "pdf_widget", None)
        if pdf_widget is None:
            return {}

        def text(widget_name):
            widget = getattr(pdf_widget, widget_name, None)
            if widget is None or not hasattr(widget, "text"):
                return ""
            try:
                return widget.text().strip()
            except Exception:
                return ""

        def current_data(widget_name, fallback="auto"):
            widget = getattr(pdf_widget, widget_name, None)
            if widget is None or not hasattr(widget, "currentData"):
                return fallback
            try:
                return widget.currentData() or fallback
            except Exception:
                return fallback

        same_widget = getattr(pdf_widget, "check_mllm_same_as_text", None)
        use_same = bool(same_widget.isChecked()) if same_widget is not None and hasattr(same_widget, "isChecked") else True
        if use_same:
            return {
                "api_key": text("edit_api_key"),
                "base_url": text("edit_base_url"),
                "model": text("edit_model"),
                "api_protocol": current_data("combo_api_protocol"),
                "image_detail": current_data("combo_mllm_image_detail"),
            }
        return {
            "api_key": text("edit_mllm_api_key"),
            "base_url": text("edit_mllm_base_url"),
            "model": text("edit_mllm_model"),
            "api_protocol": current_data("combo_mllm_api_protocol"),
            "image_detail": current_data("combo_mllm_image_detail"),
        }

    def _vlm_preannotation_artifacts_dir(self):
        project_path = getattr(self.project, "current_project_path", "") or ""
        if project_path:
            base_dir = os.path.join(os.path.dirname(os.path.abspath(project_path)), "vlm_preannotation")
        else:
            base_dir = self._default_vlm_preannotation_dir()
        os.makedirs(base_dir, exist_ok=True)
        return base_dir

    def _current_vlm_target_parts(self):
        if hasattr(self.project, "get_vlm_preannotation_target_parts"):
            return self.project.get_vlm_preannotation_target_parts()
        return []

    def _current_vlm_processing_scope(self):
        if hasattr(self.project, "get_vlm_preannotation_settings"):
            return self.project.get_vlm_preannotation_settings().get("processing_scope", "current_image")
        return "current_image"

    def _current_vlm_batch_scope(self):
        scope = self._current_vlm_processing_scope()
        return scope if scope in {"all_images", "image_group"} else "image_group"

    def _current_vlm_image_group(self):
        if hasattr(self.project, "get_vlm_preannotation_settings"):
            return self.project.get_vlm_preannotation_settings().get("image_group", "split")
        return "split"

    def _current_vlm_concurrency(self):
        if hasattr(self.project, "get_vlm_preannotation_settings"):
            settings = self.project.get_vlm_preannotation_settings()
            try:
                return max(1, min(8, int(settings.get("concurrency", 1) or 1)))
            except Exception:
                return 1
        return 1

    def _current_vlm_prompt_profile(self):
        if hasattr(self.project, "get_vlm_preannotation_settings"):
            settings = self.project.get_vlm_preannotation_settings()
            return sanitize_vlm_prompt_profile(settings.get("prompt_profile", {}))
        return default_vlm_prompt_profile()

    def _vlm_image_group_label(self, group_key):
        return self._image_group_display_name(group_key)

    def _panel_crop_identity_index(self, images, provenance_by_image=None):
        provenance_by_image = provenance_by_image or {}
        image_identities = {}
        stem_dir_index = set()
        stem_identity_index = {}
        split_crop_identities = set()
        source_with_crops = set()
        for img in images or []:
            if not img:
                continue
            try:
                identity = os.path.normcase(os.path.normpath(os.path.abspath(str(img))))
            except Exception:
                identity = str(img)
            image_identities[img] = identity
            try:
                directory = os.path.normcase(os.path.abspath(os.path.dirname(str(img))))
                stem = os.path.normcase(os.path.splitext(os.path.basename(str(img)))[0])
                stem_dir_index.add((directory, stem))
                stem_identity_index.setdefault((directory, stem), identity)
            except Exception:
                pass

        for img in images or []:
            if not img:
                continue
            identity = image_identities.get(img, "")
            provenance = provenance_by_image.get(img, {})
            derived_from = provenance.get("derived_from") if isinstance(provenance, dict) else {}
            if isinstance(derived_from, dict) and bool(derived_from.get("image_path")):
                split_crop_identities.add(identity)
                try:
                    source_identity = os.path.normcase(
                        os.path.normpath(os.path.abspath(str(derived_from.get("image_path"))))
                    )
                    source_with_crops.add(source_identity)
                except Exception:
                    pass
                continue

            base_name = os.path.basename(str(img))
            if not re.search(r"__(?:panel|crop)_\d{3}(?:_\d+)?\.(?:png|jpe?g|tif|tiff)$", base_name, re.IGNORECASE):
                continue
            try:
                crop_dir = os.path.normcase(os.path.abspath(os.path.dirname(str(img))))
                crop_stem = os.path.splitext(base_name)[0]
                source_stem = re.sub(r"__(?:panel|crop)_\d{3}(?:_\d+)?$", "", crop_stem, flags=re.IGNORECASE)
                source_key = (crop_dir, os.path.normcase(source_stem))
                if source_key in stem_dir_index:
                    split_crop_identities.add(identity)
                    source_identity = stem_identity_index.get(source_key)
                    if source_identity and source_identity != identity:
                        source_with_crops.add(source_identity)
            except Exception:
                continue

        return image_identities, split_crop_identities, source_with_crops

    def _project_image_groups(self, images=None, labeled_images=None):
        groups = {group_id: [] for group_id, _label in self._all_image_group_definitions()}
        images = [img for img in (images if images is not None else self.project.project_data.get("images", [])) if img]
        image_order = {img: index for index, img in enumerate(images)}
        provenance_by_image = {
            img: self.project.get_image_provenance(img)
            for img in images
            if hasattr(self.project, "get_image_provenance")
        }
        image_identities, split_crop_identities, source_with_crops = self._panel_crop_identity_index(
            images,
            provenance_by_image=provenance_by_image,
        )
        if labeled_images is None:
            labeled_images = {
                img
                for img in images
                if bool(self.project.get_labels(img) or self.project.get_auto_boxes(img))
            }
        else:
            labeled_images = set(labeled_images or [])

        def sort_group_items(items):
            return sorted(
                list(items or []),
                key=lambda path: (0 if path in labeled_images else 1, image_order.get(path, len(image_order))),
            )

        for img in images:
            if not img:
                continue
            provenance = provenance_by_image.get(img, {})
            manual_group = str(provenance.get("manual_image_group", "") or "").strip() if isinstance(provenance, dict) else ""
            if manual_group and manual_group in groups:
                groups[manual_group].append(img)
                continue
            identity = image_identities.get(img, "")
            is_labeled = img in labeled_images
            is_split_crop = identity in split_crop_identities
            is_hard_candidate_crop = is_split_crop and self._is_hard_joined_candidate_crop(img, provenance=provenance)
            review = provenance.get("panel_split_review") if isinstance(provenance, dict) else {}
            review_status = review.get("status") if isinstance(review, dict) else ""
            needs_manual_split = (not is_split_crop) and identity not in source_with_crops and review_status == "manual_required"
            manual_split_done = (not is_split_crop) and review_status == "manual_done"
            if needs_manual_split:
                groups.setdefault("manual", []).append(img)
            elif is_hard_candidate_crop:
                groups.setdefault("hard_candidates", []).append(img)
            elif is_split_crop:
                groups.setdefault("split", []).append(img)
            elif manual_split_done:
                groups.setdefault("manual_done", []).append(img)
            else:
                groups.setdefault("original", []).append(img)
        for group_id in list(groups.keys()):
            groups[group_id] = sort_group_items(groups.get(group_id, []))
        return groups

    def _vlm_candidate_source_meta(self, candidate, result):
        return {
            "source": "vlm_first_mile",
            "review_status": "draft",
            "confidence": float(candidate.get("confidence", 0.0) or 0.0),
            "reason": str(candidate.get("reason", "") or ""),
            "source_model": str((getattr(self, "vlm_preannotation_api_config", {}) or {}).get("model", "") or ""),
            "source_run_id": str(getattr(self, "vlm_preannotation_run_id", "") or ""),
            "report_path": str(result.get("report_path", "") or ""),
        }

    def _record_sqlite_vlm_image_result(self, image_path, result, status, box_count=0, error_message=""):
        is_sqlite = getattr(self.project, "is_sqlite_project", lambda: False)
        if not callable(is_sqlite) or not is_sqlite():
            return
        run_id = str(getattr(self, "vlm_preannotation_run_id", "") or "")
        if not run_id:
            return
        try:
            record_vlm_image_result(
                self.project,
                run_id,
                image_path,
                status=status,
                error_message=error_message or str((result or {}).get("error", "") or ""),
                raw_response_ref=str((result or {}).get("report_path", "") or ""),
                box_count=int(box_count or 0),
            )
        except Exception:
            runtime_log_exception("sqlite_vlm_image_result_record_failed", *sys.exc_info())

    def _finish_sqlite_vlm_run(self, run_id, summary):
        is_sqlite = getattr(self.project, "is_sqlite_project", lambda: False)
        if not callable(is_sqlite) or not is_sqlite():
            return
        try:
            finish_vlm_run(
                self.project,
                run_id,
                status=str((summary or {}).get("status") or "finished"),
                summary=summary or {},
            )
        except Exception:
            runtime_log_exception("sqlite_vlm_run_finish_failed", *sys.exc_info())

    def _vlm_image_paths_for_scope(self, scope):
        if scope == "all_images":
            return [path for path in self.project.project_data.get("images", []) if path]
        if scope == "image_group":
            groups = self._project_image_groups()
            return list(groups.get(self._current_vlm_image_group(), []))
        return [self.current_image] if self.current_image else []

    def _vlm_image_paths_from_settings(self):
        return self._vlm_image_paths_for_scope(self._current_vlm_processing_scope())

    def _same_project_image_path(self, left, right):
        if not left or not right:
            return False
        to_absolute = getattr(self.project, "_to_absolute", None)
        try:
            left_path = to_absolute(left) if callable(to_absolute) else os.path.abspath(str(left))
            right_path = to_absolute(right) if callable(to_absolute) else os.path.abspath(str(right))
        except Exception:
            left_path = str(left)
            right_path = str(right)
        return os.path.normcase(os.path.normpath(left_path)) == os.path.normcase(os.path.normpath(right_path))

    def _project_image_key_for_path(self, image_path):
        for candidate in self.project.project_data.get("images", []):
            if self._same_project_image_path(candidate, image_path):
                return candidate
        return ""

    def _vlm_part_list_text(self, parts):
        clean_parts = []
        for part in parts or []:
            clean_part = str(part or "").strip()
            if clean_part and clean_part not in clean_parts:
                clean_parts.append(clean_part)
        return ", ".join(clean_parts) if clean_parts else tr("none", self.current_lang)

    def _vlm_part_coverage(self, result):
        requested = []
        for part in result.get("target_parts", []) or getattr(self, "vlm_preannotation_target_parts", []) or []:
            clean_part = str(part or "").strip()
            if clean_part and clean_part not in requested:
                requested.append(clean_part)

        returned = []
        for candidate in result.get("candidates", []) or []:
            if not isinstance(candidate, dict):
                continue
            clean_part = str(candidate.get("part", "") or "").strip()
            if clean_part and clean_part not in returned:
                returned.append(clean_part)

        returned_lookup = {part.lower(): part for part in returned}
        missing = [part for part in requested if part.lower() not in returned_lookup]
        return requested, returned, missing

    def _log_vlm_part_coverage(self, result):
        image_path = str(result.get("image_path", "") or "")
        image_name = os.path.basename(image_path) if image_path else tr("Current Image", self.current_lang)
        requested, returned, missing = self._vlm_part_coverage(result)
        self.log(
            tr(
                "VLM part coverage for {0}: requested [{1}]; returned [{2}]; missing [{3}].",
                self.current_lang,
            ).format(
                image_name,
                self._vlm_part_list_text(requested),
                self._vlm_part_list_text(returned),
                self._vlm_part_list_text(missing),
            )
        )

    def run_vlm_preannotation_current(self):
        self.run_vlm_preannotation_from_settings(scope_override="current_image")

    def run_vlm_preannotation_batch(self):
        self.run_vlm_preannotation_from_settings(scope_override=self._current_vlm_batch_scope())

    def run_vlm_preannotation_from_settings(self, scope_override=None):
        processing_scope = str(scope_override or self._current_vlm_processing_scope() or "current_image")
        if processing_scope == "current_image" and not self.current_image:
            QMessageBox.warning(self, tr("VLM Pre-Annotate", self.current_lang), tr("Please select an image first.", self.current_lang))
            return
        active_vlm_threads = [
            thread
            for thread in (getattr(self, "vlm_preannotation_threads", []) or [])
            if thread is not None and thread.isRunning()
        ]
        if active_vlm_threads or (self.vlm_preannotation_thread is not None and self.vlm_preannotation_thread.isRunning()):
            QMessageBox.information(self, tr("VLM Pre-Annotate", self.current_lang), tr("VLM preannotation is already running.", self.current_lang))
            return
        target_parts = self._current_vlm_target_parts()
        if not target_parts:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Warning)
            box.setWindowTitle(tr("VLM Pre-Annotate", self.current_lang))
            box.setText(tr("Select at least one VLM target part before running pre-annotation.", self.current_lang))
            open_button = box.addButton(tr("Open VLM settings", self.current_lang), QMessageBox.AcceptRole)
            box.addButton(QMessageBox.Cancel)
            box.exec()
            if box.clickedButton() == open_button:
                self.open_stl_model_settings(focus_vlm=True)
            return
        image_paths = self._vlm_image_paths_for_scope(processing_scope)
        if not image_paths:
            QMessageBox.warning(self, tr("VLM Pre-Annotate", self.current_lang), tr("Please select an image first.", self.current_lang))
            return
        vlm_concurrency = self._current_vlm_concurrency()
        concurrency_note = "\n\n" + tr(
            "VLM API concurrency: {0}. Increase this only if your provider allows parallel requests.",
            self.current_lang,
        ).format(vlm_concurrency)
        if processing_scope == "all_images":
            if themed_yes_no_question(
                self,
                tr("VLM Pre-Annotate", self.current_lang),
                tr(
                    "Run VLM preannotation on all imported images?\n\nThis will call the multimodal API, may incur provider cost, and will write draft AI boxes and SAM polygons for later review.",
                    self.current_lang,
                )
                + concurrency_note,
                confirm_role=BUTTON_ROLE_RUN,
            ) != QMessageBox.Yes:
                return
        elif processing_scope == "image_group":
            image_group = self._current_vlm_image_group()
            if themed_yes_no_question(
                self,
                tr("VLM Pre-Annotate", self.current_lang),
                tr(
                    "Run VLM preannotation on {0} image(s) in {1}?\n\nThis will call the multimodal API, may incur provider cost, and will write draft AI boxes and SAM polygons for later review.",
                    self.current_lang,
                ).format(len(image_paths), self._vlm_image_group_label(image_group))
                + concurrency_note,
                confirm_role=BUTTON_ROLE_RUN,
            ) != QMessageBox.Yes:
                return

        try:
            api_config = load_vlm_api_config_from_runtime_settings(self._vlm_api_settings_path())
            live_config = self._vlm_api_config_from_pdf_widget()
            for key, value in live_config.items():
                if value:
                    api_config[key] = value
        except Exception as exc:
            QMessageBox.warning(self, tr("VLM Pre-Annotate", self.current_lang), str(exc))
            return
        if not api_config.get("api_key") or not api_config.get("base_url") or not api_config.get("model"):
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Warning)
            box.setWindowTitle(tr("VLM Pre-Annotate", self.current_lang))
            box.setText(tr("Configure the Multimodal LLM API in PDF Evidence Tools first.", self.current_lang))
            open_button = box.addButton(tr("Open API settings", self.current_lang), QMessageBox.AcceptRole)
            box.addButton(QMessageBox.Cancel)
            box.exec()
            if box.clickedButton() == open_button:
                self.open_pdf_multimodal_api_settings()
            return

        self.vlm_preannotation_api_config = dict(api_config)
        for button_name in ("btn_vlm_preannotate_current", "btn_vlm_preannotate_batch", "btn_vlm_preannotate"):
            button = getattr(self, button_name, None)
            if button is not None:
                button.setEnabled(False)
        self.vlm_preannotation_saved_total = 0
        self.vlm_preannotation_run_id = time.strftime("%Y%m%d_%H%M%S")
        self.vlm_preannotation_records = []
        self.vlm_preannotation_queue = list(image_paths)
        self.vlm_preannotation_threads = []
        self.vlm_preannotation_run_active = True
        self.vlm_preannotation_cancel_requested = False
        self.vlm_preannotation_cancelled_queued_images = 0
        self.vlm_preannotation_concurrency = vlm_concurrency
        self.vlm_preannotation_total_steps = max(1, len(image_paths) * 6)
        self.vlm_preannotation_completed_steps = 0
        self.vlm_preannotation_total_images = len(image_paths)
        self.vlm_preannotation_completed_images = 0
        self.vlm_preannotation_current_image = ""
        self.vlm_preannotation_active_images = {}
        self.vlm_preannotation_image_step_counts = {}
        self.vlm_preannotation_completed_image_keys = set()
        self.vlm_preannotation_target_parts = list(target_parts)
        self.vlm_preannotation_artifacts_dir = self._vlm_preannotation_artifacts_dir()
        self.vlm_preannotation_api_config = dict(api_config)
        self.vlm_preannotation_prompt_profile = self._current_vlm_prompt_profile()
        runtime_log_event(
            "vlm_batch_begin",
            project=getattr(self.project, "current_project_path", ""),
            image_count=len(image_paths),
            target_count=len(target_parts),
            concurrency=vlm_concurrency,
            scope=processing_scope,
            run_id=self.vlm_preannotation_run_id,
            artifacts_dir=self.vlm_preannotation_artifacts_dir,
        )
        self._create_vlm_progress_dialog()
        self._set_vlm_progress_ui(0, "start")
        self.log(tr("VLM API concurrency: {0}. Increase this only if your provider allows parallel requests.", self.current_lang).format(self.vlm_preannotation_concurrency))
        self._start_vlm_preannotation_workers()

    def request_stop_vlm_preannotation(self, confirm=True):
        if not getattr(self, "vlm_preannotation_run_active", False):
            return False
        if confirm:
            message = (
                tr("Stop VLM preannotation after active request(s) finish?", self.current_lang)
                + "\n\n"
                + tr(
                    "Active API request(s) may already have been sent, but no more queued images will be processed. This helps avoid unintended large API bills.",
                    self.current_lang,
                )
            )
            if themed_yes_no_question(
                self,
                tr("VLM Pre-Annotate", self.current_lang),
                message,
                confirm_role=BUTTON_ROLE_STOP,
            ) != QMessageBox.Yes:
                return False
        queued = list(getattr(self, "vlm_preannotation_queue", []) or [])
        self.vlm_preannotation_cancel_requested = True
        self.vlm_preannotation_cancelled_queued_images = int(getattr(self, "vlm_preannotation_cancelled_queued_images", 0) or 0) + len(queued)
        self.vlm_preannotation_queue = []
        button = getattr(self, "vlm_preannotation_stop_button", None)
        if button is not None:
            button.setEnabled(False)
            button.setText(tr("Stopping after current image...", self.current_lang))
        self.log(
            tr(
                "VLM stop requested. Remaining queued images were cancelled; waiting for active request(s) to finish.",
                self.current_lang,
            )
        )
        self._set_vlm_progress_ui(
            int(
                int(getattr(self, "vlm_preannotation_completed_steps", 0) or 0)
                / max(1, int(getattr(self, "vlm_preannotation_total_steps", 1) or 1))
                * 100
            ),
            "cancelled",
        )
        return True

    def _active_vlm_preannotation_threads(self):
        active = []
        for thread in getattr(self, "vlm_preannotation_threads", []) or []:
            try:
                if thread is not None and thread.isRunning():
                    active.append(thread)
            except RuntimeError:
                continue
        self.vlm_preannotation_threads = active
        self.vlm_preannotation_thread = active[0] if active else None
        return active

    def _start_vlm_preannotation_workers(self):
        if not getattr(self, "vlm_preannotation_run_active", False):
            return
        if getattr(self, "vlm_preannotation_cancel_requested", False):
            return
        active = self._active_vlm_preannotation_threads()
        limit = max(1, min(8, int(getattr(self, "vlm_preannotation_concurrency", 1) or 1)))
        while len(active) < limit and getattr(self, "vlm_preannotation_queue", []):
            thread = self._start_next_vlm_preannotation_image()
            if thread is None:
                break
            active.append(thread)
        self.vlm_preannotation_threads = active
        self.vlm_preannotation_thread = active[0] if active else None

    def _start_next_vlm_preannotation_image(self):
        queue = list(getattr(self, "vlm_preannotation_queue", []) or [])
        if not queue:
            if not self._active_vlm_preannotation_threads():
                self._finish_vlm_preannotation_run()
            return None
        image_path = queue.pop(0)
        self.vlm_preannotation_queue = queue
        self.vlm_preannotation_current_image_steps_completed = 0
        self.vlm_preannotation_current_image = image_path
        runtime_log_event(
            "vlm_worker_starting",
            image=os.path.basename(str(image_path)),
            queued=len(queue),
            run_id=getattr(self, "vlm_preannotation_run_id", ""),
        )
        self._set_vlm_progress_ui(
            int(int(getattr(self, "vlm_preannotation_completed_steps", 0) or 0) / max(1, int(getattr(self, "vlm_preannotation_total_steps", 1) or 1)) * 100),
            "image",
        )
        thread = VlmPreannotationThread(
            image_path,
            getattr(self, "vlm_preannotation_target_parts", []),
            getattr(self, "vlm_preannotation_artifacts_dir", self._vlm_preannotation_artifacts_dir()),
            getattr(self, "vlm_preannotation_api_config", {}),
            getattr(self, "vlm_preannotation_run_id", time.strftime("%Y%m%d_%H%M%S")),
            grid_cols=None,
            grid_rows=None,
            min_confidence=0.25,
            prompt_profile=getattr(self, "vlm_preannotation_prompt_profile", default_vlm_prompt_profile()),
        )
        self.vlm_preannotation_thread = thread
        active_images = getattr(self, "vlm_preannotation_active_images", None)
        if not isinstance(active_images, dict):
            active_images = {}
            self.vlm_preannotation_active_images = active_images
        step_counts = getattr(self, "vlm_preannotation_image_step_counts", None)
        if not isinstance(step_counts, dict):
            step_counts = {}
            self.vlm_preannotation_image_step_counts = step_counts
        active_images[thread] = image_path
        step_counts[self._vlm_progress_image_key(image_path)] = 0
        thread.log_signal.connect(self.log)
        thread.image_result_signal.connect(self._on_vlm_preannotation_image_result)
        thread.progress_signal.connect(lambda completed, total, step_name, worker=thread: self._on_vlm_preannotation_thread_step(worker, completed, total, step_name))
        thread.error_signal.connect(self._on_vlm_preannotation_error)
        native_finished = getattr(thread, "finished", None)
        if native_finished is not None and hasattr(native_finished, "connect"):
            native_finished.connect(lambda worker=thread: self._on_vlm_preannotation_qthread_finished(worker))
        else:
            thread.finished_signal.connect(lambda worker=thread: self._on_vlm_preannotation_qthread_finished(worker))
        thread.start()
        return thread

    def _apply_vlm_candidate(self, image_path, image_rgb, candidate, result):
        part_name = str(candidate.get("part", "") or "").strip()
        box = _clean_box(candidate.get("box_xyxy"))
        if not part_name or not box:
            return False, "invalid_candidate"

        if not self._can_replace_existing_auto_annotation(image_path, part_name, AUTO_BOX_SOURCE_VLM):
            return False, "already_labeled"

        polygon = None
        try:
            polygon = self.engine.predict_base_sam_polygon(image_rgb, box, poly_epsilon=self.inf_poly_epsilon)
        except Exception as exc:
            self.log(tr("SAM draft failed for {0}: {1}", self.current_lang).format(part_name, str(exc)))

        if polygon and len(polygon) >= 3:
            self.project.update_label(
                image_path,
                part_name,
                polygon,
                "Auto-Annotated",
                auto_box=box,
                save=False,
            )
            update_auto_box = getattr(self.project, "update_auto_box", None)
            if callable(update_auto_box):
                update_auto_box(
                    image_path,
                    part_name,
                    box,
                    source_meta=self._vlm_candidate_source_meta(candidate, result),
                    save=False,
                )
            return True, "polygon"

        update_auto_box = getattr(self.project, "update_auto_box", None)
        if callable(update_auto_box):
            update_auto_box(
                image_path,
                part_name,
                box,
                description_text="Auto-Annotated",
                source_meta=self._vlm_candidate_source_meta(candidate, result),
                save=False,
            )
        else:
            self.project.update_label(image_path, part_name, [], "Auto-Annotated", auto_box=box, save=False)
        return True, "box_only"

    def _refresh_vlm_canvas_if_current(self, image_path):
        if self._same_project_image_path(image_path, self.current_image):
            self.canvas.set_polygons(self.project.get_labels(image_path))
            self._refresh_current_canvas_boxes()
            self.canvas.update()
            self.canvas.repaint()

    def _reload_current_image_for_workbench(self):
        if not self.current_image:
            return False
        current_path = self._project_image_key_for_path(self.current_image)
        if not current_path:
            return False
        self.current_image = current_path
        if hasattr(self, "canvas"):
            has_loaded_pixmap = bool(self.canvas.original_pixmap and not self.canvas.original_pixmap.isNull())
            if not has_loaded_pixmap:
                self.canvas.load_image(current_path)
                self.on_enhancement_changed()
            self.canvas.set_polygons(self.project.get_labels(current_path))
            self._refresh_current_canvas_boxes()
            self.canvas.update()
            self.canvas.repaint()
        get_taxon = getattr(self.project, "get_taxon", self.project.get_genus)
        if hasattr(self, "genus_combo"):
            self.genus_combo.blockSignals(True)
            try:
                self.genus_combo.setCurrentText(get_taxon(current_path))
            finally:
                self.genus_combo.blockSignals(False)
        if hasattr(self, "blink_lab"):
            try:
                self.blink_lab.refresh_from_workbench(
                    current_path,
                    self.project.get_labels(current_path),
                    self.project.get_boxes(current_path),
                    self._auto_boxes_for_canvas(current_path)[0],
                )
            except Exception:
                pass
        return True

    def _on_vlm_preannotation_image_result(self, result):
        image_path = str(result.get("image_path", "") or "")
        runtime_log_event(
            "vlm_image_result_begin",
            image=os.path.basename(str(image_path)),
            status=result.get("status", ""),
            candidate_count=len(result.get("candidates", []) or []) if isinstance(result, dict) else 0,
            run_id=getattr(self, "vlm_preannotation_run_id", ""),
        )
        if not image_path or result.get("status") == "failed":
            self._log_vlm_part_coverage(result)
            self.log(tr("VLM first-mile preannotation failed: {0}", self.current_lang).format(result.get("error", "")))
            self._complete_current_vlm_image_steps("failed", image_path=image_path)
            self.vlm_preannotation_records.append(result)
            if image_path:
                self._record_sqlite_vlm_image_result(
                    image_path,
                    result,
                    "failed",
                    box_count=0,
                    error_message=str(result.get("error", "") or ""),
                )
            self._mark_current_vlm_image_done("failed", image_path=image_path)
            return
        candidates = list(result.get("candidates", []) or []) if isinstance(result, dict) else []
        if not candidates:
            self._log_vlm_part_coverage(result)
            self.log(tr("VLM first-mile preannotation returned no usable boxes.", self.current_lang))
            self._complete_current_vlm_image_steps("no_candidates", image_path=image_path)
            self.vlm_preannotation_records.append(result)
            self._record_sqlite_vlm_image_result(image_path, result, "no_candidates", box_count=0)
            self._mark_current_vlm_image_done("no_candidates", image_path=image_path)
            return
        try:
            project_image_path = self._project_image_key_for_path(image_path)
            if not project_image_path:
                raise RuntimeError(
                    tr(
                        "VLM result image is not registered in the current project: {0}",
                        self.current_lang,
                    ).format(image_path)
                )
            image_bgr = cv2.imread(image_path)
            if image_bgr is None:
                raise RuntimeError(tr("Could not read the current image.", self.current_lang))
            image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
            saved = 0
            polygon_count = 0
            box_only_count = 0
            skipped = 0
            for candidate in candidates:
                ok, mode = self._apply_vlm_candidate(project_image_path, image_rgb, candidate, result)
                if ok:
                    saved += 1
                    if mode == "polygon":
                        polygon_count += 1
                    elif mode == "box_only":
                        box_only_count += 1
                else:
                    skipped += 1
            self.vlm_preannotation_saved_total = int(getattr(self, "vlm_preannotation_saved_total", 0)) + saved
            is_sqlite = getattr(self.project, "is_sqlite_project", lambda: False)
            if callable(is_sqlite) and is_sqlite():
                self.project.flush_sqlite_changes(image_paths=[project_image_path], project_dirty=True)
            else:
                self._schedule_project_save(
                    reason="vlm_preannotation",
                    image=os.path.basename(str(project_image_path)),
                    saved_count=saved,
                )
            self._refresh_vlm_canvas_if_current(project_image_path)
            self._refresh_image_list_status_or_rebuild(project_image_path)
            self._reload_current_image_for_workbench()
            self._refresh_blink_refine_state()
            report_path = result.get("report_path", "")
            result["saved_box_count"] = saved
            result["saved_polygon_count"] = polygon_count
            result["saved_box_only_count"] = box_only_count
            result["skipped_count"] = skipped
            self.vlm_preannotation_records.append(result)
            self._record_sqlite_vlm_image_result(project_image_path, result, "done", box_count=saved)
            self._advance_vlm_progress("write", image_path=image_path)
            self._advance_vlm_progress("sam", image_path=image_path)
            self._advance_vlm_progress("report", image_path=image_path)
            self._mark_current_vlm_image_done("done", image_path=image_path)
            self._log_vlm_part_coverage(result)
            self.log(
                tr(
                    "VLM preannotation saved {0} draft(s): {1} SAM polygon(s), {2} box-only draft(s), skipped {3}. Report: {4}",
                    self.current_lang,
                ).format(saved, polygon_count, box_only_count, skipped, report_path)
            )
            runtime_log_event(
                "vlm_image_result_saved",
                image=os.path.basename(str(project_image_path)),
                saved=saved,
                polygon_count=polygon_count,
                box_only_count=box_only_count,
                skipped=skipped,
                run_id=getattr(self, "vlm_preannotation_run_id", ""),
            )
        except Exception as exc:
            runtime_log_exception("vlm_image_result_apply_failed", *sys.exc_info())
            self._complete_current_vlm_image_steps("failed", image_path=image_path)
            failed = dict(result)
            failed["status"] = "failed"
            failed["error"] = str(exc)
            self.vlm_preannotation_records.append(failed)
            self._record_sqlite_vlm_image_result(image_path, failed, "failed", box_count=0, error_message=str(exc))
            self._mark_current_vlm_image_done("failed", image_path=image_path)
            self._on_vlm_preannotation_error(str(exc))

    def _vlm_progress_image_key(self, image_path):
        if not image_path:
            return ""
        try:
            return os.path.normcase(os.path.normpath(os.path.abspath(str(image_path))))
        except Exception:
            return str(image_path)

    def _mark_current_vlm_image_done(self, step_name, image_path=None):
        image_key = self._vlm_progress_image_key(image_path)
        completed_keys = getattr(self, "vlm_preannotation_completed_image_keys", set())
        if not isinstance(completed_keys, set):
            completed_keys = set(completed_keys or [])
        if image_key and image_key in completed_keys:
            return
        if image_key:
            completed_keys.add(image_key)
        self.vlm_preannotation_completed_image_keys = completed_keys
        total_images = max(1, int(getattr(self, "vlm_preannotation_total_images", 1) or 1))
        self.vlm_preannotation_completed_images = min(
            total_images,
            int(getattr(self, "vlm_preannotation_completed_images", 0) or 0) + 1,
        )
        if image_path:
            self.vlm_preannotation_current_image = str(image_path)
        total_steps = max(1, int(getattr(self, "vlm_preannotation_total_steps", 1) or 1))
        completed_steps = int(getattr(self, "vlm_preannotation_completed_steps", 0) or 0)
        self._set_vlm_progress_ui(int(completed_steps / total_steps * 100), step_name)

    def _set_vlm_progress_ui(self, percent, step_name):
        total_images = max(1, int(getattr(self, "vlm_preannotation_total_images", 1) or 1))
        completed_images = min(total_images, int(getattr(self, "vlm_preannotation_completed_images", 0) or 0))
        current_image = str(getattr(self, "vlm_preannotation_current_image", "") or "")
        step_label = tr(str(step_name or ""), self.current_lang)
        percent = max(0, min(100, int(percent)))
        label = tr("VLM progress: {0}% ({1}/{2}) {3}", self.current_lang).format(
            percent,
            completed_images,
            total_images,
            step_label,
        )
        progress = getattr(self, "vlm_preannotation_progress_dialog", None)
        if progress is not None:
            label_widget = getattr(self, "vlm_preannotation_progress_label", None)
            path_widget = getattr(self, "vlm_preannotation_progress_path_label", None)
            bar_widget = getattr(self, "vlm_preannotation_progress_bar", None)
            if label_widget is not None:
                label_widget.setText(label)
            if path_widget is not None:
                if current_image:
                    path_widget.setText(self._short_progress_path(current_image, limit=92))
                    path_widget.setToolTip(current_image)
                    path_widget.show()
                else:
                    path_widget.setText("")
                    path_widget.setToolTip("")
                    path_widget.hide()
            if bar_widget is not None:
                bar_widget.setValue(percent)

    def _create_vlm_progress_dialog(self):
        progress = QDialog(self)
        progress.setWindowTitle(tr("VLM Pre-Annotate", self.current_lang))
        progress.setWindowModality(Qt.NonModal)
        progress.installEventFilter(self)
        layout = QVBoxLayout(progress)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)
        title_label = QLabel(tr("VLM Pre-Annotation Progress", self.current_lang))
        title_label.setWordWrap(True)
        title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        title_label.setMinimumHeight(title_label.fontMetrics().lineSpacing() + 6)
        notice_label = QLabel(
            tr(
                "Active API request(s) may already have been sent, but no more queued images will be processed. This helps avoid unintended large API bills.",
                self.current_lang,
            )
        )
        notice_label.setWordWrap(True)
        notice_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        notice_label.setMinimumHeight(notice_label.fontMetrics().lineSpacing() * 2 + 8)
        notice_label.setStyleSheet("color: #9CA3AF;")
        label = QLabel("")
        label.setWordWrap(True)
        label.setMinimumHeight(36)
        path_label = QLabel("")
        path_label.setWordWrap(True)
        path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        path_label.setStyleSheet("color: #9CA3AF;")
        path_label.hide()
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(0)
        stop_button = QPushButton(tr("Stop VLM Batch", self.current_lang))
        stop_button.clicked.connect(lambda: self.request_stop_vlm_preannotation(confirm=True))
        apply_semantic_button_style(stop_button, BUTTON_ROLE_STOP, "padding: 6px 12px;")
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        button_layout.addWidget(stop_button)
        layout.addWidget(title_label)
        layout.addWidget(notice_label)
        layout.addWidget(label)
        layout.addWidget(path_label)
        layout.addWidget(bar)
        layout.addLayout(button_layout)
        self._prepare_progress_dialog(progress, width=560)
        self.vlm_preannotation_progress_dialog = progress
        self.vlm_preannotation_progress_title_label = title_label
        self.vlm_preannotation_progress_notice_label = notice_label
        self.vlm_preannotation_progress_label = label
        self.vlm_preannotation_progress_path_label = path_label
        self.vlm_preannotation_progress_bar = bar
        self.vlm_preannotation_stop_button = stop_button
        progress.show()

    def _advance_vlm_progress(self, step_name, image_path=None):
        total = max(1, int(getattr(self, "vlm_preannotation_total_steps", 1) or 1))
        completed = min(total, int(getattr(self, "vlm_preannotation_completed_steps", 0) or 0) + 1)
        self.vlm_preannotation_completed_steps = completed
        if image_path:
            self.vlm_preannotation_current_image = str(image_path)
            image_key = self._vlm_progress_image_key(image_path)
            step_counts = getattr(self, "vlm_preannotation_image_step_counts", None)
            if not isinstance(step_counts, dict):
                step_counts = {}
                self.vlm_preannotation_image_step_counts = step_counts
            step_counts[image_key] = min(6, int(step_counts.get(image_key, 0) or 0) + 1)
            self.vlm_preannotation_current_image_steps_completed = step_counts[image_key]
        else:
            current_completed = int(getattr(self, "vlm_preannotation_current_image_steps_completed", 0) or 0)
            self.vlm_preannotation_current_image_steps_completed = min(6, current_completed + 1)
        self._set_vlm_progress_ui(int(completed / total * 100), step_name)
        self.log(tr("VLM batch progress: {0}/{1} steps ({2}).", self.current_lang).format(completed, total, step_name))

    def _on_vlm_preannotation_thread_step(self, worker_or_completed, completed_or_total=None, total_or_step_name=None, step_name=None):
        worker = None
        if step_name is None:
            step_name = total_or_step_name
        else:
            worker = worker_or_completed
        image_path = ""
        if worker is not None:
            active_images = getattr(self, "vlm_preannotation_active_images", {}) or {}
            image_path = active_images.get(worker, "")
        self._advance_vlm_progress(step_name, image_path=image_path)

    def _complete_current_vlm_image_steps(self, step_name, image_path=None):
        current_completed = int(getattr(self, "vlm_preannotation_current_image_steps_completed", 0) or 0)
        if image_path:
            step_counts = getattr(self, "vlm_preannotation_image_step_counts", {}) or {}
            current_completed = int(step_counts.get(self._vlm_progress_image_key(image_path), current_completed) or 0)
        for _ in range(max(0, 6 - current_completed)):
            self._advance_vlm_progress(step_name, image_path=image_path)

    def _finish_vlm_preannotation_run(self):
        records = list(getattr(self, "vlm_preannotation_records", []) or [])
        artifacts_dir = getattr(self, "vlm_preannotation_artifacts_dir", self._vlm_preannotation_artifacts_dir())
        run_id = getattr(self, "vlm_preannotation_run_id", time.strftime("%Y%m%d_%H%M%S"))
        cancelled = bool(getattr(self, "vlm_preannotation_cancel_requested", False))
        cancelled_queued = int(getattr(self, "vlm_preannotation_cancelled_queued_images", 0) or 0)
        report_path = os.path.join(artifacts_dir, f"vlm_preannotation_summary_{run_id}.json")
        if int(getattr(self, "vlm_preannotation_saved_total", 0) or 0) > 0:
            self._flush_pending_project_save(defer_for_navigation=False)
        summary = {
            "schema_version": "taxamask-vlm-preannotation-gui-summary-v1",
            "run_id": run_id,
            "artifacts_dir": artifacts_dir,
            "status": "cancelled" if cancelled else "finished",
            "concurrency": max(1, min(8, int(getattr(self, "vlm_preannotation_concurrency", 1) or 1))),
            "cancelled_queued_image_count": cancelled_queued,
            "target_parts": list(getattr(self, "vlm_preannotation_target_parts", []) or []),
            "prompt_profile": sanitize_vlm_prompt_profile(
                getattr(self, "vlm_preannotation_prompt_profile", default_vlm_prompt_profile())
            ),
            "image_count": len(records),
            "candidate_count": sum(len(item.get("candidates", []) or []) for item in records),
            "saved_box_count": int(getattr(self, "vlm_preannotation_saved_total", 0) or 0),
            "rejected_count": sum(len(item.get("rejected", []) or []) for item in records),
            "records": records,
        }
        self._finish_sqlite_vlm_run(run_id, summary)
        os.makedirs(artifacts_dir, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as handle:
            json.dump(summary, handle, ensure_ascii=False, indent=2)
        runtime_log_event(
            "vlm_batch_finish",
            project=getattr(self.project, "current_project_path", ""),
            report=report_path,
            status=summary.get("status", ""),
            image_count=summary.get("image_count", 0),
            saved_box_count=summary.get("saved_box_count", 0),
            cancelled_queued_image_count=cancelled_queued,
            run_id=run_id,
        )
        if cancelled:
            self.log(
                tr(
                    "VLM preannotation stopped. Images processed: {0}; queued images cancelled: {1}; saved drafts: {2}; report: {3}",
                    self.current_lang,
                ).format(
                    summary.get("image_count", 0),
                    cancelled_queued,
                    summary.get("saved_box_count", 0),
                    report_path,
                )
            )
        else:
            self.log(
                tr("VLM preannotation finished. Images: {0}; saved drafts: {1}; report: {2}", self.current_lang).format(
                    summary.get("image_count", 0),
                    summary.get("saved_box_count", 0),
                    report_path,
                )
            )
        self.vlm_preannotation_run_active = False
        for button_name in ("btn_vlm_preannotate_current", "btn_vlm_preannotate_batch", "btn_vlm_preannotate"):
            button = getattr(self, button_name, None)
            if button is not None:
                button.setEnabled(True)
        progress = getattr(self, "vlm_preannotation_progress_dialog", None)
        if progress is not None:
            label_widget = getattr(self, "vlm_preannotation_progress_label", None)
            bar_widget = getattr(self, "vlm_preannotation_progress_bar", None)
            if label_widget is not None:
                if cancelled:
                    label_widget.setText(
                        tr("VLM progress: stopped ({0} draft boxes; {1} queued images cancelled)", self.current_lang).format(
                            summary.get("saved_box_count", 0),
                            cancelled_queued,
                        )
                    )
                else:
                    label_widget.setText(
                        tr("VLM progress: finished ({0} draft boxes)", self.current_lang).format(summary.get("saved_box_count", 0))
                    )
            if bar_widget is not None:
                bar_widget.setValue(100)
            progress.removeEventFilter(self)
            progress.close()
            progress.deleteLater()
            self.vlm_preannotation_progress_dialog = None
            self.vlm_preannotation_progress_title_label = None
            self.vlm_preannotation_progress_notice_label = None
            self.vlm_preannotation_progress_label = None
            self.vlm_preannotation_progress_path_label = None
            self.vlm_preannotation_progress_bar = None
            self.vlm_preannotation_stop_button = None
        self.vlm_preannotation_cancel_requested = False
        self.vlm_preannotation_cancelled_queued_images = 0
        self.vlm_preannotation_threads = []
        self.vlm_preannotation_thread = None
        self.vlm_preannotation_active_images = {}
        self.vlm_preannotation_image_step_counts = {}
        self.vlm_preannotation_completed_image_keys = set()

    def accept_current_image_ai_drafts(self):
        if not self.current_image:
            return
        summarize = getattr(self.project, "summarize_image_ai_drafts", None)
        draft_summary = summarize(self.current_image) if callable(summarize) else {}
        reviewable_parts = list((draft_summary or {}).get("reviewable_polygon_parts", []) or [])
        if reviewable_parts:
            reply = themed_yes_no_question(
                self,
                tr("Confirm AI Drafts", self.current_lang),
                tr(
                    "Accept {0} AI polygon draft(s) on the current image?\n\nOnly drafts that already have a polygon will become training labels. Box-only drafts will stay pending until you run SAM from the box or redraw a polygon.",
                    self.current_lang,
                ).format(len(reviewable_parts)),
                confirm_role=BUTTON_ROLE_COMMIT,
            )
            if reply != QMessageBox.Yes:
                return
        count = self.project.verify_image_labels(self.current_image, save=False)
        if count:
            self._schedule_project_save()
            self.canvas.set_polygons(self.project.get_labels(self.current_image))
            self._refresh_current_canvas_boxes()
            self._refresh_image_list_status_or_rebuild(self.current_image)
            self._refresh_blink_refine_state()
            self.log(tr("Accepted {0} AI draft(s) on current image.", self.current_lang).format(count))
        else:
            self.log(tr("No reviewable AI polygon drafts on current image.", self.current_lang))
        box_only_parts = list((draft_summary or {}).get("box_only_parts", []) or [])
        if box_only_parts:
            self.log(
                tr(
                    "Current image still has {0} AI box-only draft(s): {1}. Box-only drafts cannot enter training; run SAM from the box or redraw a polygon first.",
                    self.current_lang,
                ).format(len(box_only_parts), ", ".join(box_only_parts))
            )

    def accept_batch_ai_drafts(self):
        image_paths = [path for path in self.project.project_data.get("images", []) if path]
        if not image_paths:
            self.log(tr("No reviewable AI polygon drafts in the current project.", self.current_lang))
            return

        self._flush_pending_project_save(defer_for_navigation=False)
        summarize_many = getattr(self.project, "summarize_ai_drafts_for_images", None)
        if callable(summarize_many):
            summary = summarize_many(image_paths)
        else:
            image_summaries = []
            reviewable_count = 0
            box_only_count = 0
            summarize_one = getattr(self.project, "summarize_image_ai_drafts", None)
            for image_path in image_paths:
                item = summarize_one(image_path) if callable(summarize_one) else {}
                item_reviewable = len(item.get("reviewable_polygon_parts", []) or [])
                item_box_only = len(item.get("box_only_parts", []) or [])
                if item_reviewable or item_box_only:
                    image_summaries.append({"image_path": image_path, "reviewable_count": item_reviewable, "box_only_count": item_box_only})
                    reviewable_count += item_reviewable
                    box_only_count += item_box_only
            summary = {
                "images_with_drafts": image_summaries,
                "image_count": len(image_summaries),
                "reviewable_polygon_count": reviewable_count,
                "box_only_count": box_only_count,
            }

        reviewable_count = int(summary.get("reviewable_polygon_count", 0) or 0)
        image_count = int(summary.get("image_count", 0) or 0)
        box_only_count = int(summary.get("box_only_count", 0) or 0)
        if not reviewable_count:
            self.log(tr("No reviewable AI polygon drafts in the current project.", self.current_lang))
            if box_only_count:
                box_only_images = sum(1 for item in summary.get("images_with_drafts", []) if int(item.get("box_only_count", 0) or 0) > 0)
                self.log(
                    tr(
                        "{0} image(s) in the current project still have {1} AI box-only draft(s). Box-only drafts cannot enter training; run SAM from the box or redraw polygons first.",
                        self.current_lang,
                    ).format(box_only_images, box_only_count)
                )
            return

        reply = themed_yes_no_question(
            self,
            tr("Confirm AI Drafts", self.current_lang),
            tr(
                "Accept {0} AI polygon draft(s) from {1} image(s) in the current project?\n\nOnly drafts that already have polygons will become training labels. {2} box-only draft(s) will be skipped and stay pending.",
                self.current_lang,
            ).format(reviewable_count, image_count, box_only_count),
            confirm_role=BUTTON_ROLE_COMMIT,
        )
        if reply != QMessageBox.Yes:
            return

        verify_many = getattr(self.project, "verify_ai_drafts_for_images", None)
        if callable(verify_many):
            result = verify_many(image_paths)
            accepted_count = int(result.get("accepted_count", 0) or 0)
            accepted_images = int(result.get("accepted_images", 0) or 0)
        else:
            accepted_count = 0
            accepted_images = 0
            for image_path in image_paths:
                count = self.project.verify_image_labels(image_path)
                if count:
                    accepted_count += count
                    accepted_images += 1

        if self.current_image:
            self.canvas.set_polygons(self.project.get_labels(self.current_image))
            self._refresh_current_canvas_boxes()
        self.refresh_file_list()
        self._refresh_blink_refine_state()
        if accepted_count:
            self.log(
                tr("Accepted {0} AI polygon draft(s) from {1} image(s) in the current project.", self.current_lang).format(
                    accepted_count,
                    accepted_images,
                )
            )
        else:
            self.log(tr("No reviewable AI polygon drafts in the current project.", self.current_lang))
        if box_only_count:
            box_only_images = sum(1 for item in summary.get("images_with_drafts", []) if int(item.get("box_only_count", 0) or 0) > 0)
            self.log(
                tr(
                    "{0} image(s) in the current project still have {1} AI box-only draft(s). Box-only drafts cannot enter training; run SAM from the box or redraw polygons first.",
                    self.current_lang,
                ).format(box_only_images, box_only_count)
            )

    def _on_vlm_preannotation_error(self, message):
        self.log(tr("VLM first-mile preannotation failed: {0}", self.current_lang).format(message))
        QMessageBox.warning(self, tr("VLM Pre-Annotate", self.current_lang), str(message))

    def _on_vlm_preannotation_qthread_finished(self, worker=None):
        if not getattr(self, "vlm_preannotation_run_active", False):
            return
        worker = worker or self.sender()
        worker_image = ""
        active_images = getattr(self, "vlm_preannotation_active_images", None)
        if isinstance(active_images, dict) and worker is not None:
            worker_image = active_images.pop(worker, "")
        if worker is not None:
            self.vlm_preannotation_threads = [
                thread
                for thread in (getattr(self, "vlm_preannotation_threads", []) or [])
                if thread is not worker
            ]
        runtime_log_event(
            "vlm_worker_finished",
            image=os.path.basename(str(worker_image or "")),
            active_count=len(getattr(self, "vlm_preannotation_threads", []) or []),
            queued_count=len(getattr(self, "vlm_preannotation_queue", []) or []),
            cancel_requested=bool(getattr(self, "vlm_preannotation_cancel_requested", False)),
            run_id=getattr(self, "vlm_preannotation_run_id", ""),
        )
        active = self._active_vlm_preannotation_threads()
        if getattr(self, "vlm_preannotation_cancel_requested", False):
            self.vlm_preannotation_queue = []
            if not active:
                self._finish_vlm_preannotation_run()
            return
        if getattr(self, "vlm_preannotation_queue", []):
            self._start_vlm_preannotation_workers()
            return
        if not active:
            self._finish_vlm_preannotation_run()

    def _on_vlm_preannotation_finished(self):
        self._on_vlm_preannotation_qthread_finished(self.sender())

    def run_prediction(self):
        if not self.current_image:
            return
        if _runtime_parent_backend(self.project, self.model_backend) == EXTERNAL_BACKEND_ID:
            self.run_external_prediction(self.current_image)
            return
        self.ensure_locator_preloaded()
        if not self._confirm_legacy_locator_selection_if_needed():
            return
        self.ensure_sam_preloaded()
        self.log(tr("Running inference on: {0}...", self.current_lang).format(os.path.basename(self.current_image)))
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            ps = self.engine.predict_full_pipeline(
                image_path=self.current_image,
                current_taxonomy=self.project.project_data["taxonomy"],
                locator_scope=self.project.get_locator_scope(),
                conf_thresh=self.inf_conf,
                adapt_thresh=self.inf_adapt,
                box_pad=self.inf_pad,
                noise_floor=self.inf_noise_floor,
                poly_epsilon=self.inf_poly_epsilon,
                project_route_manifest=self._active_project_route_manifest(),
                model_profile_context=self._active_model_profile_context(),
            )
            count, total_detected = self._apply_prediction_to_project(
                self.current_image,
                ps,
                only_new=True,
                save=False,
                source=AUTO_BOX_SOURCE_MODEL,
            )
            if count:
                self._schedule_project_save()
            
            labels = self.project.get_labels(self.current_image)
            manual_boxes = self.project.get_boxes(self.current_image)
            auto_boxes, vlm_boxes = self._auto_boxes_for_canvas(self.current_image)
            self.canvas.set_polygons(labels)
            self.canvas.set_boxes(manual_boxes, auto_boxes, self._current_shrink_loose_boxes(), vlm=vlm_boxes)
            self._refresh_image_list_status_or_rebuild(self.current_image)
            self._refresh_blink_refine_state()
            self._log_route_usage_summary(ps, self.current_image)
            self.log(tr("Inference complete. Detected {0} parts, saved {1} new labels.", self.current_lang).format(total_detected, count))
        finally:
            QApplication.restoreOverrideCursor()

    def run_external_prediction(self, image_path):
        self._flush_pending_project_save(defer_for_navigation=False)
        self.log(tr("Running inference on: {0}...", self.current_lang).format(os.path.basename(image_path)))
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            result = self._external_backend_runner().run_predict(
                image_path,
                model_manifest=self._active_external_backend_config().get("model_manifest", ""),
            )
            count, total_detected = self._apply_prediction_to_project(
                image_path,
                result.get("payload", {}),
                only_new=True,
                save=False,
                source=AUTO_BOX_SOURCE_EXTERNAL_MODEL,
            )
            if count:
                self._schedule_project_save()
            if image_path == self.current_image:
                self.canvas.set_polygons(self.project.get_labels(image_path))
                self._refresh_current_canvas_boxes()
                self._refresh_blink_refine_state()
            self._refresh_image_list_status_or_rebuild(image_path)
            self.log(f"External inference complete. Contract: {result.get('contract_json')}")
            self.log(tr("Inference complete. Detected {0} parts, saved {1} new labels.", self.current_lang).format(total_detected, count))
        except Exception as exc:
            self.log(f"External inference failed: {exc}")
            QMessageBox.critical(self, tr("Error", self.current_lang), str(exc))
        finally:
            QApplication.restoreOverrideCursor()

    def verify_current_image(self):
        if self.current_image:
            count = self.project.verify_image_labels(self.current_image, save=False)
            if count:
                self._schedule_project_save()
                self.canvas.set_polygons(self.project.get_labels(self.current_image))
                self._refresh_current_canvas_boxes()
                self._refresh_image_list_status_or_rebuild(self.current_image)
                self._refresh_blink_refine_state()

    def _start_external_batch_inference(self, image_paths):
        if getattr(self, "external_batch_inference_thread", None) is not None and self.external_batch_inference_thread.isRunning():
            QMessageBox.information(
                self,
                tr("Batch Inference", self.current_lang),
                tr("Batch inference is already running.", self.current_lang),
            )
            return

        self._flush_pending_project_save(defer_for_navigation=False)
        self.external_batch_inference_failed = False
        self.external_batch_inference_saved_any = False
        self.btn_batch.setEnabled(False)
        self.btn_predict.setEnabled(False)

        progress = QProgressDialog(
            tr("Starting batch inference on {0} images...", self.current_lang).format(len(image_paths)),
            "",
            0,
            max(1, len(image_paths)),
            self,
        )
        progress.setWindowTitle(tr("Batch Inference", self.current_lang))
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setCancelButton(None)
        self._prepare_progress_dialog(progress, width=520)
        progress.show()
        self.external_batch_inference_progress_dialog = progress

        backend_config = self._active_external_backend_config()
        thread = ExternalBatchInferenceThread(
            self.project,
            backend_config,
            image_paths,
            model_manifest=backend_config.get("model_manifest", ""),
            lang=self.current_lang,
        )
        if hasattr(thread, "translate"):
            thread.translate = tr
        self.external_batch_inference_thread = thread

        def on_progress(done, total, label):
            total = max(0, int(total))
            done = max(0, int(done))
            if total > 0 and progress.maximum() != total:
                progress.setRange(0, total)
            if total > 0:
                progress.setValue(min(done, total))
            message = tr("Starting batch inference on {0} images...", self.current_lang).format(total)
            if label:
                message = f"{message}\n{self._short_progress_path(label)}"
            progress.setLabelText(message)

        def on_result(image_path, result):
            saved, total = self._apply_prediction_to_project(
                image_path,
                result.get("payload", {}),
                only_new=True,
                save=False,
                source=AUTO_BOX_SOURCE_EXTERNAL_MODEL,
            )
            if saved:
                self.external_batch_inference_saved_any = True
            self.log(tr("Batch saved {0}/{1} for {2}", self.current_lang).format(saved, total, os.path.basename(image_path)))

        def on_error(message):
            self.external_batch_inference_failed = True
            self.log(tr("External batch inference failed: {0}", self.current_lang).format(message))
            QMessageBox.critical(
                self,
                tr("Error", self.current_lang),
                tr("External batch inference failed: {0}", self.current_lang).format(message),
            )

        def on_finished():
            if getattr(self, "external_batch_inference_saved_any", False):
                self.project.save_project()
            progress.close()
            progress.deleteLater()
            if getattr(self, "external_batch_inference_progress_dialog", None) is progress:
                self.external_batch_inference_progress_dialog = None
            if getattr(self, "external_batch_inference_thread", None) is thread:
                self.external_batch_inference_thread = None
            thread.deleteLater()
            self.btn_batch.setEnabled(True)
            self.btn_predict.setEnabled(True)
            self.refresh_file_list()
            self._refresh_blink_refine_state()
            if not getattr(self, "external_batch_inference_failed", False):
                self.log(tr("External batch inference finished.", self.current_lang))

        thread.log_signal.connect(self.log)
        thread.progress_signal.connect(on_progress)
        thread.result_signal.connect(on_result)
        thread.error_signal.connect(on_error)
        thread.finished_signal.connect(on_finished)
        thread.start()

    def run_batch_inference(self):
        ul = [img for img in self.project.project_data["images"] if not self.project.get_labels(img)]
        if not ul:
            return
        if _runtime_parent_backend(self.project, self.model_backend) == EXTERNAL_BACKEND_ID:
            if themed_yes_no_question(
                self,
                tr("Batch", self.current_lang),
                tr("Annotate {0} images?", self.current_lang).format(len(ul)),
                confirm_role=BUTTON_ROLE_RUN,
            ) == QMessageBox.Yes:
                self._start_external_batch_inference(ul)
            return
        self.ensure_locator_preloaded()
        if not self._confirm_legacy_locator_selection_if_needed():
            return
        self.ensure_sam_preloaded()
        if themed_yes_no_question(
            self,
            tr("Batch", self.current_lang),
            tr("Annotate {0} images?", self.current_lang).format(len(ul)),
            confirm_role=BUTTON_ROLE_RUN,
        ) == QMessageBox.Yes:
            self.btn_batch.setEnabled(False)
            self.btn_predict.setEnabled(False)
            
            tax = self.project.project_data["taxonomy"]
            locator_scope = self.project.get_locator_scope()
            self.log(tr("Starting Batch Inference with Taxonomy ({0}): {1}", self.current_lang).format(len(tax), tax))
            self.log(tr("Starting Batch Inference with Locator Scope ({0}): {1}", self.current_lang).format(len(locator_scope), locator_scope))
            
            params = {
                'conf': self.inf_conf, 'adapt': self.inf_adapt, 
                'pad': self.inf_pad, 'noise_floor': self.inf_noise_floor,
                'poly_epsilon': self.inf_poly_epsilon,
            }
            self.inf_thread = InferenceThread(
                self.engine,
                ul,
                tax,
                locator_scope,
                params,
                project_route_manifest=self._active_project_route_manifest(),
                model_profile_context=self._active_model_profile_context(),
                lang=self.current_lang,
            )
            if hasattr(self.inf_thread, "translate"):
                self.inf_thread.translate = tr
            self.inf_thread.log_signal.connect(self.log) # Fix: Connect log signal
            def on_batch_res(p, d):
                saved, total = self._apply_prediction_to_project(
                    p,
                    d,
                    only_new=True,
                    save=False,
                    source=AUTO_BOX_SOURCE_MODEL,
                )
                self._log_route_usage_summary(
                    d,
                    p,
                    prefix=ui_text("Route usage for batch image {0}", self.current_lang).format(os.path.basename(p)),
                )
                self.log(tr("Batch saved {0}/{1} for {2}", self.current_lang).format(saved, total, os.path.basename(p)))
            self.inf_thread.result_signal.connect(on_batch_res)
            self.inf_thread.finished_signal.connect(
                lambda: [
                    self.project.save_project(),
                    self.btn_batch.setEnabled(True),
                    self.btn_predict.setEnabled(True),
                    self.refresh_file_list(),
                    self._refresh_blink_refine_state(),
                ]
            )
            self.inf_thread.start()

    def export_dataset(self):
        dlg = ExportDialog(self, self.current_lang, default_dir=self._default_2d_export_dir())
        if dlg.exec():
            self._flush_pending_project_save(defer_for_navigation=False)
            p, f = dlg.get_path(), dlg.get_format()
            if not p:
                return
            self._start_dataset_export(p, f)

    def _start_dataset_export(self, output_dir, export_format):
        if getattr(self, "dataset_export_thread", None) is not None and self.dataset_export_thread.isRunning():
            QMessageBox.information(
                self,
                tr("Export", self.current_lang),
                tr("Dataset export is already running.", self.current_lang),
            )
            return

        progress = QProgressDialog(
            tr("Preparing dataset export...", self.current_lang),
            "",
            0,
            0,
            self,
        )
        progress.setWindowTitle(tr("Export Progress", self.current_lang))
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setCancelButton(None)
        self._prepare_progress_dialog(progress, width=520)
        progress.show()

        self.dataset_export_thread = DatasetExportThread(
            self.project,
            output_dir,
            export_format,
            lang=self.current_lang,
        )
        thread = self.dataset_export_thread

        def on_progress(done, total, label):
            total = max(0, int(total))
            done = max(0, int(done))
            if total > 0 and progress.maximum() != total:
                progress.setRange(0, total)
            elif total <= 0 and progress.maximum() != 0:
                progress.setRange(0, 0)
            if total > 0:
                progress.setValue(min(done, total))
            message = tr("Exporting dataset...", self.current_lang)
            if label:
                message = tr("Exporting dataset: {0}", self.current_lang).format(label)
            progress.setLabelText(message)

        def on_success(count, folder, _export_format):
            progress.setValue(progress.maximum())
            progress.close()
            message = tr("Exported {0} samples.\n\nOutput folder: {1}", self.current_lang).format(count, folder)
            self.log(message)
            try:
                open_path(folder)
            except Exception as exc:
                self.log(f"Could not open export folder: {exc}")
            QMessageBox.information(self, tr("Export", self.current_lang), message)

        def on_error(message):
            progress.close()
            QMessageBox.warning(
                self,
                tr("Export", self.current_lang),
                tr("Dataset export failed: {0}", self.current_lang).format(message),
            )

        def on_finished():
            if getattr(self, "dataset_export_thread", None) is thread:
                self.dataset_export_thread = None

        thread.progress_signal.connect(on_progress)
        thread.success_signal.connect(on_success)
        thread.error_signal.connect(on_error)
        thread.finished_signal.connect(on_finished)
        thread.start()

    def init_sam(self):
        if self.sam_thread and self.sam_thread.isRunning():
            return
        if self.sam_worker and getattr(self.sam_worker, "model", None) is not None:
            return
        mp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "weights", "sam_b.pt")
        self.log(tr("Initializing SAM (Segment Anything) on active compute device...", self.current_lang))
        self.sam_thread = QThread()
        # Pass current epsilon to worker
        self.sam_worker = SAMWorker(model_type=mp, poly_epsilon=self.inf_poly_epsilon, device=self.runtime_device)
        self.sam_worker.moveToThread(self.sam_thread)
        self.sam_thread.started.connect(self.sam_worker.load_model)
        queued_connection = Qt.ConnectionType.QueuedConnection
        if hasattr(self.sam_worker, "predict_point"):
            self.sam_point_requested.connect(self.sam_worker.predict_point, queued_connection)
        if hasattr(self.sam_worker, "predict_box"):
            self.sam_box_requested.connect(self.sam_worker.predict_box, queued_connection)
        self.sam_worker.mask_generated.connect(self.on_sam_mask_generated)
        if hasattr(self.sam_worker, "prompt_failed"):
            self.sam_worker.prompt_failed.connect(self.on_sam_prompt_failed)
        self.sam_worker.model_loaded.connect(self._on_sam_model_loaded)
        self.sam_worker.model_load_error.connect(lambda message: self.log(str(message)))
        self.sam_thread.start()

    def ensure_sam_preloaded(self):
        started = False
        if self.sam_thread and self.sam_thread.isRunning():
            pass
        elif self.sam_worker and getattr(self.sam_worker, "model", None) is not None:
            pass
        else:
            self.init_sam()
            started = True

        if self._preload_engine_parts_model_async():
            started = True
        return started

    def ensure_2d_stl_models_preloaded(self):
        locator_started = self.ensure_locator_preloaded()
        sam_started = self.ensure_sam_preloaded()
        return bool(locator_started or sam_started)

    def ensure_locator_preloaded(self):
        if not self.engine or not hasattr(self.engine, "ensure_locator_loaded"):
            return False
        if getattr(self.engine, "locator", None) is not None:
            return False
        locator_scope_len = len(self.project.get_locator_scope())
        if locator_scope_len != self.engine.current_num_classes:
            self.engine.current_num_classes = locator_scope_len
            self.engine.loaded_locator_timestamp = None
            self.engine.loaded_locator_requires_legacy_confirmation = False
            self.engine.loaded_locator_is_legacy_512 = False
        ts = self._selected_locator_timestamp()
        if ts:
            self.engine.load_locator(ts)
        else:
            self.engine.ensure_locator_loaded()
        return True

    def _preload_engine_parts_model_async(self):
        if not self.engine or not hasattr(self.engine, "ensure_parts_model_loaded"):
            return False
        if getattr(self.engine, "parts_model", None) is not None:
            return False
        existing_thread = getattr(self, "parts_model_preload_thread", None)
        if existing_thread is not None and existing_thread.is_alive():
            return False

        def worker():
            try:
                self.engine.ensure_parts_model_loaded()
            except Exception as exc:
                print(f"Error preloading Trainable SAM: {exc}")

        self.parts_model_preload_thread = threading.Thread(
            target=worker,
            name="TaxaMaskTrainableSAMPreload",
            daemon=True,
        )
        self.parts_model_preload_thread.start()
        return True

    def log(self, msg):
        self.log_console.append(msg)

if __name__ == "__main__":
    def excepthook(t, v, tb):
        import traceback
        err = "".join(traceback.format_exception(t, v, tb))
        runtime_log_exception("uncaught_exception", t, v, tb)
        print(f"CRITICAL ERROR:\n{err}")
        QMessageBox.critical(None, "Error", f"{v}")
        sys.__excepthook__(t, v, tb)
    sys.excepthook = excepthook
    app = QApplication(sys.argv)
    for icon_path in (APP_ICON_PATH, APP_ICON_FALLBACK_PATH):
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
            if not icon.isNull():
                app.setWindowIcon(icon)
                break
    register_windows_scholarly_ui_fonts()
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
