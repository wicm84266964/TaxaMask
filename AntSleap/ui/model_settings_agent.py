try:
    from AntSleap.ui.model_settings_dependencies import *
except ImportError:
    from ui.model_settings_dependencies import *


class ModelSettingsAgentMixin:
    def _selected_locator_scope(self):
        selected = []
        for check in self.locator_scope_checks:
            if check.isChecked():
                part_name = str(check.property("part_name") or check.text()).strip()
                if part_name:
                    selected.append(part_name)
        return selected

    def _selected_vlm_target_parts(self):
        selected = []
        for check in self.vlm_target_part_checks:
            if check.isChecked():
                part_name = str(check.property("part_name") or check.text()).strip()
                if part_name:
                    selected.append(part_name)
        return selected

    def _format_parent_ratio_number(self, value):
        try:
            number = float(value)
        except Exception:
            return ""
        if number <= 0:
            return ""
        if abs(number - round(number)) < 1e-9:
            return str(int(round(number)))
        return f"{number:.6g}"

    def _parent_ratio_display_values(self, aspect_ratio):
        try:
            ratio = float(aspect_ratio)
        except Exception:
            return "", ""
        if ratio <= 0:
            return "", ""
        fraction = Fraction(ratio).limit_denominator(64)
        approximate = fraction.numerator / fraction.denominator
        if abs(approximate - ratio) <= max(1e-6, abs(ratio) * 1e-4):
            return str(fraction.numerator), str(fraction.denominator)
        return self._format_parent_ratio_number(ratio), "1"

    def _parent_ratio_editor_pair(self, editors):
        if isinstance(editors, (tuple, list)) and len(editors) >= 2:
            return editors[0], editors[1]
        return None, None

    def _set_parent_box_ratio_input(self, part_name, aspect_ratio):
        editors = getattr(self, "parent_box_ratio_inputs", {}).get(part_name)
        width_edit, height_edit = self._parent_ratio_editor_pair(editors)
        if width_edit is None or height_edit is None:
            if hasattr(editors, "setText"):
                editors.setText(str(aspect_ratio) if aspect_ratio != "" else "")
            return
        width_text, height_text = self._parent_ratio_display_values(aspect_ratio)
        width_edit.setText(width_text)
        height_edit.setText(height_text)

    def _parent_box_aspect_ratio_errors(self):
        errors = []
        for part_name, editors in getattr(self, "parent_box_ratio_inputs", {}).items():
            width_edit, height_edit = self._parent_ratio_editor_pair(editors)
            if width_edit is None or height_edit is None:
                text = editors.text().strip() if hasattr(editors, "text") else ""
                if not text:
                    continue
                try:
                    ratio = float(text)
                except Exception:
                    ratio = 0
                if ratio <= 0:
                    errors.append(tr("Parent box ratio for {0} must have positive width and height values.", self.lang).format(part_name))
                continue
            width_text = width_edit.text().strip()
            height_text = height_edit.text().strip()
            if not width_text and not height_text:
                continue
            try:
                width_value = float(width_text)
                height_value = float(height_text)
            except Exception:
                width_value = 0
                height_value = 0
            if width_value <= 0 or height_value <= 0:
                errors.append(tr("Parent box ratio for {0} must have positive width and height values.", self.lang).format(part_name))
        return errors

    def _parent_box_aspect_ratio_values(self):
        ratios = {}
        for part_name, editors in getattr(self, "parent_box_ratio_inputs", {}).items():
            width_edit, height_edit = self._parent_ratio_editor_pair(editors)
            if width_edit is None or height_edit is None:
                text = editors.text().strip() if hasattr(editors, "text") else ""
                if not text:
                    continue
                try:
                    ratio = float(text)
                except Exception:
                    continue
                if ratio > 0:
                    ratios[part_name] = ratio
                continue
            width_text = width_edit.text().strip()
            height_text = height_edit.text().strip()
            if not width_text and not height_text:
                continue
            try:
                width_value = float(width_text)
                height_value = float(height_text)
            except Exception:
                continue
            if width_value <= 0 or height_value <= 0:
                continue
            ratio = width_value / height_value
            if ratio > 0:
                ratios[part_name] = ratio
        return ratios

    def request_agent_help(self):
        self.agent_requested.emit(self.get_agent_context())
        self.reject()

    def get_agent_context(self):
        prepare_command = self._command_text(self.external_prepare_command)
        train_command = self._command_text(self.external_train_command)
        predict_command = self._command_text(self.external_predict_command)
        child_predict_command = self._command_text(self.external_blink_predict_command)
        child_train_command = self._command_text(self.external_blink_train_command)
        selected_profile = self._current_profile_snapshot(update_metadata=False)
        project_active_profile = self._profile_by_id(self._project_active_profile_id()) or selected_profile
        selected_model_backend = self._legacy_model_backend_from_profile(selected_profile)
        active_model_backend = self._legacy_model_backend_from_profile(project_active_profile)
        parent_backend = selected_profile.get("parent_backend", {}) if isinstance(selected_profile.get("parent_backend"), dict) else {}
        child_defaults = selected_profile.get("child_backend_defaults", {}) if isinstance(selected_profile.get("child_backend_defaults"), dict) else {}
        parent_backend_type = parent_backend.get("backend_type", self.parent_backend_combo.currentData() if hasattr(self, "parent_backend_combo") else PARENT_BACKEND_BUILTIN)
        child_backend_type = child_defaults.get("backend_type", self.child_backend_combo.currentData() if hasattr(self, "child_backend_combo") else CHILD_BACKEND_VIT_B)
        child_training_strategy = sanitize_blink_training_strategy(
            child_defaults.get("training_strategy"),
            DEFAULT_BLINK_TRAINING_STRATEGY,
        )
        route_differences = self._routes_differing_from_child_default(selected_profile)
        route_summary = []
        for route in route_differences[:8]:
            parent = str(route.get("parent") or "").strip()
            child = str(route.get("child") or "").strip()
            backend = _route_backend_from_entry(route)
            if parent and child:
                route_summary.append(f"{parent}->{child}:{backend}")
        validation_errors = self._external_backend_validation_errors() + self._external_blink_validation_errors()
        return {
            "source_workbench": "stl_model_settings",
            "project_type": "settings",
            "settings_scope": "2d_stl_model",
            "settings_question_focus": "Advanced Extensions configuration for 2D/STL model profiles: parent model source, child expert default, custom extension contracts, and route expert compatibility.",
            "model_backend": active_model_backend,
            "selected_profile_model_backend": selected_model_backend,
            "advanced_extension_scope": "2d_stl_model_profile",
            "parent_model_source": str(parent_backend_type or ""),
            "parent_model_source_label": _parent_backend_label(parent_backend_type, self.lang),
            "default_child_expert": str(child_backend_type or ""),
            "default_child_expert_label": _child_backend_label(child_backend_type, self.lang),
            "blink_training_strategy": child_training_strategy,
            "blink_training_strategy_label": blink_training_strategy_label(child_training_strategy, self.lang),
            "default_child_route_backend": _route_backend_from_child_backend(child_backend_type),
            "route_specific_backend_count": str(len(route_differences)),
            "route_specific_backend_summary": "; ".join(route_summary),
            "runtime_device": self.combo_runtime_device.currentData() or "auto",
            "external_backend_id": self.external_backend_id.text().strip(),
            "external_display_name": self.external_display_name.text().strip(),
            "external_python": self.external_python.text().strip(),
            "parent_prepare_command_present": _agent_yes_no(bool(prepare_command)),
            "parent_train_command_present": _agent_yes_no(bool(train_command)),
            "parent_predict_command_present": _agent_yes_no(bool(predict_command)),
            "parent_prepare_command_has_contract": _agent_yes_no(_agent_command_has_contract(prepare_command)),
            "parent_train_command_has_contract": _agent_yes_no(_agent_command_has_contract(train_command)),
            "parent_predict_command_has_contract": _agent_yes_no(_agent_command_has_contract(predict_command)),
            "parent_model_manifest_present": _agent_yes_no(bool(self.external_model_manifest.text().strip())),
            "prepare_command_present": _agent_yes_no(bool(prepare_command)),
            "train_command_present": _agent_yes_no(bool(train_command)),
            "predict_command_present": _agent_yes_no(bool(predict_command)),
            "prepare_command_has_contract": _agent_yes_no(_agent_command_has_contract(prepare_command)),
            "train_command_has_contract": _agent_yes_no(_agent_command_has_contract(train_command)),
            "predict_command_has_contract": _agent_yes_no(_agent_command_has_contract(predict_command)),
            "model_manifest_present": _agent_yes_no(bool(self.external_model_manifest.text().strip())),
            "child_extension_id": self.external_blink_backend_id.text().strip(),
            "child_extension_display_name": self.external_blink_display_name.text().strip(),
            "child_extension_python": self.external_blink_python.text().strip(),
            "child_predict_command_present": _agent_yes_no(bool(child_predict_command)),
            "child_train_command_present": _agent_yes_no(bool(child_train_command)),
            "child_predict_command_has_contract": _agent_yes_no(_agent_command_has_contract(child_predict_command)),
            "child_train_command_has_contract": _agent_yes_no(_agent_command_has_contract(child_train_command)),
            "child_model_manifest_present": _agent_yes_no(bool(self.external_blink_model_manifest.text().strip())),
            "locator_scope_count": str(len(self._selected_locator_scope())),
            "parent_box_ratio_count": str(len(self._parent_box_aspect_ratio_values())),
            "child_backend": self.child_backend_combo.currentData() if hasattr(self, "child_backend_combo") else CHILD_BACKEND_VIT_B,
            "model_profile_id": self._project_active_profile_id(),
            "selected_model_profile_id": self._active_profile_id(),
            "validation_errors": _agent_error_summary(validation_errors),
        }
    def get_values(self):
        try:
            model_profiles = self._updated_model_profiles()
            active_profile = self._profile_for_legacy_values(model_profiles)
            active_values = self._legacy_values_from_profile(active_profile)
            return {
                'epochs': active_values["epochs"],
                'batch': active_values["batch"],
                'blink_epochs': active_values["blink_epochs"],
                'blink_batch': active_values["blink_batch"],
                'blink_lr': active_values["blink_lr"],
                'blink_weight_decay': active_values["blink_weight_decay"],
                'blink_input_size': active_values["blink_input_size"],
                'blink_auto_shrink_steps': active_values["blink_auto_shrink_steps"],
                'blink_training_strategy': active_values["blink_training_strategy"],
                'lr': active_values["lr"],
                'wd': active_values["wd"],
                'conf': active_values["conf"],
                'adapt': active_values["adapt"],
                'pad': active_values["pad"],
                'noise_floor': active_values["noise_floor"],
                'poly_epsilon': active_values["poly_epsilon"],
                'locator_scope': active_values["locator_scope"],
                'vlm_preannotation': active_values["vlm_preannotation"],
                'parent_box_aspect_ratios': active_values["parent_box_aspect_ratios"],
                'runtime_device': self.combo_runtime_device.currentData() or "auto",
                'model_backend': self._legacy_model_backend_from_profile(active_profile),
                'model_profiles': model_profiles,
                'external_backend': self._external_backend_from_profile(active_profile),
            }
        except: return None
