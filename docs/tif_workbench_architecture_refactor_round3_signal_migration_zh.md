# TIF Workbench Round 3 Signal Migration Ledger

由 `scripts/analyze_tif_workbench_architecture.py` 生成。目标 controller 和迁移阶段在各 Stage 实施时填写并复核。

> 状态说明：本表记录当前未提交候选工作树的信号快照。文中“候选已跑通，待正式复核”“已迁移”仅表示候选实现曾通过当时检查，不代表用户已批准阶段完成。Stage 0-5 和 Stage 6 半迁移内容必须在计划确认后逐阶段重新审计：信号最终 target、幂等连接、解绑/销毁、worker stale context 和对应测试缺一不可。

## Stage 5 Part Mask / Material 候选信号快照，待计划确认后重新审计

- 候选 controller 的 `bind_signals()` 当前注册 16 条控件信号：相邻切片复制、清除当前材料、contour 模式、矩形关键帧、删除/清空关键帧、前后关键切片、preview、accept、clear preview、材料增删改选。
- preview worker 与 metadata-only materialize worker 的 `started/progress/finished/failed/quit/deleteLater` 生命周期当前由 controller 持有；正式 Stage 5 复核必须逐条确认 stale token/context、取消、销毁和单次回调。
- 画布 contour 完成、material picker 和 overlay 交互必须在正式信号表中列为 canvas → controller，不得只统计 Qt `.connect(...)`。
- 正式通过前必须补齐：16 条控件信号的 target/幂等测试、两类 worker 回调契约、旧 Widget signal slot 删除清单、验证 suite 归属和真实 part mask/material 操作记录。

## Stage 3 Annotation / Save / Truth 候选已迁移，待计划确认后重新审计

## Stage 4 ROI-to-Part 候选迁移快照，待计划确认后重新审计

- `part_bbox_edit.textChanged`、Draw ROI、Save draft、Confirm、Cancel 共五条控件信号直接由 `TifRoiWorkflowController.bind_signals()` 注册。
- `TifSliceCanvas` 的 ROI drag finish 和 overlay 双击直接调用 ROI controller。
- `TifConfirmPartRoiWorker` 的 progress/finished/failed 直接连接 ROI controller。
- Widget 中旧 ROI signal/test wrappers 已删除；controller 唯一持有草稿状态和 confirm worker 生命周期。
- 合同测试：`test_bind_signals_is_idempotent_and_targets_roi_controller`、`test_widget_does_not_own_roi_state_or_confirm_worker_fields`。

- 25 条工具、brush size、undo/redo、保存、自动保存开关、truth promotion 和快捷键信号由 `TifAnnotationWorkflowController.bind_signals()` 直接注册。
- `auto_save_timer.timeout` 直接调用 `TifAnnotationWorkflowController.start_auto_save`。
- 自动保存、手动保存和 truth promotion worker 的 `finished` / `failed` 直接连接 Annotation controller 回调。
- `TifSliceCanvas` 的笔刷、套索、矩形/椭圆和 stroke 生命周期直接调用 Annotation controller。
- Stage 0 表格中的旧行号和旧 Widget target 仅作为历史基线；当前 controller 注册表是候选实现状态，须在计划确认后按 signal contract、解绑和单次触发要求重新审计。
- 合同测试：`test_bind_signals_is_idempotent_and_tool_button_targets_controller`，断言重复 bind 后仍为 25 条连接，保存按钮单次触发一次 controller command。

| Line | Signal | Current target | Workflow | Target owner | Stage | Contract test |
| --- | --- | --- | --- | --- | --- | --- |
| 464 | `self.specimen_list.currentItemChanged` | `self._on_specimen_tree_selected` | selection_lifecycle | `TifSelectionWorkflowController.on_tree_selection_changed` | Stage 2 completed | `test_bind_signals_is_idempotent_and_targets_controller` + GUI selection tests |
| 465 | `self.specimen_list.customContextMenuRequested` | `self._on_specimen_tree_context_menu` | selection_lifecycle | `TifSelectionWorkflowController` routed command | Stage 2 completed | `test_bind_signals_is_idempotent_and_targets_controller` |
| 481 | `self.display_mode_combo.currentIndexChanged` | `self.on_display_mode_changed` | unclassified | TBD | TBD | TBD |
| 484 | `self.slice_slider.valueChanged` | `self.on_slice_slider_changed` | volume_preview_render | TBD | TBD | TBD |
| 490 | `self.slice_axis_combo.currentIndexChanged` | `self.on_slice_axis_changed` | volume_preview_render | TBD | TBD | TBD |
| 494 | `self.label_role_combo.currentIndexChanged` | `self._reload_label_volume` | annotation_save_truth | TBD | TBD | TBD |
| 508 | `self.opacity_slider.valueChanged` | `self.render_current_slice` | volume_preview_render | TBD | TBD | TBD |
| 512 | `self.brightness_slider.valueChanged` | `self.render_current_slice` | volume_preview_render | TBD | TBD | TBD |
| 516 | `self.contrast_slider.valueChanged` | `self.render_current_slice` | volume_preview_render | TBD | TBD | TBD |
| 521 | `self.volume_cutoff_slider.valueChanged` | `self.render_volume_preview` | volume_preview_render | TBD | TBD | TBD |
| 524 | `self.volume_projection_combo.currentIndexChanged` | `self._on_volume_projection_changed` | selection_lifecycle | TBD | TBD | TBD |
| 532 | `self.volume_quality_slider.sliderPressed` | `self._on_volume_quality_drag_started` | volume_preview_render | TBD | TBD | TBD |
| 533 | `self.volume_quality_slider.sliderMoved` | `self._on_volume_quality_drag_moved` | volume_preview_render | TBD | TBD | TBD |
| 534 | `self.volume_quality_slider.sliderReleased` | `self._on_volume_quality_released` | volume_preview_render | TBD | TBD | TBD |
| 539 | `self.volume_sample_slider.valueChanged` | `self.render_volume_preview` | volume_preview_render | TBD | TBD | TBD |
| 542 | `self.volume_clarity_check.toggled` | `self._on_volume_clarity_toggled` | volume_preview_render | TBD | TBD | TBD |
| 546 | `self.volume_roi_detail_check.toggled` | `self._refresh_volume_preview` | roi_to_part | TBD | TBD | TBD |
| 550 | `self.volume_roi_source_combo.currentIndexChanged` | `self._refresh_volume_preview` | roi_to_part | TBD | TBD | TBD |
| 554 | `self.volume_roi_inspect_check.toggled` | `self._refresh_volume_preview` | roi_to_part | TBD | TBD | TBD |
| 561 | `self.volume_roi_scale_slider.sliderPressed` | `self._on_volume_roi_scale_drag_started` | roi_to_part | TBD | TBD | TBD |
| 562 | `self.volume_roi_scale_slider.valueChanged` | `self._on_volume_roi_scale_changed` | roi_to_part | TBD | TBD | TBD |
| 563 | `self.volume_roi_scale_slider.sliderReleased` | `self._on_volume_roi_scale_released` | roi_to_part | TBD | TBD | TBD |
| 568 | `self.volume_roi_budget_combo.currentIndexChanged` | `self._refresh_volume_preview` | roi_to_part | TBD | TBD | TBD |
| 582 | `self.volume_tint_combo.currentIndexChanged` | `self._on_volume_tint_changed` | volume_preview_render | TBD | TBD | TBD |
| 585 | `self.btn_volume_custom_color.clicked` | `self.choose_volume_custom_color` | volume_preview_render | TBD | TBD | TBD |
| 588 | `self.btn_volume_morphology_preset.clicked` | `self.apply_morphology_inspect_preset` | volume_preview_render | TBD | TBD | TBD |
| 594 | `self.volume_transfer_opacity_slider.sliderReleased` | `self._on_volume_transfer_opacity_released` | volume_preview_render | TBD | TBD | TBD |
| 595 | `self.volume_transfer_opacity_slider.valueChanged` | `self._on_volume_transfer_opacity_changed` | volume_preview_render | TBD | TBD | TBD |
| 600 | `self.volume_enhancement_slider.valueChanged` | `self._on_volume_display_enhancement_changed` | volume_preview_render | TBD | TBD | TBD |
| 605 | `self.volume_tone_slider.valueChanged` | `self._on_volume_display_enhancement_changed` | volume_preview_render | TBD | TBD | TBD |
| 609 | `self.volume_shader_quality_combo.currentIndexChanged` | `self._on_volume_shader_quality_changed` | volume_preview_render | TBD | TBD | TBD |
| 613 | `self.volume_surface_refine_check.toggled` | `self._on_volume_display_enhancement_changed` | volume_preview_render | TBD | TBD | TBD |
| 617 | `self.volume_clip_plane_check.toggled` | `self._on_volume_clip_plane_changed` | volume_preview_render | TBD | TBD | TBD |
| 621 | `self.volume_local_axes_check.toggled` | `self.render_volume_preview` | volume_preview_render | TBD | TBD | TBD |
| 622 | `self.volume_local_axes_check.toggled` | `self._update_local_axis_summary` | volume_preview_render | TBD | TBD | TBD |
| 632 | `self.volume_mask_combo.currentIndexChanged` | `self._on_volume_mask_changed` | volume_preview_render | TBD | TBD | TBD |
| 637 | `self.volume_mask_opacity_slider.valueChanged` | `self.render_volume_preview` | volume_preview_render | TBD | TBD | TBD |
| 640 | `self.btn_reset_volume_view.clicked` | `self.reset_volume_view` | volume_preview_render | TBD | TBD | TBD |
| 656 | `self.local_axis_details_check.toggled` | `self._update_local_axis_summary` | local_axis_reslice | TBD | TBD | TBD |
| 678 | `self.show_debug_paths_check.toggled` | `self._on_show_debug_paths_toggled` | unclassified | TBD | TBD | TBD |
| 690 | `self.material_table.itemSelectionChanged` | `self._on_material_selected` | selection_lifecycle | TBD | TBD | TBD |
| 700 | `self.btn_add_material.clicked` | `self.add_material` | part_mask_material | TBD | TBD | TBD |
| 702 | `self.btn_edit_material.clicked` | `self.edit_selected_material` | annotation_save_truth | TBD | TBD | TBD |
| 704 | `self.btn_delete_material.clicked` | `self.delete_selected_material` | part_mask_material | TBD | TBD | TBD |
| 710 | `self.label_schema_combo.currentIndexChanged` | `self._on_label_schema_selected` | annotation_save_truth | TBD | TBD | TBD |
| 725 | `self.label_schema_table.itemChanged` | `self._on_label_schema_table_item_changed` | annotation_save_truth | TBD | TBD | TBD |
| 726 | `self.label_schema_table.cellDoubleClicked` | `self._on_label_schema_table_cell_double_clicked` | annotation_save_truth | TBD | TBD | TBD |
| 727 | `self.label_schema_table.itemSelectionChanged` | `self._on_label_schema_row_selected` | selection_lifecycle | TBD | TBD | TBD |
| 730 | `self.btn_new_label_schema.clicked` | `self.new_label_schema` | annotation_save_truth | TBD | TBD | TBD |
| 733 | `self.btn_save_label_schema.clicked` | `self.save_current_label_schema` | annotation_save_truth | TBD | TBD | TBD |
| 736 | `self.btn_bind_label_schema_to_part.clicked` | `self.bind_current_part_label_schema` | annotation_save_truth | TBD | TBD | TBD |
| 739 | `self.btn_add_label_schema_row.clicked` | `self.add_label_schema_row` | annotation_save_truth | TBD | TBD | TBD |
| 742 | `self.btn_remove_label_schema_row.clicked` | `self.remove_selected_label_schema_row` | annotation_save_truth | TBD | TBD | TBD |
| 745 | `self.btn_import_label_schema.clicked` | `self.import_label_schema_dialog` | annotation_save_truth | TBD | TBD | TBD |
| 748 | `self.btn_export_label_schema.clicked` | `self.export_label_schema_dialog` | annotation_save_truth | TBD | TBD | TBD |
| 765 | `self.part_user_tag_table.itemSelectionChanged` | `self._on_part_user_tag_selected` | selection_lifecycle | TBD | TBD | TBD |
| 767 | `self.part_user_tag_table.model().rowsMoved` | `lambda *args: QTimer.singleShot(0, self.save_part_user_tag_order_from_table)` | annotation_save_truth | TBD | TBD | TBD |
| 779 | `self.part_user_tag_color_edit.textChanged` | `self._update_part_user_tag_color_swatch` | annotation_save_truth | TBD | TBD | TBD |
| 784 | `self.btn_choose_part_user_tag_color.clicked` | `self.choose_part_user_tag_color` | unclassified | TBD | TBD | TBD |
| 787 | `self.btn_new_part_user_tag.clicked` | `self.new_part_user_tag` | unclassified | TBD | TBD | TBD |
| 790 | `self.btn_save_part_user_tag.clicked` | `self.save_part_user_tag` | annotation_save_truth | TBD | TBD | TBD |
| 793 | `self.btn_delete_part_user_tag.clicked` | `self.delete_selected_part_user_tag` | unclassified | TBD | TBD | TBD |
| 796 | `self.btn_move_part_user_tag_up.clicked` | `lambda : self.move_selected_part_user_tag(-1)` | unclassified | TBD | TBD | TBD |
| 799 | `self.btn_move_part_user_tag_down.clicked` | `lambda : self.move_selected_part_user_tag(1)` | unclassified | TBD | TBD | TBD |
| 802 | `self.btn_apply_part_user_tags.clicked` | `self.apply_part_user_tags_to_current_part` | unclassified | TBD | TBD | TBD |
| 809 | `self.btn_tool_brush.clicked` | `lambda checked=False: self.set_annotation_tool_mode('brush')` | annotation_save_truth | TBD | TBD | TBD |
| 813 | `self.btn_tool_eraser.clicked` | `lambda checked=False: self.set_annotation_tool_mode('eraser')` | annotation_save_truth | TBD | TBD | TBD |
| 817 | `self.btn_tool_lasso.clicked` | `lambda checked=False: self.set_annotation_tool_mode('lasso')` | annotation_save_truth | TBD | TBD | TBD |
| 821 | `self.btn_tool_rectangle.clicked` | `lambda checked=False: self.set_annotation_tool_mode('rectangle')` | annotation_save_truth | TBD | TBD | TBD |
| 825 | `self.btn_tool_ellipse.clicked` | `lambda checked=False: self.set_annotation_tool_mode('ellipse')` | annotation_save_truth | TBD | TBD | TBD |
| 828 | `self.btn_interpolate_current_label.clicked` | `self.interpolate_current_label_between_key_slices` | annotation_save_truth | TBD | TBD | TBD |
| 832 | `self.btn_tool_picker.clicked` | `lambda checked=False: self.set_annotation_tool_mode('picker')` | annotation_save_truth | TBD | TBD | TBD |
| 836 | `self.btn_tool_pan.clicked` | `lambda checked=False: self.set_annotation_tool_mode('pan')` | annotation_save_truth | TBD | TBD | TBD |
| 841 | `self.brush_size_slider.valueChanged` | `self._on_brush_size_changed` | annotation_save_truth | TBD | TBD | TBD |
| 843 | `self.btn_undo.clicked` | `self.undo` | unclassified | TBD | TBD | TBD |
| 845 | `self.btn_redo.clicked` | `self.redo` | unclassified | TBD | TBD | TBD |
| 847 | `self.btn_save_edit.clicked` | `self.save_working_edit_async` | annotation_save_truth | TBD | TBD | TBD |
| 851 | `self.auto_save_check.toggled` | `self._on_auto_save_toggled` | annotation_save_truth | TBD | TBD | TBD |
| 861 | `self.btn_promote.clicked` | `self.promote_working_edit` | annotation_save_truth | TBD | TBD | TBD |
| 864 | `self.btn_accept_selected_ai_results.clicked` | `self.accept_selected_ai_results` | backend_result_review | TBD | TBD | TBD |
| 866 | `self.btn_copy_draft.clicked` | `self.copy_latest_model_draft_to_working_edit` | annotation_save_truth | TBD | TBD | TBD |
| 870 | `self.btn_copy_material_prev.clicked` | `lambda : self.copy_current_material_to_adjacent_slice(-1)` | part_mask_material | TBD | TBD | TBD |
| 873 | `self.btn_copy_material_next.clicked` | `lambda : self.copy_current_material_to_adjacent_slice(1)` | part_mask_material | TBD | TBD | TBD |
| 876 | `self.btn_clear_current_material.clicked` | `self.clear_current_material_on_slice` | part_mask_material | TBD | TBD | TBD |
| 879 | `self.btn_import_tif.clicked` | `self.import_tif_stack_dialog` | import_export | TBD | TBD | TBD |
| 882 | `self.btn_import_amira.clicked` | `self.import_amira_directory_dialog` | import_export | TBD | TBD | TBD |
| 886 | `self.part_bbox_edit.textChanged` | `self.render_current_slice` | annotation_save_truth | TBD | TBD | TBD |
| 890 | `self.btn_part_draw_roi.toggled` | `self.set_part_roi_draw_mode` | roi_to_part | TBD | TBD | TBD |
| 893 | `self.btn_save_part_roi.clicked` | `self.save_part_roi_draft` | annotation_save_truth | TBD | TBD | TBD |
| 896 | `self.btn_confirm_part_roi.clicked` | `self.confirm_part_roi_to_part` | roi_to_part | TBD | TBD | TBD |
| 899 | `self.btn_cancel_part_roi.clicked` | `self.cancel_part_roi_draft` | roi_to_part | TBD | TBD | TBD |
| 902 | `self.btn_create_part.clicked` | `self.create_part_from_bbox_dialog` | unclassified | TBD | TBD | TBD |
| 905 | `self.btn_add_rect_keyframe.clicked` | `self.add_current_rect_keyframe` | unclassified | TBD | TBD | TBD |
| 909 | `self.btn_draw_part_contour.toggled` | `self.set_part_contour_draw_mode` | annotation_save_truth | TBD | TBD | TBD |
| 912 | `self.btn_delete_part_contour.clicked` | `self.delete_current_part_keyframe` | annotation_save_truth | TBD | TBD | TBD |
| 915 | `self.btn_clear_part_keyframes.clicked` | `self.clear_part_mask_keyframes` | part_mask_material | TBD | TBD | TBD |
| 918 | `self.btn_prev_key_slice.clicked` | `lambda : self.jump_part_keyframe('previous')` | volume_preview_render | TBD | TBD | TBD |
| 921 | `self.btn_next_key_slice.clicked` | `lambda : self.jump_part_keyframe('next')` | volume_preview_render | TBD | TBD | TBD |
| 924 | `self.btn_preview_part_mask.clicked` | `self.preview_part_mask_from_keyframes` | part_mask_material | TBD | TBD | TBD |
| 927 | `self.btn_accept_part_mask.clicked` | `self.accept_part_mask_preview` | part_mask_material | TBD | TBD | TBD |
| 930 | `self.btn_clear_part_preview.clicked` | `self.clear_part_mask_preview` | part_mask_material | TBD | TBD | TBD |
| 933 | `self.btn_local_axis_reslice.clicked` | `self.export_current_local_axis_reslice` | volume_preview_render | TBD | TBD | TBD |
| 936 | `self.btn_copy_source_z_axis.clicked` | `self.copy_source_z_axis_to_local_axis_draft` | local_axis_reslice | TBD | TBD | TBD |
| 940 | `self.btn_pick_roll_ref_a.clicked` | `lambda checked=False: self.set_local_axis_pick_target('roll_a' if checked else '')` | local_axis_reslice | TBD | TBD | TBD |
| 944 | `self.btn_pick_roll_ref_b.clicked` | `lambda checked=False: self.set_local_axis_pick_target('roll_b' if checked else '')` | local_axis_reslice | TBD | TBD | TBD |
| 948 | `self.btn_pick_roll_ref_c.clicked` | `lambda checked=False: self.set_local_axis_pick_target('roll_c' if checked else '')` | local_axis_reslice | TBD | TBD | TBD |
| 951 | `self.btn_align_axis_to_reference_plane.clicked` | `self.align_local_axis_to_reference_plane` | local_axis_reslice | TBD | TBD | TBD |
| 954 | `self.btn_clear_roll_refs.clicked` | `self.clear_local_axis_roll_references` | local_axis_reslice | TBD | TBD | TBD |
| 957 | `self.btn_clear_local_axis_draft.clicked` | `self.clear_local_axis_draft` | local_axis_reslice | TBD | TBD | TBD |
| 963 | `self.btn_export_local_axis_training_manifest.clicked` | `self.export_local_axis_training_manifest_dialog` | local_axis_reslice | TBD | TBD | TBD |
| 966 | `self.btn_export_part_package.clicked` | `self.export_current_part_package` | import_export | TBD | TBD | TBD |
| 969 | `self.btn_delete_part_volume.clicked` | `self.delete_current_part_volume` | volume_preview_render | TBD | TBD | TBD |
| 972 | `self.btn_export_training.clicked` | `self.export_training_dataset` | backend_result_review | TBD | TBD | TBD |
| 982 | `self.backend_manifest_edit.textChanged` | `self._on_predict_manifest_text_changed` | annotation_save_truth | TBD | TBD | TBD |
| 985 | `self.btn_browse_model_manifest.clicked` | `self.browse_model_manifest` | backend_result_review | TBD | TBD | TBD |
| 988 | `self.btn_use_nnunet_backend_preset.clicked` | `self.apply_nnunet_v2_backend_preset` | backend_result_review | TBD | TBD | TBD |
| 991 | `self.btn_save_backend.clicked` | `self.save_backend_settings` | annotation_save_truth | TBD | TBD | TBD |
| 994 | `self.btn_prepare_dataset.clicked` | `lambda : self.run_backend_action('prepare_dataset')` | backend_result_review | TBD | TBD | TBD |
| 997 | `self.btn_train_backend.clicked` | `lambda : self.run_backend_action('train')` | backend_result_review | TBD | TBD | TBD |
| 1000 | `self.btn_import_prediction.clicked` | `lambda : self.run_backend_action('predict')` | backend_result_review | TBD | TBD | TBD |
| 1003 | `self.predict_filter_combo.currentIndexChanged` | `self.refresh_predict_targets` | backend_result_review | TBD | TBD | TBD |
| 1014 | `self.predict_targets_table.itemChanged` | `self._on_predict_target_item_changed` | backend_result_review | TBD | TBD | TBD |
| 1017 | `self.btn_refresh_predict_targets.clicked` | `self.refresh_predict_targets` | backend_result_review | TBD | TBD | TBD |
| 1020 | `self.btn_select_current_predict_target.clicked` | `self.select_current_predict_target` | selection_lifecycle | TBD | TBD | TBD |
| 1023 | `self.btn_select_ready_predict_targets.clicked` | `self.select_all_ready_predict_targets` | selection_lifecycle | TBD | TBD | TBD |
| 1026 | `self.btn_clear_predict_targets.clicked` | `self.clear_predict_target_selection` | selection_lifecycle | TBD | TBD | TBD |
| 1033 | `self.btn_stop_backend.clicked` | `self.cancel_backend_action` | backend_result_review | TBD | TBD | TBD |
| 1037 | `self.btn_open_backend_run.clicked` | `self.open_latest_backend_run_folder` | backend_result_review | TBD | TBD | TBD |
| 1041 | `self.btn_open_backend_result.clicked` | `self.open_latest_backend_result_json` | backend_result_review | TBD | TBD | TBD |
| 1050 | `self.btn_show_training_result_summary.clicked` | `self.show_latest_training_result_summary` | backend_result_review | TBD | TBD | TBD |
| 1054 | `self.btn_open_training_model_output.clicked` | `self.open_latest_training_model_output` | backend_result_review | TBD | TBD | TBD |
| 1058 | `self.btn_open_training_model_manifest.clicked` | `self.open_latest_training_model_manifest` | backend_result_review | TBD | TBD | TBD |
| 1062 | `self.btn_batch_predict_entry.clicked` | `self.enter_batch_prediction_from_training_result` | backend_result_review | TBD | TBD | TBD |
| 1066 | `self.model_library_combo.currentIndexChanged` | `self._on_model_library_selection_changed` | selection_lifecycle | TBD | TBD | TBD |
| 1079 | `self.btn_use_selected_tif_model.clicked` | `self.use_selected_tif_model` | backend_result_review | TBD | TBD | TBD |
| 1082 | `self.btn_save_tif_model_notes.clicked` | `self.save_selected_tif_model_notes` | annotation_save_truth | TBD | TBD | TBD |
| 1085 | `self.btn_delete_tif_model_record.clicked` | `self.delete_selected_tif_model_record` | backend_result_review | TBD | TBD | TBD |
| 1088 | `self.btn_import_external_prediction_tif.clicked` | `self.import_external_prediction_tif_dialog` | backend_result_review | TBD | TBD | TBD |
| 1096 | `self.result_region_combo.currentIndexChanged` | `self._on_result_comparison_controls_changed` | roi_to_part | TBD | TBD | TBD |
| 1097 | `self.result_source_manual_radio.toggled` | `self._on_result_comparison_controls_changed` | backend_result_review | TBD | TBD | TBD |
| 1098 | `self.result_source_editable_radio.toggled` | `self._on_result_comparison_controls_changed` | annotation_save_truth | TBD | TBD | TBD |
| 1109 | `self.btn_refresh_result_comparison.clicked` | `self.refresh_result_comparison` | backend_result_review | TBD | TBD | TBD |
| 1112 | `self.btn_open_result_comparison_target.clicked` | `self.open_selected_result_comparison_target` | backend_result_review | TBD | TBD | TBD |
| 1115 | `self.btn_show_result_region_in_3d.clicked` | `self.show_selected_result_region_in_3d` | roi_to_part | TBD | TBD | TBD |
| 1122 | `self.btn_export_current_rendering.clicked` | `self.export_current_rendering_screenshot` | volume_preview_render | TBD | TBD | TBD |
| 1125 | `self.btn_start_center.clicked` | `self.start_center_requested.emit` | shell_view_text | `TifWorkbenchShell._request_start_center` | Stage 1 completed | `test_shell_buttons_bind_once_and_emit_expected_commands` |
| 1128 | `self.btn_ask_agent.clicked` | `lambda : self.agent_requested.emit(self.get_agent_context())` | shell_view_text | `TifWorkbenchShell._request_agent` | Stage 1 completed | `test_shell_buttons_bind_once_and_emit_expected_commands` |
| 1131 | `self.btn_show_workbench_log.clicked` | `self.show_workbench_log` | shell_view_text | `TifWorkbenchShell` direct command | Stage 1 completed | `test_show_log_button_routes_directly_to_shell_command` |
| 1165 | `self.backend_elapsed_timer.timeout` | `self._update_backend_elapsed_label` | annotation_save_truth | TBD | TBD | TBD |
| 1172 | `self.shortcut_undo.activated` | `self.undo` | unclassified | TBD | TBD | TBD |
| 1174 | `self.shortcut_redo.activated` | `self.redo` | unclassified | TBD | TBD | TBD |
| 1176 | `self.shortcut_redo_alt.activated` | `self.redo` | unclassified | TBD | TBD | TBD |
| 1178 | `self.shortcut_save_edit.activated` | `self.save_working_edit_async` | annotation_save_truth | TBD | TBD | TBD |
| 1180 | `self.shortcut_tool_brush.activated` | `lambda : self.set_annotation_tool_mode('brush')` | annotation_save_truth | TBD | TBD | TBD |
| 1182 | `self.shortcut_tool_eraser.activated` | `lambda : self.set_annotation_tool_mode('eraser')` | annotation_save_truth | TBD | TBD | TBD |
| 1184 | `self.shortcut_tool_lasso.activated` | `lambda : self.set_annotation_tool_mode('lasso')` | annotation_save_truth | TBD | TBD | TBD |
| 1186 | `self.shortcut_tool_rectangle.activated` | `lambda : self.set_annotation_tool_mode('rectangle')` | annotation_save_truth | TBD | TBD | TBD |
| 1188 | `self.shortcut_tool_ellipse.activated` | `lambda : self.set_annotation_tool_mode('ellipse')` | annotation_save_truth | TBD | TBD | TBD |
| 1190 | `self.shortcut_tool_picker.activated` | `lambda : self.set_annotation_tool_mode('picker')` | annotation_save_truth | TBD | TBD | TBD |
| 1192 | `self.shortcut_brush_smaller.activated` | `lambda : self.adjust_brush_size(-1)` | annotation_save_truth | TBD | TBD | TBD |
| 1194 | `self.shortcut_brush_larger.activated` | `lambda : self.adjust_brush_size(1)` | annotation_save_truth | TBD | TBD | TBD |
| 1198 | `self.auto_save_timer.timeout` | `lambda : self.save_working_edit(show_message=True, reason='auto_save')` | annotation_save_truth | TBD | TBD | TBD |
| 1202 | `self.volume_still_timer.timeout` | `self._finish_volume_interaction` | volume_preview_render | TBD | TBD | TBD |
| 3225 | `slider.sliderPressed` | `self._start_volume_interaction` | volume_preview_render | TBD | TBD | TBD |
| 3226 | `slider.valueChanged` | `lambda _value, item=slider: self._on_volume_interaction_slider_changed(item)` | volume_preview_render | TBD | TBD | TBD |
| 3227 | `slider.sliderReleased` | `self.finish_volume_interaction_debounced` | volume_preview_render | TBD | TBD | TBD |
| 3503 | `canvas.render_failed` | `self._on_gpu_volume_failed` | volume_preview_render | TBD | TBD | TBD |
| 3505 | `canvas.render_info_changed` | `self._on_gpu_volume_info_changed` | volume_preview_render | TBD | TBD | TBD |
| 3507 | `canvas.render_stats_changed` | `self._on_gpu_volume_stats_changed` | volume_preview_render | TBD | TBD | TBD |
| 3917 | `thread.started` | `worker.run` | task_lifecycle | TBD | TBD | TBD |
| 3918 | `worker.finished` | `self._on_label_auto_save_finished` | annotation_save_truth | TBD | TBD | TBD |
| 3919 | `worker.failed` | `self._on_label_auto_save_failed` | annotation_save_truth | TBD | TBD | TBD |
| 3920 | `worker.finished` | `thread.quit` | task_lifecycle | TBD | TBD | TBD |
| 3921 | `worker.failed` | `thread.quit` | task_lifecycle | TBD | TBD | TBD |
| 3922 | `thread.finished` | `worker.deleteLater` | task_lifecycle | TBD | TBD | TBD |
| 3923 | `thread.finished` | `thread.deleteLater` | task_lifecycle | TBD | TBD | TBD |
| 4103 | `thread.started` | `worker.run` | task_lifecycle | TBD | TBD | TBD |
| 4104 | `worker.finished` | `self._on_label_manual_save_finished` | annotation_save_truth | TBD | TBD | TBD |
| 4105 | `worker.failed` | `self._on_label_manual_save_failed` | annotation_save_truth | TBD | TBD | TBD |
| 4106 | `worker.finished` | `thread.quit` | task_lifecycle | TBD | TBD | TBD |
| 4107 | `worker.failed` | `thread.quit` | task_lifecycle | TBD | TBD | TBD |
| 4108 | `thread.finished` | `worker.deleteLater` | task_lifecycle | TBD | TBD | TBD |
| 4109 | `thread.finished` | `thread.deleteLater` | task_lifecycle | TBD | TBD | TBD |
| 4548 | `dialog.destroyed` | `lambda _obj=None: setattr(self, '_tif_training_result_dialog', None)` | backend_result_review | TBD | TBD | TBD |
| 4916 | `self._tif_materialize_thread.started` | `self._tif_materialize_worker.run` | part_mask_material | TBD | TBD | TBD |
| 4917 | `self._tif_materialize_worker.progress` | `self._on_tif_materialize_progress` | part_mask_material | TBD | TBD | TBD |
| 4918 | `self._tif_materialize_worker.finished` | `self._on_tif_materialize_finished` | part_mask_material | TBD | TBD | TBD |
| 4919 | `self._tif_materialize_worker.failed` | `self._on_tif_materialize_failed` | part_mask_material | TBD | TBD | TBD |
| 4920 | `self._tif_materialize_worker.finished` | `self._tif_materialize_thread.quit` | part_mask_material | TBD | TBD | TBD |
| 4921 | `self._tif_materialize_worker.failed` | `self._tif_materialize_thread.quit` | part_mask_material | TBD | TBD | TBD |
| 4922 | `self._tif_materialize_thread.finished` | `self._tif_materialize_worker.deleteLater` | part_mask_material | TBD | TBD | TBD |
| 4923 | `self._tif_materialize_thread.finished` | `self._tif_materialize_thread.deleteLater` | part_mask_material | TBD | TBD | TBD |
| 5092 | `self._part_mask_preview_thread.started` | `self._part_mask_preview_worker.run` | part_mask_material | TBD | TBD | TBD |
| 5093 | `self._part_mask_preview_worker.progress` | `self._on_part_mask_preview_progress` | part_mask_material | TBD | TBD | TBD |
| 5094 | `self._part_mask_preview_worker.finished` | `self._on_part_mask_preview_finished` | part_mask_material | TBD | TBD | TBD |
| 5095 | `self._part_mask_preview_worker.failed` | `self._on_part_mask_preview_failed` | part_mask_material | TBD | TBD | TBD |
| 5096 | `self._part_mask_preview_worker.finished` | `self._part_mask_preview_thread.quit` | part_mask_material | TBD | TBD | TBD |
| 5097 | `self._part_mask_preview_worker.failed` | `self._part_mask_preview_thread.quit` | part_mask_material | TBD | TBD | TBD |
| 5098 | `self._part_mask_preview_thread.finished` | `self._part_mask_preview_worker.deleteLater` | part_mask_material | TBD | TBD | TBD |
| 5099 | `self._part_mask_preview_thread.finished` | `self._part_mask_preview_thread.deleteLater` | part_mask_material | TBD | TBD | TBD |
| 5202 | `self._confirm_part_roi_thread.started` | `self._confirm_part_roi_worker.run` | roi_to_part | TBD | TBD | TBD |
| 5203 | `self._confirm_part_roi_worker.progress` | `self._on_confirm_part_roi_progress` | roi_to_part | TBD | TBD | TBD |
| 5204 | `self._confirm_part_roi_worker.finished` | `self._on_confirm_part_roi_finished` | roi_to_part | TBD | TBD | TBD |
| 5205 | `self._confirm_part_roi_worker.failed` | `self._on_confirm_part_roi_failed` | roi_to_part | TBD | TBD | TBD |
| 5206 | `self._confirm_part_roi_worker.finished` | `self._confirm_part_roi_thread.quit` | roi_to_part | TBD | TBD | TBD |
| 5207 | `self._confirm_part_roi_worker.failed` | `self._confirm_part_roi_thread.quit` | roi_to_part | TBD | TBD | TBD |
| 5208 | `self._confirm_part_roi_thread.finished` | `self._confirm_part_roi_worker.deleteLater` | roi_to_part | TBD | TBD | TBD |
| 5209 | `self._confirm_part_roi_thread.finished` | `self._confirm_part_roi_thread.deleteLater` | roi_to_part | TBD | TBD | TBD |
| 5348 | `self._tif_import_thread.started` | `self._tif_import_worker.run` | task_lifecycle | TBD | TBD | TBD |
| 5349 | `self._tif_import_worker.progress` | `self._on_tif_import_progress` | task_lifecycle | TBD | TBD | TBD |
| 5350 | `self._tif_import_worker.finished` | `self._on_tif_import_finished` | import_export | TBD | TBD | TBD |
| 5352 | `self._tif_import_worker.failed` | `self._on_tif_import_failed` | import_export | TBD | TBD | TBD |
| 5353 | `self._tif_import_worker.finished` | `self._tif_import_thread.quit` | task_lifecycle | TBD | TBD | TBD |
| 5355 | `self._tif_import_worker.failed` | `self._tif_import_thread.quit` | task_lifecycle | TBD | TBD | TBD |
| 5356 | `self._tif_import_thread.finished` | `self._tif_import_worker.deleteLater` | task_lifecycle | TBD | TBD | TBD |
| 5357 | `self._tif_import_thread.finished` | `self._tif_import_thread.deleteLater` | task_lifecycle | TBD | TBD | TBD |
| 7752 | `self._tif_backend_thread.started` | `self._tif_backend_worker.run` | backend_result_review | TBD | TBD | TBD |
| 7753 | `self._tif_backend_worker.progress` | `self._on_tif_backend_progress` | backend_result_review | TBD | TBD | TBD |
| 7754 | `self._tif_backend_worker.finished` | `self._on_tif_backend_finished` | backend_result_review | TBD | TBD | TBD |
| 7755 | `self._tif_backend_worker.failed` | `self._on_tif_backend_failed` | backend_result_review | TBD | TBD | TBD |
| 7756 | `self._tif_backend_worker.finished` | `self._tif_backend_thread.quit` | backend_result_review | TBD | TBD | TBD |
| 7757 | `self._tif_backend_worker.failed` | `self._tif_backend_thread.quit` | backend_result_review | TBD | TBD | TBD |
| 7758 | `self._tif_backend_thread.finished` | `self._tif_backend_worker.deleteLater` | backend_result_review | TBD | TBD | TBD |
| 7759 | `self._tif_backend_thread.finished` | `self._on_tif_backend_thread_finished` | backend_result_review | TBD | TBD | TBD |
| 7760 | `self._tif_backend_thread.finished` | `self._tif_backend_thread.deleteLater` | backend_result_review | TBD | TBD | TBD |
| 7914 | `self.task_tabs.currentChanged` | `self._on_task_tab_changed` | task_lifecycle | TBD | TBD | TBD |
| 7915 | `self.training_mode_tabs.currentChanged` | `self._on_training_mode_tab_changed` | backend_result_review | TBD | TBD | TBD |
| 11972 | `thread.started` | `worker.run` | task_lifecycle | TBD | TBD | TBD |
| 11973 | `worker.progress` | `self._on_volume_preview_build_progress` | volume_preview_render | TBD | TBD | TBD |
| 11974 | `worker.finished` | `self._on_volume_preview_build_finished` | volume_preview_render | TBD | TBD | TBD |
| 11975 | `worker.failed` | `self._on_volume_preview_build_failed` | volume_preview_render | TBD | TBD | TBD |
| 11976 | `worker.finished` | `thread.quit` | task_lifecycle | TBD | TBD | TBD |
| 11977 | `worker.failed` | `thread.quit` | task_lifecycle | TBD | TBD | TBD |
| 11978 | `thread.finished` | `worker.deleteLater` | task_lifecycle | TBD | TBD | TBD |
| 11979 | `thread.finished` | `lambda t=thread, w=worker: self._cleanup_volume_preview_build_thread(t, w)` | volume_preview_render | TBD | TBD | TBD |
| 11980 | `thread.finished` | `thread.deleteLater` | task_lifecycle | TBD | TBD | TBD |
| 13783 | `thread.started` | `worker.run` | task_lifecycle | TBD | TBD | TBD |
| 13784 | `worker.finished` | `self._on_promote_working_edit_finished` | annotation_save_truth | TBD | TBD | TBD |
| 13785 | `worker.failed` | `self._on_promote_working_edit_failed` | annotation_save_truth | TBD | TBD | TBD |
| 13786 | `worker.finished` | `thread.quit` | task_lifecycle | TBD | TBD | TBD |
| 13787 | `worker.failed` | `thread.quit` | task_lifecycle | TBD | TBD | TBD |
| 13788 | `thread.finished` | `worker.deleteLater` | task_lifecycle | TBD | TBD | TBD |
| 13789 | `thread.finished` | `thread.deleteLater` | task_lifecycle | TBD | TBD | TBD |
| 14151 | `thread.started` | `worker.run` | task_lifecycle | TBD | TBD | TBD |
| 14152 | `worker.progress` | `self._on_local_axis_reslice_export_progress` | volume_preview_render | TBD | TBD | TBD |
| 14153 | `worker.finished` | `self._on_local_axis_reslice_export_finished` | volume_preview_render | TBD | TBD | TBD |
| 14154 | `worker.failed` | `self._on_local_axis_reslice_export_failed` | volume_preview_render | TBD | TBD | TBD |
| 14155 | `worker.finished` | `thread.quit` | task_lifecycle | TBD | TBD | TBD |
| 14156 | `worker.failed` | `thread.quit` | task_lifecycle | TBD | TBD | TBD |
| 14157 | `thread.finished` | `worker.deleteLater` | task_lifecycle | TBD | TBD | TBD |
| 14158 | `thread.finished` | `thread.deleteLater` | task_lifecycle | TBD | TBD | TBD |

## Stage 10 最终信号状态（2026-07-10）

Stage 0 表格保留为迁移前历史快照。最终候选的信号责任如下：

| Scope | 最终 owner | 连接方式 | 合同证据 | 状态 |
| --- | --- | --- | --- | --- |
| `shell` | `TifWorkbenchShell` | Signal Router | Shell 按钮单次绑定、命令直达、销毁解绑 | `verified` |
| `selection` | `TifSelectionWorkflowController` | Signal Router | 幂等绑定、选择 command、共享 context snapshot | `verified` |
| `annotation` | `TifAnnotationWorkflowController` | Signal Router | 工具按钮直达、保存 state 唯一、revision/stale 保护 | `verified` |
| `roi` | `TifRoiWorkflowController` | Signal Router | 幂等绑定、ROI draft/confirm 责任边界 | `verified` |
| `part_mask` | `TifPartMaskWorkflowController` | Signal Router | 16 条控件信号幂等、preview worker 取消与 stale token | `verified` |
| `volume_render` | `TifVolumeRenderController` | Signal Router + renderer 生命周期 | 完整 scope、GPU fallback、资源不足与 stale result | `verified` |
| `local_axis` | `TifLocalAxisController` | Signal Router | 幂等绑定、三点/roll、export stale context | `verified` |
| `backend_panel` | `TifBackendPanelController` | Signal Router + worker/thread 生命周期 | 21 条控件信号幂等、state 唯一、完成/失败/取消 | `verified` |
| `result_review` | `TifResultReviewController` | Signal Router | 9 条控件信号幂等、Selection command、truth promotion | `verified` |

- Signal Router 运行时启动烟测登记 129 条连接；重复 `bind_signals()` 不增加连接。
- 主文件只剩 11 处 `.connect()`，属于 GPU canvas 的 renderer 回调和 TIF 导入 worker/thread 生命周期；主文件不存在按钮 `clicked -> Widget wrapper` 空转链。
- controller 销毁/项目关闭由 Shell 生命周期统一解绑；后台结果继续通过 task/context/stale guard 阻止旧结果写入新目标。
- 67 条责任主体、信号、状态和 suite 登记合同测试通过；该阶段九组自动门快照为 698 条。新增 Stage 10 回归后当前最终门为 702 条。
