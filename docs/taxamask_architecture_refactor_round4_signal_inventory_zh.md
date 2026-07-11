# TaxaMask Round 4 Main Window Signal and Async Inventory

由 `scripts/analyze_main_window_architecture.py` 生成。目标 owner、解绑策略和 contract test 在对应 Stage 实施前填写。

## Qt Connections

| Line | Owner | Signal | Current target | Workflow | Stage | Target owner | Unbind | Contract test |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 556 | `MainWindow.__init__` | `self.project_save_timer.timeout` | `self._flush_pending_project_save` | shell_start_agent | 3 | TBD | TBD | TBD |
| 595 | `MainWindow.__init__` | `self.btn_export.clicked` | `self.export_dataset` | runtime_worker | 1 | TBD | TBD | TBD |
| 598 | `MainWindow.__init__` | `self.btn_crop.clicked` | `self.open_cropper` | shell_start_agent | 3 | TBD | TBD | TBD |
| 601 | `MainWindow.__init__` | `self.btn_batch_split_panels.clicked` | `self.batch_split_panel_images` | shell_start_agent | 3 | TBD | TBD | TBD |
| 604 | `MainWindow.__init__` | `self.btn_blink_entry.clicked` | `self.launch_blink_from_workbench` | blink | 6 | TBD | TBD | TBD |
| 608 | `MainWindow.__init__` | `self.btn_start_center_from_workbench.clicked` | `self.return_to_start_center_with_context` | shell_start_agent | 3 | TBD | TBD | TBD |
| 612 | `MainWindow.__init__` | `self.btn_agent_from_workbench.clicked` | `lambda : self.open_agent_from_context(self._collect_image_workbench_agent_context())` | shell_start_agent | 3 | TBD | TBD | TBD |
| 616 | `MainWindow.__init__` | `self.btn_vlm_preannotate_current.clicked` | `self.run_vlm_preannotation_current` | vlm_prediction_export | 7 | TBD | TBD | TBD |
| 620 | `MainWindow.__init__` | `self.btn_vlm_preannotate_batch.clicked` | `self.run_vlm_preannotation_batch` | vlm_prediction_export | 7 | TBD | TBD | TBD |
| 672 | `MainWindow.__init__` | `self.file_list.customContextMenuRequested` | `self.show_file_list_context_menu` | shell_start_agent | 3 | TBD | TBD | TBD |
| 673 | `MainWindow.__init__` | `self.file_list.itemClicked` | `self._handle_image_list_item_clicked` | shell_start_agent | 3 | TBD | TBD | TBD |
| 674 | `MainWindow.__init__` | `self.file_list.currentItemChanged` | `self.on_file_selected` | shell_start_agent | 3 | TBD | TBD | TBD |
| 675 | `MainWindow.__init__` | `self.file_list.imagesDroppedToGroup` | `self.move_images_to_group` | runtime_worker | 1 | TBD | TBD | TBD |
| 678 | `MainWindow.__init__` | `self.btn_add.clicked` | `self.add_images` | shell_start_agent | 3 | TBD | TBD | TBD |
| 698 | `MainWindow.__init__` | `self.radio_draw.toggled` | `self.on_tool_changed` | shell_start_agent | 3 | TBD | TBD | TBD |
| 703 | `MainWindow.__init__` | `self.radio_magic.toggled` | `self.on_tool_changed` | shell_start_agent | 3 | TBD | TBD | TBD |
| 708 | `MainWindow.__init__` | `self.radio_box.toggled` | `self.on_tool_changed` | shell_start_agent | 3 | TBD | TBD | TBD |
| 713 | `MainWindow.__init__` | `self.radio_annotation_box.toggled` | `self.on_tool_changed` | shell_start_agent | 3 | TBD | TBD | TBD |
| 718 | `MainWindow.__init__` | `self.radio_loose_shrink_box.toggled` | `self.on_tool_changed` | blink | 6 | TBD | TBD | TBD |
| 723 | `MainWindow.__init__` | `self.radio_scale.toggled` | `self.on_tool_changed` | shell_start_agent | 3 | TBD | TBD | TBD |
| 732 | `MainWindow.__init__` | `self.canvas.polygon_completed` | `self.on_polygon_completed` | shell_start_agent | 3 | TBD | TBD | TBD |
| 733 | `MainWindow.__init__` | `self.canvas.magic_wand_clicked` | `self.on_magic_wand_clicked` | shell_start_agent | 3 | TBD | TBD | TBD |
| 734 | `MainWindow.__init__` | `self.canvas.magic_box_completed` | `self.on_magic_box_completed` | shell_start_agent | 3 | TBD | TBD | TBD |
| 735 | `MainWindow.__init__` | `self.canvas.annotation_box_completed` | `self.on_annotation_box_completed` | shell_start_agent | 3 | TBD | TBD | TBD |
| 736 | `MainWindow.__init__` | `self.canvas.scale_defined` | `self.on_scale_defined` | shell_start_agent | 3 | TBD | TBD | TBD |
| 747 | `MainWindow.__init__` | `self.shortcut_undo.activated` | `self.canvas.undo` | shell_start_agent | 3 | TBD | TBD | TBD |
| 749 | `MainWindow.__init__` | `self.shortcut_redo.activated` | `self.canvas.redo` | shell_start_agent | 3 | TBD | TBD | TBD |
| 751 | `MainWindow.__init__` | `self.shortcut_save.activated` | `lambda : self._flush_pending_project_save(force=True)` | shell_start_agent | 3 | TBD | TBD | TBD |
| 753 | `MainWindow.__init__` | `self.shortcut_verify.activated` | `self.verify_current_image` | shell_start_agent | 3 | TBD | TBD | TBD |
| 778 | `MainWindow.__init__` | `self.genus_combo.currentTextChanged` | `self.on_genus_changed` | shell_start_agent | 3 | TBD | TBD | TBD |
| 787 | `MainWindow.__init__` | `self.part_list.currentItemChanged` | `self.on_part_selected` | shell_start_agent | 3 | TBD | TBD | TBD |
| 797 | `MainWindow.__init__` | `self.btn_add_part.clicked` | `self.add_taxonomy_part` | shell_start_agent | 3 | TBD | TBD | TBD |
| 800 | `MainWindow.__init__` | `self.btn_rename_part.clicked` | `self.rename_taxonomy_part` | shell_start_agent | 3 | TBD | TBD | TBD |
| 803 | `MainWindow.__init__` | `self.btn_del_part.clicked` | `self.remove_taxonomy_part` | shell_start_agent | 3 | TBD | TBD | TBD |
| 811 | `MainWindow.__init__` | `self.check_morpho.stateChanged` | `self.toggle_morphometrics` | shell_start_agent | 3 | TBD | TBD | TBD |
| 836 | `MainWindow.__init__` | `self.btn_literature_descriptions.clicked` | `self.open_literature_description_dialog` | dialog_settings | 2 | TBD | TBD | TBD |
| 886 | `MainWindow.__init__` | `self.combo_locator.activated` | `self.on_locator_changed` | shell_start_agent | 3 | TBD | TBD | TBD |
| 887 | `MainWindow.__init__` | `self.combo_locator.currentIndexChanged` | `self.update_model_delete_button_states` | shell_start_agent | 3 | TBD | TBD | TBD |
| 892 | `MainWindow.__init__` | `self.btn_del_locator.clicked` | `self.delete_locator_model` | shell_start_agent | 3 | TBD | TBD | TBD |
| 896 | `MainWindow.__init__` | `self.btn_note_locator.clicked` | `self.edit_locator_model_note` | shell_start_agent | 3 | TBD | TBD | TBD |
| 906 | `MainWindow.__init__` | `self.combo_segmenter.activated` | `self.on_segmenter_changed` | shell_start_agent | 3 | TBD | TBD | TBD |
| 907 | `MainWindow.__init__` | `self.combo_segmenter.currentIndexChanged` | `self.update_model_delete_button_states` | shell_start_agent | 3 | TBD | TBD | TBD |
| 912 | `MainWindow.__init__` | `self.btn_del_segmenter.clicked` | `self.delete_segmenter_model` | shell_start_agent | 3 | TBD | TBD | TBD |
| 916 | `MainWindow.__init__` | `self.btn_note_segmenter.clicked` | `self.edit_segmenter_model_note` | shell_start_agent | 3 | TBD | TBD | TBD |
| 931 | `MainWindow.__init__` | `self.btn_predict.clicked` | `self.run_prediction` | vlm_prediction_export | 7 | TBD | TBD | TBD |
| 935 | `MainWindow.__init__` | `self.btn_batch.clicked` | `self.run_batch_inference` | runtime_worker | 1 | TBD | TBD | TBD |
| 940 | `MainWindow.__init__` | `self.btn_accept_current_ai_drafts.clicked` | `self.accept_current_image_ai_drafts` | vlm_prediction_export | 7 | TBD | TBD | TBD |
| 944 | `MainWindow.__init__` | `self.btn_accept_batch_ai_drafts.clicked` | `self.accept_batch_ai_drafts` | vlm_prediction_export | 7 | TBD | TBD | TBD |
| 969 | `MainWindow.__init__` | `self.btn_train.clicked` | `self.run_training` | shell_start_agent | 3 | TBD | TBD | TBD |
| 974 | `MainWindow.__init__` | `self.btn_stop_training.clicked` | `self.stop_training` | shell_start_agent | 3 | TBD | TBD | TBD |
| 979 | `MainWindow.__init__` | `self.btn_clear_ai.clicked` | `self.clear_ai_labels` | shell_start_agent | 3 | TBD | TBD | TBD |
| 1001 | `MainWindow.__init__` | `self.combo_blink_parent_context.activated` | `self.on_blink_parent_context_changed` | blink | 6 | TBD | TBD | TBD |
| 1013 | `MainWindow.__init__` | `self.check_lock_parent_box_ratio.stateChanged` | `self._refresh_annotation_box_constraints` | shell_start_agent | 3 | TBD | TBD | TBD |
| 1016 | `MainWindow.__init__` | `self.btn_configure_route_expert.clicked` | `self.open_current_route_expert_settings` | blink | 6 | TBD | TBD | TBD |
| 1020 | `MainWindow.__init__` | `self.btn_blink_auto_annotate.clicked` | `self.run_blink_child_auto_annotate` | blink | 6 | TBD | TBD | TBD |
| 1027 | `MainWindow.__init__` | `self.btn_blink_auto_shrink.clicked` | `self.run_blink_auto_shrink` | blink | 6 | TBD | TBD | TBD |
| 1031 | `MainWindow.__init__` | `self.btn_blink_batch_auto_shrink.clicked` | `self.run_blink_batch_auto_shrink` | blink | 6 | TBD | TBD | TBD |
| 1039 | `MainWindow.__init__` | `self.btn_blink_train_expert.clicked` | `self.train_current_blink_expert` | blink | 6 | TBD | TBD | TBD |
| 1044 | `MainWindow.__init__` | `self.btn_blink_stop_training.clicked` | `self.stop_current_blink_expert_training` | blink | 6 | TBD | TBD | TBD |
| 1065 | `MainWindow.__init__` | `self.btn_training_results.clicked` | `self.open_training_results_browser` | shell_start_agent | 3 | TBD | TBD | TBD |
| 1105 | `MainWindow.__init__` | `self.pdf_widget.start_center_requested` | `self.return_to_start_center_with_context` | shell_start_agent | 3 | TBD | TBD | TBD |
| 1106 | `MainWindow.__init__` | `self.pdf_widget.agent_requested` | `self.open_agent_from_context` | shell_start_agent | 3 | TBD | TBD | TBD |
| 1108 | `MainWindow.__init__` | `self.tif_workbench.start_center_requested` | `self.return_to_start_center_with_context` | shell_start_agent | 3 | TBD | TBD | TBD |
| 1109 | `MainWindow.__init__` | `self.tif_workbench.agent_requested` | `self.open_agent_from_context` | shell_start_agent | 3 | TBD | TBD | TBD |
| 1123 | `MainWindow.__init__` | `self.blink_lab.start_center_requested` | `self.return_to_start_center_with_context` | blink | 6 | TBD | TBD | TBD |
| 1124 | `MainWindow.__init__` | `self.blink_lab.agent_requested` | `self.open_agent_from_context` | blink | 6 | TBD | TBD | TBD |
| 1125 | `MainWindow.__init__` | `self.blink_lab.global_labels_updated` | `self.on_global_labels_updated` | blink | 6 | TBD | TBD | TBD |
| 1126 | `MainWindow.__init__` | `self.blink_lab.route_registry_refresh_requested` | `self.refresh_route_table` | blink | 6 | TBD | TBD | TBD |
| 1205 | `MainWindow._build_start_center` | `self.agent_panel.status_changed` | `self._handle_agent_dashboard_status_changed` | shell_start_agent | 3 | TBD | TBD | TBD |
| 1241 | `MainWindow._build_start_center` | `self.btn_start_ant_code.clicked` | `self.agent_panel.start_dashboard` | shell_start_agent | 3 | TBD | TBD | TBD |
| 1244 | `MainWindow._build_start_center` | `self.btn_stop_ant_code.clicked` | `self.agent_panel.stop_dashboard` | shell_start_agent | 3 | TBD | TBD | TBD |
| 1328 | `MainWindow._build_start_quick_panel` | `self.btn_continue_last.clicked` | `self.open_last_project` | shell_start_agent | 3 | TBD | TBD | TBD |
| 1331 | `MainWindow._build_start_quick_panel` | `self.btn_open_any.clicked` | `self.open_project` | shell_start_agent | 3 | TBD | TBD | TBD |
| 1334 | `MainWindow._build_start_quick_panel` | `self.btn_general_settings.clicked` | `self.open_general_settings` | dialog_settings | 2 | TBD | TBD | TBD |
| 1369 | `MainWindow._build_project_console` | `self.btn_start_console_toggle.clicked` | `self._toggle_start_project_console` | shell_start_agent | 3 | TBD | TBD | TBD |
| 1469 | `MainWindow._build_workflow_card` | `enter_button.clicked` | `enter_callback` | shell_start_agent | 3 | TBD | TBD | TBD |
| 1473 | `MainWindow._build_workflow_card` | `create_button.clicked` | `create_callback` | shell_start_agent | 3 | TBD | TBD | TBD |
| 3053 | `MainWindow._connect_child_training_progress` | `thread.progress_signal` | `lambda value: self._set_training_progress('child', None, value)` | runtime_worker | 1 | TBD | TBD | TBD |
| 3054 | `MainWindow._connect_child_training_progress` | `thread.result_signal` | `self._on_child_training_result` | runtime_worker | 1 | TBD | TBD | TBD |
| 3055 | `MainWindow._connect_child_training_progress` | `thread.error_signal` | `self._on_child_training_error` | runtime_worker | 1 | TBD | TBD | TBD |
| 3056 | `MainWindow._connect_child_training_progress` | `thread.cancelled_signal` | `self._on_child_training_cancelled` | runtime_worker | 1 | TBD | TBD | TBD |
| 3057 | `MainWindow._connect_child_training_progress` | `thread.finished` | `self._on_child_training_finished` | runtime_worker | 1 | TBD | TBD | TBD |
| 3161 | `MainWindow._launch_training_with_preflight` | `self.trainer.log_signal` | `self.log` | dialog_settings | 2 | TBD | TBD | TBD |
| 3162 | `MainWindow._launch_training_with_preflight` | `self.trainer.progress_signal` | `lambda value: self._set_training_progress('parent', None, value)` | dialog_settings | 2 | TBD | TBD | TBD |
| 3163 | `MainWindow._launch_training_with_preflight` | `self.trainer.report_signal` | `self.show_training_report` | dialog_settings | 2 | TBD | TBD | TBD |
| 3164 | `MainWindow._launch_training_with_preflight` | `self.trainer.success_signal` | `self._on_training_success` | dialog_settings | 2 | TBD | TBD | TBD |
| 3165 | `MainWindow._launch_training_with_preflight` | `self.trainer.error_signal` | `self._on_training_error` | dialog_settings | 2 | TBD | TBD | TBD |
| 3166 | `MainWindow._launch_training_with_preflight` | `self.trainer.finished_signal` | `self._on_training_finished` | dialog_settings | 2 | TBD | TBD | TBD |
| 4594 | `MainWindow._choose_clear_ai_scope` | `scope_combo.currentIndexChanged` | `lambda _index: refresh_summary()` | shell_start_agent | 3 | TBD | TBD | TBD |
| 4595 | `MainWindow._choose_clear_ai_scope` | `clear_button.clicked` | `accept_scope` | shell_start_agent | 3 | TBD | TBD | TBD |
| 4596 | `MainWindow._choose_clear_ai_scope` | `cancel_button.clicked` | `dialog.reject` | dialog_settings | 2 | TBD | TBD | TBD |
| 5045 | `MainWindow.open_general_settings` | `dlg.agent_requested` | `self.open_agent_from_context` | dialog_settings | 2 | TBD | TBD | TBD |
| 5125 | `MainWindow.open_stl_model_settings` | `dlg.agent_requested` | `self.open_agent_from_context` | dialog_settings | 2 | TBD | TBD | TBD |
| 5227 | `MainWindow.open_tif_model_settings` | `dlg.agent_requested` | `self.open_agent_from_context` | dialog_settings | 2 | TBD | TBD | TBD |
| 5449 | `MainWindow._start_image_import` | `thread.progress_signal` | `on_progress` | runtime_worker | 1 | TBD | TBD | TBD |
| 5450 | `MainWindow._start_image_import` | `thread.success_signal` | `on_success` | runtime_worker | 1 | TBD | TBD | TBD |
| 5451 | `MainWindow._start_image_import` | `thread.error_signal` | `on_error` | runtime_worker | 1 | TBD | TBD | TBD |
| 5452 | `MainWindow._start_image_import` | `thread.finished_signal` | `on_finished` | runtime_worker | 1 | TBD | TBD | TBD |
| 8011 | `MainWindow.run_external_training` | `thread.log_signal` | `self.log` | runtime_worker | 1 | TBD | TBD | TBD |
| 8012 | `MainWindow.run_external_training` | `thread.success_signal` | `on_success` | runtime_worker | 1 | TBD | TBD | TBD |
| 8013 | `MainWindow.run_external_training` | `thread.error_signal` | `on_error` | runtime_worker | 1 | TBD | TBD | TBD |
| 8014 | `MainWindow.run_external_training` | `thread.finished_signal` | `on_finished` | runtime_worker | 1 | TBD | TBD | TBD |
| 8887 | `MainWindow._start_next_vlm_preannotation_image` | `thread.log_signal` | `self.log` | runtime_worker | 1 | TBD | TBD | TBD |
| 8888 | `MainWindow._start_next_vlm_preannotation_image` | `thread.image_result_signal` | `self._on_vlm_preannotation_image_result` | runtime_worker | 1 | TBD | TBD | TBD |
| 8889 | `MainWindow._start_next_vlm_preannotation_image` | `thread.progress_signal` | `lambda completed, total, step_name, worker=thread: self._on_vlm_preannotation_thread_step(worker, completed, total, step_name)` | runtime_worker | 1 | TBD | TBD | TBD |
| 8890 | `MainWindow._start_next_vlm_preannotation_image` | `thread.error_signal` | `self._on_vlm_preannotation_error` | runtime_worker | 1 | TBD | TBD | TBD |
| 8893 | `MainWindow._start_next_vlm_preannotation_image` | `native_finished` | `lambda worker=thread: self._on_vlm_preannotation_qthread_finished(worker)` | runtime_worker | 1 | TBD | TBD | TBD |
| 8895 | `MainWindow._start_next_vlm_preannotation_image` | `thread.finished_signal` | `lambda worker=thread: self._on_vlm_preannotation_qthread_finished(worker)` | runtime_worker | 1 | TBD | TBD | TBD |
| 9196 | `MainWindow._create_vlm_progress_dialog` | `stop_button.clicked` | `lambda : self.request_stop_vlm_preannotation(confirm=True)` | vlm_prediction_export | 7 | TBD | TBD | TBD |
| 9711 | `MainWindow._start_external_batch_inference` | `thread.log_signal` | `self.log` | runtime_worker | 1 | TBD | TBD | TBD |
| 9712 | `MainWindow._start_external_batch_inference` | `thread.progress_signal` | `on_progress` | runtime_worker | 1 | TBD | TBD | TBD |
| 9713 | `MainWindow._start_external_batch_inference` | `thread.result_signal` | `on_result` | runtime_worker | 1 | TBD | TBD | TBD |
| 9714 | `MainWindow._start_external_batch_inference` | `thread.error_signal` | `on_error` | runtime_worker | 1 | TBD | TBD | TBD |
| 9715 | `MainWindow._start_external_batch_inference` | `thread.finished_signal` | `on_finished` | runtime_worker | 1 | TBD | TBD | TBD |
| 9766 | `MainWindow.run_batch_inference` | `self.inf_thread.log_signal` | `self.log` | runtime_worker | 1 | TBD | TBD | TBD |
| 9781 | `MainWindow.run_batch_inference` | `self.inf_thread.result_signal` | `on_batch_res` | runtime_worker | 1 | TBD | TBD | TBD |
| 9782 | `MainWindow.run_batch_inference` | `self.inf_thread.finished_signal` | `lambda : [self.project.save_project(), self.btn_batch.setEnabled(True), self.btn_predict.setEnabled(True), self.refresh_file_list(), self._refresh_blink_refine_state()]` | runtime_worker | 1 | TBD | TBD | TBD |
| 9872 | `MainWindow._start_dataset_export` | `thread.progress_signal` | `on_progress` | runtime_worker | 1 | TBD | TBD | TBD |
| 9873 | `MainWindow._start_dataset_export` | `thread.success_signal` | `on_success` | runtime_worker | 1 | TBD | TBD | TBD |
| 9874 | `MainWindow._start_dataset_export` | `thread.error_signal` | `on_error` | runtime_worker | 1 | TBD | TBD | TBD |
| 9875 | `MainWindow._start_dataset_export` | `thread.finished_signal` | `on_finished` | runtime_worker | 1 | TBD | TBD | TBD |
| 9889 | `MainWindow.init_sam` | `self.sam_thread.started` | `self.sam_worker.load_model` | runtime_worker | 1 | TBD | TBD | TBD |
| 9892 | `MainWindow.init_sam` | `self.sam_point_requested` | `self.sam_worker.predict_point` | runtime_worker | 1 | TBD | TBD | TBD |
| 9894 | `MainWindow.init_sam` | `self.sam_box_requested` | `self.sam_worker.predict_box` | runtime_worker | 1 | TBD | TBD | TBD |
| 9895 | `MainWindow.init_sam` | `self.sam_worker.mask_generated` | `self.on_sam_mask_generated` | runtime_worker | 1 | TBD | TBD | TBD |
| 9897 | `MainWindow.init_sam` | `self.sam_worker.prompt_failed` | `self.on_sam_prompt_failed` | runtime_worker | 1 | TBD | TBD | TBD |
| 9898 | `MainWindow.init_sam` | `self.sam_worker.model_loaded` | `self._on_sam_model_loaded` | runtime_worker | 1 | TBD | TBD | TBD |
| 9899 | `MainWindow.init_sam` | `self.sam_worker.model_load_error` | `lambda message: self.log(str(message))` | runtime_worker | 1 | TBD | TBD | TBD |

## Thread Timer and Async Entries

| Line | Kind | Owner | Call | Workflow | Stage | Cancel/cleanup | Context guard |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2298 | thread_start | `MainWindow._schedule_project_save` | `self.project_save_timer.start` | shell_start_agent | 3 | TBD | TBD |
| 2304 | thread_start | `MainWindow._defer_project_save_for_active_navigation` | `self.project_save_timer.start` | shell_start_agent | 3 | TBD | TBD |
| 2325 | thread_start | `MainWindow._flush_pending_project_save` | `self.project_save_timer.start` | shell_start_agent | 3 | TBD | TBD |
| 2587 | single_shot | `MainWindow._preload_2d_stl_models_after_open` | `QTimer.singleShot` | shell_start_agent | 3 | TBD | TBD |
| 3171 | thread_start | `MainWindow._launch_training_with_preflight` | `self.trainer.start` | dialog_settings | 2 | TBD | TBD |
| 3225 | single_shot | `MainWindow._on_training_error` | `QTimer.singleShot` | shell_start_agent | 3 | TBD | TBD |
| 5453 | thread_start | `MainWindow._start_image_import` | `thread.start` | runtime_worker | 1 | TBD | TBD |
| 8015 | thread_start | `MainWindow.run_external_training` | `thread.start` | runtime_worker | 1 | TBD | TBD |
| 8896 | thread_start | `MainWindow._start_next_vlm_preannotation_image` | `thread.start` | runtime_worker | 1 | TBD | TBD |
| 9716 | thread_start | `MainWindow._start_external_batch_inference` | `thread.start` | runtime_worker | 1 | TBD | TBD |
| 9791 | thread_start | `MainWindow.run_batch_inference` | `self.inf_thread.start` | runtime_worker | 1 | TBD | TBD |
| 9876 | thread_start | `MainWindow._start_dataset_export` | `thread.start` | runtime_worker | 1 | TBD | TBD |
| 9885 | QThread | `MainWindow.init_sam` | `QThread` | runtime_worker | 1 | TBD | TBD |
| 9900 | thread_start | `MainWindow.init_sam` | `self.sam_thread.start` | runtime_worker | 1 | TBD | TBD |
| 9954 | python_thread | `MainWindow._preload_engine_parts_model_async` | `threading.Thread` | runtime_worker | 1 | TBD | TBD |
| 9959 | thread_start | `MainWindow._preload_engine_parts_model_async` | `self.parts_model_preload_thread.start` | runtime_worker | 1 | TBD | TBD |
