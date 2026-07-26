try:
    from AntSleap.ui.main_window_stage7_dependencies import *
except ImportError:
    from ui.main_window_stage7_dependencies import *


class MainWindowPredictionMixin:
    def clear_ai_labels(self):
        choose_scope = getattr(self, "_choose_clear_ai_scope", None)
        if callable(choose_scope):
            scope = choose_scope()
        else:
            scope = {
                "paths": list(getattr(self.project, "project_data", {}).get("images", []) or []) or ["__all__"],
                "count": 1,
                "label": tr("All project images", self.current_lang),
                "legacy_message": True,
            }
        if not scope:
            return
        paths = list(scope.get("paths", []) or [])
        expected_count = int(scope.get("count", 0) or 0)
        scope_label = str(scope.get("label", "") or tr("All project images", self.current_lang))
        if expected_count <= 0 or not paths:
            self.log(tr("No AI labels found in the selected scope.", self.current_lang))
            return
        if scope.get("legacy_message"):
            message = tr("Clear all AI labels from the current project?", self.current_lang)
        else:
            message = (
                tr("Clear selected AI labels?", self.current_lang)
                + "\n\n"
                + tr(
                    "This will remove {0} AI label(s) from {1} image(s). Manual and confirmed labels are kept.",
                    self.current_lang,
                ).format(expected_count, len(paths))
                + f"\n{scope_label}"
            )
        if themed_yes_no_question(
            self,
            tr("Clear AI Labels", self.current_lang),
            message,
            confirm_role=BUTTON_ROLE_DESTRUCTIVE,
        ) != QMessageBox.Yes:
            return
        remove_auto_labels_for_images = getattr(self.project, "remove_auto_labels_for_images", None)
        if callable(remove_auto_labels_for_images):
            c = remove_auto_labels_for_images(paths, save=False)
        else:
            remove_auto_labels = getattr(self.project, "remove_auto_labels")
            try:
                c = remove_auto_labels(save=False)
            except TypeError:
                c = remove_auto_labels()
        if c:
            self._schedule_project_save()
        self.refresh_file_list()
        if self.current_image:
            self.canvas.set_polygons(self.project.get_labels(self.current_image))
            self._refresh_current_canvas_boxes()
        self._refresh_blink_refine_state()
        self.log(tr("Removed {0} AI labels from {1}.", self.current_lang).format(c, scope_label))

    def _extract_prediction_payload(self, payload):
        """兼容新旧推理输出协议，统一返回 polygons + auto_boxes。"""
        polygons = {}
        auto_boxes = {}
        taxonomy_set = set(self.project.project_data.get("taxonomy", []))

        if not isinstance(payload, dict):
            return polygons, auto_boxes

        # 新协议: {polygons: {...}, auto_boxes: {...}}
        if isinstance(payload.get("polygons"), dict):
            polygons = {
                str(part): points
                for part, points in payload.get("polygons", {}).items()
                if str(part) in taxonomy_set
            }
            raw_auto_boxes = payload.get("auto_boxes", {}) if isinstance(payload.get("auto_boxes"), dict) else {}
            auto_boxes = {
                str(part): box
                for part, box in raw_auto_boxes.items()
                if str(part) in taxonomy_set
            }
            return polygons, auto_boxes

        # 旧协议回退: {part: polygon, part_BOX: box_polygon}
        for key, value in payload.items():
            if key.endswith("_BOX") and isinstance(value, list):
                xs = [p[0] for p in value if isinstance(p, (list, tuple)) and len(p) >= 2]
                ys = [p[1] for p in value if isinstance(p, (list, tuple)) and len(p) >= 2]
                if xs and ys:
                    real_part = key.replace("_BOX", "")
                    auto_boxes[real_part] = [float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))]
            elif isinstance(value, list):
                if key in taxonomy_set:
                    polygons[key] = value

        return polygons, auto_boxes

    def _is_unconfirmed_ai_draft(self, image_path, part_name):
        entry = self.project.project_data.get("labels", {}).get(image_path, {})
        if not isinstance(entry, dict):
            return False
        descriptions = entry.get("descriptions", {}) if isinstance(entry.get("descriptions", {}), dict) else {}
        if descriptions.get(part_name) != "Auto-Annotated":
            return False
        meta = entry.get("auto_box_meta", {}) if isinstance(entry.get("auto_box_meta", {}), dict) else {}
        review_status = ""
        if isinstance(meta.get(part_name), dict):
            review_status = str(meta.get(part_name, {}).get("review_status") or "").strip()
        return review_status != "confirmed"

    def _auto_box_meta_for_part(self, image_path, part_name):
        get_meta = getattr(self.project, "get_auto_box_meta", None)
        meta = None
        if callable(get_meta):
            try:
                meta = get_meta(image_path)
            except Exception:
                meta = None
        if not isinstance(meta, dict):
            entry = self.project.project_data.get("labels", {}).get(image_path, {})
            meta = entry.get("auto_box_meta", {}) if isinstance(entry, dict) and isinstance(entry.get("auto_box_meta", {}), dict) else {}
        part_meta = meta.get(part_name, {}) if isinstance(meta.get(part_name), dict) else {}
        return dict(part_meta)

    def _auto_box_source_for_part(self, image_path, part_name):
        meta = self._auto_box_meta_for_part(image_path, part_name)
        return str(meta.get("source") or AUTO_BOX_SOURCE_MODEL).strip() or AUTO_BOX_SOURCE_MODEL

    def _auto_box_review_status_for_part(self, image_path, part_name):
        meta = self._auto_box_meta_for_part(image_path, part_name)
        return str(meta.get("review_status") or AUTO_BOX_REVIEW_DRAFT).strip() or AUTO_BOX_REVIEW_DRAFT

    def _apply_prediction_to_project(self, image_path, payload, only_new=True, save=True, source=AUTO_BOX_SOURCE_MODEL):
        polygons, auto_boxes = self._extract_prediction_payload(payload)
        existing_parts = set(self.project.get_labels(image_path).keys())
        saved_count = 0

        for part_name, points in polygons.items():
            if only_new and not self._can_replace_existing_auto_annotation(image_path, part_name, source):
                continue

            auto_box = auto_boxes.get(part_name)
            if (not auto_box) and isinstance(points, list) and points:
                xs = [pt[0] for pt in points if isinstance(pt, (list, tuple)) and len(pt) >= 2]
                ys = [pt[1] for pt in points if isinstance(pt, (list, tuple)) and len(pt) >= 2]
                if xs and ys:
                    auto_box = [float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))]

            self.project.update_label(
                image_path,
                part_name,
                points,
                "Auto-Annotated",
                auto_box=auto_box,
                save=False,
                training_source=source,
                training_review_status="draft",
                training_accepted_via="",
            )
            if auto_box:
                update_auto_box = getattr(self.project, "update_auto_box", None)
                if callable(update_auto_box):
                    update_auto_box(
                        image_path,
                        part_name,
                        auto_box,
                        source_meta=self._auto_annotation_source_meta(source),
                        save=False,
                    )
            existing_parts.add(part_name)
            saved_count += 1

        if saved_count and save:
            self.project.save_project()
        return saved_count, len(polygons)

    def run_prediction(self):
        if not self.current_image:
            return
        if _runtime_parent_backend(self.project, self.model_backend) == EXTERNAL_BACKEND_ID:
            self.run_external_prediction(self.current_image)
            return
        self.ensure_locator_preloaded()
        if not self._confirm_legacy_locator_selection_if_needed():
            return
        self.ensure_sam_preloaded()
        self.log(tr("Running inference on: {0}...", self.current_lang).format(os.path.basename(self.current_image)))
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            prediction_context = dict(self._active_model_profile_context() or {})
            get_image_uid = getattr(self.project, "get_image_uid", None)
            if callable(get_image_uid):
                prediction_context["image_uid"] = str(
                    get_image_uid(self.current_image) or ""
                )
            ps = self.engine.predict_full_pipeline(
                image_path=self.current_image,
                current_taxonomy=self.project.project_data["taxonomy"],
                locator_scope=self.project.get_locator_scope(),
                conf_thresh=self.inf_conf,
                adapt_thresh=self.inf_adapt,
                box_pad=self.inf_pad,
                noise_floor=self.inf_noise_floor,
                poly_epsilon=self.inf_poly_epsilon,
                project_route_manifest=self._active_project_route_manifest(),
                model_profile_context=prediction_context,
            )
            count, total_detected = self._apply_prediction_to_project(
                self.current_image,
                ps,
                only_new=True,
                save=False,
                source=AUTO_BOX_SOURCE_MODEL,
            )
            if count:
                self._schedule_project_save()

            labels = self.project.get_labels(self.current_image)
            manual_boxes = self.project.get_boxes(self.current_image)
            auto_boxes, vlm_boxes = self._auto_boxes_for_canvas(self.current_image)
            self.canvas.set_polygons(labels)
            self.canvas.set_boxes(manual_boxes, auto_boxes, self._current_shrink_loose_boxes(), vlm=vlm_boxes)
            self._refresh_image_list_status_or_rebuild(self.current_image)
            self._refresh_blink_refine_state()
            self._log_route_usage_summary(ps, self.current_image)
            self.log(tr("Inference complete. Detected {0} parts, saved {1} new labels.", self.current_lang).format(total_detected, count))
        except Exception as exc:
            message = tr("Inference failed: {0}", self.current_lang).format(str(exc))
            self.log(message)
            QMessageBox.critical(
                self,
                tr("Error", self.current_lang),
                message,
            )
        finally:
            QApplication.restoreOverrideCursor()

    def run_external_prediction(self, image_path):
        self._flush_pending_project_save(defer_for_navigation=False)
        self.log(tr("Running inference on: {0}...", self.current_lang).format(os.path.basename(image_path)))
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            result = self._external_backend_runner().run_predict(
                image_path,
                model_manifest=self._active_external_backend_config().get("model_manifest", ""),
            )
            count, total_detected = self._apply_prediction_to_project(
                image_path,
                result.get("payload", {}),
                only_new=True,
                save=False,
                source=AUTO_BOX_SOURCE_EXTERNAL_MODEL,
            )
            if count:
                self._schedule_project_save()
            if image_path == self.current_image:
                self.canvas.set_polygons(self.project.get_labels(image_path))
                self._refresh_current_canvas_boxes()
                self._refresh_blink_refine_state()
            self._refresh_image_list_status_or_rebuild(image_path)
            self.log(f"External inference complete. Contract: {result.get('contract_json')}")
            self.log(tr("Inference complete. Detected {0} parts, saved {1} new labels.", self.current_lang).format(total_detected, count))
        except Exception as exc:
            self.log(f"External inference failed: {exc}")
            QMessageBox.critical(self, tr("Error", self.current_lang), str(exc))
        finally:
            QApplication.restoreOverrideCursor()

    def verify_current_image(self):
        if self.current_image:
            count = self.project.verify_image_labels(self.current_image, save=False)
            if count:
                self._schedule_project_save()
                self.canvas.set_polygons(self.project.get_labels(self.current_image))
                self._refresh_current_canvas_boxes()
                self._refresh_image_list_status_or_rebuild(self.current_image)
                self._refresh_blink_refine_state()

    def _start_external_batch_inference(self, image_paths):
        if getattr(self, "external_batch_inference_thread", None) is not None and self.external_batch_inference_thread.isRunning():
            QMessageBox.information(
                self,
                tr("Batch Inference", self.current_lang),
                tr("Batch inference is already running.", self.current_lang),
            )
            return

        self._flush_pending_project_save(defer_for_navigation=False)
        self.external_batch_inference_failed = False
        self.external_batch_inference_saved_any = False
        self.btn_batch.setEnabled(False)
        self.btn_predict.setEnabled(False)

        progress = QProgressDialog(
            tr("Starting batch inference on {0} images...", self.current_lang).format(len(image_paths)),
            "",
            0,
            max(1, len(image_paths)),
            self,
        )
        progress.setWindowTitle(tr("Batch Inference", self.current_lang))
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setCancelButton(None)
        self._prepare_progress_dialog(progress, width=520)
        progress.show()
        self.external_batch_inference_progress_dialog = progress
        task_context = self._capture_project_task_context()
        self.external_batch_inference_project_context = task_context

        backend_config = self._active_external_backend_config()
        thread = ExternalBatchInferenceThread(
            self.project,
            backend_config,
            image_paths,
            model_manifest=backend_config.get("model_manifest", ""),
            lang=self.current_lang,
        )
        if hasattr(thread, "translate"):
            thread.translate = tr
        self.external_batch_inference_thread = thread

        def on_progress(done, total, label):
            total = max(0, int(total))
            done = max(0, int(done))
            if total > 0 and progress.maximum() != total:
                progress.setRange(0, total)
            if total > 0:
                progress.setValue(min(done, total))
            message = tr("Starting batch inference on {0} images...", self.current_lang).format(total)
            if label:
                message = f"{message}\n{self._short_progress_path(label)}"
            progress.setLabelText(message)

        def on_result(image_path, result):
            if not self._project_task_context_matches(task_context):
                self._log_stale_project_task_result("external_batch_inference_result", task_context)
                return
            saved, total = self._apply_prediction_to_project(
                image_path,
                result.get("payload", {}),
                only_new=True,
                save=False,
                source=AUTO_BOX_SOURCE_EXTERNAL_MODEL,
            )
            if saved:
                self.external_batch_inference_saved_any = True
            self.log(tr("Batch saved {0}/{1} for {2}", self.current_lang).format(saved, total, os.path.basename(image_path)))

        def on_error(message):
            if not self._project_task_context_matches(task_context):
                self._log_stale_project_task_result("external_batch_inference_error", task_context)
                return
            self.external_batch_inference_failed = True
            self.log(tr("External batch inference failed: {0}", self.current_lang).format(message))
            QMessageBox.critical(
                self,
                tr("Error", self.current_lang),
                tr("External batch inference failed: {0}", self.current_lang).format(message),
            )

        def on_finished():
            context_matches = self._project_task_context_matches(task_context)
            if context_matches and getattr(self, "external_batch_inference_saved_any", False):
                self.project.save_project()
            elif not context_matches:
                self._log_stale_project_task_result("external_batch_inference_finished", task_context)
            progress.close()
            progress.deleteLater()
            if getattr(self, "external_batch_inference_progress_dialog", None) is progress:
                self.external_batch_inference_progress_dialog = None
            if getattr(self, "external_batch_inference_thread", None) is thread:
                self.external_batch_inference_thread = None
            thread.deleteLater()
            self.btn_batch.setEnabled(True)
            self.btn_predict.setEnabled(True)
            if context_matches:
                self.refresh_file_list()
                self._refresh_blink_refine_state()
            if not getattr(self, "external_batch_inference_failed", False):
                self.log(tr("External batch inference finished.", self.current_lang))

        thread.log_signal.connect(self.log)
        thread.progress_signal.connect(on_progress)
        thread.result_signal.connect(on_result)
        thread.error_signal.connect(on_error)
        thread.finished_signal.connect(on_finished)
        thread.start()

    def run_batch_inference(self):
        ul = [img for img in self.project.project_data["images"] if not self.project.get_labels(img)]
        if not ul:
            return
        if _runtime_parent_backend(self.project, self.model_backend) == EXTERNAL_BACKEND_ID:
            if themed_yes_no_question(
                self,
                tr("Batch", self.current_lang),
                tr("Annotate {0} images?", self.current_lang).format(len(ul)),
                confirm_role=BUTTON_ROLE_RUN,
            ) == QMessageBox.Yes:
                self._start_external_batch_inference(ul)
            return
        self.ensure_locator_preloaded()
        if not self._confirm_legacy_locator_selection_if_needed():
            return
        self.ensure_sam_preloaded()
        if themed_yes_no_question(
            self,
            tr("Batch", self.current_lang),
            tr("Annotate {0} images?", self.current_lang).format(len(ul)),
            confirm_role=BUTTON_ROLE_RUN,
        ) == QMessageBox.Yes:
            self.btn_batch.setEnabled(False)
            self.btn_predict.setEnabled(False)

            tax = self.project.project_data["taxonomy"]
            locator_scope = self.project.get_locator_scope()
            self.log(tr("Starting Batch Inference with Taxonomy ({0}): {1}", self.current_lang).format(len(tax), tax))
            self.log(tr("Starting Batch Inference with Locator Scope ({0}): {1}", self.current_lang).format(len(locator_scope), locator_scope))

            params = {
                'conf': self.inf_conf, 'adapt': self.inf_adapt,
                'pad': self.inf_pad, 'noise_floor': self.inf_noise_floor,
                'poly_epsilon': self.inf_poly_epsilon,
            }
            self.inf_thread = InferenceThread(
                self.engine,
                ul,
                tax,
                locator_scope,
                params,
                project_route_manifest=self._active_project_route_manifest(),
                model_profile_context=self._active_model_profile_context(),
                lang=self.current_lang,
            )
            if hasattr(self.inf_thread, "translate"):
                self.inf_thread.translate = tr
            self.inf_thread.log_signal.connect(self.log) # Fix: Connect log signal
            task_context = self._capture_project_task_context()
            self.batch_inference_project_context = task_context

            def on_batch_res(p, d):
                if not self._project_task_context_matches(task_context):
                    self._log_stale_project_task_result("batch_inference_result", task_context)
                    return
                saved, total = self._apply_prediction_to_project(
                    p,
                    d,
                    only_new=True,
                    save=False,
                    source=AUTO_BOX_SOURCE_MODEL,
                )
                self._log_route_usage_summary(
                    d,
                    p,
                    prefix=ui_text("Route usage for batch image {0}", self.current_lang).format(os.path.basename(p)),
                )
                self.log(tr("Batch saved {0}/{1} for {2}", self.current_lang).format(saved, total, os.path.basename(p)))

            def on_batch_finished():
                if self._project_task_context_matches(task_context):
                    self.project.save_project()
                    self.refresh_file_list()
                    self._refresh_blink_refine_state()
                else:
                    self._log_stale_project_task_result("batch_inference_finished", task_context)
                self.btn_batch.setEnabled(True)
                self.btn_predict.setEnabled(True)

            def on_batch_error(image_path, error_message):
                if not self._project_task_context_matches(task_context):
                    self._log_stale_project_task_result(
                        "batch_inference_error", task_context
                    )
                    return
                message = tr(
                    "Batch inference failed for {0}: {1}",
                    self.current_lang,
                ).format(os.path.basename(image_path), error_message)
                self.log(message)
                QMessageBox.critical(
                    self,
                    tr("Error", self.current_lang),
                    message,
                )

            self.inf_thread.result_signal.connect(on_batch_res)
            self.inf_thread.error_signal.connect(on_batch_error)
            self.inf_thread.finished_signal.connect(on_batch_finished)
            self.inf_thread.start()
