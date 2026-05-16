import os
import shutil
from datetime import datetime

import numpy as np
import tifffile

from .tif_materials import write_material_map
from .tif_project import TifProjectManager
from .tif_volume_io import create_empty_label_sidecar_like, write_volume_sidecar


TIF_STACK_IMPORT_REPORT_SCHEMA_VERSION = "ant3d_tif_stack_import_report_v1"
TIF_STACK_IMPORT_ADAPTER_VERSION = "tif_stack_import_adapter_v1"


def _now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _safe_filename(value):
    text = str(value or "").strip()
    clean = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in text)
    return clean.strip("_") or "source.tif"


def _read_tif_stack(path):
    array = tifffile.imread(path)
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


def _read_tif_metadata(path):
    metadata = {
        "page_count": 0,
        "series_shape": [],
        "axes": "",
        "dtype": "",
        "spacing_zyx": [1.0, 1.0, 1.0],
        "spacing_unit": "micrometer",
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
                        # TIFF resolution is pixels per unit. Without a reliable physical unit
                        # conversion, keep micrometer as the project default and record raw values.
                        metadata["x_resolution_raw"] = x_value
                        metadata["y_resolution_raw"] = y_value
                        metadata["warnings"].append("physical_spacing_not_inferred_from_tiff_resolution")
                except Exception:
                    metadata["warnings"].append("tiff_resolution_metadata_unreadable")
    return metadata


def _ratio_to_float(value):
    if isinstance(value, tuple) and len(value) == 2 and value[1]:
        return float(value[0]) / float(value[1])
    return float(value)


def import_tif_stack(
    project_manager,
    tif_path,
    specimen_id,
    modality="unknown",
    metadata_ref="",
    material_map=None,
    copy_source=True,
):
    if not isinstance(project_manager, TifProjectManager):
        raise TypeError("project_manager_must_be_tif_project_manager")
    source_path = os.path.abspath(str(tif_path))
    if not os.path.exists(source_path):
        raise FileNotFoundError(source_path)
    if os.path.splitext(source_path)[1].lower() not in {".tif", ".tiff"}:
        raise ValueError(f"not_tif_file:{source_path}")

    specimen = project_manager.create_specimen_scaffold(
        specimen_id,
        material_map=material_map or {},
        modality=modality,
        metadata_ref=metadata_ref,
    )
    specimen_root_rel = project_manager.specimen_dir(specimen_id)
    specimen_root_abs = project_manager.to_absolute(specimen_root_rel)

    raw_rel = os.path.join(specimen_root_rel, "source", "raw", _safe_filename(os.path.basename(source_path))).replace("\\", "/")
    raw_abs = project_manager.to_absolute(raw_rel)
    if copy_source:
        os.makedirs(os.path.dirname(raw_abs), exist_ok=True)
        if os.path.abspath(source_path) != os.path.abspath(raw_abs):
            shutil.copy2(source_path, raw_abs)
    else:
        raw_rel = source_path

    tif_metadata = _read_tif_metadata(source_path)
    warnings = list(tif_metadata.get("warnings", []))
    volume = _read_tif_stack(source_path)
    image_rel = os.path.join(specimen_root_rel, "working", "image.ome.zarr").replace("\\", "/")
    image_abs = project_manager.to_absolute(image_rel)
    image_meta = write_volume_sidecar(
        image_abs,
        volume,
        role="working_image",
        spacing_zyx=tif_metadata.get("spacing_zyx", [1.0, 1.0, 1.0]),
        spacing_unit=tif_metadata.get("spacing_unit", "micrometer"),
        orientation=tif_metadata.get("orientation", "unknown"),
        source_format="tif_stack",
        extra_metadata={
            "source_path": project_manager.to_relative(raw_rel),
            "import_adapter": TIF_STACK_IMPORT_ADAPTER_VERSION,
            "note": "Lightweight recoverable sidecar; not complete OME-NGFF metadata.",
        },
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
    edit_meta = create_empty_label_sidecar_like(image_abs, working_edit_abs, role="working_edit")
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
        save=False,
    )

    material_map_rel = os.path.join(specimen_root_rel, "material_map.json").replace("\\", "/")
    material_map_payload = write_material_map(project_manager.to_absolute(material_map_rel), material_map or {}, source=(material_map or {}).get("source", "manual") if isinstance(material_map, dict) else "manual")

    specimen = project_manager.get_specimen(specimen_id)
    specimen["source"]["raw_tif"] = project_manager.to_relative(raw_rel)
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
            "raw_tif": project_manager.to_relative(raw_rel),
            "working_image": image_rel,
            "working_edit": working_edit_rel,
            "material_map": material_map_rel,
        },
        "shapes": {
            "tif_stack_zyx": image_meta["shape_zyx"],
            "working_image_zyx": image_meta["shape_zyx"],
            "working_edit_zyx": edit_meta["shape_zyx"],
        },
        "dtype": {
            "working_image": image_meta["dtype"],
            "working_edit": edit_meta["dtype"],
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
        "warnings": warnings,
        "errors": [],
    }
    report_rel = os.path.join(specimen_root_rel, "working", "import_report.json").replace("\\", "/")
    report_abs = project_manager.to_absolute(report_rel)
    os.makedirs(os.path.dirname(report_abs), exist_ok=True)
    with open(report_abs, "w", encoding="utf-8") as handle:
        import json

        json.dump(report, handle, ensure_ascii=False, indent=2)
    specimen["working_volume"]["import_report"] = report_rel
    project_manager.save_project()

    return {
        "specimen": specimen,
        "report": report,
        "report_path": report_abs,
    }
