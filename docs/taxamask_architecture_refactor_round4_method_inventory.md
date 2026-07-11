# TaxaMask Round 4 Main Window Method Inventory

由 `scripts/analyze_main_window_architecture.py` 生成。Stage 0 冻结当前责任、兼容入口和目标阶段，实施时必须结合真实调用复核。

## Metrics

| Metric | Value |
| --- | --- |
| main_physical_lines | 15389 |
| top_level_class_count | 11 |
| top_level_function_count | 23 |
| all_method_count | 570 |
| private_method_count | 405 |
| connection_count | 194 |
| source_state_assignment_lines | 610 |
| main_window_lines | 9489 |
| main_window_method_count | 390 |
| main_window_connection_count | 128 |
| main_window_init_lines | 668 |
| main_window_methods_ge_50 | 42 |
| main_window_methods_ge_100 | 11 |
| main_window_unique_state_fields | 238 |
| main_window_state_assignment_occurrences | 418 |
| main_import_site_count | 15 |
| key_test_reference_line_count | 324 |
| key_test_private_reference_occurrences | 142 |
| key_test_unique_private_references | 51 |
| async_entry_count | 16 |

## Top-level Classes

| Line | Size | Class | Methods | Connects | Refs | Stage |
| --- | --- | --- | --- | --- | --- | --- |
| 1579 | 173 | `TrainingPreflightDialog` | 14 | 2 | 4 | 2 |
| 1753 | 304 | `TrainingReportDialog` | 12 | 6 | 5 | 2 |
| 2059 | 113 | `TrainingResultBrowserDialog` | 7 | 6 | 2 | 2 |
| 2174 | 667 | `RouteManagementPanel` | 34 | 7 | 9 | 2 |
| 2842 | 2135 | `ModelSettingsDialog` | 67 | 22 | 20 | 2 |
| 4979 | 138 | `GeneralSettingsDialog` | 5 | 3 | 4 | 2 |
| 5119 | 257 | `TifModelSettingsDialog` | 12 | 5 | 2 | 2 |
| 5378 | 48 | `ExportDialog` | 4 | 3 | 4 | 2 |
| 5428 | 93 | `BlinkEntryDialog` | 4 | 3 | 12 | 2 |
| 5523 | 354 | `LiteratureDescriptionDialog` | 21 | 9 | 4 | 2 |
| 5879 | 9489 | `MainWindow` | 390 | 128 | 32 | 3 |

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
| 5883 | 668 | `__init__` | unclassified | 8 | public_or_source_compatibility | 195 | 130 | 0 |
| 6552 | 2 | `_is_tif_workflow_enabled` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 6555 | 9 | `_show_tif_workflow_unavailable` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 6565 | 10 | `_apply_window_icon` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 6576 | 18 | `apply_startup_window_geometry` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 6595 | 124 | `_build_start_center` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 6720 | 25 | `_build_start_quick_panel` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 6746 | 76 | `_build_project_console` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 6823 | 3 | `_toggle_start_project_console` | shell_start_agent | 3 | signal_compatibility | 0 | 0 | 1 |
| 6827 | 12 | `_update_start_project_console_collapsed_state` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 6840 | 12 | `_build_project_console_row` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 6853 | 32 | `_build_workflow_card` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 6886 | 4 | `_show_start_center` | shell_start_agent | 3 | test_compatibility | 0 | 2 | 0 |
| 6891 | 48 | `_update_start_center_texts` | shell_start_agent | 3 | test_compatibility | 0 | 1 | 0 |
| 6940 | 3 | `_handle_agent_dashboard_status_changed` | shell_start_agent | 3 | signal_compatibility | 0 | 0 | 1 |
| 6944 | 11 | `_update_start_agent_status` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 6956 | 45 | `_refresh_project_console` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 7002 | 8 | `_start_console_collapsed_summary` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 7011 | 22 | `_start_console_project_summary` | shell_start_agent | 3 | test_compatibility | 0 | 1 | 0 |
| 7034 | 13 | `_compact_project_path` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 7048 | 19 | `_start_console_image_summary` | shell_start_agent | 3 | test_compatibility | 0 | 1 | 0 |
| 7068 | 22 | `_start_console_tif_summary` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 7091 | 14 | `_start_console_pdf_summary` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 7106 | 5 | `_is_pdf_candidate_provenance` | pdf_evidence | 5 | test_compatibility | 0 | 1 | 0 |
| 7112 | 5 | `_start_console_agent_status` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 7118 | 7 | `_agent_current_workflow_label` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 7126 | 8 | `_agent_current_project_label` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 7141 | 7 | `_recent_text_excerpt` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 7149 | 5 | `_agent_context_text` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 7155 | 202 | `_compact_agent_context` | shell_start_agent | 3 | public_or_source_compatibility | 1 | 5 | 0 |
| 7358 | 27 | `_collect_image_workbench_agent_context` | shell_start_agent | 3 | public_or_source_compatibility | 1 | 4 | 0 |
| 7386 | 13 | `_collect_blink_agent_context` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 7400 | 30 | `_pdf_agent_prompt` | shell_start_agent | 3 | test_compatibility | 0 | 1 | 0 |
| 7431 | 15 | `open_agent_for_pdf_workflow` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 7447 | 27 | `open_agent_from_context` | shell_start_agent | 3 | public_or_source_compatibility | 2 | 3 | 6 |
| 7475 | 2 | `return_to_start_center_with_context` | shell_start_agent | 3 | public_or_source_compatibility | 1 | 1 | 4 |
| 7478 | 8 | `_open_workflow_from_agent` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 7487 | 8 | `_open_model_settings_from_agent` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 7496 | 6 | `enter_image_workflow` | shell_start_agent | 3 | public_or_source_compatibility | 3 | 9 | 0 |
| 7503 | 8 | `enter_tif_workflow` | shell_start_agent | 3 | public_or_source_compatibility | 2 | 1 | 0 |
| 7512 | 2 | `_default_outputs_root` | unclassified | 8 | public_or_source_compatibility | 3 | 2 | 0 |
| 7515 | 4 | `_ensure_default_output_subdir` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 7520 | 2 | `_default_2d_stl_projects_root` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 7523 | 2 | `_default_tif_projects_root` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 7526 | 2 | `_default_startup_project_dir` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 7529 | 2 | `_startup_project_manifest_path` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 7532 | 2 | `_startup_legacy_json_project_path` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 7535 | 14 | `_open_or_create_startup_project` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 7550 | 4 | `_default_project_dialog_dir` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 7555 | 5 | `_current_2d_project_dir` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 7561 | 4 | `_default_2d_export_dir` | runtime_worker | 1 | test_compatibility | 0 | 2 | 0 |
| 7566 | 4 | `_default_vlm_preannotation_dir` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 7571 | 18 | `_default_open_project_dir` | project_lifecycle | 4 | test_compatibility | 0 | 1 | 0 |
| 7590 | 8 | `_path_is_startup_project` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 7599 | 5 | `_path_is_inside_program_package` | unclassified | 8 | public_or_source_compatibility | 3 | 0 | 0 |
| 7605 | 8 | `open_last_project` | project_lifecycle | 4 | signal_compatibility | 0 | 1 | 1 |
| 7614 | 45 | `closeEvent` | project_lifecycle | 4 | public_or_source_compatibility | 13 | 0 | 0 |
| 7660 | 10 | `_active_recent_project_path` | project_lifecycle | 4 | test_compatibility | 0 | 1 | 0 |
| 7671 | 22 | `_shutdown_background_workers` | runtime_worker | 1 | public_or_source_compatibility | 1 | 0 | 0 |
| 7694 | 3 | `destroy` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 7698 | 5 | `_schedule_project_save` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 7704 | 5 | `_defer_project_save_for_active_navigation` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 7710 | 54 | `_flush_pending_project_save` | project_lifecycle | 4 | signal_compatibility | 0 | 3 | 1 |
| 7765 | 51 | `refresh_model_list` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 7817 | 5 | `_selected_locator_timestamp` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 7823 | 4 | `_selected_locator_display_text` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 7828 | 9 | `_parent_model_filename` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 7838 | 40 | `_build_locator_combo_label` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 7879 | 7 | `_build_segmenter_combo_label` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 7887 | 5 | `_selected_segmenter_timestamp` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 7893 | 2 | `_active_project_route_manifest` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 7896 | 9 | `_active_model_profile_context` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 7906 | 6 | `_active_external_backend_config` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 7913 | 5 | `_selected_route_entry` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 7919 | 5 | `_route_runtime_status` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 7925 | 8 | `refresh_route_table` | dialog_settings | 2 | signal_compatibility | 0 | 30 | 2 |
| 7934 | 4 | `update_route_action_buttons` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 7939 | 16 | `_refresh_project_bound_views` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 7956 | 5 | `_project_image_count` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 7962 | 17 | `_prepare_image_list_for_project_open` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 7980 | 12 | `_preload_2d_stl_models_after_open` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 7993 | 5 | `_ensure_tab_visible` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 7999 | 6 | `_remove_tab_if_present` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 8006 | 23 | `_apply_project_mode_tabs` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 8030 | 13 | `_is_tif_project_file` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 8044 | 11 | `_is_stl_project_file` | project_lifecycle | 4 | test_compatibility | 0 | 1 | 0 |
| 8056 | 7 | `_read_project_probe_payload` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 8064 | 6 | `_is_sqlite_project_manifest_payload` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 8071 | 2 | `_is_tif_sqlite_project_manifest_payload` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 8074 | 2 | `_is_2d_sqlite_project_manifest_payload` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 8077 | 15 | `_is_legacy_2d_json_project_payload` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 8093 | 2 | `_is_legacy_2d_json_project_file` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 8096 | 23 | `_candidate_manifest_paths_for_sqlite_database` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 8120 | 15 | `_manifest_for_sqlite_database_file` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 8136 | 3 | `_is_project_sqlite_database_file` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 8140 | 11 | `_active_sqlite_project_manager` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 8152 | 9 | `_flush_active_sqlite_project_before_maintenance` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 8162 | 6 | `_sqlite_maintenance_default_dir` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 8169 | 42 | `backup_current_sqlite_project` | project_lifecycle | 4 | test_compatibility | 0 | 1 | 0 |
| 8212 | 42 | `export_current_project_legacy_json` | runtime_worker | 1 | test_compatibility | 0 | 1 | 0 |
| 8255 | 23 | `open_current_sqlite_migration_report` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 8279 | 4 | `appoint_selected_route_expert` | blink | 6 | signal_compatibility | 0 | 1 | 1 |
| 8284 | 4 | `toggle_selected_route_enabled` | dialog_settings | 2 | signal_compatibility | 0 | 0 | 1 |
| 8289 | 4 | `delete_selected_route` | dialog_settings | 2 | signal_compatibility | 0 | 2 | 1 |
| 8294 | 30 | `_log_route_usage_summary` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 8325 | 4 | `_locator_model_path` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8330 | 4 | `_segmenter_model_path` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8335 | 18 | `_apply_locator_selection_to_runtime` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 8354 | 2 | `_locator_selection_needs_legacy_confirmation` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8357 | 20 | `_confirm_legacy_locator_selection_if_needed` | training_model | 7 | test_compatibility | 0 | 1 | 0 |
| 8378 | 5 | `_show_structured_training_preflight` | dialog_settings | 2 | test_compatibility | 0 | 1 | 0 |
| 8384 | 3 | `_is_locator_oom_error` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8388 | 30 | `_ask_locator_oom_retry_resolution` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8419 | 3 | `_is_parent_training_running` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8423 | 4 | `_is_child_training_running` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 8428 | 2 | `_is_any_training_running` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8431 | 19 | `_set_training_progress` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8451 | 11 | `_connect_child_training_progress` | blink | 6 | test_compatibility | 0 | 1 | 0 |
| 8463 | 6 | `_on_child_training_result` | blink | 6 | signal_compatibility | 0 | 0 | 1 |
| 8470 | 3 | `_on_child_training_error` | blink | 6 | signal_compatibility | 0 | 0 | 1 |
| 8474 | 3 | `_on_child_training_cancelled` | blink | 6 | signal_compatibility | 0 | 0 | 1 |
| 8478 | 10 | `_on_child_training_finished` | blink | 6 | signal_compatibility | 0 | 0 | 1 |
| 8489 | 87 | `_launch_training_with_preflight` | dialog_settings | 2 | test_compatibility | 0 | 1 | 0 |
| 8577 | 15 | `_on_training_success` | training_model | 7 | signal_compatibility | 0 | 1 | 1 |
| 8593 | 13 | `_on_training_finished` | training_model | 7 | public_or_source_compatibility | 2 | 1 | 1 |
| 8607 | 38 | `_on_training_error` | training_model | 7 | public_or_source_compatibility | 2 | 0 | 1 |
| 8646 | 7 | `stop_training` | training_model | 7 | signal_compatibility | 0 | 0 | 1 |
| 8654 | 21 | `_apply_segmenter_selection_to_runtime` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 8676 | 12 | `update_model_delete_button_states` | training_model | 7 | signal_compatibility | 0 | 0 | 2 |
| 8689 | 33 | `_edit_parent_model_note` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8723 | 2 | `edit_locator_model_note` | training_model | 7 | signal_compatibility | 0 | 1 | 1 |
| 8726 | 2 | `edit_segmenter_model_note` | training_model | 7 | signal_compatibility | 0 | 1 | 1 |
| 8729 | 36 | `on_locator_changed` | training_model | 7 | signal_compatibility | 0 | 1 | 1 |
| 8766 | 26 | `delete_locator_model` | training_model | 7 | signal_compatibility | 0 | 2 | 1 |
| 8793 | 3 | `on_segmenter_changed` | training_model | 7 | signal_compatibility | 0 | 0 | 1 |
| 8797 | 26 | `delete_segmenter_model` | training_model | 7 | signal_compatibility | 0 | 1 | 1 |
| 8824 | 3 | `on_model_changed` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8828 | 29 | `create_menus` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 8858 | 21 | `new_project` | project_lifecycle | 4 | test_compatibility | 0 | 1 | 0 |
| 8880 | 22 | `new_tif_project` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 8903 | 9 | `_ensure_tif_project_open` | project_lifecycle | 4 | public_or_source_compatibility | 6 | 0 | 0 |
| 8913 | 29 | `import_tif_stack_action` | tif_integration | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 8943 | 28 | `import_amira_directory_action` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 8972 | 28 | `import_stl_rendered_views_action` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 9001 | 5 | `open_pdf_evidence_tools` | project_lifecycle | 4 | test_compatibility | 0 | 2 | 0 |
| 9007 | 41 | `open_pdf_multimodal_api_settings` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 9049 | 19 | `_choose_project_template` | project_lifecycle | 4 | test_compatibility | 0 | 1 | 0 |
| 9069 | 12 | `open_project` | project_lifecycle | 4 | public_or_source_compatibility | 2 | 1 | 1 |
| 9082 | 12 | `_confirm_legacy_2d_json_migration` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 9095 | 9 | `_existing_sqlite_manifest_for_legacy_json` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 9105 | 11 | `_confirm_open_existing_sqlite_migration` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 9117 | 12 | `_confirm_legacy_tif_json_migration` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 9130 | 11 | `_existing_tif_sqlite_manifest_for_legacy_json` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 9142 | 11 | `_confirm_open_existing_tif_sqlite_migration` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 9154 | 41 | `_migrate_legacy_2d_project_with_progress` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 9196 | 41 | `_migrate_legacy_tif_project_with_progress` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 9238 | 150 | `open_project_path` | project_lifecycle | 4 | public_or_source_compatibility | 2 | 14 | 0 |
| 9389 | 10 | `_format_relocation_preview` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 9400 | 54 | `check_relocate_project_images` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 9455 | 6 | `_part_item_name` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 9462 | 2 | `_current_part_name` | unclassified | 8 | test_compatibility | 0 | 5 | 0 |
| 9465 | 15 | `_workbench_parent_parts` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 9481 | 3 | `_is_parent_part` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 9485 | 23 | `_part_tree_parent_for` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 9509 | 18 | `_route_parents_for_child` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 9528 | 25 | `_resolve_child_parent` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 9554 | 15 | `_parent_context_box` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 9570 | 5 | `_current_shrink_loose_boxes` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 9576 | 28 | `_auto_boxes_for_canvas` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 9605 | 10 | `_refresh_current_canvas_boxes` | annotation_sam | 6 | test_compatibility | 0 | 1 | 0 |
| 9616 | 15 | `_route_entry_for_context` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 9632 | 26 | `_route_expert_status` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 9659 | 73 | `_current_blink_context` | blink | 6 | public_or_source_compatibility | 1 | 0 | 0 |
| 9733 | 10 | `_parent_box_aspect_ratio` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 9744 | 24 | `_parent_context_options` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 9769 | 15 | `_refresh_annotation_box_constraints` | annotation_sam | 6 | signal_compatibility | 0 | 0 | 1 |
| 9785 | 8 | `_active_box_tool_role` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 9794 | 6 | `_refresh_blink_refine_state` | blink | 6 | test_compatibility | 0 | 9 | 0 |
| 9801 | 7 | `_append_part_tree_item` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 9809 | 22 | `_select_part_in_tree` | unclassified | 8 | test_compatibility | 0 | 18 | 0 |
| 9832 | 17 | `_first_selectable_part_item` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 9850 | 75 | `_refresh_part_tree` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 9926 | 8 | `add_taxonomy_part` | image_navigation | 5 | public_or_source_compatibility | 1 | 29 | 1 |
| 9935 | 7 | `_count_ai_labels_for_images` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 9943 | 67 | `_choose_clear_ai_scope` | unclassified | 8 | test_compatibility | 0 | 1 | 0 |
| 10011 | 41 | `rename_taxonomy_part` | image_navigation | 5 | public_or_source_compatibility | 1 | 3 | 1 |
| 10053 | 13 | `remove_taxonomy_part` | image_navigation | 5 | public_or_source_compatibility | 1 | 6 | 1 |
| 10067 | 55 | `clear_ai_labels` | unclassified | 8 | signal_compatibility | 0 | 2 | 1 |
| 10123 | 6 | `on_global_labels_updated` | unclassified | 8 | signal_compatibility | 0 | 0 | 1 |
| 10130 | 190 | `refresh_ui` | unclassified | 8 | public_or_source_compatibility | 1 | 0 | 0 |
| 10321 | 78 | `_update_blink_refine_panel` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 10400 | 39 | `_update_blink_parent_context_combo` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 10440 | 51 | `open_general_settings` | dialog_settings | 2 | public_or_source_compatibility | 1 | 0 | 1 |
| 10492 | 129 | `open_stl_model_settings` | dialog_settings | 2 | public_or_source_compatibility | 2 | 0 | 0 |
| 10622 | 2 | `open_settings` | dialog_settings | 2 | public_or_source_compatibility | 1 | 0 | 0 |
| 10625 | 15 | `open_tif_model_settings` | dialog_settings | 2 | public_or_source_compatibility | 1 | 0 | 0 |
| 10641 | 13 | `change_language` | shell_start_agent | 3 | public_or_source_compatibility | 4 | 8 | 0 |
| 10655 | 22 | `change_theme` | shell_start_agent | 3 | public_or_source_compatibility | 1 | 0 | 0 |
| 10678 | 15 | `update_widget_themes` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 10694 | 66 | `update_button_themes` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 10760 | 4 | `add_images` | image_navigation | 5 | public_or_source_compatibility | 7 | 36 | 1 |
| 10765 | 94 | `_start_image_import` | shell_start_agent | 3 | test_compatibility | 0 | 1 | 0 |
| 10860 | 5 | `_set_image_import_controls_enabled` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 10866 | 20 | `open_cropper` | project_lifecycle | 4 | signal_compatibility | 0 | 0 | 1 |
| 10887 | 8 | `_is_split_crop_image` | image_navigation | 5 | test_compatibility | 0 | 5 | 0 |
| 10896 | 15 | `_is_hard_joined_candidate_crop` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 10912 | 17 | `_looks_like_panel_crop_path` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 10930 | 26 | `_has_split_crops_from_image` | image_navigation | 5 | test_compatibility | 0 | 1 | 0 |
| 10957 | 10 | `_needs_manual_panel_split` | image_navigation | 5 | test_compatibility | 0 | 8 | 0 |
| 10968 | 8 | `_is_manual_panel_split_done` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 10977 | 10 | `_set_panel_split_review` | image_navigation | 5 | test_compatibility | 0 | 6 | 0 |
| 10988 | 7 | `_clear_panel_split_review` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 10996 | 8 | `_builtin_image_group_definitions` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11005 | 16 | `_custom_image_group_definitions` | image_navigation | 5 | test_compatibility | 0 | 1 | 0 |
| 11022 | 2 | `_all_image_group_definitions` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11025 | 19 | `_training_scope_group_definitions` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11045 | 24 | `_populate_training_scope_combo` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 11070 | 5 | `_refresh_training_scope_combo` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 11076 | 16 | `_selected_training_scope_payload` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 11093 | 13 | `_populate_vlm_image_group_combo` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 11107 | 5 | `_refresh_vlm_image_group_combo` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 11113 | 6 | `_image_group_display_name` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11120 | 2 | `_custom_image_group_ids` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11123 | 9 | `_image_group_move_target_definitions` | image_navigation | 5 | test_compatibility | 0 | 2 | 0 |
| 11133 | 45 | `_remove_empty_custom_image_groups` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11179 | 13 | `_safe_custom_image_group_id` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11193 | 34 | `create_custom_image_group` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11228 | 10 | `_set_image_manual_group` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11239 | 15 | `move_images_to_group` | image_navigation | 5 | signal_compatibility | 0 | 7 | 1 |
| 11255 | 10 | `clear_selected_custom_image_group` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11266 | 10 | `_short_progress_path` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 11277 | 13 | `_prepare_progress_dialog` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 11291 | 6 | `_candidate_panel_split_sources` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11298 | 131 | `batch_split_panel_images` | image_navigation | 5 | signal_compatibility | 0 | 2 | 1 |
| 11430 | 22 | `_save_detected_panel_crops` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11453 | 10 | `_next_panel_crop_path` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11464 | 32 | `_inherit_crop_provenance` | image_navigation | 5 | test_compatibility | 0 | 3 | 0 |
| 11497 | 9 | `_selected_image_paths` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11507 | 8 | `_set_selected_panel_split_status` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11516 | 2 | `mark_selected_manual_split_done` | unclassified | 8 | test_compatibility | 0 | 2 | 0 |
| 11519 | 2 | `mark_selected_manual_split_needed` | unclassified | 8 | test_compatibility | 0 | 1 | 0 |
| 11522 | 8 | `clear_selected_split_status` | unclassified | 8 | test_compatibility | 0 | 1 | 0 |
| 11531 | 23 | `show_file_list_context_menu` | shell_start_agent | 3 | signal_compatibility | 0 | 1 | 1 |
| 11555 | 7 | `_move_selected_images_to_new_group` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11563 | 60 | `remove_selected_images` | image_navigation | 5 | test_compatibility | 0 | 4 | 0 |
| 11624 | 95 | `refresh_file_list` | image_navigation | 5 | public_or_source_compatibility | 1 | 41 | 0 |
| 11720 | 4 | `_image_has_review_content` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11725 | 19 | `_set_image_list_item_status` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11745 | 41 | `_refresh_current_image_list_status` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11787 | 6 | `_refresh_image_list_status_or_rebuild` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11794 | 7 | `_image_list_path_identity` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11802 | 10 | `_visible_image_list_paths` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11813 | 27 | `_replacement_image_after_removal` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11841 | 61 | `_remove_visible_image_list_items` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11903 | 10 | `_filtered_group_definitions_after_removal` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11914 | 14 | `_refresh_visible_image_group_header_counts` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11929 | 31 | `_select_first_visible_image_after_removal` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 11961 | 26 | `_build_image_list_state` | image_navigation | 5 | test_compatibility | 0 | 1 | 0 |
| 11988 | 12 | `_handle_image_list_item_clicked` | image_navigation | 5 | signal_compatibility | 0 | 2 | 1 |
| 12001 | 26 | `eventFilter` | unclassified | 8 | public_or_source_compatibility | 2 | 3 | 0 |
| 12028 | 35 | `_should_use_image_list_arrow_navigation` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 12064 | 21 | `_select_adjacent_image` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 12086 | 55 | `_collect_blink_roi_candidates` | blink | 6 | test_compatibility | 0 | 4 | 0 |
| 12142 | 39 | `on_file_selected` | unclassified | 8 | signal_compatibility | 0 | 0 | 1 |
| 12182 | 11 | `on_part_selected` | unclassified | 8 | public_or_source_compatibility | 2 | 0 | 1 |
| 12194 | 90 | `launch_blink_from_workbench` | blink | 6 | public_or_source_compatibility | 1 | 4 | 1 |
| 12285 | 8 | `on_genus_changed` | image_navigation | 5 | signal_compatibility | 0 | 0 | 1 |
| 12294 | 9 | `update_db_description` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 12304 | 5 | `_current_taxon_text` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 12310 | 8 | `_literature_source_taxon` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 12319 | 19 | `_set_current_image_taxon_from_literature` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 12339 | 21 | `_candidate_literature_db_paths` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 12361 | 55 | `_project_literature_db_paths` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 12417 | 39 | `_resolve_current_literature_context` | dialog_settings | 2 | test_compatibility | 0 | 3 | 0 |
| 12457 | 27 | `_resolve_literature_context_from_selected_db` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 12485 | 23 | `_choose_literature_db_for_current_taxon` | dialog_settings | 2 | test_compatibility | 0 | 1 | 0 |
| 12509 | 22 | `_literature_db_matches_image_source` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 12532 | 42 | `open_literature_description_dialog` | dialog_settings | 2 | signal_compatibility | 0 | 0 | 1 |
| 12575 | 22 | `_open_literature_description_dialog_with_context` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 12598 | 24 | `_apply_literature_description` | dialog_settings | 2 | test_compatibility | 0 | 1 | 0 |
| 12623 | 15 | `_ensure_workbench_description_visible` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 12639 | 2 | `on_enhancement_changed` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 12642 | 16 | `on_tool_changed` | annotation_sam | 6 | public_or_source_compatibility | 2 | 8 | 6 |
| 12659 | 23 | `on_blink_parent_context_changed` | blink | 6 | signal_compatibility | 0 | 2 | 1 |
| 12683 | 2 | `on_magic_wand_clicked` | annotation_sam | 6 | signal_compatibility | 0 | 0 | 1 |
| 12686 | 2 | `on_magic_box_completed` | annotation_sam | 6 | signal_compatibility | 0 | 1 | 1 |
| 12689 | 2 | `_sam_worker_ready` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 12692 | 2 | `_on_sam_model_loaded` | annotation_sam | 6 | signal_compatibility | 0 | 0 | 1 |
| 12695 | 18 | `_begin_sam_prompt` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 12714 | 6 | `_request_sam_point` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 12721 | 6 | `_request_sam_box` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 12728 | 34 | `on_annotation_box_completed` | annotation_sam | 6 | signal_compatibility | 0 | 3 | 1 |
| 12763 | 2 | `_warn_blink_context` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 12766 | 12 | `_active_child_blink_context` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 12779 | 43 | `run_blink_child_auto_annotate` | blink | 6 | signal_compatibility | 0 | 4 | 1 |
| 12823 | 9 | `_load_blink_refiner_class` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 12833 | 11 | `_active_blink_auto_shrink_steps` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 12845 | 14 | `_blink_parent_context_for_image` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 12860 | 41 | `_prepared_blink_auto_shrink_images` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 12902 | 38 | `_generate_blink_shrink_for_image` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 12941 | 42 | `run_blink_auto_shrink` | blink | 6 | signal_compatibility | 0 | 3 | 1 |
| 12984 | 90 | `run_blink_batch_auto_shrink` | blink | 6 | signal_compatibility | 0 | 1 | 1 |
| 13075 | 66 | `train_current_blink_expert` | blink | 6 | signal_compatibility | 0 | 3 | 1 |
| 13142 | 10 | `stop_current_blink_expert_training` | blink | 6 | signal_compatibility | 0 | 1 | 1 |
| 13153 | 18 | `open_current_route_expert_settings` | blink | 6 | signal_compatibility | 0 | 0 | 1 |
| 13172 | 10 | `on_sam_mask_generated` | annotation_sam | 6 | signal_compatibility | 0 | 0 | 1 |
| 13183 | 7 | `on_sam_prompt_failed` | annotation_sam | 6 | signal_compatibility | 0 | 0 | 1 |
| 13191 | 23 | `on_polygon_completed` | annotation_sam | 6 | signal_compatibility | 0 | 4 | 1 |
| 13215 | 7 | `toggle_morphometrics` | unclassified | 8 | signal_compatibility | 0 | 0 | 1 |
| 13223 | 9 | `on_scale_defined` | annotation_sam | 6 | signal_compatibility | 0 | 0 | 1 |
| 13233 | 16 | `update_measurements` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 13250 | 87 | `run_training` | training_model | 7 | public_or_source_compatibility | 1 | 2 | 1 |
| 13338 | 2 | `_external_backend_runner` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 13341 | 27 | `_sync_blink_lab_model_profile_defaults` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 13369 | 51 | `run_external_training` | training_model | 7 | test_compatibility | 0 | 1 | 0 |
| 13421 | 3 | `show_training_report` | dialog_settings | 2 | signal_compatibility | 0 | 0 | 1 |
| 13425 | 26 | `_candidate_training_experiment_dirs` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 13452 | 10 | `_resolve_report_artifact_path` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 13463 | 11 | `_training_report_time_label` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 13475 | 66 | `_training_report_payload_from_summary` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 13542 | 26 | `discover_training_reports` | dialog_settings | 2 | test_compatibility | 0 | 1 | 0 |
| 13569 | 8 | `open_training_report_payload` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 13578 | 17 | `open_training_results_browser` | project_lifecycle | 4 | signal_compatibility | 0 | 0 | 1 |
| 13596 | 37 | `_extract_prediction_payload` | vlm_prediction_export | 7 | public_or_source_compatibility | 2 | 0 | 0 |
| 13634 | 12 | `_is_unconfirmed_ai_draft` | vlm_prediction_export | 7 | public_or_source_compatibility | 2 | 0 | 0 |
| 13647 | 13 | `_auto_box_meta_for_part` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 13661 | 3 | `_auto_box_source_for_part` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 13665 | 3 | `_auto_box_review_status_for_part` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 13669 | 5 | `_auto_annotation_source_meta` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 13675 | 15 | `_can_replace_existing_auto_annotation` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 13691 | 33 | `_apply_prediction_to_project` | vlm_prediction_export | 7 | test_compatibility | 0 | 3 | 0 |
| 13725 | 5 | `_vlm_api_settings_path` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 13731 | 40 | `_vlm_api_config_from_pdf_widget` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 13772 | 8 | `_vlm_preannotation_artifacts_dir` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 13781 | 4 | `_current_vlm_target_parts` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 13786 | 4 | `_current_vlm_processing_scope` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 13791 | 3 | `_current_vlm_batch_scope` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 13795 | 4 | `_current_vlm_image_group` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 13800 | 8 | `_current_vlm_concurrency` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 13809 | 5 | `_current_vlm_prompt_profile` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 13815 | 2 | `_vlm_image_group_label` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 13818 | 57 | `_panel_crop_identity_index` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 13876 | 57 | `_project_image_groups` | project_lifecycle | 4 | test_compatibility | 0 | 8 | 0 |
| 13934 | 10 | `_vlm_candidate_source_meta` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 13945 | 19 | `_record_sqlite_vlm_image_result` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 13965 | 13 | `_finish_sqlite_vlm_run` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 13979 | 7 | `_vlm_image_paths_for_scope` | vlm_prediction_export | 7 | test_compatibility | 0 | 3 | 0 |
| 13987 | 2 | `_vlm_image_paths_from_settings` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 13990 | 11 | `_same_project_image_path` | project_lifecycle | 4 | test_compatibility | 0 | 1 | 0 |
| 14002 | 5 | `_project_image_key_for_path` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 14008 | 7 | `_vlm_part_list_text` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 14016 | 18 | `_vlm_part_coverage` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 14035 | 15 | `_log_vlm_part_coverage` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 14051 | 2 | `run_vlm_preannotation_current` | vlm_prediction_export | 7 | signal_compatibility | 0 | 0 | 1 |
| 14054 | 2 | `run_vlm_preannotation_batch` | vlm_prediction_export | 7 | signal_compatibility | 0 | 0 | 1 |
| 14057 | 121 | `run_vlm_preannotation_from_settings` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 14179 | 42 | `request_stop_vlm_preannotation` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 14222 | 11 | `_active_vlm_preannotation_threads` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 14234 | 14 | `_start_vlm_preannotation_workers` | runtime_worker | 1 | test_compatibility | 0 | 1 | 0 |
| 14249 | 53 | `_start_next_vlm_preannotation_image` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 14303 | 48 | `_apply_vlm_candidate` | vlm_prediction_export | 7 | test_compatibility | 0 | 5 | 0 |
| 14352 | 6 | `_refresh_vlm_canvas_if_current` | vlm_prediction_export | 7 | test_compatibility | 0 | 3 | 0 |
| 14359 | 34 | `_reload_current_image_for_workbench` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 14394 | 111 | `_on_vlm_preannotation_image_result` | vlm_prediction_export | 7 | signal_compatibility | 0 | 6 | 1 |
| 14506 | 7 | `_vlm_progress_image_key` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 14514 | 20 | `_mark_current_vlm_image_done` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 14535 | 30 | `_set_vlm_progress_ui` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 14566 | 54 | `_create_vlm_progress_dialog` | vlm_prediction_export | 7 | test_compatibility | 0 | 2 | 0 |
| 14621 | 18 | `_advance_vlm_progress` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 14640 | 11 | `_on_vlm_preannotation_thread_step` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 14652 | 7 | `_complete_current_vlm_image_steps` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 14660 | 100 | `_finish_vlm_preannotation_run` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 14761 | 36 | `accept_current_image_ai_drafts` | vlm_prediction_export | 7 | signal_compatibility | 0 | 3 | 1 |
| 14798 | 93 | `accept_batch_ai_drafts` | vlm_prediction_export | 7 | signal_compatibility | 0 | 1 | 1 |
| 14892 | 3 | `_on_vlm_preannotation_error` | vlm_prediction_export | 7 | signal_compatibility | 0 | 0 | 1 |
| 14896 | 33 | `_on_vlm_preannotation_qthread_finished` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 14930 | 2 | `_on_vlm_preannotation_finished` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 14933 | 46 | `run_prediction` | vlm_prediction_export | 7 | public_or_source_compatibility | 1 | 2 | 1 |
| 14980 | 30 | `run_external_prediction` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 15011 | 9 | `verify_current_image` | image_navigation | 5 | signal_compatibility | 0 | 1 | 1 |
| 15021 | 100 | `_start_external_batch_inference` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 15122 | 74 | `run_batch_inference` | runtime_worker | 1 | signal_compatibility | 0 | 1 | 1 |
| 15197 | 8 | `export_dataset` | runtime_worker | 1 | signal_compatibility | 0 | 0 | 1 |
| 15206 | 75 | `_start_dataset_export` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 15282 | 23 | `init_sam` | annotation_sam | 6 | test_compatibility | 0 | 1 | 0 |
| 15306 | 13 | `ensure_sam_preloaded` | annotation_sam | 6 | test_compatibility | 0 | 6 | 0 |
| 15320 | 4 | `ensure_2d_stl_models_preloaded` | training_model | 7 | test_compatibility | 0 | 3 | 0 |
| 15325 | 17 | `ensure_locator_preloaded` | training_model | 7 | test_compatibility | 0 | 1 | 0 |
| 15343 | 22 | `_preload_engine_parts_model_async` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 15366 | 2 | `log` | unclassified | 8 | public_or_source_compatibility | 177 | 34 | 5 |

## MainWindow State Fields

| Field | Assignments | Lines | Target owner | Stage |
| --- | --- | --- | --- | --- |
| `_image_list_state_cache` | 6 | 5981, 7964, 11790, 11753, 11617, 11635 | TBD | TBD |
| `_refreshing_part_tree` | 2 | 9855, 9914 | TBD | TBD |
| `_suppress_selection_save_flush` | 4 | 11950, 11937, 11957, 11944 | TBD | TBD |
| `_updating_blink_parent_context` | 2 | 10405, 10438 | TBD | TBD |
| `active_project_entry_path` | 8 | 5900, 6537, 8898, 8987, 9348, 8874, 9356, 9370 | TBD | TBD |
| `active_project_kind` | 13 | 5898, 6538, 6887, 7433, 7461, 7497, 7507, 8896, 8985, 9346, 8872, 9354, 9368 | TBD | TBD |
| `active_project_source_kind` | 7 | 5899, 8897, 8986, 9347, 8873, 9355, 9369 | TBD | TBD |
| `active_training_kind` | 3 | 5968, 13387, 8433 | TBD | TBD |
| `active_training_label` | 2 | 5969, 8435 | TBD | TBD |
| `agent_panel` | 1 | 6608 | TBD | TBD |
| `ai_action_panel` | 1 | 6327 | TBD | TBD |
| `ai_model_panel` | 1 | 6277 | TBD | TBD |
| `ai_panel` | 1 | 6254 | TBD | TBD |
| `blink_auto_shrink_steps` | 2 | 5910, 10541 | TBD | TBD |
| `blink_context_status_label` | 1 | 6194 | TBD | TBD |
| `blink_lab` | 1 | 6514 | TBD | TBD |
| `blink_refine_panel` | 1 | 6389 | TBD | TBD |
| `blink_train_batch` | 2 | 5906, 10537 | TBD | TBD |
| `blink_train_epochs` | 2 | 5905, 10537 | TBD | TBD |
| `blink_train_input_size` | 2 | 5909, 10540 | TBD | TBD |
| `blink_train_lr` | 2 | 5907, 10538 | TBD | TBD |
| `blink_train_weight_decay` | 2 | 5908, 10539 | TBD | TBD |
| `blink_training_strategy` | 2 | 5911, 10542 | TBD | TBD |
| `btn_accept_batch_ai_drafts` | 1 | 6347 | TBD | TBD |
| `btn_accept_current_ai_drafts` | 1 | 6343 | TBD | TBD |
| `btn_add` | 1 | 6081 | TBD | TBD |
| `btn_add_part` | 1 | 6200 | TBD | TBD |
| `btn_agent_from_workbench` | 1 | 6014 | TBD | TBD |
| `btn_batch` | 1 | 6338 | TBD | TBD |
| `btn_batch_split_panels` | 1 | 6004 | TBD | TBD |
| `btn_blink_auto_annotate` | 1 | 6423 | TBD | TBD |
| `btn_blink_auto_shrink` | 1 | 6430 | TBD | TBD |
| `btn_blink_batch_auto_shrink` | 1 | 6434 | TBD | TBD |
| `btn_blink_entry` | 1 | 6007 | TBD | TBD |
| `btn_blink_stop_training` | 1 | 6446 | TBD | TBD |
| `btn_blink_train_expert` | 1 | 6442 | TBD | TBD |
| `btn_clear_ai` | 1 | 6382 | TBD | TBD |
| `btn_configure_route_expert` | 1 | 6419 | TBD | TBD |
| `btn_continue_last` | 1 | 6731 | TBD | TBD |
| `btn_crop` | 1 | 6001 | TBD | TBD |
| `btn_del_locator` | 1 | 6294 | TBD | TBD |
| `btn_del_part` | 1 | 6206 | TBD | TBD |
| `btn_del_segmenter` | 1 | 6314 | TBD | TBD |
| `btn_export` | 1 | 5998 | TBD | TBD |
| `btn_general_settings` | 1 | 6737 | TBD | TBD |
| `btn_literature_descriptions` | 1 | 6238 | TBD | TBD |
| `btn_note_locator` | 1 | 6298 | TBD | TBD |
| `btn_note_segmenter` | 1 | 6318 | TBD | TBD |
| `btn_open_any` | 1 | 6734 | TBD | TBD |
| `btn_predict` | 1 | 6334 | TBD | TBD |
| `btn_rename_part` | 1 | 6203 | TBD | TBD |
| `btn_start_ant_code` | 1 | 6643 | TBD | TBD |
| `btn_start_center_from_workbench` | 1 | 6010 | TBD | TBD |
| `btn_start_console_toggle` | 1 | 6771 | TBD | TBD |
| `btn_stop_ant_code` | 1 | 6646 | TBD | TBD |
| `btn_stop_training` | 1 | 6376 | TBD | TBD |
| `btn_train` | 1 | 6372 | TBD | TBD |
| `btn_training_results` | 1 | 6467 | TBD | TBD |
| `btn_vlm_preannotate_batch` | 1 | 6022 | TBD | TBD |
| `btn_vlm_preannotate_current` | 1 | 6018 | TBD | TBD |
| `canvas` | 1 | 6134 | TBD | TBD |
| `canvas_shell` | 1 | 6141 | TBD | TBD |
| `check_lock_parent_box_ratio` | 1 | 6415 | TBD | TBD |
| `check_morpho` | 1 | 6214 | TBD | TBD |
| `child_training_cancel_requested` | 5 | 5967, 8475, 8486, 13105, 13147 | TBD | TBD |
| `child_training_failed` | 5 | 5966, 8464, 8471, 8485, 13104 | TBD | TBD |
| `chk_train_locator_only` | 1 | 6351 | TBD | TBD |
| `combo_blink_parent_context` | 1 | 6404 | TBD | TBD |
| `combo_locator` | 1 | 6288 | TBD | TBD |
| `combo_segmenter` | 1 | 6308 | TBD | TBD |
| `combo_training_scope` | 1 | 6365 | TBD | TBD |
| `config` | 1 | 5888 | TBD | TBD |
| `current_blink_context` | 2 | 5970, 9796 | TBD | TBD |
| `current_image` | 8 | 5930, 7971, 14365, 9449, 12165, 12848, 12851, 11614 | TBD | TBD |
| `current_lang` | 2 | 5889, 10642 | TBD | TBD |
| `current_theme` | 2 | 5890, 10657 | TBD | TBD |
| `dataset_export_thread` | 2 | 15231, 15274 | TBD | TBD |
| `db` | 1 | 5901 | TBD | TBD |
| `desc_box` | 1 | 6248 | TBD | TBD |
| `description_header_panel` | 1 | 6233 | TBD | TBD |
| `engine` | 1 | 5924 | TBD | TBD |
| `external_backend_config` | 2 | 5918, 10552 | TBD | TBD |
| `external_batch_inference_failed` | 3 | 5942, 15031, 15090 | TBD | TBD |
| `external_batch_inference_progress_dialog` | 3 | 5941, 15051, 15104 | TBD | TBD |
| `external_batch_inference_saved_any` | 3 | 5943, 15032, 15086 | TBD | TBD |
| `external_batch_inference_thread` | 3 | 5940, 15063, 15106 | TBD | TBD |
| `external_training_failed` | 3 | 5945, 13386, 13400 | TBD | TBD |
| `external_training_thread` | 3 | 5944, 13392, 13409 | TBD | TBD |
| `file_list` | 1 | 6072 | TBD | TBD |
| `genus_combo` | 1 | 6179 | TBD | TBD |
| `group_morpho` | 1 | 6217 | TBD | TBD |
| `image_import_progress_dialog` | 3 | 5939, 10804, 10847 | TBD | TBD |
| `image_import_thread` | 3 | 5938, 10807, 10851 | TBD | TBD |
| `image_list_group_collapsed` | 1 | 5976 | TBD | TBD |
| `image_taxon_panel` | 1 | 6225 | TBD | TBD |
| `inf_adapt` | 2 | 5920, 10546 | TBD | TBD |
| `inf_conf` | 2 | 5919, 10546 | TBD | TBD |
| `inf_noise_floor` | 2 | 5922, 10547 | TBD | TBD |
| `inf_pad` | 2 | 5921, 10547 | TBD | TBD |
| `inf_poly_epsilon` | 2 | 5923, 10548 | TBD | TBD |
| `inf_thread` | 2 | 5931, 15158 | TBD | TBD |
| `label_ai_workflow` | 1 | 6259 | TBD | TBD |
| `label_blink_expert` | 1 | 6411 | TBD | TBD |
| `label_blink_parent_box` | 1 | 6407 | TBD | TBD |
| `label_blink_parent_context` | 1 | 6401 | TBD | TBD |
| `label_blink_refine` | 1 | 6394 | TBD | TBD |
| `label_blink_route` | 1 | 6397 | TBD | TBD |
| `label_description` | 1 | 6243 | TBD | TBD |
| `label_logs` | 1 | 6490 | TBD | TBD |
| `label_measurements` | 1 | 6221 | TBD | TBD |
| `label_model_backend` | 1 | 6263 | TBD | TBD |
| `label_parent_annotation` | 1 | 6272 | TBD | TBD |
| `label_project_images` | 1 | 6069 | TBD | TBD |
| `label_structures` | 1 | 6183 | TBD | TBD |
| `label_taxonomy` | 1 | 6177 | TBD | TBD |
| `label_training_progress` | 1 | 6462 | TBD | TBD |
| `label_training_progress_status` | 1 | 6473 | TBD | TBD |
| `last_confirmed_locator_timestamp` | 4 | 5961, 8372, 8758, 8751 | TBD | TBD |
| `lbl_locator` | 1 | 6286 | TBD | TBD |
| `lbl_segmenter` | 1 | 6306 | TBD | TBD |
| `lbl_training_scope` | 1 | 6362 | TBD | TBD |
| `locator_preload_thread` | 1 | 5947 | TBD | TBD |
| `log_console` | 1 | 6493 | TBD | TBD |
| `logs_panel` | 1 | 6485 | TBD | TBD |
| `metadata_panel` | 1 | 6172 | TBD | TBD |
| `model_backend` | 2 | 5917, 10551 | TBD | TBD |
| `parent_annotation_panel` | 1 | 6267 | TBD | TBD |
| `parent_box_aspect_ratios` | 3 | 5982, 9737, 10567 | TBD | TBD |
| `parent_training_cancel_requested` | 3 | 5965, 8536, 8650 | TBD | TBD |
| `parent_training_failed` | 4 | 5964, 8535, 8611, 8628 | TBD | TBD |
| `part_list` | 1 | 6186 | TBD | TBD |
| `parts_model_preload_thread` | 2 | 5948, 15358 | TBD | TBD |
| `pdf_widget` | 1 | 6508 | TBD | TBD |
| `pending_sam_description` | 4 | 5937, 12711, 13179, 13187 | TBD | TBD |
| `pending_sam_image` | 4 | 5936, 12710, 13178, 13186 | TBD | TBD |
| `pending_sam_part` | 4 | 5935, 12709, 13177, 13185 | TBD | TBD |
| `pending_training_preflight` | 2 | 5962, 8523 | TBD | TBD |
| `progress` | 1 | 6478 | TBD | TBD |
| `project` | 1 | 5894 | TBD | TBD |
| `project_autosave_delay_ms` | 2 | 5953, 10459 | TBD | TBD |
| `project_last_image_switch_at` | 2 | 5955, 7707 | TBD | TBD |
| `project_save_context` | 4 | 5957, 7762, 7701, 7716 | TBD | TBD |
| `project_save_navigation_idle_ms` | 1 | 5954 | TBD | TBD |
| `project_save_pending` | 4 | 5956, 7699, 7761, 7715 | TBD | TBD |
| `project_save_timer` | 1 | 5958 | TBD | TBD |
| `radio_annotation_box` | 1 | 6115 | TBD | TBD |
| `radio_box` | 1 | 6110 | TBD | TBD |
| `radio_draw` | 1 | 6099 | TBD | TBD |
| `radio_loose_shrink_box` | 1 | 6120 | TBD | TBD |
| `radio_magic` | 1 | 6105 | TBD | TBD |
| `radio_scale` | 1 | 6125 | TBD | TBD |
| `route_settings_panel` | 1 | 6531 | TBD | TBD |
| `runtime_device` | 3 | 5916, 10464, 10550 | TBD | TBD |
| `sam_busy` | 4 | 5934, 12708, 13176, 13184 | TBD | TBD |
| `sam_thread` | 2 | 5932, 15289 | TBD | TBD |
| `sam_worker` | 2 | 5933, 15291 | TBD | TBD |
| `shortcut_redo` | 1 | 6152 | TBD | TBD |
| `shortcut_save` | 1 | 6154 | TBD | TBD |
| `shortcut_undo` | 1 | 6150 | TBD | TBD |
| `shortcut_verify` | 1 | 6156 | TBD | TBD |
| `start_agent_status_label` | 1 | 6635 | TBD | TBD |
| `start_center_widget` | 1 | 5990 | TBD | TBD |
| `start_console_agent_label` | 1 | 6808 | TBD | TBD |
| `start_console_agent_value` | 1 | 6808 | TBD | TBD |
| `start_console_body` | 1 | 6778 | TBD | TBD |
| `start_console_expanded` | 2 | 6819, 6824 | TBD | TBD |
| `start_console_images_label` | 1 | 6795 | TBD | TBD |
| `start_console_images_value` | 1 | 6795 | TBD | TBD |
| `start_console_panel` | 1 | 6678 | TBD | TBD |
| `start_console_pdf_label` | 1 | 6805 | TBD | TBD |
| `start_console_pdf_value` | 1 | 6805 | TBD | TBD |
| `start_console_project_label` | 1 | 6792 | TBD | TBD |
| `start_console_project_value` | 1 | 6792 | TBD | TBD |
| `start_console_stl_note` | 1 | 6814 | TBD | TBD |
| `start_console_summary` | 1 | 6760 | TBD | TBD |
| `start_console_tif_label` | 2 | 6799, 6803 | TBD | TBD |
| `start_console_tif_value` | 2 | 6799, 6804 | TBD | TBD |
| `start_console_title` | 1 | 6758 | TBD | TBD |
| `start_console_workflow_label` | 1 | 6789 | TBD | TBD |
| `start_console_workflow_value` | 1 | 6789 | TBD | TBD |
| `start_image_card` | 1 | 6682 | TBD | TBD |
| `start_pdf_card` | 1 | 6702 | TBD | TBD |
| `start_quick_panel` | 1 | 6680 | TBD | TBD |
| `start_recent_label` | 1 | 6727 | TBD | TBD |
| `start_subtitle` | 1 | 6623 | TBD | TBD |
| `start_tif_card` | 2 | 6691, 6693 | TBD | TBD |
| `start_title` | 1 | 6621 | TBD | TBD |
| `startup_size` | 1 | 5886 | TBD | TBD |
| `stl_project` | 1 | 5897 | TBD | TBD |
| `tabs` | 1 | 5988 | TBD | TBD |
| `tif_project` | 1 | 5896 | TBD | TBD |
| `tif_workbench` | 1 | 6511 | TBD | TBD |
| `tif_workflow_enabled` | 1 | 5893 | TBD | TBD |
| `tool_group` | 1 | 6098 | TBD | TBD |
| `tool_strip` | 1 | 6093 | TBD | TBD |
| `toolbar_flow_panel` | 1 | 6042 | TBD | TBD |
| `toolbar_project_panel` | 1 | 6033 | TBD | TBD |
| `train_batch` | 2 | 5904, 10536 | TBD | TBD |
| `train_epochs` | 2 | 5903, 10536 | TBD | TBD |
| `train_lr` | 2 | 5914, 10545 | TBD | TBD |
| `train_wd` | 2 | 5915, 10545 | TBD | TBD |
| `trainer` | 3 | 5946, 8541, 8602 | TBD | TBD |
| `training_progress_panel` | 1 | 6454 | TBD | TBD |
| `training_retry_requested` | 4 | 5963, 8534, 8610, 8619 | TBD | TBD |
| `vlm_preannotation_active_images` | 3 | 14157, 14757, 14284 | TBD | TBD |
| `vlm_preannotation_api_config` | 2 | 14138, 14162 | TBD | TBD |
| `vlm_preannotation_artifacts_dir` | 1 | 14161 | TBD | TBD |
| `vlm_preannotation_cancel_requested` | 4 | 5974, 14149, 14199, 14753 | TBD | TBD |
| `vlm_preannotation_cancelled_queued_images` | 4 | 5975, 14150, 14200, 14754 | TBD | TBD |
| `vlm_preannotation_completed_image_keys` | 3 | 14159, 14523, 14759 | TBD | TBD |
| `vlm_preannotation_completed_images` | 2 | 14155, 14525 | TBD | TBD |
| `vlm_preannotation_completed_steps` | 2 | 14153, 14624 | TBD | TBD |
| `vlm_preannotation_concurrency` | 1 | 14151 | TBD | TBD |
| `vlm_preannotation_current_image` | 4 | 14156, 14258, 14530, 14626 | TBD | TBD |
| `vlm_preannotation_current_image_steps_completed` | 3 | 14257, 14633, 14636 | TBD | TBD |
| `vlm_preannotation_image_step_counts` | 4 | 14158, 14758, 14288, 14631 | TBD | TBD |
| `vlm_preannotation_progress_bar` | 2 | 14617, 14751 | TBD | TBD |
| `vlm_preannotation_progress_dialog` | 3 | 5973, 14612, 14746 | TBD | TBD |
| `vlm_preannotation_progress_label` | 2 | 14615, 14749 | TBD | TBD |
| `vlm_preannotation_progress_notice_label` | 2 | 14614, 14748 | TBD | TBD |
| `vlm_preannotation_progress_path_label` | 2 | 14616, 14750 | TBD | TBD |
| `vlm_preannotation_progress_title_label` | 2 | 14613, 14747 | TBD | TBD |
| `vlm_preannotation_prompt_profile` | 1 | 14163 | TBD | TBD |
| `vlm_preannotation_queue` | 4 | 14146, 14201, 14256, 14920 | TBD | TBD |
| `vlm_preannotation_records` | 1 | 14145 | TBD | TBD |
| `vlm_preannotation_run_active` | 2 | 14148, 14720 | TBD | TBD |
| `vlm_preannotation_run_id` | 1 | 14144 | TBD | TBD |
| `vlm_preannotation_saved_total` | 2 | 14143, 14454 | TBD | TBD |
| `vlm_preannotation_stop_button` | 2 | 14618, 14752 | TBD | TBD |
| `vlm_preannotation_target_parts` | 1 | 14160 | TBD | TBD |
| `vlm_preannotation_thread` | 5 | 5971, 14231, 14247, 14280, 14756 | TBD | TBD |
| `vlm_preannotation_threads` | 6 | 5972, 14147, 14230, 14246, 14755, 14905 | TBD | TBD |
| `vlm_preannotation_total_images` | 1 | 14154 | TBD | TBD |
| `vlm_preannotation_total_steps` | 1 | 14152 | TBD | TBD |
| `workbench_inspector_scroll` | 1 | 6159 | TBD | TBD |
| `workbench_splitter` | 1 | 6058 | TBD | TBD |
| `workbench_top_bar` | 1 | 6027 | TBD | TBD |
| `workbench_widget` | 1 | 5992 | TBD | TBD |

## Main Import Compatibility

| File | Line | Import |
| --- | --- | --- |
| scripts/benchmark_main_window_workflows.py | 198 | `import AntSleap.main as main_module` |
| tests/test_blink_bridge.py | 22 | `import main as main_module` |
| tests/test_blink_bridge.py | 23 | `from main import BlinkEntryDialog, MainWindow` |
| tests/test_gui_smoke.py | 45 | `import AntSleap.main as main_module` |
| tests/test_main_window_stage1_modules.py | 55 | `import AntSleap.main as main_module` |
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
