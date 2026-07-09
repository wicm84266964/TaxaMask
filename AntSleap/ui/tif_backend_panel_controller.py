from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QTableWidgetItem

from .tif_workbench_translations import tt


class TifBackendPanelController:
    def __init__(self, workbench):
        self.workbench = workbench

    @property
    def project(self):
        return self.workbench.project

    @property
    def lang(self):
        return self.workbench.lang

    def _compact_path(self, path, max_chars=72):
        return self.workbench._compact_path_for_side_panel(path, max_chars=max_chars)

    def _backend_running(self):
        return bool(self.workbench._backend_action_running())

    def predict_ref_key(self, ref):
        if isinstance(ref, (list, tuple)) and len(ref) >= 3:
            return (str(ref[0] or ""), str(ref[1] or ""), str(ref[2] or ""))
        specimen_id = str((ref or {}).get("specimen_id") or "")
        part_id = str((ref or {}).get("part_id") or "")
        reslice_id = str((ref or {}).get("reslice_id") or "")
        return (specimen_id, part_id, reslice_id)

    def predict_ref_from_key(self, key):
        specimen_id, part_id, reslice_id = self.predict_ref_key(key)
        return {"specimen_id": specimen_id, "part_id": part_id, "reslice_id": reslice_id}

    def populate_predict_filter_combo(self):
        combo = getattr(self.workbench, "predict_filter_combo", None)
        if combo is None:
            return
        current = combo.currentData() if combo.count() else "all"
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(tt("All parts", self.lang), "all")
        combo.addItem(tt("Current part", self.lang), "current")
        for tag in self.project.project_data.get("part_user_tags", []) or []:
            if not isinstance(tag, dict):
                continue
            tag_id = str(tag.get("tag_id") or "")
            if not tag_id:
                continue
            combo.addItem(str(tag.get("label") or tag_id), f"tag:{tag_id}")
        index = combo.findData(current)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)

    def predict_target_rows(self):
        wb = self.workbench
        selected_filter = str(wb.predict_filter_combo.currentData() or "all") if hasattr(wb, "predict_filter_combo") else "all"
        tag_lookup = wb._part_user_tag_lookup()
        rows = []
        for specimen in self.project.project_data.get("specimens", []) or []:
            if not isinstance(specimen, dict):
                continue
            specimen_id = str(specimen.get("specimen_id") or "")
            specimen_name = str(specimen.get("display_name") or specimen_id)
            for part in specimen.get("parts", []) or []:
                if not isinstance(part, dict):
                    continue
                part_id = str(part.get("part_id") or "")
                if not specimen_id or not part_id:
                    continue
                part_tags = [str(item) for item in (part.get("user_tags") or []) if str(item or "")]
                if selected_filter == "current":
                    if specimen_id != wb.current_specimen_id or part_id != wb.current_part_id:
                        continue
                elif selected_filter.startswith("tag:"):
                    wanted_tag = selected_filter.split(":", 1)[1]
                    if wanted_tag not in part_tags:
                        continue
                reslices = self.project.list_part_reslices(specimen_id, part_id)
                if not reslices:
                    reslices = [{}]
                for reslice in reslices:
                    reslice_id = str((reslice or {}).get("reslice_id") or "")
                    try:
                        readiness = self.project.evaluate_part_predict_ready(specimen_id, part_id, reslice_id)
                    except Exception as exc:
                        readiness = {
                            "specimen_id": specimen_id,
                            "part_id": part_id,
                            "reslice_id": reslice_id,
                            "label_schema_id": str(((part.get("training") or {}).get("label_schema_id")) or ""),
                            "predict_ready": False,
                            "checks": {},
                            "reasons": [str(exc)],
                            "input_shape_zyx": [],
                        }
                    effective_reslice_id = str(readiness.get("reslice_id") or reslice_id)
                    labels = part.get("labels") or {}
                    editable = labels.get("editable_ai_result") or {}
                    rows.append(
                        {
                            "ref": {"specimen_id": specimen_id, "part_id": part_id, "reslice_id": effective_reslice_id},
                            "specimen_label": specimen_name,
                            "part_label": str((part.get("training") or {}).get("user_defined_part_name") or part.get("display_name") or part_id),
                            "part_id": part_id,
                            "reslice_id": effective_reslice_id,
                            "label_schema_id": str(readiness.get("label_schema_id") or ""),
                            "tags": ", ".join(tag_lookup.get(tag_id, tag_id) for tag_id in part_tags),
                            "ready": bool(readiness.get("predict_ready")),
                            "reasons": list(readiness.get("reasons") or []),
                            "overwrite": bool(str(editable.get("path") or "").strip()),
                            "shape": list(readiness.get("input_shape_zyx") or []),
                        }
                    )
        return rows

    def make_predict_table_item(self, text, editable=False):
        item = QTableWidgetItem(str(text or ""))
        flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        if editable:
            flags |= Qt.ItemIsEditable
        item.setFlags(flags)
        return item

    def predict_status_text(self, row):
        if row.get("ready"):
            return tt("Ready", self.lang)
        reasons = row.get("reasons") or []
        if not reasons:
            return tt("Not ready", self.lang)
        return ", ".join(str(item) for item in reasons)

    def sync_predict_selection_from_table(self):
        selected = set()
        table = self.workbench.predict_targets_table
        for row_index in range(table.rowCount()):
            item = table.item(row_index, 0)
            if item is None or item.checkState() != Qt.Checked:
                continue
            ref = item.data(Qt.UserRole) or {}
            selected.add(self.predict_ref_key(ref))
        self.workbench._tif_predict_selected_refs = selected

    def update_predict_target_summary(self):
        table = getattr(self.workbench, "predict_targets_table", None)
        if table is None:
            return
        total = table.rowCount()
        ready = 0
        selected = 0
        overwrite = 0
        blocked = 0
        for row_index in range(total):
            item = table.item(row_index, 0)
            if item is not None and item.checkState() == Qt.Checked:
                selected += 1
            ready_item = table.item(row_index, 6)
            is_ready = bool(ready_item.data(Qt.UserRole)) if ready_item is not None else False
            if is_ready:
                ready += 1
            else:
                blocked += 1
            overwrite_item = table.item(row_index, 7)
            if overwrite_item is not None and bool(overwrite_item.data(Qt.UserRole)):
                overwrite += 1
        text = tt(
            "Prediction targets: {0} listed, {1} ready, {2} selected, {3} will overwrite editable AI result, {4} incomplete.",
            self.lang,
        ).format(total, ready, selected, overwrite, blocked)
        self.workbench.predict_targets_summary_label.setText(text)

    def refresh_predict_targets(self):
        wb = self.workbench
        if not hasattr(wb, "predict_targets_table"):
            return
        self.populate_predict_filter_combo()
        table = wb.predict_targets_table
        wb._tif_predict_refreshing = True
        try:
            rows = self.predict_target_rows()
            table.blockSignals(True)
            table.setRowCount(0)
            table.setColumnCount(8)
            table.setHorizontalHeaderLabels(
                [
                    tt("Use", self.lang),
                    tt("Specimen", self.lang),
                    tt("Part", self.lang),
                    tt("Reslice", self.lang),
                    tt("Group tags", self.lang),
                    tt("Label schema", self.lang),
                    tt("Predict check", self.lang),
                    tt("Overwrite", self.lang),
                ]
            )
            for row_index, row in enumerate(rows):
                table.insertRow(row_index)
                ref = row["ref"]
                key = self.predict_ref_key(ref)
                select_item = QTableWidgetItem("")
                flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable
                select_item.setFlags(flags)
                select_item.setCheckState(Qt.Checked if key in wb._tif_predict_selected_refs and row.get("ready") else Qt.Unchecked)
                if not row.get("ready"):
                    select_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
                select_item.setData(Qt.UserRole, ref)
                table.setItem(row_index, 0, select_item)
                table.setItem(row_index, 1, self.make_predict_table_item(row["specimen_label"]))
                table.setItem(row_index, 2, self.make_predict_table_item(f"{row['part_label']} ({row['part_id']})"))
                table.setItem(row_index, 3, self.make_predict_table_item(row["reslice_id"]))
                table.setItem(row_index, 4, self.make_predict_table_item(row["tags"]))
                table.setItem(row_index, 5, self.make_predict_table_item(row["label_schema_id"]))
                status_item = self.make_predict_table_item(self.predict_status_text(row))
                status_item.setData(Qt.UserRole, bool(row.get("ready")))
                table.setItem(row_index, 6, status_item)
                overwrite_item = self.make_predict_table_item(tt("yes", self.lang) if row.get("overwrite") else tt("no", self.lang))
                overwrite_item.setData(Qt.UserRole, bool(row.get("overwrite")))
                table.setItem(row_index, 7, overwrite_item)
            table.resizeColumnsToContents()
            table.blockSignals(False)
        finally:
            wb._tif_predict_refreshing = False
        self.sync_predict_selection_from_table()
        self.update_predict_target_summary()

    def on_predict_target_item_changed(self, item):
        wb = self.workbench
        if wb._tif_predict_refreshing or item is None or item.column() != 0:
            return
        status_item = wb.predict_targets_table.item(item.row(), 6)
        if status_item is not None and not bool(status_item.data(Qt.UserRole)) and item.checkState() == Qt.Checked:
            wb.predict_targets_table.blockSignals(True)
            item.setCheckState(Qt.Unchecked)
            wb.predict_targets_table.blockSignals(False)
        self.sync_predict_selection_from_table()
        self.update_predict_target_summary()

    def select_all_ready_predict_targets(self):
        table = self.workbench.predict_targets_table
        table.blockSignals(True)
        for row_index in range(table.rowCount()):
            item = table.item(row_index, 0)
            status_item = table.item(row_index, 6)
            if item is not None and status_item is not None and bool(status_item.data(Qt.UserRole)):
                item.setCheckState(Qt.Checked)
        table.blockSignals(False)
        self.sync_predict_selection_from_table()
        self.update_predict_target_summary()

    def clear_predict_target_selection(self):
        table = self.workbench.predict_targets_table
        table.blockSignals(True)
        for row_index in range(table.rowCount()):
            item = table.item(row_index, 0)
            if item is not None:
                item.setCheckState(Qt.Unchecked)
        table.blockSignals(False)
        self.sync_predict_selection_from_table()
        self.update_predict_target_summary()

    def select_current_predict_target(self):
        wb = self.workbench
        if not wb.current_specimen_id or not wb.current_part_id:
            wb._set_operation_feedback(tt("Select a part volume before choosing the current prediction target.", self.lang))
            return False
        rows = self.predict_target_rows()
        matched = []
        for row in rows:
            ref = row.get("ref") or {}
            if ref.get("specimen_id") == wb.current_specimen_id and ref.get("part_id") == wb.current_part_id and row.get("ready"):
                if wb.current_reslice_id and ref.get("reslice_id") != wb.current_reslice_id:
                    continue
                matched.append(ref)
        if not matched and wb.current_reslice_id:
            for row in rows:
                ref = row.get("ref") or {}
                if ref.get("specimen_id") == wb.current_specimen_id and ref.get("part_id") == wb.current_part_id and row.get("ready"):
                    matched.append(ref)
        if not matched:
            wb._set_operation_feedback(tt("Current part is not ready for prediction.", self.lang))
            return False
        for ref in matched[:1]:
            wb._tif_predict_selected_refs.add(self.predict_ref_key(ref))
        self.refresh_predict_targets()
        return True

    def model_records(self):
        if hasattr(self.project, "list_tif_segmentation_models"):
            return list(self.project.list_tif_segmentation_models())
        return []

    def model_record_id(self, record):
        source = record if isinstance(record, dict) else {}
        return str(source.get("model_id") or source.get("model_manifest") or "").strip()

    def model_display_name(self, record):
        source = record if isinstance(record, dict) else {}
        model_id = str(source.get("model_id") or source.get("run_id") or source.get("model_manifest") or "model").strip()
        created = str(source.get("created_at") or "").split("T", 1)[0]
        samples = source.get("training_samples", 0)
        suffix = []
        if samples:
            suffix.append(tt("{0} sample(s)", self.lang).format(samples))
        scope = str(source.get("input_scope") or "").strip()
        if scope:
            suffix.append(scope)
        if created:
            suffix.append(created)
        return f"{model_id} ({', '.join(suffix)})" if suffix else model_id

    def format_model_summary(self, record):
        source = record if isinstance(record, dict) else {}
        if not source:
            return tt("No trained model is registered for this project.", self.lang)
        manifest = self.project.to_absolute(source.get("model_manifest", ""))
        model_path = self.project.to_absolute(source.get("model_path", ""))
        schemas = ", ".join(str(item) for item in source.get("label_schema_ids", []) if str(item or "")) or "-"
        samples = str(source.get("training_samples") or 0)
        usable = tt("usable", self.lang) if source.get("usable_for_research_prediction", True) else tt("not marked usable", self.lang)
        lines = [
            tt("Samples: {0}; schemas: {1}; status: {2}", self.lang).format(samples, schemas, usable),
            tt("Manifest: {0}", self.lang).format(self._compact_path(manifest or "-")),
        ]
        if model_path:
            lines.append(tt("Output: {0}", self.lang).format(self._compact_path(model_path)))
        return "\n".join(lines)

    def model_tooltip(self, record):
        source = record if isinstance(record, dict) else {}
        if not source:
            return tt("No trained model is registered for this project.", self.lang)
        lines = [self.model_display_name(source)]
        for label, key in (
            (tt("Model ID", self.lang), "model_id"),
            (tt("Run ID", self.lang), "run_id"),
            (tt("Model manifest", self.lang), "model_manifest"),
            (tt("Model output", self.lang), "model_path"),
        ):
            value = str(source.get(key) or "").strip()
            if value:
                if key in {"model_manifest", "model_path"}:
                    value = self.project.to_absolute(value)
                lines.append(f"{label}: {value}")
        notes = str(source.get("notes") or "").strip()
        if notes:
            lines.append(f"{tt('Notes', self.lang)}: {notes}")
        return "\n".join(lines)

    def populate_model_library_combo(self, preferred_id=None):
        wb = self.workbench
        if not hasattr(wb, "model_library_combo"):
            return
        current = str(preferred_id or wb.model_library_combo.currentData() or "").strip()
        records = self.model_records()
        wb.model_library_combo.blockSignals(True)
        wb.model_library_combo.clear()
        wb.model_library_combo.addItem(tt("No registered model", self.lang), "")
        for record in sorted(records, key=lambda item: str(item.get("created_at") or item.get("model_id") or ""), reverse=True):
            model_id = self.model_record_id(record)
            wb.model_library_combo.addItem(self.model_display_name(record), model_id)
            index = wb.model_library_combo.count() - 1
            wb.model_library_combo.setItemData(index, record, Qt.UserRole + 1)
        index = wb.model_library_combo.findData(current)
        if index < 0 and records:
            index = 1
        wb.model_library_combo.setCurrentIndex(max(0, index))
        wb.model_library_combo.blockSignals(False)
        self.on_model_library_selection_changed()

    def selected_model_record(self):
        combo = getattr(self.workbench, "model_library_combo", None)
        if combo is None:
            return None
        record = combo.currentData(Qt.UserRole + 1)
        return record if isinstance(record, dict) else None

    def on_model_library_selection_changed(self, *_args):
        wb = self.workbench
        record = self.selected_model_record()
        if hasattr(wb, "model_library_summary_label"):
            wb.model_library_summary_label.setText(self.format_model_summary(record))
            wb.model_library_summary_label.setToolTip(self.model_tooltip(record))
        if hasattr(wb, "model_library_notes_edit"):
            wb.model_library_notes_edit.blockSignals(True)
            wb.model_library_notes_edit.setPlainText(str((record or {}).get("notes") or ""))
            wb.model_library_notes_edit.blockSignals(False)
        self.refresh_model_library_controls()

    def refresh_model_library_controls(self):
        wb = self.workbench
        if not hasattr(wb, "btn_use_selected_tif_model"):
            return
        running = self._backend_running()
        record = self.selected_model_record()
        manifest = self.project.to_absolute((record or {}).get("model_manifest", ""))
        has_record = bool(record)
        wb.btn_use_selected_tif_model.setEnabled(has_record and bool(manifest) and os.path.exists(manifest) and not running)
        wb.btn_save_tif_model_notes.setEnabled(has_record and not running)
        wb.btn_delete_tif_model_record.setEnabled(has_record and not running)
        wb.model_library_notes_edit.setEnabled(has_record and not running)

    def training_result_summary_tooltip(self, summary):
        if not isinstance(summary, dict) or not summary:
            return tt("No training result yet.", self.lang)
        lines = [tt("Training result is ready for review.", self.lang)]
        for label, key in (
            (tt("Model output", self.lang), "model_output"),
            (tt("Model manifest", self.lang), "model_manifest"),
            (tt("Run ID", self.lang), "run_id"),
        ):
            value = str(summary.get(key) or "").strip()
            if value:
                lines.append(f"{label}: {value}")
        run_dir = str(summary.get("run_dir") or "").strip()
        if run_dir:
            lines.append(f"{tt('Open run folder', self.lang)}: {run_dir}")
        return "\n".join(lines)

    def format_training_result_summary_text(self, summary):
        if not isinstance(summary, dict) or not summary:
            return tt("No training result yet.", self.lang)
        metrics_count = len(summary.get("metrics") or [])
        curve_count = len(summary.get("curves") or [])
        preview_count = len(summary.get("previews") or [])
        model_output = self._compact_path(summary.get("model_output") or "-")
        model_manifest = self._compact_path(summary.get("model_manifest") or "-")
        lines = [
            tt("Training result is ready for review.", self.lang),
            tt(
                "Training result: {0} metric(s), {1} curve(s), {2} mask preview(s).\nModel output: {3}\nModel manifest: {4}",
                self.lang,
            ).format(metrics_count, curve_count, preview_count, model_output, model_manifest),
        ]
        warnings = summary.get("warnings") or []
        errors = summary.get("errors") or []
        if warnings:
            lines.append(f"{tt('Warnings', self.lang)}: {len(warnings)}")
        if errors:
            lines.append(f"{tt('Errors', self.lang)}: {len(errors)}")
        return "\n".join(lines)

    def refresh_training_result_controls(self):
        wb = self.workbench
        if not hasattr(wb, "btn_show_training_result_summary"):
            return
        running = self._backend_running()
        summary = wb._tif_training_result_summary if isinstance(wb._tif_training_result_summary, dict) else {}
        model_output = str(summary.get("model_output") or wb._tif_training_model_output_dir or "")
        model_manifest = str(summary.get("model_manifest") or wb._tif_training_model_manifest or "")
        has_summary = bool(summary)
        wb.btn_show_training_result_summary.setEnabled(has_summary and not running)
        wb.btn_open_training_model_output.setEnabled(bool(model_output) and os.path.isdir(model_output) and not running)
        wb.btn_open_training_model_manifest.setEnabled(bool(model_manifest) and os.path.exists(model_manifest) and not running)
        wb.btn_batch_predict_entry.setEnabled(bool(model_manifest) and os.path.exists(model_manifest) and not running)
        self.refresh_model_library_controls()
        if hasattr(wb, "training_result_summary_label"):
            wb.training_result_summary_label.setText(self.format_training_result_summary_text(summary))
            wb.training_result_summary_label.setToolTip(self.training_result_summary_tooltip(summary))

    def set_backend_controls_running(self, running):
        wb = self.workbench
        running = bool(running)
        wb.btn_prepare_dataset.setEnabled(not running)
        wb.btn_train_backend.setEnabled(not running)
        wb.btn_import_prediction.setEnabled(not running)
        wb.btn_browse_model_manifest.setEnabled(not running)
        wb.btn_refresh_predict_targets.setEnabled(not running)
        wb.btn_select_current_predict_target.setEnabled(not running)
        wb.btn_select_ready_predict_targets.setEnabled(not running)
        wb.btn_clear_predict_targets.setEnabled(not running)
        wb.btn_accept_selected_ai_results.setEnabled(not running)
        wb.predict_filter_combo.setEnabled(not running)
        wb.predict_targets_table.setEnabled(not running)
        wb.btn_stop_backend.setEnabled(running)
        wb.btn_open_backend_run.setEnabled(bool(wb._tif_backend_run_dir) and os.path.isdir(wb._tif_backend_run_dir) and not running)
        wb.btn_open_backend_result.setEnabled(bool(wb._tif_backend_result_json) and os.path.exists(wb._tif_backend_result_json) and not running)
        self.refresh_training_result_controls()
        self.refresh_model_library_controls()

    def on_backend_progress(self, current, total, message):
        wb = self.workbench
        wb._progress_tif_task(wb._tif_backend_task_id, current, total, str(message or ""))
        total = int(total or 0)
        current = int(current or 0)
        if total <= 0:
            value = int(getattr(wb, "_tif_backend_progress_value", 0) or 0)
        else:
            value = int(round(max(0, min(total, current)) * 100.0 / max(1, total)))
            value = max(int(getattr(wb, "_tif_backend_progress_value", 0) or 0), value)
        value = max(0, min(100, value))
        wb._tif_backend_progress_value = value
        wb.backend_progress_bar.setRange(0, 100)
        wb.backend_progress_bar.setValue(value)
        wb.backend_progress_bar.setFormat("%p%")
        text = str(message or "")
        if text:
            for line in text.splitlines():
                if line.startswith("Run folder:"):
                    path = line.split(":", 1)[1].strip()
                    if path:
                        wb._tif_backend_run_dir = path
                elif line.startswith("Result JSON:"):
                    path = line.split(":", 1)[1].strip()
                    if path:
                        wb._tif_backend_result_json = path
            first_line = text.splitlines()[0]
            wb.backend_run_status_label.setText(first_line)
            wb.training_status_label.setText(first_line)
            tail = "\n".join(text.splitlines()[-8:])
            wb.backend_log_tail.setPlainText(tail)
            wb.backend_log_tail.moveCursor(QTextCursor.End)
            if wb._backend_action_running():
                wb.btn_open_backend_run.setEnabled(bool(wb._tif_backend_run_dir) and os.path.isdir(wb._tif_backend_run_dir))
                wb.btn_open_backend_result.setEnabled(False)

    def selected_backend_samples_for_action(self, action):
        wb = self.workbench
        selected_predict_refs = []
        if action == "predict":
            self.sync_predict_selection_from_table()
            for key in sorted(wb._tif_predict_selected_refs):
                selected_predict_refs.append(self.predict_ref_from_key(key))
        service_result = wb.backend_workflow_service.selected_backend_samples_for_action(
            action,
            current_volume_scope=wb.current_volume_scope,
            current_specimen_id=wb.current_specimen_id,
            current_part_id=wb.current_part_id,
            current_reslice_id=wb.current_reslice_id,
            selected_predict_refs=selected_predict_refs,
        )
        if service_result:
            return {
                "input_scope": service_result.payload.get("input_scope") or "part_reslice",
                "part_refs": service_result.payload.get("part_refs") or [],
                "specimen_ids": service_result.payload.get("specimen_ids") or [],
                "fallback_reason": service_result.payload.get("fallback_reason", ""),
            }
        if action in {"prepare_dataset", "train"}:
            raise ValueError(wb._training_selection_error(prefer_part=(wb.current_volume_scope == "part")))
        raise ValueError(tt("Selected prediction target is incomplete: {0}", self.lang).format(", ".join(service_result.reasons or [service_result.message])))
