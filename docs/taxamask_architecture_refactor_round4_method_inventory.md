# TaxaMask Round 4 Main Window Method Inventory

由 `scripts/analyze_main_window_architecture.py` 生成。Stage 0 冻结当前责任、兼容入口和目标阶段，实施时必须结合真实调用复核。

## Metrics

| Metric | Value |
| --- | --- |
| main_physical_lines | 8394 |
| top_level_class_count | 1 |
| top_level_function_count | 0 |
| all_method_count | 351 |
| private_method_count | 246 |
| connection_count | 194 |
| source_state_assignment_lines | 188 |
| main_window_lines | 7892 |
| main_window_method_count | 351 |
| main_window_connection_count | 51 |
| main_window_init_lines | 13 |
| main_window_methods_ge_50 | 38 |
| main_window_methods_ge_100 | 8 |
| main_window_unique_state_fields | 92 |
| main_window_state_assignment_occurrences | 198 |
| main_import_site_count | 20 |
| key_test_reference_line_count | 328 |
| key_test_private_reference_occurrences | 146 |
| key_test_unique_private_references | 53 |
| async_entry_count | 16 |

## Top-level Classes

| Line | Size | Class | Methods | Connects | Refs | Stage |
| --- | --- | --- | --- | --- | --- | --- |
| 481 | 7892 | `MainWindow` | 351 | 51 | 33 | 3 |

## MainWindow Workflow Counts

| Workflow | Methods |
| --- | --- |
| annotation_sam | 20 |
| blink | 34 |
| dialog_settings | 36 |
| image_navigation | 61 |
| project_lifecycle | 52 |
| runtime_worker | 15 |
| shell_start_agent | 14 |
| tif_integration | 1 |
| training_model | 39 |
| unclassified | 30 |
| vlm_prediction_export | 49 |

## Compatibility Counts

| Compatibility | Methods |
| --- | --- |
| internal_or_unreferenced | 191 |
| public_or_source_compatibility | 95 |
| signal_compatibility | 11 |
| test_compatibility | 54 |

## MainWindow Methods

| Line | Size | Method | Workflow | Stage | Compatibility | Source refs | Test refs | Signal refs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 485 | 13 | `__init__` | unclassified | 8 | public_or_source_compatibility | 217 | 133 | 0 |
| 501 | 2 | `_default_outputs_root` | unclassified | 8 | public_or_source_compatibility | 3 | 2 | 0 |
| 504 | 4 | `_ensure_default_output_subdir` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 509 | 2 | `_default_2d_stl_projects_root` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 512 | 2 | `_default_tif_projects_root` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 515 | 2 | `_default_startup_project_dir` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 518 | 2 | `_startup_project_manifest_path` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 521 | 2 | `_startup_legacy_json_project_path` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 524 | 14 | `_open_or_create_startup_project` | project_lifecycle | 4 | public_or_source_compatibility | 1 | 0 | 0 |
| 539 | 4 | `_default_project_dialog_dir` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 544 | 5 | `_current_2d_project_dir` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 550 | 4 | `_default_2d_export_dir` | runtime_worker | 1 | test_compatibility | 0 | 2 | 0 |
| 555 | 4 | `_default_vlm_preannotation_dir` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 560 | 18 | `_default_open_project_dir` | project_lifecycle | 4 | test_compatibility | 0 | 1 | 0 |
| 579 | 8 | `_path_is_startup_project` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 588 | 5 | `_path_is_inside_program_package` | unclassified | 8 | public_or_source_compatibility | 3 | 0 | 0 |
| 594 | 8 | `open_last_project` | project_lifecycle | 4 | public_or_source_compatibility | 2 | 1 | 1 |
| 603 | 45 | `closeEvent` | project_lifecycle | 4 | public_or_source_compatibility | 13 | 0 | 0 |
| 649 | 10 | `_active_recent_project_path` | project_lifecycle | 4 | public_or_source_compatibility | 4 | 1 | 0 |
| 660 | 22 | `_shutdown_background_workers` | runtime_worker | 1 | public_or_source_compatibility | 1 | 0 | 0 |
| 683 | 3 | `destroy` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 687 | 5 | `_schedule_project_save` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 693 | 5 | `_defer_project_save_for_active_navigation` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 699 | 54 | `_flush_pending_project_save` | project_lifecycle | 4 | public_or_source_compatibility | 2 | 3 | 1 |
| 754 | 51 | `refresh_model_list` | training_model | 7 | public_or_source_compatibility | 1 | 0 | 0 |
| 806 | 5 | `_selected_locator_timestamp` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 812 | 4 | `_selected_locator_display_text` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 817 | 9 | `_parent_model_filename` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 827 | 40 | `_build_locator_combo_label` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 868 | 7 | `_build_segmenter_combo_label` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 876 | 5 | `_selected_segmenter_timestamp` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 882 | 2 | `_active_project_route_manifest` | dialog_settings | 2 | public_or_source_compatibility | 1 | 0 | 0 |
| 885 | 9 | `_active_model_profile_context` | dialog_settings | 2 | public_or_source_compatibility | 1 | 0 | 0 |
| 895 | 6 | `_active_external_backend_config` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 902 | 5 | `_selected_route_entry` | dialog_settings | 2 | public_or_source_compatibility | 7 | 0 | 0 |
| 908 | 5 | `_route_runtime_status` | runtime_worker | 1 | public_or_source_compatibility | 2 | 0 | 0 |
| 914 | 8 | `refresh_route_table` | dialog_settings | 2 | public_or_source_compatibility | 11 | 30 | 2 |
| 923 | 4 | `update_route_action_buttons` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 928 | 15 | `_refresh_project_bound_views` | project_lifecycle | 4 | public_or_source_compatibility | 2 | 0 | 0 |
| 944 | 5 | `_project_image_count` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 950 | 17 | `_prepare_image_list_for_project_open` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 968 | 12 | `_preload_2d_stl_models_after_open` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 981 | 5 | `_ensure_tab_visible` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 987 | 6 | `_remove_tab_if_present` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 994 | 29 | `_apply_project_mode_tabs` | shell_start_agent | 3 | public_or_source_compatibility | 3 | 0 | 0 |
| 1024 | 13 | `_is_tif_project_file` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 1038 | 11 | `_is_stl_project_file` | project_lifecycle | 4 | test_compatibility | 0 | 1 | 0 |
| 1050 | 7 | `_read_project_probe_payload` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 1058 | 6 | `_is_sqlite_project_manifest_payload` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 1065 | 2 | `_is_tif_sqlite_project_manifest_payload` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 1068 | 2 | `_is_2d_sqlite_project_manifest_payload` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 1071 | 15 | `_is_legacy_2d_json_project_payload` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 1087 | 2 | `_is_legacy_2d_json_project_file` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 1090 | 23 | `_candidate_manifest_paths_for_sqlite_database` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 1114 | 15 | `_manifest_for_sqlite_database_file` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 1130 | 3 | `_is_project_sqlite_database_file` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 1134 | 11 | `_active_sqlite_project_manager` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 1146 | 9 | `_flush_active_sqlite_project_before_maintenance` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 1156 | 6 | `_sqlite_maintenance_default_dir` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 1163 | 42 | `backup_current_sqlite_project` | project_lifecycle | 4 | test_compatibility | 0 | 1 | 0 |
| 1206 | 42 | `export_current_project_legacy_json` | runtime_worker | 1 | test_compatibility | 0 | 1 | 0 |
| 1249 | 23 | `open_current_sqlite_migration_report` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 1273 | 4 | `appoint_selected_route_expert` | blink | 6 | public_or_source_compatibility | 2 | 1 | 1 |
| 1278 | 4 | `toggle_selected_route_enabled` | dialog_settings | 2 | public_or_source_compatibility | 2 | 0 | 1 |
| 1283 | 4 | `delete_selected_route` | dialog_settings | 2 | public_or_source_compatibility | 2 | 2 | 1 |
| 1288 | 30 | `_log_route_usage_summary` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 1319 | 4 | `_locator_model_path` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 1324 | 4 | `_segmenter_model_path` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 1329 | 18 | `_apply_locator_selection_to_runtime` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 1348 | 2 | `_locator_selection_needs_legacy_confirmation` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 1351 | 20 | `_confirm_legacy_locator_selection_if_needed` | training_model | 7 | test_compatibility | 0 | 1 | 0 |
| 1372 | 5 | `_show_structured_training_preflight` | dialog_settings | 2 | test_compatibility | 0 | 1 | 0 |
| 1378 | 3 | `_is_locator_oom_error` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 1382 | 30 | `_ask_locator_oom_retry_resolution` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 1413 | 3 | `_is_parent_training_running` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 1417 | 4 | `_is_child_training_running` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 1422 | 2 | `_is_any_training_running` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 1425 | 19 | `_set_training_progress` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 1445 | 11 | `_connect_child_training_progress` | blink | 6 | test_compatibility | 0 | 1 | 0 |
| 1457 | 6 | `_on_child_training_result` | blink | 6 | signal_compatibility | 0 | 0 | 1 |
| 1464 | 3 | `_on_child_training_error` | blink | 6 | signal_compatibility | 0 | 0 | 1 |
| 1468 | 3 | `_on_child_training_cancelled` | blink | 6 | signal_compatibility | 0 | 0 | 1 |
| 1472 | 10 | `_on_child_training_finished` | blink | 6 | signal_compatibility | 0 | 0 | 1 |
| 1483 | 87 | `_launch_training_with_preflight` | dialog_settings | 2 | test_compatibility | 0 | 1 | 0 |
| 1571 | 15 | `_on_training_success` | training_model | 7 | signal_compatibility | 0 | 1 | 1 |
| 1587 | 13 | `_on_training_finished` | training_model | 7 | public_or_source_compatibility | 2 | 1 | 1 |
| 1601 | 38 | `_on_training_error` | training_model | 7 | public_or_source_compatibility | 2 | 0 | 1 |
| 1640 | 7 | `stop_training` | training_model | 7 | public_or_source_compatibility | 1 | 0 | 1 |
| 1648 | 21 | `_apply_segmenter_selection_to_runtime` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 1670 | 12 | `update_model_delete_button_states` | training_model | 7 | public_or_source_compatibility | 2 | 0 | 2 |
| 1683 | 33 | `_edit_parent_model_note` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 1717 | 2 | `edit_locator_model_note` | training_model | 7 | public_or_source_compatibility | 1 | 1 | 1 |
| 1720 | 2 | `edit_segmenter_model_note` | training_model | 7 | public_or_source_compatibility | 1 | 1 | 1 |
| 1723 | 36 | `on_locator_changed` | training_model | 7 | public_or_source_compatibility | 1 | 1 | 1 |
| 1760 | 26 | `delete_locator_model` | training_model | 7 | public_or_source_compatibility | 1 | 2 | 1 |
| 1787 | 3 | `on_segmenter_changed` | training_model | 7 | public_or_source_compatibility | 1 | 0 | 1 |
| 1791 | 26 | `delete_segmenter_model` | training_model | 7 | public_or_source_compatibility | 1 | 1 | 1 |
| 1818 | 3 | `on_model_changed` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 1822 | 29 | `create_menus` | shell_start_agent | 3 | public_or_source_compatibility | 3 | 0 | 0 |
| 1852 | 21 | `new_project` | project_lifecycle | 4 | public_or_source_compatibility | 1 | 1 | 0 |
| 1874 | 22 | `new_tif_project` | project_lifecycle | 4 | public_or_source_compatibility | 1 | 0 | 0 |
| 1897 | 9 | `_ensure_tif_project_open` | project_lifecycle | 4 | public_or_source_compatibility | 6 | 0 | 0 |
| 1907 | 30 | `import_tif_stack_action` | tif_integration | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 1938 | 29 | `import_amira_directory_action` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 1968 | 28 | `import_stl_rendered_views_action` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 1997 | 6 | `open_pdf_evidence_tools` | project_lifecycle | 4 | public_or_source_compatibility | 1 | 2 | 0 |
| 2004 | 41 | `open_pdf_multimodal_api_settings` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 2046 | 19 | `_choose_project_template` | project_lifecycle | 4 | test_compatibility | 0 | 1 | 0 |
| 2066 | 12 | `open_project` | project_lifecycle | 4 | public_or_source_compatibility | 3 | 1 | 1 |
| 2079 | 12 | `_confirm_legacy_2d_json_migration` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 2092 | 9 | `_existing_sqlite_manifest_for_legacy_json` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 2102 | 11 | `_confirm_open_existing_sqlite_migration` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 2114 | 12 | `_confirm_legacy_tif_json_migration` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 2127 | 11 | `_existing_tif_sqlite_manifest_for_legacy_json` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 2139 | 11 | `_confirm_open_existing_tif_sqlite_migration` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 2151 | 41 | `_migrate_legacy_2d_project_with_progress` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 2193 | 41 | `_migrate_legacy_tif_project_with_progress` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 2235 | 150 | `open_project_path` | project_lifecycle | 4 | public_or_source_compatibility | 2 | 14 | 0 |
| 2386 | 10 | `_format_relocation_preview` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 2397 | 54 | `check_relocate_project_images` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 2452 | 6 | `_part_item_name` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 2459 | 2 | `_current_part_name` | unclassified | 8 | public_or_source_compatibility | 1 | 5 | 0 |
| 2462 | 15 | `_workbench_parent_parts` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 2478 | 3 | `_is_parent_part` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 2482 | 23 | `_part_tree_parent_for` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 2506 | 18 | `_route_parents_for_child` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 2525 | 25 | `_resolve_child_parent` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 2551 | 15 | `_parent_context_box` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 2567 | 5 | `_current_shrink_loose_boxes` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 2573 | 28 | `_auto_boxes_for_canvas` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 2602 | 10 | `_refresh_current_canvas_boxes` | annotation_sam | 6 | test_compatibility | 0 | 1 | 0 |
| 2613 | 15 | `_route_entry_for_context` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 2629 | 26 | `_route_expert_status` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 2656 | 73 | `_current_blink_context` | blink | 6 | public_or_source_compatibility | 1 | 0 | 0 |
| 2730 | 10 | `_parent_box_aspect_ratio` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 2741 | 24 | `_parent_context_options` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 2766 | 15 | `_refresh_annotation_box_constraints` | annotation_sam | 6 | public_or_source_compatibility | 1 | 0 | 1 |
| 2782 | 8 | `_active_box_tool_role` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 2791 | 6 | `_refresh_blink_refine_state` | blink | 6 | public_or_source_compatibility | 1 | 9 | 0 |
| 2798 | 7 | `_append_part_tree_item` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 2806 | 22 | `_select_part_in_tree` | unclassified | 8 | test_compatibility | 0 | 18 | 0 |
| 2829 | 17 | `_first_selectable_part_item` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 2847 | 75 | `_refresh_part_tree` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 2923 | 8 | `add_taxonomy_part` | image_navigation | 5 | public_or_source_compatibility | 2 | 29 | 1 |
| 2932 | 7 | `_count_ai_labels_for_images` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 2940 | 67 | `_choose_clear_ai_scope` | unclassified | 8 | test_compatibility | 0 | 1 | 0 |
| 3008 | 41 | `rename_taxonomy_part` | image_navigation | 5 | public_or_source_compatibility | 2 | 3 | 1 |
| 3050 | 13 | `remove_taxonomy_part` | image_navigation | 5 | public_or_source_compatibility | 2 | 6 | 1 |
| 3064 | 55 | `clear_ai_labels` | unclassified | 8 | public_or_source_compatibility | 1 | 2 | 1 |
| 3120 | 6 | `on_global_labels_updated` | unclassified | 8 | public_or_source_compatibility | 1 | 0 | 1 |
| 3127 | 190 | `refresh_ui` | unclassified | 8 | public_or_source_compatibility | 2 | 0 | 0 |
| 3318 | 78 | `_update_blink_refine_panel` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 3397 | 39 | `_update_blink_parent_context_combo` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 3437 | 51 | `open_general_settings` | dialog_settings | 2 | public_or_source_compatibility | 2 | 0 | 1 |
| 3489 | 129 | `open_stl_model_settings` | dialog_settings | 2 | public_or_source_compatibility | 3 | 0 | 0 |
| 3619 | 2 | `open_settings` | dialog_settings | 2 | public_or_source_compatibility | 1 | 0 | 0 |
| 3622 | 15 | `open_tif_model_settings` | dialog_settings | 2 | public_or_source_compatibility | 2 | 0 | 0 |
| 3638 | 15 | `change_language` | shell_start_agent | 3 | public_or_source_compatibility | 4 | 8 | 0 |
| 3654 | 28 | `change_theme` | shell_start_agent | 3 | public_or_source_compatibility | 2 | 0 | 0 |
| 3683 | 15 | `update_widget_themes` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 3699 | 66 | `update_button_themes` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 3765 | 4 | `add_images` | image_navigation | 5 | public_or_source_compatibility | 8 | 36 | 1 |
| 3770 | 94 | `_start_image_import` | shell_start_agent | 3 | test_compatibility | 0 | 1 | 0 |
| 3865 | 5 | `_set_image_import_controls_enabled` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 3871 | 20 | `open_cropper` | project_lifecycle | 4 | public_or_source_compatibility | 1 | 0 | 1 |
| 3892 | 8 | `_is_split_crop_image` | image_navigation | 5 | test_compatibility | 0 | 5 | 0 |
| 3901 | 15 | `_is_hard_joined_candidate_crop` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 3917 | 17 | `_looks_like_panel_crop_path` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 3935 | 26 | `_has_split_crops_from_image` | image_navigation | 5 | test_compatibility | 0 | 1 | 0 |
| 3962 | 10 | `_needs_manual_panel_split` | image_navigation | 5 | test_compatibility | 0 | 8 | 0 |
| 3973 | 8 | `_is_manual_panel_split_done` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 3982 | 10 | `_set_panel_split_review` | image_navigation | 5 | test_compatibility | 0 | 6 | 0 |
| 3993 | 7 | `_clear_panel_split_review` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 4001 | 8 | `_builtin_image_group_definitions` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 4010 | 16 | `_custom_image_group_definitions` | image_navigation | 5 | test_compatibility | 0 | 1 | 0 |
| 4027 | 2 | `_all_image_group_definitions` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 4030 | 19 | `_training_scope_group_definitions` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 4050 | 24 | `_populate_training_scope_combo` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 4075 | 5 | `_refresh_training_scope_combo` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 4081 | 16 | `_selected_training_scope_payload` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 4098 | 13 | `_populate_vlm_image_group_combo` | vlm_prediction_export | 7 | public_or_source_compatibility | 3 | 0 | 0 |
| 4112 | 5 | `_refresh_vlm_image_group_combo` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 4118 | 6 | `_image_group_display_name` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 4125 | 2 | `_custom_image_group_ids` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 4128 | 9 | `_image_group_move_target_definitions` | image_navigation | 5 | test_compatibility | 0 | 2 | 0 |
| 4138 | 45 | `_remove_empty_custom_image_groups` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 4184 | 13 | `_safe_custom_image_group_id` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 4198 | 34 | `create_custom_image_group` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 4233 | 10 | `_set_image_manual_group` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 4244 | 15 | `move_images_to_group` | image_navigation | 5 | public_or_source_compatibility | 1 | 7 | 1 |
| 4260 | 10 | `clear_selected_custom_image_group` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 4271 | 10 | `_short_progress_path` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 4282 | 13 | `_prepare_progress_dialog` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 4296 | 6 | `_candidate_panel_split_sources` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 4303 | 131 | `batch_split_panel_images` | image_navigation | 5 | public_or_source_compatibility | 1 | 2 | 1 |
| 4435 | 22 | `_save_detected_panel_crops` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 4458 | 10 | `_next_panel_crop_path` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 4469 | 32 | `_inherit_crop_provenance` | image_navigation | 5 | test_compatibility | 0 | 3 | 0 |
| 4502 | 9 | `_selected_image_paths` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 4512 | 8 | `_set_selected_panel_split_status` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 4521 | 2 | `mark_selected_manual_split_done` | unclassified | 8 | test_compatibility | 0 | 2 | 0 |
| 4524 | 2 | `mark_selected_manual_split_needed` | unclassified | 8 | test_compatibility | 0 | 1 | 0 |
| 4527 | 8 | `clear_selected_split_status` | unclassified | 8 | test_compatibility | 0 | 1 | 0 |
| 4536 | 23 | `show_file_list_context_menu` | shell_start_agent | 3 | public_or_source_compatibility | 1 | 1 | 1 |
| 4560 | 7 | `_move_selected_images_to_new_group` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 4568 | 60 | `remove_selected_images` | image_navigation | 5 | test_compatibility | 0 | 4 | 0 |
| 4629 | 95 | `refresh_file_list` | image_navigation | 5 | public_or_source_compatibility | 2 | 41 | 0 |
| 4725 | 4 | `_image_has_review_content` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 4730 | 19 | `_set_image_list_item_status` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 4750 | 41 | `_refresh_current_image_list_status` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 4792 | 6 | `_refresh_image_list_status_or_rebuild` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 4799 | 7 | `_image_list_path_identity` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 4807 | 10 | `_visible_image_list_paths` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 4818 | 27 | `_replacement_image_after_removal` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 4846 | 61 | `_remove_visible_image_list_items` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 4908 | 10 | `_filtered_group_definitions_after_removal` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 4919 | 14 | `_refresh_visible_image_group_header_counts` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 4934 | 31 | `_select_first_visible_image_after_removal` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 4966 | 26 | `_build_image_list_state` | image_navigation | 5 | test_compatibility | 0 | 1 | 0 |
| 4993 | 12 | `_handle_image_list_item_clicked` | image_navigation | 5 | public_or_source_compatibility | 1 | 2 | 1 |
| 5006 | 26 | `eventFilter` | unclassified | 8 | public_or_source_compatibility | 2 | 3 | 0 |
| 5033 | 35 | `_should_use_image_list_arrow_navigation` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 5069 | 21 | `_select_adjacent_image` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 5091 | 55 | `_collect_blink_roi_candidates` | blink | 6 | test_compatibility | 0 | 4 | 0 |
| 5147 | 39 | `on_file_selected` | unclassified | 8 | public_or_source_compatibility | 1 | 0 | 1 |
| 5187 | 11 | `on_part_selected` | unclassified | 8 | public_or_source_compatibility | 3 | 0 | 1 |
| 5199 | 90 | `launch_blink_from_workbench` | blink | 6 | public_or_source_compatibility | 2 | 4 | 1 |
| 5290 | 8 | `on_genus_changed` | image_navigation | 5 | public_or_source_compatibility | 1 | 0 | 1 |
| 5299 | 9 | `update_db_description` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 5309 | 5 | `_current_taxon_text` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 5315 | 8 | `_literature_source_taxon` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 5324 | 19 | `_set_current_image_taxon_from_literature` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 5344 | 21 | `_candidate_literature_db_paths` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 5366 | 55 | `_project_literature_db_paths` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 5422 | 39 | `_resolve_current_literature_context` | dialog_settings | 2 | test_compatibility | 0 | 3 | 0 |
| 5462 | 27 | `_resolve_literature_context_from_selected_db` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 5490 | 23 | `_choose_literature_db_for_current_taxon` | dialog_settings | 2 | test_compatibility | 0 | 1 | 0 |
| 5514 | 22 | `_literature_db_matches_image_source` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 5537 | 42 | `open_literature_description_dialog` | dialog_settings | 2 | public_or_source_compatibility | 1 | 0 | 1 |
| 5580 | 22 | `_open_literature_description_dialog_with_context` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 5603 | 24 | `_apply_literature_description` | dialog_settings | 2 | test_compatibility | 0 | 1 | 0 |
| 5628 | 15 | `_ensure_workbench_description_visible` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 5644 | 2 | `on_enhancement_changed` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 5647 | 16 | `on_tool_changed` | annotation_sam | 6 | public_or_source_compatibility | 8 | 8 | 6 |
| 5664 | 23 | `on_blink_parent_context_changed` | blink | 6 | public_or_source_compatibility | 1 | 2 | 1 |
| 5688 | 2 | `on_magic_wand_clicked` | annotation_sam | 6 | public_or_source_compatibility | 1 | 0 | 1 |
| 5691 | 2 | `on_magic_box_completed` | annotation_sam | 6 | public_or_source_compatibility | 1 | 1 | 1 |
| 5694 | 2 | `_sam_worker_ready` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 5697 | 2 | `_on_sam_model_loaded` | annotation_sam | 6 | signal_compatibility | 0 | 0 | 1 |
| 5700 | 18 | `_begin_sam_prompt` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 5719 | 6 | `_request_sam_point` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 5726 | 6 | `_request_sam_box` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 5733 | 34 | `on_annotation_box_completed` | annotation_sam | 6 | public_or_source_compatibility | 1 | 3 | 1 |
| 5768 | 2 | `_warn_blink_context` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 5771 | 12 | `_active_child_blink_context` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 5784 | 43 | `run_blink_child_auto_annotate` | blink | 6 | public_or_source_compatibility | 1 | 4 | 1 |
| 5828 | 9 | `_load_blink_refiner_class` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 5838 | 11 | `_active_blink_auto_shrink_steps` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 5850 | 14 | `_blink_parent_context_for_image` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 5865 | 41 | `_prepared_blink_auto_shrink_images` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 5907 | 38 | `_generate_blink_shrink_for_image` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 5946 | 42 | `run_blink_auto_shrink` | blink | 6 | public_or_source_compatibility | 1 | 3 | 1 |
| 5989 | 90 | `run_blink_batch_auto_shrink` | blink | 6 | public_or_source_compatibility | 1 | 1 | 1 |
| 6080 | 66 | `train_current_blink_expert` | blink | 6 | public_or_source_compatibility | 1 | 3 | 1 |
| 6147 | 10 | `stop_current_blink_expert_training` | blink | 6 | public_or_source_compatibility | 1 | 1 | 1 |
| 6158 | 18 | `open_current_route_expert_settings` | blink | 6 | public_or_source_compatibility | 1 | 0 | 1 |
| 6177 | 10 | `on_sam_mask_generated` | annotation_sam | 6 | signal_compatibility | 0 | 0 | 1 |
| 6188 | 7 | `on_sam_prompt_failed` | annotation_sam | 6 | signal_compatibility | 0 | 0 | 1 |
| 6196 | 23 | `on_polygon_completed` | annotation_sam | 6 | public_or_source_compatibility | 1 | 4 | 1 |
| 6220 | 7 | `toggle_morphometrics` | unclassified | 8 | public_or_source_compatibility | 1 | 0 | 1 |
| 6228 | 9 | `on_scale_defined` | annotation_sam | 6 | public_or_source_compatibility | 1 | 0 | 1 |
| 6238 | 16 | `update_measurements` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 6255 | 87 | `run_training` | training_model | 7 | public_or_source_compatibility | 2 | 2 | 1 |
| 6343 | 2 | `_external_backend_runner` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 6346 | 27 | `_sync_blink_lab_model_profile_defaults` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 6374 | 51 | `run_external_training` | training_model | 7 | test_compatibility | 0 | 1 | 0 |
| 6426 | 3 | `show_training_report` | dialog_settings | 2 | signal_compatibility | 0 | 0 | 1 |
| 6430 | 26 | `_candidate_training_experiment_dirs` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 6457 | 10 | `_resolve_report_artifact_path` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 6468 | 11 | `_training_report_time_label` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 6480 | 66 | `_training_report_payload_from_summary` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 6547 | 26 | `discover_training_reports` | dialog_settings | 2 | test_compatibility | 0 | 1 | 0 |
| 6574 | 8 | `open_training_report_payload` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 6583 | 17 | `open_training_results_browser` | project_lifecycle | 4 | public_or_source_compatibility | 1 | 0 | 1 |
| 6601 | 37 | `_extract_prediction_payload` | vlm_prediction_export | 7 | public_or_source_compatibility | 2 | 0 | 0 |
| 6639 | 12 | `_is_unconfirmed_ai_draft` | vlm_prediction_export | 7 | public_or_source_compatibility | 2 | 0 | 0 |
| 6652 | 13 | `_auto_box_meta_for_part` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 6666 | 3 | `_auto_box_source_for_part` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 6670 | 3 | `_auto_box_review_status_for_part` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 6674 | 5 | `_auto_annotation_source_meta` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 6680 | 15 | `_can_replace_existing_auto_annotation` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 6696 | 33 | `_apply_prediction_to_project` | vlm_prediction_export | 7 | test_compatibility | 0 | 3 | 0 |
| 6730 | 5 | `_vlm_api_settings_path` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 6736 | 40 | `_vlm_api_config_from_pdf_widget` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 6777 | 8 | `_vlm_preannotation_artifacts_dir` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 6786 | 4 | `_current_vlm_target_parts` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 6791 | 4 | `_current_vlm_processing_scope` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 6796 | 3 | `_current_vlm_batch_scope` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 6800 | 4 | `_current_vlm_image_group` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 6805 | 8 | `_current_vlm_concurrency` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 6814 | 5 | `_current_vlm_prompt_profile` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 6820 | 2 | `_vlm_image_group_label` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 6823 | 57 | `_panel_crop_identity_index` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 6881 | 57 | `_project_image_groups` | project_lifecycle | 4 | test_compatibility | 0 | 8 | 0 |
| 6939 | 10 | `_vlm_candidate_source_meta` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 6950 | 19 | `_record_sqlite_vlm_image_result` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 6970 | 13 | `_finish_sqlite_vlm_run` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 6984 | 7 | `_vlm_image_paths_for_scope` | vlm_prediction_export | 7 | test_compatibility | 0 | 3 | 0 |
| 6992 | 2 | `_vlm_image_paths_from_settings` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 6995 | 11 | `_same_project_image_path` | project_lifecycle | 4 | test_compatibility | 0 | 1 | 0 |
| 7007 | 5 | `_project_image_key_for_path` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 7013 | 7 | `_vlm_part_list_text` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 7021 | 18 | `_vlm_part_coverage` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 7040 | 15 | `_log_vlm_part_coverage` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 7056 | 2 | `run_vlm_preannotation_current` | vlm_prediction_export | 7 | public_or_source_compatibility | 1 | 0 | 1 |
| 7059 | 2 | `run_vlm_preannotation_batch` | vlm_prediction_export | 7 | public_or_source_compatibility | 1 | 0 | 1 |
| 7062 | 121 | `run_vlm_preannotation_from_settings` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 7184 | 42 | `request_stop_vlm_preannotation` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 7227 | 11 | `_active_vlm_preannotation_threads` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 7239 | 14 | `_start_vlm_preannotation_workers` | runtime_worker | 1 | test_compatibility | 0 | 1 | 0 |
| 7254 | 53 | `_start_next_vlm_preannotation_image` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 7308 | 48 | `_apply_vlm_candidate` | vlm_prediction_export | 7 | test_compatibility | 0 | 5 | 0 |
| 7357 | 6 | `_refresh_vlm_canvas_if_current` | vlm_prediction_export | 7 | test_compatibility | 0 | 3 | 0 |
| 7364 | 34 | `_reload_current_image_for_workbench` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 7399 | 111 | `_on_vlm_preannotation_image_result` | vlm_prediction_export | 7 | signal_compatibility | 0 | 6 | 1 |
| 7511 | 7 | `_vlm_progress_image_key` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 7519 | 20 | `_mark_current_vlm_image_done` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 7540 | 30 | `_set_vlm_progress_ui` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 7571 | 54 | `_create_vlm_progress_dialog` | vlm_prediction_export | 7 | test_compatibility | 0 | 2 | 0 |
| 7626 | 18 | `_advance_vlm_progress` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 7645 | 11 | `_on_vlm_preannotation_thread_step` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 7657 | 7 | `_complete_current_vlm_image_steps` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 7665 | 100 | `_finish_vlm_preannotation_run` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 7766 | 36 | `accept_current_image_ai_drafts` | vlm_prediction_export | 7 | public_or_source_compatibility | 1 | 3 | 1 |
| 7803 | 93 | `accept_batch_ai_drafts` | vlm_prediction_export | 7 | public_or_source_compatibility | 1 | 1 | 1 |
| 7897 | 3 | `_on_vlm_preannotation_error` | vlm_prediction_export | 7 | signal_compatibility | 0 | 0 | 1 |
| 7901 | 33 | `_on_vlm_preannotation_qthread_finished` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 7935 | 2 | `_on_vlm_preannotation_finished` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 7938 | 46 | `run_prediction` | vlm_prediction_export | 7 | public_or_source_compatibility | 2 | 2 | 1 |
| 7985 | 30 | `run_external_prediction` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8016 | 9 | `verify_current_image` | image_navigation | 5 | public_or_source_compatibility | 1 | 1 | 1 |
| 8026 | 100 | `_start_external_batch_inference` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 8127 | 74 | `run_batch_inference` | runtime_worker | 1 | public_or_source_compatibility | 1 | 1 | 1 |
| 8202 | 8 | `export_dataset` | runtime_worker | 1 | public_or_source_compatibility | 1 | 0 | 1 |
| 8211 | 75 | `_start_dataset_export` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 8287 | 23 | `init_sam` | annotation_sam | 6 | test_compatibility | 0 | 1 | 0 |
| 8311 | 13 | `ensure_sam_preloaded` | annotation_sam | 6 | test_compatibility | 0 | 6 | 0 |
| 8325 | 4 | `ensure_2d_stl_models_preloaded` | training_model | 7 | public_or_source_compatibility | 1 | 3 | 0 |
| 8330 | 17 | `ensure_locator_preloaded` | training_model | 7 | test_compatibility | 0 | 1 | 0 |
| 8348 | 22 | `_preload_engine_parts_model_async` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 8371 | 2 | `log` | unclassified | 8 | public_or_source_compatibility | 192 | 34 | 5 |

## MainWindow State Fields

| Field | Assignments | Lines | Target owner | Stage |
| --- | --- | --- | --- | --- |
| `_image_list_state_cache` | 5 | 952, 4795, 4758, 4622, 4640 | TBD | TBD |
| `_refreshing_part_tree` | 2 | 2852, 2911 | TBD | TBD |
| `_suppress_selection_save_flush` | 4 | 4955, 4942, 4962, 4949 | TBD | TBD |
| `_updating_blink_parent_context` | 2 | 3402, 3435 | TBD | TBD |
| `active_project_entry_path` | 6 | 1892, 1983, 2345, 1868, 2353, 2367 | TBD | TBD |
| `active_project_kind` | 6 | 1890, 1981, 2343, 1866, 2351, 2365 | TBD | TBD |
| `active_project_source_kind` | 6 | 1891, 1982, 2344, 1867, 2352, 2366 | TBD | TBD |
| `active_training_kind` | 2 | 6392, 1427 | TBD | TBD |
| `active_training_label` | 1 | 1429 | TBD | TBD |
| `blink_auto_shrink_steps` | 1 | 3538 | TBD | TBD |
| `blink_train_batch` | 1 | 3534 | TBD | TBD |
| `blink_train_epochs` | 1 | 3534 | TBD | TBD |
| `blink_train_input_size` | 1 | 3537 | TBD | TBD |
| `blink_train_lr` | 1 | 3535 | TBD | TBD |
| `blink_train_weight_decay` | 1 | 3536 | TBD | TBD |
| `blink_training_strategy` | 1 | 3539 | TBD | TBD |
| `child_training_cancel_requested` | 4 | 1469, 1480, 6110, 6152 | TBD | TBD |
| `child_training_failed` | 4 | 1458, 1465, 1479, 6109 | TBD | TBD |
| `current_blink_context` | 1 | 2793 | TBD | TBD |
| `current_image` | 7 | 959, 7370, 2446, 5170, 5853, 5856, 4619 | TBD | TBD |
| `current_lang` | 1 | 3639 | TBD | TBD |
| `current_theme` | 1 | 3656 | TBD | TBD |
| `dataset_export_thread` | 2 | 8236, 8279 | TBD | TBD |
| `external_backend_config` | 1 | 3549 | TBD | TBD |
| `external_batch_inference_failed` | 2 | 8036, 8095 | TBD | TBD |
| `external_batch_inference_progress_dialog` | 2 | 8056, 8109 | TBD | TBD |
| `external_batch_inference_saved_any` | 2 | 8037, 8091 | TBD | TBD |
| `external_batch_inference_thread` | 2 | 8068, 8111 | TBD | TBD |
| `external_training_failed` | 2 | 6391, 6405 | TBD | TBD |
| `external_training_thread` | 2 | 6397, 6414 | TBD | TBD |
| `image_import_progress_dialog` | 2 | 3809, 3852 | TBD | TBD |
| `image_import_thread` | 2 | 3812, 3856 | TBD | TBD |
| `inf_adapt` | 1 | 3543 | TBD | TBD |
| `inf_conf` | 1 | 3543 | TBD | TBD |
| `inf_noise_floor` | 1 | 3544 | TBD | TBD |
| `inf_pad` | 1 | 3544 | TBD | TBD |
| `inf_poly_epsilon` | 1 | 3545 | TBD | TBD |
| `inf_thread` | 1 | 8163 | TBD | TBD |
| `last_confirmed_locator_timestamp` | 3 | 1366, 1752, 1745 | TBD | TBD |
| `model_backend` | 1 | 3548 | TBD | TBD |
| `parent_box_aspect_ratios` | 2 | 2734, 3564 | TBD | TBD |
| `parent_training_cancel_requested` | 2 | 1530, 1644 | TBD | TBD |
| `parent_training_failed` | 3 | 1529, 1605, 1622 | TBD | TBD |
| `parts_model_preload_thread` | 1 | 8363 | TBD | TBD |
| `pending_sam_description` | 3 | 5716, 6184, 6192 | TBD | TBD |
| `pending_sam_image` | 3 | 5715, 6183, 6191 | TBD | TBD |
| `pending_sam_part` | 3 | 5714, 6182, 6190 | TBD | TBD |
| `pending_training_preflight` | 1 | 1517 | TBD | TBD |
| `project_autosave_delay_ms` | 1 | 3456 | TBD | TBD |
| `project_last_image_switch_at` | 1 | 696 | TBD | TBD |
| `project_save_context` | 3 | 751, 690, 705 | TBD | TBD |
| `project_save_pending` | 3 | 688, 750, 704 | TBD | TBD |
| `runtime_device` | 2 | 3461, 3547 | TBD | TBD |
| `sam_busy` | 3 | 5713, 6181, 6189 | TBD | TBD |
| `sam_thread` | 1 | 8294 | TBD | TBD |
| `sam_worker` | 1 | 8296 | TBD | TBD |
| `train_batch` | 1 | 3533 | TBD | TBD |
| `train_epochs` | 1 | 3533 | TBD | TBD |
| `train_lr` | 1 | 3542 | TBD | TBD |
| `train_wd` | 1 | 3542 | TBD | TBD |
| `trainer` | 2 | 1535, 1596 | TBD | TBD |
| `training_retry_requested` | 3 | 1528, 1604, 1613 | TBD | TBD |
| `vlm_preannotation_active_images` | 3 | 7162, 7762, 7289 | TBD | TBD |
| `vlm_preannotation_api_config` | 2 | 7143, 7167 | TBD | TBD |
| `vlm_preannotation_artifacts_dir` | 1 | 7166 | TBD | TBD |
| `vlm_preannotation_cancel_requested` | 3 | 7154, 7204, 7758 | TBD | TBD |
| `vlm_preannotation_cancelled_queued_images` | 3 | 7155, 7205, 7759 | TBD | TBD |
| `vlm_preannotation_completed_image_keys` | 3 | 7164, 7528, 7764 | TBD | TBD |
| `vlm_preannotation_completed_images` | 2 | 7160, 7530 | TBD | TBD |
| `vlm_preannotation_completed_steps` | 2 | 7158, 7629 | TBD | TBD |
| `vlm_preannotation_concurrency` | 1 | 7156 | TBD | TBD |
| `vlm_preannotation_current_image` | 4 | 7161, 7263, 7535, 7631 | TBD | TBD |
| `vlm_preannotation_current_image_steps_completed` | 3 | 7262, 7638, 7641 | TBD | TBD |
| `vlm_preannotation_image_step_counts` | 4 | 7163, 7763, 7293, 7636 | TBD | TBD |
| `vlm_preannotation_progress_bar` | 2 | 7622, 7756 | TBD | TBD |
| `vlm_preannotation_progress_dialog` | 2 | 7617, 7751 | TBD | TBD |
| `vlm_preannotation_progress_label` | 2 | 7620, 7754 | TBD | TBD |
| `vlm_preannotation_progress_notice_label` | 2 | 7619, 7753 | TBD | TBD |
| `vlm_preannotation_progress_path_label` | 2 | 7621, 7755 | TBD | TBD |
| `vlm_preannotation_progress_title_label` | 2 | 7618, 7752 | TBD | TBD |
| `vlm_preannotation_prompt_profile` | 1 | 7168 | TBD | TBD |
| `vlm_preannotation_queue` | 4 | 7151, 7206, 7261, 7925 | TBD | TBD |
| `vlm_preannotation_records` | 1 | 7150 | TBD | TBD |
| `vlm_preannotation_run_active` | 2 | 7153, 7725 | TBD | TBD |
| `vlm_preannotation_run_id` | 1 | 7149 | TBD | TBD |
| `vlm_preannotation_saved_total` | 2 | 7148, 7459 | TBD | TBD |
| `vlm_preannotation_stop_button` | 2 | 7623, 7757 | TBD | TBD |
| `vlm_preannotation_target_parts` | 1 | 7165 | TBD | TBD |
| `vlm_preannotation_thread` | 4 | 7236, 7252, 7285, 7761 | TBD | TBD |
| `vlm_preannotation_threads` | 5 | 7152, 7235, 7251, 7760, 7910 | TBD | TBD |
| `vlm_preannotation_total_images` | 1 | 7159 | TBD | TBD |
| `vlm_preannotation_total_steps` | 1 | 7157 | TBD | TBD |

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
| tests/test_main_window_stage3_shell.py | 35 | `import AntSleap.main as main_module` |
| tests/test_main_window_stage3_shell.py | 88 | `self.assertNotIn("from main import", source)` |
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
| tests/test_gui_smoke.py | 242 | `patch.object(main_module.MainWindow, "_default_outputs_root", lambda _window: str(self.project_dir / "TaxaMask_outputs")), \` | - | TBD |
| tests/test_gui_smoke.py | 248 | `patch.object(main_module.QTimer, "singleShot", lambda *args, **kwargs: None):` | - | TBD |
| tests/test_gui_smoke.py | 249 | `window = main_module.MainWindow()` | - | TBD |
| tests/test_gui_smoke.py | 250 | `window._default_outputs_root = lambda: str(self.project_dir / "TaxaMask_outputs")` | `_default_outputs_root` | TBD |
| tests/test_gui_smoke.py | 251 | `window._pdf_widget_factory = build_pdf_widget` | `_pdf_widget_factory` | TBD |
| tests/test_gui_smoke.py | 349 | `self.assertIsNotNone(window.findChild(main_module.QWidget, "start2DWorkflowCard"))` | - | TBD |
| tests/test_gui_smoke.py | 350 | `self.assertIsNone(window.findChild(main_module.QWidget, "start" + "T" + "if" + "WorkflowCard"))` | - | TBD |
| tests/test_gui_smoke.py | 351 | `self.assertIsNotNone(window.findChild(main_module.QWidget, "startProjectConsole"))` | - | TBD |
| tests/test_gui_smoke.py | 356 | `rail_scroll = window.findChild(main_module.QScrollArea, "startWorkflowRailScroll")` | - | TBD |
| tests/test_gui_smoke.py | 361 | `self.assertEqual(rail_scroll.horizontalScrollBarPolicy(), main_module.Qt.ScrollBarAlwaysOff)` | - | TBD |
| tests/test_gui_smoke.py | 362 | `self.assertEqual(rail_scroll.verticalScrollBarPolicy(), main_module.Qt.ScrollBarAsNeeded)` | - | TBD |
| tests/test_gui_smoke.py | 363 | `self.assertIsNotNone(window.findChild(main_module.QWidget, "taxamaskAgentPanel"))` | - | TBD |
| tests/test_gui_smoke.py | 374 | `self.assertIsNone(window.agent_panel.findChild(main_module.QWidget, "taxamaskAgentInlineStatus"))` | - | TBD |
| tests/test_gui_smoke.py | 375 | `self.assertIsNone(window.agent_panel.findChild(main_module.QWidget, "taxamaskStartAntCodeButton"))` | - | TBD |
| tests/test_gui_smoke.py | 429 | `self.assertIsNotNone(window.findChild(main_module.QWidget, "workbenchCanvasShell"))` | - | TBD |
| tests/test_gui_smoke.py | 430 | `self.assertIsNotNone(window.findChild(main_module.QWidget, "workbenchLiteratureDescriptionButton"))` | - | TBD |
| tests/test_gui_smoke.py | 436 | `window._show_start_center()` | `_show_start_center` | TBD |
| tests/test_gui_smoke.py | 442 | `self.assertIsNone(window.findChild(main_module.QWidget, "start" + "T" + "if" + "WorkflowCard"))` | - | TBD |
| tests/test_gui_smoke.py | 462 | `window._update_start_center_texts()` | `_update_start_center_texts` | TBD |
| tests/test_gui_smoke.py | 477 | `self.assertTrue(main_module.MainWindow.ensure_2d_stl_models_preloaded(window))` | - | TBD |
| tests/test_gui_smoke.py | 478 | `self.assertFalse(main_module.MainWindow.ensure_2d_stl_models_preloaded(window))` | - | TBD |
| tests/test_gui_smoke.py | 488 | `window._show_start_center()` | `_show_start_center` | TBD |
| tests/test_gui_smoke.py | 519 | `self.assertIsNotNone(window.agent_panel.findChild(main_module.QWidget, "taxamaskAgentStack"))` | - | TBD |
| tests/test_gui_smoke.py | 528 | `panel = main_module.TaxaMaskAgentPanel(` | - | TBD |
| tests/test_gui_smoke.py | 546 | `panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=str(PROJECT_ROOT))` | - | TBD |
| tests/test_gui_smoke.py | 550 | `self.assertIsNotNone(panel.findChild(main_module.QWidget, "taxamaskAgentStack"))` | - | TBD |
| tests/test_gui_smoke.py | 558 | `panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=str(PROJECT_ROOT))` | - | TBD |
| tests/test_gui_smoke.py | 577 | `class FakeWebView(main_module.QWidget):` | - | TBD |
| tests/test_gui_smoke.py | 629 | `panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=str(PROJECT_ROOT))` | - | TBD |
| tests/test_gui_smoke.py | 650 | `panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=r"D:\lab data\TaxaMask")` | - | TBD |
| tests/test_gui_smoke.py | 666 | `panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=str(PROJECT_ROOT))` | - | TBD |
| tests/test_gui_smoke.py | 675 | `panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=str(PROJECT_ROOT))` | - | TBD |
| tests/test_gui_smoke.py | 690 | `panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=str(PROJECT_ROOT))` | - | TBD |
| tests/test_gui_smoke.py | 917 | `with patch.object(main_module.QTimer, "singleShot", lambda _ms, callback: callback()):` | - | TBD |
| tests/test_gui_smoke.py | 938 | `fake_web_view = main_module.QWidget()` | - | TBD |
| tests/test_gui_smoke.py | 960 | `fake_web_view = main_module.QWidget()` | - | TBD |
| tests/test_gui_smoke.py | 1087 | `window.open_agent_from_context(window._collect_image_workbench_agent_context())` | `_collect_image_workbench_agent_context` | TBD |
| tests/test_gui_smoke.py | 1147 | `dialog = main_module.ModelSettingsDialog(` | - | TBD |
| tests/test_gui_smoke.py | 1167 | `self.assertIsNotNone(dialog.findChild(main_module.QPushButton, "modelSettingsAskAgentButton"))` | - | TBD |
| tests/test_gui_smoke.py | 1169 | `runtime_group = dialog.findChild(main_module.QWidget, "modelSettingsRuntimeDevicePanel")` | - | TBD |
| tests/test_gui_smoke.py | 1171 | `device_combo = runtime_group.findChild(main_module.QComboBox)` | - | TBD |
| tests/test_gui_smoke.py | 1185 | `dialog = main_module.ModelSettingsDialog(` | - | TBD |
| tests/test_gui_smoke.py | 1218 | `vlm_panel = dialog.findChild(main_module.QWidget, "modelSettingsVlmPreannotationPanel")` | - | TBD |
| tests/test_gui_smoke.py | 1224 | `scope_combo = dialog.findChild(main_module.QComboBox, "modelSettingsVlmBatchScopeCombo")` | - | TBD |
| tests/test_gui_smoke.py | 1228 | `group_combo = dialog.findChild(main_module.QComboBox, "modelSettingsVlmImageGroupCombo")` | - | TBD |
| tests/test_gui_smoke.py | 1231 | `profile_combo = dialog.findChild(main_module.QComboBox, "modelSettingsVlmPromptProfileCombo")` | - | TBD |
| tests/test_gui_smoke.py | 1242 | `dialog = main_module.ModelSettingsDialog(` | - | TBD |
| tests/test_gui_smoke.py | 1268 | `combo = dialog.findChild(main_module.QComboBox, "modelSettingsVlmImageGroupCombo")` | - | TBD |
| tests/test_gui_smoke.py | 1278 | `dialog = main_module.ModelSettingsDialog(` | - | TBD |
| tests/test_gui_smoke.py | 1331 | `dialog = main_module.GeneralSettingsDialog(` | - | TBD |
| tests/test_gui_smoke.py | 1348 | `self.assertIsNotNone(dialog.findChild(main_module.QPushButton, "generalSettingsAskAgentButton"))` | - | TBD |
| tests/test_gui_smoke.py | 1353 | `self.assertIsNone(dialog.findChild(main_module.QWidget, "modelSettingsLocatorScopePanel"))` | - | TBD |
| tests/test_gui_smoke.py | 1360 | `model_dialog = main_module.ModelSettingsDialog(` | - | TBD |
| tests/test_gui_smoke.py | 1372 | `"model_backend": main_module.EXTERNAL_BACKEND_ID,` | - | TBD |
| tests/test_gui_smoke.py | 1390 | `model_dialog.child_backend_combo.findData(main_module.CHILD_BACKEND_EXTERNAL)` | - | TBD |
| tests/test_gui_smoke.py | 1408 | `"expert_backend": main_module.ROUTE_BACKEND_HEATMAP_BLINK,` | - | TBD |
| tests/test_gui_smoke.py | 1419 | `self.assertEqual(context["parent_model_source"], main_module.PARENT_BACKEND_EXTERNAL)` | - | TBD |
| tests/test_gui_smoke.py | 1420 | `self.assertEqual(context["default_child_expert"], main_module.CHILD_BACKEND_EXTERNAL)` | - | TBD |
| tests/test_gui_smoke.py | 1421 | `self.assertEqual(context["default_child_route_backend"], main_module.ROUTE_BACKEND_EXTERNAL_BLINK)` | - | TBD |
| tests/test_gui_smoke.py | 1434 | `compact = window._compact_agent_context(context)` | `_compact_agent_context` | TBD |
| tests/test_gui_smoke.py | 1438 | `self.assertEqual(compact["default_child_expert"], main_module.CHILD_BACKEND_EXTERNAL)` | - | TBD |
| tests/test_gui_smoke.py | 1458 | `tif_compact = window._compact_agent_context(` | `_compact_agent_context` | TBD |
| tests/test_gui_smoke.py | 1546 | `pdf_compact = window._compact_agent_context(` | `_compact_agent_context` | TBD |
| tests/test_gui_smoke.py | 1596 | `with patch.object(main_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1620 | `with patch.object(main_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1640 | `with patch.object(main_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1669 | `with patch.object(main_module.QMessageBox, "information", return_value=main_module.QMessageBox.Ok):` | - | TBD |
| tests/test_gui_smoke.py | 1676 | `with patch.object(main_module.QFileDialog, "getSaveFileName", return_value=(str(export_path), "JSON (*.json)")), \` | - | TBD |
| tests/test_gui_smoke.py | 1677 | `patch.object(main_module.QMessageBox, "information", return_value=main_module.QMessageBox.Ok):` | - | TBD |
| tests/test_gui_smoke.py | 1694 | `with patch.object(main_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1721 | `with patch.object(main_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1744 | `with patch.object(main_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1788 | `with patch.object(main_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1797 | `self.assertEqual(header.data(main_module.Qt.UserRole + 1), "original")` | - | TBD |
| tests/test_gui_smoke.py | 1824 | `with patch.object(main_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1847 | `with patch.object(main_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1871 | `with patch.object(main_module.QFileDialog, "getExistingDirectory", fake_get_existing_directory), \` | - | TBD |
| tests/test_gui_smoke.py | 1872 | `patch.object(main_module.QInputDialog, "getText", return_value=("review", True)), \` | - | TBD |
| tests/test_gui_smoke.py | 1889 | `ant_project_dir = Path(main_module.PACKAGE_DIR)` | - | TBD |
| tests/test_gui_smoke.py | 1891 | `self.assertEqual(Path(window._default_open_project_dir()), self.project_dir / "TaxaMask_outputs")` | `_default_open_project_dir` | TBD |
| tests/test_gui_smoke.py | 1895 | `self.assertEqual(Path(window._default_2d_export_dir()), project_dir / "exports")` | `_default_2d_export_dir` | TBD |
| tests/test_gui_smoke.py | 1896 | `self.assertEqual(Path(window._vlm_preannotation_artifacts_dir()), project_dir / "vlm_preannotation")` | `_vlm_preannotation_artifacts_dir` | TBD |
| tests/test_gui_smoke.py | 1898 | `dialog = main_module.ExportDialog(window, "en", default_dir=window._default_2d_export_dir())` | `_default_2d_export_dir` | TBD |
| tests/test_gui_smoke.py | 1916 | `window._create_vlm_progress_dialog()` | `_create_vlm_progress_dialog` | TBD |
| tests/test_gui_smoke.py | 1918 | `window._advance_vlm_progress("prepare")` | `_advance_vlm_progress` | TBD |
| tests/test_gui_smoke.py | 1922 | `self.assertEqual(progress.windowModality(), main_module.Qt.NonModal)` | - | TBD |
| tests/test_gui_smoke.py | 1936 | `window._mark_current_vlm_image_done("done")` | `_mark_current_vlm_image_done` | TBD |
| tests/test_gui_smoke.py | 1968 | `original_refresh = window._refresh_vlm_canvas_if_current` | `_refresh_vlm_canvas_if_current` | TBD |
| tests/test_gui_smoke.py | 1969 | `window._refresh_vlm_canvas_if_current = lambda path: (refresh_calls.append(path), original_refresh(path))` | `_refresh_vlm_canvas_if_current` | TBD |
| tests/test_gui_smoke.py | 1972 | `window._on_vlm_preannotation_image_result(` | `_on_vlm_preannotation_image_result` | TBD |
| tests/test_gui_smoke.py | 2027 | `window._on_vlm_preannotation_image_result(` | `_on_vlm_preannotation_image_result` | TBD |
| tests/test_gui_smoke.py | 2071 | `window._on_vlm_preannotation_image_result(` | `_on_vlm_preannotation_image_result` | TBD |
| tests/test_gui_smoke.py | 2111 | `window._create_vlm_progress_dialog()` | `_create_vlm_progress_dialog` | TBD |
| tests/test_gui_smoke.py | 2119 | `window._on_vlm_preannotation_image_result(` | `_on_vlm_preannotation_image_result` | TBD |
| tests/test_gui_smoke.py | 2170 | `window._set_panel_split_review(str(manual_image), "manual_required", reason="hard_seam_panel_split")` | `_set_panel_split_review` | TBD |
| tests/test_gui_smoke.py | 2181 | `batch_paths = window._vlm_image_paths_for_scope(window._current_vlm_batch_scope())` | `_current_vlm_batch_scope`, `_vlm_image_paths_for_scope` | TBD |
| tests/test_gui_smoke.py | 2184 | `current_paths = window._vlm_image_paths_for_scope("current_image")` | `_vlm_image_paths_for_scope` | TBD |
| tests/test_gui_smoke.py | 2189 | `groups = window._project_image_groups()` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 2227 | `window._on_vlm_preannotation_image_result(` | `_on_vlm_preannotation_image_result` | TBD |
| tests/test_gui_smoke.py | 2270 | `window._refresh_vlm_canvas_if_current(image_key)` | `_refresh_vlm_canvas_if_current` | TBD |
| tests/test_gui_smoke.py | 2297 | `ok, mode = window._apply_vlm_candidate(` | `_apply_vlm_candidate` | TBD |
| tests/test_gui_smoke.py | 2353 | `ok, mode = window._apply_vlm_candidate(` | `_apply_vlm_candidate` | TBD |
| tests/test_gui_smoke.py | 2387 | `window._same_project_image_path(` | `_same_project_image_path` | TBD |
| tests/test_gui_smoke.py | 2388 | `window.file_list.currentItem().data(main_module.Qt.UserRole),` | - | TBD |
| tests/test_gui_smoke.py | 2402 | `for index in range(main_module.BACKGROUND_IMAGE_IMPORT_THRESHOLD):` | - | TBD |
| tests/test_gui_smoke.py | 2435 | `started = window._start_image_import(image_paths)` | `_start_image_import` | TBD |
| tests/test_gui_smoke.py | 2461 | `window.model_backend = main_module.EXTERNAL_BACKEND_ID` | - | TBD |
| tests/test_gui_smoke.py | 2513 | `with patch.object(main_module, "_runtime_parent_backend", lambda *_args, **_kwargs: main_module.EXTERNAL_BACKEND_ID), \` | - | TBD |
| tests/test_gui_smoke.py | 2514 | `patch.object(main_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes), \` | - | TBD |
| tests/test_gui_smoke.py | 2548 | `path = item.data(main_module.Qt.UserRole)` | - | TBD |
| tests/test_gui_smoke.py | 2561 | `with patch.object(main_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 2710 | `prompt = window._pdf_agent_prompt()` | `_pdf_agent_prompt` | TBD |
| tests/test_gui_smoke.py | 2863 | `window._inherit_crop_provenance(` | `_inherit_crop_provenance` | TBD |
| tests/test_gui_smoke.py | 2880 | `self.assertTrue(window._is_pdf_candidate_provenance(crop_provenance))` | `_is_pdf_candidate_provenance` | TBD |
| tests/test_gui_smoke.py | 2897 | `window._inherit_crop_provenance(` | `_inherit_crop_provenance` | TBD |
| tests/test_gui_smoke.py | 2914 | `self.assertTrue(window._is_split_crop_image(str(crop_image)))` | `_is_split_crop_image` | TBD |
| tests/test_gui_smoke.py | 2926 | `window._set_panel_split_review(str(parent_image), "manual_required", reason="hard_seam_panel_split")` | `_set_panel_split_review` | TBD |
| tests/test_gui_smoke.py | 2928 | `window._inherit_crop_provenance(` | `_inherit_crop_provenance` | TBD |
| tests/test_gui_smoke.py | 2945 | `self.assertFalse(window._needs_manual_panel_split(str(parent_image)))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 2946 | `self.assertFalse(window._needs_manual_panel_split(str(crop_image)))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 2971 | `window._set_panel_split_review(str(parent_image), "manual_required", reason="hard_seam_panel_split")` | `_set_panel_split_review` | TBD |
| tests/test_gui_smoke.py | 2973 | `self.assertTrue(window._has_split_crops_from_image(str(parent_image)))` | `_has_split_crops_from_image` | TBD |
| tests/test_gui_smoke.py | 2974 | `self.assertFalse(window._needs_manual_panel_split(str(parent_image)))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 2975 | `self.assertFalse(window._needs_manual_panel_split(str(crop_image)))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 2999 | `self.assertTrue(window._needs_manual_panel_split(str(image_path)))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 3005 | `self.assertFalse(window._needs_manual_panel_split(str(image_path)))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 3028 | `window._set_panel_split_review(str(image_a), "manual_required", reason="hard_seam_panel_split")` | `_set_panel_split_review` | TBD |
| tests/test_gui_smoke.py | 3029 | `window._set_panel_split_review(str(image_b), "manual_required", reason="hard_seam_panel_split")` | `_set_panel_split_review` | TBD |
| tests/test_gui_smoke.py | 3039 | `groups = window._project_image_groups()` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 3057 | `window._set_panel_split_review(str(image_path), "manual_done", reason="user_marked_done")` | `_set_panel_split_review` | TBD |
| tests/test_gui_smoke.py | 3059 | `self.assertEqual([Path(path).name for path in window._project_image_groups()["manual_done"]], [image_path.name])` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 3062 | `groups = window._project_image_groups()` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 3086 | `groups = window._project_image_groups()` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 3089 | `self.assertEqual(window._vlm_image_group_label("review_ready"), "Review Ready")` | `_vlm_image_group_label` | TBD |
| tests/test_gui_smoke.py | 3099 | `self.assertEqual(window._current_vlm_image_group(), "review_ready")` | `_current_vlm_image_group` | TBD |
| tests/test_gui_smoke.py | 3100 | `paths = window._vlm_image_paths_for_scope("image_group")` | `_vlm_image_paths_for_scope` | TBD |
| tests/test_gui_smoke.py | 3128 | `groups = window._project_image_groups()` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 3155 | `self.assertIn("review_ready", {group_id for group_id, _label in window._image_group_move_target_definitions()})` | `_image_group_move_target_definitions` | TBD |
| tests/test_gui_smoke.py | 3159 | `self.assertEqual(window._custom_image_group_definitions(), [])` | `_custom_image_group_definitions` | TBD |
| tests/test_gui_smoke.py | 3161 | `self.assertNotIn("review_ready", {group_id for group_id, _label in window._image_group_move_target_definitions()})` | `_image_group_move_target_definitions` | TBD |
| tests/test_gui_smoke.py | 3184 | `if item.data(main_module.Qt.UserRole) and _same_path(item.data(main_module.Qt.UserRole), image_a):` | - | TBD |
| tests/test_gui_smoke.py | 3238 | `self.assertTrue(window._is_split_crop_image(str(crop_image)))` | `_is_split_crop_image` | TBD |
| tests/test_gui_smoke.py | 3239 | `self.assertFalse(window._is_split_crop_image(str(unrelated_crop)))` | `_is_split_crop_image` | TBD |
| tests/test_gui_smoke.py | 3284 | `with patch.object(main_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 3285 | `with patch.object(main_module.QMessageBox, "information", lambda *args, **kwargs: None):` | - | TBD |
| tests/test_gui_smoke.py | 3311 | `self.assertTrue(window._is_split_crop_image(generated))` | `_is_split_crop_image` | TBD |
| tests/test_gui_smoke.py | 3312 | `self.assertFalse(window._needs_manual_panel_split(generated))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 3317 | `self.assertTrue(window._is_split_crop_image(generated))` | `_is_split_crop_image` | TBD |
| tests/test_gui_smoke.py | 3318 | `self.assertFalse(window._needs_manual_panel_split(generated))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 3323 | `groups = window._project_image_groups()` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 3369 | `with patch.object(main_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 3370 | `with patch.object(main_module.QMessageBox, "information", lambda *args, **kwargs: None):` | - | TBD |
| tests/test_gui_smoke.py | 3378 | `groups = window._project_image_groups()` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 3441 | `window._ensure_pdf_widget()` | `_ensure_pdf_widget` | TBD |
| tests/test_gui_smoke.py | 3444 | `db_path, context, reason = window._resolve_current_literature_context()` | `_resolve_current_literature_context` | TBD |
| tests/test_gui_smoke.py | 3464 | `window._ensure_pdf_widget()` | `_ensure_pdf_widget` | TBD |
| tests/test_gui_smoke.py | 3480 | `db_path, context, reason = window._resolve_current_literature_context()` | `_resolve_current_literature_context` | TBD |
| tests/test_gui_smoke.py | 3502 | `window._ensure_pdf_widget()` | `_ensure_pdf_widget` | TBD |
| tests/test_gui_smoke.py | 3529 | `db_path, context, reason = window._resolve_current_literature_context()` | `_resolve_current_literature_context` | TBD |
| tests/test_gui_smoke.py | 3549 | `window._ensure_pdf_widget()` | `_ensure_pdf_widget` | TBD |
| tests/test_gui_smoke.py | 3565 | `with patch.object(main_module.QFileDialog, "getOpenFileName", return_value=(str(literature_db), "SQLite Database (*.db)")):` | - | TBD |
| tests/test_gui_smoke.py | 3566 | `db_path, context, reason = window._choose_literature_db_for_current_taxon()` | `_choose_literature_db_for_current_taxon` | TBD |
| tests/test_gui_smoke.py | 3611 | `dialog = main_module.LiteratureDescriptionDialog(` | - | TBD |
| tests/test_gui_smoke.py | 3643 | `dialog = main_module.LiteratureDescriptionDialog(` | - | TBD |
| tests/test_gui_smoke.py | 3745 | `self.assertTrue(window._is_stl_project_file(stl_path))` | `_is_stl_project_file` | TBD |
| tests/test_gui_smoke.py | 3746 | `with patch.object(main_module.QFileDialog, "getOpenFileName", return_value=(stl_path, "JSON (*.json)")):` | - | TBD |
| tests/test_gui_smoke.py | 3757 | `self.assertEqual(window._active_recent_project_path(), os.path.abspath(stl_path))` | `_active_recent_project_path` | TBD |
| tests/test_gui_smoke.py | 3759 | `context = window._collect_image_workbench_agent_context()` | `_collect_image_workbench_agent_context` | TBD |
| tests/test_gui_smoke.py | 3763 | `self.assertIn("STL rendered-view project", window._start_console_project_summary()[0])` | `_start_console_project_summary` | TBD |
| tests/test_gui_smoke.py | 3764 | `self.assertIn("1 STL rendered 2D view", window._start_console_image_summary()[0])` | `_start_console_image_summary` | TBD |
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
