import json
import os
import re
import shutil
from datetime import datetime

import numpy as np
import tifffile

from .tif_materials import write_material_map
from .tif_project import TifProjectManager
from .tif_volume_io import copy_volume_sidecar, write_volume_sidecar


AMIRA_IMPORT_REPORT_SCHEMA_VERSION = "ant3d_amira_import_report_v1"
AMIRA_IMPORT_ADAPTER_VERSION = "amira_import_adapter_v1"


_AMIRA_DTYPE_MAP = {
    "byte": np.uint8,
    "ubyte": np.uint8,
    "short": np.int16,
    "ushort": np.uint16,
    "int": np.int32,
    "uint": np.uint32,
    "float": np.float32,
    "double": np.float64,
}


def _now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _safe_filename(value):
    text = str(value or "").strip()
    clean = "".join(ch if ch.isalnum() or ch in ("-", "_", ".", " ") else "_" for ch in text)
    return clean.strip("_") or "source"


def _read_text(path):
    with open(path, "r", encoding="latin1", errors="replace") as handle:
        return handle.read()


def _normalize_ref_name(path_or_name):
    name = os.path.basename(str(path_or_name or "")).lower()
    stem, ext = os.path.splitext(name)
    stem = re.sub(r"\(\d+\)$", "", stem)
    return stem + ext


def scan_amira_directory(source_dir):
    root = os.path.abspath(str(source_dir))
    if not os.path.isdir(root):
        raise NotADirectoryError(root)

    files = []
    for entry in os.listdir(root):
        full = os.path.join(root, entry)
        if os.path.isfile(full):
            files.append(full)

    by_ext = {}
    for path in files:
        by_ext.setdefault(os.path.splitext(path)[1].lower(), []).append(path)

    return {
        "source_dir": root,
        "hx": _single_or_empty(by_ext.get(".hx", [])),
        "raw_tif": _single_or_empty((by_ext.get(".tif", []) or []) + (by_ext.get(".tiff", []) or [])),
        "labels": _single_or_empty(by_ext.get(".labels", [])),
        "resampled": _single_or_empty(by_ext.get(".resampled", [])),
        "material_statistics": _single_or_empty(by_ext.get(".materialstatistics", [])),
        "surf": _single_or_empty(by_ext.get(".surf", [])),
        "files": files,
    }


def _single_or_empty(paths):
    return os.path.abspath(paths[0]) if len(paths or []) == 1 else ""


def parse_hx_connections(hx_path):
    text = _read_text(hx_path)
    load_refs = re.findall(r'\[\s*load[^\]]+"([^"]+)"\s*\]\s+setLabel\s+"([^"]+)"', text)
    image_connections = re.findall(r'"([^"]+\.labels)"\s+ImageData connect\s+"([^"]+\.resampled)"', text)
    return {
        "load_refs": [{"path": item[0], "label": item[1]} for item in load_refs],
        "image_connections": [{"labels": item[0], "image": item[1]} for item in image_connections],
    }


def resolve_amira_files(source_dir):
    scan = scan_amira_directory(source_dir)
    hx_info = parse_hx_connections(scan["hx"]) if scan.get("hx") else {"load_refs": [], "image_connections": []}
    files = list(scan.get("files", []))

    labels_ref = ""
    resampled_ref = ""
    if hx_info["image_connections"]:
        labels_ref = hx_info["image_connections"][0]["labels"]
        resampled_ref = hx_info["image_connections"][0]["image"]

    labels_path = _match_reference(files, labels_ref, ".labels") or scan.get("labels", "")
    resampled_path = _match_reference(files, resampled_ref, ".resampled") or scan.get("resampled", "")

    return {
        "source_dir": scan["source_dir"],
        "hx": scan.get("hx", ""),
        "raw_tif": scan.get("raw_tif", ""),
        "labels": labels_path,
        "resampled": resampled_path,
        "material_statistics": scan.get("material_statistics", ""),
        "surf": scan.get("surf", ""),
        "hx_connections": hx_info,
    }


def _match_reference(files, reference, required_ext):
    if not reference:
        return ""
    wanted = _normalize_ref_name(reference)
    for path in files:
        if os.path.splitext(path)[1].lower() != required_ext:
            continue
        if _normalize_ref_name(path) == wanted:
            return os.path.abspath(path)
    wanted_stem = os.path.splitext(wanted)[0]
    for path in files:
        if os.path.splitext(path)[1].lower() != required_ext:
            continue
        candidate_stem = os.path.splitext(_normalize_ref_name(path))[0]
        if candidate_stem.startswith(wanted_stem) or wanted_stem.startswith(candidate_stem):
            return os.path.abspath(path)
    return ""


def read_amira_header(path):
    with open(path, "rb") as handle:
        data = handle.read(1024 * 512)
    marker = data.find(b"# Data section follows")
    if marker == -1:
        raise ValueError(f"amira_data_section_marker_missing:{path}")
    data_label = data.find(b"@1", marker)
    if data_label == -1:
        raise ValueError(f"amira_data_label_missing:{path}")
    line_end = data.find(b"\n", data_label)
    if line_end == -1:
        raise ValueError(f"amira_data_label_line_unterminated:{path}")
    header_bytes = data[:data_label]
    header_text = header_bytes.decode("latin1", errors="replace")
    binary_offset = line_end + 1
    return {
        "header_text": header_text,
        "binary_offset": binary_offset,
        "lattice_xyz": _parse_lattice_xyz(header_text),
        "shape_zyx": _xyz_to_zyx(_parse_lattice_xyz(header_text)),
        "dtype": _parse_lattice_dtype(header_text),
        "encoding": _parse_encoding(header_text),
        "spacing_zyx": _parse_spacing_zyx(header_text),
        "spacing_unit": _parse_spacing_unit(header_text),
        "orientation": "unknown",
        "materials": parse_materials_from_labels_header(header_text),
    }


def _parse_lattice_xyz(header_text):
    match = re.search(r"define\s+Lattice\s+(\d+)\s+(\d+)\s+(\d+)", header_text)
    if not match:
        raise ValueError("amira_lattice_definition_missing")
    return [int(match.group(1)), int(match.group(2)), int(match.group(3))]


def _xyz_to_zyx(shape_xyz):
    return [int(shape_xyz[2]), int(shape_xyz[1]), int(shape_xyz[0])]


def _parse_lattice_dtype(header_text):
    match = re.search(r"Lattice\s*\{\s*(\w+)\s+\w+\s*\}", header_text)
    if not match:
        raise ValueError("amira_lattice_dtype_missing")
    dtype_name = match.group(1).lower()
    dtype = _AMIRA_DTYPE_MAP.get(dtype_name)
    if dtype is None:
        raise ValueError(f"unsupported_amira_dtype:{dtype_name}")
    return np.dtype(dtype)


def _parse_encoding(header_text):
    match = re.search(r"@\d+\(([^,\)]+)", header_text)
    return match.group(1) if match else ""


def _parse_spacing_unit(header_text):
    if re.search(r'Coordinates\s+"?µm"?', header_text) or re.search(r'Coordinates\s+"?Âµm"?', header_text):
        return "micrometer"
    return "micrometer"


def _parse_spacing_zyx(header_text):
    match = re.search(r'Parameter:voxelSize\s+"0\s+([0-9eE+\-.]+)\s+1\s+([0-9eE+\-.]+)\s+2\s+([0-9eE+\-.]+)', header_text)
    if match:
        x, y, z = [float(match.group(index)) for index in (1, 2, 3)]
        return [z, y, x]
    match = re.search(r"BoundingBox\s+([0-9eE+\-.]+)\s+([0-9eE+\-.]+)\s+([0-9eE+\-.]+)\s+([0-9eE+\-.]+)\s+([0-9eE+\-.]+)\s+([0-9eE+\-.]+)", header_text)
    try:
        if match:
            x0, x1, y0, y1, z0, z1 = [float(match.group(index)) for index in range(1, 7)]
            x, y, z = _parse_lattice_xyz(header_text)
            return [
                abs(z1 - z0) / max(z - 1, 1),
                abs(y1 - y0) / max(y - 1, 1),
                abs(x1 - x0) / max(x - 1, 1),
            ]
    except Exception:
        pass
    return [1.0, 1.0, 1.0]


def parse_materials_from_labels_header(header_text):
    materials_block = _extract_named_block(header_text, "Materials")
    if not materials_block:
        return []
    materials = []
    for name, block in _iter_named_blocks(materials_block):
        id_match = re.search(r"\bId\s+(\d+)", block)
        material_id = int(id_match.group(1)) if id_match else None
        display_match = re.search(r'\bName\s+"([^"]+)"', block)
        display_name = display_match.group(1) if display_match else name
        color_match = re.search(r"\bColor\s+([0-9eE+\-.]+)\s+([0-9eE+\-.]+)\s+([0-9eE+\-.]+)", block)
        color = _rgb_to_hex([float(color_match.group(i)) for i in (1, 2, 3)]) if color_match else ""
        materials.append(
            {
                "id": material_id,
                "name": name,
                "display_name": display_name,
                "color": color,
                "source_name": name,
            }
        )
    return materials


def _iter_named_blocks(text):
    blocks = []
    index = 0
    while index < len(text):
        match = re.search(r"\b([A-Za-z0-9_.-]+)\s*\{", text[index:])
        if not match:
            break
        name = match.group(1)
        open_index = index + match.end() - 1
        depth = 0
        cursor = open_index
        while cursor < len(text):
            if text[cursor] == "{":
                depth += 1
            elif text[cursor] == "}":
                depth -= 1
                if depth == 0:
                    blocks.append((name, text[open_index + 1 : cursor]))
                    index = cursor + 1
                    break
            cursor += 1
        else:
            break
    return blocks


def _extract_named_block(text, name):
    start_match = re.search(r"\b" + re.escape(name) + r"\s*\{", text)
    if not start_match:
        return ""
    start = start_match.end()
    depth = 1
    index = start
    while index < len(text):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:index]
        index += 1
    return ""


def _rgb_to_hex(values):
    rgb = []
    for value in values:
        clipped = max(0.0, min(1.0, float(value)))
        rgb.append(int(round(clipped * 255)))
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def parse_material_statistics(path, header_materials=None):
    if not path or not os.path.exists(path):
        return []
    text = _read_text(path)
    names = _parse_ascii_byte_section_as_strings(text, "@2")
    labels = _parse_numeric_section(text, "@3", int)
    counts = _parse_numeric_section(text, "@4", int)
    header_by_name = {item.get("name"): item for item in header_materials or []}
    explicit_id_by_name = {item.get("name"): item for item in header_materials or [] if item.get("id") is not None}

    materials = []
    for index, name in enumerate(names):
        if index >= len(labels):
            continue
        material_id = int(labels[index])
        header = explicit_id_by_name.get(name) or header_by_name.get(name, {})
        materials.append(
            {
                "id": material_id,
                "name": name,
                "display_name": header.get("display_name") or name,
                "color": header.get("color") or "",
                "trainable": material_id != 0,
                "source_name": name,
                "voxel_count": int(counts[index]) if index < len(counts) else None,
            }
        )
    return materials


def _section_text(text, marker):
    data_start = text.find("# Data section follows")
    search_start = data_start if data_start != -1 else 0
    start = text.find(marker, search_start)
    if start == -1:
        return ""
    line_end = text.find("\n", start)
    if line_end == -1:
        return ""
    next_marker = re.search(r"\n@\d+", text[line_end + 1 :])
    if next_marker:
        end = line_end + 1 + next_marker.start()
    else:
        end = len(text)
    return text[line_end:end]


def _parse_numeric_section(text, marker, cast):
    section = _section_text(text, marker)
    values = []
    for token in re.findall(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", section):
        try:
            values.append(cast(float(token)) if cast is int else cast(token))
        except Exception:
            continue
    return values


def _parse_ascii_byte_section_as_strings(text, marker):
    values = _parse_numeric_section(text, marker, int)
    raw = bytes(max(0, min(255, value)) for value in values)
    return [chunk.decode("latin1", errors="replace") for chunk in raw.split(b"\0") if chunk]


def read_amira_volume(path):
    header = read_amira_header(path)
    expected = int(np.prod(header["shape_zyx"]))
    dtype = header["dtype"]
    if header["encoding"]:
        if header["encoding"] != "HxByteRLE":
            raise ValueError(f"unsupported_amira_encoding:{header['encoding']}")
        with open(path, "rb") as handle:
            handle.seek(header["binary_offset"])
            compressed = handle.read()
        array = decode_hxbyterle(compressed, expected, dtype=dtype)
    else:
        with open(path, "rb") as handle:
            handle.seek(header["binary_offset"])
            array = np.fromfile(handle, dtype=dtype, count=expected)
        if array.size != expected:
            raise ValueError(f"amira_volume_size_mismatch:{array.size}:{expected}")
    return array.reshape(tuple(header["shape_zyx"])), header


def decode_hxbyterle(data, expected_size, dtype=np.uint8):
    raw = bytes(data)
    result = np.empty(int(expected_size), dtype=dtype)
    in_index = 0
    out_index = 0
    while in_index < len(raw) and out_index < expected_size:
        control = raw[in_index]
        in_index += 1
        if control > 127:
            count = control & 0x7F
            end = in_index + count
            if end > len(raw):
                raise ValueError("hxbyterle_literal_run_overflow")
            result[out_index : out_index + count] = np.frombuffer(raw[in_index:end], dtype=np.uint8).astype(dtype, copy=False)
            out_index += count
            in_index = end
        else:
            count = control
            if in_index >= len(raw):
                raise ValueError("hxbyterle_repeat_run_missing_value")
            result[out_index : out_index + count] = raw[in_index]
            out_index += count
            in_index += 1
    if out_index != expected_size:
        raise ValueError(f"hxbyterle_decoded_size_mismatch:{out_index}:{expected_size}")
    return result


def import_amira_directory(
    project_manager,
    source_dir,
    specimen_id,
    modality="confocal",
    metadata_ref="",
    copy_source=False,
):
    if not isinstance(project_manager, TifProjectManager):
        raise TypeError("project_manager_must_be_tif_project_manager")
    files = resolve_amira_files(source_dir)
    for key in ("labels", "resampled"):
        if not files.get(key):
            raise FileNotFoundError(f"amira_required_file_missing:{key}")

    labels_header = read_amira_header(files["labels"])
    resampled_header = read_amira_header(files["resampled"])
    raw_tif_shape = _read_raw_tif_shape(files.get("raw_tif", ""))

    warnings = []
    if raw_tif_shape and raw_tif_shape != labels_header["shape_zyx"]:
        warnings.append("raw_tif_shape_differs_from_labels_shape")
    if resampled_header["shape_zyx"] != labels_header["shape_zyx"]:
        raise ValueError(f"resampled_label_shape_mismatch:{resampled_header['shape_zyx']}:{labels_header['shape_zyx']}")

    material_stats = parse_material_statistics(files.get("material_statistics", ""), header_materials=labels_header.get("materials", []))
    material_map = {
        "source": AMIRA_IMPORT_ADAPTER_VERSION,
        "materials": material_stats or _fallback_materials(labels_header.get("materials", [])),
    }

    project_manager.create_specimen_scaffold(
        specimen_id,
        material_map=material_map,
        modality=modality,
        metadata_ref=metadata_ref,
    )
    specimen_root_rel = project_manager.specimen_dir(specimen_id)

    source_records = _register_or_copy_sources(project_manager, specimen_root_rel, files, copy_source=copy_source)
    image_volume, image_header = read_amira_volume(files["resampled"])
    label_volume, label_header = read_amira_volume(files["labels"])

    image_rel = os.path.join(specimen_root_rel, "working", "image.ome.zarr").replace("\\", "/")
    manual_rel = os.path.join(specimen_root_rel, "labels", "manual_truth.ome.zarr").replace("\\", "/")
    edit_rel = os.path.join(specimen_root_rel, "labels", "working_edit.ome.zarr").replace("\\", "/")
    material_map_rel = os.path.join(specimen_root_rel, "material_map.json").replace("\\", "/")

    image_meta = write_volume_sidecar(
        project_manager.to_absolute(image_rel),
        image_volume,
        role="working_image",
        spacing_zyx=image_header["spacing_zyx"],
        spacing_unit=image_header["spacing_unit"],
        orientation=image_header["orientation"],
        source_format="amira_resampled",
        extra_metadata={
            "import_adapter": AMIRA_IMPORT_ADAPTER_VERSION,
            "note": "Lightweight recoverable sidecar; not complete OME-NGFF metadata.",
        },
    )
    label_meta = write_volume_sidecar(
        project_manager.to_absolute(manual_rel),
        label_volume,
        role="manual_truth",
        spacing_zyx=image_header["spacing_zyx"],
        spacing_unit=image_header["spacing_unit"],
        orientation=image_header["orientation"],
        source_format="amira_labels",
        extra_metadata={
            "import_adapter": AMIRA_IMPORT_ADAPTER_VERSION,
            "encoding": label_header["encoding"],
        },
    )
    edit_meta = copy_volume_sidecar(project_manager.to_absolute(manual_rel), project_manager.to_absolute(edit_rel), role="working_edit")
    material_map_payload = write_material_map(project_manager.to_absolute(material_map_rel), material_map, source=AMIRA_IMPORT_ADAPTER_VERSION)

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
    project_manager.register_label_volume(
        specimen_id,
        "manual_truth",
        manual_rel,
        label_meta["shape_zyx"],
        label_meta["dtype"],
        status="reviewed",
        spacing_zyx=label_meta["spacing_zyx"],
        spacing_unit=label_meta["spacing_unit"],
        orientation=label_meta["orientation"],
        fmt=label_meta["format"],
        save=False,
    )
    project_manager.register_label_volume(
        specimen_id,
        "working_edit",
        edit_rel,
        edit_meta["shape_zyx"],
        edit_meta["dtype"],
        status="copied_from_manual_truth",
        spacing_zyx=edit_meta["spacing_zyx"],
        spacing_unit=edit_meta["spacing_unit"],
        orientation=edit_meta["orientation"],
        fmt=edit_meta["format"],
        save=False,
    )

    specimen = project_manager.get_specimen(specimen_id)
    specimen["source"].update(source_records)
    specimen["material_map"] = material_map_rel
    specimen["review_status"] = "train_ready"
    specimen["train_ready"] = True
    specimen["provenance"] = {
        "import_method": AMIRA_IMPORT_ADAPTER_VERSION,
        "source_dataset": os.path.abspath(str(source_dir)),
        "notes": "AMIRA labels aligned to resampled volume.",
    }

    report = {
        "schema_version": AMIRA_IMPORT_REPORT_SCHEMA_VERSION,
        "imported_at": _now_iso(),
        "adapter_version": AMIRA_IMPORT_ADAPTER_VERSION,
        "source_dir": os.path.abspath(str(source_dir)),
        "files": {key: _basename_or_empty(value) for key, value in files.items() if key != "hx_connections"},
        "shapes": {
            "raw_tif_zyx": raw_tif_shape,
            "resampled_zyx": image_meta["shape_zyx"],
            "labels_zyx": label_meta["shape_zyx"],
        },
        "alignment": {
            "working_image": "resampled",
            "labels_aligned_to": "resampled",
            "raw_tif_used_as": "source_provenance",
            "hx_image_connection": files.get("hx_connections", {}).get("image_connections", []),
        },
        "materials": {
            "count": len(material_map_payload.get("materials", [])),
            "source": "MaterialStatistics" if material_stats else "labels_header",
        },
        "warnings": warnings,
        "errors": [],
    }
    report_rel = os.path.join(specimen_root_rel, "working", "import_report.json").replace("\\", "/")
    with open(project_manager.to_absolute(report_rel), "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    specimen["working_volume"]["import_report"] = report_rel
    project_manager.save_project()

    return {
        "specimen": specimen,
        "report": report,
        "report_path": project_manager.to_absolute(report_rel),
    }


def _fallback_materials(header_materials):
    materials = []
    for index, material in enumerate(header_materials or []):
        material_id = material.get("id")
        if material_id is None:
            material_id = index
        materials.append(
            {
                "id": material_id,
                "name": material.get("name") or str(material_id),
                "display_name": material.get("display_name") or material.get("name") or str(material_id),
                "color": material.get("color") or "",
                "trainable": material_id != 0,
                "source_name": material.get("source_name") or material.get("name") or str(material_id),
            }
        )
    return materials


def _register_or_copy_sources(project_manager, specimen_root_rel, files, copy_source=False):
    mapping = {
        "raw_tif": ("source/raw", "raw_tif"),
        "hx": ("source/amira_original", "amira_hx"),
        "labels": ("source/amira_original", "amira_labels"),
        "resampled": ("source/amira_original", "amira_resampled"),
        "material_statistics": ("source/amira_original", "amira_material_statistics"),
        "surf": ("source/amira_original", "amira_surf"),
    }
    records = {}
    for source_key, (target_dir, record_key) in mapping.items():
        source_path = files.get(source_key, "")
        if not source_path:
            continue
        if copy_source:
            rel = os.path.join(specimen_root_rel, target_dir, _safe_filename(os.path.basename(source_path))).replace("\\", "/")
            abs_target = project_manager.to_absolute(rel)
            os.makedirs(os.path.dirname(abs_target), exist_ok=True)
            if os.path.abspath(source_path) != os.path.abspath(abs_target):
                shutil.copy2(source_path, abs_target)
            records[record_key] = rel
        else:
            records[record_key] = os.path.abspath(source_path)
    return records


def _read_raw_tif_shape(path):
    if not path or not os.path.exists(path):
        return []
    try:
        with tifffile.TiffFile(path) as tif:
            if not tif.series:
                return []
            shape = list(tif.series[0].shape)
    except Exception:
        return []
    if len(shape) == 2:
        return [1, int(shape[0]), int(shape[1])]
    if len(shape) == 3:
        return [int(shape[0]), int(shape[1]), int(shape[2])]
    squeezed = [int(value) for value in shape if int(value) > 1]
    if len(squeezed) == 3:
        return squeezed
    return []


def _basename_or_empty(path):
    return os.path.basename(path) if isinstance(path, str) and path else path
