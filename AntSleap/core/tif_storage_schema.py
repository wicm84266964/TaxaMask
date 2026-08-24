"""SQLite records for TIF asset reuse and recoverable storage cleanup."""

from __future__ import annotations

import json
import time
import uuid


TIF_STORAGE_SCHEMA_VERSION = "taxamask_tif_storage_lifecycle_v1"

REQUIRED_TIF_STORAGE_TABLES = {
    "asset_chunks",
    "asset_relations",
    "run_asset_refs",
    "artifact_materializations",
    "retention_pins",
    "cleanup_plans",
    "cleanup_plan_items",
    "cleanup_events",
}

REQUIRED_TIF_STORAGE_COLUMNS = {
    "asset_chunks": {
        "id", "asset_id", "chunk_key", "relative_path", "size_bytes",
        "hash_algorithm", "digest", "metadata_json", "created_at",
    },
    "asset_relations": {
        "id", "parent_asset_id", "child_asset_id", "relation_type",
        "metadata_json", "created_at",
    },
    "run_asset_refs": {
        "id", "run_id", "asset_id", "owner_key", "role", "content_hash",
        "verified_at", "metadata_json", "created_at",
    },
    "artifact_materializations": {
        "id", "run_id", "cache_key", "format", "cache_path", "run_path",
        "lifecycle", "status", "content_hash", "size_bytes", "link_method",
        "generator", "generator_version", "effective_config_hash",
        "verified_at", "metadata_json", "created_at", "updated_at",
    },
    "retention_pins": {
        "pin_id", "target_kind", "target_id", "reason", "pinned_by",
        "active", "pinned_at", "released_at", "metadata_json",
    },
    "cleanup_plans": {
        "plan_id", "state", "scan_root", "inventory_path", "report_json_path",
        "report_markdown_path", "expected_release_bytes",
        "quarantined_bytes", "deleted_bytes", "grace_until", "lease_owner",
        "lease_expires_at", "metadata_json", "created_at", "updated_at",
    },
    "cleanup_plan_items": {
        "item_id", "plan_id", "asset_id", "cache_key", "role",
        "authority_level", "original_path", "quarantine_path", "size_bytes",
        "content_hash", "eligibility", "blocked_reason", "state",
        "metadata_json", "created_at", "updated_at",
    },
    "cleanup_events": {
        "event_id", "plan_id", "item_id", "event_type", "payload_json",
        "created_at",
    },
}


def initialize_tif_storage_schema(connection):
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS asset_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id TEXT NOT NULL,
            chunk_key TEXT NOT NULL,
            relative_path TEXT NOT NULL DEFAULT '',
            size_bytes INTEGER NOT NULL DEFAULT 0 CHECK (size_bytes >= 0),
            hash_algorithm TEXT NOT NULL DEFAULT 'sha256',
            digest TEXT NOT NULL DEFAULT '',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(asset_id, chunk_key)
        );

        CREATE TABLE IF NOT EXISTS asset_relations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_asset_id TEXT NOT NULL,
            child_asset_id TEXT NOT NULL,
            relation_type TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(parent_asset_id, child_asset_id, relation_type),
            CHECK(parent_asset_id <> child_asset_id)
        );

        CREATE TABLE IF NOT EXISTS run_asset_refs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            asset_id TEXT NOT NULL,
            owner_key TEXT NOT NULL DEFAULT '',
            role TEXT NOT NULL DEFAULT '',
            content_hash TEXT NOT NULL DEFAULT '',
            verified_at TEXT NOT NULL DEFAULT '',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (run_id) REFERENCES tif_runs(run_id) ON DELETE CASCADE,
            UNIQUE(run_id, asset_id, owner_key, role)
        );

        CREATE TABLE IF NOT EXISTS artifact_materializations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            cache_key TEXT NOT NULL,
            format TEXT NOT NULL DEFAULT '',
            cache_path TEXT NOT NULL DEFAULT '',
            run_path TEXT NOT NULL DEFAULT '',
            lifecycle TEXT NOT NULL DEFAULT 'reproducible_cache',
            status TEXT NOT NULL DEFAULT 'verified',
            content_hash TEXT NOT NULL DEFAULT '',
            size_bytes INTEGER NOT NULL DEFAULT 0 CHECK (size_bytes >= 0),
            link_method TEXT NOT NULL DEFAULT '',
            generator TEXT NOT NULL DEFAULT '',
            generator_version TEXT NOT NULL DEFAULT '',
            effective_config_hash TEXT NOT NULL DEFAULT '',
            verified_at TEXT NOT NULL DEFAULT '',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (run_id) REFERENCES tif_runs(run_id) ON DELETE CASCADE,
            UNIQUE(run_id, cache_key, run_path)
        );

        CREATE TABLE IF NOT EXISTS retention_pins (
            pin_id TEXT PRIMARY KEY,
            target_kind TEXT NOT NULL,
            target_id TEXT NOT NULL,
            reason TEXT NOT NULL,
            pinned_by TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
            pinned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            released_at TEXT NOT NULL DEFAULT '',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            UNIQUE(target_kind, target_id, reason)
        );

        CREATE TABLE IF NOT EXISTS cleanup_plans (
            plan_id TEXT PRIMARY KEY,
            state TEXT NOT NULL DEFAULT 'planned',
            scan_root TEXT NOT NULL DEFAULT '',
            inventory_path TEXT NOT NULL DEFAULT '',
            report_json_path TEXT NOT NULL DEFAULT '',
            report_markdown_path TEXT NOT NULL DEFAULT '',
            expected_release_bytes INTEGER NOT NULL DEFAULT 0,
            quarantined_bytes INTEGER NOT NULL DEFAULT 0,
            deleted_bytes INTEGER NOT NULL DEFAULT 0,
            grace_until TEXT NOT NULL DEFAULT '',
            lease_owner TEXT NOT NULL DEFAULT '',
            lease_expires_at TEXT NOT NULL DEFAULT '',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS cleanup_plan_items (
            item_id TEXT PRIMARY KEY,
            plan_id TEXT NOT NULL,
            asset_id TEXT NOT NULL DEFAULT '',
            cache_key TEXT NOT NULL DEFAULT '',
            role TEXT NOT NULL DEFAULT '',
            authority_level TEXT NOT NULL DEFAULT 'L0',
            original_path TEXT NOT NULL,
            quarantine_path TEXT NOT NULL DEFAULT '',
            size_bytes INTEGER NOT NULL DEFAULT 0,
            content_hash TEXT NOT NULL DEFAULT '',
            eligibility TEXT NOT NULL DEFAULT 'blocked',
            blocked_reason TEXT NOT NULL DEFAULT '',
            state TEXT NOT NULL DEFAULT 'planned',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (plan_id) REFERENCES cleanup_plans(plan_id) ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS cleanup_events (
            event_id TEXT PRIMARY KEY,
            plan_id TEXT NOT NULL,
            item_id TEXT,
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (plan_id) REFERENCES cleanup_plans(plan_id) ON DELETE RESTRICT,
            FOREIGN KEY (item_id) REFERENCES cleanup_plan_items(item_id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_asset_chunks_asset ON asset_chunks(asset_id);
        CREATE INDEX IF NOT EXISTS idx_asset_relations_parent ON asset_relations(parent_asset_id);
        CREATE INDEX IF NOT EXISTS idx_asset_relations_child ON asset_relations(child_asset_id);
        CREATE INDEX IF NOT EXISTS idx_run_asset_refs_run ON run_asset_refs(run_id);
        CREATE INDEX IF NOT EXISTS idx_run_asset_refs_asset ON run_asset_refs(asset_id);
        CREATE INDEX IF NOT EXISTS idx_materializations_cache ON artifact_materializations(cache_key);
        CREATE INDEX IF NOT EXISTS idx_materializations_status ON artifact_materializations(lifecycle, status);
        CREATE INDEX IF NOT EXISTS idx_retention_pins_target ON retention_pins(target_kind, target_id, active);
        CREATE INDEX IF NOT EXISTS idx_cleanup_plans_state ON cleanup_plans(state);
        CREATE INDEX IF NOT EXISTS idx_cleanup_items_plan ON cleanup_plan_items(plan_id, state);
        CREATE INDEX IF NOT EXISTS idx_cleanup_events_plan ON cleanup_events(plan_id, created_at);
        """
    )


def validate_tif_storage_schema(connection):
    tables = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    missing = sorted(REQUIRED_TIF_STORAGE_TABLES - tables)
    if missing:
        raise ValueError(f"missing_tif_storage_tables:{','.join(missing)}")
    for table_name, required_columns in sorted(REQUIRED_TIF_STORAGE_COLUMNS.items()):
        columns = {
            str(row[1])
            for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        absent = sorted(required_columns - columns)
        if absent:
            raise ValueError(
                f"missing_tif_storage_columns:{table_name}:{','.join(absent)}"
            )
    return True


def _json_text(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def insert_run_storage_records(connection, run_id, record):
    """Project one run's asset references and materializations into SQLite."""

    ref_count = 0
    materialization_count = 0
    for item in record.get("input_assets", []) or []:
        if not isinstance(item, dict) or not item.get("asset_id"):
            continue
        metadata = {
            key: value
            for key, value in item.items()
            if key
            not in {"asset_id", "owner_key", "role", "content_hash", "verified_at"}
        }
        connection.execute(
            """
            INSERT OR REPLACE INTO run_asset_refs (
                run_id, asset_id, owner_key, role, content_hash,
                verified_at, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(run_id),
                str(item.get("asset_id") or ""),
                str(item.get("owner_key") or ""),
                str(item.get("role") or ""),
                str(item.get("content_hash") or ""),
                str(item.get("verified_at") or ""),
                _json_text(metadata),
            ),
        )
        ref_count += 1

    for item in record.get("materializations", []) or []:
        if not isinstance(item, dict) or not item.get("cache_key"):
            continue
        metadata = {
            key: value
            for key, value in item.items()
            if key
            not in {
                "cache_key", "format", "cache_path", "run_path", "lifecycle",
                "status", "content_hash", "size_bytes", "link_method",
                "generator", "generator_version", "effective_config_hash",
                "verified_at",
            }
        }
        connection.execute(
            """
            INSERT OR REPLACE INTO artifact_materializations (
                run_id, cache_key, format, cache_path, run_path, lifecycle,
                status, content_hash, size_bytes, link_method, generator,
                generator_version, effective_config_hash, verified_at,
                metadata_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                str(run_id),
                str(item.get("cache_key") or ""),
                str(item.get("format") or ""),
                str(item.get("cache_path") or ""),
                str(item.get("run_path") or ""),
                str(item.get("lifecycle") or "reproducible_cache"),
                str(item.get("status") or "verified"),
                str(item.get("content_hash") or ""),
                int(item.get("size_bytes") or 0),
                str(item.get("link_method") or ""),
                str(item.get("generator") or ""),
                str(item.get("generator_version") or ""),
                str(item.get("effective_config_hash") or ""),
                str(item.get("verified_at") or ""),
                _json_text(metadata),
            ),
        )
        materialization_count += 1
    return {
        "run_asset_ref_count": ref_count,
        "materialization_count": materialization_count,
    }


def add_retention_pin(
    connection,
    target_kind,
    target_id,
    reason,
    *,
    pinned_by="",
    metadata=None,
):
    pin_id = f"pin_{uuid.uuid4().hex}"
    connection.execute(
        """
        INSERT INTO retention_pins (
            pin_id, target_kind, target_id, reason, pinned_by, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(target_kind, target_id, reason) DO UPDATE SET
            active = 1,
            pinned_by = excluded.pinned_by,
            released_at = '',
            metadata_json = excluded.metadata_json
        """,
        (
            pin_id,
            str(target_kind),
            str(target_id),
            str(reason),
            str(pinned_by or ""),
            _json_text(dict(metadata or {})),
        ),
    )
    row = connection.execute(
        """
        SELECT pin_id FROM retention_pins
        WHERE target_kind = ? AND target_id = ? AND reason = ?
        """,
        (str(target_kind), str(target_id), str(reason)),
    ).fetchone()
    return str(row[0])


def release_retention_pin(connection, pin_id):
    cursor = connection.execute(
        """
        UPDATE retention_pins
        SET active = 0, released_at = ?
        WHERE pin_id = ? AND active = 1
        """,
        (time.strftime("%Y-%m-%dT%H:%M:%S%z"), str(pin_id)),
    )
    return cursor.rowcount == 1
