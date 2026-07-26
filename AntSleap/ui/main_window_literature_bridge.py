try:
    from AntSleap.ui.main_window_navigation_dependencies import *
except ImportError:
    from ui.main_window_navigation_dependencies import *


class MainWindowLiteratureBridgeMixin:
    def on_genus_changed(self, txt):
        if self.current_image:
            set_taxon = getattr(self.project, "set_taxon", self.project.set_genus)
            try:
                set_taxon(self.current_image, txt, save=False)
            except TypeError:
                set_taxon(self.current_image, txt)
            self._schedule_project_save()

    def update_db_description(self, p):
        if p:
            saved_description = ""
            if self.current_image and hasattr(self.project, "get_part_description"):
                saved_description = self.project.get_part_description(self.current_image, p)
            if saved_description:
                self.desc_box.setText(saved_description)
            else:
                self.desc_box.setText(self.db.query_trait_description(self.genus_combo.currentText(), p))

    def _current_taxon_text(self):
        try:
            return self.genus_combo.currentText().strip()
        except Exception:
            return ""

    def _literature_source_taxon(self, source_meta):
        if not isinstance(source_meta, dict):
            return ""
        for key in ("taxon_name", "llm_taxon_name", "species_candidate"):
            value = str(source_meta.get(key) or "").strip()
            if value and value.lower() not in {"unknown", "unknown taxon", "n/a", "none", "null"}:
                return value
        return ""

    def _set_current_image_taxon_from_literature(self, source_meta):
        taxon = self._literature_source_taxon(source_meta)
        if not self.current_image or not taxon:
            return False
        set_taxon = getattr(self.project, "set_taxon", self.project.set_genus)
        try:
            set_taxon(self.current_image, taxon, save=False)
        except TypeError:
            set_taxon(self.current_image, taxon)
        self._schedule_project_save()
        if hasattr(self, "genus_combo"):
            self.genus_combo.blockSignals(True)
            try:
                if self.genus_combo.findText(taxon) < 0:
                    self.genus_combo.addItem(taxon)
                self.genus_combo.setCurrentText(taxon)
            finally:
                self.genus_combo.blockSignals(False)
        return True

    def _candidate_literature_db_paths(self, provenance):
        extra_paths = []
        inferred_db = infer_literature_db_path_from_artifact_image(self.current_image)
        if inferred_db:
            extra_paths.append(inferred_db)
        for candidate in self._project_literature_db_paths():
            if candidate:
                extra_paths.append(candidate)
        pdf_widget = getattr(self, "pdf_widget", None)
        if pdf_widget is not None and hasattr(pdf_widget, "_resolve_extract_db_path"):
            try:
                widget_path = pdf_widget._resolve_extract_db_path(pdf_widget.edit_db_path.text())
                if widget_path:
                    extra_paths.append(widget_path)
            except Exception:
                pass
        return candidate_literature_db_paths(
            repo_root=REPO_ROOT,
            provenance=provenance,
            extra_paths=extra_paths,
        )

    def _project_literature_db_paths(self):
        paths = []

        def add_path(value):
            text = str(value or "").strip()
            if not text:
                return
            try:
                expanded = os.path.abspath(os.path.expanduser(text))
            except Exception:
                return
            norm = os.path.normcase(os.path.normpath(expanded))
            if norm not in {os.path.normcase(os.path.normpath(path)) for path in paths}:
                paths.append(expanded)

        provenance_map = {}
        try:
            provenance_map = self.project.project_data.get("image_provenance", {})
        except Exception:
            provenance_map = {}
        if isinstance(provenance_map, dict):
            for provenance in provenance_map.values():
                if not isinstance(provenance, dict):
                    continue
                add_path(provenance.get("source_db"))
                source_ref = provenance.get("source_ref", {})
                if isinstance(source_ref, dict):
                    add_path(source_ref.get("db_path"))
                inferred_from_parent = infer_literature_db_path_from_artifact_image(
                    (provenance.get("derived_from") or {}).get("image_path", "")
                    if isinstance(provenance.get("derived_from"), dict)
                    else ""
                )
                add_path(inferred_from_parent)

        project_path = getattr(self.project, "current_project_path", "") or ""
        if project_path:
            project_dir = os.path.dirname(os.path.abspath(project_path))
            for value in (
                os.path.join(project_dir, "taxamask_literature.db"),
                os.path.join(project_dir, "pdf_extraction", "taxamask_literature.db"),
                os.path.join(os.path.dirname(project_dir), "pdf_extraction", "taxamask_literature.db"),
            ):
                add_path(value)
        try:
            pdf_root = os.path.join(self._default_outputs_root(), "pdf_extraction")
            add_path(os.path.join(pdf_root, "taxamask_literature.db"))
            if os.path.isdir(pdf_root):
                for dirpath, _dirnames, filenames in os.walk(pdf_root):
                    for filename in filenames:
                        if filename.lower().endswith(".db"):
                            add_path(os.path.join(dirpath, filename))
        except Exception:
            pass
        return paths

    def _resolve_current_literature_context(self):
        if not self.current_image:
            return "", {}, "no_current_image"
        provenance = {}
        if hasattr(self.project, "get_image_provenance"):
            provenance = self.project.get_image_provenance(self.current_image)
        last_reason = "literature_db_missing"
        taxon_hint = self._current_taxon_text()
        for db_path in self._candidate_literature_db_paths(provenance):
            if not os.path.exists(db_path):
                continue
            trusted_db = self._literature_db_matches_image_source(db_path, provenance)
            context = resolve_literature_context(
                db_path,
                image_path=self.current_image,
                provenance=provenance,
                taxon_hint=taxon_hint,
                allow_filename_figure_id=trusted_db,
            )
            if context.get("available"):
                return db_path, context, ""
            last_reason = str(context.get("reason", "") or last_reason)
        if taxon_hint and taxon_hint.lower() not in {"unknown", "unknown taxon", "n/a", "none", "null"}:
            for db_path in self._candidate_literature_db_paths(provenance):
                if not os.path.exists(db_path):
                    continue
                context = resolve_literature_context(
                    db_path,
                    image_path=self.current_image,
                    provenance=provenance,
                    taxon_hint=taxon_hint,
                    allow_filename_figure_id=False,
                    allow_taxon_match=True,
                )
                if context.get("available") and context.get("link_mode") == "taxon_match_not_image_provenance":
                    return db_path, context, ""
                last_reason = str(context.get("reason", "") or last_reason)
        fallback_db = default_literature_db_path(REPO_ROOT)
        return fallback_db, {}, last_reason

    def _resolve_literature_context_from_selected_db(self, db_path):
        if not self.current_image or not db_path:
            return {}, "literature_db_missing"
        provenance = {}
        if hasattr(self.project, "get_image_provenance"):
            provenance = self.project.get_image_provenance(self.current_image)
        taxon_hint = self._current_taxon_text()
        context = resolve_literature_context(
            db_path,
            image_path=self.current_image,
            provenance=provenance,
            taxon_hint=taxon_hint,
            allow_filename_figure_id=True,
        )
        if context.get("available"):
            return context, ""
        context = resolve_literature_context(
            db_path,
            image_path=self.current_image,
            provenance=provenance,
            taxon_hint=taxon_hint,
            allow_filename_figure_id=False,
            allow_taxon_match=True,
        )
        if context.get("available"):
            return context, ""
        return {}, str(context.get("reason", "") or "figure_context_missing")

    def _choose_literature_db_for_current_taxon(self):
        start_dir = os.path.join(self._default_outputs_root(), "pdf_extraction")
        if not os.path.isdir(start_dir):
            start_dir = self._default_outputs_root()
        db_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("Choose Literature Database", self.current_lang),
            start_dir,
            "SQLite Database (*.db);;All Files (*)",
        )
        db_path = str(db_path or "").strip()
        if not db_path:
            return "", {}, "literature_db_missing"
        context, reason = self._resolve_literature_context_from_selected_db(db_path)
        if context:
            pdf_widget = getattr(self, "pdf_widget", None)
            if pdf_widget is not None and hasattr(pdf_widget, "_set_extract_db_path"):
                try:
                    pdf_widget._set_extract_db_path(db_path)
                except Exception:
                    pass
            return db_path, context, ""
        return db_path, {}, reason

    def _literature_db_matches_image_source(self, db_path, provenance):
        db_norm = os.path.normcase(os.path.normpath(os.path.abspath(str(db_path or ""))))
        provenance = provenance if isinstance(provenance, dict) else {}
        source_db = str(provenance.get("source_db", "") or "").strip()
        source_ref = provenance.get("source_ref", {})
        if not isinstance(source_ref, dict):
            source_ref = {}
        for value in (source_db, source_ref.get("db_path")):
            if not value:
                continue
            try:
                candidate = os.path.normcase(os.path.normpath(os.path.abspath(os.path.expanduser(str(value)))))
            except Exception:
                continue
            if candidate == db_norm:
                return True
        inferred_db = infer_literature_db_path_from_artifact_image(self.current_image)
        if inferred_db:
            inferred_norm = os.path.normcase(os.path.normpath(os.path.abspath(inferred_db)))
            if inferred_norm == db_norm:
                return True
        return False

    def open_literature_description_dialog(self):
        if not self.current_image:
            QMessageBox.warning(self, tr("Literature Trait Descriptions", self.current_lang), tr("Please select an image first.", self.current_lang))
            return
        current_part = self._current_part_name()
        if not current_part:
            QMessageBox.warning(self, tr("Literature Trait Descriptions", self.current_lang), tr("Please select a target part first.", self.current_lang))
            return

        db_path, context, reason = self._resolve_current_literature_context()
        if not context:
            taxon_text = self._current_taxon_text()
            if taxon_text and taxon_text.lower() not in {"unknown", "unknown taxon", "n/a", "none", "null"}:
                reply = themed_yes_no_question(
                    self,
                    tr("Choose Literature Database", self.current_lang),
                    tr(
                        "No literature database was found automatically. Choose the PDF extraction database that contains this species?",
                        self.current_lang,
                    ),
                    default_button=QMessageBox.Yes,
                )
                if reply == QMessageBox.Yes:
                    db_path, context, reason = self._choose_literature_db_for_current_taxon()
                    if context:
                        return self._open_literature_description_dialog_with_context(db_path, context, current_part)
            if not self._current_taxon_text() or self._current_taxon_text().lower() in {"unknown", "unknown taxon", "n/a", "none", "null"}:
                message = tr(
                    "No PDF literature source is linked to the current image, and the current image taxon is unknown. Set the current image taxon first, or import images through the PDF candidate workflow.",
                    self.current_lang,
                )
            else:
                message = tr(
                    "No PDF literature source is linked to the current image. Import images through the PDF candidate workflow or open a project that preserves PDF image provenance.",
                    self.current_lang,
                )
            if reason == "literature_db_missing":
                message = tr("PDF literature database was not found: {0}", self.current_lang).format(db_path)
            QMessageBox.information(self, tr("Literature Trait Descriptions", self.current_lang), message)
            return

        self._open_literature_description_dialog_with_context(db_path, context, current_part)

    def _open_literature_description_dialog_with_context(self, db_path, context, current_part):
        dialog = LiteratureDescriptionDialog(
            db_path=db_path,
            context=context,
            image_path=self.current_image,
            current_part=current_part,
            taxon_hint=self._current_taxon_text(),
            parent=self,
            lang=self.current_lang,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        description_text = dialog.selected_description_text()
        if not description_text:
            return
        source_meta = dialog.selected_source()
        self._apply_literature_description(
            current_part,
            description_text,
            source_meta,
            append=(dialog.action_mode == "append"),
        )

    def _apply_literature_description(self, part_name, description_text, source_meta, append=False):
        clean_part = str(part_name or "").strip()
        clean_text = str(description_text or "").strip()
        if not self.current_image or not clean_part or not clean_text:
            return
        existing = self.desc_box.toPlainText().strip()
        missing_prefix = "No description found for "
        if append and existing and not existing.startswith(missing_prefix) and clean_text not in existing:
            final_text = f"{existing}\n\n{clean_text}"
        else:
            final_text = clean_text
        self.desc_box.setText(final_text)
        self._ensure_workbench_description_visible()
        set_part_description = getattr(self.project, "set_part_description", None)
        if callable(set_part_description):
            set_part_description(self.current_image, clean_part, final_text, source_meta=source_meta, save=False)
        else:
            existing_points = self.project.get_labels(self.current_image).get(clean_part, [])
            self.project.update_label(
                self.current_image,
                clean_part,
                existing_points,
                final_text,
                save=False,
                preserve_training_truth=True,
            )
            if source_meta and hasattr(self.project, "set_description_source"):
                self.project.set_description_source(self.current_image, clean_part, source_meta, save=False)
        self._set_current_image_taxon_from_literature(source_meta)
        self._schedule_project_save()
        self.log(tr("Applied literature description for {0}.", self.current_lang).format(clean_part))

    def _ensure_workbench_description_visible(self):
        if hasattr(self, "workbench_inspector_scroll"):
            self.workbench_inspector_scroll.setMinimumWidth(260)
        if hasattr(self, "workbench_splitter"):
            sizes = self.workbench_splitter.sizes()
            if len(sizes) >= 3 and sizes[2] < 180:
                total = max(sum(sizes), 900)
                left = sizes[0] if sizes[0] >= 180 else 240
                right = min(360, max(260, total // 5))
                center = max(360, total - left - right)
                self.workbench_splitter.setSizes([left, center, right])
        if hasattr(self, "desc_box"):
            if hasattr(self, "workbench_inspector_scroll"):
                self.workbench_inspector_scroll.ensureWidgetVisible(self.desc_box)
            self.desc_box.setFocus(Qt.OtherFocusReason)
