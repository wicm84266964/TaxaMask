import json
import os
import shutil
import struct
from datetime import datetime

import numpy as np
import tifffile

from .tif_project import TifProjectManager
from .tif_volume_io import load_volume_sidecar, read_volume_metadata, volume_sidecar_exists


TIF_TRAINING_EXPORT_SCHEMA_VERSION = "ant3d_tif_training_export_v1"
SUPPORTED_TIF_EXPORT_FORMATS = {"ome_tiff", "tiff", "nrrd", "mha", "nifti"}
NNUNET_DATASET_SCHEMA_VERSION = "ant3d_nnunet_dataset_v1"
MONAI_DATASET_SCHEMA_VERSION = "ant3d_monai_dataset_v1"


def _now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _safe_id(value):
    text = str(value or "").strip()
    clean = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in text)
    return clean.strip("_") or "specimen"


def _ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def _write_json(path, payload):
    _ensure_dir(os.path.dirname(os.path.abspath(path)))
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


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


def _shape_xyz(array):
    return [int(array.shape[2]), int(array.shape[1]), int(array.shape[0])]


def _little_endian_array(array):
    volume = np.asarray(array)
    if volume.dtype.byteorder == ">":
        volume = volume.byteswap().newbyteorder("<")
    return np.ascontiguousarray(volume)


def write_ome_tiff_volume(path, array, metadata=None):
    _ensure_dir(os.path.dirname(os.path.abspath(path)))
    volume = np.asarray(array)
    tifffile.imwrite(
        path,
        volume,
        ome=True,
        photometric="minisblack",
        metadata={"axes": "ZYX"} if volume.ndim == 3 else None,
    )
    return path


def write_tiff_volume(path, array, metadata=None):
    _ensure_dir(os.path.dirname(os.path.abspath(path)))
    tifffile.imwrite(path, np.asarray(array), photometric="minisblack")
    return path


def write_nrrd_volume(path, array, metadata=None):
    metadata = metadata or {}
    volume = _little_endian_array(array)
    spacing_x, spacing_y, spacing_z = _spacing_xyz(metadata)
    size_x, size_y, size_z = _shape_xyz(volume)
    header = "\n".join(
        [
            "NRRD0005",
            "# Complete NRRD file written by AntSleap.",
            f"type: {_dtype_to_nrrd_type(volume.dtype)}",
            "dimension: 3",
            f"sizes: {size_x} {size_y} {size_z}",
            "space: right-anterior-superior",
            f"space directions: ({spacing_x},0,0) (0,{spacing_y},0) (0,0,{spacing_z})",
            "kinds: domain domain domain",
            "encoding: raw",
            "endian: little",
            "",
            "",
        ]
    )
    _ensure_dir(os.path.dirname(os.path.abspath(path)))
    with open(path, "wb") as handle:
        handle.write(header.encode("ascii"))
        handle.write(volume.tobytes(order="C"))
    return path


def write_mha_volume(path, array, metadata=None):
    metadata = metadata or {}
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
    metadata = metadata or {}
    volume = _little_endian_array(array)
    datatype, bitpix = _dtype_to_nifti(volume.dtype)
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
    header[123] = 3 if str(metadata.get("spacing_unit", "micrometer")).lower() in {"micrometer", "micron", "um", "µm"} else 2
    header[344:348] = b"n+1\0"

    _ensure_dir(os.path.dirname(os.path.abspath(path)))
    with open(path, "wb") as handle:
        handle.write(header)
        handle.write(b"\0\0\0\0")
        handle.write(volume.tobytes(order="C"))
    return path


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
        image_meta = read_volume_metadata(image_path)
        label_meta = read_volume_metadata(label_path)
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


def export_nnunet_dataset(project_manager, output_dir, specimen_ids=None, dataset_name="Dataset001_AntSleap", require_train_ready=True):
    export = export_tif_training_dataset(
        project_manager,
        output_dir,
        specimen_ids=specimen_ids,
        formats=["nifti"],
        require_train_ready=require_train_ready,
    )
    root = os.path.abspath(str(output_dir))
    images_tr = os.path.join(root, "imagesTr")
    labels_tr = os.path.join(root, "labelsTr")
    _ensure_dir(images_tr)
    _ensure_dir(labels_tr)
    training = []
    for idx, specimen in enumerate(export["manifest"].get("specimens", []), start=1):
        case_id = f"antsleap_{idx:04d}_{_safe_id(specimen['specimen_id'])}"
        image_src = os.path.join(root, specimen["image_exports"]["nifti"])
        label_src = os.path.join(root, specimen["label_exports"]["nifti"])
        image_dst = os.path.join(images_tr, f"{case_id}_0000.nii")
        label_dst = os.path.join(labels_tr, f"{case_id}.nii")
        shutil.copy2(image_src, image_dst)
        shutil.copy2(label_src, label_dst)
        training.append(
            {
                "case_id": case_id,
                "specimen_id": specimen["specimen_id"],
                "image": os.path.relpath(image_dst, root).replace("\\", "/"),
                "label": os.path.relpath(label_dst, root).replace("\\", "/"),
            }
        )
    dataset_json = {
        "channel_names": {"0": "volume"},
        "labels": {"background": 0, "foreground": 1},
        "numTraining": len(training),
        "file_ending": ".nii",
        "name": dataset_name,
        "description": "AntSleap exported nnU-Net style dataset. Material IDs remain in label volumes; update labels mapping for a specific backend when needed.",
    }
    _write_json(os.path.join(root, "dataset.json"), dataset_json)
    manifest = {
        "schema_version": NNUNET_DATASET_SCHEMA_VERSION,
        "created_at": _now_iso(),
        "dataset_name": dataset_name,
        "source_manifest": os.path.relpath(export["manifest_path"], root).replace("\\", "/"),
        "training": training,
        "notes": [
            "NIfTI files are written without requiring nibabel; verify orientation expectations in the target nnU-Net environment.",
            "AntSleap preserves material IDs. Backend-specific class remapping should be explicit and audited.",
        ],
    }
    manifest_path = os.path.join(root, "nnunet_manifest.json")
    _write_json(manifest_path, manifest)
    return {"manifest": manifest, "manifest_path": manifest_path, "exported_count": len(training)}


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
