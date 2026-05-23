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
            "LLM_CONTEXT_DETAILED.md -> 0.1 Start Center is now the Agent Center",
            "LLM_CONTEXT_DETAILED.md -> 0.4 Settings split",
            "LLM_CONTEXT_DETAILED.md -> 0.5 Locator and SAM lazy/preload behavior",
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
        "diagnostic_route": "2d_stl_model_settings",
        "diagnostic_focus": "2D/STL model defaults, Locator scope, Blink expert defaults, and external script backend wiring.",
        "llm_context_refs": (
            "LLM_CONTEXT_DETAILED.md -> 0.4 Settings split",
            "LLM_CONTEXT_DETAILED.md -> 0.5 External script backend",
            "LLM_CONTEXT_DETAILED.md -> 9.2 Module B - Labeling Workbench & Runtime",
        ),
        "source_code_refs": (
            "AntSleap/main.py -> ModelSettingsDialog.get_agent_context",
            "AntSleap/core/external_backend.py",
            "docs/contracts/external_backend_contract_v1.md",
        ),
        "artifact_hints": (
            "2D/STL project JSON, external backend contract JSON, result JSON, training report, and model manifest are the main troubleshooting artifacts.",
        ),
        "safety_notes": COMMON_SAFETY_NOTES
        + (
            "Do not paste full private command text or API credentials into chat; use command presence and contract checks first.",
        ),
        "suggested_agent_action": "Prioritize validation_errors, command contract placeholders, runtime_device, Locator scope count, and manifest availability.",
    },
    "tif_model_settings": {
        "diagnostic_route": "tif_volume_backend_settings",
        "diagnostic_focus": "TIF backend defaults for export, training, prediction, model_draft import, and train-ready safety.",
        "llm_context_refs": (
            "LLM_CONTEXT_DETAILED.md -> 0.4 Settings split",
            "LLM_CONTEXT_DETAILED.md -> 0.3 Workflow split",
            "LLM_CONTEXT_DETAILED.md -> 0.5 Independent TIF backend contract",
        ),
        "source_code_refs": (
            "AntSleap/main.py -> TifModelSettingsDialog.get_agent_context",
            "AntSleap/core/tif_backend.py",
            "docs/ant3d_workbench/TIF后端契约_v1_实施设计_zh.md",
        ),
        "artifact_hints": (
            "TIF project JSON, exported training exchange folder, backend contract JSON, backend result JSON, model_manifest, and model_draft sidecar are the key artifacts.",
        ),
        "safety_notes": COMMON_SAFETY_NOTES
        + (
            "Prediction outputs must land in model_draft and must not overwrite manual_truth automatically.",
        ),
        "suggested_agent_action": "Check backend ID, export formats, Python executable, contract placeholders, result schema, and model_draft import path.",
    },
    "labeling": {
        "diagnostic_route": "labeling_workbench_context",
        "diagnostic_focus": "Current 2D/STL annotation image, selected morphology part, recent workbench log, and integrated Blink parent-child refinement.",
        "llm_context_refs": (
            "LLM_CONTEXT_DETAILED.md -> 0.1 Integrated parent-child refinement panel",
            "LLM_CONTEXT_DETAILED.md -> 0.4 Main workbench Blink actions",
            "LLM_CONTEXT_DETAILED.md -> 9.2 Module B - Labeling Workbench & Runtime",
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
            "LLM_CONTEXT_DETAILED.md -> 9.2.5 Standalone Blink local session semantics",
            "LLM_CONTEXT_DETAILED.md -> 9.2.6 Current data semantics: trajectory vs formal annotation",
            "LLM_CONTEXT_DETAILED.md -> 9.9 Current BLINK/Cascade Runtime Notes",
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
    "tif_volume": {
        "diagnostic_route": "tif_volume_workbench_context",
        "diagnostic_focus": "Current TIF specimen, label role, material ID, sidecar volumes, and train-ready/manual_truth safety.",
        "llm_context_refs": (
            "LLM_CONTEXT_DETAILED.md -> 0.1 TIF label layers and train-ready safety",
            "LLM_CONTEXT_DETAILED.md -> 0.4 TIF Volume Workbench UI",
            "LLM_CONTEXT_DETAILED.md -> 0.5 Independent TIF backend contract",
        ),
        "source_code_refs": (
            "AntSleap/ui/tif_workbench.py -> TifWorkbenchWidget.get_agent_context",
            "AntSleap/core/tif_project.py",
            "AntSleap/core/tif_backend.py",
        ),
        "artifact_hints": (
            "TIF project JSON, current specimen sidecars, working_edit, manual_truth, model_draft, material map, and recent workbench log are the first inspection targets.",
        ),
        "safety_notes": COMMON_SAFETY_NOTES
        + (
            "Do not write predictions or working_edit into manual_truth unless the researcher explicitly confirms that review is complete.",
        ),
        "suggested_agent_action": "Check label role and material ID before interpreting a missing overlay, training readiness issue, or prediction import problem.",
    },
    "pdf_evidence": {
        "diagnostic_route": "pdf_evidence_context",
        "diagnostic_focus": "PDF screening, figure/caption evidence, candidate provenance, and multimodal review status.",
        "llm_context_refs": (
            "LLM_CONTEXT_DETAILED.md -> 9.1 Module A - PDF Screening & Extraction",
            "LLM_CONTEXT_DETAILED.md -> 4 Candidate Flow",
            ".lab-agent/skills/taxamask-pdf-evidence/SKILL.md",
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
            "PDF evidence and extracted figures are candidates/provenance only; never promote them into training truth automatically.",
        ),
        "suggested_agent_action": "Load the PDF evidence skill before planning screening, extraction, candidate import, or provenance debugging.",
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
    if scope == "tif_volume_backend":
        return "tif_model_settings"
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
    if any(str(enriched.get(f"{prefix}_command_present") or "") for prefix in ("prepare", "train", "predict")):
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
