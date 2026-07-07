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
            "LLM_CONTEXT_DETAILED.md -> 4. Launch And Runtime",
            "LLM_CONTEXT_DETAILED.md -> 5. Agent Center",
            "LLM_CONTEXT_DETAILED.md -> 6. 2D/STL Route",
            "TaxaMask使用手册.md -> 3. 首次启动：Agent Center、语言与界面总结构",
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
            "LLM_CONTEXT_DETAILED.md -> 6. 2D/STL Route",
            "LLM_CONTEXT_DETAILED.md -> 15. External Backend Contracts",
            "LLM_CONTEXT_DETAILED.md -> 16. Ask Agent Routing",
            "TaxaMask使用手册.md -> 11. 模型设置、训练、推理与 AI 标注清理",
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
    "tif_model_settings": {
        "diagnostic_route": "tif_volume_backend_settings",
        "diagnostic_focus": "TIF volume-segmentation backend defaults for label-schema based train-ready export, project-wide part/reslice training selection, nnU-Net v2 or custom backend commands, trained model library, prediction import as editable_ai_result, raw prediction backup, and manual_truth safety. Keep this separate from the Local Axis proposal backend.",
        "llm_context_refs": (
            "LLM_CONTEXT_DETAILED.md -> 8. TIF/CT Project Model",
            "LLM_CONTEXT_DETAILED.md -> 9. TIF Workbench",
            "LLM_CONTEXT_DETAILED.md -> 15. External Backend Contracts",
            "LLM_CONTEXT_DETAILED.md -> 16. Ask Agent Routing",
            "TaxaMask使用手册.md -> 10. TIF 体数据工作台：标注与训练、部位体与局部轴重切片",
            "TaxaMask使用手册.md -> 12.4 TIF 训练体导出",
        ),
        "source_code_refs": (
            "AntSleap/main.py -> TifModelSettingsDialog.get_agent_context",
            "AntSleap/ui/tif_workbench.py -> TifWorkbenchWidget.get_agent_context",
            "AntSleap/ui/tif_workbench.py -> TifWorkbenchWidget._selected_backend_samples_for_action",
            "AntSleap/core/tif_backend.py",
            "AntSleap/core/tif_export.py",
            "AntSleap/core/tif_prediction_import.py",
            "AntSleap/tools/tif_nnunet_v2_backend.py",
            "docs/contracts/ant3d_tif_backend_contract_v1.md",
            "docs/contracts/tif_local_axis_backend_contract_v1.md",
        ),
        "artifact_hints": (
            "TIF SQLite manifest or legacy JSON entry, train-ready part/reslice refs, exported training exchange folder, backend contract JSON, backend result JSON, nnunet_v2_commands.log, TaxaMask model_manifest, project model-library record, editable_ai_result sidecar, and raw_ai_prediction_backup sidecar are the key artifacts.",
        ),
        "safety_notes": COMMON_SAFETY_NOTES
        + (
            "Part prediction outputs must land in editable_ai_result with a raw_ai_prediction_backup and must not overwrite manual_truth automatically.",
            "A label schema only defines numeric label meaning; it is not a training sample unless reviewed manual_truth exists, shapes match, and the part/reslice or specimen is marked train-ready.",
            "The bundled real nnU-Net v2 train adapter requires at least two exported training samples; prepare_dataset can still run with one sample for layout inspection.",
        ),
        "suggested_agent_action": "Check backend ID, export formats, Python executable, editable command fields, contract placeholders, nnU-Net command availability, selected model manifest/model-library record, train-ready part/reslice sample count, top-level fallback count, result schema, editable_ai_result import path, and raw backup path. If the task is Local Axis orientation or reslice proposals, switch to the local-axis contract instead.",
    },
    "labeling": {
        "diagnostic_route": "labeling_workbench_context",
        "diagnostic_focus": "Current 2D/STL annotation image, selected morphology part, recent workbench log, and integrated Blink parent-child refinement.",
        "llm_context_refs": (
            "LLM_CONTEXT_DETAILED.md -> 6. 2D/STL Route",
            "LLM_CONTEXT_DETAILED.md -> 15. External Backend Contracts",
            "LLM_CONTEXT_DETAILED.md -> 16. Ask Agent Routing",
            "TaxaMask使用手册.md -> 7. 2D/STL 标注工作台：从图片列表到正式标注",
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
            "LLM_CONTEXT_DETAILED.md -> 6. 2D/STL Route",
            "LLM_CONTEXT_DETAILED.md -> 15. External Backend Contracts",
            "LLM_CONTEXT_DETAILED.md -> 16. Ask Agent Routing",
            "TaxaMask使用手册.md -> 9. 主工作台内子部位标注：轨迹积累与专家训练",
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
        "diagnostic_focus": "Current TIF specimen, label role, label schema, material ID, sidecar volumes, slice/3D volume view state, GPU preview, Local Axis Reslice, project-wide train-ready sample selection, trained model library, backend run state, and manual_truth safety.",
        "llm_context_refs": (
            "LLM_CONTEXT_DETAILED.md -> 8. TIF/CT Project Model",
            "LLM_CONTEXT_DETAILED.md -> 9. TIF Workbench",
            "LLM_CONTEXT_DETAILED.md -> 11. GPU Volume Preview",
            "LLM_CONTEXT_DETAILED.md -> 12. Local Axis Reslice",
            "LLM_CONTEXT_DETAILED.md -> 13. Local Axis Training Material Capture",
            "LLM_CONTEXT_DETAILED.md -> 15. External Backend Contracts",
            "TaxaMask使用手册.md -> 10. TIF 体数据工作台：标注与训练、部位体与局部轴重切片",
            "TaxaMask使用手册.md -> 12.4 TIF 训练体导出",
        ),
        "source_code_refs": (
            "AntSleap/ui/tif_workbench.py -> TifWorkbenchWidget.get_agent_context",
            "AntSleap/ui/tif_gpu_volume_canvas.py",
            "AntSleap/core/tif_project.py",
            "AntSleap/core/tif_backend.py",
            "AntSleap/core/tif_local_axis_reslice.py",
            "AntSleap/core/tif_local_axis_ai.py",
            "docs/contracts/ant3d_tif_backend_contract_v1.md",
            "docs/contracts/tif_local_axis_backend_contract_v1.md",
        ),
        "artifact_hints": (
            "TIF SQLite manifest or legacy JSON entry, current specimen sidecars, active label schema, working_edit, manual_truth, editable_ai_result, raw_ai_prediction_backup, train-ready part refs, selected model manifest, backend run/result JSON, material map, volume renderer state, source spacing, and recent workbench log are the first inspection targets.",
        ),
        "safety_notes": COMMON_SAFETY_NOTES
        + (
            "Do not write predictions or working_edit into manual_truth unless the researcher explicitly confirms that review is complete.",
            "Local Axis Reslice must preserve source provenance and use nearest-neighbor interpolation for label volumes.",
            "Preparing or training TIF data should use reviewed train-ready samples across the project, not just the currently selected part, unless the code path explicitly says otherwise.",
        ),
        "suggested_agent_action": "Check display_mode, slice axis/position, volume renderer, shape/spacing, label role, label schema, material ID, selected part/reslice item, train-ready sample counts, selected model manifest, backend run state, and Local Axis draft/output state before interpreting a missing overlay, GPU preview issue, training readiness issue, prediction import problem, or reslice request.",
    },
    "pdf_evidence": {
        "diagnostic_route": "pdf_evidence_context",
        "diagnostic_focus": "PDF evidence guided workflow. Handle one stage per reply: stage 0 decide whether PDFs already exist or lawful literature/PDF harvest is needed; then check key/model readiness, screening criteria, figure-review criteria, and run/results.",
        "llm_context_refs": (
            "LLM_CONTEXT_DETAILED.md -> 7. PDF Evidence Route",
            "LLM_CONTEXT_DETAILED.md -> 5. Agent Center",
            "TaxaMask使用手册.md -> 5. PDF 处理模块：从原始 PDF 到候选数据库",
            "vendor/ant-code/config/skills/taxonomy-pdf-harvest/SKILL.md",
            ".lab-agent/skills/taxamask-pdf-evidence/SKILL.md",
        ),
        "source_code_refs": (
            "AntSleap/ui/pdf_processing_widget.py",
            "core/pdf_processor/pdf_classifier.py",
            "core/pdf_processor/pdf_extractor.py",
        ),
        "artifact_hints": (
            "Harvest records.csv, doi_list.txt, summary.json, download_manifest.csv, harvested pdfs/, core_results, debug_evidence, extraction SQLite DB, candidate image paths, and evidence index reports are the relevant artifacts.",
        ),
        "safety_notes": COMMON_SAFETY_NOTES
        + (
            "For PDF acquisition, use only open metadata and legally exposed PDF links. Do not use Sci-Hub, LibGen, paywall bypasses, CAPTCHA bypasses, or logged-in scraping.",
            "PDF evidence and extracted figures are candidates/provenance only; never promote them into training truth automatically.",
        ),
        "suggested_agent_action": "First ask whether the user already has a PDF folder or needs stage 0 lawful literature/PDF harvest. If PDFs are missing, load taxonomy-pdf-harvest first; otherwise load the PDF evidence skill. Stay on the current stage, ask at most three concise requirement-confirmation questions, summarize them as at most three items, do not dump the full workflow, and move forward only after the current stage is resolved.",
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
