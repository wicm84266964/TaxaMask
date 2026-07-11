try:
    from AntSleap.ui.main_window_stage6_dependencies import *
except ImportError:
    from ui.main_window_stage6_dependencies import *


class MainWindowAnnotationMixin:
    def _auto_boxes_for_canvas(self, image_path):
        splitter = getattr(self.project, "split_auto_boxes_by_source", None)
        if callable(splitter):
            try:
                model_boxes, vlm_boxes = splitter(image_path)
                return model_boxes if isinstance(model_boxes, dict) else {}, vlm_boxes if isinstance(vlm_boxes, dict) else {}
            except Exception:
                pass
        auto_boxes = self.project.get_auto_boxes(image_path)
        if not isinstance(auto_boxes, dict):
            return {}, {}
        meta = {}
        get_meta = getattr(self.project, "get_auto_box_meta", None)
        if callable(get_meta):
            try:
                meta = get_meta(image_path)
            except Exception:
                meta = {}
        meta = meta if isinstance(meta, dict) else {}
        model_boxes = {}
        vlm_boxes = {}
        for part_name, box in auto_boxes.items():
            part_meta = meta.get(part_name, {}) if isinstance(meta.get(part_name), dict) else {}
            if part_meta.get("source") == AUTO_BOX_SOURCE_VLM:
                vlm_boxes[part_name] = box
            else:
                model_boxes[part_name] = box
        return model_boxes, vlm_boxes

    def _refresh_current_canvas_boxes(self):
        if not self.current_image:
            return
        model_auto_boxes, vlm_auto_boxes = self._auto_boxes_for_canvas(self.current_image)
        self.canvas.set_boxes(
            self.project.get_boxes(self.current_image),
            model_auto_boxes,
            self._current_shrink_loose_boxes(),
            vlm=vlm_auto_boxes,
        )

    def _refresh_annotation_box_constraints(self):
        if not hasattr(self, "canvas"):
            return
        context = dict(getattr(self, "current_blink_context", {}) or self._current_blink_context())
        ratio = None
        lock_parent_ratio = True
        if hasattr(self, "check_lock_parent_box_ratio"):
            lock_parent_ratio = self.check_lock_parent_box_ratio.isChecked()
        if (
            self._active_box_tool_role() in {"sam", "annotation"}
            and lock_parent_ratio
            and context.get("role") == "parent"
        ):
            ratio = self._parent_box_aspect_ratio(context.get("parent_part"))
        self.canvas.set_annotation_box_aspect_ratio(ratio)

    def _active_box_tool_role(self):
        if hasattr(self, "radio_loose_shrink_box") and self.radio_loose_shrink_box.isChecked():
            return "shrink"
        if hasattr(self, "radio_annotation_box") and self.radio_annotation_box.isChecked():
            return "annotation"
        if hasattr(self, "radio_box") and self.radio_box.isChecked():
            return "sam"
        return "other"

    def on_enhancement_changed(self):
        self.canvas.set_enhancements(0, 1.0)

    def on_tool_changed(self):
        if self.radio_magic.isChecked():
            self.canvas.set_mode("MAGIC_WAND")
            self._refresh_annotation_box_constraints()
        elif self.radio_box.isChecked():
            self.canvas.set_mode("BOX_PROMPT")
            self._refresh_annotation_box_constraints()
        elif self.radio_annotation_box.isChecked() or self.radio_loose_shrink_box.isChecked():
            self.canvas.set_mode("ANNOTATION_BOX")
            self._refresh_annotation_box_constraints()
        elif self.radio_scale.isChecked():
            self.canvas.set_mode("SCALE")
            self._refresh_annotation_box_constraints()
        else:
            self.canvas.set_mode("DRAW")
            self._refresh_annotation_box_constraints()

    def on_magic_wand_clicked(self, x, y):
        self._request_sam_point(x, y)

    def on_magic_box_completed(self, x1, y1, x2, y2):
        self._request_sam_box(x1, y1, x2, y2)

    def _sam_worker_ready(self):
        return bool(self.sam_worker and getattr(self.sam_worker, "model", None) is not None)

    def _on_sam_model_loaded(self):
        self.log(tr("SAM Model Loaded and Ready!", self.current_lang))

    def _begin_sam_prompt(self):
        if not self.current_image:
            return None
        if not self._sam_worker_ready():
            self.ensure_sam_preloaded()
            self.log(tr("SAM is still loading. Try the box again after the ready message.", self.current_lang))
            return None
        if self.sam_busy:
            self.log(tr("SAM is still processing the previous prompt. Please wait a moment.", self.current_lang))
            return None
        part = self._current_part_name()
        if not part:
            return None
        self.sam_busy = True
        self.pending_sam_part = part
        self.pending_sam_image = self.current_image
        self.pending_sam_description = self.desc_box.toPlainText()
        self.pending_sam_project_context = self._capture_project_task_context()
        return self.current_image, part

    def _request_sam_point(self, x, y):
        prompt = self._begin_sam_prompt()
        if not prompt:
            return
        image_path, _part = prompt
        self.sam_point_requested.emit(image_path, float(x), float(y))

    def _request_sam_box(self, x1, y1, x2, y2):
        prompt = self._begin_sam_prompt()
        if not prompt:
            return
        image_path, _part = prompt
        self.sam_box_requested.emit(image_path, float(x1), float(y1), float(x2), float(y2))

    def on_annotation_box_completed(self, x1, y1, x2, y2):
        part = self._current_part_name()
        clean_box = _clean_box([x1, y1, x2, y2])
        if not self.current_image or not part or not clean_box:
            return

        context = self._current_blink_context()
        if self._active_box_tool_role() == "shrink":
            if context.get("role") != "child":
                self._warn_blink_context(
                    tr("Blink shrink start boxes are only used for child structures. Select a child structure first.", self.current_lang)
                )
                return
            update_loose_box = getattr(self.project, "update_shrink_loose_box", None)
            if callable(update_loose_box):
                update_loose_box(self.current_image, part, clean_box, save=False)
            self._refresh_current_canvas_boxes()
            self.log(tr("Saved Blink shrink start box for {0}.", self.current_lang).format(part))
        else:
            existing_points = self.project.get_labels(self.current_image).get(part, [])
            self.project.update_label(
                self.current_image,
                part,
                existing_points,
                self.desc_box.toPlainText(),
                box=clean_box,
                save=False,
            )
            self._refresh_current_canvas_boxes()
            if context.get("role") == "child" and context.get("parent_part"):
                self.project.remember_blink_context_parent(part, context.get("parent_part"), save=False)
            self.log(tr("Saved manual ROI box for {0}.", self.current_lang).format(part))
        self._schedule_project_save()
        self._refresh_blink_refine_state()

    def on_sam_mask_generated(self, pts, box=None):
        image_path = self.pending_sam_image or self.current_image
        part = self.pending_sam_part or self._current_part_name()
        description_text = self.pending_sam_description
        task_context = dict(getattr(self, "pending_sam_project_context", {}) or {})
        self.sam_busy = False
        self.pending_sam_part = None
        self.pending_sam_image = None
        self.pending_sam_description = ""
        self.pending_sam_project_context = {}
        if task_context and not self._project_task_context_matches(task_context):
            self._log_stale_project_task_result("sam_mask_result", task_context)
            return
        if image_path and part:
            self.on_polygon_completed(part, pts, box, image_path=image_path, description_text=description_text)

    def on_sam_prompt_failed(self, message):
        self.sam_busy = False
        self.pending_sam_part = None
        self.pending_sam_image = None
        self.pending_sam_description = ""
        self.pending_sam_project_context = {}
        if message:
            self.log(str(message))

    def on_polygon_completed(self, p, pts, box=None, image_path=None, description_text=None):
        target_image = image_path or self.current_image
        if target_image:
            if not pts:
                # Empty points means DELETE
                self.project.delete_label(target_image, p, save=False)
            else:
                label_description = self.desc_box.toPlainText() if description_text is None else str(description_text)
                if label_description.strip() == "Auto-Annotated":
                    label_description = ""
                self.project.update_label(target_image, p, pts, label_description, box=box, save=False)
            self._schedule_project_save()
            is_current_image = bool(self.current_image) and self._same_project_image_path(target_image, self.current_image)
            if is_current_image:
                self.canvas.set_polygons(self.project.get_labels(self.current_image))
                self._refresh_current_canvas_boxes()
            self._refresh_current_image_list_status(target_image)
            if is_current_image and self.check_morpho.isChecked():
                self.update_measurements(p)
            if is_current_image:
                self._refresh_blink_refine_state()

    def toggle_morphometrics(self, state):
        on = self.check_morpho.isChecked()
        self.radio_scale.setVisible(on)
        self.group_morpho.setVisible(on)
        p = self._current_part_name()
        if on and p:
            self.update_measurements(p)

    def on_scale_defined(self, lpx):
        v, ok = QInputDialog.getDouble(self, tr("Scale Tool", self.current_lang), tr("mm:", self.current_lang), 1.0, 0.001, 1000.0, 3)
        if ok and self.current_image:
            try:
                self.project.set_scale(self.current_image, lpx/v, save=False)
            except TypeError:
                self.project.set_scale(self.current_image, lpx/v)
            self._schedule_project_save()
            self.refresh_ui()

    def update_measurements(self, p):
        if not self.current_image or not p:
            return
        sc = self.project.get_scale(self.current_image)
        if not sc:
            self.label_measurements.setText(tr("No Scale.", self.current_lang))
            return
        pts = self.project.get_labels(self.current_image).get(p)
        if pts and len(pts) > 2:
            import cv2
            pts_np = np.array(pts, dtype=np.float32)
            a = cv2.contourArea(pts_np) / (sc*sc)
            peri = cv2.arcLength(pts_np, True) / sc
            self.label_measurements.setText(tr("Area: {0:.4f} mm2\nPeri: {1:.4f} mm", self.current_lang).format(a, peri))
        else:
            self.label_measurements.setText(tr("No Polygon.", self.current_lang))

    def _auto_annotation_source_meta(self, source=AUTO_BOX_SOURCE_MODEL):
        return {
            "source": source,
            "review_status": AUTO_BOX_REVIEW_DRAFT,
        }

    def _can_replace_existing_auto_annotation(self, image_path, part_name, new_source):
        existing_points = self.project.get_labels(image_path).get(part_name, [])
        if existing_points and not self._is_unconfirmed_ai_draft(image_path, part_name):
            return False
        existing_auto_boxes = self.project.get_auto_boxes(image_path)
        has_auto_box = isinstance(existing_auto_boxes, dict) and part_name in existing_auto_boxes
        if not existing_points and not has_auto_box:
            return True
        existing_status = self._auto_box_review_status_for_part(image_path, part_name)
        if existing_status == AUTO_BOX_REVIEW_CONFIRMED:
            return False
        existing_source = self._auto_box_source_for_part(image_path, part_name)
        if new_source == AUTO_BOX_SOURCE_VLM:
            return existing_source == AUTO_BOX_SOURCE_VLM
        return True

    def init_sam(self):
        if self.sam_thread and self.sam_thread.isRunning():
            return
        if self.sam_worker and getattr(self.sam_worker, "model", None) is not None:
            return
        mp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "weights", "sam_b.pt")
        self.log(tr("Initializing SAM (Segment Anything) on active compute device...", self.current_lang))
        self.sam_thread = QThread()
        # Pass current epsilon to worker
        self.sam_worker = SAMWorker(model_type=mp, poly_epsilon=self.inf_poly_epsilon, device=self.runtime_device)
        self.sam_worker.moveToThread(self.sam_thread)
        self.sam_thread.started.connect(self.sam_worker.load_model)
        queued_connection = Qt.ConnectionType.QueuedConnection
        if hasattr(self.sam_worker, "predict_point"):
            self.sam_point_requested.connect(self.sam_worker.predict_point, queued_connection)
        if hasattr(self.sam_worker, "predict_box"):
            self.sam_box_requested.connect(self.sam_worker.predict_box, queued_connection)
        self.sam_worker.mask_generated.connect(self.on_sam_mask_generated)
        if hasattr(self.sam_worker, "prompt_failed"):
            self.sam_worker.prompt_failed.connect(self.on_sam_prompt_failed)
        self.sam_worker.model_loaded.connect(self._on_sam_model_loaded)
        self.sam_worker.model_load_error.connect(lambda message: self.log(str(message)))
        self.sam_thread.start()

    def ensure_sam_preloaded(self):
        started = False
        if self.sam_thread and self.sam_thread.isRunning():
            pass
        elif self.sam_worker and getattr(self.sam_worker, "model", None) is not None:
            pass
        else:
            self.init_sam()
            started = True

        if self._preload_engine_parts_model_async():
            started = True
        return started
