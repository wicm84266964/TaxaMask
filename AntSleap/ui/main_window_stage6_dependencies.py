import os
import sys

import cv2
import numpy as np
from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import QDialog, QInputDialog, QMessageBox

try:
    from AntSleap.core.blink_refiner import BlinkRefiner
    from AntSleap.core.blink_training_strategy import (
        DEFAULT_BLINK_TRAINING_STRATEGY,
        sanitize_blink_training_strategy,
    )
    from AntSleap.core.cascade_routes import get_route_appointed_expert
    from AntSleap.core.model_profiles import (
        CHILD_BACKEND_HEATMAP,
        CHILD_BACKEND_VIT_B,
        DEFAULT_CHILD_AUTO_SHRINK_STEPS,
    )
    from AntSleap.core.project import (
        AUTO_BOX_REVIEW_CONFIRMED,
        AUTO_BOX_REVIEW_DRAFT,
        AUTO_BOX_SOURCE_MODEL,
        AUTO_BOX_SOURCE_VLM,
    )
    from AntSleap.core.sam_helper import SAMWorker
    from AntSleap.ui.main_window_dialog_support import (
        _blink_preferred_roi_parts,
        _clean_box,
        _runtime_child_backend_defaults,
    )
    from AntSleap.ui.main_window_dialogs import BlinkEntryDialog
    from AntSleap.ui.main_window_i18n import tr, ui_text
    from AntSleap.ui.style import BUTTON_ROLE_RUN, themed_yes_no_question
except ImportError:
    from core.blink_refiner import BlinkRefiner
    from core.blink_training_strategy import DEFAULT_BLINK_TRAINING_STRATEGY, sanitize_blink_training_strategy
    from core.cascade_routes import get_route_appointed_expert
    from core.model_profiles import CHILD_BACKEND_HEATMAP, CHILD_BACKEND_VIT_B, DEFAULT_CHILD_AUTO_SHRINK_STEPS
    from core.project import (
        AUTO_BOX_REVIEW_CONFIRMED,
        AUTO_BOX_REVIEW_DRAFT,
        AUTO_BOX_SOURCE_MODEL,
        AUTO_BOX_SOURCE_VLM,
    )
    from core.sam_helper import SAMWorker
    from ui.main_window_dialog_support import _blink_preferred_roi_parts, _clean_box, _runtime_child_backend_defaults
    from ui.main_window_dialogs import BlinkEntryDialog
    from ui.main_window_i18n import tr, ui_text
    from ui.style import BUTTON_ROLE_RUN, themed_yes_no_question


__all__ = [name for name in globals() if not name.startswith("__")]
