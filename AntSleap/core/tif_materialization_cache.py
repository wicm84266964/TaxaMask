"""Content-addressed, project-local cache for reproducible backend inputs."""

from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from filelock import FileLock

from .file_integrity import FULL_FILE_ALGORITHM, compute_fingerprint
from .safe_io import atomic_write_json
from .tif_storage import (
    TIF_MATERIALIZATION_GENERATOR_VERSION,
    materialization_cache_key,
    stable_payload_hash,
)


MATERIALIZATION_MANIFEST_SCHEMA = "taxamask_tif_materialization_manifest_v1"


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _contained_path(root, path):
    root_real = os.path.realpath(os.path.abspath(os.fspath(root)))
    path_abs = os.path.abspath(os.fspath(path))
    parent_real = os.path.realpath(os.path.dirname(path_abs) or ".")
    try:
        common = os.path.commonpath([root_real, parent_real])
    except ValueError as exc:
        raise ValueError(f"materialization_path_outside_root:{path_abs}") from exc
    if os.path.normcase(common) != os.path.normcase(root_real):
        raise ValueError(f"materialization_path_outside_root:{path_abs}")
    return path_abs


class TifMaterializationCache:
    def __init__(self, project_root, cache_root=None):
        self.project_root = os.path.abspath(os.fspath(project_root))
        root = cache_root or os.path.join(
            self.project_root, "cache", "tif_materializations"
        )
        self.cache_root = _contained_path(self.project_root, root)
        os.makedirs(self.cache_root, exist_ok=True)

    def _entry_paths(self, cache_key, suffix):
        digest = str(cache_key).split(":", 1)[-1]
        entry_dir = os.path.join(self.cache_root, digest[:2], digest)
        artifact = os.path.join(entry_dir, f"artifact{suffix}")
        manifest = os.path.join(entry_dir, "materialization.json")
        lock = f"{entry_dir}.lock"
        return entry_dir, artifact, manifest, lock

    def _read_valid_entry(self, cache_key, artifact_path, manifest_path):
        if not os.path.isfile(artifact_path) or not os.path.isfile(manifest_path):
            return None
        try:
            with open(manifest_path, "r", encoding="utf-8") as handle:
                manifest = json.load(handle)
            stat = os.stat(artifact_path, follow_symlinks=False)
        except (OSError, ValueError, TypeError):
            return None
        if (
            not isinstance(manifest, dict)
            or manifest.get("schema_version") != MATERIALIZATION_MANIFEST_SCHEMA
            or manifest.get("cache_key") != cache_key
            or int(manifest.get("size_bytes") or -1) != int(stat.st_size)
            or int(manifest.get("mtime_ns") or -1) != int(stat.st_mtime_ns)
            or not manifest.get("content_hash")
        ):
            return None
        fingerprint = compute_fingerprint(artifact_path, FULL_FILE_ALGORITHM)
        observed_hash = f"{fingerprint['hash_algorithm']}:{fingerprint['digest']}"
        if observed_hash != str(manifest.get("content_hash") or ""):
            return None
        manifest["verified_at"] = _now_iso()
        return manifest

    def materialize(
        self,
        *,
        destination,
        suffix,
        source_assets,
        format_id,
        writer,
        spacing_zyx=None,
        axis_order="zyx",
        interpolation="none",
        compression=None,
        effective_config=None,
        generator="tif_export",
        generator_version=TIF_MATERIALIZATION_GENERATOR_VERSION,
    ):
        cache_key, key_payload = materialization_cache_key(
            source_assets=source_assets,
            format_id=format_id,
            axis_order=axis_order,
            spacing_zyx=spacing_zyx,
            interpolation=interpolation,
            compression=compression,
            exporter_version=generator_version,
            effective_config=effective_config,
        )
        entry_dir, artifact_path, manifest_path, lock_path = self._entry_paths(
            cache_key, str(suffix or "")
        )
        os.makedirs(os.path.dirname(entry_dir), exist_ok=True)
        cache_hit = False
        with FileLock(lock_path, timeout=300):
            manifest = self._read_valid_entry(
                cache_key, artifact_path, manifest_path
            )
            if manifest is None and os.path.exists(entry_dir):
                raise RuntimeError(f"materialization_cache_entry_invalid:{cache_key}")
            if manifest is None:
                pending_dir = f"{entry_dir}.pending_{uuid.uuid4().hex}"
                pending_artifact = os.path.join(
                    pending_dir, os.path.basename(artifact_path)
                )
                os.makedirs(pending_dir, exist_ok=False)
                try:
                    writer(pending_artifact)
                    fingerprint = compute_fingerprint(
                        pending_artifact, FULL_FILE_ALGORITHM
                    )
                    stat = os.stat(pending_artifact, follow_symlinks=False)
                    manifest = {
                        "schema_version": MATERIALIZATION_MANIFEST_SCHEMA,
                        "cache_key": cache_key,
                        "cache_key_payload": key_payload,
                        "format": str(format_id or ""),
                        "artifact_name": os.path.basename(pending_artifact),
                        "content_hash": (
                            f"{fingerprint['hash_algorithm']}:{fingerprint['digest']}"
                        ),
                        "size_bytes": int(fingerprint["size_bytes"]),
                        "mtime_ns": int(stat.st_mtime_ns),
                        "source_assets": [dict(item) for item in source_assets or []],
                        "generator": str(generator or ""),
                        "generator_version": str(generator_version or ""),
                        "effective_config_hash": stable_payload_hash(
                            dict(effective_config or {})
                        ),
                        "created_at": _now_iso(),
                        "verified_at": _now_iso(),
                        "lifecycle": "reproducible_cache",
                        "status": "verified",
                    }
                    atomic_write_json(
                        os.path.join(pending_dir, "materialization.json"),
                        manifest,
                        indent=2,
                        ensure_ascii=False,
                    )
                    os.replace(pending_dir, entry_dir)
                except Exception:
                    if os.path.exists(pending_dir):
                        shutil.rmtree(pending_dir, ignore_errors=True)
                    raise
            else:
                cache_hit = True

        destination_abs = os.path.abspath(os.fspath(destination))
        os.makedirs(os.path.dirname(destination_abs) or ".", exist_ok=True)
        if os.path.lexists(destination_abs):
            raise FileExistsError(destination_abs)
        link_method = "copy"
        try:
            os.link(artifact_path, destination_abs)
            if not os.path.samefile(artifact_path, destination_abs):
                raise OSError("hardlink_identity_verification_failed")
            link_method = "hardlink"
        except OSError:
            if os.path.lexists(destination_abs):
                os.remove(destination_abs)
            shutil.copy2(artifact_path, destination_abs)

        cache_entry_rel = os.path.relpath(entry_dir, self.project_root).replace(
            "\\", "/"
        )
        try:
            destination_common = os.path.commonpath(
                [self.project_root, destination_abs]
            )
        except ValueError:
            destination_common = ""
        run_path = (
            os.path.relpath(destination_abs, self.project_root).replace("\\", "/")
            if os.path.normcase(destination_common)
            == os.path.normcase(self.project_root)
            else ""
        )
        return {
            "cache_key": cache_key,
            "format": str(format_id or ""),
            "cache_path": cache_entry_rel,
            "run_path": run_path,
            "lifecycle": "reproducible_cache",
            "status": "verified",
            "content_hash": str(manifest["content_hash"]),
            "size_bytes": int(manifest["size_bytes"]),
            "link_method": link_method,
            "generator": str(generator or ""),
            "generator_version": str(generator_version or ""),
            "effective_config_hash": str(
                manifest.get("effective_config_hash") or ""
            ),
            "verified_at": str(manifest.get("verified_at") or ""),
            "cache_hit": cache_hit,
            "unique_bytes_added_to_run": (
                0 if link_method == "hardlink" else int(manifest["size_bytes"])
            ),
            "unique_bytes_added_to_cache": (
                0 if cache_hit else int(manifest["size_bytes"])
            ),
            "source_assets": [dict(item) for item in source_assets or []],
            "read_only_contract": "backend_must_not_modify_input_in_place",
        }
