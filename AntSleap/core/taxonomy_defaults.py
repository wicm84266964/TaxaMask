import os

from .project_templates import PROJECT_TEMPLATE_ANT, get_project_template


_DEFAULT_TEMPLATE = get_project_template(PROJECT_TEMPLATE_ANT)
DEFAULT_PROJECT_TAXONOMY = list(_DEFAULT_TEMPLATE["taxonomy"])
DEFAULT_LOCATOR_SCOPE = list(_DEFAULT_TEMPLATE["locator_scope"])


def sanitize_part_name(part):
    if not isinstance(part, str):
        return ""
    return part.strip()


def is_safe_part_name(part):
    name = sanitize_part_name(part)
    if not name:
        return False
    if os.path.isabs(name):
        return False
    if any(sep in name for sep in ("/", "\\")):
        return False
    if name in {".", ".."}:
        return False
    if ".." in name:
        return False
    if ":" in name:
        return False
    return True


def _unique_nonempty_parts(parts):
    clean = []
    seen = set()
    for part in parts or []:
        if not isinstance(part, str):
            continue
        name = sanitize_part_name(part)
        if not is_safe_part_name(name):
            continue
        if not name or name in seen:
            continue
        seen.add(name)
        clean.append(name)
    return clean


def sanitize_taxonomy(parts, fallback=None):
    clean = _unique_nonempty_parts(parts)
    if clean:
        return clean
    fallback_clean = _unique_nonempty_parts(fallback or DEFAULT_PROJECT_TAXONOMY)
    return fallback_clean or list(DEFAULT_PROJECT_TAXONOMY)


def sanitize_locator_scope(scope, taxonomy, fallback=None):
    taxonomy_clean = sanitize_taxonomy(taxonomy, fallback=DEFAULT_PROJECT_TAXONOMY)
    allowed = set(taxonomy_clean)
    scope_clean = [part for part in _unique_nonempty_parts(scope) if part in allowed]
    if scope_clean:
        return scope_clean

    fallback_clean = [part for part in _unique_nonempty_parts(fallback or DEFAULT_LOCATOR_SCOPE) if part in allowed]
    if fallback_clean:
        return fallback_clean

    return list(taxonomy_clean)


def legacy_locator_scope_for_loaded_taxonomy(taxonomy):
    taxonomy_clean = sanitize_taxonomy(taxonomy, fallback=DEFAULT_PROJECT_TAXONOMY)
    return sanitize_locator_scope(taxonomy_clean, taxonomy_clean, fallback=taxonomy_clean)
