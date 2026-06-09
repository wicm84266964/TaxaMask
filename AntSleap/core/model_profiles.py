from copy import deepcopy

from .vlm_preannotation import DEFAULT_VLM_PROMPT_PROFILE_ID, sanitize_vlm_prompt_profile
from .taxonomy_defaults import DEFAULT_LOCATOR_SCOPE, sanitize_locator_scope
from .blink_training_strategy import DEFAULT_BLINK_TRAINING_STRATEGY, sanitize_blink_training_strategy


MODEL_PROFILES_SCHEMA_VERSION = "taxamask_model_profiles_v1"
DEFAULT_MODEL_PROFILE_ID = "builtin_heatmap_default"

PARENT_BACKEND_BUILTIN = "builtin_locator_sam"
PARENT_BACKEND_EXTERNAL = "external_parent"
PARENT_BACKEND_EXTERNAL_LEGACY = "external_script"
PARENT_BACKEND_TYPES = {PARENT_BACKEND_BUILTIN, PARENT_BACKEND_EXTERNAL, PARENT_BACKEND_EXTERNAL_LEGACY}

CHILD_BACKEND_VIT_B = "vit_b_blink"
CHILD_BACKEND_HEATMAP = "heatmap_blink"
CHILD_BACKEND_EXTERNAL = "external_blink"
CHILD_BACKEND_TYPES = {CHILD_BACKEND_VIT_B, CHILD_BACKEND_HEATMAP, CHILD_BACKEND_EXTERNAL}

DEFAULT_EXTERNAL_PARENT_BACKEND = {
    "backend_id": "custom_external_backend",
    "display_name": "External Script Backend",
    "python_executable": "python",
    "prepare_dataset_command": "",
    "train_command": "",
    "predict_command": "",
    "model_manifest": "",
}

DEFAULT_EXTERNAL_BLINK_BACKEND = {
    "backend_id": "custom_blink_backend",
    "display_name": "External Blink Backend",
    "python_executable": "python",
    "predict_command": "",
    "train_command": "",
    "model_manifest": "",
}

DEFAULT_PARENT_TRAIN_PARAMS = {
    "epochs": 5,
    "batch": 4,
    "lr": 1e-4,
    "weight_decay": 1e-4,
}

DEFAULT_CHILD_TRAIN_PARAMS = {
    "epochs": 5,
    "batch": 2,
    "lr": 1e-3,
    "weight_decay": 1e-4,
}

DEFAULT_CHILD_AUTO_SHRINK_STEPS = 20

DEFAULT_INFERENCE_PARAMS = {
    "conf": 0.1,
    "adapt": 0.4,
    "pad": 0.4,
    "noise_floor": 0.15,
    "poly_epsilon": 2.0,
}

DEFAULT_HEATMAP_BLINK_PARAMS = {
    "input_size": 512,
    "heatmap_sigma": 2.0,
    "wh_loss_weight": 1.0,
    "center_loss_weight": 1.0,
}

VLM_PROCESSING_SCOPES = {"current_image", "all_images", "image_group"}
VLM_IMAGE_GROUPS = {"original", "split", "hard_candidates", "manual_done", "manual"}
DEFAULT_VLM_IMAGE_GROUP = "split"


def _safe_id(value, fallback):
    text = str(value or "").strip()
    clean = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in text)
    return clean.strip("_") or fallback


def _safe_text(value, fallback=""):
    text = str(value or "").strip()
    return text or fallback


def _safe_int(value, fallback, minimum=None):
    try:
        number = int(value)
    except Exception:
        number = int(fallback)
    if minimum is not None:
        number = max(int(minimum), number)
    return number


def _safe_float(value, fallback, minimum=None):
    try:
        number = float(value)
    except Exception:
        number = float(fallback)
    if minimum is not None:
        number = max(float(minimum), number)
    return number


def _clean_backend(value, allowed, fallback):
    text = str(value or "").strip()
    return text if text in allowed else fallback


def _clean_external_config(raw_config, defaults):
    clean = dict(defaults)
    if isinstance(raw_config, dict):
        for key in clean:
            value = raw_config.get(key)
            if value is not None:
                clean[key] = str(value)
    clean["backend_id"] = _safe_id(clean.get("backend_id"), defaults["backend_id"])
    clean["display_name"] = _safe_text(clean.get("display_name"), defaults["display_name"])
    clean["python_executable"] = _safe_text(clean.get("python_executable"), "python")
    return clean


def _clean_parent_ratios(raw_ratios, taxonomy=None):
    taxonomy_set = {str(part).strip() for part in taxonomy or [] if str(part).strip()}
    clean = {}
    if not isinstance(raw_ratios, dict):
        return clean
    for part_name, ratio in raw_ratios.items():
        clean_part = str(part_name or "").strip()
        if not clean_part:
            continue
        if taxonomy_set and clean_part not in taxonomy_set:
            continue
        value = _safe_float(ratio, 0.0)
        if value > 0:
            clean[clean_part] = value
    return clean


def _clean_vlm_settings(raw_settings, taxonomy=None):
    taxonomy_set = {str(part).strip() for part in taxonomy or [] if str(part).strip()}
    if not isinstance(raw_settings, dict):
        raw_settings = {}
    target_parts = []
    for part_name in raw_settings.get("target_parts", []):
        clean_part = str(part_name or "").strip()
        if clean_part and (not taxonomy_set or clean_part in taxonomy_set) and clean_part not in target_parts:
            target_parts.append(clean_part)
    scope = str(raw_settings.get("processing_scope", "image_group") or "image_group").strip()
    if scope not in VLM_PROCESSING_SCOPES:
        scope = "image_group"
    image_group = str(raw_settings.get("image_group", DEFAULT_VLM_IMAGE_GROUP) or DEFAULT_VLM_IMAGE_GROUP).strip()
    if not image_group:
        image_group = DEFAULT_VLM_IMAGE_GROUP
    prompt_profile = sanitize_vlm_prompt_profile(raw_settings.get("prompt_profile", {}))
    prompt_profile_id = str(raw_settings.get("prompt_profile_id") or prompt_profile.get("profile_id") or DEFAULT_VLM_PROMPT_PROFILE_ID).strip()
    try:
        concurrency = int(raw_settings.get("concurrency", 1))
    except Exception:
        concurrency = 1
    concurrency = max(1, min(8, concurrency))
    return {
        "target_parts": target_parts,
        "processing_scope": scope,
        "image_group": image_group,
        "concurrency": concurrency,
        "prompt_profile_id": prompt_profile_id or DEFAULT_VLM_PROMPT_PROFILE_ID,
        "prompt_profile": prompt_profile,
    }


def _clean_train_params(raw_params, defaults):
    raw_params = raw_params if isinstance(raw_params, dict) else {}
    return {
        "epochs": _safe_int(raw_params.get("epochs"), defaults["epochs"], minimum=1),
        "batch": _safe_int(raw_params.get("batch"), defaults["batch"], minimum=1),
        "lr": _safe_float(raw_params.get("lr"), defaults["lr"], minimum=0.0),
        "weight_decay": _safe_float(raw_params.get("weight_decay"), defaults["weight_decay"], minimum=0.0),
    }


def _clean_inference_params(raw_params):
    raw_params = raw_params if isinstance(raw_params, dict) else {}
    return {
        "conf": _safe_float(raw_params.get("conf"), DEFAULT_INFERENCE_PARAMS["conf"], minimum=0.0),
        "adapt": _safe_float(raw_params.get("adapt"), DEFAULT_INFERENCE_PARAMS["adapt"], minimum=0.0),
        "pad": _safe_float(raw_params.get("pad"), DEFAULT_INFERENCE_PARAMS["pad"], minimum=0.0),
        "noise_floor": _safe_float(raw_params.get("noise_floor"), DEFAULT_INFERENCE_PARAMS["noise_floor"], minimum=0.0),
        "poly_epsilon": _safe_float(raw_params.get("poly_epsilon"), DEFAULT_INFERENCE_PARAMS["poly_epsilon"], minimum=0.0),
    }


def _clean_heatmap_params(raw_params):
    raw_params = raw_params if isinstance(raw_params, dict) else {}
    return {
        "input_size": _safe_int(raw_params.get("input_size"), DEFAULT_HEATMAP_BLINK_PARAMS["input_size"], minimum=64),
        "heatmap_sigma": _safe_float(raw_params.get("heatmap_sigma"), DEFAULT_HEATMAP_BLINK_PARAMS["heatmap_sigma"], minimum=0.1),
        "wh_loss_weight": _safe_float(raw_params.get("wh_loss_weight"), DEFAULT_HEATMAP_BLINK_PARAMS["wh_loss_weight"], minimum=0.0),
        "center_loss_weight": _safe_float(raw_params.get("center_loss_weight"), DEFAULT_HEATMAP_BLINK_PARAMS["center_loss_weight"], minimum=0.0),
    }


def _project_locator_scope(locator_scope=None, taxonomy=None):
    fallback = list(locator_scope or DEFAULT_LOCATOR_SCOPE)
    return sanitize_locator_scope(locator_scope or fallback, taxonomy or fallback, fallback=fallback)


def make_default_model_profile(
    *,
    profile_id=DEFAULT_MODEL_PROFILE_ID,
    taxonomy=None,
    locator_scope=None,
    parent_box_aspect_ratios=None,
    vlm_preannotation=None,
    parent_train_params=None,
    child_train_params=None,
    child_auto_shrink_steps=DEFAULT_CHILD_AUTO_SHRINK_STEPS,
    inference_params=None,
    parent_backend_type=PARENT_BACKEND_BUILTIN,
    external_parent_backend=None,
):
    clean_locator_scope = _project_locator_scope(locator_scope, taxonomy)
    clean_parent_backend_type = _clean_backend(
        parent_backend_type,
        PARENT_BACKEND_TYPES,
        PARENT_BACKEND_BUILTIN,
    )
    if clean_parent_backend_type == PARENT_BACKEND_EXTERNAL_LEGACY:
        clean_parent_backend_type = PARENT_BACKEND_EXTERNAL

    return {
        "profile_id": _safe_id(profile_id, DEFAULT_MODEL_PROFILE_ID),
        "display_name": "Built-in heatmap parent + default Blink",
        "description": "Default 2D/STL model profile.",
        "profile_scope": "2d_stl",
        "parent_backend": {
            "backend_type": clean_parent_backend_type,
            "locator_scope": clean_locator_scope,
            "locator_weights": "",
            "segmenter_weights": "BASE_SAM",
            "train_params": _clean_train_params(parent_train_params, DEFAULT_PARENT_TRAIN_PARAMS),
            "parent_box_aspect_ratios": _clean_parent_ratios(parent_box_aspect_ratios, taxonomy),
            "external_backend": _clean_external_config(external_parent_backend, DEFAULT_EXTERNAL_PARENT_BACKEND),
        },
        "child_backend_defaults": {
            "backend_type": CHILD_BACKEND_VIT_B,
            "input_size": 224,
            "auto_shrink_steps": _safe_int(child_auto_shrink_steps, DEFAULT_CHILD_AUTO_SHRINK_STEPS, minimum=1),
            "training_strategy": DEFAULT_BLINK_TRAINING_STRATEGY,
            "train_params": _clean_train_params(child_train_params, DEFAULT_CHILD_TRAIN_PARAMS),
            "heatmap_params": dict(DEFAULT_HEATMAP_BLINK_PARAMS),
            "external_blink_backend": dict(DEFAULT_EXTERNAL_BLINK_BACKEND),
        },
        "inference_params": {
            **_clean_inference_params(inference_params),
            "vlm_preannotation": _clean_vlm_settings(vlm_preannotation, taxonomy),
        },
    }


def sanitize_model_profile(raw_profile, *, taxonomy=None, defaults=None):
    fallback = defaults or make_default_model_profile(taxonomy=taxonomy)
    if not isinstance(raw_profile, dict):
        raw_profile = {}

    profile_id = _safe_id(raw_profile.get("profile_id"), fallback["profile_id"])
    parent_raw = raw_profile.get("parent_backend", {})
    parent_raw = parent_raw if isinstance(parent_raw, dict) else {}
    child_raw = raw_profile.get("child_backend_defaults", {})
    child_raw = child_raw if isinstance(child_raw, dict) else {}
    inference_raw = raw_profile.get("inference_params", {})
    inference_raw = inference_raw if isinstance(inference_raw, dict) else {}

    parent_defaults = fallback["parent_backend"]
    child_defaults = fallback["child_backend_defaults"]
    clean_parent_backend = _clean_backend(
        parent_raw.get("backend_type"),
        PARENT_BACKEND_TYPES,
        parent_defaults["backend_type"],
    )
    if clean_parent_backend == PARENT_BACKEND_EXTERNAL_LEGACY:
        clean_parent_backend = PARENT_BACKEND_EXTERNAL

    clean_child_backend = _clean_backend(
        child_raw.get("backend_type"),
        CHILD_BACKEND_TYPES,
        child_defaults["backend_type"],
    )

    clean_profile = {
        "profile_id": profile_id,
        "display_name": _safe_text(raw_profile.get("display_name"), fallback.get("display_name", profile_id)),
        "description": _safe_text(raw_profile.get("description"), ""),
        "profile_scope": "2d_stl",
        "parent_backend": {
            "backend_type": clean_parent_backend,
            "locator_scope": _project_locator_scope(
                parent_raw.get("locator_scope", parent_defaults.get("locator_scope")),
                taxonomy,
            ),
            "locator_weights": _safe_text(parent_raw.get("locator_weights"), parent_defaults.get("locator_weights", "")),
            "segmenter_weights": _safe_text(parent_raw.get("segmenter_weights"), parent_defaults.get("segmenter_weights", "BASE_SAM")),
            "train_params": _clean_train_params(parent_raw.get("train_params"), parent_defaults.get("train_params", DEFAULT_PARENT_TRAIN_PARAMS)),
            "parent_box_aspect_ratios": _clean_parent_ratios(
                parent_raw.get("parent_box_aspect_ratios", parent_defaults.get("parent_box_aspect_ratios", {})),
                taxonomy,
            ),
            "external_backend": _clean_external_config(
                parent_raw.get("external_backend", parent_defaults.get("external_backend", {})),
                DEFAULT_EXTERNAL_PARENT_BACKEND,
            ),
        },
        "child_backend_defaults": {
            "backend_type": clean_child_backend,
            "input_size": _safe_int(child_raw.get("input_size"), child_defaults.get("input_size", 224), minimum=64),
            "auto_shrink_steps": _safe_int(
                child_raw.get("auto_shrink_steps"),
                child_defaults.get("auto_shrink_steps", DEFAULT_CHILD_AUTO_SHRINK_STEPS),
                minimum=1,
            ),
            "training_strategy": sanitize_blink_training_strategy(
                child_raw.get("training_strategy"),
                child_defaults.get("training_strategy", DEFAULT_BLINK_TRAINING_STRATEGY),
            ),
            "train_params": _clean_train_params(child_raw.get("train_params"), child_defaults.get("train_params", DEFAULT_CHILD_TRAIN_PARAMS)),
            "heatmap_params": _clean_heatmap_params(child_raw.get("heatmap_params", child_defaults.get("heatmap_params", {}))),
            "external_blink_backend": _clean_external_config(
                child_raw.get("external_blink_backend", child_defaults.get("external_blink_backend", {})),
                DEFAULT_EXTERNAL_BLINK_BACKEND,
            ),
        },
        "inference_params": {
            **_clean_inference_params(inference_raw),
            "vlm_preannotation": _clean_vlm_settings(
                inference_raw.get("vlm_preannotation", fallback.get("inference_params", {}).get("vlm_preannotation", {})),
                taxonomy,
            ),
        },
    }
    return clean_profile


def make_default_model_profiles(**context):
    default_profile = make_default_model_profile(**context)
    return {
        "schema_version": MODEL_PROFILES_SCHEMA_VERSION,
        "active_profile_id": default_profile["profile_id"],
        "profiles": [default_profile],
    }


def sanitize_model_profiles(raw_profiles, **context):
    defaults = make_default_model_profile(**context)
    if not isinstance(raw_profiles, dict):
        raw_profiles = {}

    raw_items = raw_profiles.get("profiles", [])
    if isinstance(raw_items, dict):
        raw_items = list(raw_items.values())
    if not isinstance(raw_items, list):
        raw_items = []

    clean_profiles = []
    seen = set()
    for raw_profile in raw_items:
        clean = sanitize_model_profile(raw_profile, taxonomy=context.get("taxonomy"), defaults=defaults)
        profile_id = clean["profile_id"]
        if profile_id in seen:
            continue
        clean_profiles.append(clean)
        seen.add(profile_id)

    if defaults["profile_id"] not in seen:
        clean_profiles.insert(0, defaults)
        seen.add(defaults["profile_id"])

    active_id = _safe_id(raw_profiles.get("active_profile_id"), defaults["profile_id"])
    if active_id not in seen:
        active_id = clean_profiles[0]["profile_id"]

    return {
        "schema_version": MODEL_PROFILES_SCHEMA_VERSION,
        "active_profile_id": active_id,
        "profiles": clean_profiles,
    }


def clone_model_profiles(model_profiles):
    return deepcopy(model_profiles or make_default_model_profiles())


def get_active_model_profile(model_profiles):
    clean = sanitize_model_profiles(model_profiles)
    active_id = clean.get("active_profile_id")
    for profile in clean.get("profiles", []):
        if profile.get("profile_id") == active_id:
            return deepcopy(profile)
    return deepcopy(clean["profiles"][0])


def set_active_model_profile(model_profiles, profile_id):
    clean = sanitize_model_profiles(model_profiles)
    target = str(profile_id or "").strip()
    if not any(profile.get("profile_id") == target for profile in clean.get("profiles", [])):
        raise ValueError(f"model_profile_not_found:{target}")
    clean["active_profile_id"] = target
    return clean


def update_active_profile_snapshot(model_profiles, **context):
    clean = sanitize_model_profiles(model_profiles, **context)
    active_id = clean.get("active_profile_id")
    for index, profile in enumerate(clean.get("profiles", [])):
        if profile.get("profile_id") != active_id:
            continue
        updated = sanitize_model_profile(profile, taxonomy=context.get("taxonomy"), defaults=make_default_model_profile(**context))
        clean["profiles"][index] = updated
        return clean
    return clean
