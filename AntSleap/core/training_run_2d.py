"""Shared preparation for auditable built-in 2D training entrypoints."""

from __future__ import annotations

import os
import random
from dataclasses import dataclass

from .file_integrity import FULL_FILE_ALGORITHM, compute_fingerprint
from .project_training_inputs import resolve_2d_project_training_dataset
from .safe_io import atomic_write_json
from .training_run_recorder import TrainingRunRecorder, capture_environment
from .training_run_setup import (
    build_and_attach_verified_training_inputs,
    resolved_registry_file_specs,
)


DEFAULT_TRAINING_SEED = 20260720


@dataclass
class Prepared2DTrainingRun:
    run: object
    dataset: dict
    locator_train_records: list
    locator_validation_records: list
    parts_train_records: list
    parts_validation_records: list
    partition_by_uid: dict
    effective_config: dict


@dataclass
class PreparedBlinkTrainingRun:
    run: object
    dataset: dict
    training_records: list
    validation_records: list
    partition_by_uid: dict
    effective_config: dict


def _build_group_partition_map(
    locator_records,
    parts_records,
    *,
    sample_uid_by_path,
    seed,
    include_parts,
):
    stage_uids = {
        "locator": {
            sample_uid_by_path[str(path)] for path, _entry in locator_records
        }
    }
    if include_parts:
        stage_uids["parts"] = {
            sample_uid_by_path[str(path)] for path, _entry in parts_records
        }
    for stage, values in stage_uids.items():
        if len(values) < 2:
            raise ValueError(f"not_enough_reviewed_{stage}_samples")
    ordered = sorted(set().union(*stage_uids.values()))
    shuffled = list(ordered)
    random.Random(int(seed)).shuffle(shuffled)
    validation = set()

    def can_add(candidate):
        proposed = validation | {candidate}
        return all(values - proposed for values in stage_uids.values())

    uncovered = set(stage_uids)
    while uncovered:
        candidates = [
            uid
            for uid in shuffled
            if uid not in validation
            and any(uid in stage_uids[stage] for stage in uncovered)
            and can_add(uid)
        ]
        if not candidates:
            raise ValueError("group_split_cannot_cover_all_training_stages")
        chosen = max(
            candidates,
            key=lambda uid: sum(uid in stage_uids[stage] for stage in uncovered),
        )
        validation.add(chosen)
        uncovered = {
            stage for stage, values in stage_uids.items() if not (values & validation)
        }
    target = max(1, len(ordered) - max(1, int(len(ordered) * 0.8)))
    for candidate in shuffled:
        if len(validation) >= target:
            break
        if candidate not in validation and can_add(candidate):
            validation.add(candidate)
    return {
        uid: "validation" if uid in validation else "train" for uid in ordered
    }


def _partition(records, partition_by_uid, uid_by_path):
    train = [
        item
        for item in records
        if partition_by_uid[uid_by_path[str(item[0])]] == "train"
    ]
    validation = [
        item
        for item in records
        if partition_by_uid[uid_by_path[str(item[0])]] == "validation"
    ]
    return train, validation


def _assignments(dataset, partition_by_uid, *, include_parts):
    ids_by_uid = {}
    for item in dataset["resolved_inputs"]["files"]:
        if item["role"] in {"source_image", "human_confirmed_label"}:
            ids_by_uid.setdefault(item["owner_key"], {})[item["role"]] = item[
                "file_id"
            ]
    stages = {"locator": dataset["locator_records"]}
    if include_parts:
        stages["parts"] = dataset["parts_records"]
    assignments = []
    for stage, records in stages.items():
        for index, (path, _entry) in enumerate(records, start=1):
            uid = dataset["sample_uid_by_path"][str(path)]
            file_ids = ids_by_uid.get(uid, {})
            if set(file_ids) != {"source_image", "human_confirmed_label"}:
                raise ValueError("registry_training_pair_incomplete")
            assignments.append(
                {
                    "sample_id": f"{stage}_{index:06d}",
                    "partition": partition_by_uid[uid],
                    "group_id": uid,
                    "input_file_ids": [
                        file_ids["source_image"],
                        file_ids["human_confirmed_label"],
                    ],
                }
            )
    return assignments


def prepare_2d_training_run(
    project_manager,
    *,
    runs_root,
    entrypoint,
    effective_config,
    backend,
    include_parts,
    allowed_image_uids=None,
    max_samples=0,
    seed=DEFAULT_TRAINING_SEED,
    compute_device="not_recorded",
    cuda="not_recorded",
    initial_weight_slots=(),
    retry_of=None,
):
    """Create and start a run only after Registry evidence has been rechecked."""

    if not project_manager.is_sqlite_project():
        raise ValueError("sqlite_project_required_for_training")
    project_id = str(project_manager.project_data.get("project_id") or "")
    data_version_id = str(
        project_manager.project_data.get("project_data_version_id") or ""
    )
    recorder = TrainingRunRecorder(
        runs_root, database_path=project_manager.current_database_path
    )
    run = recorder.create_pending(entrypoint, retry_of=retry_of)
    try:
        dataset = resolve_2d_project_training_dataset(
            run,
            project_manager,
            data_version_id=data_version_id,
            max_samples=max_samples,
            allowed_image_uids=allowed_image_uids,
        )
        if dataset["project_id"] != project_id:
            raise ValueError("project_registry_identity_mismatch")
        uid_by_path = dataset["sample_uid_by_path"]
        partition_by_uid = _build_group_partition_map(
            dataset["locator_records"],
            dataset["parts_records"],
            sample_uid_by_path=uid_by_path,
            seed=seed,
            include_parts=include_parts,
        )
        locator_train, locator_validation = _partition(
            dataset["locator_records"], partition_by_uid, uid_by_path
        )
        parts_train, parts_validation = ([], [])
        if include_parts:
            parts_train, parts_validation = _partition(
                dataset["parts_records"], partition_by_uid, uid_by_path
            )
        clean_config = dict(effective_config)
        clean_config["random_seed"] = int(seed)
        config_relative = "inputs/effective_config.json"
        config_path = os.path.join(run.run_dir, *config_relative.split("/"))
        atomic_write_json(config_path, clean_config, indent=2)
        file_specs = resolved_registry_file_specs(
            dataset["resolved_inputs"],
            included_initial_weight_slots=initial_weight_slots,
        )
        file_specs.append(
            {
                "file_id": "effective_config",
                "role": "training_config",
                "path_base": "run_root",
                "relative_path": config_relative,
                "expected": compute_fingerprint(
                    config_path, FULL_FILE_ALGORITHM
                ),
            }
        )
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
            effective_config=clean_config,
            backend=dict(backend),
            environment=capture_environment(
                compute_device=compute_device, cuda=cuda
            ),
        )
        assignments = _assignments(
            dataset, partition_by_uid, include_parts=include_parts
        )
        validation_count = len(
            {
                assignment["group_id"]
                for assignment in assignments
                if assignment["partition"] == "validation"
            }
        )
        group_count = len({item["group_id"] for item in assignments})
        build_and_attach_verified_training_inputs(
            run,
            file_specs=file_specs,
            assignments=assignments,
            dataset_id=project_id,
            data_version_id=data_version_id,
            strategy={
                "name": "group_holdout",
                "version": "v1",
                "seed": int(seed),
                "validation_ratio": validation_count / group_count,
            },
            path_bases={"project_root": dataset["project_root"]},
        )
        run.mark_running()
        return Prepared2DTrainingRun(
            run=run,
            dataset=dataset,
            locator_train_records=locator_train,
            locator_validation_records=locator_validation,
            parts_train_records=parts_train,
            parts_validation_records=parts_validation,
            partition_by_uid=partition_by_uid,
            effective_config=clean_config,
        )
    except BaseException as exc:
        if run.status in {"pending", "running"}:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                run.interrupt(stage="integrity_preflight")
            else:
                run.fail(exc, stage="integrity_preflight")
        raise


def prepare_blink_training_run(
    project_manager,
    *,
    runs_root,
    entrypoint,
    target_part,
    parent_part,
    effective_config,
    backend,
    allowed_image_uids=None,
    seed=DEFAULT_TRAINING_SEED,
    compute_device="not_recorded",
    cuda="not_recorded",
    initial_weight_slots=(),
    retry_of=None,
):
    """Prepare a Blink run from registered trajectory snapshots."""

    recorder = TrainingRunRecorder(
        runs_root, database_path=project_manager.current_database_path
    )
    run = recorder.create_pending(entrypoint, retry_of=retry_of)
    try:
        project_id = str(project_manager.project_data.get("project_id") or "")
        data_version_id = str(
            project_manager.project_data.get("project_data_version_id") or ""
        )
        dataset = resolve_2d_project_training_dataset(
            run,
            project_manager,
            data_version_id=data_version_id,
            allowed_image_uids=allowed_image_uids,
        )
        records = []
        for uid in sorted(
            set(dataset["source_paths_by_uid"])
            & set(dataset["label_snapshots_by_uid"])
        ):
            label = dataset["label_snapshots_by_uid"][uid]
            trajectories = (
                label.get("trajectories")
                if isinstance(label.get("trajectories"), dict)
                else {}
            )
            trajectory = trajectories.get(target_part)
            if trajectory is None:
                continue
            context = (
                trajectory.get("parent_context", {})
                if isinstance(trajectory, dict)
                else {}
            )
            if parent_part and str(context.get("parent_part") or "") != str(
                parent_part
            ):
                continue
            records.append(
                (dataset["source_paths_by_uid"][uid], label)
            )
        uid_by_path = dataset["sample_uid_by_path"]
        partition = _build_group_partition_map(
            records,
            [],
            sample_uid_by_path=uid_by_path,
            seed=seed,
            include_parts=False,
        )
        training_records, validation_records = _partition(
            records, partition, uid_by_path
        )
        clean_config = dict(effective_config)
        clean_config["random_seed"] = int(seed)
        config_relative = "inputs/effective_config.json"
        config_path = os.path.join(run.run_dir, *config_relative.split("/"))
        atomic_write_json(config_path, clean_config, indent=2)
        file_specs = resolved_registry_file_specs(
            dataset["resolved_inputs"],
            included_initial_weight_slots=initial_weight_slots,
        )
        file_specs.append(
            {
                "file_id": "effective_config",
                "role": "training_config",
                "path_base": "run_root",
                "relative_path": config_relative,
                "expected": compute_fingerprint(
                    config_path, FULL_FILE_ALGORITHM
                ),
            }
        )
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
            effective_config=clean_config,
            backend=dict(backend),
            environment=capture_environment(
                compute_device=compute_device, cuda=cuda
            ),
        )
        ids_by_uid = {}
        for item in dataset["resolved_inputs"]["files"]:
            if item["role"] in {"source_image", "human_confirmed_label"}:
                ids_by_uid.setdefault(item["owner_key"], {})[item["role"]] = item[
                    "file_id"
                ]
        assignments = []
        for index, (path, _label) in enumerate(records, start=1):
            uid = uid_by_path[str(path)]
            ids = ids_by_uid.get(uid, {})
            if set(ids) != {"source_image", "human_confirmed_label"}:
                raise ValueError("registry_training_pair_incomplete")
            assignments.append(
                {
                    "sample_id": f"blink_{index:06d}",
                    "partition": partition[uid],
                    "group_id": uid,
                    "input_file_ids": [
                        ids["source_image"],
                        ids["human_confirmed_label"],
                    ],
                }
            )
        build_and_attach_verified_training_inputs(
            run,
            file_specs=file_specs,
            assignments=assignments,
            dataset_id=project_id,
            data_version_id=data_version_id,
            strategy={
                "name": "group_holdout",
                "version": "v1",
                "seed": int(seed),
                "validation_ratio": len(validation_records) / len(records),
            },
            path_bases={"project_root": dataset["project_root"]},
        )
        run.mark_running()
        return PreparedBlinkTrainingRun(
            run=run,
            dataset=dataset,
            training_records=training_records,
            validation_records=validation_records,
            partition_by_uid=partition,
            effective_config=clean_config,
        )
    except BaseException as exc:
        if run.status in {"pending", "running"}:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                run.interrupt(stage="integrity_preflight")
            else:
                run.fail(exc, stage="integrity_preflight")
        raise


__all__ = [
    "DEFAULT_TRAINING_SEED",
    "Prepared2DTrainingRun",
    "PreparedBlinkTrainingRun",
    "prepare_blink_training_run",
    "prepare_2d_training_run",
]
