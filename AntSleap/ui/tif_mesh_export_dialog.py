from __future__ import annotations

import os
import threading

from PySide6.QtCore import QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from AntSleap.core.location_registry import resolve_location
from AntSleap.core.mesh_export import (
    export_reviewed_label_meshes,
    reviewed_mesh_source_summary,
    safe_cleanup_incomplete_mesh_export,
    verify_mesh_export,
)
from AntSleap.core.mesh_export_ledger import MeshExportLedger


def _text(lang, english, chinese):
    return chinese if str(lang or "").lower().startswith("zh") else english


class MeshExportWorker(QThread):
    progress_signal = Signal(int, int, str)
    result_signal = Signal(dict)
    error_signal = Signal(str)

    def __init__(self, action, project_manager, kwargs, parent=None):
        super().__init__(parent)
        self.action = str(action)
        self.project = project_manager
        self.kwargs = dict(kwargs or {})
        self._cancel = threading.Event()
        self.error_record = {}

    def cancel(self):
        self._cancel.set()

    def run(self):
        try:
            if self.action == "export":
                record = export_reviewed_label_meshes(
                    self.project,
                    cancel_check=self._cancel.is_set,
                    progress_callback=lambda done, total, stage: self.progress_signal.emit(
                        int(done), int(total), str(stage)
                    ),
                    **self.kwargs,
                )
            elif self.action == "summary":
                record = reviewed_mesh_source_summary(
                    self.project,
                    cancel_check=self._cancel.is_set,
                    progress_callback=lambda done, total, stage: self.progress_signal.emit(
                        int(done), int(total), str(stage)
                    ),
                    **self.kwargs,
                )
            elif self.action == "verify":
                record = verify_mesh_export(self.project, self.kwargs["export_id"])
            elif self.action == "cleanup":
                record = safe_cleanup_incomplete_mesh_export(
                    self.project,
                    self.kwargs["export_id"],
                )
            else:
                raise ValueError("unknown_mesh_export_worker_action")
            self.result_signal.emit(dict(record or {}))
        except Exception as exc:
            self.error_record = dict(getattr(exc, "record", {}) or {})
            self.error_signal.emit(str(getattr(exc, "code", "") or exc))


class TifMeshExportDialog(QDialog):
    def __init__(
        self,
        project_manager,
        specimen_id,
        *,
        part_id="",
        reslice_id="",
        lang="en",
        parent=None,
    ):
        super().__init__(parent)
        self.project = project_manager
        self.specimen_id = str(specimen_id or "")
        self.part_id = str(part_id or "")
        self.reslice_id = str(reslice_id or "")
        self.lang = lang
        self.worker = None
        self.source_ready = False
        self.last_record = None
        self.history_records = []
        self.setWindowTitle(
            _text(lang, "Reviewed label mesh export", "人工审核标签 STL 导出")
        )
        self.resize(860, 680)
        self._build_ui()
        self._load_source_summary()
        self.refresh_history()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        self.scope_label = QLabel(self)
        self.scope_label.setWordWrap(True)
        layout.addWidget(self.scope_label)

        self.scale_label = QLabel(self)
        self.scale_label.setWordWrap(True)
        layout.addWidget(self.scale_label)

        self.label_table = QTableWidget(0, 4, self)
        self.label_table.setObjectName("tifMeshExportLabelTable")
        self.label_table.setHorizontalHeaderLabels(
            [
                _text(self.lang, "Export", "导出"),
                _text(self.lang, "Label ID", "标签 ID"),
                _text(self.lang, "Region", "区域"),
                _text(self.lang, "Voxels", "体素数"),
            ]
        )
        self.label_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.label_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.label_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.label_table)

        target_row = QHBoxLayout()
        self.target_edit = QLineEdit(self)
        self.target_edit.setObjectName("tifMeshExportTargetEdit")
        self.target_edit.setReadOnly(True)
        self.browse_button = QPushButton(
            _text(self.lang, "Choose output directory", "选择输出目录"), self
        )
        self.browse_button.clicked.connect(self.choose_target_directory)
        target_row.addWidget(self.target_edit, 1)
        target_row.addWidget(self.browse_button)
        layout.addLayout(target_row)

        options = QHBoxLayout()
        self.preview_check = QCheckBox(
            _text(
                self.lang,
                "Create smoothed preview copies (not original measurement meshes)",
                "生成平滑展示副本（不作为原始测量网格）",
            ),
            self,
        )
        self.preview_check.toggled.connect(self._update_option_state)
        self.iterations_spin = QSpinBox(self)
        self.iterations_spin.setRange(1, 100)
        self.iterations_spin.setValue(10)
        self.iterations_spin.setEnabled(False)
        options.addWidget(self.preview_check)
        options.addWidget(
            QLabel(_text(self.lang, "Iterations", "迭代次数"), self)
        )
        options.addWidget(self.iterations_spin)
        options.addStretch(1)
        layout.addLayout(options)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        self.status_label = QLabel(self)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        actions = QHBoxLayout()
        self.export_button = QPushButton(
            _text(self.lang, "Export selected STL", "导出所选 STL"), self
        )
        self.export_button.setObjectName("tifMeshExportRunButton")
        self.export_button.clicked.connect(lambda _checked=False: self.start_export())
        self.cancel_button = QPushButton(
            _text(self.lang, "Cancel", "取消"), self
        )
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_action)
        actions.addWidget(self.export_button)
        actions.addWidget(self.cancel_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        layout.addWidget(
            QLabel(_text(self.lang, "Export history", "导出历史"), self)
        )
        self.history_table = QTableWidget(0, 5, self)
        self.history_table.setObjectName("tifMeshExportHistoryTable")
        self.history_table.setHorizontalHeaderLabels(
            [
                _text(self.lang, "Status", "状态"),
                _text(self.lang, "Export ID", "导出 ID"),
                _text(self.lang, "STL", "STL 数"),
                _text(self.lang, "Created", "创建时间"),
                _text(self.lang, "Issue", "问题"),
            ]
        )
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.history_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.history_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.history_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.history_table)

        history_actions = QGridLayout()
        self.verify_button = QPushButton(
            _text(self.lang, "Verify files", "复验文件"), self
        )
        self.verify_button.clicked.connect(self.verify_selected)
        self.retry_button = QPushButton(
            _text(self.lang, "Retry as new export", "新建重试导出"), self
        )
        self.retry_button.clicked.connect(self.retry_selected)
        self.cleanup_button = QPushButton(
            _text(self.lang, "Safely clean incomplete files", "安全清理未完成文件"),
            self,
        )
        self.cleanup_button.clicked.connect(self.cleanup_selected)
        self.open_button = QPushButton(
            _text(self.lang, "Open export directory", "打开导出目录"), self
        )
        self.open_button.clicked.connect(self.open_selected_directory)
        history_actions.addWidget(self.verify_button, 0, 0)
        history_actions.addWidget(self.retry_button, 0, 1)
        history_actions.addWidget(self.cleanup_button, 1, 0)
        history_actions.addWidget(self.open_button, 1, 1)
        layout.addLayout(history_actions)

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        self.close_button = QPushButton(
            _text(self.lang, "Close", "关闭"), self
        )
        self.close_button.clicked.connect(self.accept)
        close_row.addWidget(self.close_button)
        layout.addLayout(close_row)

    def _load_source_summary(self):
        default = os.path.join(self.project.project_dir, "exports", "meshes")
        os.makedirs(default, exist_ok=True)
        self.target_edit.setText(default)
        self._start_worker(
            "summary",
            {
                "specimen_id": self.specimen_id,
                "part_id": self.part_id,
                "reslice_id": self.reslice_id,
            },
        )

    def _apply_source_summary(self, summary):
        scope = self.specimen_id
        if self.part_id:
            scope += f" / {self.part_id}"
        if self.reslice_id:
            scope += f" / {self.reslice_id}"
        self.scope_label.setText(
            _text(self.lang, "Source: {0}", "来源：{0}").format(scope)
        )
        scale_status = summary["scale_status"]
        status_text = _text(
            self.lang,
            "verified" if scale_status == "verified" else "unverified; observation only",
            "已验证" if scale_status == "verified" else "未验证，仅供观察",
        )
        self.scale_label.setText(
            _text(
                self.lang,
                "Spacing Z/Y/X: {0} {1}; axes: ZYX to XYZ; STL unit: millimeter; scale: {2}",
                "体素间距 Z/Y/X：{0} {1}；方向：ZYX 转 XYZ；STL 单位：毫米；尺度：{2}",
            ).format(summary["spacing_zyx"], summary["spacing_unit"], status_text)
        )
        labels = summary["labels"]
        self.label_table.setRowCount(len(labels))
        for row, label in enumerate(labels):
            checkbox = QCheckBox(self.label_table)
            checkbox.setChecked(True)
            self.label_table.setCellWidget(row, 0, checkbox)
            self.label_table.setItem(row, 1, QTableWidgetItem(str(label["label_id"])))
            self.label_table.setItem(row, 2, QTableWidgetItem(label["label_name"]))
            self.label_table.setItem(row, 3, QTableWidgetItem(str(label["voxel_count"])))
        self.label_table.resizeColumnsToContents()
        self.source_ready = True

    def _update_option_state(self, checked):
        self.iterations_spin.setEnabled(bool(checked))

    def choose_target_directory(self):
        selected = QFileDialog.getExistingDirectory(
            self,
            _text(self.lang, "Choose mesh output directory", "选择网格输出目录"),
            self.target_edit.text(),
        )
        if selected:
            self.target_edit.setText(selected)

    def _selected_label_ids(self):
        selected = []
        for row in range(self.label_table.rowCount()):
            checkbox = self.label_table.cellWidget(row, 0)
            if checkbox is not None and checkbox.isChecked():
                selected.append(int(self.label_table.item(row, 1).text()))
        return selected

    def _set_running(self, running):
        self.export_button.setEnabled(not running and self.source_ready)
        for widget in (
            self.browse_button,
            self.verify_button,
            self.retry_button,
            self.cleanup_button,
            self.open_button,
            self.close_button,
        ):
            widget.setEnabled(not running)
        self.cancel_button.setEnabled(running)

    def _start_worker(self, action, kwargs):
        if self.worker is not None and self.worker.isRunning():
            return
        self.worker = MeshExportWorker(action, self.project, kwargs, self)
        self.worker.progress_signal.connect(self._on_progress)
        self.worker.result_signal.connect(self._on_result)
        self.worker.error_signal.connect(self._on_error)
        self.worker.finished.connect(self._on_finished)
        self._set_running(True)
        self.status_label.setText(
            _text(self.lang, "Mesh operation running...", "网格操作正在进行...")
        )
        self.worker.start()

    def start_export(self, *, retry_of=None):
        labels = self._selected_label_ids()
        if not labels:
            QMessageBox.information(
                self,
                self.windowTitle(),
                _text(self.lang, "Select at least one label.", "请至少选择一个标签。"),
            )
            return
        target = self.target_edit.text().strip()
        if not os.path.isdir(target):
            QMessageBox.warning(
                self,
                self.windowTitle(),
                _text(self.lang, "Choose an existing output directory.", "请选择已存在的输出目录。"),
            )
            return
        self._start_worker(
            "export",
            {
                "specimen_id": self.specimen_id,
                "target_directory": target,
                "label_ids": labels,
                "part_id": self.part_id,
                "reslice_id": self.reslice_id,
                "preview_smoothing": self.preview_check.isChecked(),
                "smoothing_iterations": self.iterations_spin.value(),
                "retry_of": retry_of,
            },
        )

    def cancel_action(self):
        if self.worker is not None:
            self.worker.cancel()
            self.status_label.setText(
                _text(
                    self.lang,
                    "Cancellation requested; finishing the current safe write...",
                    "已请求取消；正在完成当前安全写入...",
                )
            )

    def _on_progress(self, done, total, stage):
        self.progress_bar.setRange(0, max(1, int(total)))
        self.progress_bar.setValue(min(int(done), max(1, int(total))))
        self.status_label.setText(str(stage))

    def _on_result(self, record):
        action = str(self.worker.action if self.worker is not None else "")
        if action == "summary":
            self._apply_source_summary(record)
            self.status_label.setText(
                _text(
                    self.lang,
                    "Reviewed source is ready for mesh export.",
                    "已审核来源可以导出网格。",
                )
            )
            return
        self.last_record = dict(record or {})
        self.refresh_history()
        status = str(record.get("status") or "")
        self.status_label.setText(
            _text(self.lang, "Mesh export status: {0}", "网格导出状态：{0}").format(status)
        )
        if status == "complete":
            QMessageBox.information(
                self,
                self.windowTitle(),
                _text(
                    self.lang,
                    "STL export completed and verified against SQLite.",
                    "STL 已导出，并与 SQLite 记录复验一致。",
                ),
            )
        elif status == "incomplete":
            QMessageBox.warning(
                self,
                self.windowTitle(),
                _text(
                    self.lang,
                    "The export is incomplete. Use verify, retry, or safe cleanup.",
                    "导出未完成，请使用复验、重试或安全清理。",
                ),
            )

    def _on_error(self, message):
        friendly = {
            "mesh_manual_truth_missing": _text(
                self.lang,
                "No reviewed training truth is available for this object.",
                "当前对象没有已审核的训练真值。",
            ),
            "mesh_manual_truth_not_reviewed": _text(
                self.lang,
                "The training truth has not been reviewed yet.",
                "当前训练真值尚未完成人工审核。",
            ),
            "retry_source_changed_create_new_export": _text(
                self.lang,
                "The reviewed labels changed. Start a new export instead of linking this as a retry.",
                "已审核标签内容发生变化。请新建导出，不要把它关联为旧任务重试。",
            ),
        }.get(str(message), str(message))
        record = dict(
            getattr(self.worker, "error_record", {}) or {}
            if self.worker is not None
            else {}
        )
        if record.get("error_stage"):
            friendly += _text(
                self.lang,
                "\nStage: {0}; export ID: {1}",
                "\n失败阶段：{0}；导出 ID：{1}",
            ).format(record["error_stage"], record.get("export_id") or "-")
        self.status_label.setText(friendly)
        self.refresh_history()
        QMessageBox.critical(self, self.windowTitle(), friendly)

    def _on_finished(self):
        self._set_running(False)
        worker = self.worker
        self.worker = None
        if worker is not None:
            worker.deleteLater()

    def refresh_history(self):
        self.history_records = MeshExportLedger(
            self.project.current_database_path
        ).list_exports(
            specimen_id=self.specimen_id,
            part_id=self.part_id,
            reslice_id=self.reslice_id,
        )
        self.history_table.setRowCount(len(self.history_records))
        for row, record in enumerate(self.history_records):
            values = (
                record.get("status"),
                record.get("export_id"),
                record.get("stl_item_count"),
                record.get("created_at"),
                record.get("error_code") or (
                    record.get("reviews", [{}])[-1].get("review_status")
                    if record.get("reviews")
                    else ""
                ),
            )
            for column, value in enumerate(values):
                self.history_table.setItem(row, column, QTableWidgetItem(str(value or "")))
        self.history_table.resizeColumnsToContents()

    def _selected_history(self):
        row = self.history_table.currentRow()
        if row < 0 or row >= len(self.history_records):
            QMessageBox.information(
                self,
                self.windowTitle(),
                _text(self.lang, "Select an export record.", "请选择一条导出记录。"),
            )
            return None
        return self.history_records[row]

    def verify_selected(self):
        record = self._selected_history()
        if record:
            self._start_worker("verify", {"export_id": record["export_id"]})

    def retry_selected(self):
        record = self._selected_history()
        if not record:
            return
        if record["status"] not in {"incomplete", "failed"}:
            QMessageBox.information(
                self,
                self.windowTitle(),
                _text(self.lang, "Only incomplete or failed exports can be retried.", "只有未完成或失败的导出可以重试。"),
            )
            return
        try:
            target = resolve_location(
                record["target_location_ref"],
                expected_kind="directory",
                database_path=getattr(
                    self.project,
                    "location_registry_database_path",
                    None,
                ),
            )
        except Exception as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        requested = {int(item["label_id"]) for item in record["requested_labels"]}
        for row in range(self.label_table.rowCount()):
            label_id = int(self.label_table.item(row, 1).text())
            checkbox = self.label_table.cellWidget(row, 0)
            checkbox.setChecked(label_id in requested)
        self.target_edit.setText(str(target))
        options = dict(record.get("options") or {})
        self.preview_check.setChecked(bool(options.get("preview_smoothing")))
        self.iterations_spin.setValue(
            int(options.get("smoothing_iterations") or 10)
        )
        self.start_export(retry_of=record["export_id"])

    def cleanup_selected(self):
        record = self._selected_history()
        if not record:
            return
        answer = QMessageBox.question(
            self,
            self.windowTitle(),
            _text(
                self.lang,
                "Remove only the incomplete files listed by this export record?",
                "只删除这条导出记录对应的未完成文件吗？",
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self._start_worker("cleanup", {"export_id": record["export_id"]})

    def open_selected_directory(self):
        record = self._selected_history()
        if not record:
            return
        try:
            parent = resolve_location(
                record["target_location_ref"],
                expected_kind="directory",
                database_path=getattr(
                    self.project,
                    "location_registry_database_path",
                    None,
                ),
            )
            path = parent / record["target_relative_path"]
        except Exception as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def reject(self):
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.information(
                self,
                self.windowTitle(),
                _text(self.lang, "Wait for the mesh operation to finish.", "请等待网格操作完成。"),
            )
            return
        super().reject()


__all__ = ["MeshExportWorker", "TifMeshExportDialog"]
