from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from AntSleap.core.file_integrity import (
    FULL_FILE_ALGORITHM,
    TREE_ALGORITHM,
    compute_fingerprint,
)


def safe_id(value: str, fallback: str = "tif_blink") -> str:
    text = str(value or "").strip()
    clean = "".join(
        char if char.isalnum() or char in {"-", "_", "."} else "_"
        for char in text
    ).strip("._")
    return clean or fallback


def resolve_compute_device(value: str) -> str:
    requested = str(value or "cpu").strip().lower()
    if requested != "auto":
        return requested
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def effective_config(args, *, input_resolution, preprocessing, model_version="1"):
    resolution = [int(value) for value in input_resolution]
    if len(resolution) not in {2, 3} or any(value <= 0 for value in resolution):
        raise ValueError("tif_blink_input_resolution_invalid")
    compute_device = resolve_compute_device(args.device)
    return {
        "epochs": int(args.epochs),
        "batch_size": int(args.batch_size),
        "learning_rate": float(args.learning_rate),
        "weight_decay": float(args.weight_decay),
        "random_seed": int(getattr(args, "seed", 17)),
        "input_resolution": resolution,
        "preprocessing": dict(preprocessing),
        "model": {
            "family": "tif_blink_unet2d",
            "version": str(model_version),
            "name": str(args.model_name),
            "base_channels": int(args.base_channels),
        },
        "loss_weights": {
            "boundary": float(args.boundary_weight),
            "dice": float(args.dice_weight),
            "consistency": float(args.consistency_weight),
        },
        "compute_device": compute_device,
        "persist_weights": True,
    }


def backend_facts(entrypoint: str):
    return {
        "backend_id": safe_id(entrypoint),
        "backend_version": "1.0",
        "adapter_id": "tif_blink_cli",
        "adapter_version": "1.0",
    }


def external_file_specs(items, *, source_id):
    specs = []
    digest_parts = []
    for index, item in enumerate(items, start=1):
        path = os.path.abspath(os.fspath(item["path"]))
        expected = compute_fingerprint(
            path, TREE_ALGORITHM if os.path.isdir(path) else FULL_FILE_ALGORITHM
        )
        file_id = safe_id(item.get("file_id") or f"external_{index:06d}")
        role = safe_id(item.get("role") or "training_context")
        digest_parts.append(f"{file_id}:{expected['digest']}")
        specs.append(
            {
                "file_id": file_id,
                "role": role,
                "data_version_id": "pending",
                "algorithm": expected["hash_algorithm"],
                "expected": expected,
                "external_location_ref": safe_id(
                    f"{source_id}.{file_id}", "external_training_input"
                ),
                "runtime_path": path,
            }
        )
    if not specs:
        raise ValueError("external_training_inputs_missing")
    version_digest = hashlib.sha256(
        "\n".join(sorted(digest_parts)).encode("utf-8")
    ).hexdigest()[:24]
    data_version_id = safe_id(f"external_data_{version_digest}")
    for spec in specs:
        spec["data_version_id"] = data_version_id
    return specs, data_version_id


def index_training_outputs(run, result):
    candidates = [
        ("training_history", "training_history", result.get("history_path"), "application/json"),
        ("model_manifest", "model_manifest", result.get("manifest_path"), "application/json"),
        ("best_checkpoint", "output_weights", result.get("best_checkpoint"), "application/x-pytorch"),
        ("last_checkpoint", "output_weights", result.get("last_checkpoint"), "application/x-pytorch"),
    ]
    progress_path = Path(run.run_dir) / "outputs" / "history_progress.jsonl"
    if progress_path.is_file():
        candidates.append(
            ("training_history_progress", "diagnostic_log", str(progress_path), "application/x-ndjson")
        )
    run_root = os.path.abspath(run.run_dir)
    history_payload = json.loads(Path(result["history_path"]).read_text(encoding="utf-8"))
    if not isinstance(history_payload, list) or not history_payload:
        raise ValueError("tif_blink_training_history_invalid")
    manifest_payload = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
    if manifest_payload.get("schema_version") != "tif_blink_model_manifest_v1":
        raise ValueError("tif_blink_model_manifest_invalid")
    for artifact_id, role, value, media_type in candidates:
        if not value:
            raise ValueError(f"tif_blink_training_artifact_missing:{artifact_id}")
        path = os.path.abspath(os.fspath(value))
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        try:
            inside = os.path.normcase(os.path.commonpath([run_root, path])) == os.path.normcase(run_root)
        except ValueError:
            inside = False
        if not inside:
            raise ValueError(f"tif_blink_training_artifact_outside_run:{artifact_id}")
        run.add_artifact(
            artifact_id=artifact_id,
            role=role,
            path=path,
            path_base="run_root",
            media_type=media_type,
        )


__all__ = [
    "backend_facts",
    "effective_config",
    "external_file_specs",
    "index_training_outputs",
    "resolve_compute_device",
    "safe_id",
]
