# TaxaMask Round 4 Main Window Method Inventory

由 `scripts/analyze_main_window_architecture.py` 生成。Stage 0 冻结当前责任、兼容入口和目标阶段，实施时必须结合真实调用复核。

## Metrics

| Metric | Value |
| --- | --- |
| main_physical_lines | 9985 |
| top_level_class_count | 1 |
| top_level_function_count | 0 |
| all_method_count | 390 |
| private_method_count | 279 |
| connection_count | 128 |
| source_state_assignment_lines | 396 |
| main_window_lines | 9489 |
| main_window_method_count | 390 |
| main_window_connection_count | 128 |
| main_window_init_lines | 668 |
| main_window_methods_ge_50 | 42 |
| main_window_methods_ge_100 | 11 |
| main_window_unique_state_fields | 238 |
| main_window_state_assignment_occurrences | 418 |
| main_import_site_count | 18 |
| key_test_reference_line_count | 324 |
| key_test_private_reference_occurrences | 142 |
| key_test_unique_private_references | 51 |
| async_entry_count | 16 |

## Top-level Classes

| Line | Size | Class | Methods | Connects | Refs | Stage |
| --- | --- | --- | --- | --- | --- | --- |
| 475 | 9489 | `MainWindow` | 390 | 128 | 32 | 3 |

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
| internal_or_unreferenced | 224 |
| public_or_source_compatibility | 46 |
| signal_compatibility | 55 |
| test_compatibility | 65 |

## MainWindow Methods

| Line | Size | Method | Workflow | Stage | Compatibility | Source refs | Test refs | Signal refs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 479 | 668 | `__init__` | unclassified | 8 | public_or_source_compatibility | 215 | 131 | 0 |
| 1148 | 2 | `_is_tif_workflow_enabled` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 1151 | 9 | `_show_tif_workflow_unavailable` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 1161 | 10 | `_apply_window_icon` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 1172 | 18 | `apply_startup_window_geometry` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 1191 | 124 | `_build_start_center` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 1316 | 25 | `_build_start_quick_panel` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 1342 | 76 | `_build_project_console` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 1419 | 3 | `_toggle_start_project_console` | shell_start_agent | 3 | signal_compatibility | 0 | 0 | 1 |
| 1423 | 12 | `_update_start_project_console_collapsed_state` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 1436 | 12 | `_build_project_console_row` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 1449 | 32 | `_build_workflow_card` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 1482 | 4 | `_show_start_center` | shell_start_agent | 3 | test_compatibility | 0 | 2 | 0 |
| 1487 | 48 | `_update_start_center_texts` | shell_start_agent | 3 | test_compatibility | 0 | 1 | 0 |
| 1536 | 3 | `_handle_agent_dashboard_status_changed` | shell_start_agent | 3 | signal_compatibility | 0 | 0 | 1 |
| 1540 | 11 | `_update_start_agent_status` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 1552 | 45 | `_refresh_project_console` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 1598 | 8 | `_start_console_collapsed_summary` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 1607 | 22 | `_start_console_project_summary` | shell_start_agent | 3 | test_compatibility | 0 | 1 | 0 |
| 1630 | 13 | `_compact_project_path` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 1644 | 19 | `_start_console_image_summary` | shell_start_agent | 3 | test_compatibility | 0 | 1 | 0 |
| 1664 | 22 | `_start_console_tif_summary` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 1687 | 14 | `_start_console_pdf_summary` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 1702 | 5 | `_is_pdf_candidate_provenance` | pdf_evidence | 5 | test_compatibility | 0 | 1 | 0 |
| 1708 | 5 | `_start_console_agent_status` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 1714 | 7 | `_agent_current_workflow_label` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 1722 | 8 | `_agent_current_project_label` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 1737 | 7 | `_recent_text_excerpt` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 1745 | 5 | `_agent_context_text` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 1751 | 202 | `_compact_agent_context` | shell_start_agent | 3 | public_or_source_compatibility | 1 | 5 | 0 |
| 1954 | 27 | `_collect_image_workbench_agent_context` | shell_start_agent | 3 | public_or_source_compatibility | 1 | 4 | 0 |
| 1982 | 13 | `_collect_blink_agent_context` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 1996 | 30 | `_pdf_agent_prompt` | shell_start_agent | 3 | test_compatibility | 0 | 1 | 0 |
| 2027 | 15 | `open_agent_for_pdf_workflow` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 2043 | 27 | `open_agent_from_context` | shell_start_agent | 3 | public_or_source_compatibility | 2 | 3 | 6 |
| 2071 | 2 | `return_to_start_center_with_context` | shell_start_agent | 3 | public_or_source_compatibility | 1 | 1 | 4 |
| 2074 | 8 | `_open_workflow_from_agent` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 2083 | 8 | `_open_model_settings_from_agent` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 2092 | 6 | `enter_image_workflow` | shell_start_agent | 3 | public_or_source_compatibility | 3 | 9 | 0 |
| 2099 | 8 | `enter_tif_workflow` | shell_start_agent | 3 | public_or_source_compatibility | 2 | 1 | 0 |
| 2108 | 2 | `_default_outputs_root` | unclassified | 8 | public_or_source_compatibility | 3 | 2 | 0 |
| 2111 | 4 | `_ensure_default_output_subdir` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 2116 | 2 | `_default_2d_stl_projects_root` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 2119 | 2 | `_default_tif_projects_root` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 2122 | 2 | `_default_startup_project_dir` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 2125 | 2 | `_startup_project_manifest_path` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 2128 | 2 | `_startup_legacy_json_project_path` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 2131 | 14 | `_open_or_create_startup_project` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 2146 | 4 | `_default_project_dialog_dir` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 2151 | 5 | `_current_2d_project_dir` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 2157 | 4 | `_default_2d_export_dir` | runtime_worker | 1 | test_compatibility | 0 | 2 | 0 |
| 2162 | 4 | `_default_vlm_preannotation_dir` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 2167 | 18 | `_default_open_project_dir` | project_lifecycle | 4 | test_compatibility | 0 | 1 | 0 |
| 2186 | 8 | `_path_is_startup_project` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 2195 | 5 | `_path_is_inside_program_package` | unclassified | 8 | public_or_source_compatibility | 3 | 0 | 0 |
| 2201 | 8 | `open_last_project` | project_lifecycle | 4 | signal_compatibility | 0 | 1 | 1 |
| 2210 | 45 | `closeEvent` | project_lifecycle | 4 | public_or_source_compatibility | 13 | 0 | 0 |
| 2256 | 10 | `_active_recent_project_path` | project_lifecycle | 4 | test_compatibility | 0 | 1 | 0 |
| 2267 | 22 | `_shutdown_background_workers` | runtime_worker | 1 | public_or_source_compatibility | 1 | 0 | 0 |
| 2290 | 3 | `destroy` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 2294 | 5 | `_schedule_project_save` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 2300 | 5 | `_defer_project_save_for_active_navigation` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 2306 | 54 | `_flush_pending_project_save` | project_lifecycle | 4 | signal_compatibility | 0 | 3 | 1 |
| 2361 | 51 | `refresh_model_list` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 2413 | 5 | `_selected_locator_timestamp` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 2419 | 4 | `_selected_locator_display_text` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 2424 | 9 | `_parent_model_filename` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 2434 | 40 | `_build_locator_combo_label` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 2475 | 7 | `_build_segmenter_combo_label` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 2483 | 5 | `_selected_segmenter_timestamp` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 2489 | 2 | `_active_project_route_manifest` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 2492 | 9 | `_active_model_profile_context` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 2502 | 6 | `_active_external_backend_config` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 2509 | 5 | `_selected_route_entry` | dialog_settings | 2 | public_or_source_compatibility | 7 | 0 | 0 |
| 2515 | 5 | `_route_runtime_status` | runtime_worker | 1 | public_or_source_compatibility | 2 | 0 | 0 |
| 2521 | 8 | `refresh_route_table` | dialog_settings | 2 | public_or_source_compatibility | 9 | 30 | 1 |
| 2530 | 4 | `update_route_action_buttons` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 2535 | 16 | `_refresh_project_bound_views` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 2552 | 5 | `_project_image_count` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 2558 | 17 | `_prepare_image_list_for_project_open` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 2576 | 12 | `_preload_2d_stl_models_after_open` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 2589 | 5 | `_ensure_tab_visible` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 2595 | 6 | `_remove_tab_if_present` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 2602 | 23 | `_apply_project_mode_tabs` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 2626 | 13 | `_is_tif_project_file` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 2640 | 11 | `_is_stl_project_file` | project_lifecycle | 4 | test_compatibility | 0 | 1 | 0 |
| 2652 | 7 | `_read_project_probe_payload` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 2660 | 6 | `_is_sqlite_project_manifest_payload` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 2667 | 2 | `_is_tif_sqlite_project_manifest_payload` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 2670 | 2 | `_is_2d_sqlite_project_manifest_payload` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 2673 | 15 | `_is_legacy_2d_json_project_payload` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 2689 | 2 | `_is_legacy_2d_json_project_file` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 2692 | 23 | `_candidate_manifest_paths_for_sqlite_database` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 2716 | 15 | `_manifest_for_sqlite_database_file` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 2732 | 3 | `_is_project_sqlite_database_file` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 2736 | 11 | `_active_sqlite_project_manager` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 2748 | 9 | `_flush_active_sqlite_project_before_maintenance` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 2758 | 6 | `_sqlite_maintenance_default_dir` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 2765 | 42 | `backup_current_sqlite_project` | project_lifecycle | 4 | test_compatibility | 0 | 1 | 0 |
| 2808 | 42 | `export_current_project_legacy_json` | runtime_worker | 1 | test_compatibility | 0 | 1 | 0 |
| 2851 | 23 | `open_current_sqlite_migration_report` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 2875 | 4 | `appoint_selected_route_expert` | blink | 6 | public_or_source_compatibility | 2 | 1 | 0 |
| 2880 | 4 | `toggle_selected_route_enabled` | dialog_settings | 2 | public_or_source_compatibility | 2 | 0 | 0 |
| 2885 | 4 | `delete_selected_route` | dialog_settings | 2 | public_or_source_compatibility | 2 | 2 | 0 |
| 2890 | 30 | `_log_route_usage_summary` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 2921 | 4 | `_locator_model_path` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 2926 | 4 | `_segmenter_model_path` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 2931 | 18 | `_apply_locator_selection_to_runtime` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 2950 | 2 | `_locator_selection_needs_legacy_confirmation` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 2953 | 20 | `_confirm_legacy_locator_selection_if_needed` | training_model | 7 | test_compatibility | 0 | 1 | 0 |
| 2974 | 5 | `_show_structured_training_preflight` | dialog_settings | 2 | test_compatibility | 0 | 1 | 0 |
| 2980 | 3 | `_is_locator_oom_error` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 2984 | 30 | `_ask_locator_oom_retry_resolution` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 3015 | 3 | `_is_parent_training_running` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 3019 | 4 | `_is_child_training_running` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 3024 | 2 | `_is_any_training_running` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 3027 | 19 | `_set_training_progress` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 3047 | 11 | `_connect_child_training_progress` | blink | 6 | test_compatibility | 0 | 1 | 0 |
| 3059 | 6 | `_on_child_training_result` | blink | 6 | signal_compatibility | 0 | 0 | 1 |
| 3066 | 3 | `_on_child_training_error` | blink | 6 | signal_compatibility | 0 | 0 | 1 |
| 3070 | 3 | `_on_child_training_cancelled` | blink | 6 | signal_compatibility | 0 | 0 | 1 |
| 3074 | 10 | `_on_child_training_finished` | blink | 6 | signal_compatibility | 0 | 0 | 1 |
| 3085 | 87 | `_launch_training_with_preflight` | dialog_settings | 2 | test_compatibility | 0 | 1 | 0 |
| 3173 | 15 | `_on_training_success` | training_model | 7 | signal_compatibility | 0 | 1 | 1 |
| 3189 | 13 | `_on_training_finished` | training_model | 7 | public_or_source_compatibility | 2 | 1 | 1 |
| 3203 | 38 | `_on_training_error` | training_model | 7 | public_or_source_compatibility | 2 | 0 | 1 |
| 3242 | 7 | `stop_training` | training_model | 7 | signal_compatibility | 0 | 0 | 1 |
| 3250 | 21 | `_apply_segmenter_selection_to_runtime` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 3272 | 12 | `update_model_delete_button_states` | training_model | 7 | signal_compatibility | 0 | 0 | 2 |
| 3285 | 33 | `_edit_parent_model_note` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 3319 | 2 | `edit_locator_model_note` | training_model | 7 | signal_compatibility | 0 | 1 | 1 |
| 3322 | 2 | `edit_segmenter_model_note` | training_model | 7 | signal_compatibility | 0 | 1 | 1 |
| 3325 | 36 | `on_locator_changed` | training_model | 7 | signal_compatibility | 0 | 1 | 1 |
| 3362 | 26 | `delete_locator_model` | training_model | 7 | signal_compatibility | 0 | 2 | 1 |
| 3389 | 3 | `on_segmenter_changed` | training_model | 7 | signal_compatibility | 0 | 0 | 1 |
| 3393 | 26 | `delete_segmenter_model` | training_model | 7 | signal_compatibility | 0 | 1 | 1 |
| 3420 | 3 | `on_model_changed` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 3424 | 29 | `create_menus` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 3454 | 21 | `new_project` | project_lifecycle | 4 | test_compatibility | 0 | 1 | 0 |
| 3476 | 22 | `new_tif_project` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 3499 | 9 | `_ensure_tif_project_open` | project_lifecycle | 4 | public_or_source_compatibility | 6 | 0 | 0 |
| 3509 | 29 | `import_tif_stack_action` | tif_integration | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 3539 | 28 | `import_amira_directory_action` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 3568 | 28 | `import_stl_rendered_views_action` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 3597 | 5 | `open_pdf_evidence_tools` | project_lifecycle | 4 | test_compatibility | 0 | 2 | 0 |
| 3603 | 41 | `open_pdf_multimodal_api_settings` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 3645 | 19 | `_choose_project_template` | project_lifecycle | 4 | test_compatibility | 0 | 1 | 0 |
| 3665 | 12 | `open_project` | project_lifecycle | 4 | public_or_source_compatibility | 2 | 1 | 1 |
| 3678 | 12 | `_confirm_legacy_2d_json_migration` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 3691 | 9 | `_existing_sqlite_manifest_for_legacy_json` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 3701 | 11 | `_confirm_open_existing_sqlite_migration` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 3713 | 12 | `_confirm_legacy_tif_json_migration` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 3726 | 11 | `_existing_tif_sqlite_manifest_for_legacy_json` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 3738 | 11 | `_confirm_open_existing_tif_sqlite_migration` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 3750 | 41 | `_migrate_legacy_2d_project_with_progress` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 3792 | 41 | `_migrate_legacy_tif_project_with_progress` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 3834 | 150 | `open_project_path` | project_lifecycle | 4 | public_or_source_compatibility | 2 | 14 | 0 |
| 3985 | 10 | `_format_relocation_preview` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 3996 | 54 | `check_relocate_project_images` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 4051 | 6 | `_part_item_name` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 4058 | 2 | `_current_part_name` | unclassified | 8 | test_compatibility | 0 | 5 | 0 |
| 4061 | 15 | `_workbench_parent_parts` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 4077 | 3 | `_is_parent_part` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 4081 | 23 | `_part_tree_parent_for` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 4105 | 18 | `_route_parents_for_child` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 4124 | 25 | `_resolve_child_parent` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 4150 | 15 | `_parent_context_box` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 4166 | 5 | `_current_shrink_loose_boxes` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 4172 | 28 | `_auto_boxes_for_canvas` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 4201 | 10 | `_refresh_current_canvas_boxes` | annotation_sam | 6 | test_compatibility | 0 | 1 | 0 |
| 4212 | 15 | `_route_entry_for_context` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 4228 | 26 | `_route_expert_status` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 4255 | 73 | `_current_blink_context` | blink | 6 | public_or_source_compatibility | 1 | 0 | 0 |
| 4329 | 10 | `_parent_box_aspect_ratio` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 4340 | 24 | `_parent_context_options` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 4365 | 15 | `_refresh_annotation_box_constraints` | annotation_sam | 6 | signal_compatibility | 0 | 0 | 1 |
| 4381 | 8 | `_active_box_tool_role` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 4390 | 6 | `_refresh_blink_refine_state` | blink | 6 | public_or_source_compatibility | 1 | 9 | 0 |
| 4397 | 7 | `_append_part_tree_item` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 4405 | 22 | `_select_part_in_tree` | unclassified | 8 | test_compatibility | 0 | 18 | 0 |
| 4428 | 17 | `_first_selectable_part_item` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 4446 | 75 | `_refresh_part_tree` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 4522 | 8 | `add_taxonomy_part` | image_navigation | 5 | public_or_source_compatibility | 1 | 29 | 1 |
| 4531 | 7 | `_count_ai_labels_for_images` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 4539 | 67 | `_choose_clear_ai_scope` | unclassified | 8 | test_compatibility | 0 | 1 | 0 |
| 4607 | 41 | `rename_taxonomy_part` | image_navigation | 5 | public_or_source_compatibility | 1 | 3 | 1 |
| 4649 | 13 | `remove_taxonomy_part` | image_navigation | 5 | public_or_source_compatibility | 1 | 6 | 1 |
| 4663 | 55 | `clear_ai_labels` | unclassified | 8 | signal_compatibility | 0 | 2 | 1 |
| 4719 | 6 | `on_global_labels_updated` | unclassified | 8 | signal_compatibility | 0 | 0 | 1 |
| 4726 | 190 | `refresh_ui` | unclassified | 8 | public_or_source_compatibility | 1 | 0 | 0 |
| 4917 | 78 | `_update_blink_refine_panel` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 4996 | 39 | `_update_blink_parent_context_combo` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 5036 | 51 | `open_general_settings` | dialog_settings | 2 | public_or_source_compatibility | 1 | 0 | 1 |
| 5088 | 129 | `open_stl_model_settings` | dialog_settings | 2 | public_or_source_compatibility | 2 | 0 | 0 |
| 5218 | 2 | `open_settings` | dialog_settings | 2 | public_or_source_compatibility | 1 | 0 | 0 |
| 5221 | 15 | `open_tif_model_settings` | dialog_settings | 2 | public_or_source_compatibility | 1 | 0 | 0 |
| 5237 | 13 | `change_language` | shell_start_agent | 3 | public_or_source_compatibility | 4 | 8 | 0 |
| 5251 | 22 | `change_theme` | shell_start_agent | 3 | public_or_source_compatibility | 1 | 0 | 0 |
| 5274 | 15 | `update_widget_themes` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 5290 | 66 | `update_button_themes` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 5356 | 4 | `add_images` | image_navigation | 5 | public_or_source_compatibility | 7 | 36 | 1 |
| 5361 | 94 | `_start_image_import` | shell_start_agent | 3 | test_compatibility | 0 | 1 | 0 |
| 5456 | 5 | `_set_image_import_controls_enabled` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 5462 | 20 | `open_cropper` | project_lifecycle | 4 | signal_compatibility | 0 | 0 | 1 |
| 5483 | 8 | `_is_split_crop_image` | image_navigation | 5 | test_compatibility | 0 | 5 | 0 |
| 5492 | 15 | `_is_hard_joined_candidate_crop` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 5508 | 17 | `_looks_like_panel_crop_path` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 5526 | 26 | `_has_split_crops_from_image` | image_navigation | 5 | test_compatibility | 0 | 1 | 0 |
| 5553 | 10 | `_needs_manual_panel_split` | image_navigation | 5 | test_compatibility | 0 | 8 | 0 |
| 5564 | 8 | `_is_manual_panel_split_done` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 5573 | 10 | `_set_panel_split_review` | image_navigation | 5 | test_compatibility | 0 | 6 | 0 |
| 5584 | 7 | `_clear_panel_split_review` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 5592 | 8 | `_builtin_image_group_definitions` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 5601 | 16 | `_custom_image_group_definitions` | image_navigation | 5 | test_compatibility | 0 | 1 | 0 |
| 5618 | 2 | `_all_image_group_definitions` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 5621 | 19 | `_training_scope_group_definitions` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 5641 | 24 | `_populate_training_scope_combo` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 5666 | 5 | `_refresh_training_scope_combo` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 5672 | 16 | `_selected_training_scope_payload` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 5689 | 13 | `_populate_vlm_image_group_combo` | vlm_prediction_export | 7 | public_or_source_compatibility | 3 | 0 | 0 |
| 5703 | 5 | `_refresh_vlm_image_group_combo` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 5709 | 6 | `_image_group_display_name` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 5716 | 2 | `_custom_image_group_ids` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 5719 | 9 | `_image_group_move_target_definitions` | image_navigation | 5 | test_compatibility | 0 | 2 | 0 |
| 5729 | 45 | `_remove_empty_custom_image_groups` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 5775 | 13 | `_safe_custom_image_group_id` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 5789 | 34 | `create_custom_image_group` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 5824 | 10 | `_set_image_manual_group` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 5835 | 15 | `move_images_to_group` | image_navigation | 5 | signal_compatibility | 0 | 7 | 1 |
| 5851 | 10 | `clear_selected_custom_image_group` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 5862 | 10 | `_short_progress_path` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 5873 | 13 | `_prepare_progress_dialog` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 5887 | 6 | `_candidate_panel_split_sources` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 5894 | 131 | `batch_split_panel_images` | image_navigation | 5 | signal_compatibility | 0 | 2 | 1 |
| 6026 | 22 | `_save_detected_panel_crops` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 6049 | 10 | `_next_panel_crop_path` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 6060 | 32 | `_inherit_crop_provenance` | image_navigation | 5 | test_compatibility | 0 | 3 | 0 |
| 6093 | 9 | `_selected_image_paths` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 6103 | 8 | `_set_selected_panel_split_status` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 6112 | 2 | `mark_selected_manual_split_done` | unclassified | 8 | test_compatibility | 0 | 2 | 0 |
| 6115 | 2 | `mark_selected_manual_split_needed` | unclassified | 8 | test_compatibility | 0 | 1 | 0 |
| 6118 | 8 | `clear_selected_split_status` | unclassified | 8 | test_compatibility | 0 | 1 | 0 |
| 6127 | 23 | `show_file_list_context_menu` | shell_start_agent | 3 | signal_compatibility | 0 | 1 | 1 |
| 6151 | 7 | `_move_selected_images_to_new_group` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 6159 | 60 | `remove_selected_images` | image_navigation | 5 | test_compatibility | 0 | 4 | 0 |
| 6220 | 95 | `refresh_file_list` | image_navigation | 5 | public_or_source_compatibility | 2 | 41 | 0 |
| 6316 | 4 | `_image_has_review_content` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 6321 | 19 | `_set_image_list_item_status` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 6341 | 41 | `_refresh_current_image_list_status` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 6383 | 6 | `_refresh_image_list_status_or_rebuild` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 6390 | 7 | `_image_list_path_identity` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 6398 | 10 | `_visible_image_list_paths` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 6409 | 27 | `_replacement_image_after_removal` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 6437 | 61 | `_remove_visible_image_list_items` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 6499 | 10 | `_filtered_group_definitions_after_removal` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 6510 | 14 | `_refresh_visible_image_group_header_counts` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 6525 | 31 | `_select_first_visible_image_after_removal` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 6557 | 26 | `_build_image_list_state` | image_navigation | 5 | test_compatibility | 0 | 1 | 0 |
| 6584 | 12 | `_handle_image_list_item_clicked` | image_navigation | 5 | signal_compatibility | 0 | 2 | 1 |
| 6597 | 26 | `eventFilter` | unclassified | 8 | public_or_source_compatibility | 2 | 3 | 0 |
| 6624 | 35 | `_should_use_image_list_arrow_navigation` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 6660 | 21 | `_select_adjacent_image` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 6682 | 55 | `_collect_blink_roi_candidates` | blink | 6 | test_compatibility | 0 | 4 | 0 |
| 6738 | 39 | `on_file_selected` | unclassified | 8 | signal_compatibility | 0 | 0 | 1 |
| 6778 | 11 | `on_part_selected` | unclassified | 8 | public_or_source_compatibility | 2 | 0 | 1 |
| 6790 | 90 | `launch_blink_from_workbench` | blink | 6 | public_or_source_compatibility | 1 | 4 | 1 |
| 6881 | 8 | `on_genus_changed` | image_navigation | 5 | signal_compatibility | 0 | 0 | 1 |
| 6890 | 9 | `update_db_description` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 6900 | 5 | `_current_taxon_text` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 6906 | 8 | `_literature_source_taxon` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 6915 | 19 | `_set_current_image_taxon_from_literature` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 6935 | 21 | `_candidate_literature_db_paths` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 6957 | 55 | `_project_literature_db_paths` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 7013 | 39 | `_resolve_current_literature_context` | dialog_settings | 2 | test_compatibility | 0 | 3 | 0 |
| 7053 | 27 | `_resolve_literature_context_from_selected_db` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 7081 | 23 | `_choose_literature_db_for_current_taxon` | dialog_settings | 2 | test_compatibility | 0 | 1 | 0 |
| 7105 | 22 | `_literature_db_matches_image_source` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 7128 | 42 | `open_literature_description_dialog` | dialog_settings | 2 | signal_compatibility | 0 | 0 | 1 |
| 7171 | 22 | `_open_literature_description_dialog_with_context` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 7194 | 24 | `_apply_literature_description` | dialog_settings | 2 | test_compatibility | 0 | 1 | 0 |
| 7219 | 15 | `_ensure_workbench_description_visible` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 7235 | 2 | `on_enhancement_changed` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 7238 | 16 | `on_tool_changed` | annotation_sam | 6 | public_or_source_compatibility | 2 | 8 | 6 |
| 7255 | 23 | `on_blink_parent_context_changed` | blink | 6 | signal_compatibility | 0 | 2 | 1 |
| 7279 | 2 | `on_magic_wand_clicked` | annotation_sam | 6 | signal_compatibility | 0 | 0 | 1 |
| 7282 | 2 | `on_magic_box_completed` | annotation_sam | 6 | signal_compatibility | 0 | 1 | 1 |
| 7285 | 2 | `_sam_worker_ready` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 7288 | 2 | `_on_sam_model_loaded` | annotation_sam | 6 | signal_compatibility | 0 | 0 | 1 |
| 7291 | 18 | `_begin_sam_prompt` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 7310 | 6 | `_request_sam_point` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 7317 | 6 | `_request_sam_box` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 7324 | 34 | `on_annotation_box_completed` | annotation_sam | 6 | signal_compatibility | 0 | 3 | 1 |
| 7359 | 2 | `_warn_blink_context` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 7362 | 12 | `_active_child_blink_context` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 7375 | 43 | `run_blink_child_auto_annotate` | blink | 6 | signal_compatibility | 0 | 4 | 1 |
| 7419 | 9 | `_load_blink_refiner_class` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 7429 | 11 | `_active_blink_auto_shrink_steps` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 7441 | 14 | `_blink_parent_context_for_image` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 7456 | 41 | `_prepared_blink_auto_shrink_images` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 7498 | 38 | `_generate_blink_shrink_for_image` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 7537 | 42 | `run_blink_auto_shrink` | blink | 6 | signal_compatibility | 0 | 3 | 1 |
| 7580 | 90 | `run_blink_batch_auto_shrink` | blink | 6 | signal_compatibility | 0 | 1 | 1 |
| 7671 | 66 | `train_current_blink_expert` | blink | 6 | signal_compatibility | 0 | 3 | 1 |
| 7738 | 10 | `stop_current_blink_expert_training` | blink | 6 | signal_compatibility | 0 | 1 | 1 |
| 7749 | 18 | `open_current_route_expert_settings` | blink | 6 | signal_compatibility | 0 | 0 | 1 |
| 7768 | 10 | `on_sam_mask_generated` | annotation_sam | 6 | signal_compatibility | 0 | 0 | 1 |
| 7779 | 7 | `on_sam_prompt_failed` | annotation_sam | 6 | signal_compatibility | 0 | 0 | 1 |
| 7787 | 23 | `on_polygon_completed` | annotation_sam | 6 | signal_compatibility | 0 | 4 | 1 |
| 7811 | 7 | `toggle_morphometrics` | unclassified | 8 | signal_compatibility | 0 | 0 | 1 |
| 7819 | 9 | `on_scale_defined` | annotation_sam | 6 | signal_compatibility | 0 | 0 | 1 |
| 7829 | 16 | `update_measurements` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 7846 | 87 | `run_training` | training_model | 7 | public_or_source_compatibility | 1 | 2 | 1 |
| 7934 | 2 | `_external_backend_runner` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 7937 | 27 | `_sync_blink_lab_model_profile_defaults` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 7965 | 51 | `run_external_training` | training_model | 7 | test_compatibility | 0 | 1 | 0 |
| 8017 | 3 | `show_training_report` | dialog_settings | 2 | signal_compatibility | 0 | 0 | 1 |
| 8021 | 26 | `_candidate_training_experiment_dirs` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8048 | 10 | `_resolve_report_artifact_path` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 8059 | 11 | `_training_report_time_label` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 8071 | 66 | `_training_report_payload_from_summary` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 8138 | 26 | `discover_training_reports` | dialog_settings | 2 | test_compatibility | 0 | 1 | 0 |
| 8165 | 8 | `open_training_report_payload` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 8174 | 17 | `open_training_results_browser` | project_lifecycle | 4 | signal_compatibility | 0 | 0 | 1 |
| 8192 | 37 | `_extract_prediction_payload` | vlm_prediction_export | 7 | public_or_source_compatibility | 2 | 0 | 0 |
| 8230 | 12 | `_is_unconfirmed_ai_draft` | vlm_prediction_export | 7 | public_or_source_compatibility | 2 | 0 | 0 |
| 8243 | 13 | `_auto_box_meta_for_part` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8257 | 3 | `_auto_box_source_for_part` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8261 | 3 | `_auto_box_review_status_for_part` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8265 | 5 | `_auto_annotation_source_meta` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 8271 | 15 | `_can_replace_existing_auto_annotation` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 8287 | 33 | `_apply_prediction_to_project` | vlm_prediction_export | 7 | test_compatibility | 0 | 3 | 0 |
| 8321 | 5 | `_vlm_api_settings_path` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8327 | 40 | `_vlm_api_config_from_pdf_widget` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8368 | 8 | `_vlm_preannotation_artifacts_dir` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 8377 | 4 | `_current_vlm_target_parts` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8382 | 4 | `_current_vlm_processing_scope` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8387 | 3 | `_current_vlm_batch_scope` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 8391 | 4 | `_current_vlm_image_group` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 8396 | 8 | `_current_vlm_concurrency` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8405 | 5 | `_current_vlm_prompt_profile` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8411 | 2 | `_vlm_image_group_label` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 8414 | 57 | `_panel_crop_identity_index` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 8472 | 57 | `_project_image_groups` | project_lifecycle | 4 | test_compatibility | 0 | 8 | 0 |
| 8530 | 10 | `_vlm_candidate_source_meta` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8541 | 19 | `_record_sqlite_vlm_image_result` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8561 | 13 | `_finish_sqlite_vlm_run` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8575 | 7 | `_vlm_image_paths_for_scope` | vlm_prediction_export | 7 | test_compatibility | 0 | 3 | 0 |
| 8583 | 2 | `_vlm_image_paths_from_settings` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8586 | 11 | `_same_project_image_path` | project_lifecycle | 4 | test_compatibility | 0 | 1 | 0 |
| 8598 | 5 | `_project_image_key_for_path` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 8604 | 7 | `_vlm_part_list_text` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8612 | 18 | `_vlm_part_coverage` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8631 | 15 | `_log_vlm_part_coverage` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8647 | 2 | `run_vlm_preannotation_current` | vlm_prediction_export | 7 | signal_compatibility | 0 | 0 | 1 |
| 8650 | 2 | `run_vlm_preannotation_batch` | vlm_prediction_export | 7 | signal_compatibility | 0 | 0 | 1 |
| 8653 | 121 | `run_vlm_preannotation_from_settings` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 8775 | 42 | `request_stop_vlm_preannotation` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 8818 | 11 | `_active_vlm_preannotation_threads` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 8830 | 14 | `_start_vlm_preannotation_workers` | runtime_worker | 1 | test_compatibility | 0 | 1 | 0 |
| 8845 | 53 | `_start_next_vlm_preannotation_image` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 8899 | 48 | `_apply_vlm_candidate` | vlm_prediction_export | 7 | test_compatibility | 0 | 5 | 0 |
| 8948 | 6 | `_refresh_vlm_canvas_if_current` | vlm_prediction_export | 7 | test_compatibility | 0 | 3 | 0 |
| 8955 | 34 | `_reload_current_image_for_workbench` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 8990 | 111 | `_on_vlm_preannotation_image_result` | vlm_prediction_export | 7 | signal_compatibility | 0 | 6 | 1 |
| 9102 | 7 | `_vlm_progress_image_key` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 9110 | 20 | `_mark_current_vlm_image_done` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 9131 | 30 | `_set_vlm_progress_ui` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 9162 | 54 | `_create_vlm_progress_dialog` | vlm_prediction_export | 7 | test_compatibility | 0 | 2 | 0 |
| 9217 | 18 | `_advance_vlm_progress` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 9236 | 11 | `_on_vlm_preannotation_thread_step` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 9248 | 7 | `_complete_current_vlm_image_steps` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 9256 | 100 | `_finish_vlm_preannotation_run` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 9357 | 36 | `accept_current_image_ai_drafts` | vlm_prediction_export | 7 | signal_compatibility | 0 | 3 | 1 |
| 9394 | 93 | `accept_batch_ai_drafts` | vlm_prediction_export | 7 | signal_compatibility | 0 | 1 | 1 |
| 9488 | 3 | `_on_vlm_preannotation_error` | vlm_prediction_export | 7 | signal_compatibility | 0 | 0 | 1 |
| 9492 | 33 | `_on_vlm_preannotation_qthread_finished` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 9526 | 2 | `_on_vlm_preannotation_finished` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 9529 | 46 | `run_prediction` | vlm_prediction_export | 7 | public_or_source_compatibility | 1 | 2 | 1 |
| 9576 | 30 | `run_external_prediction` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 9607 | 9 | `verify_current_image` | image_navigation | 5 | signal_compatibility | 0 | 1 | 1 |
| 9617 | 100 | `_start_external_batch_inference` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 9718 | 74 | `run_batch_inference` | runtime_worker | 1 | signal_compatibility | 0 | 1 | 1 |
| 9793 | 8 | `export_dataset` | runtime_worker | 1 | signal_compatibility | 0 | 0 | 1 |
| 9802 | 75 | `_start_dataset_export` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 9878 | 23 | `init_sam` | annotation_sam | 6 | test_compatibility | 0 | 1 | 0 |
| 9902 | 13 | `ensure_sam_preloaded` | annotation_sam | 6 | test_compatibility | 0 | 6 | 0 |
| 9916 | 4 | `ensure_2d_stl_models_preloaded` | training_model | 7 | test_compatibility | 0 | 3 | 0 |
| 9921 | 17 | `ensure_locator_preloaded` | training_model | 7 | test_compatibility | 0 | 1 | 0 |
| 9939 | 22 | `_preload_engine_parts_model_async` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 9962 | 2 | `log` | unclassified | 8 | public_or_source_compatibility | 188 | 34 | 5 |

## MainWindow State Fields

| Field | Assignments | Lines | Target owner | Stage |
| --- | --- | --- | --- | --- |
| `_image_list_state_cache` | 6 | 577, 2560, 6386, 6349, 6213, 6231 | TBD | TBD |
| `_refreshing_part_tree` | 2 | 4451, 4510 | TBD | TBD |
| `_suppress_selection_save_flush` | 4 | 6546, 6533, 6553, 6540 | TBD | TBD |
| `_updating_blink_parent_context` | 2 | 5001, 5034 | TBD | TBD |
| `active_project_entry_path` | 8 | 496, 1133, 3494, 3583, 3944, 3470, 3952, 3966 | TBD | TBD |
| `active_project_kind` | 13 | 494, 1134, 1483, 2029, 2057, 2093, 2103, 3492, 3581, 3942, 3468, 3950, 3964 | TBD | TBD |
| `active_project_source_kind` | 7 | 495, 3493, 3582, 3943, 3469, 3951, 3965 | TBD | TBD |
| `active_training_kind` | 3 | 564, 7983, 3029 | TBD | TBD |
| `active_training_label` | 2 | 565, 3031 | TBD | TBD |
| `agent_panel` | 1 | 1204 | TBD | TBD |
| `ai_action_panel` | 1 | 923 | TBD | TBD |
| `ai_model_panel` | 1 | 873 | TBD | TBD |
| `ai_panel` | 1 | 850 | TBD | TBD |
| `blink_auto_shrink_steps` | 2 | 506, 5137 | TBD | TBD |
| `blink_context_status_label` | 1 | 790 | TBD | TBD |
| `blink_lab` | 1 | 1110 | TBD | TBD |
| `blink_refine_panel` | 1 | 985 | TBD | TBD |
| `blink_train_batch` | 2 | 502, 5133 | TBD | TBD |
| `blink_train_epochs` | 2 | 501, 5133 | TBD | TBD |
| `blink_train_input_size` | 2 | 505, 5136 | TBD | TBD |
| `blink_train_lr` | 2 | 503, 5134 | TBD | TBD |
| `blink_train_weight_decay` | 2 | 504, 5135 | TBD | TBD |
| `blink_training_strategy` | 2 | 507, 5138 | TBD | TBD |
| `btn_accept_batch_ai_drafts` | 1 | 943 | TBD | TBD |
| `btn_accept_current_ai_drafts` | 1 | 939 | TBD | TBD |
| `btn_add` | 1 | 677 | TBD | TBD |
| `btn_add_part` | 1 | 796 | TBD | TBD |
| `btn_agent_from_workbench` | 1 | 610 | TBD | TBD |
| `btn_batch` | 1 | 934 | TBD | TBD |
| `btn_batch_split_panels` | 1 | 600 | TBD | TBD |
| `btn_blink_auto_annotate` | 1 | 1019 | TBD | TBD |
| `btn_blink_auto_shrink` | 1 | 1026 | TBD | TBD |
| `btn_blink_batch_auto_shrink` | 1 | 1030 | TBD | TBD |
| `btn_blink_entry` | 1 | 603 | TBD | TBD |
| `btn_blink_stop_training` | 1 | 1042 | TBD | TBD |
| `btn_blink_train_expert` | 1 | 1038 | TBD | TBD |
| `btn_clear_ai` | 1 | 978 | TBD | TBD |
| `btn_configure_route_expert` | 1 | 1015 | TBD | TBD |
| `btn_continue_last` | 1 | 1327 | TBD | TBD |
| `btn_crop` | 1 | 597 | TBD | TBD |
| `btn_del_locator` | 1 | 890 | TBD | TBD |
| `btn_del_part` | 1 | 802 | TBD | TBD |
| `btn_del_segmenter` | 1 | 910 | TBD | TBD |
| `btn_export` | 1 | 594 | TBD | TBD |
| `btn_general_settings` | 1 | 1333 | TBD | TBD |
| `btn_literature_descriptions` | 1 | 834 | TBD | TBD |
| `btn_note_locator` | 1 | 894 | TBD | TBD |
| `btn_note_segmenter` | 1 | 914 | TBD | TBD |
| `btn_open_any` | 1 | 1330 | TBD | TBD |
| `btn_predict` | 1 | 930 | TBD | TBD |
| `btn_rename_part` | 1 | 799 | TBD | TBD |
| `btn_start_ant_code` | 1 | 1239 | TBD | TBD |
| `btn_start_center_from_workbench` | 1 | 606 | TBD | TBD |
| `btn_start_console_toggle` | 1 | 1367 | TBD | TBD |
| `btn_stop_ant_code` | 1 | 1242 | TBD | TBD |
| `btn_stop_training` | 1 | 972 | TBD | TBD |
| `btn_train` | 1 | 968 | TBD | TBD |
| `btn_training_results` | 1 | 1063 | TBD | TBD |
| `btn_vlm_preannotate_batch` | 1 | 618 | TBD | TBD |
| `btn_vlm_preannotate_current` | 1 | 614 | TBD | TBD |
| `canvas` | 1 | 730 | TBD | TBD |
| `canvas_shell` | 1 | 737 | TBD | TBD |
| `check_lock_parent_box_ratio` | 1 | 1011 | TBD | TBD |
| `check_morpho` | 1 | 810 | TBD | TBD |
| `child_training_cancel_requested` | 5 | 563, 3071, 3082, 7701, 7743 | TBD | TBD |
| `child_training_failed` | 5 | 562, 3060, 3067, 3081, 7700 | TBD | TBD |
| `chk_train_locator_only` | 1 | 947 | TBD | TBD |
| `combo_blink_parent_context` | 1 | 1000 | TBD | TBD |
| `combo_locator` | 1 | 884 | TBD | TBD |
| `combo_segmenter` | 1 | 904 | TBD | TBD |
| `combo_training_scope` | 1 | 961 | TBD | TBD |
| `config` | 1 | 484 | TBD | TBD |
| `current_blink_context` | 2 | 566, 4392 | TBD | TBD |
| `current_image` | 8 | 526, 2567, 8961, 4045, 6761, 7444, 7447, 6210 | TBD | TBD |
| `current_lang` | 2 | 485, 5238 | TBD | TBD |
| `current_theme` | 2 | 486, 5253 | TBD | TBD |
| `dataset_export_thread` | 2 | 9827, 9870 | TBD | TBD |
| `db` | 1 | 497 | TBD | TBD |
| `desc_box` | 1 | 844 | TBD | TBD |
| `description_header_panel` | 1 | 829 | TBD | TBD |
| `engine` | 1 | 520 | TBD | TBD |
| `external_backend_config` | 2 | 514, 5148 | TBD | TBD |
| `external_batch_inference_failed` | 3 | 538, 9627, 9686 | TBD | TBD |
| `external_batch_inference_progress_dialog` | 3 | 537, 9647, 9700 | TBD | TBD |
| `external_batch_inference_saved_any` | 3 | 539, 9628, 9682 | TBD | TBD |
| `external_batch_inference_thread` | 3 | 536, 9659, 9702 | TBD | TBD |
| `external_training_failed` | 3 | 541, 7982, 7996 | TBD | TBD |
| `external_training_thread` | 3 | 540, 7988, 8005 | TBD | TBD |
| `file_list` | 1 | 668 | TBD | TBD |
| `genus_combo` | 1 | 775 | TBD | TBD |
| `group_morpho` | 1 | 813 | TBD | TBD |
| `image_import_progress_dialog` | 3 | 535, 5400, 5443 | TBD | TBD |
| `image_import_thread` | 3 | 534, 5403, 5447 | TBD | TBD |
| `image_list_group_collapsed` | 1 | 572 | TBD | TBD |
| `image_taxon_panel` | 1 | 821 | TBD | TBD |
| `inf_adapt` | 2 | 516, 5142 | TBD | TBD |
| `inf_conf` | 2 | 515, 5142 | TBD | TBD |
| `inf_noise_floor` | 2 | 518, 5143 | TBD | TBD |
| `inf_pad` | 2 | 517, 5143 | TBD | TBD |
| `inf_poly_epsilon` | 2 | 519, 5144 | TBD | TBD |
| `inf_thread` | 2 | 527, 9754 | TBD | TBD |
| `label_ai_workflow` | 1 | 855 | TBD | TBD |
| `label_blink_expert` | 1 | 1007 | TBD | TBD |
| `label_blink_parent_box` | 1 | 1003 | TBD | TBD |
| `label_blink_parent_context` | 1 | 997 | TBD | TBD |
| `label_blink_refine` | 1 | 990 | TBD | TBD |
| `label_blink_route` | 1 | 993 | TBD | TBD |
| `label_description` | 1 | 839 | TBD | TBD |
| `label_logs` | 1 | 1086 | TBD | TBD |
| `label_measurements` | 1 | 817 | TBD | TBD |
| `label_model_backend` | 1 | 859 | TBD | TBD |
| `label_parent_annotation` | 1 | 868 | TBD | TBD |
| `label_project_images` | 1 | 665 | TBD | TBD |
| `label_structures` | 1 | 779 | TBD | TBD |
| `label_taxonomy` | 1 | 773 | TBD | TBD |
| `label_training_progress` | 1 | 1058 | TBD | TBD |
| `label_training_progress_status` | 1 | 1069 | TBD | TBD |
| `last_confirmed_locator_timestamp` | 4 | 557, 2968, 3354, 3347 | TBD | TBD |
| `lbl_locator` | 1 | 882 | TBD | TBD |
| `lbl_segmenter` | 1 | 902 | TBD | TBD |
| `lbl_training_scope` | 1 | 958 | TBD | TBD |
| `locator_preload_thread` | 1 | 543 | TBD | TBD |
| `log_console` | 1 | 1089 | TBD | TBD |
| `logs_panel` | 1 | 1081 | TBD | TBD |
| `metadata_panel` | 1 | 768 | TBD | TBD |
| `model_backend` | 2 | 513, 5147 | TBD | TBD |
| `parent_annotation_panel` | 1 | 863 | TBD | TBD |
| `parent_box_aspect_ratios` | 3 | 578, 4333, 5163 | TBD | TBD |
| `parent_training_cancel_requested` | 3 | 561, 3132, 3246 | TBD | TBD |
| `parent_training_failed` | 4 | 560, 3131, 3207, 3224 | TBD | TBD |
| `part_list` | 1 | 782 | TBD | TBD |
| `parts_model_preload_thread` | 2 | 544, 9954 | TBD | TBD |
| `pdf_widget` | 1 | 1104 | TBD | TBD |
| `pending_sam_description` | 4 | 533, 7307, 7775, 7783 | TBD | TBD |
| `pending_sam_image` | 4 | 532, 7306, 7774, 7782 | TBD | TBD |
| `pending_sam_part` | 4 | 531, 7305, 7773, 7781 | TBD | TBD |
| `pending_training_preflight` | 2 | 558, 3119 | TBD | TBD |
| `progress` | 1 | 1074 | TBD | TBD |
| `project` | 1 | 490 | TBD | TBD |
| `project_autosave_delay_ms` | 2 | 549, 5055 | TBD | TBD |
| `project_last_image_switch_at` | 2 | 551, 2303 | TBD | TBD |
| `project_save_context` | 4 | 553, 2358, 2297, 2312 | TBD | TBD |
| `project_save_navigation_idle_ms` | 1 | 550 | TBD | TBD |
| `project_save_pending` | 4 | 552, 2295, 2357, 2311 | TBD | TBD |
| `project_save_timer` | 1 | 554 | TBD | TBD |
| `radio_annotation_box` | 1 | 711 | TBD | TBD |
| `radio_box` | 1 | 706 | TBD | TBD |
| `radio_draw` | 1 | 695 | TBD | TBD |
| `radio_loose_shrink_box` | 1 | 716 | TBD | TBD |
| `radio_magic` | 1 | 701 | TBD | TBD |
| `radio_scale` | 1 | 721 | TBD | TBD |
| `route_settings_panel` | 1 | 1127 | TBD | TBD |
| `runtime_device` | 3 | 512, 5060, 5146 | TBD | TBD |
| `sam_busy` | 4 | 530, 7304, 7772, 7780 | TBD | TBD |
| `sam_thread` | 2 | 528, 9885 | TBD | TBD |
| `sam_worker` | 2 | 529, 9887 | TBD | TBD |
| `shortcut_redo` | 1 | 748 | TBD | TBD |
| `shortcut_save` | 1 | 750 | TBD | TBD |
| `shortcut_undo` | 1 | 746 | TBD | TBD |
| `shortcut_verify` | 1 | 752 | TBD | TBD |
| `start_agent_status_label` | 1 | 1231 | TBD | TBD |
| `start_center_widget` | 1 | 586 | TBD | TBD |
| `start_console_agent_label` | 1 | 1404 | TBD | TBD |
| `start_console_agent_value` | 1 | 1404 | TBD | TBD |
| `start_console_body` | 1 | 1374 | TBD | TBD |
| `start_console_expanded` | 2 | 1415, 1420 | TBD | TBD |
| `start_console_images_label` | 1 | 1391 | TBD | TBD |
| `start_console_images_value` | 1 | 1391 | TBD | TBD |
| `start_console_panel` | 1 | 1274 | TBD | TBD |
| `start_console_pdf_label` | 1 | 1401 | TBD | TBD |
| `start_console_pdf_value` | 1 | 1401 | TBD | TBD |
| `start_console_project_label` | 1 | 1388 | TBD | TBD |
| `start_console_project_value` | 1 | 1388 | TBD | TBD |
| `start_console_stl_note` | 1 | 1410 | TBD | TBD |
| `start_console_summary` | 1 | 1356 | TBD | TBD |
| `start_console_tif_label` | 2 | 1395, 1399 | TBD | TBD |
| `start_console_tif_value` | 2 | 1395, 1400 | TBD | TBD |
| `start_console_title` | 1 | 1354 | TBD | TBD |
| `start_console_workflow_label` | 1 | 1385 | TBD | TBD |
| `start_console_workflow_value` | 1 | 1385 | TBD | TBD |
| `start_image_card` | 1 | 1278 | TBD | TBD |
| `start_pdf_card` | 1 | 1298 | TBD | TBD |
| `start_quick_panel` | 1 | 1276 | TBD | TBD |
| `start_recent_label` | 1 | 1323 | TBD | TBD |
| `start_subtitle` | 1 | 1219 | TBD | TBD |
| `start_tif_card` | 2 | 1287, 1289 | TBD | TBD |
| `start_title` | 1 | 1217 | TBD | TBD |
| `startup_size` | 1 | 482 | TBD | TBD |
| `stl_project` | 1 | 493 | TBD | TBD |
| `tabs` | 1 | 584 | TBD | TBD |
| `tif_project` | 1 | 492 | TBD | TBD |
| `tif_workbench` | 1 | 1107 | TBD | TBD |
| `tif_workflow_enabled` | 1 | 489 | TBD | TBD |
| `tool_group` | 1 | 694 | TBD | TBD |
| `tool_strip` | 1 | 689 | TBD | TBD |
| `toolbar_flow_panel` | 1 | 638 | TBD | TBD |
| `toolbar_project_panel` | 1 | 629 | TBD | TBD |
| `train_batch` | 2 | 500, 5132 | TBD | TBD |
| `train_epochs` | 2 | 499, 5132 | TBD | TBD |
| `train_lr` | 2 | 510, 5141 | TBD | TBD |
| `train_wd` | 2 | 511, 5141 | TBD | TBD |
| `trainer` | 3 | 542, 3137, 3198 | TBD | TBD |
| `training_progress_panel` | 1 | 1050 | TBD | TBD |
| `training_retry_requested` | 4 | 559, 3130, 3206, 3215 | TBD | TBD |
| `vlm_preannotation_active_images` | 3 | 8753, 9353, 8880 | TBD | TBD |
| `vlm_preannotation_api_config` | 2 | 8734, 8758 | TBD | TBD |
| `vlm_preannotation_artifacts_dir` | 1 | 8757 | TBD | TBD |
| `vlm_preannotation_cancel_requested` | 4 | 570, 8745, 8795, 9349 | TBD | TBD |
| `vlm_preannotation_cancelled_queued_images` | 4 | 571, 8746, 8796, 9350 | TBD | TBD |
| `vlm_preannotation_completed_image_keys` | 3 | 8755, 9119, 9355 | TBD | TBD |
| `vlm_preannotation_completed_images` | 2 | 8751, 9121 | TBD | TBD |
| `vlm_preannotation_completed_steps` | 2 | 8749, 9220 | TBD | TBD |
| `vlm_preannotation_concurrency` | 1 | 8747 | TBD | TBD |
| `vlm_preannotation_current_image` | 4 | 8752, 8854, 9126, 9222 | TBD | TBD |
| `vlm_preannotation_current_image_steps_completed` | 3 | 8853, 9229, 9232 | TBD | TBD |
| `vlm_preannotation_image_step_counts` | 4 | 8754, 9354, 8884, 9227 | TBD | TBD |
| `vlm_preannotation_progress_bar` | 2 | 9213, 9347 | TBD | TBD |
| `vlm_preannotation_progress_dialog` | 3 | 569, 9208, 9342 | TBD | TBD |
| `vlm_preannotation_progress_label` | 2 | 9211, 9345 | TBD | TBD |
| `vlm_preannotation_progress_notice_label` | 2 | 9210, 9344 | TBD | TBD |
| `vlm_preannotation_progress_path_label` | 2 | 9212, 9346 | TBD | TBD |
| `vlm_preannotation_progress_title_label` | 2 | 9209, 9343 | TBD | TBD |
| `vlm_preannotation_prompt_profile` | 1 | 8759 | TBD | TBD |
| `vlm_preannotation_queue` | 4 | 8742, 8797, 8852, 9516 | TBD | TBD |
| `vlm_preannotation_records` | 1 | 8741 | TBD | TBD |
| `vlm_preannotation_run_active` | 2 | 8744, 9316 | TBD | TBD |
| `vlm_preannotation_run_id` | 1 | 8740 | TBD | TBD |
| `vlm_preannotation_saved_total` | 2 | 8739, 9050 | TBD | TBD |
| `vlm_preannotation_stop_button` | 2 | 9214, 9348 | TBD | TBD |
| `vlm_preannotation_target_parts` | 1 | 8756 | TBD | TBD |
| `vlm_preannotation_thread` | 5 | 567, 8827, 8843, 8876, 9352 | TBD | TBD |
| `vlm_preannotation_threads` | 6 | 568, 8743, 8826, 8842, 9351, 9501 | TBD | TBD |
| `vlm_preannotation_total_images` | 1 | 8750 | TBD | TBD |
| `vlm_preannotation_total_steps` | 1 | 8748 | TBD | TBD |
| `workbench_inspector_scroll` | 1 | 755 | TBD | TBD |
| `workbench_splitter` | 1 | 654 | TBD | TBD |
| `workbench_top_bar` | 1 | 623 | TBD | TBD |
| `workbench_widget` | 1 | 588 | TBD | TBD |

## Main Import Compatibility

| File | Line | Import |
| --- | --- | --- |
| scripts/benchmark_main_window_workflows.py | 198 | `import AntSleap.main as main_module` |
| tests/test_blink_bridge.py | 22 | `import main as main_module` |
| tests/test_blink_bridge.py | 23 | `from main import BlinkEntryDialog, MainWindow` |
| tests/test_gui_smoke.py | 45 | `import AntSleap.main as main_module` |
| tests/test_main_window_stage1_modules.py | 55 | `import AntSleap.main as main_module` |
| tests/test_main_window_stage2_dialogs.py | 11 | `import AntSleap.main as main_module` |
| tests/test_main_window_stage2_dialogs.py | 52 | `self.assertNotIn("from main import", source)` |
| tests/test_main_window_stage2_dialogs.py | 74 | `import AntSleap.main as main_module` |
| tests/test_reporting_routes.py | 45 | `from AntSleap.main import TrainingReportDialog` |
| tests/test_tif_backend.py | 558 | `"from AntSleap.tools.tif_trainer_backend import main",` |
| tests/test_tif_backend.py | 599 | `"from AntSleap.tools.tif_trainer_backend import main",` |
| tests/test_tif_backend.py | 645 | `"from AntSleap.tools.tif_trainer_backend import main",` |
| tests/test_tif_backend.py | 684 | `"from AntSleap.tools.tif_trainer_backend import main",` |
| tests/test_tif_backend.py | 742 | `"from AntSleap.tools.tif_trainer_backend import main",` |
| tests/test_tif_nnunet_v2_backend.py | 33 | `"from AntSleap.tools.tif_nnunet_v2_backend import main",` |
| tests/test_ui_localization.py | 19 | `import AntSleap.main as main_module` |
| tests/test_ui_localization.py | 22 | `from AntSleap.main import ExportDialog, BlinkEntryDialog, ModelSettingsDialog, RouteManagementPanel, TrainingPreflightDialog, TrainingReportDialog` |
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
| tests/test_gui_smoke.py | 236 | `patch.object(main_module.MainWindow, "_default_outputs_root", lambda _window: str(self.project_dir / "TaxaMask_outputs")), \` | - | TBD |
| tests/test_gui_smoke.py | 242 | `patch.object(main_module.QTimer, "singleShot", lambda *args, **kwargs: None):` | - | TBD |
| tests/test_gui_smoke.py | 243 | `window = main_module.MainWindow()` | - | TBD |
| tests/test_gui_smoke.py | 244 | `window._default_outputs_root = lambda: str(self.project_dir / "TaxaMask_outputs")` | `_default_outputs_root` | TBD |
| tests/test_gui_smoke.py | 342 | `self.assertIsNotNone(window.findChild(main_module.QWidget, "start2DWorkflowCard"))` | - | TBD |
| tests/test_gui_smoke.py | 343 | `self.assertIsNone(window.findChild(main_module.QWidget, "start" + "T" + "if" + "WorkflowCard"))` | - | TBD |
| tests/test_gui_smoke.py | 344 | `self.assertIsNotNone(window.findChild(main_module.QWidget, "startProjectConsole"))` | - | TBD |
| tests/test_gui_smoke.py | 349 | `rail_scroll = window.findChild(main_module.QScrollArea, "startWorkflowRailScroll")` | - | TBD |
| tests/test_gui_smoke.py | 354 | `self.assertEqual(rail_scroll.horizontalScrollBarPolicy(), main_module.Qt.ScrollBarAlwaysOff)` | - | TBD |
| tests/test_gui_smoke.py | 355 | `self.assertEqual(rail_scroll.verticalScrollBarPolicy(), main_module.Qt.ScrollBarAsNeeded)` | - | TBD |
| tests/test_gui_smoke.py | 356 | `self.assertIsNotNone(window.findChild(main_module.QWidget, "taxamaskAgentPanel"))` | - | TBD |
| tests/test_gui_smoke.py | 367 | `self.assertIsNone(window.agent_panel.findChild(main_module.QWidget, "taxamaskAgentInlineStatus"))` | - | TBD |
| tests/test_gui_smoke.py | 368 | `self.assertIsNone(window.agent_panel.findChild(main_module.QWidget, "taxamaskStartAntCodeButton"))` | - | TBD |
| tests/test_gui_smoke.py | 422 | `self.assertIsNotNone(window.findChild(main_module.QWidget, "workbenchCanvasShell"))` | - | TBD |
| tests/test_gui_smoke.py | 423 | `self.assertIsNotNone(window.findChild(main_module.QWidget, "workbenchLiteratureDescriptionButton"))` | - | TBD |
| tests/test_gui_smoke.py | 429 | `window._show_start_center()` | `_show_start_center` | TBD |
| tests/test_gui_smoke.py | 435 | `self.assertIsNone(window.findChild(main_module.QWidget, "start" + "T" + "if" + "WorkflowCard"))` | - | TBD |
| tests/test_gui_smoke.py | 455 | `window._update_start_center_texts()` | `_update_start_center_texts` | TBD |
| tests/test_gui_smoke.py | 470 | `self.assertTrue(main_module.MainWindow.ensure_2d_stl_models_preloaded(window))` | - | TBD |
| tests/test_gui_smoke.py | 471 | `self.assertFalse(main_module.MainWindow.ensure_2d_stl_models_preloaded(window))` | - | TBD |
| tests/test_gui_smoke.py | 481 | `window._show_start_center()` | `_show_start_center` | TBD |
| tests/test_gui_smoke.py | 512 | `self.assertIsNotNone(window.agent_panel.findChild(main_module.QWidget, "taxamaskAgentStack"))` | - | TBD |
| tests/test_gui_smoke.py | 521 | `panel = main_module.TaxaMaskAgentPanel(` | - | TBD |
| tests/test_gui_smoke.py | 539 | `panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=str(PROJECT_ROOT))` | - | TBD |
| tests/test_gui_smoke.py | 543 | `self.assertIsNotNone(panel.findChild(main_module.QWidget, "taxamaskAgentStack"))` | - | TBD |
| tests/test_gui_smoke.py | 551 | `panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=str(PROJECT_ROOT))` | - | TBD |
| tests/test_gui_smoke.py | 570 | `class FakeWebView(main_module.QWidget):` | - | TBD |
| tests/test_gui_smoke.py | 622 | `panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=str(PROJECT_ROOT))` | - | TBD |
| tests/test_gui_smoke.py | 643 | `panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=r"D:\lab data\TaxaMask")` | - | TBD |
| tests/test_gui_smoke.py | 659 | `panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=str(PROJECT_ROOT))` | - | TBD |
| tests/test_gui_smoke.py | 668 | `panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=str(PROJECT_ROOT))` | - | TBD |
| tests/test_gui_smoke.py | 683 | `panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=str(PROJECT_ROOT))` | - | TBD |
| tests/test_gui_smoke.py | 910 | `with patch.object(main_module.QTimer, "singleShot", lambda _ms, callback: callback()):` | - | TBD |
| tests/test_gui_smoke.py | 931 | `fake_web_view = main_module.QWidget()` | - | TBD |
| tests/test_gui_smoke.py | 953 | `fake_web_view = main_module.QWidget()` | - | TBD |
| tests/test_gui_smoke.py | 1080 | `window.open_agent_from_context(window._collect_image_workbench_agent_context())` | `_collect_image_workbench_agent_context` | TBD |
| tests/test_gui_smoke.py | 1088 | `self.assertIn("MainWindow._collect_image_workbench_agent_context", context["source_code_refs"])` | `_collect_image_workbench_agent_context` | TBD |
| tests/test_gui_smoke.py | 1140 | `dialog = main_module.ModelSettingsDialog(` | - | TBD |
| tests/test_gui_smoke.py | 1160 | `self.assertIsNotNone(dialog.findChild(main_module.QPushButton, "modelSettingsAskAgentButton"))` | - | TBD |
| tests/test_gui_smoke.py | 1162 | `runtime_group = dialog.findChild(main_module.QWidget, "modelSettingsRuntimeDevicePanel")` | - | TBD |
| tests/test_gui_smoke.py | 1164 | `device_combo = runtime_group.findChild(main_module.QComboBox)` | - | TBD |
| tests/test_gui_smoke.py | 1178 | `dialog = main_module.ModelSettingsDialog(` | - | TBD |
| tests/test_gui_smoke.py | 1211 | `vlm_panel = dialog.findChild(main_module.QWidget, "modelSettingsVlmPreannotationPanel")` | - | TBD |
| tests/test_gui_smoke.py | 1217 | `scope_combo = dialog.findChild(main_module.QComboBox, "modelSettingsVlmBatchScopeCombo")` | - | TBD |
| tests/test_gui_smoke.py | 1221 | `group_combo = dialog.findChild(main_module.QComboBox, "modelSettingsVlmImageGroupCombo")` | - | TBD |
| tests/test_gui_smoke.py | 1224 | `profile_combo = dialog.findChild(main_module.QComboBox, "modelSettingsVlmPromptProfileCombo")` | - | TBD |
| tests/test_gui_smoke.py | 1235 | `dialog = main_module.ModelSettingsDialog(` | - | TBD |
| tests/test_gui_smoke.py | 1261 | `combo = dialog.findChild(main_module.QComboBox, "modelSettingsVlmImageGroupCombo")` | - | TBD |
| tests/test_gui_smoke.py | 1271 | `dialog = main_module.ModelSettingsDialog(` | - | TBD |
| tests/test_gui_smoke.py | 1324 | `dialog = main_module.GeneralSettingsDialog(` | - | TBD |
| tests/test_gui_smoke.py | 1341 | `self.assertIsNotNone(dialog.findChild(main_module.QPushButton, "generalSettingsAskAgentButton"))` | - | TBD |
| tests/test_gui_smoke.py | 1346 | `self.assertIsNone(dialog.findChild(main_module.QWidget, "modelSettingsLocatorScopePanel"))` | - | TBD |
| tests/test_gui_smoke.py | 1353 | `model_dialog = main_module.ModelSettingsDialog(` | - | TBD |
| tests/test_gui_smoke.py | 1365 | `"model_backend": main_module.EXTERNAL_BACKEND_ID,` | - | TBD |
| tests/test_gui_smoke.py | 1383 | `model_dialog.child_backend_combo.findData(main_module.CHILD_BACKEND_EXTERNAL)` | - | TBD |
| tests/test_gui_smoke.py | 1401 | `"expert_backend": main_module.ROUTE_BACKEND_HEATMAP_BLINK,` | - | TBD |
| tests/test_gui_smoke.py | 1412 | `self.assertEqual(context["parent_model_source"], main_module.PARENT_BACKEND_EXTERNAL)` | - | TBD |
| tests/test_gui_smoke.py | 1413 | `self.assertEqual(context["default_child_expert"], main_module.CHILD_BACKEND_EXTERNAL)` | - | TBD |
| tests/test_gui_smoke.py | 1414 | `self.assertEqual(context["default_child_route_backend"], main_module.ROUTE_BACKEND_EXTERNAL_BLINK)` | - | TBD |
| tests/test_gui_smoke.py | 1427 | `compact = window._compact_agent_context(context)` | `_compact_agent_context` | TBD |
| tests/test_gui_smoke.py | 1431 | `self.assertEqual(compact["default_child_expert"], main_module.CHILD_BACKEND_EXTERNAL)` | - | TBD |
| tests/test_gui_smoke.py | 1451 | `tif_compact = window._compact_agent_context(` | `_compact_agent_context` | TBD |
| tests/test_gui_smoke.py | 1539 | `pdf_compact = window._compact_agent_context(` | `_compact_agent_context` | TBD |
| tests/test_gui_smoke.py | 1589 | `with patch.object(main_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1613 | `with patch.object(main_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1633 | `with patch.object(main_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1662 | `with patch.object(main_module.QMessageBox, "information", return_value=main_module.QMessageBox.Ok):` | - | TBD |
| tests/test_gui_smoke.py | 1669 | `with patch.object(main_module.QFileDialog, "getSaveFileName", return_value=(str(export_path), "JSON (*.json)")), \` | - | TBD |
| tests/test_gui_smoke.py | 1670 | `patch.object(main_module.QMessageBox, "information", return_value=main_module.QMessageBox.Ok):` | - | TBD |
| tests/test_gui_smoke.py | 1687 | `with patch.object(main_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1714 | `with patch.object(main_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1737 | `with patch.object(main_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1781 | `with patch.object(main_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1790 | `self.assertEqual(header.data(main_module.Qt.UserRole + 1), "original")` | - | TBD |
| tests/test_gui_smoke.py | 1817 | `with patch.object(main_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1840 | `with patch.object(main_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1864 | `with patch.object(main_module.QFileDialog, "getExistingDirectory", fake_get_existing_directory), \` | - | TBD |
| tests/test_gui_smoke.py | 1865 | `patch.object(main_module.QInputDialog, "getText", return_value=("review", True)), \` | - | TBD |
| tests/test_gui_smoke.py | 1882 | `ant_project_dir = Path(main_module.PACKAGE_DIR)` | - | TBD |
| tests/test_gui_smoke.py | 1884 | `self.assertEqual(Path(window._default_open_project_dir()), self.project_dir / "TaxaMask_outputs")` | `_default_open_project_dir` | TBD |
| tests/test_gui_smoke.py | 1888 | `self.assertEqual(Path(window._default_2d_export_dir()), project_dir / "exports")` | `_default_2d_export_dir` | TBD |
| tests/test_gui_smoke.py | 1889 | `self.assertEqual(Path(window._vlm_preannotation_artifacts_dir()), project_dir / "vlm_preannotation")` | `_vlm_preannotation_artifacts_dir` | TBD |
| tests/test_gui_smoke.py | 1891 | `dialog = main_module.ExportDialog(window, "en", default_dir=window._default_2d_export_dir())` | `_default_2d_export_dir` | TBD |
| tests/test_gui_smoke.py | 1909 | `window._create_vlm_progress_dialog()` | `_create_vlm_progress_dialog` | TBD |
| tests/test_gui_smoke.py | 1911 | `window._advance_vlm_progress("prepare")` | `_advance_vlm_progress` | TBD |
| tests/test_gui_smoke.py | 1915 | `self.assertEqual(progress.windowModality(), main_module.Qt.NonModal)` | - | TBD |
| tests/test_gui_smoke.py | 1929 | `window._mark_current_vlm_image_done("done")` | `_mark_current_vlm_image_done` | TBD |
| tests/test_gui_smoke.py | 1961 | `original_refresh = window._refresh_vlm_canvas_if_current` | `_refresh_vlm_canvas_if_current` | TBD |
| tests/test_gui_smoke.py | 1962 | `window._refresh_vlm_canvas_if_current = lambda path: (refresh_calls.append(path), original_refresh(path))` | `_refresh_vlm_canvas_if_current` | TBD |
| tests/test_gui_smoke.py | 1965 | `window._on_vlm_preannotation_image_result(` | `_on_vlm_preannotation_image_result` | TBD |
| tests/test_gui_smoke.py | 2020 | `window._on_vlm_preannotation_image_result(` | `_on_vlm_preannotation_image_result` | TBD |
| tests/test_gui_smoke.py | 2064 | `window._on_vlm_preannotation_image_result(` | `_on_vlm_preannotation_image_result` | TBD |
| tests/test_gui_smoke.py | 2104 | `window._create_vlm_progress_dialog()` | `_create_vlm_progress_dialog` | TBD |
| tests/test_gui_smoke.py | 2112 | `window._on_vlm_preannotation_image_result(` | `_on_vlm_preannotation_image_result` | TBD |
| tests/test_gui_smoke.py | 2163 | `window._set_panel_split_review(str(manual_image), "manual_required", reason="hard_seam_panel_split")` | `_set_panel_split_review` | TBD |
| tests/test_gui_smoke.py | 2174 | `batch_paths = window._vlm_image_paths_for_scope(window._current_vlm_batch_scope())` | `_current_vlm_batch_scope`, `_vlm_image_paths_for_scope` | TBD |
| tests/test_gui_smoke.py | 2177 | `current_paths = window._vlm_image_paths_for_scope("current_image")` | `_vlm_image_paths_for_scope` | TBD |
| tests/test_gui_smoke.py | 2182 | `groups = window._project_image_groups()` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 2220 | `window._on_vlm_preannotation_image_result(` | `_on_vlm_preannotation_image_result` | TBD |
| tests/test_gui_smoke.py | 2263 | `window._refresh_vlm_canvas_if_current(image_key)` | `_refresh_vlm_canvas_if_current` | TBD |
| tests/test_gui_smoke.py | 2290 | `ok, mode = window._apply_vlm_candidate(` | `_apply_vlm_candidate` | TBD |
| tests/test_gui_smoke.py | 2346 | `ok, mode = window._apply_vlm_candidate(` | `_apply_vlm_candidate` | TBD |
| tests/test_gui_smoke.py | 2380 | `window._same_project_image_path(` | `_same_project_image_path` | TBD |
| tests/test_gui_smoke.py | 2381 | `window.file_list.currentItem().data(main_module.Qt.UserRole),` | - | TBD |
| tests/test_gui_smoke.py | 2395 | `for index in range(main_module.BACKGROUND_IMAGE_IMPORT_THRESHOLD):` | - | TBD |
| tests/test_gui_smoke.py | 2428 | `started = window._start_image_import(image_paths)` | `_start_image_import` | TBD |
| tests/test_gui_smoke.py | 2454 | `window.model_backend = main_module.EXTERNAL_BACKEND_ID` | - | TBD |
| tests/test_gui_smoke.py | 2506 | `with patch.object(main_module, "_runtime_parent_backend", lambda *_args, **_kwargs: main_module.EXTERNAL_BACKEND_ID), \` | - | TBD |
| tests/test_gui_smoke.py | 2507 | `patch.object(main_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes), \` | - | TBD |
| tests/test_gui_smoke.py | 2541 | `path = item.data(main_module.Qt.UserRole)` | - | TBD |
| tests/test_gui_smoke.py | 2554 | `with patch.object(main_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 2703 | `prompt = window._pdf_agent_prompt()` | `_pdf_agent_prompt` | TBD |
| tests/test_gui_smoke.py | 2856 | `window._inherit_crop_provenance(` | `_inherit_crop_provenance` | TBD |
| tests/test_gui_smoke.py | 2873 | `self.assertTrue(window._is_pdf_candidate_provenance(crop_provenance))` | `_is_pdf_candidate_provenance` | TBD |
| tests/test_gui_smoke.py | 2890 | `window._inherit_crop_provenance(` | `_inherit_crop_provenance` | TBD |
| tests/test_gui_smoke.py | 2907 | `self.assertTrue(window._is_split_crop_image(str(crop_image)))` | `_is_split_crop_image` | TBD |
| tests/test_gui_smoke.py | 2919 | `window._set_panel_split_review(str(parent_image), "manual_required", reason="hard_seam_panel_split")` | `_set_panel_split_review` | TBD |
| tests/test_gui_smoke.py | 2921 | `window._inherit_crop_provenance(` | `_inherit_crop_provenance` | TBD |
| tests/test_gui_smoke.py | 2938 | `self.assertFalse(window._needs_manual_panel_split(str(parent_image)))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 2939 | `self.assertFalse(window._needs_manual_panel_split(str(crop_image)))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 2964 | `window._set_panel_split_review(str(parent_image), "manual_required", reason="hard_seam_panel_split")` | `_set_panel_split_review` | TBD |
| tests/test_gui_smoke.py | 2966 | `self.assertTrue(window._has_split_crops_from_image(str(parent_image)))` | `_has_split_crops_from_image` | TBD |
| tests/test_gui_smoke.py | 2967 | `self.assertFalse(window._needs_manual_panel_split(str(parent_image)))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 2968 | `self.assertFalse(window._needs_manual_panel_split(str(crop_image)))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 2992 | `self.assertTrue(window._needs_manual_panel_split(str(image_path)))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 2998 | `self.assertFalse(window._needs_manual_panel_split(str(image_path)))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 3021 | `window._set_panel_split_review(str(image_a), "manual_required", reason="hard_seam_panel_split")` | `_set_panel_split_review` | TBD |
| tests/test_gui_smoke.py | 3022 | `window._set_panel_split_review(str(image_b), "manual_required", reason="hard_seam_panel_split")` | `_set_panel_split_review` | TBD |
| tests/test_gui_smoke.py | 3032 | `groups = window._project_image_groups()` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 3050 | `window._set_panel_split_review(str(image_path), "manual_done", reason="user_marked_done")` | `_set_panel_split_review` | TBD |
| tests/test_gui_smoke.py | 3052 | `self.assertEqual([Path(path).name for path in window._project_image_groups()["manual_done"]], [image_path.name])` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 3055 | `groups = window._project_image_groups()` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 3079 | `groups = window._project_image_groups()` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 3082 | `self.assertEqual(window._vlm_image_group_label("review_ready"), "Review Ready")` | `_vlm_image_group_label` | TBD |
| tests/test_gui_smoke.py | 3092 | `self.assertEqual(window._current_vlm_image_group(), "review_ready")` | `_current_vlm_image_group` | TBD |
| tests/test_gui_smoke.py | 3093 | `paths = window._vlm_image_paths_for_scope("image_group")` | `_vlm_image_paths_for_scope` | TBD |
| tests/test_gui_smoke.py | 3121 | `groups = window._project_image_groups()` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 3148 | `self.assertIn("review_ready", {group_id for group_id, _label in window._image_group_move_target_definitions()})` | `_image_group_move_target_definitions` | TBD |
| tests/test_gui_smoke.py | 3152 | `self.assertEqual(window._custom_image_group_definitions(), [])` | `_custom_image_group_definitions` | TBD |
| tests/test_gui_smoke.py | 3154 | `self.assertNotIn("review_ready", {group_id for group_id, _label in window._image_group_move_target_definitions()})` | `_image_group_move_target_definitions` | TBD |
| tests/test_gui_smoke.py | 3177 | `if item.data(main_module.Qt.UserRole) and _same_path(item.data(main_module.Qt.UserRole), image_a):` | - | TBD |
| tests/test_gui_smoke.py | 3231 | `self.assertTrue(window._is_split_crop_image(str(crop_image)))` | `_is_split_crop_image` | TBD |
| tests/test_gui_smoke.py | 3232 | `self.assertFalse(window._is_split_crop_image(str(unrelated_crop)))` | `_is_split_crop_image` | TBD |
| tests/test_gui_smoke.py | 3277 | `with patch.object(main_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 3278 | `with patch.object(main_module.QMessageBox, "information", lambda *args, **kwargs: None):` | - | TBD |
| tests/test_gui_smoke.py | 3304 | `self.assertTrue(window._is_split_crop_image(generated))` | `_is_split_crop_image` | TBD |
| tests/test_gui_smoke.py | 3305 | `self.assertFalse(window._needs_manual_panel_split(generated))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 3310 | `self.assertTrue(window._is_split_crop_image(generated))` | `_is_split_crop_image` | TBD |
| tests/test_gui_smoke.py | 3311 | `self.assertFalse(window._needs_manual_panel_split(generated))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 3316 | `groups = window._project_image_groups()` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 3362 | `with patch.object(main_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 3363 | `with patch.object(main_module.QMessageBox, "information", lambda *args, **kwargs: None):` | - | TBD |
| tests/test_gui_smoke.py | 3371 | `groups = window._project_image_groups()` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 3436 | `db_path, context, reason = window._resolve_current_literature_context()` | `_resolve_current_literature_context` | TBD |
| tests/test_gui_smoke.py | 3471 | `db_path, context, reason = window._resolve_current_literature_context()` | `_resolve_current_literature_context` | TBD |
| tests/test_gui_smoke.py | 3519 | `db_path, context, reason = window._resolve_current_literature_context()` | `_resolve_current_literature_context` | TBD |
| tests/test_gui_smoke.py | 3554 | `with patch.object(main_module.QFileDialog, "getOpenFileName", return_value=(str(literature_db), "SQLite Database (*.db)")):` | - | TBD |
| tests/test_gui_smoke.py | 3555 | `db_path, context, reason = window._choose_literature_db_for_current_taxon()` | `_choose_literature_db_for_current_taxon` | TBD |
| tests/test_gui_smoke.py | 3600 | `dialog = main_module.LiteratureDescriptionDialog(` | - | TBD |
| tests/test_gui_smoke.py | 3632 | `dialog = main_module.LiteratureDescriptionDialog(` | - | TBD |
| tests/test_gui_smoke.py | 3734 | `self.assertTrue(window._is_stl_project_file(stl_path))` | `_is_stl_project_file` | TBD |
| tests/test_gui_smoke.py | 3735 | `with patch.object(main_module.QFileDialog, "getOpenFileName", return_value=(stl_path, "JSON (*.json)")):` | - | TBD |
| tests/test_gui_smoke.py | 3746 | `self.assertEqual(window._active_recent_project_path(), os.path.abspath(stl_path))` | `_active_recent_project_path` | TBD |
| tests/test_gui_smoke.py | 3748 | `context = window._collect_image_workbench_agent_context()` | `_collect_image_workbench_agent_context` | TBD |
| tests/test_gui_smoke.py | 3752 | `self.assertIn("STL rendered-view project", window._start_console_project_summary()[0])` | `_start_console_project_summary` | TBD |
| tests/test_gui_smoke.py | 3753 | `self.assertIn("1 STL rendered 2D view", window._start_console_image_summary()[0])` | `_start_console_image_summary` | TBD |
| tests/test_reporting_routes.py | 45 | `from AntSleap.main import TrainingReportDialog` | - | TBD |
| tests/test_ui_localization.py | 22 | `from AntSleap.main import ExportDialog, BlinkEntryDialog, ModelSettingsDialog, RouteManagementPanel, TrainingPreflightDialog, TrainingReportDialog` | - | TBD |
| tests/test_ui_localization.py | 305 | `self.assertEqual(main_module.tr("Close", "zh"), "关闭")` | - | TBD |
| tests/test_ui_localization.py | 306 | `self.assertEqual(main_module.tr("Select Directory", "zh"), "选择目录")` | - | TBD |
| tests/test_ui_localization.py | 309 | `self.assertEqual(main_module.tr("Del", "zh"), "删除")` | - | TBD |
| tests/test_ui_localization.py | 310 | `self.assertEqual(main_module.tr("Locator switched to: {0}", "zh"), "定位器已切换为：{0}")` | - | TBD |
| tests/test_ui_localization.py | 312 | `main_module.tr("Delete the selected locator model file from disk.", "zh"),` | - | TBD |
| tests/test_ui_localization.py | 316 | `main_module.tr("Delete the selected segmenter model file from disk.", "zh"),` | - | TBD |
| tests/test_ui_localization.py | 553 | `self.assertEqual(len(locator_group.findChildren(main_module.QCheckBox)), 3)` | - | TBD |
| tests/test_ui_localization.py | 643 | `"model_backend": main_module.BUILTIN_BACKEND_ID,` | - | TBD |
| tests/test_ui_localization.py | 657 | `self.assertEqual(dialog.backend_combo.currentData(), main_module.EXTERNAL_BACKEND_ID)` | - | TBD |
| tests/test_ui_localization.py | 679 | `self.assertEqual(values_before_activation["model_backend"], main_module.BUILTIN_BACKEND_ID)` | - | TBD |
| tests/test_ui_localization.py | 691 | `self.assertEqual(values_after_activation["model_backend"], main_module.EXTERNAL_BACKEND_ID)` | - | TBD |
| tests/test_ui_localization.py | 710 | `"model_backend": main_module.BUILTIN_BACKEND_ID,` | - | TBD |
| tests/test_ui_localization.py | 745 | `self.assertEqual(dialog.backend_combo.currentData(), main_module.EXTERNAL_BACKEND_ID)` | - | TBD |
| tests/test_ui_localization.py | 748 | `self.assertEqual(dialog.child_backend_combo.itemText(dialog.child_backend_combo.findData(main_module.CHILD_BACKEND_EXTERNAL)), "Custom Child Extension")` | - | TBD |
| tests/test_ui_localization.py | 754 | `self.assertEqual(values["model_backend"], main_module.EXTERNAL_BACKEND_ID)` | - | TBD |
| tests/test_ui_localization.py | 774 | `"model_backend": main_module.EXTERNAL_BACKEND_ID,` | - | TBD |
| tests/test_ui_localization.py | 788 | `self.assertEqual(dialog.backend_combo.currentData(), main_module.EXTERNAL_BACKEND_ID)` | - | TBD |
| tests/test_ui_localization.py | 958 | `tabs = dialog.findChild(main_module.QTabWidget)` | - | TBD |
| tests/test_ui_localization.py | 959 | `overview_text = tabs.widget(0).findChild(main_module.QTextEdit).toPlainText()` | - | TBD |
| tests/test_ui_localization.py | 961 | `coverage_text = tabs.widget(1).findChild(main_module.QTextEdit).toPlainText()` | - | TBD |
| tests/test_ui_localization.py | 1026 | `main_module.MainWindow.clear_ai_labels(window)` | - | TBD |
| tests/test_ui_polish_scope.py | 955 | `preflight_dialog = main_module.TrainingPreflightDialog(preflight, parent=owner, lang="en")` | - | TBD |
| tests/test_ui_polish_scope.py | 956 | `entry_dialog = main_module.BlinkEntryDialog(` | - | TBD |
| tests/test_ui_polish_scope.py | 1014 | `patch.object(main_module.QTimer, "singleShot", lambda *args, **kwargs: None):` | - | TBD |
| tests/test_ui_polish_scope.py | 1015 | `return main_module.MainWindow()` | - | TBD |
| tests/test_ui_polish_scope.py | 1169 | `with patch.object(main_module.QMessageBox, "information", lambda *args, **kwargs: None):` | - | TBD |
| tests/test_ui_polish_scope.py | 1203 | `with patch.object(main_module.QMessageBox, "information", lambda *args, **kwargs: None):` | - | TBD |
| tests/test_ui_polish_scope.py | 1210 | `with patch.object(main_module.QMessageBox, "information", lambda *args, **kwargs: None):` | - | TBD |
| tests/test_ui_polish_scope.py | 1346 | `if item.data(main_module.Qt.UserRole + 1) == "original":` | - | TBD |
| tests/test_ui_polish_scope.py | 1352 | `window._handle_image_list_item_clicked(original_header)` | `_handle_image_list_item_clicked` | TBD |
| tests/test_ui_polish_scope.py | 1382 | `cached_state = window._image_list_state_cache` | `_image_list_state_cache` | TBD |
| tests/test_ui_polish_scope.py | 1389 | `if item.data(main_module.Qt.UserRole + 1) == "original":` | - | TBD |
| tests/test_ui_polish_scope.py | 1395 | `window._handle_image_list_item_clicked(original_header)` | `_handle_image_list_item_clicked` | TBD |
| tests/test_ui_polish_scope.py | 1398 | `self.assertIs(window._image_list_state_cache, cached_state)` | `_image_list_state_cache` | TBD |
| tests/test_ui_polish_scope.py | 1421 | `window._apply_literature_description(` | `_apply_literature_description` | TBD |
| tests/test_ui_polish_scope.py | 1479 | `self.assertEqual(head_item.data(0, main_module.Qt.UserRole), "Head")` | - | TBD |
| tests/test_ui_polish_scope.py | 1481 | `self.assertEqual(head_item.child(0).data(0, main_module.Qt.UserRole), "Mandible")` | - | TBD |
| tests/test_ui_polish_scope.py | 1484 | `self.assertIsNone(cross_region_item.data(0, main_module.Qt.UserRole))` | - | TBD |
| tests/test_ui_polish_scope.py | 1485 | `self.assertEqual(cross_region_item.child(0).data(0, main_module.Qt.UserRole), "Seta")` | - | TBD |
| tests/test_ui_polish_scope.py | 1489 | `self.assertEqual(window._current_part_name(), "Mandible")` | `_current_part_name` | TBD |
| tests/test_ui_polish_scope.py | 1494 | `self.assertIsNone(window._current_part_name())` | `_current_part_name` | TBD |
| tests/test_ui_polish_scope.py | 1538 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 1539 | `context = window._refresh_blink_refine_state()` | `_refresh_blink_refine_state` | TBD |
| tests/test_ui_polish_scope.py | 1572 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 1582 | `context = window._refresh_blink_refine_state()` | `_refresh_blink_refine_state` | TBD |
| tests/test_ui_polish_scope.py | 1608 | `self.assertEqual(window.part_list.topLevelItem(0).data(0, main_module.Qt.UserRole), "Head")` | - | TBD |
| tests/test_ui_polish_scope.py | 1611 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 1612 | `context = window._refresh_blink_refine_state()` | `_refresh_blink_refine_state` | TBD |
| tests/test_ui_polish_scope.py | 1627 | `self.assertEqual(window.part_list.topLevelItem(0).child(0).data(0, main_module.Qt.UserRole), "Mandible")` | - | TBD |
| tests/test_ui_polish_scope.py | 1651 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 1652 | `context = window._refresh_blink_refine_state()` | `_refresh_blink_refine_state` | TBD |
| tests/test_ui_polish_scope.py | 1670 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 1699 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 1722 | `window._select_part_in_tree("Head")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 1743 | `canvas = main_module.AnnotationCanvas()` | - | TBD |
| tests/test_ui_polish_scope.py | 1774 | `window._select_part_in_tree("Head")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 1778 | `with patch.object(main_module.QMessageBox, "information") as info:` | - | TBD |
| tests/test_ui_polish_scope.py | 1830 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 1899 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 1900 | `before_context = window._refresh_blink_refine_state()` | `_refresh_blink_refine_state` | TBD |
| tests/test_ui_polish_scope.py | 1906 | `after_context = window._refresh_blink_refine_state()` | `_refresh_blink_refine_state` | TBD |
| tests/test_ui_polish_scope.py | 1939 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 1940 | `context = window._refresh_blink_refine_state()` | `_refresh_blink_refine_state` | TBD |
| tests/test_ui_polish_scope.py | 1945 | `with patch.object(main_module.QMessageBox, "information") as info:` | - | TBD |
| tests/test_ui_polish_scope.py | 1951 | `window._refresh_blink_refine_state()` | `_refresh_blink_refine_state` | TBD |
| tests/test_ui_polish_scope.py | 1997 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 1998 | `context = window._refresh_blink_refine_state()` | `_refresh_blink_refine_state` | TBD |
| tests/test_ui_polish_scope.py | 2004 | `with patch.object(main_module.QMessageBox, "information") as info:` | - | TBD |
| tests/test_ui_polish_scope.py | 2062 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 2135 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 2137 | `with patch.object(main_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_ui_polish_scope.py | 2175 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 2176 | `with patch.object(main_module.QMessageBox, "information") as info:` | - | TBD |
| tests/test_ui_polish_scope.py | 2181 | `with patch.object(main_module.QMessageBox, "information") as info:` | - | TBD |
| tests/test_ui_polish_scope.py | 2217 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 2317 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 2358 | `window._connect_child_training_progress()` | `_connect_child_training_progress` | TBD |
| tests/test_ui_polish_scope.py | 2382 | `main_module.json.dumps(` | - | TBD |
| tests/test_ui_polish_scope.py | 2390 | `"parent_backend": main_module.PARENT_BACKEND_BUILTIN,` | - | TBD |
| tests/test_ui_polish_scope.py | 2400 | `main_module.json.dumps(` | - | TBD |
| tests/test_ui_polish_scope.py | 2406 | `"training_strategy": main_module.BLINK_STRATEGY_TWO_STAGE_FULL_THEN_INSIDE,` | - | TBD |
| tests/test_ui_polish_scope.py | 2431 | `dialog = main_module.TrainingResultBrowserDialog(reports, lang="en")` | - | TBD |
| tests/test_ui_polish_scope.py | 2467 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 2471 | `patch.object(main_module.QMessageBox, "information") as info:` | - | TBD |
| tests/test_ui_polish_scope.py | 2479 | `with patch.object(main_module.QMessageBox, "information") as info:` | - | TBD |
| tests/test_ui_polish_scope.py | 2501 | `return_value=main_module.QMessageBox.Yes,` | - | TBD |
| tests/test_ui_polish_scope.py | 2567 | `dialog = main_module.ModelSettingsDialog(` | - | TBD |
| tests/test_ui_polish_scope.py | 2606 | `self.assertIsNotNone(dialog.findChild(main_module.QToolButton, "modelSettingsVlmDetailToggle"))` | - | TBD |
| tests/test_ui_polish_scope.py | 2623 | `with patch.object(main_module.QDialog, "exec", return_value=main_module.QDialog.DialogCode.Accepted) as exec_dialog:` | - | TBD |
| tests/test_ui_polish_scope.py | 2626 | `with patch.object(model_settings_dataset_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_ui_polish_scope.py | 2632 | `self.assertIsInstance(dialog.spin_blink_auto_shrink_steps, main_module.NoWheelSpinBox)` | - | TBD |
| tests/test_ui_polish_scope.py | 2634 | `self.assertIsInstance(dialog.spin_vlm_concurrency, main_module.NoWheelSpinBox)` | - | TBD |
| tests/test_ui_polish_scope.py | 2674 | `spin = main_module.NoWheelSpinBox()` | - | TBD |
| tests/test_ui_polish_scope.py | 2682 | `slider = main_module.NoWheelSlider(main_module.Qt.Horizontal)` | - | TBD |
| tests/test_ui_polish_scope.py | 2736 | `return_value=main_module.QMessageBox.Yes,` | - | TBD |
| tests/test_ui_polish_scope.py | 2792 | `main_module.QInputDialog,` | - | TBD |
| tests/test_ui_polish_scope.py | 2817 | `dialog = main_module.ModelSettingsDialog(` | - | TBD |
| tests/test_ui_polish_scope.py | 2838 | `device_combo = runtime_group.findChild(main_module.QComboBox)` | - | TBD |
| tests/test_ui_polish_scope.py | 2846 | `checks = {check.text(): check for check in locator_group.findChildren(main_module.QCheckBox)}` | - | TBD |
| tests/test_ui_polish_scope.py | 2869 | `dialog = main_module.ModelSettingsDialog(` | - | TBD |
| tests/test_ui_polish_scope.py | 2986 | `saved, total = window._apply_prediction_to_project(image_key, prediction, only_new=True, save=False)` | `_apply_prediction_to_project` | TBD |
| tests/test_ui_polish_scope.py | 2998 | `saved, total = window._apply_prediction_to_project(` | `_apply_prediction_to_project` | TBD |
| tests/test_ui_polish_scope.py | 3036 | `ok, mode = window._apply_vlm_candidate(` | `_apply_vlm_candidate` | TBD |
| tests/test_ui_polish_scope.py | 3078 | `saved, total = window._apply_prediction_to_project(image_key, prediction, only_new=True, save=False)` | `_apply_prediction_to_project` | TBD |
| tests/test_ui_polish_scope.py | 3118 | `window._refresh_current_canvas_boxes()` | `_refresh_current_canvas_boxes` | TBD |
| tests/test_ui_polish_scope.py | 3148 | `ok, mode = window._apply_vlm_candidate(` | `_apply_vlm_candidate` | TBD |
| tests/test_ui_polish_scope.py | 3166 | `ok, mode = window._apply_vlm_candidate(` | `_apply_vlm_candidate` | TBD |
| tests/test_ui_polish_scope.py | 3203 | `context = window._collect_image_workbench_agent_context()` | `_collect_image_workbench_agent_context` | TBD |
| tests/test_ui_polish_scope.py | 3209 | `compact = window._compact_agent_context(context)` | `_compact_agent_context` | TBD |
| tests/test_ui_polish_scope.py | 3225 | `window._on_training_success()` | `_on_training_success` | TBD |
| tests/test_ui_polish_scope.py | 3307 | `main_module.QInputDialog,` | - | TBD |
| tests/test_ui_polish_scope.py | 3325 | `main_module.QInputDialog,` | - | TBD |
| tests/test_ui_polish_scope.py | 3349 | `return_value=main_module.QMessageBox.Yes,` | - | TBD |
| tests/test_ui_polish_scope.py | 3425 | `return_value=main_module.QMessageBox.Yes,` | - | TBD |
| tests/test_ui_polish_scope.py | 3453 | `return_value=main_module.QMessageBox.Yes,` | - | TBD |
| tests/test_ui_polish_scope.py | 3547 | `window._flush_pending_project_save()` | `_flush_pending_project_save` | TBD |
| tests/test_ui_polish_scope.py | 3685 | `if item.data(main_module.Qt.UserRole) == image_paths[0]:` | - | TBD |
| tests/test_ui_polish_scope.py | 3692 | `with patch.object(main_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes), \` | - | TBD |
| tests/test_ui_polish_scope.py | 3705 | `window.file_list.item(row).data(main_module.Qt.UserRole)` | - | TBD |
| tests/test_ui_polish_scope.py | 3707 | `if window.file_list.item(row).data(main_module.Qt.UserRole)` | - | TBD |
| tests/test_ui_polish_scope.py | 3744 | `if item.data(main_module.Qt.UserRole) == image_paths[1]:` | - | TBD |
| tests/test_ui_polish_scope.py | 3750 | `with patch.object(main_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_ui_polish_scope.py | 3755 | `self.assertEqual(window.file_list.currentItem().data(main_module.Qt.UserRole), image_paths[2])` | - | TBD |
| tests/test_ui_polish_scope.py | 3757 | `window.file_list.item(row).data(main_module.Qt.UserRole)` | - | TBD |
| tests/test_ui_polish_scope.py | 3759 | `if window.file_list.item(row).data(main_module.Qt.UserRole)` | - | TBD |
| tests/test_ui_polish_scope.py | 3796 | `if item.data(main_module.Qt.UserRole) == image_paths[2]:` | - | TBD |
| tests/test_ui_polish_scope.py | 3802 | `with patch.object(main_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_ui_polish_scope.py | 3807 | `self.assertEqual(window.file_list.currentItem().data(main_module.Qt.UserRole), image_paths[1])` | - | TBD |
| tests/test_ui_polish_scope.py | 3809 | `window.file_list.item(row).data(main_module.Qt.UserRole)` | - | TBD |
| tests/test_ui_polish_scope.py | 3811 | `if window.file_list.item(row).data(main_module.Qt.UserRole)` | - | TBD |
| tests/test_ui_polish_scope.py | 4009 | `return_value=main_module.QMessageBox.No,` | - | TBD |
| tests/test_ui_polish_scope.py | 4018 | `return_value=main_module.QMessageBox.Yes,` | - | TBD |
| tests/test_ui_polish_scope.py | 4061 | `return_value=main_module.QMessageBox.Yes,` | - | TBD |
| tests/test_ui_polish_scope.py | 4104 | `window.vlm_preannotation_prompt_profile = main_module.default_vlm_prompt_profile()` | - | TBD |
| tests/test_ui_polish_scope.py | 4110 | `return_value=main_module.QMessageBox.Yes,` | - | TBD |
| tests/test_ui_polish_scope.py | 4121 | `window._on_vlm_preannotation_finished()` | `_on_vlm_preannotation_finished` | TBD |
| tests/test_ui_polish_scope.py | 4162 | `window.vlm_preannotation_prompt_profile = main_module.default_vlm_prompt_profile()` | - | TBD |
| tests/test_ui_polish_scope.py | 4166 | `window._start_vlm_preannotation_workers()` | `_start_vlm_preannotation_workers` | TBD |
| tests/test_ui_polish_scope.py | 4271 | `return_value=main_module.QMessageBox.Yes,` | - | TBD |
| tests/test_ui_polish_scope.py | 4332 | `return_value=main_module.QMessageBox.Yes,` | - | TBD |
| tests/test_ui_polish_scope.py | 4397 | `self.assertFalse(window._flush_pending_project_save())` | `_flush_pending_project_save` | TBD |
| tests/test_ui_polish_scope.py | 4402 | `window._flush_pending_project_save(force=True)` | `_flush_pending_project_save` | TBD |
| tests/test_ui_polish_scope.py | 4513 | `window._on_vlm_preannotation_image_result(result)` | `_on_vlm_preannotation_image_result` | TBD |
