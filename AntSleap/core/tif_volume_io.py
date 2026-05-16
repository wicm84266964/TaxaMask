import json
import os
import shutil
from datetime import datetime

import numpy as np


VOLUME_SIDECAR_SCHEMA_VERSION = "ant3d_volume_sidecar_v1"
VOLUME_SIDECAR_FORMAT = "ant3d_volume_sidecar"
VOLUME_ARRAY_FILENAME = "array.npy"
VOLUME_METADATA_FILENAME = "metadata.json"
OME_NGFF_VERSION = "0.4"
OME_ZARR_ARRAY_PATH = "0"


def _now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _shape_zyx(array):
    if array.ndim != 3:
        raise ValueError(f"volume_must_be_3d:{array.ndim}")
    return [int(array.shape[0]), int(array.shape[1]), int(array.shape[2])]


def _normalize_spacing(spacing_zyx):
    if spacing_zyx is None:
        return [1.0, 1.0, 1.0]
    if len(spacing_zyx) != 3:
        raise ValueError("spacing_zyx_must_have_3_values")
    return [float(value) for value in spacing_zyx]


def _default_chunk_shape(shape_zyx):
    z, y, x = [int(value) for value in shape_zyx]
    return [max(1, min(z, 64)), max(1, min(y, 256)), max(1, min(x, 256))]


def _json_scalar(value):
    if isinstance(value, np.generic):
        return value.item()
    return value


def _zarr_dtype(dtype):
    np_dtype = np.dtype(dtype)
    if np_dtype.byteorder == "=":
        np_dtype = np_dtype.newbyteorder("<" if np.little_endian else ">")
    return np_dtype.str


def _write_json(path, payload):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _write_ome_ngff_zarr(sidecar_path, volume, role, spacing_zyx, spacing_unit, chunk_shape_zyx=None):
    """Write a minimal OME-NGFF v0.4 Zarr v2 store beside the legacy npy copy."""
    path = os.path.abspath(str(sidecar_path))
    array_dir = os.path.join(path, OME_ZARR_ARRAY_PATH)
    if os.path.exists(array_dir):
        shutil.rmtree(array_dir)
    os.makedirs(array_dir, exist_ok=True)

    shape = _shape_zyx(volume)
    chunks = [int(value) for value in (chunk_shape_zyx or _default_chunk_shape(shape))]
    chunks = [max(1, min(int(chunks[idx]), int(shape[idx]))) for idx in range(3)]
    dtype = np.dtype(volume.dtype)
    fill_value = _json_scalar(np.array(0, dtype=dtype)[()])

    _write_json(os.path.join(path, ".zgroup"), {"zarr_format": 2})
    _write_json(
        os.path.join(array_dir, ".zarray"),
        {
            "zarr_format": 2,
            "shape": shape,
            "chunks": chunks,
            "dtype": _zarr_dtype(dtype),
            "compressor": None,
            "fill_value": fill_value,
            "order": "C",
            "filters": None,
            "dimension_separator": ".",
        },
    )

    axes = [
        {"name": "z", "type": "space", "unit": str(spacing_unit or "micrometer")},
        {"name": "y", "type": "space", "unit": str(spacing_unit or "micrometer")},
        {"name": "x", "type": "space", "unit": str(spacing_unit or "micrometer")},
    ]
    _write_json(
        os.path.join(path, ".zattrs"),
        {
            "multiscales": [
                {
                    "version": OME_NGFF_VERSION,
                    "name": os.path.basename(path),
                    "axes": axes,
                    "datasets": [
                        {
                            "path": OME_ZARR_ARRAY_PATH,
                            "coordinateTransformations": [
                                {
                                    "type": "scale",
                                    "scale": [float(value) for value in spacing_zyx],
                                }
                            ],
                        }
                    ],
                    "type": "labels" if "label" in str(role).lower() or str(role).lower() in {"manual_truth", "working_edit", "model_draft"} else "image",
                }
            ],
            "ant3d": {
                "role": str(role or "unknown"),
                "axes": "zyx",
            },
        },
    )

    volume_c = np.ascontiguousarray(volume)
    for z0 in range(0, shape[0], chunks[0]):
        for y0 in range(0, shape[1], chunks[1]):
            for x0 in range(0, shape[2], chunks[2]):
                chunk = np.ascontiguousarray(
                    volume_c[
                        z0 : min(z0 + chunks[0], shape[0]),
                        y0 : min(y0 + chunks[1], shape[1]),
                        x0 : min(x0 + chunks[2], shape[2]),
                    ]
                )
                chunk_name = f"{z0 // chunks[0]}.{y0 // chunks[1]}.{x0 // chunks[2]}"
                with open(os.path.join(array_dir, chunk_name), "wb") as handle:
                    handle.write(chunk.tobytes(order="C"))
    return {
        "ome_ngff_version": OME_NGFF_VERSION,
        "zarr_format": 2,
        "zarr_array_path": OME_ZARR_ARRAY_PATH,
        "zarr_chunks_zyx": chunks,
    }


def metadata_path(sidecar_path):
    return os.path.join(str(sidecar_path), VOLUME_METADATA_FILENAME)


def array_path(sidecar_path):
    return os.path.join(str(sidecar_path), VOLUME_ARRAY_FILENAME)


def write_volume_sidecar(
    sidecar_path,
    array,
    role,
    spacing_zyx=None,
    spacing_unit="micrometer",
    orientation="unknown",
    source_format="",
    extra_metadata=None,
    write_ome_zarr=True,
    chunk_shape_zyx=None,
):
    volume = np.asarray(array)
    shape = _shape_zyx(volume)
    path = os.path.abspath(str(sidecar_path))
    os.makedirs(path, exist_ok=True)
    np.save(array_path(path), volume, allow_pickle=False)

    now = _now_iso()
    spacing = _normalize_spacing(spacing_zyx)
    ngff_metadata = {}
    ome_ngff_complete = False
    storage = "npy"
    if write_ome_zarr:
        ngff_metadata = _write_ome_ngff_zarr(
            path,
            volume,
            role=role,
            spacing_zyx=spacing,
            spacing_unit=spacing_unit,
            chunk_shape_zyx=chunk_shape_zyx,
        )
        ome_ngff_complete = True
        storage = "npy+ome_zarr_v2"
    metadata = {
        "schema_version": VOLUME_SIDECAR_SCHEMA_VERSION,
        "format": VOLUME_SIDECAR_FORMAT,
        "storage": storage,
        "ome_ngff_complete": ome_ngff_complete,
        "role": str(role or "unknown"),
        "axes": "zyx",
        "shape_zyx": shape,
        "dtype": str(volume.dtype),
        "spacing_zyx": spacing,
        "spacing_unit": str(spacing_unit or "micrometer"),
        "orientation": str(orientation or "unknown"),
        "source_format": str(source_format or ""),
        "created_at": now,
        "updated_at": now,
    }
    metadata.update(ngff_metadata)
    if isinstance(extra_metadata, dict):
        for key, value in extra_metadata.items():
            if key not in {"schema_version", "format", "storage", "shape_zyx", "dtype"}:
                metadata[key] = value

    with open(metadata_path(path), "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2)
    return metadata


def read_volume_metadata(sidecar_path):
    with open(metadata_path(sidecar_path), "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("volume_metadata_not_object")
    if payload.get("schema_version") != VOLUME_SIDECAR_SCHEMA_VERSION:
        raise ValueError(f"unsupported_volume_sidecar_schema:{payload.get('schema_version')}")
    return payload


def volume_sidecar_exists(sidecar_path):
    return os.path.exists(metadata_path(sidecar_path)) and os.path.exists(array_path(sidecar_path))


def load_volume_sidecar(sidecar_path, mmap_mode=None):
    read_volume_metadata(sidecar_path)
    return np.load(array_path(sidecar_path), mmap_mode=mmap_mode, allow_pickle=False)


def save_volume_array(sidecar_path, array):
    metadata = read_volume_metadata(sidecar_path)
    volume = np.asarray(array)
    if [int(value) for value in volume.shape] != [int(value) for value in metadata.get("shape_zyx", [])]:
        raise ValueError(f"volume_shape_change_not_allowed:{volume.shape}:{metadata.get('shape_zyx')}")
    np.save(array_path(sidecar_path), volume, allow_pickle=False)
    metadata["dtype"] = str(volume.dtype)
    metadata["updated_at"] = _now_iso()
    if metadata.get("ome_ngff_complete"):
        ngff_metadata = _write_ome_ngff_zarr(
            sidecar_path,
            volume,
            role=metadata.get("role", "unknown"),
            spacing_zyx=metadata.get("spacing_zyx", [1.0, 1.0, 1.0]),
            spacing_unit=metadata.get("spacing_unit", "micrometer"),
            chunk_shape_zyx=metadata.get("zarr_chunks_zyx"),
        )
        metadata.update(ngff_metadata)
    with open(metadata_path(sidecar_path), "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2)
    return metadata


def create_empty_label_sidecar_like(image_sidecar_path, label_sidecar_path, dtype="uint16", fill_value=0, role="working_edit"):
    image_meta = read_volume_metadata(image_sidecar_path)
    shape = tuple(int(value) for value in image_meta["shape_zyx"])
    array = np.full(shape, fill_value, dtype=np.dtype(dtype))
    return write_volume_sidecar(
        label_sidecar_path,
        array,
        role=role,
        spacing_zyx=image_meta.get("spacing_zyx"),
        spacing_unit=image_meta.get("spacing_unit", "micrometer"),
        orientation=image_meta.get("orientation", "unknown"),
        source_format="empty_label_like",
    )


def copy_volume_sidecar(source_sidecar_path, target_sidecar_path, role=None):
    source = os.path.abspath(str(source_sidecar_path))
    target = os.path.abspath(str(target_sidecar_path))
    if not volume_sidecar_exists(source):
        raise FileNotFoundError(source)
    if os.path.exists(target):
        shutil.rmtree(target)
    shutil.copytree(source, target)
    if role:
        metadata = read_volume_metadata(target)
        metadata["role"] = str(role)
        metadata["updated_at"] = _now_iso()
        with open(metadata_path(target), "w", encoding="utf-8") as handle:
            json.dump(metadata, handle, ensure_ascii=False, indent=2)
        return metadata
    return read_volume_metadata(target)
