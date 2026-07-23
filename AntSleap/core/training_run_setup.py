"""Shared integrity and split setup for UI-independent training entrypoints."""

from __future__ import annotations

import copy
import os
from collections.abc import Mapping

from AntSleap.core.file_integrity import DEFAULT_CHUNK_SIZE
from AntSleap.core.integrity_manifest_service import (
    IntegrityManifestService,
    build_external_file_entry,
    build_file_entry,
    require_verified_training_inputs,
)
from AntSleap.core.safe_io import atomic_write_json
from AntSleap.core.project_integrity_registry import (
    get_training_baseline_snapshot,
    resolve_training_baseline_inputs,
)
from AntSleap.core.training_run_recorder import (
    utc_now,
    validate_split_assignments,
)


INTEGRITY_MANIFEST_FILENAME = "integrity_manifest.json"
SPLIT_MANIFEST_FILENAME = "split_manifest.json"

_COMMON_FILE_SPEC_FIELDS = frozenset(
    {"file_id", "role", "data_version_id", "algorithm", "expected"}
)
_MANAGED_FILE_SPEC_FIELDS = _COMMON_FILE_SPEC_FIELDS | frozenset(
    {"path_base", "relative_path", "entry_kind"}
)
_EXTERNAL_FILE_SPEC_FIELDS = _COMMON_FILE_SPEC_FIELDS | frozenset(
    {"external_location_ref", "runtime_path"}
)


def _build_integrity_entry(run, spec, default_data_version_id):
    if not isinstance(spec, Mapping):
        raise TypeError("training_file_spec_not_object")
    payload = dict(spec)
    data_version_id = payload.get("data_version_id", default_data_version_id)
    expected = payload.get("expected")
    if not isinstance(expected, Mapping):
        raise ValueError("training_file_expected_fingerprint_missing")
    required_expected = {
        "entry_kind",
        "size_bytes",
        "hash_algorithm",
        "digest",
    }
    if not required_expected.issubset(expected):
        raise ValueError("training_file_expected_fingerprint_incomplete")
    if "external_location_ref" in payload or "runtime_path" in payload:
        unexpected = set(payload) - set(_EXTERNAL_FILE_SPEC_FIELDS)
        if unexpected:
            raise ValueError(
                f"external_file_spec_field_invalid:{sorted(unexpected)[0]}"
            )
        location_ref = payload.get("external_location_ref")
        runtime_path = payload.get("runtime_path")
        if runtime_path is None:
            raise ValueError("external_file_spec_runtime_path_missing")
        run.register_external_location(location_ref, runtime_path)
        entry = build_external_file_entry(
            payload.get("file_id"),
            payload.get("role"),
            location_ref,
            data_version_id,
            algorithm=payload.get("algorithm"),
        )
        entry.update(
            {
                "size_bytes": expected["size_bytes"],
                "mtime_ns": expected.get("mtime_ns"),
                "hash_algorithm": expected["hash_algorithm"],
                "digest": expected["digest"],
            }
        )
        return entry

    unexpected = set(payload) - set(_MANAGED_FILE_SPEC_FIELDS)
    if unexpected:
        raise ValueError(f"managed_file_spec_field_invalid:{sorted(unexpected)[0]}")
    entry = build_file_entry(
        payload.get("file_id"),
        payload.get("role"),
        payload.get("path_base"),
        payload.get("relative_path"),
        data_version_id,
        algorithm=payload.get("algorithm"),
        entry_kind=payload.get("entry_kind"),
    )
    entry.update(
        {
            "entry_kind": expected["entry_kind"],
            "size_bytes": expected["size_bytes"],
            "mtime_ns": expected.get("mtime_ns"),
            "hash_algorithm": expected["hash_algorithm"],
            "digest": expected["digest"],
        }
    )
    return entry


def build_and_attach_verified_training_inputs(
    run,
    *,
    file_specs,
    assignments,
    dataset_id,
    data_version_id,
    strategy,
    path_bases=None,
    chunk_size=DEFAULT_CHUNK_SIZE,
    progress_callback=None,
    cancel_check=None,
):
    """Create, verify, and attach immutable input and split evidence to a run."""

    managed_bases = {"run_root": run.run_dir}
    for path_base, base_dir in dict(path_bases or {}).items():
        if path_base == "run_root":
            if os.path.normcase(os.path.abspath(os.fspath(base_dir))) != os.path.normcase(
                os.path.abspath(run.run_dir)
            ):
                raise ValueError("run_root_override_not_allowed")
            continue
        run.register_path_base(path_base, base_dir)
        managed_bases[path_base] = os.path.abspath(os.fspath(base_dir))

    specs = list(file_specs or [])
    if not specs:
        raise ValueError("training_file_specs_missing")
    entries = [
        _build_integrity_entry(run, spec, data_version_id) for spec in specs
    ]

    integrity_path = os.path.join(run.run_dir, INTEGRITY_MANIFEST_FILENAME)
    service = IntegrityManifestService(
        integrity_path,
        managed_bases,
        external_locations=run._external_locations,
    )
    service.create_manifest(run.run_id, entries)
    verified = service.verify_manifest(
        chunk_size=chunk_size,
        progress_callback=progress_callback,
        cancel_check=cancel_check,
    )
    require_verified_training_inputs(
        verified,
        required_file_ids=[entry["file_id"] for entry in entries],
    )
    integrity_ref = run.attach_integrity_manifest(integrity_path)

    clean_assignments = copy.deepcopy(list(assignments or []))
    validate_split_assignments(clean_assignments)
    if not isinstance(strategy, Mapping):
        raise TypeError("split_strategy_not_object")
    stamp = utc_now()
    split_payload = {
        "schema_version": "taxamask_training_split_v1",
        "split_id": f"split_{run.run_id}",
        "run_id": run.run_id,
        "status": "verified",
        "created_at": stamp,
        "started_at": stamp,
        "finished_at": stamp,
        "dataset_id": dataset_id,
        "strategy": copy.deepcopy(dict(strategy)),
        "assignments": clean_assignments,
        "error": None,
    }
    split_path = os.path.join(run.run_dir, SPLIT_MANIFEST_FILENAME)
    atomic_write_json(split_path, split_payload, indent=2)
    split_ref = run.attach_split_manifest(split_path)
    return {
        "integrity_manifest": integrity_ref,
        "split_manifest": split_ref,
        "verified_file_count": len(entries),
        "assignment_count": len(clean_assignments),
    }


def _resolved_file_spec(entry):
    run_role = {
        "source_image": "training_image",
    }.get(entry["role"], entry["role"])
    expected = {
        key: entry.get(key)
        for key in (
            "entry_kind",
            "size_bytes",
            "mtime_ns",
            "hash_algorithm",
            "digest",
        )
    }
    base = {
        "file_id": entry["file_id"],
        "role": run_role,
        "data_version_id": entry["data_version_id"],
        "algorithm": entry["hash_algorithm"],
        "expected": expected,
    }
    if "materializer" in entry:
        materializer = entry["materializer"]
        return {
            **base,
            "path_base": "run_root",
            "relative_path": materializer["relative_path"],
            "entry_kind": entry["entry_kind"],
        }
    location = entry["location"]
    if location["location_kind"] == "managed_relative":
        return {
            **base,
            "path_base": location["path_base"],
            "relative_path": location["relative_path"],
            "entry_kind": entry["entry_kind"],
        }
    return {
        **base,
        "external_location_ref": location["opaque_ref"],
        "runtime_path": location["runtime_path"],
    }


def resolved_registry_file_specs(
    resolved_inputs, *, included_initial_weight_slots=None
):
    """Convert verified Registry inputs into immutable run file specs."""

    if not isinstance(resolved_inputs, Mapping):
        raise TypeError("resolved_registry_inputs_not_object")
    if resolved_inputs.get("status") != "verified":
        raise ValueError("resolved_registry_inputs_not_verified")
    files = list(resolved_inputs.get("files") or [])
    if not files:
        raise ValueError("resolved_registry_inputs_empty")
    selected_slots = (
        None
        if included_initial_weight_slots is None
        else {str(value) for value in included_initial_weight_slots}
    )
    return [
        _resolved_file_spec(item)
        for item in files
        if item.get("role") != "initial_weights"
        or selected_slots is None
        or item.get("owner_key") in selected_slots
    ]


def build_and_attach_registry_training_inputs(
    run,
    *,
    database_path,
    project_root,
    assignments,
    dataset_id,
    strategy,
    data_version_id=None,
    opaque_locations=None,
    managed_roots=None,
    chunk_size=DEFAULT_CHUNK_SIZE,
    progress_callback=None,
    cancel_check=None,
):
    """Resolve immutable project expectations, then build run-scoped evidence."""

    snapshot = get_training_baseline_snapshot(database_path, data_version_id)
    resolved = resolve_training_baseline_inputs(
        database_path,
        snapshot,
        project_root=project_root,
        run_root=run.run_dir,
        opaque_locations=opaque_locations,
        managed_roots=managed_roots,
    )
    path_bases = {"project_root": project_root}
    path_bases.update(dict(managed_roots or {}))
    return build_and_attach_verified_training_inputs(
        run,
        file_specs=resolved_registry_file_specs(resolved),
        assignments=assignments,
        dataset_id=dataset_id,
        data_version_id=resolved["data_version_id"],
        strategy=strategy,
        path_bases=path_bases,
        chunk_size=chunk_size,
        progress_callback=progress_callback,
        cancel_check=cancel_check,
    )


__all__ = [
    "INTEGRITY_MANIFEST_FILENAME",
    "SPLIT_MANIFEST_FILENAME",
    "build_and_attach_registry_training_inputs",
    "build_and_attach_verified_training_inputs",
    "resolved_registry_file_specs",
]
