# TaxaMask Round 4 Main Window Method Inventory

由 `scripts/analyze_main_window_architecture.py` 生成。Stage 0 冻结当前责任、兼容入口和目标阶段，实施时必须结合真实调用复核。

## Metrics

| Metric | Value |
| --- | --- |
| main_physical_lines | 16024 |
| top_level_class_count | 22 |
| top_level_function_count | 35 |
| all_method_count | 592 |
| private_method_count | 413 |
| connection_count | 194 |
| source_state_assignment_lines | 658 |
| main_window_lines | 9483 |
| main_window_method_count | 390 |
| main_window_connection_count | 128 |
| main_window_init_lines | 668 |
| main_window_methods_ge_50 | 42 |
| main_window_methods_ge_100 | 10 |
| main_window_unique_state_fields | 238 |
| main_window_state_assignment_occurrences | 418 |
| main_import_site_count | 14 |
| key_test_reference_line_count | 324 |
| key_test_private_reference_occurrences | 142 |
| key_test_unique_private_references | 51 |
| async_entry_count | 16 |

## Top-level Classes

| Line | Size | Class | Methods | Connects | Refs | Stage |
| --- | --- | --- | --- | --- | --- | --- |
| 469 | 41 | `InferenceThread` | 2 | 0 | 2 | 1 |
| 512 | 87 | `VlmPreannotationThread` | 2 | 0 | 2 | 1 |
| 601 | 31 | `DatasetExportThread` | 2 | 0 | 1 | 1 |
| 634 | 22 | `ImageImportThread` | 2 | 0 | 2 | 1 |
| 658 | 30 | `ExternalBatchInferenceThread` | 2 | 0 | 2 | 1 |
| 690 | 20 | `ExternalTrainingThread` | 2 | 0 | 2 | 1 |
| 1887 | 5 | `NoWheelComboBox` | 1 | 0 | 16 | 1 |
| 1894 | 5 | `NoWheelSpinBox` | 1 | 0 | 4 | 1 |
| 1901 | 5 | `NoWheelSlider` | 1 | 0 | 2 | 1 |
| 1908 | 57 | `ImageGroupListWidget` | 5 | 0 | 1 | 1 |
| 2010 | 208 | `TrainingThread` | 2 | 0 | 1 | 1 |
| 2220 | 173 | `TrainingPreflightDialog` | 14 | 2 | 4 | 2 |
| 2394 | 304 | `TrainingReportDialog` | 12 | 6 | 5 | 2 |
| 2700 | 113 | `TrainingResultBrowserDialog` | 7 | 6 | 2 | 2 |
| 2815 | 667 | `RouteManagementPanel` | 34 | 7 | 9 | 2 |
| 3483 | 2135 | `ModelSettingsDialog` | 67 | 22 | 20 | 2 |
| 5620 | 138 | `GeneralSettingsDialog` | 5 | 3 | 4 | 2 |
| 5760 | 257 | `TifModelSettingsDialog` | 12 | 5 | 2 | 2 |
| 6019 | 48 | `ExportDialog` | 4 | 3 | 4 | 2 |
| 6069 | 93 | `BlinkEntryDialog` | 4 | 3 | 12 | 2 |
| 6164 | 354 | `LiteratureDescriptionDialog` | 21 | 9 | 4 | 2 |
| 6520 | 9483 | `MainWindow` | 390 | 128 | 32 | 3 |

## MainWindow Workflow Counts

| Workflow | Methods |
| --- | --- |
| annotation_sam | 20 |
| blink | 35 |
| dialog_settings | 37 |
| image_navigation | 61 |
| pdf_evidence | 1 |
| project_lifecycle | 53 |
| runtime_worker | 15 |
| shell_start_agent | 48 |
| tif_integration | 1 |
| training_model | 39 |
| unclassified | 31 |
| vlm_prediction_export | 49 |

## Compatibility Counts

| Compatibility | Methods |
| --- | --- |
| internal_or_unreferenced | 227 |
| public_or_source_compatibility | 38 |
| signal_compatibility | 59 |
| test_compatibility | 66 |

## MainWindow Methods

| Line | Size | Method | Workflow | Stage | Compatibility | Source refs | Test refs | Signal refs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 6524 | 668 | `__init__` | unclassified | 8 | public_or_source_compatibility | 179 | 129 | 0 |
| 7193 | 2 | `_is_tif_workflow_enabled` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 7196 | 9 | `_show_tif_workflow_unavailable` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 7206 | 10 | `_apply_window_icon` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 7217 | 18 | `apply_startup_window_geometry` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 7236 | 124 | `_build_start_center` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 7361 | 25 | `_build_start_quick_panel` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 7387 | 76 | `_build_project_console` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 7464 | 3 | `_toggle_start_project_console` | shell_start_agent | 3 | signal_compatibility | 0 | 0 | 1 |
| 7468 | 12 | `_update_start_project_console_collapsed_state` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 7481 | 12 | `_build_project_console_row` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 7494 | 32 | `_build_workflow_card` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 7527 | 4 | `_show_start_center` | shell_start_agent | 3 | test_compatibility | 0 | 2 | 0 |
| 7532 | 48 | `_update_start_center_texts` | shell_start_agent | 3 | test_compatibility | 0 | 1 | 0 |
| 7581 | 3 | `_handle_agent_dashboard_status_changed` | shell_start_agent | 3 | signal_compatibility | 0 | 0 | 1 |
| 7585 | 11 | `_update_start_agent_status` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 7597 | 45 | `_refresh_project_console` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 7643 | 8 | `_start_console_collapsed_summary` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 7652 | 22 | `_start_console_project_summary` | shell_start_agent | 3 | test_compatibility | 0 | 1 | 0 |
| 7675 | 13 | `_compact_project_path` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 7689 | 19 | `_start_console_image_summary` | shell_start_agent | 3 | test_compatibility | 0 | 1 | 0 |
| 7709 | 22 | `_start_console_tif_summary` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 7732 | 14 | `_start_console_pdf_summary` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 7747 | 5 | `_is_pdf_candidate_provenance` | pdf_evidence | 5 | test_compatibility | 0 | 1 | 0 |
| 7753 | 5 | `_start_console_agent_status` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 7759 | 7 | `_agent_current_workflow_label` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 7767 | 8 | `_agent_current_project_label` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 7782 | 7 | `_recent_text_excerpt` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 7790 | 5 | `_agent_context_text` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 7796 | 202 | `_compact_agent_context` | shell_start_agent | 3 | public_or_source_compatibility | 1 | 5 | 0 |
| 7999 | 27 | `_collect_image_workbench_agent_context` | shell_start_agent | 3 | public_or_source_compatibility | 1 | 4 | 0 |
| 8027 | 13 | `_collect_blink_agent_context` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 8041 | 30 | `_pdf_agent_prompt` | shell_start_agent | 3 | test_compatibility | 0 | 1 | 0 |
| 8072 | 15 | `open_agent_for_pdf_workflow` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 8088 | 27 | `open_agent_from_context` | shell_start_agent | 3 | public_or_source_compatibility | 2 | 3 | 6 |
| 8116 | 2 | `return_to_start_center_with_context` | shell_start_agent | 3 | public_or_source_compatibility | 1 | 1 | 4 |
| 8119 | 8 | `_open_workflow_from_agent` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 8128 | 8 | `_open_model_settings_from_agent` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 8137 | 6 | `enter_image_workflow` | shell_start_agent | 3 | public_or_source_compatibility | 3 | 9 | 0 |
| 8144 | 8 | `enter_tif_workflow` | shell_start_agent | 3 | public_or_source_compatibility | 2 | 1 | 0 |
| 8153 | 2 | `_default_outputs_root` | unclassified | 8 | public_or_source_compatibility | 3 | 2 | 0 |
| 8156 | 4 | `_ensure_default_output_subdir` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 8161 | 2 | `_default_2d_stl_projects_root` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 8164 | 2 | `_default_tif_projects_root` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 8167 | 2 | `_default_startup_project_dir` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 8170 | 2 | `_startup_project_manifest_path` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 8173 | 2 | `_startup_legacy_json_project_path` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 8176 | 14 | `_open_or_create_startup_project` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 8191 | 4 | `_default_project_dialog_dir` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 8196 | 5 | `_current_2d_project_dir` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 8202 | 4 | `_default_2d_export_dir` | runtime_worker | 1 | test_compatibility | 0 | 2 | 0 |
| 8207 | 4 | `_default_vlm_preannotation_dir` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8212 | 18 | `_default_open_project_dir` | project_lifecycle | 4 | test_compatibility | 0 | 1 | 0 |
| 8231 | 8 | `_path_is_startup_project` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 8240 | 5 | `_path_is_inside_program_package` | unclassified | 8 | public_or_source_compatibility | 3 | 0 | 0 |
| 8246 | 8 | `open_last_project` | project_lifecycle | 4 | signal_compatibility | 0 | 1 | 1 |
| 8255 | 45 | `closeEvent` | project_lifecycle | 4 | public_or_source_compatibility | 13 | 0 | 0 |
| 8301 | 10 | `_active_recent_project_path` | project_lifecycle | 4 | test_compatibility | 0 | 1 | 0 |
| 8312 | 22 | `_shutdown_background_workers` | runtime_worker | 1 | public_or_source_compatibility | 1 | 0 | 0 |
| 8335 | 3 | `destroy` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 8339 | 5 | `_schedule_project_save` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 8345 | 5 | `_defer_project_save_for_active_navigation` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 8351 | 54 | `_flush_pending_project_save` | project_lifecycle | 4 | signal_compatibility | 0 | 3 | 1 |
| 8406 | 51 | `refresh_model_list` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8458 | 5 | `_selected_locator_timestamp` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8464 | 4 | `_selected_locator_display_text` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8469 | 9 | `_parent_model_filename` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8479 | 40 | `_build_locator_combo_label` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8520 | 7 | `_build_segmenter_combo_label` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8528 | 5 | `_selected_segmenter_timestamp` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8534 | 2 | `_active_project_route_manifest` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 8537 | 9 | `_active_model_profile_context` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 8547 | 6 | `_active_external_backend_config` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 8554 | 5 | `_selected_route_entry` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 8560 | 5 | `_route_runtime_status` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 8566 | 8 | `refresh_route_table` | dialog_settings | 2 | signal_compatibility | 0 | 30 | 2 |
| 8575 | 4 | `update_route_action_buttons` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 8580 | 16 | `_refresh_project_bound_views` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 8597 | 5 | `_project_image_count` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 8603 | 17 | `_prepare_image_list_for_project_open` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 8621 | 12 | `_preload_2d_stl_models_after_open` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8634 | 5 | `_ensure_tab_visible` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 8640 | 6 | `_remove_tab_if_present` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 8647 | 23 | `_apply_project_mode_tabs` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 8671 | 13 | `_is_tif_project_file` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 8685 | 11 | `_is_stl_project_file` | project_lifecycle | 4 | test_compatibility | 0 | 1 | 0 |
| 8697 | 7 | `_read_project_probe_payload` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 8705 | 6 | `_is_sqlite_project_manifest_payload` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 8712 | 2 | `_is_tif_sqlite_project_manifest_payload` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 8715 | 2 | `_is_2d_sqlite_project_manifest_payload` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 8718 | 15 | `_is_legacy_2d_json_project_payload` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 8734 | 2 | `_is_legacy_2d_json_project_file` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 8737 | 23 | `_candidate_manifest_paths_for_sqlite_database` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 8761 | 15 | `_manifest_for_sqlite_database_file` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 8777 | 3 | `_is_project_sqlite_database_file` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 8781 | 11 | `_active_sqlite_project_manager` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 8793 | 9 | `_flush_active_sqlite_project_before_maintenance` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 8803 | 6 | `_sqlite_maintenance_default_dir` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 8810 | 42 | `backup_current_sqlite_project` | project_lifecycle | 4 | test_compatibility | 0 | 1 | 0 |
| 8853 | 42 | `export_current_project_legacy_json` | runtime_worker | 1 | test_compatibility | 0 | 1 | 0 |
| 8896 | 23 | `open_current_sqlite_migration_report` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 8920 | 4 | `appoint_selected_route_expert` | blink | 6 | signal_compatibility | 0 | 1 | 1 |
| 8925 | 4 | `toggle_selected_route_enabled` | dialog_settings | 2 | signal_compatibility | 0 | 0 | 1 |
| 8930 | 4 | `delete_selected_route` | dialog_settings | 2 | signal_compatibility | 0 | 2 | 1 |
| 8935 | 30 | `_log_route_usage_summary` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 8966 | 4 | `_locator_model_path` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8971 | 4 | `_segmenter_model_path` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8976 | 18 | `_apply_locator_selection_to_runtime` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 8995 | 2 | `_locator_selection_needs_legacy_confirmation` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8998 | 20 | `_confirm_legacy_locator_selection_if_needed` | training_model | 7 | test_compatibility | 0 | 1 | 0 |
| 9019 | 5 | `_show_structured_training_preflight` | dialog_settings | 2 | test_compatibility | 0 | 1 | 0 |
| 9025 | 3 | `_is_locator_oom_error` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 9029 | 30 | `_ask_locator_oom_retry_resolution` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 9060 | 3 | `_is_parent_training_running` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 9064 | 4 | `_is_child_training_running` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 9069 | 2 | `_is_any_training_running` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 9072 | 19 | `_set_training_progress` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 9092 | 11 | `_connect_child_training_progress` | blink | 6 | test_compatibility | 0 | 1 | 0 |
| 9104 | 6 | `_on_child_training_result` | blink | 6 | signal_compatibility | 0 | 0 | 1 |
| 9111 | 3 | `_on_child_training_error` | blink | 6 | signal_compatibility | 0 | 0 | 1 |
| 9115 | 3 | `_on_child_training_cancelled` | blink | 6 | signal_compatibility | 0 | 0 | 1 |
| 9119 | 10 | `_on_child_training_finished` | blink | 6 | signal_compatibility | 0 | 0 | 1 |
| 9130 | 85 | `_launch_training_with_preflight` | dialog_settings | 2 | test_compatibility | 0 | 1 | 0 |
| 9216 | 15 | `_on_training_success` | training_model | 7 | signal_compatibility | 0 | 1 | 1 |
| 9232 | 13 | `_on_training_finished` | training_model | 7 | public_or_source_compatibility | 2 | 1 | 1 |
| 9246 | 38 | `_on_training_error` | training_model | 7 | public_or_source_compatibility | 2 | 0 | 1 |
| 9285 | 7 | `stop_training` | training_model | 7 | signal_compatibility | 0 | 0 | 1 |
| 9293 | 21 | `_apply_segmenter_selection_to_runtime` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 9315 | 12 | `update_model_delete_button_states` | training_model | 7 | signal_compatibility | 0 | 0 | 2 |
| 9328 | 33 | `_edit_parent_model_note` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 9362 | 2 | `edit_locator_model_note` | training_model | 7 | signal_compatibility | 0 | 1 | 1 |
| 9365 | 2 | `edit_segmenter_model_note` | training_model | 7 | signal_compatibility | 0 | 1 | 1 |
| 9368 | 36 | `on_locator_changed` | training_model | 7 | signal_compatibility | 0 | 1 | 1 |
| 9405 | 26 | `delete_locator_model` | training_model | 7 | signal_compatibility | 0 | 2 | 1 |
| 9432 | 3 | `on_segmenter_changed` | training_model | 7 | signal_compatibility | 0 | 0 | 1 |
| 9436 | 26 | `delete_segmenter_model` | training_model | 7 | signal_compatibility | 0 | 1 | 1 |
| 9463 | 3 | `on_model_changed` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 9467 | 29 | `create_menus` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 9497 | 21 | `new_project` | project_lifecycle | 4 | test_compatibility | 0 | 1 | 0 |
| 9519 | 22 | `new_tif_project` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 9542 | 9 | `_ensure_tif_project_open` | project_lifecycle | 4 | public_or_source_compatibility | 6 | 0 | 0 |
| 9552 | 29 | `import_tif_stack_action` | tif_integration | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 9582 | 28 | `import_amira_directory_action` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 9611 | 28 | `import_stl_rendered_views_action` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 9640 | 5 | `open_pdf_evidence_tools` | project_lifecycle | 4 | test_compatibility | 0 | 2 | 0 |
| 9646 | 41 | `open_pdf_multimodal_api_settings` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 9688 | 19 | `_choose_project_template` | project_lifecycle | 4 | test_compatibility | 0 | 1 | 0 |
| 9708 | 12 | `open_project` | project_lifecycle | 4 | public_or_source_compatibility | 2 | 1 | 1 |
| 9721 | 12 | `_confirm_legacy_2d_json_migration` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 9734 | 9 | `_existing_sqlite_manifest_for_legacy_json` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 9744 | 11 | `_confirm_open_existing_sqlite_migration` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 9756 | 12 | `_confirm_legacy_tif_json_migration` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 9769 | 11 | `_existing_tif_sqlite_manifest_for_legacy_json` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 9781 | 11 | `_confirm_open_existing_tif_sqlite_migration` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 9793 | 41 | `_migrate_legacy_2d_project_with_progress` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 9835 | 41 | `_migrate_legacy_tif_project_with_progress` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 9877 | 150 | `open_project_path` | project_lifecycle | 4 | public_or_source_compatibility | 2 | 14 | 0 |
| 10028 | 10 | `_format_relocation_preview` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 10039 | 54 | `check_relocate_project_images` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 10094 | 6 | `_part_item_name` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 10101 | 2 | `_current_part_name` | unclassified | 8 | test_compatibility | 0 | 5 | 0 |
| 10104 | 15 | `_workbench_parent_parts` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 10120 | 3 | `_is_parent_part` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 10124 | 23 | `_part_tree_parent_for` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 10148 | 18 | `_route_parents_for_child` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 10167 | 25 | `_resolve_child_parent` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 10193 | 15 | `_parent_context_box` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 10209 | 5 | `_current_shrink_loose_boxes` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 10215 | 28 | `_auto_boxes_for_canvas` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 10244 | 10 | `_refresh_current_canvas_boxes` | annotation_sam | 6 | test_compatibility | 0 | 1 | 0 |
| 10255 | 15 | `_route_entry_for_context` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 10271 | 26 | `_route_expert_status` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 10298 | 73 | `_current_blink_context` | blink | 6 | public_or_source_compatibility | 1 | 0 | 0 |
| 10372 | 10 | `_parent_box_aspect_ratio` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 10383 | 24 | `_parent_context_options` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 10408 | 15 | `_refresh_annotation_box_constraints` | annotation_sam | 6 | signal_compatibility | 0 | 0 | 1 |
| 10424 | 8 | `_active_box_tool_role` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 10433 | 6 | `_refresh_blink_refine_state` | blink | 6 | test_compatibility | 0 | 9 | 0 |
| 10440 | 7 | `_append_part_tree_item` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 10448 | 22 | `_select_part_in_tree` | unclassified | 8 | test_compatibility | 0 | 18 | 0 |
| 10471 | 17 | `_first_selectable_part_item` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 10489 | 75 | `_refresh_part_tree` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 10565 | 8 | `add_taxonomy_part` | image_navigation | 5 | public_or_source_compatibility | 1 | 29 | 1 |
| 10574 | 7 | `_count_ai_labels_for_images` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 10582 | 67 | `_choose_clear_ai_scope` | unclassified | 8 | test_compatibility | 0 | 1 | 0 |
| 10650 | 41 | `rename_taxonomy_part` | image_navigation | 5 | public_or_source_compatibility | 1 | 3 | 1 |
| 10692 | 13 | `remove_taxonomy_part` | image_navigation | 5 | public_or_source_compatibility | 1 | 6 | 1 |
| 10706 | 55 | `clear_ai_labels` | unclassified | 8 | signal_compatibility | 0 | 2 | 1 |
| 10762 | 6 | `on_global_labels_updated` | unclassified | 8 | signal_compatibility | 0 | 0 | 1 |
| 10769 | 190 | `refresh_ui` | unclassified | 8 | public_or_source_compatibility | 1 | 0 | 0 |
| 10960 | 78 | `_update_blink_refine_panel` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 11039 | 39 | `_update_blink_parent_context_combo` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 11079 | 51 | `open_general_settings` | dialog_settings | 2 | public_or_source_compatibility | 1 | 0 | 1 |
| 11131 | 129 | `open_stl_model_settings` | dialog_settings | 2 | public_or_source_compatibility | 2 | 0 | 0 |
| 11261 | 2 | `open_settings` | dialog_settings | 2 | public_or_source_compatibility | 1 | 0 | 0 |
| 11264 | 15 | `open_tif_model_settings` | dialog_settings | 2 | public_or_source_compatibility | 1 | 0 | 0 |
| 11280 | 13 | `change_language` | shell_start_agent | 3 | public_or_source_compatibility | 4 | 8 | 0 |
| 11294 | 22 | `change_theme` | shell_start_agent | 3 | public_or_source_compatibility | 1 | 0 | 0 |
| 11317 | 15 | `update_widget_themes` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 11333 | 66 | `update_button_themes` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 11399 | 4 | `add_images` | image_navigation | 5 | public_or_source_compatibility | 6 | 35 | 1 |
| 11404 | 94 | `_start_image_import` | shell_start_agent | 3 | test_compatibility | 0 | 1 | 0 |
| 11499 | 5 | `_set_image_import_controls_enabled` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11505 | 20 | `open_cropper` | project_lifecycle | 4 | signal_compatibility | 0 | 0 | 1 |
| 11526 | 8 | `_is_split_crop_image` | image_navigation | 5 | test_compatibility | 0 | 5 | 0 |
| 11535 | 15 | `_is_hard_joined_candidate_crop` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11551 | 17 | `_looks_like_panel_crop_path` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11569 | 26 | `_has_split_crops_from_image` | image_navigation | 5 | test_compatibility | 0 | 1 | 0 |
| 11596 | 10 | `_needs_manual_panel_split` | image_navigation | 5 | test_compatibility | 0 | 8 | 0 |
| 11607 | 8 | `_is_manual_panel_split_done` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11616 | 10 | `_set_panel_split_review` | image_navigation | 5 | test_compatibility | 0 | 6 | 0 |
| 11627 | 7 | `_clear_panel_split_review` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11635 | 8 | `_builtin_image_group_definitions` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11644 | 16 | `_custom_image_group_definitions` | image_navigation | 5 | test_compatibility | 0 | 1 | 0 |
| 11661 | 2 | `_all_image_group_definitions` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11664 | 19 | `_training_scope_group_definitions` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11684 | 24 | `_populate_training_scope_combo` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 11709 | 5 | `_refresh_training_scope_combo` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 11715 | 16 | `_selected_training_scope_payload` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 11732 | 13 | `_populate_vlm_image_group_combo` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 11746 | 5 | `_refresh_vlm_image_group_combo` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 11752 | 6 | `_image_group_display_name` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11759 | 2 | `_custom_image_group_ids` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11762 | 9 | `_image_group_move_target_definitions` | image_navigation | 5 | test_compatibility | 0 | 2 | 0 |
| 11772 | 45 | `_remove_empty_custom_image_groups` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11818 | 13 | `_safe_custom_image_group_id` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11832 | 34 | `create_custom_image_group` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11867 | 10 | `_set_image_manual_group` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11878 | 15 | `move_images_to_group` | image_navigation | 5 | signal_compatibility | 0 | 7 | 1 |
| 11894 | 10 | `clear_selected_custom_image_group` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11905 | 10 | `_short_progress_path` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 11916 | 13 | `_prepare_progress_dialog` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 11930 | 6 | `_candidate_panel_split_sources` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11937 | 131 | `batch_split_panel_images` | image_navigation | 5 | signal_compatibility | 0 | 2 | 1 |
| 12069 | 22 | `_save_detected_panel_crops` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 12092 | 10 | `_next_panel_crop_path` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 12103 | 32 | `_inherit_crop_provenance` | image_navigation | 5 | test_compatibility | 0 | 3 | 0 |
| 12136 | 9 | `_selected_image_paths` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 12146 | 8 | `_set_selected_panel_split_status` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 12155 | 2 | `mark_selected_manual_split_done` | unclassified | 8 | test_compatibility | 0 | 2 | 0 |
| 12158 | 2 | `mark_selected_manual_split_needed` | unclassified | 8 | test_compatibility | 0 | 1 | 0 |
| 12161 | 8 | `clear_selected_split_status` | unclassified | 8 | test_compatibility | 0 | 1 | 0 |
| 12170 | 23 | `show_file_list_context_menu` | shell_start_agent | 3 | signal_compatibility | 0 | 1 | 1 |
| 12194 | 7 | `_move_selected_images_to_new_group` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 12202 | 60 | `remove_selected_images` | image_navigation | 5 | test_compatibility | 0 | 4 | 0 |
| 12263 | 95 | `refresh_file_list` | image_navigation | 5 | public_or_source_compatibility | 1 | 41 | 0 |
| 12359 | 4 | `_image_has_review_content` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 12364 | 19 | `_set_image_list_item_status` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 12384 | 41 | `_refresh_current_image_list_status` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 12426 | 6 | `_refresh_image_list_status_or_rebuild` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 12433 | 7 | `_image_list_path_identity` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 12441 | 10 | `_visible_image_list_paths` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 12452 | 27 | `_replacement_image_after_removal` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 12480 | 61 | `_remove_visible_image_list_items` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 12542 | 10 | `_filtered_group_definitions_after_removal` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 12553 | 14 | `_refresh_visible_image_group_header_counts` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 12568 | 31 | `_select_first_visible_image_after_removal` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 12600 | 26 | `_build_image_list_state` | image_navigation | 5 | test_compatibility | 0 | 1 | 0 |
| 12627 | 12 | `_handle_image_list_item_clicked` | image_navigation | 5 | signal_compatibility | 0 | 2 | 1 |
| 12640 | 26 | `eventFilter` | unclassified | 8 | public_or_source_compatibility | 2 | 3 | 0 |
| 12667 | 35 | `_should_use_image_list_arrow_navigation` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 12703 | 21 | `_select_adjacent_image` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 12725 | 55 | `_collect_blink_roi_candidates` | blink | 6 | test_compatibility | 0 | 4 | 0 |
| 12781 | 39 | `on_file_selected` | unclassified | 8 | signal_compatibility | 0 | 0 | 1 |
| 12821 | 11 | `on_part_selected` | unclassified | 8 | public_or_source_compatibility | 2 | 0 | 1 |
| 12833 | 90 | `launch_blink_from_workbench` | blink | 6 | public_or_source_compatibility | 1 | 4 | 1 |
| 12924 | 8 | `on_genus_changed` | image_navigation | 5 | signal_compatibility | 0 | 0 | 1 |
| 12933 | 9 | `update_db_description` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 12943 | 5 | `_current_taxon_text` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 12949 | 8 | `_literature_source_taxon` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 12958 | 19 | `_set_current_image_taxon_from_literature` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 12978 | 21 | `_candidate_literature_db_paths` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 13000 | 55 | `_project_literature_db_paths` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 13056 | 39 | `_resolve_current_literature_context` | dialog_settings | 2 | test_compatibility | 0 | 3 | 0 |
| 13096 | 27 | `_resolve_literature_context_from_selected_db` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 13124 | 23 | `_choose_literature_db_for_current_taxon` | dialog_settings | 2 | test_compatibility | 0 | 1 | 0 |
| 13148 | 22 | `_literature_db_matches_image_source` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 13171 | 42 | `open_literature_description_dialog` | dialog_settings | 2 | signal_compatibility | 0 | 0 | 1 |
| 13214 | 22 | `_open_literature_description_dialog_with_context` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 13237 | 24 | `_apply_literature_description` | dialog_settings | 2 | test_compatibility | 0 | 1 | 0 |
| 13262 | 15 | `_ensure_workbench_description_visible` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 13278 | 2 | `on_enhancement_changed` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 13281 | 16 | `on_tool_changed` | annotation_sam | 6 | public_or_source_compatibility | 2 | 8 | 6 |
| 13298 | 23 | `on_blink_parent_context_changed` | blink | 6 | signal_compatibility | 0 | 2 | 1 |
| 13322 | 2 | `on_magic_wand_clicked` | annotation_sam | 6 | signal_compatibility | 0 | 0 | 1 |
| 13325 | 2 | `on_magic_box_completed` | annotation_sam | 6 | signal_compatibility | 0 | 1 | 1 |
| 13328 | 2 | `_sam_worker_ready` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 13331 | 2 | `_on_sam_model_loaded` | annotation_sam | 6 | signal_compatibility | 0 | 0 | 1 |
| 13334 | 18 | `_begin_sam_prompt` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 13353 | 6 | `_request_sam_point` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 13360 | 6 | `_request_sam_box` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 13367 | 34 | `on_annotation_box_completed` | annotation_sam | 6 | signal_compatibility | 0 | 3 | 1 |
| 13402 | 2 | `_warn_blink_context` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 13405 | 12 | `_active_child_blink_context` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 13418 | 43 | `run_blink_child_auto_annotate` | blink | 6 | signal_compatibility | 0 | 4 | 1 |
| 13462 | 9 | `_load_blink_refiner_class` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 13472 | 11 | `_active_blink_auto_shrink_steps` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 13484 | 14 | `_blink_parent_context_for_image` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 13499 | 41 | `_prepared_blink_auto_shrink_images` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 13541 | 38 | `_generate_blink_shrink_for_image` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 13580 | 42 | `run_blink_auto_shrink` | blink | 6 | signal_compatibility | 0 | 3 | 1 |
| 13623 | 90 | `run_blink_batch_auto_shrink` | blink | 6 | signal_compatibility | 0 | 1 | 1 |
| 13714 | 66 | `train_current_blink_expert` | blink | 6 | signal_compatibility | 0 | 3 | 1 |
| 13781 | 10 | `stop_current_blink_expert_training` | blink | 6 | signal_compatibility | 0 | 1 | 1 |
| 13792 | 18 | `open_current_route_expert_settings` | blink | 6 | signal_compatibility | 0 | 0 | 1 |
| 13811 | 10 | `on_sam_mask_generated` | annotation_sam | 6 | signal_compatibility | 0 | 0 | 1 |
| 13822 | 7 | `on_sam_prompt_failed` | annotation_sam | 6 | signal_compatibility | 0 | 0 | 1 |
| 13830 | 23 | `on_polygon_completed` | annotation_sam | 6 | signal_compatibility | 0 | 4 | 1 |
| 13854 | 7 | `toggle_morphometrics` | unclassified | 8 | signal_compatibility | 0 | 0 | 1 |
| 13862 | 9 | `on_scale_defined` | annotation_sam | 6 | signal_compatibility | 0 | 0 | 1 |
| 13872 | 16 | `update_measurements` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 13889 | 87 | `run_training` | training_model | 7 | public_or_source_compatibility | 1 | 2 | 1 |
| 13977 | 2 | `_external_backend_runner` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 13980 | 27 | `_sync_blink_lab_model_profile_defaults` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 14008 | 51 | `run_external_training` | training_model | 7 | test_compatibility | 0 | 1 | 0 |
| 14060 | 3 | `show_training_report` | dialog_settings | 2 | signal_compatibility | 0 | 0 | 1 |
| 14064 | 26 | `_candidate_training_experiment_dirs` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 14091 | 10 | `_resolve_report_artifact_path` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 14102 | 11 | `_training_report_time_label` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 14114 | 66 | `_training_report_payload_from_summary` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 14181 | 26 | `discover_training_reports` | dialog_settings | 2 | test_compatibility | 0 | 1 | 0 |
| 14208 | 8 | `open_training_report_payload` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 14217 | 17 | `open_training_results_browser` | project_lifecycle | 4 | signal_compatibility | 0 | 0 | 1 |
| 14235 | 37 | `_extract_prediction_payload` | vlm_prediction_export | 7 | public_or_source_compatibility | 2 | 0 | 0 |
| 14273 | 12 | `_is_unconfirmed_ai_draft` | vlm_prediction_export | 7 | public_or_source_compatibility | 2 | 0 | 0 |
| 14286 | 13 | `_auto_box_meta_for_part` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 14300 | 3 | `_auto_box_source_for_part` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 14304 | 3 | `_auto_box_review_status_for_part` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 14308 | 5 | `_auto_annotation_source_meta` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 14314 | 15 | `_can_replace_existing_auto_annotation` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 14330 | 33 | `_apply_prediction_to_project` | vlm_prediction_export | 7 | test_compatibility | 0 | 3 | 0 |
| 14364 | 5 | `_vlm_api_settings_path` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 14370 | 40 | `_vlm_api_config_from_pdf_widget` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 14411 | 8 | `_vlm_preannotation_artifacts_dir` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 14420 | 4 | `_current_vlm_target_parts` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 14425 | 4 | `_current_vlm_processing_scope` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 14430 | 3 | `_current_vlm_batch_scope` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 14434 | 4 | `_current_vlm_image_group` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 14439 | 8 | `_current_vlm_concurrency` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 14448 | 5 | `_current_vlm_prompt_profile` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 14454 | 2 | `_vlm_image_group_label` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 14457 | 57 | `_panel_crop_identity_index` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 14515 | 57 | `_project_image_groups` | project_lifecycle | 4 | test_compatibility | 0 | 8 | 0 |
| 14573 | 10 | `_vlm_candidate_source_meta` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 14584 | 19 | `_record_sqlite_vlm_image_result` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 14604 | 13 | `_finish_sqlite_vlm_run` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 14618 | 7 | `_vlm_image_paths_for_scope` | vlm_prediction_export | 7 | test_compatibility | 0 | 3 | 0 |
| 14626 | 2 | `_vlm_image_paths_from_settings` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 14629 | 11 | `_same_project_image_path` | project_lifecycle | 4 | test_compatibility | 0 | 1 | 0 |
| 14641 | 5 | `_project_image_key_for_path` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 14647 | 7 | `_vlm_part_list_text` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 14655 | 18 | `_vlm_part_coverage` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 14674 | 15 | `_log_vlm_part_coverage` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 14690 | 2 | `run_vlm_preannotation_current` | vlm_prediction_export | 7 | signal_compatibility | 0 | 0 | 1 |
| 14693 | 2 | `run_vlm_preannotation_batch` | vlm_prediction_export | 7 | signal_compatibility | 0 | 0 | 1 |
| 14696 | 121 | `run_vlm_preannotation_from_settings` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 14818 | 42 | `request_stop_vlm_preannotation` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 14861 | 11 | `_active_vlm_preannotation_threads` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 14873 | 14 | `_start_vlm_preannotation_workers` | runtime_worker | 1 | test_compatibility | 0 | 1 | 0 |
| 14888 | 53 | `_start_next_vlm_preannotation_image` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 14942 | 48 | `_apply_vlm_candidate` | vlm_prediction_export | 7 | test_compatibility | 0 | 5 | 0 |
| 14991 | 6 | `_refresh_vlm_canvas_if_current` | vlm_prediction_export | 7 | test_compatibility | 0 | 3 | 0 |
| 14998 | 34 | `_reload_current_image_for_workbench` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 15033 | 111 | `_on_vlm_preannotation_image_result` | vlm_prediction_export | 7 | signal_compatibility | 0 | 6 | 1 |
| 15145 | 7 | `_vlm_progress_image_key` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 15153 | 20 | `_mark_current_vlm_image_done` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 15174 | 30 | `_set_vlm_progress_ui` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 15205 | 54 | `_create_vlm_progress_dialog` | vlm_prediction_export | 7 | test_compatibility | 0 | 2 | 0 |
| 15260 | 18 | `_advance_vlm_progress` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 15279 | 11 | `_on_vlm_preannotation_thread_step` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 15291 | 7 | `_complete_current_vlm_image_steps` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 15299 | 100 | `_finish_vlm_preannotation_run` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 15400 | 36 | `accept_current_image_ai_drafts` | vlm_prediction_export | 7 | signal_compatibility | 0 | 3 | 1 |
| 15437 | 93 | `accept_batch_ai_drafts` | vlm_prediction_export | 7 | signal_compatibility | 0 | 1 | 1 |
| 15531 | 3 | `_on_vlm_preannotation_error` | vlm_prediction_export | 7 | signal_compatibility | 0 | 0 | 1 |
| 15535 | 33 | `_on_vlm_preannotation_qthread_finished` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 15569 | 2 | `_on_vlm_preannotation_finished` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 15572 | 46 | `run_prediction` | vlm_prediction_export | 7 | public_or_source_compatibility | 1 | 2 | 1 |
| 15619 | 30 | `run_external_prediction` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 15650 | 9 | `verify_current_image` | image_navigation | 5 | signal_compatibility | 0 | 1 | 1 |
| 15660 | 98 | `_start_external_batch_inference` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 15759 | 72 | `run_batch_inference` | runtime_worker | 1 | signal_compatibility | 0 | 1 | 1 |
| 15832 | 8 | `export_dataset` | runtime_worker | 1 | signal_compatibility | 0 | 0 | 1 |
| 15841 | 75 | `_start_dataset_export` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 15917 | 23 | `init_sam` | annotation_sam | 6 | test_compatibility | 0 | 1 | 0 |
| 15941 | 13 | `ensure_sam_preloaded` | annotation_sam | 6 | test_compatibility | 0 | 6 | 0 |
| 15955 | 4 | `ensure_2d_stl_models_preloaded` | training_model | 7 | test_compatibility | 0 | 3 | 0 |
| 15960 | 17 | `ensure_locator_preloaded` | training_model | 7 | test_compatibility | 0 | 1 | 0 |
| 15978 | 22 | `_preload_engine_parts_model_async` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 16001 | 2 | `log` | unclassified | 8 | public_or_source_compatibility | 174 | 33 | 5 |

## MainWindow State Fields

| Field | Assignments | Lines | Target owner | Stage |
| --- | --- | --- | --- | --- |
| `_image_list_state_cache` | 6 | 6622, 8605, 12429, 12392, 12256, 12274 | TBD | TBD |
| `_refreshing_part_tree` | 2 | 10494, 10553 | TBD | TBD |
| `_suppress_selection_save_flush` | 4 | 12589, 12576, 12596, 12583 | TBD | TBD |
| `_updating_blink_parent_context` | 2 | 11044, 11077 | TBD | TBD |
| `active_project_entry_path` | 8 | 6541, 7178, 9537, 9626, 9987, 9513, 9995, 10009 | TBD | TBD |
| `active_project_kind` | 13 | 6539, 7179, 7528, 8074, 8102, 8138, 8148, 9535, 9624, 9985, 9511, 9993, 10007 | TBD | TBD |
| `active_project_source_kind` | 7 | 6540, 9536, 9625, 9986, 9512, 9994, 10008 | TBD | TBD |
| `active_training_kind` | 3 | 6609, 14026, 9074 | TBD | TBD |
| `active_training_label` | 2 | 6610, 9076 | TBD | TBD |
| `agent_panel` | 1 | 7249 | TBD | TBD |
| `ai_action_panel` | 1 | 6968 | TBD | TBD |
| `ai_model_panel` | 1 | 6918 | TBD | TBD |
| `ai_panel` | 1 | 6895 | TBD | TBD |
| `blink_auto_shrink_steps` | 2 | 6551, 11180 | TBD | TBD |
| `blink_context_status_label` | 1 | 6835 | TBD | TBD |
| `blink_lab` | 1 | 7155 | TBD | TBD |
| `blink_refine_panel` | 1 | 7030 | TBD | TBD |
| `blink_train_batch` | 2 | 6547, 11176 | TBD | TBD |
| `blink_train_epochs` | 2 | 6546, 11176 | TBD | TBD |
| `blink_train_input_size` | 2 | 6550, 11179 | TBD | TBD |
| `blink_train_lr` | 2 | 6548, 11177 | TBD | TBD |
| `blink_train_weight_decay` | 2 | 6549, 11178 | TBD | TBD |
| `blink_training_strategy` | 2 | 6552, 11181 | TBD | TBD |
| `btn_accept_batch_ai_drafts` | 1 | 6988 | TBD | TBD |
| `btn_accept_current_ai_drafts` | 1 | 6984 | TBD | TBD |
| `btn_add` | 1 | 6722 | TBD | TBD |
| `btn_add_part` | 1 | 6841 | TBD | TBD |
| `btn_agent_from_workbench` | 1 | 6655 | TBD | TBD |
| `btn_batch` | 1 | 6979 | TBD | TBD |
| `btn_batch_split_panels` | 1 | 6645 | TBD | TBD |
| `btn_blink_auto_annotate` | 1 | 7064 | TBD | TBD |
| `btn_blink_auto_shrink` | 1 | 7071 | TBD | TBD |
| `btn_blink_batch_auto_shrink` | 1 | 7075 | TBD | TBD |
| `btn_blink_entry` | 1 | 6648 | TBD | TBD |
| `btn_blink_stop_training` | 1 | 7087 | TBD | TBD |
| `btn_blink_train_expert` | 1 | 7083 | TBD | TBD |
| `btn_clear_ai` | 1 | 7023 | TBD | TBD |
| `btn_configure_route_expert` | 1 | 7060 | TBD | TBD |
| `btn_continue_last` | 1 | 7372 | TBD | TBD |
| `btn_crop` | 1 | 6642 | TBD | TBD |
| `btn_del_locator` | 1 | 6935 | TBD | TBD |
| `btn_del_part` | 1 | 6847 | TBD | TBD |
| `btn_del_segmenter` | 1 | 6955 | TBD | TBD |
| `btn_export` | 1 | 6639 | TBD | TBD |
| `btn_general_settings` | 1 | 7378 | TBD | TBD |
| `btn_literature_descriptions` | 1 | 6879 | TBD | TBD |
| `btn_note_locator` | 1 | 6939 | TBD | TBD |
| `btn_note_segmenter` | 1 | 6959 | TBD | TBD |
| `btn_open_any` | 1 | 7375 | TBD | TBD |
| `btn_predict` | 1 | 6975 | TBD | TBD |
| `btn_rename_part` | 1 | 6844 | TBD | TBD |
| `btn_start_ant_code` | 1 | 7284 | TBD | TBD |
| `btn_start_center_from_workbench` | 1 | 6651 | TBD | TBD |
| `btn_start_console_toggle` | 1 | 7412 | TBD | TBD |
| `btn_stop_ant_code` | 1 | 7287 | TBD | TBD |
| `btn_stop_training` | 1 | 7017 | TBD | TBD |
| `btn_train` | 1 | 7013 | TBD | TBD |
| `btn_training_results` | 1 | 7108 | TBD | TBD |
| `btn_vlm_preannotate_batch` | 1 | 6663 | TBD | TBD |
| `btn_vlm_preannotate_current` | 1 | 6659 | TBD | TBD |
| `canvas` | 1 | 6775 | TBD | TBD |
| `canvas_shell` | 1 | 6782 | TBD | TBD |
| `check_lock_parent_box_ratio` | 1 | 7056 | TBD | TBD |
| `check_morpho` | 1 | 6855 | TBD | TBD |
| `child_training_cancel_requested` | 5 | 6608, 9116, 9127, 13744, 13786 | TBD | TBD |
| `child_training_failed` | 5 | 6607, 9105, 9112, 9126, 13743 | TBD | TBD |
| `chk_train_locator_only` | 1 | 6992 | TBD | TBD |
| `combo_blink_parent_context` | 1 | 7045 | TBD | TBD |
| `combo_locator` | 1 | 6929 | TBD | TBD |
| `combo_segmenter` | 1 | 6949 | TBD | TBD |
| `combo_training_scope` | 1 | 7006 | TBD | TBD |
| `config` | 1 | 6529 | TBD | TBD |
| `current_blink_context` | 2 | 6611, 10435 | TBD | TBD |
| `current_image` | 8 | 6571, 8612, 15004, 10088, 12804, 13487, 13490, 12253 | TBD | TBD |
| `current_lang` | 2 | 6530, 11281 | TBD | TBD |
| `current_theme` | 2 | 6531, 11296 | TBD | TBD |
| `dataset_export_thread` | 2 | 15866, 15909 | TBD | TBD |
| `db` | 1 | 6542 | TBD | TBD |
| `desc_box` | 1 | 6889 | TBD | TBD |
| `description_header_panel` | 1 | 6874 | TBD | TBD |
| `engine` | 1 | 6565 | TBD | TBD |
| `external_backend_config` | 2 | 6559, 11191 | TBD | TBD |
| `external_batch_inference_failed` | 3 | 6583, 15670, 15727 | TBD | TBD |
| `external_batch_inference_progress_dialog` | 3 | 6582, 15690, 15741 | TBD | TBD |
| `external_batch_inference_saved_any` | 3 | 6584, 15671, 15723 | TBD | TBD |
| `external_batch_inference_thread` | 3 | 6581, 15700, 15743 | TBD | TBD |
| `external_training_failed` | 3 | 6586, 14025, 14039 | TBD | TBD |
| `external_training_thread` | 3 | 6585, 14031, 14048 | TBD | TBD |
| `file_list` | 1 | 6713 | TBD | TBD |
| `genus_combo` | 1 | 6820 | TBD | TBD |
| `group_morpho` | 1 | 6858 | TBD | TBD |
| `image_import_progress_dialog` | 3 | 6580, 11443, 11486 | TBD | TBD |
| `image_import_thread` | 3 | 6579, 11446, 11490 | TBD | TBD |
| `image_list_group_collapsed` | 1 | 6617 | TBD | TBD |
| `image_taxon_panel` | 1 | 6866 | TBD | TBD |
| `inf_adapt` | 2 | 6561, 11185 | TBD | TBD |
| `inf_conf` | 2 | 6560, 11185 | TBD | TBD |
| `inf_noise_floor` | 2 | 6563, 11186 | TBD | TBD |
| `inf_pad` | 2 | 6562, 11186 | TBD | TBD |
| `inf_poly_epsilon` | 2 | 6564, 11187 | TBD | TBD |
| `inf_thread` | 2 | 6572, 15795 | TBD | TBD |
| `label_ai_workflow` | 1 | 6900 | TBD | TBD |
| `label_blink_expert` | 1 | 7052 | TBD | TBD |
| `label_blink_parent_box` | 1 | 7048 | TBD | TBD |
| `label_blink_parent_context` | 1 | 7042 | TBD | TBD |
| `label_blink_refine` | 1 | 7035 | TBD | TBD |
| `label_blink_route` | 1 | 7038 | TBD | TBD |
| `label_description` | 1 | 6884 | TBD | TBD |
| `label_logs` | 1 | 7131 | TBD | TBD |
| `label_measurements` | 1 | 6862 | TBD | TBD |
| `label_model_backend` | 1 | 6904 | TBD | TBD |
| `label_parent_annotation` | 1 | 6913 | TBD | TBD |
| `label_project_images` | 1 | 6710 | TBD | TBD |
| `label_structures` | 1 | 6824 | TBD | TBD |
| `label_taxonomy` | 1 | 6818 | TBD | TBD |
| `label_training_progress` | 1 | 7103 | TBD | TBD |
| `label_training_progress_status` | 1 | 7114 | TBD | TBD |
| `last_confirmed_locator_timestamp` | 4 | 6602, 9013, 9397, 9390 | TBD | TBD |
| `lbl_locator` | 1 | 6927 | TBD | TBD |
| `lbl_segmenter` | 1 | 6947 | TBD | TBD |
| `lbl_training_scope` | 1 | 7003 | TBD | TBD |
| `locator_preload_thread` | 1 | 6588 | TBD | TBD |
| `log_console` | 1 | 7134 | TBD | TBD |
| `logs_panel` | 1 | 7126 | TBD | TBD |
| `metadata_panel` | 1 | 6813 | TBD | TBD |
| `model_backend` | 2 | 6558, 11190 | TBD | TBD |
| `parent_annotation_panel` | 1 | 6908 | TBD | TBD |
| `parent_box_aspect_ratios` | 3 | 6623, 10376, 11206 | TBD | TBD |
| `parent_training_cancel_requested` | 3 | 6606, 9177, 9289 | TBD | TBD |
| `parent_training_failed` | 4 | 6605, 9176, 9250, 9267 | TBD | TBD |
| `part_list` | 1 | 6827 | TBD | TBD |
| `parts_model_preload_thread` | 2 | 6589, 15993 | TBD | TBD |
| `pdf_widget` | 1 | 7149 | TBD | TBD |
| `pending_sam_description` | 4 | 6578, 13350, 13818, 13826 | TBD | TBD |
| `pending_sam_image` | 4 | 6577, 13349, 13817, 13825 | TBD | TBD |
| `pending_sam_part` | 4 | 6576, 13348, 13816, 13824 | TBD | TBD |
| `pending_training_preflight` | 2 | 6603, 9164 | TBD | TBD |
| `progress` | 1 | 7119 | TBD | TBD |
| `project` | 1 | 6535 | TBD | TBD |
| `project_autosave_delay_ms` | 2 | 6594, 11098 | TBD | TBD |
| `project_last_image_switch_at` | 2 | 6596, 8348 | TBD | TBD |
| `project_save_context` | 4 | 6598, 8403, 8342, 8357 | TBD | TBD |
| `project_save_navigation_idle_ms` | 1 | 6595 | TBD | TBD |
| `project_save_pending` | 4 | 6597, 8340, 8402, 8356 | TBD | TBD |
| `project_save_timer` | 1 | 6599 | TBD | TBD |
| `radio_annotation_box` | 1 | 6756 | TBD | TBD |
| `radio_box` | 1 | 6751 | TBD | TBD |
| `radio_draw` | 1 | 6740 | TBD | TBD |
| `radio_loose_shrink_box` | 1 | 6761 | TBD | TBD |
| `radio_magic` | 1 | 6746 | TBD | TBD |
| `radio_scale` | 1 | 6766 | TBD | TBD |
| `route_settings_panel` | 1 | 7172 | TBD | TBD |
| `runtime_device` | 3 | 6557, 11103, 11189 | TBD | TBD |
| `sam_busy` | 4 | 6575, 13347, 13815, 13823 | TBD | TBD |
| `sam_thread` | 2 | 6573, 15924 | TBD | TBD |
| `sam_worker` | 2 | 6574, 15926 | TBD | TBD |
| `shortcut_redo` | 1 | 6793 | TBD | TBD |
| `shortcut_save` | 1 | 6795 | TBD | TBD |
| `shortcut_undo` | 1 | 6791 | TBD | TBD |
| `shortcut_verify` | 1 | 6797 | TBD | TBD |
| `start_agent_status_label` | 1 | 7276 | TBD | TBD |
| `start_center_widget` | 1 | 6631 | TBD | TBD |
| `start_console_agent_label` | 1 | 7449 | TBD | TBD |
| `start_console_agent_value` | 1 | 7449 | TBD | TBD |
| `start_console_body` | 1 | 7419 | TBD | TBD |
| `start_console_expanded` | 2 | 7460, 7465 | TBD | TBD |
| `start_console_images_label` | 1 | 7436 | TBD | TBD |
| `start_console_images_value` | 1 | 7436 | TBD | TBD |
| `start_console_panel` | 1 | 7319 | TBD | TBD |
| `start_console_pdf_label` | 1 | 7446 | TBD | TBD |
| `start_console_pdf_value` | 1 | 7446 | TBD | TBD |
| `start_console_project_label` | 1 | 7433 | TBD | TBD |
| `start_console_project_value` | 1 | 7433 | TBD | TBD |
| `start_console_stl_note` | 1 | 7455 | TBD | TBD |
| `start_console_summary` | 1 | 7401 | TBD | TBD |
| `start_console_tif_label` | 2 | 7440, 7444 | TBD | TBD |
| `start_console_tif_value` | 2 | 7440, 7445 | TBD | TBD |
| `start_console_title` | 1 | 7399 | TBD | TBD |
| `start_console_workflow_label` | 1 | 7430 | TBD | TBD |
| `start_console_workflow_value` | 1 | 7430 | TBD | TBD |
| `start_image_card` | 1 | 7323 | TBD | TBD |
| `start_pdf_card` | 1 | 7343 | TBD | TBD |
| `start_quick_panel` | 1 | 7321 | TBD | TBD |
| `start_recent_label` | 1 | 7368 | TBD | TBD |
| `start_subtitle` | 1 | 7264 | TBD | TBD |
| `start_tif_card` | 2 | 7332, 7334 | TBD | TBD |
| `start_title` | 1 | 7262 | TBD | TBD |
| `startup_size` | 1 | 6527 | TBD | TBD |
| `stl_project` | 1 | 6538 | TBD | TBD |
| `tabs` | 1 | 6629 | TBD | TBD |
| `tif_project` | 1 | 6537 | TBD | TBD |
| `tif_workbench` | 1 | 7152 | TBD | TBD |
| `tif_workflow_enabled` | 1 | 6534 | TBD | TBD |
| `tool_group` | 1 | 6739 | TBD | TBD |
| `tool_strip` | 1 | 6734 | TBD | TBD |
| `toolbar_flow_panel` | 1 | 6683 | TBD | TBD |
| `toolbar_project_panel` | 1 | 6674 | TBD | TBD |
| `train_batch` | 2 | 6545, 11175 | TBD | TBD |
| `train_epochs` | 2 | 6544, 11175 | TBD | TBD |
| `train_lr` | 2 | 6555, 11184 | TBD | TBD |
| `train_wd` | 2 | 6556, 11184 | TBD | TBD |
| `trainer` | 3 | 6587, 9182, 9241 | TBD | TBD |
| `training_progress_panel` | 1 | 7095 | TBD | TBD |
| `training_retry_requested` | 4 | 6604, 9175, 9249, 9258 | TBD | TBD |
| `vlm_preannotation_active_images` | 3 | 14796, 15396, 14923 | TBD | TBD |
| `vlm_preannotation_api_config` | 2 | 14777, 14801 | TBD | TBD |
| `vlm_preannotation_artifacts_dir` | 1 | 14800 | TBD | TBD |
| `vlm_preannotation_cancel_requested` | 4 | 6615, 14788, 14838, 15392 | TBD | TBD |
| `vlm_preannotation_cancelled_queued_images` | 4 | 6616, 14789, 14839, 15393 | TBD | TBD |
| `vlm_preannotation_completed_image_keys` | 3 | 14798, 15162, 15398 | TBD | TBD |
| `vlm_preannotation_completed_images` | 2 | 14794, 15164 | TBD | TBD |
| `vlm_preannotation_completed_steps` | 2 | 14792, 15263 | TBD | TBD |
| `vlm_preannotation_concurrency` | 1 | 14790 | TBD | TBD |
| `vlm_preannotation_current_image` | 4 | 14795, 14897, 15169, 15265 | TBD | TBD |
| `vlm_preannotation_current_image_steps_completed` | 3 | 14896, 15272, 15275 | TBD | TBD |
| `vlm_preannotation_image_step_counts` | 4 | 14797, 15397, 14927, 15270 | TBD | TBD |
| `vlm_preannotation_progress_bar` | 2 | 15256, 15390 | TBD | TBD |
| `vlm_preannotation_progress_dialog` | 3 | 6614, 15251, 15385 | TBD | TBD |
| `vlm_preannotation_progress_label` | 2 | 15254, 15388 | TBD | TBD |
| `vlm_preannotation_progress_notice_label` | 2 | 15253, 15387 | TBD | TBD |
| `vlm_preannotation_progress_path_label` | 2 | 15255, 15389 | TBD | TBD |
| `vlm_preannotation_progress_title_label` | 2 | 15252, 15386 | TBD | TBD |
| `vlm_preannotation_prompt_profile` | 1 | 14802 | TBD | TBD |
| `vlm_preannotation_queue` | 4 | 14785, 14840, 14895, 15559 | TBD | TBD |
| `vlm_preannotation_records` | 1 | 14784 | TBD | TBD |
| `vlm_preannotation_run_active` | 2 | 14787, 15359 | TBD | TBD |
| `vlm_preannotation_run_id` | 1 | 14783 | TBD | TBD |
| `vlm_preannotation_saved_total` | 2 | 14782, 15093 | TBD | TBD |
| `vlm_preannotation_stop_button` | 2 | 15257, 15391 | TBD | TBD |
| `vlm_preannotation_target_parts` | 1 | 14799 | TBD | TBD |
| `vlm_preannotation_thread` | 5 | 6612, 14870, 14886, 14919, 15395 | TBD | TBD |
| `vlm_preannotation_threads` | 6 | 6613, 14786, 14869, 14885, 15394, 15544 | TBD | TBD |
| `vlm_preannotation_total_images` | 1 | 14793 | TBD | TBD |
| `vlm_preannotation_total_steps` | 1 | 14791 | TBD | TBD |
| `workbench_inspector_scroll` | 1 | 6800 | TBD | TBD |
| `workbench_splitter` | 1 | 6699 | TBD | TBD |
| `workbench_top_bar` | 1 | 6668 | TBD | TBD |
| `workbench_widget` | 1 | 6633 | TBD | TBD |

## Main Import Compatibility

| File | Line | Import |
| --- | --- | --- |
| scripts/benchmark_main_window_workflows.py | 198 | `import AntSleap.main as main_module` |
| tests/test_blink_bridge.py | 22 | `import main as main_module` |
| tests/test_blink_bridge.py | 23 | `from main import BlinkEntryDialog, MainWindow` |
| tests/test_gui_smoke.py | 45 | `import AntSleap.main as main_module` |
| tests/test_reporting_routes.py | 45 | `from AntSleap.main import TrainingReportDialog` |
| tests/test_tif_backend.py | 558 | `"from AntSleap.tools.tif_trainer_backend import main",` |
| tests/test_tif_backend.py | 599 | `"from AntSleap.tools.tif_trainer_backend import main",` |
| tests/test_tif_backend.py | 645 | `"from AntSleap.tools.tif_trainer_backend import main",` |
| tests/test_tif_backend.py | 684 | `"from AntSleap.tools.tif_trainer_backend import main",` |
| tests/test_tif_backend.py | 742 | `"from AntSleap.tools.tif_trainer_backend import main",` |
| tests/test_tif_nnunet_v2_backend.py | 33 | `"from AntSleap.tools.tif_nnunet_v2_backend import main",` |
| tests/test_ui_localization.py | 19 | `import AntSleap.main as main_module` |
| tests/test_ui_localization.py | 20 | `from AntSleap.main import ExportDialog, BlinkEntryDialog, ModelSettingsDialog, RouteManagementPanel, TrainingPreflightDialog, TrainingReportDialog` |
| tests/test_ui_polish_scope.py | 44 | `import AntSleap.main as main_module` |

## Key Test Dependencies

| File | Line | Reference | Private refs | Migration target |
| --- | --- | --- | --- | --- |
| tests/test_blink_bridge.py | 23 | `from main import BlinkEntryDialog, MainWindow` | - | TBD |
| tests/test_blink_bridge.py | 434 | `preferred_roi_parts = main_module._blink_preferred_roi_parts(` | - | TBD |
| tests/test_blink_bridge.py | 438 | `roi_candidates = MainWindow._collect_blink_roi_candidates(` | `_collect_blink_roi_candidates` | TBD |
| tests/test_blink_bridge.py | 524 | `fake_window._current_part_name = lambda: "Mandible"` | `_current_part_name` | TBD |
| tests/test_blink_bridge.py | 525 | `fake_window._collect_blink_roi_candidates = lambda image_path, selected_part, preferred_roi_parts=None: MainWindow._collect_blink_roi_candidates(` | `_collect_blink_roi_candidates` | TBD |
| tests/test_blink_bridge.py | 533 | `MainWindow.launch_blink_from_workbench(fake_window)` | - | TBD |
| tests/test_blink_bridge.py | 591 | `fake_window._current_part_name = lambda: "Mandible"` | `_current_part_name` | TBD |
| tests/test_blink_bridge.py | 592 | `fake_window._collect_blink_roi_candidates = lambda image_path, selected_part, preferred_roi_parts=None: MainWindow._collect_blink_roi_candidates(` | `_collect_blink_roi_candidates` | TBD |
| tests/test_blink_bridge.py | 598 | `fake_window._auto_boxes_for_canvas = lambda image_path: self.pm.split_auto_boxes_by_source(image_path)` | `_auto_boxes_for_canvas` | TBD |
| tests/test_blink_bridge.py | 601 | `MainWindow.launch_blink_from_workbench(fake_window)` | - | TBD |
| tests/test_blink_bridge.py | 652 | `fake_window._current_part_name = lambda: "Mandible"` | `_current_part_name` | TBD |
| tests/test_blink_bridge.py | 653 | `fake_window._collect_blink_roi_candidates = lambda image_path, selected_part, preferred_roi_parts=None: MainWindow._collect_blink_roi_candidates(` | `_collect_blink_roi_candidates` | TBD |
| tests/test_blink_bridge.py | 661 | `MainWindow.launch_blink_from_workbench(fake_window)` | - | TBD |
| tests/test_gui_smoke.py | 235 | `patch.object(main_module.MainWindow, "_default_outputs_root", lambda _window: str(self.project_dir / "TaxaMask_outputs")), \` | - | TBD |
| tests/test_gui_smoke.py | 241 | `patch.object(main_module.QTimer, "singleShot", lambda *args, **kwargs: None):` | - | TBD |
| tests/test_gui_smoke.py | 242 | `window = main_module.MainWindow()` | - | TBD |
| tests/test_gui_smoke.py | 243 | `window._default_outputs_root = lambda: str(self.project_dir / "TaxaMask_outputs")` | `_default_outputs_root` | TBD |
| tests/test_gui_smoke.py | 341 | `self.assertIsNotNone(window.findChild(main_module.QWidget, "start2DWorkflowCard"))` | - | TBD |
| tests/test_gui_smoke.py | 342 | `self.assertIsNone(window.findChild(main_module.QWidget, "start" + "T" + "if" + "WorkflowCard"))` | - | TBD |
| tests/test_gui_smoke.py | 343 | `self.assertIsNotNone(window.findChild(main_module.QWidget, "startProjectConsole"))` | - | TBD |
| tests/test_gui_smoke.py | 348 | `rail_scroll = window.findChild(main_module.QScrollArea, "startWorkflowRailScroll")` | - | TBD |
| tests/test_gui_smoke.py | 353 | `self.assertEqual(rail_scroll.horizontalScrollBarPolicy(), main_module.Qt.ScrollBarAlwaysOff)` | - | TBD |
| tests/test_gui_smoke.py | 354 | `self.assertEqual(rail_scroll.verticalScrollBarPolicy(), main_module.Qt.ScrollBarAsNeeded)` | - | TBD |
| tests/test_gui_smoke.py | 355 | `self.assertIsNotNone(window.findChild(main_module.QWidget, "taxamaskAgentPanel"))` | - | TBD |
| tests/test_gui_smoke.py | 366 | `self.assertIsNone(window.agent_panel.findChild(main_module.QWidget, "taxamaskAgentInlineStatus"))` | - | TBD |
| tests/test_gui_smoke.py | 367 | `self.assertIsNone(window.agent_panel.findChild(main_module.QWidget, "taxamaskStartAntCodeButton"))` | - | TBD |
| tests/test_gui_smoke.py | 421 | `self.assertIsNotNone(window.findChild(main_module.QWidget, "workbenchCanvasShell"))` | - | TBD |
| tests/test_gui_smoke.py | 422 | `self.assertIsNotNone(window.findChild(main_module.QWidget, "workbenchLiteratureDescriptionButton"))` | - | TBD |
| tests/test_gui_smoke.py | 428 | `window._show_start_center()` | `_show_start_center` | TBD |
| tests/test_gui_smoke.py | 434 | `self.assertIsNone(window.findChild(main_module.QWidget, "start" + "T" + "if" + "WorkflowCard"))` | - | TBD |
| tests/test_gui_smoke.py | 454 | `window._update_start_center_texts()` | `_update_start_center_texts` | TBD |
| tests/test_gui_smoke.py | 469 | `self.assertTrue(main_module.MainWindow.ensure_2d_stl_models_preloaded(window))` | - | TBD |
| tests/test_gui_smoke.py | 470 | `self.assertFalse(main_module.MainWindow.ensure_2d_stl_models_preloaded(window))` | - | TBD |
| tests/test_gui_smoke.py | 480 | `window._show_start_center()` | `_show_start_center` | TBD |
| tests/test_gui_smoke.py | 511 | `self.assertIsNotNone(window.agent_panel.findChild(main_module.QWidget, "taxamaskAgentStack"))` | - | TBD |
| tests/test_gui_smoke.py | 520 | `panel = main_module.TaxaMaskAgentPanel(` | - | TBD |
| tests/test_gui_smoke.py | 538 | `panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=str(PROJECT_ROOT))` | - | TBD |
| tests/test_gui_smoke.py | 542 | `self.assertIsNotNone(panel.findChild(main_module.QWidget, "taxamaskAgentStack"))` | - | TBD |
| tests/test_gui_smoke.py | 550 | `panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=str(PROJECT_ROOT))` | - | TBD |
| tests/test_gui_smoke.py | 569 | `class FakeWebView(main_module.QWidget):` | - | TBD |
| tests/test_gui_smoke.py | 621 | `panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=str(PROJECT_ROOT))` | - | TBD |
| tests/test_gui_smoke.py | 642 | `panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=r"D:\lab data\TaxaMask")` | - | TBD |
| tests/test_gui_smoke.py | 658 | `panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=str(PROJECT_ROOT))` | - | TBD |
| tests/test_gui_smoke.py | 667 | `panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=str(PROJECT_ROOT))` | - | TBD |
| tests/test_gui_smoke.py | 682 | `panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=str(PROJECT_ROOT))` | - | TBD |
| tests/test_gui_smoke.py | 909 | `with patch.object(main_module.QTimer, "singleShot", lambda _ms, callback: callback()):` | - | TBD |
| tests/test_gui_smoke.py | 930 | `fake_web_view = main_module.QWidget()` | - | TBD |
| tests/test_gui_smoke.py | 952 | `fake_web_view = main_module.QWidget()` | - | TBD |
| tests/test_gui_smoke.py | 1079 | `window.open_agent_from_context(window._collect_image_workbench_agent_context())` | `_collect_image_workbench_agent_context` | TBD |
| tests/test_gui_smoke.py | 1087 | `self.assertIn("MainWindow._collect_image_workbench_agent_context", context["source_code_refs"])` | `_collect_image_workbench_agent_context` | TBD |
| tests/test_gui_smoke.py | 1139 | `dialog = main_module.ModelSettingsDialog(` | - | TBD |
| tests/test_gui_smoke.py | 1159 | `self.assertIsNotNone(dialog.findChild(main_module.QPushButton, "modelSettingsAskAgentButton"))` | - | TBD |
| tests/test_gui_smoke.py | 1161 | `runtime_group = dialog.findChild(main_module.QWidget, "modelSettingsRuntimeDevicePanel")` | - | TBD |
| tests/test_gui_smoke.py | 1163 | `device_combo = runtime_group.findChild(main_module.QComboBox)` | - | TBD |
| tests/test_gui_smoke.py | 1177 | `dialog = main_module.ModelSettingsDialog(` | - | TBD |
| tests/test_gui_smoke.py | 1210 | `vlm_panel = dialog.findChild(main_module.QWidget, "modelSettingsVlmPreannotationPanel")` | - | TBD |
| tests/test_gui_smoke.py | 1216 | `scope_combo = dialog.findChild(main_module.QComboBox, "modelSettingsVlmBatchScopeCombo")` | - | TBD |
| tests/test_gui_smoke.py | 1220 | `group_combo = dialog.findChild(main_module.QComboBox, "modelSettingsVlmImageGroupCombo")` | - | TBD |
| tests/test_gui_smoke.py | 1223 | `profile_combo = dialog.findChild(main_module.QComboBox, "modelSettingsVlmPromptProfileCombo")` | - | TBD |
| tests/test_gui_smoke.py | 1234 | `dialog = main_module.ModelSettingsDialog(` | - | TBD |
| tests/test_gui_smoke.py | 1260 | `combo = dialog.findChild(main_module.QComboBox, "modelSettingsVlmImageGroupCombo")` | - | TBD |
| tests/test_gui_smoke.py | 1270 | `dialog = main_module.ModelSettingsDialog(` | - | TBD |
| tests/test_gui_smoke.py | 1323 | `dialog = main_module.GeneralSettingsDialog(` | - | TBD |
| tests/test_gui_smoke.py | 1340 | `self.assertIsNotNone(dialog.findChild(main_module.QPushButton, "generalSettingsAskAgentButton"))` | - | TBD |
| tests/test_gui_smoke.py | 1345 | `self.assertIsNone(dialog.findChild(main_module.QWidget, "modelSettingsLocatorScopePanel"))` | - | TBD |
| tests/test_gui_smoke.py | 1352 | `model_dialog = main_module.ModelSettingsDialog(` | - | TBD |
| tests/test_gui_smoke.py | 1364 | `"model_backend": main_module.EXTERNAL_BACKEND_ID,` | - | TBD |
| tests/test_gui_smoke.py | 1382 | `model_dialog.child_backend_combo.findData(main_module.CHILD_BACKEND_EXTERNAL)` | - | TBD |
| tests/test_gui_smoke.py | 1400 | `"expert_backend": main_module.ROUTE_BACKEND_HEATMAP_BLINK,` | - | TBD |
| tests/test_gui_smoke.py | 1411 | `self.assertEqual(context["parent_model_source"], main_module.PARENT_BACKEND_EXTERNAL)` | - | TBD |
| tests/test_gui_smoke.py | 1412 | `self.assertEqual(context["default_child_expert"], main_module.CHILD_BACKEND_EXTERNAL)` | - | TBD |
| tests/test_gui_smoke.py | 1413 | `self.assertEqual(context["default_child_route_backend"], main_module.ROUTE_BACKEND_EXTERNAL_BLINK)` | - | TBD |
| tests/test_gui_smoke.py | 1426 | `compact = window._compact_agent_context(context)` | `_compact_agent_context` | TBD |
| tests/test_gui_smoke.py | 1430 | `self.assertEqual(compact["default_child_expert"], main_module.CHILD_BACKEND_EXTERNAL)` | - | TBD |
| tests/test_gui_smoke.py | 1450 | `tif_compact = window._compact_agent_context(` | `_compact_agent_context` | TBD |
| tests/test_gui_smoke.py | 1538 | `pdf_compact = window._compact_agent_context(` | `_compact_agent_context` | TBD |
| tests/test_gui_smoke.py | 1588 | `with patch.object(main_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1612 | `with patch.object(main_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1632 | `with patch.object(main_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1661 | `with patch.object(main_module.QMessageBox, "information", return_value=main_module.QMessageBox.Ok):` | - | TBD |
| tests/test_gui_smoke.py | 1668 | `with patch.object(main_module.QFileDialog, "getSaveFileName", return_value=(str(export_path), "JSON (*.json)")), \` | - | TBD |
| tests/test_gui_smoke.py | 1669 | `patch.object(main_module.QMessageBox, "information", return_value=main_module.QMessageBox.Ok):` | - | TBD |
| tests/test_gui_smoke.py | 1686 | `with patch.object(main_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1713 | `with patch.object(main_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1736 | `with patch.object(main_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1780 | `with patch.object(main_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1789 | `self.assertEqual(header.data(main_module.Qt.UserRole + 1), "original")` | - | TBD |
| tests/test_gui_smoke.py | 1816 | `with patch.object(main_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1839 | `with patch.object(main_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1863 | `with patch.object(main_module.QFileDialog, "getExistingDirectory", fake_get_existing_directory), \` | - | TBD |
| tests/test_gui_smoke.py | 1864 | `patch.object(main_module.QInputDialog, "getText", return_value=("review", True)), \` | - | TBD |
| tests/test_gui_smoke.py | 1881 | `ant_project_dir = Path(main_module.PACKAGE_DIR)` | - | TBD |
| tests/test_gui_smoke.py | 1883 | `self.assertEqual(Path(window._default_open_project_dir()), self.project_dir / "TaxaMask_outputs")` | `_default_open_project_dir` | TBD |
| tests/test_gui_smoke.py | 1887 | `self.assertEqual(Path(window._default_2d_export_dir()), project_dir / "exports")` | `_default_2d_export_dir` | TBD |
| tests/test_gui_smoke.py | 1888 | `self.assertEqual(Path(window._vlm_preannotation_artifacts_dir()), project_dir / "vlm_preannotation")` | `_vlm_preannotation_artifacts_dir` | TBD |
| tests/test_gui_smoke.py | 1890 | `dialog = main_module.ExportDialog(window, "en", default_dir=window._default_2d_export_dir())` | `_default_2d_export_dir` | TBD |
| tests/test_gui_smoke.py | 1908 | `window._create_vlm_progress_dialog()` | `_create_vlm_progress_dialog` | TBD |
| tests/test_gui_smoke.py | 1910 | `window._advance_vlm_progress("prepare")` | `_advance_vlm_progress` | TBD |
| tests/test_gui_smoke.py | 1914 | `self.assertEqual(progress.windowModality(), main_module.Qt.NonModal)` | - | TBD |
| tests/test_gui_smoke.py | 1928 | `window._mark_current_vlm_image_done("done")` | `_mark_current_vlm_image_done` | TBD |
| tests/test_gui_smoke.py | 1960 | `original_refresh = window._refresh_vlm_canvas_if_current` | `_refresh_vlm_canvas_if_current` | TBD |
| tests/test_gui_smoke.py | 1961 | `window._refresh_vlm_canvas_if_current = lambda path: (refresh_calls.append(path), original_refresh(path))` | `_refresh_vlm_canvas_if_current` | TBD |
| tests/test_gui_smoke.py | 1964 | `window._on_vlm_preannotation_image_result(` | `_on_vlm_preannotation_image_result` | TBD |
| tests/test_gui_smoke.py | 2019 | `window._on_vlm_preannotation_image_result(` | `_on_vlm_preannotation_image_result` | TBD |
| tests/test_gui_smoke.py | 2063 | `window._on_vlm_preannotation_image_result(` | `_on_vlm_preannotation_image_result` | TBD |
| tests/test_gui_smoke.py | 2103 | `window._create_vlm_progress_dialog()` | `_create_vlm_progress_dialog` | TBD |
| tests/test_gui_smoke.py | 2111 | `window._on_vlm_preannotation_image_result(` | `_on_vlm_preannotation_image_result` | TBD |
| tests/test_gui_smoke.py | 2162 | `window._set_panel_split_review(str(manual_image), "manual_required", reason="hard_seam_panel_split")` | `_set_panel_split_review` | TBD |
| tests/test_gui_smoke.py | 2173 | `batch_paths = window._vlm_image_paths_for_scope(window._current_vlm_batch_scope())` | `_current_vlm_batch_scope`, `_vlm_image_paths_for_scope` | TBD |
| tests/test_gui_smoke.py | 2176 | `current_paths = window._vlm_image_paths_for_scope("current_image")` | `_vlm_image_paths_for_scope` | TBD |
| tests/test_gui_smoke.py | 2181 | `groups = window._project_image_groups()` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 2219 | `window._on_vlm_preannotation_image_result(` | `_on_vlm_preannotation_image_result` | TBD |
| tests/test_gui_smoke.py | 2262 | `window._refresh_vlm_canvas_if_current(image_key)` | `_refresh_vlm_canvas_if_current` | TBD |
| tests/test_gui_smoke.py | 2289 | `ok, mode = window._apply_vlm_candidate(` | `_apply_vlm_candidate` | TBD |
| tests/test_gui_smoke.py | 2345 | `ok, mode = window._apply_vlm_candidate(` | `_apply_vlm_candidate` | TBD |
| tests/test_gui_smoke.py | 2379 | `window._same_project_image_path(` | `_same_project_image_path` | TBD |
| tests/test_gui_smoke.py | 2380 | `window.file_list.currentItem().data(main_module.Qt.UserRole),` | - | TBD |
| tests/test_gui_smoke.py | 2394 | `for index in range(main_module.BACKGROUND_IMAGE_IMPORT_THRESHOLD):` | - | TBD |
| tests/test_gui_smoke.py | 2427 | `started = window._start_image_import(image_paths)` | `_start_image_import` | TBD |
| tests/test_gui_smoke.py | 2453 | `window.model_backend = main_module.EXTERNAL_BACKEND_ID` | - | TBD |
| tests/test_gui_smoke.py | 2505 | `with patch.object(main_module, "_runtime_parent_backend", lambda *_args, **_kwargs: main_module.EXTERNAL_BACKEND_ID), \` | - | TBD |
| tests/test_gui_smoke.py | 2506 | `patch.object(main_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes), \` | - | TBD |
| tests/test_gui_smoke.py | 2540 | `path = item.data(main_module.Qt.UserRole)` | - | TBD |
| tests/test_gui_smoke.py | 2553 | `with patch.object(main_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 2702 | `prompt = window._pdf_agent_prompt()` | `_pdf_agent_prompt` | TBD |
| tests/test_gui_smoke.py | 2855 | `window._inherit_crop_provenance(` | `_inherit_crop_provenance` | TBD |
| tests/test_gui_smoke.py | 2872 | `self.assertTrue(window._is_pdf_candidate_provenance(crop_provenance))` | `_is_pdf_candidate_provenance` | TBD |
| tests/test_gui_smoke.py | 2889 | `window._inherit_crop_provenance(` | `_inherit_crop_provenance` | TBD |
| tests/test_gui_smoke.py | 2906 | `self.assertTrue(window._is_split_crop_image(str(crop_image)))` | `_is_split_crop_image` | TBD |
| tests/test_gui_smoke.py | 2918 | `window._set_panel_split_review(str(parent_image), "manual_required", reason="hard_seam_panel_split")` | `_set_panel_split_review` | TBD |
| tests/test_gui_smoke.py | 2920 | `window._inherit_crop_provenance(` | `_inherit_crop_provenance` | TBD |
| tests/test_gui_smoke.py | 2937 | `self.assertFalse(window._needs_manual_panel_split(str(parent_image)))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 2938 | `self.assertFalse(window._needs_manual_panel_split(str(crop_image)))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 2963 | `window._set_panel_split_review(str(parent_image), "manual_required", reason="hard_seam_panel_split")` | `_set_panel_split_review` | TBD |
| tests/test_gui_smoke.py | 2965 | `self.assertTrue(window._has_split_crops_from_image(str(parent_image)))` | `_has_split_crops_from_image` | TBD |
| tests/test_gui_smoke.py | 2966 | `self.assertFalse(window._needs_manual_panel_split(str(parent_image)))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 2967 | `self.assertFalse(window._needs_manual_panel_split(str(crop_image)))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 2991 | `self.assertTrue(window._needs_manual_panel_split(str(image_path)))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 2997 | `self.assertFalse(window._needs_manual_panel_split(str(image_path)))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 3020 | `window._set_panel_split_review(str(image_a), "manual_required", reason="hard_seam_panel_split")` | `_set_panel_split_review` | TBD |
| tests/test_gui_smoke.py | 3021 | `window._set_panel_split_review(str(image_b), "manual_required", reason="hard_seam_panel_split")` | `_set_panel_split_review` | TBD |
| tests/test_gui_smoke.py | 3031 | `groups = window._project_image_groups()` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 3049 | `window._set_panel_split_review(str(image_path), "manual_done", reason="user_marked_done")` | `_set_panel_split_review` | TBD |
| tests/test_gui_smoke.py | 3051 | `self.assertEqual([Path(path).name for path in window._project_image_groups()["manual_done"]], [image_path.name])` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 3054 | `groups = window._project_image_groups()` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 3078 | `groups = window._project_image_groups()` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 3081 | `self.assertEqual(window._vlm_image_group_label("review_ready"), "Review Ready")` | `_vlm_image_group_label` | TBD |
| tests/test_gui_smoke.py | 3091 | `self.assertEqual(window._current_vlm_image_group(), "review_ready")` | `_current_vlm_image_group` | TBD |
| tests/test_gui_smoke.py | 3092 | `paths = window._vlm_image_paths_for_scope("image_group")` | `_vlm_image_paths_for_scope` | TBD |
| tests/test_gui_smoke.py | 3120 | `groups = window._project_image_groups()` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 3147 | `self.assertIn("review_ready", {group_id for group_id, _label in window._image_group_move_target_definitions()})` | `_image_group_move_target_definitions` | TBD |
| tests/test_gui_smoke.py | 3151 | `self.assertEqual(window._custom_image_group_definitions(), [])` | `_custom_image_group_definitions` | TBD |
| tests/test_gui_smoke.py | 3153 | `self.assertNotIn("review_ready", {group_id for group_id, _label in window._image_group_move_target_definitions()})` | `_image_group_move_target_definitions` | TBD |
| tests/test_gui_smoke.py | 3176 | `if item.data(main_module.Qt.UserRole) and _same_path(item.data(main_module.Qt.UserRole), image_a):` | - | TBD |
| tests/test_gui_smoke.py | 3230 | `self.assertTrue(window._is_split_crop_image(str(crop_image)))` | `_is_split_crop_image` | TBD |
| tests/test_gui_smoke.py | 3231 | `self.assertFalse(window._is_split_crop_image(str(unrelated_crop)))` | `_is_split_crop_image` | TBD |
| tests/test_gui_smoke.py | 3276 | `with patch.object(main_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 3277 | `with patch.object(main_module.QMessageBox, "information", lambda *args, **kwargs: None):` | - | TBD |
| tests/test_gui_smoke.py | 3303 | `self.assertTrue(window._is_split_crop_image(generated))` | `_is_split_crop_image` | TBD |
| tests/test_gui_smoke.py | 3304 | `self.assertFalse(window._needs_manual_panel_split(generated))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 3309 | `self.assertTrue(window._is_split_crop_image(generated))` | `_is_split_crop_image` | TBD |
| tests/test_gui_smoke.py | 3310 | `self.assertFalse(window._needs_manual_panel_split(generated))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 3315 | `groups = window._project_image_groups()` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 3361 | `with patch.object(main_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 3362 | `with patch.object(main_module.QMessageBox, "information", lambda *args, **kwargs: None):` | - | TBD |
| tests/test_gui_smoke.py | 3370 | `groups = window._project_image_groups()` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 3435 | `db_path, context, reason = window._resolve_current_literature_context()` | `_resolve_current_literature_context` | TBD |
| tests/test_gui_smoke.py | 3470 | `db_path, context, reason = window._resolve_current_literature_context()` | `_resolve_current_literature_context` | TBD |
| tests/test_gui_smoke.py | 3518 | `db_path, context, reason = window._resolve_current_literature_context()` | `_resolve_current_literature_context` | TBD |
| tests/test_gui_smoke.py | 3553 | `with patch.object(main_module.QFileDialog, "getOpenFileName", return_value=(str(literature_db), "SQLite Database (*.db)")):` | - | TBD |
| tests/test_gui_smoke.py | 3554 | `db_path, context, reason = window._choose_literature_db_for_current_taxon()` | `_choose_literature_db_for_current_taxon` | TBD |
| tests/test_gui_smoke.py | 3599 | `dialog = main_module.LiteratureDescriptionDialog(` | - | TBD |
| tests/test_gui_smoke.py | 3631 | `dialog = main_module.LiteratureDescriptionDialog(` | - | TBD |
| tests/test_gui_smoke.py | 3733 | `self.assertTrue(window._is_stl_project_file(stl_path))` | `_is_stl_project_file` | TBD |
| tests/test_gui_smoke.py | 3734 | `with patch.object(main_module.QFileDialog, "getOpenFileName", return_value=(stl_path, "JSON (*.json)")):` | - | TBD |
| tests/test_gui_smoke.py | 3745 | `self.assertEqual(window._active_recent_project_path(), os.path.abspath(stl_path))` | `_active_recent_project_path` | TBD |
| tests/test_gui_smoke.py | 3747 | `context = window._collect_image_workbench_agent_context()` | `_collect_image_workbench_agent_context` | TBD |
| tests/test_gui_smoke.py | 3751 | `self.assertIn("STL rendered-view project", window._start_console_project_summary()[0])` | `_start_console_project_summary` | TBD |
| tests/test_gui_smoke.py | 3752 | `self.assertIn("1 STL rendered 2D view", window._start_console_image_summary()[0])` | `_start_console_image_summary` | TBD |
| tests/test_reporting_routes.py | 45 | `from AntSleap.main import TrainingReportDialog` | - | TBD |
| tests/test_ui_localization.py | 20 | `from AntSleap.main import ExportDialog, BlinkEntryDialog, ModelSettingsDialog, RouteManagementPanel, TrainingPreflightDialog, TrainingReportDialog` | - | TBD |
| tests/test_ui_localization.py | 303 | `self.assertEqual(main_module.tr("Close", "zh"), "关闭")` | - | TBD |
| tests/test_ui_localization.py | 304 | `self.assertEqual(main_module.tr("Select Directory", "zh"), "选择目录")` | - | TBD |
| tests/test_ui_localization.py | 307 | `self.assertEqual(main_module.tr("Del", "zh"), "删除")` | - | TBD |
| tests/test_ui_localization.py | 308 | `self.assertEqual(main_module.tr("Locator switched to: {0}", "zh"), "定位器已切换为：{0}")` | - | TBD |
| tests/test_ui_localization.py | 310 | `main_module.tr("Delete the selected locator model file from disk.", "zh"),` | - | TBD |
| tests/test_ui_localization.py | 314 | `main_module.tr("Delete the selected segmenter model file from disk.", "zh"),` | - | TBD |
| tests/test_ui_localization.py | 551 | `self.assertEqual(len(locator_group.findChildren(main_module.QCheckBox)), 3)` | - | TBD |
| tests/test_ui_localization.py | 641 | `"model_backend": main_module.BUILTIN_BACKEND_ID,` | - | TBD |
| tests/test_ui_localization.py | 655 | `self.assertEqual(dialog.backend_combo.currentData(), main_module.EXTERNAL_BACKEND_ID)` | - | TBD |
| tests/test_ui_localization.py | 677 | `self.assertEqual(values_before_activation["model_backend"], main_module.BUILTIN_BACKEND_ID)` | - | TBD |
| tests/test_ui_localization.py | 689 | `self.assertEqual(values_after_activation["model_backend"], main_module.EXTERNAL_BACKEND_ID)` | - | TBD |
| tests/test_ui_localization.py | 708 | `"model_backend": main_module.BUILTIN_BACKEND_ID,` | - | TBD |
| tests/test_ui_localization.py | 743 | `self.assertEqual(dialog.backend_combo.currentData(), main_module.EXTERNAL_BACKEND_ID)` | - | TBD |
| tests/test_ui_localization.py | 746 | `self.assertEqual(dialog.child_backend_combo.itemText(dialog.child_backend_combo.findData(main_module.CHILD_BACKEND_EXTERNAL)), "Custom Child Extension")` | - | TBD |
| tests/test_ui_localization.py | 752 | `self.assertEqual(values["model_backend"], main_module.EXTERNAL_BACKEND_ID)` | - | TBD |
| tests/test_ui_localization.py | 772 | `"model_backend": main_module.EXTERNAL_BACKEND_ID,` | - | TBD |
| tests/test_ui_localization.py | 786 | `self.assertEqual(dialog.backend_combo.currentData(), main_module.EXTERNAL_BACKEND_ID)` | - | TBD |
| tests/test_ui_localization.py | 956 | `tabs = dialog.findChild(main_module.QTabWidget)` | - | TBD |
| tests/test_ui_localization.py | 957 | `overview_text = tabs.widget(0).findChild(main_module.QTextEdit).toPlainText()` | - | TBD |
| tests/test_ui_localization.py | 959 | `coverage_text = tabs.widget(1).findChild(main_module.QTextEdit).toPlainText()` | - | TBD |
| tests/test_ui_localization.py | 1024 | `main_module.MainWindow.clear_ai_labels(window)` | - | TBD |
| tests/test_ui_polish_scope.py | 953 | `preflight_dialog = main_module.TrainingPreflightDialog(preflight, parent=owner, lang="en")` | - | TBD |
| tests/test_ui_polish_scope.py | 954 | `entry_dialog = main_module.BlinkEntryDialog(` | - | TBD |
| tests/test_ui_polish_scope.py | 1012 | `patch.object(main_module.QTimer, "singleShot", lambda *args, **kwargs: None):` | - | TBD |
| tests/test_ui_polish_scope.py | 1013 | `return main_module.MainWindow()` | - | TBD |
| tests/test_ui_polish_scope.py | 1167 | `with patch.object(main_module.QMessageBox, "information", lambda *args, **kwargs: None):` | - | TBD |
| tests/test_ui_polish_scope.py | 1201 | `with patch.object(main_module.QMessageBox, "information", lambda *args, **kwargs: None):` | - | TBD |
| tests/test_ui_polish_scope.py | 1208 | `with patch.object(main_module.QMessageBox, "information", lambda *args, **kwargs: None):` | - | TBD |
| tests/test_ui_polish_scope.py | 1344 | `if item.data(main_module.Qt.UserRole + 1) == "original":` | - | TBD |
| tests/test_ui_polish_scope.py | 1350 | `window._handle_image_list_item_clicked(original_header)` | `_handle_image_list_item_clicked` | TBD |
| tests/test_ui_polish_scope.py | 1380 | `cached_state = window._image_list_state_cache` | `_image_list_state_cache` | TBD |
| tests/test_ui_polish_scope.py | 1387 | `if item.data(main_module.Qt.UserRole + 1) == "original":` | - | TBD |
| tests/test_ui_polish_scope.py | 1393 | `window._handle_image_list_item_clicked(original_header)` | `_handle_image_list_item_clicked` | TBD |
| tests/test_ui_polish_scope.py | 1396 | `self.assertIs(window._image_list_state_cache, cached_state)` | `_image_list_state_cache` | TBD |
| tests/test_ui_polish_scope.py | 1419 | `window._apply_literature_description(` | `_apply_literature_description` | TBD |
| tests/test_ui_polish_scope.py | 1477 | `self.assertEqual(head_item.data(0, main_module.Qt.UserRole), "Head")` | - | TBD |
| tests/test_ui_polish_scope.py | 1479 | `self.assertEqual(head_item.child(0).data(0, main_module.Qt.UserRole), "Mandible")` | - | TBD |
| tests/test_ui_polish_scope.py | 1482 | `self.assertIsNone(cross_region_item.data(0, main_module.Qt.UserRole))` | - | TBD |
| tests/test_ui_polish_scope.py | 1483 | `self.assertEqual(cross_region_item.child(0).data(0, main_module.Qt.UserRole), "Seta")` | - | TBD |
| tests/test_ui_polish_scope.py | 1487 | `self.assertEqual(window._current_part_name(), "Mandible")` | `_current_part_name` | TBD |
| tests/test_ui_polish_scope.py | 1492 | `self.assertIsNone(window._current_part_name())` | `_current_part_name` | TBD |
| tests/test_ui_polish_scope.py | 1536 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 1537 | `context = window._refresh_blink_refine_state()` | `_refresh_blink_refine_state` | TBD |
| tests/test_ui_polish_scope.py | 1570 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 1580 | `context = window._refresh_blink_refine_state()` | `_refresh_blink_refine_state` | TBD |
| tests/test_ui_polish_scope.py | 1606 | `self.assertEqual(window.part_list.topLevelItem(0).data(0, main_module.Qt.UserRole), "Head")` | - | TBD |
| tests/test_ui_polish_scope.py | 1609 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 1610 | `context = window._refresh_blink_refine_state()` | `_refresh_blink_refine_state` | TBD |
| tests/test_ui_polish_scope.py | 1625 | `self.assertEqual(window.part_list.topLevelItem(0).child(0).data(0, main_module.Qt.UserRole), "Mandible")` | - | TBD |
| tests/test_ui_polish_scope.py | 1649 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 1650 | `context = window._refresh_blink_refine_state()` | `_refresh_blink_refine_state` | TBD |
| tests/test_ui_polish_scope.py | 1668 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 1697 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 1720 | `window._select_part_in_tree("Head")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 1741 | `canvas = main_module.AnnotationCanvas()` | - | TBD |
| tests/test_ui_polish_scope.py | 1772 | `window._select_part_in_tree("Head")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 1776 | `with patch.object(main_module.QMessageBox, "information") as info:` | - | TBD |
| tests/test_ui_polish_scope.py | 1828 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 1897 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 1898 | `before_context = window._refresh_blink_refine_state()` | `_refresh_blink_refine_state` | TBD |
| tests/test_ui_polish_scope.py | 1904 | `after_context = window._refresh_blink_refine_state()` | `_refresh_blink_refine_state` | TBD |
| tests/test_ui_polish_scope.py | 1937 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 1938 | `context = window._refresh_blink_refine_state()` | `_refresh_blink_refine_state` | TBD |
| tests/test_ui_polish_scope.py | 1943 | `with patch.object(main_module.QMessageBox, "information") as info:` | - | TBD |
| tests/test_ui_polish_scope.py | 1949 | `window._refresh_blink_refine_state()` | `_refresh_blink_refine_state` | TBD |
| tests/test_ui_polish_scope.py | 1995 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 1996 | `context = window._refresh_blink_refine_state()` | `_refresh_blink_refine_state` | TBD |
| tests/test_ui_polish_scope.py | 2002 | `with patch.object(main_module.QMessageBox, "information") as info:` | - | TBD |
| tests/test_ui_polish_scope.py | 2060 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 2133 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 2135 | `with patch.object(main_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_ui_polish_scope.py | 2173 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 2174 | `with patch.object(main_module.QMessageBox, "information") as info:` | - | TBD |
| tests/test_ui_polish_scope.py | 2179 | `with patch.object(main_module.QMessageBox, "information") as info:` | - | TBD |
| tests/test_ui_polish_scope.py | 2215 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 2315 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 2356 | `window._connect_child_training_progress()` | `_connect_child_training_progress` | TBD |
| tests/test_ui_polish_scope.py | 2380 | `main_module.json.dumps(` | - | TBD |
| tests/test_ui_polish_scope.py | 2388 | `"parent_backend": main_module.PARENT_BACKEND_BUILTIN,` | - | TBD |
| tests/test_ui_polish_scope.py | 2398 | `main_module.json.dumps(` | - | TBD |
| tests/test_ui_polish_scope.py | 2404 | `"training_strategy": main_module.BLINK_STRATEGY_TWO_STAGE_FULL_THEN_INSIDE,` | - | TBD |
| tests/test_ui_polish_scope.py | 2429 | `dialog = main_module.TrainingResultBrowserDialog(reports, lang="en")` | - | TBD |
| tests/test_ui_polish_scope.py | 2465 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 2469 | `patch.object(main_module.QMessageBox, "information") as info:` | - | TBD |
| tests/test_ui_polish_scope.py | 2477 | `with patch.object(main_module.QMessageBox, "information") as info:` | - | TBD |
| tests/test_ui_polish_scope.py | 2499 | `return_value=main_module.QMessageBox.Yes,` | - | TBD |
| tests/test_ui_polish_scope.py | 2565 | `dialog = main_module.ModelSettingsDialog(` | - | TBD |
| tests/test_ui_polish_scope.py | 2604 | `self.assertIsNotNone(dialog.findChild(main_module.QToolButton, "modelSettingsVlmDetailToggle"))` | - | TBD |
| tests/test_ui_polish_scope.py | 2621 | `with patch.object(main_module.QDialog, "exec", return_value=main_module.QDialog.DialogCode.Accepted) as exec_dialog:` | - | TBD |
| tests/test_ui_polish_scope.py | 2624 | `with patch.object(main_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_ui_polish_scope.py | 2630 | `self.assertIsInstance(dialog.spin_blink_auto_shrink_steps, main_module.NoWheelSpinBox)` | - | TBD |
| tests/test_ui_polish_scope.py | 2632 | `self.assertIsInstance(dialog.spin_vlm_concurrency, main_module.NoWheelSpinBox)` | - | TBD |
| tests/test_ui_polish_scope.py | 2672 | `spin = main_module.NoWheelSpinBox()` | - | TBD |
| tests/test_ui_polish_scope.py | 2680 | `slider = main_module.NoWheelSlider(main_module.Qt.Horizontal)` | - | TBD |
| tests/test_ui_polish_scope.py | 2734 | `return_value=main_module.QMessageBox.Yes,` | - | TBD |
| tests/test_ui_polish_scope.py | 2790 | `main_module.QInputDialog,` | - | TBD |
| tests/test_ui_polish_scope.py | 2815 | `dialog = main_module.ModelSettingsDialog(` | - | TBD |
| tests/test_ui_polish_scope.py | 2836 | `device_combo = runtime_group.findChild(main_module.QComboBox)` | - | TBD |
| tests/test_ui_polish_scope.py | 2844 | `checks = {check.text(): check for check in locator_group.findChildren(main_module.QCheckBox)}` | - | TBD |
| tests/test_ui_polish_scope.py | 2867 | `dialog = main_module.ModelSettingsDialog(` | - | TBD |
| tests/test_ui_polish_scope.py | 2984 | `saved, total = window._apply_prediction_to_project(image_key, prediction, only_new=True, save=False)` | `_apply_prediction_to_project` | TBD |
| tests/test_ui_polish_scope.py | 2996 | `saved, total = window._apply_prediction_to_project(` | `_apply_prediction_to_project` | TBD |
| tests/test_ui_polish_scope.py | 3034 | `ok, mode = window._apply_vlm_candidate(` | `_apply_vlm_candidate` | TBD |
| tests/test_ui_polish_scope.py | 3076 | `saved, total = window._apply_prediction_to_project(image_key, prediction, only_new=True, save=False)` | `_apply_prediction_to_project` | TBD |
| tests/test_ui_polish_scope.py | 3116 | `window._refresh_current_canvas_boxes()` | `_refresh_current_canvas_boxes` | TBD |
| tests/test_ui_polish_scope.py | 3146 | `ok, mode = window._apply_vlm_candidate(` | `_apply_vlm_candidate` | TBD |
| tests/test_ui_polish_scope.py | 3164 | `ok, mode = window._apply_vlm_candidate(` | `_apply_vlm_candidate` | TBD |
| tests/test_ui_polish_scope.py | 3201 | `context = window._collect_image_workbench_agent_context()` | `_collect_image_workbench_agent_context` | TBD |
| tests/test_ui_polish_scope.py | 3207 | `compact = window._compact_agent_context(context)` | `_compact_agent_context` | TBD |
| tests/test_ui_polish_scope.py | 3223 | `window._on_training_success()` | `_on_training_success` | TBD |
| tests/test_ui_polish_scope.py | 3305 | `main_module.QInputDialog,` | - | TBD |
| tests/test_ui_polish_scope.py | 3323 | `main_module.QInputDialog,` | - | TBD |
| tests/test_ui_polish_scope.py | 3347 | `return_value=main_module.QMessageBox.Yes,` | - | TBD |
| tests/test_ui_polish_scope.py | 3423 | `return_value=main_module.QMessageBox.Yes,` | - | TBD |
| tests/test_ui_polish_scope.py | 3451 | `return_value=main_module.QMessageBox.Yes,` | - | TBD |
| tests/test_ui_polish_scope.py | 3545 | `window._flush_pending_project_save()` | `_flush_pending_project_save` | TBD |
| tests/test_ui_polish_scope.py | 3683 | `if item.data(main_module.Qt.UserRole) == image_paths[0]:` | - | TBD |
| tests/test_ui_polish_scope.py | 3690 | `with patch.object(main_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes), \` | - | TBD |
| tests/test_ui_polish_scope.py | 3703 | `window.file_list.item(row).data(main_module.Qt.UserRole)` | - | TBD |
| tests/test_ui_polish_scope.py | 3705 | `if window.file_list.item(row).data(main_module.Qt.UserRole)` | - | TBD |
| tests/test_ui_polish_scope.py | 3742 | `if item.data(main_module.Qt.UserRole) == image_paths[1]:` | - | TBD |
| tests/test_ui_polish_scope.py | 3748 | `with patch.object(main_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_ui_polish_scope.py | 3753 | `self.assertEqual(window.file_list.currentItem().data(main_module.Qt.UserRole), image_paths[2])` | - | TBD |
| tests/test_ui_polish_scope.py | 3755 | `window.file_list.item(row).data(main_module.Qt.UserRole)` | - | TBD |
| tests/test_ui_polish_scope.py | 3757 | `if window.file_list.item(row).data(main_module.Qt.UserRole)` | - | TBD |
| tests/test_ui_polish_scope.py | 3794 | `if item.data(main_module.Qt.UserRole) == image_paths[2]:` | - | TBD |
| tests/test_ui_polish_scope.py | 3800 | `with patch.object(main_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_ui_polish_scope.py | 3805 | `self.assertEqual(window.file_list.currentItem().data(main_module.Qt.UserRole), image_paths[1])` | - | TBD |
| tests/test_ui_polish_scope.py | 3807 | `window.file_list.item(row).data(main_module.Qt.UserRole)` | - | TBD |
| tests/test_ui_polish_scope.py | 3809 | `if window.file_list.item(row).data(main_module.Qt.UserRole)` | - | TBD |
| tests/test_ui_polish_scope.py | 4007 | `return_value=main_module.QMessageBox.No,` | - | TBD |
| tests/test_ui_polish_scope.py | 4016 | `return_value=main_module.QMessageBox.Yes,` | - | TBD |
| tests/test_ui_polish_scope.py | 4059 | `return_value=main_module.QMessageBox.Yes,` | - | TBD |
| tests/test_ui_polish_scope.py | 4102 | `window.vlm_preannotation_prompt_profile = main_module.default_vlm_prompt_profile()` | - | TBD |
| tests/test_ui_polish_scope.py | 4108 | `return_value=main_module.QMessageBox.Yes,` | - | TBD |
| tests/test_ui_polish_scope.py | 4119 | `window._on_vlm_preannotation_finished()` | `_on_vlm_preannotation_finished` | TBD |
| tests/test_ui_polish_scope.py | 4160 | `window.vlm_preannotation_prompt_profile = main_module.default_vlm_prompt_profile()` | - | TBD |
| tests/test_ui_polish_scope.py | 4164 | `window._start_vlm_preannotation_workers()` | `_start_vlm_preannotation_workers` | TBD |
| tests/test_ui_polish_scope.py | 4269 | `return_value=main_module.QMessageBox.Yes,` | - | TBD |
| tests/test_ui_polish_scope.py | 4330 | `return_value=main_module.QMessageBox.Yes,` | - | TBD |
| tests/test_ui_polish_scope.py | 4395 | `self.assertFalse(window._flush_pending_project_save())` | `_flush_pending_project_save` | TBD |
| tests/test_ui_polish_scope.py | 4400 | `window._flush_pending_project_save(force=True)` | `_flush_pending_project_save` | TBD |
| tests/test_ui_polish_scope.py | 4511 | `window._on_vlm_preannotation_image_result(result)` | `_on_vlm_preannotation_image_result` | TBD |
