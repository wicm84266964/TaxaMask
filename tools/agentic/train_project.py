import argparse
import os
import random
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch.utils.data import DataLoader


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", ".."))
ANTSLEAP_ROOT = os.path.join(REPO_ROOT, "AntSleap")
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from AntSleap.core.dataset import TwoStageDataset  # noqa: E402
from AntSleap.core.engine import AntEngine  # noqa: E402
from AntSleap.core.file_integrity import (  # noqa: E402
    FULL_FILE_ALGORITHM,
    compute_fingerprint,
)
from AntSleap.core.model_profiles import (  # noqa: E402
    DEFAULT_LOCATOR_LOSS_WEIGHTS,
    sanitize_loss_weights,
)
from AntSleap.core.project import ProjectManager  # noqa: E402
from AntSleap.core.project_training_inputs import (  # noqa: E402
    resolve_2d_project_training_dataset,
)
from AntSleap.core.runtime_device import resolve_torch_device  # noqa: E402
from AntSleap.core.safe_io import atomic_write_json  # noqa: E402
from AntSleap.core.training_preflight import build_training_preflight  # noqa: E402
from AntSleap.core.training_run_recorder import (  # noqa: E402
    ACTIVE_STATUSES,
    TrainingRunRecordError,
    TrainingRunRecorder,
)
from AntSleap.core.training_run_setup import (  # noqa: E402
    build_and_attach_verified_training_inputs,
    resolved_registry_file_specs,
)
from AntSleap.core.training_weight_publisher import (  # noqa: E402
    TrainingWeightPublicationError,
    TrainingWeightPublisher,
)


TRAINING_RUNS_ROOT = os.path.join(
    REPO_ROOT, "TaxaMask_outputs", "runtime_logs", "training_runs"
)
MANAGED_MODEL_ROOT = os.path.join(ANTSLEAP_ROOT, "weights")
BASE_SAM_WEIGHTS_PATH = os.path.join(MANAGED_MODEL_ROOT, "sam_b.pt")
HEADLESS_LEARNING_RATE = 1e-4
HEADLESS_WEIGHT_DECAY = 1e-4
HEADLESS_INPUT_RESOLUTION = (1024, 1024)
_STABLE_IMAGE_UID = re.compile(r"^[A-Za-z0-9._-]{1,240}$")


def _write_json(path: str, payload: dict[str, Any]) -> None:
    atomic_write_json(os.path.abspath(path), payload, indent=2)


def _limit_samples(records: list[tuple[str, dict[str, Any]]], max_samples: int) -> list[tuple[str, dict[str, Any]]]:
    selected = list(records or [])
    return selected[:max_samples] if max_samples > 0 else selected


def _build_reviewed_training_inputs(
    manager: ProjectManager,
    taxonomy: list[str],
    locator_scope: list[str],
    max_samples: int,
) -> tuple[dict[str, Any], list[tuple[str, dict[str, Any]]], list[tuple[str, dict[str, Any]]]]:
    project_data = manager.project_data if isinstance(manager.project_data, dict) else {}
    preflight = build_training_preflight(
        project_data.get("images", []),
        project_data.get("labels", {}),
        taxonomy,
        locator_scope,
    )
    locator_records = _limit_samples(preflight.get("locator_samples", []), max_samples)
    parts_records = _limit_samples(preflight.get("parts_samples", []), max_samples)
    return preflight, locator_records, parts_records


def _preflight_exclusion_counts(preflight: dict[str, Any]) -> dict[str, int]:
    keys = {
        "missing_images": "excluded_missing_images",
        "invalid_images": "excluded_invalid_images",
        "zero_annotation_images": "excluded_zero_annotation_images",
        "invalid_annotation_images": "excluded_invalid_annotation_images",
        "auto_draft_only_images": "excluded_auto_draft_images",
    }
    counts = {
        report_key: len(preflight.get(preflight_key, []) or [])
        for report_key, preflight_key in keys.items()
    }
    counts["total_excluded_images"] = sum(counts.values())
    return counts


def _build_group_partition_map(
    locator_records: list[tuple[str, dict[str, Any]]],
    parts_records: list[tuple[str, dict[str, Any]]],
    seed: int,
    *,
    include_parts: bool,
    sample_uid_by_path: dict[str, str],
) -> dict[str, str]:
    def sample_uid(image_path: str) -> str:
        path_key = str(image_path)
        uid = str(sample_uid_by_path.get(path_key) or "").strip()
        if not _STABLE_IMAGE_UID.fullmatch(uid):
            raise ValueError("stable_image_uid_missing_or_invalid")
        return uid

    stage_paths = {
        "locator": {sample_uid(path) for path, _entry in locator_records},
    }
    if include_parts:
        stage_paths["parts"] = {sample_uid(path) for path, _entry in parts_records}

    ordered_uids: list[str] = []
    seen = set()
    for records in (locator_records, parts_records if include_parts else []):
        for image_path, _entry in records:
            uid = sample_uid(image_path)
            if uid not in seen:
                seen.add(uid)
                ordered_uids.append(uid)
    shuffled = list(ordered_uids)
    random.Random(seed).shuffle(shuffled)
    validation_paths: set[str] = set()

    def can_add(candidate: str) -> bool:
        proposed = validation_paths | {candidate}
        return all(len(paths - proposed) >= 1 for paths in stage_paths.values())

    missing_stages = {
        stage for stage, paths in stage_paths.items() if not (paths & validation_paths)
    }
    while missing_stages:
        candidates = [
            path
            for path in shuffled
            if path not in validation_paths
            and any(path in stage_paths[stage] for stage in missing_stages)
            and can_add(path)
        ]
        if not candidates:
            raise ValueError("group_split_cannot_cover_all_training_stages")
        candidate = max(
            candidates,
            key=lambda path: sum(
                path in stage_paths[stage] for stage in missing_stages
            ),
        )
        validation_paths.add(candidate)
        missing_stages = {
            stage
            for stage, paths in stage_paths.items()
            if not (paths & validation_paths)
        }

    target_validation_count = max(
        1, len(ordered_uids) - max(1, int(len(ordered_uids) * 0.8))
    )
    for candidate in shuffled:
        if len(validation_paths) >= target_validation_count:
            break
        if candidate not in validation_paths and can_add(candidate):
            validation_paths.add(candidate)

    return {
        uid: "validation" if uid in validation_paths else "train"
        for uid in ordered_uids
    }


def _build_sample_uid_map(manager, locator_records, parts_records):
    get_image_uid = getattr(manager, "get_image_uid", None)
    if not callable(get_image_uid):
        raise ValueError("stable_image_uid_lookup_unavailable")
    uid_by_path: dict[str, str] = {}
    path_by_uid: dict[str, str] = {}
    for image_path, _entry in list(locator_records) + list(parts_records):
        path_key = str(image_path)
        if path_key in uid_by_path:
            continue
        uid = str(get_image_uid(image_path) or "").strip()
        if not _STABLE_IMAGE_UID.fullmatch(uid):
            raise ValueError("stable_image_uid_missing_or_invalid")
        previous_path = path_by_uid.get(uid)
        if previous_path is not None and previous_path != path_key:
            raise ValueError("stable_image_uid_duplicate")
        uid_by_path[path_key] = uid
        path_by_uid[uid] = path_key
    return uid_by_path


def _partition_records(records, partition_by_uid, sample_uid_by_path):
    train_records = [
        record
        for record in records
        if partition_by_uid[sample_uid_by_path[str(record[0])]] == "train"
    ]
    validation_records = [
        record
        for record in records
        if partition_by_uid[sample_uid_by_path[str(record[0])]] == "validation"
    ]
    return train_records, validation_records


def _random_seed_facts(seed):
    clean_seed = max(0, int(seed))
    return {
        "python": clean_seed,
        "numpy": clean_seed % (2**32),
        "pytorch": clean_seed,
        "cuda": clean_seed,
    }


def _effective_config(args, parent_backend):
    locator_loss_weights = sanitize_loss_weights(
        parent_backend.get("loss_weights"), DEFAULT_LOCATOR_LOSS_WEIGHTS
    )
    return {
        "epochs": max(1, int(args.epochs)),
        "batch_size": max(1, int(args.batch_size)),
        "learning_rate": HEADLESS_LEARNING_RATE,
        "weight_decay": HEADLESS_WEIGHT_DECAY,
        "random_seed": max(0, int(args.seed)),
        "random_seeds": _random_seed_facts(args.seed),
        "input_resolution": list(HEADLESS_INPUT_RESOLUTION),
        "preprocessing": {
            "dataset_adapter": "TwoStageDataset",
            "locator_mode": "locator",
            "parts_mode": "parts" if args.train_parts else "disabled",
            "parts_batch_size": 1,
            "parts_mask_resolution": [256, 256],
            "trusted_preflight": "build_training_preflight_v1",
        },
        "model": {
            "family": "AntEngine",
            "version": "1",
            "locator": "TraitRegressor",
            "parts": "TrainableSAM" if args.train_parts else "disabled",
        },
        "loss_weights": {
            "locator": locator_loss_weights,
            "parts": {"dice": 1.0} if args.train_parts else {},
        },
        "max_samples": int(args.max_samples),
        "train_parts": bool(args.train_parts),
        "persist_weights": bool(args.save_weights),
        "device_preference": str(args.device),
    }


def _backend_facts():
    return {
        "backend_id": "builtin_locator_sam",
        "backend_version": "1.0",
        "adapter_id": "headless_project_cli",
        "adapter_version": "1.0",
    }


def _runtime_environment(device_preference):
    resolved = resolve_torch_device(device_preference)
    return {
        "compute_device": str(resolved),
        "cuda": str(torch.version.cuda or "not_available"),
    }


def _managed_relative_path(path, base_dir):
    target = Path(path).resolve(strict=True)
    base = Path(base_dir).resolve(strict=True)
    try:
        relative = target.relative_to(base)
    except ValueError:
        return None
    return relative.as_posix()


def _prepare_training_evidence(
    run,
    *,
    project_root,
    data_version_id,
    dataset_id,
    effective_config,
    resolved_inputs,
    locator_records,
    parts_records,
    partition_by_uid,
    sample_uid_by_path,
    seed,
    include_parts,
    initial_weight_slots=(),
):
    config_relative = "inputs/effective_config.json"
    config_path = os.path.join(run.run_dir, *config_relative.split("/"))
    _write_json(config_path, effective_config)
    file_specs = resolved_registry_file_specs(
        resolved_inputs,
        included_initial_weight_slots=initial_weight_slots,
    )
    file_specs.append(
        {
            "file_id": "effective_config",
            "role": "training_config",
            "path_base": "run_root",
            "relative_path": config_relative,
            "expected": compute_fingerprint(config_path, FULL_FILE_ALGORITHM),
        }
    )
    file_ids_by_uid = {}
    for item in resolved_inputs["files"]:
        if item["role"] in {"source_image", "human_confirmed_label"}:
            file_ids_by_uid.setdefault(item["owner_key"], {})[item["role"]] = item[
                "file_id"
            ]

    assignments = []
    records_by_stage = {"locator": locator_records}
    if include_parts:
        records_by_stage["parts"] = parts_records
    for stage, records in records_by_stage.items():
        for index, (image_path, _label_entry) in enumerate(records, start=1):
            image_uid = sample_uid_by_path[str(image_path)]
            file_ids = file_ids_by_uid.get(image_uid, {})
            if set(file_ids) != {"source_image", "human_confirmed_label"}:
                raise ValueError("registry_training_pair_incomplete")
            assignments.append(
                {
                    "sample_id": f"{stage}_{index:06d}",
                    "partition": partition_by_uid[image_uid],
                    "group_id": image_uid,
                    "input_file_ids": [
                        file_ids["source_image"],
                        file_ids["human_confirmed_label"],
                    ],
                }
            )

    selected_uids = {
        sample_uid_by_path[str(path)]
        for records in records_by_stage.values()
        for path, _entry in records
    }
    validation_groups = {
        image_uid
        for image_uid in selected_uids
        if partition_by_uid[image_uid] == "validation"
    }
    validation_ratio = float(len(validation_groups)) / float(len(selected_uids))
    return build_and_attach_verified_training_inputs(
        run,
        file_specs=file_specs,
        assignments=assignments,
        dataset_id=dataset_id,
        data_version_id=data_version_id,
        strategy={
            "name": "group_holdout",
            "version": "v1",
            "seed": int(seed),
            "validation_ratio": validation_ratio,
        },
        path_bases={"project_root": project_root},
    )


def _seed_training(seed):
    seeds = _random_seed_facts(seed)
    random.seed(seeds["python"])
    np.random.seed(seeds["numpy"])
    torch.manual_seed(seeds["pytorch"])
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seeds["cuda"])
    return seeds


def _initial_report(args):
    return {
        "schema_version": "formica-headless-training-report-v1",
        "training_run_id": "",
        "project": os.path.abspath(args.project),
        "epochs": max(1, int(args.epochs)),
        "batch_size": max(1, int(args.batch_size)),
        "max_samples": int(args.max_samples),
        "taxonomy": [],
        "locator_scope": [],
        "source_image_count": 0,
        "labeled_sample_count": 0,
        "locator_eligible_sample_count": 0,
        "parts_eligible_sample_count": 0,
        "locator_selected_sample_count": 0,
        "parts_selected_sample_count": 0,
        "excluded_counts": {},
        "preflight_warnings": [],
        "train_count": 0,
        "val_count": 0,
        "parts_train_count": 0,
        "parts_val_count": 0,
        "locator_history": [],
        "parts_history": [],
        "saved_weights_timestamp": "",
        "weight_publication_status": (
            "not_started" if args.save_weights else "not_requested"
        ),
        "weight_publication_error_code": "",
        "status": "failed",
        "error": "",
    }


def _run_is_active(run):
    try:
        return run is not None and run.status in ACTIVE_STATUSES
    except Exception:
        return False


def _archive_report_payload(report, stage):
    payload = dict(report)
    payload.pop("project", None)
    if payload.get("error"):
        payload["error"] = f"headless_training_stopped_during_{stage}"
    return payload


def _index_run_report(run, report, stage):
    if any(
        item.get("artifact_id") == "training_report"
        for item in run.record.get("artifacts", [])
    ):
        return
    report_path = os.path.join(run.run_dir, "training_report.json")
    _write_json(report_path, _archive_report_payload(report, stage))
    run.add_artifact(
        artifact_id="training_report",
        role="training_report",
        path=report_path,
        media_type="application/json",
    )


def _weight_artifact_specs(run_id, *, include_segmenter):
    specs = [
        {
            "artifact_id": "locator_checkpoint",
            "role": "output_weights",
            "relative_path": f"locator_{run_id}.pth",
            "media_type": "application/octet-stream",
        }
    ]
    if include_segmenter:
        specs.append(
            {
                "artifact_id": "sam_decoder_checkpoint",
                "role": "output_weights",
                "relative_path": f"sam_decoder_lora_{run_id}.pth",
                "media_type": "application/octet-stream",
            }
        )
    return specs


def _index_published_weights(run, publication):
    run.register_path_base("managed_model_root", MANAGED_MODEL_ROOT)
    indexed = []
    for expected in publication.get("artifacts", []):
        relative = str(expected.get("relative_path") or "")
        path = os.path.join(MANAGED_MODEL_ROOT, *relative.split("/"))
        observed = run.add_artifact(
            artifact_id=expected["artifact_id"],
            role="output_weights",
            path=path,
            path_base="managed_model_root",
            media_type=expected["media_type"],
        )
        for field in (
            "artifact_id",
            "role",
            "path_base",
            "relative_path",
            "entry_kind",
            "size_bytes",
            "hash_algorithm",
            "digest",
            "media_type",
        ):
            if observed.get(field) != expected.get(field):
                raise ValueError(f"published_weight_artifact_mismatch:{field}")
        indexed.append(observed)
    return indexed


def _load_run_record_or_none(recorder, run_id):
    try:
        return recorder.load(run_id)
    except TrainingRunRecordError:
        run_dir = os.path.join(recorder.runs_root, str(run_id))
        if not os.path.lexists(run_dir):
            return None
        raise


def _write_publication_report(report_path, report):
    try:
        _write_json(report_path, report)
        return True
    except (Exception, KeyboardInterrupt):
        return False


def _safe_publication_print(message):
    try:
        print(message)
    except BaseException:
        pass


def _activate_weight_publication(
    publisher,
    run_id,
    successful_record,
    report,
    report_path,
):
    """Finish model publication without rewriting an already-successful run."""

    try:
        publisher.activate(run_id, successful_record)
    except KeyboardInterrupt:
        report["weight_publication_status"] = "pending_recovery"
        report["weight_publication_error_code"] = "publication_activation_interrupted"
        _write_publication_report(report_path, report)
        _safe_publication_print("weight_publication_status=pending_recovery")
        _safe_publication_print(
            "weight_publication_error_code=publication_activation_interrupted"
        )
        return 2
    except Exception as exc:
        recoverable = isinstance(exc, TrainingWeightPublicationError) and bool(
            exc.recoverable
        )
        if isinstance(exc, OSError):
            recoverable = True
        code = str(
            getattr(exc, "code", "publication_activation_failed")
            or "publication_activation_failed"
        )
        report["weight_publication_status"] = (
            "pending_recovery" if recoverable else "needs_attention"
        )
        report["weight_publication_error_code"] = code
        _write_publication_report(report_path, report)
        _safe_publication_print(
            f"weight_publication_status={report['weight_publication_status']}"
        )
        _safe_publication_print(f"weight_publication_error_code={code}")
        return 2

    report["weight_publication_status"] = "active"
    report["weight_publication_error_code"] = ""
    if not _write_publication_report(report_path, report):
        _safe_publication_print("weight_publication_status=active")
        _safe_publication_print("weight_publication_report_update=failed")
        return 2
    _safe_publication_print("weight_publication_status=active")
    return 0


def _finish_unsuccessful(
    run,
    report,
    report_path,
    *,
    error,
    stage,
    cancelled,
    weight_publisher=None,
):
    report["status"] = "cancelled" if cancelled else "failed"
    report["error"] = "keyboard_interrupt" if cancelled else str(error)
    try:
        _write_json(report_path, report)
    except Exception:
        pass
    if _run_is_active(run):
        try:
            _index_run_report(run, report, stage)
        except Exception:
            pass
    if _run_is_active(run):
        if cancelled:
            run.cancel(stage=stage)
        else:
            run.fail(
                error,
                code="headless_training_failed",
                summary=f"Headless training stopped during {stage}.",
                stage=stage,
                recoverable=stage
                in {"project_load", "preflight", "integrity_preflight"},
            )
    if weight_publisher is not None and run is not None:
        try:
            weight_publisher.recover(
                lambda run_id: _load_run_record_or_none(run.recorder, run_id)
            )
        except Exception:
            pass
    return 130 if cancelled else 1


def _print_summary(report, report_path):
    print(f"status={report['status']}")
    print(f"weight_publication_status={report['weight_publication_status']}")
    print(f"labeled_sample_count={report['labeled_sample_count']}")
    print(f"train_count={report['train_count']}")
    print(f"val_count={report['val_count']}")
    print(f"report={os.path.abspath(report_path)}")


def _ensure_global_failure_run(run, report):
    if run is not None:
        return run
    try:
        fallback = TrainingRunRecorder(TRAINING_RUNS_ROOT).create_pending(
            "headless_builtin_locator_sam"
        )
        report["training_run_id"] = fallback.run_id
        return fallback
    except Exception:
        return None


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
    report = _initial_report(args)
    report_path = os.path.abspath(args.report)
    run = None
    recorder = None
    weight_publisher = None
    stage = "run_setup"
    try:
        stage = "project_load"
        manager = ProjectManager()
        manager.load_project(os.path.abspath(args.project))
        project_data = (
            manager.project_data if isinstance(manager.project_data, dict) else {}
        )
        project_id = str(project_data.get("project_id") or "").strip()
        data_version_id = str(
            project_data.get("project_data_version_id") or ""
        ).strip()
        if not project_id or not data_version_id:
            raise ValueError("project_traceability_identity_missing")
        if not manager.is_sqlite_project() or not manager.current_database_path:
            raise ValueError("sqlite_project_required_for_training")
        recorder = TrainingRunRecorder(
            TRAINING_RUNS_ROOT,
            database_path=manager.current_database_path,
        )
        run = recorder.create_pending("headless_builtin_locator_sam")
        report["training_run_id"] = run.run_id
        if args.save_weights:
            weight_publisher = TrainingWeightPublisher(MANAGED_MODEL_ROOT)
            weight_publisher.recover(
                lambda run_id: _load_run_record_or_none(recorder, run_id)
            )

        stage = "integrity_preflight"
        registry_dataset = resolve_2d_project_training_dataset(
            run,
            manager,
            data_version_id=data_version_id,
            max_samples=int(args.max_samples),
        )
        if registry_dataset["data_version_id"] != data_version_id:
            raise ValueError("project_registry_data_version_mismatch")
        run.attach_facts(
            project_ref={
                "project_kind": "taxamask_2d",
                "project_id": project_id,
                "project_data_version_id": data_version_id,
            },
            dataset_ref={
                "dataset_id": project_id,
                "data_version_id": data_version_id,
                "trusted_label_policy": "human_confirmed_only",
                "source_kind": "project",
            },
        )

        taxonomy = registry_dataset["taxonomy"]
        locator_scope = registry_dataset["locator_scope"]
        get_active_profile = getattr(manager, "get_active_model_profile", None)
        active_profile = get_active_profile() if callable(get_active_profile) else {}
        active_profile = active_profile if isinstance(active_profile, dict) else {}
        parent_backend = (
            active_profile.get("parent_backend", {})
            if isinstance(active_profile.get("parent_backend"), dict)
            else {}
        )

        stage = "preflight"
        locator_records = registry_dataset["locator_records"]
        parts_records = registry_dataset["parts_records"]
        eligible_paths = {
            str(image_path)
            for image_path, _label_entry in (locator_records + parts_records)
        }
        excluded_count = max(0, registry_dataset["source_count"] - len(eligible_paths))
        report.update(
            {
                "taxonomy": taxonomy,
                "locator_scope": locator_scope,
                "source_image_count": registry_dataset["source_count"],
                "labeled_sample_count": len(eligible_paths),
                "locator_eligible_sample_count": len(locator_records),
                "parts_eligible_sample_count": len(parts_records),
                "locator_selected_sample_count": len(locator_records),
                "parts_selected_sample_count": len(parts_records),
                "excluded_counts": {
                    "unregistered_manual_truth_images": excluded_count,
                    "total_excluded_images": excluded_count,
                },
                "preflight_warnings": [],
            }
        )
        if len(locator_records) < 2:
            raise ValueError("not_enough_reviewed_locator_samples")
        if args.train_parts and len(parts_records) < 2:
            raise ValueError("not_enough_reviewed_parts_samples")
        initial_weight_slots = {
            item.get("owner_key")
            for item in registry_dataset["resolved_inputs"]["files"]
            if item.get("role") == "initial_weights"
        }
        if args.train_parts and "parent.sam_base" not in initial_weight_slots:
            raise ValueError(
                "headless_base_sam_not_registered_use_gui_training_once"
            )

        sample_uid_by_path = {
            str(path): registry_dataset["sample_uid_by_path"][str(path)]
            for path, _entry in (
                list(locator_records)
                + (list(parts_records) if args.train_parts else [])
            )
        }
        partition_by_uid = _build_group_partition_map(
            locator_records,
            parts_records,
            int(args.seed),
            include_parts=bool(args.train_parts),
            sample_uid_by_path=sample_uid_by_path,
        )
        locator_train_records, locator_val_records = _partition_records(
            locator_records, partition_by_uid, sample_uid_by_path
        )
        report["train_count"] = len(locator_train_records)
        report["val_count"] = len(locator_val_records)
        parts_train_records, parts_val_records = ([], [])
        if args.train_parts:
            parts_train_records, parts_val_records = _partition_records(
                parts_records, partition_by_uid, sample_uid_by_path
            )
            report["parts_train_count"] = len(parts_train_records)
            report["parts_val_count"] = len(parts_val_records)

        effective_config = _effective_config(args, parent_backend)
        run.attach_facts(
            effective_config=effective_config,
            backend=_backend_facts(),
            environment=_runtime_environment(args.device),
        )

        _prepare_training_evidence(
            run,
            project_root=registry_dataset["project_root"],
            data_version_id=data_version_id,
            dataset_id=project_id,
            effective_config=effective_config,
            resolved_inputs=registry_dataset["resolved_inputs"],
            locator_records=locator_records,
            parts_records=parts_records,
            partition_by_uid=partition_by_uid,
            sample_uid_by_path=sample_uid_by_path,
            seed=int(args.seed),
            include_parts=bool(args.train_parts),
            initial_weight_slots=("parent.sam_base",) if args.train_parts else (),
        )
        run.mark_running()

        stage = "training"
        _seed_training(args.seed)
        engine = AntEngine(
            learning_rate=HEADLESS_LEARNING_RATE,
            weight_decay=HEADLESS_WEIGHT_DECAY,
            num_classes=len(locator_scope),
            device=args.device,
            locator_loss_weights=effective_config["loss_weights"]["locator"],
        )
        report["device"] = str(engine.device)
        report["loss_config"] = engine.loss_config_snapshot
        locator_model = engine.ensure_locator_loaded()
        locator_train = TwoStageDataset(
            locator_train_records, locator_scope, mode="locator"
        )
        locator_val = TwoStageDataset(
            locator_val_records, locator_scope, mode="locator"
        )
        dl_train = DataLoader(locator_train, batch_size=max(1, int(args.batch_size)), shuffle=True)
        dl_val = DataLoader(locator_val, batch_size=max(1, int(args.batch_size)), shuffle=False)

        for epoch in range(max(1, int(args.epochs))):
            train_loss = engine.train_epoch(
                dl_train, locator_model, engine.opt_loc, None
            )
            metrics = engine.validate_epoch(dl_val, locator_model)
            report["locator_history"].append(
                {
                    "epoch": epoch,
                    "train_loss": float(train_loss),
                    "val_loss": float(metrics.get("loss", 0.0)),
                    "pixel_error": float(metrics.get("pixel_error", 0.0)),
                }
            )

        if args.train_parts:
            parts_train = TwoStageDataset(parts_train_records, taxonomy, mode="parts")
            parts_val = TwoStageDataset(parts_val_records, taxonomy, mode="parts")
            dl_parts_train = DataLoader(parts_train, batch_size=1, shuffle=True)
            dl_parts_val = DataLoader(parts_val, batch_size=1, shuffle=False)
            parts_model = engine.ensure_parts_model_loaded()
            for epoch in range(max(1, int(args.epochs))):
                train_loss = engine.train_epoch(
                    dl_parts_train,
                    parts_model,
                    engine.opt_parts,
                    engine.crit_parts,
                )
                metrics = engine.validate_epoch(dl_parts_val, parts_model)
                report["parts_history"].append(
                    {
                        "epoch": epoch,
                        "train_loss": float(train_loss),
                        "val_loss": float(metrics.get("loss", 0.0)),
                        "iou": float(metrics.get("iou", 0.0)),
                    }
                )

        if args.save_weights:
            stage = "weight_staging"
            output_root = os.path.join(run.run_dir, "outputs")
            os.makedirs(output_root, exist_ok=True)
            with tempfile.TemporaryDirectory(
                prefix=".weight-staging-", dir=output_root
            ) as staging_dir:
                report["saved_weights_timestamp"] = engine.save_weights(
                    save_locator=True,
                    save_segmenter=bool(args.train_parts),
                    output_dir=staging_dir,
                    artifact_key=run.run_id,
                )
                publication = weight_publisher.publish_pending(
                    run.run_id,
                    staging_dir,
                    _weight_artifact_specs(
                        run.run_id, include_segmenter=bool(args.train_parts)
                    ),
                )
            stage = "artifact_index"
            _index_published_weights(run, publication)
            report["weight_publication_status"] = "pending_activation"
            report["weight_publication_error_code"] = ""

        report["status"] = "passed"
        report["error"] = ""
        _write_json(report_path, report)
        _index_run_report(run, report, "completed")
        successful_record = run.succeed()
        if weight_publisher is not None:
            try:
                exit_code = _activate_weight_publication(
                    weight_publisher,
                    run.run_id,
                    successful_record,
                    report,
                    report_path,
                )
            except BaseException:
                report["weight_publication_status"] = "needs_attention"
                report["weight_publication_error_code"] = (
                    "publication_activation_boundary_failed"
                )
                _write_publication_report(report_path, report)
                _safe_publication_print("weight_publication_status=needs_attention")
                _safe_publication_print(
                    "weight_publication_error_code=publication_activation_boundary_failed"
                )
                exit_code = 2
        else:
            exit_code = 0
    except KeyboardInterrupt as exc:
        run = _ensure_global_failure_run(run, report)
        exit_code = _finish_unsuccessful(
            run,
            report,
            report_path,
            error=exc,
            stage=stage,
            cancelled=True,
            weight_publisher=weight_publisher,
        )
    except Exception as exc:
        run = _ensure_global_failure_run(run, report)
        exit_code = _finish_unsuccessful(
            run,
            report,
            report_path,
            error=exc,
            stage=stage,
            cancelled=False,
            weight_publisher=weight_publisher,
        )

    _print_summary(report, report_path)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
