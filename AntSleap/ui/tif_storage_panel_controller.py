from __future__ import annotations

import os

from PySide6.QtCore import QObject, QThread, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QMessageBox, QTableWidgetItem

from .tif_workbench_translations import tt
from .tif_workbench_workers import TifStorageScanWorker


def _bytes_text(value):
    amount = float(value or 0)
    if amount >= 1e9:
        return f"{amount / 1e9:.2f} GB"
    if amount >= 1e6:
        return f"{amount / 1e6:.2f} MB"
    if amount >= 1e3:
        return f"{amount / 1e3:.2f} KB"
    return f"{int(amount)} B"


class TifStoragePanelController(QObject):
    VIEW_SCOPE = "storage_panel"

    def __init__(self, workbench):
        super().__init__(workbench)
        self.workbench = workbench
        self.thread = None
        self.worker = None
        self.operation = ""
        self.last_inventory = None
        self.last_plan = None
        self.last_report_paths = {}

    def bind_signals(self):
        wb = self.workbench
        wb.workbench_view.register_scope(
            self.VIEW_SCOPE,
            "btn_analyze_storage",
            "btn_generate_cleanup_plan",
            "btn_storage_agent",
            "btn_open_storage_report",
            "storage_table",
            "storage_summary_label",
            "storage_help_label",
        )
        wb.btn_analyze_storage.clicked.connect(lambda: self.start_scan("inventory"))
        wb.btn_generate_cleanup_plan.clicked.connect(
            lambda: self.start_scan("cleanup_plan")
        )
        wb.btn_storage_agent.clicked.connect(self.request_agent)
        wb.btn_open_storage_report.clicked.connect(self.open_latest_report)
        self.apply_language()
        self._sync_button_state()

    def apply_language(self):
        wb = self.workbench
        lang = wb.lang
        wb.storage_help_label.setText(
            tt(
                "Occupancy analysis is read-only. Cleanup plans automatically rescan and only include registered, verified caches; historical unregistered files remain protected.",
                lang,
            )
        )
        if self.last_inventory is None and self.thread is None:
            wb.storage_summary_label.setText(tt("No storage scan yet.", lang))
        wb.btn_analyze_storage.setText(tt("Analyze occupancy", lang))
        wb.btn_generate_cleanup_plan.setText(tt("Generate cleanup plan", lang))
        wb.btn_storage_agent.setText(tt("Ask embedded Agent", lang))
        wb.btn_open_storage_report.setText(tt("Open latest report", lang))
        wb.storage_table.setHorizontalHeaderLabels(
            [
                tt("Path", lang),
                tt("Role", lang),
                tt("Layer", lang),
                tt("Size", lang),
                tt("Status", lang),
                tt("Reason", lang),
            ]
        )

    def cancel_and_wait_scan(self, timeout_ms=5000):
        if self.thread is None:
            return True
        cancel = getattr(self.worker, "cancel", None)
        if callable(cancel):
            cancel()
        self.thread.requestInterruption()
        self.thread.quit()
        return bool(self.thread.wait(max(0, int(timeout_ms))))

    def reset_for_project(self):
        if self.thread is not None and self.thread.isRunning():
            return False
        self.last_inventory = None
        self.last_plan = None
        self.last_report_paths = {}
        self.workbench.storage_table.setRowCount(0)
        self.workbench.storage_summary_label.setText(
            tt("No storage scan yet.", self.workbench.lang)
        )
        self._sync_button_state()
        return True

    def on_workbench_closing(self):
        self.cancel_and_wait_scan()

    def _sqlite_project_available(self):
        return bool(
            getattr(self.workbench.project, "is_sqlite_project", lambda: False)()
            and getattr(self.workbench.project, "project_dir", "")
        )

    def _sync_button_state(self):
        wb = self.workbench
        idle = self.thread is None
        available = self._sqlite_project_available()
        wb.btn_analyze_storage.setEnabled(idle and available)
        wb.btn_generate_cleanup_plan.setEnabled(idle and available)
        wb.btn_storage_agent.setEnabled(
            idle and available and self.last_plan is not None
        )
        wb.btn_open_storage_report.setEnabled(idle and bool(self.last_report_paths))

    def _start_worker(self, worker, operation):
        if self.thread is not None:
            QMessageBox.information(
                self.workbench,
                tt("Storage management", self.workbench.lang),
                tt("A storage operation is already running.", self.workbench.lang),
            )
            return False
        thread = QThread(self.workbench)
        self.thread = thread
        self.worker = worker
        self.operation = str(operation or "")
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        progress = getattr(worker, "progress", None)
        if progress is not None:
            progress.connect(self._on_progress)
        worker.finished.connect(self._on_worker_finished)
        worker.failed.connect(self._on_worker_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(self._clear_worker)
        thread.finished.connect(thread.deleteLater)
        thread.start()
        self._sync_button_state()
        return True

    def start_scan(self, mode):
        wb = self.workbench
        if not self._sqlite_project_available():
            QMessageBox.warning(
                wb,
                tt("Storage management", wb.lang),
                tt("Open a SQLite TIF project before using storage management.", wb.lang),
            )
            return False
        started = self._start_worker(
            TifStorageScanWorker(wb.project, mode=mode),
            mode,
        )
        if started:
            wb.storage_summary_label.setText(
                tt("Scanning storage occupancy...", wb.lang)
            )
        return started

    def _on_progress(self, current, total, message):
        display = tt(str(message or ""), self.workbench.lang)
        self.workbench.storage_summary_label.setText(display)
        if hasattr(self.workbench, "log"):
            self.workbench.log(display)

    def _on_worker_finished(self, payload):
        data = payload if isinstance(payload, dict) else {}
        self.last_inventory = data.get("inventory")
        self.last_plan = data.get("plan")
        self.last_report_paths = data.get("report_paths") or {}
        self._fill_table()
        summary = (self.last_inventory or {}).get("summary") or {}
        unknown_count = sum(
            1
            for item in (self.last_inventory or {}).get("items", [])
            if item.get("classification_reason") == "unknown_is_protected"
        )
        message = tt(
            "Occupancy {0}. Unique allocated {1}. Unknown protected items {2}.",
            self.workbench.lang,
        ).format(
            _bytes_text(summary.get("logical_bytes")),
            _bytes_text(summary.get("unique_allocated_bytes")),
            unknown_count,
        )
        if self.last_plan:
            eligible = [
                item
                for item in self.last_plan.get("items", [])
                if item.get("eligibility") == "eligible"
            ]
            blocked = [
                item
                for item in self.last_plan.get("items", [])
                if item.get("eligibility") != "eligible"
            ]
            message += " " + tt(
                "Dry-run candidates {0}, blocked {1}, estimated release {2}. Nothing was deleted.",
                self.workbench.lang,
            ).format(
                len(eligible),
                len(blocked),
                _bytes_text(self.last_plan.get("expected_release_bytes")),
            )
            if not self.last_plan.get("items"):
                message += " " + tt(
                    "The cleanup plan was generated successfully, but this project has no registered reproducible caches. Historical unregistered files remain protected.",
                    self.workbench.lang,
                )
        self.workbench.storage_summary_label.setText(message)

    def _on_worker_failed(self, message):
        text = str(message or "")
        if text == "tif_storage_scan_cancelled":
            self.workbench.storage_summary_label.setText(
                tt("Storage scan cancelled.", self.workbench.lang)
            )
            return
        QMessageBox.warning(
            self.workbench,
            tt("Storage management", self.workbench.lang),
            text,
        )
        self.workbench.storage_summary_label.setText(text)

    def _clear_worker(self):
        self.worker = None
        self.thread = None
        self.operation = ""
        self._sync_button_state()

    def _fill_table(self):
        table = self.workbench.storage_table
        rows = []
        plan_items = (self.last_plan or {}).get("items", []) or []
        if plan_items:
            for item in plan_items:
                status = (
                    "candidate"
                    if item.get("eligibility") == "eligible"
                    else "blocked"
                )
                reason = (
                    item.get("blocked_reason")
                    or item.get("reproducible_evidence")
                    or ""
                )
                rows.append((item, status, reason))
        else:
            for item in (self.last_inventory or {}).get("items", []) or []:
                status = (
                    "protected"
                    if item.get("authority_level") in {"L0", "L1"}
                    else "registered cache"
                )
                rows.append((item, status, item.get("classification_reason") or ""))
        table.setRowCount(len(rows))
        for row_index, (item, status, reason) in enumerate(rows):
            values = [
                item.get("original_path") or item.get("relative_path") or "",
                item.get("role") or "",
                item.get("authority_level") or "",
                _bytes_text(item.get("size_bytes") or item.get("logical_bytes")),
                status if item.get("state") in {None, "", "planned"} else item.get("state"),
                reason,
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
                if column == 0:
                    cell.setData(Qt.UserRole, item)
                table.setItem(row_index, column, cell)
        table.resizeColumnsToContents()

    def _absolute_report_path(self, value):
        path = str(value or "")
        if not path:
            return ""
        if os.path.isabs(path):
            return os.path.abspath(path)
        return os.path.abspath(os.path.join(self.workbench.project.project_dir, path))

    def _report_path(self, report):
        paths = (report or {}).get("report_paths") or {}
        return self._absolute_report_path(
            paths.get("markdown_path") or paths.get("json_path") or ""
        )

    def request_agent(self):
        wb = self.workbench
        if self.last_plan is None:
            QMessageBox.information(
                wb,
                tt("Storage management", wb.lang),
                tt(
                    "Generate a cleanup plan before asking the embedded Agent.",
                    wb.lang,
                ),
            )
            return

        summary = (self.last_inventory or {}).get("summary") or {}
        plan_items = self.last_plan.get("items") or []
        eligible_count = sum(
            1 for item in plan_items if item.get("eligibility") == "eligible"
        )
        blocked_count = len(plan_items) - eligible_count
        unknown_count = sum(
            1
            for item in (self.last_inventory or {}).get("items", [])
            if item.get("classification_reason") == "unknown_is_protected"
        )
        cleanup_report = self._report_path(self.last_plan)
        inventory_report = self._report_path(self.last_inventory)
        report_directory = os.path.dirname(cleanup_report or inventory_report)
        plan_state = str(self.last_plan.get("state") or "planned")
        plan_id = str(self.last_plan.get("plan_id") or "")

        context = dict(wb.get_agent_context() or {})
        context.update(
            {
                "source_workbench": "tif_storage",
                "storage_inventory_report": inventory_report,
                "storage_cleanup_report": cleanup_report,
                "storage_report_directory": report_directory,
                "storage_logical_bytes": "{0} ({1})".format(
                    int(summary.get("logical_bytes") or 0),
                    _bytes_text(summary.get("logical_bytes")),
                ),
                "storage_unique_bytes": "{0} ({1})".format(
                    int(summary.get("unique_allocated_bytes") or 0),
                    _bytes_text(summary.get("unique_allocated_bytes")),
                ),
                "storage_candidate_count": str(eligible_count),
                "storage_blocked_count": str(blocked_count),
                "storage_unknown_protected_count": str(unknown_count),
                "storage_expected_release_bytes": "{0} ({1})".format(
                    int(self.last_plan.get("expected_release_bytes") or 0),
                    _bytes_text(self.last_plan.get("expected_release_bytes")),
                ),
                "storage_plan_state": (
                    f"{plan_state}; plan_id={plan_id}" if plan_id else plan_state
                ),
                "storage_agent_request": tt(
                    "Read the latest occupancy inventory and cleanup plan, explain what can be safely reclaimed and what remains protected, and give a clear recommendation for the current large TIF dataset. Do not move or delete any file without the researcher's explicit authorization.",
                    wb.lang,
                ),
            }
        )
        wb.agent_requested.emit(context)

    def open_latest_report(self):
        value = (
            self.last_report_paths.get("markdown_path")
            or self.last_report_paths.get("json_path")
            or ""
        )
        path = self._absolute_report_path(value)
        if not path or not os.path.isfile(path):
            QMessageBox.information(
                self.workbench,
                tt("Storage management", self.workbench.lang),
                tt("No report has been generated yet.", self.workbench.lang),
            )
            return
        message = tt("Opened report: {0}", self.workbench.lang).format(path)
        self.workbench.storage_summary_label.setText(message)
        if hasattr(self.workbench, "log"):
            self.workbench.log(message)
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))
