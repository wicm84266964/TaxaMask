import os


LEGACY_EXPERT_FILENAME = "best_expert.pth"
PROJECT_ROUTE_MANIFEST_VERSION = "project-v2"


def _clean_part_name(value):
    text = str(value or "").strip()
    if not text:
        return None
    if "/" in text or "\\" in text:
        return None
    return text


def _clean_free_text(value):
    text = str(value or "").strip()
    return text or None


def _clean_expert_filename(value):
    text = str(value or "").strip().replace("\\", "/")
    if not text:
        return None
    filename = os.path.basename(text)
    if not filename or filename in {".", ".."}:
        return None
    if not filename.lower().endswith(".pth"):
        return None
    return filename


def build_expert_id(expert_part, expert_filename):
    clean_part = _clean_part_name(expert_part)
    clean_filename = _clean_expert_filename(expert_filename)
    if not clean_part or not clean_filename:
        return None
    return f"{clean_part}/{clean_filename}"


def parse_expert_id(expert_id):
    text = str(expert_id or "").strip().replace("\\", "/")
    if not text:
        return None, None
    parts = [segment for segment in text.split("/") if segment]
    if len(parts) < 2:
        return None, None
    clean_part = _clean_part_name(parts[-2])
    clean_filename = _clean_expert_filename(parts[-1])
    return clean_part, clean_filename


def sanitize_expert_reference(
    expert_part=None,
    expert_filename=None,
    expert_id=None,
    legacy_expert_name=None,
    default_filename=None,
):
    clean_part = None
    clean_filename = None

    if expert_id:
        clean_part, clean_filename = parse_expert_id(expert_id)

    if not clean_part:
        clean_part = _clean_part_name(expert_part)
    if not clean_filename:
        clean_filename = _clean_expert_filename(expert_filename)

    legacy_name = _clean_part_name(legacy_expert_name)
    if not clean_part and legacy_name:
        clean_part = legacy_name

    chosen_default_filename = _clean_expert_filename(default_filename)
    if clean_part and not clean_filename:
        clean_filename = chosen_default_filename

    expert_identifier = build_expert_id(clean_part, clean_filename)
    if not expert_identifier:
        return {
            "expert_part": None,
            "expert_filename": None,
            "expert_id": None,
        }

    return {
        "expert_part": clean_part,
        "expert_filename": clean_filename,
        "expert_id": expert_identifier,
    }


def sanitize_expert_candidate(candidate_entry, default_filename=None):
    if isinstance(candidate_entry, str):
        payload = {"expert_id": candidate_entry}
    elif isinstance(candidate_entry, dict):
        payload = candidate_entry
    else:
        return None

    clean_candidate = sanitize_expert_reference(
        expert_part=payload.get("expert_part"),
        expert_filename=payload.get("expert_filename"),
        expert_id=payload.get("expert_id"),
        legacy_expert_name=payload.get("expert_name"),
        default_filename=default_filename,
    )
    if not clean_candidate.get("expert_id"):
        return None
    return clean_candidate


def merge_expert_candidates(*candidate_groups, appointed_expert=None, default_filename=None):
    merged_candidates = []
    seen_ids = set()

    def add_candidate(candidate_entry):
        clean_candidate = sanitize_expert_candidate(candidate_entry, default_filename=default_filename)
        if not clean_candidate:
            return

        expert_id = clean_candidate.get("expert_id")
        if not expert_id or expert_id in seen_ids:
            return

        merged_candidates.append(clean_candidate)
        seen_ids.add(expert_id)

    add_candidate(appointed_expert)
    for group in candidate_groups:
        if isinstance(group, (list, tuple)):
            for candidate_entry in group:
                add_candidate(candidate_entry)
        else:
            add_candidate(group)

    return merged_candidates


def get_route_appointed_expert(route_entry, default_filename=None):
    if not isinstance(route_entry, dict):
        return sanitize_expert_reference(default_filename=default_filename)

    appointed_entry = route_entry.get("appointed_expert")
    if isinstance(appointed_entry, dict):
        clean_nested_reference = sanitize_expert_reference(
            expert_part=appointed_entry.get("expert_part"),
            expert_filename=appointed_entry.get("expert_filename"),
            expert_id=appointed_entry.get("expert_id"),
            legacy_expert_name=appointed_entry.get("expert_name"),
            default_filename=default_filename,
        )
        if clean_nested_reference.get("expert_id"):
            return clean_nested_reference

    return sanitize_expert_reference(
        expert_part=route_entry.get("expert_part"),
        expert_filename=route_entry.get("expert_filename"),
        expert_id=route_entry.get("expert_id"),
        legacy_expert_name=route_entry.get("expert_name"),
        default_filename=default_filename,
    )


def get_route_persisted_expert_candidates(route_entry, default_filename=None):
    if not isinstance(route_entry, dict):
        return []

    appointed_expert = get_route_appointed_expert(route_entry, default_filename=default_filename)
    return merge_expert_candidates(
        route_entry.get("expert_candidates", []),
        appointed_expert,
        default_filename=default_filename,
    )


def sanitize_project_route_entry(route_entry, taxonomy=None):
    if not isinstance(route_entry, dict):
        return None

    taxonomy_set = set(taxonomy or [])
    parent = _clean_part_name(route_entry.get("parent"))
    child = _clean_part_name(route_entry.get("child"))
    if not parent or not child or parent == child:
        return None
    if taxonomy_set and (parent not in taxonomy_set or child not in taxonomy_set):
        return None

    min_conf = route_entry.get("min_conf")
    if isinstance(min_conf, (int, float)):
        min_conf = float(min_conf)
    else:
        min_conf = None

    clean_appointed_expert = get_route_appointed_expert(route_entry)
    expert_candidates = get_route_persisted_expert_candidates(route_entry)

    clean_entry = {
        "parent": parent,
        "child": child,
        "enabled": bool(route_entry.get("enabled", False)),
        "min_conf": min_conf,
        "registration_source": _clean_free_text(route_entry.get("registration_source")) or "project",
        "focus_source": _clean_free_text(route_entry.get("focus_source")),
        "appointed_expert": dict(clean_appointed_expert),
        "expert_candidates": [dict(candidate) for candidate in expert_candidates],
    }
    clean_entry.update(clean_appointed_expert)
    return clean_entry


def sanitize_project_route_manifest(raw_manifest, taxonomy=None):
    routes = []
    if isinstance(raw_manifest, dict):
        routes = raw_manifest.get("routes", [])
    elif isinstance(raw_manifest, list):
        routes = raw_manifest

    if not isinstance(routes, list):
        routes = []

    deduped_routes = {}
    for item in routes:
        clean_entry = sanitize_project_route_entry(item, taxonomy=taxonomy)
        if not clean_entry:
            continue
        deduped_routes[(clean_entry["parent"], clean_entry["child"])] = clean_entry

    ordered_routes = sorted(
        deduped_routes.values(),
        key=lambda entry: (entry.get("parent", ""), entry.get("child", "")),
    )
    return {
        "version": PROJECT_ROUTE_MANIFEST_VERSION,
        "routes": ordered_routes,
    }


def sanitize_legacy_route_manifest(raw_manifest):
    clean_manifest = {
        "version": "",
        "approved": False,
        "routes": [],
    }
    if not isinstance(raw_manifest, dict):
        return clean_manifest

    clean_manifest["version"] = str(raw_manifest.get("version", "") or "").strip()
    clean_manifest["approved"] = bool(raw_manifest.get("approved", False))
    routes = raw_manifest.get("routes", [])
    if not isinstance(routes, list):
        return clean_manifest

    clean_routes = []
    for item in routes:
        if not isinstance(item, dict):
            continue
        parent = _clean_part_name(item.get("parent"))
        child = _clean_part_name(item.get("child"))
        if not parent or not child:
            continue

        min_conf = item.get("min_conf")
        if isinstance(min_conf, (int, float)):
            min_conf = float(min_conf)
        else:
            min_conf = None

        clean_route = {
            "parent": parent,
            "child": child,
            "enabled": bool(clean_manifest["approved"]),
            "min_conf": min_conf,
            "registration_source": "legacy_global_manifest",
            "focus_source": None,
        }
        clean_route.update(
            sanitize_expert_reference(
                expert_part=item.get("expert_part"),
                expert_filename=item.get("expert_filename"),
                expert_id=item.get("expert_id"),
                legacy_expert_name=item.get("expert_name") or child,
                default_filename=LEGACY_EXPERT_FILENAME,
            )
        )
        clean_routes.append(clean_route)

    clean_manifest["routes"] = clean_routes
    return clean_manifest


def route_manifest_has_routes(route_manifest):
    if not isinstance(route_manifest, dict):
        return False
    routes = route_manifest.get("routes", [])
    return isinstance(routes, list) and len(routes) > 0


def format_expert_label(route_entry):
    if not isinstance(route_entry, dict):
        return "Unappointed"
    appointed_expert = get_route_appointed_expert(route_entry)
    expert_id = appointed_expert.get("expert_id")
    if expert_id:
        return str(expert_id)
    expert_part = appointed_expert.get("expert_part")
    expert_filename = appointed_expert.get("expert_filename")
    fallback_id = build_expert_id(expert_part, expert_filename)
    return fallback_id or "Unappointed"
