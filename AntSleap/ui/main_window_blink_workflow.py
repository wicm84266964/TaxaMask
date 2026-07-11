try:
    from AntSleap.ui.main_window_stage6_dependencies import *
except ImportError:
    from ui.main_window_stage6_dependencies import *


class MainWindowBlinkWorkflowMixin:
    def _is_child_training_running(self):
        blink_lab = getattr(self, "blink_lab", None)
        thread = getattr(blink_lab, "training_thread", None) if blink_lab is not None else None
        return bool(thread and thread.isRunning())

    def _connect_child_training_progress(self):
        blink_lab = getattr(self, "blink_lab", None)
        thread = getattr(blink_lab, "training_thread", None) if blink_lab is not None else None
        if thread is None or getattr(thread, "_taxamask_shared_progress_connected", False):
            return
        thread._taxamask_shared_progress_connected = True
        thread.progress_signal.connect(lambda value: self._set_training_progress("child", None, value))
        thread.result_signal.connect(self._on_child_training_result)
        thread.error_signal.connect(self._on_child_training_error)
        thread.cancelled_signal.connect(self._on_child_training_cancelled)
        thread.finished.connect(self._on_child_training_finished)

    def _on_child_training_result(self, save_path):
        self.child_training_failed = not bool(save_path)
        if save_path:
            self._set_training_progress("child", tr("Child-part expert training finished.", self.current_lang), 100)
        else:
            self._set_training_progress("child", tr("Child-part expert training failed.", self.current_lang), self.progress.value())

    def _on_child_training_error(self, _error_msg):
        self.child_training_failed = True
        self._set_training_progress("child", tr("Child-part expert training failed.", self.current_lang), self.progress.value())

    def _on_child_training_cancelled(self):
        self.child_training_cancel_requested = True
        self._set_training_progress("child", tr("Training cancelled.", self.current_lang), self.progress.value())

    def _on_child_training_finished(self):
        if self.active_training_kind == "child" and not self.child_training_failed and not self.child_training_cancel_requested:
            self._set_training_progress("child", tr("Child-part expert training finished.", self.current_lang), 100)
        if hasattr(self, "btn_train"):
            self.btn_train.setEnabled(True)
        if hasattr(self, "btn_blink_stop_training"):
            self.btn_blink_stop_training.setEnabled(False)
        self.child_training_failed = False
        self.child_training_cancel_requested = False
        self._refresh_blink_refine_state()

    def run_blink_child_auto_annotate(self):
        context = self._active_child_blink_context(require_ready=True)
        if not context or not self.current_image:
            return
        child_part = context.get("child_part")
        parent_part = context.get("parent_part")
        parent_box = context.get("parent_box")
        self.log(tr("Running child auto-annotation for {0} via {1}.", self.current_lang).format(child_part, parent_part))
        try:
            expert_result = self.engine.cascade_manager.infer_child_part(
                self.current_image,
                parent_box,
                child_part,
                parent_part=parent_part,
                route_manifest=self.project.get_cascade_routes(),
            )
            if not isinstance(expert_result, dict):
                self._warn_blink_context(tr("No usable route expert result was returned for this child structure.", self.current_lang))
                return
            raw_box = _clean_box(expert_result.get("box"))
            if not raw_box:
                self._warn_blink_context(tr("The route expert did not return a valid child box.", self.current_lang))
                return
            image_bgr = cv2.imread(self.current_image)
            if image_bgr is None:
                raise RuntimeError(tr("Could not read the current image.", self.current_lang))
            image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
            polygon = self.engine.predict_base_sam_polygon(image_rgb, raw_box, poly_epsilon=self.inf_poly_epsilon)
            if polygon and len(polygon) >= 3:
                self.project.update_label(self.current_image, child_part, polygon, self.desc_box.toPlainText(), box=raw_box, save=False)
                self.canvas.set_polygons(self.project.get_labels(self.current_image))
                self._refresh_current_canvas_boxes()
                self.log(tr("Generated child draft polygon for {0}.", self.current_lang).format(child_part))
            else:
                existing_points = self.project.get_labels(self.current_image).get(child_part, [])
                self.project.update_label(self.current_image, child_part, existing_points, self.desc_box.toPlainText(), box=raw_box, save=False)
                self._refresh_current_canvas_boxes()
                self.log(tr("Route expert produced a child box for {0}; refine polygon manually.", self.current_lang).format(child_part))
            self.project.remember_blink_context_parent(child_part, parent_part, save=False)
            self._schedule_project_save()
            self._refresh_blink_refine_state()
        except Exception as exc:
            self._warn_blink_context(tr("Child auto-annotation failed: {0}", self.current_lang).format(str(exc)))

    def _load_blink_refiner_class(self):
        if "core.blink_refiner" in sys.modules:
            from core.blink_refiner import BlinkRefiner
            return BlinkRefiner
        try:
            from AntSleap.core.blink_refiner import BlinkRefiner
        except ImportError:
            from core.blink_refiner import BlinkRefiner
        return BlinkRefiner

    def _active_blink_auto_shrink_steps(self):
        child_defaults = _runtime_child_backend_defaults(self.project)
        try:
            value = int(child_defaults.get("auto_shrink_steps", self.blink_auto_shrink_steps))
        except Exception:
            value = self.blink_auto_shrink_steps
        try:
            value = int(value)
        except Exception:
            value = DEFAULT_CHILD_AUTO_SHRINK_STEPS
        return max(1, min(200, value))

    def _blink_parent_context_for_image(self, image_path, child_part, parent_part):
        previous_current = self.current_image
        try:
            self.current_image = image_path
            parent_box, parent_box_source = self._parent_context_box(parent_part)
        finally:
            self.current_image = previous_current
        if not parent_box:
            return None
        return {
            "parent_part": parent_part,
            "parent_box": parent_box,
            "source": parent_box_source or "workbench",
        }

    def _prepared_blink_auto_shrink_images(self, child_part, parent_part):
        prepared = []
        missing_polygon = 0
        missing_loose_box = 0
        missing_parent_box = 0
        existing_trajectory = 0
        for image_path in self.project.project_data.get("images", []):
            if not image_path:
                continue
            labels = self.project.project_data.get("labels", {}).get(image_path, {})
            parts = labels.get("parts", {}) if isinstance(labels.get("parts", {}), dict) else {}
            polygon = parts.get(child_part, [])
            if not polygon or len(polygon) < 3:
                missing_polygon += 1
                continue
            loose_boxes = labels.get("shrink_loose_boxes", {}) if isinstance(labels.get("shrink_loose_boxes", {}), dict) else {}
            loose_box = _clean_box(loose_boxes.get(child_part))
            if not loose_box:
                missing_loose_box += 1
                continue
            trajectories = labels.get("trajectories", {}) if isinstance(labels.get("trajectories", {}), dict) else {}
            if child_part in trajectories:
                existing_trajectory += 1
                continue
            parent_context = self._blink_parent_context_for_image(image_path, child_part, parent_part)
            if not parent_context:
                missing_parent_box += 1
                continue
            prepared.append({
                "image_path": image_path,
                "polygon": polygon,
                "loose_box": loose_box,
                "parent_context": parent_context,
            })
        return {
            "prepared": prepared,
            "missing_polygon": missing_polygon,
            "missing_loose_box": missing_loose_box,
            "missing_parent_box": missing_parent_box,
            "existing_trajectory": existing_trajectory,
        }

    def _generate_blink_shrink_for_image(self, image_path, child_part, polygon, loose_box, parent_context, refiner, steps=None):
        image_bgr = cv2.imread(image_path)
        if image_bgr is None:
            raise RuntimeError(tr("Could not read the current image.", self.current_lang))
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        trajectory = refiner.generate_shrink_trajectory(
            image_rgb,
            loose_box,
            polygon,
            steps=steps or self._active_blink_auto_shrink_steps(),
        )
        if not trajectory:
            return []
        self.project.update_trajectory(
            image_path,
            child_part,
            trajectory,
            parent_context=parent_context,
            save=False,
        )
        best_box = _clean_box(trajectory[-1].get("box") if isinstance(trajectory[-1], dict) else None)
        if best_box:
            description = ""
            if self.current_image and self._same_project_image_path(image_path, self.current_image):
                description = self.desc_box.toPlainText()
            else:
                descriptions = self.project.project_data.get("labels", {}).get(image_path, {}).get("descriptions", {})
                if isinstance(descriptions, dict):
                    description = descriptions.get(child_part, "")
            self.project.update_label(
                image_path,
                child_part,
                polygon,
                description,
                box=best_box,
                save=False,
            )
        return trajectory

    def run_blink_auto_shrink(self):
        context = self._active_child_blink_context(require_ready=False)
        if not context or not self.current_image:
            return
        child_part = context.get("child_part")
        parent_part = context.get("parent_part")
        polygon = self.project.get_labels(self.current_image).get(child_part, [])
        if not polygon or len(polygon) < 3:
            self._warn_blink_context(tr("Draw or confirm the child polygon before auto-shrink.", self.current_lang))
            return
        loose_boxes = self.project.get_shrink_loose_boxes(self.current_image) if hasattr(self.project, "get_shrink_loose_boxes") else {}
        loose_box = _clean_box(loose_boxes.get(child_part) if isinstance(loose_boxes, dict) else None)
        if not loose_box:
            self._warn_blink_context(tr("Select Blink Shrink Start Box on the canvas toolbar and draw one around the child first.", self.current_lang))
            return
        try:
            BlinkRefiner = self._load_blink_refiner_class()
            parts_model = self.engine.ensure_parts_model_loaded() if hasattr(self.engine, "ensure_parts_model_loaded") else self.engine.parts_model
            sam_model = getattr(parts_model, "ultralytics_sam", None)
            refiner = BlinkRefiner(sam_model=sam_model, device=self.runtime_device)
            trajectory = self._generate_blink_shrink_for_image(
                self.current_image,
                child_part,
                polygon,
                loose_box,
                {
                    "parent_part": parent_part,
                    "parent_box": context.get("parent_box"),
                    "source": context.get("parent_box_source") or "workbench",
                },
                refiner,
            )
            if not trajectory:
                self._warn_blink_context(tr("Auto-shrink did not generate a trajectory.", self.current_lang))
                return
            self.project.remember_blink_context_parent(child_part, parent_part, save=False)
            self._schedule_project_save()
            self._refresh_current_canvas_boxes()
            self._refresh_blink_refine_state()
            self.log(tr("Saved {0} shrink trajectory frames for {1}.", self.current_lang).format(len(trajectory), child_part))
        except Exception as exc:
            self._warn_blink_context(tr("Auto-shrink failed: {0}", self.current_lang).format(str(exc)))

    def run_blink_batch_auto_shrink(self):
        context = self._active_child_blink_context(require_ready=False)
        if not context:
            return
        child_part = context.get("child_part")
        parent_part = context.get("parent_part")
        if not child_part or not parent_part:
            return

        summary = self._prepared_blink_auto_shrink_images(child_part, parent_part)
        prepared = list(summary.get("prepared", []) or [])
        if not prepared:
            self.log(
                tr(
                    "No prepared images for batch auto-shrink. Existing trajectories: {0}; missing polygon: {1}; missing shrink box: {2}; missing parent box: {3}.",
                    self.current_lang,
                ).format(
                    summary.get("existing_trajectory", 0),
                    summary.get("missing_polygon", 0),
                    summary.get("missing_loose_box", 0),
                    summary.get("missing_parent_box", 0),
                )
            )
            return

        reply = themed_yes_no_question(
            self,
            tr("Batch auto-shrink", self.current_lang),
            tr(
                "Batch auto-shrink prepared {0} image(s) for {1}. Existing trajectories skipped: {2}; missing polygon: {3}; missing shrink box: {4}; missing parent box: {5}.\n\nRun auto-shrink for all prepared images?",
                self.current_lang,
            ).format(
                len(prepared),
                child_part,
                summary.get("existing_trajectory", 0),
                summary.get("missing_polygon", 0),
                summary.get("missing_loose_box", 0),
                summary.get("missing_parent_box", 0),
            ),
            confirm_role=BUTTON_ROLE_RUN,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            BlinkRefiner = self._load_blink_refiner_class()
            parts_model = self.engine.ensure_parts_model_loaded() if hasattr(self.engine, "ensure_parts_model_loaded") else self.engine.parts_model
            sam_model = getattr(parts_model, "ultralytics_sam", None)
            refiner = BlinkRefiner(sam_model=sam_model, device=self.runtime_device)
            success = 0
            failed = 0
            for item in prepared:
                try:
                    trajectory = self._generate_blink_shrink_for_image(
                        item["image_path"],
                        child_part,
                        item["polygon"],
                        item["loose_box"],
                        item["parent_context"],
                        refiner,
                    )
                    if trajectory:
                        success += 1
                    else:
                        failed += 1
                except Exception as exc:
                    failed += 1
                    self.log(
                        tr("Auto-shrink failed: {0}", self.current_lang).format(
                            f"{os.path.basename(str(item.get('image_path', '')))} | {exc}"
                        )
                    )
            if success:
                self.project.remember_blink_context_parent(child_part, parent_part, save=False)
                self.project.save_project()
            if self.current_image:
                self.canvas.set_polygons(self.project.get_labels(self.current_image))
                self._refresh_current_canvas_boxes()
            self._refresh_image_list_status_or_rebuild(self.current_image)
            self._refresh_blink_refine_state()
            self.log(
                tr("Batch auto-shrink finished for {0}/{1} image(s) of {2}. Failed: {3}.", self.current_lang).format(
                    success,
                    len(prepared),
                    child_part,
                    failed,
                )
            )
        except Exception as exc:
            self._warn_blink_context(tr("Auto-shrink failed: {0}", self.current_lang).format(str(exc)))

    def train_current_blink_expert(self):
        context = self._active_child_blink_context(require_ready=False)
        if not context:
            return
        if self._is_parent_training_running():
            self._warn_blink_context(tr("Parent-part training is running. Wait for it to finish before training a child expert.", self.current_lang))
            return
        if getattr(self.blink_lab, "training_thread", None) is not None and self.blink_lab.training_thread.isRunning():
            self._warn_blink_context(tr("Blink expert training is already running.", self.current_lang))
            return
        child_part = context.get("child_part")
        parent_part = context.get("parent_part")
        scope_payload = self._selected_training_scope_payload()
        scope_images = list(scope_payload.get("images", []) or [])
        scope_label = str(scope_payload.get("label") or tr("All Images", self.current_lang))
        scope_id = str(scope_payload.get("scope_id") or "__all__")
        if not scope_images:
            self._warn_blink_context(
                tr(
                    "Selected training scope is empty. Choose another image group or add images to this group first.",
                    self.current_lang,
                )
            )
            return
        child_training_scope = {
            "scope_id": scope_id,
            "label": scope_label,
            "image_count": len(scope_images),
        }
        self.child_training_failed = False
        self.child_training_cancel_requested = False
        self.btn_train.setEnabled(False)
        self._set_training_progress(
            "child",
            f"{tr('Child-part expert training', self.current_lang)}: {parent_part} -> {child_part}",
            0,
        )
        self.blink_lab.canvas.current_tool_part = child_part
        self.blink_lab.session_target_part = child_part
        self.blink_lab.current_image_path = self.current_image
        self.blink_lab.active_session = {
            "image_path": self.current_image,
            "target_part": child_part,
            "focus_roi": {
                "part": parent_part,
                "source": context.get("parent_box_source") or "workbench",
                "box": context.get("parent_box"),
            },
        }
        self.blink_lab.training_route_context = self.blink_lab._route_context_for_training(parent_part, child_part)
        self.blink_lab.train_expert_model(
            allowed_image_paths=scope_images,
            training_scope=child_training_scope,
        )
        self._connect_child_training_progress()
        if getattr(self.blink_lab, "training_thread", None) is None:
            self.btn_train.setEnabled(True)
            if hasattr(self, "btn_blink_stop_training"):
                self.btn_blink_stop_training.setEnabled(False)
            self._set_training_progress(None, tr("No training running.", self.current_lang), 0)
        else:
            if hasattr(self, "btn_blink_stop_training"):
                self.btn_blink_stop_training.setEnabled(True)
        self._refresh_blink_refine_state()
        self.log(tr("Started Blink expert training for {0} -> {1}.", self.current_lang).format(parent_part, child_part))
        self.log(tr("Training scope: {0} ({1} image(s))", self.current_lang).format(scope_label, len(scope_images)))

    def stop_current_blink_expert_training(self):
        if not self._is_child_training_running():
            if hasattr(self, "btn_blink_stop_training"):
                self.btn_blink_stop_training.setEnabled(False)
            return
        self.child_training_cancel_requested = True
        if hasattr(self, "btn_blink_stop_training"):
            self.btn_blink_stop_training.setEnabled(False)
        self._set_training_progress("child", tr("Stopping child-part expert training...", self.current_lang), self.progress.value())
        self.blink_lab.stop_expert_training()

    def open_current_route_expert_settings(self):
        context = self._refresh_blink_refine_state()
        parent_part = context.get("parent_part")
        child_part = context.get("child_part")
        if not parent_part or not child_part:
            self._warn_blink_context(tr("Select a child structure with a parent context first.", self.current_lang))
            return
        if hasattr(self.project, "register_cascade_route_candidate"):
            self.project.register_cascade_route_candidate(
                parent_part,
                child_part,
                focus_source=context.get("parent_box_source"),
                registration_source="workbench_blink_refine",
                save=False,
            )
            self.project.remember_blink_context_parent(child_part, parent_part, save=False)
            self._schedule_project_save()
        self.open_stl_model_settings(target_route=(parent_part, child_part))
