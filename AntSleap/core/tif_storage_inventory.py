"""Read-only TIF project storage inventory and human-auditable reports."""

from __future__ import annotations

import hashlib
import json
import os
from collections import defaultdict
from datetime import datetime, timezone

from .file_integrity import FULL_FILE_ALGORITHM, compute_fingerprint
from .safe_io import atomic_write_json, atomic_write_text
from .sqlite_storage import connect_sqlite_database_readonly
from .tif_integrity_bridge import _iter_volume_assets
from .tif_storage import (
    AUTHORITY_L0,
    AUTHORITY_L1,
    AUTHORITY_L2,
    AUTHORITY_L3,
    TIF_STORAGE_POLICY_VERSION,
    format_bytes,
)


TIF_STORAGE_INVENTORY_SCHEMA = "taxamask_tif_storage_inventory_v1"


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _norm(path):
    return os.path.normcase(os.path.realpath(os.path.abspath(os.fspath(path))))


def _is_link_like(path):
    return os.path.islink(path) or bool(
        getattr(os.path, "isjunction", lambda _path: False)(path)
    )


def _is_within(root, path):
    try:
        return os.path.commonpath([_norm(root), _norm(path)]) == _norm(root)
    except ValueError:
        return False


def _allocated_bytes(stat_result):
    blocks = getattr(stat_result, "st_blocks", None)
    if isinstance(blocks, int) and blocks >= 0:
        return int(blocks * 512)
    return int(stat_result.st_size)


def _authority_for_role(role):
    clean = str(role or "unknown")
    if clean in {"source_volume", "manual_truth", "human_confirmed_label"}:
        return AUTHORITY_L0
    if clean in {
        "working_image", "working_edit", "editable_ai_result",
        "training_image", "training_context",
    }:
        return AUTHORITY_L1
    if clean in {
        "reproducible_cache",
        "quarantined_reproducible_cache",
        "preview_cache",
        "staging",
    }:
        return AUTHORITY_L2
    if clean in {"transaction_temp", "download_partial"}:
        return AUTHORITY_L3
    return AUTHORITY_L0


def _project_path_index(project_manager):
    root = project_manager.project_dir
    index = []
    for item in _iter_volume_assets(project_manager):
        try:
            absolute = project_manager.to_absolute(item.get("path") or "")
        except (TypeError, ValueError):
            continue
        if not absolute or not _is_within(root, absolute):
            continue
        role = str(item.get("role") or "unknown")
        index.append(
            {
                "path": _norm(absolute),
                "role": role,
                "owner_key": str(item.get("owner_key") or ""),
                "authority_level": _authority_for_role(role),
                "classification_reason": "registered_project_asset",
                "include_descendants": True,
            }
        )
    for run in project_manager.project_data.get("runs", []) or []:
        if not isinstance(run, dict):
            continue
        for item in run.get("materializations", []) or []:
            if not isinstance(item, dict):
                continue
            lifecycle = str(item.get("lifecycle") or "")
            status = str(item.get("status") or "")
            if lifecycle != "reproducible_cache" or status not in {
                "verified",
                "completed_reproducible",
            }:
                continue
            paths = []
            run_path = str(item.get("run_path") or "")
            if run_path:
                paths.append((run_path, "registered_run_materialization"))
            cache_path = str(item.get("cache_path") or "")
            if cache_path:
                try:
                    cache_dir = project_manager.to_absolute(cache_path)
                    manifest_path = os.path.join(cache_dir, "materialization.json")
                    with open(manifest_path, "r", encoding="utf-8") as handle:
                        manifest = json.load(handle)
                    artifact_name = str(manifest.get("artifact_name") or "")
                    if artifact_name and os.path.basename(artifact_name) == artifact_name:
                        paths.extend(
                            [
                                (
                                    os.path.join(cache_path, "materialization.json"),
                                    "registered_cache_manifest",
                                ),
                                (
                                    os.path.join(cache_path, artifact_name),
                                    "registered_cache_artifact",
                                ),
                            ]
                        )
                except (OSError, TypeError, ValueError):
                    pass
            for relative_path, reason in paths:
                try:
                    absolute = project_manager.to_absolute(relative_path)
                except (TypeError, ValueError):
                    continue
                if not absolute or not _is_within(root, absolute):
                    continue
                index.append(
                    {
                        "path": _norm(absolute),
                        "role": "reproducible_cache",
                        "owner_key": str(item.get("cache_key") or ""),
                        "authority_level": AUTHORITY_L2,
                        "classification_reason": reason,
                        "include_descendants": False,
                    }
                )
    if project_manager.is_sqlite_project():
        connection = connect_sqlite_database_readonly(
            project_manager.current_database_path
        )
        try:
            rows = connection.execute(
                """
                SELECT plan_id, item_id, cache_key, quarantine_path
                FROM cleanup_plan_items
                WHERE state IN ('quarantined', 'deleting')
                  AND quarantine_path <> ''
                ORDER BY plan_id, original_path
                """
            ).fetchall()
        finally:
            connection.close()
        for plan_id, item_id, cache_key, relative_path in rows:
            try:
                absolute = project_manager.to_absolute(relative_path)
            except (TypeError, ValueError):
                continue
            if not absolute or not _is_within(root, absolute):
                continue
            index.append(
                {
                    "path": _norm(absolute),
                    "role": "quarantined_reproducible_cache",
                    "owner_key": str(cache_key or item_id or plan_id or ""),
                    "authority_level": AUTHORITY_L2,
                    "classification_reason": "registered_cleanup_quarantine",
                    "include_descendants": os.path.isdir(absolute),
                }
            )
    for special_path, role, reason in (
        (
            getattr(project_manager, "current_project_path", ""),
            "project_manifest",
            "project_control_file",
        ),
        (
            getattr(project_manager, "current_database_path", ""),
            "project_sqlite",
            "project_control_file",
        ),
    ):
        if special_path:
            index.append(
                {
                    "path": _norm(special_path),
                    "role": role,
                    "owner_key": role,
                    "authority_level": AUTHORITY_L0,
                    "classification_reason": reason,
                    "include_descendants": False,
                }
            )
    index.sort(key=lambda item: len(item["path"]), reverse=True)
    return index


def _classify_path(project_root, absolute_path, index):
    normalized = _norm(absolute_path)
    for registered in index:
        base = registered["path"]
        if normalized == base or (
            registered.get("include_descendants")
            and normalized.startswith(base + os.sep)
        ):
            return dict(registered)
    return {
        "role": "unknown",
        "owner_key": "",
        "authority_level": AUTHORITY_L0,
        "classification_reason": "unknown_is_protected",
    }


def _digest_group(paths):
    digests = defaultdict(list)
    for path in paths:
        fingerprint = compute_fingerprint(path, FULL_FILE_ALGORITHM)
        digests[fingerprint["digest"]].append(path)
    return [
        {"content_hash": f"sha256:{digest}", "paths": sorted(group)}
        for digest, group in sorted(digests.items())
        if len(group) > 1
    ]


def scan_tif_project_storage(
    project_manager,
    *,
    verify_duplicate_content=False,
    cancel_check=None,
):
    """Scan without following links or changing any project file."""

    root = os.path.abspath(project_manager.project_dir)
    if not os.path.isdir(root):
        raise FileNotFoundError(root)
    index = _project_path_index(project_manager)
    items = []
    logical_bytes = 0
    allocated_bytes = 0
    unique_allocated_bytes = 0
    seen_file_ids = set()
    size_groups = defaultdict(list)
    cancelled = False

    for current_root, dir_names, file_names in os.walk(root, followlinks=False):
        dir_names.sort(key=str.casefold)
        file_names.sort(key=str.casefold)
        safe_dirs = []
        for name in dir_names:
            path = os.path.join(current_root, name)
            if _is_link_like(path):
                classification = _classify_path(root, path, index)
                items.append(
                    {
                        "relative_path": os.path.relpath(path, root).replace("\\", "/"),
                        "entry_kind": "symlink",
                        "logical_bytes": 0,
                        "allocated_bytes": 0,
                        "role": classification["role"],
                        "owner_key": classification["owner_key"],
                        "authority_level": AUTHORITY_L0,
                        "classification_reason": "link_not_followed_protected",
                        "reclaimable": False,
                    }
                )
            else:
                safe_dirs.append(name)
        dir_names[:] = safe_dirs
        for name in file_names:
            if cancel_check and cancel_check():
                cancelled = True
                break
            path = os.path.join(current_root, name)
            if _is_link_like(path):
                classification = {
                    "role": "unknown",
                    "owner_key": "",
                    "authority_level": AUTHORITY_L0,
                    "classification_reason": "link_not_followed_protected",
                }
                kind = "symlink"
                stat_result = os.lstat(path)
                logical = int(stat_result.st_size)
                allocated = _allocated_bytes(stat_result)
            else:
                try:
                    stat_result = os.stat(path, follow_symlinks=False)
                except OSError as exc:
                    items.append(
                        {
                            "relative_path": os.path.relpath(path, root).replace("\\", "/"),
                            "entry_kind": "unreadable",
                            "logical_bytes": 0,
                            "allocated_bytes": 0,
                            "role": "unknown",
                            "owner_key": "",
                            "authority_level": AUTHORITY_L0,
                            "classification_reason": f"stat_failed:{exc}",
                            "reclaimable": False,
                        }
                    )
                    continue
                classification = _classify_path(root, path, index)
                kind = "file"
                logical = int(stat_result.st_size)
                allocated = _allocated_bytes(stat_result)
                size_groups[logical].append(path)
            file_id = (int(stat_result.st_dev), int(stat_result.st_ino))
            unique_bytes = 0 if file_id in seen_file_ids else allocated
            seen_file_ids.add(file_id)
            logical_bytes += logical
            allocated_bytes += allocated
            unique_allocated_bytes += unique_bytes
            items.append(
                {
                    "relative_path": os.path.relpath(path, root).replace("\\", "/"),
                    "entry_kind": kind,
                    "logical_bytes": logical,
                    "allocated_bytes": allocated,
                    "unique_allocated_bytes": unique_bytes,
                    "hardlink_count": int(stat_result.st_nlink),
                    "role": classification["role"],
                    "owner_key": classification["owner_key"],
                    "authority_level": classification["authority_level"],
                    "classification_reason": classification["classification_reason"],
                    "reclaimable": classification["authority_level"] in {AUTHORITY_L2, AUTHORITY_L3},
                }
            )
        if cancelled:
            break

    by_layer = defaultdict(lambda: {"files": 0, "logical_bytes": 0, "allocated_bytes": 0})
    by_role = defaultdict(lambda: {"files": 0, "logical_bytes": 0, "allocated_bytes": 0})
    for item in items:
        for target, key in (
            (by_layer, item["authority_level"]),
            (by_role, item["role"]),
        ):
            target[key]["files"] += 1
            target[key]["logical_bytes"] += int(item.get("logical_bytes") or 0)
            target[key]["allocated_bytes"] += int(item.get("allocated_bytes") or 0)

    quarantine_bytes = sum(
        int(item.get("allocated_bytes") or 0)
        for item in items
        if item.get("classification_reason") == "registered_cleanup_quarantine"
    )

    potential = []
    verified = []
    for size, paths in sorted(size_groups.items()):
        if size <= 0 or len(paths) < 2:
            continue
        relative_paths = [os.path.relpath(path, root).replace("\\", "/") for path in paths]
        potential.append(
            {
                "size_bytes": int(size),
                "paths": sorted(relative_paths),
                "status": "same_size_only_not_proof",
            }
        )
        if verify_duplicate_content:
            verified.extend(_digest_group(paths))

    report = {
        "schema_version": TIF_STORAGE_INVENTORY_SCHEMA,
        "storage_policy_version": TIF_STORAGE_POLICY_VERSION,
        "scanned_at": _now_iso(),
        "scan_root": root,
        "project_id": str(project_manager.project_data.get("project_id") or ""),
        "cancelled": cancelled,
        "read_only": True,
        "summary": {
            "entry_count": len(items),
            "logical_bytes": logical_bytes,
            "allocated_bytes": allocated_bytes,
            "unique_allocated_bytes": unique_allocated_bytes,
            "hardlink_shared_bytes": max(0, allocated_bytes - unique_allocated_bytes),
            "active_allocated_bytes": max(0, allocated_bytes - quarantine_bytes),
            "quarantined_allocated_bytes": quarantine_bytes,
        },
        "by_authority_level": dict(sorted(by_layer.items())),
        "by_role": dict(sorted(by_role.items())),
        "items": items,
        "potential_duplicate_groups": potential,
        "verified_duplicate_groups": verified,
        "notes": [
            "Unknown files are protected as L0.",
            "Same file size is only a candidate signal and never proves duplicate content.",
            "Directory links and symbolic links are not followed.",
            "Unique allocated bytes de-duplicate hardlinks by file identity.",
        ],
    }
    report["inventory_id"] = "inventory_" + hashlib.sha256(
        json.dumps(
            {
                "project_id": report["project_id"],
                "scanned_at": report["scanned_at"],
                "summary": report["summary"],
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:16]
    return report


def inventory_markdown(report):
    summary = report.get("summary") or {}
    lines = [
        "# TIF 存储只读盘点报告",
        "",
        f"- 扫描时间：{report.get('scanned_at', '')}",
        f"- 扫描根目录：`{report.get('scan_root', '')}`",
        f"- 项目 ID：`{report.get('project_id', '')}`",
        f"- 扫描状态：{'已取消，结果不完整' if report.get('cancelled') else '完成'}",
        "- 数据操作：只读；未移动、未压缩、未删除任何文件",
        "",
        "## 总量",
        "",
        "| 项目 | 数值 |",
        "| --- | ---: |",
        f"| 文件/链接条目 | {int(summary.get('entry_count') or 0):,} |",
        f"| 逻辑大小 | {format_bytes(summary.get('logical_bytes'))} |",
        f"| 分配大小 | {format_bytes(summary.get('allocated_bytes'))} |",
        f"| 活动数据分配大小 | {format_bytes(summary.get('active_allocated_bytes'))} |",
        f"| 隔离待释放分配大小 | {format_bytes(summary.get('quarantined_allocated_bytes'))} |",
        f"| 去除 hardlink 重复后的分配大小 | {format_bytes(summary.get('unique_allocated_bytes'))} |",
        "",
        "## 数据分层",
        "",
        "| 层级 | 条目 | 逻辑大小 | 分配大小 | 默认处理 |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for level in (AUTHORITY_L0, AUTHORITY_L1, AUTHORITY_L2, AUTHORITY_L3):
        item = (report.get("by_authority_level") or {}).get(level, {})
        policy = "保护" if level in {AUTHORITY_L0, AUTHORITY_L1} else "仅在通过清理安全门后可隔离"
        lines.append(
            f"| {level} | {int(item.get('files') or 0):,} | "
            f"{format_bytes(item.get('logical_bytes'))} | "
            f"{format_bytes(item.get('allocated_bytes'))} | {policy} |"
        )
    lines.extend(
        [
            "",
            "## 去重说明",
            "",
            f"- 同大小候选组：{len(report.get('potential_duplicate_groups') or [])}",
            f"- 已做完整内容哈希确认的重复组：{len(report.get('verified_duplicate_groups') or [])}",
            "- 同大小、同文件名或同路径结构都不能单独作为删除依据。",
            "- 未知文件统一按 L0 保护。",
            "",
        ]
    )
    return "\n".join(lines)


def write_inventory_reports(report, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    json_path = os.path.join(output_dir, "inventory.json")
    markdown_path = os.path.join(output_dir, "inventory_zh.md")
    atomic_write_json(json_path, report, indent=2, ensure_ascii=False)
    atomic_write_text(markdown_path, inventory_markdown(report), encoding="utf-8")
    return {"json_path": json_path, "markdown_path": markdown_path}
