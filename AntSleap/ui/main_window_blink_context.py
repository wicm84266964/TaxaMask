try:
    from AntSleap.ui.main_window_stage6_dependencies import *
except ImportError:
    from ui.main_window_stage6_dependencies import *


class MainWindowBlinkContextMixin:
    def appoint_selected_route_expert(self):
        panel = getattr(self, "route_settings_panel", None)
        if panel is not None:
            panel.appoint_selected_route_expert()

    def _route_parents_for_child(self, child_part):
        clean_child = str(child_part or "").strip()
        if not clean_child:
            return []
        routes = []
        try:
            routes = self.project.iter_cascade_routes()
        except Exception:
            routes = []
        parents = []
        for route in routes or []:
            if not isinstance(route, dict):
                continue
            parent = str(route.get("parent") or "").strip()
            child = str(route.get("child") or "").strip()
            if parent and child == clean_child and parent != clean_child and parent not in parents:
                parents.append(parent)
        return parents

    def _resolve_child_parent(self, child_part):
        clean_child = str(child_part or "").strip()
        if not clean_child:
            return None, "none"
        taxonomy = set(str(part).strip() for part in self.project.project_data.get("taxonomy", []) if str(part).strip())

        remembered_parent = None
        get_parent = getattr(self.project, "get_blink_context_parent", None)
        if callable(get_parent):
            try:
                remembered_parent = get_parent(clean_child)
            except Exception:
                remembered_parent = None
        remembered_parent = str(remembered_parent or "").strip()
        if remembered_parent and remembered_parent in taxonomy and remembered_parent != clean_child:
            return remembered_parent, "remembered"

        route_parents = self._route_parents_for_child(clean_child)
        if len(route_parents) == 1:
            return route_parents[0], "route"

        tree_parent = self._part_tree_parent_for(clean_child)
        if tree_parent and tree_parent != clean_child:
            return tree_parent, "part_tree"
        return None, "none"

    def _parent_context_box(self, parent_part):
        if not self.current_image or not parent_part:
            return None, "none"
        manual = self.project.get_boxes(self.current_image)
        box = _clean_box(manual.get(parent_part) if isinstance(manual, dict) else None)
        if box:
            return box, "manual"
        auto, vlm = self._auto_boxes_for_canvas(self.current_image)
        box = _clean_box(auto.get(parent_part) if isinstance(auto, dict) else None)
        if box:
            return box, "auto"
        box = _clean_box(vlm.get(parent_part) if isinstance(vlm, dict) else None)
        if box:
            return box, "vlm"
        return None, "none"

    def _current_shrink_loose_boxes(self):
        if not self.current_image or not hasattr(self.project, "get_shrink_loose_boxes"):
            return {}
        boxes = self.project.get_shrink_loose_boxes(self.current_image)
        return boxes if isinstance(boxes, dict) else {}

    def _route_entry_for_context(self, parent_part, child_part):
        get_route = getattr(self.project, "get_cascade_route", None)
        if callable(get_route):
            try:
                route = get_route(parent_part, child_part)
            except Exception:
                route = None
            if isinstance(route, dict):
                return dict(route)
        for route in self.project.iter_cascade_routes():
            if not isinstance(route, dict):
                continue
            if route.get("parent") == parent_part and route.get("child") == child_part:
                return dict(route)
        return None

    def _route_expert_status(self, route_entry):
        if not isinstance(route_entry, dict):
            return "missing", tr("Route not configured", self.current_lang), False
        appointed = get_route_appointed_expert(route_entry)
        has_appointed = bool(appointed.get("expert_id"))
        block_reason = None
        cascade_manager = getattr(getattr(self, "engine", None), "cascade_manager", None)
        get_block = getattr(cascade_manager, "get_route_block_reason", None)
        if callable(get_block):
            try:
                block_reason = get_block(route_entry)
            except Exception:
                block_reason = None
        if block_reason == "expert_unappointed":
            return "unappointed", ui_text("Expert not appointed yet", self.current_lang), False
        if block_reason == "expert_model_missing":
            if has_appointed:
                return "ready", tr("Expert file missing", self.current_lang), True
            return "missing_file", tr("Expert file missing", self.current_lang), False
        if not has_appointed:
            return "unappointed", ui_text("Expert not appointed yet", self.current_lang), False
        if not bool(route_entry.get("enabled", False)):
            return "disabled", ui_text("Disabled", self.current_lang), has_appointed
        if has_appointed:
            return "ready", ui_text("Enabled", self.current_lang), True
        return "unappointed", ui_text("Expert not appointed yet", self.current_lang), False

    def _current_blink_context(self):
        selected_part = self._current_part_name()
        context = {
            "selected_part": selected_part,
            "role": "none",
            "parent_part": None,
            "child_part": None,
            "parent_source": "none",
            "route_label": "",
            "parent_box": None,
            "parent_box_source": "none",
            "has_parent_box": False,
            "route_entry": None,
            "route_status": "none",
            "route_status_text": ui_text("Unknown", self.current_lang),
            "has_appointed_expert": False,
            "can_refine": False,
            "disabled_reason": tr("Select a child structure first.", self.current_lang),
        }
        if not selected_part:
            return context

        if self._is_parent_part(selected_part):
            box, source = self._parent_context_box(selected_part)
            context.update(
                {
                    "role": "parent",
                    "parent_part": selected_part,
                    "parent_box": box,
                    "parent_box_source": source,
                    "has_parent_box": bool(box),
                    "disabled_reason": tr("Select a child structure for refinement.", self.current_lang),
                }
            )
            return context

        parent_part, parent_source = self._resolve_child_parent(selected_part)
        context.update(
            {
                "role": "child",
                "child_part": selected_part,
                "parent_part": parent_part,
                "parent_source": parent_source,
            }
        )
        if parent_part:
            context["route_label"] = f"{parent_part} -> {selected_part}"
            parent_box, parent_box_source = self._parent_context_box(parent_part)
            route_entry = self._route_entry_for_context(parent_part, selected_part)
            route_status, route_status_text, has_appointed = self._route_expert_status(route_entry)
            context.update(
                {
                    "parent_box": parent_box,
                    "parent_box_source": parent_box_source,
                    "has_parent_box": bool(parent_box),
                    "route_entry": route_entry,
                    "route_status": route_status,
                    "route_status_text": route_status_text,
                    "has_appointed_expert": has_appointed,
                }
            )
        if not parent_part:
            context["disabled_reason"] = tr("Choose or remember a parent structure for this child first.", self.current_lang)
        elif not context["has_parent_box"]:
            context["disabled_reason"] = tr("Draw a parent box before child refinement.", self.current_lang)
        elif context["route_status"] in {"missing", "unappointed", "missing_file"}:
            context["disabled_reason"] = tr("Configure a route expert before automatic child annotation.", self.current_lang)
        elif context["route_status"] == "disabled":
            context["disabled_reason"] = tr("Enable the current route before automatic child annotation.", self.current_lang)
        else:
            context["can_refine"] = True
            context["disabled_reason"] = ""
        return context

    def _parent_box_aspect_ratio(self, parent_part):
        ratios = getattr(self, "parent_box_aspect_ratios", None)
        if not isinstance(ratios, dict):
            ratios = self.project.get_parent_box_aspect_ratios() if hasattr(self.project, "get_parent_box_aspect_ratios") else {}
            self.parent_box_aspect_ratios = dict(ratios)
        try:
            ratio = float(ratios.get(parent_part))
        except Exception:
            ratio = None
        return ratio if ratio and ratio > 0 else None

    def _parent_context_options(self, child_part):
        clean_child = str(child_part or "").strip()
        if not clean_child:
            return []
        taxonomy = {
            str(part).strip()
            for part in self.project.project_data.get("taxonomy", [])
            if str(part).strip()
        }
        options = []
        for parent_part in (
            list(self._workbench_parent_parts())
            + list(self._route_parents_for_child(clean_child))
            + [self._part_tree_parent_for(clean_child)]
        ):
            clean_parent = str(parent_part or "").strip()
            if (
                clean_parent
                and clean_parent != clean_child
                and clean_parent in taxonomy
                and clean_parent not in options
            ):
                options.append(clean_parent)
        return options

    def _refresh_blink_refine_state(self):
        context = self._current_blink_context()
        self.current_blink_context = dict(context)
        self._refresh_annotation_box_constraints()
        self._update_blink_refine_panel(context)
        return context

    def _update_blink_refine_panel(self, context=None):
        if not hasattr(self, "blink_refine_panel"):
            return
        context = dict(context or getattr(self, "current_blink_context", {}) or {})
        role = context.get("role") or "none"
        selected_part = context.get("selected_part") or ""
        parent_part = context.get("parent_part") or ""
        child_part = context.get("child_part") or ""

        if role == "parent":
            role_text = tr("Parent context", self.current_lang)
            box_status = tr("parent box exists", self.current_lang) if context.get("has_parent_box") else tr("parent box missing", self.current_lang)
            summary = tr("Current structure: {0} ({1}); {2}.", self.current_lang).format(selected_part, role_text, box_status)
        elif role == "child":
            role_text = tr("Child structure", self.current_lang)
            route_text = context.get("route_label") or tr("Parent not selected", self.current_lang)
            summary = tr("Current structure: {0} ({1}); route {2}.", self.current_lang).format(selected_part, role_text, route_text)
        else:
            summary = tr("Select a structure to see Blink parent-child status.", self.current_lang)

        self.blink_context_status_label.setText(summary)
        self.label_blink_route.setText(
            tr("Current route: {0}", self.current_lang).format(context.get("route_label") or tr("Not available", self.current_lang))
        )
        self.label_blink_parent_context.setText(tr("Parent context:", self.current_lang))
        self._update_blink_parent_context_combo(context)
        parent_box_text = tr("Parent box: {0}", self.current_lang).format(
            tr("available ({0})", self.current_lang).format(context.get("parent_box_source"))
            if context.get("has_parent_box")
            else tr("missing", self.current_lang)
        )
        if parent_part and role == "child":
            parent_box_text = f"{parent_part} · {parent_box_text}"
        self.label_blink_parent_box.setText(parent_box_text)
        self.label_blink_expert.setText(
            tr("Route expert: {0}", self.current_lang).format(context.get("route_status_text") or ui_text("Unknown", self.current_lang))
        )
        self.check_lock_parent_box_ratio.setText(tr("Lock parent box ratio", self.current_lang))
        self.check_lock_parent_box_ratio.setToolTip(
            tr(
                "Off by default. Enable when preparing fixed-ratio parent boxes for child-part training; it affects parent SAM box prompts and parent manual ROI boxes.",
                self.current_lang,
            )
        )

        can_open_route = bool(parent_part and child_part)
        self.btn_configure_route_expert.setEnabled(can_open_route)
        self.btn_configure_route_expert.setToolTip(
            tr("Open route expert settings for {0}.", self.current_lang).format(context.get("route_label"))
            if can_open_route
            else tr("Select a child structure with a parent context first.", self.current_lang)
        )

        can_refine = bool(context.get("can_refine"))
        disabled_reason = str(context.get("disabled_reason") or "")
        self.btn_blink_auto_annotate.setEnabled(can_refine)
        self.btn_blink_auto_annotate.setToolTip(disabled_reason)
        self.btn_blink_auto_shrink.setEnabled(bool(role == "child" and parent_part and context.get("has_parent_box")))
        self.btn_blink_auto_shrink.setToolTip(disabled_reason if not self.btn_blink_auto_shrink.isEnabled() else "")
        if hasattr(self, "btn_blink_batch_auto_shrink"):
            self.btn_blink_batch_auto_shrink.setEnabled(bool(role == "child" and parent_part))
            self.btn_blink_batch_auto_shrink.setToolTip(disabled_reason if not self.btn_blink_batch_auto_shrink.isEnabled() else "")
        parent_training_busy = self._is_parent_training_running()
        child_training_busy = self._is_child_training_running()
        training_busy = parent_training_busy or child_training_busy
        can_train_child = bool(role == "child" and parent_part) and not training_busy
        self.btn_blink_train_expert.setEnabled(can_train_child)
        if self.btn_blink_train_expert.isEnabled():
            train_child_tooltip = tr("Training uses saved shrink trajectories for this parent-child route.", self.current_lang)
        elif parent_training_busy:
            train_child_tooltip = tr("Parent-part training is running. Wait for it to finish before training a child expert.", self.current_lang)
        elif child_training_busy:
            train_child_tooltip = tr("Blink expert training is already running.", self.current_lang)
        else:
            train_child_tooltip = tr("Select a child structure with a parent context first.", self.current_lang)
        self.btn_blink_train_expert.setToolTip(
            train_child_tooltip
        )

    def _update_blink_parent_context_combo(self, context):
        if not hasattr(self, "combo_blink_parent_context"):
            return
        context = dict(context or {})
        combo = self.combo_blink_parent_context
        self._updating_blink_parent_context = True
        try:
            combo.blockSignals(True)
            combo.clear()
            role = context.get("role")
            child_part = context.get("child_part")
            parent_part = context.get("parent_part")
            options = self._parent_context_options(child_part) if role == "child" else []
            prompt_text = tr("Choose parent context", self.current_lang)
            unavailable_text = tr("Parent context unavailable", self.current_lang)
            if hasattr(combo, "setPlaceholderText"):
                combo.setPlaceholderText(prompt_text if role == "child" else unavailable_text)
            for option in options:
                combo.addItem(option, option)
            index = combo.findData(parent_part)
            if index >= 0:
                combo.setCurrentIndex(index)
            elif options:
                combo.setCurrentIndex(-1)
            else:
                combo.addItem(unavailable_text, "")
                item = combo.model().item(0) if combo.model() is not None else None
                if item is not None:
                    item.setEnabled(False)
                combo.setCurrentIndex(0)
            combo.setEnabled(role == "child" and bool(options))
            combo.setToolTip(
                prompt_text
                if combo.isEnabled()
                else unavailable_text
            )
        finally:
            combo.blockSignals(False)
            self._updating_blink_parent_context = False

    def launch_blink_from_workbench(self):
        if not self.current_image:
            QMessageBox.warning(self, tr("Child Expert Session Entry", self.current_lang), tr("Please select an image first.", self.current_lang))
            return

        selected_part = self._current_part_name()
        if not selected_part:
            QMessageBox.warning(self, tr("Child Expert Session Entry", self.current_lang), tr("Please select a target part first.", self.current_lang))
            return

        taxonomy = list(self.project.project_data.get("taxonomy", []))
        remembered_parent_map = self.project.get_blink_context_roi_parents()
        remembered_parent = remembered_parent_map.get(str(selected_part or "").strip())
        preferred_roi_parts = _blink_preferred_roi_parts(selected_part, remembered_parent)
        roi_candidates = self._collect_blink_roi_candidates(
            self.current_image,
            selected_part,
            preferred_roi_parts=preferred_roi_parts,
        )
        if not roi_candidates:
            QMessageBox.information(
                self,
                tr("Child Expert Session Entry", self.current_lang),
                tr("No entry ROI is available yet. Draw a manual box or generate an auto box in the workbench first.", self.current_lang),
            )
            return

        dialog = BlinkEntryDialog(
            self.current_image,
            taxonomy,
            selected_part,
            roi_candidates,
            self,
            self.current_lang,
            remembered_parent_map=remembered_parent_map,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        session = dialog.get_session_spec(self.current_image)
        if not session:
            QMessageBox.warning(
                self,
                tr("Child Expert Session Entry", self.current_lang),
                tr("Failed to build a child expert session from the selected options.", self.current_lang),
            )
            return

        labels = self.project.get_labels(self.current_image)
        manual_boxes = self.project.get_boxes(self.current_image)
        box_splitter = getattr(self, "_auto_boxes_for_canvas", None)
        if callable(box_splitter):
            auto_boxes, _vlm_boxes = box_splitter(self.current_image)
        else:
            project_splitter = getattr(self.project, "split_auto_boxes_by_source", None)
            if callable(project_splitter):
                auto_boxes, _vlm_boxes = project_splitter(self.current_image)
            else:
                auto_boxes = self.project.get_auto_boxes(self.current_image)
        started = self.blink_lab.start_session(session, labels, manual_boxes, auto_boxes)
        if not started:
            return
        self.tabs.setCurrentWidget(self.blink_lab)

        focus_roi = session.get("focus_roi", {})
        if not isinstance(focus_roi, dict):
            focus_roi = {}
        remembered_target_part = session.get("target_part")
        remembered_parent_part = str(focus_roi.get("part") or "").strip()
        if remembered_parent_part and remembered_target_part:
            if remembered_parent_part == remembered_target_part:
                self.project.clear_blink_context_parent(remembered_target_part)
            else:
                self.project.remember_blink_context_parent(remembered_target_part, remembered_parent_part)
                if hasattr(self.project, "register_cascade_route_candidate"):
                    self.project.register_cascade_route_candidate(
                        remembered_parent_part,
                        remembered_target_part,
                        focus_source=focus_roi.get("source"),
                        registration_source="blink_candidate",
                    )
                    if hasattr(self, "refresh_route_table"):
                        self.refresh_route_table()
        focus_label = focus_roi.get("part", "ROI")
        focus_source = focus_roi.get("source", "manual")
        self.log(
            tr("Opened child expert session for {0} via {1} ({2}).", self.current_lang).format(
                session.get('target_part'), focus_label, focus_source
            )
        )

    def on_blink_parent_context_changed(self, _index=None):
        if getattr(self, "_updating_blink_parent_context", False):
            return
        child_part = self._current_part_name()
        parent_part = self.combo_blink_parent_context.currentData() if hasattr(self, "combo_blink_parent_context") else None
        child_part = str(child_part or "").strip()
        parent_part = str(parent_part or "").strip()
        if not child_part or not parent_part or child_part == parent_part:
            return
        if self._is_parent_part(child_part):
            return
        if hasattr(self.project, "remember_blink_context_parent"):
            self.project.remember_blink_context_parent(child_part, parent_part, save=False)
        if hasattr(self.project, "register_cascade_route_candidate"):
            self.project.register_cascade_route_candidate(
                parent_part,
                child_part,
                registration_source="workbench_blink_refine",
                save=False,
            )
        self._schedule_project_save()
        self.refresh_route_table()
        self.log(tr("Manual parent context set: {0} -> {1}.", self.current_lang).format(parent_part, child_part))

    def _warn_blink_context(self, message):
        QMessageBox.information(self, tr("Child-part annotation", self.current_lang), message)

    def _active_child_blink_context(self, require_ready=False):
        context = self._refresh_blink_refine_state()
        if context.get("role") != "child" or not context.get("child_part") or not context.get("parent_part"):
            self._warn_blink_context(tr("Select a child structure with a parent context first.", self.current_lang))
            return None
        if not context.get("has_parent_box"):
            self._warn_blink_context(tr("Draw a parent box before child refinement.", self.current_lang))
            return None
        if require_ready and not context.get("can_refine"):
            self._warn_blink_context(context.get("disabled_reason") or tr("Configure the current route before continuing.", self.current_lang))
            return None
        return context

    def _sync_blink_lab_model_profile_defaults(self):
        if not hasattr(self, "blink_lab"):
            return
        child_defaults = _runtime_child_backend_defaults(self.project)
        train_params = child_defaults.get("train_params", {}) if isinstance(child_defaults.get("train_params"), dict) else {}
        heatmap_params = child_defaults.get("heatmap_params", {}) if isinstance(child_defaults.get("heatmap_params"), dict) else {}
        backend_type = child_defaults.get("backend_type") or CHILD_BACKEND_VIT_B
        input_size = child_defaults.get("input_size", self.blink_train_input_size)
        auto_shrink_steps = child_defaults.get("auto_shrink_steps", self.blink_auto_shrink_steps)
        training_strategy = sanitize_blink_training_strategy(
            child_defaults.get("training_strategy"),
            DEFAULT_BLINK_TRAINING_STRATEGY,
        )
        if backend_type == CHILD_BACKEND_HEATMAP:
            input_size = heatmap_params.get("input_size", input_size)
        self.blink_lab.set_training_defaults(
            train_params.get("epochs", self.blink_train_epochs),
            train_params.get("batch", self.blink_train_batch),
            train_params.get("lr", self.blink_train_lr),
            train_params.get("weight_decay", self.blink_train_weight_decay),
            input_size,
            self.runtime_device,
            trainer_backend=backend_type,
            heatmap_params=heatmap_params,
            auto_shrink_steps=auto_shrink_steps,
            training_strategy=training_strategy,
        )
