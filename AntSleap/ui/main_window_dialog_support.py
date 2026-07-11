import os
import re

try:
    from AntSleap.core.cascade_routes import (
        ROUTE_BACKEND_EXTERNAL_BLINK,
        ROUTE_BACKEND_HEATMAP_BLINK,
        ROUTE_BACKEND_VIT_B_BLINK,
    )
    from AntSleap.core.external_backend import BUILTIN_BACKEND_ID, EXTERNAL_BACKEND_ID
    from AntSleap.core.model_profiles import (
        CHILD_BACKEND_EXTERNAL,
        CHILD_BACKEND_HEATMAP,
        CHILD_BACKEND_VIT_B,
        DEFAULT_MODEL_PROFILE_ID,
        PARENT_BACKEND_BUILTIN,
        PARENT_BACKEND_EXTERNAL,
    )
    from AntSleap.ui.main_window_i18n import tr, ui_text
except ImportError:
    from core.cascade_routes import (
        ROUTE_BACKEND_EXTERNAL_BLINK,
        ROUTE_BACKEND_HEATMAP_BLINK,
        ROUTE_BACKEND_VIT_B_BLINK,
    )
    from core.external_backend import BUILTIN_BACKEND_ID, EXTERNAL_BACKEND_ID
    from core.model_profiles import (
        CHILD_BACKEND_EXTERNAL,
        CHILD_BACKEND_HEATMAP,
        CHILD_BACKEND_VIT_B,
        DEFAULT_MODEL_PROFILE_ID,
        PARENT_BACKEND_BUILTIN,
        PARENT_BACKEND_EXTERNAL,
    )
    from ui.main_window_i18n import tr, ui_text


PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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
DEFAULT_TIF_PROJECTS_DIR_NAME = "tif_projects"
DEFAULT_STARTUP_PROJECT_DIR_NAME = "_startup"
BACKGROUND_IMAGE_IMPORT_THRESHOLD = 20
LARGE_PROJECT_OPEN_LIGHTWEIGHT_THRESHOLD = 500
BRAND_ASSETS_DIR = os.path.join(PACKAGE_DIR, "assets", "brand")
APP_ICON_PATH = os.path.join(BRAND_ASSETS_DIR, "taxamask_app_icon_white.ico")
APP_ICON_FALLBACK_PATH = os.path.join(BRAND_ASSETS_DIR, "taxamask_app_icon_white.png")
EXPERIMENTAL_TIF_WORKFLOW_ENV = "TAXAMASK_ENABLE_TIF_WORKFLOW"


def _env_flag_enabled(name):
    value = str(os.environ.get(name, "") or "").strip().lower()
    return value in {"1", "true", "yes", "on"}


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
