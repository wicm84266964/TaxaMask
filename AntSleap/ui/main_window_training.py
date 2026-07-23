try:
    from AntSleap.ui.main_window_stage7_dependencies import *
except ImportError:
    from ui.main_window_stage7_dependencies import *


class MainWindowTrainingMixin:
    def _offer_training_integrity_recovery(self, error):
        code = str(getattr(error, "code", "") or error)
        markers = (
            "integrity",
            "digest",
            "fingerprint",
            "source_missing",
            "opaque_location",
            "initial_weight",
            "managed_locator_publication",
            "managed_segmenter_publication",
        )
        if not any(marker in code for marker in markers):
            return
        dialog = TrainingIntegrityRecoveryDialog(self.project, self)
        dialog.exec()

    def _current_training_initial_weights(self, train_segmenter):
        entries = []
        managed = self._verified_managed_parent_weights()
        managed_by_path = {
            item["relative_path"]: item
            for group in managed.values()
            for item in group
        }
        locator_ref = self._selected_locator_timestamp()
        if locator_ref:
            locator_path = self._locator_model_path(locator_ref)
            if ("/" in locator_ref or "\\" in locator_ref) and locator_ref not in managed_by_path:
                raise ValueError("managed_locator_publication_not_verified")
            item = {
                "slot": "parent.locator",
                "path": locator_path,
            }
            if locator_ref in managed_by_path:
                item["expected"] = managed_by_path[locator_ref]["expected"]
            entries.append(item)
        if train_segmenter:
            entries.append(
                {
                    "slot": "parent.sam_base",
                    "path": self.engine.base_sam_path,
                }
            )
            segmenter_ref = self._selected_segmenter_timestamp()
            if segmenter_ref:
                segmenter_path = self._segmenter_model_path(segmenter_ref)
                if ("/" in segmenter_ref or "\\" in segmenter_ref) and segmenter_ref not in managed_by_path:
                    raise ValueError("managed_segmenter_publication_not_verified")
                item = {
                    "slot": "parent.sam_decoder",
                    "path": segmenter_path,
                }
                if segmenter_ref in managed_by_path:
                    item["expected"] = managed_by_path[segmenter_ref]["expected"]
                entries.append(item)
        return entries

    def _ensure_training_initial_weights_registered(self, train_segmenter):
        try:
            entries = self._current_training_initial_weights(train_segmenter)
            if not entries:
                return True
            status = inspect_initial_weight_registration(self.project, entries)
        except Exception as exc:
            QMessageBox.critical(
                self,
                tr("Starting model verification", self.current_lang),
                str(exc),
            )
            return False
        if status.get("verified"):
            return True
        by_slot = {item["slot"]: item for item in entries}
        needs_researcher_attestation = [
            item
            for item in status["items"]
            if not by_slot[item["slot"]].get("expected")
        ]
        if needs_researcher_attestation:
            details = ", ".join(
                f"{item['slot']}: {item['status']}"
                for item in needs_researcher_attestation
            )
            answer = QMessageBox.question(
                self,
                tr("Register starting model version", self.current_lang),
                tr(
                    "The starting model files are not yet registered for this project, or no longer match the registered version: {0}. Register the current files as a new trusted version? Training will not start if you choose No.",
                    self.current_lang,
                ).format(details),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return False
        observed_by_slot = {
            item["slot"]: item.get("observed") for item in status["items"]
        }
        registration_entries = []
        for item in entries:
            clean = dict(item)
            if clean.get("expected") is None:
                clean["expected"] = observed_by_slot[item["slot"]]
            registration_entries.append(clean)
        try:
            register_initial_weight_version(
                self.project,
                registration_entries,
                note=(
                    "Researcher approved current starting model files."
                    if needs_researcher_attestation
                    else "Verified active training publication registered for this project."
                ),
            )
            return inspect_initial_weight_registration(
                self.project, registration_entries
            ).get("verified", False)
        except Exception as exc:
            QMessageBox.critical(
                self,
                tr("Starting model verification", self.current_lang),
                str(exc),
            )
            return False

    def _ensure_training_integrity_baseline(self):
        if not self.project.is_sqlite_project():
            QMessageBox.warning(
                self,
                tr("Training", self.current_lang),
                tr(
                    "Training now requires a SQLite project with a registered data baseline. Migrate this project to SQLite first.",
                    self.current_lang,
                ),
            )
            return False
        state = self.project.integrity_registry_state()
        if state.get("status") == "ready":
            return True
        answer = QMessageBox.question(
            self,
            tr("Training data baseline", self.current_lang),
            tr(
                "Before the first training run, TaxaMask must register the current source images, reviewed labels, and label schema as the trusted baseline. This reads the files to calculate hashes and does not modify them. Register the baseline now?",
                self.current_lang,
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return False
        progress = QProgressDialog(
            tr("Registering the trusted training baseline...", self.current_lang),
            tr("Cancel", self.current_lang),
            0,
            100,
            self,
        )
        progress.setWindowModality(Qt.WindowModality.WindowModal)

        def on_progress(current, total, _item):
            progress.setMaximum(max(1, int(total)))
            progress.setValue(int(current))
            QApplication.processEvents()

        try:
            self.project.initialize_integrity_baseline(
                note="Researcher approved the initial training baseline.",
                progress_callback=on_progress,
                cancel_check=progress.wasCanceled,
            )
        except Exception as exc:
            if getattr(exc, "code", "") == "legacy_truth_attestation_required":
                confirm = QMessageBox.question(
                    self,
                    tr("Confirm historical labels", self.current_lang),
                    tr(
                        "Some historical polygons have no saved review source. Confirm only if you have reviewed these labels and accept them as training truth.",
                        self.current_lang,
                    ),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if confirm != QMessageBox.StandardButton.Yes:
                    return False
                try:
                    self.project.initialize_integrity_baseline(
                        legacy_truth_attestation=True,
                        note="Researcher attested that historical polygons were reviewed.",
                        progress_callback=on_progress,
                        cancel_check=progress.wasCanceled,
                    )
                except Exception as retry_exc:
                    QMessageBox.critical(
                        self,
                        tr("Training data baseline", self.current_lang),
                        str(retry_exc),
                    )
                    return False
            else:
                QMessageBox.critical(
                    self,
                    tr("Training data baseline", self.current_lang),
                    str(exc),
                )
                return False
        finally:
            progress.close()
        return self.project.integrity_registry_state().get("status") == "ready"

    def _show_structured_training_preflight(self, preflight):
        dialog = TrainingPreflightDialog(preflight, self, self.current_lang)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        return bool(dialog.accepted_training())

    def _is_locator_oom_error(self, exc):
        message = str(exc or "").lower()
        return "out of memory" in message or "cuda out of memory" in message

    def _ask_locator_oom_retry_resolution(self, current_resolution, lower_options):
        if not lower_options:
            QMessageBox.warning(
                self,
                tr("Training Retry", self.current_lang),
                tr("No lower locator resolutions are available for retry.", self.current_lang),
            )
            return None

        options_text = ", ".join(format_size_pair(value) for value in lower_options)
        message = tr(
            "Locator stage ran out of memory at {0}. You can retry with a lower locator size: {1}",
            self.current_lang,
        ).format(format_size_pair(current_resolution), options_text)

        selected_text, ok = QInputDialog.getItem(
            self,
            tr("Training Retry", self.current_lang),
            message,
            [format_size_pair(value) for value in lower_options],
            0,
            False,
        )
        if not ok or not selected_text:
            return None

        for candidate in lower_options:
            if format_size_pair(candidate) == str(selected_text).strip():
                return tuple(candidate)
        return None

    def _is_parent_training_running(self):
        external_thread = getattr(self, "external_training_thread", None)
        return bool((self.trainer and self.trainer.isRunning()) or (external_thread and external_thread.isRunning()))

    def _is_any_training_running(self):
        return self._is_parent_training_running() or self._is_child_training_running()

    def _set_training_progress(self, kind=None, status_text=None, percent=None):
        if kind:
            self.active_training_kind = kind
        if status_text is not None:
            self.active_training_label = str(status_text)
        if percent is not None:
            try:
                progress_value = max(0, min(100, int(percent)))
            except Exception:
                progress_value = None
        else:
            progress_value = None
        if hasattr(self, "label_training_progress_status"):
            text = self.active_training_label or tr("No training running.", self.current_lang)
            if progress_value is not None:
                text = f"{text} | {progress_value}%"
            self.label_training_progress_status.setText(text)
        if progress_value is not None and hasattr(self, "progress"):
            self.progress.setValue(progress_value)

    def _launch_training_with_preflight(
        self,
        preflight,
        tax,
        locator_scope,
        train_segmenter=True,
        training_scope=None,
        retry_of=None,
    ):
        if self._is_child_training_running():
            self.log(tr("Child-part expert training is running. Wait for it to finish before training parent models.", self.current_lang))
            QMessageBox.information(
                self,
                tr("Training", self.current_lang),
                tr("Child-part expert training is running. Wait for it to finish before training parent models.", self.current_lang),
            )
            return
        active_preflight = dict(preflight or {})
        if not self._ensure_training_initial_weights_registered(train_segmenter):
            self.parent_training_failed = True
            return
        active_training_scope = dict(training_scope or {})
        scope_label = str(
            active_training_scope.get("label")
            or active_preflight.get("training_scope_label")
            or tr("All Images", self.current_lang)
        )
        scope_id = str(
            active_training_scope.get("scope_id")
            or active_preflight.get("training_scope_id")
            or "__all__"
        )
        try:
            scope_image_count = int(
                active_preflight.get(
                    "training_scope_image_count",
                    len(active_training_scope.get("images", []) or []),
                )
                or 0
            )
        except Exception:
            scope_image_count = 0
        active_preflight["training_scope_id"] = scope_id
        active_preflight["training_scope_label"] = scope_label
        active_preflight["training_scope_image_count"] = scope_image_count
        self.pending_training_preflight = {
            "preflight": active_preflight,
            "taxonomy": list(tax or []),
            "locator_scope": list(locator_scope or []),
            "train_segmenter": bool(train_segmenter),
            "training_scope": {
                "scope_id": scope_id,
                "label": scope_label,
                "image_count": scope_image_count,
            },
        }
        self.training_retry_requested = False
        self.parent_training_failed = False
        self.parent_training_cancel_requested = False
        self.parent_training_project_context = self._capture_project_task_context()

        self.engine.locator_resolution = tuple(active_preflight.get("selected_locator_size") or (512, 512))
        active_profile = _active_profile_from_manager(self.project)
        parent_backend = active_profile.get("parent_backend", {}) if isinstance(active_profile.get("parent_backend"), dict) else {}
        effective_loss_config = self.engine.set_locator_loss_weights(parent_backend.get("loss_weights"))
        allowed_uids = [
            self.project.get_image_uid(path)
            for path in active_training_scope.get("images", []) or []
        ]
        effective_config = {
            "epochs": max(1, int(self.train_epochs)),
            "batch_size": max(1, int(self.train_batch)),
            "learning_rate": float(self.train_lr),
            "weight_decay": float(self.train_wd),
            "random_seed": DEFAULT_TRAINING_SEED,
            "input_resolution": list(self.engine.locator_resolution),
            "preprocessing": {
                "dataset_adapter": "TwoStageDataset",
                "locator_batch_multiplier": 2,
                "parts_batch_size": 1,
                "parts_mask_resolution": [256, 256],
            },
            "model": {
                "family": "AntEngine",
                "version": "1",
                "locator": "TraitRegressor",
                "parts": "TrainableSAM" if train_segmenter else "disabled",
            },
            "loss_weights": dict(effective_loss_config),
            "train_segmenter": bool(train_segmenter),
            "active_profile_id": str(active_profile.get("profile_id") or ""),
            "training_scope_id": scope_id,
        }
        runs_root = os.path.join(
            os.path.dirname(os.path.abspath(self.project.current_project_path)),
            "runs",
            "train",
        )
        try:
            initial_weight_slots = [
                item["slot"]
                for item in self._current_training_initial_weights(train_segmenter)
            ]
            prepared_run = prepare_2d_training_run(
                self.project,
                runs_root=runs_root,
                entrypoint="builtin_locator_sam",
                effective_config=effective_config,
                backend={
                    "backend_id": "builtin_locator_sam",
                    "backend_version": "1.0",
                    "adapter_id": "gui_training_thread",
                    "adapter_version": "1.0",
                },
                include_parts=bool(train_segmenter),
                allowed_image_uids=allowed_uids,
                seed=DEFAULT_TRAINING_SEED,
                compute_device=str(getattr(self.engine, "device", "not_recorded")),
                cuda=str(torch.version.cuda or "not_available"),
                initial_weight_slots=initial_weight_slots,
                retry_of=retry_of,
            )
        except Exception as exc:
            self.parent_training_failed = True
            QMessageBox.critical(
                self,
                tr("Training preflight", self.current_lang),
                tr(
                    "Training did not start because the registered files or data version could not be verified: {0}",
                    self.current_lang,
                ).format(str(exc)),
            )
            self._offer_training_integrity_recovery(exc)
            return
        frozen = prepared_run.dataset
        active_preflight.update(
            {
                "taxonomy": list(frozen["taxonomy"]),
                "locator_scope": list(frozen["locator_scope"]),
                "locator_samples": list(frozen["locator_records"]),
                "parts_samples": list(frozen["parts_records"]),
                "locator_train_data": list(prepared_run.locator_train_records),
                "locator_val_data": list(prepared_run.locator_validation_records),
                "parts_train_data": list(prepared_run.parts_train_records),
                "parts_val_data": list(prepared_run.parts_validation_records),
            }
        )
        tax = list(frozen["taxonomy"])
        locator_scope = list(frozen["locator_scope"])
        self.trainer = TrainingThread(
            self.engine,
            active_preflight,
            tax,
            locator_scope,
            self.train_epochs,
            self.train_batch,
            lang=self.current_lang,
            train_segmenter=train_segmenter,
            training_context={
                "active_profile_id": active_profile.get("profile_id", ""),
                "parent_backend": parent_backend.get("backend_type", PARENT_BACKEND_BUILTIN),
                "locator_scope": list(locator_scope or []),
                "train_segmenter": bool(train_segmenter),
                "locator_resolution": list(self.engine.locator_resolution),
                "loss_config": effective_loss_config,
                "training_scope": {
                    "scope_id": scope_id,
                    "label": scope_label,
                    "image_count": scope_image_count,
                },
            },
            training_run=prepared_run.run,
            model_output_root=self.engine.weights_dir,
        )
        if hasattr(self.trainer, "translate"):
            self.trainer.translate = tr
        self.trainer.log_signal.connect(self.log)
        self.trainer.progress_signal.connect(lambda value: self._set_training_progress("parent", None, value))
        self.trainer.report_signal.connect(self.show_training_report)
        self.trainer.success_signal.connect(self._on_training_success)
        self.trainer.error_signal.connect(self._on_training_error)
        self.trainer.finished_signal.connect(self._on_training_finished)
        self.btn_train.setEnabled(False)
        self.btn_stop_training.setEnabled(True)
        self._set_training_progress("parent", tr("Parent-part model training", self.current_lang), 0)
        self._refresh_blink_refine_state()
        self.trainer.start()

    def _on_training_success(self):
        task_context = getattr(self, "parent_training_project_context", {})
        if task_context and not self._project_task_context_matches(task_context):
            self._log_stale_project_task_result("parent_training_success", task_context)
            return
        context = dict(getattr(self.trainer, "training_context", {}) or {})
        locator_weights = context.get("locator_weights") or None
        segmenter_weights = context.get("segmenter_weights") or None
        if (locator_weights or segmenter_weights) and hasattr(self.project, "update_active_model_profile_parent_weights"):
            self.project.update_active_model_profile_parent_weights(
                locator_weights=locator_weights,
                segmenter_weights=segmenter_weights,
                save=False,
            )
            self.project.save_project()
            self.log(
                tr("Active model profile updated with trained parent weights.", self.current_lang)
            )
        self.refresh_model_list()

    def _on_training_finished(self):
        task_context = getattr(self, "parent_training_project_context", {})
        context_matches = not task_context or self._project_task_context_matches(task_context)
        self.btn_train.setEnabled(False if self.training_retry_requested else True)
        self.btn_stop_training.setEnabled(False)
        if not self.training_retry_requested and not self.parent_training_failed and not self.parent_training_cancel_requested:
            if self.active_training_kind == "parent":
                self._set_training_progress("parent", tr("Parent-part model training finished.", self.current_lang), 100)
            if context_matches:
                self.refresh_model_list()
            else:
                self._log_stale_project_task_result("parent_training_finished", task_context)
        if not self.training_retry_requested:
            finished_trainer = self.trainer
            self.trainer = None
            if finished_trainer is not None and hasattr(finished_trainer, "deleteLater"):
                finished_trainer.deleteLater()
        self._refresh_blink_refine_state()

    def _on_training_error(self, payload):
        task_context = getattr(self, "parent_training_project_context", {})
        if task_context and not self._project_task_context_matches(task_context):
            self._log_stale_project_task_result("parent_training_error", task_context)
            return
        payload = dict(payload or {})
        error_type = payload.get("type")
        self.training_retry_requested = False
        self.parent_training_failed = True

        if error_type == "oom" and payload.get("stage") == "locator":
            retry_resolution = self._ask_locator_oom_retry_resolution(
                payload.get("current_resolution") or 512,
                payload.get("lower_options", []),
            )
            if retry_resolution is not None and self.pending_training_preflight:
                retry_of = str(
                    getattr(
                        getattr(self.trainer, "training_run", None),
                        "run_id",
                        "",
                    )
                    or ""
                )
                self.training_retry_requested = True
                updated_preflight = dict(self.pending_training_preflight.get("preflight") or {})
                updated_preflight["selected_locator_size"] = tuple(retry_resolution)
                updated_preflight["lower_locator_size_options"] = [
                    tuple(value)
                    for value in updated_preflight.get("lower_locator_size_options", [])
                    if tuple(value) != tuple(retry_resolution)
                ]
                self.pending_training_preflight["preflight"] = updated_preflight
                self.parent_training_failed = False
                QTimer.singleShot(
                    0,
                    lambda: self._launch_training_with_preflight(
                        updated_preflight,
                        self.pending_training_preflight.get("taxonomy", []),
                        self.pending_training_preflight.get("locator_scope", []),
                        self.pending_training_preflight.get("train_segmenter", True),
                        self.pending_training_preflight.get("training_scope", {}),
                        retry_of=retry_of or None,
                    ),
                )
                return

        message = str(payload.get("message") or "Training failed.")
        self._set_training_progress("parent", tr("Parent-part model training failed.", self.current_lang), self.progress.value())
        self.log(tr("Training aborted: {0}", self.current_lang).format(message))
        QMessageBox.critical(self, tr("Error", self.current_lang), message)

    def stop_training(self):
        if self.trainer and self.trainer.isRunning():
            self.trainer.requestInterruption()
            self.btn_stop_training.setEnabled(False)
            self.parent_training_cancel_requested = True
            self._set_training_progress("parent", tr("Stopping parent-part training...", self.current_lang), self.progress.value())
            self.log(tr("Stopping training after the current epoch/batch...", self.current_lang))

    def run_training(self):
        self._flush_pending_project_save(defer_for_navigation=False)
        if self.trainer and self.trainer.isRunning():
            self.log(tr("Training already running...", self.current_lang))
            return
        if self._is_child_training_running():
            self.log(tr("Child-part expert training is running. Wait for it to finish before training parent models.", self.current_lang))
            QMessageBox.information(
                self,
                tr("Training", self.current_lang),
                tr("Child-part expert training is running. Wait for it to finish before training parent models.", self.current_lang),
            )
            return
        if not self._ensure_training_integrity_baseline():
            return
        scope_payload = self._selected_training_scope_payload()
        scope_id = str(scope_payload.get("scope_id", "__all__") or "__all__")
        if _runtime_parent_backend(self.project, self.model_backend) == EXTERNAL_BACKEND_ID:
            if scope_id != "__all__":
                QMessageBox.information(
                    self,
                    tr("Training", self.current_lang),
                    tr(
                        "Parent-part image-group training is available for the built-in Locator/SAM backend. Custom parent extensions still receive the full project contract.",
                        self.current_lang,
                    )
                    + "\n\n"
                    + tr(
                        "Choose All Images to run this custom parent extension, or switch the active profile to Built-in Locator + SAM for image-group training.",
                        self.current_lang,
                    ),
                )
                return
            self.run_external_training()
            return
        images = list(scope_payload.get("images", []) or [])
        labels_by_image = dict(self.project.project_data.get("labels", {}))
        if not images:
            QMessageBox.warning(
                self,
                tr("No Labels", self.current_lang),
                tr("Selected training scope is empty. Choose another image group or add images to this group first.", self.current_lang),
            )
            return
        tax = self.project.project_data["taxonomy"]
        locator_scope = self.project.get_locator_scope()
        preflight = build_training_preflight(images, labels_by_image, tax, locator_scope)
        scope_label = str(scope_payload.get("label", "") or tr("All Images", self.current_lang))
        preflight["training_scope_id"] = scope_id
        preflight["training_scope_label"] = scope_label
        preflight["training_scope_image_count"] = len(images)

        if not preflight.get("locator_samples") and not preflight.get("parts_samples"):
            QMessageBox.warning(self, tr("No Labels", self.current_lang), tr("Annotate first!", self.current_lang))
            return

        self.log(tr("Training scope: {0} ({1} image(s))", self.current_lang).format(scope_label, len(images)))
        self.log(tr("Training with Taxonomy ({0}): {1}", self.current_lang).format(len(tax), tax))
        self.log(tr("Training with Locator Scope ({0}): {1}", self.current_lang).format(len(locator_scope), locator_scope))
        self.log(describe_training_preflight(preflight))
        train_segmenter = not self.chk_train_locator_only.isChecked()
        if not train_segmenter and not preflight.get("locator_samples"):
            QMessageBox.warning(
                self,
                tr("Training", self.current_lang),
                tr("Locator stage skipped: no eligible locator samples.", self.current_lang),
            )
            return

        if len(locator_scope) != self.engine.current_num_classes:
            self.engine.rebuild_locator(len(locator_scope), self.train_lr, self.train_wd)

        if not self._show_structured_training_preflight(preflight):
            return

        if preflight.get("locator_samples"):
            self.ensure_locator_preloaded()
        if not self._confirm_legacy_locator_selection_if_needed():
            return
        if train_segmenter and preflight.get("parts_samples"):
            self.ensure_sam_preloaded()

        self._launch_training_with_preflight(
            preflight,
            tax,
            locator_scope,
            train_segmenter=train_segmenter,
            training_scope=scope_payload,
        )

    def run_external_training(self):
        self._flush_pending_project_save(defer_for_navigation=False)
        if getattr(self, "external_training_thread", None) is not None and self.external_training_thread.isRunning():
            self.log(tr("Training already running...", self.current_lang))
            return
        if self._is_child_training_running():
            self.log(tr("Child-part expert training is running. Wait for it to finish before training parent models.", self.current_lang))
            QMessageBox.information(
                self,
                tr("Training", self.current_lang),
                tr("Child-part expert training is running. Wait for it to finish before training parent models.", self.current_lang),
            )
            return
        if not self.project.current_project_path:
            QMessageBox.warning(self, tr("Training", self.current_lang), tr("Save Project", self.current_lang))
            return

        self.external_training_failed = False
        self.active_training_kind = "parent"
        self.btn_train.setEnabled(False)
        self.btn_stop_training.setEnabled(False)
        self._set_training_progress("parent", tr("Parent-part model training", self.current_lang), 0)
        thread = ExternalTrainingThread(self.project, self._active_external_backend_config())
        self.external_training_thread = thread
        task_context = self._capture_project_task_context()
        self.external_training_project_context = task_context

        def on_success(summary):
            if not self._project_task_context_matches(task_context):
                self._log_stale_project_task_result("external_training_success", task_context)
                return
            self._set_training_progress("parent", tr("Parent-part model training finished.", self.current_lang), 100)
            self.log(f"External training complete. Contract: {summary.get('contract_json')}")
            self.log(f"External model manifest: {summary.get('model_manifest')}")

        def on_error(message):
            if not self._project_task_context_matches(task_context):
                self._log_stale_project_task_result("external_training_error", task_context)
                return
            self.external_training_failed = True
            self._set_training_progress("parent", tr("Parent-part model training failed.", self.current_lang), self.progress.value())
            self.log(f"External training failed: {message}")
            QMessageBox.critical(self, tr("Error", self.current_lang), str(message))

        def on_finished():
            if not getattr(self, "external_training_failed", False):
                self._set_training_progress("parent", tr("Parent-part model training finished.", self.current_lang), 100)
            if getattr(self, "external_training_thread", None) is thread:
                self.external_training_thread = None
            thread.deleteLater()
            self.btn_train.setEnabled(True)
            self.btn_stop_training.setEnabled(False)
            self._refresh_blink_refine_state()

        thread.log_signal.connect(self.log)
        thread.success_signal.connect(on_success)
        thread.error_signal.connect(on_error)
        thread.finished_signal.connect(on_finished)
        thread.start()

    def show_training_report(self, report_data):
        dlg = TrainingReportDialog(report_data, self, self.current_lang)
        dlg.exec()

    def _candidate_training_experiment_dirs(self):
        roots = []

        weights_dir = getattr(self.engine, "weights_dir", "")
        if weights_dir:
            roots.append(os.path.join(os.path.dirname(os.path.abspath(weights_dir)), "experiments"))

        project_path = getattr(self.project, "current_project_path", "") or ""
        if project_path:
            project_root = os.path.dirname(os.path.abspath(project_path))
            roots.append(os.path.join(project_root, "experiments"))
            roots.append(os.path.join(os.path.dirname(project_root), "experiments"))

        roots.append(os.path.join(PACKAGE_DIR, "experiments"))

        seen = set()
        clean_roots = []
        for root in roots:
            if not root:
                continue
            root_abs = os.path.abspath(root)
            if root_abs in seen:
                continue
            seen.add(root_abs)
            clean_roots.append(root_abs)
        return clean_roots

    def _resolve_report_artifact_path(self, report_dir, summary, summary_key, fallback_name=None):
        value = summary.get(summary_key) if isinstance(summary, dict) else None
        if isinstance(value, str) and value.strip():
            candidate = value.strip()
            if not os.path.isabs(candidate):
                candidate = os.path.join(report_dir, candidate)
            return candidate
        if fallback_name:
            return os.path.join(report_dir, fallback_name)
        return None

    def _training_report_time_label(self, report_dir):
        name = os.path.basename(os.path.normpath(report_dir))
        match = re.search(r"(\d{8})_(\d{6})", name)
        if match:
            date_value, time_value = match.groups()
            return f"{date_value[0:4]}-{date_value[4:6]}-{date_value[6:8]} {time_value[0:2]}:{time_value[2:4]}:{time_value[4:6]}"
        try:
            timestamp = os.path.getmtime(report_dir)
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
        except Exception:
            return tr("Unknown time", self.current_lang)

    def _training_report_payload_from_summary(self, report_dir, summary_path):
        try:
            with open(summary_path, "r", encoding="utf-8") as handle:
                summary = json.load(handle)
        except Exception:
            return None
        if not isinstance(summary, dict):
            return None

        dir_name = os.path.basename(os.path.normpath(report_dir))
        kind = str(summary.get("kind") or "").strip()
        is_child = kind in {"blink_expert_report", "heatmap_blink_expert_report"} or dir_name.startswith(("blink_", "heatmap_blink_"))
        report_type = "child" if is_child else "parent"
        if is_child:
            target = str(summary.get("part_name") or "").strip() or tr("Unknown target", self.current_lang)
            parent_part = str(summary.get("parent_part") or "").strip()
            target_label = f"{parent_part} -> {target}" if parent_part else target
            backend_label = tr("Heatmap Blink Expert", self.current_lang) if kind.startswith("heatmap") or dir_name.startswith("heatmap_blink_") else tr("ViT-B Blink Expert", self.current_lang)
            strategy = (
                summary.get("training_strategy")
                or (summary.get("train_params") if isinstance(summary.get("train_params"), dict) else {}).get("training_strategy")
                or (summary.get("manifest") if isinstance(summary.get("manifest"), dict) else {}).get("training_strategy")
            )
        else:
            context = summary.get("training_context") if isinstance(summary.get("training_context"), dict) else {}
            locator_scope = context.get("locator_scope") if isinstance(context.get("locator_scope"), list) else []
            target_label = ", ".join(str(part) for part in locator_scope) if locator_scope else tr("Parent-part model training", self.current_lang)
            backend_label = _parent_backend_label(context.get("parent_backend", PARENT_BACKEND_BUILTIN), self.current_lang)
            strategy = "locator-only" if context.get("train_segmenter") is False else ""

        if is_child and strategy:
            strategy_label = blink_training_strategy_label(strategy, self.current_lang)
        elif (not is_child) and strategy == "locator-only":
            strategy_label = tr("Train Locator only (skip SAM)", self.current_lang)
        else:
            strategy_label = str(strategy or "")
        validation_count = summary.get("validation_count", "")
        try:
            samples_label = str(int(validation_count))
        except Exception:
            samples_label = str(validation_count or "")

        metrics_path = self._resolve_report_artifact_path(report_dir, summary, "metrics_plot", "metrics_plot.png")
        val_path = self._resolve_report_artifact_path(report_dir, summary, "validation_summary_image", "validation_samples.png")
        validation_index_path = self._resolve_report_artifact_path(report_dir, summary, "validation_index_csv", "validation_index.csv")
        details_dir = self._resolve_report_artifact_path(report_dir, summary, "validation_details_dir", "val_details")

        report = {
            "report_type": report_type,
            "type_label": tr("Child-part", self.current_lang) if is_child else tr("Parent-part", self.current_lang),
            "target_label": target_label,
            "backend_label": backend_label,
            "strategy_label": strategy_label,
            "samples_label": samples_label,
            "time_label": self._training_report_time_label(report_dir),
            "dir": report_dir,
            "csv": self._resolve_report_artifact_path(report_dir, summary, "training_log_csv", "training_log.csv"),
            "metrics": metrics_path if metrics_path and os.path.exists(metrics_path) else metrics_path,
            "val": val_path if val_path and os.path.exists(val_path) else val_path,
            "validation_index": validation_index_path,
            "report_summary": summary_path,
            "validation_summary": summary,
            "details_dir": details_dir,
            "model_path": summary.get("model_path", ""),
        }
        return report

    def discover_training_reports(self):
        reports = []
        seen_dirs = set()
        for experiments_root in self._candidate_training_experiment_dirs():
            if not os.path.isdir(experiments_root):
                continue
            try:
                entries = sorted(os.scandir(experiments_root), key=lambda entry: entry.name.lower())
            except Exception:
                continue
            for entry in entries:
                if not entry.is_dir():
                    continue
                report_dir = os.path.abspath(entry.path)
                if report_dir in seen_dirs:
                    continue
                summary_path = os.path.join(report_dir, "report_summary.json")
                if not os.path.exists(summary_path):
                    continue
                report = self._training_report_payload_from_summary(report_dir, summary_path)
                if not report:
                    continue
                seen_dirs.add(report_dir)
                reports.append(report)
        reports.extend(self._discover_training_run_records())
        reports.sort(key=lambda item: item.get("time_label", ""), reverse=True)
        return reports

    def _training_run_stores(self):
        project_path = str(self.project.current_project_path or "")
        root = os.path.join(
            os.path.dirname(os.path.abspath(project_path)), "runs", "train"
        )
        return (
            TrainingRunRecorder(
                root,
                database_path=self.project.current_database_path,
                recover_on_startup=False,
            ),
            TrainingRunNoteStore(
                root, database_path=self.project.current_database_path
            ),
        )

    def _discover_training_run_records(self):
        is_sqlite_project = getattr(self.project, "is_sqlite_project", None)
        if not callable(is_sqlite_project) or not is_sqlite_project():
            return []
        try:
            recorder, notes = self._training_run_stores()
            records = recorder.list_records()
        except Exception:
            runtime_log_exception("training_run_browser_load_failed", *sys.exc_info())
            return []
        results = []
        for record in records:
            note = notes.load(record["run_id"])
            config = record.get("effective_config") or {}
            model = config.get("model") or {}
            results.append(
                {
                    "report_type": "run",
                    "type_label": tr("Training run", self.current_lang),
                    "target_label": str(model.get("family") or record.get("entrypoint") or ""),
                    "backend_label": str((record.get("backend") or {}).get("backend_id") or ""),
                    "strategy_label": str(record.get("entrypoint") or ""),
                    "samples_label": str(len((record.get("artifacts") or []))),
                    "time_label": str(record.get("created_at") or ""),
                    "status_label": str(record.get("status") or ""),
                    "note_label": str(note.get("importance") or ("Yes" if note.get("has_content") else "")),
                    "dir": "",
                    "run_id": record["run_id"],
                    "run_record": record,
                }
            )
        return results

    def open_training_report_payload(self, report):
        if not isinstance(report, dict):
            return
        if report.get("report_type") == "run":
            dialog = QDialog(self)
            dialog.setWindowTitle(tr("Training run details", self.current_lang))
            layout = QVBoxLayout(dialog)
            details = QTextEdit(dialog)
            details.setReadOnly(True)
            details.setPlainText(json.dumps(report.get("run_record") or {}, ensure_ascii=False, indent=2))
            layout.addWidget(details)
            dialog.resize(820, 620)
            dialog.exec()
            return
        if report.get("report_type") == "child":
            dlg = BlinkExpertTrainingReportDialog(report, self.current_lang, self)
        else:
            dlg = TrainingReportDialog(report, self, self.current_lang)
        dlg.exec()

    def edit_training_run_note(self, report):
        run_id = str((report or {}).get("run_id") or "")
        if not run_id:
            return
        try:
            _recorder, store = self._training_run_stores()
            existing = store.load(run_id)
            dialog = TrainingRunNoteDialog(
                run_id,
                existing,
                parent=self,
                lang=self.current_lang,
            )
            if dialog.exec() == QDialog.DialogCode.Accepted:
                store.save(
                    run_id,
                    **dialog.values(),
                    expected_updated_at=existing.get("updated_at"),
                )
        except Exception as exc:
            QMessageBox.critical(self, tr("Training Run Note", self.current_lang), str(exc))

    def open_training_results_browser(self):
        reports = self.discover_training_reports()
        if not reports:
            QMessageBox.information(
                self,
                tr("Training Results", self.current_lang),
                tr("No training reports found.", self.current_lang),
            )
            return
        dlg = TrainingResultBrowserDialog(
            reports,
            parent=self,
            lang=self.current_lang,
            preview_callback=self.open_training_report_payload,
            refresh_callback=self.discover_training_reports,
            note_callback=self.edit_training_run_note,
        )
        dlg.exec()
