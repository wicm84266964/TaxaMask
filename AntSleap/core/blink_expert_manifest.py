import json
import os
from datetime import datetime


BLINK_EXPERT_MANIFEST_SCHEMA_VERSION = "taxamask_blink_expert_manifest_v1"
BLINK_EXPERT_BACKEND_VIT_B = "vit_b_blink"
BLINK_EXPERT_BACKEND_HEATMAP = "heatmap_blink"
BLINK_EXPERT_BACKEND_EXTERNAL = "external_blink"


def default_manifest_path_for_weights(weights_path):
    text = str(weights_path or "").strip()
    if not text:
        return ""
    root, _ext = os.path.splitext(text)
    return f"{root}.manifest.json"


def _clean_part(value):
    text = str(value or "").strip()
    return text or None


def _clean_input_size(value, fallback=(224, 224)):
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        raw_w, raw_h = value[0], value[1]
    else:
        raw_w = raw_h = value
    try:
        width = int(raw_w)
        height = int(raw_h)
    except Exception:
        width, height = int(fallback[0]), int(fallback[1])
    if width <= 0 or height <= 0:
        width, height = int(fallback[0]), int(fallback[1])
    return [width, height]


def expert_id_from_weights(weights_path, child_part=None):
    filename = os.path.basename(str(weights_path or "").strip())
    clean_child = _clean_part(child_part)
    if not filename or not clean_child:
        return filename
    return f"{clean_child}/{filename}"


def build_blink_expert_manifest(
    weights_path,
    *,
    expert_backend=BLINK_EXPERT_BACKEND_VIT_B,
    parent_part=None,
    child_part=None,
    input_size=(224, 224),
    project_json="",
    trajectory_count=0,
    output_schema="vit_b_box_regression_v1",
    train_params=None,
    created_at=None,
):
    clean_weights_path = os.path.abspath(str(weights_path or ""))
    clean_child = _clean_part(child_part)
    return {
        "schema_version": BLINK_EXPERT_MANIFEST_SCHEMA_VERSION,
        "expert_backend": str(expert_backend or BLINK_EXPERT_BACKEND_VIT_B).strip() or BLINK_EXPERT_BACKEND_VIT_B,
        "expert_id": expert_id_from_weights(clean_weights_path, clean_child),
        "parent_part": _clean_part(parent_part),
        "child_part": clean_child,
        "input_size": _clean_input_size(input_size),
        "weights": {
            "main": os.path.basename(clean_weights_path),
        },
        "output_schema": str(output_schema or "vit_b_box_regression_v1"),
        "train_data": {
            "project_json": str(project_json or ""),
            "trajectory_count": int(trajectory_count or 0),
        },
        "train_params": dict(train_params or {}),
        "created_at": created_at or datetime.now().isoformat(timespec="seconds"),
    }


def write_blink_expert_manifest(weights_path, manifest_path=None, **kwargs):
    target_path = manifest_path or default_manifest_path_for_weights(weights_path)
    if not target_path:
        raise ValueError("blink_expert_manifest_path_missing")
    manifest = build_blink_expert_manifest(weights_path, **kwargs)
    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
    return target_path, manifest


def load_blink_expert_manifest(manifest_path):
    path = str(manifest_path or "").strip()
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}
