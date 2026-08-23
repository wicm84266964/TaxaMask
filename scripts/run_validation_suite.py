from __future__ import annotations

import argparse
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SUITES: dict[str, list[str]] = {
    "tif_core": [
        "tests.test_tif_architecture_test_groups",
        "tests.test_tif_label_guard",
        "tests.test_tif_write_guard",
        "tests.test_tif_truth_policy",
        "tests.test_tif_prediction_policy",
        "tests.test_tif_project",
        "tests.test_tif_backend",
        "tests.test_tif_stack_import",
        "tests.test_amira_import",
        "tests.test_tif_prediction_import",
    ],
    "tif_storage_safety": [
        "tests.test_safe_io",
        "tests.test_tif_json_to_sqlite_migration",
        "tests.test_tif_sqlite_loader",
        "tests.test_tif_sqlite_schema",
    ],
    "tif_services": [
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
    ],
    "tif_preview_export": [
        "tests.test_tif_roi_preview",
        "tests.test_tif_volume_preview",
        "tests.test_tif_gpu_volume_canvas",
        "tests.test_tif_transfer_function",
        "tests.test_tif_export",
        "tests.test_tif_local_axis_reslice",
        "tests.test_tif_local_axis_ai",
        "tests.test_tif_local_axis_batch",
        "tests.test_tif_resource_policy",
        "tests.test_tif_preview_controller",
    ],
    "tif_model_backends": [
        "tests.test_tif_brain_input_cleaning",
        "tests.test_tif_nnunet_v2_backend",
        "tests.test_tif_blink_core",
        "tests.test_tif_blink_nnunet_core",
    ],
    "tif_workbench": [
        "tests.test_tif_workbench",
        "tests.test_tif_backend_panel_controller",
        "tests.test_tif_result_review_controller",
        "tests.test_tif_local_axis_controller",
        "tests.test_tif_agent_context",
        "tests.test_tif_workbench_style",
        "tests.test_tif_workbench_shell",
        "tests.test_tif_workbench_signal_router",
        "tests.test_tif_workbench_coordinator",
        "tests.test_tif_selection_workflow_controller",
        "tests.test_tif_project_lifecycle_controller",
        "tests.test_tif_annotation_workflow_controller",
        "tests.test_tif_roi_workflow_controller",
        "tests.test_tif_part_mask_workflow_controller",
        "tests.test_tif_volume_render_controller",
        "tests.test_tif_round3_real_data_acceptance",
    ],
    "gui_smoke": ["tests.test_gui_smoke"],
    "ui_polish": ["tests.test_ui_polish_scope"],
    "tif_layout": ["tests.test_tif_workbench_layout"],
    "pdf_safety": ["tests.test_pdf_profile_deletion_safety"],
    "validation_tooling": [
        "tests.test_validation_suite_script",
        "tests.test_release_workflow",
    ],
    "tif_architecture_round3": ["tests.test_tif_workbench_architecture_analysis"],
    "taxamask_architecture_round4": [
        "tests.test_main_window_architecture_analysis",
        "tests.test_main_window_performance_benchmark",
        "tests.test_main_window_stage1_modules",
        "tests.test_main_window_stage2_dialogs",
        "tests.test_main_window_stage3_shell",
        "tests.test_main_window_stage4_project_lifecycle",
        "tests.test_main_window_stage5_navigation",
        "tests.test_main_window_stage6_annotation_blink",
        "tests.test_main_window_stage7_training_prediction",
        "tests.test_main_window_stage8_architecture",
    ],
    "validation_chunk_sample": ["tests.test_safe_io.SafeIoTests.test_atomic_write_json_failure_keeps_existing_file_and_removes_tmp"],
    "sqlite_2d": [
        "tests.test_2d_json_to_sqlite_migration",
        "tests.test_2d_sqlite_project_load",
        "tests.test_2d_sqlite_project_save",
        "tests.test_2d_sqlite_schema",
        "tests.test_sqlite_large_scale_rehearsal",
        "tests.test_sqlite_project_maintenance",
        "tests.test_sqlite_storage",
    ],
    "agentic_misc": [
        "tests.test_agent_context_routes",
        "tests.test_agentic_auto_annotate",
        "tests.test_agentic_candidate_import",
        "tests.test_agentic_contract",
        "tests.test_agentic_multimodal_export",
        "tests.test_api_runtime_settings_schema",
        "tests.test_config_cleanup",
        "tests.test_platform_open",
        "tests.test_poppler_discovery",
        "tests.test_reporting_routes",
        "tests.test_runtime_device",
        "tests.test_sam_worker",
        "tests.test_ui_localization",
        "tests.test_window_geometry",
    ],
    "blink_locator": [
        "tests.test_blink_bridge",
        "tests.test_blink_expert_manifest",
        "tests.test_blink_heatmap_dataset",
        "tests.test_blink_route_backends",
        "tests.test_blink_training_strategy",
        "tests.test_external_blink_backend",
        "tests.test_locator_resolution_metadata",
        "tests.test_locator_scope",
        "tests.test_model_profiles",
        "tests.test_part_tree",
        "tests.test_training_preflight",
    ],
    "pdf_literature": [
        "tests.test_panel_splitter",
        "tests.test_figure_profile",
        "tests.test_literature_description_bridge",
        "tests.test_part_description_profile",
        "tests.test_pdf_classifier_llm_review",
        "tests.test_pdf_figure_filename",
        "tests.test_pdf_part_description_extraction",
        "tests.test_specimen_linkage_pdf_evidence",
    ],
    "v2410_release_audit": [
        "tests.test_pdf_figure_filename.FigureFilenameTests.test_caption_whitespace_is_safe_for_windows_filename",
        "tests.test_pdf_figure_filename.FigureFilenameTests.test_pdf_identity_prevents_sanitized_and_truncated_name_collisions",
        "tests.test_pdf_figure_filename.FigureFilenameTests.test_pdf_scope_is_stable_for_content_updates_at_the_same_source_path",
        "tests.test_pdf_figure_filename.FigureFilenameTests.test_relative_pdf_scope_does_not_change_with_current_working_directory",
        "tests.test_pdf_figure_filename.FigureFilenameTests.test_distinct_sqlite_file_path_strings_never_share_a_pdf_scope",
        "tests.test_pdf_figure_filename.FigureFilenameTests.test_unicode_only_caption_falls_back_to_figure",
        "tests.test_pdf_figure_filename.FigureFilenameTests.test_real_import_ready_files_and_manifests_are_isolated_per_pdf",
        "tests.test_pdf_figure_filename.FigureFilenameTests.test_import_ready_copy_failure_preserves_previous_projection",
        "tests.test_pdf_figure_filename.FigureFilenameTests.test_import_ready_missing_source_preserves_previous_projection",
        "tests.test_pdf_figure_filename.FigureFilenameTests.test_import_ready_publish_reports_temporary_backup_cleanup_failure",
        "tests.test_pdf_figure_filename.FigureFilenameTests.test_import_ready_manifest_write_failure_preserves_previous_projection",
        "tests.test_pdf_figure_filename.FigureFilenameTests.test_import_ready_publish_failure_restores_previous_projection",
        "tests.test_pdf_figure_filename.FigureFilenameTests.test_import_ready_incomplete_rollback_preserves_manual_recovery_directory",
        "tests.test_pdf_figure_filename.FigureFilenameTests.test_unambiguous_legacy_import_ready_artifacts_are_removed_after_sync",
        "tests.test_pdf_figure_filename.FigureFilenameTests.test_case_only_legacy_scopes_are_ambiguous_on_case_insensitive_filesystems",
        "tests.test_pdf_figure_filename.FigureFilenameTests.test_locked_legacy_artifacts_do_not_fail_import_ready_sync",
        "tests.test_pdf_figure_filename.FigureFilenameTests.test_second_run_removes_only_untouched_audit_artifacts_in_the_same_scope",
        "tests.test_pdf_figure_filename.FigureFilenameTests.test_failed_main_extraction_does_not_cleanup_previous_audit_artifacts",
        "tests.test_pdf_figure_filename.FigureFilenameTests.test_persist_failure_preserves_old_run_artifacts_and_removes_current_run",
        "tests.test_pdf_figure_filename.FigureFilenameTests.test_commit_failure_does_not_publish_exports_and_closes_document",
        "tests.test_pdf_figure_filename.FigureFilenameTests.test_export_failure_is_partial_success_and_resume_retries_projection_only",
        "tests.test_pdf_figure_filename.FigureFilenameTests.test_resume_with_missing_source_image_runs_full_extraction",
        "tests.test_pdf_figure_filename.FigureFilenameTests.test_agentic_extract_figures_marks_projection_failure_partial",
        "tests.test_pdf_figure_filename.FigureFilenameTests.test_agentic_extract_figures_keeps_success_and_resume_statuses_passed",
        "tests.test_pdf_figure_filename.FigureFilenameTests.test_stale_audit_cleanup_permission_error_is_warning_only",
        "tests.test_pdf_figure_filename.FigureFilenameTests.test_failed_run_cleanup_permission_error_is_warning_only",
        "tests.test_figure_profile.PDFExtractorProfileTests.test_import_ready_export_copies_only_accepted_figures",
        "tests.test_ui_localization.UiLocalizationTests.test_pdf_worker_logs_import_ready_export_failure_in_english_and_chinese",
        "tests.test_ui_localization.UiLocalizationTests.test_pdf_worker_logs_import_ready_cleanup_warning_in_english_and_chinese",
        "tests.test_release_workflow.ReleaseWorkflowTests.test_release_requires_every_expected_ci_check",
        "tests.test_release_workflow.ReleaseWorkflowTests.test_release_validates_version_metadata_and_uses_descriptive_title",
        "tests.test_path_identity.PathIdentityTests.test_paths_overlap_uses_physical_ancestor_for_case_insensitive_nonexistent_child",
        "tests.test_path_identity.PathIdentityTests.test_paths_overlap_keeps_case_sensitive_sibling_directories_distinct",
        "tests.test_2d_sqlite_project_load.Project2DSQLiteLoadTests.test_failed_load_restores_complete_manager_runtime_state",
        "tests.test_2d_sqlite_project_load.Project2DSQLiteLoadTests.test_failed_create_restores_complete_manager_runtime_state",
        "tests.test_2d_sqlite_project_load.Project2DSQLiteLoadTests.test_deep_runtime_snapshot_restores_in_place_nested_mutations",
        "tests.test_2d_sqlite_project_load.Project2DSQLiteLoadTests.test_sqlite_reload_rebuilds_stl_label_mirrors_from_provenance",
        "tests.test_stl_review_bridge.StlReviewBridgeTests.test_register_updates_existing_record_once_without_false_truth_version",
        "tests.test_stl_review_bridge.StlReviewBridgeTests.test_register_new_source_advances_integrity_version_in_single_save",
        "tests.test_stl_review_bridge.StlReviewBridgeTests.test_save_false_stages_without_changing_sqlite",
        "tests.test_stl_review_bridge.StlReviewBridgeTests.test_sqlite_write_failure_restores_memory_and_transaction",
        "tests.test_stl_review_bridge.StlReviewBridgeTests.test_partial_add_failure_removes_already_staged_image",
        "tests.test_stl_review_bridge.StlReviewBridgeTests.test_json_replace_failure_restores_memory_and_project_file",
        "tests.test_tif_annotation_workflow_controller.TifAnnotationWorkflowControllerTests.test_worker_signal_is_delivered_on_controller_gui_thread",
        "tests.test_tif_annotation_workflow_controller.TifAnnotationWorkflowControllerTests.test_auto_save_wait_timeout_preserves_running_task_references",
        "tests.test_tif_annotation_workflow_controller.TifAnnotationWorkflowControllerTests.test_sync_save_stops_when_auto_save_wait_times_out",
        "tests.test_tif_annotation_workflow_controller.TifAnnotationWorkflowControllerTests.test_dirty_without_slice_indexes_uses_bounded_recovery_snapshot",
        "tests.test_tif_annotation_workflow_controller.TifAnnotationWorkflowControllerTests.test_pending_recovery_restores_slice_history_tool_and_material",
        "tests.test_tif_annotation_workflow_controller.TifAnnotationWorkflowControllerTests.test_empty_recovery_snapshot_does_not_clear_existing_pending_recovery",
        "tests.test_tif_annotation_workflow_controller.TifAnnotationWorkflowControllerTests.test_auto_save_metadata_failure_keeps_dirty_slice_recovery",
        "tests.test_tif_annotation_workflow_controller.TifAnnotationWorkflowControllerTests.test_manual_save_metadata_failure_keeps_dirty_slice_recovery",
        "tests.test_tif_annotation_workflow_controller.TifAnnotationWorkflowControllerTests.test_unsaved_cancel_restores_previously_active_auto_save_timer",
        "tests.test_tif_annotation_workflow_controller.TifAnnotationWorkflowControllerTests.test_failed_save_restores_previously_active_auto_save_timer",
        "tests.test_tif_annotation_workflow_controller.TifAnnotationWorkflowControllerTests.test_unrestorable_pending_recovery_blocks_close_without_discarding_snapshot",
        "tests.test_tif_annotation_workflow_controller.TifAnnotationWorkflowControllerTests.test_current_manual_save_failure_restarts_enabled_auto_save_timer",
        "tests.test_tif_project.TifProjectTests.test_failed_load_restores_complete_manager_runtime_state",
        "tests.test_tif_project.TifProjectTests.test_successful_load_does_not_carry_pending_data_version_into_target_project",
        "tests.test_tif_project.TifProjectTests.test_failed_create_restores_complete_manager_runtime_state",
        "tests.test_tif_project.TifProjectTests.test_manifest_write_then_raise_removes_published_project_entry",
        "tests.test_tif_project.TifProjectTests.test_volume_sidecar_copy_entrypoints_enforce_platform_path_identity",
        "tests.test_tif_project.TifProjectTests.test_volume_sidecar_copy_entrypoints_reject_ancestor_and_descendant_overlap",
        "tests.test_tif_project.TifProjectTests.test_working_edit_promotion_enforces_platform_reported_path_identity",
        "tests.test_tif_project.TifProjectTests.test_full_truth_promotion_rejects_ancestor_target_without_touching_labels",
        "tests.test_tif_project.TifProjectTests.test_part_truth_promotions_reject_ancestor_target_without_touching_labels",
        "tests.test_tif_project.TifProjectTests.test_part_truth_promotion_rejects_editable_platform_alias",
        "tests.test_tif_project.TifProjectTests.test_part_reslice_truth_promotion_rejects_editable_platform_alias",
        "tests.test_tif_project.TifProjectTests.test_part_manual_truth_same_physical_path_remains_existing_truth",
        "tests.test_tif_project.TifProjectTests.test_copy_model_draft_to_working_edit_commits_volume_and_sqlite_record",
        "tests.test_tif_project.TifProjectTests.test_single_volume_commit_cleanup_error_is_recorded_without_failing_copy",
        "tests.test_tif_project.TifProjectTests.test_volume_cleanup_warning_sidecar_is_bounded_and_atomic_write_failure_is_nonfatal",
        "tests.test_tif_project.TifProjectTests.test_volume_cleanup_warning_atomic_replace_failure_preserves_previous_file",
        "tests.test_tif_project.TifProjectTests.test_volume_cleanup_warning_sidecar_requires_matching_nonempty_project_id",
        "tests.test_tif_project.TifProjectTests.test_malformed_volume_cleanup_warning_sidecar_does_not_block_project_load",
        "tests.test_tif_project.TifProjectTests.test_volume_cleanup_warning_reader_enforces_exact_byte_limit",
        "tests.test_tif_project.TifProjectTests.test_volume_cleanup_warning_reader_rejects_identity_swap_during_open",
        "tests.test_tif_project.TifProjectTests.test_volume_cleanup_warning_sidecar_rejects_parent_directory_alias",
        "tests.test_tif_project.TifProjectTests.test_volume_cleanup_warning_concurrent_processes_merge_without_loss",
        "tests.test_tif_project.TifProjectTests.test_cleanup_warning_paths_are_relative_or_redacted_before_persistence",
        "tests.test_tif_project.TifProjectTests.test_saturated_cleanup_warning_merge_preserves_each_new_writer",
        "tests.test_tif_project.TifProjectTests.test_invalid_regular_cleanup_sidecar_is_isolated_before_new_warning",
        "tests.test_tif_project.TifProjectTests.test_cleanup_warning_error_redacts_relative_external_paths",
        "tests.test_tif_project.TifProjectTests.test_invalid_cleanup_sidecar_is_preserved_when_isolation_slot_is_unsafe",
        "tests.test_tif_project.TifProjectTests.test_safe_json_fstat_failure_closes_fd_and_removes_temp",
        "tests.test_tif_project.TifProjectTests.test_posix_parent_fstat_failure_closes_new_directory_descriptor",
        "tests.test_tif_project.TifProjectTests.test_advisory_lock_fdopen_failure_closes_open_descriptor",
        "tests.test_tif_project.TifProjectTests.test_advisory_lock_rejects_repeated_acquire_without_losing_lock",
        "tests.test_tif_project.TifProjectTests.test_safe_json_read_rejects_content_stat_change_and_closes_fd",
        "tests.test_tif_project.TifProjectTests.test_batch_volume_commit_cleanup_errors_are_recorded_without_failing_promotion",
        "tests.test_tif_project.TifProjectTests.test_copy_model_draft_rejects_ancestor_target_without_touching_manual_truth",
        "tests.test_tif_project.TifProjectTests.test_copy_model_draft_rejects_target_inside_manual_truth",
        "tests.test_tif_project.TifProjectTests.test_copy_manual_truth_to_distinct_working_edit_remains_supported",
        "tests.test_tif_project.TifProjectTests.test_copy_model_draft_save_failure_rolls_back_volume_memory_and_sqlite",
        "tests.test_tif_project.TifProjectTests.test_copy_model_draft_refuses_working_edit_alias_to_manual_truth",
        "tests.test_tif_project.TifProjectTests.test_copy_model_draft_enforces_platform_reported_path_identity",
        "tests.test_tif_project.TifProjectTests.test_copy_model_draft_refuses_source_alias_to_manual_truth",
        "tests.test_tif_workbench.TifWorkbenchTests.test_copy_model_draft_releases_open_working_edit_before_replacement",
        "tests.test_tif_workbench.TifWorkbenchTests.test_copy_model_draft_failure_restores_unsaved_working_edit",
        "tests.test_tif_workbench.TifWorkbenchTests.test_copy_model_draft_dirty_without_slice_indexes_blocks_destructive_copy",
        "tests.test_tif_workbench.TifWorkbenchTests.test_copy_model_draft_context_mismatch_restores_auto_save_timer",
        "tests.test_tif_workbench.TifWorkbenchTests.test_copy_model_draft_rechecks_write_lock_after_confirmation",
        "tests.test_tif_workbench.TifWorkbenchTests.test_copy_model_draft_copy_and_reload_failure_keeps_pending_recovery",
        "tests.test_tif_workbench.TifWorkbenchTests.test_copy_model_draft_second_attempt_reuses_pending_recovery_after_double_failure",
        "tests.test_tif_workbench.TifWorkbenchTests.test_sync_save_metadata_failure_preserves_dirty_slice_snapshot",
        "tests.test_tif_project_lifecycle_controller.TifProjectLifecycleControllerTests.test_close_project_stops_when_auto_save_wait_times_out",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_window_close_honors_active_tif_unsaved_cancel",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_open_project_does_not_replace_active_tif_when_close_is_cancelled",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_failed_target_load_restores_closed_active_tif_workbench",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_open_tif_refresh_failure_reloads_previous_tif_project",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_tif_refresh_failure_restores_preclose_specimen_part_reslice_selection",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_open_tif_config_failure_reloads_previous_tif_project",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_open_tif_log_failure_reloads_previous_tif_project",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_image_to_tif_config_failure_restores_source_manager_and_ui",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_image_to_tif_log_failure_restores_source_manager_and_ui",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_image_to_tif_refresh_failure_restores_empty_config_tab_canvas_and_cache",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_real_partial_tif_refresh_restores_source_after_nested_widget_failure",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_start_to_tif_log_failure_restores_start_center_state",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_stl_to_tif_log_failure_restores_stl_source_state",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_tif_to_2d_prepare_failure_restores_all_source_state",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_stl_common_finalize_failure_rolls_back_staged_registration",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_stl_final_save_failure_rolls_back_staged_registration",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_successful_stl_open_commits_once_then_finalizes_rollback_token",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_stl_import_action_refresh_failure_rolls_back_and_restores_ui",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_tif_close_exception_rebuilds_workbench_and_aborts_switch",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_new_tif_refresh_failure_reloads_previous_tif_project",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_tif_recovery_refreshes_workbench_when_config_rollback_fails",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_new_2d_project_does_not_flush_or_create_when_active_tif_close_is_cancelled",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_new_tif_project_does_not_flush_or_create_when_active_tif_close_is_cancelled",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_invalid_project_entry_does_not_close_active_tif",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_legacy_migration_closes_active_tif_before_writing_outputs",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_successful_legacy_migration_closes_active_tif_only_once",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_new_2d_finalize_failures_rollback_disk_and_allow_same_name_retry",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_new_tif_finalize_failures_rollback_disk_and_allow_same_name_retry",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_new_project_preexisting_artifacts_are_never_removed_or_claimed_for_recovery",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_new_2d_cleanup_move_failure_preserves_project_for_same_name_recovery",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_preexisting_sqlite_journal_blocks_new_2d_and_tif_before_publication",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_successful_finalize_remove_failure_leaves_committed_marker",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_structurally_valid_forged_marker_never_claims_existing_project",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_expired_recovery_marker_never_claims_or_cleans_artifacts",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_recovery_marker_rooted_atomic_write_preserves_fixed_tmp_file",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_recovery_marker_write_refuses_path_outside_project",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_recovery_marker_rooted_atomic_write_preserves_fixed_tmp_link",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_delete_marker_update_failure_deletes_nothing_and_memory_recovers",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_partial_quarantine_delete_failure_keeps_state_and_same_owner_finishes",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_preserved_new_project_marker_requires_manual_review_for_fresh_owner",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_new_project_sidecar_toctou_is_preserved_and_refused",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_bad_recovery_marker_and_modified_preserved_project_are_never_claimed",
        "tests.test_main_window_stage4_project_lifecycle.MainWindowStage4ProjectLifecycleTests.test_partial_quarantine_requires_same_owner_recovery",
        "tests.test_main_window_stage7_training_prediction.MainWindowStage7TrainingPredictionTests.test_tif_write_threads_block_project_switch",
        "tests.test_main_window_stage8_architecture.MainWindowStage8ArchitectureTests.test_workflow_modules_stay_within_reviewable_size",
        "tests.test_main_window_stage8_architecture.MainWindowStage8ArchitectureTests.test_tif_task_manager_activity_blocks_project_switch",
        "tests.test_main_window_stage8_architecture.MainWindowStage8ArchitectureTests.test_finished_tif_thread_does_not_block_without_active_task",
        "tests.test_tif_mesh_export_dialog.TifMeshExportDialogTests.test_workbench_routes_full_and_reslice_scope_to_mesh_dialog",
    ],
    "generic_vlm_stl": [
        "tests.test_generic_export_schema",
        "tests.test_generic_taxonomy_workflow",
        "tests.test_macro_micro_pipeline",
        "tests.test_stl_project",
        "tests.test_stl_rendered_views",
        "tests.test_stl_review_bridge",
        "tests.test_vlm_preannotation",
    ],
    "round5_traceability": [
        "tests.test_agentic_train_project",
        "tests.test_blink_reproducibility",
        "tests.test_blink_training_backend_guard",
        "tests.test_blink_training_run_lifecycle",
        "tests.test_embedded_skill_bundles",
        "tests.test_embedded_taxonomy_paper_finder",
        "tests.test_engine_weight_staging",
        "tests.test_file_integrity",
        "tests.test_gui_training_run_lifecycle",
        "tests.test_integrity_manifest_service",
        "tests.test_location_registry",
        "tests.test_loss_weight_config",
        "tests.test_loss_weight_profile_wiring",
        "tests.test_path_identity",
        "tests.test_project_integrity_bridge",
        "tests.test_project_integrity_recovery",
        "tests.test_project_integrity_registry",
        "tests.test_tif_blink_training_lifecycle",
        "tests.test_tif_integrity_bridge",
        "tests.test_training_initial_weights",
        "tests.test_training_integrity_recovery_dialog",
        "tests.test_training_preflight_worker",
        "tests.test_training_run_2d",
        "tests.test_training_run_notes",
        "tests.test_training_run_recorder",
        "tests.test_training_run_setup",
        "tests.test_training_run_tif",
        "tests.test_training_truth",
        "tests.test_training_weight_publisher",
    ],
    "round5_inference": [
        "tests.test_predict_full_pipeline_baseline",
        "tests.test_inference_thread_runtime",
    ],
    "round5_mesh": [
        "tests.test_mesh_export",
        "tests.test_mesh_export_ledger",
        "tests.test_tif_mesh_export_dialog",
    ],
    "round5_local_axis_risk": [
        "tests.test_tif_local_axis_batch",
        "tests.test_tif_result_review_controller",
        "tests.test_tif_truth_policy",
        "tests.test_tif_truth_promotion_service",
    ],
    "round5_ci_smoke": [
        "tests.test_integrity_manifest_service.IntegrityManifestServiceTests.test_create_and_verify_manifest_atomically",
        "tests.test_integrity_manifest_service.IntegrityManifestServiceTests.test_pending_started_record_recovers_to_incomplete",
        "tests.test_project_integrity_bridge.ProjectIntegrityBridgeTests.test_training_snapshot_uses_current_registered_version",
        "tests.test_predict_full_pipeline_baseline.PredictFullPipelineBaselineTests.test_frozen_scenarios_match_public_result_and_diagnostic_baseline",
        "tests.test_mesh_export.MeshExportTests.test_non_isotropic_zyx_volume_becomes_physical_xyz_mesh",
        "tests.test_mesh_export.MeshExportTests.test_export_records_raw_and_preview_stl_in_sqlite",
        "tests.test_mesh_export.MeshExportTests.test_cancel_after_first_item_leaves_incomplete_recoverable_run",
        "tests.test_mesh_export.MeshExportTests.test_temporary_stl_validation_failure_leaves_no_partial_file",
        "tests.test_tif_local_axis_batch.TifLocalAxisBatchTests.test_risk_components_compare_active_model_id_and_version",
        "tests.test_tif_local_axis_batch.TifLocalAxisBatchTests.test_sorting_and_accepting_selected_axis_do_not_bypass_manual_truth_gate",
        "tests.test_tif_result_review_controller.TifResultReviewControllerTests.test_accept_selected_results_uses_truth_promotion_service",
        "tests.test_tif_truth_policy.TifTruthPolicyTests.test_training_uses_manual_truth_only",
    ],
    "round5_path_safety": [
        "tests.test_file_integrity.FileIntegrityTests.test_tree_rejects_symlink_instead_of_following_it",
        "tests.test_file_integrity.FileIntegrityTests.test_root_symlink_is_rejected",
        "tests.test_integrity_manifest_service.IntegrityManifestServiceTests.test_managed_root_symlink_is_rejected_even_when_target_is_contained",
        "tests.test_integrity_manifest_service.IntegrityManifestServiceTests.test_managed_parent_symlink_is_rejected_before_fingerprinting",
        "tests.test_location_registry.LocationRegistryTests.test_target_and_parent_symlinks_are_rejected",
        "tests.test_location_registry.LocationRegistryTests.test_windows_reparse_path_is_rejected_without_os_privileges",
        "tests.test_project_integrity_recovery.ProjectIntegrityRecoveryTests.test_inspection_and_registration_reject_linked_parent",
        "tests.test_tif_integrity_bridge.TifIntegrityBridgeTests.test_baseline_rejects_asset_below_symlinked_parent",
        "tests.test_project_integrity_registry.ProjectIntegrityRegistryTests.test_resolver_rejects_symlink_root_and_leaves_no_temp_files",
        "tests.test_project_integrity_registry.ProjectIntegrityRegistryTests.test_resolver_rejects_windows_reparse_root_without_os_privileges",
        "tests.test_mesh_export.MeshExportTests.test_manual_truth_path_rejects_symlink_components",
        "tests.test_mesh_export.MeshExportTests.test_export_target_rejects_symlink_components",
        "tests.test_mesh_export.MeshExportTests.test_safe_cleanup_rejects_linked_export_root",
        "tests.test_mesh_export.MeshExportTests.test_safe_cleanup_rejects_linked_descendant",
        "tests.test_mesh_export.MeshExportTests.test_verify_rejects_linked_export_root",
        "tests.test_training_run_recorder.TrainingRunRecorderTests.test_external_directory_symlink_root_is_rejected",
        "tests.test_training_run_recorder.TrainingRunRecorderTests.test_registered_path_base_rejects_symlinked_parent",
        "tests.test_training_run_recorder.TrainingRunRecorderTests.test_artifact_symlink_is_rejected",
        "tests.test_training_run_notes.TrainingRunNoteStoreTests.test_note_projection_symlink_is_ignored",
        "tests.test_training_weight_publisher.TrainingWeightPublisherTests.test_source_file_and_parent_symlinks_are_rejected",
        "tests.test_training_weight_publisher.TrainingWeightPublisherTests.test_managed_root_and_training_runs_links_are_rejected",
        "tests.test_training_weight_publisher.TrainingWeightPublisherTests.test_unsafe_hidden_directory_is_preserved_for_manual_review",
        "tests.test_path_identity.PathIdentityTests.test_realpath_resolves_directory_aliases_when_supported",
        "tests.test_path_identity.PathIdentityTests.test_project_image_state_uses_one_key_across_directory_aliases",
    ],
}

# Keep the historical name as a compatibility alias for the current release audit.
SUITES["v249_post_release_audit"] = list(SUITES["v2410_release_audit"])

DEFAULT_ORDER = [
    name
    for name in SUITES
    if name not in {
        "validation_chunk_sample",
        "v2410_release_audit",
        "v249_post_release_audit",
        "round5_ci_smoke",
        "round5_path_safety",
    }
]
SUITE_CHOICES = list(SUITES)
SUITE_DEFAULT_CHUNK_SIZES = {
    "gui_smoke": 3,
    "ui_polish": 5,
}


def _test_count(modules: list[str]) -> int:
    total = 0
    for module in modules:
        path = ROOT / (module.replace(".", os.sep) + ".py")
        if not path.exists():
            if module.startswith("tests.") and ".test_" in module:
                total += 1
            continue
        with path.open("r", encoding="utf-8") as handle:
            total += sum(1 for line in handle if line.lstrip().startswith("def test_"))
    return total


def _iter_test_ids(suite: unittest.TestSuite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _iter_test_ids(item)
        else:
            test_id = item.id() if hasattr(item, "id") else ""
            if test_id:
                yield test_id


def _test_ids(modules: list[str]) -> list[str]:
    suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
    return list(_iter_test_ids(suite))


def _chunks(items: list[str], size: int) -> list[list[str]]:
    if size <= 0:
        return [items]
    return [items[index : index + size] for index in range(0, len(items), size)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run TaxaMask validation suites in stable groups.")
    parser.add_argument("--list", action="store_true", help="List available suites and test counts.")
    parser.add_argument("--suite", action="append", choices=SUITE_CHOICES, help="Run only the named suite. Can be repeated.")
    parser.add_argument("--timeout", type=int, default=900, help="Per-suite timeout in seconds.")
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=None,
        help="Override suite chunking. Use 0 to disable chunking; omit to use stable per-suite defaults.",
    )
    args = parser.parse_args(argv)

    if args.list:
        for name in DEFAULT_ORDER:
            print(f"{name}: {_test_count(SUITES[name])} tests")
        return 0

    selected = args.suite or DEFAULT_ORDER
    env = os.environ.copy()
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env.setdefault("QT_OPENGL", "software")
    env.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --disable-gpu-compositing")

    python = sys.executable
    for name in selected:
        modules = SUITES[name]
        print(f"\n=== {name} ({_test_count(modules)} tests) ===", flush=True)
        chunk_size = SUITE_DEFAULT_CHUNK_SIZES.get(name, 0) if args.chunk_size is None else int(args.chunk_size)
        if chunk_size > 0:
            try:
                test_ids = _test_ids(modules)
            except Exception as exc:
                print(f"Failed to collect test ids for {name}: {exc}", file=sys.stderr)
                return 1
            groups = _chunks(test_ids, chunk_size) if test_ids else [modules]
            for index, group in enumerate(groups, 1):
                print(f"--- {name} chunk {index}/{len(groups)} ({len(group)} tests) ---", flush=True)
                command = [python, "-m", "unittest", *group]
                try:
                    subprocess.run(command, cwd=ROOT, env=env, timeout=args.timeout, check=True)
                except subprocess.TimeoutExpired:
                    print(f"Suite chunk timed out after {args.timeout}s: {name} chunk {index}", file=sys.stderr)
                    return 124
                except subprocess.CalledProcessError as exc:
                    print(f"Suite chunk failed: {name} chunk {index}", file=sys.stderr)
                    return int(exc.returncode or 1)
            continue

        command = [python, "-m", "unittest", *modules]
        try:
            subprocess.run(command, cwd=ROOT, env=env, timeout=args.timeout, check=True)
        except subprocess.TimeoutExpired:
            print(f"Suite timed out after {args.timeout}s: {name}", file=sys.stderr)
            return 124
        except subprocess.CalledProcessError as exc:
            print(f"Suite failed: {name}", file=sys.stderr)
            return int(exc.returncode or 1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
