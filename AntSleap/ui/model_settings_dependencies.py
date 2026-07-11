import time
from fractions import Fraction

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QTextEdit,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

try:
    from AntSleap.core.blink_training_strategy import (
        BLINK_STRATEGY_FULL_INSIDE_RANDOM,
        BLINK_STRATEGY_TRIVIEW_RANDOM,
        BLINK_STRATEGY_TWO_STAGE_FULL_THEN_INSIDE,
        DEFAULT_BLINK_TRAINING_STRATEGY,
        blink_training_strategy_label,
        blink_training_strategy_note,
        sanitize_blink_training_strategy,
    )
    from AntSleap.core.external_backend import (
        BUILTIN_BACKEND_ID,
        EXTERNAL_BACKEND_ID,
        sanitize_external_backend_config,
    )
    from AntSleap.core.model_profiles import (
        CHILD_BACKEND_EXTERNAL,
        CHILD_BACKEND_HEATMAP,
        CHILD_BACKEND_VIT_B,
        DEFAULT_CHILD_AUTO_SHRINK_STEPS,
        DEFAULT_EXTERNAL_BLINK_BACKEND,
        DEFAULT_HEATMAP_BLINK_PARAMS,
        DEFAULT_MODEL_PROFILE_ID,
        PARENT_BACKEND_BUILTIN,
        PARENT_BACKEND_EXTERNAL,
        sanitize_model_profiles,
    )
    from AntSleap.core.runtime_device import normalize_device_preference
    from AntSleap.core.vlm_preannotation import (
        DEFAULT_VLM_PROMPT_PROFILE_ID,
        default_vlm_prompt_profile,
        sanitize_vlm_prompt_profile,
    )
    from AntSleap.ui.main_window_dialog_support import (
        _agent_command_has_contract,
        _agent_error_summary,
        _agent_yes_no,
        _child_backend_label,
        _format_backend_contract_error,
        _parent_backend_label,
        _route_backend_from_child_backend,
        _route_backend_from_entry,
    )
    from AntSleap.ui.main_window_i18n import tr, ui_text
    from AntSleap.ui.main_window_widgets import NoWheelComboBox, NoWheelSpinBox
    from AntSleap.ui.style import (
        BUTTON_ROLE_COMMIT,
        BUTTON_ROLE_DESTRUCTIVE,
        BUTTON_ROLE_NEUTRAL,
        BUTTON_ROLE_STOP,
        SURFACE_ROLE_SUBTLE,
        apply_semantic_button_style,
        apply_surface_role,
        apply_theme_dialog_button_box_style,
        themed_yes_no_question,
    )
except ImportError:
    from core.blink_training_strategy import (
        BLINK_STRATEGY_FULL_INSIDE_RANDOM,
        BLINK_STRATEGY_TRIVIEW_RANDOM,
        BLINK_STRATEGY_TWO_STAGE_FULL_THEN_INSIDE,
        DEFAULT_BLINK_TRAINING_STRATEGY,
        blink_training_strategy_label,
        blink_training_strategy_note,
        sanitize_blink_training_strategy,
    )
    from core.external_backend import BUILTIN_BACKEND_ID, EXTERNAL_BACKEND_ID, sanitize_external_backend_config
    from core.model_profiles import (
        CHILD_BACKEND_EXTERNAL,
        CHILD_BACKEND_HEATMAP,
        CHILD_BACKEND_VIT_B,
        DEFAULT_CHILD_AUTO_SHRINK_STEPS,
        DEFAULT_EXTERNAL_BLINK_BACKEND,
        DEFAULT_HEATMAP_BLINK_PARAMS,
        DEFAULT_MODEL_PROFILE_ID,
        PARENT_BACKEND_BUILTIN,
        PARENT_BACKEND_EXTERNAL,
        sanitize_model_profiles,
    )
    from core.runtime_device import normalize_device_preference
    from core.vlm_preannotation import (
        DEFAULT_VLM_PROMPT_PROFILE_ID,
        default_vlm_prompt_profile,
        sanitize_vlm_prompt_profile,
    )
    from ui.main_window_dialog_support import (
        _agent_command_has_contract,
        _agent_error_summary,
        _agent_yes_no,
        _child_backend_label,
        _format_backend_contract_error,
        _parent_backend_label,
        _route_backend_from_child_backend,
        _route_backend_from_entry,
    )
    from ui.main_window_i18n import tr, ui_text
    from ui.main_window_widgets import NoWheelComboBox, NoWheelSpinBox
    from ui.style import (
        BUTTON_ROLE_COMMIT,
        BUTTON_ROLE_DESTRUCTIVE,
        BUTTON_ROLE_NEUTRAL,
        BUTTON_ROLE_STOP,
        SURFACE_ROLE_SUBTLE,
        apply_semantic_button_style,
        apply_surface_role,
        apply_theme_dialog_button_box_style,
        themed_yes_no_question,
    )


__all__ = [name for name in globals() if not name.startswith("__")]
