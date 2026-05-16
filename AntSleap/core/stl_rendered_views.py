import os
import re


STL_RENDERED_VIEW_REGISTRY_SCHEMA_VERSION = "ant3d_stl_rendered_view_registry_v1"


DEFAULT_STL_VIEW_NAMES = [
    "front",
    "back",
    "left",
    "right",
    "dorsal",
    "ventral",
    "lateral",
    "anterior",
    "posterior",
    "head",
]


def normalize_view_name(value, known_views=None):
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    aliases = {
        "top": "dorsal",
        "bottom": "ventral",
        "side": "lateral",
        "front_view": "front",
        "back_view": "back",
    }
    text = aliases.get(text, text)
    if known_views and text not in set(known_views):
        return ""
    return text


def parse_rendered_view_filename(path, known_views=None):
    known = [normalize_view_name(item) for item in (known_views or DEFAULT_STL_VIEW_NAMES)]
    known_set = set(known)
    stem = os.path.splitext(os.path.basename(str(path)))[0]
    tokens = [token for token in re.split(r"[_\-\s]+", stem) if token]
    if len(tokens) < 2:
        return None

    normalized_tokens = [normalize_view_name(token) for token in tokens]
    view_index = len(tokens) - 1
    view_name = normalized_tokens[view_index]
    if view_name not in known_set:
        return None
    if view_index <= 0:
        return None

    specimen_id = "_".join(tokens[:view_index]).strip("_")
    if not specimen_id:
        return None
    return {
        "specimen_id": specimen_id,
        "view_name": view_name,
        "path": os.path.abspath(str(path)),
        "filename": os.path.basename(str(path)),
    }


def build_stl_rendered_view_registry(paths, known_views=None):
    known = [normalize_view_name(item) for item in (known_views or DEFAULT_STL_VIEW_NAMES)]
    specimens = {}
    unparsed = []
    duplicate_views = []

    for path in paths:
        parsed = parse_rendered_view_filename(path, known)
        if parsed is None:
            unparsed.append(os.path.abspath(str(path)))
            continue
        specimen = specimens.setdefault(
            parsed["specimen_id"],
            {
                "specimen_id": parsed["specimen_id"],
                "views": {},
                "review_status": "not_started",
                "metadata_ref": "",
            },
        )
        view_name = parsed["view_name"]
        if view_name in specimen["views"]:
            duplicate_views.append(
                {
                    "specimen_id": parsed["specimen_id"],
                    "view_name": view_name,
                    "existing": specimen["views"][view_name]["path"],
                    "duplicate": parsed["path"],
                }
            )
            continue
        specimen["views"][view_name] = {
            "path": parsed["path"],
            "filename": parsed["filename"],
            "view_name": view_name,
        }

    return {
        "schema_version": STL_RENDERED_VIEW_REGISTRY_SCHEMA_VERSION,
        "known_views": known,
        "specimens": sorted(specimens.values(), key=lambda item: item["specimen_id"]),
        "unparsed": unparsed,
        "duplicate_views": duplicate_views,
    }
