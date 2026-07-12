try:
    from AntSleap.ui.model_settings_dependencies import *
except ImportError:
    from ui.model_settings_dependencies import *


class ModelSettingsDatasetMixin:
    def _make_scroll_tab(self, content_widget):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        scroll.setWidget(content_widget)
        return scroll

    def _make_command_editor(self, text, placeholder):
        editor = QTextEdit()
        editor.setAcceptRichText(False)
        editor.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        editor.setMinimumHeight(72)
        editor.setPlainText(str(text or ""))
        editor.setPlaceholderText(placeholder)
        return editor

    def _make_prompt_profile_editor(self):
        editor = QTextEdit()
        editor.setAcceptRichText(False)
        editor.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        editor.setMinimumHeight(72)
        return editor

    def _toggle_vlm_details(self, checked):
        details = getattr(self, "vlm_details_widget", None)
        if details is not None:
            details.setVisible(bool(checked))
        toggle = getattr(self, "btn_vlm_detail_toggle", None)
        if toggle is not None:
            toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)

    def _update_blink_training_strategy_note(self):
        combo = getattr(self, "combo_blink_training_strategy", None)
        label = getattr(self, "blink_training_strategy_note", None)
        if combo is None or label is None:
            return
        strategy = sanitize_blink_training_strategy(combo.currentData())
        label.setText(blink_training_strategy_note(strategy, self.lang))

    def _command_text(self, editor):
        return editor.toPlainText().strip()

    def _set_prompt_editor_read_only(self, read_only):
        for widget in [
            getattr(self, "vlm_prompt_profile_name", None),
            getattr(self, "vlm_prompt_taxon_context", None),
            getattr(self, "vlm_prompt_body_rules", None),
            getattr(self, "vlm_prompt_anchor_rules", None),
            getattr(self, "vlm_prompt_extra_instructions", None),
        ]:
            if widget is not None:
                widget.setReadOnly(bool(read_only))

    def _set_vlm_prompt_profile_controls(self, settings):
        if not hasattr(self, "combo_vlm_prompt_profile"):
            return
        settings = settings if isinstance(settings, dict) else {}
        profile = sanitize_vlm_prompt_profile(settings.get("prompt_profile", {}))
        profile_id = str(settings.get("prompt_profile_id") or profile.get("profile_id") or DEFAULT_VLM_PROMPT_PROFILE_ID)
        if profile_id == DEFAULT_VLM_PROMPT_PROFILE_ID:
            profile = default_vlm_prompt_profile()
        else:
            profile_id = "project_custom"
        self._last_custom_vlm_prompt_profile = sanitize_vlm_prompt_profile(profile if profile_id != DEFAULT_VLM_PROMPT_PROFILE_ID else {"profile_id": "project_custom"})
        self.combo_vlm_prompt_profile.blockSignals(True)
        index = self.combo_vlm_prompt_profile.findData(profile_id)
        self.combo_vlm_prompt_profile.setCurrentIndex(index if index >= 0 else 0)
        self.combo_vlm_prompt_profile.blockSignals(False)
        self.vlm_prompt_profile_name.setText(str(profile.get("display_name", "")))
        self.vlm_prompt_taxon_context.setPlainText(str(profile.get("taxon_context", "")))
        self.vlm_prompt_body_rules.setPlainText(str(profile.get("body_focus_rules", "")))
        self.vlm_prompt_anchor_rules.setPlainText(str(profile.get("part_anchor_rules", "")))
        self.vlm_prompt_extra_instructions.setPlainText(str(profile.get("extra_instructions", "")))
        self._refresh_vlm_prompt_profile_editors()

    def _refresh_vlm_prompt_profile_editors(self):
        if not hasattr(self, "combo_vlm_prompt_profile"):
            return
        is_builtin = self.combo_vlm_prompt_profile.currentData() == DEFAULT_VLM_PROMPT_PROFILE_ID
        if is_builtin:
            self._last_custom_vlm_prompt_profile = self._current_vlm_prompt_profile_values()["prompt_profile"]
            profile = default_vlm_prompt_profile()
            self.vlm_prompt_profile_name.setText(str(profile.get("display_name", "")))
            self.vlm_prompt_taxon_context.setPlainText(str(profile.get("taxon_context", "")))
            self.vlm_prompt_body_rules.setPlainText(str(profile.get("body_focus_rules", "")))
            self.vlm_prompt_anchor_rules.setPlainText(str(profile.get("part_anchor_rules", "")))
            self.vlm_prompt_extra_instructions.setPlainText(str(profile.get("extra_instructions", "")))
        else:
            profile = sanitize_vlm_prompt_profile(getattr(self, "_last_custom_vlm_prompt_profile", {}) or {"profile_id": "project_custom"})
            self.vlm_prompt_profile_name.setText(str(profile.get("display_name", "")))
            self.vlm_prompt_taxon_context.setPlainText(str(profile.get("taxon_context", "")))
            self.vlm_prompt_body_rules.setPlainText(str(profile.get("body_focus_rules", "")))
            self.vlm_prompt_anchor_rules.setPlainText(str(profile.get("part_anchor_rules", "")))
            self.vlm_prompt_extra_instructions.setPlainText(str(profile.get("extra_instructions", "")))
        self._set_prompt_editor_read_only(is_builtin)

    def _current_vlm_prompt_profile_values(self):
        if not hasattr(self, "combo_vlm_prompt_profile"):
            profile = default_vlm_prompt_profile()
            return {
                "prompt_profile_id": profile["profile_id"],
                "prompt_profile": profile,
            }
        if self.combo_vlm_prompt_profile.currentData() == DEFAULT_VLM_PROMPT_PROFILE_ID:
            profile = default_vlm_prompt_profile()
            return {
                "prompt_profile_id": DEFAULT_VLM_PROMPT_PROFILE_ID,
                "prompt_profile": profile,
            }
        raw_profile = {
            "profile_id": "project_custom",
            "display_name": self.vlm_prompt_profile_name.text().strip() or tr("Project Custom Prompt", self.lang),
            "taxon_context": self.vlm_prompt_taxon_context.toPlainText().strip(),
            "body_focus_rules": self.vlm_prompt_body_rules.toPlainText().strip(),
            "part_anchor_rules": self.vlm_prompt_anchor_rules.toPlainText().strip(),
            "extra_instructions": self.vlm_prompt_extra_instructions.toPlainText().strip(),
        }
        profile = sanitize_vlm_prompt_profile(raw_profile)
        return {
            "prompt_profile_id": "project_custom",
            "prompt_profile": profile,
        }

    def _blink_dataset_owner_project(self):
        owner = getattr(self, "owner_window", None)
        project = getattr(owner, "project", None) if owner is not None else None
        if project is None:
            project = getattr(owner, "project_manager", None) if owner is not None else None
        return owner, project

    def _refresh_blink_dataset_table(self):
        if not hasattr(self, "blink_dataset_tree"):
            return
        self.blink_dataset_tree.clear()
        self.blink_dataset_rows = []
        _owner, project = self._blink_dataset_owner_project()
        summarize = getattr(project, "summarize_blink_trajectory_datasets", None)
        if callable(summarize):
            try:
                self.blink_dataset_rows = [
                    dict(row)
                    for row in summarize()
                    if isinstance(row, dict)
                ]
            except Exception:
                self.blink_dataset_rows = []
        if not self.blink_dataset_rows:
            item = QTreeWidgetItem(
                [
                    tr("No Blink shrink trajectory datasets have been generated yet.", self.lang),
                    "",
                    "",
                    "",
                ]
            )
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.blink_dataset_tree.addTopLevelItem(item)
        else:
            for row in self.blink_dataset_rows:
                parent_part = str(row.get("parent_part") or tr("Unknown", self.lang))
                child_part = str(row.get("child_part") or tr("Unknown", self.lang))
                sources = row.get("sources", [])
                if not isinstance(sources, list):
                    sources = []
                item = QTreeWidgetItem(
                    [
                        f"{parent_part} -> {child_part}",
                        str(row.get("image_count", 0)),
                        str(row.get("frame_count", 0)),
                        ", ".join(str(source) for source in sources if str(source).strip()) or tr("Unknown", self.lang),
                    ]
                )
                item.setData(0, Qt.ItemDataRole.UserRole, dict(row))
                self.blink_dataset_tree.addTopLevelItem(item)
        self.blink_dataset_tree.resizeColumnToContents(1)
        self.blink_dataset_tree.resizeColumnToContents(2)
        self.blink_dataset_tree.resizeColumnToContents(3)
        self._refresh_blink_dataset_actions()

    def _selected_blink_dataset_summary(self):
        if not hasattr(self, "blink_dataset_tree"):
            return None
        item = self.blink_dataset_tree.currentItem()
        if item is None:
            return None
        summary = item.data(0, Qt.ItemDataRole.UserRole)
        return dict(summary) if isinstance(summary, dict) else None

    def _refresh_blink_dataset_actions(self):
        summary = self._selected_blink_dataset_summary()
        enabled = bool(summary)
        if hasattr(self, "btn_blink_dataset_details"):
            self.btn_blink_dataset_details.setEnabled(enabled)
        if hasattr(self, "btn_blink_dataset_delete"):
            self.btn_blink_dataset_delete.setEnabled(enabled)

    def _format_blink_dataset_details(self, summary):
        parent_part = str(summary.get("parent_part") or tr("Unknown", self.lang))
        child_part = str(summary.get("child_part") or tr("Unknown", self.lang))
        sources = summary.get("sources", [])
        if not isinstance(sources, list):
            sources = []
        lines = [
            tr("Route", self.lang) + f": {parent_part} -> {child_part}",
            tr("Images", self.lang) + f": {summary.get('image_count', 0)}",
            tr("Frames", self.lang) + f": {summary.get('frame_count', 0)}",
            tr("Sources", self.lang) + ": " + (", ".join(str(source) for source in sources if str(source).strip()) or tr("Unknown", self.lang)),
            "",
        ]
        images = summary.get("images", [])
        if isinstance(images, list):
            for index, image_info in enumerate(images, start=1):
                if not isinstance(image_info, dict):
                    continue
                image_path = str(image_info.get("image_path") or "")
                source = str(image_info.get("source") or "unknown")
                frame_count = image_info.get("frame_count", 0)
                parent_box = image_info.get("parent_box")
                lines.append(f"{index}. {image_path}")
                lines.append(f"   {tr('Frames', self.lang)}: {frame_count}; {tr('Source', self.lang)}: {source}")
                if parent_box:
                    lines.append(f"   {tr('Parent box: {0}', self.lang).format(parent_box)}")
        return "\n".join(lines).strip()

    def _show_blink_dataset_details(self):
        summary = self._selected_blink_dataset_summary()
        if not summary:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("Blink Shrink Dataset Details", self.lang))
        dialog.resize(720, 520)
        layout = QVBoxLayout(dialog)
        details = QTextEdit()
        details.setReadOnly(True)
        details.setAcceptRichText(False)
        details.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        details.setPlainText(self._format_blink_dataset_details(summary))
        layout.addWidget(details)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        apply_theme_dialog_button_box_style(
            buttons,
            ok_role=BUTTON_ROLE_COMMIT,
            cancel_role=BUTTON_ROLE_STOP,
            theme=getattr(getattr(self, "owner_window", None), "current_theme", "dark"),
        )
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.exec()

    def _delete_selected_blink_dataset(self):
        summary = self._selected_blink_dataset_summary()
        if not summary:
            return
        parent_part = str(summary.get("parent_part") or "").strip()
        child_part = str(summary.get("child_part") or "").strip()
        route_label = f"{parent_part} -> {child_part}"
        image_count = int(summary.get("image_count") or 0)
        reply = themed_yes_no_question(
            self,
            tr("Delete Blink Shrink Dataset", self.lang),
            tr(
                "Delete Blink shrink dataset for {0}?\n\nThis removes {1} image trajectory record(s) from the current project. It does not delete labels or images.",
                self.lang,
            ).format(route_label, image_count),
            confirm_role=BUTTON_ROLE_DESTRUCTIVE,
        )
        if reply != QMessageBox.Yes:
            return
        owner, project = self._blink_dataset_owner_project()
        delete_dataset = getattr(project, "delete_blink_trajectory_dataset", None)
        removed = 0
        if callable(delete_dataset):
            removed = int(delete_dataset(parent_part, child_part) or 0)
        self._refresh_blink_dataset_table()
        refresh_state = getattr(owner, "_refresh_blink_refine_state", None)
        if callable(refresh_state):
            refresh_state()
        refresh_files = getattr(owner, "refresh_file_list", None)
        if callable(refresh_files):
            refresh_files()
        log = getattr(owner, "log", None)
        if callable(log):
            log(
                tr("Deleted {0} Blink shrink trajectory record(s) for {1}.", self.lang).format(
                    removed,
                    route_label,
                )
            )
