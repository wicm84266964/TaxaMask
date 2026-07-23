"""Durable, UI-independent records for TaxaMask training runs."""

from __future__ import annotations

import importlib.metadata
import json
import math
import ntpath
import os
import platform
import posixpath
import re
import secrets
import sqlite3
import stat
import subprocess
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from AntSleap.core.file_integrity import DEFAULT_CHUNK_SIZE, QUICK_FILE_ALGORITHM
from AntSleap.core.integrity_manifest_service import (
    PATH_BASES,
    PROTECTED_FULL_HASH_ROLES,
    IntegrityManifestError,
    IntegrityManifestService,
    require_verified_training_inputs,
    validate_relative_path,
)
from AntSleap.core.safe_io import atomic_write_json


TRAINING_RUN_SCHEMA_VERSION = "taxamask_training_run_v1"
TRAINING_RUN_FILENAME = "training_run.json"
TRAINING_RUN_LEDGER_FILENAME = "training_runs.sqlite"
TRAINING_RUN_LEDGER_SCHEMA_VERSION = 1
ACTIVITY_LOCK_FILENAME = ".activity.lock"

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"
STATUS_INTERRUPTED = "interrupted"

ACTIVE_STATUSES = frozenset({STATUS_PENDING, STATUS_RUNNING})
TERMINAL_STATUSES = frozenset(
    {STATUS_SUCCEEDED, STATUS_FAILED, STATUS_CANCELLED, STATUS_INTERRUPTED}
)
ALL_STATUSES = ACTIVE_STATUSES | TERMINAL_STATUSES

_LEDGER_REQUIRED_COLUMNS = {
    "run_id",
    "record_schema_version",
    "status",
    "entrypoint",
    "project_id",
    "project_data_version_id",
    "created_at",
    "updated_at",
    "record_json",
}
_NOTE_LEDGER_REQUIRED_COLUMNS = {
    "run_id",
    "schema_version",
    "note_ref",
    "created_at",
    "updated_at",
    "note_json",
}
_LEDGER_REQUIRED_TRIGGERS = {
    "trg_training_runs_terminal_immutable_update",
    "trg_training_runs_immutable_delete",
}


def initialize_training_run_ledger_schema(connection):
    """Install the authoritative SQLite ledger used by every training entrypoint."""

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS training_run_ledger_meta (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            schema_version INTEGER NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS training_runs (
            run_id TEXT PRIMARY KEY,
            record_schema_version TEXT NOT NULL,
            status TEXT NOT NULL CHECK (
                status IN ('pending', 'running', 'succeeded', 'failed', 'cancelled', 'interrupted')
            ),
            entrypoint TEXT NOT NULL,
            project_id TEXT NOT NULL DEFAULT '',
            project_data_version_id TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            record_json TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_training_runs_project
            ON training_runs(project_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_training_runs_status
            ON training_runs(status, created_at);

        CREATE TABLE IF NOT EXISTS training_run_notes (
            run_id TEXT PRIMARY KEY,
            schema_version TEXT NOT NULL,
            note_ref TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            note_json TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES training_runs(run_id) ON DELETE RESTRICT
        );

        CREATE TRIGGER IF NOT EXISTS trg_training_runs_terminal_immutable_update
        BEFORE UPDATE ON training_runs
        WHEN OLD.status IN ('succeeded', 'failed', 'cancelled', 'interrupted')
        BEGIN
            SELECT RAISE(ABORT, 'training_run_terminal_immutable');
        END;

        CREATE TRIGGER IF NOT EXISTS trg_training_runs_immutable_delete
        BEFORE DELETE ON training_runs
        BEGIN
            SELECT RAISE(ABORT, 'training_run_delete_forbidden');
        END;
        """
    )
    connection.execute(
        """
        INSERT INTO training_run_ledger_meta (id, schema_version, updated_at)
        VALUES (1, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            schema_version = excluded.schema_version,
            updated_at = excluded.updated_at
        """,
        (TRAINING_RUN_LEDGER_SCHEMA_VERSION, utc_now()),
    )


def validate_training_run_ledger_schema(connection):
    tables = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    required_tables = {
        "training_run_ledger_meta",
        "training_runs",
        "training_run_notes",
    }
    missing_tables = sorted(required_tables - tables)
    if missing_tables:
        raise TrainingRunRecordError(
            f"training_run_ledger_tables_missing:{','.join(missing_tables)}"
        )
    columns = {
        str(row[1])
        for row in connection.execute("PRAGMA table_info(training_runs)").fetchall()
    }
    missing_columns = sorted(_LEDGER_REQUIRED_COLUMNS - columns)
    if missing_columns:
        raise TrainingRunRecordError(
            f"training_run_ledger_columns_missing:{','.join(missing_columns)}"
        )
    note_columns = {
        str(row[1])
        for row in connection.execute(
            "PRAGMA table_info(training_run_notes)"
        ).fetchall()
    }
    missing_note_columns = sorted(
        _NOTE_LEDGER_REQUIRED_COLUMNS - note_columns
    )
    if missing_note_columns:
        raise TrainingRunRecordError(
            "training_run_note_ledger_columns_missing:"
            + ",".join(missing_note_columns)
        )
    triggers = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'trigger'"
        ).fetchall()
    }
    missing_triggers = sorted(_LEDGER_REQUIRED_TRIGGERS - triggers)
    if missing_triggers:
        raise TrainingRunRecordError(
            f"training_run_ledger_triggers_missing:{','.join(missing_triggers)}"
        )
    row = connection.execute(
        "SELECT schema_version FROM training_run_ledger_meta WHERE id = 1"
    ).fetchone()
    if row is None or int(row[0]) != TRAINING_RUN_LEDGER_SCHEMA_VERSION:
        raise TrainingRunRecordError("training_run_ledger_schema_unsupported")
    return True


def _connect_training_run_ledger(database_path):
    connection = sqlite3.connect(str(database_path), timeout=30.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    connection.execute("PRAGMA journal_mode = WAL")
    with connection:
        initialize_training_run_ledger_schema(connection)
    validate_training_run_ledger_schema(connection)
    return connection

ALLOWED_FACT_FIELDS = frozenset(
    {
        "project_ref",
        "dataset_ref",
        "integrity_manifest",
        "split_manifest",
        "effective_config",
        "backend",
        "code",
        "environment",
        "note_ref",
        "artifacts",
    }
)
ENVIRONMENT_FIELDS = frozenset(
    {"platform", "python", "pytorch", "cuda", "compute_device"}
)
CODE_FIELDS = frozenset(
    {"taxamask_version", "revision", "working_tree_dirty"}
)
REQUIRED_EFFECTIVE_CONFIG_FIELDS = frozenset(
    {
        "epochs",
        "batch_size",
        "learning_rate",
        "weight_decay",
        "random_seed",
        "input_resolution",
        "preprocessing",
        "model",
        "loss_weights",
    }
)
TRUSTED_LABEL_POLICIES = frozenset(
    {
        "manual_truth_only",
        "human_confirmed_only",
        "manual_truth_and_human_confirmed",
        "verified_external_truth",
    }
)
FROZEN_WHEN_RUNNING = frozenset(
    {
        "project_ref",
        "dataset_ref",
        "integrity_manifest",
        "split_manifest",
        "effective_config",
        "backend",
        "code",
        "environment",
        "note_ref",
    }
)
PROJECT_REF_FIELDS = frozenset(
    {"project_kind", "project_id", "project_data_version_id"}
)
DATASET_REF_FIELDS = frozenset(
    {
        "dataset_id",
        "data_version_id",
        "trusted_label_policy",
        "source_kind",
        "trusted_source_ref",
    }
)
BACKEND_REQUIRED_FIELDS = frozenset(
    {"backend_id", "backend_version", "adapter_id", "adapter_version"}
)
TRUSTED_TRUTH_ROLES = {
    "manual_truth_only": frozenset({"manual_truth"}),
    "human_confirmed_only": frozenset({"human_confirmed_label"}),
    "manual_truth_and_human_confirmed": frozenset(
        {"manual_truth", "human_confirmed_label"}
    ),
    "verified_external_truth": frozenset(
        {"verified_external_truth", "manual_truth"}
    ),
}
SPLIT_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "split_id",
        "run_id",
        "status",
        "created_at",
        "started_at",
        "finished_at",
        "dataset_id",
        "strategy",
        "assignments",
        "error",
    }
)

_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
_FORBIDDEN_KEY_PATTERN = re.compile(
    r"(?:^|_)(?:password|passwd|secret|token|api_key|apikey|access_key|"
    r"private_key|command|command_line|argv|username|user_name)(?:$|_)",
    re.IGNORECASE,
)
_EMBEDDED_ABSOLUTE_PATH = re.compile(
    r"(?:(?<![^\W_])[A-Za-z]:[\\/]|\\\\|"
    r"(?<![^\W_])(?<!:)/{2}(?=[^/\s])|"
    r"(?<![^\W_])(?<!/)/(?:[^/\s]+(?:/|$))|"
    r"(?<![^\W_])~[\\/])"
)
_SECRET_TEXT_PATTERN = re.compile(
    r"(?:api[_ -]?key|access[_ -]?token|password|secret)\s*[:=]",
    re.IGNORECASE,
)
_SECRET_VALUE_PATTERN = re.compile(
    r"(?:\bBearer\s+[A-Za-z0-9._~+/=-]{8,}|"
    r"\bsk-[A-Za-z0-9_-]{8,}|"
    r"\bgh[pousr]_[A-Za-z0-9]{8,}|"
    r"\bAKIA[0-9A-Z]{12,}|"
    r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,})",
    re.IGNORECASE,
)


class TrainingRunRecordError(RuntimeError):
    """Base error for invalid or unsafe run-record operations."""


class InvalidRunTransition(TrainingRunRecordError):
    """Raised when a state transition is not allowed."""


class TerminalRunImmutable(TrainingRunRecordError):
    """Raised when code attempts to edit a terminal run."""


class UnsafeRunFact(TrainingRunRecordError):
    """Raised when a fact could leak a path, command, or secret."""


class IncompleteSuccessfulRun(TrainingRunRecordError):
    """Raised when a run lacks evidence required for success."""


def utc_now() -> str:
    """Return a timezone-aware UTC timestamp with microsecond precision."""

    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def new_training_run_id() -> str:
    """Return a collision-resistant, path-safe training run ID."""

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"train_{stamp}_{secrets.token_hex(4)}"


def note_ref_for_run(run_id: str) -> str:
    return f"training_note_{_validate_id(run_id, 'run_id')}"


def _validate_id(value, field_name, *, max_length=240) -> str:
    text = str(value or "").strip()
    if not text or len(text) > max_length or not _ID_PATTERN.fullmatch(text):
        raise UnsafeRunFact(f"invalid_{field_name}")
    return text


def _looks_like_absolute_path(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if text.lower().startswith("file://"):
        return True
    if ntpath.isabs(text) or posixpath.isabs(text):
        return True
    return bool(_EMBEDDED_ABSOLUTE_PATH.search(text))


def _is_reparse_point(stat_result: os.stat_result) -> bool:
    attributes = int(getattr(stat_result, "st_file_attributes", 0) or 0)
    flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400) or 0x400)
    return bool(attributes & flag)


def _require_safe_filesystem_entry(path, *, expected_kind=None):
    result = os.lstat(os.fspath(path))
    if stat.S_ISLNK(result.st_mode) or _is_reparse_point(result):
        raise UnsafeRunFact("filesystem_link_not_allowed")
    if expected_kind is None and not (
        stat.S_ISDIR(result.st_mode) or stat.S_ISREG(result.st_mode)
    ):
        raise UnsafeRunFact("safe_file_or_directory_required")
    if expected_kind == "directory" and not stat.S_ISDIR(result.st_mode):
        raise UnsafeRunFact("safe_directory_required")
    if expected_kind == "file" and not stat.S_ISREG(result.st_mode):
        raise UnsafeRunFact("safe_regular_file_required")
    return result


def _canonical_relative_path(value) -> str:
    raw = str(value or "")
    try:
        clean = validate_relative_path(raw)
    except IntegrityManifestError as exc:
        raise UnsafeRunFact("artifact_relative_path_invalid") from exc
    if clean != raw:
        raise UnsafeRunFact("artifact_relative_path_not_canonical")
    return clean


def _managed_lexical_path(base_dir, relative_path):
    base = os.path.abspath(os.fspath(base_dir))
    _require_safe_filesystem_entry(base, expected_kind="directory")
    clean_relative = _canonical_relative_path(relative_path)
    target = os.path.abspath(os.path.join(base, *clean_relative.split("/")))
    try:
        if os.path.normcase(os.path.commonpath([base, target])) != os.path.normcase(base):
            raise UnsafeRunFact("artifact_outside_path_base")
    except ValueError as exc:
        raise UnsafeRunFact("artifact_outside_path_base") from exc

    current = target
    while True:
        if os.path.lexists(current):
            result = os.lstat(current)
            if stat.S_ISLNK(result.st_mode) or _is_reparse_point(result):
                raise UnsafeRunFact("filesystem_link_not_allowed")
        if os.path.normcase(current) == os.path.normcase(base):
            break
        parent = os.path.dirname(current)
        if parent == current:
            raise UnsafeRunFact("artifact_outside_path_base")
        current = parent

    resolved = str(Path(target).resolve(strict=True))
    try:
        if os.path.normcase(os.path.commonpath([base, resolved])) != os.path.normcase(base):
            raise UnsafeRunFact("artifact_outside_path_base")
    except ValueError as exc:
        raise UnsafeRunFact("artifact_outside_path_base") from exc
    return target, clean_relative


def _read_json_nofollow(path):
    flags = os.O_RDONLY | int(getattr(os, "O_BINARY", 0))
    flags |= int(getattr(os, "O_NOFOLLOW", 0))
    descriptor = os.open(os.fspath(path), flags)
    with os.fdopen(descriptor, "r", encoding="utf-8", closefd=True) as handle:
        result = os.fstat(handle.fileno())
        if not stat.S_ISREG(result.st_mode) or _is_reparse_point(result):
            raise UnsafeRunFact("safe_regular_file_required")
        return json.load(handle)


def _validate_iso_timestamp(value, field_name):
    if not isinstance(value, str) or not value:
        raise IncompleteSuccessfulRun(f"split_timestamp_missing:{field_name}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise IncompleteSuccessfulRun(f"split_timestamp_invalid:{field_name}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise IncompleteSuccessfulRun(f"split_timestamp_timezone_missing:{field_name}")
    return value


def _assert_safe_payload(value, *, field_path="facts"):
    if value is None or isinstance(value, (bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise UnsafeRunFact(f"non_finite_number_not_allowed:{field_path}")
        return
    if isinstance(value, str):
        if "\x00" in value:
            raise UnsafeRunFact(f"nul_not_allowed:{field_path}")
        if _looks_like_absolute_path(value):
            raise UnsafeRunFact(f"absolute_path_not_allowed:{field_path}")
        if _SECRET_TEXT_PATTERN.search(value):
            raise UnsafeRunFact(f"secret_text_not_allowed:{field_path}")
        if _SECRET_VALUE_PATTERN.search(value):
            raise UnsafeRunFact(f"secret_value_not_allowed:{field_path}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_safe_payload(item, field_path=f"{field_path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            clean_key = str(key or "").strip()
            if not clean_key:
                raise UnsafeRunFact(f"empty_key_not_allowed:{field_path}")
            if _FORBIDDEN_KEY_PATTERN.search(clean_key):
                raise UnsafeRunFact(f"sensitive_field_not_allowed:{field_path}.{clean_key}")
            _assert_safe_payload(item, field_path=f"{field_path}.{clean_key}")
        return
    raise UnsafeRunFact(f"unsupported_value_type:{field_path}")


def _package_version() -> str:
    for package_name in ("TaxaMask", "AntSleap"):
        try:
            return importlib.metadata.version(package_name)
        except importlib.metadata.PackageNotFoundError:
            continue
    return "development"


def capture_code_revision(repository_root=None, *, taxamask_version=None) -> dict:
    """Capture only revision facts; command lines and repository paths are discarded."""

    root = Path(repository_root or Path(__file__).resolve().parents[2])
    revision = "not_recorded"
    dirty = None
    try:
        revision_result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        )
        candidate = revision_result.stdout.strip()
        if re.fullmatch(r"[0-9a-fA-F]{7,64}", candidate):
            revision = candidate.lower()
        status_result = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"],
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        )
        dirty = bool(status_result.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return {
        "taxamask_version": str(taxamask_version or _package_version()),
        "revision": revision,
        "working_tree_dirty": dirty,
    }


def capture_environment(*, compute_device="not_recorded", cuda="not_recorded") -> dict:
    """Capture a fixed environment whitelist without importing torch."""

    try:
        pytorch_version = importlib.metadata.version("torch")
    except importlib.metadata.PackageNotFoundError:
        pytorch_version = "not_installed"
    return {
        "platform": platform.system().lower() or "unknown",
        "python": platform.python_version(),
        "pytorch": pytorch_version,
        "cuda": str(cuda or "not_recorded"),
        "compute_device": str(compute_device or "not_recorded"),
    }


def validate_split_assignments(assignments) -> dict:
    """Validate final assignments and return group-to-partition membership."""

    if not isinstance(assignments, list) or not assignments:
        raise IncompleteSuccessfulRun("split_assignments_missing")
    group_partitions = {}
    sample_ids = set()
    for index, assignment in enumerate(assignments):
        if not isinstance(assignment, dict):
            raise IncompleteSuccessfulRun(f"split_assignment_not_object:{index}")
        sample_id = _validate_id(assignment.get("sample_id"), "sample_id")
        group_id = _validate_id(assignment.get("group_id"), "group_id")
        partition = str(assignment.get("partition") or "").strip().lower()
        if partition not in {"train", "validation", "test"}:
            raise IncompleteSuccessfulRun(f"split_partition_invalid:{sample_id}")
        if sample_id in sample_ids:
            raise IncompleteSuccessfulRun(f"split_sample_duplicate:{sample_id}")
        sample_ids.add(sample_id)
        prior = group_partitions.setdefault(group_id, partition)
        if prior != partition:
            raise IncompleteSuccessfulRun(
                f"split_group_leakage:{group_id}:{prior}:{partition}"
            )
        input_file_ids = assignment.get("input_file_ids")
        if not isinstance(input_file_ids, list) or not input_file_ids:
            raise IncompleteSuccessfulRun(f"split_input_files_missing:{sample_id}")
        for file_id in input_file_ids:
            _validate_id(file_id, "input_file_id")
    return dict(group_partitions)


class _ActivityLock:
    """A process-held, non-blocking file lock used only for liveness."""

    def __init__(self, path):
        self.path = os.path.abspath(str(path))
        self.handle = None

    def acquire(self) -> bool:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if os.path.lexists(self.path):
            try:
                _require_safe_filesystem_entry(self.path, expected_kind="file")
            except UnsafeRunFact as exc:
                raise TrainingRunRecordError("activity_lock_unsafe") from exc
        flags = os.O_RDWR | os.O_CREAT | int(getattr(os, "O_BINARY", 0))
        flags |= int(getattr(os, "O_NOFOLLOW", 0))
        descriptor = os.open(self.path, flags, 0o600)
        handle = os.fdopen(descriptor, "r+b", closefd=True)
        try:
            opened = os.fstat(handle.fileno())
            if not stat.S_ISREG(opened.st_mode) or _is_reparse_point(opened):
                raise TrainingRunRecordError("activity_lock_unsafe")
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
                os.fsync(handle.fileno())
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except TrainingRunRecordError:
            handle.close()
            raise
        except (OSError, IOError):
            handle.close()
            return False
        self.handle = handle
        return True

    def release(self):
        handle, self.handle = self.handle, None
        if handle is None:
            return
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except (OSError, IOError):
            pass
        finally:
            handle.close()


def _clean_error(
    *,
    code,
    summary,
    stage,
    recoverable,
    diagnostic_artifact_id=None,
) -> dict:
    clean_code = _validate_id(code, "error_code")
    clean_stage = _validate_id(stage, "error_stage")
    clean_summary = " ".join(str(summary or "Training failed.").split())[:500]
    if (
        not clean_summary
        or _looks_like_absolute_path(clean_summary)
        or _SECRET_TEXT_PATTERN.search(clean_summary)
        or _SECRET_VALUE_PATTERN.search(clean_summary)
    ):
        clean_summary = "Training did not finish; sensitive diagnostic details were omitted."
    error = {
        "code": clean_code,
        "summary": clean_summary,
        "stage": clean_stage,
        "recoverable": bool(recoverable),
        "diagnostic_artifact_id": None,
    }
    if diagnostic_artifact_id is not None:
        error["diagnostic_artifact_id"] = _validate_id(
            diagnostic_artifact_id, "diagnostic_artifact_id"
        )
    return error


def _validate_whitelist(mapping, allowed, field_name):
    if not isinstance(mapping, dict):
        raise UnsafeRunFact(f"{field_name}_must_be_object")
    unexpected = set(mapping) - set(allowed)
    if unexpected:
        raise UnsafeRunFact(
            f"{field_name}_field_not_allowed:{sorted(str(item) for item in unexpected)[0]}"
        )
    _assert_safe_payload(mapping, field_path=field_name)
    return dict(mapping)


def _validate_artifact_record(artifact):
    if not isinstance(artifact, dict):
        raise UnsafeRunFact("artifact_must_be_object")
    artifact_id = _validate_id(artifact.get("artifact_id"), "artifact_id")
    _validate_id(artifact.get("role"), "artifact_role")
    entry_kind = str(artifact.get("entry_kind") or "")
    if entry_kind == "external_reference":
        _validate_id(artifact.get("external_location_ref"), "external_location_ref")
        if "path_base" in artifact or "relative_path" in artifact:
            raise UnsafeRunFact(f"external_artifact_path_not_allowed:{artifact_id}")
    elif entry_kind in {"file", "directory"}:
        path_base = _validate_id(artifact.get("path_base"), "path_base")
        if path_base not in PATH_BASES:
            raise UnsafeRunFact(f"artifact_path_base_invalid:{artifact_id}")
        relative_path = str(artifact.get("relative_path") or "")
        try:
            _canonical_relative_path(relative_path)
        except UnsafeRunFact as exc:
            raise UnsafeRunFact(f"artifact_relative_path_invalid:{artifact_id}") from exc
    else:
        raise UnsafeRunFact(f"artifact_entry_kind_invalid:{artifact_id}")
    size_bytes = artifact.get("size_bytes")
    digest = str(artifact.get("digest") or "")
    algorithm = str(artifact.get("hash_algorithm") or "")
    if not isinstance(size_bytes, int) or size_bytes < 0:
        raise UnsafeRunFact(f"artifact_size_invalid:{artifact_id}")
    if algorithm not in {
        "sha256",
        "sha256-tree-v1",
        "taxamask-sampled-sha256-v1",
    }:
        raise UnsafeRunFact(f"artifact_hash_algorithm_invalid:{artifact_id}")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise UnsafeRunFact(f"artifact_digest_invalid:{artifact_id}")
    _assert_safe_payload(artifact, field_path=f"artifact.{artifact_id}")


def _merge_facts(record, facts):
    if not facts:
        return record
    if not isinstance(facts, dict):
        raise UnsafeRunFact("facts_must_be_object")
    unexpected = set(facts) - set(ALLOWED_FACT_FIELDS)
    if unexpected:
        raise UnsafeRunFact(f"fact_field_not_allowed:{sorted(unexpected)[0]}")
    result = dict(record)
    for key, value in facts.items():
        if key == "environment":
            current = dict(result.get(key) or {})
            current.update(_validate_whitelist(value, ENVIRONMENT_FIELDS, key))
            result[key] = current
        elif key == "code":
            current = dict(result.get(key) or {})
            current.update(_validate_whitelist(value, CODE_FIELDS, key))
            result[key] = current
        elif key in {"project_ref", "dataset_ref"}:
            if not isinstance(value, dict):
                raise UnsafeRunFact(f"{key}_must_be_object")
            _assert_safe_payload(value, field_path=key)
            result[key] = dict(value)
        elif key in {"effective_config", "backend"}:
            if not isinstance(value, dict):
                raise UnsafeRunFact(f"{key}_must_be_object")
            _assert_safe_payload(value, field_path=key)
            current = dict(result.get(key) or {})
            current.update(value)
            result[key] = current
        elif key == "note_ref":
            expected = note_ref_for_run(result["run_id"])
            if value != expected:
                raise UnsafeRunFact("note_ref_must_match_run_id")
            result[key] = expected
        elif key == "artifacts":
            if not isinstance(value, list):
                raise UnsafeRunFact("artifacts_must_be_list")
            for artifact in value:
                _validate_artifact_record(artifact)
            ids = [item["artifact_id"] for item in value]
            if len(ids) != len(set(ids)):
                raise UnsafeRunFact("artifact_id_duplicate")
            result[key] = [dict(item) for item in value]
        elif key in {"integrity_manifest", "split_manifest"}:
            if not isinstance(value, dict):
                raise UnsafeRunFact(f"{key}_must_be_object")
            _validate_artifact_record(value)
            _assert_safe_payload(value, field_path=key)
            result[key] = dict(value)
    return result


class TrainingRunRecorder:
    """Owns exclusive run directories and performs startup recovery."""

    def __init__(
        self,
        runs_root,
        *,
        database_path=None,
        recover_on_startup=True,
    ):
        requested_root = os.path.abspath(str(runs_root))
        os.makedirs(requested_root, exist_ok=True)
        self.runs_root = str(Path(requested_root).resolve(strict=True))
        requested_database = os.path.abspath(
            os.fspath(
                database_path
                or os.path.join(self.runs_root, TRAINING_RUN_LEDGER_FILENAME)
            )
        )
        os.makedirs(os.path.dirname(requested_database), exist_ok=True)
        self.database_path = requested_database
        self._mutex = threading.RLock()
        self._locks = {}
        self.projection_errors = []
        connection = _connect_training_run_ledger(self.database_path)
        connection.close()
        self.startup_recovery_report = {
            "interrupted": [],
            "active": [],
            "invalid": [],
        }
        if recover_on_startup:
            self.startup_recovery_report = self.recover_interrupted_runs()

    def _record_text(self, record):
        _assert_safe_payload(record, field_path="training_run")
        return json.dumps(
            record,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    def _write_projection(self, record):
        run_id = str(record.get("run_id") or "")
        run_dir = os.path.join(self.runs_root, run_id)
        try:
            _require_safe_filesystem_entry(run_dir, expected_kind="directory")
            atomic_write_json(
                os.path.join(run_dir, TRAINING_RUN_FILENAME), record, indent=2
            )
        except Exception as exc:
            self.projection_errors.append(
                {"run_id": run_id, "error_type": type(exc).__name__}
            )

    def _insert_record(self, record):
        text = self._record_text(record)
        project_ref = record.get("project_ref") or {}
        now = utc_now()
        connection = _connect_training_run_ledger(self.database_path)
        try:
            with connection:
                connection.execute(
                    """
                    INSERT INTO training_runs (
                        run_id, record_schema_version, status, entrypoint,
                        project_id, project_data_version_id, created_at, updated_at,
                        record_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record["run_id"],
                        record["schema_version"],
                        record["status"],
                        record["entrypoint"],
                        str(project_ref.get("project_id") or ""),
                        str(project_ref.get("project_data_version_id") or ""),
                        record["created_at"],
                        now,
                        text,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise TrainingRunRecordError(
                f"training_run_ledger_insert_failed:{record['run_id']}"
            ) from exc
        finally:
            connection.close()
        self._write_projection(record)

    def _update_record(self, record, *, expected_status):
        text = self._record_text(record)
        project_ref = record.get("project_ref") or {}
        connection = _connect_training_run_ledger(self.database_path)
        try:
            with connection:
                cursor = connection.execute(
                    """
                    UPDATE training_runs
                    SET record_schema_version = ?, status = ?, entrypoint = ?,
                        project_id = ?, project_data_version_id = ?,
                        updated_at = ?, record_json = ?
                    WHERE run_id = ? AND status = ?
                    """,
                    (
                        record["schema_version"],
                        record["status"],
                        record["entrypoint"],
                        str(project_ref.get("project_id") or ""),
                        str(project_ref.get("project_data_version_id") or ""),
                        utc_now(),
                        text,
                        record["run_id"],
                        expected_status,
                    ),
                )
                if cursor.rowcount != 1:
                    raise InvalidRunTransition(
                        f"training_run_compare_and_swap_failed:{record['run_id']}"
                    )
        except sqlite3.IntegrityError as exc:
            if "training_run_terminal_immutable" in str(exc):
                raise TerminalRunImmutable(
                    f"terminal_run_immutable:{record['run_id']}"
                ) from exc
            raise TrainingRunRecordError(
                f"training_run_ledger_update_failed:{record['run_id']}"
            ) from exc
        finally:
            connection.close()
        self._write_projection(record)
        return dict(record)

    def _load_record(self, clean_run_id):
        connection = _connect_training_run_ledger(self.database_path)
        try:
            row = connection.execute(
                "SELECT record_json FROM training_runs WHERE run_id = ?",
                (clean_run_id,),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise TrainingRunRecordError(f"training_run_not_found:{clean_run_id}")
        try:
            return json.loads(str(row["record_json"]))
        except (ValueError, TypeError) as exc:
            raise TrainingRunRecordError(
                f"training_run_record_unreadable:{clean_run_id}"
            ) from exc

    def create_pending(
        self,
        entrypoint,
        *,
        retry_of=None,
        facts=None,
        project_ref=None,
        dataset_ref=None,
        effective_config=None,
        backend=None,
        code=None,
        environment=None,
    ):
        clean_entrypoint = _validate_id(entrypoint, "entrypoint", max_length=128)
        clean_retry = _validate_id(retry_of, "retry_of") if retry_of else None
        if clean_retry:
            retry_record = self.load(clean_retry)
            if retry_record["status"] not in {
                STATUS_FAILED,
                STATUS_CANCELLED,
                STATUS_INTERRUPTED,
            }:
                raise InvalidRunTransition("retry_of_must_reference_unsuccessful_terminal_run")
        combined_facts = dict(facts or {})
        for key, value in (
            ("project_ref", project_ref),
            ("dataset_ref", dataset_ref),
            ("effective_config", effective_config),
            ("backend", backend),
            ("code", code),
            ("environment", environment),
        ):
            if value is not None:
                combined_facts[key] = value

        for _attempt in range(64):
            run_id = new_training_run_id()
            run_dir = os.path.join(self.runs_root, run_id)
            try:
                os.mkdir(run_dir)
            except FileExistsError:
                continue
            lock = _ActivityLock(os.path.join(run_dir, ACTIVITY_LOCK_FILENAME))
            if not lock.acquire():
                continue
            record = {
                "schema_version": TRAINING_RUN_SCHEMA_VERSION,
                "run_id": run_id,
                "status": STATUS_PENDING,
                "entrypoint": clean_entrypoint,
                "created_at": utc_now(),
                "started_at": None,
                "finished_at": None,
                "retry_of": clean_retry,
                "project_ref": {},
                "dataset_ref": {},
                "integrity_manifest": None,
                "split_manifest": None,
                "effective_config": {},
                "backend": {},
                "code": capture_code_revision(),
                "environment": capture_environment(),
                "note_ref": note_ref_for_run(run_id),
                "artifacts": [],
                "error": None,
            }
            try:
                record = _merge_facts(record, combined_facts)
                _assert_safe_payload(record, field_path="training_run")
                self._insert_record(record)
            except Exception:
                lock.release()
                raise
            with self._mutex:
                self._locks[run_id] = lock
            return TrainingRun(self, run_id, run_dir)
        raise TrainingRunRecordError("could_not_create_exclusive_run_directory")

    def load(self, run_id):
        clean_run_id = _validate_id(run_id, "run_id")
        try:
            record = self._load_record(clean_run_id)
            _assert_safe_payload(record, field_path="training_run")
        except (UnsafeRunFact, ValueError, TypeError) as exc:
            raise TrainingRunRecordError(f"training_run_record_unreadable:{clean_run_id}") from exc
        if (
            not isinstance(record, dict)
            or record.get("schema_version") != TRAINING_RUN_SCHEMA_VERSION
            or record.get("run_id") != clean_run_id
            or record.get("status") not in ALL_STATUSES
        ):
            raise TrainingRunRecordError(f"training_run_record_invalid:{clean_run_id}")
        return record

    def list_records(self, *, limit=500):
        clean_limit = max(1, min(5000, int(limit)))
        connection = _connect_training_run_ledger(self.database_path)
        try:
            rows = connection.execute(
                "SELECT record_json FROM training_runs "
                "ORDER BY created_at DESC, run_id DESC LIMIT ?",
                (clean_limit,),
            ).fetchall()
        finally:
            connection.close()
        records = []
        for row in rows:
            try:
                record = json.loads(str(row["record_json"]))
                if (
                    isinstance(record, dict)
                    and record.get("schema_version") == TRAINING_RUN_SCHEMA_VERSION
                    and record.get("status") in ALL_STATUSES
                ):
                    records.append(record)
            except (TypeError, ValueError):
                continue
        return records

    def recover_interrupted_runs(self):
        report = {"interrupted": [], "active": [], "invalid": []}
        connection = _connect_training_run_ledger(self.database_path)
        try:
            rows = connection.execute(
                """
                SELECT run_id FROM training_runs
                WHERE status IN ('pending', 'running')
                ORDER BY created_at, run_id
                """
            ).fetchall()
            known_ids = {
                str(row[0])
                for row in connection.execute(
                    "SELECT run_id FROM training_runs"
                ).fetchall()
            }
        finally:
            connection.close()

        try:
            for child in os.scandir(self.runs_root):
                if (
                    child.name.startswith("train_")
                    and _ID_PATTERN.fullmatch(child.name)
                    and child.name not in known_ids
                ):
                    report["invalid"].append(child.name)
        except OSError:
            pass

        for row in rows:
            run_id = str(row["run_id"])
            run_dir = os.path.join(self.runs_root, run_id)
            try:
                _require_safe_filesystem_entry(run_dir, expected_kind="directory")
                record = self.load(run_id)
            except (
                OSError,
                UnsafeRunFact,
                ValueError,
                TypeError,
                TrainingRunRecordError,
            ):
                report["invalid"].append(run_id)
                continue
            if record.get("status") not in ACTIVE_STATUSES:
                continue
            lock = _ActivityLock(os.path.join(run_dir, ACTIVITY_LOCK_FILENAME))
            try:
                acquired = lock.acquire()
            except TrainingRunRecordError:
                report["invalid"].append(run_id)
                continue
            if not acquired:
                report["active"].append(run_id)
                continue
            try:
                current = self.load(run_id)
                if current.get("status") not in ACTIVE_STATUSES:
                    continue
                previous_status = current["status"]
                current["status"] = STATUS_INTERRUPTED
                current["finished_at"] = utc_now()
                current["error"] = _clean_error(
                    code="process_interrupted",
                    summary=(
                        "The previous training process ended before this run reached "
                        "a terminal state."
                    ),
                    stage="startup_recovery",
                    recoverable=True,
                )
                self._update_record(current, expected_status=previous_status)
                report["interrupted"].append(run_id)
            except (
                OSError,
                ValueError,
                TypeError,
                UnsafeRunFact,
                TrainingRunRecordError,
            ):
                report["invalid"].append(run_id)
            finally:
                lock.release()
        return report

    def _release(self, run_id):
        with self._mutex:
            lock = self._locks.pop(run_id, None)
        if lock is not None:
            lock.release()


class TrainingRun:
    """Mutable handle for one run until it reaches an immutable terminal state."""

    def __init__(self, recorder, run_id, run_dir):
        self.recorder = recorder
        self.run_id = run_id
        self.run_dir = os.path.abspath(str(run_dir))
        self.record_path = os.path.join(self.run_dir, TRAINING_RUN_FILENAME)
        self._mutex = threading.RLock()
        self._path_bases = {"run_root": self.run_dir}
        self._external_paths = {}
        self._external_locations = {}
        self._closed = False

    @property
    def note_ref(self):
        return note_ref_for_run(self.run_id)

    @property
    def record(self):
        return self.recorder.load(self.run_id)

    @property
    def status(self):
        return self.record["status"]

    def attach_facts(self, facts=None, **kwargs):
        updates = dict(facts or {})
        updates.update(kwargs)
        with self._mutex:
            current = self.record
            self._require_mutable(current)
            if "artifacts" in updates:
                raise UnsafeRunFact("artifacts_are_append_only")
            if current["status"] == STATUS_RUNNING:
                frozen = set(updates) & set(FROZEN_WHEN_RUNNING)
                if frozen:
                    raise InvalidRunTransition(
                        f"running_fact_frozen:{sorted(frozen)[0]}"
                    )
            updated = _merge_facts(current, updates)
            _assert_safe_payload(updated, field_path="training_run")
            return self.recorder._update_record(
                updated, expected_status=current["status"]
            )

    def register_path_base(self, path_base, base_dir):
        self._ensure_open()
        clean_base = _validate_id(path_base, "path_base")
        if clean_base not in PATH_BASES:
            raise UnsafeRunFact(f"path_base_not_allowed:{clean_base}")
        resolved = str(Path(base_dir).resolve(strict=True))
        _require_safe_filesystem_entry(resolved, expected_kind="directory")
        self._path_bases[clean_base] = resolved
        return clean_base

    def register_external_location(self, external_location_ref, path):
        """Register an opaque integrity source location without persisting its path."""

        with self._mutex:
            current = self.record
            self._require_mutable(current)
            if current["status"] != STATUS_PENDING:
                raise InvalidRunTransition("external_location_frozen_after_start")
            clean_ref = _validate_id(
                external_location_ref, "external_location_ref"
            )
            target = os.path.abspath(os.fspath(path))
            _require_safe_filesystem_entry(target)
            existing = self._external_locations.get(clean_ref)
            if existing is not None and os.path.normcase(existing) != os.path.normcase(
                target
            ):
                raise UnsafeRunFact(
                    f"external_location_ref_conflict:{clean_ref}"
                )
            self._external_locations[clean_ref] = target
            return clean_ref

    def fingerprint_artifact(
        self,
        *,
        artifact_id,
        role,
        path,
        path_base="run_root",
        base_dir=None,
        media_type=None,
        algorithm=None,
    ):
        self._ensure_open()
        clean_id = _validate_id(artifact_id, "artifact_id")
        clean_role = _validate_id(role, "artifact_role")
        clean_base = _validate_id(path_base, "path_base")
        if base_dir is not None:
            self.register_path_base(clean_base, base_dir)
        if clean_base not in self._path_bases:
            raise UnsafeRunFact(f"path_base_not_registered:{clean_base}")
        base = self._path_bases[clean_base]
        raw_path = Path(path)
        if raw_path.is_absolute():
            raw_target = os.path.abspath(os.fspath(raw_path))
            try:
                relative = os.path.relpath(raw_target, base).replace("\\", "/")
            except ValueError as exc:
                raise UnsafeRunFact(f"artifact_outside_path_base:{clean_id}") from exc
        else:
            relative = str(path).replace("\\", "/")
        try:
            target, relative = _managed_lexical_path(base, relative)
        except UnsafeRunFact as exc:
            raise UnsafeRunFact(f"artifact_path_unsafe:{clean_id}") from exc
        from AntSleap.core.file_integrity import compute_fingerprint

        fingerprint = compute_fingerprint(target, algorithm=algorithm)
        artifact = {
            "artifact_id": clean_id,
            "role": clean_role,
            "path_base": clean_base,
            "relative_path": relative,
            "entry_kind": fingerprint["entry_kind"],
            "size_bytes": fingerprint["size_bytes"],
            "hash_algorithm": fingerprint["hash_algorithm"],
            "digest": fingerprint["digest"],
        }
        if media_type:
            artifact["media_type"] = str(media_type).strip()
        _validate_artifact_record(artifact)
        return artifact

    def add_artifact(self, **kwargs):
        artifact = self.fingerprint_artifact(**kwargs)
        self._append_artifact(artifact)
        return dict(artifact)

    def add_external_artifact(
        self,
        *,
        artifact_id,
        role,
        path,
        external_location_ref,
        media_type=None,
        algorithm=None,
    ):
        self._ensure_open()
        clean_id = _validate_id(artifact_id, "artifact_id")
        clean_role = _validate_id(role, "artifact_role")
        clean_location = _validate_id(external_location_ref, "external_location_ref")
        target = os.path.abspath(os.fspath(path))
        _require_safe_filesystem_entry(target)
        from AntSleap.core.file_integrity import compute_fingerprint

        fingerprint = compute_fingerprint(target, algorithm=algorithm)
        artifact = {
            "artifact_id": clean_id,
            "role": clean_role,
            "entry_kind": "external_reference",
            "external_location_ref": clean_location,
            "size_bytes": fingerprint["size_bytes"],
            "hash_algorithm": fingerprint["hash_algorithm"],
            "digest": fingerprint["digest"],
        }
        if media_type:
            artifact["media_type"] = str(media_type).strip()
        _validate_artifact_record(artifact)
        self._external_paths[clean_id] = target
        self._append_artifact(artifact)
        return dict(artifact)

    def _append_artifact(self, artifact):
        with self._mutex:
            current = self.record
            self._require_mutable(current)
            artifacts = [dict(item) for item in current.get("artifacts") or []]
            if any(item.get("artifact_id") == artifact["artifact_id"] for item in artifacts):
                raise UnsafeRunFact(f"artifact_id_duplicate:{artifact['artifact_id']}")
            artifacts.append(dict(artifact))
            current["artifacts"] = artifacts
            self.recorder._update_record(
                current, expected_status=current["status"]
            )

    def attach_integrity_manifest(
        self, path, *, path_base="run_root", base_dir=None
    ):
        payload = _read_json_object(path)
        if payload.get("schema_version") != "taxamask_integrity_manifest_v1":
            raise IncompleteSuccessfulRun("integrity_manifest_schema_invalid")
        if payload.get("run_id") != self.run_id:
            raise IncompleteSuccessfulRun("integrity_manifest_run_id_mismatch")
        manifest_id = _validate_id(payload.get("manifest_id"), "manifest_id")
        artifact = self.fingerprint_artifact(
            artifact_id="integrity_manifest",
            role="integrity_manifest",
            path=path,
            path_base=path_base,
            base_dir=base_dir,
            media_type="application/json",
        )
        artifact["manifest_id"] = manifest_id
        self.attach_facts(integrity_manifest=artifact)
        return dict(artifact)

    def attach_split_manifest(self, path, *, path_base="run_root", base_dir=None):
        payload = _read_json_object(path)
        current = self.record
        integrity_payload = self._integrity_payload(current)
        _validate_split_manifest_payload(
            payload,
            self.run_id,
            dataset_ref=current.get("dataset_ref"),
            integrity_files={item["file_id"]: item for item in integrity_payload["files"]},
        )
        split_id = _validate_id(payload.get("split_id"), "split_id")
        artifact = self.fingerprint_artifact(
            artifact_id="split_manifest",
            role="training_split",
            path=path,
            path_base=path_base,
            base_dir=base_dir,
            media_type="application/json",
        )
        artifact["split_id"] = split_id
        self.attach_facts(split_manifest=artifact)
        return dict(artifact)

    def mark_running(
        self,
        *,
        integrity_chunk_size=DEFAULT_CHUNK_SIZE,
        integrity_progress_callback=None,
        cancel_check=None,
    ):
        with self._mutex:
            current = self.record
            self._require_mutable(current)
            if current["status"] != STATUS_PENDING:
                raise InvalidRunTransition(
                    f"invalid_transition:{current['status']}->{STATUS_RUNNING}"
                )
            self._validate_dataset_policy(current)
            baseline_integrity = self._validate_integrity_manifest(
                current, require_recheck=False
            )
            self._validate_split_reference(current, baseline_integrity)
            self._validate_effective_config(current, allow_pending_external=True)
            self._validate_backend(current)
            self._validate_code_environment(current)
            source_path = self._resolve_artifact(current["integrity_manifest"])
            recheck_path = os.path.join(
                self.run_dir, f"integrity_recheck_{secrets.token_hex(4)}.json"
            )
            service = IntegrityManifestService(
                source_path,
                self._path_bases,
                external_locations=self._external_locations,
            )
            recheck = service.recheck_verified(
                output_manifest_path=recheck_path,
                chunk_size=integrity_chunk_size,
                progress_callback=integrity_progress_callback,
                cancel_check=cancel_check,
            )
            self.attach_integrity_manifest(service.last_written_path)
            current = self.record
            if recheck.get("status") != "verified":
                raise IncompleteSuccessfulRun(
                    f"integrity_recheck_not_verified:{recheck.get('status')}"
                )
            require_verified_training_inputs(recheck)
            rechecked_integrity = self._validate_integrity_manifest(
                current, require_recheck=True
            )
            self._validate_split_reference(current, rechecked_integrity)
            previous_status = current["status"]
            current["status"] = STATUS_RUNNING
            current["started_at"] = utc_now()
            current["error"] = None
            return self.recorder._update_record(
                current, expected_status=previous_status
            )

    def succeed(self):
        with self._mutex:
            current = self.record
            self._require_mutable(current)
            if current["status"] != STATUS_RUNNING:
                raise InvalidRunTransition(
                    f"invalid_transition:{current['status']}->{STATUS_SUCCEEDED}"
                )
            self._validate_success(current)
            return self._finish(current, STATUS_SUCCEEDED, error=None)

    def resolve_external_effective_config(self, effective_config):
        """Freeze backend-resolved values while an external run is active."""

        with self._mutex:
            current = self.record
            self._require_mutable(current)
            if current["status"] != STATUS_RUNNING:
                raise InvalidRunTransition(
                    "external_effective_config_requires_running_run"
                )
            pending = current.get("effective_config") or {}
            if pending.get("resolution_status") != "pending_external":
                raise InvalidRunTransition(
                    "external_effective_config_not_pending"
                )
            resolved = dict(effective_config or {})
            resolved["resolution_status"] = "resolved"
            candidate = dict(current)
            candidate["effective_config"] = resolved
            self._validate_effective_config(candidate)
            config_path = os.path.join(
                self.run_dir, "outputs", "effective_config_resolved.json"
            )
            atomic_write_json(config_path, resolved, indent=2)
            artifact = self.fingerprint_artifact(
                artifact_id="resolved_effective_config",
                role="training_config",
                path=config_path,
                path_base="run_root",
                media_type="application/json",
            )
            artifacts = [dict(item) for item in current.get("artifacts") or []]
            if any(item.get("artifact_id") == artifact["artifact_id"] for item in artifacts):
                raise UnsafeRunFact("resolved_effective_config_duplicate")
            artifacts.append(artifact)
            current["effective_config"] = resolved
            current["artifacts"] = artifacts
            return self.recorder._update_record(
                current, expected_status=STATUS_RUNNING
            )

    def fail(
        self,
        error=None,
        *,
        code="training_failed",
        summary=None,
        stage="training",
        recoverable=False,
        diagnostic_artifact_id=None,
    ):
        if summary is None and error is not None:
            summary = f"Training failed with {type(error).__name__}."
        clean_error = _clean_error(
            code=code,
            summary=summary or "Training failed.",
            stage=stage,
            recoverable=recoverable,
            diagnostic_artifact_id=diagnostic_artifact_id,
        )
        with self._mutex:
            current = self.record
            self._require_mutable(current)
            return self._finish(current, STATUS_FAILED, error=clean_error)

    def cancel(self, *, summary="Training was cancelled by the user.", stage="training"):
        clean_error = _clean_error(
            code="user_cancelled",
            summary=summary,
            stage=stage,
            recoverable=True,
        )
        with self._mutex:
            current = self.record
            self._require_mutable(current)
            return self._finish(current, STATUS_CANCELLED, error=clean_error)

    def interrupt(
        self,
        *,
        code="process_interrupted",
        summary="Training stopped before reaching a completed result.",
        stage="training",
    ):
        clean_error = _clean_error(
            code=code,
            summary=summary,
            stage=stage,
            recoverable=True,
        )
        with self._mutex:
            current = self.record
            self._require_mutable(current)
            return self._finish(current, STATUS_INTERRUPTED, error=clean_error)

    @contextmanager
    def exception_boundary(self, *, stage="training"):
        try:
            yield self
        except (KeyboardInterrupt, SystemExit):
            if self.status in ACTIVE_STATUSES:
                self.interrupt(stage=stage)
            raise
        except BaseException as exc:
            if self.status in ACTIVE_STATUSES:
                self.fail(exc, stage=stage)
            raise

    def close(self):
        if not self._closed:
            self._closed = True
            self.recorder._release(self.run_id)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, _traceback):
        try:
            if exc_type is None:
                if self.status in ACTIVE_STATUSES:
                    self.interrupt(
                        code="context_exited_without_terminal",
                        summary="Training context exited without a success, failure, or cancellation result.",
                        stage="context",
                    )
            elif issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
                if self.status in ACTIVE_STATUSES:
                    self.interrupt(stage="context")
            elif self.status in ACTIVE_STATUSES:
                self.fail(exc, stage="context")
        finally:
            self.close()
        return False

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def _require_mutable(self, current):
        if current["status"] in TERMINAL_STATUSES:
            raise TerminalRunImmutable(f"terminal_run_immutable:{self.run_id}")
        self._ensure_open()
        if current["status"] not in ACTIVE_STATUSES:
            raise InvalidRunTransition(f"unknown_run_status:{current['status']}")

    def _ensure_open(self):
        if self._closed:
            raise TrainingRunRecordError(f"run_handle_closed:{self.run_id}")

    def _finish(self, current, status, *, error):
        previous_status = current["status"]
        current["status"] = status
        current["finished_at"] = utc_now()
        current["error"] = error
        result = self.recorder._update_record(
            current, expected_status=previous_status
        )
        self.close()
        return result

    def _validate_dataset_policy(self, record):
        dataset = record.get("dataset_ref")
        if not isinstance(dataset, dict):
            raise IncompleteSuccessfulRun("dataset_ref_missing")
        for field in ("dataset_id", "data_version_id", "trusted_label_policy"):
            if not str(dataset.get(field) or "").strip():
                raise IncompleteSuccessfulRun(f"dataset_ref_field_missing:{field}")
        if dataset["trusted_label_policy"] not in TRUSTED_LABEL_POLICIES:
            raise IncompleteSuccessfulRun("dataset_trusted_label_policy_invalid")
        base_fields = {
            "dataset_id",
            "data_version_id",
            "trusted_label_policy",
            "source_kind",
        }
        source_kind = dataset.get("source_kind")
        if source_kind == "project":
            if set(dataset) != base_fields:
                raise IncompleteSuccessfulRun("project_dataset_ref_fields_invalid")
            project = record.get("project_ref")
            if not isinstance(project, dict) or set(project) != set(PROJECT_REF_FIELDS):
                raise IncompleteSuccessfulRun("project_ref_incomplete")
            if any(not str(project.get(field) or "").strip() for field in PROJECT_REF_FIELDS):
                raise IncompleteSuccessfulRun("project_ref_incomplete")
        elif source_kind == "verified_external":
            if set(dataset) != base_fields | {"trusted_source_ref"}:
                raise IncompleteSuccessfulRun("external_dataset_ref_fields_invalid")
            if record.get("project_ref") not in ({}, None):
                raise IncompleteSuccessfulRun("external_project_ref_must_be_empty")
            if dataset.get("trusted_label_policy") != "verified_external_truth":
                raise IncompleteSuccessfulRun("external_dataset_policy_invalid")
            _validate_id(dataset.get("trusted_source_ref"), "trusted_source_ref")
        else:
            raise IncompleteSuccessfulRun("dataset_source_kind_invalid")

    def _integrity_payload(self, record):
        reference = record.get("integrity_manifest")
        if not isinstance(reference, dict):
            raise IncompleteSuccessfulRun("integrity_manifest_missing")
        self._verify_artifact(reference)
        return _read_json_object(self._resolve_artifact(reference))

    def _validate_integrity_manifest(self, record, *, require_recheck):
        reference = record.get("integrity_manifest")
        payload = self._integrity_payload(record)
        if payload.get("schema_version") != "taxamask_integrity_manifest_v1":
            raise IncompleteSuccessfulRun("integrity_manifest_schema_invalid")
        if payload.get("run_id") != self.run_id:
            raise IncompleteSuccessfulRun("integrity_manifest_run_id_mismatch")
        if payload.get("manifest_id") != reference.get("manifest_id"):
            raise IncompleteSuccessfulRun("integrity_manifest_id_mismatch")
        if payload.get("status") != "verified":
            raise IncompleteSuccessfulRun("integrity_manifest_not_verified")
        files = payload.get("files")
        if not isinstance(files, list) or not files:
            raise IncompleteSuccessfulRun("integrity_manifest_files_missing")
        if any(not isinstance(item, dict) or item.get("status") != "verified" for item in files):
            raise IncompleteSuccessfulRun("integrity_manifest_file_not_verified")
        if require_recheck and not str(payload.get("recheck_of") or "").strip():
            raise IncompleteSuccessfulRun("integrity_manifest_recheck_missing")
        require_verified_training_inputs(payload)
        return payload

    def _validate_split_reference(self, record, integrity_payload):
        split_ref = record.get("split_manifest")
        if not isinstance(split_ref, dict):
            raise IncompleteSuccessfulRun("split_manifest_missing")
        self._verify_artifact(split_ref)
        split_payload = _read_json_object(self._resolve_artifact(split_ref))
        _validate_split_manifest_payload(
            split_payload,
            self.run_id,
            dataset_ref=record.get("dataset_ref"),
            integrity_files={item["file_id"]: item for item in integrity_payload["files"]},
        )
        if split_payload.get("split_id") != split_ref.get("split_id"):
            raise IncompleteSuccessfulRun("split_manifest_id_mismatch")
        return split_payload

    def _validate_effective_config(self, record, *, allow_pending_external=False):
        config = record.get("effective_config")
        if not isinstance(config, dict):
            raise IncompleteSuccessfulRun("effective_config_missing")
        if config.get("resolution_status") == "pending_external":
            if not allow_pending_external:
                raise IncompleteSuccessfulRun(
                    "external_effective_config_not_resolved"
                )
            if set(config) != {
                "resolution_status",
                "adapter_invocation",
                "persist_weights",
            }:
                raise IncompleteSuccessfulRun(
                    "pending_external_config_fields_invalid"
                )
            if not isinstance(config.get("adapter_invocation"), dict):
                raise IncompleteSuccessfulRun(
                    "pending_external_adapter_invocation_invalid"
                )
            if not isinstance(config.get("persist_weights"), bool):
                raise IncompleteSuccessfulRun(
                    "effective_config_persist_weights_invalid"
                )
            _assert_safe_payload(config, field_path="effective_config")
            return
        missing = REQUIRED_EFFECTIVE_CONFIG_FIELDS - set(config)
        if missing:
            raise IncompleteSuccessfulRun(
                f"effective_config_field_missing:{sorted(missing)[0]}"
            )
        smoke_execution = config.get("execution_kind") in {
            "contract_smoke",
            "backend_dry_run",
        }
        if smoke_execution and config.get("persist_weights") is not False:
            raise IncompleteSuccessfulRun(
                "smoke_effective_config_must_not_persist_weights"
            )
        for field in ("epochs", "batch_size"):
            value = config.get(field)
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or (value < 0 if smoke_execution else value <= 0)
            ):
                raise IncompleteSuccessfulRun(f"effective_config_value_invalid:{field}")
        for field, allow_zero in (("learning_rate", False), ("weight_decay", True)):
            value = config.get(field)
            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not math.isfinite(float(value))
                or (
                    float(value) < 0
                    if allow_zero or smoke_execution
                    else float(value) <= 0
                )
            ):
                raise IncompleteSuccessfulRun(f"effective_config_value_invalid:{field}")
        seed = config.get("random_seed")
        if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
            raise IncompleteSuccessfulRun("effective_config_value_invalid:random_seed")
        resolution = config.get("input_resolution")
        if (
            not isinstance(resolution, (list, tuple))
            or len(resolution) not in {2, 3}
            or any(
                not isinstance(value, int) or isinstance(value, bool) or value <= 0
                for value in resolution
            )
        ):
            raise IncompleteSuccessfulRun("effective_config_value_invalid:input_resolution")
        model = config.get("model")
        if not isinstance(model, dict):
            raise IncompleteSuccessfulRun("effective_config_model_missing")
        for field in ("family", "version"):
            if not str(model.get(field) or "").strip():
                raise IncompleteSuccessfulRun(f"effective_config_model_field_missing:{field}")
        if not isinstance(config.get("preprocessing"), dict):
            raise IncompleteSuccessfulRun("effective_config_preprocessing_invalid")
        loss_weights = config.get("loss_weights")
        if not isinstance(loss_weights, dict):
            raise IncompleteSuccessfulRun("effective_config_loss_weights_invalid")
        if "persist_weights" in config and not isinstance(
            config.get("persist_weights"), bool
        ):
            raise IncompleteSuccessfulRun(
                "effective_config_persist_weights_invalid"
            )

        def validate_loss_values(values, prefix="loss_weights"):
            for key, value in values.items():
                if isinstance(value, dict):
                    validate_loss_values(value, f"{prefix}.{key}")
                elif (
                    not isinstance(value, (int, float))
                    or isinstance(value, bool)
                    or not math.isfinite(float(value))
                    or float(value) < 0
                ):
                    raise IncompleteSuccessfulRun(
                        f"effective_config_loss_weight_invalid:{prefix}.{key}"
                    )

        validate_loss_values(loss_weights)
        _assert_safe_payload(config, field_path="effective_config")

    def _validate_backend(self, record):
        backend = record.get("backend")
        if not isinstance(backend, dict):
            raise IncompleteSuccessfulRun("backend_missing")
        missing = BACKEND_REQUIRED_FIELDS - set(backend)
        if missing:
            raise IncompleteSuccessfulRun(f"backend_field_missing:{sorted(missing)[0]}")
        for field in BACKEND_REQUIRED_FIELDS:
            try:
                _validate_id(backend.get(field), f"backend_{field}")
            except UnsafeRunFact as exc:
                raise IncompleteSuccessfulRun(
                    f"backend_field_invalid:{field}"
                ) from exc
        _assert_safe_payload(backend, field_path="backend")

    def _validate_code_environment(self, record):
        code = record.get("code")
        if not isinstance(code, dict) or set(code) != set(CODE_FIELDS):
            raise IncompleteSuccessfulRun("code_revision_facts_incomplete")
        environment = record.get("environment")
        if not isinstance(environment, dict) or set(environment) != set(ENVIRONMENT_FIELDS):
            raise IncompleteSuccessfulRun("environment_facts_incomplete")
        for field in ENVIRONMENT_FIELDS:
            if not str(environment.get(field) or "").strip():
                raise IncompleteSuccessfulRun(f"environment_field_missing:{field}")
        _assert_safe_payload(environment, field_path="environment")

    def _validate_success(self, record):
        config = record.get("effective_config") or {}
        self._validate_dataset_policy(record)
        integrity_payload = self._validate_integrity_manifest(record, require_recheck=True)
        if any(
            item.get("role") in PROTECTED_FULL_HASH_ROLES
            and item.get("hash_algorithm") == QUICK_FILE_ALGORITHM
            for item in integrity_payload["files"]
        ):
            raise IncompleteSuccessfulRun(
                "protected_training_input_quick_fingerprint"
            )
        self._validate_split_reference(record, integrity_payload)
        self._validate_effective_config(record)
        self._validate_backend(record)
        self._validate_code_environment(record)

        artifacts = record.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            raise IncompleteSuccessfulRun("training_artifacts_missing")
        artifact_ids = set()
        has_output_weights = False
        for artifact in artifacts:
            _validate_artifact_record(artifact)
            artifact_id = artifact["artifact_id"]
            if artifact_id in artifact_ids:
                raise IncompleteSuccessfulRun(f"artifact_id_duplicate:{artifact_id}")
            artifact_ids.add(artifact_id)
            has_output_weights = has_output_weights or artifact.get("role") == "output_weights"
            if (
                artifact.get("role") in PROTECTED_FULL_HASH_ROLES
                and artifact.get("hash_algorithm") == QUICK_FILE_ALGORITHM
            ):
                raise IncompleteSuccessfulRun(
                    f"protected_artifact_quick_fingerprint:{artifact_id}"
                )
            self._verify_artifact(artifact)
        if config.get("persist_weights", True) and not has_output_weights:
            raise IncompleteSuccessfulRun("output_weights_artifact_missing")

    def _resolve_artifact(self, artifact):
        path_base = artifact.get("path_base")
        if path_base not in self._path_bases:
            raise IncompleteSuccessfulRun(f"path_base_not_available:{path_base}")
        try:
            target, _relative = _managed_lexical_path(
                self._path_bases[path_base], artifact["relative_path"]
            )
        except UnsafeRunFact as exc:
            raise IncompleteSuccessfulRun(
                f"artifact_outside_path_base:{artifact.get('artifact_id')}"
            ) from exc
        return target

    def _verify_artifact(self, artifact):
        artifact_id = artifact.get("artifact_id")
        is_external = artifact.get("entry_kind") == "external_reference"
        if is_external:
            path = self._external_paths.get(artifact_id)
            if not path:
                raise IncompleteSuccessfulRun(
                    f"external_artifact_location_unavailable:{artifact_id}"
                )
        else:
            path = self._resolve_artifact(artifact)
        from AntSleap.core.file_integrity import compute_fingerprint

        current = compute_fingerprint(path, algorithm=artifact.get("hash_algorithm"))
        comparable_fields = ("size_bytes", "hash_algorithm", "digest")
        if not is_external:
            comparable_fields = ("entry_kind",) + comparable_fields
        for field in comparable_fields:
            expected = artifact.get(field)
            observed = current.get(field)
            if expected != observed:
                raise IncompleteSuccessfulRun(
                    f"artifact_fingerprint_mismatch:{artifact_id}:{field}"
                )


def _read_json_object(path):
    payload = _read_json_nofollow(path)
    if not isinstance(payload, dict):
        raise IncompleteSuccessfulRun("json_artifact_must_be_object")
    return payload


def _validate_split_manifest_payload(
    payload,
    run_id,
    *,
    dataset_ref=None,
    integrity_files=None,
):
    if not isinstance(payload, dict) or set(payload) != set(SPLIT_TOP_LEVEL_FIELDS):
        raise IncompleteSuccessfulRun("split_manifest_fields_invalid")
    if payload.get("schema_version") != "taxamask_training_split_v1":
        raise IncompleteSuccessfulRun("split_manifest_schema_invalid")
    if payload.get("run_id") != run_id:
        raise IncompleteSuccessfulRun("split_manifest_run_id_mismatch")
    if payload.get("status") != "verified":
        raise IncompleteSuccessfulRun("split_manifest_not_verified")
    if payload.get("error") is not None:
        raise IncompleteSuccessfulRun("split_manifest_error_invalid")
    _validate_id(payload.get("split_id"), "split_id")
    for field in ("created_at", "started_at", "finished_at"):
        _validate_iso_timestamp(payload.get(field), field)
    dataset_id = _validate_id(payload.get("dataset_id"), "dataset_id")
    if not isinstance(dataset_ref, dict) or dataset_id != dataset_ref.get("dataset_id"):
        raise IncompleteSuccessfulRun("split_dataset_id_mismatch")
    strategy = payload.get("strategy")
    if not isinstance(strategy, dict) or set(strategy) - {
        "name",
        "version",
        "seed",
        "validation_ratio",
    }:
        raise IncompleteSuccessfulRun("split_strategy_invalid")
    _validate_id(strategy.get("name"), "split_strategy_name")
    _validate_id(strategy.get("version"), "split_strategy_version")
    if not isinstance(strategy.get("seed"), int) or isinstance(strategy.get("seed"), bool):
        raise IncompleteSuccessfulRun("split_strategy_seed_invalid")
    validate_split_assignments(payload.get("assignments"))
    known_files = dict(integrity_files or {})
    allowed_truth_roles = TRUSTED_TRUTH_ROLES.get(
        (dataset_ref or {}).get("trusted_label_policy"), frozenset()
    )
    file_partitions = {}
    for assignment in payload["assignments"]:
        unexpected = set(assignment) - {
            "sample_id",
            "partition",
            "group_id",
            "input_file_ids",
        }
        if unexpected:
            raise IncompleteSuccessfulRun("split_assignment_fields_invalid")
        has_trusted_truth = False
        for file_id in assignment["input_file_ids"]:
            if file_id not in known_files:
                raise IncompleteSuccessfulRun(
                    f"split_input_file_not_verified:{file_id}"
                )
            entry = known_files[file_id]
            if entry.get("data_version_id") != dataset_ref.get("data_version_id"):
                raise IncompleteSuccessfulRun(
                    f"split_input_data_version_mismatch:{file_id}"
                )
            partition = assignment["partition"]
            prior = file_partitions.setdefault(file_id, partition)
            if prior != partition:
                raise IncompleteSuccessfulRun(
                    f"split_input_file_partition_leakage:{file_id}"
                )
            if entry.get("role") in allowed_truth_roles:
                has_trusted_truth = True
        if not has_trusted_truth:
            raise IncompleteSuccessfulRun(
                f"split_trusted_truth_missing:{assignment['sample_id']}"
            )
