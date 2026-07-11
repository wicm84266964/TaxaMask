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
    from AntSleap.ui.main_window_image_grouping import MainWindowImageGroupingMixin
    from AntSleap.ui.main_window_image_navigation import MainWindowImageNavigationMixin
    from AntSleap.ui.main_window_literature_bridge import MainWindowLiteratureBridgeMixin
    from AntSleap.ui.main_window_model_management import MainWindowModelManagementMixin
    from AntSleap.ui.main_window_part_tree import MainWindowPartTreeMixin
    from AntSleap.ui.main_window_prediction import MainWindowPredictionMixin
    from AntSleap.ui.main_window_presentation import MainWindowPresentationMixin
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
    from ui.main_window_image_grouping import MainWindowImageGroupingMixin
    from ui.main_window_image_navigation import MainWindowImageNavigationMixin
    from ui.main_window_literature_bridge import MainWindowLiteratureBridgeMixin
    from ui.main_window_model_management import MainWindowModelManagementMixin
    from ui.main_window_part_tree import MainWindowPartTreeMixin
    from ui.main_window_prediction import MainWindowPredictionMixin
    from ui.main_window_presentation import MainWindowPresentationMixin
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
    MainWindowImageGroupingMixin,
    MainWindowLiteratureBridgeMixin,
    MainWindowAnnotationMixin,
    MainWindowBlinkContextMixin,
    MainWindowBlinkWorkflowMixin,
    MainWindowModelManagementMixin,
    MainWindowTrainingMixin,
    MainWindowPredictionMixin,
    MainWindowVlmMixin,
    MainWindowExportMixin,
    MainWindowPresentationMixin,
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
