def _clean_part(value):
    text = str(value or "").strip()
    return text or None


def _unique_ordered(values):
    seen = set()
    result = []
    for value in values or []:
        clean = _clean_part(value)
        if clean and clean not in seen:
            result.append(clean)
            seen.add(clean)
    return result


def build_part_tree_groups(taxonomy, locator_scope=None, routes=None):
    """Build a UI-only parent/child grouping for project taxonomy parts."""
    clean_taxonomy = _unique_ordered(taxonomy)
    taxonomy_set = set(clean_taxonomy)
    clean_locator_scope = [part for part in _unique_ordered(locator_scope) if part in taxonomy_set]
    clean_routes = []
    child_parents = {}

    for route in routes or []:
        if not isinstance(route, dict):
            continue
        parent = _clean_part(route.get("parent"))
        child = _clean_part(route.get("child"))
        if not parent or not child or parent == child:
            continue
        if parent not in taxonomy_set or child not in taxonomy_set:
            continue
        clean_routes.append({"parent": parent, "child": child})
        child_parents.setdefault(child, [])
        if parent not in child_parents[child]:
            child_parents[child].append(parent)

    parent_order = []
    for parent in clean_locator_scope:
        if parent not in parent_order:
            parent_order.append(parent)
    for route in clean_routes:
        parent = route["parent"]
        if parent not in parent_order:
            parent_order.append(parent)

    grouped_children = set()
    cross_region = []
    for part in clean_taxonomy:
        parents = child_parents.get(part, [])
        if len(parents) > 1:
            cross_region.append(part)
            grouped_children.add(part)

    parent_groups = []
    for parent in parent_order:
        children = [
            part
            for part in clean_taxonomy
            if part != parent and child_parents.get(part) == [parent]
        ]
        grouped_children.update(children)
        parent_groups.append({"part": parent, "children": children})

    parent_set = set(parent_order)
    ungrouped = [
        part
        for part in clean_taxonomy
        if part not in parent_set and part not in grouped_children
    ]

    return {
        "parents": parent_groups,
        "cross_region": cross_region,
        "ungrouped": ungrouped,
    }
