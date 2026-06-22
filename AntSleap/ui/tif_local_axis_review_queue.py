from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

try:
    from AntSleap.core.tif_local_axis_batch import batch_export_accepted_reslices, list_local_axis_queue, update_proposal_status
except ModuleNotFoundError as exc:
    if exc.name != "AntSleap":
        raise
    from core.tif_local_axis_batch import batch_export_accepted_reslices, list_local_axis_queue, update_proposal_status


QUEUE_STATUSES = [
    ("all", "All"),
    ("no_proposal", "No proposal"),
    ("proposed", "Proposed"),
    ("needs_review", "Needs review"),
    ("accepted", "Accepted"),
    ("exported", "Exported"),
    ("rejected", "Rejected"),
    ("hard_cases", "Hard cases"),
]


QUEUE_TRANSLATIONS = {
    "zh": {
        "Local Axis Review Queue": "局部轴复核队列",
        "Status": "状态",
        "All": "全部",
        "No proposal": "无建议项",
        "Proposed": "待复核",
        "Needs review": "需要复核",
        "Accepted": "已接受",
        "Exported": "已导出",
        "Rejected": "已拒绝",
        "Hard cases": "困难样本",
        "Template": "模板",
        "Model version": "模型版本",
        "Hard flag": "困难标记",
        "Sort": "排序",
        "Status/specimen": "状态 / 标本",
        "Confidence low first": "置信度低优先",
        "Confidence high first": "置信度高优先",
        "Refresh": "刷新",
        "Specimen": "标本",
        "Part": "部位",
        "Kind": "类型",
        "Proposal": "建议项",
        "Reslice": "重切片",
        "Confidence": "置信度",
        "Hard flags": "困难标记",
        "Accept": "接受",
        "Reject": "拒绝",
        "Open proposal": "打开建议项",
        "Batch export accepted": "批量导出已接受项",
        "Select a local frame proposal row first.": "请先选择一条局部坐标系建议项。",
        "{0} local axis queue rows": "{0} 条局部轴队列记录",
        "Batch export finished: {0} exported, {1} skipped": "批量导出完成：已导出 {0} 条，跳过 {1} 条",
        "all": "全部",
        "no_proposal": "无建议项",
        "proposed": "待复核",
        "needs_review": "需要复核",
        "accepted": "已接受",
        "exported": "已导出",
        "rejected": "已拒绝",
        "hard_cases": "困难样本",
        "local_frame_proposal": "局部坐标系建议",
        "reslice": "重切片",
    }
}


def tt(text, lang="en"):
    return QUEUE_TRANSLATIONS.get(lang, {}).get(text, text)


class TifLocalAxisReviewQueueWidget(QWidget):
    open_proposal_requested = Signal(str, str, str)

    def __init__(self, project_manager, parent=None, lang="en"):
        super().__init__(parent)
        self.project = project_manager
        self.lang = lang
        self.rows = []
        self.setObjectName("tifLocalAxisReviewQueue")

        root = QVBoxLayout(self)
        filters = QHBoxLayout()
        filters.addWidget(QLabel(tt("Status", self.lang)))
        self.status_combo = QComboBox()
        for value, label in QUEUE_STATUSES:
            self.status_combo.addItem(tt(label, self.lang), value)
        self.template_filter_edit = QComboBox()
        self.template_filter_edit.setEditable(True)
        self.template_filter_edit.addItem("", "")
        self.model_version_filter_edit = QComboBox()
        self.model_version_filter_edit.setEditable(True)
        self.model_version_filter_edit.addItem("", "")
        self.hard_flag_filter_edit = QComboBox()
        self.hard_flag_filter_edit.setEditable(True)
        self.hard_flag_filter_edit.addItem("", "")
        self.sort_combo = QComboBox()
        self.sort_combo.addItem(tt("Status/specimen", self.lang), "status_specimen")
        self.sort_combo.addItem(tt("Confidence low first", self.lang), "confidence_asc")
        self.sort_combo.addItem(tt("Confidence high first", self.lang), "confidence_desc")
        self.sort_combo.addItem(tt("Model version", self.lang), "model_version")
        filters.addWidget(self.status_combo)
        filters.addWidget(QLabel(tt("Template", self.lang)))
        filters.addWidget(self.template_filter_edit)
        filters.addWidget(QLabel(tt("Model version", self.lang)))
        filters.addWidget(self.model_version_filter_edit)
        filters.addWidget(QLabel(tt("Hard flag", self.lang)))
        filters.addWidget(self.hard_flag_filter_edit)
        filters.addWidget(QLabel(tt("Sort", self.lang)))
        filters.addWidget(self.sort_combo)
        filters.addStretch(1)
        self.btn_refresh = QPushButton(tt("Refresh", self.lang))
        filters.addWidget(self.btn_refresh)
        root.addLayout(filters)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            [tt(text, self.lang) for text in ["Status", "Specimen", "Part", "Kind", "Proposal", "Reslice", "Template", "Confidence", "Hard flags"]]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        root.addWidget(self.table, 1)

        actions = QHBoxLayout()
        self.btn_accept = QPushButton(tt("Accept", self.lang))
        self.btn_needs_review = QPushButton(tt("Needs review", self.lang))
        self.btn_reject = QPushButton(tt("Reject", self.lang))
        self.btn_open_proposal = QPushButton(tt("Open proposal", self.lang))
        self.btn_batch_export = QPushButton(tt("Batch export accepted", self.lang))
        actions.addWidget(self.btn_accept)
        actions.addWidget(self.btn_needs_review)
        actions.addWidget(self.btn_reject)
        actions.addWidget(self.btn_open_proposal)
        actions.addStretch(1)
        actions.addWidget(self.btn_batch_export)
        root.addLayout(actions)

        self.status_label = QLabel("")
        root.addWidget(self.status_label)

        self.status_combo.currentIndexChanged.connect(self.refresh)
        self.template_filter_edit.currentTextChanged.connect(self.refresh)
        self.model_version_filter_edit.currentTextChanged.connect(self.refresh)
        self.hard_flag_filter_edit.currentTextChanged.connect(self.refresh)
        self.sort_combo.currentIndexChanged.connect(self.refresh)
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_accept.clicked.connect(lambda: self.update_selected_status("accepted"))
        self.btn_needs_review.clicked.connect(lambda: self.update_selected_status("needs_review"))
        self.btn_reject.clicked.connect(lambda: self.update_selected_status("rejected"))
        self.btn_open_proposal.clicked.connect(self.open_selected_proposal)
        self.btn_batch_export.clicked.connect(self.batch_export_accepted)
        self.refresh()

    def filters(self):
        filters = {"status": self.status_combo.currentData() or "all"}
        template_id = self.template_filter_edit.currentText().strip()
        if template_id:
            filters["template_id"] = template_id
        model_version = self.model_version_filter_edit.currentText().strip()
        if model_version:
            filters["model_version"] = model_version
        hard_flag = self.hard_flag_filter_edit.currentText().strip()
        if hard_flag:
            filters["hard_case_flag"] = hard_flag
        filters["sort"] = self.sort_combo.currentData() or "status_specimen"
        return filters

    def refresh(self):
        self.rows = list_local_axis_queue(self.project, self.filters())
        self.table.setRowCount(len(self.rows))
        templates = sorted({str(row.get("template_id", "")) for row in self.rows if row.get("template_id")})
        model_versions = sorted({str(row.get("model_version", "")) for row in self.rows if row.get("model_version")})
        hard_flags = sorted(
            {
                str(flag)
                for row in self.rows
                for flag in (row.get("hard_case_flags", []) or [])
                if str(flag)
            }
        )
        self._merge_combo_values(self.template_filter_edit, templates)
        self._merge_combo_values(self.model_version_filter_edit, model_versions)
        self._merge_combo_values(self.hard_flag_filter_edit, hard_flags)
        for row_index, row in enumerate(self.rows):
            values = [
                tt(row.get("status", ""), self.lang),
                row.get("specimen_id", ""),
                row.get("part_id", ""),
                tt(row.get("kind", ""), self.lang),
                row.get("proposal_id", ""),
                row.get("reslice_id", ""),
                row.get("template_id", ""),
                f"{float(row.get('confidence', 0.0) or 0.0):.3f}",
                ", ".join(row.get("hard_case_flags", []) or []),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row_index, col, item)
        self.status_label.setText(tt("{0} local axis queue rows", self.lang).format(len(self.rows)))
        return self.rows

    def _merge_combo_values(self, combo, values):
        current = combo.currentText()
        combo.blockSignals(True)
        known = {combo.itemText(index) for index in range(combo.count())}
        for value in values:
            if value not in known:
                combo.addItem(value, value)
        combo.setCurrentText(current)
        combo.blockSignals(False)

    def selected_row(self):
        selected = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not selected:
            return None
        index = selected[0].row()
        if index < 0 or index >= len(self.rows):
            return None
        return self.rows[index]

    def update_selected_status(self, status):
        row = self.selected_row()
        if not row or row.get("kind") != "local_frame_proposal" or not row.get("proposal_id"):
            QMessageBox.information(
                self,
                tt("Local Axis Review Queue", self.lang),
                tt("Select a local frame proposal row first.", self.lang),
            )
            return None
        record = update_proposal_status(
            self.project,
            row.get("proposal_id"),
            status,
            specimen_id=row.get("specimen_id"),
            part_id=row.get("part_id"),
        )
        self.refresh()
        return record

    def open_selected_proposal(self):
        row = self.selected_row()
        if not row or row.get("kind") != "local_frame_proposal" or not row.get("proposal_id"):
            QMessageBox.information(
                self,
                tt("Local Axis Review Queue", self.lang),
                tt("Select a local frame proposal row first.", self.lang),
            )
            return None
        self.open_proposal_requested.emit(row.get("specimen_id", ""), row.get("part_id", ""), row.get("proposal_id", ""))
        return row

    def batch_export_accepted(self):
        result = batch_export_accepted_reslices(self.project)
        self.refresh()
        self.status_label.setText(
            tt("Batch export finished: {0} exported, {1} skipped", self.lang).format(
                len(result.get("exported", [])),
                len(result.get("skipped", [])),
            )
        )
        return result
