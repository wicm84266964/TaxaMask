"""Shared Registry evidence setup for TIF, nnU-Net, and Local Axis training."""

from __future__ import annotations

import os
import random

from .file_integrity import FULL_FILE_ALGORITHM, compute_fingerprint
from .location_registry import resolve_locations
from .project_integrity_registry import (
    get_training_baseline_snapshot,
    resolve_training_baseline_inputs,
)
from .safe_io import atomic_write_json
from .training_run_recorder import capture_environment
from .training_run_setup import (
    build_and_attach_verified_training_inputs,
    resolved_registry_file_specs,
)


DEFAULT_TIF_TRAINING_SEED = 20260720


def _partition_groups(group_ids, seed):
    groups = sorted({str(value) for value in group_ids if str(value)})
    if len(groups) < 2:
        raise ValueError("not_enough_independent_training_groups")
    shuffled = list(groups)
    random.Random(int(seed)).shuffle(shuffled)
    validation_count = max(1, len(groups) - max(1, int(len(groups) * 0.8)))
    validation = set(shuffled[:validation_count])
    return {
        group: "validation" if group in validation else "train"
        for group in groups
    }


def attach_tif_training_evidence(
    run,
    project_manager,
    *,
    sample_specs,
    effective_config,
    backend,
    seed=DEFAULT_TIF_TRAINING_SEED,
    compute_device="not_recorded",
    cuda="not_recorded",
    deferred_effective_config=False,
    trusted_label_policy="manual_truth_only",
    extra_owner_keys=None,
):
    """Attach fixed TIF inputs to a pending run and transition it to running."""

    database_path = str(project_manager.current_database_path or "")
    project_id = str(project_manager.project_data.get("project_id") or "")
    data_version_id = str(
        project_manager.project_data.get("project_data_version_id") or ""
    )
    snapshot = get_training_baseline_snapshot(database_path, data_version_id)
    opaque_refs = [
        item["location"]["opaque_ref"]
        for item in snapshot["files"]
        if isinstance(item.get("location"), dict)
        and item["location"].get("location_kind") == "opaque_ref"
    ]
    opaque_locations = resolve_locations(
        opaque_refs,
        database_path=getattr(
            project_manager, "location_registry_database_path", None
        ),
    )
    resolved = resolve_training_baseline_inputs(
        database_path,
        snapshot,
        project_root=project_manager.project_dir,
        run_root=run.run_dir,
        opaque_locations=opaque_locations,
    )
    if resolved["project_id"] != project_id:
        raise ValueError("project_registry_identity_mismatch")
    specs = list(sample_specs or [])
    if not specs:
        raise ValueError("tif_training_samples_missing")
    partition_by_group = _partition_groups(
        [item.get("group_id") for item in specs], seed
    )
    files_by_owner = {
        item["owner_key"]: item for item in resolved["files"]
    }
    selected_owner_keys = {
        str(owner_key)
        for spec in specs
        for owner_key in spec.get("owner_keys", [])
    }
    selected_owner_keys.add(project_id)
    selected_owner_keys.update(
        str(value) for value in (extra_owner_keys or []) if str(value)
    )
    assignments = []
    for index, spec in enumerate(specs, start=1):
        owner_keys = [str(value) for value in spec.get("owner_keys", [])]
        if not owner_keys:
            raise ValueError("tif_training_sample_inputs_missing")
        missing = [key for key in owner_keys if key not in files_by_owner]
        if missing:
            raise ValueError(f"tif_registry_asset_missing:{missing[0]}")
        group_id = str(spec.get("group_id") or "")
        assignments.append(
            {
                "sample_id": str(spec.get("sample_id") or f"tif_{index:06d}"),
                "partition": partition_by_group[group_id],
                "group_id": group_id,
                "input_file_ids": [
                    files_by_owner[key]["file_id"] for key in owner_keys
                ],
            }
        )
    clean_config = dict(effective_config)
    if deferred_effective_config:
        invocation = dict(clean_config.get("adapter_invocation") or {})
        invocation["random_seed"] = int(seed)
        clean_config["adapter_invocation"] = invocation
    else:
        clean_config["random_seed"] = int(seed)
    config_relative = "inputs/effective_config.json"
    config_path = os.path.join(run.run_dir, *config_relative.split("/"))
    atomic_write_json(config_path, clean_config, indent=2)
    selected_resolved = dict(resolved)
    selected_resolved["files"] = [
        item
        for item in resolved["files"]
        if str(item.get("owner_key") or "") in selected_owner_keys
    ]
    file_specs = resolved_registry_file_specs(selected_resolved)
    file_specs.append(
        {
            "file_id": "effective_config",
            "role": (
                "training_invocation_config"
                if deferred_effective_config
                else "training_config"
            ),
            "path_base": "run_root",
            "relative_path": config_relative,
            "expected": compute_fingerprint(
                config_path, FULL_FILE_ALGORITHM
            ),
        }
    )
    run.attach_facts(
        project_ref={
            "project_kind": "taxamask_tif",
            "project_id": project_id,
            "project_data_version_id": data_version_id,
        },
        dataset_ref={
            "dataset_id": project_id,
            "data_version_id": data_version_id,
            "trusted_label_policy": str(trusted_label_policy),
            "source_kind": "project",
        },
        effective_config=clean_config,
        backend=dict(backend),
        environment=capture_environment(
            compute_device=compute_device, cuda=cuda
        ),
    )
    validation_groups = {
        group
        for group, partition in partition_by_group.items()
        if partition == "validation"
    }
    build_and_attach_verified_training_inputs(
        run,
        file_specs=file_specs,
        assignments=assignments,
        dataset_id=project_id,
        data_version_id=data_version_id,
        strategy={
            "name": "specimen_group_holdout",
            "version": "v1",
            "seed": int(seed),
            "validation_ratio": len(validation_groups)
            / len(partition_by_group),
        },
        path_bases={"project_root": project_manager.project_dir},
    )
    run.mark_running()
    return {
        "resolved_inputs": resolved,
        "assignments": assignments,
        "partition_by_group": partition_by_group,
        "effective_config": clean_config,
    }


__all__ = [
    "DEFAULT_TIF_TRAINING_SEED",
    "attach_tif_training_evidence",
]
