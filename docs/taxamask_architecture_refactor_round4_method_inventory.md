# TaxaMask Round 4 Main Window Method Inventory

由 `scripts/analyze_main_window_architecture.py` 生成。Stage 0 冻结当前责任、兼容入口和目标阶段，实施时必须结合真实调用复核。

## Metrics

| Metric | Value |
| --- | --- |
| main_physical_lines | 5113 |
| top_level_class_count | 1 |
| top_level_function_count | 0 |
| all_method_count | 189 |
| private_method_count | 121 |
| connection_count | 194 |
| source_state_assignment_lines | 144 |
| main_window_lines | 4603 |
| main_window_method_count | 189 |
| main_window_connection_count | 44 |
| main_window_init_lines | 13 |
| main_window_methods_ge_50 | 26 |
| main_window_methods_ge_100 | 6 |
| main_window_unique_state_fields | 81 |
| main_window_state_assignment_occurrences | 154 |
| main_import_site_count | 24 |
| key_test_reference_line_count | 328 |
| key_test_private_reference_occurrences | 146 |
| key_test_unique_private_references | 53 |
| async_entry_count | 16 |

## Top-level Classes

| Line | Size | Class | Methods | Connects | Refs | Stage |
| --- | --- | --- | --- | --- | --- | --- |
| 489 | 4603 | `MainWindow` | 189 | 44 | 39 | 3 |

## MainWindow Workflow Counts

| Workflow | Methods |
| --- | --- |
| annotation_sam | 20 |
| blink | 33 |
| dialog_settings | 21 |
| image_navigation | 3 |
| project_lifecycle | 4 |
| runtime_worker | 12 |
| shell_start_agent | 5 |
| training_model | 35 |
| unclassified | 10 |
| vlm_prediction_export | 46 |

## Compatibility Counts

| Compatibility | Methods |
| --- | --- |
| internal_or_unreferenced | 83 |
| public_or_source_compatibility | 71 |
| signal_compatibility | 11 |
| test_compatibility | 24 |

## MainWindow Methods

| Line | Size | Method | Workflow | Stage | Compatibility | Source refs | Test refs | Signal refs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 502 | 13 | `__init__` | unclassified | 8 | public_or_source_compatibility | 217 | 139 | 0 |
| 519 | 51 | `refresh_model_list` | training_model | 7 | public_or_source_compatibility | 1 | 0 | 0 |
| 571 | 5 | `_selected_locator_timestamp` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 577 | 4 | `_selected_locator_display_text` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 582 | 9 | `_parent_model_filename` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 592 | 40 | `_build_locator_combo_label` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 633 | 7 | `_build_segmenter_combo_label` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 641 | 5 | `_selected_segmenter_timestamp` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 647 | 2 | `_active_project_route_manifest` | dialog_settings | 2 | public_or_source_compatibility | 1 | 0 | 0 |
| 650 | 9 | `_active_model_profile_context` | dialog_settings | 2 | public_or_source_compatibility | 1 | 0 | 0 |
| 660 | 6 | `_active_external_backend_config` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 667 | 5 | `_selected_route_entry` | dialog_settings | 2 | public_or_source_compatibility | 7 | 0 | 0 |
| 673 | 5 | `_route_runtime_status` | runtime_worker | 1 | public_or_source_compatibility | 2 | 0 | 0 |
| 679 | 8 | `refresh_route_table` | dialog_settings | 2 | public_or_source_compatibility | 12 | 30 | 2 |
| 688 | 4 | `update_route_action_buttons` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 694 | 4 | `appoint_selected_route_expert` | blink | 6 | public_or_source_compatibility | 2 | 1 | 1 |
| 699 | 4 | `toggle_selected_route_enabled` | dialog_settings | 2 | public_or_source_compatibility | 2 | 0 | 1 |
| 704 | 4 | `delete_selected_route` | dialog_settings | 2 | public_or_source_compatibility | 2 | 2 | 1 |
| 709 | 30 | `_log_route_usage_summary` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 740 | 4 | `_locator_model_path` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 745 | 4 | `_segmenter_model_path` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 750 | 18 | `_apply_locator_selection_to_runtime` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 769 | 2 | `_locator_selection_needs_legacy_confirmation` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 772 | 20 | `_confirm_legacy_locator_selection_if_needed` | training_model | 7 | test_compatibility | 0 | 1 | 0 |
| 793 | 5 | `_show_structured_training_preflight` | dialog_settings | 2 | test_compatibility | 0 | 1 | 0 |
| 799 | 3 | `_is_locator_oom_error` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 803 | 30 | `_ask_locator_oom_retry_resolution` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 834 | 3 | `_is_parent_training_running` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 838 | 4 | `_is_child_training_running` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 843 | 2 | `_is_any_training_running` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 846 | 19 | `_set_training_progress` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 866 | 11 | `_connect_child_training_progress` | blink | 6 | test_compatibility | 0 | 1 | 0 |
| 878 | 6 | `_on_child_training_result` | blink | 6 | signal_compatibility | 0 | 0 | 1 |
| 885 | 3 | `_on_child_training_error` | blink | 6 | signal_compatibility | 0 | 0 | 1 |
| 889 | 3 | `_on_child_training_cancelled` | blink | 6 | signal_compatibility | 0 | 0 | 1 |
| 893 | 10 | `_on_child_training_finished` | blink | 6 | signal_compatibility | 0 | 0 | 1 |
| 904 | 87 | `_launch_training_with_preflight` | dialog_settings | 2 | test_compatibility | 0 | 1 | 0 |
| 992 | 15 | `_on_training_success` | training_model | 7 | signal_compatibility | 0 | 1 | 1 |
| 1008 | 13 | `_on_training_finished` | training_model | 7 | public_or_source_compatibility | 2 | 1 | 1 |
| 1022 | 38 | `_on_training_error` | training_model | 7 | public_or_source_compatibility | 2 | 0 | 1 |
| 1061 | 7 | `stop_training` | training_model | 7 | public_or_source_compatibility | 1 | 0 | 1 |
| 1069 | 21 | `_apply_segmenter_selection_to_runtime` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 1091 | 12 | `update_model_delete_button_states` | training_model | 7 | public_or_source_compatibility | 2 | 0 | 2 |
| 1104 | 33 | `_edit_parent_model_note` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 1138 | 2 | `edit_locator_model_note` | training_model | 7 | public_or_source_compatibility | 1 | 1 | 1 |
| 1141 | 2 | `edit_segmenter_model_note` | training_model | 7 | public_or_source_compatibility | 1 | 1 | 1 |
| 1144 | 36 | `on_locator_changed` | training_model | 7 | public_or_source_compatibility | 1 | 1 | 1 |
| 1181 | 26 | `delete_locator_model` | training_model | 7 | public_or_source_compatibility | 1 | 2 | 1 |
| 1208 | 3 | `on_segmenter_changed` | training_model | 7 | public_or_source_compatibility | 1 | 0 | 1 |
| 1212 | 26 | `delete_segmenter_model` | training_model | 7 | public_or_source_compatibility | 1 | 1 | 1 |
| 1239 | 3 | `on_model_changed` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 1243 | 29 | `create_menus` | shell_start_agent | 3 | public_or_source_compatibility | 3 | 0 | 0 |
| 1275 | 18 | `_route_parents_for_child` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 1294 | 25 | `_resolve_child_parent` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 1320 | 15 | `_parent_context_box` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 1336 | 5 | `_current_shrink_loose_boxes` | blink | 6 | public_or_source_compatibility | 1 | 1 | 0 |
| 1342 | 28 | `_auto_boxes_for_canvas` | vlm_prediction_export | 7 | public_or_source_compatibility | 2 | 2 | 0 |
| 1371 | 10 | `_refresh_current_canvas_boxes` | annotation_sam | 6 | public_or_source_compatibility | 1 | 1 | 0 |
| 1382 | 15 | `_route_entry_for_context` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 1398 | 26 | `_route_expert_status` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 1425 | 73 | `_current_blink_context` | blink | 6 | public_or_source_compatibility | 1 | 0 | 0 |
| 1499 | 10 | `_parent_box_aspect_ratio` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 1510 | 24 | `_parent_context_options` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 1535 | 15 | `_refresh_annotation_box_constraints` | annotation_sam | 6 | public_or_source_compatibility | 1 | 0 | 1 |
| 1551 | 8 | `_active_box_tool_role` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 1560 | 6 | `_refresh_blink_refine_state` | blink | 6 | public_or_source_compatibility | 5 | 10 | 0 |
| 1568 | 55 | `clear_ai_labels` | unclassified | 8 | public_or_source_compatibility | 1 | 2 | 1 |
| 1624 | 6 | `on_global_labels_updated` | unclassified | 8 | public_or_source_compatibility | 1 | 0 | 1 |
| 1631 | 190 | `refresh_ui` | unclassified | 8 | public_or_source_compatibility | 6 | 0 | 0 |
| 1822 | 78 | `_update_blink_refine_panel` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 1901 | 39 | `_update_blink_parent_context_combo` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 1941 | 51 | `open_general_settings` | dialog_settings | 2 | public_or_source_compatibility | 2 | 0 | 1 |
| 1993 | 129 | `open_stl_model_settings` | dialog_settings | 2 | public_or_source_compatibility | 3 | 0 | 0 |
| 2123 | 2 | `open_settings` | dialog_settings | 2 | public_or_source_compatibility | 1 | 0 | 0 |
| 2126 | 15 | `open_tif_model_settings` | dialog_settings | 2 | public_or_source_compatibility | 2 | 0 | 0 |
| 2142 | 15 | `change_language` | shell_start_agent | 3 | public_or_source_compatibility | 4 | 8 | 0 |
| 2158 | 28 | `change_theme` | shell_start_agent | 3 | public_or_source_compatibility | 2 | 0 | 0 |
| 2187 | 15 | `update_widget_themes` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 2203 | 66 | `update_button_themes` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 2271 | 90 | `launch_blink_from_workbench` | blink | 6 | public_or_source_compatibility | 2 | 4 | 1 |
| 2363 | 2 | `on_enhancement_changed` | unclassified | 8 | public_or_source_compatibility | 1 | 1 | 0 |
| 2366 | 16 | `on_tool_changed` | annotation_sam | 6 | public_or_source_compatibility | 8 | 8 | 6 |
| 2383 | 23 | `on_blink_parent_context_changed` | blink | 6 | public_or_source_compatibility | 1 | 2 | 1 |
| 2407 | 2 | `on_magic_wand_clicked` | annotation_sam | 6 | public_or_source_compatibility | 1 | 0 | 1 |
| 2410 | 2 | `on_magic_box_completed` | annotation_sam | 6 | public_or_source_compatibility | 1 | 1 | 1 |
| 2413 | 2 | `_sam_worker_ready` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 2416 | 2 | `_on_sam_model_loaded` | annotation_sam | 6 | signal_compatibility | 0 | 0 | 1 |
| 2419 | 18 | `_begin_sam_prompt` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 2438 | 6 | `_request_sam_point` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 2445 | 6 | `_request_sam_box` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 2452 | 34 | `on_annotation_box_completed` | annotation_sam | 6 | public_or_source_compatibility | 1 | 3 | 1 |
| 2487 | 2 | `_warn_blink_context` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 2490 | 12 | `_active_child_blink_context` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 2503 | 43 | `run_blink_child_auto_annotate` | blink | 6 | public_or_source_compatibility | 1 | 4 | 1 |
| 2547 | 9 | `_load_blink_refiner_class` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 2557 | 11 | `_active_blink_auto_shrink_steps` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 2569 | 14 | `_blink_parent_context_for_image` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 2584 | 41 | `_prepared_blink_auto_shrink_images` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 2626 | 38 | `_generate_blink_shrink_for_image` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 2665 | 42 | `run_blink_auto_shrink` | blink | 6 | public_or_source_compatibility | 1 | 3 | 1 |
| 2708 | 90 | `run_blink_batch_auto_shrink` | blink | 6 | public_or_source_compatibility | 1 | 1 | 1 |
| 2799 | 66 | `train_current_blink_expert` | blink | 6 | public_or_source_compatibility | 1 | 3 | 1 |
| 2866 | 10 | `stop_current_blink_expert_training` | blink | 6 | public_or_source_compatibility | 1 | 1 | 1 |
| 2877 | 18 | `open_current_route_expert_settings` | blink | 6 | public_or_source_compatibility | 1 | 0 | 1 |
| 2896 | 10 | `on_sam_mask_generated` | annotation_sam | 6 | signal_compatibility | 0 | 0 | 1 |
| 2907 | 7 | `on_sam_prompt_failed` | annotation_sam | 6 | signal_compatibility | 0 | 0 | 1 |
| 2915 | 23 | `on_polygon_completed` | annotation_sam | 6 | public_or_source_compatibility | 1 | 4 | 1 |
| 2939 | 7 | `toggle_morphometrics` | unclassified | 8 | public_or_source_compatibility | 1 | 0 | 1 |
| 2947 | 9 | `on_scale_defined` | annotation_sam | 6 | public_or_source_compatibility | 1 | 0 | 1 |
| 2957 | 16 | `update_measurements` | annotation_sam | 6 | public_or_source_compatibility | 1 | 0 | 0 |
| 2974 | 87 | `run_training` | training_model | 7 | public_or_source_compatibility | 2 | 2 | 1 |
| 3062 | 2 | `_external_backend_runner` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 3065 | 27 | `_sync_blink_lab_model_profile_defaults` | blink | 6 | public_or_source_compatibility | 1 | 0 | 0 |
| 3093 | 51 | `run_external_training` | training_model | 7 | test_compatibility | 0 | 1 | 0 |
| 3145 | 3 | `show_training_report` | dialog_settings | 2 | signal_compatibility | 0 | 0 | 1 |
| 3149 | 26 | `_candidate_training_experiment_dirs` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 3176 | 10 | `_resolve_report_artifact_path` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 3187 | 11 | `_training_report_time_label` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 3199 | 66 | `_training_report_payload_from_summary` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 3266 | 26 | `discover_training_reports` | dialog_settings | 2 | test_compatibility | 0 | 1 | 0 |
| 3293 | 8 | `open_training_report_payload` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 3302 | 17 | `open_training_results_browser` | project_lifecycle | 4 | public_or_source_compatibility | 1 | 0 | 1 |
| 3320 | 37 | `_extract_prediction_payload` | vlm_prediction_export | 7 | public_or_source_compatibility | 2 | 0 | 0 |
| 3358 | 12 | `_is_unconfirmed_ai_draft` | vlm_prediction_export | 7 | public_or_source_compatibility | 2 | 0 | 0 |
| 3371 | 13 | `_auto_box_meta_for_part` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 3385 | 3 | `_auto_box_source_for_part` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 3389 | 3 | `_auto_box_review_status_for_part` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 3393 | 5 | `_auto_annotation_source_meta` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 3399 | 15 | `_can_replace_existing_auto_annotation` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 3415 | 33 | `_apply_prediction_to_project` | vlm_prediction_export | 7 | test_compatibility | 0 | 3 | 0 |
| 3449 | 5 | `_vlm_api_settings_path` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 3455 | 40 | `_vlm_api_config_from_pdf_widget` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 3496 | 8 | `_vlm_preannotation_artifacts_dir` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 3505 | 4 | `_current_vlm_target_parts` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 3510 | 4 | `_current_vlm_processing_scope` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 3515 | 3 | `_current_vlm_batch_scope` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 3519 | 4 | `_current_vlm_image_group` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 3524 | 8 | `_current_vlm_concurrency` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 3533 | 5 | `_current_vlm_prompt_profile` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 3539 | 2 | `_vlm_image_group_label` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 3542 | 57 | `_panel_crop_identity_index` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 3600 | 57 | `_project_image_groups` | project_lifecycle | 4 | public_or_source_compatibility | 5 | 8 | 0 |
| 3658 | 10 | `_vlm_candidate_source_meta` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 3669 | 19 | `_record_sqlite_vlm_image_result` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 3689 | 13 | `_finish_sqlite_vlm_run` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 3703 | 7 | `_vlm_image_paths_for_scope` | vlm_prediction_export | 7 | test_compatibility | 0 | 3 | 0 |
| 3711 | 2 | `_vlm_image_paths_from_settings` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 3714 | 11 | `_same_project_image_path` | project_lifecycle | 4 | public_or_source_compatibility | 9 | 2 | 0 |
| 3726 | 5 | `_project_image_key_for_path` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 3732 | 7 | `_vlm_part_list_text` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 3740 | 18 | `_vlm_part_coverage` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 3759 | 15 | `_log_vlm_part_coverage` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 3775 | 2 | `run_vlm_preannotation_current` | vlm_prediction_export | 7 | public_or_source_compatibility | 1 | 0 | 1 |
| 3778 | 2 | `run_vlm_preannotation_batch` | vlm_prediction_export | 7 | public_or_source_compatibility | 1 | 0 | 1 |
| 3781 | 121 | `run_vlm_preannotation_from_settings` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 3903 | 42 | `request_stop_vlm_preannotation` | vlm_prediction_export | 7 | public_or_source_compatibility | 2 | 1 | 0 |
| 3946 | 11 | `_active_vlm_preannotation_threads` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 3958 | 14 | `_start_vlm_preannotation_workers` | runtime_worker | 1 | test_compatibility | 0 | 1 | 0 |
| 3973 | 53 | `_start_next_vlm_preannotation_image` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 4027 | 48 | `_apply_vlm_candidate` | vlm_prediction_export | 7 | test_compatibility | 0 | 5 | 0 |
| 4076 | 6 | `_refresh_vlm_canvas_if_current` | vlm_prediction_export | 7 | test_compatibility | 0 | 3 | 0 |
| 4083 | 34 | `_reload_current_image_for_workbench` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 4118 | 111 | `_on_vlm_preannotation_image_result` | vlm_prediction_export | 7 | signal_compatibility | 0 | 6 | 1 |
| 4230 | 7 | `_vlm_progress_image_key` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 4238 | 20 | `_mark_current_vlm_image_done` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 4259 | 30 | `_set_vlm_progress_ui` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 4290 | 54 | `_create_vlm_progress_dialog` | vlm_prediction_export | 7 | test_compatibility | 0 | 2 | 0 |
| 4345 | 18 | `_advance_vlm_progress` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 4364 | 11 | `_on_vlm_preannotation_thread_step` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 4376 | 7 | `_complete_current_vlm_image_steps` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 4384 | 100 | `_finish_vlm_preannotation_run` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 4485 | 36 | `accept_current_image_ai_drafts` | vlm_prediction_export | 7 | public_or_source_compatibility | 1 | 3 | 1 |
| 4522 | 93 | `accept_batch_ai_drafts` | vlm_prediction_export | 7 | public_or_source_compatibility | 1 | 1 | 1 |
| 4616 | 3 | `_on_vlm_preannotation_error` | vlm_prediction_export | 7 | signal_compatibility | 0 | 0 | 1 |
| 4620 | 33 | `_on_vlm_preannotation_qthread_finished` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 4654 | 2 | `_on_vlm_preannotation_finished` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 4657 | 46 | `run_prediction` | vlm_prediction_export | 7 | public_or_source_compatibility | 2 | 2 | 1 |
| 4704 | 30 | `run_external_prediction` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 4735 | 9 | `verify_current_image` | image_navigation | 5 | public_or_source_compatibility | 1 | 1 | 1 |
| 4745 | 100 | `_start_external_batch_inference` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 4846 | 74 | `run_batch_inference` | runtime_worker | 1 | public_or_source_compatibility | 1 | 1 | 1 |
| 4921 | 8 | `export_dataset` | runtime_worker | 1 | public_or_source_compatibility | 1 | 0 | 1 |
| 4930 | 75 | `_start_dataset_export` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 5006 | 23 | `init_sam` | annotation_sam | 6 | test_compatibility | 0 | 1 | 0 |
| 5030 | 13 | `ensure_sam_preloaded` | annotation_sam | 6 | test_compatibility | 0 | 6 | 0 |
| 5044 | 4 | `ensure_2d_stl_models_preloaded` | training_model | 7 | public_or_source_compatibility | 4 | 3 | 0 |
| 5049 | 17 | `ensure_locator_preloaded` | training_model | 7 | test_compatibility | 0 | 1 | 0 |
| 5067 | 22 | `_preload_engine_parts_model_async` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 5090 | 2 | `log` | unclassified | 8 | public_or_source_compatibility | 215 | 35 | 5 |

## MainWindow State Fields

| Field | Assignments | Lines | Target owner | Stage |
| --- | --- | --- | --- | --- |
| `_updating_blink_parent_context` | 2 | 1906, 1939 | TBD | TBD |
| `active_training_kind` | 2 | 3111, 848 | TBD | TBD |
| `active_training_label` | 1 | 850 | TBD | TBD |
| `blink_auto_shrink_steps` | 1 | 2042 | TBD | TBD |
| `blink_train_batch` | 1 | 2038 | TBD | TBD |
| `blink_train_epochs` | 1 | 2038 | TBD | TBD |
| `blink_train_input_size` | 1 | 2041 | TBD | TBD |
| `blink_train_lr` | 1 | 2039 | TBD | TBD |
| `blink_train_weight_decay` | 1 | 2040 | TBD | TBD |
| `blink_training_strategy` | 1 | 2043 | TBD | TBD |
| `child_training_cancel_requested` | 4 | 890, 901, 2829, 2871 | TBD | TBD |
| `child_training_failed` | 4 | 879, 886, 900, 2828 | TBD | TBD |
| `current_blink_context` | 1 | 1562 | TBD | TBD |
| `current_image` | 3 | 4089, 2572, 2575 | TBD | TBD |
| `current_lang` | 1 | 2143 | TBD | TBD |
| `current_theme` | 1 | 2160 | TBD | TBD |
| `dataset_export_thread` | 2 | 4955, 4998 | TBD | TBD |
| `external_backend_config` | 1 | 2053 | TBD | TBD |
| `external_batch_inference_failed` | 2 | 4755, 4814 | TBD | TBD |
| `external_batch_inference_progress_dialog` | 2 | 4775, 4828 | TBD | TBD |
| `external_batch_inference_saved_any` | 2 | 4756, 4810 | TBD | TBD |
| `external_batch_inference_thread` | 2 | 4787, 4830 | TBD | TBD |
| `external_training_failed` | 2 | 3110, 3124 | TBD | TBD |
| `external_training_thread` | 2 | 3116, 3133 | TBD | TBD |
| `inf_adapt` | 1 | 2047 | TBD | TBD |
| `inf_conf` | 1 | 2047 | TBD | TBD |
| `inf_noise_floor` | 1 | 2048 | TBD | TBD |
| `inf_pad` | 1 | 2048 | TBD | TBD |
| `inf_poly_epsilon` | 1 | 2049 | TBD | TBD |
| `inf_thread` | 1 | 4882 | TBD | TBD |
| `last_confirmed_locator_timestamp` | 3 | 787, 1173, 1166 | TBD | TBD |
| `model_backend` | 1 | 2052 | TBD | TBD |
| `parent_box_aspect_ratios` | 2 | 1503, 2068 | TBD | TBD |
| `parent_training_cancel_requested` | 2 | 951, 1065 | TBD | TBD |
| `parent_training_failed` | 3 | 950, 1026, 1043 | TBD | TBD |
| `parts_model_preload_thread` | 1 | 5082 | TBD | TBD |
| `pending_sam_description` | 3 | 2435, 2903, 2911 | TBD | TBD |
| `pending_sam_image` | 3 | 2434, 2902, 2910 | TBD | TBD |
| `pending_sam_part` | 3 | 2433, 2901, 2909 | TBD | TBD |
| `pending_training_preflight` | 1 | 938 | TBD | TBD |
| `project_autosave_delay_ms` | 1 | 1960 | TBD | TBD |
| `runtime_device` | 2 | 1965, 2051 | TBD | TBD |
| `sam_busy` | 3 | 2432, 2900, 2908 | TBD | TBD |
| `sam_thread` | 1 | 5013 | TBD | TBD |
| `sam_worker` | 1 | 5015 | TBD | TBD |
| `train_batch` | 1 | 2037 | TBD | TBD |
| `train_epochs` | 1 | 2037 | TBD | TBD |
| `train_lr` | 1 | 2046 | TBD | TBD |
| `train_wd` | 1 | 2046 | TBD | TBD |
| `trainer` | 2 | 956, 1017 | TBD | TBD |
| `training_retry_requested` | 3 | 949, 1025, 1034 | TBD | TBD |
| `vlm_preannotation_active_images` | 3 | 3881, 4481, 4008 | TBD | TBD |
| `vlm_preannotation_api_config` | 2 | 3862, 3886 | TBD | TBD |
| `vlm_preannotation_artifacts_dir` | 1 | 3885 | TBD | TBD |
| `vlm_preannotation_cancel_requested` | 3 | 3873, 3923, 4477 | TBD | TBD |
| `vlm_preannotation_cancelled_queued_images` | 3 | 3874, 3924, 4478 | TBD | TBD |
| `vlm_preannotation_completed_image_keys` | 3 | 3883, 4247, 4483 | TBD | TBD |
| `vlm_preannotation_completed_images` | 2 | 3879, 4249 | TBD | TBD |
| `vlm_preannotation_completed_steps` | 2 | 3877, 4348 | TBD | TBD |
| `vlm_preannotation_concurrency` | 1 | 3875 | TBD | TBD |
| `vlm_preannotation_current_image` | 4 | 3880, 3982, 4254, 4350 | TBD | TBD |
| `vlm_preannotation_current_image_steps_completed` | 3 | 3981, 4357, 4360 | TBD | TBD |
| `vlm_preannotation_image_step_counts` | 4 | 3882, 4482, 4012, 4355 | TBD | TBD |
| `vlm_preannotation_progress_bar` | 2 | 4341, 4475 | TBD | TBD |
| `vlm_preannotation_progress_dialog` | 2 | 4336, 4470 | TBD | TBD |
| `vlm_preannotation_progress_label` | 2 | 4339, 4473 | TBD | TBD |
| `vlm_preannotation_progress_notice_label` | 2 | 4338, 4472 | TBD | TBD |
| `vlm_preannotation_progress_path_label` | 2 | 4340, 4474 | TBD | TBD |
| `vlm_preannotation_progress_title_label` | 2 | 4337, 4471 | TBD | TBD |
| `vlm_preannotation_prompt_profile` | 1 | 3887 | TBD | TBD |
| `vlm_preannotation_queue` | 4 | 3870, 3925, 3980, 4644 | TBD | TBD |
| `vlm_preannotation_records` | 1 | 3869 | TBD | TBD |
| `vlm_preannotation_run_active` | 2 | 3872, 4444 | TBD | TBD |
| `vlm_preannotation_run_id` | 1 | 3868 | TBD | TBD |
| `vlm_preannotation_saved_total` | 2 | 3867, 4178 | TBD | TBD |
| `vlm_preannotation_stop_button` | 2 | 4342, 4476 | TBD | TBD |
| `vlm_preannotation_target_parts` | 1 | 3884 | TBD | TBD |
| `vlm_preannotation_thread` | 4 | 3955, 3971, 4004, 4480 | TBD | TBD |
| `vlm_preannotation_threads` | 5 | 3871, 3954, 3970, 4479, 4629 | TBD | TBD |
| `vlm_preannotation_total_images` | 1 | 3878 | TBD | TBD |
| `vlm_preannotation_total_steps` | 1 | 3876 | TBD | TBD |

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
| tests/test_main_window_stage4_project_lifecycle.py | 34 | `import AntSleap.main as main_module` |
| tests/test_main_window_stage4_project_lifecycle.py | 76 | `self.assertNotIn("from main import", source)` |
| tests/test_main_window_stage5_navigation.py | 81 | `import AntSleap.main as main_module` |
| tests/test_main_window_stage5_navigation.py | 101 | `self.assertNotIn("from main import", source)` |
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
| tests/test_gui_smoke.py | 244 | `patch.object(main_module.MainWindow, "_default_outputs_root", lambda _window: str(self.project_dir / "TaxaMask_outputs")), \` | - | TBD |
| tests/test_gui_smoke.py | 250 | `patch.object(main_module.QTimer, "singleShot", lambda *args, **kwargs: None):` | - | TBD |
| tests/test_gui_smoke.py | 251 | `window = main_module.MainWindow()` | - | TBD |
| tests/test_gui_smoke.py | 252 | `window._default_outputs_root = lambda: str(self.project_dir / "TaxaMask_outputs")` | `_default_outputs_root` | TBD |
| tests/test_gui_smoke.py | 253 | `window._pdf_widget_factory = build_pdf_widget` | `_pdf_widget_factory` | TBD |
| tests/test_gui_smoke.py | 351 | `self.assertIsNotNone(window.findChild(main_module.QWidget, "start2DWorkflowCard"))` | - | TBD |
| tests/test_gui_smoke.py | 352 | `self.assertIsNone(window.findChild(main_module.QWidget, "start" + "T" + "if" + "WorkflowCard"))` | - | TBD |
| tests/test_gui_smoke.py | 353 | `self.assertIsNotNone(window.findChild(main_module.QWidget, "startProjectConsole"))` | - | TBD |
| tests/test_gui_smoke.py | 358 | `rail_scroll = window.findChild(main_module.QScrollArea, "startWorkflowRailScroll")` | - | TBD |
| tests/test_gui_smoke.py | 363 | `self.assertEqual(rail_scroll.horizontalScrollBarPolicy(), main_module.Qt.ScrollBarAlwaysOff)` | - | TBD |
| tests/test_gui_smoke.py | 364 | `self.assertEqual(rail_scroll.verticalScrollBarPolicy(), main_module.Qt.ScrollBarAsNeeded)` | - | TBD |
| tests/test_gui_smoke.py | 365 | `self.assertIsNotNone(window.findChild(main_module.QWidget, "taxamaskAgentPanel"))` | - | TBD |
| tests/test_gui_smoke.py | 376 | `self.assertIsNone(window.agent_panel.findChild(main_module.QWidget, "taxamaskAgentInlineStatus"))` | - | TBD |
| tests/test_gui_smoke.py | 377 | `self.assertIsNone(window.agent_panel.findChild(main_module.QWidget, "taxamaskStartAntCodeButton"))` | - | TBD |
| tests/test_gui_smoke.py | 431 | `self.assertIsNotNone(window.findChild(main_module.QWidget, "workbenchCanvasShell"))` | - | TBD |
| tests/test_gui_smoke.py | 432 | `self.assertIsNotNone(window.findChild(main_module.QWidget, "workbenchLiteratureDescriptionButton"))` | - | TBD |
| tests/test_gui_smoke.py | 438 | `window._show_start_center()` | `_show_start_center` | TBD |
| tests/test_gui_smoke.py | 444 | `self.assertIsNone(window.findChild(main_module.QWidget, "start" + "T" + "if" + "WorkflowCard"))` | - | TBD |
| tests/test_gui_smoke.py | 464 | `window._update_start_center_texts()` | `_update_start_center_texts` | TBD |
| tests/test_gui_smoke.py | 479 | `self.assertTrue(main_module.MainWindow.ensure_2d_stl_models_preloaded(window))` | - | TBD |
| tests/test_gui_smoke.py | 480 | `self.assertFalse(main_module.MainWindow.ensure_2d_stl_models_preloaded(window))` | - | TBD |
| tests/test_gui_smoke.py | 490 | `window._show_start_center()` | `_show_start_center` | TBD |
| tests/test_gui_smoke.py | 521 | `self.assertIsNotNone(window.agent_panel.findChild(main_module.QWidget, "taxamaskAgentStack"))` | - | TBD |
| tests/test_gui_smoke.py | 530 | `panel = main_module.TaxaMaskAgentPanel(` | - | TBD |
| tests/test_gui_smoke.py | 548 | `panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=str(PROJECT_ROOT))` | - | TBD |
| tests/test_gui_smoke.py | 552 | `self.assertIsNotNone(panel.findChild(main_module.QWidget, "taxamaskAgentStack"))` | - | TBD |
| tests/test_gui_smoke.py | 560 | `panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=str(PROJECT_ROOT))` | - | TBD |
| tests/test_gui_smoke.py | 579 | `class FakeWebView(main_module.QWidget):` | - | TBD |
| tests/test_gui_smoke.py | 631 | `panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=str(PROJECT_ROOT))` | - | TBD |
| tests/test_gui_smoke.py | 652 | `panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=r"D:\lab data\TaxaMask")` | - | TBD |
| tests/test_gui_smoke.py | 668 | `panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=str(PROJECT_ROOT))` | - | TBD |
| tests/test_gui_smoke.py | 677 | `panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=str(PROJECT_ROOT))` | - | TBD |
| tests/test_gui_smoke.py | 692 | `panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=str(PROJECT_ROOT))` | - | TBD |
| tests/test_gui_smoke.py | 919 | `with patch.object(main_module.QTimer, "singleShot", lambda _ms, callback: callback()):` | - | TBD |
| tests/test_gui_smoke.py | 940 | `fake_web_view = main_module.QWidget()` | - | TBD |
| tests/test_gui_smoke.py | 962 | `fake_web_view = main_module.QWidget()` | - | TBD |
| tests/test_gui_smoke.py | 1089 | `window.open_agent_from_context(window._collect_image_workbench_agent_context())` | `_collect_image_workbench_agent_context` | TBD |
| tests/test_gui_smoke.py | 1149 | `dialog = main_module.ModelSettingsDialog(` | - | TBD |
| tests/test_gui_smoke.py | 1169 | `self.assertIsNotNone(dialog.findChild(main_module.QPushButton, "modelSettingsAskAgentButton"))` | - | TBD |
| tests/test_gui_smoke.py | 1171 | `runtime_group = dialog.findChild(main_module.QWidget, "modelSettingsRuntimeDevicePanel")` | - | TBD |
| tests/test_gui_smoke.py | 1173 | `device_combo = runtime_group.findChild(main_module.QComboBox)` | - | TBD |
| tests/test_gui_smoke.py | 1187 | `dialog = main_module.ModelSettingsDialog(` | - | TBD |
| tests/test_gui_smoke.py | 1220 | `vlm_panel = dialog.findChild(main_module.QWidget, "modelSettingsVlmPreannotationPanel")` | - | TBD |
| tests/test_gui_smoke.py | 1226 | `scope_combo = dialog.findChild(main_module.QComboBox, "modelSettingsVlmBatchScopeCombo")` | - | TBD |
| tests/test_gui_smoke.py | 1230 | `group_combo = dialog.findChild(main_module.QComboBox, "modelSettingsVlmImageGroupCombo")` | - | TBD |
| tests/test_gui_smoke.py | 1233 | `profile_combo = dialog.findChild(main_module.QComboBox, "modelSettingsVlmPromptProfileCombo")` | - | TBD |
| tests/test_gui_smoke.py | 1244 | `dialog = main_module.ModelSettingsDialog(` | - | TBD |
| tests/test_gui_smoke.py | 1270 | `combo = dialog.findChild(main_module.QComboBox, "modelSettingsVlmImageGroupCombo")` | - | TBD |
| tests/test_gui_smoke.py | 1280 | `dialog = main_module.ModelSettingsDialog(` | - | TBD |
| tests/test_gui_smoke.py | 1333 | `dialog = main_module.GeneralSettingsDialog(` | - | TBD |
| tests/test_gui_smoke.py | 1350 | `self.assertIsNotNone(dialog.findChild(main_module.QPushButton, "generalSettingsAskAgentButton"))` | - | TBD |
| tests/test_gui_smoke.py | 1355 | `self.assertIsNone(dialog.findChild(main_module.QWidget, "modelSettingsLocatorScopePanel"))` | - | TBD |
| tests/test_gui_smoke.py | 1362 | `model_dialog = main_module.ModelSettingsDialog(` | - | TBD |
| tests/test_gui_smoke.py | 1374 | `"model_backend": main_module.EXTERNAL_BACKEND_ID,` | - | TBD |
| tests/test_gui_smoke.py | 1392 | `model_dialog.child_backend_combo.findData(main_module.CHILD_BACKEND_EXTERNAL)` | - | TBD |
| tests/test_gui_smoke.py | 1410 | `"expert_backend": main_module.ROUTE_BACKEND_HEATMAP_BLINK,` | - | TBD |
| tests/test_gui_smoke.py | 1421 | `self.assertEqual(context["parent_model_source"], main_module.PARENT_BACKEND_EXTERNAL)` | - | TBD |
| tests/test_gui_smoke.py | 1422 | `self.assertEqual(context["default_child_expert"], main_module.CHILD_BACKEND_EXTERNAL)` | - | TBD |
| tests/test_gui_smoke.py | 1423 | `self.assertEqual(context["default_child_route_backend"], main_module.ROUTE_BACKEND_EXTERNAL_BLINK)` | - | TBD |
| tests/test_gui_smoke.py | 1436 | `compact = window._compact_agent_context(context)` | `_compact_agent_context` | TBD |
| tests/test_gui_smoke.py | 1440 | `self.assertEqual(compact["default_child_expert"], main_module.CHILD_BACKEND_EXTERNAL)` | - | TBD |
| tests/test_gui_smoke.py | 1460 | `tif_compact = window._compact_agent_context(` | `_compact_agent_context` | TBD |
| tests/test_gui_smoke.py | 1548 | `pdf_compact = window._compact_agent_context(` | `_compact_agent_context` | TBD |
| tests/test_gui_smoke.py | 1598 | `with patch.object(project_lifecycle_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1622 | `with patch.object(project_lifecycle_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1642 | `with patch.object(project_lifecycle_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1671 | `with patch.object(main_module.QMessageBox, "information", return_value=main_module.QMessageBox.Ok):` | - | TBD |
| tests/test_gui_smoke.py | 1678 | `with patch.object(main_module.QFileDialog, "getSaveFileName", return_value=(str(export_path), "JSON (*.json)")), \` | - | TBD |
| tests/test_gui_smoke.py | 1679 | `patch.object(main_module.QMessageBox, "information", return_value=main_module.QMessageBox.Ok):` | - | TBD |
| tests/test_gui_smoke.py | 1696 | `with patch.object(project_lifecycle_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1723 | `with patch.object(project_lifecycle_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1746 | `with patch.object(project_lifecycle_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1790 | `with patch.object(project_lifecycle_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1799 | `self.assertEqual(header.data(main_module.Qt.UserRole + 1), "original")` | - | TBD |
| tests/test_gui_smoke.py | 1826 | `with patch.object(project_lifecycle_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1849 | `with patch.object(project_lifecycle_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1873 | `with patch.object(main_module.QFileDialog, "getExistingDirectory", fake_get_existing_directory), \` | - | TBD |
| tests/test_gui_smoke.py | 1874 | `patch.object(main_module.QInputDialog, "getText", return_value=("review", True)), \` | - | TBD |
| tests/test_gui_smoke.py | 1891 | `ant_project_dir = Path(main_module.PACKAGE_DIR)` | - | TBD |
| tests/test_gui_smoke.py | 1893 | `self.assertEqual(Path(window._default_open_project_dir()), self.project_dir / "TaxaMask_outputs")` | `_default_open_project_dir` | TBD |
| tests/test_gui_smoke.py | 1897 | `self.assertEqual(Path(window._default_2d_export_dir()), project_dir / "exports")` | `_default_2d_export_dir` | TBD |
| tests/test_gui_smoke.py | 1898 | `self.assertEqual(Path(window._vlm_preannotation_artifacts_dir()), project_dir / "vlm_preannotation")` | `_vlm_preannotation_artifacts_dir` | TBD |
| tests/test_gui_smoke.py | 1900 | `dialog = main_module.ExportDialog(window, "en", default_dir=window._default_2d_export_dir())` | `_default_2d_export_dir` | TBD |
| tests/test_gui_smoke.py | 1918 | `window._create_vlm_progress_dialog()` | `_create_vlm_progress_dialog` | TBD |
| tests/test_gui_smoke.py | 1920 | `window._advance_vlm_progress("prepare")` | `_advance_vlm_progress` | TBD |
| tests/test_gui_smoke.py | 1924 | `self.assertEqual(progress.windowModality(), main_module.Qt.NonModal)` | - | TBD |
| tests/test_gui_smoke.py | 1938 | `window._mark_current_vlm_image_done("done")` | `_mark_current_vlm_image_done` | TBD |
| tests/test_gui_smoke.py | 1970 | `original_refresh = window._refresh_vlm_canvas_if_current` | `_refresh_vlm_canvas_if_current` | TBD |
| tests/test_gui_smoke.py | 1971 | `window._refresh_vlm_canvas_if_current = lambda path: (refresh_calls.append(path), original_refresh(path))` | `_refresh_vlm_canvas_if_current` | TBD |
| tests/test_gui_smoke.py | 1974 | `window._on_vlm_preannotation_image_result(` | `_on_vlm_preannotation_image_result` | TBD |
| tests/test_gui_smoke.py | 2029 | `window._on_vlm_preannotation_image_result(` | `_on_vlm_preannotation_image_result` | TBD |
| tests/test_gui_smoke.py | 2073 | `window._on_vlm_preannotation_image_result(` | `_on_vlm_preannotation_image_result` | TBD |
| tests/test_gui_smoke.py | 2113 | `window._create_vlm_progress_dialog()` | `_create_vlm_progress_dialog` | TBD |
| tests/test_gui_smoke.py | 2121 | `window._on_vlm_preannotation_image_result(` | `_on_vlm_preannotation_image_result` | TBD |
| tests/test_gui_smoke.py | 2172 | `window._set_panel_split_review(str(manual_image), "manual_required", reason="hard_seam_panel_split")` | `_set_panel_split_review` | TBD |
| tests/test_gui_smoke.py | 2183 | `batch_paths = window._vlm_image_paths_for_scope(window._current_vlm_batch_scope())` | `_current_vlm_batch_scope`, `_vlm_image_paths_for_scope` | TBD |
| tests/test_gui_smoke.py | 2186 | `current_paths = window._vlm_image_paths_for_scope("current_image")` | `_vlm_image_paths_for_scope` | TBD |
| tests/test_gui_smoke.py | 2191 | `groups = window._project_image_groups()` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 2229 | `window._on_vlm_preannotation_image_result(` | `_on_vlm_preannotation_image_result` | TBD |
| tests/test_gui_smoke.py | 2272 | `window._refresh_vlm_canvas_if_current(image_key)` | `_refresh_vlm_canvas_if_current` | TBD |
| tests/test_gui_smoke.py | 2299 | `ok, mode = window._apply_vlm_candidate(` | `_apply_vlm_candidate` | TBD |
| tests/test_gui_smoke.py | 2355 | `ok, mode = window._apply_vlm_candidate(` | `_apply_vlm_candidate` | TBD |
| tests/test_gui_smoke.py | 2389 | `window._same_project_image_path(` | `_same_project_image_path` | TBD |
| tests/test_gui_smoke.py | 2390 | `window.file_list.currentItem().data(main_module.Qt.UserRole),` | - | TBD |
| tests/test_gui_smoke.py | 2404 | `for index in range(main_module.BACKGROUND_IMAGE_IMPORT_THRESHOLD):` | - | TBD |
| tests/test_gui_smoke.py | 2437 | `started = window._start_image_import(image_paths)` | `_start_image_import` | TBD |
| tests/test_gui_smoke.py | 2463 | `window.model_backend = main_module.EXTERNAL_BACKEND_ID` | - | TBD |
| tests/test_gui_smoke.py | 2515 | `with patch.object(main_module, "_runtime_parent_backend", lambda *_args, **_kwargs: main_module.EXTERNAL_BACKEND_ID), \` | - | TBD |
| tests/test_gui_smoke.py | 2516 | `patch.object(main_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes), \` | - | TBD |
| tests/test_gui_smoke.py | 2550 | `path = item.data(main_module.Qt.UserRole)` | - | TBD |
| tests/test_gui_smoke.py | 2563 | `with patch.object(image_navigation_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 2712 | `prompt = window._pdf_agent_prompt()` | `_pdf_agent_prompt` | TBD |
| tests/test_gui_smoke.py | 2865 | `window._inherit_crop_provenance(` | `_inherit_crop_provenance` | TBD |
| tests/test_gui_smoke.py | 2882 | `self.assertTrue(window._is_pdf_candidate_provenance(crop_provenance))` | `_is_pdf_candidate_provenance` | TBD |
| tests/test_gui_smoke.py | 2899 | `window._inherit_crop_provenance(` | `_inherit_crop_provenance` | TBD |
| tests/test_gui_smoke.py | 2916 | `self.assertTrue(window._is_split_crop_image(str(crop_image)))` | `_is_split_crop_image` | TBD |
| tests/test_gui_smoke.py | 2928 | `window._set_panel_split_review(str(parent_image), "manual_required", reason="hard_seam_panel_split")` | `_set_panel_split_review` | TBD |
| tests/test_gui_smoke.py | 2930 | `window._inherit_crop_provenance(` | `_inherit_crop_provenance` | TBD |
| tests/test_gui_smoke.py | 2947 | `self.assertFalse(window._needs_manual_panel_split(str(parent_image)))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 2948 | `self.assertFalse(window._needs_manual_panel_split(str(crop_image)))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 2973 | `window._set_panel_split_review(str(parent_image), "manual_required", reason="hard_seam_panel_split")` | `_set_panel_split_review` | TBD |
| tests/test_gui_smoke.py | 2975 | `self.assertTrue(window._has_split_crops_from_image(str(parent_image)))` | `_has_split_crops_from_image` | TBD |
| tests/test_gui_smoke.py | 2976 | `self.assertFalse(window._needs_manual_panel_split(str(parent_image)))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 2977 | `self.assertFalse(window._needs_manual_panel_split(str(crop_image)))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 3001 | `self.assertTrue(window._needs_manual_panel_split(str(image_path)))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 3007 | `self.assertFalse(window._needs_manual_panel_split(str(image_path)))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 3030 | `window._set_panel_split_review(str(image_a), "manual_required", reason="hard_seam_panel_split")` | `_set_panel_split_review` | TBD |
| tests/test_gui_smoke.py | 3031 | `window._set_panel_split_review(str(image_b), "manual_required", reason="hard_seam_panel_split")` | `_set_panel_split_review` | TBD |
| tests/test_gui_smoke.py | 3041 | `groups = window._project_image_groups()` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 3059 | `window._set_panel_split_review(str(image_path), "manual_done", reason="user_marked_done")` | `_set_panel_split_review` | TBD |
| tests/test_gui_smoke.py | 3061 | `self.assertEqual([Path(path).name for path in window._project_image_groups()["manual_done"]], [image_path.name])` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 3064 | `groups = window._project_image_groups()` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 3088 | `groups = window._project_image_groups()` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 3091 | `self.assertEqual(window._vlm_image_group_label("review_ready"), "Review Ready")` | `_vlm_image_group_label` | TBD |
| tests/test_gui_smoke.py | 3101 | `self.assertEqual(window._current_vlm_image_group(), "review_ready")` | `_current_vlm_image_group` | TBD |
| tests/test_gui_smoke.py | 3102 | `paths = window._vlm_image_paths_for_scope("image_group")` | `_vlm_image_paths_for_scope` | TBD |
| tests/test_gui_smoke.py | 3130 | `groups = window._project_image_groups()` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 3157 | `self.assertIn("review_ready", {group_id for group_id, _label in window._image_group_move_target_definitions()})` | `_image_group_move_target_definitions` | TBD |
| tests/test_gui_smoke.py | 3161 | `self.assertEqual(window._custom_image_group_definitions(), [])` | `_custom_image_group_definitions` | TBD |
| tests/test_gui_smoke.py | 3163 | `self.assertNotIn("review_ready", {group_id for group_id, _label in window._image_group_move_target_definitions()})` | `_image_group_move_target_definitions` | TBD |
| tests/test_gui_smoke.py | 3186 | `if item.data(main_module.Qt.UserRole) and _same_path(item.data(main_module.Qt.UserRole), image_a):` | - | TBD |
| tests/test_gui_smoke.py | 3240 | `self.assertTrue(window._is_split_crop_image(str(crop_image)))` | `_is_split_crop_image` | TBD |
| tests/test_gui_smoke.py | 3241 | `self.assertFalse(window._is_split_crop_image(str(unrelated_crop)))` | `_is_split_crop_image` | TBD |
| tests/test_gui_smoke.py | 3286 | `with patch.object(image_navigation_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 3287 | `with patch.object(main_module.QMessageBox, "information", lambda *args, **kwargs: None):` | - | TBD |
| tests/test_gui_smoke.py | 3313 | `self.assertTrue(window._is_split_crop_image(generated))` | `_is_split_crop_image` | TBD |
| tests/test_gui_smoke.py | 3314 | `self.assertFalse(window._needs_manual_panel_split(generated))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 3319 | `self.assertTrue(window._is_split_crop_image(generated))` | `_is_split_crop_image` | TBD |
| tests/test_gui_smoke.py | 3320 | `self.assertFalse(window._needs_manual_panel_split(generated))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 3325 | `groups = window._project_image_groups()` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 3371 | `with patch.object(image_navigation_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 3372 | `with patch.object(main_module.QMessageBox, "information", lambda *args, **kwargs: None):` | - | TBD |
| tests/test_gui_smoke.py | 3380 | `groups = window._project_image_groups()` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 3443 | `window._ensure_pdf_widget()` | `_ensure_pdf_widget` | TBD |
| tests/test_gui_smoke.py | 3446 | `db_path, context, reason = window._resolve_current_literature_context()` | `_resolve_current_literature_context` | TBD |
| tests/test_gui_smoke.py | 3466 | `window._ensure_pdf_widget()` | `_ensure_pdf_widget` | TBD |
| tests/test_gui_smoke.py | 3482 | `db_path, context, reason = window._resolve_current_literature_context()` | `_resolve_current_literature_context` | TBD |
| tests/test_gui_smoke.py | 3504 | `window._ensure_pdf_widget()` | `_ensure_pdf_widget` | TBD |
| tests/test_gui_smoke.py | 3531 | `db_path, context, reason = window._resolve_current_literature_context()` | `_resolve_current_literature_context` | TBD |
| tests/test_gui_smoke.py | 3551 | `window._ensure_pdf_widget()` | `_ensure_pdf_widget` | TBD |
| tests/test_gui_smoke.py | 3567 | `with patch.object(main_module.QFileDialog, "getOpenFileName", return_value=(str(literature_db), "SQLite Database (*.db)")):` | - | TBD |
| tests/test_gui_smoke.py | 3568 | `db_path, context, reason = window._choose_literature_db_for_current_taxon()` | `_choose_literature_db_for_current_taxon` | TBD |
| tests/test_gui_smoke.py | 3613 | `dialog = main_module.LiteratureDescriptionDialog(` | - | TBD |
| tests/test_gui_smoke.py | 3645 | `dialog = main_module.LiteratureDescriptionDialog(` | - | TBD |
| tests/test_gui_smoke.py | 3747 | `self.assertTrue(window._is_stl_project_file(stl_path))` | `_is_stl_project_file` | TBD |
| tests/test_gui_smoke.py | 3748 | `with patch.object(main_module.QFileDialog, "getOpenFileName", return_value=(stl_path, "JSON (*.json)")):` | - | TBD |
| tests/test_gui_smoke.py | 3759 | `self.assertEqual(window._active_recent_project_path(), os.path.abspath(stl_path))` | `_active_recent_project_path` | TBD |
| tests/test_gui_smoke.py | 3761 | `context = window._collect_image_workbench_agent_context()` | `_collect_image_workbench_agent_context` | TBD |
| tests/test_gui_smoke.py | 3765 | `self.assertIn("STL rendered-view project", window._start_console_project_summary()[0])` | `_start_console_project_summary` | TBD |
| tests/test_gui_smoke.py | 3766 | `self.assertIn("1 STL rendered 2D view", window._start_console_image_summary()[0])` | `_start_console_image_summary` | TBD |
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
| tests/test_ui_polish_scope.py | 957 | `preflight_dialog = main_module.TrainingPreflightDialog(preflight, parent=owner, lang="en")` | - | TBD |
| tests/test_ui_polish_scope.py | 958 | `entry_dialog = main_module.BlinkEntryDialog(` | - | TBD |
| tests/test_ui_polish_scope.py | 1016 | `patch.object(main_module.QTimer, "singleShot", lambda *args, **kwargs: None):` | - | TBD |
| tests/test_ui_polish_scope.py | 1017 | `return main_module.MainWindow()` | - | TBD |
| tests/test_ui_polish_scope.py | 1171 | `with patch.object(main_module.QMessageBox, "information", lambda *args, **kwargs: None):` | - | TBD |
| tests/test_ui_polish_scope.py | 1205 | `with patch.object(main_module.QMessageBox, "information", lambda *args, **kwargs: None):` | - | TBD |
| tests/test_ui_polish_scope.py | 1212 | `with patch.object(main_module.QMessageBox, "information", lambda *args, **kwargs: None):` | - | TBD |
| tests/test_ui_polish_scope.py | 1348 | `if item.data(main_module.Qt.UserRole + 1) == "original":` | - | TBD |
| tests/test_ui_polish_scope.py | 1354 | `window._handle_image_list_item_clicked(original_header)` | `_handle_image_list_item_clicked` | TBD |
| tests/test_ui_polish_scope.py | 1384 | `cached_state = window._image_list_state_cache` | `_image_list_state_cache` | TBD |
| tests/test_ui_polish_scope.py | 1391 | `if item.data(main_module.Qt.UserRole + 1) == "original":` | - | TBD |
| tests/test_ui_polish_scope.py | 1397 | `window._handle_image_list_item_clicked(original_header)` | `_handle_image_list_item_clicked` | TBD |
| tests/test_ui_polish_scope.py | 1400 | `self.assertIs(window._image_list_state_cache, cached_state)` | `_image_list_state_cache` | TBD |
| tests/test_ui_polish_scope.py | 1423 | `window._apply_literature_description(` | `_apply_literature_description` | TBD |
| tests/test_ui_polish_scope.py | 1481 | `self.assertEqual(head_item.data(0, main_module.Qt.UserRole), "Head")` | - | TBD |
| tests/test_ui_polish_scope.py | 1483 | `self.assertEqual(head_item.child(0).data(0, main_module.Qt.UserRole), "Mandible")` | - | TBD |
| tests/test_ui_polish_scope.py | 1486 | `self.assertIsNone(cross_region_item.data(0, main_module.Qt.UserRole))` | - | TBD |
| tests/test_ui_polish_scope.py | 1487 | `self.assertEqual(cross_region_item.child(0).data(0, main_module.Qt.UserRole), "Seta")` | - | TBD |
| tests/test_ui_polish_scope.py | 1491 | `self.assertEqual(window._current_part_name(), "Mandible")` | `_current_part_name` | TBD |
| tests/test_ui_polish_scope.py | 1496 | `self.assertIsNone(window._current_part_name())` | `_current_part_name` | TBD |
| tests/test_ui_polish_scope.py | 1540 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 1541 | `context = window._refresh_blink_refine_state()` | `_refresh_blink_refine_state` | TBD |
| tests/test_ui_polish_scope.py | 1574 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 1584 | `context = window._refresh_blink_refine_state()` | `_refresh_blink_refine_state` | TBD |
| tests/test_ui_polish_scope.py | 1610 | `self.assertEqual(window.part_list.topLevelItem(0).data(0, main_module.Qt.UserRole), "Head")` | - | TBD |
| tests/test_ui_polish_scope.py | 1613 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 1614 | `context = window._refresh_blink_refine_state()` | `_refresh_blink_refine_state` | TBD |
| tests/test_ui_polish_scope.py | 1629 | `self.assertEqual(window.part_list.topLevelItem(0).child(0).data(0, main_module.Qt.UserRole), "Mandible")` | - | TBD |
| tests/test_ui_polish_scope.py | 1653 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 1654 | `context = window._refresh_blink_refine_state()` | `_refresh_blink_refine_state` | TBD |
| tests/test_ui_polish_scope.py | 1672 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 1701 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 1724 | `window._select_part_in_tree("Head")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 1745 | `canvas = main_module.AnnotationCanvas()` | - | TBD |
| tests/test_ui_polish_scope.py | 1776 | `window._select_part_in_tree("Head")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 1780 | `with patch.object(main_module.QMessageBox, "information") as info:` | - | TBD |
| tests/test_ui_polish_scope.py | 1832 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 1901 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 1902 | `before_context = window._refresh_blink_refine_state()` | `_refresh_blink_refine_state` | TBD |
| tests/test_ui_polish_scope.py | 1908 | `after_context = window._refresh_blink_refine_state()` | `_refresh_blink_refine_state` | TBD |
| tests/test_ui_polish_scope.py | 1941 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 1942 | `context = window._refresh_blink_refine_state()` | `_refresh_blink_refine_state` | TBD |
| tests/test_ui_polish_scope.py | 1947 | `with patch.object(main_module.QMessageBox, "information") as info:` | - | TBD |
| tests/test_ui_polish_scope.py | 1953 | `window._refresh_blink_refine_state()` | `_refresh_blink_refine_state` | TBD |
| tests/test_ui_polish_scope.py | 1999 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 2000 | `context = window._refresh_blink_refine_state()` | `_refresh_blink_refine_state` | TBD |
| tests/test_ui_polish_scope.py | 2006 | `with patch.object(main_module.QMessageBox, "information") as info:` | - | TBD |
| tests/test_ui_polish_scope.py | 2064 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 2137 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 2139 | `with patch.object(main_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_ui_polish_scope.py | 2177 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 2178 | `with patch.object(main_module.QMessageBox, "information") as info:` | - | TBD |
| tests/test_ui_polish_scope.py | 2183 | `with patch.object(main_module.QMessageBox, "information") as info:` | - | TBD |
| tests/test_ui_polish_scope.py | 2219 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 2319 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 2360 | `window._connect_child_training_progress()` | `_connect_child_training_progress` | TBD |
| tests/test_ui_polish_scope.py | 2384 | `main_module.json.dumps(` | - | TBD |
| tests/test_ui_polish_scope.py | 2392 | `"parent_backend": main_module.PARENT_BACKEND_BUILTIN,` | - | TBD |
| tests/test_ui_polish_scope.py | 2402 | `main_module.json.dumps(` | - | TBD |
| tests/test_ui_polish_scope.py | 2408 | `"training_strategy": main_module.BLINK_STRATEGY_TWO_STAGE_FULL_THEN_INSIDE,` | - | TBD |
| tests/test_ui_polish_scope.py | 2433 | `dialog = main_module.TrainingResultBrowserDialog(reports, lang="en")` | - | TBD |
| tests/test_ui_polish_scope.py | 2469 | `window._select_part_in_tree("Mandible")` | `_select_part_in_tree` | TBD |
| tests/test_ui_polish_scope.py | 2473 | `patch.object(main_module.QMessageBox, "information") as info:` | - | TBD |
| tests/test_ui_polish_scope.py | 2481 | `with patch.object(main_module.QMessageBox, "information") as info:` | - | TBD |
| tests/test_ui_polish_scope.py | 2503 | `return_value=main_module.QMessageBox.Yes,` | - | TBD |
| tests/test_ui_polish_scope.py | 2569 | `dialog = main_module.ModelSettingsDialog(` | - | TBD |
| tests/test_ui_polish_scope.py | 2608 | `self.assertIsNotNone(dialog.findChild(main_module.QToolButton, "modelSettingsVlmDetailToggle"))` | - | TBD |
| tests/test_ui_polish_scope.py | 2625 | `with patch.object(main_module.QDialog, "exec", return_value=main_module.QDialog.DialogCode.Accepted) as exec_dialog:` | - | TBD |
| tests/test_ui_polish_scope.py | 2628 | `with patch.object(model_settings_dataset_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_ui_polish_scope.py | 2634 | `self.assertIsInstance(dialog.spin_blink_auto_shrink_steps, main_module.NoWheelSpinBox)` | - | TBD |
| tests/test_ui_polish_scope.py | 2636 | `self.assertIsInstance(dialog.spin_vlm_concurrency, main_module.NoWheelSpinBox)` | - | TBD |
| tests/test_ui_polish_scope.py | 2676 | `spin = main_module.NoWheelSpinBox()` | - | TBD |
| tests/test_ui_polish_scope.py | 2684 | `slider = main_module.NoWheelSlider(main_module.Qt.Horizontal)` | - | TBD |
| tests/test_ui_polish_scope.py | 2738 | `return_value=main_module.QMessageBox.Yes,` | - | TBD |
| tests/test_ui_polish_scope.py | 2794 | `main_module.QInputDialog,` | - | TBD |
| tests/test_ui_polish_scope.py | 2819 | `dialog = main_module.ModelSettingsDialog(` | - | TBD |
| tests/test_ui_polish_scope.py | 2840 | `device_combo = runtime_group.findChild(main_module.QComboBox)` | - | TBD |
| tests/test_ui_polish_scope.py | 2848 | `checks = {check.text(): check for check in locator_group.findChildren(main_module.QCheckBox)}` | - | TBD |
| tests/test_ui_polish_scope.py | 2871 | `dialog = main_module.ModelSettingsDialog(` | - | TBD |
| tests/test_ui_polish_scope.py | 2988 | `saved, total = window._apply_prediction_to_project(image_key, prediction, only_new=True, save=False)` | `_apply_prediction_to_project` | TBD |
| tests/test_ui_polish_scope.py | 3000 | `saved, total = window._apply_prediction_to_project(` | `_apply_prediction_to_project` | TBD |
| tests/test_ui_polish_scope.py | 3038 | `ok, mode = window._apply_vlm_candidate(` | `_apply_vlm_candidate` | TBD |
| tests/test_ui_polish_scope.py | 3080 | `saved, total = window._apply_prediction_to_project(image_key, prediction, only_new=True, save=False)` | `_apply_prediction_to_project` | TBD |
| tests/test_ui_polish_scope.py | 3120 | `window._refresh_current_canvas_boxes()` | `_refresh_current_canvas_boxes` | TBD |
| tests/test_ui_polish_scope.py | 3150 | `ok, mode = window._apply_vlm_candidate(` | `_apply_vlm_candidate` | TBD |
| tests/test_ui_polish_scope.py | 3168 | `ok, mode = window._apply_vlm_candidate(` | `_apply_vlm_candidate` | TBD |
| tests/test_ui_polish_scope.py | 3205 | `context = window._collect_image_workbench_agent_context()` | `_collect_image_workbench_agent_context` | TBD |
| tests/test_ui_polish_scope.py | 3211 | `compact = window._compact_agent_context(context)` | `_compact_agent_context` | TBD |
| tests/test_ui_polish_scope.py | 3227 | `window._on_training_success()` | `_on_training_success` | TBD |
| tests/test_ui_polish_scope.py | 3309 | `main_module.QInputDialog,` | - | TBD |
| tests/test_ui_polish_scope.py | 3327 | `main_module.QInputDialog,` | - | TBD |
| tests/test_ui_polish_scope.py | 3351 | `return_value=main_module.QMessageBox.Yes,` | - | TBD |
| tests/test_ui_polish_scope.py | 3427 | `return_value=main_module.QMessageBox.Yes,` | - | TBD |
| tests/test_ui_polish_scope.py | 3455 | `return_value=main_module.QMessageBox.Yes,` | - | TBD |
| tests/test_ui_polish_scope.py | 3549 | `window._flush_pending_project_save()` | `_flush_pending_project_save` | TBD |
| tests/test_ui_polish_scope.py | 3687 | `if item.data(main_module.Qt.UserRole) == image_paths[0]:` | - | TBD |
| tests/test_ui_polish_scope.py | 3694 | `with patch.object(image_navigation_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes), \` | - | TBD |
| tests/test_ui_polish_scope.py | 3707 | `window.file_list.item(row).data(main_module.Qt.UserRole)` | - | TBD |
| tests/test_ui_polish_scope.py | 3709 | `if window.file_list.item(row).data(main_module.Qt.UserRole)` | - | TBD |
| tests/test_ui_polish_scope.py | 3746 | `if item.data(main_module.Qt.UserRole) == image_paths[1]:` | - | TBD |
| tests/test_ui_polish_scope.py | 3752 | `with patch.object(image_navigation_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_ui_polish_scope.py | 3757 | `self.assertEqual(window.file_list.currentItem().data(main_module.Qt.UserRole), image_paths[2])` | - | TBD |
| tests/test_ui_polish_scope.py | 3759 | `window.file_list.item(row).data(main_module.Qt.UserRole)` | - | TBD |
| tests/test_ui_polish_scope.py | 3761 | `if window.file_list.item(row).data(main_module.Qt.UserRole)` | - | TBD |
| tests/test_ui_polish_scope.py | 3798 | `if item.data(main_module.Qt.UserRole) == image_paths[2]:` | - | TBD |
| tests/test_ui_polish_scope.py | 3804 | `with patch.object(image_navigation_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_ui_polish_scope.py | 3809 | `self.assertEqual(window.file_list.currentItem().data(main_module.Qt.UserRole), image_paths[1])` | - | TBD |
| tests/test_ui_polish_scope.py | 3811 | `window.file_list.item(row).data(main_module.Qt.UserRole)` | - | TBD |
| tests/test_ui_polish_scope.py | 3813 | `if window.file_list.item(row).data(main_module.Qt.UserRole)` | - | TBD |
| tests/test_ui_polish_scope.py | 4011 | `return_value=main_module.QMessageBox.No,` | - | TBD |
| tests/test_ui_polish_scope.py | 4020 | `return_value=main_module.QMessageBox.Yes,` | - | TBD |
| tests/test_ui_polish_scope.py | 4063 | `return_value=main_module.QMessageBox.Yes,` | - | TBD |
| tests/test_ui_polish_scope.py | 4106 | `window.vlm_preannotation_prompt_profile = main_module.default_vlm_prompt_profile()` | - | TBD |
| tests/test_ui_polish_scope.py | 4112 | `return_value=main_module.QMessageBox.Yes,` | - | TBD |
| tests/test_ui_polish_scope.py | 4123 | `window._on_vlm_preannotation_finished()` | `_on_vlm_preannotation_finished` | TBD |
| tests/test_ui_polish_scope.py | 4164 | `window.vlm_preannotation_prompt_profile = main_module.default_vlm_prompt_profile()` | - | TBD |
| tests/test_ui_polish_scope.py | 4168 | `window._start_vlm_preannotation_workers()` | `_start_vlm_preannotation_workers` | TBD |
| tests/test_ui_polish_scope.py | 4273 | `return_value=main_module.QMessageBox.Yes,` | - | TBD |
| tests/test_ui_polish_scope.py | 4334 | `return_value=main_module.QMessageBox.Yes,` | - | TBD |
| tests/test_ui_polish_scope.py | 4399 | `self.assertFalse(window._flush_pending_project_save())` | `_flush_pending_project_save` | TBD |
| tests/test_ui_polish_scope.py | 4404 | `window._flush_pending_project_save(force=True)` | `_flush_pending_project_save` | TBD |
| tests/test_ui_polish_scope.py | 4515 | `window._on_vlm_preannotation_image_result(result)` | `_on_vlm_preannotation_image_result` | TBD |
