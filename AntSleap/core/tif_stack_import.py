import copy
import os
import re
import shutil
from datetime import datetime

import numpy as np
import tifffile

from .safe_io import atomic_write_json
from .tif_label_guard import can_write_label_role
from .tif_materials import write_material_map
from .tif_project import TifProjectManager
from .tif_volume_io import create_empty_label_sidecar_like, create_volume_sidecar_memmap
from .tif_write_guard import WriteIntent, ensure_write_allowed


TIF_STACK_IMPORT_REPORT_SCHEMA_VERSION = "ant3d_tif_stack_import_report_v1"
TIF_STACK_IMPORT_ADAPTER_VERSION = "tif_stack_import_adapter_v1"
TIF_STACK_METADATA_IMPORT_ADAPTER_VERSION = "tif_stack_metadata_import_adapter_v1"
TIF_SLICE_SERIES_IMPORT_ADAPTER_VERSION = "tif_slice_series_import_adapter_v1"
TIF_SLICE_SERIES_MANIFEST_SCHEMA_VERSION = "ant3d_tif_slice_series_manifest_v1"
TIF_SLICE_SERIES_ORDERING = "natural_filename_v1"


def _now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _maximum_material_id(material_map):
    maximum = 0
    for item in (material_map or {}).get("materials", []) if isinstance(material_map, dict) else []:
        try:
            maximum = max(maximum, int(item.get("id", 0)))
        except (AttributeError, TypeError, ValueError):
            continue
    return maximum


def _safe_filename(value):
    text = str(value or "").strip()
    clean = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in text)
    return clean.strip("_") or "source.tif"


def _require_guard(result, prefix):
    if result:
        return result
    reason = getattr(result, "reason", "denied")
    details = getattr(result, "details", {})
    raise ValueError(f"{prefix}:{reason}:{details}")


def _guard_import_edit_write(project_manager, target_path, *, source_path="", audit_metadata=None, allow_overwrite=False):
    _require_guard(
        can_write_label_role(
            "working_edit",
            operation="create_empty_edit_layer",
            audit_metadata=audit_metadata,
            overwrite_existing=allow_overwrite,
        ),
        "tif_label_guard_denied",
    )
    ensure_write_allowed(
        WriteIntent(
            target_path=target_path,
            project_root=project_manager.project_dir,
            source_path=source_path,
            source_role="tif_stack_import_source",
            target_role="working_edit",
            operation="create_empty_edit_layer",
            audit_metadata=dict(audit_metadata or {}) if isinstance(audit_metadata, dict) else {},
            allow_overwrite=allow_overwrite,
            allowed_roots=(project_manager.project_dir,),
        )
    )


def _coerce_tif_array_to_zyx(array):
    volume = np.asarray(array)
    if volume.ndim == 2:
        volume = volume[np.newaxis, :, :]
    if volume.ndim > 3:
        squeezed = np.squeeze(volume)
        if squeezed.ndim == 3:
            volume = squeezed
        else:
            raise ValueError(f"unsupported_tif_stack_dimensions:{volume.shape}")
    if volume.ndim != 3:
        raise ValueError(f"unsupported_tif_stack_dimensions:{volume.shape}")
    return volume


def _squeezed_shape_and_axes(shape, axes):
    values = [int(value) for value in shape]
    axis_text = str(axes or "")
    if len(axis_text) != len(values):
        axis_text = "?" * len(values)
    while len(values) > 3:
        removed = False
        for index, value in enumerate(values):
            if value == 1:
                values.pop(index)
                axis_text = axis_text[:index] + axis_text[index + 1 :]
                removed = True
                break
        if not removed:
            raise ValueError(f"unsupported_tif_stack_dimensions:{tuple(shape)}")
    return values, axis_text


def _series_shape_zyx(series):
    shape, axes = _squeezed_shape_and_axes(series.shape, getattr(series, "axes", ""))
    if len(shape) == 2:
        return [1, int(shape[0]), int(shape[1])]
    if len(shape) != 3:
        raise ValueError(f"unsupported_tif_stack_dimensions:{tuple(series.shape)}")
    if "Y" in axes and "X" in axes:
        y = int(shape[axes.index("Y")])
        x = int(shape[axes.index("X")])
        if "Z" in axes:
            z = int(shape[axes.index("Z")])
        else:
            z_axes = [index for index, axis in enumerate(axes) if axis not in {"Y", "X"}]
            if len(z_axes) != 1:
                raise ValueError(f"unsupported_tif_stack_axes:{axes}")
            z = int(shape[z_axes[0]])
        return [z, y, x]
    return [int(shape[0]), int(shape[1]), int(shape[2])]


def _emit_progress(progress_callback, current, total, message):
    if progress_callback is None:
        return
    progress_callback(int(current), int(total), str(message))


def _stage_progress(progress_callback, start, end):
    start = int(start)
    end = max(start, int(end))

    def emit(current, total, message):
        total = max(1, int(total or 1))
        current = max(0, min(total, int(current or 0)))
        value = start + int(round((float(current) / float(total)) * float(end - start)))
        _emit_progress(progress_callback, value, 100, message)

    return emit


def _try_write_tif_pages(tif, target, progress_callback=None):
    series = tif.series[0] if tif.series else None
    pages = list(series.pages if series is not None else tif.pages)
    if not pages:
        raise ValueError("tif_stack_has_no_pages")
    if len(pages) == int(target.shape[0]):
        for index, page in enumerate(pages):
            page_volume = _coerce_tif_array_to_zyx(page.asarray())
            if page_volume.shape[0] != 1 or tuple(page_volume.shape[1:]) != tuple(target.shape[1:]):
                return False
            target[index] = page_volume[0]
            _emit_progress(progress_callback, index + 1, len(pages), "Reading TIF slices")
        return True
    if len(pages) == 1:
        if int(target.shape[0]) > 1:
            return False
        page_volume = _coerce_tif_array_to_zyx(pages[0].asarray())
        if tuple(page_volume.shape) == tuple(target.shape):
            target[:] = page_volume
            _emit_progress(progress_callback, 1, 1, "Reading TIF volume")
            return True
    return False


def _stream_tif_stack_to_sidecar(
    source_path,
    image_abs,
    tif_metadata,
    progress_callback=None,
):
    shape_zyx = [int(value) for value in tif_metadata["shape_zyx"]]
    dtype = np.dtype(tif_metadata["dtype"])
    image_meta, target = create_volume_sidecar_memmap(
        image_abs,
        shape_zyx,
        dtype,
        role="working_image",
        spacing_zyx=tif_metadata.get("spacing_zyx", [1.0, 1.0, 1.0]),
        spacing_unit=tif_metadata.get("spacing_unit", "unknown"),
        orientation=tif_metadata.get("orientation", "unknown"),
        source_format="tif_stack",
        extra_metadata={
            "source_path": tif_metadata.get("source_path", ""),
            "import_adapter": TIF_STACK_IMPORT_ADAPTER_VERSION,
            "note": "Numpy sidecar written by streaming TIF import; exchange formats are generated at export time.",
        },
    )
    try:
        with tifffile.TiffFile(source_path) as tif:
            _emit_progress(progress_callback, 6, 100, "Inspecting TIF")
            wrote_pages = _try_write_tif_pages(
                tif,
                target,
                progress_callback=_stage_progress(progress_callback, 8, 90),
            )
            if not wrote_pages:
                _emit_progress(progress_callback, 10, 100, "Reading TIF volume")
                result = tif.asarray(series=0, out=target, maxworkers=1)
                if result is not None and result is not target:
                    target[:] = _coerce_tif_array_to_zyx(result)
                _emit_progress(progress_callback, 90, 100, "TIF volume decoded")
        _emit_progress(progress_callback, 92, 100, "Flushing working volume to project storage")
        target.flush()
    finally:
        if hasattr(target, "_mmap"):
            target._mmap.close()
    return image_meta


def _build_tif_working_sidecar(
    source_path,
    image_abs,
    tif_metadata,
    progress_callback=None,
):
    image_abs = os.path.abspath(str(image_abs))
    building_abs = f"{image_abs}.building"
    if os.path.exists(image_abs):
        raise FileExistsError(f"working_sidecar_target_already_exists:{image_abs}")
    if os.path.exists(building_abs):
        shutil.rmtree(building_abs)
    try:
        image_meta = _stream_tif_stack_to_sidecar(
            source_path,
            building_abs,
            tif_metadata,
            progress_callback=progress_callback,
        )
        _emit_progress(progress_callback, 94, 100, "Finalizing working volume")
        os.replace(building_abs, image_abs)
        return image_meta
    except Exception:
        if os.path.exists(building_abs):
            shutil.rmtree(building_abs, ignore_errors=True)
        raise


def _read_tif_metadata(path):
    metadata = {
        "page_count": 0,
        "series_shape": [],
        "axes": "",
        "dtype": "",
        "spacing_zyx": [1.0, 1.0, 1.0],
        "spacing_unit": "unknown",
        "orientation": "unknown",
        "warnings": [],
    }
    with tifffile.TiffFile(path) as tif:
        metadata["page_count"] = len(tif.pages)
        if tif.series:
            series = tif.series[0]
            metadata["series_shape"] = [int(value) for value in series.shape]
            metadata["axes"] = str(series.axes)
            metadata["dtype"] = str(series.dtype)
            metadata["shape_zyx"] = _series_shape_zyx(series)
        first_page = tif.pages[0] if tif.pages else None
        if first_page is not None:
            x_resolution = first_page.tags.get("XResolution")
            y_resolution = first_page.tags.get("YResolution")
            resolution_unit = first_page.tags.get("ResolutionUnit")
            if resolution_unit is not None:
                metadata["resolution_unit_raw"] = str(resolution_unit.value)
            if x_resolution is not None and y_resolution is not None:
                try:
                    x_value = _ratio_to_float(x_resolution.value)
                    y_value = _ratio_to_float(y_resolution.value)
                    if x_value > 0 and y_value > 0:
                        # TIFF resolution is pixels per unit. Without reliable XYZ physical
                        # metadata, retain raw values but keep the project unit unknown.
                        metadata["x_resolution_raw"] = x_value
                        metadata["y_resolution_raw"] = y_value
                        metadata["warnings"].append("physical_spacing_not_inferred_from_tiff_resolution")
                except Exception:
                    metadata["warnings"].append("tiff_resolution_metadata_unreadable")
    if metadata["spacing_unit"] == "unknown":
        metadata["warnings"].append("physical_spacing_unit_unknown")
    return metadata


def _ratio_to_float(value):
    if isinstance(value, tuple) and len(value) == 2 and value[1]:
        return float(value[0]) / float(value[1])
    return float(value)


def _natural_tif_path_key(path):
    name = os.path.basename(str(path or "")).casefold()
    chunks = []
    for value in re.split(r"(\d+)", name):
        if value.isdigit():
            chunks.append((1, int(value), len(value)))
        else:
            chunks.append((0, value))
    return tuple(chunks), os.path.normcase(os.path.abspath(str(path or "")))


def order_tif_slice_series_paths(tif_paths):
    normalized = []
    seen = set()
    for value in tif_paths or ():
        path = os.path.abspath(str(value or "").strip())
        if not path:
            continue
        key = os.path.normcase(path)
        if key in seen:
            raise ValueError(f"duplicate_tif_slice_path:{path}")
        seen.add(key)
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
        if os.path.splitext(path)[1].lower() not in {".tif", ".tiff"}:
            raise ValueError(f"not_tif_file:{path}")
        normalized.append(path)
    if not normalized:
        raise ValueError("tif_slice_series_is_empty")
    return sorted(normalized, key=_natural_tif_path_key)


def _slice_shape_and_axes(shape, axes):
    values = [int(value) for value in shape]
    axis_text = str(axes or "")
    if len(axis_text) != len(values):
        axis_text = "?" * len(values)
    while len(values) > 2:
        removable = [
            index
            for index, (value, axis) in enumerate(zip(values, axis_text))
            if value == 1 and axis not in {"Y", "X"}
        ]
        if not removable and "Y" not in axis_text and "X" not in axis_text:
            removable = [index for index, value in enumerate(values) if value == 1]
        if not removable:
            raise ValueError(f"tif_slice_file_must_be_single_plane:{tuple(shape)}:{axis_text}")
        index = removable[0]
        values.pop(index)
        axis_text = axis_text[:index] + axis_text[index + 1 :]
    if len(values) != 2:
        raise ValueError(f"tif_slice_file_must_be_2d:{tuple(shape)}:{axis_text}")
    if "Y" in axis_text and "X" in axis_text:
        return [int(values[axis_text.index("Y")]), int(values[axis_text.index("X")])], axis_text
    return [int(values[0]), int(values[1])], axis_text


def _tif_slice_grayscale_metadata(page, path):
    samples_per_pixel = int(getattr(page, "samplesperpixel", 0) or 0)
    photometric_value = getattr(page, "photometric", None)
    photometric = str(getattr(photometric_value, "name", "") or "").upper()
    if samples_per_pixel != 1:
        raise ValueError(
            f"tif_slice_file_must_be_single_channel:{path}:samples_per_pixel={samples_per_pixel}"
        )
    if photometric not in {"MINISBLACK", "MINISWHITE"}:
        raise ValueError(
            f"tif_slice_file_must_be_grayscale:{path}:photometric={photometric or 'UNKNOWN'}"
        )
    return {
        "samples_per_pixel": samples_per_pixel,
        "photometric": photometric,
    }


def _read_tif_slice_header(path):
    with tifffile.TiffFile(path) as tif:
        if len(tif.pages) != 1 or not tif.series:
            raise ValueError(f"tif_slice_file_must_contain_one_page:{path}:{len(tif.pages)}")
        grayscale = _tif_slice_grayscale_metadata(tif.pages[0], path)
        series = tif.series[0]
        shape_yx, axes = _slice_shape_and_axes(series.shape, getattr(series, "axes", ""))
        return {
            "path": path,
            "shape_yx": shape_yx,
            "series_shape": [int(value) for value in series.shape],
            "axes": str(getattr(series, "axes", "") or axes),
            "dtype": str(np.dtype(series.dtype)),
            "file_size": int(os.path.getsize(path)),
            **grayscale,
        }


def inspect_tif_slice_series(tif_paths):
    ordered_paths = order_tif_slice_series_paths(tif_paths)
    headers = [_read_tif_slice_header(path) for path in ordered_paths]
    expected_shape = list(headers[0]["shape_yx"])
    expected_dtype = str(headers[0]["dtype"])
    expected_photometric = str(headers[0]["photometric"])
    for header in headers[1:]:
        if list(header["shape_yx"]) != expected_shape:
            raise ValueError(
                "tif_slice_series_shape_mismatch:"
                f"{header['path']}:expected={tuple(expected_shape)}:found={tuple(header['shape_yx'])}"
            )
        if str(header["dtype"]) != expected_dtype:
            raise ValueError(
                "tif_slice_series_dtype_mismatch:"
                f"{header['path']}:expected={expected_dtype}:found={header['dtype']}"
            )
        if str(header["photometric"]) != expected_photometric:
            raise ValueError(
                "tif_slice_series_photometric_mismatch:"
                f"{header['path']}:expected={expected_photometric}:found={header['photometric']}"
            )
    warnings = ["physical_spacing_unit_unknown", "slice_spacing_not_provided"]
    if expected_photometric == "MINISWHITE":
        warnings.append("source_photometric_miniswhite_preserved")
    return {
        "ordered_paths": ordered_paths,
        "headers": headers,
        "shape_zyx": [len(ordered_paths), *expected_shape],
        "dtype": expected_dtype,
        "spacing_zyx": [1.0, 1.0, 1.0],
        "spacing_unit": "unknown",
        "orientation": "unknown",
        "ordering": TIF_SLICE_SERIES_ORDERING,
        "photometric": expected_photometric,
        "samples_per_pixel": 1,
        "warnings": warnings,
    }


def _read_tif_slice_yx(path, expected_shape, expected_dtype, expected_photometric):
    with tifffile.TiffFile(path) as tif:
        if len(tif.pages) != 1 or not tif.series:
            raise ValueError(f"tif_slice_file_must_contain_one_page:{path}:{len(tif.pages)}")
        grayscale = _tif_slice_grayscale_metadata(tif.pages[0], path)
        if grayscale["photometric"] != str(expected_photometric):
            raise ValueError(
                "tif_slice_series_photometric_changed:"
                f"{path}:expected={expected_photometric}:found={grayscale['photometric']}"
            )
        series = tif.series[0]
        array = np.asarray(series.asarray(maxworkers=1))
        axes = str(getattr(series, "axes", "") or "")
    while array.ndim > 2:
        axis_text = axes if len(axes) == array.ndim else "?" * array.ndim
        removable = [
            index
            for index, (value, axis) in enumerate(zip(array.shape, axis_text))
            if int(value) == 1 and axis not in {"Y", "X"}
        ]
        if not removable and "Y" not in axis_text and "X" not in axis_text:
            removable = [index for index, value in enumerate(array.shape) if int(value) == 1]
        if not removable:
            raise ValueError(f"tif_slice_file_must_be_single_plane:{path}:{array.shape}:{axes}")
        index = removable[0]
        array = np.squeeze(array, axis=index)
        if len(axes) == len(axis_text):
            axes = axes[:index] + axes[index + 1 :]
    if array.ndim != 2:
        raise ValueError(f"tif_slice_file_must_be_2d:{path}:{array.shape}:{axes}")
    if len(axes) == 2 and set(axes) >= {"Y", "X"} and axes.index("Y") > axes.index("X"):
        array = np.transpose(array)
    if list(array.shape) != list(expected_shape):
        raise ValueError(
            f"tif_slice_series_shape_changed:{path}:expected={tuple(expected_shape)}:found={array.shape}"
        )
    if str(array.dtype) != str(expected_dtype):
        raise ValueError(
            f"tif_slice_series_dtype_changed:{path}:expected={expected_dtype}:found={array.dtype}"
        )
    return array


def _stream_tif_slice_series_to_sidecar(source_paths, image_abs, series_metadata, progress_callback=None):
    image_meta, target = create_volume_sidecar_memmap(
        image_abs,
        series_metadata["shape_zyx"],
        np.dtype(series_metadata["dtype"]),
        role="working_image",
        spacing_zyx=series_metadata.get("spacing_zyx", [1.0, 1.0, 1.0]),
        spacing_unit=series_metadata.get("spacing_unit", "unknown"),
        orientation=series_metadata.get("orientation", "unknown"),
        source_format="tif_slice_series",
        extra_metadata={
            "source_manifest": series_metadata.get("source_manifest", ""),
            "source_file_count": len(source_paths),
            "source_ordering": TIF_SLICE_SERIES_ORDERING,
            "source_photometric": series_metadata.get("photometric", ""),
            "import_adapter": TIF_SLICE_SERIES_IMPORT_ADAPTER_VERSION,
            "note": "Numpy sidecar streamed from selected single-plane TIF files in recorded order.",
        },
    )
    try:
        total = len(source_paths)
        for index, source_path in enumerate(source_paths):
            target[index] = _read_tif_slice_yx(
                source_path,
                series_metadata["shape_zyx"][1:],
                series_metadata["dtype"],
                series_metadata["photometric"],
            )
            _emit_progress(progress_callback, index + 1, total, "Reading selected TIF slices")
        target.flush()
    finally:
        if hasattr(target, "_mmap"):
            target._mmap.close()
    return image_meta


def _build_tif_slice_series_working_sidecar(source_paths, image_abs, series_metadata, progress_callback=None):
    image_abs = os.path.abspath(str(image_abs))
    building_abs = f"{image_abs}.building"
    if os.path.exists(image_abs):
        raise FileExistsError(f"working_sidecar_target_already_exists:{image_abs}")
    if os.path.exists(building_abs):
        shutil.rmtree(building_abs)
    try:
        image_meta = _stream_tif_slice_series_to_sidecar(
            source_paths,
            building_abs,
            series_metadata,
            progress_callback=_stage_progress(progress_callback, 15, 90),
        )
        _emit_progress(progress_callback, 94, 100, "Finalizing working volume")
        os.replace(building_abs, image_abs)
        return image_meta
    except Exception:
        if os.path.exists(building_abs):
            shutil.rmtree(building_abs, ignore_errors=True)
        raise


def import_tif_slice_series(
    project_manager,
    tif_paths,
    specimen_id,
    modality="unknown",
    metadata_ref="",
    material_map=None,
    copy_source=False,
    create_working_edit=False,
    progress_callback=None,
):
    if not isinstance(project_manager, TifProjectManager):
        raise TypeError("project_manager_must_be_tif_project_manager")
    _emit_progress(progress_callback, 1, 100, "Inspecting selected TIF slices")
    series_metadata = inspect_tif_slice_series(tif_paths)
    original_paths = list(series_metadata["ordered_paths"])
    warnings = list(series_metadata.get("warnings", []))

    specimen = project_manager.create_specimen_scaffold(
        specimen_id,
        material_map=material_map or {},
        modality=modality,
        metadata_ref=metadata_ref,
    )
    try:
        specimen_root_rel = project_manager.specimen_dir(specimen_id)
        specimen_root_abs = project_manager.to_absolute(specimen_root_rel)
        source_entries = []
        working_source_paths = []
        for index, source_path in enumerate(original_paths):
            stored_path = source_path
            if copy_source:
                stored_name = f"{index:06d}_{_safe_filename(os.path.basename(source_path))}"
                stored_path = os.path.join(specimen_root_abs, "source", "raw", "slices", stored_name)
                os.makedirs(os.path.dirname(stored_path), exist_ok=True)
                shutil.copy2(source_path, stored_path)
            stored_ref = project_manager.to_relative(stored_path) if copy_source else stored_path
            source_entries.append(
                {
                    "z_index": index,
                    "filename": os.path.basename(source_path),
                    "original_path": source_path,
                    "stored_path": stored_ref,
                    "size_bytes": int(os.path.getsize(source_path)),
                }
            )
            working_source_paths.append(stored_path)

        manifest_rel = os.path.join(specimen_root_rel, "source", "tif_slice_series_manifest.json").replace("\\", "/")
        manifest_abs = project_manager.to_absolute(manifest_rel)
        parent_dirs = {os.path.dirname(path) for path in original_paths}
        manifest = {
            "schema_version": TIF_SLICE_SERIES_MANIFEST_SCHEMA_VERSION,
            "created_at": _now_iso(),
            "specimen_id": str(specimen_id),
            "ordering": TIF_SLICE_SERIES_ORDERING,
            "selected_file_count": len(original_paths),
            "source_directory": next(iter(parent_dirs)) if len(parent_dirs) == 1 else "",
            "source_files_copied": bool(copy_source),
            "shape_zyx": list(series_metadata["shape_zyx"]),
            "dtype": str(series_metadata["dtype"]),
            "photometric": str(series_metadata["photometric"]),
            "samples_per_pixel": int(series_metadata["samples_per_pixel"]),
            "slices": source_entries,
        }
        atomic_write_json(manifest_abs, manifest, indent=2, ensure_ascii=False)

        image_rel = os.path.join(specimen_root_rel, "working", "image.ome.zarr").replace("\\", "/")
        image_abs = project_manager.to_absolute(image_rel)
        series_metadata["source_manifest"] = manifest_rel
        _emit_progress(progress_callback, 12, 100, "Preparing selected TIF slice series")
        image_meta = _build_tif_slice_series_working_sidecar(
            working_source_paths,
            image_abs,
            series_metadata,
            progress_callback=progress_callback,
        )
        project_manager.register_working_volume(
            specimen_id,
            image_rel,
            image_meta["shape_zyx"],
            image_meta["dtype"],
            spacing_zyx=image_meta["spacing_zyx"],
            spacing_unit=image_meta["spacing_unit"],
            orientation=image_meta["orientation"],
            fmt=image_meta["format"],
            save=False,
        )

        working_edit_rel = os.path.join(specimen_root_rel, "labels", "working_edit.ome.zarr").replace("\\", "/")
        working_edit_abs = project_manager.to_absolute(working_edit_rel)
        edit_meta = None
        if create_working_edit:
            _emit_progress(progress_callback, 96, 100, "Creating editable label layer")
            import_audit = {
                "import_adapter": TIF_SLICE_SERIES_IMPORT_ADAPTER_VERSION,
                "source_manifest": manifest_rel,
                "specimen_id": str(specimen_id),
            }
            _guard_import_edit_write(
                project_manager,
                working_edit_abs,
                source_path=manifest_abs,
                audit_metadata=import_audit,
                allow_overwrite=False,
            )
            edit_meta = create_empty_label_sidecar_like(
                image_abs,
                working_edit_abs,
                max_label_id=_maximum_material_id(material_map),
                role="working_edit",
                write_ome_zarr=False,
            )
            project_manager.register_label_volume(
                specimen_id,
                "working_edit",
                working_edit_rel,
                edit_meta["shape_zyx"],
                edit_meta["dtype"],
                status="empty_edit",
                spacing_zyx=edit_meta["spacing_zyx"],
                spacing_unit=edit_meta["spacing_unit"],
                orientation=edit_meta["orientation"],
                fmt=edit_meta["format"],
                operation="create_empty_edit_layer",
                save=False,
            )
        else:
            working_edit_rel = ""

        material_map_rel = os.path.join(specimen_root_rel, "material_map.json").replace("\\", "/")
        material_map_payload = write_material_map(
            project_manager.to_absolute(material_map_rel),
            material_map or {},
            source=(material_map or {}).get("source", "manual") if isinstance(material_map, dict) else "manual",
        )

        specimen = project_manager.get_specimen(specimen_id)
        specimen["source"]["raw_tif"] = ""
        specimen["source"]["tif_slice_series_manifest"] = manifest_rel
        specimen["material_map"] = material_map_rel
        specimen["review_status"] = "not_started"
        specimen["train_ready"] = False
        specimen["metadata"].update(
            {
                "source_kind": "tif_slice_series",
                "source_tif_series_manifest": manifest_rel,
                "source_tif_series_count": len(original_paths),
            }
        )
        specimen["provenance"] = {
            "import_method": TIF_SLICE_SERIES_IMPORT_ADAPTER_VERSION,
            "source_file": manifest_rel,
            "source_file_count": len(original_paths),
            "notes": "Selected single-plane TIF files were naturally sorted and streamed into one working volume.",
        }

        report = {
            "schema_version": TIF_STACK_IMPORT_REPORT_SCHEMA_VERSION,
            "imported_at": _now_iso(),
            "adapter_version": TIF_SLICE_SERIES_IMPORT_ADAPTER_VERSION,
            "source_file": manifest_rel,
            "specimen_id": str(specimen_id),
            "files": {
                "raw_tif": "",
                "tif_slice_series_manifest": manifest_rel,
                "working_image": image_rel,
                "working_edit": working_edit_rel,
                "material_map": material_map_rel,
            },
            "source_series": {
                "selected_file_count": len(original_paths),
                "ordering": TIF_SLICE_SERIES_ORDERING,
                "first_file": original_paths[0],
                "last_file": original_paths[-1],
                "source_files_copied": bool(copy_source),
            },
            "shapes": {
                "tif_stack_zyx": image_meta["shape_zyx"],
                "working_image_zyx": image_meta["shape_zyx"],
                "working_edit_zyx": edit_meta["shape_zyx"] if edit_meta else [],
            },
            "dtype": {
                "working_image": image_meta["dtype"],
                "working_edit": edit_meta["dtype"] if edit_meta else "",
            },
            "tiff_metadata": {
                "shape_zyx": list(series_metadata["shape_zyx"]),
                "dtype": str(series_metadata["dtype"]),
                "spacing_zyx": list(series_metadata["spacing_zyx"]),
                "spacing_unit": str(series_metadata["spacing_unit"]),
                "orientation": str(series_metadata["orientation"]),
                "photometric": str(series_metadata["photometric"]),
                "samples_per_pixel": int(series_metadata["samples_per_pixel"]),
            },
            "materials": {
                "count": len(material_map_payload.get("materials", [])),
                "source": material_map_payload.get("source", "manual"),
            },
            "alignment": {
                "working_image": "selected_tif_slice_series",
                "manual_truth": "not_created",
                "raw_tif_used_as": "ordered_single_plane_tif_sources",
            },
            "memory_policy": {
                "import_mode": "stream_selected_tif_slices_to_memmap_sidecar",
                "whole_volume_imread": False,
                "one_source_slice_loaded_at_a_time": True,
                "ome_zarr_exchange_deferred": True,
                "source_tif_copied": bool(copy_source),
                "working_edit_created_on_import": bool(create_working_edit),
            },
            "warnings": warnings,
            "errors": [],
        }
        report_rel = os.path.join(specimen_root_rel, "working", "import_report.json").replace("\\", "/")
        report_abs = project_manager.to_absolute(report_rel)
        atomic_write_json(report_abs, report, indent=2, ensure_ascii=False)
        specimen["working_volume"]["import_report"] = report_rel
        _emit_progress(progress_callback, 98, 100, "Saving TIF project")
        project_manager.save_project()
    except Exception:
        project_manager.discard_specimen_scaffold(specimen_id, save=True)
        raise

    return {
        "import_kind": "tif_slice_series",
        "specimen": specimen,
        "report": report,
        "report_path": report_abs,
        "source_manifest_path": manifest_abs,
    }


def import_tif_stack(
    project_manager,
    tif_path,
    specimen_id,
    modality="unknown",
    metadata_ref="",
    material_map=None,
    copy_source=True,
    create_working_edit=True,
    progress_callback=None,
):
    if not isinstance(project_manager, TifProjectManager):
        raise TypeError("project_manager_must_be_tif_project_manager")
    source_path = os.path.abspath(str(tif_path))
    if not os.path.exists(source_path):
        raise FileNotFoundError(source_path)
    if os.path.splitext(source_path)[1].lower() not in {".tif", ".tiff"}:
        raise ValueError(f"not_tif_file:{source_path}")

    tif_metadata = _read_tif_metadata(source_path)
    warnings = list(tif_metadata.get("warnings", []))

    specimen = project_manager.create_specimen_scaffold(
        specimen_id,
        material_map=material_map or {},
        modality=modality,
        metadata_ref=metadata_ref,
    )
    try:
        specimen_root_rel = project_manager.specimen_dir(specimen_id)
        specimen_root_abs = project_manager.to_absolute(specimen_root_rel)

        raw_rel = os.path.join(specimen_root_rel, "source", "raw", _safe_filename(os.path.basename(source_path))).replace("\\", "/")
        raw_abs = project_manager.to_absolute(raw_rel)
        source_ref = project_manager.to_relative(raw_rel)
        if copy_source:
            _emit_progress(progress_callback, 1, 100, "Copying source TIF")
            os.makedirs(os.path.dirname(raw_abs), exist_ok=True)
            if os.path.abspath(source_path) != os.path.abspath(raw_abs):
                shutil.copy2(source_path, raw_abs)
        else:
            raw_rel = source_path
            source_ref = source_path

        image_rel = os.path.join(specimen_root_rel, "working", "image.ome.zarr").replace("\\", "/")
        image_abs = project_manager.to_absolute(image_rel)
        tif_metadata["source_path"] = source_ref
        _emit_progress(progress_callback, 5, 100, "Preparing sidecar")
        image_meta = _build_tif_working_sidecar(
            source_path,
            image_abs,
            tif_metadata,
            progress_callback=progress_callback,
        )
        project_manager.register_working_volume(
            specimen_id,
            image_rel,
            image_meta["shape_zyx"],
            image_meta["dtype"],
            spacing_zyx=image_meta["spacing_zyx"],
            spacing_unit=image_meta["spacing_unit"],
            orientation=image_meta["orientation"],
            fmt=image_meta["format"],
            save=False,
        )

        working_edit_rel = os.path.join(specimen_root_rel, "labels", "working_edit.ome.zarr").replace("\\", "/")
        working_edit_abs = project_manager.to_absolute(working_edit_rel)
        edit_meta = None
        if create_working_edit:
            _emit_progress(progress_callback, 96, 100, "Creating editable label layer")
            import_audit = {
                "import_adapter": TIF_STACK_IMPORT_ADAPTER_VERSION,
                "source_path": source_path,
                "specimen_id": str(specimen_id),
            }
            _guard_import_edit_write(
                project_manager,
                working_edit_abs,
                source_path=source_path,
                audit_metadata=import_audit,
                allow_overwrite=False,
            )
            edit_meta = create_empty_label_sidecar_like(
                image_abs,
                working_edit_abs,
                max_label_id=_maximum_material_id(material_map),
                role="working_edit",
                write_ome_zarr=False,
            )
            project_manager.register_label_volume(
                specimen_id,
                "working_edit",
                working_edit_rel,
                edit_meta["shape_zyx"],
                edit_meta["dtype"],
                status="empty_edit",
                spacing_zyx=edit_meta["spacing_zyx"],
                spacing_unit=edit_meta["spacing_unit"],
                orientation=edit_meta["orientation"],
                fmt=edit_meta["format"],
                operation="create_empty_edit_layer",
                save=False,
            )
        else:
            working_edit_rel = ""

        material_map_rel = os.path.join(specimen_root_rel, "material_map.json").replace("\\", "/")
        material_map_payload = write_material_map(project_manager.to_absolute(material_map_rel), material_map or {}, source=(material_map or {}).get("source", "manual") if isinstance(material_map, dict) else "manual")

        specimen = project_manager.get_specimen(specimen_id)
        specimen["source"]["raw_tif"] = source_ref
        specimen["material_map"] = material_map_rel
        specimen["review_status"] = "not_started"
        specimen["train_ready"] = False
        specimen["provenance"] = {
            "import_method": TIF_STACK_IMPORT_ADAPTER_VERSION,
            "source_file": source_path,
            "notes": "Plain TIF stack import creates working image and empty working_edit, not manual_truth.",
        }

        report = {
            "schema_version": TIF_STACK_IMPORT_REPORT_SCHEMA_VERSION,
            "imported_at": _now_iso(),
            "adapter_version": TIF_STACK_IMPORT_ADAPTER_VERSION,
            "source_file": source_path,
            "specimen_id": str(specimen_id),
            "files": {
                "raw_tif": source_ref,
                "working_image": image_rel,
                "working_edit": working_edit_rel,
                "material_map": material_map_rel,
            },
            "shapes": {
                "tif_stack_zyx": image_meta["shape_zyx"],
                "working_image_zyx": image_meta["shape_zyx"],
                "working_edit_zyx": edit_meta["shape_zyx"] if edit_meta else [],
            },
            "dtype": {
                "working_image": image_meta["dtype"],
                "working_edit": edit_meta["dtype"] if edit_meta else "",
            },
            "tiff_metadata": tif_metadata,
            "materials": {
                "count": len(material_map_payload.get("materials", [])),
                "source": material_map_payload.get("source", "manual"),
            },
            "alignment": {
                "working_image": "plain_tif_stack",
                "manual_truth": "not_created",
                "raw_tif_used_as": "source_and_working_input",
            },
            "memory_policy": {
                "import_mode": "stream_to_memmap_sidecar",
                "whole_volume_imread": False,
                "ome_zarr_exchange_deferred": True,
                "source_tif_copied": bool(copy_source),
                "working_edit_created_on_import": bool(create_working_edit),
            },
            "warnings": warnings,
            "errors": [],
        }
        report_rel = os.path.join(specimen_root_rel, "working", "import_report.json").replace("\\", "/")
        report_abs = project_manager.to_absolute(report_rel)
        atomic_write_json(report_abs, report, indent=2, ensure_ascii=False)
        specimen["working_volume"]["import_report"] = report_rel
        _emit_progress(progress_callback, 98, 100, "Saving TIF project")
        project_manager.save_project()
    except Exception:
        project_manager.discard_specimen_scaffold(specimen_id, save=True)
        raise

    return {
        "specimen": specimen,
        "report": report,
        "report_path": report_abs,
    }


def register_tif_stack_metadata(
    project_manager,
    tif_path,
    specimen_id,
    modality="unknown",
    metadata_ref="",
    material_map=None,
    progress_callback=None,
):
    if not isinstance(project_manager, TifProjectManager):
        raise TypeError("project_manager_must_be_tif_project_manager")
    source_path = os.path.abspath(str(tif_path))
    if not os.path.exists(source_path):
        raise FileNotFoundError(source_path)
    if os.path.splitext(source_path)[1].lower() not in {".tif", ".tiff"}:
        raise ValueError(f"not_tif_file:{source_path}")

    _emit_progress(progress_callback, 1, 100, "Reading TIF metadata")
    tif_metadata = _read_tif_metadata(source_path)
    warnings = list(tif_metadata.get("warnings", []))
    file_size = int(os.path.getsize(source_path))

    specimen = project_manager.create_specimen_scaffold(
        specimen_id,
        material_map=material_map or {},
        modality=modality,
        metadata_ref=metadata_ref,
    )
    try:
        specimen_root_rel = project_manager.specimen_dir(specimen_id)
        material_map_rel = os.path.join(specimen_root_rel, "material_map.json").replace("\\", "/")
        material_map_payload = write_material_map(
            project_manager.to_absolute(material_map_rel),
            material_map or {},
            source=(material_map or {}).get("source", "manual") if isinstance(material_map, dict) else "manual",
        )

        shape_zyx = [int(value) for value in tif_metadata.get("shape_zyx", [])]
        spacing_zyx = [float(value) for value in tif_metadata.get("spacing_zyx", []) or []]
        metadata_record = {
            "import_status": "metadata_only",
            "source_tif": source_path,
            "source_file_size": file_size,
            "shape_zyx": shape_zyx,
            "dtype": str(tif_metadata.get("dtype") or ""),
            "spacing_zyx": spacing_zyx,
            "spacing_unit": str(tif_metadata.get("spacing_unit", "unknown") or "unknown"),
            "orientation": str(tif_metadata.get("orientation", "unknown") or "unknown"),
            "tiff_metadata": dict(tif_metadata),
        }

        specimen = project_manager.get_specimen(specimen_id)
        specimen["source"]["raw_tif"] = source_path
        specimen["material_map"] = material_map_rel
        specimen["working_volume"].update(
            {
                "path": "",
                "format": "",
                "shape_zyx": shape_zyx,
                "dtype": metadata_record["dtype"],
                "spacing_zyx": spacing_zyx,
                "spacing_unit": metadata_record["spacing_unit"],
                "orientation": metadata_record["orientation"],
                "status": "metadata_only",
                "source_path": source_path,
                "source_file_size": file_size,
            }
        )
        specimen["review_status"] = "not_started"
        specimen["train_ready"] = False
        specimen["metadata"].update(metadata_record)
        specimen["provenance"] = {
            "import_method": TIF_STACK_METADATA_IMPORT_ADAPTER_VERSION,
            "source_file": source_path,
            "notes": "Metadata-only TIF registration. Full sidecar materialization is deferred until explicitly requested.",
        }

        report = {
            "schema_version": TIF_STACK_IMPORT_REPORT_SCHEMA_VERSION,
            "imported_at": _now_iso(),
            "adapter_version": TIF_STACK_METADATA_IMPORT_ADAPTER_VERSION,
            "source_file": source_path,
            "specimen_id": str(specimen_id),
            "files": {
                "raw_tif": source_path,
                "working_image": "",
                "working_edit": "",
                "material_map": material_map_rel,
            },
            "shapes": {
                "tif_stack_zyx": shape_zyx,
                "working_image_zyx": [],
                "working_edit_zyx": [],
            },
            "dtype": {
                "source_tif": metadata_record["dtype"],
                "working_image": "",
                "working_edit": "",
            },
            "tiff_metadata": tif_metadata,
            "materials": {
                "count": len(material_map_payload.get("materials", [])),
                "source": material_map_payload.get("source", "manual"),
            },
            "alignment": {
                "working_image": "metadata_only_not_materialized",
                "manual_truth": "not_created",
                "raw_tif_used_as": "deferred_source",
            },
            "memory_policy": {
                "import_mode": "metadata_only",
                "whole_volume_imread": False,
                "sidecar_created_on_import": False,
                "ome_zarr_exchange_deferred": True,
                "source_tif_copied": False,
                "working_edit_created_on_import": False,
                "source_file_size": file_size,
            },
            "warnings": warnings,
            "errors": [],
        }
        report_rel = os.path.join(specimen_root_rel, "working", "import_report.json").replace("\\", "/")
        report_abs = project_manager.to_absolute(report_rel)
        atomic_write_json(report_abs, report, indent=2, ensure_ascii=False)
        specimen["working_volume"]["import_report"] = report_rel
        _emit_progress(progress_callback, 98, 100, "Saving TIF metadata")
        project_manager.save_project()
    except Exception:
        project_manager.discard_specimen_scaffold(specimen_id, save=True)
        raise

    return {
        "specimen": specimen,
        "report": report,
        "report_path": report_abs,
    }


def materialize_registered_tif_stack(
    project_manager,
    specimen_id,
    progress_callback=None,
):
    if not isinstance(project_manager, TifProjectManager):
        raise TypeError("project_manager_must_be_tif_project_manager")
    specimen = project_manager.get_specimen(specimen_id, default=None)
    if specimen is None:
        raise KeyError(f"unknown_specimen_id:{specimen_id}")
    source_text = str((specimen.get("metadata") or {}).get("source_tif") or (specimen.get("source") or {}).get("raw_tif") or "")
    if not source_text:
        raise FileNotFoundError(source_text)
    source_path = os.path.abspath(source_text)
    if not os.path.exists(source_path):
        raise FileNotFoundError(source_path)
    if os.path.splitext(source_path)[1].lower() not in {".tif", ".tiff"}:
        raise ValueError(f"not_tif_file:{source_path}")

    _emit_progress(progress_callback, 1, 100, "Reading metadata")
    tif_metadata = _read_tif_metadata(source_path)
    warnings = list(tif_metadata.get("warnings", []))
    source_ref = source_path
    specimen_root_rel = project_manager.specimen_dir(specimen_id)
    image_rel = os.path.join(specimen_root_rel, "working", "image.ome.zarr").replace("\\", "/")
    image_abs = project_manager.to_absolute(image_rel)
    material_map_rel = specimen.get("material_map", "") or os.path.join(specimen_root_rel, "material_map.json").replace("\\", "/")
    report_rel = os.path.join(specimen_root_rel, "working", "import_report.json").replace("\\", "/")
    report_abs = project_manager.to_absolute(report_rel)
    if os.path.exists(image_abs):
        raise FileExistsError(f"materialize_target_already_exists:{image_abs}")
    specimen_snapshot = copy.deepcopy(specimen)
    report_snapshot = None
    if os.path.isfile(report_abs):
        with open(report_abs, "rb") as handle:
            report_snapshot = handle.read()
    tif_metadata["source_path"] = source_ref
    try:
        _emit_progress(progress_callback, 5, 100, "Preparing sidecar")
        image_meta = _build_tif_working_sidecar(
            source_path,
            image_abs,
            tif_metadata,
            progress_callback=progress_callback,
        )
        project_manager.register_working_volume(
            specimen_id,
            image_rel,
            image_meta["shape_zyx"],
            image_meta["dtype"],
            spacing_zyx=image_meta["spacing_zyx"],
            spacing_unit=image_meta["spacing_unit"],
            orientation=image_meta["orientation"],
            fmt=image_meta["format"],
            save=False,
        )
        specimen = project_manager.get_specimen(specimen_id)
        specimen["source"]["raw_tif"] = source_ref
        specimen["material_map"] = material_map_rel
        specimen.setdefault("metadata", {})["import_status"] = "materialized"
        specimen.setdefault("metadata", {})["source_tif"] = source_path
        specimen["provenance"] = {
            "import_method": TIF_STACK_IMPORT_ADAPTER_VERSION,
            "source_file": source_path,
            "notes": "Metadata-only TIF registration materialized into a working image sidecar. No working_edit was created.",
        }

        report = {
            "schema_version": TIF_STACK_IMPORT_REPORT_SCHEMA_VERSION,
            "imported_at": _now_iso(),
            "adapter_version": TIF_STACK_IMPORT_ADAPTER_VERSION,
            "source_file": source_path,
            "specimen_id": str(specimen_id),
            "files": {
                "raw_tif": source_ref,
                "working_image": image_rel,
                "working_edit": "",
                "material_map": material_map_rel,
            },
            "shapes": {
                "tif_stack_zyx": image_meta["shape_zyx"],
                "working_image_zyx": image_meta["shape_zyx"],
                "working_edit_zyx": [],
            },
            "dtype": {
                "working_image": image_meta["dtype"],
                "working_edit": "",
            },
            "tiff_metadata": tif_metadata,
            "alignment": {
                "working_image": "plain_tif_stack",
                "manual_truth": "not_created",
                "raw_tif_used_as": "deferred_source",
            },
            "memory_policy": {
                "import_mode": "materialize_metadata_to_memmap_sidecar",
                "whole_volume_imread": False,
                "ome_zarr_exchange_deferred": True,
                "source_tif_copied": False,
                "working_edit_created_on_import": False,
            },
            "warnings": warnings,
            "errors": [],
        }
        atomic_write_json(report_abs, report, indent=2, ensure_ascii=False)
        specimen["working_volume"]["import_report"] = report_rel
        _emit_progress(progress_callback, 98, 100, "Saving TIF project")
        project_manager.save_project()
    except Exception as exc:
        rollback_errors = []
        specimen.clear()
        specimen.update(specimen_snapshot)
        try:
            if os.path.exists(image_abs):
                shutil.rmtree(image_abs)
        except Exception as rollback_exc:
            rollback_errors.append(f"sidecar:{rollback_exc}")
        try:
            if report_snapshot is None:
                if os.path.exists(report_abs):
                    os.remove(report_abs)
            else:
                report_tmp = f"{report_abs}.rollback.tmp"
                with open(report_tmp, "wb") as handle:
                    handle.write(report_snapshot)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(report_tmp, report_abs)
        except Exception as rollback_exc:
            rollback_errors.append(f"report:{rollback_exc}")
        if rollback_errors:
            raise RuntimeError(
                f"tif_materialize_failed:{exc};rollback_failed:{'|'.join(rollback_errors)}"
            ) from exc
        raise

    return {
        "specimen": specimen,
        "report": report,
        "report_path": report_abs,
    }
