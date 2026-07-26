"""SQLite-backed immutable project data baselines and runtime resolution."""

from __future__ import annotations

import datetime as _datetime
import hashlib
import json
import math
import ntpath
import os
import posixpath
import re
import stat
import threading
import unicodedata
import uuid
import weakref
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .file_integrity import (
    FingerprintCancelled,
    FingerprintError,
    FULL_FILE_ALGORITHM,
    QUICK_FILE_ALGORITHM,
    TREE_ALGORITHM,
    compute_fingerprint,
)
from .project_traceability import validate_traceability_id
from .sqlite_storage import connect_sqlite_database, connect_sqlite_database_readonly


REGISTRY_SCHEMA_VERSION = 1
BASELINE_SNAPSHOT_SCHEMA_VERSION = "taxamask_project_integrity_baseline_v1"
LABEL_SNAPSHOT_SCHEMA_ID = "taxamask_2d_label_snapshot_v1"

REGISTRY_UNINITIALIZED = "uninitialized"
REGISTRY_READY = "ready"
REGISTRY_RECOVERY_REQUIRED = "recovery_required"
REGISTRY_STATUSES = frozenset(
    {REGISTRY_UNINITIALIZED, REGISTRY_READY, REGISTRY_RECOVERY_REQUIRED}
)
VERSION_STATUSES = frozenset({"pending", "committed", "aborted"})
CHANGE_KINDS = frozenset({"set", "tombstone"})
OPERATION_STATUSES = frozenset(
    {
        "prepared",
        "fs_applied",
        "db_committed",
        "finalized",
        "rolled_back",
        "needs_attention",
    }
)
OPERATION_TRANSITIONS = {
    "prepared": frozenset({"fs_applied", "db_committed", "rolled_back", "needs_attention"}),
    "fs_applied": frozenset({"db_committed", "rolled_back", "needs_attention"}),
    "db_committed": frozenset({"finalized", "needs_attention"}),
    "needs_attention": frozenset({"finalized", "rolled_back"}),
    "finalized": frozenset(),
    "rolled_back": frozenset(),
}
PATH_BASES = frozenset({"project_root", "run_root", "export_root", "managed_model_root"})

_HEX_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")
_EMBEDDED_ABSOLUTE_PATH_RE = re.compile(
    r"(?:^|[\s\"'(=])(?:[A-Za-z]:[\\/]|\\\\|/(?:home|Users|tmp|var|etc)/)"
)
_CONTROL_CHARACTER_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SENSITIVE_KEY_RE = re.compile(
    r"(?:^|_)(?:password|passwd|secret|token|api_key|apikey|access_key|"
    r"private_key|command|command_line|argv|username|user_name)(?:$|_)",
    re.IGNORECASE,
)
_SECRET_VALUE_RE = re.compile(
    r"(?i)\b(?:api[_ -]?key|access[_ -]?token|secret|password)\b\s*[:=]\s*\S+"
)
_MEDIA_TYPE_RE = re.compile(r"^[A-Za-z0-9.+-]+/[A-Za-z0-9.+-]+$")

PROTECTED_FULL_HASH_ROLES = frozenset(
    {
        "manual_truth",
        "human_confirmed_label",
        "verified_external_truth",
        "label_schema",
        "training_config",
        "initial_weights",
        "output_weights",
        "model_manifest",
        "source_image",
    }
)

REQUIRED_REGISTRY_TABLES = frozenset(
    {
        "integrity_registry_state",
        "integrity_data_versions",
        "integrity_assets",
        "integrity_asset_revisions",
        "integrity_version_changes",
        "integrity_asset_heads",
        "integrity_locations",
        "integrity_operations",
        "integrity_verification_events",
    }
)
REQUIRED_REGISTRY_COLUMNS = {
    "integrity_registry_state": {
        "registry_id", "schema_version", "project_kind", "project_id", "status",
        "root_data_version_id", "current_data_version_id", "recovery_reason",
        "initialized_at", "updated_at",
    },
    "integrity_data_versions": {
        "data_version_id", "parent_data_version_id", "status", "change_reason",
        "metadata_json", "created_at", "committed_at", "aborted_at",
    },
    "integrity_assets": {
        "asset_id", "owner_kind", "owner_key", "role", "media_type",
        "metadata_json", "created_at",
    },
    "integrity_asset_revisions": {
        "revision_id", "asset_id", "entry_kind", "size_bytes", "mtime_ns",
        "hash_algorithm", "digest", "schema_id", "snapshot_text",
        "metadata_json", "created_at",
    },
    "integrity_version_changes": {
        "data_version_id", "asset_id", "change_kind", "revision_id",
        "metadata_json", "created_at",
    },
    "integrity_asset_heads": {
        "asset_id", "data_version_id", "revision_id", "tombstoned",
    },
    "integrity_locations": {
        "location_id", "asset_id", "location_kind", "path_base",
        "relative_path", "opaque_ref", "is_active", "metadata_json",
        "created_at", "updated_at",
    },
    "integrity_operations": {
        "operation_id", "operation_kind", "status", "target_location_ref",
        "temp_location_ref", "backup_location_ref", "payload_json",
        "error_json", "created_at", "updated_at",
    },
    "integrity_verification_events": {
        "event_id", "data_version_id", "asset_id", "revision_id", "status",
        "observed_entry_kind", "observed_size_bytes", "observed_hash_algorithm",
        "observed_digest", "error_code", "verified_at",
    },
}
REQUIRED_REGISTRY_TRIGGERS = frozenset(
    {
        "trg_integrity_asset_revisions_immutable_update",
        "trg_integrity_asset_revisions_immutable_delete",
        "trg_integrity_version_changes_immutable_update",
        "trg_integrity_version_changes_immutable_delete",
        "trg_integrity_data_versions_terminal_update",
        "trg_integrity_data_versions_terminal_delete",
        "trg_integrity_asset_heads_pending_insert",
        "trg_integrity_asset_heads_pending_update",
        "trg_integrity_asset_heads_immutable_delete",
        "trg_integrity_operations_terminal_update",
        "trg_integrity_operations_terminal_delete",
    }
)


class ProjectIntegrityRegistryError(ValueError):
    def __init__(self, code, summary=None):
        self.code = str(code or "project_integrity_registry_error")
        super().__init__(str(summary or self.code))


@dataclass(frozen=True)
class RegistryVerifiedFile:
    file_id: str
    role: str
    asset_id: str
    revision_id: str
    data_version_id: str
    event_id: str
    verified_at: str
    observed_entry_kind: str
    manifest_entry_kind: str
    observed_size_bytes: int
    observed_mtime_ns: int
    observed_hash_algorithm: str
    observed_digest: str
    locator_kind: str
    path_base: str
    relative_path: str
    external_location_ref: str
    runtime_path: str
    runtime_stat_size_bytes: int
    runtime_stat_mtime_ns: int
    runtime_metadata_digest: str


@dataclass(frozen=True)
class RegistryVerificationClaim:
    batch_id: str
    project_id: str
    data_version_id: str
    files: tuple


@dataclass(frozen=True)
class _RegistryVerificationPayload:
    batch_id: str
    database_path: str
    run_dir: str
    project_id: str
    data_version_id: str
    files: tuple


_REGISTRY_CAPABILITY_MUTEX = threading.Lock()
_ISSUED_REGISTRY_BATCHES = weakref.WeakKeyDictionary()
_ISSUED_REGISTRY_RECEIPTS = weakref.WeakKeyDictionary()


class _OpaqueRegistryCapability:
    __slots__ = ("__weakref__",)

    def __init__(self, *_args, **_kwargs):
        raise ProjectIntegrityRegistryError(
            "registry_verification_capability_not_issued"
        )

    def __setattr__(self, _name, _value):
        raise AttributeError("registry_verification_capability_is_immutable")

    @property
    def consumed(self):
        store = (
            _ISSUED_REGISTRY_BATCHES
            if type(self) is RegistryVerificationBatch
            else _ISSUED_REGISTRY_RECEIPTS
        )
        with _REGISTRY_CAPABILITY_MUTEX:
            return self not in store


class RegistryVerificationBatch(_OpaqueRegistryCapability):
    """Opaque one-use handle for a successful Registry verification."""

    __slots__ = ()


class RegistryVerificationReceipt(_OpaqueRegistryCapability):
    """Opaque one-use handle accepted by the specialized training gate."""

    __slots__ = ()


def _capability_path(path):
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def _new_capability_handle(capability_type, store, payload):
    handle = object.__new__(capability_type)
    with _REGISTRY_CAPABILITY_MUTEX:
        store[handle] = payload
    return handle


def _take_capability(capability, capability_type, store, missing_code):
    if type(capability) is not capability_type:
        _raise(missing_code)
    with _REGISTRY_CAPABILITY_MUTEX:
        payload = store.pop(capability, None)
    if payload is None:
        suffix = (
            "batch_already_consumed"
            if capability_type is RegistryVerificationBatch
            else "receipt_already_consumed"
        )
        _raise(f"registry_verification_{suffix}")
    return payload


def _peek_capability(capability, capability_type, store, missing_code):
    if type(capability) is not capability_type:
        _raise(missing_code)
    with _REGISTRY_CAPABILITY_MUTEX:
        payload = store.get(capability)
    if payload is None:
        suffix = (
            "batch_already_consumed"
            if capability_type is RegistryVerificationBatch
            else "receipt_already_consumed"
        )
        _raise(f"registry_verification_{suffix}")
    return payload


def _copy_verified_file(item):
    return RegistryVerifiedFile(
        **{
            field_name: getattr(item, field_name)
            for field_name in RegistryVerifiedFile.__dataclass_fields__
        }
    )


def _claim_from_payload(payload):
    return RegistryVerificationClaim(
        batch_id=payload.batch_id,
        project_id=payload.project_id,
        data_version_id=payload.data_version_id,
        files=tuple(_copy_verified_file(item) for item in payload.files),
    )


def _raise(code, summary=None):
    raise ProjectIntegrityRegistryError(code, summary)


def _now_iso():
    return _datetime.datetime.now(_datetime.timezone.utc).isoformat(
        timespec="microseconds"
    ).replace("+00:00", "Z")


def _new_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex}"


def _safe_id(value, field_name):
    try:
        return validate_traceability_id(value, field_name)
    except ValueError as exc:
        raise ProjectIntegrityRegistryError(f"invalid_{field_name}") from exc


def _canonical_relative_path(value):
    if not isinstance(value, str):
        _raise("invalid_relative_path")
    text = value.strip().replace("\\", "/")
    if (
        not text
        or "\x00" in text
        or text.startswith("/")
        or _WINDOWS_DRIVE_RE.match(text)
        or ntpath.isabs(text)
        or posixpath.isabs(text)
    ):
        _raise("invalid_relative_path")
    parts = text.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        _raise("invalid_relative_path")
    return "/".join(parts)


def _looks_like_absolute_path(value):
    text = str(value or "").strip()
    return bool(
        text
        and (
            ntpath.isabs(text)
            or posixpath.isabs(text)
            or _EMBEDDED_ABSOLUTE_PATH_RE.search(text)
        )
    )


def _normalise_safe_payload(value, *, field_path="payload"):
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            _raise("unsafe_non_finite_number", field_path)
        return value
    if isinstance(value, str):
        text = unicodedata.normalize("NFC", value)
        if len(text) > 65536 or _CONTROL_CHARACTER_RE.search(text):
            _raise("unsafe_text_value", field_path)
        if _looks_like_absolute_path(text):
            _raise("absolute_path_not_allowed", field_path)
        if _SECRET_VALUE_RE.search(text):
            _raise("secret_value_not_allowed", field_path)
        return text
    if isinstance(value, (list, tuple)):
        return [
            _normalise_safe_payload(item, field_path=f"{field_path}[{index}]")
            for index, item in enumerate(value)
        ]
    if isinstance(value, Mapping):
        result = {}
        for raw_key, item in value.items():
            key = unicodedata.normalize("NFC", str(raw_key or "").strip())
            if not key or _CONTROL_CHARACTER_RE.search(key):
                _raise("unsafe_metadata_key", field_path)
            if _SENSITIVE_KEY_RE.search(key):
                _raise("sensitive_field_not_allowed", f"{field_path}.{key}")
            if key in result:
                _raise("normalised_metadata_key_collision", f"{field_path}.{key}")
            result[key] = _normalise_safe_payload(
                item, field_path=f"{field_path}.{key}"
            )
        return result
    _raise("unsupported_metadata_value", field_path)


def _canonical_json_text(payload, *, field_path="payload"):
    normalised = _normalise_safe_payload(payload, field_path=field_path)
    return json.dumps(
        normalised,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _safe_free_text(value, field_name, *, allow_empty=False, max_length=1024):
    text = _normalise_safe_payload(str(value or "").strip(), field_path=field_name)
    if (not text and not allow_empty) or len(text) > max_length:
        _raise(f"invalid_{field_name}")
    return text


def canonical_snapshot_text(payload):
    if not isinstance(payload, Mapping):
        _raise("snapshot_payload_not_object")
    return _canonical_json_text(dict(payload), field_path="snapshot")


def _text_fingerprint(text):
    encoded = str(text).encode("utf-8")
    return {
        "entry_kind": "file",
        "size_bytes": len(encoded),
        "mtime_ns": None,
        "hash_algorithm": FULL_FILE_ALGORITHM,
        "digest": hashlib.sha256(encoded).hexdigest(),
    }


def _normalise_expected(expected, *, role=""):
    if not isinstance(expected, Mapping):
        _raise("expected_fingerprint_missing")
    entry_kind = str(expected.get("entry_kind") or "")
    algorithm = str(expected.get("hash_algorithm") or "")
    digest = str(expected.get("digest") or "").lower()
    size = expected.get("size_bytes")
    mtime_ns = expected.get("mtime_ns")
    if entry_kind not in {"file", "directory"}:
        _raise("invalid_entry_kind")
    if entry_kind == "file" and algorithm not in {
        FULL_FILE_ALGORITHM,
        QUICK_FILE_ALGORITHM,
    }:
        _raise("invalid_hash_algorithm")
    if entry_kind == "directory" and algorithm != TREE_ALGORITHM:
        _raise("invalid_hash_algorithm")
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        _raise("invalid_expected_size")
    if not _HEX_DIGEST_RE.fullmatch(digest):
        _raise("invalid_expected_digest")
    if str(role or "") in PROTECTED_FULL_HASH_ROLES:
        required = TREE_ALGORITHM if entry_kind == "directory" else FULL_FILE_ALGORITHM
        if algorithm != required:
            _raise("protected_hash_algorithm_invalid")
    if mtime_ns is not None and (
        not isinstance(mtime_ns, int) or isinstance(mtime_ns, bool) or mtime_ns < 0
    ):
        _raise("invalid_expected_mtime")
    return {
        "entry_kind": entry_kind,
        "size_bytes": size,
        "mtime_ns": mtime_ns,
        "hash_algorithm": algorithm,
        "digest": digest,
    }


def initialize_project_integrity_registry_schema(connection):
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS integrity_registry_state (
            registry_id INTEGER PRIMARY KEY CHECK (registry_id = 1),
            schema_version INTEGER NOT NULL,
            project_kind TEXT NOT NULL DEFAULT '',
            project_id TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'uninitialized'
                CHECK (status IN ('uninitialized', 'ready', 'recovery_required')),
            root_data_version_id TEXT NOT NULL DEFAULT '',
            current_data_version_id TEXT NOT NULL DEFAULT '',
            recovery_reason TEXT NOT NULL DEFAULT '',
            initialized_at TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS integrity_data_versions (
            data_version_id TEXT PRIMARY KEY,
            parent_data_version_id TEXT,
            status TEXT NOT NULL CHECK (status IN ('pending', 'committed', 'aborted')),
            change_reason TEXT NOT NULL DEFAULT '',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            committed_at TEXT,
            aborted_at TEXT,
            FOREIGN KEY (parent_data_version_id) REFERENCES integrity_data_versions(data_version_id)
        );

        CREATE TABLE IF NOT EXISTS integrity_assets (
            asset_id TEXT PRIMARY KEY,
            owner_kind TEXT NOT NULL,
            owner_key TEXT NOT NULL,
            role TEXT NOT NULL,
            media_type TEXT NOT NULL DEFAULT '',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            UNIQUE(owner_kind, owner_key, role)
        );

        CREATE TABLE IF NOT EXISTS integrity_asset_revisions (
            revision_id TEXT PRIMARY KEY,
            asset_id TEXT NOT NULL,
            entry_kind TEXT NOT NULL CHECK (entry_kind IN ('file', 'directory')),
            size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
            mtime_ns INTEGER,
            hash_algorithm TEXT NOT NULL,
            digest TEXT NOT NULL,
            schema_id TEXT NOT NULL DEFAULT '',
            snapshot_text TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            FOREIGN KEY (asset_id) REFERENCES integrity_assets(asset_id) ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS integrity_version_changes (
            data_version_id TEXT NOT NULL,
            asset_id TEXT NOT NULL,
            change_kind TEXT NOT NULL CHECK (change_kind IN ('set', 'tombstone')),
            revision_id TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            PRIMARY KEY (data_version_id, asset_id),
            CHECK (
                (change_kind = 'set' AND revision_id IS NOT NULL)
                OR (change_kind = 'tombstone' AND revision_id IS NULL)
            ),
            FOREIGN KEY (data_version_id) REFERENCES integrity_data_versions(data_version_id) ON DELETE RESTRICT,
            FOREIGN KEY (asset_id) REFERENCES integrity_assets(asset_id) ON DELETE RESTRICT,
            FOREIGN KEY (revision_id) REFERENCES integrity_asset_revisions(revision_id) ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS integrity_asset_heads (
            asset_id TEXT PRIMARY KEY,
            data_version_id TEXT NOT NULL,
            revision_id TEXT,
            tombstoned INTEGER NOT NULL DEFAULT 0 CHECK (tombstoned IN (0, 1)),
            CHECK (
                (tombstoned = 0 AND revision_id IS NOT NULL)
                OR (tombstoned = 1 AND revision_id IS NULL)
            ),
            FOREIGN KEY (data_version_id) REFERENCES integrity_data_versions(data_version_id) ON DELETE RESTRICT,
            FOREIGN KEY (asset_id) REFERENCES integrity_assets(asset_id) ON DELETE RESTRICT,
            FOREIGN KEY (revision_id) REFERENCES integrity_asset_revisions(revision_id) ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS integrity_locations (
            location_id TEXT PRIMARY KEY,
            asset_id TEXT NOT NULL,
            location_kind TEXT NOT NULL CHECK (location_kind IN ('managed_relative', 'opaque_ref')),
            path_base TEXT,
            relative_path TEXT,
            opaque_ref TEXT,
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            CHECK (
                (location_kind = 'managed_relative' AND path_base IS NOT NULL
                    AND relative_path IS NOT NULL AND opaque_ref IS NULL)
                OR (location_kind = 'opaque_ref' AND path_base IS NULL
                    AND relative_path IS NULL AND opaque_ref IS NOT NULL)
            ),
            FOREIGN KEY (asset_id) REFERENCES integrity_assets(asset_id) ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS integrity_operations (
            operation_id TEXT PRIMARY KEY,
            operation_kind TEXT NOT NULL,
            status TEXT NOT NULL CHECK (
                status IN ('prepared', 'fs_applied', 'db_committed', 'finalized',
                           'rolled_back', 'needs_attention')
            ),
            target_location_ref TEXT NOT NULL DEFAULT '',
            temp_location_ref TEXT NOT NULL DEFAULT '',
            backup_location_ref TEXT NOT NULL DEFAULT '',
            payload_json TEXT NOT NULL DEFAULT '{}',
            error_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS integrity_verification_events (
            event_id TEXT PRIMARY KEY,
            data_version_id TEXT NOT NULL,
            asset_id TEXT NOT NULL,
            revision_id TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('verified', 'mismatch', 'missing', 'incomplete')),
            observed_entry_kind TEXT,
            observed_size_bytes INTEGER,
            observed_hash_algorithm TEXT,
            observed_digest TEXT,
            error_code TEXT NOT NULL DEFAULT '',
            verified_at TEXT NOT NULL,
            FOREIGN KEY (data_version_id) REFERENCES integrity_data_versions(data_version_id) ON DELETE RESTRICT,
            FOREIGN KEY (asset_id) REFERENCES integrity_assets(asset_id) ON DELETE RESTRICT,
            FOREIGN KEY (revision_id) REFERENCES integrity_asset_revisions(revision_id) ON DELETE RESTRICT
        );

        CREATE INDEX IF NOT EXISTS idx_integrity_assets_owner
            ON integrity_assets(owner_kind, owner_key);
        CREATE INDEX IF NOT EXISTS idx_integrity_revisions_asset
            ON integrity_asset_revisions(asset_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_integrity_heads_version
            ON integrity_asset_heads(data_version_id, tombstoned);
        CREATE INDEX IF NOT EXISTS idx_integrity_locations_asset_active
            ON integrity_locations(asset_id, is_active);
        CREATE INDEX IF NOT EXISTS idx_integrity_verification_version
            ON integrity_verification_events(data_version_id, status);

        CREATE TRIGGER IF NOT EXISTS trg_integrity_asset_revisions_immutable_update
        BEFORE UPDATE ON integrity_asset_revisions
        BEGIN
            SELECT RAISE(ABORT, 'asset_revision_immutable');
        END;

        CREATE TRIGGER IF NOT EXISTS trg_integrity_asset_revisions_immutable_delete
        BEFORE DELETE ON integrity_asset_revisions
        BEGIN
            SELECT RAISE(ABORT, 'asset_revision_immutable');
        END;

        CREATE TRIGGER IF NOT EXISTS trg_integrity_version_changes_immutable_update
        BEFORE UPDATE ON integrity_version_changes
        BEGIN
            SELECT RAISE(ABORT, 'version_change_immutable');
        END;

        CREATE TRIGGER IF NOT EXISTS trg_integrity_version_changes_immutable_delete
        BEFORE DELETE ON integrity_version_changes
        BEGIN
            SELECT RAISE(ABORT, 'version_change_immutable');
        END;

        CREATE TRIGGER IF NOT EXISTS trg_integrity_data_versions_terminal_update
        BEFORE UPDATE ON integrity_data_versions
        WHEN OLD.status IN ('committed', 'aborted')
        BEGIN
            SELECT RAISE(ABORT, 'data_version_immutable');
        END;

        CREATE TRIGGER IF NOT EXISTS trg_integrity_data_versions_terminal_delete
        BEFORE DELETE ON integrity_data_versions
        WHEN OLD.status IN ('committed', 'aborted')
        BEGIN
            SELECT RAISE(ABORT, 'data_version_immutable');
        END;

        CREATE TRIGGER IF NOT EXISTS trg_integrity_asset_heads_pending_insert
        BEFORE INSERT ON integrity_asset_heads
        WHEN COALESCE((
            SELECT status FROM integrity_data_versions
            WHERE data_version_id = NEW.data_version_id
        ), '') != 'pending'
        BEGIN
            SELECT RAISE(ABORT, 'asset_head_requires_pending_version');
        END;

        CREATE TRIGGER IF NOT EXISTS trg_integrity_asset_heads_pending_update
        BEFORE UPDATE ON integrity_asset_heads
        WHEN COALESCE((
            SELECT status FROM integrity_data_versions
            WHERE data_version_id = NEW.data_version_id
        ), '') != 'pending'
        BEGIN
            SELECT RAISE(ABORT, 'asset_head_requires_pending_version');
        END;

        CREATE TRIGGER IF NOT EXISTS trg_integrity_asset_heads_immutable_delete
        BEFORE DELETE ON integrity_asset_heads
        BEGIN
            SELECT RAISE(ABORT, 'asset_head_delete_forbidden');
        END;

        CREATE TRIGGER IF NOT EXISTS trg_integrity_operations_terminal_update
        BEFORE UPDATE ON integrity_operations
        WHEN OLD.status IN ('finalized', 'rolled_back')
        BEGIN
            SELECT RAISE(ABORT, 'operation_terminal');
        END;

        CREATE TRIGGER IF NOT EXISTS trg_integrity_operations_terminal_delete
        BEFORE DELETE ON integrity_operations
        WHEN OLD.status IN ('finalized', 'rolled_back')
        BEGIN
            SELECT RAISE(ABORT, 'operation_terminal');
        END;
        """
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO integrity_registry_state (registry_id, schema_version, status)
        VALUES (1, ?, 'uninitialized')
        """,
        (REGISTRY_SCHEMA_VERSION,),
    )


def validate_project_integrity_registry_schema(connection):
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    tables = {str(row[0]) for row in rows}
    missing = sorted(REQUIRED_REGISTRY_TABLES - tables)
    if missing:
        _raise("missing_integrity_registry_tables", ",".join(missing))
    for table_name, required_columns in REQUIRED_REGISTRY_COLUMNS.items():
        columns = {
            str(row[1])
            for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        missing_columns = sorted(required_columns - columns)
        if missing_columns:
            _raise(
                "missing_integrity_registry_columns",
                f"{table_name}:{','.join(missing_columns)}",
            )
    triggers = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'trigger'"
        ).fetchall()
    }
    missing_triggers = sorted(REQUIRED_REGISTRY_TRIGGERS - triggers)
    if missing_triggers:
        _raise("missing_integrity_registry_triggers", ",".join(missing_triggers))
    row = connection.execute(
        "SELECT schema_version FROM integrity_registry_state WHERE registry_id = 1"
    ).fetchone()
    if row is None or int(row[0] or 0) != REGISTRY_SCHEMA_VERSION:
        _raise("unsupported_integrity_registry_schema_version")
    return True


def sync_registry_identity(connection, project_kind, project_id):
    clean_kind = _safe_id(project_kind, "project_kind")
    clean_project_id = _safe_id(project_id, "project_id")
    validate_project_integrity_registry_schema(connection)
    row = connection.execute(
        "SELECT project_kind, project_id, status FROM integrity_registry_state WHERE registry_id = 1"
    ).fetchone()
    old_kind = str(row[0] or "") if row else ""
    old_project_id = str(row[1] or "") if row else ""
    if old_kind and old_kind != clean_kind:
        _raise("registry_project_kind_mismatch")
    if old_project_id and old_project_id != clean_project_id:
        _raise("registry_project_id_mismatch")
    connection.execute(
        """
        UPDATE integrity_registry_state
        SET project_kind = ?, project_id = ?, updated_at = ?
        WHERE registry_id = 1
        """,
        (clean_kind, clean_project_id, _now_iso()),
    )


def registry_state(connection):
    validate_project_integrity_registry_schema(connection)
    row = connection.execute(
        """
        SELECT schema_version, project_kind, project_id, status,
               root_data_version_id, current_data_version_id, recovery_reason,
               initialized_at, updated_at
        FROM integrity_registry_state WHERE registry_id = 1
        """
    ).fetchone()
    if row is None:
        _raise("integrity_baseline_missing")
    keys = (
        "schema_version",
        "project_kind",
        "project_id",
        "status",
        "root_data_version_id",
        "current_data_version_id",
        "recovery_reason",
        "initialized_at",
        "updated_at",
    )
    return dict(zip(keys, row))


def _ensure_asset(connection, entry):
    owner_kind = _safe_id(entry.get("owner_kind"), "owner_kind")
    owner_key = _safe_free_text(entry.get("owner_key"), "owner_key")
    role = _safe_id(entry.get("role"), "asset_role")
    media_type = _safe_free_text(
        entry.get("media_type"), "media_type", allow_empty=True, max_length=255
    )
    if media_type and not _MEDIA_TYPE_RE.fullmatch(media_type):
        _raise("invalid_media_type")
    row = connection.execute(
        """
        SELECT asset_id FROM integrity_assets
        WHERE owner_kind = ? AND owner_key = ? AND role = ?
        """,
        (owner_kind, owner_key, role),
    ).fetchone()
    if row:
        return str(row[0])
    asset_id = _safe_id(entry.get("asset_id") or _new_id("asset"), "asset_id")
    connection.execute(
        """
        INSERT INTO integrity_assets (
            asset_id, owner_kind, owner_key, role, media_type, metadata_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            asset_id,
            owner_kind,
            owner_key,
            role,
            media_type,
            _canonical_json_text(
                dict(entry.get("asset_metadata") or {}), field_path="asset_metadata"
            ),
            _now_iso(),
        ),
    )
    return asset_id


def _normalise_location(location):
    if location is None:
        return None
    if not isinstance(location, Mapping):
        _raise("invalid_asset_location")
    location_kind = str(location.get("location_kind") or "managed_relative")
    location_id = _safe_id(
        location.get("location_id") or _new_id("location"), "location_id"
    )
    if location_kind == "managed_relative":
        path_base = str(location.get("path_base") or "")
        if path_base not in PATH_BASES or path_base == "run_root":
            _raise("invalid_registry_path_base")
        relative_path = _canonical_relative_path(location.get("relative_path"))
        opaque_ref = None
    elif location_kind == "opaque_ref":
        path_base = None
        relative_path = None
        opaque_ref = _safe_id(location.get("opaque_ref"), "opaque_location_ref")
    else:
        _raise("invalid_location_kind")
    return {
        "location_id": location_id,
        "location_kind": location_kind,
        "path_base": path_base,
        "relative_path": relative_path,
        "opaque_ref": opaque_ref,
        "metadata_json": _canonical_json_text(
            dict(location.get("metadata") or {}), field_path="location_metadata"
        ),
    }


def _active_location(connection, asset_id):
    row = connection.execute(
        """
        SELECT location_id, location_kind, path_base, relative_path,
               opaque_ref, metadata_json
        FROM integrity_locations
        WHERE asset_id = ? AND is_active = 1
        ORDER BY created_at DESC, location_id DESC
        LIMIT 1
        """,
        (asset_id,),
    ).fetchone()
    if not row:
        return None
    return {
        "location_id": str(row[0]),
        "location_kind": str(row[1]),
        "path_base": row[2],
        "relative_path": row[3],
        "opaque_ref": row[4],
        "metadata_json": str(row[5] or "{}"),
    }


def _revision_location(
    connection,
    asset_id,
    revision_id,
    *,
    data_version_id=None,
    prefer_active=False,
):
    """Resolve a revision's location without letting a later relocation rewrite history.

    Locations are intentionally kept outside the immutable revision table so a
    same-content relocation can update the current project without creating a
    new data version.  Historical snapshots therefore need an as-of lookup:
    the location that introduced a revision is used for that revision's own
    data version, while a later inherited data version may use a relocation
    that happened before that version was created.  The current snapshot is
    explicitly allowed to use the active location.
    """
    revision = connection.execute(
        """
        SELECT created_at FROM integrity_asset_revisions
        WHERE asset_id = ? AND revision_id = ?
        """,
        (asset_id, revision_id),
    ).fetchone()
    if not revision:
        return None
    next_revision = connection.execute(
        """
        SELECT MIN(created_at) FROM integrity_asset_revisions
        WHERE asset_id = ? AND created_at > ?
        """,
        (asset_id, str(revision[0])),
    ).fetchone()
    rows = connection.execute(
        """
        SELECT location_id, location_kind, path_base, relative_path,
               opaque_ref, metadata_json, created_at
        FROM integrity_locations
        WHERE asset_id = ?
        ORDER BY created_at DESC, location_id DESC
        """,
        (asset_id,),
    ).fetchall()

    def payload(row):
        return {
            "location_id": str(row[0]),
            "location_kind": str(row[1]),
            "path_base": row[2],
            "relative_path": row[3],
            "opaque_ref": row[4],
        }

    parsed_rows = []
    for row in rows:
        try:
            metadata = json.loads(str(row[5] or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            metadata = {}
        parsed_rows.append((row, metadata))

    # The live project must follow the active location, including a
    # same-content relocation that deliberately did not advance data_version.
    if prefer_active:
        active = connection.execute(
            """
            SELECT location_id, location_kind, path_base, relative_path,
                   opaque_ref, metadata_json, created_at
            FROM integrity_locations
            WHERE asset_id = ? AND is_active = 1
            ORDER BY created_at DESC, location_id DESC
            LIMIT 1
            """,
            (asset_id,),
        ).fetchone()
        if active:
            return payload(active)

    matching = [
        (row, metadata)
        for row, metadata in parsed_rows
        if str(metadata.get("revision_id") or "") == str(revision_id)
    ]

    if data_version_id and matching:
        target_version = connection.execute(
            """
            SELECT created_at, committed_at
            FROM integrity_data_versions
            WHERE data_version_id = ?
            """,
            (str(data_version_id),),
        ).fetchone()
        origin_version = connection.execute(
            """
            SELECT data_version_id
            FROM integrity_version_changes
            WHERE asset_id = ? AND revision_id = ? AND change_kind = 'set'
            ORDER BY created_at ASC, data_version_id ASC
            LIMIT 1
            """,
            (asset_id, str(revision_id)),
        ).fetchone()
        origin_id = str(origin_version[0]) if origin_version else ""

        # A revision's own data version is its immutable point-in-time
        # snapshot.  Prefer the non-alias location that was registered with
        # that revision, even if a later relocation now has the same revision
        # id in the table.
        if origin_id and origin_id == str(data_version_id):
            original = [
                (row, metadata)
                for row, metadata in matching
                if not bool(metadata.get("same_content_alias"))
            ]
            if original:
                row, _metadata = min(
                    original,
                    key=lambda item: (str(item[0][6] or ""), str(item[0][0])),
                )
                return payload(row)

        # For a later historical version, a relocation is valid when it was
        # recorded before that version was created.  This preserves a moved
        # location for an inherited asset without allowing relocations that
        # happened afterwards to rewrite the old snapshot.
        as_of = str((target_version or [""])[0] or "")
        if as_of:
            eligible = [
                (row, metadata)
                for row, metadata in matching
                if str(row[6] or "") <= as_of
            ]
            if eligible:
                row, _metadata = max(
                    eligible,
                    key=lambda item: (str(item[0][6] or ""), str(item[0][0])),
                )
                return payload(row)

        # Legacy databases may have location rows without reliable timestamps
        # or origin metadata.  Keep the first non-alias location as the safest
        # historical fallback.
        original = [
            (row, metadata)
            for row, metadata in matching
            if not bool(metadata.get("same_content_alias"))
        ]
        if original:
            row, _metadata = min(
                original,
                key=lambda item: (str(item[0][6] or ""), str(item[0][0])),
            )
            return payload(row)

    # Preserve the pre-versioned registry fallback for old rows and callers
    # that do not provide a data-version context.
    if matching:
        return payload(matching[0][0])

    revision_created = str(revision[0])
    next_created = str((next_revision or [""])[0] or "")
    for row, _metadata in parsed_rows:
        created = str(row[6] or "")
        if created >= revision_created and (
            not next_created or created < next_created
        ):
            return payload(row)
    return None


def _same_location(current, prepared):
    if not current or not prepared:
        return current is prepared
    return all(
        current.get(key) == prepared.get(key)
        for key in (
            "location_kind",
            "path_base",
            "relative_path",
            "opaque_ref",
        )
    )


def _insert_location(
    connection,
    asset_id,
    location,
    *,
    revision_id="",
    digest="",
    data_version_id="",
    same_content_alias=False,
):
    prepared_location = dict(location) if isinstance(location, Mapping) else location
    if isinstance(prepared_location, dict) and revision_id:
        metadata = dict(prepared_location.get("metadata") or {})
        metadata.update(
            {
                "revision_id": str(revision_id),
                "digest": str(digest or ""),
                "data_version_id": str(data_version_id or ""),
                "same_content_alias": bool(same_content_alias),
            }
        )
        prepared_location["metadata"] = metadata
    prepared = _normalise_location(prepared_location)
    if prepared is None:
        return None
    connection.execute(
        "UPDATE integrity_locations SET is_active = 0, updated_at = ? WHERE asset_id = ?",
        (_now_iso(), asset_id),
    )
    connection.execute(
        """
        INSERT INTO integrity_locations (
            location_id, asset_id, location_kind, path_base, relative_path,
            opaque_ref, metadata_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            prepared["location_id"],
            asset_id,
            prepared["location_kind"],
            prepared["path_base"],
            prepared["relative_path"],
            prepared["opaque_ref"],
            prepared["metadata_json"],
            _now_iso(),
            _now_iso(),
        ),
    )
    return prepared["location_id"]


def _insert_revision(connection, asset_id, entry):
    snapshot_text = entry.get("snapshot_text")
    if snapshot_text is not None:
        try:
            snapshot_payload = json.loads(str(snapshot_text))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ProjectIntegrityRegistryError("snapshot_json_invalid") from exc
        if not isinstance(snapshot_payload, Mapping):
            _raise("snapshot_payload_not_object")
        canonical_text = canonical_snapshot_text(snapshot_payload)
        if str(snapshot_text) != canonical_text:
            _raise("snapshot_text_not_canonical")
        snapshot_text = canonical_text
        expected = _text_fingerprint(snapshot_text)
    else:
        expected = _normalise_expected(
            entry.get("expected"), role=entry.get("role")
        )
    expected = _normalise_expected(expected, role=entry.get("role"))
    schema_id = (
        _safe_id(entry.get("schema_id"), "schema_id")
        if str(entry.get("schema_id") or "").strip()
        else ""
    )
    if snapshot_text is not None and not schema_id:
        _raise("snapshot_schema_missing")
    revision_id = _safe_id(
        entry.get("revision_id") or _new_id("revision"), "revision_id"
    )
    connection.execute(
        """
        INSERT INTO integrity_asset_revisions (
            revision_id, asset_id, entry_kind, size_bytes, mtime_ns,
            hash_algorithm, digest, schema_id, snapshot_text, metadata_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            revision_id,
            asset_id,
            expected["entry_kind"],
            expected["size_bytes"],
            expected["mtime_ns"],
            expected["hash_algorithm"],
            expected["digest"],
            schema_id,
            snapshot_text,
            _canonical_json_text(
                dict(entry.get("revision_metadata") or {}),
                field_path="revision_metadata",
            ),
            _now_iso(),
        ),
    )
    return revision_id, expected


def register_project_baseline(
    connection,
    *,
    project_kind,
    project_id,
    data_version_id,
    entries,
    reason="explicit_baseline_registration",
    baseline_metadata=None,
):
    """Register a baseline inside the caller's transaction without committing it."""

    clean_project_id = _safe_id(project_id, "project_id")
    clean_version_id = _safe_id(data_version_id, "project_data_version_id")
    clean_entries = list(entries or [])
    if not clean_entries:
        _raise("baseline_entries_missing")
    metadata = _normalise_safe_payload(
        dict(baseline_metadata or {}), field_path="baseline_metadata"
    )
    raw_legacy_count = metadata.get("legacy_truth_count", 0)
    if isinstance(raw_legacy_count, bool):
        _raise("invalid_legacy_truth_count")
    try:
        legacy_truth_count = int(raw_legacy_count)
    except (TypeError, ValueError) as exc:
        raise ProjectIntegrityRegistryError("invalid_legacy_truth_count") from exc
    if legacy_truth_count < 0:
        _raise("invalid_legacy_truth_count")
    legacy_attestation = metadata.get("legacy_truth_attestation", False)
    if not isinstance(legacy_attestation, bool):
        _raise("invalid_legacy_truth_attestation")
    if legacy_truth_count and not legacy_attestation:
        _raise("legacy_truth_attestation_required")
    metadata["legacy_truth_count"] = legacy_truth_count
    metadata["legacy_truth_attestation"] = legacy_attestation
    validate_project_integrity_registry_schema(connection)
    sync_registry_identity(connection, project_kind, clean_project_id)
    state = registry_state(connection)
    if state["status"] != REGISTRY_UNINITIALIZED:
        _raise("integrity_baseline_already_registered")
    stamp = _now_iso()
    connection.execute(
        """
        INSERT INTO integrity_data_versions (
            data_version_id, parent_data_version_id, status, change_reason,
            metadata_json, created_at
        ) VALUES (?, NULL, 'pending', ?, ?, ?)
        """,
        (
            clean_version_id,
            _safe_id(reason, "change_reason"),
            _canonical_json_text(metadata, field_path="baseline_metadata"),
            stamp,
        ),
    )
    seen_assets = set()
    for entry in clean_entries:
        if not isinstance(entry, Mapping):
            _raise("baseline_entry_not_object")
        asset_id = _ensure_asset(connection, entry)
        if asset_id in seen_assets:
            _raise("duplicate_baseline_asset")
        seen_assets.add(asset_id)
        revision_id, expected = _insert_revision(connection, asset_id, entry)
        _insert_location(
            connection,
            asset_id,
            entry.get("location"),
            revision_id=revision_id,
            digest=expected["digest"],
            data_version_id=clean_version_id,
        )
        connection.execute(
            """
            INSERT INTO integrity_version_changes (
                data_version_id, asset_id, change_kind, revision_id, metadata_json, created_at
            ) VALUES (?, ?, 'set', ?, '{}', ?)
            """,
            (clean_version_id, asset_id, revision_id, stamp),
        )
        connection.execute(
            """
            INSERT INTO integrity_asset_heads (asset_id, data_version_id, revision_id, tombstoned)
            VALUES (?, ?, ?, 0)
            """,
            (asset_id, clean_version_id, revision_id),
        )
    connection.execute(
        """
        UPDATE integrity_data_versions
        SET status = 'committed', committed_at = ?
        WHERE data_version_id = ? AND status = 'pending'
        """,
        (stamp, clean_version_id),
    )
    updated = connection.execute(
        """
        UPDATE integrity_registry_state
        SET status = 'ready', root_data_version_id = ?, current_data_version_id = ?,
            recovery_reason = '', initialized_at = ?, updated_at = ?
        WHERE registry_id = 1 AND status = 'uninitialized'
        """,
        (clean_version_id, clean_version_id, stamp, stamp),
    )
    if updated.rowcount != 1:
        _raise("integrity_baseline_concurrent_update")
    _insert_finalized_operation(
        connection,
        "baseline_registration",
        payload={
            "data_version_id": clean_version_id,
            "entry_count": len(clean_entries),
            "legacy_truth_count": legacy_truth_count,
            "legacy_truth_attestation": legacy_attestation,
        },
    )
    return get_registry_version_snapshot(connection, clean_version_id)


def _current_head(connection, asset_id):
    return connection.execute(
        """
        SELECT h.revision_id, h.tombstoned, r.digest, r.size_bytes,
               r.hash_algorithm, r.entry_kind, a.role
        FROM integrity_asset_heads h
        JOIN integrity_assets a ON a.asset_id = h.asset_id
        LEFT JOIN integrity_asset_revisions r ON r.revision_id = h.revision_id
        WHERE h.asset_id = ?
        """,
        (asset_id,),
    ).fetchone()


def commit_project_data_version(
    connection,
    *,
    project_id,
    parent_data_version_id,
    new_data_version_id,
    changes,
    reason,
):
    """Commit immutable changes inside the caller's existing SQLite transaction."""

    clean_project_id = _safe_id(project_id, "project_id")
    parent_id = _safe_id(parent_data_version_id, "parent_data_version_id")
    new_id = _safe_id(new_data_version_id, "project_data_version_id")
    clean_changes = list(changes or [])
    state = registry_state(connection)
    if state["status"] != REGISTRY_READY:
        _raise("integrity_baseline_missing")
    if state["project_id"] != clean_project_id:
        _raise("registry_project_id_mismatch")
    if state["current_data_version_id"] != parent_id:
        _raise("data_version_compare_and_swap_failed")

    prepared = []
    relocations = []
    for change in clean_changes:
        if not isinstance(change, Mapping):
            _raise("version_change_not_object")
        kind = str(change.get("change_kind") or "set")
        if kind not in CHANGE_KINDS:
            _raise("invalid_change_kind")
        asset_id = _ensure_asset(connection, change)
        current = _current_head(connection, asset_id)
        if kind == "tombstone":
            if not current or int(current[1] or 0) == 1:
                continue
            prepared.append((kind, asset_id, None, change))
            continue
        snapshot_text = change.get("snapshot_text")
        expected = (
            _text_fingerprint(str(snapshot_text))
            if snapshot_text is not None
            else _normalise_expected(
                change.get("expected"), role=change.get("role")
            )
        )
        expected = _normalise_expected(expected, role=change.get("role"))
        if (
            current
            and int(current[1] or 0) == 0
            and str(current[2] or "") == expected["digest"]
            and int(current[3] or 0) == expected["size_bytes"]
            and str(current[4] or "") == expected["hash_algorithm"]
            and str(current[5] or "") == expected["entry_kind"]
        ):
            if "location" in change:
                runtime_path = change.get("runtime_path")
                if not runtime_path:
                    _raise("relocation_runtime_path_required")
                relocations.append((asset_id, change.get("location"), runtime_path))
            continue
        prepared.append((kind, asset_id, expected, change))

    relocated = []
    for asset_id, location, runtime_path in relocations:
        result = _relocate_project_asset(
            connection,
            project_id=clean_project_id,
            asset_id=asset_id,
            location=location,
            runtime_path=runtime_path,
        )
        if result["changed"]:
            relocated.append(result)

    if not prepared:
        return {
            "changed": False,
            "data_version_id": parent_id,
            "change_count": 0,
            "location_change_count": len(relocated),
        }

    stamp = _now_iso()
    connection.execute(
        """
        INSERT INTO integrity_data_versions (
            data_version_id, parent_data_version_id, status, change_reason,
            metadata_json, created_at
        ) VALUES (?, ?, 'pending', ?, '{}', ?)
        """,
        (new_id, parent_id, _safe_id(reason, "change_reason"), stamp),
    )
    for kind, asset_id, _expected, change in prepared:
        if kind == "tombstone":
            revision_id = None
            tombstoned = 1
        else:
            revision_id, actual = _insert_revision(connection, asset_id, change)
            tombstoned = 0
            if "location" in change:
                _insert_location(
                    connection,
                    asset_id,
                    change.get("location"),
                    revision_id=revision_id,
                    digest=actual["digest"],
                    data_version_id=new_id,
                )
        connection.execute(
            """
            INSERT INTO integrity_version_changes (
                data_version_id, asset_id, change_kind, revision_id,
                metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                new_id,
                asset_id,
                kind,
                revision_id,
                _canonical_json_text(
                    dict(change.get("change_metadata") or {}),
                    field_path="change_metadata",
                ),
                stamp,
            ),
        )
        connection.execute(
            """
            INSERT INTO integrity_asset_heads (asset_id, data_version_id, revision_id, tombstoned)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(asset_id) DO UPDATE SET
                data_version_id = excluded.data_version_id,
                revision_id = excluded.revision_id,
                tombstoned = excluded.tombstoned
            """,
            (asset_id, new_id, revision_id, tombstoned),
        )
    connection.execute(
        """
        UPDATE integrity_data_versions
        SET status = 'committed', committed_at = ?
        WHERE data_version_id = ? AND status = 'pending'
        """,
        (stamp, new_id),
    )
    updated = connection.execute(
        """
        UPDATE integrity_registry_state
        SET current_data_version_id = ?, updated_at = ?
        WHERE registry_id = 1 AND status = 'ready'
          AND project_id = ? AND current_data_version_id = ?
        """,
        (new_id, stamp, clean_project_id, parent_id),
    )
    if updated.rowcount != 1:
        _raise("data_version_compare_and_swap_failed")
    return {
        "changed": True,
        "data_version_id": new_id,
        "parent_data_version_id": parent_id,
        "change_count": len(prepared),
        "location_change_count": len(relocated),
    }


def get_registry_version_snapshot(connection, data_version_id=None):
    state = registry_state(connection)
    if state["status"] != REGISTRY_READY:
        _raise("integrity_baseline_missing")
    version_id = _safe_id(
        data_version_id or state["current_data_version_id"], "project_data_version_id"
    )
    version = connection.execute(
        """
        SELECT status, parent_data_version_id, created_at, committed_at
        FROM integrity_data_versions WHERE data_version_id = ?
        """,
        (version_id,),
    ).fetchone()
    if not version or str(version[0] or "") != "committed":
        _raise("integrity_baseline_missing")
    if version_id == state["current_data_version_id"]:
        rows = connection.execute(
            """
        SELECT a.asset_id, a.owner_kind, a.owner_key, a.role, a.media_type,
               r.revision_id, r.entry_kind, r.size_bytes, r.mtime_ns,
               r.hash_algorithm, r.digest, r.schema_id, r.snapshot_text,
               l.location_id, l.location_kind, l.path_base,
               l.relative_path, l.opaque_ref
        FROM integrity_asset_heads h
        JOIN integrity_assets a ON a.asset_id = h.asset_id
        JOIN integrity_asset_revisions r ON r.revision_id = h.revision_id
        LEFT JOIN integrity_locations l ON l.asset_id = a.asset_id AND l.is_active = 1
        WHERE h.tombstoned = 0
        ORDER BY a.role, a.owner_kind, a.owner_key, a.asset_id
            """
        ).fetchall()
    else:
        rows = connection.execute(
            """
        WITH RECURSIVE version_lineage(data_version_id, depth) AS (
            SELECT ?, 0
            UNION ALL
            SELECT v.parent_data_version_id, version_lineage.depth + 1
            FROM integrity_data_versions v
            JOIN version_lineage ON v.data_version_id = version_lineage.data_version_id
            WHERE v.parent_data_version_id IS NOT NULL
        ),
        ranked_changes AS (
            SELECT c.asset_id, c.change_kind, c.revision_id,
                   ROW_NUMBER() OVER (
                       PARTITION BY c.asset_id ORDER BY version_lineage.depth
                   ) AS change_rank
            FROM version_lineage
            JOIN integrity_version_changes c
              ON c.data_version_id = version_lineage.data_version_id
        ),
        resolved_heads AS (
            SELECT asset_id, revision_id
            FROM ranked_changes
            WHERE change_rank = 1 AND change_kind = 'set'
        )
        SELECT a.asset_id, a.owner_kind, a.owner_key, a.role, a.media_type,
               r.revision_id, r.entry_kind, r.size_bytes, r.mtime_ns,
               r.hash_algorithm, r.digest, r.schema_id, r.snapshot_text,
               l.location_id, l.location_kind, l.path_base,
               l.relative_path, l.opaque_ref
        FROM resolved_heads h
        JOIN integrity_assets a ON a.asset_id = h.asset_id
        JOIN integrity_asset_revisions r ON r.revision_id = h.revision_id
        LEFT JOIN integrity_locations l ON l.asset_id = a.asset_id AND l.is_active = 1
        ORDER BY a.role, a.owner_kind, a.owner_key, a.asset_id
            """,
            (version_id,),
        ).fetchall()
    files = []
    for row in rows:
        (
            asset_id,
            owner_kind,
            owner_key,
            role,
            media_type,
            revision_id,
            entry_kind,
            size_bytes,
            mtime_ns,
            algorithm,
            digest,
            schema_id,
            snapshot_text,
            location_id,
            location_kind,
            path_base,
            relative_path,
            opaque_ref,
        ) = row
        bound_location = _revision_location(
            connection,
            str(asset_id),
            str(revision_id),
            data_version_id=version_id,
            prefer_active=(version_id == state["current_data_version_id"]),
        )
        if bound_location is not None:
            location_id = bound_location["location_id"]
            location_kind = bound_location["location_kind"]
            path_base = bound_location["path_base"]
            relative_path = bound_location["relative_path"]
            opaque_ref = bound_location["opaque_ref"]
        item = {
            "file_id": str(asset_id),
            "asset_id": str(asset_id),
            "owner_kind": str(owner_kind),
            "owner_key": str(owner_key),
            "role": str(role),
            "media_type": str(media_type or ""),
            "revision_id": str(revision_id),
            "entry_kind": str(entry_kind),
            "size_bytes": int(size_bytes),
            "mtime_ns": int(mtime_ns) if mtime_ns is not None else None,
            "hash_algorithm": str(algorithm),
            "digest": str(digest),
            "data_version_id": version_id,
            "source_kind": "registry_expected",
        }
        if snapshot_text is not None:
            item["materializer"] = {
                "schema_id": str(schema_id or ""),
                "revision_id": str(revision_id),
                "path_base": "run_root",
                "relative_path": f"registry_snapshots/{asset_id}.json",
            }
        elif location_kind == "managed_relative":
            item["location"] = {
                "location_id": str(location_id),
                "location_kind": "managed_relative",
                "path_base": str(path_base),
                "relative_path": str(relative_path),
            }
        elif location_kind == "opaque_ref":
            item["location"] = {
                "location_id": str(location_id),
                "location_kind": "opaque_ref",
                "opaque_ref": str(opaque_ref),
            }
        else:
            _raise("asset_runtime_source_missing")
        if ("location" in item) == ("materializer" in item):
            _raise("asset_runtime_source_ambiguous")
        files.append(item)
    if not files:
        _raise("integrity_baseline_missing")
    return {
        "schema_version": BASELINE_SNAPSHOT_SCHEMA_VERSION,
        "project_kind": str(state["project_kind"]),
        "project_id": str(state["project_id"]),
        "data_version_id": version_id,
        "status": "registered",
        "files": files,
    }


def get_training_baseline_snapshot(database_path, data_version_id=None):
    _require_safe_existing_path(database_path, expected_kind="file")
    connection = connect_sqlite_database_readonly(database_path)
    try:
        validate_project_integrity_registry_schema(connection)
        return get_registry_version_snapshot(connection, data_version_id)
    finally:
        connection.close()


def read_materialized_registry_payloads(
    database_path,
    snapshot,
    *,
    roles=None,
):
    """Read immutable JSON snapshots for selection without touching source files.

    Training selection may need to know whether a label contains a usable
    locator/parts annotation before deciding which source images to hash.  The
    label snapshots are already immutable Registry revisions, so reading them
    directly from SQLite avoids a second file-verification pass while keeping
    selection tied to the requested data version.
    """

    if not isinstance(snapshot, Mapping):
        _raise("integrity_baseline_missing")
    version_id = _safe_id(
        snapshot.get("data_version_id"), "project_data_version_id"
    )
    authoritative = get_training_baseline_snapshot(database_path, version_id)
    if authoritative != dict(snapshot):
        _raise("integrity_baseline_snapshot_stale")
    allowed_roles = (
        {str(value) for value in roles}
        if roles is not None
        else None
    )
    entries = [
        item
        for item in snapshot.get("files", [])
        if isinstance(item.get("materializer"), Mapping)
        and (allowed_roles is None or str(item.get("role") or "") in allowed_roles)
    ]
    if not entries:
        return {}

    revisions = {}
    connection = connect_sqlite_database_readonly(database_path)
    try:
        validate_project_integrity_registry_schema(connection)
        revision_ids = [str(item.get("revision_id") or "") for item in entries]
        for start in range(0, len(revision_ids), 400):
            chunk = revision_ids[start : start + 400]
            placeholders = ",".join("?" for _ in chunk)
            rows = connection.execute(
                f"""
                SELECT revision_id, asset_id, snapshot_text
                FROM integrity_asset_revisions
                WHERE revision_id IN ({placeholders})
                """,
                chunk,
            ).fetchall()
            for row in rows:
                revisions[str(row[0])] = (str(row[1]), row[2])
    finally:
        connection.close()

    payloads = {}
    for entry in entries:
        file_id = str(entry.get("file_id") or "")
        revision_id = str(entry.get("revision_id") or "")
        row = revisions.get(revision_id)
        if row is None or row[0] != str(entry.get("asset_id") or ""):
            _raise("snapshot_materializer_missing")
        snapshot_text = row[1]
        if snapshot_text is None:
            _raise("snapshot_materializer_missing")
        expected = _text_fingerprint(snapshot_text)
        if any(
            expected.get(key) != entry.get(key)
            for key in ("entry_kind", "size_bytes", "hash_algorithm", "digest")
        ):
            _raise("snapshot_digest_mismatch")
        try:
            payload = json.loads(str(snapshot_text))
        except (TypeError, ValueError) as exc:
            raise ProjectIntegrityRegistryError(
                "snapshot_payload_invalid"
            ) from exc
        if canonical_snapshot_text(payload) != str(snapshot_text):
            _raise("snapshot_text_not_canonical")
        payloads[file_id] = payload
    return payloads


def _is_reparse_point(stat_result):
    attributes = int(getattr(stat_result, "st_file_attributes", 0) or 0)
    flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400) or 0x400)
    return bool(attributes & flag)


def _require_safe_entry(path, *, expected_kind=None):
    result = os.lstat(os.fspath(path))
    if stat.S_ISLNK(result.st_mode) or _is_reparse_point(result):
        _raise("filesystem_link_not_allowed")
    if expected_kind == "file" and not stat.S_ISREG(result.st_mode):
        _raise("safe_regular_file_required")
    if expected_kind == "directory" and not stat.S_ISDIR(result.st_mode):
        _raise("safe_directory_required")
    return result


def _absolute_chain(path):
    absolute = os.path.abspath(os.fspath(path))
    drive, tail = os.path.splitdrive(absolute)
    anchor = f"{drive}{os.sep}" if drive else os.sep
    relative = tail.lstrip("\\/")
    current = anchor
    yield current
    for part in [item for item in re.split(r"[\\/]", relative) if item]:
        current = os.path.join(current, part)
        yield current


def _require_safe_existing_path(path, *, expected_kind=None):
    chain = list(_absolute_chain(path))
    for index, current in enumerate(chain):
        is_last = index == len(chain) - 1
        _require_safe_entry(
            current,
            expected_kind=expected_kind if is_last else "directory",
        )
    return os.path.abspath(os.fspath(path))


def _runtime_metadata_snapshot(path, *, expected_kind, cancel_check=None):
    """Capture path identity and tree metadata without rereading file contents."""

    root = _require_safe_existing_path(path, expected_kind=expected_kind)
    digest = hashlib.sha256()
    root_result = None

    def visit(current, relative_path):
        nonlocal root_result
        if cancel_check is not None and cancel_check():
            raise FingerprintCancelled()
        result = _require_safe_entry(current)
        if stat.S_ISREG(result.st_mode):
            entry_kind = "file"
        elif stat.S_ISDIR(result.st_mode):
            entry_kind = "directory"
        else:
            _raise("safe_filesystem_entry_required")
        if root_result is None:
            root_result = result
        mtime_ns = int(
            getattr(result, "st_mtime_ns", int(result.st_mtime * 1_000_000_000))
        )
        record = [
            str(relative_path).replace("\\", "/"),
            entry_kind,
            int(result.st_mode),
            int(result.st_size),
            mtime_ns,
            int(getattr(result, "st_dev", 0) or 0),
            int(getattr(result, "st_ino", 0) or 0),
            int(getattr(result, "st_file_attributes", 0) or 0),
        ]
        digest.update(
            json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode(
                "utf-8"
            )
        )
        digest.update(b"\n")
        if entry_kind == "directory":
            try:
                with os.scandir(current) as iterator:
                    children = sorted(iterator, key=lambda item: item.name)
            except OSError as exc:
                raise ProjectIntegrityRegistryError(
                    "source_metadata_scan_failed"
                ) from exc
            for child in children:
                child_relative = (
                    child.name
                    if not relative_path
                    else f"{relative_path}/{child.name}"
                )
                visit(child.path, child_relative)

    visit(root, "")
    root_kind = "directory" if stat.S_ISDIR(root_result.st_mode) else "file"
    root_mtime_ns = int(
        getattr(
            root_result,
            "st_mtime_ns",
            int(root_result.st_mtime * 1_000_000_000),
        )
    )
    return {
        "entry_kind": root_kind,
        "size_bytes": int(root_result.st_size),
        "mtime_ns": root_mtime_ns,
        "metadata_digest": digest.hexdigest(),
    }


def _require_verified_file_stable(
    item,
    *,
    progress_callback=None,
    cancel_check=None,
):
    current = _runtime_metadata_snapshot(
        item.runtime_path,
        expected_kind=item.observed_entry_kind,
        cancel_check=cancel_check,
    )
    expected = {
        "entry_kind": item.observed_entry_kind,
        "size_bytes": item.runtime_stat_size_bytes,
        "mtime_ns": item.runtime_stat_mtime_ns,
        "metadata_digest": item.runtime_metadata_digest,
    }
    if current != expected:
        _raise(
            "registry_verified_source_changed",
            f"registry_verified_source_changed:{item.file_id}",
        )
    observed = compute_fingerprint(
        item.runtime_path,
        item.observed_hash_algorithm,
        progress_callback=progress_callback,
        cancel_check=cancel_check,
    )
    expected_fingerprint = {
        "entry_kind": item.observed_entry_kind,
        "size_bytes": item.observed_size_bytes,
        "hash_algorithm": item.observed_hash_algorithm,
        "digest": item.observed_digest,
    }
    if not _matches_expected(expected_fingerprint, observed):
        _raise(
            "registry_verified_source_changed",
            f"registry_verified_source_changed:{item.file_id}",
        )


def recheck_registry_verified_files(
    files,
    *,
    detail_progress_callback=None,
    cancel_check=None,
):
    """Recheck run-bound Registry inputs before a successful run is published."""

    verified_files = tuple(files or ())
    if not verified_files or any(
        type(item) is not RegistryVerifiedFile for item in verified_files
    ):
        _raise("registry_verified_files_required")
    total_bytes = sum(max(0, item.observed_size_bytes) for item in verified_files)
    completed_bytes = 0
    for file_index, item in enumerate(verified_files, start=1):
        callback = None
        if detail_progress_callback is not None:
            display_name = os.path.basename(os.path.normpath(item.runtime_path))

            def callback(done, total, *, _item=item, _index=file_index, _name=display_name):
                detail_progress_callback(
                    {
                        "phase": "registry_completion_recheck",
                        "file_index": _index,
                        "file_count": len(verified_files),
                        "file_id": _item.file_id,
                        "role": _item.role,
                        "display_name": _name,
                        "bytes_done": int(done),
                        "bytes_total": int(total),
                        "total_bytes_done": completed_bytes + int(done),
                        "total_bytes": total_bytes,
                    }
                )

        _require_verified_file_stable(
            item,
            progress_callback=callback,
            cancel_check=cancel_check,
        )
        completed_bytes += max(0, item.observed_size_bytes)
    if cancel_check is not None and cancel_check():
        raise FingerprintCancelled()
    return {"status": "verified", "file_count": len(verified_files)}


def _require_safe_existing_components(base, target):
    relative = os.path.relpath(target, base)
    current = base
    for part in [] if relative == "." else relative.split(os.sep):
        current = os.path.join(current, part)
        if not os.path.lexists(current):
            break
        _require_safe_entry(
            current,
            expected_kind="directory" if current != target else None,
        )


def _safe_runtime_target(root, relative_path):
    base = _require_safe_existing_path(root, expected_kind="directory")
    clean = _canonical_relative_path(relative_path)
    target = os.path.abspath(os.path.join(base, *clean.split("/")))
    try:
        if os.path.normcase(os.path.commonpath([base, target])) != os.path.normcase(base):
            _raise("runtime_target_outside_root")
    except ValueError as exc:
        raise ProjectIntegrityRegistryError("runtime_target_outside_root") from exc
    _require_safe_existing_components(base, target)
    return target, clean


def _fsync_directory(path):
    try:
        descriptor = os.open(
            os.fspath(path), os.O_RDONLY | int(getattr(os, "O_BINARY", 0))
        )
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError:
        pass


def _ensure_safe_parent_directories(root, target):
    parent = os.path.dirname(target) or root
    relative = os.path.relpath(parent, root)
    current = root
    for part in [] if relative == "." else relative.split(os.sep):
        current = os.path.join(current, part)
        try:
            os.mkdir(current)
        except FileExistsError:
            pass
        _require_safe_entry(current, expected_kind="directory")
    return parent


def _atomic_write_snapshot(root, path, text):
    root_abs = _require_safe_existing_path(root, expected_kind="directory")
    target = os.path.abspath(os.fspath(path))
    try:
        if os.path.normcase(os.path.commonpath([root_abs, target])) != os.path.normcase(
            root_abs
        ):
            _raise("runtime_target_outside_root")
    except ValueError as exc:
        raise ProjectIntegrityRegistryError("runtime_target_outside_root") from exc
    directory = _ensure_safe_parent_directories(root_abs, target)
    if os.path.lexists(target):
        _require_safe_entry(target, expected_kind="file")
    temp_path = os.path.join(
        directory,
        f".{os.path.basename(target)}.tmp_{uuid.uuid4().hex}",
    )
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= int(getattr(os, "O_BINARY", 0))
    flags |= int(getattr(os, "O_NOFOLLOW", 0))
    descriptor = None
    try:
        descriptor = os.open(temp_path, flags, 0o600)
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or _is_reparse_point(opened):
            _raise("safe_regular_file_required")
        payload = str(text).encode("utf-8")
        offset = 0
        while offset < len(payload):
            written = os.write(descriptor, payload[offset:])
            if written <= 0:
                raise OSError("snapshot_write_incomplete")
            offset += written
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        _require_safe_entry(temp_path, expected_kind="file")
        os.replace(temp_path, target)
        _require_safe_entry(target, expected_kind="file")
        _fsync_directory(directory)
    except Exception:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        try:
            if os.path.lexists(temp_path):
                _require_safe_entry(temp_path, expected_kind="file")
                os.remove(temp_path)
        except OSError:
            pass
        raise


def _matches_expected(expected, observed):
    return all(
        expected.get(key) == observed.get(key)
        for key in ("entry_kind", "size_bytes", "hash_algorithm", "digest")
    )


def _record_verification(connection, version_id, entry, status, observed=None, error_code=""):
    observed = dict(observed or {})
    event_id = _new_id("verify")
    verified_at = _now_iso()
    connection.execute(
        """
        INSERT INTO integrity_verification_events (
            event_id, data_version_id, asset_id, revision_id, status,
            observed_entry_kind, observed_size_bytes, observed_hash_algorithm,
            observed_digest, error_code, verified_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            version_id,
            entry["asset_id"],
            entry["revision_id"],
            status,
            observed.get("entry_kind"),
            observed.get("size_bytes"),
            observed.get("hash_algorithm"),
            observed.get("digest"),
            str(error_code or ""),
            verified_at,
        ),
    )
    return {
        "event_id": event_id,
        "data_version_id": version_id,
        "asset_id": entry["asset_id"],
        "revision_id": entry["revision_id"],
        "status": str(status),
        "observed_entry_kind": observed.get("entry_kind"),
        "observed_size_bytes": observed.get("size_bytes"),
        "observed_mtime_ns": observed.get("mtime_ns"),
        "observed_hash_algorithm": observed.get("hash_algorithm"),
        "observed_digest": observed.get("digest"),
        "error_code": str(error_code or ""),
        "verified_at": verified_at,
    }


def _require_capability_binding(
    payload,
    *,
    database_path,
    run_dir,
    project_id,
    data_version_id,
):
    if payload.database_path != _capability_path(database_path):
        _raise("registry_verification_database_mismatch")
    if payload.run_dir != _capability_path(run_dir):
        _raise("registry_verification_run_mismatch")
    if payload.project_id != str(project_id or ""):
        _raise("registry_verification_project_mismatch")
    if payload.data_version_id != str(data_version_id or ""):
        _raise("registry_verification_data_version_mismatch")


def _require_registry_evidence_rows(payload, selected):
    _require_safe_existing_path(payload.database_path, expected_kind="file")
    _require_safe_existing_path(payload.run_dir, expected_kind="directory")
    connection = connect_sqlite_database_readonly(payload.database_path)
    try:
        validate_project_integrity_registry_schema(connection)
        state = registry_state(connection)
        if state["project_id"] != payload.project_id:
            _raise("registry_verification_project_mismatch")
        authoritative = get_registry_version_snapshot(
            connection, payload.data_version_id
        )
        entries_by_asset = {
            str(entry["asset_id"]): entry for entry in authoritative["files"]
        }
        for item in selected:
            entry = entries_by_asset.get(item.asset_id)
            if entry is None:
                _raise(f"registry_verification_asset_missing:{item.file_id}")
            expected = {
                "file_id": item.file_id,
                "revision_id": item.revision_id,
                "role": item.role,
                "entry_kind": item.observed_entry_kind,
                "size_bytes": item.observed_size_bytes,
                "hash_algorithm": item.observed_hash_algorithm,
                "digest": item.observed_digest,
            }
            if any(entry.get(field) != value for field, value in expected.items()):
                _raise(f"registry_verification_asset_mismatch:{item.file_id}")
            if item.locator_kind == "materialized_snapshot":
                materializer = entry.get("materializer") or {}
                if (
                    item.path_base != "run_root"
                    or materializer.get("relative_path") != item.relative_path
                ):
                    _raise(f"registry_verification_locator_mismatch:{item.file_id}")
            else:
                location = entry.get("location") or {}
                if location.get("location_kind") != item.locator_kind:
                    _raise(f"registry_verification_locator_mismatch:{item.file_id}")
                if item.locator_kind == "managed_relative" and (
                    location.get("path_base") != item.path_base
                    or location.get("relative_path") != item.relative_path
                ):
                    _raise(f"registry_verification_locator_mismatch:{item.file_id}")
                if item.locator_kind == "opaque_ref" and (
                    location.get("opaque_ref") != item.external_location_ref
                ):
                    _raise(f"registry_verification_locator_mismatch:{item.file_id}")

        rows_by_id = {}
        event_ids = [item.event_id for item in selected]
        for offset in range(0, len(event_ids), 400):
            chunk = event_ids[offset : offset + 400]
            placeholders = ",".join("?" for _value in chunk)
            rows = connection.execute(
                f"""
                SELECT event_id, data_version_id, asset_id, revision_id, status,
                       observed_entry_kind, observed_size_bytes,
                       observed_hash_algorithm, observed_digest, error_code,
                       verified_at
                FROM integrity_verification_events
                WHERE event_id IN ({placeholders})
                """,
                tuple(chunk),
            ).fetchall()
            rows_by_id.update({str(row[0]): row for row in rows})
        for item in selected:
            row = rows_by_id.get(item.event_id)
            expected = (
                item.event_id,
                item.data_version_id,
                item.asset_id,
                item.revision_id,
                "verified",
                item.observed_entry_kind,
                item.observed_size_bytes,
                item.observed_hash_algorithm,
                item.observed_digest,
                "",
                item.verified_at,
            )
            if row is None:
                _raise(f"registry_verification_event_missing:{item.file_id}")
            if tuple(row) != expected:
                _raise(f"registry_verification_event_mismatch:{item.file_id}")
    finally:
        connection.close()


def consume_registry_verification_batch(
    batch,
    *,
    database_path,
    run_dir,
    project_id,
    data_version_id,
    selected_file_ids,
):
    """Validate Registry events and exchange a one-use batch for a receipt."""

    payload = _take_capability(
        batch,
        RegistryVerificationBatch,
        _ISSUED_REGISTRY_BATCHES,
        "registry_verification_batch_required",
    )
    _require_capability_binding(
        payload,
        database_path=database_path,
        run_dir=run_dir,
        project_id=project_id,
        data_version_id=data_version_id,
    )
    requested = tuple(str(value or "") for value in selected_file_ids or ())
    if not requested or any(not value for value in requested):
        _raise("registry_verification_selected_files_missing")
    if len(requested) != len(set(requested)):
        _raise("registry_verification_selected_files_duplicate")
    if any(type(item) is not RegistryVerifiedFile for item in payload.files):
        _raise("registry_verification_file_invalid")
    evidence_by_file = {item.file_id: item for item in payload.files}
    if len(evidence_by_file) != len(payload.files):
        _raise("registry_verification_file_duplicate")
    missing = set(requested) - set(evidence_by_file)
    if missing:
        _raise(f"registry_verification_file_missing:{sorted(missing)[0]}")
    selected = tuple(evidence_by_file[file_id] for file_id in requested)
    if len({item.event_id for item in selected}) != len(selected):
        _raise("registry_verification_event_duplicate")
    receipt_payload = _RegistryVerificationPayload(
        batch_id=payload.batch_id,
        database_path=payload.database_path,
        run_dir=payload.run_dir,
        project_id=payload.project_id,
        data_version_id=payload.data_version_id,
        files=selected,
    )
    _require_registry_evidence_rows(receipt_payload, selected)
    return _new_capability_handle(
        RegistryVerificationReceipt,
        _ISSUED_REGISTRY_RECEIPTS,
        receipt_payload,
    )


def inspect_registry_verification_receipt(
    receipt,
    *,
    database_path,
    run_dir,
    project_id,
    data_version_id,
):
    """Return a detached evidence copy without consuming the receipt."""

    payload = _peek_capability(
        receipt,
        RegistryVerificationReceipt,
        _ISSUED_REGISTRY_RECEIPTS,
        "registry_verification_receipt_required",
    )
    _require_capability_binding(
        payload,
        database_path=database_path,
        run_dir=run_dir,
        project_id=project_id,
        data_version_id=data_version_id,
    )
    return _claim_from_payload(payload)


def claim_registry_verification_receipt(
    receipt,
    *,
    database_path,
    run_dir,
    project_id,
    data_version_id,
    detail_progress_callback=None,
    cancel_check=None,
):
    """Consume and revalidate a receipt at the training transition."""

    payload = _take_capability(
        receipt,
        RegistryVerificationReceipt,
        _ISSUED_REGISTRY_RECEIPTS,
        "registry_verification_receipt_required",
    )
    _require_capability_binding(
        payload,
        database_path=database_path,
        run_dir=run_dir,
        project_id=project_id,
        data_version_id=data_version_id,
    )
    _require_registry_evidence_rows(payload, payload.files)
    files = tuple(payload.files)
    total_bytes = sum(max(0, item.observed_size_bytes) for item in files)
    completed_bytes = 0
    for file_index, item in enumerate(files, start=1):
        callback = None
        if detail_progress_callback is not None:
            display_name = os.path.basename(os.path.normpath(item.runtime_path))

            def callback(done, total, *, _item=item, _index=file_index, _name=display_name):
                detail_progress_callback(
                    {
                        "phase": "registry_final_recheck",
                        "file_index": _index,
                        "file_count": len(files),
                        "file_id": _item.file_id,
                        "role": _item.role,
                        "display_name": _name,
                        "bytes_done": int(done),
                        "bytes_total": int(total),
                        "total_bytes_done": total_bytes + completed_bytes + int(done),
                        "total_bytes": total_bytes * 2,
                    }
                )

        _require_verified_file_stable(
            item,
            progress_callback=callback,
            cancel_check=cancel_check,
        )
        completed_bytes += max(0, item.observed_size_bytes)
    if cancel_check is not None and cancel_check():
        raise FingerprintCancelled()
    return _claim_from_payload(payload)


def registry_verification_audit_payload(claim, *, run_id):
    """Build the path-redacted, persistent audit receipt for one run."""

    if type(claim) is not RegistryVerificationClaim:
        _raise("registry_verification_claim_required")
    files = []
    for item in claim.files:
        locator = {"locator_kind": item.locator_kind}
        if item.locator_kind == "opaque_ref":
            locator["external_location_ref"] = item.external_location_ref
        else:
            locator.update(
                {
                    "path_base": item.path_base,
                    "relative_path": item.relative_path,
                }
            )
        files.append(
            {
                "file_id": item.file_id,
                "role": item.role,
                "asset_id": item.asset_id,
                "revision_id": item.revision_id,
                "event_id": item.event_id,
                "verified_at": item.verified_at,
                "entry_kind": item.observed_entry_kind,
                "size_bytes": item.observed_size_bytes,
                "mtime_ns": item.observed_mtime_ns,
                "hash_algorithm": item.observed_hash_algorithm,
                "digest": item.observed_digest,
                "runtime_metadata_digest": item.runtime_metadata_digest,
                "locator": locator,
            }
        )
    return {
        "schema_version": "taxamask_registry_verification_receipt_v1",
        "batch_id": claim.batch_id,
        "run_id": str(run_id),
        "project_id": claim.project_id,
        "data_version_id": claim.data_version_id,
        "files": files,
    }


def resolve_training_baseline_inputs(
    database_path,
    snapshot,
    *,
    project_root,
    run_root,
    opaque_locations=None,
    managed_roots=None,
    progress_callback=None,
    detail_progress_callback=None,
    cancel_check=None,
    issue_verification_batch=False,
    selected_file_ids=None,
):
    """Verify registry expected facts and materialize snapshots under run_root."""

    if not isinstance(snapshot, Mapping):
        _raise("integrity_baseline_missing")
    if snapshot.get("schema_version") != BASELINE_SNAPSHOT_SCHEMA_VERSION:
        _raise("integrity_baseline_schema_invalid")
    version_id = _safe_id(snapshot.get("data_version_id"), "project_data_version_id")
    roots = {
        "project_root": os.path.abspath(os.fspath(project_root)),
        "run_root": os.path.abspath(os.fspath(run_root)),
    }
    for path_base, root in dict(managed_roots or {}).items():
        clean_base = str(path_base or "")
        if clean_base not in PATH_BASES or clean_base == "run_root":
            _raise("runtime_path_base_not_allowed")
        if clean_base == "project_root":
            if os.path.normcase(os.path.abspath(os.fspath(root))) != os.path.normcase(
                roots["project_root"]
            ):
                _raise("project_root_override_not_allowed")
            continue
        roots[clean_base] = os.path.abspath(os.fspath(root))
    for root in roots.values():
        _require_safe_existing_path(root, expected_kind="directory")
    _require_safe_existing_path(database_path, expected_kind="file")
    connection = connect_sqlite_database(database_path)
    try:
        authoritative = get_registry_version_snapshot(connection, version_id)
        if authoritative != dict(snapshot):
            _raise("integrity_baseline_snapshot_stale")
        resolved_files = []
        verified_files = []
        opaque = dict(opaque_locations or {})
        all_entries = list(authoritative["files"])
        if selected_file_ids is None:
            entries = all_entries
        else:
            selected = {
                _safe_id(value, "file_id") for value in selected_file_ids
            }
            available = {
                str(entry.get("file_id") or "") for entry in all_entries
            }
            if not selected:
                _raise("training_input_selection_empty")
            if selected - available:
                _raise("training_input_selection_unknown_file")
            entries = [
                entry
                for entry in all_entries
                if str(entry.get("file_id") or "") in selected
            ]
        total_expected_bytes = sum(
            max(0, int(entry.get("size_bytes") or 0)) for entry in entries
        )
        completed_bytes = 0
        for file_index, entry in enumerate(entries, start=1):
            expected = {
                key: entry.get(key)
                for key in ("entry_kind", "size_bytes", "hash_algorithm", "digest")
            }
            runtime = dict(entry)

            def fingerprint(path):
                if cancel_check is not None and cancel_check():
                    raise FingerprintCancelled()
                callback = None
                if progress_callback is not None or detail_progress_callback is not None:
                    display_name = os.path.basename(os.path.normpath(path))

                    def callback(done, total):
                        if progress_callback is not None:
                            progress_callback(done, total)
                        if detail_progress_callback is not None:
                            detail_progress_callback(
                                {
                                    "phase": "registry_verification",
                                    "file_index": file_index,
                                    "file_count": len(entries),
                                    "file_id": str(entry.get("file_id") or ""),
                                    "role": str(entry.get("role") or "file"),
                                    "display_name": display_name,
                                    "bytes_done": int(done),
                                    "bytes_total": int(total),
                                    "total_bytes_done": completed_bytes + int(done),
                                    "total_bytes": (
                                        total_expected_bytes * 2
                                        if issue_verification_batch
                                        else total_expected_bytes
                                    ),
                                }
                            )

                return compute_fingerprint(
                    path,
                    entry["hash_algorithm"],
                    progress_callback=callback,
                    cancel_check=cancel_check,
                )

            try:
                if "location" in entry:
                    location = dict(entry["location"])
                    if location["location_kind"] == "managed_relative":
                        path_base = str(location["path_base"])
                        if path_base not in roots:
                            _raise("runtime_path_base_not_available")
                        runtime_path, clean_relative = _safe_runtime_target(
                            roots[path_base], location["relative_path"]
                        )
                        locator_kind = "managed_relative"
                        locator_path_base = path_base
                        locator_relative_path = clean_relative
                        locator_external_ref = ""
                    else:
                        opaque_ref = location["opaque_ref"]
                        if opaque_ref not in opaque:
                            _raise("opaque_location_unavailable")
                        raw_runtime_path = os.fspath(opaque[opaque_ref])
                        if not os.path.isabs(raw_runtime_path):
                            _raise("opaque_runtime_path_not_absolute")
                        runtime_path = os.path.abspath(raw_runtime_path)
                        clean_relative = None
                        locator_kind = "opaque_ref"
                        locator_path_base = ""
                        locator_relative_path = ""
                        locator_external_ref = str(opaque_ref)
                    _require_safe_existing_path(
                        runtime_path, expected_kind=entry["entry_kind"]
                    )
                    observed = fingerprint(runtime_path)
                    if not _matches_expected(expected, observed):
                        _record_verification(
                            connection, version_id, entry, "mismatch", observed, "source_digest_mismatch"
                        )
                        _raise("source_digest_mismatch")
                    location["runtime_path"] = runtime_path
                    if clean_relative is not None:
                        location["relative_path"] = clean_relative
                    runtime["location"] = location
                else:
                    materializer = dict(entry["materializer"])
                    target, clean_relative = _safe_runtime_target(
                        roots["run_root"], materializer["relative_path"]
                    )
                    row = connection.execute(
                        """
                        SELECT snapshot_text FROM integrity_asset_revisions
                        WHERE revision_id = ? AND asset_id = ?
                        """,
                        (entry["revision_id"], entry["asset_id"]),
                    ).fetchone()
                    if not row or row[0] is None:
                        _raise("snapshot_materializer_missing")
                    if cancel_check is not None and cancel_check():
                        raise FingerprintCancelled()
                    _atomic_write_snapshot(roots["run_root"], target, str(row[0]))
                    observed = fingerprint(target)
                    if not _matches_expected(expected, observed):
                        _record_verification(
                            connection, version_id, entry, "mismatch", observed, "materialized_digest_mismatch"
                        )
                        _raise("materialized_digest_mismatch")
                    materializer["relative_path"] = clean_relative
                    materializer["runtime_path"] = target
                    materializer["materialized"] = True
                    runtime["materializer"] = materializer
                    runtime_path = target
                    locator_kind = "materialized_snapshot"
                    locator_path_base = "run_root"
                    locator_relative_path = clean_relative
                    locator_external_ref = ""
                runtime["status"] = "verified"
                manifest_entry_kind = (
                    "external_reference"
                    if runtime.get("location", {}).get("location_kind") == "opaque_ref"
                    else str(observed["entry_kind"])
                )
                if issue_verification_batch:
                    metadata = _runtime_metadata_snapshot(
                        runtime_path,
                        expected_kind=str(observed["entry_kind"]),
                        cancel_check=cancel_check,
                    )
                    if (
                        metadata["entry_kind"] != observed["entry_kind"]
                        or metadata["mtime_ns"] != observed["mtime_ns"]
                        or (
                            observed["entry_kind"] == "file"
                            and metadata["size_bytes"] != observed["size_bytes"]
                        )
                    ):
                        _record_verification(
                            connection,
                            version_id,
                            entry,
                            "incomplete",
                            observed,
                            "source_changed_after_verification",
                        )
                        _raise("source_changed_after_verification")
                event = _record_verification(
                    connection, version_id, entry, "verified", observed
                )
                if issue_verification_batch:
                    verified_files.append(
                        RegistryVerifiedFile(
                            file_id=str(entry["file_id"]),
                            role=str(entry["role"]),
                            asset_id=str(entry["asset_id"]),
                            revision_id=str(entry["revision_id"]),
                            data_version_id=version_id,
                            event_id=str(event["event_id"]),
                            verified_at=str(event["verified_at"]),
                            observed_entry_kind=str(observed["entry_kind"]),
                            manifest_entry_kind=manifest_entry_kind,
                            observed_size_bytes=int(observed["size_bytes"]),
                            observed_mtime_ns=int(observed["mtime_ns"]),
                            observed_hash_algorithm=str(observed["hash_algorithm"]),
                            observed_digest=str(observed["digest"]),
                            locator_kind=locator_kind,
                            path_base=locator_path_base,
                            relative_path=locator_relative_path,
                            external_location_ref=locator_external_ref,
                            runtime_path=_capability_path(runtime_path),
                            runtime_stat_size_bytes=int(metadata["size_bytes"]),
                            runtime_stat_mtime_ns=int(metadata["mtime_ns"]),
                            runtime_metadata_digest=str(
                                metadata["metadata_digest"]
                            ),
                        )
                    )
                resolved_files.append(runtime)
                completed_bytes += int(observed["size_bytes"])
            except ProjectIntegrityRegistryError:
                raise
            except FingerprintError as exc:
                _record_verification(
                    connection,
                    version_id,
                    entry,
                    "incomplete",
                    {},
                    str(exc.code),
                )
                raise ProjectIntegrityRegistryError(str(exc.code)) from exc
            except FileNotFoundError as exc:
                _record_verification(
                    connection, version_id, entry, "missing", {}, "source_missing"
                )
                raise ProjectIntegrityRegistryError("source_missing") from exc
        connection.commit()
        result = {
            "schema_version": BASELINE_SNAPSHOT_SCHEMA_VERSION,
            "project_kind": authoritative["project_kind"],
            "project_id": authoritative["project_id"],
            "data_version_id": version_id,
            "status": "verified",
            "files": resolved_files,
        }
        if issue_verification_batch:
            payload = _RegistryVerificationPayload(
                batch_id=f"registry_verify_{uuid.uuid4().hex}",
                database_path=_capability_path(database_path),
                run_dir=_capability_path(roots["run_root"]),
                project_id=str(authoritative["project_id"]),
                data_version_id=version_id,
                files=tuple(verified_files),
            )
            result["verification_batch"] = _new_capability_handle(
                RegistryVerificationBatch,
                _ISSUED_REGISTRY_BATCHES,
                payload,
            )
        return result
    except Exception:
        connection.commit()
        raise
    finally:
        connection.close()


def _operation_refs(target_location_ref, temp_location_ref, backup_location_ref):
    return [
        _safe_id(value, "operation_location_ref") if value else ""
        for value in (target_location_ref, temp_location_ref, backup_location_ref)
    ]


def _insert_finalized_operation(
    connection,
    operation_kind,
    *,
    target_location_ref="",
    temp_location_ref="",
    backup_location_ref="",
    payload=None,
):
    operation_id = _new_id("operation")
    stamp = _now_iso()
    refs = _operation_refs(
        target_location_ref, temp_location_ref, backup_location_ref
    )
    connection.execute(
        """
        INSERT INTO integrity_operations (
            operation_id, operation_kind, status, target_location_ref,
            temp_location_ref, backup_location_ref, payload_json,
            error_json, created_at, updated_at
        ) VALUES (?, ?, 'finalized', ?, ?, ?, ?, '{}', ?, ?)
        """,
        (
            operation_id,
            _safe_id(operation_kind, "operation_kind"),
            refs[0],
            refs[1],
            refs[2],
            _canonical_json_text(
                dict(payload or {}), field_path="operation_payload"
            ),
            stamp,
            stamp,
        ),
    )
    return operation_id


def _relocate_project_asset(
    connection,
    *,
    project_id,
    asset_id,
    location,
    runtime_path,
):
    clean_project_id = _safe_id(project_id, "project_id")
    clean_asset_id = _safe_id(asset_id, "asset_id")
    state = registry_state(connection)
    if state["status"] != REGISTRY_READY:
        _raise("integrity_baseline_missing")
    if state["project_id"] != clean_project_id:
        _raise("registry_project_id_mismatch")
    current = _current_head(connection, clean_asset_id)
    if not current or int(current[1] or 0) == 1:
        _raise("relocation_asset_not_active")
    prepared_location = _normalise_location(location)
    old_location = _active_location(connection, clean_asset_id)
    if _same_location(old_location, prepared_location):
        return {
            "changed": False,
            "asset_id": clean_asset_id,
            "data_version_id": state["current_data_version_id"],
        }
    runtime = os.fspath(runtime_path)
    if not os.path.isabs(runtime):
        _raise("relocation_runtime_path_not_absolute")
    runtime = _require_safe_existing_path(runtime, expected_kind=str(current[5]))
    observed = compute_fingerprint(runtime, str(current[4]))
    expected = {
        "entry_kind": str(current[5]),
        "size_bytes": int(current[3]),
        "hash_algorithm": str(current[4]),
        "digest": str(current[2]),
    }
    if not _matches_expected(expected, observed):
        _raise("relocation_digest_mismatch")
    new_location_id = _insert_location(
        connection,
        clean_asset_id,
        location,
        revision_id=str(current[0]),
        digest=str(current[2]),
        data_version_id=state["current_data_version_id"],
        same_content_alias=True,
    )
    old_location_id = str((old_location or {}).get("location_id") or "")
    operation_id = _insert_finalized_operation(
        connection,
        "asset_relocation",
        target_location_ref=new_location_id,
        backup_location_ref=old_location_id,
        payload={
            "asset_id": clean_asset_id,
            "data_version_id": state["current_data_version_id"],
            "digest": expected["digest"],
            "same_content_verified": True,
        },
    )
    return {
        "changed": True,
        "asset_id": clean_asset_id,
        "data_version_id": state["current_data_version_id"],
        "old_location_id": old_location_id,
        "new_location_id": new_location_id,
        "operation_id": operation_id,
    }


def relocate_project_asset(
    connection,
    *,
    project_id,
    asset_id,
    location,
    runtime_path,
):
    """Relocate an unchanged asset inside the caller's transaction."""

    return _relocate_project_asset(
        connection,
        project_id=project_id,
        asset_id=asset_id,
        location=location,
        runtime_path=runtime_path,
    )


def create_operation(
    connection,
    operation_kind,
    *,
    target_location_ref="",
    temp_location_ref="",
    backup_location_ref="",
    payload=None,
):
    """Create a prepared recovery operation inside the caller's transaction."""

    operation_id = _new_id("operation")
    stamp = _now_iso()
    refs = _operation_refs(
        target_location_ref, temp_location_ref, backup_location_ref
    )
    connection.execute(
        """
        INSERT INTO integrity_operations (
            operation_id, operation_kind, status, target_location_ref,
            temp_location_ref, backup_location_ref, payload_json,
            error_json, created_at, updated_at
        ) VALUES (?, ?, 'prepared', ?, ?, ?, ?, '{}', ?, ?)
        """,
        (
            operation_id,
            _safe_id(operation_kind, "operation_kind"),
            refs[0],
            refs[1],
            refs[2],
            _canonical_json_text(
                dict(payload or {}), field_path="operation_payload"
            ),
            stamp,
            stamp,
        ),
    )
    return operation_id


def update_operation_status(connection, operation_id, status, *, error=None):
    clean_status = str(status or "")
    if clean_status not in OPERATION_STATUSES:
        _raise("invalid_operation_status")
    clean_operation_id = _safe_id(operation_id, "operation_id")
    row = connection.execute(
        "SELECT status FROM integrity_operations WHERE operation_id = ?",
        (clean_operation_id,),
    ).fetchone()
    if not row:
        _raise("operation_not_found")
    current_status = str(row[0] or "")
    if clean_status == current_status:
        return current_status
    if clean_status not in OPERATION_TRANSITIONS.get(current_status, frozenset()):
        _raise("invalid_operation_transition")
    updated = connection.execute(
        """
        UPDATE integrity_operations SET status = ?, error_json = ?, updated_at = ?
        WHERE operation_id = ?
        """,
        (
            clean_status,
            _canonical_json_text(
                dict(error or {}), field_path="operation_error"
            ),
            _now_iso(),
            clean_operation_id,
        ),
    )
    if updated.rowcount != 1:
        _raise("operation_not_found")
    return clean_status


__all__ = [
    "BASELINE_SNAPSHOT_SCHEMA_VERSION",
    "CHANGE_KINDS",
    "LABEL_SNAPSHOT_SCHEMA_ID",
    "OPERATION_STATUSES",
    "ProjectIntegrityRegistryError",
    "RegistryVerificationBatch",
    "RegistryVerificationClaim",
    "RegistryVerificationReceipt",
    "RegistryVerifiedFile",
    "REGISTRY_READY",
    "REGISTRY_RECOVERY_REQUIRED",
    "REGISTRY_SCHEMA_VERSION",
    "REGISTRY_UNINITIALIZED",
    "canonical_snapshot_text",
    "claim_registry_verification_receipt",
    "commit_project_data_version",
    "consume_registry_verification_batch",
    "create_operation",
    "get_registry_version_snapshot",
    "get_training_baseline_snapshot",
    "initialize_project_integrity_registry_schema",
    "inspect_registry_verification_receipt",
    "register_project_baseline",
    "read_materialized_registry_payloads",
    "relocate_project_asset",
    "registry_state",
    "registry_verification_audit_payload",
    "recheck_registry_verified_files",
    "resolve_training_baseline_inputs",
    "sync_registry_identity",
    "update_operation_status",
    "validate_project_integrity_registry_schema",
]
