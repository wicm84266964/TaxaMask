import argparse
import json
import os
import random
import sys
from typing import Any

from torch.utils.data import DataLoader


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", ".."))
ANTSLEAP_ROOT = os.path.join(REPO_ROOT, "AntSleap")
if ANTSLEAP_ROOT not in sys.path:
    sys.path.insert(0, ANTSLEAP_ROOT)

from core.dataset import TwoStageDataset  # noqa: E402
from core.engine import AntEngine  # noqa: E402
from core.project import ProjectManager  # noqa: E402


def _write_json(path: str, payload: dict[str, Any]) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _collect_labeled_data(manager: ProjectManager) -> list[tuple[str, dict[str, Any]]]:
    records: list[tuple[str, dict[str, Any]]] = []
    for image_path in manager.project_data.get("images", []):
        label_data = manager.project_data.get("labels", {}).get(image_path, {})
        if not isinstance(label_data, dict):
            continue
        parts = label_data.get("parts", {})
        if not parts:
            continue
        if not os.path.exists(image_path):
            continue
        records.append((image_path, label_data))
    return records


def _split_data(records: list[tuple[str, dict[str, Any]]], seed: int) -> tuple[list[Any], list[Any]]:
    shuffled = list(records)
    rng = random.Random(seed)
    rng.shuffle(shuffled)
    if len(shuffled) <= 1:
        return shuffled, shuffled
    split_index = max(1, int(len(shuffled) * 0.8))
    if split_index >= len(shuffled):
        split_index = len(shuffled) - 1
    return shuffled[:split_index], shuffled[split_index:]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a small headless TaxaMask training job.")
    parser.add_argument("--project", required=True, help="Input project JSON.")
    parser.add_argument("--report", required=True, help="Output training report JSON.")
    parser.add_argument("--epochs", type=int, default=1, help="Epoch count.")
    parser.add_argument("--batch-size", type=int, default=2, help="Locator batch size.")
    parser.add_argument("--max-samples", type=int, default=12, help="Limit labeled samples for smoke tests; <=0 uses all.")
    parser.add_argument("--seed", type=int, default=20260427, help="Deterministic split seed.")
    parser.add_argument("--train-parts", action="store_true", help="Also train the SAM decoder stage.")
    parser.add_argument("--save-weights", action="store_true", help="Persist trained weights into AntSleap/weights.")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto", help="Compute device preference.")
    args = parser.parse_args()

    manager = ProjectManager()
    manager.load_project(os.path.abspath(args.project))
    taxonomy = manager.project_data.get("taxonomy", [])
    locator_scope = manager.get_locator_scope()
    records = _collect_labeled_data(manager)
    if args.max_samples > 0:
        records = records[: args.max_samples]

    report: dict[str, Any] = {
        "schema_version": "formica-headless-training-report-v1",
        "project": os.path.abspath(args.project),
        "epochs": max(1, int(args.epochs)),
        "batch_size": max(1, int(args.batch_size)),
        "max_samples": int(args.max_samples),
        "taxonomy": taxonomy,
        "locator_scope": locator_scope,
        "labeled_sample_count": len(records),
        "train_count": 0,
        "val_count": 0,
        "locator_history": [],
        "parts_history": [],
        "saved_weights_timestamp": "",
        "status": "failed",
        "error": "",
    }

    try:
        if len(records) < 2:
            raise ValueError("not_enough_labeled_samples")

        train_records, val_records = _split_data(records, int(args.seed))
        report["train_count"] = len(train_records)
        report["val_count"] = len(val_records)

        engine = AntEngine(num_classes=len(locator_scope), device=args.device)
        report["device"] = str(engine.device)
        locator_train = TwoStageDataset(train_records, locator_scope, mode="locator")
        locator_val = TwoStageDataset(val_records, locator_scope, mode="locator")
        dl_train = DataLoader(locator_train, batch_size=max(1, int(args.batch_size)), shuffle=True)
        dl_val = DataLoader(locator_val, batch_size=max(1, int(args.batch_size)), shuffle=False)

        for epoch in range(max(1, int(args.epochs))):
            train_loss = engine.train_epoch(dl_train, engine.locator, engine.opt_loc, None)
            metrics = engine.validate_epoch(dl_val, engine.locator)
            report["locator_history"].append(
                {
                    "epoch": epoch,
                    "train_loss": float(train_loss),
                    "val_loss": float(metrics.get("loss", 0.0)),
                    "pixel_error": float(metrics.get("pixel_error", 0.0)),
                }
            )

        if args.train_parts:
            parts_train = TwoStageDataset(train_records, taxonomy, mode="parts")
            parts_val = TwoStageDataset(val_records, taxonomy, mode="parts")
            dl_parts_train = DataLoader(parts_train, batch_size=1, shuffle=True)
            dl_parts_val = DataLoader(parts_val, batch_size=1, shuffle=False)
            for epoch in range(max(1, int(args.epochs))):
                train_loss = engine.train_epoch(dl_parts_train, engine.parts_model, engine.opt_parts, engine.crit_parts)
                metrics = engine.validate_epoch(dl_parts_val, engine.parts_model)
                report["parts_history"].append(
                    {
                        "epoch": epoch,
                        "train_loss": float(train_loss),
                        "val_loss": float(metrics.get("loss", 0.0)),
                        "iou": float(metrics.get("iou", 0.0)),
                    }
                )

        if args.save_weights:
            report["saved_weights_timestamp"] = engine.save_weights()

        report["status"] = "passed"
    except Exception as exc:
        report["error"] = str(exc)

    _write_json(os.path.abspath(args.report), report)
    print(f"status={report['status']}")
    print(f"labeled_sample_count={report['labeled_sample_count']}")
    print(f"train_count={report['train_count']}")
    print(f"val_count={report['val_count']}")
    print(f"report={os.path.abspath(args.report)}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
