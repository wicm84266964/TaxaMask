import os

from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)

try:
    from AntSleap.core.agent_context_routes import enrich_agent_context
    from AntSleap.core.blink_training_strategy import (
        DEFAULT_BLINK_TRAINING_STRATEGY,
        sanitize_blink_training_strategy,
    )
    from AntSleap.core.config import ConfigManager
    from AntSleap.core.database import MultiModalDB
    from AntSleap.core.engine import AntEngine
    from AntSleap.core.external_backend import (
        BUILTIN_BACKEND_ID,
        sanitize_external_backend_config,
    )
    from AntSleap.core.model_profiles import DEFAULT_CHILD_AUTO_SHRINK_STEPS
    from AntSleap.core.project import ProjectManager
    from AntSleap.core.runtime_device import normalize_device_preference
    from AntSleap.core.stl_project import StlRenderedProjectManager
    from AntSleap.core.tif_project import TifProjectManager
    from AntSleap.core.window_geometry import compute_centered_window_geometry
    from AntSleap.ui.blink_lab import BlinkLabWidget
    from AntSleap.ui.canvas import AnnotationCanvas
    from AntSleap.ui.main_window_dialog_support import (
        APP_ICON_FALLBACK_PATH,
        APP_ICON_PATH,
        EXPERIMENTAL_TIF_WORKFLOW_ENV,
        _active_profile_from_manager,
        _env_flag_enabled,
    )
    from AntSleap.ui.main_window_i18n import tr
    from AntSleap.ui.main_window_widgets import ImageGroupListWidget, NoWheelComboBox
    from AntSleap.ui.route_management_panel import RouteManagementPanel
    from AntSleap.ui.style import (
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
        apply_semantic_button_style,
        apply_surface_role,
        normalize_theme,
    )
    from AntSleap.ui.taxamask_agent_panel import TaxaMaskAgentPanel
except ImportError:
    from core.agent_context_routes import enrich_agent_context
    from core.blink_training_strategy import DEFAULT_BLINK_TRAINING_STRATEGY, sanitize_blink_training_strategy
    from core.config import ConfigManager
    from core.database import MultiModalDB
    from core.engine import AntEngine
    from core.external_backend import BUILTIN_BACKEND_ID, sanitize_external_backend_config
    from core.model_profiles import DEFAULT_CHILD_AUTO_SHRINK_STEPS
    from core.project import ProjectManager
    from core.runtime_device import normalize_device_preference
    from core.stl_project import StlRenderedProjectManager
    from core.tif_project import TifProjectManager
    from core.window_geometry import compute_centered_window_geometry
    from ui.blink_lab import BlinkLabWidget
    from ui.canvas import AnnotationCanvas
    from ui.main_window_dialog_support import (
        APP_ICON_FALLBACK_PATH,
        APP_ICON_PATH,
        EXPERIMENTAL_TIF_WORKFLOW_ENV,
        _active_profile_from_manager,
        _env_flag_enabled,
    )
    from ui.main_window_i18n import tr
    from ui.main_window_widgets import ImageGroupListWidget, NoWheelComboBox
    from ui.route_management_panel import RouteManagementPanel
    from ui.style import (
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
        apply_semantic_button_style,
        apply_surface_role,
        normalize_theme,
    )
    from ui.taxamask_agent_panel import TaxaMaskAgentPanel


PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(PACKAGE_DIR)

__all__ = [name for name in globals() if not name.startswith("__")]
