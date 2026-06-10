PROJECT_TEMPLATE_GENERIC = "generic_taxonomy"
PROJECT_TEMPLATE_ANT = "ant_default"


PROJECT_TEMPLATES = {
    PROJECT_TEMPLATE_GENERIC: {
        "template_id": PROJECT_TEMPLATE_GENERIC,
        "display_name": "Generic taxonomy mask project",
        "taxonomy": ["Object", "Region", "Structure"],
        "locator_scope": ["Object"],
        "taxon_label": "Taxon",
        "category_supercategory": "biological_structure",
    },
    PROJECT_TEMPLATE_ANT: {
        "template_id": PROJECT_TEMPLATE_ANT,
        "display_name": "Ant morphology (validated example)",
        "taxonomy": ["Head", "Mesosoma", "Gaster"],
        "locator_scope": ["Head", "Mesosoma", "Gaster"],
        "taxon_label": "Genus",
        "category_supercategory": "ant_part",
    },
}


DEFAULT_PROJECT_TEMPLATE_ID = PROJECT_TEMPLATE_GENERIC


def get_project_template(template_id=None):
    clean_id = str(template_id or DEFAULT_PROJECT_TEMPLATE_ID).strip()
    template = PROJECT_TEMPLATES.get(clean_id) or PROJECT_TEMPLATES[DEFAULT_PROJECT_TEMPLATE_ID]
    return {
        "template_id": template["template_id"],
        "display_name": template["display_name"],
        "taxonomy": list(template["taxonomy"]),
        "locator_scope": list(template["locator_scope"]),
        "taxon_label": template["taxon_label"],
        "category_supercategory": template["category_supercategory"],
    }


def iter_project_templates():
    return [get_project_template(template_id) for template_id in PROJECT_TEMPLATES]
