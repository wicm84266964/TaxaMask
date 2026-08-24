"""Shared storage identities, label dtype policy, and disk preflight estimates."""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
from pathlib import Path

import numpy as np


TIF_STORAGE_POLICY_VERSION = "taxamask_tif_storage_policy_v1"
TIF_MATERIALIZATION_GENERATOR_VERSION = "taxamask_tif_materialization_v1"
GIB = 1024 ** 3
DEFAULT_TRANSACTION_RESERVE_BYTES = 20 * GIB
DEFAULT_SAFETY_RATIO = 0.15

AUTHORITY_L0 = "L0"
AUTHORITY_L1 = "L1"
AUTHORITY_L2 = "L2"
AUTHORITY_L3 = "L3"
PROTECTED_AUTHORITY_LEVELS = frozenset({AUTHORITY_L0, AUTHORITY_L1})
RECLAIMABLE_AUTHORITY_LEVELS = frozenset({AUTHORITY_L2, AUTHORITY_L3})


def canonical_json_bytes(payload):
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def stable_payload_hash(payload, *, prefix="sha256"):
    digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    return f"{prefix}:{digest}" if prefix else digest


def materialization_cache_key(
    *,
    source_assets,
    format_id,
    axis_order="zyx",
    spacing_zyx=None,
    interpolation="none",
    compression=None,
    exporter_version=TIF_MATERIALIZATION_GENERATOR_VERSION,
    effective_config=None,
):
    payload = {
        "schema_version": TIF_STORAGE_POLICY_VERSION,
        "source_assets": sorted(
            [
                {
                    "asset_id": str(item.get("asset_id") or ""),
                    "content_hash": str(item.get("content_hash") or ""),
                    "role": str(item.get("role") or ""),
                }
                for item in (source_assets or [])
                if isinstance(item, dict)
            ],
            key=lambda item: (item["asset_id"], item["role"], item["content_hash"]),
        ),
        "format": str(format_id or ""),
        "axis_order": str(axis_order or "zyx"),
        "spacing_zyx": [float(value) for value in (spacing_zyx or [])],
        "interpolation": str(interpolation or "none"),
        "compression": dict(compression or {}),
        "exporter_version": str(exporter_version or ""),
        "effective_config": dict(effective_config or {}),
    }
    return stable_payload_hash(payload), payload


def label_dtype_for_max_id(max_label_id):
    try:
        maximum = int(max_label_id)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid_label_id:{max_label_id}") from exc
    if maximum < 0:
        raise ValueError(f"negative_label_id_not_supported:{maximum}")
    for dtype in (np.uint8, np.uint16, np.uint32, np.uint64):
        if maximum <= int(np.iinfo(dtype).max):
            return np.dtype(dtype)
    raise OverflowError(f"label_id_exceeds_uint64:{maximum}")


def label_dtype_for_ids(label_ids, *, default_max_id=0):
    values = []
    for value in label_ids or []:
        try:
            values.append(int(value))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid_label_id:{value}") from exc
    maximum = max(values) if values else int(default_max_id or 0)
    return label_dtype_for_max_id(maximum)


def label_values_fit_dtype(array, dtype):
    target = np.dtype(dtype)
    if target.kind != "u":
        raise ValueError(f"label_dtype_must_be_unsigned_integer:{target}")
    values = np.asarray(array)
    if values.size == 0:
        return True
    if values.dtype.kind not in {"b", "u", "i"}:
        return False
    minimum = int(np.min(values))
    maximum = int(np.max(values))
    info = np.iinfo(target)
    return minimum >= 0 and maximum <= int(info.max)


def ensure_label_value_fits_dtype(value, dtype):
    clean_value = int(value)
    target = np.dtype(dtype)
    if target.kind != "u":
        raise ValueError(f"label_dtype_must_be_unsigned_integer:{target}")
    if clean_value < 0 or clean_value > int(np.iinfo(target).max):
        raise OverflowError(
            f"label_id_not_representable:{clean_value}:{target.name}"
        )
    return clean_value


def logical_volume_bytes(record):
    if not isinstance(record, dict):
        return 0
    shape = record.get("shape_zyx") or []
    if len(shape) != 3:
        return 0
    try:
        count = math.prod(max(0, int(value)) for value in shape)
        dtype = np.dtype(record.get("dtype") or "uint8")
    except (TypeError, ValueError):
        return 0
    return int(count * dtype.itemsize)


def _nearest_existing_path(path):
    candidate = Path(path).resolve()
    while not candidate.exists() and candidate.parent != candidate:
        candidate = candidate.parent
    return candidate


def estimate_storage_preflight(
    contract,
    target_path,
    *,
    backend_id="",
    required_formats=None,
    cache_hit_bytes=0,
):
    """Estimate peak and durable growth conservatively from uncompressed shapes."""

    action = str((contract or {}).get("action") or "prepare_dataset")
    samples = (
        list((contract or {}).get("part_samples") or [])
        if (contract or {}).get("input_scope") == "part_reslice"
        else list((contract or {}).get("specimens") or [])
    )
    input_bytes = 0
    for sample in samples:
        if not isinstance(sample, dict):
            continue
        input_bytes += logical_volume_bytes(sample.get("input_volume") or {})
        input_bytes += logical_volume_bytes(sample.get("label_volume") or {})

    formats = [str(value) for value in (required_formats or []) if str(value)]
    is_nnunet = str(backend_id or "") == "taxamask_tif_nnunet_v2_backend"
    if is_nnunet:
        materialization_multiplier = 1.0
    else:
        materialization_multiplier = float(max(1, len(formats)))
    estimated_materialization = max(
        0,
        int(math.ceil(input_bytes * materialization_multiplier))
        - max(0, int(cache_hit_bytes or 0)),
    )
    backend_multiplier = {
        "prepare_dataset": 1.0 if is_nnunet else 0.5,
        "train": 3.0 if is_nnunet else 2.0,
        "predict": 2.0,
    }.get(action, 1.0)
    backend_working_set = int(math.ceil(input_bytes * backend_multiplier))
    estimate_basis = backend_working_set + estimated_materialization
    transaction_reserve = max(
        int(math.ceil(estimate_basis * DEFAULT_SAFETY_RATIO)),
        DEFAULT_TRANSACTION_RESERVE_BYTES,
    )
    required_peak = estimate_basis + transaction_reserve
    existing = _nearest_existing_path(target_path)
    disk = shutil.disk_usage(existing)
    free_bytes = int(disk.free)
    return {
        "schema_version": TIF_STORAGE_POLICY_VERSION,
        "action": action,
        "backend_id": str(backend_id or ""),
        "target_path": os.path.abspath(os.fspath(target_path)),
        "available_bytes": free_bytes,
        "input_logical_bytes": int(input_bytes),
        "backend_minimum_working_set_bytes": backend_working_set,
        "new_materialization_estimate_bytes": estimated_materialization,
        "persistent_new_estimate_bytes": estimated_materialization,
        "transaction_reserve_bytes": transaction_reserve,
        "safety_margin_ratio": DEFAULT_SAFETY_RATIO,
        "required_peak_bytes": required_peak,
        "sufficient": free_bytes >= required_peak,
        "confidence": "low_conservative" if input_bytes else "unknown",
        "required_formats": formats,
        "cache_hit_bytes": max(0, int(cache_hit_bytes or 0)),
        "notes": [
            "Estimate uses uncompressed shape and dtype, not compressed source size.",
            "The reserve is max(15% of estimated work, 20 GiB).",
            "nnU-Net preprocessing can vary by dataset and configuration.",
        ],
    }


def enforce_storage_preflight(report):
    if not isinstance(report, dict) or report.get("sufficient") is not True:
        available = int((report or {}).get("available_bytes") or 0)
        required = int((report or {}).get("required_peak_bytes") or 0)
        raise OSError(
            "tif_storage_preflight_insufficient:"
            f"available={format_bytes(available)}:required={format_bytes(required)}"
        )
    return report


def format_bytes(value):
    size = max(0, int(value or 0))
    if size >= GIB:
        return f"{size / GIB:.2f} GiB"
    if size >= 1024 ** 2:
        return f"{size / (1024 ** 2):.2f} MiB"
    if size >= 1024:
        return f"{size / 1024:.2f} KiB"
    return f"{size} bytes"
