from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from PySide6.QtCore import QEventLoop, QObject, Qt
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox, QTableWidgetItem

try:
    from AntSleap.core.tif_prediction_import import default_prediction_id_for_tif, import_external_prediction_tif
    from AntSleap.core.tif_volume_io import load_volume_sidecar, volume_sidecar_exists
    from AntSleap.ui.tif_workbench_translations import tt
except ModuleNotFoundError as exc:
    if exc.name != "AntSleap":
        raise
    from core.tif_prediction_import import default_prediction_id_for_tif, import_external_prediction_tif
    from core.tif_volume_io import load_volume_sidecar, volume_sidecar_exists
    from ui.tif_workbench_translations import tt


@dataclass
class TifResultReviewState:
    refreshing: bool = False
    stale: bool = True
    opening_target: bool = False
    region_mask_cache: dict = field(default_factory=dict)
    region_mask_cache_key: object = None


class TifResultReviewController(QObject):
    VIEW_SCOPE = "result_review"

    def __init__(self, workbench):
        super().__init__(workbench)
        self.workbench = workbench
        self.state = TifResultReviewState()

    def bind_signals(self):
        wb = self.workbench
        view = wb.workbench_view
        names = ("btn_accept_selected_ai_results", "btn_import_external_prediction_tif", "result_region_combo", "btn_refresh_result_comparison", "btn_open_result_comparison_target", "btn_show_result_region_in_3d", "result_source_manual_radio", "result_source_editable_radio", "training_mode_tabs")
        view.register_scope(self.VIEW_SCOPE, *names)
        bindings = (
            ("accept", "btn_accept_selected_ai_results", "clicked", self.accept_selected_results),
            ("import_external", "btn_import_external_prediction_tif", "clicked", self.import_external_prediction_dialog),
            ("region", "result_region_combo", "currentIndexChanged", self.on_result_comparison_controls_changed),
            ("refresh", "btn_refresh_result_comparison", "clicked", self.refresh_comparison),
            ("open", "btn_open_result_comparison_target", "clicked", self.open_selected_target),
            ("show_region", "btn_show_result_region_in_3d", "clicked", self.show_selected_region_in_3d),
            ("source_manual", "result_source_manual_radio", "toggled", self.on_result_comparison_controls_changed),
            ("source_editable", "result_source_editable_radio", "toggled", self.on_result_comparison_controls_changed),
            ("training_tab", "training_mode_tabs", "currentChanged", self.on_training_mode_tab_changed),
        )
        for key, widget_name, signal_name, slot in bindings:
            signal = getattr(view.require(self.VIEW_SCOPE, widget_name), signal_name)
            wb.signal_router.bind(self.VIEW_SCOPE, key, signal, slot)

    def result_source_role(self):
        wb = self.workbench
        if getattr(wb, "result_source_editable_radio", None) is not None and wb.result_source_editable_radio.isChecked():
            return "editable_ai_result"
        return "manual_truth"


    def result_region_id(self):
        wb = self.workbench
        combo = getattr(wb, "result_region_combo", None)
        if combo is None or not combo.count():
            return 0
        try:
            return int(combo.currentData() or 0)
        except (TypeError, ValueError):
            return 0


    def result_region_name(self):
        wb = self.workbench
        combo = getattr(wb, "result_region_combo", None)
        if combo is None or not combo.count():
            return tt("All", wb.lang)
        text = str(combo.currentText() or "").strip()
        if "·" in text:
            text = text.split("·", 1)[1].strip()
        return text or tt("All", wb.lang)


    def result_comparison_tab_is_active(self):
        wb = self.workbench
        return bool(
            hasattr(wb, "task_tabs")
            and hasattr(wb, "training_mode_tabs")
            and hasattr(wb, "result_compare_page")
            and wb.task_tabs.currentWidget() is wb.training_mode_tabs
            and wb.training_mode_tabs.currentWidget() is wb.result_compare_page
        )


    def mark_result_comparison_stale(self):
        wb = self.workbench
        self.state.stale = True
        if hasattr(wb, "result_compare_summary_label") and not self.result_comparison_tab_is_active():
            wb.result_compare_summary_label.setText(tt("Result comparison will refresh when opened.", wb.lang))


    def refresh_result_comparison_if_visible(self):
        wb = self.workbench
        if self.result_comparison_tab_is_active():
            self.refresh_comparison()
        else:
            self.mark_result_comparison_stale()


    def part_comparison_name(self, part):
        wb = self.workbench
        training = (part or {}).get("training") or {}
        return str(
            training.get("user_defined_part_name")
            or (part or {}).get("display_name")
            or (part or {}).get("part_id")
            or ""
        ).strip()


    def active_comparison_part_name(self):
        wb = self.workbench
        if wb.current_volume_scope == "part" and isinstance(wb.current_part, dict):
            return self.part_comparison_name(wb.current_part)
        return ""


    def preferred_result_reslice_id(self, specimen_id, part):
        wb = self.workbench
        training = (part or {}).get("training") or {}
        active_reslice_id = str(training.get("active_reslice_id") or "").strip()
        part_id = str((part or {}).get("part_id") or "")
        if active_reslice_id:
            try:
                if wb.project.get_part_reslice(specimen_id, part_id, active_reslice_id, default=None) is not None:
                    return active_reslice_id
            except Exception:
                return active_reslice_id
        reslices = []
        try:
            reslices = wb.project.list_part_reslices(specimen_id, part_id)
        except Exception:
            reslices = ((part or {}).get("metadata") or {}).get("local_axis_reslices", []) or []
        if reslices:
            return str((reslices[-1] or {}).get("reslice_id") or "")
        return ""


    def label_volume_counts_for_result(self, record, region_id):
        wb = self.workbench
        path = wb.project.to_absolute((record or {}).get("path", ""))
        if not path:
            return {"ok": False, "status": tt("Label path missing", wb.lang), "path": ""}
        if not volume_sidecar_exists(path):
            return {"ok": False, "status": tt("Label file missing", wb.lang), "path": path}
        try:
            volume = load_volume_sidecar(path, mmap_mode="r")
            shape = tuple(int(value) for value in getattr(volume, "shape", ()) or ())
            if len(shape) != 3 or min(shape) <= 0:
                return {"ok": False, "status": tt("Label read failed: {0}", wb.lang).format("empty_or_non_3d"), "path": path}
            total_labeled = 0
            region_voxels = 0
            plane_values = max(1, int(np.prod(shape[1:])))
            z_chunk = max(1, min(int(shape[0]), int((32 * 1024 * 1024) / (plane_values * max(1, np.dtype(getattr(volume, "dtype", np.uint16)).itemsize)))))
            for z0 in range(0, int(shape[0]), z_chunk):
                z1 = min(int(shape[0]), z0 + z_chunk)
                chunk = np.asarray(volume[z0:z1])
                total_labeled += int(np.count_nonzero(chunk))
                if int(region_id) > 0:
                    region_voxels += int(np.count_nonzero(chunk == int(region_id)))
                else:
                    region_voxels += int(np.count_nonzero(chunk))
            percent = (float(region_voxels) / float(total_labeled) * 100.0) if total_labeled else 0.0
            return {
                "ok": True,
                "status": str((record or {}).get("status") or "available"),
                "path": path,
                "shape": shape,
                "region_voxels": region_voxels,
                "total_labeled_voxels": total_labeled,
                "percent": percent,
            }
        except Exception as exc:
            return {"ok": False, "status": tt("Label read failed: {0}", wb.lang).format(str(exc)), "path": path}


    def result_comparison_rows(self):
        wb = self.workbench
        source_role = self.result_source_role()
        region_id = self.result_region_id()
        active_part_name = self.active_comparison_part_name()
        rows = []
        for specimen in wb.project.project_data.get("specimens", []) or []:
            if not isinstance(specimen, dict):
                continue
            specimen_id = str(specimen.get("specimen_id") or "")
            if not specimen_id:
                continue
            specimen_label = str(specimen.get("display_name") or specimen_id)
            for part in specimen.get("parts", []) or []:
                if not isinstance(part, dict):
                    continue
                part_id = str(part.get("part_id") or "")
                if not part_id:
                    continue
                part_name = self.part_comparison_name(part)
                if active_part_name and part_name and part_name != active_part_name:
                    continue
                labels = part.get("labels") or {}
                record = labels.get(source_role) or {}
                ref = {
                    "specimen_id": specimen_id,
                    "part_id": part_id,
                    "reslice_id": self.preferred_result_reslice_id(specimen_id, part),
                }
                counts = self.label_volume_counts_for_result(record, region_id) if record and str(record.get("path") or "").strip() else {
                    "ok": False,
                    "status": tt("Missing {0}", wb.lang).format(source_role),
                    "path": "",
                }
                rows.append(
                    {
                        "ref": ref,
                        "specimen_label": specimen_label,
                        "part_label": part_name or part_id,
                        "part_id": part_id,
                        "reslice_id": ref["reslice_id"],
                        "source_role": source_role,
                        "source_status": counts.get("status", ""),
                        "ok": bool(counts.get("ok")),
                        "label_path": counts.get("path", ""),
                        "shape": tuple(counts.get("shape") or (record.get("shape_zyx") or [])),
                        "region_voxels": int(counts.get("region_voxels") or 0),
                        "total_labeled_voxels": int(counts.get("total_labeled_voxels") or 0),
                        "percent": float(counts.get("percent") or 0.0),
                    }
                )
        return rows


    def make_result_table_item(self, text):
        wb = self.workbench
        item = QTableWidgetItem(str(text or ""))
        item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        return item


    def format_result_shape(self, shape):
        wb = self.workbench
        try:
            values = tuple(int(value) for value in shape)
        except (TypeError, ValueError):
            values = ()
        if len(values) != 3 or min(values) <= 0:
            return "-"
        return " / ".join(str(value) for value in values)


    def update_result_comparison_summary(self, rows):
        wb = self.workbench
        rows = list(rows or [])
        total = len(rows)
        ok_rows = [row for row in rows if row.get("ok")]
        region_voxels = sum(int(row.get("region_voxels") or 0) for row in ok_rows)
        labeled_voxels = sum(int(row.get("total_labeled_voxels") or 0) for row in ok_rows)
        percent = (float(region_voxels) / float(labeled_voxels) * 100.0) if labeled_voxels else 0.0
        part_name = self.active_comparison_part_name() or tt("All comparable parts", wb.lang)
        text = tt(
            "Listed {0} {1} part result(s); {2} have {3}. Region voxels: {4} / labeled voxels: {5} ({6}%).",
            wb.lang,
        ).format(
            total,
            part_name,
            len(ok_rows),
            self.result_source_role(),
            wb._format_count(region_voxels),
            wb._format_count(labeled_voxels),
            f"{percent:.2f}",
        )
        if total == 0:
            text = tt("No comparable part is selected yet. Select a part volume or use all parts.", wb.lang)
        wb.result_compare_summary_label.setText(text)


    def refresh_comparison(self):
        wb = self.workbench
        if not hasattr(wb, "result_compare_table"):
            return []
        self.state.stale = False
        rows = self.result_comparison_rows()
        table = wb.result_compare_table
        self.state.refreshing = True
        try:
            table.blockSignals(True)
            table.setRowCount(0)
            table.setColumnCount(8)
            table.setHorizontalHeaderLabels(
                [
                    tt("Specimen", wb.lang),
                    tt("Part", wb.lang),
                    tt("Reslice", wb.lang),
                    tt("Region voxels", wb.lang),
                    tt("Labeled voxels", wb.lang),
                    tt("Region %", wb.lang),
                    tt("Source status", wb.lang),
                    tt("Shape Z/Y/X", wb.lang),
                ]
            )
            for row_index, row in enumerate(rows):
                table.insertRow(row_index)
                first_item = self.make_result_table_item(row["specimen_label"])
                first_item.setData(Qt.UserRole, dict(row))
                table.setItem(row_index, 0, first_item)
                table.setItem(row_index, 1, self.make_result_table_item(f"{row['part_label']} ({row['part_id']})"))
                table.setItem(row_index, 2, self.make_result_table_item(row.get("reslice_id") or "-"))
                table.setItem(row_index, 3, self.make_result_table_item(wb._format_count(row.get("region_voxels"))))
                table.setItem(row_index, 4, self.make_result_table_item(wb._format_count(row.get("total_labeled_voxels"))))
                table.setItem(row_index, 5, self.make_result_table_item(f"{float(row.get('percent') or 0.0):.2f}"))
                table.setItem(row_index, 6, self.make_result_table_item(row.get("source_status") or "-"))
                table.setItem(row_index, 7, self.make_result_table_item(self.format_result_shape(row.get("shape"))))
            table.resizeColumnsToContents()
            if rows and not table.selectedItems():
                table.selectRow(0)
        finally:
            table.blockSignals(False)
            self.state.refreshing = False
        self.update_result_comparison_summary(rows)
        self.sync_result_comparison_controls()
        return rows


    def selected_result_comparison_row(self):
        wb = self.workbench
        table = getattr(wb, "result_compare_table", None)
        if table is None:
            return {}
        selected = table.selectedItems()
        row_index = selected[0].row() if selected else table.currentRow()
        if row_index < 0:
            return {}
        item = table.item(row_index, 0)
        if item is None:
            return {}
        row = item.data(Qt.UserRole)
        return dict(row or {}) if isinstance(row, dict) else {}


    def set_label_role_if_available(self, role):
        wb = self.workbench
        if not hasattr(wb, "label_role_combo"):
            return False
        index = wb.label_role_combo.findData(role)
        if index < 0:
            return False
        if index == wb.label_role_combo.currentIndex():
            wb._reload_label_volume()
            return True
        wb.label_role_combo.setCurrentIndex(index)
        return True


    def open_selected_target(self):
        wb = self.workbench
        if self.state.opening_target:
            return False
        row = self.selected_result_comparison_row()
        ref = row.get("ref") or {}
        specimen_id = str(ref.get("specimen_id") or "")
        part_id = str(ref.get("part_id") or "")
        reslice_id = str(ref.get("reslice_id") or "")
        if not specimen_id or not part_id:
            wb._set_operation_feedback(tt("Select a result row before opening the 3D preview.", wb.lang))
            return False
        scope = "part_reslice" if reslice_id else "part"
        start_message = tt("Opening selected result in 3D...", wb.lang)
        wb._set_operation_feedback(start_message)
        if hasattr(wb, "display_mode_combo"):
            wb.on_display_mode_changed("volume")
        wb.volume_render_controller._set_volume_canvas_status_text(start_message, replace_existing=True)
        wb.volume_render_controller._update_volume_render_status_label(start_message)
        if hasattr(wb, "btn_open_result_comparison_target"):
            wb.btn_open_result_comparison_target.setEnabled(False)
        QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)
        self.state.opening_target = True
        try:
            selection_result = wb.selection_workflow_controller.select_payload(
                {
                    "specimen_id": specimen_id,
                    "scope": scope,
                    "part_id": part_id,
                    "reslice_id": reslice_id,
                }
            )
            if not selection_result:
                wb._set_operation_feedback(tt("Select a result row before opening the 3D preview.", wb.lang))
                return False
            self.set_label_role_if_available(self.result_source_role())
            wb.on_display_mode_changed("volume")
            self.invalidate_result_region_mask_cache(clear_active_mask_preview=True)
            wb.volume_render_controller._reset_active_volume_preview_state()
            if hasattr(wb, "task_tabs") and hasattr(wb, "training_mode_tabs"):
                wb.task_tabs.setCurrentWidget(wb.training_mode_tabs)
                wb.training_mode_tabs.setCurrentWidget(wb.result_compare_page)
            if self.result_region_id() > 0 and bool(row.get("ok")):
                wb._set_volume_mask_mode("masked_image")
            elif row and not bool(row.get("ok")):
                wb._set_volume_mask_mode("image_only")
            wb._set_scope_controls_enabled()
            wb.volume_render_controller.render_volume_preview()
            message = tt("Opened {0} / {1} for 3D region comparison.", wb.lang).format(specimen_id, part_id)
            wb._set_operation_feedback(message)
            return True
        finally:
            self.state.opening_target = False
            self.sync_result_comparison_controls()


    def show_selected_region_in_3d(self):
        wb = self.workbench
        if self.result_region_id() <= 0:
            wb._set_operation_feedback(tt("Region highlight requires a specific region label.", wb.lang))
            return False
        row = self.selected_result_comparison_row()
        ref = row.get("ref") or {}
        selected_key = (
            str(ref.get("specimen_id") or ""),
            str(ref.get("part_id") or ""),
            str(ref.get("reslice_id") or ""),
        )
        current_key = (
            str(wb.current_specimen_id or ""),
            str(wb.current_part_id or ""),
            str(wb.current_reslice_id or ""),
        )
        if wb.current_volume_scope != "part" or wb.image_volume is None or (selected_key[0] and selected_key != current_key):
            if not self.open_selected_target():
                return False
        self.set_label_role_if_available(self.result_source_role())
        message = tt("Preparing mask preview...", wb.lang)
        wb._set_operation_feedback(message)
        wb.volume_render_controller._set_volume_canvas_status_text(message)
        wb.volume_render_controller._update_volume_render_status_label(message)
        QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)
        if wb.volume_render_controller._active_result_region_mask_volume() is None:
            wb._set_operation_feedback(tt("Selected source has no label volume for the current part.", wb.lang))
            return False
        wb.volume_render_controller._clear_volume_mask_caches(owner=wb.volume_render_controller._active_volume_cache_owner())
        wb.volume_render_controller._reset_active_volume_preview_state()
        wb._set_volume_mask_mode("masked_image")
        wb.on_display_mode_changed("volume")
        wb.volume_render_controller.render_volume_preview()
        wb._set_operation_feedback(tt("Region highlight is ready in 3D preview.", wb.lang))
        return True


    def on_result_comparison_controls_changed(self, *args):
        wb = self.workbench
        self.invalidate_result_region_mask_cache(clear_active_mask_preview=True)
        if hasattr(wb, "result_compare_table") and not self.state.refreshing:
            self.refresh_result_comparison_if_visible()
        if wb.display_mode == "volume":
            wb.volume_render_controller.render_volume_preview()


    def on_training_mode_tab_changed(self, *_args):
        wb = self.workbench
        if self.result_comparison_tab_is_active() and self.state.stale:
            self.refresh_comparison()


    def sync_result_comparison_controls(self):
        wb = self.workbench
        if hasattr(wb, "btn_refresh_result_comparison"):
            wb.btn_refresh_result_comparison.setEnabled(bool(wb.project.project_data.get("specimens", [])))
        has_result_rows = bool(getattr(wb, "result_compare_table", None) and wb.result_compare_table.rowCount() > 0)
        if hasattr(wb, "btn_open_result_comparison_target"):
            wb.btn_open_result_comparison_target.setEnabled(has_result_rows)
        if hasattr(wb, "btn_show_result_region_in_3d"):
            wb.btn_show_result_region_in_3d.setEnabled(self.result_region_id() > 0 and has_result_rows)


    def invalidate_result_region_mask_cache(self, clear_active_mask_preview=True):
        wb = self.workbench
        self.state.region_mask_cache = {}
        self.state.region_mask_cache_key = None
        if clear_active_mask_preview:
            wb.volume_render_controller._clear_volume_mask_caches(owner=wb.volume_render_controller._active_volume_cache_owner())


    def import_external_prediction_dialog(self):
        wb = self.workbench
        if not wb.coordinator.guard_backend_write_lock():
            return
        if not wb._ensure_tif_project_open():
            return
        if not wb.current_specimen_id:
            QMessageBox.warning(
                wb,
                tt("Import External Label TIF", wb.lang),
                tt("Please select a specimen with a working volume first.", wb.lang),
            )
            return
        specimen_id = wb.current_specimen_id
        specimen = wb.project.get_specimen(specimen_id, default=None)
        working = (specimen or {}).get("working_volume") or {}
        if not working.get("path") or not volume_sidecar_exists(wb.project.to_absolute(working.get("path", ""))):
            QMessageBox.warning(
                wb,
                tt("Import External Label TIF", wb.lang),
                tt("Please select a specimen with a working volume first.", wb.lang),
            )
            return
        labels = specimen.get("labels") or {}
        current_edit = labels.get("working_edit") or {}
        if str(current_edit.get("path") or "").strip():
            reply = QMessageBox.question(
                wb,
                tt("Import External Label TIF", wb.lang),
                tt("This predict run will overwrite the current editable result for selected target(s), but will not overwrite training truth. Continue?", wb.lang),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
        tif_path, _ = QFileDialog.getOpenFileName(
            wb,
            tt("Import External Label TIF", wb.lang),
            "",
            "TIF/TIFF (*.tif *.tiff)",
        )
        if not tif_path:
            return
        prediction_id, ok = QInputDialog.getText(
            wb,
            tt("Import External Label TIF", wb.lang),
            tt("Prediction ID:", wb.lang),
            text=default_prediction_id_for_tif(tif_path),
        )
        if not ok or not prediction_id:
            return
        source_model, ok = QInputDialog.getText(
            wb,
            tt("Import External Label TIF", wb.lang),
            tt("Source model:", wb.lang),
            text="nnUNet",
        )
        if not ok:
            return
        try:
            result = import_external_prediction_tif(
                wb.project,
                specimen_id,
                tif_path,
                prediction_id=prediction_id,
                source_model=source_model or "external_tif",
            )
        except Exception as exc:
            QMessageBox.critical(wb, tt("Import External Label TIF", wb.lang), str(exc))
            return
        wb.refresh_project(reload_current=False)
        wb._select_specimen_after_import(specimen_id)
        index = wb.label_role_combo.findData("working_edit")
        if index >= 0:
            wb.label_role_combo.setCurrentIndex(index)
        wb.load_specimen(specimen_id)
        report_path = result.get("report_path", "")
        message = tt("Imported external label TIF as editable review result for specimen {0}. Report: {1}", wb.lang).format(specimen_id, report_path)
        wb.training_status_label.setText(message)
        wb.log(message)


    def selected_part_refs_for_review_acceptance(self):
        wb = self.workbench
        return [
            ref
            for ref in wb.backend_panel_controller.selected_predict_refs()
            if ref["specimen_id"] and ref["part_id"]
        ]


    def format_part_ref_label(self, ref):
        wb = self.workbench
        specimen_id = str((ref or {}).get("specimen_id") or "")
        part_id = str((ref or {}).get("part_id") or "")
        reslice_id = str((ref or {}).get("reslice_id") or "")
        label = f"{specimen_id}:{part_id}" if specimen_id or part_id else ""
        return f"{label}:{reslice_id}" if label and reslice_id else label


    def format_review_reasons(self, report):
        reasons = [str(item) for item in (report or {}).get("reasons") or []]
        return ", ".join(reasons)

    def summarize_review_blockers(self, blocked, limit=4):
        wb = self.workbench
        parts = []
        for item in blocked or []:
            label = self.format_part_ref_label(item)
            report = item.get("report") if isinstance(item.get("report"), dict) else {}
            reasons = self.format_review_reasons(report) or ", ".join(str(reason) for reason in (item.get("reasons") or []))
            detail = wb._format_review_blocker_detail(report) if report else ""
            parts.append(f"{label} [{reasons}; {detail}]" if detail else f"{label} [{reasons}]")
        if len(parts) > int(limit):
            parts = parts[: int(limit)] + [f"+{len(blocked) - int(limit)}"]
        return "; ".join(parts)


    def split_review_acceptance_refs(self, refs):
        wb = self.workbench
        result = wb.truth_promotion_service.split_review_acceptance_refs(
            refs,
            require_opened_for_review=False,
        )
        report = result.payload.get("report", {}) if result else {}
        ready = list(report.get("ready") or [])
        not_opened = list(report.get("not_opened") or [])
        blocked = list(report.get("blocked") or [])
        return ready, not_opened, blocked


    def accept_selected_results(self):
        wb = self.workbench
        if not wb.coordinator.guard_backend_write_lock():
            return False
        if wb.current_volume_scope == "part" and wb.annotation_workflow_controller.has_unsaved_changes():
            message = tt("Save current labels before accepting selected AI results.", wb.lang)
            wb._set_operation_feedback(message)
            QMessageBox.information(wb, tt("Accept working edit", wb.lang), message)
            return False
        refs = self.selected_part_refs_for_review_acceptance()
        if not refs:
            QMessageBox.warning(wb, tt("Accept working edit", wb.lang), tt("No selected editable AI result is ready for acceptance.", wb.lang))
            return False
        try:
            ready, not_opened, blocked = self.split_review_acceptance_refs(refs)
        except Exception as exc:
            QMessageBox.warning(wb, tt("Accept working edit", wb.lang), str(exc))
            return False
        if blocked:
            message = tt("Selected editable AI result(s) have label/schema problems: {0}", wb.lang).format(self.summarize_review_blockers(blocked))
            QMessageBox.warning(wb, tt("Accept working edit", wb.lang), message)
            wb._set_operation_feedback(message)
            return False
        if not ready:
            QMessageBox.warning(wb, tt("Accept working edit", wb.lang), tt("No selected editable AI result is ready for acceptance.", wb.lang))
            return False
        if not_opened:
            reply = QMessageBox.question(
                wb,
                tt("Accept working edit", wb.lang),
                tt("Some selected editable AI result(s) have not been opened for review. Accept them as training truth anyway?", wb.lang),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return False
        reply = QMessageBox.question(
            wb,
            tt("Accept working edit", wb.lang),
            tt("Accept {0} selected editable AI result(s) as training truth?", wb.lang).format(len(ready)),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return False
        try:
            service_result = wb.truth_promotion_service.promote_reviewed_refs(
                ready,
                require_opened_for_review=False,
                save=True,
            )
        except Exception as exc:
            QMessageBox.warning(wb, tt("Accept working edit", wb.lang), str(exc))
            return False
        if not service_result:
            message = service_result.message or ", ".join(service_result.reasons or [])
            QMessageBox.warning(wb, tt("Accept working edit", wb.lang), message)
            return False
        result = service_result.payload.get("result", {})
        wb.refresh_project(reload_current=False)
        if wb.current_specimen_id and wb.current_part_id:
            wb.selection_workflow_controller.select_payload(
                {
                    "specimen_id": wb.current_specimen_id,
                    "scope": "part_reslice" if wb.current_reslice_id else "part",
                    "part_id": wb.current_part_id,
                    "reslice_id": wb.current_reslice_id,
                }
            )
        message = tt("Accepted {0} editable AI result(s) as training truth.", wb.lang).format(result.get("count", 0))
        wb._set_operation_feedback(message)
        return True
