"""Dry-run, quarantine, restore, and delayed deletion for reproducible TIF caches."""

from __future__ import annotations

import copy
import json
import os
import shutil
import socket
import uuid
from datetime import datetime, timedelta, timezone

from filelock import FileLock

from .file_integrity import FULL_FILE_ALGORITHM, compute_fingerprint
from .location_registry import require_safe_existing_path
from .safe_io import atomic_write_json, atomic_write_text
from .sqlite_storage import connect_sqlite_database
from .tif_sqlite_schema import validate_tif_project_schema
from .tif_storage import AUTHORITY_L2, TIF_STORAGE_POLICY_VERSION, format_bytes
from .tif_storage_inventory import scan_tif_project_storage, write_inventory_reports
from .tif_storage_schema import add_retention_pin, release_retention_pin


CLEANUP_REPORT_SCHEMA = "taxamask_tif_cleanup_plan_v1"
DEFAULT_QUARANTINE_GRACE_DAYS = 7


def _now():
    return datetime.now(timezone.utc)


def _now_iso():
    return _now().isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_iso(value):
    text = str(value or "").strip().replace("Z", "+00:00")
    if not text:
        return None
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _json_text(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _relative(root, path):
    return os.path.relpath(path, root).replace("\\", "/")


def _is_link_like(path):
    return os.path.islink(path) or bool(
        getattr(os.path, "isjunction", lambda _path: False)(path)
    )


def _safe_relative_target(root, relative_path, *, must_exist=True):
    relative = str(relative_path or "").replace("\\", "/")
    if not relative or os.path.isabs(relative) or relative == ".." or relative.startswith("../"):
        raise ValueError(f"cleanup_path_not_project_relative:{relative}")
    target = os.path.abspath(os.path.join(root, relative))
    try:
        common = os.path.commonpath([os.path.realpath(root), os.path.realpath(target)])
    except ValueError as exc:
        raise ValueError(f"cleanup_path_outside_project:{relative}") from exc
    if os.path.normcase(common) != os.path.normcase(os.path.realpath(root)):
        raise ValueError(f"cleanup_path_outside_project:{relative}")
    if must_exist:
        return require_safe_existing_path(target)
    parent = os.path.dirname(target)
    if os.path.exists(parent):
        require_safe_existing_path(parent)
    return target


def _tree_size(path):
    logical = 0
    releasable = 0
    seen = set()
    for current, dir_names, file_names in os.walk(path, followlinks=False):
        dir_names[:] = sorted(
            name
            for name in dir_names
            if not _is_link_like(os.path.join(current, name))
        )
        for name in sorted(file_names):
            item = os.path.join(current, name)
            if _is_link_like(item):
                continue
            stat_result = os.stat(item, follow_symlinks=False)
            logical += int(stat_result.st_size)
            file_id = (int(stat_result.st_dev), int(stat_result.st_ino))
            if file_id in seen:
                continue
            seen.add(file_id)
            allocated = int(getattr(stat_result, "st_blocks", 0) or 0) * 512
            if allocated <= 0:
                allocated = int(stat_result.st_size)
            if int(stat_result.st_nlink) <= 1:
                releasable += allocated
    return logical, releasable


def _iter_regular_files(path):
    if os.path.isfile(path) and not _is_link_like(path):
        yield path
        return
    for current, dir_names, file_names in os.walk(path, followlinks=False):
        dir_names[:] = sorted(
            name
            for name in dir_names
            if not _is_link_like(os.path.join(current, name))
        )
        for name in sorted(file_names):
            item = os.path.join(current, name)
            if not _is_link_like(item):
                yield item


def _verify_cache_entry(entry_dir, expected_hash):
    manifest_path = os.path.join(entry_dir, "materialization.json")
    with open(manifest_path, "r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    artifact_name = str(manifest.get("artifact_name") or "")
    if not artifact_name or os.path.basename(artifact_name) != artifact_name:
        raise ValueError("cleanup_materialization_artifact_name_invalid")
    expected_names = {"materialization.json", artifact_name}
    observed_names = set(os.listdir(entry_dir))
    unexpected = sorted(observed_names - expected_names)
    missing = sorted(expected_names - observed_names)
    if unexpected or missing:
        raise ValueError(
            "cleanup_cache_entry_members_invalid:"
            f"unexpected={','.join(unexpected)}:missing={','.join(missing)}"
        )
    artifact_path = require_safe_existing_path(os.path.join(entry_dir, artifact_name))
    fingerprint = compute_fingerprint(artifact_path, FULL_FILE_ALGORITHM)
    observed = f"{fingerprint['hash_algorithm']}:{fingerprint['digest']}"
    manifest_hash = str(manifest.get("content_hash") or "")
    if observed != manifest_hash or (expected_hash and observed != expected_hash):
        raise ValueError(f"cleanup_materialization_hash_mismatch:{entry_dir}")
    return manifest, observed


def _verify_materialized_file(path, expected_hash):
    target = require_safe_existing_path(path)
    if not os.path.isfile(target) or _is_link_like(target):
        raise ValueError(f"cleanup_materialization_not_regular_file:{path}")
    fingerprint = compute_fingerprint(target, FULL_FILE_ALGORITHM)
    observed = f"{fingerprint['hash_algorithm']}:{fingerprint['digest']}"
    if not expected_hash or observed != str(expected_hash):
        raise ValueError(f"cleanup_materialization_hash_mismatch:{path}")
    return observed


def _verify_reproducible_tree(path, expected_hash):
    target = require_safe_existing_path(path)
    if not os.path.isdir(target) or _is_link_like(target):
        raise ValueError(f"cleanup_materialization_not_regular_directory:{path}")
    fingerprint = compute_fingerprint(target)
    observed = f"{fingerprint['hash_algorithm']}:{fingerprint['digest']}"
    if not expected_hash or observed != str(expected_hash):
        raise ValueError(f"cleanup_materialization_hash_mismatch:{path}")
    return observed


def _verify_plan_item(path, item):
    if item.get("path_kind") == "cache_entry":
        _manifest, observed = _verify_cache_entry(path, item.get("content_hash"))
        return observed
    if item.get("path_kind") == "legacy_reproducible_tree":
        return _verify_reproducible_tree(path, item.get("content_hash"))
    return _verify_materialized_file(path, item.get("content_hash"))


def _remove_path(path):
    if os.path.isdir(path) and not _is_link_like(path):
        shutil.rmtree(path)
    else:
        os.remove(path)


def cleanup_plan_markdown(report):
    lines = [
        "# TIF 存储清理计划",
        "",
        f"- 计划 ID：`{report.get('plan_id', '')}`",
        f"- 状态：`{report.get('state', '')}`",
        f"- 生成时间：{report.get('created_at', '')}",
        f"- 扫描根目录：`{report.get('scan_root', '')}`",
        f"- 预计释放：{format_bytes(report.get('expected_release_bytes'))}",
        f"- 已隔离：{format_bytes(report.get('quarantined_bytes'))}",
        f"- 已物理删除：{format_bytes(report.get('deleted_bytes'))}",
        f"- 隔离宽限期至：{report.get('grace_until') or '尚未开始'}",
        "",
        "## 安全边界",
        "",
        "- 本计划只允许处理已登记，或经旧数据迁移校验为可再生成且哈希复验通过的 L2 缓存。",
        "- 源体、manual_truth、项目 SQLite、最终模型和未知文件不进入可执行候选。",
        "- 执行阶段先移动到同项目同卷 quarantine，不直接删除。",
        "",
        "## 项目",
        "",
        "| 状态 | 角色 | 路径 | 大小 | 原因 |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for item in report.get("items", []) or []:
        reason = item.get("blocked_reason") or item.get("reproducible_evidence") or ""
        lines.append(
            f"| {item.get('eligibility', '')}/{item.get('state', '')} | "
            f"{item.get('role', '')} | `{item.get('original_path', '')}` | "
            f"{format_bytes(item.get('size_bytes'))} | {reason} |"
        )
    lines.append("")
    return "\n".join(lines)


class TifStorageLifecycleManager:
    def __init__(self, project_manager):
        if not project_manager.is_sqlite_project():
            raise ValueError("tif_storage_lifecycle_requires_sqlite_project")
        self.project_manager = project_manager
        self.project_root = os.path.abspath(project_manager.project_dir)
        self.database_path = os.path.abspath(project_manager.current_database_path)
        self.report_root = os.path.join(self.project_root, "storage_reports")
        self.quarantine_root = os.path.join(self.project_root, ".quarantine")
        self.lock_path = os.path.join(self.project_root, ".taxamask_storage.lock")

    def _connect(self):
        connection = connect_sqlite_database(self.database_path)
        validate_tif_project_schema(connection)
        return connection

    def analyze(self, *, verify_duplicate_content=False, cancel_check=None):
        report = scan_tif_project_storage(
            self.project_manager,
            verify_duplicate_content=verify_duplicate_content,
            cancel_check=cancel_check,
        )
        output_dir = os.path.join(self.report_root, report["inventory_id"])
        paths = write_inventory_reports(report, output_dir)
        report["report_paths"] = {
            key: _relative(self.project_root, value) for key, value in paths.items()
        }
        return report

    def _active_pin_exists(self, connection, cache_key):
        return connection.execute(
            """
            SELECT 1 FROM retention_pins
            WHERE active = 1 AND target_kind IN ('cache_key', 'materialization')
              AND target_id = ?
            LIMIT 1
            """,
            (str(cache_key),),
        ).fetchone() is not None

    def _cache_candidates(self, connection):
        rows = connection.execute(
            """
            SELECT m.cache_key, m.cache_path, m.run_path, m.content_hash,
                   m.size_bytes, m.status, m.run_id, r.result_status
            FROM artifact_materializations m
            JOIN tif_runs r ON r.run_id = m.run_id
            WHERE m.lifecycle = 'reproducible_cache'
            ORDER BY m.cache_key, m.cache_path, m.run_path, m.run_id
            """
        ).fetchall()
        grouped = {}
        for row in rows:
            grouped.setdefault(str(row[0] or ""), []).append(row)
        results = []
        for cache_key, group in sorted(grouped.items()):
            blocked_reason = ""
            eligibility = "eligible"
            cache_paths = sorted({str(row[1] or "") for row in group if row[1]})
            content_hashes = sorted({str(row[3] or "") for row in group if row[3]})
            statuses = {str(row[5] or "") for row in group}
            run_statuses = {str(row[7] or "") for row in group}
            content_hash = content_hashes[0] if len(content_hashes) == 1 else ""
            if self._active_pin_exists(connection, cache_key):
                eligibility = "blocked"
                blocked_reason = "retention_pin_active"
            elif statuses - {"verified", "completed_reproducible"}:
                eligibility = "blocked"
                blocked_reason = "materialization_status_not_verified"
            elif run_statuses - {"success", "completed", "succeeded"}:
                eligibility = "blocked"
                blocked_reason = "materialization_run_not_completed"
            elif len(cache_paths) != 1 or not content_hash:
                eligibility = "blocked"
                blocked_reason = "materialization_identity_inconsistent"

            targets = []
            try:
                if cache_paths:
                    cache_path = cache_paths[0]
                    entry_dir = _safe_relative_target(
                        self.project_root, cache_path, must_exist=True
                    )
                    _verify_cache_entry(entry_dir, content_hash)
                    targets.append(
                        {
                            "path": cache_path,
                            "absolute_path": entry_dir,
                            "path_kind": "cache_entry",
                            "run_ids": sorted({str(row[6] or "") for row in group}),
                        }
                    )
                seen_run_paths = set()
                for row in group:
                    run_path = str(row[2] or "")
                    if not run_path or run_path in seen_run_paths:
                        continue
                    seen_run_paths.add(run_path)
                    absolute = _safe_relative_target(
                        self.project_root, run_path, must_exist=True
                    )
                    _verify_materialized_file(absolute, content_hash)
                    targets.append(
                        {
                            "path": run_path,
                            "absolute_path": absolute,
                            "path_kind": "run_materialization",
                            "run_ids": sorted(
                                {
                                    str(item[6] or "")
                                    for item in group
                                    if str(item[2] or "") == run_path
                                }
                            ),
                        }
                    )
            except Exception as exc:
                eligibility = "blocked"
                blocked_reason = f"cache_verification_failed:{exc}"

            file_identities = {}
            for target_index, target in enumerate(targets):
                logical_bytes = 0
                for file_path in _iter_regular_files(target["absolute_path"]):
                    stat_result = os.stat(file_path, follow_symlinks=False)
                    logical_bytes += int(stat_result.st_size)
                    file_id = (int(stat_result.st_dev), int(stat_result.st_ino))
                    entry = file_identities.setdefault(
                        file_id,
                        {
                            "allocated_bytes": int(
                                (getattr(stat_result, "st_blocks", 0) or 0) * 512
                                or stat_result.st_size
                            ),
                            "hardlink_count": int(stat_result.st_nlink),
                            "target_indexes": [],
                        },
                    )
                    entry["target_indexes"].append(target_index)
                target["size_bytes"] = logical_bytes
                target["expected_release_bytes"] = 0

            for identity in file_identities.values():
                target_indexes = identity["target_indexes"]
                if len(target_indexes) < int(identity["hardlink_count"]):
                    eligibility = "blocked"
                    blocked_reason = "materialization_has_unmanaged_hardlinks"
                    continue
                if target_indexes:
                    targets[target_indexes[-1]]["expected_release_bytes"] += int(
                        identity["allocated_bytes"]
                    )

            if not targets:
                targets = [
                    {
                        "path": cache_paths[0] if cache_paths else "",
                        "path_kind": "cache_entry",
                        "run_ids": sorted({str(row[6] or "") for row in group}),
                        "size_bytes": max(int(row[4] or 0) for row in group),
                        "expected_release_bytes": 0,
                    }
                ]
            for target in targets:
                results.append(
                    {
                        "item_id": f"cleanup_item_{uuid.uuid4().hex}",
                        "asset_id": "",
                        "cache_key": cache_key,
                        "role": "reproducible_cache",
                        "authority_level": AUTHORITY_L2,
                        "original_path": target["path"],
                        "quarantine_path": "",
                        "path_kind": target["path_kind"],
                        "size_bytes": int(target["size_bytes"]),
                        "expected_release_bytes": int(
                            target["expected_release_bytes"]
                        ),
                        "content_hash": content_hash,
                        "eligibility": eligibility,
                        "blocked_reason": blocked_reason,
                        "state": "planned",
                        "run_ids": target["run_ids"],
                        "reproducible_evidence": (
                            "cache manifest + source asset identities + generator version + hash verification"
                            if eligibility == "eligible"
                            else ""
                        ),
                    }
                )
        return results

    def create_cleanup_plan(self, *, inventory=None, cache_keys=None):
        inventory = inventory or self.analyze()
        if inventory.get("cancelled"):
            raise ValueError("cleanup_plan_requires_complete_inventory")
        plan_id = f"cleanup_{_now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        created_at = _now_iso()
        connection = self._connect()
        try:
            items = self._cache_candidates(connection)
            selected_cache_keys = None
            if cache_keys is not None:
                selected_cache_keys = {
                    str(value or "").strip()
                    for value in cache_keys
                    if str(value or "").strip()
                }
                if not selected_cache_keys:
                    raise ValueError("cleanup_plan_requires_selected_cache_keys")
                known_cache_keys = {str(item.get("cache_key") or "") for item in items}
                missing = sorted(selected_cache_keys - known_cache_keys)
                if missing:
                    raise ValueError(
                        "cleanup_plan_cache_keys_missing:" + ",".join(missing)
                    )
                items = [
                    item
                    for item in items
                    if str(item.get("cache_key") or "") in selected_cache_keys
                ]
            expected = sum(
                int(item.get("expected_release_bytes") or 0)
                for item in items
                if item["eligibility"] == "eligible"
            )
            output_dir = os.path.join(self.report_root, plan_id)
            os.makedirs(output_dir, exist_ok=True)
            report_json_path = os.path.join(output_dir, "cleanup_plan.json")
            report_markdown_path = os.path.join(output_dir, "cleanup_plan_zh.md")
            inventory_path = str(
                (inventory.get("report_paths") or {}).get("json_path") or ""
            )
            report = {
                "schema_version": CLEANUP_REPORT_SCHEMA,
                "storage_policy_version": TIF_STORAGE_POLICY_VERSION,
                "plan_id": plan_id,
                "state": "planned",
                "created_at": created_at,
                "updated_at": created_at,
                "scan_root": self.project_root,
                "inventory_path": inventory_path,
                "expected_release_bytes": expected,
                "quarantined_bytes": 0,
                "deleted_bytes": 0,
                "grace_until": "",
                "partial_success": False,
                "items": items,
            }
            with connection:
                connection.execute(
                    """
                    INSERT INTO cleanup_plans (
                        plan_id, state, scan_root, inventory_path,
                        report_json_path, report_markdown_path,
                        expected_release_bytes, metadata_json
                    ) VALUES (?, 'planned', ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        plan_id,
                        _relative(self.project_root, self.project_root),
                        inventory_path,
                        _relative(self.project_root, report_json_path),
                        _relative(self.project_root, report_markdown_path),
                        expected,
                        _json_text(
                            {
                                "inventory_id": inventory.get("inventory_id", ""),
                                "selected_cache_keys": sorted(selected_cache_keys or []),
                            }
                        ),
                    ),
                )
                for item in items:
                    connection.execute(
                        """
                        INSERT INTO cleanup_plan_items (
                            item_id, plan_id, asset_id, cache_key, role,
                            authority_level, original_path, quarantine_path,
                            size_bytes, content_hash, eligibility,
                            blocked_reason, state, metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, '', ?, ?, ?, ?, 'planned', ?)
                        """,
                        (
                            item["item_id"], plan_id, item["asset_id"],
                            item["cache_key"], item["role"],
                            item["authority_level"], item["original_path"],
                            item["size_bytes"], item["content_hash"],
                            item["eligibility"], item["blocked_reason"],
                            _json_text(
                                {
                                    "run_ids": item["run_ids"],
                                    "path_kind": item["path_kind"],
                                    "expected_release_bytes": item["expected_release_bytes"],
                                    "reproducible_evidence": item["reproducible_evidence"],
                                }
                            ),
                        ),
                    )
                self._insert_event(
                    connection, plan_id, None, "plan_created", {"expected_release_bytes": expected}
                )
            self._write_report(report)
            return report
        finally:
            connection.close()

    def _insert_event(self, connection, plan_id, item_id, event_type, payload=None):
        connection.execute(
            """
            INSERT INTO cleanup_events (
                event_id, plan_id, item_id, event_type, payload_json
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                f"cleanup_event_{uuid.uuid4().hex}",
                str(plan_id),
                str(item_id) if item_id else None,
                str(event_type),
                _json_text(dict(payload or {})),
            ),
        )

    def _load_plan(self, connection, plan_id):
        plan = connection.execute(
            "SELECT * FROM cleanup_plans WHERE plan_id = ?", (str(plan_id),)
        ).fetchone()
        if plan is None:
            raise KeyError(f"cleanup_plan_not_found:{plan_id}")
        columns = [item[1] for item in connection.execute("PRAGMA table_info(cleanup_plans)")]
        plan_dict = dict(zip(columns, plan))
        item_columns = [
            item[1] for item in connection.execute("PRAGMA table_info(cleanup_plan_items)")
        ]
        items = [
            dict(zip(item_columns, row))
            for row in connection.execute(
                "SELECT * FROM cleanup_plan_items WHERE plan_id = ? ORDER BY original_path",
                (str(plan_id),),
            ).fetchall()
        ]
        for item in items:
            try:
                metadata = json.loads(item.get("metadata_json") or "{}")
            except (TypeError, ValueError):
                metadata = {}
            item.update(metadata if isinstance(metadata, dict) else {})
        plan_dict["items"] = items
        return plan_dict

    def _write_report(self, report):
        output_dir = os.path.join(self.report_root, report["plan_id"])
        os.makedirs(output_dir, exist_ok=True)
        json_path = os.path.join(output_dir, "cleanup_plan.json")
        markdown_path = os.path.join(output_dir, "cleanup_plan_zh.md")
        report["report_paths"] = {
            "json_path": _relative(self.project_root, json_path),
            "markdown_path": _relative(self.project_root, markdown_path),
        }
        atomic_write_json(
            json_path,
            report,
            indent=2,
            ensure_ascii=False,
        )
        atomic_write_text(
            markdown_path,
            cleanup_plan_markdown(report),
            encoding="utf-8",
        )
        return dict(report["report_paths"])

    def list_cleanup_plans(self, *, states=None, limit=100):
        requested_states = [
            str(value or "").strip() for value in (states or []) if str(value or "").strip()
        ]
        sql = """
            SELECT p.plan_id, p.state, p.created_at, p.updated_at,
                   p.expected_release_bytes, p.quarantined_bytes,
                   p.deleted_bytes, p.grace_until,
                   SUM(CASE WHEN i.state = 'quarantined' THEN 1 ELSE 0 END),
                   COUNT(i.item_id)
            FROM cleanup_plans p
            LEFT JOIN cleanup_plan_items i ON i.plan_id = p.plan_id
        """
        parameters = []
        if requested_states:
            placeholders = ",".join("?" for _ in requested_states)
            sql += f" WHERE p.state IN ({placeholders})"
            parameters.extend(requested_states)
        sql += " GROUP BY p.plan_id ORDER BY p.created_at DESC, p.plan_id DESC LIMIT ?"
        parameters.append(max(1, min(int(limit), 1000)))
        connection = self._connect()
        try:
            rows = connection.execute(sql, parameters).fetchall()
        finally:
            connection.close()
        return [
            {
                "plan_id": str(row[0]),
                "state": str(row[1]),
                "created_at": str(row[2]),
                "updated_at": str(row[3]),
                "expected_release_bytes": int(row[4] or 0),
                "quarantined_bytes": int(row[5] or 0),
                "deleted_bytes": int(row[6] or 0),
                "grace_until": str(row[7] or ""),
                "quarantined_item_count": int(row[8] or 0),
                "item_count": int(row[9] or 0),
            }
            for row in rows
        ]

    def _update_run_materializations(self, cache_key, **updates):
        changed = 0
        for run in self.project_manager.project_data.get("runs", []) or []:
            if not isinstance(run, dict):
                continue
            for item in run.get("materializations", []) or []:
                if isinstance(item, dict) and item.get("cache_key") == cache_key:
                    item.update(updates)
                    changed += 1
        return changed

    def quarantine(self, plan_id, *, grace_days=DEFAULT_QUARANTINE_GRACE_DAYS):
        grace_days = max(1, int(grace_days))
        with FileLock(self.lock_path, timeout=30):
            connection = self._connect()
            project_snapshot = copy.deepcopy(self.project_manager.project_data)
            moved = []
            project_saved = False
            database_committed = False
            try:
                plan = self._load_plan(connection, plan_id)
                if plan["state"] == "quarantined":
                    report = self.report(plan_id, connection=connection)
                    self._write_report(report)
                    return report
                if plan["state"] != "planned":
                    raise ValueError(f"cleanup_plan_not_planned:{plan['state']}")
                eligible = [
                    item for item in plan["items"] if item["eligibility"] == "eligible"
                ]
                for item in eligible:
                    source = _safe_relative_target(
                        self.project_root, item["original_path"], must_exist=False
                    )
                    quarantine_rel = (
                        f".quarantine/{plan_id}/{item['original_path']}"
                    ).replace("//", "/")
                    target = _safe_relative_target(
                        self.project_root, quarantine_rel, must_exist=False
                    )
                    source_exists = os.path.lexists(source)
                    target_exists = os.path.lexists(target)
                    if source_exists and target_exists:
                        raise FileExistsError(
                            f"cleanup_quarantine_source_and_target_exist:{item['item_id']}"
                        )
                    if not source_exists and not target_exists:
                        raise FileNotFoundError(
                            f"cleanup_quarantine_source_and_target_missing:{item['item_id']}"
                        )
                    if source_exists:
                        source = require_safe_existing_path(source)
                        observed = _verify_plan_item(source, item)
                        os.makedirs(os.path.dirname(target), exist_ok=True)
                        os.replace(source, target)
                    else:
                        target = require_safe_existing_path(target)
                        observed = _verify_plan_item(target, item)
                    moved.append((source, target, item, quarantine_rel, observed))

                grace_until = (
                    _now() + timedelta(days=grace_days)
                ).isoformat(timespec="seconds").replace("+00:00", "Z")
                for _source, _target, item, quarantine_rel, _observed in moved:
                    updates = {"status": "quarantined"}
                    if item.get("path_kind") == "cache_entry":
                        updates["cache_path"] = quarantine_rel
                    self._update_run_materializations(item["cache_key"], **updates)
                self.project_manager.save_project()
                project_saved = True
                with connection:
                    for _source, _target, item, quarantine_rel, observed in moved:
                        connection.execute(
                            """
                            UPDATE cleanup_plan_items
                            SET quarantine_path = ?, state = 'quarantined',
                                content_hash = ?, updated_at = CURRENT_TIMESTAMP
                            WHERE item_id = ?
                            """,
                            (quarantine_rel, observed, item["item_id"]),
                        )
                        self._insert_event(
                            connection,
                            plan_id,
                            item["item_id"],
                            "item_quarantined",
                            {"from": item["original_path"], "to": quarantine_rel},
                        )
                    connection.execute(
                        """
                        UPDATE cleanup_plans
                        SET state = 'quarantined', quarantined_bytes = ?,
                            grace_until = ?, lease_owner = '', lease_expires_at = '',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE plan_id = ?
                        """,
                        (
                            sum(
                                int(item.get("expected_release_bytes") or 0)
                                for _, _, item, _, _ in moved
                            ),
                            grace_until,
                            str(plan_id),
                        ),
                    )
                    self._insert_event(
                        connection, plan_id, None, "plan_quarantined", {"grace_until": grace_until}
                    )
                database_committed = True
                report = self.report(plan_id, connection=connection)
                self._write_report(report)
                return report
            except Exception as exc:
                if database_committed:
                    raise
                self.project_manager.project_data = project_snapshot
                rollback_errors = []
                for source, target, _item, _rel, _hash in reversed(moved):
                    if os.path.lexists(target) and not os.path.lexists(source):
                        try:
                            os.makedirs(os.path.dirname(source), exist_ok=True)
                            os.replace(target, source)
                        except OSError as rollback_exc:
                            rollback_errors.append(str(rollback_exc))
                if project_saved:
                    try:
                        self.project_manager.save_project()
                    except Exception as rollback_exc:
                        rollback_errors.append(str(rollback_exc))
                if rollback_errors:
                    raise RuntimeError(
                        "cleanup_quarantine_rollback_failed:"
                        + "|".join(rollback_errors)
                    ) from exc
                raise
            finally:
                connection.close()

    def restore(self, plan_id):
        with FileLock(self.lock_path, timeout=30):
            connection = self._connect()
            project_snapshot = copy.deepcopy(self.project_manager.project_data)
            moved = []
            project_saved = False
            database_committed = False
            try:
                plan = self._load_plan(connection, plan_id)
                if plan["state"] == "restored":
                    report = self.report(plan_id, connection=connection)
                    self._write_report(report)
                    return report
                if plan["state"] != "quarantined":
                    raise ValueError(f"cleanup_plan_not_quarantined:{plan['state']}")
                items = [item for item in plan["items"] if item["state"] == "quarantined"]
                for item in items:
                    source = _safe_relative_target(
                        self.project_root, item["quarantine_path"], must_exist=False
                    )
                    target = _safe_relative_target(
                        self.project_root, item["original_path"], must_exist=False
                    )
                    source_exists = os.path.lexists(source)
                    target_exists = os.path.lexists(target)
                    if source_exists and target_exists:
                        raise FileExistsError(
                            f"cleanup_restore_source_and_target_exist:{item['item_id']}"
                        )
                    if not source_exists and not target_exists:
                        raise FileNotFoundError(
                            f"cleanup_restore_source_and_target_missing:{item['item_id']}"
                        )
                    if source_exists:
                        source = require_safe_existing_path(source)
                        _verify_plan_item(source, item)
                        os.makedirs(os.path.dirname(target), exist_ok=True)
                        os.replace(source, target)
                    else:
                        target = require_safe_existing_path(target)
                        _verify_plan_item(target, item)
                    moved.append((source, target, item))
                    updates = {"status": "verified"}
                    if item.get("path_kind") == "cache_entry":
                        updates["cache_path"] = item["original_path"]
                    self._update_run_materializations(item["cache_key"], **updates)
                self.project_manager.save_project()
                project_saved = True
                with connection:
                    for _source, _target, item in moved:
                        connection.execute(
                            """
                            UPDATE cleanup_plan_items
                            SET state = 'restored', quarantine_path = '',
                                updated_at = CURRENT_TIMESTAMP
                            WHERE item_id = ?
                            """,
                            (item["item_id"],),
                        )
                        self._insert_event(
                            connection, plan_id, item["item_id"], "item_restored", {}
                        )
                    connection.execute(
                        """
                        UPDATE cleanup_plans
                        SET state = 'restored', grace_until = '',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE plan_id = ?
                        """,
                        (str(plan_id),),
                    )
                    self._insert_event(connection, plan_id, None, "plan_restored", {})
                database_committed = True
                report = self.report(plan_id, connection=connection)
                self._write_report(report)
                return report
            except Exception as exc:
                if database_committed:
                    raise
                self.project_manager.project_data = project_snapshot
                rollback_errors = []
                for source, target, _item in reversed(moved):
                    if os.path.lexists(target) and not os.path.lexists(source):
                        try:
                            os.makedirs(os.path.dirname(source), exist_ok=True)
                            os.replace(target, source)
                        except OSError as rollback_exc:
                            rollback_errors.append(str(rollback_exc))
                if project_saved:
                    try:
                        self.project_manager.save_project()
                    except Exception as rollback_exc:
                        rollback_errors.append(str(rollback_exc))
                if rollback_errors:
                    raise RuntimeError(
                        "cleanup_restore_rollback_failed:"
                        + "|".join(rollback_errors)
                    ) from exc
                raise
            finally:
                connection.close()

    def purge(
        self,
        plan_id,
        *,
        confirmation,
        override_grace_period=False,
    ):
        if str(confirmation or "") != str(plan_id):
            raise ValueError("cleanup_purge_confirmation_mismatch")
        with FileLock(self.lock_path, timeout=30):
            connection = self._connect()
            try:
                plan = self._load_plan(connection, plan_id)
                if plan["state"] not in {"quarantined", "deleted"}:
                    raise ValueError(f"cleanup_plan_not_quarantined:{plan['state']}")
                if plan["state"] == "quarantined":
                    grace_until = _parse_iso(plan.get("grace_until"))
                    grace_period_active = grace_until is None or _now() < grace_until
                    if grace_period_active and not override_grace_period:
                        raise ValueError(
                            f"cleanup_grace_period_active:{plan.get('grace_until', '')}"
                        )
                    if grace_period_active:
                        with connection:
                            self._insert_event(
                                connection,
                                plan_id,
                                None,
                                "grace_period_overridden",
                                {
                                    "original_grace_until": plan.get("grace_until", ""),
                                    "reason": "user_confirmed_project_validation",
                                },
                            )

                    # Verify every untouched item before the first irreversible delete.
                    # Items already marked deleting were verified before that durable
                    # transition and may be partially removed after an interrupted run.
                    for item in plan["items"]:
                        if item["state"] != "quarantined":
                            continue
                        target = _safe_relative_target(
                            self.project_root,
                            item["quarantine_path"],
                            must_exist=True,
                        )
                        _verify_plan_item(target, item)

                    for item in plan["items"]:
                        if item["state"] not in {"quarantined", "deleting"}:
                            continue
                        target = _safe_relative_target(
                            self.project_root,
                            item["quarantine_path"],
                            must_exist=item["state"] == "quarantined",
                        )
                        if item["state"] == "quarantined":
                            with connection:
                                cursor = connection.execute(
                                    """
                                    UPDATE cleanup_plan_items
                                    SET state = 'deleting', updated_at = CURRENT_TIMESTAMP
                                    WHERE item_id = ? AND state = 'quarantined'
                                    """,
                                    (item["item_id"],),
                                )
                                if cursor.rowcount != 1:
                                    raise RuntimeError(
                                        f"cleanup_item_state_changed:{item['item_id']}"
                                    )
                                self._insert_event(
                                    connection,
                                    plan_id,
                                    item["item_id"],
                                    "item_delete_started",
                                    {},
                                )
                        if os.path.lexists(target):
                            _remove_path(target)
                        with connection:
                            connection.execute(
                                """
                                UPDATE cleanup_plan_items
                                SET state = 'deleted', updated_at = CURRENT_TIMESTAMP
                                WHERE item_id = ? AND state = 'deleting'
                                """,
                                (item["item_id"],),
                            )
                            self._insert_event(
                                connection,
                                plan_id,
                                item["item_id"],
                                "item_deleted",
                                {},
                            )

                # The manifest is deliberately synchronized from the durable item
                # states. Re-running purge repairs it if a previous save was interrupted.
                plan = self._load_plan(connection, plan_id)
                deleted_items = [
                    item for item in plan["items"] if item["state"] == "deleted"
                ]
                for item in deleted_items:
                    updates = {"status": "deleted"}
                    if item.get("path_kind") == "cache_entry":
                        updates["cache_path"] = ""
                    self._update_run_materializations(item["cache_key"], **updates)
                self.project_manager.save_project()
                deleted = sum(
                    int(item.get("expected_release_bytes") or 0)
                    for item in deleted_items
                )
                with connection:
                    connection.execute(
                        """
                        UPDATE cleanup_plans
                        SET state = 'deleted', deleted_bytes = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE plan_id = ?
                        """,
                        (deleted, str(plan_id)),
                    )
                    self._insert_event(connection, plan_id, None, "plan_deleted", {})
                report = self.report(plan_id, connection=connection)
                self._write_report(report)
                return report
            finally:
                connection.close()

    def pin(self, target_kind, target_id, reason, *, pinned_by=""):
        connection = self._connect()
        try:
            with connection:
                return add_retention_pin(
                    connection,
                    target_kind,
                    target_id,
                    reason,
                    pinned_by=pinned_by,
                    metadata={"host": socket.gethostname()},
                )
        finally:
            connection.close()

    def unpin(self, pin_id):
        connection = self._connect()
        try:
            with connection:
                return release_retention_pin(connection, pin_id)
        finally:
            connection.close()

    def report(self, plan_id, *, connection=None):
        owns_connection = connection is None
        connection = connection or self._connect()
        try:
            plan = self._load_plan(connection, plan_id)
            report = {
                "schema_version": CLEANUP_REPORT_SCHEMA,
                "storage_policy_version": TIF_STORAGE_POLICY_VERSION,
                "plan_id": str(plan["plan_id"]),
                "state": str(plan["state"]),
                "created_at": str(plan["created_at"]),
                "updated_at": str(plan["updated_at"]),
                "scan_root": self.project_root,
                "inventory_path": str(plan.get("inventory_path") or ""),
                "expected_release_bytes": int(plan.get("expected_release_bytes") or 0),
                "quarantined_bytes": int(plan.get("quarantined_bytes") or 0),
                "deleted_bytes": int(plan.get("deleted_bytes") or 0),
                "grace_until": str(plan.get("grace_until") or ""),
                "partial_success": any(
                    item.get("state") == "failed" for item in plan["items"]
                ),
                "items": [
                    {
                        key: value
                        for key, value in item.items()
                        if key not in {"metadata_json"}
                    }
                    for item in plan["items"]
                ],
            }
            return report
        finally:
            if owns_connection:
                connection.close()
