import gzip
import json
import os
import shutil
import struct
from datetime import datetime

import numpy as np
import tifffile

from .safe_io import atomic_write_json
from .tif_project import TifProjectManager
from .tif_storage import label_dtype_for_max_id
from .tif_volume_io import load_volume_sidecar, read_volume_metadata, volume_sidecar_exists


TIF_TRAINING_EXPORT_SCHEMA_VERSION = "ant3d_tif_training_export_v1"
TIF_PART_TRAINING_EXPORT_SCHEMA_VERSION = "ant3d_tif_part_training_export_v1"
SUPPORTED_TIF_EXPORT_FORMATS = {"ome_tiff", "tiff", "nrrd", "mha", "nifti"}
NNUNET_DATASET_SCHEMA_VERSION = "ant3d_nnunet_dataset_v1"
NNUNET_PART_DATASET_SCHEMA_VERSION = "ant3d_tif_part_nnunet_dataset_v1"
MONAI_DATASET_SCHEMA_VERSION = "ant3d_monai_dataset_v1"


def _now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _safe_id(value):
    text = str(value or "").strip()
    clean = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in text)
    return clean.strip("_") or "specimen"


def _safe_label_name(value, fallback):
    text = str(value or "").strip() or str(fallback or "").strip()
    clean = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in text)
    return clean.strip("_") or "label"


def _ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def _write_json(path, payload):
    atomic_write_json(path, payload, indent=2, ensure_ascii=False)


def _dtype_to_nrrd_type(dtype):
    dtype = np.dtype(dtype)
    mapping = {
        np.dtype("uint8"): "uint8",
        np.dtype("int8"): "int8",
        np.dtype("uint16"): "uint16",
        np.dtype("int16"): "int16",
        np.dtype("uint32"): "uint32",
        np.dtype("int32"): "int32",
        np.dtype("float32"): "float",
        np.dtype("float64"): "double",
    }
    if dtype not in mapping:
        raise ValueError(f"unsupported_nrrd_dtype:{dtype}")
    return mapping[dtype]


def _dtype_to_mha_type(dtype):
    dtype = np.dtype(dtype)
    mapping = {
        np.dtype("uint8"): "MET_UCHAR",
        np.dtype("int8"): "MET_CHAR",
        np.dtype("uint16"): "MET_USHORT",
        np.dtype("int16"): "MET_SHORT",
        np.dtype("uint32"): "MET_UINT",
        np.dtype("int32"): "MET_INT",
        np.dtype("float32"): "MET_FLOAT",
        np.dtype("float64"): "MET_DOUBLE",
    }
    if dtype not in mapping:
        raise ValueError(f"unsupported_mha_dtype:{dtype}")
    return mapping[dtype]


def _dtype_to_nifti(dtype):
    dtype = np.dtype(dtype)
    mapping = {
        np.dtype("uint8"): (2, 8),
        np.dtype("int16"): (4, 16),
        np.dtype("int32"): (8, 32),
        np.dtype("float32"): (16, 32),
        np.dtype("float64"): (64, 64),
        np.dtype("int8"): (256, 8),
        np.dtype("uint16"): (512, 16),
        np.dtype("uint32"): (768, 32),
    }
    if dtype not in mapping:
        raise ValueError(f"unsupported_nifti_dtype:{dtype}")
    return mapping[dtype]


def _spacing_xyz(metadata):
    spacing_zyx = metadata.get("spacing_zyx") or [1.0, 1.0, 1.0]
    spacing_zyx = [float(value) for value in spacing_zyx]
    return [spacing_zyx[2], spacing_zyx[1], spacing_zyx[0]]


def _canonical_spacing_unit(value):
    text = str(value or "unknown").strip().lower()
    text = text.replace("µ", "u").replace("μ", "u")
    aliases = {
        "micrometer": "micrometer",
        "micrometers": "micrometer",
        "micron": "micrometer",
        "microns": "micrometer",
        "um": "micrometer",
        "millimeter": "millimeter",
        "millimeters": "millimeter",
        "mm": "millimeter",
        "meter": "meter",
        "meters": "meter",
        "m": "meter",
    }
    return aliases.get(text, "unknown")


def _normalized_spacing(value):
    try:
        spacing = [float(item) for item in (value or [])]
    except (TypeError, ValueError):
        return [1.0, 1.0, 1.0], False
    valid = len(spacing) == 3 and all(np.isfinite(item) and item > 0 for item in spacing)
    return (spacing if valid else [1.0, 1.0, 1.0]), bool(valid)


def _spacing_matches(left, right):
    left_spacing, left_valid = _normalized_spacing(left)
    right_spacing, right_valid = _normalized_spacing(right)
    return bool(
        left_valid
        and right_valid
        and np.allclose(left_spacing, right_spacing, rtol=1e-6, atol=1e-9)
    )


def _sanitize_exchange_metadata(metadata=None, registry_record=None):
    """Return only the physical scale that every authoritative record verifies."""
    clean = dict(metadata) if isinstance(metadata, dict) else {}
    unit = _canonical_spacing_unit(clean.get("spacing_unit"))
    spacing, spacing_valid = _normalized_spacing(clean.get("spacing_zyx"))
    verified = clean.get("scale_verified") is True and unit != "unknown" and spacing_valid
    if registry_record is not None:
        record_unit = _canonical_spacing_unit(
            registry_record.get("spacing_unit") if isinstance(registry_record, dict) else None
        )
        verified = (
            verified
            and isinstance(registry_record, dict)
            and registry_record.get("scale_verified") is True
            and record_unit == unit
            and _spacing_matches(spacing, registry_record.get("spacing_zyx"))
        )
    clean["spacing_zyx"] = spacing
    clean["spacing_unit"] = unit if verified else "unknown"
    clean["scale_verified"] = bool(verified)
    return clean


def _manifest_scale_metadata(metadata):
    clean = _sanitize_exchange_metadata(metadata)
    return {
        "spacing_zyx": list(clean["spacing_zyx"]),
        "spacing_unit": clean["spacing_unit"],
        "scale_verified": clean["scale_verified"],
    }


def _reslice_exchange_metadata(reslice, fallback_metadata=None, audit_metadata=None):
    """Recover Local Axis TIFF geometry from its audited reslice record."""
    clean = dict(fallback_metadata) if isinstance(fallback_metadata, dict) else {}
    reslice = reslice if isinstance(reslice, dict) else {}
    audit_metadata = audit_metadata if isinstance(audit_metadata, dict) else {}
    params = reslice.get("reslice_params") if isinstance(reslice.get("reslice_params"), dict) else {}
    source = reslice.get("source") if isinstance(reslice.get("source"), dict) else {}
    audit_params = audit_metadata.get("reslice_params") if isinstance(audit_metadata.get("reslice_params"), dict) else {}
    audit_source = audit_metadata.get("source") if isinstance(audit_metadata.get("source"), dict) else {}
    clean["spacing_zyx"] = (
        params.get("output_spacing_zyx")
        or clean.get("spacing_zyx")
        or source.get("part_spacing_zyx")
        or [1.0, 1.0, 1.0]
    )
    record_unit = _canonical_spacing_unit(source.get("part_spacing_unit"))
    audit_unit = _canonical_spacing_unit(audit_source.get("part_spacing_unit"))
    audit_spacing = (
        audit_params.get("output_spacing_zyx")
        or audit_source.get("part_spacing_zyx")
    )
    outputs = audit_metadata.get("outputs") if isinstance(audit_metadata.get("outputs"), dict) else {}
    fallback_shape = clean.get("shape_zyx")
    audit_shape = outputs.get("image_shape_zyx")
    shape_matches = not audit_shape or [int(value) for value in audit_shape] == [int(value) for value in (fallback_shape or [])]
    clean["spacing_unit"] = record_unit
    clean["scale_verified"] = (
        source.get("part_scale_verified") is True
        and audit_source.get("part_scale_verified") is True
        and record_unit != "unknown"
        and record_unit == audit_unit
        and _spacing_matches(clean.get("spacing_zyx"), audit_spacing)
        and shape_matches
    )
    return _sanitize_exchange_metadata(clean)


def _shape_xyz(array):
    return [int(array.shape[2]), int(array.shape[1]), int(array.shape[0])]


def _read_any_volume(path, mmap_mode=None):
    abs_path = os.path.abspath(str(path))
    if volume_sidecar_exists(abs_path):
        array = load_volume_sidecar(abs_path, mmap_mode=mmap_mode)
        metadata = read_volume_metadata(abs_path)
        return array, metadata
    if os.path.exists(abs_path):
        lower = abs_path.lower()
        if lower.endswith(".nii") or lower.endswith(".nii.gz"):
            array, metadata = read_nifti_volume_with_metadata(abs_path)
            return np.asarray(array), metadata
        if mmap_mode:
            try:
                array = tifffile.memmap(abs_path, mode=mmap_mode)
            except (OSError, TypeError, ValueError):
                array = tifffile.imread(abs_path)
        else:
            array = tifffile.imread(abs_path)
        metadata = {
            "shape_zyx": [int(value) for value in np.asarray(array).shape],
            "dtype": str(np.asarray(array).dtype),
            "spacing_zyx": [1.0, 1.0, 1.0],
            "spacing_unit": "unknown",
            "orientation": "local_axis_reslice",
            "format": "tiff",
        }
        return np.asarray(array), metadata
    raise FileNotFoundError(abs_path)


def _close_memory_mapped_array(array):
    current = array
    visited = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        memory_map = getattr(current, "_mmap", None)
        if memory_map is not None:
            memory_map.close()
            return
        current = getattr(current, "base", None)


def _inspect_any_volume(path):
    abs_path = os.path.abspath(str(path))
    if volume_sidecar_exists(abs_path):
        metadata = read_volume_metadata(abs_path)
        return [int(value) for value in metadata.get("shape_zyx", [])], metadata
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(abs_path)
    if abs_path.lower().endswith((".nii", ".nii.gz")):
        array, metadata = read_nifti_volume_with_metadata(abs_path)
        return [int(value) for value in array.shape], metadata
    with tifffile.TiffFile(abs_path) as tif:
        if not tif.series:
            raise ValueError(f"tiff_series_missing:{abs_path}")
        series = tif.series[0]
        shape = [int(value) for value in series.shape]
        dtype = str(np.dtype(series.dtype))
    return shape, {
        "shape_zyx": shape,
        "dtype": dtype,
        "spacing_zyx": [1.0, 1.0, 1.0],
        "spacing_unit": "unknown",
        "scale_verified": False,
        "orientation": "local_axis_reslice",
        "format": "tiff",
    }


def _little_endian_array(array):
    volume = np.asarray(array)
    if volume.dtype.byteorder == ">":
        volume = volume.byteswap().newbyteorder("<")
    return np.ascontiguousarray(volume)


def write_ome_tiff_volume(path, array, metadata=None):
    _ensure_dir(os.path.dirname(os.path.abspath(path)))
    volume = np.asarray(array)
    exchange_metadata = _sanitize_exchange_metadata(metadata)
    ome_metadata = {"axes": "ZYX"} if volume.ndim == 3 else None
    if ome_metadata is not None and exchange_metadata["scale_verified"]:
        spacing_x, spacing_y, spacing_z = _spacing_xyz(exchange_metadata)
        ome_unit = {
            "micrometer": "µm",
            "millimeter": "mm",
            "meter": "m",
        }[exchange_metadata["spacing_unit"]]
        ome_metadata.update(
            {
                "PhysicalSizeX": spacing_x,
                "PhysicalSizeXUnit": ome_unit,
                "PhysicalSizeY": spacing_y,
                "PhysicalSizeYUnit": ome_unit,
                "PhysicalSizeZ": spacing_z,
                "PhysicalSizeZUnit": ome_unit,
            }
        )
    tifffile.imwrite(
        path,
        volume,
        ome=True,
        photometric="minisblack",
        metadata=ome_metadata,
    )
    return path


def write_tiff_volume(path, array, metadata=None):
    _ensure_dir(os.path.dirname(os.path.abspath(path)))
    exchange_metadata = _sanitize_exchange_metadata(metadata)
    tifffile.imwrite(
        path,
        np.asarray(array),
        photometric="minisblack",
        metadata={
            "axes": "ZYX",
            **_manifest_scale_metadata(exchange_metadata),
        },
    )
    return path


def write_nrrd_volume(path, array, metadata=None):
    metadata = _sanitize_exchange_metadata(metadata)
    volume = _little_endian_array(array)
    spacing_x, spacing_y, spacing_z = _spacing_xyz(metadata)
    size_x, size_y, size_z = _shape_xyz(volume)
    header_lines = [
            "NRRD0005",
            "# Complete NRRD file written by AntSleap.",
            f"type: {_dtype_to_nrrd_type(volume.dtype)}",
            "dimension: 3",
            f"sizes: {size_x} {size_y} {size_z}",
            "space: right-anterior-superior",
            f"space directions: ({spacing_x},0,0) (0,{spacing_y},0) (0,0,{spacing_z})",
            "kinds: domain domain domain",
            f"TaxaMask_scale_verified:={'true' if metadata['scale_verified'] else 'false'}",
            f"TaxaMask_spacing_unit:={metadata['spacing_unit']}",
            "encoding: raw",
            "endian: little",
            "",
            "",
    ]
    if metadata["scale_verified"]:
        nrrd_unit = {"micrometer": "um", "millimeter": "mm", "meter": "m"}[metadata["spacing_unit"]]
        header_lines.insert(8, f'space units: "{nrrd_unit}" "{nrrd_unit}" "{nrrd_unit}"')
    header = "\n".join(header_lines)
    _ensure_dir(os.path.dirname(os.path.abspath(path)))
    with open(path, "wb") as handle:
        handle.write(header.encode("ascii"))
        handle.write(volume.tobytes(order="C"))
    return path


def write_mha_volume(path, array, metadata=None):
    metadata = _sanitize_exchange_metadata(metadata)
    volume = _little_endian_array(array)
    spacing_x, spacing_y, spacing_z = _spacing_xyz(metadata)
    size_x, size_y, size_z = _shape_xyz(volume)
    header = "\n".join(
        [
            "ObjectType = Image",
            "NDims = 3",
            "BinaryData = True",
            "BinaryDataByteOrderMSB = False",
            "CompressedData = False",
            "TransformMatrix = 1 0 0 0 1 0 0 0 1",
            "Offset = 0 0 0",
            "CenterOfRotation = 0 0 0",
            "AnatomicalOrientation = RAI",
            f"ElementSpacing = {spacing_x} {spacing_y} {spacing_z}",
            f"TaxaMaskScaleVerified = {'True' if metadata['scale_verified'] else 'False'}",
            f"TaxaMaskSpacingUnit = {metadata['spacing_unit']}",
            f"DimSize = {size_x} {size_y} {size_z}",
            f"ElementType = {_dtype_to_mha_type(volume.dtype)}",
            "ElementDataFile = LOCAL",
            "",
        ]
    )
    _ensure_dir(os.path.dirname(os.path.abspath(path)))
    with open(path, "wb") as handle:
        handle.write(header.encode("ascii"))
        handle.write(volume.tobytes(order="C"))
    return path


def write_nifti_volume(path, array, metadata=None):
    metadata = _sanitize_exchange_metadata(metadata)
    volume = (
        array
        if hasattr(array, "shape")
        and hasattr(array, "dtype")
        and hasattr(array, "__getitem__")
        else np.asarray(array)
    )
    volume_dtype = np.dtype(volume.dtype)
    target_dtype = volume_dtype.newbyteorder("<") if volume_dtype.itemsize > 1 else volume_dtype
    datatype, bitpix = _dtype_to_nifti(target_dtype)
    size_x, size_y, size_z = _shape_xyz(volume)
    spacing_x, spacing_y, spacing_z = _spacing_xyz(metadata)

    header = bytearray(348)
    struct.pack_into("<i", header, 0, 348)
    struct.pack_into("<8h", header, 40, 3, size_x, size_y, size_z, 1, 1, 1, 1)
    struct.pack_into("<h", header, 70, datatype)
    struct.pack_into("<h", header, 72, bitpix)
    struct.pack_into("<8f", header, 76, 0.0, spacing_x, spacing_y, spacing_z, 1.0, 1.0, 1.0, 1.0)
    struct.pack_into("<f", header, 108, 352.0)
    struct.pack_into("<f", header, 112, 1.0)
    struct.pack_into("<h", header, 252, 1)
    struct.pack_into("<h", header, 254, 1)
    struct.pack_into("<4f", header, 280, spacing_x, 0.0, 0.0, 0.0)
    struct.pack_into("<4f", header, 296, 0.0, spacing_y, 0.0, 0.0)
    struct.pack_into("<4f", header, 312, 0.0, 0.0, spacing_z, 0.0)
    spacing_unit = metadata["spacing_unit"]
    if spacing_unit == "micrometer":
        header[123] = 3
    elif spacing_unit == "millimeter":
        header[123] = 2
    elif spacing_unit == "meter":
        header[123] = 1
    else:
        header[123] = 0
    header[344:348] = b"n+1\0"

    _ensure_dir(os.path.dirname(os.path.abspath(path)))
    def write_payload(handle):
        handle.write(bytes(header))
        handle.write(b"\0\0\0\0")
        for z0 in range(0, int(volume.shape[0]), 16):
            chunk = np.asarray(volume[z0 : z0 + 16])
            if chunk.dtype != target_dtype:
                chunk = chunk.astype(target_dtype, copy=False)
            if not chunk.flags.c_contiguous:
                chunk = np.ascontiguousarray(chunk)
            handle.write(chunk.tobytes(order="C"))

    if str(path).lower().endswith(".gz"):
        with open(path, "wb") as raw_handle:
            with gzip.GzipFile(
                filename="",
                mode="wb",
                compresslevel=6,
                fileobj=raw_handle,
                mtime=0,
            ) as handle:
                write_payload(handle)
    else:
        with open(path, "wb") as handle:
            write_payload(handle)
    return path


def read_nifti_volume_with_metadata(path):
    abs_path = os.path.abspath(str(path))
    if abs_path.lower().endswith(".gz"):
        with gzip.open(abs_path, "rb") as handle:
            data = handle.read()
    else:
        with open(abs_path, "rb") as handle:
            data = handle.read()
    if len(data) < 352:
        raise ValueError(f"invalid_nifti_file:{abs_path}")
    sizeof_hdr = struct.unpack_from("<i", data, 0)[0]
    endian = "<"
    if sizeof_hdr != 348:
        sizeof_hdr_be = struct.unpack_from(">i", data, 0)[0]
        if sizeof_hdr_be == 348:
            endian = ">"
        else:
            raise ValueError(f"invalid_nifti_header:{abs_path}:{sizeof_hdr}")
    dims = struct.unpack_from(f"{endian}8h", data, 40)
    if int(dims[0]) < 3:
        raise ValueError(f"nifti_volume_must_be_3d:{abs_path}:{dims[0]}")
    size_x, size_y, size_z = int(dims[1]), int(dims[2]), int(dims[3])
    datatype = struct.unpack_from(f"{endian}h", data, 70)[0]
    pixdim = struct.unpack_from(f"{endian}8f", data, 76)
    vox_offset = int(round(struct.unpack_from(f"{endian}f", data, 108)[0]))
    xyzt_units = data[123]
    dtype_map = {
        2: np.dtype("uint8"),
        4: np.dtype("int16"),
        8: np.dtype("int32"),
        16: np.dtype("float32"),
        64: np.dtype("float64"),
        256: np.dtype("int8"),
        512: np.dtype("uint16"),
        768: np.dtype("uint32"),
    }
    dtype = dtype_map.get(int(datatype))
    if dtype is None:
        raise ValueError(f"unsupported_nifti_datatype:{datatype}")
    if endian == ">":
        dtype = dtype.newbyteorder(">")
    count = size_x * size_y * size_z
    start = max(352, vox_offset)
    needed = start + count * dtype.itemsize
    if len(data) < needed:
        raise ValueError(f"truncated_nifti_data:{abs_path}:{len(data)}:{needed}")
    array = np.frombuffer(data, dtype=dtype, count=count, offset=start).reshape((size_z, size_y, size_x))
    spacing_xyz = [float(pixdim[1] or 1.0), float(pixdim[2] or 1.0), float(pixdim[3] or 1.0)]
    unit_code = int(xyzt_units) & 0x07
    spacing_unit = (
        "micrometer"
        if unit_code == 3
        else "millimeter"
        if unit_code == 2
        else "meter"
        if unit_code == 1
        else "unknown"
    )
    metadata = {
        "shape_zyx": [int(value) for value in np.asarray(array).shape],
        "dtype": str(np.asarray(array).dtype),
        "spacing_zyx": [spacing_xyz[2], spacing_xyz[1], spacing_xyz[0]],
        "spacing_unit": spacing_unit,
        "scale_verified": spacing_unit != "unknown",
        "orientation": "local_axis_reslice",
        "format": "nifti",
    }
    return np.asarray(array), metadata


def read_nifti_volume(path):
    array, _metadata = read_nifti_volume_with_metadata(path)
    return array


_FORMAT_WRITERS = {
    "ome_tiff": ("ome_tiff", ".ome.tif", write_ome_tiff_volume),
    "tiff": ("tiff", ".tif", write_tiff_volume),
    "nrrd": ("nrrd", ".nrrd", write_nrrd_volume),
    "mha": ("mha", ".mha", write_mha_volume),
    "nifti": ("nifti", ".nii", write_nifti_volume),
}


def export_tif_training_dataset(project_manager, output_dir, specimen_ids=None, formats=None, require_train_ready=True):
    if not isinstance(project_manager, TifProjectManager):
        raise TypeError("project_manager_must_be_tif_project_manager")
    selected_formats = list(formats or ["ome_tiff", "nrrd", "mha", "nifti"])
    unknown = sorted(set(selected_formats) - SUPPORTED_TIF_EXPORT_FORMATS)
    if unknown:
        raise ValueError(f"unsupported_tif_export_formats:{','.join(unknown)}")

    out_root = os.path.abspath(str(output_dir))
    volumes_dir = os.path.join(out_root, "volumes")
    labels_dir = os.path.join(out_root, "labels")
    materials_dir = os.path.join(out_root, "materials")
    for folder in (volumes_dir, labels_dir, materials_dir):
        _ensure_dir(folder)

    ids = [str(item) for item in specimen_ids] if specimen_ids else [
        item.get("specimen_id") for item in project_manager.project_data.get("specimens", [])
    ]
    exported = []
    warnings = []
    for specimen_id in ids:
        specimen = project_manager.get_specimen(specimen_id, default=None)
        if specimen is None:
            raise KeyError(f"unknown_specimen_id:{specimen_id}")
        readiness = project_manager.evaluate_train_ready(specimen_id)
        if require_train_ready and not readiness["train_ready"]:
            raise ValueError(f"specimen_not_train_ready:{specimen_id}:{','.join(readiness['reasons'])}")
        if not readiness["train_ready"]:
            warnings.append({"specimen_id": specimen_id, "warning": "exported_not_train_ready", "reasons": readiness["reasons"]})

        working_record = specimen.get("working_volume") or {}
        label_record = (specimen.get("labels") or {}).get("manual_truth") or {}
        image_path = project_manager.to_absolute(working_record.get("path", ""))
        label_path = project_manager.to_absolute(label_record.get("path", ""))
        if not volume_sidecar_exists(image_path):
            raise FileNotFoundError(image_path)
        if not volume_sidecar_exists(label_path):
            raise FileNotFoundError(label_path)
        image = load_volume_sidecar(image_path)
        label = load_volume_sidecar(label_path)
        if list(image.shape) != list(label.shape):
            raise ValueError(f"image_label_shape_mismatch:{specimen_id}:{image.shape}:{label.shape}")
        image_meta = _sanitize_exchange_metadata(
            read_volume_metadata(image_path),
            working_record,
        )
        label_meta = _sanitize_exchange_metadata(
            read_volume_metadata(label_path),
            label_record,
        )
        safe = _safe_id(specimen_id)

        material_rel = specimen.get("material_map", "")
        material_export = ""
        if material_rel:
            material_abs = project_manager.to_absolute(material_rel)
            if os.path.exists(material_abs):
                material_export = os.path.join(materials_dir, f"{safe}_material_map.json")
                shutil.copy2(material_abs, material_export)

        image_exports = {}
        label_exports = {}
        for fmt in selected_formats:
            format_id, ext, writer = _FORMAT_WRITERS[fmt]
            image_out = os.path.join(volumes_dir, f"{safe}_image{ext}")
            label_out = os.path.join(labels_dir, f"{safe}_manual_truth{ext}")
            writer(image_out, image, image_meta)
            writer(label_out, label, label_meta)
            image_exports[format_id] = os.path.relpath(image_out, out_root).replace("\\", "/")
            label_exports[format_id] = os.path.relpath(label_out, out_root).replace("\\", "/")

        exported.append(
            {
                "specimen_id": specimen_id,
                "modality": specimen.get("modality", "unknown"),
                "shape_zyx": [int(value) for value in image.shape],
                **_manifest_scale_metadata(image_meta),
                "label_scale": _manifest_scale_metadata(label_meta),
                "exchange_metadata": {
                    "image": _manifest_scale_metadata(image_meta),
                    "label": _manifest_scale_metadata(label_meta),
                },
                "image_exports": image_exports,
                "label_exports": label_exports,
                "label_role": "manual_truth",
                "material_map": os.path.relpath(material_export, out_root).replace("\\", "/") if material_export else "",
                "source_project": os.path.abspath(project_manager.current_project_path or ""),
            }
        )

    manifest = {
        "schema_version": TIF_TRAINING_EXPORT_SCHEMA_VERSION,
        "created_at": _now_iso(),
        "project_json": os.path.abspath(project_manager.current_project_path or ""),
        "formats": selected_formats,
        "specimens": exported,
        "warnings": warnings,
    }
    manifest_path = os.path.join(out_root, "tif_training_export_manifest.json")
    _write_json(manifest_path, manifest)
    return {
        "manifest": manifest,
        "manifest_path": manifest_path,
        "exported_count": len(exported),
    }


def export_tif_part_training_dataset(project_manager, output_dir, part_refs=None, formats=None, require_train_ready=True):
    if not isinstance(project_manager, TifProjectManager):
        raise TypeError("project_manager_must_be_tif_project_manager")
    selected_formats = list(formats or ["ome_tiff", "nrrd", "mha", "nifti"])
    unknown = sorted(set(selected_formats) - SUPPORTED_TIF_EXPORT_FORMATS)
    if unknown:
        raise ValueError(f"unsupported_tif_export_formats:{','.join(unknown)}")

    out_root = os.path.abspath(str(output_dir))
    volumes_dir = os.path.join(out_root, "part_volumes")
    labels_dir = os.path.join(out_root, "part_labels")
    schemas_dir = os.path.join(out_root, "label_schemas")
    for folder in (volumes_dir, labels_dir, schemas_dir):
        _ensure_dir(folder)

    refs = []
    if part_refs is not None:
        for ref in part_refs:
            if not isinstance(ref, dict):
                continue
            refs.append(
                {
                    "specimen_id": str(ref.get("specimen_id") or ""),
                    "part_id": str(ref.get("part_id") or ""),
                    "reslice_id": str(ref.get("reslice_id") or ""),
                }
            )
    else:
        for item in project_manager.list_train_ready_parts():
            refs.append(
                {
                    "specimen_id": item["readiness"]["specimen_id"],
                    "part_id": item["readiness"]["part_id"],
                    "reslice_id": item["readiness"].get("reslice_id", ""),
                }
            )
    if not refs:
        raise ValueError("no_part_training_samples")

    exported = []
    warnings = []
    schema_exports = {}
    for ref in refs:
        specimen_id = ref["specimen_id"]
        part_id = ref["part_id"]
        readiness = project_manager.evaluate_part_train_ready(specimen_id, part_id, ref.get("reslice_id", ""))
        if require_train_ready and not readiness["train_ready"]:
            raise ValueError(f"part_not_train_ready:{specimen_id}:{part_id}:{','.join(readiness['reasons'])}")
        if not readiness["train_ready"]:
            warnings.append({"specimen_id": specimen_id, "part_id": part_id, "warning": "exported_not_train_ready", "reasons": readiness["reasons"]})
        specimen = project_manager.get_specimen(specimen_id)
        part = project_manager.get_part(specimen_id, part_id)
        reslice = project_manager.get_part_reslice(specimen_id, part_id, readiness.get("reslice_id", ""), default=None)
        if reslice is None:
            raise ValueError(f"part_reslice_missing:{specimen_id}:{part_id}:{readiness.get('reslice_id', '')}")
        image_path = project_manager.to_absolute(reslice.get("image_path", ""))
        label_record = readiness.get("label_record") or project_manager.part_label_record(
            specimen_id,
            part_id,
            "manual_truth",
            reslice_id=readiness.get("reslice_id", ""),
        )
        label_path = project_manager.to_absolute(label_record.get("path", ""))
        image, image_meta = _read_any_volume(image_path)
        label, label_meta = _read_any_volume(label_path)
        if list(image.shape) != list(label.shape):
            raise ValueError(f"part_image_label_shape_mismatch:{specimen_id}:{part_id}:{image.shape}:{label.shape}")
        reslice_audit = {}
        reslice_metadata_path = project_manager.to_absolute(reslice.get("metadata_path", ""))
        if reslice_metadata_path and os.path.isfile(reslice_metadata_path):
            try:
                with open(reslice_metadata_path, "r", encoding="utf-8") as handle:
                    loaded_audit = json.load(handle)
                if isinstance(loaded_audit, dict):
                    reslice_audit = loaded_audit
            except (OSError, ValueError, TypeError):
                reslice_audit = {}
        image_meta = _reslice_exchange_metadata(reslice, image_meta, reslice_audit)
        label_meta = _sanitize_exchange_metadata(label_meta, label_record)

        safe = _safe_id(f"{specimen_id}_{part_id}_{reslice.get('reslice_id', '')}")
        image_exports = {}
        label_exports = {}
        for fmt in selected_formats:
            format_id, ext, writer = _FORMAT_WRITERS[fmt]
            image_out = os.path.join(volumes_dir, f"{safe}_image{ext}")
            label_out = os.path.join(labels_dir, f"{safe}_manual_truth{ext}")
            writer(image_out, image, image_meta)
            writer(label_out, label, label_meta)
            image_exports[format_id] = os.path.relpath(image_out, out_root).replace("\\", "/")
            label_exports[format_id] = os.path.relpath(label_out, out_root).replace("\\", "/")

        schema_id = readiness.get("label_schema_id", "")
        if schema_id and schema_id not in schema_exports:
            schema = project_manager.get_label_schema(schema_id, default={})
            schema_path = os.path.join(schemas_dir, f"{_safe_id(schema_id)}.json")
            _write_json(schema_path, schema)
            schema_exports[schema_id] = os.path.relpath(schema_path, out_root).replace("\\", "/")

        training = part.get("training") or {}
        exported.append(
            {
                "sample_id": safe,
                "specimen_id": specimen_id,
                "specimen_display_name": specimen.get("display_name", specimen_id),
                "part_id": part_id,
                "user_defined_part_name": training.get("user_defined_part_name") or part.get("display_name") or part_id,
                "reslice_id": reslice.get("reslice_id", ""),
                "reslice_record": {
                    "image_path": reslice.get("image_path", ""),
                    "metadata_path": reslice.get("metadata_path", ""),
                    "local_frame": reslice.get("local_frame", {}),
                    "reslice_params": reslice.get("reslice_params", {}),
                },
                "shape_zyx": [int(value) for value in image.shape],
                **_manifest_scale_metadata(image_meta),
                "label_scale": _manifest_scale_metadata(label_meta),
                "exchange_metadata": {
                    "image": _manifest_scale_metadata(image_meta),
                    "label": _manifest_scale_metadata(label_meta),
                },
                "image_exports": image_exports,
                "label_exports": label_exports,
                "label_role": "manual_truth",
                "label_schema_id": schema_id,
                "label_schema": schema_exports.get(schema_id, ""),
                "source_project": os.path.abspath(project_manager.current_project_path or ""),
            }
        )

    manifest = {
        "schema_version": TIF_PART_TRAINING_EXPORT_SCHEMA_VERSION,
        "created_at": _now_iso(),
        "project_json": os.path.abspath(project_manager.current_project_path or ""),
        "formats": selected_formats,
        "samples": exported,
        "warnings": warnings,
        "safety": {
            "input_scope": "part_reslice",
            "label_role": "manual_truth",
            "allow_editable_ai_result_as_training_label": False,
        },
    }
    manifest_path = os.path.join(out_root, "tif_part_training_export_manifest.json")
    _write_json(manifest_path, manifest)
    return {
        "manifest": manifest,
        "manifest_path": manifest_path,
        "exported_count": len(exported),
    }


def export_nnunet_dataset(
    project_manager,
    output_dir,
    specimen_ids=None,
    dataset_name="Dataset001_AntSleap",
    require_train_ready=True,
    file_ending=".nii",
    materialization_cache=None,
    asset_references=None,
):
    return _export_nnunet_dataset_direct(
        project_manager,
        output_dir,
        specimen_ids=specimen_ids,
        dataset_name=dataset_name,
        require_train_ready=require_train_ready,
        file_ending=file_ending,
        materialization_cache=materialization_cache,
        asset_references=asset_references,
    )


def _asset_refs_by_owner(asset_references, owner_key):
    return [
        dict(item)
        for item in (asset_references or [])
        if isinstance(item, dict) and str(item.get("owner_key") or "") == str(owner_key)
    ]


def _materialize_nnunet_nifti(
    destination,
    array,
    metadata,
    *,
    materialization_cache=None,
    source_assets=None,
    artifact_kind,
    effective_config=None,
):
    writer = lambda path: write_nifti_volume(path, array, metadata)
    if materialization_cache is None or not source_assets:
        writer(destination)
        return None
    return materialization_cache.materialize(
        destination=destination,
        suffix=".nii.gz" if str(destination).lower().endswith(".nii.gz") else ".nii",
        source_assets=source_assets,
        format_id=f"nnunet_nifti_{artifact_kind}",
        writer=writer,
        spacing_zyx=(metadata or {}).get("spacing_zyx"),
        axis_order="zyx",
        compression={"id": "gzip", "level": 6}
        if str(destination).lower().endswith(".gz")
        else {},
        effective_config={
            "artifact_kind": str(artifact_kind),
            "spacing_unit": str((metadata or {}).get("spacing_unit") or "unknown"),
            "scale_verified": (metadata or {}).get("scale_verified") is True,
            **dict(effective_config or {}),
        },
        generator="tif_export.write_nifti_volume",
    )


def _export_nnunet_dataset_direct(
    project_manager,
    output_dir,
    specimen_ids=None,
    dataset_name="Dataset001_AntSleap",
    require_train_ready=True,
    file_ending=".nii",
    materialization_cache=None,
    asset_references=None,
):
    if not isinstance(project_manager, TifProjectManager):
        raise TypeError("project_manager_must_be_tif_project_manager")
    file_ending = str(file_ending or ".nii").strip()
    if file_ending not in {".nii", ".nii.gz"}:
        raise ValueError(f"unsupported_nnunet_file_ending:{file_ending}")
    root = os.path.abspath(str(output_dir))
    images_tr = os.path.join(root, "imagesTr")
    labels_tr = os.path.join(root, "labelsTr")
    _ensure_dir(images_tr)
    _ensure_dir(labels_tr)
    training = []
    materializations = []
    ids = [str(item) for item in specimen_ids] if specimen_ids else [
        item.get("specimen_id") for item in project_manager.project_data.get("specimens", [])
    ]
    for idx, specimen_id in enumerate(ids, start=1):
        source_specimen = project_manager.get_specimen(specimen_id, default=None)
        if source_specimen is None:
            raise KeyError(f"unknown_specimen_id:{specimen_id}")
        readiness = project_manager.evaluate_train_ready(specimen_id)
        if require_train_ready and not readiness["train_ready"]:
            raise ValueError(
                f"specimen_not_train_ready:{specimen_id}:{','.join(readiness['reasons'])}"
            )
        image_record = source_specimen.get("working_volume") or {}
        label_record = (source_specimen.get("labels") or {}).get("manual_truth") or {}
        image_path = project_manager.to_absolute(image_record.get("path", ""))
        label_path = project_manager.to_absolute(label_record.get("path", ""))
        if not volume_sidecar_exists(image_path):
            raise FileNotFoundError(image_path)
        if not volume_sidecar_exists(label_path):
            raise FileNotFoundError(label_path)
        image = load_volume_sidecar(image_path, mmap_mode="r")
        label = load_volume_sidecar(label_path, mmap_mode="r")
        try:
            if list(image.shape) != list(label.shape):
                raise ValueError(
                    f"image_label_shape_mismatch:{specimen_id}:{image.shape}:{label.shape}"
                )
            image_meta = _sanitize_exchange_metadata(
                read_volume_metadata(image_path), image_record
            )
            label_meta = _sanitize_exchange_metadata(
                read_volume_metadata(label_path), label_record
            )
            case_id = f"antsleap_{idx:04d}_{_safe_id(specimen_id)}"
            image_dst = os.path.join(images_tr, f"{case_id}_0000{file_ending}")
            label_dst = os.path.join(labels_tr, f"{case_id}{file_ending}")
            image_materialization = _materialize_nnunet_nifti(
                image_dst,
                image,
                image_meta,
                materialization_cache=materialization_cache,
                source_assets=_asset_refs_by_owner(
                    asset_references, f"specimen.{specimen_id}.working"
                ),
                artifact_kind="image",
            )
            label_materialization = _materialize_nnunet_nifti(
                label_dst,
                label,
                label_meta,
                materialization_cache=materialization_cache,
                source_assets=_asset_refs_by_owner(
                    asset_references, f"specimen.{specimen_id}.manual_truth"
                ),
                artifact_kind="label",
                effective_config={"label_id_mode": "identity"},
            )
            materializations.extend(
                item
                for item in (image_materialization, label_materialization)
                if item is not None
            )
            training.append(
                {
                    "case_id": case_id,
                    "specimen_id": specimen_id,
                    "image": os.path.relpath(image_dst, root).replace("\\", "/"),
                    "label": os.path.relpath(label_dst, root).replace("\\", "/"),
                    "spacing_zyx": image_meta.get("spacing_zyx", []),
                    "spacing_unit": image_meta.get("spacing_unit", "unknown"),
                    "scale_verified": image_meta.get("scale_verified") is True,
                }
            )
        finally:
            for volume in (image, label):
                _close_memory_mapped_array(volume)
    dataset_json = {
        "channel_names": {"0": "volume"},
        "labels": {"background": 0, "foreground": 1},
        "numTraining": len(training),
        "file_ending": file_ending,
        "name": dataset_name,
        "description": "AntSleap exported nnU-Net style dataset. Material IDs remain in label volumes; update labels mapping for a specific backend when needed.",
    }
    _write_json(os.path.join(root, "dataset.json"), dataset_json)
    manifest = {
        "schema_version": NNUNET_DATASET_SCHEMA_VERSION,
        "created_at": _now_iso(),
        "dataset_name": dataset_name,
        "source_manifest": "",
        "training": training,
        "materializations": materializations,
        "notes": [
            "NIfTI files are written without requiring nibabel; verify orientation expectations in the target nnU-Net environment.",
            "AntSleap preserves material IDs. Backend-specific class remapping should be explicit and audited.",
        ],
    }
    manifest_path = os.path.join(root, "nnunet_manifest.json")
    _write_json(manifest_path, manifest)
    return {
        "manifest": manifest,
        "manifest_path": manifest_path,
        "exported_count": len(training),
        "materializations": materializations,
    }


def _schema_labels_for_part_export(project_manager, samples):
    label_signature = None
    schema_ids = []
    canonical_labels = []
    for sample in samples:
        schema_id = str(sample.get("label_schema_id") or "").strip()
        if not schema_id:
            raise ValueError(f"part_nnunet_label_schema_missing:{sample.get('sample_id', '')}")
        schema = project_manager.get_label_schema(schema_id, default=None)
        labels = (schema or {}).get("labels") if isinstance(schema, dict) else []
        if not labels:
            raise ValueError(f"part_nnunet_label_schema_missing:{schema_id}")
        signature = []
        for label in labels:
            if not isinstance(label, dict):
                continue
            try:
                label_id = int(label.get("id"))
            except (TypeError, ValueError):
                continue
            if label_id < 0:
                continue
            name = str(label.get("name") or f"label_{label_id}")
            display_name = str(label.get("display_name") or name or f"Label {label_id}")
            signature.append((label_id, name, display_name))
        signature.sort(key=lambda item: item[0])
        if not signature:
            raise ValueError(f"part_nnunet_label_schema_empty:{schema_id}")
        comparison_signature = [(label_id, name) for label_id, name, _display_name in signature]
        if label_signature is None:
            label_signature = comparison_signature
            canonical_labels = [
                {
                    "id": label_id,
                    "name": name,
                    "display_name": display_name,
                }
                for label_id, name, display_name in signature
            ]
        elif comparison_signature != label_signature:
            raise ValueError(f"mixed_part_label_schemas_not_supported:{','.join(sorted(set(schema_ids + [schema_id])))}")
        if schema_id not in schema_ids:
            schema_ids.append(schema_id)
    label_ids = {int(item["id"]) for item in canonical_labels}
    if 0 not in label_ids:
        canonical_labels.insert(0, {"id": 0, "name": "background", "display_name": "Background"})
    return schema_ids, canonical_labels


def _preflight_part_nnunet_labels(project_manager, part_refs=None, require_train_ready=True):
    refs = []
    if part_refs is not None:
        for ref in part_refs:
            if not isinstance(ref, dict):
                continue
            refs.append(
                {
                    "specimen_id": str(ref.get("specimen_id") or ""),
                    "part_id": str(ref.get("part_id") or ""),
                    "reslice_id": str(ref.get("reslice_id") or ""),
                }
            )
    else:
        for item in project_manager.list_train_ready_parts():
            refs.append(
                {
                    "specimen_id": item["readiness"]["specimen_id"],
                    "part_id": item["readiness"]["part_id"],
                    "reslice_id": item["readiness"].get("reslice_id", ""),
                }
            )
    if not refs:
        raise ValueError("no_part_training_samples")
    samples = []
    for ref in refs:
        specimen_id = ref["specimen_id"]
        part_id = ref["part_id"]
        readiness = project_manager.evaluate_part_train_ready(specimen_id, part_id, ref.get("reslice_id", ""))
        if require_train_ready and not readiness["train_ready"]:
            raise ValueError(f"part_not_train_ready:{specimen_id}:{part_id}:{','.join(readiness['reasons'])}")
        samples.append(
            {
                "sample_id": _safe_id(f"{specimen_id}_{part_id}_{readiness.get('reslice_id', '')}"),
                "label_schema_id": readiness.get("label_schema_id", ""),
            }
        )
    return _schema_labels_for_part_export(project_manager, samples)


def _nnunet_labels_mapping(labels):
    mapping = {}
    used_names = set()
    for label in sorted(labels, key=lambda item: int(item.get("id", 0))):
        label_id = int(label.get("id", 0))
        base = "background" if label_id == 0 else _safe_label_name(label.get("name") or label.get("display_name"), f"label_{label_id}")
        name = base
        suffix = 2
        while name in used_names:
            name = f"{base}_{suffix}"
            suffix += 1
        used_names.add(name)
        mapping[name] = label_id
    if "background" not in mapping:
        mapping = {"background": 0, **mapping}
    return mapping


def _compact_nnunet_label_plan(labels):
    source_ids = sorted({int(item.get("id", 0)) for item in labels if int(item.get("id", 0)) >= 0})
    if 0 not in source_ids:
        source_ids.insert(0, 0)
    source_to_nnunet = {}
    nnunet_to_source = {}
    for target_id, source_id in enumerate(source_ids):
        source_to_nnunet[int(source_id)] = int(target_id)
        nnunet_to_source[int(target_id)] = int(source_id)
    return source_to_nnunet, nnunet_to_source


def remap_label_ids(array, mapping, dtype=None):
    volume = np.asarray(array)
    clean_mapping = {}
    for key, value in (mapping or {}).items():
        try:
            clean_mapping[int(key)] = int(value)
        except (TypeError, ValueError):
            continue
    if not clean_mapping:
        return volume.astype(dtype or volume.dtype, copy=True)
    out_dtype = np.dtype(dtype or np.uint16)
    output = np.zeros(volume.shape, dtype=out_dtype)
    for source_id, target_id in clean_mapping.items():
        if source_id == 0 and target_id == 0:
            continue
        output[volume == source_id] = target_id
    return output


class _ChunkRemappedLabelVolume:
    def __init__(self, source, mapping, dtype):
        self.source = source
        self.mapping = {
            int(source_id): int(target_id)
            for source_id, target_id in (mapping or {}).items()
        }
        self.dtype = np.dtype(dtype)
        self.shape = tuple(int(value) for value in source.shape)

    def __getitem__(self, key):
        source_chunk = np.asarray(self.source[key])
        output = np.zeros(source_chunk.shape, dtype=self.dtype)
        for source_id, target_id in self.mapping.items():
            if source_id == 0 and target_id == 0:
                continue
            output[source_chunk == source_id] = target_id
        return output


def _collect_part_nnunet_samples(
    project_manager,
    part_refs=None,
    *,
    require_train_ready=True,
):
    refs = []
    if part_refs is not None:
        for ref in part_refs:
            if isinstance(ref, dict):
                refs.append(
                    {
                        "specimen_id": str(ref.get("specimen_id") or ""),
                        "part_id": str(ref.get("part_id") or ""),
                        "reslice_id": str(ref.get("reslice_id") or ""),
                    }
                )
    else:
        for item in project_manager.list_train_ready_parts():
            refs.append(
                {
                    "specimen_id": item["readiness"]["specimen_id"],
                    "part_id": item["readiness"]["part_id"],
                    "reslice_id": item["readiness"].get("reslice_id", ""),
                }
            )
    if not refs:
        raise ValueError("no_part_training_samples")

    samples = []
    for ref in refs:
        specimen_id = ref["specimen_id"]
        part_id = ref["part_id"]
        readiness = project_manager.evaluate_part_train_ready(
            specimen_id, part_id, ref.get("reslice_id", "")
        )
        if require_train_ready and not readiness["train_ready"]:
            raise ValueError(
                f"part_not_train_ready:{specimen_id}:{part_id}:"
                f"{','.join(readiness['reasons'])}"
            )
        specimen = project_manager.get_specimen(specimen_id)
        part = project_manager.get_part(specimen_id, part_id)
        reslice_id = str(readiness.get("reslice_id") or "")
        reslice = project_manager.get_part_reslice(
            specimen_id, part_id, reslice_id, default=None
        )
        if reslice is None:
            raise ValueError(
                f"part_reslice_missing:{specimen_id}:{part_id}:{reslice_id}"
            )
        image_path = project_manager.to_absolute(reslice.get("image_path", ""))
        label_record = readiness.get("label_record") or project_manager.part_label_record(
            specimen_id,
            part_id,
            "manual_truth",
            reslice_id=reslice_id,
        )
        label_path = project_manager.to_absolute(label_record.get("path", ""))
        image_shape, image_meta = _inspect_any_volume(image_path)
        label_shape, label_meta = _inspect_any_volume(label_path)
        if image_shape != label_shape:
            raise ValueError(
                f"part_image_label_shape_mismatch:{specimen_id}:{part_id}:"
                f"{image_shape}:{label_shape}"
            )
        reslice_audit = {}
        metadata_path = project_manager.to_absolute(reslice.get("metadata_path", ""))
        if metadata_path and os.path.isfile(metadata_path):
            try:
                with open(metadata_path, "r", encoding="utf-8") as handle:
                    loaded = json.load(handle)
                if isinstance(loaded, dict):
                    reslice_audit = loaded
            except (OSError, TypeError, ValueError):
                reslice_audit = {}
        image_meta = _reslice_exchange_metadata(reslice, image_meta, reslice_audit)
        label_meta = _sanitize_exchange_metadata(label_meta, label_record)
        training = part.get("training") or {}
        sample_id = _safe_id(f"{specimen_id}_{part_id}_{reslice_id}")
        owner_prefix = f"reslice.{specimen_id}.{part_id}.{reslice_id}"
        samples.append(
            {
                "sample_id": sample_id,
                "specimen_id": specimen_id,
                "specimen_display_name": specimen.get("display_name", specimen_id),
                "part_id": part_id,
                "user_defined_part_name": training.get("user_defined_part_name")
                or part.get("display_name")
                or part_id,
                "reslice_id": reslice_id,
                "label_schema_id": readiness.get("label_schema_id", ""),
                "shape_zyx": image_shape,
                **_manifest_scale_metadata(image_meta),
                "label_scale": _manifest_scale_metadata(label_meta),
                "_image_path": image_path,
                "_label_path": label_path,
                "_image_meta": image_meta,
                "_label_meta": label_meta,
                "_image_owner_key": f"{owner_prefix}.image",
                "_label_owner_key": f"{owner_prefix}.manual_truth",
            }
        )
    return samples


def export_tif_part_nnunet_dataset(
    project_manager,
    output_dir,
    part_refs=None,
    dataset_name="Dataset001_TaxaMaskTifPart",
    require_train_ready=True,
    file_ending=".nii",
    label_id_mode="preserve",
    split_mode="all_train",
    include_images_ts=False,
    materialization_cache=None,
    asset_references=None,
):
    preflight_schema_ids, preflight_labels = _preflight_part_nnunet_labels(
        project_manager,
        part_refs=part_refs,
        require_train_ready=require_train_ready,
    )
    samples = _collect_part_nnunet_samples(
        project_manager,
        part_refs=part_refs,
        require_train_ready=require_train_ready,
    )
    root = os.path.abspath(str(output_dir))
    images_tr = os.path.join(root, "imagesTr")
    labels_tr = os.path.join(root, "labelsTr")
    _ensure_dir(images_tr)
    _ensure_dir(labels_tr)

    schema_ids, labels = _schema_labels_for_part_export(project_manager, samples)
    if schema_ids != preflight_schema_ids or labels != preflight_labels:
        raise ValueError("part_nnunet_label_schema_changed_during_export")
    file_ending = str(file_ending or ".nii").strip()
    if file_ending not in {".nii", ".nii.gz"}:
        raise ValueError(f"unsupported_nnunet_file_ending:{file_ending}")
    label_id_mode = str(label_id_mode or "preserve").strip().lower()
    if label_id_mode not in {"preserve", "compact"}:
        raise ValueError(f"unsupported_nnunet_label_id_mode:{label_id_mode}")
    split_mode = str(split_mode or "all_train").strip().lower()
    if split_mode not in {"all_train", "leave_one_val"}:
        raise ValueError(f"unsupported_nnunet_split_mode:{split_mode}")
    labels_mapping = _nnunet_labels_mapping(labels)
    source_to_nnunet, nnunet_to_source = _compact_nnunet_label_plan(labels)
    if label_id_mode == "preserve":
        source_ids = sorted({int(item.get("id", 0)) for item in labels if int(item.get("id", 0)) >= 0})
        if 0 not in source_ids:
            source_ids.insert(0, 0)
        source_to_nnunet = {int(value): int(value) for value in source_ids}
        nnunet_to_source = {int(value): int(value) for value in source_ids}
    if label_id_mode == "compact":
        source_labels = {int(item.get("id", 0)): item for item in labels}
        compact_mapping = {}
        used_names = set()
        for source_id, target_id in source_to_nnunet.items():
            item = source_labels.get(source_id, {"id": source_id, "name": f"label_{source_id}"})
            base = "background" if target_id == 0 else _safe_label_name(item.get("name") or item.get("display_name"), f"label_{target_id}")
            name = base
            suffix = 2
            while name in used_names:
                name = f"{base}_{suffix}"
                suffix += 1
            used_names.add(name)
            compact_mapping[name] = int(target_id)
        labels_mapping = compact_mapping
    training = []
    materializations = []
    for idx, sample in enumerate(samples, start=1):
        case_id = f"taxamask_part_{idx:04d}_{_safe_id(sample.get('specimen_id'))}_{_safe_id(sample.get('part_id'))}"
        image_dst = os.path.join(images_tr, f"{case_id}_0000{file_ending}")
        label_dst = os.path.join(labels_tr, f"{case_id}{file_ending}")
        image, _loaded_image_meta = _read_any_volume(
            sample["_image_path"], mmap_mode="r"
        )
        source_label, _loaded_label_meta = _read_any_volume(
            sample["_label_path"], mmap_mode="r"
        )
        image_meta = sample["_image_meta"]
        label_meta = sample["_label_meta"]
        try:
            if list(image.shape) != sample.get("shape_zyx") or list(
                source_label.shape
            ) != sample.get("shape_zyx"):
                raise ValueError(
                    f"part_volume_changed_during_export:{sample.get('sample_id', '')}"
                )
            image_materialization = _materialize_nnunet_nifti(
                image_dst,
                image,
                image_meta,
                materialization_cache=materialization_cache,
                source_assets=_asset_refs_by_owner(
                    asset_references, sample["_image_owner_key"]
                ),
                artifact_kind="image",
                effective_config={"input_scope": "part_reslice"},
            )
            label = source_label
            if label_id_mode == "compact":
                label = _ChunkRemappedLabelVolume(
                    source_label,
                    source_to_nnunet,
                    label_dtype_for_max_id(max(source_to_nnunet.values())),
                )
            label_materialization = _materialize_nnunet_nifti(
                label_dst,
                label,
                label_meta,
                materialization_cache=materialization_cache,
                source_assets=_asset_refs_by_owner(
                    asset_references, sample["_label_owner_key"]
                ),
                artifact_kind="label",
                effective_config={
                    "input_scope": "part_reslice",
                    "label_id_mode": label_id_mode,
                    "source_to_nnunet": {
                        str(key): int(value)
                        for key, value in sorted(source_to_nnunet.items())
                    },
                },
            )
            materializations.extend(
                item
                for item in (image_materialization, label_materialization)
                if item is not None
            )
            training.append(
                {
                    "case_id": case_id,
                    "sample_id": sample.get("sample_id", ""),
                    "specimen_id": sample.get("specimen_id", ""),
                    "part_id": sample.get("part_id", ""),
                    "reslice_id": sample.get("reslice_id", ""),
                    "user_defined_part_name": sample.get("user_defined_part_name", ""),
                    "label_schema_id": sample.get("label_schema_id", ""),
                    "image": os.path.relpath(image_dst, root).replace("\\", "/"),
                    "label": os.path.relpath(label_dst, root).replace("\\", "/"),
                    "shape_zyx": sample.get("shape_zyx", []),
                    "spacing_zyx": sample.get("spacing_zyx", []),
                    "spacing_unit": sample.get("spacing_unit", "unknown"),
                    "scale_verified": sample.get("scale_verified") is True,
                }
            )
        finally:
            _close_memory_mapped_array(image)
            _close_memory_mapped_array(source_label)

    if include_images_ts:
        images_ts = os.path.join(root, "imagesTs")
        _ensure_dir(images_ts)
    split_payload = {"train": [item["case_id"] for item in training], "val": []}
    if split_mode == "leave_one_val" and len(training) > 1:
        split_payload["val"] = [training[-1]["case_id"]]
        split_payload["train"] = [item["case_id"] for item in training[:-1]]
    splits_path = os.path.join(root, "splits_final.json")
    _write_json(splits_path, [split_payload])

    dataset_json = {
        "channel_names": {"0": "part_reslice_volume"},
        "labels": labels_mapping,
        "numTraining": len(training),
        "file_ending": file_ending,
        "name": dataset_name,
        "description": "TaxaMask part-level TIF volume-segmentation dataset exported for nnU-Net v2. Labels come from the active part label schema.",
        "reference": "TaxaMask TIF part-reslice training loop",
        "licence": "research_project_local",
        "release": "0.1",
    }
    dataset_json_path = os.path.join(root, "dataset.json")
    _write_json(dataset_json_path, dataset_json)
    manifest = {
        "schema_version": NNUNET_PART_DATASET_SCHEMA_VERSION,
        "created_at": _now_iso(),
        "dataset_name": dataset_name,
        "dataset_json": os.path.relpath(dataset_json_path, root).replace("\\", "/"),
        "source_manifest": "",
        "splits_final": os.path.relpath(splits_path, root).replace("\\", "/"),
        "file_ending": file_ending,
        "label_id_mode": label_id_mode,
        "label_id_mapping": {
            "source_to_nnunet": {str(key): int(value) for key, value in source_to_nnunet.items()},
            "nnunet_to_source": {str(key): int(value) for key, value in nnunet_to_source.items()},
        },
        "label_schema_ids": schema_ids,
        "labels": labels,
        "training": training,
        "materializations": materializations,
        "safety": {
            "input_scope": "part_reslice",
            "label_role": "manual_truth",
            "allow_editable_ai_result_as_training_label": False,
            "reject_mixed_label_schemas": True,
        },
        "notes": [
            "NIfTI files are written without requiring nibabel; verify orientation expectations in the target nnU-Net environment.",
            "If label_id_mode is compact, nnU-Net labels are consecutive and the manifest records how to restore TaxaMask label IDs.",
        ],
    }
    manifest_path = os.path.join(root, "nnunet_part_manifest.json")
    _write_json(manifest_path, manifest)
    return {
        "manifest": manifest,
        "manifest_path": manifest_path,
        "exported_count": len(training),
        "materializations": materializations,
    }


def export_monai_dataset(project_manager, output_dir, specimen_ids=None, require_train_ready=True):
    export = export_tif_training_dataset(
        project_manager,
        output_dir,
        specimen_ids=specimen_ids,
        formats=["nifti", "nrrd", "mha"],
        require_train_ready=require_train_ready,
    )
    root = os.path.abspath(str(output_dir))
    training = []
    for specimen in export["manifest"].get("specimens", []):
        training.append(
            {
                "specimen_id": specimen["specimen_id"],
                "image": specimen["image_exports"]["nifti"],
                "label": specimen["label_exports"]["nifti"],
                "image_nrrd": specimen["image_exports"]["nrrd"],
                "label_nrrd": specimen["label_exports"]["nrrd"],
                "image_mha": specimen["image_exports"]["mha"],
                "label_mha": specimen["label_exports"]["mha"],
                "material_map": specimen.get("material_map", ""),
                "spacing_zyx": specimen.get("spacing_zyx", []),
                "spacing_unit": specimen.get("spacing_unit", "unknown"),
                "scale_verified": specimen.get("scale_verified") is True,
            }
        )
    datalist = {"training": training, "validation": []}
    datalist_path = os.path.join(root, "monai_datalist.json")
    _write_json(datalist_path, datalist)
    manifest = {
        "schema_version": MONAI_DATASET_SCHEMA_VERSION,
        "created_at": _now_iso(),
        "source_manifest": os.path.relpath(export["manifest_path"], root).replace("\\", "/"),
        "datalist": os.path.basename(datalist_path),
        "training_count": len(training),
        "notes": [
            "MONAI datalist paths are relative to this export directory.",
            "Use the material_map files for audited class naming and trainable-material decisions.",
        ],
    }
    manifest_path = os.path.join(root, "monai_manifest.json")
    _write_json(manifest_path, manifest)
    return {"manifest": manifest, "manifest_path": manifest_path, "exported_count": len(training)}
