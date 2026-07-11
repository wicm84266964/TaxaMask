# TaxaMask Round 4 Main Window Method Inventory

由 `scripts/analyze_main_window_architecture.py` 生成。Stage 0 冻结当前责任、兼容入口和目标阶段，实施时必须结合真实调用复核。

## Metrics

| Metric | Value |
| --- | --- |
| main_physical_lines | 7207 |
| top_level_class_count | 1 |
| top_level_function_count | 0 |
| all_method_count | 283 |
| private_method_count | 194 |
| connection_count | 194 |
| source_state_assignment_lines | 160 |
| main_window_lines | 6703 |
| main_window_method_count | 283 |
| main_window_connection_count | 51 |
| main_window_init_lines | 13 |
| main_window_methods_ge_50 | 35 |
| main_window_methods_ge_100 | 7 |
| main_window_unique_state_fields | 86 |
| main_window_state_assignment_occurrences | 170 |
| main_import_site_count | 22 |
| key_test_reference_line_count | 328 |
| key_test_private_reference_occurrences | 146 |
| key_test_unique_private_references | 53 |
| async_entry_count | 16 |

## Top-level Classes

| Line | Size | Class | Methods | Connects | Refs | Stage |
| --- | --- | --- | --- | --- | --- | --- |
| 483 | 6703 | `MainWindow` | 283 | 51 | 36 | 3 |

## MainWindow Workflow Counts

| Workflow | Methods |
| --- | --- |
| annotation_sam | 20 |
| blink | 34 |
| dialog_settings | 33 |
| image_navigation | 61 |
| project_lifecycle | 5 |
| runtime_worker | 12 |
| shell_start_agent | 8 |
| training_model | 38 |
| unclassified | 24 |
| vlm_prediction_export | 48 |

## Compatibility Counts

| Compatibility | Methods |
| --- | --- |
| internal_or_unreferenced | 142 |
| public_or_source_compatibility | 83 |
| signal_compatibility | 11 |
| test_compatibility | 47 |

## MainWindow Methods

| Line | Size | Method | Workflow | Stage | Compatibility | Source refs | Test refs | Signal refs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 493 | 13 | `__init__` | unclassified | 8 | public_or_source_compatibility | 217 | 135 | 0 |
| 510 | 51 | `refresh_model_list` | training_model | 7 | public_or_source_compatibility | 1 | 0 | 0 |
| 562 | 5 | `_selected_locator_timestamp` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 568 | 4 | `_selected_locator_display_text` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 573 | 9 | `_parent_model_filename` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 583 | 40 | `_build_locator_combo_label` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 624 | 7 | `_build_segmenter_combo_label` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 632 | 5 | `_selected_segmenter_timestamp` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 638 | 2 | `_active_project_route_manifest` | dialog_settings | 2 | public_or_source_compatibility | 1 | 0 | 0 |
| 641 | 9 | `_active_model_profile_context` | dialog_settings | 2 | public_or_source_compatibility | 1 | 0 | 0 |
| 651 | 6 | `_active_external_backend_config` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 658 | 5 | `_selected_route_entry` | dialog_settings | 2 | public_or_source_compatibility | 7 | 0 | 0 |
| 664 | 5 | `_route_runtime_status` | runtime_worker | 1 | public_or_source_compatibility | 2 | 0 | 0 |
| 670 | 8 | `refresh_route_table` | dialog_settings | 2 | public_or_source_compatibility | 12 | 30 | 2 |
| 679 | 4 | `update_route_action_buttons` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 685 | 4 | `appoint_selected_route_expert` | blink | 6 | public_or_source_compatibility | 2 | 1 | 1 |
| 690 | 4 | `toggle_selected_route_enabled` | dialog_settings | 2 | public_or_source_compatibility | 2 | 0 | 1 |
| 695 | 4 | `delete_selected_route` | dialog_settings | 2 | public_or_source_compatibility | 2 | 2 | 1 |
| 700 | 30 | `_log_route_usage_summary` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 731 | 4 | `_locator_model_path` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 736 | 4 | `_segmenter_model_path` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 741 | 18 | `_apply_locator_selection_to_runtime` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 760 | 2 | `_locator_selection_needs_legacy_confirmation` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 763 | 20 | `_confirm_legacy_locator_selection_if_needed` | training_model | 7 | test_compatibility | 0 | 1 | 0 |
| 784 | 5 | `_show_structured_training_preflight` | dialog_settings | 2 | test_compatibility | 0 | 1 | 0 |
| 790 | 3 | `_is_locator_oom_error` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 794 | 30 | `_ask_locator_oom_retry_resolution` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 825 | 3 | `_is_parent_training_running` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 829 | 4 | `_is_child_training_running` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 834 | 2 | `_is_any_training_running` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 837 | 19 | `_set_training_progress` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 857 | 11 | `_connect_child_training_progress` | blink | 6 | test_compatibility | 0 | 1 | 0 |
| 869 | 6 | `_on_child_training_result` | blink | 6 | signal_compatibility | 0 | 0 | 1 |
| 876 | 3 | `_on_child_training_error` | blink | 6 | signal_compatibility | 0 | 0 | 1 |
| 880 | 3 | `_on_child_training_cancelled` | blink | 6 | signal_compatibility | 0 | 0 | 1 |
| 884 | 10 | `_on_child_training_finished` | blink | 6 | signal_compatibility | 0 | 0 | 1 |
| 895 | 87 | `_launch_training_with_preflight` | dialog_settings | 2 | test_compatibility | 0 | 1 | 0 |
| 983 | 15 | `_on_training_success` | training_model | 7 | signal_compatibility | 0 | 1 | 1 |
| 999 | 13 | `_on_training_finished` | training_model | 7 | public_or_source_compatibility | 2 | 1 | 1 |
| 1013 | 38 | `_on_training_error` | training_model | 7 | public_or_source_compatibility | 2 | 0 | 1 |
| 1052 | 7 | `stop_training` | training_model | 7 | public_or_source_compatibility | 1 | 0 | 1 |
| 1060 | 21 | `_apply_segmenter_selection_to_runtime` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 1082 | 12 | `update_model_delete_button_states` | training_model | 7 | public_or_source_compatibility | 2 | 0 | 2 |
| 1095 | 33 | `_edit_parent_model_note` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 1129 | 2 | `edit_locator_model_note` | training_model | 7 | public_or_source_compatibility | 1 | 1 | 1 |
| 1132 | 2 | `edit_segmenter_model_note` | training_model | 7 | public_or_source_compatibility | 1 | 1 | 1 |
| 1135 | 36 | `on_locator_changed` | training_model | 7 | public_or_source_compatibility | 1 | 1 | 1 |
| 1172 | 26 | `delete_locator_model` | training_model | 7 | public_or_source_compatibility | 1 | 2 | 1 |
| 1199 | 3 | `on_segmenter_changed` | training_model | 7 | public_or_source_compatibility | 1 | 0 | 1 |
| 1203 | 26 | `delete_segmenter_model` | training_model | 7 | public_or_source_compatibility | 1 | 1 | 1 |
| 1230 | 3 | `on_model_changed` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 1234 | 29 | `create_menus` | shell_start_agent | 3 | public_or_source_compatibility | 3 | 0 | 0 |
| 1265 | 6 | `_part_item_name` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 1272 | 2 | `_current_part_name` | unclassified | 8 | public_or_source_compatibility | 1 | 5 | 0 |
| 1275 | 15 | `_workbench_parent_parts` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 1291 | 3 | `_is_parent_part` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 1295 | 23 | `_part_tree_parent_for` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 1319 | 18 | `_route_parents_for_child` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 1338 | 25 | `_resolve_child_parent` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 1364 | 15 | `_parent_context_box` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 1380 | 5 | `_current_shrink_loose_boxes` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 1386 | 28 | `_auto_boxes_for_canvas` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 1415 | 10 | `_refresh_current_canvas_boxes` | annotation_sam | 6 | test_compatibility | 0 | 1 | 0 |
| 1426 | 15 | `_route_entry_for_context` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 1442 | 26 | `_route_expert_status` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 1469 | 73 | `_current_blink_context` | blink | 6 | public_or_source_compatibility | 1 | 0 | 0 |
| 1543 | 10 | `_parent_box_aspect_ratio` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 1554 | 24 | `_parent_context_options` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 1579 | 15 | `_refresh_annotation_box_constraints` | annotation_sam | 6 | public_or_source_compatibility | 1 | 0 | 1 |
| 1595 | 8 | `_active_box_tool_role` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 1604 | 6 | `_refresh_blink_refine_state` | blink | 6 | public_or_source_compatibility | 1 | 9 | 0 |
| 1611 | 7 | `_append_part_tree_item` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 1619 | 22 | `_select_part_in_tree` | unclassified | 8 | test_compatibility | 0 | 18 | 0 |
| 1642 | 17 | `_first_selectable_part_item` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 1660 | 75 | `_refresh_part_tree` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 1736 | 8 | `add_taxonomy_part` | image_navigation | 5 | public_or_source_compatibility | 2 | 29 | 1 |
| 1745 | 7 | `_count_ai_labels_for_images` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 1753 | 67 | `_choose_clear_ai_scope` | unclassified | 8 | test_compatibility | 0 | 1 | 0 |
| 1821 | 41 | `rename_taxonomy_part` | image_navigation | 5 | public_or_source_compatibility | 2 | 3 | 1 |
| 1863 | 13 | `remove_taxonomy_part` | image_navigation | 5 | public_or_source_compatibility | 2 | 6 | 1 |
| 1877 | 55 | `clear_ai_labels` | unclassified | 8 | public_or_source_compatibility | 1 | 2 | 1 |
| 1933 | 6 | `on_global_labels_updated` | unclassified | 8 | public_or_source_compatibility | 1 | 0 | 1 |
| 1940 | 190 | `refresh_ui` | unclassified | 8 | public_or_source_compatibility | 3 | 0 | 0 |
| 2131 | 78 | `_update_blink_refine_panel` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 2210 | 39 | `_update_blink_parent_context_combo` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 2250 | 51 | `open_general_settings` | dialog_settings | 2 | public_or_source_compatibility | 2 | 0 | 1 |
| 2302 | 129 | `open_stl_model_settings` | dialog_settings | 2 | public_or_source_compatibility | 3 | 0 | 0 |
| 2432 | 2 | `open_settings` | dialog_settings | 2 | public_or_source_compatibility | 1 | 0 | 0 |
| 2435 | 15 | `open_tif_model_settings` | dialog_settings | 2 | public_or_source_compatibility | 2 | 0 | 0 |
| 2451 | 15 | `change_language` | shell_start_agent | 3 | public_or_source_compatibility | 4 | 8 | 0 |
| 2467 | 28 | `change_theme` | shell_start_agent | 3 | public_or_source_compatibility | 2 | 0 | 0 |
| 2496 | 15 | `update_widget_themes` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 2512 | 66 | `update_button_themes` | shell_start_agent | 3 | internal_or_unreferenced | 0 | 0 | 0 |
| 2578 | 4 | `add_images` | image_navigation | 5 | public_or_source_compatibility | 8 | 36 | 1 |
| 2583 | 94 | `_start_image_import` | shell_start_agent | 3 | test_compatibility | 0 | 1 | 0 |
| 2678 | 5 | `_set_image_import_controls_enabled` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 2684 | 20 | `open_cropper` | project_lifecycle | 4 | public_or_source_compatibility | 1 | 0 | 1 |
| 2705 | 8 | `_is_split_crop_image` | image_navigation | 5 | test_compatibility | 0 | 5 | 0 |
| 2714 | 15 | `_is_hard_joined_candidate_crop` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 2730 | 17 | `_looks_like_panel_crop_path` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 2748 | 26 | `_has_split_crops_from_image` | image_navigation | 5 | test_compatibility | 0 | 1 | 0 |
| 2775 | 10 | `_needs_manual_panel_split` | image_navigation | 5 | test_compatibility | 0 | 8 | 0 |
| 2786 | 8 | `_is_manual_panel_split_done` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 2795 | 10 | `_set_panel_split_review` | image_navigation | 5 | test_compatibility | 0 | 6 | 0 |
| 2806 | 7 | `_clear_panel_split_review` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 2814 | 8 | `_builtin_image_group_definitions` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 2823 | 16 | `_custom_image_group_definitions` | image_navigation | 5 | test_compatibility | 0 | 1 | 0 |
| 2840 | 2 | `_all_image_group_definitions` | image_navigation | 5 | public_or_source_compatibility | 1 | 0 | 0 |
| 2843 | 19 | `_training_scope_group_definitions` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 2863 | 24 | `_populate_training_scope_combo` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 2888 | 5 | `_refresh_training_scope_combo` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 2894 | 16 | `_selected_training_scope_payload` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 2911 | 13 | `_populate_vlm_image_group_combo` | vlm_prediction_export | 7 | public_or_source_compatibility | 3 | 0 | 0 |
| 2925 | 5 | `_refresh_vlm_image_group_combo` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 2931 | 6 | `_image_group_display_name` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 2938 | 2 | `_custom_image_group_ids` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 2941 | 9 | `_image_group_move_target_definitions` | image_navigation | 5 | test_compatibility | 0 | 2 | 0 |
| 2951 | 45 | `_remove_empty_custom_image_groups` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 2997 | 13 | `_safe_custom_image_group_id` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 3011 | 34 | `create_custom_image_group` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 3046 | 10 | `_set_image_manual_group` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 3057 | 15 | `move_images_to_group` | image_navigation | 5 | public_or_source_compatibility | 1 | 7 | 1 |
| 3073 | 10 | `clear_selected_custom_image_group` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 3084 | 10 | `_short_progress_path` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 3095 | 13 | `_prepare_progress_dialog` | dialog_settings | 2 | public_or_source_compatibility | 2 | 0 | 0 |
| 3109 | 6 | `_candidate_panel_split_sources` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 3116 | 131 | `batch_split_panel_images` | image_navigation | 5 | public_or_source_compatibility | 1 | 2 | 1 |
| 3248 | 22 | `_save_detected_panel_crops` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 3271 | 10 | `_next_panel_crop_path` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 3282 | 32 | `_inherit_crop_provenance` | image_navigation | 5 | test_compatibility | 0 | 3 | 0 |
| 3315 | 9 | `_selected_image_paths` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 3325 | 8 | `_set_selected_panel_split_status` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 3334 | 2 | `mark_selected_manual_split_done` | unclassified | 8 | test_compatibility | 0 | 2 | 0 |
| 3337 | 2 | `mark_selected_manual_split_needed` | unclassified | 8 | test_compatibility | 0 | 1 | 0 |
| 3340 | 8 | `clear_selected_split_status` | unclassified | 8 | test_compatibility | 0 | 1 | 0 |
| 3349 | 23 | `show_file_list_context_menu` | shell_start_agent | 3 | public_or_source_compatibility | 1 | 1 | 1 |
| 3373 | 7 | `_move_selected_images_to_new_group` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 3381 | 60 | `remove_selected_images` | image_navigation | 5 | test_compatibility | 0 | 4 | 0 |
| 3442 | 95 | `refresh_file_list` | image_navigation | 5 | public_or_source_compatibility | 4 | 41 | 0 |
| 3538 | 4 | `_image_has_review_content` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 3543 | 19 | `_set_image_list_item_status` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 3563 | 41 | `_refresh_current_image_list_status` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 3605 | 6 | `_refresh_image_list_status_or_rebuild` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 3612 | 7 | `_image_list_path_identity` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 3620 | 10 | `_visible_image_list_paths` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 3631 | 27 | `_replacement_image_after_removal` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 3659 | 61 | `_remove_visible_image_list_items` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 3721 | 10 | `_filtered_group_definitions_after_removal` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 3732 | 14 | `_refresh_visible_image_group_header_counts` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 3747 | 31 | `_select_first_visible_image_after_removal` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 3779 | 26 | `_build_image_list_state` | image_navigation | 5 | test_compatibility | 0 | 1 | 0 |
| 3806 | 12 | `_handle_image_list_item_clicked` | image_navigation | 5 | public_or_source_compatibility | 1 | 2 | 1 |
| 3819 | 26 | `eventFilter` | unclassified | 8 | public_or_source_compatibility | 2 | 3 | 0 |
| 3846 | 35 | `_should_use_image_list_arrow_navigation` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 3882 | 21 | `_select_adjacent_image` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 3904 | 55 | `_collect_blink_roi_candidates` | blink | 6 | test_compatibility | 0 | 4 | 0 |
| 3960 | 39 | `on_file_selected` | unclassified | 8 | public_or_source_compatibility | 1 | 0 | 1 |
| 4000 | 11 | `on_part_selected` | unclassified | 8 | public_or_source_compatibility | 3 | 0 | 1 |
| 4012 | 90 | `launch_blink_from_workbench` | blink | 6 | public_or_source_compatibility | 2 | 4 | 1 |
| 4103 | 8 | `on_genus_changed` | image_navigation | 5 | public_or_source_compatibility | 1 | 0 | 1 |
| 4112 | 9 | `update_db_description` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 4122 | 5 | `_current_taxon_text` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 4128 | 8 | `_literature_source_taxon` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 4137 | 19 | `_set_current_image_taxon_from_literature` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 4157 | 21 | `_candidate_literature_db_paths` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 4179 | 55 | `_project_literature_db_paths` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 4235 | 39 | `_resolve_current_literature_context` | dialog_settings | 2 | test_compatibility | 0 | 3 | 0 |
| 4275 | 27 | `_resolve_literature_context_from_selected_db` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 4303 | 23 | `_choose_literature_db_for_current_taxon` | dialog_settings | 2 | test_compatibility | 0 | 1 | 0 |
| 4327 | 22 | `_literature_db_matches_image_source` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 4350 | 42 | `open_literature_description_dialog` | dialog_settings | 2 | public_or_source_compatibility | 1 | 0 | 1 |
| 4393 | 22 | `_open_literature_description_dialog_with_context` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 4416 | 24 | `_apply_literature_description` | dialog_settings | 2 | test_compatibility | 0 | 1 | 0 |
| 4441 | 15 | `_ensure_workbench_description_visible` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 4457 | 2 | `on_enhancement_changed` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 4460 | 16 | `on_tool_changed` | annotation_sam | 6 | public_or_source_compatibility | 8 | 8 | 6 |
| 4477 | 23 | `on_blink_parent_context_changed` | blink | 6 | public_or_source_compatibility | 1 | 2 | 1 |
| 4501 | 2 | `on_magic_wand_clicked` | annotation_sam | 6 | public_or_source_compatibility | 1 | 0 | 1 |
| 4504 | 2 | `on_magic_box_completed` | annotation_sam | 6 | public_or_source_compatibility | 1 | 1 | 1 |
| 4507 | 2 | `_sam_worker_ready` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 4510 | 2 | `_on_sam_model_loaded` | annotation_sam | 6 | signal_compatibility | 0 | 0 | 1 |
| 4513 | 18 | `_begin_sam_prompt` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 4532 | 6 | `_request_sam_point` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 4539 | 6 | `_request_sam_box` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 4546 | 34 | `on_annotation_box_completed` | annotation_sam | 6 | public_or_source_compatibility | 1 | 3 | 1 |
| 4581 | 2 | `_warn_blink_context` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 4584 | 12 | `_active_child_blink_context` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 4597 | 43 | `run_blink_child_auto_annotate` | blink | 6 | public_or_source_compatibility | 1 | 4 | 1 |
| 4641 | 9 | `_load_blink_refiner_class` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 4651 | 11 | `_active_blink_auto_shrink_steps` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 4663 | 14 | `_blink_parent_context_for_image` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 4678 | 41 | `_prepared_blink_auto_shrink_images` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 4720 | 38 | `_generate_blink_shrink_for_image` | blink | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 4759 | 42 | `run_blink_auto_shrink` | blink | 6 | public_or_source_compatibility | 1 | 3 | 1 |
| 4802 | 90 | `run_blink_batch_auto_shrink` | blink | 6 | public_or_source_compatibility | 1 | 1 | 1 |
| 4893 | 66 | `train_current_blink_expert` | blink | 6 | public_or_source_compatibility | 1 | 3 | 1 |
| 4960 | 10 | `stop_current_blink_expert_training` | blink | 6 | public_or_source_compatibility | 1 | 1 | 1 |
| 4971 | 18 | `open_current_route_expert_settings` | blink | 6 | public_or_source_compatibility | 1 | 0 | 1 |
| 4990 | 10 | `on_sam_mask_generated` | annotation_sam | 6 | signal_compatibility | 0 | 0 | 1 |
| 5001 | 7 | `on_sam_prompt_failed` | annotation_sam | 6 | signal_compatibility | 0 | 0 | 1 |
| 5009 | 23 | `on_polygon_completed` | annotation_sam | 6 | public_or_source_compatibility | 1 | 4 | 1 |
| 5033 | 7 | `toggle_morphometrics` | unclassified | 8 | public_or_source_compatibility | 1 | 0 | 1 |
| 5041 | 9 | `on_scale_defined` | annotation_sam | 6 | public_or_source_compatibility | 1 | 0 | 1 |
| 5051 | 16 | `update_measurements` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 5068 | 87 | `run_training` | training_model | 7 | public_or_source_compatibility | 2 | 2 | 1 |
| 5156 | 2 | `_external_backend_runner` | unclassified | 8 | internal_or_unreferenced | 0 | 0 | 0 |
| 5159 | 27 | `_sync_blink_lab_model_profile_defaults` | blink | 6 | public_or_source_compatibility | 1 | 0 | 0 |
| 5187 | 51 | `run_external_training` | training_model | 7 | test_compatibility | 0 | 1 | 0 |
| 5239 | 3 | `show_training_report` | dialog_settings | 2 | signal_compatibility | 0 | 0 | 1 |
| 5243 | 26 | `_candidate_training_experiment_dirs` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 5270 | 10 | `_resolve_report_artifact_path` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 5281 | 11 | `_training_report_time_label` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 5293 | 66 | `_training_report_payload_from_summary` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 5360 | 26 | `discover_training_reports` | dialog_settings | 2 | test_compatibility | 0 | 1 | 0 |
| 5387 | 8 | `open_training_report_payload` | dialog_settings | 2 | internal_or_unreferenced | 0 | 0 | 0 |
| 5396 | 17 | `open_training_results_browser` | project_lifecycle | 4 | public_or_source_compatibility | 1 | 0 | 1 |
| 5414 | 37 | `_extract_prediction_payload` | vlm_prediction_export | 7 | public_or_source_compatibility | 2 | 0 | 0 |
| 5452 | 12 | `_is_unconfirmed_ai_draft` | vlm_prediction_export | 7 | public_or_source_compatibility | 2 | 0 | 0 |
| 5465 | 13 | `_auto_box_meta_for_part` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 5479 | 3 | `_auto_box_source_for_part` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 5483 | 3 | `_auto_box_review_status_for_part` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 5487 | 5 | `_auto_annotation_source_meta` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 5493 | 15 | `_can_replace_existing_auto_annotation` | annotation_sam | 6 | internal_or_unreferenced | 0 | 0 | 0 |
| 5509 | 33 | `_apply_prediction_to_project` | vlm_prediction_export | 7 | test_compatibility | 0 | 3 | 0 |
| 5543 | 5 | `_vlm_api_settings_path` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 5549 | 40 | `_vlm_api_config_from_pdf_widget` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 5590 | 8 | `_vlm_preannotation_artifacts_dir` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 5599 | 4 | `_current_vlm_target_parts` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 5604 | 4 | `_current_vlm_processing_scope` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 5609 | 3 | `_current_vlm_batch_scope` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 5613 | 4 | `_current_vlm_image_group` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 5618 | 8 | `_current_vlm_concurrency` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 5627 | 5 | `_current_vlm_prompt_profile` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 5633 | 2 | `_vlm_image_group_label` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 5636 | 57 | `_panel_crop_identity_index` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 5694 | 57 | `_project_image_groups` | project_lifecycle | 4 | test_compatibility | 0 | 8 | 0 |
| 5752 | 10 | `_vlm_candidate_source_meta` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 5763 | 19 | `_record_sqlite_vlm_image_result` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 5783 | 13 | `_finish_sqlite_vlm_run` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 5797 | 7 | `_vlm_image_paths_for_scope` | vlm_prediction_export | 7 | test_compatibility | 0 | 3 | 0 |
| 5805 | 2 | `_vlm_image_paths_from_settings` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 5808 | 11 | `_same_project_image_path` | project_lifecycle | 4 | test_compatibility | 0 | 1 | 0 |
| 5820 | 5 | `_project_image_key_for_path` | project_lifecycle | 4 | internal_or_unreferenced | 0 | 0 | 0 |
| 5826 | 7 | `_vlm_part_list_text` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 5834 | 18 | `_vlm_part_coverage` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 5853 | 15 | `_log_vlm_part_coverage` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 5869 | 2 | `run_vlm_preannotation_current` | vlm_prediction_export | 7 | public_or_source_compatibility | 1 | 0 | 1 |
| 5872 | 2 | `run_vlm_preannotation_batch` | vlm_prediction_export | 7 | public_or_source_compatibility | 1 | 0 | 1 |
| 5875 | 121 | `run_vlm_preannotation_from_settings` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 5997 | 42 | `request_stop_vlm_preannotation` | vlm_prediction_export | 7 | public_or_source_compatibility | 1 | 1 | 0 |
| 6040 | 11 | `_active_vlm_preannotation_threads` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 6052 | 14 | `_start_vlm_preannotation_workers` | runtime_worker | 1 | test_compatibility | 0 | 1 | 0 |
| 6067 | 53 | `_start_next_vlm_preannotation_image` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 6121 | 48 | `_apply_vlm_candidate` | vlm_prediction_export | 7 | test_compatibility | 0 | 5 | 0 |
| 6170 | 6 | `_refresh_vlm_canvas_if_current` | vlm_prediction_export | 7 | test_compatibility | 0 | 3 | 0 |
| 6177 | 34 | `_reload_current_image_for_workbench` | image_navigation | 5 | internal_or_unreferenced | 0 | 0 | 0 |
| 6212 | 111 | `_on_vlm_preannotation_image_result` | vlm_prediction_export | 7 | signal_compatibility | 0 | 6 | 1 |
| 6324 | 7 | `_vlm_progress_image_key` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 6332 | 20 | `_mark_current_vlm_image_done` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 6353 | 30 | `_set_vlm_progress_ui` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 6384 | 54 | `_create_vlm_progress_dialog` | vlm_prediction_export | 7 | test_compatibility | 0 | 2 | 0 |
| 6439 | 18 | `_advance_vlm_progress` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 6458 | 11 | `_on_vlm_preannotation_thread_step` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 6470 | 7 | `_complete_current_vlm_image_steps` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 6478 | 100 | `_finish_vlm_preannotation_run` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 6579 | 36 | `accept_current_image_ai_drafts` | vlm_prediction_export | 7 | public_or_source_compatibility | 1 | 3 | 1 |
| 6616 | 93 | `accept_batch_ai_drafts` | vlm_prediction_export | 7 | public_or_source_compatibility | 1 | 1 | 1 |
| 6710 | 3 | `_on_vlm_preannotation_error` | vlm_prediction_export | 7 | signal_compatibility | 0 | 0 | 1 |
| 6714 | 33 | `_on_vlm_preannotation_qthread_finished` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 6748 | 2 | `_on_vlm_preannotation_finished` | vlm_prediction_export | 7 | test_compatibility | 0 | 1 | 0 |
| 6751 | 46 | `run_prediction` | vlm_prediction_export | 7 | public_or_source_compatibility | 2 | 2 | 1 |
| 6798 | 30 | `run_external_prediction` | vlm_prediction_export | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 6829 | 9 | `verify_current_image` | image_navigation | 5 | public_or_source_compatibility | 1 | 1 | 1 |
| 6839 | 100 | `_start_external_batch_inference` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 6940 | 74 | `run_batch_inference` | runtime_worker | 1 | public_or_source_compatibility | 1 | 1 | 1 |
| 7015 | 8 | `export_dataset` | runtime_worker | 1 | public_or_source_compatibility | 1 | 0 | 1 |
| 7024 | 75 | `_start_dataset_export` | runtime_worker | 1 | internal_or_unreferenced | 0 | 0 | 0 |
| 7100 | 23 | `init_sam` | annotation_sam | 6 | test_compatibility | 0 | 1 | 0 |
| 7124 | 13 | `ensure_sam_preloaded` | annotation_sam | 6 | test_compatibility | 0 | 6 | 0 |
| 7138 | 4 | `ensure_2d_stl_models_preloaded` | training_model | 7 | public_or_source_compatibility | 4 | 3 | 0 |
| 7143 | 17 | `ensure_locator_preloaded` | training_model | 7 | test_compatibility | 0 | 1 | 0 |
| 7161 | 22 | `_preload_engine_parts_model_async` | training_model | 7 | internal_or_unreferenced | 0 | 0 | 0 |
| 7184 | 2 | `log` | unclassified | 8 | public_or_source_compatibility | 209 | 34 | 5 |

## MainWindow State Fields

| Field | Assignments | Lines | Target owner | Stage |
| --- | --- | --- | --- | --- |
| `_image_list_state_cache` | 4 | 3608, 3571, 3435, 3453 | TBD | TBD |
| `_refreshing_part_tree` | 2 | 1665, 1724 | TBD | TBD |
| `_suppress_selection_save_flush` | 4 | 3768, 3755, 3775, 3762 | TBD | TBD |
| `_updating_blink_parent_context` | 2 | 2215, 2248 | TBD | TBD |
| `active_training_kind` | 2 | 5205, 839 | TBD | TBD |
| `active_training_label` | 1 | 841 | TBD | TBD |
| `blink_auto_shrink_steps` | 1 | 2351 | TBD | TBD |
| `blink_train_batch` | 1 | 2347 | TBD | TBD |
| `blink_train_epochs` | 1 | 2347 | TBD | TBD |
| `blink_train_input_size` | 1 | 2350 | TBD | TBD |
| `blink_train_lr` | 1 | 2348 | TBD | TBD |
| `blink_train_weight_decay` | 1 | 2349 | TBD | TBD |
| `blink_training_strategy` | 1 | 2352 | TBD | TBD |
| `child_training_cancel_requested` | 4 | 881, 892, 4923, 4965 | TBD | TBD |
| `child_training_failed` | 4 | 870, 877, 891, 4922 | TBD | TBD |
| `current_blink_context` | 1 | 1606 | TBD | TBD |
| `current_image` | 5 | 6183, 3983, 4666, 4669, 3432 | TBD | TBD |
| `current_lang` | 1 | 2452 | TBD | TBD |
| `current_theme` | 1 | 2469 | TBD | TBD |
| `dataset_export_thread` | 2 | 7049, 7092 | TBD | TBD |
| `external_backend_config` | 1 | 2362 | TBD | TBD |
| `external_batch_inference_failed` | 2 | 6849, 6908 | TBD | TBD |
| `external_batch_inference_progress_dialog` | 2 | 6869, 6922 | TBD | TBD |
| `external_batch_inference_saved_any` | 2 | 6850, 6904 | TBD | TBD |
| `external_batch_inference_thread` | 2 | 6881, 6924 | TBD | TBD |
| `external_training_failed` | 2 | 5204, 5218 | TBD | TBD |
| `external_training_thread` | 2 | 5210, 5227 | TBD | TBD |
| `image_import_progress_dialog` | 2 | 2622, 2665 | TBD | TBD |
| `image_import_thread` | 2 | 2625, 2669 | TBD | TBD |
| `inf_adapt` | 1 | 2356 | TBD | TBD |
| `inf_conf` | 1 | 2356 | TBD | TBD |
| `inf_noise_floor` | 1 | 2357 | TBD | TBD |
| `inf_pad` | 1 | 2357 | TBD | TBD |
| `inf_poly_epsilon` | 1 | 2358 | TBD | TBD |
| `inf_thread` | 1 | 6976 | TBD | TBD |
| `last_confirmed_locator_timestamp` | 3 | 778, 1164, 1157 | TBD | TBD |
| `model_backend` | 1 | 2361 | TBD | TBD |
| `parent_box_aspect_ratios` | 2 | 1547, 2377 | TBD | TBD |
| `parent_training_cancel_requested` | 2 | 942, 1056 | TBD | TBD |
| `parent_training_failed` | 3 | 941, 1017, 1034 | TBD | TBD |
| `parts_model_preload_thread` | 1 | 7176 | TBD | TBD |
| `pending_sam_description` | 3 | 4529, 4997, 5005 | TBD | TBD |
| `pending_sam_image` | 3 | 4528, 4996, 5004 | TBD | TBD |
| `pending_sam_part` | 3 | 4527, 4995, 5003 | TBD | TBD |
| `pending_training_preflight` | 1 | 929 | TBD | TBD |
| `project_autosave_delay_ms` | 1 | 2269 | TBD | TBD |
| `runtime_device` | 2 | 2274, 2360 | TBD | TBD |
| `sam_busy` | 3 | 4526, 4994, 5002 | TBD | TBD |
| `sam_thread` | 1 | 7107 | TBD | TBD |
| `sam_worker` | 1 | 7109 | TBD | TBD |
| `train_batch` | 1 | 2346 | TBD | TBD |
| `train_epochs` | 1 | 2346 | TBD | TBD |
| `train_lr` | 1 | 2355 | TBD | TBD |
| `train_wd` | 1 | 2355 | TBD | TBD |
| `trainer` | 2 | 947, 1008 | TBD | TBD |
| `training_retry_requested` | 3 | 940, 1016, 1025 | TBD | TBD |
| `vlm_preannotation_active_images` | 3 | 5975, 6575, 6102 | TBD | TBD |
| `vlm_preannotation_api_config` | 2 | 5956, 5980 | TBD | TBD |
| `vlm_preannotation_artifacts_dir` | 1 | 5979 | TBD | TBD |
| `vlm_preannotation_cancel_requested` | 3 | 5967, 6017, 6571 | TBD | TBD |
| `vlm_preannotation_cancelled_queued_images` | 3 | 5968, 6018, 6572 | TBD | TBD |
| `vlm_preannotation_completed_image_keys` | 3 | 5977, 6341, 6577 | TBD | TBD |
| `vlm_preannotation_completed_images` | 2 | 5973, 6343 | TBD | TBD |
| `vlm_preannotation_completed_steps` | 2 | 5971, 6442 | TBD | TBD |
| `vlm_preannotation_concurrency` | 1 | 5969 | TBD | TBD |
| `vlm_preannotation_current_image` | 4 | 5974, 6076, 6348, 6444 | TBD | TBD |
| `vlm_preannotation_current_image_steps_completed` | 3 | 6075, 6451, 6454 | TBD | TBD |
| `vlm_preannotation_image_step_counts` | 4 | 5976, 6576, 6106, 6449 | TBD | TBD |
| `vlm_preannotation_progress_bar` | 2 | 6435, 6569 | TBD | TBD |
| `vlm_preannotation_progress_dialog` | 2 | 6430, 6564 | TBD | TBD |
| `vlm_preannotation_progress_label` | 2 | 6433, 6567 | TBD | TBD |
| `vlm_preannotation_progress_notice_label` | 2 | 6432, 6566 | TBD | TBD |
| `vlm_preannotation_progress_path_label` | 2 | 6434, 6568 | TBD | TBD |
| `vlm_preannotation_progress_title_label` | 2 | 6431, 6565 | TBD | TBD |
| `vlm_preannotation_prompt_profile` | 1 | 5981 | TBD | TBD |
| `vlm_preannotation_queue` | 4 | 5964, 6019, 6074, 6738 | TBD | TBD |
| `vlm_preannotation_records` | 1 | 5963 | TBD | TBD |
| `vlm_preannotation_run_active` | 2 | 5966, 6538 | TBD | TBD |
| `vlm_preannotation_run_id` | 1 | 5962 | TBD | TBD |
| `vlm_preannotation_saved_total` | 2 | 5961, 6272 | TBD | TBD |
| `vlm_preannotation_stop_button` | 2 | 6436, 6570 | TBD | TBD |
| `vlm_preannotation_target_parts` | 1 | 5978 | TBD | TBD |
| `vlm_preannotation_thread` | 4 | 6049, 6065, 6098, 6574 | TBD | TBD |
| `vlm_preannotation_threads` | 5 | 5965, 6048, 6064, 6573, 6723 | TBD | TBD |
| `vlm_preannotation_total_images` | 1 | 5972 | TBD | TBD |
| `vlm_preannotation_total_steps` | 1 | 5970 | TBD | TBD |

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
| tests/test_gui_smoke.py | 243 | `patch.object(main_module.MainWindow, "_default_outputs_root", lambda _window: str(self.project_dir / "TaxaMask_outputs")), \` | - | TBD |
| tests/test_gui_smoke.py | 249 | `patch.object(main_module.QTimer, "singleShot", lambda *args, **kwargs: None):` | - | TBD |
| tests/test_gui_smoke.py | 250 | `window = main_module.MainWindow()` | - | TBD |
| tests/test_gui_smoke.py | 251 | `window._default_outputs_root = lambda: str(self.project_dir / "TaxaMask_outputs")` | `_default_outputs_root` | TBD |
| tests/test_gui_smoke.py | 252 | `window._pdf_widget_factory = build_pdf_widget` | `_pdf_widget_factory` | TBD |
| tests/test_gui_smoke.py | 350 | `self.assertIsNotNone(window.findChild(main_module.QWidget, "start2DWorkflowCard"))` | - | TBD |
| tests/test_gui_smoke.py | 351 | `self.assertIsNone(window.findChild(main_module.QWidget, "start" + "T" + "if" + "WorkflowCard"))` | - | TBD |
| tests/test_gui_smoke.py | 352 | `self.assertIsNotNone(window.findChild(main_module.QWidget, "startProjectConsole"))` | - | TBD |
| tests/test_gui_smoke.py | 357 | `rail_scroll = window.findChild(main_module.QScrollArea, "startWorkflowRailScroll")` | - | TBD |
| tests/test_gui_smoke.py | 362 | `self.assertEqual(rail_scroll.horizontalScrollBarPolicy(), main_module.Qt.ScrollBarAlwaysOff)` | - | TBD |
| tests/test_gui_smoke.py | 363 | `self.assertEqual(rail_scroll.verticalScrollBarPolicy(), main_module.Qt.ScrollBarAsNeeded)` | - | TBD |
| tests/test_gui_smoke.py | 364 | `self.assertIsNotNone(window.findChild(main_module.QWidget, "taxamaskAgentPanel"))` | - | TBD |
| tests/test_gui_smoke.py | 375 | `self.assertIsNone(window.agent_panel.findChild(main_module.QWidget, "taxamaskAgentInlineStatus"))` | - | TBD |
| tests/test_gui_smoke.py | 376 | `self.assertIsNone(window.agent_panel.findChild(main_module.QWidget, "taxamaskStartAntCodeButton"))` | - | TBD |
| tests/test_gui_smoke.py | 430 | `self.assertIsNotNone(window.findChild(main_module.QWidget, "workbenchCanvasShell"))` | - | TBD |
| tests/test_gui_smoke.py | 431 | `self.assertIsNotNone(window.findChild(main_module.QWidget, "workbenchLiteratureDescriptionButton"))` | - | TBD |
| tests/test_gui_smoke.py | 437 | `window._show_start_center()` | `_show_start_center` | TBD |
| tests/test_gui_smoke.py | 443 | `self.assertIsNone(window.findChild(main_module.QWidget, "start" + "T" + "if" + "WorkflowCard"))` | - | TBD |
| tests/test_gui_smoke.py | 463 | `window._update_start_center_texts()` | `_update_start_center_texts` | TBD |
| tests/test_gui_smoke.py | 478 | `self.assertTrue(main_module.MainWindow.ensure_2d_stl_models_preloaded(window))` | - | TBD |
| tests/test_gui_smoke.py | 479 | `self.assertFalse(main_module.MainWindow.ensure_2d_stl_models_preloaded(window))` | - | TBD |
| tests/test_gui_smoke.py | 489 | `window._show_start_center()` | `_show_start_center` | TBD |
| tests/test_gui_smoke.py | 520 | `self.assertIsNotNone(window.agent_panel.findChild(main_module.QWidget, "taxamaskAgentStack"))` | - | TBD |
| tests/test_gui_smoke.py | 529 | `panel = main_module.TaxaMaskAgentPanel(` | - | TBD |
| tests/test_gui_smoke.py | 547 | `panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=str(PROJECT_ROOT))` | - | TBD |
| tests/test_gui_smoke.py | 551 | `self.assertIsNotNone(panel.findChild(main_module.QWidget, "taxamaskAgentStack"))` | - | TBD |
| tests/test_gui_smoke.py | 559 | `panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=str(PROJECT_ROOT))` | - | TBD |
| tests/test_gui_smoke.py | 578 | `class FakeWebView(main_module.QWidget):` | - | TBD |
| tests/test_gui_smoke.py | 630 | `panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=str(PROJECT_ROOT))` | - | TBD |
| tests/test_gui_smoke.py | 651 | `panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=r"D:\lab data\TaxaMask")` | - | TBD |
| tests/test_gui_smoke.py | 667 | `panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=str(PROJECT_ROOT))` | - | TBD |
| tests/test_gui_smoke.py | 676 | `panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=str(PROJECT_ROOT))` | - | TBD |
| tests/test_gui_smoke.py | 691 | `panel = main_module.TaxaMaskAgentPanel("en", workspace_dir=str(PROJECT_ROOT))` | - | TBD |
| tests/test_gui_smoke.py | 918 | `with patch.object(main_module.QTimer, "singleShot", lambda _ms, callback: callback()):` | - | TBD |
| tests/test_gui_smoke.py | 939 | `fake_web_view = main_module.QWidget()` | - | TBD |
| tests/test_gui_smoke.py | 961 | `fake_web_view = main_module.QWidget()` | - | TBD |
| tests/test_gui_smoke.py | 1088 | `window.open_agent_from_context(window._collect_image_workbench_agent_context())` | `_collect_image_workbench_agent_context` | TBD |
| tests/test_gui_smoke.py | 1148 | `dialog = main_module.ModelSettingsDialog(` | - | TBD |
| tests/test_gui_smoke.py | 1168 | `self.assertIsNotNone(dialog.findChild(main_module.QPushButton, "modelSettingsAskAgentButton"))` | - | TBD |
| tests/test_gui_smoke.py | 1170 | `runtime_group = dialog.findChild(main_module.QWidget, "modelSettingsRuntimeDevicePanel")` | - | TBD |
| tests/test_gui_smoke.py | 1172 | `device_combo = runtime_group.findChild(main_module.QComboBox)` | - | TBD |
| tests/test_gui_smoke.py | 1186 | `dialog = main_module.ModelSettingsDialog(` | - | TBD |
| tests/test_gui_smoke.py | 1219 | `vlm_panel = dialog.findChild(main_module.QWidget, "modelSettingsVlmPreannotationPanel")` | - | TBD |
| tests/test_gui_smoke.py | 1225 | `scope_combo = dialog.findChild(main_module.QComboBox, "modelSettingsVlmBatchScopeCombo")` | - | TBD |
| tests/test_gui_smoke.py | 1229 | `group_combo = dialog.findChild(main_module.QComboBox, "modelSettingsVlmImageGroupCombo")` | - | TBD |
| tests/test_gui_smoke.py | 1232 | `profile_combo = dialog.findChild(main_module.QComboBox, "modelSettingsVlmPromptProfileCombo")` | - | TBD |
| tests/test_gui_smoke.py | 1243 | `dialog = main_module.ModelSettingsDialog(` | - | TBD |
| tests/test_gui_smoke.py | 1269 | `combo = dialog.findChild(main_module.QComboBox, "modelSettingsVlmImageGroupCombo")` | - | TBD |
| tests/test_gui_smoke.py | 1279 | `dialog = main_module.ModelSettingsDialog(` | - | TBD |
| tests/test_gui_smoke.py | 1332 | `dialog = main_module.GeneralSettingsDialog(` | - | TBD |
| tests/test_gui_smoke.py | 1349 | `self.assertIsNotNone(dialog.findChild(main_module.QPushButton, "generalSettingsAskAgentButton"))` | - | TBD |
| tests/test_gui_smoke.py | 1354 | `self.assertIsNone(dialog.findChild(main_module.QWidget, "modelSettingsLocatorScopePanel"))` | - | TBD |
| tests/test_gui_smoke.py | 1361 | `model_dialog = main_module.ModelSettingsDialog(` | - | TBD |
| tests/test_gui_smoke.py | 1373 | `"model_backend": main_module.EXTERNAL_BACKEND_ID,` | - | TBD |
| tests/test_gui_smoke.py | 1391 | `model_dialog.child_backend_combo.findData(main_module.CHILD_BACKEND_EXTERNAL)` | - | TBD |
| tests/test_gui_smoke.py | 1409 | `"expert_backend": main_module.ROUTE_BACKEND_HEATMAP_BLINK,` | - | TBD |
| tests/test_gui_smoke.py | 1420 | `self.assertEqual(context["parent_model_source"], main_module.PARENT_BACKEND_EXTERNAL)` | - | TBD |
| tests/test_gui_smoke.py | 1421 | `self.assertEqual(context["default_child_expert"], main_module.CHILD_BACKEND_EXTERNAL)` | - | TBD |
| tests/test_gui_smoke.py | 1422 | `self.assertEqual(context["default_child_route_backend"], main_module.ROUTE_BACKEND_EXTERNAL_BLINK)` | - | TBD |
| tests/test_gui_smoke.py | 1435 | `compact = window._compact_agent_context(context)` | `_compact_agent_context` | TBD |
| tests/test_gui_smoke.py | 1439 | `self.assertEqual(compact["default_child_expert"], main_module.CHILD_BACKEND_EXTERNAL)` | - | TBD |
| tests/test_gui_smoke.py | 1459 | `tif_compact = window._compact_agent_context(` | `_compact_agent_context` | TBD |
| tests/test_gui_smoke.py | 1547 | `pdf_compact = window._compact_agent_context(` | `_compact_agent_context` | TBD |
| tests/test_gui_smoke.py | 1597 | `with patch.object(project_lifecycle_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1621 | `with patch.object(project_lifecycle_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1641 | `with patch.object(project_lifecycle_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1670 | `with patch.object(main_module.QMessageBox, "information", return_value=main_module.QMessageBox.Ok):` | - | TBD |
| tests/test_gui_smoke.py | 1677 | `with patch.object(main_module.QFileDialog, "getSaveFileName", return_value=(str(export_path), "JSON (*.json)")), \` | - | TBD |
| tests/test_gui_smoke.py | 1678 | `patch.object(main_module.QMessageBox, "information", return_value=main_module.QMessageBox.Ok):` | - | TBD |
| tests/test_gui_smoke.py | 1695 | `with patch.object(project_lifecycle_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1722 | `with patch.object(project_lifecycle_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1745 | `with patch.object(project_lifecycle_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1789 | `with patch.object(project_lifecycle_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1798 | `self.assertEqual(header.data(main_module.Qt.UserRole + 1), "original")` | - | TBD |
| tests/test_gui_smoke.py | 1825 | `with patch.object(project_lifecycle_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1848 | `with patch.object(project_lifecycle_module, "themed_yes_no_question", return_value=main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 1872 | `with patch.object(main_module.QFileDialog, "getExistingDirectory", fake_get_existing_directory), \` | - | TBD |
| tests/test_gui_smoke.py | 1873 | `patch.object(main_module.QInputDialog, "getText", return_value=("review", True)), \` | - | TBD |
| tests/test_gui_smoke.py | 1890 | `ant_project_dir = Path(main_module.PACKAGE_DIR)` | - | TBD |
| tests/test_gui_smoke.py | 1892 | `self.assertEqual(Path(window._default_open_project_dir()), self.project_dir / "TaxaMask_outputs")` | `_default_open_project_dir` | TBD |
| tests/test_gui_smoke.py | 1896 | `self.assertEqual(Path(window._default_2d_export_dir()), project_dir / "exports")` | `_default_2d_export_dir` | TBD |
| tests/test_gui_smoke.py | 1897 | `self.assertEqual(Path(window._vlm_preannotation_artifacts_dir()), project_dir / "vlm_preannotation")` | `_vlm_preannotation_artifacts_dir` | TBD |
| tests/test_gui_smoke.py | 1899 | `dialog = main_module.ExportDialog(window, "en", default_dir=window._default_2d_export_dir())` | `_default_2d_export_dir` | TBD |
| tests/test_gui_smoke.py | 1917 | `window._create_vlm_progress_dialog()` | `_create_vlm_progress_dialog` | TBD |
| tests/test_gui_smoke.py | 1919 | `window._advance_vlm_progress("prepare")` | `_advance_vlm_progress` | TBD |
| tests/test_gui_smoke.py | 1923 | `self.assertEqual(progress.windowModality(), main_module.Qt.NonModal)` | - | TBD |
| tests/test_gui_smoke.py | 1937 | `window._mark_current_vlm_image_done("done")` | `_mark_current_vlm_image_done` | TBD |
| tests/test_gui_smoke.py | 1969 | `original_refresh = window._refresh_vlm_canvas_if_current` | `_refresh_vlm_canvas_if_current` | TBD |
| tests/test_gui_smoke.py | 1970 | `window._refresh_vlm_canvas_if_current = lambda path: (refresh_calls.append(path), original_refresh(path))` | `_refresh_vlm_canvas_if_current` | TBD |
| tests/test_gui_smoke.py | 1973 | `window._on_vlm_preannotation_image_result(` | `_on_vlm_preannotation_image_result` | TBD |
| tests/test_gui_smoke.py | 2028 | `window._on_vlm_preannotation_image_result(` | `_on_vlm_preannotation_image_result` | TBD |
| tests/test_gui_smoke.py | 2072 | `window._on_vlm_preannotation_image_result(` | `_on_vlm_preannotation_image_result` | TBD |
| tests/test_gui_smoke.py | 2112 | `window._create_vlm_progress_dialog()` | `_create_vlm_progress_dialog` | TBD |
| tests/test_gui_smoke.py | 2120 | `window._on_vlm_preannotation_image_result(` | `_on_vlm_preannotation_image_result` | TBD |
| tests/test_gui_smoke.py | 2171 | `window._set_panel_split_review(str(manual_image), "manual_required", reason="hard_seam_panel_split")` | `_set_panel_split_review` | TBD |
| tests/test_gui_smoke.py | 2182 | `batch_paths = window._vlm_image_paths_for_scope(window._current_vlm_batch_scope())` | `_current_vlm_batch_scope`, `_vlm_image_paths_for_scope` | TBD |
| tests/test_gui_smoke.py | 2185 | `current_paths = window._vlm_image_paths_for_scope("current_image")` | `_vlm_image_paths_for_scope` | TBD |
| tests/test_gui_smoke.py | 2190 | `groups = window._project_image_groups()` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 2228 | `window._on_vlm_preannotation_image_result(` | `_on_vlm_preannotation_image_result` | TBD |
| tests/test_gui_smoke.py | 2271 | `window._refresh_vlm_canvas_if_current(image_key)` | `_refresh_vlm_canvas_if_current` | TBD |
| tests/test_gui_smoke.py | 2298 | `ok, mode = window._apply_vlm_candidate(` | `_apply_vlm_candidate` | TBD |
| tests/test_gui_smoke.py | 2354 | `ok, mode = window._apply_vlm_candidate(` | `_apply_vlm_candidate` | TBD |
| tests/test_gui_smoke.py | 2388 | `window._same_project_image_path(` | `_same_project_image_path` | TBD |
| tests/test_gui_smoke.py | 2389 | `window.file_list.currentItem().data(main_module.Qt.UserRole),` | - | TBD |
| tests/test_gui_smoke.py | 2403 | `for index in range(main_module.BACKGROUND_IMAGE_IMPORT_THRESHOLD):` | - | TBD |
| tests/test_gui_smoke.py | 2436 | `started = window._start_image_import(image_paths)` | `_start_image_import` | TBD |
| tests/test_gui_smoke.py | 2462 | `window.model_backend = main_module.EXTERNAL_BACKEND_ID` | - | TBD |
| tests/test_gui_smoke.py | 2514 | `with patch.object(main_module, "_runtime_parent_backend", lambda *_args, **_kwargs: main_module.EXTERNAL_BACKEND_ID), \` | - | TBD |
| tests/test_gui_smoke.py | 2515 | `patch.object(main_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes), \` | - | TBD |
| tests/test_gui_smoke.py | 2549 | `path = item.data(main_module.Qt.UserRole)` | - | TBD |
| tests/test_gui_smoke.py | 2562 | `with patch.object(main_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 2711 | `prompt = window._pdf_agent_prompt()` | `_pdf_agent_prompt` | TBD |
| tests/test_gui_smoke.py | 2864 | `window._inherit_crop_provenance(` | `_inherit_crop_provenance` | TBD |
| tests/test_gui_smoke.py | 2881 | `self.assertTrue(window._is_pdf_candidate_provenance(crop_provenance))` | `_is_pdf_candidate_provenance` | TBD |
| tests/test_gui_smoke.py | 2898 | `window._inherit_crop_provenance(` | `_inherit_crop_provenance` | TBD |
| tests/test_gui_smoke.py | 2915 | `self.assertTrue(window._is_split_crop_image(str(crop_image)))` | `_is_split_crop_image` | TBD |
| tests/test_gui_smoke.py | 2927 | `window._set_panel_split_review(str(parent_image), "manual_required", reason="hard_seam_panel_split")` | `_set_panel_split_review` | TBD |
| tests/test_gui_smoke.py | 2929 | `window._inherit_crop_provenance(` | `_inherit_crop_provenance` | TBD |
| tests/test_gui_smoke.py | 2946 | `self.assertFalse(window._needs_manual_panel_split(str(parent_image)))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 2947 | `self.assertFalse(window._needs_manual_panel_split(str(crop_image)))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 2972 | `window._set_panel_split_review(str(parent_image), "manual_required", reason="hard_seam_panel_split")` | `_set_panel_split_review` | TBD |
| tests/test_gui_smoke.py | 2974 | `self.assertTrue(window._has_split_crops_from_image(str(parent_image)))` | `_has_split_crops_from_image` | TBD |
| tests/test_gui_smoke.py | 2975 | `self.assertFalse(window._needs_manual_panel_split(str(parent_image)))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 2976 | `self.assertFalse(window._needs_manual_panel_split(str(crop_image)))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 3000 | `self.assertTrue(window._needs_manual_panel_split(str(image_path)))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 3006 | `self.assertFalse(window._needs_manual_panel_split(str(image_path)))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 3029 | `window._set_panel_split_review(str(image_a), "manual_required", reason="hard_seam_panel_split")` | `_set_panel_split_review` | TBD |
| tests/test_gui_smoke.py | 3030 | `window._set_panel_split_review(str(image_b), "manual_required", reason="hard_seam_panel_split")` | `_set_panel_split_review` | TBD |
| tests/test_gui_smoke.py | 3040 | `groups = window._project_image_groups()` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 3058 | `window._set_panel_split_review(str(image_path), "manual_done", reason="user_marked_done")` | `_set_panel_split_review` | TBD |
| tests/test_gui_smoke.py | 3060 | `self.assertEqual([Path(path).name for path in window._project_image_groups()["manual_done"]], [image_path.name])` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 3063 | `groups = window._project_image_groups()` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 3087 | `groups = window._project_image_groups()` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 3090 | `self.assertEqual(window._vlm_image_group_label("review_ready"), "Review Ready")` | `_vlm_image_group_label` | TBD |
| tests/test_gui_smoke.py | 3100 | `self.assertEqual(window._current_vlm_image_group(), "review_ready")` | `_current_vlm_image_group` | TBD |
| tests/test_gui_smoke.py | 3101 | `paths = window._vlm_image_paths_for_scope("image_group")` | `_vlm_image_paths_for_scope` | TBD |
| tests/test_gui_smoke.py | 3129 | `groups = window._project_image_groups()` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 3156 | `self.assertIn("review_ready", {group_id for group_id, _label in window._image_group_move_target_definitions()})` | `_image_group_move_target_definitions` | TBD |
| tests/test_gui_smoke.py | 3160 | `self.assertEqual(window._custom_image_group_definitions(), [])` | `_custom_image_group_definitions` | TBD |
| tests/test_gui_smoke.py | 3162 | `self.assertNotIn("review_ready", {group_id for group_id, _label in window._image_group_move_target_definitions()})` | `_image_group_move_target_definitions` | TBD |
| tests/test_gui_smoke.py | 3185 | `if item.data(main_module.Qt.UserRole) and _same_path(item.data(main_module.Qt.UserRole), image_a):` | - | TBD |
| tests/test_gui_smoke.py | 3239 | `self.assertTrue(window._is_split_crop_image(str(crop_image)))` | `_is_split_crop_image` | TBD |
| tests/test_gui_smoke.py | 3240 | `self.assertFalse(window._is_split_crop_image(str(unrelated_crop)))` | `_is_split_crop_image` | TBD |
| tests/test_gui_smoke.py | 3285 | `with patch.object(main_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 3286 | `with patch.object(main_module.QMessageBox, "information", lambda *args, **kwargs: None):` | - | TBD |
| tests/test_gui_smoke.py | 3312 | `self.assertTrue(window._is_split_crop_image(generated))` | `_is_split_crop_image` | TBD |
| tests/test_gui_smoke.py | 3313 | `self.assertFalse(window._needs_manual_panel_split(generated))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 3318 | `self.assertTrue(window._is_split_crop_image(generated))` | `_is_split_crop_image` | TBD |
| tests/test_gui_smoke.py | 3319 | `self.assertFalse(window._needs_manual_panel_split(generated))` | `_needs_manual_panel_split` | TBD |
| tests/test_gui_smoke.py | 3324 | `groups = window._project_image_groups()` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 3370 | `with patch.object(main_module, "themed_yes_no_question", lambda *args, **kwargs: main_module.QMessageBox.Yes):` | - | TBD |
| tests/test_gui_smoke.py | 3371 | `with patch.object(main_module.QMessageBox, "information", lambda *args, **kwargs: None):` | - | TBD |
| tests/test_gui_smoke.py | 3379 | `groups = window._project_image_groups()` | `_project_image_groups` | TBD |
| tests/test_gui_smoke.py | 3442 | `window._ensure_pdf_widget()` | `_ensure_pdf_widget` | TBD |
| tests/test_gui_smoke.py | 3445 | `db_path, context, reason = window._resolve_current_literature_context()` | `_resolve_current_literature_context` | TBD |
| tests/test_gui_smoke.py | 3465 | `window._ensure_pdf_widget()` | `_ensure_pdf_widget` | TBD |
| tests/test_gui_smoke.py | 3481 | `db_path, context, reason = window._resolve_current_literature_context()` | `_resolve_current_literature_context` | TBD |
| tests/test_gui_smoke.py | 3503 | `window._ensure_pdf_widget()` | `_ensure_pdf_widget` | TBD |
| tests/test_gui_smoke.py | 3530 | `db_path, context, reason = window._resolve_current_literature_context()` | `_resolve_current_literature_context` | TBD |
| tests/test_gui_smoke.py | 3550 | `window._ensure_pdf_widget()` | `_ensure_pdf_widget` | TBD |
| tests/test_gui_smoke.py | 3566 | `with patch.object(main_module.QFileDialog, "getOpenFileName", return_value=(str(literature_db), "SQLite Database (*.db)")):` | - | TBD |
| tests/test_gui_smoke.py | 3567 | `db_path, context, reason = window._choose_literature_db_for_current_taxon()` | `_choose_literature_db_for_current_taxon` | TBD |
| tests/test_gui_smoke.py | 3612 | `dialog = main_module.LiteratureDescriptionDialog(` | - | TBD |
| tests/test_gui_smoke.py | 3644 | `dialog = main_module.LiteratureDescriptionDialog(` | - | TBD |
| tests/test_gui_smoke.py | 3746 | `self.assertTrue(window._is_stl_project_file(stl_path))` | `_is_stl_project_file` | TBD |
| tests/test_gui_smoke.py | 3747 | `with patch.object(main_module.QFileDialog, "getOpenFileName", return_value=(stl_path, "JSON (*.json)")):` | - | TBD |
| tests/test_gui_smoke.py | 3758 | `self.assertEqual(window._active_recent_project_path(), os.path.abspath(stl_path))` | `_active_recent_project_path` | TBD |
| tests/test_gui_smoke.py | 3760 | `context = window._collect_image_workbench_agent_context()` | `_collect_image_workbench_agent_context` | TBD |
| tests/test_gui_smoke.py | 3764 | `self.assertIn("STL rendered-view project", window._start_console_project_summary()[0])` | `_start_console_project_summary` | TBD |
| tests/test_gui_smoke.py | 3765 | `self.assertIn("1 STL rendered 2D view", window._start_console_image_summary()[0])` | `_start_console_image_summary` | TBD |
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
