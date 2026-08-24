import hashlib
import json
import os
from datetime import datetime

from .expert_notes import EXPERT_NOTES_FILENAME
from .taxonomy_defaults import is_safe_part_name
from .training_weight_publisher import (
    PUBLICATION_LOCK_FILENAME,
    TRAINING_BUNDLE_DIRECTORY,
)


BLINK_EXPERT_MANIFEST_LEGACY_SCHEMA_VERSION = "taxamask_blink_expert_manifest_v1"
BLINK_EXPERT_MANIFEST_SCHEMA_VERSION = "taxamask_blink_expert_manifest_v2"
BLINK_EXPERT_MANIFEST_SUPPORTED_SCHEMA_VERSIONS = frozenset(
    {
        BLINK_EXPERT_MANIFEST_LEGACY_SCHEMA_VERSION,
        BLINK_EXPERT_MANIFEST_SCHEMA_VERSION,
    }
)
BLINK_EXPERT_BACKEND_VIT_B = "vit_b_blink"
BLINK_EXPERT_BACKEND_HEATMAP = "heatmap_blink"
BLINK_EXPERT_BACKEND_EXTERNAL = "external_blink"
BLINK_EXPERT_OUTPUT_SCHEMA_VIT_B = "vit_b_box_regression_v1"
BLINK_EXPERT_OUTPUT_SCHEMA_HEATMAP = "heatmap_wh_box_v1"
BLINK_EXPERT_PREPROCESSING_SCHEMA_VERSION = "taxamask_blink_preprocessing_v1"
BLINK_EXPERT_RESERVED_PART_NAMES = frozenset(
    {
        TRAINING_BUNDLE_DIRECTORY.casefold(),
        EXPERT_NOTES_FILENAME.casefold(),
        "cascade_routes.json".casefold(),
        PUBLICATION_LOCK_FILENAME.casefold(),
    }
)


def is_safe_blink_expert_part_name(value):
    if not is_safe_part_name(value):
        return False
    return str(value).strip().casefold() not in BLINK_EXPERT_RESERVED_PART_NAMES


def require_safe_blink_expert_part_name(value):
    clean_value = str(value).strip() if isinstance(value, str) else ""
    if not is_safe_blink_expert_part_name(clean_value):
        raise ValueError("blink_expert_part_name_unsafe_or_reserved")
    return clean_value


def build_blink_preprocessing_contract():
    """Return the inference preprocessing contract shared by Blink trainers."""
    return {
        "schema_version": BLINK_EXPERT_PREPROCESSING_SCHEMA_VERSION,
        "image_decode": "opencv_imread",
        "color_conversion": "bgr_to_rgb",
        "roi": "parent_box_crop",
        "resize": {
            "mode": "stretch",
            "interpolation": "opencv_inter_cubic",
        },
        "tensor": {
            "layout": "chw",
            "dtype": "float32",
            "scale": "divide_255",
        },
    }


def default_manifest_path_for_weights(weights_path):
    text = str(weights_path or "").strip()
    if not text:
        return ""
    root, _ext = os.path.splitext(text)
    return f"{root}.manifest.json"


def _clean_part(value):
    text = str(value or "").strip()
    return text or None


def _strict_part(value):
    if not isinstance(value, str):
        return None
    text = value.strip()
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


def _strict_input_size(value):
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        raw_width, raw_height = value[0], value[1]
    else:
        raw_width = raw_height = value
    if isinstance(raw_width, bool) or isinstance(raw_height, bool):
        return None
    try:
        width = int(raw_width)
        height = int(raw_height)
    except (TypeError, ValueError, OverflowError):
        return None
    if width <= 0 or height <= 0:
        return None
    return [width, height]


def decode_blink_expert_manifest_payload(manifest_payload):
    if not isinstance(manifest_payload, bytes) or not manifest_payload:
        raise ValueError("blink_manifest_payload_invalid")
    try:
        manifest = json.loads(manifest_payload)
    except (UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("blink_manifest_payload_invalid") from exc
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version")
        not in BLINK_EXPERT_MANIFEST_SUPPORTED_SCHEMA_VERSIONS
    ):
        raise ValueError("blink_manifest_payload_schema_invalid")
    return manifest


def verify_blink_manifest_payload(manifest_payload, manifest_identity):
    if not isinstance(manifest_payload, bytes) or not manifest_payload:
        raise ValueError("blink_manifest_payload_invalid")
    if not isinstance(manifest_identity, dict):
        raise ValueError("blink_manifest_payload_identity_missing")
    observed_digest = hashlib.sha256(manifest_payload).hexdigest()
    if (
        manifest_identity.get("size_bytes") != len(manifest_payload)
        or manifest_identity.get("hash_algorithm") != "sha256"
        or manifest_identity.get("digest") != observed_digest
    ):
        raise ValueError("blink_manifest_payload_identity_mismatch")
    return decode_blink_expert_manifest_payload(manifest_payload), observed_digest


def validate_blink_route_identity(
    manifest,
    *,
    route_parent_part=None,
    route_child_part=None,
):
    """Bind one Blink manifest to the parent -> child route using it."""
    if not isinstance(manifest, dict):
        raise ValueError("blink_expert_contract_missing")
    schema_version = manifest.get("schema_version")
    if schema_version not in BLINK_EXPERT_MANIFEST_SUPPORTED_SCHEMA_VERSIONS:
        raise ValueError("blink_manifest_payload_schema_invalid")

    manifest_parent = _strict_part(manifest.get("parent_part"))
    manifest_child = _strict_part(manifest.get("child_part"))
    route_parent = _strict_part(route_parent_part)
    route_child = _strict_part(route_child_part)

    if manifest_child and not is_safe_blink_expert_part_name(manifest_child):
        raise ValueError("blink_manifest_child_part_unsafe_or_reserved")
    if route_child and not is_safe_blink_expert_part_name(route_child):
        raise ValueError("blink_route_child_part_unsafe_or_reserved")

    if schema_version == BLINK_EXPERT_MANIFEST_SCHEMA_VERSION:
        if not manifest_parent:
            raise ValueError("blink_manifest_parent_part_missing")
        if not manifest_child:
            raise ValueError("blink_manifest_child_part_missing")
        if not route_parent:
            raise ValueError("blink_route_parent_part_missing")
        if not route_child:
            raise ValueError("blink_route_child_part_missing")

    if manifest_parent and route_parent and manifest_parent != route_parent:
        raise ValueError("blink_route_parent_part_mismatch")
    if manifest_child and route_child and manifest_child != route_child:
        raise ValueError("blink_route_child_part_mismatch")

    return {
        "parent_part": manifest_parent or route_parent,
        "child_part": manifest_child or route_child,
    }


def validate_blink_expert_contract(
    manifest,
    checkpoint_meta,
    *,
    expected_backend,
    route_input_size=None,
    route_parent_part=None,
    route_child_part=None,
):
    """Cross-check immutable publication evidence before model construction."""
    if not isinstance(manifest, dict) or not isinstance(checkpoint_meta, dict):
        raise ValueError("blink_expert_contract_missing")
    schema_version = manifest.get("schema_version")
    if schema_version not in BLINK_EXPERT_MANIFEST_SUPPORTED_SCHEMA_VERSIONS:
        raise ValueError("blink_manifest_payload_schema_invalid")
    if manifest.get("expert_backend") != expected_backend:
        raise ValueError("blink_manifest_backend_mismatch")

    route_identity = validate_blink_route_identity(
        manifest,
        route_parent_part=route_parent_part,
        route_child_part=route_child_part,
    )
    manifest_parent = _strict_part(manifest.get("parent_part"))
    manifest_child = _strict_part(manifest.get("child_part"))
    route_parent = _strict_part(route_parent_part)
    route_child = _strict_part(route_child_part)
    checkpoint_parent = _strict_part(checkpoint_meta.get("parent_part"))
    checkpoint_child = _strict_part(checkpoint_meta.get("child_part"))
    checkpoint_legacy_child = _strict_part(checkpoint_meta.get("part_name"))
    if (
        checkpoint_child
        and checkpoint_legacy_child
        and checkpoint_child != checkpoint_legacy_child
    ):
        raise ValueError("blink_checkpoint_child_part_alias_mismatch")
    checkpoint_child = checkpoint_child or checkpoint_legacy_child

    if schema_version == BLINK_EXPERT_MANIFEST_SCHEMA_VERSION:
        if not checkpoint_parent:
            raise ValueError("blink_checkpoint_parent_part_missing")
        if not checkpoint_child:
            raise ValueError("blink_checkpoint_child_part_missing")

    expected_parent = manifest_parent or route_parent
    expected_child = manifest_child or route_child
    if (
        checkpoint_parent
        and expected_parent
        and checkpoint_parent != expected_parent
    ):
        raise ValueError("blink_checkpoint_parent_part_mismatch")
    if checkpoint_child and expected_child and checkpoint_child != expected_child:
        raise ValueError("blink_checkpoint_child_part_mismatch")

    expected_output_schema = {
        BLINK_EXPERT_BACKEND_VIT_B: BLINK_EXPERT_OUTPUT_SCHEMA_VIT_B,
        BLINK_EXPERT_BACKEND_HEATMAP: BLINK_EXPERT_OUTPUT_SCHEMA_HEATMAP,
    }.get(expected_backend)
    if expected_output_schema and manifest.get("output_schema") != expected_output_schema:
        raise ValueError("blink_manifest_output_schema_mismatch")

    expected_kind = {
        BLINK_EXPERT_BACKEND_VIT_B: "blink_expert_locator",
        BLINK_EXPERT_BACKEND_HEATMAP: "blink_heatmap_expert",
    }.get(expected_backend)
    checkpoint_kind = str(checkpoint_meta.get("kind") or "").strip()
    if (
        schema_version == BLINK_EXPERT_MANIFEST_SCHEMA_VERSION
        and expected_kind
        and not checkpoint_kind
    ):
        raise ValueError("blink_checkpoint_kind_missing")
    if checkpoint_kind and expected_kind and checkpoint_kind != expected_kind:
        raise ValueError("blink_checkpoint_kind_mismatch")

    manifest_input = _strict_input_size(manifest.get("input_size"))
    checkpoint_input = _strict_input_size(checkpoint_meta.get("input_size"))
    if not manifest_input or not checkpoint_input:
        raise ValueError("blink_input_size_evidence_missing")
    if manifest_input != checkpoint_input:
        raise ValueError("blink_input_size_evidence_mismatch")
    if route_input_size is not None:
        route_input = _strict_input_size(route_input_size)
        if not route_input or route_input != manifest_input:
            raise ValueError("blink_route_input_size_mismatch")

    manifest_preprocessing = manifest.get("preprocessing")
    checkpoint_preprocessing = checkpoint_meta.get("preprocessing")
    if schema_version == BLINK_EXPERT_MANIFEST_SCHEMA_VERSION:
        expected_preprocessing = build_blink_preprocessing_contract()
        if (
            manifest_preprocessing != expected_preprocessing
            or checkpoint_preprocessing != expected_preprocessing
        ):
            raise ValueError("blink_preprocessing_evidence_mismatch")
    elif (
        manifest_preprocessing is not None
        or checkpoint_preprocessing is not None
    ) and manifest_preprocessing != checkpoint_preprocessing:
        raise ValueError("blink_preprocessing_evidence_mismatch")

    return {
        "input_size": manifest_input,
        "preprocessing": manifest_preprocessing,
        "parent_part": route_identity["parent_part"],
        "child_part": route_identity["child_part"],
    }


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
    output_schema=None,
    preprocessing=None,
    train_params=None,
    initialization=None,
    seeds=None,
    created_at=None,
):
    clean_weights_path = os.path.abspath(str(weights_path or ""))
    clean_child = _clean_part(child_part)
    if clean_child:
        clean_child = require_safe_blink_expert_part_name(clean_child)
    clean_backend = (
        str(expert_backend or BLINK_EXPERT_BACKEND_VIT_B).strip()
        or BLINK_EXPERT_BACKEND_VIT_B
    )
    clean_output_schema = str(output_schema or "").strip() or {
        BLINK_EXPERT_BACKEND_HEATMAP: BLINK_EXPERT_OUTPUT_SCHEMA_HEATMAP,
        BLINK_EXPERT_BACKEND_VIT_B: BLINK_EXPERT_OUTPUT_SCHEMA_VIT_B,
    }.get(clean_backend, BLINK_EXPERT_OUTPUT_SCHEMA_VIT_B)
    return {
        "schema_version": BLINK_EXPERT_MANIFEST_SCHEMA_VERSION,
        "expert_backend": clean_backend,
        "expert_id": expert_id_from_weights(clean_weights_path, clean_child),
        "parent_part": _clean_part(parent_part),
        "child_part": clean_child,
        "input_size": _clean_input_size(input_size),
        "weights": {
            "main": os.path.basename(clean_weights_path),
        },
        "output_schema": clean_output_schema,
        "preprocessing": dict(
            preprocessing or build_blink_preprocessing_contract()
        ),
        "train_data": {
            "project_json": str(project_json or ""),
            "trajectory_count": int(trajectory_count or 0),
        },
        "train_params": dict(train_params or {}),
        "initialization": dict(initialization or {}),
        "seeds": dict(seeds or {}),
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
