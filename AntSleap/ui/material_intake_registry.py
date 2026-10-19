"""Reserved registration point for Material Processing Center intake pages.

A new intake method should call register_material_intake_page() from its own
module and set material_page_id on its tab. Do not copy pdf_evidence unless
that page is explicitly allowed to import into the labeling workbench.
"""

from __future__ import annotations

PDF_EVIDENCE_WORKBENCH = "pdf_evidence"
UNCONNECTED_WORKBENCH = "material_intake"

_PAGES = {}


def register_material_intake_page(page):
    page_id = str(page.get("page_id") or "").strip()
    if not page_id:
        raise ValueError("material_intake_page_id_required")
    _PAGES[page_id] = dict(page)
    return _PAGES[page_id]


def registered_material_page_ids():
    return tuple(_PAGES)


def workbench_import_allowed(page_id):
    page = _PAGES.get(str(page_id or ""))
    return bool(page and page.get("connected_to_workbench"))


def resolve_material_intake_page(page_id, facts=None):
    facts = facts or {}
    page = _PAGES.get(str(page_id or ""))
    if page is None:
        return {
            "page_id": str(page_id or "unregistered_intake_page"),
            "source_workbench": UNCONNECTED_WORKBENCH,
            "project_type": UNCONNECTED_WORKBENCH,
            "diagnostic_route": "material_intake_context",
            "connected_to_workbench": False,
            "include_pdf_fields": False,
            "pathway_label_key": "Unregistered material intake",
            "settings_focus": "new_material_intake_page",
            "acquisition_stage": "unregistered_material_page",
            "page_instruction": (
                "The user opened a material intake page that is not registered. "
                "Use the visible page name and the fields on that page. "
                "Do not assume it is PDF screening or figure extraction, and do not import it into the labeling workbench."
            ),
        }
    stage = page["resolve_stage"](facts)
    resolved = {
        "page_id": page["page_id"],
        "source_workbench": page["source_workbench"],
        "project_type": page["project_type"],
        "diagnostic_route": page.get("diagnostic_route") or f"{page['source_workbench']}_context",
        "connected_to_workbench": bool(page.get("connected_to_workbench")),
        "include_pdf_fields": bool(page.get("include_pdf_fields")),
        "pathway_label_key": page.get("pathway_label_key") or page["page_id"],
    }
    resolved.update(stage)
    return resolved


def _literature_screening_stage(facts):
    if facts.get("has_source_folder"):
        return {
            "settings_focus": "stage_2_screening_criteria_and_run_diagnosis",
            "acquisition_stage": "stage_2_existing_pdf_folder_ready_for_screening",
            "page_instruction": (
                "The user is on the literature-screening page of the Material Processing Center. "
                "Use the PDF input folder, screening output folder, logic profile, and batch settings. "
                "Do not switch the task to figure extraction unless the user asks."
            ),
        }
    return {
        "settings_focus": "stage_0_confirm_existing_pdfs_or_discovery_mode",
        "acquisition_stage": "stage_0_existing_pdfs_daily_review_topic_search_selected_download_or_batch_harvest",
        "page_instruction": (
            "The user is on the literature-screening page of the Material Processing Center, and no PDF input folder is set. "
            "Confirm whether PDFs already exist or which lawful discovery mode is needed. "
            "Do not jump to figure extraction."
        ),
    }


def _data_extraction_stage(_facts):
    return {
        "settings_focus": "stage_3_figure_extraction_review_and_import_ready_export",
        "acquisition_stage": "stage_3_current_extraction_or_review",
        "page_instruction": (
            "The user is on the data-extraction page of the Material Processing Center. "
            "Use the extraction input folder, result folder, database, figure profile, multimodal switch, and Poppler status. "
            "Do not restart from whether PDFs exist, and do not treat the screening page settings as the current task."
        ),
    }


def _register_builtin_pages():
    register_material_intake_page({
        "page_id": "literature_screening",
        "source_workbench": PDF_EVIDENCE_WORKBENCH,
        "project_type": PDF_EVIDENCE_WORKBENCH,
        "diagnostic_route": "pdf_evidence_context",
        "connected_to_workbench": True,
        "include_pdf_fields": True,
        "pathway_label_key": "PDF literature evidence pathway",
        "resolve_stage": _literature_screening_stage,
    })
    register_material_intake_page({
        "page_id": "data_extraction",
        "source_workbench": PDF_EVIDENCE_WORKBENCH,
        "project_type": PDF_EVIDENCE_WORKBENCH,
        "diagnostic_route": "pdf_evidence_context",
        "connected_to_workbench": True,
        "include_pdf_fields": True,
        "pathway_label_key": "PDF literature evidence pathway",
        "resolve_stage": _data_extraction_stage,
    })


_register_builtin_pages()
