"""Auditable migration helpers for legacy TIF projects."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path

import numpy as np
from filelock import FileLock

from .file_integrity import FULL_FILE_ALGORITHM, compute_fingerprint
from .safe_io import atomic_write_json, atomic_write_text
from .sqlite_storage import backup_sqlite_database, connect_sqlite_database
from .tif_project import TifProjectManager
from .tif_storage import AUTHORITY_L2, TIF_STORAGE_POLICY_VERSION, format_bytes
from .tif_storage_lifecycle import (
    CLEANUP_REPORT_SCHEMA,
    DEFAULT_QUARANTINE_GRACE_DAYS,
    TifStorageLifecycleManager,
    _json_text,
    _now_iso,
    _relative,
)
from .tif_volume_io import (
    _write_ome_ngff_zarr,
    array_path,
    metadata_path,
    read_volume_metadata,
    volume_sidecar_exists,
)


LABEL_DTYPE_MIGRATION_SCHEMA = "taxamask_tif_label_dtype_migration_v1"
LEGACY_RUN_MIGRATION_SCHEMA = "taxamask_tif_legacy_run_cleanup_v1"
COPY_CHUNK_TARGET_BYTES = 128 * 1024 * 1024
LABEL_ROLES = frozenset(
    {
        "manual_truth",
        "working_edit",
        "editable_ai_result",
        "model_draft",
        "raw_ai_prediction_backup",
        "part_manual_truth",
        "part_editable_ai_result",
        "part_mask",
    }
)


def _now_local_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _normalize_relative(path):
    return str(path or "").replace("\\", "/").lstrip("./")


def _safe_project_path(project_root, relative_path, *, must_exist=True):
    root = os.path.realpath(os.path.abspath(os.fspath(project_root)))
    relative = _normalize_relative(relative_path)
    if not relative or os.path.isabs(relative) or relative.startswith("../"):
        raise ValueError(f"migration_path_not_project_relative:{relative}")
    target = os.path.abspath(os.path.join(root, relative))
    try:
        common = os.path.commonpath([root, os.path.realpath(target)])
    except ValueError as exc:
        raise ValueError(f"migration_path_outside_project:{relative}") from exc
    if os.path.normcase(common) != os.path.normcase(root):
        raise ValueError(f"migration_path_outside_project:{relative}")
    if must_exist and not os.path.exists(target):
        raise FileNotFoundError(target)
    return target


def _directory_size(path):
    total = 0
    for current, dir_names, file_names in os.walk(path, followlinks=False):
        dir_names[:] = [
            name
            for name in sorted(dir_names)
            if not os.path.islink(os.path.join(current, name))
        ]
        for name in sorted(file_names):
            item = os.path.join(current, name)
            if not os.path.islink(item):
                total += int(os.path.getsize(item))
    return total


def _iter_label_sidecars(project_root):
    specimens = Path(project_root) / "specimens"
    if not specimens.is_dir():
        return
    for candidate in sorted(specimens.rglob("metadata.json")):
        sidecar = candidate.parent
        if not volume_sidecar_exists(sidecar):
            continue
        metadata = read_volume_metadata(sidecar)
        role = str(metadata.get("role") or "")
        if role not in LABEL_ROLES and "label" not in role.lower():
            continue
        yield sidecar, metadata


def _chunk_depth(shape, itemsize):
    plane_bytes = max(1, int(shape[1]) * int(shape[2]) * int(itemsize))
    return max(1, min(int(shape[0]), COPY_CHUNK_TARGET_BYTES // plane_bytes))


def _scan_array(path):
    array = np.load(path, mmap_mode="r", allow_pickle=False)
    if array.ndim != 3 or array.dtype.kind not in {"b", "u", "i"}:
        raise ValueError(f"label_array_not_unsigned_3d:{path}:{array.dtype}:{array.shape}")
    minimum = None
    maximum = None
    raw_hash = hashlib.sha256()
    depth = _chunk_depth(array.shape, array.dtype.itemsize)
    for z0 in range(0, int(array.shape[0]), depth):
        chunk = np.ascontiguousarray(array[z0 : z0 + depth])
        current_min = int(np.min(chunk)) if chunk.size else 0
        current_max = int(np.max(chunk)) if chunk.size else 0
        minimum = current_min if minimum is None else min(minimum, current_min)
        maximum = current_max if maximum is None else max(maximum, current_max)
        raw_hash.update(chunk.tobytes(order="C"))
    if minimum is None:
        minimum = 0
        maximum = 0
    if minimum < 0:
        raise ValueError(f"label_array_contains_negative_value:{path}:{minimum}")
    return {
        "shape_zyx": [int(value) for value in array.shape],
        "dtype": str(array.dtype),
        "minimum": minimum,
        "maximum": maximum,
        "raw_value_bytes_sha256": raw_hash.hexdigest(),
    }


def analyze_label_dtype_migration(project_manager):
    project_root = os.path.abspath(project_manager.project_dir)
    candidates = []
    for sidecar, metadata in _iter_label_sidecars(project_root):
        scan = _scan_array(array_path(sidecar))
        target_dtype = np.dtype(
            "uint8"
            if scan["maximum"] <= np.iinfo(np.uint8).max
            else "uint16"
            if scan["maximum"] <= np.iinfo(np.uint16).max
            else "uint32"
            if scan["maximum"] <= np.iinfo(np.uint32).max
            else "uint64"
        )
        before_bytes = _directory_size(sidecar)
        source_dtype = np.dtype(scan["dtype"])
        eligible = source_dtype.kind == "u" and target_dtype.itemsize < source_dtype.itemsize
        candidates.append(
            {
                "relative_path": _relative(project_root, sidecar),
                "role": str(metadata.get("role") or ""),
                "shape_zyx": scan["shape_zyx"],
                "source_dtype": scan["dtype"],
                "target_dtype": str(target_dtype),
                "minimum": scan["minimum"],
                "maximum": scan["maximum"],
                "before_bytes": before_bytes,
                "array_bytes": int(os.path.getsize(array_path(sidecar))),
                "raw_value_bytes_sha256": scan["raw_value_bytes_sha256"],
                "eligible": eligible,
                "status": "planned" if eligible else "unchanged",
            }
        )
    return candidates


def _metadata_for_migrated_sidecar(source_metadata, target_dtype, maximum):
    metadata = dict(source_metadata)
    metadata["dtype"] = str(np.dtype(target_dtype))
    metadata["updated_at"] = _now_local_iso()
    history = list(metadata.get("storage_migrations") or [])
    history.append(
        {
            "schema_version": LABEL_DTYPE_MIGRATION_SCHEMA,
            "migrated_at": metadata["updated_at"],
            "source_dtype": str(source_metadata.get("dtype") or ""),
            "target_dtype": str(np.dtype(target_dtype)),
            "verified_maximum": int(maximum),
            "lossless": True,
        }
    )
    metadata["storage_migrations"] = history[-20:]
    return metadata


def _stage_label_sidecar(source, staging, item):
    os.makedirs(staging, exist_ok=False)
    source_metadata = read_volume_metadata(source)
    source_array = np.load(array_path(source), mmap_mode="r", allow_pickle=False)
    target_dtype = np.dtype(item["target_dtype"])
    target_array = np.lib.format.open_memmap(
        array_path(staging),
        mode="w+",
        dtype=target_dtype,
        shape=source_array.shape,
    )
    source_semantic_hash = hashlib.sha256()
    depth = _chunk_depth(source_array.shape, source_array.dtype.itemsize)
    for z0 in range(0, int(source_array.shape[0]), depth):
        converted = np.ascontiguousarray(
            source_array[z0 : z0 + depth], dtype=target_dtype
        )
        target_array[z0 : z0 + depth] = converted
        source_semantic_hash.update(converted.tobytes(order="C"))
    target_array.flush()
    if hasattr(target_array, "_mmap"):
        target_array._mmap.close()
    del target_array

    metadata = _metadata_for_migrated_sidecar(
        source_metadata,
        target_dtype,
        item["maximum"],
    )
    if source_metadata.get("ome_ngff_complete") is True:
        staged_array = np.load(array_path(staging), mmap_mode="r", allow_pickle=False)
        ngff = _write_ome_ngff_zarr(
            staging,
            staged_array,
            role=metadata.get("role", "unknown"),
            spacing_zyx=metadata.get("spacing_zyx") or [1.0, 1.0, 1.0],
            spacing_unit=metadata.get("spacing_unit", "unknown"),
            chunk_shape_zyx=metadata.get("zarr_chunks_zyx"),
            scale_verified=metadata.get("scale_verified") is True,
        )
        metadata.update(ngff)
        metadata["storage"] = "npy+ome_zarr_v2"
        metadata["ome_ngff_complete"] = True
    else:
        for key in (
            "ome_ngff_version",
            "zarr_format",
            "zarr_array_path",
            "zarr_chunks_zyx",
            "zarr_compressor",
            "zarr_zero_chunks_omitted",
        ):
            metadata.pop(key, None)
        metadata["storage"] = "npy"
        metadata["ome_ngff_complete"] = False
        metadata.pop("ome_ngff_stale_after_edit", None)
    atomic_write_json(metadata_path(staging), metadata, indent=2, ensure_ascii=False)

    verified = np.load(array_path(staging), mmap_mode="r", allow_pickle=False)
    target_hash = hashlib.sha256()
    verified_min = None
    verified_max = None
    depth = _chunk_depth(verified.shape, verified.dtype.itemsize)
    for z0 in range(0, int(verified.shape[0]), depth):
        chunk = np.ascontiguousarray(verified[z0 : z0 + depth])
        current_min = int(np.min(chunk)) if chunk.size else 0
        current_max = int(np.max(chunk)) if chunk.size else 0
        verified_min = current_min if verified_min is None else min(verified_min, current_min)
        verified_max = current_max if verified_max is None else max(verified_max, current_max)
        target_hash.update(chunk.tobytes(order="C"))
    if list(verified.shape) != item["shape_zyx"] or str(verified.dtype) != item["target_dtype"]:
        raise ValueError(f"label_dtype_migration_shape_or_dtype_mismatch:{source}")
    if verified_min != item["minimum"] or verified_max != item["maximum"]:
        raise ValueError(f"label_dtype_migration_value_range_mismatch:{source}")
    if target_hash.hexdigest() != source_semantic_hash.hexdigest():
        raise ValueError(f"label_dtype_migration_semantic_hash_mismatch:{source}")
    return {
        "semantic_sha256": target_hash.hexdigest(),
        "after_bytes": _directory_size(staging),
    }


def _rewrite_dtype_references(value, relative_path, target_dtype):
    changed = 0
    if isinstance(value, dict):
        if _normalize_relative(value.get("path")) == relative_path:
            if str(value.get("dtype") or "") != target_dtype:
                value["dtype"] = target_dtype
                changed += 1
        for child in value.values():
            changed += _rewrite_dtype_references(child, relative_path, target_dtype)
    elif isinstance(value, list):
        for child in value:
            changed += _rewrite_dtype_references(child, relative_path, target_dtype)
    return changed


def _update_database_dtype(connection, relative_path, target_dtype):
    normalized = _normalize_relative(relative_path)
    volume_rows = connection.execute(
        "SELECT id, metadata_json FROM volume_assets WHERE REPLACE(path, '\\', '/') = ?",
        (normalized,),
    ).fetchall()
    volume_updates = 0
    for row_id, metadata_text in volume_rows:
        try:
            metadata = json.loads(metadata_text or "{}")
        except (TypeError, ValueError):
            metadata = {}
        _rewrite_dtype_references(metadata, normalized, target_dtype)
        connection.execute(
            """
            UPDATE volume_assets
            SET dtype = ?, metadata_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (target_dtype, _json_text(metadata), int(row_id)),
        )
        volume_updates += 1

    reslice_updates = 0
    columns = ("training_json", "training_sample_json")
    for row in connection.execute(
        "SELECT id, training_json, training_sample_json FROM part_reslices"
    ).fetchall():
        updates = {}
        for column, text in zip(columns, row[1:]):
            try:
                payload = json.loads(text or "{}")
            except (TypeError, ValueError):
                payload = {}
            if _rewrite_dtype_references(payload, normalized, target_dtype):
                updates[column] = _json_text(payload)
        if updates:
            assignments = ", ".join(f"{key} = ?" for key in updates)
            connection.execute(
                f"UPDATE part_reslices SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                [*updates.values(), int(row[0])],
            )
            reslice_updates += 1
    return {
        "volume_asset_rows": volume_updates,
        "part_reslice_rows": reslice_updates,
    }


def _label_report_markdown(report):
    lines = [
        "# TIF 标签 dtype 无损迁移报告",
        "",
        f"- 状态：`{report.get('state', '')}`",
        f"- 开始时间：{report.get('started_at', '')}",
        f"- 完成时间：{report.get('finished_at', '') or '尚未完成'}",
        f"- 迁移前占用：{format_bytes(report.get('before_bytes'))}",
        f"- 迁移后占用：{format_bytes(report.get('after_bytes'))}",
        f"- 已实际释放：{format_bytes(report.get('released_bytes'))}",
        "- 校验：逐块值域 + 转换后语义 SHA-256；数值不变，仅缩窄整数 dtype。",
        "",
        "| 状态 | 角色 | 路径 | dtype | 最大值 | 释放 |",
        "| --- | --- | --- | --- | ---: | ---: |",
    ]
    for item in report.get("items", []) or []:
        lines.append(
            f"| {item.get('status', '')} | {item.get('role', '')} | "
            f"`{item.get('relative_path', '')}` | "
            f"{item.get('source_dtype', '')} -> {item.get('target_dtype', '')} | "
            f"{item.get('maximum', '')} | {format_bytes(item.get('released_bytes'))} |"
        )
    lines.append("")
    return "\n".join(lines)


def migrate_label_dtypes(project_manager):
    project_root = os.path.abspath(project_manager.project_dir)
    lock_path = os.path.join(project_root, ".taxamask_storage.lock")
    migration_id = (
        "label_dtype_migration_"
        + datetime.now().strftime("%Y%m%d_%H%M%S")
        + "_"
        + uuid.uuid4().hex[:8]
    )
    report_dir = os.path.join(project_root, "storage_reports", migration_id)
    os.makedirs(report_dir, exist_ok=False)
    report_path = os.path.join(report_dir, "migration.json")
    markdown_path = os.path.join(report_dir, "migration_zh.md")
    report = {
        "schema_version": LABEL_DTYPE_MIGRATION_SCHEMA,
        "migration_id": migration_id,
        "state": "running",
        "started_at": _now_iso(),
        "finished_at": "",
        "project_root": project_root,
        "database_backup": "",
        "before_bytes": 0,
        "after_bytes": 0,
        "released_bytes": 0,
        "items": [],
    }

    def persist():
        atomic_write_json(report_path, report, indent=2, ensure_ascii=False)
        atomic_write_text(markdown_path, _label_report_markdown(report), encoding="utf-8")

    persist()
    with FileLock(lock_path, timeout=30):
        candidates = analyze_label_dtype_migration(project_manager)
        report["items"] = candidates
        report["before_bytes"] = sum(
            int(item["before_bytes"]) for item in candidates if item["eligible"]
        )
        backup = backup_sqlite_database(
            project_manager.current_database_path,
            backup_dir=report_dir,
            stem="project.before_label_dtype_migration",
            min_interval_seconds=0,
        )
        report["database_backup"] = _relative(project_root, backup) if backup else ""
        persist()

        connection = connect_sqlite_database(project_manager.current_database_path)
        try:
            for item in report["items"]:
                if not item["eligible"]:
                    continue
                source = _safe_project_path(project_root, item["relative_path"])
                transaction_id = uuid.uuid4().hex
                staging = f"{source}.dtype_migration_pending_{transaction_id}"
                rollback = f"{source}.dtype_migration_rollback_{transaction_id}"
                try:
                    verification = _stage_label_sidecar(source, staging, item)
                    os.replace(source, rollback)
                    try:
                        os.replace(staging, source)
                        with connection:
                            item["database_updates"] = _update_database_dtype(
                                connection,
                                item["relative_path"],
                                item["target_dtype"],
                            )
                    except Exception:
                        if os.path.exists(source):
                            shutil.rmtree(source)
                        os.replace(rollback, source)
                        raise
                    shutil.rmtree(rollback)
                    item.update(verification)
                    item["released_bytes"] = max(
                        0, int(item["before_bytes"]) - int(item["after_bytes"])
                    )
                    item["status"] = "migrated"
                    report["after_bytes"] += int(item["after_bytes"])
                    report["released_bytes"] += int(item["released_bytes"])
                    persist()
                except Exception as exc:
                    item["status"] = "failed"
                    item["error"] = f"{type(exc).__name__}:{exc}"
                    report["state"] = "failed"
                    persist()
                    raise
                finally:
                    if os.path.exists(staging):
                        shutil.rmtree(staging, ignore_errors=True)
        finally:
            connection.close()
    report["state"] = "completed"
    report["finished_at"] = _now_iso()
    persist()
    return report


def _has_regular_files(path):
    return any(candidate.is_file() for candidate in Path(path).rglob("*"))


def _contract_sources(contract):
    sources = []
    for sample in contract.get("part_samples", []) or []:
        if not isinstance(sample, dict):
            continue
        for role, key in (("source_volume", "input_volume"), ("manual_truth", "label_volume")):
            record = sample.get(key) or {}
            path = str(record.get("path") or "") if isinstance(record, dict) else ""
            if path:
                sources.append({"role": role, "path": path})
    return sources


def _legacy_run_targets(project_root):
    targets = []
    runs_root = Path(project_root) / "runs"
    layouts = {
        "prepare_dataset": (
            Path("dataset"),
            Path("nnunet") / "nnUNet_raw",
            Path("nnunet") / "nnUNet_preprocessed",
        ),
        "train": (
            Path("nnunet") / "nnUNet_raw",
            Path("nnunet") / "nnUNet_preprocessed",
        ),
    }
    for workflow, sections in layouts.items():
        workflow_root = runs_root / workflow
        if not workflow_root.is_dir():
            continue
        for run_root in sorted(path for path in workflow_root.iterdir() if path.is_dir()):
            contract_path = run_root / "contract.json"
            if not contract_path.is_file():
                continue
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            if str(contract.get("action") or "") != workflow:
                continue
            sources = _contract_sources(contract)
            if not sources or any(not os.path.exists(item["path"]) for item in sources):
                continue
            for section in sections:
                candidate = run_root / section
                if candidate.is_dir() and _has_regular_files(candidate):
                    targets.append(
                        {
                            "run_id": run_root.name,
                            "workflow": workflow,
                            "path": candidate,
                            "contract_path": contract_path,
                            "contract": contract,
                            "sources": sources,
                        }
                    )
    return targets


def create_legacy_run_cleanup_plan(project_manager):
    project_root = os.path.abspath(project_manager.project_dir)
    lifecycle = TifStorageLifecycleManager(project_manager)
    inventory = lifecycle.analyze()
    plan_id = (
        "cleanup_legacy_"
        + datetime.now().strftime("%Y%m%d_%H%M%S")
        + "_"
        + uuid.uuid4().hex[:8]
    )
    source_fingerprints = {}
    items = []
    for target in _legacy_run_targets(project_root):
        fingerprint = compute_fingerprint(target["path"])
        content_hash = f"{fingerprint['hash_algorithm']}:{fingerprint['digest']}"
        source_records = []
        for source in target["sources"]:
            source_path = os.path.abspath(source["path"])
            fingerprint_path = (
                array_path(source_path)
                if os.path.isdir(source_path) and volume_sidecar_exists(source_path)
                else source_path
            )
            cache_key = os.path.normcase(os.path.realpath(fingerprint_path))
            if cache_key not in source_fingerprints:
                source_fingerprints[cache_key] = compute_fingerprint(
                    fingerprint_path,
                    FULL_FILE_ALGORITHM,
                )
            source_fp = source_fingerprints[cache_key]
            source_records.append(
                {
                    "role": source["role"],
                    "path": _relative(project_root, source_path),
                    "content_hash": f"{source_fp['hash_algorithm']}:{source_fp['digest']}",
                    "size_bytes": int(source_fp["size_bytes"]),
                }
            )
        contract_fp = compute_fingerprint(target["contract_path"], FULL_FILE_ALGORITHM)
        items.append(
            {
                "item_id": f"cleanup_item_{uuid.uuid4().hex}",
                "asset_id": "",
                "cache_key": f"legacy-tree:{fingerprint['digest']}",
                "role": "legacy_reproducible_run_cache",
                "authority_level": AUTHORITY_L2,
                "original_path": _relative(project_root, target["path"]),
                "quarantine_path": "",
                "path_kind": "legacy_reproducible_tree",
                "size_bytes": int(fingerprint["size_bytes"]),
                "expected_release_bytes": int(fingerprint["size_bytes"]),
                "content_hash": content_hash,
                "eligibility": "eligible",
                "blocked_reason": "",
                "state": "planned",
                "run_ids": [target["run_id"]],
                "reproducible_evidence": (
                    "legacy contract + authoritative source full hashes + directory tree hash"
                ),
                "legacy_migration_schema": LEGACY_RUN_MIGRATION_SCHEMA,
                "workflow": target["workflow"],
                "contract_hash": f"{contract_fp['hash_algorithm']}:{contract_fp['digest']}",
                "source_assets": source_records,
            }
        )

    expected = sum(int(item["expected_release_bytes"]) for item in items)
    created_at = _now_iso()
    inventory_path = str((inventory.get("report_paths") or {}).get("json_path") or "")
    report_dir = os.path.join(project_root, "storage_reports", plan_id)
    report_json_path = os.path.join(report_dir, "cleanup_plan.json")
    report_markdown_path = os.path.join(report_dir, "cleanup_plan_zh.md")
    os.makedirs(report_dir, exist_ok=False)
    connection = lifecycle._connect()
    try:
        with connection:
            connection.execute(
                """
                INSERT INTO cleanup_plans (
                    plan_id, state, scan_root, inventory_path,
                    report_json_path, report_markdown_path,
                    expected_release_bytes, metadata_json
                ) VALUES (?, 'planned', '.', ?, ?, ?, ?, ?)
                """,
                (
                    plan_id,
                    inventory_path,
                    _relative(project_root, report_json_path),
                    _relative(project_root, report_markdown_path),
                    expected,
                    _json_text({"legacy_migration_schema": LEGACY_RUN_MIGRATION_SCHEMA}),
                ),
            )
            for item in items:
                metadata = {
                    key: item[key]
                    for key in (
                        "run_ids",
                        "path_kind",
                        "expected_release_bytes",
                        "reproducible_evidence",
                        "legacy_migration_schema",
                        "workflow",
                        "contract_hash",
                        "source_assets",
                    )
                }
                connection.execute(
                    """
                    INSERT INTO cleanup_plan_items (
                        item_id, plan_id, asset_id, cache_key, role,
                        authority_level, original_path, quarantine_path,
                        size_bytes, content_hash, eligibility,
                        blocked_reason, state, metadata_json
                    ) VALUES (?, ?, '', ?, ?, ?, ?, '', ?, ?, 'eligible', '', 'planned', ?)
                    """,
                    (
                        item["item_id"],
                        plan_id,
                        item["cache_key"],
                        item["role"],
                        item["authority_level"],
                        item["original_path"],
                        item["size_bytes"],
                        item["content_hash"],
                        _json_text(metadata),
                    ),
                )
            lifecycle._insert_event(
                connection,
                plan_id,
                None,
                "legacy_plan_created",
                {"expected_release_bytes": expected, "item_count": len(items)},
            )
        report = lifecycle.report(plan_id, connection=connection)
        report["schema_version"] = CLEANUP_REPORT_SCHEMA
        report["storage_policy_version"] = TIF_STORAGE_POLICY_VERSION
        lifecycle._write_report(report)
        return report
    finally:
        connection.close()


def quarantine_legacy_run_caches(
    project_manager,
    *,
    grace_days=DEFAULT_QUARANTINE_GRACE_DAYS,
):
    lifecycle = TifStorageLifecycleManager(project_manager)
    plan = create_legacy_run_cleanup_plan(project_manager)
    return lifecycle.quarantine(plan["plan_id"], grace_days=grace_days)


def _print_result(payload):
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Migrate legacy TIF project storage safely.")
    parser.add_argument("--project", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("analyze-labels")
    commands.add_parser("migrate-labels")
    quarantine = commands.add_parser("quarantine-legacy-runs")
    quarantine.add_argument("--grace-days", type=int, default=DEFAULT_QUARANTINE_GRACE_DAYS)
    args = parser.parse_args(argv)

    manager = TifProjectManager()
    manager.load_project(args.project)
    if not manager.is_sqlite_project():
        raise ValueError("tif_storage_migration_requires_sqlite_project")
    if args.command == "analyze-labels":
        result = {"items": analyze_label_dtype_migration(manager)}
    elif args.command == "migrate-labels":
        result = migrate_label_dtypes(manager)
    else:
        result = quarantine_legacy_run_caches(manager, grace_days=args.grace_days)
    _print_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
