import csv
import json
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    from AntSleap.core.platform_open import open_path
    from AntSleap.core.training_preflight import describe_part_coverage, format_size_pair
    from AntSleap.ui.main_window_dialog_support import (
        _translate_training_warning_text,
        _translate_validation_provenance,
        _yes_no_text,
    )
    from AntSleap.ui.main_window_i18n import tr, ui_text
    from AntSleap.ui.main_window_widgets import NoWheelComboBox, NoWheelSlider
    from AntSleap.ui.style import (
        BUTTON_ROLE_NEUTRAL,
        BUTTON_ROLE_RUN,
        BUTTON_ROLE_STOP,
        apply_semantic_button_style,
        apply_theme_dialog_button_box_style,
    )
except ImportError:
    from core.platform_open import open_path
    from core.training_preflight import describe_part_coverage, format_size_pair
    from ui.main_window_dialog_support import (
        _translate_training_warning_text,
        _translate_validation_provenance,
        _yes_no_text,
    )
    from ui.main_window_i18n import tr, ui_text
    from ui.main_window_widgets import NoWheelComboBox, NoWheelSlider
    from ui.style import (
        BUTTON_ROLE_NEUTRAL,
        BUTTON_ROLE_RUN,
        BUTTON_ROLE_STOP,
        apply_semantic_button_style,
        apply_theme_dialog_button_box_style,
    )


class TrainingPreflightDialog(QDialog):
    def __init__(self, preflight, parent=None, lang="en"):
        super().__init__(parent)
        self.lang = lang
        self.preflight = dict(preflight or {})
        self.current_theme = getattr(parent, "current_theme", "dark")
        self._accepted = False
        self._accepted_mixed_resolution = False
        self.setWindowTitle(tr("Training Preflight", self.lang))
        self.resize(920, 760)

        layout = QVBoxLayout(self)

        intro = QLabel(
            tr(
                "Training will use only saved annotations and image files. View/manifest gating is no longer used in the main Train Models path.",
                self.lang,
            )
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.summary_label = QLabel(self._build_overall_summary())
        self.summary_label.setWordWrap(True)
        self.summary_label.setObjectName("mutedLabel")
        layout.addWidget(self.summary_label)

        tabs = QTabWidget()
        tabs.addTab(self._build_overview_tab(), ui_text("Overview", self.lang))
        tabs.addTab(self._build_coverage_tab(), ui_text("Coverage", self.lang))
        tabs.addTab(self._build_warnings_tab(), ui_text("Warnings", self.lang))
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons = buttons
        self.btn_train = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.btn_cancel = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        self.btn_train.setText(tr("Train anyway", self.lang))
        self.btn_cancel.setText(tr("Cancel", self.lang))
        self.set_theme(self.current_theme)
        buttons.accepted.connect(self._accept_training)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def set_theme(self, theme):
        self.current_theme = theme
        apply_theme_dialog_button_box_style(
            getattr(self, "buttons", None),
            ok_role=BUTTON_ROLE_RUN,
            cancel_role=BUTTON_ROLE_STOP,
            theme=theme,
        )

    def _ui(self, text):
        return ui_text(text, self.lang)

    def _translate_warning(self, text):
        return _translate_training_warning_text(text, self.lang)

    def _warnings_text(self):
        warnings = list(self.preflight.get("warnings", []))
        excluded_sections = [
            ("Missing images", self.preflight.get("excluded_missing_images", [])),
            ("Unreadable images", self.preflight.get("excluded_invalid_images", [])),
            ("Zero-annotation images", self.preflight.get("excluded_zero_annotation_images", [])),
            ("Invalid-annotation images", self.preflight.get("excluded_invalid_annotation_images", [])),
        ]
        lines = []
        if warnings:
            lines.append(self._ui("Warnings:"))
            lines.extend(f"- {self._translate_warning(warning)}" for warning in warnings)
        else:
            lines.append(self._ui("No warnings. The current saved annotations satisfy the training gate."))
        for title, values in excluded_sections:
            if values:
                lines.append("")
                lines.append(f"{self._ui(title)}:")
                lines.extend(f"- {os.path.basename(str(value))}" for value in values)
        return "\n".join(lines)
    def _build_overall_summary(self):
        locator_count = int(self.preflight.get("locator_image_count", 0))
        parts_count = int(self.preflight.get("parts_image_count", 0))
        locator_ready = self._ui("Ready") if locator_count > 0 else self._ui("Skipped")
        sam_ready = self._ui("Ready") if parts_count > 0 else self._ui("Skipped")
        selected_locator_size = format_size_pair(self.preflight.get("selected_locator_size"))
        if self.preflight.get("mixed_native_resolutions"):
            mixed_note = tr("Mixed native image resolutions detected among locator-eligible images. Training will unify them to the smallest native resolution tier among eligible images: {0}. Continue?", self.lang).format(selected_locator_size)
        else:
            mixed_note = self._ui("Mixed-resolution decision: locator training will use {0}.").format(selected_locator_size)
        return (
            f"{self._ui('Locator stage: {0} | SAM stage: {1}').format(locator_ready, sam_ready)}\n"
            f"{self._ui('Locator size: {0}').format(selected_locator_size)}\n"
            f"{mixed_note}"
        )

    def _make_readonly_text(self, text):
        box = QTextEdit()
        box.setReadOnly(True)
        box.setPlainText(text)
        box.setMinimumHeight(160)
        return box

    def _coverage_lines(self, title, total_count, train_count, val_count, total_text, train_text, val_text):
        lines = [
            self._ui(title),
            f"  {self._ui('total images: {0}').format(total_count)}",
            f"  {self._ui('train images: {0}').format(train_count)}",
            f"  {self._ui('val images: {0}').format(val_count)}",
            f"  {self._ui('total coverage: {0}').format(total_text)}",
            f"  {self._ui('train coverage: {0}').format(train_text)}",
            f"  {self._ui('val coverage: {0}').format(val_text)}",
        ]
        return "\n".join(lines)

    def _build_overview_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        selected_locator_size = format_size_pair(self.preflight.get("selected_locator_size"))
        locator_size_summary = str(self.preflight.get("locator_size_summary", "none") or "none")
        overview_lines = [
            self._ui("Training scope: {0}").format(
                f"{self.preflight.get('training_scope_label', self._ui('All Images'))} ({int(self.preflight.get('training_scope_image_count', 0) or 0)})"
            ),
            self._ui("Locator eligible images: {0}").format(int(self.preflight.get('locator_image_count', 0))),
            self._ui("SAM/parts eligible images: {0}").format(int(self.preflight.get('parts_image_count', 0))),
            self._ui("Selected locator size: {0}").format(selected_locator_size),
            self._ui("Eligible locator native sizes: {0}").format(locator_size_summary),
            self._ui("Mixed native resolutions: {0}").format(_yes_no_text(self.preflight.get('mixed_native_resolutions'), self.lang)),
        ]
        layout.addWidget(self._make_readonly_text("\n".join(overview_lines)))
        return tab

    def _build_coverage_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        locator_text = self._coverage_lines(
            "Locator coverage",
            int(self.preflight.get("locator_image_count", 0)),
            len(self.preflight.get("locator_train_data", []) or []),
            len(self.preflight.get("locator_val_data", []) or []),
            describe_part_coverage(self.preflight.get("locator_part_counts", {}), self.preflight.get("locator_scope", [])),
            describe_part_coverage(self.preflight.get("locator_train_part_counts", {}), self.preflight.get("locator_scope", [])),
            describe_part_coverage(self.preflight.get("locator_val_part_counts", {}), self.preflight.get("locator_scope", [])),
        )
        parts_text = self._coverage_lines(
            "SAM / parts coverage",
            int(self.preflight.get("parts_image_count", 0)),
            len(self.preflight.get("parts_train_data", []) or []),
            len(self.preflight.get("parts_val_data", []) or []),
            describe_part_coverage(self.preflight.get("parts_part_counts", {}), self.preflight.get("taxonomy", [])),
            describe_part_coverage(self.preflight.get("parts_train_part_counts", {}), self.preflight.get("taxonomy", [])),
            describe_part_coverage(self.preflight.get("parts_val_part_counts", {}), self.preflight.get("taxonomy", [])),
        )
        layout.addWidget(self._make_readonly_text(locator_text + "\n\n" + parts_text))
        return tab

    def _build_warnings_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(self._make_readonly_text(self._warnings_text()))
        return tab

    def _accept_training(self):
        self._accepted = True
        self._accepted_mixed_resolution = not bool(self.preflight.get("mixed_native_resolutions"))
        self.accept()

    def accepted_training(self):
        return self._accepted

    def accepted_mixed_resolution(self):
        return self._accepted_mixed_resolution

class TrainingReportDialog(QDialog):
    def __init__(self, report_data, parent=None, lang="en"):
        super().__init__(parent)
        self.lang = lang
        self.setWindowTitle(tr("Training Report & Validation", self.lang))
        self.resize(1200, 800)
        self.report_data = dict(report_data or {})
        self.validation_rows = self._load_validation_rows()
        self.filtered_validation_rows = list(self.validation_rows)
        self.report_summary = self._load_report_summary()

        layout = QVBoxLayout(self)

        tabs = QTabWidget()

        tab_summary = QWidget()
        summary_layout = QVBoxLayout(tab_summary)
        self.summary_box = QTextEdit()
        self.summary_box.setReadOnly(True)
        self.summary_box.setPlainText(self._build_summary_text())
        summary_layout.addWidget(self.summary_box)
        tabs.addTab(tab_summary, tr("Summary", self.lang))

        # Tab 1: Metrics Plot
        tab_metrics = QWidget()
        layout_m = QVBoxLayout(tab_metrics)
        self.lbl_metrics = QLabel(tr("No Metrics Generated", self.lang))
        self.lbl_metrics.setAlignment(Qt.AlignCenter)
        if report_data.get('metrics') and os.path.exists(report_data['metrics']):
            from PySide6.QtGui import QPixmap
            pix = QPixmap(report_data['metrics'])
            self.lbl_metrics.setPixmap(pix.scaled(1000, 700, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout_m.addWidget(self.lbl_metrics)
        tabs.addTab(tab_metrics, tr("Training Metrics", self.lang))

        # Tab 2: Validation Samples
        tab_val = QWidget()
        layout_v = QVBoxLayout(tab_val)

        # Controls for deterministic browsing
        ctrl_layout = QHBoxLayout()
        ctrl_layout.addWidget(QLabel(tr("Show Validation Set %:", self.lang)))

        self.slider_pct = NoWheelSlider(Qt.Horizontal)
        self.slider_pct.setRange(5, 100)
        self.slider_pct.setValue(20)
        self.slider_pct.setTickPosition(QSlider.TicksBelow)
        self.slider_pct.setTickInterval(10)

        self.lbl_pct = QLabel("20%")
        self.slider_pct.valueChanged.connect(lambda v: self.lbl_pct.setText(f"{v}%"))

        ctrl_layout.addWidget(self.slider_pct)
        ctrl_layout.addWidget(self.lbl_pct)

        self.validation_filter = NoWheelComboBox()
        self.validation_filter.addItem(tr("All validation", self.lang), "all")
        self.validation_filter.addItem(tr("Macro locator", self.lang), "macro_locator")
        self.validation_filter.currentIndexChanged.connect(self.load_gallery)
        ctrl_layout.addWidget(self.validation_filter)

        btn_load = QPushButton(tr("Load Samples", self.lang))
        btn_load.clicked.connect(self.load_gallery)
        ctrl_layout.addWidget(btn_load)
        ctrl_layout.addStretch()

        layout_v.addLayout(ctrl_layout)

        # Scroll Area
        scroll_v = QScrollArea()
        scroll_v.setWidgetResizable(True)
        self.content_v = QWidget()
        self.layout_gallery = QVBoxLayout(self.content_v) # Main layout for scroll content

        # 1. Initial Summary Image
        self.lbl_val = QLabel(tr("No Validation Summary", self.lang))
        self.lbl_val.setAlignment(Qt.AlignCenter)
        if report_data.get('val') and os.path.exists(report_data['val']):
            from PySide6.QtGui import QPixmap
            pix = QPixmap(report_data['val'])
            self.lbl_val.setPixmap(pix)
            self.layout_gallery.addWidget(QLabel(tr("--- Initial Summary (Top 6) ---", self.lang)))
            self.layout_gallery.addWidget(self.lbl_val)

        self.validation_index_table = QTableWidget(0, 5)
        self.validation_index_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.validation_index_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.validation_index_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.validation_index_table.setAlternatingRowColors(True)
        self.validation_index_table.verticalHeader().setVisible(False)
        self.validation_index_table.horizontalHeader().setStretchLastSection(True)
        self.validation_index_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.validation_index_table.setHorizontalHeaderLabels([
            ui_text("ID", self.lang),
            ui_text("Image", self.lang),
            ui_text("Source", self.lang),
            ui_text("Valid Parts", self.lang),
            ui_text("Max Error(px)", self.lang),
        ])
        self.validation_index_table.itemSelectionChanged.connect(self._load_selected_detail_preview)
        layout_v.addWidget(self.validation_index_table)

        # 2. Dynamic Grid Placeholder
        self.grid_widget = QWidget()
        self.grid_layout = None # Will be created on load
        self.layout_gallery.addWidget(QLabel(tr("--- Detailed Inspection ---", self.lang)))
        self.layout_gallery.addWidget(self.grid_widget)
        self.layout_gallery.addStretch()

        scroll_v.setWidget(self.content_v)
        layout_v.addWidget(scroll_v)
        tabs.addTab(tab_val, tr("Validation Inspection", self.lang))

        layout.addWidget(tabs)

        # Bottom Buttons
        btn_layout = QHBoxLayout()
        btn_open = QPushButton(tr("Open Report Folder", self.lang))
        btn_open.clicked.connect(self.open_folder)
        btn_close = QPushButton(tr("Close", self.lang))
        btn_close.clicked.connect(self.accept)

        btn_layout.addWidget(btn_open)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

        self.load_gallery()

    def _ui(self, text):
        return ui_text(text, self.lang)

    def _load_report_summary(self):
        summary_path = self.report_data.get("report_summary")
        if summary_path and os.path.exists(summary_path):
            try:
                with open(summary_path, "r", encoding="utf-8") as handle:
                    loaded = json.load(handle)
                    if isinstance(loaded, dict):
                        return loaded
            except Exception:
                pass
        summary = self.report_data.get("validation_summary")
        return dict(summary or {})

    def _load_validation_rows(self):
        if isinstance(self.report_data.get("validation_rows"), list):
            return [dict(row) for row in self.report_data.get("validation_rows", []) if isinstance(row, dict)]
        index_path = self.report_data.get("validation_index")
        rows = []
        if index_path and os.path.exists(index_path):
            try:
                with open(index_path, "r", encoding="utf-8", newline="") as handle:
                    reader = csv.DictReader(handle)
                    for row in reader:
                        rows.append(dict(row))
            except Exception:
                pass
        return rows

    def _build_summary_text(self):
        lines = []
        if self.report_summary:
            context = self.report_summary.get("training_context") if isinstance(self.report_summary.get("training_context"), dict) else {}
            training_scope = context.get("training_scope") if isinstance(context.get("training_scope"), dict) else {}
            if training_scope:
                lines.append(
                    tr("Training scope: {0} ({1} image(s))", self.lang).format(
                        training_scope.get("label", self._ui("All Images")),
                        training_scope.get("image_count", 0),
                    )
                )
            lines.append(self._ui("Validation count: {0}").format(self.report_summary.get('validation_count', 0)))
            lines.append(self._ui("Preview count: {0}").format(self.report_summary.get('validation_preview_count', 0)))
            provenance_counts = self.report_summary.get("validation_provenance_counts", {}) or {}
            if provenance_counts:
                lines.append(self._ui("Provenance counts:"))
                for key, value in sorted(provenance_counts.items()):
                    lines.append(f"- {_translate_validation_provenance(key, self.lang)}: {value}")
            metrics_name = self.report_summary.get("metrics_plot")
            if metrics_name:
                lines.append(self._ui("Metrics plot: {0}").format(metrics_name))
            validation_index = self.report_summary.get("validation_index_csv")
            if validation_index:
                lines.append(self._ui("Validation index: {0}").format(validation_index))
        else:
            lines.append(self._ui("No structured report summary found."))

        if self.validation_rows:
            lines.append("")
            lines.append(self._ui("Validation samples:"))
            for row in self.validation_rows[:10]:
                lines.append(
                    f"- {row.get('sample_id', '')}: {row.get('image_name', '')} | {_translate_validation_provenance(row.get('provenance', ''), self.lang)} | {row.get('error_summary', '')}"
                )
        return "\n".join(lines)

    def _current_filtered_rows(self):
        filter_value = self.validation_filter.currentData() if hasattr(self, "validation_filter") else "all"
        if filter_value in (None, "all"):
            return list(self.validation_rows)
        return [row for row in self.validation_rows if row.get("provenance") == filter_value]

    def _detail_image_path(self, row):
        details_dir = self.report_data.get("details_dir") or os.path.join(self.report_data.get("dir", ""), "val_details")
        detail_name = row.get("detail_image") if isinstance(row, dict) else None
        if not detail_name:
            return None
        path = os.path.join(details_dir, detail_name)
        return path if os.path.exists(path) else None

    def _rebuild_gallery_grid(self, selected_rows):
        if self.grid_layout:
            while self.grid_layout.count():
                item = self.grid_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
            QWidget().setLayout(self.grid_layout)

        from PySide6.QtWidgets import QGridLayout
        from PySide6.QtGui import QPixmap

        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(10)
        row_idx = 0
        col_idx = 0
        max_cols = 3
        for row in selected_rows:
            detail_path = self._detail_image_path(row)
            if not detail_path:
                continue
            label = QLabel()
            pix = QPixmap(detail_path)
            if pix.width() > 400:
                pix = pix.scaledToWidth(400, Qt.SmoothTransformation)
            label.setPixmap(pix)
            label.setToolTip(f"{row.get('sample_id', '')} | {row.get('image_name', '')}")
            self.grid_layout.addWidget(label, row_idx, col_idx)
            col_idx += 1
            if col_idx >= max_cols:
                col_idx = 0
                row_idx += 1

    def _populate_validation_index_table(self, selected_rows):
        self.validation_index_table.setRowCount(len(selected_rows))
        for row_idx, row in enumerate(selected_rows):
            values = [
                row.get("sample_id", ""),
                row.get("image_name", ""),
                _translate_validation_provenance(row.get("provenance", ""), self.lang),
                row.get("valid_parts", ""),
                row.get("max_error_px", ""),
            ]
            for col_idx, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, dict(row))
                self.validation_index_table.setItem(row_idx, col_idx, item)

    def _load_selected_detail_preview(self):
        current_row = self.validation_index_table.currentRow()
        if current_row < 0:
            return
        item = self.validation_index_table.item(current_row, 0)
        if not item:
            return
        row = item.data(Qt.UserRole)
        if not isinstance(row, dict):
            return
        self._rebuild_gallery_grid([row])

    def load_gallery(self):
        val_dir = self.report_data.get("details_dir") or os.path.join(self.report_data.get('dir', ''), "val_details")
        if not os.path.exists(val_dir):
            QMessageBox.warning(self, tr("Error", self.lang), tr("No validation details found at {0}", self.lang).format(val_dir))
            return

        if not self.validation_rows:
            QMessageBox.warning(self, tr("Error", self.lang), tr("No images found.", self.lang))
            return

        filtered_rows = self._current_filtered_rows()
        if not filtered_rows:
            self.filtered_validation_rows = []
            self.validation_index_table.setRowCount(0)
            self._rebuild_gallery_grid([])
            self.lbl_pct.setText(tr("{0}% ({1} images)", self.lang).format(self.slider_pct.value(), 0))
            return

        pct = self.slider_pct.value()
        count = max(1, int(len(filtered_rows) * (pct / 100.0)))
        selected_rows = filtered_rows[:count]
        self.filtered_validation_rows = list(selected_rows)
        self._populate_validation_index_table(selected_rows)
        self._rebuild_gallery_grid(selected_rows[: min(6, len(selected_rows))])
        if selected_rows:
            self.validation_index_table.setCurrentCell(0, 0)
        self.lbl_pct.setText(tr("{0}% ({1} images)", self.lang).format(pct, count))

    def open_folder(self):
        d = self.report_data.get('dir')
        if d:
            open_path(d)

class TrainingResultBrowserDialog(QDialog):
    def __init__(self, reports, parent=None, lang="en", preview_callback=None, refresh_callback=None):
        super().__init__(parent)
        self.lang = lang
        self.reports = list(reports or [])
        self.preview_callback = preview_callback
        self.refresh_callback = refresh_callback
        self.setWindowTitle(tr("Training Result Browser", self.lang))
        self.resize(1120, 620)

        layout = QVBoxLayout(self)

        self.table = QTableWidget(0, 7)
        self.table.setObjectName("trainingResultBrowserTable")
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.setHorizontalHeaderLabels([
            tr("Type", self.lang),
            tr("Target", self.lang),
            tr("Backend", self.lang),
            tr("Strategy", self.lang),
            tr("Samples", self.lang),
            tr("Time", self.lang),
            tr("Report Folder", self.lang),
        ])
        self.table.itemSelectionChanged.connect(self._refresh_actions)
        self.table.doubleClicked.connect(lambda _index=None: self.preview_selected())
        layout.addWidget(self.table, 1)

        button_row = QHBoxLayout()
        self.btn_preview = QPushButton(tr("Preview Report", self.lang))
        self.btn_preview.clicked.connect(self.preview_selected)
        apply_semantic_button_style(self.btn_preview, BUTTON_ROLE_RUN)
        button_row.addWidget(self.btn_preview)
        self.btn_open_folder = QPushButton(tr("Open Report Folder", self.lang))
        self.btn_open_folder.clicked.connect(self.open_selected_folder)
        apply_semantic_button_style(self.btn_open_folder, BUTTON_ROLE_NEUTRAL)
        button_row.addWidget(self.btn_open_folder)

        self.btn_refresh = QPushButton(tr("Refresh", self.lang))
        self.btn_refresh.clicked.connect(self.refresh_reports)
        apply_semantic_button_style(self.btn_refresh, BUTTON_ROLE_NEUTRAL)
        button_row.addWidget(self.btn_refresh)

        button_row.addStretch()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_button = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_button:
            close_button.setText(tr("Close", self.lang))
        buttons.rejected.connect(self.reject)
        button_row.addWidget(buttons)
        layout.addLayout(button_row)

        self.populate(self.reports)

    def populate(self, reports):
        self.reports = list(reports or [])
        self.table.setRowCount(len(self.reports))
        for row_idx, report in enumerate(self.reports):
            values = [
                report.get("type_label", ""),
                report.get("target_label", ""),
                report.get("backend_label", ""),
                report.get("strategy_label", ""),
                report.get("samples_label", ""),
                report.get("time_label", ""),
                report.get("dir", ""),
            ]
            for col_idx, value in enumerate(values):
                item = QTableWidgetItem(str(value or ""))
                item.setToolTip(str(value or ""))
                item.setData(Qt.UserRole, dict(report))
                self.table.setItem(row_idx, col_idx, item)
        self.table.resizeColumnsToContents()
        if self.reports:
            self.table.setCurrentCell(0, 0)
        self._refresh_actions()

    def selected_report(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if not item:
            return None
        data = item.data(Qt.UserRole)
        return dict(data) if isinstance(data, dict) else None

    def _refresh_actions(self):
        has_selection = self.selected_report() is not None
        self.btn_preview.setEnabled(has_selection)
        self.btn_open_folder.setEnabled(has_selection)

    def preview_selected(self):
        report = self.selected_report()
        if report and callable(self.preview_callback):
            self.preview_callback(report)

    def open_selected_folder(self):
        report = self.selected_report()
        folder = report.get("dir") if isinstance(report, dict) else ""
        if folder:
            open_path(folder)

    def refresh_reports(self):
        if callable(self.refresh_callback):
            self.populate(self.refresh_callback() or [])
