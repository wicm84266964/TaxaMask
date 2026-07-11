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
    from AntSleap.ui.main_window_image_navigation import MainWindowImageNavigationMixin
    from AntSleap.ui.main_window_literature_bridge import MainWindowLiteratureBridgeMixin
    from AntSleap.ui.main_window_part_tree import MainWindowPartTreeMixin
    from AntSleap.ui.main_window_project_lifecycle import MainWindowProjectLifecycleMixin
    from AntSleap.ui.main_window_shell import MainWindowShellMixin
    from AntSleap.ui.main_window_start_center import MainWindowStartCenterMixin
except ImportError:
    from ui.main_window_agent_context import MainWindowAgentContextMixin
    from ui.main_window_image_navigation import MainWindowImageNavigationMixin
    from ui.main_window_literature_bridge import MainWindowLiteratureBridgeMixin
    from ui.main_window_part_tree import MainWindowPartTreeMixin
    from ui.main_window_project_lifecycle import MainWindowProjectLifecycleMixin
    from ui.main_window_shell import MainWindowShellMixin
    from ui.main_window_start_center import MainWindowStartCenterMixin


class MainWindow(
    MainWindowShellMixin,
    MainWindowStartCenterMixin,
    MainWindowAgentContextMixin,
    MainWindowProjectLifecycleMixin,
    MainWindowPartTreeMixin,
    MainWindowImageNavigationMixin,
    MainWindowLiteratureBridgeMixin,
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
