try:
    from AntSleap.ui.main_window_stage7_dependencies import *
except ImportError:
    from ui.main_window_stage7_dependencies import *


class MainWindowVlmMixin:
    def _vlm_api_settings_path(self):
        pdf_widget = getattr(self, "pdf_widget", None)
        if pdf_widget is not None and getattr(pdf_widget, "api_settings_file", ""):
            return pdf_widget.api_settings_file
        return os.path.join(REPO_ROOT, "screener_configs", "api_runtime_settings.json")

    def _vlm_api_config_from_pdf_widget(self):
        pdf_widget = getattr(self, "pdf_widget", None)
        if pdf_widget is None:
            return {}

        def text(widget_name):
            widget = getattr(pdf_widget, widget_name, None)
            if widget is None or not hasattr(widget, "text"):
                return ""
            try:
                return widget.text().strip()
            except Exception:
                return ""

        def current_data(widget_name, fallback="auto"):
            widget = getattr(pdf_widget, widget_name, None)
            if widget is None or not hasattr(widget, "currentData"):
                return fallback
            try:
                return widget.currentData() or fallback
            except Exception:
                return fallback

        same_widget = getattr(pdf_widget, "check_mllm_same_as_text", None)
        use_same = bool(same_widget.isChecked()) if same_widget is not None and hasattr(same_widget, "isChecked") else True
        if use_same:
            return {
                "api_key": text("edit_api_key"),
                "base_url": text("edit_base_url"),
                "model": text("edit_model"),
                "api_protocol": current_data("combo_api_protocol"),
                "image_detail": current_data("combo_mllm_image_detail"),
            }
        return {
            "api_key": text("edit_mllm_api_key"),
            "base_url": text("edit_mllm_base_url"),
            "model": text("edit_mllm_model"),
            "api_protocol": current_data("combo_mllm_api_protocol"),
            "image_detail": current_data("combo_mllm_image_detail"),
        }

    def _vlm_preannotation_artifacts_dir(self):
        project_path = getattr(self.project, "current_project_path", "") or ""
        if project_path:
            base_dir = os.path.join(os.path.dirname(os.path.abspath(project_path)), "vlm_preannotation")
        else:
            base_dir = self._default_vlm_preannotation_dir()
        os.makedirs(base_dir, exist_ok=True)
        return base_dir

    def _current_vlm_target_parts(self):
        if hasattr(self.project, "get_vlm_preannotation_target_parts"):
            return self.project.get_vlm_preannotation_target_parts()
        return []

    def _current_vlm_processing_scope(self):
        if hasattr(self.project, "get_vlm_preannotation_settings"):
            return self.project.get_vlm_preannotation_settings().get("processing_scope", "current_image")
        return "current_image"

    def _current_vlm_batch_scope(self):
        scope = self._current_vlm_processing_scope()
        return scope if scope in {"all_images", "image_group"} else "image_group"

    def _current_vlm_image_group(self):
        if hasattr(self.project, "get_vlm_preannotation_settings"):
            return self.project.get_vlm_preannotation_settings().get("image_group", "split")
        return "split"

    def _current_vlm_concurrency(self):
        if hasattr(self.project, "get_vlm_preannotation_settings"):
            settings = self.project.get_vlm_preannotation_settings()
            try:
                return max(1, min(8, int(settings.get("concurrency", 1) or 1)))
            except Exception:
                return 1
        return 1

    def _current_vlm_prompt_profile(self):
        if hasattr(self.project, "get_vlm_preannotation_settings"):
            settings = self.project.get_vlm_preannotation_settings()
            return sanitize_vlm_prompt_profile(settings.get("prompt_profile", {}))
        return default_vlm_prompt_profile()

    def _vlm_image_group_label(self, group_key):
        return self._image_group_display_name(group_key)

    def _vlm_candidate_source_meta(self, candidate, result):
        return {
            "source": "vlm_first_mile",
            "review_status": "draft",
            "confidence": float(candidate.get("confidence", 0.0) or 0.0),
            "reason": str(candidate.get("reason", "") or ""),
            "source_model": str((getattr(self, "vlm_preannotation_api_config", {}) or {}).get("model", "") or ""),
            "source_run_id": str(getattr(self, "vlm_preannotation_run_id", "") or ""),
            "report_path": str(result.get("report_path", "") or ""),
        }

    def _record_sqlite_vlm_image_result(self, image_path, result, status, box_count=0, error_message=""):
        task_context = getattr(self, "vlm_preannotation_project_context", {})
        if task_context and not self._project_task_context_matches(task_context):
            self._log_stale_project_task_result("vlm_sqlite_image_result", task_context)
            return
        is_sqlite = getattr(self.project, "is_sqlite_project", lambda: False)
        if not callable(is_sqlite) or not is_sqlite():
            return
        run_id = str(getattr(self, "vlm_preannotation_run_id", "") or "")
        if not run_id:
            return
        try:
            record_vlm_image_result(
                self.project,
                run_id,
                image_path,
                status=status,
                error_message=error_message or str((result or {}).get("error", "") or ""),
                raw_response_ref=str((result or {}).get("report_path", "") or ""),
                box_count=int(box_count or 0),
            )
        except Exception:
            runtime_log_exception("sqlite_vlm_image_result_record_failed", *sys.exc_info())

    def _finish_sqlite_vlm_run(self, run_id, summary):
        task_context = getattr(self, "vlm_preannotation_project_context", {})
        if task_context and not self._project_task_context_matches(task_context):
            self._log_stale_project_task_result("vlm_sqlite_run_finish", task_context)
            return
        is_sqlite = getattr(self.project, "is_sqlite_project", lambda: False)
        if not callable(is_sqlite) or not is_sqlite():
            return
        try:
            finish_vlm_run(
                self.project,
                run_id,
                status=str((summary or {}).get("status") or "finished"),
                summary=summary or {},
            )
        except Exception:
            runtime_log_exception("sqlite_vlm_run_finish_failed", *sys.exc_info())

    def _vlm_image_paths_for_scope(self, scope):
        if scope == "all_images":
            return [path for path in self.project.project_data.get("images", []) if path]
        if scope == "image_group":
            groups = self._project_image_groups()
            return list(groups.get(self._current_vlm_image_group(), []))
        return [self.current_image] if self.current_image else []

    def _vlm_image_paths_from_settings(self):
        return self._vlm_image_paths_for_scope(self._current_vlm_processing_scope())

    def _vlm_part_list_text(self, parts):
        clean_parts = []
        for part in parts or []:
            clean_part = str(part or "").strip()
            if clean_part and clean_part not in clean_parts:
                clean_parts.append(clean_part)
        return ", ".join(clean_parts) if clean_parts else tr("none", self.current_lang)

    def _vlm_part_coverage(self, result):
        requested = []
        for part in result.get("target_parts", []) or getattr(self, "vlm_preannotation_target_parts", []) or []:
            clean_part = str(part or "").strip()
            if clean_part and clean_part not in requested:
                requested.append(clean_part)

        returned = []
        for candidate in result.get("candidates", []) or []:
            if not isinstance(candidate, dict):
                continue
            clean_part = str(candidate.get("part", "") or "").strip()
            if clean_part and clean_part not in returned:
                returned.append(clean_part)

        returned_lookup = {part.lower(): part for part in returned}
        missing = [part for part in requested if part.lower() not in returned_lookup]
        return requested, returned, missing

    def _log_vlm_part_coverage(self, result):
        image_path = str(result.get("image_path", "") or "")
        image_name = os.path.basename(image_path) if image_path else tr("Current Image", self.current_lang)
        requested, returned, missing = self._vlm_part_coverage(result)
        self.log(
            tr(
                "VLM part coverage for {0}: requested [{1}]; returned [{2}]; missing [{3}].",
                self.current_lang,
            ).format(
                image_name,
                self._vlm_part_list_text(requested),
                self._vlm_part_list_text(returned),
                self._vlm_part_list_text(missing),
            )
        )

    def run_vlm_preannotation_current(self):
        self.run_vlm_preannotation_from_settings(scope_override="current_image")

    def run_vlm_preannotation_batch(self):
        self.run_vlm_preannotation_from_settings(scope_override=self._current_vlm_batch_scope())

    def run_vlm_preannotation_from_settings(self, scope_override=None):
        processing_scope = str(scope_override or self._current_vlm_processing_scope() or "current_image")
        if processing_scope == "current_image" and not self.current_image:
            QMessageBox.warning(self, tr("VLM Pre-Annotate", self.current_lang), tr("Please select an image first.", self.current_lang))
            return
        active_vlm_threads = [
            thread
            for thread in (getattr(self, "vlm_preannotation_threads", []) or [])
            if thread is not None and thread.isRunning()
        ]
        if active_vlm_threads or (self.vlm_preannotation_thread is not None and self.vlm_preannotation_thread.isRunning()):
            QMessageBox.information(self, tr("VLM Pre-Annotate", self.current_lang), tr("VLM preannotation is already running.", self.current_lang))
            return
        target_parts = self._current_vlm_target_parts()
        if not target_parts:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Warning)
            box.setWindowTitle(tr("VLM Pre-Annotate", self.current_lang))
            box.setText(tr("Select at least one VLM target part before running pre-annotation.", self.current_lang))
            open_button = box.addButton(tr("Open VLM settings", self.current_lang), QMessageBox.AcceptRole)
            box.addButton(QMessageBox.Cancel)
            box.exec()
            if box.clickedButton() == open_button:
                self.open_stl_model_settings(focus_vlm=True)
            return
        image_paths = self._vlm_image_paths_for_scope(processing_scope)
        if not image_paths:
            QMessageBox.warning(self, tr("VLM Pre-Annotate", self.current_lang), tr("Please select an image first.", self.current_lang))
            return
        vlm_concurrency = self._current_vlm_concurrency()
        concurrency_note = "\n\n" + tr(
            "VLM API concurrency: {0}. Increase this only if your provider allows parallel requests.",
            self.current_lang,
        ).format(vlm_concurrency)
        if processing_scope == "all_images":
            if themed_yes_no_question(
                self,
                tr("VLM Pre-Annotate", self.current_lang),
                tr(
                    "Run VLM preannotation on all imported images?\n\nThis will call the multimodal API, may incur provider cost, and will write draft AI boxes and SAM polygons for later review.",
                    self.current_lang,
                )
                + concurrency_note,
                confirm_role=BUTTON_ROLE_RUN,
            ) != QMessageBox.Yes:
                return
        elif processing_scope == "image_group":
            image_group = self._current_vlm_image_group()
            if themed_yes_no_question(
                self,
                tr("VLM Pre-Annotate", self.current_lang),
                tr(
                    "Run VLM preannotation on {0} image(s) in {1}?\n\nThis will call the multimodal API, may incur provider cost, and will write draft AI boxes and SAM polygons for later review.",
                    self.current_lang,
                ).format(len(image_paths), self._vlm_image_group_label(image_group))
                + concurrency_note,
                confirm_role=BUTTON_ROLE_RUN,
            ) != QMessageBox.Yes:
                return

        try:
            api_config = load_vlm_api_config_from_runtime_settings(self._vlm_api_settings_path())
            live_config = self._vlm_api_config_from_pdf_widget()
            for key, value in live_config.items():
                if value:
                    api_config[key] = value
        except Exception as exc:
            QMessageBox.warning(self, tr("VLM Pre-Annotate", self.current_lang), str(exc))
            return
        if not api_config.get("api_key") or not api_config.get("base_url") or not api_config.get("model"):
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Warning)
            box.setWindowTitle(tr("VLM Pre-Annotate", self.current_lang))
            box.setText(tr("Configure the Multimodal LLM API in PDF Evidence Tools first.", self.current_lang))
            open_button = box.addButton(tr("Open API settings", self.current_lang), QMessageBox.AcceptRole)
            box.addButton(QMessageBox.Cancel)
            box.exec()
            if box.clickedButton() == open_button:
                self.open_pdf_multimodal_api_settings()
            return

        self.vlm_preannotation_api_config = dict(api_config)
        for button_name in ("btn_vlm_preannotate_current", "btn_vlm_preannotate_batch", "btn_vlm_preannotate"):
            button = getattr(self, button_name, None)
            if button is not None:
                button.setEnabled(False)
        self.vlm_preannotation_saved_total = 0
        self.vlm_preannotation_run_id = time.strftime("%Y%m%d_%H%M%S")
        self.vlm_preannotation_project_context = self._capture_project_task_context()
        self.vlm_preannotation_records = []
        self.vlm_preannotation_queue = list(image_paths)
        self.vlm_preannotation_threads = []
        self.vlm_preannotation_run_active = True
        self.vlm_preannotation_cancel_requested = False
        self.vlm_preannotation_cancelled_queued_images = 0
        self.vlm_preannotation_concurrency = vlm_concurrency
        self.vlm_preannotation_total_steps = max(1, len(image_paths) * 6)
        self.vlm_preannotation_completed_steps = 0
        self.vlm_preannotation_total_images = len(image_paths)
        self.vlm_preannotation_completed_images = 0
        self.vlm_preannotation_current_image = ""
        self.vlm_preannotation_active_images = {}
        self.vlm_preannotation_image_step_counts = {}
        self.vlm_preannotation_completed_image_keys = set()
        self.vlm_preannotation_target_parts = list(target_parts)
        self.vlm_preannotation_artifacts_dir = self._vlm_preannotation_artifacts_dir()
        self.vlm_preannotation_api_config = dict(api_config)
        self.vlm_preannotation_prompt_profile = self._current_vlm_prompt_profile()
        runtime_log_event(
            "vlm_batch_begin",
            project=getattr(self.project, "current_project_path", ""),
            image_count=len(image_paths),
            target_count=len(target_parts),
            concurrency=vlm_concurrency,
            scope=processing_scope,
            run_id=self.vlm_preannotation_run_id,
            artifacts_dir=self.vlm_preannotation_artifacts_dir,
        )
        self._create_vlm_progress_dialog()
        self._set_vlm_progress_ui(0, "start")
        self.log(tr("VLM API concurrency: {0}. Increase this only if your provider allows parallel requests.", self.current_lang).format(self.vlm_preannotation_concurrency))
        self._start_vlm_preannotation_workers()

    def request_stop_vlm_preannotation(self, confirm=True):
        if not getattr(self, "vlm_preannotation_run_active", False):
            return False
        if confirm:
            message = (
                tr("Stop VLM preannotation after active request(s) finish?", self.current_lang)
                + "\n\n"
                + tr(
                    "Active API request(s) may already have been sent, but no more queued images will be processed. This helps avoid unintended large API bills.",
                    self.current_lang,
                )
            )
            if themed_yes_no_question(
                self,
                tr("VLM Pre-Annotate", self.current_lang),
                message,
                confirm_role=BUTTON_ROLE_STOP,
            ) != QMessageBox.Yes:
                return False
        queued = list(getattr(self, "vlm_preannotation_queue", []) or [])
        self.vlm_preannotation_cancel_requested = True
        self.vlm_preannotation_cancelled_queued_images = int(getattr(self, "vlm_preannotation_cancelled_queued_images", 0) or 0) + len(queued)
        self.vlm_preannotation_queue = []
        button = getattr(self, "vlm_preannotation_stop_button", None)
        if button is not None:
            button.setEnabled(False)
            button.setText(tr("Stopping after current image...", self.current_lang))
        self.log(
            tr(
                "VLM stop requested. Remaining queued images were cancelled; waiting for active request(s) to finish.",
                self.current_lang,
            )
        )
        self._set_vlm_progress_ui(
            int(
                int(getattr(self, "vlm_preannotation_completed_steps", 0) or 0)
                / max(1, int(getattr(self, "vlm_preannotation_total_steps", 1) or 1))
                * 100
            ),
            "cancelled",
        )
        return True

    def _active_vlm_preannotation_threads(self):
        active = []
        for thread in getattr(self, "vlm_preannotation_threads", []) or []:
            try:
                if thread is not None and thread.isRunning():
                    active.append(thread)
            except RuntimeError:
                continue
        self.vlm_preannotation_threads = active
        self.vlm_preannotation_thread = active[0] if active else None
        return active

    def _start_vlm_preannotation_workers(self):
        if not getattr(self, "vlm_preannotation_run_active", False):
            return
        if getattr(self, "vlm_preannotation_cancel_requested", False):
            return
        active = self._active_vlm_preannotation_threads()
        limit = max(1, min(8, int(getattr(self, "vlm_preannotation_concurrency", 1) or 1)))
        while len(active) < limit and getattr(self, "vlm_preannotation_queue", []):
            thread = self._start_next_vlm_preannotation_image()
            if thread is None:
                break
            active.append(thread)
        self.vlm_preannotation_threads = active
        self.vlm_preannotation_thread = active[0] if active else None

    def _start_next_vlm_preannotation_image(self):
        queue = list(getattr(self, "vlm_preannotation_queue", []) or [])
        if not queue:
            if not self._active_vlm_preannotation_threads():
                self._finish_vlm_preannotation_run()
            return None
        image_path = queue.pop(0)
        self.vlm_preannotation_queue = queue
        self.vlm_preannotation_current_image_steps_completed = 0
        self.vlm_preannotation_current_image = image_path
        runtime_log_event(
            "vlm_worker_starting",
            image=os.path.basename(str(image_path)),
            queued=len(queue),
            run_id=getattr(self, "vlm_preannotation_run_id", ""),
        )
        self._set_vlm_progress_ui(
            int(int(getattr(self, "vlm_preannotation_completed_steps", 0) or 0) / max(1, int(getattr(self, "vlm_preannotation_total_steps", 1) or 1)) * 100),
            "image",
        )
        thread = VlmPreannotationThread(
            image_path,
            getattr(self, "vlm_preannotation_target_parts", []),
            getattr(self, "vlm_preannotation_artifacts_dir", self._vlm_preannotation_artifacts_dir()),
            getattr(self, "vlm_preannotation_api_config", {}),
            getattr(self, "vlm_preannotation_run_id", time.strftime("%Y%m%d_%H%M%S")),
            grid_cols=None,
            grid_rows=None,
            min_confidence=0.25,
            prompt_profile=getattr(self, "vlm_preannotation_prompt_profile", default_vlm_prompt_profile()),
        )
        self.vlm_preannotation_thread = thread
        active_images = getattr(self, "vlm_preannotation_active_images", None)
        if not isinstance(active_images, dict):
            active_images = {}
            self.vlm_preannotation_active_images = active_images
        step_counts = getattr(self, "vlm_preannotation_image_step_counts", None)
        if not isinstance(step_counts, dict):
            step_counts = {}
            self.vlm_preannotation_image_step_counts = step_counts
        active_images[thread] = image_path
        step_counts[self._vlm_progress_image_key(image_path)] = 0
        thread.log_signal.connect(self.log)
        thread.image_result_signal.connect(
            lambda result, worker=thread: self._on_vlm_preannotation_image_result(result, worker=worker)
        )
        thread.progress_signal.connect(lambda completed, total, step_name, worker=thread: self._on_vlm_preannotation_thread_step(worker, completed, total, step_name))
        thread.error_signal.connect(self._on_vlm_preannotation_error)
        native_finished = getattr(thread, "finished", None)
        if native_finished is not None and hasattr(native_finished, "connect"):
            native_finished.connect(lambda worker=thread: self._on_vlm_preannotation_qthread_finished(worker))
        else:
            thread.finished_signal.connect(lambda worker=thread: self._on_vlm_preannotation_qthread_finished(worker))
        thread.start()
        return thread

    def _apply_vlm_candidate(self, image_path, image_rgb, candidate, result):
        part_name = str(candidate.get("part", "") or "").strip()
        box = _clean_box(candidate.get("box_xyxy"))
        if not part_name or not box:
            return False, "invalid_candidate"

        if not self._can_replace_existing_auto_annotation(image_path, part_name, AUTO_BOX_SOURCE_VLM):
            return False, "already_labeled"

        polygon = None
        try:
            polygon = self.engine.predict_base_sam_polygon(image_rgb, box, poly_epsilon=self.inf_poly_epsilon)
        except Exception as exc:
            self.log(tr("SAM draft failed for {0}: {1}", self.current_lang).format(part_name, str(exc)))

        if polygon and len(polygon) >= 3:
            self.project.update_label(
                image_path,
                part_name,
                polygon,
                "Auto-Annotated",
                auto_box=box,
                save=False,
                training_source="vlm_first_mile",
                training_review_status="draft",
                training_accepted_via="",
            )
            update_auto_box = getattr(self.project, "update_auto_box", None)
            if callable(update_auto_box):
                update_auto_box(
                    image_path,
                    part_name,
                    box,
                    source_meta=self._vlm_candidate_source_meta(candidate, result),
                    save=False,
                )
            return True, "polygon"

        update_auto_box = getattr(self.project, "update_auto_box", None)
        if callable(update_auto_box):
            update_auto_box(
                image_path,
                part_name,
                box,
                description_text="Auto-Annotated",
                source_meta=self._vlm_candidate_source_meta(candidate, result),
                save=False,
            )
        else:
            self.project.update_label(
                image_path,
                part_name,
                [],
                "Auto-Annotated",
                auto_box=box,
                save=False,
                training_source="vlm_first_mile",
                training_review_status="draft",
                training_accepted_via="",
            )
        return True, "box_only"

    def _refresh_vlm_canvas_if_current(self, image_path):
        if self._same_project_image_path(image_path, self.current_image):
            self.canvas.set_polygons(self.project.get_labels(image_path))
            self._refresh_current_canvas_boxes()
            self.canvas.update()
            self.canvas.repaint()

    def _reload_current_image_for_workbench(self):
        if not self.current_image:
            return False
        current_path = self._project_image_key_for_path(self.current_image)
        if not current_path:
            return False
        self.current_image = current_path
        if hasattr(self, "canvas"):
            has_loaded_pixmap = bool(self.canvas.original_pixmap and not self.canvas.original_pixmap.isNull())
            if not has_loaded_pixmap:
                self.canvas.load_image(current_path)
                self.on_enhancement_changed()
            self.canvas.set_polygons(self.project.get_labels(current_path))
            self._refresh_current_canvas_boxes()
            self.canvas.update()
            self.canvas.repaint()
        get_taxon = getattr(self.project, "get_taxon", self.project.get_genus)
        if hasattr(self, "genus_combo"):
            self.genus_combo.blockSignals(True)
            try:
                self.genus_combo.setCurrentText(get_taxon(current_path))
            finally:
                self.genus_combo.blockSignals(False)
        if hasattr(self, "blink_lab"):
            try:
                self.blink_lab.refresh_from_workbench(
                    current_path,
                    self.project.get_labels(current_path),
                    self.project.get_boxes(current_path),
                    self._auto_boxes_for_canvas(current_path)[0],
                )
            except Exception:
                pass
        return True

    def _on_vlm_preannotation_image_result(self, result, worker=None):
        current_run_id = str(getattr(self, "vlm_preannotation_run_id", "") or "")
        worker_run_id = str(getattr(worker, "run_id", "") or "") if worker is not None else ""
        if worker_run_id and worker_run_id != current_run_id:
            runtime_log_event(
                "stale_vlm_run_result_skipped",
                worker_run_id=worker_run_id,
                current_run_id=current_run_id,
            )
            return
        task_context = getattr(self, "vlm_preannotation_project_context", {})
        if task_context and not self._project_task_context_matches(task_context):
            self._log_stale_project_task_result("vlm_image_result", task_context)
            self.vlm_preannotation_cancel_requested = True
            self.vlm_preannotation_queue = []
            stale_result = dict(result or {})
            stale_result["status"] = "stale_project"
            self.vlm_preannotation_records.append(stale_result)
            image_path = str(stale_result.get("image_path", "") or "")
            self._complete_current_vlm_image_steps("cancelled", image_path=image_path)
            self._mark_current_vlm_image_done("cancelled", image_path=image_path)
            return
        image_path = str(result.get("image_path", "") or "")
        runtime_log_event(
            "vlm_image_result_begin",
            image=os.path.basename(str(image_path)),
            status=result.get("status", ""),
            candidate_count=len(result.get("candidates", []) or []) if isinstance(result, dict) else 0,
            run_id=getattr(self, "vlm_preannotation_run_id", ""),
        )
        if not image_path or result.get("status") == "failed":
            self._log_vlm_part_coverage(result)
            self.log(tr("VLM first-mile preannotation failed: {0}", self.current_lang).format(result.get("error", "")))
            self._complete_current_vlm_image_steps("failed", image_path=image_path)
            self.vlm_preannotation_records.append(result)
            if image_path:
                self._record_sqlite_vlm_image_result(
                    image_path,
                    result,
                    "failed",
                    box_count=0,
                    error_message=str(result.get("error", "") or ""),
                )
            self._mark_current_vlm_image_done("failed", image_path=image_path)
            return
        candidates = list(result.get("candidates", []) or []) if isinstance(result, dict) else []
        if not candidates:
            self._log_vlm_part_coverage(result)
            self.log(tr("VLM first-mile preannotation returned no usable boxes.", self.current_lang))
            self._complete_current_vlm_image_steps("no_candidates", image_path=image_path)
            self.vlm_preannotation_records.append(result)
            self._record_sqlite_vlm_image_result(image_path, result, "no_candidates", box_count=0)
            self._mark_current_vlm_image_done("no_candidates", image_path=image_path)
            return
        try:
            project_image_path = self._project_image_key_for_path(image_path)
            if not project_image_path:
                raise RuntimeError(
                    tr(
                        "VLM result image is not registered in the current project: {0}",
                        self.current_lang,
                    ).format(image_path)
                )
            image_bgr = cv2.imread(image_path)
            if image_bgr is None:
                raise RuntimeError(tr("Could not read the current image.", self.current_lang))
            image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
            saved = 0
            polygon_count = 0
            box_only_count = 0
            skipped = 0
            for candidate in candidates:
                ok, mode = self._apply_vlm_candidate(project_image_path, image_rgb, candidate, result)
                if ok:
                    saved += 1
                    if mode == "polygon":
                        polygon_count += 1
                    elif mode == "box_only":
                        box_only_count += 1
                else:
                    skipped += 1
            self.vlm_preannotation_saved_total = int(getattr(self, "vlm_preannotation_saved_total", 0)) + saved
            is_sqlite = getattr(self.project, "is_sqlite_project", lambda: False)
            if callable(is_sqlite) and is_sqlite():
                self.project.flush_sqlite_changes(image_paths=[project_image_path], project_dirty=True)
            else:
                self._schedule_project_save(
                    reason="vlm_preannotation",
                    image=os.path.basename(str(project_image_path)),
                    saved_count=saved,
                )
            self._refresh_vlm_canvas_if_current(project_image_path)
            self._refresh_image_list_status_or_rebuild(project_image_path)
            self._reload_current_image_for_workbench()
            self._refresh_blink_refine_state()
            report_path = result.get("report_path", "")
            result["saved_box_count"] = saved
            result["saved_polygon_count"] = polygon_count
            result["saved_box_only_count"] = box_only_count
            result["skipped_count"] = skipped
            self.vlm_preannotation_records.append(result)
            self._record_sqlite_vlm_image_result(project_image_path, result, "done", box_count=saved)
            self._advance_vlm_progress("write", image_path=image_path)
            self._advance_vlm_progress("sam", image_path=image_path)
            self._advance_vlm_progress("report", image_path=image_path)
            self._mark_current_vlm_image_done("done", image_path=image_path)
            self._log_vlm_part_coverage(result)
            self.log(
                tr(
                    "VLM preannotation saved {0} draft(s): {1} SAM polygon(s), {2} box-only draft(s), skipped {3}. Report: {4}",
                    self.current_lang,
                ).format(saved, polygon_count, box_only_count, skipped, report_path)
            )
            runtime_log_event(
                "vlm_image_result_saved",
                image=os.path.basename(str(project_image_path)),
                saved=saved,
                polygon_count=polygon_count,
                box_only_count=box_only_count,
                skipped=skipped,
                run_id=getattr(self, "vlm_preannotation_run_id", ""),
            )
        except Exception as exc:
            runtime_log_exception("vlm_image_result_apply_failed", *sys.exc_info())
            self._complete_current_vlm_image_steps("failed", image_path=image_path)
            failed = dict(result)
            failed["status"] = "failed"
            failed["error"] = str(exc)
            self.vlm_preannotation_records.append(failed)
            self._record_sqlite_vlm_image_result(image_path, failed, "failed", box_count=0, error_message=str(exc))
            self._mark_current_vlm_image_done("failed", image_path=image_path)
            self._on_vlm_preannotation_error(str(exc))

    def _vlm_progress_image_key(self, image_path):
        if not image_path:
            return ""
        try:
            return os.path.normcase(os.path.normpath(os.path.abspath(str(image_path))))
        except Exception:
            return str(image_path)

    def _mark_current_vlm_image_done(self, step_name, image_path=None):
        image_key = self._vlm_progress_image_key(image_path)
        completed_keys = getattr(self, "vlm_preannotation_completed_image_keys", set())
        if not isinstance(completed_keys, set):
            completed_keys = set(completed_keys or [])
        if image_key and image_key in completed_keys:
            return
        if image_key:
            completed_keys.add(image_key)
        self.vlm_preannotation_completed_image_keys = completed_keys
        total_images = max(1, int(getattr(self, "vlm_preannotation_total_images", 1) or 1))
        self.vlm_preannotation_completed_images = min(
            total_images,
            int(getattr(self, "vlm_preannotation_completed_images", 0) or 0) + 1,
        )
        if image_path:
            self.vlm_preannotation_current_image = str(image_path)
        total_steps = max(1, int(getattr(self, "vlm_preannotation_total_steps", 1) or 1))
        completed_steps = int(getattr(self, "vlm_preannotation_completed_steps", 0) or 0)
        self._set_vlm_progress_ui(int(completed_steps / total_steps * 100), step_name)

    def _set_vlm_progress_ui(self, percent, step_name):
        total_images = max(1, int(getattr(self, "vlm_preannotation_total_images", 1) or 1))
        completed_images = min(total_images, int(getattr(self, "vlm_preannotation_completed_images", 0) or 0))
        current_image = str(getattr(self, "vlm_preannotation_current_image", "") or "")
        step_label = tr(str(step_name or ""), self.current_lang)
        percent = max(0, min(100, int(percent)))
        label = tr("VLM progress: {0}% ({1}/{2}) {3}", self.current_lang).format(
            percent,
            completed_images,
            total_images,
            step_label,
        )
        progress = getattr(self, "vlm_preannotation_progress_dialog", None)
        if progress is not None:
            label_widget = getattr(self, "vlm_preannotation_progress_label", None)
            path_widget = getattr(self, "vlm_preannotation_progress_path_label", None)
            bar_widget = getattr(self, "vlm_preannotation_progress_bar", None)
            if label_widget is not None:
                label_widget.setText(label)
            if path_widget is not None:
                if current_image:
                    path_widget.setText(self._short_progress_path(current_image, limit=92))
                    path_widget.setToolTip(current_image)
                    path_widget.show()
                else:
                    path_widget.setText("")
                    path_widget.setToolTip("")
                    path_widget.hide()
            if bar_widget is not None:
                bar_widget.setValue(percent)

    def _create_vlm_progress_dialog(self):
        progress = QDialog(self)
        progress.setWindowTitle(tr("VLM Pre-Annotate", self.current_lang))
        progress.setWindowModality(Qt.NonModal)
        progress.installEventFilter(self)
        layout = QVBoxLayout(progress)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)
        title_label = QLabel(tr("VLM Pre-Annotation Progress", self.current_lang))
        title_label.setWordWrap(True)
        title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        title_label.setMinimumHeight(title_label.fontMetrics().lineSpacing() + 6)
        notice_label = QLabel(
            tr(
                "Active API request(s) may already have been sent, but no more queued images will be processed. This helps avoid unintended large API bills.",
                self.current_lang,
            )
        )
        notice_label.setWordWrap(True)
        notice_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        notice_label.setMinimumHeight(notice_label.fontMetrics().lineSpacing() * 2 + 8)
        notice_label.setStyleSheet("color: #9CA3AF;")
        label = QLabel("")
        label.setWordWrap(True)
        label.setMinimumHeight(36)
        path_label = QLabel("")
        path_label.setWordWrap(True)
        path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        path_label.setStyleSheet("color: #9CA3AF;")
        path_label.hide()
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(0)
        stop_button = QPushButton(tr("Stop VLM Batch", self.current_lang))
        stop_button.clicked.connect(lambda: self.request_stop_vlm_preannotation(confirm=True))
        apply_semantic_button_style(stop_button, BUTTON_ROLE_STOP, "padding: 6px 12px;")
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        button_layout.addWidget(stop_button)
        layout.addWidget(title_label)
        layout.addWidget(notice_label)
        layout.addWidget(label)
        layout.addWidget(path_label)
        layout.addWidget(bar)
        layout.addLayout(button_layout)
        self._prepare_progress_dialog(progress, width=560)
        self.vlm_preannotation_progress_dialog = progress
        self.vlm_preannotation_progress_title_label = title_label
        self.vlm_preannotation_progress_notice_label = notice_label
        self.vlm_preannotation_progress_label = label
        self.vlm_preannotation_progress_path_label = path_label
        self.vlm_preannotation_progress_bar = bar
        self.vlm_preannotation_stop_button = stop_button
        progress.show()

    def _advance_vlm_progress(self, step_name, image_path=None):
        total = max(1, int(getattr(self, "vlm_preannotation_total_steps", 1) or 1))
        completed = min(total, int(getattr(self, "vlm_preannotation_completed_steps", 0) or 0) + 1)
        self.vlm_preannotation_completed_steps = completed
        if image_path:
            self.vlm_preannotation_current_image = str(image_path)
            image_key = self._vlm_progress_image_key(image_path)
            step_counts = getattr(self, "vlm_preannotation_image_step_counts", None)
            if not isinstance(step_counts, dict):
                step_counts = {}
                self.vlm_preannotation_image_step_counts = step_counts
            step_counts[image_key] = min(6, int(step_counts.get(image_key, 0) or 0) + 1)
            self.vlm_preannotation_current_image_steps_completed = step_counts[image_key]
        else:
            current_completed = int(getattr(self, "vlm_preannotation_current_image_steps_completed", 0) or 0)
            self.vlm_preannotation_current_image_steps_completed = min(6, current_completed + 1)
        self._set_vlm_progress_ui(int(completed / total * 100), step_name)
        self.log(tr("VLM batch progress: {0}/{1} steps ({2}).", self.current_lang).format(completed, total, step_name))

    def _on_vlm_preannotation_thread_step(self, worker_or_completed, completed_or_total=None, total_or_step_name=None, step_name=None):
        worker = None
        if step_name is None:
            step_name = total_or_step_name
        else:
            worker = worker_or_completed
        image_path = ""
        if worker is not None:
            active_images = getattr(self, "vlm_preannotation_active_images", {}) or {}
            image_path = active_images.get(worker, "")
        self._advance_vlm_progress(step_name, image_path=image_path)

    def _complete_current_vlm_image_steps(self, step_name, image_path=None):
        current_completed = int(getattr(self, "vlm_preannotation_current_image_steps_completed", 0) or 0)
        if image_path:
            step_counts = getattr(self, "vlm_preannotation_image_step_counts", {}) or {}
            current_completed = int(step_counts.get(self._vlm_progress_image_key(image_path), current_completed) or 0)
        for _ in range(max(0, 6 - current_completed)):
            self._advance_vlm_progress(step_name, image_path=image_path)

    def _finish_vlm_preannotation_run(self):
        records = list(getattr(self, "vlm_preannotation_records", []) or [])
        artifacts_dir = getattr(self, "vlm_preannotation_artifacts_dir", self._vlm_preannotation_artifacts_dir())
        run_id = getattr(self, "vlm_preannotation_run_id", time.strftime("%Y%m%d_%H%M%S"))
        task_context = getattr(self, "vlm_preannotation_project_context", {})
        context_matches = not task_context or self._project_task_context_matches(task_context)
        cancelled = bool(getattr(self, "vlm_preannotation_cancel_requested", False))
        cancelled_queued = int(getattr(self, "vlm_preannotation_cancelled_queued_images", 0) or 0)
        report_path = os.path.join(artifacts_dir, f"vlm_preannotation_summary_{run_id}.json")
        if context_matches and int(getattr(self, "vlm_preannotation_saved_total", 0) or 0) > 0:
            self._flush_pending_project_save(defer_for_navigation=False)
        summary = {
            "schema_version": "taxamask-vlm-preannotation-gui-summary-v1",
            "run_id": run_id,
            "artifacts_dir": artifacts_dir,
            "status": "stale_project" if not context_matches else ("cancelled" if cancelled else "finished"),
            "concurrency": max(1, min(8, int(getattr(self, "vlm_preannotation_concurrency", 1) or 1))),
            "cancelled_queued_image_count": cancelled_queued,
            "target_parts": list(getattr(self, "vlm_preannotation_target_parts", []) or []),
            "prompt_profile": sanitize_vlm_prompt_profile(
                getattr(self, "vlm_preannotation_prompt_profile", default_vlm_prompt_profile())
            ),
            "image_count": len(records),
            "candidate_count": sum(len(item.get("candidates", []) or []) for item in records),
            "saved_box_count": int(getattr(self, "vlm_preannotation_saved_total", 0) or 0),
            "rejected_count": sum(len(item.get("rejected", []) or []) for item in records),
            "records": records,
        }
        if context_matches:
            self._finish_sqlite_vlm_run(run_id, summary)
        else:
            self._log_stale_project_task_result("vlm_run_finish", task_context)
        os.makedirs(artifacts_dir, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as handle:
            json.dump(summary, handle, ensure_ascii=False, indent=2)
        runtime_log_event(
            "vlm_batch_finish",
            project=getattr(self.project, "current_project_path", ""),
            report=report_path,
            status=summary.get("status", ""),
            image_count=summary.get("image_count", 0),
            saved_box_count=summary.get("saved_box_count", 0),
            cancelled_queued_image_count=cancelled_queued,
            run_id=run_id,
        )
        if cancelled:
            self.log(
                tr(
                    "VLM preannotation stopped. Images processed: {0}; queued images cancelled: {1}; saved drafts: {2}; report: {3}",
                    self.current_lang,
                ).format(
                    summary.get("image_count", 0),
                    cancelled_queued,
                    summary.get("saved_box_count", 0),
                    report_path,
                )
            )
        else:
            self.log(
                tr("VLM preannotation finished. Images: {0}; saved drafts: {1}; report: {2}", self.current_lang).format(
                    summary.get("image_count", 0),
                    summary.get("saved_box_count", 0),
                    report_path,
                )
            )
        self.vlm_preannotation_run_active = False
        for button_name in ("btn_vlm_preannotate_current", "btn_vlm_preannotate_batch", "btn_vlm_preannotate"):
            button = getattr(self, button_name, None)
            if button is not None:
                button.setEnabled(True)
        progress = getattr(self, "vlm_preannotation_progress_dialog", None)
        if progress is not None:
            label_widget = getattr(self, "vlm_preannotation_progress_label", None)
            bar_widget = getattr(self, "vlm_preannotation_progress_bar", None)
            if label_widget is not None:
                if cancelled:
                    label_widget.setText(
                        tr("VLM progress: stopped ({0} draft boxes; {1} queued images cancelled)", self.current_lang).format(
                            summary.get("saved_box_count", 0),
                            cancelled_queued,
                        )
                    )
                else:
                    label_widget.setText(
                        tr("VLM progress: finished ({0} draft boxes)", self.current_lang).format(summary.get("saved_box_count", 0))
                    )
            if bar_widget is not None:
                bar_widget.setValue(100)
            progress.removeEventFilter(self)
            progress.close()
            progress.deleteLater()
            self.vlm_preannotation_progress_dialog = None
            self.vlm_preannotation_progress_title_label = None
            self.vlm_preannotation_progress_notice_label = None
            self.vlm_preannotation_progress_label = None
            self.vlm_preannotation_progress_path_label = None
            self.vlm_preannotation_progress_bar = None
            self.vlm_preannotation_stop_button = None
        self.vlm_preannotation_cancel_requested = False
        self.vlm_preannotation_cancelled_queued_images = 0
        self.vlm_preannotation_threads = []
        self.vlm_preannotation_thread = None
        self.vlm_preannotation_active_images = {}
        self.vlm_preannotation_image_step_counts = {}
        self.vlm_preannotation_completed_image_keys = set()

    def accept_current_image_ai_drafts(self):
        if not self.current_image:
            return
        summarize = getattr(self.project, "summarize_image_ai_drafts", None)
        draft_summary = summarize(self.current_image) if callable(summarize) else {}
        reviewable_parts = list((draft_summary or {}).get("reviewable_polygon_parts", []) or [])
        if reviewable_parts:
            reply = themed_yes_no_question(
                self,
                tr("Confirm AI Drafts", self.current_lang),
                tr(
                    "Accept {0} AI polygon draft(s) on the current image?\n\nOnly drafts that already have a polygon will become training labels. Box-only drafts will stay pending until you run SAM from the box or redraw a polygon.",
                    self.current_lang,
                ).format(len(reviewable_parts)),
                confirm_role=BUTTON_ROLE_COMMIT,
            )
            if reply != QMessageBox.Yes:
                return
        count = self.project.verify_image_labels(self.current_image, save=False)
        if count:
            self._schedule_project_save()
            self.canvas.set_polygons(self.project.get_labels(self.current_image))
            self._refresh_current_canvas_boxes()
            self._refresh_image_list_status_or_rebuild(self.current_image)
            self._refresh_blink_refine_state()
            self.log(tr("Accepted {0} AI draft(s) on current image.", self.current_lang).format(count))
        else:
            self.log(tr("No reviewable AI polygon drafts on current image.", self.current_lang))
        box_only_parts = list((draft_summary or {}).get("box_only_parts", []) or [])
        if box_only_parts:
            self.log(
                tr(
                    "Current image still has {0} AI box-only draft(s): {1}. Box-only drafts cannot enter training; run SAM from the box or redraw a polygon first.",
                    self.current_lang,
                ).format(len(box_only_parts), ", ".join(box_only_parts))
            )

    def accept_batch_ai_drafts(self):
        image_paths = [path for path in self.project.project_data.get("images", []) if path]
        if not image_paths:
            self.log(tr("No reviewable AI polygon drafts in the current project.", self.current_lang))
            return

        self._flush_pending_project_save(defer_for_navigation=False)
        summarize_many = getattr(self.project, "summarize_ai_drafts_for_images", None)
        if callable(summarize_many):
            summary = summarize_many(image_paths)
        else:
            image_summaries = []
            reviewable_count = 0
            box_only_count = 0
            summarize_one = getattr(self.project, "summarize_image_ai_drafts", None)
            for image_path in image_paths:
                item = summarize_one(image_path) if callable(summarize_one) else {}
                item_reviewable = len(item.get("reviewable_polygon_parts", []) or [])
                item_box_only = len(item.get("box_only_parts", []) or [])
                if item_reviewable or item_box_only:
                    image_summaries.append({"image_path": image_path, "reviewable_count": item_reviewable, "box_only_count": item_box_only})
                    reviewable_count += item_reviewable
                    box_only_count += item_box_only
            summary = {
                "images_with_drafts": image_summaries,
                "image_count": len(image_summaries),
                "reviewable_polygon_count": reviewable_count,
                "box_only_count": box_only_count,
            }

        reviewable_count = int(summary.get("reviewable_polygon_count", 0) or 0)
        image_count = int(summary.get("image_count", 0) or 0)
        box_only_count = int(summary.get("box_only_count", 0) or 0)
        if not reviewable_count:
            self.log(tr("No reviewable AI polygon drafts in the current project.", self.current_lang))
            if box_only_count:
                box_only_images = sum(1 for item in summary.get("images_with_drafts", []) if int(item.get("box_only_count", 0) or 0) > 0)
                self.log(
                    tr(
                        "{0} image(s) in the current project still have {1} AI box-only draft(s). Box-only drafts cannot enter training; run SAM from the box or redraw polygons first.",
                        self.current_lang,
                    ).format(box_only_images, box_only_count)
                )
            return

        reply = themed_yes_no_question(
            self,
            tr("Confirm AI Drafts", self.current_lang),
            tr(
                "Accept {0} AI polygon draft(s) from {1} image(s) in the current project?\n\nOnly drafts that already have polygons will become training labels. {2} box-only draft(s) will be skipped and stay pending.",
                self.current_lang,
            ).format(reviewable_count, image_count, box_only_count),
            confirm_role=BUTTON_ROLE_COMMIT,
        )
        if reply != QMessageBox.Yes:
            return

        verify_many = getattr(self.project, "verify_ai_drafts_for_images", None)
        if callable(verify_many):
            result = verify_many(image_paths)
            accepted_count = int(result.get("accepted_count", 0) or 0)
            accepted_images = int(result.get("accepted_images", 0) or 0)
        else:
            accepted_count = 0
            accepted_images = 0
            for image_path in image_paths:
                count = self.project.verify_image_labels(image_path)
                if count:
                    accepted_count += count
                    accepted_images += 1

        if self.current_image:
            self.canvas.set_polygons(self.project.get_labels(self.current_image))
            self._refresh_current_canvas_boxes()
        self.refresh_file_list()
        self._refresh_blink_refine_state()
        if accepted_count:
            self.log(
                tr("Accepted {0} AI polygon draft(s) from {1} image(s) in the current project.", self.current_lang).format(
                    accepted_count,
                    accepted_images,
                )
            )
        else:
            self.log(tr("No reviewable AI polygon drafts in the current project.", self.current_lang))
        if box_only_count:
            box_only_images = sum(1 for item in summary.get("images_with_drafts", []) if int(item.get("box_only_count", 0) or 0) > 0)
            self.log(
                tr(
                    "{0} image(s) in the current project still have {1} AI box-only draft(s). Box-only drafts cannot enter training; run SAM from the box or redraw polygons first.",
                    self.current_lang,
                ).format(box_only_images, box_only_count)
            )

    def _on_vlm_preannotation_error(self, message):
        self.log(tr("VLM first-mile preannotation failed: {0}", self.current_lang).format(message))
        QMessageBox.warning(self, tr("VLM Pre-Annotate", self.current_lang), str(message))

    def _on_vlm_preannotation_qthread_finished(self, worker=None):
        if not getattr(self, "vlm_preannotation_run_active", False):
            return
        worker = worker or self.sender()
        current_run_id = str(getattr(self, "vlm_preannotation_run_id", "") or "")
        worker_run_id = str(getattr(worker, "run_id", "") or "") if worker is not None else ""
        if worker_run_id and worker_run_id != current_run_id:
            runtime_log_event(
                "stale_vlm_worker_finished_skipped",
                worker_run_id=worker_run_id,
                current_run_id=current_run_id,
            )
            if hasattr(worker, "deleteLater"):
                worker.deleteLater()
            return
        worker_image = ""
        active_images = getattr(self, "vlm_preannotation_active_images", None)
        if isinstance(active_images, dict) and worker is not None:
            worker_image = active_images.pop(worker, "")
        if worker is not None:
            self.vlm_preannotation_threads = [
                thread
                for thread in (getattr(self, "vlm_preannotation_threads", []) or [])
                if thread is not worker
            ]
        runtime_log_event(
            "vlm_worker_finished",
            image=os.path.basename(str(worker_image or "")),
            active_count=len(getattr(self, "vlm_preannotation_threads", []) or []),
            queued_count=len(getattr(self, "vlm_preannotation_queue", []) or []),
            cancel_requested=bool(getattr(self, "vlm_preannotation_cancel_requested", False)),
            run_id=getattr(self, "vlm_preannotation_run_id", ""),
        )
        active = self._active_vlm_preannotation_threads()
        if getattr(self, "vlm_preannotation_cancel_requested", False):
            self.vlm_preannotation_queue = []
            if not active:
                self._finish_vlm_preannotation_run()
            return
        if getattr(self, "vlm_preannotation_queue", []):
            self._start_vlm_preannotation_workers()
            return
        if not active:
            self._finish_vlm_preannotation_run()

    def _on_vlm_preannotation_finished(self):
        self._on_vlm_preannotation_qthread_finished(self.sender())
