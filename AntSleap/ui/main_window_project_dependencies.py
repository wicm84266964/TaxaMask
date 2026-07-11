import json
import os
import sys
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox, QProgressDialog

try:
    from AntSleap.app_runtime import runtime_log_event, runtime_log_exception
    from AntSleap.core.amira_import import import_amira_directory
    from AntSleap.core.platform_open import open_path
    from AntSleap.core.project_sqlite_maintenance import (
        backup_sqlite_project_manifest,
        export_sqlite_project_to_legacy_json,
        sqlite_project_migration_report_path,
    )
    from AntSleap.core.project_sqlite_migration import (
        default_sqlite_manifest_path,
        migrate_legacy_2d_json_to_sqlite,
    )
    from AntSleap.core.project_templates import DEFAULT_PROJECT_TEMPLATE_ID, iter_project_templates
    from AntSleap.core.sqlite_storage import (
        PROJECT_MANIFEST_SCHEMA_VERSION,
        SQLITE_BACKEND,
        read_project_manifest,
        resolve_manifest_database_path,
    )
    from AntSleap.core.stl_project import STL_PROJECT_SCHEMA_VERSION, STL_PROJECT_TYPE
    from AntSleap.core.stl_review_bridge import (
        import_stl_rendered_views_into_2d_project,
        register_stl_rendered_views_for_2d_review,
    )
    from AntSleap.core.tif_project import TIF_PROJECT_SCHEMA_VERSION, TIF_PROJECT_TYPE
    from AntSleap.core.tif_sqlite_migration import (
        default_tif_sqlite_manifest_path,
        migrate_legacy_tif_json_to_sqlite,
    )
    from AntSleap.core.tif_stack_import import import_tif_stack
    from AntSleap.ui.main_window_dialog_support import (
        DEFAULT_2D_STL_PROJECTS_DIR_NAME,
        DEFAULT_OUTPUTS_DIR_NAME,
        DEFAULT_PROJECT_NAME,
        DEFAULT_STARTUP_PROJECT_DIR_NAME,
        DEFAULT_TIF_PROJECTS_DIR_NAME,
        LARGE_PROJECT_OPEN_LIGHTWEIGHT_THRESHOLD,
    )
    from AntSleap.ui.main_window_i18n import tr
    from AntSleap.ui.style import BUTTON_ROLE_COMMIT, themed_yes_no_question
except ImportError:
    from app_runtime import runtime_log_event, runtime_log_exception
    from core.amira_import import import_amira_directory
    from core.platform_open import open_path
    from core.project_sqlite_maintenance import (
        backup_sqlite_project_manifest,
        export_sqlite_project_to_legacy_json,
        sqlite_project_migration_report_path,
    )
    from core.project_sqlite_migration import default_sqlite_manifest_path, migrate_legacy_2d_json_to_sqlite
    from core.project_templates import DEFAULT_PROJECT_TEMPLATE_ID, iter_project_templates
    from core.sqlite_storage import (
        PROJECT_MANIFEST_SCHEMA_VERSION,
        SQLITE_BACKEND,
        read_project_manifest,
        resolve_manifest_database_path,
    )
    from core.stl_project import STL_PROJECT_SCHEMA_VERSION, STL_PROJECT_TYPE
    from core.stl_review_bridge import import_stl_rendered_views_into_2d_project, register_stl_rendered_views_for_2d_review
    from core.tif_project import TIF_PROJECT_SCHEMA_VERSION, TIF_PROJECT_TYPE
    from core.tif_sqlite_migration import default_tif_sqlite_manifest_path, migrate_legacy_tif_json_to_sqlite
    from core.tif_stack_import import import_tif_stack
    from ui.main_window_dialog_support import (
        DEFAULT_2D_STL_PROJECTS_DIR_NAME,
        DEFAULT_OUTPUTS_DIR_NAME,
        DEFAULT_PROJECT_NAME,
        DEFAULT_STARTUP_PROJECT_DIR_NAME,
        DEFAULT_TIF_PROJECTS_DIR_NAME,
        LARGE_PROJECT_OPEN_LIGHTWEIGHT_THRESHOLD,
    )
    from ui.main_window_i18n import tr
    from ui.style import BUTTON_ROLE_COMMIT, themed_yes_no_question


PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(PACKAGE_DIR)

__all__ = [name for name in globals() if not name.startswith("__")]
