# TaxaMask Round 4 Main Window Signal and Async Inventory

由 `scripts/analyze_main_window_architecture.py` 生成。目标 owner、解绑策略和 contract test 在对应 Stage 实施前填写。

## Qt Connections

| File | Line | Binding | Owner | Signal | Current target | Workflow | Stage | Target owner | Unbind | Contract test |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AntSleap/main.py | 1451 | connect | `MainWindow._connect_child_training_progress` | `thread.progress_signal` | `lambda value: self._set_training_progress('child', None, value)` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 1452 | connect | `MainWindow._connect_child_training_progress` | `thread.result_signal` | `self._on_child_training_result` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 1453 | connect | `MainWindow._connect_child_training_progress` | `thread.error_signal` | `self._on_child_training_error` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 1454 | connect | `MainWindow._connect_child_training_progress` | `thread.cancelled_signal` | `self._on_child_training_cancelled` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 1455 | connect | `MainWindow._connect_child_training_progress` | `thread.finished` | `self._on_child_training_finished` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 1559 | connect | `MainWindow._launch_training_with_preflight` | `self.trainer.log_signal` | `self.log` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/main.py | 1560 | connect | `MainWindow._launch_training_with_preflight` | `self.trainer.progress_signal` | `lambda value: self._set_training_progress('parent', None, value)` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/main.py | 1561 | connect | `MainWindow._launch_training_with_preflight` | `self.trainer.report_signal` | `self.show_training_report` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/main.py | 1562 | connect | `MainWindow._launch_training_with_preflight` | `self.trainer.success_signal` | `self._on_training_success` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/main.py | 1563 | connect | `MainWindow._launch_training_with_preflight` | `self.trainer.error_signal` | `self._on_training_error` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/main.py | 1564 | connect | `MainWindow._launch_training_with_preflight` | `self.trainer.finished_signal` | `self._on_training_finished` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/main.py | 2995 | connect | `MainWindow._choose_clear_ai_scope` | `scope_combo.currentIndexChanged` | `lambda _index: refresh_summary()` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/main.py | 2996 | connect | `MainWindow._choose_clear_ai_scope` | `clear_button.clicked` | `accept_scope` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/main.py | 2997 | connect | `MainWindow._choose_clear_ai_scope` | `cancel_button.clicked` | `dialog.reject` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/main.py | 3446 | connect | `MainWindow.open_general_settings` | `dlg.agent_requested` | `self.open_agent_from_context` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/main.py | 3526 | connect | `MainWindow.open_stl_model_settings` | `dlg.agent_requested` | `self.open_agent_from_context` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/main.py | 3628 | connect | `MainWindow.open_tif_model_settings` | `dlg.agent_requested` | `self.open_agent_from_context` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/main.py | 3858 | connect | `MainWindow._start_image_import` | `thread.progress_signal` | `on_progress` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 3859 | connect | `MainWindow._start_image_import` | `thread.success_signal` | `on_success` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 3860 | connect | `MainWindow._start_image_import` | `thread.error_signal` | `on_error` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 3861 | connect | `MainWindow._start_image_import` | `thread.finished_signal` | `on_finished` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 6420 | connect | `MainWindow.run_external_training` | `thread.log_signal` | `self.log` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 6421 | connect | `MainWindow.run_external_training` | `thread.success_signal` | `on_success` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 6422 | connect | `MainWindow.run_external_training` | `thread.error_signal` | `on_error` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 6423 | connect | `MainWindow.run_external_training` | `thread.finished_signal` | `on_finished` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 7296 | connect | `MainWindow._start_next_vlm_preannotation_image` | `thread.log_signal` | `self.log` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 7297 | connect | `MainWindow._start_next_vlm_preannotation_image` | `thread.image_result_signal` | `self._on_vlm_preannotation_image_result` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 7298 | connect | `MainWindow._start_next_vlm_preannotation_image` | `thread.progress_signal` | `lambda completed, total, step_name, worker=thread: self._on_vlm_preannotation_thread_step(worker, completed, total, step_name)` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 7299 | connect | `MainWindow._start_next_vlm_preannotation_image` | `thread.error_signal` | `self._on_vlm_preannotation_error` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 7302 | connect | `MainWindow._start_next_vlm_preannotation_image` | `native_finished` | `lambda worker=thread: self._on_vlm_preannotation_qthread_finished(worker)` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 7304 | connect | `MainWindow._start_next_vlm_preannotation_image` | `thread.finished_signal` | `lambda worker=thread: self._on_vlm_preannotation_qthread_finished(worker)` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 7605 | connect | `MainWindow._create_vlm_progress_dialog` | `stop_button.clicked` | `lambda : self.request_stop_vlm_preannotation(confirm=True)` | vlm_prediction_export | 7 | TBD | TBD | TBD |
| AntSleap/main.py | 8120 | connect | `MainWindow._start_external_batch_inference` | `thread.log_signal` | `self.log` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 8121 | connect | `MainWindow._start_external_batch_inference` | `thread.progress_signal` | `on_progress` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 8122 | connect | `MainWindow._start_external_batch_inference` | `thread.result_signal` | `on_result` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 8123 | connect | `MainWindow._start_external_batch_inference` | `thread.error_signal` | `on_error` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 8124 | connect | `MainWindow._start_external_batch_inference` | `thread.finished_signal` | `on_finished` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 8175 | connect | `MainWindow.run_batch_inference` | `self.inf_thread.log_signal` | `self.log` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 8190 | connect | `MainWindow.run_batch_inference` | `self.inf_thread.result_signal` | `on_batch_res` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 8191 | connect | `MainWindow.run_batch_inference` | `self.inf_thread.finished_signal` | `lambda : [self.project.save_project(), self.btn_batch.setEnabled(True), self.btn_predict.setEnabled(True), self.refresh_file_list(), self._refresh_blink_refine_state()]` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 8281 | connect | `MainWindow._start_dataset_export` | `thread.progress_signal` | `on_progress` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 8282 | connect | `MainWindow._start_dataset_export` | `thread.success_signal` | `on_success` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 8283 | connect | `MainWindow._start_dataset_export` | `thread.error_signal` | `on_error` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 8284 | connect | `MainWindow._start_dataset_export` | `thread.finished_signal` | `on_finished` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 8298 | connect | `MainWindow.init_sam` | `self.sam_thread.started` | `self.sam_worker.load_model` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 8301 | connect | `MainWindow.init_sam` | `self.sam_point_requested` | `self.sam_worker.predict_point` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 8303 | connect | `MainWindow.init_sam` | `self.sam_box_requested` | `self.sam_worker.predict_box` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 8304 | connect | `MainWindow.init_sam` | `self.sam_worker.mask_generated` | `self.on_sam_mask_generated` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 8306 | connect | `MainWindow.init_sam` | `self.sam_worker.prompt_failed` | `self.on_sam_prompt_failed` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 8307 | connect | `MainWindow.init_sam` | `self.sam_worker.model_loaded` | `self._on_sam_model_loaded` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/main.py | 8308 | connect | `MainWindow.init_sam` | `self.sam_worker.model_load_error` | `lambda message: self.log(str(message))` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/ui/main_window_dialogs.py | 84 | connect | `ExportDialog.__init__` | `btn_browse.clicked` | `self.browse` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/ui/main_window_dialogs.py | 90 | connect | `ExportDialog.__init__` | `btn_ok.clicked` | `self.accept` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/ui/main_window_dialogs.py | 93 | connect | `ExportDialog.__init__` | `btn_cancel.clicked` | `self.reject` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/ui/main_window_dialogs.py | 161 | connect | `BlinkEntryDialog.__init__` | `buttons.accepted` | `self.accept` | blink | 6 | TBD | TBD | TBD |
| AntSleap/ui/main_window_dialogs.py | 162 | connect | `BlinkEntryDialog.__init__` | `buttons.rejected` | `self.reject` | blink | 6 | TBD | TBD | TBD |
| AntSleap/ui/main_window_dialogs.py | 166 | connect | `BlinkEntryDialog.__init__` | `self.target_combo.currentIndexChanged` | `self._sync_preferred_roi` | blink | 6 | TBD | TBD | TBD |
| AntSleap/ui/main_window_dialogs.py | 249 | connect | `LiteratureDescriptionDialog.__init__` | `self.btn_search.clicked` | `self.refresh_records` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/main_window_dialogs.py | 258 | connect | `LiteratureDescriptionDialog.__init__` | `self.raw_scope_combo.currentIndexChanged` | `self.refresh_raw_records` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/main_window_dialogs.py | 287 | connect | `LiteratureDescriptionDialog.__init__` | `self.table.itemSelectionChanged` | `self._on_selection_changed` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/main_window_dialogs.py | 311 | connect | `LiteratureDescriptionDialog.__init__` | `self.raw_table.itemSelectionChanged` | `self._on_raw_selection_changed` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/main_window_dialogs.py | 313 | connect | `LiteratureDescriptionDialog.__init__` | `self.result_tabs.currentChanged` | `self._on_result_tab_changed` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/main_window_dialogs.py | 324 | connect | `LiteratureDescriptionDialog.__init__` | `self.btn_replace.clicked` | `self.accept_replace` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/main_window_dialogs.py | 326 | connect | `LiteratureDescriptionDialog.__init__` | `self.btn_append.clicked` | `self.accept_append` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/main_window_dialogs.py | 328 | connect | `LiteratureDescriptionDialog.__init__` | `self.btn_close.clicked` | `self.reject` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/main_window_dialogs.py | 335 | connect | `LiteratureDescriptionDialog.__init__` | `self.search_edit.returnPressed` | `self.refresh_records` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/training_report_dialogs.py | 102 | connect | `TrainingPreflightDialog.__init__` | `buttons.accepted` | `self._accept_training` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/training_report_dialogs.py | 103 | connect | `TrainingPreflightDialog.__init__` | `buttons.rejected` | `self.reject` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/training_report_dialogs.py | 285 | connect | `TrainingReportDialog.__init__` | `self.slider_pct.valueChanged` | `lambda v: self.lbl_pct.setText(f'{v}%')` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/training_report_dialogs.py | 293 | connect | `TrainingReportDialog.__init__` | `self.validation_filter.currentIndexChanged` | `self.load_gallery` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/training_report_dialogs.py | 297 | connect | `TrainingReportDialog.__init__` | `btn_load.clicked` | `self.load_gallery` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/training_report_dialogs.py | 334 | connect | `TrainingReportDialog.__init__` | `self.validation_index_table.itemSelectionChanged` | `self._load_selected_detail_preview` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/training_report_dialogs.py | 353 | connect | `TrainingReportDialog.__init__` | `btn_open.clicked` | `self.open_folder` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/training_report_dialogs.py | 355 | connect | `TrainingReportDialog.__init__` | `btn_close.clicked` | `self.accept` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/training_report_dialogs.py | 569 | connect | `TrainingResultBrowserDialog.__init__` | `self.table.itemSelectionChanged` | `self._refresh_actions` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/training_report_dialogs.py | 570 | connect | `TrainingResultBrowserDialog.__init__` | `self.table.doubleClicked` | `lambda _index=None: self.preview_selected()` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/training_report_dialogs.py | 575 | connect | `TrainingResultBrowserDialog.__init__` | `self.btn_preview.clicked` | `self.preview_selected` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/training_report_dialogs.py | 579 | connect | `TrainingResultBrowserDialog.__init__` | `self.btn_open_folder.clicked` | `self.open_selected_folder` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/training_report_dialogs.py | 584 | connect | `TrainingResultBrowserDialog.__init__` | `self.btn_refresh.clicked` | `self.refresh_reports` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/training_report_dialogs.py | 593 | connect | `TrainingResultBrowserDialog.__init__` | `buttons.rejected` | `self.reject` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/route_management_panel.py | 118 | connect | `RouteManagementPanel.init_ui` | `self.route_tree.itemSelectionChanged` | `self.update_action_buttons` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/route_management_panel.py | 125 | connect | `RouteManagementPanel.init_ui` | `self.btn_refresh_routes.clicked` | `self.refresh_route_table` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/route_management_panel.py | 130 | connect | `RouteManagementPanel.init_ui` | `self.btn_appoint_route_expert.clicked` | `self.appoint_selected_route_expert` | blink | 6 | TBD | TBD | TBD |
| AntSleap/ui/route_management_panel.py | 135 | connect | `RouteManagementPanel.init_ui` | `self.btn_toggle_route.clicked` | `self.toggle_selected_route_enabled` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/route_management_panel.py | 140 | connect | `RouteManagementPanel.init_ui` | `self.btn_delete_route.clicked` | `self.delete_selected_route` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/route_management_panel.py | 145 | connect | `RouteManagementPanel.init_ui` | `self.btn_edit_expert_note.clicked` | `self.edit_selected_expert_note` | blink | 6 | TBD | TBD | TBD |
| AntSleap/ui/route_management_panel.py | 150 | connect | `RouteManagementPanel.init_ui` | `self.btn_delete_expert_file.clicked` | `self.delete_selected_expert_file` | blink | 6 | TBD | TBD | TBD |
| AntSleap/ui/settings_dialogs.py | 151 | connect | `GeneralSettingsDialog.__init__` | `btn_ask_agent.clicked` | `self.request_agent_help` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/settings_dialogs.py | 154 | connect | `GeneralSettingsDialog.__init__` | `btn_save.clicked` | `self.accept_with_validation` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/settings_dialogs.py | 157 | connect | `GeneralSettingsDialog.__init__` | `btn_cancel.clicked` | `self.reject` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/settings_dialogs.py | 298 | connect | `TifModelSettingsDialog.__init__` | `btn_validate.clicked` | `self.validate_backend` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/settings_dialogs.py | 305 | connect | `TifModelSettingsDialog.__init__` | `btn_nnunet_preset.clicked` | `self.apply_nnunet_v2_preset` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/settings_dialogs.py | 324 | connect | `TifModelSettingsDialog.__init__` | `btn_ask_agent.clicked` | `self.request_agent_help` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/settings_dialogs.py | 327 | connect | `TifModelSettingsDialog.__init__` | `btn_save.clicked` | `self.accept_with_validation` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/settings_dialogs.py | 330 | connect | `TifModelSettingsDialog.__init__` | `btn_cancel.clicked` | `self.reject` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/model_settings_view.py | 70 | connect | `ModelSettingsViewMixin._build_profile_and_parent_extension` | `self.combo_model_profile.currentIndexChanged` | `self._load_selected_profile_fields` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/model_settings_view.py | 71 | connect | `ModelSettingsViewMixin._build_profile_and_parent_extension` | `self.profile_name_edit.textChanged` | `self._update_current_profile_metadata` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/model_settings_view.py | 72 | connect | `ModelSettingsViewMixin._build_profile_and_parent_extension` | `self.profile_description_edit.textChanged` | `self._update_current_profile_metadata` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/model_settings_view.py | 73 | connect | `ModelSettingsViewMixin._build_profile_and_parent_extension` | `self.btn_new_profile.clicked` | `self.new_model_profile` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/model_settings_view.py | 74 | connect | `ModelSettingsViewMixin._build_profile_and_parent_extension` | `self.btn_copy_profile.clicked` | `self.copy_model_profile` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/model_settings_view.py | 75 | connect | `ModelSettingsViewMixin._build_profile_and_parent_extension` | `self.btn_delete_profile.clicked` | `self.delete_model_profile` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/model_settings_view.py | 76 | connect | `ModelSettingsViewMixin._build_profile_and_parent_extension` | `self.btn_set_active_profile.clicked` | `self.set_selected_profile_active` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/model_settings_view.py | 143 | connect | `ModelSettingsViewMixin._build_profile_and_parent_extension` | `self.parent_backend_combo.currentIndexChanged` | `self._sync_legacy_backend_combo_from_parent_backend` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/model_settings_view.py | 144 | connect | `ModelSettingsViewMixin._build_profile_and_parent_extension` | `self.parent_backend_combo.currentIndexChanged` | `lambda _index: self._refresh_model_source_summaries()` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/model_settings_view.py | 162 | connect | `ModelSettingsViewMixin._build_profile_and_parent_extension` | `self.child_backend_combo.currentIndexChanged` | `lambda _index: self._refresh_model_source_summaries()` | blink | 6 | TBD | TBD | TBD |
| AntSleap/ui/model_settings_view.py | 239 | connect | `ModelSettingsViewMixin._build_profile_and_parent_extension` | `btn_validate_external.clicked` | `self.validate_external_backend` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/model_settings_view.py | 410 | connect | `ModelSettingsViewMixin._build_child_tab` | `self.combo_blink_training_strategy.currentIndexChanged` | `self._update_blink_training_strategy_note` | blink | 6 | TBD | TBD | TBD |
| AntSleap/ui/model_settings_view.py | 486 | connect | `ModelSettingsViewMixin._build_child_tab` | `self.blink_dataset_tree.itemSelectionChanged` | `self._refresh_blink_dataset_actions` | blink | 6 | TBD | TBD | TBD |
| AntSleap/ui/model_settings_view.py | 495 | connect | `ModelSettingsViewMixin._build_child_tab` | `self.btn_blink_dataset_details.clicked` | `self._show_blink_dataset_details` | blink | 6 | TBD | TBD | TBD |
| AntSleap/ui/model_settings_view.py | 499 | connect | `ModelSettingsViewMixin._build_child_tab` | `self.btn_blink_dataset_delete.clicked` | `self._delete_selected_blink_dataset` | blink | 6 | TBD | TBD | TBD |
| AntSleap/ui/model_settings_view.py | 574 | connect | `ModelSettingsViewMixin._build_child_tab` | `btn_validate_external_blink.clicked` | `self.validate_external_blink_backend` | blink | 6 | TBD | TBD | TBD |
| AntSleap/ui/model_settings_view.py | 649 | connect | `ModelSettingsViewMixin._build_inference_tab` | `self.btn_vlm_detail_toggle.toggled` | `self._toggle_vlm_details` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/ui/model_settings_view.py | 702 | connect | `ModelSettingsViewMixin._build_inference_tab` | `self.combo_vlm_prompt_profile.currentIndexChanged` | `lambda _index: self._refresh_vlm_prompt_profile_editors()` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/ui/model_settings_view.py | 764 | connect | `ModelSettingsViewMixin._build_dialog_actions` | `btn_ask_agent.clicked` | `self.request_agent_help` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/model_settings_view.py | 767 | connect | `ModelSettingsViewMixin._build_dialog_actions` | `btn_save.clicked` | `self.accept_with_validation` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/model_settings_view.py | 770 | connect | `ModelSettingsViewMixin._build_dialog_actions` | `btn_cancel.clicked` | `self.reject` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/model_settings_dataset.py | 256 | connect | `ModelSettingsDatasetMixin._show_blink_dataset_details` | `buttons.accepted` | `dialog.accept` | blink | 6 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 99 | connect | `MainWindowShellMixin._initialize_main_window_state` | `self.project_save_timer.timeout` | `self._flush_pending_project_save` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 147 | connect | `MainWindowShellMixin._build_main_window_views` | `self.btn_export.clicked` | `self.export_dataset` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 150 | connect | `MainWindowShellMixin._build_main_window_views` | `self.btn_crop.clicked` | `self.open_cropper` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 153 | connect | `MainWindowShellMixin._build_main_window_views` | `self.btn_batch_split_panels.clicked` | `self.batch_split_panel_images` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 156 | connect | `MainWindowShellMixin._build_main_window_views` | `self.btn_blink_entry.clicked` | `self.launch_blink_from_workbench` | blink | 6 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 160 | connect | `MainWindowShellMixin._build_main_window_views` | `self.btn_start_center_from_workbench.clicked` | `self.shell_coordinator.return_to_start` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 164 | connect | `MainWindowShellMixin._build_main_window_views` | `self.btn_agent_from_workbench.clicked` | `lambda : self.shell_coordinator.open_agent(self._collect_image_workbench_agent_context())` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 170 | connect | `MainWindowShellMixin._build_main_window_views` | `self.btn_vlm_preannotate_current.clicked` | `self.run_vlm_preannotation_current` | vlm_prediction_export | 7 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 174 | connect | `MainWindowShellMixin._build_main_window_views` | `self.btn_vlm_preannotate_batch.clicked` | `self.run_vlm_preannotation_batch` | vlm_prediction_export | 7 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 226 | connect | `MainWindowShellMixin._build_main_window_views` | `self.file_list.customContextMenuRequested` | `self.show_file_list_context_menu` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 227 | connect | `MainWindowShellMixin._build_main_window_views` | `self.file_list.itemClicked` | `self._handle_image_list_item_clicked` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 228 | connect | `MainWindowShellMixin._build_main_window_views` | `self.file_list.currentItemChanged` | `self.on_file_selected` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 229 | connect | `MainWindowShellMixin._build_main_window_views` | `self.file_list.imagesDroppedToGroup` | `self.move_images_to_group` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 232 | connect | `MainWindowShellMixin._build_main_window_views` | `self.btn_add.clicked` | `self.add_images` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 252 | connect | `MainWindowShellMixin._build_main_window_views` | `self.radio_draw.toggled` | `self.on_tool_changed` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 257 | connect | `MainWindowShellMixin._build_main_window_views` | `self.radio_magic.toggled` | `self.on_tool_changed` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 262 | connect | `MainWindowShellMixin._build_main_window_views` | `self.radio_box.toggled` | `self.on_tool_changed` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 267 | connect | `MainWindowShellMixin._build_main_window_views` | `self.radio_annotation_box.toggled` | `self.on_tool_changed` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 272 | connect | `MainWindowShellMixin._build_main_window_views` | `self.radio_loose_shrink_box.toggled` | `self.on_tool_changed` | blink | 6 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 277 | connect | `MainWindowShellMixin._build_main_window_views` | `self.radio_scale.toggled` | `self.on_tool_changed` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 286 | connect | `MainWindowShellMixin._build_main_window_views` | `self.canvas.polygon_completed` | `self.on_polygon_completed` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 287 | connect | `MainWindowShellMixin._build_main_window_views` | `self.canvas.magic_wand_clicked` | `self.on_magic_wand_clicked` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 288 | connect | `MainWindowShellMixin._build_main_window_views` | `self.canvas.magic_box_completed` | `self.on_magic_box_completed` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 289 | connect | `MainWindowShellMixin._build_main_window_views` | `self.canvas.annotation_box_completed` | `self.on_annotation_box_completed` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 290 | connect | `MainWindowShellMixin._build_main_window_views` | `self.canvas.scale_defined` | `self.on_scale_defined` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 301 | connect | `MainWindowShellMixin._build_main_window_views` | `self.shortcut_undo.activated` | `self.canvas.undo` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 303 | connect | `MainWindowShellMixin._build_main_window_views` | `self.shortcut_redo.activated` | `self.canvas.redo` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 305 | connect | `MainWindowShellMixin._build_main_window_views` | `self.shortcut_save.activated` | `lambda : self._flush_pending_project_save(force=True)` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 307 | connect | `MainWindowShellMixin._build_main_window_views` | `self.shortcut_verify.activated` | `self.verify_current_image` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 332 | connect | `MainWindowShellMixin._build_main_window_views` | `self.genus_combo.currentTextChanged` | `self.on_genus_changed` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 341 | connect | `MainWindowShellMixin._build_main_window_views` | `self.part_list.currentItemChanged` | `self.on_part_selected` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 351 | connect | `MainWindowShellMixin._build_main_window_views` | `self.btn_add_part.clicked` | `self.add_taxonomy_part` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 354 | connect | `MainWindowShellMixin._build_main_window_views` | `self.btn_rename_part.clicked` | `self.rename_taxonomy_part` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 357 | connect | `MainWindowShellMixin._build_main_window_views` | `self.btn_del_part.clicked` | `self.remove_taxonomy_part` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 365 | connect | `MainWindowShellMixin._build_main_window_views` | `self.check_morpho.stateChanged` | `self.toggle_morphometrics` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 390 | connect | `MainWindowShellMixin._build_main_window_views` | `self.btn_literature_descriptions.clicked` | `self.open_literature_description_dialog` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 440 | connect | `MainWindowShellMixin._build_main_window_views` | `self.combo_locator.activated` | `self.on_locator_changed` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 441 | connect | `MainWindowShellMixin._build_main_window_views` | `self.combo_locator.currentIndexChanged` | `self.update_model_delete_button_states` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 446 | connect | `MainWindowShellMixin._build_main_window_views` | `self.btn_del_locator.clicked` | `self.delete_locator_model` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 450 | connect | `MainWindowShellMixin._build_main_window_views` | `self.btn_note_locator.clicked` | `self.edit_locator_model_note` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 460 | connect | `MainWindowShellMixin._build_main_window_views` | `self.combo_segmenter.activated` | `self.on_segmenter_changed` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 461 | connect | `MainWindowShellMixin._build_main_window_views` | `self.combo_segmenter.currentIndexChanged` | `self.update_model_delete_button_states` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 466 | connect | `MainWindowShellMixin._build_main_window_views` | `self.btn_del_segmenter.clicked` | `self.delete_segmenter_model` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 470 | connect | `MainWindowShellMixin._build_main_window_views` | `self.btn_note_segmenter.clicked` | `self.edit_segmenter_model_note` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 485 | connect | `MainWindowShellMixin._build_main_window_views` | `self.btn_predict.clicked` | `self.run_prediction` | vlm_prediction_export | 7 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 489 | connect | `MainWindowShellMixin._build_main_window_views` | `self.btn_batch.clicked` | `self.run_batch_inference` | runtime_worker | 1 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 494 | connect | `MainWindowShellMixin._build_main_window_views` | `self.btn_accept_current_ai_drafts.clicked` | `self.accept_current_image_ai_drafts` | vlm_prediction_export | 7 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 498 | connect | `MainWindowShellMixin._build_main_window_views` | `self.btn_accept_batch_ai_drafts.clicked` | `self.accept_batch_ai_drafts` | vlm_prediction_export | 7 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 523 | connect | `MainWindowShellMixin._build_main_window_views` | `self.btn_train.clicked` | `self.run_training` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 528 | connect | `MainWindowShellMixin._build_main_window_views` | `self.btn_stop_training.clicked` | `self.stop_training` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 533 | connect | `MainWindowShellMixin._build_main_window_views` | `self.btn_clear_ai.clicked` | `self.clear_ai_labels` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 555 | connect | `MainWindowShellMixin._build_main_window_views` | `self.combo_blink_parent_context.activated` | `self.on_blink_parent_context_changed` | blink | 6 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 567 | connect | `MainWindowShellMixin._build_main_window_views` | `self.check_lock_parent_box_ratio.stateChanged` | `self._refresh_annotation_box_constraints` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 570 | connect | `MainWindowShellMixin._build_main_window_views` | `self.btn_configure_route_expert.clicked` | `self.open_current_route_expert_settings` | blink | 6 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 574 | connect | `MainWindowShellMixin._build_main_window_views` | `self.btn_blink_auto_annotate.clicked` | `self.run_blink_child_auto_annotate` | blink | 6 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 581 | connect | `MainWindowShellMixin._build_main_window_views` | `self.btn_blink_auto_shrink.clicked` | `self.run_blink_auto_shrink` | blink | 6 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 585 | connect | `MainWindowShellMixin._build_main_window_views` | `self.btn_blink_batch_auto_shrink.clicked` | `self.run_blink_batch_auto_shrink` | blink | 6 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 593 | connect | `MainWindowShellMixin._build_main_window_views` | `self.btn_blink_train_expert.clicked` | `self.train_current_blink_expert` | blink | 6 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 598 | connect | `MainWindowShellMixin._build_main_window_views` | `self.btn_blink_stop_training.clicked` | `self.stop_current_blink_expert_training` | blink | 6 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 619 | connect | `MainWindowShellMixin._build_main_window_views` | `self.btn_training_results.clicked` | `self.open_training_results_browser` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 680 | connect_once | `MainWindowShellMixin._connect_main_window_integrations` | `self.blink_lab.start_center_requested` | `self.shell_coordinator.return_to_start` | blink | 6 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 685 | connect_once | `MainWindowShellMixin._connect_main_window_integrations` | `self.blink_lab.agent_requested` | `self.shell_coordinator.open_agent` | blink | 6 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 690 | connect_once | `MainWindowShellMixin._connect_main_window_integrations` | `self.blink_lab.global_labels_updated` | `self.on_global_labels_updated` | blink | 6 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 695 | connect_once | `MainWindowShellMixin._connect_main_window_integrations` | `self.blink_lab.route_registry_refresh_requested` | `self.refresh_route_table` | blink | 6 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 716 | connect_once | `MainWindowShellMixin._ensure_pdf_widget` | `self.pdf_widget.start_center_requested` | `self.shell_coordinator.return_to_start` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 721 | connect_once | `MainWindowShellMixin._ensure_pdf_widget` | `self.pdf_widget.agent_requested` | `self.shell_coordinator.open_agent` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 741 | connect_once | `MainWindowShellMixin._ensure_tif_workbench` | `self.tif_workbench.start_center_requested` | `self.shell_coordinator.return_to_start` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_shell.py | 746 | connect_once | `MainWindowShellMixin._ensure_tif_workbench` | `self.tif_workbench.agent_requested` | `self.shell_coordinator.open_agent` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_start_center.py | 65 | connect | `MainWindowStartCenterMixin._build_start_center` | `self.agent_panel.status_changed` | `self._handle_agent_dashboard_status_changed` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_start_center.py | 101 | connect | `MainWindowStartCenterMixin._build_start_center` | `self.btn_start_ant_code.clicked` | `self.agent_panel.start_dashboard` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_start_center.py | 104 | connect | `MainWindowStartCenterMixin._build_start_center` | `self.btn_stop_ant_code.clicked` | `self.agent_panel.stop_dashboard` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_start_center.py | 188 | connect | `MainWindowStartCenterMixin._build_start_quick_panel` | `self.btn_continue_last.clicked` | `self.open_last_project` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_start_center.py | 191 | connect | `MainWindowStartCenterMixin._build_start_quick_panel` | `self.btn_open_any.clicked` | `self.open_project` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_start_center.py | 194 | connect | `MainWindowStartCenterMixin._build_start_quick_panel` | `self.btn_general_settings.clicked` | `self.open_general_settings` | dialog_settings | 2 | TBD | TBD | TBD |
| AntSleap/ui/main_window_start_center.py | 229 | connect | `MainWindowStartCenterMixin._build_project_console` | `self.btn_start_console_toggle.clicked` | `self._toggle_start_project_console` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_start_center.py | 329 | connect | `MainWindowStartCenterMixin._build_workflow_card` | `enter_button.clicked` | `enter_callback` | shell_start_agent | 3 | TBD | TBD | TBD |
| AntSleap/ui/main_window_start_center.py | 333 | connect | `MainWindowStartCenterMixin._build_workflow_card` | `create_button.clicked` | `create_callback` | shell_start_agent | 3 | TBD | TBD | TBD |

## Thread Timer and Async Entries

| File | Line | Kind | Owner | Call | Workflow | Stage | Cancel/cleanup | Context guard |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AntSleap/main.py | 691 | thread_start | `MainWindow._schedule_project_save` | `self.project_save_timer.start` | shell_start_agent | 3 | TBD | TBD |
| AntSleap/main.py | 697 | thread_start | `MainWindow._defer_project_save_for_active_navigation` | `self.project_save_timer.start` | shell_start_agent | 3 | TBD | TBD |
| AntSleap/main.py | 718 | thread_start | `MainWindow._flush_pending_project_save` | `self.project_save_timer.start` | shell_start_agent | 3 | TBD | TBD |
| AntSleap/main.py | 979 | single_shot | `MainWindow._preload_2d_stl_models_after_open` | `QTimer.singleShot` | shell_start_agent | 3 | TBD | TBD |
| AntSleap/main.py | 1569 | thread_start | `MainWindow._launch_training_with_preflight` | `self.trainer.start` | dialog_settings | 2 | TBD | TBD |
| AntSleap/main.py | 1623 | single_shot | `MainWindow._on_training_error` | `QTimer.singleShot` | shell_start_agent | 3 | TBD | TBD |
| AntSleap/main.py | 3862 | thread_start | `MainWindow._start_image_import` | `thread.start` | runtime_worker | 1 | TBD | TBD |
| AntSleap/main.py | 6424 | thread_start | `MainWindow.run_external_training` | `thread.start` | runtime_worker | 1 | TBD | TBD |
| AntSleap/main.py | 7305 | thread_start | `MainWindow._start_next_vlm_preannotation_image` | `thread.start` | runtime_worker | 1 | TBD | TBD |
| AntSleap/main.py | 8125 | thread_start | `MainWindow._start_external_batch_inference` | `thread.start` | runtime_worker | 1 | TBD | TBD |
| AntSleap/main.py | 8200 | thread_start | `MainWindow.run_batch_inference` | `self.inf_thread.start` | runtime_worker | 1 | TBD | TBD |
| AntSleap/main.py | 8285 | thread_start | `MainWindow._start_dataset_export` | `thread.start` | runtime_worker | 1 | TBD | TBD |
| AntSleap/main.py | 8294 | QThread | `MainWindow.init_sam` | `QThread` | runtime_worker | 1 | TBD | TBD |
| AntSleap/main.py | 8309 | thread_start | `MainWindow.init_sam` | `self.sam_thread.start` | runtime_worker | 1 | TBD | TBD |
| AntSleap/main.py | 8363 | python_thread | `MainWindow._preload_engine_parts_model_async` | `threading.Thread` | runtime_worker | 1 | TBD | TBD |
| AntSleap/main.py | 8368 | thread_start | `MainWindow._preload_engine_parts_model_async` | `self.parts_model_preload_thread.start` | runtime_worker | 1 | TBD | TBD |
