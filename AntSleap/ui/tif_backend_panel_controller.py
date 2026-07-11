from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, Qt, QThread, QUrl
from PySide6.QtGui import QDesktopServices, QTextCursor
from PySide6.QtWidgets import QMessageBox, QTableWidgetItem

from .tif_workbench_dialogs import TifTrainingResultDialog, summarize_tif_training_result
from .tif_workbench_translations import tt
from .tif_workbench_workers import TifBackendActionWorker


@dataclass
class TifBackendPanelState:
    thread: object = None
    worker: object = None
    task_id: str = ""
    action: str = ""
    started_mono: float = 0.0
    run_dir: str = ""
    result_json: str = ""
    last_result: object = None
    pending_selection: dict = field(default_factory=dict)
    pending_action_after_save: object = None
    progress_value: int = 0
    training_result_summary: object = None
    training_result_dialog: object = None
    training_model_output_dir: str = ""
    training_model_manifest: str = ""
    predict_selected_refs: set = field(default_factory=set)
    predict_refreshing: bool = False


class TifBackendPanelController(QObject):
    VIEW_SCOPE = "backend_panel"

    def __init__(self, workbench):
        super().__init__(workbench)
        self.workbench = workbench
        self.state = TifBackendPanelState()

    def bind_signals(self):
        wb = self.workbench
        view = wb.workbench_view
        names = (
            "backend_manifest_edit", "btn_browse_model_manifest", "btn_use_nnunet_backend_preset",
            "btn_save_backend", "btn_prepare_dataset", "btn_train_backend", "btn_import_prediction",
            "predict_filter_combo", "predict_targets_table", "btn_refresh_predict_targets",
            "btn_select_current_predict_target", "btn_select_ready_predict_targets", "btn_clear_predict_targets",
            "btn_stop_backend", "btn_open_backend_run", "btn_open_backend_result", "model_library_combo",
            "btn_show_training_result_summary", "btn_open_training_model_output",
            "btn_open_training_model_manifest", "btn_batch_predict_entry",
        )
        view.register_scope(self.VIEW_SCOPE, *names)
        bindings = (
            ("manifest", "backend_manifest_edit", "textChanged", self.on_predict_manifest_text_changed),
            ("browse_manifest", "btn_browse_model_manifest", "clicked", self.browse_model_manifest),
            ("preset", "btn_use_nnunet_backend_preset", "clicked", self.apply_nnunet_v2_backend_preset),
            ("save", "btn_save_backend", "clicked", self.save_backend_settings),
            ("prepare", "btn_prepare_dataset", "clicked", self.run_prepare_dataset),
            ("train", "btn_train_backend", "clicked", self.run_train),
            ("predict", "btn_import_prediction", "clicked", self.run_predict),
            ("filter", "predict_filter_combo", "currentIndexChanged", self.refresh_predict_targets),
            ("target_item", "predict_targets_table", "itemChanged", self.on_predict_target_item_changed),
            ("refresh_targets", "btn_refresh_predict_targets", "clicked", self.refresh_predict_targets),
            ("select_current", "btn_select_current_predict_target", "clicked", self.select_current_predict_target),
            ("select_ready", "btn_select_ready_predict_targets", "clicked", self.select_all_ready_predict_targets),
            ("clear_targets", "btn_clear_predict_targets", "clicked", self.clear_predict_target_selection),
            ("stop", "btn_stop_backend", "clicked", self.cancel_backend_action),
            ("open_run", "btn_open_backend_run", "clicked", self.open_latest_backend_run_folder),
            ("open_result", "btn_open_backend_result", "clicked", self.open_latest_backend_result_json),
            ("model", "model_library_combo", "currentIndexChanged", self.on_model_library_selection_changed),
            ("show_summary", "btn_show_training_result_summary", "clicked", self.show_latest_training_result_summary),
            ("open_model_output", "btn_open_training_model_output", "clicked", self.open_latest_training_model_output),
            ("open_model_manifest", "btn_open_training_model_manifest", "clicked", self.open_latest_training_model_manifest),
            ("batch_predict", "btn_batch_predict_entry", "clicked", self.enter_batch_prediction_from_training_result),
        )
        for key, widget_name, signal_name, slot in bindings:
            signal = getattr(view.require(self.VIEW_SCOPE, widget_name), signal_name)
            wb.signal_router.bind(self.VIEW_SCOPE, key, signal, slot)

    def on_predict_manifest_text_changed(self, text):
        self.workbench.backend_config["model_manifest"] = str(text or "").strip()
        return self.workbench.backend_config["model_manifest"]

    def browse_model_manifest(self):
        return self.workbench.browse_model_manifest()

    def apply_nnunet_v2_backend_preset(self):
        return self.workbench.apply_nnunet_v2_backend_preset()

    def save_backend_settings(self):
        return self.workbench.save_backend_settings()

    def run_prepare_dataset(self):
        return self.run_backend_action("prepare_dataset")

    def run_train(self):
        return self.run_backend_action("train")

    def run_predict(self):
        return self.run_backend_action("predict")


    @property
    def project(self):
        return self.workbench.project

    @property
    def lang(self):
        return self.workbench.lang

    def _compact_path(self, path, max_chars=72):
        return self.workbench._compact_path_for_side_panel(path, max_chars=max_chars)

    def _backend_running(self):
        return self.action_running()

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

    def selected_predict_refs(self):
        self.sync_predict_selection_from_table()
        return [self.predict_ref_from_key(key) for key in sorted(self.state.predict_selected_refs)]

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
        self.state.predict_selected_refs = selected

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
        self.state.predict_refreshing = True
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
                select_item.setCheckState(Qt.Checked if key in self.state.predict_selected_refs and row.get("ready") else Qt.Unchecked)
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
            self.state.predict_refreshing = False
        self.sync_predict_selection_from_table()
        self.update_predict_target_summary()

    def on_predict_target_item_changed(self, item):
        wb = self.workbench
        if self.state.predict_refreshing or item is None or item.column() != 0:
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
            self.state.predict_selected_refs.add(self.predict_ref_key(ref))
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
        summary = self.state.training_result_summary if isinstance(self.state.training_result_summary, dict) else {}
        model_output = str(summary.get("model_output") or self.state.training_model_output_dir or "")
        model_manifest = str(summary.get("model_manifest") or self.state.training_model_manifest or "")
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
        wb.btn_open_backend_run.setEnabled(bool(self.state.run_dir) and os.path.isdir(self.state.run_dir) and not running)
        wb.btn_open_backend_result.setEnabled(bool(self.state.result_json) and os.path.exists(self.state.result_json) and not running)
        self.refresh_training_result_controls()
        self.refresh_model_library_controls()

    def on_backend_progress(self, current, total, message):
        wb = self.workbench
        wb._progress_tif_task(self.state.task_id, current, total, str(message or ""))
        total = int(total or 0)
        current = int(current or 0)
        if total <= 0:
            value = int(getattr(wb, "_tif_backend_progress_value", 0) or 0)
        else:
            value = int(round(max(0, min(total, current)) * 100.0 / max(1, total)))
            value = max(int(getattr(wb, "_tif_backend_progress_value", 0) or 0), value)
        value = max(0, min(100, value))
        self.state.progress_value = value
        wb.backend_progress_bar.setRange(0, 100)
        wb.backend_progress_bar.setValue(value)
        wb.backend_progress_bar.setFormat("%p%")
        text = str(message or "")
        if text:
            for line in text.splitlines():
                if line.startswith("Run folder:"):
                    path = line.split(":", 1)[1].strip()
                    if path:
                        self.state.run_dir = path
                elif line.startswith("Result JSON:"):
                    path = line.split(":", 1)[1].strip()
                    if path:
                        self.state.result_json = path
            first_line = text.splitlines()[0]
            wb.backend_run_status_label.setText(first_line)
            if wb._task_context_matches_current(
                self.state.task_id,
                fields=("specimen_id", "volume_scope", "part_id", "reslice_id"),
            ):
                wb.training_status_label.setText(first_line)
            tail = "\n".join(text.splitlines()[-8:])
            wb.backend_log_tail.setPlainText(tail)
            wb.backend_log_tail.moveCursor(QTextCursor.End)
            if self.action_running():
                wb.btn_open_backend_run.setEnabled(bool(self.state.run_dir) and os.path.isdir(self.state.run_dir))
                wb.btn_open_backend_result.setEnabled(False)

    def format_part_ref_label(self, ref):
        specimen_id = str((ref or {}).get("specimen_id") or "")
        part_id = str((ref or {}).get("part_id") or "")
        reslice_id = str((ref or {}).get("reslice_id") or "")
        label = f"{specimen_id}:{part_id}" if specimen_id or part_id else ""
        return f"{label}:{reslice_id}" if label and reslice_id else label

    def selected_backend_samples_for_action(self, action):
        wb = self.workbench
        selected_predict_refs = []
        if action == "predict":
            self.sync_predict_selection_from_table()
            for key in sorted(self.state.predict_selected_refs):
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
            raise ValueError(self._training_selection_error(prefer_part=(wb.current_volume_scope == "part")))
        raise ValueError(tt("Selected prediction target is incomplete: {0}", self.lang).format(", ".join(service_result.reasons or [service_result.message])))

    def action_running(self):
        wb = self.workbench
        return self.state.thread is not None

    def _set_training_result_summary(self, summary):
        wb = self.workbench
        previous_auto_manifest = str(wb._tif_training_model_manifest or "")
        summary = summary if isinstance(summary, dict) and summary else None
        wb._tif_training_result_summary = summary
        wb._tif_training_model_output_dir = str((summary or {}).get("model_output") or "")
        wb._tif_training_model_manifest = str((summary or {}).get("model_manifest") or "")
        if wb._tif_training_model_manifest:
            wb.backend_manifest_edit.setText(wb._tif_training_model_manifest)
            wb.backend_config["model_manifest"] = wb._tif_training_model_manifest
        elif previous_auto_manifest and wb.backend_manifest_edit.text().strip() == previous_auto_manifest:
            wb.backend_manifest_edit.clear()
            wb.backend_config["model_manifest"] = ""
        if hasattr(wb, "training_result_summary_label"):
            wb.training_result_summary_label.setText(self.format_training_result_summary_text(summary))
            wb.training_result_summary_label.setToolTip(self.training_result_summary_tooltip(summary))
        self.refresh_training_result_controls()

    def _register_training_summary_model(self, summary, backend_result=None, contract=None):
        wb = self.workbench
        summary = summary if isinstance(summary, dict) else {}
        backend_result = backend_result if isinstance(backend_result, dict) else {}
        contract = contract if isinstance(contract, dict) else {}
        manifest = str(summary.get("model_manifest") or (backend_result.get("provenance") or {}).get("model_manifest") or "").strip()
        if not manifest:
            return None
        metrics_summary = ((backend_result.get("metrics") or {}).get("summary") or {}) if isinstance(backend_result.get("metrics"), dict) else {}
        try:
            record = wb.project.register_tif_segmentation_model_from_manifest(
                manifest,
                {
                    "backend_id": backend_result.get("backend_id") or contract.get("backend_id"),
                    "run_id": backend_result.get("run_id") or contract.get("run_id") or summary.get("run_id"),
                    "run_dir": summary.get("run_dir") or contract.get("run_dir"),
                    "result_json": backend_result.get("_result_json") or contract.get("result_json"),
                    "dataset_manifest": (backend_result.get("provenance") or {}).get("dataset_manifest", ""),
                    "training_samples": metrics_summary.get("training_samples", 0),
                    "usable_for_research_prediction": (backend_result.get("provenance") or {}).get("usable_for_research_prediction", True),
                },
                save=True,
            )
        except Exception as exc:
            wb.log(tt("Model registration skipped: {0}", wb.lang).format(str(exc)))
            return None
        return record

    def show_latest_training_result_summary(self, show_message=True):
        wb = self.workbench
        summary = wb._tif_training_result_summary if isinstance(wb._tif_training_result_summary, dict) else None
        if not summary:
            if show_message:
                QMessageBox.information(wb, tt("Training result", wb.lang), tt("No training result summary is available yet.", wb.lang))
            return False
        if wb._tif_training_result_dialog is not None:
            try:
                wb._tif_training_result_dialog.close()
            except Exception:
                pass
        dialog = TifTrainingResultDialog(summary, wb.lang, wb)
        dialog.setAttribute(Qt.WA_DeleteOnClose, True)
        dialog.destroyed.connect(lambda _obj=None: setattr(self, "_tif_training_result_dialog", None))
        wb._tif_training_result_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        return True

    def open_latest_training_model_output(self):
        wb = self.workbench
        path = str(wb._tif_training_model_output_dir or "")
        if not path or not os.path.isdir(path):
            QMessageBox.information(wb, tt("Training result", wb.lang), tt("No model output folder is available yet.", wb.lang))
            return False
        return QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def open_latest_training_model_manifest(self):
        wb = self.workbench
        path = str(wb._tif_training_model_manifest or "")
        if not path or not os.path.exists(path):
            QMessageBox.information(wb, tt("Training result", wb.lang), tt("No model manifest is available yet.", wb.lang))
            return False
        return QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def enter_batch_prediction_from_training_result(self):
        wb = self.workbench
        manifest = str(wb._tif_training_model_manifest or "")
        if not manifest or not os.path.exists(manifest):
            QMessageBox.information(wb, tt("Training result", wb.lang), tt("No model manifest is available yet.", wb.lang))
            return False
        wb.backend_manifest_edit.setText(manifest)
        wb.backend_config["model_manifest"] = manifest
        if hasattr(wb, "task_tabs") and hasattr(wb, "training_mode_tabs"):
            wb.task_tabs.setCurrentWidget(wb.training_mode_tabs)
            wb.training_mode_tabs.setCurrentWidget(wb.training_task_page)
        self.populate_predict_filter_combo()
        if wb.current_volume_scope in {"part", "part_reslice"} and wb.current_specimen_id and wb.current_part_id:
            index = wb.predict_filter_combo.findData("current")
            if index >= 0:
                wb.predict_filter_combo.setCurrentIndex(index)
            self.select_current_predict_target()
        else:
            self.refresh_predict_targets()
        wb.btn_import_prediction.setFocus(Qt.OtherFocusReason)
        wb._set_operation_feedback(tt("Model manifest filled for batch prediction. Choose target part(s), then run prediction.", wb.lang))
        return True

    def _cleanup_tif_backend_thread(self):
        wb = self.workbench
        wb.backend_elapsed_timer.stop()
        wb._tif_backend_action = ""
        wb._tif_backend_started_mono = 0.0
        self.set_backend_controls_running(False)
        wb._set_scope_controls_enabled()

    def _on_tif_backend_thread_finished(self):
        wb = self.workbench
        wb._tif_backend_worker = None
        wb._tif_backend_thread = None
        self.set_backend_controls_running(False)
        wb._set_scope_controls_enabled()

    def _validated_predict_model_manifest(self):
        wb = self.workbench
        manifest = str(wb.backend_config.get("model_manifest") or wb.backend_manifest_edit.text() or "").strip()
        if not manifest:
            raise ValueError(tt("Select a model manifest before prediction.", wb.lang))
        candidate = manifest
        if not os.path.isabs(candidate):
            candidate = wb.project.to_absolute(candidate) if wb.project.project_dir else os.path.abspath(candidate)
        candidate = os.path.abspath(candidate)
        if not os.path.exists(candidate):
            raise ValueError(tt("Model manifest does not exist: {0}", wb.lang).format(manifest))
        wb.backend_manifest_edit.setText(candidate)
        wb.backend_config["model_manifest"] = candidate
        return candidate

    def _predict_will_overwrite_editable_result(self, part_refs=None, specimen_ids=None, input_scope="part_reslice"):
        wb = self.workbench
        result = wb.backend_workflow_service.predict_will_overwrite_editable_result(
            part_refs=part_refs,
            specimen_ids=specimen_ids,
            input_scope=input_scope,
        )
        return bool(result.payload.get("overwrite"))

    def _confirm_predict_overwrite_if_needed(self, part_refs=None, specimen_ids=None, input_scope="part_reslice"):
        wb = self.workbench
        if not self._predict_will_overwrite_editable_result(part_refs=part_refs, specimen_ids=specimen_ids, input_scope=input_scope):
            return True
        reply = QMessageBox.question(
            wb,
            tt("TIF backend", wb.lang),
            tt("This predict run will overwrite the current editable result for selected target(s), but will not overwrite training truth. Continue?", wb.lang),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return reply == QMessageBox.Yes

    def _start_backend_status(self, action, part_refs=None, specimen_ids=None, input_scope="part_reslice"):
        wb = self.workbench
        wb._tif_backend_action = str(action or "")
        wb._tif_backend_started_mono = time.monotonic()
        wb._tif_backend_run_dir = ""
        wb._tif_backend_result_json = ""
        wb._tif_backend_last_result = None
        wb._tif_backend_progress_value = 0
        wb.backend_progress_bar.setRange(0, 100)
        wb.backend_progress_bar.setValue(0)
        wb.backend_progress_bar.setFormat("%p%")
        wb.backend_log_tail.clear()
        if action == "train":
            self._set_training_result_summary(None)
        status = tt("Running {0}...", wb.lang).format(action)
        if str(input_scope or "") == "top_level_volume":
            detail = tt("{0} {1} top-level volume(s).", wb.lang).format(status, len(specimen_ids or []))
        else:
            detail = tt("{0} {1} part sample(s).", wb.lang).format(status, len(part_refs or []))
        wb.backend_run_status_label.setText(detail)
        wb.training_status_label.setText(detail)
        wb.backend_elapsed_label.setText(tt("Elapsed: {0}", wb.lang).format("00:00"))
        wb.backend_elapsed_timer.start()
        self.set_backend_controls_running(True)
        wb._set_backend_write_locked_controls(True)
        wb._sync_undo_redo_buttons()
        wb.log(detail)

    def _backend_failure_summary(self, text, action=None):
        wb = self.workbench
        raw = str(text or "")
        lower = raw.lower()
        action_text = str(action or wb._tif_backend_action or "").strip() or tt("backend task", wb.lang)
        if "_cancelled" in lower:
            return tt("Run cancelled: {0}", wb.lang).format(action_text)
        if "nnunet_training_requires_at_least_2_samples" in lower:
            count = "0"
            marker = "nnunet_training_requires_at_least_2_samples:"
            tail = raw.split(marker, 1)[1] if marker in raw else ""
            if tail:
                count = tail.split()[0].split(":")[0].strip() or "0"
            return tt("Training needs at least 2 accepted training samples; current selection has {0}.", wb.lang).format(count)
        if "nnunet_command_not_found" in lower:
            return tt("nnU-Net command was not found in the selected backend Python environment.", wb.lang)
        if "nnunet_command_failed" in lower:
            return tt("nnU-Net command failed. Open the run folder and check nnunet_v2_commands.log.", wb.lang)
        if "tif_backend_train_failed" in lower:
            return tt("Training failed. Details are kept in the backend log and run folder.", wb.lang)
        if "tif_backend_prepare_dataset_failed" in lower:
            return tt("Dataset preparation failed. Details are kept in the backend log and run folder.", wb.lang)
        if "tif_backend_predict_failed" in lower:
            return tt("Prediction failed. Details are kept in the backend log and run folder.", wb.lang)
        return tt("Run failed: {0}", wb.lang).format(action_text)

    def _backend_failure_dialog_text(self, summary, detail):
        wb = self.workbench
        lines = [str(summary or tt("Run failed.", wb.lang))]
        run_dir = str(wb._tif_backend_run_dir or "").strip()
        result_json = str(wb._tif_backend_result_json or "").strip()
        if run_dir:
            lines.append(f"{tt('Run folder', wb.lang)}: {run_dir}")
        if result_json:
            lines.append(f"{tt('Result JSON', wb.lang)}: {result_json}")
        detail = str(detail or "").strip()
        if detail and len(detail) < 320:
            lines.append(detail)
        return "\n".join(lines)

    def _on_tif_backend_finished(self, result):
        wb = self.workbench
        result = result if isinstance(result, dict) else {}
        task_id = wb._tif_backend_task_id
        task_current = wb._task_context_matches_current(task_id, fields=("specimen_id", "volume_scope", "part_id", "reslice_id"))
        wb._tif_backend_last_result = result
        wb._tif_backend_run_dir = str(result.get("run_dir") or "")
        backend_result = result.get("result") if isinstance(result.get("result"), dict) else {}
        wb._tif_backend_result_json = str(((result.get("contract") or {}).get("result_json")) or backend_result.get("_result_json") or "")
        wb._tif_backend_progress_value = 100
        wb.backend_progress_bar.setRange(0, 100)
        wb.backend_progress_bar.setValue(100)
        wb.backend_progress_bar.setFormat("%p%")
        action = str(result.get("contract", {}).get("action") or wb._tif_backend_action or "")
        message = tt("Run finished: {0}\nRun: {1}", wb.lang).format(action, wb._tif_backend_run_dir)
        wb.backend_run_status_label.setText(message)
        if task_current:
            wb.training_status_label.setText(message)
        wb.log(message)
        pending = dict(wb._tif_backend_pending_selection or {})
        wb._finish_tif_task(task_id, payload=result, message="backend_action_finished")
        self._cleanup_tif_backend_thread()
        wb.refresh_project(reload_current=False)
        if action == "train":
            backend_result = result.get("result") if isinstance(result.get("result"), dict) else result
            result_json = str((backend_result or {}).get("_result_json") or wb._tif_backend_result_json or "")
            summary = summarize_tif_training_result(backend_result, result_json=result_json, run_dir=wb._tif_backend_run_dir)
            model_record = self._register_training_summary_model(summary, backend_result, result.get("contract", {}))
            self._set_training_result_summary(summary)
            self.populate_model_library_combo(self.model_record_id(model_record) if model_record else None)
            self.show_latest_training_result_summary(show_message=False)
        if action == "predict" and task_current and pending.get("specimen_id") and pending.get("input_scope") == "top_level_volume":
            wb.selection_workflow_controller.select_payload(
                {"specimen_id": pending.get("specimen_id", ""), "scope": "full"}
            )
            index = wb.label_role_combo.findData("working_edit")
            if index >= 0:
                wb.label_role_combo.setCurrentIndex(index)
            if hasattr(wb, "task_tabs") and hasattr(wb, "training_mode_tabs"):
                wb.task_tabs.setCurrentWidget(wb.training_mode_tabs)
                wb.training_mode_tabs.setCurrentWidget(wb.annotation_task_page)
        elif action == "predict" and task_current and pending.get("specimen_id") and pending.get("part_id"):
            wb.selection_workflow_controller.select_payload(
                {
                    "specimen_id": pending.get("specimen_id", ""),
                    "scope": "part_reslice" if pending.get("reslice_id") else "part",
                    "part_id": pending.get("part_id", ""),
                    "reslice_id": pending.get("reslice_id", ""),
                }
            )
            index = wb.label_role_combo.findData("editable_ai_result")
            if index >= 0:
                wb.label_role_combo.setCurrentIndex(index)
            if hasattr(wb, "task_tabs") and hasattr(wb, "training_mode_tabs"):
                wb.task_tabs.setCurrentWidget(wb.training_mode_tabs)
                wb.training_mode_tabs.setCurrentWidget(wb.annotation_task_page)
        if action == "predict":
            self.refresh_predict_targets()
        wb._tif_backend_pending_selection = {}
        wb._tif_backend_task_id = ""

    def _on_tif_backend_failed(self, message, context=None):
        wb = self.workbench
        text = str(message or "")
        context = context if isinstance(context, dict) else {}
        task_id = wb._tif_backend_task_id
        task_current = (
            bool(task_id)
            and wb._task_context_matches_current(
                task_id,
                fields=("specimen_id", "volume_scope", "part_id", "reslice_id"),
            )
        ) or (not task_id and self.action_running())
        wb._tif_backend_run_dir = str(context.get("run_dir") or wb._tif_backend_run_dir or "")
        wb._tif_backend_result_json = str(context.get("result_json") or wb._tif_backend_result_json or "")
        action = wb._tif_backend_action
        status = self._backend_failure_summary(text, action=action)
        wb._tif_backend_progress_value = 0
        wb.backend_progress_bar.setRange(0, 100)
        wb.backend_progress_bar.setValue(0)
        wb.backend_progress_bar.setFormat("%p%")
        wb.backend_run_status_label.setText(status)
        if task_current:
            wb.training_status_label.setText(status)
        detail_lines = text.splitlines()
        detail_tail = "\n".join(detail_lines[-12:]) if detail_lines else text
        wb.backend_log_tail.setPlainText(detail_tail)
        wb.backend_log_tail.setToolTip(text)
        wb.log(status)
        wb._tif_backend_pending_selection = {}
        task = wb.task_manager.task(task_id)
        if task is not None and task.status == "cancelled":
            wb._cancel_tif_task(task_id, task.error or status)
        else:
            wb._fail_tif_task(task_id, text, payload=context, message=status)
        self._cleanup_tif_backend_thread()
        wb._tif_backend_task_id = ""
        if "_cancelled" not in text:
            QMessageBox.warning(wb, tt("TIF backend", wb.lang), self._backend_failure_dialog_text(status, text))

    def cancel_backend_action(self):
        wb = self.workbench
        if not self.action_running() or wb._tif_backend_worker is None:
            return
        action = wb._tif_backend_action
        wb._tif_backend_worker.cancel()
        message = tt("Cancelling {0}...", wb.lang).format(action)
        wb.backend_run_status_label.setText(message)
        wb.training_status_label.setText(message)
        wb.log(message)
        wb._cancel_tif_task(wb._tif_backend_task_id, message)

    def open_latest_backend_run_folder(self):
        wb = self.workbench
        path = str(wb._tif_backend_run_dir or "")
        if not path or not os.path.isdir(path):
            QMessageBox.information(wb, tt("TIF backend", wb.lang), tt("No backend run folder is available yet.", wb.lang))
            return False
        return QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def open_latest_backend_result_json(self):
        wb = self.workbench
        path = str(wb._tif_backend_result_json or "")
        if not path or not os.path.exists(path):
            QMessageBox.information(wb, tt("TIF backend", wb.lang), tt("No backend result JSON is available yet.", wb.lang))
            return False
        return QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _queue_backend_action_after_save(self, action, selection):
        wb = self.workbench
        wb._pending_backend_action_after_save = {
            "action": str(action or ""),
            "selection": {
                "part_refs": [dict(ref or {}) for ref in (selection or {}).get("part_refs", [])],
                "specimen_ids": [str(item) for item in (selection or {}).get("specimen_ids", [])],
                "input_scope": str((selection or {}).get("input_scope") or "part_reslice"),
            },
        }

    def _resume_pending_backend_action_after_save(self):
        wb = self.workbench
        pending = wb._pending_backend_action_after_save
        if not pending:
            return False
        if wb.working_edit_dirty:
            wb._set_operation_feedback(tt("Save finished with remaining unsaved labels. Backend run was not started.", wb.lang))
            wb._pending_backend_action_after_save = None
            return False
        wb._pending_backend_action_after_save = None
        self._start_backend_action_with_selection(pending.get("action", ""), pending.get("selection") or {})
        return True

    def _confirm_or_queue_save_before_backend_action(self, action, selection):
        wb = self.workbench
        if not wb.working_edit_dirty and not wb.annotation_workflow_controller.auto_save_thread is not None and not wb.annotation_workflow_controller.manual_save_thread is not None:
            return True
        if wb.annotation_workflow_controller.manual_save_thread is not None:
            self._queue_backend_action_after_save(action, selection)
            wb._set_operation_feedback(tt("Label save is running. Backend run will start after saving finishes.", wb.lang))
            return False
        if not wb.working_edit_dirty and wb.annotation_workflow_controller.auto_save_thread is not None:
            self._queue_backend_action_after_save(action, selection)
            wb._set_operation_feedback(tt("Finishing auto-save before backend run...", wb.lang))
            return False

        title = tt("Unsaved editable AI result", wb.lang) if wb.current_volume_scope == "part" else tt("Unsaved current labels", wb.lang)
        prompt = (
            tt("Save changes to the current editable AI result before continuing?", wb.lang)
            if wb.current_volume_scope == "part"
            else tt("Save changes to the current labels before continuing?", wb.lang)
        )
        reply = QMessageBox.question(
            wb,
            title,
            prompt,
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )
        if reply == QMessageBox.Cancel:
            return False
        if reply == QMessageBox.Discard:
            wb.annotation_workflow_controller.reset_dirty_tracking()
            wb._update_save_status()
            if wb.current_specimen_id:
                wb._load_edit_volume()
            return True

        self._queue_backend_action_after_save(action, selection)
        if not wb.save_working_edit_async(show_message=True):
            wb._pending_backend_action_after_save = None
        return False

    def _start_backend_action_with_selection(self, action, selection):
        wb = self.workbench
        part_refs = selection.get("part_refs") or []
        specimen_ids = selection.get("specimen_ids") or []
        input_scope = selection.get("input_scope") or "part_reslice"
        if self.action_running():
            QMessageBox.information(wb, tt("TIF backend", wb.lang), tt("Backend task is already running.", wb.lang))
            return
        wb._tif_backend_pending_selection = {
            "specimen_id": wb.current_specimen_id,
            "part_id": wb.current_part_id,
            "reslice_id": wb.current_reslice_id,
            "input_scope": input_scope,
        }
        self._start_backend_status(action, part_refs=part_refs, specimen_ids=specimen_ids, input_scope=input_scope)
        task = wb._start_tif_task(
            "backend_action",
            action=action,
            payload={
                "input_scope": input_scope,
                "part_ref_count": len(part_refs or []),
                "specimen_count": len(specimen_ids or []),
                "pending_selection": dict(wb._tif_backend_pending_selection or {}),
            },
            request_key=wb._task_request_key((action, input_scope, part_refs or specimen_ids)),
            message=tt("Backend run is active. Stop it or wait until it finishes before editing project data.", wb.lang),
        )
        wb._tif_backend_task_id = task.task_id
        wb._tif_backend_thread = QThread(wb)
        wb._tif_backend_worker = TifBackendActionWorker(
            wb.project,
            wb.backend_config,
            action,
            part_refs=part_refs,
            specimen_ids=specimen_ids,
            input_scope=input_scope,
            model_manifest=wb.backend_config.get("model_manifest", ""),
        )
        wb._tif_backend_worker.moveToThread(wb._tif_backend_thread)
        wb._tif_backend_thread.started.connect(wb._tif_backend_worker.run)
        wb._tif_backend_worker.progress.connect(self.on_backend_progress)
        wb._tif_backend_worker.finished.connect(self._on_tif_backend_finished)
        wb._tif_backend_worker.failed.connect(self._on_tif_backend_failed)
        wb._tif_backend_worker.finished.connect(wb._tif_backend_thread.quit)
        wb._tif_backend_worker.failed.connect(wb._tif_backend_thread.quit)
        wb._tif_backend_thread.finished.connect(wb._tif_backend_worker.deleteLater)
        wb._tif_backend_thread.finished.connect(self._on_tif_backend_thread_finished)
        wb._tif_backend_thread.finished.connect(wb._tif_backend_thread.deleteLater)
        wb._tif_backend_thread.start()

    def run_backend_action(self, action):
        wb = self.workbench
        if not wb._ensure_tif_project_open():
            return
        if self.action_running():
            QMessageBox.information(wb, tt("TIF backend", wb.lang), tt("Backend task is already running.", wb.lang))
            return
        wb.backend_config = wb._backend_config_from_ui()
        if wb.config_manager is not None:
            wb.config_manager.set("tif_backend", dict(wb.backend_config))
            wb.config_manager.save()
        command_key = {
            "prepare_dataset": "prepare_dataset_command",
            "train": "train_command",
            "predict": "predict_command",
        }.get(action, "")
        if command_key and not wb.backend_config.get(command_key, "").strip():
            QMessageBox.warning(wb, tt("TIF backend", wb.lang), tt("No command configured for this backend action.", wb.lang))
            return
        if action == "predict":
            try:
                self._validated_predict_model_manifest()
            except Exception as exc:
                message = tt("Action failed: {0}", wb.lang).format(str(exc))
                wb.training_status_label.setText(message)
                wb.log(message)
                QMessageBox.warning(wb, tt("TIF backend", wb.lang), str(exc))
                return
        try:
            selection = self.selected_backend_samples_for_action(action)
        except Exception as exc:
            message = tt("Action failed: {0}", wb.lang).format(str(exc))
            wb.training_status_label.setText(message)
            wb.log(message)
            QMessageBox.warning(wb, tt("TIF backend", wb.lang), str(exc))
            return
        part_refs = selection.get("part_refs") or []
        specimen_ids = selection.get("specimen_ids") or []
        input_scope = selection.get("input_scope") or "part_reslice"
        if action == "predict" and not self._confirm_predict_overwrite_if_needed(part_refs=part_refs, specimen_ids=specimen_ids, input_scope=input_scope):
            return
        if not self._confirm_or_queue_save_before_backend_action(action, selection):
            return
        self._start_backend_action_with_selection(action, selection)

    def _format_train_ready_reasons(self, reasons):
        wb = self.workbench
        labels = {
            "manual_truth_missing": "Training truth is missing; accept the current editable labels as training truth first.",
            "part_not_marked_train_ready": "Part has not been marked as verified train-ready.",
            "part_record_missing": "Part record is missing.",
            "part_volume_missing": "Part image is missing.",
            "reslice_record_missing": "Reslice record is missing.",
            "reslice_output_missing": "Reslice image is missing.",
            "label_schema_missing": "Label schema is missing or empty.",
            "part_label_shape_mismatch": "Part label shape does not match the part/reslice image.",
            "unknown_label_ids": "Label IDs are not all defined in the bound label schema.",
            "label_volume_unreadable": "Label volume cannot be read.",
            "specimen_not_marked_train_ready": "Specimen has not been marked train-ready.",
            "working_volume_missing": "Working image is missing.",
            "material_map_missing": "Material map is missing.",
            "image_label_shape_mismatch": "Image and label shapes do not match.",
            "no_trainable_material": "No trainable material is defined in the material map.",
        }
        readable = []
        for reason in reasons or []:
            text = str(reason or "").strip()
            if not text:
                continue
            key = text.split(":", 1)[0]
            label = tt(labels.get(key, text), wb.lang)
            if ":" in text and key in labels:
                label = f"{label} ({text.split(':', 1)[1]})"
            readable.append(label)
        return readable

    def _part_training_readiness_reports(self, prefer_current=False, limit=4):
        wb = self.workbench
        reports = []
        if prefer_current and wb.current_specimen_id and wb.current_part_id:
            try:
                readiness = wb.project.evaluate_part_train_ready(
                    wb.current_specimen_id,
                    wb.current_part_id,
                    wb.current_reslice_id,
                    validate_label_ids=False,
                )
            except Exception as exc:
                readiness = {
                    "specimen_id": wb.current_specimen_id,
                    "part_id": wb.current_part_id,
                    "reslice_id": wb.current_reslice_id,
                    "train_ready": False,
                    "reasons": [str(exc)],
                }
            reports.append(readiness)
            return reports
        for specimen in wb.project.project_data.get("specimens", []) or []:
            if not isinstance(specimen, dict):
                continue
            specimen_id = str(specimen.get("specimen_id") or "")
            for part in specimen.get("parts", []) or []:
                if not isinstance(part, dict):
                    continue
                part_id = str(part.get("part_id") or "")
                if not specimen_id or not part_id:
                    continue
                try:
                    readiness = wb.project.evaluate_part_train_ready(specimen_id, part_id, validate_label_ids=False)
                except Exception as exc:
                    readiness = {
                        "specimen_id": specimen_id,
                        "part_id": part_id,
                        "reslice_id": "",
                        "train_ready": False,
                        "reasons": [str(exc)],
                    }
                reports.append(readiness)
                if len(reports) >= int(limit):
                    return reports
        return reports

    def _top_level_training_readiness_reports(self, limit=4):
        wb = self.workbench
        reports = []
        for specimen in wb.project.project_data.get("specimens", []) or []:
            if not isinstance(specimen, dict):
                continue
            specimen_id = str(specimen.get("specimen_id") or "")
            if not specimen_id:
                continue
            try:
                readiness = wb.project.evaluate_train_ready(specimen_id)
            except Exception as exc:
                readiness = {
                    "specimen_id": specimen_id,
                    "train_ready": False,
                    "reasons": [str(exc)],
                }
            reports.append(readiness)
            if len(reports) >= int(limit):
                break
        return reports

    def _summarize_training_readiness_reports(self, title, reports, empty_message, all_ready_message, scope, limit=4):
        wb = self.workbench
        lines = [tt(title, wb.lang)]
        if not reports:
            lines.append(f"- {tt(empty_message, wb.lang)}")
            return lines
        blocked_count = 0
        for report in reports[: int(limit)]:
            if report.get("train_ready"):
                continue
            blocked_count += 1
            if scope == "part":
                label = self.format_part_ref_label(report) or "-"
            else:
                label = str(report.get("specimen_id") or "-")
            reasons = self._format_train_ready_reasons(report.get("reasons") or [])
            detail = "; ".join(reasons) if reasons else "-"
            lines.append(f"- {label}: {tt('Missing: {0}', wb.lang).format(detail)}")
        if blocked_count == 0:
            lines.append(f"- {tt(all_ready_message, wb.lang)}")
        remaining = max(0, len(reports) - int(limit))
        if remaining:
            lines.append(f"- {tt('+{0} more', wb.lang).format(remaining)}")
        return lines

    def _training_reports_need_truth_acceptance(self, reports):
        wb = self.workbench
        for report in reports or []:
            reasons = {str(item).split(":", 1)[0] for item in (report.get("reasons") or [])}
            if reasons.intersection({"manual_truth_missing", "part_not_marked_train_ready"}):
                return True
        return False

    def _training_selection_error(self, prefer_part=False):
        wb = self.workbench
        if prefer_part:
            part_reports = self._part_training_readiness_reports(prefer_current=True, limit=4)
            lines = [tt("Current part/reslice is not train-ready yet.", wb.lang), ""]
            lines.extend(
                self._summarize_training_readiness_reports(
                    "Part readiness",
                    part_reports,
                    "No project part volumes are available.",
                    "All checked part samples are train-ready.",
                    "part",
                )
            )
            if self._training_reports_need_truth_acceptance(part_reports):
                lines.extend(["", tt("Next step: save current labels, then click Accept as training truth in Label review. Training uses reviewed manual_truth only; editable labels are not sent to training directly.", wb.lang)])
            return "\n".join(lines)
        part_reports = self._part_training_readiness_reports(prefer_current=False, limit=4)
        top_reports = self._top_level_training_readiness_reports(limit=4)
        lines = [tt("No train-ready samples are available for training.", wb.lang), ""]
        lines.extend(
            self._summarize_training_readiness_reports(
                "Part readiness",
                part_reports,
                "No project part volumes are available.",
                "All checked part samples are train-ready.",
                "part",
            )
        )
        lines.append("")
        lines.extend(
            self._summarize_training_readiness_reports(
                "Top-level readiness",
                top_reports,
                "No top-level volume records are available.",
                "All checked top-level volumes are train-ready.",
                "top",
            )
        )
        if self._training_reports_need_truth_acceptance(part_reports):
            lines.extend(["", tt("Next step: save current labels, then click Accept as training truth in Label review. Training uses reviewed manual_truth only; editable labels are not sent to training directly.", wb.lang)])
        return "\n".join(lines)
