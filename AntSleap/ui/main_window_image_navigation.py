try:
    from AntSleap.ui.main_window_navigation_dependencies import *
    from AntSleap.core.path_identity import path_identity
except ImportError:
    from ui.main_window_navigation_dependencies import *
    from core.path_identity import path_identity


class MainWindowImageNavigationMixin:
    def add_images(self):
        fs, _ = QFileDialog.getOpenFileNames(self, tr("Select Images", self.current_lang), "", "Images (*.png *.jpg *.jpeg *.tif)")
        if fs:
            self._start_image_import(fs)

    def _start_image_import(self, image_paths, crop_records=None, completion_message=None, show_success_message=False):
        paths = [path for path in list(image_paths or []) if path]
        if not paths:
            return False
        if getattr(self, "image_import_thread", None) is not None and self.image_import_thread.isRunning():
            QMessageBox.information(
                self,
                tr("Image Import", self.current_lang),
                tr("Image import is already running.", self.current_lang),
            )
            return False

        crop_records = list(crop_records or [])
        self._flush_pending_project_save(defer_for_navigation=False)
        if len(paths) < BACKGROUND_IMAGE_IMPORT_THRESHOLD:
            added = self.project.add_images(paths)
            self._inherit_crop_provenance(crop_records)
            self.refresh_file_list()
            message = completion_message or tr("Imported {0}/{1} image(s).", self.current_lang).format(added, len(paths))
            self.log(message)
            if show_success_message:
                QMessageBox.information(self, tr("Success", self.current_lang), message)
            return True

        progress = QProgressDialog(
            tr("Preparing image import...", self.current_lang),
            "",
            0,
            len(paths),
            self,
        )
        progress.setWindowTitle(tr("Image Import Progress", self.current_lang))
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setCancelButton(None)
        self._prepare_progress_dialog(progress, width=520)
        progress.show()
        self.image_import_progress_dialog = progress
        self._set_image_import_controls_enabled(False)

        self.image_import_thread = ImageImportThread(self.project, paths)
        thread = self.image_import_thread
        task_context = self._capture_project_task_context()
        self.image_import_project_context = task_context

        def on_progress(done, total, label):
            total = max(0, int(total))
            done = max(0, int(done))
            if total > 0 and progress.maximum() != total:
                progress.setRange(0, total)
            if total > 0:
                progress.setValue(min(done, total))
            if label:
                message = tr("Importing images: {0}/{1}\n{2}", self.current_lang).format(
                    min(done, total),
                    total,
                    self._short_progress_path(label, limit=72),
                )
            else:
                message = tr("Importing images: {0}/{1}", self.current_lang).format(min(done, total), total)
            progress.setLabelText(message)

        def on_success(added, total):
            if not self._project_task_context_matches(task_context):
                self._log_stale_project_task_result("image_import_success", task_context)
                return
            progress.setValue(progress.maximum())
            self._inherit_crop_provenance(crop_records)
            self.refresh_file_list()
            message = completion_message or tr("Imported {0}/{1} image(s).", self.current_lang).format(added, total)
            self.log(message)
            if show_success_message:
                QMessageBox.information(self, tr("Success", self.current_lang), message)

        def on_error(message):
            if not self._project_task_context_matches(task_context):
                self._log_stale_project_task_result("image_import_error", task_context)
                return
            self.log(tr("Image import failed: {0}", self.current_lang).format(message))
            QMessageBox.critical(
                self,
                tr("Image Import", self.current_lang),
                tr("Image import failed: {0}", self.current_lang).format(message),
            )

        def on_finished():
            progress.close()
            if self.image_import_progress_dialog is progress:
                self.image_import_progress_dialog = None
            thread.deleteLater()
            if self.image_import_thread is thread:
                self.image_import_thread = None
                self._set_image_import_controls_enabled(True)

        thread.progress_signal.connect(on_progress)
        thread.success_signal.connect(on_success)
        thread.error_signal.connect(on_error)
        thread.finished_signal.connect(on_finished)
        thread.start()
        return True

    def _set_image_import_controls_enabled(self, enabled):
        for attr in ("btn_add", "btn_crop", "btn_batch_split_panels"):
            widget = getattr(self, attr, None)
            if widget is not None:
                widget.setEnabled(bool(enabled))

    def open_cropper(self):
        img = None
        if self.file_list.currentItem():
            selected_path = self.file_list.currentItem().data(Qt.UserRole)
            if selected_path:
                img = selected_path
            else:
                fn = self.file_list.currentItem().text().strip()
                for p in self.project.project_data["images"]:
                    if os.path.basename(p) == fn:
                        img = p
                        break
        dlg = ImageCropper(initial_image=img, parent=self, lang=self.current_lang)
        if dlg.exec():
            nf = dlg.get_files()
            if nf:
                crop_records = []
                if hasattr(dlg, "get_crop_records"):
                    crop_records = dlg.get_crop_records()
                self._start_image_import(nf, crop_records=crop_records)

    def _is_split_crop_image(self, image_path):
        if not image_path or not hasattr(self.project, "get_image_provenance"):
            return False
        provenance = self.project.get_image_provenance(image_path)
        derived_from = provenance.get("derived_from") if isinstance(provenance, dict) else {}
        if isinstance(derived_from, dict) and bool(derived_from.get("image_path")):
            return True
        return self._looks_like_panel_crop_path(image_path)

    def _is_hard_joined_candidate_crop(self, image_path, provenance=None):
        if not image_path or not hasattr(self.project, "get_image_provenance"):
            return False
        if provenance is None:
            provenance = self.project.get_image_provenance(image_path)
        if not isinstance(provenance, dict):
            return False
        derived_from = provenance.get("derived_from")
        if not isinstance(derived_from, dict):
            return False
        return str(derived_from.get("crop_source") or "").strip() in {
            "hard_seam_panel_split",
            "letter_label_panel_split",
            "label_guided_panel_split",
        }

    def _looks_like_panel_crop_path(self, image_path):
        """Fallback for crops created before provenance was available."""
        if not image_path:
            return False
        base_name = os.path.basename(str(image_path))
        if not re.search(r"__(?:panel|crop)_\d{3}(?:_\d+)?\.(?:png|jpe?g|tif|tiff)$", base_name, re.IGNORECASE):
            return False
        crop_dir = path_identity(os.path.dirname(str(image_path)))
        crop_abs = path_identity(image_path)
        crop_stem = os.path.splitext(base_name)[0]
        source_stem = re.sub(r"__(?:panel|crop)_\d{3}(?:_\d+)?$", "", crop_stem, flags=re.IGNORECASE)
        return any(
            path_identity(path) != crop_abs
            and path_identity(os.path.dirname(path)) == crop_dir
            and os.path.normcase(os.path.splitext(os.path.basename(path))[0]) == os.path.normcase(source_stem)
            for path in self.project.project_data.get("images", [])
        )

    def _has_split_crops_from_image(self, image_path):
        if not image_path or not hasattr(self.project, "get_image_provenance"):
            return False
        source_abs = path_identity(image_path)
        source_dir = path_identity(os.path.dirname(str(image_path)))
        source_stem = os.path.normcase(os.path.splitext(os.path.basename(str(image_path)))[0])
        for path in self.project.project_data.get("images", []):
            if not path:
                continue
            crop_abs = path_identity(path)
            if crop_abs == source_abs:
                continue
            provenance = self.project.get_image_provenance(path)
            derived_from = provenance.get("derived_from") if isinstance(provenance, dict) else {}
            if isinstance(derived_from, dict) and derived_from.get("image_path"):
                derived_abs = path_identity(derived_from.get("image_path"))
                if derived_abs == source_abs:
                    return True
            if not self._looks_like_panel_crop_path(path):
                continue
            crop_dir = path_identity(os.path.dirname(str(path)))
            crop_stem = os.path.splitext(os.path.basename(str(path)))[0]
            parent_stem = re.sub(r"__(?:panel|crop)_\d{3}(?:_\d+)?$", "", crop_stem, flags=re.IGNORECASE)
            if crop_dir == source_dir and os.path.normcase(parent_stem) == source_stem:
                return True
        return False

    def _needs_manual_panel_split(self, image_path):
        if not image_path or not hasattr(self.project, "get_image_provenance"):
            return False
        if self._is_split_crop_image(image_path):
            return False
        if self._has_split_crops_from_image(image_path):
            return False
        provenance = self.project.get_image_provenance(image_path)
        review = provenance.get("panel_split_review") if isinstance(provenance, dict) else {}
        return isinstance(review, dict) and review.get("status") == "manual_required"

    def _is_manual_panel_split_done(self, image_path):
        if not image_path or not hasattr(self.project, "get_image_provenance"):
            return False
        if self._is_split_crop_image(image_path):
            return False
        provenance = self.project.get_image_provenance(image_path)
        review = provenance.get("panel_split_review") if isinstance(provenance, dict) else {}
        return isinstance(review, dict) and review.get("status") == "manual_done"

    def _set_panel_split_review(self, image_path, status, reason="", detections=None):
        if not image_path or not hasattr(self.project, "get_image_provenance"):
            return
        provenance = self.project.get_image_provenance(image_path)
        provenance["panel_split_review"] = {
            "status": str(status or ""),
            "reason": str(reason or ""),
            "candidate_count": len(detections or []),
        }
        self.project.set_image_provenance(image_path, provenance, save=False)

    def _clear_panel_split_review(self, image_path):
        if not image_path or not hasattr(self.project, "get_image_provenance"):
            return
        provenance = self.project.get_image_provenance(image_path)
        if "panel_split_review" in provenance:
            del provenance["panel_split_review"]
            self.project.set_image_provenance(image_path, provenance, save=False)

    def _builtin_image_group_definitions(self):
        return [
            ("original", tr("Original Images", self.current_lang)),
            ("split", tr("Split Crops", self.current_lang)),
            ("hard_candidates", tr("Hard-joined Candidates", self.current_lang)),
            ("manual_done", tr("Manual Split Done", self.current_lang)),
            ("manual", tr("Manual Split Needed", self.current_lang)),
        ]

    def _custom_image_group_definitions(self):
        groups = self.project.project_data.get("image_groups", {}) if hasattr(self, "project") else {}
        raw_groups = groups.get("custom_groups", []) if isinstance(groups, dict) else []
        clean = []
        seen = set()
        if isinstance(raw_groups, list):
            for group in raw_groups:
                if not isinstance(group, dict):
                    continue
                group_id = str(group.get("id", "") or "").strip()
                name = str(group.get("name", "") or "").strip()
                if not group_id or not name or group_id in seen:
                    continue
                seen.add(group_id)
                clean.append((group_id, name))
        return clean

    def _all_image_group_definitions(self):
        return self._builtin_image_group_definitions() + self._custom_image_group_definitions()

    def _training_scope_group_definitions(self, all_images=None):
        images = [path for path in (all_images if all_images is not None else self.project.project_data.get("images", [])) if path]
        state = getattr(self, "_image_list_state_cache", None)
        if isinstance(state, dict):
            try:
                state_total = int(state.get("total_count", -1))
            except Exception:
                state_total = -1
            group_definitions = list(state.get("group_definitions", []) or [])
            if state_total == len(images) and group_definitions:
                return group_definitions

        image_groups = self._project_image_groups(images=images)
        group_definitions = []
        for group_key, label in self._builtin_image_group_definitions():
            group_definitions.append((group_key, label, image_groups.get(group_key, []), group_key == "split"))
        for group_key, label in self._custom_image_group_definitions():
            group_definitions.append((group_key, label, image_groups.get(group_key, []), False))
        return group_definitions

    def _populate_training_scope_combo(self, selected_scope=None):
        if not hasattr(self, "combo_training_scope"):
            return
        current = str(selected_scope or self.combo_training_scope.currentData() or "__all__")
        all_images = [path for path in self.project.project_data.get("images", []) if path]
        group_definitions = self._training_scope_group_definitions(all_images)
        self.combo_training_scope.blockSignals(True)
        self.combo_training_scope.clear()
        self.combo_training_scope.addItem(
            tr("All Images ({0})", self.current_lang).format(len(all_images)),
            "__all__",
        )
        for group_id, label, group_images, _is_split_group in group_definitions:
            group_images = list(group_images or [])
            if group_images:
                self.combo_training_scope.addItem(
                    tr("{0} ({1})", self.current_lang).format(label, len(group_images)),
                    group_id,
                )
        index = self.combo_training_scope.findData(current)
        if index < 0:
            index = self.combo_training_scope.findData("__all__")
        self.combo_training_scope.setCurrentIndex(index if index >= 0 else 0)
        self.combo_training_scope.blockSignals(False)

    def _refresh_training_scope_combo(self):
        selected = "__all__"
        if hasattr(self, "combo_training_scope"):
            selected = str(self.combo_training_scope.currentData() or selected)
        self._populate_training_scope_combo(selected)

    def _selected_training_scope_payload(self):
        all_images = [path for path in self.project.project_data.get("images", []) if path]
        scope_id = "__all__"
        if hasattr(self, "combo_training_scope"):
            scope_id = str(self.combo_training_scope.currentData() or "__all__")
        if scope_id == "__all__":
            label = tr("All Images", self.current_lang)
            return {"scope_id": "__all__", "label": label, "images": all_images}

        group_images = []
        for group_id, _label, images, _is_split_group in self._training_scope_group_definitions(all_images):
            if str(group_id) == scope_id:
                group_images = list(images or [])
                break
        label = self._image_group_display_name(scope_id) or scope_id
        return {"scope_id": scope_id, "label": label, "images": group_images}

    def _populate_vlm_image_group_combo(self, selected_group=None):
        if not hasattr(self, "combo_vlm_image_group"):
            return
        current = str(selected_group or self.combo_vlm_image_group.currentData() or "split")
        self.combo_vlm_image_group.blockSignals(True)
        self.combo_vlm_image_group.clear()
        for group_id, label in self._all_image_group_definitions():
            self.combo_vlm_image_group.addItem(label, group_id)
        index = self.combo_vlm_image_group.findData(current)
        if index < 0:
            index = self.combo_vlm_image_group.findData("split")
        self.combo_vlm_image_group.setCurrentIndex(index if index >= 0 else 0)
        self.combo_vlm_image_group.blockSignals(False)

    def _refresh_vlm_image_group_combo(self):
        selected = "split"
        if hasattr(self, "combo_vlm_image_group"):
            selected = str(self.combo_vlm_image_group.currentData() or selected)
        self._populate_vlm_image_group_combo(selected)

    def _image_group_display_name(self, group_key):
        key = str(group_key or "").strip()
        for group_id, label in self._all_image_group_definitions():
            if group_id == key:
                return label
        return key

    def _custom_image_group_ids(self):
        return {group_id for group_id, _label in self._custom_image_group_definitions()}

    def _image_group_move_target_definitions(self):
        definitions = list(self._builtin_image_group_definitions())
        custom_groups = self._custom_image_group_definitions()
        if custom_groups:
            image_groups = self._project_image_groups()
            for group_id, label in custom_groups:
                if image_groups.get(group_id):
                    definitions.append((group_id, label))
        return definitions

    def _remove_empty_custom_image_groups(self):
        if not hasattr(self, "project"):
            return set()
        groups_config = self.project.project_data.get("image_groups", {})
        if not isinstance(groups_config, dict):
            return set()
        custom_groups = list(groups_config.get("custom_groups", []) or [])
        if not custom_groups:
            return set()

        image_groups = self._project_image_groups()
        kept_groups = []
        removed_ids = set()
        seen = set()
        for group in custom_groups:
            if not isinstance(group, dict):
                continue
            group_id = str(group.get("id", "") or "").strip()
            name = str(group.get("name", "") or "").strip()
            if not group_id or not name or group_id in seen:
                continue
            seen.add(group_id)
            if image_groups.get(group_id):
                kept_groups.append(group)
            else:
                removed_ids.add(group_id)

        if not removed_ids:
            return set()

        groups_config["custom_groups"] = kept_groups
        self.project.project_data["image_groups"] = groups_config
        if hasattr(self.project, "mark_sqlite_project_dirty"):
            self.project.mark_sqlite_project_dirty()

        settings = self.project.project_data.get("vlm_preannotation")
        if isinstance(settings, dict) and str(settings.get("image_group", "") or "").strip() in removed_ids:
            settings["image_group"] = DEFAULT_VLM_IMAGE_GROUP

        collapsed = getattr(self, "image_list_group_collapsed", None)
        if isinstance(collapsed, dict):
            for group_id in removed_ids:
                collapsed.pop(group_id, None)

        return removed_ids

    def _safe_custom_image_group_id(self, name):
        text = str(name or "").strip()
        clean = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in text).strip("_")
        clean = clean or "custom_group"
        if clean in {"original", "split", "hard_candidates", "manual_done", "manual"}:
            clean = f"custom_{clean}"
        existing = {group_id for group_id, _label in self._all_image_group_definitions()}
        group_id = clean
        suffix = 2
        while group_id in existing:
            group_id = f"{clean}_{suffix}"
            suffix += 1
        return group_id

    def create_custom_image_group(self):
        removed_empty = self._remove_empty_custom_image_groups()
        if removed_empty:
            self._schedule_project_save()
            self.refresh_file_list()
            self._refresh_vlm_image_group_combo()
        name, ok = QInputDialog.getText(
            self,
            tr("New Image Group", self.current_lang),
            tr("Group Name:", self.current_lang),
        )
        name = str(name or "").strip()
        if not ok or not name:
            return ""
        existing_names = {
            str(label).strip().lower()
            for _group_id, label in self._all_image_group_definitions()
            if str(label).strip()
        }
        if name.lower() in existing_names:
            QMessageBox.information(self, tr("New Image Group", self.current_lang), tr("Image group already exists.", self.current_lang))
            return ""
        groups = dict(self.project.project_data.get("image_groups", {}) or {})
        custom_groups = list(groups.get("custom_groups", []) or [])
        group_id = self._safe_custom_image_group_id(name)
        custom_groups.append({"id": group_id, "name": name[:80]})
        groups["custom_groups"] = custom_groups
        self.project.project_data["image_groups"] = groups
        if hasattr(self.project, "mark_sqlite_project_dirty"):
            self.project.mark_sqlite_project_dirty()
        self._schedule_project_save()
        self.refresh_file_list()
        self._refresh_vlm_image_group_combo()
        return group_id

    def _set_image_manual_group(self, image_path, group_key):
        if not image_path or not hasattr(self.project, "get_image_provenance"):
            return
        key = str(group_key or "").strip()
        provenance = self.project.get_image_provenance(image_path)
        if key:
            provenance["manual_image_group"] = key
        else:
            provenance.pop("manual_image_group", None)
        self.project.set_image_provenance(image_path, provenance, save=False)

    def move_images_to_group(self, image_paths, group_key):
        paths = [path for path in (image_paths or []) if path]
        key = str(group_key or "").strip()
        if not paths or not key:
            return
        allowed = {group_id for group_id, _label in self._all_image_group_definitions()}
        if key not in allowed:
            return
        for path in paths:
            self._set_image_manual_group(path, key)
        self._remove_empty_custom_image_groups()
        self._schedule_project_save()
        self.refresh_file_list()
        self._refresh_vlm_image_group_combo()
        self.log(tr("Moved {0} image(s) to {1}.", self.current_lang).format(len(paths), self._image_group_display_name(key)))

    def clear_selected_custom_image_group(self):
        paths = self._selected_image_paths()
        if not paths:
            return
        for path in paths:
            self._set_image_manual_group(path, "")
        self._remove_empty_custom_image_groups()
        self._schedule_project_save()
        self.refresh_file_list()
        self._refresh_vlm_image_group_combo()

    def _short_progress_path(self, path, limit=64):
        name = os.path.basename(str(path or ""))
        if len(name) <= limit:
            return name
        root, ext = os.path.splitext(name)
        ext = ext[:10]
        keep = max(12, limit - len(ext) - 3)
        head = max(6, keep // 2)
        tail = max(6, keep - head)
        return f"{root[:head]}...{root[-tail:]}{ext}"

    def _prepare_progress_dialog(self, progress, width=460):
        if progress is None:
            return
        progress.setMinimumWidth(int(width))
        progress.setMaximumWidth(int(width))
        progress.adjustSize()
        try:
            center = self.frameGeometry().center()
            rect = progress.frameGeometry()
            rect.moveCenter(center)
            progress.move(rect.topLeft())
        except Exception:
            pass

    def _candidate_panel_split_sources(self):
        return [
            path
            for path in self.project.project_data.get("images", [])
            if path and not self._is_split_crop_image(path)
        ]

    def batch_split_panel_images(self):
        source_images = self._candidate_panel_split_sources()
        if not source_images:
            QMessageBox.information(self, tr("Empty", self.current_lang), tr("No panel crops were detected.", self.current_lang))
            return
        reply = themed_yes_no_question(
            self,
            tr("Batch Split Plates", self.current_lang),
            tr(
                "Run automatic panel splitting on {0} original image(s)?\n\nDetected crops will be added after the original images. Please review the generated crops before training.",
                self.current_lang,
            ).format(len(source_images)),
            confirm_role=BUTTON_ROLE_COMMIT,
        )
        if reply != QMessageBox.Yes:
            return

        crop_records = []
        skipped = 0
        manual_required = 0
        cancelled = False
        progress = QProgressDialog(
            tr("Batch Split Plates", self.current_lang),
            tr("Cancel", self.current_lang),
            0,
            len(source_images),
            self,
        )
        progress.setWindowTitle(tr("Batch Split Plates", self.current_lang))
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setValue(0)
        self._prepare_progress_dialog(progress)
        app = QApplication.instance()
        if app is not None:
            app.processEvents()

        for index, source_image in enumerate(source_images, start=1):
            progress.setLabelText(
                f"{tr('Batch Split Plates', self.current_lang)}: {index}/{len(source_images)}\n{self._short_progress_path(source_image)}"
            )
            progress.setValue(index - 1)
            if app is not None:
                app.processEvents()
            if progress.wasCanceled():
                cancelled = True
                break
            try:
                detections = detect_panel_crops(source_image)
            except Exception as exc:
                skipped += 1
                self._set_panel_split_review(source_image, "skipped", reason=f"error: {exc}")
                self.log(f"Panel split skipped {os.path.basename(source_image)}: {exc}")
                continue
            hard_joined_detections = [
                detection
                for detection in detections
                if str(detection.get("source") or "") in {"hard_seam_panel_split", "letter_label_panel_split", "label_guided_panel_split"}
            ]
            if hard_joined_detections and not any(
                str(detection.get("source") or "") in {"white_separator_panel_split", "mixed_separator_panel_split"}
                for detection in detections
            ):
                manual_required += 1
                self._set_panel_split_review(
                    source_image,
                    "candidate_split",
                    reason="hard_seam_panel_split_candidate",
                    detections=hard_joined_detections,
                )
                crop_records.extend(self._save_detected_panel_crops(source_image, hard_joined_detections))
                progress.setValue(index)
                if app is not None:
                    app.processEvents()
                continue
            detections = [
                detection
                for detection in detections
                if str(detection.get("source") or "") in {"white_separator_panel_split", "mixed_separator_panel_split"}
            ]
            if not detections:
                skipped += 1
                self._set_panel_split_review(source_image, "skipped", reason="no_split_detected")
                continue
            crop_records.extend(self._save_detected_panel_crops(source_image, detections))
            self._set_panel_split_review(source_image, "auto_split", reason="white_separator_panel_split", detections=detections)
            progress.setValue(index)
            if app is not None:
                app.processEvents()

        progress.setValue(len(source_images))

        if not crop_records:
            if hasattr(self.project, "save_project"):
                self.project.save_project()
            if cancelled:
                self.refresh_file_list()
                message = tr("Panel splitting cancelled.", self.current_lang)
                QMessageBox.information(self, tr("Batch Split Plates", self.current_lang), message)
                return
            if manual_required:
                self.refresh_file_list()
                message = tr(
                    "Panel splitting finished: {0} crop(s) from {1} image(s); hard-joined candidate plates needing review: {2}; no split detected/errors: {3}.",
                    self.current_lang,
                ).format(0, 0, manual_required, skipped)
                QMessageBox.information(self, tr("Batch Split Plates", self.current_lang), message)
                return
            QMessageBox.information(self, tr("Empty", self.current_lang), tr("No panel crops were detected.", self.current_lang))
            return

        message = tr(
            "Panel splitting finished: {0} crop(s) from {1} image(s); hard-joined candidate plates needing review: {2}; no split detected/errors: {3}.",
            self.current_lang,
        ).format(
            len(crop_records),
            len({record.get("source_image") for record in crop_records}),
            manual_required,
            skipped,
        )
        if cancelled:
            message = f"{message}\n{tr('Panel splitting cancelled.', self.current_lang)}"
        progress.close()
        self._start_image_import(
            [record["path"] for record in crop_records],
            crop_records=crop_records,
            completion_message=message,
            show_success_message=True,
        )

    def _save_detected_panel_crops(self, source_image, detections):
        records = []
        save_dir = os.path.dirname(source_image)
        base_name = os.path.splitext(os.path.basename(source_image))[0]
        with PILImage.open(source_image) as img:
            for index, detection in enumerate(detections, start=1):
                box = [int(value) for value in detection.get("box", [])]
                if len(box) != 4 or box[2] <= box[0] or box[3] <= box[1]:
                    continue
                new_path = self._next_panel_crop_path(save_dir, base_name, index)
                img.crop(tuple(box)).save(new_path, quality=95)
                records.append(
                    {
                        "path": os.path.abspath(new_path),
                        "source_image": os.path.abspath(source_image),
                        "crop_index": index,
                        "crop_box": list(box),
                        "source_size": [int(img.width), int(img.height)],
                        "crop_source": str(detection.get("source") or "auto_panel_split"),
                    }
                )
        return records

    def _next_panel_crop_path(self, save_dir, base_name, index):
        candidate = os.path.join(save_dir, f"{base_name}__panel_{index:03d}.jpg")
        if not os.path.exists(candidate):
            return candidate
        suffix = 2
        while True:
            candidate = os.path.join(save_dir, f"{base_name}__panel_{index:03d}_{suffix}.jpg")
            if not os.path.exists(candidate):
                return candidate
            suffix += 1

    def _inherit_crop_provenance(self, crop_records):
        if not crop_records or not hasattr(self.project, "get_image_provenance"):
            return
        changed = False
        for record in crop_records:
            if not isinstance(record, dict):
                continue
            crop_path = record.get("path")
            source_image = record.get("source_image")
            if not crop_path or not source_image:
                continue
            parent_provenance = self.project.get_image_provenance(source_image)
            crop_provenance = dict(parent_provenance)
            parent_review = parent_provenance.get("panel_split_review") if isinstance(parent_provenance, dict) else {}
            parent_was_manual_required = isinstance(parent_review, dict) and parent_review.get("status") == "manual_required"
            crop_provenance.pop("panel_split_review", None)
            parent_source_type = str(parent_provenance.get("source_type", "") or "image").strip() or "image"
            crop_source = str(record.get("crop_source") or "manual")
            crop_provenance["source_type"] = "pdf_candidate_crop" if self._is_pdf_candidate_provenance(parent_provenance) else f"{parent_source_type}_crop"
            crop_provenance["derived_from"] = {
                "image_path": os.path.abspath(source_image),
                "crop_index": int(record.get("crop_index", 0) or 0),
                "crop_box": list(record.get("crop_box", []) or []),
                "source_size": list(record.get("source_size", []) or []),
                "crop_source": crop_source,
            }
            self.project.set_image_provenance(crop_path, crop_provenance, save=False)
            if crop_source == "manual" or parent_was_manual_required:
                self._set_panel_split_review(source_image, "manual_done", reason="manual_crop_saved")
            changed = True
        if changed:
            self.project.save_project()

    def _selected_image_paths(self):
        if not hasattr(self, "file_list"):
            return []
        paths = []
        for item in self.file_list.selectedItems():
            path = item.data(Qt.UserRole)
            if path:
                paths.append(path)
        return paths

    def _set_selected_panel_split_status(self, status, reason):
        paths = self._selected_image_paths()
        if not paths:
            return
        for path in paths:
            self._set_panel_split_review(path, status, reason=reason)
        self._schedule_project_save()
        self.refresh_file_list()

    def mark_selected_manual_split_done(self):
        self._set_selected_panel_split_status("manual_done", "user_marked_done")

    def mark_selected_manual_split_needed(self):
        self._set_selected_panel_split_status("manual_required", "user_marked_manual_required")

    def clear_selected_split_status(self):
        paths = self._selected_image_paths()
        if not paths:
            return
        for path in paths:
            self._clear_panel_split_review(path)
        self._schedule_project_save()
        self.refresh_file_list()

    def show_file_list_context_menu(self, pos):
        its = self.file_list.selectedItems()
        if not its:
            return
        its = [item for item in its if item.data(Qt.UserRole)]
        if not its:
            return
        m = QMenu(self)
        if len(its) == 1:
            m.addAction(tr("Crop this Image", self.current_lang), self.open_cropper)
        m.addSeparator()
        m.addAction(tr("Mark Manual Split Done", self.current_lang), self.mark_selected_manual_split_done)
        m.addAction(tr("Mark Needs Manual Split", self.current_lang), self.mark_selected_manual_split_needed)
        m.addAction(tr("Clear Split Status", self.current_lang), self.clear_selected_split_status)
        m.addSeparator()
        m.addAction(tr("New Image Group", self.current_lang), self._move_selected_images_to_new_group)
        move_menu = m.addMenu(tr("Move to Image Group", self.current_lang))
        for group_id, label in self._image_group_move_target_definitions():
            move_menu.addAction(label, lambda checked=False, gid=group_id: self.move_images_to_group(self._selected_image_paths(), gid))
        m.addAction(tr("Clear Custom Image Group", self.current_lang), self.clear_selected_custom_image_group)
        m.addSeparator()
        m.addAction(tr("Remove Image", self.current_lang), self.remove_selected_images)
        m.exec(self.file_list.mapToGlobal(pos))

    def _move_selected_images_to_new_group(self):
        paths = self._selected_image_paths()
        if not paths:
            return
        group_id = self.create_custom_image_group()
        if group_id:
            self.move_images_to_group(paths, group_id)

    def remove_selected_images(self):
        paths = self._selected_image_paths()
        if not paths:
            return
        if themed_yes_no_question(
            self,
            tr("Remove", self.current_lang),
            tr("Remove {0} images?", self.current_lang).format(len(paths)),
            confirm_role=BUTTON_ROLE_DESTRUCTIVE,
        ) == QMessageBox.Yes:
            was_current_removed = bool(
                self.current_image
                and any(self._same_project_image_path(path, self.current_image) for path in paths)
            )
            previous_current_image = self.current_image
            previous_visible_paths = self._visible_image_list_paths()
            replacement_image = None
            if was_current_removed:
                replacement_image = self._replacement_image_after_removal(
                    previous_visible_paths,
                    paths,
                    previous_current_image,
                )
            remove_many = getattr(self.project, "remove_images", None)
            if callable(remove_many):
                remove_many(paths, save=False)
            else:
                for path in paths:
                    self.project.remove_image(path, save=False)
            runtime_log_event(
                "remove_images",
                count=len(paths),
                removed_current=was_current_removed,
                previous_current=os.path.basename(str(previous_current_image or "")),
                replacement=os.path.basename(str(replacement_image or "")),
                project=getattr(self.project, "current_project_path", ""),
                remaining_images=len(self.project.project_data.get("images", []) or []),
            )
            self._schedule_project_save(
                reason="remove_images",
                changed_count=len(paths),
                removed_current=was_current_removed,
            )
            current_still_registered = bool(
                self.current_image
                and any(
                    self._same_project_image_path(path, self.current_image)
                    for path in self.project.project_data.get("images", [])
                )
            )
            if not current_still_registered:
                self.current_image = None
                self.canvas.load_image("")
            if not self._remove_visible_image_list_items(paths):
                self._image_list_state_cache = None
                self.refresh_file_list(restore_selection=bool(self.current_image))
                if was_current_removed and replacement_image:
                    self._select_first_visible_image_after_removal(replacement_image)
            elif was_current_removed:
                self._select_first_visible_image_after_removal(replacement_image)

    def refresh_file_list(self, restore_selection=True, reuse_group_cache=False):
        # 1. Remember the currently selected image path
        current_selection_path = self.current_image

        self.file_list.blockSignals(True) # Prevent signal spam during rebuild
        self.file_list.setUpdatesEnabled(False)
        try:
            self.file_list.clear()
            state = self._image_list_state_cache if reuse_group_cache else None
            if not isinstance(state, dict):
                state = self._build_image_list_state()
                self._image_list_state_cache = state

            total_count = int(state.get("total_count", 0) or 0)
            labeled_count = int(state.get("labeled_count", 0) or 0)
            group_definitions = list(state.get("group_definitions", []) or [])
            labeled_images = set(state.get("labeled_images", set()) or set())
            split_images = set(state.get("split_images", set()) or set())
            non_empty_groups = [group for group in group_definitions if group[2]]
            has_collapsed_group = any(
                bool(self.image_list_group_collapsed.get(group[0], False))
                for group in non_empty_groups
            )
            use_group_headers = (
                total_count >= LARGE_PROJECT_OPEN_LIGHTWEIGHT_THRESHOLD
                or has_collapsed_group
                or not (len(non_empty_groups) == 1 and non_empty_groups[0][0] == "original")
            )

            item_to_select = None
            first_image_item = None
            theme_colors = get_theme_config(self.current_theme)

            def add_group_header(group_key, text, count):
                collapsed = bool(self.image_list_group_collapsed.get(group_key, False))
                arrow = "▸" if collapsed else "▾"
                item = QListWidgetItem(f"{arrow} {text} ({count})")
                item.setData(Qt.UserRole, None)
                item.setData(Qt.UserRole + 1, group_key)
                item.setFlags((item.flags() | Qt.ItemIsEnabled | Qt.ItemIsSelectable) & ~Qt.ItemIsEditable)
                item.setForeground(QColor(theme_colors["text_dim"]))
                self.file_list.addItem(item)
                return collapsed

            def add_image_item(img, is_split_crop=False, group_key=""):
                nonlocal item_to_select, first_image_item
                base_name = os.path.basename(img)
                display_name = f"  {base_name}" if is_split_crop else base_name
                item = QListWidgetItem(display_name)
                item.setData(Qt.UserRole, img) # Store full path for safer lookup
                item.setData(Qt.UserRole + 2, group_key)
                if is_split_crop:
                    item.setToolTip(tr("Split Crops", self.current_lang))

                if img in labeled_images:
                    item.setForeground(QColor(theme_colors["success"]))
                elif is_split_crop:
                    item.setForeground(QColor(theme_colors["text_dim"]))
                else:
                    item.setForeground(QColor(theme_colors["text_soft"]))

                self.file_list.addItem(item)
                if first_image_item is None:
                    first_image_item = item

                # Check if this is the one we were looking at
                if current_selection_path and self._same_project_image_path(img, current_selection_path):
                    item_to_select = item

            for group_key, label, images, is_split_group in group_definitions:
                if not images:
                    continue
                if use_group_headers:
                    collapsed = add_group_header(group_key, label, len(images))
                    if collapsed:
                        continue
                for img in images:
                    add_image_item(img, is_split_crop=(is_split_group or img in split_images), group_key=group_key)

            # 2. Restore Selection
            if restore_selection:
                target_item = item_to_select or first_image_item
                if target_item:
                    self.file_list.setCurrentItem(target_item)
                    self.file_list.scrollToItem(target_item) # Ensure visible
                    if target_item.data(Qt.UserRole):
                        self.on_file_selected(target_item, None)

            # Update the header label on the left side
            header_base = tr("PROJECT IMAGES", self.current_lang)
            self.label_project_images.setText(f"{header_base} ({labeled_count}/{total_count})")
            self._refresh_training_scope_combo()
        finally:
            self.file_list.setUpdatesEnabled(True)
            self.file_list.blockSignals(False)

    def _image_has_review_content(self, image_path):
        if not image_path:
            return False
        return bool(self.project.get_labels(image_path) or self.project.get_auto_boxes(image_path))

    def _set_image_list_item_status(self, item, image_path, labeled_images=None, split_images=None):
        if item is None or not image_path:
            return
        group_key = str(item.data(Qt.UserRole + 2) or "")
        if labeled_images is None:
            is_labeled = self._image_has_review_content(image_path)
        else:
            is_labeled = image_path in set(labeled_images or [])
        if split_images is None:
            is_split_crop = group_key == "split" or self._is_split_crop_image(image_path)
        else:
            is_split_crop = group_key == "split" or image_path in set(split_images or [])
        theme_colors = get_theme_config(self.current_theme)
        if is_labeled:
            item.setForeground(QColor(theme_colors["success"]))
        elif is_split_crop:
            item.setForeground(QColor(theme_colors["text_dim"]))
        else:
            item.setForeground(QColor(theme_colors["text_soft"]))

    def _refresh_current_image_list_status(self, image_path=None):
        image_path = image_path or self.current_image
        if not image_path or not hasattr(self, "file_list"):
            return False

        state = self._image_list_state_cache
        if not isinstance(state, dict):
            state = self._build_image_list_state()
            self._image_list_state_cache = state

        labeled_images = set(state.get("labeled_images", set()) or set())
        before_labeled = image_path in labeled_images
        after_labeled = self._image_has_review_content(image_path)
        if after_labeled:
            labeled_images.add(image_path)
        else:
            labeled_images.discard(image_path)

        state["labeled_images"] = labeled_images
        if before_labeled != after_labeled:
            state["labeled_count"] = max(0, int(state.get("labeled_count", 0) or 0) + (1 if after_labeled else -1))

        target_item = None
        for index in range(self.file_list.count()):
            item = self.file_list.item(index)
            if item is not None and self._same_project_image_path(item.data(Qt.UserRole), image_path):
                target_item = item
                break
        if target_item is not None:
            self._set_image_list_item_status(
                target_item,
                image_path,
                labeled_images=labeled_images,
                split_images=set(state.get("split_images", set()) or set()),
            )

        header_base = tr("PROJECT IMAGES", self.current_lang)
        self.label_project_images.setText(
            f"{header_base} ({int(state.get('labeled_count', 0) or 0)}/{int(state.get('total_count', 0) or 0)})"
        )
        return target_item is not None

    def _refresh_image_list_status_or_rebuild(self, image_path=None):
        if self._refresh_current_image_list_status(image_path):
            return True
        self._image_list_state_cache = None
        self.refresh_file_list(restore_selection=bool(self.current_image))
        return False

    def _image_list_path_identity(self, path):
        if not path:
            return ""
        try:
            return path_identity(path)
        except Exception:
            return str(path)

    def _visible_image_list_paths(self):
        if not hasattr(self, "file_list"):
            return []
        paths = []
        for row in range(self.file_list.count()):
            item = self.file_list.item(row)
            path = item.data(Qt.UserRole) if item is not None else None
            if path:
                paths.append(path)
        return paths

    def _replacement_image_after_removal(self, previous_visible_paths, removed_paths, previous_current_image):
        visible_paths = [path for path in list(previous_visible_paths or []) if path]
        if not visible_paths:
            return None

        removed_identities = {
            self._image_list_path_identity(path)
            for path in list(removed_paths or [])
            if path
        }
        removed_identities.discard("")

        current_index = -1
        for index, path in enumerate(visible_paths):
            if self._same_project_image_path(path, previous_current_image):
                current_index = index
                break

        if current_index < 0:
            search_order = visible_paths
        else:
            search_order = visible_paths[current_index + 1:] + list(reversed(visible_paths[:current_index]))

        for path in search_order:
            if self._image_list_path_identity(path) not in removed_identities:
                return path
        return None

    def _remove_visible_image_list_items(self, image_paths):
        if not image_paths or not hasattr(self, "file_list"):
            return False
        state = self._image_list_state_cache
        if not isinstance(state, dict):
            return False

        remove_identities = set()
        for path in image_paths:
            identity = self._image_list_path_identity(path)
            if identity:
                remove_identities.add(identity)
        if not remove_identities:
            return False

        removed_visible_rows = 0
        self.file_list.blockSignals(True)
        self.file_list.setUpdatesEnabled(False)
        try:
            for row in range(self.file_list.count() - 1, -1, -1):
                item = self.file_list.item(row)
                path = item.data(Qt.UserRole) if item is not None else None
                if not path:
                    continue
                identity = self._image_list_path_identity(path)
                if identity in remove_identities:
                    removed_visible_rows += 1
                    self.file_list.takeItem(row)
        finally:
            self.file_list.setUpdatesEnabled(True)
            self.file_list.blockSignals(False)

        labeled_images = set(state.get("labeled_images", set()) or set())
        removed_labeled = 0
        filtered_labeled = set()
        for path in labeled_images:
            identity = self._image_list_path_identity(path)
            if identity in remove_identities:
                removed_labeled += 1
            else:
                filtered_labeled.add(path)
        state["labeled_images"] = filtered_labeled
        state["split_images"] = {
            path
            for path in set(state.get("split_images", set()) or set())
            if self._image_list_path_identity(path) not in remove_identities
        }
        state["total_count"] = max(0, int(state.get("total_count", 0) or 0) - len(remove_identities))
        state["labeled_count"] = max(0, int(state.get("labeled_count", 0) or 0) - removed_labeled)
        state["group_definitions"] = self._filtered_group_definitions_after_removal(
            state.get("group_definitions", []),
            remove_identities,
        )
        self._refresh_visible_image_group_header_counts(state.get("group_definitions", []))

        header_base = tr("PROJECT IMAGES", self.current_lang)
        self.label_project_images.setText(
            f"{header_base} ({int(state.get('labeled_count', 0) or 0)}/{int(state.get('total_count', 0) or 0)})"
        )
        self._refresh_training_scope_combo()
        return removed_visible_rows > 0

    def _filtered_group_definitions_after_removal(self, group_definitions, remove_identities):
        filtered = []
        for group_key, label, images, is_split_group in list(group_definitions or []):
            kept_images = []
            for path in list(images or []):
                identity = self._image_list_path_identity(path)
                if identity not in remove_identities:
                    kept_images.append(path)
            filtered.append((group_key, label, kept_images, is_split_group))
        return filtered

    def _refresh_visible_image_group_header_counts(self, group_definitions):
        counts = {
            str(group_key): len(list(images or []))
            for group_key, _label, images, _is_split_group in list(group_definitions or [])
        }
        for row in range(self.file_list.count()):
            item = self.file_list.item(row)
            group_key = item.data(Qt.UserRole + 1) if item is not None else None
            if not group_key:
                continue
            key = str(group_key)
            collapsed = bool(self.image_list_group_collapsed.get(key, False))
            arrow = "▸" if collapsed else "▾"
            item.setText(f"{arrow} {self._image_group_display_name(key)} ({counts.get(key, 0)})")

    def _select_first_visible_image_after_removal(self, preferred_path=None):
        if not hasattr(self, "file_list"):
            return False
        if preferred_path:
            for row in range(self.file_list.count()):
                item = self.file_list.item(row)
                if item is not None and self._same_project_image_path(item.data(Qt.UserRole), preferred_path):
                    previous = bool(getattr(self, "_suppress_selection_save_flush", False))
                    self._suppress_selection_save_flush = True
                    try:
                        self.file_list.setCurrentItem(item)
                        self.file_list.scrollToItem(item)
                        if not self.current_image or not self._same_project_image_path(self.current_image, item.data(Qt.UserRole)):
                            self.on_file_selected(item, None)
                    finally:
                        self._suppress_selection_save_flush = previous
                    return True
        for row in range(self.file_list.count()):
            item = self.file_list.item(row)
            if item is not None and item.data(Qt.UserRole):
                previous = bool(getattr(self, "_suppress_selection_save_flush", False))
                self._suppress_selection_save_flush = True
                try:
                    self.file_list.setCurrentItem(item)
                    self.file_list.scrollToItem(item)
                    if not self.current_image or not self._same_project_image_path(self.current_image, item.data(Qt.UserRole)):
                        self.on_file_selected(item, None)
                finally:
                    self._suppress_selection_save_flush = previous
                return True
        return False

    def _build_image_list_state(self):
        images = [img for img in self.project.project_data.get("images", []) if img]
        total_count = len(images)
        labeled_images = {
            img
            for img in images
            if bool(self.project.get_labels(img) or self.project.get_auto_boxes(img))
        }
        image_groups = self._project_image_groups(
            images=images,
            labeled_images=labeled_images,
        )

        group_definitions = []
        for group_key, label in self._builtin_image_group_definitions():
            group_definitions.append((group_key, label, image_groups.get(group_key, []), group_key == "split"))
        for group_key, label in self._custom_image_group_definitions():
            group_definitions.append((group_key, label, image_groups.get(group_key, []), False))

        return {
            "total_count": total_count,
            "labeled_count": len(labeled_images),
            "labeled_images": labeled_images,
            "split_images": set(image_groups.get("split", []) or []),
            "group_definitions": group_definitions,
        }

    def _handle_image_list_item_clicked(self, item):
        if item is None:
            return
        group_key = item.data(Qt.UserRole + 1)
        if not group_key:
            return
        key = str(group_key)
        self.image_list_group_collapsed[key] = not bool(self.image_list_group_collapsed.get(key, False))
        self.file_list.blockSignals(True)
        self.file_list.setCurrentItem(None)
        self.file_list.blockSignals(False)
        self.refresh_file_list(restore_selection=False, reuse_group_cache=True)

    def eventFilter(self, watched, event):
        if (
            event is not None
            and event.type() == QEvent.Close
            and watched is getattr(self, "vlm_preannotation_progress_dialog", None)
            and getattr(self, "vlm_preannotation_run_active", False)
        ):
            if hasattr(event, "spontaneous") and not event.spontaneous():
                event.ignore()
                return True
            if self.request_stop_vlm_preannotation(confirm=True):
                event.ignore()
                return True
            event.ignore()
            return True
        if (
            event is not None
            and event.type() == QEvent.KeyPress
            and event.key() in (Qt.Key_Up, Qt.Key_Down)
            and event.modifiers() == Qt.NoModifier
            and self._should_use_image_list_arrow_navigation(watched)
        ):
            self._select_adjacent_image(1 if event.key() == Qt.Key_Down else -1)
            event.accept()
            return True
        return super().eventFilter(watched, event)

    def _should_use_image_list_arrow_navigation(self, watched):
        if not hasattr(self, "tabs") or not hasattr(self, "workbench_widget") or not hasattr(self, "file_list"):
            return False
        if self.tabs.currentWidget() is not self.workbench_widget:
            return False
        if getattr(self, "active_project_kind", "image") != "image":
            return False
        if getattr(self.file_list, "count", lambda: 0)() <= 0:
            return False

        focus = QApplication.focusWidget()
        widget = watched if isinstance(watched, QWidget) else focus
        if widget is None:
            return False

        blocked_types = (
            QLineEdit,
            QTextEdit,
            QComboBox,
            QSpinBox,
            QSlider,
            QTreeWidget,
            QTableWidget,
        )
        if isinstance(widget, blocked_types):
            return False

        parent = widget
        while parent is not None:
            if parent in (self.file_list, self.canvas, self.canvas_shell, self.workbench_widget):
                return True
            if isinstance(parent, (QLineEdit, QTextEdit, QComboBox, QSpinBox, QSlider, QTreeWidget, QTableWidget)):
                return False
            parent = parent.parentWidget()
        return False

    def _select_adjacent_image(self, direction):
        if not hasattr(self, "file_list"):
            return False
        direction = 1 if int(direction or 0) >= 0 else -1
        count = self.file_list.count()
        if count <= 0:
            return False

        current_row = self.file_list.currentRow()
        if current_row < 0:
            current_row = -1 if direction > 0 else count

        row = current_row + direction
        while 0 <= row < count:
            item = self.file_list.item(row)
            if item is not None and item.data(Qt.UserRole):
                self.file_list.setCurrentItem(item)
                self.file_list.scrollToItem(item, QAbstractItemView.PositionAtCenter)
                return True
            row += direction
        return False

    def _collect_blink_roi_candidates(self, image_path, selected_part=None, preferred_roi_parts=None):
        manual_boxes = self.project.get_boxes(image_path)
        box_splitter = getattr(self, "_auto_boxes_for_canvas", None)
        if callable(box_splitter):
            auto_boxes, vlm_boxes = box_splitter(image_path)
        else:
            project_splitter = getattr(self.project, "split_auto_boxes_by_source", None)
            if callable(project_splitter):
                auto_boxes, vlm_boxes = project_splitter(image_path)
            else:
                auto_boxes = self.project.get_auto_boxes(image_path)
                vlm_boxes = {}
                get_meta = getattr(self.project, "get_auto_box_meta", None)
                meta = get_meta(image_path) if callable(get_meta) else {}
                meta = meta if isinstance(meta, dict) else {}
                if isinstance(auto_boxes, dict):
                    model_boxes = {}
                    for part_name, box in auto_boxes.items():
                        part_meta = meta.get(part_name, {}) if isinstance(meta.get(part_name), dict) else {}
                        if part_meta.get("source") == AUTO_BOX_SOURCE_VLM:
                            vlm_boxes[part_name] = box
                        else:
                            model_boxes[part_name] = box
                    auto_boxes = model_boxes
        candidates = []

        def _append(boxes, source):
            if not isinstance(boxes, dict):
                return

            ordered_parts = list(boxes.keys())
            preferred_parts = [part for part in list(preferred_roi_parts or []) if part in ordered_parts]
            if preferred_parts:
                ordered_parts = preferred_parts + [part for part in ordered_parts if part not in preferred_parts]

            for part in ordered_parts:
                box = boxes.get(part)
                if not isinstance(box, (list, tuple)) or len(box) != 4:
                    continue
                try:
                    clean_box = [float(v) for v in box]
                except Exception:
                    continue
                if clean_box[2] <= clean_box[0] or clean_box[3] <= clean_box[1]:
                    continue
                candidates.append({
                    "part": part,
                    "source": source,
                    "box": clean_box,
                })

        _append(manual_boxes, "manual")
        _append(auto_boxes, "auto")
        _append(vlm_boxes, "vlm")
        return candidates
