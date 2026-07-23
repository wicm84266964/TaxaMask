from __future__ import annotations

import datetime as _datetime
import os
import re
import secrets
import shutil
from pathlib import Path

import numpy as np

from .file_integrity import FULL_FILE_ALGORITHM, compute_fingerprint
from .location_registry import register_location, resolve_location
from .mesh_export_ledger import MeshExportLedger, MeshExportLedgerError
from .safe_io import atomic_write_json
from .tif_volume_io import load_volume_sidecar, read_volume_metadata, volume_sidecar_exists


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
_UNIT_TO_MM = {
    "m": 1000.0,
    "meter": 1000.0,
    "meters": 1000.0,
    "cm": 10.0,
    "centimeter": 10.0,
    "centimeters": 10.0,
    "mm": 1.0,
    "millimeter": 1.0,
    "millimeters": 1.0,
    "um": 0.001,
    "micrometer": 0.001,
    "micrometers": 0.001,
    "micron": 0.001,
    "microns": 0.001,
    "nm": 0.000001,
    "nanometer": 0.000001,
    "nanometers": 0.000001,
}


class MeshExportError(RuntimeError):
    def __init__(self, code, *, export_id="", record=None):
        self.code = str(code or "mesh_export_error")
        self.export_id = str(export_id or "")
        self.record = dict(record or {})
        super().__init__(self.code)


class MeshExportCancelled(MeshExportError):
    pass


def _now_iso():
    return _datetime.datetime.now(_datetime.timezone.utc).isoformat(
        timespec="microseconds"
    ).replace("+00:00", "Z")


def _new_export_id():
    timestamp = _datetime.datetime.now(_datetime.timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )
    return f"mesh_{timestamp}_{secrets.token_hex(4)}"


def _safe_name(value, fallback):
    text = _SAFE_NAME_RE.sub("_", str(value or "").strip()).strip("._-")
    return (text or fallback)[:120]


def _mesh_dependencies():
    try:
        from skimage import measure
        import trimesh
        from trimesh.smoothing import filter_taubin
    except ImportError as exc:
        raise MeshExportError("mesh_dependencies_unavailable") from exc
    return measure, trimesh, filter_taubin


def _release_mapped_volume(volume):
    mapped = getattr(volume, "_mmap", None)
    if mapped is not None:
        try:
            mapped.close()
        except Exception:
            pass


def spacing_to_millimeters(spacing_zyx, spacing_unit):
    try:
        spacing = [float(value) for value in spacing_zyx]
    except (TypeError, ValueError) as exc:
        raise MeshExportError("mesh_spacing_invalid") from exc
    if len(spacing) != 3 or any(value <= 0 for value in spacing):
        raise MeshExportError("mesh_spacing_invalid")
    unit = str(spacing_unit or "").strip().lower().replace("µ", "u").replace("μ", "u")
    factor = _UNIT_TO_MM.get(unit)
    if factor is None:
        return spacing, "scale_unverified", 1.0
    return [value * factor for value in spacing], "verified", factor


def _manual_truth_record(project_manager, specimen_id, part_id="", reslice_id=""):
    if part_id:
        record = project_manager.part_label_record(
            specimen_id,
            part_id,
            "manual_truth",
            reslice_id=reslice_id,
        )
    else:
        specimen = project_manager.get_specimen(specimen_id, default=None)
        if not isinstance(specimen, dict):
            raise MeshExportError("mesh_specimen_not_found")
        record = (specimen.get("labels") or {}).get("manual_truth") or {}
    if not isinstance(record, dict) or not record.get("path"):
        raise MeshExportError("mesh_manual_truth_missing")
    if str(record.get("role") or "manual_truth") != "manual_truth":
        raise MeshExportError("mesh_source_must_be_manual_truth")
    status = str(record.get("status") or "reviewed")
    if status not in {"reviewed", "verified", "train_ready"}:
        raise MeshExportError("mesh_manual_truth_not_reviewed")
    source_path = project_manager.to_absolute(record["path"])
    if not volume_sidecar_exists(source_path):
        raise MeshExportError("mesh_manual_truth_missing")
    return dict(record), source_path


def _schema_label_names(project_manager, specimen_id, part_id="", reslice_id=""):
    schema_id = ""
    if part_id:
        part = project_manager.get_part(specimen_id, part_id, default=None) or {}
        training = part.get("training") if isinstance(part, dict) else {}
        schema_id = str((training or {}).get("label_schema_id") or "")
        if reslice_id:
            reslice = project_manager.get_part_reslice(
                specimen_id,
                part_id,
                reslice_id,
                default=None,
            ) or {}
            schema_id = str(
                (reslice.get("training") or {}).get("label_schema_id")
                or schema_id
            )
    if not schema_id:
        schemas = [
            item
            for item in project_manager.project_data.get("label_schemas", []) or []
            if isinstance(item, dict)
        ]
        if len(schemas) == 1:
            schema_id = str(schemas[0].get("schema_id") or "")
    schema = project_manager.get_label_schema(schema_id, default=None) or {}
    names = {}
    for item in schema.get("labels", []) or []:
        if not isinstance(item, dict):
            continue
        try:
            label_id = int(item.get("id"))
        except (TypeError, ValueError):
            continue
        names[label_id] = str(
            item.get("display_name") or item.get("name") or f"label_{label_id}"
        )
    return names


def reviewed_mesh_source_summary(
    project_manager,
    specimen_id,
    *,
    part_id="",
    reslice_id="",
    cancel_check=None,
    progress_callback=None,
):
    record, source_path = _manual_truth_record(
        project_manager,
        specimen_id,
        part_id=part_id,
        reslice_id=reslice_id,
    )
    metadata = read_volume_metadata(source_path)
    volume = load_volume_sidecar(source_path, mmap_mode="r")
    counts = {}
    try:
        total = int(volume.shape[0])
        for index in range(total):
            if cancel_check and cancel_check():
                raise MeshExportCancelled("mesh_source_scan_cancelled")
            values, value_counts = np.unique(volume[index], return_counts=True)
            for value, count in zip(values.tolist(), value_counts.tolist()):
                label_id = int(value)
                if label_id > 0:
                    counts[label_id] = counts.get(label_id, 0) + int(count)
            if progress_callback:
                progress_callback(index + 1, total, "scan_labels")
        shape_zyx = [int(value) for value in volume.shape]
    finally:
        _release_mapped_volume(volume)
    names = _schema_label_names(
        project_manager,
        specimen_id,
        part_id=part_id,
        reslice_id=reslice_id,
    )
    spacing_mm, scale_status, conversion_factor = spacing_to_millimeters(
        metadata.get("spacing_zyx") or record.get("spacing_zyx"),
        metadata.get("spacing_unit") or record.get("spacing_unit"),
    )
    return {
        "specimen_id": str(specimen_id),
        "part_id": str(part_id or ""),
        "reslice_id": str(reslice_id or ""),
        "source_relative_path": project_manager.to_relative(source_path),
        "shape_zyx": shape_zyx,
        "spacing_zyx": [
            float(value) for value in metadata.get("spacing_zyx", [])
        ],
        "spacing_unit": str(metadata.get("spacing_unit") or "unknown"),
        "spacing_zyx_mm": spacing_mm,
        "unit_conversion_factor": conversion_factor,
        "scale_status": scale_status,
        "labels": [
            {
                "label_id": label_id,
                "label_name": names.get(label_id, f"label_{label_id}"),
                "voxel_count": counts[label_id],
            }
            for label_id in sorted(counts)
        ],
    }


def _label_bbox_zyx(volume, label_id, cancel_check=None):
    minimum = [None, None, None]
    maximum = [None, None, None]
    for z_index in range(int(volume.shape[0])):
        if cancel_check and cancel_check():
            raise MeshExportCancelled("mesh_export_cancelled")
        y_indices, x_indices = np.nonzero(volume[z_index] == label_id)
        if not len(y_indices):
            continue
        values_min = [z_index, int(y_indices.min()), int(x_indices.min())]
        values_max = [z_index + 1, int(y_indices.max()) + 1, int(x_indices.max()) + 1]
        for axis in range(3):
            minimum[axis] = (
                values_min[axis]
                if minimum[axis] is None
                else min(minimum[axis], values_min[axis])
            )
            maximum[axis] = (
                values_max[axis]
                if maximum[axis] is None
                else max(maximum[axis], values_max[axis])
            )
    if minimum[0] is None:
        return None
    return tuple(slice(minimum[axis], maximum[axis]) for axis in range(3))


def _mesh_quality(mesh):
    components = mesh.split(only_watertight=False)
    return {
        "vertex_count": int(len(mesh.vertices)),
        "face_count": int(len(mesh.faces)),
        "bounds_xyz_mm": np.asarray(mesh.bounds, dtype=np.float64).tolist(),
        "component_count": int(len(components)),
        "watertight": bool(mesh.is_watertight),
    }


def label_mesh_from_volume(
    volume,
    label_id,
    *,
    spacing_zyx_mm,
    cancel_check=None,
):
    measure, trimesh, _filter_taubin = _mesh_dependencies()
    bbox = _label_bbox_zyx(volume, int(label_id), cancel_check=cancel_check)
    if bbox is None:
        raise MeshExportError("mesh_label_empty")
    binary = np.asarray(volume[bbox] == int(label_id), dtype=np.uint8)
    padded = np.pad(binary, 1, mode="constant", constant_values=0)
    vertices_zyx, faces, _normals, _values = measure.marching_cubes(
        padded,
        level=0.5,
        spacing=tuple(float(value) for value in spacing_zyx_mm),
        allow_degenerate=False,
    )
    origin_zyx = np.asarray(
        [bbox[axis].start - 1 for axis in range(3)],
        dtype=np.float64,
    ) * np.asarray(spacing_zyx_mm, dtype=np.float64)
    vertices_zyx = np.asarray(vertices_zyx, dtype=np.float64) + origin_zyx
    vertices_xyz = vertices_zyx[:, [2, 1, 0]]
    mesh = trimesh.Trimesh(
        vertices=vertices_xyz,
        faces=np.asarray(faces, dtype=np.int64),
        process=False,
        validate=False,
    )
    if len(mesh.faces) == 0:
        raise MeshExportError("mesh_surface_empty")
    return mesh, bbox


def smoothed_preview_mesh(mesh, iterations=10):
    _measure, _trimesh, filter_taubin = _mesh_dependencies()
    try:
        iterations = int(iterations)
    except (TypeError, ValueError) as exc:
        raise MeshExportError("mesh_smoothing_iterations_invalid") from exc
    if iterations < 1 or iterations > 100:
        raise MeshExportError("mesh_smoothing_iterations_invalid")
    preview = mesh.copy()
    filter_taubin(
        preview,
        lamb=0.5,
        nu=0.53,
        iterations=iterations,
    )
    return preview


def _atomic_publish_stl(mesh, final_path):
    _measure, trimesh, _filter_taubin = _mesh_dependencies()
    final_path = Path(final_path)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    if final_path.exists():
        raise MeshExportError("mesh_output_exists")
    temporary = final_path.with_name(
        f".{final_path.name}.tmp_{secrets.token_hex(6)}"
    )
    payload = mesh.export(file_type="stl")
    if not isinstance(payload, (bytes, bytearray)):
        payload = bytes(payload)
    try:
        with open(temporary, "xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        reopened = trimesh.load_mesh(
            temporary,
            file_type="stl",
            process=False,
        )
        if int(len(reopened.faces)) != int(len(mesh.faces)):
            raise MeshExportError("mesh_stl_reopen_face_mismatch")
        if not np.allclose(
            np.asarray(reopened.bounds),
            np.asarray(mesh.bounds),
            rtol=1e-5,
            atol=1e-7,
        ):
            raise MeshExportError("mesh_stl_reopen_bounds_mismatch")
        try:
            os.link(temporary, final_path, follow_symlinks=False)
        except (NotImplementedError, TypeError):
            os.rename(temporary, final_path)
        else:
            os.unlink(temporary)
        return compute_fingerprint(final_path, FULL_FILE_ALGORITHM)
    except Exception:
        try:
            if temporary.exists():
                temporary.unlink()
        except OSError:
            pass
        raise


def _item_record(
    export_id,
    label_id,
    label_name,
    kind,
    relative_path,
    mesh,
    fingerprint,
    scale_status,
    processing,
):
    quality = _mesh_quality(mesh)
    return {
        "artifact_id": _safe_name(f"{kind}_label_{label_id}", "mesh_item"),
        "label_id": int(label_id),
        "label_name": str(label_name),
        "kind": kind,
        "relative_path": str(relative_path).replace("\\", "/"),
        "size_bytes": int(fingerprint["size_bytes"]),
        "hash_algorithm": str(fingerprint["hash_algorithm"]),
        "digest": str(fingerprint["digest"]),
        **quality,
        "scale_status": scale_status,
        "processing": dict(processing),
    }


def _diagnostic(output_root, export_id, code, stage):
    try:
        reports = Path(output_root) / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        path = reports / "diagnostic.json"
        payload = {
            "schema_version": "taxamask_mesh_export_diagnostic_v1",
            "export_id": export_id,
            "status": "incomplete",
            "error_code": str(code or "mesh_export_failed"),
            "error_stage": str(stage or "unknown"),
        }
        atomic_write_json(path, payload, indent=2, ensure_ascii=False)
    except Exception:
        pass


def export_reviewed_label_meshes(
    project_manager,
    specimen_id,
    target_directory,
    *,
    label_ids,
    part_id="",
    reslice_id="",
    label_names=None,
    preview_smoothing=False,
    smoothing_iterations=10,
    cancel_check=None,
    progress_callback=None,
    retry_of=None,
):
    if not project_manager.is_sqlite_project():
        raise MeshExportError("mesh_export_requires_sqlite_project")
    clean_label_ids = sorted({int(value) for value in label_ids if int(value) > 0})
    if not clean_label_ids:
        raise MeshExportError("mesh_export_requires_labels")
    target_directory = Path(target_directory).resolve()
    if not target_directory.is_dir():
        raise MeshExportError("mesh_target_directory_missing")
    source_record, source_path = _manual_truth_record(
        project_manager,
        specimen_id,
        part_id=part_id,
        reslice_id=reslice_id,
    )
    source_fingerprint = compute_fingerprint(
        source_path,
        progress_callback=(
            (lambda done, total: progress_callback(done, total, "hash_source"))
            if progress_callback
            else None
        ),
        cancel_check=cancel_check,
    )
    metadata = read_volume_metadata(source_path)
    spacing_mm, scale_status, conversion_factor = spacing_to_millimeters(
        metadata.get("spacing_zyx") or source_record.get("spacing_zyx"),
        metadata.get("spacing_unit") or source_record.get("spacing_unit"),
    )
    export_id = _new_export_id()
    output_relative = f"mesh_export_{export_id}"
    output_root = target_directory / output_relative
    location_ref = register_location(
        target_directory,
        entry_kind="directory",
        database_path=getattr(
            project_manager,
            "location_registry_database_path",
            None,
        ),
    )
    project_id = str(project_manager.project_data.get("project_id") or "")
    data_version_id = str(
        project_manager.project_data.get("project_data_version_id") or ""
    )
    names = _schema_label_names(
        project_manager,
        specimen_id,
        part_id=part_id,
        reslice_id=reslice_id,
    )
    names.update({int(key): str(value) for key, value in (label_names or {}).items()})
    requested_labels = [
        {
            "label_id": label_id,
            "label_name": names.get(label_id, f"label_{label_id}"),
        }
        for label_id in clean_label_ids
    ]
    ledger = MeshExportLedger(project_manager.current_database_path)
    try:
        ledger.create_pending(
            {
                "export_id": export_id,
                "retry_of": retry_of,
                "project_id": project_id,
                "specimen_id": specimen_id,
                "part_id": part_id,
                "reslice_id": reslice_id,
                "source_data_version_id": data_version_id,
                "target_location_ref": location_ref,
                "target_relative_path": output_relative,
                "source_relative_path": project_manager.to_relative(source_path),
                "source_entry_kind": source_fingerprint["entry_kind"],
                "source_size_bytes": source_fingerprint["size_bytes"],
                "source_hash_algorithm": source_fingerprint["hash_algorithm"],
                "source_digest": source_fingerprint["digest"],
                "source_hashed_at": _now_iso(),
                "coordinates": {
                    "source_axis_order": "zyx",
                    "mesh_axis_order": "xyz",
                    "spacing_zyx": [
                        float(value)
                        for value in metadata.get("spacing_zyx", [])
                    ],
                    "spacing_unit": str(
                        metadata.get("spacing_unit") or "unknown"
                    ),
                    "spacing_zyx_mm": spacing_mm,
                    "output_unit": "millimeter",
                    "unit_conversion_factor": conversion_factor,
                    "axis_transform": [
                        [0, 0, 1, 0],
                        [0, 1, 0, 0],
                        [1, 0, 0, 0],
                        [0, 0, 0, 1],
                    ],
                    "scale_status": scale_status,
                },
                "requested_labels": requested_labels,
                "options": {
                    "preview_smoothing": bool(preview_smoothing),
                    "smoothing_iterations": int(smoothing_iterations),
                },
            }
        )
    except MeshExportLedgerError as exc:
        raise MeshExportError(str(exc)) from exc
    stage = "prepare_output"
    volume = None
    try:
        ledger.mark_running(export_id)
        output_root.mkdir(parents=False, exist_ok=False)
        (output_root / "raw").mkdir()
        if preview_smoothing:
            (output_root / "preview").mkdir()
        volume = load_volume_sidecar(source_path, mmap_mode="r")
        total_steps = len(clean_label_ids) * (2 if preview_smoothing else 1)
        completed_steps = 0
        for label_id in clean_label_ids:
            if cancel_check and cancel_check():
                raise MeshExportCancelled("mesh_export_cancelled")
            label_name = names.get(label_id, f"label_{label_id}")
            stage = f"label_{label_id}_marching_cubes"
            mesh, _bbox = label_mesh_from_volume(
                volume,
                label_id,
                spacing_zyx_mm=spacing_mm,
                cancel_check=cancel_check,
            )
            stem = "_".join(
                (
                    _safe_name(specimen_id, "specimen"),
                    f"label_{label_id}",
                    _safe_name(label_name, f"label_{label_id}"),
                )
            )
            raw_relative = f"raw/{stem}.stl"
            stage = f"label_{label_id}_publish_raw"
            raw_fingerprint = _atomic_publish_stl(
                mesh,
                output_root / raw_relative,
            )
            ledger.add_item(
                export_id,
                _item_record(
                    export_id,
                    label_id,
                    label_name,
                    "raw",
                    raw_relative,
                    mesh,
                    raw_fingerprint,
                    scale_status,
                    {
                        "smoothed": False,
                        "filled_holes": False,
                        "removed_components": False,
                    },
                ),
            )
            completed_steps += 1
            if progress_callback:
                progress_callback(completed_steps, total_steps, f"raw_label_{label_id}")

            if preview_smoothing:
                stage = f"label_{label_id}_smooth_preview"
                preview = smoothed_preview_mesh(
                    mesh,
                    iterations=smoothing_iterations,
                )
                raw_quality = _mesh_quality(mesh)
                preview_quality = _mesh_quality(preview)
                preview_relative = f"preview/{stem}_smoothed_preview.stl"
                preview_fingerprint = _atomic_publish_stl(
                    preview,
                    output_root / preview_relative,
                )
                ledger.add_item(
                    export_id,
                    _item_record(
                        export_id,
                        label_id,
                        label_name,
                        "preview",
                        preview_relative,
                        preview,
                        preview_fingerprint,
                        scale_status,
                        {
                            "smoothed": True,
                            "method": "taubin",
                            "iterations": int(smoothing_iterations),
                            "lambda": 0.5,
                            "nu": 0.53,
                            "filled_holes": False,
                            "removed_components": False,
                            "source_raw_artifact_id": f"raw_label_{label_id}",
                            "metric_delta_from_raw": {
                                "vertex_count": preview_quality["vertex_count"]
                                - raw_quality["vertex_count"],
                                "face_count": preview_quality["face_count"]
                                - raw_quality["face_count"],
                                "bounds_xyz_mm": (
                                    np.asarray(preview_quality["bounds_xyz_mm"])
                                    - np.asarray(raw_quality["bounds_xyz_mm"])
                                ).tolist(),
                            },
                        },
                    ),
                )
                completed_steps += 1
                if progress_callback:
                    progress_callback(
                        completed_steps,
                        total_steps,
                        f"preview_label_{label_id}",
                    )

        stage = "verify_source"
        source_after = compute_fingerprint(source_path)
        if any(
            source_after.get(key) != source_fingerprint.get(key)
            for key in ("entry_kind", "size_bytes", "hash_algorithm", "digest")
        ):
            raise MeshExportError("mesh_source_changed_during_export")
        record = ledger.load(export_id)
        stage = "verify_stl"
        for item in record["items"]:
            fingerprint = compute_fingerprint(
                output_root / item["relative_path"],
                FULL_FILE_ALGORITHM,
            )
            if any(
                fingerprint.get(key) != item.get(key)
                for key in ("size_bytes", "hash_algorithm", "digest")
            ):
                raise MeshExportError("mesh_stl_post_publish_mismatch")
        return ledger.finish(export_id, "complete")
    except MeshExportCancelled as exc:
        _diagnostic(output_root, export_id, exc.code, stage)
        return ledger.finish(
            export_id,
            "incomplete",
            error_code=exc.code,
            error_summary=exc.code,
            error_stage=stage,
            recoverable=True,
            recovery_action="retry_or_safe_cleanup",
        )
    except Exception as exc:
        code = str(getattr(exc, "code", "") or type(exc).__name__)
        _diagnostic(output_root, export_id, code, stage)
        status = "incomplete" if output_root.exists() else "failed"
        record = ledger.finish(
            export_id,
            status,
            error_code=code,
            error_summary=code,
            error_stage=stage,
            recoverable=True,
            recovery_action="verify_retry_or_safe_cleanup",
        )
        raise MeshExportError(code, export_id=export_id, record=record) from exc
    finally:
        _release_mapped_volume(volume)


def verify_mesh_export(project_manager, export_id):
    ledger = MeshExportLedger(project_manager.current_database_path)
    record = ledger.load(export_id)
    issues = []
    try:
        parent = resolve_location(
            record["target_location_ref"],
            expected_kind="directory",
            database_path=getattr(
                project_manager,
                "location_registry_database_path",
                None,
            ),
        )
        output_root = parent / record["target_relative_path"]
    except Exception:
        output_root = None
        issues.append({"reason": "target_location_unavailable"})
    source_path = project_manager.to_absolute(record["source_relative_path"])
    try:
        source = compute_fingerprint(source_path)
        if any(
            source.get(key) != record.get(f"source_{key}", record.get(key))
            for key in ("size_bytes", "hash_algorithm", "digest")
        ):
            issues.append({"reason": "source_digest_mismatch"})
    except Exception:
        issues.append({"reason": "source_unavailable"})
    if output_root is not None:
        expected_kinds = {"raw"}
        if bool((record.get("options") or {}).get("preview_smoothing")):
            expected_kinds.add("preview")
        expected_items = {
            (int(label["label_id"]), kind)
            for label in record.get("requested_labels", [])
            for kind in expected_kinds
        }
        recorded_items = {
            (int(item["label_id"]), str(item["kind"]))
            for item in record["items"]
        }
        for label_id, kind in sorted(expected_items - recorded_items):
            issues.append(
                {
                    "artifact_id": f"{kind}_label_{label_id}",
                    "reason": "stl_not_recorded",
                }
            )
        for item in record["items"]:
            try:
                fingerprint = compute_fingerprint(
                    output_root / item["relative_path"],
                    FULL_FILE_ALGORITHM,
                )
                if any(
                    fingerprint.get(key) != item.get(key)
                    for key in ("size_bytes", "hash_algorithm", "digest")
                ):
                    issues.append(
                        {
                            "artifact_id": item["artifact_id"],
                            "reason": "stl_digest_mismatch",
                        }
                    )
            except Exception:
                issues.append(
                    {
                        "artifact_id": item["artifact_id"],
                        "reason": "stl_unavailable",
                    }
                )
    if issues:
        if record["status"] == "complete":
            return ledger.add_review(
                export_id,
                "needs_attention",
                error_code="mesh_export_verification_failed",
                summary="One or more mesh artifacts no longer match the completed record.",
                details={"issues": issues},
            )
        if record["status"] == "incomplete":
            return ledger.finish(
                export_id,
                "incomplete",
                error_code="mesh_export_verification_failed",
                error_summary="mesh_export_verification_failed",
                error_stage="verify",
                recoverable=True,
                recovery_action="retry_or_safe_cleanup",
            )
        return ledger.add_review(
            export_id,
            "needs_attention",
            error_code="mesh_export_verification_failed",
            summary="The failed export is still incomplete.",
            details={"issues": issues},
        )
    if record["status"] == "incomplete":
        return ledger.finish(export_id, "complete")
    return ledger.add_review(
        export_id,
        "verified",
        summary="Source and STL fingerprints match the SQLite record.",
    )


def safe_cleanup_incomplete_mesh_export(project_manager, export_id):
    ledger = MeshExportLedger(project_manager.current_database_path)
    record = ledger.load(export_id)
    if record["status"] not in {"incomplete", "failed"}:
        raise MeshExportError("mesh_cleanup_requires_incomplete_export")
    parent = resolve_location(
        record["target_location_ref"],
        expected_kind="directory",
        database_path=getattr(
            project_manager,
            "location_registry_database_path",
            None,
        ),
    )
    target = (parent / record["target_relative_path"]).resolve()
    if target.parent != parent.resolve() or not target.name.startswith("mesh_export_mesh_"):
        raise MeshExportError("mesh_cleanup_target_invalid")
    if target.exists():
        shutil.rmtree(target)
    return ledger.add_review(
        export_id,
        "needs_attention",
        error_code="mesh_export_safely_cleaned",
        summary="Incomplete external mesh files were removed by explicit user action.",
        details={"action": "safe_cleanup"},
    )


__all__ = [
    "MeshExportCancelled",
    "MeshExportError",
    "export_reviewed_label_meshes",
    "label_mesh_from_volume",
    "reviewed_mesh_source_summary",
    "safe_cleanup_incomplete_mesh_export",
    "smoothed_preview_mesh",
    "spacing_to_millimeters",
    "verify_mesh_export",
]
