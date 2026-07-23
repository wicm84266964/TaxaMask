from __future__ import annotations

import os
from datetime import datetime

from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QProgressDialog,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)
from PySide6.QtCore import Qt

from AntSleap.core.project_integrity_recovery import (
    inspect_project_integrity,
    register_current_asset_version,
    write_redacted_integrity_diagnostic,
)
from AntSleap.core.training_initial_weights import register_initial_weight_version
from AntSleap.core.tif_integrity_bridge import relocate_tif_project_asset


INTEGRITY_ERROR_MARKERS = (
    "integrity",
    "digest",
    "fingerprint",
    "source_missing",
    "source_read_denied",
    "opaque_location",
    "initial_weight",
    "manual_truth",
)


def is_training_integrity_error(error):
    code = str(getattr(error, "code", "") or error).lower()
    return any(marker in code for marker in INTEGRITY_ERROR_MARKERS)


class TrainingIntegrityRecoveryDialog(QDialog):
    def __init__(self, project_manager, parent=None):
        super().__init__(parent)
        self.project = project_manager
        self.report = {"items": []}
        self.setWindowTitle("训练文件完整性恢复 / Training file recovery")
        self.resize(1100, 520)
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "训练已停止。请先恢复、重新定位或登记文件新版本；所有必需文件复验通过后才能重试训练。"
            )
        )
        self.table = QTableWidget(0, 7, self)
        self.table.setHorizontalHeaderLabels(
            [
                "角色 / Role",
                "文件 / File",
                "登记大小",
                "当前大小",
                "登记指纹",
                "当前指纹",
                "状态 / 原因",
            ]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)
        actions = QHBoxLayout()
        for text, callback in (
            ("重新复验", self.refresh_report),
            ("重新定位 / 恢复副本", self.relocate_selected),
            ("登记为新版本", self.register_selected),
            ("导出脱敏诊断", self.save_diagnostic),
            ("关闭", self.reject),
        ):
            button = QPushButton(text, self)
            button.clicked.connect(callback)
            actions.addWidget(button)
        layout.addLayout(actions)
        self.refresh_report()

    def _selected_issue(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.report.get("items", [])):
            QMessageBox.information(self, "请选择文件", "请先选择一行文件记录。")
            return None
        return self.report["items"][row]

    @staticmethod
    def _short_digest(value):
        text = str(value or "")
        return text[:12] if text else "-"

    def refresh_report(self):
        progress = QProgressDialog(
            "正在核对训练文件指纹...", "取消", 0, 0, self
        )
        progress.setWindowTitle("文件完整性复验")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(250)

        def on_progress(current, total, role):
            maximum = max(1, int(total or 1))
            progress.setRange(0, maximum)
            progress.setValue(min(int(current or 0), maximum))
            progress.setLabelText(f"正在核对：{role}")
            QApplication.processEvents()

        try:
            self.report = inspect_project_integrity(
                self.project,
                progress_callback=on_progress,
                cancel_check=progress.wasCanceled,
            )
        except Exception as exc:
            if "integrity_check_cancelled" not in str(exc):
                QMessageBox.critical(self, "完整性复验失败", str(exc))
            return
        finally:
            progress.close()
        items = list(self.report.get("items", []))
        self.table.setRowCount(len(items))
        for row, item in enumerate(items):
            expected = item.get("expected") or {}
            observed = item.get("observed") or {}
            values = (
                item.get("role"),
                item.get("runtime_path"),
                expected.get("size_bytes"),
                observed.get("size_bytes"),
                self._short_digest(expected.get("digest")),
                self._short_digest(observed.get("digest")),
                item.get("status") if not item.get("error_code") else f"{item.get('status')}: {item.get('error_code')}",
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(str(value if value is not None else "-")))
        self.table.resizeColumnsToContents()

    def relocate_selected(self):
        issue = self._selected_issue()
        if issue is None:
            return
        candidate = self._choose_relocation_candidate(issue)
        if not candidate:
            return
        try:
            if issue.get("role") == "source_image":
                relocation = self.project.relocate_registered_images(
                    [{"old_path": issue["runtime_path"], "new_path": candidate}]
                )
                if relocation.get("rejected"):
                    raise ValueError(relocation["rejected"][0]["reason"])
                self.project.apply_image_path_remap(
                    relocation["relocated"], save=True
                )
            elif issue.get("role") == "initial_weights":
                register_initial_weight_version(
                    self.project,
                    [
                        {
                            "slot": issue["owner_key"],
                            "path": candidate,
                            "expected": issue["expected"],
                        }
                    ],
                    note="Unchanged starting model relocated or restored from backup.",
                )
            elif issue.get("owner_kind") == "tif_asset":
                relocate_tif_project_asset(self.project, issue, candidate)
            else:
                raise ValueError("relocation_not_available_for_this_file_role")
        except Exception as exc:
            QMessageBox.critical(
                self,
                "无法重新定位",
                f"所选文件必须与登记内容完全一致。\n\n{exc}",
            )
            return
        self.refresh_report()

    def _choose_relocation_candidate(self, issue):
        runtime_path = str((issue or {}).get("runtime_path") or "")
        if runtime_path.lower().endswith(".zarr") or os.path.isdir(runtime_path):
            return QFileDialog.getExistingDirectory(
                self, "选择移动后的目录或恢复副本"
            )
        candidate, _ = QFileDialog.getOpenFileName(
            self, "选择移动后的文件或恢复副本"
        )
        return candidate

    def register_selected(self):
        issue = self._selected_issue()
        if issue is None:
            return
        note, accepted = QInputDialog.getMultiLineText(
            self,
            "登记文件新版本",
            "请说明文件为何发生了有意修改（该说明会进入项目审计记录）：",
        )
        if not accepted or not str(note).strip():
            return
        try:
            if issue.get("owner_kind") in {"image", "tif_asset"}:
                register_current_asset_version(self.project, issue, note=note)
            elif issue.get("role") == "initial_weights":
                register_initial_weight_version(
                    self.project,
                    [{"slot": issue["owner_key"], "path": issue["runtime_path"]}],
                    note=note,
                )
            else:
                raise ValueError("new_version_not_available_for_this_file_role")
        except Exception as exc:
            QMessageBox.critical(self, "新版本登记失败", str(exc))
            return
        self.refresh_report()

    def save_diagnostic(self):
        project_root = os.path.dirname(
            os.path.abspath(self.project.current_project_path)
        )
        output_dir = os.path.join(project_root, "runs", "diagnostics")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(
            output_dir,
            f"integrity_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json",
        )
        try:
            written = write_redacted_integrity_diagnostic(self.report, output_path)
        except Exception as exc:
            QMessageBox.critical(self, "诊断文件保存失败", str(exc))
            return
        QMessageBox.information(
            self,
            "诊断文件已保存",
            f"已保存脱敏诊断，不包含本机绝对路径：\n{written}",
        )


__all__ = [
    "TrainingIntegrityRecoveryDialog",
    "is_training_integrity_error",
]
