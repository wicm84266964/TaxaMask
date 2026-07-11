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
    from AntSleap.ui.blink_lab import BlinkExpertTrainingReportDialog, BlinkLabWidget
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
    from ui.blink_lab import BlinkExpertTrainingReportDialog, BlinkLabWidget
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


try:
    from AntSleap.ui.main_window_agent_context import MainWindowAgentContextMixin
    from AntSleap.ui.main_window_annotation import MainWindowAnnotationMixin
    from AntSleap.ui.main_window_blink_context import MainWindowBlinkContextMixin
    from AntSleap.ui.main_window_blink_workflow import MainWindowBlinkWorkflowMixin
    from AntSleap.ui.main_window_export import MainWindowExportMixin
    from AntSleap.ui.main_window_image_navigation import MainWindowImageNavigationMixin
    from AntSleap.ui.main_window_literature_bridge import MainWindowLiteratureBridgeMixin
    from AntSleap.ui.main_window_model_management import MainWindowModelManagementMixin
    from AntSleap.ui.main_window_part_tree import MainWindowPartTreeMixin
    from AntSleap.ui.main_window_prediction import MainWindowPredictionMixin
    from AntSleap.ui.main_window_project_lifecycle import MainWindowProjectLifecycleMixin
    from AntSleap.ui.main_window_shell import MainWindowShellMixin
    from AntSleap.ui.main_window_start_center import MainWindowStartCenterMixin
    from AntSleap.ui.main_window_training import MainWindowTrainingMixin
    from AntSleap.ui.main_window_vlm import MainWindowVlmMixin
except ImportError:
    from ui.main_window_agent_context import MainWindowAgentContextMixin
    from ui.main_window_annotation import MainWindowAnnotationMixin
    from ui.main_window_blink_context import MainWindowBlinkContextMixin
    from ui.main_window_blink_workflow import MainWindowBlinkWorkflowMixin
    from ui.main_window_export import MainWindowExportMixin
    from ui.main_window_image_navigation import MainWindowImageNavigationMixin
    from ui.main_window_literature_bridge import MainWindowLiteratureBridgeMixin
    from ui.main_window_model_management import MainWindowModelManagementMixin
    from ui.main_window_part_tree import MainWindowPartTreeMixin
    from ui.main_window_prediction import MainWindowPredictionMixin
    from ui.main_window_project_lifecycle import MainWindowProjectLifecycleMixin
    from ui.main_window_shell import MainWindowShellMixin
    from ui.main_window_start_center import MainWindowStartCenterMixin
    from ui.main_window_training import MainWindowTrainingMixin
    from ui.main_window_vlm import MainWindowVlmMixin


class MainWindow(
    MainWindowShellMixin,
    MainWindowStartCenterMixin,
    MainWindowAgentContextMixin,
    MainWindowProjectLifecycleMixin,
    MainWindowPartTreeMixin,
    MainWindowImageNavigationMixin,
    MainWindowLiteratureBridgeMixin,
    MainWindowAnnotationMixin,
    MainWindowBlinkContextMixin,
    MainWindowBlinkWorkflowMixin,
    MainWindowModelManagementMixin,
    MainWindowTrainingMixin,
    MainWindowPredictionMixin,
    MainWindowVlmMixin,
    MainWindowExportMixin,
    QMainWindow,
):
    sam_point_requested = Signal(str, float, float)
    sam_box_requested = Signal(str, float, float, float, float)

    def __init__(self):
        super().__init__()
        self._initialize_main_window_state(
            config_factory=ConfigManager,
            project_factory=ProjectManager,
            tif_project_factory=TifProjectManager,
            stl_project_factory=StlRenderedProjectManager,
            database_factory=MultiModalDB,
            engine_factory=AntEngine,
        )
        self._build_main_window_views()
        self._connect_main_window_integrations()
        self._finish_main_window_startup()























































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
        if getattr(self, "tif_workbench", None) is not None:
            self.tif_workbench.set_config_manager(self.config)
        self.log(tr("TIF backend settings updated.", self.current_lang))

    def change_language(self, lang):
        self.current_lang = lang
        self.config.set("language", lang)
        if getattr(self, "pdf_widget", None) is not None:
            self.pdf_widget.change_language(lang)
        if getattr(self, "tif_workbench", None) is not None:
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

        for widget in [
            getattr(self, "pdf_widget", None),
            self.blink_lab,
            self.canvas,
            getattr(self, "tif_workbench", None),
            getattr(self, "agent_panel", None),
        ]:
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
