# TIF Workbench Round 3 Test Migration Ledger

由 `scripts/analyze_tif_workbench_architecture.py` 生成。`target_layer` 是 Stage 0 初始建议，实施阶段必须结合测试真实断言复核。

> 状态说明：本表是候选迁移台账，不是完成清单。2026-07-10 当前工作树已提前推进到 Stage 6 半迁移状态；所有“已迁移”描述都必须在用户确认计划后，按 Stage 0-10 重新核对测试目标、私有 seam、验证 suite 和真实研究路径，才能标记为 `verified`。

| File | Line | Test | Workflow | Private refs | Initial target |
| --- | --- | --- | --- | --- | --- |
| tests/test_gui_smoke.py | 313 | `test_main_window_constructs_offscreen_without_loading_sam` | unclassified | - | gui_key_path |
| tests/test_gui_smoke.py | 395 | `test_main_window_reuses_existing_startup_sqlite_project` | selection_lifecycle | - | gui_key_path |
| tests/test_gui_smoke.py | 411 | `test_start_center_workflow_buttons_switch_visible_tabs` | shell_view_text | - | gui_key_path |
| tests/test_gui_smoke.py | 445 | `test_start_center_recent_project_uses_short_display_and_full_tooltip` | selection_lifecycle | - | gui_key_path |
| tests/test_gui_smoke.py | 463 | `test_enter_image_workflow_preloads_models_once_and_keeps_them_after_start_center` | backend_result_review | - | gui_key_path |
| tests/test_gui_smoke.py | 489 | `test_agent_panel_embeds_ant_code_dashboard_controls` | shell_view_text | - | gui_key_path |
| tests/test_gui_smoke.py | 519 | `test_agent_panel_uses_source_dashboard_not_distributed_exe` | shell_view_text | - | gui_key_path |
| tests/test_gui_smoke.py | 535 | `test_agent_panel_defers_embedded_webview_until_dashboard_load` | shell_view_text | - | gui_key_path |
| tests/test_gui_smoke.py | 547 | `test_agent_panel_creates_embedded_webview_on_load` | shell_view_text | - | gui_key_path |
| tests/test_gui_smoke.py | 599 | `test_qtwebengine_flags_disable_agent_gpu_logging_by_default` | volume_preview_render | - | gui_key_path |
| tests/test_gui_smoke.py | 611 | `test_agent_panel_can_launch_dashboard_through_wsl` | shell_view_text | - | gui_key_path |
| tests/test_gui_smoke.py | 638 | `test_agent_panel_windows_path_fallback_converts_to_wsl_mount` | shell_view_text | - | gui_key_path |
| tests/test_gui_smoke.py | 655 | `test_agent_panel_uses_browser_mode_on_linux` | shell_view_text | - | gui_key_path |
| tests/test_gui_smoke.py | 666 | `test_agent_panel_ready_opens_browser_in_browser_mode` | shell_view_text | - | gui_key_path |
| tests/test_gui_smoke.py | 681 | `test_agent_panel_browser_mode_copies_context_to_clipboard` | shell_view_text | - | gui_key_path |
| tests/test_gui_smoke.py | 709 | `test_agent_panel_preflights_before_loading_webview` | shell_view_text | - | gui_key_path |
| tests/test_gui_smoke.py | 727 | `test_agent_panel_post_load_script_reconciles_embedded_trust` | shell_view_text | - | gui_key_path |
| tests/test_gui_smoke.py | 740 | `test_agent_panel_embed_style_defers_to_dashboard_composer` | shell_view_text | - | gui_key_path |
| tests/test_gui_smoke.py | 758 | `test_agent_panel_embed_style_switches_to_light_theme` | shell_view_text | - | gui_key_path |
| tests/test_gui_smoke.py | 793 | `test_agent_panel_keeps_pending_prompt_until_insert_confirmed` | shell_view_text | - | gui_key_path |
| tests/test_gui_smoke.py | 822 | `test_agent_panel_ignores_stale_prompt_insert_callback` | shell_view_text | - | gui_key_path |
| tests/test_gui_smoke.py | 846 | `test_agent_panel_keeps_context_after_startup_json_warning` | shell_view_text | - | gui_key_path |
| tests/test_gui_smoke.py | 883 | `test_agent_panel_allows_extra_embed_ready_retries_for_pending_context` | shell_view_text | - | gui_key_path |
| tests/test_gui_smoke.py | 919 | `test_agent_panel_returns_to_fallback_when_embed_never_becomes_ready` | shell_view_text | - | gui_key_path |
| tests/test_gui_smoke.py | 947 | `test_agent_panel_returns_to_fallback_when_web_load_fails` | shell_view_text | - | gui_key_path |
| tests/test_gui_smoke.py | 966 | `test_agent_panel_stop_dashboard_terminates_process_tree` | shell_view_text | - | gui_key_path |
| tests/test_gui_smoke.py | 995 | `test_agent_panel_owned_dashboard_matching_is_project_scoped` | selection_lifecycle | - | gui_key_path |
| tests/test_gui_smoke.py | 1020 | `test_agent_panel_blocks_invalid_active_project_json` | selection_lifecycle | - | gui_key_path |
| tests/test_gui_smoke.py | 1036 | `test_agent_panel_warns_but_does_not_block_unselected_workspace_json` | task_lifecycle | - | gui_key_path |
| tests/test_gui_smoke.py | 1056 | `test_start_center_entry_is_navigation_only` | unclassified | - | gui_key_path |
| tests/test_gui_smoke.py | 1072 | `test_ask_agent_carries_compact_context_only` | shell_view_text | - | gui_key_path |
| tests/test_gui_smoke.py | 1093 | `test_ask_agent_auto_starts_ant_code_and_queues_context` | shell_view_text | - | gui_key_path |
| tests/test_gui_smoke.py | 1110 | `test_ask_agent_reuses_running_ant_code` | unclassified | - | gui_key_path |
| tests/test_gui_smoke.py | 1129 | `test_language_switch_and_model_settings_are_lightweight` | backend_result_review | - | gui_key_path |
| tests/test_gui_smoke.py | 1176 | `test_vlm_preannotation_settings_live_in_inference_tab` | annotation_save_truth | - | gui_key_path |
| tests/test_gui_smoke.py | 1233 | `test_model_settings_vlm_group_combo_accepts_custom_groups` | backend_result_review | - | gui_key_path |
| tests/test_gui_smoke.py | 1269 | `test_model_settings_vlm_custom_prompt_profile_round_trips` | backend_result_review | - | gui_key_path |
| tests/test_gui_smoke.py | 1310 | `test_vlm_workbench_buttons_use_action_specific_labels` | annotation_save_truth | - | gui_key_path |
| tests/test_gui_smoke.py | 1322 | `test_general_settings_are_not_2d_stl_model_settings` | backend_result_review | - | gui_key_path |
| tests/test_gui_smoke.py | 1349 | `test_settings_ask_agent_context_is_compact_and_command_safe` | shell_view_text | - | gui_key_path |
| tests/test_gui_smoke.py | 1447 | `test_agent_context_compaction_keeps_pdf_and_tif_route_fields` | shell_view_text | - | gui_key_path |
| tests/test_gui_smoke.py | 1553 | `test_project_create_and_open_lightweight_path` | selection_lifecycle | - | gui_key_path |
| tests/test_gui_smoke.py | 1575 | `test_open_legacy_2d_json_migrates_to_sqlite_manifest` | import_export | - | gui_key_path |
| tests/test_gui_smoke.py | 1601 | `test_open_already_migrated_legacy_json_uses_existing_manifest` | import_export | - | gui_key_path |
| tests/test_gui_smoke.py | 1621 | `test_open_2d_sqlite_database_redirects_to_project_entry_manifest` | selection_lifecycle | - | gui_key_path |
| tests/test_gui_smoke.py | 1641 | `test_sqlite_project_maintenance_menu_actions_create_backup_and_legacy_export` | selection_lifecycle | - | gui_key_path |
| tests/test_gui_smoke.py | 1674 | `test_open_legacy_tif_json_migrates_to_sqlite_manifest` | import_export | - | gui_key_path |
| tests/test_gui_smoke.py | 1701 | `test_open_already_migrated_legacy_tif_json_uses_existing_manifest` | import_export | - | gui_key_path |
| tests/test_gui_smoke.py | 1724 | `test_open_tif_sqlite_database_redirects_to_project_entry_manifest` | selection_lifecycle | - | gui_key_path |
| tests/test_gui_smoke.py | 1747 | `test_continue_last_large_project_opens_with_collapsed_image_groups` | selection_lifecycle | - | gui_key_path |
| tests/test_gui_smoke.py | 1793 | `test_open_small_project_after_large_project_restores_expanded_image_list` | selection_lifecycle | - | gui_key_path |
| tests/test_gui_smoke.py | 1844 | `test_new_project_dialogs_default_to_output_roots` | selection_lifecycle | - | gui_key_path |
| tests/test_gui_smoke.py | 1873 | `test_open_and_export_defaults_stay_out_of_program_package` | import_export | - | gui_key_path |
| tests/test_gui_smoke.py | 1893 | `test_vlm_preannotation_progress_ui_tracks_steps` | annotation_save_truth | - | gui_key_path |
| tests/test_gui_smoke.py | 1933 | `test_vlm_result_refreshes_current_canvas_with_project_relative_path` | selection_lifecycle | - | gui_key_path |
| tests/test_gui_smoke.py | 1989 | `test_vlm_result_logs_requested_returned_and_missing_parts` | backend_result_review | - | gui_key_path |
| tests/test_gui_smoke.py | 2039 | `test_vlm_no_candidate_result_logs_all_requested_parts_missing` | backend_result_review | - | gui_key_path |
| tests/test_gui_smoke.py | 2076 | `test_vlm_result_repaints_canvas_while_progress_dialog_is_open` | backend_result_review | - | gui_key_path |
| tests/test_gui_smoke.py | 2140 | `test_vlm_preannotation_scope_can_target_split_crop_group` | annotation_save_truth | - | gui_key_path |
| tests/test_gui_smoke.py | 2183 | `test_vlm_result_updates_workbench_without_file_list_rebuild` | backend_result_review | - | gui_key_path |
| tests/test_gui_smoke.py | 2236 | `test_vlm_auto_box_is_painted_after_refresh` | unclassified | - | gui_key_path |
| tests/test_gui_smoke.py | 2272 | `test_vlm_candidate_writes_box_and_polygon_without_progress_dialog_reentry` | task_lifecycle | - | gui_key_path |
| tests/test_gui_smoke.py | 2303 | `test_vlm_grid_box_is_mapped_before_sam_prompt` | unclassified | - | gui_key_path |
| tests/test_gui_smoke.py | 2359 | `test_refresh_file_list_restores_selection_with_project_relative_path` | selection_lifecycle | - | gui_key_path |
| tests/test_gui_smoke.py | 2382 | `test_bulk_image_import_uses_background_progress_thread` | task_lifecycle | - | gui_key_path |
| tests/test_gui_smoke.py | 2435 | `test_external_batch_inference_uses_background_thread_and_single_save` | annotation_save_truth | - | gui_key_path |
| tests/test_gui_smoke.py | 2518 | `test_remove_selected_images_uses_batch_project_remove` | selection_lifecycle | - | gui_key_path |
| tests/test_gui_smoke.py | 2560 | `test_external_training_uses_background_thread` | backend_result_review | - | gui_key_path |
| tests/test_gui_smoke.py | 2610 | `test_pdf_evidence_tools_open_on_demand` | unclassified | - | gui_key_path |
| tests/test_gui_smoke.py | 2708 | `test_pdf_database_viewer_paginates_figure_records` | shell_view_text | - | gui_key_path |
| tests/test_gui_smoke.py | 2832 | `test_pdf_candidate_crop_inherits_parent_provenance` | unclassified | - | gui_key_path |
| tests/test_gui_smoke.py | 2875 | `test_plain_image_crop_gets_traceable_provenance_for_grouping` | unclassified | - | gui_key_path |
| tests/test_gui_smoke.py | 2905 | `test_crop_from_manual_required_parent_leaves_manual_queue` | unclassified | - | gui_key_path |
| tests/test_gui_smoke.py | 2942 | `test_existing_crop_from_manual_required_parent_is_not_manual_queue` | unclassified | - | gui_key_path |
| tests/test_gui_smoke.py | 2972 | `test_user_can_adjust_panel_split_status_from_image_list` | shell_view_text | - | gui_key_path |
| tests/test_gui_smoke.py | 3007 | `test_multi_selected_manual_split_done_moves_to_done_group` | unclassified | - | gui_key_path |
| tests/test_gui_smoke.py | 3038 | `test_manual_done_images_can_be_moved_into_split_group` | unclassified | - | gui_key_path |
| tests/test_gui_smoke.py | 3059 | `test_custom_image_group_can_collect_images_and_feed_vlm_scope` | unclassified | - | gui_key_path |
| tests/test_gui_smoke.py | 3093 | `test_labeled_images_sort_to_top_within_custom_image_group` | annotation_save_truth | - | gui_key_path |
| tests/test_gui_smoke.py | 3124 | `test_empty_custom_image_group_is_removed_from_move_targets` | unclassified | - | gui_key_path |
| tests/test_gui_smoke.py | 3153 | `test_file_list_context_menu_shows_new_group_at_top_level_only` | shell_view_text | - | gui_key_path |
| tests/test_gui_smoke.py | 3214 | `test_legacy_panel_crop_filename_is_grouped_as_split_crop` | shell_view_text | - | gui_key_path |
| tests/test_gui_smoke.py | 3236 | `test_batch_panel_split_adds_white_and_hard_seam_candidate_crops` | shell_view_text | - | gui_key_path |
| tests/test_gui_smoke.py | 3329 | `test_batch_panel_split_does_not_force_equal_grid_from_labels` | annotation_save_truth | - | gui_key_path |
| tests/test_gui_smoke.py | 3370 | `test_literature_context_prefers_image_artifact_db_over_current_pdf_widget_db` | shell_view_text | - | gui_key_path |
| tests/test_gui_smoke.py | 3440 | `test_manual_image_can_reference_same_taxon_literature_db` | unclassified | - | gui_key_path |
| tests/test_gui_smoke.py | 3476 | `test_manual_image_finds_literature_db_from_other_project_pdf_image` | selection_lifecycle | - | gui_key_path |
| tests/test_gui_smoke.py | 3522 | `test_manual_image_can_choose_literature_db_when_auto_paths_are_missing` | unclassified | - | gui_key_path |
| tests/test_gui_smoke.py | 3560 | `test_literature_dialog_exposes_structured_and_raw_text_layers` | shell_view_text | - | gui_key_path |
| tests/test_gui_smoke.py | 3617 | `test_literature_dialog_chinese_action_buttons_are_explicit` | shell_view_text | - | gui_key_path |
| tests/test_gui_smoke.py | 3641 | `test_pdf_multimodal_same_as_text_shows_effective_text_settings` | shell_view_text | `_current_multimodal_api_settings` | workflow_controller |
| tests/test_gui_smoke.py | 3676 | `test_multimodal_connection_test_uses_nontrivial_generated_png` | unclassified | - | gui_key_path |
| tests/test_gui_smoke.py | 3690 | `test_connection_test_accepts_reasoning_content_when_chat_content_is_empty` | unclassified | - | gui_key_path |
| tests/test_gui_smoke.py | 3713 | `test_stl_project_open_path_registers_views_into_labeling_workbench` | selection_lifecycle | - | gui_key_path |
| tests/test_tif_workbench.py | 274 | `test_tif_workbench_theme_switch_updates_panels_and_canvas_background` | shell_view_text | - | gui_key_path |
| tests/test_tif_workbench.py | 300 | `test_cpu_volume_canvas_recomposes_cached_pixmap_when_theme_changes` | volume_preview_render | - | gui_key_path |
| tests/test_tif_workbench.py | 357 | `test_tif_workbench_loads_specimen_and_renders_overlay` | selection_lifecycle | - | gui_key_path |
| tests/test_tif_workbench.py | 401 | `test_specimen_tree_loads_full_and_part_volumes` | selection_lifecycle | `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 444 | `test_specimen_tree_groups_part_reslices_under_part` | selection_lifecycle | - | gui_key_path |
| tests/test_tif_workbench.py | 510 | `test_select_volume_tree_item_targets_specific_reslice` | selection_lifecycle | `_local_axis_volume_overlays`, `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 574 | `test_select_volume_tree_item_does_not_fallback_to_wrong_reslice` | selection_lifecycle | `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 604 | `test_select_volume_tree_item_reports_missing_reslice_group` | selection_lifecycle | `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 619 | `test_local_axis_reslice_button_is_enabled_for_part_volume` | volume_preview_render | `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 656 | `test_local_axis_review_queue_updates_status_and_batch_exports` | local_axis_reslice | - | gui_key_path |
| tests/test_tif_workbench.py | 700 | `test_local_axis_review_queue_filters_sorts_and_emits_open_proposal` | local_axis_reslice | - | gui_key_path |
| tests/test_tif_workbench.py | 752 | `test_local_axis_model_panel_exports_imports_and_registers_models` | local_axis_reslice | - | gui_key_path |
| tests/test_tif_workbench.py | 818 | `test_local_axis_model_panel_generates_baseline_proposals` | local_axis_reslice | - | gui_key_path |
| tests/test_tif_workbench.py | 834 | `test_local_axis_model_panel_saves_dedicated_backend_config` | annotation_save_truth | - | gui_key_path |
| tests/test_tif_workbench.py | 868 | `test_part_bbox_input_draws_roi_overlay_on_current_slice` | roi_to_part | - | gui_key_path |
| tests/test_tif_workbench.py | 888 | `test_dragging_roi_updates_bbox_for_current_axis` | roi_to_part | - | gui_key_path |
| tests/test_tif_workbench.py | 909 | `test_dragging_loaded_roi_draft_updates_original_draft` | roi_to_part | - | gui_key_path |
| tests/test_tif_workbench.py | 940 | `test_roi_draft_saves_without_writing_part_until_confirmed` | annotation_save_truth | - | gui_key_path |
| tests/test_tif_workbench.py | 971 | `test_confirm_saved_roi_uses_latest_bbox_text` | annotation_save_truth | - | gui_key_path |
| tests/test_tif_workbench.py | 996 | `test_saved_roi_draft_autosaves_later_dragged_boxes` | annotation_save_truth | - | gui_key_path |
| tests/test_tif_workbench.py | 1026 | `test_confirm_roi_initializes_part_mask_from_key_slice_rect_shell` | roi_to_part | - | gui_key_path |
| tests/test_tif_workbench.py | 1063 | `test_confirm_roi_initializes_part_mask_from_full_volume_freehand_contours` | annotation_save_truth | - | gui_key_path |
| tests/test_tif_workbench.py | 1111 | `test_full_volume_mask_preview_enables_accept_and_creates_part_mask` | part_mask_material | - | gui_key_path |
| tests/test_tif_workbench.py | 1154 | `test_large_part_mask_preview_starts_background_task` | part_mask_material | `_part_mask_preview_thread`, `_set_scope_controls_enabled` | workflow_controller |
| tests/test_tif_workbench.py | 1195 | `test_large_confirm_roi_starts_background_task` | roi_to_part | `_confirm_part_roi_thread`, `_set_scope_controls_enabled` | workflow_controller |
| tests/test_tif_workbench.py | 1226 | `test_confirm_roi_background_request_reuses_accepted_preview_mask` | roi_to_part | `_confirm_part_roi_thread`, `_set_scope_controls_enabled` | workflow_controller |
| tests/test_tif_workbench.py | 1275 | `test_confirm_roi_worker_creates_part_and_writes_accepted_mask` | roi_to_part | `_build_confirm_part_roi_request`, `_full_volume_contours_payload` | workflow_controller |
| tests/test_tif_workbench.py | 1329 | `test_roi_draft_saves_and_restores_full_volume_freehand_contours` | annotation_save_truth | `_load_roi_draft_for_editing` | workflow_controller |
| tests/test_tif_workbench.py | 1361 | `test_part_mask_preview_ignores_roi_shell_after_adding_new_key_slice` | roi_to_part | - | gui_key_path |
| tests/test_tif_workbench.py | 1400 | `test_part_mask_preview_filters_legacy_roi_shell_keyframes` | roi_to_part | `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 1441 | `test_clear_part_mask_keyframes_resets_legacy_roi_shell_and_mask` | roi_to_part | `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 1498 | `test_create_part_button_is_not_in_locate_part_workflow` | shell_view_text | - | gui_key_path |
| tests/test_tif_workbench.py | 1508 | `test_rectangular_keyframe_button_is_not_in_part_mask_workflow` | part_mask_material | - | gui_key_path |
| tests/test_tif_workbench.py | 1517 | `test_double_click_created_part_roi_opens_part_volume` | roi_to_part | `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 1545 | `test_delete_current_part_volume_removes_part_storage_and_returns_to_parent` | volume_preview_render | `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 1580 | `test_first_roi_drag_does_not_use_default_bbox` | roi_to_part | - | gui_key_path |
| tests/test_tif_workbench.py | 1601 | `test_roi_drag_accumulates_boxes_in_one_slice_direction` | roi_to_part | - | gui_key_path |
| tests/test_tif_workbench.py | 1633 | `test_roi_drag_replaces_key_slice_rect_instead_of_expanding_it` | roi_to_part | - | gui_key_path |
| tests/test_tif_workbench.py | 1661 | `test_delete_part_volume_from_tree_without_loading_part` | volume_preview_render | `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 1687 | `test_part_freehand_contour_saves_overlay_and_deletes_key_slice` | annotation_save_truth | `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 1722 | `test_contour_draw_mode_uses_subpixel_points_and_hides_brush_radius_preview` | annotation_save_truth | `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 1756 | `test_part_key_slice_navigation_jumps_between_saved_contours` | annotation_save_truth | `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 1784 | `test_dirty_contours_do_not_break_slice_overlay` | annotation_save_truth | `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 1807 | `test_part_mask_preview_reports_quality_and_3d_mask_modes_render` | part_mask_material | `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 1846 | `test_part_volume_3d_defaults_to_masked_image_after_mask_is_accepted` | volume_preview_render | `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 1880 | `test_part_volume_3d_left_drag_uses_full_volume_pitch_direction` | volume_preview_render | `_select_volume_tree_item`, `_volume_pitch` | workflow_controller |
| tests/test_tif_workbench.py | 1912 | `test_result_comparison_exports_current_rendering_screenshot` | volume_preview_render | `_current_result_region_slug`, `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 1950 | `test_result_comparison_lists_region_counts_and_opens_selected_part_3d` | roi_to_part | `_active_result_region_mask_volume`, `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 2076 | `test_result_comparison_can_open_part_even_when_selected_source_is_missing` | backend_result_review | - | gui_key_path |
| tests/test_tif_workbench.py | 2108 | `test_part_switch_defers_result_comparison_counts_until_tab_visible` | backend_result_review | `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 2155 | `test_reslice_switch_does_not_fallback_to_full_tif_read_when_memmap_fails` | volume_preview_render | `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 2200 | `test_copy_source_z_axis_creates_visible_local_axis_draft` | local_axis_reslice | `_local_axis_volume_overlays`, `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 2225 | `test_local_axis_output_endpoint_drag_updates_draft_in_3d_view` | local_axis_reslice | `_local_axis_volume_overlays`, `_select_volume_tree_item`, `_volume_yaw` | workflow_controller |
| tests/test_tif_workbench.py | 2262 | `test_local_axis_output_body_drag_moves_whole_axis_in_3d_view` | local_axis_reslice | `_local_axis_volume_overlays`, `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 2304 | `test_local_axis_roll_reference_uses_clip_plane_and_updates_frame` | local_axis_reslice | `_local_axis_volume_overlays`, `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 2360 | `test_local_axis_roll_reference_pick_ignores_preview_busy_lock` | volume_preview_render | `_backend_write_lock_active`, `_finish_tif_task`, `_select_volume_tree_item`, `_start_tif_task` | workflow_controller |
| tests/test_tif_workbench.py | 2388 | `test_local_axis_controls_remain_available_during_preview_busy_lock` | volume_preview_render | `_backend_write_lock_active`, `_finish_tif_task`, `_select_volume_tree_item`, `_set_scope_controls_enabled`, `_start_tif_task` | workflow_controller |
| tests/test_tif_workbench.py | 2415 | `test_local_axis_pick_target_auto_creates_draft_during_preview_busy_lock` | volume_preview_render | `_finish_tif_task`, `_local_axis_pick_target`, `_select_volume_tree_item`, `_start_tif_task` | workflow_controller |
| tests/test_tif_workbench.py | 2442 | `test_busy_lock_matrix_allows_preview_only_local_axis_draft_interaction` | volume_preview_render | `_backend_write_lock_active`, `_finish_tif_task`, `_guard_backend_write_lock`, `_guard_local_axis_draft_interaction`, `_local_axis_draft_lock_ignored_task_types`, `_select_volume_tree_item`, `_start_tif_task` | workflow_controller |
| tests/test_tif_workbench.py | 2483 | `test_local_axis_three_point_plane_aligns_output_z_and_exports_reference` | local_axis_reslice | `_current_local_axis_reslice_payload`, `_local_axis_volume_overlays`, `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 2539 | `test_local_axis_clip_plane_depth_advances_from_viewer_side` | local_axis_reslice | `_clip_plane_rotated_depth`, `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 2564 | `test_local_axis_sidebar_export_records_training_sample` | local_axis_reslice | `_current_local_axis_draft`, `_local_axis_reslice_export_running`, `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 2647 | `test_local_axis_volume_section_follows_part_3d_context` | volume_preview_render | `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 2688 | `test_local_axis_draft_is_scoped_to_current_part` | local_axis_reslice | `_local_axis_volume_overlays`, `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 2708 | `test_selected_saved_reslice_is_read_only_and_draws_saved_axis_overlay` | annotation_save_truth | `_current_local_axis_draft`, `_current_local_axis_reslice_payload`, `_is_editable_part_volume`, `_local_axis_volume_overlays`, `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 2777 | `test_copy_source_z_axis_uses_current_part_id_as_template` | unclassified | `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 2794 | `test_task_tabs_follow_tif_workflow_context` | task_lifecycle | `_select_volume_tree_item`, `_sync_mode_sections` | workflow_controller |
| tests/test_tif_workbench.py | 2843 | `test_part_mask_buttons_refresh_when_returning_to_slice_z_view` | part_mask_material | `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 2871 | `test_rectangular_keyframe_clears_stale_preview_mask` | volume_preview_render | `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 2888 | `test_part_volume_color_can_override_parent_render_color` | volume_preview_render | `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 2911 | `test_part_volume_color_override_survives_project_reload` | selection_lifecycle | `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 2930 | `test_part_extraction_flow_reopens_with_mask_contours_and_extraction` | annotation_save_truth | `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 2974 | `test_part_package_export_status_does_not_expand_sidebar_with_full_path` | shell_view_text | `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 2995 | `test_right_sidebar_visible_pages_do_not_overflow_control_panel` | shell_view_text | `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 3048 | `test_brush_edit_saves_working_edit_without_touching_manual_truth` | annotation_save_truth | `_dirty_edit_slices` | workflow_controller |
| tests/test_tif_workbench.py | 3100 | `test_working_edit_is_created_lazily_when_painting` | annotation_save_truth | - | gui_key_path |
| tests/test_tif_workbench.py | 3143 | `test_material_map_can_be_edited_and_refuses_used_delete` | annotation_save_truth | `_material_id_is_used`, `_save_material_map` | workflow_controller |
| tests/test_tif_workbench.py | 3196 | `test_training_handoff_controls_are_visible` | backend_result_review | - | gui_key_path |
| tests/test_tif_workbench.py | 3348 | `test_volume_canvas_is_created_lazily_and_released_before_agent` | volume_preview_render | `_volume_canvas_created`, `_volume_canvas_renderer` | workflow_controller |
| tests/test_tif_workbench.py | 3395 | `test_3d_mask_mode_falls_back_from_gpu_canvas_to_cpu_pixmap_canvas` | volume_preview_render | `_select_volume_tree_item`, `_volume_canvas_created`, `_volume_canvas_renderer` | workflow_controller |
| tests/test_tif_workbench.py | 3435 | `test_masked_image_mode_uses_gpu_canvas_when_available` | volume_preview_render | `_ensure_volume_preview`, `_select_volume_tree_item`, `_volume_canvas_created`, `_volume_canvas_renderer`, `_volume_transfer_preset` | workflow_controller |
| tests/test_tif_workbench.py | 3503 | `test_mask_boundary_mode_uses_gpu_canvas_when_mask_texture_is_available` | volume_preview_render | `_select_volume_tree_item`, `_volume_canvas_created`, `_volume_canvas_renderer` | workflow_controller |
| tests/test_tif_workbench.py | 3555 | `test_image_only_mode_restores_gpu_after_temporary_mask_cpu_fallback` | volume_preview_render | `_select_volume_tree_item`, `_volume_canvas_created`, `_volume_canvas_renderer` | workflow_controller |
| tests/test_tif_workbench.py | 3591 | `test_ask_agent_context_includes_tif_view_and_annotation_training_focus` | annotation_save_truth | `_volume_canvas_renderer` | workflow_controller |
| tests/test_tif_workbench.py | 3645 | `test_composite_drag_preview_uses_lighter_interaction_budget` | volume_preview_render | `_active_volume_sample_count`, `_active_volume_target_dim`, `_volume_canvas_renderer`, `_volume_render_mode`, `_volume_render_state` | workflow_controller |
| tests/test_tif_workbench.py | 3673 | `test_roi_high_detail_scale_raises_still_gpu_sample_steps` | roi_to_part | `_active_volume_sample_count`, `_volume_canvas_renderer`, `_volume_render_mode`, `_volume_render_state`, `_volume_zoom` | workflow_controller |
| tests/test_tif_workbench.py | 3693 | `test_volume_depth_sliders_use_interaction_preview_while_dragging` | volume_preview_render | `_request_volume_interaction_render`, `_volume_render_mode` | workflow_controller |
| tests/test_tif_workbench.py | 3721 | `test_volume_quality_slider_rebuilds_only_after_release` | volume_preview_render | `_on_volume_quality_changed`, `_refresh_volume_preview`, `_volume_quality_committed_value` | workflow_controller |
| tests/test_tif_workbench.py | 3767 | `test_volume_roi_scale_slider_updates_only_after_release` | roi_to_part | `_on_volume_roi_scale_changed` | workflow_controller |
| tests/test_tif_workbench.py | 3799 | `test_volume_transfer_opacity_saves_only_after_drag_release` | annotation_save_truth | `_save_active_volume_view_settings` | workflow_controller |
| tests/test_tif_workbench.py | 3832 | `test_right_panel_controls_ignore_mouse_wheel_changes` | shell_view_text | - | gui_key_path |
| tests/test_tif_workbench.py | 3868 | `test_canvas_wheel_and_arrow_keys_page_slices` | volume_preview_render | - | gui_key_path |
| tests/test_tif_workbench.py | 3896 | `test_slice_slider_arrow_keys_follow_review_shortcuts` | volume_preview_render | - | gui_key_path |
| tests/test_tif_workbench.py | 3929 | `test_control_slider_arrow_keys_follow_review_shortcuts` | shell_view_text | - | gui_key_path |
| tests/test_tif_workbench.py | 3953 | `test_canvas_zoom_pan_and_slice_change_preserve_view` | volume_preview_render | - | gui_key_path |
| tests/test_tif_workbench.py | 3985 | `test_tif_workbench_can_view_z_y_x_orthogonal_slices` | volume_preview_render | - | gui_key_path |
| tests/test_tif_workbench.py | 4018 | `test_side_angle_slices_are_read_only_for_label_safety` | annotation_save_truth | - | gui_key_path |
| tests/test_tif_workbench.py | 4038 | `test_display_mode_switcher_stays_left_of_its_label` | annotation_save_truth | - | gui_key_path |
| tests/test_tif_workbench.py | 4050 | `test_tif_workbench_can_render_drag_rotate_volume_preview` | volume_preview_render | `_clamp_volume_pan`, `_finish_volume_interaction`, `_update_volume_render_status_label`, `_volume_canvas_renderer`, `_volume_gl_renderer_info`, `_volume_pan_limit`, `_volume_pan_x`, `_volume_pan_y`, `_volume_pitch`, `_volume_preview`, `_volume_render_mode`, `_volume_yaw`, `_volume_zoom` | workflow_controller |
| tests/test_tif_workbench.py | 4186 | `test_volume_preview_cache_keeps_drag_and_still_textures_separate` | volume_preview_render | `_ensure_volume_preview`, `_volume_canvas_renderer`, `_volume_preview_algorithm`, `_volume_preview_cache` | workflow_controller |
| tests/test_tif_workbench.py | 4208 | `test_volume_preview_cache_keeps_three_recent_specimen_owners` | selection_lifecycle | `_ensure_volume_preview`, `_volume_canvas_renderer`, `_volume_preview_cache` | workflow_controller |
| tests/test_tif_workbench.py | 4245 | `test_high_quality_volume_preview_cache_reduces_owner_limit` | volume_preview_render | `_ensure_volume_preview`, `_volume_canvas_renderer`, `_volume_preview_cache` | workflow_controller |
| tests/test_tif_workbench.py | 4268 | `test_volume_quality_change_keeps_gpu_texture_cache_before_budgeted_rebuild` | volume_preview_render | `_commit_volume_quality_change`, `_refresh_volume_preview`, `_volume_canvas_created`, `_volume_canvas_renderer`, `_volume_quality_committed_value` | workflow_controller |
| tests/test_tif_workbench.py | 4311 | `test_switching_specimen_resets_active_preview_without_flushing_lru_cache` | selection_lifecycle | `_ensure_volume_preview`, `_reset_active_volume_preview_state`, `_volume_canvas_renderer`, `_volume_preview`, `_volume_preview_cache` | workflow_controller |
| tests/test_tif_workbench.py | 4330 | `test_switching_specimen_cancels_pending_preview_without_locking_tree` | selection_lifecycle | `_cancel_volume_preview_build`, `_set_volume_preview_build_controls_busy`, `_volume_preview_build_worker`, `_volume_preview_pending_key`, `_volume_preview_pending_mask_key`, `_volume_preview_pending_token` | workflow_controller |
| tests/test_tif_workbench.py | 4352 | `test_deferred_specimen_switch_render_keeps_gpu_stream_path` | selection_lifecycle | `_defer_volume_preview_render_once` | workflow_controller |
| tests/test_tif_workbench.py | 4374 | `test_user_tree_switch_shows_volume_pending_status_before_loading` | volume_preview_render | `_defer_volume_preview_render_once`, `_loading_specimen`, `_on_specimen_tree_selected` | workflow_controller |
| tests/test_tif_workbench.py | 4399 | `test_volume_preview_wait_state_blocks_clicks_but_allows_wheel_events` | volume_preview_render | `_begin_volume_preview_ui_wait`, `_end_volume_preview_ui_wait` | workflow_controller |
| tests/test_tif_workbench.py | 4413 | `test_metadata_only_specimen_shows_deferred_volume_message` | selection_lifecycle | - | gui_key_path |
| tests/test_tif_workbench.py | 4446 | `test_metadata_only_slice_review_starts_working_volume_build` | volume_preview_render | - | gui_key_path |
| tests/test_tif_workbench.py | 4475 | `test_switching_metadata_only_specimen_to_volume_starts_materialize_flow` | selection_lifecycle | - | gui_key_path |
| tests/test_tif_workbench.py | 4500 | `test_still_volume_preview_uses_detail_preserving_downsample` | volume_preview_render | `_ensure_volume_preview`, `_volume_canvas_renderer` | workflow_controller |
| tests/test_tif_workbench.py | 4519 | `test_volume_source_geometry_stays_fixed_across_preview_sizes` | volume_preview_render | `_ensure_volume_preview`, `_volume_canvas_renderer`, `_volume_source_geometry` | workflow_controller |
| tests/test_tif_workbench.py | 4554 | `test_full_volume_roi_high_detail_uploads_original_bbox_crop` | roi_to_part | `_ensure_volume_preview`, `_roi_texture_budget_bytes`, `_volume_canvas_created`, `_volume_canvas_renderer`, `_volume_render_mode`, `_volume_roi_preview_bbox`, `_volume_zoom` | workflow_controller |
| tests/test_tif_workbench.py | 4628 | `test_roi_crop_request_uses_roi_status_text_at_default_zoom` | roi_to_part | `_volume_canvas_renderer`, `_volume_preview_request`, `_volume_render_mode`, `_volume_zoom` | workflow_controller |
| tests/test_tif_workbench.py | 4651 | `test_full_volume_bbox_does_not_crop_without_roi_inspect` | roi_to_part | `_ensure_volume_preview`, `_volume_canvas_renderer`, `_volume_render_mode`, `_volume_roi_preview_bbox`, `_volume_zoom` | workflow_controller |
| tests/test_tif_workbench.py | 4682 | `test_full_volume_bbox_does_not_crop_until_bbox_source_selected` | volume_preview_render | `_ensure_volume_preview`, `_volume_canvas_renderer`, `_volume_render_mode`, `_volume_roi_preview_bbox`, `_volume_zoom` | workflow_controller |
| tests/test_tif_workbench.py | 4711 | `test_volume_roi_source_can_use_saved_roi_draft` | annotation_save_truth | `_ensure_volume_preview`, `_populate_volume_roi_source_combo`, `_volume_canvas_renderer`, `_volume_render_mode`, `_volume_roi_preview_bbox`, `_volume_zoom` | workflow_controller |
| tests/test_tif_workbench.py | 4757 | `test_volume_roi_source_can_use_part_parent_bbox` | roi_to_part | `_ensure_volume_preview`, `_populate_volume_roi_source_combo`, `_volume_canvas_renderer`, `_volume_render_mode`, `_volume_roi_preview_bbox`, `_volume_zoom` | workflow_controller |
| tests/test_tif_workbench.py | 4810 | `test_roi_high_detail_budget_preset_controls_texture_budget_and_cache_key` | roi_to_part | `_ensure_volume_preview`, `_roi_texture_budget_bytes`, `_volume_canvas_renderer`, `_volume_preview_source_shape`, `_volume_render_mode`, `_volume_zoom` | workflow_controller |
| tests/test_tif_workbench.py | 4843 | `test_cpu_volume_front_clip_discards_viewer_side_depths` | volume_preview_render | `_viewer_side_front_clip_mask` | workflow_controller |
| tests/test_tif_workbench.py | 4856 | `test_volume_preview_keeps_uint8_source_without_float_copy` | volume_preview_render | `_normalize_volume_preview_to_uint8` | workflow_controller |
| tests/test_tif_workbench.py | 4869 | `test_volume_preview_normalizes_uint16_source_for_gpu_upload` | volume_preview_render | `_normalize_volume_preview_to_uint8` | workflow_controller |
| tests/test_tif_workbench.py | 4882 | `test_clarity_mode_preserves_uint16_preview_for_gpu_upload` | volume_preview_render | `_ensure_volume_preview`, `_volume_canvas_renderer` | workflow_controller |
| tests/test_tif_workbench.py | 4896 | `test_clarity_toggle_keeps_previous_preview_variants_cached` | volume_preview_render | `_ensure_volume_preview`, `_on_volume_clarity_toggled`, `_volume_canvas_renderer`, `_volume_clarity_mode`, `_volume_preview_cache`, `_volume_preview_request`, `_volume_render_mode` | workflow_controller |
| tests/test_tif_workbench.py | 4927 | `test_volume_preview_cache_limits_variants_per_owner` | volume_preview_render | `_prune_volume_preview_cache`, `_volume_cache_owner_from_key`, `_volume_preview_cache` | workflow_controller |
| tests/test_tif_workbench.py | 4952 | `test_default_mask_mode_change_keeps_volume_preview_cache` | volume_preview_render | `_active_volume_cache_owner`, `_apply_default_volume_mask_mode`, `_volume_mask_preview_cache`, `_volume_preview_cache` | workflow_controller |
| tests/test_tif_workbench.py | 4977 | `test_volume_performance_report_exposes_gpu_texture_cache` | volume_preview_render | `_volume_canvas_renderer`, `_volume_last_stats` | workflow_controller |
| tests/test_tif_workbench.py | 5005 | `test_part_volume_still_preview_preserves_uint16_detail_by_default` | volume_preview_render | `_ensure_volume_preview`, `_volume_canvas_renderer` | workflow_controller |
| tests/test_tif_workbench.py | 5019 | `test_local_detail_check_keeps_roi_high_detail_supersample` | roi_to_part | `_active_volume_roi_scale`, `_volume_canvas_renderer`, `_volume_render_mode`, `_volume_zoom` | workflow_controller |
| tests/test_tif_workbench.py | 5040 | `test_part_local_detail_check_raises_still_texture_target` | shell_view_text | `_active_volume_target_dim`, `_volume_canvas_renderer` | workflow_controller |
| tests/test_tif_workbench.py | 5059 | `test_transfer_function_change_keeps_volume_texture_cache` | volume_preview_render | `_volume_canvas_created`, `_volume_canvas_renderer`, `_volume_preview_cache` | workflow_controller |
| tests/test_tif_workbench.py | 5100 | `test_morphology_transfer_function_is_available_without_reuploading_texture` | volume_preview_render | `_volume_canvas_created`, `_volume_canvas_renderer` | workflow_controller |
| tests/test_tif_workbench.py | 5144 | `test_shader_quality_mode_controls_experimental_rendering` | volume_preview_render | `_volume_canvas_created`, `_volume_canvas_renderer` | workflow_controller |
| tests/test_tif_workbench.py | 5207 | `test_apply_morphology_inspect_preset_updates_display_without_reuploading_texture` | shell_view_text | `_volume_canvas_created`, `_volume_canvas_renderer` | workflow_controller |
| tests/test_tif_workbench.py | 5257 | `test_volume_drag_updates_gpu_camera_without_reuploading_texture` | volume_preview_render | `_finish_volume_interaction`, `_render_volume_interaction_preview`, `_volume_canvas_created`, `_volume_canvas_renderer`, `_volume_render_mode` | workflow_controller |
| tests/test_tif_workbench.py | 5318 | `test_transfer_opacity_change_keeps_volume_texture_cache` | volume_preview_render | `_volume_canvas_created`, `_volume_canvas_renderer`, `_volume_preview_cache` | workflow_controller |
| tests/test_tif_workbench.py | 5361 | `test_large_gpu_upload_uses_non_modal_status` | volume_preview_render | `_sync_gpu_volume_canvas`, `_volume_canvas_created`, `_volume_canvas_renderer`, `_volume_render_mode` | workflow_controller |
| tests/test_tif_workbench.py | 5407 | `test_large_gpu_upload_keeps_previous_frame_without_forced_process_events` | volume_preview_render | `_sync_gpu_volume_canvas`, `_volume_canvas_created`, `_volume_canvas_renderer`, `_volume_render_mode` | workflow_controller |
| tests/test_tif_workbench.py | 5446 | `test_full_volume_still_preview_prefers_gpu_stream_build_before_cpu_preview` | volume_preview_render | `_active_volume_target_dim`, `_volume_canvas_created`, `_volume_canvas_renderer`, `_volume_last_stats`, `_volume_preview_request`, `_volume_render_mode` | workflow_controller |
| tests/test_tif_workbench.py | 5499 | `test_large_full_volume_prefers_gpu_stream_before_background_cpu_preview` | volume_preview_render | `_volume_canvas_created`, `_volume_canvas_renderer`, `_volume_last_stats`, `_volume_preview_request`, `_volume_render_mode` | workflow_controller |
| tests/test_tif_workbench.py | 5564 | `test_gpu_stream_rebuild_keeps_existing_frame_without_pending_flash` | volume_preview_render | `_volume_canvas_created`, `_volume_canvas_renderer`, `_volume_last_stats`, `_volume_render_mode` | workflow_controller |
| tests/test_tif_workbench.py | 5616 | `test_roi_crop_preview_prefers_gpu_stream_build_before_cpu_preview` | roi_to_part | `_volume_canvas_created`, `_volume_canvas_renderer`, `_volume_preview_request`, `_volume_render_mode`, `_volume_roi_preview_source_shape` | workflow_controller |
| tests/test_tif_workbench.py | 5674 | `test_part_local_detail_preview_prefers_gpu_stream_build_before_cpu_preview` | volume_preview_render | `_volume_canvas_created`, `_volume_canvas_renderer`, `_volume_mask_preview_request`, `_volume_render_mode` | workflow_controller |
| tests/test_tif_workbench.py | 5743 | `test_large_part_volume_preview_starts_background_before_gpu_stream_build` | volume_preview_render | `_volume_canvas_created`, `_volume_canvas_renderer`, `_volume_preview_build_thread`, `_volume_preview_request`, `_volume_render_mode` | workflow_controller |
| tests/test_tif_workbench.py | 5798 | `test_full_volume_part_mask_preview_uses_roi_background_for_3d` | roi_to_part | `_apply_default_volume_mask_mode`, `_volume_canvas_created`, `_volume_canvas_renderer`, `_volume_preview_build_thread`, `_volume_render_mode` | workflow_controller |
| tests/test_tif_workbench.py | 5878 | `test_small_part_volume_preview_can_use_gpu_stream_build` | volume_preview_render | `_volume_canvas_created`, `_volume_canvas_renderer`, `_volume_render_mode` | workflow_controller |
| tests/test_tif_workbench.py | 5930 | `test_gpu_mask_source_for_roi_request_uses_roi_crop` | roi_to_part | `_gpu_mask_source_for_request` | workflow_controller |
| tests/test_tif_workbench.py | 5949 | `test_gpu_stream_degradation_is_reported_without_extra_panel` | volume_preview_render | `_volume_canvas_renderer`, `_volume_last_stats`, `_volume_stats_text`, `_volume_status_summary_text` | workflow_controller |
| tests/test_tif_workbench.py | 5980 | `test_volume_quality_commit_keeps_gpu_texture_cache_for_budgeted_reuse` | volume_preview_render | `_commit_volume_quality_change`, `_volume_canvas_created`, `_volume_canvas_renderer`, `_volume_quality_committed_value` | workflow_controller |
| tests/test_tif_workbench.py | 6017 | `test_gpu_stream_degradation_reduces_preview_cache_owner_limit` | volume_preview_render | `_volume_cache_owner_limit`, `_volume_canvas_renderer`, `_volume_last_stats` | workflow_controller |
| tests/test_tif_workbench.py | 6033 | `test_large_volume_mask_preview_can_run_in_background_with_status` | volume_preview_render | `_cache_volume_preview_result`, `_cancel_and_wait_volume_preview_build`, `_volume_canvas_renderer`, `_volume_mask_preview_cache`, `_volume_mask_preview_request`, `_volume_preview_build_thread`, `_volume_preview_request`, `_volume_render_mode` | workflow_controller |
| tests/test_tif_workbench.py | 6065 | `test_stale_background_volume_preview_result_is_ignored` | volume_preview_render | `_on_volume_preview_build_finished`, `_volume_canvas_renderer`, `_volume_preview_cache`, `_volume_preview_pending_key`, `_volume_preview_pending_token`, `_volume_preview_request`, `_volume_render_mode` | workflow_controller |
| tests/test_tif_workbench.py | 6093 | `test_stale_background_volume_preview_context_is_cancelled` | volume_preview_render | `_on_volume_preview_build_finished`, `_start_tif_task`, `_task_request_key`, `_volume_preview_build_task_id`, `_volume_preview_cache`, `_volume_preview_pending_key`, `_volume_preview_pending_mask_key`, `_volume_preview_pending_token`, `_volume_preview_request` | workflow_controller |
| tests/test_tif_workbench.py | 6126 | `test_stale_background_volume_preview_cleanup_keeps_current_task` | volume_preview_render | `_cleanup_volume_preview_build_thread`, `_volume_preview_build_thread`, `_volume_preview_build_worker` | workflow_controller |
| tests/test_tif_workbench.py | 6150 | `test_background_volume_preview_busy_locks_rebuild_controls` | volume_preview_render | `_set_volume_preview_build_controls_busy` | workflow_controller |
| tests/test_tif_workbench.py | 6176 | `test_volume_enhancement_and_clip_plane_are_passed_to_gpu_state` | volume_preview_render | `_volume_canvas_created`, `_volume_canvas_renderer`, `_volume_pitch`, `_volume_render_mode`, `_volume_yaw` | workflow_controller |
| tests/test_tif_workbench.py | 6239 | `test_masked_volume_preview_is_cached_for_interaction_reuse` | volume_preview_render | `_masked_volume_preview`, `_volume_masked_preview_cache` | workflow_controller |
| tests/test_tif_workbench.py | 6259 | `test_volume_preview_is_read_only_for_label_safety` | annotation_save_truth | - | gui_key_path |
| tests/test_tif_workbench.py | 6279 | `test_tif_batch_import_worker_registers_multiple_stacks_metadata_only` | import_export | - | gui_key_path |
| tests/test_tif_workbench.py | 6311 | `test_tif_batch_import_worker_keeps_successes_when_one_stack_fails` | import_export | - | gui_key_path |
| tests/test_tif_workbench.py | 6338 | `test_tif_materialize_worker_builds_working_volume_for_metadata_only_specimen` | selection_lifecycle | - | gui_key_path |
| tests/test_tif_workbench.py | 6371 | `test_tif_materialize_worker_does_not_delete_source_inside_specimen_folder` | selection_lifecycle | - | gui_key_path |
| tests/test_tif_workbench.py | 6407 | `test_tif_workbench_chinese_labels_cover_import_and_backend_controls` | annotation_save_truth | - | gui_key_path |
| tests/test_tif_workbench.py | 6458 | `test_tif_workbench_literal_translation_keys_are_in_chinese_table` | shell_view_text | - | gui_key_path |
| tests/test_tif_workbench.py | 6479 | `test_tif_volume_canvas_factory_reports_gpu_or_cpu_renderer` | volume_preview_render | - | gui_key_path |
| tests/test_tif_workbench.py | 6497 | `test_tif_volume_canvas_factory_can_disable_gpu_preview` | volume_preview_render | - | gui_key_path |
| tests/test_tif_workbench.py | 6508 | `test_gpu_volume_unavailable_reason_is_safe_to_call` | volume_preview_render | - | gui_key_path |
| tests/test_tif_workbench.py | 6512 | `test_tif_workbench_releases_optional_gpu_renderer_on_close` | volume_preview_render | - | gui_key_path |
| tests/test_tif_workbench.py | 6533 | `test_label_role_help_explains_editable_and_read_only_layers` | annotation_save_truth | - | gui_key_path |
| tests/test_tif_workbench.py | 6553 | `test_painting_is_blocked_on_read_only_label_layers` | annotation_save_truth | - | gui_key_path |
| tests/test_tif_workbench.py | 6575 | `test_auto_save_writes_working_edit_after_brush_change` | annotation_save_truth | `_on_label_auto_save_finished`, `_snapshot_label_auto_save_request` | workflow_controller |
| tests/test_tif_workbench.py | 6610 | `test_background_auto_save_keeps_later_same_slice_edits_dirty` | annotation_save_truth | `_dirty_edit_slices`, `_edit_slice_revisions`, `_mark_edit_slice_dirty`, `_on_label_auto_save_finished`, `_snapshot_label_auto_save_request` | workflow_controller |
| tests/test_tif_workbench.py | 6645 | `test_manual_save_queues_behind_running_auto_save_without_waiting` | annotation_save_truth | `_label_auto_save_thread`, `_label_manual_save_running`, `_on_label_auto_save_finished`, `_pending_manual_save_after_auto`, `_snapshot_label_auto_save_request` | workflow_controller |
| tests/test_tif_workbench.py | 6684 | `test_label_auto_save_worker_writes_dirty_slice_in_qt_thread` | annotation_save_truth | - | gui_key_path |
| tests/test_tif_workbench.py | 6724 | `test_visible_annotation_tools_paint_erase_lasso_pick_and_pan` | annotation_save_truth | `_set_current_material_id` | workflow_controller |
| tests/test_tif_workbench.py | 6774 | `test_brush_drag_interpolates_stroke_and_uses_single_undo_step` | annotation_save_truth | `_set_current_material_id` | workflow_controller |
| tests/test_tif_workbench.py | 6803 | `test_lasso_fill_fills_closed_outline_and_undoes_as_single_step` | unclassified | `_dirty_edit_slices`, `_set_current_material_id` | workflow_controller |
| tests/test_tif_workbench.py | 6843 | `test_rectangle_and_ellipse_fill_preview_write_dirty_and_warn_on_risky_area` | annotation_save_truth | `_set_current_material_id` | workflow_controller |
| tests/test_tif_workbench.py | 6880 | `test_current_material_copy_to_neighbor_and_clear_are_confirmed_single_undo_steps` | part_mask_material | `_dirty_edit_slices`, `_set_current_material_id` | workflow_controller |
| tests/test_tif_workbench.py | 6918 | `test_interpolate_fill_uses_current_label_key_slices` | annotation_save_truth | `_dirty_edit_slices`, `_set_current_material_id` | workflow_controller |
| tests/test_tif_workbench.py | 6940 | `test_part_volume_annotation_tools_save_editable_ai_result_not_part_mask` | annotation_save_truth | `_select_volume_tree_item`, `_set_current_material_id` | workflow_controller |
| tests/test_tif_workbench.py | 7028 | `test_saved_part_reslice_edits_reslice_labels_and_hides_part_mask_tools` | annotation_save_truth | `_active_part_mask_likely_available`, `_active_part_mask_volume`, `_select_volume_tree_item`, `_set_current_material_id` | workflow_controller |
| tests/test_tif_workbench.py | 7097 | `test_research_smoke_part_annotation_local_axis_save_and_reopen` | annotation_save_truth | `_select_volume_tree_item`, `_set_current_material_id` | workflow_controller |
| tests/test_tif_workbench.py | 7170 | `test_shape_and_slice_helpers_respect_read_only_layer_and_axis` | volume_preview_render | `_set_current_material_id` | workflow_controller |
| tests/test_tif_workbench.py | 7198 | `test_annotation_cursor_preview_tracks_tool_radius_and_read_only_state` | annotation_save_truth | - | gui_key_path |
| tests/test_tif_workbench.py | 7233 | `test_save_status_and_undo_redo_controls_follow_dirty_slices` | annotation_save_truth | `_set_current_material_id`, `_update_save_status` | workflow_controller |
| tests/test_tif_workbench.py | 7274 | `test_annotation_shortcuts_adjust_tools_radius_save_and_redo` | annotation_save_truth | `_set_current_material_id` | workflow_controller |
| tests/test_tif_workbench.py | 7316 | `test_advanced_annotation_tools_are_spec_only_until_designed` | annotation_save_truth | - | gui_key_path |
| tests/test_tif_workbench.py | 7337 | `test_read_only_slice_axis_reports_block_reason_without_editing` | annotation_save_truth | - | gui_key_path |
| tests/test_tif_workbench.py | 7354 | `test_unsaved_working_edit_prompt_can_cancel_close_and_save` | annotation_save_truth | `_confirm_discard_or_save_working_edit` | workflow_controller |
| tests/test_tif_workbench.py | 7375 | `test_backend_settings_save_into_config_manager` | annotation_save_truth | - | gui_key_path |
| tests/test_tif_workbench.py | 7408 | `test_nnunet_preset_fills_editable_tif_backend_fields` | annotation_save_truth | `_backend_config_from_ui` | workflow_controller |
| tests/test_tif_workbench.py | 7432 | `test_backend_run_controls_are_present_and_idle_by_default` | backend_result_review | - | gui_key_path |
| tests/test_tif_workbench.py | 7463 | `test_backend_unknown_total_progress_stays_percent_bar` | backend_result_review | `_on_tif_backend_progress`, `_start_backend_status`, `_tif_backend_thread`, `_tif_backend_worker` | workflow_controller |
| tests/test_tif_workbench.py | 7482 | `test_training_result_side_panel_compacts_long_paths_without_losing_tooltip` | backend_result_review | `_set_training_result_summary` | workflow_controller |
| tests/test_tif_workbench.py | 7514 | `test_training_result_summary_resolves_metrics_and_artifacts` | backend_result_review | - | gui_key_path |
| tests/test_tif_workbench.py | 7569 | `test_training_result_dialog_renders_tables_and_preview_percentage` | volume_preview_render | - | gui_key_path |
| tests/test_tif_workbench.py | 7616 | `test_train_finished_updates_training_result_panel_and_prediction_manifest` | backend_result_review | `_on_tif_backend_finished`, `_refresh_training_result_controls`, `_set_training_result_summary`, `_tif_backend_thread`, `_tif_backend_worker` | workflow_controller |
| tests/test_tif_workbench.py | 7700 | `test_tif_model_library_selects_notes_and_deletes_registration_only` | backend_result_review | `_populate_tif_model_library_combo` | workflow_controller |
| tests/test_tif_workbench.py | 7752 | `test_predict_target_table_lists_predict_ready_part_without_manual_truth` | annotation_save_truth | `_selected_part_refs_for_action` | workflow_controller |
| tests/test_tif_workbench.py | 7783 | `test_label_schema_and_user_tags_ui_bind_current_part` | annotation_save_truth | `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 7865 | `test_label_schema_import_export_dialogs_round_trip` | annotation_save_truth | `_populate_label_schema_combo` | workflow_controller |
| tests/test_tif_workbench.py | 7907 | `test_new_label_schema_uses_current_part_instead_of_brain_default` | annotation_save_truth | - | gui_key_path |
| tests/test_tif_workbench.py | 7933 | `test_label_schema_import_cancel_keeps_existing_schema` | annotation_save_truth | - | gui_key_path |
| tests/test_tif_workbench.py | 7965 | `test_browse_model_manifest_sets_predict_manifest` | backend_result_review | - | gui_key_path |
| tests/test_tif_workbench.py | 7982 | `test_predict_requires_existing_model_manifest_before_backend_start` | backend_result_review | `_backend_action_running` | workflow_controller |
| tests/test_tif_workbench.py | 8004 | `test_part_training_action_reports_missing_training_truth_without_top_level_fallback` | annotation_save_truth | `_backend_action_running`, `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 8027 | `test_backend_action_waits_for_async_label_save_before_starting` | annotation_save_truth | `_backend_action_running`, `_pending_backend_action_after_save`, `_resume_pending_backend_action_after_save`, `_tif_backend_thread`, `_tif_backend_worker` | workflow_controller |
| tests/test_tif_workbench.py | 8103 | `test_accept_selected_ai_results_promotes_batch_to_manual_truth` | annotation_save_truth | - | gui_key_path |
| tests/test_tif_workbench.py | 8139 | `test_accept_selected_ai_results_requires_saved_current_edit` | annotation_save_truth | - | gui_key_path |
| tests/test_tif_workbench.py | 8172 | `test_ai_review_check_label_reports_unknown_ids` | annotation_save_truth | `_select_volume_tree_item` | workflow_controller |
| tests/test_tif_workbench.py | 8201 | `test_accept_selected_ai_results_warns_before_unopened_batch_acceptance` | backend_result_review | - | gui_key_path |
| tests/test_tif_workbench.py | 8235 | `test_accept_selected_ai_results_blocks_unknown_label_ids` | annotation_save_truth | - | gui_key_path |
| tests/test_tif_workbench.py | 8265 | `test_predict_overwrite_prompt_blocks_or_allows_backend_start` | backend_result_review | `_backend_action_running`, `_tif_backend_thread`, `_tif_backend_worker` | workflow_controller |
| tests/test_tif_workbench.py | 8346 | `test_training_selection_defers_expensive_part_label_id_scan` | selection_lifecycle | `_selected_backend_samples_for_action` | workflow_controller |
| tests/test_tif_workbench.py | 8368 | `test_backend_write_lock_blocks_project_mutations` | selection_lifecycle | `_backend_write_lock_active`, `_set_scope_controls_enabled`, `_tif_backend_thread`, `_tif_backend_worker` | workflow_controller |
| tests/test_tif_workbench.py | 8406 | `test_task_manager_preview_lock_blocks_project_mutations` | selection_lifecycle | `_backend_write_lock_active`, `_backend_write_lock_message`, `_finish_tif_task`, `_start_tif_task` | workflow_controller |
| tests/test_tif_workbench.py | 8422 | `test_backend_failure_preserves_run_folder_for_log_review` | backend_result_review | `_on_tif_backend_failed`, `_tif_backend_action`, `_tif_backend_result_json`, `_tif_backend_run_dir`, `_tif_backend_thread`, `_tif_backend_worker` | workflow_controller |
| tests/test_tif_workbench.py | 8452 | `test_backend_failure_summarizes_single_sample_training_requirement` | backend_result_review | `_on_tif_backend_failed`, `_tif_backend_action`, `_tif_backend_thread`, `_tif_backend_worker` | workflow_controller |
| tests/test_ui_polish_scope.py | 877 | `test_scientific_theme_exposes_comfort_selectors` | unclassified | - | gui_key_path |
| tests/test_ui_polish_scope.py | 891 | `test_dark_theme_palette_covers_linux_native_backgrounds` | unclassified | - | gui_key_path |
| tests/test_ui_polish_scope.py | 897 | `test_light_theme_palette_covers_linux_native_backgrounds` | unclassified | - | gui_key_path |
| tests/test_ui_polish_scope.py | 903 | `test_scientific_theme_strengthens_generic_checked_indicators_without_touching_chip_radios` | unclassified | - | gui_key_path |
| tests/test_ui_polish_scope.py | 911 | `test_themed_buttons_refresh_when_switching_to_light_mode` | shell_view_text | - | gui_key_path |
| tests/test_ui_polish_scope.py | 929 | `test_dialog_button_box_theme_helper_produces_button_like_controls` | shell_view_text | - | gui_key_path |
| tests/test_ui_polish_scope.py | 1015 | `test_pdf_processing_widget_exposes_polish_panels` | shell_view_text | - | gui_key_path |
| tests/test_ui_polish_scope.py | 1046 | `test_pdf_processing_api_inputs_keep_usable_height_when_resized` | unclassified | - | gui_key_path |
| tests/test_ui_polish_scope.py | 1076 | `test_blink_lab_exposes_session_action_and_training_panels` | backend_result_review | - | gui_key_path |
| tests/test_ui_polish_scope.py | 1096 | `test_blink_training_report_matches_parent_dataset_browsing` | backend_result_review | - | gui_key_path |
| tests/test_ui_polish_scope.py | 1142 | `test_cropper_exposes_load_draw_export_flow_panels` | shell_view_text | - | gui_key_path |
| tests/test_ui_polish_scope.py | 1157 | `test_cropper_exports_traceable_crop_records` | import_export | - | gui_key_path |
| tests/test_ui_polish_scope.py | 1184 | `test_cropper_auto_splits_white_gutter_figure_plate` | unclassified | - | gui_key_path |
| tests/test_ui_polish_scope.py | 1217 | `test_cropper_can_delete_and_clear_auto_split_candidates_before_saving` | unclassified | - | gui_key_path |
| tests/test_ui_polish_scope.py | 1237 | `test_main_window_exposes_workbench_polish_hierarchy` | unclassified | - | gui_key_path |
| tests/test_ui_polish_scope.py | 1315 | `test_image_group_header_collapse_does_not_load_image_during_startup` | unclassified | - | gui_key_path |
| tests/test_ui_polish_scope.py | 1359 | `test_image_group_header_collapse_reuses_large_project_group_cache` | selection_lifecycle | - | gui_key_path |
| tests/test_ui_polish_scope.py | 1400 | `test_literature_description_append_reveals_editable_target_box` | annotation_save_truth | - | gui_key_path |
| tests/test_ui_polish_scope.py | 1448 | `test_blink_workbench_uses_lightweight_agent_entry_only` | unclassified | - | gui_key_path |
| tests/test_ui_polish_scope.py | 1460 | `test_part_tree_nests_blink_children_and_preserves_child_selection` | selection_lifecycle | - | gui_key_path |
| tests/test_ui_polish_scope.py | 1497 | `test_workbench_blink_context_resolves_parent_route_and_status` | shell_view_text | - | gui_key_path |
| tests/test_ui_polish_scope.py | 1550 | `test_workbench_parent_context_combo_can_remember_manual_parent` | shell_view_text | - | gui_key_path |
| tests/test_ui_polish_scope.py | 1586 | `test_single_locator_parent_does_not_auto_bind_new_child_part` | unclassified | - | gui_key_path |
| tests/test_ui_polish_scope.py | 1629 | `test_workbench_parent_context_combo_lists_only_real_parent_options` | shell_view_text | - | gui_key_path |
| tests/test_ui_polish_scope.py | 1662 | `test_workbench_parent_context_combo_uses_disabled_unavailable_message_without_options` | shell_view_text | - | gui_key_path |
| tests/test_ui_polish_scope.py | 1677 | `test_annotation_box_roles_keep_child_box_and_shrink_loose_box_separate` | annotation_save_truth | - | gui_key_path |
| tests/test_ui_polish_scope.py | 1713 | `test_parent_box_ratio_lock_defaults_off_and_can_affect_sam_and_roi_boxes` | roi_to_part | - | gui_key_path |
| tests/test_ui_polish_scope.py | 1740 | `test_locked_annotation_box_ratio_keeps_drag_point_inside_box` | annotation_save_truth | - | gui_key_path |
| tests/test_ui_polish_scope.py | 1753 | `test_loose_shrink_box_tool_is_child_only` | unclassified | - | gui_key_path |
| tests/test_ui_polish_scope.py | 1785 | `test_workbench_child_auto_annotate_uses_route_expert_and_sam_polygon` | annotation_save_truth | - | gui_key_path |
| tests/test_ui_polish_scope.py | 1848 | `test_workbench_child_auto_annotate_accepts_parent_auto_box_after_prediction_refresh` | annotation_save_truth | - | gui_key_path |
| tests/test_ui_polish_scope.py | 1917 | `test_workbench_child_auto_annotate_requires_ready_route_and_parent_box` | annotation_save_truth | - | gui_key_path |
| tests/test_ui_polish_scope.py | 1955 | `test_child_auto_annotate_does_not_run_with_unappointed_route_expert` | annotation_save_truth | - | gui_key_path |
| tests/test_ui_polish_scope.py | 2012 | `test_workbench_auto_shrink_saves_parent_context_trajectory` | annotation_save_truth | - | gui_key_path |
| tests/test_ui_polish_scope.py | 2077 | `test_workbench_batch_auto_shrink_skips_existing_trajectories` | unclassified | - | gui_key_path |
| tests/test_ui_polish_scope.py | 2153 | `test_workbench_auto_shrink_requires_polygon_and_loose_box` | unclassified | - | gui_key_path |
| tests/test_ui_polish_scope.py | 2186 | `test_workbench_train_current_blink_expert_uses_current_parent_child_context` | backend_result_review | - | gui_key_path |
| tests/test_ui_polish_scope.py | 2234 | `test_child_expert_datasets_filter_trajectories_by_training_scope_images` | backend_result_review | - | gui_key_path |
| tests/test_ui_polish_scope.py | 2283 | `test_workbench_shared_training_progress_tracks_child_expert_thread` | backend_result_review | - | gui_key_path |
| tests/test_ui_polish_scope.py | 2339 | `test_workbench_child_training_stop_button_delegates_to_blink_lab` | backend_result_review | - | gui_key_path |
| tests/test_ui_polish_scope.py | 2368 | `test_workbench_training_results_browser_discovers_parent_and_child_reports` | backend_result_review | - | gui_key_path |
| tests/test_ui_polish_scope.py | 2441 | `test_workbench_training_buttons_are_mutually_exclusive` | backend_result_review | - | gui_key_path |
| tests/test_ui_polish_scope.py | 2483 | `test_remove_selected_tree_part_delegates_to_project_cleanup` | selection_lifecycle | - | gui_key_path |
| tests/test_ui_polish_scope.py | 2509 | `test_model_settings_hosts_project_route_management_panel` | selection_lifecycle | - | gui_key_path |
| tests/test_ui_polish_scope.py | 2664 | `test_settings_numeric_controls_ignore_mouse_wheel` | shell_view_text | - | gui_key_path |
| tests/test_ui_polish_scope.py | 2688 | `test_route_panel_can_delete_selected_child_expert_file` | shell_view_text | - | gui_key_path |
| tests/test_ui_polish_scope.py | 2752 | `test_route_panel_can_edit_selected_child_expert_note` | annotation_save_truth | - | gui_key_path |
| tests/test_ui_polish_scope.py | 2814 | `test_model_settings_exposes_locator_scope_selection` | selection_lifecycle | - | gui_key_path |
| tests/test_ui_polish_scope.py | 2866 | `test_model_settings_parent_box_ratio_rejects_partial_width_height` | backend_result_review | - | gui_key_path |
| tests/test_ui_polish_scope.py | 2895 | `test_main_window_run_prediction_omits_retired_cascade_toggle_argument` | backend_result_review | - | gui_key_path |
| tests/test_ui_polish_scope.py | 2957 | `test_parent_prediction_can_replace_unconfirmed_vlm_draft_but_keeps_confirmed_label` | annotation_save_truth | - | gui_key_path |
| tests/test_ui_polish_scope.py | 3011 | `test_vlm_does_not_replace_model_prediction_draft` | backend_result_review | - | gui_key_path |
| tests/test_ui_polish_scope.py | 3049 | `test_parent_prediction_can_replace_box_only_vlm_draft` | backend_result_review | - | gui_key_path |
| tests/test_ui_polish_scope.py | 3086 | `test_canvas_splits_vlm_and_model_auto_boxes` | backend_result_review | - | gui_key_path |
| tests/test_ui_polish_scope.py | 3123 | `test_vlm_preannotation_can_replace_unconfirmed_draft_but_keeps_confirmed_label` | annotation_save_truth | - | gui_key_path |
| tests/test_ui_polish_scope.py | 3177 | `test_workbench_agent_context_includes_model_profile_and_route_backend` | backend_result_review | - | gui_key_path |
| tests/test_ui_polish_scope.py | 3213 | `test_training_success_updates_active_model_profile_parent_weights` | backend_result_review | - | gui_key_path |
| tests/test_ui_polish_scope.py | 3238 | `test_main_window_model_delete_buttons_are_clear_and_stateful` | backend_result_review | - | gui_key_path |
| tests/test_ui_polish_scope.py | 3292 | `test_main_window_parent_model_notes_are_editable_and_cleanup_on_delete` | annotation_save_truth | - | gui_key_path |
| tests/test_ui_polish_scope.py | 3357 | `test_main_window_locator_combo_marks_legacy_and_logs_display_state` | unclassified | - | gui_key_path |
| tests/test_ui_polish_scope.py | 3383 | `test_main_window_model_selector_rows_use_shared_grid_alignment` | backend_result_review | - | gui_key_path |
| tests/test_ui_polish_scope.py | 3408 | `test_main_window_locator_delete_removes_prefixed_weight_file` | unclassified | - | gui_key_path |
| tests/test_ui_polish_scope.py | 3435 | `test_main_window_segmenter_delete_resets_runtime_to_base` | unclassified | - | gui_key_path |
| tests/test_ui_polish_scope.py | 3462 | `test_main_window_same_image_refresh_preserves_viewport` | unclassified | - | gui_key_path |
| tests/test_ui_polish_scope.py | 3505 | `test_main_window_polygon_edit_defers_save_and_skips_blink_auto_sync` | annotation_save_truth | - | gui_key_path |
| tests/test_ui_polish_scope.py | 3554 | `test_main_window_sam_box_request_is_queued_without_direct_worker_call` | unclassified | - | gui_key_path |
| tests/test_ui_polish_scope.py | 3601 | `test_main_window_polygon_edit_updates_image_list_without_full_rebuild` | annotation_save_truth | - | gui_key_path |
| tests/test_ui_polish_scope.py | 3639 | `test_main_window_remove_selected_images_defers_save_and_removes_visible_rows` | annotation_save_truth | - | gui_key_path |
| tests/test_ui_polish_scope.py | 3712 | `test_main_window_remove_current_middle_image_selects_next_visible_image` | unclassified | - | gui_key_path |
| tests/test_ui_polish_scope.py | 3764 | `test_main_window_remove_current_last_image_selects_previous_visible_image` | unclassified | - | gui_key_path |
| tests/test_ui_polish_scope.py | 3816 | `test_main_window_move_images_to_group_defers_save` | annotation_save_truth | - | gui_key_path |
| tests/test_ui_polish_scope.py | 3860 | `test_main_window_training_scope_limits_parent_training_preflight_to_selected_group` | backend_result_review | - | gui_key_path |
| tests/test_ui_polish_scope.py | 3936 | `test_main_window_manual_polygon_edit_clears_auto_annotated_blocker` | annotation_save_truth | - | gui_key_path |
| tests/test_ui_polish_scope.py | 3976 | `test_main_window_accept_current_ai_drafts_requires_confirmation` | unclassified | - | gui_key_path |
| tests/test_ui_polish_scope.py | 4027 | `test_main_window_accept_current_ai_drafts_updates_list_without_full_rebuild` | unclassified | - | gui_key_path |
| tests/test_ui_polish_scope.py | 4073 | `test_vlm_stop_clears_remaining_queue_and_finishes_cancelled_run` | task_lifecycle | - | gui_key_path |
| tests/test_ui_polish_scope.py | 4135 | `test_vlm_preannotation_starts_workers_up_to_configured_concurrency` | annotation_save_truth | - | gui_key_path |
| tests/test_ui_polish_scope.py | 4178 | `test_main_window_verify_current_image_defers_save_and_updates_list` | annotation_save_truth | - | gui_key_path |
| tests/test_ui_polish_scope.py | 4220 | `test_main_window_accept_batch_ai_drafts_confirms_project_auto_drafts` | selection_lifecycle | - | gui_key_path |
| tests/test_ui_polish_scope.py | 4285 | `test_clear_ai_labels_can_target_selected_image_group` | annotation_save_truth | - | gui_key_path |
| tests/test_ui_polish_scope.py | 4343 | `test_main_window_image_switch_keeps_pending_polygon_edit_async` | annotation_save_truth | - | gui_key_path |
| tests/test_ui_polish_scope.py | 4407 | `test_main_window_image_switch_does_not_save_taxon_combo_update` | annotation_save_truth | - | gui_key_path |
| tests/test_ui_polish_scope.py | 4459 | `test_main_window_vlm_image_result_updates_list_without_full_rebuild` | backend_result_review | - | gui_key_path |

## Stage 10 最终迁移状态（2026-07-10）

Stage 0 表格继续保留为历史基线，不回写旧行号。最终候选按责任层复核如下：

| 研究工作流 | 最终直接测试入口 | 默认验证 suite | 状态 |
| --- | --- | --- | --- |
| Selection | `tests/test_tif_selection_workflow_controller.py` | `tif_workbench` | `verified` |
| Project Lifecycle | `tests/test_tif_project_lifecycle_controller.py` | `tif_workbench` | `verified` |
| Annotation / Save / Truth | `tests/test_tif_annotation_workflow_controller.py` | `tif_workbench` | `verified` |
| ROI-to-Part | `tests/test_tif_roi_workflow_controller.py` | `tif_workbench` | `verified` |
| Part Mask / Material | `tests/test_tif_part_mask_workflow_controller.py` | `tif_workbench` | `verified` |
| Volume Preview / Rendering | `tests/test_tif_volume_render_controller.py`、`tests/test_tif_preview_controller.py` | `tif_workbench`、`tif_preview_export` | `verified` |
| Local Axis / Reslice | `tests/test_tif_local_axis_controller.py` | `tif_workbench` | `verified` |
| Backend / Training / Prediction | `tests/test_tif_backend_panel_controller.py` | `tif_workbench` | `verified` |
| Result Review | `tests/test_tif_result_review_controller.py` | `tif_workbench` | `verified` |
| Shell / Signal Router / Coordinator | `tests/test_tif_workbench_shell.py`、`tests/test_tif_workbench_signal_router.py`、`tests/test_tif_workbench_coordinator.py` | `tif_workbench` | `verified` |
| Architecture limits | `tests/test_tif_workbench_architecture_analysis.py` | `tif_architecture_round3` | `verified` |

- `tests/test_tif_workbench.py` 保留 220 条完整 Widget 和关键 GUI 路径测试，用于验证真实控件组合、线程完成后的界面刷新和跨工作流闭环；它不再是所有行为的唯一受测入口。
- 11 组责任主体共有 58 条 controller/shell/coordinator 直接测试；Stage 10 另以 67 条登记、信号和状态合同测试复核默认 suite 覆盖。
- Stage 10 审计发现 ROI controller 曾漏登 `scripts/run_validation_suite.py`，Volume Render controller 曾漏登架构 GUI 分组；现已补齐并由验证脚本合同测试证明。
- 当时九组自动门快照共 698 条通过。新增 Stage 10 可见状态与 readiness 回归后，当前最终门为 702 条。

## Stage 10 隔离真实数据补充证据（2026-07-10）

- `tests/test_tif_round3_real_data_acceptance.py` 已进入 `tif_workbench` suite 和 GUI 架构分组。
- 默认无 `TAXAMASK_REAL_TIF_FIXTURE` 时安全跳过；显式指向真实只读 sidecar 时，在 `.tmp_validation` 隔离 SQLite 项目执行完整写入链。
- 本机使用真实蚂蚁体积（11×144×104）完成 ROI-to-Part、accepted mask、部位标注保存、Local Axis reslice 和 SQLite 重开选择；源 sidecar SHA-256 树哈希前后一致。
- 包含该真实数据测试的阶段快照九组共 698 条通过；当前最终门为 702 条。


## Stage 10 真实 GPU 预测与 SQLite 重开补充证据（2026-07-10）

- `tests/test_tif_json_to_sqlite_migration.py` 增加顶层 `raw_ai_prediction_backup` 的 SQLite 行、统计和 manager 重开断言。
- `tests/test_tif_nnunet_v2_backend.py::TifNnunetV2BackendTests.test_adapter_predict_top_level_volume_imports_current_labels` 增加预测完成后 SQLite 重开、raw backup 状态/路径/体积一致性断言。
- 真实 GPU 0 + Dataset601 匹配脑体积经生产 `TifBackendRunner` 连续两次完成预测；修复后一次运行 225 个 sliding-window step、`returncode=0`，SQLite 重开恢复 raw backup。
- 修复后显式启用真实 fixture 的九组验证仍为 698 条全部通过，最终 42 个修改/新增 Python 文件 `py_compile` 通过。
- 技术叠加图已人工检查输入与预测坐标一致、结果非空；该检查不替代蚂蚁脑区科研质量判断。

## 可见状态同步与 renderer 工厂回归补充（2026-07-10）

- 新增工作台回归：三维模式下加载 part 后，`display_mode`、下拉框和 `view_stack` 继续一致，加载反馈进入完成态。
- 新增 Local Axis 回归：同一 part 重新加载不清除现有草稿；切换到其他 part 仍按作用域清除。
- 新增 renderer 工厂回归：显式要求嵌入式 QOpenGLWidget 时，其优先级高于离屏 renderer；画布创建使用稳定 Qt parent。
- 最终显式真实 fixture 九组自动门共 **702 条全部通过**。
- 本机可见 OpenGL 初始化兼容性与数据/模型安全分开记录；隔离验收通过正式 CPU 3D fallback 完成真实体与 Local Axis overlay 观察。
