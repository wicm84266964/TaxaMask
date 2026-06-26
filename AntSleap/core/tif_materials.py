import json
import os

from .safe_io import atomic_write_json


TIF_MATERIAL_MAP_SCHEMA_VERSION = "ant3d_tif_material_map_v1"
BACKGROUND_MATERIAL_ID = 0


_DEFAULT_COLOR_PALETTE = [
    "#f94144",
    "#f3722c",
    "#f9c74f",
    "#90be6d",
    "#43aa8b",
    "#577590",
    "#277da1",
    "#9b5de5",
    "#f15bb5",
    "#00bbf9",
    "#00f5d4",
    "#b8f2e6",
]


def _safe_material_name(value, fallback):
    text = str(value or "").strip()
    if not text:
        text = str(fallback)
    clean = "".join(ch if ch.isalnum() or ch in ("_", "-", ".") else "_" for ch in text)
    return clean.strip("_") or str(fallback)


def _normalize_color(value, material_id, name):
    text = str(value or "").strip()
    if len(text) == 7 and text.startswith("#"):
        try:
            int(text[1:], 16)
            return text.lower()
        except ValueError:
            pass
    if material_id == BACKGROUND_MATERIAL_ID:
        return "#000000"
    palette_index = (int(material_id) - 1) % len(_DEFAULT_COLOR_PALETTE)
    return _DEFAULT_COLOR_PALETTE[palette_index]


def default_background_material():
    return {
        "id": BACKGROUND_MATERIAL_ID,
        "name": "background",
        "display_name": "Background",
        "color": "#000000",
        "trainable": False,
        "source_name": "background",
    }


def normalize_material(material):
    if not isinstance(material, dict):
        raise ValueError("material_not_object")

    try:
        material_id = int(material.get("id"))
    except (TypeError, ValueError):
        raise ValueError("material_id_invalid")
    if material_id < 0:
        raise ValueError("material_id_negative")

    source_name = str(material.get("source_name") or material.get("display_name") or material.get("name") or material_id)
    name = _safe_material_name(material.get("name") or source_name, material_id)
    display_name = str(material.get("display_name") or source_name or name).strip() or name
    trainable = bool(material.get("trainable", material_id != BACKGROUND_MATERIAL_ID))
    if material_id == BACKGROUND_MATERIAL_ID:
        trainable = False

    return {
        "id": material_id,
        "name": name,
        "display_name": display_name,
        "color": _normalize_color(material.get("color"), material_id, name),
        "trainable": trainable,
        "source_name": source_name,
    }


def sanitize_material_map(payload=None, source="manual"):
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValueError("material_map_not_object")

    source_value = str(payload.get("source") or source or "manual")
    materials = payload.get("materials")
    if materials is None:
        materials = [default_background_material()]
    if not isinstance(materials, list):
        raise ValueError("materials_not_list")

    normalized = []
    seen_ids = set()
    has_background = False
    for material in materials:
        clean = normalize_material(material)
        if clean["id"] in seen_ids:
            raise ValueError(f"duplicate_material_id:{clean['id']}")
        seen_ids.add(clean["id"])
        has_background = has_background or clean["id"] == BACKGROUND_MATERIAL_ID
        normalized.append(clean)

    if not has_background:
        normalized.append(default_background_material())

    normalized.sort(key=lambda item: item["id"])
    return {
        "schema_version": TIF_MATERIAL_MAP_SCHEMA_VERSION,
        "source": source_value,
        "materials": normalized,
    }


def has_trainable_material(material_map):
    if not isinstance(material_map, dict):
        return False
    for material in material_map.get("materials", []):
        if isinstance(material, dict) and material.get("id") != BACKGROUND_MATERIAL_ID and bool(material.get("trainable")):
            return True
    return False


def next_material_id(material_map):
    payload = sanitize_material_map(material_map or {})
    used = {int(item["id"]) for item in payload.get("materials", [])}
    candidate = 1
    while candidate in used:
        candidate += 1
    return candidate


def upsert_material(material_map, material):
    payload = sanitize_material_map(material_map or {})
    clean = normalize_material(material)
    materials = [item for item in payload.get("materials", []) if int(item.get("id", -1)) != clean["id"]]
    materials.append(clean)
    payload["materials"] = materials
    return sanitize_material_map(payload, source=payload.get("source", "manual"))


def remove_material(material_map, material_id):
    clean_id = int(material_id)
    if clean_id == BACKGROUND_MATERIAL_ID:
        raise ValueError("cannot_remove_background_material")
    payload = sanitize_material_map(material_map or {})
    materials = [item for item in payload.get("materials", []) if int(item.get("id", -1)) != clean_id]
    if len(materials) == len(payload.get("materials", [])):
        raise KeyError(f"unknown_material_id:{clean_id}")
    payload["materials"] = materials
    return sanitize_material_map(payload, source=payload.get("source", "manual"))


def write_material_map(path, payload=None, source="manual"):
    clean = sanitize_material_map(payload, source=source)
    atomic_write_json(path, clean, indent=2, ensure_ascii=False)
    return clean


def read_material_map(path):
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return sanitize_material_map(payload, source=payload.get("source", "file") if isinstance(payload, dict) else "file")
