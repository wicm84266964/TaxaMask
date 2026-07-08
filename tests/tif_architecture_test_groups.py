"""Curated TIF architecture regression groups.

These groups keep the TIF workbench refactor checks readable for humans and
usable with ``python -m unittest`` in the TaxaMask conda environment.
"""

TIF_CORE_SAFETY_TESTS = (
    "tests.test_tif_label_guard",
    "tests.test_tif_write_guard",
    "tests.test_tif_truth_policy",
    "tests.test_tif_prediction_policy",
    "tests.test_tif_project",
    "tests.test_tif_backend",
    "tests.test_tif_stack_import",
    "tests.test_amira_import",
    "tests.test_tif_prediction_import",
)

TIF_SERVICE_TASK_TESTS = (
    "tests.test_tif_selection_controller",
    "tests.test_tif_label_edit_service",
    "tests.test_tif_truth_promotion_service",
    "tests.test_tif_roi_part_service",
    "tests.test_tif_backend_workflow_service",
    "tests.test_tif_volume_preview_service",
    "tests.test_tif_local_axis_service",
    "tests.test_tif_task_context",
    "tests.test_tif_task_state",
    "tests.test_tif_task_manager",
    "tests.test_tif_workbench_states",
)

TIF_PREVIEW_AND_EXPORT_TESTS = (
    "tests.test_tif_roi_preview",
    "tests.test_tif_volume_preview",
    "tests.test_tif_gpu_volume_canvas",
    "tests.test_tif_export",
    "tests.test_tif_local_axis_reslice",
    "tests.test_tif_local_axis_ai",
    "tests.test_tif_local_axis_batch",
)

TIF_GUI_KEY_PATH_TESTS = (
    "tests.test_tif_workbench",
    "tests.test_tif_backend_panel_controller",
    "tests.test_tif_local_axis_controller",
)

TIF_RESEARCH_SMOKE_TESTS = (
    "tests.test_tif_backend.TifBackendTests.test_tif_trainer_adapter_smoke_closes_review_retrain_loop",
    "tests.test_tif_workbench.TifWorkbenchTests.test_tif_batch_import_worker_registers_multiple_stacks_metadata_only",
    "tests.test_tif_workbench.TifWorkbenchTests.test_confirm_roi_worker_creates_part_and_writes_accepted_mask",
    "tests.test_tif_workbench.TifWorkbenchTests.test_auto_save_writes_working_edit_after_brush_change",
    "tests.test_tif_workbench.TifWorkbenchTests.test_accept_selected_ai_results_promotes_batch_to_manual_truth",
    "tests.test_tif_workbench.TifWorkbenchTests.test_train_finished_updates_training_result_panel_and_prediction_manifest",
    "tests.test_tif_workbench.TifWorkbenchTests.test_stale_background_volume_preview_context_is_cancelled",
    "tests.test_tif_workbench.TifWorkbenchTests.test_3d_mask_mode_falls_back_from_gpu_canvas_to_cpu_pixmap_canvas",
)

TIF_ARCHITECTURE_REGRESSION_GROUPS = {
    "core_safety": TIF_CORE_SAFETY_TESTS,
    "service_task": TIF_SERVICE_TASK_TESTS,
    "preview_export": TIF_PREVIEW_AND_EXPORT_TESTS,
    "gui_key_path": TIF_GUI_KEY_PATH_TESTS,
    "research_smoke": TIF_RESEARCH_SMOKE_TESTS,
}

TIF_RESEARCH_SAFETY_COVERAGE = {
    "prediction_import_never_overwrites_manual_truth": (
        "tests.test_tif_backend.TifBackendTests.test_part_predict_result_imports_editable_ai_result_without_touching_manual_truth",
        "tests.test_tif_backend.TifBackendTests.test_top_level_predict_result_imports_current_labels_without_touching_training_truth",
        "tests.test_tif_backend.TifBackendTests.test_backend_prediction_artifact_cannot_import_as_manual_truth",
    ),
    "raw_ai_prediction_backup_is_audit_only": (
        "tests.test_tif_label_guard.TifLabelGuardTests.test_label_role_write_matrix_protects_truth_and_raw_backup",
        "tests.test_tif_project.TifProjectTests.test_raw_backup_cannot_be_promoted_to_manual_truth",
        "tests.test_tif_label_edit_service.TifLabelEditServiceTests.test_raw_backup_save_is_blocked",
    ),
    "unreviewed_results_do_not_enter_training": (
        "tests.test_tif_backend.TifBackendTests.test_predict_contract_accepts_objectively_ready_part_without_manual_truth",
        "tests.test_tif_workbench.TifWorkbenchTests.test_part_training_action_reports_missing_training_truth_without_top_level_fallback",
        "tests.test_tif_truth_policy.TifTruthPolicyTests.test_training_uses_manual_truth_only",
    ),
    "save_failure_keeps_dirty_state": (
        "tests.test_tif_workbench.TifWorkbenchTests.test_unsaved_working_edit_prompt_can_cancel_close_and_save",
        "tests.test_tif_workbench.TifWorkbenchTests.test_background_auto_save_keeps_later_same_slice_edits_dirty",
    ),
    "stale_task_result_does_not_write_current_part": (
        "tests.test_tif_task_manager.TifTaskManagerTests.test_context_matching_blocks_stale_results",
        "tests.test_tif_workbench.TifWorkbenchTests.test_stale_background_volume_preview_context_is_cancelled",
        "tests.test_tif_workbench.TifWorkbenchTests.test_stale_background_volume_preview_result_is_ignored",
    ),
    "roi_output_shape_matches_bbox": (
        "tests.test_tif_roi_preview.TifRoiPreviewTests.test_roi_bbox_crop_and_shape_are_zyx",
        "tests.test_tif_roi_part_service.TifRoiPartServiceTests.test_confirm_part_roi_request_is_structured_and_sized",
    ),
    "training_selection_uses_train_ready_samples": (
        "tests.test_tif_backend_workflow_service.TifBackendWorkflowServiceTests.test_training_prefers_train_ready_parts",
        "tests.test_tif_backend.TifBackendTests.test_contract_uses_manual_truth_for_prepare_dataset",
        "tests.test_tif_export.TifExportTests.test_part_training_export_uses_resliced_part_and_manual_truth",
    ),
    "local_axis_export_respects_backend_write_lock": (
        "tests.test_tif_workbench.TifWorkbenchTests.test_backend_write_lock_blocks_project_mutations",
        "tests.test_tif_workbench.TifWorkbenchTests.test_task_manager_preview_lock_blocks_project_mutations",
    ),
}


def unittest_command_for(group_name):
    targets = TIF_ARCHITECTURE_REGRESSION_GROUPS[group_name]
    return "python -m unittest " + " ".join(targets)
