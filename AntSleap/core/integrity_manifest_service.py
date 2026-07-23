"""Versioned integrity manifests and the non-bypassable training gate."""

from __future__ import annotations

import copy
import datetime as _datetime
import json
import os
import re
import stat
import threading
import unicodedata
import uuid
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Sequence

from .file_integrity import (
    DEFAULT_CHUNK_SIZE,
    FULL_FILE_ALGORITHM,
    QUICK_FILE_ALGORITHM,
    TREE_ALGORITHM,
    FingerprintCancelled,
    FingerprintError,
    compute_fingerprint,
)
from .safe_io import atomic_write_json


SCHEMA_VERSION = "taxamask_integrity_manifest_v1"
PATH_BASES = frozenset(
    {
        "project_root",
        "run_root",
        "export_root",
        "managed_model_root",
        "runtime_log_root",
    }
)
MANIFEST_STATUSES = frozenset(
    {"pending", "verified", "mismatch", "missing", "incomplete"}
)
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
    }
)
_TERMINAL_STATUSES = frozenset({"verified", "mismatch", "missing", "incomplete"})
_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "manifest_id",
        "run_id",
        "status",
        "phase",
        "created_at",
        "started_at",
        "finished_at",
        "attempt",
        "retry_of",
        "recheck_of",
        "supersedes",
        "baseline_captured_at",
        "note_ref",
        "supersession",
        "relocations",
        "files",
        "error",
    }
)
_FILE_ENTRY_FIELDS = frozenset(
    {
        "file_id",
        "role",
        "path_base",
        "relative_path",
        "external_location_ref",
        "entry_kind",
        "size_bytes",
        "mtime_ns",
        "hash_algorithm",
        "digest",
        "status",
        "verified_at",
        "baseline_captured_at",
        "data_version_id",
        "error",
        "expected_entry_kind",
        "expected_size_bytes",
        "expected_mtime_ns",
        "expected_hash_algorithm",
        "expected_digest",
    }
)
_ERROR_FIELDS = frozenset(
    {"code", "summary", "stage", "recoverable", "diagnostic_artifact_id"}
)
_MANIFEST_PHASES = frozenset({"baseline_capture", "verification"})
_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_HEX_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")
_ABSOLUTE_NOTE_PATH_RE = re.compile(
    r"(?:[A-Za-z]:[\\/][^\s]+|\\\\[^\s]+|/(?:home|Users)/[^\s]+)"
)
_SECRET_NOTE_RE = re.compile(
    r"(?i)\b(?:api[_ -]?key|access[_ -]?token|secret|password)\b\s*[:=]\s*[^\s]+"
)


def _error(
    code: str,
    summary: str,
    *,
    stage: str = "integrity_verify",
    recoverable: bool = True,
) -> Dict[str, object]:
    return {
        "code": str(code),
        "summary": str(summary),
        "stage": str(stage),
        "recoverable": bool(recoverable),
        "diagnostic_artifact_id": None,
    }


class IntegrityManifestError(ValueError):
    def __init__(self, error: Mapping[str, object], *, issues=None) -> None:
        self.error = dict(error)
        self.code = str(self.error.get("code", "integrity_manifest_error"))
        self.issues = list(issues or [])
        super().__init__(str(self.error.get("summary", "The integrity operation failed.")))

    def as_error(self) -> Dict[str, object]:
        result = dict(self.error)
        if self.issues:
            result["issues"] = copy.deepcopy(self.issues)
        return result


class IntegrityGateError(IntegrityManifestError):
    pass


def _raise_manifest_error(
    code: str,
    summary: str,
    *,
    stage: str = "integrity_manifest",
    recoverable: bool = False,
    issues=None,
) -> None:
    raise IntegrityManifestError(
        _error(code, summary, stage=stage, recoverable=recoverable), issues=issues
    )


def _validate_timestamp(value, field_name, *, allow_none=True):
    if value is None and allow_none:
        return None
    if not isinstance(value, str) or not value:
        _raise_manifest_error(
            "invalid_manifest_time", f"The {field_name} timestamp is invalid."
        )
    try:
        parsed = _datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise IntegrityManifestError(
            _error(
                "invalid_manifest_time",
                f"The {field_name} timestamp is invalid.",
                stage="integrity_manifest",
                recoverable=False,
            )
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _raise_manifest_error(
            "invalid_manifest_time", f"The {field_name} timestamp must include a timezone."
        )
    return value


def _clean_error_payload(value, *, required):
    if value is None:
        if required:
            _raise_manifest_error(
                "invalid_manifest_error", "An unsuccessful state requires an error."
            )
        return None
    if not isinstance(value, Mapping):
        _raise_manifest_error("invalid_manifest_error", "The integrity error is invalid.")
    code = _validate_id(value.get("code"), "error_code")
    stage = _validate_id(value.get("stage"), "error_stage")
    summary = " ".join(str(value.get("summary") or "").split())[:500]
    if (
        not summary
        or _ABSOLUTE_NOTE_PATH_RE.search(summary)
        or _SECRET_NOTE_RE.search(summary)
    ):
        summary = "The integrity operation did not finish; sensitive details were omitted."
    recoverable = value.get("recoverable")
    if not isinstance(recoverable, bool):
        _raise_manifest_error(
            "invalid_manifest_error", "The integrity error recovery flag is invalid."
        )
    diagnostic = value.get("diagnostic_artifact_id")
    if diagnostic is not None:
        diagnostic = _validate_id(diagnostic, "diagnostic_artifact_id")
    return {
        "code": code,
        "summary": summary,
        "stage": stage,
        "recoverable": recoverable,
        "diagnostic_artifact_id": diagnostic,
    }


def _now_iso() -> str:
    return _datetime.datetime.now().astimezone().isoformat(timespec="microseconds")


def _new_id(prefix: str) -> str:
    timestamp = _datetime.datetime.now(_datetime.timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )
    return f"{prefix}_{timestamp}_{uuid.uuid4().hex[:8]}"


def _validate_id(value, field_name: str) -> str:
    text = str(value or "")
    if not text or not _ID_RE.fullmatch(text):
        _raise_manifest_error(
            "invalid_record_id", f"The {field_name} is not a valid stable identifier."
        )
    return text


def validate_relative_path(relative_path) -> str:
    """Return an NFC/POSIX relative path or reject it without echoing it."""

    if not isinstance(relative_path, str):
        _raise_manifest_error(
            "invalid_relative_path", "A managed relative path is invalid."
        )
    normalised = unicodedata.normalize("NFC", relative_path)
    if (
        not normalised
        or "\0" in normalised
        or "\\" in normalised
        or normalised.startswith("/")
        or _WINDOWS_DRIVE_RE.match(normalised)
    ):
        _raise_manifest_error(
            "invalid_relative_path", "A managed relative path is invalid."
        )
    segments = normalised.split("/")
    if any(segment in {"", ".", ".."} for segment in segments):
        _raise_manifest_error(
            "invalid_relative_path", "A managed relative path is invalid."
        )
    return normalised


def _normalise_algorithm(algorithm):
    if algorithm is None:
        return None
    selected = str(algorithm).strip().lower()
    if selected == "quick_fingerprint":
        selected = QUICK_FILE_ALGORITHM
    if selected not in {FULL_FILE_ALGORITHM, TREE_ALGORITHM, QUICK_FILE_ALGORITHM}:
        _raise_manifest_error(
            "unsupported_hash_algorithm",
            "The requested integrity algorithm is not supported.",
        )
    return selected


def build_file_entry(
    file_id,
    role,
    path_base,
    relative_path,
    data_version_id,
    *,
    algorithm=None,
    entry_kind=None,
) -> Dict[str, object]:
    """Build a pending, path-safe integrity entry for a run-scoped manifest."""

    file_id = _validate_id(file_id, "file_id")
    role = _validate_id(role, "file_role")
    path_base = str(path_base or "")
    if path_base not in PATH_BASES:
        _raise_manifest_error("unknown_path_base", "The managed path base is unknown.")
    relative_path = validate_relative_path(relative_path)
    data_version_id = _validate_id(data_version_id, "data_version_id")
    algorithm = _normalise_algorithm(algorithm)
    if entry_kind not in {None, "file", "directory"}:
        _raise_manifest_error("invalid_entry_kind", "The integrity entry kind is invalid.")
    if entry_kind == "directory" and algorithm not in {None, TREE_ALGORITHM}:
        _raise_manifest_error(
            "unsupported_hash_algorithm",
            "Directories must use sha256-tree-v1.",
        )
    if entry_kind == "file" and algorithm == TREE_ALGORITHM:
        _raise_manifest_error(
            "unsupported_hash_algorithm", "Files cannot use sha256-tree-v1."
        )
    _validate_role_algorithm(role, entry_kind, algorithm)
    return {
        "file_id": file_id,
        "role": role,
        "path_base": path_base,
        "relative_path": relative_path,
        "entry_kind": entry_kind,
        "size_bytes": None,
        "mtime_ns": None,
        "hash_algorithm": algorithm,
        "digest": None,
        "status": "pending",
        "verified_at": None,
        "data_version_id": data_version_id,
        "error": None,
    }


def build_external_file_entry(
    file_id,
    role,
    external_location_ref,
    data_version_id,
    *,
    algorithm=None,
) -> Dict[str, object]:
    """Build a pending external reference without archiving its local path."""

    file_id = _validate_id(file_id, "file_id")
    role = _validate_id(role, "file_role")
    external_location_ref = _validate_id(
        external_location_ref, "external_location_ref"
    )
    data_version_id = _validate_id(data_version_id, "data_version_id")
    algorithm = _normalise_algorithm(algorithm)
    _validate_role_algorithm(role, "external_reference", algorithm)
    return {
        "file_id": file_id,
        "role": role,
        "entry_kind": "external_reference",
        "external_location_ref": external_location_ref,
        "size_bytes": None,
        "mtime_ns": None,
        "hash_algorithm": algorithm,
        "digest": None,
        "status": "pending",
        "verified_at": None,
        "data_version_id": data_version_id,
        "error": None,
    }


def _validate_digest_fields(entry: Mapping[str, object], status: str) -> None:
    kind = entry.get("entry_kind")
    algorithm = entry.get("hash_algorithm")
    digest = entry.get("digest")
    size = entry.get("size_bytes")
    if status in {"verified", "mismatch"}:
        if kind not in {"file", "directory", "external_reference"}:
            _raise_manifest_error("invalid_entry_kind", "A completed entry kind is invalid.")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            _raise_manifest_error(
                "invalid_integrity_size", "A completed integrity size is invalid."
            )
        if algorithm not in {FULL_FILE_ALGORITHM, TREE_ALGORITHM, QUICK_FILE_ALGORITHM}:
            _raise_manifest_error(
                "unsupported_hash_algorithm",
                "A completed integrity algorithm is invalid.",
            )
        if kind == "directory" and algorithm != TREE_ALGORITHM:
            _raise_manifest_error(
                "unsupported_hash_algorithm",
                "Directories must use sha256-tree-v1.",
            )
        if kind == "file" and algorithm == TREE_ALGORITHM:
            _raise_manifest_error(
                "unsupported_hash_algorithm", "Files cannot use sha256-tree-v1."
            )
        if not isinstance(digest, str) or not _HEX_DIGEST_RE.fullmatch(digest):
            _raise_manifest_error(
                "invalid_integrity_digest", "A completed integrity digest is invalid."
            )
        mtime_ns = entry.get("mtime_ns")
        if kind != "external_reference" and (
            not isinstance(mtime_ns, int)
            or isinstance(mtime_ns, bool)
            or mtime_ns < 0
        ):
            _raise_manifest_error(
                "invalid_integrity_mtime", "A completed integrity modification time is invalid."
            )
        if kind == "external_reference" and mtime_ns is not None and (
            not isinstance(mtime_ns, int)
            or isinstance(mtime_ns, bool)
            or mtime_ns < 0
        ):
            _raise_manifest_error(
                "invalid_integrity_mtime", "An external modification time is invalid."
            )
    elif kind is not None and kind not in {"file", "directory", "external_reference"}:
        _raise_manifest_error("invalid_entry_kind", "The integrity entry kind is invalid.")


def _validate_role_algorithm(role, entry_kind, algorithm) -> None:
    if algorithm is None or role not in PROTECTED_FULL_HASH_ROLES:
        return
    if algorithm == QUICK_FILE_ALGORITHM:
        _raise_manifest_error(
            "quick_fingerprint_not_archival",
            "This protected file role requires a complete integrity hash.",
        )
    if entry_kind == "directory" and algorithm != TREE_ALGORITHM:
        _raise_manifest_error(
            "protected_hash_algorithm_invalid",
            "A protected directory must use sha256-tree-v1.",
        )
    if entry_kind == "file" and algorithm != FULL_FILE_ALGORITHM:
        _raise_manifest_error(
            "protected_hash_algorithm_invalid",
            "A protected file must use complete sha256.",
        )


def validate_manifest(manifest: Mapping[str, object]) -> Dict[str, object]:
    if not isinstance(manifest, Mapping):
        _raise_manifest_error("manifest_invalid", "The integrity manifest is invalid.")
    payload = {
        key: copy.deepcopy(manifest[key])
        for key in _TOP_LEVEL_FIELDS
        if key in manifest
    }
    if payload.get("schema_version") != SCHEMA_VERSION:
        _raise_manifest_error(
            "unsupported_manifest_schema",
            "The integrity manifest schema is not supported.",
        )
    payload["manifest_id"] = _validate_id(payload.get("manifest_id"), "manifest_id")
    payload["run_id"] = _validate_id(payload.get("run_id"), "run_id")
    status = payload.get("status")
    if status not in MANIFEST_STATUSES:
        _raise_manifest_error("invalid_manifest_status", "The manifest status is invalid.")
    phase = payload.get("phase")
    if phase is not None and phase not in _MANIFEST_PHASES:
        _raise_manifest_error("invalid_manifest_phase", "The manifest phase is invalid.")
    payload["created_at"] = _validate_timestamp(
        payload.get("created_at"), "created_at", allow_none=False
    )
    payload["started_at"] = _validate_timestamp(payload.get("started_at"), "started_at")
    payload["finished_at"] = _validate_timestamp(payload.get("finished_at"), "finished_at")
    if "baseline_captured_at" in payload:
        payload["baseline_captured_at"] = _validate_timestamp(
            payload.get("baseline_captured_at"), "baseline_captured_at"
        )
    attempt = payload.get("attempt")
    if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
        _raise_manifest_error("invalid_manifest_attempt", "The manifest attempt is invalid.")
    for relation in ("retry_of", "recheck_of", "supersedes"):
        if payload.get(relation) is not None:
            payload[relation] = _validate_id(payload[relation], relation)
    if payload.get("note_ref") is not None:
        payload["note_ref"] = _validate_id(payload["note_ref"], "note_ref")
    if status == "pending" and payload.get("finished_at") is not None:
        _raise_manifest_error(
            "invalid_manifest_time", "A pending manifest cannot have a finish time."
        )
    if status in _TERMINAL_STATUSES and not payload.get("finished_at"):
        _raise_manifest_error(
            "invalid_manifest_time", "A completed manifest requires a finish time."
        )
    payload["error"] = _clean_error_payload(
        payload.get("error"), required=status in {"mismatch", "missing", "incomplete"}
    )
    if status in {"pending", "verified"} and payload["error"] is not None:
        _raise_manifest_error(
            "invalid_manifest_error", "This manifest status cannot contain an error."
        )
    files = payload.get("files")
    if not isinstance(files, list) or not files:
        _raise_manifest_error("manifest_files_missing", "The manifest has no file entries.")
    seen_ids = set()
    clean_files = []
    for raw_entry in files:
        if not isinstance(raw_entry, Mapping):
            _raise_manifest_error("manifest_entry_invalid", "A manifest entry is invalid.")
        entry = {
            key: copy.deepcopy(raw_entry[key])
            for key in _FILE_ENTRY_FIELDS
            if key in raw_entry
        }
        file_id = _validate_id(entry.get("file_id"), "file_id")
        entry["file_id"] = file_id
        if file_id in seen_ids:
            _raise_manifest_error(
                "duplicate_file_id", "The manifest contains duplicate file identifiers."
            )
        seen_ids.add(file_id)
        entry["role"] = _validate_id(entry.get("role"), "file_role")
        if entry.get("entry_kind") == "external_reference":
            if "path_base" in raw_entry or "relative_path" in raw_entry:
                _raise_manifest_error(
                    "external_reference_path_not_allowed",
                    "An external reference cannot archive a local path.",
                )
            entry.pop("path_base", None)
            entry.pop("relative_path", None)
            entry["external_location_ref"] = _validate_id(
                entry.get("external_location_ref"), "external_location_ref"
            )
        else:
            if "external_location_ref" in raw_entry:
                _raise_manifest_error(
                    "managed_reference_external_location_not_allowed",
                    "A managed file cannot mix an external location reference.",
                )
            entry.pop("external_location_ref", None)
            if entry.get("path_base") not in PATH_BASES:
                _raise_manifest_error("unknown_path_base", "The managed path base is unknown.")
            entry["relative_path"] = validate_relative_path(entry.get("relative_path"))
        entry["data_version_id"] = _validate_id(
            entry.get("data_version_id"), "data_version_id"
        )
        entry_status = entry.get("status")
        if entry_status not in MANIFEST_STATUSES:
            _raise_manifest_error("invalid_entry_status", "A file status is invalid.")
        entry["error"] = _clean_error_payload(
            entry.get("error"),
            required=entry_status in {"mismatch", "missing", "incomplete"},
        )
        if entry_status in {"pending", "verified"} and entry["error"] is not None:
            _raise_manifest_error(
                "invalid_manifest_error", "This file status cannot contain an error."
            )
        entry["verified_at"] = _validate_timestamp(
            entry.get("verified_at"), "verified_at"
        )
        if entry_status in {"verified", "mismatch"} and entry["verified_at"] is None:
            _raise_manifest_error(
                "invalid_manifest_time", "A checked file requires verified_at."
            )
        if "baseline_captured_at" in entry:
            entry["baseline_captured_at"] = _validate_timestamp(
                entry.get("baseline_captured_at"), "baseline_captured_at"
            )
        if entry.get("hash_algorithm") is not None:
            entry["hash_algorithm"] = _normalise_algorithm(entry["hash_algorithm"])
        _validate_digest_fields(entry, entry_status)
        _validate_role_algorithm(
            entry["role"], entry.get("entry_kind"), entry.get("hash_algorithm")
        )
        expected_fields = (
            entry.get("expected_entry_kind"),
            entry.get("expected_size_bytes"),
            entry.get("expected_hash_algorithm"),
            entry.get("expected_digest"),
        )
        if any(value is not None for value in expected_fields):
            if any(value is None for value in expected_fields):
                _raise_manifest_error(
                    "expected_fingerprint_incomplete",
                    "The expected integrity fingerprint is incomplete.",
                )
            expected_kind, expected_size, expected_algorithm, expected_digest = expected_fields
            expected_algorithm = _normalise_algorithm(expected_algorithm)
            entry["expected_hash_algorithm"] = expected_algorithm
            if expected_kind not in {"file", "directory", "external_reference"}:
                _raise_manifest_error(
                    "invalid_entry_kind", "The expected integrity entry kind is invalid."
                )
            if (
                not isinstance(expected_size, int)
                or isinstance(expected_size, bool)
                or expected_size < 0
            ):
                _raise_manifest_error(
                    "invalid_integrity_size", "The expected integrity size is invalid."
                )
            if not isinstance(expected_digest, str) or not _HEX_DIGEST_RE.fullmatch(
                expected_digest
            ):
                _raise_manifest_error(
                    "invalid_integrity_digest", "The expected integrity digest is invalid."
                )
            _validate_role_algorithm(entry["role"], expected_kind, expected_algorithm)
            if entry.get("expected_mtime_ns") is not None and (
                not isinstance(entry["expected_mtime_ns"], int)
                or isinstance(entry["expected_mtime_ns"], bool)
                or entry["expected_mtime_ns"] < 0
            ):
                _raise_manifest_error(
                    "invalid_integrity_mtime",
                    "The expected integrity modification time is invalid.",
                )
        clean_files.append(entry)
    payload["files"] = clean_files
    if status in _TERMINAL_STATUSES and _top_status(clean_files) != status:
        _raise_manifest_error(
            "manifest_status_conflict",
            "The manifest status conflicts with its file entries.",
        )

    if "relocations" in payload:
        if not isinstance(payload["relocations"], list):
            _raise_manifest_error("relocation_audit_invalid", "Relocation audit is invalid.")
        clean_relocations = []
        for raw in payload["relocations"]:
            if not isinstance(raw, Mapping):
                _raise_manifest_error(
                    "relocation_audit_invalid", "Relocation audit is invalid."
                )
            old = raw.get("from")
            new = raw.get("to")
            if not isinstance(old, Mapping) or not isinstance(new, Mapping):
                _raise_manifest_error(
                    "relocation_audit_invalid", "Relocation audit is invalid."
                )
            external_audit = "external_location_ref" in old or "external_location_ref" in new
            if external_audit:
                if set(old) != {"external_location_ref"} or set(new) != {
                    "external_location_ref"
                }:
                    _raise_manifest_error(
                        "relocation_audit_invalid", "Relocation audit is invalid."
                    )
                old_location = {
                    "external_location_ref": _validate_id(
                        old.get("external_location_ref"), "external_location_ref"
                    )
                }
                new_location = {
                    "external_location_ref": _validate_id(
                        new.get("external_location_ref"), "external_location_ref"
                    )
                }
            else:
                old_location = {
                    "path_base": _validate_id(old.get("path_base"), "path_base"),
                    "relative_path": validate_relative_path(old.get("relative_path")),
                }
                new_location = {
                    "path_base": _validate_id(new.get("path_base"), "path_base"),
                    "relative_path": validate_relative_path(new.get("relative_path")),
                }
            clean_relocations.append(
                {
                    "file_id": _validate_id(raw.get("file_id"), "file_id"),
                    "from": old_location,
                    "to": new_location,
                    "verified_at": _validate_timestamp(
                        raw.get("verified_at"), "relocation_verified_at", allow_none=False
                    ),
                    "hash_algorithm": _normalise_algorithm(raw.get("hash_algorithm")),
                    "digest": str(raw.get("digest") or ""),
                }
            )
            if not _HEX_DIGEST_RE.fullmatch(clean_relocations[-1]["digest"]):
                _raise_manifest_error(
                    "invalid_integrity_digest", "A relocation digest is invalid."
                )
        payload["relocations"] = clean_relocations
    if "supersession" in payload:
        raw = payload["supersession"]
        if not isinstance(raw, Mapping):
            _raise_manifest_error("supersession_audit_invalid", "Supersession audit is invalid.")
        note = str(raw.get("note") or "").strip()[:1000]
        note = _ABSOLUTE_NOTE_PATH_RE.sub("[REDACTED_PATH]", note)
        note = _SECRET_NOTE_RE.sub("[REDACTED_SECRET]", note)
        payload["supersession"] = {
            "file_id": _validate_id(raw.get("file_id"), "file_id"),
            "previous_data_version_id": _validate_id(
                raw.get("previous_data_version_id"), "data_version_id"
            ),
            "new_data_version_id": _validate_id(
                raw.get("new_data_version_id"), "data_version_id"
            ),
            "reason_code": _validate_id(raw.get("reason_code"), "reason_code"),
            "note": note,
            "recorded_at": _validate_timestamp(
                raw.get("recorded_at"), "supersession_recorded_at", allow_none=False
            ),
        }
    return payload


def load_manifest(path) -> Dict[str, object]:
    try:
        with open(os.fspath(path), "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError, TypeError) as exc:
        raise IntegrityManifestError(
            _error(
                "manifest_unreadable",
                "The integrity manifest could not be read.",
                stage="integrity_manifest",
                recoverable=True,
            )
        ) from exc
    return validate_manifest(payload)


def write_manifest(path, manifest: Mapping[str, object]) -> Dict[str, object]:
    payload = validate_manifest(manifest)
    try:
        atomic_write_json(os.fspath(path), payload, indent=2, ensure_ascii=False)
    except OSError as exc:
        raise IntegrityManifestError(
            _error(
                "manifest_write_failed",
                "The integrity manifest could not be written atomically.",
                stage="integrity_manifest",
                recoverable=True,
            )
        ) from exc
    return payload


def _safe_commonpath_contains(base: str, target: str) -> bool:
    try:
        common = os.path.commonpath([base, target])
    except ValueError:
        return False
    return os.path.normcase(common) == os.path.normcase(base)


def _resolve_managed_path(
    path_base: str,
    relative_path: str,
    roots: Mapping[str, str],
) -> str:
    if path_base not in PATH_BASES or path_base not in roots:
        _raise_manifest_error(
            "path_base_unavailable",
            "The managed path base is not available on this workstation.",
            stage="integrity_verify",
            recoverable=True,
        )
    relative_path = validate_relative_path(relative_path)
    try:
        base = str(Path(os.fspath(roots[path_base])).resolve(strict=True))
    except (OSError, TypeError) as exc:
        raise IntegrityManifestError(
            _error(
                "path_base_unavailable",
                "The managed path base is not available on this workstation.",
                recoverable=True,
            )
        ) from exc
    candidate = Path(base).joinpath(*relative_path.split("/"))
    try:
        resolved = str(candidate.resolve(strict=False))
    except OSError as exc:
        raise IntegrityManifestError(
            _error(
                "managed_path_unresolvable",
                "The managed relative path could not be resolved safely.",
                recoverable=True,
            )
        ) from exc
    if not _safe_commonpath_contains(base, resolved):
        _raise_manifest_error(
            "managed_path_escape",
            "The managed relative path leaves its approved root.",
            stage="integrity_verify",
            recoverable=False,
        )
    # Hash the lexical path so the fingerprint layer can reject a symlink or
    # junction at the artifact root. ``resolved`` is used only for containment.
    return str(candidate)


def _fingerprint_error(exc: BaseException) -> Dict[str, object]:
    if isinstance(exc, FingerprintError):
        return exc.as_error()
    if isinstance(exc, IntegrityManifestError):
        return dict(exc.error)
    if isinstance(exc, FileNotFoundError):
        return _error("source_missing", "The recorded integrity source is missing.")
    if isinstance(exc, PermissionError):
        return _error(
            "source_read_denied", "The recorded integrity source cannot be read."
        )
    return _error(
        "integrity_check_failed", "The integrity source could not be verified."
    )


def _preserve_expected(entry: Dict[str, object]) -> None:
    for key in ("entry_kind", "size_bytes", "mtime_ns", "hash_algorithm", "digest"):
        value = entry.get(key)
        if value is not None and f"expected_{key}" not in entry:
            entry[f"expected_{key}"] = value


def _apply_observed(entry: Dict[str, object], observed: Mapping[str, object]) -> None:
    external = entry.get("entry_kind") == "external_reference"
    for key in ("entry_kind", "size_bytes", "mtime_ns", "hash_algorithm", "digest"):
        if external and key == "entry_kind":
            continue
        entry[key] = observed.get(key)


def _clear_observed(entry: Dict[str, object]) -> None:
    external = entry.get("entry_kind") == "external_reference"
    for key in ("entry_kind", "size_bytes", "mtime_ns", "hash_algorithm", "digest"):
        if external and key == "entry_kind":
            continue
        entry[key] = None


def _expected_values(entry: Mapping[str, object]) -> Dict[str, object]:
    result = {
        key: entry.get(f"expected_{key}", entry.get(key))
        for key in ("entry_kind", "size_bytes", "hash_algorithm", "digest")
    }
    if entry.get("entry_kind") == "external_reference":
        result["entry_kind"] = "external_reference"
    return result


def _entry_matches_expected(
    expected: Mapping[str, object], observed: Mapping[str, object]
) -> bool:
    return all(
        expected.get(key) == observed.get(key)
        for key in ("entry_kind", "size_bytes", "hash_algorithm", "digest")
    )


def _has_complete_expected(expected: Mapping[str, object]) -> bool:
    return (
        expected.get("entry_kind") in {"file", "directory", "external_reference"}
        and isinstance(expected.get("size_bytes"), int)
        and not isinstance(expected.get("size_bytes"), bool)
        and expected.get("size_bytes") >= 0
        and expected.get("hash_algorithm")
        in {FULL_FILE_ALGORITHM, TREE_ALGORITHM, QUICK_FILE_ALGORITHM}
        and isinstance(expected.get("digest"), str)
        and bool(_HEX_DIGEST_RE.fullmatch(expected["digest"]))
    )


def _phase_for_files(files: Sequence[Mapping[str, object]]) -> str:
    return (
        "verification"
        if all(_has_complete_expected(_expected_values(entry)) for entry in files)
        else "baseline_capture"
    )


def _manifest_phase(payload: Mapping[str, object]) -> str:
    phase = payload.get("phase")
    if phase in _MANIFEST_PHASES:
        return phase
    return _phase_for_files(payload.get("files") or [])


def _top_status(files: Sequence[Mapping[str, object]]) -> str:
    statuses = [entry.get("status") for entry in files]
    if "mismatch" in statuses:
        return "mismatch"
    if "missing" in statuses:
        return "missing"
    if any(status != "verified" for status in statuses):
        return "incomplete"
    return "verified"


def _top_error(status: str):
    if status == "verified":
        return None
    if status == "mismatch":
        return _error(
            "manifest_digest_mismatch",
            "One or more recorded files no longer match their integrity records.",
        )
    if status == "missing":
        return _error(
            "manifest_source_missing", "One or more recorded files are missing."
        )
    return _error(
        "manifest_incomplete", "The integrity check did not finish for every file."
    )


class _ManifestActivityLock:
    def __init__(self, path):
        self.path = os.path.abspath(os.fspath(path))
        self.handle = None

    def acquire(self) -> bool:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        if os.path.lexists(self.path):
            result = os.lstat(self.path)
            attributes = int(getattr(result, "st_file_attributes", 0) or 0)
            reparse = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
            if stat.S_ISLNK(result.st_mode) or attributes & reparse or not stat.S_ISREG(
                result.st_mode
            ):
                raise IntegrityManifestError(
                    _error(
                        "manifest_lock_unsafe",
                        "The integrity activity lock is not a safe regular file.",
                        stage="integrity_manifest",
                        recoverable=False,
                    )
                )
        flags = os.O_RDWR | os.O_CREAT | int(getattr(os, "O_BINARY", 0))
        flags |= int(getattr(os, "O_NOFOLLOW", 0))
        try:
            descriptor = os.open(self.path, flags, 0o600)
            handle = os.fdopen(descriptor, "r+b", closefd=True)
            result = os.fstat(handle.fileno())
            attributes = int(getattr(result, "st_file_attributes", 0) or 0)
            reparse = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
            if not stat.S_ISREG(result.st_mode) or attributes & reparse:
                handle.close()
                raise IntegrityManifestError(
                    _error(
                        "manifest_lock_unsafe",
                        "The integrity activity lock is not a safe regular file.",
                        stage="integrity_manifest",
                        recoverable=False,
                    )
                )
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
        except IntegrityManifestError:
            raise
        except (OSError, IOError):
            try:
                handle.close()
            except (UnboundLocalError, OSError):
                pass
            return False
        self.handle = handle
        return True

    def release(self) -> None:
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


def _locked_operation(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self._activity_guard():
            return method(self, *args, **kwargs)

    return wrapped


class IntegrityManifestService:
    def __init__(
        self,
        manifest_path,
        path_bases: Mapping[str, object],
        external_locations: Optional[Mapping[str, object]] = None,
    ) -> None:
        self.manifest_path = os.path.abspath(os.fspath(manifest_path))
        if not isinstance(path_bases, Mapping):
            _raise_manifest_error("path_bases_invalid", "Managed path bases are invalid.")
        unknown = set(path_bases) - PATH_BASES
        if unknown:
            _raise_manifest_error("unknown_path_base", "A managed path base is unknown.")
        self.path_bases = {
            str(key): os.path.abspath(os.fspath(value)) for key, value in path_bases.items()
        }
        if external_locations is not None and not isinstance(external_locations, Mapping):
            _raise_manifest_error(
                "external_locations_invalid", "External location mappings are invalid."
            )
        self.external_locations = {
            _validate_id(key, "external_location_ref"): os.path.abspath(os.fspath(value))
            for key, value in dict(external_locations or {}).items()
        }
        self.last_written_path = None
        self._local_mutex = threading.RLock()
        self._lock_depth = 0
        self._held_activity_lock = None

    def _resolve_entry_path(self, entry: Mapping[str, object]) -> str:
        if entry.get("entry_kind") == "external_reference":
            location_ref = _validate_id(
                entry.get("external_location_ref"), "external_location_ref"
            )
            if location_ref not in self.external_locations:
                raise IntegrityManifestError(
                    _error(
                        "external_location_unavailable",
                        "The external source location is not available on this workstation.",
                        stage="integrity_verify",
                        recoverable=True,
                    )
                )
            return self.external_locations[location_ref]
        return _resolve_managed_path(
            entry["path_base"], entry["relative_path"], self.path_bases
        )

    @staticmethod
    def _observed_for_entry(
        entry: Mapping[str, object], observed: Mapping[str, object]
    ) -> Dict[str, object]:
        result = dict(observed)
        if entry.get("entry_kind") == "external_reference":
            result["entry_kind"] = "external_reference"
        return result

    @contextmanager
    def _activity_guard(self):
        with self._local_mutex:
            if self._lock_depth == 0:
                lock = _ManifestActivityLock(f"{self.manifest_path}.activity.lock")
                if not lock.acquire():
                    raise IntegrityManifestError(
                        _error(
                            "manifest_busy",
                            "Another process is updating this integrity manifest.",
                            stage="integrity_manifest",
                            recoverable=True,
                        )
                    )
                self._held_activity_lock = lock
            self._lock_depth += 1
            try:
                yield
            finally:
                self._lock_depth -= 1
                if self._lock_depth == 0:
                    lock, self._held_activity_lock = self._held_activity_lock, None
                    if lock is not None:
                        lock.release()

    @_locked_operation
    def create_manifest(
        self,
        run_id,
        files: Iterable[Mapping[str, object]],
        *,
        manifest_id=None,
        retry_of=None,
        attempt=1,
    ) -> Dict[str, object]:
        if os.path.exists(self.manifest_path):
            _raise_manifest_error(
                "manifest_already_exists",
                "An integrity manifest already exists at the requested record location.",
            )
        clean_files = [copy.deepcopy(dict(entry)) for entry in files]
        if not clean_files:
            _raise_manifest_error("manifest_files_missing", "The manifest has no file entries.")
        now = _now_iso()
        payload = {
            "schema_version": SCHEMA_VERSION,
            "manifest_id": manifest_id or _new_id("integrity"),
            "run_id": run_id,
            "status": "pending",
            "phase": _phase_for_files(clean_files),
            "created_at": now,
            "started_at": None,
            "finished_at": None,
            "attempt": max(1, int(attempt)),
            "retry_of": retry_of,
            "files": clean_files,
            "error": None,
        }
        written = write_manifest(self.manifest_path, payload)
        self.last_written_path = self.manifest_path
        return written

    def load(self) -> Dict[str, object]:
        return load_manifest(self.manifest_path)

    def _write(self, payload: Mapping[str, object]) -> Dict[str, object]:
        written = write_manifest(self.manifest_path, payload)
        self.last_written_path = self.manifest_path
        return written

    @_locked_operation
    def capture_expected_fingerprints(
        self,
        *,
        chunk_size=DEFAULT_CHUNK_SIZE,
        progress_callback=None,
        cancel_check=None,
    ) -> Dict[str, object]:
        """Explicitly register current content as the expected data version."""

        payload = self.load()
        if (
            payload["status"] != "pending"
            or payload.get("started_at") is not None
            or _manifest_phase(payload) != "baseline_capture"
        ):
            raise IntegrityManifestError(
                _error(
                    "baseline_capture_not_allowed",
                    "A baseline can only be captured before integrity verification starts.",
                    stage="integrity_manifest",
                    recoverable=False,
                )
            )
        captured_at = _now_iso()
        payload["phase"] = "baseline_capture"
        payload["started_at"] = captured_at
        payload["finished_at"] = None
        payload["error"] = None
        self._write(payload)
        failed = False
        for entry in payload["files"]:
            expected = _expected_values(entry)
            if _has_complete_expected(expected):
                continue
            try:
                resolved = self._resolve_entry_path(entry)
                callback = None
                if progress_callback is not None:
                    file_id = entry["file_id"]

                    def callback(done, total, _file_id=file_id):
                        progress_callback(_file_id, done, total)

                observed = compute_fingerprint(
                    resolved,
                    entry.get("hash_algorithm"),
                    chunk_size=chunk_size,
                    progress_callback=callback,
                    cancel_check=cancel_check,
                )
                observed = self._observed_for_entry(entry, observed)
                _validate_role_algorithm(
                    entry["role"], observed["entry_kind"], observed["hash_algorithm"]
                )
                _apply_observed(entry, observed)
                entry["baseline_captured_at"] = captured_at
                entry["status"] = "pending"
                entry["verified_at"] = None
                entry["error"] = None
            except BaseException as exc:
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    raise
                _clear_observed(entry)
                entry["status"] = "incomplete"
                entry["verified_at"] = None
                entry["error"] = _fingerprint_error(exc)
                failed = True
            self._write(payload)
            if isinstance(entry.get("error"), Mapping) and entry["error"].get(
                "code"
            ) == "user_cancelled":
                break
        if failed:
            payload["status"] = "incomplete"
            payload["finished_at"] = _now_iso()
            payload["error"] = _top_error("incomplete")
        else:
            payload["baseline_captured_at"] = captured_at
            payload["status"] = "pending"
            payload["phase"] = "verification"
            payload["started_at"] = None
            payload["finished_at"] = None
            payload["error"] = None
        return self._write(payload)

    @_locked_operation
    def verify_manifest(
        self,
        *,
        chunk_size=DEFAULT_CHUNK_SIZE,
        progress_callback=None,
        cancel_check=None,
    ) -> Dict[str, object]:
        payload = self.load()
        if payload["status"] == "verified":
            raise IntegrityManifestError(
                _error(
                    "manifest_recheck_required",
                    "A verified manifest is immutable; create a new recheck record.",
                    stage="integrity_manifest",
                    recoverable=True,
                )
            )
        if payload["status"] != "pending":
            raise IntegrityManifestError(
                _error(
                    "manifest_terminal",
                    "This integrity record is terminal; use recovery or create a superseding record.",
                    stage="integrity_manifest",
                    recoverable=True,
                )
            )
        if _manifest_phase(payload) != "verification":
            raise IntegrityManifestError(
                _error(
                    "baseline_capture_required",
                    "Expected fingerprints must be captured before verification.",
                    stage="integrity_manifest",
                    recoverable=True,
                )
            )
        payload["phase"] = "verification"
        if payload.get("started_at") is None:
            payload["started_at"] = _now_iso()
        payload["error"] = None
        self._write(payload)

        cancelled = False
        for entry in payload["files"]:
            if entry.get("status") == "verified":
                continue
            if entry.get("status") != "pending":
                continue
            expected = _expected_values(entry)
            if not _has_complete_expected(expected):
                _preserve_expected(entry)
                _clear_observed(entry)
                entry["status"] = "incomplete"
                entry["verified_at"] = None
                entry["error"] = _error(
                    "expected_fingerprint_missing",
                    "The expected fingerprint must be registered before verification.",
                    stage="integrity_verify",
                    recoverable=True,
                )
                self._write(payload)
                continue
            try:
                resolved = self._resolve_entry_path(entry)
                algorithm = entry.get("hash_algorithm")
                if algorithm is None:
                    algorithm = entry.get("expected_hash_algorithm")

                callback = None
                if progress_callback is not None:
                    file_id = entry["file_id"]

                    def callback(done, total, _file_id=file_id):
                        progress_callback(_file_id, done, total)

                observed = compute_fingerprint(
                    resolved,
                    algorithm,
                    chunk_size=chunk_size,
                    progress_callback=callback,
                    cancel_check=cancel_check,
                )
                observed = self._observed_for_entry(entry, observed)
                if _entry_matches_expected(expected, observed):
                    _apply_observed(entry, observed)
                    for key in list(entry):
                        if key.startswith("expected_"):
                            entry.pop(key, None)
                    entry["status"] = "verified"
                    entry["verified_at"] = _now_iso()
                    entry["error"] = None
                else:
                    _preserve_expected(entry)
                    _apply_observed(entry, observed)
                    entry["status"] = "mismatch"
                    entry["verified_at"] = _now_iso()
                    entry["error"] = _error(
                        "source_digest_mismatch",
                        "The source no longer matches its recorded integrity fingerprint.",
                    )
            except FileNotFoundError as exc:
                _preserve_expected(entry)
                _clear_observed(entry)
                entry["status"] = "missing"
                entry["verified_at"] = None
                entry["error"] = _fingerprint_error(exc)
            except BaseException as exc:
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    raise
                _preserve_expected(entry)
                _clear_observed(entry)
                entry["status"] = "incomplete"
                entry["verified_at"] = None
                entry["error"] = _fingerprint_error(exc)
                if isinstance(exc, FingerprintCancelled):
                    cancelled = True
            self._write(payload)
            if cancelled:
                break

        payload["status"] = _top_status(payload["files"])
        payload["finished_at"] = _now_iso()
        payload["error"] = _top_error(payload["status"])
        return self._write(payload)

    @_locked_operation
    def recheck_verified(
        self,
        *,
        output_manifest_path=None,
        chunk_size=DEFAULT_CHUNK_SIZE,
        progress_callback=None,
        cancel_check=None,
    ) -> Dict[str, object]:
        source = self.load()
        if source["status"] != "verified":
            raise IntegrityManifestError(
                _error(
                    "manifest_not_recheckable",
                    "Only a verified integrity manifest can create a recheck record.",
                    stage="integrity_manifest",
                    recoverable=False,
                )
            )
        now = _now_iso()
        manifest_id = _new_id("integrity")
        payload = copy.deepcopy(source)
        payload.update(
            {
                "manifest_id": manifest_id,
                "status": "pending",
                "phase": "verification",
                "created_at": now,
                "started_at": None,
                "finished_at": None,
                "attempt": max(1, int(source.get("attempt", 1))) + 1,
                "retry_of": None,
                "recheck_of": source["manifest_id"],
                "error": None,
            }
        )
        for entry in payload["files"]:
            for key in list(entry):
                if key.startswith("expected_"):
                    entry.pop(key, None)
            entry["status"] = "pending"
            entry["verified_at"] = None
            entry["error"] = None
        destination = self._new_record_path(manifest_id, output_manifest_path)
        destination_service = IntegrityManifestService(
            destination,
            self.path_bases,
            external_locations=self.external_locations,
        )
        with destination_service._activity_guard():
            write_manifest(destination, payload)
        result = destination_service.verify_manifest(
            chunk_size=chunk_size,
            progress_callback=progress_callback,
            cancel_check=cancel_check,
        )
        self.last_written_path = destination
        return result

    @_locked_operation
    def resume_incomplete(self, **verify_kwargs) -> Dict[str, object]:
        payload = self.load()
        if payload["status"] != "incomplete":
            raise IntegrityManifestError(
                _error(
                    "manifest_not_resumable",
                    "Only an incomplete integrity record can be resumed.",
                    stage="integrity_manifest",
                    recoverable=False,
                )
            )
        phase = _manifest_phase(payload)
        payload["status"] = "pending"
        payload["phase"] = phase
        payload["started_at"] = None
        payload["finished_at"] = None
        payload["attempt"] = max(1, int(payload.get("attempt", 1))) + 1
        payload["error"] = None
        for entry in payload["files"]:
            _preserve_expected(entry)
            expected = _expected_values(entry)
            for key in ("entry_kind", "size_bytes", "hash_algorithm", "digest"):
                if expected.get(key) is not None:
                    entry[key] = expected[key]
            entry["status"] = "pending"
            entry["verified_at"] = None
            entry["error"] = None
        self._write(payload)
        if phase == "baseline_capture":
            return self.capture_expected_fingerprints(**verify_kwargs)
        return self.verify_manifest(**verify_kwargs)

    @_locked_operation
    def recover_pending_as_incomplete(self) -> Dict[str, object]:
        payload = self.load()
        if payload["status"] != "pending" or payload.get("started_at") is None:
            return payload
        for entry in payload["files"]:
            if entry.get("status") == "pending":
                entry["status"] = "incomplete"
                entry["error"] = _error(
                    "process_interrupted",
                    "The application stopped before this integrity check finished.",
                    stage="recovery_check",
                )
        payload["status"] = "incomplete"
        payload["finished_at"] = _now_iso()
        payload["error"] = _error(
            "process_interrupted",
            "The application stopped before the integrity manifest finished.",
            stage="recovery_check",
        )
        return self._write(payload)

    def _new_record_path(self, manifest_id: str, output_manifest_path=None) -> str:
        if output_manifest_path is not None:
            result = os.path.abspath(os.fspath(output_manifest_path))
        else:
            current = Path(self.manifest_path)
            result = str(
                current.with_name(f"{current.stem}.{manifest_id}{current.suffix or '.json'}")
            )
        if os.path.normcase(result) == os.path.normcase(self.manifest_path):
            _raise_manifest_error(
                "terminal_manifest_immutable",
                "A terminal integrity manifest cannot be overwritten.",
            )
        if os.path.exists(result):
            _raise_manifest_error(
                "manifest_already_exists",
                "An integrity manifest already exists at the requested record location.",
            )
        return result

    @_locked_operation
    def relocate_same_digest(
        self,
        file_id,
        new_path_base=None,
        new_relative_path=None,
        *,
        new_external_location_ref=None,
        output_manifest_path=None,
        chunk_size=DEFAULT_CHUNK_SIZE,
        progress_callback=None,
        cancel_check=None,
    ) -> Dict[str, object]:
        source = self.load()
        file_id = _validate_id(file_id, "file_id")
        matches = [entry for entry in source["files"] if entry["file_id"] == file_id]
        if not matches:
            _raise_manifest_error("file_id_missing", "The requested file record does not exist.")
        old_entry = matches[0]
        external = old_entry.get("entry_kind") == "external_reference"
        if external:
            if new_path_base is not None or new_relative_path is not None:
                _raise_manifest_error(
                    "external_relocation_path_not_allowed",
                    "An external relocation must use an opaque location reference.",
                )
            new_external_location_ref = _validate_id(
                new_external_location_ref, "external_location_ref"
            )
            if old_entry.get("external_location_ref") == new_external_location_ref:
                _raise_manifest_error(
                    "relocation_same_path", "The relocation target is unchanged."
                )
            candidate_entry = dict(old_entry)
            candidate_entry["external_location_ref"] = new_external_location_ref
            resolved = self._resolve_entry_path(candidate_entry)
        else:
            if new_external_location_ref is not None:
                _raise_manifest_error(
                    "managed_relocation_external_ref_not_allowed",
                    "A managed relocation cannot use an external location reference.",
                )
            new_path_base = str(new_path_base or "")
            if new_path_base not in PATH_BASES:
                _raise_manifest_error("unknown_path_base", "The managed path base is unknown.")
            new_relative_path = validate_relative_path(new_relative_path)
            if (
                old_entry["path_base"] == new_path_base
                and old_entry["relative_path"] == new_relative_path
            ):
                _raise_manifest_error(
                    "relocation_same_path", "The relocation target is unchanged."
                )
            resolved = _resolve_managed_path(
                new_path_base, new_relative_path, self.path_bases
            )
        expected = _expected_values(old_entry)
        if expected.get("digest") is None or expected.get("hash_algorithm") is None:
            _raise_manifest_error(
                "relocation_fingerprint_missing",
                "The original file has no complete fingerprint for relocation.",
                recoverable=True,
            )
        try:
            observed = compute_fingerprint(
                resolved,
                expected["hash_algorithm"],
                chunk_size=chunk_size,
                progress_callback=progress_callback,
                cancel_check=cancel_check,
            )
            observed = self._observed_for_entry(old_entry, observed)
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            raise IntegrityManifestError(_fingerprint_error(exc)) from exc
        if not _entry_matches_expected(expected, observed):
            raise IntegrityManifestError(
                _error(
                    "relocation_digest_mismatch",
                    "The selected relocation target does not contain the recorded content.",
                )
            )

        now = _now_iso()
        manifest_id = _new_id("integrity")
        payload = copy.deepcopy(source)
        payload.update(
            {
                "manifest_id": manifest_id,
                "status": "pending",
                "phase": "verification",
                "created_at": now,
                "started_at": None,
                "finished_at": None,
                "attempt": max(1, int(source.get("attempt", 1))) + 1,
                "retry_of": None,
                "recheck_of": source["manifest_id"],
                "supersedes": source["manifest_id"],
                "error": None,
            }
        )
        entry = next(item for item in payload["files"] if item["file_id"] == file_id)
        if external:
            old_location = {
                "external_location_ref": entry["external_location_ref"]
            }
            new_location = {
                "external_location_ref": new_external_location_ref
            }
            entry["external_location_ref"] = new_external_location_ref
        else:
            old_location = {
                "path_base": entry["path_base"],
                "relative_path": entry["relative_path"],
            }
            new_location = {
                "path_base": new_path_base,
                "relative_path": new_relative_path,
            }
            entry["path_base"] = new_path_base
            entry["relative_path"] = new_relative_path
        _apply_observed(entry, observed)
        payload.setdefault("relocations", []).append(
            {
                "file_id": file_id,
                "from": old_location,
                "to": new_location,
                "verified_at": now,
                "hash_algorithm": observed["hash_algorithm"],
                "digest": observed["digest"],
            }
        )
        for pending_entry in payload["files"]:
            expected_pending = _expected_values(pending_entry)
            if not _has_complete_expected(expected_pending):
                raise IntegrityManifestError(
                    _error(
                        "relocation_fingerprint_missing",
                        "Every file requires a complete expected fingerprint before relocation.",
                        stage="integrity_verify",
                        recoverable=True,
                    )
                )
            for key in ("entry_kind", "size_bytes", "hash_algorithm", "digest"):
                pending_entry[key] = expected_pending[key]
            if pending_entry.get("expected_mtime_ns") is not None:
                pending_entry["mtime_ns"] = pending_entry["expected_mtime_ns"]
            for key in list(pending_entry):
                if key.startswith("expected_"):
                    pending_entry.pop(key, None)
            pending_entry["status"] = "pending"
            pending_entry["verified_at"] = None
            pending_entry["error"] = None
        payload["status"] = "pending"
        payload["finished_at"] = None
        payload["error"] = None
        destination = self._new_record_path(manifest_id, output_manifest_path)
        destination_service = IntegrityManifestService(
            destination,
            self.path_bases,
            external_locations=self.external_locations,
        )
        with destination_service._activity_guard():
            write_manifest(destination, payload)
        written = destination_service.verify_manifest(
            chunk_size=chunk_size,
            progress_callback=(
                (lambda file_id, done, total: progress_callback(done, total))
                if progress_callback is not None
                else None
            ),
            cancel_check=cancel_check,
        )
        self.last_written_path = destination
        return written

    relocate_file = relocate_same_digest

    @_locked_operation
    def supersede_with_note(
        self,
        file_id,
        *,
        note,
        data_version_id=None,
        new_path_base=None,
        new_relative_path=None,
        output_manifest_path=None,
        algorithm=None,
        chunk_size=DEFAULT_CHUNK_SIZE,
        progress_callback=None,
        cancel_check=None,
    ) -> Dict[str, object]:
        source = self.load()
        file_id = _validate_id(file_id, "file_id")
        note = str(note or "").strip()
        if not note:
            _raise_manifest_error(
                "supersession_note_required",
                "Registering a new data version requires a note.",
            )
        if len(note) > 1000 or "\0" in note:
            _raise_manifest_error(
                "supersession_note_invalid", "The version note is invalid."
            )
        note = _ABSOLUTE_NOTE_PATH_RE.sub("[REDACTED_PATH]", note)
        note = _SECRET_NOTE_RE.sub("[REDACTED_SECRET]", note)
        matches = [entry for entry in source["files"] if entry["file_id"] == file_id]
        if not matches:
            _raise_manifest_error("file_id_missing", "The requested file record does not exist.")
        old_entry = matches[0]
        path_base = str(new_path_base or old_entry["path_base"])
        relative_path = validate_relative_path(
            new_relative_path or old_entry["relative_path"]
        )
        if path_base not in PATH_BASES:
            _raise_manifest_error("unknown_path_base", "The managed path base is unknown.")
        selected_algorithm = _normalise_algorithm(algorithm)
        if selected_algorithm is None:
            selected_algorithm = old_entry.get("hash_algorithm") or old_entry.get(
                "expected_hash_algorithm"
            )
        resolved = _resolve_managed_path(path_base, relative_path, self.path_bases)
        try:
            observed = compute_fingerprint(
                resolved,
                selected_algorithm,
                chunk_size=chunk_size,
                progress_callback=progress_callback,
                cancel_check=cancel_check,
            )
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            raise IntegrityManifestError(_fingerprint_error(exc)) from exc

        now = _now_iso()
        manifest_id = _new_id("integrity")
        new_data_version_id = data_version_id or _new_id("data")
        _validate_id(new_data_version_id, "data_version_id")
        payload = copy.deepcopy(source)
        payload.update(
            {
                "manifest_id": manifest_id,
                "status": "pending",
                "phase": "verification",
                "created_at": now,
                "started_at": None,
                "finished_at": None,
                "attempt": 1,
                "retry_of": None,
                "supersedes": source["manifest_id"],
                "note_ref": _new_id("note"),
                "supersession": {
                    "file_id": file_id,
                    "previous_data_version_id": old_entry["data_version_id"],
                    "new_data_version_id": new_data_version_id,
                    "reason_code": "intentional_file_update",
                    "note": note,
                    "recorded_at": now,
                },
                "error": None,
            }
        )
        for entry in payload["files"]:
            _preserve_expected(entry)
            expected = _expected_values(entry)
            for key in ("entry_kind", "size_bytes", "mtime_ns", "hash_algorithm", "digest"):
                if expected.get(key) is not None:
                    entry[key] = expected[key]
            entry["status"] = "pending"
            entry["verified_at"] = None
            entry["error"] = None
        updated = next(item for item in payload["files"] if item["file_id"] == file_id)
        updated["path_base"] = path_base
        updated["relative_path"] = relative_path
        updated["data_version_id"] = new_data_version_id
        _apply_observed(updated, observed)
        for key in list(updated):
            if key.startswith("expected_"):
                updated.pop(key, None)
        destination = self._new_record_path(manifest_id, output_manifest_path)
        written = write_manifest(destination, payload)
        self.last_written_path = destination
        return written

    supersede_file = supersede_with_note


def require_verified_training_inputs(
    manifest_or_path,
    *,
    required_file_ids: Optional[Iterable[str]] = None,
    required_roles: Optional[Iterable[str]] = None,
) -> Dict[str, object]:
    """Reject every non-verified training manifest without an override path."""

    if isinstance(manifest_or_path, Mapping):
        manifest = validate_manifest(manifest_or_path)
    else:
        manifest = load_manifest(manifest_or_path)
    issues = []
    entries = {entry["file_id"]: entry for entry in manifest["files"]}
    required_ids = {_validate_id(value, "file_id") for value in (required_file_ids or [])}
    required_role_set = {str(value) for value in (required_roles or [])}
    for missing_id in sorted(required_ids - set(entries)):
        issues.append(
            {"file_id": missing_id, "status": "missing", "reason_code": "record_missing"}
        )
    present_roles = {entry["role"] for entry in manifest["files"]}
    for missing_role in sorted(required_role_set - present_roles):
        issues.append(
            {"role": missing_role, "status": "missing", "reason_code": "role_missing"}
        )
    for entry in manifest["files"]:
        if entry["status"] != "verified":
            issues.append(
                {
                    "file_id": entry["file_id"],
                    "role": entry["role"],
                    "status": entry["status"],
                    "reason_code": "file_not_verified",
                }
            )
    if manifest["status"] != "verified" or issues:
        raise IntegrityGateError(
            _error(
                "training_inputs_not_verified",
                "Training cannot start until every required input passes integrity verification.",
                stage="training_preflight",
                recoverable=True,
            ),
            issues=issues,
        )
    return manifest


__all__ = [
    "SCHEMA_VERSION",
    "PATH_BASES",
    "PROTECTED_FULL_HASH_ROLES",
    "IntegrityManifestError",
    "IntegrityGateError",
    "IntegrityManifestService",
    "validate_relative_path",
    "validate_manifest",
    "build_file_entry",
    "build_external_file_entry",
    "load_manifest",
    "write_manifest",
    "require_verified_training_inputs",
]
