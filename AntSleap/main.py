import sys
import os


def _is_wsl_runtime():
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        with open("/proc/version", "r", encoding="utf-8", errors="ignore") as handle:
            return "microsoft" in handle.read().lower()
    except OSError:
        return False


def _append_env_flag(name, flag):
    current = os.environ.get(name, "")
    flags = current.split()
    if flag not in flags:
        flags.append(flag)
        os.environ[name] = " ".join(flags)


def _prepare_qt_runtime_environment():
    # These must be set before importing cv2/PySide6. WSLg and some Linux
    # desktops can segfault while Qt WebEngine probes EGL/GPU acceleration.
    _append_env_flag("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu-compositing")
    linux_runtime = sys.platform == "linux" or _is_wsl_runtime()
    if linux_runtime:
        _append_env_flag("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu")
        os.environ.setdefault("QT_OPENGL", "software")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
        os.environ.setdefault("TAXAMASK_ANTCODE_BROWSER_MODE", "1")


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


def _ensure_qtwebengine_cpu_compositing():
    _append_env_flag("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu")
    _append_env_flag("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu-compositing")


_ensure_qtwebengine_cpu_compositing()

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(PACKAGE_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

_RUNTIME_LOG_FILE = None
_RUNTIME_LOG_PATH = ""


def _runtime_log_enabled():
    return str(os.environ.get("TAXAMASK_RUNTIME_LOG", "1")).strip().lower() not in {"0", "false", "no", "off"}


def _runtime_log_timestamp():
    import time as _time

    return _time.strftime("%Y-%m-%d %H:%M:%S")


def _runtime_log_filename_timestamp():
    import time as _time

    return _time.strftime("%Y%m%d_%H%M%S")


def _runtime_log_prune(log_dir):
    try:
        keep = int(os.environ.get("TAXAMASK_RUNTIME_LOG_KEEP", "20") or 20)
    except Exception:
        keep = 20
    keep = max(1, keep)
    try:
        entries = [
            os.path.join(log_dir, name)
            for name in os.listdir(log_dir)
            if name.startswith("taxamask_runtime_") and name.endswith(".log")
        ]
        entries.sort(key=lambda path: os.path.getmtime(path), reverse=True)
        for old_path in entries[keep:]:
            try:
                os.remove(old_path)
            except OSError:
                pass
    except OSError:
        pass


def _setup_runtime_logging():
    global _RUNTIME_LOG_FILE, _RUNTIME_LOG_PATH
    if _RUNTIME_LOG_FILE is not None or not _runtime_log_enabled():
        return _RUNTIME_LOG_PATH
    try:
        log_dir = os.path.join(REPO_ROOT, "TaxaMask_outputs", "runtime_logs")
        os.makedirs(log_dir, exist_ok=True)
        _runtime_log_prune(log_dir)
        filename = f"taxamask_runtime_{_runtime_log_filename_timestamp()}_{os.getpid()}.log"
        _RUNTIME_LOG_PATH = os.path.join(log_dir, filename)
        _RUNTIME_LOG_FILE = open(_RUNTIME_LOG_PATH, "a", encoding="utf-8", buffering=1)
        try:
            import faulthandler

            faulthandler.enable(file=_RUNTIME_LOG_FILE, all_threads=True)
        except Exception:
            pass
        runtime_log_event("startup", python=sys.executable, cwd=os.getcwd(), pid=os.getpid())
        _runtime_log_prune(log_dir)
    except Exception:
        _RUNTIME_LOG_FILE = None
        _RUNTIME_LOG_PATH = ""
    return _RUNTIME_LOG_PATH


def _runtime_log_value(value, limit=500):
    text = str(value)
    text = text.replace("\r", "\\r").replace("\n", "\\n")
    if len(text) > limit:
        text = text[:limit] + "...<truncated>"
    return text


def runtime_log_event(event, **fields):
    handle = _RUNTIME_LOG_FILE
    if handle is None:
        return
    try:
        parts = [f"[{_runtime_log_timestamp()}]", _runtime_log_value(event, 80)]
        for key in sorted(fields):
            value = fields.get(key)
            if value is None:
                continue
            parts.append(f"{key}={_runtime_log_value(value)}")
        handle.write(" ".join(parts) + "\n")
        handle.flush()
    except Exception:
        pass


def runtime_log_exception(event, exc_type, exc_value, exc_tb):
    handle = _RUNTIME_LOG_FILE
    if handle is None:
        return
    try:
        import traceback

        runtime_log_event(event, error=repr(exc_value))
        handle.write("".join(traceback.format_exception(exc_type, exc_value, exc_tb)))
        if not str(exc_value).endswith("\n"):
            handle.write("\n")
        handle.flush()
    except Exception:
        pass


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
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSize, QMimeData, QEvent
from PySide6.QtGui import QIcon, QAction, QColor, QDrag
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
        register_windows_scholarly_ui_fonts,
        themed_yes_no_question,
    )
    from AntSleap.ui.cropper import ImageCropper
    from AntSleap.ui.pdf_processing_widget import PdfProcessingWidget
    from AntSleap.ui.blink_lab import BlinkExpertTrainingReportDialog, BlinkLabWidget
    from AntSleap.ui.taxamask_agent_panel import TaxaMaskAgentPanel
    from AntSleap.core.dataset import TwoStageDataset
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
    from AntSleap.core.stl_project import STL_PROJECT_SCHEMA_VERSION, STL_PROJECT_TYPE, StlRenderedProjectManager
    from AntSleap.core.stl_review_bridge import import_stl_rendered_views_into_2d_project, register_stl_rendered_views_for_2d_review
    from AntSleap.core.part_tree import build_part_tree_groups
    from AntSleap.core.platform_open import open_path
    from AntSleap.core.runtime_device import normalize_device_preference, resolve_torch_device
    from AntSleap.core.agent_context_routes import enrich_agent_context
    from AntSleap.core.vlm_preannotation import (
        DEFAULT_VLM_PROMPT_PROFILE_ID,
        VLM_PREANNOTATION_SCHEMA_VERSION,
        default_vlm_prompt_profile,
        load_vlm_api_config_from_runtime_settings,
        run_vlm_preannotation,
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
        register_windows_scholarly_ui_fonts,
        themed_yes_no_question,
    )
    from ui.cropper import ImageCropper
    from ui.pdf_processing_widget import PdfProcessingWidget
    from ui.blink_lab import BlinkExpertTrainingReportDialog, BlinkLabWidget
    from ui.taxamask_agent_panel import TaxaMaskAgentPanel
    from core.dataset import TwoStageDataset
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
    from core.stl_project import STL_PROJECT_SCHEMA_VERSION, STL_PROJECT_TYPE, StlRenderedProjectManager
    from core.stl_review_bridge import import_stl_rendered_views_into_2d_project, register_stl_rendered_views_for_2d_review
    from core.part_tree import build_part_tree_groups
    from core.platform_open import open_path
    from core.runtime_device import normalize_device_preference, resolve_torch_device
    from core.agent_context_routes import enrich_agent_context
    from core.vlm_preannotation import (
        DEFAULT_VLM_PROMPT_PROFILE_ID,
        VLM_PREANNOTATION_SCHEMA_VERSION,
        default_vlm_prompt_profile,
        load_vlm_api_config_from_runtime_settings,
        run_vlm_preannotation,
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

from torch.utils.data import DataLoader

try:
    from AntSleap.core.panel_splitter import detect_panel_crops
except ImportError:
    from core.panel_splitter import detect_panel_crops

class InferenceThread(QThread):
    log_signal = Signal(str)
    progress_signal = Signal(int)
    result_signal = Signal(str, dict)
    finished_signal = Signal()
    
    def __init__(self, engine, img_paths, taxonomy, locator_scope, inf_params, project_route_manifest=None, model_profile_context=None, lang="en"):
        super().__init__()
        self.engine = engine
        self.img_paths = img_paths
        self.taxonomy = taxonomy
        self.locator_scope = locator_scope
        self.inf_params = inf_params
        self.project_route_manifest = dict(project_route_manifest or {})
        self.model_profile_context = dict(model_profile_context or {})
        self.lang = lang

    def run(self):
        self.log_signal.emit(tr("Starting batch inference on {0} images...", self.lang).format(len(self.img_paths)))
        count = 0
        for img_path in self.img_paths:
            preds = self.engine.predict_full_pipeline(
                img_path, 
                current_taxonomy=self.taxonomy,
                locator_scope=self.locator_scope,
                conf_thresh=self.inf_params['conf'],
                adapt_thresh=self.inf_params['adapt'],
                box_pad=self.inf_params['pad'],
                noise_floor=self.inf_params['noise_floor'],
                poly_epsilon=self.inf_params['poly_epsilon'],
                project_route_manifest=self.project_route_manifest,
                model_profile_context=self.model_profile_context,
            )
            if preds:
                self.result_signal.emit(img_path, preds)
                self.log_signal.emit(tr("Processed {0}", self.lang).format(os.path.basename(img_path)))
            
            count += 1
            self.progress_signal.emit(int(count / len(self.img_paths) * 100))
            
        self.finished_signal.emit()


class VlmPreannotationThread(QThread):
    log_signal = Signal(str)
    image_result_signal = Signal(dict)
    progress_signal = Signal(int, int, str)
    error_signal = Signal(str)
    finished_signal = Signal()

    def __init__(
        self,
        image_path,
        target_parts,
        artifacts_dir,
        api_config,
        run_id,
        grid_cols=None,
        grid_rows=None,
        min_confidence=0.25,
        prompt_profile=None,
    ):
        super().__init__()
        self.image_path = image_path
        self.target_parts = list(target_parts or [])
        self.artifacts_dir = artifacts_dir
        self.api_config = dict(api_config or {})
        self.run_id = str(run_id or time.strftime("%Y%m%d_%H%M%S"))
        self.grid_cols = int(grid_cols) if grid_cols else None
        self.grid_rows = int(grid_rows) if grid_rows else None
        self.min_confidence = float(min_confidence)
        self.prompt_profile = sanitize_vlm_prompt_profile(prompt_profile)

    def run(self):
        def mark_step(step_name):
            self.progress_signal.emit(1, 1, str(step_name))

        try:
            self.log_signal.emit(f"VLM first-mile preannotation started: {os.path.basename(self.image_path)}")
            result = run_vlm_preannotation(
                self.image_path,
                self.target_parts,
                self.artifacts_dir,
                api_config=self.api_config,
                grid_cols=self.grid_cols,
                grid_rows=self.grid_rows,
                min_confidence=self.min_confidence,
                prompt_profile=self.prompt_profile,
                run_id=self.run_id,
                progress_callback=mark_step,
            )
            self.image_result_signal.emit(result)
        except Exception as exc:
            message = str(exc)
            report_match = re.search(r"report=([^;]+)$", message)
            raw_match = re.search(r"raw_response=([^;]+);", message)
            self.image_result_signal.emit(
                {
                    "schema_version": VLM_PREANNOTATION_SCHEMA_VERSION,
                    "status": "failed",
                    "image_path": self.image_path,
                    "target_parts": self.target_parts,
                    "candidates": [],
                    "rejected": [{"part": "", "reason": message}],
                    "error": message,
                    "raw_response_path": raw_match.group(1).strip() if raw_match else "",
                    "report_path": report_match.group(1).strip() if report_match else "",
                }
            )
        finally:
            self.finished_signal.emit()


class DatasetExportThread(QThread):
    progress_signal = Signal(int, int, str)
    success_signal = Signal(int, str, str)
    error_signal = Signal(str)
    finished_signal = Signal()

    def __init__(self, project, output_dir, export_format, lang="en"):
        super().__init__()
        self.project = project
        self.output_dir = output_dir
        self.export_format = export_format
        self.lang = lang

    def run(self):
        def progress(done, total, label):
            self.progress_signal.emit(int(done), int(total), str(label or ""))

        try:
            if self.export_format == "multimodal":
                count = self.project.export_multimodal_dataset(self.output_dir, progress_callback=progress)
            elif self.export_format == "coco":
                count = self.project.export_coco(self.output_dir, progress_callback=progress)
            else:
                count = self.project.export_yolo(self.output_dir, progress_callback=progress)
            if hasattr(self.project, "write_model_profile_export_summary"):
                self.project.write_model_profile_export_summary(self.output_dir, export_format=self.export_format)
            self.success_signal.emit(int(count), self.output_dir, self.export_format)
        except Exception as exc:
            self.error_signal.emit(str(exc))
        finally:
            self.finished_signal.emit()


class ImageImportThread(QThread):
    progress_signal = Signal(int, int, str)
    success_signal = Signal(int, int)
    error_signal = Signal(str)
    finished_signal = Signal()

    def __init__(self, project, image_paths):
        super().__init__()
        self.project = project
        self.image_paths = list(image_paths or [])

    def run(self):
        def progress(done, total, label):
            self.progress_signal.emit(int(done), int(total), str(label or ""))

        try:
            added = self.project.add_images(self.image_paths, progress_callback=progress)
            self.success_signal.emit(int(added), len(self.image_paths))
        except Exception as exc:
            self.error_signal.emit(str(exc))
        finally:
            self.finished_signal.emit()


class ExternalBatchInferenceThread(QThread):
    log_signal = Signal(str)
    progress_signal = Signal(int, int, str)
    result_signal = Signal(str, dict)
    error_signal = Signal(str)
    finished_signal = Signal()

    def __init__(self, project, backend_config, image_paths, model_manifest="", lang="en"):
        super().__init__()
        self.project = project
        self.backend_config = sanitize_external_backend_config(backend_config)
        self.image_paths = list(image_paths or [])
        self.model_manifest = str(model_manifest or "")
        self.lang = lang

    def run(self):
        total = len(self.image_paths)
        self.log_signal.emit(tr("Starting batch inference on {0} images...", self.lang).format(total))
        runner = ExternalBackendRunner(self.project, self.backend_config)
        for index, image_path in enumerate(self.image_paths, start=1):
            try:
                self.progress_signal.emit(index - 1, total, str(image_path))
                result = runner.run_predict(image_path, model_manifest=self.model_manifest)
                self.result_signal.emit(str(image_path), result)
                self.log_signal.emit(tr("Processed {0}", self.lang).format(os.path.basename(str(image_path))))
                self.progress_signal.emit(index, total, str(image_path))
            except Exception as exc:
                self.error_signal.emit(str(exc))
                break
        self.finished_signal.emit()


class ExternalTrainingThread(QThread):
    log_signal = Signal(str)
    success_signal = Signal(dict)
    error_signal = Signal(str)
    finished_signal = Signal()

    def __init__(self, project, backend_config):
        super().__init__()
        self.project = project
        self.backend_config = sanitize_external_backend_config(backend_config)

    def run(self):
        try:
            self.log_signal.emit("External backend training started.")
            summary = ExternalBackendRunner(self.project, self.backend_config).run_prepare_and_train()
            self.success_signal.emit(dict(summary or {}))
        except Exception as exc:
            self.error_signal.emit(str(exc))
        finally:
            self.finished_signal.emit()

# --- Localization ---
TRANSLATIONS = {
    "zh": {
        "PROJECT IMAGES": "项目图片",
        "+ Add Images": "+ 添加图片",
        "Import & Crop": "导入并裁剪",
        "Batch Split Plates": "批量切分拼图",
        "Manual Draw": "手动绘制",
        "Magic Wand (SAM)": "魔棒 (SAM)",
        "Box Prompt (SAM)": "框选 (SAM)",
        "SAM Box Segmentation": "SAM框选分割",
        "Tool: Magic Wand (SAM) - Click to auto-segment.": "工具: 魔棒 - 点击自动分割",
        "Tool: Box Prompt (SAM) - Drag to segment area.": "工具: 框选 - 拖拽选择区域",
        "Draw a box to run SAM immediately and create a draft polygon for the current part.": "拖拽框选后立即调用 SAM，为当前部位生成草稿轮廓。",
        "Tool: Manual Draw - Click points to outline.": "工具: 手动 - 点击绘制轮廓",
        "Taxon": "分类单元",
        "Current image taxon": "当前图片物种",
        "Per-image taxon metadata used for export and literature search hints. This does not change the structure labels.": "每张图片自己的物种/分类单元元数据，用于导出和文献检索提示；不会改变结构标签。",
        "Structures": "结构标签",
        "DESCRIPTION (Linked)": "描述 (关联)",
        "Literature Traits": "文献性状",
        "Literature Trait Descriptions": "文献性状描述",
        "Search Part:": "搜索部位：",
        "Search": "搜索",
        "Structured Descriptions": "结构化描述",
        "Raw Text Blocks": "原文块搜索",
        "Raw Search Scope:": "原文检索范围：",
        "Current Taxon First": "当前物种优先",
        "Whole Current PDF": "当前 PDF 全文",
        "Replace Current Description": "替换当前描述",
        "Append to Current Description": "追加到当前描述末尾",
        "Close": "关闭",
        "Caste": "品级",
        "Part": "部位",
        "Role": "角色",
        "Block": "文本块",
        "Pages": "页码",
        "Page": "页码",
        "Conf.": "置信度",
        "Status": "状态",
        "Description": "描述",
        "Text": "文本",
        "Current Part": "当前部位",
        "Image": "图片",
        "PDF": "PDF",
        "Source PDF": "来源 PDF",
        "Source Mode": "来源模式",
        "Current image PDF source": "当前图片来源文献",
        "Same-taxon literature reference": "同物种文献引用",
        "This image is not linked to the selected PDF figure. Descriptions are matched by the current image taxon name only.": "当前图片没有关联到该 PDF 图版；这里的描述仅按当前图片物种名匹配。",
        "No PDF literature source is linked to the current image, and the current image taxon is unknown. Set the current image taxon first, or import images through the PDF candidate workflow.": "当前图片没有关联 PDF 文献来源，且当前图片物种未知。请先设置当前图片物种，或通过 PDF 候选图片流程导入。",
        "Choose Literature Database": "选择文献数据库",
        "No literature database was found automatically. Choose the PDF extraction database that contains this species?": "未自动找到文献数据库。是否选择一个包含该物种的 PDF 提取数据库？",
        "pronotum / 前胸背板 / propodeum ...": "pronotum / 前胸背板 / propodeum ...",
        "No literature description matched the current image, taxon, and part search.": "当前图片、物种和部位搜索没有匹配到文献描述。",
        "No raw PDF text block matched the current search. Try Whole Current PDF or broader terms.": "当前搜索没有匹配到 PDF 原文块。可以切换到“当前 PDF 全文”或使用更宽泛的关键词。",
        "No PDF literature source is linked to the current image. Import images through the PDF candidate workflow or open a project that preserves PDF image provenance.": "当前图片没有关联 PDF 文献来源。请通过 PDF 候选图片流程导入，或打开保留了 PDF 图片来源记录的项目。",
        "PDF literature database was not found: {0}": "未找到 PDF 文献数据库：{0}",
        "Applied literature description for {0}.": "已应用 {0} 的文献描述。",
        "Search PDF-extracted taxon/part descriptions linked to the current image and apply one to the current part description box.": "搜索与当前图片关联的 PDF 抽取物种/文献性状描述，并应用到当前部位描述框。",
        "Auto Annotation": "自动标注",
        "Parent-part annotation": "父部位标注",
        "Auto (Current)": "自动标注 (当前)",
        "Batch (All)": "批量标注 (全部)",
        "VLM First-Mile Boxes": "VLM 第一公里框",
        "VLM Pre-Annotate": "VLM 预标注",
        "VLM Pre-Label": "VLM预标注",
        "VLM Batch Pre-Label": "VLM批量预标",
        "Use the configured multimodal model to propose SAM prompt boxes for the current image. Results are draft AI boxes until reviewed.": "使用已配置的多模态模型为当前图片生成 SAM 提示框。结果在复核前只是 AI 草稿框。",
        "Use the configured multimodal model to propose draft boxes for the current image only.": "仅对当前图片调用多模态模型生成草稿框。",
        "Use the configured multimodal model to batch pre-annotate the configured image range.": "按设置的批量范围调用多模态模型批量生成草稿框。",
        "AI Multimodal Pre-Annotation:": "AI 多模态预标注：",
        "Choose which existing project structures will be sent to the multimodal model. This list is separate from main locator parts.": "选择哪些已有项目结构会发送给多模态大模型。这个列表与主定位结构分开。",
        "VLM Target Parts:": "VLM 目标部位：",
        "VLM Batch Scope:": "VLM 批量范围：",
        "All imported images": "已导入所有图像",
        "Images in selected list group": "指定图片列表分组",
        "VLM Image Group:": "VLM 图片分组：",
        "VLM API Concurrency:": "VLM API 并发数：",
        "Default is 1 to protect rate-limited API keys. Increase only if your provider explicitly allows parallel requests; high concurrency can trigger throttling, extra charges, or account blocking.": "默认 1，用于保护有速率限制的 API key。只有当服务商明确允许并行请求时再调高；高并发可能触发限速、额外费用或封号。",
        "VLM Detailed Settings": "VLM 详细设置",
        "VLM Prompt Profile:": "VLM 提示词方案：",
        "Built-in Ant Taxonomy Default": "内置蚂蚁分类学默认",
        "Project Custom Prompt": "项目自定义提示词",
        "Profile Name:": "方案名称：",
        "Research Taxon / Image Context:": "研究类群 / 图像背景：",
        "Main Body / Attachment Rules:": "主体与附属结构规则：",
        "Part Anchor Rules:": "部位锚点规则：",
        "Extra VLM Instructions:": "额外 VLM 指令：",
        "Prompt profile only changes the instructions sent to the multimodal model. The grid input, JSON schema, coordinate mapping, and SAM draft generation stay locked.": "提示词方案只改变发送给多模态模型的说明；网格输入、JSON 格式、坐标映射和 SAM 草稿生成仍保持锁定。",
        "Use the built-in ant prompt profile as a stable baseline. Choose Project Custom Prompt when adapting VLM pre-annotation to another taxon or a special image style.": "内置蚂蚁提示词方案是稳定基线。需要适配其它类群或特殊图像风格时，请选择“项目自定义提示词”。",
        "Select at least one VLM target part before running pre-annotation.": "运行预标注前，请至少选择一个 VLM 目标部位。",
        "Open VLM settings": "打开 VLM 设置",
        "Please select an image first.": "请先选择一张图片。",
        "VLM preannotation is already running.": "VLM 预标注正在运行。",
        "No target structures are available for VLM preannotation.": "当前没有可供 VLM 预标注的目标结构。",
        "Configure the Multimodal LLM API in PDF Evidence Tools first.": "请先在 PDF 文献处理工具中配置多模态 LLM API。",
        "Open API settings": "打开 API 设置",
        "VLM first-mile preannotation started for {0}.": "VLM 第一公里预标注已开始：{0}。",
        "Run VLM preannotation on all imported images?\n\nThis will call the multimodal API, may incur provider cost, and will write draft AI boxes and SAM polygons for later review.": "对已导入的所有图像运行 VLM 预标注？\n\n这会调用多模态 API，可能产生服务商费用，并写入待复核的 AI 草稿框和 SAM 掩码。",
        "Run VLM preannotation on {0} image(s) in {1}?\n\nThis will call the multimodal API, may incur provider cost, and will write draft AI boxes and SAM polygons for later review.": "对“{1}”中的 {0} 张图像运行 VLM 预标注？\n\n这会调用多模态 API，可能产生服务商费用，并写入待复核的 AI 草稿框和 SAM 掩码。",
        "VLM API concurrency: {0}. Increase this only if your provider allows parallel requests.": "VLM API 并发数：{0}。只有服务商允许并行请求时才建议调高。",
        "VLM batch progress: {0}/{1} steps ({2}).": "VLM 批量进度：{0}/{1} 步（{2}）。",
        "VLM Pre-Annotation Progress": "VLM 预标注进度",
        "Stop VLM Batch": "停止 VLM 批量任务",
        "Stop VLM preannotation after active request(s) finish?": "在已发出的请求结束后停止 VLM 预标注吗？",
        "Active API request(s) may already have been sent, but no more queued images will be processed. This helps avoid unintended large API bills.": "已经发出的 API 请求可能无法撤回，但剩余队列不会继续处理。这样可以避免意外产生大额 API 费用。",
        "VLM stop requested. Remaining queued images were cancelled; waiting for active request(s) to finish.": "已请求停止 VLM。剩余队列已取消，正在等待已发出的请求结束。",
        "VLM preannotation stopped. Images processed: {0}; queued images cancelled: {1}; saved drafts: {2}; report: {3}": "VLM 预标注已停止。已处理图像：{0}；已取消排队图像：{1}；保存草稿：{2}；报告：{3}",
        "VLM progress: stopped ({0} draft boxes; {1} queued images cancelled)": "VLM 进度：已停止（{0} 个草稿框；已取消 {1} 张排队图像）",
        "Stopping after current image...": "将在当前图片结束后停止...",
        "VLM progress: {0}% ({1}/{2}) {3}": "VLM 进度：{0}%（{1}/{2}）{3}",
        "VLM progress: {0}% ({1}/{2}) {3} - {4}": "VLM 进度：{0}%（{1}/{2}）{3} - {4}",
        "VLM progress: finished ({0} draft boxes)": "VLM 进度：完成（{0} 个草稿框）",
        "start": "开始",
        "image": "当前图像",
        "prepare": "准备输入图",
        "vlm": "调用 VLM",
        "parse": "解析结果",
        "write": "写入草稿",
        "sam": "生成 SAM 草稿",
        "report": "写入报告",
        "done": "完成当前图",
        "cancelled": "已请求停止",
        "failed": "失败",
        "no_candidates": "无可用框",
        "VLM preannotation finished. Images: {0}; saved drafts: {1}; report: {2}": "VLM 预标注完成。图像：{0}；保存草稿：{1}；报告：{2}",
        "Confirm current AI polygon drafts": "通过当前图可训练 AI 草稿",
        "Confirm batch AI polygon drafts": "批量通过可训练 AI 草稿",
        "Confirm AI Drafts": "确认 AI 草稿",
        "Only confirms AI drafts that already have polygons. Box-only drafts stay pending until SAM or manual drawing creates a polygon.": "只通过已经有多边形轮廓的 AI 草稿。仅框草稿会继续待处理，直到用 SAM 或手工绘制生成多边形。",
        "Confirms polygon AI drafts across the current project after a confirmation dialog.": "弹窗确认后，通过当前项目中已有多边形的 AI 草稿。",
        "Accept {0} AI polygon draft(s) on the current image?\n\nOnly drafts that already have a polygon will become training labels. Box-only drafts will stay pending until you run SAM from the box or redraw a polygon.": "通过当前图像 {0} 个 AI 多边形草稿吗？\n\n只有已经生成多边形轮廓的草稿会变成可训练标签。仅框草稿会继续保留为待处理，需要先用框调用 SAM 或手工重画多边形。",
        "Accept {0} AI polygon draft(s) from {1} image(s) in the current project?\n\nOnly drafts that already have polygons will become training labels. {2} box-only draft(s) will be skipped and stay pending.": "通过当前项目中 {1} 张图像里的 {0} 个 AI 多边形草稿吗？\n\n只有已经生成多边形轮廓的草稿会变成可训练标签。{2} 个仅框草稿会被跳过并继续保留为待处理。",
        "Accepted {0} AI draft(s) on current image.": "已通过当前图像 {0} 个 AI 草稿。",
        "Accepted {0} AI polygon draft(s) from {1} image(s) in the current project.": "已通过当前项目中 {1} 张图像里的 {0} 个 AI 多边形草稿。",
        "No reviewable AI polygon drafts on current image.": "当前图像没有可通过的 AI 多边形草稿。",
        "No reviewable AI polygon drafts in the current project.": "当前项目中没有可通过的 AI 多边形草稿。",
        "Current image still has {0} AI box-only draft(s): {1}. Box-only drafts cannot enter training; run SAM from the box or redraw a polygon first.": "当前图像还有 {0} 个仅框 AI 草稿：{1}。仅框草稿不能进入训练；请先用框调用 SAM 或手工重画多边形。",
        "{0} image(s) in the current project still have {1} AI box-only draft(s). Box-only drafts cannot enter training; run SAM from the box or redraw polygons first.": "当前项目中还有 {0} 张图像共 {1} 个仅框 AI 草稿。仅框草稿不能进入训练；请先用框调用 SAM 或手工重画多边形。",
        "SAM draft failed for {0}: {1}": "SAM 草稿生成失败：{0}，原因：{1}",
        "VLM part coverage for {0}: requested [{1}]; returned [{2}]; missing [{3}].": "VLM 部位覆盖（{0}）：请求 [{1}]；返回 [{2}]；缺失 [{3}]。",
        "VLM first-mile preannotation returned no usable boxes.": "VLM 第一公里预标注没有返回可用框。",
        "VLM preannotation saved {0} draft(s): {1} SAM polygon(s), {2} box-only draft(s), skipped {3}. Report: {4}": "VLM 预标注已保存 {0} 个草稿：{1} 个 SAM 多边形，{2} 个仅框草稿，跳过 {3} 个。报告：{4}",
        "VLM first-mile preannotation failed: {0}": "VLM 第一公里预标注失败：{0}",
        "Could not read the current image.": "无法读取当前图片。",
        "Current Image": "当前图片",
        "Train Models": "训练模型",
        "Training Scope:": "训练范围：",
        "All Images": "全部图片",
        "All Images ({0})": "全部图片（{0}）",
        "{0} ({1})": "{0}（{1}）",
        "Training scope: {0} ({1} image(s))": "训练范围：{0}（{1} 张图片）",
        "Selected training scope is empty. Choose another image group or add images to this group first.": "当前训练范围没有图片。请换一个图像标签，或先把图片加入这个标签。",
        "Parent-part image-group training is available for the built-in Locator/SAM backend. Custom parent extensions still receive the full project contract.": "父部位按图像标签训练目前用于内置 Locator/SAM 后端。自定义父部位拓展仍会收到完整项目契约。",
        "Choose All Images to run this custom parent extension, or switch the active profile to Built-in Locator + SAM for image-group training.": "如需运行自定义父部位拓展，请选择“全部图片”；如需按图像标签训练，请把当前模型方案切回“内置 Locator + SAM”。",
        "LOGS": "日志",
        "Export Dataset": "导出数据集",
        "Export Multimodal Dataset": "导出多模态数据",
        "Model Settings": "模型设置",
        "2D/STL Model Settings": "2D/STL 模型设置",
        "General Settings": "通用设置",
        "General Application Settings": "软件通用设置",
        "Application Preferences": "软件使用偏好",
        "General settings control the whole application: language, theme, startup behavior, autosave, and the default compute device. Workflow-specific training parameters stay in their own model settings.": "通用设置只控制整个软件的使用习惯：语言、主题、启动方式、自动保存和默认计算设备。具体工作流的训练参数放在各自的模型设置里。",
        "Language:": "语言：",
        "Theme:": "主题：",
        "Startup Behavior:": "启动方式：",
        "Show Start Center": "显示启动中心",
        "Continue last project automatically": "自动继续上次项目",
        "Project Autosave Interval (seconds):": "项目自动保存间隔（秒）：",
        "Default Runtime Device:": "默认计算设备：",
        "Runtime device here is the default for built-in 2D/STL models and other internal Torch tasks. Custom extensions use the Python executable and commands configured in Advanced Extensions.": "这里的计算设备是内置 2D/STL 模型和其他内部 Torch 任务的默认值。自定义拓展使用高级拓展中配置的 Python 解释器和命令。",
        "Only the audited dark theme is currently enabled.": "当前只启用已经检查过的深色主题。",
        "Autosave interval must be a positive number.": "自动保存间隔必须是正数。",
        "General settings updated.": "通用设置已更新。",
        "2D/STL Morphology Model Settings": "2D/STL 形态学模型设置",
        "2D/STL morphology settings control rendered STL views and ordinary morphology images.": "2D/STL 形态学设置控制 STL 渲染视角图和普通形态图片。",
        "Training Data Safety": "训练数据安全规则",
        "Training source: manual_truth only.": "训练来源：仅 manual_truth 人工真值。",
        "Prediction import: model_draft layer.": "预测导入：进入 model_draft 草稿层。",
        "Manual truth is never overwritten automatically.": "人工真值不会被自动覆盖。",
        "Export Formats:": "导出格式：",
        "Supported export formats: {0}": "支持的导出格式：{0}",
        "Invalid Settings": "设置无效",
        "Workflow": "工作流",
        "Start Center": "启动中心",
        "TaxaMask Workflow Selection": "TaxaMask 工作流选择",
        "TaxaMask Agent Center": "TaxaMask Agent 中心",
        "Choose the data type you want to work with today.": "选择今天要处理的数据类型。",
        "Ask Ant-Code to configure workflows, inspect errors, prepare PDF evidence, or plan training. Use the right rail when you want to enter a workbench directly.": "让 Ant-Code 帮你配置工作流、检查报错、准备 PDF 文献处理或规划训练。需要直接进入工作台时，使用右侧入口。",
        "Project Console": "项目控制台",
        "Expand Project Console": "展开项目控制台",
        "Collapse Project Console": "折叠项目控制台",
        "Current workflow": "当前工作流",
        "Current project": "当前项目",
        "2D/STL images": "2D/STL 图片",
        "PDF evidence": "PDF 文献处理",
        "Ant-Code ready": "Ant-Code 已就绪",
        "Ant-Code stopped": "Ant-Code 未启动",
        "Repository only; no research project selected": "仅仓库上下文；尚未选择研究项目",
        "Recent project: {0}": "最近项目：{0}",
        "2D project: {0}": "2D 项目：{0}",
        "STL rendered-view project: {0}": "STL 渲染视角图项目：{0}",
        "{0} image(s), {1} labeled, {2} STL rendered 2D view(s)": "{0} 张图片，{1} 张已有人工标注，{2} 张 STL 渲染 2D 视角图",
        "PDF literature workflow ready; {0} review candidate(s)": "PDF 文献处理向导已就绪；{0} 个候选图待复核",
        "PDF literature workflow docs missing": "PDF 文献处理上下文文档未找到",
        "STL source stays as exported high-resolution 2D views; TaxaMask does not label 3D meshes.": "STL 来源保持为外部导出的高分辨率 2D 视角图；TaxaMask 不做 3D mesh 标注。",
        "Start Ant-Code": "启动 Ant-Code",
        "Stop Ant-Code": "停止 Ant-Code",
        "Agent status: {0}": "Agent 状态：{0}",
        "2D / STL morphology annotation": "2D / STL 形态学标注",
        "Annotate high-resolution 2D views rendered from STL, or ordinary 2D morphology images, then train Locator/SAM/Blink models.": "标注从 STL 导出的高分辨率 2D 视角图，或普通 2D 形态图像，并训练 Locator/SAM/Blink 模型。",
        "PDF evidence workflow": "PDF 文献处理流程",
        "Use Agent first to confirm the target taxon, screening rules, figure extraction scope, evidence indexes, candidate review, and safe import.": "先让 Agent 确认目标类群、筛选规则、图文提取范围、证据索引、候选复核和安全导入。",
        "Plan PDF workflow with Agent": "让 Agent 规划 PDF 流程",
        "Open PDF tools": "打开 PDF 工具",
        "Continue last project": "继续上次项目",
        "No recent project": "暂无最近项目",
        "Enter 2D/STL workflow": "进入 2D/STL 工作流",
        "Open any project": "打开任意项目",
        "Create 2D/STL project": "新建 2D/STL 项目",
        "Open 2D/STL Project": "打开 2D/STL 项目",
        "2D/STL Morphology Workflow": "2D/STL 形态学工作流",
        "Opened 2D/STL workflow.": "已进入 2D/STL 工作流。",
        "Ask Agent": "询问 Agent",
        "Ask Agent about these settings. Current values are summarized without sending full command text.": "询问 Agent 这些设置。只发送当前值摘要，不发送完整命令文本。",
        "Local task cards": "本地任务卡",
        "Idle": "空闲",
        "No active project": "未打开项目",
        "Model Backend:": "模型后端：",
        "Built-in Locator + SAM": "内置 Locator + SAM",
        "External Script Backend": "外部脚本后端",
        "Runtime Device:": "运行设备：",
        "Auto (CUDA if available)": "自动（有 CUDA 则使用）",
        "CPU only": "仅 CPU",
        "CUDA GPU": "CUDA 显卡",
        "Controls built-in Locator/SAM/Blink training and inference. External backends use their own command environment. CPU can run small tests, but CUDA is recommended for real training.": "控制内置 Locator/SAM/Blink 的训练和推理。自定义拓展使用自己的命令环境。CPU 可用于小规模测试，正式训练建议使用 CUDA。",
        "Controls built-in Locator/SAM/Blink training and inference. Custom extensions use their own command environment. CPU can run small tests, but CUDA is recommended for real training.": "控制内置 Locator/SAM/Blink 的训练和推理。自定义拓展使用自己的命令环境。CPU 可用于小规模测试，正式训练建议使用 CUDA。",
        "Runtime device resolved to: {0}": "运行设备已解析为：{0}",
        "Active model profile updated with trained parent weights.": "当前模型方案已记录本次训练得到的父部位权重。",
    "External Backend": "高级拓展",
        "Advanced Extensions": "高级拓展",
    "Backend ID:": "后端 ID：",
        "Extension ID:": "拓展 ID：",
    "Display Name:": "显示名称：",
    "Python Executable:": "Python 解释器：",
    "Prepare Dataset Command:": "数据准备命令：",
    "Train Command:": "训练命令：",
    "Predict Command:": "推理命令：",
    "Model Manifest Path:": "模型 manifest 路径：",
    "Validate External Backend": "校验外部后端",
    "External backend note:": "外部后端说明：",
    "Use this advanced entry when you want TaxaMask to call your own training or prediction scripts. Commands run in an isolated external_runs directory and receive a contract JSON path through {contract} or {contract_json}. When this backend is selected, built-in Locator/SAM training and prediction do not run for that task.": "当你希望 TaxaMask 调用自己的训练或推理脚本时使用这个高级入口。命令会在独立的 external_runs 目录中运行，并通过 {contract} 或 {contract_json} 接收契约 JSON 路径。选择该后端后，本次任务不会运行内置 Locator/SAM 训练或推理。",
        "Advanced extensions collect high-impact model source switches plus custom script and manifest settings for the current model profile. Parent-part and child-part pages show the active sources as read-only summaries.": "高级拓展集中保存当前模型方案里的关键模型来源切换，以及自定义脚本和 manifest 设置。父部位、子部位页面只读展示当前生效来源。",
        "Advanced extension order: 1) choose or save the model profile, 2) choose parent/default child model sources, 3) fill the parent or child custom extension blocks only when those sources are selected.": "高级拓展按运行关系排列：1）选择或保存模型方案；2）选择父部位/默认子部位模型来源；3）只有选中自定义来源时，下面的父部位或子部位自定义拓展才会参与运行。",
        "1. Model Profiles": "1. 模型方案",
        "2. Model Source Switches": "2. 模型来源切换",
        "3. Parent-part Custom Extension": "3. 父部位自定义拓展",
        "4. Child-part Custom Extension": "4. 子部位自定义拓展",
        "Use this advanced entry when you want TaxaMask to call your own parent-part training or prediction scripts. Commands run in an isolated external_runs directory and receive a contract JSON path through {contract} or {contract_json}. When Parent Model Source is set to Custom Parent Extension for the active model profile, built-in Locator/SAM training and prediction do not run for that task.": "当你希望 TaxaMask 调用自己的父部位训练或推理脚本时，在这里配置。命令会在独立的 external_runs 目录中运行，并通过 {contract} 或 {contract_json} 接收契约 JSON 路径。当当前模型方案的父部位模型来源设为“自定义父部位拓展”时，本次任务不会运行内置 Locator/SAM 训练或推理。",
        "Compatibility display only. Choose Parent Model Source in Advanced Extensions to switch the active parent model source.": "这里只是旧字段兼容显示。要切换实际父部位模型来源，请在“高级拓展”页选择父部位模型来源。",
    "External backend configuration looks valid.": "父部位拓展配置看起来可用。",
    "External backend needs at least a train command or a predict command.": "父部位拓展至少需要填写训练命令或推理命令。",
        "External backend command '{0}' must include {contract} or {contract_json}.": "父部位拓展命令“{0}”必须包含 {contract} 或 {contract_json}。",
        "External backend ID is required.": "父部位拓展 ID 不能为空。",
        "Parent extension configuration looks valid.": "父部位拓展配置看起来可用。",
        "Parent extension needs at least a train command or a predict command.": "父部位拓展至少需要填写训练命令或推理命令。",
        "Parent extension command '{0}' must include {contract} or {contract_json}.": "父部位拓展命令“{0}”必须包含 {contract} 或 {contract_json}。",
        "Parent extension ID is required.": "父部位拓展 ID 不能为空。",
        "Model Profiles": "模型方案",
        "Profile": "方案",
        "Current Model Profile:": "当前模型方案：",
        "Profile ID:": "方案 ID：",
        "Profile Display Name:": "方案显示名称：",
        "Profile Description:": "方案说明：",
        "Profile Summary:": "方案摘要：",
        "New Profile": "新建方案",
        "Save Current Settings as New Profile": "从当前设置保存为新方案",
        "Copy Profile": "复制方案",
        "Delete Profile": "删除方案",
        "Set Active": "设为当前方案",
        "Set as Active Profile": "设为当前方案",
        "{0} (active)": "{0}（当前）",
        "Project profile changes are saved into the current project JSON. The old global settings are still synchronized for compatibility.": "方案改动会保存到当前项目 JSON。旧的全局设置仍会同步，保证已有训练和推理入口兼容。",
        "Project profile changes are saved into the current project JSON. Save the current controls as a profile after configuring and validating the backend you want to reuse.": "模型方案会保存到当前项目 JSON。请先配置并校验想复用的模型来源或高级拓展，再把当前控件保存为方案。",
        "Project profile changes are saved into the current project JSON. Save the current controls as a profile after choosing the model sources and validating any advanced extensions you want to reuse.": "模型方案会保存到当前项目 JSON。请先选择模型来源，并校验想复用的高级拓展，再把当前控件保存为方案。",
        "Parent extension settings are saved inside the current model profile when Parent Model Source is set to Custom Parent Extension.": "当父部位模型来源设为“自定义父部位拓展”时，这里的父部位拓展配置会保存到当前模型方案中。",
        "External parent backend settings are saved inside the current model profile when Parent Backend is set to External Parent Backend.": "当父部位模型来源设为“自定义父部位拓展”时，这里的父部位拓展配置会保存到当前模型方案中。",
        "Child extension settings are saved inside the current model profile when Default Child Backend is set to Custom Child Extension.": "当默认子部位专家设为“自定义子部位拓展”时，这里的子部位拓展配置会保存到当前模型方案中。",
        "External Blink backend settings are saved inside the current model profile when Default Child Backend is set to External Blink Expert.": "当默认子部位专家设为“自定义子部位拓展”时，这里的子部位拓展配置会保存到当前模型方案中。",
        "Active now: parent-part training and Auto annotation will call this custom parent extension.": "当前生效：父部位训练和自动标注会调用这个自定义父部位拓展。",
        "Not active now: parent-part tasks use Built-in Locator + SAM. These fields are saved for profiles that switch Parent Model Source to Custom Parent Extension.": "当前未生效：父部位任务会使用内置 Locator + SAM。这里的字段会保留给切换到“自定义父部位拓展”的模型方案使用。",
        "Active now: this custom child extension is the default child expert for unresolved routes. Appointed route experts still keep their own bindings.": "当前生效：这个自定义子部位拓展会作为未指定路由的默认子部位专家。已经指定的路由专家仍保留自己的绑定。",
        "Not active now: the default child expert is {0}. These fields are saved for profiles that switch Default Child Expert to Custom Child Extension.": "当前未生效：默认子部位专家是 {0}。这里的字段会保留给切换到“自定义子部位拓展”的模型方案使用。",
        "Model Source Switches": "模型来源切换",
        "Choose the high-impact model sources for the current profile here. Existing child route experts stay route-specific; this default mainly affects new/default child expert training and unresolved route defaults.": "在这里选择当前方案的关键模型来源。已有子部位路由专家仍按各自路由保存；这个默认值主要影响新建/默认子部位专家训练，以及未明确指定时的路由默认值。",
        "Current parent model source: {0}": "当前父部位模型来源：{0}",
        "Current default child expert: {0}": "当前默认子部位专家：{0}",
        "Read-only summary. Change this source in Advanced Extensions.": "只读摘要。请在“高级拓展”中切换。",
        "Parent source changes parent-part training and Auto annotation. Custom Parent Extension calls the configured script below instead of built-in Locator/SAM.": "父部位来源会改变父部位训练和自动标注链路。选择自定义父部位拓展后，会调用下方配置的脚本，而不是内置 Locator/SAM。",
        "Default child expert affects new/default child expert training. During inference, each appointed parent -> child route calls the backend recorded on that route.": "默认子部位专家会影响新建/默认子部位专家训练。推理时，每条已指定的父部位 -> 子部位路由会调用该路由记录的后端。",
        "Project active profile: {0}": "项目当前方案：{0}",
        "Parent backend: {0}": "父部位后端：{0}",
        "Main locator parts: {0}": "主定位部位：{0}",
        "Default child backend: {0}": "默认子部位后端：{0}",
        "Route-specific experts differing from this default: {0}": "与此默认后端不同的路由专家：{0}",
        "Inference: conf={0}, pad={1}, noise={2}": "推理参数：置信度={0}，扩框={1}，底噪={2}",
        "Existing route experts are kept as route-specific bindings; switching profiles does not silently reappoint trained child experts.": "已有路由专家会保留为单独路由绑定；切换方案不会悄悄重新指定已经训练好的子部位专家。",
        "External parent backend: {0}": "父部位拓展：{0}",
        "External Blink backend: {0}": "子部位拓展：{0}",
        "configured": "已配置",
        "missing train/predict command": "缺少训练/推理命令",
        "missing predict command": "缺少推理命令",
        "none": "无",
        "No model profile selected.": "未选择模型方案。",
        "The built-in default profile cannot be deleted.": "内置默认方案不能删除。",
        "At least one model profile must remain in the project.": "项目中至少需要保留一个模型方案。",
        "Delete model profile {0}?\n\nThis removes only the saved profile configuration from the current project. Model weights, external scripts, and route expert bindings are not deleted.": "删除模型方案 {0}？\n\n这只会删除当前项目中保存的方案配置，不会删除模型权重、外部脚本或路由专家绑定。",
        "Set {0} as the active model profile?": "将 {0} 设为当前模型方案？",
        "Parent backend: {0} -> {1}": "父部位后端：{0} -> {1}",
        "Default child backend: {0} -> {1}": "默认子部位后端：{0} -> {1}",
        "Route-specific experts differing from the target default: {0}": "与目标默认后端不同的路由专家：{0}",
        "Existing route experts stay appointed; this switch only changes the project default profile.": "已有路由专家会继续保持指定；本次切换只改变项目默认模型方案。",
        "Parent-part annotation": "父部位标注",
        "Child-part annotation": "子部位标注",
        "Parent Backend:": "父部位模型来源：",
        "Parent Model Source:": "父部位模型来源：",
        "External Parent Backend": "自定义父部位拓展",
        "Custom Parent Extension": "自定义父部位拓展",
        "Default Child Backend:": "默认子部位专家：",
        "Default Child Expert:": "默认子部位专家：",
        "ViT-B Blink Expert": "ViT-B Blink 专家",
        "Heatmap Blink Expert": "热力图 Blink 专家",
        "External Blink Expert": "自定义子部位拓展",
        "Custom Script Extension": "自定义脚本拓展",
        "Custom Child Extension": "自定义子部位拓展",
        "Heatmap Blink Parameters:": "热力图 Blink 参数：",
        "Heatmap Input Size:": "热力图输入尺寸：",
        "Heatmap Sigma:": "热力图 Sigma：",
        "WH Loss Weight:": "宽高回归损失权重：",
        "Center Loss Weight:": "中心点损失权重：",
        "Parent-part Custom Extension": "父部位自定义拓展",
        "Child-part Custom Extension": "子部位自定义拓展",
        "External Blink Backend:": "子部位自定义拓展：",
        "External Blink Backend ID:": "子部位拓展 ID：",
        "External Blink Display Name:": "子部位拓展显示名称：",
        "External Blink Python Executable:": "子部位拓展 Python 解释器：",
        "External Blink Predict Command:": "子部位拓展推理命令：",
        "External Blink Train Command:": "子部位拓展训练命令：",
        "External Blink Model Manifest:": "子部位拓展模型 manifest：",
        "Child Extension ID:": "子部位拓展 ID：",
        "Child Extension Display Name:": "子部位拓展显示名称：",
        "Child Extension Python Executable:": "子部位拓展 Python 解释器：",
        "Child Extension Predict Command:": "子部位拓展推理命令：",
        "Child Extension Train Command:": "子部位拓展训练命令：",
        "Child Extension Model Manifest:": "子部位拓展模型 manifest：",
        "Validate External Blink Backend": "校验子部位拓展",
        "Validate Parent Extension": "校验父部位拓展",
        "Validate Child Extension": "校验子部位拓展",
        "External Blink backend configuration looks valid.": "子部位拓展配置看起来可用。",
        "External Blink backend needs a predict command before it can be used for child-part annotation.": "子部位拓展需要填写推理命令，才能用于子部位标注。",
        "External Blink backend command '{0}' must include {contract} or {contract_json}.": "子部位拓展命令“{0}”必须包含 {contract} 或 {contract_json}。",
        "External Blink backend ID is required.": "子部位拓展 ID 不能为空。",
        "Child extension configuration looks valid.": "子部位拓展配置看起来可用。",
        "Child extension needs a predict command before it can be used for child-part annotation.": "子部位拓展需要填写推理命令，才能用于子部位标注。",
        "Child extension command '{0}' must include {contract} or {contract_json}.": "子部位拓展命令“{0}”必须包含 {contract} 或 {contract_json}。",
        "Child extension ID is required.": "子部位拓展 ID 不能为空。",
        "Training": "训练",
        "Inference": "推理",
        "Language": "语言",
        "Theme": "主题",
        "Dark Mode": "深色模式",
        "File": "文件",
        "Settings": "设置",
        "Epochs:": "训练轮数 (Epochs):",
        "Batch Size:": "批次大小 (Batch Size):",
        "Blink Expert Training Defaults:": "Blink 专家训练默认值：",
        "Blink Training Strategy:": "Blink 训练方案：",
        "Choose which Blink training process to use for child-part experts. Plan 1 is the current baseline; Plan 2 removes outside-view training; Plan 3 trains full-view first and inside-view second.": "选择子部位专家使用哪种 Blink 训练流程。方案一是当前基线；方案二去掉外视角训练；方案三先训练全图视角，再训练内视角。",
        "Default Blink Epochs:": "默认 Blink 训练轮数：",
        "Default Blink Batch Size:": "默认 Blink 批次大小：",
        "Default Blink Learning Rate:": "默认 Blink 学习率：",
        "Default Blink Weight Decay:": "默认 Blink 权重衰减：",
        "Default Blink Input Size:": "默认 Blink 输入尺寸：",
        "Auto-shrink Steps:": "自动收缩步数：",
        "Number of interpolation steps from the loose shrink start box to the final target box. 20 steps saves 21 trajectory frames including the starting frame.": "从宽松收缩起始框到最终目标框的插值步数。20 步会保存包含起始帧在内的 21 个轨迹帧。",
        "These defaults are shown in Child Expert Session when the app starts or settings are saved. You can still adjust them for a single expert before training.": "这些默认值会在应用启动或保存设置后显示到子部位专家会话。训练单个专家前仍可在会话中临时调整。",
        "Parent Box Aspect Ratios:": "父级框长宽比：",
        "Used when the main labeling workbench draws parent context boxes. Enter each as width : height, for example 4 : 3. Child boxes and Blink shrink start boxes stay free-ratio.": "主标注工作台绘制父级上下文框时使用。请按宽 : 高输入，例如 4 : 3。子部位框和 Blink 收缩起始框保持自由比例。",
        "Width": "宽",
        "Height": "高",
        "Parent box ratio for {0} must have positive width and height values.": "{0} 的父级框比例必须填写正数宽度和高度。",
        "Learning Rate:": "学习率 (LR):",
        "Weight Decay (L2 Reg):": "权重衰减 (L2正则):",
        "Main Locator Parts:": "主定位结构：",
        "Choose which structures the built-in Locator should learn as large, stable targets. Small structures can stay in Structures and be refined with SAM, Blink, or an external backend.": "选择哪些结构交给内置 Locator 作为大而稳定的目标来学习。小结构仍可保留在结构标签中，再通过 SAM、Blink 或自定义拓展精修。",
        "Choose which structures the built-in Locator should learn as large, stable targets. Small structures can stay in Structures and be refined with SAM, Blink, or a custom extension.": "选择哪些结构交给内置 Locator 作为大而稳定的目标来学习。小结构仍可保留在结构标签中，再通过 SAM、Blink 或自定义拓展精修。",
        "At least one main locator part must be selected.": "至少需要选择一个主定位结构。",
        "Train from Scratch (Reset Weights)": "从头训练 (重置权重)",
        "Validation Report %:": "测试集展示比例 (%):",
        "Confidence Threshold:": "置信度阈值:",
        "Adaptive Thresh Ratio:": "自适应阈值比例:",
        "Box Padding Ratio:": "框扩展比例:",
        "Noise Floor:": "底噪阈值:",
        "Polygon Simplification (px):": "多边形简化度 (px):",
        "Cancel": "取消",
        "Close": "关闭",
        "Save": "保存",
        "Export": "导出",
        "Export Progress": "导出进度",
        "Preparing dataset export...": "正在准备导出数据集...",
        "Exporting dataset...": "正在导出数据集...",
        "Exporting dataset: {0}": "正在导出数据集：{0}",
        "Dataset export is already running.": "数据集正在导出中。",
        "Dataset export failed: {0}": "数据集导出失败：{0}",
        "Exported {0} samples.\n\nOutput folder: {1}": "已导出 {0} 个样本。\n\n输出文件夹：{1}",
        "Image Import": "图片导入",
        "Image Import Progress": "图片导入进度",
        "Preparing image import...": "正在准备导入图片...",
        "Importing images: {0}/{1}": "正在导入图片：{0}/{1}",
        "Importing images: {0}/{1}\n{2}": "正在导入图片：{0}/{1}\n{2}",
        "Imported {0}/{1} image(s).": "已导入 {0}/{1} 张图片。",
        "Image import is already running.": "图片导入正在进行中。",
        "Image import is running. Please wait for it to finish before closing TaxaMask.": "图片导入正在进行中，请等待完成后再关闭 TaxaMask。",
        "Image import failed: {0}": "图片导入失败：{0}",
        "Batch inference is already running.": "批量推理正在进行中。",
        "Batch inference is running. Please wait for it to finish before closing TaxaMask.": "批量推理正在进行中，请等待完成后再关闭 TaxaMask。",
        "External batch inference failed: {0}": "外部批量推理失败：{0}",
        "External batch inference finished.": "外部批量推理已结束。",
        "External backend training is running. Please wait for it to finish before closing TaxaMask.": "外部后端训练正在进行中，请等待完成后再关闭 TaxaMask。",
        "Browse": "浏览",
        "Select Directory": "选择目录",
        "Export Format:": "导出格式:",
        "Export Path:": "导出路径:",
        "No Labels": "无标签",
        "Annotate images first!": "请先标注图片！",
        "Starting training on active compute device...": "开始在当前计算设备上训练...",
        "Training Locator...": "正在训练定位器...",
        "Training Segmentation...": "正在训练分割器...",
        "Training Finished! Weights saved.": "训练完成！权重已保存。",
        "Batch Inference": "批量推理",
        "Clear AI Labels": "清除 AI 标签",
        "Run auto-annotation on {0} images?\nThis may take a while.": "对 {0} 张图片进行自动标注？\n这可能需要一段时间。",
        "Batch Complete": "批量完成",
        "Batch inference finished.": "批量推理已结束。",
        "System Initialized. Starting SAM loader in 1s...": "系统初始化。1秒后加载 SAM...",
        "Initializing SAM (Segment Anything) on active compute device...": "正在当前计算设备上初始化 SAM...",
        "SAM Model Loaded and Ready!": "SAM 模型加载完毕！",
        "Warning: SAM weights not found at {model_path}": "警告：未在 {model_path} 找到 SAM 权重",
        "Enable Morphometrics": "启用形态测量",
        "Scale Tool": "标尺工具",
        "Tool: Scale - Drag to define 1mm.": "工具: 标尺 - 拖动定义1mm长度。",
        "Enter length in mm:": "输入长度 (mm):",
        "Measurements": "测量数据",
        "Area:": "面积:",
        "Perimeter:": "周长:",
        "Scale set to {:.2f} px/mm": "标尺已设定: {:.2f} px/mm",
        "Open Project": "打开项目",
        "TaxaMask Projects (*.json);;All Files (*)": "TaxaMask 项目 (*.json);;所有文件 (*)",
        "Migrate 2D Project to SQLite": "迁移 2D 项目到 SQLite",
        "Migrating 2D project to SQLite...": "正在迁移 2D 项目到 SQLite...",
        "This is an older 2D JSON project. TaxaMask now stores 2D projects in SQLite so large annotation projects are saved incrementally instead of rewriting one large JSON file.\n\nThe old JSON will not be overwritten. A SQLite database, a manifest file, a migration report, and a legacy JSON backup will be created next to the project.\n\nMigrate and open the SQLite project now?": "这是旧版 2D JSON 项目。TaxaMask 现在会把 2D 项目保存到 SQLite，这样大型标注项目可以增量保存，而不是反复重写一个很大的 JSON 文件。\n\n旧 JSON 不会被覆盖。程序会在项目旁边生成 SQLite 数据库、manifest 入口文件、迁移报告和旧 JSON 备份。\n\n现在迁移并打开 SQLite 项目吗？",
        "A migrated SQLite version already exists for this old JSON project.\n\nOpen the existing SQLite manifest instead?\n\n{0}": "这个旧 JSON 项目旁边已经有迁移后的 SQLite 版本。\n\n改为打开现有 SQLite manifest 吗？\n\n{0}",
        "2D project migration failed. The old JSON was not modified.\n\n{0}": "2D 项目迁移失败。旧 JSON 未被修改。\n\n{0}",
        "Migrated legacy 2D JSON project to SQLite. Manifest: {0}; database: {1}; report: {2}": "已将旧版 2D JSON 项目迁移到 SQLite。Manifest：{0}；数据库：{1}；报告：{2}",
        "New Project": "新建项目",
        "Open STL Rendered-View Project": "打开 STL 渲染视图项目",
        "Project Template:": "项目模板：",
        "Generic taxonomy mask project": "通用分类掩码项目",
        "Ant morphology (validated example)": "蚂蚁形态学（已验证示例）",
        "Save Project": "保存项目",
        "Backup SQLite Project": "备份 SQLite 项目",
        "Export Legacy JSON": "导出 legacy JSON",
        "Open Migration Report": "打开迁移报告",
        "The current project is not a SQLite-backed project.": "当前项目不是 SQLite 主存储项目。",
        "SQLite project backup failed.\n\n{0}": "SQLite 项目备份失败。\n\n{0}",
        "SQLite project backup was skipped because a recent backup already exists.": "已存在较新的 SQLite 备份，本次跳过。",
        "SQLite project backup created. Manifest: {0}; database: {1}": "已创建 SQLite 项目备份。Manifest：{0}；数据库：{1}",
        "SQLite backup created.\n\nOpen this manifest to inspect the backup:\n{0}": "SQLite 备份已创建。\n\n可打开这个 manifest 检查备份：\n{0}",
        "Legacy JSON export failed.\n\n{0}": "legacy JSON 导出失败。\n\n{0}",
        "Exported SQLite project to legacy JSON for audit. Path: {0}; stats: {1}": "已将 SQLite 项目导出为用于审计的 legacy JSON。路径：{0}；统计：{1}",
        "Legacy JSON export created:\n{0}": "legacy JSON 导出已创建：\n{0}",
        "No migration report is recorded for this project.": "这个项目没有记录迁移报告。",
        "Migration report path:\n{0}": "迁移报告路径：\n{0}",
        "Import STL Rendered Views to Labeling Workbench": "导入 STL 渲染视角图到标注工作台",
        "Specimen ID:": "Specimen 编号：",
        "Imported STL rendered views into the Labeling Workbench from {0}. Registered views: {1}, specimens: {2}, unparsed files: {3}.": "已从 {0} 将 STL 渲染视角图导入标注工作台。登记视角图：{1}，Specimen 数：{2}，未解析文件：{3}。",
        "Registered STL rendered-view project into the Labeling Workbench. Views: {0}, missing files: {1}.": "已将 STL 渲染视图项目登记进标注工作台。视角图：{0}，缺失文件：{1}。",
        "Check / Relocate Project Images": "检查/重定位项目图片",
        "Project Image Health": "项目图片健康检查",
        "Project has {0}/{1} image paths available. Missing: {2}.": "项目共有 {1} 条图片路径，当前可访问 {0} 条，缺失 {2} 条。",
        "All project image paths are available.": "当前项目图片路径全部可访问。",
        "Select New Image Root": "选择新的图片根目录",
        "Relocation Preview": "重定位预览",
        "Matched {0} missing image path(s). Still unresolved: {1}.\n\nPreview:\n{2}\n\nApply this remap and save the project?": "已匹配 {0} 条缺失图片路径，仍未解决 {1} 条。\n\n预览：\n{2}\n\n是否应用这次重定位并保存项目？",
        "No missing image paths could be matched under the selected folder.": "在所选文件夹下没有匹配到缺失图片路径。",
        "Remapped {0} project image path(s).": "已重定位 {0} 条项目图片路径。",
        "Head": "头部 (Head)",
        "Mesosoma": "胸部 (Mesosoma)",
        "Thorax": "胸部 (Thorax)", 
        "Gaster": "腹部 (Gaster)",
        "Mandible": "上颚 (Mandible)",
        "Eye": "复眼 (Eye)",
        "Unknown": "未知 (Unknown)",
        "Labeling Workbench": "标注工作台",
        "PDF Processing": "文献处理",
        "PDF Evidence Tools": "PDF 文献处理工具",
        "Open PDF Evidence Tools": "打开 PDF 文献处理工具",
        "Opened STL rendered-view project and registered it into the Labeling Workbench: {0}": "已打开 STL 渲染视图项目，并登记进标注工作台：{0}",
        "Add Structure": "添加结构标签",
        "Rename Structure": "重命名结构标签",
        "Remove Structure": "删除结构标签",
        "Crop this Image": "裁剪此图片",
        "Remove Image": "移除图片",
        "Run automatic panel splitting on {0} original image(s)?\n\nDetected crops will be added after the original images. Please review the generated crops before training.": "对 {0} 张原图执行自动拼图切分？\n\n检测到的裁剪图会追加在原图后面。训练前请先复核生成的小图。",
        "Panel splitting finished: {0} crop(s) from {1} image(s); hard-joined candidate plates needing review: {2}; no split detected/errors: {3}.": "拼图切分完成：从 {1} 张图片生成 {0} 张裁剪图；硬拼接候选需复核 {2} 张；未检测到或读取失败 {3} 张。",
        "Panel splitting cancelled.": "拼图切分已取消。",
        "No panel crops were detected.": "未检测到可切分的拼图。",
        "Original Images": "原图",
        "Split Crops": "切分图",
        "Hard-joined Candidates": "硬拼接候选",
        "Manual Split Done": "已完成手动切分",
        "Manual Split Needed": "待手动切分",
        "Custom Image Groups": "自定义图片分组",
        "New Image Group": "新建图片分组",
        "Move to Image Group": "移动到图片分组",
        "Clear Custom Image Group": "清除自定义图片分组",
        "Group Name:": "分组名称：",
        "Image group already exists.": "图片分组已存在。",
        "Moved {0} image(s) to {1}.": "已将 {0} 张图片移动到“{1}”。",
        "Mark Manual Split Done": "标记为已完成手动切分",
        "Mark Needs Manual Split": "标记为待手动切分",
        "Clear Split Status": "清除切分状态",
        "Error": "错误",
        "Success": "成功",
        "Open Child Expert Session": "打开子部位专家会话",
        "Child Expert Session": "子部位专家会话",
        "Workbench child-part refinement": "工作台子部位精修",
        "Child-part annotation": "子部位标注",
        "Configure Route Expert": "配置路由专家",
        "Annotation Box": "标注框",
        "Annotation box": "正式标注框",
        "Manual ROI Box": "人工ROI框",
        "Draw or replace the manually confirmed ROI box saved with the current part. It does not run SAM by itself.": "为当前部位保存或替换人工 ROI 框；这个工具只保存框，不会自动调用 SAM。",
        "Loose shrink box": "收缩松框",
        "Loose Shrink Box": "收缩松框",
        "Blink Shrink Start Box": "Blink收缩起始框",
        "Draw a loose starting box around a child structure for Blink auto-shrink trajectory training. It is not the final annotation box.": "围绕子部位画一个宽松起始框，用于 Blink 自动收缩轨迹训练；它不是最终标注框。",
        "Annotate child from existing parent box": "用已有父框标注子部位",
        "Run auto-shrink": "执行自动收缩",
        "Train current child expert": "训练当前子部位专家",
        "Parent context": "父级上下文",
        "Child structure": "子部位",
        "Main locator parts": "主定位部位",
        "Blink child parts": "Blink 子部位",
        "Cross-region structures": "跨区域结构",
        "Ungrouped structures": "未分组结构",
        "Structure group": "结构分组",
        "Parent not selected": "未选择父级",
        "parent box exists": "父级框已存在",
        "parent box missing": "父级框未框选",
        "Current structure: {0} ({1}); {2}.": "当前部位：{0}（{1}）；{2}。",
        "Current structure: {0} ({1}); route {2}.": "当前部位：{0}（{1}）；路由 {2}。",
        "Select a structure to see Blink parent-child status.": "选择部位后显示 Blink 父子状态。",
        "Current route: {0}": "当前路由：{0}",
        "Not available": "不可用",
        "Parent box: {0}": "父级框：{0}",
        "available ({0})": "已存在（{0}）",
        "missing": "缺失",
        "Route expert: {0}": "路由专家：{0}",
        "Parent context:": "父级上下文：",
        "Choose parent context": "选择父级上下文",
        "Parent context unavailable": "父级上下文不可用",
        "Manual parent context set: {0} -> {1}.": "已手动设置父级上下文：{0} -> {1}。",
        "Route not configured": "路由未配置",
        "Lock parent box ratio": "锁定父级框比例",
        "Off by default. Enable when preparing fixed-ratio parent boxes for child-part training; it affects parent SAM box prompts and parent manual ROI boxes.": "默认关闭。准备子部位训练所需的固定比例父级框时再开启；开启后会影响父级 SAM 框选和父级人工 ROI 框。",
        "Open route expert settings for {0}.": "打开 {0} 的路由专家设置。",
        "Select a child structure first.": "请先选择子部位。",
        "Select a child structure for refinement.": "请选择子部位进行精修。",
        "Select a child structure with a parent context first.": "请先选择带父级上下文的子部位。",
        "Choose or remember a parent structure for this child first.": "请先为这个子部位指定或记忆父级结构。",
        "Draw a parent box before child refinement.": "请先绘制父级框，再进行子部位精修。",
        "Configure a route expert before automatic child annotation.": "请先配置路由专家，再自动标注子部位。",
        "Enable the current route before automatic child annotation.": "请先启用当前路由，再自动标注子部位。",
        "Training uses saved shrink trajectories for this parent-child route.": "训练会使用这条父子路由下已保存的收缩轨迹。",
        "Training progress": "训练进度",
        "Training Results": "训练结果",
        "Training Result Browser": "训练结果浏览器",
        "Preview Report": "预览报告",
        "No training reports found.": "未找到训练报告。",
        "Type": "类型",
        "Target": "目标",
        "Backend": "后端",
        "Strategy": "方案",
        "Samples": "样本数",
        "Time": "时间",
        "Report Folder": "报告文件夹",
        "Parent-part": "父部位",
        "Child-part": "子部位",
        "Unknown time": "未知时间",
        "Unknown target": "未知目标",
        "No training running.": "当前没有训练任务。",
        "Parent-part model training": "父部位模型训练",
        "Child-part expert training": "子部位专家训练",
        "Parent-part model training finished.": "父部位模型训练完成。",
        "Child-part expert training finished.": "子部位专家训练完成。",
        "Parent-part model training failed.": "父部位模型训练失败。",
        "Child-part expert training failed.": "子部位专家训练失败。",
        "Stopping parent-part training...": "正在停止父部位模型训练...",
        "Stopping child-part expert training...": "正在停止子部位专家训练...",
        "Child-part expert training is running. Wait for it to finish before training parent models.": "子部位专家训练正在进行，请等待结束后再训练父部位模型。",
        "Parent-part training is running. Wait for it to finish before training a child expert.": "父部位模型训练正在进行，请等待结束后再训练子部位专家。",
        "Configure the current route before continuing.": "请先配置当前路由再继续。",
        "Saved Blink shrink start box for {0}.": "已为 {0} 保存 Blink 收缩起始框。",
        "Blink shrink start boxes are only used for child structures. Select a child structure first.": "Blink 收缩起始框只用于子部位。请先选择一个子部位。",
        "Saved manual ROI box for {0}.": "已为 {0} 保存人工 ROI 框。",
        "Running child auto-annotation for {0} via {1}.": "正在通过 {1} 自动标注子部位 {0}。",
        "No usable route expert result was returned for this child structure.": "当前子部位没有返回可用的路由专家结果。",
        "The route expert did not return a valid child box.": "路由专家没有返回有效的子部位框。",
        "Could not read the current image.": "无法读取当前图片。",
        "Generated child draft polygon for {0}.": "已为 {0} 生成子部位草稿多边形。",
        "Route expert produced a child box for {0}; refine polygon manually.": "路由专家已为 {0} 生成子部位框；请手动精修多边形。",
        "Child auto-annotation failed: {0}": "子部位自动标注失败：{0}",
        "Draw or confirm the child polygon before auto-shrink.": "请先绘制或确认子部位多边形，再执行自动收缩。",
        "Select Blink Shrink Start Box on the canvas toolbar and draw one around the child first.": "请先在画布上方选择 Blink 收缩起始框，并围绕子部位画一个宽松起始框。",
        "Auto-shrink did not generate a trajectory.": "自动收缩没有生成轨迹。",
        "Saved {0} shrink trajectory frames for {1}.": "已为 {1} 保存 {0} 帧收缩轨迹。",
        "Auto-shrink failed: {0}": "自动收缩失败：{0}",
        "Batch auto-shrink": "批量自动收缩",
        "Batch auto-shrink prepared {0} image(s) for {1}. Existing trajectories skipped: {2}; missing polygon: {3}; missing shrink box: {4}; missing parent box: {5}.\n\nRun auto-shrink for all prepared images?": "已为 {1} 准备 {0} 张可批量自动收缩的图片。已跳过已有轨迹：{2}；缺少多边形：{3}；缺少收缩起始框：{4}；缺少父框：{5}。\n\n是否对这些图片执行自动收缩？",
        "No prepared images for batch auto-shrink. Existing trajectories: {0}; missing polygon: {1}; missing shrink box: {2}; missing parent box: {3}.": "没有可批量自动收缩的图片。已有轨迹：{0}；缺少多边形：{1}；缺少收缩起始框：{2}；缺少父框：{3}。",
        "Batch auto-shrink finished for {0}/{1} image(s) of {2}. Failed: {3}.": "{2} 的批量自动收缩完成：{0}/{1} 张成功。失败：{3}。",
        "Blink Shrink Training Datasets": "Blink收缩训练数据集",
        "Shows saved auto-shrink trajectories used to train child-part experts. Each row is grouped by parent -> child route.": "展示已保存的自动收缩轨迹，这些数据用于训练子部位专家。每行按父部位 -> 子部位路由分组。",
        "No Blink shrink trajectory datasets have been generated yet.": "尚未生成 Blink 收缩轨迹数据集。",
        "Route": "路由",
        "Images": "图片数",
        "Frames": "帧数",
        "Sources": "来源",
        "View Details": "查看详情",
        "Delete Dataset": "删除数据集",
        "Blink Shrink Dataset Details": "Blink收缩数据集详情",
        "Delete Blink Shrink Dataset": "删除 Blink 收缩数据集",
        "Delete Blink shrink dataset for {0}?\n\nThis removes {1} image trajectory record(s) from the current project. It does not delete labels or images.": "删除 {0} 的 Blink 收缩数据集吗？\n\n这会从当前项目中移除 {1} 条图片轨迹记录，不会删除标注或图片。",
        "Deleted {0} Blink shrink trajectory record(s) for {1}.": "已删除 {1} 的 {0} 条 Blink 收缩轨迹记录。",
        "Blink expert training is already running.": "Blink 专家训练已经在运行。",
        "Started Blink expert training for {0} -> {1}.": "已开始训练 Blink 专家：{0} -> {1}。",
        "Training Report & Validation": "训练报告与验证",
        "Summary": "摘要",
        "No Metrics Generated": "未生成指标图",
        "Training Metrics": "训练指标",
        "Show Validation Set %:": "显示验证集比例：",
        "Load Samples": "加载样本",
        "All validation": "全部验证",
        "Macro locator": "宏定位器",
        "No Validation Summary": "无验证摘要",
        "--- Initial Summary (Top 6) ---": "--- 初始摘要（前 6 张）---",
        "--- Detailed Inspection ---": "--- 详细检查 ---",
        "Validation Inspection": "验证检查",
        "Open Report Folder": "打开报告文件夹",
        "No validation details found at {0}": "未在 {0} 找到验证详情",
        "No images found.": "未找到图片。",
        "{0}% ({1} images)": "{0}%（{1} 张图片）",
        "Cascade Routes": "级联路由",
        "Appoint Expert": "指定专家",
        "Delete Route": "删除路由",
        "Delete Expert File": "删除专家文件",
        "Delete the selected project route only.": "只删除当前选中的项目路由。",
        "Delete the selected expert model file from disk.": "从磁盘删除当前选中的专家模型文件。",
        "Select an available expert file to delete the model file from disk.": "请选择一个真实存在的专家文件，才能从磁盘删除模型文件。",
        "Enable Route": "启用路由",
        "Disable Route": "停用路由",
        "Awaiting expert": "待指定专家",
        "Expert file missing": "专家文件缺失",
        "Delete route {0} -> {1}?": "删除路由 {0} -> {1}？",
        "No trained experts were found under weights/experts.": "未在 weights/experts 下找到已训练专家。",
        "Refresh": "刷新",
        "Info": "提示",
        "Select export directory...": "选择导出目录...",
        "Multimodal (Crops + JSONL)": "多模态（裁剪图 + JSONL）",
        "COCO (Standard)": "COCO（标准）",
        "YOLO (Segmentation)": "YOLO（分割）",
        "Enter Child Expert Session": "进入子部位专家会话",
        "Image: {0}": "图片：{0}",
        "Target Part:": "目标部位：",
        "Entry ROI:": "进入 ROI：",
        "Manual Box": "手工框",
        "Auto Box": "自动框",
        "Model Prediction Box": "模型预测框",
        "VLM Draft Box": "VLM 草稿框",
        "Target Part is the child part you want to refine. Entry ROI is the parent/context region Blink will zoom into. This project remembers the parent/context ROI you chose for each target part, and later Blink entries reuse that remembered context.": "目标部位是你要精修的子部位；进入 ROI 是 Blink 将放大的父级/上下文区域。这个项目会记住你为每个目标部位选择过的父级/上下文 ROI，之后再次进入 Blink 时会复用这份项目内记忆。",
        "Brightness:": "亮度：",
        "Contrast:": "对比度：",
        "Locator:": "定位器：",
        "Segmenter:": "分割器：",
        "Del": "删除",
        "Note": "备注",
        "Delete": "删除",
        "No Locators Found": "未找到定位器",
        "Base SAM (Original)": "基础 SAM（原始）",
        "Edit Locator Note": "编辑定位器备注",
        "Edit Segmenter Note": "编辑分割器备注",
        "Model display note:": "模型显示备注：",
        "Edit the selected locator model display note.": "编辑当前选中定位器模型的显示备注。",
        "Edit the selected segmenter model display note.": "编辑当前选中分割器模型的显示备注。",
        "Updated model note for {0}: {1}": "已更新模型备注 {0}：{1}",
        "Cleared model note for {0}.": "已清空模型备注 {0}。",
        "Delete the selected locator model file from disk.": "从磁盘删除当前选中的定位器模型文件。",
        "Delete the selected segmenter model file from disk.": "从磁盘删除当前选中的分割器模型文件。",
        "Delete Model": "删除模型",
        "Delete locator model {0}?": "删除定位器模型 {0}？",
        "Locator reset to base (untrained).": "定位器已重置为基础（未训练）状态。",
        "Segmenter switched to: Base SAM (Original)": "分割器已切换为：基础 SAM（原始）",
        "Segmenter switched to: Fine-tuned {0}": "分割器已切换为：微调版 {0}",
        "Delete segmenter LoRA {0}?": "删除分割器 LoRA {0}？",
        "New Project Directory": "新建项目目录",
        "Project Name:": "项目名称：",
        "Structure Name:": "结构标签名称：",
        "New Structure Name:": "新的结构标签名称：",
        "Exists.": "已存在。",
        "Rename '{0}' to '{1}'? Existing labels, VLM drafts, parent-child routes, and training context for this structure will be moved to the new name.": "将“{0}”重命名为“{1}”？这个结构已有的标注、VLM 草稿、父子路由和训练上下文都会迁移到新名称。",
        "Could not rename structure. The new name may already exist or contain unsafe characters.": "无法重命名结构标签。新名称可能已存在，或包含不安全字符。",
        "Delete '{0}'?": "删除“{0}”？",
        "Clear AI": "清除 AI",
        "Are you sure?": "确定吗？",
        "Clear all AI labels from the current project?": "清除当前项目中的全部 AI 标签？",
        "Clear AI Label Scope": "清除 AI 标签范围",
        "Scope:": "范围：",
        "All project images": "全部项目图片",
        "Images in group: {0}": "图片分组：{0}",
        "This will remove {0} AI label(s) from {1} image(s). Manual and confirmed labels are kept.": "将从 {1} 张图片中清除 {0} 个 AI 标签。人工标签和已确认标签会保留。",
        "No AI labels found in the selected scope.": "所选范围内没有 AI 标签。",
        "Clear selected AI labels?": "清除所选范围内的 AI 标签吗？",
        "Removed {0} AI labels from {1}.": "已从 {1} 清除 {0} 个 AI 标签。",
        "Select Images": "选择图片",
        "Remove": "移除",
        "Remove {0} images?": "移除 {0} 张图片？",
        "Child Expert Session Entry": "子部位专家会话入口",
        "Please select an image first.": "请先选择一张图片。",
        "Please select a target part first.": "请先选择目标部位。",
        "No entry ROI is available yet. Draw a manual box or generate an auto box in the workbench first.": "当前还没有可用的进入 ROI，请先在工作台中绘制手工框或生成自动框。",
        "Failed to build a child expert session from the selected options.": "无法根据当前选择建立子部位专家会话。",
        "Opened child expert session for {0} via {1} ({2}).": "已通过 {1}（{2}）为 {0} 打开子部位专家会话。",
        "mm:": "毫米：",
        "No Scale.": "未设置比例尺。",
        "Area: {0:.4f} mm2\nPeri: {1:.4f} mm": "面积：{0:.4f} mm²\n周长：{1:.4f} mm",
        "No Polygon.": "无多边形。",
        "Annotate first!": "请先完成标注！",
        "Training Split Error": "训练划分错误",
        "Training aborted: {0}": "训练已中止：{0}",
        "Settings updated.": "设置已更新。",
        "Language: {0}": "语言：{0}",
        "Running inference on: {0}...": "正在对 {0} 进行推理...",
        "Inference complete. Detected {0} parts, saved {1} new labels.": "推理完成。检测到 {0} 个部位，保存了 {1} 个新标签。",
        "Batch": "批量",
        "Annotate {0} images?": "对 {0} 张图片进行标注？",
        "Starting Batch Inference with Taxonomy ({0}): {1}": "开始批量推理，分类体系（{0}）：{1}",
        "Batch saved {0}/{1} for {2}": "已为 {2} 保存 {0}/{1}",
        "Exported {0} samples.": "已导出 {0} 个样本。",
        "Global labels updated from Child Expert Session.": "全局标签已从子部位专家会话同步更新。",
        "Restored session: {0}": "已恢复会话：{0}",
        "System Initialized.": "系统已初始化。",
        "Syncing Engine Taxonomy ({0} -> {1})...": "正在同步引擎分类体系（{0} -> {1}）...",
        "Taxonomy changed. Please retrain or select a matching model.": "分类体系已变化，请重新训练或选择匹配的模型。",
        "Training with Taxonomy ({0}): {1}": "使用分类体系进行训练（{0}）：{1}",
        "Training with Locator Scope ({0}): {1}": "使用定位器范围进行训练（{0}）：{1}",
        "Starting Batch Inference with Locator Scope ({0}): {1}": "开始批量推理，定位器范围（{0}）：{1}",
        "Syncing Locator Scope ({0} -> {1})...": "正在同步定位器范围（{0} -> {1}）...",
        "Locator scope changed. Please retrain or select a matching model.": "定位器范围已变化，请重新训练或选择匹配的模型。",
        "Starting batch inference on {0} images...": "开始对 {0} 张图片进行批量推理...",
        "Processed {0}": "已处理 {0}",
        "Training SAM... (BS=1)": "正在训练 SAM...（批次=1）",
        "Generating Report...": "正在生成报告...",
        "Loc Ep {0}: Train {1:.4f} | Val {2:.4f} | Err {3:.1f}px": "定位器轮次 {0}：训练 {1:.4f} | 验证 {2:.4f} | 误差 {3:.1f}px",
        "SAM Ep {0}: Train {1:.4f} | Val {2:.4f} | IoU {3:.2%}": "SAM 轮次 {0}：训练 {1:.4f} | 验证 {2:.4f} | IoU {3:.2%}",
        "Training Finished! All validation results saved to {0}/val_details": "训练完成！所有验证结果已保存到 {0}/val_details",
        "Locator training size set to {0}": "定位器训练尺寸设为 {0}",
        "Locator stage skipped: no eligible locator samples.": "定位器阶段已跳过：没有可用的定位器样本。",
        "SAM stage skipped: no eligible SAM/parts samples.": "SAM 阶段已跳过：没有可用的 SAM/部位样本。",
        "SAM stage skipped: locator-only training is enabled.": "SAM 阶段已跳过：已启用仅训练定位器。",
        "Training cancelled.": "训练已取消。",
        "Training already running...": "训练已在进行中...",
        "Stop Training": "停止训练",
        "Stopping training after the current epoch/batch...": "将在当前轮次/批次结束后停止训练...",
        "Train Locator only (skip SAM)": "仅训练定位器（跳过 SAM）",
        "Skip SAM/parts training for this run. Useful when the base SAM result is already good enough.": "本次训练跳过 SAM/部位分割训练。适合基础 SAM 效果已经足够好的情况。",
        "Training Preflight": "训练预检",
        "Training Readiness Warning": "训练准备警告",
        "Training Confirmation Required": "需要训练确认",
        "Training Retry": "训练重试",
        "Train anyway": "仍然训练",
        "Retry with lower resolution": "用更低分辨率重试",
        "Legacy Locator Confirmation": "旧版定位器确认",
        "The selected locator checkpoint does not store its training resolution. It will be treated as a legacy 512px locator only if you confirm.": "当前选中的定位器检查点没有保存训练分辨率。只有在你确认后，程序才会把它当作旧版 512px 定位器使用。",
        "Training will use only saved annotations and image files. View/manifest gating is no longer used in the main Train Models path.": "主训练路径现在只依据已保存标注和图像文件，不再依赖视图/manifest 门控。",
        "Mixed native image resolutions detected among locator-eligible images. Training will unify them to the smallest native resolution tier among eligible images: {0}. Continue?": "检测到可用于 locator 训练的图片存在混合原生分辨率。训练会统一到这些合格图片中最小的原生分辨率层级：{0}。是否继续？",
        "Locator stage ran out of memory at {0}. You can retry with a lower locator size: {1}": "定位器阶段在 {0} 时发生显存不足。你可以改用更低的定位器尺寸重试：{1}",
        "No lower locator resolutions are available for retry.": "已经没有更低的 locator 分辨率可供重试。",
        "Training preflight summary:\n{0}": "训练预检摘要：\n{0}",
        "Proceed with training?": "是否继续训练？",
        "Locator switched to: {0}": "定位器已切换为：{0}"
    }
}

def tr(text, lang="en"):
    if lang == "zh":
        return TRANSLATIONS["zh"].get(text, text)
    return text


SECTION_TRANSLATIONS = {
    "zh": {
        "Overview": "概览",
        "Coverage": "覆盖情况",
        "Warnings": "警告",
        "Ready": "就绪",
        "Skipped": "跳过",
        "Locator stage: {0} | SAM stage: {1}": "Locator 阶段：{0} | SAM 阶段：{1}",
        "Locator size: {0}": "Locator 尺寸：{0}",
        "Mixed-resolution decision: locator training will use {0}.": "混合分辨率处理：Locator 训练将统一使用 {0}。",
        "total images: {0}": "总图片数：{0}",
        "train images: {0}": "训练集图片数：{0}",
        "val images: {0}": "验证集图片数：{0}",
        "total coverage: {0}": "总覆盖：{0}",
        "train coverage: {0}": "训练覆盖：{0}",
        "val coverage: {0}": "验证覆盖：{0}",
        "Locator eligible images: {0}": "可用于 Locator 训练的图片：{0}",
        "SAM/parts eligible images: {0}": "可用于 SAM/部位训练的图片：{0}",
        "Training scope: {0}": "训练范围：{0}",
        "All Images": "全部图片",
        "Selected locator size: {0}": "选定的 Locator 尺寸：{0}",
        "Eligible locator native sizes: {0}": "符合条件的 Locator 原始尺寸：{0}",
        "Mixed native resolutions: {0}": "存在混合原生分辨率：{0}",
        "Locator coverage": "Locator 标注覆盖情况",
        "SAM / parts coverage": "SAM / 部位标注覆盖情况",
        "Missing images": "缺失图片",
        "Unreadable images": "无法读取的图片",
        "Zero-annotation images": "零标注图片",
        "Invalid-annotation images": "无效标注图片",
        "Warnings:": "警告：",
        "No warnings. The current saved annotations satisfy the training gate.": "当前没有警告，现有已保存标注已满足训练条件。",
        "ID": "编号",
        "Image": "图片",
        "Source": "来源",
        "Valid Parts": "有效部位",
        "Max Error(px)": "最大误差（px）",
        "Validation count: {0}": "验证样本数：{0}",
        "Preview count: {0}": "预览样本数：{0}",
        "Provenance counts:": "来源统计：",
        "Metrics plot: {0}": "指标图：{0}",
        "Validation index: {0}": "验证索引：{0}",
        "No structured report summary found.": "未找到结构化报告摘要。",
        "Validation samples:": "验证样本：",
        "Project Routes": "项目路由",
        "Project Route Management": "项目路由管理",
        "Manage parent-child expert routes in the current 2D workflow here. Deleting a route removes only this project record; training or appointing an expert later can register a candidate again.": "可在当前 2D 工作流里管理父部位到子部位专家的路线。删除路线只会移除当前项目中的这条记录；之后训练或指定专家时仍可重新登记候选专家。",
        "Project routes below control which parent -> child expert links are available.": "下方项目中的 route 决定哪些 parent -> child expert 链路可以实际使用。",
        "Delete Route": "删除路由",
        "Edit Expert Note": "编辑专家备注",
        "Expert display note:": "专家显示备注：",
        "Select an expert row to edit its display note.": "请选择一个专家模型行来编辑显示备注。",
        "Updated expert note for {0}: {1}": "已更新专家备注 {0}：{1}",
        "Cleared expert note for {0}.": "已清空专家备注 {0}。",
        "Delete Expert File": "删除专家文件",
        "Delete the selected project route only.": "只删除当前选中的项目路由。",
        "Delete the selected expert model file from disk.": "从磁盘删除当前选中的专家模型文件。",
        "Select an available expert file to delete the model file from disk.": "请选择一个真实存在的专家文件，才能从磁盘删除模型文件。",
        "Parent": "父部位",
        "Child": "子部位",
        "Cross-region structures": "跨区域结构",
        "Ungrouped structures": "未分组结构",
        "Main locator parts": "主定位部位",
        "Blink child parts": "Blink 子部位",
        "Structure group": "结构分组",
        "Enabled": "已启用",
        "Disabled": "已停用",
        "Expert": "专家",
        "Status": "状态",
        "Profile Fit": "方案匹配",
        "Yes": "是",
        "No": "否",
        "Not appointed": "未指定",
        "Expert not appointed yet": "尚未指定专家",
        "No appointed expert": "未指定专家",
        "Matches active profile": "匹配当前方案",
        "Route-specific backend": "路由单独后端",
        "Active profile default: {0}\nRoute expert backend: {1}": "当前方案默认：{0}\n路由专家后端：{1}",
        "Project": "项目",
        "Blink candidate": "Blink 候选",
        "Blink training": "Blink 训练",
        "Legacy global manifest": "Legacy 全局清单",
        "Appointed": "已指定",
        "Available": "可指定",
        "History": "历史候选",
        "Missing file history": "缺文件历史",
        "Discoverable": "可发现",
        "Select the expert to appoint for {0} -> {1}": "为 {0} -> {1} 选择要指定的专家",
        "This route has no appointed expert yet. Appoint an expert first, then enable the route.": "这条路由还没有指定专家。请先指定专家，再启用该路由。",
        "The appointed expert file for this route is missing. Reappoint an available expert before enabling the route.": "这条路由指定的专家文件缺失。请先重新指定一个可用专家，再启用该路由。",
        "Route {0} -> {1} now uses expert {2}.": "路由 {0} -> {1} 现已指定专家 {2}。",
        "Route {0} -> {1} enabled.": "路由 {0} -> {1} 已启用。",
        "Route {0} -> {1} disabled.": "路由 {0} -> {1} 已停用。",
        "Delete expert file {0}?\n\nThis removes the model file from disk and clears current-project expert references to it. Parent -> child route records are kept, but they will return to an unappointed state if this was the appointed expert.": "删除专家文件 {0}？\n\n这会从磁盘删除模型文件，并清理当前项目中指向它的专家引用。父 -> 子路由记录会保留；如果它原本是指定专家，该路由会回到未指定专家状态。",
        "Deleted expert file {0}. Cleared {1} current-project route reference(s).": "已删除专家文件 {0}，并清理当前项目中的 {1} 条路由引用。",
        "Failed to delete expert file: {0}": "删除专家文件失败：{0}",
        "Delete project route {0} -> {1}?\n\nThis removes the current project route record only. If you reopen Blink later with the same parent/child context, Blink can register this route again as a candidate.": "删除项目路由 {0} -> {1}？\n\n这只会移除当前项目里的这条路由记录。如果你之后在相同父/子部位上下文下再次打开 Blink，Blink 仍可把这条路由重新登记为候选。",
        "Deleted route {0} -> {1}.": "已删除路由 {0} -> {1}。",
        "Remove missing expert history {0} from route {1} -> {2}?\n\nThis only cleans the current project route history. It does not delete any model file.": "从路由 {1} -> {2} 中移除缺文件专家历史 {0}？\n\n这只会清理当前项目里的路由历史，不会删除任何模型文件。",
        "Removed missing expert history {0} from route {1} -> {2}.": "已从路由 {1} -> {2} 移除缺文件专家历史 {0}。",
        "Current Image": "当前图片",
        "Route usage for {0}": "路由使用情况：{0}",
        "Route usage for batch image {0}": "批量图片的路由使用情况：{0}",
        "source={0}; attempted={1}; applied={2}": "来源={0}；尝试={1}；应用={2}",
        "Model audit: profile={0}; parent_backend={1}; route_backends={2}": "模型审计：方案={0}；父部位后端={1}；路由后端={2}",
        "Route blocks: {0}": "路由阻断：{0}",
        "Unknown": "未知",
    }
}


def ui_text(text, lang="en"):
    if lang == "zh":
        return SECTION_TRANSLATIONS["zh"].get(text, text)
    return text


def _yes_no_text(value, lang="en"):
    return ui_text("Yes", lang) if value else ui_text("No", lang)


def _translate_validation_provenance(value, lang="en"):
    mapping = {
        "macro_locator": tr("Macro locator", lang),
        "all": tr("All validation", lang),
    }
    return mapping.get(str(value or ""), str(value or ""))


def _translate_route_registration_source(value, lang="en"):
    mapping = {
        "project": ui_text("Project", lang),
        "blink_candidate": ui_text("Blink candidate", lang),
        "blink_training": ui_text("Blink training", lang),
        "workbench_blink_refine": tr("Workbench child-part refinement", lang),
        "legacy_global_manifest": ui_text("Legacy global manifest", lang),
    }
    text = str(value or "project")
    return mapping.get(text, text)


def _route_backend_label(value, lang="en"):
    backend = str(value or ROUTE_BACKEND_VIT_B_BLINK).strip() or ROUTE_BACKEND_VIT_B_BLINK
    mapping = {
        ROUTE_BACKEND_VIT_B_BLINK: tr("ViT-B Blink Expert", lang),
        ROUTE_BACKEND_HEATMAP_BLINK: tr("Heatmap Blink Expert", lang),
        ROUTE_BACKEND_EXTERNAL_BLINK: tr("Custom Child Extension", lang),
    }
    return mapping.get(backend, backend)


def _parent_backend_label(value, lang="en"):
    backend = str(value or PARENT_BACKEND_BUILTIN).strip() or PARENT_BACKEND_BUILTIN
    mapping = {
        PARENT_BACKEND_BUILTIN: tr("Built-in Locator + SAM", lang),
        PARENT_BACKEND_EXTERNAL: tr("Custom Parent Extension", lang),
        EXTERNAL_BACKEND_ID: tr("Custom Parent Extension", lang),
    }
    return mapping.get(backend, backend)


def _child_backend_label(value, lang="en"):
    backend = str(value or CHILD_BACKEND_VIT_B).strip() or CHILD_BACKEND_VIT_B
    mapping = {
        CHILD_BACKEND_VIT_B: tr("ViT-B Blink Expert", lang),
        CHILD_BACKEND_HEATMAP: tr("Heatmap Blink Expert", lang),
        CHILD_BACKEND_EXTERNAL: tr("Custom Child Extension", lang),
    }
    return mapping.get(backend, backend)


def _route_backend_from_child_backend(value):
    backend = str(value or CHILD_BACKEND_VIT_B).strip() or CHILD_BACKEND_VIT_B
    mapping = {
        CHILD_BACKEND_VIT_B: ROUTE_BACKEND_VIT_B_BLINK,
        CHILD_BACKEND_HEATMAP: ROUTE_BACKEND_HEATMAP_BLINK,
        CHILD_BACKEND_EXTERNAL: ROUTE_BACKEND_EXTERNAL_BLINK,
    }
    return mapping.get(backend, ROUTE_BACKEND_VIT_B_BLINK)


def _active_profile_from_manager(project_manager):
    get_profile = getattr(project_manager, "get_active_model_profile", None)
    if callable(get_profile):
        try:
            profile = get_profile()
            if isinstance(profile, dict) and profile:
                return profile
        except Exception:
            pass
    return {
        "profile_id": DEFAULT_MODEL_PROFILE_ID,
        "display_name": "Built-in heatmap parent + default Blink",
        "parent_backend": {"backend_type": PARENT_BACKEND_BUILTIN},
        "child_backend_defaults": {"backend_type": CHILD_BACKEND_VIT_B},
    }


def _runtime_parent_backend(project_manager, fallback=BUILTIN_BACKEND_ID):
    profile = _active_profile_from_manager(project_manager)
    parent_backend = profile.get("parent_backend", {}) if isinstance(profile.get("parent_backend"), dict) else {}
    backend_type = str(parent_backend.get("backend_type") or "").strip()
    if backend_type == PARENT_BACKEND_EXTERNAL:
        return EXTERNAL_BACKEND_ID
    if backend_type == PARENT_BACKEND_BUILTIN:
        return BUILTIN_BACKEND_ID
    return fallback or BUILTIN_BACKEND_ID


def _runtime_child_backend_defaults(project_manager):
    profile = _active_profile_from_manager(project_manager)
    child_defaults = profile.get("child_backend_defaults", {}) if isinstance(profile.get("child_backend_defaults"), dict) else {}
    return dict(child_defaults)


def _route_backend_from_entry(route_entry):
    if not isinstance(route_entry, dict):
        return ROUTE_BACKEND_VIT_B_BLINK
    appointed = route_entry.get("appointed_expert")
    if isinstance(appointed, dict) and appointed.get("expert_backend"):
        return appointed.get("expert_backend")
    return route_entry.get("expert_backend") or ROUTE_BACKEND_VIT_B_BLINK


def _route_manifest_from_entry(route_entry):
    if not isinstance(route_entry, dict):
        return ""
    appointed = route_entry.get("appointed_expert")
    if isinstance(appointed, dict) and appointed.get("expert_manifest"):
        return str(appointed.get("expert_manifest") or "")
    return str(route_entry.get("expert_manifest") or "")


def _compact_path_text(value, limit=52):
    text = str(value or "").strip().replace("\\", "/")
    if len(text) <= limit:
        return text
    return "..." + text[-max(1, limit - 3):]


def _translate_training_warning_text(text, lang="en"):
    warning_text = str(text or "")
    if lang != "zh":
        return warning_text

    patterns = [
        (
            r"^Excluded (\d+) image\(s\) missing on disk from training\.$",
            "训练中排除了 {0} 张磁盘缺失图片。",
        ),
        (
            r"^Excluded (\d+) unreadable image\(s\) from training\.$",
            "训练中排除了 {0} 张无法读取的图片。",
        ),
        (
            r"^Excluded (\d+) image\(s\) whose saved annotations were invalid\.$",
            "训练中排除了 {0} 张已保存标注无效的图片。",
        ),
        (
            r"^Excluded (\d+) image\(s\) with only unreviewed Auto-Annotated drafts from training\.$",
            "训练中排除了 {0} 张只有未复核 Auto-Annotated 草稿的图片。",
        ),
        (
            r"^Excluded (\d+) zero-annotation image\(s\) from training\.$",
            "训练中排除了 {0} 张零标注图片。",
        ),
        (
            r"^No locator-eligible images were found\. The locator stage will be skipped\.$",
            "没有找到可用于 Locator 训练的图片，Locator 阶段将被跳过。",
        ),
        (
            r"^Only 1 locator-eligible image was found; training and validation will reuse the same image\.$",
            "只找到 1 张可用于 Locator 训练的图片，训练与验证将复用同一张图片。",
        ),
        (
            r"^No SAM/parts-eligible images were found\. The SAM stage will be skipped\.$",
            "没有找到可用于 SAM/部位训练的图片，SAM 阶段将被跳过。",
        ),
        (
            r"^Only 1 SAM/parts-eligible image was found; training and validation will reuse the same image\.$",
            "只找到 1 张可用于 SAM/部位训练的图片，训练与验证将复用同一张图片。",
        ),
        (
            r"^Locator coverage is 0 for '(.+)', so that locator part will not be trained\.$",
            "'{0}' 的 Locator 标注覆盖为 0，因此该部位不会进入 Locator 训练。",
        ),
        (
            r"^SAM/parts coverage is 0 for '(.+)', so that part will not enter SAM training\.$",
            "'{0}' 的 SAM/部位标注覆盖为 0，因此该部位不会进入 SAM 训练。",
        ),
    ]

    for pattern, template in patterns:
        match = re.match(pattern, warning_text)
        if match:
            return template.format(*match.groups())
    return warning_text


WORKBENCH_WINDOW_TITLE = "TaxaMask Workbench"
DEFAULT_PROJECT_NAME = "TaxaMask_Project"
DEFAULT_OUTPUTS_DIR_NAME = "TaxaMask_outputs"
DEFAULT_2D_STL_PROJECTS_DIR_NAME = "2d_stl_projects"
DEFAULT_STARTUP_PROJECT_DIR_NAME = "_startup"
BACKGROUND_IMAGE_IMPORT_THRESHOLD = 20
LARGE_PROJECT_OPEN_LIGHTWEIGHT_THRESHOLD = 500
BRAND_ASSETS_DIR = os.path.join(PACKAGE_DIR, "assets", "brand")
APP_ICON_PATH = os.path.join(BRAND_ASSETS_DIR, "taxamask_app_icon_white.ico")
APP_ICON_FALLBACK_PATH = os.path.join(BRAND_ASSETS_DIR, "taxamask_app_icon_white.png")


class NoWheelComboBox(QComboBox):
    """Combo box that ignores mouse-wheel changes to avoid accidental selection changes."""

    def wheelEvent(self, event):
        event.ignore()


class NoWheelSpinBox(QSpinBox):
    """Spin box that lets scroll areas handle the wheel instead of changing values."""

    def wheelEvent(self, event):
        event.ignore()


class NoWheelSlider(QSlider):
    """Slider that ignores wheel changes to prevent accidental parameter edits."""

    def wheelEvent(self, event):
        event.ignore()


class ImageGroupListWidget(QListWidget):
    """Image list with project-internal drag/drop grouping."""

    imagesDroppedToGroup = Signal(list, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)

    def startDrag(self, _supported_actions):
        paths = [
            item.data(Qt.UserRole)
            for item in self.selectedItems()
            if item and item.data(Qt.UserRole)
        ]
        if not paths:
            return
        mime = QMimeData()
        mime.setData("application/x-taxamask-image-paths", json.dumps(paths).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.MoveAction)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-taxamask-image-paths"):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-taxamask-image-paths"):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event):
        if not event.mimeData().hasFormat("application/x-taxamask-image-paths"):
            super().dropEvent(event)
            return
        target_item = self.itemAt(event.position().toPoint())
        if target_item is None:
            return
        group_key = target_item.data(Qt.UserRole + 1) or target_item.data(Qt.UserRole + 2)
        if not group_key:
            return
        try:
            paths = json.loads(bytes(event.mimeData().data("application/x-taxamask-image-paths")).decode("utf-8"))
        except Exception:
            paths = []
        paths = [str(path) for path in paths if str(path or "").strip()]
        if not paths:
            return
        self.imagesDroppedToGroup.emit(paths, str(group_key))
        event.acceptProposedAction()


def _agent_yes_no(value):
    return "yes" if value else "no"


def _agent_command_has_contract(command_text):
    command = str(command_text or "")
    return "{contract}" in command or "{contract_json}" in command


def _agent_error_summary(errors, limit=4):
    items = [str(error).strip() for error in (errors or []) if str(error).strip()]
    if not items:
        return "none"
    shown = items[:limit]
    if len(items) > limit:
        shown.append(f"+{len(items) - limit} more")
    return " | ".join(shown)


def _format_backend_contract_error(template, command_name):
    return str(template or "").replace("{0}", str(command_name))


def _blink_preferred_roi_parts(target_part, remembered_parent_part=None):
    target = str(target_part or "").strip()
    remembered_parent = str(remembered_parent_part or "").strip()
    preferred_parts = []
    if remembered_parent and remembered_parent != target:
        preferred_parts.append(remembered_parent)
    return preferred_parts


def _clean_box(box):
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        return None
    try:
        clean = [float(value) for value in box]
    except Exception:
        return None
    if clean[2] <= clean[0] or clean[3] <= clean[1]:
        return None
    return clean

class TrainingThread(QThread):
    log_signal = Signal(str)
    progress_signal = Signal(int)
    report_signal = Signal(dict)
    success_signal = Signal()
    error_signal = Signal(dict)
    finished_signal = Signal()
    
    def __init__(
        self,
        engine,
        preflight,
        taxonomy,
        locator_scope,
        epochs=5,
        batch_size=4,
        lang="en",
        train_segmenter=True,
        training_context=None,
    ):
        super().__init__()
        self.engine = engine
        self.preflight = dict(preflight or {})
        self.taxonomy = taxonomy
        self.locator_scope = locator_scope
        self.epochs = epochs
        self.batch_size = batch_size
        self.lang = lang
        self.train_segmenter = bool(train_segmenter)
        self.training_context = dict(training_context or {})
        self.locator_train_data = list(self.preflight.get("locator_train_data", []))
        self.locator_val_data = list(self.preflight.get("locator_val_data", []))
        self.parts_train_data = list(self.preflight.get("parts_train_data", []))
        self.parts_val_data = list(self.preflight.get("parts_val_data", []))
        self.locator_resolution = tuple(self.preflight.get("selected_locator_size") or (512, 512))
        self.has_locator_stage = bool(self.locator_train_data and self.locator_val_data)
        self.has_parts_stage = bool(self.train_segmenter and self.parts_train_data and self.parts_val_data)
        self.saved_weights_timestamp = None
         
    def run(self):
        try:
            self.log_signal.emit("Starting training on active compute device...")

            self.engine.locator_resolution = tuple(self.locator_resolution)
            self.log_signal.emit(
                tr("Locator training size set to {0}", self.lang).format(format_size_pair(self.engine.locator_resolution))
            )

            self.engine.history["locator_train"] = []
            self.engine.history["locator_val"] = []
            self.engine.history["pixel_error"] = []
            self.engine.history["parts_train"] = []
            self.engine.history["parts_val"] = []
            self.engine.history["iou"] = []

            dl_loc_val = None

            if self.has_locator_stage:
                locator = self.engine.ensure_locator_loaded()
                opt_loc = self.engine.opt_loc
                ds_loc_train = TwoStageDataset(
                    self.locator_train_data,
                    self.locator_scope,
                    mode='locator',
                    input_size=tuple(self.engine.locator_resolution),
                )
                ds_loc_val = TwoStageDataset(
                    self.locator_val_data,
                    self.locator_scope,
                    mode='locator',
                    input_size=tuple(self.engine.locator_resolution),
                )
                dl_loc_train = DataLoader(ds_loc_train, batch_size=max(1, self.batch_size*2), shuffle=True)
                dl_loc_val = DataLoader(ds_loc_val, batch_size=max(1, self.batch_size*2), shuffle=False)

                self.log_signal.emit("Training Locator...")
                try:
                    for epoch in range(self.epochs): 
                        if self.isInterruptionRequested():
                            self.log_signal.emit(tr("Training cancelled.", self.lang))
                            return
                        loss_t = self.engine.train_epoch(
                            dl_loc_train,
                            locator,
                            opt_loc,
                            None,
                            stop_callback=self.isInterruptionRequested,
                        )
                        if loss_t is None:
                            self.log_signal.emit(tr("Training cancelled.", self.lang))
                            return
                        if self.isInterruptionRequested():
                            self.log_signal.emit(tr("Training cancelled.", self.lang))
                            return
                        metrics_v = self.engine.validate_epoch(
                            dl_loc_val,
                            locator,
                            stop_callback=self.isInterruptionRequested,
                        )
                        if metrics_v is None:
                            self.log_signal.emit(tr("Training cancelled.", self.lang))
                            return
                        self.engine.history["locator_train"].append(loss_t)
                        self.engine.history["locator_val"].append(metrics_v['loss'])
                        self.engine.history["pixel_error"].append(metrics_v['pixel_error'])
                        self.log_signal.emit(
                            tr("Loc Ep {0}: Train {1:.4f} | Val {2:.4f} | Err {3:.1f}px", self.lang).format(
                                epoch, loss_t, metrics_v['loss'], metrics_v['pixel_error']
                            )
                        )
                        self.progress_signal.emit(int((epoch+1)/(self.epochs*2) * 100))
                except RuntimeError as exc:
                    if "out of memory" in str(exc).lower():
                        if torch.cuda.is_available():
                            torch.cuda.empty_cache()
                        self.error_signal.emit(
                            {
                                "type": "oom",
                                "stage": "locator",
                                "current_resolution": tuple(self.engine.locator_resolution),
                                "lower_options": list(self.preflight.get("lower_locator_size_options", [])),
                                "message": str(exc),
                            }
                        )
                        return
                    raise
            else:
                self.log_signal.emit(tr("Locator stage skipped: no eligible locator samples.", self.lang))
                self.progress_signal.emit(50)

            if self.has_parts_stage:
                ds_parts_train = TwoStageDataset(self.parts_train_data, self.taxonomy, mode='parts')
                ds_parts_val = TwoStageDataset(self.parts_val_data, self.taxonomy, mode='parts')
                dl_parts_train = DataLoader(ds_parts_train, batch_size=1, shuffle=True)
                dl_parts_val = DataLoader(ds_parts_val, batch_size=1, shuffle=False)
                parts_model = self.engine.ensure_parts_model_loaded()
                opt_parts = self.engine.opt_parts

                self.log_signal.emit(tr("Training SAM... (BS=1)", self.lang))
                for epoch in range(self.epochs):
                    if self.isInterruptionRequested():
                        self.log_signal.emit(tr("Training cancelled.", self.lang))
                        return
                    loss_t = self.engine.train_epoch(
                        dl_parts_train,
                        parts_model,
                        opt_parts,
                        self.engine.crit_parts,
                        stop_callback=self.isInterruptionRequested,
                    )
                    if loss_t is None:
                        self.log_signal.emit(tr("Training cancelled.", self.lang))
                        return
                    if self.isInterruptionRequested():
                        self.log_signal.emit(tr("Training cancelled.", self.lang))
                        return
                    metrics_v = self.engine.validate_epoch(
                        dl_parts_val,
                        parts_model,
                        stop_callback=self.isInterruptionRequested,
                    )
                    if metrics_v is None:
                        self.log_signal.emit(tr("Training cancelled.", self.lang))
                        return
                    self.engine.history["parts_train"].append(loss_t)
                    self.engine.history["parts_val"].append(metrics_v['loss'])
                    self.engine.history["iou"].append(metrics_v['iou'])
                    self.log_signal.emit(
                        tr("SAM Ep {0}: Train {1:.4f} | Val {2:.4f} | IoU {3:.2%}", self.lang).format(
                            epoch, loss_t, metrics_v['loss'], metrics_v['iou']
                        )
                    )
                    self.progress_signal.emit(50 + int((epoch+1)/(self.epochs*2) * 100))
            else:
                if self.train_segmenter:
                    self.log_signal.emit(tr("SAM stage skipped: no eligible SAM/parts samples.", self.lang))
                else:
                    self.log_signal.emit(tr("SAM stage skipped: locator-only training is enabled.", self.lang))
                self.progress_signal.emit(100)

            if self.isInterruptionRequested():
                self.log_signal.emit(tr("Training cancelled.", self.lang))
                return
                
            self.saved_weights_timestamp = self.engine.save_weights(save_locator=self.has_locator_stage, save_segmenter=self.has_parts_stage)
            if self.saved_weights_timestamp:
                self.training_context["saved_weights_timestamp"] = self.saved_weights_timestamp
                self.training_context["locator_weights"] = (
                    f"locator_{self.saved_weights_timestamp}.pth" if self.has_locator_stage else ""
                )
                self.training_context["segmenter_weights"] = (
                    f"sam_decoder_lora_{self.saved_weights_timestamp}.pth" if self.has_parts_stage else ""
                )
            self.log_signal.emit(tr("Generating Report...", self.lang))
            
            # Initial report shows only a small summary (e.g., 6 images)
            # Detailed inspection is handled by the UI post-training.
            report = self.engine.generate_report(dl_loc_val, num_samples=6, training_context=self.training_context)
            
            self.report_signal.emit(report)
            self.log_signal.emit(
                tr("Training Finished! All validation results saved to {0}/val_details", self.lang).format(report['dir'])
            )
            self.success_signal.emit()
        except Exception as exc:
            self.error_signal.emit({"type": "error", "message": str(exc)})
        finally:
            self.finished_signal.emit()


class TrainingPreflightDialog(QDialog):
    def __init__(self, preflight, parent=None, lang="en"):
        super().__init__(parent)
        self.lang = lang
        self.preflight = dict(preflight or {})
        self.current_theme = getattr(parent, "current_theme", "dark")
        self._accepted = False
        self._accepted_mixed_resolution = False
        self.setWindowTitle(tr("Training Preflight", self.lang))
        self.resize(920, 760)

        layout = QVBoxLayout(self)

        intro = QLabel(
            tr(
                "Training will use only saved annotations and image files. View/manifest gating is no longer used in the main Train Models path.",
                self.lang,
            )
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.summary_label = QLabel(self._build_overall_summary())
        self.summary_label.setWordWrap(True)
        self.summary_label.setObjectName("mutedLabel")
        layout.addWidget(self.summary_label)

        tabs = QTabWidget()
        tabs.addTab(self._build_overview_tab(), ui_text("Overview", self.lang))
        tabs.addTab(self._build_coverage_tab(), ui_text("Coverage", self.lang))
        tabs.addTab(self._build_warnings_tab(), ui_text("Warnings", self.lang))
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons = buttons
        self.btn_train = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.btn_cancel = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        self.btn_train.setText(tr("Train anyway", self.lang))
        self.btn_cancel.setText(tr("Cancel", self.lang))
        self.set_theme(self.current_theme)
        buttons.accepted.connect(self._accept_training)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def set_theme(self, theme):
        self.current_theme = theme
        apply_theme_dialog_button_box_style(
            getattr(self, "buttons", None),
            ok_role=BUTTON_ROLE_RUN,
            cancel_role=BUTTON_ROLE_STOP,
            theme=theme,
        )

    def _ui(self, text):
        return ui_text(text, self.lang)

    def _translate_warning(self, text):
        return _translate_training_warning_text(text, self.lang)

    def _warnings_text(self):
        warnings = list(self.preflight.get("warnings", []))
        excluded_sections = [
            ("Missing images", self.preflight.get("excluded_missing_images", [])),
            ("Unreadable images", self.preflight.get("excluded_invalid_images", [])),
            ("Zero-annotation images", self.preflight.get("excluded_zero_annotation_images", [])),
            ("Invalid-annotation images", self.preflight.get("excluded_invalid_annotation_images", [])),
        ]
        lines = []
        if warnings:
            lines.append(self._ui("Warnings:"))
            lines.extend(f"- {self._translate_warning(warning)}" for warning in warnings)
        else:
            lines.append(self._ui("No warnings. The current saved annotations satisfy the training gate."))
        for title, values in excluded_sections:
            if values:
                lines.append("")
                lines.append(f"{self._ui(title)}:")
                lines.extend(f"- {os.path.basename(str(value))}" for value in values)
        return "\n".join(lines)

    def _build_overall_summary(self):
        locator_count = int(self.preflight.get("locator_image_count", 0))
        parts_count = int(self.preflight.get("parts_image_count", 0))
        locator_ready = self._ui("Ready") if locator_count > 0 else self._ui("Skipped")
        sam_ready = self._ui("Ready") if parts_count > 0 else self._ui("Skipped")
        selected_locator_size = format_size_pair(self.preflight.get("selected_locator_size"))
        if self.preflight.get("mixed_native_resolutions"):
            mixed_note = tr("Mixed native image resolutions detected among locator-eligible images. Training will unify them to the smallest native resolution tier among eligible images: {0}. Continue?", self.lang).format(selected_locator_size)
        else:
            mixed_note = self._ui("Mixed-resolution decision: locator training will use {0}.").format(selected_locator_size)
        return (
            f"{self._ui('Locator stage: {0} | SAM stage: {1}').format(locator_ready, sam_ready)}\n"
            f"{self._ui('Locator size: {0}').format(selected_locator_size)}\n"
            f"{mixed_note}"
        )

    def _make_readonly_text(self, text):
        box = QTextEdit()
        box.setReadOnly(True)
        box.setPlainText(text)
        box.setMinimumHeight(160)
        return box

    def _coverage_lines(self, title, total_count, train_count, val_count, total_text, train_text, val_text):
        lines = [
            self._ui(title),
            f"  {self._ui('total images: {0}').format(total_count)}",
            f"  {self._ui('train images: {0}').format(train_count)}",
            f"  {self._ui('val images: {0}').format(val_count)}",
            f"  {self._ui('total coverage: {0}').format(total_text)}",
            f"  {self._ui('train coverage: {0}').format(train_text)}",
            f"  {self._ui('val coverage: {0}').format(val_text)}",
        ]
        return "\n".join(lines)

    def _build_overview_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        selected_locator_size = format_size_pair(self.preflight.get("selected_locator_size"))
        locator_size_summary = str(self.preflight.get("locator_size_summary", "none") or "none")
        overview_lines = [
            self._ui("Training scope: {0}").format(
                f"{self.preflight.get('training_scope_label', self._ui('All Images'))} ({int(self.preflight.get('training_scope_image_count', 0) or 0)})"
            ),
            self._ui("Locator eligible images: {0}").format(int(self.preflight.get('locator_image_count', 0))),
            self._ui("SAM/parts eligible images: {0}").format(int(self.preflight.get('parts_image_count', 0))),
            self._ui("Selected locator size: {0}").format(selected_locator_size),
            self._ui("Eligible locator native sizes: {0}").format(locator_size_summary),
            self._ui("Mixed native resolutions: {0}").format(_yes_no_text(self.preflight.get('mixed_native_resolutions'), self.lang)),
        ]
        layout.addWidget(self._make_readonly_text("\n".join(overview_lines)))
        return tab

    def _build_coverage_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        locator_text = self._coverage_lines(
            "Locator coverage",
            int(self.preflight.get("locator_image_count", 0)),
            len(self.preflight.get("locator_train_data", []) or []),
            len(self.preflight.get("locator_val_data", []) or []),
            describe_part_coverage(self.preflight.get("locator_part_counts", {}), self.preflight.get("locator_scope", [])),
            describe_part_coverage(self.preflight.get("locator_train_part_counts", {}), self.preflight.get("locator_scope", [])),
            describe_part_coverage(self.preflight.get("locator_val_part_counts", {}), self.preflight.get("locator_scope", [])),
        )
        parts_text = self._coverage_lines(
            "SAM / parts coverage",
            int(self.preflight.get("parts_image_count", 0)),
            len(self.preflight.get("parts_train_data", []) or []),
            len(self.preflight.get("parts_val_data", []) or []),
            describe_part_coverage(self.preflight.get("parts_part_counts", {}), self.preflight.get("taxonomy", [])),
            describe_part_coverage(self.preflight.get("parts_train_part_counts", {}), self.preflight.get("taxonomy", [])),
            describe_part_coverage(self.preflight.get("parts_val_part_counts", {}), self.preflight.get("taxonomy", [])),
        )
        layout.addWidget(self._make_readonly_text(locator_text + "\n\n" + parts_text))
        return tab

    def _build_warnings_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(self._make_readonly_text(self._warnings_text()))
        return tab

    def _accept_training(self):
        self._accepted = True
        self._accepted_mixed_resolution = not bool(self.preflight.get("mixed_native_resolutions"))
        self.accept()

    def accepted_training(self):
        return self._accepted

    def accepted_mixed_resolution(self):
        return self._accepted_mixed_resolution

class TrainingReportDialog(QDialog):
    def __init__(self, report_data, parent=None, lang="en"):
        super().__init__(parent)
        self.lang = lang
        self.setWindowTitle(tr("Training Report & Validation", self.lang))
        self.resize(1200, 800)
        self.report_data = dict(report_data or {})
        self.validation_rows = self._load_validation_rows()
        self.filtered_validation_rows = list(self.validation_rows)
        self.report_summary = self._load_report_summary()
        
        layout = QVBoxLayout(self)
        
        tabs = QTabWidget()

        tab_summary = QWidget()
        summary_layout = QVBoxLayout(tab_summary)
        self.summary_box = QTextEdit()
        self.summary_box.setReadOnly(True)
        self.summary_box.setPlainText(self._build_summary_text())
        summary_layout.addWidget(self.summary_box)
        tabs.addTab(tab_summary, tr("Summary", self.lang))
        
        # Tab 1: Metrics Plot
        tab_metrics = QWidget()
        layout_m = QVBoxLayout(tab_metrics)
        self.lbl_metrics = QLabel(tr("No Metrics Generated", self.lang))
        self.lbl_metrics.setAlignment(Qt.AlignCenter)
        if report_data.get('metrics') and os.path.exists(report_data['metrics']):
            from PySide6.QtGui import QPixmap
            pix = QPixmap(report_data['metrics'])
            self.lbl_metrics.setPixmap(pix.scaled(1000, 700, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout_m.addWidget(self.lbl_metrics)
        tabs.addTab(tab_metrics, tr("Training Metrics", self.lang))
        
        # Tab 2: Validation Samples
        tab_val = QWidget()
        layout_v = QVBoxLayout(tab_val)
        
        # Controls for deterministic browsing
        ctrl_layout = QHBoxLayout()
        ctrl_layout.addWidget(QLabel(tr("Show Validation Set %:", self.lang)))
        
        self.slider_pct = NoWheelSlider(Qt.Horizontal)
        self.slider_pct.setRange(5, 100)
        self.slider_pct.setValue(20)
        self.slider_pct.setTickPosition(QSlider.TicksBelow)
        self.slider_pct.setTickInterval(10)
        
        self.lbl_pct = QLabel("20%")
        self.slider_pct.valueChanged.connect(lambda v: self.lbl_pct.setText(f"{v}%"))
        
        ctrl_layout.addWidget(self.slider_pct)
        ctrl_layout.addWidget(self.lbl_pct)

        self.validation_filter = NoWheelComboBox()
        self.validation_filter.addItem(tr("All validation", self.lang), "all")
        self.validation_filter.addItem(tr("Macro locator", self.lang), "macro_locator")
        self.validation_filter.currentIndexChanged.connect(self.load_gallery)
        ctrl_layout.addWidget(self.validation_filter)
        
        btn_load = QPushButton(tr("Load Samples", self.lang))
        btn_load.clicked.connect(self.load_gallery)
        ctrl_layout.addWidget(btn_load)
        ctrl_layout.addStretch()
        
        layout_v.addLayout(ctrl_layout)
        
        # Scroll Area
        scroll_v = QScrollArea()
        scroll_v.setWidgetResizable(True)
        self.content_v = QWidget()
        self.layout_gallery = QVBoxLayout(self.content_v) # Main layout for scroll content
        
        # 1. Initial Summary Image
        self.lbl_val = QLabel(tr("No Validation Summary", self.lang))
        self.lbl_val.setAlignment(Qt.AlignCenter)
        if report_data.get('val') and os.path.exists(report_data['val']):
            from PySide6.QtGui import QPixmap
            pix = QPixmap(report_data['val'])
            self.lbl_val.setPixmap(pix)
            self.layout_gallery.addWidget(QLabel(tr("--- Initial Summary (Top 6) ---", self.lang)))
            self.layout_gallery.addWidget(self.lbl_val)
        
        self.validation_index_table = QTableWidget(0, 5)
        self.validation_index_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.validation_index_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.validation_index_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.validation_index_table.setAlternatingRowColors(True)
        self.validation_index_table.verticalHeader().setVisible(False)
        self.validation_index_table.horizontalHeader().setStretchLastSection(True)
        self.validation_index_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.validation_index_table.setHorizontalHeaderLabels([
            ui_text("ID", self.lang),
            ui_text("Image", self.lang),
            ui_text("Source", self.lang),
            ui_text("Valid Parts", self.lang),
            ui_text("Max Error(px)", self.lang),
        ])
        self.validation_index_table.itemSelectionChanged.connect(self._load_selected_detail_preview)
        layout_v.addWidget(self.validation_index_table)

        # 2. Dynamic Grid Placeholder
        self.grid_widget = QWidget()
        self.grid_layout = None # Will be created on load
        self.layout_gallery.addWidget(QLabel(tr("--- Detailed Inspection ---", self.lang)))
        self.layout_gallery.addWidget(self.grid_widget)
        self.layout_gallery.addStretch()
        
        scroll_v.setWidget(self.content_v)
        layout_v.addWidget(scroll_v)
        tabs.addTab(tab_val, tr("Validation Inspection", self.lang))
        
        layout.addWidget(tabs)
        
        # Bottom Buttons
        btn_layout = QHBoxLayout()
        btn_open = QPushButton(tr("Open Report Folder", self.lang))
        btn_open.clicked.connect(self.open_folder)
        btn_close = QPushButton(tr("Close", self.lang))
        btn_close.clicked.connect(self.accept)
        
        btn_layout.addWidget(btn_open)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

        self.load_gallery()

    def _ui(self, text):
        return ui_text(text, self.lang)

    def _load_report_summary(self):
        summary_path = self.report_data.get("report_summary")
        if summary_path and os.path.exists(summary_path):
            try:
                with open(summary_path, "r", encoding="utf-8") as handle:
                    loaded = json.load(handle)
                    if isinstance(loaded, dict):
                        return loaded
            except Exception:
                pass
        summary = self.report_data.get("validation_summary")
        return dict(summary or {})

    def _load_validation_rows(self):
        if isinstance(self.report_data.get("validation_rows"), list):
            return [dict(row) for row in self.report_data.get("validation_rows", []) if isinstance(row, dict)]
        index_path = self.report_data.get("validation_index")
        rows = []
        if index_path and os.path.exists(index_path):
            try:
                with open(index_path, "r", encoding="utf-8", newline="") as handle:
                    reader = csv.DictReader(handle)
                    for row in reader:
                        rows.append(dict(row))
            except Exception:
                pass
        return rows

    def _build_summary_text(self):
        lines = []
        if self.report_summary:
            context = self.report_summary.get("training_context") if isinstance(self.report_summary.get("training_context"), dict) else {}
            training_scope = context.get("training_scope") if isinstance(context.get("training_scope"), dict) else {}
            if training_scope:
                lines.append(
                    tr("Training scope: {0} ({1} image(s))", self.lang).format(
                        training_scope.get("label", self._ui("All Images")),
                        training_scope.get("image_count", 0),
                    )
                )
            lines.append(self._ui("Validation count: {0}").format(self.report_summary.get('validation_count', 0)))
            lines.append(self._ui("Preview count: {0}").format(self.report_summary.get('validation_preview_count', 0)))
            provenance_counts = self.report_summary.get("validation_provenance_counts", {}) or {}
            if provenance_counts:
                lines.append(self._ui("Provenance counts:"))
                for key, value in sorted(provenance_counts.items()):
                    lines.append(f"- {_translate_validation_provenance(key, self.lang)}: {value}")
            metrics_name = self.report_summary.get("metrics_plot")
            if metrics_name:
                lines.append(self._ui("Metrics plot: {0}").format(metrics_name))
            validation_index = self.report_summary.get("validation_index_csv")
            if validation_index:
                lines.append(self._ui("Validation index: {0}").format(validation_index))
        else:
            lines.append(self._ui("No structured report summary found."))

        if self.validation_rows:
            lines.append("")
            lines.append(self._ui("Validation samples:"))
            for row in self.validation_rows[:10]:
                lines.append(
                    f"- {row.get('sample_id', '')}: {row.get('image_name', '')} | {_translate_validation_provenance(row.get('provenance', ''), self.lang)} | {row.get('error_summary', '')}"
                )
        return "\n".join(lines)

    def _current_filtered_rows(self):
        filter_value = self.validation_filter.currentData() if hasattr(self, "validation_filter") else "all"
        if filter_value in (None, "all"):
            return list(self.validation_rows)
        return [row for row in self.validation_rows if row.get("provenance") == filter_value]

    def _detail_image_path(self, row):
        details_dir = self.report_data.get("details_dir") or os.path.join(self.report_data.get("dir", ""), "val_details")
        detail_name = row.get("detail_image") if isinstance(row, dict) else None
        if not detail_name:
            return None
        path = os.path.join(details_dir, detail_name)
        return path if os.path.exists(path) else None

    def _rebuild_gallery_grid(self, selected_rows):
        if self.grid_layout:
            while self.grid_layout.count():
                item = self.grid_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
            QWidget().setLayout(self.grid_layout)

        from PySide6.QtWidgets import QGridLayout
        from PySide6.QtGui import QPixmap

        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(10)

        row_idx = 0
        col_idx = 0
        max_cols = 3
        for row in selected_rows:
            detail_path = self._detail_image_path(row)
            if not detail_path:
                continue
            label = QLabel()
            pix = QPixmap(detail_path)
            if pix.width() > 400:
                pix = pix.scaledToWidth(400, Qt.SmoothTransformation)
            label.setPixmap(pix)
            label.setToolTip(f"{row.get('sample_id', '')} | {row.get('image_name', '')}")
            self.grid_layout.addWidget(label, row_idx, col_idx)
            col_idx += 1
            if col_idx >= max_cols:
                col_idx = 0
                row_idx += 1

    def _populate_validation_index_table(self, selected_rows):
        self.validation_index_table.setRowCount(len(selected_rows))
        for row_idx, row in enumerate(selected_rows):
            values = [
                row.get("sample_id", ""),
                row.get("image_name", ""),
                _translate_validation_provenance(row.get("provenance", ""), self.lang),
                row.get("valid_parts", ""),
                row.get("max_error_px", ""),
            ]
            for col_idx, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, dict(row))
                self.validation_index_table.setItem(row_idx, col_idx, item)

    def _load_selected_detail_preview(self):
        current_row = self.validation_index_table.currentRow()
        if current_row < 0:
            return
        item = self.validation_index_table.item(current_row, 0)
        if not item:
            return
        row = item.data(Qt.UserRole)
        if not isinstance(row, dict):
            return
        self._rebuild_gallery_grid([row])

    def load_gallery(self):
        val_dir = self.report_data.get("details_dir") or os.path.join(self.report_data.get('dir', ''), "val_details")
        if not os.path.exists(val_dir):
            QMessageBox.warning(self, tr("Error", self.lang), tr("No validation details found at {0}", self.lang).format(val_dir))
            return

        if not self.validation_rows:
            QMessageBox.warning(self, tr("Error", self.lang), tr("No images found.", self.lang))
            return

        filtered_rows = self._current_filtered_rows()
        if not filtered_rows:
            self.filtered_validation_rows = []
            self.validation_index_table.setRowCount(0)
            self._rebuild_gallery_grid([])
            self.lbl_pct.setText(tr("{0}% ({1} images)", self.lang).format(self.slider_pct.value(), 0))
            return

        pct = self.slider_pct.value()
        count = max(1, int(len(filtered_rows) * (pct / 100.0)))
        selected_rows = filtered_rows[:count]
        self.filtered_validation_rows = list(selected_rows)
        self._populate_validation_index_table(selected_rows)
        self._rebuild_gallery_grid(selected_rows[: min(6, len(selected_rows))])
        if selected_rows:
            self.validation_index_table.setCurrentCell(0, 0)
        self.lbl_pct.setText(tr("{0}% ({1} images)", self.lang).format(pct, count))
        
    def open_folder(self):
        d = self.report_data.get('dir')
        if d:
            open_path(d)


class TrainingResultBrowserDialog(QDialog):
    def __init__(self, reports, parent=None, lang="en", preview_callback=None, refresh_callback=None):
        super().__init__(parent)
        self.lang = lang
        self.reports = list(reports or [])
        self.preview_callback = preview_callback
        self.refresh_callback = refresh_callback
        self.setWindowTitle(tr("Training Result Browser", self.lang))
        self.resize(1120, 620)

        layout = QVBoxLayout(self)

        self.table = QTableWidget(0, 7)
        self.table.setObjectName("trainingResultBrowserTable")
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.setHorizontalHeaderLabels([
            tr("Type", self.lang),
            tr("Target", self.lang),
            tr("Backend", self.lang),
            tr("Strategy", self.lang),
            tr("Samples", self.lang),
            tr("Time", self.lang),
            tr("Report Folder", self.lang),
        ])
        self.table.itemSelectionChanged.connect(self._refresh_actions)
        self.table.doubleClicked.connect(lambda _index=None: self.preview_selected())
        layout.addWidget(self.table, 1)

        button_row = QHBoxLayout()
        self.btn_preview = QPushButton(tr("Preview Report", self.lang))
        self.btn_preview.clicked.connect(self.preview_selected)
        apply_semantic_button_style(self.btn_preview, BUTTON_ROLE_RUN)
        button_row.addWidget(self.btn_preview)

        self.btn_open_folder = QPushButton(tr("Open Report Folder", self.lang))
        self.btn_open_folder.clicked.connect(self.open_selected_folder)
        apply_semantic_button_style(self.btn_open_folder, BUTTON_ROLE_NEUTRAL)
        button_row.addWidget(self.btn_open_folder)

        self.btn_refresh = QPushButton(tr("Refresh", self.lang))
        self.btn_refresh.clicked.connect(self.refresh_reports)
        apply_semantic_button_style(self.btn_refresh, BUTTON_ROLE_NEUTRAL)
        button_row.addWidget(self.btn_refresh)

        button_row.addStretch()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_button = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_button:
            close_button.setText(tr("Close", self.lang))
        buttons.rejected.connect(self.reject)
        button_row.addWidget(buttons)
        layout.addLayout(button_row)

        self.populate(self.reports)

    def populate(self, reports):
        self.reports = list(reports or [])
        self.table.setRowCount(len(self.reports))
        for row_idx, report in enumerate(self.reports):
            values = [
                report.get("type_label", ""),
                report.get("target_label", ""),
                report.get("backend_label", ""),
                report.get("strategy_label", ""),
                report.get("samples_label", ""),
                report.get("time_label", ""),
                report.get("dir", ""),
            ]
            for col_idx, value in enumerate(values):
                item = QTableWidgetItem(str(value or ""))
                item.setToolTip(str(value or ""))
                item.setData(Qt.UserRole, dict(report))
                self.table.setItem(row_idx, col_idx, item)
        self.table.resizeColumnsToContents()
        if self.reports:
            self.table.setCurrentCell(0, 0)
        self._refresh_actions()

    def selected_report(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if not item:
            return None
        data = item.data(Qt.UserRole)
        return dict(data) if isinstance(data, dict) else None

    def _refresh_actions(self):
        has_selection = self.selected_report() is not None
        self.btn_preview.setEnabled(has_selection)
        self.btn_open_folder.setEnabled(has_selection)

    def preview_selected(self):
        report = self.selected_report()
        if report and callable(self.preview_callback):
            self.preview_callback(report)

    def open_selected_folder(self):
        report = self.selected_report()
        folder = report.get("dir") if isinstance(report, dict) else ""
        if folder:
            open_path(folder)

    def refresh_reports(self):
        if callable(self.refresh_callback):
            self.populate(self.refresh_callback() or [])


class RouteManagementPanel(QWidget):
    NODE_TYPE_ROLE = Qt.UserRole
    NODE_PAYLOAD_ROLE = Qt.UserRole + 1

    def __init__(self, owner, lang="en", parent=None):
        super().__init__(parent)
        self.owner = owner
        self.lang = lang
        self.init_ui()
        self.retranslate_ui()

    def _ui(self, text):
        return ui_text(text, self.lang)

    def _tr(self, text):
        return tr(text, self.lang)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.header_label = QLabel()
        self.header_label.setObjectName("HeaderLabel")
        layout.addWidget(self.header_label)

        self.note_label = QLabel()
        self.note_label.setWordWrap(True)
        self.note_label.setObjectName("mutedLabel")
        layout.addWidget(self.note_label)

        self.route_tree = QTreeWidget()
        self.route_tree.setObjectName("projectRouteTree")
        self.route_tree.setAlternatingRowColors(True)
        self.route_tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.route_tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.route_tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.route_tree.setRootIsDecorated(True)
        self.route_tree.setItemsExpandable(True)
        self.route_tree.setUniformRowHeights(True)
        self.route_tree.header().setStretchLastSection(True)
        self.route_tree.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.route_tree.itemSelectionChanged.connect(self.update_action_buttons)
        self.route_tree.setMinimumHeight(380)
        self.route_tree.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.route_tree, 1)

        button_row = QHBoxLayout()
        self.btn_refresh_routes = QPushButton()
        self.btn_refresh_routes.clicked.connect(self.refresh_route_table)
        apply_semantic_button_style(self.btn_refresh_routes, BUTTON_ROLE_NEUTRAL)
        button_row.addWidget(self.btn_refresh_routes)

        self.btn_appoint_route_expert = QPushButton()
        self.btn_appoint_route_expert.clicked.connect(self.appoint_selected_route_expert)
        apply_semantic_button_style(self.btn_appoint_route_expert, BUTTON_ROLE_COMMIT)
        button_row.addWidget(self.btn_appoint_route_expert)

        self.btn_toggle_route = QPushButton()
        self.btn_toggle_route.clicked.connect(self.toggle_selected_route_enabled)
        apply_semantic_button_style(self.btn_toggle_route, BUTTON_ROLE_NEUTRAL)
        button_row.addWidget(self.btn_toggle_route)

        self.btn_delete_route = QPushButton()
        self.btn_delete_route.clicked.connect(self.delete_selected_route)
        apply_semantic_button_style(self.btn_delete_route, BUTTON_ROLE_DESTRUCTIVE)
        button_row.addWidget(self.btn_delete_route)

        self.btn_edit_expert_note = QPushButton()
        self.btn_edit_expert_note.clicked.connect(self.edit_selected_expert_note)
        apply_semantic_button_style(self.btn_edit_expert_note, BUTTON_ROLE_NEUTRAL)
        button_row.addWidget(self.btn_edit_expert_note)

        self.btn_delete_expert_file = QPushButton()
        self.btn_delete_expert_file.clicked.connect(self.delete_selected_expert_file)
        apply_semantic_button_style(self.btn_delete_expert_file, BUTTON_ROLE_DESTRUCTIVE)
        button_row.addWidget(self.btn_delete_expert_file)

        layout.addLayout(button_row)

    def set_language(self, lang):
        self.lang = lang
        self.retranslate_ui()
        self.refresh_route_table()

    def set_theme(self, theme):
        apply_theme_button_style(self.btn_refresh_routes, BUTTON_ROLE_NEUTRAL, "", theme)
        apply_theme_button_style(self.btn_appoint_route_expert, BUTTON_ROLE_COMMIT, "", theme)
        apply_theme_button_style(self.btn_toggle_route, BUTTON_ROLE_NEUTRAL, "", theme)
        apply_theme_button_style(self.btn_delete_route, BUTTON_ROLE_DESTRUCTIVE, "", theme)
        apply_theme_button_style(self.btn_edit_expert_note, BUTTON_ROLE_NEUTRAL, "", theme)
        apply_theme_button_style(self.btn_delete_expert_file, BUTTON_ROLE_DESTRUCTIVE, "", theme)

    def retranslate_ui(self):
        self.header_label.setText(self._ui("Project Routes"))
        self.note_label.setText(
            self._ui(
                "Manage parent-child expert routes in the current 2D workflow here. Deleting a route removes only this project record; training or appointing an expert later can register a candidate again."
            )
        )
        self.btn_refresh_routes.setText(self._tr("Refresh"))
        self.btn_appoint_route_expert.setText(self._tr("Appoint Expert"))
        self.btn_delete_route.setText(self._ui("Delete Route"))
        self.btn_delete_route.setToolTip(self._ui("Delete the selected project route only."))
        self.btn_edit_expert_note.setText(self._ui("Edit Expert Note"))
        self.btn_edit_expert_note.setToolTip(self._ui("Select an expert row to edit its display note."))
        self.btn_delete_expert_file.setText(self._ui("Delete Expert File"))
        self.btn_delete_expert_file.setToolTip(self._ui("Select an available expert file to delete the model file from disk."))
        self.route_tree.setHeaderLabels([
            self._ui("Parent"),
            self._ui("Child"),
            self._ui("Enabled"),
            self._ui("Backend"),
            self._ui("Expert"),
            self._ui("Status"),
            self._ui("Profile Fit"),
            self._ui("Source"),
        ])
        self.update_action_buttons()

    def _selected_node_payload(self):
        item = self.route_tree.currentItem()
        if item is None:
            return None
        payload = item.data(0, self.NODE_PAYLOAD_ROLE)
        return dict(payload) if isinstance(payload, dict) else None

    def _selected_route_entry(self):
        payload = self._selected_node_payload() or {}
        route = payload.get("route")
        return dict(route) if isinstance(route, dict) else None

    def _selected_expert_entry(self):
        payload = self._selected_node_payload() or {}
        expert = payload.get("expert")
        return dict(expert) if isinstance(expert, dict) else None

    def _make_node_payload(self, kind, *, route=None, expert=None, parent_part=None):
        payload = {"kind": str(kind or "")}
        if isinstance(route, dict):
            payload["route"] = dict(route)
        if isinstance(expert, dict):
            payload["expert"] = dict(expert)
        if parent_part:
            payload["parent_part"] = str(parent_part)
        return payload

    def _available_experts_by_part(self):
        cascade_manager = getattr(getattr(self.owner, "engine", None), "cascade_manager", None)
        if cascade_manager is None:
            return {}

        experts_by_part = {}
        for expert in cascade_manager.list_available_experts() or []:
            if not isinstance(expert, dict):
                continue
            expert_part = str(expert.get("expert_part") or "").strip()
            if not expert_part:
                continue
            experts_by_part.setdefault(expert_part, []).append(dict(expert))
        return experts_by_part

    def _expert_notes(self):
        weights_dir = getattr(getattr(self.owner, "engine", None), "weights_dir", "")
        return load_expert_notes(weights_dir)

    def _expert_root_dir(self):
        weights_dir = getattr(getattr(self.owner, "engine", None), "weights_dir", "")
        return os.path.abspath(os.path.join(str(weights_dir or ""), "experts"))

    def _is_safe_expert_file_path(self, file_path):
        if not isinstance(file_path, str) or not file_path:
            return False
        try:
            expert_root = self._expert_root_dir()
            file_abs = os.path.abspath(file_path)
            return (
                os.path.commonpath([expert_root, file_abs]) == expert_root
                and os.path.isfile(file_abs)
                and file_abs.lower().endswith(".pth")
            )
        except Exception:
            return False

    def _selected_existing_expert_file(self):
        expert = self._selected_expert_entry()
        if not expert:
            return None
        file_path = expert.get("path")
        if not self._is_safe_expert_file_path(file_path):
            return None
        expert_id = str(expert.get("expert_id") or "").strip()
        return {"path": os.path.abspath(file_path), "expert_id": expert_id}

    def _route_expert_candidates(self, route_entry, available_experts_by_part):
        route = dict(route_entry or {})
        cascade_manager = getattr(getattr(self.owner, "engine", None), "cascade_manager", None)
        resolve_route_expert_path = getattr(cascade_manager, "resolve_route_expert_path", None)
        child_part = str(route.get("child") or "").strip()

        appointed_label = format_expert_label(route)
        appointed_candidate = None
        if appointed_label != "Unappointed":
            appointed_candidate = {
                "expert_id": appointed_label,
                "expert_part": route.get("expert_part") or route.get("child"),
                "expert_filename": route.get("expert_filename"),
                "expert_backend": _route_backend_from_entry(route),
                "expert_manifest": _route_manifest_from_entry(route),
                "input_size": route.get("input_size"),
                "backend_params": route.get("backend_params") if isinstance(route.get("backend_params"), dict) else {},
                "note": route.get("note"),
                "path": resolve_route_expert_path(route) if callable(resolve_route_expert_path) else None,
            }

        candidates = []
        persisted_candidates = get_route_persisted_expert_candidates(route)
        runtime_candidates = available_experts_by_part.get(child_part, [])
        merged_candidates = merge_expert_candidates(
            persisted_candidates,
            runtime_candidates,
            appointed_expert=appointed_candidate,
        )

        available_by_id = {}
        for expert in runtime_candidates:
            expert_id = str(expert.get("expert_id") or "").strip()
            if not expert_id:
                continue
            available_by_id[expert_id] = dict(expert)

        persisted_ids = {
            str(candidate.get("expert_id") or "").strip()
            for candidate in persisted_candidates
            if isinstance(candidate, dict)
        }

        for candidate in merged_candidates:
            expert_id = str(candidate.get("expert_id") or "").strip()
            if not expert_id:
                continue

            runtime_match = available_by_id.get(expert_id)
            is_appointed = expert_id == appointed_label
            is_persisted = expert_id in persisted_ids or is_appointed
            merged_candidate = dict(candidate)
            if isinstance(runtime_match, dict):
                merged_candidate.update(runtime_match)

            merged_candidate["appointed"] = is_appointed
            merged_candidate["is_persisted"] = is_persisted
            merged_candidate["is_discoverable"] = isinstance(runtime_match, dict)
            path_value = merged_candidate.get("path")
            merged_candidate["file_exists"] = bool(path_value) and os.path.exists(path_value)
            candidates.append(merged_candidate)
        return candidates

    def _set_item_payload(self, item, payload):
        item.setData(0, self.NODE_TYPE_ROLE, payload.get("kind"))
        item.setData(0, self.NODE_PAYLOAD_ROLE, payload)

    def _active_child_route_backend(self):
        defaults = _runtime_child_backend_defaults(getattr(self.owner, "project", None))
        return _route_backend_from_child_backend(defaults.get("backend_type", CHILD_BACKEND_VIT_B))

    def _route_profile_fit_text(self, route_entry):
        route = dict(route_entry or {})
        route_label = format_expert_label(route)
        if route_label == "Unappointed":
            return self._ui("No appointed expert")
        default_backend = self._active_child_route_backend()
        route_backend = _route_backend_from_entry(route)
        if route_backend == default_backend:
            return self._ui("Matches active profile")
        return self._ui("Route-specific backend")

    def _route_profile_fit_tooltip(self, route_entry):
        route = dict(route_entry or {})
        default_backend = self._active_child_route_backend()
        route_backend = _route_backend_from_entry(route)
        return self._ui("Active profile default: {0}\nRoute expert backend: {1}").format(
            _route_backend_label(default_backend, self.lang),
            _route_backend_label(route_backend, self.lang),
        )

    def _build_route_tree_item(self, parent_item, route_entry, expert_candidates):
        route = dict(route_entry or {})
        expert_notes = self._expert_notes()
        route_item = QTreeWidgetItem(parent_item)
        self._set_item_payload(route_item, self._make_node_payload("route", route=route))
        route_item.setText(1, str(route.get("child") or ""))
        route_item.setText(2, _yes_no_text(route.get("enabled"), self.lang))
        backend_value = _route_backend_from_entry(route)
        route_item.setText(3, _route_backend_label(backend_value, self.lang))
        route_item.setToolTip(3, f"{_route_backend_label(backend_value, self.lang)}\n{backend_value}")
        route_label = format_expert_label(route)
        if route_label != "Unappointed":
            route_note = expert_notes.get(route_label, "")
            route_display = format_expert_display_name(route_label, route_note)
            route_item.setText(4, route_display)
            manifest_value = _route_manifest_from_entry(route)
            tooltip = f"{route_display}\n{route_label}"
            if manifest_value:
                tooltip += f"\n{manifest_value}"
            route_item.setToolTip(4, tooltip)
        else:
            route_item.setText(4, self._ui("Not appointed"))
        route_item.setText(5, self._route_runtime_status(route))
        route_item.setText(6, self._route_profile_fit_text(route))
        route_item.setToolTip(6, self._route_profile_fit_tooltip(route))
        route_item.setText(7, _translate_route_registration_source(route.get("registration_source"), self.lang))

        if not expert_candidates:
            placeholder_item = QTreeWidgetItem(route_item)
            self._set_item_payload(placeholder_item, self._make_node_payload("expert_placeholder", route=route))
            placeholder_item.setText(3, _route_backend_label(backend_value, self.lang))
            placeholder_item.setText(4, self._ui("Not appointed"))
            placeholder_item.setText(5, self._ui("Expert not appointed yet"))
            placeholder_item.setText(6, self._ui("No appointed expert"))
            placeholder_item.setFlags(placeholder_item.flags() & ~Qt.ItemIsSelectable)
            return route_item

        for expert in expert_candidates:
            expert_item = QTreeWidgetItem(route_item)
            self._set_item_payload(expert_item, self._make_node_payload("expert", route=route, expert=expert))
            expert_id = str(expert.get("expert_id") or "").strip()
            is_appointed = bool(expert.get("appointed"))
            is_discoverable = bool(expert.get("is_discoverable"))
            is_persisted = bool(expert.get("is_persisted"))
            file_exists = bool(expert.get("file_exists"))
            expert_note = expert_notes.get(expert_id, "")
            expert_label = format_expert_display_name(expert_id, expert_note, appointed=is_appointed)
            backend_value = expert.get("expert_backend") or route.get("expert_backend") or ROUTE_BACKEND_VIT_B_BLINK
            manifest_value = expert.get("expert_manifest") or route.get("expert_manifest") or ""
            expert_item.setText(3, _route_backend_label(backend_value, self.lang))
            expert_item.setText(4, expert_label)
            expert_item.setToolTip(
                3,
                f"{_route_backend_label(backend_value, self.lang)}\n{backend_value}",
            )
            expert_item.setToolTip(
                4,
                f"{expert_label}\n{expert_id}\n{manifest_value}".strip(),
            )
            if is_appointed:
                status_text = self._ui("Appointed")
            elif is_persisted and not file_exists:
                status_text = self._ui("Missing file history")
            elif is_persisted:
                status_text = self._ui("History")
            elif is_discoverable:
                status_text = self._ui("Discoverable")
            else:
                status_text = self._ui("Available")
            expert_item.setText(5, status_text)
            expert_item.setText(
                6,
                self._ui("Matches active profile")
                if backend_value == self._active_child_route_backend()
                else self._ui("Route-specific backend"),
            )
            expert_item.setToolTip(
                6,
                self._ui("Active profile default: {0}\nRoute expert backend: {1}").format(
                    _route_backend_label(self._active_child_route_backend(), self.lang),
                    _route_backend_label(backend_value, self.lang),
                ),
            )
            if is_appointed:
                expert_font = expert_item.font(4)
                expert_font.setBold(True)
                expert_item.setFont(4, expert_font)
                status_font = expert_item.font(5)
                status_font.setBold(True)
                expert_item.setFont(5, status_font)
        return route_item

    def _find_parent_item(self, parent_part):
        clean_parent = str(parent_part or "").strip()
        for index in range(self.route_tree.topLevelItemCount()):
            item = self.route_tree.topLevelItem(index)
            if item is None:
                continue
            payload = item.data(0, self.NODE_PAYLOAD_ROLE)
            if isinstance(payload, dict) and payload.get("kind") == "parent" and payload.get("parent_part") == clean_parent:
                return item
        return None

    def _find_route_item(self, parent_part, child_part):
        parent_item = self._find_parent_item(parent_part)
        clean_child = str(child_part or "").strip()
        if parent_item is None or not clean_child:
            return None
        for index in range(parent_item.childCount()):
            item = parent_item.child(index)
            if item is None:
                continue
            payload = item.data(0, self.NODE_PAYLOAD_ROLE)
            route = payload.get("route") if isinstance(payload, dict) else None
            if isinstance(route, dict) and route.get("parent") == str(parent_part or "").strip() and route.get("child") == clean_child:
                return item
        return None

    def _find_expert_item(self, parent_part, child_part, expert_id):
        route_item = self._find_route_item(parent_part, child_part)
        clean_expert_id = str(expert_id or "").strip()
        if route_item is None or not clean_expert_id:
            return None
        for index in range(route_item.childCount()):
            item = route_item.child(index)
            if item is None:
                continue
            payload = item.data(0, self.NODE_PAYLOAD_ROLE)
            expert = payload.get("expert") if isinstance(payload, dict) else None
            if isinstance(expert, dict) and str(expert.get("expert_id") or "").strip() == clean_expert_id:
                return item
        return None

    def _route_runtime_status(self, route_entry):
        if not route_entry:
            return self._ui("Unknown")
        block_reason = self.owner.engine.cascade_manager.get_route_block_reason(route_entry)
        if block_reason == "expert_unappointed":
            return self._ui("Expert not appointed yet")
        if block_reason == "expert_model_missing":
            return self._tr("Expert file missing")
        return self._ui("Enabled") if bool(route_entry.get("enabled", False)) else self._ui("Disabled")

    def refresh_route_table(self):
        routes = self.owner.project.iter_cascade_routes()
        experts_by_part = self._available_experts_by_part()
        self.route_tree.clear()
        parent_items = {}

        for route in routes:
            parent_part = str(route.get("parent") or "")
            parent_item = parent_items.get(parent_part)
            if parent_item is None:
                parent_item = QTreeWidgetItem(self.route_tree)
                self._set_item_payload(parent_item, self._make_node_payload("parent", parent_part=parent_part))
                parent_item.setText(0, parent_part)
                parent_item.setExpanded(True)
                parent_items[parent_part] = parent_item

            expert_candidates = self._route_expert_candidates(route, experts_by_part)
            route_item = self._build_route_tree_item(parent_item, route, expert_candidates)
            route_item.setExpanded(True)

        self.route_tree.expandAll()
        self.update_action_buttons()

    def update_action_buttons(self):
        payload = self._selected_node_payload() or {}
        route = self._selected_route_entry()
        expert = self._selected_expert_entry()
        selected_kind = str(payload.get("kind") or "")
        can_delete_missing_history = (
            selected_kind == "expert"
            and bool(route)
            and bool(expert)
            and bool(expert.get("is_persisted"))
            and not bool(expert.get("file_exists"))
            and not bool(expert.get("appointed"))
            and hasattr(self.owner.project, "remove_cascade_route_expert_candidate")
        )
        self.btn_appoint_route_expert.setEnabled(selected_kind == "expert" and bool(self._selected_expert_entry()))
        self.btn_delete_route.setEnabled((selected_kind == "route" and bool(route)) or can_delete_missing_history)
        can_edit_expert_note = selected_kind == "expert" and bool(expert) and bool(str(expert.get("expert_id") or "").strip())
        self.btn_edit_expert_note.setEnabled(can_edit_expert_note)
        can_delete_expert_file = selected_kind == "expert" and bool(self._selected_existing_expert_file())
        self.btn_delete_expert_file.setEnabled(can_delete_expert_file)
        if can_delete_expert_file:
            self.btn_delete_expert_file.setToolTip(self._ui("Delete the selected expert model file from disk."))
        else:
            self.btn_delete_expert_file.setToolTip(self._ui("Select an available expert file to delete the model file from disk."))
        self.btn_toggle_route.setEnabled(selected_kind == "route" and bool(route))
        self.btn_toggle_route.setText(
            self._tr("Disable Route") if route and route.get("enabled") else self._tr("Enable Route")
        )

    def edit_selected_expert_note(self):
        payload = self._selected_node_payload() or {}
        if str(payload.get("kind") or "") != "expert":
            return
        route = self._selected_route_entry()
        expert = self._selected_expert_entry()
        if not route or not expert:
            return
        expert_id = str(expert.get("expert_id") or "").strip()
        if not expert_id:
            return
        weights_dir = getattr(getattr(self.owner, "engine", None), "weights_dir", "")
        current_note = self._expert_notes().get(expert_id, "")
        note, ok = QInputDialog.getText(
            self,
            self._ui("Edit Expert Note"),
            self._ui("Expert display note:"),
            QLineEdit.Normal,
            current_note,
        )
        if not ok:
            return
        clean_note = set_expert_note(weights_dir, expert_id, note)
        parent_part = route.get("parent")
        child_part = route.get("child")
        self.refresh_route_table()
        refreshed_item = self._find_expert_item(parent_part, child_part, expert_id)
        if refreshed_item is not None:
            self.route_tree.setCurrentItem(refreshed_item)
        if clean_note:
            self.owner.log(self._ui("Updated expert note for {0}: {1}").format(expert_id, clean_note))
        else:
            self.owner.log(self._ui("Cleared expert note for {0}.").format(expert_id))

    def appoint_selected_route_expert(self):
        payload = self._selected_node_payload() or {}
        if str(payload.get("kind") or "") != "expert":
            return
        route = self._selected_route_entry()
        expert = self._selected_expert_entry()
        if not route or not expert:
            return
        selected_label = str(expert.get("expert_id") or "").strip()
        if not selected_label:
            return

        updated = self.owner.project.appoint_cascade_route_expert(
            route.get("parent"),
            route.get("child"),
            expert_id=selected_label,
            expert_backend=expert.get("expert_backend") or route.get("expert_backend") or ROUTE_BACKEND_VIT_B_BLINK,
            expert_manifest=expert.get("expert_manifest") or route.get("expert_manifest"),
            input_size=expert.get("input_size") or route.get("input_size"),
            backend_params=expert.get("backend_params") if isinstance(expert.get("backend_params"), dict) else route.get("backend_params"),
            note=expert.get("note") or route.get("note"),
        )
        if updated:
            self.refresh_route_table()
            self.owner.log(
                self._ui("Route {0} -> {1} now uses expert {2}.").format(
                    route.get("parent"),
                    route.get("child"),
                    selected_label,
                )
            )

    def toggle_selected_route_enabled(self):
        payload = self._selected_node_payload() or {}
        if str(payload.get("kind") or "") != "route":
            return
        route = self._selected_route_entry()
        if not route:
            return
        block_reason = self.owner.engine.cascade_manager.get_route_block_reason(route)
        if not route.get("enabled") and block_reason == "expert_unappointed":
            QMessageBox.information(self, self._tr("Appoint Expert"), self._ui("This route has no appointed expert yet. Appoint an expert first, then enable the route."))
            return
        if not route.get("enabled") and block_reason == "expert_model_missing":
            QMessageBox.information(self, self._tr("Appoint Expert"), self._ui("The appointed expert file for this route is missing. Reappoint an available expert before enabling the route."))
            return

        updated = self.owner.project.set_cascade_route_enabled(
            route.get("parent"),
            route.get("child"),
            not bool(route.get("enabled")),
        )
        if updated:
            self.refresh_route_table()
            if updated.get("enabled"):
                self.owner.log(self._ui("Route {0} -> {1} enabled.").format(updated.get("parent"), updated.get("child")))
            else:
                self.owner.log(self._ui("Route {0} -> {1} disabled.").format(updated.get("parent"), updated.get("child")))

    def delete_selected_route(self):
        payload = self._selected_node_payload() or {}
        if str(payload.get("kind") or "") == "expert":
            self.remove_selected_missing_expert_history()
            return
        if str(payload.get("kind") or "") != "route":
            return
        route = self._selected_route_entry()
        if not route:
            return
        reply = themed_yes_no_question(
            self,
            self._tr("Delete"),
            self._ui(
                "Delete project route {0} -> {1}?\n\nThis removes the current project route record only. If you reopen Blink later with the same parent/child context, Blink can register this route again as a candidate."
            ).format(route.get("parent"), route.get("child")),
            confirm_role=BUTTON_ROLE_DESTRUCTIVE,
        )
        if reply != QMessageBox.Yes:
            return
        if self.owner.project.delete_cascade_route(route.get("parent"), route.get("child")):
            self.refresh_route_table()
            self.owner.log(self._ui("Deleted route {0} -> {1}.").format(route.get("parent"), route.get("child")))

    def delete_selected_expert_file(self):
        file_info = self._selected_existing_expert_file()
        if not file_info:
            return
        file_path = file_info["path"]
        expert_id = file_info.get("expert_id") or os.path.basename(file_path)
        reply = themed_yes_no_question(
            self,
            self._ui("Delete Expert File"),
            self._ui(
                "Delete expert file {0}?\n\nThis removes the model file from disk and clears current-project expert references to it. Parent -> child route records are kept, but they will return to an unappointed state if this was the appointed expert."
            ).format(expert_id),
            confirm_role=BUTTON_ROLE_DESTRUCTIVE,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            os.remove(file_path)
            if expert_id:
                weights_dir = getattr(getattr(self.owner, "engine", None), "weights_dir", "")
                set_expert_note(weights_dir, expert_id, "")
            cascade_manager = getattr(getattr(self.owner, "engine", None), "cascade_manager", None)
            loaded_experts = getattr(cascade_manager, "loaded_experts", None)
            if isinstance(loaded_experts, dict):
                loaded_experts.clear()
            cleanup_refs = getattr(getattr(self.owner, "project", None), "remove_cascade_route_expert_references", None)
            cleanup_count = 0
            if callable(cleanup_refs):
                cleanup_count = int(cleanup_refs(expert_id, save=True) or 0)
            self.refresh_route_table()
            self.owner.log(self._ui("Deleted expert file {0}. Cleared {1} current-project route reference(s).").format(expert_id, cleanup_count))
        except Exception as exc:
            QMessageBox.critical(
                self,
                self._tr("Delete Model"),
                self._ui("Failed to delete expert file: {0}").format(exc),
            )

    def remove_selected_missing_expert_history(self):
        route = self._selected_route_entry()
        expert = self._selected_expert_entry()
        if not route or not expert:
            return
        if not bool(expert.get("is_persisted")) or bool(expert.get("file_exists")) or bool(expert.get("appointed")):
            return
        remove_candidate = getattr(self.owner.project, "remove_cascade_route_expert_candidate", None)
        if not callable(remove_candidate):
            return
        expert_id = str(expert.get("expert_id") or "").strip()
        if not expert_id:
            return
        reply = themed_yes_no_question(
            self,
            self._tr("Delete"),
            self._ui(
                "Remove missing expert history {0} from route {1} -> {2}?\n\nThis only cleans the current project route history. It does not delete any model file."
            ).format(expert_id, route.get("parent"), route.get("child")),
            confirm_role=BUTTON_ROLE_DESTRUCTIVE,
        )
        if reply != QMessageBox.Yes:
            return
        if remove_candidate(route.get("parent"), route.get("child"), expert_id):
            self.refresh_route_table()
            self.owner.log(
                self._ui("Removed missing expert history {0} from route {1} -> {2}.").format(
                    expert_id,
                    route.get("parent"),
                    route.get("child"),
                )
            )

class ModelSettingsDialog(QDialog):
    agent_requested = Signal(dict)

    def __init__(self, params, lang="en", parent=None, route_panel=None):
        super().__init__(parent)
        self.lang = lang
        self.route_panel = route_panel
        self.setWindowTitle(tr("2D/STL Morphology Model Settings", lang))
        self.resize(880, 680)
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        self.locator_scope_checks = []
        self.vlm_target_part_checks = []
        self.taxonomy = [str(part) for part in params.get("taxonomy", []) if str(part).strip()]
        self.initial_locator_scope = [str(part) for part in params.get("locator_scope", []) if str(part).strip()]
        self.vlm_image_group_definitions = self._normalize_vlm_image_group_definitions(
            params.get("vlm_image_group_definitions", [])
        )
        if not self.taxonomy:
            self.taxonomy = list(self.initial_locator_scope)
        if not self.initial_locator_scope:
            self.initial_locator_scope = list(self.taxonomy)
        model_profile_context = {
            "taxonomy": self.taxonomy,
            "locator_scope": self.initial_locator_scope,
            "parent_box_aspect_ratios": params.get("parent_box_aspect_ratios", {}),
            "vlm_preannotation": params.get("vlm_preannotation", {}),
            "child_auto_shrink_steps": params.get("blink_auto_shrink_steps", DEFAULT_CHILD_AUTO_SHRINK_STEPS),
        }
        raw_model_profiles = params.get("model_profiles", {})
        if (
            (not isinstance(raw_model_profiles, dict) or not raw_model_profiles.get("profiles"))
            and params.get("model_backend") == EXTERNAL_BACKEND_ID
        ):
            model_profile_context["parent_backend_type"] = PARENT_BACKEND_EXTERNAL
            model_profile_context["external_parent_backend"] = params.get("external_backend", {})
        self.model_profiles = sanitize_model_profiles(
            params.get("model_profiles", {}),
            **model_profile_context,
        )
        active_profile = self._active_profile()
        parent_backend = active_profile.get("parent_backend", {}) if isinstance(active_profile, dict) else {}
        child_defaults = active_profile.get("child_backend_defaults", {}) if isinstance(active_profile, dict) else {}
        self.owner_window = parent if hasattr(parent, "project") else None

        workflow_note = QLabel(
            tr(
                "2D/STL morphology settings control rendered STL views and ordinary morphology images.",
                lang,
            )
        )
        workflow_note.setWordWrap(True)
        workflow_note.setObjectName("mutedLabel")
        layout.addWidget(workflow_note)

        profile_group = QGroupBox(tr("Model Profiles", lang))
        apply_surface_role(profile_group, SURFACE_ROLE_SUBTLE, "modelSettingsProfilePanel")
        profile_form = QGridLayout(profile_group)
        profile_form.setContentsMargins(12, 12, 12, 12)
        profile_form.setHorizontalSpacing(10)
        profile_form.setVerticalSpacing(8)
        profile_note = QLabel(tr("Project profile changes are saved into the current project JSON. Save the current controls as a profile after choosing the model sources and validating any advanced extensions you want to reuse.", lang))
        profile_note.setWordWrap(True)
        profile_note.setObjectName("mutedLabel")
        profile_form.addWidget(profile_note, 0, 0, 1, 3)
        profile_form.addWidget(QLabel(tr("Current Model Profile:", lang)), 1, 0)
        self.combo_model_profile = NoWheelComboBox()
        self.combo_model_profile.setObjectName("modelSettingsProfileCombo")
        profile_form.addWidget(self.combo_model_profile, 1, 1, 1, 2)
        profile_form.addWidget(QLabel(tr("Profile ID:", lang)), 2, 0)
        self.profile_id_edit = QLineEdit()
        self.profile_id_edit.setReadOnly(True)
        profile_form.addWidget(self.profile_id_edit, 2, 1, 1, 2)
        profile_form.addWidget(QLabel(tr("Profile Display Name:", lang)), 3, 0)
        self.profile_name_edit = QLineEdit()
        profile_form.addWidget(self.profile_name_edit, 3, 1, 1, 2)
        profile_form.addWidget(QLabel(tr("Profile Description:", lang)), 4, 0)
        self.profile_description_edit = QTextEdit()
        self.profile_description_edit.setAcceptRichText(False)
        self.profile_description_edit.setMinimumHeight(82)
        profile_form.addWidget(self.profile_description_edit, 4, 1, 1, 2)
        profile_form.addWidget(QLabel(tr("Profile Summary:", lang)), 5, 0)
        self.profile_summary_box = QTextEdit()
        self.profile_summary_box.setObjectName("modelSettingsProfileSummary")
        self.profile_summary_box.setReadOnly(True)
        self.profile_summary_box.setAcceptRichText(False)
        self.profile_summary_box.setMinimumHeight(128)
        profile_form.addWidget(self.profile_summary_box, 5, 1, 1, 2)
        profile_buttons = QHBoxLayout()
        self.btn_new_profile = QPushButton(tr("Save Current Settings as New Profile", lang))
        self.btn_copy_profile = QPushButton(tr("Copy Profile", lang))
        self.btn_delete_profile = QPushButton(tr("Delete Profile", lang))
        self.btn_set_active_profile = QPushButton(tr("Set as Active Profile", lang))
        for button, role in [
            (self.btn_new_profile, BUTTON_ROLE_NEUTRAL),
            (self.btn_copy_profile, BUTTON_ROLE_NEUTRAL),
            (self.btn_delete_profile, BUTTON_ROLE_DESTRUCTIVE),
            (self.btn_set_active_profile, BUTTON_ROLE_COMMIT),
        ]:
            apply_semantic_button_style(button, role)
            profile_buttons.addWidget(button)
        profile_form.addLayout(profile_buttons, 6, 0, 1, 3)
        self._refresh_profile_combo()
        self.combo_model_profile.currentIndexChanged.connect(self._load_selected_profile_fields)
        self.profile_name_edit.textChanged.connect(self._update_current_profile_metadata)
        self.profile_description_edit.textChanged.connect(self._update_current_profile_metadata)
        self.btn_new_profile.clicked.connect(self.new_model_profile)
        self.btn_copy_profile.clicked.connect(self.copy_model_profile)
        self.btn_delete_profile.clicked.connect(self.delete_model_profile)
        self.btn_set_active_profile.clicked.connect(self.set_selected_profile_active)
        self.profile_tab_index = None

        tab_backend = QWidget()
        tab_backend.setObjectName("modelSettingsAdvancedExtensionsTab")
        form_backend = QVBoxLayout(tab_backend)
        advanced_note = QLabel(
            tr(
                "Advanced extensions collect high-impact model source switches plus custom script and manifest settings for the current model profile. Parent-part and child-part pages show the active sources as read-only summaries.",
                lang,
            )
        )
        advanced_note.setWordWrap(True)
        advanced_note.setObjectName("mutedLabel")
        form_backend.addWidget(advanced_note)
        advanced_order_note = QLabel(
            tr(
                "Advanced extension order: 1) choose or save the model profile, 2) choose parent/default child model sources, 3) fill the parent or child custom extension blocks only when those sources are selected.",
                lang,
            )
        )
        advanced_order_note.setWordWrap(True)
        advanced_order_note.setObjectName("mutedLabel")
        form_backend.addWidget(advanced_order_note)
        profile_group.setTitle(tr("1. Model Profiles", lang))
        form_backend.addWidget(profile_group)
        self.backend_combo = NoWheelComboBox()
        self.backend_combo.addItem(tr("Built-in Locator + SAM", lang), BUILTIN_BACKEND_ID)
        self.backend_combo.addItem(tr("Custom Script Extension", lang), EXTERNAL_BACKEND_ID)
        initial_backend = params.get("model_backend", BUILTIN_BACKEND_ID)
        active_parent = active_profile.get("parent_backend", {}) if isinstance(active_profile.get("parent_backend"), dict) else {}
        if active_parent.get("backend_type") == PARENT_BACKEND_EXTERNAL:
            initial_backend = EXTERNAL_BACKEND_ID
        elif active_parent.get("backend_type") == PARENT_BACKEND_BUILTIN:
            initial_backend = BUILTIN_BACKEND_ID
        backend_index = self.backend_combo.findData(initial_backend)
        self.backend_combo.setCurrentIndex(backend_index if backend_index >= 0 else 0)
        self.backend_combo.setEnabled(False)
        self.backend_combo.setToolTip(
            tr(
                "Compatibility display only. Choose Parent Model Source in Advanced Extensions to switch the active parent model source.",
                lang,
            )
        )
        self.backend_combo.setVisible(False)

        model_source_group = QGroupBox(tr("2. Model Source Switches", lang))
        model_source_group.setObjectName("modelSettingsModelSourceSwitchPanel")
        apply_surface_role(model_source_group, SURFACE_ROLE_SUBTLE, "modelSettingsModelSourceSwitchPanel")
        model_source_layout = QVBoxLayout(model_source_group)
        model_source_layout.setContentsMargins(12, 12, 12, 12)
        model_source_layout.setSpacing(8)
        model_source_note = QLabel(
            tr(
                "Choose the high-impact model sources for the current profile here. Existing child route experts stay route-specific; this default mainly affects new/default child expert training and unresolved route defaults.",
                lang,
            )
        )
        model_source_note.setWordWrap(True)
        model_source_note.setObjectName("mutedLabel")
        model_source_layout.addWidget(model_source_note)
        model_source_layout.addWidget(QLabel(tr("Parent Model Source:", lang)))
        self.parent_backend_combo = NoWheelComboBox()
        self.parent_backend_combo.addItem(tr("Built-in Locator + SAM", lang), PARENT_BACKEND_BUILTIN)
        self.parent_backend_combo.addItem(tr("Custom Parent Extension", lang), PARENT_BACKEND_EXTERNAL)
        parent_backend_index = self.parent_backend_combo.findData(parent_backend.get("backend_type", PARENT_BACKEND_BUILTIN))
        self.parent_backend_combo.setCurrentIndex(parent_backend_index if parent_backend_index >= 0 else 0)
        self.parent_backend_combo.currentIndexChanged.connect(self._sync_legacy_backend_combo_from_parent_backend)
        self.parent_backend_combo.currentIndexChanged.connect(lambda _index: self._refresh_model_source_summaries())
        model_source_layout.addWidget(self.parent_backend_combo)
        parent_source_note = QLabel(
            tr(
                "Parent source changes parent-part training and Auto annotation. Custom Parent Extension calls the configured script below instead of built-in Locator/SAM.",
                lang,
            )
        )
        parent_source_note.setWordWrap(True)
        parent_source_note.setObjectName("mutedLabel")
        model_source_layout.addWidget(parent_source_note)
        model_source_layout.addWidget(QLabel(tr("Default Child Expert:", lang)))
        self.child_backend_combo = NoWheelComboBox()
        self.child_backend_combo.addItem(tr("ViT-B Blink Expert", lang), CHILD_BACKEND_VIT_B)
        self.child_backend_combo.addItem(tr("Heatmap Blink Expert", lang), CHILD_BACKEND_HEATMAP)
        self.child_backend_combo.addItem(tr("Custom Child Extension", lang), CHILD_BACKEND_EXTERNAL)
        child_backend_index = self.child_backend_combo.findData(child_defaults.get("backend_type", CHILD_BACKEND_VIT_B))
        self.child_backend_combo.setCurrentIndex(child_backend_index if child_backend_index >= 0 else 0)
        self.child_backend_combo.currentIndexChanged.connect(lambda _index: self._refresh_model_source_summaries())
        model_source_layout.addWidget(self.child_backend_combo)
        child_source_note = QLabel(
            tr(
                "Default child expert affects new/default child expert training. During inference, each appointed parent -> child route calls the backend recorded on that route.",
                lang,
            )
        )
        child_source_note.setWordWrap(True)
        child_source_note.setObjectName("mutedLabel")
        model_source_layout.addWidget(child_source_note)
        form_backend.addWidget(model_source_group)

        parent_extension_group = QGroupBox(tr("3. Parent-part Custom Extension", lang))
        parent_extension_group.setObjectName("modelSettingsParentExtensionPanel")
        apply_surface_role(parent_extension_group, SURFACE_ROLE_SUBTLE, "modelSettingsParentExtensionPanel")
        parent_extension_layout = QVBoxLayout(parent_extension_group)
        parent_extension_layout.setContentsMargins(12, 12, 12, 12)
        parent_extension_layout.setSpacing(8)
        self.parent_extension_status_label = QLabel()
        self.parent_extension_status_label.setObjectName("modelSettingsParentExtensionStatus")
        self.parent_extension_status_label.setWordWrap(True)
        parent_extension_layout.addWidget(self.parent_extension_status_label)
        external_note = QLabel(
            tr("Use this advanced entry when you want TaxaMask to call your own parent-part training or prediction scripts. Commands run in an isolated external_runs directory and receive a contract JSON path through {contract} or {contract_json}. When Parent Model Source is set to Custom Parent Extension for the active model profile, built-in Locator/SAM training and prediction do not run for that task.", lang)
        )
        external_note.setWordWrap(True)
        external_note.setObjectName("mutedLabel")
        parent_extension_layout.addWidget(external_note)
        external_profile_note = QLabel(
            tr(
                "Parent extension settings are saved inside the current model profile when Parent Model Source is set to Custom Parent Extension.",
                lang,
            )
        )
        external_profile_note.setWordWrap(True)
        external_profile_note.setObjectName("mutedLabel")
        parent_extension_layout.addWidget(external_profile_note)

        external_config = sanitize_external_backend_config(params.get("external_backend", {}))
        parent_extension_layout.addWidget(QLabel(tr("Extension ID:", lang)))
        self.external_backend_id = QLineEdit(external_config.get("backend_id", ""))
        parent_extension_layout.addWidget(self.external_backend_id)
        parent_extension_layout.addWidget(QLabel(tr("Display Name:", lang)))
        self.external_display_name = QLineEdit(external_config.get("display_name", ""))
        parent_extension_layout.addWidget(self.external_display_name)
        parent_extension_layout.addWidget(QLabel(tr("Python Executable:", lang)))
        self.external_python = QLineEdit(external_config.get("python_executable", "python"))
        parent_extension_layout.addWidget(self.external_python)
        parent_extension_layout.addWidget(QLabel(tr("Prepare Dataset Command:", lang)))
        self.external_prepare_command = self._make_command_editor(
            external_config.get("prepare_dataset_command", ""),
            "{python} scripts/prepare_dataset.py --contract {contract_json}",
        )
        parent_extension_layout.addWidget(self.external_prepare_command)
        parent_extension_layout.addWidget(QLabel(tr("Train Command:", lang)))
        self.external_train_command = self._make_command_editor(
            external_config.get("train_command", ""),
            "{python} scripts/train_model.py --contract {contract_json}",
        )
        parent_extension_layout.addWidget(self.external_train_command)
        parent_extension_layout.addWidget(QLabel(tr("Predict Command:", lang)))
        self.external_predict_command = self._make_command_editor(
            external_config.get("predict_command", ""),
            "{python} scripts/predict_image.py --contract {contract_json}",
        )
        parent_extension_layout.addWidget(self.external_predict_command)
        parent_extension_layout.addWidget(QLabel(tr("Model Manifest Path:", lang)))
        self.external_model_manifest = QLineEdit(external_config.get("model_manifest", ""))
        self.external_model_manifest.setPlaceholderText("{run_dir}/model/taxamask_model_manifest.json")
        parent_extension_layout.addWidget(self.external_model_manifest)
        self.external_validation_label = QLabel()
        self.external_validation_label.setObjectName("mutedLabel")
        self.external_validation_label.setWordWrap(True)
        parent_extension_layout.addWidget(self.external_validation_label)
        btn_validate_external = QPushButton(tr("Validate Parent Extension", lang))
        apply_semantic_button_style(btn_validate_external, BUTTON_ROLE_NEUTRAL)
        btn_validate_external.clicked.connect(self.validate_external_backend)
        parent_extension_layout.addWidget(btn_validate_external)
        form_backend.addWidget(parent_extension_group)
        
        tab_parent = QWidget()
        tab_parent.setObjectName("modelSettingsParentTab")
        form_parent = QVBoxLayout(tab_parent)
        self.parent_backend_status_label = QLabel()
        self.parent_backend_status_label.setObjectName("modelSettingsParentSourceSummary")
        self.parent_backend_status_label.setWordWrap(True)
        form_parent.addWidget(self.parent_backend_status_label)
        parent_backend_status_note = QLabel(tr("Read-only summary. Change this source in Advanced Extensions.", lang))
        parent_backend_status_note.setWordWrap(True)
        parent_backend_status_note.setObjectName("mutedLabel")
        form_parent.addWidget(parent_backend_status_note)
        form_parent.addWidget(QLabel(tr("Epochs:", lang)))
        self.spin_epochs = QLineEdit(str(params['epochs']))
        form_parent.addWidget(self.spin_epochs)
        form_parent.addWidget(QLabel(tr("Batch Size:", lang)))
        self.spin_batch = QLineEdit(str(params['batch']))
        form_parent.addWidget(self.spin_batch)
        form_parent.addWidget(QLabel(tr("Learning Rate:", lang)))
        self.spin_lr = QLineEdit(str(params['lr']))
        form_parent.addWidget(self.spin_lr)
        form_parent.addWidget(QLabel(tr("Weight Decay (L2 Reg):", lang)))
        self.spin_wd = QLineEdit(str(params['wd']))
        form_parent.addWidget(self.spin_wd)

        device_group = QGroupBox(tr("Runtime Device:", lang))
        apply_surface_role(device_group, SURFACE_ROLE_SUBTLE, "modelSettingsRuntimeDevicePanel")
        device_layout = QVBoxLayout(device_group)
        device_layout.setContentsMargins(12, 12, 12, 12)
        device_layout.setSpacing(8)
        device_note = QLabel(
            tr(
                "Controls built-in Locator/SAM/Blink training and inference. Custom extensions use their own command environment. CPU can run small tests, but CUDA is recommended for real training.",
                lang,
            )
        )
        device_note.setWordWrap(True)
        device_note.setObjectName("mutedLabel")
        device_layout.addWidget(device_note)
        self.combo_runtime_device = NoWheelComboBox()
        self.combo_runtime_device.addItem(tr("Auto (CUDA if available)", lang), "auto")
        self.combo_runtime_device.addItem(tr("CPU only", lang), "cpu")
        self.combo_runtime_device.addItem(tr("CUDA GPU", lang), "cuda")
        runtime_device = normalize_device_preference(params.get("runtime_device", "auto"))
        runtime_index = self.combo_runtime_device.findData(runtime_device)
        self.combo_runtime_device.setCurrentIndex(runtime_index if runtime_index >= 0 else 0)
        device_layout.addWidget(self.combo_runtime_device)
        form_parent.addWidget(device_group)

        parent_ratio_group = QGroupBox(tr("Parent Box Aspect Ratios:", lang))
        apply_surface_role(parent_ratio_group, SURFACE_ROLE_SUBTLE, "modelSettingsParentBoxRatioPanel")
        ratio_layout = QGridLayout(parent_ratio_group)
        ratio_layout.setContentsMargins(12, 12, 12, 12)
        ratio_layout.setHorizontalSpacing(10)
        ratio_layout.setVerticalSpacing(8)
        ratio_note = QLabel(
            tr(
                "Used when the main labeling workbench draws parent context boxes. Enter each as width : height, for example 4 : 3. Child boxes and Blink shrink start boxes stay free-ratio.",
                lang,
            )
        )
        ratio_note.setWordWrap(True)
        ratio_note.setObjectName("mutedLabel")
        ratio_layout.addWidget(ratio_note, 0, 0, 1, 4)
        self.parent_box_ratio_inputs = {}
        ratio_map = params.get("parent_box_aspect_ratios", {}) if isinstance(params.get("parent_box_aspect_ratios", {}), dict) else {}
        default_ratio_parts = ["Head", "Mesosoma", "Gaster", "Whole body"]
        ratio_parts = []
        for part_name in list(self.initial_locator_scope) + default_ratio_parts:
            clean_part = str(part_name or "").strip()
            if clean_part and clean_part not in ratio_parts:
                ratio_parts.append(clean_part)
        ratio_layout.addWidget(QLabel(tr("Width", lang)), 1, 1)
        ratio_layout.addWidget(QLabel(tr("Height", lang)), 1, 3)
        for index, part_name in enumerate(ratio_parts, start=2):
            ratio_layout.addWidget(QLabel(part_name), index, 0)
            width_edit = QLineEdit()
            width_edit.setPlaceholderText("4")
            width_edit.setMaximumWidth(90)
            height_edit = QLineEdit()
            height_edit.setPlaceholderText("3")
            height_edit.setMaximumWidth(90)
            self.parent_box_ratio_inputs[part_name] = (width_edit, height_edit)
            self._set_parent_box_ratio_input(part_name, ratio_map.get(part_name, ""))
            ratio_layout.addWidget(width_edit, index, 1)
            ratio_layout.addWidget(QLabel(":"), index, 2)
            ratio_layout.addWidget(height_edit, index, 3)
        form_parent.addWidget(parent_ratio_group)

        locator_group = QGroupBox(tr("Main Locator Parts:", lang))
        apply_surface_role(locator_group, SURFACE_ROLE_SUBTLE, "modelSettingsLocatorScopePanel")
        locator_layout = QVBoxLayout(locator_group)
        locator_layout.setContentsMargins(12, 12, 12, 12)
        locator_layout.setSpacing(8)
        locator_note = QLabel(
            tr(
                "Choose which structures the built-in Locator should learn as large, stable targets. Small structures can stay in Structures and be refined with SAM, Blink, or a custom extension.",
                lang,
            )
        )
        locator_note.setWordWrap(True)
        locator_note.setObjectName("mutedLabel")
        locator_layout.addWidget(locator_note)

        locator_grid = QGridLayout()
        locator_grid.setContentsMargins(0, 4, 0, 0)
        locator_grid.setHorizontalSpacing(16)
        locator_grid.setVerticalSpacing(6)
        for index, part_name in enumerate(self.taxonomy):
            check = QCheckBox(part_name)
            check.setChecked(part_name in self.initial_locator_scope)
            check.setProperty("part_name", part_name)
            self.locator_scope_checks.append(check)
            locator_grid.addWidget(check, index // 2, index % 2)
        locator_layout.addLayout(locator_grid)
        self.locator_scope_validation_label = QLabel("")
        self.locator_scope_validation_label.setObjectName("mutedLabel")
        locator_layout.addWidget(self.locator_scope_validation_label)
        form_parent.addWidget(locator_group)
        form_parent.addStretch()
        self.parent_tab_index = self.tabs.addTab(self._make_scroll_tab(tab_parent), tr("Parent-part annotation", lang))

        tab_child = QWidget()
        tab_child.setObjectName("modelSettingsChildTab")
        form_child = QVBoxLayout(tab_child)
        self.child_backend_status_label = QLabel()
        self.child_backend_status_label.setObjectName("modelSettingsChildSourceSummary")
        self.child_backend_status_label.setWordWrap(True)
        form_child.addWidget(self.child_backend_status_label)
        child_backend_status_note = QLabel(tr("Read-only summary. Change this source in Advanced Extensions.", lang))
        child_backend_status_note.setWordWrap(True)
        child_backend_status_note.setObjectName("mutedLabel")
        form_child.addWidget(child_backend_status_note)

        blink_group = QGroupBox(tr("Blink Expert Training Defaults:", lang))
        apply_surface_role(blink_group, SURFACE_ROLE_SUBTLE, "modelSettingsBlinkTrainingPanel")
        blink_layout = QVBoxLayout(blink_group)
        blink_layout.setContentsMargins(12, 12, 12, 12)
        blink_layout.setSpacing(8)
        blink_note = QLabel(
            tr(
                "These defaults are shown in Child Expert Session when the app starts or settings are saved. You can still adjust them for a single expert before training.",
                lang,
            )
        )
        blink_note.setWordWrap(True)
        blink_note.setObjectName("mutedLabel")
        blink_layout.addWidget(blink_note)
        blink_layout.addWidget(QLabel(tr("Blink Training Strategy:", lang)))
        self.combo_blink_training_strategy = NoWheelComboBox()
        for strategy in (
            BLINK_STRATEGY_TRIVIEW_RANDOM,
            BLINK_STRATEGY_FULL_INSIDE_RANDOM,
            BLINK_STRATEGY_TWO_STAGE_FULL_THEN_INSIDE,
        ):
            self.combo_blink_training_strategy.addItem(blink_training_strategy_label(strategy, lang), strategy)
        selected_strategy = sanitize_blink_training_strategy(
            child_defaults.get("training_strategy"),
            params.get("blink_training_strategy", DEFAULT_BLINK_TRAINING_STRATEGY),
        )
        strategy_index = self.combo_blink_training_strategy.findData(selected_strategy)
        self.combo_blink_training_strategy.setCurrentIndex(strategy_index if strategy_index >= 0 else 0)
        self.combo_blink_training_strategy.currentIndexChanged.connect(self._update_blink_training_strategy_note)
        blink_layout.addWidget(self.combo_blink_training_strategy)
        self.blink_training_strategy_note = QLabel("")
        self.blink_training_strategy_note.setWordWrap(True)
        self.blink_training_strategy_note.setObjectName("mutedLabel")
        blink_layout.addWidget(self.blink_training_strategy_note)
        self._update_blink_training_strategy_note()
        blink_layout.addWidget(QLabel(tr("Default Blink Epochs:", lang)))
        self.spin_blink_epochs = QLineEdit(str(params.get("blink_epochs", 5)))
        blink_layout.addWidget(self.spin_blink_epochs)
        blink_layout.addWidget(QLabel(tr("Default Blink Batch Size:", lang)))
        self.spin_blink_batch = QLineEdit(str(params.get("blink_batch", 2)))
        blink_layout.addWidget(self.spin_blink_batch)
        blink_layout.addWidget(QLabel(tr("Default Blink Learning Rate:", lang)))
        self.spin_blink_lr = QLineEdit(str(params.get("blink_lr", 1e-3)))
        blink_layout.addWidget(self.spin_blink_lr)
        blink_layout.addWidget(QLabel(tr("Default Blink Weight Decay:", lang)))
        self.spin_blink_wd = QLineEdit(str(params.get("blink_weight_decay", 1e-4)))
        blink_layout.addWidget(self.spin_blink_wd)
        blink_layout.addWidget(QLabel(tr("Default Blink Input Size:", lang)))
        self.combo_blink_input_size = NoWheelComboBox()
        for side in [224, 384, 512]:
            self.combo_blink_input_size.addItem(f"{side} x {side}", side)
        try:
            input_side = int(params.get("blink_input_size", 224))
        except Exception:
            input_side = 224
        input_index = self.combo_blink_input_size.findData(input_side)
        self.combo_blink_input_size.setCurrentIndex(input_index if input_index >= 0 else 0)
        blink_layout.addWidget(self.combo_blink_input_size)
        blink_layout.addWidget(QLabel(tr("Auto-shrink Steps:", lang)))
        self.spin_blink_auto_shrink_steps = NoWheelSpinBox()
        self.spin_blink_auto_shrink_steps.setRange(1, 200)
        try:
            shrink_steps = int(child_defaults.get("auto_shrink_steps", params.get("blink_auto_shrink_steps", DEFAULT_CHILD_AUTO_SHRINK_STEPS)))
        except Exception:
            shrink_steps = DEFAULT_CHILD_AUTO_SHRINK_STEPS
        self.spin_blink_auto_shrink_steps.setValue(max(1, min(200, shrink_steps)))
        self.spin_blink_auto_shrink_steps.setToolTip(
            tr(
                "Number of interpolation steps from the loose shrink start box to the final target box. 20 steps saves 21 trajectory frames including the starting frame.",
                lang,
            )
        )
        blink_layout.addWidget(self.spin_blink_auto_shrink_steps)
        form_child.addWidget(blink_group)

        blink_dataset_group = QGroupBox(tr("Blink Shrink Training Datasets", lang))
        blink_dataset_group.setObjectName("modelSettingsBlinkDatasetPanel")
        apply_surface_role(blink_dataset_group, SURFACE_ROLE_SUBTLE, "modelSettingsBlinkDatasetPanel")
        blink_dataset_layout = QVBoxLayout(blink_dataset_group)
        blink_dataset_layout.setContentsMargins(12, 12, 12, 12)
        blink_dataset_layout.setSpacing(8)
        self.blink_dataset_note = QLabel(
            tr(
                "Shows saved auto-shrink trajectories used to train child-part experts. Each row is grouped by parent -> child route.",
                lang,
            )
        )
        self.blink_dataset_note.setWordWrap(True)
        self.blink_dataset_note.setObjectName("mutedLabel")
        blink_dataset_layout.addWidget(self.blink_dataset_note)
        self.blink_dataset_tree = QTreeWidget()
        self.blink_dataset_tree.setObjectName("modelSettingsBlinkDatasetTree")
        self.blink_dataset_tree.setRootIsDecorated(False)
        self.blink_dataset_tree.setAlternatingRowColors(True)
        self.blink_dataset_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.blink_dataset_tree.setHeaderLabels(
            [
                tr("Route", lang),
                tr("Images", lang),
                tr("Frames", lang),
                tr("Sources", lang),
            ]
        )
        self.blink_dataset_tree.setMinimumHeight(160)
        self.blink_dataset_tree.itemSelectionChanged.connect(self._refresh_blink_dataset_actions)
        header = self.blink_dataset_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 4):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        blink_dataset_layout.addWidget(self.blink_dataset_tree)
        dataset_buttons = QHBoxLayout()
        self.btn_blink_dataset_details = QPushButton(tr("View Details", lang))
        self.btn_blink_dataset_details.setObjectName("modelSettingsBlinkDatasetDetailsButton")
        self.btn_blink_dataset_details.clicked.connect(self._show_blink_dataset_details)
        apply_semantic_button_style(self.btn_blink_dataset_details, BUTTON_ROLE_NEUTRAL)
        self.btn_blink_dataset_delete = QPushButton(tr("Delete Dataset", lang))
        self.btn_blink_dataset_delete.setObjectName("modelSettingsBlinkDatasetDeleteButton")
        self.btn_blink_dataset_delete.clicked.connect(self._delete_selected_blink_dataset)
        apply_semantic_button_style(self.btn_blink_dataset_delete, BUTTON_ROLE_DESTRUCTIVE)
        dataset_buttons.addWidget(self.btn_blink_dataset_details)
        dataset_buttons.addWidget(self.btn_blink_dataset_delete)
        dataset_buttons.addStretch(1)
        blink_dataset_layout.addLayout(dataset_buttons)
        form_child.addWidget(blink_dataset_group)

        heatmap_group = QGroupBox(tr("Heatmap Blink Parameters:", lang))
        apply_surface_role(heatmap_group, SURFACE_ROLE_SUBTLE, "modelSettingsHeatmapBlinkPanel")
        heatmap_layout = QVBoxLayout(heatmap_group)
        heatmap_params = child_defaults.get("heatmap_params", {}) if isinstance(child_defaults.get("heatmap_params"), dict) else {}
        self.spin_heatmap_input_size = QLineEdit(str(heatmap_params.get("input_size", DEFAULT_HEATMAP_BLINK_PARAMS["input_size"])))
        self.spin_heatmap_sigma = QLineEdit(str(heatmap_params.get("heatmap_sigma", DEFAULT_HEATMAP_BLINK_PARAMS["heatmap_sigma"])))
        self.spin_heatmap_wh_loss = QLineEdit(str(heatmap_params.get("wh_loss_weight", DEFAULT_HEATMAP_BLINK_PARAMS["wh_loss_weight"])))
        self.spin_heatmap_center_loss = QLineEdit(str(heatmap_params.get("center_loss_weight", DEFAULT_HEATMAP_BLINK_PARAMS["center_loss_weight"])))
        for label_text, editor in [
            (tr("Heatmap Input Size:", lang), self.spin_heatmap_input_size),
            (tr("Heatmap Sigma:", lang), self.spin_heatmap_sigma),
            (tr("WH Loss Weight:", lang), self.spin_heatmap_wh_loss),
            (tr("Center Loss Weight:", lang), self.spin_heatmap_center_loss),
        ]:
            heatmap_layout.addWidget(QLabel(label_text))
            heatmap_layout.addWidget(editor)
        form_child.addWidget(heatmap_group)

        external_blink_group = QGroupBox(tr("4. Child-part Custom Extension", lang))
        apply_surface_role(external_blink_group, SURFACE_ROLE_SUBTLE, "modelSettingsExternalBlinkPanel")
        external_blink_layout = QVBoxLayout(external_blink_group)
        external_blink_layout.setContentsMargins(12, 12, 12, 12)
        external_blink_layout.setSpacing(8)
        self.child_extension_status_label = QLabel()
        self.child_extension_status_label.setObjectName("modelSettingsChildExtensionStatus")
        self.child_extension_status_label.setWordWrap(True)
        external_blink_layout.addWidget(self.child_extension_status_label)
        external_blink_note = QLabel(
            tr(
                "Child extension settings are saved inside the current model profile when Default Child Backend is set to Custom Child Extension.",
                lang,
            )
        )
        external_blink_note.setWordWrap(True)
        external_blink_note.setObjectName("mutedLabel")
        external_blink_layout.addWidget(external_blink_note)
        external_blink = dict(DEFAULT_EXTERNAL_BLINK_BACKEND)
        if isinstance(child_defaults.get("external_blink_backend"), dict):
            external_blink.update(child_defaults.get("external_blink_backend"))
        self.external_blink_backend_id = QLineEdit(external_blink.get("backend_id", ""))
        self.external_blink_display_name = QLineEdit(external_blink.get("display_name", ""))
        self.external_blink_python = QLineEdit(external_blink.get("python_executable", "python"))
        self.external_blink_predict_command = self._make_command_editor(
            external_blink.get("predict_command", ""),
            "{python} scripts/predict_child.py --contract {contract_json}",
        )
        self.external_blink_train_command = self._make_command_editor(
            external_blink.get("train_command", ""),
            "{python} scripts/train_child.py --contract {contract_json}",
        )
        self.external_blink_model_manifest = QLineEdit(external_blink.get("model_manifest", ""))
        for label_text, widget in [
            (tr("Child Extension ID:", lang), self.external_blink_backend_id),
            (tr("Child Extension Display Name:", lang), self.external_blink_display_name),
            (tr("Child Extension Python Executable:", lang), self.external_blink_python),
            (tr("Child Extension Predict Command:", lang), self.external_blink_predict_command),
            (tr("Child Extension Train Command:", lang), self.external_blink_train_command),
            (tr("Child Extension Model Manifest:", lang), self.external_blink_model_manifest),
        ]:
            external_blink_layout.addWidget(QLabel(label_text))
            external_blink_layout.addWidget(widget)
        self.external_blink_validation_label = QLabel()
        self.external_blink_validation_label.setObjectName("mutedLabel")
        self.external_blink_validation_label.setWordWrap(True)
        external_blink_layout.addWidget(self.external_blink_validation_label)
        btn_validate_external_blink = QPushButton(tr("Validate Child Extension", lang))
        apply_semantic_button_style(btn_validate_external_blink, BUTTON_ROLE_NEUTRAL)
        btn_validate_external_blink.clicked.connect(self.validate_external_blink_backend)
        external_blink_layout.addWidget(btn_validate_external_blink)
        form_backend.addWidget(external_blink_group)
        form_backend.addStretch()
        form_child.addStretch()
        self.child_tab_index = self.tabs.addTab(self._make_scroll_tab(tab_child), tr("Child-part annotation", lang))

        tab_inf = QWidget()
        form_inf = QVBoxLayout(tab_inf)
        form_inf.addWidget(QLabel(tr("Confidence Threshold:", lang)))
        self.spin_conf = QLineEdit(str(params['conf']))
        form_inf.addWidget(self.spin_conf)
        form_inf.addWidget(QLabel(tr("Adaptive Thresh Ratio:", lang)))
        self.spin_adapt = QLineEdit(str(params['adapt']))
        form_inf.addWidget(self.spin_adapt)
        form_inf.addWidget(QLabel(tr("Noise Floor:", lang)))
        self.spin_noise = QLineEdit(str(params['noise_floor']))
        form_inf.addWidget(self.spin_noise)
        form_inf.addWidget(QLabel(tr("Polygon Simplification (px):", lang)))
        self.spin_poly = QLineEdit(str(params.get('poly_epsilon', 2.0)))
        form_inf.addWidget(self.spin_poly)
        form_inf.addWidget(QLabel(tr("Box Padding Ratio:", lang)))
        self.spin_pad = QLineEdit(str(params['pad']))
        form_inf.addWidget(self.spin_pad)

        vlm_settings = params.get("vlm_preannotation", {}) if isinstance(params.get("vlm_preannotation", {}), dict) else {}
        vlm_group = QGroupBox(tr("AI Multimodal Pre-Annotation:", lang))
        apply_surface_role(vlm_group, SURFACE_ROLE_SUBTLE, "modelSettingsVlmPreannotationPanel")
        vlm_layout = QVBoxLayout(vlm_group)
        vlm_layout.setContentsMargins(12, 12, 12, 12)
        vlm_layout.setSpacing(8)
        vlm_note = QLabel(
            tr(
                "Choose which existing project structures will be sent to the multimodal model. This list is separate from main locator parts.",
                lang,
            )
        )
        vlm_note.setWordWrap(True)
        vlm_note.setObjectName("mutedLabel")
        vlm_layout.addWidget(vlm_note)
        vlm_layout.addWidget(QLabel(tr("VLM Target Parts:", lang)))
        vlm_grid = QGridLayout()
        vlm_grid.setContentsMargins(0, 4, 0, 0)
        vlm_grid.setHorizontalSpacing(16)
        vlm_grid.setVerticalSpacing(6)
        selected_vlm_parts = {
            str(part).strip()
            for part in vlm_settings.get("target_parts", [])
            if str(part).strip()
        }
        for index, part_name in enumerate(self.taxonomy):
            check = QCheckBox(part_name)
            check.setChecked(part_name in selected_vlm_parts)
            check.setProperty("part_name", part_name)
            self.vlm_target_part_checks.append(check)
            vlm_grid.addWidget(check, index // 2, index % 2)
        vlm_layout.addLayout(vlm_grid)

        self.btn_vlm_detail_toggle = QToolButton()
        self.btn_vlm_detail_toggle.setObjectName("modelSettingsVlmDetailToggle")
        self.btn_vlm_detail_toggle.setText(tr("VLM Detailed Settings", lang))
        self.btn_vlm_detail_toggle.setCheckable(True)
        self.btn_vlm_detail_toggle.setChecked(False)
        self.btn_vlm_detail_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.btn_vlm_detail_toggle.setArrowType(Qt.RightArrow)
        vlm_layout.addWidget(self.btn_vlm_detail_toggle)

        self.vlm_details_widget = QWidget()
        self.vlm_details_widget.setObjectName("modelSettingsVlmDetailsPanel")
        vlm_details_layout = QVBoxLayout(self.vlm_details_widget)
        vlm_details_layout.setContentsMargins(0, 4, 0, 0)
        vlm_details_layout.setSpacing(8)
        self.vlm_details_widget.setVisible(False)
        self.btn_vlm_detail_toggle.toggled.connect(self._toggle_vlm_details)

        vlm_details_layout.addWidget(QLabel(tr("VLM Batch Scope:", lang)))
        self.combo_vlm_processing_scope = NoWheelComboBox()
        self.combo_vlm_processing_scope.setObjectName("modelSettingsVlmBatchScopeCombo")
        self.combo_vlm_processing_scope.addItem(tr("All imported images", lang), "all_images")
        self.combo_vlm_processing_scope.addItem(tr("Images in selected list group", lang), "image_group")
        scope_value = str(vlm_settings.get("processing_scope", "image_group") or "image_group")
        if scope_value == "current_image":
            scope_value = "image_group"
        scope_index = self.combo_vlm_processing_scope.findData(scope_value)
        self.combo_vlm_processing_scope.setCurrentIndex(scope_index if scope_index >= 0 else 0)
        vlm_details_layout.addWidget(self.combo_vlm_processing_scope)
        vlm_details_layout.addWidget(QLabel(tr("VLM Image Group:", lang)))
        self.combo_vlm_image_group = NoWheelComboBox()
        self.combo_vlm_image_group.setObjectName("modelSettingsVlmImageGroupCombo")
        self._populate_vlm_image_group_combo(str(vlm_settings.get("image_group", "split") or "split"))
        vlm_details_layout.addWidget(self.combo_vlm_image_group)
        vlm_details_layout.addWidget(QLabel(tr("VLM API Concurrency:", lang)))
        self.spin_vlm_concurrency = NoWheelSpinBox()
        self.spin_vlm_concurrency.setObjectName("modelSettingsVlmConcurrencySpin")
        self.spin_vlm_concurrency.setRange(1, 8)
        self.spin_vlm_concurrency.setValue(max(1, min(8, int(vlm_settings.get("concurrency", 1) or 1))))
        self.spin_vlm_concurrency.setToolTip(
            tr(
                "Default is 1 to protect rate-limited API keys. Increase only if your provider explicitly allows parallel requests; high concurrency can trigger throttling, extra charges, or account blocking.",
                lang,
            )
        )
        vlm_details_layout.addWidget(self.spin_vlm_concurrency)
        vlm_concurrency_note = QLabel(
            tr(
                "Default is 1 to protect rate-limited API keys. Increase only if your provider explicitly allows parallel requests; high concurrency can trigger throttling, extra charges, or account blocking.",
                lang,
            )
        )
        vlm_concurrency_note.setWordWrap(True)
        vlm_concurrency_note.setObjectName("mutedLabel")
        vlm_details_layout.addWidget(vlm_concurrency_note)
        vlm_details_layout.addWidget(QLabel(tr("VLM Prompt Profile:", lang)))
        vlm_profile_note = QLabel(
            tr(
                "Prompt profile only changes the instructions sent to the multimodal model. The grid input, JSON schema, coordinate mapping, and SAM draft generation stay locked.",
                lang,
            )
        )
        vlm_profile_note.setWordWrap(True)
        vlm_profile_note.setObjectName("mutedLabel")
        vlm_details_layout.addWidget(vlm_profile_note)
        self.combo_vlm_prompt_profile = NoWheelComboBox()
        self.combo_vlm_prompt_profile.setObjectName("modelSettingsVlmPromptProfileCombo")
        self.combo_vlm_prompt_profile.addItem(tr("Built-in Ant Taxonomy Default", lang), DEFAULT_VLM_PROMPT_PROFILE_ID)
        self.combo_vlm_prompt_profile.addItem(tr("Project Custom Prompt", lang), "project_custom")
        self.combo_vlm_prompt_profile.currentIndexChanged.connect(lambda _index: self._refresh_vlm_prompt_profile_editors())
        vlm_details_layout.addWidget(self.combo_vlm_prompt_profile)
        vlm_prompt_help = QLabel(
            tr(
                "Use the built-in ant prompt profile as a stable baseline. Choose Project Custom Prompt when adapting VLM pre-annotation to another taxon or a special image style.",
                lang,
            )
        )
        vlm_prompt_help.setWordWrap(True)
        vlm_prompt_help.setObjectName("mutedLabel")
        vlm_details_layout.addWidget(vlm_prompt_help)
        vlm_details_layout.addWidget(QLabel(tr("Profile Name:", lang)))
        self.vlm_prompt_profile_name = QLineEdit()
        self.vlm_prompt_profile_name.setObjectName("modelSettingsVlmPromptProfileName")
        vlm_details_layout.addWidget(self.vlm_prompt_profile_name)
        self.vlm_prompt_taxon_context = self._make_prompt_profile_editor()
        self.vlm_prompt_body_rules = self._make_prompt_profile_editor()
        self.vlm_prompt_anchor_rules = self._make_prompt_profile_editor()
        self.vlm_prompt_extra_instructions = self._make_prompt_profile_editor()
        for label_text, editor in [
            (tr("Research Taxon / Image Context:", lang), self.vlm_prompt_taxon_context),
            (tr("Main Body / Attachment Rules:", lang), self.vlm_prompt_body_rules),
            (tr("Part Anchor Rules:", lang), self.vlm_prompt_anchor_rules),
            (tr("Extra VLM Instructions:", lang), self.vlm_prompt_extra_instructions),
        ]:
            vlm_details_layout.addWidget(QLabel(label_text))
            vlm_details_layout.addWidget(editor)
        vlm_layout.addWidget(self.vlm_details_widget)
        self._set_vlm_prompt_profile_controls(vlm_settings)
        form_inf.addWidget(vlm_group)

        self.lbl_cascade_note = QLabel(
            ui_text(
                "Project routes below control which parent -> child expert links are available.",
                lang,
            )
        )
        self.lbl_cascade_note.setWordWrap(True)
        self.lbl_cascade_note.setObjectName("mutedLabel")
        form_inf.addWidget(self.lbl_cascade_note)

        if self.route_panel is not None:
            route_group = QGroupBox(ui_text("Project Route Management", lang))
            apply_surface_role(route_group, SURFACE_ROLE_SUBTLE, "modelSettingsRoutePanel")
            route_layout = QVBoxLayout(route_group)
            route_layout.setContentsMargins(12, 12, 12, 12)
            route_layout.setSpacing(10)
            route_layout.addWidget(self.route_panel)
            form_inf.addWidget(route_group, 1)

        form_inf.addStretch()
        self.inference_tab_index = self.tabs.addTab(self._make_scroll_tab(tab_inf), tr("Inference", lang))
        self.advanced_extensions_tab_index = self.tabs.addTab(self._make_scroll_tab(tab_backend), tr("Advanced Extensions", lang))
        self.external_backend_tab_index = self.advanced_extensions_tab_index
        
        layout.addWidget(self.tabs, 1)
        btn_layout = QHBoxLayout()
        btn_ask_agent = QPushButton(tr("Ask Agent", lang))
        btn_ask_agent.setObjectName("modelSettingsAskAgentButton")
        btn_ask_agent.setToolTip(tr("Ask Agent about these settings. Current values are summarized without sending full command text.", lang))
        apply_semantic_button_style(btn_ask_agent, BUTTON_ROLE_NEUTRAL)
        btn_ask_agent.clicked.connect(self.request_agent_help)
        btn_save = QPushButton(tr("Save", lang))
        apply_semantic_button_style(btn_save, BUTTON_ROLE_COMMIT)
        btn_save.clicked.connect(self.accept_with_validation)
        btn_cancel = QPushButton(tr("Cancel", lang))
        apply_semantic_button_style(btn_cancel, BUTTON_ROLE_STOP)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_ask_agent)
        btn_layout.addStretch(1)
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        self._refresh_blink_dataset_table()
        self._load_selected_profile_fields()

    def _make_scroll_tab(self, content_widget):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        scroll.setWidget(content_widget)
        return scroll

    def _make_command_editor(self, text, placeholder):
        editor = QTextEdit()
        editor.setAcceptRichText(False)
        editor.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        editor.setMinimumHeight(72)
        editor.setPlainText(str(text or ""))
        editor.setPlaceholderText(placeholder)
        return editor

    def _make_prompt_profile_editor(self):
        editor = QTextEdit()
        editor.setAcceptRichText(False)
        editor.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        editor.setMinimumHeight(72)
        return editor

    def _toggle_vlm_details(self, checked):
        details = getattr(self, "vlm_details_widget", None)
        if details is not None:
            details.setVisible(bool(checked))
        toggle = getattr(self, "btn_vlm_detail_toggle", None)
        if toggle is not None:
            toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)

    def _update_blink_training_strategy_note(self):
        combo = getattr(self, "combo_blink_training_strategy", None)
        label = getattr(self, "blink_training_strategy_note", None)
        if combo is None or label is None:
            return
        strategy = sanitize_blink_training_strategy(combo.currentData())
        label.setText(blink_training_strategy_note(strategy, self.lang))

    def _command_text(self, editor):
        return editor.toPlainText().strip()

    def _set_prompt_editor_read_only(self, read_only):
        for widget in [
            getattr(self, "vlm_prompt_profile_name", None),
            getattr(self, "vlm_prompt_taxon_context", None),
            getattr(self, "vlm_prompt_body_rules", None),
            getattr(self, "vlm_prompt_anchor_rules", None),
            getattr(self, "vlm_prompt_extra_instructions", None),
        ]:
            if widget is not None:
                widget.setReadOnly(bool(read_only))

    def _set_vlm_prompt_profile_controls(self, settings):
        if not hasattr(self, "combo_vlm_prompt_profile"):
            return
        settings = settings if isinstance(settings, dict) else {}
        profile = sanitize_vlm_prompt_profile(settings.get("prompt_profile", {}))
        profile_id = str(settings.get("prompt_profile_id") or profile.get("profile_id") or DEFAULT_VLM_PROMPT_PROFILE_ID)
        if profile_id == DEFAULT_VLM_PROMPT_PROFILE_ID:
            profile = default_vlm_prompt_profile()
        else:
            profile_id = "project_custom"
        self._last_custom_vlm_prompt_profile = sanitize_vlm_prompt_profile(profile if profile_id != DEFAULT_VLM_PROMPT_PROFILE_ID else {"profile_id": "project_custom"})
        self.combo_vlm_prompt_profile.blockSignals(True)
        index = self.combo_vlm_prompt_profile.findData(profile_id)
        self.combo_vlm_prompt_profile.setCurrentIndex(index if index >= 0 else 0)
        self.combo_vlm_prompt_profile.blockSignals(False)
        self.vlm_prompt_profile_name.setText(str(profile.get("display_name", "")))
        self.vlm_prompt_taxon_context.setPlainText(str(profile.get("taxon_context", "")))
        self.vlm_prompt_body_rules.setPlainText(str(profile.get("body_focus_rules", "")))
        self.vlm_prompt_anchor_rules.setPlainText(str(profile.get("part_anchor_rules", "")))
        self.vlm_prompt_extra_instructions.setPlainText(str(profile.get("extra_instructions", "")))
        self._refresh_vlm_prompt_profile_editors()

    def _refresh_vlm_prompt_profile_editors(self):
        if not hasattr(self, "combo_vlm_prompt_profile"):
            return
        is_builtin = self.combo_vlm_prompt_profile.currentData() == DEFAULT_VLM_PROMPT_PROFILE_ID
        if is_builtin:
            self._last_custom_vlm_prompt_profile = self._current_vlm_prompt_profile_values()["prompt_profile"]
            profile = default_vlm_prompt_profile()
            self.vlm_prompt_profile_name.setText(str(profile.get("display_name", "")))
            self.vlm_prompt_taxon_context.setPlainText(str(profile.get("taxon_context", "")))
            self.vlm_prompt_body_rules.setPlainText(str(profile.get("body_focus_rules", "")))
            self.vlm_prompt_anchor_rules.setPlainText(str(profile.get("part_anchor_rules", "")))
            self.vlm_prompt_extra_instructions.setPlainText(str(profile.get("extra_instructions", "")))
        else:
            profile = sanitize_vlm_prompt_profile(getattr(self, "_last_custom_vlm_prompt_profile", {}) or {"profile_id": "project_custom"})
            self.vlm_prompt_profile_name.setText(str(profile.get("display_name", "")))
            self.vlm_prompt_taxon_context.setPlainText(str(profile.get("taxon_context", "")))
            self.vlm_prompt_body_rules.setPlainText(str(profile.get("body_focus_rules", "")))
            self.vlm_prompt_anchor_rules.setPlainText(str(profile.get("part_anchor_rules", "")))
            self.vlm_prompt_extra_instructions.setPlainText(str(profile.get("extra_instructions", "")))
        self._set_prompt_editor_read_only(is_builtin)

    def _current_vlm_prompt_profile_values(self):
        if not hasattr(self, "combo_vlm_prompt_profile"):
            profile = default_vlm_prompt_profile()
            return {
                "prompt_profile_id": profile["profile_id"],
                "prompt_profile": profile,
            }
        if self.combo_vlm_prompt_profile.currentData() == DEFAULT_VLM_PROMPT_PROFILE_ID:
            profile = default_vlm_prompt_profile()
            return {
                "prompt_profile_id": DEFAULT_VLM_PROMPT_PROFILE_ID,
                "prompt_profile": profile,
            }
        raw_profile = {
            "profile_id": "project_custom",
            "display_name": self.vlm_prompt_profile_name.text().strip() or tr("Project Custom Prompt", self.lang),
            "taxon_context": self.vlm_prompt_taxon_context.toPlainText().strip(),
            "body_focus_rules": self.vlm_prompt_body_rules.toPlainText().strip(),
            "part_anchor_rules": self.vlm_prompt_anchor_rules.toPlainText().strip(),
            "extra_instructions": self.vlm_prompt_extra_instructions.toPlainText().strip(),
        }
        profile = sanitize_vlm_prompt_profile(raw_profile)
        return {
            "prompt_profile_id": "project_custom",
            "prompt_profile": profile,
        }

    def _blink_dataset_owner_project(self):
        owner = getattr(self, "owner_window", None)
        project = getattr(owner, "project", None) if owner is not None else None
        if project is None:
            project = getattr(owner, "project_manager", None) if owner is not None else None
        return owner, project

    def _refresh_blink_dataset_table(self):
        if not hasattr(self, "blink_dataset_tree"):
            return
        self.blink_dataset_tree.clear()
        self.blink_dataset_rows = []
        _owner, project = self._blink_dataset_owner_project()
        summarize = getattr(project, "summarize_blink_trajectory_datasets", None)
        if callable(summarize):
            try:
                self.blink_dataset_rows = [
                    dict(row)
                    for row in summarize()
                    if isinstance(row, dict)
                ]
            except Exception:
                self.blink_dataset_rows = []
        if not self.blink_dataset_rows:
            item = QTreeWidgetItem(
                [
                    tr("No Blink shrink trajectory datasets have been generated yet.", self.lang),
                    "",
                    "",
                    "",
                ]
            )
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.blink_dataset_tree.addTopLevelItem(item)
        else:
            for row in self.blink_dataset_rows:
                parent_part = str(row.get("parent_part") or tr("Unknown", self.lang))
                child_part = str(row.get("child_part") or tr("Unknown", self.lang))
                sources = row.get("sources", [])
                if not isinstance(sources, list):
                    sources = []
                item = QTreeWidgetItem(
                    [
                        f"{parent_part} -> {child_part}",
                        str(row.get("image_count", 0)),
                        str(row.get("frame_count", 0)),
                        ", ".join(str(source) for source in sources if str(source).strip()) or tr("Unknown", self.lang),
                    ]
                )
                item.setData(0, Qt.ItemDataRole.UserRole, dict(row))
                self.blink_dataset_tree.addTopLevelItem(item)
        self.blink_dataset_tree.resizeColumnToContents(1)
        self.blink_dataset_tree.resizeColumnToContents(2)
        self.blink_dataset_tree.resizeColumnToContents(3)
        self._refresh_blink_dataset_actions()

    def _selected_blink_dataset_summary(self):
        if not hasattr(self, "blink_dataset_tree"):
            return None
        item = self.blink_dataset_tree.currentItem()
        if item is None:
            return None
        summary = item.data(0, Qt.ItemDataRole.UserRole)
        return dict(summary) if isinstance(summary, dict) else None

    def _refresh_blink_dataset_actions(self):
        summary = self._selected_blink_dataset_summary()
        enabled = bool(summary)
        if hasattr(self, "btn_blink_dataset_details"):
            self.btn_blink_dataset_details.setEnabled(enabled)
        if hasattr(self, "btn_blink_dataset_delete"):
            self.btn_blink_dataset_delete.setEnabled(enabled)

    def _format_blink_dataset_details(self, summary):
        parent_part = str(summary.get("parent_part") or tr("Unknown", self.lang))
        child_part = str(summary.get("child_part") or tr("Unknown", self.lang))
        sources = summary.get("sources", [])
        if not isinstance(sources, list):
            sources = []
        lines = [
            tr("Route", self.lang) + f": {parent_part} -> {child_part}",
            tr("Images", self.lang) + f": {summary.get('image_count', 0)}",
            tr("Frames", self.lang) + f": {summary.get('frame_count', 0)}",
            tr("Sources", self.lang) + ": " + (", ".join(str(source) for source in sources if str(source).strip()) or tr("Unknown", self.lang)),
            "",
        ]
        images = summary.get("images", [])
        if isinstance(images, list):
            for index, image_info in enumerate(images, start=1):
                if not isinstance(image_info, dict):
                    continue
                image_path = str(image_info.get("image_path") or "")
                source = str(image_info.get("source") or "unknown")
                frame_count = image_info.get("frame_count", 0)
                parent_box = image_info.get("parent_box")
                lines.append(f"{index}. {image_path}")
                lines.append(f"   {tr('Frames', self.lang)}: {frame_count}; {tr('Source', self.lang)}: {source}")
                if parent_box:
                    lines.append(f"   {tr('Parent box: {0}', self.lang).format(parent_box)}")
        return "\n".join(lines).strip()

    def _show_blink_dataset_details(self):
        summary = self._selected_blink_dataset_summary()
        if not summary:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("Blink Shrink Dataset Details", self.lang))
        dialog.resize(720, 520)
        layout = QVBoxLayout(dialog)
        details = QTextEdit()
        details.setReadOnly(True)
        details.setAcceptRichText(False)
        details.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        details.setPlainText(self._format_blink_dataset_details(summary))
        layout.addWidget(details)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        apply_theme_dialog_button_box_style(
            buttons,
            ok_role=BUTTON_ROLE_COMMIT,
            cancel_role=BUTTON_ROLE_STOP,
            theme=getattr(getattr(self, "owner_window", None), "current_theme", "dark"),
        )
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.exec()

    def _delete_selected_blink_dataset(self):
        summary = self._selected_blink_dataset_summary()
        if not summary:
            return
        parent_part = str(summary.get("parent_part") or "").strip()
        child_part = str(summary.get("child_part") or "").strip()
        route_label = f"{parent_part} -> {child_part}"
        image_count = int(summary.get("image_count") or 0)
        reply = themed_yes_no_question(
            self,
            tr("Delete Blink Shrink Dataset", self.lang),
            tr(
                "Delete Blink shrink dataset for {0}?\n\nThis removes {1} image trajectory record(s) from the current project. It does not delete labels or images.",
                self.lang,
            ).format(route_label, image_count),
            confirm_role=BUTTON_ROLE_DESTRUCTIVE,
        )
        if reply != QMessageBox.Yes:
            return
        owner, project = self._blink_dataset_owner_project()
        delete_dataset = getattr(project, "delete_blink_trajectory_dataset", None)
        removed = 0
        if callable(delete_dataset):
            removed = int(delete_dataset(parent_part, child_part) or 0)
        self._refresh_blink_dataset_table()
        refresh_state = getattr(owner, "_refresh_blink_refine_state", None)
        if callable(refresh_state):
            refresh_state()
        refresh_files = getattr(owner, "refresh_file_list", None)
        if callable(refresh_files):
            refresh_files()
        log = getattr(owner, "log", None)
        if callable(log):
            log(
                tr("Deleted {0} Blink shrink trajectory record(s) for {1}.", self.lang).format(
                    removed,
                    route_label,
                )
            )

    def _active_profile_id(self):
        selected = ""
        if hasattr(self, "combo_model_profile"):
            selected = str(self.combo_model_profile.currentData() or "").strip()
        return selected or str(self.model_profiles.get("active_profile_id") or DEFAULT_MODEL_PROFILE_ID)

    def _project_active_profile_id(self):
        return str(self.model_profiles.get("active_profile_id") or DEFAULT_MODEL_PROFILE_ID)

    def _active_profile(self):
        active_id = str(self.model_profiles.get("active_profile_id") or DEFAULT_MODEL_PROFILE_ID)
        if hasattr(self, "combo_model_profile"):
            combo_id = str(self.combo_model_profile.currentData() or "").strip()
            if combo_id:
                active_id = combo_id
        for profile in self.model_profiles.get("profiles", []):
            if isinstance(profile, dict) and profile.get("profile_id") == active_id:
                return dict(profile)
        profiles = self.model_profiles.get("profiles", [])
        return dict(profiles[0]) if profiles and isinstance(profiles[0], dict) else {}

    def _refresh_profile_combo(self, select_id=None):
        if not hasattr(self, "combo_model_profile"):
            return
        target = str(select_id or self.model_profiles.get("active_profile_id") or DEFAULT_MODEL_PROFILE_ID)
        self.combo_model_profile.blockSignals(True)
        self.combo_model_profile.clear()
        for profile in self.model_profiles.get("profiles", []):
            if not isinstance(profile, dict):
                continue
            profile_id = str(profile.get("profile_id") or "").strip()
            if not profile_id:
                continue
            label = profile.get("display_name") or profile_id
            if profile_id == self._project_active_profile_id():
                label = tr("{0} (active)", self.lang).format(label)
            self.combo_model_profile.addItem(str(label), profile_id)
        index = self.combo_model_profile.findData(target)
        self.combo_model_profile.setCurrentIndex(index if index >= 0 else 0)
        self.combo_model_profile.blockSignals(False)
        self._load_selected_profile_fields()

    def _load_selected_profile_fields(self):
        profile = self._active_profile()
        if hasattr(self, "profile_id_edit"):
            self.profile_id_edit.blockSignals(True)
            self.profile_id_edit.setText(str(profile.get("profile_id") or ""))
            self.profile_id_edit.blockSignals(False)
        if hasattr(self, "profile_name_edit"):
            self.profile_name_edit.blockSignals(True)
            self.profile_name_edit.setText(str(profile.get("display_name") or ""))
            self.profile_name_edit.blockSignals(False)
        if hasattr(self, "profile_description_edit"):
            self.profile_description_edit.blockSignals(True)
            self.profile_description_edit.setPlainText(str(profile.get("description") or ""))
            self.profile_description_edit.blockSignals(False)
        self._apply_profile_to_controls(profile)
        self._refresh_profile_summary()

    def _update_current_profile_metadata(self):
        active_id = self._active_profile_id()
        for profile in self.model_profiles.get("profiles", []):
            if not isinstance(profile, dict) or profile.get("profile_id") != active_id:
                continue
            if hasattr(self, "profile_name_edit"):
                profile["display_name"] = self.profile_name_edit.text().strip() or active_id
            if hasattr(self, "profile_description_edit"):
                profile["description"] = self.profile_description_edit.toPlainText().strip()
            break
        self._refresh_profile_summary()

    def _profile_by_id(self, profile_id):
        target = str(profile_id or "").strip()
        for profile in self.model_profiles.get("profiles", []):
            if isinstance(profile, dict) and str(profile.get("profile_id") or "").strip() == target:
                return dict(profile)
        return {}

    def _route_entries_for_profile_summary(self):
        panel = getattr(self, "route_panel", None)
        project = getattr(getattr(panel, "owner", None), "project", None) if panel is not None else None
        iter_routes = getattr(project, "iter_cascade_routes", None)
        if callable(iter_routes):
            try:
                return [dict(route) for route in iter_routes() if isinstance(route, dict)]
            except Exception:
                return []
        return []

    def _routes_differing_from_child_default(self, profile):
        child_defaults = profile.get("child_backend_defaults", {}) if isinstance(profile.get("child_backend_defaults"), dict) else {}
        default_backend = _route_backend_from_child_backend(child_defaults.get("backend_type", CHILD_BACKEND_VIT_B))
        differing = []
        for route in self._route_entries_for_profile_summary():
            route_backend = _route_backend_from_entry(route)
            if route_backend != default_backend:
                differing.append(dict(route))
        return differing

    def _profile_external_status_lines(self, profile):
        parent_backend = profile.get("parent_backend", {}) if isinstance(profile.get("parent_backend"), dict) else {}
        child_defaults = profile.get("child_backend_defaults", {}) if isinstance(profile.get("child_backend_defaults"), dict) else {}
        lines = []
        if parent_backend.get("backend_type") == PARENT_BACKEND_EXTERNAL:
            external = parent_backend.get("external_backend", {}) if isinstance(parent_backend.get("external_backend"), dict) else {}
            has_command = any(str(external.get(key) or "").strip() for key in ("train_command", "predict_command"))
            lines.append(
                tr("External parent backend: {0}", self.lang).format(
                    tr("configured", self.lang) if has_command else tr("missing train/predict command", self.lang)
                )
            )
        if child_defaults.get("backend_type") == CHILD_BACKEND_EXTERNAL:
            external_blink = child_defaults.get("external_blink_backend", {}) if isinstance(child_defaults.get("external_blink_backend"), dict) else {}
            has_predict = bool(str(external_blink.get("predict_command") or "").strip())
            lines.append(
                tr("External Blink backend: {0}", self.lang).format(
                    tr("configured", self.lang) if has_predict else tr("missing predict command", self.lang)
                )
            )
        return lines

    def _build_profile_summary(self, profile):
        if not isinstance(profile, dict):
            return tr("No model profile selected.", self.lang)
        parent_backend = profile.get("parent_backend", {}) if isinstance(profile.get("parent_backend"), dict) else {}
        child_defaults = profile.get("child_backend_defaults", {}) if isinstance(profile.get("child_backend_defaults"), dict) else {}
        inference_params = profile.get("inference_params", {}) if isinstance(profile.get("inference_params"), dict) else {}
        locator_scope = [
            str(part).strip()
            for part in parent_backend.get("locator_scope", [])
            if str(part).strip()
        ] if isinstance(parent_backend.get("locator_scope"), list) else []
        differing_routes = self._routes_differing_from_child_default(profile)
        route_note = tr(
            "Existing route experts are kept as route-specific bindings; switching profiles does not silently reappoint trained child experts.",
            self.lang,
        )
        lines = [
            tr("Project active profile: {0}", self.lang).format(
                self._active_profile_label(self._profile_by_id(self._project_active_profile_id()))
            ),
            tr("Parent backend: {0}", self.lang).format(_parent_backend_label(parent_backend.get("backend_type"), self.lang)),
            tr("Main locator parts: {0}", self.lang).format(", ".join(locator_scope) if locator_scope else tr("none", self.lang)),
            tr("Default child backend: {0}", self.lang).format(_child_backend_label(child_defaults.get("backend_type"), self.lang)),
            tr("Route-specific experts differing from this default: {0}", self.lang).format(len(differing_routes)),
            tr("Inference: conf={0}, pad={1}, noise={2}", self.lang).format(
                inference_params.get("conf", ""),
                inference_params.get("pad", ""),
                inference_params.get("noise_floor", ""),
            ),
        ]
        lines.extend(self._profile_external_status_lines(profile))
        lines.append(route_note)
        return "\n".join(lines)

    def _refresh_profile_summary(self):
        if not hasattr(self, "profile_summary_box"):
            return
        try:
            profile = self._current_profile_snapshot(update_metadata=False) if hasattr(self, "parent_backend_combo") else self._active_profile()
        except Exception:
            profile = self._active_profile()
        self.profile_summary_box.setPlainText(self._build_profile_summary(profile))

    def _active_profile_label(self, profile):
        profile_id = str(profile.get("profile_id") or "").strip()
        display_name = str(profile.get("display_name") or "").strip()
        if display_name and display_name != profile_id:
            return f"{display_name} ({profile_id})"
        return profile_id or tr("Unknown", self.lang)

    def _profile_id_seed(self, base="custom_profile"):
        existing = {
            str(profile.get("profile_id") or "")
            for profile in self.model_profiles.get("profiles", [])
            if isinstance(profile, dict)
        }
        safe_base = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in str(base or "custom_profile"))
        safe_base = safe_base.strip("_") or "custom_profile"
        if safe_base not in existing:
            return safe_base
        for index in range(2, 1000):
            candidate = f"{safe_base}_{index}"
            if candidate not in existing:
                return candidate
        return f"{safe_base}_{int(time.time())}"

    def new_model_profile(self):
        current = self._current_profile_snapshot()
        new_id = self._profile_id_seed("custom_profile")
        current["profile_id"] = new_id
        current["display_name"] = tr("New Profile", self.lang)
        current["description"] = ""
        self.model_profiles.setdefault("profiles", []).append(current)
        self._refresh_profile_combo(new_id)

    def copy_model_profile(self):
        current = self._current_profile_snapshot()
        base_id = current.get("profile_id") or "copied_profile"
        new_id = self._profile_id_seed(f"{base_id}_copy")
        current["profile_id"] = new_id
        current["display_name"] = f"{current.get('display_name') or base_id} Copy"
        self.model_profiles.setdefault("profiles", []).append(current)
        self._refresh_profile_combo(new_id)

    def delete_model_profile(self):
        active_id = self._active_profile_id()
        current_profile = self._profile_by_id(active_id)
        if active_id == DEFAULT_MODEL_PROFILE_ID:
            QMessageBox.information(
                self,
                tr("Delete Profile", self.lang),
                tr("The built-in default profile cannot be deleted.", self.lang),
            )
            return
        profiles = [
            profile
            for profile in self.model_profiles.get("profiles", [])
            if isinstance(profile, dict) and profile.get("profile_id") != active_id
        ]
        if not profiles:
            QMessageBox.information(
                self,
                tr("Delete Profile", self.lang),
                tr("At least one model profile must remain in the project.", self.lang),
            )
            return
        reply = themed_yes_no_question(
            self,
            tr("Delete Profile", self.lang),
            tr(
                "Delete model profile {0}?\n\nThis removes only the saved profile configuration from the current project. Model weights, external scripts, and route expert bindings are not deleted.",
                self.lang,
            ).format(self._active_profile_label(current_profile)),
            confirm_role=BUTTON_ROLE_DESTRUCTIVE,
        )
        if reply != QMessageBox.Yes:
            return
        self.model_profiles["profiles"] = profiles
        current_project_active = self._project_active_profile_id()
        remaining_ids = {
            str(profile.get("profile_id") or "")
            for profile in profiles
            if isinstance(profile, dict)
        }
        if current_project_active not in remaining_ids:
            self.model_profiles["active_profile_id"] = profiles[0].get("profile_id", DEFAULT_MODEL_PROFILE_ID)
        self._refresh_profile_combo(self.model_profiles["active_profile_id"])

    def _profile_switch_message(self, current_profile, target_profile):
        current_parent = current_profile.get("parent_backend", {}) if isinstance(current_profile.get("parent_backend"), dict) else {}
        current_child = current_profile.get("child_backend_defaults", {}) if isinstance(current_profile.get("child_backend_defaults"), dict) else {}
        target_parent = target_profile.get("parent_backend", {}) if isinstance(target_profile.get("parent_backend"), dict) else {}
        target_child = target_profile.get("child_backend_defaults", {}) if isinstance(target_profile.get("child_backend_defaults"), dict) else {}
        differing_routes = self._routes_differing_from_child_default(target_profile)
        lines = [
            tr("Set {0} as the active model profile?", self.lang).format(self._active_profile_label(target_profile)),
            "",
            tr("Parent backend: {0} -> {1}", self.lang).format(
                _parent_backend_label(current_parent.get("backend_type"), self.lang),
                _parent_backend_label(target_parent.get("backend_type"), self.lang),
            ),
            tr("Default child backend: {0} -> {1}", self.lang).format(
                _child_backend_label(current_child.get("backend_type"), self.lang),
                _child_backend_label(target_child.get("backend_type"), self.lang),
            ),
            tr("Route-specific experts differing from the target default: {0}", self.lang).format(len(differing_routes)),
            tr("Existing route experts stay appointed; this switch only changes the project default profile.", self.lang),
        ]
        return "\n".join(lines)

    def set_selected_profile_active(self):
        selected_id = self._active_profile_id()
        current_id = self._project_active_profile_id()
        target_profile = self._profile_by_id(selected_id)
        if not target_profile:
            QMessageBox.warning(self, tr("Set as Active Profile", self.lang), tr("No model profile selected.", self.lang))
            return
        current_profile = self._profile_by_id(current_id) or target_profile
        if selected_id != current_id:
            reply = themed_yes_no_question(
                self,
                tr("Set as Active Profile", self.lang),
                self._profile_switch_message(current_profile, target_profile),
                confirm_role=BUTTON_ROLE_COMMIT,
            )
            if reply != QMessageBox.Yes:
                self._refresh_profile_combo(current_id)
                return
        self.model_profiles["active_profile_id"] = selected_id
        self._update_current_profile_metadata()
        self._refresh_profile_combo(selected_id)

    def _sync_legacy_backend_combo_from_parent_backend(self):
        if not hasattr(self, "backend_combo") or not hasattr(self, "parent_backend_combo"):
            return
        backend_id = EXTERNAL_BACKEND_ID if self.parent_backend_combo.currentData() == PARENT_BACKEND_EXTERNAL else BUILTIN_BACKEND_ID
        backend_index = self.backend_combo.findData(backend_id)
        self.backend_combo.setCurrentIndex(backend_index if backend_index >= 0 else 0)

    def _refresh_model_source_summaries(self):
        if hasattr(self, "parent_backend_status_label") and hasattr(self, "parent_backend_combo"):
            self.parent_backend_status_label.setText(
                tr("Current parent model source: {0}", self.lang).format(
                    _parent_backend_label(self.parent_backend_combo.currentData(), self.lang)
                )
            )
        if hasattr(self, "child_backend_status_label") and hasattr(self, "child_backend_combo"):
            self.child_backend_status_label.setText(
                tr("Current default child expert: {0}", self.lang).format(
                    _child_backend_label(self.child_backend_combo.currentData(), self.lang)
                )
            )
        if hasattr(self, "parent_extension_status_label") and hasattr(self, "parent_backend_combo"):
            if self.parent_backend_combo.currentData() == PARENT_BACKEND_EXTERNAL:
                parent_text = tr(
                    "Active now: parent-part training and Auto annotation will call this custom parent extension.",
                    self.lang,
                )
            else:
                parent_text = tr(
                    "Not active now: parent-part tasks use Built-in Locator + SAM. These fields are saved for profiles that switch Parent Model Source to Custom Parent Extension.",
                    self.lang,
                )
            self.parent_extension_status_label.setText(parent_text)
        if hasattr(self, "child_extension_status_label") and hasattr(self, "child_backend_combo"):
            if self.child_backend_combo.currentData() == CHILD_BACKEND_EXTERNAL:
                child_text = tr(
                    "Active now: this custom child extension is the default child expert for unresolved routes. Appointed route experts still keep their own bindings.",
                    self.lang,
                )
            else:
                child_text = tr(
                    "Not active now: the default child expert is {0}. These fields are saved for profiles that switch Default Child Expert to Custom Child Extension.",
                    self.lang,
                ).format(_child_backend_label(self.child_backend_combo.currentData(), self.lang))
            self.child_extension_status_label.setText(child_text)
        if hasattr(self, "profile_summary_box"):
            self._refresh_profile_summary()

    def _apply_profile_to_controls(self, profile):
        if not isinstance(profile, dict):
            return
        parent_backend = profile.get("parent_backend", {}) if isinstance(profile.get("parent_backend"), dict) else {}
        child_defaults = profile.get("child_backend_defaults", {}) if isinstance(profile.get("child_backend_defaults"), dict) else {}
        inference_params = profile.get("inference_params", {}) if isinstance(profile.get("inference_params"), dict) else {}

        if hasattr(self, "parent_backend_combo"):
            index = self.parent_backend_combo.findData(parent_backend.get("backend_type", PARENT_BACKEND_BUILTIN))
            self.parent_backend_combo.setCurrentIndex(index if index >= 0 else 0)
        self._sync_legacy_backend_combo_from_parent_backend()
        if hasattr(self, "child_backend_combo"):
            index = self.child_backend_combo.findData(child_defaults.get("backend_type", CHILD_BACKEND_VIT_B))
            self.child_backend_combo.setCurrentIndex(index if index >= 0 else 0)
        self._refresh_model_source_summaries()

        external_parent = sanitize_external_backend_config(parent_backend.get("external_backend", {}))
        for editor_name, key in [
            ("external_backend_id", "backend_id"),
            ("external_display_name", "display_name"),
            ("external_python", "python_executable"),
            ("external_model_manifest", "model_manifest"),
        ]:
            if hasattr(self, editor_name):
                getattr(self, editor_name).setText(str(external_parent.get(key, "")))
        for editor_name, key in [
            ("external_prepare_command", "prepare_dataset_command"),
            ("external_train_command", "train_command"),
            ("external_predict_command", "predict_command"),
        ]:
            if hasattr(self, editor_name):
                getattr(self, editor_name).setPlainText(str(external_parent.get(key, "")))

        train_params = parent_backend.get("train_params", {}) if isinstance(parent_backend.get("train_params"), dict) else {}
        for editor_name, value in [
            ("spin_epochs", train_params.get("epochs")),
            ("spin_batch", train_params.get("batch")),
            ("spin_lr", train_params.get("lr")),
            ("spin_wd", train_params.get("weight_decay")),
        ]:
            if hasattr(self, editor_name) and value is not None:
                getattr(self, editor_name).setText(str(value))

        child_train = child_defaults.get("train_params", {}) if isinstance(child_defaults.get("train_params"), dict) else {}
        for editor_name, value in [
            ("spin_blink_epochs", child_train.get("epochs")),
            ("spin_blink_batch", child_train.get("batch")),
            ("spin_blink_lr", child_train.get("lr")),
            ("spin_blink_wd", child_train.get("weight_decay")),
        ]:
            if hasattr(self, editor_name) and value is not None:
                getattr(self, editor_name).setText(str(value))
        if hasattr(self, "combo_blink_input_size"):
            try:
                input_size = int(child_defaults.get("input_size", 224))
            except Exception:
                input_size = 224
            index = self.combo_blink_input_size.findData(input_size)
            self.combo_blink_input_size.setCurrentIndex(index if index >= 0 else 0)
        if hasattr(self, "spin_blink_auto_shrink_steps"):
            try:
                shrink_steps = int(child_defaults.get("auto_shrink_steps", DEFAULT_CHILD_AUTO_SHRINK_STEPS))
            except Exception:
                shrink_steps = DEFAULT_CHILD_AUTO_SHRINK_STEPS
            self.spin_blink_auto_shrink_steps.setValue(max(1, min(200, shrink_steps)))
        if hasattr(self, "combo_blink_training_strategy"):
            strategy = sanitize_blink_training_strategy(
                child_defaults.get("training_strategy"),
                DEFAULT_BLINK_TRAINING_STRATEGY,
            )
            index = self.combo_blink_training_strategy.findData(strategy)
            self.combo_blink_training_strategy.setCurrentIndex(index if index >= 0 else 0)
            self._update_blink_training_strategy_note()

        heatmap_params = child_defaults.get("heatmap_params", {}) if isinstance(child_defaults.get("heatmap_params"), dict) else {}
        for editor_name, key in [
            ("spin_heatmap_input_size", "input_size"),
            ("spin_heatmap_sigma", "heatmap_sigma"),
            ("spin_heatmap_wh_loss", "wh_loss_weight"),
            ("spin_heatmap_center_loss", "center_loss_weight"),
        ]:
            if hasattr(self, editor_name):
                getattr(self, editor_name).setText(str(heatmap_params.get(key, DEFAULT_HEATMAP_BLINK_PARAMS.get(key, ""))))

        external_blink = dict(DEFAULT_EXTERNAL_BLINK_BACKEND)
        if isinstance(child_defaults.get("external_blink_backend"), dict):
            external_blink.update(child_defaults.get("external_blink_backend"))
        for editor_name, key in [
            ("external_blink_backend_id", "backend_id"),
            ("external_blink_display_name", "display_name"),
            ("external_blink_python", "python_executable"),
            ("external_blink_model_manifest", "model_manifest"),
        ]:
            if hasattr(self, editor_name):
                getattr(self, editor_name).setText(str(external_blink.get(key, "")))
        if hasattr(self, "external_blink_predict_command"):
            self.external_blink_predict_command.setPlainText(str(external_blink.get("predict_command", "")))
        if hasattr(self, "external_blink_train_command"):
            self.external_blink_train_command.setPlainText(str(external_blink.get("train_command", "")))

        locator_scope = parent_backend.get("locator_scope", [])
        if isinstance(locator_scope, list):
            selected = {str(part).strip() for part in locator_scope if str(part).strip()}
            for check in getattr(self, "locator_scope_checks", []):
                part_name = str(check.property("part_name") or check.text()).strip()
                check.setChecked(part_name in selected)

        ratios = parent_backend.get("parent_box_aspect_ratios", {})
        if isinstance(ratios, dict):
            for part_name in getattr(self, "parent_box_ratio_inputs", {}):
                self._set_parent_box_ratio_input(part_name, ratios.get(part_name, ""))

        for editor_name, key in [
            ("spin_conf", "conf"),
            ("spin_adapt", "adapt"),
            ("spin_pad", "pad"),
            ("spin_noise", "noise_floor"),
            ("spin_poly", "poly_epsilon"),
        ]:
            if hasattr(self, editor_name) and key in inference_params:
                getattr(self, editor_name).setText(str(inference_params.get(key)))

        vlm = inference_params.get("vlm_preannotation", {}) if isinstance(inference_params.get("vlm_preannotation"), dict) else {}
        selected_vlm = {str(part).strip() for part in vlm.get("target_parts", []) if str(part).strip()}
        for check in getattr(self, "vlm_target_part_checks", []):
            part_name = str(check.property("part_name") or check.text()).strip()
            check.setChecked(part_name in selected_vlm)
        if hasattr(self, "combo_vlm_processing_scope"):
            scope_value = str(vlm.get("processing_scope", "image_group") or "image_group")
            if scope_value == "current_image":
                scope_value = "image_group"
            index = self.combo_vlm_processing_scope.findData(scope_value)
            self.combo_vlm_processing_scope.setCurrentIndex(index if index >= 0 else 0)
        if hasattr(self, "combo_vlm_image_group"):
            self._populate_vlm_image_group_combo(str(vlm.get("image_group", "split") or "split"))
        if hasattr(self, "spin_vlm_concurrency"):
            try:
                concurrency = int(vlm.get("concurrency", 1))
            except Exception:
                concurrency = 1
            self.spin_vlm_concurrency.setValue(max(1, min(8, concurrency)))
        self._set_vlm_prompt_profile_controls(vlm)

    def _default_vlm_image_group_definitions(self):
        return [
            ("original", tr("Original Images", self.lang)),
            ("split", tr("Split Crops", self.lang)),
            ("hard_candidates", tr("Hard-joined Candidates", self.lang)),
            ("manual_done", tr("Manual Split Done", self.lang)),
            ("manual", tr("Manual Split Needed", self.lang)),
        ]

    def _normalize_vlm_image_group_definitions(self, raw_definitions):
        clean = []
        seen = set()

        def add(group_id, label):
            group_id = str(group_id or "").strip()
            label = str(label or "").strip()
            if not group_id or not label or group_id in seen:
                return
            seen.add(group_id)
            clean.append((group_id, label))

        for group_id, label in self._default_vlm_image_group_definitions():
            add(group_id, label)
        if isinstance(raw_definitions, list):
            for item in raw_definitions:
                if isinstance(item, dict):
                    add(item.get("id", ""), item.get("name", ""))
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    add(item[0], item[1])
        return clean

    def _populate_vlm_image_group_combo(self, selected_group=None):
        if not hasattr(self, "combo_vlm_image_group"):
            return
        current = str(selected_group or self.combo_vlm_image_group.currentData() or "split")
        self.combo_vlm_image_group.blockSignals(True)
        self.combo_vlm_image_group.clear()
        for group_id, label in self.vlm_image_group_definitions:
            self.combo_vlm_image_group.addItem(label, group_id)
        index = self.combo_vlm_image_group.findData(current)
        if index < 0:
            index = self.combo_vlm_image_group.findData("split")
        self.combo_vlm_image_group.setCurrentIndex(index if index >= 0 else 0)
        self.combo_vlm_image_group.blockSignals(False)

    def _external_blink_config_values(self):
        return {
            "backend_id": self.external_blink_backend_id.text().strip() if hasattr(self, "external_blink_backend_id") else DEFAULT_EXTERNAL_BLINK_BACKEND["backend_id"],
            "display_name": self.external_blink_display_name.text().strip() if hasattr(self, "external_blink_display_name") else DEFAULT_EXTERNAL_BLINK_BACKEND["display_name"],
            "python_executable": self.external_blink_python.text().strip() if hasattr(self, "external_blink_python") else "python",
            "predict_command": self._command_text(self.external_blink_predict_command) if hasattr(self, "external_blink_predict_command") else "",
            "train_command": self._command_text(self.external_blink_train_command) if hasattr(self, "external_blink_train_command") else "",
            "model_manifest": self.external_blink_model_manifest.text().strip() if hasattr(self, "external_blink_model_manifest") else "",
        }

    def _external_blink_validation_errors(self):
        if not hasattr(self, "child_backend_combo") or self.child_backend_combo.currentData() != CHILD_BACKEND_EXTERNAL:
            return []
        config = self._external_blink_config_values()
        errors = []
        if not config["backend_id"]:
            errors.append(tr("Child extension ID is required.", self.lang))
        if not config["predict_command"]:
            errors.append(tr("Child extension needs a predict command before it can be used for child-part annotation.", self.lang))
        commands = {
            "predict_child": config["predict_command"],
            "train_child": config["train_command"],
        }
        for command_name, command_text in commands.items():
            if command_text and "{contract}" not in command_text and "{contract_json}" not in command_text:
                errors.append(
                    _format_backend_contract_error(
                        tr(
                            "Child extension command '{0}' must include {contract} or {contract_json}.",
                            self.lang,
                        ),
                        command_name,
                    )
                )
        return errors

    def validate_external_blink_backend(self):
        errors = self._external_blink_validation_errors()
        if errors:
            self.external_blink_validation_label.setText("\n".join(errors))
            QMessageBox.warning(self, tr("Advanced Extensions", self.lang), "\n".join(errors))
            return False
        self.external_blink_validation_label.setText(tr("Child extension configuration looks valid.", self.lang))
        QMessageBox.information(self, tr("Advanced Extensions", self.lang), tr("Child extension configuration looks valid.", self.lang))
        return True

    def _current_profile_snapshot(self, update_metadata=True):
        if update_metadata:
            self._update_current_profile_metadata()
        active_id = self._active_profile_id()
        base_profile = self._active_profile()
        parent_backend = dict(base_profile.get("parent_backend", {}) if isinstance(base_profile.get("parent_backend"), dict) else {})
        child_defaults = dict(base_profile.get("child_backend_defaults", {}) if isinstance(base_profile.get("child_backend_defaults"), dict) else {})
        inference_params = dict(base_profile.get("inference_params", {}) if isinstance(base_profile.get("inference_params"), dict) else {})
        parent_backend.update(
            {
                "backend_type": self.parent_backend_combo.currentData() or PARENT_BACKEND_BUILTIN,
                "locator_scope": self._selected_locator_scope(),
                "train_params": {
                    "epochs": int(self.spin_epochs.text()),
                    "batch": int(self.spin_batch.text()),
                    "lr": float(self.spin_lr.text()),
                    "weight_decay": float(self.spin_wd.text()),
                },
                "parent_box_aspect_ratios": self._parent_box_aspect_ratio_values(),
                "external_backend": sanitize_external_backend_config(
                    {
                        "backend_id": self.external_backend_id.text(),
                        "display_name": self.external_display_name.text(),
                        "python_executable": self.external_python.text(),
                        "prepare_dataset_command": self._command_text(self.external_prepare_command),
                        "train_command": self._command_text(self.external_train_command),
                        "predict_command": self._command_text(self.external_predict_command),
                        "model_manifest": self.external_model_manifest.text(),
                    }
                ),
            }
        )
        child_defaults.update(
            {
                "backend_type": self.child_backend_combo.currentData() or CHILD_BACKEND_VIT_B,
                "input_size": int(self.combo_blink_input_size.currentData() or 224),
                "auto_shrink_steps": int(self.spin_blink_auto_shrink_steps.value())
                if hasattr(self, "spin_blink_auto_shrink_steps")
                else DEFAULT_CHILD_AUTO_SHRINK_STEPS,
                "training_strategy": sanitize_blink_training_strategy(
                    self.combo_blink_training_strategy.currentData()
                    if hasattr(self, "combo_blink_training_strategy")
                    else DEFAULT_BLINK_TRAINING_STRATEGY
                ),
                "train_params": {
                    "epochs": int(self.spin_blink_epochs.text()),
                    "batch": int(self.spin_blink_batch.text()),
                    "lr": float(self.spin_blink_lr.text()),
                    "weight_decay": float(self.spin_blink_wd.text()),
                },
                "heatmap_params": {
                    "input_size": int(float(self.spin_heatmap_input_size.text())),
                    "heatmap_sigma": float(self.spin_heatmap_sigma.text()),
                    "wh_loss_weight": float(self.spin_heatmap_wh_loss.text()),
                    "center_loss_weight": float(self.spin_heatmap_center_loss.text()),
                },
                "external_blink_backend": self._external_blink_config_values(),
            }
        )
        inference_params.update(
            {
                "conf": float(self.spin_conf.text()),
                "adapt": float(self.spin_adapt.text()),
                "pad": float(self.spin_pad.text()),
                "noise_floor": float(self.spin_noise.text()),
                "poly_epsilon": float(self.spin_poly.text()),
                "vlm_preannotation": {
                    "target_parts": self._selected_vlm_target_parts(),
                    "processing_scope": self.combo_vlm_processing_scope.currentData() or "image_group",
                    "image_group": self.combo_vlm_image_group.currentData() if hasattr(self, "combo_vlm_image_group") else "split",
                    "concurrency": int(self.spin_vlm_concurrency.value()) if hasattr(self, "spin_vlm_concurrency") else 1,
                    **self._current_vlm_prompt_profile_values(),
                },
            }
        )
        return {
            "profile_id": active_id,
            "display_name": self.profile_name_edit.text().strip() or active_id,
            "description": self.profile_description_edit.toPlainText().strip(),
            "profile_scope": "2d_stl",
            "parent_backend": parent_backend,
            "child_backend_defaults": child_defaults,
            "inference_params": inference_params,
        }

    def _updated_model_profiles(self):
        snapshot = self._current_profile_snapshot()
        active_id = self._project_active_profile_id()
        profiles = []
        replaced = False
        for profile in self.model_profiles.get("profiles", []):
            if not isinstance(profile, dict):
                continue
            if profile.get("profile_id") == snapshot.get("profile_id"):
                profiles.append(snapshot)
                replaced = True
            else:
                profiles.append(dict(profile))
        if not replaced:
            profiles.append(snapshot)
        clean = sanitize_model_profiles(
            {
                "schema_version": self.model_profiles.get("schema_version"),
                "active_profile_id": self._project_active_profile_id(),
                "profiles": profiles,
            },
            taxonomy=self.taxonomy,
            locator_scope=self._selected_locator_scope(),
            parent_box_aspect_ratios=self._parent_box_aspect_ratio_values(),
            vlm_preannotation={
                "target_parts": self._selected_vlm_target_parts(),
                "processing_scope": self.combo_vlm_processing_scope.currentData() or "image_group",
                "image_group": self.combo_vlm_image_group.currentData() if hasattr(self, "combo_vlm_image_group") else "split",
                "concurrency": int(self.spin_vlm_concurrency.value()) if hasattr(self, "spin_vlm_concurrency") else 1,
                **self._current_vlm_prompt_profile_values(),
            },
        )
        self.model_profiles = clean
        return clean

    def _profile_for_legacy_values(self, model_profiles):
        active_id = str((model_profiles or {}).get("active_profile_id") or DEFAULT_MODEL_PROFILE_ID)
        for profile in (model_profiles or {}).get("profiles", []):
            if isinstance(profile, dict) and str(profile.get("profile_id") or "") == active_id:
                return dict(profile)
        profiles = (model_profiles or {}).get("profiles", [])
        return dict(profiles[0]) if profiles and isinstance(profiles[0], dict) else self._current_profile_snapshot(update_metadata=False)

    def _legacy_values_from_profile(self, profile):
        parent_backend = profile.get("parent_backend", {}) if isinstance(profile.get("parent_backend"), dict) else {}
        child_defaults = profile.get("child_backend_defaults", {}) if isinstance(profile.get("child_backend_defaults"), dict) else {}
        parent_train = parent_backend.get("train_params", {}) if isinstance(parent_backend.get("train_params"), dict) else {}
        child_train = child_defaults.get("train_params", {}) if isinstance(child_defaults.get("train_params"), dict) else {}
        inference_params = profile.get("inference_params", {}) if isinstance(profile.get("inference_params"), dict) else {}
        vlm = inference_params.get("vlm_preannotation", {}) if isinstance(inference_params.get("vlm_preannotation"), dict) else {}
        return {
            "epochs": int(parent_train.get("epochs", self.spin_epochs.text())),
            "batch": int(parent_train.get("batch", self.spin_batch.text())),
            "blink_epochs": int(child_train.get("epochs", self.spin_blink_epochs.text())),
            "blink_batch": int(child_train.get("batch", self.spin_blink_batch.text())),
            "blink_lr": float(child_train.get("lr", self.spin_blink_lr.text())),
            "blink_weight_decay": float(child_train.get("weight_decay", self.spin_blink_wd.text())),
            "blink_input_size": int(child_defaults.get("input_size", self.combo_blink_input_size.currentData() or 224)),
            "blink_auto_shrink_steps": int(child_defaults.get("auto_shrink_steps", DEFAULT_CHILD_AUTO_SHRINK_STEPS)),
            "blink_training_strategy": sanitize_blink_training_strategy(
                child_defaults.get("training_strategy"),
                DEFAULT_BLINK_TRAINING_STRATEGY,
            ),
            "lr": float(parent_train.get("lr", self.spin_lr.text())),
            "wd": float(parent_train.get("weight_decay", self.spin_wd.text())),
            "conf": float(inference_params.get("conf", self.spin_conf.text())),
            "adapt": float(inference_params.get("adapt", self.spin_adapt.text())),
            "pad": float(inference_params.get("pad", self.spin_pad.text())),
            "noise_floor": float(inference_params.get("noise_floor", self.spin_noise.text())),
            "poly_epsilon": float(inference_params.get("poly_epsilon", self.spin_poly.text())),
            "locator_scope": list(parent_backend.get("locator_scope", self._selected_locator_scope()) or []),
            "vlm_preannotation": {
                "target_parts": list(vlm.get("target_parts", self._selected_vlm_target_parts()) or []),
                "processing_scope": str(vlm.get("processing_scope", self.combo_vlm_processing_scope.currentData() or "image_group") or "image_group"),
                "image_group": str(vlm.get("image_group", self.combo_vlm_image_group.currentData() if hasattr(self, "combo_vlm_image_group") else "split") or "split"),
                "concurrency": int(vlm.get("concurrency", self.spin_vlm_concurrency.value() if hasattr(self, "spin_vlm_concurrency") else 1) or 1),
                "prompt_profile_id": str(vlm.get("prompt_profile_id", DEFAULT_VLM_PROMPT_PROFILE_ID) or DEFAULT_VLM_PROMPT_PROFILE_ID),
                "prompt_profile": sanitize_vlm_prompt_profile(vlm.get("prompt_profile", {})),
            },
            "parent_box_aspect_ratios": dict(parent_backend.get("parent_box_aspect_ratios", self._parent_box_aspect_ratio_values()) or {}),
        }

    def _legacy_model_backend_from_profile(self, profile):
        parent_backend = profile.get("parent_backend", {}) if isinstance(profile.get("parent_backend"), dict) else {}
        return EXTERNAL_BACKEND_ID if parent_backend.get("backend_type") == PARENT_BACKEND_EXTERNAL else BUILTIN_BACKEND_ID

    def _external_backend_from_profile(self, profile):
        parent_backend = profile.get("parent_backend", {}) if isinstance(profile.get("parent_backend"), dict) else {}
        return sanitize_external_backend_config(parent_backend.get("external_backend", {}))

    def _current_parent_backend_requires_external_config(self):
        if hasattr(self, "parent_backend_combo"):
            return self.parent_backend_combo.currentData() == PARENT_BACKEND_EXTERNAL
        return self.backend_combo.currentData() == EXTERNAL_BACKEND_ID

    def _external_backend_validation_errors(self):
        if not self._current_parent_backend_requires_external_config():
            return []
        errors = []
        if not self.external_backend_id.text().strip():
            errors.append(tr("Parent extension ID is required.", self.lang))

        commands = {
            "prepare_dataset": self._command_text(self.external_prepare_command),
            "train": self._command_text(self.external_train_command),
            "predict": self._command_text(self.external_predict_command),
        }
        if not commands["train"] and not commands["predict"]:
            errors.append(tr("Parent extension needs at least a train command or a predict command.", self.lang))

        for command_name, command_text in commands.items():
            if command_text and "{contract}" not in command_text and "{contract_json}" not in command_text:
                errors.append(
                    _format_backend_contract_error(
                        tr(
                            "Parent extension command '{0}' must include {contract} or {contract_json}.",
                            self.lang,
                        ),
                        command_name,
                    )
                )
        return errors

    def validate_external_backend(self):
        errors = self._external_backend_validation_errors()
        if errors:
            self.external_validation_label.setText("\n".join(errors))
            QMessageBox.warning(self, tr("Advanced Extensions", self.lang), "\n".join(errors))
            return False
        self.external_validation_label.setText(tr("Parent extension configuration looks valid.", self.lang))
        QMessageBox.information(self, tr("Advanced Extensions", self.lang), tr("Parent extension configuration looks valid.", self.lang))
        return True

    def accept_with_validation(self):
        errors = self._external_backend_validation_errors()
        errors.extend(self._external_blink_validation_errors())
        errors.extend(self._parent_box_aspect_ratio_errors())
        if not self._selected_locator_scope():
            errors.append(tr("At least one main locator part must be selected.", self.lang))
        if errors:
            message = "\n".join(errors)
            self.external_validation_label.setText(message)
            if hasattr(self, "external_blink_validation_label"):
                self.external_blink_validation_label.setText(message)
            self.locator_scope_validation_label.setText(message)
            QMessageBox.warning(self, tr("Model Settings", self.lang), message)
            return
        self.accept()

    def _selected_locator_scope(self):
        selected = []
        for check in self.locator_scope_checks:
            if check.isChecked():
                part_name = str(check.property("part_name") or check.text()).strip()
                if part_name:
                    selected.append(part_name)
        return selected

    def _selected_vlm_target_parts(self):
        selected = []
        for check in self.vlm_target_part_checks:
            if check.isChecked():
                part_name = str(check.property("part_name") or check.text()).strip()
                if part_name:
                    selected.append(part_name)
        return selected

    def _format_parent_ratio_number(self, value):
        try:
            number = float(value)
        except Exception:
            return ""
        if number <= 0:
            return ""
        if abs(number - round(number)) < 1e-9:
            return str(int(round(number)))
        return f"{number:.6g}"

    def _parent_ratio_display_values(self, aspect_ratio):
        try:
            ratio = float(aspect_ratio)
        except Exception:
            return "", ""
        if ratio <= 0:
            return "", ""
        fraction = Fraction(ratio).limit_denominator(64)
        approximate = fraction.numerator / fraction.denominator
        if abs(approximate - ratio) <= max(1e-6, abs(ratio) * 1e-4):
            return str(fraction.numerator), str(fraction.denominator)
        return self._format_parent_ratio_number(ratio), "1"

    def _parent_ratio_editor_pair(self, editors):
        if isinstance(editors, (tuple, list)) and len(editors) >= 2:
            return editors[0], editors[1]
        return None, None

    def _set_parent_box_ratio_input(self, part_name, aspect_ratio):
        editors = getattr(self, "parent_box_ratio_inputs", {}).get(part_name)
        width_edit, height_edit = self._parent_ratio_editor_pair(editors)
        if width_edit is None or height_edit is None:
            if hasattr(editors, "setText"):
                editors.setText(str(aspect_ratio) if aspect_ratio != "" else "")
            return
        width_text, height_text = self._parent_ratio_display_values(aspect_ratio)
        width_edit.setText(width_text)
        height_edit.setText(height_text)

    def _parent_box_aspect_ratio_errors(self):
        errors = []
        for part_name, editors in getattr(self, "parent_box_ratio_inputs", {}).items():
            width_edit, height_edit = self._parent_ratio_editor_pair(editors)
            if width_edit is None or height_edit is None:
                text = editors.text().strip() if hasattr(editors, "text") else ""
                if not text:
                    continue
                try:
                    ratio = float(text)
                except Exception:
                    ratio = 0
                if ratio <= 0:
                    errors.append(tr("Parent box ratio for {0} must have positive width and height values.", self.lang).format(part_name))
                continue
            width_text = width_edit.text().strip()
            height_text = height_edit.text().strip()
            if not width_text and not height_text:
                continue
            try:
                width_value = float(width_text)
                height_value = float(height_text)
            except Exception:
                width_value = 0
                height_value = 0
            if width_value <= 0 or height_value <= 0:
                errors.append(tr("Parent box ratio for {0} must have positive width and height values.", self.lang).format(part_name))
        return errors

    def _parent_box_aspect_ratio_values(self):
        ratios = {}
        for part_name, editors in getattr(self, "parent_box_ratio_inputs", {}).items():
            width_edit, height_edit = self._parent_ratio_editor_pair(editors)
            if width_edit is None or height_edit is None:
                text = editors.text().strip() if hasattr(editors, "text") else ""
                if not text:
                    continue
                try:
                    ratio = float(text)
                except Exception:
                    continue
                if ratio > 0:
                    ratios[part_name] = ratio
                continue
            width_text = width_edit.text().strip()
            height_text = height_edit.text().strip()
            if not width_text and not height_text:
                continue
            try:
                width_value = float(width_text)
                height_value = float(height_text)
            except Exception:
                continue
            if width_value <= 0 or height_value <= 0:
                continue
            ratio = width_value / height_value
            if ratio > 0:
                ratios[part_name] = ratio
        return ratios

    def request_agent_help(self):
        self.agent_requested.emit(self.get_agent_context())
        self.reject()

    def get_agent_context(self):
        prepare_command = self._command_text(self.external_prepare_command)
        train_command = self._command_text(self.external_train_command)
        predict_command = self._command_text(self.external_predict_command)
        child_predict_command = self._command_text(self.external_blink_predict_command)
        child_train_command = self._command_text(self.external_blink_train_command)
        selected_profile = self._current_profile_snapshot(update_metadata=False)
        project_active_profile = self._profile_by_id(self._project_active_profile_id()) or selected_profile
        selected_model_backend = self._legacy_model_backend_from_profile(selected_profile)
        active_model_backend = self._legacy_model_backend_from_profile(project_active_profile)
        parent_backend = selected_profile.get("parent_backend", {}) if isinstance(selected_profile.get("parent_backend"), dict) else {}
        child_defaults = selected_profile.get("child_backend_defaults", {}) if isinstance(selected_profile.get("child_backend_defaults"), dict) else {}
        parent_backend_type = parent_backend.get("backend_type", self.parent_backend_combo.currentData() if hasattr(self, "parent_backend_combo") else PARENT_BACKEND_BUILTIN)
        child_backend_type = child_defaults.get("backend_type", self.child_backend_combo.currentData() if hasattr(self, "child_backend_combo") else CHILD_BACKEND_VIT_B)
        child_training_strategy = sanitize_blink_training_strategy(
            child_defaults.get("training_strategy"),
            DEFAULT_BLINK_TRAINING_STRATEGY,
        )
        route_differences = self._routes_differing_from_child_default(selected_profile)
        route_summary = []
        for route in route_differences[:8]:
            parent = str(route.get("parent") or "").strip()
            child = str(route.get("child") or "").strip()
            backend = _route_backend_from_entry(route)
            if parent and child:
                route_summary.append(f"{parent}->{child}:{backend}")
        validation_errors = self._external_backend_validation_errors() + self._external_blink_validation_errors()
        return {
            "source_workbench": "stl_model_settings",
            "project_type": "settings",
            "settings_scope": "2d_stl_model",
            "settings_question_focus": "Advanced Extensions configuration for 2D/STL model profiles: parent model source, child expert default, custom extension contracts, and route expert compatibility.",
            "model_backend": active_model_backend,
            "selected_profile_model_backend": selected_model_backend,
            "advanced_extension_scope": "2d_stl_model_profile",
            "parent_model_source": str(parent_backend_type or ""),
            "parent_model_source_label": _parent_backend_label(parent_backend_type, self.lang),
            "default_child_expert": str(child_backend_type or ""),
            "default_child_expert_label": _child_backend_label(child_backend_type, self.lang),
            "blink_training_strategy": child_training_strategy,
            "blink_training_strategy_label": blink_training_strategy_label(child_training_strategy, self.lang),
            "default_child_route_backend": _route_backend_from_child_backend(child_backend_type),
            "route_specific_backend_count": str(len(route_differences)),
            "route_specific_backend_summary": "; ".join(route_summary),
            "runtime_device": self.combo_runtime_device.currentData() or "auto",
            "external_backend_id": self.external_backend_id.text().strip(),
            "external_display_name": self.external_display_name.text().strip(),
            "external_python": self.external_python.text().strip(),
            "parent_prepare_command_present": _agent_yes_no(bool(prepare_command)),
            "parent_train_command_present": _agent_yes_no(bool(train_command)),
            "parent_predict_command_present": _agent_yes_no(bool(predict_command)),
            "parent_prepare_command_has_contract": _agent_yes_no(_agent_command_has_contract(prepare_command)),
            "parent_train_command_has_contract": _agent_yes_no(_agent_command_has_contract(train_command)),
            "parent_predict_command_has_contract": _agent_yes_no(_agent_command_has_contract(predict_command)),
            "parent_model_manifest_present": _agent_yes_no(bool(self.external_model_manifest.text().strip())),
            "prepare_command_present": _agent_yes_no(bool(prepare_command)),
            "train_command_present": _agent_yes_no(bool(train_command)),
            "predict_command_present": _agent_yes_no(bool(predict_command)),
            "prepare_command_has_contract": _agent_yes_no(_agent_command_has_contract(prepare_command)),
            "train_command_has_contract": _agent_yes_no(_agent_command_has_contract(train_command)),
            "predict_command_has_contract": _agent_yes_no(_agent_command_has_contract(predict_command)),
            "model_manifest_present": _agent_yes_no(bool(self.external_model_manifest.text().strip())),
            "child_extension_id": self.external_blink_backend_id.text().strip(),
            "child_extension_display_name": self.external_blink_display_name.text().strip(),
            "child_extension_python": self.external_blink_python.text().strip(),
            "child_predict_command_present": _agent_yes_no(bool(child_predict_command)),
            "child_train_command_present": _agent_yes_no(bool(child_train_command)),
            "child_predict_command_has_contract": _agent_yes_no(_agent_command_has_contract(child_predict_command)),
            "child_train_command_has_contract": _agent_yes_no(_agent_command_has_contract(child_train_command)),
            "child_model_manifest_present": _agent_yes_no(bool(self.external_blink_model_manifest.text().strip())),
            "locator_scope_count": str(len(self._selected_locator_scope())),
            "parent_box_ratio_count": str(len(self._parent_box_aspect_ratio_values())),
            "child_backend": self.child_backend_combo.currentData() if hasattr(self, "child_backend_combo") else CHILD_BACKEND_VIT_B,
            "model_profile_id": self._project_active_profile_id(),
            "selected_model_profile_id": self._active_profile_id(),
            "validation_errors": _agent_error_summary(validation_errors),
        }

    def get_values(self):
        try:
            model_profiles = self._updated_model_profiles()
            active_profile = self._profile_for_legacy_values(model_profiles)
            active_values = self._legacy_values_from_profile(active_profile)
            return {
                'epochs': active_values["epochs"],
                'batch': active_values["batch"],
                'blink_epochs': active_values["blink_epochs"],
                'blink_batch': active_values["blink_batch"],
                'blink_lr': active_values["blink_lr"],
                'blink_weight_decay': active_values["blink_weight_decay"],
                'blink_input_size': active_values["blink_input_size"],
                'blink_auto_shrink_steps': active_values["blink_auto_shrink_steps"],
                'blink_training_strategy': active_values["blink_training_strategy"],
                'lr': active_values["lr"],
                'wd': active_values["wd"],
                'conf': active_values["conf"],
                'adapt': active_values["adapt"],
                'pad': active_values["pad"],
                'noise_floor': active_values["noise_floor"],
                'poly_epsilon': active_values["poly_epsilon"],
                'locator_scope': active_values["locator_scope"],
                'vlm_preannotation': active_values["vlm_preannotation"],
                'parent_box_aspect_ratios': active_values["parent_box_aspect_ratios"],
                'runtime_device': self.combo_runtime_device.currentData() or "auto",
                'model_backend': self._legacy_model_backend_from_profile(active_profile),
                'model_profiles': model_profiles,
                'external_backend': self._external_backend_from_profile(active_profile),
            }
        except: return None


class GeneralSettingsDialog(QDialog):
    agent_requested = Signal(dict)

    def __init__(self, params, lang="en", parent=None):
        super().__init__(parent)
        self.lang = lang
        self.setWindowTitle(tr("General Application Settings", lang))
        self.resize(620, 460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        note = QLabel(
            tr(
                "General settings control the whole application: language, theme, startup behavior, autosave, and the default compute device. Workflow-specific training parameters stay in their own model settings.",
                lang,
            )
        )
        note.setWordWrap(True)
        note.setObjectName("mutedLabel")
        layout.addWidget(note)

        group = QGroupBox(tr("Application Preferences", lang))
        apply_surface_role(group, SURFACE_ROLE_SUBTLE, "generalSettingsPreferencesPanel")
        form = QFormLayout(group)
        form.setContentsMargins(12, 12, 12, 12)
        form.setSpacing(10)

        self.language_combo = NoWheelComboBox()
        self.language_combo.addItem("English", "en")
        self.language_combo.addItem("中文", "zh")
        language_index = self.language_combo.findData(params.get("language", "en"))
        self.language_combo.setCurrentIndex(language_index if language_index >= 0 else 0)
        form.addRow(QLabel(tr("Language:", lang)), self.language_combo)

        self.theme_combo = NoWheelComboBox()
        self.theme_combo.addItem(tr("Dark Mode", lang), "dark")
        theme_index = self.theme_combo.findData(normalize_theme(params.get("theme", "dark")))
        self.theme_combo.setCurrentIndex(theme_index if theme_index >= 0 else 0)
        form.addRow(QLabel(tr("Theme:", lang)), self.theme_combo)

        theme_note = QLabel(tr("Only the audited dark theme is currently enabled.", lang))
        theme_note.setWordWrap(True)
        theme_note.setObjectName("mutedLabel")
        form.addRow(QLabel(""), theme_note)

        self.startup_combo = NoWheelComboBox()
        self.startup_combo.addItem(tr("Show Start Center", lang), "start_center")
        self.startup_combo.addItem(tr("Continue last project automatically", lang), "continue_last")
        startup_index = self.startup_combo.findData(params.get("startup_behavior", "start_center"))
        self.startup_combo.setCurrentIndex(startup_index if startup_index >= 0 else 0)
        form.addRow(QLabel(tr("Startup Behavior:", lang)), self.startup_combo)

        self.autosave_seconds = QLineEdit(str(params.get("project_autosave_interval_sec", 3)))
        form.addRow(QLabel(tr("Project Autosave Interval (seconds):", lang)), self.autosave_seconds)

        self.runtime_combo = NoWheelComboBox()
        self.runtime_combo.addItem(tr("Auto (CUDA if available)", lang), "auto")
        self.runtime_combo.addItem(tr("CPU only", lang), "cpu")
        self.runtime_combo.addItem(tr("CUDA GPU", lang), "cuda")
        runtime_index = self.runtime_combo.findData(normalize_device_preference(params.get("runtime_device", "auto")))
        self.runtime_combo.setCurrentIndex(runtime_index if runtime_index >= 0 else 0)
        form.addRow(QLabel(tr("Default Runtime Device:", lang)), self.runtime_combo)

        runtime_note = QLabel(
            tr(
                "Runtime device here is the default for built-in 2D/STL models and other internal Torch tasks. Custom extensions use the Python executable and commands configured in Advanced Extensions.",
                lang,
            )
        )
        runtime_note.setWordWrap(True)
        runtime_note.setObjectName("mutedLabel")
        form.addRow(QLabel(""), runtime_note)

        layout.addWidget(group)
        layout.addStretch(1)

        buttons = QHBoxLayout()
        btn_ask_agent = QPushButton(tr("Ask Agent", lang))
        btn_ask_agent.setObjectName("generalSettingsAskAgentButton")
        btn_ask_agent.setToolTip(tr("Ask Agent about these settings. Current values are summarized without sending full command text.", lang))
        apply_semantic_button_style(btn_ask_agent, BUTTON_ROLE_NEUTRAL)
        btn_ask_agent.clicked.connect(self.request_agent_help)
        btn_save = QPushButton(tr("Save", lang))
        apply_semantic_button_style(btn_save, BUTTON_ROLE_COMMIT)
        btn_save.clicked.connect(self.accept_with_validation)
        btn_cancel = QPushButton(tr("Cancel", lang))
        apply_semantic_button_style(btn_cancel, BUTTON_ROLE_STOP)
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(btn_ask_agent)
        buttons.addStretch(1)
        buttons.addWidget(btn_save)
        buttons.addWidget(btn_cancel)
        layout.addLayout(buttons)

    def accept_with_validation(self):
        try:
            autosave = int(float(self.autosave_seconds.text()))
        except Exception:
            autosave = 0
        if autosave <= 0:
            QMessageBox.warning(self, tr("Invalid Settings", self.lang), tr("Autosave interval must be a positive number.", self.lang))
            return
        self.accept()

    def get_values(self):
        try:
            return {
                "language": self.language_combo.currentData() or "en",
                "theme": normalize_theme(self.theme_combo.currentData() or "dark"),
                "startup_behavior": self.startup_combo.currentData() or "start_center",
                "project_autosave_interval_sec": int(float(self.autosave_seconds.text())),
                "runtime_device": normalize_device_preference(self.runtime_combo.currentData() or "auto"),
            }
        except Exception:
            return None

    def request_agent_help(self):
        self.agent_requested.emit(self.get_agent_context())
        self.reject()

    def get_agent_context(self):
        return {
            "source_workbench": "general_settings",
            "project_type": "settings",
            "settings_scope": "general",
            "settings_question_focus": "Application language, startup behavior, autosave timing, and default runtime device.",
            "language": self.language_combo.currentData() or "en",
            "theme": normalize_theme(self.theme_combo.currentData() or "dark"),
            "startup_behavior": self.startup_combo.currentData() or "start_center",
            "project_autosave_interval_sec": self.autosave_seconds.text().strip(),
            "runtime_device": normalize_device_preference(self.runtime_combo.currentData() or "auto"),
            "validation_errors": _agent_error_summary([]),
        }


class ExportDialog(QDialog):
    def __init__(self, parent=None, lang="en", default_dir=""):
        super().__init__(parent)
        self.lang = lang
        self.default_dir = os.path.abspath(str(default_dir)) if default_dir else ""
        self.setWindowTitle(tr("Export Dataset", self.lang))
        self.resize(400, 150)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr("Export Format:", self.lang)))
        self.format_combo = NoWheelComboBox()
        self.format_combo.addItem(tr("Multimodal (Crops + JSONL)", self.lang), "multimodal")
        self.format_combo.addItem(tr("COCO (Standard)", self.lang), "coco")
        self.format_combo.addItem(tr("YOLO (Segmentation)", self.lang), "yolo")
        layout.addWidget(self.format_combo)
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText(tr("Select export directory...", self.lang))
        if self.default_dir:
            self.path_edit.setText(self.default_dir)
        layout.addWidget(QLabel(tr("Export Path:", self.lang)))
        browse_layout = QHBoxLayout()
        browse_layout.addWidget(self.path_edit)
        btn_browse = QPushButton(tr("Browse", self.lang))
        apply_semantic_button_style(btn_browse, BUTTON_ROLE_NEUTRAL)
        btn_browse.clicked.connect(self.browse)
        browse_layout.addWidget(btn_browse)
        layout.addLayout(browse_layout)
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton(tr("Export", self.lang))
        apply_semantic_button_style(btn_ok, BUTTON_ROLE_COMMIT)
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton(tr("Cancel", self.lang))
        apply_semantic_button_style(btn_cancel, BUTTON_ROLE_STOP)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
    def browse(self):
        start_dir = self.path_edit.text().strip() or self.default_dir
        if start_dir and not os.path.isdir(start_dir):
            start_dir = os.path.dirname(start_dir)
        d = QFileDialog.getExistingDirectory(self, tr("Select Directory", self.lang), start_dir)
        if d:
            self.path_edit.setText(d)
    def get_path(self): 
        return self.path_edit.text()
    def get_format(self): 
        return self.format_combo.currentData() or self.format_combo.currentText()


class BlinkEntryDialog(QDialog):
    def __init__(self, image_path, taxonomy, selected_part, roi_candidates, parent=None, lang="en", remembered_parent_map=None):
        super().__init__(parent)
        self.lang = lang
        self.current_theme = getattr(parent, "current_theme", "dark")
        self.remembered_parent_map = dict(remembered_parent_map or {})
        self.setWindowTitle(tr("Enter Child Expert Session", self.lang))
        self.setModal(True)
        self.resize(520, 220)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr("Image: {0}", self.lang).format(os.path.basename(image_path))))

        target_row = QHBoxLayout()
        target_row.addWidget(QLabel(tr("Target Part:", self.lang)))
        self.target_combo = NoWheelComboBox()
        for part in taxonomy:
            self.target_combo.addItem(tr(part, self.lang), part)
        selected_idx = self.target_combo.findData(selected_part)
        if selected_idx >= 0:
            self.target_combo.setCurrentIndex(selected_idx)
        target_row.addWidget(self.target_combo)
        layout.addLayout(target_row)

        roi_row = QHBoxLayout()
        roi_row.addWidget(QLabel(tr("Entry ROI:", self.lang)))
        self.roi_combo = NoWheelComboBox()
        for candidate in roi_candidates:
            source = candidate.get("source")
            if source == "manual":
                source_text = tr("Manual Box", self.lang)
            elif source == "vlm":
                source_text = tr("VLM Draft Box", self.lang)
            else:
                source_text = tr("Model Prediction Box", self.lang)
            label = f"{tr(candidate.get('part', 'ROI'), self.lang)} ({source_text})"
            self.roi_combo.addItem(label, candidate)
        roi_row.addWidget(self.roi_combo)
        layout.addLayout(roi_row)

        self.tip_label = QLabel(
            tr("Target Part is the child part you want to refine. Entry ROI is the parent/context region Blink will zoom into. This project remembers the parent/context ROI you chose for each target part, and later Blink entries reuse that remembered context.", self.lang)
        )
        self.tip_label.setWordWrap(True)
        layout.addWidget(self.tip_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons = buttons
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.set_theme(self.current_theme)
        layout.addWidget(buttons)

        self.target_combo.currentIndexChanged.connect(self._sync_preferred_roi)
        self._sync_preferred_roi(self.target_combo.currentIndex())

    def set_theme(self, theme):
        self.current_theme = theme
        apply_theme_dialog_button_box_style(
            getattr(self, "buttons", None),
            ok_role=BUTTON_ROLE_RUN,
            cancel_role=BUTTON_ROLE_STOP,
            theme=theme,
        )

    def _sync_preferred_roi(self, _index):
        target_part = self.target_combo.currentData() or self.target_combo.currentText()
        remembered_parent = self.remembered_parent_map.get(str(target_part or "").strip())
        for preferred_part in _blink_preferred_roi_parts(target_part, remembered_parent):
            for idx in range(self.roi_combo.count()):
                candidate = self.roi_combo.itemData(idx)
                if isinstance(candidate, dict) and candidate.get("part") == preferred_part:
                    self.roi_combo.setCurrentIndex(idx)
                    return

        self.roi_combo.setCurrentIndex(-1)

    def get_session_spec(self, image_path):
        focus_roi = self.roi_combo.currentData()
        if not isinstance(focus_roi, dict):
            return None

        target_part = self.target_combo.currentData() or self.target_combo.currentText().strip()
        if not target_part:
            return None

        return {
            "image_path": image_path,
            "target_part": target_part,
            "focus_roi": focus_roi,
        }


class LiteratureDescriptionDialog(QDialog):
    def __init__(
        self,
        *,
        db_path,
        context,
        image_path,
        current_part,
        taxon_hint,
        parent=None,
        lang="en",
    ):
        super().__init__(parent)
        self.lang = lang
        self.current_theme = getattr(parent, "current_theme", "dark")
        self.db_path = str(db_path or "")
        self.context = dict(context or {})
        self.image_path = str(image_path or "")
        self.current_part = str(current_part or "")
        self.taxon_hint = str(taxon_hint or "")
        self.records = []
        self.raw_records = []
        self.selected_record = None
        self.selected_raw_record = None
        self.action_mode = "replace"

        self.setWindowTitle(tr("Literature Trait Descriptions", self.lang))
        self.setModal(True)
        self.resize(980, 680)

        layout = QVBoxLayout(self)
        self.source_label = QLabel(self._source_summary_text())
        self.source_label.setWordWrap(True)
        self.source_label.setObjectName("mutedLabel")
        layout.addWidget(self.source_label)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel(tr("Search Part:", self.lang)))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(tr("pronotum / 前胸背板 / propodeum ...", self.lang))
        self.search_edit.setText(self.current_part)
        search_row.addWidget(self.search_edit, 1)
        self.btn_search = QPushButton(tr("Search", self.lang))
        self.btn_search.clicked.connect(self.refresh_records)
        search_row.addWidget(self.btn_search)
        layout.addLayout(search_row)

        raw_scope_row = QHBoxLayout()
        raw_scope_row.addWidget(QLabel(tr("Raw Search Scope:", self.lang)))
        self.raw_scope_combo = QComboBox()
        self.raw_scope_combo.addItem(tr("Current Taxon First", self.lang), "taxon")
        self.raw_scope_combo.addItem(tr("Whole Current PDF", self.lang), "pdf")
        self.raw_scope_combo.currentIndexChanged.connect(self.refresh_raw_records)
        raw_scope_row.addWidget(self.raw_scope_combo)
        raw_scope_row.addStretch()
        layout.addLayout(raw_scope_row)

        self.result_tabs = QTabWidget()
        self.table = QTableWidget(0, 7)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setHorizontalHeaderLabels(
            [
                tr("Taxon", self.lang),
                tr("Caste", self.lang),
                tr("Part", self.lang),
                tr("Pages", self.lang),
                tr("Conf.", self.lang),
                tr("Status", self.lang),
                tr("Description", self.lang),
            ]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.Stretch)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.result_tabs.addTab(self.table, tr("Structured Descriptions", self.lang))

        self.raw_table = QTableWidget(0, 6)
        self.raw_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.raw_table.setSelectionMode(QTableWidget.SingleSelection)
        self.raw_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.raw_table.setHorizontalHeaderLabels(
            [
                tr("Page", self.lang),
                tr("Block", self.lang),
                tr("Taxon", self.lang),
                tr("Role", self.lang),
                tr("Conf.", self.lang),
                tr("Text", self.lang),
            ]
        )
        raw_header = self.raw_table.horizontalHeader()
        raw_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        raw_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        raw_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        raw_header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        raw_header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        raw_header.setSectionResizeMode(5, QHeaderView.Stretch)
        self.raw_table.itemSelectionChanged.connect(self._on_raw_selection_changed)
        self.result_tabs.addTab(self.raw_table, tr("Raw Text Blocks", self.lang))
        self.result_tabs.currentChanged.connect(self._on_result_tab_changed)
        layout.addWidget(self.result_tabs, 1)

        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMinimumHeight(150)
        self.preview.setObjectName("LinkedDescriptionBox")
        layout.addWidget(self.preview)

        button_row = QHBoxLayout()
        self.btn_replace = QPushButton(tr("Replace Current Description", self.lang))
        self.btn_replace.clicked.connect(self.accept_replace)
        self.btn_append = QPushButton(tr("Append to Current Description", self.lang))
        self.btn_append.clicked.connect(self.accept_append)
        self.btn_close = QPushButton(tr("Close", self.lang))
        self.btn_close.clicked.connect(self.reject)
        button_row.addStretch()
        button_row.addWidget(self.btn_replace)
        button_row.addWidget(self.btn_append)
        button_row.addWidget(self.btn_close)
        layout.addLayout(button_row)

        self.search_edit.returnPressed.connect(self.refresh_records)
        self.set_theme(self.current_theme)
        self.refresh_records()

    def set_theme(self, theme):
        self.current_theme = theme
        apply_theme_button_style(getattr(self, "btn_search", None), BUTTON_ROLE_NEUTRAL, "", theme)
        apply_theme_button_style(getattr(self, "btn_replace", None), BUTTON_ROLE_COMMIT, "", theme)
        apply_theme_button_style(getattr(self, "btn_append", None), BUTTON_ROLE_NEUTRAL, "", theme)
        apply_theme_button_style(getattr(self, "btn_close", None), BUTTON_ROLE_STOP, "", theme)

    def refresh_records(self):
        self.records = query_literature_part_descriptions(
            self.db_path,
            context=self.context,
            current_part=self.current_part,
            search_text=self.search_edit.text(),
            taxon_hint=self.taxon_hint,
        )
        self.raw_records = query_literature_text_blocks(
            self.db_path,
            context=self.context,
            current_part=self.current_part,
            search_text=self.search_edit.text(),
            taxon_hint=self.taxon_hint,
            scope=self.raw_scope_combo.currentData() or "taxon",
        )
        self._populate_table()
        self._populate_raw_table()

    def refresh_raw_records(self):
        self.raw_records = query_literature_text_blocks(
            self.db_path,
            context=self.context,
            current_part=self.current_part,
            search_text=self.search_edit.text(),
            taxon_hint=self.taxon_hint,
            scope=self.raw_scope_combo.currentData() or "taxon",
        )
        self._populate_raw_table()

    def selected_description_text(self):
        if self._active_result_kind() == "raw":
            record = self.selected_raw_record or {}
            return str(record.get("text_content", "") or "").strip()
        record = self.selected_record or {}
        return str(record.get("description_text", "") or "").strip()

    def selected_source(self):
        if self._active_result_kind() == "raw":
            if not self.selected_raw_record:
                return {}
            return build_text_block_source(self.selected_raw_record, self.context)
        if not self.selected_record:
            return {}
        return build_description_source(self.selected_record, self.context)

    def accept_replace(self):
        if not self._has_active_selection():
            return
        self.action_mode = "replace"
        self.accept()

    def accept_append(self):
        if not self._has_active_selection():
            return
        self.action_mode = "append"
        self.accept()

    def _populate_table(self):
        self.table.setRowCount(0)
        self.selected_record = None
        self.preview.clear()
        for row_index, record in enumerate(self.records):
            self.table.insertRow(row_index)
            values = [
                record.get("taxon_name", ""),
                record.get("caste_or_stage", ""),
                f"{record.get('part_label', '')} / {record.get('part_key', '')}",
                ", ".join(str(page) for page in record.get("source_pages", []) or []),
                f"{float(record.get('confidence') or 0.0):.3f}",
                record.get("review_status", ""),
                self._short_text(record.get("description_text", "")),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value or ""))
                item.setData(Qt.UserRole, row_index)
                self.table.setItem(row_index, column, item)
        if self.records:
            self.table.selectRow(0)
        else:
            self._sync_action_buttons()
            self.preview.setPlainText(tr("No literature description matched the current image, taxon, and part search.", self.lang))

    def _populate_raw_table(self):
        self.raw_table.setRowCount(0)
        self.selected_raw_record = None
        for row_index, record in enumerate(self.raw_records):
            self.raw_table.insertRow(row_index)
            values = [
                record.get("page_number", ""),
                record.get("block_ref", ""),
                record.get("llm_taxon_name", ""),
                record.get("llm_role", "") or record.get("section_hint", "") or record.get("text_type", ""),
                f"{float(record.get('llm_confidence') or 0.0):.3f}",
                self._short_text(record.get("text_content", "")),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value or ""))
                item.setData(Qt.UserRole, row_index)
                self.raw_table.setItem(row_index, column, item)
        if self.raw_records:
            self.raw_table.selectRow(0)
        else:
            self._sync_action_buttons()
            if self._active_result_kind() == "raw":
                self.preview.setPlainText(tr("No raw PDF text block matched the current search. Try Whole Current PDF or broader terms.", self.lang))

    def _on_selection_changed(self):
        selected = self.table.selectedItems()
        if not selected:
            self.selected_record = None
            self.preview.clear()
            self._sync_action_buttons()
            return
        row_index = selected[0].data(Qt.UserRole)
        try:
            self.selected_record = self.records[int(row_index)]
        except Exception:
            self.selected_record = None
        self._sync_preview()
        self._sync_action_buttons()

    def _on_raw_selection_changed(self):
        selected = self.raw_table.selectedItems()
        if not selected:
            self.selected_raw_record = None
            if self._active_result_kind() == "raw":
                self.preview.clear()
            self._sync_action_buttons()
            return
        row_index = selected[0].data(Qt.UserRole)
        try:
            self.selected_raw_record = self.raw_records[int(row_index)]
        except Exception:
            self.selected_raw_record = None
        if self._active_result_kind() == "raw":
            self._sync_preview()
        self._sync_action_buttons()

    def _sync_preview(self):
        if self._active_result_kind() == "raw":
            self._sync_raw_preview()
            return
        record = self.selected_record or {}
        if not record:
            self.preview.clear()
            return
        pages = ", ".join(str(page) for page in record.get("source_pages", []) or [])
        refs = ", ".join(str(ref) for ref in record.get("source_block_refs", []) or [])
        meta = (
            f"{record.get('taxon_name', '')} | {record.get('caste_or_stage', '')} | "
            f"{record.get('part_label', '')} / {record.get('part_key', '')}\n"
            f"{tr('Source PDF', self.lang)}: {record.get('file_name') or self.context.get('pdf_file') or ''}\n"
            f"{tr('Pages', self.lang)}: {pages} | refs: {refs} | "
            f"conf={float(record.get('confidence') or 0.0):.3f} | {record.get('review_status', '')}"
        )
        self.preview.setPlainText(f"{meta}\n\n{record.get('description_text', '')}")

    def _sync_raw_preview(self):
        record = self.selected_raw_record or {}
        if not record:
            self.preview.clear()
            return
        meta = (
            f"{tr('Source PDF', self.lang)}: {record.get('file_name') or self.context.get('pdf_file') or ''}\n"
            f"{tr('Page', self.lang)}: {record.get('page_number', '')} | "
            f"{tr('Block', self.lang)}: {record.get('block_ref', '')} | "
            f"{tr('Role', self.lang)}: {record.get('llm_role', '') or record.get('section_hint', '') or record.get('text_type', '')} | "
            f"conf={float(record.get('llm_confidence') or 0.0):.3f}\n"
            f"{tr('Taxon', self.lang)}: {record.get('llm_taxon_name', '') or self.context.get('species_candidate') or ''}"
        )
        self.preview.setPlainText(f"{meta}\n\n{record.get('text_content', '')}")

    def _sync_action_buttons(self):
        enabled = bool(self.selected_raw_record) if self._active_result_kind() == "raw" else bool(self.selected_record)
        self.btn_replace.setEnabled(enabled)
        self.btn_append.setEnabled(enabled)

    def _on_result_tab_changed(self, _index):
        self._sync_preview()
        self._sync_action_buttons()

    def _has_active_selection(self):
        return bool(self.selected_raw_record) if self._active_result_kind() == "raw" else bool(self.selected_record)

    def _active_result_kind(self):
        if getattr(self, "result_tabs", None) is not None and self.result_tabs.currentWidget() == getattr(self, "raw_table", None):
            return "raw"
        return "structured"

    def _source_summary_text(self):
        pieces = [
            f"{tr('Image', self.lang)}: {os.path.basename(self.image_path)}",
            f"{tr('Source Mode', self.lang)}: {self._source_mode_label()}",
            f"{tr('PDF', self.lang)}: {self.context.get('pdf_file') or tr('Unknown', self.lang)}",
            f"{tr('Taxon', self.lang)}: {self.context.get('species_candidate') or self.taxon_hint or tr('Unknown', self.lang)}",
            f"{tr('Current Part', self.lang)}: {self.current_part or tr('Unknown', self.lang)}",
        ]
        summary = " | ".join(pieces)
        if self.context.get("link_mode") == "taxon_match_not_image_provenance":
            summary = f"{summary}\n{tr('This image is not linked to the selected PDF figure. Descriptions are matched by the current image taxon name only.', self.lang)}"
        return summary

    def _source_mode_label(self):
        if self.context.get("link_mode") == "taxon_match_not_image_provenance":
            return tr("Same-taxon literature reference", self.lang)
        return tr("Current image PDF source", self.lang)

    @staticmethod
    def _short_text(value, limit=160):
        text = " ".join(str(value or "").split())
        if len(text) <= limit:
            return text
        return text[: limit - 3] + "..."


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
        self.project = ProjectManager()
        self.project.set_known_relocated_roots(self.config.get("known_relocated_roots", []))
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
        self.start_console_pdf_label, self.start_console_pdf_value = self._build_project_console_row(
            grid, 3, "startConsolePdfValue"
        )
        self.start_console_agent_label, self.start_console_agent_value = self._build_project_console_row(
            grid, 4, "startConsoleAgentValue"
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
        self.start_console_pdf_label.setText(tr("PDF evidence", self.current_lang))
        self.start_console_agent_label.setText("Ant-Code")

        self.start_console_workflow_value.setText(self._agent_current_workflow_label())
        project_summary, project_detail = self._start_console_project_summary()
        image_summary, image_detail = self._start_console_image_summary()
        pdf_summary, pdf_detail = self._start_console_pdf_summary()
        agent_summary = self._start_console_agent_status()
        summary = self._start_console_collapsed_summary(project_summary, agent_summary)
        self.start_console_summary.setText(summary)
        self.start_console_summary.setToolTip(f"{project_summary}\n{agent_summary}".strip())
        self.start_console_project_value.setText(project_summary)
        self.start_console_images_value.setText(image_summary)
        self.start_console_pdf_value.setText(pdf_summary)
        self.start_console_agent_value.setText(agent_summary)
        self.start_console_workflow_value.setToolTip(self._agent_current_workflow_label())
        self.start_console_project_value.setToolTip(project_detail)
        self.start_console_images_value.setToolTip(image_detail)
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

    def _start_console_pdf_summary(self):
        context_paths = [
            os.path.join(REPO_ROOT, "ANTCODE.md"),
            os.path.join(REPO_ROOT, "TaxaMask使用手册.md"),
            os.path.join(REPO_ROOT, "LLM_CONTEXT_DETAILED.md"),
        ]
        missing_paths = [path for path in context_paths if not os.path.exists(path)]
        if missing_paths:
            return tr("PDF literature workflow docs missing", self.current_lang), "\n".join(missing_paths)
        candidates = 0
        for image_path in (self.project.project_data or {}).get("images", []):
            provenance = self.project.get_image_provenance(image_path)
            if self._is_pdf_candidate_provenance(provenance):
                entry = (self.project.project_data or {}).get("labels", {}).get(image_path, {})
                if not isinstance(entry, dict) or entry.get("status") != "labeled":
                    candidates += 1
        summary = tr("PDF literature workflow ready; {0} review candidate(s)", self.current_lang).format(candidates)
        detail = f"{summary}\n" + "\n".join(context_paths)
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
        if kind == "image":
            return tr("2D/STL Morphology Workflow", self.current_lang)
        return tr("Start Center", self.current_lang)

    def _agent_current_project_label(self):
        if getattr(self, "active_project_kind", "start") == "image":
            path = self._active_recent_project_path() or getattr(self.project, "current_project_path", "") or ""
        else:
            path = self.config.get("last_project_path", "") or ""
        return path if path else tr("No active project", self.current_lang)

    AGENT_CONTEXT_TEXT_LIMIT = 320
    AGENT_CONTEXT_LOG_LINES = 6
    AGENT_CONTEXT_LOG_LINE_LIMIT = 160
    AGENT_CONTEXT_TOTAL_LIMIT = 3600

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
            "active_specimen_id",
            "active_image_path",
            "active_label_role",
            "active_slice_axis",
            "active_slice_position",
            "active_label_shape_zyx",
            "selected_part",
            "display_mode",
            "train_ready_status",
            "train_ready_reasons",
            "screener_profile",
            "figure_profile",
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
            "validation_errors",
            "diagnostic_route",
            "diagnostic_focus",
            "health_check_summary",
            "llm_context_refs",
            "source_code_refs",
            "artifact_hints",
            "safety_notes",
            "suggested_agent_action",
            "agent_route_source",
            "recent_log_excerpt",
        )
        compact = {}
        for key in allowed_keys:
            value = (context or {}).get(key)
            if not value:
                continue
            limit = self.AGENT_CONTEXT_TEXT_LIMIT
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
        if self.current_lang != "zh":
            return (
                "Please take over one TaxaMask PDF literature-processing task as a staged guide. "
                "This workflow is for taxonomy researchers across different taxa; do not assume the user studies ants, "
                "and do not assume the current screening or figure-extraction profiles are already suitable.\n\n"
                "First read and follow these local public context documents:\n"
                "- ANTCODE.md\n"
                "- TaxaMask使用手册.md\n"
                "- LLM_CONTEXT_DETAILED.md\n\n"
                "Current context:\n"
                f"- Current project: {project_hint}\n"
                f"- PDF status: {pdf_summary}\n"
                "- PDF screening depends on a text LLM key/model; multimodal figure review also needs a usable vision model configuration.\n\n"
                "Do not dump the whole workflow at once. Move through four stages and handle only the current stage in each turn, asking at most three questions:\n"
                "1. Check key/model readiness.\n"
                "2. Adapt the target taxon and PDF screening criteria.\n"
                "3. Adapt figure/caption processing and multimodal review requirements.\n"
                "4. Run the workflow and explain output locations plus review/import boundaries.\n\n"
                "Prefer short requirement-confirmation questions or concise options. "
                "Start at stage 1 only: confirm whether the text LLM key, base URL, model, and API protocol are configured locally for the PDF tools or runtime environment. "
                "If multimodal review is needed, also confirm the vision model configuration. Do not ask the user to paste real API keys into chat. "
                "After stage 1 is resolved, continue to the next stage without expanding later configuration early."
            )
        return (
            "请按 TaxaMask 的 PDF 文献处理流程作为分阶段向导接管一次任务。"
            "这个流程面向各种分类学研究者，不要默认用户研究蚂蚁，也不要默认当前筛选配置或图文提取配置已经合适。\n\n"
            "请先读取并遵守这些公开上下文文档：\n"
            "- ANTCODE.md\n"
            "- TaxaMask使用手册.md\n"
            "- LLM_CONTEXT_DETAILED.md\n\n"
            "当前现场：\n"
            f"- 当前项目：{project_hint}\n"
            f"- PDF 状态：{pdf_summary}\n"
            "- PDF 筛选依赖文本 LLM key/model；启用多模态图文复核时还需要可用的视觉模型配置。\n\n"
            "请不要一次性输出全流程长说明。请按四个阶段推进，每轮只处理当前阶段，最多问 3 个问题：\n"
            "1. key/model 就绪检查。\n"
            "2. 目标类群与 PDF 筛选条件适配。\n"
            "3. figure/caption 数据处理与图文复核条件适配。\n"
            "4. 跑通流程、说明产物位置和复核/导入边界。\n\n"
            "请优先使用需求确认式交互：给我简短选项或短问题让我确认，不要用长段说明替代确认。"
            "现在先停在第 1 阶段：只确认文本 LLM key、base URL、model、API 协议是否已在本地 PDF 工具或运行环境配置好；"
            "如果要多模态复核，再确认视觉模型配置。不要要求我在聊天里粘贴真实 key。"
            "完成第 1 阶段后，再进入下一阶段，不要提前展开后面复杂配置。"
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
        if not payload:
            payload = self._collect_image_workbench_agent_context()
        payload = self._compact_agent_context(payload)
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
        self.enter_image_workflow()

    def _open_model_settings_from_agent(self, workflow):
        self.open_stl_model_settings()

    def enter_image_workflow(self):
        self.active_project_kind = "image"
        self._refresh_project_bound_views()
        self.tabs.setCurrentWidget(self.workbench_widget)
        self.ensure_2d_stl_models_preloaded()
        self.log(tr("Opened 2D/STL workflow.", self.current_lang))

    def _default_outputs_root(self):
        return os.path.abspath(os.path.join(REPO_ROOT, DEFAULT_OUTPUTS_DIR_NAME))

    def _ensure_default_output_subdir(self, *parts):
        path = os.path.join(self._default_outputs_root(), *parts)
        os.makedirs(path, exist_ok=True)
        return path

    def _default_2d_stl_projects_root(self):
        return self._ensure_default_output_subdir(DEFAULT_2D_STL_PROJECTS_DIR_NAME)

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
        try:
            self.open_project_path(last_project)
        except Exception:
            runtime_log_exception("open_last_project_failed", *sys.exc_info())
            self.config.set("last_project_path", "")
            self.config.save()
            self.log(tr("Last project could not be opened and was cleared from startup: {0}", self.current_lang).format(last_project))
            QMessageBox.warning(
                self,
                tr("Open Last Project", self.current_lang),
                tr("The last project could not be opened, so TaxaMask returned to the start screen.\n\n{0}", self.current_lang).format(last_project),
            )

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
        if active_kind == "image":
            if source_kind == "stl":
                return getattr(self.stl_project, "current_project_path", None) or getattr(self, "active_project_entry_path", "")
            return getattr(self.project, "current_project_path", None) or getattr(self, "active_project_entry_path", "")
        return ""

    def _shutdown_background_workers(self):
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
            self.project.save_project(force=force)
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
            for widget in (self.workbench_widget, self.blink_lab, self.pdf_widget):
                self._remove_tab_if_present(widget)
            self._ensure_tab_visible(self.start_center_widget, tr("Start Center", self.current_lang))
            self.tabs.setCurrentWidget(self.start_center_widget)
            return
        self._remove_tab_if_present(self.start_center_widget)
        self._remove_tab_if_present(self.blink_lab)
        self._ensure_tab_visible(self.workbench_widget, tr("Labeling Workbench", self.current_lang))
        if self.tabs.currentWidget() is None:
            self.tabs.setCurrentWidget(self.workbench_widget)

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

    def _is_2d_sqlite_project_manifest_payload(self, payload):
        return self._is_sqlite_project_manifest_payload(payload)

    def _is_legacy_2d_json_project_payload(self, payload):
        if not isinstance(payload, dict):
            return False
        if self._is_sqlite_project_manifest_payload(payload):
            return False
        if (
            payload.get("schema_version") == STL_PROJECT_SCHEMA_VERSION
            or payload.get("project_type") == STL_PROJECT_TYPE
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
        if filename.endswith(".taxamask.sqlite"):
            candidates.append(os.path.join(directory, f"{filename[:-len('.taxamask.sqlite')]}.sqlite_manifest.json"))
        for name in os.listdir(directory) if os.path.isdir(directory) else []:
            if name.endswith(".sqlite_manifest.json"):
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
        return os.path.basename(str(path or "")).endswith(".taxamask.sqlite")

    def _active_sqlite_project_manager(self):
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
        self._flush_pending_project_save(force=True, defer_for_navigation=False)
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
        workflow_menu.addAction(tr("Import STL Rendered Views to Labeling Workbench", self.current_lang), self.import_stl_rendered_views_action)
        settings_menu = menubar.addMenu(tr("Settings", self.current_lang))
        settings_menu.addAction(tr("General Settings", self.current_lang), self.open_general_settings)
        settings_menu.addAction(tr("2D/STL Model Settings", self.current_lang), self.open_stl_model_settings)

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
            tr("TaxaMask Projects (*.json);;All Files (*)", self.current_lang),
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
                        "This is a SQLite database file, but TaxaMask could not find the matching project entry file. Please open the project entry file next to it instead:\n\n2D: *.sqlite_manifest.json\n\nSelected database:\n{0}",
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
        if self._is_stl_project_file(f):
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
            return "missing_file", tr("Expert file missing", self.current_lang), has_appointed
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
        scope = self._choose_clear_ai_scope()
        if not scope:
            return
        paths = list(scope.get("paths", []) or [])
        expected_count = int(scope.get("count", 0) or 0)
        scope_label = str(scope.get("label", "") or tr("All project images", self.current_lang))
        if expected_count <= 0 or not paths:
            self.log(tr("No AI labels found in the selected scope.", self.current_lang))
            return
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
        self.btn_del_locator.setText(tr("Del", self.current_lang))
        self.btn_del_locator.setToolTip(tr("Delete the selected locator model file from disk.", self.current_lang))
        self.btn_note_locator.setText(tr("Note", self.current_lang))
        self.btn_note_locator.setToolTip(tr("Edit the selected locator model display note.", self.current_lang))
        self.btn_del_segmenter.setText(tr("Del", self.current_lang))
        self.btn_del_segmenter.setToolTip(tr("Delete the selected segmenter model file from disk.", self.current_lang))
        self.btn_note_segmenter.setText(tr("Note", self.current_lang))
        self.btn_note_segmenter.setToolTip(tr("Edit the selected segmenter model display note.", self.current_lang))
        for index in range(self.tabs.count()):
            widget = self.tabs.widget(index)
            if widget is self.workbench_widget:
                self.tabs.setTabText(index, tr("Labeling Workbench", self.current_lang))
            elif widget is self.blink_lab:
                self.tabs.setTabText(index, tr("Child Expert Session", self.current_lang))
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

    def change_language(self, lang):
        self.current_lang = lang
        self.config.set("language", lang)
        self.pdf_widget.change_language(lang)
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

        for widget in [self.pdf_widget, self.blink_lab, self.canvas]:
            if hasattr(widget, "set_theme"):
                widget.set_theme(theme)

        if hasattr(self, "route_settings_panel"):
            self.route_settings_panel.set_theme(theme)

        self.update_widget_themes()
        self.update_button_themes()
        self.log(f"Theme: {tr('Dark Mode', self.current_lang)}")

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
            apply_theme_button_style(self.btn_del_locator, BUTTON_ROLE_DESTRUCTIVE, "", self.current_theme)
        if hasattr(self, "btn_note_locator"):
            apply_theme_button_style(self.btn_note_locator, BUTTON_ROLE_NEUTRAL, "", self.current_theme)
        if hasattr(self, "btn_del_segmenter"):
            apply_theme_button_style(self.btn_del_segmenter, BUTTON_ROLE_DESTRUCTIVE, "", self.current_theme)
        if hasattr(self, "btn_note_segmenter"):
            apply_theme_button_style(self.btn_note_segmenter, BUTTON_ROLE_NEUTRAL, "", self.current_theme)
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
        fs, _ = QFileDialog.getOpenFileNames(self, tr("Select Images", self.current_lang), "", "Images (*.png *.jpg *.jpeg)")
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
        if not re.search(r"__(?:panel|crop)_\d{3}(?:_\d+)?\.(?:png|jpe?g)$", base_name, re.IGNORECASE):
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

            def add_group_header(group_key, text, count):
                collapsed = bool(self.image_list_group_collapsed.get(group_key, False))
                arrow = "▸" if collapsed else "▾"
                item = QListWidgetItem(f"{arrow} {text} ({count})")
                item.setData(Qt.UserRole, None)
                item.setData(Qt.UserRole + 1, group_key)
                item.setFlags((item.flags() | Qt.ItemIsEnabled | Qt.ItemIsSelectable) & ~Qt.ItemIsEditable)
                item.setForeground(QColor("#8EA0A8"))
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
                    item.setForeground(QColor("#8FBC8F")) # DarkSeaGreen
                elif is_split_crop:
                    item.setForeground(QColor("#AAB4C2"))
                else:
                    item.setForeground(QColor("#CCCCCC")) # Grey

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
        if is_labeled:
            item.setForeground(QColor("#8FBC8F"))
        elif is_split_crop:
            item.setForeground(QColor("#AAB4C2"))
        else:
            item.setForeground(QColor("#CCCCCC"))

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
        self._refresh_training_scope_combo()
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
            if not re.search(r"__(?:panel|crop)_\d{3}(?:_\d+)?\.(?:png|jpe?g)$", base_name, re.IGNORECASE):
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
        self.vlm_preannotation_target_parts = list(target_parts)
        self.vlm_preannotation_artifacts_dir = self._vlm_preannotation_artifacts_dir()
        self.vlm_preannotation_api_config = dict(api_config)
        self.vlm_preannotation_prompt_profile = self._current_vlm_prompt_profile()
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
        self._set_vlm_progress_ui(
            int(int(getattr(self, "vlm_preannotation_completed_steps", 0) or 0) / max(1, int(getattr(self, "vlm_preannotation_total_steps", 1) or 1)) * 100),
            "image",
        )
        self.vlm_preannotation_thread = VlmPreannotationThread(
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
        self.vlm_preannotation_thread.log_signal.connect(self.log)
        self.vlm_preannotation_thread.image_result_signal.connect(self._on_vlm_preannotation_image_result)
        self.vlm_preannotation_thread.progress_signal.connect(self._on_vlm_preannotation_thread_step)
        self.vlm_preannotation_thread.error_signal.connect(self._on_vlm_preannotation_error)
        self.vlm_preannotation_thread.finished_signal.connect(self._on_vlm_preannotation_finished)
        self.vlm_preannotation_thread.start()
        return self.vlm_preannotation_thread

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
        if not image_path or result.get("status") == "failed":
            self._log_vlm_part_coverage(result)
            self.log(tr("VLM first-mile preannotation failed: {0}", self.current_lang).format(result.get("error", "")))
            self._complete_current_vlm_image_steps("failed")
            self.vlm_preannotation_records.append(result)
            if image_path:
                self._record_sqlite_vlm_image_result(
                    image_path,
                    result,
                    "failed",
                    box_count=0,
                    error_message=str(result.get("error", "") or ""),
                )
            self._mark_current_vlm_image_done("failed")
            return
        candidates = list(result.get("candidates", []) or []) if isinstance(result, dict) else []
        if not candidates:
            self._log_vlm_part_coverage(result)
            self.log(tr("VLM first-mile preannotation returned no usable boxes.", self.current_lang))
            self._complete_current_vlm_image_steps("no_candidates")
            self.vlm_preannotation_records.append(result)
            self._record_sqlite_vlm_image_result(image_path, result, "no_candidates", box_count=0)
            self._mark_current_vlm_image_done("no_candidates")
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
            self._advance_vlm_progress("write")
            self._advance_vlm_progress("sam")
            self._advance_vlm_progress("report")
            self._mark_current_vlm_image_done("done")
            self._log_vlm_part_coverage(result)
            self.log(
                tr(
                    "VLM preannotation saved {0} draft(s): {1} SAM polygon(s), {2} box-only draft(s), skipped {3}. Report: {4}",
                    self.current_lang,
                ).format(saved, polygon_count, box_only_count, skipped, report_path)
            )
        except Exception as exc:
            self._complete_current_vlm_image_steps("failed")
            failed = dict(result)
            failed["status"] = "failed"
            failed["error"] = str(exc)
            self.vlm_preannotation_records.append(failed)
            self._record_sqlite_vlm_image_result(image_path, failed, "failed", box_count=0, error_message=str(exc))
            self._mark_current_vlm_image_done("failed")
            self._on_vlm_preannotation_error(str(exc))

    def _mark_current_vlm_image_done(self, step_name):
        total_images = max(1, int(getattr(self, "vlm_preannotation_total_images", 1) or 1))
        self.vlm_preannotation_completed_images = min(
            total_images,
            int(getattr(self, "vlm_preannotation_completed_images", 0) or 0) + 1,
        )
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
        notice_label = QLabel(
            tr(
                "Active API request(s) may already have been sent, but no more queued images will be processed. This helps avoid unintended large API bills.",
                self.current_lang,
            )
        )
        notice_label.setWordWrap(True)
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

    def _advance_vlm_progress(self, step_name):
        total = max(1, int(getattr(self, "vlm_preannotation_total_steps", 1) or 1))
        completed = min(total, int(getattr(self, "vlm_preannotation_completed_steps", 0) or 0) + 1)
        self.vlm_preannotation_completed_steps = completed
        current_completed = int(getattr(self, "vlm_preannotation_current_image_steps_completed", 0) or 0)
        self.vlm_preannotation_current_image_steps_completed = min(6, current_completed + 1)
        self._set_vlm_progress_ui(int(completed / total * 100), step_name)
        self.log(tr("VLM batch progress: {0}/{1} steps ({2}).", self.current_lang).format(completed, total, step_name))

    def _on_vlm_preannotation_thread_step(self, _completed, _total, step_name):
        self._advance_vlm_progress(step_name)

    def _complete_current_vlm_image_steps(self, step_name):
        current_completed = int(getattr(self, "vlm_preannotation_current_image_steps_completed", 0) or 0)
        for _ in range(max(0, 6 - current_completed)):
            self._advance_vlm_progress(step_name)

    def _finish_vlm_preannotation_run(self):
        records = list(getattr(self, "vlm_preannotation_records", []) or [])
        artifacts_dir = getattr(self, "vlm_preannotation_artifacts_dir", self._vlm_preannotation_artifacts_dir())
        run_id = getattr(self, "vlm_preannotation_run_id", time.strftime("%Y%m%d_%H%M%S"))
        cancelled = bool(getattr(self, "vlm_preannotation_cancel_requested", False))
        cancelled_queued = int(getattr(self, "vlm_preannotation_cancelled_queued_images", 0) or 0)
        report_path = os.path.join(artifacts_dir, f"vlm_preannotation_summary_{run_id}.json")
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

    def _on_vlm_preannotation_finished(self):
        if not getattr(self, "vlm_preannotation_run_active", False):
            return
        sender_thread = self.sender()
        if sender_thread is not None:
            self.vlm_preannotation_threads = [
                thread
                for thread in (getattr(self, "vlm_preannotation_threads", []) or [])
                if thread is not sender_thread
            ]
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
        runtime_log_exception("uncaught_exception", t, v, tb)
        err = "".join(traceback.format_exception(t, v, tb))
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
