import json
import os

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    from AntSleap.ui.tif_workbench_canvas import WheelSafeSpinBox
    from AntSleap.ui.tif_workbench_translations import tt
except ModuleNotFoundError as exc:
    if exc.name != "AntSleap":
        raise
    from ui.tif_workbench_canvas import WheelSafeSpinBox
    from ui.tif_workbench_translations import tt


class MaterialEditorDialog(QDialog):
    def __init__(self, material=None, next_id=1, parent=None, lang="en"):
        super().__init__(parent)
        self.lang = lang
        self.setWindowTitle(tt("Material", self.lang))
        material = dict(material or {})
        self.id_spin = WheelSafeSpinBox()
        self.id_spin.setRange(0, 65535)
        self.id_spin.setValue(int(material.get("id", next_id)))
        self.id_spin.setEnabled(not material)
        self.name_edit = QLineEdit(str(material.get("name", "")))
        self.display_edit = QLineEdit(str(material.get("display_name", material.get("name", ""))))
        self.color_edit = QLineEdit(str(material.get("color", "#f94144")))
        self.color_edit.setObjectName("tifMaterialColorValue")
        self.color_edit.setVisible(False)
        self.color_swatch = QLabel("")
        self.color_swatch.setObjectName("tifMaterialDialogColorSwatch")
        self.color_swatch.setFixedSize(44, 24)
        self.trainable_check = QCheckBox(tt("Trainable", self.lang))
        self.trainable_check.setChecked(bool(material.get("trainable", self.id_spin.value() != 0)))
        self.color_button = QPushButton(tt("Choose color", self.lang))
        self.color_button.clicked.connect(self.choose_color)
        self._update_color_swatch()

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow(tt("ID", self.lang), self.id_spin)
        form.addRow(tt("Name", self.lang), self.name_edit)
        form.addRow(tt("Display name", self.lang), self.display_edit)
        color_row = QHBoxLayout()
        color_row.addWidget(self.color_swatch)
        color_row.addWidget(self.color_button)
        color_row.addStretch(1)
        form.addRow(tt("Color", self.lang), color_row)
        form.addRow("", self.trainable_check)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def choose_color(self):
        color = QColorDialog.getColor(QColor(self.color_edit.text()), self, "Material color")
        if color.isValid():
            self.color_edit.setText(color.name())
            self._update_color_swatch()

    def _update_color_swatch(self):
        color = QColor(self.color_edit.text())
        if not color.isValid():
            color = QColor("#f94144")
            self.color_edit.setText(color.name())
        self.color_swatch.setToolTip(color.name())
        self.color_swatch.setStyleSheet(
            f"background-color: {color.name()}; border: 1px solid #D7E0E4; border-radius: 5px;"
        )

    def get_material(self):
        material_id = int(self.id_spin.value())
        name = self.name_edit.text().strip() or f"material_{material_id}"
        display_name = self.display_edit.text().strip() or name
        return {
            "id": material_id,
            "name": name,
            "display_name": display_name,
            "color": self.color_edit.text().strip(),
            "trainable": bool(self.trainable_check.isChecked() and material_id != 0),
            "source_name": display_name,
        }


class TifPartNameDialog(QDialog):
    def __init__(self, title, part_id="", display_name="", parent=None, lang="en", id_label="Part ID:"):
        super().__init__(parent)
        self.lang = lang
        self.setWindowTitle(tt(title, self.lang))
        layout = QFormLayout(self)
        self.part_id_edit = QLineEdit(str(part_id or ""))
        self.display_name_edit = QLineEdit(str(display_name or part_id or ""))
        layout.addRow(tt(id_label, self.lang), self.part_id_edit)
        layout.addRow(tt("Display name:", self.lang), self.display_name_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def values(self):
        part_id = self.part_id_edit.text().strip()
        display_name = self.display_name_edit.text().strip() or part_id
        return part_id, display_name


def _safe_training_result_text(value):
    if isinstance(value, float):
        return f"{value:.4g}"
    if isinstance(value, (int, bool)):
        return str(value)
    if value is None:
        return "-"
    if isinstance(value, (list, tuple)):
        return ", ".join(_safe_training_result_text(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _flatten_training_metrics(value, prefix=""):
    rows = []
    if isinstance(value, dict):
        for key in sorted(value.keys(), key=lambda item: str(item)):
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            rows.extend(_flatten_training_metrics(value.get(key), child_prefix))
        return rows
    rows.append((prefix or "value", _safe_training_result_text(value)))
    return rows


def _artifact_absolute_path(result_json, artifact):
    path = str((artifact or {}).get("path") or "").strip()
    if not path:
        return ""
    if os.path.isabs(path):
        return os.path.normpath(path)
    base = os.path.dirname(os.path.abspath(str(result_json or ""))) if result_json else os.getcwd()
    return os.path.abspath(os.path.join(base, path))


def _result_relative_absolute_path(result_json, path):
    path = str(path or "").strip()
    if not path:
        return ""
    if os.path.isabs(path):
        return os.path.normpath(path)
    if result_json:
        return os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(result_json)), path))
    return os.path.abspath(path)


def summarize_tif_training_result(result, result_json="", run_dir=""):
    result = result if isinstance(result, dict) else {}
    result_json = str(result_json or result.get("_result_json") or "").strip()
    run_dir = str(run_dir or result.get("run_dir") or "").strip()
    if not run_dir and result_json:
        run_dir = os.path.dirname(os.path.abspath(result_json))
    metrics = result.get("metrics") if isinstance(result.get("metrics"), dict) else {}
    artifacts = []
    for artifact in result.get("artifacts", []) or []:
        if not isinstance(artifact, dict):
            continue
        item = dict(artifact)
        item["absolute_path"] = _artifact_absolute_path(result_json, item)
        artifacts.append(item)
    warnings = [str(item) for item in (result.get("warnings") or [])]
    errors = [str(item) for item in (result.get("errors") or [])]
    provenance = result.get("provenance") if isinstance(result.get("provenance"), dict) else {}
    model_manifest = _result_relative_absolute_path(result_json, provenance.get("model_manifest") or "")
    if not model_manifest:
        for artifact in artifacts:
            if str(artifact.get("type") or "") == "model_manifest" and artifact.get("absolute_path"):
                model_manifest = str(artifact.get("absolute_path") or "")
                break
    model_output = ""
    for artifact in artifacts:
        artifact_type = str(artifact.get("type") or "")
        artifact_path = str(artifact.get("absolute_path") or "")
        if artifact_type in {"model_output_dir", "model_dir", "checkpoint_dir"} and artifact_path:
            model_output = artifact_path
            break
    if not model_output:
        for artifact in artifacts:
            artifact_path = str(artifact.get("absolute_path") or "")
            if artifact_path and os.path.isdir(artifact_path):
                model_output = artifact_path
                break
    if not model_output and run_dir:
        candidate = os.path.join(run_dir, "outputs")
        if os.path.isdir(candidate):
            model_output = candidate
    curves = []
    previews = []
    for artifact in artifacts:
        artifact_type = str(artifact.get("type") or "").lower()
        artifact_format = str(artifact.get("format") or "").lower()
        artifact_path = str(artifact.get("path") or "").lower()
        is_image_like = artifact_format in {"png", "jpg", "jpeg", "svg", "html"}
        if artifact_type in {"training_curve", "training_curves", "loss_curve", "metric_curve"} or (is_image_like and "curve" in f"{artifact_type} {artifact_path}"):
            curves.append(artifact)
        if artifact_type in {"mask_preview", "sample_mask_preview", "prediction_preview", "validation_preview"} or "preview" in f"{artifact_type} {artifact_path}":
            previews.append(artifact)
    summary_metrics = _flatten_training_metrics(metrics)
    return {
        "action": str(result.get("action") or ""),
        "status": str(result.get("status") or ""),
        "backend_id": str(result.get("backend_id") or ""),
        "run_id": str(result.get("run_id") or ""),
        "run_dir": os.path.abspath(run_dir) if run_dir else "",
        "result_json": os.path.abspath(result_json) if result_json else "",
        "model_manifest": os.path.abspath(model_manifest) if model_manifest else "",
        "model_output": os.path.abspath(model_output) if model_output else "",
        "metrics": summary_metrics,
        "artifacts": artifacts,
        "curves": curves,
        "previews": previews,
        "warnings": warnings,
        "errors": errors,
        "provenance": provenance,
    }


class TifTrainingResultDialog(QDialog):
    def __init__(self, summary, lang="en", parent=None):
        super().__init__(parent)
        self.summary = summary if isinstance(summary, dict) else {}
        self.lang = lang
        self.setWindowTitle(tt("Training result summary", self.lang))
        self.resize(760, 620)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        header = QLabel(self._header_text())
        header.setWordWrap(True)
        layout.addWidget(header)

        self.metrics_table = QTableWidget(0, 2)
        self.metrics_table.setObjectName("tifTrainingResultMetricsTable")
        self.metrics_table.setHorizontalHeaderLabels([tt("Key metrics", self.lang), tt("Value", self.lang)])
        self.metrics_table.horizontalHeader().setStretchLastSection(True)
        self.metrics_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.metrics_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._populate_metrics()
        layout.addWidget(self.metrics_table, 1)

        artifact_label = QLabel(tt("Artifacts", self.lang))
        layout.addWidget(artifact_label)
        self.artifact_table = QTableWidget(0, 4)
        self.artifact_table.setObjectName("tifTrainingResultArtifactTable")
        self.artifact_table.setHorizontalHeaderLabels([tt("Type", self.lang), tt("Format", self.lang), tt("Path", self.lang), tt("Status", self.lang)])
        self.artifact_table.horizontalHeader().setStretchLastSection(True)
        self.artifact_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.artifact_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._populate_artifacts()
        layout.addWidget(self.artifact_table, 1)

        preview_header = QHBoxLayout()
        preview_header.addWidget(QLabel(tt("Training curves / mask previews", self.lang)))
        self.preview_percent_slider = QSlider(Qt.Horizontal)
        self.preview_percent_slider.setObjectName("tifTrainingResultPreviewPercentSlider")
        self.preview_percent_slider.setRange(5, 100)
        self.preview_percent_slider.setValue(20)
        self.preview_percent_slider.setTickPosition(QSlider.TicksBelow)
        self.preview_percent_slider.setTickInterval(10)
        self.preview_percent_label = QLabel("")
        self.preview_percent_label.setObjectName("tifTrainingResultPreviewPercentText")
        self.preview_percent_slider.valueChanged.connect(self._populate_preview_gallery)
        preview_header.addWidget(self.preview_percent_slider, 1)
        preview_header.addWidget(self.preview_percent_label)
        layout.addLayout(preview_header)

        self.preview_scroll = QScrollArea()
        self.preview_scroll.setObjectName("tifTrainingResultPreviewScroll")
        self.preview_scroll.setWidgetResizable(True)
        self.preview_scroll.setMinimumHeight(150)
        self.preview_body = QWidget()
        self.preview_body.setObjectName("tifTrainingResultPreviewGallery")
        self.preview_grid = QGridLayout(self.preview_body)
        self.preview_grid.setSpacing(10)
        self.preview_scroll.setWidget(self.preview_body)
        layout.addWidget(self.preview_scroll, 1)
        self._populate_preview_gallery()

        detail = QTextEdit()
        detail.setObjectName("tifTrainingResultDetailText")
        detail.setReadOnly(True)
        detail.setMinimumHeight(92)
        detail.setPlainText(self._detail_text())
        layout.addWidget(detail)

        button_row = QHBoxLayout()
        self.btn_open_run = QPushButton(tt("Open run folder", self.lang))
        self.btn_open_run.clicked.connect(lambda: self._open_path(self.summary.get("run_dir", "")))
        self.btn_open_run.setEnabled(bool(self.summary.get("run_dir")) and os.path.isdir(self.summary.get("run_dir", "")))
        self.btn_open_model_output = QPushButton(tt("Open model output", self.lang))
        self.btn_open_model_output.clicked.connect(lambda: self._open_path(self.summary.get("model_output", "")))
        self.btn_open_model_output.setEnabled(bool(self.summary.get("model_output")) and os.path.exists(self.summary.get("model_output", "")))
        self.btn_open_manifest = QPushButton(tt("Open model manifest", self.lang))
        self.btn_open_manifest.clicked.connect(lambda: self._open_path(self.summary.get("model_manifest", "")))
        self.btn_open_manifest.setEnabled(bool(self.summary.get("model_manifest")) and os.path.exists(self.summary.get("model_manifest", "")))
        button_row.addWidget(self.btn_open_run)
        button_row.addWidget(self.btn_open_model_output)
        button_row.addWidget(self.btn_open_manifest)
        button_row.addStretch(1)
        close_button = QPushButton(tt("Close", self.lang))
        close_button.clicked.connect(self.accept)
        button_row.addWidget(close_button)
        layout.addLayout(button_row)

    def _header_text(self):
        parts = [
            f"{tt('Status', self.lang)}: {self.summary.get('status') or '-'}",
            f"{tt('Backend ID', self.lang)}: {self.summary.get('backend_id') or '-'}",
            f"{tt('Run ID', self.lang)}: {self.summary.get('run_id') or '-'}",
        ]
        model_manifest = self.summary.get("model_manifest") or "-"
        parts.append(f"{tt('Model manifest', self.lang)}: {model_manifest}")
        return "\n".join(parts)

    def _populate_metrics(self):
        rows = list(self.summary.get("metrics") or [])
        if not rows:
            rows = [(tt("Key metrics", self.lang), "-")]
        self.metrics_table.setRowCount(len(rows))
        for row, (key, value) in enumerate(rows):
            self.metrics_table.setItem(row, 0, QTableWidgetItem(str(key)))
            self.metrics_table.setItem(row, 1, QTableWidgetItem(str(value)))
        self.metrics_table.resizeColumnsToContents()

    def _populate_artifacts(self):
        artifacts = list(self.summary.get("artifacts") or [])
        self.artifact_table.setRowCount(len(artifacts))
        for row, artifact in enumerate(artifacts):
            path = str(artifact.get("absolute_path") or artifact.get("path") or "")
            status = tt("exists", self.lang) if path and os.path.exists(path) else tt("missing", self.lang)
            self.artifact_table.setItem(row, 0, QTableWidgetItem(str(artifact.get("type") or "")))
            self.artifact_table.setItem(row, 1, QTableWidgetItem(str(artifact.get("format") or "")))
            self.artifact_table.setItem(row, 2, QTableWidgetItem(path))
            self.artifact_table.setItem(row, 3, QTableWidgetItem(status))
        self.artifact_table.resizeColumnsToContents()

    def _clear_preview_gallery(self):
        while self.preview_grid.count():
            item = self.preview_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _displayable_artifact_rows(self):
        rows = []
        for artifact in self.summary.get("curves") or []:
            rows.append((tt("Training curves", self.lang), artifact))
        previews = list(self.summary.get("previews") or [])
        pct = int(self.preview_percent_slider.value()) if hasattr(self, "preview_percent_slider") else 20
        preview_count = 0
        if previews:
            preview_count = max(1, int(len(previews) * (pct / 100.0)))
        for artifact in previews[:preview_count]:
            rows.append((tt("Mask previews", self.lang), artifact))
        if hasattr(self, "preview_percent_label"):
            self.preview_percent_label.setText(f"{pct}% ({preview_count})")
        return rows

    def _artifact_preview_path(self, artifact):
        path = str((artifact or {}).get("absolute_path") or (artifact or {}).get("path") or "")
        return path if path else ""

    def _artifact_is_pixmap_like(self, artifact, path):
        fmt = str((artifact or {}).get("format") or "").lower()
        ext = os.path.splitext(str(path or ""))[1].lower().lstrip(".")
        return fmt in {"png", "jpg", "jpeg", "bmp"} or ext in {"png", "jpg", "jpeg", "bmp"}

    def _artifact_caption(self, section, artifact, path):
        name = str((artifact or {}).get("display_name") or (artifact or {}).get("type") or section)
        if path:
            tail = os.path.basename(path) or path
            return f"{section}\n{name}\n{tail}"
        return f"{section}\n{name}"

    def _add_preview_text(self, row, column, text):
        label = QLabel(str(text or ""))
        label.setWordWrap(True)
        label.setMinimumWidth(180)
        self.preview_grid.addWidget(label, row, column)

    def _add_preview_artifact(self, index, section, artifact):
        row = index // 3
        column = index % 3
        path = self._artifact_preview_path(artifact)
        container = QWidget()
        item_layout = QVBoxLayout(container)
        item_layout.setContentsMargins(0, 0, 0, 0)
        item_layout.setSpacing(4)
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignCenter)
        image_label.setMinimumSize(180, 92)
        if path and os.path.exists(path) and self._artifact_is_pixmap_like(artifact, path):
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                pixmap = pixmap.scaledToWidth(220, Qt.SmoothTransformation)
                image_label.setPixmap(pixmap)
            else:
                image_label.setText(path)
        elif path:
            image_label.setText(path)
        else:
            image_label.setText("-")
        image_label.setToolTip(path)
        caption = QLabel(self._artifact_caption(section, artifact, path))
        caption.setWordWrap(True)
        caption.setToolTip(path)
        item_layout.addWidget(image_label)
        item_layout.addWidget(caption)
        self.preview_grid.addWidget(container, row, column)

    def _populate_preview_gallery(self, *_args):
        self._clear_preview_gallery()
        rows = self._displayable_artifact_rows()
        if not rows:
            self._add_preview_text(0, 0, "\n".join([tt("No training curve artifact declared.", self.lang), tt("No mask preview artifact declared.", self.lang)]))
            return
        for index, (section, artifact) in enumerate(rows):
            self._add_preview_artifact(index, section, artifact)

    def _detail_text(self):
        lines = []
        curves = self.summary.get("curves") or []
        previews = self.summary.get("previews") or []
        lines.append(f"{tt('Training curves', self.lang)}: {len(curves)}")
        if not curves:
            lines.append(tt("No training curve artifact declared.", self.lang))
        lines.append(f"{tt('Mask previews', self.lang)}: {len(previews)}")
        if not previews:
            lines.append(tt("No mask preview artifact declared.", self.lang))
        warnings = self.summary.get("warnings") or []
        errors = self.summary.get("errors") or []
        if warnings:
            lines.append("")
            lines.append(tt("Warnings", self.lang))
            lines.extend(f"- {item}" for item in warnings)
        if errors:
            lines.append("")
            lines.append(tt("Errors", self.lang))
            lines.extend(f"- {item}" for item in errors)
        return "\n".join(lines)

    def _open_path(self, path):
        path = str(path or "")
        if not path or not os.path.exists(path):
            return False
        return QDesktopServices.openUrl(QUrl.fromLocalFile(path))
