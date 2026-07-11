import os
import re

from PIL import Image as PILImage
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

try:
    from AntSleap.app_runtime import runtime_log_event
    from AntSleap.core.literature_descriptions import (
        candidate_literature_db_paths,
        default_literature_db_path,
        infer_literature_db_path_from_artifact_image,
        resolve_literature_context,
    )
    from AntSleap.core.model_profiles import DEFAULT_VLM_IMAGE_GROUP
    from AntSleap.core.part_tree import build_part_tree_groups
    from AntSleap.core.panel_splitter import detect_panel_crops
    from AntSleap.ui.cropper import ImageCropper
    from AntSleap.ui.main_window_dialog_support import (
        BACKGROUND_IMAGE_IMPORT_THRESHOLD,
        LARGE_PROJECT_OPEN_LIGHTWEIGHT_THRESHOLD,
    )
    from AntSleap.ui.main_window_dialogs import LiteratureDescriptionDialog
    from AntSleap.ui.main_window_i18n import tr
    from AntSleap.ui.main_window_widgets import NoWheelComboBox
    from AntSleap.ui.main_window_workers import ImageImportThread
    from AntSleap.ui.style import (
        BUTTON_ROLE_COMMIT,
        BUTTON_ROLE_DESTRUCTIVE,
        BUTTON_ROLE_STOP,
        apply_semantic_button_style,
        get_theme_config,
        themed_yes_no_question,
    )
except ImportError:
    from app_runtime import runtime_log_event
    from core.literature_descriptions import (
        candidate_literature_db_paths,
        default_literature_db_path,
        infer_literature_db_path_from_artifact_image,
        resolve_literature_context,
    )
    from core.model_profiles import DEFAULT_VLM_IMAGE_GROUP
    from core.part_tree import build_part_tree_groups
    from core.panel_splitter import detect_panel_crops
    from ui.cropper import ImageCropper
    from ui.main_window_dialog_support import BACKGROUND_IMAGE_IMPORT_THRESHOLD, LARGE_PROJECT_OPEN_LIGHTWEIGHT_THRESHOLD
    from ui.main_window_dialogs import LiteratureDescriptionDialog
    from ui.main_window_i18n import tr
    from ui.main_window_widgets import NoWheelComboBox
    from ui.main_window_workers import ImageImportThread
    from ui.style import (
        BUTTON_ROLE_COMMIT,
        BUTTON_ROLE_DESTRUCTIVE,
        BUTTON_ROLE_STOP,
        apply_semantic_button_style,
        get_theme_config,
        themed_yes_no_question,
    )


PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(PACKAGE_DIR)

__all__ = [name for name in globals() if not name.startswith("__")]
