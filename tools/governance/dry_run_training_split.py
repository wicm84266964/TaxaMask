import argparse
import hashlib
import importlib.util
import json
import os
import sys
from typing import Any


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _load_training_loader_module():
    module_path = os.path.join(
        REPO_ROOT,
        "AntSleap",
        "core",
        "governance",
        "training_manifest_loader.py",
    )
    spec = importlib.util.spec_from_file_location(
        "training_manifest_loader_runtime", module_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from: {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TRAINING_LOADER_MODULE = _load_training_loader_module()
load_training_split_from_manifests = getattr(
    TRAINING_LOADER_MODULE,
    "load_training_split_from_manifests",
)


def _load_labeled_data(project_path: str) -> list[tuple[str, dict[str, Any]]]:
    with open(project_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    labels = payload.get("labels", {})
    if not isinstance(labels, dict):
        raise ValueError("project_labels_not_object")

    labeled: list[tuple[str, dict[str, Any]]] = []
    for image_path, label_data in labels.items():
        if not isinstance(label_data, dict):
            continue
        parts = label_data.get("parts", {})
        if not isinstance(parts, dict) or len(parts) == 0:
            continue
        labeled.append((str(image_path), label_data))

    if not labeled:
        raise ValueError("no_labeled_data")

    return labeled


def _membership_hash(records: list[tuple[str, dict[str, Any]]], prefix: str) -> list[str]:
    return [f"{prefix}|{image_path}" for image_path, _ in records]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dry-run governance manifest split for training (no GUI runtime)."
    )
    parser.add_argument("--project", required=True, help="Project JSON path.")
    parser.add_argument("--split", required=True, help="Split manifest path.")
    parser.add_argument("--train-manifest", required=True, help="Core2 train manifest path.")
    args = parser.parse_args()

    labeled_data = _load_labeled_data(args.project)
    split_result = load_training_split_from_manifests(
        labeled_data=labeled_data,
        split_manifest_path=args.split,
        train_manifest_path=args.train_manifest,
        project_path=args.project,
    )

    train_records = split_result.get("train", [])
    val_records = split_result.get("val", [])
    if not isinstance(train_records, list) or not isinstance(val_records, list):
        raise ValueError("invalid_split_result")

    lines = _membership_hash(train_records, "train") + _membership_hash(val_records, "val")
    runtime_membership_hash = hashlib.sha256(
        "\n".join(sorted(lines)).encode("utf-8")
    ).hexdigest()

    print("split_source=manifest")
    print(f"train_count={len(train_records)}")
    print(f"val_count={len(val_records)}")
    print(f"split_membership_fingerprint={split_result.get('membership_fingerprint', '')}")
    print(f"runtime_membership_hash={runtime_membership_hash}")
    print(
        f"missing_manifest_refs={len(split_result.get('missing_train_ids', [])) + len(split_result.get('missing_val_ids', []))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
