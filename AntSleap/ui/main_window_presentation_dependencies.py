from PySide6.QtWidgets import QApplication

try:
    from AntSleap.core.blink_training_strategy import DEFAULT_BLINK_TRAINING_STRATEGY, sanitize_blink_training_strategy
    from AntSleap.core.external_backend import (
        BUILTIN_BACKEND_ID,
        EXTERNAL_BACKEND_ID,
        sanitize_external_backend_config,
    )
    from AntSleap.core.model_profiles import DEFAULT_CHILD_AUTO_SHRINK_STEPS
    from AntSleap.core.runtime_device import normalize_device_preference
    from AntSleap.core.tif_backend import DEFAULT_TIF_BACKEND_CONFIG
    from AntSleap.ui.main_window_dialog_support import WORKBENCH_WINDOW_TITLE, _runtime_parent_backend
    from AntSleap.ui.main_window_i18n import tr
    from AntSleap.ui.model_settings_dialog import ModelSettingsDialog
    from AntSleap.ui.settings_dialogs import GeneralSettingsDialog, TifModelSettingsDialog
    from AntSleap.ui.style import (
        BUTTON_ROLE_COMMIT,
        BUTTON_ROLE_DESTRUCTIVE,
        BUTTON_ROLE_NEUTRAL,
        BUTTON_ROLE_RUN,
        BUTTON_ROLE_STOP,
        apply_theme_button_style,
        build_theme_palette,
        get_theme_config,
        get_theme_stylesheet,
        normalize_theme,
        refresh_themed_buttons,
    )
except ImportError:
    from core.blink_training_strategy import DEFAULT_BLINK_TRAINING_STRATEGY, sanitize_blink_training_strategy
    from core.external_backend import BUILTIN_BACKEND_ID, EXTERNAL_BACKEND_ID, sanitize_external_backend_config
    from core.model_profiles import DEFAULT_CHILD_AUTO_SHRINK_STEPS
    from core.runtime_device import normalize_device_preference
    from core.tif_backend import DEFAULT_TIF_BACKEND_CONFIG
    from ui.main_window_dialog_support import WORKBENCH_WINDOW_TITLE, _runtime_parent_backend
    from ui.main_window_i18n import tr
    from ui.model_settings_dialog import ModelSettingsDialog
    from ui.settings_dialogs import GeneralSettingsDialog, TifModelSettingsDialog
    from ui.style import (
        BUTTON_ROLE_COMMIT,
        BUTTON_ROLE_DESTRUCTIVE,
        BUTTON_ROLE_NEUTRAL,
        BUTTON_ROLE_RUN,
        BUTTON_ROLE_STOP,
        apply_theme_button_style,
        build_theme_palette,
        get_theme_config,
        get_theme_stylesheet,
        normalize_theme,
        refresh_themed_buttons,
    )


__all__ = [name for name in globals() if not name.startswith("__")]
