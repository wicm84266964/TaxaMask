import argparse
import hashlib
import json
import os
import sys
from typing import Any

from PIL import Image


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from AntSleap.core.project import (  # noqa: E402
    AUTO_BOX_REVIEW_CONFIRMED,
    AUTO_BOX_REVIEW_DRAFT,
    AUTO_BOX_SOURCE_MODEL,
    ProjectManager,
)
from AntSleap.core.project_integrity_registry import (  # noqa: E402
    get_training_baseline_snapshot,
)
from AntSleap.core.safe_io import (  # noqa: E402
    atomic_write_json,
    read_bytes_bounded_in_root,
    read_json_bounded_in_root,
)
from AntSleap.core.training_initial_weights import (  # noqa: E402
    read_verified_initial_weight,
)
from AntSleap.core.file_integrity import (  # noqa: E402
    FULL_FILE_ALGORITHM,
)
from AntSleap.core.training_run_recorder import (  # noqa: E402
    TRAINING_RUN_FILENAME,
    TrainingRunRecorder,
)
from AntSleap.core.training_weight_publisher import (  # noqa: E402
    TrainingWeightPublisher,
)


def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: str, payload: dict[str, Any]) -> None:
    atomic_write_json(path, payload, ensure_ascii=False, indent=2)


def _extract_prediction_payload(payload: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    polygons: dict[str, Any] = {}
    auto_boxes: dict[str, Any] = {}
    if not isinstance(payload, dict):
        return polygons, auto_boxes
    if isinstance(payload.get("polygons"), dict):
        polygons = payload.get("polygons", {})
        if isinstance(payload.get("auto_boxes"), dict):
            auto_boxes = payload.get("auto_boxes", {})
        return polygons, auto_boxes
    for key, value in payload.items():
        if key.endswith("_BOX") and isinstance(value, list):
            xs = [point[0] for point in value if isinstance(point, (list, tuple)) and len(point) >= 2]
            ys = [point[1] for point in value if isinstance(point, (list, tuple)) and len(point) >= 2]
            if xs and ys:
                auto_boxes[key.replace("_BOX", "")] = [float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))]
        elif isinstance(value, list):
            polygons[key] = value
    return polygons, auto_boxes


def _prediction_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        records = payload.get("predictions")
        if isinstance(records, list):
            return [item for item in records if isinstance(item, dict)]
        images = payload.get("images")
        if isinstance(images, dict):
            return [
                {"image_path": image_path, "payload": prediction}
                for image_path, prediction in images.items()
            ]
        return [
            {"image_path": image_path, "payload": prediction}
            for image_path, prediction in payload.items()
            if isinstance(image_path, str) and isinstance(prediction, dict)
        ]
    return []


def _image_size(path: str) -> tuple[float, float] | None:
    try:
        with Image.open(path) as image:
            width, height = image.size
        return float(width), float(height)
    except Exception:
        return None


def _clean_box(raw_box: Any, image_size: tuple[float, float] | None) -> list[float] | None:
    if not isinstance(raw_box, (list, tuple)) or len(raw_box) != 4:
        return None
    try:
        x1, y1, x2, y2 = [float(value) for value in raw_box]
    except Exception:
        return None
    if image_size is not None:
        width, height = image_size
        x1 = max(0.0, min(x1, width - 0.1))
        x2 = max(0.0, min(x2, width - 0.1))
        y1 = max(0.0, min(y1, height - 0.1))
        y2 = max(0.0, min(y2, height - 0.1))
    if x2 <= x1 or y2 <= y1:
        return None
    return [x1, y1, x2, y2]


def _clean_polygon(raw_points: Any, image_size: tuple[float, float] | None) -> list[list[float]] | None:
    if not isinstance(raw_points, list) or len(raw_points) < 3:
        return None
    clean: list[list[float]] = []
    for point in raw_points:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        try:
            x = float(point[0])
            y = float(point[1])
        except Exception:
            continue
        if image_size is not None:
            width, height = image_size
            x = max(0.0, min(x, width - 0.1))
            y = max(0.0, min(y, height - 0.1))
        clean.append([x, y])
    return clean if len(clean) >= 3 else None


def _is_unconfirmed_ai_draft(manager: ProjectManager, image_path: str, part_name: str) -> bool:
    labels_entry = manager.project_data.get("labels", {}).get(image_path, {})
    if not isinstance(labels_entry, dict):
        return False
    descriptions = labels_entry.get("descriptions", {}) if isinstance(labels_entry.get("descriptions", {}), dict) else {}
    if descriptions.get(part_name) != "Auto-Annotated":
        return False
    meta = labels_entry.get("auto_box_meta", {}) if isinstance(labels_entry.get("auto_box_meta", {}), dict) else {}
    part_meta = meta.get(part_name, {}) if isinstance(meta.get(part_name), dict) else {}
    return str(part_meta.get("review_status") or AUTO_BOX_REVIEW_DRAFT).strip() != AUTO_BOX_REVIEW_CONFIRMED


def _can_model_replace(manager: ProjectManager, image_path: str, part_name: str, only_new: bool) -> bool:
    labels_by_part = manager.get_labels(image_path)
    has_label = part_name in labels_by_part
    auto_boxes = manager.get_auto_boxes(image_path)
    has_auto_box = isinstance(auto_boxes, dict) and part_name in auto_boxes
    if not has_label and not has_auto_box:
        return True
    meta = manager.get_auto_box_meta(image_path)
    part_meta = meta.get(part_name, {}) if isinstance(meta, dict) and isinstance(meta.get(part_name), dict) else {}
    review_status = str(part_meta.get("review_status") or AUTO_BOX_REVIEW_DRAFT).strip()
    if review_status == AUTO_BOX_REVIEW_CONFIRMED:
        return False
    if has_label and not _is_unconfirmed_ai_draft(manager, image_path, part_name):
        return False
    if not only_new:
        return True
    return has_label or has_auto_box


def _apply_payload(
    manager: ProjectManager,
    image_path: str,
    payload: Any,
    only_new: bool,
    save_drafts_only: bool = False,
) -> dict[str, Any]:
    polygons, auto_boxes = _extract_prediction_payload(payload)
    prediction_meta = (
        dict(payload.get("meta") or {})
        if isinstance(payload, dict) and isinstance(payload.get("meta"), dict)
        else {}
    )
    prediction_scores = (
        dict(payload.get("scores") or {})
        if isinstance(payload, dict) and isinstance(payload.get("scores"), dict)
        else {}
    )
    taxonomy = set(manager.project_data.get("taxonomy", []))
    image_size = _image_size(image_path)

    saved = 0
    rejected: list[dict[str, str]] = []
    part_names = list(polygons.keys())
    if save_drafts_only:
        for part_name in auto_boxes.keys():
            if part_name not in polygons:
                part_names.append(part_name)

    for part_name in part_names:
        raw_points = polygons.get(part_name)
        clean_part = str(part_name).strip()
        if not clean_part:
            rejected.append({"part": str(part_name), "reason": "empty_part"})
            continue
        if taxonomy and clean_part not in taxonomy:
            rejected.append({"part": clean_part, "reason": "unknown_taxonomy"})
            continue
        if not _can_model_replace(manager, image_path, clean_part, only_new):
            rejected.append({"part": clean_part, "reason": "already_labeled"})
            continue
        clean_box = _clean_box(auto_boxes.get(clean_part), image_size)
        clean_polygon = _clean_polygon(raw_points, image_size)
        if clean_polygon is None and not save_drafts_only:
            rejected.append({"part": clean_part, "reason": "invalid_polygon"})
            continue
        if clean_box is None:
            if clean_polygon is None:
                rejected.append({"part": clean_part, "reason": "invalid_box"})
                continue
            xs = [point[0] for point in clean_polygon]
            ys = [point[1] for point in clean_polygon]
            clean_box = _clean_box([min(xs), min(ys), max(xs), max(ys)], image_size)
        if save_drafts_only:
            update_auto_box = getattr(manager, "update_auto_box", None)
            if callable(update_auto_box) and clean_box is not None:
                update_auto_box(
                    image_path,
                    clean_part,
                    clean_box,
                    description_text="Auto-Annotated",
                    source_meta={"source": AUTO_BOX_SOURCE_MODEL, "review_status": AUTO_BOX_REVIEW_DRAFT},
                    save=False,
                )
            else:
                manager.update_label(
                    image_path,
                    clean_part,
                    [],
                    "Auto-Annotated",
                    auto_box=clean_box,
                    save=False,
                    training_source=AUTO_BOX_SOURCE_MODEL,
                    training_review_status=AUTO_BOX_REVIEW_DRAFT,
                    training_accepted_via="",
                )
        else:
            manager.update_label(
                image_path,
                clean_part,
                clean_polygon,
                "Auto-Annotated",
                auto_box=clean_box,
                save=False,
                training_source=AUTO_BOX_SOURCE_MODEL,
                training_review_status=AUTO_BOX_REVIEW_DRAFT,
                training_accepted_via="",
            )
            update_auto_box = getattr(manager, "update_auto_box", None)
            if callable(update_auto_box) and clean_box is not None:
                update_auto_box(
                    image_path,
                    clean_part,
                    clean_box,
                    source_meta={"source": AUTO_BOX_SOURCE_MODEL, "review_status": AUTO_BOX_REVIEW_DRAFT},
                    save=False,
                )
        saved += 1
    detected_count = len(part_names) if save_drafts_only else len(polygons)
    return {
        "image_path": image_path,
        "detected_count": detected_count,
        "saved_count": saved,
        "rejected": rejected,
        "predicted_parts": sorted(
            set(polygons) | set(auto_boxes) | set(prediction_scores)
        ),
        "prediction_scores": prediction_scores,
        "prediction_meta": prediction_meta,
    }


def _canonical_json_identity(payload: Any) -> dict[str, Any]:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "hash_algorithm": FULL_FILE_ALGORITHM,
        "size_bytes": len(encoded),
        "digest": hashlib.sha256(encoded).hexdigest(),
    }


def _training_base_sam_evidence(
    manager: ProjectManager,
    record: dict[str, Any],
    *,
    run_dir: str,
) -> dict[str, Any]:
    project_ref = record.get("project_ref") or {}
    data_version_id = str(project_ref.get("project_data_version_id") or "")
    if not data_version_id:
        raise ValueError("training_run_data_version_missing")
    snapshot = get_training_baseline_snapshot(
        manager.current_database_path,
        data_version_id,
    )
    registered = [
        item
        for item in snapshot.get("files", [])
        if item.get("owner_kind") == "model_weight"
        and item.get("owner_key") == "parent.sam_base"
        and item.get("role") == "initial_weights"
    ]
    if len(registered) != 1:
        raise ValueError("training_run_base_sam_registry_entry_missing")
    registered_weight = registered[0]

    manifest_ref = record.get("integrity_manifest")
    if not isinstance(manifest_ref, dict):
        raise ValueError("training_run_integrity_manifest_missing")
    if manifest_ref.get("path_base") != "run_root":
        raise ValueError("training_run_integrity_manifest_path_invalid")
    relative_path = str(manifest_ref.get("relative_path") or "")
    manifest_path = os.path.abspath(
        os.path.join(run_dir, *relative_path.split("/"))
    )
    try:
        inside_run = os.path.normcase(
            os.path.commonpath([run_dir, manifest_path])
        ) == os.path.normcase(run_dir)
    except ValueError:
        inside_run = False
    expected_size = manifest_ref.get("size_bytes")
    if (
        not relative_path
        or not inside_run
        or not isinstance(expected_size, int)
        or isinstance(expected_size, bool)
        or expected_size <= 0
    ):
        raise ValueError("training_run_integrity_manifest_path_invalid")
    manifest_bytes = read_bytes_bounded_in_root(
        manifest_path,
        trusted_root=run_dir,
        max_bytes=expected_size,
    )
    manifest_identity = {
        "entry_kind": "file",
        "size_bytes": len(manifest_bytes),
        "hash_algorithm": FULL_FILE_ALGORITHM,
        "digest": hashlib.sha256(manifest_bytes).hexdigest(),
    }
    for field in ("entry_kind", "size_bytes", "hash_algorithm", "digest"):
        if manifest_identity.get(field) != manifest_ref.get(field):
            raise ValueError(
                f"training_run_integrity_manifest_mismatch:{field}"
            )
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("training_run_integrity_manifest_invalid") from exc
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != "taxamask_integrity_manifest_v1"
        or manifest.get("run_id") != record.get("run_id")
        or manifest.get("status") != "verified"
    ):
        raise ValueError("training_run_integrity_manifest_invalid")
    included = [
        item
        for item in manifest.get("files", [])
        if isinstance(item, dict)
        and item.get("file_id") == registered_weight.get("file_id")
        and item.get("role") == "initial_weights"
        and item.get("status") == "verified"
    ]
    if len(included) != 1:
        raise ValueError("training_run_base_sam_not_in_verified_inputs")
    run_weight = included[0]
    for field in ("size_bytes", "hash_algorithm", "digest", "data_version_id"):
        if run_weight.get(field) != registered_weight.get(field):
            raise ValueError(f"training_run_base_sam_evidence_mismatch:{field}")
    return {
        "slot": "parent.sam_base",
        "file_id": str(registered_weight.get("file_id") or ""),
        "data_version_id": data_version_id,
        "fingerprint": {
            key: registered_weight.get(key)
            for key in ("entry_kind", "size_bytes", "hash_algorithm", "digest")
        },
        "integrity_manifest": {
            "path_base": "run_root",
            "relative_path": relative_path,
            "size_bytes": manifest_identity["size_bytes"],
            "hash_algorithm": manifest_identity["hash_algorithm"],
            "digest": manifest_identity["digest"],
        },
    }


def _managed_checkpoint_bundle(
    manager: ProjectManager,
    *,
    training_run_id: str,
    runs_root: str,
    managed_model_root: str,
    require_sam_decoder: bool,
) -> dict[str, Any]:
    run_id = str(training_run_id or "").strip()
    if not run_id:
        raise ValueError("training_run_id_required")
    if not str(runs_root or "").strip():
        raise ValueError("runs_root_required")
    if not str(managed_model_root or "").strip():
        raise ValueError("managed_model_root_required")
    if not manager.is_sqlite_project() or not manager.current_database_path:
        raise ValueError("sqlite_project_required_for_managed_engine")

    resolved_runs_root = os.path.abspath(os.fspath(runs_root))
    resolved_model_root = os.path.abspath(os.fspath(managed_model_root))
    recorder = TrainingRunRecorder(
        resolved_runs_root,
        database_path=manager.current_database_path,
        recover_on_startup=False,
    )
    record = recorder.load(run_id)
    if record.get("status") != "succeeded":
        raise ValueError("training_run_not_succeeded")

    run_dir = os.path.abspath(os.path.join(resolved_runs_root, run_id))
    if not os.path.isdir(run_dir):
        raise ValueError("training_run_directory_missing")
    projected_record = read_json_bounded_in_root(
        os.path.join(run_dir, TRAINING_RUN_FILENAME),
        trusted_root=resolved_runs_root,
        max_bytes=16 * 1024 * 1024,
    )
    if projected_record != record:
        raise ValueError("training_run_projection_mismatch")

    run_project_id = str((record.get("project_ref") or {}).get("project_id") or "")
    project_id = str(manager.project_data.get("project_id") or "")
    if not run_project_id or not project_id:
        raise ValueError("training_run_project_identity_missing")
    if run_project_id != project_id:
        raise ValueError("training_run_project_identity_mismatch")

    training_base_sam = (
        _training_base_sam_evidence(manager, record, run_dir=run_dir)
        if require_sam_decoder
        else None
    )

    active = TrainingWeightPublisher(resolved_model_root).list_active(recorder.load)
    publications = [
        item
        for item in active.get("publications", [])
        if str(item.get("run_id") or "") == run_id
    ]
    if len(publications) != 1:
        rejected_reasons = sorted(
            str(item.get("reason") or "")
            for item in active.get("rejected", [])
            if str(item.get("run_id") or "") == run_id
            and str(item.get("reason") or "")
        )
        suffix = f":{rejected_reasons[0]}" if rejected_reasons else ""
        raise ValueError(f"locator_publication_not_active{suffix}")

    publication = publications[0]

    def read_artifact(artifact_id: str) -> dict[str, Any]:
        error_prefix = (
            "locator_checkpoint"
            if artifact_id == "locator_checkpoint"
            else "sam_decoder_checkpoint"
        )
        artifacts = [
            item
            for item in publication.get("artifacts", [])
            if item.get("artifact_id") == artifact_id
            and item.get("role") == "output_weights"
            and item.get("path_base") == "managed_model_root"
            and item.get("hash_algorithm") == FULL_FILE_ALGORITHM
        ]
        if len(artifacts) != 1:
            raise ValueError(f"{error_prefix}_artifact_invalid")
        artifact = artifacts[0]
        relative_path = str(artifact.get("relative_path") or "")
        checkpoint_path = os.path.abspath(
            os.path.join(resolved_model_root, *relative_path.split("/"))
        )
        try:
            inside_model_root = os.path.normcase(
                os.path.commonpath([resolved_model_root, checkpoint_path])
            ) == os.path.normcase(resolved_model_root)
        except ValueError:
            inside_model_root = False
        if not relative_path or not inside_model_root:
            raise ValueError(f"{error_prefix}_outside_managed_model_root")
        if not os.path.isfile(checkpoint_path):
            raise ValueError(f"{error_prefix}_missing")

        expected_size = artifact.get("size_bytes")
        if (
            not isinstance(expected_size, int)
            or isinstance(expected_size, bool)
            or expected_size <= 0
        ):
            raise ValueError(f"{error_prefix}_artifact_invalid")
        checkpoint_payload = read_bytes_bounded_in_root(
            checkpoint_path,
            trusted_root=resolved_model_root,
            max_bytes=expected_size,
        )
        observed = {
            "entry_kind": "file",
            "size_bytes": len(checkpoint_payload),
            "hash_algorithm": FULL_FILE_ALGORITHM,
            "digest": hashlib.sha256(checkpoint_payload).hexdigest(),
        }
        for field in ("entry_kind", "size_bytes", "hash_algorithm", "digest"):
            if observed.get(field) != artifact.get(field):
                raise ValueError(
                    f"{error_prefix}_fingerprint_mismatch:{field}"
                )
        return {
            "path": checkpoint_path,
            "payload": checkpoint_payload,
            "evidence": {
                "artifact_id": artifact_id,
                "path_base": "managed_model_root",
                "relative_path": relative_path,
                "size_bytes": observed["size_bytes"],
                "hash_algorithm": observed["hash_algorithm"],
                "digest": observed["digest"],
                "loaded": False,
            },
        }

    locator = read_artifact("locator_checkpoint")
    decoder = (
        read_artifact("sam_decoder_checkpoint")
        if require_sam_decoder
        else None
    )
    return {
        "run_id": run_id,
        "training_run": {
            "run_id": run_id,
            "project_ref": dict(record.get("project_ref") or {}),
            "dataset_ref": dict(record.get("dataset_ref") or {}),
        },
        "publication": {
            "schema_version": str(publication.get("schema_version") or ""),
            "status": str(publication.get("status") or ""),
            "created_at": publication.get("created_at"),
            "activated_at": publication.get("activated_at"),
            "run_id": str(publication.get("run_id") or ""),
        },
        "training_base_sam": training_base_sam,
        "locator_checkpoint": locator,
        "sam_decoder_checkpoint": decoder,
    }


def _managed_locator_checkpoint(
    manager: ProjectManager,
    *,
    training_run_id: str,
    runs_root: str,
    managed_model_root: str,
) -> tuple[str, dict[str, Any], bytes]:
    bundle = _managed_checkpoint_bundle(
        manager,
        training_run_id=training_run_id,
        runs_root=runs_root,
        managed_model_root=managed_model_root,
        require_sam_decoder=False,
    )
    locator = bundle["locator_checkpoint"]
    evidence = dict(locator["evidence"])
    evidence["run_id"] = bundle["run_id"]
    return locator["path"], evidence, locator["payload"]


def _run_engine_predictions(
    manager: ProjectManager,
    confidence: float,
    *,
    training_run_id: str,
    runs_root: str,
    managed_model_root: str,
    base_sam_path: str = "",
    only_new: bool = False,
    device: str = "auto",
    draft_boxes_only: bool = False,
    evidence_out: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from AntSleap.core.engine import (  # Imported lazily because this can initialize model weights.
        LOCATOR_CHECKPOINT_SCHEMA_VERSION,
        AntEngine,
    )

    locator_scope = list(manager.get_locator_scope())
    route_manifest = manager.get_cascade_routes()
    routes = route_manifest.get("routes", [])
    route_identity = _canonical_json_identity(route_manifest)
    requested_evidence = {
        "run_id": str(training_run_id or ""),
        "project_ref": {
            "project_id": str(manager.project_data.get("project_id") or ""),
            "project_data_version_id": str(
                manager.project_data.get("project_data_version_id") or ""
            ),
        },
        "route_manifest_evidence": {
            "version": str(route_manifest.get("version") or ""),
            "route_count": len(routes),
            "enabled_route_count": sum(
                1
                for route in routes
                if isinstance(route, dict) and bool(route.get("enabled", False))
            ),
            **route_identity,
        },
        "prediction_mode": (
            "locator_boxes" if draft_boxes_only else "full_pipeline"
        ),
    }

    def sync_evidence(payload: dict[str, Any]) -> None:
        if isinstance(evidence_out, dict):
            evidence_out.clear()
            evidence_out.update(payload)

    sync_evidence(requested_evidence)
    checkpoint_bundle = _managed_checkpoint_bundle(
        manager,
        training_run_id=training_run_id,
        runs_root=runs_root,
        managed_model_root=managed_model_root,
        require_sam_decoder=not draft_boxes_only,
    )
    locator_checkpoint = checkpoint_bundle["locator_checkpoint"]
    checkpoint_path = locator_checkpoint["path"]
    checkpoint_payload = locator_checkpoint["payload"]
    checkpoint_evidence = dict(locator_checkpoint["evidence"])
    checkpoint_evidence["run_id"] = checkpoint_bundle["run_id"]
    run_id = checkpoint_evidence["run_id"]
    decoder = checkpoint_bundle["sam_decoder_checkpoint"]
    checkpoint_evidence.update(requested_evidence)
    checkpoint_evidence.update(
        {
            "run_id": run_id,
            "training_run": checkpoint_bundle["training_run"],
            "publication": checkpoint_bundle["publication"],
            "training_base_sam": checkpoint_bundle["training_base_sam"],
            "base_sam_evidence": None,
            "sam_decoder_evidence": (
                dict(decoder["evidence"]) if decoder is not None else None
            ),
        }
    )
    sync_evidence(checkpoint_evidence)
    managed_root = os.path.abspath(os.fspath(managed_model_root))
    engine = AntEngine(
        num_classes=len(locator_scope),
        device=device,
        weights_dir=managed_root,
        locator_scope=locator_scope,
    )
    cascade_manager = getattr(engine, "cascade_manager", None)
    if cascade_manager is not None:
        cascade_manager.project_manager = manager
    elif any(
        bool(item.get("enabled", False))
        for item in route_manifest.get("routes", [])
        if isinstance(item, dict)
    ):
        raise ValueError("cascade_manager_required_for_enabled_project_routes")

    base_sam_evidence = None
    if not draft_boxes_only:
        try:
            item = read_verified_initial_weight(
                manager,
                {"slot": "parent.sam_base", "path": base_sam_path},
            )
        except Exception as exc:
            raise ValueError("base_sam_registry_verification_failed") from exc
        expected_base = checkpoint_bundle["training_base_sam"]["fingerprint"]
        if any(
            item["observed"].get(field) != expected_base.get(field)
            for field in ("entry_kind", "size_bytes", "hash_algorithm", "digest")
        ):
            raise ValueError("base_sam_training_run_mismatch")
        engine.configure_verified_base_sam(
            item["payload"],
            reference=os.path.abspath(os.fspath(item["path"])),
            fingerprint=item["observed"],
        )
        base_sam_evidence = {
            "slot": "parent.sam_base",
            "path": os.path.abspath(os.fspath(item["path"])),
            "status": item["status"],
            "fingerprint": item["observed"],
            "loaded_from_verified_bytes": True,
        }
        checkpoint_evidence["base_sam_evidence"] = base_sam_evidence
        sync_evidence(checkpoint_evidence)
    engine.load_locator(
        run_id,
        checkpoint_path=checkpoint_path,
        checkpoint_payload=checkpoint_payload,
        require_complete=True,
        expected_locator_scope=locator_scope,
    )
    if (
        engine.locator is None
        or str(engine.loaded_locator_timestamp or "") != run_id
        or str(engine.loaded_locator_schema_version or "")
        != LOCATOR_CHECKPOINT_SCHEMA_VERSION
        or list(engine.loaded_locator_scope or []) != locator_scope
    ):
        raise ValueError("locator_checkpoint_load_failed")
    checkpoint_evidence["loaded"] = True
    checkpoint_evidence["checkpoint_schema_version"] = (
        engine.loaded_locator_schema_version
    )
    checkpoint_evidence["locator_scope"] = list(engine.loaded_locator_scope)
    checkpoint_evidence["base_sam_evidence"] = base_sam_evidence
    sync_evidence(checkpoint_evidence)
    if not draft_boxes_only:
        engine.load_sam_decoder(
            run_id,
            checkpoint_path=decoder["path"],
            checkpoint_bytes=decoder["payload"],
            expected_base_sam_fingerprint=checkpoint_bundle[
                "training_base_sam"
            ]["fingerprint"],
            require_base_sam_match=True,
        )
        expected_decoder_reference = decoder["evidence"]["relative_path"]
        if (
            engine.parts_model is None
            or engine.loaded_sam_decoder_reference != expected_decoder_reference
        ):
            raise ValueError("sam_decoder_checkpoint_load_failed")
        decoder_evidence = dict(decoder["evidence"])
        decoder_evidence["loaded"] = True
        checkpoint_evidence["sam_decoder_evidence"] = decoder_evidence
        sync_evidence(checkpoint_evidence)

    records: list[dict[str, Any]] = []
    for image_path in manager.project_data.get("images", []):
        predict = (
            engine.predict_box_pipeline
            if draft_boxes_only
            else engine.predict_full_pipeline
        )
        payload = predict(
            image_path,
            manager.project_data.get("taxonomy", []),
            locator_scope,
            conf_thresh=confidence,
            project_route_manifest=route_manifest,
        )
        records.append({"image_path": image_path, "payload": payload})
    return records, checkpoint_evidence


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply batch auto-annotation predictions to a TaxaMask project JSON.")
    parser.add_argument("--project", required=True, help="Input project JSON.")
    parser.add_argument(
        "--out",
        required=True,
        help=(
            "Output project JSON. SQLite manifests must use the same path as "
            "--project; copy the manifest and database before running when an "
            "isolated output is required."
        ),
    )
    parser.add_argument("--predictions", default="", help="Prediction JSON. Omit only with --run-engine.")
    parser.add_argument("--run-engine", action="store_true", help="Run AntEngine.predict_full_pipeline for each project image.")
    parser.add_argument("--training-run-id", default="", help="Succeeded training run whose active locator checkpoint must be loaded.")
    parser.add_argument("--runs-root", default="", help="Training run record directory used by --run-engine.")
    parser.add_argument("--managed-model-root", default="", help="Managed model publication root used by --run-engine.")
    parser.add_argument(
        "--base-sam-path",
        default="",
        help=(
            "Registry-verified parent.sam_base path required for full-pipeline "
            "engine inference; unused with --draft-boxes-only."
        ),
    )
    parser.add_argument("--only-new", action="store_true", help="Do not overwrite already-labeled parts.")
    parser.add_argument("--draft-boxes-only", action="store_true", help="Write only draft auto_boxes instead of training-eligible polygons.")
    parser.add_argument("--confidence", type=float, default=0.35, help="Inference confidence threshold for --run-engine.")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto", help="Compute device preference for --run-engine.")
    parser.add_argument("--report", default="", help="Optional annotation report JSON path.")
    args = parser.parse_args()
    if args.run_engine:
        missing = [
            option
            for option, value in (
                ("--training-run-id", args.training_run_id),
                ("--runs-root", args.runs_root),
                ("--managed-model-root", args.managed_model_root),
            )
            if not str(value or "").strip()
        ]
        if missing:
            parser.error("--run-engine requires " + ", ".join(missing))
        if not args.draft_boxes_only and not str(args.base_sam_path or "").strip():
            parser.error(
                "--run-engine full-pipeline mode requires --base-sam-path"
            )

    project_path = os.path.abspath(args.project)
    out_project = os.path.abspath(args.out)
    report_path = os.path.abspath(args.report) if args.report else os.path.splitext(out_project)[0] + "_auto_annotation_report.json"
    os.makedirs(os.path.dirname(out_project) or os.getcwd(), exist_ok=True)

    manager = ProjectManager()
    manager.load_project(project_path)
    if manager.is_sqlite_project():
        if os.path.normcase(os.path.realpath(project_path)) != os.path.normcase(
            os.path.realpath(out_project)
        ):
            raise ValueError(
                "sqlite_output_must_match_input_manifest; copy the SQLite project "
                "before running to create an isolated output"
            )
        storage_write_mode = "sqlite_in_place"
    else:
        manager.current_project_path = out_project
        manager.enable_legacy_json_writes_for_compatibility(True)
        storage_write_mode = "legacy_json_copy"

    checkpoint_evidence = None
    if args.run_engine:
        partial_evidence: dict[str, Any] = {}
        try:
            records, checkpoint_evidence = _run_engine_predictions(
                manager,
                float(args.confidence),
                training_run_id=args.training_run_id,
                runs_root=args.runs_root,
                managed_model_root=args.managed_model_root,
                base_sam_path=args.base_sam_path,
                only_new=bool(args.only_new),
                device=args.device,
                draft_boxes_only=bool(args.draft_boxes_only),
                evidence_out=partial_evidence,
            )
        except Exception as exc:
            _write_json(
                report_path,
                {
                    "schema_version": "formica-auto-annotation-report-v1",
                    "status": "failed",
                    "failure_stage": "engine_prediction",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "project_input": project_path,
                    "project_output": out_project,
                    "storage_write_mode": storage_write_mode,
                    "prediction_source": "engine",
                    "checkpoint_evidence": partial_evidence or None,
                    "engine_prediction_mode": (
                        "locator_boxes"
                        if args.draft_boxes_only
                        else "full_pipeline"
                    ),
                    "draft_boxes_only": bool(args.draft_boxes_only),
                    "image_count": 0,
                    "applied_label_count": 0,
                    "saved_label_count": 0,
                    "save_completed": False,
                    "rejected_count": 0,
                    "results": [],
                },
            )
            raise
    elif args.predictions:
        records = _prediction_records(_load_json(os.path.abspath(args.predictions)))
    else:
        raise SystemExit("--predictions is required unless --run-engine is set")

    transaction_state = manager._snapshot_runtime_state(deep=True)
    journal_transaction = manager.begin_label_journal_transaction()
    image_lookup = {os.path.abspath(path): path for path in manager.project_data.get("images", [])}
    results: list[dict[str, Any]] = []
    failure_stage = "apply_predictions"
    try:
        for record in records:
            raw_image_path = str(record.get("image_path", "") or "")
            abs_image_path = os.path.abspath(raw_image_path)
            image_path = image_lookup.get(
                abs_image_path,
                manager._to_absolute(raw_image_path),
            )
            if not image_path or not os.path.exists(image_path):
                results.append(
                    {
                        "image_path": raw_image_path,
                        "detected_count": 0,
                        "saved_count": 0,
                        "rejected": [
                            {"part": "", "reason": "image_not_found"}
                        ],
                        "predicted_parts": [],
                        "prediction_scores": {},
                        "prediction_meta": {},
                    }
                )
                continue
            if image_path not in manager.project_data.get("images", []):
                manager.add_images([image_path], save=False)
            results.append(
                _apply_payload(
                    manager,
                    image_path,
                    record.get("payload"),
                    bool(args.only_new),
                    save_drafts_only=bool(args.draft_boxes_only),
                )
            )

        failure_stage = "project_save"
        manager.save_project()
    except Exception as exc:
        manager.rollback_label_journal_transaction(journal_transaction)
        manager._restore_runtime_state(transaction_state)
        applied_label_count = sum(
            int(item.get("saved_count", 0) or 0) for item in results
        )
        _write_json(
            report_path,
            {
                "schema_version": "formica-auto-annotation-report-v1",
                "status": "failed",
                "failure_stage": failure_stage,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "project_input": project_path,
                "project_output": out_project,
                "storage_write_mode": storage_write_mode,
                "prediction_source": (
                    "engine" if args.run_engine else os.path.abspath(args.predictions)
                ),
                "checkpoint_evidence": checkpoint_evidence,
                "engine_prediction_mode": (
                    "locator_boxes"
                    if args.run_engine and args.draft_boxes_only
                    else "full_pipeline" if args.run_engine else None
                ),
                "draft_boxes_only": bool(args.draft_boxes_only),
                "image_count": len(results),
                "applied_label_count": applied_label_count,
                "saved_label_count": 0,
                "save_completed": False,
                "rejected_count": sum(
                    len(item.get("rejected", []) or []) for item in results
                ),
                "results": results,
            },
        )
        raise
    applied_label_count = sum(
        int(item.get("saved_count", 0) or 0) for item in results
    )
    # save_project() is the durable commit point. The legacy recovery journal is
    # supplemental and flushes only after that call returns successfully.
    journal_entry_count = len(manager._label_journal_transaction_entries)
    journal_byte_count = int(manager._label_journal_transaction_bytes)
    journal_error = None
    try:
        journal_committed = manager.commit_label_journal_transaction(
            journal_transaction
        )
    except Exception as exc:
        journal_committed = False
        journal_error = {
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    if manager.is_sqlite_project():
        journal_status = "not_applicable"
    elif journal_entry_count == 0:
        journal_status = "not_required"
    else:
        journal_status = "committed" if journal_committed else "failed"

    warnings = []
    if not journal_committed:
        warning = {
            "code": "legacy_label_journal_commit_failed",
            "message": (
                "The project was saved, but its supplemental legacy recovery "
                "journal was not updated."
            ),
        }
        if journal_error:
            warning.update(journal_error)
        warnings.append(warning)
    report = {
        "schema_version": "formica-auto-annotation-report-v1",
        "status": "passed" if journal_committed else "partial_success",
        "project_input": project_path,
        "project_output": out_project,
        "storage_write_mode": storage_write_mode,
        "sqlite_database": (
            os.path.abspath(manager.current_database_path)
            if manager.is_sqlite_project() and manager.current_database_path
            else None
        ),
        "prediction_source": "engine" if args.run_engine else os.path.abspath(args.predictions),
        "checkpoint_evidence": checkpoint_evidence,
        "engine_prediction_mode": (
            "locator_boxes"
            if args.run_engine and args.draft_boxes_only
            else "full_pipeline" if args.run_engine else None
        ),
        "draft_boxes_only": bool(args.draft_boxes_only),
        "image_count": len(results),
        "applied_label_count": applied_label_count,
        "saved_label_count": applied_label_count,
        "save_completed": True,
        "journal_status": journal_status,
        "journal_entry_count": journal_entry_count,
        "journal_byte_count": journal_byte_count,
        "journal_commit": {
            "status": journal_status,
            "record_count": journal_entry_count,
            "byte_count": journal_byte_count,
            "retryable_after_exit": False,
            "recovery_reference": None,
        },
        "warnings": warnings,
        "rejected_count": sum(len(item.get("rejected", []) or []) for item in results),
        "results": results,
    }
    if not journal_committed:
        report["warning_stage"] = "label_journal_commit"
    _write_json(report_path, report)

    print(f"status={report['status']}")
    print(f"image_count={report['image_count']}")
    print(f"saved_label_count={report['saved_label_count']}")
    print(f"rejected_count={report['rejected_count']}")
    print(f"journal_status={report['journal_status']}")
    print(f"project_output={out_project}")
    print(f"report={report_path}")
    return 0 if journal_committed else 3


if __name__ == "__main__":
    raise SystemExit(main())
