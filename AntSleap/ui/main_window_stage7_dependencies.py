import json
import os
import re
import sys
import threading
import time

import cv2
import torch
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QProgressDialog,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
)

try:
    from AntSleap.app_runtime import runtime_log_event, runtime_log_exception
    from AntSleap.core.blink_training_strategy import blink_training_strategy_label
    from AntSleap.core.external_backend import (
        EXTERNAL_BACKEND_ID,
        ExternalBackendRunner,
        sanitize_external_backend_config,
    )
    from AntSleap.core.model_profiles import PARENT_BACKEND_BUILTIN, PARENT_BACKEND_EXTERNAL
    from AntSleap.core.parent_model_notes import (
        format_parent_model_display_name,
        load_parent_model_notes,
        set_parent_model_note,
    )
    from AntSleap.core.project import (
        AUTO_BOX_REVIEW_DRAFT,
        AUTO_BOX_SOURCE_EXTERNAL_MODEL,
        AUTO_BOX_SOURCE_MODEL,
        AUTO_BOX_SOURCE_VLM,
    )
    from AntSleap.core.project_sqlite_writer import finish_vlm_run, record_vlm_image_result
    from AntSleap.core.training_preflight import build_training_preflight, describe_training_preflight, format_size_pair
    from AntSleap.core.training_run_2d import (
        DEFAULT_TRAINING_SEED,
        prepare_2d_training_run,
    )
    from AntSleap.core.training_run_recorder import TrainingRunRecorder
    from AntSleap.core.training_run_notes import TrainingRunNoteStore
    from AntSleap.core.training_initial_weights import (
        inspect_initial_weight_registration,
        register_initial_weight_version,
    )
    from AntSleap.core.training_weight_publisher import TrainingWeightPublisher
    from AntSleap.core.vlm_preannotation import (
        default_vlm_prompt_profile,
        load_vlm_api_config_from_runtime_settings,
        sanitize_vlm_prompt_profile,
    )
    from AntSleap.ui.blink_lab import BlinkExpertTrainingReportDialog
    from AntSleap.ui.main_window_dialog_support import (
        _active_profile_from_manager,
        _clean_box,
        _parent_backend_label,
        _runtime_parent_backend,
    )
    from AntSleap.ui.main_window_dialogs import ExportDialog
    from AntSleap.ui.main_window_i18n import tr, ui_text
    from AntSleap.ui.main_window_workers import (
        DatasetExportThread,
        ExternalBatchInferenceThread,
        ExternalTrainingThread,
        InferenceThread,
        TrainingThread,
        VlmPreannotationThread,
    )
    from AntSleap.ui.style import (
        BUTTON_ROLE_COMMIT,
        BUTTON_ROLE_DESTRUCTIVE,
        BUTTON_ROLE_RUN,
        BUTTON_ROLE_STOP,
        apply_semantic_button_style,
        themed_yes_no_question,
    )
    from AntSleap.ui.training_report_dialogs import (
        TrainingPreflightDialog,
        TrainingReportDialog,
        TrainingResultBrowserDialog,
        TrainingRunNoteDialog,
    )
    from AntSleap.ui.training_integrity_recovery_dialog import TrainingIntegrityRecoveryDialog
except ImportError:
    from app_runtime import runtime_log_event, runtime_log_exception
    from core.blink_training_strategy import blink_training_strategy_label
    from core.external_backend import EXTERNAL_BACKEND_ID, ExternalBackendRunner, sanitize_external_backend_config
    from core.model_profiles import PARENT_BACKEND_BUILTIN, PARENT_BACKEND_EXTERNAL
    from core.parent_model_notes import format_parent_model_display_name, load_parent_model_notes, set_parent_model_note
    from core.project import (
        AUTO_BOX_REVIEW_DRAFT,
        AUTO_BOX_SOURCE_EXTERNAL_MODEL,
        AUTO_BOX_SOURCE_MODEL,
        AUTO_BOX_SOURCE_VLM,
    )
    from core.project_sqlite_writer import finish_vlm_run, record_vlm_image_result
    from core.training_preflight import build_training_preflight, describe_training_preflight, format_size_pair
    from core.training_run_2d import DEFAULT_TRAINING_SEED, prepare_2d_training_run
    from core.training_run_recorder import TrainingRunRecorder
    from core.training_run_notes import TrainingRunNoteStore
    from core.training_initial_weights import inspect_initial_weight_registration, register_initial_weight_version
    from core.training_weight_publisher import TrainingWeightPublisher
    from core.vlm_preannotation import (
        default_vlm_prompt_profile,
        load_vlm_api_config_from_runtime_settings,
        sanitize_vlm_prompt_profile,
    )
    from ui.blink_lab import BlinkExpertTrainingReportDialog
    from ui.main_window_dialog_support import _active_profile_from_manager, _clean_box, _parent_backend_label, _runtime_parent_backend
    from ui.main_window_dialogs import ExportDialog
    from ui.main_window_i18n import tr, ui_text
    from ui.main_window_workers import (
        DatasetExportThread,
        ExternalBatchInferenceThread,
        ExternalTrainingThread,
        InferenceThread,
        TrainingThread,
        VlmPreannotationThread,
    )
    from ui.style import (
        BUTTON_ROLE_COMMIT,
        BUTTON_ROLE_DESTRUCTIVE,
        BUTTON_ROLE_RUN,
        BUTTON_ROLE_STOP,
        apply_semantic_button_style,
        themed_yes_no_question,
    )
    from ui.training_report_dialogs import TrainingPreflightDialog, TrainingReportDialog, TrainingResultBrowserDialog, TrainingRunNoteDialog
    from ui.training_integrity_recovery_dialog import TrainingIntegrityRecoveryDialog


PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(PACKAGE_DIR)

__all__ = [name for name in globals() if not name.startswith("__")]
