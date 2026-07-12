import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

try:
    from AntSleap.core.literature_descriptions import (
        build_description_source,
        build_text_block_source,
        query_literature_part_descriptions,
        query_literature_text_blocks,
    )
    from AntSleap.ui.main_window_dialog_support import _blink_preferred_roi_parts
    from AntSleap.ui.main_window_i18n import tr
    from AntSleap.ui.main_window_widgets import NoWheelComboBox
    from AntSleap.ui.style import (
        BUTTON_ROLE_COMMIT,
        BUTTON_ROLE_NEUTRAL,
        BUTTON_ROLE_RUN,
        BUTTON_ROLE_STOP,
        apply_semantic_button_style,
        apply_theme_button_style,
        apply_theme_dialog_button_box_style,
    )
except ImportError:
    from core.literature_descriptions import (
        build_description_source,
        build_text_block_source,
        query_literature_part_descriptions,
        query_literature_text_blocks,
    )
    from ui.main_window_dialog_support import _blink_preferred_roi_parts
    from ui.main_window_i18n import tr
    from ui.main_window_widgets import NoWheelComboBox
    from ui.style import (
        BUTTON_ROLE_COMMIT,
        BUTTON_ROLE_NEUTRAL,
        BUTTON_ROLE_RUN,
        BUTTON_ROLE_STOP,
        apply_semantic_button_style,
        apply_theme_button_style,
        apply_theme_dialog_button_box_style,
    )


class ExportDialog(QDialog):
    def __init__(self, parent=None, lang="en", default_dir=""):
        super().__init__(parent)
        self.lang = lang
        self.default_dir = os.path.abspath(str(default_dir)) if default_dir else ""
        self.setWindowTitle(tr("Export Dataset", self.lang))
        self.resize(400, 150)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr("Export Format:", self.lang)))
        self.format_combo = NoWheelComboBox()
        self.format_combo.addItem(tr("Multimodal (Crops + JSONL)", self.lang), "multimodal")
        self.format_combo.addItem(tr("COCO (Standard)", self.lang), "coco")
        self.format_combo.addItem(tr("YOLO (Segmentation)", self.lang), "yolo")
        layout.addWidget(self.format_combo)
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText(tr("Select export directory...", self.lang))
        if self.default_dir:
            self.path_edit.setText(self.default_dir)
        layout.addWidget(QLabel(tr("Export Path:", self.lang)))
        browse_layout = QHBoxLayout()
        browse_layout.addWidget(self.path_edit)
        btn_browse = QPushButton(tr("Browse", self.lang))
        apply_semantic_button_style(btn_browse, BUTTON_ROLE_NEUTRAL)
        btn_browse.clicked.connect(self.browse)
        browse_layout.addWidget(btn_browse)
        layout.addLayout(browse_layout)
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton(tr("Export", self.lang))
        apply_semantic_button_style(btn_ok, BUTTON_ROLE_COMMIT)
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton(tr("Cancel", self.lang))
        apply_semantic_button_style(btn_cancel, BUTTON_ROLE_STOP)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def browse(self):
        start_dir = self.path_edit.text().strip() or self.default_dir
        if start_dir and not os.path.isdir(start_dir):
            start_dir = os.path.dirname(start_dir)
        d = QFileDialog.getExistingDirectory(self, tr("Select Directory", self.lang), start_dir)
        if d:
            self.path_edit.setText(d)
    def get_path(self):
        return self.path_edit.text()
    def get_format(self):
        return self.format_combo.currentData() or self.format_combo.currentText()


class BlinkEntryDialog(QDialog):
    def __init__(self, image_path, taxonomy, selected_part, roi_candidates, parent=None, lang="en", remembered_parent_map=None):
        super().__init__(parent)
        self.lang = lang
        self.current_theme = getattr(parent, "current_theme", "dark")
        self.remembered_parent_map = dict(remembered_parent_map or {})
        self.setWindowTitle(tr("Enter Child Expert Session", self.lang))
        self.setModal(True)
        self.resize(520, 220)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr("Image: {0}", self.lang).format(os.path.basename(image_path))))

        target_row = QHBoxLayout()
        target_row.addWidget(QLabel(tr("Target Part:", self.lang)))
        self.target_combo = NoWheelComboBox()
        for part in taxonomy:
            self.target_combo.addItem(tr(part, self.lang), part)
        selected_idx = self.target_combo.findData(selected_part)
        if selected_idx >= 0:
            self.target_combo.setCurrentIndex(selected_idx)
        target_row.addWidget(self.target_combo)
        layout.addLayout(target_row)

        roi_row = QHBoxLayout()
        roi_row.addWidget(QLabel(tr("Entry ROI:", self.lang)))
        self.roi_combo = NoWheelComboBox()
        for candidate in roi_candidates:
            source = candidate.get("source")
            if source == "manual":
                source_text = tr("Manual Box", self.lang)
            elif source == "vlm":
                source_text = tr("VLM Draft Box", self.lang)
            else:
                source_text = tr("Model Prediction Box", self.lang)
            label = f"{tr(candidate.get('part', 'ROI'), self.lang)} ({source_text})"
            self.roi_combo.addItem(label, candidate)
        roi_row.addWidget(self.roi_combo)
        layout.addLayout(roi_row)

        self.tip_label = QLabel(
            tr("Target Part is the child part you want to refine. Entry ROI is the parent/context region Blink will zoom into. This project remembers the parent/context ROI you chose for each target part, and later Blink entries reuse that remembered context.", self.lang)
        )
        self.tip_label.setWordWrap(True)
        layout.addWidget(self.tip_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons = buttons
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.set_theme(self.current_theme)
        layout.addWidget(buttons)

        self.target_combo.currentIndexChanged.connect(self._sync_preferred_roi)
        self._sync_preferred_roi(self.target_combo.currentIndex())

    def set_theme(self, theme):
        self.current_theme = theme
        apply_theme_dialog_button_box_style(
            getattr(self, "buttons", None),
            ok_role=BUTTON_ROLE_RUN,
            cancel_role=BUTTON_ROLE_STOP,
            theme=theme,
        )

    def _sync_preferred_roi(self, _index):
        target_part = self.target_combo.currentData() or self.target_combo.currentText()
        remembered_parent = self.remembered_parent_map.get(str(target_part or "").strip())
        for preferred_part in _blink_preferred_roi_parts(target_part, remembered_parent):
            for idx in range(self.roi_combo.count()):
                candidate = self.roi_combo.itemData(idx)
                if isinstance(candidate, dict) and candidate.get("part") == preferred_part:
                    self.roi_combo.setCurrentIndex(idx)
                    return

        self.roi_combo.setCurrentIndex(-1)

    def get_session_spec(self, image_path):
        focus_roi = self.roi_combo.currentData()
        if not isinstance(focus_roi, dict):
            return None

        target_part = self.target_combo.currentData() or self.target_combo.currentText().strip()
        if not target_part:
            return None

        return {
            "image_path": image_path,
            "target_part": target_part,
            "focus_roi": focus_roi,
        }


class LiteratureDescriptionDialog(QDialog):
    def __init__(
        self,
        *,
        db_path,
        context,
        image_path,
        current_part,
        taxon_hint,
        parent=None,
        lang="en",
    ):
        super().__init__(parent)
        self.lang = lang
        self.current_theme = getattr(parent, "current_theme", "dark")
        self.db_path = str(db_path or "")
        self.context = dict(context or {})
        self.image_path = str(image_path or "")
        self.current_part = str(current_part or "")
        self.taxon_hint = str(taxon_hint or "")
        self.records = []
        self.raw_records = []
        self.selected_record = None
        self.selected_raw_record = None
        self.action_mode = "replace"

        self.setWindowTitle(tr("Literature Trait Descriptions", self.lang))
        self.setModal(True)
        self.resize(980, 680)

        layout = QVBoxLayout(self)
        self.source_label = QLabel(self._source_summary_text())
        self.source_label.setWordWrap(True)
        self.source_label.setObjectName("mutedLabel")
        layout.addWidget(self.source_label)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel(tr("Search Part:", self.lang)))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(tr("pronotum / 前胸背板 / propodeum ...", self.lang))
        self.search_edit.setText(self.current_part)
        search_row.addWidget(self.search_edit, 1)
        self.btn_search = QPushButton(tr("Search", self.lang))
        self.btn_search.clicked.connect(self.refresh_records)
        search_row.addWidget(self.btn_search)
        layout.addLayout(search_row)

        raw_scope_row = QHBoxLayout()
        raw_scope_row.addWidget(QLabel(tr("Raw Search Scope:", self.lang)))
        self.raw_scope_combo = QComboBox()
        self.raw_scope_combo.addItem(tr("Current Taxon First", self.lang), "taxon")
        self.raw_scope_combo.addItem(tr("Whole Current PDF", self.lang), "pdf")
        self.raw_scope_combo.currentIndexChanged.connect(self.refresh_raw_records)
        raw_scope_row.addWidget(self.raw_scope_combo)
        raw_scope_row.addStretch()
        layout.addLayout(raw_scope_row)

        self.result_tabs = QTabWidget()
        self.table = QTableWidget(0, 7)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setHorizontalHeaderLabels(
            [
                tr("Taxon", self.lang),
                tr("Caste", self.lang),
                tr("Part", self.lang),
                tr("Pages", self.lang),
                tr("Conf.", self.lang),
                tr("Status", self.lang),
                tr("Description", self.lang),
            ]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.Stretch)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.result_tabs.addTab(self.table, tr("Structured Descriptions", self.lang))

        self.raw_table = QTableWidget(0, 6)
        self.raw_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.raw_table.setSelectionMode(QTableWidget.SingleSelection)
        self.raw_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.raw_table.setHorizontalHeaderLabels(
            [
                tr("Page", self.lang),
                tr("Block", self.lang),
                tr("Taxon", self.lang),
                tr("Role", self.lang),
                tr("Conf.", self.lang),
                tr("Text", self.lang),
            ]
        )
        raw_header = self.raw_table.horizontalHeader()
        raw_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        raw_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        raw_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        raw_header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        raw_header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        raw_header.setSectionResizeMode(5, QHeaderView.Stretch)
        self.raw_table.itemSelectionChanged.connect(self._on_raw_selection_changed)
        self.result_tabs.addTab(self.raw_table, tr("Raw Text Blocks", self.lang))
        self.result_tabs.currentChanged.connect(self._on_result_tab_changed)
        layout.addWidget(self.result_tabs, 1)

        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMinimumHeight(150)
        self.preview.setObjectName("LinkedDescriptionBox")
        layout.addWidget(self.preview)

        button_row = QHBoxLayout()
        self.btn_replace = QPushButton(tr("Replace Current Description", self.lang))
        self.btn_replace.clicked.connect(self.accept_replace)
        self.btn_append = QPushButton(tr("Append to Current Description", self.lang))
        self.btn_append.clicked.connect(self.accept_append)
        self.btn_close = QPushButton(tr("Close", self.lang))
        self.btn_close.clicked.connect(self.reject)
        button_row.addStretch()
        button_row.addWidget(self.btn_replace)
        button_row.addWidget(self.btn_append)
        button_row.addWidget(self.btn_close)
        layout.addLayout(button_row)

        self.search_edit.returnPressed.connect(self.refresh_records)
        self.set_theme(self.current_theme)
        self.refresh_records()

    def set_theme(self, theme):
        self.current_theme = theme
        apply_theme_button_style(getattr(self, "btn_search", None), BUTTON_ROLE_NEUTRAL, "", theme)
        apply_theme_button_style(getattr(self, "btn_replace", None), BUTTON_ROLE_COMMIT, "", theme)
        apply_theme_button_style(getattr(self, "btn_append", None), BUTTON_ROLE_NEUTRAL, "", theme)
        apply_theme_button_style(getattr(self, "btn_close", None), BUTTON_ROLE_STOP, "", theme)

    def refresh_records(self):
        self.records = query_literature_part_descriptions(
            self.db_path,
            context=self.context,
            current_part=self.current_part,
            search_text=self.search_edit.text(),
            taxon_hint=self.taxon_hint,
        )
        self.raw_records = query_literature_text_blocks(
            self.db_path,
            context=self.context,
            current_part=self.current_part,
            search_text=self.search_edit.text(),
            taxon_hint=self.taxon_hint,
            scope=self.raw_scope_combo.currentData() or "taxon",
        )
        self._populate_table()
        self._populate_raw_table()

    def refresh_raw_records(self):
        self.raw_records = query_literature_text_blocks(
            self.db_path,
            context=self.context,
            current_part=self.current_part,
            search_text=self.search_edit.text(),
            taxon_hint=self.taxon_hint,
            scope=self.raw_scope_combo.currentData() or "taxon",
        )
        self._populate_raw_table()

    def selected_description_text(self):
        if self._active_result_kind() == "raw":
            record = self.selected_raw_record or {}
            return str(record.get("text_content", "") or "").strip()
        record = self.selected_record or {}
        return str(record.get("description_text", "") or "").strip()

    def selected_source(self):
        if self._active_result_kind() == "raw":
            if not self.selected_raw_record:
                return {}
            return build_text_block_source(self.selected_raw_record, self.context)
        if not self.selected_record:
            return {}
        return build_description_source(self.selected_record, self.context)

    def accept_replace(self):
        if not self._has_active_selection():
            return
        self.action_mode = "replace"
        self.accept()

    def accept_append(self):
        if not self._has_active_selection():
            return
        self.action_mode = "append"
        self.accept()

    def _populate_table(self):
        self.table.setRowCount(0)
        self.selected_record = None
        self.preview.clear()
        for row_index, record in enumerate(self.records):
            self.table.insertRow(row_index)
            values = [
                record.get("taxon_name", ""),
                record.get("caste_or_stage", ""),
                f"{record.get('part_label', '')} / {record.get('part_key', '')}",
                ", ".join(str(page) for page in record.get("source_pages", []) or []),
                f"{float(record.get('confidence') or 0.0):.3f}",
                record.get("review_status", ""),
                self._short_text(record.get("description_text", "")),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value or ""))
                item.setData(Qt.UserRole, row_index)
                self.table.setItem(row_index, column, item)
        if self.records:
            self.table.selectRow(0)
        else:
            self._sync_action_buttons()
            self.preview.setPlainText(tr("No literature description matched the current image, taxon, and part search.", self.lang))

    def _populate_raw_table(self):
        self.raw_table.setRowCount(0)
        self.selected_raw_record = None
        for row_index, record in enumerate(self.raw_records):
            self.raw_table.insertRow(row_index)
            values = [
                record.get("page_number", ""),
                record.get("block_ref", ""),
                record.get("llm_taxon_name", ""),
                record.get("llm_role", "") or record.get("section_hint", "") or record.get("text_type", ""),
                f"{float(record.get('llm_confidence') or 0.0):.3f}",
                self._short_text(record.get("text_content", "")),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value or ""))
                item.setData(Qt.UserRole, row_index)
                self.raw_table.setItem(row_index, column, item)
        if self.raw_records:
            self.raw_table.selectRow(0)
        else:
            self._sync_action_buttons()
            if self._active_result_kind() == "raw":
                self.preview.setPlainText(tr("No raw PDF text block matched the current search. Try Whole Current PDF or broader terms.", self.lang))

    def _on_selection_changed(self):
        selected = self.table.selectedItems()
        if not selected:
            self.selected_record = None
            self.preview.clear()
            self._sync_action_buttons()
            return
        row_index = selected[0].data(Qt.UserRole)
        try:
            self.selected_record = self.records[int(row_index)]
        except Exception:
            self.selected_record = None
        self._sync_preview()
        self._sync_action_buttons()

    def _on_raw_selection_changed(self):
        selected = self.raw_table.selectedItems()
        if not selected:
            self.selected_raw_record = None
            if self._active_result_kind() == "raw":
                self.preview.clear()
            self._sync_action_buttons()
            return
        row_index = selected[0].data(Qt.UserRole)
        try:
            self.selected_raw_record = self.raw_records[int(row_index)]
        except Exception:
            self.selected_raw_record = None
        if self._active_result_kind() == "raw":
            self._sync_preview()
        self._sync_action_buttons()

    def _sync_preview(self):
        if self._active_result_kind() == "raw":
            self._sync_raw_preview()
            return
        record = self.selected_record or {}
        if not record:
            self.preview.clear()
            return
        pages = ", ".join(str(page) for page in record.get("source_pages", []) or [])
        refs = ", ".join(str(ref) for ref in record.get("source_block_refs", []) or [])
        meta = (
            f"{record.get('taxon_name', '')} | {record.get('caste_or_stage', '')} | "
            f"{record.get('part_label', '')} / {record.get('part_key', '')}\n"
            f"{tr('Source PDF', self.lang)}: {record.get('file_name') or self.context.get('pdf_file') or ''}\n"
            f"{tr('Pages', self.lang)}: {pages} | refs: {refs} | "
            f"conf={float(record.get('confidence') or 0.0):.3f} | {record.get('review_status', '')}"
        )
        self.preview.setPlainText(f"{meta}\n\n{record.get('description_text', '')}")

    def _sync_raw_preview(self):
        record = self.selected_raw_record or {}
        if not record:
            self.preview.clear()
            return
        meta = (
            f"{tr('Source PDF', self.lang)}: {record.get('file_name') or self.context.get('pdf_file') or ''}\n"
            f"{tr('Page', self.lang)}: {record.get('page_number', '')} | "
            f"{tr('Block', self.lang)}: {record.get('block_ref', '')} | "
            f"{tr('Role', self.lang)}: {record.get('llm_role', '') or record.get('section_hint', '') or record.get('text_type', '')} | "
            f"conf={float(record.get('llm_confidence') or 0.0):.3f}\n"
            f"{tr('Taxon', self.lang)}: {record.get('llm_taxon_name', '') or self.context.get('species_candidate') or ''}"
        )
        self.preview.setPlainText(f"{meta}\n\n{record.get('text_content', '')}")

    def _sync_action_buttons(self):
        enabled = bool(self.selected_raw_record) if self._active_result_kind() == "raw" else bool(self.selected_record)
        self.btn_replace.setEnabled(enabled)
        self.btn_append.setEnabled(enabled)

    def _on_result_tab_changed(self, _index):
        self._sync_preview()
        self._sync_action_buttons()

    def _has_active_selection(self):
        return bool(self.selected_raw_record) if self._active_result_kind() == "raw" else bool(self.selected_record)

    def _active_result_kind(self):
        if getattr(self, "result_tabs", None) is not None and self.result_tabs.currentWidget() == getattr(self, "raw_table", None):
            return "raw"
        return "structured"

    def _source_summary_text(self):
        pieces = [
            f"{tr('Image', self.lang)}: {os.path.basename(self.image_path)}",
            f"{tr('Source Mode', self.lang)}: {self._source_mode_label()}",
            f"{tr('PDF', self.lang)}: {self.context.get('pdf_file') or tr('Unknown', self.lang)}",
            f"{tr('Taxon', self.lang)}: {self.context.get('species_candidate') or self.taxon_hint or tr('Unknown', self.lang)}",
            f"{tr('Current Part', self.lang)}: {self.current_part or tr('Unknown', self.lang)}",
        ]
        summary = " | ".join(pieces)
        if self.context.get("link_mode") == "taxon_match_not_image_provenance":
            summary = f"{summary}\n{tr('This image is not linked to the selected PDF figure. Descriptions are matched by the current image taxon name only.', self.lang)}"
        return summary

    def _source_mode_label(self):
        if self.context.get("link_mode") == "taxon_match_not_image_provenance":
            return tr("Same-taxon literature reference", self.lang)
        return tr("Current image PDF source", self.lang)

    @staticmethod
    def _short_text(value, limit=160):
        text = " ".join(str(value or "").split())
        if len(text) <= limit:
            return text
        return text[: limit - 3] + "..."
