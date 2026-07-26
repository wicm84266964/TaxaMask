from __future__ import annotations

import datetime as _datetime
import math
import os
import re
import secrets
import stat
from pathlib import Path

import numpy as np

from .file_integrity import FULL_FILE_ALGORITHM, compute_fingerprint
from .location_registry import (
    LocationRegistryError,
    register_location,
    require_safe_existing_path,
    resolve_location,
)
from .mesh_export_ledger import MeshExportLedger, MeshExportLedgerError
from .project_integrity_registry import get_training_baseline_snapshot
from .safe_io import atomic_write_json
from .tif_truth_policy import can_use_role_for_training
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


def spacing_to_millimeters(spacing_zyx, spacing_unit, *, scale_verified=False):
    try:
        spacing = [float(value) for value in spacing_zyx]
    except (TypeError, ValueError) as exc:
        raise MeshExportError("mesh_spacing_invalid") from exc
    if len(spacing) != 3 or any(
        not math.isfinite(value) or value <= 0 for value in spacing
    ):
        raise MeshExportError("mesh_spacing_invalid")
    unit = str(spacing_unit or "").strip().lower().replace("µ", "u").replace("μ", "u")
    factor = _UNIT_TO_MM.get(unit)
    if factor is None or scale_verified is not True:
        return spacing, "scale_unverified", 1.0
    return [value * factor for value in spacing], "verified", factor


def _mesh_coordinate_context(spacing_zyx, spacing_unit, *, scale_verified=False):
    mesh_spacing, scale_status, conversion_factor = spacing_to_millimeters(
        spacing_zyx,
        spacing_unit,
        scale_verified=scale_verified,
    )
    verified = scale_status == "verified"
    context = {
        "mesh_spacing_zyx": mesh_spacing,
        "scale_status": scale_status,
        "unit_conversion_factor": conversion_factor,
        "scale_verified": verified,
        "mesh_purpose": "measurement" if verified else "observation",
        "output_unit": "millimeter" if verified else "unitless",
    }
    if verified:
        context["spacing_zyx_mm"] = mesh_spacing
    return context


def _source_scale_verified(metadata, record):
    if not isinstance(metadata, dict) or not isinstance(record, dict):
        return False
    metadata_unit = str(metadata.get("spacing_unit") or "").strip().lower().replace("µ", "u").replace("μ", "u")
    record_unit = str(record.get("spacing_unit") or "").strip().lower().replace("µ", "u").replace("μ", "u")
    try:
        metadata_spacing = [float(value) for value in (metadata.get("spacing_zyx") or [])]
        record_spacing = [float(value) for value in (record.get("spacing_zyx") or [])]
    except (TypeError, ValueError):
        return False
    return bool(
        metadata.get("scale_verified") is True
        and record.get("scale_verified") is True
        and metadata_unit in _UNIT_TO_MM
        and record_unit in _UNIT_TO_MM
        and math.isclose(_UNIT_TO_MM[metadata_unit], _UNIT_TO_MM[record_unit], rel_tol=0.0, abs_tol=0.0)
        and len(metadata_spacing) == 3
        and len(record_spacing) == 3
        and all(
            math.isfinite(left)
            and math.isfinite(right)
            and left > 0
            and right > 0
            and math.isclose(left, right, rel_tol=1e-6, abs_tol=1e-9)
            for left, right in zip(metadata_spacing, record_spacing)
        )
    )


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
    role = str(record.get("role") or "manual_truth")
    if role != "manual_truth":
        raise MeshExportError("mesh_source_must_be_manual_truth")
    truth_policy = can_use_role_for_training(
        role,
        status=record.get("status"),
        record_exists=True,
        review_audit=record.get("review_audit"),
        training=record.get("training"),
    )
    if not truth_policy:
        raise MeshExportError("mesh_manual_truth_not_reviewed")
    source_path = project_manager.to_absolute(record["path"])
    try:
        source_path = require_safe_existing_path(source_path)
    except LocationRegistryError as exc:
        raise MeshExportError("mesh_manual_truth_path_unsafe") from exc
    if not volume_sidecar_exists(source_path):
        raise MeshExportError("mesh_manual_truth_missing")
    return dict(record), source_path


def _manual_truth_owner_key(specimen_id, part_id="", reslice_id=""):
    if reslice_id:
        return f"reslice.{specimen_id}.{part_id}.{reslice_id}.manual_truth"
    if part_id:
        return f"part.{specimen_id}.{part_id}.manual_truth"
    return f"specimen.{specimen_id}.manual_truth"


def _registry_revision_runtime_path(project_manager, revision):
    location = revision.get("location")
    if not isinstance(location, dict):
        raise MeshExportError("mesh_registry_manual_truth_location_unavailable")
    location_kind = str(location.get("location_kind") or "")
    if location_kind == "managed_relative":
        if str(location.get("path_base") or "") != "project_root":
            raise MeshExportError("mesh_registry_manual_truth_location_unavailable")
        relative_path = str(location.get("relative_path") or "")
        if not relative_path:
            raise MeshExportError("mesh_registry_manual_truth_location_unavailable")
        try:
            return require_safe_existing_path(
                project_manager.to_absolute(relative_path),
                expected_kind=revision.get("entry_kind"),
            )
        except LocationRegistryError as exc:
            raise MeshExportError("mesh_manual_truth_path_unsafe") from exc
    if location_kind == "opaque_ref":
        opaque_ref = str(location.get("opaque_ref") or "")
        if not opaque_ref:
            raise MeshExportError("mesh_registry_manual_truth_location_unavailable")
        try:
            return os.fspath(
                resolve_location(
                    opaque_ref,
                    expected_kind=revision.get("entry_kind"),
                    database_path=getattr(
                        project_manager,
                        "location_registry_database_path",
                        None,
                    ),
                )
            )
        except Exception as exc:
            raise MeshExportError(
                "mesh_registry_manual_truth_location_unavailable"
            ) from exc
    raise MeshExportError("mesh_registry_manual_truth_location_unavailable")


def _require_same_registry_revision_location(
    project_manager,
    source_path,
    revision,
):
    registered_path = _registry_revision_runtime_path(project_manager, revision)
    try:
        entry_kind = str(revision.get("entry_kind") or "")
        require_safe_existing_path(source_path, expected_kind=entry_kind)
        require_safe_existing_path(registered_path, expected_kind=entry_kind)
        same_location = os.path.samefile(source_path, registered_path)
    except LocationRegistryError as exc:
        raise MeshExportError("mesh_manual_truth_path_unsafe") from exc
    except OSError as exc:
        raise MeshExportError(
            "mesh_registry_manual_truth_location_unavailable"
        ) from exc
    if not same_location:
        raise MeshExportError("mesh_registry_manual_truth_location_mismatch")


def _manual_truth_registry_revision(
    project_manager,
    specimen_id,
    *,
    part_id="",
    reslice_id="",
    data_version_id,
):
    clean_version_id = str(data_version_id or "")
    if not clean_version_id:
        raise MeshExportError("mesh_registry_data_version_missing")
    try:
        snapshot = get_training_baseline_snapshot(
            project_manager.current_database_path,
            clean_version_id,
        )
    except Exception as exc:
        raise MeshExportError("mesh_registry_baseline_unavailable") from exc
    project_id = str(project_manager.project_data.get("project_id") or "")
    if str(snapshot.get("project_id") or "") != project_id:
        raise MeshExportError("mesh_registry_project_mismatch")
    if str(snapshot.get("data_version_id") or "") != clean_version_id:
        raise MeshExportError("mesh_registry_data_version_mismatch")
    owner_key = _manual_truth_owner_key(
        specimen_id,
        part_id=part_id,
        reslice_id=reslice_id,
    )
    matches = [
        item
        for item in snapshot.get("files", [])
        if item.get("owner_kind") == "tif_asset"
        and item.get("owner_key") == owner_key
        and item.get("role") == "manual_truth"
    ]
    if not matches:
        raise MeshExportError("mesh_registry_manual_truth_missing")
    if len(matches) != 1:
        raise MeshExportError("mesh_registry_manual_truth_ambiguous")
    expected = matches[0]
    if not str(expected.get("revision_id") or ""):
        raise MeshExportError("mesh_registry_manual_truth_revision_missing")
    if str(expected.get("data_version_id") or "") != clean_version_id:
        raise MeshExportError("mesh_registry_manual_truth_revision_mismatch")
    return expected


def _verify_manual_truth_registry_revision(
    project_manager,
    specimen_id,
    source_path,
    *,
    part_id="",
    reslice_id="",
    cancel_check=None,
    progress_callback=None,
):
    """Verify the selected truth against the current committed Registry revision."""

    data_version_id = str(
        project_manager.project_data.get("project_data_version_id") or ""
    )
    if not data_version_id:
        raise MeshExportError("mesh_registry_data_version_missing")
    try:
        current_snapshot = get_training_baseline_snapshot(
            project_manager.current_database_path
        )
    except Exception as exc:
        raise MeshExportError("mesh_registry_baseline_unavailable") from exc
    if str(current_snapshot.get("data_version_id") or "") != data_version_id:
        raise MeshExportError("mesh_registry_data_version_mismatch")
    expected = _manual_truth_registry_revision(
        project_manager,
        specimen_id,
        part_id=part_id,
        reslice_id=reslice_id,
        data_version_id=data_version_id,
    )
    _require_same_registry_revision_location(
        project_manager,
        source_path,
        expected,
    )
    observed = compute_fingerprint(
        source_path,
        expected["hash_algorithm"],
        progress_callback=progress_callback,
        cancel_check=cancel_check,
    )
    if any(
        observed.get(key) != expected.get(key)
        for key in ("entry_kind", "size_bytes", "hash_algorithm", "digest")
    ):
        raise MeshExportError("mesh_manual_truth_registry_mismatch")
    return expected, observed


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
    _verify_manual_truth_registry_revision(
        project_manager,
        specimen_id,
        source_path,
        part_id=part_id,
        reslice_id=reslice_id,
        cancel_check=cancel_check,
        progress_callback=(
            (
                lambda done, total: progress_callback(
                    done,
                    total,
                    "verify_registry_truth",
                )
            )
            if progress_callback
            else None
        ),
    )
    metadata = read_volume_metadata(source_path)
    volume = load_volume_sidecar(source_path, mmap_mode="r")
    try:
        label_statistics = _scan_label_statistics(
            volume,
            cancel_check=cancel_check,
            progress_callback=progress_callback,
            cancel_code="mesh_source_scan_cancelled",
            progress_stage="scan_labels",
        )
        shape_zyx = [int(value) for value in volume.shape]
    finally:
        _release_mapped_volume(volume)
    names = _schema_label_names(
        project_manager,
        specimen_id,
        part_id=part_id,
        reslice_id=reslice_id,
    )
    coordinates = _mesh_coordinate_context(
        metadata.get("spacing_zyx") or record.get("spacing_zyx"),
        metadata.get("spacing_unit") or record.get("spacing_unit"),
        scale_verified=_source_scale_verified(metadata, record),
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
        **coordinates,
        "labels": [
            {
                "label_id": label_id,
                "label_name": names.get(label_id, f"label_{label_id}"),
                "voxel_count": label_statistics[label_id]["voxel_count"],
                "bbox_zyx": label_statistics[label_id]["bbox_zyx"],
            }
            for label_id in sorted(label_statistics)
        ],
    }


def _scan_label_statistics(
    volume,
    *,
    label_ids=None,
    cancel_check=None,
    progress_callback=None,
    cancel_code="mesh_export_cancelled",
    progress_stage="scan_label_bounds",
    row_chunk_size=128,
):
    selected = (
        {int(value) for value in label_ids if int(value) > 0}
        if label_ids is not None
        else None
    )
    statistics = {}
    depth = int(volume.shape[0])
    height = int(volume.shape[1])
    for z_index in range(depth):
        if cancel_check and cancel_check():
            raise MeshExportCancelled(cancel_code)
        for y_start in range(0, height, max(1, int(row_chunk_size))):
            block = np.asarray(
                volume[z_index, y_start : y_start + row_chunk_size]
            )
            y_indices, x_indices = np.nonzero(block)
            if not len(y_indices):
                continue
            labels = np.asarray(block[y_indices, x_indices])
            positive = labels > 0
            if not np.all(positive):
                y_indices = y_indices[positive]
                x_indices = x_indices[positive]
                labels = labels[positive]
            if not len(labels):
                continue
            values, inverse, counts = np.unique(
                labels,
                return_inverse=True,
                return_counts=True,
            )
            minimum_y = np.full(len(values), block.shape[0], dtype=np.int64)
            maximum_y = np.full(len(values), -1, dtype=np.int64)
            minimum_x = np.full(len(values), block.shape[1], dtype=np.int64)
            maximum_x = np.full(len(values), -1, dtype=np.int64)
            np.minimum.at(minimum_y, inverse, y_indices)
            np.maximum.at(maximum_y, inverse, y_indices)
            np.minimum.at(minimum_x, inverse, x_indices)
            np.maximum.at(maximum_x, inverse, x_indices)
            for value_index, raw_label_id in enumerate(values.tolist()):
                label_id = int(raw_label_id)
                if selected is not None and label_id not in selected:
                    continue
                current = statistics.setdefault(
                    label_id,
                    {
                        "voxel_count": 0,
                        "minimum_zyx": [None, None, None],
                        "maximum_zyx": [None, None, None],
                    },
                )
                current["voxel_count"] += int(counts[value_index])
                values_min = [
                    z_index,
                    y_start + int(minimum_y[value_index]),
                    int(minimum_x[value_index]),
                ]
                values_max = [
                    z_index + 1,
                    y_start + int(maximum_y[value_index]) + 1,
                    int(maximum_x[value_index]) + 1,
                ]
                for axis in range(3):
                    current["minimum_zyx"][axis] = (
                        values_min[axis]
                        if current["minimum_zyx"][axis] is None
                        else min(current["minimum_zyx"][axis], values_min[axis])
                    )
                    current["maximum_zyx"][axis] = (
                        values_max[axis]
                        if current["maximum_zyx"][axis] is None
                        else max(current["maximum_zyx"][axis], values_max[axis])
                    )
        if progress_callback:
            progress_callback(z_index + 1, depth, progress_stage)
    return {
        label_id: {
            "voxel_count": int(item["voxel_count"]),
            "bbox_zyx": [
                [item["minimum_zyx"][axis], item["maximum_zyx"][axis]]
                for axis in range(3)
            ],
        }
        for label_id, item in statistics.items()
    }


def _label_bbox_zyx(volume, label_id, cancel_check=None):
    result = _scan_label_statistics(
        volume,
        label_ids=[label_id],
        cancel_check=cancel_check,
    ).get(int(label_id))
    if not result:
        return None
    return tuple(slice(start, stop) for start, stop in result["bbox_zyx"])


def _mesh_quality(mesh):
    components = mesh.split(only_watertight=False)
    return {
        "vertex_count": int(len(mesh.vertices)),
        "face_count": int(len(mesh.faces)),
        "bounds_xyz": np.asarray(mesh.bounds, dtype=np.float64).tolist(),
        "component_count": int(len(components)),
        "watertight": bool(mesh.is_watertight),
    }


def label_mesh_from_volume(
    volume,
    label_id,
    *,
    spacing_zyx_mm=None,
    mesh_spacing_zyx=None,
    bbox_zyx=None,
    cancel_check=None,
):
    measure, trimesh, _filter_taubin = _mesh_dependencies()
    spacing = mesh_spacing_zyx if mesh_spacing_zyx is not None else spacing_zyx_mm
    if spacing is None:
        raise MeshExportError("mesh_spacing_invalid")
    if bbox_zyx is None:
        bbox = _label_bbox_zyx(volume, int(label_id), cancel_check=cancel_check)
    else:
        try:
            bbox = tuple(
                item if isinstance(item, slice) else slice(int(item[0]), int(item[1]))
                for item in bbox_zyx
            )
        except (TypeError, ValueError, IndexError) as exc:
            raise MeshExportError("mesh_label_bbox_invalid") from exc
        if len(bbox) != 3 or any(
            item.start is None or item.stop is None or item.start >= item.stop
            for item in bbox
        ):
            raise MeshExportError("mesh_label_bbox_invalid")
    if bbox is None:
        raise MeshExportError("mesh_label_empty")
    binary = np.asarray(volume[bbox] == int(label_id), dtype=np.uint8)
    padded = np.pad(binary, 1, mode="constant", constant_values=0)
    vertices_zyx, faces, _normals, _values = measure.marching_cubes(
        padded,
        level=0.5,
        spacing=tuple(float(value) for value in spacing),
        allow_degenerate=False,
    )
    origin_zyx = np.asarray(
        [bbox[axis].start - 1 for axis in range(3)],
        dtype=np.float64,
    ) * np.asarray(spacing, dtype=np.float64)
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


def _safe_output_directory(path):
    try:
        return Path(require_safe_existing_path(path, expected_kind="directory"))
    except LocationRegistryError as exc:
        raise MeshExportError("mesh_output_path_unsafe") from exc


def _ensure_safe_output_directory(path):
    target = Path(os.path.abspath(os.fspath(path)))
    missing = []
    current = target
    while not os.path.lexists(current):
        parent = current.parent
        if parent == current:
            raise MeshExportError("mesh_output_path_unsafe")
        missing.append(current)
        current = parent
    _safe_output_directory(current)
    for directory in reversed(missing):
        try:
            directory.mkdir()
        except FileExistsError:
            pass
        except OSError as exc:
            raise MeshExportError("mesh_output_directory_create_failed") from exc
        _safe_output_directory(directory)
    return _safe_output_directory(target)


def _atomic_publish_stl(mesh, final_path):
    _measure, trimesh, _filter_taubin = _mesh_dependencies()
    final_path = Path(os.path.abspath(os.fspath(final_path)))
    parent = _ensure_safe_output_directory(final_path.parent)
    final_path = parent / final_path.name
    if os.path.lexists(final_path):
        try:
            require_safe_existing_path(final_path)
        except LocationRegistryError as exc:
            raise MeshExportError("mesh_output_path_unsafe") from exc
        raise MeshExportError("mesh_output_exists")
    temporary = final_path.with_name(
        f".{final_path.name}.tmp_{secrets.token_hex(6)}"
    )
    payload = mesh.export(file_type="stl")
    if not isinstance(payload, (bytes, bytearray)):
        payload = bytes(payload)
    try:
        _safe_output_directory(parent)
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        flags |= int(getattr(os, "O_BINARY", 0))
        flags |= int(getattr(os, "O_NOFOLLOW", 0))
        descriptor = os.open(temporary, flags, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            require_safe_existing_path(temporary, expected_kind="file")
        except LocationRegistryError as exc:
            raise MeshExportError("mesh_output_path_unsafe") from exc
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
        _safe_output_directory(parent)
        try:
            require_safe_existing_path(temporary, expected_kind="file")
        except LocationRegistryError as exc:
            raise MeshExportError("mesh_output_path_unsafe") from exc
        if os.path.lexists(final_path):
            raise MeshExportError("mesh_output_exists")
        try:
            os.link(temporary, final_path, follow_symlinks=False)
        except (NotImplementedError, TypeError):
            os.rename(temporary, final_path)
        else:
            os.unlink(temporary)
        try:
            require_safe_existing_path(final_path, expected_kind="file")
        except LocationRegistryError as exc:
            raise MeshExportError("mesh_output_path_unsafe") from exc
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
    output_unit,
    mesh_purpose,
    processing,
):
    quality = _mesh_quality(mesh)
    processing = dict(processing)
    is_preview = kind == "preview"
    item_purpose = "display_preview" if is_preview else mesh_purpose
    measurement_allowed = bool(
        not is_preview
        and item_purpose == "measurement"
        and output_unit == "millimeter"
        and scale_status == "verified"
    )
    processing.update(
        {
            "bounds_xyz": quality["bounds_xyz"],
            "bounds_unit": output_unit,
            "mesh_purpose": item_purpose,
            "measurement_allowed": measurement_allowed,
        }
    )
    if is_preview:
        processing["source_mesh_purpose"] = mesh_purpose
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
        "bounds_unit": output_unit,
        "mesh_purpose": item_purpose,
        "measurement_allowed": measurement_allowed,
        "role": "display_preview" if is_preview else f"{item_purpose}_mesh",
        "scale_status": scale_status,
        "processing": processing,
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
    try:
        target_directory = Path(
            require_safe_existing_path(
                target_directory,
                expected_kind="directory",
            )
        )
    except LocationRegistryError as exc:
        if getattr(exc, "code", "") == "location_path_missing":
            raise MeshExportError("mesh_target_directory_missing") from exc
        raise MeshExportError("mesh_target_directory_unsafe") from exc
    source_record, source_path = _manual_truth_record(
        project_manager,
        specimen_id,
        part_id=part_id,
        reslice_id=reslice_id,
    )
    _source_revision, source_fingerprint = _verify_manual_truth_registry_revision(
        project_manager,
        specimen_id,
        source_path,
        part_id=part_id,
        reslice_id=reslice_id,
        progress_callback=(
            (lambda done, total: progress_callback(done, total, "hash_source"))
            if progress_callback
            else None
        ),
        cancel_check=cancel_check,
    )
    metadata = read_volume_metadata(source_path)
    coordinate_context = _mesh_coordinate_context(
        metadata.get("spacing_zyx") or source_record.get("spacing_zyx"),
        metadata.get("spacing_unit") or source_record.get("spacing_unit"),
        scale_verified=_source_scale_verified(metadata, source_record),
    )
    mesh_spacing = coordinate_context["mesh_spacing_zyx"]
    scale_status = coordinate_context["scale_status"]
    output_unit = coordinate_context["output_unit"]
    mesh_purpose = coordinate_context["mesh_purpose"]
    export_id = _new_export_id()
    output_relative = f"mesh_export_{export_id}_{mesh_purpose}"
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
                    **coordinate_context,
                    "axis_transform": [
                        [0, 0, 1, 0],
                        [0, 1, 0, 0],
                        [1, 0, 0, 0],
                        [0, 0, 0, 1],
                    ],
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
        mesh_steps = len(clean_label_ids) * (2 if preview_smoothing else 1)
        scan_steps = int(volume.shape[0])
        total_steps = scan_steps + mesh_steps
        stage = "scan_label_bounds"
        label_statistics = _scan_label_statistics(
            volume,
            label_ids=clean_label_ids,
            cancel_check=cancel_check,
            progress_callback=(
                (
                    lambda done, _total, scan_stage: progress_callback(
                        done,
                        total_steps,
                        scan_stage,
                    )
                )
                if progress_callback
                else None
            ),
        )
        missing_labels = [
            label_id for label_id in clean_label_ids if label_id not in label_statistics
        ]
        if missing_labels:
            raise MeshExportError("mesh_label_empty")
        completed_steps = scan_steps
        for label_id in clean_label_ids:
            if cancel_check and cancel_check():
                raise MeshExportCancelled("mesh_export_cancelled")
            label_name = names.get(label_id, f"label_{label_id}")
            stage = f"label_{label_id}_marching_cubes"
            mesh, _bbox = label_mesh_from_volume(
                volume,
                label_id,
                mesh_spacing_zyx=mesh_spacing,
                bbox_zyx=label_statistics[label_id]["bbox_zyx"],
                cancel_check=cancel_check,
            )
            stem = "_".join(
                (
                    _safe_name(specimen_id, "specimen"),
                    f"label_{label_id}",
                    _safe_name(label_name, f"label_{label_id}"),
                    f"{mesh_purpose}_{'mm' if output_unit == 'millimeter' else 'unitless'}",
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
                    output_unit,
                    mesh_purpose,
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
                        output_unit,
                        mesh_purpose,
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
                                "bounds_xyz": (
                                    np.asarray(preview_quality["bounds_xyz"])
                                    - np.asarray(raw_quality["bounds_xyz"])
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
        stage = "commit_complete"
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
        recovery_action = (
            "verify_complete_or_retry_or_safe_cleanup"
            if stage == "commit_complete"
            else "verify_retry_or_safe_cleanup"
        )
        record = ledger.finish(
            export_id,
            status,
            error_code=code,
            error_summary=code,
            error_stage=stage,
            recoverable=True,
            recovery_action=recovery_action,
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
        output_root = Path(
            require_safe_existing_path(
                parent / record["target_relative_path"],
                expected_kind="directory",
            )
        )
    except LocationRegistryError:
        output_root = None
        issues.append({"reason": "target_path_unsafe"})
    except Exception:
        output_root = None
        issues.append({"reason": "target_location_unavailable"})
    try:
        source_revision = _manual_truth_registry_revision(
            project_manager,
            record["specimen_id"],
            part_id=record.get("part_id", ""),
            reslice_id=record.get("reslice_id", ""),
            data_version_id=record["source_data_version_id"],
        )
        if any(
            source_revision.get(key)
            != record.get(f"source_{key}", record.get(key))
            for key in ("entry_kind", "size_bytes", "hash_algorithm", "digest")
        ):
            issues.append({"reason": "source_revision_mismatch"})
        source_path = _registry_revision_runtime_path(
            project_manager,
            source_revision,
        )
        source_path = require_safe_existing_path(
            source_path,
            expected_kind=source_revision["entry_kind"],
        )
        source = compute_fingerprint(
            source_path,
            record["source_hash_algorithm"],
        )
        if any(
            source.get(key) != record.get(f"source_{key}", record.get(key))
            for key in ("entry_kind", "size_bytes", "hash_algorithm", "digest")
        ):
            issues.append({"reason": "source_digest_mismatch"})
    except LocationRegistryError:
        issues.append({"reason": "source_path_unsafe"})
    except MeshExportError as exc:
        issues.append({"reason": exc.code})
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
                stl_path = require_safe_existing_path(
                    output_root / item["relative_path"],
                    expected_kind="file",
                )
                fingerprint = compute_fingerprint(
                    stl_path,
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
            except LocationRegistryError:
                issues.append(
                    {
                        "artifact_id": item["artifact_id"],
                        "reason": "stl_path_unsafe",
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
        if record["status"] in {"pending", "running", "incomplete"}:
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
    if record["status"] in {"pending", "running", "incomplete"}:
        return ledger.finish(export_id, "complete")
    return ledger.add_review(
        export_id,
        "verified",
        summary="Source and STL fingerprints match the SQLite record.",
    )


def recover_interrupted_mesh_exports(
    project_manager,
    *,
    specimen_id="",
    part_id=None,
    reslice_id=None,
    cancel_check=None,
    progress_callback=None,
):
    ledger = MeshExportLedger(project_manager.current_database_path)
    candidates = ledger.list_exports(
        specimen_id=specimen_id,
        part_id=part_id,
        reslice_id=reslice_id,
        statuses=("pending", "running", "incomplete"),
    )
    interrupted = [
        record
        for record in candidates
        if record["status"] in {"pending", "running"}
        or (
            record["status"] == "incomplete"
            and bool(record.get("recoverable"))
            and record.get("recovery_action")
            == "verify_complete_or_retry_or_safe_cleanup"
        )
    ]
    recovered = []
    total = len(interrupted)
    for index, record in enumerate(interrupted):
        if cancel_check and cancel_check():
            raise MeshExportCancelled("mesh_recovery_cancelled")
        recovered.append(
            verify_mesh_export(project_manager, record["export_id"])
        )
        if progress_callback:
            progress_callback(index + 1, total, "verify_interrupted_export")
    return {
        "checked_count": total,
        "complete_count": sum(
            item.get("status") == "complete" for item in recovered
        ),
        "incomplete_count": sum(
            item.get("status") == "incomplete" for item in recovered
        ),
        "records": recovered,
    }


def _mesh_cleanup_identity(path, *, expected_kind=None):
    safe_path = Path(
        require_safe_existing_path(path, expected_kind=expected_kind)
    )
    result = os.lstat(safe_path)
    attributes = int(getattr(result, "st_file_attributes", 0) or 0)
    reparse_flag = int(
        getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400) or 0x400
    )
    if stat.S_ISLNK(result.st_mode) or bool(attributes & reparse_flag):
        raise MeshExportError("mesh_cleanup_target_unsafe")
    if not (stat.S_ISREG(result.st_mode) or stat.S_ISDIR(result.st_mode)):
        raise MeshExportError("mesh_cleanup_target_unsafe")
    if expected_kind == "file" and not stat.S_ISREG(result.st_mode):
        raise MeshExportError("mesh_cleanup_target_unsafe")
    if expected_kind == "directory" and not stat.S_ISDIR(result.st_mode):
        raise MeshExportError("mesh_cleanup_target_unsafe")
    return safe_path, result, (
        int(result.st_dev),
        int(result.st_ino),
        int(stat.S_IFMT(result.st_mode)),
    )


def _require_unchanged_mesh_cleanup_entry(path, expected_kind, identity):
    safe_path, _result, current_identity = _mesh_cleanup_identity(
        path,
        expected_kind=expected_kind,
    )
    if current_identity != identity:
        raise MeshExportError("mesh_cleanup_target_changed")
    return safe_path


def _remove_safe_mesh_export_tree(target):
    root, _root_stat, root_identity = _mesh_cleanup_identity(
        target,
        expected_kind="directory",
    )
    files = []
    directories = []
    stack = [root]
    while stack:
        current = Path(
            require_safe_existing_path(
                stack.pop(),
                expected_kind="directory",
            )
        )
        with os.scandir(current) as entries:
            for entry in entries:
                child, result, identity = _mesh_cleanup_identity(entry.path)
                if stat.S_ISREG(result.st_mode):
                    files.append((child, identity))
                elif stat.S_ISDIR(result.st_mode):
                    directories.append((child, identity))
                    stack.append(child)
                else:
                    raise MeshExportError("mesh_cleanup_target_unsafe")

    for path, identity in files:
        safe_path = _require_unchanged_mesh_cleanup_entry(
            path,
            "file",
            identity,
        )
        os.unlink(safe_path)
    for path, identity in sorted(
        directories,
        key=lambda item: len(item[0].parts),
        reverse=True,
    ):
        safe_path = _require_unchanged_mesh_cleanup_entry(
            path,
            "directory",
            identity,
        )
        os.rmdir(safe_path)
    safe_root = _require_unchanged_mesh_cleanup_entry(
        root,
        "directory",
        root_identity,
    )
    os.rmdir(safe_root)


def safe_cleanup_incomplete_mesh_export(project_manager, export_id):
    ledger = MeshExportLedger(project_manager.current_database_path)
    record = ledger.load(export_id)
    if record["status"] not in {"incomplete", "failed"}:
        raise MeshExportError("mesh_cleanup_requires_incomplete_export")
    relative = record.get("target_relative_path")
    if (
        not isinstance(relative, str)
        or not relative
        or "/" in relative
        or "\\" in relative
        or relative in {".", ".."}
        or not relative.startswith("mesh_export_mesh_")
    ):
        raise MeshExportError("mesh_cleanup_target_invalid")
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
        safe_parent = Path(
            require_safe_existing_path(
                parent,
                expected_kind="directory",
            )
        )
        target = Path(
            require_safe_existing_path(
                safe_parent / relative,
                expected_kind="directory",
            )
        )
        _remove_safe_mesh_export_tree(target)
    except LocationRegistryError as exc:
        raise MeshExportError("mesh_cleanup_target_unsafe") from exc
    except MeshExportError:
        raise
    except OSError as exc:
        raise MeshExportError("mesh_cleanup_failed") from exc
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
    "recover_interrupted_mesh_exports",
    "reviewed_mesh_source_summary",
    "safe_cleanup_incomplete_mesh_export",
    "smoothed_preview_mesh",
    "spacing_to_millimeters",
    "verify_mesh_export",
]
