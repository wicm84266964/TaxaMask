# pyright: reportMissingImports=false, reportGeneralTypeIssues=false

import hashlib
import io
import json
import ntpath
import os
import stat
import torch
import cv2

from .projection import CoordinateMapper
from .cascade_routes import (
    LEGACY_EXPERT_FILENAME,
    ROUTE_BACKEND_EXTERNAL_BLINK,
    ROUTE_BACKEND_HEATMAP_BLINK,
    ROUTE_BACKEND_VIT_B_BLINK,
    build_expert_id,
    format_expert_label,
    parse_expert_id,
    route_manifest_has_routes,
    sanitize_legacy_route_manifest,
    sanitize_project_route_manifest,
)
from .expert_notes import load_expert_notes
from .file_integrity import FULL_FILE_ALGORITHM, compute_fingerprint
from .blink_expert_manifest import (
    BLINK_EXPERT_MANIFEST_SCHEMA_VERSION,
    BLINK_EXPERT_MANIFEST_SUPPORTED_SCHEMA_VERSIONS,
    decode_blink_expert_manifest_payload,
    default_manifest_path_for_weights,
    is_safe_blink_expert_part_name,
    validate_blink_expert_contract,
    validate_blink_route_identity,
    verify_blink_manifest_payload,
)
from .blink_expert_backends import BlinkBackendError, create_default_blink_backend_registry
from .external_blink_backend import sanitize_external_blink_config
from .safe_io import (
    UnsafeFilesystemPath,
    read_bytes_bounded_in_root,
    read_json_bounded_in_root,
)
from .training_weight_publisher import (
    PUBLICATION_FILENAME,
    PUBLICATION_SCHEMA_VERSION,
    PUBLICATION_STATUS_ACTIVE,
    TRAINING_BUNDLE_DIRECTORY,
)
try:
    from AntSleap.models.expert_networks import MicroExpertLocator
except ImportError:
    from models.expert_networks import MicroExpertLocator


_MANAGED_JSON_MAX_BYTES = 2 * 1024 * 1024


class CascadingManager:
    """
    级联推理骨架 (Cascade Inference Scaffold)
    
    用于前期验证阶段：展示大模型与微观专家 (Transformer) 的接力工作流。
    未来将对接真实的 anatomy_tree.json 进行动态路由。
    """
    def __init__(self, main_engine):
        self.engine = main_engine
        self.device = main_engine.device
        self.project_manager = None
        
        # 缓存已加载的专家模型，避免重复加载
        self.loaded_experts = {}
        self.blink_backend_registry = create_default_blink_backend_registry()
        self.expert_dir = os.path.join(main_engine.weights_dir, "experts")
        self.route_manifest_path = os.path.join(self.expert_dir, "cascade_routes.json")
        self.legacy_route_manifest = {
            "version": "",
            "approved": False,
            "routes": [],
        }
        self.load_routes()

    def _blink_backends(self):
        if not hasattr(self, "blink_backend_registry") or self.blink_backend_registry is None:
            self.blink_backend_registry = create_default_blink_backend_registry()
        return self.blink_backend_registry

    def load_routes(self, route_manifest_path=None):
        """加载专家路由合同。未配置或未批准时返回默认关闭态。"""
        path = route_manifest_path or self.route_manifest_path
        self.route_manifest_path = path

        if not os.path.exists(path):
            self.legacy_route_manifest = {"version": "", "approved": False, "routes": []}
            return False

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            self.legacy_route_manifest = {"version": "", "approved": False, "routes": []}
            return False

        self.legacy_route_manifest = sanitize_legacy_route_manifest(raw)
        return self.routes_ready()

    def routes_ready(self, route_manifest=None):
        manifest = route_manifest if isinstance(route_manifest, dict) else self.legacy_route_manifest
        routes = manifest.get("routes", []) if isinstance(manifest, dict) else []
        if not isinstance(routes, list):
            return False
        return any(bool(route.get("enabled", False)) for route in routes if isinstance(route, dict))

    def get_runtime_route_manifest(self, project_route_manifest=None):
        project_manifest = sanitize_project_route_manifest(project_route_manifest or {})
        if route_manifest_has_routes(project_manifest):
            return project_manifest
        return {
            "version": self.legacy_route_manifest.get("version", ""),
            "routes": [dict(route) for route in self.legacy_route_manifest.get("routes", [])],
        }

    def _find_route(self, parent_part, child_part_name, route_manifest=None):
        manifest = self.get_runtime_route_manifest(route_manifest)
        if not self.routes_ready(manifest):
            return None

        parent_part = str(parent_part or "").strip()
        child_part_name = str(child_part_name or "").strip()
        if not parent_part or not child_part_name:
            return None

        route_list = manifest.get("routes", [])
        if not isinstance(route_list, list):
            return None

        for route in route_list:
            if not isinstance(route, dict):
                continue
            if not bool(route.get("enabled", False)):
                continue
            route_parent = route.get("parent", "")
            route_child = route.get("child", "")
            if route_parent == parent_part and route_child == child_part_name:
                return route
        return None

    def resolve_route_for_child(self, child_part_name, available_parents, route_manifest=None):
        manifest = self.get_runtime_route_manifest(route_manifest)
        if not self.routes_ready(manifest):
            return None

        child_part_name = str(child_part_name or "").strip()
        if not child_part_name:
            return None

        available = [str(part).strip() for part in available_parents or [] if str(part).strip()]
        if not available:
            return None

        route_list = manifest.get("routes", [])
        for route in route_list:
            if not isinstance(route, dict):
                continue
            if not bool(route.get("enabled", False)):
                continue
            route_child = str(route.get("child", "")).strip()
            if route_child != child_part_name:
                continue
            route_parent = str(route.get("parent", "")).strip()
            if route_parent in available:
                return route
        return None

    def can_override(self, parent_part, child_part_name, route_manifest=None):
        return self._find_route(parent_part, child_part_name, route_manifest=route_manifest) is not None

    def get_route_min_conf(self, parent_part, child_part_name, route_manifest=None):
        route = self._find_route(parent_part, child_part_name, route_manifest=route_manifest)
        if not route:
            return None
        min_conf = route.get("min_conf", None)
        if isinstance(min_conf, (int, float)):
            return float(min_conf)
        return None

    def describe_route(self, route):
        if not isinstance(route, dict):
            return "unknown-route"
        parent = str(route.get("parent") or "?").strip() or "?"
        child = str(route.get("child") or "?").strip() or "?"
        expert_label = format_expert_label(route)
        backend = str(route.get("expert_backend") or ROUTE_BACKEND_VIT_B_BLINK).strip() or ROUTE_BACKEND_VIT_B_BLINK
        return f"{parent}->{child} [{backend}:{expert_label}]"

    def route_has_explicit_expert(self, route):
        if not isinstance(route, dict):
            return False
        appointed = route.get("appointed_expert")
        appointed_manifest = appointed.get("expert_manifest") if isinstance(appointed, dict) else None
        return bool(
            route.get("expert_id")
            or route.get("expert_part")
            or route.get("expert_filename")
            or route.get("expert_manifest")
            or appointed_manifest
        )

    @staticmethod
    def _is_link_or_reparse(stat_result):
        attributes = int(getattr(stat_result, "st_file_attributes", 0) or 0)
        reparse_flag = int(
            getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400) or 0x400
        )
        return stat.S_ISLNK(stat_result.st_mode) or bool(attributes & reparse_flag)

    def _managed_path_from_reference(self, reference, *, base_dir=None):
        try:
            text = os.fspath(reference).strip()
        except (AttributeError, TypeError):
            return None
        if not text or "\x00" in text:
            return None

        portable = text.replace("\\", "/")
        if ".." in portable.split("/"):
            return None

        root = os.path.abspath(self.expert_dir)
        native_absolute = os.path.isabs(text)
        windows_absolute = ntpath.isabs(text)
        if windows_absolute and not native_absolute:
            return None
        if native_absolute:
            target = os.path.abspath(text)
        else:
            drive, _tail = ntpath.splitdrive(text)
            if drive:
                return None
            anchor = os.path.abspath(base_dir or root)
            target = os.path.abspath(
                os.path.join(anchor, *[part for part in portable.split("/") if part not in {"", "."}])
            )

        try:
            inside = os.path.normcase(os.path.commonpath([root, target])) == os.path.normcase(root)
        except ValueError:
            inside = False
        if not inside or os.path.normcase(target) == os.path.normcase(root):
            return None
        return target

    def _safe_managed_entry(self, reference, *, expect_directory=False, base_dir=None):
        target = self._managed_path_from_reference(reference, base_dir=base_dir)
        if not target:
            return None
        root = os.path.abspath(self.expert_dir)
        try:
            root_stat = os.lstat(root)
            if self._is_link_or_reparse(root_stat) or not stat.S_ISDIR(root_stat.st_mode):
                return None
            relative = os.path.relpath(target, root)
            parts = [part for part in relative.split(os.sep) if part not in {"", "."}]
            if not parts:
                return None
            current = root
            for index, part in enumerate(parts):
                current = os.path.join(current, part)
                if not os.path.lexists(current):
                    return None
                current_stat = os.lstat(current)
                if self._is_link_or_reparse(current_stat):
                    return None
                is_final = index == len(parts) - 1
                if not is_final and not stat.S_ISDIR(current_stat.st_mode):
                    return None
                if is_final:
                    expected_mode = stat.S_ISDIR if expect_directory else stat.S_ISREG
                    if not expected_mode(current_stat.st_mode):
                        return None
        except (OSError, ValueError):
            return None
        return target

    def _safe_managed_file(self, reference, *, base_dir=None):
        return self._safe_managed_entry(reference, base_dir=base_dir)

    def _safe_managed_directory(self, reference, *, base_dir=None):
        return self._safe_managed_entry(
            reference,
            expect_directory=True,
            base_dir=base_dir,
        )

    def _read_managed_json(self, reference):
        path = self._safe_managed_file(reference)
        if not path:
            return None
        try:
            payload = read_json_bounded_in_root(
                path,
                trusted_root=self.expert_dir,
                max_bytes=_MANAGED_JSON_MAX_BYTES,
            )
        except (OSError, UnicodeError, ValueError, UnsafeFilesystemPath, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _route_manifest_reference(route):
        manifest = route.get("expert_manifest") if isinstance(route, dict) else None
        if manifest:
            return manifest
        appointed = route.get("appointed_expert") if isinstance(route, dict) else None
        if isinstance(appointed, dict):
            return appointed.get("expert_manifest")
        return None

    def _training_bundle_run_id(self, path):
        managed_path = self._managed_path_from_reference(path)
        if not managed_path:
            return None
        try:
            relative = os.path.relpath(managed_path, os.path.abspath(self.expert_dir))
        except ValueError:
            return None
        parts = [part for part in relative.replace("\\", "/").split("/") if part]
        if len(parts) < 3 or parts[0].casefold() != TRAINING_BUNDLE_DIRECTORY.casefold():
            return None
        run_id = parts[1]
        if run_id in {".", ".."} or "/" in run_id or "\\" in run_id:
            return None
        return run_id

    def _load_active_training_bundle(
        self,
        run_id,
        *,
        checkpoint_path=None,
        manifest_path=None,
        stable_manifest_payload=None,
    ):
        clean_run_id = str(run_id or "").strip()
        if not clean_run_id or clean_run_id in {".", ".."} or "/" in clean_run_id or "\\" in clean_run_id:
            return None
        bundle_reference = f"{TRAINING_BUNDLE_DIRECTORY}/{clean_run_id}"
        if not self._safe_managed_directory(bundle_reference):
            return None
        publication_reference = f"{bundle_reference}/{PUBLICATION_FILENAME}"
        payload = self._read_managed_json(publication_reference)
        if not isinstance(payload, dict):
            return None
        if (
            payload.get("schema_version") != PUBLICATION_SCHEMA_VERSION
            or payload.get("status") != PUBLICATION_STATUS_ACTIVE
            or payload.get("run_id") != clean_run_id
            or not isinstance(payload.get("activated_at"), str)
            or not payload.get("activated_at")
        ):
            return None

        artifacts = payload.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            return None
        prefix = f"{TRAINING_BUNDLE_DIRECTORY}/{clean_run_id}/"
        checkpoint_key = (
            os.path.normcase(os.path.abspath(os.fspath(checkpoint_path)))
            if checkpoint_path
            else None
        )
        manifest_key = (
            os.path.normcase(os.path.abspath(os.fspath(manifest_path)))
            if manifest_path
            else None
        )
        resolved_artifacts = []
        seen_paths = set()
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                return None
            role = str(artifact.get("role") or "")
            relative_path = artifact.get("relative_path")
            if (
                role not in {"output_weights", "model_manifest"}
                or artifact.get("path_base") != "managed_model_root"
                or artifact.get("entry_kind") != "file"
                or not isinstance(relative_path, str)
                or "\\" in relative_path
                or not relative_path.startswith(prefix)
            ):
                return None
            target = self._safe_managed_file(relative_path)
            if not target or os.path.basename(target).casefold() == PUBLICATION_FILENAME.casefold():
                return None
            path_key = os.path.normcase(target)
            if path_key in seen_paths:
                return None
            seen_paths.add(path_key)
            size_bytes = artifact.get("size_bytes")
            if (
                not isinstance(size_bytes, int)
                or isinstance(size_bytes, bool)
                or size_bytes < 0
                or os.path.getsize(target) != size_bytes
            ):
                return None
            digest = str(artifact.get("digest") or "")
            if (
                artifact.get("hash_algorithm") != FULL_FILE_ALGORITHM
                or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest)
            ):
                return None
            is_checkpoint_target = (
                checkpoint_key is not None and path_key == checkpoint_key
            )
            is_manifest_target = (
                manifest_key is not None and path_key == manifest_key
            )
            if is_checkpoint_target and is_manifest_target:
                return None
            artifact_payload = None
            try:
                if is_checkpoint_target or is_manifest_target:
                    expected_role = (
                        "output_weights"
                        if is_checkpoint_target
                        else "model_manifest"
                    )
                    if role != expected_role:
                        return None
                    if is_manifest_target and stable_manifest_payload is not None:
                        if not isinstance(stable_manifest_payload, bytes):
                            return None
                        artifact_payload = stable_manifest_payload
                    else:
                        artifact_payload = read_bytes_bounded_in_root(
                            target,
                            trusted_root=self.expert_dir,
                            max_bytes=size_bytes,
                        )
                    observed = {
                        "size_bytes": len(artifact_payload),
                        "hash_algorithm": FULL_FILE_ALGORITHM,
                        "digest": hashlib.sha256(artifact_payload).hexdigest(),
                    }
                else:
                    observed = compute_fingerprint(
                        target,
                        algorithm=FULL_FILE_ALGORITHM,
                    )
            except Exception:
                return None
            if any(
                observed.get(field) != artifact.get(field)
                for field in ("size_bytes", "hash_algorithm", "digest")
            ):
                return None
            resolved = dict(artifact)
            resolved["path"] = target
            if artifact_payload is not None:
                if is_checkpoint_target:
                    resolved["checkpoint_bytes"] = artifact_payload
                else:
                    resolved["manifest_payload"] = artifact_payload
                resolved["payload_identity"] = {
                    "source": "active_training_publication",
                    "reference": relative_path,
                    "publication_run_id": clean_run_id,
                    "size_bytes": len(artifact_payload),
                    "hash_algorithm": FULL_FILE_ALGORITHM,
                    "digest": hashlib.sha256(artifact_payload).hexdigest(),
                }
            resolved_artifacts.append(resolved)
        return {
            "run_id": clean_run_id,
            "publication_path": self._safe_managed_file(publication_reference),
            "artifacts": resolved_artifacts,
        }

    @staticmethod
    def _decode_blink_manifest_payload(manifest_payload):
        try:
            manifest = decode_blink_expert_manifest_payload(manifest_payload)
        except ValueError:
            return None
        if (
            not isinstance(manifest, dict)
            or manifest.get("schema_version")
            not in BLINK_EXPERT_MANIFEST_SUPPORTED_SCHEMA_VERSIONS
        ):
            return None
        return manifest

    def _read_stable_manifest_record(self, manifest_reference, *, source):
        manifest_path = self._safe_managed_file(manifest_reference)
        if not manifest_path or not manifest_path.lower().endswith(".json"):
            return None
        try:
            expected_size = os.path.getsize(manifest_path)
            if expected_size <= 0 or expected_size > _MANAGED_JSON_MAX_BYTES:
                return None
            manifest_payload = read_bytes_bounded_in_root(
                manifest_path,
                trusted_root=self.expert_dir,
                max_bytes=expected_size,
            )
        except (OSError, ValueError, UnsafeFilesystemPath):
            return None
        if len(manifest_payload) != expected_size:
            return None
        manifest = self._decode_blink_manifest_payload(manifest_payload)
        if not isinstance(manifest, dict):
            return None
        return {
            "path": manifest_path,
            "manifest": manifest,
            "manifest_payload": manifest_payload,
            "manifest_identity": {
                "source": str(source or "legacy_manifest_compatibility"),
                "reference": manifest_path.replace("\\", "/"),
                "size_bytes": len(manifest_payload),
                "hash_algorithm": FULL_FILE_ALGORITHM,
                "digest": hashlib.sha256(manifest_payload).hexdigest(),
            },
        }

    def _resolve_manifest_weights_record(
        self,
        manifest_reference,
        *,
        include_checkpoint_bytes=False,
    ):
        manifest_record = self._read_stable_manifest_record(
            manifest_reference,
            source="legacy_manifest_compatibility",
        )
        if not isinstance(manifest_record, dict):
            return None
        manifest_path = manifest_record["path"]
        manifest = manifest_record["manifest"]
        weights = manifest.get("weights")
        main_weights = weights.get("main") if isinstance(weights, dict) else None
        if not isinstance(main_weights, str):
            return None
        main_weights = main_weights.strip()
        if (
            not main_weights
            or "/" in main_weights
            or "\\" in main_weights
            or main_weights in {".", ".."}
            or not main_weights.lower().endswith(".pth")
        ):
            return None
        weights_path = self._safe_managed_file(
            main_weights,
            base_dir=os.path.dirname(manifest_path),
        )
        if not weights_path:
            return None

        manifest_run_id = self._training_bundle_run_id(manifest_path)
        weights_run_id = self._training_bundle_run_id(weights_path)
        if not manifest_run_id and not weights_run_id:
            return {
                "path": weights_path,
                "digest": "",
                "checkpoint_bytes": None,
                "source": "legacy_manifest_compatibility",
                "manifest": manifest,
                "manifest_payload": manifest_record["manifest_payload"],
                "manifest_identity": manifest_record["manifest_identity"],
            }
        if not manifest_run_id or manifest_run_id != weights_run_id:
            return None
        if manifest.get("schema_version") != BLINK_EXPERT_MANIFEST_SCHEMA_VERSION:
            return None

        bundle = self._load_active_training_bundle(
            manifest_run_id,
            checkpoint_path=weights_path if include_checkpoint_bytes else None,
            manifest_path=manifest_path,
            stable_manifest_payload=manifest_record["manifest_payload"],
        )
        if not bundle:
            return None
        manifest_key = os.path.normcase(os.path.abspath(manifest_path))
        weights_key = os.path.normcase(os.path.abspath(weights_path))
        artifacts_by_path = {
            os.path.normcase(os.path.abspath(item["path"])): item
            for item in bundle.get("artifacts", [])
        }
        manifest_artifact = artifacts_by_path.get(manifest_key)
        weights_artifact = artifacts_by_path.get(weights_key)
        if (
            not isinstance(manifest_artifact, dict)
            or manifest_artifact.get("role") != "model_manifest"
            or not isinstance(weights_artifact, dict)
            or weights_artifact.get("role") != "output_weights"
        ):
            return None
        manifest_payload = manifest_artifact.get("manifest_payload")
        manifest_identity = manifest_artifact.get("payload_identity")
        stable_manifest = self._decode_blink_manifest_payload(manifest_payload)
        if (
            not isinstance(stable_manifest, dict)
            or not isinstance(manifest_identity, dict)
            or stable_manifest.get("schema_version")
            != BLINK_EXPERT_MANIFEST_SCHEMA_VERSION
        ):
            return None
        stable_weights = stable_manifest.get("weights")
        stable_main = (
            stable_weights.get("main")
            if isinstance(stable_weights, dict)
            else None
        )
        if not isinstance(stable_main, str):
            return None
        stable_main = stable_main.strip()
        if (
            not stable_main
            or "/" in stable_main
            or "\\" in stable_main
            or stable_main in {".", ".."}
            or not stable_main.lower().endswith(".pth")
        ):
            return None
        stable_weights_path = self._safe_managed_file(
            stable_main,
            base_dir=os.path.dirname(manifest_path),
        )
        if (
            not stable_weights_path
            or os.path.normcase(os.path.abspath(stable_weights_path))
            != weights_key
        ):
            return None
        checkpoint_bytes = weights_artifact.get("checkpoint_bytes")
        if include_checkpoint_bytes and not isinstance(checkpoint_bytes, bytes):
            return None
        return {
            "path": weights_path,
            "digest": str(weights_artifact.get("digest") or ""),
            "checkpoint_bytes": checkpoint_bytes,
            "source": "active_training_publication",
            "publication_run_id": manifest_run_id,
            "manifest": stable_manifest,
            "manifest_payload": manifest_payload,
            "manifest_identity": dict(manifest_identity),
        }

    def _resolve_manifest_weights_path(self, manifest_reference):
        record = self._resolve_manifest_weights_record(manifest_reference)
        return record.get("path") if isinstance(record, dict) else None

    def _resolve_route_manifest_record(
        self,
        route,
        *,
        include_checkpoint_bytes=False,
    ):
        manifest_reference = self._route_manifest_reference(route)
        if not manifest_reference:
            return None, None
        record = self._resolve_manifest_weights_record(
            manifest_reference,
            include_checkpoint_bytes=include_checkpoint_bytes,
        )
        if not isinstance(record, dict):
            return None, "expert_model_missing"
        try:
            validate_blink_route_identity(
                record.get("manifest"),
                route_parent_part=(route or {}).get("parent"),
                route_child_part=(route or {}).get("child"),
            )
        except ValueError as exc:
            return None, str(exc)
        return record, None

    def _read_legacy_checkpoint_record(self, model_path, *, source):
        safe_path = self._safe_managed_file(model_path)
        if not safe_path:
            return None
        try:
            expected_size = os.path.getsize(safe_path)
            checkpoint_bytes = read_bytes_bounded_in_root(
                safe_path,
                trusted_root=self.expert_dir,
                max_bytes=expected_size,
            )
        except (OSError, ValueError, UnsafeFilesystemPath):
            return None
        if len(checkpoint_bytes) != expected_size:
            return None
        return {
            "path": safe_path,
            "digest": hashlib.sha256(checkpoint_bytes).hexdigest(),
            "checkpoint_bytes": checkpoint_bytes,
            "source": source,
        }

    def resolve_route_expert_checkpoint(self, route):
        """Return one stable checkpoint payload for an internal Blink backend.

        Active publications are authenticated against their publication record.
        Older non-publication experts remain loadable through an explicit
        compatibility boundary, but are still read once through the managed root.
        """

        if not isinstance(route, dict):
            return None
        manifest_reference = self._route_manifest_reference(route)
        if manifest_reference:
            record, _block_reason = self._resolve_route_manifest_record(
                route,
                include_checkpoint_bytes=True,
            )
            if not isinstance(record, dict):
                return None
            if record.get("source") == "active_training_publication":
                return record
            checkpoint_record = self._read_legacy_checkpoint_record(
                record.get("path"),
                source=str(record.get("source") or "legacy_manifest_compatibility"),
            )
            if not isinstance(checkpoint_record, dict):
                return None
            checkpoint_record["manifest_payload"] = record.get(
                "manifest_payload"
            )
            checkpoint_record["manifest_identity"] = dict(
                record.get("manifest_identity") or {}
            )
            return checkpoint_record

        model_path = self.resolve_route_expert_path(route)
        return self._read_legacy_checkpoint_record(
            model_path,
            source="legacy_route_compatibility",
        )

    def _runtime_route_record(self, route):
        runtime_route = dict(route or {})
        manifest_reference = self._route_manifest_reference(runtime_route)
        if not manifest_reference:
            return runtime_route
        manifest_path = self._safe_managed_file(manifest_reference)
        if not manifest_path:
            return runtime_route
        runtime_route["expert_manifest"] = manifest_path
        appointed = runtime_route.get("appointed_expert")
        if isinstance(appointed, dict):
            runtime_route["appointed_expert"] = dict(appointed)
            runtime_route["appointed_expert"]["expert_manifest"] = manifest_path
        return runtime_route

    def resolve_route_expert_path(self, route):
        if not isinstance(route, dict):
            return None

        manifest_reference = self._route_manifest_reference(route)
        if manifest_reference:
            record, _block_reason = self._resolve_route_manifest_record(route)
            return record.get("path") if isinstance(record, dict) else None

        expert_id = route.get("expert_id")
        expert_part, expert_filename = parse_expert_id(expert_id)
        if not expert_part:
            raw_part = route.get("expert_part") or route.get("expert_name")
            if isinstance(raw_part, str) and raw_part.strip():
                expert_part = raw_part.strip()
        if not expert_filename:
            raw_filename = route.get("expert_filename")
            if isinstance(raw_filename, str) and raw_filename.strip():
                expert_filename = os.path.basename(raw_filename.strip())

        is_legacy_route = str(route.get("registration_source") or "") == "legacy_global_manifest"
        if is_legacy_route:
            if not expert_part:
                expert_part = str(route.get("child") or "").strip()
            if not expert_filename:
                expert_filename = LEGACY_EXPERT_FILENAME

        if (
            not expert_part
            or not expert_filename
            or not is_safe_blink_expert_part_name(expert_part)
        ):
            return None
        legacy_path = os.path.join(self.expert_dir, expert_part, expert_filename)
        if os.path.lexists(legacy_path):
            return self._safe_managed_file(legacy_path)
        return legacy_path

    def get_route_block_reason(self, route):
        if not isinstance(route, dict):
            return "route_missing"
        is_legacy_route = str(route.get("registration_source") or "") == "legacy_global_manifest"
        backend = str(route.get("expert_backend") or ROUTE_BACKEND_VIT_B_BLINK).strip() or ROUTE_BACKEND_VIT_B_BLINK
        try:
            self._blink_backends().get(backend)
        except BlinkBackendError:
            return "expert_backend_unknown"
        route_child = str(route.get("child") or "").strip()
        if route_child and not is_safe_blink_expert_part_name(route_child):
            return "blink_route_child_part_unsafe_or_reserved"
        if backend == ROUTE_BACKEND_EXTERNAL_BLINK:
            config = self._external_blink_route_config(route)
            if not config.get("predict_command"):
                return "external_blink_predict_command_missing"
            return None
        if not is_legacy_route and not self.route_has_explicit_expert(route):
            return "expert_unappointed"
        manifest_reference = self._route_manifest_reference(route)
        if manifest_reference:
            manifest_record, manifest_block_reason = (
                self._resolve_route_manifest_record(route)
            )
            if manifest_block_reason:
                return manifest_block_reason
            route_path = manifest_record.get("path")
        else:
            route_path = self.resolve_route_expert_path(route)
        if not route_path:
            return "expert_model_missing" if self.route_has_explicit_expert(route) or is_legacy_route else "expert_unappointed"
        if not os.path.isfile(route_path):
            return "expert_model_missing"
        return None

    def _external_blink_route_config(self, route):
        route_params = route.get("backend_params") if isinstance(route, dict) else {}
        if isinstance(route_params, dict) and route_params.get("predict_command"):
            return sanitize_external_blink_config(route_params)
        project_manager = getattr(self, "project_manager", None)
        get_profile = getattr(project_manager, "get_active_model_profile", None)
        profile = get_profile() if callable(get_profile) else {}
        child_defaults = profile.get("child_backend_defaults", {}) if isinstance(profile, dict) and isinstance(profile.get("child_backend_defaults"), dict) else {}
        external_blink = child_defaults.get("external_blink_backend", {}) if isinstance(child_defaults.get("external_blink_backend"), dict) else {}
        return sanitize_external_blink_config(external_blink)

    def route_is_usable(self, route):
        return self.get_route_block_reason(route) is None

    def list_available_experts(self):
        experts = []
        if not os.path.exists(self.expert_dir):
            return experts
        expert_notes = load_expert_notes(self.engine.weights_dir)

        seen_paths = set()
        for part_folder in sorted(os.listdir(self.expert_dir)):
            if not is_safe_blink_expert_part_name(part_folder):
                continue
            part_path = os.path.join(self.expert_dir, part_folder)
            if not self._safe_managed_directory(part_path):
                continue
            for filename in sorted(os.listdir(part_path)):
                if not filename.lower().endswith(".pth"):
                    continue
                expert_id = build_expert_id(part_folder, filename)
                if not expert_id:
                    continue
                weights_path = os.path.join(part_path, filename)
                weights_path = self._safe_managed_file(weights_path)
                if not weights_path:
                    continue
                manifest_path = default_manifest_path_for_weights(weights_path)
                manifest = self._read_managed_json(manifest_path)
                if (
                    not isinstance(manifest, dict)
                    or manifest.get("schema_version")
                    not in BLINK_EXPERT_MANIFEST_SUPPORTED_SCHEMA_VERSIONS
                ):
                    manifest = {}
                elif self._resolve_manifest_weights_path(manifest_path) != weights_path:
                    manifest = {}
                input_size = manifest.get("input_size") if isinstance(manifest, dict) else None
                experts.append(
                    {
                        "expert_part": part_folder,
                        "expert_filename": filename,
                        "expert_id": expert_id,
                        "expert_backend": manifest.get("expert_backend") if isinstance(manifest, dict) and manifest.get("expert_backend") else ROUTE_BACKEND_VIT_B_BLINK,
                        "expert_manifest": manifest_path if manifest else "",
                        "input_size": input_size,
                        "backend_params": {},
                        "path": weights_path,
                        "note": expert_notes.get(expert_id, ""),
                    }
                )
                seen_paths.add(os.path.normcase(weights_path))

        training_root = self._safe_managed_directory(TRAINING_BUNDLE_DIRECTORY)
        if training_root:
            for run_id in sorted(os.listdir(training_root)):
                bundle = self._load_active_training_bundle(run_id)
                if not bundle:
                    continue
                artifacts = bundle.get("artifacts", [])
                manifests_by_path = {
                    os.path.normcase(os.path.abspath(item["path"])): item
                    for item in artifacts
                    if item.get("role") == "model_manifest"
                }
                for artifact in artifacts:
                    weights_path = artifact.get("path")
                    if (
                        artifact.get("role") != "output_weights"
                        or not isinstance(weights_path, str)
                        or not weights_path.lower().endswith(".pth")
                        or os.path.normcase(weights_path) in seen_paths
                    ):
                        continue
                    manifest_path = default_manifest_path_for_weights(weights_path)
                    if os.path.normcase(os.path.abspath(manifest_path)) not in manifests_by_path:
                        continue
                    manifest = self._read_managed_json(manifest_path)
                    if (
                        not isinstance(manifest, dict)
                        or manifest.get("schema_version")
                        not in BLINK_EXPERT_MANIFEST_SUPPORTED_SCHEMA_VERSIONS
                        or self._resolve_manifest_weights_path(manifest_path) != weights_path
                    ):
                        continue
                    expert_part = str(manifest.get("child_part") or os.path.basename(os.path.dirname(weights_path))).strip()
                    if not is_safe_blink_expert_part_name(expert_part):
                        continue
                    expert_filename = os.path.basename(weights_path)
                    expert_id = build_expert_id(expert_part, expert_filename)
                    if not expert_id:
                        continue
                    experts.append(
                        {
                            "expert_part": expert_part,
                            "expert_filename": expert_filename,
                            "expert_id": expert_id,
                            "expert_backend": manifest.get("expert_backend") or ROUTE_BACKEND_VIT_B_BLINK,
                            "expert_manifest": manifest_path,
                            "input_size": manifest.get("input_size"),
                            "backend_params": {},
                            "path": weights_path,
                            "note": expert_notes.get(expert_id, ""),
                            "publication_run_id": bundle.get("run_id"),
                        }
                    )
                    seen_paths.add(os.path.normcase(weights_path))
        experts.sort(
            key=lambda item: (
                str(item.get("expert_part") or "").casefold(),
                str(item.get("expert_filename") or "").casefold(),
                str(item.get("path") or "").casefold(),
            )
        )
        return experts
         
    def _load_expert(
        self,
        part_name,
        model_path=None,
        *,
        checkpoint_bytes=None,
        checkpoint_digest="",
        checkpoint_source="legacy_direct_compatibility",
        manifest_payload=None,
        manifest_identity=None,
        route_record=None,
    ):
        """懒加载：需要时才把对应的 Transformer 专家拉进显存"""
        if model_path is None:
            return None

        if checkpoint_bytes is None:
            record = self._read_legacy_checkpoint_record(
                model_path,
                source=checkpoint_source,
            )
            if not record:
                return None
            model_path = record["path"]
            checkpoint_bytes = record["checkpoint_bytes"]
            checkpoint_digest = record["digest"]
            checkpoint_source = record["source"]
        if not isinstance(checkpoint_bytes, bytes):
            return None

        observed_digest = hashlib.sha256(checkpoint_bytes).hexdigest()
        if checkpoint_digest and checkpoint_digest != observed_digest:
            raise BlinkBackendError("blink_checkpoint_payload_digest_mismatch")
        manifest = None
        manifest_digest = "no-manifest"
        if manifest_payload is not None:
            try:
                manifest, manifest_digest = verify_blink_manifest_payload(
                    manifest_payload,
                    manifest_identity,
                )
            except ValueError as exc:
                raise BlinkBackendError(str(exc)) from exc

        cache_key = ":".join(
            (
                ROUTE_BACKEND_VIT_B_BLINK,
                str(checkpoint_source or "unknown"),
                os.path.normcase(os.path.abspath(model_path)),
                manifest_digest,
                observed_digest,
            )
        )
        if cache_key in self.loaded_experts:
            expert_model = self.loaded_experts[cache_key]
            if manifest is not None:
                try:
                    validate_blink_expert_contract(
                        manifest,
                        getattr(expert_model, "_taxamask_meta", {}),
                        expected_backend=ROUTE_BACKEND_VIT_B_BLINK,
                        route_input_size=(route_record or {}).get("input_size"),
                        route_parent_part=(route_record or {}).get("parent"),
                        route_child_part=(route_record or {}).get("child"),
                    )
                except ValueError as exc:
                    raise BlinkBackendError(str(exc)) from exc
            return expert_model

        print(f"Loading Micro-Expert for [{part_name}] from {model_path}...")
        loaded = torch.load(
            io.BytesIO(checkpoint_bytes),
            map_location=self.device,
            weights_only=True,
        )
        checkpoint_state = loaded
        checkpoint_meta = {}
        if isinstance(loaded, dict) and isinstance(loaded.get("state_dict"), dict):
            checkpoint_state = loaded.get("state_dict", {})
            checkpoint_meta = loaded.get("meta", {}) if isinstance(loaded.get("meta"), dict) else {}
        if manifest is not None:
            try:
                contract = validate_blink_expert_contract(
                    manifest,
                    checkpoint_meta,
                    expected_backend=ROUTE_BACKEND_VIT_B_BLINK,
                    route_input_size=(route_record or {}).get("input_size"),
                    route_parent_part=(route_record or {}).get("parent"),
                    route_child_part=(route_record or {}).get("child"),
                )
            except ValueError as exc:
                raise BlinkBackendError(str(exc)) from exc
            checkpoint_meta = dict(checkpoint_meta)
            checkpoint_meta["input_size"] = list(contract["input_size"])
        input_size = checkpoint_meta.get("input_size") or [224, 224]
        try:
            input_side = int(input_size[0] if isinstance(input_size, (list, tuple)) else input_size)
        except Exception:
            input_side = 224
        expert_model = MicroExpertLocator(pretrained=False, image_size=input_side).to(self.device)
        expert_model.load_state_dict(checkpoint_state)
        expert_model._taxamask_meta = checkpoint_meta
        expert_model.eval()
         
        self.loaded_experts[cache_key] = expert_model
        return expert_model

    def _infer_with_loaded_expert(self, image_path, parent_box, child_part_name, expert_model):
        if expert_model is None:
            return None

        img_np = cv2.imread(image_path)
        if img_np is None:
            return None
        img_np = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)
        h, w, _ = img_np.shape

        meta = getattr(expert_model, "_taxamask_meta", {}) if expert_model is not None else {}
        input_size = meta.get("input_size") if isinstance(meta, dict) else None
        try:
            input_side = int(input_size[0] if isinstance(input_size, (list, tuple)) else input_size)
        except Exception:
            input_side = int(getattr(expert_model, "image_size", 224) or 224)
        target_size = (input_side, input_side)
        mapper = CoordinateMapper((w, h), parent_box, target_size=target_size)
        zoomed_img_np = mapper.crop_and_resize(img_np)

        img_tensor = torch.from_numpy(zoomed_img_np).permute(2, 0, 1).float() / 255.0
        img_tensor = img_tensor.unsqueeze(0).to(self.device)

        with torch.no_grad():
            preds_cxcywh_rel = expert_model(img_tensor)[0]
            preds_rel = preds_cxcywh_rel.cpu().numpy()

        local_box = expert_model._cxcywh_to_xyxy(preds_rel, target_size[0], target_size[1])
        local_box = CoordinateMapper.clamp_bbox_to_size(local_box, target_size[0], target_size[1])

        box_w = max(1e-6, float(local_box[2] - local_box[0]))
        box_h = max(1e-6, float(local_box[3] - local_box[1]))
        area_ratio = (box_w * box_h) / float(target_size[0] * target_size[1])
        if area_ratio < 0.002:
            return None

        confidence = 1.0
        global_box = mapper.bbox_local_to_global(local_box)

        print(
            f"Cascading Success: Found {child_part_name} at global coords {global_box} "
            f"(conf={confidence:.3f}, area_ratio={area_ratio:.3f})"
        )
        return {
            "box": global_box,
            "confidence": confidence,
            "area_ratio": float(area_ratio),
        }

    def infer_legacy_expert_in_parent_box(self, image_path, parent_box, child_part_name):
        legacy_path = os.path.join(self.expert_dir, child_part_name, LEGACY_EXPERT_FILENAME)
        expert_model = self._load_expert(child_part_name, model_path=legacy_path)
        if expert_model is None:
            print(f"Legacy expert model for {child_part_name} not found. Skipping.")
            return None
        return self._infer_with_loaded_expert(image_path, parent_box, child_part_name, expert_model)

    def run_cascading_inference(self, image_path, parent_part="Head", child_part="Mandible", parent_box=None, route_manifest=None):
        """
        验证逻辑：
        1. 获取父节点的框 (模拟大模型输出)
        2. 裁剪放大
        3. 专家推理
        4. 坐标回传
        """
        # 注意：这里我们为了简化测试，假设父节点已经被识别，
        # 在真实应用中，这一步应该调用 self.engine.locator.predict() 获取。
        # 这里我们假定 project 已经有了 Head 的手动框或者机器框作为父节点。
        
        # 为了避免循环依赖，这里默认由调用方直接提供 parent_box
        if parent_box is None:
            print(
                f"Cascade Scaffold: missing parent_box for parent={parent_part}, child={child_part}. "
                "Call infer_child_part() directly with a valid parent_box."
            )
            return None

        return self.infer_child_part(
            image_path=image_path,
            parent_box=parent_box,
            child_part_name=child_part,
            parent_part=parent_part,
            route_manifest=route_manifest,
        )
         
    def infer_child_part(self, image_path, parent_box, child_part_name, parent_part="macro_locator", route_manifest=None):
        """
        核心接力函数：在大图的 parent_box 中，寻找 child_part。
        返回：全局坐标下的 [x1, y1, x2, y2]
        """
        route = self._find_route(parent_part, child_part_name, route_manifest=route_manifest)
        if route is None:
            return None

        backend = str(route.get("expert_backend") or ROUTE_BACKEND_VIT_B_BLINK).strip() or ROUTE_BACKEND_VIT_B_BLINK
        try:
            return self._blink_backends().predict_child_box(
                backend,
                manager=self,
                image_path=image_path,
                parent_box=parent_box,
                child_part_name=child_part_name,
                parent_part=parent_part,
                route_record=self._runtime_route_record(route),
                context={
                    "route_manifest": route_manifest,
                },
            )
        except BlinkBackendError as exc:
            print(f"Blink backend failed for {child_part_name}: {exc}")
            return None
