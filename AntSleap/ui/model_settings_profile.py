try:
    from AntSleap.ui.model_settings_dependencies import *
except ImportError:
    from ui.model_settings_dependencies import *


class ModelSettingsProfileMixin:
    def _active_profile_id(self):
        selected = ""
        if hasattr(self, "combo_model_profile"):
            selected = str(self.combo_model_profile.currentData() or "").strip()
        return selected or str(self.model_profiles.get("active_profile_id") or DEFAULT_MODEL_PROFILE_ID)

    def _project_active_profile_id(self):
        return str(self.model_profiles.get("active_profile_id") or DEFAULT_MODEL_PROFILE_ID)

    def _active_profile(self):
        active_id = str(self.model_profiles.get("active_profile_id") or DEFAULT_MODEL_PROFILE_ID)
        if hasattr(self, "combo_model_profile"):
            combo_id = str(self.combo_model_profile.currentData() or "").strip()
            if combo_id:
                active_id = combo_id
        for profile in self.model_profiles.get("profiles", []):
            if isinstance(profile, dict) and profile.get("profile_id") == active_id:
                return dict(profile)
        profiles = self.model_profiles.get("profiles", [])
        return dict(profiles[0]) if profiles and isinstance(profiles[0], dict) else {}

    def _refresh_profile_combo(self, select_id=None):
        if not hasattr(self, "combo_model_profile"):
            return
        target = str(select_id or self.model_profiles.get("active_profile_id") or DEFAULT_MODEL_PROFILE_ID)
        self.combo_model_profile.blockSignals(True)
        self.combo_model_profile.clear()
        for profile in self.model_profiles.get("profiles", []):
            if not isinstance(profile, dict):
                continue
            profile_id = str(profile.get("profile_id") or "").strip()
            if not profile_id:
                continue
            label = profile.get("display_name") or profile_id
            if profile_id == self._project_active_profile_id():
                label = tr("{0} (active)", self.lang).format(label)
            self.combo_model_profile.addItem(str(label), profile_id)
        index = self.combo_model_profile.findData(target)
        self.combo_model_profile.setCurrentIndex(index if index >= 0 else 0)
        self.combo_model_profile.blockSignals(False)
        self._load_selected_profile_fields()

    def _load_selected_profile_fields(self):
        profile = self._active_profile()
        if hasattr(self, "profile_id_edit"):
            self.profile_id_edit.blockSignals(True)
            self.profile_id_edit.setText(str(profile.get("profile_id") or ""))
            self.profile_id_edit.blockSignals(False)
        if hasattr(self, "profile_name_edit"):
            self.profile_name_edit.blockSignals(True)
            self.profile_name_edit.setText(str(profile.get("display_name") or ""))
            self.profile_name_edit.blockSignals(False)
        if hasattr(self, "profile_description_edit"):
            self.profile_description_edit.blockSignals(True)
            self.profile_description_edit.setPlainText(str(profile.get("description") or ""))
            self.profile_description_edit.blockSignals(False)
        self._apply_profile_to_controls(profile)
        self._refresh_profile_summary()

    def _update_current_profile_metadata(self):
        active_id = self._active_profile_id()
        for profile in self.model_profiles.get("profiles", []):
            if not isinstance(profile, dict) or profile.get("profile_id") != active_id:
                continue
            if hasattr(self, "profile_name_edit"):
                profile["display_name"] = self.profile_name_edit.text().strip() or active_id
            if hasattr(self, "profile_description_edit"):
                profile["description"] = self.profile_description_edit.toPlainText().strip()
            break
        self._refresh_profile_summary()

    def _profile_by_id(self, profile_id):
        target = str(profile_id or "").strip()
        for profile in self.model_profiles.get("profiles", []):
            if isinstance(profile, dict) and str(profile.get("profile_id") or "").strip() == target:
                return dict(profile)
        return {}

    def _route_entries_for_profile_summary(self):
        panel = getattr(self, "route_panel", None)
        project = getattr(getattr(panel, "owner", None), "project", None) if panel is not None else None
        iter_routes = getattr(project, "iter_cascade_routes", None)
        if callable(iter_routes):
            try:
                return [dict(route) for route in iter_routes() if isinstance(route, dict)]
            except Exception:
                return []
        return []

    def _routes_differing_from_child_default(self, profile):
        child_defaults = profile.get("child_backend_defaults", {}) if isinstance(profile.get("child_backend_defaults"), dict) else {}
        default_backend = _route_backend_from_child_backend(child_defaults.get("backend_type", CHILD_BACKEND_VIT_B))
        differing = []
        for route in self._route_entries_for_profile_summary():
            route_backend = _route_backend_from_entry(route)
            if route_backend != default_backend:
                differing.append(dict(route))
        return differing

    def _profile_external_status_lines(self, profile):
        parent_backend = profile.get("parent_backend", {}) if isinstance(profile.get("parent_backend"), dict) else {}
        child_defaults = profile.get("child_backend_defaults", {}) if isinstance(profile.get("child_backend_defaults"), dict) else {}
        lines = []
        if parent_backend.get("backend_type") == PARENT_BACKEND_EXTERNAL:
            external = parent_backend.get("external_backend", {}) if isinstance(parent_backend.get("external_backend"), dict) else {}
            has_command = any(str(external.get(key) or "").strip() for key in ("train_command", "predict_command"))
            lines.append(
                tr("External parent backend: {0}", self.lang).format(
                    tr("configured", self.lang) if has_command else tr("missing train/predict command", self.lang)
                )
            )
        if child_defaults.get("backend_type") == CHILD_BACKEND_EXTERNAL:
            external_blink = child_defaults.get("external_blink_backend", {}) if isinstance(child_defaults.get("external_blink_backend"), dict) else {}
            has_predict = bool(str(external_blink.get("predict_command") or "").strip())
            lines.append(
                tr("External Blink backend: {0}", self.lang).format(
                    tr("configured", self.lang) if has_predict else tr("missing predict command", self.lang)
                )
            )
        return lines

    def _build_profile_summary(self, profile):
        if not isinstance(profile, dict):
            return tr("No model profile selected.", self.lang)
        parent_backend = profile.get("parent_backend", {}) if isinstance(profile.get("parent_backend"), dict) else {}
        child_defaults = profile.get("child_backend_defaults", {}) if isinstance(profile.get("child_backend_defaults"), dict) else {}
        inference_params = profile.get("inference_params", {}) if isinstance(profile.get("inference_params"), dict) else {}
        locator_scope = [
            str(part).strip()
            for part in parent_backend.get("locator_scope", [])
            if str(part).strip()
        ] if isinstance(parent_backend.get("locator_scope"), list) else []
        differing_routes = self._routes_differing_from_child_default(profile)
        route_note = tr(
            "Existing route experts are kept as route-specific bindings; switching profiles does not silently reappoint trained child experts.",
            self.lang,
        )
        lines = [
            tr("Project active profile: {0}", self.lang).format(
                self._active_profile_label(self._profile_by_id(self._project_active_profile_id()))
            ),
            tr("Parent backend: {0}", self.lang).format(_parent_backend_label(parent_backend.get("backend_type"), self.lang)),
            tr("Main locator parts: {0}", self.lang).format(", ".join(locator_scope) if locator_scope else tr("none", self.lang)),
            tr("Default child backend: {0}", self.lang).format(_child_backend_label(child_defaults.get("backend_type"), self.lang)),
            tr("Route-specific experts differing from this default: {0}", self.lang).format(len(differing_routes)),
            tr("Inference: conf={0}, pad={1}, noise={2}", self.lang).format(
                inference_params.get("conf", ""),
                inference_params.get("pad", ""),
                inference_params.get("noise_floor", ""),
            ),
        ]
        lines.extend(self._profile_external_status_lines(profile))
        lines.append(route_note)
        return "\n".join(lines)

    def _refresh_profile_summary(self):
        if not hasattr(self, "profile_summary_box"):
            return
        try:
            profile = self._current_profile_snapshot(update_metadata=False) if hasattr(self, "parent_backend_combo") else self._active_profile()
        except Exception:
            profile = self._active_profile()
        self.profile_summary_box.setPlainText(self._build_profile_summary(profile))

    def _active_profile_label(self, profile):
        profile_id = str(profile.get("profile_id") or "").strip()
        display_name = str(profile.get("display_name") or "").strip()
        if display_name and display_name != profile_id:
            return f"{display_name} ({profile_id})"
        return profile_id or tr("Unknown", self.lang)

    def _profile_id_seed(self, base="custom_profile"):
        existing = {
            str(profile.get("profile_id") or "")
            for profile in self.model_profiles.get("profiles", [])
            if isinstance(profile, dict)
        }
        safe_base = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in str(base or "custom_profile"))
        safe_base = safe_base.strip("_") or "custom_profile"
        if safe_base not in existing:
            return safe_base
        for index in range(2, 1000):
            candidate = f"{safe_base}_{index}"
            if candidate not in existing:
                return candidate
        return f"{safe_base}_{int(time.time())}"

    def new_model_profile(self):
        current = self._current_profile_snapshot()
        new_id = self._profile_id_seed("custom_profile")
        current["profile_id"] = new_id
        current["display_name"] = tr("New Profile", self.lang)
        current["description"] = ""
        self.model_profiles.setdefault("profiles", []).append(current)
        self._refresh_profile_combo(new_id)

    def copy_model_profile(self):
        current = self._current_profile_snapshot()
        base_id = current.get("profile_id") or "copied_profile"
        new_id = self._profile_id_seed(f"{base_id}_copy")
        current["profile_id"] = new_id
        current["display_name"] = f"{current.get('display_name') or base_id} Copy"
        self.model_profiles.setdefault("profiles", []).append(current)
        self._refresh_profile_combo(new_id)

    def delete_model_profile(self):
        active_id = self._active_profile_id()
        current_profile = self._profile_by_id(active_id)
        if active_id == DEFAULT_MODEL_PROFILE_ID:
            QMessageBox.information(
                self,
                tr("Delete Profile", self.lang),
                tr("The built-in default profile cannot be deleted.", self.lang),
            )
            return
        profiles = [
            profile
            for profile in self.model_profiles.get("profiles", [])
            if isinstance(profile, dict) and profile.get("profile_id") != active_id
        ]
        if not profiles:
            QMessageBox.information(
                self,
                tr("Delete Profile", self.lang),
                tr("At least one model profile must remain in the project.", self.lang),
            )
            return
        reply = themed_yes_no_question(
            self,
            tr("Delete Profile", self.lang),
            tr(
                "Delete model profile {0}?\n\nThis removes only the saved profile configuration from the current project. Model weights, external scripts, and route expert bindings are not deleted.",
                self.lang,
            ).format(self._active_profile_label(current_profile)),
            confirm_role=BUTTON_ROLE_DESTRUCTIVE,
        )
        if reply != QMessageBox.Yes:
            return
        self.model_profiles["profiles"] = profiles
        current_project_active = self._project_active_profile_id()
        remaining_ids = {
            str(profile.get("profile_id") or "")
            for profile in profiles
            if isinstance(profile, dict)
        }
        if current_project_active not in remaining_ids:
            self.model_profiles["active_profile_id"] = profiles[0].get("profile_id", DEFAULT_MODEL_PROFILE_ID)
        self._refresh_profile_combo(self.model_profiles["active_profile_id"])

    def _profile_switch_message(self, current_profile, target_profile):
        current_parent = current_profile.get("parent_backend", {}) if isinstance(current_profile.get("parent_backend"), dict) else {}
        current_child = current_profile.get("child_backend_defaults", {}) if isinstance(current_profile.get("child_backend_defaults"), dict) else {}
        target_parent = target_profile.get("parent_backend", {}) if isinstance(target_profile.get("parent_backend"), dict) else {}
        target_child = target_profile.get("child_backend_defaults", {}) if isinstance(target_profile.get("child_backend_defaults"), dict) else {}
        differing_routes = self._routes_differing_from_child_default(target_profile)
        lines = [
            tr("Set {0} as the active model profile?", self.lang).format(self._active_profile_label(target_profile)),
            "",
            tr("Parent backend: {0} -> {1}", self.lang).format(
                _parent_backend_label(current_parent.get("backend_type"), self.lang),
                _parent_backend_label(target_parent.get("backend_type"), self.lang),
            ),
            tr("Default child backend: {0} -> {1}", self.lang).format(
                _child_backend_label(current_child.get("backend_type"), self.lang),
                _child_backend_label(target_child.get("backend_type"), self.lang),
            ),
            tr("Route-specific experts differing from the target default: {0}", self.lang).format(len(differing_routes)),
            tr("Existing route experts stay appointed; this switch only changes the project default profile.", self.lang),
        ]
        return "\n".join(lines)

    def set_selected_profile_active(self):
        selected_id = self._active_profile_id()
        current_id = self._project_active_profile_id()
        target_profile = self._profile_by_id(selected_id)
        if not target_profile:
            QMessageBox.warning(self, tr("Set as Active Profile", self.lang), tr("No model profile selected.", self.lang))
            return
        current_profile = self._profile_by_id(current_id) or target_profile
        if selected_id != current_id:
            reply = themed_yes_no_question(
                self,
                tr("Set as Active Profile", self.lang),
                self._profile_switch_message(current_profile, target_profile),
                confirm_role=BUTTON_ROLE_COMMIT,
            )
            if reply != QMessageBox.Yes:
                self._refresh_profile_combo(current_id)
                return
        self.model_profiles["active_profile_id"] = selected_id
        self._update_current_profile_metadata()
        self._refresh_profile_combo(selected_id)

    def _sync_legacy_backend_combo_from_parent_backend(self):
        if not hasattr(self, "backend_combo") or not hasattr(self, "parent_backend_combo"):
            return
        backend_id = EXTERNAL_BACKEND_ID if self.parent_backend_combo.currentData() == PARENT_BACKEND_EXTERNAL else BUILTIN_BACKEND_ID
        backend_index = self.backend_combo.findData(backend_id)
        self.backend_combo.setCurrentIndex(backend_index if backend_index >= 0 else 0)

    def _refresh_model_source_summaries(self):
        if hasattr(self, "parent_backend_status_label") and hasattr(self, "parent_backend_combo"):
            self.parent_backend_status_label.setText(
                tr("Current parent model source: {0}", self.lang).format(
                    _parent_backend_label(self.parent_backend_combo.currentData(), self.lang)
                )
            )
        if hasattr(self, "child_backend_status_label") and hasattr(self, "child_backend_combo"):
            self.child_backend_status_label.setText(
                tr("Current default child expert: {0}", self.lang).format(
                    _child_backend_label(self.child_backend_combo.currentData(), self.lang)
                )
            )
        if hasattr(self, "parent_extension_status_label") and hasattr(self, "parent_backend_combo"):
            if self.parent_backend_combo.currentData() == PARENT_BACKEND_EXTERNAL:
                parent_text = tr(
                    "Active now: parent-part training and Auto annotation will call this custom parent extension.",
                    self.lang,
                )
            else:
                parent_text = tr(
                    "Not active now: parent-part tasks use Built-in Locator + SAM. These fields are saved for profiles that switch Parent Model Source to Custom Parent Extension.",
                    self.lang,
                )
            self.parent_extension_status_label.setText(parent_text)
        if hasattr(self, "child_extension_status_label") and hasattr(self, "child_backend_combo"):
            if self.child_backend_combo.currentData() == CHILD_BACKEND_EXTERNAL:
                child_text = tr(
                    "Active now: this custom child extension is the default child expert for unresolved routes. Appointed route experts still keep their own bindings.",
                    self.lang,
                )
            else:
                child_text = tr(
                    "Not active now: the default child expert is {0}. These fields are saved for profiles that switch Default Child Expert to Custom Child Extension.",
                    self.lang,
                ).format(_child_backend_label(self.child_backend_combo.currentData(), self.lang))
            self.child_extension_status_label.setText(child_text)
        if hasattr(self, "profile_summary_box"):
            self._refresh_profile_summary()

    def _apply_profile_to_controls(self, profile):
        if not isinstance(profile, dict):
            return
        parent_backend = profile.get("parent_backend", {}) if isinstance(profile.get("parent_backend"), dict) else {}
        child_defaults = profile.get("child_backend_defaults", {}) if isinstance(profile.get("child_backend_defaults"), dict) else {}
        inference_params = profile.get("inference_params", {}) if isinstance(profile.get("inference_params"), dict) else {}

        if hasattr(self, "parent_backend_combo"):
            index = self.parent_backend_combo.findData(parent_backend.get("backend_type", PARENT_BACKEND_BUILTIN))
            self.parent_backend_combo.setCurrentIndex(index if index >= 0 else 0)
        self._sync_legacy_backend_combo_from_parent_backend()
        if hasattr(self, "child_backend_combo"):
            index = self.child_backend_combo.findData(child_defaults.get("backend_type", CHILD_BACKEND_VIT_B))
            self.child_backend_combo.setCurrentIndex(index if index >= 0 else 0)
        self._refresh_model_source_summaries()

        external_parent = sanitize_external_backend_config(parent_backend.get("external_backend", {}))
        for editor_name, key in [
            ("external_backend_id", "backend_id"),
            ("external_display_name", "display_name"),
            ("external_python", "python_executable"),
            ("external_model_manifest", "model_manifest"),
        ]:
            if hasattr(self, editor_name):
                getattr(self, editor_name).setText(str(external_parent.get(key, "")))
        for editor_name, key in [
            ("external_prepare_command", "prepare_dataset_command"),
            ("external_train_command", "train_command"),
            ("external_predict_command", "predict_command"),
        ]:
            if hasattr(self, editor_name):
                getattr(self, editor_name).setPlainText(str(external_parent.get(key, "")))

        train_params = parent_backend.get("train_params", {}) if isinstance(parent_backend.get("train_params"), dict) else {}
        for editor_name, value in [
            ("spin_epochs", train_params.get("epochs")),
            ("spin_batch", train_params.get("batch")),
            ("spin_lr", train_params.get("lr")),
            ("spin_wd", train_params.get("weight_decay")),
        ]:
            if hasattr(self, editor_name) and value is not None:
                getattr(self, editor_name).setText(str(value))

        child_train = child_defaults.get("train_params", {}) if isinstance(child_defaults.get("train_params"), dict) else {}
        for editor_name, value in [
            ("spin_blink_epochs", child_train.get("epochs")),
            ("spin_blink_batch", child_train.get("batch")),
            ("spin_blink_lr", child_train.get("lr")),
            ("spin_blink_wd", child_train.get("weight_decay")),
        ]:
            if hasattr(self, editor_name) and value is not None:
                getattr(self, editor_name).setText(str(value))
        if hasattr(self, "combo_blink_input_size"):
            try:
                input_size = int(child_defaults.get("input_size", 224))
            except Exception:
                input_size = 224
            index = self.combo_blink_input_size.findData(input_size)
            self.combo_blink_input_size.setCurrentIndex(index if index >= 0 else 0)
        if hasattr(self, "spin_blink_auto_shrink_steps"):
            try:
                shrink_steps = int(child_defaults.get("auto_shrink_steps", DEFAULT_CHILD_AUTO_SHRINK_STEPS))
            except Exception:
                shrink_steps = DEFAULT_CHILD_AUTO_SHRINK_STEPS
            self.spin_blink_auto_shrink_steps.setValue(max(1, min(200, shrink_steps)))
        if hasattr(self, "combo_blink_training_strategy"):
            strategy = sanitize_blink_training_strategy(
                child_defaults.get("training_strategy"),
                DEFAULT_BLINK_TRAINING_STRATEGY,
            )
            index = self.combo_blink_training_strategy.findData(strategy)
            self.combo_blink_training_strategy.setCurrentIndex(index if index >= 0 else 0)
            self._update_blink_training_strategy_note()

        heatmap_params = child_defaults.get("heatmap_params", {}) if isinstance(child_defaults.get("heatmap_params"), dict) else {}
        for editor_name, key in [
            ("spin_heatmap_input_size", "input_size"),
            ("spin_heatmap_sigma", "heatmap_sigma"),
            ("spin_heatmap_wh_loss", "wh_loss_weight"),
            ("spin_heatmap_center_loss", "center_loss_weight"),
        ]:
            if hasattr(self, editor_name):
                getattr(self, editor_name).setText(str(heatmap_params.get(key, DEFAULT_HEATMAP_BLINK_PARAMS.get(key, ""))))

        external_blink = dict(DEFAULT_EXTERNAL_BLINK_BACKEND)
        if isinstance(child_defaults.get("external_blink_backend"), dict):
            external_blink.update(child_defaults.get("external_blink_backend"))
        for editor_name, key in [
            ("external_blink_backend_id", "backend_id"),
            ("external_blink_display_name", "display_name"),
            ("external_blink_python", "python_executable"),
            ("external_blink_model_manifest", "model_manifest"),
        ]:
            if hasattr(self, editor_name):
                getattr(self, editor_name).setText(str(external_blink.get(key, "")))
        if hasattr(self, "external_blink_predict_command"):
            self.external_blink_predict_command.setPlainText(str(external_blink.get("predict_command", "")))
        if hasattr(self, "external_blink_train_command"):
            self.external_blink_train_command.setPlainText(str(external_blink.get("train_command", "")))
        locator_scope = parent_backend.get("locator_scope", [])
        if isinstance(locator_scope, list):
            selected = {str(part).strip() for part in locator_scope if str(part).strip()}
            for check in getattr(self, "locator_scope_checks", []):
                part_name = str(check.property("part_name") or check.text()).strip()
                check.setChecked(part_name in selected)

        ratios = parent_backend.get("parent_box_aspect_ratios", {})
        if isinstance(ratios, dict):
            for part_name in getattr(self, "parent_box_ratio_inputs", {}):
                self._set_parent_box_ratio_input(part_name, ratios.get(part_name, ""))

        for editor_name, key in [
            ("spin_conf", "conf"),
            ("spin_adapt", "adapt"),
            ("spin_pad", "pad"),
            ("spin_noise", "noise_floor"),
            ("spin_poly", "poly_epsilon"),
        ]:
            if hasattr(self, editor_name) and key in inference_params:
                getattr(self, editor_name).setText(str(inference_params.get(key)))

        vlm = inference_params.get("vlm_preannotation", {}) if isinstance(inference_params.get("vlm_preannotation"), dict) else {}
        selected_vlm = {str(part).strip() for part in vlm.get("target_parts", []) if str(part).strip()}
        for check in getattr(self, "vlm_target_part_checks", []):
            part_name = str(check.property("part_name") or check.text()).strip()
            check.setChecked(part_name in selected_vlm)
        if hasattr(self, "combo_vlm_processing_scope"):
            scope_value = str(vlm.get("processing_scope", "image_group") or "image_group")
            if scope_value == "current_image":
                scope_value = "image_group"
            index = self.combo_vlm_processing_scope.findData(scope_value)
            self.combo_vlm_processing_scope.setCurrentIndex(index if index >= 0 else 0)
        if hasattr(self, "combo_vlm_image_group"):
            self._populate_vlm_image_group_combo(str(vlm.get("image_group", "split") or "split"))
        if hasattr(self, "spin_vlm_concurrency"):
            try:
                concurrency = int(vlm.get("concurrency", 1))
            except Exception:
                concurrency = 1
            self.spin_vlm_concurrency.setValue(max(1, min(8, concurrency)))
        self._set_vlm_prompt_profile_controls(vlm)

    def _default_vlm_image_group_definitions(self):
        return [
            ("original", tr("Original Images", self.lang)),
            ("split", tr("Split Crops", self.lang)),
            ("hard_candidates", tr("Hard-joined Candidates", self.lang)),
            ("manual_done", tr("Manual Split Done", self.lang)),
            ("manual", tr("Manual Split Needed", self.lang)),
        ]

    def _normalize_vlm_image_group_definitions(self, raw_definitions):
        clean = []
        seen = set()

        def add(group_id, label):
            group_id = str(group_id or "").strip()
            label = str(label or "").strip()
            if not group_id or not label or group_id in seen:
                return
            seen.add(group_id)
            clean.append((group_id, label))

        for group_id, label in self._default_vlm_image_group_definitions():
            add(group_id, label)
        if isinstance(raw_definitions, list):
            for item in raw_definitions:
                if isinstance(item, dict):
                    add(item.get("id", ""), item.get("name", ""))
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    add(item[0], item[1])
        return clean

    def _populate_vlm_image_group_combo(self, selected_group=None):
        if not hasattr(self, "combo_vlm_image_group"):
            return
        current = str(selected_group or self.combo_vlm_image_group.currentData() or "split")
        self.combo_vlm_image_group.blockSignals(True)
        self.combo_vlm_image_group.clear()
        for group_id, label in self.vlm_image_group_definitions:
            self.combo_vlm_image_group.addItem(label, group_id)
        index = self.combo_vlm_image_group.findData(current)
        if index < 0:
            index = self.combo_vlm_image_group.findData("split")
        self.combo_vlm_image_group.setCurrentIndex(index if index >= 0 else 0)
        self.combo_vlm_image_group.blockSignals(False)

    def _external_blink_config_values(self):
        return {
            "backend_id": self.external_blink_backend_id.text().strip() if hasattr(self, "external_blink_backend_id") else DEFAULT_EXTERNAL_BLINK_BACKEND["backend_id"],
            "display_name": self.external_blink_display_name.text().strip() if hasattr(self, "external_blink_display_name") else DEFAULT_EXTERNAL_BLINK_BACKEND["display_name"],
            "python_executable": self.external_blink_python.text().strip() if hasattr(self, "external_blink_python") else "python",
            "predict_command": self._command_text(self.external_blink_predict_command) if hasattr(self, "external_blink_predict_command") else "",
            "train_command": self._command_text(self.external_blink_train_command) if hasattr(self, "external_blink_train_command") else "",
            "model_manifest": self.external_blink_model_manifest.text().strip() if hasattr(self, "external_blink_model_manifest") else "",
        }

    def _external_blink_validation_errors(self):
        if not hasattr(self, "child_backend_combo") or self.child_backend_combo.currentData() != CHILD_BACKEND_EXTERNAL:
            return []
        config = self._external_blink_config_values()
        errors = []
        if not config["backend_id"]:
            errors.append(tr("Child extension ID is required.", self.lang))
        if not config["predict_command"]:
            errors.append(tr("Child extension needs a predict command before it can be used for child-part annotation.", self.lang))
        commands = {
            "predict_child": config["predict_command"],
            "train_child": config["train_command"],
        }
        for command_name, command_text in commands.items():
            if command_text and "{contract}" not in command_text and "{contract_json}" not in command_text:
                errors.append(
                    _format_backend_contract_error(
                        tr(
                            "Child extension command '{0}' must include {contract} or {contract_json}.",
                            self.lang,
                        ),
                        command_name,
                    )
                )
        return errors

    def validate_external_blink_backend(self):
        errors = self._external_blink_validation_errors()
        if errors:
            self.external_blink_validation_label.setText("\n".join(errors))
            QMessageBox.warning(self, tr("Advanced Extensions", self.lang), "\n".join(errors))
            return False
        self.external_blink_validation_label.setText(tr("Child extension configuration looks valid.", self.lang))
        QMessageBox.information(self, tr("Advanced Extensions", self.lang), tr("Child extension configuration looks valid.", self.lang))
        return True

    def _current_profile_snapshot(self, update_metadata=True):
        if update_metadata:
            self._update_current_profile_metadata()
        active_id = self._active_profile_id()
        base_profile = self._active_profile()
        parent_backend = dict(base_profile.get("parent_backend", {}) if isinstance(base_profile.get("parent_backend"), dict) else {})
        child_defaults = dict(base_profile.get("child_backend_defaults", {}) if isinstance(base_profile.get("child_backend_defaults"), dict) else {})
        inference_params = dict(base_profile.get("inference_params", {}) if isinstance(base_profile.get("inference_params"), dict) else {})
        parent_backend.update(
            {
                "backend_type": self.parent_backend_combo.currentData() or PARENT_BACKEND_BUILTIN,
                "locator_scope": self._selected_locator_scope(),
                "train_params": {
                    "epochs": int(self.spin_epochs.text()),
                    "batch": int(self.spin_batch.text()),
                    "lr": float(self.spin_lr.text()),
                    "weight_decay": float(self.spin_wd.text()),
                },
                "parent_box_aspect_ratios": self._parent_box_aspect_ratio_values(),
                "external_backend": sanitize_external_backend_config(
                    {
                        "backend_id": self.external_backend_id.text(),
                        "display_name": self.external_display_name.text(),
                        "python_executable": self.external_python.text(),
                        "prepare_dataset_command": self._command_text(self.external_prepare_command),
                        "train_command": self._command_text(self.external_train_command),
                        "predict_command": self._command_text(self.external_predict_command),
                        "model_manifest": self.external_model_manifest.text(),
                    }
                ),
            }
        )
        child_defaults.update(
            {
                "backend_type": self.child_backend_combo.currentData() or CHILD_BACKEND_VIT_B,
                "input_size": int(self.combo_blink_input_size.currentData() or 224),
                "auto_shrink_steps": int(self.spin_blink_auto_shrink_steps.value())
                if hasattr(self, "spin_blink_auto_shrink_steps")
                else DEFAULT_CHILD_AUTO_SHRINK_STEPS,
                "training_strategy": sanitize_blink_training_strategy(
                    self.combo_blink_training_strategy.currentData()
                    if hasattr(self, "combo_blink_training_strategy")
                    else DEFAULT_BLINK_TRAINING_STRATEGY
                ),
                "train_params": {
                    "epochs": int(self.spin_blink_epochs.text()),
                    "batch": int(self.spin_blink_batch.text()),
                    "lr": float(self.spin_blink_lr.text()),
                    "weight_decay": float(self.spin_blink_wd.text()),
                },
                "heatmap_params": {
                    "input_size": int(float(self.spin_heatmap_input_size.text())),
                    "heatmap_sigma": float(self.spin_heatmap_sigma.text()),
                    "wh_loss_weight": float(self.spin_heatmap_wh_loss.text()),
                    "center_loss_weight": float(self.spin_heatmap_center_loss.text()),
                },
                "external_blink_backend": self._external_blink_config_values(),
            }
        )
        inference_params.update(
            {
                "conf": float(self.spin_conf.text()),
                "adapt": float(self.spin_adapt.text()),
                "pad": float(self.spin_pad.text()),
                "noise_floor": float(self.spin_noise.text()),
                "poly_epsilon": float(self.spin_poly.text()),
                "vlm_preannotation": {
                    "target_parts": self._selected_vlm_target_parts(),
                    "processing_scope": self.combo_vlm_processing_scope.currentData() or "image_group",
                    "image_group": self.combo_vlm_image_group.currentData() if hasattr(self, "combo_vlm_image_group") else "split",
                    "concurrency": int(self.spin_vlm_concurrency.value()) if hasattr(self, "spin_vlm_concurrency") else 1,
                    **self._current_vlm_prompt_profile_values(),
                },
            }
        )
        return {
            "profile_id": active_id,
            "display_name": self.profile_name_edit.text().strip() or active_id,
            "description": self.profile_description_edit.toPlainText().strip(),
            "profile_scope": "2d_stl",
            "parent_backend": parent_backend,
            "child_backend_defaults": child_defaults,
            "inference_params": inference_params,
        }

    def _updated_model_profiles(self):
        snapshot = self._current_profile_snapshot()
        active_id = self._project_active_profile_id()
        profiles = []
        replaced = False
        for profile in self.model_profiles.get("profiles", []):
            if not isinstance(profile, dict):
                continue
            if profile.get("profile_id") == snapshot.get("profile_id"):
                profiles.append(snapshot)
                replaced = True
            else:
                profiles.append(dict(profile))
        if not replaced:
            profiles.append(snapshot)
        clean = sanitize_model_profiles(
            {
                "schema_version": self.model_profiles.get("schema_version"),
                "active_profile_id": self._project_active_profile_id(),
                "profiles": profiles,
            },
            taxonomy=self.taxonomy,
            locator_scope=self._selected_locator_scope(),
            parent_box_aspect_ratios=self._parent_box_aspect_ratio_values(),
            vlm_preannotation={
                "target_parts": self._selected_vlm_target_parts(),
                "processing_scope": self.combo_vlm_processing_scope.currentData() or "image_group",
                "image_group": self.combo_vlm_image_group.currentData() if hasattr(self, "combo_vlm_image_group") else "split",
                "concurrency": int(self.spin_vlm_concurrency.value()) if hasattr(self, "spin_vlm_concurrency") else 1,
                **self._current_vlm_prompt_profile_values(),
            },
        )
        self.model_profiles = clean
        return clean

    def _profile_for_legacy_values(self, model_profiles):
        active_id = str((model_profiles or {}).get("active_profile_id") or DEFAULT_MODEL_PROFILE_ID)
        for profile in (model_profiles or {}).get("profiles", []):
            if isinstance(profile, dict) and str(profile.get("profile_id") or "") == active_id:
                return dict(profile)
        profiles = (model_profiles or {}).get("profiles", [])
        return dict(profiles[0]) if profiles and isinstance(profiles[0], dict) else self._current_profile_snapshot(update_metadata=False)

    def _legacy_values_from_profile(self, profile):
        parent_backend = profile.get("parent_backend", {}) if isinstance(profile.get("parent_backend"), dict) else {}
        child_defaults = profile.get("child_backend_defaults", {}) if isinstance(profile.get("child_backend_defaults"), dict) else {}
        parent_train = parent_backend.get("train_params", {}) if isinstance(parent_backend.get("train_params"), dict) else {}
        child_train = child_defaults.get("train_params", {}) if isinstance(child_defaults.get("train_params"), dict) else {}
        inference_params = profile.get("inference_params", {}) if isinstance(profile.get("inference_params"), dict) else {}
        vlm = inference_params.get("vlm_preannotation", {}) if isinstance(inference_params.get("vlm_preannotation"), dict) else {}
        return {
            "epochs": int(parent_train.get("epochs", self.spin_epochs.text())),
            "batch": int(parent_train.get("batch", self.spin_batch.text())),
            "blink_epochs": int(child_train.get("epochs", self.spin_blink_epochs.text())),
            "blink_batch": int(child_train.get("batch", self.spin_blink_batch.text())),
            "blink_lr": float(child_train.get("lr", self.spin_blink_lr.text())),
            "blink_weight_decay": float(child_train.get("weight_decay", self.spin_blink_wd.text())),
            "blink_input_size": int(child_defaults.get("input_size", self.combo_blink_input_size.currentData() or 224)),
            "blink_auto_shrink_steps": int(child_defaults.get("auto_shrink_steps", DEFAULT_CHILD_AUTO_SHRINK_STEPS)),
            "blink_training_strategy": sanitize_blink_training_strategy(
                child_defaults.get("training_strategy"),
                DEFAULT_BLINK_TRAINING_STRATEGY,
            ),
            "lr": float(parent_train.get("lr", self.spin_lr.text())),
            "wd": float(parent_train.get("weight_decay", self.spin_wd.text())),
            "conf": float(inference_params.get("conf", self.spin_conf.text())),
            "adapt": float(inference_params.get("adapt", self.spin_adapt.text())),
            "pad": float(inference_params.get("pad", self.spin_pad.text())),
            "noise_floor": float(inference_params.get("noise_floor", self.spin_noise.text())),
            "poly_epsilon": float(inference_params.get("poly_epsilon", self.spin_poly.text())),
            "locator_scope": list(parent_backend.get("locator_scope", self._selected_locator_scope()) or []),
            "vlm_preannotation": {
                "target_parts": list(vlm.get("target_parts", self._selected_vlm_target_parts()) or []),
                "processing_scope": str(vlm.get("processing_scope", self.combo_vlm_processing_scope.currentData() or "image_group") or "image_group"),
                "image_group": str(vlm.get("image_group", self.combo_vlm_image_group.currentData() if hasattr(self, "combo_vlm_image_group") else "split") or "split"),
                "concurrency": int(vlm.get("concurrency", self.spin_vlm_concurrency.value() if hasattr(self, "spin_vlm_concurrency") else 1) or 1),
                "prompt_profile_id": str(vlm.get("prompt_profile_id", DEFAULT_VLM_PROMPT_PROFILE_ID) or DEFAULT_VLM_PROMPT_PROFILE_ID),
                "prompt_profile": sanitize_vlm_prompt_profile(vlm.get("prompt_profile", {})),
            },
            "parent_box_aspect_ratios": dict(parent_backend.get("parent_box_aspect_ratios", self._parent_box_aspect_ratio_values()) or {}),
        }

    def _legacy_model_backend_from_profile(self, profile):
        parent_backend = profile.get("parent_backend", {}) if isinstance(profile.get("parent_backend"), dict) else {}
        return EXTERNAL_BACKEND_ID if parent_backend.get("backend_type") == PARENT_BACKEND_EXTERNAL else BUILTIN_BACKEND_ID

    def _external_backend_from_profile(self, profile):
        parent_backend = profile.get("parent_backend", {}) if isinstance(profile.get("parent_backend"), dict) else {}
        return sanitize_external_backend_config(parent_backend.get("external_backend", {}))

    def _current_parent_backend_requires_external_config(self):
        if hasattr(self, "parent_backend_combo"):
            return self.parent_backend_combo.currentData() == PARENT_BACKEND_EXTERNAL
        return self.backend_combo.currentData() == EXTERNAL_BACKEND_ID

    def _external_backend_validation_errors(self):
        if not self._current_parent_backend_requires_external_config():
            return []
        errors = []
        if not self.external_backend_id.text().strip():
            errors.append(tr("Parent extension ID is required.", self.lang))

        commands = {
            "prepare_dataset": self._command_text(self.external_prepare_command),
            "train": self._command_text(self.external_train_command),
            "predict": self._command_text(self.external_predict_command),
        }
        if not commands["train"] and not commands["predict"]:
            errors.append(tr("Parent extension needs at least a train command or a predict command.", self.lang))

        for command_name, command_text in commands.items():
            if command_text and "{contract}" not in command_text and "{contract_json}" not in command_text:
                errors.append(
                    _format_backend_contract_error(
                        tr(
                            "Parent extension command '{0}' must include {contract} or {contract_json}.",
                            self.lang,
                        ),
                        command_name,
                    )
                )
        return errors

    def validate_external_backend(self):
        errors = self._external_backend_validation_errors()
        if errors:
            self.external_validation_label.setText("\n".join(errors))
            QMessageBox.warning(self, tr("Advanced Extensions", self.lang), "\n".join(errors))
            return False
        self.external_validation_label.setText(tr("Parent extension configuration looks valid.", self.lang))
        QMessageBox.information(self, tr("Advanced Extensions", self.lang), tr("Parent extension configuration looks valid.", self.lang))
        return True

    def accept_with_validation(self):
        errors = self._external_backend_validation_errors()
        errors.extend(self._external_blink_validation_errors())
        errors.extend(self._parent_box_aspect_ratio_errors())
        if not self._selected_locator_scope():
            errors.append(tr("At least one main locator part must be selected.", self.lang))
        if errors:
            message = "\n".join(errors)
            self.external_validation_label.setText(message)
            if hasattr(self, "external_blink_validation_label"):
                self.external_blink_validation_label.setText(message)
            self.locator_scope_validation_label.setText(message)
            QMessageBox.warning(self, tr("Model Settings", self.lang), message)
            return
        self.accept()
