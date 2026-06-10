"""Compact routing hints for TaxaMask Ask Agent handoff prompts."""

from __future__ import annotations

from copy import deepcopy


COMMON_SAFETY_NOTES = (
    "Do not run destructive file operations, publish code, or start GPU-heavy jobs without explicit user intent.",
)


AGENT_CONTEXT_ROUTES = {
    "general_settings": {
        "diagnostic_route": "general_settings_runtime",
        "diagnostic_focus": "Application language, startup behavior, autosave interval, and default runtime device.",
        "llm_context_refs": (
            "LLM_CONTEXT_DETAILED.md -> Agent Center",
            "LLM_CONTEXT_DETAILED.md -> Public Workflow Routes",
            "TaxaMask使用手册.md -> Agent Center",
        ),
        "source_code_refs": (
            "AntSleap/main.py -> GeneralSettingsDialog.get_agent_context",
            "AntSleap/main.py -> MainWindow._compact_agent_context",
            "AntSleap/ui/taxamask_agent_panel.py -> TaxaMaskAgentPanel._context_prompt",
        ),
        "artifact_hints": (
            "user_config.json stores local runtime preferences and is intentionally ignored by Git.",
        ),
        "safety_notes": COMMON_SAFETY_NOTES,
        "suggested_agent_action": "Check whether the user's startup/runtime expectation matches the current settings summary.",
    },
    "stl_model_settings": {
        "diagnostic_route": "2d_stl_advanced_extensions",
        "diagnostic_focus": "Advanced Extensions for 2D/STL model profiles: parent model source, default child expert, custom parent/child extension contracts, and route expert compatibility.",
        "llm_context_refs": (
            "LLM_CONTEXT_DETAILED.md -> External Backend Contracts",
            "LLM_CONTEXT_DETAILED.md -> Blink And Child-Part Experts",
            "TaxaMask使用手册.md -> 外部模型后端",
        ),
        "source_code_refs": (
            "AntSleap/main.py -> ModelSettingsDialog.get_agent_context",
            "AntSleap/main.py -> ModelSettingsDialog._current_profile_snapshot",
            "docs/contracts/external_backend_contract_v1.md",
            "docs/contracts/external_blink_backend_contract_v1.md",
            "AntSleap/core/model_profiles.py",
            "AntSleap/core/external_backend.py",
            "AntSleap/core/external_blink_backend.py",
            "AntSleap/core/cascade_routes.py",
            "AntSleap/core/blink_expert_backends.py",
        ),
        "artifact_hints": (
            "2D/STL project JSON, active model profile, external parent/child contract JSON, result JSON, training report, route manifest, and model manifest are the main troubleshooting artifacts.",
        ),
        "safety_notes": COMMON_SAFETY_NOTES
        + (
            "Do not paste full private command text or API credentials into chat; use command presence, contract checks, profile fields, and route backend summaries first.",
        ),
        "suggested_agent_action": "Treat this as a TaxaMask Advanced Extensions configuration task. First inspect parent_model_source, default_child_expert, validation_errors, parent/child command contract flags, manifest availability, and route_specific_backend_summary; then modify only the relevant model profile, extension contract, or routing code.",
    },
    "labeling": {
        "diagnostic_route": "labeling_workbench_context",
        "diagnostic_focus": "Current 2D/STL annotation image, selected morphology part, recent workbench log, and integrated Blink parent-child refinement.",
        "llm_context_refs": (
            "LLM_CONTEXT_DETAILED.md -> 2D/STL Morphology",
            "LLM_CONTEXT_DETAILED.md -> VLM And SAM Drafts",
            "TaxaMask使用手册.md -> Labeling Workbench",
        ),
        "source_code_refs": (
            "AntSleap/main.py -> MainWindow._collect_image_workbench_agent_context",
            "AntSleap/main.py -> MainWindow._current_blink_context",
            "AntSleap/core/project.py",
        ),
        "artifact_hints": (
            "Current project JSON, active image path, annotations, shrink_loose_boxes, cascade_routes, and recent log excerpt are the first things to inspect.",
        ),
        "safety_notes": COMMON_SAFETY_NOTES
        + (
            "PDF candidates and model predictions are not accepted training truth until reviewed by the researcher.",
        ),
        "suggested_agent_action": "Explain the current image/part state first, then inspect project JSON or logs only if the symptom needs deeper evidence.",
    },
    "blink": {
        "diagnostic_route": "blink_refinement_context",
        "diagnostic_focus": "Standalone Blink fallback session, parent/context ROI, child target part, local dirty state, and expert training logs.",
        "llm_context_refs": (
            "LLM_CONTEXT_DETAILED.md -> Blink And Child-Part Experts",
            "TaxaMask使用手册.md -> Blink 子部位专家",
        ),
        "source_code_refs": (
            "AntSleap/ui/blink_lab.py -> BlinkLabWidget.get_agent_context",
            "AntSleap/ui/blink_lab.py -> BlinkLabWidget.train_expert_model",
            "AntSleap/core/blink_trainer.py",
        ),
        "artifact_hints": (
            "Project route records, trajectory data, Blink training report, active image path, and recent training log are the relevant artifacts.",
        ),
        "safety_notes": COMMON_SAFETY_NOTES
        + (
            "Do not treat auto-shrink trajectory output as a corrected formal polygon unless the researcher accepts it in the workbench.",
        ),
        "suggested_agent_action": "Separate trajectory training material from formal annotation state before recommending a fix.",
    },
    "pdf_evidence": {
        "diagnostic_route": "pdf_literature_context",
        "diagnostic_focus": "PDF literature-processing guided workflow. Handle one stage per reply: first check key/model readiness, then screening criteria, then figure-review criteria, then run/results.",
        "llm_context_refs": (
            "ANTCODE.md -> Public Workflow Routes",
            "LLM_CONTEXT_DETAILED.md -> PDF Literature Processing",
            "TaxaMask使用手册.md -> PDF 文献处理",
        ),
        "source_code_refs": (
            "AntSleap/ui/pdf_processing_widget.py",
            "core/pdf_processor/pdf_classifier.py",
            "core/pdf_processor/pdf_extractor.py",
        ),
        "artifact_hints": (
            "core_results, debug_evidence, extraction SQLite DB, candidate image paths, and evidence index reports are the relevant artifacts.",
        ),
        "safety_notes": COMMON_SAFETY_NOTES
        + (
            "PDF-derived literature trait descriptions and extracted figures are candidates/provenance only; never promote them into training truth automatically.",
        ),
        "suggested_agent_action": "Stay on the current PDF literature-processing stage. Use concise requirement-confirmation questions, ask at most three items, do not dump the full workflow, and only move to the next stage after the current one is resolved.",
    },
}


def _as_text(value):
    if isinstance(value, (list, tuple)):
        return "; ".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "").strip()


def _command_contract_missing(context):
    for prefix in ("prepare", "train", "predict"):
        if context.get(f"{prefix}_command_present") == "yes" and context.get(f"{prefix}_command_has_contract") == "no":
            return True
    for prefix in ("parent_prepare", "parent_train", "parent_predict", "child_train", "child_predict"):
        if context.get(f"{prefix}_command_present") == "yes" and context.get(f"{prefix}_command_has_contract") == "no":
            return True
    return False


def _validation_present(context):
    value = str(context.get("validation_errors") or "").strip().lower()
    return bool(value and value != "none")


def _route_key(context):
    source = str((context or {}).get("source_workbench") or "").strip()
    if source:
        return source
    scope = str((context or {}).get("settings_scope") or "").strip()
    if scope == "2d_stl_model":
        return "stl_model_settings"
    if scope == "general":
        return "general_settings"
    return ""


def enrich_agent_context(context):
    """Attach compact routing hints to an Ask Agent context dictionary."""

    enriched = dict(context or {})
    route = deepcopy(AGENT_CONTEXT_ROUTES.get(_route_key(enriched), {}))
    if not route:
        return enriched

    notes = list(route.get("safety_notes", ()))
    health = []
    validation = _validation_present(enriched)
    contract_missing = _command_contract_missing(enriched)
    health.append(f"validation_errors={'present' if validation else 'none'}")
    command_prefixes = (
        "prepare",
        "train",
        "predict",
        "parent_prepare",
        "parent_train",
        "parent_predict",
        "child_train",
        "child_predict",
    )
    if any(str(enriched.get(f"{prefix}_command_present") or "") for prefix in command_prefixes):
        health.append(f"contract_placeholder={'missing' if contract_missing else 'ok_or_not_applicable'}")

    if contract_missing:
        route["diagnostic_route"] = f"{route.get('diagnostic_route', 'agent_context')}:contract_placeholder_missing"
        route["diagnostic_focus"] = (
            f"{route.get('diagnostic_focus', '').rstrip()} Prioritize command templates that are present but missing "
            "{contract} or {contract_json}."
        ).strip()
    elif validation:
        route["diagnostic_route"] = f"{route.get('diagnostic_route', 'agent_context')}:validation_errors_present"
        route["diagnostic_focus"] = (
            f"{route.get('diagnostic_focus', '').rstrip()} Prioritize the current validation_errors summary."
        ).strip()

    if "agent_route_source" not in enriched:
        enriched["agent_route_source"] = "AntSleap/core/agent_context_routes.py"

    for key in (
        "diagnostic_route",
        "diagnostic_focus",
        "llm_context_refs",
        "source_code_refs",
        "artifact_hints",
        "safety_notes",
        "suggested_agent_action",
    ):
        if key not in enriched and key in route:
            enriched[key] = _as_text(route[key])
    if health and "health_check_summary" not in enriched:
        enriched["health_check_summary"] = "; ".join(health)
    if notes and "safety_notes" not in enriched:
        enriched["safety_notes"] = _as_text(notes)
    return enriched
