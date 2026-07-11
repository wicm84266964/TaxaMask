try:
    from AntSleap.ui.main_window_navigation_dependencies import *
except ImportError:
    from ui.main_window_navigation_dependencies import *


class MainWindowPartTreeMixin:
    def _part_item_name(self, item):
        if item is None:
            return None
        part_name = item.data(0, Qt.UserRole)
        clean_name = str(part_name or "").strip()
        return clean_name or None

    def _current_part_name(self):
        return self._part_item_name(self.part_list.currentItem())

    def _workbench_parent_parts(self):
        project = getattr(self, "project", None)
        taxonomy = list(getattr(project, "project_data", {}).get("taxonomy", [])) if project is not None else []
        taxonomy_set = {str(part).strip() for part in taxonomy if str(part).strip()}
        get_scope = getattr(project, "get_locator_scope", None)
        try:
            scope = get_scope() if callable(get_scope) else []
        except Exception:
            scope = []
        parents = []
        for part in scope or []:
            clean = str(part or "").strip()
            if clean and clean in taxonomy_set and clean not in parents:
                parents.append(clean)
        return parents

    def _is_parent_part(self, part_name):
        clean_part = str(part_name or "").strip()
        return bool(clean_part) and clean_part in set(self._workbench_parent_parts())

    def _part_tree_parent_for(self, part_name):
        clean_part = str(part_name or "").strip()
        if not clean_part or not hasattr(self, "part_list"):
            return None

        def walk(item):
            if item is None:
                return None
            if self._part_item_name(item) == clean_part:
                parent_item = item.parent()
                parent_part = self._part_item_name(parent_item)
                return parent_part if parent_part and parent_part != clean_part else None
            for index in range(item.childCount()):
                found = walk(item.child(index))
                if found:
                    return found
            return None

        for index in range(self.part_list.topLevelItemCount()):
            found_parent = walk(self.part_list.topLevelItem(index))
            if found_parent:
                return found_parent
        return None

    def _append_part_tree_item(self, parent_item, text, part_name=None, tooltip=None):
        item = QTreeWidgetItem(parent_item) if parent_item is not None else QTreeWidgetItem(self.part_list)
        item.setText(0, text)
        item.setData(0, Qt.UserRole, part_name)
        if tooltip:
            item.setToolTip(0, tooltip)
        return item

    def _select_part_in_tree(self, part_name):
        clean_name = str(part_name or "").strip()
        if not clean_name:
            return False

        def walk(item):
            if item is None:
                return None
            if self._part_item_name(item) == clean_name:
                return item
            for index in range(item.childCount()):
                found = walk(item.child(index))
                if found is not None:
                    return found
            return None

        for index in range(self.part_list.topLevelItemCount()):
            found_item = walk(self.part_list.topLevelItem(index))
            if found_item is not None:
                self.part_list.setCurrentItem(found_item)
                return True
        return False

    def _first_selectable_part_item(self):
        def walk(item):
            if item is None:
                return None
            if self._part_item_name(item):
                return item
            for index in range(item.childCount()):
                found = walk(item.child(index))
                if found is not None:
                    return found
            return None

        for index in range(self.part_list.topLevelItemCount()):
            found_item = walk(self.part_list.topLevelItem(index))
            if found_item is not None:
                return found_item
        return None

    def _refresh_part_tree(self, selected_part=None):
        if getattr(self, "_refreshing_part_tree", False):
            return
        if not hasattr(self, "part_list"):
            return
        self._refreshing_part_tree = True
        previous_selection = selected_part or self._current_part_name()
        try:
            self.part_list.blockSignals(True)
            self.part_list.clear()
            groups = build_part_tree_groups(
                self.project.project_data.get("taxonomy", []),
                self.project.get_locator_scope(),
                self.project.iter_cascade_routes(),
            )

            for parent_group in groups.get("parents", []):
                parent_part = parent_group.get("part")
                if not parent_part:
                    continue
                parent_item = self._append_part_tree_item(
                    None,
                    tr(parent_part, self.current_lang),
                    part_name=parent_part,
                    tooltip=tr("Main locator parts", self.current_lang),
                )
                for child_part in parent_group.get("children", []):
                    self._append_part_tree_item(
                        parent_item,
                        tr(child_part, self.current_lang),
                        part_name=child_part,
                        tooltip=tr("Blink child parts", self.current_lang),
                    )
                parent_item.setExpanded(True)

            cross_region = groups.get("cross_region", [])
            if cross_region:
                group_item = self._append_part_tree_item(
                    None,
                    tr("Cross-region structures", self.current_lang),
                    tooltip=tr("Structure group", self.current_lang),
                )
                for part_name in cross_region:
                    self._append_part_tree_item(group_item, tr(part_name, self.current_lang), part_name=part_name)
                group_item.setExpanded(True)

            ungrouped = groups.get("ungrouped", [])
            if ungrouped:
                group_item = self._append_part_tree_item(
                    None,
                    tr("Ungrouped structures", self.current_lang),
                    tooltip=tr("Structure group", self.current_lang),
                )
                for part_name in ungrouped:
                    self._append_part_tree_item(group_item, tr(part_name, self.current_lang), part_name=part_name)
                group_item.setExpanded(True)

            selected = self._select_part_in_tree(previous_selection)
            if not selected:
                first_part_item = self._first_selectable_part_item()
                if first_part_item is not None:
                    self.part_list.setCurrentItem(first_part_item)
        finally:
            self.part_list.blockSignals(False)
            self._refreshing_part_tree = False

        current_part = self._current_part_name()
        if current_part:
            self.canvas.set_active_part(current_part)
            self.update_db_description(current_part)
        else:
            self.canvas.set_active_part(None)
            self.desc_box.clear()
        if hasattr(self, "blink_refine_panel"):
            self._refresh_blink_refine_state()

    def add_taxonomy_part(self):
        name, ok = QInputDialog.getText(self, tr("Add Structure", self.current_lang), tr("Structure Name:", self.current_lang))
        if ok and name:
            if self.project.add_taxonomy_part(name.strip()):
                self.refresh_ui()
                self.project.save_project()
            else:
                QMessageBox.warning(self, tr("Error", self.current_lang), tr("Exists.", self.current_lang))

    def _count_ai_labels_for_images(self, image_paths):
        count = 0
        for image_path in image_paths or []:
            entry = self.project.project_data.get("labels", {}).get(image_path, {})
            descriptions = entry.get("descriptions", {}) if isinstance(entry.get("descriptions", {}), dict) else {}
            count += sum(1 for desc in descriptions.values() if desc == "Auto-Annotated")
        return count

    def _choose_clear_ai_scope(self):
        all_images = [path for path in self.project.project_data.get("images", []) if path]
        scope_options = [("__all__", tr("All project images", self.current_lang), all_images)]
        image_groups = self._project_image_groups(images=all_images)
        for group_id, group_label in self._all_image_group_definitions():
            group_images = list(image_groups.get(group_id, []) or [])
            if group_images:
                scope_options.append((group_id, tr("Images in group: {0}", self.current_lang).format(group_label), group_images))

        dialog = QDialog(self)
        dialog.setWindowTitle(tr("Clear AI Label Scope", self.current_lang))
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        layout.addWidget(QLabel(tr("Scope:", self.current_lang)))
        scope_combo = NoWheelComboBox()
        for group_id, label, paths in scope_options:
            scope_combo.addItem(label, {"group_id": group_id, "label": label, "paths": list(paths)})
        layout.addWidget(scope_combo)
        summary_label = QLabel()
        summary_label.setWordWrap(True)
        summary_label.setObjectName("mutedLabel")
        layout.addWidget(summary_label)
        button_row = QHBoxLayout()
        clear_button = QPushButton(tr("Clear AI", self.current_lang))
        apply_semantic_button_style(clear_button, BUTTON_ROLE_DESTRUCTIVE)
        cancel_button = QPushButton(tr("Cancel", self.current_lang))
        apply_semantic_button_style(cancel_button, BUTTON_ROLE_STOP)
        button_row.addStretch(1)
        button_row.addWidget(clear_button)
        button_row.addWidget(cancel_button)
        layout.addLayout(button_row)
        selected_payload = {"accepted": False, "paths": [], "label": "", "count": 0}

        def refresh_summary():
            payload = scope_combo.currentData() or {}
            paths = list(payload.get("paths", []) or [])
            count = self._count_ai_labels_for_images(paths)
            selected_payload.update({"paths": paths, "label": payload.get("label", ""), "count": count})
            if count:
                summary_label.setText(
                    tr(
                        "This will remove {0} AI label(s) from {1} image(s). Manual and confirmed labels are kept.",
                        self.current_lang,
                    ).format(count, len(paths))
                )
                clear_button.setEnabled(True)
            else:
                summary_label.setText(tr("No AI labels found in the selected scope.", self.current_lang))
                clear_button.setEnabled(False)

        def accept_scope():
            selected_payload["accepted"] = True
            dialog.accept()

        scope_combo.currentIndexChanged.connect(lambda _index: refresh_summary())
        clear_button.clicked.connect(accept_scope)
        cancel_button.clicked.connect(dialog.reject)
        refresh_summary()
        self._prepare_progress_dialog(dialog, width=460)
        if not dialog.exec() or not selected_payload["accepted"]:
            return None
        return {
            "paths": list(selected_payload.get("paths", []) or []),
            "label": str(selected_payload.get("label", "") or ""),
            "count": int(selected_payload.get("count", 0) or 0),
        }

    def rename_taxonomy_part(self):
        old_name = self._current_part_name()
        if not old_name:
            return
        new_name, ok = QInputDialog.getText(
            self,
            tr("Rename Structure", self.current_lang),
            tr("New Structure Name:", self.current_lang),
            text=old_name,
        )
        new_name = str(new_name or "").strip()
        if not ok or not new_name or new_name == old_name:
            return
        if themed_yes_no_question(
            self,
            tr("Rename Structure", self.current_lang),
            tr(
                "Rename '{0}' to '{1}'? Existing labels, VLM drafts, parent-child routes, and training context for this structure will be moved to the new name.",
                self.current_lang,
            ).format(old_name, new_name),
            confirm_role=BUTTON_ROLE_COMMIT,
        ) != QMessageBox.Yes:
            return

        rename_part = getattr(self.project, "rename_taxonomy_part", None)
        renamed = bool(rename_part(old_name, new_name, save=False)) if callable(rename_part) else False
        if not renamed:
            QMessageBox.warning(
                self,
                tr("Rename Structure", self.current_lang),
                tr("Could not rename structure. The new name may already exist or contain unsafe characters.", self.current_lang),
            )
            return

        self._schedule_project_save()
        self.refresh_ui()
        self._select_part_in_tree(new_name)
        if self.current_image:
            self.canvas.set_polygons(self.project.get_labels(self.current_image))
            self._refresh_current_canvas_boxes()
        self._refresh_blink_refine_state()

    def remove_taxonomy_part(self):
        part_name = self._current_part_name()
        if not part_name:
            return
        if themed_yes_no_question(
            self,
            tr("Remove Structure", self.current_lang),
            tr("Delete '{0}'?", self.current_lang).format(part_name),
            confirm_role=BUTTON_ROLE_DESTRUCTIVE,
        ) == QMessageBox.Yes:
            if self.project.remove_taxonomy_part(part_name):
                self.refresh_ui()
                self.project.save_project()

    def on_file_selected(self, curr, prev):
        if not curr:
            return
        if curr.data(Qt.UserRole + 1):
            return

        # Robust Retrieval: Try getting data from UserRole first
        p = curr.data(Qt.UserRole)

        # Fallback for old items (shouldn't happen with new refresh logic)
        if not p:
            fn = curr.text()
            p = next((path for path in self.project.project_data["images"] if os.path.basename(path) == fn), None)
        if not p:
            return

        if p:
            previous_image = self.current_image
            same_image = bool(previous_image) and self._same_project_image_path(previous_image, p)
            if not same_image:
                self._defer_project_save_for_active_navigation()
            has_loaded_pixmap = bool(self.canvas.original_pixmap and not self.canvas.original_pixmap.isNull())

            self.current_image = p
            labels = self.project.get_labels(p)
            manual_boxes = self.project.get_boxes(p)
            auto_boxes, vlm_boxes = self._auto_boxes_for_canvas(p)
            if not (same_image and has_loaded_pixmap):
                self.canvas.load_image(p)
                self.on_enhancement_changed()
            self.canvas.set_polygons(labels)
            self.canvas.set_boxes(manual_boxes, auto_boxes, self._current_shrink_loose_boxes(), vlm=vlm_boxes)
            get_taxon = getattr(self.project, "get_taxon", self.project.get_genus)
            self.genus_combo.blockSignals(True)
            try:
                self.genus_combo.setCurrentText(get_taxon(p))
            finally:
                self.genus_combo.blockSignals(False)
            self._refresh_blink_refine_state()

    def on_part_selected(self, curr, prev):
        p = self._part_item_name(curr)
        if not p:
            self.canvas.set_active_part(None)
            self.desc_box.clear()
            return
        self.canvas.set_active_part(p)
        self.update_db_description(p)
        if self.check_morpho.isChecked():
            self.update_measurements(p)
        self._refresh_blink_refine_state()
