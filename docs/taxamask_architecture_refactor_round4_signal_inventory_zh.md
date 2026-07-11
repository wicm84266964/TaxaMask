# TaxaMask Round 4 Main Window Signal and Async Inventory

由 `scripts/analyze_main_window_architecture.py` 生成。目标 owner、解绑策略和 contract test 在对应 Stage 实施前填写。

## Qt Connections

| Line | Owner | Signal | Current target | Workflow | Stage | Target owner | Unbind | Contract test |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1619 | `TrainingPreflightDialog.__init__` | `buttons.accepted` | `self._accept_training` | dialog_settings | 2 | TBD | TBD | TBD |
| 1620 | `TrainingPreflightDialog.__init__` | `buttons.rejected` | `self.reject` | dialog_settings | 2 | TBD | TBD | TBD |
| 1803 | `TrainingReportDialog.__init__` | `self.slider_pct.valueChanged` | `lambda v: self.lbl_pct.setText(f'{v}%')` | dialog_settings | 2 | TBD | TBD | TBD |
| 1811 | `TrainingReportDialog.__init__` | `self.validation_filter.currentIndexChanged` | `self.load_gallery` | dialog_settings | 2 | TBD | TBD | TBD |
| 1815 | `TrainingReportDialog.__init__` | `btn_load.clicked` | `self.load_gallery` | dialog_settings | 2 | TBD | TBD | TBD |
| 1852 | `TrainingReportDialog.__init__` | `self.validation_index_table.itemSelectionChanged` | `self._load_selected_detail_preview` | dialog_settings | 2 | TBD | TBD | TBD |
| 1871 | `TrainingReportDialog.__init__` | `btn_open.clicked` | `self.open_folder` | dialog_settings | 2 | TBD | TBD | TBD |
| 1873 | `TrainingReportDialog.__init__` | `btn_close.clicked` | `self.accept` | dialog_settings | 2 | TBD | TBD | TBD |
| 2089 | `TrainingResultBrowserDialog.__init__` | `self.table.itemSelectionChanged` | `self._refresh_actions` | dialog_settings | 2 | TBD | TBD | TBD |
| 2090 | `TrainingResultBrowserDialog.__init__` | `self.table.doubleClicked` | `lambda _index=None: self.preview_selected()` | dialog_settings | 2 | TBD | TBD | TBD |
| 2095 | `TrainingResultBrowserDialog.__init__` | `self.btn_preview.clicked` | `self.preview_selected` | dialog_settings | 2 | TBD | TBD | TBD |
| 2100 | `TrainingResultBrowserDialog.__init__` | `self.btn_open_folder.clicked` | `self.open_selected_folder` | dialog_settings | 2 | TBD | TBD | TBD |
| 2105 | `TrainingResultBrowserDialog.__init__` | `self.btn_refresh.clicked` | `self.refresh_reports` | dialog_settings | 2 | TBD | TBD | TBD |
| 2114 | `TrainingResultBrowserDialog.__init__` | `buttons.rejected` | `self.reject` | dialog_settings | 2 | TBD | TBD | TBD |
| 2216 | `RouteManagementPanel.init_ui` | `self.route_tree.itemSelectionChanged` | `self.update_action_buttons` | dialog_settings | 2 | TBD | TBD | TBD |
| 2223 | `RouteManagementPanel.init_ui` | `self.btn_refresh_routes.clicked` | `self.refresh_route_table` | dialog_settings | 2 | TBD | TBD | TBD |
| 2228 | `RouteManagementPanel.init_ui` | `self.btn_appoint_route_expert.clicked` | `self.appoint_selected_route_expert` | blink | 6 | TBD | TBD | TBD |
| 2233 | `RouteManagementPanel.init_ui` | `self.btn_toggle_route.clicked` | `self.toggle_selected_route_enabled` | dialog_settings | 2 | TBD | TBD | TBD |
| 2238 | `RouteManagementPanel.init_ui` | `self.btn_delete_route.clicked` | `self.delete_selected_route` | dialog_settings | 2 | TBD | TBD | TBD |
| 2243 | `RouteManagementPanel.init_ui` | `self.btn_edit_expert_note.clicked` | `self.edit_selected_expert_note` | blink | 6 | TBD | TBD | TBD |
| 2248 | `RouteManagementPanel.init_ui` | `self.btn_delete_expert_file.clicked` | `self.delete_selected_expert_file` | blink | 6 | TBD | TBD | TBD |
| 2946 | `ModelSettingsDialog.__init__` | `self.combo_model_profile.currentIndexChanged` | `self._load_selected_profile_fields` | dialog_settings | 2 | TBD | TBD | TBD |
| 2947 | `ModelSettingsDialog.__init__` | `self.profile_name_edit.textChanged` | `self._update_current_profile_metadata` | dialog_settings | 2 | TBD | TBD | TBD |
| 2948 | `ModelSettingsDialog.__init__` | `self.profile_description_edit.textChanged` | `self._update_current_profile_metadata` | dialog_settings | 2 | TBD | TBD | TBD |
| 2949 | `ModelSettingsDialog.__init__` | `self.btn_new_profile.clicked` | `self.new_model_profile` | dialog_settings | 2 | TBD | TBD | TBD |
| 2950 | `ModelSettingsDialog.__init__` | `self.btn_copy_profile.clicked` | `self.copy_model_profile` | dialog_settings | 2 | TBD | TBD | TBD |
| 2951 | `ModelSettingsDialog.__init__` | `self.btn_delete_profile.clicked` | `self.delete_model_profile` | dialog_settings | 2 | TBD | TBD | TBD |
| 2952 | `ModelSettingsDialog.__init__` | `self.btn_set_active_profile.clicked` | `self.set_selected_profile_active` | dialog_settings | 2 | TBD | TBD | TBD |
| 3019 | `ModelSettingsDialog.__init__` | `self.parent_backend_combo.currentIndexChanged` | `self._sync_legacy_backend_combo_from_parent_backend` | dialog_settings | 2 | TBD | TBD | TBD |
| 3020 | `ModelSettingsDialog.__init__` | `self.parent_backend_combo.currentIndexChanged` | `lambda _index: self._refresh_model_source_summaries()` | dialog_settings | 2 | TBD | TBD | TBD |
| 3038 | `ModelSettingsDialog.__init__` | `self.child_backend_combo.currentIndexChanged` | `lambda _index: self._refresh_model_source_summaries()` | blink | 6 | TBD | TBD | TBD |
| 3115 | `ModelSettingsDialog.__init__` | `btn_validate_external.clicked` | `self.validate_external_backend` | dialog_settings | 2 | TBD | TBD | TBD |
| 3280 | `ModelSettingsDialog.__init__` | `self.combo_blink_training_strategy.currentIndexChanged` | `self._update_blink_training_strategy_note` | blink | 6 | TBD | TBD | TBD |
| 3356 | `ModelSettingsDialog.__init__` | `self.blink_dataset_tree.itemSelectionChanged` | `self._refresh_blink_dataset_actions` | blink | 6 | TBD | TBD | TBD |
| 3365 | `ModelSettingsDialog.__init__` | `self.btn_blink_dataset_details.clicked` | `self._show_blink_dataset_details` | blink | 6 | TBD | TBD | TBD |
| 3369 | `ModelSettingsDialog.__init__` | `self.btn_blink_dataset_delete.clicked` | `self._delete_selected_blink_dataset` | blink | 6 | TBD | TBD | TBD |
| 3444 | `ModelSettingsDialog.__init__` | `btn_validate_external_blink.clicked` | `self.validate_external_blink_backend` | blink | 6 | TBD | TBD | TBD |
| 3517 | `ModelSettingsDialog.__init__` | `self.btn_vlm_detail_toggle.toggled` | `self._toggle_vlm_details` | vlm_prediction_export | 7 | TBD | TBD | TBD |
| 3570 | `ModelSettingsDialog.__init__` | `self.combo_vlm_prompt_profile.currentIndexChanged` | `lambda _index: self._refresh_vlm_prompt_profile_editors()` | vlm_prediction_export | 7 | TBD | TBD | TBD |
| 3631 | `ModelSettingsDialog.__init__` | `btn_ask_agent.clicked` | `self.request_agent_help` | dialog_settings | 2 | TBD | TBD | TBD |
| 3634 | `ModelSettingsDialog.__init__` | `btn_save.clicked` | `self.accept_with_validation` | dialog_settings | 2 | TBD | TBD | TBD |
| 3637 | `ModelSettingsDialog.__init__` | `btn_cancel.clicked` | `self.reject` | dialog_settings | 2 | TBD | TBD | TBD |
| 3894 | `ModelSettingsDialog._show_blink_dataset_details` | `buttons.accepted` | `dialog.accept` | blink | 6 | TBD | TBD | TBD |
| 5065 | `GeneralSettingsDialog.__init__` | `btn_ask_agent.clicked` | `self.request_agent_help` | dialog_settings | 2 | TBD | TBD | TBD |
| 5068 | `GeneralSettingsDialog.__init__` | `btn_save.clicked` | `self.accept_with_validation` | dialog_settings | 2 | TBD | TBD | TBD |
| 5071 | `GeneralSettingsDialog.__init__` | `btn_cancel.clicked` | `self.reject` | dialog_settings | 2 | TBD | TBD | TBD |
| 5213 | `TifModelSettingsDialog.__init__` | `btn_validate.clicked` | `self.validate_backend` | dialog_settings | 2 | TBD | TBD | TBD |
| 5220 | `TifModelSettingsDialog.__init__` | `btn_nnunet_preset.clicked` | `self.apply_nnunet_v2_preset` | dialog_settings | 2 | TBD | TBD | TBD |
| 5239 | `TifModelSettingsDialog.__init__` | `btn_ask_agent.clicked` | `self.request_agent_help` | dialog_settings | 2 | TBD | TBD | TBD |
| 5242 | `TifModelSettingsDialog.__init__` | `btn_save.clicked` | `self.accept_with_validation` | dialog_settings | 2 | TBD | TBD | TBD |
| 5245 | `TifModelSettingsDialog.__init__` | `btn_cancel.clicked` | `self.reject` | dialog_settings | 2 | TBD | TBD | TBD |
| 5401 | `ExportDialog.__init__` | `btn_browse.clicked` | `self.browse` | runtime_worker | 1 | TBD | TBD | TBD |
| 5407 | `ExportDialog.__init__` | `btn_ok.clicked` | `self.accept` | runtime_worker | 1 | TBD | TBD | TBD |
| 5410 | `ExportDialog.__init__` | `btn_cancel.clicked` | `self.reject` | runtime_worker | 1 | TBD | TBD | TBD |
| 5478 | `BlinkEntryDialog.__init__` | `buttons.accepted` | `self.accept` | blink | 6 | TBD | TBD | TBD |
| 5479 | `BlinkEntryDialog.__init__` | `buttons.rejected` | `self.reject` | blink | 6 | TBD | TBD | TBD |
| 5483 | `BlinkEntryDialog.__init__` | `self.target_combo.currentIndexChanged` | `self._sync_preferred_roi` | blink | 6 | TBD | TBD | TBD |
| 5566 | `LiteratureDescriptionDialog.__init__` | `self.btn_search.clicked` | `self.refresh_records` | dialog_settings | 2 | TBD | TBD | TBD |
| 5575 | `LiteratureDescriptionDialog.__init__` | `self.raw_scope_combo.currentIndexChanged` | `self.refresh_raw_records` | dialog_settings | 2 | TBD | TBD | TBD |
| 5604 | `LiteratureDescriptionDialog.__init__` | `self.table.itemSelectionChanged` | `self._on_selection_changed` | dialog_settings | 2 | TBD | TBD | TBD |
| 5628 | `LiteratureDescriptionDialog.__init__` | `self.raw_table.itemSelectionChanged` | `self._on_raw_selection_changed` | dialog_settings | 2 | TBD | TBD | TBD |
| 5630 | `LiteratureDescriptionDialog.__init__` | `self.result_tabs.currentChanged` | `self._on_result_tab_changed` | dialog_settings | 2 | TBD | TBD | TBD |
| 5641 | `LiteratureDescriptionDialog.__init__` | `self.btn_replace.clicked` | `self.accept_replace` | dialog_settings | 2 | TBD | TBD | TBD |
| 5643 | `LiteratureDescriptionDialog.__init__` | `self.btn_append.clicked` | `self.accept_append` | dialog_settings | 2 | TBD | TBD | TBD |
| 5645 | `LiteratureDescriptionDialog.__init__` | `self.btn_close.clicked` | `self.reject` | dialog_settings | 2 | TBD | TBD | TBD |
| 5652 | `LiteratureDescriptionDialog.__init__` | `self.search_edit.returnPressed` | `self.refresh_records` | dialog_settings | 2 | TBD | TBD | TBD |
| 5960 | `MainWindow.__init__` | `self.project_save_timer.timeout` | `self._flush_pending_project_save` | shell_start_agent | 3 | TBD | TBD | TBD |
| 5999 | `MainWindow.__init__` | `self.btn_export.clicked` | `self.export_dataset` | runtime_worker | 1 | TBD | TBD | TBD |
| 6002 | `MainWindow.__init__` | `self.btn_crop.clicked` | `self.open_cropper` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6005 | `MainWindow.__init__` | `self.btn_batch_split_panels.clicked` | `self.batch_split_panel_images` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6008 | `MainWindow.__init__` | `self.btn_blink_entry.clicked` | `self.launch_blink_from_workbench` | blink | 6 | TBD | TBD | TBD |
| 6012 | `MainWindow.__init__` | `self.btn_start_center_from_workbench.clicked` | `self.return_to_start_center_with_context` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6016 | `MainWindow.__init__` | `self.btn_agent_from_workbench.clicked` | `lambda : self.open_agent_from_context(self._collect_image_workbench_agent_context())` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6020 | `MainWindow.__init__` | `self.btn_vlm_preannotate_current.clicked` | `self.run_vlm_preannotation_current` | vlm_prediction_export | 7 | TBD | TBD | TBD |
| 6024 | `MainWindow.__init__` | `self.btn_vlm_preannotate_batch.clicked` | `self.run_vlm_preannotation_batch` | vlm_prediction_export | 7 | TBD | TBD | TBD |
| 6076 | `MainWindow.__init__` | `self.file_list.customContextMenuRequested` | `self.show_file_list_context_menu` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6077 | `MainWindow.__init__` | `self.file_list.itemClicked` | `self._handle_image_list_item_clicked` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6078 | `MainWindow.__init__` | `self.file_list.currentItemChanged` | `self.on_file_selected` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6079 | `MainWindow.__init__` | `self.file_list.imagesDroppedToGroup` | `self.move_images_to_group` | runtime_worker | 1 | TBD | TBD | TBD |
| 6082 | `MainWindow.__init__` | `self.btn_add.clicked` | `self.add_images` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6102 | `MainWindow.__init__` | `self.radio_draw.toggled` | `self.on_tool_changed` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6107 | `MainWindow.__init__` | `self.radio_magic.toggled` | `self.on_tool_changed` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6112 | `MainWindow.__init__` | `self.radio_box.toggled` | `self.on_tool_changed` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6117 | `MainWindow.__init__` | `self.radio_annotation_box.toggled` | `self.on_tool_changed` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6122 | `MainWindow.__init__` | `self.radio_loose_shrink_box.toggled` | `self.on_tool_changed` | blink | 6 | TBD | TBD | TBD |
| 6127 | `MainWindow.__init__` | `self.radio_scale.toggled` | `self.on_tool_changed` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6136 | `MainWindow.__init__` | `self.canvas.polygon_completed` | `self.on_polygon_completed` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6137 | `MainWindow.__init__` | `self.canvas.magic_wand_clicked` | `self.on_magic_wand_clicked` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6138 | `MainWindow.__init__` | `self.canvas.magic_box_completed` | `self.on_magic_box_completed` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6139 | `MainWindow.__init__` | `self.canvas.annotation_box_completed` | `self.on_annotation_box_completed` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6140 | `MainWindow.__init__` | `self.canvas.scale_defined` | `self.on_scale_defined` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6151 | `MainWindow.__init__` | `self.shortcut_undo.activated` | `self.canvas.undo` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6153 | `MainWindow.__init__` | `self.shortcut_redo.activated` | `self.canvas.redo` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6155 | `MainWindow.__init__` | `self.shortcut_save.activated` | `lambda : self._flush_pending_project_save(force=True)` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6157 | `MainWindow.__init__` | `self.shortcut_verify.activated` | `self.verify_current_image` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6182 | `MainWindow.__init__` | `self.genus_combo.currentTextChanged` | `self.on_genus_changed` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6191 | `MainWindow.__init__` | `self.part_list.currentItemChanged` | `self.on_part_selected` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6201 | `MainWindow.__init__` | `self.btn_add_part.clicked` | `self.add_taxonomy_part` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6204 | `MainWindow.__init__` | `self.btn_rename_part.clicked` | `self.rename_taxonomy_part` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6207 | `MainWindow.__init__` | `self.btn_del_part.clicked` | `self.remove_taxonomy_part` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6215 | `MainWindow.__init__` | `self.check_morpho.stateChanged` | `self.toggle_morphometrics` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6240 | `MainWindow.__init__` | `self.btn_literature_descriptions.clicked` | `self.open_literature_description_dialog` | dialog_settings | 2 | TBD | TBD | TBD |
| 6290 | `MainWindow.__init__` | `self.combo_locator.activated` | `self.on_locator_changed` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6291 | `MainWindow.__init__` | `self.combo_locator.currentIndexChanged` | `self.update_model_delete_button_states` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6296 | `MainWindow.__init__` | `self.btn_del_locator.clicked` | `self.delete_locator_model` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6300 | `MainWindow.__init__` | `self.btn_note_locator.clicked` | `self.edit_locator_model_note` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6310 | `MainWindow.__init__` | `self.combo_segmenter.activated` | `self.on_segmenter_changed` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6311 | `MainWindow.__init__` | `self.combo_segmenter.currentIndexChanged` | `self.update_model_delete_button_states` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6316 | `MainWindow.__init__` | `self.btn_del_segmenter.clicked` | `self.delete_segmenter_model` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6320 | `MainWindow.__init__` | `self.btn_note_segmenter.clicked` | `self.edit_segmenter_model_note` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6335 | `MainWindow.__init__` | `self.btn_predict.clicked` | `self.run_prediction` | vlm_prediction_export | 7 | TBD | TBD | TBD |
| 6339 | `MainWindow.__init__` | `self.btn_batch.clicked` | `self.run_batch_inference` | runtime_worker | 1 | TBD | TBD | TBD |
| 6344 | `MainWindow.__init__` | `self.btn_accept_current_ai_drafts.clicked` | `self.accept_current_image_ai_drafts` | vlm_prediction_export | 7 | TBD | TBD | TBD |
| 6348 | `MainWindow.__init__` | `self.btn_accept_batch_ai_drafts.clicked` | `self.accept_batch_ai_drafts` | vlm_prediction_export | 7 | TBD | TBD | TBD |
| 6373 | `MainWindow.__init__` | `self.btn_train.clicked` | `self.run_training` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6378 | `MainWindow.__init__` | `self.btn_stop_training.clicked` | `self.stop_training` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6383 | `MainWindow.__init__` | `self.btn_clear_ai.clicked` | `self.clear_ai_labels` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6405 | `MainWindow.__init__` | `self.combo_blink_parent_context.activated` | `self.on_blink_parent_context_changed` | blink | 6 | TBD | TBD | TBD |
| 6417 | `MainWindow.__init__` | `self.check_lock_parent_box_ratio.stateChanged` | `self._refresh_annotation_box_constraints` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6420 | `MainWindow.__init__` | `self.btn_configure_route_expert.clicked` | `self.open_current_route_expert_settings` | blink | 6 | TBD | TBD | TBD |
| 6424 | `MainWindow.__init__` | `self.btn_blink_auto_annotate.clicked` | `self.run_blink_child_auto_annotate` | blink | 6 | TBD | TBD | TBD |
| 6431 | `MainWindow.__init__` | `self.btn_blink_auto_shrink.clicked` | `self.run_blink_auto_shrink` | blink | 6 | TBD | TBD | TBD |
| 6435 | `MainWindow.__init__` | `self.btn_blink_batch_auto_shrink.clicked` | `self.run_blink_batch_auto_shrink` | blink | 6 | TBD | TBD | TBD |
| 6443 | `MainWindow.__init__` | `self.btn_blink_train_expert.clicked` | `self.train_current_blink_expert` | blink | 6 | TBD | TBD | TBD |
| 6448 | `MainWindow.__init__` | `self.btn_blink_stop_training.clicked` | `self.stop_current_blink_expert_training` | blink | 6 | TBD | TBD | TBD |
| 6469 | `MainWindow.__init__` | `self.btn_training_results.clicked` | `self.open_training_results_browser` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6509 | `MainWindow.__init__` | `self.pdf_widget.start_center_requested` | `self.return_to_start_center_with_context` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6510 | `MainWindow.__init__` | `self.pdf_widget.agent_requested` | `self.open_agent_from_context` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6512 | `MainWindow.__init__` | `self.tif_workbench.start_center_requested` | `self.return_to_start_center_with_context` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6513 | `MainWindow.__init__` | `self.tif_workbench.agent_requested` | `self.open_agent_from_context` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6527 | `MainWindow.__init__` | `self.blink_lab.start_center_requested` | `self.return_to_start_center_with_context` | blink | 6 | TBD | TBD | TBD |
| 6528 | `MainWindow.__init__` | `self.blink_lab.agent_requested` | `self.open_agent_from_context` | blink | 6 | TBD | TBD | TBD |
| 6529 | `MainWindow.__init__` | `self.blink_lab.global_labels_updated` | `self.on_global_labels_updated` | blink | 6 | TBD | TBD | TBD |
| 6530 | `MainWindow.__init__` | `self.blink_lab.route_registry_refresh_requested` | `self.refresh_route_table` | blink | 6 | TBD | TBD | TBD |
| 6609 | `MainWindow._build_start_center` | `self.agent_panel.status_changed` | `self._handle_agent_dashboard_status_changed` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6645 | `MainWindow._build_start_center` | `self.btn_start_ant_code.clicked` | `self.agent_panel.start_dashboard` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6648 | `MainWindow._build_start_center` | `self.btn_stop_ant_code.clicked` | `self.agent_panel.stop_dashboard` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6732 | `MainWindow._build_start_quick_panel` | `self.btn_continue_last.clicked` | `self.open_last_project` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6735 | `MainWindow._build_start_quick_panel` | `self.btn_open_any.clicked` | `self.open_project` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6738 | `MainWindow._build_start_quick_panel` | `self.btn_general_settings.clicked` | `self.open_general_settings` | dialog_settings | 2 | TBD | TBD | TBD |
| 6773 | `MainWindow._build_project_console` | `self.btn_start_console_toggle.clicked` | `self._toggle_start_project_console` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6873 | `MainWindow._build_workflow_card` | `enter_button.clicked` | `enter_callback` | shell_start_agent | 3 | TBD | TBD | TBD |
| 6877 | `MainWindow._build_workflow_card` | `create_button.clicked` | `create_callback` | shell_start_agent | 3 | TBD | TBD | TBD |
| 8457 | `MainWindow._connect_child_training_progress` | `thread.progress_signal` | `lambda value: self._set_training_progress('child', None, value)` | runtime_worker | 1 | TBD | TBD | TBD |
| 8458 | `MainWindow._connect_child_training_progress` | `thread.result_signal` | `self._on_child_training_result` | runtime_worker | 1 | TBD | TBD | TBD |
| 8459 | `MainWindow._connect_child_training_progress` | `thread.error_signal` | `self._on_child_training_error` | runtime_worker | 1 | TBD | TBD | TBD |
| 8460 | `MainWindow._connect_child_training_progress` | `thread.cancelled_signal` | `self._on_child_training_cancelled` | runtime_worker | 1 | TBD | TBD | TBD |
| 8461 | `MainWindow._connect_child_training_progress` | `thread.finished` | `self._on_child_training_finished` | runtime_worker | 1 | TBD | TBD | TBD |
| 8565 | `MainWindow._launch_training_with_preflight` | `self.trainer.log_signal` | `self.log` | dialog_settings | 2 | TBD | TBD | TBD |
| 8566 | `MainWindow._launch_training_with_preflight` | `self.trainer.progress_signal` | `lambda value: self._set_training_progress('parent', None, value)` | dialog_settings | 2 | TBD | TBD | TBD |
| 8567 | `MainWindow._launch_training_with_preflight` | `self.trainer.report_signal` | `self.show_training_report` | dialog_settings | 2 | TBD | TBD | TBD |
| 8568 | `MainWindow._launch_training_with_preflight` | `self.trainer.success_signal` | `self._on_training_success` | dialog_settings | 2 | TBD | TBD | TBD |
| 8569 | `MainWindow._launch_training_with_preflight` | `self.trainer.error_signal` | `self._on_training_error` | dialog_settings | 2 | TBD | TBD | TBD |
| 8570 | `MainWindow._launch_training_with_preflight` | `self.trainer.finished_signal` | `self._on_training_finished` | dialog_settings | 2 | TBD | TBD | TBD |
| 9998 | `MainWindow._choose_clear_ai_scope` | `scope_combo.currentIndexChanged` | `lambda _index: refresh_summary()` | shell_start_agent | 3 | TBD | TBD | TBD |
| 9999 | `MainWindow._choose_clear_ai_scope` | `clear_button.clicked` | `accept_scope` | shell_start_agent | 3 | TBD | TBD | TBD |
| 10000 | `MainWindow._choose_clear_ai_scope` | `cancel_button.clicked` | `dialog.reject` | dialog_settings | 2 | TBD | TBD | TBD |
| 10449 | `MainWindow.open_general_settings` | `dlg.agent_requested` | `self.open_agent_from_context` | dialog_settings | 2 | TBD | TBD | TBD |
| 10529 | `MainWindow.open_stl_model_settings` | `dlg.agent_requested` | `self.open_agent_from_context` | dialog_settings | 2 | TBD | TBD | TBD |
| 10631 | `MainWindow.open_tif_model_settings` | `dlg.agent_requested` | `self.open_agent_from_context` | dialog_settings | 2 | TBD | TBD | TBD |
| 10853 | `MainWindow._start_image_import` | `thread.progress_signal` | `on_progress` | runtime_worker | 1 | TBD | TBD | TBD |
| 10854 | `MainWindow._start_image_import` | `thread.success_signal` | `on_success` | runtime_worker | 1 | TBD | TBD | TBD |
| 10855 | `MainWindow._start_image_import` | `thread.error_signal` | `on_error` | runtime_worker | 1 | TBD | TBD | TBD |
| 10856 | `MainWindow._start_image_import` | `thread.finished_signal` | `on_finished` | runtime_worker | 1 | TBD | TBD | TBD |
| 13415 | `MainWindow.run_external_training` | `thread.log_signal` | `self.log` | runtime_worker | 1 | TBD | TBD | TBD |
| 13416 | `MainWindow.run_external_training` | `thread.success_signal` | `on_success` | runtime_worker | 1 | TBD | TBD | TBD |
| 13417 | `MainWindow.run_external_training` | `thread.error_signal` | `on_error` | runtime_worker | 1 | TBD | TBD | TBD |
| 13418 | `MainWindow.run_external_training` | `thread.finished_signal` | `on_finished` | runtime_worker | 1 | TBD | TBD | TBD |
| 14291 | `MainWindow._start_next_vlm_preannotation_image` | `thread.log_signal` | `self.log` | runtime_worker | 1 | TBD | TBD | TBD |
| 14292 | `MainWindow._start_next_vlm_preannotation_image` | `thread.image_result_signal` | `self._on_vlm_preannotation_image_result` | runtime_worker | 1 | TBD | TBD | TBD |
| 14293 | `MainWindow._start_next_vlm_preannotation_image` | `thread.progress_signal` | `lambda completed, total, step_name, worker=thread: self._on_vlm_preannotation_thread_step(worker, completed, total, step_name)` | runtime_worker | 1 | TBD | TBD | TBD |
| 14294 | `MainWindow._start_next_vlm_preannotation_image` | `thread.error_signal` | `self._on_vlm_preannotation_error` | runtime_worker | 1 | TBD | TBD | TBD |
| 14297 | `MainWindow._start_next_vlm_preannotation_image` | `native_finished` | `lambda worker=thread: self._on_vlm_preannotation_qthread_finished(worker)` | runtime_worker | 1 | TBD | TBD | TBD |
| 14299 | `MainWindow._start_next_vlm_preannotation_image` | `thread.finished_signal` | `lambda worker=thread: self._on_vlm_preannotation_qthread_finished(worker)` | runtime_worker | 1 | TBD | TBD | TBD |
| 14600 | `MainWindow._create_vlm_progress_dialog` | `stop_button.clicked` | `lambda : self.request_stop_vlm_preannotation(confirm=True)` | vlm_prediction_export | 7 | TBD | TBD | TBD |
| 15115 | `MainWindow._start_external_batch_inference` | `thread.log_signal` | `self.log` | runtime_worker | 1 | TBD | TBD | TBD |
| 15116 | `MainWindow._start_external_batch_inference` | `thread.progress_signal` | `on_progress` | runtime_worker | 1 | TBD | TBD | TBD |
| 15117 | `MainWindow._start_external_batch_inference` | `thread.result_signal` | `on_result` | runtime_worker | 1 | TBD | TBD | TBD |
| 15118 | `MainWindow._start_external_batch_inference` | `thread.error_signal` | `on_error` | runtime_worker | 1 | TBD | TBD | TBD |
| 15119 | `MainWindow._start_external_batch_inference` | `thread.finished_signal` | `on_finished` | runtime_worker | 1 | TBD | TBD | TBD |
| 15170 | `MainWindow.run_batch_inference` | `self.inf_thread.log_signal` | `self.log` | runtime_worker | 1 | TBD | TBD | TBD |
| 15185 | `MainWindow.run_batch_inference` | `self.inf_thread.result_signal` | `on_batch_res` | runtime_worker | 1 | TBD | TBD | TBD |
| 15186 | `MainWindow.run_batch_inference` | `self.inf_thread.finished_signal` | `lambda : [self.project.save_project(), self.btn_batch.setEnabled(True), self.btn_predict.setEnabled(True), self.refresh_file_list(), self._refresh_blink_refine_state()]` | runtime_worker | 1 | TBD | TBD | TBD |
| 15276 | `MainWindow._start_dataset_export` | `thread.progress_signal` | `on_progress` | runtime_worker | 1 | TBD | TBD | TBD |
| 15277 | `MainWindow._start_dataset_export` | `thread.success_signal` | `on_success` | runtime_worker | 1 | TBD | TBD | TBD |
| 15278 | `MainWindow._start_dataset_export` | `thread.error_signal` | `on_error` | runtime_worker | 1 | TBD | TBD | TBD |
| 15279 | `MainWindow._start_dataset_export` | `thread.finished_signal` | `on_finished` | runtime_worker | 1 | TBD | TBD | TBD |
| 15293 | `MainWindow.init_sam` | `self.sam_thread.started` | `self.sam_worker.load_model` | runtime_worker | 1 | TBD | TBD | TBD |
| 15296 | `MainWindow.init_sam` | `self.sam_point_requested` | `self.sam_worker.predict_point` | runtime_worker | 1 | TBD | TBD | TBD |
| 15298 | `MainWindow.init_sam` | `self.sam_box_requested` | `self.sam_worker.predict_box` | runtime_worker | 1 | TBD | TBD | TBD |
| 15299 | `MainWindow.init_sam` | `self.sam_worker.mask_generated` | `self.on_sam_mask_generated` | runtime_worker | 1 | TBD | TBD | TBD |
| 15301 | `MainWindow.init_sam` | `self.sam_worker.prompt_failed` | `self.on_sam_prompt_failed` | runtime_worker | 1 | TBD | TBD | TBD |
| 15302 | `MainWindow.init_sam` | `self.sam_worker.model_loaded` | `self._on_sam_model_loaded` | runtime_worker | 1 | TBD | TBD | TBD |
| 15303 | `MainWindow.init_sam` | `self.sam_worker.model_load_error` | `lambda message: self.log(str(message))` | runtime_worker | 1 | TBD | TBD | TBD |

## Thread Timer and Async Entries

| Line | Kind | Owner | Call | Workflow | Stage | Cancel/cleanup | Context guard |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 7702 | thread_start | `MainWindow._schedule_project_save` | `self.project_save_timer.start` | shell_start_agent | 3 | TBD | TBD |
| 7708 | thread_start | `MainWindow._defer_project_save_for_active_navigation` | `self.project_save_timer.start` | shell_start_agent | 3 | TBD | TBD |
| 7729 | thread_start | `MainWindow._flush_pending_project_save` | `self.project_save_timer.start` | shell_start_agent | 3 | TBD | TBD |
| 7991 | single_shot | `MainWindow._preload_2d_stl_models_after_open` | `QTimer.singleShot` | shell_start_agent | 3 | TBD | TBD |
| 8575 | thread_start | `MainWindow._launch_training_with_preflight` | `self.trainer.start` | dialog_settings | 2 | TBD | TBD |
| 8629 | single_shot | `MainWindow._on_training_error` | `QTimer.singleShot` | shell_start_agent | 3 | TBD | TBD |
| 10857 | thread_start | `MainWindow._start_image_import` | `thread.start` | runtime_worker | 1 | TBD | TBD |
| 13419 | thread_start | `MainWindow.run_external_training` | `thread.start` | runtime_worker | 1 | TBD | TBD |
| 14300 | thread_start | `MainWindow._start_next_vlm_preannotation_image` | `thread.start` | runtime_worker | 1 | TBD | TBD |
| 15120 | thread_start | `MainWindow._start_external_batch_inference` | `thread.start` | runtime_worker | 1 | TBD | TBD |
| 15195 | thread_start | `MainWindow.run_batch_inference` | `self.inf_thread.start` | runtime_worker | 1 | TBD | TBD |
| 15280 | thread_start | `MainWindow._start_dataset_export` | `thread.start` | runtime_worker | 1 | TBD | TBD |
| 15289 | QThread | `MainWindow.init_sam` | `QThread` | runtime_worker | 1 | TBD | TBD |
| 15304 | thread_start | `MainWindow.init_sam` | `self.sam_thread.start` | runtime_worker | 1 | TBD | TBD |
| 15358 | python_thread | `MainWindow._preload_engine_parts_model_async` | `threading.Thread` | runtime_worker | 1 | TBD | TBD |
| 15363 | thread_start | `MainWindow._preload_engine_parts_model_async` | `self.parts_model_preload_thread.start` | runtime_worker | 1 | TBD | TBD |
